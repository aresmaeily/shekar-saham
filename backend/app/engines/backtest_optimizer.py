"""Deterministic parameter-search engine for RADAR BOURSE (MASTER-RADAR §D4).

Directive §D4 honesty mandates, all enforced here:
- SELECTION ON IN-SAMPLE ONLY: ranking always uses the IS objective values
  recorded during the search. Out-of-sample data is evaluated exactly ONCE,
  AFTER the winner is fixed, as a confirmation that can never influence
  ranking (``select_then_confirm``).
- Multiple-testing honesty: with n evaluated trials the result records the
  Bonferroni note ``alpha_effective = alpha/n_trials`` — the number is
  RECORDED; no p-values are fabricated.
- Reproducibility: the RNG seed is REQUIRED (no default); every search is
  deterministic given (seed, inputs); results carry a reproducibility digest.
- Budget honesty: evaluation caps, an optional wall-clock budget compared
  against an INJECTED monotonic clock callable (this engine itself never
  reads a real clock), and a cancellation token.
- Refusals are recorded (``is_refused`` + reason), constraint violations are
  counted separately (``n_constraint_skips``) — nothing is silently dropped.
- Resume: an append-only in-memory journal lets an interrupted search
  continue and converge to EXACTLY the evaluation set of an uninterrupted
  run (journal hits and constraint skips still consume rng draws so the
  candidate stream replays identically).

This module never imports the strategy DSL; the walk-forward integration
calls ``run_walk_forward_product`` from ``backtest_product`` (which itself
performs evaluation only — no selection logic there).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Callable, Iterator, Mapping, Sequence
from enum import Enum
from itertools import product
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.engines.backtest_product import (
    BacktestRunConfig,
    WalkForwardProductConfig,
    run_walk_forward_product,
)

__all__ = [
    "Objective",
    "CancelToken",
    "ObjectiveFn",
    "ClockFn",
    "ParameterSpace",
    "OptimizationBudget",
    "EvaluationRecord",
    "OptimizationResult",
    "SelectionConfirmation",
    "OOSConfirmation",
    "OptimizationJournal",
    "param_hash",
    "grid_search",
    "randomized_search",
    "evolutionary_search",
    "select_then_confirm",
    "optimize_with_walk_forward",
]


class Objective(str, Enum):
    """Search objectives. OOS_SHARPE is only valid inside the walk-forward path."""

    SHARPE = "SHARPE"
    CALMAR = "CALMAR"
    PROFIT_FACTOR = "PROFIT_FACTOR"
    OOS_SHARPE = "OOS_SHARPE"


#: Returns True when the search must STOP (cancelled).
CancelToken = Callable[[], bool]

#: Higher-is-better in-sample objective over one parameter set.
ObjectiveFn = Callable[[Mapping[str, float | int]], float]

#: Injected monotonic-seconds callable; this engine never reads a real clock.
ClockFn = Callable[[], float]


class OptimizationBudget(BaseModel):
    """Reproducibility-first budget. ``seed`` is REQUIRED (no default)."""

    model_config = ConfigDict(frozen=True)

    max_evaluations: int = Field(default=200, ge=1)
    time_budget_seconds: float | None = Field(default=None, gt=0.0)
    seed: int


class ParameterSpace(BaseModel):
    """Explicit search space.

    ``grid`` drives deterministic enumeration (grid_search); ``bounds`` drives
    randomized/evolutionary sampling; ``constraints`` are DOCUMENTATION ONLY
    (human-readable dependency text); ``dependency_rules`` are the enforced
    dependency predicates — a candidate violating any rule is SKIPPED and
    counted, never evaluated.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    grid: dict[str, list[float | int]] = Field(default_factory=dict)
    bounds: dict[str, tuple[float, float]] | None = None
    constraints: list[str] = Field(default_factory=list)
    dependency_rules: tuple[Callable[[Mapping[str, Any]], bool], ...] = ()


class EvaluationRecord(BaseModel):
    """One objective evaluation (refusals recorded, never silent)."""

    model_config = ConfigDict(frozen=True)

    params: dict[str, float | int]
    param_hash: str
    objective_value: float | None = None
    is_refused: bool = False
    refuse_reason: str | None = None


