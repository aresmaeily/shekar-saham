"""Engine-neutral store interface for AI-3 Research Memory (pre-decision work).

This module is AUTHORIZED PRE-DECISION WORK ONLY. Owner decisions D1–D7 for
AI-3 persistence are PENDING (none recorded as of 2026-11-02, none assumed —
see ``docs/active/AI3_PERSISTENCE_DECISION_PACKET.md``). No concrete storage
engine is implemented here: no SQLite file, no filesystem blob store, no
network storage. The ONLY reference implementation is in-memory, and it does
not reimplement the contracts — it COMPOSES the delivered in-memory contracts
(``EpisodicRunArchive`` + ``SemanticLessonStore`` from
``app/domain/research_memory.py``) by delegation.

What this module provides:
- ``ResearchMemoryStore`` — a ``typing.Protocol`` mirroring the contracts'
  append-only APIs at store level (one object exposing both the episodic
  archive view and the semantic-lesson view plus an integrity view).
- ``InMemoryResearchMemoryStore`` — the in-memory reference adapter; the
  contracts remain the canonical behavior reference (reuse rule 02:107-112).
- ``canonical_research_memory_json`` / ``sha256_hex`` — deterministic
  canonical serialization over contract records (sorted keys, explicit
  separators, UTF-8, Decimal-as-string) so any future adapter can maintain a
  per-record digest ledger.
- ``ResearchMemoryIntegrityReport`` — frozen verification record.
- ``verify_integrity`` — pure, fail-closed digest verification that returns a
  refusal record; it NEVER raises raw exceptions.

Structural guarantees (binding on every implementer of the protocol):
- APPEND-ONLY. No update, delete, purge or rewrite path exists on the
  protocol — this is structural, not conventional. The protocol exposes
  append/get/index/verify operations only.
- Implementers MUST NOT add purge or retention-expiry paths for episodic
  research evidence: "Episodic research artifacts remain immutable" and
  "nothing expires out of the archive" (brief constraints A3/A11;
  ``research_memory.py:119-158`` docstring, test-pinned). Retirement of a
  semantic lesson is a NEW terminal version — history is never rewritten
  (A4; ``research_memory.py:247-318``).
- FAIL-CLOSED on missing/corrupt records, with honest semantics inherited
  from the contracts (documented so no behavior is invented):
  * Unknown ids produce an EXPLICIT MISS — ``get_episodic`` /
    ``latest_lesson`` return ``None`` and the index/history queries return
    empty tuples. This matches the underlying contracts exactly: they
    express a miss as ``None``/empty (NOT ``KeyError``); the store wraps
    that behavior honestly and never fabricates a substitute record.
  * Conflicting appends are REFUSED — re-appending the same episodic entry
    id with different content raises ``ValueError("episodic_archive_conflict")``
    and registering a non-increasing/mismatched lesson version raises the
    contract's ``ValueError``; the store propagates the contract refusals
    verbatim and its state is unchanged by a refused operation.
  * Corrupt/mutated records are caught by verification: ``verify_integrity``
    recomputes digests over canonical serialization and returns a refusal
    record (``verify_ok=False``) listing mismatched/missing ids; it never
    raises raw exceptions.

Contract/domain only: deterministic, clock-free (timestamps passed in), no
I/O, no network, no LLM, no route, no config change, no existing module
modified. Persistence technology remains an owner-environment decision
(D1–D7 PENDING); this interface is what any accepted adapter must satisfy.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.domain.research_memory import (
    EpisodicRunArchive,
    EpisodicRunArtifact,
    SemanticLesson,
    SemanticLessonStore,
    lessons_active_at,
)

__all__ = [
    "InMemoryResearchMemoryStore",
    "ResearchMemoryIntegrityReport",
    "ResearchMemoryStore",
    "canonical_research_memory_json",
    "sha256_hex",
    "verify_integrity",
]


# ---------------------------------------------------------------------------
# Canonical serialization — deterministic, engine-neutral
# ---------------------------------------------------------------------------


def _canonical_value(value: Any) -> Any:
    """Reduce a value to JSON-canonical primitives deterministically.

    Policy (recorded, not invented):
    - pydantic models are reduced via ``model_dump(mode="json")`` (pydantic
      v2 already renders ``Decimal`` as string and aware datetimes as ISO-8601
      UTC strings — the same policy is enforced below for raw values);
    - ``Decimal`` → ``str`` (DECIMAL_AS_STRING: no binary-float drift may
      enter a digest);
    - ``datetime`` → ``value.isoformat()`` (aware instants only in the
      contract records; naive values are the caller's error and stay
      honestly representable as ISO text);
    - mappings/sequences are walked recursively; everything else must already
      be a JSON primitive, otherwise ``json.dumps`` refuses (fail-closed).
    """
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): _canonical_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def canonical_research_memory_json(record: Any) -> str:
    """Deterministic canonical JSON for a research-memory record.

    Sorted keys, explicit separators ``,`` / ``:``, ``ensure_ascii=False``
    (text is UTF-8 when encoded for digesting), ``allow_nan=False`` so
    NaN/Infinity are refused instead of silently serialized. Two records
    with identical content — regardless of construction/insertion order —
    produce byte-identical output; calling this function twice on the same
    record is byte-identical (pure function, no clock, no randomness).
    Non-serializable content raises (fail-closed: refuse, never coerce).
    """
    payload = _canonical_value(record)
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_hex(text: str) -> str:
    """SHA-256 hex digest of the UTF-8 encoding of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Integrity report — frozen record
