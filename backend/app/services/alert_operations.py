"""D-AI-30 operational service: event-triggered enqueue gate, budget-enforced
in-product dispatcher, 30-minute freshness/coverage job, fail-closed kill
switches, observability and retention (CONSOL-GOV-41 A2).

Hard boundaries (owner decisions, binding):
- In-product inbox ONLY (``IN_PRODUCT_INBOX``); no external egress of any kind.
- Synthetic/Paper only: alerts whose declared ``data_trust_state`` is not
  synthetic/mock are refused BEFORE dedup/budget/delivery (decision 8).
- Kill switches default ENGAGED and fail closed on missing/malformed or
  inconsistent configuration (decision 5).
- Every budget is enforced BEFORE dispatch and never exceeded (decision 2).
- Dispatcher self-failure is visible through health/status + structured local
  logs; it NEVER enqueues alerts into itself (decision 6 — no recursive
  self-alerting).
- The scheduled freshness check processes only events already produced by
  governed local contracts via the injected ``coverage_provider``; with no
  provider (the default) it performs an honest no-op — no crawling, no
  external source discovery, no real-data scans (decision 1).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from app.data.alert_ops_store import AlertOpsStore
from app.domain.alert_operations import (
    DELIVERY_CHANNEL,
    JOB_DISPATCHER,
    JOB_FRESHNESS_CHECK,
    OWNER_BUDGETS,
    SYNTHETIC_PAPER_LABEL,
    OwnerBudgets,
    canonical_fingerprint,
    dedup_key as compute_dedup_key,
    dedup_window_start,
    evaluate_budgets,
    freshness_due,
    hour_window_start,
    kill_switch_gate,
    minute_window_start,
    next_retry_delay_seconds,
    trust_gate,
)
from app.domain.governed_alerts import GovernedAlertObject, is_expired

logger = logging.getLogger("shekar.alert_ops")

DEFAULT_SUMMARY_MAX_CHARS = 280


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _summary_of(alert: GovernedAlertObject, max_chars: int = DEFAULT_SUMMARY_MAX_CHARS) -> str:
    """Minimum-necessary human-readable summary (decision 7).

    Subject + reason-for-now, total length capped. Evidence IDs, invalidation
    details and the full alert JSON stay internal (database-only references).
    """
    text = f"{alert.subject} — {alert.reason_for_now.strip()}"
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def _failure_state_for(consecutive_failures: int) -> str:
    if consecutive_failures == 0:
        return "HEALTHY"
    if consecutive_failures <= 2:
        return "DEGRADED"
    if consecutive_failures <= 4:
        return "FAILING"
    return "HALTED"


class AlertOperationsService:
    """Single owner-approved operational capability (Synthetic/Paper, in-product)."""

    def __init__(
        self,
        store: AlertOpsStore | None = None,
        *,
        budgets: OwnerBudgets = OWNER_BUDGETS,
        clock: Callable[[], datetime] | None = None,
        coverage_provider: Callable[[], Any] | None = None,
    ) -> None:
        self.store = store or AlertOpsStore()
        self.budgets = budgets
        self._clock = clock or _utcnow
        self._coverage_provider = coverage_provider
        self.store.migrate()
        self.last_dispatcher_error: str | None = None

    # --- helpers -----------------------------------------------------------
    def _now(self) -> datetime:
        return self._clock()

    def _scopes(self, kind: str, job_id: str) -> dict[str, tuple[str, datetime]]:
        now = self._now()
        return {
            "global_jobs": (f"jobs:GLOBAL:{hour_window_start(now).isoformat()}", hour_window_start(now)),
            "kind_jobs": (f"jobs:KIND:{kind}:{hour_window_start(now).isoformat()}", hour_window_start(now)),
            "channel_hour": (f"deliveries:{DELIVERY_CHANNEL}:H:{hour_window_start(now).isoformat()}", hour_window_start(now)),
            "channel_minute": (f"deliveries:{DELIVERY_CHANNEL}:M:{minute_window_start(now).isoformat()}", minute_window_start(now)),
        }

    def _kill_switches(self, job_id: str) -> tuple[str | None, str | None]:
        return self.store.kill_switch_state("GLOBAL"), self.store.kill_switch_state(job_id)

    # --- event-triggered processing (decision 1) ----------------------------
    def enqueue_governed_alert(
        self,
        alert: GovernedAlertObject,
        *,
        source_event_id: str | None = None,
        actor: str = "event-trigger",
    ) -> dict[str, Any]:
        """Process one event already produced by a governed local contract.

        Order of gates (each audited): type → trust → dedup. Budgets and kill
        switches are dispatch-time concerns; queueing is durable and idempotent.
        """
        now = self._now()
        if not isinstance(alert, GovernedAlertObject):
            self.store.audit("ENQUEUE_REJECTED", "type", {"reason": "not_a_governed_alert_object"}, now)
            return {"status": "REJECTED", "code": "not_a_governed_alert_object"}

        gate = trust_gate(alert)
        if not gate.allowed:
            self.store.audit(
                "ENQUEUE_REJECTED",
                f"trust:{alert.alert_kind}",
                {"code": gate.first_code, "subject": alert.subject, "actor": actor},
                now,
            )
            logger.warning("alert_ops enqueue refused: %s (%s)", gate.first_code, alert.alert_kind)
            return {"status": "REJECTED", "code": gate.first_code, "detail": list(gate.codes)}

        key = compute_dedup_key(alert, source_event_id)
        window_start = dedup_window_start(now, self.budgets.dedup_window)
        existing = self.store.find_outbox_by_key(key)
        if existing is not None:
            created = datetime.fromisoformat(existing["created_at"])
            within_window = (now - created) < self.budgets.dedup_window
            if within_window and existing["status"] in ("QUEUED", "DELIVERED", "DEAD_LETTERED"):
                self.store.audit(
                    "DEDUP_SUPPRESSED",
                    key[:16],
                    {"kind": alert.alert_kind, "subject": alert.subject, "outbox_id": existing["id"], "actor": actor},
                    now,
                )
                return {"status": "SUPPRESSED", "code": "duplicate_within_dedup_window", "outbox_id": existing["id"]}

        row_id = self.store.enqueue(
            dedup_key=key,
            dedup_window=window_start.isoformat(),
            alert=alert,
            alert_json=alert.model_dump_json(),
            source_event_id=source_event_id,
            fingerprint=canonical_fingerprint(alert),
            now=now,
        )
        self.store.audit(
            "ENQUEUED",
            key[:16],
            {"kind": alert.alert_kind, "subject": alert.subject, "outbox_id": row_id, "actor": actor},
            now,
        )
        return {"status": "QUEUED", "outbox_id": row_id, "dedup_key": key}

    # --- dispatcher (decision 2/3/4) -----------------------------------------
    def dispatch(self, *, job_id: str = JOB_DISPATCHER, limit: int = 100) -> dict[str, Any]:
        """One dispatcher execution: kill switches → budgets → delivery.

        All limits are enforced before any delivery; refusals are audited and
        visible in health/status. The dispatcher run itself is a monitoring-job
        execution counted against the global hourly budget.
        """
        now = self._now()
        report: dict[str, Any] = {
            "job_id": job_id,
            "ran_at": now.isoformat(),
            "allowed": False,
            "codes": [],
            "processed": 0,
            "delivered": 0,
            "suppressed": 0,
            "expired_dropped": 0,
            "budget_refusals": 0,
            "retries_scheduled": 0,
            "dead_lettered": 0,
            "queue_depth_before": self.store.queue_depth(),
            "queue_depth_after": None,
        }
        try:
            global_state, job_state_sw = self._kill_switches(job_id)
            gate = kill_switch_gate(global_state, job_state_sw)
            if not gate.allowed:
                report["codes"] = list(gate.codes)
                self.store.audit("KILL_SWITCH_REFUSAL", job_id, {"codes": list(gate.codes)}, now)
                # A refused run is NOT a job execution; budgets untouched.
                report["queue_depth_after"] = self.store.queue_depth()
                return report

            scopes = self._scopes("*", job_id)
            g_scope, g_window = scopes["global_jobs"]
            if self.store.counter_value(g_scope, g_window) >= self.budgets.global_max_job_executions_per_hour:
                report["codes"] = ["budget_global_jobs_exhausted"]
                report["budget_refusals"] = 1
                self.store.audit("BUDGET_REFUSAL", "GLOBAL", {"code": "budget_global_jobs_exhausted", "job": job_id}, now)
                report["queue_depth_after"] = self.store.queue_depth()
                return report
            self.store.increment_counter(g_scope, g_window)

            rows = self.store.due_outbox_rows(now, limit=limit)
            kind_budget_cache: dict[str, int] = {}
            row_failures = 0
            last_row_error: str | None = None
            for row in rows:
                alert = GovernedAlertObject.model_validate_json(row["alert_json"])
                kind = row["alert_kind"]
                report["processed"] += 1

                # Expiry drop BEFORE delivery (decision 4).
                if is_expired(alert, now):
                    self.store.update_outbox(
                        row["id"], status="DROPPED_EXPIRED", attempts=row["attempts"],
                        next_attempt_at=None, last_error_code="expired", now=now,
                    )
                    report["expired_dropped"] += 1
                    self.store.audit("EXPIRY_DROP", key_ref(row), {"kind": kind, "subject": alert.subject}, now)
                    continue

                # Per-kind budget (decision 2), before dispatch.
                k_scope, k_window = self._scopes(kind, job_id)["kind_jobs"]
                if kind not in kind_budget_cache:
                    kind_budget_cache[kind] = self.store.counter_value(k_scope, k_window)
                if kind_budget_cache[kind] >= self.budgets.per_alert_kind_max_executions_per_hour:
                    report["budget_refusals"] += 1
                    self.store.audit("BUDGET_REFUSAL", f"KIND:{kind}", {"code": "budget_kind_exhausted", "outbox_id": row["id"]}, now)
                    continue

                # Channel delivery budgets: hourly + per-minute burst, BEFORE dispatch.
                _, ch_window_h = self._scopes(kind, job_id)["channel_hour"]
                _, ch_window_m = self._scopes(kind, job_id)["channel_minute"]
                ch_hour_used = self.store.counter_value(
                    f"deliveries:{DELIVERY_CHANNEL}:H:{hour_window_start(now).isoformat()}", hour_window_start(now)
                )
                ch_min_used = self.store.counter_value(
                    f"deliveries:{DELIVERY_CHANNEL}:M:{minute_window_start(now).isoformat()}", minute_window_start(now)
                )
                budget_gate = evaluate_budgets(
                    global_jobs_used=0,  # global already accounted for this run
                    kind_jobs_used=kind_budget_cache[kind],
                    channel_deliveries_used_hour=ch_hour_used,
                    channel_deliveries_used_minute=ch_min_used,
                    budgets=self.budgets,
                )
                if not budget_gate.allowed:
                    report["budget_refusals"] += 1
                    self.store.audit(
                        "BUDGET_REFUSAL",
                        f"CHANNEL:{kind}",
                        {"codes": list(budget_gate.codes), "outbox_id": row["id"]},
                        now,
                    )
                    continue

                # Deliver (single in-product channel; idempotent via outbox_id UNIQUE).
                try:
                    self.store.deliver_to_inbox(
                        outbox_id=row["id"],
                        dedup_key=row["dedup_key"],
                        alert=alert,
                        alert_json=row["alert_json"],
                        summary=_summary_of(alert),
                        now=now,
                    )
                except Exception as exc:  # delivery failure → bounded retry (decision 4)
                    attempts = int(row["attempts"]) + 1
                    code = f"delivery_error:{type(exc).__name__}"
                    delay = next_retry_delay_seconds(attempts, self.budgets)
                    if delay is None or attempts >= self.budgets.max_delivery_attempts:
                        self.store.update_outbox(
                            row["id"], status="DEAD_LETTERED", attempts=attempts,
                            next_attempt_at=None, last_error_code=code, now=now,
                        )
                        self.store.dead_letter(
                            outbox_id=row["id"], dedup_key=row["dedup_key"], alert_json=row["alert_json"],
                            alert_kind=kind, attempts=attempts, last_error_code=code,
                            reason="retry_exhausted", now=now,
                        )
                        report["dead_lettered"] += 1
                        self.store.audit("RETRY_EXHAUSTED", key_ref(row), {"kind": kind, "attempts": attempts}, now)
                    else:
                        self.store.update_outbox(
                            row["id"], status="QUEUED", attempts=attempts,
                            next_attempt_at=now + _seconds(delay), last_error_code=code, now=now,
                        )
                        report["retries_scheduled"] += 1
                        self.store.audit("RETRY_SCHEDULED", key_ref(row), {"kind": kind, "attempts": attempts, "delay_s": delay}, now)
                    row_failures += 1
                    last_row_error = code
                    continue

                self.store.update_outbox(
                    row["id"], status="DELIVERED", attempts=int(row["attempts"]) + 1,
                    next_attempt_at=None, last_error_code=None, now=now,
                )
                self.store.increment_counter(k_scope, k_window)
                self.store.increment_counter(f"deliveries:{DELIVERY_CHANNEL}:H:{hour_window_start(now).isoformat()}", hour_window_start(now))
                self.store.increment_counter(f"deliveries:{DELIVERY_CHANNEL}:M:{minute_window_start(now).isoformat()}", minute_window_start(now))
                kind_budget_cache[kind] += 1
                report["delivered"] += 1
                self.store.audit("DELIVERED", key_ref(row), {"kind": kind, "subject": alert.subject, "channel": DELIVERY_CHANNEL}, now)

            report["allowed"] = True
            report["queue_depth_after"] = self.store.queue_depth()
            # Run-level honesty (decision 6): a run with any row-level delivery
            # failure is NOT a clean success for last-success/failure-state.
            self._record_job_result(
                job_id,
                success=(row_failures == 0),
                error_code=last_row_error,
                now=now,
            )
            self.last_dispatcher_error = None
        except Exception as exc:  # dispatcher self-failure (decision 6)
            self.last_dispatcher_error = f"{type(exc).__name__}: {exc}"
            logger.exception("alert_ops dispatcher self-failure")
            self.store.audit("DISPATCHER_ERROR", job_id, {"error": self.last_dispatcher_error}, now)
            self._record_job_result(job_id, success=False, error_code=self.last_dispatcher_error[:120], now=now)
            report["codes"] = ["dispatcher_error"]
            report["queue_depth_after"] = self.store.queue_depth()
        return report

    # --- scheduled freshness/coverage check (decision 1, O1-b) -----------------
    def run_freshness_check(self, *, job_id: str = JOB_FRESHNESS_CHECK) -> dict[str, Any]:
        """Bounded scheduled check over governed LOCAL contracts only.

        The coverage provider is injected at construction; the default service
        has none, and the job then records an honest no-op. No crawling, no
        external discovery, no real-data scans.
        """
        now = self._now()
        report: dict[str, Any] = {
            "job_id": job_id,
            "ran_at": now.isoformat(),
            "due": freshness_due(None, now, self.budgets),
            "enqueued": 0,
            "stale_source_ids": [],
            "note": "no coverage provider configured — governed local contracts produced no coverage event",
        }
        global_state, job_state_sw = self._kill_switches(job_id)
        gate = kill_switch_gate(global_state, job_state_sw)
        if not gate.allowed:
            report["codes"] = list(gate.codes)
            self.store.audit("KILL_SWITCH_REFUSAL", job_id, {"codes": list(gate.codes)}, now)
            report["queue_depth_after"] = self.store.queue_depth()
            return report

        state = self.store.job_state(job_id)
        last_success = datetime.fromisoformat(state["last_success_at"]) if state and state["last_success_at"] else None
        if not freshness_due(last_success, now, self.budgets):
            report["due"] = False
            report["queue_depth_after"] = self.store.queue_depth()
            return report

        scopes = self._scopes("*", job_id)
        g_scope, g_window = scopes["global_jobs"]
        if self.store.counter_value(g_scope, g_window) >= self.budgets.global_max_job_executions_per_hour:
            report["codes"] = ["budget_global_jobs_exhausted"]
            self.store.audit("BUDGET_REFUSAL", "GLOBAL", {"code": "budget_global_jobs_exhausted", "job": job_id}, now)
            report["queue_depth_after"] = self.store.queue_depth()
            return report
        self.store.increment_counter(g_scope, g_window)

        provider = self._coverage_provider
        if provider is None:
            self._record_job_result(job_id, success=True, error_code=None, now=now)
            report["queue_depth_after"] = self.store.queue_depth()
            self.store.audit("FRESHNESS_CHECK", job_id, {"result": "no-op", "enqueued": 0}, now)
            return report

        try:
            coverage = provider()
        except Exception as exc:
            self._record_job_result(job_id, success=False, error_code=f"coverage_provider_error:{type(exc).__name__}", now=now)
            report["codes"] = ["coverage_provider_error"]
            report["queue_depth_after"] = self.store.queue_depth()
            return report

        stale = tuple(getattr(coverage, "stale_sources", ()) or ())
        report["stale_source_ids"] = list(stale)
        if stale:
            as_of = getattr(coverage, "as_of_utc", now)
            evidence_ref = f"coverage:{getattr(coverage, 'registry_version', 1)}:{getattr(as_of, 'isoformat', lambda: str(as_of))()}"
            for source_id in stale:
                # Deterministic internal id (no PYTHONHASHSEED dependence).
                aid = "STALENESS-" + hashlib.sha256(f"{source_id}|{evidence_ref}".encode()).hexdigest()[:12]
                alert = GovernedAlertObject(
                    alert_id=aid,
                    alert_kind="SOURCE_STALENESS",
                    subject=source_id,
                    created_at_utc=now,
                    reason_for_now=f"Governed coverage check flagged source as stale at {evidence_ref}.",
                    confidence="1",
                    confidence_basis="declared: coverage report staleness classification (synthetic fixture input)",
                    data_trust_state="synthetic",
                    risk_semantics="staleness may invalidate downstream signals derived from this source",
                    evidence_ids=(evidence_ref,),
                    invalidation_conditions=(f"source {source_id} refreshed within its freshness SLA",),
                    expiry_open_ended=True,
                    run_id="alert-ops-freshness",
                    stale_source_ids=(source_id,),
                )
                result = self.enqueue_governed_alert(alert, source_event_id=evidence_ref, actor=job_id)
                if result.get("status") == "QUEUED":
                    report["enqueued"] += 1
        self._record_job_result(job_id, success=True, error_code=None, now=now)
        report["queue_depth_after"] = self.store.queue_depth()
        self.store.audit("FRESHNESS_CHECK", job_id, {"enqueued": report["enqueued"], "stale": len(stale)}, now)
        return report

    # --- tick: the observable schedule (decision 1) ------------------------------
    def tick(self) -> dict[str, Any]:
        """Run the freshness job when due, then one dispatcher execution.

        The 30-minute schedule lives in ``OwnerBudgets.freshness_check_interval_seconds``
        (owner-pinned 1800) and the last-success state — explicit and observable
        through ``health()``; nothing is hard-coded elsewhere.
        """
        fresh = self.run_freshness_check()
        disp = self.dispatch()
        return {"freshness": fresh, "dispatch": disp}

    # --- kill switches (decision 5) ----------------------------------------------
    def set_kill_switch(self, scope: str, state: str, *, actor: str, reason: str = "") -> dict[str, Any]:
        now = self._now()
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("kill_switch_scope_malformed")
        if state not in ("ENGAGED", "RELEASED"):
            raise ValueError("kill_switch_state_malformed")
        previous = self.store.kill_switch_state(scope.strip())
        if previous == state:
            self.store.audit(
                "KILL_SWITCH_TRANSITION", scope.strip(), {"from": previous, "to": state, "actor": actor, "reason": reason, "no_op": True}, now
            )
        else:
            self.store.set_kill_switch(scope.strip(), state, now, actor)
            self.store.audit(
                "KILL_SWITCH_TRANSITION", scope.strip(), {"from": previous, "to": state, "actor": actor, "reason": reason}, now
            )
            logger.info("alert_ops kill switch %s: %s -> %s (by %s)", scope.strip(), previous, state, actor)
        return {"scope": scope.strip(), "state": state, "previous": previous}

    def kill_switches(self) -> list[dict[str, Any]]:
        return self.store.kill_switch_rows()

    # --- observability (decision 6) -------------------------------------------------
    def health(self) -> dict[str, Any]:
        now = self._now()
        dispatcher_state = self.store.job_state(JOB_DISPATCHER) or {}
        freshness_state = self.store.job_state(JOB_FRESHNESS_CHECK) or {}
        counts = self.store.outbox_counts_by_status()
        return {
            "mode": "SYNTHETIC_OR_PAPER",
            "label": SYNTHETIC_PAPER_LABEL,
            "delivery_channel": DELIVERY_CHANNEL,
            "budgets": {
                "global_max_job_executions_per_hour": self.budgets.global_max_job_executions_per_hour,
                "per_alert_kind_max_executions_per_hour": self.budgets.per_alert_kind_max_executions_per_hour,
                "per_channel_max_deliveries_per_hour": self.budgets.per_channel_max_deliveries_per_hour,
                "per_minute_burst_max_deliveries": self.budgets.per_minute_burst_max_deliveries,
                "freshness_check_interval_seconds": self.budgets.freshness_check_interval_seconds,
                "dedup_window_hours": int(self.budgets.dedup_window.total_seconds() // 3600),
                "max_delivery_attempts": self.budgets.max_delivery_attempts,
                "retry_delay_seconds": list(self.budgets.retry_delay_seconds),
                "retention_days": self.budgets.retention_days,
            },
            "run_id": f"alert-ops-{now.strftime('%Y%m%dT%H%M%S')}",
            "queue_depth": self.store.queue_depth(),
            "outbox_counts_by_status": counts,
            "delivery_success_total": counts.get("DELIVERED", 0),
            "dead_letter_count": self.store.dead_letter_count(),
            "retry_exhaustion_total": self.store.audit_count("RETRY_EXHAUSTED"),
            "budget_refusal_total": self.store.audit_count("BUDGET_REFUSAL"),
            "kill_switch_transitions_total": self.store.audit_count("KILL_SWITCH_TRANSITION"),
            "kill_switches": self.store.kill_switch_rows(),
            "dispatcher": {
                "job_id": JOB_DISPATCHER,
                "last_attempt_utc": dispatcher_state.get("last_run_at"),
                "last_success_utc": dispatcher_state.get("last_success_at"),
                "failure_state": dispatcher_state.get("failure_state", "HEALTHY"),
                "consecutive_failures": int(dispatcher_state.get("consecutive_failures") or 0),
                "last_error_code": dispatcher_state.get("last_error_code"),
                "self_failure_visible": self.last_dispatcher_error,
            },
            "freshness_job": {
                "job_id": JOB_FRESHNESS_CHECK,
                "interval_seconds": self.budgets.freshness_check_interval_seconds,
                "last_run_utc": freshness_state.get("last_run_at"),
                "last_success_utc": freshness_state.get("last_success_at"),
                "failure_state": freshness_state.get("failure_state", "HEALTHY"),
                "consecutive_failures": int(freshness_state.get("consecutive_failures") or 0),
                "last_error_code": freshness_state.get("last_error_code"),
            },
            "jobs": self.store.all_job_states(),
            "retention": {
                "days": self.budgets.retention_days,
                "last_purge_audit": (self.store.audit_rows(limit=1, category="RETENTION_PURGE") or [None])[0],
            },
        }

    # --- retention (decision 7) -------------------------------------------------------
    def purge_expired_records(self) -> dict[str, Any]:
        now = self._now()
        purged = self.store.purge_expired_records(now, self.budgets.retention_days)
        self.store.audit("RETENTION_PURGE", "alert-ops", {"purged": purged, "retention_days": self.budgets.retention_days}, now)
        return {"purged": purged, "ran_at": now.isoformat()}

    # --- internal -----------------------------------------------------------------------
    def _record_job_result(self, job_id: str, *, success: bool, error_code: str | None, now: datetime) -> None:
        state = self.store.job_state(job_id) or {}
        failures = 0 if success else int(state.get("consecutive_failures") or 0) + 1
        self.store.upsert_job_state(
            job_id,
            last_run_at=now,
            last_success_at=now if success else None,
            consecutive_failures=failures,
            failure_state=_failure_state_for(failures),
            last_error_code=error_code,
        )
        if not success:
            # Decision 6: structured local log ONLY — never a self-alert.
            logger.error("alert_ops job %s failed (%s consecutive): %s", job_id, failures, error_code)


def _seconds(n: int) -> Any:
    from datetime import timedelta

    return timedelta(seconds=n)


def key_ref(row: dict[str, Any]) -> str:
    return str(row.get("dedup_key", ""))[:16]


# --- explicit, observable background schedule (decision 1) --------------------
# The loop interval (60 s) is only the scheduler's heartbeat; the 30-minute
# freshness cadence itself lives in OwnerBudgets.freshness_check_interval_seconds
# and the recorded last-success state (visible in health()). Every tick remains
# gated by kill switches and budgets — ENGAGED (the default) refuses execution.
_loop_task: Any = None


async def background_loop(interval_seconds: int = 60) -> None:
    import asyncio

    try:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                service.tick()
            except Exception:
                logger.exception("alert_ops tick failed (dispatcher self-failure visible in health)")
    except asyncio.CancelledError:
        return


async def start_background_loop(interval_seconds: int = 60) -> None:
    import asyncio
    import os

    global _loop_task
    if not os.getenv("ALERT_OPS_LOOP", "1").strip().lower() in {"1", "true", "yes", "on"}:
        logger.info("alert_ops background loop disabled by ALERT_OPS_LOOP")
        return
    if _loop_task is None or _loop_task.done():
        _loop_task = asyncio.create_task(background_loop(interval_seconds))
        logger.info("alert_ops background loop started (interval=%ss; kill switches still gate every tick)", interval_seconds)


async def stop_background_loop() -> None:
    global _loop_task
    if _loop_task is not None:
        _loop_task.cancel()
        _loop_task = None
        logger.info("alert_ops background loop stopped")


#: Module-level singleton shared by the API layer and the background loop.
#: Construction is additive (CREATE TABLE IF NOT EXISTS) and idempotent.
service = AlertOperationsService()
