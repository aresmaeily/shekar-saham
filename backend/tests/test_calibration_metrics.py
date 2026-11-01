"""AI-7 pure calibration metric producers — acceptance tests.

Sources: 02:102-104 (calibration), 02:172-179 (calibration/drift in the
product loop; no production mutation), 06 charter §7 (maturity before
evaluation — label-leakage guard), 02:202 (pre-G2 synthetic class;
data_class closed to SYNTHETIC/PAPER), dependency matrix §AI-7. All
expected values are HAND-COMPUTED; producers run exact rational
arithmetic and never round inside.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest

from app.domain.calibration import MAX_BUCKETS, CalibrationRecord
from app.domain.calibration_metrics import (
    brier_score,
    build_calibration_record,
    bucket_upper_bounds,
    expected_calibration_error,
    parse_pairs,
    reliability_buckets,
    round_for_presentation,
)
from app.domain.prediction import PredictionRecord

UTC = timezone.utc
T0 = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)


def _prediction(horizon_end: datetime, prediction_id: str = "pred-1") -> PredictionRecord:
    return PredictionRecord(
        prediction_id=prediction_id,
        subject="synthetic:regime-X-persist",
        registered_at_utc=T0,
        outcome_horizon_end_utc=horizon_end,
        evaluation_metric="directional_hit",
        event_maturity_rule="horizon-end",
        invalidation_rule="stop-hit",
        evidence_ids=("ev-1",),
        creator="synthetic-test",
    )


#: Measurement instant AFTER the predictions' horizons (registered at T0,
#: horizons end 1h/12h later; a prediction registered at T0 cannot be
#: matured AT T0 — the horizon must end after registration).
T_MEASURE = T0 + timedelta(hours=6)


# ---------------------------------------------------------------------------
# parse_pairs refusals (exact reason codes)
# ---------------------------------------------------------------------------


def test_empty_pairs_refused_everywhere() -> None:
    with pytest.raises(ValueError, match="empty_pairs"):
        parse_pairs([])
    with pytest.raises(ValueError, match="empty_pairs"):
        brier_score([])
    with pytest.raises(ValueError, match="empty_pairs"):
        expected_calibration_error([], 4)
    with pytest.raises(ValueError, match="empty_pairs"):
        reliability_buckets([], 4)


def test_non_finite_probability_refused() -> None:
    with pytest.raises(ValueError, match="predicted_probability_must_be_finite"):
        parse_pairs([(float("nan"), 0)])
    with pytest.raises(ValueError, match="predicted_probability_must_be_finite"):
        parse_pairs([(float("inf"), 1)])


def test_out_of_range_probability_refused() -> None:
    with pytest.raises(ValueError, match="predicted_probability_out_of_range"):
        parse_pairs([(1.5, 1)])
    with pytest.raises(ValueError, match="predicted_probability_out_of_range"):
        parse_pairs([(-0.1, 0)])


def test_non_binary_outcome_refused_bool_accepted() -> None:
    with pytest.raises(ValueError, match="outcome_must_be_binary"):
        parse_pairs([(0.5, 2)])
    with pytest.raises(ValueError, match="outcome_must_be_binary"):
        parse_pairs([(0.5, 0.5)])
    assert parse_pairs([(0.5, True)]) == ((1 / 2, 1),)


# ---------------------------------------------------------------------------
# Brier score — hand-computed expectations
# ---------------------------------------------------------------------------


def test_brier_hand_computed_example() -> None:
    # Hand check: [(0.9, 1), (0.2, 0)] -> ((1-0.9)^2 + (0.2-0)^2)/2
    #   = (0.1^2 + 0.2^2)/2 = (0.01 + 0.04)/2 = 0.05/2 = 0.025 EXACTLY
    # (exact rational arithmetic; the float result equals the literal 0.025).
    assert brier_score([(0.9, 1), (0.2, 0)]) == 0.025


def test_brier_perfect_and_worst() -> None:
    assert brier_score([(0.0, 0), (1.0, 1)]) == 0.0
    assert brier_score([(1.0, 0), (0.0, 1)]) == 1.0


def test_brier_deterministic() -> None:
    pairs = [(0.9, 1), (0.2, 0), (0.7, 1)]
    assert brier_score(pairs) == brier_score(pairs)
    # Hand check: (0.01 + 0.04 + 0.09)/3 = 0.14/3 = 7/150 exactly.
    assert brier_score(pairs) == float(Fraction(7, 150))


# ---------------------------------------------------------------------------
# Bucket edges implied by CalibrationBucket
# ---------------------------------------------------------------------------


def test_bucket_upper_bounds_implied_edges() -> None:
    assert bucket_upper_bounds(2) == (0.5, 1.0)
    assert bucket_upper_bounds(4) == (0.25, 0.5, 0.75, 1.0)


def test_bucket_count_bounds_refused() -> None:
    with pytest.raises(ValueError, match="bucket_count_out_of_bounds"):
        bucket_upper_bounds(0)
    with pytest.raises(ValueError, match="bucket_count_out_of_bounds"):
        bucket_upper_bounds(MAX_BUCKETS + 1)
    with pytest.raises(ValueError, match="bucket_count_out_of_bounds"):
        expected_calibration_error([(0.5, 1)], 0)
    with pytest.raises(ValueError, match="bucket_count_out_of_bounds"):
        reliability_buckets([(0.5, 1)], MAX_BUCKETS + 1)


# ---------------------------------------------------------------------------
# ECE / reliability buckets — hand-computed expectations
# ---------------------------------------------------------------------------


def test_ece_perfect_calibration_zero() -> None:
    # bucket (0,0.5]: p̄=0, ȳ=0; bucket (0.5,1]: p̄=1, ȳ=1 -> ECE=0
    assert expected_calibration_error([(0.0, 0), (1.0, 1)], 2) == 0.0


def test_ece_hand_computed() -> None:
    # bucket (0,0.5]: p̄=0.05, ȳ=0 -> |Δ|=0.05, weight 1/2
    # bucket (0.5,1]: p̄=0.95, ȳ=1 -> |Δ|=0.05, weight 1/2  => ECE = 0.05
    assert expected_calibration_error([(0.05, 0), (0.95, 1)], 2) == 0.05
    # inverted outcomes: |0.05-1|*1/2 + |0.95-0|*1/2 = 0.95
    assert expected_calibration_error([(0.05, 1), (0.95, 0)], 2) == 0.95


def test_reliability_buckets_shape_and_means() -> None:
    buckets = reliability_buckets([(0.2, 0), (0.8, 1)], 2)
    assert [b.upper_bound for b in buckets] == [0.5, 1.0]
    assert [(b.predicted_mean, b.observed_frequency, b.count) for b in buckets] == [
        (0.2, 0.0, 1),
        (0.8, 1.0, 1),
    ]


def test_empty_buckets_dropped_counts_still_sum() -> None:
    buckets = reliability_buckets([(0.1, 0), (0.2, 1)], 4)
    assert len(buckets) == 1
    assert buckets[0].upper_bound == 0.25
    assert buckets[0].count == 2


def test_edge_probability_belongs_to_lower_bucket() -> None:
    # Documented convention: a bucket's membership is (previous, upper], so
    # p=0.5 with 2 buckets lands in the bucket whose upper bound is 0.5.
    buckets = reliability_buckets([(0.5, 1), (0.6, 0)], 2)
    assert buckets[0].upper_bound == 0.5
    assert buckets[0].predicted_mean == 0.5


# ---------------------------------------------------------------------------
# build_calibration_record (canonical schema consumed verbatim)
# ---------------------------------------------------------------------------


def _record(**kw) -> CalibrationRecord:
    base = dict(
        calibration_id="cal-1",
        subject_kind="PREDICTION",
        subject_ref="pred-2026-10-29-001",
        pairs=[(0.9, 1), (0.2, 0)],
        measured_at_utc=T0,
        data_class="SYNTHETIC",
        evidence_ref="research_memory://episodic/cal-1",
    )
    base.update(kw)
    return build_calibration_record(**base)


def test_record_happy_path() -> None:
    record = _record(bucket_count=2)
    assert record.sample_size == 2
    assert record.brier_score == 0.025
    # Hand check (bucket_count=2): bucket (0,0.5]: p=0.2, y=0 -> |0.2|*1/2;
    # bucket (0.5,1]: p=0.9, y=1 -> |0.1|*1/2  =>  ECE = 0.15
    assert record.expected_calibration_error == 0.15
    assert sum(b.count for b in record.buckets) == record.sample_size
    assert record.universal_calibration_claimed is False


def test_record_refuses_empty_pairs() -> None:
    with pytest.raises(ValueError, match="empty_pairs"):
        _record(pairs=[])


def test_record_data_class_closed_set() -> None:
    with pytest.raises(ValueError, match="data_class_not_in_closed_set"):
        _record(data_class="LIVE")  # type: ignore[arg-type]
    assert _record(data_class="PAPER").data_class == "PAPER"


def test_record_refuses_pre_maturity_prediction() -> None:
    # Horizon ends 12h after registration; measured 6h after -> PENDING.
    immature = _prediction(T0 + timedelta(hours=12))
    with pytest.raises(ValueError, match=r"prediction_not_matured:pred-1"):
        _record(pairs=[(0.9, 1)], measured_at_utc=T_MEASURE, prediction_records=(immature,))


def test_record_accepts_matured_prediction() -> None:
    # Horizon ends 1h after registration; measured 6h after -> MATURED.
    matured = _prediction(T0 + timedelta(hours=1))
    record = _record(pairs=[(0.9, 1)], measured_at_utc=T_MEASURE, prediction_records=(matured,))
    assert record.sample_size == 1


def test_record_prediction_pairs_count_mismatch_refused() -> None:
    matured = _prediction(T0 + timedelta(hours=1))
    with pytest.raises(ValueError, match="prediction_records_pairs_mismatch"):
        _record(prediction_records=(matured,))


# ---------------------------------------------------------------------------
# Presentation helper is presentation-only
# ---------------------------------------------------------------------------


def test_round_for_presentation_is_not_used_by_producers() -> None:
    # The producer result stays the exact-arithmetic float; the helper is
    # for display only and is never applied inside any producer.
    assert brier_score([(0.9, 1), (0.2, 0)]) == 0.025
    assert round_for_presentation(0.01234, 3) == 0.012
    with pytest.raises(ValueError, match="value_must_be_finite"):
        round_for_presentation(float("nan"))
    with pytest.raises(ValueError, match="digits_out_of_bounds"):
        round_for_presentation(0.5, 11)


def test_no_clock_or_io_in_module() -> None:
    import inspect

    import app.domain.calibration_metrics as mod

    src = inspect.getsource(mod)
    assert "datetime.now" not in src
    assert "time.time" not in src
    assert "requests" not in src and "urlopen" not in src
