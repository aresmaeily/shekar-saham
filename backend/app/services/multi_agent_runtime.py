"""Thin central multi-agent orchestrator runtime (additive runtime block, AI-MA-R).

Composes the EXISTING AI-MA contract layer — nothing in it is modified:
- ``app.domain.multi_agent``: OrchestrationPlan / OrchestrationStep,
  ``execution_waves`` (deterministic bounded-parallel schedule),
  SpecialistContract, BranchResult (artifact-first, orchestrator-addressed),
  TraceEvent / TraceLog (one trace fabric), ``isolate_failure``,
  ``bind_run_context``, ``bind_specialist_to_step``, MAX_PARALLEL_BRANCHES,
- ``app.domain.multi_agent_failure_model``: the closed nine-kind taxonomy,
  ``classify_step_failure``, ``FAILURE_RUN_CONTAINMENT``,
- ``app.domain.run_governance``: RunContext / ArtifactRef.

Scope guards (pre-G2 synthetic class, 02 line 202; 02-product: "No fixed
agent count. No peer-to-peer backbone. No autonomous spawning."):
- The runtime owns NO financial truth and performs NO synthesis beyond
  ``deterministic_synthesis`` — a pure, LLM-free combiner of artifact-first
  SUCCEEDED BranchResults labeled ``authority=DETERMINISTIC_ONLY``.
- Bounded parallelism (D-AI-24): per-wave concurrency NEVER exceeds
  ``min(plan.max_parallel, MAX_PARALLEL_BRANCHES)``; ``execution_waves``
  already splits wide levels, and the runtime re-chunks defensively.
- Per-step timeout via ``asyncio.wait_for`` with
  ``SpecialistContract.timeout_seconds``; the deadline instant comes from the
  injected ``clock`` (default ``time.monotonic`` — never ``time.time``).
  Late/straggler results that somehow return after their deadline are
  DISCARDED and recorded as cancelled-at-deadline timeouts — they never leak
  into results.
- Failure containment: every step failure is classified via
  ``classify_step_failure``; run-level containment is the CONJUNCTION of
  ``multi_agent.isolate_failure`` (dependency-graph decision — load-bearing
  failures terminate) and ``FAILURE_RUN_CONTAINMENT`` (kind-level ceiling —
  fail-closed kinds terminate). TERMINATE_RUN stops scheduling further
  waves; the failure stays a visible frozen record (nothing swallowed).
- Determinism: steps are dispatched in plan order; within a wave ALL tasks
  are awaited, then results and outcome traces are appended in step order —
  trace and result ordering never depend on task completion order. Given
  the same plan/registry/executors and injected clocks, the RuntimeRunResult
  is byte-stable (modulo the injected timestamps).
- Cancellation: an outer ``asyncio.CancelledError`` propagates cleanly
  (children cancelled, no orphaned tasks, no fabricated trace events); the
  caller's ``trace_sink`` (optional) retains the honest partial trace.

Clock discipline: durations/deadlines come ONLY from the injected ``clock``
(a callable returning float seconds); wall-clock instants on trace events
and BranchResults come ONLY from the injected ``now_utc``. Tests MUST inject
deterministic implementations.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import (
    Any,
    Dict,
    Callable,
    Iterable,
    Literal,
    Mapping,
    Protocol,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict, Field

from app.domain.multi_agent import (
    MAX_PARALLEL_BRANCHES,
    BranchResult,
    CapabilityRegistry,
    OrchestrationPlan,
    OrchestrationStep,
    SpecialistContract,
    TraceEvent,
    TraceKind,
    TraceLog,
    bind_run_context,
    bind_specialist_to_step,
    execution_waves,
    isolate_failure,
)
from app.domain.multi_agent_failure_model import (
    FAILURE_BEHAVIOR,
    FAILURE_RUN_CONTAINMENT,
    FailureKind,
    classify_step_failure,
)
from app.domain.run_governance import ArtifactRef, RunContext, assert_autonomy_permitted

__all__ = [
    "StepPayload",
    "SpecialistOutcome",
    "SpecialistExecutor",
    "SpecialistExecutorRegistry",
    "SyntheticSpecialistExecutor",
    "MultiAgentRuntime",
    "RuntimeRunResult",
    "DeterministicSynthesis",
    "SynthesisSource",
    "SynthesisRefusal",
    "deterministic_synthesis",
]

_RUNTIME_TRACE_PREFIX = "runtime"
_SUMMARY_MAX = 500
_DETAIL_MAX = 500
_CODE_MAX = 500


# ---------------------------------------------------------------------------
# Step payload + specialist outcome contracts
# ---------------------------------------------------------------------------


class StepPayload(BaseModel):
    """Deterministic input handed to a specialist executor for ONE step.

    Artifact-first (D-AI-23): dependency outputs travel as BranchResult
    records (which themselves carry ArtifactRefs), never as inline blobs.
    ``consumes`` is the step's own declared consumes list, passed through
    verbatim.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    specialist_id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    depends_on: tuple[str, ...] = ()
    consumes: tuple[str, ...] = ()
    consumed_results: tuple[BranchResult, ...] = ()
    notes: str = ""


