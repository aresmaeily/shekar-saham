"""D-AI-30 operational alert execution contracts (CONSOL-GOV-41, approved restricted scope).

Owner decision record: ``docs/active/GOV41_OWNER_DECISION_AMENDMENT_2026-10-30.md``
(A2 — ten binding decisions; A3/A4 — AI-2 owner actions remain closed-denied).

Scope ruling (binding): **Synthetic/Paper-only, in-product operational monitoring
and alerts.** Every budget, window, delay, retention period and the delivery
channel below are OWNER-PINNED exact values, not tunables: a different value is
unrepresentable (the frozen models refuse it). Nothing here performs I/O; this
module is the decision layer the service layer must consult BEFORE any dispatch.

Reuse (no existing module modified): ``governed_alerts.GovernedAlertObject``
(the nine-kind P5/P6 contract supplies the alert objects; per-kind dedicated
bindings and the 06 §4 M&A non-conflation guard stay enforced there),
``evidence.ensure_utc`` (UTC enforcement), ``monitoring.KillSwitchState``
(identical fail-closed semantics).

Privacy boundary: the canonical fingerprint and dedup key are deterministic
hashes over alert identity fields only (kind/subject/binding/event id) — never
credentials, tokens, or user content (owner decision 7).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.governed_alerts import GovernedAlertObject
from app.domain.monitoring import KillSwitchState

#: Exact owner-mandated label (decision 8). Every visible alert carries it.
SYNTHETIC_PAPER_LABEL = "SYNTHETIC / PAPER — NOT LIVE"

#: Closed delivery channel set (decision 3): in-product inbox ONLY. External
#: egress (Telegram/Bale/websocket fan-out/webhook/email/SMS) is not just
#: disabled — it is unrepresentable in this type.
DeliveryChannel = Literal["IN_PRODUCT_INBOX"]
DELIVERY_CHANNEL: DeliveryChannel = "IN_PRODUCT_INBOX"

#: Trust states eligible for operational alert delivery (decision 8):
#: synthetic/paper only. Mixed, stale, unavailable — and a fortiori live —
#: are blocked before dispatch.
DELIVERABLE_TRUST_STATES: tuple[str, ...] = ("synthetic", "mock")
BLOCKED_TRUST_STATES: tuple[str, ...] = ("live", "mixed", "stale", "unavailable")

#: Approved job identifiers (explicit, observable schedule configuration,
#: decision 1 / 5). Every other job id stays fail-closed.
JOB_FRESHNESS_CHECK = "OA-ALERT-OPS-FRESHNESS-30MIN"
JOB_DISPATCHER = "OA-ALERT-OPS-DISPATCHER"

_OUTBOX_STATUS = Literal["QUEUED", "DELIVERED", "DEAD_LETTERED", "DROPPED_EXPIRED"]


class OwnerBudgets(BaseModel):
    """Owner-pinned budgets (decision 2) and windows (decisions 1/4/7).

    Every field is locked to the exact owner value; constructing any other
    value raises, so configuration cannot drift from the decision record.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    #: O1-b — scheduled freshness/coverage checks every 30 minutes.
    freshness_check_interval_seconds: int
    #: O2-c — global maximum monitoring-job executions per hour.
    global_max_job_executions_per_hour: int
    #: O2-c — per alert kind executions per hour.
    per_alert_kind_max_executions_per_hour: int
    #: O2-c — per in-product delivery channel deliveries per hour.
    per_channel_max_deliveries_per_hour: int
    #: O2-c — per-minute burst ceiling (deliveries).
    per_minute_burst_max_deliveries: int
    #: Decision 4 — durable deduplication window.
    dedup_window: timedelta
    #: Decision 4 — maximum delivery attempts.
    max_delivery_attempts: int
    #: Decision 4 — retry delays: 30 seconds, then 120 seconds.
    retry_delay_seconds: tuple[int, int]
    #: Decision 7 — retention for operational alert/dispatch records.
    retention_days: int
    #: Decision 3 — the only delivery channel.
    delivery_channel: DeliveryChannel

    @field_validator(
        "freshness_check_interval_seconds",
        "global_max_job_executions_per_hour",
        "per_alert_kind_max_executions_per_hour",
        "per_channel_max_deliveries_per_hour",
        "per_minute_burst_max_deliveries",
        "max_delivery_attempts",
        "retention_days",
    )
    @classmethod
    def _positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("budget_value_must_be_positive")
        return v

    @model_validator(mode="after")
    def _owner_pinned(self) -> "OwnerBudgets":
        pinned = {
            "freshness_check_interval_seconds": (self.freshness_check_interval_seconds, 1800),
            "global_max_job_executions_per_hour": (self.global_max_job_executions_per_hour, 30),
            "per_alert_kind_max_executions_per_hour": (self.per_alert_kind_max_executions_per_hour, 6),
            "per_channel_max_deliveries_per_hour": (self.per_channel_max_deliveries_per_hour, 10),
            "per_minute_burst_max_deliveries": (self.per_minute_burst_max_deliveries, 3),
            "max_delivery_attempts": (self.max_delivery_attempts, 3),
            "retention_days": (self.retention_days, 90),
        }
        for name, (actual, expected) in pinned.items():
            if actual != expected:
                raise ValueError(f"owner_decision_deviation:{name}")
        if self.dedup_window != timedelta(hours=24):
            raise ValueError("owner_decision_deviation:dedup_window")
        if tuple(self.retry_delay_seconds) != (30, 120):
            raise ValueError("owner_decision_deviation:retry_delays")
        if self.delivery_channel != "IN_PRODUCT_INBOX":
            raise ValueError("owner_decision_deviation:delivery_channel")
        return self