# ---------------------------------------------------------------------------


class ResearchMemoryIntegrityReport(BaseModel):
    """Frozen integrity/verification record for a research-memory store.

    - ``entry_digests``: per episodic entry ``(entry_id, sha256)`` over the
      canonical serialization of the record, in append (insertion) order.
    - ``entry_count``: number of episodic entries digested.
    - ``lesson_version_counts``: ``(lesson_id, version_count)`` per semantic
      lesson, sorted by ``lesson_id`` for determinism (version history is
      never rewritten, so the count is append-only growth).
    - ``verify_ok``: True when every stored record was read and canonically
      digested without refusal (self-consistency of THIS report). External
      digest comparison is ``verify_integrity``'s job, not this flag's.
    - ``mismatched_entry_ids`` / ``missing_entry_ids``: populated only by
      ``verify_integrity`` refusal records (mutated digest / expected entry
      absent from the store respectively), sorted, deduplicated.
    - ``refusal_reasons``: sorted, deduplicated machine-readable refusal
      reasons; empty exactly when nothing was refused.
    """

    model_config = ConfigDict(frozen=True)

    verify_ok: bool = True
    entry_count: int = Field(default=0, ge=0)
    entry_digests: tuple[tuple[str, str], ...] = ()
    lesson_version_counts: tuple[tuple[str, int], ...] = ()
    mismatched_entry_ids: tuple[str, ...] = ()
    missing_entry_ids: tuple[str, ...] = ()
    refusal_reasons: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Protocol — engine-neutral store interface
# ---------------------------------------------------------------------------


