"""AI-5 proactive-research job state-history ledger — acceptance tests.

Sources: 02:92-95 (budget, observability, recovery, kill switch), 02:186
(idempotency, retry ceilings, kill switch), 06 §9 (idempotency, run
identity, audit trace), dependency matrix §AI-5 (contract extension only;
no scheduler runtime). Records only — no execution, no scheduling, no I/O,
no clock reads.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.proactive_research_ledger import (
    JobLedgerStateAt,
    JobTickAttemptRecord,
    JobTickRefusalRecord,
    ProactiveResearchJobLedger,
)

UTC = timezone.utc
T0 = datetime(2026, 10, 28, 8, 0, 0, tzinfo=UTC)


def _attempt(
    tick: int = 0,
    at: datetime | None = None,
    job_id: str = "rj-1",
    trigger_id: str = "trg-cron",
    notes: str = "",
) -> JobTickAttemptRecord:
    return JobTickAttemptRecord(
        job_id=job_id,
        trigger_id=trigger_id,
        tick_index=tick,
        attempted_at_utc=at or T0,
        notes=notes,
    )


def _refusal(
    reason: str = "KILL_SWITCH_ENGAGED",
    tick: int = 0,
    at: datetime | None = None,
    job_id: str = "rj-1",
    trigger_id: str = "trg-cron",
    notes: str = "",
) -> JobTickRefusalRecord:
    return JobTickRefusalRecord(
        job_id=job_id,
        trigger_id=trigger_id,
        tick_index=tick,
        reason=reason,  # type: ignore[arg-type]
        refused_at_utc=at or T0,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Idempotent append with conflict refusal
# ---------------------------------------------------------------------------


def test_append_attempt_ok() -> None:
    ledger = ProactiveResearchJobLedger().append_attempt(_attempt(tick=0))
    assert len(ledger.attempts) == 1
    assert ledger.attempts[0].dedup_key == ("rj-1", "trg-cron", 0)


def test_identical_reappend_is_idempotent_noop() -> None:
    record = _attempt(tick=0)
    ledger = ProactiveResearchJobLedger().append_attempt(record)
    again = ledger.append_attempt(record)
    assert again == ledger
    assert len(again.attempts) == 1


def test_conflicting_reappend_refused() -> None:
    ledger = ProactiveResearchJobLedger().append_attempt(_attempt(tick=0))
    with pytest.raises(ValueError, match="ledger_attempt_conflict"):
        ledger.append_attempt(_attempt(tick=0, notes="different content"))


def test_refusal_records_for_both_closed_reasons() -> None:
    ledger = (
        ProactiveResearchJobLedger()
        .append_refusal(_refusal(reason="KILL_SWITCH_ENGAGED", tick=0))
        .append_refusal(_refusal(reason="BUDGET_EXHAUSTED", tick=1))
    )
    assert [r.reason for r in ledger.refusals] == [
        "KILL_SWITCH_ENGAGED",
        "BUDGET_EXHAUSTED",
    ]


def test_attempt_on_refused_tick_refused() -> None:
    ledger = ProactiveResearchJobLedger().append_refusal(_refusal(tick=0))
    with pytest.raises(ValueError, match="ledger_tick_already_refused"):
        ledger.append_attempt(_attempt(tick=0))


def test_refusal_on_attempted_tick_refused() -> None:
    ledger = ProactiveResearchJobLedger().append_attempt(_attempt(tick=0))
    with pytest.raises(ValueError, match="ledger_tick_already_attempted"):
        ledger.append_refusal(_refusal(tick=0))


def test_conflicting_refusal_reappend_refused() -> None:
    ledger = ProactiveResearchJobLedger().append_refusal(_refusal(tick=0))
    with pytest.raises(ValueError, match="ledger_refusal_conflict"):
        ledger.append_refusal(_refusal(tick=0, notes="different content"))


def test_dedup_key_scopes_job_and_trigger() -> None:
    # Same tick index under a DIFFERENT job/trigger identity is a new key.
    ledger = ProactiveResearchJobLedger().append_attempt(_attempt(tick=0, job_id="rj-1"))
    other = ledger.append_attempt(_attempt(tick=0, job_id="rj-2"))
    assert len(other.attempts) == 2


# ---------------------------------------------------------------------------
# Point-in-time view (fail-closed)
# ---------------------------------------------------------------------------


def test_state_at_is_point_in_time() -> None:
    ledger = (
        ProactiveResearchJobLedger()
        .append_attempt(_attempt(tick=0, at=T0))
        .append_attempt(_attempt(tick=1, at=T0 + timedelta(hours=2)))
    )
    early: JobLedgerStateAt = ledger.state_at("rj-1", T0 + timedelta(hours=1))
    assert early.attempt_count == 1
    assert early.last_attempt_at_utc == T0
    late = ledger.state_at("rj-1", T0 + timedelta(hours=3))
    assert late.attempt_count == 2
    assert late.last_attempt_at_utc == T0 + timedelta(hours=2)


def test_state_at_reports_last_refusal_reason() -> None:
    ledger = (
        ProactiveResearchJobLedger()
        .append_refusal(_refusal(reason="KILL_SWITCH_ENGAGED", tick=0, at=T0))
        .append_refusal(_refusal(reason="BUDGET_EXHAUSTED", tick=1, at=T0 + timedelta(hours=1)))
    )
    state = ledger.state_at("rj-1", T0 + timedelta(hours=2))
    assert state.refusal_count == 2
    assert state.last_refusal_reason == "BUDGET_EXHAUSTED"


def test_state_at_unknown_job_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown_job_id"):
        ProactiveResearchJobLedger().state_at("ghost", T0)


def test_state_at_known_job_before_first_record_is_zeroed() -> None:
    # A KNOWN job observed before its first record honestly reports zeroed
    # counters — unlike an unknown job, which is refused (fail-closed).
    ledger = ProactiveResearchJobLedger().append_attempt(_attempt(tick=0, at=T0))
    state = ledger.state_at("rj-1", T0 - timedelta(hours=1))
    assert state.attempt_count == 0 and state.last_attempt_at_utc is None


# ---------------------------------------------------------------------------
# Integrity digest / append-only structure / record discipline
# ---------------------------------------------------------------------------


def test_integrity_digest_deterministic_and_append_sensitive() -> None:
    a = ProactiveResearchJobLedger().append_attempt(_attempt(tick=0)).append_refusal(
        _refusal(tick=1)
    )
    b = ProactiveResearchJobLedger().append_attempt(_attempt(tick=0)).append_refusal(
        _refusal(tick=1)
    )
    assert a.integrity_digest() == b.integrity_digest()
    assert a.integrity_digest() != b.append_attempt(_attempt(tick=2)).integrity_digest()
    assert (
        ProactiveResearchJobLedger().integrity_digest()
        == ProactiveResearchJobLedger().integrity_digest()
    )


def test_ledger_is_append_only_by_construction() -> None:
    public_api = {
        name for name in dir(ProactiveResearchJobLedger) if not name.startswith("_")
    }
    forbidden = {"update", "delete", "purge", "remove", "rewrite", "expire", "retire", "drop"}
    assert public_api & forbidden == set()
    assert {"append_attempt", "append_refusal", "state_at", "integrity_digest"} <= public_api


def test_record_freeze_and_field_discipline() -> None:
    record = _attempt(tick=0)
    with pytest.raises(ValidationError):
        record.tick_index = 5  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _attempt(tick=-1)
    with pytest.raises(ValidationError):
        _attempt(at=datetime(2026, 10, 28, 8, 0, 0))  # naive timestamp
    with pytest.raises(ValidationError):
        _refusal(reason="OWNER_DISCRETION")  # closed refusal vocabulary only