class SpecialistOutcome(BaseModel):
    """What an executor returns for one step (pre-BranchResult, pre-labeling).

    The runtime — not the executor — mints BranchResults, so addressing
    (``orchestrator:<run_id>``), branch ids, timestamps and status rules stay
    in one place. ``failure_kind`` is optional: executors that know their
    failure kind (multi_agent_failure_model taxonomy) may declare it;
    otherwise the runtime classifies deterministically.
    """

    model_config = ConfigDict(frozen=True)

    ok: bool
    degraded: bool = False
    artifact: ArtifactRef | None = None
    summary: str = Field(default="", max_length=_SUMMARY_MAX)
    failure_code: str | None = None
    failure_kind: FailureKind | None = None
    # 2026-11-08 owner directive (§4 Multi-Agent UI): the executor may attach
    # its own bounded content payload so honest UIs can show WHAT a branch
    # produced (server-provided payloads only). The ref — not the blob —
    # still travels through BranchResults; content rides the run result only.
    content: Dict[str, Any] | None = None


@runtime_checkable
class SpecialistExecutor(Protocol):
    """Executor seam for one registered specialist (reference pattern).

    Implementations MUST be async, bounded, and synthetic-safe: no network,
    no LLM, no production mutation. ``deadline`` is an absolute monotonic
    float from the runtime's injected clock — executors should treat it as
    advisory; the runtime enforces it with ``asyncio.wait_for`` and DISCARDS
    any result returned after the deadline.
    """

    async def execute(
        self, step: OrchestrationStep, payload: StepPayload, deadline: float
    ) -> SpecialistOutcome: ...


class SyntheticSpecialistExecutor:
    """Deterministic synthetic executor (offline tests / paper runs only).

    Returns a fixed SpecialistOutcome per step_id; raises nothing. Never
    touches settings, env, network or LLM. Reference implementation of the
    SpecialistExecutor pattern.
    """

    def __init__(
        self,
        outcomes: Mapping[str, SpecialistOutcome],
        default: SpecialistOutcome | None = None,
    ) -> None:
        self._outcomes = dict(outcomes)
        self._default = default

    async def execute(
        self, step: OrchestrationStep, payload: StepPayload, deadline: float
    ) -> SpecialistOutcome:
        outcome = self._outcomes.get(step.step_id, self._default)
        if outcome is None:
            return SpecialistOutcome(
                ok=False, failure_code=f"no_synthetic_outcome:{step.step_id}"
            )
        return outcome


class SpecialistExecutorRegistry:
    """Immutable specialist_id → (contract, executor) composition registry.

    Executors may only be registered for specialists that exist in the
    CapabilityRegistry (misregistration is a construction-time error, not a
    runtime failure). Missing EXECUTORS for registered contracts are a
    runtime condition: the affected step fails as UNAVAILABLE_SPECIALIST.
    """

    def __init__(
        self,
        contracts: CapabilityRegistry,
        executors: Mapping[str, SpecialistExecutor],
    ) -> None:
        self._contracts = contracts
        self._executors: dict[str, SpecialistExecutor] = dict(executors)
        known = {c.specialist_id for c in contracts.entries}
        unknown = sorted(set(self._executors) - known)
        if unknown:
            raise ValueError(f"executor_without_registered_contract:{','.join(unknown)[:200]}")

    @property
    def contracts(self) -> CapabilityRegistry:
        return self._contracts

    def contract_for(self, step: OrchestrationStep) -> SpecialistContract | None:
        contract = self._contracts.get(step.specialist_id)
        if contract is None:
            return None
        try:
            bind_specialist_to_step(step, contract)
        except ValueError:
            return None
        return contract

    def executor_for(self, specialist_id: str) -> SpecialistExecutor | None:
        return self._executors.get(specialist_id)


