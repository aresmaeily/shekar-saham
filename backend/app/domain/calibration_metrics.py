"""AI-7 pure calibration metric producers for RADAR BOURSE.

Corpus loci (2026-10-02 amendment corpus; see also
AI4_AI7_P343_DEPENDENCY_MATRIX.md §AI-7):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 102-104: "AI-7 —
  Continuous Learning/Productization: Calibration, model/prompt evaluation,
  recovery, rollback, observability and evidence-based autonomy expansion."
- 02 lines 172-179: AI-7/P10 loop — calibration, drift and invalidation
  quality; "must not automatically change production, promote filters,
  alter permissions/budgets, or deploy software."
- 02 line 202: pre-G2 authorized class — bounded design, schema work,
  synthetic/paper tests and safe dry-run work only.
- 06 charter §7: after maturity, predictions are compared to reality and
  error categories/calibration/drift produce research proposals —
  evaluation BEFORE maturity is label leakage and is refused here.
- Dependency matrix §AI-7 "Authorized NOW: contract extension only".

This module is the deterministic numeric producer the
``app.domain.calibration`` contracts anticipated ("no calibration
computation" there — here, and only here, the arithmetic lives). It
composes canonical schemas by direct import:

- ``CalibrationRecord`` / ``CalibrationBucket`` from
  ``app.domain.calibration`` (its schema is consumed verbatim);
- ``maturity_state`` from ``app.domain.prediction`` (pre-maturity
  predictions are refused, never silently scored);
- ``DATA_CLASS`` stays locked to the calibration contract's closed
  SYNTHETIC/PAPER set.

Determinism discipline:
- every float result is computed with EXACT rational arithmetic
  (``fractions.Fraction``) over the supplied inputs and converted to
  ``float`` exactly once at the end — no rounding inside any producer;
- ``round_for_presentation`` exists ONLY as a documented presentation
  helper for audit display; no module code path calls it;
- bucket edges follow what ``CalibrationBucket`` implies: ``bucket_count``
  buckets over (0, 1] with upper bounds ``i/bucket_count`` for
  ``i = 1..bucket_count`` (each bucket carries only its ``upper_bound``,
  so a bucket's membership is ``(previous_upper, upper_bound]`` with 0
  included in the first bucket).

No network, no I/O, no clock reads, no LLM, no wall time. Empty pairs are
refused everywhere (an "empty" calibration is not a measurement).
"""

from __future__ import annotations

import math
from datetime import datetime
from fractions import Fraction
from typing import Sequence

from app.domain.calibration import DATA_CLASS, MAX_BUCKETS, CalibrationBucket, CalibrationRecord
from app.domain.prediction import PredictionRecord, maturity_state

__all__ = [
    "CalibrationPair",
    "parse_pairs",
    "brier_score",
    "expected_calibration_error",
    "reliability_buckets",
    "bucket_upper_bounds",
    "build_calibration_record",
    "round_for_presentation",
]

#: A calibration pair: (predicted_probability, observed_binary_outcome).
CalibrationPair = tuple[float, float]


