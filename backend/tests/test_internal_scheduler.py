"""test_internal_scheduler.py — WAVE-M (OA-4, owner directive 2026-11-05)

Service-level battery for the bounded LOCAL internal scheduler
(app/services/internal_scheduler.py + scheduler_run_store.py +
scheduler_jobs.py). Acceptance coverage (directive §3 WAVE-M + §5, mapped):

- fail-closed default: SCHEDULER_ENABLED=0 refuses start AND enqueue, and
  NOTHING is scheduled, nothing recorded
  (test_disabled_start_refused, test_disabled_enqueue_refuses_and_records_nothing,
  test_posture_honest_while_disabled);
- bounded queue: queue-depth cap refuses with queue_full
  (test_queue_cap_refused);
- run identity + idempotency keys: identical (key, payload) replay is a
  no-op with NO re-execution; a different payload under the same key is
  refused (test_idempotent_replay_never_reexecutes,
  test_idempotency_conflict_refused, test_idempotency_key_malformed);
- max concurrency: runs never exceed the cap (test_concurrency_cap_holds);
- per-run time budget: the budget cancels the handler and the run honest-
  fails (test_run_timeout_budget_enforced);
- late-completion containment: a handler that completes AFTER its timeout
  (or after the kill switch) is discarded — its result is NEVER committed
  to the immutable history (test_late_completion_never_committed,
  test_kill_discards_late_completion);
- pause/resume/stop: pause holds the queue, resume dispatches, stop
  cancels queued runs and refuses further enqueue
  (test_pause_holds_and_resume_dispatches, test_stop_cancels_queued_and_refuses);
- bounded retries + dead-letter: exhausted attempts land exactly once in
  DEAD_LETTERED (test_retry_then_complete, test_dead_letter_after_bounded_retries);
- kill-switch: ENGAGE kills active runs and blocks enqueue; RELEASE re-arms
  (test_kill_switch_engage_blocks_and_kills);
- restart recovery: non-terminal runs in the durable history are closed
  INTERRUPTED at startup — never silently dropped, never auto-resumed
  (test_restart_recovery_interrupts_nonterminal);
- store integrity: append-only event ledger — unknown event types rejected,
  event-id conflicts rejected, byte-identical re-append is an idempotent
  no-op, row-digest tampering fails closed, schema-digest mismatch fails
  closed, verified backup/restore (durable-store tests, tmp sqlite files)
  (test_store_* family);
- provenance: every run carries actor, payload digest, attempts, UTC
  instants and the config fingerprint (test_run_provenance_complete);
- no-egress structure: the scheduler modules construct no network client
  (source scan, test_no_egress_structural) and the service never reads
  settings after construction (test_no_settings_access_after_construction);
- governed research-loop handler: payload validation refuses malformed
  input BEFORE anything executes; a valid payload delegates to the
  governed runner whose own fail-closed gates yield the honest
  gated_not_executed outcome with the committed defaults
  (test_research_loop_handler_gated_honest,
  test_research_loop_handler_refuses_bad_payload).

Honesty note: this battery never constructs a network transport and never
asserts a live/verified posture; the scheduler's only side effects here are
memory-store events and stub-handler invocations.
"""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.internal_scheduler import (
    PAYLOAD_MAX_BYTES,
    InternalScheduler,
    SchedulerRefused,
    get_scheduler,
    reset_scheduler_cache,
)
from app.services.scheduler_jobs import research_loop_handler
from app.services.scheduler_run_store import (
    MemorySchedulerRunStore,
    SchedulerRunStoreCorruption,
    SchedulerRunStoreError,
    DurableSchedulerRunStore,
    derive_run_state,
    reset_scheduler_run_store_cache,
)

