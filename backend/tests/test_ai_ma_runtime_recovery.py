"""WAVE-AB3 (2026-11-08): AI-MA runtime recovery + autonomy-gate tests.

Closes two recorded P1/P0 gaps of the runtime audit:

1. RECOVERY: FAILURE_BEHAVIOR declared PROVIDER_ERROR / MALFORMED_OUTPUT /
   TIMEOUT as RETRY_WITHIN_BUDGET, but ``execute_plan`` never retried — the
   mapping was advisory only. The runtime now performs EXACTLY ONE bounded
   immediate retry per step per run, each retry charged to the specialist's
   own invocation budget and traced as STEP_RETRY; the retried attempt's
   outcome is the recorded outcome (fail-honest).
2. AUTONOMY GATE: ``execute_plan`` never called ``assert_autonomy_permitted``
   (the check existed only at RunContext construction). The orchestration
   path now refuses any run minted above the L2 ceiling before dispatching
   anything.

All tests are offline/synthetic (injected clocks, deterministic executors).
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.multi_agent import OrchestrationPlan, OrchestrationStep
from app.domain.multi_agent_failure_model import NINE_FAILURE_KINDS
from app.domain.run_governance import RunContext
from app.services.multi_agent_runtime import (
    SpecialistExecutorRegistry,
    SpecialistOutcome,
    SyntheticSpecialistExecutor,
)


def _run_context(run_id: str = "run-recover-1", level: str = "L2") -> RunContext:
    from datetime import datetime, timezone

    return RunContext(
        run_id=run_id,
        run_kind="AI_MA_ORCHESTRATION",
        autonomy_level=level,
        policy_version="radar-policy-1",
        created_at_utc=datetime(2026, 11, 8, tzinfo=timezone.utc),
    )



def _branch_attempt(branch) -> int:
    """The attempt number is encoded in branch_id as ':a<attempt>'."""
    return int(branch.branch_id.rsplit(":a", 1)[1])

def _plan(run_id: str, steps_spec) -> OrchestrationPlan:
    steps = tuple(
        OrchestrationStep(
            step_id=step_id,
            specialist_id=specialist,
            capability=capability,
            produces=f"radar.artifact.{step_id}.v1",
            depends_on=depends,
            consumes=consumes,
        )
        for (step_id, specialist, capability, depends, consumes) in steps_spec
    )
    return OrchestrationPlan(
        plan_id=f"{run_id}-plan",
        run_id=run_id,
        steps=steps,
        policy_version="radar-policy-1",
        max_parallel=2,
    )


def _contract_registry(contracts):
    from app.domain.multi_agent import CapabilityRegistry

    reg = CapabilityRegistry()
    for c in contracts:
        reg = reg.with_specialist(c)
    return reg


def _make_contract(specialist_id: str, *, capability: str, max_invocations: int = 2, timeout: int = 30):
    from app.domain.multi_agent import SpecialistContract

    return SpecialistContract(
        specialist_id=specialist_id,
        purpose="test contract for recovery behaviour",
        capability=capability,
        allowed_tools=("invalidation_completeness_check",),
        input_schema_ref="radar.schema.test.in.v1",
        output_schema_ref="radar.schema.test.out.v1",
        authority_boundary="ADVISORY_ONLY (test fixture)",
        max_invocations_per_run=max_invocations,
        timeout_seconds=timeout,
        trace_prefix="test_sp",
        failure_behavior="RETRY_WITHIN_BUDGET",
        measurable_benefit_ref="docs/active/AIMA_C_EXECUTION_RECORD.md",
        coordination_cost_note="bounded single-call test fixture",
    )


class FlakyExecutor:
    """Deterministic executor that fails the first N dispatches per step."""

    def __init__(self, failures_before_success: int = 1, failure_code: str = "PROVIDER_ERROR", failure_kind=None):
        self._failures_before_success = failures_before_success
        self._failure_code = failure_code
        self._failure_kind = failure_kind
        self._dispatch_counts: dict[str, int] = {}

    async def execute(self, step, payload, deadline) -> SpecialistOutcome:
        n = self._dispatch_counts.get(step.step_id, 0) + 1
        self._dispatch_counts[step.step_id] = n
        if n <= self._failures_before_success:
            return SpecialistOutcome(
                ok=False,
                failure_code=self._failure_code,
                failure_kind=self._failure_kind,
                summary=f"transient failure #{n}",
            )
        return SpecialistOutcome(ok=True, summary=f"recovered on attempt #{n}")


def _runtime():
    from app.services.multi_agent_runtime import MultiAgentRuntime

    ticks = {"n": 0}

    def clock():
        ticks["n"] += 1
        return float(ticks["n"])

    return MultiAgentRuntime(clock=clock)


def _independent_step_plan(run_id: str, capability: str = "hypothesis_draft"):
    # single step, no dependents: a failure never terminates via the graph,
    # so the ONLY way the run succeeds is the recovery path
    return _plan(
        run_id,
        [("s1", "AIMA-HYPOTHESIS-DRAFT", capability, (), ())],
    )


@pytest.mark.parametrize(
    "failure_kind",
    ["PROVIDER_ERROR", "MALFORMED_OUTPUT", "TIMEOUT"],
)
def test_retryable_failure_is_retried_once_and_recovered(failure_kind):
    contract = _make_contract("AIMA-HYPOTHESIS-DRAFT", capability="hypothesis_draft")
    registry = SpecialistExecutorRegistry(
        _contract_registry([contract]),
        {"AIMA-HYPOTHESIS-DRAFT": FlakyExecutor(1, failure_kind="PROVIDER_ERROR")},
    )
    plan = _independent_step_plan("run-retry-ok")
    runtime = _runtime()
    result = asyncio.run(runtime.execute_plan(plan, registry, _run_context("run-retry-ok")))
    assert not result.terminated
    assert len(result.results) == 1
    branch = result.results[0]
    assert branch.status == "SUCCEEDED"
    assert _branch_attempt(branch) == 2, "the recorded outcome must be the RETRIED attempt"
    kinds = [e.kind for e in result.trace.events]
    assert "STEP_RETRY" in kinds, "retry must be traced"
    # one original dispatch + exactly one retry dispatch (the STEP_RETRY event
    # itself is the retry's dispatch record — no duplicate STEP_DISPATCHED)
    assert kinds.count("STEP_DISPATCHED") == 1
    assert kinds.count("STEP_RETRY") == 1
    # final trace shows the SUCCESS after the retry
    assert kinds[-1] == "STEP_SUCCEEDED"


def test_retry_that_fails_again_records_the_retried_failure_honestly():
    contract = _make_contract("AIMA-HYPOTHESIS-DRAFT", capability="hypothesis_draft")
    registry = SpecialistExecutorRegistry(
        _contract_registry([contract]),
        {"AIMA-HYPOTHESIS-DRAFT": FlakyExecutor(99, failure_kind="PROVIDER_ERROR")},
    )
    plan = _independent_step_plan("run-retry-fail")
    runtime = _runtime()
    result = asyncio.run(runtime.execute_plan(plan, registry, _run_context("run-retry-fail")))
    branch = result.results[0]
    assert branch.status == "FAILED"
    assert _branch_attempt(branch) == 2, "recorded failure must be the retried attempt, not the original"
    retried = [e for e in result.trace.events if e.kind == "STEP_RETRY"]
    assert len(retried) == 1, "exactly ONE retry per step per run"


def test_retry_is_charged_to_the_specialist_budget_ceiling():
    # budget = 2: original + retry consume the whole budget; a SECOND failing
    # step for the same specialist gets BUDGET_EXHAUSTED, never a free retry
    contract = _make_contract("AIMA-HYPOTHESIS-DRAFT", capability="hypothesis_draft", max_invocations=2)
    registry = SpecialistExecutorRegistry(
        _contract_registry([contract]),
        {"AIMA-HYPOTHESIS-DRAFT": FlakyExecutor(99, failure_kind="PROVIDER_ERROR")},
    )
    plan = _plan(
        "run-retry-budget",
        [
            ("s1", "AIMA-HYPOTHESIS-DRAFT", "hypothesis_draft", (), ()),
            ("s2", "AIMA-HYPOTHESIS-DRAFT", "hypothesis_draft", (), ()),
        ],
    )
    runtime = _runtime()
    result = asyncio.run(runtime.execute_plan(plan, registry, _run_context("run-retry-budget")))
    by_step = {b.step_id: b for b in result.results}
    assert by_step["s1"].status == "FAILED" and _branch_attempt(by_step["s1"]) == 2, (
        "s1's retry fits the budget (attempt 2 == max) and must be recorded"
    )
    assert by_step["s2"].status == "FAILED"
    assert _branch_attempt(by_step["s2"]) == 1, (
        "s2's retry would be attempt 3 > budget 2 — the retry is refused and "
        "the ORIGINAL attempt-1 failure stays the recorded outcome"
    )
    # only s1 got a retry (budget exhausted before s2 could)
    retry_step_ids = [e.step_id for e in result.trace.events if e.kind == "STEP_RETRY"]
    assert "s1" in retry_step_ids
    assert "s2" not in retry_step_ids


def test_non_retryable_failure_never_retries():
    contract = _make_contract("AIMA-HYPOTHESIS-DRAFT", capability="hypothesis_draft")
    registry = SpecialistExecutorRegistry(
        _contract_registry([contract]),
        {"AIMA-HYPOTHESIS-DRAFT": FlakyExecutor(1, failure_kind="POLICY_VIOLATION")},
    )
    plan = _independent_step_plan("run-no-retry")
    runtime = _runtime()
    result = asyncio.run(runtime.execute_plan(plan, registry, _run_context("run-no-retry")))
    kinds = [e.kind for e in result.trace.events]
    assert "STEP_RETRY" not in kinds
    assert result.results[0].status == "FAILED"


def test_run_above_l2_autonomy_ceiling_refused_before_any_dispatch():
    contract = _make_contract("AIMA-HYPOTHESIS-DRAFT", capability="hypothesis_draft")
    executor = FlakyExecutor(0)  # would succeed instantly if ever dispatched
    registry = SpecialistExecutorRegistry(
        _contract_registry([contract]), {"AIMA-HYPOTHESIS-DRAFT": executor}
    )
    plan = _independent_step_plan("run-l3-refused")
    runtime = _runtime()
    with pytest.raises(ValueError, match="autonomy_level_exceeds_declared_ceiling"):
        asyncio.run(
            runtime.execute_plan(plan, registry, _run_context("run-l3-refused", level="L3"))
        )
    # nothing executed
    assert executor._dispatch_counts == {}


def test_l2_and_below_are_accepted():
    contract = _make_contract("AIMA-HYPOTHESIS-DRAFT", capability="hypothesis_draft")
    registry = SpecialistExecutorRegistry(
        _contract_registry([contract]),
        {"AIMA-HYPOTHESIS-DRAFT": FlakyExecutor(0)},
    )
    for level in ("L0", "L1", "L2"):
        run_id = f"run-ok-{level}"
        plan = _independent_step_plan(run_id)
        runtime = _runtime()
        result = asyncio.run(runtime.execute_plan(plan, registry, _run_context(run_id, level=level)))
        assert result.results[0].status == "SUCCEEDED"
