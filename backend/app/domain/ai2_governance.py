"""AI-2 loop-hardening governance contracts for RADAR BOURSE (AI2-F).

Corpus locus (2026-10-02 amendment corpus, byte-verified):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 44–53 (AI-2 — Research
  Loop Hardening / MVRL): "Required: immutable run identity - provenance -
  budget/time/iteration limits - evidence artifacts - duplicate detection -
  failure/recovery - invalidation - human approval state."
- 02 lines 10–11 / 201–202: G2 blocks all real-data AI-2 execution; before
  G2 only bounded design/schema/synthetic work is allowed. These contracts
  are exactly that class — they enable NOTHING by themselves.
- D-AI-22 (run provenance precedes scale), D-AI-28 (episodic immutable /
  semantic curated), D-AI-40 (gates preserved), D-AI-41 (capability is not
  implementation evidence).

Relationship to the existing AI-2 Category A service
(`backend/app/services/ai2_service.py`, AI2-A..AI2-E): the service is NOT
modified. These are the run-governance contracts that wrap, label, ledger,
budget, invalidate and gate AI-2 runs. They reuse the AI1-GC canonical run
identity (`run_governance.py`) so every AI-2 run is traceable to one
RunContext (02_PRODUCT… rules 10/12). Composition is exercised at test
level; the service remains default-off (AI2_ENABLED=0) and G2-blocked.

Contract/domain only: frozen records, deterministic, clock-free (elapsed
time, timestamps always passed in), no I/O, no network, no LLM, no scheduler.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.run_governance import (
    ApprovalState,
    ArtifactRef,
    RunContext,
    provenance_complete,
)

AI2RunStatus = Literal[
    "LEDGERED",
    "DUPLICATE_FLAGGED",
    "BUDGET_EXHAUSTED",
    "INVALIDATED",
    "GATED_NOT_EXECUTED",
    "FAILED",
    "COMPLETED",
]

DuplicateClass = Literal[
    "NEW",
    "DUPLICATE_IDENTICAL",
    "DUPLICATE_REPEATED_QUESTION",
]


# ---------------------------------------------------------------------------
# Budget / time / iteration limits (02 line 51)
# ---------------------------------------------------------------------------


class AI2BudgetSpec(BaseModel):
    """Immutable resource ceilings for one AI-2 research run.

    Structural bounds mirror the existing hard ceilings of the monitoring
    and provider contracts; a budget cannot be unbounded by construction.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    max_provider_invocations: int = Field(ge=1, le=16)
    max_iterations: int = Field(ge=1, le=64)
    max_wall_seconds: int = Field(ge=1, le=86400)


class BudgetUsage(BaseModel):
    """Observable usage counters of a run (deterministic inputs only)."""

    model_config = ConfigDict(frozen=True)

    provider_invocations: int = Field(ge=0)
    iterations: int = Field(ge=0)
    wall_seconds: float = Field(ge=0.0)


BudgetVerdict = Literal["WITHIN_BUDGET", "BUDGET_EXHAUSTED"]


def budget_verdict(spec: AI2BudgetSpec, usage: BudgetUsage) -> BudgetVerdict:
    """Deterministic budget decision (02 line 51; D-AI-24 bounded resources).

    Clock-free: ``usage.wall_seconds`` is measured by the caller and passed
    in; this function never reads a clock.
    """
    if (
        usage.provider_invocations >= spec.max_provider_invocations
        or usage.iterations >= spec.max_iterations
        or usage.wall_seconds >= spec.max_wall_seconds
    ):
        return "BUDGET_EXHAUSTED"
    return "WITHIN_BUDGET"


# ---------------------------------------------------------------------------
# Evidence artifacts (02 line 52)
# ---------------------------------------------------------------------------