_NOW = datetime(2026, 11, 6, 8, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 0.01
        return self.t


def _now_utc() -> datetime:
    return _NOW


def _mk(
    handlers: dict,
    *,
    enabled: bool = True,
    max_queue: int = 8,
    max_concurrent: int = 1,
    run_timeout_sec: float = 5.0,
    max_attempts: int = 2,
) -> InternalScheduler:
    return InternalScheduler(
        MemorySchedulerRunStore(),
        handlers,
        enabled=enabled,
        max_queue=max_queue,
        max_concurrent=max_concurrent,
        run_timeout_sec=run_timeout_sec,
        max_attempts=max_attempts,
        clock=FakeClock(),
        now_utc=_now_utc,
    )


async def _wait_state(scheduler: InternalScheduler, run_id: str, states: set, timeout: float = 5.0):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        detail = scheduler.run_detail(run_id)
        if detail is not None and detail["state"] in states:
            return detail
        await asyncio.sleep(0.01)
    detail = scheduler.run_detail(run_id)
    raise AssertionError(f"state not reached: want={states} got={detail and detail['state']}")


def _ok_handler():
    async def _h(p, *, run_provenance=None):
        await asyncio.sleep(0.01)
        return {"done": True, "echo": p.get("x")}
    return _h


def _failing_handler(message="boom"):
    async def _h(p, *, run_provenance=None):
        raise RuntimeError(message)
    return _h


def _flaky_handler(calls: list):
    async def _h(p, *, run_provenance=None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("first-attempt-failure")
        return {"done": True}
    return _h


# ---------------------------------------------------------------------------
# Fail-closed default (OA-4 gate)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disabled_start_refused():
    s = _mk({"stub": _ok_handler()}, enabled=False)
    with pytest.raises(SchedulerRefused) as exc:
        await s.start()
    assert exc.value.code == "scheduler_disabled"
    assert s.posture()["enabled"] is False


@pytest.mark.asyncio
async def test_disabled_enqueue_refuses_and_records_nothing():
    s = _mk({"stub": _ok_handler()}, enabled=False)
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("stub", {"x": 1}, idempotency_key="k1")
    assert exc.value.code == "scheduler_disabled"
    assert s._store.all_events(100) == []  # nothing recorded


@pytest.mark.asyncio
async def test_posture_honest_while_disabled():
    s = _mk({"stub": _ok_handler()}, enabled=False)
    p = s.posture()
    assert p["enabled"] is False
    assert p["state"] == "created"
    assert p["kill_switch"] == "RELEASED"
    assert p["honesty"]["no_egress"]
    assert p["honesty"]["execution_domain"] == "SYNTHETIC_OR_PAPER"


# ---------------------------------------------------------------------------
# Happy path + provenance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enabled_run_completes_with_provenance():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    res = await s.enqueue("stub", {"x": 1}, idempotency_key="k1", actor="tester")
    assert res["ok"] is True and res["run_id"]
    detail = await _wait_state(s, res["run_id"], {"COMPLETED"})
    types = [e["event_type"] for e in detail["events"]]
    assert types == ["ENQUEUED", "STARTED", "SUCCEEDED", "COMPLETED"]
    succeeded = next(e for e in detail["events"] if e["event_type"] == "SUCCEEDED")
    assert succeeded["payload"]["outcome_digest"]
    assert detail["attempts"] == 1
    assert s.posture()["counters"]["completed_total"] == 1
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_run_provenance_complete():
    captured = {}

    async def handler(p, *, run_provenance=None):
        captured.update(run_provenance or {})
        return {"ok": True}

    s = _mk({"stub": handler})
    await s.start()
    res = await s.enqueue("stub", {"x": 2}, idempotency_key="prov", actor="auditor")
    await _wait_state(s, res["run_id"], {"COMPLETED"})
    assert captured["run_id"] == res["run_id"]
    assert captured["actor"] == "auditor"
    assert captured["job_type"] == "stub"
    assert captured["execution_domain"] == "SYNTHETIC_OR_PAPER"
    assert captured["enqueued_payload_digest"]
    assert captured["scheduler_config"]["max_concurrent"] == 1
    await s.stop(actor="tester")


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotent_replay_never_reexecutes():
    calls = []

    async def handler(p, *, run_provenance=None):
        calls.append(1)
        return {"n": len(calls)}

    s = _mk({"stub": handler})
    await s.start()
    first = await s.enqueue("stub", {"x": 1}, idempotency_key="same-key")
    await _wait_state(s, first["run_id"], {"COMPLETED"})
    second = await s.enqueue("stub", {"x": 1}, idempotency_key="same-key")
    assert second["replayed"] is True
    assert second["run_id"] == first["run_id"]
    assert len(calls) == 1  # NO re-execution
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_idempotency_conflict_refused():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    await s.enqueue("stub", {"x": 1}, idempotency_key="key-c")
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("stub", {"x": 999}, idempotency_key="key-c")
    assert exc.value.code == "idempotency_conflict"
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_idempotency_key_malformed():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    for bad in ("", "  ", "x" * 129):
        with pytest.raises(SchedulerRefused) as exc:
            await s.enqueue("stub", {"x": 1}, idempotency_key=bad)
        assert exc.value.code == "idempotency_key_malformed"
    await s.stop(actor="tester")


# ---------------------------------------------------------------------------
# Bounds: queue cap, concurrency cap, payload bounds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_queue_cap_refused():
    s = _mk({"stub": _ok_handler()}, max_queue=1)
    await s.start()
    await s.pause(actor="tester")  # keep the first run queued
    await s.enqueue("stub", {"x": 1}, idempotency_key="q1")
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("stub", {"x": 2}, idempotency_key="q2")
    assert exc.value.code == "queue_full"
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_concurrency_cap_holds():
    active = []
    overlaps = []

    async def handler(p, *, run_provenance=None):
        active.append(1)
        overlaps.append(len(active))
        await asyncio.sleep(0.03)
        active.pop()
        return {"ok": True}

    s = _mk({"stub": handler}, max_concurrent=1)
    await s.start()
    r1 = await s.enqueue("stub", {"x": 1}, idempotency_key="c1")
    r2 = await s.enqueue("stub", {"x": 2}, idempotency_key="c2")
    await _wait_state(s, r1["run_id"], {"COMPLETED"})
    await _wait_state(s, r2["run_id"], {"COMPLETED"})
    assert max(overlaps) == 1  # never two handlers at once
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_unknown_job_type_refused():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("nope", {"x": 1}, idempotency_key="u1")
    assert exc.value.code == "unknown_job_type"
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_payload_oversized_refused():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    big = {"blob": "x" * (PAYLOAD_MAX_BYTES + 10)}
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("stub", big, idempotency_key="big1")
    assert exc.value.code == "payload_oversized"
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_payload_must_be_object():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("stub", [1, 2, 3], idempotency_key="l1")  # type: ignore[arg-type]
    assert exc.value.code == "payload_must_be_object"
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_bounds_invalid_rejected():
    with pytest.raises(SchedulerRefused):
        _mk({"stub": _ok_handler()}, max_queue=0)
    with pytest.raises(SchedulerRefused):
        _mk({"stub": _ok_handler()}, run_timeout_sec=0)
    with pytest.raises(SchedulerRefused):
        _mk({"stub": _ok_handler()}, max_attempts=0)


# ---------------------------------------------------------------------------
# Per-run budget + containment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_timeout_budget_enforced():
    async def slow(p, *, run_provenance=None):
        await asyncio.sleep(1.5)
        return {"never": True}

    s = _mk({"slow": slow}, run_timeout_sec=0.05, max_attempts=1)
    await s.start()
    res = await s.enqueue("slow", {"x": 1}, idempotency_key="t1")
    detail = await _wait_state(s, res["run_id"], {"DEAD_LETTERED"})
    types = [e["event_type"] for e in detail["events"]]
    assert "TIMED_OUT" in types
    assert "SUCCEEDED" not in types  # the slow result never committed
    assert s.posture()["counters"]["timed_out_total"] == 1
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_late_completion_never_committed():
    async def ignores_cancel(p, *, run_provenance=None):
        try:
            await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            return {"late": True}  # completes AFTER cancellation
        return {"ontime": True}

    s = _mk({"late": ignores_cancel}, run_timeout_sec=0.05, max_attempts=1)
    await s.start()
    res = await s.enqueue("late", {"x": 1}, idempotency_key="late1")
    detail = await _wait_state(s, res["run_id"], {"DEAD_LETTERED"})
    await asyncio.sleep(0.2)  # give any late completion a chance to leak
    detail = s.run_detail(res["run_id"])
    types = [e["event_type"] for e in detail["events"]]
    assert "SUCCEEDED" not in types
    assert "COMPLETED" not in types
    assert types[-1] == "DEAD_LETTERED"
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_kill_discards_late_completion():
    async def ignores_cancel(p, *, run_provenance=None):
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            await asyncio.sleep(0.05)
            return {"late_after_kill": True}
        return {"done": True}

    s = _mk({"k": ignores_cancel}, run_timeout_sec=10.0, max_attempts=1)
    await s.start()
    res = await s.enqueue("k", {"x": 1}, idempotency_key="kk1")
    detail_running = await _wait_state(s, res["run_id"], {"RUNNING"})
    assert detail_running["state"] == "RUNNING"
    await s.set_kill_switch("ENGAGE", actor="owner", reason="drill")
    detail = s.run_detail(res["run_id"])
    assert detail["state"] == "KILLED"
    await asyncio.sleep(0.3)  # the late completion lands here
    types = [e["event_type"] for e in s.run_detail(res["run_id"])["events"]]
    assert "SUCCEEDED" not in types and "COMPLETED" not in types
    assert s.posture()["counters"]["killed_total"] == 1


# ---------------------------------------------------------------------------
# Retries + dead-letter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_then_complete():
    calls = []
    s = _mk({"flaky": _flaky_handler(calls)}, max_attempts=2)
    await s.start()
    res = await s.enqueue("flaky", {"x": 1}, idempotency_key="r1")
    detail = await _wait_state(s, res["run_id"], {"COMPLETED"})
    types = [e["event_type"] for e in detail["events"]]
    assert "FAILED_ATTEMPT" in types and "RETRY_QUEUED" in types
    assert detail["attempts"] == 2
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_dead_letter_after_bounded_retries():
    s = _mk({"bad": _failing_handler()}, max_attempts=2)
    await s.start()
    res = await s.enqueue("bad", {"x": 1}, idempotency_key="d1")
    detail = await _wait_state(s, res["run_id"], {"DEAD_LETTERED"})
    failed = [e for e in detail["events"] if e["event_type"] == "FAILED_ATTEMPT"]
    assert len(failed) == 2  # bounded attempts, exactly
    assert failed[0]["payload"]["error"].startswith("RuntimeError")
    assert detail["state"] == "DEAD_LETTERED"
    assert s.posture()["counters"]["dead_lettered_total"] == 1
    await s.stop(actor="tester")


# ---------------------------------------------------------------------------
# pause / resume / stop / kill-switch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pause_holds_and_resume_dispatches():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    await s.pause(actor="tester")
    res = await s.enqueue("stub", {"x": 1}, idempotency_key="p1")
    await asyncio.sleep(0.1)
    assert s.run_detail(res["run_id"])["state"] == "QUEUED"  # held
    assert s.posture()["queue_depth"] == 1
    await s.resume(actor="tester")
    await _wait_state(s, res["run_id"], {"COMPLETED"})
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_resume_requires_paused():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    with pytest.raises(SchedulerRefused) as exc:
        await s.resume(actor="tester")
    assert exc.value.code == "resume_requires_paused"
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_stop_cancels_queued_and_refuses():
    s = _mk({"stub": _ok_handler()})
    await s.start()
    await s.pause(actor="tester")
    r1 = await s.enqueue("stub", {"x": 1}, idempotency_key="s1")
    r2 = await s.enqueue("stub", {"x": 2}, idempotency_key="s2")
    await s.stop(actor="owner", drain=False)
    assert s.run_detail(r1["run_id"])["state"] == "CANCELLED"
    assert s.run_detail(r2["run_id"])["state"] == "CANCELLED"
    assert s.posture()["state"] == "stopped"
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("stub", {"x": 3}, idempotency_key="s3")
    assert exc.value.code == "scheduler_stopped"


@pytest.mark.asyncio
async def test_kill_switch_engage_blocks_and_kills():
    async def slowish(p, *, run_provenance=None):
        await asyncio.sleep(2.0)
        return {"done": True}

    s = _mk({"slow": slowish})
    await s.start()
    res = await s.enqueue("slow", {"x": 1}, idempotency_key="k1")
    await _wait_state(s, res["run_id"], {"RUNNING"})
    result = await s.set_kill_switch("ENGAGE", actor="owner", reason="safety drill")
    assert result["kill_switch"] == "ENGAGED"
    assert s.run_detail(res["run_id"])["state"] == "KILLED"
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("slow", {"x": 2}, idempotency_key="k2")
    assert exc.value.code == "kill_switch_engaged"
    await s.set_kill_switch("RELEASE", actor="owner", reason="drill over")
    ok = await s.enqueue("slow", {"x": 3}, idempotency_key="k3")
    assert ok["ok"] is True
    await s.stop(actor="tester")


@pytest.mark.asyncio
async def test_kill_switch_state_malformed():
    s = _mk({"stub": _ok_handler()})
    with pytest.raises(SchedulerRefused) as exc:
        await s.set_kill_switch("ENGAGED!", actor="owner", reason="bad")
    assert exc.value.code == "kill_switch_state_malformed"


# ---------------------------------------------------------------------------
# Restart recovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restart_recovery_interrupts_nonterminal():
    store = MemorySchedulerRunStore()
    s1 = InternalScheduler(
        store, {"stub": _ok_handler()}, enabled=True,
        max_queue=8, max_concurrent=1, run_timeout_sec=5.0, max_attempts=2,
        clock=FakeClock(), now_utc=_now_utc,
    )
    await s1.start()
    await s1.pause(actor="tester")
    res = await s1.enqueue("stub", {"x": 1}, idempotency_key="rec1")
    assert s1.run_detail(res["run_id"])["state"] == "QUEUED"
    # Process "restart": a NEW scheduler over the SAME history recovers.
    s2 = InternalScheduler(
        store, {"stub": _ok_handler()}, enabled=True,
        max_queue=8, max_concurrent=1, run_timeout_sec=5.0, max_attempts=2,
        clock=FakeClock(), now_utc=_now_utc,
    )
    recovered = await s2.recover_on_startup()
    assert recovered == 1
    detail = s2.run_detail(res["run_id"])
    assert detail["state"] == "INTERRUPTED"
    assert detail["terminal"] is True
    # start() recovers automatically too (and refuses double recovery harm)
    store2 = MemorySchedulerRunStore()
    s3 = InternalScheduler(
        store2, {"stub": _ok_handler()}, enabled=True,
        max_queue=8, max_concurrent=1, run_timeout_sec=5.0, max_attempts=2,
        clock=FakeClock(), now_utc=_now_utc,
    )
    out = await s3.start()
    assert out["recovered_interrupted"] == 0  # nothing non-terminal in store2
    await s3.stop(actor="tester")


# ---------------------------------------------------------------------------
# Store integrity (append-only ledger, digests, migrations, backup)
# ---------------------------------------------------------------------------

def test_store_unknown_event_type_rejected():
    store = MemorySchedulerRunStore()
    with pytest.raises(SchedulerRunStoreError):
        store.append_event(
            event_id="e1", run_id="r1", event_type="NOT_A_REAL_EVENT",
            at_utc=_NOW.isoformat(), actor="t", payload={},
        )


def test_store_event_id_conflict_and_idempotent_reappend():
    store = MemorySchedulerRunStore()
    body = dict(event_id="e1", run_id="r1", event_type="ENQUEUED",
                at_utc=_NOW.isoformat(), actor="t", payload={"a": 1})
    appended, _ = store.append_event(**body)
    assert appended is True
    again, dup_ok = store.append_event(**body)
    assert again is False and dup_ok is True  # byte-identical = idempotent no-op
    with pytest.raises(SchedulerRunStoreError) as exc:
        store.append_event(event_id="e1", run_id="r1", event_type="ENQUEUED",
                           at_utc=_NOW.isoformat(), actor="t", payload={"a": 2})
    assert "conflict" in str(exc.value)


def test_derive_run_state_transitions():
    ev = lambda t, p=None, at="2026-11-06T08:00:00+00:00": {"event_type": t, "payload": p or {}, "at_utc": at}
    d = derive_run_state([ev("ENQUEUED")])
    assert d["state"] == "QUEUED" and d["terminal"] is False
    d = derive_run_state([ev("ENQUEUED"), ev("STARTED")])
    assert d["state"] == "RUNNING"
    d = derive_run_state([ev("ENQUEUED"), ev("STARTED"), ev("SUCCEEDED", {"outcome_digest": "x"}), ev("COMPLETED")])
    assert d["state"] == "COMPLETED" and d["terminal"] is True
    assert d["outcome_digest"] == "x"
    d = derive_run_state([ev("ENQUEUED"), ev("STARTED"), ev("FAILED_ATTEMPT", {"attempt": 1, "error": "e"}), ev("RETRY_QUEUED")])
    assert d["state"] == "QUEUED" and d["attempts"] == 1 and d["retry_queued"] == 1
    d = derive_run_state([ev("ENQUEUED"), ev("STARTED"), ev("INTERRUPTED")])
    assert d["state"] == "INTERRUPTED" and d["terminal"] is True
    d = derive_run_state([ev("ENQUEUED"), ev("KILLED")])
    assert d["state"] == "KILLED" and d["terminal"] is True


def test_durable_store_row_digest_tamper_fails_closed(tmp_path: Path):
    db = tmp_path / "hist.sqlite3"
    store = DurableSchedulerRunStore(db)
    store.append_event(event_id="e1", run_id="r1", event_type="ENQUEUED",
                       at_utc=_NOW.isoformat(), actor="t", payload={"a": 1})
    assert store.verify_all_rows() == 1
    store.close()
    # Tamper directly under the store's feet:
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE scheduler_run_events SET payload=? WHERE event_id='e1'",
        ('{"a": 999, "event_id": "e1", "run_id": "r1", "event_type": "ENQUEUED", '
         '"at_utc": "%s", "actor": "t", "payload": {"a": 1}}' % _NOW.isoformat(),),
    )
    conn.commit()
    conn.close()
    with pytest.raises(SchedulerRunStoreCorruption):
        DurableSchedulerRunStore(db)


def test_durable_store_schema_digest_mismatch_fails_closed(tmp_path: Path):
    db = tmp_path / "hist2.sqlite3"
    store = DurableSchedulerRunStore(db)
    store.close()
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE scheduler_migrations SET sql_digest='deadbeef'")
    conn.commit()
    conn.close()
    with pytest.raises(SchedulerRunStoreCorruption):
        DurableSchedulerRunStore(db)


def test_durable_store_backup_restore_roundtrip(tmp_path: Path):
    db = tmp_path / "hist3.sqlite3"
    store = DurableSchedulerRunStore(db)
    for i in range(3):
        store.append_event(event_id=f"e{i}", run_id=f"r{i}", event_type="ENQUEUED",
                           at_utc=_NOW.isoformat(), actor="t", payload={"i": i})
    backup = store.backup(tmp_path / "backups", keep=3)
    assert backup.is_file()
    store.append_event(event_id="e-after", run_id="r-after", event_type="ENQUEUED",
                       at_utc=_NOW.isoformat(), actor="t", payload={"after": True})
    assert store.verify_all_rows() == 4
    restored = store.restore_from(backup)
    assert restored == 3  # post-backup event is gone (restore is authoritative)
    assert store.verify_all_rows() == 3
    assert store.find_run_by_idempotency_key("missing") is None
    store.close()


def test_durable_store_idempotency_key_lookup(tmp_path: Path):
    db = tmp_path / "hist4.sqlite3"
    store = DurableSchedulerRunStore(db)
    store.append_event(
        event_id="e1", run_id="run-abc", event_type="ENQUEUED",
        at_utc=_NOW.isoformat(), actor="t",
        payload={"job_type": "stub", "idempotency_key": "idem-42",
                 "payload_digest": "d", "actor": "t"},
    )
    assert store.find_run_by_idempotency_key("idem-42") == "run-abc"
    assert store.find_run_by_idempotency_key("nope") is None
    store.close()


# ---------------------------------------------------------------------------
# WAVE-M independent-QA remediation pins (M1/M3/M4 + L1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_refused_while_disabled():
    """M1: the honesty envelope claim is TRUE — stop() refuses while the
    gate is closed and records nothing."""
    s = _mk({"stub": _ok_handler()}, enabled=False)
    with pytest.raises(SchedulerRefused) as exc:
        await s.stop(actor="tester")
    assert exc.value.code == "scheduler_disabled"
    assert s._store.all_events(100) == []


@pytest.mark.asyncio
async def test_kill_switch_refused_while_disabled():
    """M1: kill-switch transitions are gate-gated too (no history writes)."""
    s = _mk({"stub": _ok_handler()}, enabled=False)
    with pytest.raises(SchedulerRefused) as exc:
        await s.set_kill_switch("ENGAGE", actor="owner", reason="drill")
    assert exc.value.code == "scheduler_disabled"
    with pytest.raises(SchedulerRefused):
        await s.set_kill_switch("RELEASE", actor="owner", reason="drill")
    assert s._store.all_events(100) == []


@pytest.mark.asyncio
async def test_kill_cancels_inner_handler():
    """M4: the governed HANDLER task itself is cancelled on kill — no
    orphaned handler keeps running detached after KILL."""
    cancelled_flag = {"inner": False}

    async def cancellable(p, *, run_provenance=None):
        try:
            await asyncio.sleep(5.0)
            return {"done": True}
        except asyncio.CancelledError:
            cancelled_flag["inner"] = True
            raise

    s = _mk({"c": cancellable})
    await s.start()
    res = await s.enqueue("c", {"x": 1}, idempotency_key="m4")
    await _wait_state(s, res["run_id"], {"RUNNING"})
    await s.set_kill_switch("ENGAGE", actor="owner", reason="m4 drill")
    assert s.run_detail(res["run_id"])["state"] == "KILLED"
    deadline = asyncio.get_event_loop().time() + 2.0
    while not cancelled_flag["inner"] and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.02)
    assert cancelled_flag["inner"] is True
    assert s._inner == {}  # tracked handler tasks are cleaned up