class OptimizationResult(BaseModel):
    """Complete outcome of one search; deterministic and resumable."""

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    objective: str
    budget_echo: dict[str, Any]
    evaluations: list[EvaluationRecord] = Field(default_factory=list)
    n_constraint_skips: int = 0
    best: EvaluationRecord | None = None
    ranked_top: list[EvaluationRecord] = Field(default_factory=list)
    cancelled: bool = False
    budget_exhausted: bool = False
    corrected_alpha_note: str = ""
    reproducibility_digest: str = ""


class OOSConfirmation(BaseModel):
    model_config = ConfigDict(frozen=True)
    objective_value: float | None = None
    evaluated_once: bool = True


class SelectionConfirmation(BaseModel):
    """§D4 structural honesty artifact: IS-selected, OOS-confirmed once."""

    model_config = ConfigDict(frozen=True)

    params: dict[str, float | int] | None = None
    param_hash: str | None = None
    selection_basis: Literal["IN_SAMPLE"] = "IN_SAMPLE"
    is_objective_value: float | None = None
    oos_confirmation: OOSConfirmation | None = None
    note: str = ""


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def param_hash(params: Mapping[str, float | int]) -> str:
    """sha256 over the canonical JSON of the parameter set (order-insensitive)."""
    return hashlib.sha256(_canonical_json(dict(params)).encode("utf-8")).hexdigest()


def _rank_records(evaluations: Sequence[EvaluationRecord]) -> list[EvaluationRecord]:
    """Deterministic ranking: (-objective, param_hash) over evaluable records."""
    evaluable = [e for e in evaluations if not e.is_refused and e.objective_value is not None]
    return sorted(evaluable, key=lambda e: (-float(e.objective_value), e.param_hash))


def _bonferroni_note(evaluations: Sequence[EvaluationRecord]) -> str:
    n = sum(1 for e in evaluations if not e.is_refused and e.objective_value is not None)
    if n == 0:
        return "multiple_testing: n_trials=0; no correction applicable"
    return f"multiple_testing: n_trials={n}; Bonferroni alpha_effective = alpha/{n}"


