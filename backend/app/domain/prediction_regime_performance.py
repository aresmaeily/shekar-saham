"""Regime-sliced prediction performance (WP-I, purely additive).

WAVE-AB5 scope: the P3 regime-sliced evaluation requirement (02:145) applied
to the L5 prediction-feedback loop. The durable prediction store records
matured+evaluated predictions; this module computes PER-REGIME Brier / ECE
over caller-declared regime bindings.

Module-placement choice (documented, per the work-item's explicit option):
this is a NEW module instead of an extension of
``app.domain.calibration_metrics`` because it needs the CLOSED regime-label
vocabulary from ``app.engines.regime_slices`` (single source of truth — the
labels are never re-declared here), while ``calibration_metrics`` stays the
pure numeric producer with no regime concept. The exact-arithmetic helpers
(:func:`brier_score`, :func:`expected_calibration_error`) are REUSED by
direct import — no numeric logic is duplicated or forked.

Honesty discipline (mirrors ``regime_slices.slice_by_regime``):
- regime labels are CALLER-DECLARED from the closed vocabulary — this module
  never infers a regime from data;
- a declared regime with no bound predictions is reported as an EMPTY SLICE
  with an explicit reason — never fabricated, never silently dropped;
- deterministic ordering: slices are emitted in the closed vocabulary's
  canonical order, restricted to the caller-declared labels;
- every float is computed with EXACT rational arithmetic
  (``fractions.Fraction`` over the stated decimal inputs) and converted to
  ``float`` exactly once inside the reused calibration producers;
- no clock reads (maturity/evaluation is the CALLER's enforcement duty at
  the store layer: the API surface refuses unevaluated and look-ahead
  bindings before calling this function), no I/O, no network, no LLM.

Nothing here mutates anything, registers anything, or grants authority.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.calibration_metrics import (
    brier_score,
    expected_calibration_error,
)
from app.engines.regime_slices import REGIME_LABELS, RegimeLabel

__all__ = [
    "RegimeBoundPrediction",
    "RegimePerformanceSlice",
    "slice_prediction_performance_by_regime",
]

EMPTY_SLICE_REASON = "no_matured_evaluated_predictions_bound_to_regime"


class RegimeBoundPrediction(BaseModel):
    """One matured+evaluated prediction bound to a caller-declared regime.

    ``regime_label`` must come from the closed ``RegimeLabel`` vocabulary;
    ``observed`` is the binary outcome (0/1; bools accepted as 0/1);
    ``predicted_probability`` is the probability that was registered with
    the calibration pair. The maturity+evaluation precondition is enforced
    by the CALLER (the API surface validates against the durable store
    before constructing these records); this record keeps the binding
    honest and deterministic.
    """

    model_config = ConfigDict(frozen=True)

    prediction_id: str = Field(min_length=1, max_length=128)
    regime_label: RegimeLabel
    predicted_probability: float = Field(ge=0.0, le=1.0)
    observed: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _binary_observed(self) -> "RegimeBoundPrediction":
        # Same binary discipline as calibration_metrics.parse_pairs: the
        # observed outcome must be exactly 0 or 1 (bools are 0/1 too).
        exact = Fraction(str(self.observed))
        if exact not in (Fraction(0), Fraction(1)):
            raise ValueError("outcome_must_be_binary")
        if not math.isfinite(self.predicted_probability):
            raise ValueError("predicted_probability_must_be_finite")
        return self


class RegimePerformanceSlice(BaseModel):
    """One regime's deterministic performance row (frozen).

    For a NON-empty slice, ``brier_score`` / ``expected_calibration_error``
    are the exact-arithmetic values from the reused calibration producers.
    For an EMPTY slice both are ``None`` and ``empty_reason`` states why —
    a gap is reported, never fabricated.
    """

    model_config = ConfigDict(frozen=True)

    regime_label: RegimeLabel
    prediction_count: int = Field(ge=0)
    brier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    expected_calibration_error: float | None = Field(default=None, ge=0.0, le=1.0)
    bucket_count: int = Field(ge=1)
    empty: bool
    empty_reason: str | None = None

    @model_validator(mode="after")
    def _slice_honesty(self) -> "RegimePerformanceSlice":
        if self.empty:
            if self.prediction_count != 0:
                raise ValueError("empty_slice_with_nonzero_count")
            if self.brier_score is not None or self.expected_calibration_error is not None:
                raise ValueError("empty_slice_with_scores")
            if not self.empty_reason:
                raise ValueError("empty_slice_requires_reason")
        else:
            if self.prediction_count <= 0:
                raise ValueError("nonempty_slice_requires_records")
            if self.brier_score is None or self.expected_calibration_error is None:
                raise ValueError("nonempty_slice_requires_scores")
        return self


def _validate_declared_labels(regime_labels: Sequence[str]) -> list[str]:
    if len(regime_labels) == 0:
        raise ValueError("no_regime_labels")
    seen: set[str] = set()
    for label in regime_labels:
        if not isinstance(label, str) or label not in REGIME_LABELS:
            raise ValueError(f"unknown_regime_label:{label!r}")
        if label in seen:
            raise ValueError(f"duplicate_regime_label:{label}")
        seen.add(label)
    # Deterministic order: the closed vocabulary's canonical order.
    return [label for label in REGIME_LABELS if label in seen]


def _validate_bucket_count(bucket_count: int) -> int:
    if not isinstance(bucket_count, int) or isinstance(bucket_count, bool):
        raise ValueError("bucket_count_out_of_bounds")
    if not 1 <= bucket_count <= 32:
        raise ValueError("bucket_count_out_of_bounds")
    return bucket_count


def slice_prediction_performance_by_regime(
    bound_records: Sequence[RegimeBoundPrediction],
    regime_labels: Sequence[str],
    *,
    bucket_count: int = 10,
) -> tuple[RegimePerformanceSlice, ...]:
    """Deterministic per-regime Brier/ECE over bound matured+evaluated pairs.

    Parameters
    ----------
    bound_records:
        One record per evaluated prediction, each bound to a regime label
        from the closed vocabulary. Duplicate ``prediction_id`` bindings are
        refused (``duplicate_prediction_binding``); a record bound to a label
        the caller did not declare is refused
        (``bound_label_not_declared``) — explicit-in, explicit-out.
    regime_labels:
        The caller-DECLARED reporting set (subset of the closed vocabulary;
        duplicates and unknown labels refused). Output slices follow the
        vocabulary's canonical order restricted to this set.
    bucket_count:
        Explicit ECE bucketing resolution (1..32); never a module constant.

    Returns
    -------
    tuple[RegimePerformanceSlice, ...]
        Per-regime rows: count + exact Brier + exact ECE for non-empty
        slices; count=0 with ``empty=True`` and an explicit reason for
        declared regimes with no bound predictions (gaps are explicit, never
        fabricated).

    Refusals (``ValueError`` reason codes): ``no_regime_labels``,
    ``unknown_regime_label:<label>``, ``duplicate_regime_label:<label>``,
    ``bucket_count_out_of_bounds``, ``duplicate_prediction_binding:<id>``,
    ``bound_label_not_declared:<label>``, plus the pair-shape refusals of
    the reused calibration producers.
    """
    bucket_count = _validate_bucket_count(bucket_count)
    declared = _validate_declared_labels(regime_labels)
    declared_set = set(declared)

    by_label: dict[str, list[tuple[float, float]]] = {label: [] for label in declared}
    seen_ids: set[str] = set()
    for record in bound_records:
        if record.prediction_id in seen_ids:
            raise ValueError(f"duplicate_prediction_binding:{record.prediction_id}")
        seen_ids.add(record.prediction_id)
        if record.regime_label not in declared_set:
            raise ValueError(f"bound_label_not_declared:{record.regime_label}")
        by_label[record.regime_label].append(
            (
                record.predicted_probability,
                # parse_pairs accepts int 0/1 (or bool) as the binary outcome;
                # a float 1.0 is refused by the engine, so the exact-binary
                # record value is passed as an int (the record validator has
                # already pinned it to exactly 0 or 1).
                int(Fraction(str(record.observed))),
            )
        )

    slices: list[RegimePerformanceSlice] = []
    for label in declared:
        pairs = by_label[label]
        if not pairs:
            slices.append(
                RegimePerformanceSlice(
                    regime_label=label,  # type: ignore[arg-type]
                    prediction_count=0,
                    brier_score=None,
                    expected_calibration_error=None,
                    bucket_count=bucket_count,
                    empty=True,
                    empty_reason=EMPTY_SLICE_REASON,
                )
            )
            continue
        # Exact rational arithmetic inside the reused producers; converted
        # to float exactly once there. Deterministic given the same records.
        slices.append(
            RegimePerformanceSlice(
                regime_label=label,  # type: ignore[arg-type]
                prediction_count=len(pairs),
                brier_score=brier_score(pairs),
                expected_calibration_error=expected_calibration_error(pairs, bucket_count),
                bucket_count=bucket_count,
                empty=False,
                empty_reason=None,
            )
        )
    return tuple(slices)
