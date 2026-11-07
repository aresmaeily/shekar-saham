"""WAVE-AI (2026-11-08, WP-C): bounded parallel execution closure tests.

The WAVE-AI-ACCEPTANCE directive §4 requires the AI-MA runtime to implement
and TEST bounded parallel execution for genuinely independent branches —
not a fixed sequential plan described as parallel. This suite pins:

- the fixed HTTP plan now has TWO genuinely independent advisory branches
  (interpretation ∥ learning-challenge, both consuming only the hypothesis
  artifact) executed as ONE bounded wave (max_parallel=2 ≤ ceiling 4);
- OBSERVED concurrency: probe executors prove the branches actually run
  concurrently and that per-run concurrency never exceeds the bound;
- explicit per-run budgets (concurrency ceiling, per-step timeout,
  per-specialist invocation ceiling) are enforced;
- one canonical RunContext/RunProvenance per run;
- artifact-first branch exchange with verifiable, run-independent digests;
- deterministic synthesis over the actual branch results (refusals visible);
- cancellation propagates cleanly; failure isolation keeps independent
  branches alive; bounded recovery (exactly one retry per step) charges the
  specialist's own invocation budget;
- trace completeness and branch-level provenance (branch_id, artifact).

Runtime-level tests use instrumented executors over the REAL
MultiAgentRuntime; HTTP-level tests go through the real mounted router.
No LLM, no network, no production mutation — synthetic/paper only.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.ai_ma_specialists import shipped_capability_registry
from app.domain.multi_agent import execution_waves
from app.domain.run_governance import RunContext
from app.services.ai_ma_specialist_executors import shipped_specialist_executors
from app.services.multi_agent_runtime import (
    MultiAgentRuntime,
    SpecialistExecutorRegistry,
    SpecialistOutcome,
)
from app.main import app


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    get_settings.cache_clear()
    import os

    os.environ.setdefault("DATA_SOURCE", "mock")
    return TestClient(app, client=("aima-wp-c-test", 12402))


def _run(coro):
    """Run a coroutine on a FRESH event loop (get_event_loop has no current
    loop once other suites close it — order-independent by construction)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _runtime_context(run_id: str = "aima-wpc-run") -> RunContext:
    return RunContext(
        run_id=run_id,
        run_kind="AI_MA_ORCHESTRATION",
        autonomy_level="L1",
        policy_version="radar-policy-1",
        created_at_utc=__import__("datetime").datetime(
            2026, 11, 8, tzinfo=__import__("datetime").timezone.utc
        ),
        notes="wp-c bounded parallel test",
    )


def _shipped_registry():
    contracts = shipped_capability_registry()
    executors = shipped_specialist_executors(contracts)
    return SpecialistExecutorRegistry(contracts, executors)


def _fixed_plan_for_runtime(run_id: str):
    """The same fixed plan the API mints (imported from the API module)."""
    from app.api.ai_ma_api import _build_fixed_plan

    return _build_fixed_plan(run_id, "پرسش آزمون اجرای موازی محدود")


class _FnExecutor:
    """Adapter: exposes a bare async fn as an executor object (runtime seam)."""

    def __init__(self, fn):
        self._fn = fn

    async def execute(self, step, payload, deadline):
        return await self._fn(step, payload, deadline)


class _ConcurrencyProbe:
    """Wraps executors and records observed in-flight concurrency."""

    def __init__(self, registry: SpecialistExecutorRegistry):
        self.inflight = 0
        self.max_inflight = 0
        self._registry = registry

    def wrap(self, specialist_id: str):
        base = self._registry.executor_for(specialist_id)

        async def wrapped(step, payload, deadline):
            self.inflight += 1
            self.max_inflight = max(self.max_inflight, self.inflight)
            try:
                await asyncio.sleep(0.02)  # widen the overlap window
                return await base.execute(step, payload, deadline)
            finally:
                self.inflight -= 1

        return _FnExecutor(wrapped)

    def probed_registry(self) -> "SpecialistExecutorRegistry":
        base = self._registry
        probe = self

        class _Probed(SpecialistExecutorRegistry):
            def executor_for(self, specialist_id):
                inner = base.executor_for(specialist_id)
                if inner is None:
                    return None
                return probe.wrap(specialist_id)

        return _Probed(base.contracts, {})


