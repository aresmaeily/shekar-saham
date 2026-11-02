"""AI-MA runtime E2E integration test — bounded-parallel orchestration (WP-4/T3).

INTEGRATION scope (composes existing public APIs in-process; nothing new is
wired, nothing existing is modified):

    MultiAgentRuntime                (app.services.multi_agent_runtime)
      → execution_waves / OrchestrationPlan / BranchResult / TraceLog
                                        (app.domain.multi_agent)
      → classify_step_failure / FAILURE_RUN_CONTAINMENT
                                        (app.domain.multi_agent_failure_model)
      → deterministic_synthesis        (app.services.multi_agent_runtime)
      → RunContext / ArtifactRef       (app.domain.run_governance)

Asserted end-to-end (synthetic/offline only; no network, no LLM, no
production mutation, no self-escalation):
- bounded-parallel wave execution is deterministic: completion order never
  leaks into recorded results or trace order (event-choreographed executors
  force the REVERSE completion order of the plan order);
- per-step timeout cancels the specialist (CancelledError delivered) and
  DISCARDS the late result — including the straggler path where an executor
  returns after its injected-clock deadline;
- failure isolation: a LOAD-BEARING failure (a step another step depends on)
  terminates the run; an independent branch failure is contained;
- deterministic_synthesis refuses mixed run ids and pins authority to
  DETERMINISTIC_ONLY;
- the closed nine-kind failure-model taxonomy, driven AT the runtime
  boundary, lands exactly on the documented per-kind run containment
  (FAILURE_RUN_CONTAINMENT conjoined with the dependency-graph decision).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.domain.multi_agent import (
    CapabilityRegistry,
    OrchestrationPlan,
    OrchestrationStep,
    SpecialistContract,
)
from app.domain.multi_agent_failure_model import FAILURE_RUN_CONTAINMENT, NINE_FAILURE_KINDS
from app.domain.run_governance import ArtifactRef, RunContext
from app.services.multi_agent_runtime import (
    MultiAgentRuntime,
    SpecialistExecutorRegistry,
    SpecialistOutcome,
    deterministic_synthesis,
)

UTC = timezone.utc
T0 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)
RUN = "run-ai-ma-e2e"
ART = ArtifactRef(artifact_id="art-1", kind="analysis", ref="artifact://art-1")


def _cap_for(specialist_id: str) -> str:
    return "cap_" + specialist_id.replace("-", "_")


def contract(
    specialist_id: str = "spec-a",
    capability: str | None = None,
    **over: object,
) -> SpecialistContract:
    base = dict(
        specialist_id=specialist_id,
        purpose="Bounded synthetic specialist for runtime integration tests.",
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


def step(
    step_id: str,
    depends_on: tuple[str, ...] = (),
    specialist_id: str | None = None,
    **over: object,
) -> OrchestrationStep:
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


def plan(steps: tuple[OrchestrationStep, ...], max_parallel: int = 4) -> OrchestrationPlan:
    return OrchestrationPlan(
        plan_id="plan-e2e",
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


def registry(
    contracts: tuple[SpecialistContract, ...], executors: dict
) -> SpecialistExecutorRegistry:
    caps = CapabilityRegistry()
    for c in contracts:
        caps = caps.with_specialist(c)
    return SpecialistExecutorRegistry(caps, executors)


class SteppedClock:
    """Deterministic injected clock with explicit advancement."""

    def __init__(self, start: float = 100.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# ---------------------------------------------------------------------------
# Completion order never leaks into recorded results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completion_order_never_leaks_into_results_or_trace() -> None:
    """Wave s1,s2,s3 completes in the order s2→s3→s1 (event-choreographed);
    results and trace MUST be recorded in plan/step order."""
    ev_b = asyncio.Event()  # set when s2 completed
    ev_c = asyncio.Event()  # set when s3 completed
    completion_order: list[str] = []

    async def make(step_id: str, wait: asyncio.Event | None, signal: asyncio.Event | None):
        class _Exec:
            async def execute(self, step, payload, deadline):
                if wait is not None:
                    await wait.wait()
                outcome = SpecialistOutcome(
                    ok=True,
                    artifact=ArtifactRef(
                        artifact_id=f"art-{step_id}", kind="analysis", ref=f"artifact://{step_id}"
                    ),
                    summary=f"done {step_id}",
                )
                completion_order.append(step_id)
                if signal is not None:
                    signal.set()
                return outcome

        return _Exec()

    executors = {
        "spec-s1": await make("s1", ev_c, None),
        "spec-s2": await make("s2", None, ev_b),
        "spec-s3": await make("s3", ev_b, ev_c),
    }
    contracts = tuple(contract(f"spec-{sid}") for sid in ("s1", "s2", "s3"))
    reg = registry(contracts, executors)
    p = plan((step("s1"), step("s2"), step("s3")), max_parallel=4)

    result = await MultiAgentRuntime().execute_plan(p, reg, run_context())

    # The executors actually completed in NON-plan order.
    assert completion_order == ["s2", "s3", "s1"]
    # …but the recorded results follow plan order exactly.
    assert [r.step_id for r in result.results] == ["s1", "s2", "s3"]
    assert all(r.status == "SUCCEEDED" for r in result.results)
    # Trace: dispatches in step order, then outcomes in step order.
    kinds = [(e.step_id, e.kind) for e in result.trace.events]
    assert kinds == [
        (None, "PLAN_CREATED"),
        ("s1", "STEP_DISPATCHED"),
        ("s2", "STEP_DISPATCHED"),
        ("s3", "STEP_DISPATCHED"),
        ("s1", "STEP_SUCCEEDED"),
        ("s2", "STEP_SUCCEEDED"),
        ("s3", "STEP_SUCCEEDED"),
    ]
    assert result.waves_executed == 1 and result.waves_total == 1
    assert result.steps_scheduled == ("s1", "s2", "s3")
    assert result.steps_unscheduled == ()
    assert not result.terminated


# ---------------------------------------------------------------------------
# Per-step timeout: cancel + discard late results (both paths)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_cancels_hung_executor_and_discards_late_result() -> None:
    cancelled = {"flag": False}

    class _Hung:
        async def execute(self, step, payload, deadline):
            try:
                await asyncio.Event().wait()  # never set within the deadline
            except asyncio.CancelledError:
                cancelled["flag"] = True
                raise
            return SpecialistOutcome(ok=True, artifact=ART, summary="late")  # pragma: no cover

    reg = registry(
        (contract("spec-h", timeout_seconds=1),), {"spec-h": _Hung()}
    )
    result = await MultiAgentRuntime().execute_plan(
        plan((step("h", specialist_id="spec-h"),), max_parallel=1), reg, run_context()
    )
    assert cancelled["flag"] is True  # the hang was actually cancelled
    assert not result.terminated  # TIMEOUT containment: continue other branches
    (branch,) = result.results
    assert branch.status == "FAILED"
    assert branch.failure_code is not None
    assert "TIMEOUT" in branch.failure_code
    assert "deadline_exceeded" in branch.failure_code
    assert "late result discarded" in branch.failure_code


@pytest.mark.asyncio
async def test_straggler_result_returned_after_deadline_is_discarded() -> None:
    """An executor that RETURNS after its injected-clock deadline: the late
    ok outcome is discarded and recorded as a cancelled-at-deadline timeout —
    it never leaks into results."""
    clock = SteppedClock(start=100.0)

    class _Straggler:
        async def execute(self, step, payload, deadline):
            clock.advance(10.0)  # blow past the deadline before returning
            return SpecialistOutcome(ok=True, artifact=ART, summary="straggler-ok")

    reg = registry(
        (contract("spec-str", timeout_seconds=5),), {"spec-str": _Straggler()}
    )
    runtime = MultiAgentRuntime(clock=clock, now_utc=lambda: T0)
    result = await runtime.execute_plan(
        plan((step("str", specialist_id="spec-str"),), max_parallel=1), reg, run_context()
    )
    (branch,) = result.results
    assert branch.status == "FAILED"
    assert branch.failure_code is not None
    assert "TIMEOUT" in branch.failure_code
    assert "straggler_discarded" in branch.failure_code
    assert "late result discarded" in branch.failure_code
    # The late SUCCEEDED payload never surfaced anywhere.
    assert all(r.status != "SUCCEEDED" for r in result.results)
    assert all("straggler-ok" not in (e.detail or "") for e in result.trace.events)


# ---------------------------------------------------------------------------
# Failure isolation: load-bearing terminates, independent is contained
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_bearing_failure_terminates_the_run() -> None:
    """s2 depends on s1; s1 fails → TERMINATE_RUN, s2 never dispatched."""

    class _Fails:
        async def execute(self, step, payload, deadline):
            raise RuntimeError("provider exploded")

    class _Never:
        async def execute(self, step, payload, deadline):  # pragma: no cover
            raise AssertionError("dependent step must not be dispatched")

    reg = registry(
        (contract("spec-s1"), contract("spec-s2")),
        {"spec-s1": _Fails(), "spec-s2": _Never()},
    )
    result = await MultiAgentRuntime().execute_plan(
        plan((step("s1"), step("s2", depends_on=("s1",))), max_parallel=2),
        reg,
        run_context(),
    )
    assert result.terminated is True
    assert result.termination_reason == "step_failed:s1:PROVIDER_ERROR"
    assert result.waves_executed == 1
    assert [r.step_id for r in result.results] == ["s1"]
    assert result.steps_unscheduled == ("s2",)
    dispatched = [e.step_id for e in result.trace.events if e.kind == "STEP_DISPATCHED"]
    assert dispatched == ["s1"]
    terminated_events = [e for e in result.trace.events if e.kind == "RUN_TERMINATED"]
    assert len(terminated_events) == 1
    # Nothing swallowed: the failure stays a visible frozen record.
    (s1,) = result.results
    assert s1.status == "FAILED" and "PROVIDER_ERROR" in (s1.failure_code or "")


@pytest.mark.asyncio
async def test_independent_branch_failure_is_contained() -> None:
    """No dependency between s1 (fails) and s2 (succeeds): the run continues,
    both results are recorded, and the failure stays visible."""

    class _Fails:
        async def execute(self, step, payload, deadline):
            raise RuntimeError("boom")

    class _Ok:
        async def execute(self, step, payload, deadline):
            return SpecialistOutcome(ok=True, artifact=ART, summary="fine")

    reg = registry(
        (contract("spec-s1"), contract("spec-s2")),
        {"spec-s1": _Fails(), "spec-s2": _Ok()},
    )
    result = await MultiAgentRuntime().execute_plan(
        plan((step("s1"), step("s2")), max_parallel=2), reg, run_context()
    )
    assert result.terminated is False
    assert result.termination_reason is None
    assert [r.step_id for r in result.results] == ["s1", "s2"]
    by_id = {r.step_id: r for r in result.results}
    assert by_id["s1"].status == "FAILED" and "PROVIDER_ERROR" in (by_id["s1"].failure_code or "")
    assert by_id["s2"].status == "SUCCEEDED"


# ---------------------------------------------------------------------------
# Deterministic synthesis: authority stays DETERMINISTIC_ONLY, mixed runs refused
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesis_pinned_authority_and_mixed_run_refusal() -> None:
    class _Ok:
        async def execute(self, step, payload, deadline):
            return SpecialistOutcome(ok=True, artifact=ART, summary="artifact-first")

    reg = registry((contract("spec-s1"),), {"spec-s1": _Ok()})
    result = await MultiAgentRuntime().execute_plan(
        plan((step("s1"),), max_parallel=1), reg, run_context()
    )
    synthesis = deterministic_synthesis(result.results)
    assert synthesis.authority == "DETERMINISTIC_ONLY"
    assert synthesis.run_id == RUN
    assert len(synthesis.sources) == 1
    assert synthesis.refused == ()

    # Mixed run ids: EVERY result is refused, nothing is blended.
    other_run = result.results[0].model_copy(update={"run_id": "run-other", "branch_id": "b2"})
    mixed = deterministic_synthesis([result.results[0], other_run])
    assert mixed.authority == "DETERMINISTIC_ONLY"
    assert mixed.sources == ()
    assert mixed.run_id is None
    assert {r.reason for r in mixed.refused} == {"mixed_run_ids"}
    assert {r.branch_id for r in mixed.refused} == {"run-ai-ma-e2e:s1:a1", "b2"}

    # Non-succeeded and summary-only results are visibly refused.
    failed_branch = result.results[0].model_copy(
        update={
            "status": "FAILED",
            "failure_code": "x",
            "artifact": None,
            "summary": "",
        }
    )
    assert [r.reason for r in deterministic_synthesis([failed_branch]).refused] == [
        "non_succeeded_status"
    ]


# ---------------------------------------------------------------------------
# Nine-kind failure taxonomy, driven AT the runtime boundary
# ---------------------------------------------------------------------------


def _kind_driver(kind: str):
    """Return (executors, contracts, steps, clock) producing ``kind`` at the
    runtime boundary, as documented in multi_agent_failure_model."""

    class _Raising:
        def __init__(self, exc: BaseException):
            self._exc = exc

        async def execute(self, step, payload, deadline):
            raise self._exc

    class _Declaring:
        def __init__(self, failure_kind: str):
            self._kind = failure_kind

        async def execute(self, step, payload, deadline):
            return SpecialistOutcome(
                ok=False, failure_kind=self._kind, failure_code=f"declared:{self._kind}"
            )

    class _Malformed:
        async def execute(self, step, payload, deadline):
            return "not-a-SpecialistOutcome"  # executor contract violation

    class _NoPayload:
        async def execute(self, step, payload, deadline):
            return SpecialistOutcome(ok=True)  # no artifact, no summary

    class _Straggler:
        def __init__(self, clock: SteppedClock):
            self._clock = clock

        async def execute(self, step, payload, deadline):
            self._clock.advance(10.0)
            return SpecialistOutcome(ok=True, artifact=ART, summary="late")

    if kind == "PROVIDER_ERROR":
        return {"spec-x": _Raising(RuntimeError("provider down"))}, (contract("spec-x"),), None
    if kind == "MALFORMED_OUTPUT":
        return {"spec-x": _Malformed()}, (contract("spec-x"),), None
    if kind == "MISSING_EVIDENCE":
        return {"spec-x": _NoPayload()}, (contract("spec-x"),), None
    if kind == "DATA_TRUST_LOW":
        return {"spec-x": _Declaring("DATA_TRUST_LOW")}, (contract("spec-x"),), None
    if kind == "TIMEOUT":
        clock = SteppedClock(start=100.0)
        runtime_clock = clock
        return (
            {"spec-x": _Straggler(clock)},
            (contract("spec-x", timeout_seconds=5),),
            runtime_clock,
        )
    if kind == "BUDGET_EXHAUSTED":
        # One specialist, max_invocations_per_run=1; x2 runs in a LATER wave
        # (depends on x1, which succeeds) so the ceiling bites on the second
        # wave's dispatch — the budget is charged at dispatch time per chunk.
        return (
            {"spec-dup": _OkExecutor()},
            (contract("spec-dup", max_invocations_per_run=1),),
            None,
        )
    if kind == "POLICY_VIOLATION":
        return {"spec-x": _Raising(ValueError("contract breach"))}, (contract("spec-x"),), None
    if kind == "DUPLICATE_OPERATION":
        return {"spec-x": _Declaring("DUPLICATE_OPERATION")}, (contract("spec-x"),), None
    if kind == "UNAVAILABLE_SPECIALIST":
        # Contract registered but NO executor: unavailable at dispatch.
        return {}, (contract("spec-x"),), None
    raise AssertionError(f"unhandled kind {kind}")  # pragma: no cover


class _OkExecutor:
    async def execute(self, step, payload, deadline):
        return SpecialistOutcome(ok=True, artifact=ART, summary="first attempt wins")


def _steps_for(kind: str) -> tuple[OrchestrationStep, ...]:
    if kind == "BUDGET_EXHAUSTED":
        return (
            step("x1", specialist_id="spec-dup"),
            step("x2", depends_on=("x1",), specialist_id="spec-dup"),
        )
    return (step("x", specialist_id="spec-x"),)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", NINE_FAILURE_KINDS)
async def test_nine_kind_taxonomy_containment_at_runtime_boundary(kind: str) -> None:
    """Each of the nine kinds is produced by a real executor/dispatch path and
    lands on its documented containment: FAILURE_RUN_CONTAINMENT[kind]
    conjoined with the dependency-graph decision (no dependents here, so the
    kind decision decides). The failure stays a visible frozen record."""
    executors, contracts, clock = _kind_driver(kind)
    reg = registry(contracts, executors)
    runtime = (
        MultiAgentRuntime(clock=clock, now_utc=lambda: T0)
        if clock is not None
        else MultiAgentRuntime(now_utc=lambda: T0)
    )
    result = await runtime.execute_plan(
        plan(_steps_for(kind), max_parallel=2), reg, run_context()
    )

    expected_terminate = FAILURE_RUN_CONTAINMENT[kind] == "TERMINATE_RUN"
    assert result.terminated is expected_terminate, kind
    if expected_terminate:
        assert result.termination_reason is not None
        assert result.termination_reason.startswith("step_failed:")
        assert kind in result.termination_reason

    failed = [r for r in result.results if r.status == "FAILED"]
    assert failed, kind
    assert all(kind in (r.failure_code or "") for r in failed), kind
    step_failed = [e for e in result.trace.events if e.kind == "STEP_FAILED"]
    assert step_failed, kind
    # Nothing swallowed: every failing step has a visible trace record.
    assert {e.step_id for e in step_failed} == {r.step_id for r in failed}
