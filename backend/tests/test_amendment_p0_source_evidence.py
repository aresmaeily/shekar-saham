"""P0-AMD-1 acceptance tests: source registry (D1), monitoring jobs (D5),
evidence items and PIT semantics (D3).

Tests are derived from the amendment corpus acceptance criteria
(docs/active/P0_AMENDMENT_CONTRACTS_SCOPE_DERIVATION_REPORT.md §3), not from
the implementation: each test cites its corpus requirement.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.evidence import EvidenceConflict, EvidenceItem, filter_eligible, is_eligible_at
from app.domain.evidence import independent_corroboration_count as icc
from app.domain.monitoring import (
    MAX_CONCURRENCY,
    MAX_RETRY_ATTEMPTS,
    MAX_RUNS_PER_HOUR,
    MAX_TIMEOUT_SECONDS,
    BudgetSpec,
    MonitoringJobSpec,
    MonitoringJobState,
    RetryPolicy,
    TriggerSpec,
    effective_run_permission,
)
from app.domain.source_registry import (
    CoverageReport,
    RateLimit,
    SourceDescriptor,
    SourceRegistry,
    default_precedence_for_tier,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _source(**over) -> SourceDescriptor:
    base = dict(
        source_id="src-codal",
        name="Codal exchange disclosures",
        tier="PRIMARY_REGULATOR",
        precedence_class=default_precedence_for_tier("PRIMARY_REGULATOR"),
        ownership="exchange",
        permitted_access="public API within published rate limits",
        access_terms_version="terms-2026-01",
        refresh_policy="SCHEDULED",
    )
    base.update(over)
    return SourceDescriptor(**base)


def _evidence(**over) -> EvidenceItem:
    base = dict(
        evidence_id="ev-1",
        source_id="src-codal",
        source_identifier="https://codal.example/f/1",
        publisher="Codal",
        retrieval_time_utc=T1,
        publication_status="KNOWN",
        publication_time_utc=T0,
        source_tier="PRIMARY_REGULATOR",
        extraction_method="deterministic-parser-v1",
        corroboration_status="UNVERIFIED",
        trust_status="VERIFIED",
        citations=("Codal filing 1",),
    )
    base.update(over)
    return EvidenceItem(**base)


def _job_spec(**over) -> MonitoringJobSpec:
    base = dict(
        job_id="job-market-scan",
        target_source_ids=("src-codal",),
        trigger=TriggerSpec(kind="SCHEDULED", schedule_expression="owner-configured"),
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds_base=30),
        budget=BudgetSpec(max_runs_per_hour=4, max_timeout_seconds=600, max_concurrency=2),
        observability_ref="run-identity+audit-trace",
        alerting_ref="alert-channel-primary",
    )
    base.update(over)
    return MonitoringJobSpec(**base)


# ---------------------------------------------------------------------------
# D1 — source registry, tiers, coverage honesty
# ---------------------------------------------------------------------------


def test_registry_registration_is_versioned_and_append_only() -> None:
    reg = SourceRegistry()
    assert reg.registry_version == 1 and reg.entries == ()
    reg2 = reg.with_source(_source())
    assert reg2.registry_version == 2 and len(reg2.entries) == 1
    assert reg.registry_version == 1 and reg.entries == ()  # original immutable
    reg3 = reg2.with_source(_source(source_id="src-news", tier="REPUTABLE_FINANCIAL_NEWS",
                                    precedence_class="SECONDARY"))
    assert reg3.registry_version == 3 and len(reg3.entries) == 2


def test_registry_reregistration_identical_is_idempotent_conflicting_rejected() -> None:
    reg = SourceRegistry().with_source(_source())
    assert reg.with_source(_source()) is reg  # idempotent no-op
    with pytest.raises(ValueError, match="source_registry_conflict"):
        reg.with_source(_source(name="renamed"))


def test_source_precedence_must_match_tier() -> None:
    assert default_precedence_for_tier("PRIMARY_REGULATOR") == "PRIMARY"
    assert default_precedence_for_tier("REPUTABLE_FINANCIAL_NEWS") == "SECONDARY"
    with pytest.raises(ValidationError, match="precedence_class_inconsistent_with_tier"):
        _source(precedence_class="SECONDARY")


def test_source_descriptor_has_no_credential_material() -> None:
    """Credentials required is a boolean fact, never a secret (03 §Security)."""
    s = _source(credentials_required=True)
    assert s.credentials_required is True
    dumped = s.model_dump()
    assert not any("secret" in k or "token" in k or "key" in k or "password" in k for k in dumped)


def test_coverage_report_is_honest_and_cannot_claim_universal_coverage() -> None:
    """D-AI-38 / 06 §3: report gaps, staleness, inaccessible sources; never
    claim to monitor the entire internet."""
    reg = (
        SourceRegistry()
        .with_source(_source(status="ACTIVE", last_success_utc=T0,
                             freshness_target=timedelta(days=1)))
        .with_source(_source(source_id="src-stale", tier="ISSUER_ANNOUNCEMENT",
                             precedence_class="PRIMARY", status="ACTIVE",
                             last_success_utc=T0, freshness_target=timedelta(days=1)))
        .with_source(_source(source_id="src-down", tier="REPUTABLE_FINANCIAL_NEWS",
                             precedence_class="SECONDARY", status="INACCESSIBLE"))
        .with_source(_source(source_id="src-never", tier="MACROECONOMIC",
                             precedence_class="SECONDARY"))
    )
    report = reg.coverage_report(
        T2,
        required_source_classes=("SECTOR_INDUSTRY",),
        known_gaps=("no options chain source configured",),
    )
    assert report.universal_coverage_claimed is False
    assert report.total_configured == 4 and report.active == 2
    assert report.inaccessible == ("src-down",)
    assert set(report.stale_sources) == {"src-codal", "src-stale"}  # 8 months > 1 day
    assert set(report.never_retrieved) == {"src-down", "src-never"}  # no success recorded
    assert report.uncovered_source_classes == ("SECTOR_INDUSTRY",)
    assert report.known_gaps == ("no options chain source configured",)
    with pytest.raises(ValidationError):
        CoverageReport(
            as_of_utc=T2, registry_version=1, total_configured=0,
            universal_coverage_claimed=True,  # type: ignore[arg-type]
        )


def test_freshness_target_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="freshness_target_must_be_positive"):
        _source(freshness_target=timedelta(0))


def test_rate_limit_ceiling_is_structured_not_guessed() -> None:
    rl = RateLimit(max_requests_per_minute=60, max_retrievals_per_day=1000)
    assert rl.max_requests_per_minute == 60
    with pytest.raises(ValidationError):
        RateLimit(max_requests_per_minute=0)


# ---------------------------------------------------------------------------
# D5 — monitoring job identity, fail-closed kill switch
# ---------------------------------------------------------------------------


def test_kill_switch_defaults_engaged_fail_closed() -> None:
    """06 §9 / D-AI-32: kill switch present; default state must be safe."""
    spec = _job_spec()
    assert spec.kill_switch == "ENGAGED"
    assert spec.run_allowed() is False
    released = _job_spec(kill_switch="RELEASED")
    assert released.run_allowed() is True


def test_trigger_kind_consistency() -> None:
    with pytest.raises(ValidationError, match="scheduled_trigger_requires_expression"):
        TriggerSpec(kind="SCHEDULED")
    with pytest.raises(ValidationError, match="event_trigger_requires_event_types"):
        TriggerSpec(kind="EVENT_DRIVEN")
    with pytest.raises(ValidationError, match="event_trigger_forbids_schedule_expression"):
        TriggerSpec(kind="EVENT_DRIVEN", event_types=("filing",), schedule_expression="x")
    with pytest.raises(ValidationError, match="scheduled_trigger_forbids_event_types"):
        TriggerSpec(kind="SCHEDULED", schedule_expression="x", event_types=("filing",))


def test_retry_and_budget_ceilings_are_enforced() -> None:
    """06 §9: retry ceilings, timeout, concurrency/rate limits — bounded."""
    with pytest.raises(ValidationError):
        RetryPolicy(max_attempts=MAX_RETRY_ATTEMPTS + 1, backoff_seconds_base=1)
    with pytest.raises(ValidationError):
        BudgetSpec(max_runs_per_hour=MAX_RUNS_PER_HOUR + 1, max_timeout_seconds=1,
                   max_concurrency=1)
    with pytest.raises(ValidationError):
        BudgetSpec(max_runs_per_hour=1, max_timeout_seconds=MAX_TIMEOUT_SECONDS + 1,
                   max_concurrency=1)
    with pytest.raises(ValidationError):
        BudgetSpec(max_runs_per_hour=1, max_timeout_seconds=1, max_concurrency=MAX_CONCURRENCY + 1)


def test_job_state_consistency_rules() -> None:
    with pytest.raises(ValidationError, match="healthy_state_requires_zero"):
        MonitoringJobState(job_id="j", consecutive_failures=2)
    with pytest.raises(ValidationError, match="halted_state_requires_failure_alert"):
        MonitoringJobState(job_id="j", failure_state="HALTED")
    ok = MonitoringJobState(job_id="j", failure_state="HALTED", failure_alert_sent=True)
    assert ok.failure_alert_sent is True


def test_effective_run_permission_is_fail_closed() -> None:
    spec = _job_spec()
    healthy = MonitoringJobState(job_id="job-market-scan")
    assert effective_run_permission(spec, healthy) is False  # kill switch engaged
    released = _job_spec(kill_switch="RELEASED")
    assert effective_run_permission(released, healthy) is True
    halted = MonitoringJobState(job_id="job-market-scan", failure_state="HALTED",
                                failure_alert_sent=True)
    assert effective_run_permission(released, halted) is False  # recovery is explicit
    assert effective_run_permission(released, MonitoringJobState(job_id="other")) is False


def test_job_spec_targets_and_sla_validation() -> None:
    with pytest.raises(ValidationError, match="target_source_ids_duplicates"):
        _job_spec(target_source_ids=("a", "a"))
    with pytest.raises(ValidationError, match="freshness_sla_must_be_positive"):
        _job_spec(freshness_sla=timedelta(0))


# ---------------------------------------------------------------------------
# D3 — evidence item schema, corroboration, conflicts, PIT eligibility
# ---------------------------------------------------------------------------


def test_publication_time_is_recorded_separately_and_never_defaulted() -> None:
    """06 §3.5: publication time separate from retrieval time; unknown stays
    explicitly unknown — it must never be silently defaulted."""
    e = _evidence()
    assert e.publication_time_utc == T0 and e.retrieval_time_utc == T1
    with pytest.raises(ValidationError, match="known_publication_requires_timestamp"):
        _evidence(publication_time_utc=None, publication_status="KNOWN")
    unknown = _evidence(publication_time_utc=None, publication_status="UNAVAILABLE")
    assert unknown.publication_time_utc is None  # stays unknown, not replaced


def test_document_hash_and_citation_requirements() -> None:
    e = _evidence(document_sha256="a" * 64)
    assert e.document_sha256 == "a" * 64
    with pytest.raises(ValidationError):
        _evidence(document_sha256="not-a-hash")
    with pytest.raises(ValidationError, match="citations"):
        _evidence(citations=())


def test_syndicated_copies_are_not_independent_corroboration() -> None:
    """06 §3.3: syndications must not be mistaken for independent corroboration;
    duplicates from one source cluster to one count."""
    items = [
        _evidence(evidence_id="ev-1", corroboration_status="CORROBORATED"),
        _evidence(evidence_id="ev-2", source_id="src-codal", corroboration_status="CORROBORATED"),
        _evidence(evidence_id="ev-3", source_id="src-wire-copy", corroboration_status="SYNDICATED_COPY"),
        _evidence(evidence_id="ev-4", source_id="src-unverified", corroboration_status="UNVERIFIED"),
    ]
    assert icc(items) == 1  # two CORROBORATED items share one source_id
    assert icc([_evidence(evidence_id="ev-5", source_id="s1", corroboration_status="CORROBORATED"),
                _evidence(evidence_id="ev-6", source_id="s2", corroboration_status="CORROBORATED")]) == 2


def test_conflicts_stay_explicit_until_deterministic_or_human_resolution() -> None:
    """06 §3.4 / D-AI-33: contradictions remain explicit; no silent merge."""
    conflict = EvidenceConflict(
        conflict_id="cf-1", evidence_ids=("ev-1", "ev-2"),
        description="revenue figures disagree", status="OPEN",
    )
    assert conflict.resolution_rule is None
    with pytest.raises(ValidationError, match="open_conflict_cannot_carry_resolution"):
        EvidenceConflict(conflict_id="cf-1", evidence_ids=("ev-1", "ev-2"),
                         description="x", status="OPEN", resolution_rule="take-max")
    with pytest.raises(ValidationError, match="resolved_conflict_requires"):
        EvidenceConflict(conflict_id="cf-1", evidence_ids=("ev-1", "ev-2"),
                         description="x", status="RESOLVED_HUMAN")
    resolved = EvidenceConflict(
        conflict_id="cf-1", evidence_ids=("ev-1", "ev-2"), description="x",
        status="RESOLVED_DETERMINISTIC", resolution_rule="prefer-primary-source-v1",
        resolved_by="deterministic-rule", resolved_at_utc=T1,
    )
    assert resolved.status == "RESOLVED_DETERMINISTIC"


def test_pit_eligibility_excludes_later_information() -> None:
    """02:142 / 06 §3.6: historical research cannot use later-published info."""
    early = _evidence()  # published T0, retrieved T1
    assert is_eligible_at(early, T1) is True  # possessed at retrieval, published earlier
    assert is_eligible_at(early, T0) is False  # retrieved only at T1
    assert is_eligible_at(early, T0 - timedelta(seconds=1)) is False
    later_published = _evidence(evidence_id="ev-2", publication_time_utc=T2)
    assert is_eligible_at(later_published, T1) is False
    assert is_eligible_at(later_published, T2) is True


def test_pit_availability_uses_later_of_publication_and_retrieval() -> None:
    from app.domain.evidence import availability_time

    late_retrieval = _evidence(evidence_id="ev-2", publication_time_utc=T0,
                               retrieval_time_utc=T2)
    assert availability_time(late_retrieval) == T2  # possession confirmed at retrieval
    unknown_pub = _evidence(evidence_id="ev-3", publication_time_utc=None,
                            publication_status="UNAVAILABLE", retrieval_time_utc=T1)
    assert availability_time(unknown_pub) == T1  # conservative: retrieval time


def test_filter_eligible_is_deterministic() -> None:
    items = [_evidence(), _evidence(evidence_id="ev-2", publication_time_utc=T2)]
    assert tuple(i.evidence_id for i in filter_eligible(items, T1)) == ("ev-1",)
    assert tuple(i.evidence_id for i in filter_eligible(items, T2)) == ("ev-1", "ev-2")


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone_aware"):
        _evidence(retrieval_time_utc=datetime(2026, 6, 1))  # no tzinfo
