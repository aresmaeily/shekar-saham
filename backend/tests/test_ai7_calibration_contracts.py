"""AI-7 Continuous Learning/Productization acceptance tests (corpus-derived).

Sources: 02:102-104 (calibration + evidence-based autonomy expansion),
02:172-179 (AI-7/P10 product loop; must not automatically change
production), 02:202 (pre-G2 synthetic class; data_class closed to
SYNTHETIC/PAPER), D-AI-31 (DEFERRED UNTIL EVIDENCE — autonomy expands only
from measured evidence; owner call), 04:72 (owner-Accountable acts; T6),
D-AI-38 lineage (coverage honesty), 05:200/202 (no runtime authorized by
D-AI-32..39; capability is not evidence). Contract-level synthetic tests
only — no computation run, no I/O, no network, no LLM, no real data
(02:202; G2 NOT_PASSED).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.calibration import (
    MAX_BUCKETS,
    MAX_SUPPORTING_CALIBRATIONS,
    AutonomyExpansionEvidence,
    CalibrationBucket,
    CalibrationRecord,
    autonomy_expansion_permission,
)

UTC = timezone.utc
T0 = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)


def _bucket(i: int, count: int = 10) -> CalibrationBucket:
    return CalibrationBucket(
        upper_bound=(i + 1) / 10,
        predicted_mean=(i + 0.5) / 10,
        observed_frequency=(i + 0.4) / 10,
        count=count,
    )


def _record(**kw) -> CalibrationRecord:
    base = dict(
        calibration_id="cal-1",
        subject_kind="PREDICTION",
        subject_ref="pred-2026-10-29-001",
        measured_at_utc=T0,
        data_class="SYNTHETIC",
        sample_size=10,
        brier_score=0.18,
        coverage_complete=True,
        evidence_ref="research_memory://episodic/cal-1",
    )
    base.update(kw)
    return CalibrationRecord(**base)


def _evidence(**kw) -> AutonomyExpansionEvidence:
    base = dict(
        expansion_evidence_id="aee-1",
        from_level="L1",
        to_level="L2",
        supporting_calibration_ids=("cal-1", "cal-2"),
        window_start_utc=T0,
        window_end_utc=datetime(2026, 10, 29, 18, 0, 0, tzinfo=UTC),
    )
    base.update(kw)
    return AutonomyExpansionEvidence(**base)


# ---------------------------------------------------------------------------
# CalibrationRecord — construction and structural invariants
# ---------------------------------------------------------------------------


def test_record_with_score_only_ok() -> None:
    r = _record()
    assert r.brier_score == 0.18 and r.buckets == ()
    assert r.schema_version


def test_empty_record_refused() -> None:
    with pytest.raises(ValidationError):
        _record(brier_score=None, expected_calibration_error=None, buckets=())


def test_ece_alone_satisfies_measurement_requirement() -> None:
    r = _record(brier_score=None, expected_calibration_error=0.07)
    assert r.expected_calibration_error == 0.07


def test_data_class_live_unrepresentable() -> None:
    with pytest.raises(ValidationError):
        _record(data_class="LIVE")  # type: ignore[arg-type]


def test_data_class_paper_ok() -> None:
    assert _record(data_class="PAPER").data_class == "PAPER"


def test_naive_timestamp_rejected_aware_round_trips() -> None:
    # Canonical rule (evidence.ensure_utc): naive timestamps are REJECTED,
    # not silently converted.
    with pytest.raises(ValidationError):
        _record(measured_at_utc=datetime(2026, 10, 29, 12, 0, 0))
    r = _record()
    assert r.measured_at_utc.tzinfo is not None


def test_universal_calibration_claim_unrepresentable() -> None:
    with pytest.raises(ValidationError):
        CalibrationRecord.model_validate(_record().model_dump() | {"universal_calibration_claimed": True})


def test_incomplete_coverage_requires_gaps() -> None:
    with pytest.raises(ValidationError):
        _record(coverage_complete=False)


def test_incomplete_coverage_with_gaps_ok() -> None:
    r = _record(coverage_complete=False, coverage_gaps=("regime-Z unlabeled",))
    assert r.coverage_gaps == ("regime-Z unlabeled",)


def test_blank_coverage_gap_refused() -> None:
    with pytest.raises(ValidationError):
        _record(coverage_complete=False, coverage_gaps=("  ",))


def test_brier_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        _record(brier_score=1.01)
    with pytest.raises(ValidationError):
        _record(brier_score=-0.01)


def test_ece_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        _record(expected_calibration_error=1.5)
    with pytest.raises(ValidationError):
        _record(expected_calibration_error=-0.1)


def test_subject_ref_bounded() -> None:
    with pytest.raises(ValidationError):
        _record(subject_ref="x" * 129)
    assert _record(subject_ref="x" * 128).subject_ref == "x" * 128


@pytest.mark.parametrize("kind", ["PREDICTION", "PRODUCT_AUDIT", "RESEARCH_OUTPUT"])
def test_subject_kinds_accepted(kind: str) -> None:
    assert _record(subject_kind=kind).subject_kind == kind


def test_invalid_subject_kind_refused() -> None:
    with pytest.raises(ValidationError):
        _record(subject_kind="ANYTHING")  # type: ignore[arg-type]


def test_frozen_record_rejects_mutation() -> None:
    with pytest.raises(ValidationError):
        _record().calibration_id = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CalibrationRecord — bucket arithmetic honesty
# ---------------------------------------------------------------------------


def test_bucket_counts_must_sum_to_sample_size() -> None:
    with pytest.raises(ValidationError):
        _record(
            sample_size=100,
            brier_score=None,
            buckets=(_bucket(0, count=10), _bucket(1, count=10)),
        )


def test_bucket_counts_summing_ok() -> None:
    r = _record(
        sample_size=20,
        brier_score=None,
        buckets=(_bucket(0, count=10), _bucket(1, count=10)),
    )
    assert len(r.buckets) == 2


def test_buckets_must_be_strictly_ascending() -> None:
    with pytest.raises(ValidationError):
        _record(
            sample_size=20,
            brier_score=None,
            buckets=(_bucket(1, count=10), _bucket(0, count=10)),
        )


def test_duplicate_bucket_bounds_refused() -> None:
    dup = CalibrationBucket(upper_bound=0.5, predicted_mean=0.4, observed_frequency=0.4, count=5)
    with pytest.raises(ValidationError):
        _record(sample_size=10, brier_score=None, buckets=(dup, dup.model_copy()))


def test_bucket_ceiling_enforced() -> None:
    with pytest.raises(ValidationError):
        _record(
            sample_size=MAX_BUCKETS + 1,
            brier_score=None,
            buckets=tuple(_bucket(i, count=1) for i in range(MAX_BUCKETS + 1)),
        )


def test_bucket_field_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        CalibrationBucket(upper_bound=1.01, predicted_mean=0.4, observed_frequency=0.4, count=1)
    with pytest.raises(ValidationError):
        CalibrationBucket(upper_bound=0.5, predicted_mean=1.4, observed_frequency=0.4, count=1)
    with pytest.raises(ValidationError):
        CalibrationBucket(upper_bound=0.5, predicted_mean=0.4, observed_frequency=-0.1, count=1)
    with pytest.raises(ValidationError):
        CalibrationBucket(upper_bound=0.5, predicted_mean=0.4, observed_frequency=0.4, count=0)


def test_bucket_ceiling_bound_is_one() -> None:
    b = CalibrationBucket(upper_bound=1.0, predicted_mean=1.0, observed_frequency=1.0, count=1)
    assert b.upper_bound == 1.0


# ---------------------------------------------------------------------------
# AutonomyExpansionEvidence — EVIDENCE_ONLY structural pins
# ---------------------------------------------------------------------------


def test_evidence_record_ok() -> None:
    e = _evidence()
    assert e.status == "EVIDENCE_ONLY" and e.approval_state == "NOT_GRANTED"


def test_approval_state_pinned_not_granted() -> None:
    with pytest.raises(ValidationError):
        AutonomyExpansionEvidence.model_validate(_evidence().model_dump() | {"approval_state": "APPROVED"})


def test_status_pinned_evidence_only() -> None:
    with pytest.raises(ValidationError):
        AutonomyExpansionEvidence.model_validate(_evidence().model_dump() | {"status": "EXECUTED"})


def test_downward_expansion_refused() -> None:
    with pytest.raises(ValidationError):
        _evidence(from_level="L2", to_level="L1")


def test_same_level_expansion_refused() -> None:
    with pytest.raises(ValidationError):
        _evidence(from_level="L2", to_level="L2")


def test_window_end_before_start_refused() -> None:
    with pytest.raises(ValidationError):
        _evidence(
            window_start_utc=datetime(2026, 10, 29, 18, 0, 0, tzinfo=UTC),
            window_end_utc=T0,
        )


def test_naive_window_timestamp_refused() -> None:
    with pytest.raises(ValidationError):
        _evidence(window_start_utc=datetime(2026, 10, 29, 12, 0, 0))


def test_supporting_ids_duplicates_refused() -> None:
    with pytest.raises(ValidationError):
        _evidence(supporting_calibration_ids=("cal-1", "cal-1"))


def test_supporting_ids_blank_refused() -> None:
    with pytest.raises(ValidationError):
        _evidence(supporting_calibration_ids=("cal-1", " "))


def test_supporting_ids_ceiling_enforced() -> None:
    with pytest.raises(ValidationError):
        _evidence(
            supporting_calibration_ids=tuple(f"c{i}" for i in range(MAX_SUPPORTING_CALIBRATIONS + 1))
        )


def test_supporting_ids_min_one_enforced() -> None:
    with pytest.raises(ValidationError):
        _evidence(supporting_calibration_ids=())


def test_frozen_evidence_rejects_mutation() -> None:
    with pytest.raises(ValidationError):
        _evidence().approval_state = "APPROVED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Deterministic permission gate (owner-gated; always refuses)
# ---------------------------------------------------------------------------


def test_expansion_permission_always_refuses() -> None:
    ok, refusals = autonomy_expansion_permission(_evidence())
    assert ok is False
    assert refusals == ("autonomy_expansion_owner_gated",)


def test_expansion_permission_tag_order_stable() -> None:
    # Defense-in-depth path: model_construct bypasses min_length validation.
    hollow = AutonomyExpansionEvidence.model_construct(
        expansion_evidence_id="aee-x",
        from_level="L1",
        to_level="L2",
        supporting_calibration_ids=(),
        window_start_utc=T0,
        window_end_utc=T0,
        status="EVIDENCE_ONLY",
        approval_state="NOT_GRANTED",
        notes="",
    )
    ok, refusals = autonomy_expansion_permission(hollow)
    assert ok is False
    assert refusals == ("no_supporting_evidence", "autonomy_expansion_owner_gated")


def test_expansion_permission_deterministic() -> None:
    e = _evidence()
    assert autonomy_expansion_permission(e) == autonomy_expansion_permission(e)


def test_no_io_clock_or_network_in_module() -> None:
    import inspect

    import app.domain.calibration as mod

    src = inspect.getsource(mod)
    assert "datetime.now" not in src
    assert "time.time" not in src
    assert "requests" not in src and "urlopen" not in src


def test_serialization_round_trip() -> None:
    r = _record(coverage_complete=False, coverage_gaps=("g",))
    assert CalibrationRecord.model_validate_json(r.model_dump_json()) == r
    e = _evidence()
    assert AutonomyExpansionEvidence.model_validate_json(e.model_dump_json()) == e