# ---------------------------------------------------------------------------
# Runtime run result + internal step-outcome record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeRunResult:
    """Honest, deterministic result of one ``execute_plan`` invocation."""

    plan_id: str
    run_id: str
    results: tuple[BranchResult, ...]
    trace: TraceLog
    waves_executed: int
    waves_total: int
    terminated: bool
    termination_reason: str | None
    steps_scheduled: tuple[str, ...]
    steps_unscheduled: tuple[str, ...]
    # 2026-11-08 owner directive (§4): per-step artifact CONTENT (bounded,
    # server-provided) keyed by step_id — the honest material for UI artifact
    # viewers. Empty when no executor attached content. Never persisted.
    artifact_contents: Dict[str, Dict[str, Any]] | None = None


@dataclass(frozen=True)
class _StepOutcome:
    """Internal per-step outcome; recorded in step order after each wave."""

    branch_result: BranchResult
    trace_kind: TraceKind
    trace_prefix: str
    detail: str
    kind: FailureKind | None = None  # set for FAILED / DEGRADED outcomes
    content: Dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# The runtime
# ---------------------------------------------------------------------------


class MultiAgentRuntime:
    """Thin central orchestrator over injected specialist executors."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        now_utc: Callable[[], datetime] | None = None,
        max_parallel_ceiling: int = MAX_PARALLEL_BRANCHES,
    ) -> None:
        self._clock = clock if clock is not None else time.monotonic
        self._now_utc = now_utc if now_utc is not None else (lambda: datetime.now(timezone.utc))
        self._ceiling = max(1, min(int(max_parallel_ceiling), MAX_PARALLEL_BRANCHES))

    @property
    def max_parallel_ceiling(self) -> int:
        """The effective per-wave concurrency ceiling of THIS runtime instance
        (never above the global MAX_PARALLEL_BRANCHES). Exposed read-only so
        honest surfaces can disclose the actual bound (WAVE-AI WP-C)."""
        return self._ceiling

    # -- public API ---------------------------------------------------------

    async def execute_plan(
        self,
        plan: OrchestrationPlan,
        registry: SpecialistExecutorRegistry,
        run_context: RunContext,
        *,
        trace_sink: list[TraceEvent] | None = None,
    ) -> RuntimeRunResult:
        """Walk ``execution_waves(plan)`` in order with bounded parallelism.

        Raises ValueError via ``bind_run_context`` on plan/context mismatch
        (caller error, fail fast). asyncio.CancelledError propagates cleanly.
        Every other failure is contained into visible frozen records.
        """
        bind_run_context(plan, run_context)
        # WAVE-AB3 (WP-C): the autonomy-ceiling gate is now enforced INSIDE the
        # orchestration path (was only enforced at RunContext construction — the
        # runtime itself never checked). Advisory orchestration runs at ceiling
        # L2: a run minted above the ceiling is refused before ANY step
        # dispatches (fail-closed; nothing executes, nothing is recorded).
        assert_autonomy_permitted(run_context, "L2")
        events = trace_sink if trace_sink is not None else []
        self._emit(
            events,
            run_id=plan.run_id,
            step_id=None,
            trace_prefix=_RUNTIME_TRACE_PREFIX,
            kind="PLAN_CREATED",
            detail=(
                f"plan_id={plan.plan_id}; steps={len(plan.steps)}; "
                f"max_parallel={plan.max_parallel}"
            ),
        )

        step_map = {s.step_id: s for s in plan.steps}
        waves = execution_waves(plan)
        results_by_step: dict[str, BranchResult] = {}
        collected_contents: dict[str, dict[str, Any]] = {}
        invocation_counts: dict[str, int] = {}
        scheduled: list[str] = []
        terminated = False
        termination_reason: str | None = None
        waves_executed = 0
        ceiling = max(1, min(plan.max_parallel, self._ceiling))

        for wave in waves:
            if terminated:
                break
            waves_executed += 1
            for chunk_start in range(0, len(wave), ceiling):
                chunk = wave[chunk_start : chunk_start + ceiling]

                # --- dispatch preparation (step order) -------------------
                dispatchable: list[
                    tuple[OrchestrationStep, SpecialistContract, Any, int, float]
                ] = []
                blocked: dict[str, _StepOutcome] = {}
                for step_id in chunk:
                    step = step_map[step_id]
                    contract = registry.contract_for(step)
                    if contract is None:
                        kind = classify_step_failure(None, specialist_unavailable=True)
                        blocked[step_id] = self._failure_outcome(
                            plan,
                            step,
                            contract=None,
                            attempt=0,
                            kind=kind,
                            detail=f"UNAVAILABLE_SPECIALIST:not_registered:{step.specialist_id}",
                        )
                        continue
                    executor = registry.executor_for(step.specialist_id)
                    if executor is None:
                        kind = classify_step_failure(None, specialist_unavailable=True)
                        blocked[step_id] = self._failure_outcome(
                            plan,
                            step,
                            contract=contract,
                            attempt=0,
                            kind=kind,
                            detail="UNAVAILABLE_SPECIALIST:no_executor_registered",
                        )
                        continue
                    attempt = invocation_counts.get(contract.specialist_id, 0) + 1
                    if attempt > contract.max_invocations_per_run:
                        kind = classify_step_failure(None, budget_state="BUDGET_EXHAUSTED")
                        blocked[step_id] = self._failure_outcome(
                            plan,
                            step,
                            contract=contract,
                            attempt=attempt,
                            kind=kind,
                            detail=(
                                f"BUDGET_EXHAUSTED:max_invocations_per_run="
                                f"{contract.max_invocations_per_run}"
                            ),
                        )
                        continue
                    deadline = self._clock() + contract.timeout_seconds
                    dispatchable.append((step, contract, executor, attempt, deadline))

                # --- dispatch traces (step order, before any execution) ---
                for step, contract, _executor, attempt, _deadline in dispatchable:
                    invocation_counts[contract.specialist_id] = attempt
                    scheduled.append(step.step_id)
                    self._emit(
                        events,
                        run_id=plan.run_id,
                        step_id=step.step_id,
                        trace_prefix=contract.trace_prefix,
                        kind="STEP_DISPATCHED",
                        detail=(
                            f"specialist_id={contract.specialist_id}; attempt={attempt}; "
                            f"timeout_seconds={contract.timeout_seconds}"
                        ),
                    )

                # --- await ALL tasks of the wave, then record in step order
                outcomes: dict[str, _StepOutcome] = dict(blocked)
                run_outcomes = await self._run_dispatched(
                    plan, results_by_step, dispatchable
                )
                for outcome in run_outcomes:
                    outcomes[outcome.branch_result.step_id] = outcome

                # --- WAVE-AB3 recovery: bounded RETRY_WITHIN_BUDGET ---------
                # The failure model declares PROVIDER_ERROR / MALFORMED_OUTPUT /
                # TIMEOUT as retryable. The runtime previously left that mapping
                # advisory — it never retried (recorded P1 gap). Now: exactly ONE
                # deterministic immediate retry per step per run, each retry a
                # NEW invocation charged to the specialist's own budget ceiling
                # (no silent budget bypass), traced as STEP_RETRY, and the final
                # outcome recorded is the RETRIED attempt's outcome (fail-honest:
                # a retry that fails again is recorded as failed, never as the
                # original transient error). Non-retryable kinds, exhausted
                # budgets and already-retried steps pass through untouched.
                dispatch_map = {step.step_id: (step, contract, executor) for step, contract, executor, _a, _d in dispatchable}
                retried_this_wave: dict[str, _StepOutcome] = {}
                for step_id in chunk:
                    if step_id not in outcomes or step_id in retried_this_wave:
                        continue
                    outcome = outcomes[step_id]
                    if outcome.branch_result.status == "SUCCEEDED":
                        continue
                    if outcome.kind is None or FAILURE_BEHAVIOR.get(outcome.kind) != "RETRY_WITHIN_BUDGET":
                        continue
                    entry = dispatch_map.get(step_id)
                    if entry is None:
                        continue  # blocked/budget/refused outcomes never retry
                    retry_step, retry_contract, retry_executor = entry
                    next_attempt = invocation_counts.get(retry_contract.specialist_id, 0) + 1
                    if next_attempt > retry_contract.max_invocations_per_run:
                        continue  # budget ceiling holds across retries too
                    retry_deadline = self._clock() + retry_contract.timeout_seconds
                    self._emit(
                        events,
                        run_id=plan.run_id,
                        step_id=step_id,
                        trace_prefix=retry_contract.trace_prefix,
                        kind="STEP_RETRY",
                        detail=(
                            f"failure_kind={outcome.kind}; attempt={next_attempt}; "
                            f"max_invocations_per_run={retry_contract.max_invocations_per_run}"
                        ),
                    )
                    retry_outcomes = await self._run_dispatched(
                        plan,
                        results_by_step,
                        [(retry_step, retry_contract, retry_executor, next_attempt, retry_deadline)],
                    )
                    if retry_outcomes:
                        invocation_counts[retry_contract.specialist_id] = next_attempt
                        scheduled.append(step_id)
                        retried_this_wave[step_id] = retry_outcomes[0]
                        outcomes[step_id] = retry_outcomes[0]

                for step_id in chunk:
                    outcome = outcomes[step_id]
                    results_by_step[step_id] = outcome.branch_result
                    # 2026-11-08 owner directive (§4): accumulate content
                    # across wave chunks (the per-chunk outcomes dict is
                    # scoped); only the FINAL succeeded attempt is kept.
                    if (
                        outcome.branch_result.status == "SUCCEEDED"
                        and outcome.branch_result.artifact is not None
                        and outcome.content is not None
                    ):
                        collected_contents[step_id] = dict(outcome.content)
                    self._emit(
                        events,
                        run_id=plan.run_id,
                        step_id=step_id,
                        trace_prefix=outcome.trace_prefix,
                        kind=outcome.trace_kind,
                        detail=outcome.detail,
                        artifact_id=self._artifact_id_of(outcome.branch_result),
                    )

                # --- failure isolation (chunk order; first decision wins) --
                for step_id in chunk:
                    outcome = outcomes[step_id]
                    if outcome.branch_result.status == "SUCCEEDED":
                        continue
                    graph_decision = isolate_failure(
                        step_id, plan, tuple(results_by_step.values())
                    )
                    kind_decision = (
                        FAILURE_RUN_CONTAINMENT[outcome.kind]
                        if outcome.kind is not None
                        else "CONTINUE_OTHER_BRANCHES"
                    )
                    if graph_decision == "TERMINATE_RUN" or kind_decision == "TERMINATE_RUN":
                        terminated = True
                        termination_reason = f"step_failed:{step_id}:{outcome.kind}"
                        self._emit(
                            events,
                            run_id=plan.run_id,
                            step_id=None,
                            trace_prefix=_RUNTIME_TRACE_PREFIX,
                            kind="RUN_TERMINATED",
                            detail=termination_reason,
                        )
                        break
                if terminated:
                    break
            if terminated:
                break

        trace = TraceLog()
        for event in events:
            trace = trace.append(event)
        results = tuple(
            results_by_step[s.step_id] for s in plan.steps if s.step_id in results_by_step
        )
        unscheduled = tuple(s.step_id for s in plan.steps if s.step_id not in results_by_step)
        # 2026-11-08 owner directive (§4): keep ONLY the final succeeded
        # attempt's content per step (a retried failure's stale content is
        # never surfaced); content without an artifact ref is never collected.
        artifact_contents = dict(collected_contents)
        return RuntimeRunResult(
            plan_id=plan.plan_id,
            run_id=plan.run_id,
            results=results,
            trace=trace,
            waves_executed=waves_executed,
            waves_total=len(waves),
            terminated=terminated,
            termination_reason=termination_reason,
            steps_scheduled=tuple(scheduled),
            steps_unscheduled=unscheduled,
            artifact_contents=artifact_contents,
        )

    # -- step execution -------------------------------------------------------

    async def _run_dispatched(
        self,
        plan: OrchestrationPlan,
        results_by_step: Mapping[str, BranchResult],
        dispatchable: list[tuple[OrchestrationStep, SpecialistContract, Any, int, float]],
    ) -> list[_StepOutcome]:
        """Run all dispatched steps concurrently; return outcomes (any order).

        The CALLER records outcomes in step order after this returns —
        completion order never leaks into results or traces.
        """
        if not dispatchable:
            return []

        async def _one(
            step: OrchestrationStep,
            contract: SpecialistContract,
            executor: Any,
            attempt: int,
            deadline: float,
        ) -> _StepOutcome:
            payload = self._build_payload(plan, step, results_by_step)
            remaining = deadline - self._clock()
            if remaining <= 0:
                return self._timeout_outcome(
                    plan, step, contract, attempt, "deadline_passed"
                )
            try:
                outcome = await asyncio.wait_for(
                    executor.execute(step, payload, deadline), timeout=remaining
                )
            except asyncio.CancelledError:
                # Outer cancellation propagates cleanly; no fabricated record.
                raise
            except TimeoutError:
                return self._timeout_outcome(
                    plan, step, contract, attempt, "deadline_exceeded"
                )
            except Exception as exc:  # noqa: BLE001 — contained, classified, visible
                kind = classify_step_failure(type(exc))
                detail = f"{kind}:{type(exc).__name__}:{str(exc)[:120]}"
                return self._failure_outcome(
                    plan, step, contract=contract, attempt=attempt, kind=kind, detail=detail
                )
            # Straggler guard: a result that arrives after its deadline is a
            # cancelled late completion — DISCARDED, never leaked into results.
            if self._clock() > deadline:
                return self._timeout_outcome(
                    plan, step, contract, attempt, "straggler_discarded"
                )
            return self._outcome_from_executor(plan, step, contract, attempt, outcome)

        # Children run concurrently; exceptions are contained inside _one
        # (only CancelledError can escape, by contract).
        return list(
            await asyncio.gather(
                *(
                    _one(step, contract, executor, attempt, deadline)
                    for (step, contract, executor, attempt, deadline) in dispatchable
                )
            )
        )

    # -- outcome construction --------------------------------------------------

    def _timeout_outcome(
        self,
        plan: OrchestrationPlan,
        step: OrchestrationStep,
        contract: SpecialistContract,
        attempt: int,
        why: str,
    ) -> _StepOutcome:
        kind = classify_step_failure(TimeoutError, timeout_elapsed=True)
        return self._failure_outcome(
            plan,
            step,
            contract=contract,
            attempt=attempt,
            kind=kind,
            detail=f"TIMEOUT:step_cancelled_at_deadline ({why}); late result discarded",
        )

    def _outcome_from_executor(
        self,
        plan: OrchestrationPlan,
        step: OrchestrationStep,
        contract: SpecialistContract,
        attempt: int,
        outcome: Any,
    ) -> _StepOutcome:
        if not isinstance(outcome, SpecialistOutcome):
            kind = classify_step_failure(None, malformed_output=True)
            return self._failure_outcome(
                plan,
                step,
                contract=contract,
                attempt=attempt,
                kind=kind,
                detail=f"{kind}:executor_contract_violation (non-SpecialistOutcome)",
            )
        if outcome.ok:
            if outcome.artifact is not None:
                branch = self._branch_result(
                    plan,
                    step,
                    contract,
                    attempt,
                    status="SUCCEEDED",
                    artifact=outcome.artifact,
                    summary=outcome.summary[:_SUMMARY_MAX],
                    summary_only=False,
                    failure_code=None,
                )
                return _StepOutcome(
                    branch_result=branch,
                    trace_kind="STEP_SUCCEEDED",
                    trace_prefix=contract.trace_prefix,
                    detail="ok (artifact-first)",
                    kind=outcome.failure_kind,
                    content=outcome.content,
                )
            if outcome.summary.strip():
                branch = self._branch_result(
                    plan,
                    step,
                    contract,
                    attempt,
                    status="SUCCEEDED",
                    artifact=None,
                    summary=outcome.summary[:_SUMMARY_MAX],
                    summary_only=True,
                    failure_code=None,
                )
                return _StepOutcome(
                    branch_result=branch,
                    trace_kind="STEP_SUCCEEDED",
                    trace_prefix=contract.trace_prefix,
                    detail="ok (summary_only)",
                    kind=outcome.failure_kind,
                )
            kind = classify_step_failure(None, artifact_invalid=True)
            return self._failure_outcome(
                plan,
                step,
                contract=contract,
                attempt=attempt,
                kind=kind,
                detail=f"{kind}:executor_returned_no_payload",
            )
        kind = outcome.failure_kind or classify_step_failure(None)
        code = outcome.failure_code or f"{kind}:executor_reported_failure"
        if outcome.artifact is not None:
            # DEGRADED/FAILED BranchResults cannot carry payloads (validator);
            # a dropped artifact stays visible in the failure code.
            code = f"{code};artifact_discarded"
        status: str = "DEGRADED" if outcome.degraded else "FAILED"
        branch = self._branch_result(
            plan,
            step,
            contract,
            attempt,
            status=status,
            artifact=None,
            summary="",
            summary_only=False,
            failure_code=code[:_CODE_MAX],
        )
        return _StepOutcome(
            branch_result=branch,
            trace_kind="STEP_DEGRADED" if outcome.degraded else "STEP_FAILED",
            trace_prefix=contract.trace_prefix,
            detail=f"{status}:{code[:200]}",
            kind=kind,
        )

    def _failure_outcome(
        self,
        plan: OrchestrationPlan,
        step: OrchestrationStep,
        *,
        contract: SpecialistContract | None,
        attempt: int,
        kind: FailureKind,
        detail: str,
    ) -> _StepOutcome:
        branch = self._branch_result(
            plan,
            step,
            contract,
            attempt,
            status="FAILED",
            artifact=None,
            summary="",
            summary_only=False,
            failure_code=detail[:_CODE_MAX],
        )
        return _StepOutcome(
            branch_result=branch,
            trace_kind="STEP_FAILED",
            trace_prefix=contract.trace_prefix if contract is not None else _RUNTIME_TRACE_PREFIX,
            detail=detail[:_DETAIL_MAX],
            kind=kind,
        )

    # -- helpers ---------------------------------------------------------------

    def _branch_result(
        self,
        plan: OrchestrationPlan,
        step: OrchestrationStep,
        contract: SpecialistContract | None,
        attempt: int,
        *,
        status: str,
        artifact: ArtifactRef | None,
        summary: str,
        summary_only: bool,
        failure_code: str | None,
    ) -> BranchResult:
        return BranchResult(
            branch_id=f"{plan.run_id}:{step.step_id}:a{max(attempt, 1)}",
            run_id=plan.run_id,
            step_id=step.step_id,
            specialist_id=(
                contract.specialist_id if contract is not None else step.specialist_id
            ),
            addressed_to=f"orchestrator:{plan.run_id}",
            status=status,  # type: ignore[arg-type]
            artifact=artifact,
            summary=summary,
            summary_only=summary_only,
            failure_code=failure_code,
            completed_at_utc=self._now_utc(),
        )

    def _build_payload(
        self,
        plan: OrchestrationPlan,
        step: OrchestrationStep,
        results_by_step: Mapping[str, BranchResult],
    ) -> StepPayload:
        consumed = tuple(
            results_by_step[dep] for dep in step.depends_on if dep in results_by_step
        )
        return StepPayload(
            run_id=plan.run_id,
            plan_id=plan.plan_id,
            step_id=step.step_id,
            specialist_id=step.specialist_id,
            capability=step.capability,
            depends_on=step.depends_on,
            consumes=step.consumes,
            consumed_results=consumed,
            notes=step.notes,  # WAVE-AB3: step-level notes (e.g. the hypothesis
            # specialist's 'question:' input) now reach the executor verbatim —
            # previously the runtime dropped them, leaving the field always empty
        )

    @staticmethod
    def _artifact_id_of(result: BranchResult) -> str | None:
        return result.artifact.artifact_id if result.artifact is not None else None

    def _emit(
        self,
        events: list[TraceEvent],
        *,
        run_id: str,
        step_id: str | None,
        trace_prefix: str,
        kind: TraceKind,
        detail: str,
        artifact_id: str | None = None,
    ) -> None:
        events.append(
            TraceEvent(
                event_id=self._event_id(run_id, step_id, kind),
                run_id=run_id,
                step_id=step_id,
                trace_prefix=trace_prefix,
                kind=kind,
                at_utc=self._now_utc(),
                detail=detail[:_DETAIL_MAX],
                artifact_id=artifact_id,
            )
        )

    @staticmethod
    def _event_id(run_id: str, step_id: str | None, kind: TraceKind) -> str:
        if step_id is None:
            return f"{run_id}:{kind.lower()}"
        return f"{run_id}:{step_id}:{kind.lower()}"


# ---------------------------------------------------------------------------
# Deterministic synthesis (no LLM, no generation)
# ---------------------------------------------------------------------------


class SynthesisSource(BaseModel):
    """One artifact-first SUCCEEDED branch folded into the synthesis."""

    model_config = ConfigDict(frozen=True)

    branch_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    specialist_id: str = Field(min_length=1)
    artifact: ArtifactRef
    summary: str = ""


class SynthesisRefusal(BaseModel):
    """One visibly refused BranchResult (nothing silently swallowed)."""

    model_config = ConfigDict(frozen=True)

    branch_id: str = Field(min_length=1)
    step_id: str | None = None
    reason: str = Field(min_length=1)


class DeterministicSynthesis(BaseModel):
    """Pure, LLM-free merge of artifact-first SUCCEEDED branch results.

    ``authority`` is pinned to DETERMINISTIC_ONLY: this record NEVER carries
    generated content — only references to existing artifacts produced by
    governed specialist branches.
    """

    model_config = ConfigDict(frozen=True)

    authority: Literal["DETERMINISTIC_ONLY"] = "DETERMINISTIC_ONLY"
    run_id: str | None = None
    sources: tuple[SynthesisSource, ...] = ()
    refused: tuple[SynthesisRefusal, ...] = ()


def deterministic_synthesis(results: Iterable[BranchResult]) -> DeterministicSynthesis:
    """Merge ONLY artifact-first SUCCEEDED results addressed to the orchestrator.

    Pure combiner: no LLM, no generation, no clock. FAILED/DEGRADED payloads
    are refused (visible in ``refused`` with a reason — never blended);
    summary-only successes (no artifact) are refused; results spanning
    multiple run_ids are ALL refused (mixing runs would fabricate context).
    Output ordering is (step_id, branch_id) — independent of input order.
    """
    materialized = list(results)
    run_ids = {r.run_id for r in materialized}
    if len(run_ids) > 1:
        refused = tuple(
            sorted(
                (
                    SynthesisRefusal(
                        branch_id=r.branch_id, step_id=r.step_id, reason="mixed_run_ids"
                    )
                    for r in materialized
                ),
                key=lambda x: (x.branch_id, x.reason),
            )
        )
        return DeterministicSynthesis(refused=refused)

    run_id = next(iter(run_ids)) if run_ids else None
    sources: list[SynthesisSource] = []
    refusals: list[SynthesisRefusal] = []
    for r in materialized:
        if r.addressed_to != f"orchestrator:{r.run_id}":
            refusals.append(
                SynthesisRefusal(
                    branch_id=r.branch_id, step_id=r.step_id, reason="peer_addressing"
                )
            )
        elif r.status != "SUCCEEDED":
            refusals.append(
                SynthesisRefusal(
                    branch_id=r.branch_id, step_id=r.step_id, reason="non_succeeded_status"
                )
            )
        elif r.artifact is None:
            refusals.append(
                SynthesisRefusal(
                    branch_id=r.branch_id,
                    step_id=r.step_id,
                    reason="summary_only_without_artifact",
                )
            )
        else:
            sources.append(
                SynthesisSource(
                    branch_id=r.branch_id,
                    step_id=r.step_id,
                    specialist_id=r.specialist_id,
                    artifact=r.artifact,
                    summary=r.summary,
                )
            )
    sources.sort(key=lambda s: (s.step_id, s.branch_id))
    refusals.sort(key=lambda x: (x.branch_id, x.reason))
    return DeterministicSynthesis(run_id=run_id, sources=tuple(sources), refused=tuple(refusals))