@pytest.mark.asyncio
async def test_idempotency_conflict_different_job_type():
    """L1: same key + same payload + different job_type is a conflict, not
    a silent misattributed replay."""
    s = _mk({"stub": _ok_handler(), "other": _ok_handler()})
    await s.start()
    await s.enqueue("stub", {"x": 1}, idempotency_key="jt-1")
    with pytest.raises(SchedulerRefused) as exc:
        await s.enqueue("other", {"x": 1}, idempotency_key="jt-1")
    assert exc.value.code == "idempotency_conflict"
    await s.stop(actor="tester")


def test_durable_runs_index_excludes_scheduler_level_events(tmp_path: Path):
    """M3: PAUSED/RESUMED/STOPPED/KILL_* carry run_id '' (lifecycle
    records) and MUST NOT appear as phantom pseudo-runs in the index."""
    db = tmp_path / "phantom.sqlite3"
    store = DurableSchedulerRunStore(db)
    store.append_event(event_id="r", run_id="real-run", event_type="ENQUEUED",
                       at_utc=_NOW.isoformat(), actor="t",
                       payload={"job_type": "stub", "idempotency_key": "k"})
    for i, ev in enumerate(("PAUSED", "RESUMED", "KILL_ENGAGED", "KILL_RELEASED", "STOPPED")):
        store.append_event(event_id=f"l{i}", run_id="", event_type=ev,
                           at_utc=_NOW.isoformat(), actor="t", payload={})
    index = store.runs_index(limit=50)
    assert [e["run_id"] for e in index] == ["real-run"]  # no phantom ''
    assert store.all_events(100)
    store.close()


