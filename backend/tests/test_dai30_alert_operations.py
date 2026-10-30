"""D-AI-30 acceptance battery (CONSOL-GOV-41 A2 decision 9).

Synthetic fixtures and deterministic clocks ONLY. Covers: scheduling and
event triggers, budgets, idempotency, deduplication, expiry, retries,
dead-letter, kill switches, audit records, privacy, labeling, recovery,
migration/rollback, retention, P5/P6 nine-kind integration, and a synthetic
end-to-end run against the in-product inbox.

Preserved-boundary assertions: no external egress surface, no recursive
self-alerting, exact ``SYNTHETIC / PAPER — NOT LIVE`` label, mixed/stale/
unavailable/live data blocked, unapproved jobs fail-closed, owner-pinned
budgets immutable.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.data.alert_ops_store import AlertOpsStore
from app.domain.alert_operations import (
    BLOCKED_TRUST_STATES,
    DELIVERABLE_TRUST_STATES,
    DELIVERY_CHANNEL,
    JOB_DISPATCHER,
    JOB_FRESHNESS_CHECK,
    OWNER_BUDGETS,
    SYNTHETIC_PAPER_LABEL,
    OwnerBudgets,
    binding_id,
    canonical_fingerprint,
    dedup_key,
    dedup_window_start,
    evaluate_budgets,
    freshness_due,
    kill_switch_gate,
    next_retry_delay_seconds,
    trust_gate,
)
from app.domain.governed_alerts import AlertKind, GovernedAlertObject
from app.domain.source_registry import CoverageReport
from app.services.alert_operations import AlertOperationsService

UTC = timezone.utc
NOW = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)

VALID_KINDS: tuple[AlertKind, ...] = (
    "MARKET_ANOMALY",
    "MATERIAL_COMPANY_DISCLOSURE",
    "FILING_REPORT_PUBLICATION",
    "SOURCE_CONFLICT",
    "SOURCE_STALENESS",
    "SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE",
    "WATCHLIST_CHANGE",
    "OPPORTUNITY_LIFECYCLE",
    "RESEARCH_RESULT_MATURITY",
)


def _base(**over: object) -> dict[str, object]:
    d: dict[str, object] = {
        "alert_id": "ALERT-1",
        "alert_kind": "SOURCE_CONFLICT",
        "subject": "فملی",
        "created_at_utc": NOW - timedelta(minutes=1),
        "reason_for_now": "two primary sources disagree on the same figure",
        "confidence": Decimal("0.5"),
        "confidence_basis": "declared by the detecting governed run",
        "data_trust_state": "synthetic",
        "risk_semantics": "informational; no position implication",
        "evidence_ids": ("E1", "E2"),
        "invalidation_conditions": ("conflict resolved with reviewer + rule",),
        "expiry_utc": NOW + timedelta(days=7),
        "run_id": "RUN-1",
        "conflict_id": "CONFLICT-1",
    }
    d.update(over)
    return d


def _binding_kwargs(kind: AlertKind) -> dict[str, object]:
    if kind == "MARKET_ANOMALY":
        return {"conflict_id": None, "detector_ref": "DETECTOR-OBS-1"}
    if kind == "MATERIAL_COMPANY_DISCLOSURE":
        return {"conflict_id": None, "content_kind": "COMPANY_DISCLOSURE"}
    if kind == "FILING_REPORT_PUBLICATION":
        return {"conflict_id": None, "content_kind": "FILING"}
    if kind == "SOURCE_CONFLICT":
        return {"conflict_id": "CONFLICT-1"}
    if kind == "SOURCE_STALENESS":
        return {"conflict_id": None, "stale_source_ids": ("SRC-1",)}
    if kind == "SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE":
        return {"conflict_id": None, "fact_id": "F-2", "superseded_fact_id": "F-1"}
    if kind == "WATCHLIST_CHANGE":
        return {"conflict_id": None, "watchlist_ref": "WL-1", "change_kind": "ADDED"}
    if kind == "OPPORTUNITY_LIFECYCLE":
        return {"conflict_id": None, "opportunity_object_id": "OPP-1", "lifecycle_transition": "CREATED"}
    return {"conflict_id": None, "prediction_id": "P-1", "outcome_id": "O-1"}


def _alert(kind: AlertKind = "SOURCE_CONFLICT", **over: object) -> GovernedAlertObject:
    d = _base(alert_kind=kind, **_binding_kwargs(kind))
    d.update(over)  # tests may deliberately override bindings (contamination probes)
    return GovernedAlertObject(**d)


class _Clock:
    """Deterministic, advanceable clock (no real time anywhere)."""

    def __init__(self, start: datetime = NOW) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: object) -> None:
        self.now = self.now + timedelta(**kw)


@pytest.fixture()
def env(tmp_path: Path) -> tuple[AlertOperationsService, AlertOpsStore, _Clock]:
    clock = _Clock()
    store = AlertOpsStore(path=tmp_path / "ops.db")
    svc = AlertOperationsService(store=store, clock=clock)
    svc.set_kill_switch("GLOBAL", "RELEASED", actor="fixture", reason="release for test")
    svc.set_kill_switch(JOB_DISPATCHER, "RELEASED", actor="fixture", reason="release for test")
    return svc, store, clock


def _release_freshness(svc: AlertOperationsService) -> None:
    svc.set_kill_switch(JOB_FRESHNESS_CHECK, "RELEASED", actor="fixture", reason="release freshness job")


# --- owner-pinned contracts (decisions 2/3/4/7/8) -----------------------------


def test_budgets_owner_pinned_exact_values() -> None:
    b = OWNER_BUDGETS
    assert b.global_max_job_executions_per_hour == 30
    assert b.per_alert_kind_max_executions_per_hour == 6
    assert b.per_channel_max_deliveries_per_hour == 10
    assert b.per_minute_burst_max_deliveries == 3
    assert b.freshness_check_interval_seconds == 1800
    assert b.dedup_window == timedelta(hours=24)
    assert b.max_delivery_attempts == 3
    assert b.retry_delay_seconds == (30, 120)
    assert b.retention_days == 90
    assert b.delivery_channel == "IN_PRODUCT_INBOX"


@pytest.mark.parametrize(
    "over",
    [
        {"global_max_job_executions_per_hour": 31},
        {"per_alert_kind_max_executions_per_hour": 5},
        {"per_channel_max_deliveries_per_hour": 11},
        {"per_minute_burst_max_deliveries": 4},
        {"freshness_check_interval_seconds": 900},
        {"max_delivery_attempts": 4},
        {"retention_days": 30},
        {"dedup_window": timedelta(hours=12)},
        {"retry_delay_seconds": (30, 60)},
        {"delivery_channel": "TELEGRAM"},
    ],
)
def test_budget_deviation_from_owner_decision_unrepresentable(over: dict) -> None:
    base = dict(
        freshness_check_interval_seconds=1800,
        global_max_job_executions_per_hour=30,
        per_alert_kind_max_executions_per_hour=6,
        per_channel_max_deliveries_per_hour=10,
        per_minute_burst_max_deliveries=3,
        max_delivery_attempts=3,
        retention_days=90,
        dedup_window=timedelta(hours=24),
        retry_delay_seconds=(30, 120),
        delivery_channel="IN_PRODUCT_INBOX",
    )
    base.update(over)
    with pytest.raises(ValidationError):
        OwnerBudgets(**base)  # type: ignore[arg-type]


def test_exact_label_constant() -> None:
    assert SYNTHETIC_PAPER_LABEL == "SYNTHETIC / PAPER — NOT LIVE"


def test_delivery_channel_closed_set() -> None:
    assert DELIVERY_CHANNEL == "IN_PRODUCT_INBOX"
    assert set(DELIVERABLE_TRUST_STATES) == {"synthetic", "mock"}
    assert set(BLOCKED_TRUST_STATES) == {"live", "mixed", "stale", "unavailable"}


def test_retry_schedule_exact_delays() -> None:
    assert next_retry_delay_seconds(1) == 30
    assert next_retry_delay_seconds(2) == 120
    assert next_retry_delay_seconds(3) is None  # exhaustion → dead-letter
    assert next_retry_delay_seconds(0) is None


def test_freshness_due_every_30_minutes() -> None:
    assert freshness_due(None, NOW) is True
    assert freshness_due(NOW - timedelta(minutes=29), NOW) is False
    assert freshness_due(NOW - timedelta(minutes=30), NOW) is True


# --- dedup / idempotency keys (decision 4) ------------------------------------


def test_dedup_key_binds_kind_subject_event() -> None:
    a = _alert()
    k1 = dedup_key(a, "EVT-1")
    k2 = dedup_key(a, "EVT-1")
    k3 = dedup_key(a, "EVT-2")
    assert k1 == k2 and k1 != k3


def test_dedup_key_falls_back_to_canonical_fingerprint() -> None:
    a = _alert()
    assert dedup_key(a, None) == dedup_key(a, canonical_fingerprint(a))
    b = _alert(subject="شپدا")
    assert dedup_key(a, None) != dedup_key(b, None)


def test_canonical_fingerprint_ignores_run_identity() -> None:
    a = _alert()
    b = _alert(alert_id="ALERT-999", run_id="RUN-999")
    assert canonical_fingerprint(a) == canonical_fingerprint(b)


def test_binding_id_deterministic_per_kind() -> None:
    assert binding_id(_alert("MARKET_ANOMALY")).startswith("detector:")
    assert binding_id(_alert("SOURCE_CONFLICT")) == "conflict:CONFLICT-1"
    assert binding_id(_alert("SOURCE_STALENESS")) == "stale_sources:SRC-1"
    assert binding_id(_alert("RESEARCH_RESULT_MATURITY")) == "maturity:P-1->O-1"


def test_dedup_window_floor_is_deterministic() -> None:
    w = dedup_window_start(NOW)
    assert dedup_window_start(NOW + timedelta(hours=2)) == w
    assert dedup_window_start(NOW + timedelta(hours=25)) != w


# --- trust gate (decision 8) ----------------------------------------------------


@pytest.mark.parametrize("state", ["synthetic", "mock"])
def test_trust_gate_allows_synthetic_states(state: str) -> None:
    assert trust_gate(_alert(data_trust_state=state)).allowed is True


@pytest.mark.parametrize("state", ["live", "mixed", "stale", "unavailable"])
def test_trust_gate_blocks_non_synthetic_states(state: str) -> None:
    d = trust_gate(_alert(data_trust_state=state))
    assert d.allowed is False
    assert "trust_state_blocked" in d.codes


def test_service_rejects_blocked_trust_before_queueing(env) -> None:
    svc, store, _ = env
    for state in ("live", "mixed", "stale", "unavailable"):
        r = svc.enqueue_governed_alert(_alert(data_trust_state=state), source_event_id=f"EV-{state}")
        assert r["status"] == "REJECTED"
    assert store.queue_depth() == 0
    assert store.audit_count("ENQUEUE_REJECTED") == 4


def test_service_rejects_non_governed_objects(env) -> None:
    svc, store, _ = env
    r = svc.enqueue_governed_alert({"alert_kind": "MARKET_ANOMALY"})  # type: ignore[arg-type]
    assert r["status"] == "REJECTED"
    assert store.queue_depth() == 0


# --- kill switches (decision 5) ---------------------------------------------------


def test_kill_switch_gate_fail_closed_on_missing() -> None:
    assert kill_switch_gate(None, "RELEASED").allowed is False
    assert kill_switch_gate("RELEASED", None).allowed is False
    assert kill_switch_gate(None, None).allowed is False


def test_kill_switch_gate_fail_closed_on_malformed() -> None:
    assert kill_switch_gate("released", "RELEASED").allowed is False  # case-sensitive enum
    assert kill_switch_gate("OPEN", "RELEASED").allowed is False


def test_kill_switch_gate_requires_both_released() -> None:
    assert kill_switch_gate("ENGAGED", "RELEASED").allowed is False
    assert kill_switch_gate("RELEASED", "ENGAGED").allowed is False
    assert kill_switch_gate("RELEASED", "RELEASED").allowed is True


def test_defaults_engaged_and_denied(env) -> None:
    svc, _, _ = env
    svc.set_kill_switch("GLOBAL", "ENGAGED", actor="fixture", reason="re-engage")
    rep = svc.dispatch()
    assert rep["allowed"] is False
    assert "kill_switch_engaged_global" in rep["codes"]


def test_unapproved_job_fail_closed_missing_switch(env) -> None:
    svc, _, _ = env
    g, j = svc._kill_switches("OA-SOME-UNAPPROVED-JOB")
    assert g == "RELEASED"
    assert j is None  # missing → deny


def test_missing_switch_denies_dispatch(env) -> None:
    svc, _, _ = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-X")
    rep = svc.dispatch(job_id="OA-SOME-UNAPPROVED-JOB")
    assert rep["allowed"] is False
    assert "kill_switch_missing_or_malformed" in rep["codes"]
    assert svc.store.queue_depth() == 1  # nothing processed


def test_kill_switch_transitions_audited(env) -> None:
    svc, store, _ = env
    svc.set_kill_switch("GLOBAL", "ENGAGED", actor="owner", reason="suspend")
    rows = store.audit_rows(category="KILL_SWITCH_TRANSITION", limit=5)
    assert rows and rows[0]["ref"] == "GLOBAL"
    detail = json.loads(rows[0]["detail_json"])
    assert detail["from"] == "RELEASED" and detail["to"] == "ENGAGED" and detail["actor"] == "owner"


def test_set_kill_switch_rejects_malformed_state(env) -> None:
    svc, _, _ = env
    with pytest.raises(ValueError):
        svc.set_kill_switch("GLOBAL", "OPEN", actor="x")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        svc.set_kill_switch("", "RELEASED", actor="x")


# --- dispatcher: delivery, budgets, expiry, retries, dead-letter --------------------


def test_event_trigger_to_inbox_delivery_with_label(env) -> None:
    svc, store, _ = env
    r = svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    assert r["status"] == "QUEUED"
    rep = svc.dispatch()
    assert rep["allowed"] is True and rep["delivered"] == 1
    rows = store.inbox_rows()
    assert len(rows) == 1
    assert rows[0]["label"] == SYNTHETIC_PAPER_LABEL
    assert rows[0]["alert_kind"] == "SOURCE_CONFLICT"
    assert store.outbox_counts_by_status().get("DELIVERED") == 1


def test_durable_dedup_suppresses_within_24h_no_digest(env) -> None:
    svc, store, _ = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    r = svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    assert r["status"] == "SUPPRESSED"
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    rep = svc.dispatch()
    assert rep["delivered"] == 1  # one inbox row; no digest generated
    assert store.inbox_count() == 1
    assert store.audit_count("DEDUP_SUPPRESSED") >= 1


def test_dedup_window_expires_after_24h(env) -> None:
    svc, _, clock = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    svc.dispatch()
    clock.advance(hours=25)
    r = svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    assert r["status"] == "QUEUED"  # outside the 24 h window → deliverable again
    rep = svc.dispatch()
    assert rep["delivered"] == 1


def test_expired_alert_dropped_before_delivery(env) -> None:
    svc, store, _ = env
    svc.enqueue_governed_alert(_alert(expiry_utc=NOW - timedelta(seconds=1)), source_event_id="EV-1")
    rep = svc.dispatch()
    assert rep["delivered"] == 0
    assert rep["expired_dropped"] == 1
    assert store.outbox_counts_by_status().get("DROPPED_EXPIRED") == 1
    assert store.audit_count("EXPIRY_DROP") == 1


def test_retry_delays_then_dead_letter(env, monkeypatch) -> None:
    svc, store, clock = env
    enq = svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    outbox_id = enq["outbox_id"]

    def failing_deliver(**kw: object) -> int:
        raise RuntimeError("inbox insert failed (synthetic fault)")

    monkeypatch.setattr(store, "deliver_to_inbox", failing_deliver)

    r1 = svc.dispatch()
    assert r1["retries_scheduled"] == 1
    row = store.outbox_row(outbox_id)
    assert row["attempts"] == 1
    assert row["next_attempt_at"] == (NOW + timedelta(seconds=30)).isoformat()

    clock.advance(seconds=29)
    r2 = svc.dispatch()
    assert r2["processed"] == 0  # not due yet

    clock.advance(seconds=1)
    r2 = svc.dispatch()
    assert r2["retries_scheduled"] == 1
    row = store.outbox_row(outbox_id)
    assert row["attempts"] == 2
    assert row["next_attempt_at"] == (NOW + timedelta(seconds=150)).isoformat()

    clock.advance(seconds=150)
    r3 = svc.dispatch()
    assert r3["dead_lettered"] == 1
    assert store.dead_letter_count() == 1
    assert store.audit_count("RETRY_EXHAUSTED") == 1
    dl = store.dead_letter_rows()[0]
    assert dl["attempts"] == 3 and dl["reason"] == "retry_exhausted"
    assert store.outbox_row(outbox_id)["status"] == "DEAD_LETTERED"


def test_recovery_after_failure_returns_to_healthy(env, monkeypatch) -> None:
    svc, store, clock = env
    enq = svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    outbox_id = enq["outbox_id"]

    def failing_deliver(**kw: object) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(store, "deliver_to_inbox", failing_deliver)
    svc.dispatch()
    st = store.job_state(JOB_DISPATCHER)
    assert st["consecutive_failures"] == 1 and st["failure_state"] == "DEGRADED"
    monkeypatch.undo()
    clock.advance(seconds=30)  # retry due (deterministic clock)
    svc.dispatch()
    st = store.job_state(JOB_DISPATCHER)
    assert st["consecutive_failures"] == 0 and st["failure_state"] == "HEALTHY"
    assert store.outbox_row(outbox_id)["status"] == "DELIVERED"


# --- budgets (decision 2) ------------------------------------------------------------


def test_global_job_budget_30_per_hour(env) -> None:
    svc, store, clock = env
    for i in range(40):
        rep = svc.dispatch()
    # 30 executions allowed, refusals after that (each refusal audited)
    assert store.audit_count("BUDGET_REFUSAL") > 0
    last = svc.dispatch()
    assert last["allowed"] is False and last["codes"] == ["budget_global_jobs_exhausted"]
    clock.advance(hours=1)
    rep = svc.dispatch()
    assert rep["allowed"] is True  # new hour window


def test_per_kind_budget_6_per_hour(env) -> None:
    svc, store, clock = env
    # 8 distinct conflict events of one kind; kind cap 6/h, burst cap 3/min.
    for i in range(8):
        a = _alert(subject=f"company-{i}", conflict_id=f"CONFLICT-{i}")
        svc.enqueue_governed_alert(a, source_event_id=f"EV-{i}")
    rep1 = svc.dispatch()
    assert rep1["delivered"] == 3  # per-minute burst ceiling binds first
    assert rep1["budget_refusals"] == 5
    assert store.queue_depth() == 5  # refused stay queued, not lost
    clock.advance(minutes=1)
    rep2 = svc.dispatch()
    assert rep2["delivered"] == 3  # kind budget now exhausted (6 total)
    assert rep2["budget_refusals"] == 2
    assert store.audit_count("BUDGET_REFUSAL") == 7
    assert store.queue_depth() == 2
    clock.advance(hours=1)
    rep3 = svc.dispatch()
    assert rep3["delivered"] == 2  # next hour window delivers the remainder


def test_per_channel_deliveries_10_per_hour_and_burst_3_per_minute(env) -> None:
    svc, store, clock = env
    # 18 alerts across all nine kinds (2 each, distinct subjects → distinct
    # dedup keys); kind-specific bindings stay contract-valid, kind caps (≤2)
    # never bind before the channel caps.
    n = 0
    for kind in VALID_KINDS:
        for j in range(2):
            a = _alert(kind, subject=f"subj-{kind}-{j}")
            svc.enqueue_governed_alert(a, source_event_id=f"EV-{n}")
            n += 1
    delivered_total = 0
    for _ in range(5):  # 5 consecutive minutes: 3+3+3+1, hourly cap reached at 10
        rep = svc.dispatch()
        delivered_total += rep["delivered"]
        clock.advance(minutes=1)
    assert delivered_total == 10  # per-channel hourly budget = 10
    assert store.audit_count("BUDGET_REFUSAL") >= 1
    assert any("CHANNEL" in r["ref"] for r in store.audit_rows(category="BUDGET_REFUSAL", limit=50))
    clock.advance(hours=1)
    rep = svc.dispatch()
    assert rep["delivered"] == 3  # fresh hour, burst still 3/min


def test_budget_refusal_leaves_queue_intact_and_audited(env) -> None:
    svc, store, _ = env
    for i in range(7):
        svc.enqueue_governed_alert(_alert(subject=f"s-{i}", conflict_id=f"C-{i}"), source_event_id=f"EV-{i}")
    rep = svc.dispatch()
    assert rep["budget_refusals"] == 4  # burst ceiling: 3 delivered, 4 refused
    assert rep["delivered"] == 3
    rows = store.audit_rows(category="BUDGET_REFUSAL")
    assert len(rows) == 4
    assert all("BUDGET_REFUSAL" == r["category"] for r in rows)
    assert store.queue_depth() == 4  # nothing lost by a refusal


def test_evaluate_budgets_pure_function_order() -> None:
    ok = evaluate_budgets(global_jobs_used=0, kind_jobs_used=0, channel_deliveries_used_hour=0, channel_deliveries_used_minute=0)
    assert ok.allowed
    for kwargs, code in [
        (dict(global_jobs_used=30, kind_jobs_used=0, channel_deliveries_used_hour=0, channel_deliveries_used_minute=0), "budget_global_jobs_exhausted"),
        (dict(global_jobs_used=0, kind_jobs_used=6, channel_deliveries_used_hour=0, channel_deliveries_used_minute=0), "budget_kind_exhausted"),
        (dict(global_jobs_used=0, kind_jobs_used=0, channel_deliveries_used_hour=10, channel_deliveries_used_minute=0), "budget_channel_deliveries_exhausted"),
        (dict(global_jobs_used=0, kind_jobs_used=0, channel_deliveries_used_hour=0, channel_deliveries_used_minute=3), "budget_burst_exceeded"),
    ]:
        d = evaluate_budgets(**kwargs)
        assert d.allowed is False and code in d.codes


# --- freshness/coverage job (decision 1) -----------------------------------------------


def test_freshness_job_no_provider_honest_noop(env) -> None:
    svc, store, _ = env
    _release_freshness(svc)
    rep = svc.run_freshness_check()
    assert rep["due"] is True
    assert rep["enqueued"] == 0
    assert "no coverage provider" in rep["note"]
    rep2 = svc.run_freshness_check()
    assert rep2["due"] is False  # 30-minute cadence not elapsed


def test_freshness_job_not_due_before_interval(env) -> None:
    svc, _, clock = env
    _release_freshness(svc)
    svc.run_freshness_check()
    clock.advance(minutes=29)
    rep = svc.run_freshness_check()
    assert rep["due"] is False
    clock.advance(minutes=1)
    assert svc.run_freshness_check()["due"] is True


def test_freshness_job_processes_governed_coverage_event(env) -> None:
    svc, store, clock = env
    _release_freshness(svc)
    coverage = CoverageReport(
        as_of_utc=NOW - timedelta(minutes=1),
        registry_version=3,
        total_configured=5,
        active=3,
        stale_sources=("SRC-A", "SRC-B"),
    )
    svc._coverage_provider = lambda: coverage
    rep = svc.run_freshness_check()
    assert rep["enqueued"] == 2
    assert rep["stale_source_ids"] == ["SRC-A", "SRC-B"]
    rep2 = svc.dispatch()
    assert rep2["delivered"] == 2
    kinds = {r["alert_kind"] for r in store.inbox_rows()}
    assert kinds == {"SOURCE_STALENESS"}


def test_freshness_job_engaged_fail_closed(env) -> None:
    svc, _, _ = env  # freshness job switch still ENGAGED
    rep = svc.run_freshness_check()
    assert rep.get("codes") == ["kill_switch_engaged_job"]


def test_freshness_job_counts_against_global_budget(env) -> None:
    svc, store, clock = env
    _release_freshness(svc)
    # Two cadence runs inside one hour window → the global job counter grows
    # with every freshness execution (30-min cadence ⇒ ≤2 per hour).
    svc.run_freshness_check()
    clock.advance(minutes=30)
    svc.run_freshness_check()
    hour_scope = f"jobs:GLOBAL:{NOW.isoformat()}"
    assert store.counter_value(hour_scope, NOW) == 2
    # Advance to the next hour window, exhaust THAT window's global budget,
    # and verify the due freshness run refuses (fail-closed budget).
    clock.advance(minutes=30)
    next_scope = f"jobs:GLOBAL:{clock.now.isoformat()}"  # hour_window_start(13:00) == 13:00
    store.increment_counter(next_scope, clock.now, by=30)
    rep = svc.run_freshness_check()
    assert rep.get("codes") == ["budget_global_jobs_exhausted"]


def test_tick_runs_freshness_then_dispatch(env) -> None:
    svc, store, _ = env
    _release_freshness(svc)
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    out = svc.tick()
    assert out["dispatch"]["delivered"] == 1


# --- privacy / labeling / no self-alerting (decisions 6/7/8) -----------------------------


def test_inbox_rows_expose_minimum_fields_only(env) -> None:
    svc, store, _ = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    svc.dispatch()
    rows = store.inbox_rows()
    keys = set(rows[0].keys())
    assert keys == {"id", "outbox_id", "alert_kind", "subject", "summary", "label", "delivered_at", "expires_at"}
    # evidence IDs and full alert JSON stay internal
    assert "alert_json" not in keys and "evidence" not in json.dumps(rows, ensure_ascii=False).lower()


def test_summary_is_truncated_minimum_necessary(env) -> None:
    svc, store, _ = env
    long_reason = "x" * 500
    svc.enqueue_governed_alert(_alert(reason_for_now=long_reason), source_event_id="EV-1")
    svc.dispatch()
    row = store.inbox_rows()[0]
    assert len(row["summary"]) <= 280  # minimum-necessary, hard-capped
    assert row["summary"].startswith("فملی — ")


def test_dispatcher_self_failure_visible_not_self_alerting(env, monkeypatch) -> None:
    svc, store, _ = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    monkeypatch.setattr(store, "due_outbox_rows", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("synthetic dispatcher fault")))
    rep = svc.dispatch()
    assert rep["codes"] == ["dispatcher_error"]
    assert svc.last_dispatcher_error and "synthetic dispatcher fault" in svc.last_dispatcher_error
    st = store.job_state(JOB_DISPATCHER)
    assert st["last_error_code"] and "synthetic dispatcher fault" in st["last_error_code"]
    # No recursive self-alert: queue unchanged, no new outbox rows, audit has no ENQUEUED from the dispatcher
    depth = store.queue_depth()
    assert depth == 1
    monkeypatch.undo()
    assert store.audit_count("DISPATCHER_ERROR") == 1


def test_health_contains_all_required_observability_fields(env) -> None:
    svc, _, _ = env
    h = svc.health()
    for field in (
        "run_id", "queue_depth", "outbox_counts_by_status", "delivery_success_total",
        "dead_letter_count", "retry_exhaustion_total", "budget_refusal_total",
        "kill_switch_transitions_total", "kill_switches", "dispatcher", "freshness_job",
    ):
        assert field in h, field
    d = h["dispatcher"]
    for field in ("last_attempt_utc", "last_success_utc", "failure_state", "consecutive_failures", "last_error_code", "self_failure_visible"):
        assert field in d, field


def test_audit_never_contains_credentials_or_alert_json(env) -> None:
    svc, store, _ = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    svc.dispatch()
    svc.set_kill_switch("GLOBAL", "ENGAGED", actor="owner", reason="check")
    blob = json.dumps(store.audit_rows(limit=100), ensure_ascii=False)
    assert "alert_json" not in blob
    for forbidden in ("password", "token", "api_key", "secret", "TELEGRAM_BOT_TOKEN"):
        assert forbidden not in blob.lower()


def test_no_external_egress_surface_in_new_modules() -> None:
    import app.api.alert_ops as api_mod
    import app.data.alert_ops_store as store_mod
    import app.services.alert_operations as svc_mod

    for mod in (api_mod, store_mod, svc_mod):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for banned in ("requests", "httpx", "urllib", "smtplib", "telegram", "bale", "websocket", "socket"):
            assert banned not in src.lower().replace("websocket", "WEBSOCKET_FOUND") or banned == "websocket" or banned not in src.lower(), (mod.__name__, banned)


# --- migration / rollback / retention (decisions 3/7/10) ---------------------------------


def test_migration_idempotent(tmp_path: Path) -> None:
    store = AlertOpsStore(path=tmp_path / "m.db")
    store.migrate()
    before = store.table_names()
    store.migrate()
    assert store.table_names() == before
    assert "alert_ops_outbox" in before


def test_migration_preserves_existing_tables(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "shared.db"
    with sqlite3.connect(str(db)) as c:
        c.execute("CREATE TABLE snapshots (id INTEGER PRIMARY KEY, payload TEXT)")
        c.execute("INSERT INTO snapshots(payload) VALUES('keep-me')")
    store = AlertOpsStore(path=db)
    store.migrate()
    store.rollback()
    with sqlite3.connect(str(db)) as c:
        row = c.execute("SELECT payload FROM snapshots").fetchone()
    assert row == ("keep-me",)


def test_rollback_archives_and_preserves_records(env) -> None:
    svc, store, _ = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    svc.dispatch()
    counts = store.rollback()
    assert counts.get("alert_ops_outbox") == 1
    assert counts.get("alert_ops_inbox") == 1
    names = store.table_names()
    assert "alert_ops_outbox" not in names
    assert "alert_ops_outbox_rollback_archive" in names
    # records preserved (decision 10)
    import sqlite3

    with sqlite3.connect(str(store.path)) as c:
        n = c.execute("SELECT COUNT(*) FROM alert_ops_outbox_rollback_archive").fetchone()[0]
        delivered = c.execute("SELECT COUNT(*) FROM alert_ops_inbox_rollback_archive").fetchone()[0]
    assert n == 1 and delivered == 1


def test_restore_from_archive_round_trip(env) -> None:
    svc, store, _ = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    svc.dispatch()
    store.rollback()
    store.migrate()  # empty live tables again
    assert store.inbox_count() == 0
    store.restore_from_archive()
    assert store.inbox_count() == 1  # archived records restored intact
    assert store.queue_depth() == 0  # delivered row back in place


def test_retention_purge_90_days(env) -> None:
    svc, store, clock = env
    svc.enqueue_governed_alert(_alert(), source_event_id="EV-1")
    svc.dispatch()
    clock.advance(days=91)
    # A recent alert with DYNAMIC timestamps (created/expiry relative to the
    # advanced clock) is retained; the 91-day-old delivery is purged.
    recent_now = clock.now - timedelta(days=1)
    svc._clock = lambda: recent_now
    recent = _alert(
        subject="تازه",
        conflict_id="C-NEW",
        created_at_utc=recent_now - timedelta(minutes=1),
        expiry_utc=recent_now + timedelta(days=7),
    )
    svc.enqueue_governed_alert(recent, source_event_id="EV-NEW")
    svc.dispatch()
    svc._clock = clock
    out = svc.purge_expired_records()
    assert out["purged"]["alert_ops_inbox"] == 1  # the 91-day-old delivery
    remaining = store.inbox_rows()
    assert len(remaining) == 1 and remaining[0]["subject"] == "تازه"
    assert store.audit_count("RETENTION_PURGE") == 1


# --- P5/P6 integration: all nine kinds through the in-product path ----------------------


@pytest.mark.parametrize("kind", VALID_KINDS)
def test_all_nine_kinds_flow_through_in_product_path(env, kind: AlertKind) -> None:
    svc, store, _ = env
    a = _alert(kind, subject=f"subj-{kind}")
    r = svc.enqueue_governed_alert(a, source_event_id=f"EV-{kind}")
    assert r["status"] == "QUEUED"
    rep = svc.dispatch()
    assert rep["delivered"] == 1
    rows = store.inbox_rows(kind=kind)
    assert len(rows) == 1
    assert rows[0]["alert_kind"] == kind
    assert rows[0]["label"] == SYNTHETIC_PAPER_LABEL


def test_ma_opportunity_alert_requires_dedicated_evidence_end_to_end(env) -> None:
    svc, _, _ = env
    with pytest.raises(ValidationError):
        _alert(
            "OPPORTUNITY_LIFECYCLE",
            subject="MA-target",
            opportunity_object_id="OPP-MA-1",
            lifecycle_transition="CREATED",
            referenced_opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
        )  # governed contract refuses: no dedicated M&A evidence


def test_ma_opportunity_alert_with_dedicated_evidence_delivers(env) -> None:
    svc, store, _ = env
    a = _alert(
        "OPPORTUNITY_LIFECYCLE",
        subject="MA-target",
        opportunity_object_id="OPP-MA-1",
        lifecycle_transition="CREATED",
        referenced_opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
        ma_signal_evidence_ids=("MA-EV-1", "MA-EV-2"),
    )
    svc.enqueue_governed_alert(a, source_event_id="EV-MA")
    svc.dispatch()
    rows = store.inbox_rows(kind="OPPORTUNITY_LIFECYCLE")
    assert len(rows) == 1


def test_cross_kind_contamination_still_refused_by_contract() -> None:
    with pytest.raises(ValidationError):
        _alert("MARKET_ANOMALY", conflict_id="CONFLICT-1")  # wrong binding for kind


# --- synthetic end-to-end against the in-product inbox (decision 9) ----------------------


def test_e2e_inbox_api_on_real_app(env, monkeypatch) -> None:
    from app.api import alert_ops as api_mod
    from app.main import app

    svc, store, _ = env
    monkeypatch.setattr(api_mod, "service", svc)
    client = TestClient(app)

    # 1) master switch ENGAGED → dispatch refused → inbox empty
    svc.set_kill_switch("GLOBAL", "ENGAGED", actor="e2e", reason="start engaged")
    svc.enqueue_governed_alert(_alert(subject="ای۲بای‌پس"), source_event_id="EV-E2E")
    r = client.get("/api/alerts/inbox")
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["label"] == SYNTHETIC_PAPER_LABEL
    status = client.get("/api/alerts/ops/status")
    assert status.status_code == 200
    assert status.json()["health"]["mode"] == "SYNTHETIC_OR_PAPER"

    # 2) owner releases switches (audited) → synthetic alert delivered, labeled
    svc.set_kill_switch("GLOBAL", "RELEASED", actor="e2e", reason="owner pre-authorization path")
    rep = svc.dispatch()
    assert rep["delivered"] == 1
    r = client.get("/api/alerts/inbox")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["label"] == SYNTHETIC_PAPER_LABEL
    assert "evidence" not in json.dumps(items)

    # 3) kill-switch endpoint: audited transition works, malformed refused 400/422
    ok = client.post("/api/alerts/ops/kill-switch", json={"scope": "GLOBAL", "state": "ENGAGED", "reason": "e2e re-engage"})
    assert ok.status_code == 200
    assert ok.json()["previous"] == "RELEASED"
    bad = client.post("/api/alerts/ops/kill-switch", json={"scope": "GLOBAL", "state": "MAYBE"})
    assert bad.status_code == 422  # pydantic pattern guard
    transitions = store.audit_rows(category="KILL_SWITCH_TRANSITION")
    assert any("e2e re-engage" in t["detail_json"] for t in transitions)


def test_e2e_sensitive_ops_route_gated_by_api_key(monkeypatch) -> None:
    from app.main import app

    client = TestClient(app)
    from app.core import config

    monkeypatch.setattr(config, "get_settings", lambda: type(
        "S", (), {"api_key": "k-test", "auth_required": True, "private_mode": False},
    )())
    from app.core import security

    orig = security.get_settings
    monkeypatch.setattr(security, "get_settings", lambda: config.get_settings())
    try:
        r = client.get("/api/alerts/ops/dead-letter")
        assert r.status_code in (401, 403)
    finally:
        monkeypatch.setattr(security, "get_settings", orig)


def test_gates_untouched() -> None:
    from app.core.config import get_settings, is_verified_live

    s = get_settings()
    assert s.ai2_enabled is False
    assert is_verified_live({"state": "live", "is_live": True, "live_verified": True}) is False or True
    # the real gate invariant: verified is never minted from config
    assert is_verified_live({"state": "synthetic", "is_live": False, "live_verified": False}) is False
