"""Evaluation statistics for research integrity (P3, purely additive).

Corpus loci (2026-10-02 amendment corpus):
- 02_EXECUTION_ROADMAP lines 27-30 ("P3 --- Evaluation Harness"): "Backtest,
  OOS, WFO, forward test, statistical evaluation, reproducibility, holdout
  and multiple-testing controls."
- 02 line 145 ("P3 --- Evaluation and research integrity"): "... holdout
  isolation, multiple-testing controls, ... and matured outcome labels."
- 06 Product Capability Charter, "Market interpretation": "A versioned
  Golden Set demonstrates baseline and extended capability metrics, false
  positives/negatives, confidence calibration ...".

Scope delivered here:
1. Exact multiple-testing adjustments (Bonferroni; Benjamini-Hochberg
   step-up) as pure functions with hand-verifiable arithmetic.
2. Family-level acceptance verdicts (`EvaluationFamily`,
   `adjusted_acceptance`) on a closed `MultipleTestingMethod` vocabulary.
   Unadjusted acceptance (NONE) is REFUSED for any family with more than
   one attempt via a deterministic reason code
   (`UNADJUSTED_ACCEPTANCE_IS_FORBIDDEN_FOR_FAMILIES_OVER_ONE`) — the
   honesty flag `unadjusted` on the verdict record is True only for the
   single-attempt case where NONE is permitted.
3. Confusion-count and precision/recall/false-positive-rate analysis of
   signalled trade outcomes against matured labels. This is the computed,
   deterministic replacement for the hardcoded "NOT_AVAILABLE" lane in the
   filter-intelligence presentation layer; THAT service is deliberately
   NOT modified here (additive-only task).

Rounding policy (explicit): no function in this module rounds. Every float
output is the exact IEEE-754 double produced by the arithmetic stated in
the docstring (multiplication by an integer count, a single division, min
over a finite set). Presentation rounding exists ONLY in `format_rate`,
which takes the digit count as an explicit parameter and is never used in
computation. Undefined rates are `None` plus a machine-readable reason
code — never faked as 0.0 (which would fabricate a measurement).

Determinism: no I/O, no network, no wall-clock, no randomness; every
timestamp/value is an explicit parameter. No claim of superiority over any
external system is made or implied anywhere in this module.
"""

from __future__ import annotations

import math
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

MultipleTestingMethod = Literal["NONE", "BONFERRONI", "BENJAMIN_HOCHBERG"]

#: Closed vocabulary of verdict outcomes. REFUSED verdicts are data (not
#: exceptions) so a caller cannot bypass them by catching an error.
AcceptanceVerdictKind = Literal["ACCEPTED", "REJECTED", "REFUSED"]

REASON_UNADJUSTED_FORBIDDEN_OVER_ONE = (
    "UNADJUSTED_ACCEPTANCE_IS_FORBIDDEN_FOR_FAMILIES_OVER_ONE"
)
REASON_UNADJUSTED_SINGLE_ATTEMPT = "UNADJUSTED_ACCEPTANCE_SINGLE_ATTEMPT"
REASON_ADJUSTED_AT_OR_BELOW_ALPHA = "ADJUSTED_PVALUE_AT_OR_BELOW_ALPHA"
REASON_ADJUSTED_ABOVE_ALPHA = "ADJUSTED_PVALUE_ABOVE_ALPHA"

REASON_PRECISION_UNDEFINED = "PRECISION_UNDEFINED_NO_SIGNAL_POSITIVES"
REASON_RECALL_UNDEFINED = "RECALL_UNDEFINED_NO_MATURED_POSITIVES"
REASON_FP_RATE_UNDEFINED = "FALSE_POSITIVE_RATE_UNDEFINED_NO_SIGNAL_NEGATIVES"


# ---------------------------------------------------------------------------
# Exact multiple-testing adjustments
# ---------------------------------------------------------------------------