@pytest.mark.asyncio
async def test_durable_restart_recovery_no_phantom(tmp_path: Path):
    """M3 (recovery side): restart recovery closes exactly the real
    non-terminal runs — a history full of lifecycle events recovers 0."""
    db = tmp_path / "rec.sqlite3"
    store = DurableSchedulerRunStore(db)
    s1 = InternalScheduler(
        store, {"stub": _ok_handler()}, enabled=True,
        max_queue=8, max_concurrent=1, run_timeout_sec=5.0, max_attempts=2,
        clock=FakeClock(), now_utc=_now_utc,
    )
    await s1.start()
    await s1.pause(actor="tester")
    seeded = await s1.enqueue("stub", {"x": 1}, idempotency_key="rec2")
    s1._store.close()
    # fresh process over the SAME durable history
    store2 = DurableSchedulerRunStore(db)
    s2 = InternalScheduler(
        store2, {"stub": _ok_handler()}, enabled=True,
        max_queue=8, max_concurrent=1, run_timeout_sec=5.0, max_attempts=2,
        clock=FakeClock(), now_utc=_now_utc,
    )
    out = await s2.start()
    assert out["recovered_interrupted"] == 1  # exactly the one real run
    detail = s2.run_detail(seeded["run_id"])
    assert detail["state"] == "INTERRUPTED" and detail["terminal"]
    await s2.stop(actor="tester")
    store2.close()


