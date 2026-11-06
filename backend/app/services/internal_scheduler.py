"""Internal research scheduler (WAVE-M, OA-4; 2026-11-06).

Additive module — nothing existing is modified. A LOCAL, bounded,
read-only-over-the-product scheduler for synthetic/paper research jobs:

- FAIL-CLOSED: the ``enabled`` flag is injected at construction (the
  composition root reads settings ONCE). With the default
  (``SCHEDULER_ENABLED=0``) ``start()`` and ``enqueue()`` refuse and
  nothing is ever scheduled or executed.
- The scheduler NEVER reads or writes settings after construction, NEVER
  constructs a network client, and has NO egress/notification/broker
  surface of any kind. Its only side effects are (a) run-history events in
  the injected store and (b) invocation of the injected handler callables.
- It CANNOT bypass AI-2 or Two-Key gates: handlers run UNDER their own
  governance. The built-in research-loop handler delegates to the existing
  governed research-loop runner whose own fail-closed gates (committed
  defaults refuse execution, synthetic/paper-only transport policy) still
  apply — a scheduled run into closed gates yields an honest
  ``gated_not_executed`` ledger record, never an execution. This module
  itself never reads, writes, or names any AI-2 gate.
- BOUNDED: queue-depth cap, max-concurrency cap, per-run wall-time budget,
  bounded retries (exhausted attempts → immutable DEAD_LETTERED state),
  bounded payload/output sizes, bounded history reads.
- RELIABLE: run identity (uuid), idempotency keys (identical replay is a
  no-op; conflicting payload under the same key is refused), pause/resume,
  graceful stop, kill-switch, restart recovery (non-terminal runs found at
  startup are closed INTERRUPTED — never silently dropped, never
  auto-resumed), late-completion containment (a result arriving after
  timeout/kill is discarded, never committed), immutable append-only run
  history with row digests.

Clock discipline (repository style): wall-time DURATIONS come from the
injected ``clock`` (default ``time.monotonic``); wall-clock INSTANTS come
from the injected ``now_utc`` (default UTC now). The asyncio dispatch
budgets use the event-loop's own clock — an honest, disclosed limitation
``posture()`` reports verbatim.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.services.scheduler_run_store import (
    get_scheduler_run_store,
)

__all__ = [
    "SchedulerRefused",
    "JobHandler",
    "InternalScheduler",
    "get_scheduler",
    "reset_scheduler_cache",
    "PAYLOAD_MAX_BYTES",
    "OUTCOME_MAX_BYTES",
]

#: Bounded payload / output caps (fixed engineering-authority ceilings).
PAYLOAD_MAX_BYTES = 65536
OUTCOME_MAX_BYTES = 65536
_ERROR_MAX_CHARS = 500

JobHandler = Callable[..., Awaitable[Dict[str, Any]]]


class SchedulerRefused(Exception):
    """Honest refusal with a machine-readable reason code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest_of(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _bounded_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return text[:_ERROR_MAX_CHARS]


class InternalScheduler:
    """Bounded local scheduler over an injected handler registry + store."""

    def __init__(
        self,
        store: Any,
        handlers: Dict[str, JobHandler],
        *,
        enabled: bool = False,
        max_queue: int = 32,
        max_concurrent: int = 1,
        run_timeout_sec: float = 60.0,
        max_attempts: int = 2,
        clock: Callable[[], float] | None = None,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        if max_queue < 1 or max_concurrent < 1 or run_timeout_sec <= 0 or max_attempts < 1:
            raise SchedulerRefused("scheduler_bounds_invalid")
        self._store = store
        self._handlers: Dict[str, JobHandler] = dict(handlers)
        self._enabled = bool(enabled)
        self._max_queue = int(max_queue)
        self._max_concurrent = int(max_concurrent)
        self._run_timeout_sec = float(run_timeout_sec)
        self._max_attempts = int(max_attempts)
        self._clock = clock if clock is not None else time.monotonic
        self._now_utc = now_utc if now_utc is not None else (
            lambda: datetime.now(timezone.utc)
        )
        self._state = "created"  # created | running | paused | stopped
        self._kill_engaged = False
        self._queue: List[str] = []  # pending run_ids (FIFO, bounded)
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._active: Dict[str, asyncio.Task] = {}
        self._inner: Dict[str, asyncio.Task] = {}  # run_id → handler task
        self._attempts: Dict[str, int] = {}
        self._wakeup = asyncio.Event()
        self._worker: Optional[asyncio.Task] = None
        self._counters: Dict[str, int] = {
            "enqueued_total": 0,
            "executed_total": 0,
            "completed_total": 0,
            "failed_total": 0,
            "timed_out_total": 0,
            "killed_total": 0,
            "cancelled_total": 0,
            "dead_lettered_total": 0,
            "interrupted_recovered_total": 0,
            "refused_total": 0,
        }

    # ------------------------------------------------------------- helpers
    def _utc(self) -> str:
        return self._now_utc().isoformat()

    def _record(self, counters_key: str) -> None:
        self._counters[counters_key] = self._counters.get(counters_key, 0) + 1

    async def _append(
        self,
        *,
        run_id: str,
        event_type: str,
        actor: str,
        payload: Dict[str, Any],
    ) -> str:
        event_id = uuid.uuid4().hex
        self._store.append_event(
            event_id=event_id,
            run_id=run_id,
            event_type=event_type,
            at_utc=self._utc(),
            actor=actor,
            payload=payload,
        )
        return event_id

    def config_fingerprint(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "max_queue": self._max_queue,
            "max_concurrent": self._max_concurrent,
            "run_timeout_sec": self._run_timeout_sec,
            "max_attempts": self._max_attempts,
            "registered_job_types": sorted(self._handlers.keys()),
            "store_backend": getattr(self._store, "backend_label", "unknown"),
        }

    # -------------------------------------------------------------- posture
    def posture(self) -> Dict[str, Any]:
        return {
            "scheduler": "internal_research_scheduler",
            "enabled": self._enabled,
            "state": self._state,
            "kill_switch": "ENGAGED" if self._kill_engaged else "RELEASED",
            "queue_depth": len(self._queue),
            "active_runs": len(self._active),
            "registered_job_types": sorted(self._handlers.keys()),
            "bounded_by": {
                "max_queue": self._max_queue,
                "max_concurrent": self._max_concurrent,
                "run_timeout_sec": self._run_timeout_sec,
                "max_attempts": self._max_attempts,
                "payload_max_bytes": PAYLOAD_MAX_BYTES,
                "outcome_max_bytes": OUTCOME_MAX_BYTES,
            },
            "counters": dict(self._counters),
            "honesty": {
                "local_only": "زمان‌بند فقط محلی است؛ هیچ خروجی بیرونی/اعلان/بروکر ندارد",
                "no_egress": "no external notification egress exists by construction",
                "no_settings_access": "settings are read ONCE by the composition root; the service never reads/writes them",
                "gate_respect": "handlers run under their own governance; closed gates yield honest gated_not_executed records, never an execution",
                "dispatch_clock": "asyncio dispatch budgets use the event-loop clock; recorded durations use the injected monotonic clock",
                "execution_domain": "SYNTHETIC_OR_PAPER",
                "history": "append-only event ledger with row digests; restart closes non-terminal runs as INTERRUPTED",
            },
            "config_fingerprint": self.config_fingerprint(),
        }

    # ------------------------------------------------------------ lifecycle
    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        if job_type in self._handlers:
            raise SchedulerRefused("job_type_already_registered")
        self._handlers[job_type] = handler

    async def start(self) -> Dict[str, Any]:
        if not self._enabled:
            self._counters["refused_total"] += 1
            raise SchedulerRefused("scheduler_disabled")
        if self._state == "running":
            return {"ok": True, "already_running": True}
        if self._state == "stopped":
            raise SchedulerRefused("scheduler_stopped")
        # Restart recovery FIRST: any non-terminal run in the durable
        # history is closed INTERRUPTED (never auto-resumed).
        recovered = await self.recover_on_startup()
        self._state = "running"
        self._wakeup.clear()
        self._worker = asyncio.create_task(self._worker_loop())
        return {"ok": True, "recovered_interrupted": recovered}

    async def recover_on_startup(self) -> int:
        recovered = 0
        for entry in self._store.runs_index(limit=200):
            if entry.get("terminal"):
                continue
            run_id = entry["run_id"]
            self._store.append_event(
                event_id=uuid.uuid4().hex,
                run_id=run_id,
                event_type="INTERRUPTED",
                at_utc=self._utc(),
                actor="scheduler_recovery",
                payload={
                    "reason": "non_terminal_run_at_startup",
                    "prior_state": entry.get("state"),
                    "recovered_at_startup": True,
                },
            )
            recovered += 1
        self._counters["interrupted_recovered_total"] += recovered
        return recovered

    async def pause(self, *, actor: str) -> Dict[str, Any]:
        if self._state != "running":
            raise SchedulerRefused("pause_requires_running")
        self._state = "paused"
        await self._append(run_id="", event_type="PAUSED", actor=actor, payload={})
        return {"ok": True, "state": self._state}

    async def resume(self, *, actor: str) -> Dict[str, Any]:
        if self._state != "paused":
            raise SchedulerRefused("resume_requires_paused")
        if self._kill_engaged:
            raise SchedulerRefused("kill_switch_engaged")
        self._state = "running"
        await self._append(run_id="", event_type="RESUMED", actor=actor, payload={})
        self._wakeup.set()
        return {"ok": True, "state": self._state}

    async def stop(self, *, actor: str, drain: bool = False) -> Dict[str, Any]:
        if not self._enabled:
            self._record("refused_total")
            raise SchedulerRefused("scheduler_disabled")
        if self._state == "stopped":
            return {"ok": True, "already_stopped": True}
        if not drain:
            # queued (not yet dispatched) runs → CANCELLED, immutably
            for run_id in list(self._queue):
                await self._append(
                    run_id=run_id,
                    event_type="CANCELLED",
                    actor=actor,
                    payload={"reason": "scheduler_stop"},
                )
                self._record("cancelled_total")
            self._queue.clear()
        self._state = "stopped"
        self._wakeup.set()
        worker = self._worker
        if worker is not None:
            try:
                await asyncio.wait_for(asyncio.shield(worker), timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                worker.cancel()
            except Exception:
                pass
            self._worker = None
        await self._append(run_id="", event_type="STOPPED", actor=actor, payload={"drain": bool(drain)})
        return {"ok": True, "state": self._state}

    async def set_kill_switch(self, state: str, *, actor: str, reason: str) -> Dict[str, Any]:
        if not self._enabled:
            self._record("refused_total")
            raise SchedulerRefused("scheduler_disabled")
        normalized = str(state).strip().upper()
        if normalized not in {"ENGAGE", "RELEASE"}:
            raise SchedulerRefused("kill_switch_state_malformed")
        if normalized == "ENGAGE":
            self._kill_engaged = True
            # Kill every active run immediately; late completions discarded.
            # BOTH the wrapper and the inner handler task are cancelled —
            # an orphaned handler must not keep running detached after KILL.
            for run_id, task in list(self._active.items()):
                inner = self._inner.get(run_id)
                if inner is not None and not inner.done():
                    inner.cancel()
                if not task.done():
                    task.cancel()
                await self._append(
                    run_id=run_id,
                    event_type="KILLED",
                    actor=actor,
                    payload={"reason": reason[:_ERROR_MAX_CHARS], "kill_switch": True},
                )
                self._record("killed_total")
            self._active.clear()
            self._queue.clear()
            await self._append(run_id="", event_type="KILL_ENGAGED", actor=actor, payload={"reason": reason[:_ERROR_MAX_CHARS]})
            return {"ok": True, "kill_switch": "ENGAGED", "state": self._state}
        self._kill_engaged = False
        await self._append(run_id="", event_type="KILL_RELEASED", actor=actor, payload={"reason": reason[:_ERROR_MAX_CHARS]})
        return {"ok": True, "kill_switch": "RELEASED", "state": self._state}

    # -------------------------------------------------------------- enqueue
    async def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        *,
        idempotency_key: str,
        actor: str = "api-user",
    ) -> Dict[str, Any]:
        if not self._enabled:
            self._record("refused_total")
            raise SchedulerRefused("scheduler_disabled")
        if self._state == "stopped":
            self._record("refused_total")
            raise SchedulerRefused("scheduler_stopped")
        if self._kill_engaged:
            self._record("refused_total")
            raise SchedulerRefused("kill_switch_engaged")
        if self._state == "created":
            self._record("refused_total")
            raise SchedulerRefused("scheduler_not_started")
        if not isinstance(payload, dict):
            self._record("refused_total")
            raise SchedulerRefused("payload_must_be_object")
        if job_type not in self._handlers:
            self._record("refused_total")
            raise SchedulerRefused("unknown_job_type")
        key = str(idempotency_key).strip()
        if not key or len(key) > 128:
            self._record("refused_total")
            raise SchedulerRefused("idempotency_key_malformed")
        payload_digest = _digest_of(payload)
        try:
            canonical_len = len(_canonical(payload).encode("utf-8"))
        except (TypeError, ValueError):
            self._record("refused_total")
            raise SchedulerRefused("payload_not_canonicalizable")
        if canonical_len > PAYLOAD_MAX_BYTES:
            self._record("refused_total")
            raise SchedulerRefused("payload_oversized")

        # Idempotency: identical (key, job_type, payload) → replay, never
        # re-execution; a different payload OR a different job_type under the
        # same key → conflict refusal (no silent misattribution).
        existing_run = self._store.find_run_by_idempotency_key(key)
        if existing_run is not None:
            events = self._store.events_for_run(existing_run)
            derived = _derive_from(events)
            enq = next(
                (e for e in events if e["event_type"] == "ENQUEUED"), None
            )
            if (
                enq is not None
                and (enq["payload"] or {}).get("payload_digest") == payload_digest
                and (enq["payload"] or {}).get("job_type") == job_type
            ):
                return {
                    "ok": True,
                    "run_id": existing_run,
                    "replayed": True,
                    "state": derived["state"],
                    "note": "idempotent replay; no re-execution",
                }
            self._record("refused_total")
            raise SchedulerRefused(
                "idempotency_conflict",
                "same idempotency_key with a different payload or job_type",
            )

        if len(self._queue) >= self._max_queue:
            self._record("refused_total")
            raise SchedulerRefused("queue_full")

        run_id = uuid.uuid4().hex
        self._store.append_event(
            event_id=uuid.uuid4().hex,
            run_id=run_id,
            event_type="ENQUEUED",
            at_utc=self._utc(),
            actor=actor,
            payload={
                "job_type": job_type,
                "idempotency_key": key,
                "payload_digest": payload_digest,
                "actor": actor,
                "execution_domain": "SYNTHETIC_OR_PAPER",
                "config_fingerprint": self.config_fingerprint(),
            },
        )
        self._runs[run_id] = {
            "job_type": job_type,
            "payload": payload,
            "payload_digest": payload_digest,
            "idempotency_key": key,
            "actor": actor,
        }
        self._attempts[run_id] = 0
        self._queue.append(run_id)
        self._record("enqueued_total")
        self._wakeup.set()
        return {"ok": True, "run_id": run_id, "replayed": False, "state": "QUEUED"}

    # --------------------------------------------------------------- worker
    async def _worker_loop(self) -> None:
        while True:
            if self._state == "stopped":
                return
            if self._kill_engaged or self._state == "paused" or not self._queue or len(self._active) >= self._max_concurrent:
                self._wakeup.clear()
                await self._wakeup.wait()
                continue
            run_id = self._queue.pop(0)
            run = self._runs.get(run_id)
            if run is None:
                continue
            self._attempts[run_id] = self._attempts.get(run_id, 0) + 1
            attempt = self._attempts[run_id]
            task = asyncio.create_task(self._run_one(run_id, run, attempt))
            self._active[run_id] = task
            # Wake the dispatcher when the slot frees, else queued runs
            # would sleep forever under max_concurrent back-pressure.
            task.add_done_callback(
                lambda _t, rid=run_id: (
                    self._active.pop(rid, None),
                    self._inner.pop(rid, None),
                    self._wakeup.set(),
                )
            )

    async def _run_one(self, run_id: str, run: Dict[str, Any], attempt: int) -> None:
        job_type = run["job_type"]
        handler = self._handlers[job_type]
        started_wall = self._clock()
        await self._append(
            run_id=run_id,
            event_type="STARTED",
            actor=run["actor"],
            payload={"attempt": attempt, "job_type": job_type},
        )
        self._record("executed_total")
        provenance = {
            "run_id": run_id,
            "attempt": attempt,
            "job_type": job_type,
            "actor": run["actor"],
            "enqueued_payload_digest": run["payload_digest"],
            "scheduler_config": self.config_fingerprint(),
            "execution_domain": "SYNTHETIC_OR_PAPER",
        }
        inner = asyncio.create_task(handler(run["payload"], run_provenance=provenance))
        self._inner[run_id] = inner
        try:
            done, _pending = await asyncio.wait({inner}, timeout=self._run_timeout_sec)
            wall = self._clock() - started_wall

            # Kill path already recorded KILLED and cancelled the inner task.
            if inner.cancelled() and self._kill_engaged:
                return
            if inner.cancelled():
                await self._append(
                    run_id=run_id,
                    event_type="CANCELLED",
                    actor=run["actor"],
                    payload={"reason": "cancelled_during_execution"},
                )
                self._record("cancelled_total")
                return

            if not done:
                # Per-run wall-time budget exceeded. Containment: cancel the
                # handler and DISCARD any late completion — it is never committed.
                inner.cancel()
                try:
                    await asyncio.wait({inner}, timeout=5.0)
                except Exception:
                    pass
                self._record("timed_out_total")
                await self._fail_or_retry(
                    run_id=run_id,
                    run=run,
                    attempt=attempt,
                    error=f"run_timeout:{self._run_timeout_sec}s",
                    event_type="TIMED_OUT",
                    wall=wall,
                )
                return

            exc = inner.exception()
            if exc is not None:
                self._record("failed_total")
                await self._fail_or_retry(
                    run_id=run_id,
                    run=run,
                    attempt=attempt,
                    error=_bounded_error(exc),
                    event_type="FAILED_ATTEMPT",
                    wall=wall,
                )
                return

            result = inner.result()
            try:
                outcome_canonical = _canonical(result if isinstance(result, dict) else {"value": result})
            except (TypeError, ValueError):
                outcome_canonical = _canonical({"error": "outcome_not_canonicalizable"})
            if len(outcome_canonical.encode("utf-8")) > OUTCOME_MAX_BYTES:
                outcome_canonical = _canonical({"truncated": True, "outcome_digest_note": "outcome_oversized_replaced"})
            outcome_digest = hashlib.sha256(outcome_canonical.encode("utf-8")).hexdigest()
            await self._append(
                run_id=run_id,
                event_type="SUCCEEDED",
                actor=run["actor"],
                payload={
                    "attempt": attempt,
                    "wall_seconds": round(wall, 6),
                    "outcome_digest": outcome_digest,
                    "outcome": json.loads(outcome_canonical),
                },
            )
            await self._append(
                run_id=run_id,
                event_type="COMPLETED",
                actor=run["actor"],
                payload={"attempts": attempt, "outcome_digest": outcome_digest},
            )
            self._record("completed_total")
        finally:
            self._inner.pop(run_id, None)

    async def _fail_or_retry(
        self,
        *,
        run_id: str,
        run: Dict[str, Any],
        attempt: int,
        error: str,
        event_type: str,
        wall: float,
    ) -> None:
        await self._append(
            run_id=run_id,
            event_type=event_type,
            actor=run["actor"],
            payload={"attempt": attempt, "error": error, "wall_seconds": round(wall, 6)},
        )
        if attempt < self._max_attempts:
            await self._append(
                run_id=run_id,
                event_type="RETRY_QUEUED",
                actor=run["actor"],
                payload={"attempt": attempt, "next_attempt": attempt + 1},
            )
            self._queue.append(run_id)
            self._wakeup.set()
            return
        await self._append(
            run_id=run_id,
            event_type="DEAD_LETTERED",
            actor=run["actor"],
            payload={"attempts": attempt, "last_error": error},
        )
        self._record("dead_lettered_total")

    # ---------------------------------------------------------------- reads
    def run_detail(self, run_id: str) -> Optional[Dict[str, Any]]:
        events = self._store.events_for_run(run_id)
        if not events:
            return None
        derived = _derive_from(events)
        return {"run_id": run_id, **derived, "events": events}

    def runs_index(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._store.runs_index(limit=max(1, min(int(limit), 200)))

    def recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._store.all_events(limit=max(1, min(int(limit), 500)))

    def verify_history(self) -> Dict[str, Any]:
        count = self._store.verify_all_rows()
        return {"ok": True, "events_verified": count}

    @property
    def kill_engaged(self) -> bool:
        return self._kill_engaged

    @property
    def state(self) -> str:
        return self._state


def _derive_from(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Local derive wrapper importing the store's pure function."""
    from app.services.scheduler_run_store import derive_run_state

    return derive_run_state(events)


_SCHEDULER: Optional[InternalScheduler] = None


def get_scheduler() -> InternalScheduler:
    """Composition root: build the scheduler ONCE from settings.

    Settings are read HERE (once) — the service itself never reads them.
    Default wiring registers the governed synthetic/paper research-loop
    handler only; with ``SCHEDULER_ENABLED=0`` (the committed default) the
    instance exists but refuses start/enqueue (fail-closed).
    """
    global _SCHEDULER
    if _SCHEDULER is not None:
        return _SCHEDULER
    from app.core.config import get_settings
    from app.services.scheduler_jobs import build_default_handlers

    settings = get_settings()
    store = get_scheduler_run_store()
    scheduler = InternalScheduler(
        store,
        build_default_handlers(),
        enabled=bool(getattr(settings, "scheduler_enabled", False)),
        max_queue=int(getattr(settings, "scheduler_max_queue", 32)),
        max_concurrent=int(getattr(settings, "scheduler_max_concurrent", 1)),
        run_timeout_sec=float(getattr(settings, "scheduler_run_timeout_sec", 60.0)),
        max_attempts=int(getattr(settings, "scheduler_max_attempts", 2)),
    )
    _SCHEDULER = scheduler
    return scheduler


def reset_scheduler_cache() -> None:
    """Test hook: drop the cached scheduler (env changes take effect)."""
    global _SCHEDULER
    _SCHEDULER = None
