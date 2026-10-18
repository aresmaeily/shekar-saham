"""AI-MA-C acceptance tests — multi-agent runtime contract layer.

Derived from the 2026-10-02 amendment corpus, NOT from the implementation:
02 lines 55–81 (AI-MA-1..6 + "No fixed agent count. No peer-to-peer backbone.
No autonomous spawning."), 02-product rules 1–12 + admission rules + failure
model, 03 §Orchestrator/§Specialist, D-AI-20/21/23/24.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.multi_agent import (
    BranchResult,
    CapabilityRegistry,
    MAX_PARALLEL_BRANCHES,
    OrchestrationPlan,
    OrchestrationStep,
    SpecialistContract,
    TraceEvent,
    TraceLog,
    execution_waves,
    isolate_failure,
)
from app.domain.run_governance import ArtifactRef

UTC = timezone.utc
T0 = datetime(2026, 10, 18, 12, 30, 0, tzinfo=UTC)
RUN = "run-ma-1"
ART = ArtifactRef(artifact_id="a1", kind="analysis", ref="artifact://a1")


def specialist(specialist_id: str = "spec-hypothesis", capability: str = "hypothesis_draft", **over: object) -> SpecialistContract:
    base = dict(
        specialist_id=specialist_id,
        purpose="Draft bounded research hypotheses from controlled context.",
        capability=capability,
        allowed_tools=("controlled_context_reader",),
        input_schema_ref="schema://ai-ma/hypothesis-in",
        output_schema_ref="schema://ai-ma/hypothesis-out",
        authority_boundary="advisory only; no financial truth, no production mutation",
        max_invocations_per_run=2,
        timeout_seconds=120,
        trace_prefix="hyp",
        failure_behavior="FAIL_CLOSED",
        measurable_benefit_ref="evidence://admission/hypothesis-benefit",
        coordination_cost_note="single bounded delegation per run",
    )
    base.update(over)
    return SpecialistContract(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AI-MA-2 — specialist contract (03 §Specialist; admission rules; D-AI-21)
# ---------------------------------------------------------------------------


def test_specialist_contract_minimal_valid_and_frozen() -> None:
    s = specialist()
    assert s.interaction_pattern == "AGENT_AS_TOOL"  # default per D-AI-21
    with pytest.raises(ValidationError):
        s.purpose = "mutated"  # type: ignore[misc]


def test_handoff_requires_justification() -> None:
    with pytest.raises(ValidationError, match="handoff_requires_justification"):
        specialist(interaction_pattern="HANDOFF")
    ok = specialist(interaction_pattern="HANDOFF", handoff_justification="Ownership transfer materially required: continued reasoning needs mutable working set.")
    assert ok.handoff_justification
    with pytest.raises(ValidationError, match="agent_as_tool_cannot_carry_handoff_justification"):
        specialist(handoff_justification="stray")


def test_consequential_specialist_requires_owner_change_record() -> None:
    with pytest.raises(ValidationError, match="consequential_specialist_requires_owner_change_record"):
        specialist(consequential=True)
    ok = specialist(consequential=True, owner_change_record="decision://owner/2026-10-02")
    assert ok.owner_change_record


def test_specialist_required_fields_enforced() -> None:
    with pytest.raises(ValidationError):
        specialist(allowed_tools=())
    with pytest.raises(ValidationError):
        specialist(authority_boundary="")
    with pytest.raises(ValidationError):
        specialist(capability="Hypothesis-Draft")  # pattern: lowercase only
    with pytest.raises(ValidationError):
        specialist(allowed_tools=("t1", "t1"))


# ---------------------------------------------------------------------------
# AI-MA-2 — capability registry (distinct capability; no fixed count)
# ---------------------------------------------------------------------------


def test_registry_append_idempotent_conflict_and_version() -> None:
    reg = CapabilityRegistry().with_specialist(specialist())
    assert reg.registry_version == 2
    assert reg.with_specialist(specialist()) is reg  # idempotent
    with pytest.raises(ValueError, match="specialist_registry_conflict"):
        reg.with_specialist(specialist(purpose="Different purpose."))
    assert len(reg.entries) == 1


def test_capability_must_be_distinct() -> None:
    reg = CapabilityRegistry().with_specialist(specialist())
    with pytest.raises(ValueError, match="capability_not_distinct"):
        reg.with_specialist(specialist(specialist_id="spec-2", capability="hypothesis_draft"))


def test_registry_no_fixed_count_and_resolve() -> None:
    reg = (
        CapabilityRegistry()
        .with_specialist(specialist())
        .with_specialist(specialist("spec-learn", "learning_challenge"))
        .with_specialist(specialist("spec-interp", "interpretation"))
    )
    assert len(reg.entries) == 3  # no fixed count — grew to three
    assert reg.resolve("interpretation").specialist_id == "spec-interp"
    assert reg.resolve("nonexistent") is None


# ---------------------------------------------------------------------------
# AI-MA-1 — orchestration plan (two-level depth; acyclic; bounded fan-out)
# ---------------------------------------------------------------------------


def step(step_id: str, depends_on: tuple[str, ...] = (), **over: object) -> OrchestrationStep:
    base = dict(
        step_id=step_id,
        specialist_id=f"spec-{step_id}",
        capability="hypothesis_draft",
        produces=f"artifact://{RUN}/{step_id}",
        depends_on=depends_on,
    )
    base.update(over)
    return OrchestrationStep(**base)  # type: ignore[arg-type]


def plan(steps: tuple[OrchestrationStep, ...], max_parallel: int = 2) -> OrchestrationPlan:
    return OrchestrationPlan(
        plan_id="plan-1",
        run_id=RUN,
        steps=steps,
        max_parallel=max_parallel,
        policy_version="gov-1",
    )


def test_plan_bound_to_run_and_frozen() -> None:
    p = plan((step("s1"),))
    assert p.run_id == RUN
    with pytest.raises(ValidationError):
        p.run_id = "other"  # type: ignore[misc]


def test_plan_rejects_cycles_unknown_deps_self_dep() -> None:
    with pytest.raises(ValidationError, match="plan_has_dependency_cycle"):
        plan((step("s1", ("s2",)), step("s2", ("s1",))))
    with pytest.raises(ValidationError, match="dependency_references_unknown_step"):
        plan((step("s1", ("ghost",)),))
    with pytest.raises(ValidationError, match="step_cannot_depend_on_itself"):
        step("s1", ("s1",))


def test_plan_rejects_depth_three_and_duplicate_ids() -> None:
    with pytest.raises(ValidationError, match="hierarchy_depth_exceeds_two_levels"):
        plan((step("s1", specialist_id="orchestrator:inner"),))
    with pytest.raises(ValidationError, match="step_ids_duplicates"):
        plan((step("s1"), step("s1")))


def test_plan_fan_out_ceiling_is_engineering_bounded() -> None:
    assert MAX_PARALLEL_BRANCHES == 4
    with pytest.raises(ValidationError):
        plan((step("s1"),), max_parallel=5)


# ---------------------------------------------------------------------------
# AI-MA-4 — deterministic bounded-parallel waves (D-AI-24)
# ---------------------------------------------------------------------------


def test_execution_waves_respect_dependencies() -> None:
    steps = (step("a"), step("b"), step("c", ("a", "b")), step("d", ("c",)))
    waves = execution_waves(plan(steps))
    assert waves == (("a", "b"), ("c",), ("d",))


def test_execution_waves_split_wide_levels_to_ceiling() -> None:
    steps = tuple(step(sid) for sid in ("a", "b", "c", "d", "e"))
    waves = execution_waves(plan(steps, max_parallel=2))
    assert waves == (("a", "b"), ("c", "d"), ("e",))
    wide = execution_waves(plan(tuple(step(sid) for sid in ("a", "b", "c", "d")), max_parallel=4))
    assert wide == (("a", "b", "c", "d"),)


def test_execution_waves_deterministic_and_pure() -> None:
    steps = (step("a"), step("b", ("a",)), step("c", ("a",)))
    p = plan(steps)
    assert execution_waves(p) == execution_waves(p)
    assert len(p.steps) == 3  # input unchanged


# ---------------------------------------------------------------------------
# AI-MA-5 — artifact-first exchange + no peer-to-peer (D-AI-20/23)
# ---------------------------------------------------------------------------


def branch(**over: object) -> BranchResult:
    base = dict(
        branch_id="br-1",
        run_id=RUN,
        step_id="s1",
        specialist_id="spec-s1",
        addressed_to=f"orchestrator:{RUN}",
        status="SUCCEEDED",
        artifact=ART,
        completed_at_utc=T0,
    )
    base.update(over)
    return BranchResult(**base)  # type: ignore[arg-type]


def test_branch_result_artifact_first_and_frozen() -> None:
    r = branch()
    assert r.artifact is not None
    with pytest.raises(ValidationError):
        r.status = "FAILED"  # type: ignore[misc]


def test_peer_to_peer_addressing_structurally_refused() -> None:
    with pytest.raises(ValidationError, match="peer_to_peer_addressing_refused"):
        branch(addressed_to="spec-other-branch")


def test_summary_only_requires_summary() -> None:
    ok = branch(artifact=None, summary_only=True, summary="Small structured summary under bound.")
    assert ok.summary_only
    with pytest.raises(ValidationError, match="summary_only_result_requires_summary"):
        branch(artifact=None, summary_only=True)
    with pytest.raises(ValidationError, match="artifact_first_exchange_requires_artifact"):
        branch(artifact=None)


def test_failed_branch_is_contained_and_payload_free() -> None:
    f = branch(status="FAILED", failure_code="specialist_timeout", artifact=None)
    assert f.failure_code == "specialist_timeout"
    with pytest.raises(ValidationError, match="failed_result_requires_failure_code"):
        branch(status="FAILED", artifact=None)
    with pytest.raises(ValidationError, match="failed_result_cannot_carry_payload"):
        branch(status="FAILED", failure_code="x")
    with pytest.raises(ValidationError, match="succeeded_result_cannot_carry_failure_code"):
        branch(failure_code="x")


# ---------------------------------------------------------------------------
# AI-MA-6 — one trace fabric + failure isolation
# ---------------------------------------------------------------------------


def ev(event_id: str = "e1", **over: object) -> TraceEvent:
    base = dict(
        event_id=event_id,
        run_id=RUN,
        step_id="s1",
        trace_prefix="orch",
        kind="STEP_DISPATCHED",
        at_utc=T0,
    )
    base.update(over)
    return TraceEvent(**base)  # type: ignore[arg-type]


def test_trace_log_append_idempotent_conflict_and_filter() -> None:
    log = TraceLog().append(ev())
    assert log.append(ev()) is log
    with pytest.raises(ValueError, match="trace_event_conflict"):
        log.append(ev(kind="STEP_FAILED"))
    log2 = log.append(ev("e2", run_id="run-other"))
    assert len(log2.for_run(RUN)) == 1
    assert len(log2.events) == 2


def test_trace_events_carry_specialist_prefix() -> None:
    e = ev(trace_prefix="hyp", kind="STEP_SUCCEEDED", artifact_id="a1")
    assert e.trace_prefix == "hyp" and e.artifact_id == "a1"


def test_isolate_failure_load_bearing_vs_independent() -> None:
    p = plan((step("a"), step("b", ("a",)), step("c")))
    failed_a = branch(branch_id="f1", step_id="a", status="FAILED", failure_code="boom", artifact=None)
    assert isolate_failure("a", p, (failed_a,)) == "TERMINATE_RUN"
    failed_c = branch(branch_id="f2", step_id="c", status="FAILED", failure_code="boom", artifact=None)
    assert isolate_failure("c", p, (failed_c,)) == "CONTINUE_OTHER_BRANCHES"


def test_isolate_failure_is_deterministic() -> None:
    p = plan((step("a"), step("c")))
    r = branch(branch_id="f3", step_id="c", status="FAILED", failure_code="boom", artifact=None)
    assert isolate_failure("c", p, (r,)) == isolate_failure("c", p, (r,))