# ---------------------------------------------------------------------------
# Structural guarantees
# ---------------------------------------------------------------------------

def test_no_egress_structural():
    import pathlib
    for name in (
        "internal_scheduler.py",
        "scheduler_run_store.py",
        "scheduler_jobs.py",
    ):
        text = pathlib.Path("app/services", name).read_text(encoding="utf-8")
        for banned in ("httpx", "requests.", "urllib", "socket", "subprocess",
                       "smtplib", "telegram", "webhook", "aiohttp"):
            assert banned not in text, f"{name}: {banned}"


def test_no_settings_access_after_construction():
    import pathlib
    text = pathlib.Path("app/services/internal_scheduler.py").read_text(encoding="utf-8")
    # get_settings appears EXACTLY twice (import + call), both confined to
    # the composition-root function — the service class never reads it.
    assert text.count("get_settings") == 2
    root = text.split("def get_scheduler", 1)[1]
    service_part = text.split("def get_scheduler", 1)[0]
    assert "get_settings" not in service_part  # class bodies have none
    assert root.count("get_settings") == 2
    assert text.count("AI2_ENABLED") == 0
    assert text.count("os.getenv") == 0


def test_scheduler_api_file_is_generic():
    """The G2 counter-pin discipline: the generic scheduler HTTP surface
    carries no reference naming the governed generation seam."""
    import pathlib
    text = pathlib.Path("app/api/scheduler_api.py").read_text(encoding="utf-8")
    import re as _re
    assert not _re.search(r"\bai2\b", text, _re.IGNORECASE)
    for banned in ("asyncio.create_task", "BackgroundTasks", "httpx", "requests.",
                   "urllib", "socket", "subprocess"):
        assert banned not in text, banned


