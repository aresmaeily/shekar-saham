"""Canonical run-governance contracts for RADAR BOURSE (AI-1 governed orchestration).

Corpus loci (2026-10-02 amendment corpus, byte-verified):
- 00_OWNER_ROADMAP_DECISION §Binding principles 9: "One RunContext /
  RunProvenance is minted per governed research run."
- 02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE rule 10: "One canonical
  RunContext/RunProvenance binds each governed run." Rule 12: "Every
  agent/tool/handoff/artifact/memory operation is traceable to run_id."
- 03_AI_GOVERNANCE_BOUNDARIES §Run provenance: every governed run binds, as
  applicable, run_id, parent_run_id, hypothesis_id, dataset_version,
  code_commit, model_version, prompt_version, evaluation_version,
  policy_version, approval_state, timestamps, artifact references.
  "Missing required provenance blocks governed acceptance."
- 03 §Autonomy levels: L0 Observer, L1 Assistant, L2 Bounded Research Agent,
  L3 Orchestrator, L4 Consequential Action — human-controlled only. "Agents
  cannot silently increase their autonomy level."
- D-AI-22 (05 register): governance-grade RunContext/RunProvenance precedes
  Multi-Agent scale.

Contract/domain only: frozen records, deterministic, clock-free (every
timestamp is passed in as an argument), no I/O, no network, no LLM, no
scheduler. Financial truth is untouched (D-AI-19). This module defines
identity/policy records only; it computes no market value.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc

ApprovalState = Literal[
    "NOT_REQUIRED",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "ESCALATED",
]

AutonomyLevel = Literal["L0", "L1", "L2", "L3", "L4"]

#: Ordering used by the autonomy-ceiling guard (03 §Autonomy levels).
_AUTONOMY_ORDER: dict[str, int] = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}

_RUN_KIND_PATTERN = r"^[A-Z][A-Z0-9_]*$"


class ArtifactRef(BaseModel):
    """Reference to a large intermediate result exchanged by artifact
    reference (D-AI-23; 02_PRODUCT… rule 9). The ref itself is small;
    content lives outside the context record."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    kind: str = Field(min_length=1, max_length=64)
    ref: str = Field(min_length=1, max_length=512)
    sha256: str | None = None

    @field_validator("sha256")
    @classmethod
    def _sha256_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("artifact_sha256_must_be_64_hex")
        return v.lower()


