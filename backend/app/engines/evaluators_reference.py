"""AI-4 deterministic reference evaluators for RADAR BOURSE.

Corpus loci (2026-10-02 amendment corpus; see also
AI4_AI7_P343_DEPENDENCY_MATRIX.md §AI-4):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 87-90: "AI-4 --- Governed
  Generation: AI-generated filters/indicators/strategy specifications only
  through sandbox -> deterministic evaluation -> lifecycle -> approval."
- 02 lines 158-159: hypotheses enter the governed research lifecycle "when
  a suitable deterministic evaluator exists"; generated artifacts "remain
  candidates until isolated tests, evaluation gates and required human
  approval are passed."
- D-AI-19: financial truth (metrics, evaluation) remains DETERMINISTIC —
  no LLM, no stochastic scoring anywhere in this module.
- Dependency matrix §AI-4: contract layer + synthetic tests (pre-G2 class).

This module provides the reference deterministic evaluators the
``app.domain.governed_generation`` bindings anticipate:

- ``evaluate_filter_dsl`` evaluates a Filter-DSL expression string against
  a supplied row set via the PUBLIC safe evaluator of
  ``app.engines.filter_dsl`` (never eval/exec; malformed expressions are
  refused by filter_dsl's own safety layer and surfaced honestly as a
  refusal outcome, never swallowed and never turned into a metric);
- ``evaluate_signal_pairs`` computes hit-rate / return-spread metrics over
  supplied (entered, realized_return) pairs with exact rational
  arithmetic;
- ``evaluate_pass_rate`` computes a bounded pass-rate metric.

Each evaluator returns a frozen outcome record carrying canonical
``governed_generation.EvaluationMetric`` values; identical inputs produce
identical records. ``reference_evaluator_registry()`` binds them into a
canonical ``EvaluatorRegistry`` (``service_class`` structurally
DETERMINISTIC; dataset origins closed to SYNTHETIC/PAPER).

No LLM, no network, no I/O, no clock reads, no execution of candidates —
the evaluators consume supplied data only.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.domain.evidence import SCHEMA_VERSION
from app.domain.governed_generation import (
    DatasetOrigin,
    DeterministicEvaluatorBinding,
    EvaluationMetric,
    EvaluatorRegistry,
    GeneratedCandidate,
)
from app.engines.filter_dsl import FilterError, run_filter

__all__ = [
    "REFERENCE_EVALUATOR_VERSION",
    "REFERENCE_FILTER_DSL_EVALUATOR_ID",
    "REFERENCE_SIGNAL_PAIRS_EVALUATOR_ID",
    "REFERENCE_PASS_RATE_EVALUATOR_ID",
    "REFERENCE_SOFTWARE_CHANGE_EVALUATOR_ID",
    "FilterDslEvaluation",
    "SignalPairEvaluation",
    "PassRateEvaluation",
    "SoftwareChangeEvaluation",
    "evaluate_filter_dsl",
    "evaluate_signal_pairs",
    "evaluate_pass_rate",
    "evaluate_software_change_proposal",
    "reference_evaluator_registry",
]

REFERENCE_EVALUATOR_VERSION = "1.0.0"

REFERENCE_FILTER_DSL_EVALUATOR_ID = "reference.filter_dsl"
REFERENCE_SIGNAL_PAIRS_EVALUATOR_ID = "reference.signal_pairs"
REFERENCE_PASS_RATE_EVALUATOR_ID = "reference.pass_rate"
REFERENCE_SOFTWARE_CHANGE_EVALUATOR_ID = "reference.software_change_proposal"

#: Pre-G2 dataset closure (02:202): SYNTHETIC/PAPER only, LIVE excluded.
_ACCEPTED_DATASET_ORIGINS: tuple[DatasetOrigin, ...] = ("SYNTHETIC", "PAPER")

_METRIC_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


def _exact_ratio(numerator: int, denominator: int) -> float:
    """Exact rational → float, converted exactly once (no rounding chain)."""
    return float(Fraction(numerator, denominator))


# ---------------------------------------------------------------------------
# Outcome records (frozen; deterministic equality for the same inputs)
# ---------------------------------------------------------------------------


class FilterDslEvaluation(BaseModel):
    """Outcome of one Filter-DSL evaluation.

    ``accepted=False`` records filter_dsl's own safety refusal verbatim
    (``refusal_code=filter_dsl_refused`` + the DSL layer's detail) — a
    malformed candidate is surfaced, never scored and never silently
    dropped.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    accepted: bool
    refusal_code: str | None = None
    refusal_detail: str | None = None
    evaluated_rows: int | None = Field(default=None, ge=0)
    matched_rows: int | None = Field(default=None, ge=0)
    hit_rate: float | None = None
    metrics: tuple[EvaluationMetric, ...] = ()


class SignalPairEvaluation(BaseModel):
    """Outcome of one signal/pairs evaluation (exact-arithmetic metrics)."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    accepted: Literal[True] = True
    pair_count: int = Field(ge=1)
    entered_count: int = Field(ge=0)
    metrics: tuple[EvaluationMetric, ...] = ()


class PassRateEvaluation(BaseModel):
    """Outcome of one pass-rate evaluation (bounded, deterministic)."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    accepted: Literal[True] = True
    passed: int = Field(ge=0)
    total: int = Field(ge=1)
    metrics: tuple[EvaluationMetric, ...] = ()


class SoftwareChangeEvaluation(BaseModel):
    """Outcome of one SOFTWARE_CHANGE_PROPOSAL structural evaluation.

    ``accepted=False`` records a malformed-candidate refusal verbatim
    (``refusal_code`` + detail) — surfaced, never scored and never silently
    dropped (same honesty discipline as ``FilterDslEvaluation``). A wrong-kind
    input is a caller contract error and raises instead (see the evaluator).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    accepted: bool
    refusal_code: str | None = None
    refusal_detail: str | None = None
    candidate_id: str = Field(min_length=1)
    metrics: tuple[EvaluationMetric, ...] = ()


def _metrics(*name_values: tuple[str, float]) -> tuple[EvaluationMetric, ...]:
    return tuple(EvaluationMetric(name=name, value=value) for name, value in name_values)


# ---------------------------------------------------------------------------
# Reference evaluator 1: Filter DSL over a supplied row set
# ---------------------------------------------------------------------------


def evaluate_filter_dsl(
    specification: str,
    rows: Sequence[Mapping[str, Any]],
) -> FilterDslEvaluation:
    """Evaluate a Filter-DSL expression string against supplied rows.

    The evaluation goes through ``filter_dsl.run_filter`` — the public
    safe evaluator (AST-validated, allow-listed fields/functions, no
    eval/exec). Deterministic behaviour:

    - ``empty_row_set`` — metrics over zero rows would be invented, so an
      empty row set is refused outright;
    - a malformed/unsafe DSL string raises ``FilterError`` inside
      filter_dsl; that refusal is surfaced HONESTLY as
      ``accepted=False`` / ``refusal_code=filter_dsl_refused`` with the
      DSL layer's message preserved — no metric is produced;
    - otherwise ``hit_rate = matched / evaluated`` with exact rational
      arithmetic (converted to float once) plus the raw counts as metrics.
    """
    if rows is None or len(rows) == 0:
        raise ValueError("empty_row_set")
    rows_list = [dict(r) for r in rows]
    try:
        matched = run_filter(specification, rows_list)
    except FilterError as exc:
        return FilterDslEvaluation(
            accepted=False,
            refusal_code="filter_dsl_refused",
            refusal_detail=str(exc),
        )
    total = len(rows_list)
    hit_rate = _exact_ratio(len(matched), total)
    return FilterDslEvaluation(
        accepted=True,
        evaluated_rows=total,
        matched_rows=len(matched),
        hit_rate=hit_rate,
        metrics=_metrics(
            ("hit_rate", hit_rate),
            ("matched_rows", float(len(matched))),
            ("evaluated_rows", float(total)),
        ),
    )


# ---------------------------------------------------------------------------
# Reference evaluator 2: hit-rate / return-spread over supplied pairs
# ---------------------------------------------------------------------------


def evaluate_signal_pairs(
    pairs: Sequence[tuple[bool, float]],
) -> SignalPairEvaluation:
    """Compute hit-rate / return metrics over supplied signal pairs.

    Each pair is ``(entered, realized_return)``. Deterministic refusals:
    ``empty_pairs``; ``entered_must_be_boolean`` (strict bool; 0/1 ints
    are refused so signal semantics cannot drift); and
    ``return_must_be_finite`` (NaN/inf returns would poison every mean).

    Exact rational arithmetic over the stated decimal inputs; metrics:
    ``hit_rate`` (share of pairs entered), ``mean_return_when_entered`` /
    ``mean_return_when_flat`` (emitted only for non-empty sides — nothing
    invented), and ``return_spread`` (mean_entered − mean_flat, emitted
    only when BOTH sides exist).
    """
    if pairs is None or len(pairs) == 0:
        raise ValueError("empty_pairs")
    entered_returns: list[Fraction] = []
    flat_returns: list[Fraction] = []
    for entered, realized_return in pairs:
        if not isinstance(entered, bool):
            raise ValueError("entered_must_be_boolean")
        if isinstance(realized_return, bool) or not isinstance(realized_return, (int, float)):
            raise ValueError("return_must_be_finite")
        if not math.isfinite(float(realized_return)):
            raise ValueError("return_must_be_finite")
        value = Fraction(str(realized_return))
        (entered_returns if entered else flat_returns).append(value)
    total = len(pairs)
    entered_count = len(entered_returns)
    metrics: list[EvaluationMetric] = [
        EvaluationMetric(name="hit_rate", value=_exact_ratio(entered_count, total))
    ]
    if entered_returns:
        mean_entered = sum(entered_returns, Fraction(0)) / Fraction(len(entered_returns))
        metrics.append(EvaluationMetric(name="mean_return_when_entered", value=float(mean_entered)))
    if flat_returns:
        mean_flat = sum(flat_returns, Fraction(0)) / Fraction(len(flat_returns))
        metrics.append(EvaluationMetric(name="mean_return_when_flat", value=float(mean_flat)))
    if entered_returns and flat_returns:
        spread = (
            sum(entered_returns, Fraction(0)) / Fraction(len(entered_returns))
            - sum(flat_returns, Fraction(0)) / Fraction(len(flat_returns))
        )
        metrics.append(EvaluationMetric(name="return_spread", value=float(spread)))
    return SignalPairEvaluation(
        pair_count=total,
        entered_count=entered_count,
        metrics=tuple(metrics),
    )


# ---------------------------------------------------------------------------
# Reference evaluator 3: bounded pass-rate
# ---------------------------------------------------------------------------


def evaluate_pass_rate(passed: int, total: int) -> PassRateEvaluation:
    """Bounded deterministic pass-rate (e.g. golden-set / regression runs).

    Refusals: ``total_must_be_positive`` (a rate over zero trials is not a
    measurement) and ``passed_out_of_range`` (passed outside [0, total]).
    Exact rational arithmetic: ``pass_rate = passed / total``.
    """
    if not isinstance(total, int) or isinstance(total, bool) or total < 1:
        raise ValueError("total_must_be_positive")
    if not isinstance(passed, int) or isinstance(passed, bool) or not 0 <= passed <= total:
        raise ValueError("passed_out_of_range")
    rate = _exact_ratio(passed, total)
    return PassRateEvaluation(
        passed=passed,
        total=total,
        metrics=_metrics(("pass_rate", rate)),
    )


# ---------------------------------------------------------------------------
# Reference evaluator 4: SOFTWARE_CHANGE_PROPOSAL structural completeness
# ---------------------------------------------------------------------------


_SOFTWARE_CHANGE_MANDATORY_FIELDS: tuple[str, ...] = (
    "baseline",
    "expected_benefit",
    "evidence_summary",
    "uncertainty",
    "cost",
    "risks",
    "rollback_plan",
    "evaluation_design",
)


def evaluate_software_change_proposal(
    candidate: GeneratedCandidate,
) -> SoftwareChangeEvaluation:
    """Structural completeness evaluation of a SOFTWARE_CHANGE_PROPOSAL.

    DETERMINISTIC service class; no semantic quality judgment, no candidate
    execution, no network, no I/O, no clock reads (02:179 defines the eight
    mandatory proposal fields; D-AI-12/13 no-production-mutation discipline
    makes the rollback plan the load-bearing field).

    Refusals:
    - a candidate of any other kind raises ``ValueError("kind_must_be_"
      "software_change_proposal")`` — a caller contract error, exactly like
      ``evaluate_pass_rate``'s out-of-range refusals;
    - a candidate that reaches this evaluator with ``proposal=None`` (only
      possible through a validation-bypassing constructor such as
      ``model_construct``, because the GeneratedCandidate kind↔proposal
      model_validator refuses the pairing) is surfaced as an honest refusal
      record ``accepted=False`` with ``refusal_code="proposal_fields_required"
      — never scored, never silently dropped.

    Metrics (exact rational arithmetic, one float conversion each):
    - ``mandatory_fields_present`` / ``mandatory_fields_total`` (8) and
      ``completeness_ratio = present / total`` — fields are strip-checked
      from the actual values, never assumed from the schema ``min_length``;
    - ``rollback_plan_present`` / ``evaluation_design_present`` (0.0/1.0).

    ``accepted=True`` iff all eight fields are non-empty. This measures
    STRUCTURAL admissibility only: the semantic quality of the proposal text
    is not scored — no invented thresholds, no placeholder semantics.

    Registry note: the canonical ``reference_evaluator_registry()`` does NOT
    bind this evaluator (existing tests pin the three-binding registry and
    the honest ``None`` gap for this kind); the binding is a recorded
    follow-up for the next registry revision. The evaluator is fully
    callable and bindable via ``DeterministicEvaluatorBinding`` with
    ``evaluation_contract="app.engines.evaluators_reference."
    "evaluate_software_change_proposal"``.
    """
    if candidate.kind != "SOFTWARE_CHANGE_PROPOSAL":
        raise ValueError("kind_must_be_software_change_proposal")
    proposal = candidate.proposal
    if proposal is None:
        return SoftwareChangeEvaluation(
            accepted=False,
            refusal_code="proposal_fields_required",
            refusal_detail=(
                "SOFTWARE_CHANGE_PROPOSAL candidate carries no proposal fields"
            ),
            candidate_id=candidate.candidate_id,
            metrics=(),
        )
    values = [getattr(proposal, name) for name in _SOFTWARE_CHANGE_MANDATORY_FIELDS]
    present = sum(1 for value in values if isinstance(value, str) and value.strip())
    total = len(_SOFTWARE_CHANGE_MANDATORY_FIELDS)
    accepted = present == total
    metrics = _metrics(
        ("mandatory_fields_present", float(present)),
        ("mandatory_fields_total", float(total)),
        ("completeness_ratio", _exact_ratio(present, total)),
        (
            "rollback_plan_present",
            1.0 if isinstance(proposal.rollback_plan, str) and proposal.rollback_plan.strip() else 0.0,
        ),
        (
            "evaluation_design_present",
            1.0 if isinstance(proposal.evaluation_design, str) and proposal.evaluation_design.strip() else 0.0,
        ),
    )
    return SoftwareChangeEvaluation(
        accepted=accepted,
        refusal_code=None if accepted else "mandatory_fields_incomplete",
        refusal_detail=None
        if accepted
        else "completed "
        + str(present)
        + "/"
        + str(total)
        + " mandatory proposal fields",
        candidate_id=candidate.candidate_id,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Registry factory (canonical bindings, DETERMINISTIC service class only)
# ---------------------------------------------------------------------------


def reference_evaluator_registry() -> EvaluatorRegistry:
    """Factory: the canonical ``EvaluatorRegistry`` of reference evaluators.

    Bindings are deterministic in kind coverage; every binding declares
    ``service_class=DETERMINISTIC`` (the only value the schema admits) and
    accepts only the pre-G2 dataset origins (SYNTHETIC/PAPER). Kinds with
    NO binding here resolve to ``None`` — an honest gap, never a placeholder
    evaluator. Unbound-kind honesty at this registry revision (WS-5 wave,
    2026-11-02): SOFTWARE_CHANGE_PROPOSAL has a callable deterministic
    reference evaluator (``evaluate_software_change_proposal``) that is
    deliberately NOT bound here — existing tests pin the three-binding
    registry shape and the ``None`` resolution for this kind, and the
    additive-only discipline forbids amending them in this wave (binding =
    recorded follow-up); FUNDAMENTAL_FEATURE has no evaluator at all and
    also resolves to ``None``.
    """
    bindings = (
        DeterministicEvaluatorBinding(
            evaluator_id=REFERENCE_FILTER_DSL_EVALUATOR_ID,
            evaluator_version=REFERENCE_EVALUATOR_VERSION,
            service_class="DETERMINISTIC",
            evaluates_kinds=("FILTER",),
            accepted_dataset_origins=_ACCEPTED_DATASET_ORIGINS,
            evaluation_contract="app.engines.evaluators_reference.evaluate_filter_dsl",
        ),
        DeterministicEvaluatorBinding(
            evaluator_id=REFERENCE_SIGNAL_PAIRS_EVALUATOR_ID,
            evaluator_version=REFERENCE_EVALUATOR_VERSION,
            service_class="DETERMINISTIC",
            evaluates_kinds=("STRATEGY_SPEC",),
            accepted_dataset_origins=_ACCEPTED_DATASET_ORIGINS,
            evaluation_contract="app.engines.evaluators_reference.evaluate_signal_pairs",
        ),
        DeterministicEvaluatorBinding(
            evaluator_id=REFERENCE_PASS_RATE_EVALUATOR_ID,
            evaluator_version=REFERENCE_EVALUATOR_VERSION,
            service_class="DETERMINISTIC",
            evaluates_kinds=("SCORING_RULE", "INDICATOR"),
            accepted_dataset_origins=_ACCEPTED_DATASET_ORIGINS,
            evaluation_contract="app.engines.evaluators_reference.evaluate_pass_rate",
        ),
    )
    return EvaluatorRegistry(bindings=bindings)
