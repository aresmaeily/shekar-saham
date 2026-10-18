"""AI-1 gap-closure acceptance tests — opportunity objects, clusters, governed monitoring.

Derived from the 2026-10-02 amendment corpus (byte-verified), NOT from the
implementation:
- 02_EXECUTION_ROADMAP lines 148–153: four-way opportunity-kind distinction;
  each object needs evidence, timestamp, confidence semantics, data trust,
  risk, invalidation/expiry and reason-for-now; M&A "never conflated with a
  stock-buy signal".
- 06_PRODUCT_CAPABILITY_CHARTER §4: three-concept non-conflation; an
  acquisition-target signal requires its own evidence and must not be
  inferred solely from a stock opportunity score.
- 06 §6: explainable clusters; formal class definitions; the five explanation
  questions; historical evaluation never fabricated.
- 02 lines 155–156, 193 + D-AI-32/38 + 06 §9: governed monitoring honesty —
  permission truth, coverage honesty, failure honesty, fail-closed refusal.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.monitoring import (
    BudgetSpec,
    MonitoringJobSpec,
    MonitoringJobState,
    RetryPolicy,
    TriggerSpec,
)
from app.domain.monitoring_governance import (
    GovernedMonitoringCycleRecord,
    record_monitoring_cycle,
)
from app.domain.opportunity import (
    ClassDefinition,
    OpportunityCluster,
    OpportunityObject,
    active_at,
    is_expired,
)
from app.domain.run_governance import RunContext
from app.domain.source_registry import CoverageReport

UTC = timezone.utc
T0 = datetime(2026, 10, 18, 9, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 18, 9, 30, 0, tzinfo=UTC)
EXPIRY = T0 + timedelta(days=5)

CLASS_DEF = ClassDefinition(
    label="EARLY_ACCUMULATION",
    formal_definition="Sustained quiet buying with rising value and flat price over N sessions.",
    data_prerequisites=("money_flow", "volume", "close_series"),
    time_horizon="swing",
)


def obj(**over: object) -> OpportunityObject:
    base = dict(
        object_id="o1",
        opportunity_kind="MARKET_STOCK_INVESTMENT_CANDIDATE",
        company_role="INVESTMENT_CANDIDATE",
        subject="فملی",
        created_at_utc=T0,
        reason_for_now="Money-flow turned positive while price stayed flat for 4 sessions.",
        confidence=Decimal("0.62"),
        confidence_basis="deterministic composite score with trust cap",
        data_trust_state="live",
        risk_semantics="medium; liquidity contraction invalidates",
        evidence_ids=("ev-1", "ev-2"),
        invalidation_conditions=("money_flow negative for 2 sessions",),
        expiry_utc=EXPIRY,
        basis="EVIDENCE_BASED",
        run_id="run-1",
    )
    base.update(over)
    return OpportunityObject(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# OpportunityObject — 02 lines 148–153 required fields
# ---------------------------------------------------------------------------


def test_opportunity_object_minimal_valid_and_frozen() -> None:
    o = obj()
    assert o.schema_version
    with pytest.raises(ValidationError):
        o.reason_for_now = "mutated"  # type: ignore[misc]


def test_required_honesty_fields_enforced() -> None:
    with pytest.raises(ValidationError):
        obj(reason_for_now="")  # empty reason-for-now (02:153)
    with pytest.raises(ValidationError):
        obj(invalidation_conditions=())  # no invalidation (02:153)
    with pytest.raises(ValidationError):
        obj(evidence_ids=())  # no evidence (02:153)
    with pytest.raises(ValidationError):
        obj(data_trust_state="")  # no data-trust semantics (02:153)
    with pytest.raises(ValidationError):
        obj(risk_semantics="")  # no risk semantics (02:153)
    with pytest.raises(ValidationError):
        obj(confidence_basis="")  # no confidence semantics (02:153)


def test_expiry_must_be_explicit_not_forgotten() -> None:
    with pytest.raises(ValidationError, match="expiry_must_be_dated_or_explicitly_open_ended"):
        obj(expiry_utc=None, expiry_open_ended=False)
    open_ended = obj(expiry_utc=None, expiry_open_ended=True)
    assert open_ended.expiry_utc is None
    with pytest.raises(ValidationError, match="open_ended_expiry_forbids_date"):
        obj(expiry_open_ended=True)


def test_confidence_bounds_deterministic() -> None:
    with pytest.raises(ValidationError):
        obj(confidence=Decimal("1.5"))
    with pytest.raises(ValidationError):
        obj(confidence=Decimal("-0.1"))


# ---------------------------------------------------------------------------
# M&A non-conflation — 06 §4 / 02:148–153
# ---------------------------------------------------------------------------


def test_ma_signal_refuses_score_only_basis() -> None:
    with pytest.raises(ValidationError, match="ma_signal_requires_evidence_basis"):
        obj(
            opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
            company_role="MA_TARGET_SIGNAL",
            basis="OPPORTUNITY_SCORE_ONLY",
            ma_signal_evidence_ids=("ma-ev-1",),
        )


def test_ma_signal_requires_dedicated_evidence() -> None:
    with pytest.raises(ValidationError, match="ma_signal_requires_dedicated_evidence"):
        obj(
            opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
            company_role="MA_TARGET_SIGNAL",
            basis="EVIDENCE_BASED",
            ma_signal_evidence_ids=(),
        )


def test_ma_signal_with_own_evidence_accepted() -> None:
    o = obj(
        opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
        company_role="MA_TARGET_SIGNAL",
        basis="EVIDENCE_BASED",
        evidence_ids=("ev-1",),
        ma_signal_evidence_ids=("ma-ev-1", "ma-ev-2"),
        reason_for_now="Two independent regulatory filings reference a stake change.",
    )
    assert o.ma_signal_evidence_ids == ("ma-ev-1", "ma-ev-2")


@pytest.mark.parametrize(
    ("kind", "role"),
    [
        ("MARKET_STOCK_INVESTMENT_CANDIDATE", "WATCHLIST_COMPANY"),
        ("USER_WATCHLIST_COMPANY_INTELLIGENCE", "INVESTMENT_CANDIDATE"),
        ("CORPORATE_MA_ACQUISITION_TARGET_SIGNAL", "INVESTMENT_CANDIDATE"),
    ],
)
def test_kind_role_conflation_rejected(kind: str, role: str) -> None:
    with pytest.raises(ValidationError, match="opportunity_kind_company_role_conflation"):
        obj(opportunity_kind=kind, company_role=role)  # type: ignore[arg-type]


def test_event_driven_kind_role_free_but_evidence_still_required() -> None:
    o = obj(
        opportunity_kind="EVENT_NEWS_DRIVEN_CANDIDATE",
        company_role="INVESTMENT_CANDIDATE",
        reason_for_now="Exchange disclosure published today.",
    )
    assert o.opportunity_kind == "EVENT_NEWS_DRIVEN_CANDIDATE"


# ---------------------------------------------------------------------------
# Class labels and clusters — 06 §6
# ---------------------------------------------------------------------------


def test_labelled_class_requires_matching_definition() -> None:
    with pytest.raises(ValidationError, match="labelled_class_requires_class_definition"):
        obj(class_label="EARLY_ACCUMULATION")
    with pytest.raises(ValidationError, match="class_definition_label_mismatch"):
        obj(
            class_label="EARLY_ACCUMULATION",
            class_definition=CLASS_DEF.model_copy(update={"label": "RELATIVE_STRENGTH"}),
        )
    ok = obj(class_label="EARLY_ACCUMULATION", class_definition=CLASS_DEF)
    assert ok.class_definition is not None


def test_unclassified_object_cannot_carry_definition() -> None:
    with pytest.raises(ValidationError, match="unclassified_object_cannot_carry_class_definition"):
        obj(class_definition=CLASS_DEF)


def test_expiry_helpers_deterministic() -> None:
    o = obj()
    assert not is_expired(o, T0 + timedelta(days=4))
    assert is_expired(o, EXPIRY)
    assert is_expired(o, EXPIRY + timedelta(seconds=1))
    open_ended = obj(expiry_utc=None, expiry_open_ended=True)
    assert not is_expired(open_ended, T0 + timedelta(days=3650))
    future = obj(created_at_utc=T1)
    assert not active_at(future, T0)
    assert active_at(o, T0 + timedelta(days=1))


def cluster(**over: object) -> OpportunityCluster:
    base = dict(
        cluster_id="c1",
        class_label="EARLY_ACCUMULATION",
        class_definition=CLASS_DEF,
        member_object_ids=("o1", "o2"),
        created_at_utc=T0,
        run_id="run-1",
        why_now="Sector-wide value expansion started this session.",
        invalidation_conditions=("breadth collapse",),
        risk_adjusted_interpretation="Favorable asymmetry only while liquidity holds.",
        missing_information=("institutional queue depth",),
        confidence=Decimal("0.55"),
        confidence_basis="cluster-level deterministic aggregate",
    )
    base.update(over)
    return OpportunityCluster(**base)  # type: ignore[arg-type]


def test_cluster_requires_all_five_explanations() -> None:
    ok = cluster()
    assert ok.why_now and ok.invalidation_conditions and ok.missing_information
    with pytest.raises(ValidationError):
        cluster(why_now="")
    with pytest.raises(ValidationError):
        cluster(invalidation_conditions=())
    with pytest.raises(ValidationError):
        cluster(risk_adjusted_interpretation="")
    with pytest.raises(ValidationError):
        cluster(missing_information=())


def test_cluster_refuses_unclassified_and_requires_run_id() -> None:
    with pytest.raises(ValidationError, match="cluster_requires_concrete_class"):
        cluster(
            class_label="UNCLASSIFIED",
            class_definition=CLASS_DEF.model_copy(update={"label": "UNCLASSIFIED"}),
        )
    with pytest.raises(ValidationError):
        cluster(run_id="")


def test_cluster_members_distinct() -> None:
    with pytest.raises(ValidationError, match="duplicate_items"):
        cluster(member_object_ids=("o1", "o1"))


# ---------------------------------------------------------------------------
# Governed monitoring cycle — 02:155–156/193, D-AI-32/38, 06 §9
# ---------------------------------------------------------------------------


def spec(kill_switch: str = "ENGAGED", job_id: str = "job-1") -> MonitoringJobSpec:
    return MonitoringJobSpec(
        job_id=job_id,
        target_source_ids=("src-1", "src-2"),
        trigger=TriggerSpec(kind="SCHEDULED", schedule_expression="0 8 * * *"),
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds_base=5),
        budget=BudgetSpec(max_runs_per_hour=4, max_timeout_seconds=600, max_concurrency=1),
        observability_ref="obs://job-1",
        alerting_ref="alerts://job-1",
        kill_switch=kill_switch,  # type: ignore[arg-type]
    )


def state(job_id: str = "job-1", **over: object) -> MonitoringJobState:
    base = dict(job_id=job_id, last_attempt_utc=T0)
    base.update(over)
    return MonitoringJobState(**base)  # type: ignore[arg-type]


def run_ctx() -> RunContext:
    return RunContext(
        run_id="run-mon-1",
        run_kind="MONITORING_CYCLE",
        policy_version="gov-1",
        created_at_utc=T0,
    )


def coverage() -> CoverageReport:
    return CoverageReport(
        as_of_utc=T0,
        registry_version=3,
        total_configured=5,
        active=3,
        inaccessible=("src-9",),
        stale_sources=("src-2",),
        never_retrieved=("src-4",),
        uncovered_source_classes=("REGULATOR_FILING",),
        known_gaps=("no macro calendar source",),
    )


def test_released_job_completed_cycle() -> None:
    rec = record_monitoring_cycle(
        record_id="rec-1",
        spec=spec(kill_switch="RELEASED"),
        state=state(last_success_utc=T0 - timedelta(hours=1)),
        context=run_ctx(),
        coverage=coverage(),
        started_at_utc=T0,
        finished_at_utc=T1,
        sources_attempted=("src-1", "src-2"),
        sources_succeeded=("src-1", "src-2"),
        event_ids=("ev-m1",),
    )
    assert rec.outcome == "COMPLETED"
    assert rec.permission_granted is True
    assert rec.coverage.universal_coverage_claimed is False  # D-AI-38 structural lock


def test_kill_switch_engaged_refuses_fail_closed() -> None:
    rec = record_monitoring_cycle(
        record_id="rec-2",
        spec=spec(kill_switch="ENGAGED"),
        state=state(),
        context=run_ctx(),
        coverage=coverage(),
        started_at_utc=T0,
        sources_attempted=("src-1",),
    )
    assert rec.outcome == "REFUSED_BY_POLICY"
    assert rec.permission_granted is False
    assert rec.finished_at_utc is None
    with pytest.raises(ValidationError, match="refused_cycle_cannot_claim_successes_or_events"):
        GovernedMonitoringCycleRecord(
            **{**rec.model_dump(), "event_ids": ("ghost",)}
        )


def test_halted_job_refused() -> None:
    rec = record_monitoring_cycle(
        record_id="rec-3",
        spec=spec(kill_switch="RELEASED"),
        state=state(failure_state="HALTED", failure_alert_sent=True),
        context=run_ctx(),
        coverage=coverage(),
        started_at_utc=T0,
        sources_attempted=("src-1",),
    )
    assert rec.outcome == "REFUSED_BY_POLICY"


def test_job_id_mismatch_refused() -> None:
    with pytest.raises(ValueError, match="job_id_mismatch"):
        record_monitoring_cycle(
            record_id="rec-4",
            spec=spec(kill_switch="RELEASED"),
            state=state(job_id="other-job"),
            context=run_ctx(),
            coverage=coverage(),
            started_at_utc=T0,
            sources_attempted=("src-1",),
            sources_succeeded=("src-1",),
        )


def test_failed_sources_force_honest_outcome() -> None:
    rec = record_monitoring_cycle(
        record_id="rec-5",
        spec=spec(kill_switch="RELEASED"),
        state=state(last_success_utc=T0),
        context=run_ctx(),
        coverage=coverage(),
        started_at_utc=T0,
        finished_at_utc=T1,
        sources_attempted=("src-1", "src-2"),
        sources_succeeded=("src-1",),
        sources_failed=("src-2",),
        failure_notes=("src-2 timeout",),
    )
    assert rec.outcome == "PARTIAL"
    with pytest.raises(ValidationError, match="failed_sources_force_partial_or_failed_outcome"):
        GovernedMonitoringCycleRecord(**{**rec.model_dump(), "outcome": "COMPLETED"})
    with pytest.raises(ValidationError, match="executed_cycle_requires_finish_timestamp"):
        GovernedMonitoringCycleRecord(**{**rec.model_dump(), "finished_at_utc": None})


def test_failed_cycle_with_success_forces_partial() -> None:
    rec = record_monitoring_cycle(
        record_id="rec-6",
        spec=spec(kill_switch="RELEASED"),
        state=state(last_success_utc=T0),
        context=run_ctx(),
        coverage=coverage(),
        started_at_utc=T0,
        finished_at_utc=T1,
        sources_attempted=("src-1", "src-2"),
        sources_succeeded=("src-1",),
        sources_failed=("src-2",),
    )
    assert rec.outcome == "PARTIAL"
    with pytest.raises(ValidationError, match="succeeded_sources_force_partial_outcome"):
        GovernedMonitoringCycleRecord(**{**rec.model_dump(), "outcome": "FAILED"})


def test_source_outcomes_must_be_within_attempted_set() -> None:
    with pytest.raises(ValidationError, match="source_outcomes_outside_attempted_set"):
        record_monitoring_cycle(
            record_id="rec-7",
            spec=spec(kill_switch="RELEASED"),
            state=state(last_success_utc=T0),
            context=run_ctx(),
            coverage=coverage(),
            started_at_utc=T0,
            finished_at_utc=T1,
            sources_attempted=("src-1",),
            sources_succeeded=("src-1", "src-ghost"),
        )


def test_cycle_requires_monitoring_run_kind() -> None:
    wrong = RunContext(
        run_id="run-x",
        run_kind="SYMBOL_INTERPRETATION",
        policy_version="gov-1",
        created_at_utc=T0,
    )
    with pytest.raises(ValueError, match="monitoring_cycle_requires_monitoring_run_kind"):
        record_monitoring_cycle(
            record_id="rec-8",
            spec=spec(kill_switch="RELEASED"),
            state=state(last_success_utc=T0),
            context=wrong,
            coverage=coverage(),
            started_at_utc=T0,
            finished_at_utc=T1,
            sources_attempted=("src-1",),
            sources_succeeded=("src-1",),
        )


def test_cycle_record_frozen_and_naive_timestamp_rejected() -> None:
    rec = record_monitoring_cycle(
        record_id="rec-9",
        spec=spec(kill_switch="RELEASED"),
        state=state(last_success_utc=T0),
        context=run_ctx(),
        coverage=coverage(),
        started_at_utc=T0,
        finished_at_utc=T1,
        sources_attempted=("src-1",),
        sources_succeeded=("src-1",),
    )
    with pytest.raises(ValidationError):
        rec.outcome = "FAILED"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        record_monitoring_cycle(
            record_id="rec-10",
            spec=spec(kill_switch="RELEASED"),
            state=state(last_success_utc=T0),
            context=run_ctx(),
            coverage=coverage(),
            started_at_utc=datetime(2026, 10, 18, 9, 0, 0),
            finished_at_utc=T1,
            sources_attempted=("src-1",),
            sources_succeeded=("src-1",),
        )


def test_naive_coverage_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        CoverageReport(
            as_of_utc=datetime(2026, 10, 18, 9, 0, 0),
            registry_version=1,
            total_configured=1,
            active=1,
        )