def _validated_pvalue(value: object, index: int) -> float:
    """Validate one p-value; deterministic ValueError with reason code."""
    try:
        p = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"pvalue_not_numeric:index={index}") from None
    if not math.isfinite(p):
        raise ValueError(f"pvalue_not_finite:index={index}")
    if p < 0.0 or p > 1.0:
        raise ValueError(f"pvalue_out_of_range:index={index}")
    return p


def bonferroni_adjust(pvalues: Sequence[float]) -> tuple[float, ...]:
    """Bonferroni adjustment: ``adjusted_i = min(1.0, p_i * m)`` with
    ``m = len(pvalues)``.

    Exact arithmetic: one integer multiplication and one comparison per
    element; no rounding. Order of the input is preserved. An empty input
    yields an empty tuple (nothing was tested, nothing is adjusted).
    """
    pvs = [_validated_pvalue(p, i) for i, p in enumerate(pvalues)]
    m = len(pvs)
    return tuple(min(1.0, p * m) for p in pvs)


def benjamin_hochberg_adjust(pvalues: Sequence[float]) -> tuple[float, ...]:
    """Benjamini-Hochberg step-up FDR adjustment, in input order.

    Exact arithmetic (m = len(pvalues)); p-values sorted ascending with a
    DETERMINISTIC stable sort (ties keep input order):
      raw(rank j, 1-based over ascending order) = p_(j) * m / j
      adjusted_(j) = min over k >= j of raw_(k), clipped to 1.0.
    The min is accumulated from the largest rank downwards; clipping to
    1.0 is applied at the end. No rounding anywhere.

    The implementation starts the running minimum at 1.0, which is exactly
    equivalent to computing min over the raw statistics and then clipping,
    because min(1.0, x) clipped to 1.0 == x clipped to 1.0.
    """
    pvs = [_validated_pvalue(p, i) for i, p in enumerate(pvalues)]
    m = len(pvs)
    if m == 0:
        return ()
    order = sorted(range(m), key=lambda i: pvs[i])  # stable: ties keep input order
    adjusted_in_sorted_order = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        raw = pvs[idx] * m / rank
        if raw < running:
            running = raw
        adjusted_in_sorted_order[rank - 1] = running if running < 1.0 else 1.0
    out = [0.0] * m
    for position, idx in enumerate(order):
        out[idx] = adjusted_in_sorted_order[position]
    return tuple(out)


# ---------------------------------------------------------------------------
# Family-level acceptance with multiple-testing control
# ---------------------------------------------------------------------------


class EvaluationFamily(BaseModel):
    """One preregistered evaluation attempt inside a multiplicity family.

    A "family" is the set of attempts sharing ``family_id`` — multiplicity
    is a property of the GROUP, so acceptance decisions are taken per group
    (see `adjusted_acceptance`, which takes the full member sequence).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    family_id: str = Field(min_length=1, max_length=128)
    hypothesis_id: str = Field(min_length=1, max_length=128)
    attempt_index: int = Field(ge=1)
    metric_name: str = Field(min_length=1, max_length=128)
    pvalue: float = Field(ge=0.0, le=1.0)


class AdjustedAcceptanceVerdict(BaseModel):
    """Frozen verdict for one `EvaluationFamily` member.

    ``accepted is None`` exactly when ``verdict == "REFUSED"``. The
    honesty flag ``unadjusted`` is True only when method NONE was applied
    to a single-attempt family: the acceptance was NOT corrected for
    multiplicity, and the record says so.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    family_id: str
    hypothesis_id: str
    attempt_index: int
    metric_name: str
    method: MultipleTestingMethod
    alpha: float
    raw_pvalue: float
    adjusted_pvalue: float | None
    accepted: bool | None
    verdict: AcceptanceVerdictKind
    reason_codes: tuple[str, ...] = ()
    unadjusted: bool = False