class AI2EvidenceArtifact(BaseModel):
    """Evidence-artifact binding for one AI-2 run.

    Large intermediate results are exchanged by artifact reference
    (D-AI-23); the artifact records the exact input snapshot it was
    produced from and the data-trust state observed at production time.
    """

    model_config = ConfigDict(frozen=True)

    artifact: ArtifactRef
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=128)
    input_snapshot_sha256: str = Field(min_length=64, max_length=64)
    data_trust_state: str = Field(min_length=1, max_length=64)
    created_at_utc: datetime
    notes: str = ""

    @field_validator("created_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("input_snapshot_sha256")
    @classmethod
    def _hex64(cls, v: str) -> str:
        if any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("input_snapshot_sha256_must_be_hex")
        return v.lower()


# ---------------------------------------------------------------------------
# Recovery (02 line 52 "failure/recovery")
# ---------------------------------------------------------------------------

RecoveryDecision = Literal["RETRY_WITHIN_BUDGET", "ESCALATE_FAIL_CLOSED"]


def recovery_decision(
    *,
    failed_invocations: int,
    budget: AI2BudgetSpec,
    failure_is_deterministic_gate: bool,
) -> RecoveryDecision:
    """Deterministic recovery classification for a failed AI-2 step.

    Policy (02 line 52; fail-closed governance):
    - a deterministic-gate refusal (configuration/trust/G2) is NEVER retried;
    - provider-style failures may retry only while the invocation budget
      allows it (bounded retries; ceiling inclusive).
    """
    if failure_is_deterministic_gate:
        return "ESCALATE_FAIL_CLOSED"
    if failed_invocations + 1 > budget.max_provider_invocations:
        return "ESCALATE_FAIL_CLOSED"
    return "RETRY_WITHIN_BUDGET"


# ---------------------------------------------------------------------------
# Invalidation (02 line 53)
# ---------------------------------------------------------------------------


class AI2InvalidationRule(BaseModel):
    """Deterministic invalidation of a prior AI-2 result.

    A stored AI-2 outcome is invalidated when the trust state it was
    produced under no longer holds, or when the deterministic input
    snapshot version it consumed was superseded. Invalidation is a
    LABEL, never a deletion: prior records remain immutable history.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    reason_codes: tuple[
        Literal["TRUST_STATE_CHANGED", "TRUST_DOWNGRADED", "DATASET_SUPERSEDED", "EXPLICIT_OWNER"],
        ...,
    ]
    declared_by: str = Field(min_length=1, max_length=128)
    declared_at_utc: datetime

    @field_validator("declared_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("reason_codes")
    @classmethod
    def _distinct(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("reason_codes_duplicates")
        return v

    @model_validator(mode="after")
    def _non_empty(self) -> "AI2InvalidationRule":
        if not self.reason_codes:
            raise ValueError("invalidation_requires_reason")
        return self


def invalidates(
    previous_trust_state: str,
    current_trust_state: str,
    previous_dataset_version: str | None,
    current_dataset_version: str | None,
) -> tuple[str, ...]:
    """Deterministic invalidation evaluation between two observation points.

    Returns the fired reason codes (empty tuple = still valid). Trust-state
    comparison is exact-string and deterministic; a ``None`` dataset version
    can never be silently treated as equal to a named version.
    """
    reasons: list[str] = []
    if previous_trust_state != current_trust_state:
        reasons.append("TRUST_STATE_CHANGED")
    _TRUST_ORDER = {"live": 3, "stale": 2, "mock": 1, "synthetic": 1, "unavailable": 0}
    if (
        _TRUST_ORDER.get(current_trust_state, -1) < _TRUST_ORDER.get(previous_trust_state, -1)
        and current_trust_state != previous_trust_state
    ):
        reasons.append("TRUST_DOWNGRADED")
    if (
        previous_dataset_version is not None
        and current_dataset_version is not None
        and previous_dataset_version != current_dataset_version
    ):
        reasons.append("DATASET_SUPERSEDED")
    return tuple(reasons)


# ---------------------------------------------------------------------------
# Immutable run record + duplicate detection (02 lines 50, 52)
# ---------------------------------------------------------------------------


class AI2RunRecord(BaseModel):
    """Immutable ledger record of one AI-2 run (02 lines 50–53).

    Binds: the canonical run identity (RunContext fields), the run's
    provenance essentials, the human approval state, and the outcome
    status. Records are append-only ledger entries — invalidation is a
    status transition recorded as a NEW record, never a rewrite.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=128)
    run_kind: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    policy_version: str = Field(min_length=1)
    task: str = Field(min_length=1, max_length=64)
    input_snapshot_sha256: str = Field(min_length=64, max_length=64)
    trust_state: str = Field(min_length=1, max_length=64)
    dataset_version: str | None = None
    approval_state: ApprovalState
    status: AI2RunStatus
    artifact: AI2EvidenceArtifact | None = None
    recorded_at_utc: datetime
    notes: str = ""

    @field_validator("recorded_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("input_snapshot_sha256")
    @classmethod
    def _hex64(cls, v: str) -> str:
        if any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("input_snapshot_sha256_must_be_hex")
        return v.lower()

    @field_validator("task")
    @classmethod
    def _known_task(cls, v: str) -> str:
        if v not in {"assistant", "analyst", "optimizer", "research", "strategy", "risk"}:
            raise ValueError("unknown_ai2_task")
        return v

    @model_validator(mode="after")
    def _status_consistency(self) -> "AI2RunRecord":
        if self.status == "COMPLETED" and self.artifact is None:
            raise ValueError("completed_run_requires_evidence_artifact")
        if self.status in {"LEDGERED", "DUPLICATE_FLAGGED"} and self.artifact is not None:
            raise ValueError("non_terminal_status_cannot_carry_artifact")
        return self


def classify_duplicate(
    ledger: "AI2RunLedger",
    *,
    task: str,
    input_snapshot_sha256: str,
) -> DuplicateClass:
    """Deterministic duplicate classification against the ledger.

    - an identical (task, input snapshot) pair already ledgered is
      ``DUPLICATE_IDENTICAL``;
    - the same question task with a different snapshot is
      ``DUPLICATE_REPEATED_QUESTION`` (allowed, but visible);
    - otherwise ``NEW``. Detection only LABELS; it never blocks ledgering.
    """
    for rec in ledger.records:
        if rec.task != task:
            continue
        if rec.input_snapshot_sha256 == input_snapshot_sha256:
            return "DUPLICATE_IDENTICAL"
        return "DUPLICATE_REPEATED_QUESTION"
    return "NEW"


class AI2RunLedger:
    """Append-only in-memory AI-2 run ledger (duplicate detection; 02:52).

    Same discipline as the episodic log: NEW record ids append; byte-identical
    re-ledgering is an idempotent no-op; conflicting re-use of a record_id is
    rejected. No update or delete path exists — invalidation appends a new
    record with status ``INVALIDATED``.
    """

    def __init__(self, records: tuple[AI2RunRecord, ...] = ()) -> None:
        self._records: tuple[AI2RunRecord, ...] = records

    @property
    def records(self) -> tuple[AI2RunRecord, ...]:
        return self._records

    def get(self, record_id: str) -> AI2RunRecord | None:
        for r in self._records:
            if r.record_id == record_id:
                return r
        return None

    def history_for_run(self, run_id: str) -> tuple[AI2RunRecord, ...]:
        return tuple(r for r in self._records if r.run_id == run_id)

    def append(self, record: AI2RunRecord) -> "AI2RunLedger":
        existing = self.get(record.record_id)
        if existing is not None:
            if existing == record:
                return self
            raise ValueError("ai2_ledger_record_conflict")
        return AI2RunLedger(self._records + (record,))


# ---------------------------------------------------------------------------
# Governed acceptance (02 line 53 "human approval state" + 03 §Run provenance)
# ---------------------------------------------------------------------------


def governed_acceptance(
    context: RunContext,
    record: AI2RunRecord,
    *,
    additionally_required_provenance: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Deterministic acceptance gate for an AI-2 run's outputs.

    Returns the missing/blocking items (empty = accepted). Blocks when:
    - the record's run identity does not bind to the context;
    - required provenance (03 §Run provenance) is incomplete;
    - the run reached COMPLETED without a recorded approval state when the
      context demanded one (APPROVED requires an approver — enforced by the
      RunContext model itself).
    """
    blocking: list[str] = []
    if record.run_id != context.run_id:
        blocking.append("run_id_binding")
    if record.run_kind != context.run_kind:
        blocking.append("run_kind_binding")
    if not provenance_complete(
        context,
        _minimal_provenance(context, record),
        additionally_required=additionally_required_provenance,
    ):
        blocking.append("provenance_incomplete")
    if record.approval_state in {"PENDING", "ESCALATED"}:
        blocking.append("human_approval_outstanding")
    if record.approval_state == "REJECTED":
        blocking.append("human_approval_rejected")
    return tuple(blocking)


def _minimal_provenance(context: RunContext, record: AI2RunRecord):
    """Project a record onto the 03 §Run provenance completeness checker."""
    from app.domain.run_governance import RunProvenance

    return RunProvenance(
        run_id=record.run_id,
        policy_version=record.policy_version,
        started_at_utc=record.recorded_at_utc,
        finished_at_utc=record.recorded_at_utc,
        dataset_version=record.dataset_version,
    )
