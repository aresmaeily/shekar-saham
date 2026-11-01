"""Multi-agent runtime tests (additive AI-MA execution layer).

Covers the thin central orchestrator over the EXISTING contract layer
(app/domain/multi_agent.py — unchanged): bounded-parallel wave execution,
step-order result recording (completion order never leaks), artifact-first
dependency payloads, per-step timeout with late-result discard, failure
classification/containment via the additive failure model, budget ceilings,
deterministic re-runs, clean outer cancellation, and the pure LLM-free
deterministic synthesis combiner (authority DETERMINISTIC_ONLY).

All executors are synthetic/offline: no network, no LLM, no production
mutation, no settings access. AI-2 restrictions untouched (AI2_ENABLED=0,
verified=False, SYNTHETIC_OR_PAPER).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from itertools import count

import pytest
from pydantic import ValidationError

from app.domain.multi_agent import (
    MAX_PARALLEL_BRANCHES,
    CapabilityRegistry,
    OrchestrationPlan,
    OrchestrationStep,
    SpecialistContract,
    TraceKind,
)
from app.domain.multi_agent_failure_model import FAILURE_RUN_CONTAINMENT
from app.domain.run_governance import ArtifactRef, RunContext
from app.services.multi_agent_runtime import (
    DeterministicSynthesis,
    MultiAgentRuntime,
    SpecialistExecutorRegistry,
    SpecialistOutcome,
    StepPayload,
    SyntheticSpecialistExecutor,
    deterministic_synthesis,
)

UTC = timezone.utc
T0 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)
RUN = "run-mar-1"
ART1 = ArtifactRef(artifact_id="a1", kind="analysis", ref="artifact://a1")
ART2 = ArtifactRef(artifact_id="a2", kind="analysis", ref="artifact://a2")

CAP = "hypothesis_draft"


def _cap_for(specialist_id: str) -> str:
    """CapabilityRegistry requires distinct capabilities per specialist.

    Capability pattern is ^[a-z][a-z0-9_]*$ — map hyphens to underscores."""
    return "cap_" + specialist_id.replace("-", "_")


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def contract(specialist_id: str = "spec-s1", capability: str | None = None, **over: object) -> SpecialistContract:
    base = dict(
        specialist_id=specialist_id,
        purpose="Bounded synthetic specialist for runtime tests.",
        capability=capability or _cap_for(specialist_id),
        allowed_tools=("controlled_context_reader",),
        input_schema_ref="schema://ai-ma/hypothesis-in",
        output_schema_ref="schema://ai-ma/hypothesis-out",
        authority_boundary="advisory only; no financial truth, no production mutation",
        max_invocations_per_run=2,
        timeout_seconds=120,
        trace_prefix="rt",
        failure_behavior="FAIL_CLOSED",
        measurable_benefit_ref="evidence://admission/runtime-benefit",
        coordination_cost_note="single bounded delegation per run",
    )
    base.update(over)
    return SpecialistContract(**base)  # type: ignore[arg-type]


def step(step_id: str, depends_on: tuple[str, ...] = (), specialist_id: str | None = None, **over: object) -> OrchestrationStep:
    sid = specialist_id or f"spec-{step_id}"
    base = dict(
        step_id=step_id,
        specialist_id=sid,
        capability=_cap_for(sid),
        produces=f"artifact://{RUN}/{step_id}",
        depends_on=depends_on,
    )
    base.update(over)
    return OrchestrationStep(**base)  # type: ignore[arg-type]


def plan(steps: tuple[OrchestrationStep, ...], max_parallel: int = 2) -> OrchestrationPlan:
    return OrchestrationPlan(
        plan_id="plan-rt-1",
        run_id=RUN,
        steps=steps,
        max_parallel=max_parallel,
        policy_version="gov-1",
    )


def run_context() -> RunContext:
    return RunContext(
        run_id=RUN,
        run_kind="AI_MA_ORCHESTRATION",
        policy_version="gov-1",
        created_at_utc=T0,
    )


def ok_outcome(artifact: ArtifactRef | None = ART1, summary: str = "done") -> SpecialistOutcome:
    return SpecialistOutcome(ok=True, artifact=artifact, summary=summary)


def registry(contracts: tuple[SpecialistContract, ...], executors: dict) -> SpecialistExecutorRegistry:
    caps = CapabilityRegistry()
    for c in contracts:
        caps = caps.with_specialist(c)
    return SpecialistExecutorRegistry(caps, executors)


def run(plan_, registry_) -> object:
    return asyncio.run(MultiAgentRuntime().execute_plan(plan_, registry_, run_context()))


def by_step(result, step_id: str):
    return next(r for r in result.results if r.step_id == step_id)


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_step_success_end_to_end() -> None:
    reg = registry((contract(),), {"spec-s1": SyntheticSpecialistExecutor({"s1": ok_outcome()})})
    result = await MultiAgentRuntime().execute_plan(plan((step("s1"),)), reg, run_context())
    assert result.plan_id == "plan-rt-1"
    assert result.run_id == RUN
    assert not result.terminated
    assert result.termination_reason is None
    assert result.waves_executed == 1 and result.waves_total == 1
    assert result.steps_scheduled == ("s1",)
    assert result.steps_unscheduled == ()
    branch = by_step(result, "s1")
    assert branch.status == "SUCCEEDED"
    assert branch.addressed_to == f"orchestrator:{RUN}"
    assert branch.artifact == ART1


@pytest.mark.asyncio
async def test_results_and_trace_recorded_in_step_order_not_completion_order() -> None:
    """s2 completes first (no sleep), s1 lags — results/trace stay in step order."""

    class LaggyExecutor(SyntheticSpecialistExecutor):
        async def execute(self, step_obj, payload, deadline):  # noqa: ANN001
            if step_obj.step_id == "s1":
                await asyncio.sleep(0.03)
            return await super().execute(step_obj, payload, deadline)

    reg = registry(
        (contract("spec-s1"), contract("spec-s2")),
        {"spec-s1": LaggyExecutor({"s1": ok_outcome(ART1)}), "spec-s2": SyntheticSpecialistExecutor({"s2": ok_outcome(ART2)})},
    )
    result = await MultiAgentRuntime().execute_plan(plan((step("s1"), step("s2"))), reg, run_context())
    assert [r.step_id for r in result.results] == ["s1", "s2"]
    succeeded = [e for e in result.trace.events if e.kind == "STEP_SUCCEEDED"]
    assert [e.step_id for e in succeeded] == ["s1", "s2"]


@pytest.mark.asyncio
async def test_dependency_payload_is_artifact_first() -> None:
    captured: dict[str, StepPayload] = {}

    class CapturingExecutor(SyntheticSpecialistExecutor):
        async def execute(self, step_obj, payload, deadline):  # noqa: ANN001
            captured[step_obj.step_id] = payload
            return await super().execute(step_obj, payload, deadline)

    reg = registry(
        (contract("spec-s1"), contract("spec-s2")),
        {"spec-s1": SyntheticSpecialistExecutor({"s1": ok_outcome(ART1)}), "spec-s2": CapturingExecutor({"s2": ok_outcome(ART2)})},
    )
    result = await MultiAgentRuntime().execute_plan(plan((step("s1"), step("s2", depends_on=("s1",)))), reg, run_context())
    assert by_step(result, "s2").status == "SUCCEEDED"
    payload = captured["s2"]
    assert payload.depends_on == ("s1",)
    assert len(payload.consumed_results) == 1
    consumed = payload.consumed_results[0]
    assert consumed.step_id == "s1" and consumed.artifact == ART1
    # Artifact-first: the consumed dependency travels as a BranchResult with an
    # ArtifactRef, not as an inline blob.
    assert consumed.artifact.ref == "artifact://a1"


@pytest.mark.asyncio
async def test_two_level_depth_plan_executes_in_two_waves() -> None:
    reg = registry(
        (contract("spec-s1"), contract("spec-s2"), contract("spec-s3")),
        {
            "spec-s1": SyntheticSpecialistExecutor({"s1": ok_outcome(ART1)}),
            "spec-s2": SyntheticSpecialistExecutor({"s2": ok_outcome(ART2)}),
            "spec-s3": SyntheticSpecialistExecutor({"s3": ok_outcome(ART1)}),
        },
    )
    result = await MultiAgentRuntime().execute_plan(
        plan((step("s1"), step("s2"), step("s3", depends_on=("s1", "s2")))), reg, run_context()
    )
    assert result.waves_total == 2 and result.waves_executed == 2
    assert not result.terminated
    assert [r.step_id for r in result.results] == ["s1", "s2", "s3"]


# ---------------------------------------------------------------------------
# Failure paths — classification + containment (compose the failure model)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_executor_fails_step_as_unavailable_specialist_and_continues() -> None:
    # Contract registered, executor missing -> step fails UNAVAILABLE_SPECIALIST.
    # That kind is CONTINUE_OTHER_BRANCHES, so an independent sibling succeeds.
    reg = registry(
        (contract("spec-s1"), contract("spec-s2")),
        {"spec-s2": SyntheticSpecialistExecutor({"s2": ok_outcome(ART2)})},
    )
    result = await MultiAgentRuntime().execute_plan(plan((step("s1"), step("s2"))), reg, run_context())
    failed = by_step(result, "s1")
    assert failed.status == "FAILED"
    assert failed.failure_code is not None and failed.failure_code.startswith("UNAVAILABLE_SPECIALIST")
    assert by_step(result, "s2").status == "SUCCEEDED"
    assert not result.terminated


@pytest.mark.asyncio
async def test_unregistered_specialist_refused() -> None:
    # Step references a specialist absent from the CapabilityRegistry entirely.
    reg = registry((contract("spec-other"),), {})
    result = await MultiAgentRuntime().execute_plan(plan((step("s1", specialist_id="spec-ghost"),)), reg, run_context())
    failed = by_step(result, "s1")
    assert failed.status == "FAILED"
    assert "UNAVAILABLE_SPECIALIST" in (failed.failure_code or "")


@pytest.mark.asyncio
async def test_specialist_budget_exhaustion_terminates_run() -> None:
    # One specialist, max_invocations_per_run=1. s2 runs in a LATER wave
    # (depends on s1): within one chunk the budget is charged at dispatch
    # time, so the ceiling bites on the second wave's dispatch.
    c = contract("spec-solo", max_invocations_per_run=1)
    reg = registry((c,), {"spec-solo": SyntheticSpecialistExecutor({}, default=ok_outcome(ART1))})
    result = await MultiAgentRuntime().execute_plan(
        plan((step("s1", specialist_id="spec-solo"), step("s2", depends_on=("s1",), specialist_id="spec-solo"))), reg, run_context()
    )
    assert by_step(result, "s1").status == "SUCCEEDED"
    exhausted = by_step(result, "s2")
    assert exhausted.status == "FAILED"
    assert "BUDGET_EXHAUSTED" in (exhausted.failure_code or "")
    assert result.terminated
    assert result.termination_reason is not None
    assert result.termination_reason.startswith("step_failed:s2:BUDGET_EXHAUSTED")


@pytest.mark.asyncio
async def test_step_timeout_discards_late_result_and_continues() -> None:
    class HangingExecutor(SyntheticSpecialistExecutor):
        async def execute(self, step_obj, payload, deadline):  # noqa: ANN001
            if step_obj.step_id == "s1":
                await asyncio.sleep(30)  # far beyond the 1s contract timeout
            return await super().execute(step_obj, payload, deadline)

    reg = registry(
        (contract("spec-s1", timeout_seconds=1), contract("spec-s2")),
        {"spec-s1": HangingExecutor({"s1": ok_outcome(ART1)}), "spec-s2": SyntheticSpecialistExecutor({"s2": ok_outcome(ART2)})},
    )
    result = await MultiAgentRuntime().execute_plan(plan((step("s1"), step("s2"))), reg, run_context())
    timed_out = by_step(result, "s1")
    assert timed_out.status == "FAILED"
    assert timed_out.failure_code is not None and timed_out.failure_code.startswith("TIMEOUT")
    assert "late result discarded" in timed_out.failure_code
    # TIMEOUT containment is CONTINUE_OTHER_BRANCHES — the sibling survived.
    assert by_step(result, "s2").status == "SUCCEEDED"
    assert not result.terminated


@pytest.mark.asyncio
async def test_executor_exception_classified_deterministically() -> None:
    class ThrowingExecutor(SyntheticSpecialistExecutor):
        async def execute(self, step_obj, payload, deadline):  # noqa: ANN001
            raise RuntimeError("synthetic provider outage")

    reg = registry((contract("spec-s1"),), {"spec-s1": ThrowingExecutor({})})
    result = await MultiAgentRuntime().execute_plan(plan((step("s1"),)), reg, run_context())
    failed = by_step(result, "s1")
    assert failed.status == "FAILED"
    # RuntimeError is not a contract-family exception -> PROVIDER_ERROR.
    assert failed.failure_code is not None
    assert failed.failure_code.startswith("PROVIDER_ERROR")
    assert "RuntimeError" in failed.failure_code


@pytest.mark.asyncio
async def test_load_bearing_failure_terminates_and_unscheduled_reported() -> None:
    # s3 depends on s1; s1 fails (PROVIDER_ERROR contains, but the GRAPH makes
    # s1 load-bearing for s3 via isolate_failure) — s3 must end unscheduled.
    reg = registry(
        (contract("spec-s1"), contract("spec-s2"), contract("spec-s3")),
        {
            "spec-s1": SyntheticSpecialistExecutor({"s1": SpecialistOutcome(ok=False, failure_code="PROVIDER_ERROR:down")}),
            "spec-s2": SyntheticSpecialistExecutor({"s2": ok_outcome(ART2)}),
            "spec-s3": SyntheticSpecialistExecutor({"s3": ok_outcome(ART1)}),
        },
    )
    result = await MultiAgentRuntime().execute_plan(
        plan((step("s1"), step("s2"), step("s3", depends_on=("s1",)))), reg, run_context()
    )
    assert by_step(result, "s1").status == "FAILED"
    assert by_step(result, "s2").status == "SUCCEEDED"
    assert "s3" in result.steps_unscheduled
    assert result.terminated
    assert result.termination_reason is not None
    assert result.termination_reason.startswith("step_failed:s1:")


@pytest.mark.asyncio
async def test_deadline_already_passed_short_circuits_before_execution() -> None:
    # Injected clock advances faster than the timeout: remaining <= 0 at
    # dispatch -> deadline_passed outcome, executor never invoked.
    invoked: list[str] = []

    class NotInvokedExecutor(SyntheticSpecialistExecutor):
        async def execute(self, step_obj, payload, deadline):  # noqa: ANN001
            invoked.append(step_obj.step_id)
            return await super().execute(step_obj, payload, deadline)

    ticks = count(start=0, step=10_000)  # each clock() call jumps 10 000s
    reg = registry(
        (contract("spec-s1", timeout_seconds=5),),
        {"spec-s1": NotInvokedExecutor({"s1": ok_outcome(ART1)})},
    )
    runtime = MultiAgentRuntime(clock=lambda: float(next(ticks)))
    result = await runtime.execute_plan(plan((step("s1"),)), reg, run_context())
    assert invoked == []  # never executed
    failed = by_step(result, "s1")
    assert failed.status == "FAILED"
    assert failed.failure_code is not None and "deadline_passed" in failed.failure_code


# ---------------------------------------------------------------------------
# Determinism, ceilings, trace fabric, cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_plan_and_registry_give_identical_results_and_trace() -> None:
    reg = registry(
        (contract("spec-s1"), contract("spec-s2")),
        {"spec-s1": SyntheticSpecialistExecutor({"s1": ok_outcome(ART1)}), "spec-s2": SyntheticSpecialistExecutor({"s2": ok_outcome(ART2)})},
    )
    runtime = MultiAgentRuntime(now_utc=lambda: T0)  # fixed clock → identical records
    r1 = await runtime.execute_plan(plan((step("s1"), step("s2"))), reg, run_context())
    r2 = await runtime.execute_plan(plan((step("s1"), step("s2"))), reg, run_context())
    assert r1.results == r2.results
    ev1 = [(e.kind, e.step_id, e.detail) for e in r1.trace.events]
    ev2 = [(e.kind, e.step_id, e.detail) for e in r2.trace.events]
    assert ev1 == ev2


@pytest.mark.asyncio
async def test_trace_fabric_records_plan_dispatch_success_kinds() -> None:
    sink: list = []
    reg = registry((contract(),), {"spec-s1": SyntheticSpecialistExecutor({"s1": ok_outcome()})})
    await MultiAgentRuntime().execute_plan(plan((step("s1"),)), reg, run_context(), trace_sink=sink)
    kinds = [e.kind for e in sink]
    assert kinds[0] == "PLAN_CREATED"
    assert "STEP_DISPATCHED" in kinds and "STEP_SUCCEEDED" in kinds
    assert len(sink) >= 3
    # Every event is bound to the same run id — one fabric per run.
    assert {e.run_id for e in sink} == {RUN}


@pytest.mark.asyncio
async def test_parallel_ceiling_never_exceeds_bounded_maximum() -> None:
    # 4 independent steps; plan asks max_parallel=4; runtime ceiling clamps to
    # MAX_PARALLEL_BRANCHES. All four still complete (bounded, not dropped).
    contracts = tuple(contract(f"spec-s{i}") for i in range(1, 5))
    executors = {f"spec-s{i}": SyntheticSpecialistExecutor({f"s{i}": ok_outcome(ART1)}) for i in range(1, 5)}
    reg = registry(contracts, executors)
    runtime = MultiAgentRuntime(max_parallel_ceiling=99)  # must clamp
    result = await runtime.execute_plan(
        plan(tuple(step(f"s{i}") for i in range(1, 5)), max_parallel=MAX_PARALLEL_BRANCHES), reg, run_context()
    )
    assert len(result.results) == 4
    assert all(r.status == "SUCCEEDED" for r in result.results)
    assert runtime._ceiling <= MAX_PARALLEL_BRANCHES  # structural clamp held


@pytest.mark.asyncio
async def test_plan_run_context_mismatch_fails_fast() -> None:
    reg = registry((contract(),), {"spec-s1": SyntheticSpecialistExecutor({"s1": ok_outcome()})})
    other = RunContext(
        run_id="run-other",
        run_kind="AI_MA_ORCHESTRATION",
        policy_version="gov-1",
        created_at_utc=T0,
    )
    with pytest.raises(ValueError, match="plan_run_id_mismatch"):
        await MultiAgentRuntime().execute_plan(plan((step("s1"),)), reg, other)


@pytest.mark.asyncio
async def test_outer_cancellation_propagates_without_fabricated_results() -> None:
    class SlowExecutor(SyntheticSpecialistExecutor):
        async def execute(self, step_obj, payload, deadline):  # noqa: ANN001
            await asyncio.sleep(30)
            return await super().execute(step_obj, payload, deadline)

    reg = registry((contract("spec-s1", timeout_seconds=120),), {"spec-s1": SlowExecutor({"s1": ok_outcome()})})
    task = asyncio.ensure_future(MultiAgentRuntime().execute_plan(plan((step("s1"),)), reg, run_context()))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # No result record was fabricated by the runtime for the cancelled step
    # (cancellation propagates; containment happens only for executor-level
    # failures, not outer cancellation).


# ---------------------------------------------------------------------------
# Deterministic synthesis combiner (pure, LLM-free)
# ---------------------------------------------------------------------------


def branch(branch_id: str, step_id: str, status: str = "SUCCEEDED", artifact=None, summary: str = "", summary_only: bool = False, run_id: str = RUN):
    from app.domain.multi_agent import BranchResult

    return BranchResult(
        branch_id=branch_id,
        run_id=run_id,
        step_id=step_id,
        specialist_id=f"spec-{step_id}",
        addressed_to=f"orchestrator:{run_id}",
        status=status,  # type: ignore[arg-type]
        artifact=artifact,
        summary=summary,
        summary_only=summary_only,
        failure_code=None if status == "SUCCEEDED" else "PROVIDER_ERROR:x",
        completed_at_utc=T0,
    )


def test_synthesis_merges_only_succeeded_artifact_first_branches() -> None:
    results = (
        branch("b1", "s1", artifact=ART1, summary="alpha"),
        branch("b2", "s2", artifact=ART2, summary="beta"),
        branch("b3", "s3", status="FAILED"),
        branch("b4", "s4", status="DEGRADED"),
        branch("b5", "s5", summary="summary-only", summary_only=True),  # no artifact
    )
    out = deterministic_synthesis(results)
    assert isinstance(out, DeterministicSynthesis)
    assert out.authority == "DETERMINISTIC_ONLY"
    assert [s.branch_id for s in out.sources] == ["b1", "b2"]
    refused_ids = {r.branch_id for r in out.refused}
    assert refused_ids == {"b3", "b4", "b5"}
    # Nothing silently swallowed: every refusal carries a reason.
    assert all(r.reason for r in out.refused)
    assert any(r.reason == "summary_only_without_artifact" for r in out.refused)


def test_synthesis_is_deterministic_under_input_reordering() -> None:
    results = [
        branch("b2", "s2", artifact=ART2),
        branch("b1", "s1", artifact=ART1),
        branch("b3", "s3", status="FAILED"),
    ]
    a = deterministic_synthesis(results)
    b = deterministic_synthesis(list(reversed(results)))
    assert a.sources == b.sources
    assert a.refused == b.refused


def test_synthesis_run_id_consistency_and_empty_input() -> None:
    assert deterministic_synthesis(()).sources == ()
    # Mixing run ids in one synthesis call is refused for EVERY branch —
    # a synthesis output never blends records from different runs.
    mixed = (branch("b1", "s1", artifact=ART1), branch("b2", "s2", status="FAILED", run_id="run-other"))
    out = deterministic_synthesis(mixed)
    assert out.sources == ()
    assert out.run_id is None
    assert {r.reason for r in out.refused} == {"mixed_run_ids"}
    # Uniform run id: the synthesis carries that run id.
    uniform = (branch("b1", "s1", artifact=ART1), branch("b2", "s2", artifact=ART2))
    assert deterministic_synthesis(uniform).run_id == RUN


def test_step_payload_frozen() -> None:
    payload = StepPayload(
        run_id=RUN,
        plan_id="plan-rt-1",
        step_id="s1",
        specialist_id="spec-s1",
        capability=CAP,
    )
    with pytest.raises(ValidationError):
        payload.step_id = "s2"  # type: ignore[misc]


def test_failure_containment_table_covers_all_nine_kinds() -> None:
    # The runtime relies on FAILURE_RUN_CONTAINMENT being total over the
    # taxonomy — pin it here so a new kind cannot silently miss containment.
    from app.domain.multi_agent_failure_model import NINE_FAILURE_KINDS

    assert set(FAILURE_RUN_CONTAINMENT) == set(NINE_FAILURE_KINDS)
    assert all(v in {"CONTINUE_OTHER_BRANCHES", "TERMINATE_RUN"} for v in FAILURE_RUN_CONTAINMENT.values())
    assert set(TraceKind.__args__) >= {"PLAN_CREATED", "STEP_DISPATCHED", "STEP_SUCCEEDED", "STEP_FAILED"}  # type: ignore[attr-defined]
