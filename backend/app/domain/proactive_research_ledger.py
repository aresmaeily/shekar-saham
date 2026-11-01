"""AI-5 append-only proactive-research job state-history ledger.

Corpus loci (2026-10-02 amendment corpus; see also
AI4_AI7_P343_DEPENDENCY_MATRIX.md §AI-5):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 92-95: "AI-5 — Proactive
  Intelligence: Scheduled/event-triggered bounded research with budget,
  observability, recovery and kill switch."
- 02 line 186: "Cadence, thresholds and budgets require explicit
  configuration, observability, idempotency, retry ceilings and a kill
  switch."
- 06 charter §9: every job needs idempotency, retry ceilings, run identity,
  audit trace, failure alert, kill switch.
- Dependency matrix §AI-5: "Authorized NOW: contract extension only (e.g.
  proactive-research job contracts reusing the P0 monitoring schema);
  scheduler runtime is owner-gated."

Design (additive to ``app.domain.proactive_research``):
- this ledger is an OBSERVABILITY record layer only: no execution, no
  scheduling, no trigger evaluation, nothing is run. The kill-switch /
  budget permission SEMANTICS stay in ``proactive_research`` /
  ``monitoring``; this module only files deterministic refusal RECORDS
  (``KILL_SWITCH_ENGAGED`` / ``BUDGET_EXHAUSTED``) that a caller produced
  by applying those semantics;
- idempotency discipline mirrors the alert-ops outbox pattern
  (``app.data.alert_ops_store``: durable dedup keys, idempotent re-apply,
  conflict refusal) — reimplemented here as a pure value object; the
  store itself is NOT imported (contracts only);
- attempt dedup key is exactly ``(job_id, trigger_id, tick_index)``; one
  tick carries at most one record (an attempt XOR a refusal) — a
  conflicting second record for the same key is refused;
- append-only value object: appends return NEW ledgers; no update, delete,
  edit or purge/retention path exists (episodic evidence is never purged);
- ``state_at(job_id, ts)`` is the point-in-time view (fail-closed on
  unknown job ids);
- ``integrity_digest()`` is a deterministic SHA-256 over the canonical
  serialization of the whole ledger.

No network, no I/O, no clock reads, no LLM. All timestamps are arguments.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc

__all__ = [
    "TickRefusalReason",
    "JobTickAttemptRecord",
    "JobTickRefusalRecord",
    "JobLedgerStateAt",
    "ProactiveResearchJobLedger",
]

TickRefusalReason = Literal["KILL_SWITCH_ENGAGED", "BUDGET_EXHAUSTED"]

_TICK_REJECTION_CODES: dict[str, str] = {
    "attempt": "ledger_tick_already_attempted",
    "refusal": "ledger_tick_already_refused",
}


class JobTickAttemptRecord(BaseModel):
    """One filed attempt of one proactive-research job tick.

    The deterministic dedup key is ``(job_id, trigger_id, tick_index)``.
    The record states THAT a tick was attempted under a governed job/
    trigger identity — it records no outcome, executes nothing, and
    carries no authority.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    job_id: str = Field(min_length=1, max_length=128)
    trigger_id: str = Field(min_length=1, max_length=128)
    tick_index: int = Field(ge=0)
    attempted_at_utc: datetime
    notes: str = ""

    @field_validator("attempted_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @property
    def dedup_key(self) -> tuple[str, str, int]:
        return (self.job_id, self.trigger_id, self.tick_index)


class JobTickRefusalRecord(BaseModel):
    """One filed refusal of one proactive-research job tick.

    Refusal reasons are the closed pair the governed permission semantics
    produce: kill switch ENGAGED or budget exhausted (02:186; 06 §9). A
    refusal is a record — releasing the kill switch or raising the budget
    remains an owner/configuration decision elsewhere.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    job_id: str = Field(min_length=1, max_length=128)
    trigger_id: str = Field(min_length=1, max_length=128)
    tick_index: int = Field(ge=0)
    reason: TickRefusalReason
    refused_at_utc: datetime
    notes: str = ""

    @field_validator("refused_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @property
    def dedup_key(self) -> tuple[str, str, int]:
        return (self.job_id, self.trigger_id, self.tick_index)


class JobLedgerStateAt(BaseModel):
    """Point-in-time summary of one job's ledger state (honesty fields)."""

    model_config = ConfigDict(frozen=True)

    job_id: str = Field(min_length=1, max_length=128)
    as_of_utc: datetime
    attempt_count: int = Field(ge=0)
    refusal_count: int = Field(ge=0)
    last_attempt_at_utc: datetime | None = None
    last_refusal_at_utc: datetime | None = None
    last_refusal_reason: TickRefusalReason | None = None
    notes: str = ""

    @field_validator("as_of_utc", "last_attempt_at_utc", "last_refusal_at_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)


def _canonical_attempt_line(r: JobTickAttemptRecord) -> str:
    return "|".join(
        (
            "A",
            r.job_id,
            r.trigger_id,
            str(r.tick_index),
            r.attempted_at_utc.isoformat(),
            r.notes,
        )
    )


def _canonical_refusal_line(r: JobTickRefusalRecord) -> str:
    return "|".join(
        (
            "F",
            r.job_id,
            r.trigger_id,
            str(r.tick_index),
            r.reason,
            r.refused_at_utc.isoformat(),
            r.notes,
        )
    )


class ProactiveResearchJobLedger:
    """Append-only per-job state history (value object; no execution).

    Deterministic append rules (idempotency with conflict refusal):
    - appending an attempt whose dedup key already holds an IDENTICAL
      attempt record is an idempotent no-op (returns ``self``);
    - appending a DIFFERENT attempt under the same dedup key raises
      ``ledger_attempt_conflict``;
    - appending a record (attempt or refusal) under a dedup key already
      held by the other kind raises ``ledger_tick_already_refused`` /
      ``ledger_tick_already_attempted``;
    - refusal appends follow the symmetric rules
      (``ledger_refusal_conflict`` for differing content);
    - history is never rewritten: appends return NEW ledgers and the class
      exposes no update/delete/purge method (structural absence).
    """

    def __init__(
        self,
        attempts: tuple[JobTickAttemptRecord, ...] = (),
        refusals: tuple[JobTickRefusalRecord, ...] = (),
    ) -> None:
        self._attempts: tuple[JobTickAttemptRecord, ...] = attempts
        self._refusals: tuple[JobTickRefusalRecord, ...] = refusals

    @property
    def attempts(self) -> tuple[JobTickAttemptRecord, ...]:
        return self._attempts

    @property
    def refusals(self) -> tuple[JobTickRefusalRecord, ...]:
        return self._refusals

    # -- append-only API ------------------------------------------------------
    def append_attempt(self, record: JobTickAttemptRecord) -> "ProactiveResearchJobLedger":
        for existing in self._refusals:
            if existing.dedup_key == record.dedup_key:
                raise ValueError(_TICK_REJECTION_CODES["refusal"])
        for existing in self._attempts:
            if existing.dedup_key == record.dedup_key:
                if existing == record:
                    return self  # idempotent re-append
                raise ValueError("ledger_attempt_conflict")
        return ProactiveResearchJobLedger(self._attempts + (record,), self._refusals)

    def append_refusal(self, record: JobTickRefusalRecord) -> "ProactiveResearchJobLedger":
        for existing in self._attempts:
            if existing.dedup_key == record.dedup_key:
                raise ValueError(_TICK_REJECTION_CODES["attempt"])
        for existing in self._refusals:
            if existing.dedup_key == record.dedup_key:
                if existing == record:
                    return self  # idempotent re-append
                raise ValueError("ledger_refusal_conflict")
        return ProactiveResearchJobLedger(self._attempts, self._refusals + (record,))

    # -- point-in-time view (fail-closed) --------------------------------------
    def state_at(self, job_id: str, ts: datetime) -> JobLedgerStateAt:
        """Ledger state of ``job_id`` as of ``ts`` (records at/before ts).

        Unknown ``job_id`` (no records at all) raises ``unknown_job_id`` —
        a missing history must never be mistaken for an empty one. Note:
        a job whose every record falls AFTER ``ts`` yields zeroed counters
        (a known job observed before its first record) — the job is known,
        the cutoff simply precedes its history.
        """
        cutoff = ensure_utc(ts)
        attempts = tuple(
            a for a in self._attempts if a.job_id == job_id and a.attempted_at_utc <= cutoff
        )
        refusals = tuple(
            r for r in self._refusals if r.job_id == job_id and r.refused_at_utc <= cutoff
        )
        if not self._job_known(job_id):
            raise ValueError("unknown_job_id")
        last_attempt = max(
            attempts, key=lambda a: (a.attempted_at_utc, a.tick_index), default=None
        )
        last_refusal = max(
            refusals, key=lambda r: (r.refused_at_utc, r.tick_index), default=None
        )
        return JobLedgerStateAt(
            job_id=job_id,
            as_of_utc=cutoff,
            attempt_count=len(attempts),
            refusal_count=len(refusals),
            last_attempt_at_utc=None if last_attempt is None else last_attempt.attempted_at_utc,
            last_refusal_at_utc=None if last_refusal is None else last_refusal.refused_at_utc,
            last_refusal_reason=None if last_refusal is None else last_refusal.reason,
        )

    def _job_known(self, job_id: str) -> bool:
        return any(a.job_id == job_id for a in self._attempts) or any(
            r.job_id == job_id for r in self._refusals
        )

    # -- integrity --------------------------------------------------------------
    def integrity_digest(self) -> str:
        """Deterministic SHA-256 over the canonical ledger serialization.

        Same records in the same append order ⇒ same digest, always.
        """
        lines = [_canonical_attempt_line(a) for a in self._attempts]
        lines += [_canonical_refusal_line(r) for r in self._refusals]
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProactiveResearchJobLedger):
            return NotImplemented
        return self._attempts == other._attempts and self._refusals == other._refusals

    def __hash__(self) -> int:  # pragma: no cover - value-object nicety
        return hash((self._attempts, self._refusals))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"ProactiveResearchJobLedger(attempts={len(self._attempts)}, "
            f"refusals={len(self._refusals)})"
        )
