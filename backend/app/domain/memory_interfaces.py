"""Memory interface contracts for RADAR BOURSE (AI-1 memory interfaces).

Corpus loci (2026-10-02 amendment corpus, byte-verified):
- 02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE §Memory: "Run Context = execution
  state. Episodic Memory = immutable research evidence. Semantic Memory =
  curated, versioned knowledge."
- 03_AI_GOVERNANCE_BOUNDARIES §Memory: "Episodic research evidence is
  immutable. Semantic learning is versioned and curated. No memory operation
  may silently modify production logic."
- D-AI-28 (05 register): episodic memory is immutable evidence; semantic
  memory is curated/versioned.
- 02_PRODUCT… rule 12: "Every agent/tool/handoff/artifact/memory operation is
  traceable to run_id."

Scope note: AI-1 delivers memory *interfaces* (contracts + deterministic
in-memory append/version semantics). The AI-3 block ("Research Memory",
02_EXECUTION_ROADMAP lines 83–85) delivers the episodic/semantic memory
system itself; persistence is therefore intentionally NOT implemented here.

Contract/domain only: frozen records, deterministic, clock-free (timestamps
passed in), no I/O, no network, no LLM. The only operations this module can
express are memory-scoped (closed ``MemoryOperationKind`` set) — no state or
field can represent a production mutation (03 §Memory).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc

EpisodicKind = Literal[
    "RESEARCH_RUN_EVIDENCE",
    "EVALUATION_ARTIFACT",
    "OBSERVATION_RECORD",
]
CurationBasis = Literal["DETERMINISTIC_RULE", "HUMAN_REVIEW"]
SemanticStatus = Literal["ACTIVE", "SUPERSEDED", "RETIRED"]

#: Closed operation set (03 §Memory): memory operations are appends,
#: registrations and curated supersessions — nothing else, and in particular
#: no operation kind that could express a production change exists.
MemoryOperationKind = Literal[
    "APPEND_EPISODIC",
    "REGISTER_SEMANTIC",
    "SUPERSEDE_SEMANTIC",
]


class EpisodicMemoryRecord(BaseModel):
    """Immutable episodic record of research evidence (D-AI-28).

    Frozen by construction; the accompanying :class:`EpisodicMemoryLog`
    exposes append/get/history only — no update or delete operation exists,
    so immutability is structural, not conventional.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=128)
    memory_kind: EpisodicKind
    stored_at_utc: datetime
    payload_ref: str = Field(min_length=1, max_length=512)
    payload_sha256: str | None = None
    summary: str = Field(default="", max_length=1000)
    notes: str = ""

    @field_validator("stored_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("payload_sha256")
    @classmethod
    def _sha256_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("payload_sha256_must_be_64_hex")
        return v.lower()


class EpisodicMemoryLog:
    """Append-only in-memory episodic log (deterministic, no persistence).

    Semantics mirror the P0-AMD-1 ``SourceRegistry`` discipline:
    - a NEW ``record_id`` appends and returns the new log;
    - re-appending a byte-identical record is an idempotent no-op;
    - re-appending the same ``record_id`` with different content is a
      conflict and raises ``ValueError`` (history is never rewritten).
    """

    def __init__(self, records: tuple[EpisodicMemoryRecord, ...] = ()) -> None:
        self._records: tuple[EpisodicMemoryRecord, ...] = records

    @property
    def records(self) -> tuple[EpisodicMemoryRecord, ...]:
        return self._records

    def get(self, record_id: str) -> EpisodicMemoryRecord | None:
        for r in self._records:
            if r.record_id == record_id:
                return r
        return None

    def history_for_run(self, run_id: str) -> tuple[EpisodicMemoryRecord, ...]:
        """All episodic records bound to one governed run (arch rule 12)."""
        return tuple(r for r in self._records if r.run_id == run_id)

    def append(self, record: EpisodicMemoryRecord) -> "EpisodicMemoryLog":
        existing = self.get(record.record_id)
        if existing is not None:
            if existing == record:
                return self  # idempotent re-append
            raise ValueError("episodic_record_conflict")
        return EpisodicMemoryLog(self._records + (record,))


class SemanticMemoryEntry(BaseModel):
    """Curated, versioned semantic-memory entry (D-AI-28).

    Curation must name its basis: a deterministic rule or a human reviewer
    (mirrors the explicit-resolution rule of ``EvidenceConflict``). Version 1
    supersedes nothing; any later version must name the entry version it
    supersedes (02_PRODUCT… §Memory: semantic memory is curated/versioned).
    """

    model_config = ConfigDict(frozen=True)

    entry_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    version: int = Field(ge=1)
    supersedes_version: int | None = None
    statement: str = Field(min_length=1, max_length=2000)
    knowledge_ref: str = Field(min_length=1, max_length=512)
    curated_by: str = Field(min_length=1, max_length=128)
    curation_basis: CurationBasis
    status: SemanticStatus = "ACTIVE"
    created_at_utc: datetime
    run_id: str | None = None
    notes: str = ""

    @field_validator("created_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _version_chain_consistency(self) -> "SemanticMemoryEntry":
        if self.version == 1 and self.supersedes_version is not None:
            raise ValueError("version_one_must_not_supersede")
        if self.version > 1:
            if self.supersedes_version is None:
                raise ValueError("later_version_requires_superseded_version")
            if self.supersedes_version >= self.version:
                raise ValueError("superseded_version_must_be_earlier")
        return self


class SemanticMemoryStore:
    """Versioned in-memory semantic store (deterministic, no persistence).

    One active version per ``entry_id``; supersession is explicit and
    append-only. History is never rewritten.
    """

    def __init__(self, entries: tuple[SemanticMemoryEntry, ...] = ()) -> None:
        self._entries: tuple[SemanticMemoryEntry, ...] = entries

    @property
    def entries(self) -> tuple[SemanticMemoryEntry, ...]:
        return self._entries

    def latest(self, entry_id: str) -> SemanticMemoryEntry | None:
        best: SemanticMemoryEntry | None = None
        for e in self._entries:
            if e.entry_id == entry_id and (best is None or e.version > best.version):
                best = e
        return best

    def history(self, entry_id: str) -> tuple[SemanticMemoryEntry, ...]:
        """All versions of an entry, oldest first."""
        return tuple(
            sorted(
                (e for e in self._entries if e.entry_id == entry_id),
                key=lambda e: e.version,
            )
        )

    def register(self, entry: SemanticMemoryEntry) -> "SemanticMemoryStore":
        current = self.latest(entry.entry_id)
        if current is not None:
            if current.version >= entry.version:
                raise ValueError("semantic_entry_version_not_increasing")
            if current.status != "ACTIVE":
                raise ValueError("cannot_extend_non_active_semantic_entry")
            if entry.supersedes_version != current.version:
                raise ValueError("semantic_supersession_parent_mismatch")
            superseded = SemanticMemoryEntry(
                **{**current.model_dump(), "status": "SUPERSEDED"}
            )
            # Replace ONLY the current active version with its superseded
            # copy; every older version stays in history untouched.
            kept = tuple(
                e
                for e in self._entries
                if not (e.entry_id == entry.entry_id and e.version == current.version)
            )
            return SemanticMemoryStore(kept + (superseded, entry))
        if entry.version != 1:
            raise ValueError("first_registered_version_must_be_one")
        return SemanticMemoryStore(self._entries + (entry,))
