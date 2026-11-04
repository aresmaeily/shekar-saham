"""walk_forward.py — W3-3C walk-forward orchestration engine (additive).

Pure orchestration ONLY: window computation, per-fold seed derivation, the
fold loop (select in-sample -> confirm out-of-sample once) and aggregation.
This module never imports the strategy DSL and never touches the seeded-data
loader; the caller (strategy_lab.py POST /walkforward) injects the per-window
objective evaluator, which rides the SAME seeded-series path as /backtest and
/optimize. No wall clock is read anywhere in this module; identical inputs
produce byte-identical results.

PINNED WINDOW MATH (0-indexed bar positions over the seeded series; end
indexes are EXCLUSIVE — python slice convention bars[start:end]):
    fold i (i = 0..n-1):
        train window = bars [i*test_bars, i*test_bars + train_bars)
        test  window = bars [i*test_bars + train_bars,
                             i*test_bars + train_bars + test_bars)
    - FIT RULE (fail-closed): train_bars + n * test_bars <= available,
      where available = number of seeded bars returned for
      (symbol, timeframe, count). Otherwise ValueError.
    - Test windows are rolling and NON-OVERLAPPING (fold i's test window ends
      exactly where fold i+1's is still train-only... precisely: test windows
      are disjoint because fold i's test end == i*test_bars + train_bars +
      test_bars <= (i+1)*test_bars + train_bars == fold i+1's test start);
      chronological order. NOTE: a later fold's TRAIN window may overlap an
      earlier fold's TEST window — that is the definition of rolling
      walk-forward; the discipline is per fold (below).
    - NO fold ever sees data beyond its own windows for selection: slices are
      cut BEFORE any evaluation and each closure captures only its own slice.

PINNED PER-FOLD SEED DERIVATION:
    fold_seed(i) = base_seed + i        (deterministic; recorded per fold)

OOS-CONFIRMED-ONCE DISCIPLINE (structural, not convention):
    1. Selection: per fold, the optimizer's ``grid_search`` runs ONLY over
       that fold's train window through the injected IS closure. Ranking is
       computed by the optimizer engine from the IS EvaluationRecords alone.
    2. Confirmation: the optimizer's ``select_then_confirm`` is then called
       with the SAME IS closure and the fold's OOS closure. By that engine
       function's API shape the OOS closure is invoked EXACTLY ONCE, AFTER
       the winner is frozen, and its value is returned as confirmation
       metadata only — there is no code path by which it can enter ranking
       (the optimizer ranks ``search.evaluations``, which only ever contains
       train-window records). Fold rows therefore carry ``oos_eval_count``
       (0 when the fold had no evaluable candidate, else 1) which NEVER
       enters ``evaluated_count`` (the IS selection-trial count).
    3. ``select_then_confirm`` re-evaluates the IS objective once on the
       frozen winner — a recomputation of an already-ranked point, not a new
       selection trial.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.engines.backtest_optimizer import (
    Objective,
    OptimizationBudget,
    ParameterSpace,
    grid_search,
    select_then_confirm,
)

__all__ = [
    "WALK_FORWARD_ENGINE_VERSION",
    "SELECTION_BASIS",
    "FoldWindows",
    "WalkForwardResult",
    "fold_windows",
    "per_fold_seed",
    "aggregate_fold_stats",
    "reproducibility_digest",
    "run_walk_forward",
]

WALK_FORWARD_ENGINE_VERSION = "WALK-FORWARD-1.0.0"

#: Response pin: selection happens per fold on that fold's train window ONLY.
SELECTION_BASIS = "IN_SAMPLE_PER_FOLD"

#: One fold = ((train_start, train_end), (test_start, test_end)); half-open
#: index pairs over the seeded series (bars[start:end]).
FoldWindows = tuple[tuple[int, int], tuple[int, int]]

#: Per-window objective evaluator injected by the caller: (params, window
#: bars) -> higher-is-better objective float. Raises when the objective is
#: unavailable (e.g. no trades) — the optimizer records the refusal.
EvaluateFn = Callable[[Mapping[str, float | int], Sequence[Mapping[str, Any]]], float]


def fold_windows(available: int, n: int, train_bars: int, test_bars: int) -> list[FoldWindows]:
    """Compute the pinned fold windows (see module docstring for the math).

    Raises ValueError on degenerate arguments (negative ``available``, non-
    positive ``n``/``train_bars``/``test_bars``) and on the unfit case
    ``train_bars + n * test_bars > available`` — the unfit message names BOTH
    numbers so callers can surface an honest available-vs-required 422.

    NOTE: the product bounds (n 2..12, train_bars >= 30, test_bars >= 10) are
    enforced at the API body model; this engine function is deliberately
    general and enforces only mathematical validity + the fit rule.
    """
    if not isinstance(available, int) or isinstance(available, bool) or available < 0:
        raise ValueError(f"fold_windows_invalid_available: available={available!r}")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError(f"fold_windows_invalid_n: n={n!r} (must be >= 1)")
    if not isinstance(train_bars, int) or isinstance(train_bars, bool) or train_bars < 1:
        raise ValueError(f"fold_windows_invalid_train_bars: train_bars={train_bars!r}")
    if not isinstance(test_bars, int) or isinstance(test_bars, bool) or test_bars < 1:
        raise ValueError(f"fold_windows_invalid_test_bars: test_bars={test_bars!r}")
    required = train_bars + n * test_bars
    if required > available:
        raise ValueError(
            f"fold_windows_unfit: required train_bars + n*test_bars = {required} bars"
            f" > available {available} bars"
        )
    windows: list[FoldWindows] = []
    for i in range(n):
        train_start = i * test_bars
        train_end = train_start + train_bars
        test_start = train_end
        test_end = test_start + test_bars
        windows.append(((train_start, train_end), (test_start, test_end)))
    return windows


def per_fold_seed(seed: int, fold_index: int) -> int:
    """PINNED derivation (do not change): fold_seed(i) = seed + i.

    Deterministic and collision-free across folds of one run; recorded per
    fold row and folded into the reproducibility digest.
    """
    return int(seed) + int(fold_index)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def reproducibility_digest(
    body_params: Mapping[str, Any], fold_rows: Sequence[Mapping[str, Any]]
) -> str:
    """sha256 over the canonical JSON of {"body": body_params, "folds": rows}.

    Mirrors the optimizer engine's digest discipline (canonical json -> sha256).
    The caller MUST pass only deterministic body parameters — never a trust
    envelope (its ``checked_at`` is a wall-clock instant by canonical design
    and would break reproducibility).
    """
    payload = {"body": dict(body_params), "folds": [dict(row) for row in fold_rows]}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def aggregate_fold_stats(
    fold_rows: Sequence[Mapping[str, Any]], objective: "Objective | str"
) -> dict[str, Any]:
    """Aggregate per-fold rows into the response's ``aggregate`` block.

    - Stats are computed over folds with a non-None ``oos_objective`` (a fold
      whose train window produced no evaluable candidate — or whose single OOS
      confirmation was refused — contributes to ``n_folds`` but not to the
      OOS statistics; ``confirmed_folds`` counts the contributors).
    - ``oos_evaluated_once_per_fold`` is the structural invariant "every fold
      touched its test window AT MOST once (exactly once when a winner was
      selected) and the test window never influenced selection"; a value of
      False would indicate an engine-contract violation.
    """
    objective_value = getattr(objective, "value", objective)
    oos_values = [
        float(row["oos_objective"]) for row in fold_rows if row.get("oos_objective") is not None
    ]
    confirmed = sum(1 for row in fold_rows if row.get("best_params") is not None)
    once_ok = all(int(row.get("oos_eval_count", 0)) <= 1 for row in fold_rows)
    if oos_values:
        stats: dict[str, Any] = {
            "oos_mean": sum(oos_values) / len(oos_values),
            "oos_median": statistics.median(oos_values),
            "oos_min": min(oos_values),
            "oos_max": max(oos_values),
        }
    else:
        stats = {"oos_mean": None, "oos_median": None, "oos_min": None, "oos_max": None}
    return {
        "n_folds": len(fold_rows),
        "objective": str(objective_value),
        "confirmed_folds": confirmed,
        "positive_folds": sum(1 for v in oos_values if v > 0.0),
        **stats,
        "selection_basis": SELECTION_BASIS,
        "oos_evaluated_once_per_fold": bool(once_ok),
    }


@dataclass(frozen=True)
class WalkForwardResult:
    """Complete outcome of one walk-forward run (json-ready, deterministic)."""

    folds: list[dict[str, Any]]
    aggregate: dict[str, Any]
    bonferroni_note: str
    reproducibility_digest: str


def run_walk_forward(
    bars: Sequence[Mapping[str, Any]],
    *,
    n: int,
    train_bars: int,
    test_bars: int,
    space: ParameterSpace,
    objective: Objective,
    seed: int,
    max_evals_per_fold: int,
    evaluate: EvaluateFn,
    digest_body: Mapping[str, Any],
    strategy_id: str = "",
) -> WalkForwardResult:
    """Per-fold IS-selection + OOS-confirmed-once over ``bars``.

    Contract (all pinned in the module docstring):
    - windows from :func:`fold_windows` (ValueError on unfit — callers turn it
      into an honest available-vs-required 422);
    - per-fold seed = :func:`per_fold_seed`(seed, fold_index);
    - per fold: ``grid_search`` over the TRAIN window only -> winner frozen on
      IS only -> ``select_then_confirm`` evaluates the TEST window exactly
      once with the frozen winner (structurally unable to influence ranking —
      the optimizer's ranking reads only the IS EvaluationRecords, and the OOS
      closure is invoked a single time AFTER the winner is fixed);
    - aggregation via :func:`aggregate_fold_stats`; Bonferroni note reuses the
      optimizer engine's note format over the TOTAL evaluable IS trials across
      folds (each fold row also carries the engine's own per-fold note);
    - reproducibility digest over ``digest_body`` (caller-pinned body echo)
      + the fold table.
    """
    windows = fold_windows(len(bars), n, train_bars, test_bars)
    fold_rows: list[dict[str, Any]] = []
    total_evaluable = 0
    for i, (train_window, test_window) in enumerate(windows):
        fold_seed = per_fold_seed(seed, i)
        train_slice = list(bars[train_window[0]:train_window[1]])
        test_slice = list(bars[test_window[0]:test_window[1]])

        def is_objective(params: Mapping[str, float | int], _train: list = train_slice) -> float:
            return evaluate(params, _train)

        def oos_objective(params: Mapping[str, float | int], _test: list = test_slice) -> float:
            return evaluate(params, _test)

        budget = OptimizationBudget(max_evaluations=max_evals_per_fold, seed=fold_seed)
        search = grid_search(space, is_objective, budget, objective=objective, strategy_id=strategy_id)
        # OOS-confirmed-once, structurally: `search.evaluations` contains ONLY
        # train-window records (grid_search never sees the test slice), and
        # select_then_confirm (a) ranks from those records alone, then (b)
        # invokes the oos closure EXACTLY ONCE with the already-frozen winner.
        # The OOS value is returned as confirmation metadata and has no code
        # path into ranking. The test window is never part of this fold's
        # train slice (non-overlapping windows by fold_windows construction).
        confirmation = select_then_confirm(search, is_objective, oos_objective)
        oos_conf = confirmation.oos_confirmation
        has_winner = confirmation.params is not None
        evaluable = sum(
            1 for e in search.evaluations if not e.is_refused and e.objective_value is not None
        )
        total_evaluable += evaluable
        fold_rows.append(
            {
                "fold_index": i,
                "train": {"start_index": train_window[0], "end_index": train_window[1]},
                "test": {"start_index": test_window[0], "end_index": test_window[1]},
                "fold_seed": fold_seed,
                "best_params": dict(confirmation.params) if has_winner else None,
                "is_objective": confirmation.is_objective_value,
                "oos_objective": (oos_conf.objective_value if oos_conf is not None else None),
                "evaluated_count": len(search.evaluations),
                "evaluable_count": evaluable,
                "oos_eval_count": 1 if has_winner else 0,
                "oos_evaluated_once": bool(oos_conf and oos_conf.evaluated_once) if has_winner else False,
                "constraint_skips": search.n_constraint_skips,
                "budget_exhausted": search.budget_exhausted,
                "cancelled": search.cancelled,
                "bonferroni_note": search.corrected_alpha_note,
                "note": confirmation.note
                if has_winner
                else (
                    "no evaluable candidates in this fold's train window; "
                    "test window never touched (recorded, not silent)"
                ),
            }
        )
    aggregate = aggregate_fold_stats(fold_rows, objective)
    if total_evaluable == 0:
        bonferroni_note = (
            "multiple_testing: n_trials=0; no correction applicable"
            " (walk-forward per-fold IS selection)"
        )
    else:
        bonferroni_note = (
            f"multiple_testing: n_trials={total_evaluable};"
            f" Bonferroni alpha_effective = alpha/{total_evaluable}"
            " (walk-forward: selection runs per fold on that fold's train window;"
            " each fold row carries the engine's own note)"
        )
    digest = reproducibility_digest(digest_body, fold_rows)
    return WalkForwardResult(
        folds=fold_rows,
        aggregate=aggregate,
        bonferroni_note=bonferroni_note,
        reproducibility_digest=digest,
    )