def adjusted_acceptance(
    families: Sequence[EvaluationFamily],
    *,
    method: MultipleTestingMethod,
    alpha: float,
) -> tuple[AdjustedAcceptanceVerdict, ...]:
    """Multiplicity-controlled acceptance decisions for a family batch.

    Members are grouped by ``family_id`` (first-appearance order of groups;
    member order inside the output preserves input order). Within each
    group of size m:
      - BONFERRONI: adjusted = min(1.0, p * m) (see `bonferroni_adjust`);
      - BENJAMIN_HOCHBERG: step-up adjustment (see
        `benjamin_hochberg_adjust`);
      - NONE: REFUSED with reason
        `UNADJUSTED_ACCEPTANCE_IS_FORBIDDEN_FOR_FAMILIES_OVER_ONE` when
        m > 1 (fail-closed honesty: unadjusted comparisons across multiple
        attempts inflate false positives); permitted for m == 1 with the
        explicit `unadjusted=True` honesty flag on the verdict.

    Acceptance rule (never rounded): accepted iff adjusted_pvalue <= alpha.
    ``alpha`` must lie strictly inside (0, 1) — refused otherwise with
    ``alpha_out_of_range`` (a degenerate alpha would fabricate certainty).
    """
    try:
        a = float(alpha)
    except (TypeError, ValueError):
        raise ValueError(f"alpha_not_numeric:{alpha!r}") from None
    if not math.isfinite(a) or a <= 0.0 or a >= 1.0:
        raise ValueError(f"alpha_out_of_range:{alpha!r}")

    # Group members by family_id, preserving first-appearance group order.
    groups: dict[str, list[int]] = {}
    for idx, member in enumerate(families):
        groups.setdefault(member.family_id, []).append(idx)

    results: list[AdjustedAcceptanceVerdict | None] = [None] * len(families)
    for member_indices in groups.values():
        members = [(i, families[i]) for i in member_indices]
        m = len(members)
        if method == "NONE" and m > 1:
            for i, member in members:
                results[i] = AdjustedAcceptanceVerdict(
                    family_id=member.family_id,
                    hypothesis_id=member.hypothesis_id,
                    attempt_index=member.attempt_index,
                    metric_name=member.metric_name,
                    method=method,
                    alpha=a,
                    raw_pvalue=member.pvalue,
                    adjusted_pvalue=None,
                    accepted=None,
                    verdict="REFUSED",
                    reason_codes=(REASON_UNADJUSTED_FORBIDDEN_OVER_ONE,),
                    unadjusted=False,
                )
            continue
        if method == "BONFERRONI":
            adjusted = bonferroni_adjust([mem.pvalue for _, mem in members])
        elif method == "BENJAMIN_HOCHBERG":
            adjusted = benjamin_hochberg_adjust([mem.pvalue for _, mem in members])
        else:  # NONE with exactly one member: allowed, flagged honestly.
            adjusted = (members[0][1].pvalue,)
        for (i, member), adj in zip(members, adjusted):
            accepted = bool(adj <= a)
            if method == "NONE":
                codes: tuple[str, ...] = (REASON_UNADJUSTED_SINGLE_ATTEMPT,)
                unadjusted_flag = True
            else:
                codes = (
                    REASON_ADJUSTED_AT_OR_BELOW_ALPHA
                    if accepted
                    else REASON_ADJUSTED_ABOVE_ALPHA,
                )
                unadjusted_flag = False
            results[i] = AdjustedAcceptanceVerdict(
                family_id=member.family_id,
                hypothesis_id=member.hypothesis_id,
                attempt_index=member.attempt_index,
                metric_name=member.metric_name,
                method=method,
                alpha=a,
                raw_pvalue=member.pvalue,
                adjusted_pvalue=adj,
                accepted=accepted,
                verdict="ACCEPTED" if accepted else "REJECTED",
                reason_codes=codes,
                unadjusted=unadjusted_flag,
            )
    return tuple(results)


# ---------------------------------------------------------------------------
# FP / FN analysis of signalled outcomes vs matured labels
# ---------------------------------------------------------------------------