class RunContext(BaseModel):
    """Canonical identity of one governed run (00 principle 9; arch rule 10).

    Frozen at creation: a governed run's identity is immutable history.
    ``autonomy_level`` records the level under which the run was authorized;
    exceeding a declared ceiling is refused by :func:`assert_autonomy_permitted`
    (03 §Autonomy levels: agents cannot silently increase autonomy).
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    parent_run_id: str | None = None
    run_kind: str = Field(min_length=1, max_length=64, pattern=_RUN_KIND_PATTERN)
    autonomy_level: AutonomyLevel = "L0"
    approval_state: ApprovalState = "NOT_REQUIRED"
    approved_by: str | None = None
    approval_ref: str | None = None
    policy_version: str = Field(min_length=1)
    created_at_utc: datetime
    artifacts: tuple[ArtifactRef, ...] = ()
    notes: str = ""

    @field_validator("created_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _l4_requires_human_approval(self) -> "RunContext":
        if self.autonomy_level == "L4":
            if self.approval_state != "APPROVED" or not self.approved_by or not self.approval_ref:
                raise ValueError("l4_requires_recorded_human_approval")
        if self.approval_state == "APPROVED" and not self.approved_by:
            raise ValueError("approved_state_requires_approver")
        artifact_ids = [a.artifact_id for a in self.artifacts]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("artifact_ids_duplicates")
        return self


class RunProvenance(BaseModel):
    """Provenance bindings for one governed run (03 §Run provenance).

    Fields the run did not use stay explicitly ``None`` — never invented,
    never defaulted (P0-AMD-1 sentinel discipline). ``started_at_utc`` and
    ``finished_at_utc`` are both-or-none.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    parent_run_id: str | None = None
    hypothesis_id: str | None = None
    dataset_version: str | None = None
    code_commit: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    evaluation_version: str | None = None
    policy_version: str | None = None
    approval_state: ApprovalState = "NOT_REQUIRED"
    started_at_utc: datetime | None = None
    finished_at_utc: datetime | None = None
    artifact_refs: tuple[str, ...] = ()

    @field_validator("started_at_utc", "finished_at_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("code_commit")
    @classmethod
    def _commit_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) != 40 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("code_commit_must_be_40_hex")
        return v.lower()

    @field_validator("artifact_refs")
    @classmethod
    def _distinct_refs(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("artifact_refs_duplicates")
        return v

    @model_validator(mode="after")
    def _interval_consistency(self) -> "RunProvenance":
        if (self.started_at_utc is None) != (self.finished_at_utc is None):
            raise ValueError("started_and_finished_both_or_none")
        if (
            self.started_at_utc is not None
            and self.finished_at_utc is not None
            and self.finished_at_utc < self.started_at_utc
        ):
            raise ValueError("finished_before_started")
        return self


def assert_autonomy_permitted(context: RunContext, ceiling: AutonomyLevel) -> None:
    """Deterministic autonomy-ceiling guard (03 §Autonomy levels).

    Raises ``ValueError`` when the run's recorded autonomy level exceeds the
    declared ceiling. A governor/policy gate calls this before delegating;
    it never mutates the context.
    """
    if _AUTONOMY_ORDER[context.autonomy_level] > _AUTONOMY_ORDER[ceiling]:
        raise ValueError("autonomy_level_exceeds_declared_ceiling")


def bind_provenance(context: RunContext, provenance: RunProvenance) -> None:
    """Deterministic run-id binding (arch rule 10/12).

    The provenance record must belong to the same run as the context.
    Raises ``ValueError`` on mismatch; returns nothing on success.
    """
    if provenance.run_id != context.run_id:
        raise ValueError("provenance_run_id_mismatch")
    if (
        context.parent_run_id is not None
        and provenance.parent_run_id is not None
        and provenance.parent_run_id != context.parent_run_id
    ):
        raise ValueError("provenance_parent_run_id_mismatch")


#: Fields every governed run must be able to evidence before its results are
#: accepted (03 §Run provenance: "Missing required provenance blocks governed
#: acceptance"). Callers may extend the requirement per run kind; they may
#: not shrink it.
_BASE_REQUIRED_PROVENANCE: tuple[str, ...] = (
    "policy_version",
    "started_at_utc",
    "finished_at_utc",
)


def missing_required_provenance(
    context: RunContext,
    provenance: RunProvenance,
    *,
    additionally_required: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return the names of required provenance bindings that are missing.

    Deterministic and side-effect free. A non-empty result BLOCKS governed
    acceptance of the run's outputs (03 §Run provenance). The base set is
    fixed by this module; ``additionally_required`` can demand run-kind
    specific fields (e.g. ``dataset_version`` for evaluations).
    """
    try:
        bind_provenance(context, provenance)
    except ValueError:
        return ("run_id_binding",)
    missing: list[str] = []
    values = {
        "policy_version": provenance.policy_version,
        "started_at_utc": provenance.started_at_utc,
        "finished_at_utc": provenance.finished_at_utc,
        "hypothesis_id": provenance.hypothesis_id,
        "dataset_version": provenance.dataset_version,
        "code_commit": provenance.code_commit,
        "model_version": provenance.model_version,
        "prompt_version": provenance.prompt_version,
        "evaluation_version": provenance.evaluation_version,
    }
    for name in _BASE_REQUIRED_PROVENANCE + additionally_required:
        if values.get(name) is None:
            missing.append(name)
    return tuple(missing)


def provenance_complete(
    context: RunContext,
    provenance: RunProvenance,
    *,
    additionally_required: tuple[str, ...] = (),
) -> bool:
    """True when no required provenance binding is missing."""
    return (
        len(
            missing_required_provenance(
                context, provenance, additionally_required=additionally_required
            )
        )
        == 0
    )