def _fraction(value: object, code_finite: str) -> Fraction:
    """Exact conversion of a supplied input to a rational.

    ``str``-based so the DECIMAL the caller stated (0.9 → 9/10) is what the
    arithmetic sees — exact arithmetic on inputs, not on binary-float
    artifacts. Non-finite inputs are refused.
    """
    try:
        fraction = Fraction(str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError(code_finite) from exc
    if not math.isfinite(float(fraction)):
        raise ValueError(code_finite)
    return fraction


def parse_pairs(pairs: Sequence[CalibrationPair]) -> tuple[tuple[Fraction, Fraction], ...]:
    """Validate and exactly convert calibration pairs.

    Refusals (deterministic reason codes):
    - ``empty_pairs`` — no pairs at all (never a measurement);
    - ``predicted_probability_must_be_finite`` — NaN/inf/non-numeric;
    - ``predicted_probability_out_of_range`` — outside [0, 1];
    - ``outcome_must_be_binary`` — observed outcome not in {0, 1}
      (bools are accepted as 0/1; any other value, including 0.5 or 2, is
      refused).
    """
    if pairs is None or len(pairs) == 0:
        raise ValueError("empty_pairs")
    parsed: list[tuple[Fraction, Fraction]] = []
    for predicted, observed in pairs:
        if isinstance(predicted, bool):
            raise ValueError("predicted_probability_must_be_finite")
        p = _fraction(predicted, "predicted_probability_must_be_finite")
        if p < 0 or p > 1:
            raise ValueError("predicted_probability_out_of_range")
        if isinstance(observed, bool):
            y = Fraction(1) if observed else Fraction(0)
        elif isinstance(observed, int) and observed in (0, 1):
            y = Fraction(observed)
        else:
            raise ValueError("outcome_must_be_binary")
        parsed.append((p, y))
    return tuple(parsed)


def brier_score(pairs: Sequence[CalibrationPair]) -> float:
    """Mean squared error of predicted probabilities vs binary outcomes.

    Exact arithmetic: ``Brier = (1/n) * Σ (p_i − y_i)²`` over
    ``fractions.Fraction``; converted to float once. Hand check:
    ``[(0.9, 1), (0.2, 0)]`` → ((1−0.9)² + 0.2²)/2 = (0.01 + 0.04)/2 =
    1/40 = 0.025 exactly.
    """
    parsed = parse_pairs(pairs)
    total = sum((p - y) ** 2 for p, y in parsed)
    return float(total / Fraction(len(parsed)))


def bucket_upper_bounds(bucket_count: int) -> tuple[float, ...]:
    """Bucket edges implied by ``CalibrationBucket`` (its upper bounds).

    ``bucket_count`` buckets tile (0, 1] with upper bounds
    ``i/bucket_count``. ``bucket_count`` outside 1..``MAX_BUCKETS`` is
    refused (``bucket_count_out_of_bounds``).
    """
    if not isinstance(bucket_count, int) or isinstance(bucket_count, bool):
        raise ValueError("bucket_count_out_of_bounds")
    if not 1 <= bucket_count <= MAX_BUCKETS:
        raise ValueError("bucket_count_out_of_bounds")
    return tuple(float(Fraction(i, bucket_count)) for i in range(1, bucket_count + 1))


def _bucket_index(p: Fraction, bucket_count: int) -> int:
    # Bucket b (0-based) covers (b/N, (b+1)/N] with 0 included in bucket 0;
    # a probability exactly ON an edge belongs to the higher bucket.
    index = math.floor(p * bucket_count)
    if p > 0 and p * bucket_count == index:
        index -= 1
    return min(max(index, 0), bucket_count - 1)


def expected_calibration_error(
    pairs: Sequence[CalibrationPair], bucket_count: int
) -> float:
    """ECE over the CalibrationBucket-implied edges.

    ``ECE = Σ_b (n_b / n) * |mean_p_b − mean_y_b|`` with exact rational
    arithmetic; empty buckets contribute nothing. Refusals as for
    :func:`parse_pairs` plus ``bucket_count_out_of_bounds``.
    """
    parsed = parse_pairs(pairs)
    if not isinstance(bucket_count, int) or isinstance(bucket_count, bool):
        raise ValueError("bucket_count_out_of_bounds")
    if not 1 <= bucket_count <= MAX_BUCKETS:
        raise ValueError("bucket_count_out_of_bounds")
    n = Fraction(len(parsed))
    sums: dict[int, tuple[Fraction, Fraction]] = {}
    counts: dict[int, int] = {}
    for p, y in parsed:
        idx = _bucket_index(p, bucket_count)
        s_p, s_y = sums.get(idx, (Fraction(0), Fraction(0)))
        sums[idx] = (s_p + p, s_y + y)
        counts[idx] = counts.get(idx, 0) + 1
    total = Fraction(0)
    for idx, count in counts.items():
        s_p, s_y = sums[idx]
        mean_p = s_p / count
        mean_y = s_y / count
        total += (Fraction(count) / n) * abs(mean_p - mean_y)
    return float(total)


def reliability_buckets(
    pairs: Sequence[CalibrationPair], bucket_count: int
) -> tuple[CalibrationBucket, ...]:
    """Non-empty reliability buckets as canonical ``CalibrationBucket`` rows.

    Only NON-EMPTY buckets are emitted (``CalibrationBucket`` requires
    ``count >= 1``); the emitted rows keep strictly ascending upper bounds
    and their counts sum to the sample size (the ``CalibrationRecord``
    invariant). Exact means converted to float once.
    """
    parsed = parse_pairs(pairs)
    if not isinstance(bucket_count, int) or isinstance(bucket_count, bool):
        raise ValueError("bucket_count_out_of_bounds")
    if not 1 <= bucket_count <= MAX_BUCKETS:
        raise ValueError("bucket_count_out_of_bounds")
    sums: dict[int, tuple[Fraction, Fraction]] = {}
    counts: dict[int, int] = {}
    for p, y in parsed:
        idx = _bucket_index(p, bucket_count)
        s_p, s_y = sums.get(idx, (Fraction(0), Fraction(0)))
        sums[idx] = (s_p + p, s_y + y)
        counts[idx] = counts.get(idx, 0) + 1
    buckets: list[CalibrationBucket] = []
    for idx in sorted(counts):
        s_p, s_y = sums[idx]
        count = counts[idx]
        buckets.append(
            CalibrationBucket(
                upper_bound=float(Fraction(idx + 1, bucket_count)),
                predicted_mean=float(s_p / count),
                observed_frequency=float(s_y / count),
                count=count,
            )
        )
    return tuple(buckets)


def build_calibration_record(
    *,
    calibration_id: str,
    subject_kind: str,
    subject_ref: str,
    pairs: Sequence[CalibrationPair],
    measured_at_utc: datetime,
    data_class: DATA_CLASS,
    evidence_ref: str,
    bucket_count: int = 10,
    coverage_complete: bool = True,
    coverage_gaps: tuple[str, ...] = (),
    prediction_records: tuple[PredictionRecord, ...] = (),
    calibration_note: str = "",
) -> CalibrationRecord:
    """Build a canonical ``CalibrationRecord`` from raw pairs.

    Deterministic refusals (in addition to the schema's own):
    - ``empty_pairs`` / pair-shape refusals from :func:`parse_pairs`;
    - ``bucket_count_out_of_bounds``;
    - ``data_class_not_in_closed_set`` — only SYNTHETIC/PAPER (02:202) are
      representable at this layer;
    - ``prediction_records_pairs_mismatch`` — when prediction records are
      supplied, exactly one record per pair is required;
    - ``prediction_not_matured:<prediction_id>`` — any supplied prediction
      whose horizon has not ended by ``measured_at_utc`` (label-leakage
      guard via ``prediction.maturity_state``, 06 §7).

    ``bucket_count`` is an explicit parameter (the reliability-bucket
    resolution used for the emitted ECE and buckets); no threshold or
    bucketing value is invented inside.
    """
    parsed = parse_pairs(pairs)
    if data_class not in ("SYNTHETIC", "PAPER"):
        raise ValueError("data_class_not_in_closed_set")
    if prediction_records:
        if len(prediction_records) != len(parsed):
            raise ValueError("prediction_records_pairs_mismatch")
        for record in prediction_records:
            if maturity_state(record, measured_at_utc) != "MATURED":
                raise ValueError(f"prediction_not_matured:{record.prediction_id}")
    brier = brier_score(pairs)
    ece = expected_calibration_error(pairs, bucket_count)
    buckets = reliability_buckets(pairs, bucket_count)
    return CalibrationRecord(
        calibration_id=calibration_id,
        subject_kind=subject_kind,  # type: ignore[arg-type]
        subject_ref=subject_ref,
        measured_at_utc=measured_at_utc,
        data_class=data_class,
        sample_size=len(parsed),
        brier_score=brier,
        expected_calibration_error=ece,
        buckets=buckets,
        coverage_complete=coverage_complete,
        coverage_gaps=coverage_gaps,
        evidence_ref=evidence_ref,
        calibration_note=calibration_note,
    )


def round_for_presentation(value: float, digits: int = 4) -> float:
    """Presentation helper for audit display — NEVER used by producers.

    The module's contract is "no rounding inside": every producer returns
    the exact-arithmetic float. This helper exists so a UI/audit layer can
    round for HUMANS without any producer silently trimming precision.
    """
    if not math.isfinite(value):
        raise ValueError("value_must_be_finite")
    if not 0 <= digits <= 10:
        raise ValueError("digits_out_of_bounds")
    return round(value, digits)