class _FlakyExecutor:
    """Fails the first `fail_times` invocations, then delegates to a base."""

    def __init__(self, base, fail_times: int, failure_kind: str = "PROVIDER_ERROR"):
        self._base = base
        self._remaining = fail_times
        self._failure_kind = failure_kind
        self.calls = 0

    async def execute(self, step, payload, deadline):
        self.calls += 1
        if self._remaining > 0:
            self._remaining -= 1
            return SpecialistOutcome(
                ok=False,
                failure_code="TRANSIENT_PROVIDER_FAILURE",
                failure_kind=self._failure_kind,
                summary="transient (injected)",
            )
        return await self._base.execute(step, payload, deadline)


class _SleepingExecutor:
    """Sleeps past any deadline before returning (straggler generator)."""

    def __init__(self, sleep_seconds: float):
        self._sleep = sleep_seconds

    async def execute(self, step, payload, deadline):
        await asyncio.sleep(self._sleep)
        return SpecialistOutcome(ok=True, summary="late arrival", artifact=None)


# ---------------------------------------------------------------------------
# HTTP-level: plan shape, schedule, artifacts, synthesis, provenance
# ---------------------------------------------------------------------------


def test_fixed_plan_is_bounded_parallel_not_sequential(client):
    res = client.post(
        "/api/v10/aima/orchestrate",
        json={"question": "آیا پلن ثابت موازی محدود است؟"},
    )
    assert res.status_code == 200
    data = res.json()
    plan = data["plan"]
    # the two advisory branches are genuinely independent (both consume s1 only)
    steps = {s["step_id"]: s for s in plan["steps"]}
    assert steps["s2_interpretation"]["depends_on"] == ["s1_hypothesis"]
    assert steps["s3_challenge"]["depends_on"] == ["s1_hypothesis"]
    assert "s2_interpretation" not in steps["s3_challenge"]["depends_on"]
    # the schedule is a real parallel wave, NOT a sequential chain
    assert plan["max_parallel"] == 2
    assert plan["runtime_parallel_ceiling"] == 4
    assert plan["wave_schedule"] == [
        ["s1_hypothesis"],
        ["s2_interpretation", "s3_challenge"],
    ]
    assert data["waves_total"] == 2
    assert data["waves_executed"] == 2
    # honesty discloses the bounded-parallel posture
    assert "bounded_parallel" in data["honesty"]


def test_observed_branch_concurrency_is_two_and_bounded(client):
    # instrument the REAL runtime behind the API by executing the same fixed
    # plan through the runtime with probe executors (the API path is pinned
    # separately); observed max in-flight must be exactly 2 in wave 2
    run_id = "aima-wpc-obs"
    plan = _fixed_plan_for_runtime(run_id)
    registry = _shipped_registry()
    probe = _ConcurrencyProbe(registry)
    runtime = MultiAgentRuntime()
    result = _run(
        runtime.execute_plan(plan, probe.probed_registry(), _runtime_context(run_id))
    )
    assert result.terminated is False
    statuses = {b.step_id: b.status for b in result.results}
    assert statuses == {
        "s1_hypothesis": "SUCCEEDED",
        "s2_interpretation": "SUCCEEDED",
        "s3_challenge": "SUCCEEDED",
    }
    # genuinely concurrent (both branches overlapped) AND bounded (≤2)
    assert probe.max_inflight == 2, f"observed concurrency {probe.max_inflight}"


def test_artifact_first_exchange_with_run_independent_digests(client):
    body = {"question": "artifact-first branch exchange؟"}
    r1 = client.post("/api/v10/aima/orchestrate", json=body).json()
    r2 = client.post("/api/v10/aima/orchestrate", json=body).json()
    for run in (r1, r2):
        for step in run["steps"]:
            assert step["status"] == "SUCCEEDED"
            art = step["artifact"]
            assert art is not None, "shipped specialists must mint ArtifactRefs"
            assert art["sha256"] and len(art["sha256"]) == 64
            assert art["ref"].startswith("inmem://aima/")
            assert art["kind"].startswith("aima.")
    # content digests are run-INDEPENDENT (same question → same sha256)
    d1 = {s["step_id"]: s["artifact"]["sha256"] for s in r1["steps"]}
    d2 = {s["step_id"]: s["artifact"]["sha256"] for s in r2["steps"]}
    assert d1 == d2
    # per-run identity still differs
    assert r1["steps"][0]["artifact"]["artifact_id"] != (
        r2["steps"][0]["artifact"]["artifact_id"]
    )


