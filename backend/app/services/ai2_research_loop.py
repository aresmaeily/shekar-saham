"""AI-2 synthetic/paper research-loop runner (additive runtime block, AI2-B).

Composes the EXISTING AI-2 contracts — nothing in them is modified:
- ``app.services.ai2_service.AI2Service.run`` (single stage-2 invocation;
  gated outcomes; ``executed_shadow`` is the synthetic-transport-only label),
- ``app.domain.ai2_governance`` (AI2BudgetSpec, budget_verdict,
  classify_duplicate, AI2RunRecord, AI2RunLedger, AI2EvidenceArtifact,
  recovery_decision),
- ``app.domain.run_governance`` (RunContext identity binding),
- ``app.domain.research_memory`` (EpisodicRunArchive / EpisodicRunArtifact),
- ``app.domain.g2_gate.execution_mode`` (the SYNTHETIC_OR_PAPER label).

Governance invariants preserved by construction (see REM1/AI2-F records):
- The runner NEVER reads or writes settings, NEVER touches AI2_ENABLED, and
  NEVER constructs a network transport. A synthetic transport reaches the
  service ONLY because the caller injects it (``transport=...``); with no
  injection the service itself gates the run (AI2_ENABLED=0 default,
  G2 fail-closed). ``execution_mode`` here is used purely as a LABEL source.
- The loop is bounded: EXACTLY ONE stage-2 ``AI2Service.run`` invocation per
  ``execute_run`` call, and the session budget (``AI2BudgetSpec`` ceilings —
  max_provider_invocations is therefore also the max-runs-per-session bound,
  since each run consumes exactly one invocation) is enforced ACROSS calls
  via ``budget_verdict`` before each run. Exhausted budget refuses further
  runs with a BUDGET_EXHAUSTED ledger record — the runner never raises raw
  exceptions out of ``execute_run`` (unexpected internal errors map to a
  FAILED record + ``runner_error`` outcome; asyncio.CancelledError is
  re-raised — cancellation must propagate).

Clock discipline (mirrors the repository's clock-free contract style):
- Wall-time durations come ONLY from the injected ``clock`` (a callable
  returning float seconds; default ``time.monotonic`` — NEVER ``time.time``).
- Wall-clock instants (recorded_at_utc, refusal timestamps) come ONLY from
  the injected ``now_utc`` (default ``datetime.now(timezone.utc)``).
  Tests MUST inject deterministic implementations of both.

OUTCOME → LEDGER-STATUS MAPPING TABLE (explicit, engineering-authority
record; ``governed_acceptance`` accepts ONLY status COMPLETED, so every
non-COMPLETED row below is structurally un-acceptable):

    ====================  ======================  =========================
    AI2Service outcome    AI2RunRecord.status     governed_acceptance
    (AI2Status)                                   verdict on the record
    ====================  ======================  =========================
    executed              COMPLETED               may accept (unreachable
                          (+ evidence artifact)   while AI2_ENABLED=0 /
                                                  G2 fail-closed gates hold)
    executed_shadow       LEDGERED                refused
                                                  ("run_status_not_
                                                  completed") — a synthetic
                                                  shadow run is NEVER
                                                  COMPLETED, by mapping and
                                                  by validator (LEDGERED
                                                  cannot carry an artifact)
    failed_provider       FAILED                  refused
    failed_schema         FAILED                  refused
    gated_not_executed    GATED_NOT_EXECUTED      refused
    (runner refusals)     DUPLICATE_FLAGGED /     refused
                          BUDGET_EXHAUSTED
    ====================  ======================  =========================

Duplicate policy (per ``classify_duplicate`` semantics): DUPLICATE_IDENTICAL
refuses the run BEFORE any execution (nothing runs, nothing appends — the
identical run is already ledgered); DUPLICATE_REPEATED_QUESTION is "allowed,
but visible" — the run EXECUTES and its ledger record is flagged
``DUPLICATE_FLAGGED`` (which, per the AI2RunRecord validator, cannot carry an
artifact, so a flagged run can never become an accepted COMPLETED record;
the underlying service outcome stays visible in ``record.notes`` and on the
returned outcome). Archive evidence (when an archive is provided) is still
appended for honestly-executed runs — with the SYNTHETIC_OR_PAPER label
carried through in the entry notes.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.ai2_governance import (
    AI2BudgetSpec,
    AI2EvidenceArtifact,
    AI2RunLedger,
    AI2RunRecord,
    AI2RunStatus,
    BudgetUsage,
    BudgetVerdict,
    DuplicateClass,
    RecoveryDecision,
    budget_verdict,
    classify_duplicate,
    recovery_decision,
)
from app.domain.evidence import ensure_utc
from app.domain.g2_gate import execution_mode
from app.domain.research_memory import EpisodicRunArchive, EpisodicRunArtifact
from app.domain.run_governance import ApprovalState, ArtifactRef, RunContext
from app.services.ai2_service import AI2Request, AI2Result, AI2Service, AI2Transport

__all__ = [
    "AI2ResearchRunInput",
    "AI2LoopOutcome",
    "AI2LoopRefusal",
    "AI2LoopStatus",
    "AI2ResearchLoopRunner",
    "OUTCOME_STATUS_MAP",
    "append_record_idempotent",
]

#: The known AI-2 tasks (same closed set as AI2RunRecord._known_task /
#: AITaskType in ai_service.py).
_AI2_TASKS = frozenset({"assistant", "analyst", "optimizer", "research", "strategy", "risk"})

#: Explicit outcome → ledger-status mapping table (see module docstring).
OUTCOME_STATUS_MAP: dict[str, AI2RunStatus] = {
    "executed": "COMPLETED",
    "executed_shadow": "LEDGERED",
    "failed_provider": "FAILED",
    "failed_schema": "FAILED",
    "gated_not_executed": "GATED_NOT_EXECUTED",
}

_SHA_LENGTH = 64


def _hex64(v: str) -> str:
    if len(v) != _SHA_LENGTH or any(c not in "0123456789abcdef" for c in v.lower()):
        raise ValueError("input_snapshot_sha256_must_be_64_hex")
    return v.lower()


# ---------------------------------------------------------------------------
# Run input contract
# ---------------------------------------------------------------------------


class AI2ResearchRunInput(BaseModel):
    """Caller-supplied identity + payload for ONE bounded loop run.

    ``input_snapshot_sha256`` is the PRE-RUN input identity used for
    duplicate classification and ledger keying (the service's own
    provenance hash of the deterministic context is recorded on the
    evidence artifact — both are honest, distinct identities: caller-declared
    run identity vs. service-observed input snapshot).
    """

    model_config = ConfigDict(frozen=True)

    record_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    run_kind: str = Field(
        default="AI2_INTERPRETATION", min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$"
    )
    policy_version: str = Field(min_length=1)
    task: str = Field(min_length=1, max_length=64)
    request: AI2Request
    input_snapshot_sha256: str = Field(min_length=_SHA_LENGTH, max_length=_SHA_LENGTH)
    approval_state: ApprovalState = "NOT_REQUIRED"
    approved_by: str | None = None
    dataset_version: str | None = None
    #: Declared trust state used on refusal records where nothing was
    #: observed ("unobserved" is the explicit no-observation sentinel).
    declared_trust_state: str = Field(default="unobserved", min_length=1, max_length=64)
    notes: str = ""

    @field_validator("input_snapshot_sha256")
    @classmethod
    def _hex(cls, v: str) -> str:
        return _hex64(v)

    @field_validator("task")
    @classmethod
    def _known_task(cls, v: str) -> str:
        if v not in _AI2_TASKS:
            raise ValueError("unknown_ai2_task")
        return v

    @model_validator(mode="after")
    def _consistency(self) -> "AI2ResearchRunInput":
        if self.task != self.request.task:
            raise ValueError("run_input_task_must_match_request_task")
        if self.approval_state == "APPROVED" and not self.approved_by:
            raise ValueError("approved_state_requires_approver")
        return self


# ---------------------------------------------------------------------------
# Outcome / status records
# ---------------------------------------------------------------------------


class AI2LoopOutcome(BaseModel):
    """Honest result of one ``execute_run`` call (never raises raw errors)."""

    model_config = ConfigDict(frozen=True)

    #: Service outcome label verbatim ("executed", "executed_shadow",
    #: "failed_provider", "failed_schema", "gated_not_executed") or a
    #: runner refusal label ("duplicate_refused", "budget_exhausted",
    #: "ledger_record_conflict", "runner_error", "run_context_mismatch").
    outcome: str
    ok: bool
    ledger_status: AI2RunStatus | None = None
    record: AI2RunRecord | None = None
    result: AI2Result | None = None
    duplicate_class: DuplicateClass | None = None
    elapsed_wall_seconds: float = Field(default=0.0, ge=0.0)
    recovery: RecoveryDecision | None = None
    #: "SYNTHETIC_OR_PAPER" / "LIVE" — forced to SYNTHETIC_OR_PAPER for
    #: executed_shadow (the service's test-only-transport guarantee).
    execution_label: str | None = None
    refusal_reason: str | None = None
    archived_evidence: bool = False
    notes: str = ""


class AI2LoopRefusal(BaseModel):
    """One refusal entry in the loop's honest refused-reasons ledger."""

    model_config = ConfigDict(frozen=True)

    reason: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    record_id: str | None = None
    detail: str = ""
    at_utc: datetime

    @field_validator("at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


class AI2LoopStatus(BaseModel):
    """Honest loop status: runs executed, refusals, budget remaining."""

    model_config = ConfigDict(frozen=True)

    runs_attempted: int = Field(ge=0)
    stage2_invocations_used: int = Field(ge=0)
    iterations_used: int = Field(ge=0)
    wall_seconds_used: float = Field(ge=0.0)
    max_provider_invocations: int = Field(ge=1)
    max_iterations: int = Field(ge=1)
    max_wall_seconds: int = Field(ge=1)
    remaining_provider_invocations: int = Field(ge=0)
    remaining_iterations: int = Field(ge=0)
    remaining_wall_seconds: float = Field(ge=0.0)
    budget_now: BudgetVerdict
    ledger_size: int = Field(ge=0)
    records_appended: int = Field(ge=0)
    refusals: tuple[AI2LoopRefusal, ...] = ()
    last_outcome: str | None = None


def append_record_idempotent(
    ledger: AI2RunLedger, record: AI2RunRecord
) -> tuple[AI2RunLedger, bool, bool]:
    """Idempotent, conflict-safe ledger append (append-only preserved).

    Returns ``(ledger, appended, conflict)``:
    - byte-identical re-append of an existing record_id → no-op,
      ``appended=True, conflict=False`` (the record is in the ledger);
    - conflicting reuse of a record_id → ``appended=False, conflict=True``
      (ledger returned unchanged; the CALLER decides visibility — the
      runner turns this into a refusal outcome instead of raising);
    - new record_id → appended to a NEW immutable ledger instance.
    """
    existing = ledger.get(record.record_id)
    if existing is not None:
        if existing == record:
            return ledger, True, False
        return ledger, False, True
    return ledger.append(record), True, False


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------


class AI2ResearchLoopRunner:
    """Bounded research-loop runner around ONE injected AI2Service.

    Session state (invocation/iteration/wall counters, refusal ledger) lives
    on the runner instance and persists ACROSS ``execute_run`` calls; the
    ``AI2RunLedger`` remains the immutable append-only record store.
    """

    def __init__(
        self,
        service: AI2Service,
        ledger: AI2RunLedger,
        budget: AI2BudgetSpec,
        archive: EpisodicRunArchive | None = None,
        *,
        clock: Callable[[], float] | None = None,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service
        self._ledger = ledger
        self._budget = budget
        self._archive = archive
        # Default clock is time.monotonic (durations only) — never time.time.
        self._clock = clock if clock is not None else time.monotonic
        self._now_utc = now_utc if now_utc is not None else (lambda: datetime.now(timezone.utc))
        self._invocations = 0
        self._iterations = 0
        self._wall_seconds = 0.0
        self._failed_invocations = 0
        self._attempts = 0
        self._records_appended = 0
        self._refusals: list[AI2LoopRefusal] = []
        self._last_outcome: str | None = None

    # -- public API --------------------------------------------------------

    @property
    def ledger(self) -> AI2RunLedger:
        return self._ledger

    @property
    def archive(self) -> EpisodicRunArchive | None:
        """The runner's CURRENT archive view (appends produce new immutable
        instances; the runner adopts each new instance)."""
        return self._archive

    async def execute_run(
        self,
        run_input: AI2ResearchRunInput,
        market_service: Any,
        *,
        transport: AI2Transport | None = None,
        run_context: RunContext | None = None,
    ) -> AI2LoopOutcome:
        """One bounded loop iteration (at most ONE stage-2 invocation).

        Order of gates (documented): optional RunContext identity binding →
        pre-run duplicate classification (IDENTICAL refuses) → budget
        precheck (exhausted refuses with a BUDGET_EXHAUSTED record) → the
        single AI2Service.run invocation → outcome mapping / record append /
        recovery decision / archive append.
        """
        self._attempts += 1

        # 0) Optional canonical identity binding (RunContext composition).
        if run_context is not None:
            mismatch = self._context_binding_error(run_input, run_context)
            if mismatch is not None:
                return self._refuse(
                    "run_context_mismatch",
                    run_input.run_id,
                    run_input.record_id,
                    mismatch,
                    ledger_status=None,
                )

        # 1) Pre-run duplicate classification against the ledger.
        dup = classify_duplicate(
            self._ledger,
            task=run_input.task,
            input_snapshot_sha256=run_input.input_snapshot_sha256,
        )
        if dup == "DUPLICATE_IDENTICAL":
            # Refuse BEFORE any execution; nothing runs, nothing appends
            # (the identical run is already ledgered — classification only
            # labels, and the refusal is visible in the loop status).
            return self._refuse(
                "duplicate_refused",
                run_input.run_id,
                run_input.record_id,
                "identical (task, input_snapshot) pair already ledgered",
                ledger_status=None,
                duplicate_class=dup,
            )

        # 2) Budget precheck across the session (budget_verdict is inclusive:
        #    usage AT a ceiling is exhausted).
        usage = BudgetUsage(
            provider_invocations=self._invocations,
            iterations=self._iterations,
            wall_seconds=self._wall_seconds,
        )
        if budget_verdict(self._budget, usage) == "BUDGET_EXHAUSTED":
            record = self._build_record(
                run_input,
                status="BUDGET_EXHAUSTED",
                service_status=None,
                trust_state=run_input.declared_trust_state,
                elapsed=0.0,
                duplicate_class=dup,
                execution_label=None,
                recovery=None,
                notes=f"budget_exhausted_pre_run; usage={usage.model_dump()}; "
                f"no stage-2 invocation was performed",
            )
            return self._commit(record, outcome_label="budget_exhausted", ok=False)

        # 3) The single bounded stage-2 invocation; wall time ONLY via the
        #    injected clock. Cancellation propagates; anything else is
        #    contained into an honest record (never a raw exception).
        start = self._clock()
        try:
            result = await self._service.run(run_input.request, market_service, transport=transport)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — contained by contract, mapped below
            elapsed = self._clock() - start
            self._account(invocation=1, iteration=1, wall=elapsed, failed=True)
            record = self._build_record(
                run_input,
                status="FAILED",
                service_status=None,
                trust_state=run_input.declared_trust_state,
                elapsed=elapsed,
                duplicate_class=dup,
                execution_label=None,
                recovery="ESCALATE_FAIL_CLOSED",
                notes=f"runner_internal_error:{type(exc).__name__}; stage-2 outcome unknown",
            )
            return self._commit(
                record, outcome_label="runner_error", ok=False, recovery="ESCALATE_FAIL_CLOSED"
            )
        elapsed = self._clock() - start
        self._account(invocation=1, iteration=1, wall=elapsed, failed=not result.ok)

        # 4) Outcome → record mapping (explicit table; see module docstring).
        service_status = result.status
        provenance = result.provenance
        if service_status not in OUTCOME_STATUS_MAP:
            # Defense in depth: an unknown service label maps to FAILED and
            # stays visible — never silently accepted.
            record = self._build_record(
                run_input,
                status="FAILED",
                service_status=service_status,
                trust_state=run_input.declared_trust_state,
                elapsed=elapsed,
                duplicate_class=dup,
                execution_label=None,
                recovery="ESCALATE_FAIL_CLOSED",
                notes=f"unknown_service_outcome:{service_status}",
            )
            return self._commit(
                record, outcome_label="runner_error", ok=False, recovery="ESCALATE_FAIL_CLOSED"
            )

        execution_label: str | None
        if service_status == "executed_shadow":
            # Synthetic-only outcome: the service attached a TEST ONLY
            # transport; the label is forced to SYNTHETIC_OR_PAPER and the
            # record status is LEDGERED (never COMPLETED) — governed_acceptance
            # can never accept it.
            execution_label = "SYNTHETIC_OR_PAPER"
        elif provenance is not None:
            execution_label = execution_mode(bool(provenance.live_verified))
        else:
            execution_label = None

        recovery: RecoveryDecision | None = None
        if not result.ok:
            gate_failure = service_status == "gated_not_executed"
            recovery = recovery_decision(
                failed_invocations=self._failed_invocations,
                budget=self._budget,
                failure_is_deterministic_gate=gate_failure,
            )

        artifact: AI2EvidenceArtifact | None = None
        if result.ok and provenance is not None:
            artifact = self._build_evidence_artifact(run_input, result, execution_label)

        duplicate_flag = dup == "DUPLICATE_REPEATED_QUESTION"
        mapped_status = OUTCOME_STATUS_MAP[service_status]
        final_status: AI2RunStatus = "DUPLICATE_FLAGGED" if duplicate_flag else mapped_status

        record = self._build_record(
            run_input,
            status=final_status,
            service_status=service_status,
            trust_state=(
                provenance.data_trust_state if provenance is not None else run_input.declared_trust_state
            ),
            elapsed=elapsed,
            duplicate_class=dup,
            execution_label=execution_label,
            recovery=recovery,
            artifact=artifact if final_status == "COMPLETED" else None,
        )
        committed = self._commit(
            record,
            outcome_label=service_status,
            ok=bool(result.ok),
            result=result,
            duplicate_class=dup,
            elapsed=elapsed,
            recovery=recovery,
            execution_label=execution_label,
        )
        if committed.refusal_reason is not None:
            return committed  # ledger conflict: nothing archived

        # 5) Post-run: archive honest evidence (synthetic/paper label carried
        #    through; cutoff from the result provenance; recorded_at from the
        #    injected clock).
        if artifact is not None and self._archive is not None:
            archived = self._archive_evidence(
                run_input, record, artifact, service_status, execution_label
            )
            if committed.record is not None:
                committed = committed.model_copy(update={"archived_evidence": archived})
        return committed

    def loop_status(self) -> AI2LoopStatus:
        """Honest status: runs attempted/executed, refusals, budget remaining."""
        usage = BudgetUsage(
            provider_invocations=self._invocations,
            iterations=self._iterations,
            wall_seconds=self._wall_seconds,
        )
        return AI2LoopStatus(
            runs_attempted=self._attempts,
            stage2_invocations_used=self._invocations,
            iterations_used=self._iterations,
            wall_seconds_used=self._wall_seconds,
            max_provider_invocations=self._budget.max_provider_invocations,
            max_iterations=self._budget.max_iterations,
            max_wall_seconds=self._budget.max_wall_seconds,
            remaining_provider_invocations=max(
                0, self._budget.max_provider_invocations - self._invocations
            ),
            remaining_iterations=max(0, self._budget.max_iterations - self._iterations),
            remaining_wall_seconds=max(
                0.0, float(self._budget.max_wall_seconds) - self._wall_seconds
            ),
            budget_now=budget_verdict(self._budget, usage),
            ledger_size=len(self._ledger.records),
            records_appended=self._records_appended,
            refusals=tuple(self._refusals),
            last_outcome=self._last_outcome,
        )

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _context_binding_error(
        run_input: AI2ResearchRunInput, context: RunContext
    ) -> str | None:
        if run_input.run_id != context.run_id:
            return "run_id_binding"
        if run_input.run_kind != context.run_kind:
            return "run_kind_binding"
        return None

    def _account(self, *, invocation: int, iteration: int, wall: float, failed: bool) -> None:
        self._invocations += invocation
        self._iterations += iteration
        self._wall_seconds += wall
        if failed:
            self._failed_invocations += 1

    def _refuse(
        self,
        reason: str,
        run_id: str,
        record_id: str | None,
        detail: str,
        *,
        ledger_status: AI2RunStatus | None,
        duplicate_class: DuplicateClass | None = None,
    ) -> AI2LoopOutcome:
        self._refusals.append(
            AI2LoopRefusal(
                reason=reason,
                run_id=run_id,
                record_id=record_id,
                detail=detail,
                at_utc=ensure_utc(self._now_utc()),
            )
        )
        self._last_outcome = reason
        return AI2LoopOutcome(
            outcome=reason,
            ok=False,
            ledger_status=ledger_status,
            duplicate_class=duplicate_class,
            refusal_reason=reason,
            notes=detail,
        )

    def _build_evidence_artifact(
        self,
        run_input: AI2ResearchRunInput,
        result: AI2Result,
        execution_label: str | None,
    ) -> AI2EvidenceArtifact | None:
        provenance = result.provenance
        if provenance is None:
            return None
        try:
            created = ensure_utc(datetime.fromisoformat(provenance.created_at_utc))
        except (TypeError, ValueError):
            # The service always stamps a UTC ISO string; if that ever
            # changes we refuse to invent a timestamp — fall back to the
            # injected now and say so.
            created = ensure_utc(self._now_utc())
        return AI2EvidenceArtifact(
            artifact=ArtifactRef(
                artifact_id=f"ai2-{run_input.record_id}",
                kind="ai2_evidence",
                ref=f"ai2-evidence://{run_input.run_id}/{run_input.record_id}",
            ),
            run_id=run_input.run_id,
            input_snapshot_sha256=provenance.input_snapshot_sha256,
            data_trust_state=provenance.data_trust_state,
            created_at_utc=created,
            notes=(
                f"outcome={result.status}; execution_label={execution_label}; "
                "logical reference only (no persistence by the runner)"
            ),
        )

    def _archive_evidence(
        self,
        run_input: AI2ResearchRunInput,
        record: AI2RunRecord,
        artifact: AI2EvidenceArtifact,
        service_status: str,
        execution_label: str | None,
    ) -> bool:
        assert self._archive is not None
        entry = EpisodicRunArtifact(
            entry_id=f"episodic-{record.record_id}",
            run_id=record.run_id,
            run_kind=record.run_kind,
            hypothesis_id=None,
            artifact=artifact.artifact,
            input_snapshot_sha256=artifact.input_snapshot_sha256,
            trust_state=artifact.data_trust_state,
            code_commit=None,
            dataset_version=record.dataset_version,
            policy_version=record.policy_version,
            # Information cutoff = the provenance instant the result was
            # produced at (02 line 142); recorded_at = injected clock.
            information_cutoff_utc=artifact.created_at_utc,
            recorded_at_utc=ensure_utc(self._now_utc()),
            notes=(
                f"execution_label={execution_label}; outcome={service_status}; "
                f"ledger_status={record.status}; synthetic/paper label carried through"
            ),
        )
        try:
            self._archive = self._archive.append(entry)
            return True
        except ValueError as exc:
            self._refusals.append(
                AI2LoopRefusal(
                    reason="archive_append_refused",
                    run_id=run_input.run_id,
                    record_id=run_input.record_id,
                    detail=str(exc),
                    at_utc=ensure_utc(self._now_utc()),
                )
            )
            return False

    def _build_record(
        self,
        run_input: AI2ResearchRunInput,
        *,
        status: AI2RunStatus,
        service_status: str | None,
        trust_state: str,
        elapsed: float,
        duplicate_class: DuplicateClass | None,
        execution_label: str | None,
        recovery: RecoveryDecision | None,
        artifact: AI2EvidenceArtifact | None = None,
        notes: str = "",
    ) -> AI2RunRecord:
        parts = [
            f"outcome={service_status or 'not_executed'}",
            f"duplicate_class={duplicate_class}",
            f"execution_label={execution_label}",
            f"wall_seconds={elapsed:.6f}",
            f"recovery={recovery or '-'}",
        ]
        if status == "LEDGERED":
            parts.append("synthetic_shadow_run_never_completed")
        if notes:
            parts.append(notes)
        if run_input.notes:
            parts.append(f"caller_notes={run_input.notes}")
        return AI2RunRecord(
            record_id=run_input.record_id,
            run_id=run_input.run_id,
            run_kind=run_input.run_kind,
            policy_version=run_input.policy_version,
            task=run_input.task,
            input_snapshot_sha256=run_input.input_snapshot_sha256,
            trust_state=trust_state,
            dataset_version=run_input.dataset_version,
            approval_state=run_input.approval_state,
            approved_by=run_input.approved_by,
            status=status,
            artifact=artifact,
            recorded_at_utc=ensure_utc(self._now_utc()),
            notes="; ".join(parts),
        )

    def _commit(
        self,
        record: AI2RunRecord,
        *,
        outcome_label: str,
        ok: bool,
        result: AI2Result | None = None,
        duplicate_class: DuplicateClass | None = None,
        elapsed: float = 0.0,
        recovery: RecoveryDecision | None = None,
        execution_label: str | None = None,
    ) -> AI2LoopOutcome:
        ledger, appended, conflict = append_record_idempotent(self._ledger, record)
        if conflict:
            return self._refuse(
                "ledger_record_conflict",
                record.run_id,
                record.record_id,
                "conflicting reuse of record_id; ledger unchanged",
                ledger_status=None,
                duplicate_class=duplicate_class,
            )
        self._ledger = ledger
        if appended:
            self._records_appended += 1
        self._last_outcome = outcome_label
        return AI2LoopOutcome(
            outcome=outcome_label,
            ok=ok,
            ledger_status=record.status,
            record=record,
            result=result,
            duplicate_class=duplicate_class,
            elapsed_wall_seconds=elapsed,
            recovery=recovery,
            execution_label=execution_label,
            archived_evidence=False,
        )