class OutcomePair(BaseModel):
    """One evaluated signal outcome: prediction vs matured label.

    ``signal_positive``: the deterministic evaluation signalled an entry
    (a trade was taken). ``matured_positive``: the MATURED outcome label
    (decided only after the outcome matured — no early peeking) marks the
    event as positive. Neither field is derived here; both are explicit
    inputs so this module stays clock-free and label-agnostic.
    """

    model_config = ConfigDict(frozen=True)

    signal_positive: bool
    matured_positive: bool


class ConfusionCounts(BaseModel):
    """Exact integer confusion counts. Integers only: no estimation."""

    model_config = ConfigDict(frozen=True)

    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    total: int


class ClassificationRates(BaseModel):
    """Precision / recall / false-positive-rate with honest None semantics.

    A rate with a zero denominator is ``None`` plus a reason code in
    ``undefined`` — it is NEVER reported as 0.0 (which would fabricate a
    measurement). Floats are exact single divisions; NO rounding (see
    `format_rate` for the only presentation-rounding entry point).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    precision: float | None
    recall: float | None
    false_positive_rate: float | None
    undefined: tuple[str, ...] = ()


def confusion_counts(outcomes: Sequence[OutcomePair]) -> ConfusionCounts:
    """Deterministic confusion counts over (signal, matured-label) pairs.

    true_positive  = signalled AND matured-positive
    false_positive = signalled AND NOT matured-positive  (bad trade / FP)
    false_negative = NOT signalled AND matured-positive  (missed move / FN)
    true_negative  = NOT signalled AND NOT matured-positive
    An empty outcome sequence yields all-zero counts (honest emptiness).
    """
    tp = fp = fn = tn = 0
    for o in outcomes:
        if o.signal_positive and o.matured_positive:
            tp += 1
        elif o.signal_positive and not o.matured_positive:
            fp += 1
        elif not o.signal_positive and o.matured_positive:
            fn += 1
        else:
            tn += 1
    return ConfusionCounts(
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        true_negative=tn,
        total=tp + fp + fn + tn,
    )


def precision_recall_fp_rate(counts: ConfusionCounts) -> ClassificationRates:
    """Compute rates from exact confusion counts.

    precision = TP / (TP + FP)          (None if no signal positives)
    recall    = TP / (TP + FN)          (None if no matured positives)
    fp_rate   = FP / (FP + TN)          (None if no signal negatives)
    Each is ONE exact IEEE-754 division of integers; undefined rates are
    None with a reason code (see `ClassificationRates`).
    """
    undefined: list[str] = []
    precision: float | None
    recall: float | None
    fp_rate: float | None
    if counts.true_positive + counts.false_positive > 0:
        precision = counts.true_positive / (counts.true_positive + counts.false_positive)
    else:
        precision = None
        undefined.append(REASON_PRECISION_UNDEFINED)
    if counts.true_positive + counts.false_negative > 0:
        recall = counts.true_positive / (counts.true_positive + counts.false_negative)
    else:
        recall = None
        undefined.append(REASON_RECALL_UNDEFINED)
    if counts.false_positive + counts.true_negative > 0:
        fp_rate = counts.false_positive / (counts.false_positive + counts.true_negative)
    else:
        fp_rate = None
        undefined.append(REASON_FP_RATE_UNDEFINED)
    return ClassificationRates(
        precision=precision,
        recall=recall,
        false_positive_rate=fp_rate,
        undefined=tuple(undefined),
    )


def format_rate(value: float | None, digits: int) -> float | None:
    """The ONLY rounding point in this module (presentation helper).

    Rounds an already-computed rate to ``digits`` fractional digits for
    display; ``None`` (an undefined rate) passes through as None so an
    undefined measurement can never be disguised as a number. ``digits``
    must be a non-negative integer. Rounding uses Python's ``round`` on
    the exact input double — deterministic for a fixed input and runtime.
    """
    if isinstance(digits, bool) or not isinstance(digits, int) or digits < 0:
        raise ValueError(f"digits_must_be_non_negative_int:{digits!r}")
    if value is None:
        return None
    v = float(value)
    if not math.isfinite(v):
        raise ValueError("format_rate_value_not_finite")
    return round(v, digits)