#: The single approved budget instance (owner decision record A2).
OWNER_BUDGETS = OwnerBudgets(
    freshness_check_interval_seconds=1800,
    global_max_job_executions_per_hour=30,
    per_alert_kind_max_executions_per_hour=6,
    per_channel_max_deliveries_per_hour=10,
    per_minute_burst_max_deliveries=3,
    dedup_window=timedelta(hours=24),
    max_delivery_attempts=3,
    retry_delay_seconds=(30, 120),
    retention_days=90,
    delivery_channel="IN_PRODUCT_INBOX",
)


class DispatchDecision(BaseModel):
    """Pure fail-closed permission decision (audit codes included)."""

    model_config = ConfigDict(frozen=True)

    allowed: bool
    codes: tuple[str, ...] = ()

    @property
    def first_code(self) -> str | None:
        return self.codes[0] if self.codes else None


def refused(*codes: str) -> DispatchDecision:
    return DispatchDecision(allowed=False, codes=tuple(codes))


def allowed() -> DispatchDecision:
    return DispatchDecision(allowed=True, codes=())


def binding_id(alert: GovernedAlertObject) -> str:
    """Deterministic per-kind trigger-binding string (the "binding ID").

    Uses exactly the kind's dedicated binding fields; other kinds' fields are
    structurally empty (enforced by the governed contract), so the mapping is
    total and unambiguous.
    """
    k = alert.alert_kind
    if k == "MARKET_ANOMALY":
        return f"detector:{alert.detector_ref}"
    if k in ("MATERIAL_COMPANY_DISCLOSURE", "FILING_REPORT_PUBLICATION"):
        return f"content:{alert.content_kind}"
    if k == "SOURCE_CONFLICT":
        return f"conflict:{alert.conflict_id}"
    if k == "SOURCE_STALENESS":
        return "stale_sources:" + ",".join(sorted(alert.stale_source_ids))
    if k == "SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE":
        return f"fact_chain:{alert.superseded_fact_id}->{alert.fact_id}"
    if k == "WATCHLIST_CHANGE":
        return f"watchlist:{alert.watchlist_ref}:{alert.change_kind}"
    if k == "OPPORTUNITY_LIFECYCLE":
        return f"opportunity:{alert.opportunity_object_id}:{alert.lifecycle_transition}"
    return f"maturity:{alert.prediction_id}->{alert.outcome_id}"


def _canonical_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_fingerprint(alert: GovernedAlertObject) -> str:
    """Deterministic canonical fingerprint (decision 4, no-source-event case).

    Hashes semantic identity only: kind, subject, binding, evidence refs.
    alert_id / run_id / created_at / notes are excluded so an identical
    re-detection produces the same fingerprint regardless of run identity.
    """
    return _canonical_hash(
        {
            "kind": alert.alert_kind,
            "subject": alert.subject,
            "binding": binding_id(alert),
            "evidence": sorted(alert.evidence_ids),
        }
    )


def dedup_key(alert: GovernedAlertObject, source_event_id: str | None) -> str:
    """Durable idempotency key (decision 4): kind + subject + binding + event.

    When ``source_event_id`` is unavailable the canonical fingerprint stands
    in, exactly as the owner decision specifies.
    """
    event = source_event_id if source_event_id else canonical_fingerprint(alert)
    return _canonical_hash(
        {
            "kind": alert.alert_kind,
            "subject": alert.subject,
            "binding": binding_id(alert),
            "event": event,
        }
    )