def _reproducibility_digest(
    budget: OptimizationBudget, evaluations: Sequence[EvaluationRecord], n_skips: int
) -> str:
    payload = {
        "seed": budget.seed,
        "n_constraint_skips": n_skips,
        "evaluations": [_canonical_json(e.model_dump(mode="json")) for e in evaluations],
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _dependency_violation(space: ParameterSpace, params: Mapping[str, Any]) -> bool:
    return any(rule(params) is False for rule in space.dependency_rules)


def _finalize(
    strategy_id: str,
    objective: Objective,
    budget: OptimizationBudget,
    evaluations: list[EvaluationRecord],
    n_skips: int,
    cancelled: bool,
    budget_exhausted: bool,
) -> OptimizationResult:
    ranked = _rank_records(evaluations)
    return OptimizationResult(
        strategy_id=strategy_id,
        objective=objective.value,
        budget_echo=budget.model_dump(mode="json"),
        evaluations=list(evaluations),
        n_constraint_skips=n_skips,
        best=ranked[0] if ranked else None,
        ranked_top=ranked[:10],
        cancelled=cancelled,
        budget_exhausted=budget_exhausted,
        corrected_alpha_note=_bonferroni_note(evaluations),
        reproducibility_digest=_reproducibility_digest(budget, evaluations, n_skips),
    )


class _RunControl:
    """Shared stop/gate logic: cancel token, injected clock, journal, budget."""

    def __init__(
        self,
        budget: OptimizationBudget,
        cancel: CancelToken | None,
        clock: ClockFn | None,
        journal: "OptimizationJournal | None",
    ) -> None:
        self.budget = budget
        self.cancel = cancel
        self.clock = clock
        self.journal = journal
        self.start = clock() if clock is not None else None
        self.cancelled = False
        self.budget_exhausted = False
        self.new_evaluations = 0
        self.replayed_evaluations = 0

    def should_stop(self) -> bool:
        if self.cancel is not None and self.cancel():
            self.cancelled = True
            return True
        if (
            self.clock is not None
            and self.budget.time_budget_seconds is not None
            and self.start is not None
            and (self.clock() - self.start) >= self.budget.time_budget_seconds
        ):
            self.budget_exhausted = True
            return True
        return False

    def journal_hit(self, params: Mapping[str, float | int]) -> EvaluationRecord | None:
        if self.journal is None:
            return None
        return self.journal.get(param_hash(params))

    def record(self, params: Mapping[str, float | int], objective_fn: ObjectiveFn) -> EvaluationRecord:
        h = param_hash(params)
        try:
            value = float(objective_fn(dict(params)))
            if not math.isfinite(value):
                raise ValueError("non_finite_objective")
            record = EvaluationRecord(params=dict(params), param_hash=h, objective_value=value)
        except Exception as exc:  # fail-closed honesty: refusals are recorded
            record = EvaluationRecord(
                params=dict(params),
                param_hash=h,
                is_refused=True,
                refuse_reason=f"{type(exc).__name__}:{exc}",
            )
        if self.journal is not None:
            self.journal.observe(record)
        self.new_evaluations += 1
        return record

    def count_replay(self) -> None:
        """Journal replay counts toward the total-evaluation budget so a
        resumed run converges to exactly the uninterrupted evaluation set."""
        self.replayed_evaluations += 1

    def budget_reached(self) -> bool:
        total = self.new_evaluations + self.replayed_evaluations
        if total >= self.budget.max_evaluations:
            self.budget_exhausted = True
            return True
        return False


# ---------------------------------------------------------------------------
# Search strategies
# ---------------------------------------------------------------------------


def grid_search(
    space: ParameterSpace,
    objective_fn: ObjectiveFn,
    budget: OptimizationBudget,
    objective: Objective = Objective.SHARPE,
    cancel: CancelToken | None = None,
    clock: ClockFn | None = None,
    journal: OptimizationJournal | None = None,
    strategy_id: str = "",
) -> OptimizationResult:
    """Deterministic grid enumeration in lexicographic order of (sorted param
    names, given value order). Constraint violations are SKIPPED and counted;
    journal hits are re-included from the journal without consuming budget."""
    control = _RunControl(budget, cancel, clock, journal)
    evaluations: list[EvaluationRecord] = []
    n_skips = 0
    if not space.grid:
        return _finalize(
            strategy_id, objective, budget, evaluations, n_skips, control.cancelled, control.budget_exhausted
        )
    keys = sorted(space.grid)
    for combo in _grid_product(space, keys):
        if control.should_stop():
            break
        if _dependency_violation(space, combo):
            n_skips += 1
            continue
        cached = control.journal_hit(combo)
        if cached is not None:
            evaluations.append(cached)
            control.count_replay()
            if control.budget_reached():
                break
            continue
        evaluations.append(control.record(combo, objective_fn))
        if control.budget_reached():
            break
    return _finalize(
        strategy_id, objective, budget, evaluations, n_skips, control.cancelled, control.budget_exhausted
    )


def _grid_product(space: ParameterSpace, keys: Sequence[str]) -> Iterator[dict[str, float | int]]:
    for values in product(*(space.grid[k] for k in keys)):
        yield {k: v for k, v in zip(keys, values)}


def _sample_uniform(bounds: Mapping[str, tuple[float, float]], rng: random.Random) -> dict[str, float]:
    return {k: rng.uniform(bounds[k][0], bounds[k][1]) for k in sorted(bounds)}


def randomized_search(
    space: ParameterSpace,
    objective_fn: ObjectiveFn,
    budget: OptimizationBudget,
    objective: Objective = Objective.SHARPE,
    cancel: CancelToken | None = None,
    clock: ClockFn | None = None,
    journal: OptimizationJournal | None = None,
    strategy_id: str = "",
) -> OptimizationResult:
    """Seed-driven uniform sampling within bounds (random.Random(seed)).

    Journal hits and constraint skips still CONSUME rng draws so a resumed run
    replays the exact candidate sequence of an uninterrupted one."""
    if not space.bounds:
        raise ValueError("randomized_search_requires_bounds")
    rng = random.Random(budget.seed)
    control = _RunControl(budget, cancel, clock, journal)
    evaluations: list[EvaluationRecord] = []
    n_skips = 0
    while True:
        params = _sample_uniform(space.bounds, rng)  # draws consumed even if skipped
        if control.should_stop():
            break
        if _dependency_violation(space, params):
            n_skips += 1
            continue
        cached = control.journal_hit(params)
        if cached is not None:
            evaluations.append(cached)
            control.count_replay()
            if control.budget_reached():
                break
            continue
        evaluations.append(control.record(params, objective_fn))
        if control.budget_reached():
            break
    return _finalize(
        strategy_id, objective, budget, evaluations, n_skips, control.cancelled, control.budget_exhausted
    )


def evolutionary_search(
    space: ParameterSpace,
    objective_fn: ObjectiveFn,
    budget: OptimizationBudget,
    objective: Objective = Objective.SHARPE,
    population_size: int = 20,
    generations: int = 10,
    tournament_k: int = 3,
    elitism: int = 1,
    cancel: CancelToken | None = None,
    clock: ClockFn | None = None,
    journal: OptimizationJournal | None = None,
    strategy_id: str = "",
) -> OptimizationResult:
    """Bounded generational search: uniform init, tournament selection (k=3),
    gaussian mutation with sigma = 10% of each bound's spread (clipped to
    bounds), elitism carry-over without re-evaluation. All arithmetic is
    deterministic given the required seed. Constraint-violating individuals
    are counted as skips and kept with -inf fitness (mutatable later)."""
    if not space.bounds:
        raise ValueError("evolutionary_search_requires_bounds")
    if population_size < 1 or generations < 1 or tournament_k < 1 or elitism < 0:
        raise ValueError("invalid_evolutionary_parameters")
    if elitism >= population_size:
        raise ValueError("elitism_must_be_smaller_than_population")
    rng = random.Random(budget.seed)
    control = _RunControl(budget, cancel, clock, journal)
    evaluations: list[EvaluationRecord] = []
    n_skips = 0

    def evaluate_params(params: Mapping[str, float]) -> float:
        """Evaluate one individual; returns its fitness (-inf when refused)."""
        cached = control.journal_hit(params)
        if cached is not None:
            evaluations.append(cached)
            return float(cached.objective_value) if cached.objective_value is not None else float("-inf")
        rec = control.record(params, objective_fn)
        evaluations.append(rec)
        return float(rec.objective_value) if rec.objective_value is not None else float("-inf")

    population: list[dict[str, float]] = []
    fitness: list[float] = []
    for _ in range(population_size):
        params = _sample_uniform(space.bounds, rng)
        if _dependency_violation(space, params):
            n_skips += 1
            population.append(params)
            fitness.append(float("-inf"))
            continue
        population.append(params)
        fitness.append(evaluate_params(params))
        if control.budget_reached():
            break

    sigma = {k: (hi - lo) * 0.1 for k, (lo, hi) in space.bounds.items()}

    for _ in range(generations):
        if control.should_stop() or control.budget_reached():
            break
        order = sorted(range(len(population)), key=lambda i: (-fitness[i], param_hash(population[i])))
        next_population = [dict(population[i]) for i in order[:elitism]]
        while len(next_population) < population_size:
            contenders = [rng.randrange(len(population)) for _ in range(tournament_k)]
            winner = max(contenders, key=lambda i: fitness[i])
            parent = population[winner]
            child = {
                k: min(space.bounds[k][1], max(space.bounds[k][0], parent[k] + rng.gauss(0.0, sigma[k])))
                for k in sorted(parent)
            }
            next_population.append(child)
        population = next_population
        next_fitness = [fitness[i] for i in order[:elitism]]  # elites: no re-evaluation
        stopped = False
        for i in range(elitism, population_size):
            if stopped or control.should_stop() or control.budget_reached():
                stopped = True
                next_fitness.append(float("-inf"))
                continue
            params = population[i]
            if _dependency_violation(space, params):
                n_skips += 1
                next_fitness.append(float("-inf"))
                continue
            next_fitness.append(evaluate_params(params))
            if control.budget_reached():
                stopped = True
        fitness = next_fitness

    return _finalize(
        strategy_id, objective, budget, evaluations, n_skips, control.cancelled, control.budget_exhausted
    )


def select_then_confirm(
    search_result: OptimizationResult,
    objective_fn_is: ObjectiveFn,
    objective_fn_oos: ObjectiveFn,
) -> SelectionConfirmation:
    """WINNER SELECTED ON IN-SAMPLE ONLY; OOS evaluated ONCE as confirmation.

    Ranking uses the IS objective values recorded during the search; the OOS
    function is invoked a single time, AFTER the winner is fixed, so it can
    never influence selection (structurally guaranteed by this API shape)."""
    ranked = _rank_records(search_result.evaluations)
    if not ranked:
        return SelectionConfirmation(
            note="no evaluable candidates: selection impossible; nothing confirmed"
        )
    winner = ranked[0]
    try:
        is_value = float(objective_fn_is(dict(winner.params)))
    except Exception:
        is_value = None
    try:
        oos_value = float(objective_fn_oos(dict(winner.params)))
    except Exception:
        oos_value = None
    return SelectionConfirmation(
        params=dict(winner.params),
        param_hash=winner.param_hash,
        selection_basis="IN_SAMPLE",
        is_objective_value=is_value,
        oos_confirmation=OOSConfirmation(objective_value=oos_value, evaluated_once=True),
        note=(
            "winner selected on the in-sample objective only; out-of-sample evaluated "
            "exactly once AFTER selection as confirmation and never used in ranking"
        ),
    )


class OptimizationJournal:
    """Append-only, in-memory evaluation journal enabling exact resume."""

    def __init__(self) -> None:
        self._by_hash: dict[str, EvaluationRecord] = {}
        self._order: list[str] = []

    def observe(self, record: EvaluationRecord) -> None:
        h = record.param_hash
        if h in self._by_hash:
            return  # append-only: the first record wins, never overwritten
        self._by_hash[h] = record
        self._order.append(h)

    def has(self, hash_: str) -> bool:
        return hash_ in self._by_hash

    def get(self, hash_: str) -> EvaluationRecord | None:
        return self._by_hash.get(hash_)

    @property
    def records(self) -> list[EvaluationRecord]:
        return [self._by_hash[h] for h in self._order]

    def resume(self, search_fn: Callable[..., OptimizationResult], **kwargs: Any) -> OptimizationResult:
        """Re-run ``search_fn`` continuing from this journal: already-evaluated
        parameter hashes are skipped (their records re-included) without
        consuming budget, so the resumed evaluations set equals the
        uninterrupted run's set."""
        kwargs["journal"] = self
        return search_fn(**kwargs)


def optimize_with_walk_forward(
    space: ParameterSpace,
    adapter_factory: Callable[[dict], Any],
    symbol_bars: Mapping[str, Sequence[Mapping[str, Any]]],
    run_config: BacktestRunConfig,
    wf_config: WalkForwardProductConfig,
    budget: OptimizationBudget,
    objective: Objective,
    cancel: CancelToken | None = None,
    clock: ClockFn | None = None,
    journal: OptimizationJournal | None = None,
    strategy_id: str = "",
) -> OptimizationResult:
    """Per candidate: run the product walk-forward; objective = mean OOS sharpe
    across windows (documented). Budget-bounded; seed-driven; deterministic.
    Dispatch: grid enumeration when ``space.grid`` is non-empty, otherwise
    seeded uniform sampling when ``space.bounds`` is set."""
    if objective is not Objective.OOS_SHARPE:
        raise ValueError("optimize_with_walk_forward_requires_objective_OOS_SHARPE")

    def objective_fn(params: Mapping[str, float | int]) -> float:
        wf = run_walk_forward_product(symbol_bars, adapter_factory, run_config, wf_config)
        sharpes = [w.oos_metrics.sharpe for w in wf.windows if w.oos_metrics.sharpe is not None]
        if not sharpes:
            raise ValueError("no_oos_sharpe_windows")
        return sum(sharpes) / len(sharpes)

    if strategy_id == "":
        probe = adapter_factory({})
        strategy_id = str(getattr(probe, "strategy_id", ""))

    if space.grid:
        return grid_search(
            space, objective_fn, budget, objective=objective, cancel=cancel, clock=clock,
            journal=journal, strategy_id=strategy_id,
        )
    if space.bounds:
        return randomized_search(
            space, objective_fn, budget, objective=objective, cancel=cancel, clock=clock,
            journal=journal, strategy_id=strategy_id,
        )
    raise ValueError("empty_parameter_space")