def test_synthesis_folds_artifact_branches_and_refuses_nothing(client):
    res = client.post(
        "/api/v10/aima/orchestrate",
        json={"question": "synthesis over artifact branches؟"},
    )
    data = res.json()
    syn = data["synthesis"]
    assert syn["authority"] == "DETERMINISTIC_ONLY"
    assert syn["run_id"] == data["run_id"]
    src_steps = sorted(s["step_id"] for s in syn["sources"])
    assert src_steps == ["s1_hypothesis", "s2_interpretation", "s3_challenge"]
    assert syn["refused"] == []
    # every source is artifact-addressed with a digest
    for s in syn["sources"]:
        assert s["artifact"]["sha256"]


def test_governance_record_is_complete_for_the_parallel_run(client):
    res = client.post(
        "/api/v10/aima/orchestrate", json={"question": "گاورنانس اجرای موازی"}
    )
    data = res.json()
    gov = data["governance"]
    assert gov["provenance_missing"] == []
    assert gov["governed_acceptance_blocked"] is False
    assert gov["autonomy_level"] == "L1"
    trace = data["trace"]
    assert trace[0]["kind"] == "PLAN_CREATED"
    # every step dispatched exactly once and closed exactly once
    for step_id in ("s1_hypothesis", "s2_interpretation", "s3_challenge"):
        dispatched = [e for e in trace if e["step_id"] == step_id and e["kind"] == "STEP_DISPATCHED"]
        closed = [
            e
            for e in trace
            if e["step_id"] == step_id
            and e["kind"] in ("STEP_SUCCEEDED", "STEP_FAILED", "STEP_DEGRADED")
        ]
        assert len(dispatched) == 1, step_id
        assert len(closed) == 1, step_id
    # branch-level provenance: branch_id present for every step row
    for s in data["steps"]:
        assert s["branch_id"].startswith(data["run_id"] + ":")


# ---------------------------------------------------------------------------
# runtime-level: budgets, isolation, cancellation, recovery, idempotency
# ---------------------------------------------------------------------------


def _isolate_registry_for(base_registry, overrides: dict, timeout_overrides: dict | None = None):
    """Replace executors for given specialist ids (objects with .execute).

    ``timeout_overrides`` maps specialist_id → timeout_seconds and is applied
    via contract model_copy — the SHIPPED contracts are never mutated; the
    test registry hands the runtime a bounded view for deadline testing.
    """
    timeout_overrides = timeout_overrides or {}

    class _Override(SpecialistExecutorRegistry):
        def executor_for(self, specialist_id):
            if specialist_id in overrides:
                inner = overrides[specialist_id]
                return inner if hasattr(inner, "execute") else _FnExecutor(inner)
            return base_registry.executor_for(specialist_id)

        def contract_for(self, step):
            contract = base_registry.contract_for(step)
            if contract is not None and contract.specialist_id in timeout_overrides:
                return contract.model_copy(
                    update={"timeout_seconds": timeout_overrides[contract.specialist_id]}
                )
            return contract

    return _Override(base_registry.contracts, {})


def test_failure_isolation_in_parallel_wave_keeps_independent_branch():
    run_id = "aima-wpc-iso"
    plan = _fixed_plan_for_runtime(run_id)
    base = _shipped_registry()

    async def failing(step, payload, deadline):
        return SpecialistOutcome(
            ok=False,
            failure_code="INJECTED_PROVIDER_FAILURE",
            failure_kind="PROVIDER_ERROR",
            summary="injected failure",
        )

    reg = _isolate_registry_for(base, {"AIMA-INTERPRETATION": failing})
    runtime = MultiAgentRuntime()
    result = _run(
        runtime.execute_plan(plan, reg, _runtime_context(run_id))
    )
    statuses = {b.step_id: (b.status, b.failure_code) for b in result.results}
    # the failed branch is visible and classified; the independent branch survived
    assert statuses["s2_interpretation"][0] == "FAILED"
    assert "INJECTED_PROVIDER_FAILURE" in statuses["s2_interpretation"][1]
    assert statuses["s3_challenge"][0] == "SUCCEEDED"
    assert statuses["s1_hypothesis"][0] == "SUCCEEDED"
    assert result.terminated is False  # PROVIDER_ERROR → CONTINUE_OTHER_BRANCHES
    # deterministic synthesis visibly refuses the failed branch
    from app.services.multi_agent_runtime import deterministic_synthesis

    syn = deterministic_synthesis(result.results)
    refused_steps = {r.step_id for r in syn.refused}
    assert "s2_interpretation" in refused_steps