def test_composition_root_registers_governed_handler():
    reset_scheduler_cache()
    reset_scheduler_run_store_cache()
    import os
    old_backend = os.environ.get("SCHEDULER_STORE_BACKEND")
    os.environ["SCHEDULER_STORE_BACKEND"] = "memory"
    try:
        s = get_scheduler()
        assert s.posture()["registered_job_types"] == ["research_loop"]
        assert s.posture()["enabled"] is False  # committed default gate
    finally:
        if old_backend is None:
            os.environ.pop("SCHEDULER_STORE_BACKEND", None)
        else:
            os.environ["SCHEDULER_STORE_BACKEND"] = old_backend
        reset_scheduler_cache()
        reset_scheduler_run_store_cache()


# ---------------------------------------------------------------------------
# Governed research-loop handler
# ---------------------------------------------------------------------------

def _valid_payload() -> dict:
    import hashlib
    snapshot = hashlib.sha256(b"deterministic-context").hexdigest()
    return {
        "question": "تست سنتز استراتژی (paper)",
        "task": "strategy",
        "record_id": "sched-rec-1",
        "run_id": "sched-run-1",
        "policy_version": "gov-1",
        "input_snapshot_sha256": snapshot,
    }


@pytest.mark.asyncio
async def test_research_loop_handler_gated_honest():
    summary = await research_loop_handler(_valid_payload(), run_provenance={"run_id": "sched-run-1", "attempt": 1})
    assert summary["job"] == "research_loop"
    assert summary["outcome"] == "gated_not_executed"
    assert summary["ok"] is False
    assert summary["ledger_status"] == "GATED_NOT_EXECUTED"
    assert summary["execution_domain"] == "SYNTHETIC_OR_PAPER"
    assert summary["note"]


@pytest.mark.asyncio
async def test_research_loop_handler_refuses_bad_payload():
    bad = _valid_payload()
    bad["input_snapshot_sha256"] = "not-hex"  # malformed snapshot
    summary = await research_loop_handler(bad, run_provenance={})
    assert summary["outcome"] == "payload_refused"
    assert summary["executed"] is False
    assert summary["refusal_reason"]


@pytest.mark.asyncio
async def test_research_loop_handler_refuses_unknown_task():
    bad = _valid_payload()
    bad["task"] = "trading"  # outside the closed task set
    summary = await research_loop_handler(bad, run_provenance={})
    assert summary["outcome"] == "payload_refused"