@runtime_checkable
class ResearchMemoryStore(Protocol):
    """Engine-neutral, APPEND-ONLY store interface for research memory.

    STRUCTURAL GUARANTEES (binding on every implementer — the protocol has
    no update/delete/purge/rewrite member, and none may be added):

    - APPEND-ONLY: the only state-changing operations are
      ``append_episodic`` and ``register_lesson``. There is NO update,
      delete, purge or rewrite path on the protocol — this is structural,
      not conventional.
    - NO PURGE / NO RETENTION-EXPIRY: implementers MUST NOT add purge or
      retention-expiry for episodic research evidence. Episodic artifacts
      are immutable and nothing expires out of the archive (A3/A11:
      ``02:159``, ``03 §Memory``, ``research_memory.py`` archive docstring,
      test-pinned). Semantic lessons are curated/versioned: supersession
      and retirement are NEW terminal versions; history is never rewritten
      (A4, D-AI-28).
    - FAIL-CLOSED on missing/corrupt records:
      * unknown ids → explicit miss: ``get_episodic``/``latest_lesson``
        return ``None``; index/history views return empty tuples. The
        underlying contracts express a miss as ``None``/empty — NOT
        ``KeyError`` — and the store wraps that behavior honestly; no
        substitute record is ever fabricated;
      * conflicting appends → refused with the contracts' own ``ValueError``
        (``episodic_archive_conflict``, ``lesson_version_not_increasing``,
        ...); a refused operation leaves the store unchanged;
      * corruption/mutation → detected by digest verification
        (``integrity_report`` + ``verify_integrity``), which return refusal
        records and never raise raw exceptions.

    POINT-IN-TIME honesty (A5, ``02:142``): ``episodic_available_at`` and
    ``lessons_active_at`` are pure cutoff views over explicitly recorded
    timestamps; no clock is read.

    Method contracts mirror ``EpisodicRunArchive`` and ``SemanticLessonStore``
    exactly (the contracts remain the canonical behavior reference):

    - ``append_episodic(entry)`` — append one immutable episodic run
      artifact; idempotent for an identical re-append; refuses conflicting
      content under the same id (contract ``ValueError``).
    - ``get_episodic(entry_id)`` — the entry or ``None`` (explicit miss).
    - ``episodic_for_run(run_id)`` / ``episodic_for_hypothesis(hypothesis_id)``
      — insertion-ordered tuple views.
    - ``episodic_available_at(cutoff)`` — entries with
      ``recorded_at_utc <= cutoff`` (point-in-time; deterministic).
    - ``register_lesson(lesson)`` — register one curated, versioned lesson;
      version chain rules enforced by the contract (increasing versions,
      correct supersession parent); refuses bad chains (contract
      ``ValueError``).
    - ``latest_lesson(lesson_id)`` — highest registered version or ``None``.
    - ``lesson_history(lesson_id)`` — all versions ordered by version.
    - ``lessons_active_at(cutoff)`` — point-in-time active-lesson view
      (module ``lessons_active_at`` semantics).
    - ``integrity_report()`` — frozen ``ResearchMemoryIntegrityReport``:
      per-entry id + sha256 over canonical serialization, entry count,
      lesson version counts, ``verify_ok``.

    Implementers MUST compose — not replace — the in-memory contracts, which
    remain the canonical behavior reference (02:107-112 reuse rule).
    """

    def append_episodic(self, entry: EpisodicRunArtifact) -> None: ...

    def get_episodic(self, entry_id: str) -> EpisodicRunArtifact | None: ...

    def episodic_for_run(self, run_id: str) -> tuple[EpisodicRunArtifact, ...]: ...

    def episodic_for_hypothesis(
        self, hypothesis_id: str
    ) -> tuple[EpisodicRunArtifact, ...]: ...

    def episodic_available_at(
        self, cutoff: datetime
    ) -> tuple[EpisodicRunArtifact, ...]: ...

    def register_lesson(self, lesson: SemanticLesson) -> None: ...

    def latest_lesson(self, lesson_id: str) -> SemanticLesson | None: ...

    def lesson_history(self, lesson_id: str) -> tuple[SemanticLesson, ...]: ...

    def lessons_active_at(self, cutoff: datetime) -> tuple[SemanticLesson, ...]: ...

    def integrity_report(self) -> ResearchMemoryIntegrityReport: ...


# ---------------------------------------------------------------------------
# In-memory reference adapter — delegation, not reimplementation
# ---------------------------------------------------------------------------


