"""AI-7 product-audit run / drift / prompt-evaluation records — tests.

Sources: 02:102-105 (model/prompt evaluation), 02:172-179 (product loop;
must not automatically change production), 06 §7 (PIT calibration/drift
windows), 06 §8 (domain-matched evaluators), dependency matrix §AI-7.
Synthetic tests only — no execution, no I/O, no clock reads.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Mapping

import pytest
from pydantic import ValidationError

from app.domain.product_audit_records import (
    CalibrationWindowDigest,
    DomainEvaluatorResult,
    DriftAssessment,
    DriftRecord,
    DriftVerdict,
    ProductAuditRunRecord,
    PromptModelEvaluationRecord,
    WindowMetric,
    compare_windows,
)

UTC = timezone.utc
T0 = datetime(2026, 10, 20, 0, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 27, 0, 0, 0, tzinfo=UTC)
T2 = datetime(2026, 11, 3, 0, 0, 0, tzinfo=UTC)
T3 = datetime(2026, 11, 10, 0, 0, 0, tzinfo=UTC)


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _result(**kw) -> DomainEvaluatorResult:
    base = dict(
        domain="FILTERS_STRATEGIES",
        evaluator_kind="BACKTEST",
        evaluator_ref="app.engines.backtest",
        metrics_digest=_digest("filter-backtest-metrics"),
        evidence_ids=("ev-1",),
    )
    base.update(kw)
    return DomainEvaluatorResult(**base)


def _run_record(**kw) -> ProductAuditRunRecord:
    base = dict(
        run_record_id="par-1",
        run_id="run-1",
        charter_version="charter-2026-10-02",
        executed_at_utc=T2,
        domain_results=(_result(),),
        proposal_ids=("prop-1",),
        data_class="SYNTHETIC",
    )
    base.update(kw)
    return ProductAuditRunRecord(**base)


def _window(
    seed: str,
    start: datetime,
    end: datetime,
    metric_values: Mapping[str, float] | None = None,
) -> CalibrationWindowDigest:
    return CalibrationWindowDigest(
        window_start_utc=start,
        window_end_utc=end,
        digest=_digest(seed),
        metric_values=tuple(
            WindowMetric(name=name, value=value)
            for name, value in (metric_values or {}).items()
        ),
    )


def _drift_record(
    earlier: CalibrationWindowDigest | None = None,
    later: CalibrationWindowDigest | None = None,
    **kw,
) -> DriftRecord:
    base = dict(
        drift_record_id="drift-1",
        subject_ref="pred-2026-10-29-001",
        earlier_window=earlier or _window("w1", T0, T1, {"brier": 0.20, "ece": 0.05}),
        later_window=later or _window("w2", T1, T2, {"brier": 0.30, "ece": 0.04}),
        data_class="SYNTHETIC",
    )
    base.update(kw)
    return DriftRecord(**base)


# ---------------------------------------------------------------------------
# ProductAuditRunRecord
# ---------------------------------------------------------------------------


def test_run_record_advisory_and_data_class_pinned() -> None:
    record = _run_record()
    assert record.advisory_only is True
    assert record.data_class == "SYNTHETIC"


def test_run_record_data_class_live_refused() -> None:
    # The canonical closed set (calibration.DATA_CLASS) refuses LIVE at the
    # schema level; the explicit closed-set check remains as
    # defense-in-depth for constructor bypasses.
    with pytest.raises(ValidationError, match="Input should be 'SYNTHETIC' or 'PAPER'"):
        _run_record(data_class="LIVE")  # type: ignore[arg-type]


def test_domain_evaluator_vocabulary_and_domain_match() -> None:
    # canonical product_audit vocabularies; backtest-family only for
    # FILTERS_STRATEGIES (06 §8) — the canonical rule is re-enforced here.
    with pytest.raises(ValidationError, match="evaluator_not_allowed_for_domain"):
        _result(domain="PRODUCT_UX", evaluator_kind="BACKTEST")
    assert _result(domain="PRODUCT_UX", evaluator_kind="REGRESSION").domain == "PRODUCT_UX"


def test_run_record_duplicate_domains_refused() -> None:
    with pytest.raises(ValidationError, match="duplicate_domain_results"):
        _run_record(domain_results=(_result(), _result()))


def test_run_record_duplicate_proposal_ids_refused() -> None:
    with pytest.raises(ValidationError, match="proposal_ids_duplicates"):
        _run_record(proposal_ids=("p-1", "p-1"))


def test_run_record_metrics_digest_shape() -> None:
    with pytest.raises(ValidationError, match="metrics_digest_must_be_64_hex"):
        _result(metrics_digest="deadbeef")


def test_run_record_advisory_only_unrepresentable_as_false() -> None:
    payload = _run_record().model_dump() | {"advisory_only": False}
    with pytest.raises(ValidationError):
        ProductAuditRunRecord.model_validate(payload)


# ---------------------------------------------------------------------------
# DriftRecord (two digested windows, PIT-ordered, verdict deferred)
# ---------------------------------------------------------------------------


def test_drift_record_pit_boundary_inclusive_ok() -> None:
    # Later window starting EXACTLY when the earlier ends is PIT-ordered.
    record = _drift_record()
    assert record.later_window.window_start_utc == T1
    assert record.earlier_window.window_end_utc == T1


def test_drift_record_pit_violation_refused() -> None:
    overlapping = _window("w2", T0, T3, {"brier": 0.3})
    with pytest.raises(ValidationError, match="windows_not_pit_ordered"):
        _drift_record(later=overlapping)


def test_drift_record_carries_no_verdict_field() -> None:
    # The drift verdict is deferred to compare_windows — the record schema
    # has no verdict field at all (structural absence).
    assert "verdict" not in DriftRecord.model_fields
    assert "drift_verdict" not in DriftRecord.model_fields


def test_window_end_before_start_refused() -> None:
    with pytest.raises(ValidationError, match="window_end_before_start"):
        _window("w", T1, T0)


def test_window_metric_digest_and_names_discipline() -> None:
    with pytest.raises(ValidationError, match="digest_must_be_64_hex"):
        CalibrationWindowDigest(window_start_utc=T0, window_end_utc=T1, digest="zz")
    with pytest.raises(ValidationError, match="window_metric_names_duplicates"):
        CalibrationWindowDigest(
            window_start_utc=T0,
            window_end_utc=T1,
            digest=_digest("w"),
            metric_values=(
                WindowMetric(name="brier", value=0.1),
                WindowMetric(name="brier", value=0.2),
            ),
        )
    with pytest.raises(ValidationError, match="metric_value_must_be_finite"):
        WindowMetric(name="brier", value=float("nan"))


# ---------------------------------------------------------------------------
# compare_windows (pure; explicit thresholds; deterministic)
# ---------------------------------------------------------------------------

THRESHOLDS: Mapping[str, float] = {"brier": 0.05, "ece": 0.05}


def test_compare_windows_drift_detected() -> None:
    earlier = _window("w1", T0, T1, {"brier": 0.20, "ece": 0.05})
    later = _window("w2", T1, T2, {"brier": 0.30, "ece": 0.04})
    assessment = compare_windows(earlier, later, thresholds=THRESHOLDS)
    assert isinstance(assessment, DriftAssessment)
    assert assessment.drift_verdict == "DRIFT_DETECTED"
    assert assessment.reason_codes == ("drift_detected:brier",)
    by_name = {a.name: a for a in assessment.metric_assessments}
    assert by_name["brier"].verdict == "DRIFTED"
    assert by_name["brier"].delta == 0.10
    assert by_name["brier"].threshold == 0.05
    assert by_name["ece"].verdict == "STABLE"  # |0.04-0.05| = 0.01 <= 0.05


def test_compare_windows_boundary_is_strict() -> None:
    # |delta| == threshold exactly -> STABLE (drift requires strictly more).
    earlier = _window("w1", T0, T1, {"brier": 0.20})
    later = _window("w2", T1, T2, {"brier": 0.25})
    assessment = compare_windows(earlier, later, thresholds={"brier": 0.05})
    assert assessment.drift_verdict == "NO_DRIFT_DETECTED"
    assert assessment.reason_codes == ("no_drift_detected",)


def test_compare_windows_unevaluated_metrics_honest() -> None:
    # No threshold for "ece" -> NOT_EVALUATED; metric present in only one
    # window -> NOT_EVALUATED (never guessed).
    earlier = _window("w1", T0, T1, {"brier": 0.20, "ece": 0.05, "only_earlier": 1.0})
    later = _window("w2", T1, T2, {"brier": 0.20, "ece": 0.04, "only_later": 2.0})
    assessment = compare_windows(earlier, later, thresholds={"brier": 0.05})
    verdicts = {a.name: a.verdict for a in assessment.metric_assessments}
    assert verdicts == {
        "brier": "STABLE",
        "ece": "NOT_EVALUATED",
        "only_earlier": "NOT_EVALUATED",
        "only_later": "NOT_EVALUATED",
    }


def test_compare_windows_deterministic() -> None:
    earlier = _window("w1", T0, T1, {"brier": 0.20})
    later = _window("w2", T1, T2, {"brier": 0.40})
    assert compare_windows(earlier, later, thresholds=THRESHOLDS) == compare_windows(
        earlier, later, thresholds=THRESHOLDS
    )


def test_compare_windows_pit_violation_refused() -> None:
    earlier = _window("w1", T0, T3, {"brier": 0.20})
    later = _window("w2", T1, T2, {"brier": 0.40})
    with pytest.raises(ValueError, match="windows_not_pit_ordered"):
        compare_windows(earlier, later, thresholds=THRESHOLDS)


def test_compare_windows_thresholds_validated() -> None:
    earlier = _window("w1", T0, T1, {"brier": 0.20})
    later = _window("w2", T1, T2, {"brier": 0.40})
    with pytest.raises(ValueError, match="threshold_must_be_finite_nonnegative"):
        compare_windows(earlier, later, thresholds={"brier": -1.0})
    with pytest.raises(ValueError, match="threshold_must_be_finite_nonnegative"):
        compare_windows(earlier, later, thresholds={"brier": float("nan")})


# ---------------------------------------------------------------------------
# PromptModelEvaluationRecord (synthetic-labeled; no production mutation)
# ---------------------------------------------------------------------------


def _prompt_eval(**kw) -> PromptModelEvaluationRecord:
    base = dict(
        evaluation_id="pme-1",
        prompt_version="prompt-v7",
        model_id="synthetic-model-A",
        metrics_digest=_digest("prompt-eval-metrics"),
        evaluated_at_utc=T2,
        data_class="PAPER",
    )
    base.update(kw)
    return PromptModelEvaluationRecord(**base)


def test_prompt_eval_pinned_labels() -> None:
    record = _prompt_eval()
    assert record.model_id_label == "SYNTHETIC_MODEL"
    assert record.production_mutation is False
    assert record.advisory_only is True


def test_prompt_eval_production_mutation_unrepresentable() -> None:
    payload = _prompt_eval().model_dump() | {"production_mutation": True}
    with pytest.raises(ValidationError):
        PromptModelEvaluationRecord.model_validate(payload)


def test_prompt_eval_live_label_unrepresentable() -> None:
    payload = _prompt_eval().model_dump() | {"model_id_label": "PRODUCTION_MODEL"}
    with pytest.raises(ValidationError):
        PromptModelEvaluationRecord.model_validate(payload)


def test_prompt_eval_data_class_closed() -> None:
    with pytest.raises(ValidationError, match="Input should be 'SYNTHETIC' or 'PAPER'"):
        _prompt_eval(data_class="LIVE")  # type: ignore[arg-type]


def test_drift_verdict_vocabulary_closed() -> None:
    from typing import get_args

    assert set(get_args(DriftVerdict)) == {"DRIFT_DETECTED", "NO_DRIFT_DETECTED"}