def dedup_window_start(at_utc: datetime, window: timedelta = OWNER_BUDGETS.dedup_window) -> datetime:
    """Floor a timestamp into its dedup window (durable 24 h suppression)."""
    ts = ensure_utc(at_utc)
    epoch = datetime(1970, 1, 1, tzinfo=ts.tzinfo)
    seconds = int((ts - epoch).total_seconds())
    w = int(window.total_seconds())
    return epoch + timedelta(seconds=seconds - (seconds % w))


def trust_gate(alert: GovernedAlertObject) -> DispatchDecision:
    """Decision 8: synthetic/paper trust states only; blocked states named."""
    state = (alert.data_trust_state or "").strip().lower()
    if state in DELIVERABLE_TRUST_STATES:
        return allowed()
    return refused("trust_state_blocked", f"trust_state:{state or 'missing'}")


def kill_switch_gate(global_state: str | None, job_state: str | None) -> DispatchDecision:
    """Decision 5 (O5-b): fail-closed kill-switch evaluation.

    Missing (None), malformed (not ENGAGED/RELEASED), or inconsistent states
    deny execution. Both the global switch and the job switch must be
    RELEASED for a job to run.
    """
    valid = ("ENGAGED", "RELEASED")
    if global_state is None or job_state is None:
        return refused("kill_switch_missing_or_malformed")
    if global_state not in valid or job_state not in valid:
        return refused("kill_switch_missing_or_malformed")
    if global_state == "ENGAGED":
        return refused("kill_switch_engaged_global")
    if job_state == "ENGAGED":
        return refused("kill_switch_engaged_job")
    return allowed()


def evaluate_budgets(
    *,
    global_jobs_used: int,
    kind_jobs_used: int,
    channel_deliveries_used_hour: int,
    channel_deliveries_used_minute: int,
    budgets: OwnerBudgets = OWNER_BUDGETS,
) -> DispatchDecision:
    """Decision 2 (O2-c): all limits checked BEFORE dispatch; never exceeded."""
    if global_jobs_used >= budgets.global_max_job_executions_per_hour:
        return refused("budget_global_jobs_exhausted")
    if kind_jobs_used >= budgets.per_alert_kind_max_executions_per_hour:
        return refused("budget_kind_exhausted")
    if channel_deliveries_used_hour >= budgets.per_channel_max_deliveries_per_hour:
        return refused("budget_channel_deliveries_exhausted")
    if channel_deliveries_used_minute >= budgets.per_minute_burst_max_deliveries:
        return refused("budget_burst_exceeded")
    return allowed()


def next_retry_delay_seconds(attempts_so_far: int, budgets: OwnerBudgets = OWNER_BUDGETS) -> int | None:
    """Decision 4: 30 s after the first failed attempt, 120 s after the
    second; a third failure is exhaustion (dead-letter), not another retry."""
    delays = budgets.retry_delay_seconds
    if attempts_so_far < 1 or attempts_so_far > budgets.max_delivery_attempts:
        return None
    if attempts_so_far > len(delays):
        return None
    return delays[attempts_so_far - 1]


def hour_window_start(at_utc: datetime) -> datetime:
    return dedup_window_start(at_utc, timedelta(hours=1))


def minute_window_start(at_utc: datetime) -> datetime:
    return dedup_window_start(at_utc, timedelta(minutes=1))


def freshness_due(last_success_utc: datetime | None, now_utc: datetime, budgets: OwnerBudgets = OWNER_BUDGETS) -> bool:
    """O1-b: the scheduled freshness/coverage check is due every 30 minutes."""
    if last_success_utc is None:
        return True
    return (ensure_utc(now_utc) - ensure_utc(last_success_utc)) >= timedelta(seconds=budgets.freshness_check_interval_seconds)


__all__ = [
    "BLOCKED_TRUST_STATES",
    "DELIVERABLE_TRUST_STATES",
    "DELIVERY_CHANNEL",
    "DispatchDecision",
    "JOB_DISPATCHER",
    "JOB_FRESHNESS_CHECK",
    "KillSwitchState",
    "OWNER_BUDGETS",
    "OwnerBudgets",
    "SYNTHETIC_PAPER_LABEL",
    "allowed",
    "binding_id",
    "canonical_fingerprint",
    "dedup_key",
    "dedup_window_start",
    "evaluate_budgets",
    "freshness_due",
    "hour_window_start",
    "kill_switch_gate",
    "minute_window_start",
    "next_retry_delay_seconds",
    "refused",
    "trust_gate",
]