def test_parallel_timeout_discards_straggler_and_keeps_other_branch():
    run_id = "aima-wpc-tmo"
    plan = _fixed_plan_for_runtime(run_id)
    base = _shipped_registry()
    reg = _isolate_registry_for(
        base,
        {"AIMA-INTERPRETATION": _SleepingExecutor(5.0)},
        timeout_overrides={"AIMA-INTERPRETATION": 1},  # shipped contracts untouched
    )
    runtime = MultiAgentRuntime()  # real monotonic clock
    result = _run(
        runtime.execute_plan(plan, reg, _runtime_context(run_id))
    )
    statuses = {b.step_id: b.status for b in result.results}
    assert statuses["s2_interpretation"] == "FAILED"  # cancelled at deadline
    assert statuses["s3_challenge"] == "SUCCEEDED"  # independent branch unaffected
    kinds = [e.kind for e in result.trace.events]
    assert "STEP_SUCCEEDED" in kinds
    # the late result never leaked: no second outcome row for s2
    s2_rows = [b for b in result.results if b.step_id == "s2_interpretation"]
    assert len(s2_rows) == 1


def test_retry_within_budget_in_parallel_wave_charges_invocation_budget():
    run_id = "aima-wpc-retry"
    plan = _fixed_plan_for_runtime(run_id)
    base = _shipped_registry()
    flaky = _FlakyExecutor(base.executor_for("AIMA-INTERPRETATION"), fail_times=1)
    reg = _isolate_registry_for(base, {"AIMA-INTERPRETATION": flaky})
    runtime = MultiAgentRuntime()
    result = _run(
        runtime.execute_plan(plan, reg, _runtime_context(run_id))
    )
    statuses = {b.step_id: b.status for b in result.results}
    assert statuses["s2_interpretation"] == "SUCCEEDED"  # retry recovered
    assert flaky.calls == 2  # initial + exactly one bounded retry
    kinds = [(e.step_id, e.kind) for e in result.trace.events]
    assert ("s2_interpretation", "STEP_RETRY") in kinds
    # the retry is charged to the contract's ceiling (2): a second retry is impossible
    assert statuses["s1_hypothesis"] == "SUCCEEDED"
    assert statuses["s3_challenge"] == "SUCCEEDED"


def test_retry_budget_ceiling_holds_across_retries():
    run_id = "aima-wpc-budget"
    plan = _fixed_plan_for_runtime(run_id)
    base = _shipped_registry()
    flaky = _FlakyExecutor(
        base.executor_for("AIMA-INTERPRETATION"), fail_times=10
    )  # always fails transiently
    reg = _isolate_registry_for(base, {"AIMA-INTERPRETATION": flaky})
    runtime = MultiAgentRuntime()
    result = _run(
        runtime.execute_plan(plan, reg, _runtime_context(run_id))
    )
    # ceiling 2: one initial + ONE retry — never more, despite transient failures
    assert flaky.calls == 2
    statuses = {b.step_id: b.status for b in result.results}
    assert statuses["s2_interpretation"] == "FAILED"  # honest final failure
    # independent branch still completed
    assert statuses["s3_challenge"] == "SUCCEEDED"


def test_cancellation_propagates_cleanly_from_parallel_wave():
    run_id = "aima-wpc-cancel"
    plan = _fixed_plan_for_runtime(run_id)
    base = _shipped_registry()
    reg = _isolate_registry_for(
        base, {"AIMA-INTERPRETATION": _SleepingExecutor(30.0)}
    )
    runtime = MultiAgentRuntime()

    async def scenario():
        task = asyncio.ensure_future(
            runtime.execute_plan(plan, reg, _runtime_context(run_id))
        )
        await asyncio.sleep(0.2)  # let wave 2 dispatch into the sleeping branch
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return "cancelled-cleanly"
        return "not-cancelled"

    outcome = _run(scenario())
    assert outcome == "cancelled-cleanly"


def test_plan_run_context_binding_is_idempotent_checked():
    run_id = "aima-wpc-bind"
    plan = _fixed_plan_for_runtime(run_id)
    base = _shipped_registry()
    runtime = MultiAgentRuntime()
    # a mismatched RunContext (different run_id) is a caller error — refused
    with pytest.raises(ValueError):
        _run(
            runtime.execute_plan(plan, base, _runtime_context("aima-other-run"))
        )


def test_wave_schedule_is_a_pure_function_of_the_plan():
    plan = _fixed_plan_for_runtime("aima-wpc-waves")
    waves = execution_waves(plan)
    assert waves == (("s1_hypothesis",), ("s2_interpretation", "s3_challenge"))
    # width bound: no wave exceeds min(max_parallel, ceiling)
    for wave in waves:
        assert len(wave) <= plan.max_parallel