class InMemoryResearchMemoryStore:
    """In-memory reference implementation of ``ResearchMemoryStore``.

    COMPOSES the delivered contracts by delegation: the episodic view IS an
    ``EpisodicRunArchive`` and the semantic view IS a ``SemanticLessonStore``
    (both kept as the current immutable state; every append replaces the
    current state with the contract's returned next state). Idempotent
    appends and conflict refusals behave exactly as those contracts behave —
    identical re-append is a no-op; conflicting content under the same id
    raises the contract ``ValueError`` and leaves the store unchanged.

    No storage engine lives here: this adapter is the deterministic
    in-memory reference against which any future persistence adapter
    (SQLite/JSONL/server-class — owner decision PENDING, D1–D7) must be
    proven equivalent. Single-writer by construction; no locking, no I/O,
    no clock reads.

    Constructor seeding is deliberate: an adapter may be seeded with
    contract-state built through the contracts' own lifecycle APIs (e.g. a
    lesson store carrying superseded/retired versions), so every view —
    including point-in-time views over retirement — is delegated, never
    re-derived.
    """

    def __init__(
        self,
        *,
        archive: EpisodicRunArchive | None = None,
        lessons: SemanticLessonStore | None = None,
    ) -> None:
        self._archive: EpisodicRunArchive = (
            archive if archive is not None else EpisodicRunArchive()
        )
        self._lessons: SemanticLessonStore = (
            lessons if lessons is not None else SemanticLessonStore()
        )

    # -- episodic (D1) ------------------------------------------------------

    def append_episodic(self, entry: EpisodicRunArtifact) -> None:
        """Delegate to ``EpisodicRunArchive.append``; idempotent for an
        identical entry, refuses conflict (contract ``ValueError``) before
        any state change."""
        self._archive = self._archive.append(entry)

    def get_episodic(self, entry_id: str) -> EpisodicRunArtifact | None:
        return self._archive.get(entry_id)

    def episodic_for_run(self, run_id: str) -> tuple[EpisodicRunArtifact, ...]:
        return self._archive.for_run(run_id)

    def episodic_for_hypothesis(
        self, hypothesis_id: str
    ) -> tuple[EpisodicRunArtifact, ...]:
        return self._archive.for_hypothesis(hypothesis_id)

    def episodic_available_at(
        self, cutoff: datetime
    ) -> tuple[EpisodicRunArtifact, ...]:
        return self._archive.available_at(cutoff)

    # -- semantic lessons (D2) ----------------------------------------------

    def register_lesson(self, lesson: SemanticLesson) -> None:
        """Delegate to ``SemanticLessonStore.register``; chain guards and
        refusals are the contract's own."""
        self._lessons = self._lessons.register(lesson)

    def latest_lesson(self, lesson_id: str) -> SemanticLesson | None:
        return self._lessons.latest(lesson_id)

    def lesson_history(self, lesson_id: str) -> tuple[SemanticLesson, ...]:
        return self._lessons.history(lesson_id)

    def lessons_active_at(self, cutoff: datetime) -> tuple[SemanticLesson, ...]:
        return lessons_active_at(self._lessons, cutoff)

    # -- integrity ----------------------------------------------------------

    def integrity_report(self) -> ResearchMemoryIntegrityReport:
        """Digest every stored episodic entry over its canonical
        serialization (insertion order) and count semantic-lesson versions
        per lesson id (sorted). ``verify_ok`` is True when every record was
        read and digested without refusal — always true here, because the
        contracts structurally hold frozen records; external digest
        comparison is ``verify_integrity``."""
        digests: list[tuple[str, str]] = []
        for e in self._archive.entries:
            digests.append((e.entry_id, sha256_hex(canonical_research_memory_json(e))))
        lesson_ids = {l.lesson_id for l in self._lessons.lessons}
        counts = tuple(
            sorted((lid, len(self._lessons.history(lid))) for lid in lesson_ids)
        )
        return ResearchMemoryIntegrityReport(
            verify_ok=True,
            entry_count=len(digests),
            entry_digests=tuple(digests),
            lesson_version_counts=counts,
        )


# ---------------------------------------------------------------------------
# Pure, fail-closed verification
# ---------------------------------------------------------------------------


def verify_integrity(
    store: ResearchMemoryStore,
    expected_digests: Mapping[str, str],
) -> ResearchMemoryIntegrityReport:
    """Recompute per-entry digests and compare against ``expected_digests``.

    Pure function. Fail-closed refusal semantics (never raises raw
    exceptions — every refusal is a returned ``ResearchMemoryIntegrityReport``
    with ``verify_ok=False``):

    - digest mismatch (record present but content/canonicalization differs
      from expectation) → listed in ``mismatched_entry_ids``;
    - expected entry absent from the store (an append-only violation —
      deletion) → listed in ``missing_entry_ids``;
    - the store's own report refusing (or any unexpected failure) →
      recorded in ``refusal_reasons``.

    Append-only honesty: entries appended AFTER the expected snapshot was
    taken are legal (append is the only legal change) — they are visible in
    the returned report's ``entry_digests``/``entry_count`` but are NOT
    refusals. ``verify_ok`` is True only when there is no mismatch, nothing
    expected is missing, and the store's own report raised no refusal.
    """
    try:
        report = store.integrity_report()
        current = dict(report.entry_digests)
        mismatched = tuple(
            sorted(
                eid
                for eid, digest in expected_digests.items()
                if eid in current and current[eid] != digest
            )
        )
        missing = tuple(
            sorted(eid for eid in expected_digests if eid not in current)
        )
        reasons: set[str] = set(report.refusal_reasons)
        if mismatched:
            reasons.add("digest_mismatch")
        if missing:
            reasons.add("expected_entry_missing_from_store")
        if not report.verify_ok:
            reasons.add("store_report_not_ok")
        return ResearchMemoryIntegrityReport(
            verify_ok=not reasons,
            entry_count=report.entry_count,
            entry_digests=report.entry_digests,
            lesson_version_counts=report.lesson_version_counts,
            mismatched_entry_ids=mismatched,
            missing_entry_ids=missing,
            refusal_reasons=tuple(sorted(reasons)),
        )
    except Exception as exc:  # fail-closed refusal — never a raw exception
        return ResearchMemoryIntegrityReport(
            verify_ok=False,
            entry_count=0,
            refusal_reasons=(f"verify_refused:{type(exc).__name__}",),
        )
