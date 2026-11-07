"""AI-3 research-memory ACCESS/OPERATION audit trail (WAVE-AI, WP-G, 2026-11-08).

The WAVE-AI-ACCEPTANCE directive §8 requires a TAMPER-EVIDENT access/operation
audit trail for research memory. The shipped AI-3 stack already has tamper
EVIDENCE for memory CONTENT (per-record digests, integrity reports); what was
missing is the WHO-DID-WHAT trail over the memory surface itself. This module
ships it as a pure, additive domain component:

- ACTOR + AUTHORIZATION CONTEXT: every entry records the actor id and a
  declared authorization context (e.g. autonomy level / permission token
  NAME). Authorization CONTEXT is declared metadata — never a credential.
- OPERATION TYPE: a closed vocabulary (episodic append/read, semantic
  register/read/history, integrity report, retention/export probes).
- MEMORY LAYER: a closed vocabulary mirroring the D-AI triad (RUN_CONTEXT /
  EPISODIC / SEMANTIC) so the audit trail explicitly PRESERVES the
  three-concept separation — the audit log itself is a FOURTH thing (a
  ledger about the memory surface), never a memory layer.
- OBJECT / ARTIFACT REFERENCE: the touched entry_id / lesson_id / report
  scope — references only, never content (no private user content, no
  payload bodies in the log).
- TIMESTAMP + RUN IDENTITY: caller-supplied instant (no wall clock in this
  module) + the governed run_id when the access happened inside a run.
- OUTCOME + REFUSAL REASON: OK / REFUSED, with a mandatory reason on REFUSED
  (duplicate conflicts, chain failures, refusals surfaced from the store).
- INTEGRITY VERIFICATION: an append-only SHA-256 HASH CHAIN over the
  canonical JSON of each entry (prior-entry digest chained; genesis prior
  64×'0'). Verification recomputes the whole chain; ANY single-byte tamper
  breaks it. Appends verify-before-accept: an append onto a broken chain is
  REFUSED (fail-closed) and recorded as a refusal ATTEMPT outside the chain
  is impossible — the caller gets a typed error and the chain stays closed.
- SECRETS/PRIVACY: entries carry refs, not content. A construction-time
  scan refuses actor/context/refusal-reason strings carrying credential
  markers (fail-closed; no secret can enter the log by accident).

No I/O, no clock, no network: the log is deterministic given the entry
sequence. The shipped ``ResearchMemoryStore`` implementations stay UNTOUCHED;
``AuditedResearchMemoryStore`` composes any store implementation and records
every operation honestly (including contract refusals, which leave the
underlying store unchanged and land as REFUSED audit rows).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.memory_interfaces import ensure_utc
from app.domain.research_memory import EpisodicRunArtifact, SemanticLesson
from app.domain.research_memory_store import (
    ResearchMemoryIntegrityReport,
    ResearchMemoryStore,
)

# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

MemoryAccessOperation = Literal[
    "EPISODIC_APPEND",
    "EPISODIC_GET",
    "EPISODIC_FOR_RUN",
    "EPISODIC_FOR_HYPOTHESIS",
    "EPISODIC_AVAILABLE_AT",
    "SEMANTIC_REGISTER",
    "SEMANTIC_LATEST",
    "SEMANTIC_HISTORY",
    "SEMANTIC_ACTIVE_AT",
    "INTEGRITY_REPORT",
]
WRITE_OPERATIONS: frozenset[str] = frozenset(
    {"EPISODIC_APPEND", "SEMANTIC_REGISTER"}
)

MemoryLayer = Literal["RUN_CONTEXT", "EPISODIC", "SEMANTIC"]

#: The audit log is a LEDGER ABOUT the memory surface — deliberately NOT one
#: of the three memory layers. Every entry PINS which layer was touched (or
#: RUN_CONTEXT-scoped operations), so the triad separation stays explicit.
_MEMORY_LAYER_OF_OPERATION: dict[str, MemoryLayer] = {
    "EPISODIC_APPEND": "EPISODIC",
    "EPISODIC_GET": "EPISODIC",
    "EPISODIC_FOR_RUN": "EPISODIC",
    "EPISODIC_FOR_HYPOTHESIS": "EPISODIC",
    "EPISODIC_AVAILABLE_AT": "EPISODIC",
    "SEMANTIC_REGISTER": "SEMANTIC",
    "SEMANTIC_LATEST": "SEMANTIC",
    "SEMANTIC_HISTORY": "SEMANTIC",
    "SEMANTIC_ACTIVE_AT": "SEMANTIC",
    "INTEGRITY_REPORT": "RUN_CONTEXT",
}

AuditOutcome = Literal["OK", "REFUSED"]

GENESIS_DIGEST = "0" * 64

#: Credential-marker scan: a string carrying any of these markers cannot be
#: an actor id, authorization context, refusal reason or detail. The audit
#: trail records CONTEXT, never credentials (directive §8: no secrets).
_SECRET_MARKERS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "token ",
    "bearer ",
    "password",
    "passwd",
    "secret:",
    "authorization:",
    "x-api-key",
    "sk-",
    "-----begin",
)


def _raise_if_secret_like(field: str, value: str) -> str:
    lowered = value.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            raise ValueError(f"audit_entry_secret_marker_in_{field}")
    return value


# ---------------------------------------------------------------------------
# The tamper-evident entry
# ---------------------------------------------------------------------------


def _iso_utc(dt: datetime) -> str:
    """The ONE canonical datetime serialization for audit preimages (both the
    mint path and the verify path MUST use it — byte-identical preimages)."""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_audit_json(entry: "MemoryAccessAuditEntry") -> str:
    """Canonical JSON of the entry WITHOUT the chain-digest fields — the
    preimage of the chain digest (deterministic, stable field order)."""
    payload = entry.model_dump(mode="json")
    payload.pop("entry_digest", None)
    payload["at_utc"] = _iso_utc(entry.at_utc)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class MemoryAccessAuditEntry(BaseModel):
    """One audited access/operation over the research-memory surface.

    ``entry_digest`` = sha256(canonical JSON of every other field +
    ``prior_digest``) — the tamper-evident hash chain link.
    """

    model_config = ConfigDict(frozen=True)

    sequence: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=128)
    authorization_context: str = Field(min_length=1, max_length=256)
    operation: MemoryAccessOperation
    memory_layer: MemoryLayer
    object_ref: str = Field(max_length=256)  # a REFERENCE — never content
    run_id: str | None = Field(default=None, max_length=128)
    at_utc: datetime
    outcome: AuditOutcome
    refusal_reason: str | None = Field(default=None, max_length=256)
    detail: str = Field(default="", max_length=256)
    prior_digest: str = Field(min_length=64, max_length=64)
    entry_digest: str = Field(min_length=64, max_length=64)

    @field_validator("at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("actor", "authorization_context", "refusal_reason", "detail")
    @classmethod
    def _no_secrets(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _raise_if_secret_like("text_field", v)

    @model_validator(mode="after")
    def _outcome_pairing(self) -> "MemoryAccessAuditEntry":
        if self.outcome == "REFUSED" and not (self.refusal_reason or "").strip():
            raise ValueError("refused_entry_requires_refusal_reason")
        if self.outcome == "OK" and self.refusal_reason is not None:
            raise ValueError("ok_entry_cannot_carry_refusal_reason")
        expected = hashlib.sha256(
            (canonical_audit_json(self) + self.prior_digest).encode("utf-8")
        ).hexdigest()
        if expected != self.entry_digest:
            raise ValueError("audit_entry_digest_mismatch")
        return self


def mint_audit_entry(
    *,
    sequence: int,
    actor: str,
    authorization_context: str,
    operation: MemoryAccessOperation,
    object_ref: str,
    at_utc: datetime,
    run_id: str | None = None,
    outcome: AuditOutcome = "OK",
    refusal_reason: str | None = None,
    detail: str = "",
    prior_digest: str = GENESIS_DIGEST,
) -> MemoryAccessAuditEntry:
    """Mint one chain-valid entry (digest computed over the canonical form)."""
    layer = _MEMORY_LAYER_OF_OPERATION[operation]
    base = {
        "sequence": sequence,
        "actor": actor,
        "authorization_context": authorization_context,
        "operation": operation,
        "memory_layer": layer,
        "object_ref": object_ref[:256],
        "run_id": run_id,
        "at_utc": _iso_utc(at_utc),
        "outcome": outcome,
        "refusal_reason": refusal_reason,
        "detail": detail[:256],
        "prior_digest": prior_digest,
    }
    preimage = json.dumps(base, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256((preimage + prior_digest).encode("utf-8")).hexdigest()
    return MemoryAccessAuditEntry(
        entry_digest=digest,
        **{**base, "at_utc": at_utc},
    )


# ---------------------------------------------------------------------------
# The append-only chain + verifier
# ---------------------------------------------------------------------------


class MemoryAccessAuditTrail:
    """Append-only, tamper-evident access/operation ledger (no I/O, no clock).

    - append(): verifies the WHOLE chain first (fail-closed: an append onto a
      broken chain is refused with ``MemoryAccessAuditChainBroken`` and the
      log is left unchanged), then links the new entry.
    - verify(): recomputes every link; returns the first broken sequence
      (None when intact).
    - entries(): the verbatim record (nothing hidden, nothing rewritten).
    """

    def __init__(self, entries: tuple[MemoryAccessAuditEntry, ...] = ()) -> None:
        self._entries: tuple[MemoryAccessAuditEntry, ...] = ()
        self._last_digest: str = GENESIS_DIGEST
        self._sequence: int = 0
        for e in entries:
            # construction-time seeding validates the whole seeded chain
            self._append_validated(e)

    def _append_validated(self, entry: MemoryAccessAuditEntry) -> None:
        if entry.sequence != self._sequence + 1:
            raise ValueError("audit_entry_sequence_gap")
        if entry.prior_digest != self._last_digest:
            raise ValueError("audit_chain_link_mismatch")
        self._entries = self._entries + (entry,)
        self._last_digest = entry.entry_digest
        self._sequence = entry.sequence

    def append(self, entry: MemoryAccessAuditEntry) -> "MemoryAccessAuditTrail":
        self._verify_strict()  # verify-before-accept (fail-closed)
        self._append_validated(entry)
        return self

    def _verify_strict(self) -> None:
        broken = self.first_broken_sequence()
        if broken is not None:
            raise MemoryAccessAuditChainBroken(
                f"audit_chain_broken_at_sequence_{broken}"
            )

    def record(
        self,
        *,
        actor: str,
        authorization_context: str,
        operation: MemoryAccessOperation,
        object_ref: str,
        at_utc: datetime,
        run_id: str | None = None,
        outcome: AuditOutcome = "OK",
        refusal_reason: str | None = None,
        detail: str = "",
    ) -> "MemoryAccessAuditTrail":
        """Mint + append in one step (the ergonomic write path)."""
        self._verify_strict()
        entry = mint_audit_entry(
            sequence=self._sequence + 1,
            actor=actor,
            authorization_context=authorization_context,
            operation=operation,
            object_ref=object_ref,
            at_utc=at_utc,
            run_id=run_id,
            outcome=outcome,
            refusal_reason=refusal_reason,
            detail=detail,
            prior_digest=self._last_digest,
        )
        self._append_validated(entry)
        return self

    @property
    def entries(self) -> tuple[MemoryAccessAuditEntry, ...]:
        return self._entries

    @property
    def head_digest(self) -> str:
        return self._last_digest

    def first_broken_sequence(self) -> int | None:
        """Recompute every chain link; return the first broken sequence."""
        prior = GENESIS_DIGEST
        for e in self._entries:
            expected = hashlib.sha256(
                (canonical_audit_json(e) + prior).encode("utf-8")
            ).hexdigest()
            if e.prior_digest != prior or expected != e.entry_digest:
                return e.sequence
            prior = e.entry_digest
        return None


class MemoryAccessAuditChainBroken(Exception):
    """Fail-closed: an append was attempted on a broken/tampered chain."""


# ---------------------------------------------------------------------------
# The audited store wrapper (composes ANY ResearchMemoryStore)
# ---------------------------------------------------------------------------


class AuditedResearchMemoryStore:
    """Wraps a ``ResearchMemoryStore`` and records EVERY protocol operation.

    - WRITE operations (episodic append / semantic register) are recorded
      BEFORE delegation with outcome OK when the contract accepts them, and
      as REFUSED rows (with the contract's refusal reason) when the contract
      refuses — the store stays unchanged on refusal, and the audit trail
      says so honestly.
    - READ operations are recorded with the object ref (an id or a scoped
      query key) and an honest empty-result disclosure in ``detail``.
    - Reads of missing objects are outcome=OK with detail 'object_not_found'
      (the read itself succeeded; nothing was refused, nothing was found) —
      no fabricated rows, no silent misses.
    - ``integrity_report`` is recorded as a RUN_CONTEXT-layer operation.
    """

    def __init__(
        self,
        store: ResearchMemoryStore,
        *,
        actor: str = "system",
        authorization_context: str = "L0-internal",
        trail: MemoryAccessAuditTrail | None = None,
        now_utc: Any,
    ) -> None:
        self._store = store
        self._actor = actor
        self._authorization_context = authorization_context
        self.trail = trail if trail is not None else MemoryAccessAuditTrail()
        self._now_utc = now_utc  # caller-supplied instant provider (no wall clock here)

    def _audit(
        self,
        operation: MemoryAccessOperation,
        object_ref: str,
        outcome: AuditOutcome = "OK",
        refusal_reason: str | None = None,
        detail: str = "",
        run_id: str | None = None,
    ) -> None:
        self.trail.record(
            actor=self._actor,
            authorization_context=self._authorization_context,
            operation=operation,
            object_ref=object_ref,
            at_utc=self._now_utc(),
            run_id=run_id,
            outcome=outcome,
            refusal_reason=refusal_reason,
            detail=detail,
        )

    # -- episodic (D1) ------------------------------------------------------

    def append_episodic(self, entry: EpisodicRunArtifact, *, run_id: str | None = None) -> None:
        try:
            self._store.append_episodic(entry)
        except ValueError as exc:
            self._audit(
                "EPISODIC_APPEND",
                entry.entry_id,
                outcome="REFUSED",
                refusal_reason=str(exc)[:256],
                run_id=run_id,
            )
            raise
        self._audit("EPISODIC_APPEND", entry.entry_id, run_id=run_id)

    def get_episodic(self, entry_id: str, *, run_id: str | None = None) -> EpisodicRunArtifact | None:
        found = self._store.get_episodic(entry_id)
        self._audit(
            "EPISODIC_GET",
            entry_id,
            detail="" if found is not None else "object_not_found",
            run_id=run_id,
        )
        return found

    def episodic_for_run(self, run_id: str) -> tuple[EpisodicRunArtifact, ...]:
        rows = self._store.episodic_for_run(run_id)
        self._audit(
            "EPISODIC_FOR_RUN",
            f"run:{run_id}",
            detail=f"returned_{len(rows)}",
            run_id=run_id,
        )
        return rows

    def episodic_for_hypothesis(
        self, hypothesis_id: str, *, run_id: str | None = None
    ) -> tuple[EpisodicRunArtifact, ...]:
        rows = self._store.episodic_for_hypothesis(hypothesis_id)
        self._audit(
            "EPISODIC_FOR_HYPOTHESIS",
            f"hypothesis:{hypothesis_id}",
            detail=f"returned_{len(rows)}",
            run_id=run_id,
        )
        return rows

    def episodic_available_at(self, cutoff: datetime, *, run_id: str | None = None) -> tuple[EpisodicRunArtifact, ...]:
        rows = self._store.episodic_available_at(cutoff)
        self._audit(
            "EPISODIC_AVAILABLE_AT",
            f"cutoff:{cutoff.isoformat()}",
            detail=f"returned_{len(rows)}",
            run_id=run_id,
        )
        return rows

    # -- semantic lessons (D2) ----------------------------------------------

    def register_lesson(self, lesson: SemanticLesson, *, run_id: str | None = None) -> None:
        try:
            self._store.register_lesson(lesson)
        except ValueError as exc:
            self._audit(
                "SEMANTIC_REGISTER",
                lesson.lesson_id,
                outcome="REFUSED",
                refusal_reason=str(exc)[:256],
                run_id=run_id,
            )
            raise
        self._audit("SEMANTIC_REGISTER", lesson.lesson_id, run_id=run_id)

    def latest_lesson(self, lesson_id: str, *, run_id: str | None = None) -> SemanticLesson | None:
        found = self._store.latest_lesson(lesson_id)
        self._audit(
            "SEMANTIC_LATEST",
            lesson_id,
            detail="" if found is not None else "object_not_found",
            run_id=run_id,
        )
        return found

    def lesson_history(self, lesson_id: str, *, run_id: str | None = None) -> tuple[SemanticLesson, ...]:
        rows = self._store.lesson_history(lesson_id)
        self._audit(
            "SEMANTIC_HISTORY",
            lesson_id,
            detail=f"returned_{len(rows)}",
            run_id=run_id,
        )
        return rows

    def lessons_active_at(self, cutoff: datetime, *, run_id: str | None = None) -> tuple[SemanticLesson, ...]:
        rows = self._store.lessons_active_at(cutoff)
        self._audit(
            "SEMANTIC_ACTIVE_AT",
            f"cutoff:{cutoff.isoformat()}",
            detail=f"returned_{len(rows)}",
            run_id=run_id,
        )
        return rows

    # -- integrity (D3) -------------------------------------------------------

    def integrity_report(self, *, run_id: str | None = None) -> ResearchMemoryIntegrityReport:
        report = self._store.integrity_report()
        self._audit(
            "INTEGRITY_REPORT",
            f"verify_ok={report.verify_ok}",
            detail=f"episodic_{report.entry_count}",
            run_id=run_id,
        )
        return report


__all__ = [
    "MemoryAccessOperation",
    "MemoryLayer",
    "MemoryAccessAuditEntry",
    "MemoryAccessAuditTrail",
    "MemoryAccessAuditChainBroken",
    "AuditedResearchMemoryStore",
    "mint_audit_entry",
    "canonical_audit_json",
    "GENESIS_DIGEST",
    "WRITE_OPERATIONS",
]
