"""AI-5 Proactive Intelligence acceptance tests (corpus-derived).

Sources: 02:92-95 (bounded research with budget/observability/recovery/kill
switch), 02:155-156 (coverage honesty), 02:186 (explicit configuration,
idempotency, retry ceilings, kill switch), 02:202 (pre-G2 synthetic class),
D-AI-30 (DEFERRED UNTIL CORE STABILITY — runtime excluded), D-AI-38
(coverage/freshness honesty; no universal-coverage implication), D-AI-19
(deterministic financial authority), 06 §9 (no hard-coded cadence).
Contract-level synthetic tests only — no scheduler, no I/O, no network, no
LLM, no real data (02:202; G2 NOT_PASSED).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.monitoring import BudgetSpec, RetryPolicy, TriggerSpec
from app.domain.proactive_research import (
    MAX_RESEARCH_QUESTIONS,
    CoverageFreshnessStatement,
    ProactiveResearchJobSpec,
    ProactiveResearchJobState,
    effective_research_run_permission,
)
from app.domain.run_governance import RunContext, RunProvenance

UTC = timezone.utc


def _trigger() -> TriggerSpec:
    return TriggerSpec(kind="SCHEDULED", schedule_expression="OWNER_CONFIGURED")


def _spec(kill_switch: str = "ENGAGED", job_id: str = "rj-1") -> ProactiveResearchJobSpec:
    return ProactiveResearchJobSpec(
        research_job_id=job_id,
        trigger=_trigger(),
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds_base=30),
        budget=BudgetSpec(max_runs_per_hour=4, max_timeout_seconds=600, max_concurrency=1),
        research_questions=("Q1: does regime X persist?",),
        evidence_ref="research_memory://episodic",
        observability_ref="obs://rj-1",
        alerting_ref="alerts://rj-1",
        kill_switch=kill_switch,  # type: ignore[arg-type]
    )


def _state(job_id: str = "rj-1", **kw) -> ProactiveResearchJobState:
    return ProactiveResearchJobState(research_job_id=job_id, **kw)


def _context(**kw) -> RunContext:
    base = dict(
        run_id="run-1",
        run_kind="PROACTIVE_RESEARCH",
        autonomy_level="L0",
        approval_state="NOT_REQUIRED",
        policy_version="pv-1",
        created_at_utc=datetime(2026, 10, 28, 12, 0, 0, tzinfo=UTC),
    )
    base.update(kw)
    return RunContext(**base)


def _provenance(run_id: str = "run-1", **kw) -> RunProvenance:
    base = dict(
        run_id=run_id,
        policy_version="pv-1",
        started_at_utc=datetime(2026, 10, 28, 12, 0, 0, tzinfo=UTC),
        finished_at_utc=datetime(2026, 10, 28, 12, 5, 0, tzinfo=UTC),
        hypothesis_id="h-1",
        dataset_version="synthetic-2026-10-28",
        code_commit="0" * 40,
        model_version="none-contract-only",
        prompt_version="none-contract-only",
        evaluation_version="none-contract-only",
    )
    base.update(kw)
    return RunProvenance(**base)


# ---------------------------------------------------------------------------
# Spec construction and structural invariants
# ---------------------------------------------------------------------------


def test_spec_defaults_fail_closed() -> None:
    spec = _spec()
    assert spec.kill_switch == "ENGAGED"
    assert spec.run_allowed() is False


def test_released_kill_switch_allows_policy_run() -> None:
    spec = _spec(kill_switch="RELEASED")
    assert spec.run_allowed() is True


def test_production_mutation_structurally_forbidden() -> None:
    assert ProactiveResearchJobSpec.model_fields["production_mutation"].annotation is not bool
    dump = _spec().model_dump() | {"production_mutation": True}
    with pytest.raises(ValidationError):
        ProactiveResearchJobSpec.model_validate(dump)


def test_financial_authority_pinned_deterministic() -> None:
    spec = _spec()
    assert spec.financial_authority == "DETERMINISTIC_ONLY"
    with pytest.raises(ValidationError):
        ProactiveResearchJobSpec.model_validate(spec.model_dump() | {"financial_authority": "AI_GENERATED"})


def test_coverage_honesty_required_pinned_true() -> None:
    with pytest.raises(ValidationError):
        ProactiveResearchJobSpec.model_validate(_spec().model_dump() | {"coverage_honesty_required": False})


def test_output_binding_pinned_episodic() -> None:
    with pytest.raises(ValidationError):
        ProactiveResearchJobSpec.model_validate(_spec().model_dump() | {"output_binding": "PRODUCTION_APPLY"})


def test_scheduled_trigger_requires_expression() -> None:
    with pytest.raises(ValidationError):
        TriggerSpec(kind="SCHEDULED")


def test_event_trigger_requires_event_types() -> None:
    with pytest.raises(ValidationError):
        TriggerSpec(kind="EVENT_DRIVEN")


def test_scheduled_trigger_forbids_event_types() -> None:
    with pytest.raises(ValidationError):
        TriggerSpec(kind="SCHEDULED", schedule_expression="0 9 * * *", event_types=("gap",))


def test_event_trigger_forbids_schedule_expression() -> None:
    with pytest.raises(ValidationError):
        TriggerSpec(kind="EVENT_DRIVEN", event_types=("gap",), schedule_expression="0 9 * * *")


def test_research_questions_empty_rejected() -> None:
    dump = _spec().model_dump() | {"research_questions": ()}
    with pytest.raises(ValidationError):
        ProactiveResearchJobSpec.model_validate(dump)


def test_research_questions_blank_rejected() -> None:
    dump = _spec().model_dump() | {"research_questions": ("  ",)}
    with pytest.raises(ValidationError):
        ProactiveResearchJobSpec.model_validate(dump)


def test_research_questions_duplicates_rejected() -> None:
    dump = _spec().model_dump() | {"research_questions": ("Q1", "Q1")}
    with pytest.raises(ValidationError):
        ProactiveResearchJobSpec.model_validate(dump)


def test_research_questions_ceiling_enforced() -> None:
    dump = _spec().model_dump() | {"research_questions": tuple(f"q{i}" for i in range(MAX_RESEARCH_QUESTIONS + 1))}
    with pytest.raises(ValidationError):
        ProactiveResearchJobSpec.model_validate(dump)


def test_budget_ceilings_bounded_by_p0_schema() -> None:
    with pytest.raises(ValidationError):
        BudgetSpec(max_runs_per_hour=61, max_timeout_seconds=600, max_concurrency=1)
    with pytest.raises(ValidationError):
        RetryPolicy(max_attempts=11, backoff_seconds_base=1)


def test_no_cadence_value_exists_in_spec() -> None:
    dump = _spec().model_dump()
    assert "schedule_expression" not in {k for k in dump if "cadence" in k.lower()}
    assert dump["trigger"]["schedule_expression"] == "OWNER_CONFIGURED"


def test_schema_version_bound() -> None:
    assert _spec().schema_version and _state().schema_version


def test_frozen_models_reject_mutation() -> None:
    spec = _spec()
    with pytest.raises(ValidationError):
        spec.research_job_id = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# State honesty rules
# ---------------------------------------------------------------------------


def test_healthy_requires_zero_failures() -> None:
    with pytest.raises(ValidationError):
        _state(consecutive_failures=2)


def test_halted_requires_failure_alert() -> None:
    with pytest.raises(ValidationError):
        _state(failure_state="HALTED", consecutive_failures=3, failure_alert_sent=False)


def test_halted_with_alert_is_representable() -> None:
    st = _state(failure_state="HALTED", consecutive_failures=3, failure_alert_sent=True)
    assert st.failure_state == "HALTED"


def test_naive_timestamp_rejected_aware_round_trips() -> None:
    # Canonical rule (evidence.ensure_utc): naive timestamps are REJECTED,
    # not silently converted — mirrors MonitoringJobState._utc exactly.
    with pytest.raises(ValidationError):
        _state(last_success_utc=datetime(2026, 10, 28, 12, 0, 0))
    st = _state(last_success_utc=datetime(2026, 10, 28, 12, 0, 0, tzinfo=UTC))
    assert st.last_success_utc is not None and st.last_success_utc.tzinfo is not None


def test_artifact_ids_bounded_and_distinct() -> None:
    with pytest.raises(ValidationError):
        _state(last_run_artifact_ids=tuple(f"a{i}" for i in range(33)))
    with pytest.raises(ValidationError):
        _state(last_run_artifact_ids=("a1", "a1"))


# ---------------------------------------------------------------------------
# Coverage/freshness honesty (D-AI-38)
# ---------------------------------------------------------------------------


def test_universal_coverage_claim_unrepresentable() -> None:
    with pytest.raises(ValidationError):
        CoverageFreshnessStatement.model_validate(
            {
                "research_job_id": "rj-1",
                "coverage_declared": True,
                "coverage_complete": True,
                "universal_coverage_claimed": True,
            }
        )


def test_incomplete_coverage_requires_known_gaps() -> None:
    with pytest.raises(ValidationError):
        CoverageFreshnessStatement(
            research_job_id="rj-1", coverage_declared=True, coverage_complete=False
        )


def test_complete_statement_with_gaps_and_conflicts_ok() -> None:
    st = CoverageFreshnessStatement(
        research_job_id="rj-1",
        coverage_declared=True,
        coverage_complete=False,
        known_gaps=("source-B inaccessible",),
        source_failures=("source-C timeout",),
        unresolved_conflicts=("A vs B price conflict",),
        last_successful_retrieval_utc=datetime(2026, 10, 28, 11, 0, 0, tzinfo=UTC),
        freshness_age_seconds=3600.0,
    )
    assert st.known_gaps and st.universal_coverage_claimed is False


def test_freshness_age_non_negative() -> None:
    with pytest.raises(ValidationError):
        CoverageFreshnessStatement(
            research_job_id="rj-1",
            coverage_declared=True,
            coverage_complete=True,
            freshness_age_seconds=-1.0,
        )


# ---------------------------------------------------------------------------
# Deterministic run permission
# ---------------------------------------------------------------------------


def test_permission_refused_when_kill_switch_engaged() -> None:
    ok, refusals = effective_research_run_permission(
        _spec(), _state(), _context(), _provenance(), autonomy_ceiling="L2"
    )
    assert ok is False and "kill_switch_engaged" in refusals


def test_permission_refused_on_job_id_mismatch() -> None:
    ok, refusals = effective_research_run_permission(
        _spec(kill_switch="RELEASED"),
        _state(job_id="other"),
        _context(),
        _provenance(),
        autonomy_ceiling="L2",
    )
    assert ok is False and "job_id_mismatch" in refusals


def test_permission_refused_when_halted() -> None:
    ok, refusals = effective_research_run_permission(
        _spec(kill_switch="RELEASED"),
        _state(failure_state="HALTED", consecutive_failures=3, failure_alert_sent=True),
        _context(),
        _provenance(),
        autonomy_ceiling="L2",
    )
    assert ok is False and "failure_state_halted" in refusals


def test_permission_refused_on_missing_provenance() -> None:
    ok, refusals = effective_research_run_permission(
        _spec(kill_switch="RELEASED"),
        _state(),
        _context(),
        _provenance(dataset_version=None),
        autonomy_ceiling="L2",
    )
    assert ok is False
    assert "missing_provenance:dataset_version" in refusals


def test_permission_refused_on_provenance_run_mismatch() -> None:
    ok, refusals = effective_research_run_permission(
        _spec(kill_switch="RELEASED"),
        _state(),
        _context(),
        _provenance(run_id="other-run"),
        autonomy_ceiling="L2",
    )
    assert ok is False and "missing_provenance:run_id_binding" in refusals


def test_permission_refused_when_autonomy_exceeds_ceiling() -> None:
    ok, refusals = effective_research_run_permission(
        _spec(kill_switch="RELEASED"),
        _state(),
        _context(autonomy_level="L3"),
        _provenance(),
        autonomy_ceiling="L2",
    )
    assert ok is False and "autonomy_level_exceeds_declared_ceiling" in refusals


def test_permission_granted_on_fully_governed_cycle() -> None:
    ok, refusals = effective_research_run_permission(
        _spec(kill_switch="RELEASED"),
        _state(),
        _context(),
        _provenance(),
        autonomy_ceiling="L2",
    )
    assert ok is True and refusals == ()


def test_permission_is_deterministic() -> None:
    args = (_spec(kill_switch="RELEASED"), _state(), _context(), _provenance())
    a = effective_research_run_permission(*args, autonomy_ceiling="L2")
    b = effective_research_run_permission(*args, autonomy_ceiling="L2")
    assert a == b


def test_refusal_tags_stable_and_ordered() -> None:
    ok, refusals = effective_research_run_permission(
        _spec(),  # ENGAGED
        _state(job_id="other"),
        _context(autonomy_level="L3"),  # L3 needs no approval record; exceeds L0 ceiling
        _provenance(run_id="mismatch"),
        autonomy_ceiling="L0",
    )
    assert ok is False
    assert refusals == (
        "kill_switch_engaged",
        "job_id_mismatch",
        "missing_provenance:run_id_binding",
        "autonomy_level_exceeds_declared_ceiling",
    )


def test_no_timedelta_or_clock_io_in_module() -> None:
    import inspect

    import app.domain.proactive_research as mod

    src = inspect.getsource(mod)
    assert "datetime.now" not in src
    assert "time.time" not in src
    assert "requests" not in src and "urlopen" not in src


def test_serialization_round_trip() -> None:
    spec = _spec()
    assert ProactiveResearchJobSpec.model_validate_json(spec.model_dump_json()) == spec
    st = _state(last_success_utc=datetime(2026, 10, 28, 12, 0, 0, tzinfo=UTC))
    assert ProactiveResearchJobState.model_validate_json(st.model_dump_json()) == st
