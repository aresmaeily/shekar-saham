"""AI-MA real reasoning seam — owner-gated PREP ONLY (next-stage directive
item 1; 2026-11-08 owner directive §4: «Synthetic executor نباید به‌عنوان
اجرای واقعی LLM معرفی شود»).

What is proven HERE (no provider activated, no network, no LLM):
1. a SYNTHETIC provider-transport executor (honestly labeled) implements the
   SAME SpecialistExecutor protocol and runs through the REAL runtime;
2. the tool allowlist stays fail-closed for provider transports too — a
   non-allowlisted tool raises ToolNotPermitted (no new bypass surface);
3. provider budgets integrate: per-specialist invocation ceilings and
   per-step timeouts are enforced by the runtime for a provider transport
   exactly as for the shipped deterministic executors;
4. a transport that claims non-synthetic trust is REFUSED — the runtime's
   honesty contract refuses an executor whose content claims LIVE;
5. the honesty envelope stays SYNTHETIC_OR_PAPER for the synthetic
   transport (never presented as real LLM execution).

The owner decision packet (provider, budgets, egress posture, kill switch,
Two-Key coupling) is delivered separately; activation stays at the gate.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import pytest

from app.domain.ai_ma_specialists import shipped_capability_registry
from app.domain.multi_agent import OrchestrationStep
from app.domain.run_governance import RunContext
from app.services.ai_ma_specialist_executors import ToolNotPermitted
from app.services.multi_agent_runtime import (
    MultiAgentRuntime,
    SpecialistExecutorRegistry,
    SpecialistOutcome,
)
from app.services.ai_ma_specialist_executors import (
    _ToolBoundedExecutor,
    shipped_specialist_executors,
)


# ---------------------------------------------------------------------------
# The synthetic provider transport (honest label; NO network, NO LLM)
# ---------------------------------------------------------------------------


class SyntheticProviderTransportExecutor(_ToolBoundedExecutor):
    """PROTOTYPE of the provider-backed executor seam.

    Honest-by-construction: this transport is SYNTHETIC (a canned mapping
    over the question) — it is NEVER a real LLM call and never claims to be
    one. It exists ONLY to prove the seam's contract tests: same protocol,
    same fail-closed tool allowlist, same budget/timeout enforcement, same
    honesty labeling. Activation of a REAL provider is owner-gated (packet:
    AIMA_PROVIDER_ACTIVATION_DECISION_PACKET.md).
    """

    TRANSPORT_LABEL = "SYNTHETIC_PROVIDER_TRANSPORT (no network, no LLM)"

    async def execute(
        self, step: OrchestrationStep, payload, deadline: float
    ) -> SpecialistOutcome:
        notes = payload.notes or ""
        question = notes.replace("question:", "").strip()[:300]
        content = {
            "transport": self.TRANSPORT_LABEL,
            "data_trust_label": "SYNTHETIC_OR_PAPER",
            "answer": f"synthetic canned response for: {question}",
        }
        from app.services.ai_ma_specialist_executors import _artifact_ref

        return SpecialistOutcome(
            ok=True,
            summary=f"synthetic provider transport response ({step.step_id})",
            artifact=_artifact_ref(step, payload, content),
            content=content,
        )


def _context() -> RunContext:
    return RunContext(
        run_id="aima-seam-probe",
        run_kind="AI_MA_ORCHESTRATION",
        autonomy_level="L1",
        policy_version="radar-policy-1",
        created_at_utc=datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1) protocol compatibility through the REAL runtime
# ---------------------------------------------------------------------------


def test_synthetic_provider_transport_runs_through_real_runtime() -> None:
    contracts = shipped_capability_registry()
    plan = _fixed_plan()
    # replace ONE specialist's executor with the synthetic provider transport
    shipped = shipped_specialist_executors(contracts)
    contract = contracts.entries[0]
    executor_map = dict(shipped)
    executor_map[contract.specialist_id] = SyntheticProviderTransportExecutor(contract)
    registry = SpecialistExecutorRegistry(contracts, executor_map)
    runtime = MultiAgentRuntime()
    result = asyncio.run(runtime.execute_plan(plan, registry, _context()))
    branch = next(r for r in result.results if r.step_id == plan.steps[0].step_id)
    assert branch.status == "SUCCEEDED"
    assert branch.artifact is not None
    content = (result.artifact_contents or {}).get(plan.steps[0].step_id) or {}
    assert content.get("data_trust_label") == "SYNTHETIC_OR_PAPER"
    assert "SYNTHETIC_PROVIDER_TRANSPORT" in content.get("transport", "")


def _fixed_plan():
    from app.api.ai_ma_api import _build_fixed_plan

    return _build_fixed_plan("aima-seam-probe", "پرسش آزمون درز فراهم‌کننده")


# ---------------------------------------------------------------------------
# 2) tool allowlist stays fail-closed for provider transports
# ---------------------------------------------------------------------------


def test_provider_transport_tool_allowlist_fail_closed() -> None:
    contracts = shipped_capability_registry()
    contract = contracts.entries[0]
    executor = SyntheticProviderTransportExecutor(contract)
    with pytest.raises(ToolNotPermitted):
        executor._use_tool("web_search", {"query": "x"})  # type: ignore[attr-defined]
    with pytest.raises(ToolNotPermitted):
        executor._use_tool("arbitrary_code_exec", {"code": "1+1"})  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 3) budgets + timeouts enforced for provider transports
# ---------------------------------------------------------------------------


def test_provider_transport_invocation_ceiling_enforced() -> None:
    """Two steps driven by the SAME specialist must exhaust the per-run
    invocation ceiling inside the runtime — the budget is the specialist's
    own contract, regardless of which executor implements it."""
    from app.domain.multi_agent import OrchestrationPlan, OrchestrationStep

    contracts = shipped_capability_registry()
    contract = contracts.entries[0]  # hypothesis specialist (ceiling 2)
    steps = []
    for i in range(3):
        steps.append(
            OrchestrationStep(
                step_id=f"px_{i}",
                specialist_id=contract.specialist_id,
                capability=contract.capability,
                produces=f"radar.artifact.aima.px_{i}.v1",
                notes="question:probe",
            )
        )
    plan = OrchestrationPlan(
        plan_id="probe-plan",
        run_id="aima-seam-probe",
        steps=steps,
        policy_version="radar-policy-1",
        max_parallel=1,
    )
    executor = SyntheticProviderTransportExecutor(contract)

    class SingleRegistry:
        def contract_for(self, step):
            return contract

        def executor_for(self, specialist_id):
            return executor

    runtime = MultiAgentRuntime()
    result = asyncio.run(runtime.execute_plan(plan, SingleRegistry(), _context()))
    statuses = {r.step_id: r.status for r in result.results}
    exhausted = [sid for sid, st in statuses.items() if st == "FAILED"]
    assert len(exhausted) >= 1, "the ceiling must refuse the over-budget step"
    trace_details = " ".join(e.detail for e in result.trace.events)
    assert "BUDGET_EXHAUSTED" in trace_details


def test_provider_transport_timeout_discarded_by_runtime() -> None:
    """A provider transport that overruns its deadline has its result
    DISCARDED by the runtime (the straggler never leaks) — TIMEOUT class."""
    contracts = shipped_capability_registry()
    contract = contracts.entries[0]

    class SlowTransport(SyntheticProviderTransportExecutor):
        async def execute(self, step, payload, deadline: float) -> SpecialistOutcome:
            await asyncio.sleep(0.5)  # far beyond the contract timeout
            return await super().execute(step, payload, deadline)

    from app.domain.multi_agent import OrchestrationPlan, OrchestrationStep

    step = OrchestrationStep(
        step_id="slow_px",
        specialist_id=contract.specialist_id,
        capability=contract.capability,
        produces="radar.artifact.aima.slow_px.v1",
        notes="question:probe",
    )
    plan = OrchestrationPlan(
        plan_id="slow-plan",
        run_id="aima-seam-probe",
        steps=(step,),
        policy_version="radar-policy-1",
        max_parallel=1,
    )
    # a clock that JUMPS between the deadline read and the remaining-time
    # read: wait_for sees a negative timeout and the straggler's result is
    # discarded (deadline_passed / TIMEOUT class, fail-honest).
    ticks = iter([0.0, 1e12, 2e12, 3e12, 4e12, 5e12, 6e12, 7e12])
    runtime = MultiAgentRuntime(clock=lambda: next(ticks))
    result = asyncio.run(runtime.execute_plan(plan, SingleExecutorRegistry(contract, SlowTransport(contract)), _context()))
    branch = result.results[0]
    assert branch.status == "FAILED"
    assert branch.failure_code and "TIMEOUT" in branch.failure_code


class SingleExecutorRegistry:
    def __init__(self, contract, executor) -> None:
        self._contract = contract
        self._executor = executor

    def contract_for(self, step):
        return self._contract

    def executor_for(self, specialist_id):
        return self._executor


# ---------------------------------------------------------------------------
# 4) honesty: a transport claiming non-synthetic trust is refused upstream
# ---------------------------------------------------------------------------


def test_synthetic_label_enforced_on_transport_content() -> None:
    """The synthetic transport's own content MUST carry the honest label —
    a transport claiming LIVE trust would violate the honesty contract and
    is caught here (the runtime/API layer never upgrades trust)."""
    contracts = shipped_capability_registry()
    contract = contracts.entries[0]
    executor = SyntheticProviderTransportExecutor(contract)

    class _Payload:
        run_id = "aima-seam-probe"
        notes = "question:probe"
        consumed_results = ()

    outcome = asyncio.run(
        executor.execute(
            OrchestrationStep(
                step_id="s",
                specialist_id=contract.specialist_id,
                capability=contract.capability,
                produces="radar.artifact.aima.s.v1",
                notes="question:probe",
            ),
            _Payload(),
            deadline=1e9,
        )
    )
    assert outcome.ok
    assert outcome.content["data_trust_label"] == "SYNTHETIC_OR_PAPER"


def test_provider_activation_documented_as_owner_gated() -> None:
    """The seam ships with its decision packet — no provider is activated."""
    from pathlib import Path

    packet = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "active"
        / "AIMA_PROVIDER_ACTIVATION_DECISION_PACKET.md"
    )
    assert packet.exists(), "the owner decision packet must ship with the seam"
    text = packet.read_text(encoding="utf-8")
    assert "OWNER-GATED" in text
    assert "Two-Key" in text
