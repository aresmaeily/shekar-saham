"""AI-1 ↔ alert-ops composition tests (additive; no production wiring).

What is composed here, and how:
- AI-1 monitoring contracts: ``app/domain/monitoring.py``
  (TriggerSpec/RetryPolicy/BudgetSpec, MonitoringJobSpec/State,
  ``effective_run_permission``, ``MAX_RUNS_PER_HOUR``, ``MAX_RETRY_ATTEMPTS``,
  the shared ``KillSwitchState`` literal) and
  ``app/domain/monitoring_governance.py`` (governed monitoring-cycle records
  via ``record_monitoring_cycle``).
- The alert-ops governed-alert producer: ``app/domain/governed_alerts.py``
  (nine-kind ``GovernedAlertObject``), ``app/domain/alert_operations.py``
  (owner-pinned budgets, kill-switch/budget/trust gates, retry schedule),
  ``app/services/alert_operations.AlertOperationsService`` and the additive
  ``alert_ops_*`` sqlite tables in ``app/data/alert_ops_store.py``.

Composition happens INSIDE the tests only: a governed monitoring cycle
record's coverage-derived staleness event is handed to the producer as an
ordinary ``GovernedAlertObject`` — exactly the object shape the producer
already accepts. No route, scheduler, delivery channel, producer loop or
module is created or modified. The tests pin that the composed behavior
preserves both sides' invariants: fail-closed kill-switch defaults with
stable recorded refusal reasons, in-product-inbox-only delivery, durable
dedup across independent monitoring runs, budget-exhaustion and retry-ceiling
semantics that agree across the two contract surfaces, expiry semantics that
match the opportunity layer, and a store surface that gains no new tables and
no egress imports.

Synthetic data only: injected deterministic clock, fixed timestamps, sqlite
store inside a pytest tmp dir (auto-cleaned by pytest).
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

import app.data.alert_ops_store as alert_ops_store_module
import app.services.alert_operations as alert_ops_service_module
from app.data.alert_ops_store import AlertOpsStore
from app.domain import (
    alert_operations as alert_ops_contracts,
    monitoring as monitoring_contracts,
    monitoring_governance as monitoring_governance_contracts,
)
from app.domain.alert_operations import (
    DELIVERY_CHANNEL,
    JOB_DISPATCHER,
    JOB_FRESHNESS_CHECK,
    OWNER_BUDGETS,
    SYNTHETIC_PAPER_LABEL,
    binding_id,
    canonical_fingerprint,
    dedup_key,
    evaluate_budgets,
    kill_switch_gate,
    next_retry_delay_seconds,
)
from app.domain.governed_alerts import GovernedAlertObject
from app.domain.governed_alerts import is_expired as alert_is_expired
from app.domain.monitoring import (
    MAX_RETRY_ATTEMPTS,
    MAX_RUNS_PER_HOUR,
    BudgetSpec,
    MonitoringJobSpec,
    MonitoringJobState,
    RetryPolicy,
    TriggerSpec,
    effective_run_permission,
)
from app.domain.monitoring_governance import record_monitoring_cycle
from app.domain.opportunity import OpportunityObject
from app.domain.opportunity import is_expired as opportunity_is_expired
from app.domain.run_governance import RunContext
from app.domain.source_registry import CoverageReport
from app.services.alert_operations import AlertOperationsService

UTC = timezone.utc
NOW = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)

#: The additive storage surface of the alert-ops producer (7 tables). The
#: composition must never grow it.
ALERT_OPS_TABLES = {
    "alert_ops_outbox",
    "alert_ops_inbox",
    "alert_ops_dead_letter",
    "alert_ops_budget_counters",
    "alert_ops_kill_switches",
    "alert_ops_job_state",
    "alert_ops_audit",
}

#: Outbound-transport modules that must never appear in the imports of any
#: composed module (no-egress invariant; import-level scan, comment-immune).
BANNED_EGRESS_IMPORTS = {
    "requests",
    "httpx",
    "urllib",
    "urllib3",
    "socket",
    "ssl",
    "smtplib",
    "ftplib",
    "telnetlib",
    "poplib",
    "imaplib",
    "telegram",
    "bale",
    "websocket",
    "websockets",
    "aiohttp",
}


class _Clock:
    """Deterministic, advanceable clock (no wall-clock time anywhere)."""

    def __init__(self, start: datetime = NOW) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: int) -> None:
        self.now = self.now + timedelta(**kwargs)


@pytest.fixture()
def env(tmp_path: Path) -> tuple[AlertOperationsService, AlertOpsStore, _Clock]:
    """Producer whose GLOBAL + dispatcher kill switches are explicitly RELEASED."""
    clock = _Clock()
    store = AlertOpsStore(path=tmp_path / "ops.db")
    svc = AlertOperationsService(store=store, clock=clock)
    svc.set_kill_switch("GLOBAL", "RELEASED", actor="fixture", reason="release for composition test")
    svc.set_kill_switch(JOB_DISPATCHER, "RELEASED", actor="fixture", reason="release for composition test")
    return svc, store, clock


@pytest.fixture()
def engaged_env(tmp_path: Path) -> tuple[AlertOperationsService, AlertOpsStore]:
    """Producer left at its schema-seeded fail-closed defaults (ENGAGED)."""
    store = AlertOpsStore(path=tmp_path / "ops-engaged.db")
    svc = AlertOperationsService(store=store, clock=_Clock())
    return svc, store


# --- AI-1 monitoring-side builders (P0-AMD-1 contracts, unchanged) ----------


def mon_spec(
    kill_switch: str = "ENGAGED",
    job_id: str = "job-ai1-mon-1",
    retry_policy: RetryPolicy | None = None,
) -> MonitoringJobSpec:
    return MonitoringJobSpec(
        job_id=job_id,
        target_source_ids=("SRC-A", "SRC-B"),
        trigger=TriggerSpec(kind="SCHEDULED", schedule_expression="*/30 * * * *"),
        retry_policy=retry_policy or RetryPolicy(max_attempts=2, backoff_seconds_base=5),
        budget=BudgetSpec(max_runs_per_hour=4, max_timeout_seconds=600, max_concurrency=1),
        observability_ref="obs://job-ai1-mon-1",
        alerting_ref="alerts://job-ai1-mon-1",
        kill_switch=kill_switch,  # type: ignore[arg-type]
    )


def mon_state(job_id: str = "job-ai1-mon-1", **over: object) -> MonitoringJobState:
    base: dict[str, object] = {"job_id": job_id, "last_attempt_utc": NOW}
    base.update(over)
    return MonitoringJobState(**base)  # type: ignore[arg-type]


def run_ctx(run_id: str = "run-mon-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        run_kind="MONITORING_CYCLE",
        policy_version="gov-1",
        created_at_utc=NOW,
    )


def coverage(as_of_utc: datetime | None = None, stale: tuple[str, ...] = ("SRC-A",)) -> CoverageReport:
    return CoverageReport(
        as_of_utc=as_of_utc or NOW - timedelta(minutes=1),
        registry_version=1,
        total_configured=2,
        active=1,
        stale_sources=stale,
    )


# --- monitoring-derived trigger (the composed hand-off object) --------------


def staleness_alert(*, alert_id: str, source_id: str, evidence_ref: str, run_id: str, **over: object) -> GovernedAlertObject:
    """The SOURCE_STALENESS alert a monitoring cycle's coverage report yields.

    Same derivation the alert-ops freshness job performs internally
    (kind-dedicated binding, coverage-evidence reference, synthetic trust),
    here built test-side from a governed cycle record — no new wiring.
    """
    d: dict[str, object] = {
        "alert_id": alert_id,
        "alert_kind": "SOURCE_STALENESS",
        "subject": source_id,
        "created_at_utc": NOW,
        "reason_for_now": "Governed monitoring cycle flagged the source as stale.",
        "confidence": Decimal("1"),
        "confidence_basis": "declared: governed coverage staleness classification (synthetic)",
        "data_trust_state": "synthetic",
        "risk_semantics": "staleness may invalidate downstream signals derived from this source",
        "evidence_ids": (evidence_ref,),
        "invalidation_conditions": (f"source {source_id} refreshed within its freshness SLA",),
        "expiry_open_ended": True,
        "run_id": run_id,
        "stale_source_ids": (source_id,),
    }
    d.update(over)
    return GovernedAlertObject(**d)  # type: ignore[arg-type]


def opportunity_probe(expiry_utc: datetime | None, *, expiry_open_ended: bool = False) -> OpportunityObject:
    """Minimal honest opportunity object for cross-layer expiry comparison."""
    return OpportunityObject(
        object_id="opp-probe-1",
        opportunity_kind="MARKET_STOCK_INVESTMENT_CANDIDATE",
        company_role="INVESTMENT_CANDIDATE",
        subject="فملی",
        created_at_utc=NOW,
        reason_for_now="synthetic probe for cross-layer expiry semantics",
        confidence=Decimal("0.5"),
        confidence_basis="declared probe input",
        data_trust_state="synthetic",
        risk_semantics="none; synthetic probe",
        evidence_ids=("ev-probe-1",),
        invalidation_conditions=("probe invalidated",),
        expiry_utc=expiry_utc,
        expiry_open_ended=expiry_open_ended,
        basis="EVIDENCE_BASED",
        run_id="run-probe-1",
    )


def cycle_record(
    record_id: str,
    *,
    run_id: str = "run-mon-1",
    kill_switch: str = "RELEASED",
    cov: CoverageReport | None = None,
    succeeded: tuple[str, ...] = ("SRC-B",),
    failed: tuple[str, ...] = ("SRC-A",),
) -> object:
    """Governed monitoring-cycle record binding a cycle to its permission truth."""
    spec = mon_spec(kill_switch=kill_switch)
    if kill_switch == "ENGAGED":
        succeeded, failed = (), ()
    rec = record_monitoring_cycle(
        record_id=record_id,
        spec=spec,
        state=mon_state(last_success_utc=NOW - timedelta(hours=1)),
        context=run_ctx(run_id),
        coverage=cov or coverage(),
        started_at_utc=NOW - timedelta(minutes=5),
        finished_at_utc=None if kill_switch == "ENGAGED" else NOW,
        sources_attempted=("SRC-A", "SRC-B"),
        sources_succeeded=succeeded,
        sources_failed=failed,
    )
    return rec


def _evidence_ref(rec: object) -> str:
    cov = rec.coverage  # type: ignore[attr-defined]
    return f"coverage:{cov.registry_version}:{cov.as_of_utc.isoformat()}"


# --- 1) fail-closed defaults agree on both sides ------------------------------


def test_fail_closed_kill_switch_defaults_agree_on_both_sides(engaged_env: tuple[AlertOperationsService, AlertOpsStore]) -> None:
    """The fail-closed default is the same literal on both surfaces: the store
    seeds every approved scope ENGAGED, and a fresh monitoring spec is born
    ENGAGED and may not run until explicitly released."""
    _, store = engaged_env
    assert store.kill_switch_state("GLOBAL") == "ENGAGED"
    assert store.kill_switch_state(JOB_DISPATCHER) == "ENGAGED"
    assert store.kill_switch_state(JOB_FRESHNESS_CHECK) == "ENGAGED"
    assert store.kill_switch_state("OA-UNAPPROVED-JOB") is None  # unapproved → missing → denied

    spec = mon_spec()
    assert spec.kill_switch == "ENGAGED"
    assert spec.run_allowed() is False
    assert effective_run_permission(spec, mon_state()) is False


# --- 2) kill switch ENGAGED → refusal recorded, nothing dispatched -----------


def test_engaged_kill_switch_refuses_cycle_and_dispatcher_with_recorded_reasons(
    engaged_env: tuple[AlertOperationsService, AlertOpsStore],
) -> None:
    """With the kill switch ENGAGED, the AI-1 side records a REFUSED_BY_POLICY
    cycle carrying no successes/events/finish, and the alert-ops side records
    a stable dispatch refusal — the monitoring-derived trigger is queued but
    never dispatched and nothing reaches the inbox."""
    svc, store = engaged_env
    rec = cycle_record("rec-refused", kill_switch="ENGAGED")
    assert rec.outcome == "REFUSED_BY_POLICY"  # type: ignore[attr-defined]
    assert rec.permission_granted is False  # type: ignore[attr-defined]
    assert rec.event_ids == () and rec.sources_succeeded == ()  # type: ignore[attr-defined]
    assert rec.finished_at_utc is None  # type: ignore[attr-defined]

    # A monitoring-derived trigger that "would have fired" reaches the
    # producer's durable queue, but dispatch is refused by the engaged switch.
    alert = staleness_alert(
        alert_id="STALE-ENGAGED-SRC-A",
        source_id="SRC-A",
        evidence_ref=_evidence_ref(rec),
        run_id="run-mon-1",
    )
    r = svc.enqueue_governed_alert(alert, source_event_id="EV-1")
    assert r["status"] == "QUEUED"

    rep = svc.dispatch()
    assert rep["allowed"] is False
    assert rep["codes"] == ["kill_switch_engaged_global"]
    assert rep["delivered"] == 0
    assert rep["queue_depth_after"] == 1  # queued, not lost, not dispatched
    assert store.inbox_count() == 0

    rows = store.audit_rows(category="KILL_SWITCH_REFUSAL")
    assert len(rows) == 1
    assert rows[0]["ref"] == JOB_DISPATCHER
    assert "kill_switch_engaged_global" in json.loads(rows[0]["detail_json"])["codes"]


# --- 3) shared kill-switch vocabulary; malformed states refused --------------


def test_kill_switch_vocabulary_is_shared_and_malformed_states_refused() -> None:
    """Both surfaces speak the same two-state fail-closed vocabulary: the
    alert-ops contracts literally reuse the AI-1 ``KillSwitchState`` type.
    Malformed states are refused by the gate and unrepresentable as a spec
    literal; the AI-1 HALTED refusal (explicit owner recovery) is stricter."""
    assert alert_ops_contracts.KillSwitchState is monitoring_contracts.KillSwitchState
    assert get_args(alert_ops_contracts.KillSwitchState) == ("ENGAGED", "RELEASED")

    assert kill_switch_gate("ENGAGED", "RELEASED").codes == ("kill_switch_engaged_global",)
    assert kill_switch_gate("RELEASED", "ENGAGED").codes == ("kill_switch_engaged_job",)
    assert kill_switch_gate("OPEN", "RELEASED").codes == ("kill_switch_missing_or_malformed",)
    assert kill_switch_gate("RELEASED", "RELEASED").allowed is True

    with pytest.raises(ValidationError):
        mon_spec(kill_switch="OPEN")  # type: ignore[arg-type]

    assert effective_run_permission(mon_spec("RELEASED"), mon_state(last_success_utc=NOW)) is True
    assert (
        effective_run_permission(
            mon_spec("RELEASED"), mon_state(failure_state="HALTED", failure_alert_sent=True)
        )
        is False
    )


# --- 4) released cycle → staleness alert → inbox ONLY -------------------------


def test_released_monitoring_cycle_derives_staleness_alert_delivered_inbox_only(
    env: tuple[AlertOperationsService, AlertOpsStore, _Clock],
) -> None:
    """A released monitoring job's cycle record (failed source forces an honest
    PARTIAL outcome) composes with the producer: the coverage-derived
    staleness alert is queued, delivered exactly once into IN_PRODUCT_INBOX
    with the mandated label, and a re-dispatch never duplicates it."""
    svc, store, _ = env
    rec = cycle_record("rec-1")  # SRC-A failed, SRC-B succeeded
    assert rec.outcome == "PARTIAL"  # type: ignore[attr-defined]
    assert rec.permission_granted is True  # type: ignore[attr-defined]

    evidence_ref = _evidence_ref(rec)
    alert = staleness_alert(
        alert_id="STALE-CYC1-SRC-A",
        source_id="SRC-A",
        evidence_ref=evidence_ref,
        run_id=rec.run_id,  # lineage: alert carries the monitoring run identity
    )
    assert alert.run_id == rec.run_id  # type: ignore[attr-defined]
    assert evidence_ref == f"coverage:1:{(NOW - timedelta(minutes=1)).isoformat()}"
    assert binding_id(alert) == "stale_sources:SRC-A"

    r = svc.enqueue_governed_alert(alert, source_event_id=evidence_ref)
    assert r["status"] == "QUEUED"

    rep = svc.dispatch()
    assert rep["allowed"] is True
    assert rep["delivered"] == 1
    assert rep["dead_lettered"] == 0

    rows = store.inbox_rows()
    assert len(rows) == 1
    assert rows[0]["alert_kind"] == "SOURCE_STALENESS"
    assert rows[0]["subject"] == "SRC-A"
    assert rows[0]["label"] == SYNTHETIC_PAPER_LABEL
    assert DELIVERY_CHANNEL == "IN_PRODUCT_INBOX"
    assert store.outbox_counts_by_status().get("DELIVERED") == 1
    assert store.dead_letter_count() == 0

    # Idempotent surface: a second dispatch re-delivers nothing.
    rep2 = svc.dispatch()
    assert rep2["delivered"] == 0
    assert store.inbox_count() == 1


# --- 5) independent monitoring runs → durable dedup, one delivery ------------


def test_independent_monitoring_runs_detecting_same_staleness_dedup_to_one_delivery(
    env: tuple[AlertOperationsService, AlertOpsStore, _Clock],
) -> None:
    """Two different monitoring runs (different run ids, different alert ids)
    detecting the same staleness produce the same canonical identity: the
    fingerprint ignores run identity, so the producer's durable dedup window
    suppresses the repeat instead of double-delivering."""
    svc, store, _ = env
    rec1 = cycle_record("rec-1", run_id="run-mon-1")
    rec2 = cycle_record("rec-2", run_id="run-mon-2")
    assert rec1.run_id != rec2.run_id  # type: ignore[attr-defined]

    ev1, ev2 = _evidence_ref(rec1), _evidence_ref(rec2)
    assert ev1 == ev2  # same coverage identity → same semantic trigger

    a1 = staleness_alert(alert_id="STALE-RUN1-SRC-A", source_id="SRC-A", evidence_ref=ev1, run_id="run-mon-1")
    a2 = staleness_alert(alert_id="STALE-RUN2-SRC-A", source_id="SRC-A", evidence_ref=ev2, run_id="run-mon-2")
    assert a1.alert_id != a2.alert_id and a1.run_id != a2.run_id
    assert canonical_fingerprint(a1) == canonical_fingerprint(a2)  # run identity ignored
    assert dedup_key(a1, ev1) == dedup_key(a2, ev2)

    r1 = svc.enqueue_governed_alert(a1, source_event_id=ev1)
    r2 = svc.enqueue_governed_alert(a2, source_event_id=ev2)
    assert r1["status"] == "QUEUED"
    assert r2["status"] == "SUPPRESSED"
    assert r2["outbox_id"] == r1["outbox_id"]

    rep = svc.dispatch()
    assert rep["delivered"] == 1
    assert store.inbox_count() == 1


# --- 6) expiry: dispatcher drop + cross-layer semantics parity ----------------


def test_expired_monitoring_derived_alert_dropped_and_expiry_semantics_match_opportunity_layer(
    env: tuple[AlertOperationsService, AlertOpsStore, _Clock],
) -> None:
    """Expiry is terminal on both sides with identical inclusive-boundary
    semantics: the producer drops an expired monitoring-derived alert BEFORE
    delivery (audited, dead-letter-free), and the governed-alert expiry helper
    agrees with the opportunity-layer helper at every instant."""
    svc, store, _ = env

    expiry = NOW + timedelta(days=1)
    alert = staleness_alert(
        alert_id="STALE-EXP-SRC-A",
        source_id="SRC-A",
        evidence_ref="coverage:1:exp",
        run_id="run-mon-1",
        expiry_open_ended=False,
        expiry_utc=expiry,
    )
    opp = opportunity_probe(expiry_utc=expiry)
    for at in (expiry - timedelta(seconds=1), expiry, expiry + timedelta(seconds=1)):
        assert opportunity_is_expired(opp, at) == alert_is_expired(alert, at)
    assert alert_is_expired(alert, expiry - timedelta(seconds=1)) is False
    assert alert_is_expired(alert, expiry) is True  # boundary inclusive

    open_alert = staleness_alert(
        alert_id="STALE-OPEN-SRC-A",
        source_id="SRC-A",
        evidence_ref="coverage:1:open",
        run_id="run-mon-1",
        expiry_utc=None,
        expiry_open_ended=True,
    )
    open_opp = opportunity_probe(None, expiry_open_ended=True)
    far = NOW + timedelta(days=3650)
    assert alert_is_expired(open_alert, far) is False
    assert opportunity_is_expired(open_opp, far) is False

    expired = staleness_alert(
        alert_id="STALE-PAST-SRC-A",
        source_id="SRC-A",
        evidence_ref="coverage:1:past",
        run_id="run-mon-1",
        expiry_open_ended=False,
        expiry_utc=NOW - timedelta(seconds=1),
    )
    assert svc.enqueue_governed_alert(expired, source_event_id="EV-EXP")["status"] == "QUEUED"
    rep = svc.dispatch()
    assert rep["delivered"] == 0
    assert rep["expired_dropped"] == 1
    assert store.outbox_counts_by_status().get("DROPPED_EXPIRED") == 1
    assert store.audit_count("EXPIRY_DROP") == 1
    assert store.inbox_count() == 0
    assert store.dead_letter_count() == 0


# --- 7) budget ceilings + refusal codes agree across the two surfaces --------


def test_budget_ceilings_and_refusal_codes_consistent_across_sides() -> None:
    """The owner-pinned producer budgets fit inside the AI-1 structural
    ceilings (a matching monitoring BudgetSpec is representable; an
    above-ceiling one is not), and the pure budget gate's refusal codes are
    exactly the codes the producer audits."""
    assert OWNER_BUDGETS.global_max_job_executions_per_hour <= MAX_RUNS_PER_HOUR
    assert OWNER_BUDGETS.per_alert_kind_max_executions_per_hour <= MAX_RUNS_PER_HOUR

    matching = BudgetSpec(
        max_runs_per_hour=OWNER_BUDGETS.global_max_job_executions_per_hour,
        max_timeout_seconds=600,
        max_concurrency=1,
    )
    assert matching.max_runs_per_hour == OWNER_BUDGETS.global_max_job_executions_per_hour
    with pytest.raises(ValidationError):
        BudgetSpec(max_runs_per_hour=MAX_RUNS_PER_HOUR + 1, max_timeout_seconds=600, max_concurrency=1)

    d = evaluate_budgets(
        global_jobs_used=OWNER_BUDGETS.global_max_job_executions_per_hour,
        kind_jobs_used=0,
        channel_deliveries_used_hour=0,
        channel_deliveries_used_minute=0,
    )
    assert d.allowed is False and d.first_code == "budget_global_jobs_exhausted"
    d = evaluate_budgets(
        global_jobs_used=0,
        kind_jobs_used=OWNER_BUDGETS.per_alert_kind_max_executions_per_hour,
        channel_deliveries_used_hour=0,
        channel_deliveries_used_minute=0,
    )
    assert d.first_code == "budget_kind_exhausted"
    d = evaluate_budgets(
        global_jobs_used=0,
        kind_jobs_used=0,
        channel_deliveries_used_hour=0,
        channel_deliveries_used_minute=OWNER_BUDGETS.per_minute_burst_max_deliveries,
    )
    assert d.first_code == "budget_burst_exceeded"


# --- 8) budget refusals keep monitoring-derived alerts queued, not lost ------


def test_budget_refusals_keep_monitoring_derived_alerts_queued_not_lost(
    env: tuple[AlertOperationsService, AlertOpsStore, _Clock],
) -> None:
    """Eight monitoring-derived staleness triggers meet the burst ceiling
    first (3/min), then the per-kind hourly cap (6): every refusal is audited
    with the same codes the pure gate emits, every refused trigger stays
    queued, and the next hour window drains the remainder."""
    svc, store, clock = env
    for i in range(8):
        alert = staleness_alert(
            alert_id=f"STALE-{i}",
            source_id=f"SRC-{i}",
            evidence_ref=f"coverage:1:stale-SRC-{i}",
            run_id="run-mon-1",
        )
        r = svc.enqueue_governed_alert(alert, source_event_id=f"EV-{i}")
        assert r["status"] == "QUEUED"

    rep1 = svc.dispatch()
    assert rep1["delivered"] == 3  # per-minute burst ceiling binds first
    assert rep1["budget_refusals"] == 5
    assert store.queue_depth() == 5

    clock.advance(minutes=1)
    rep2 = svc.dispatch()
    assert rep2["delivered"] == 3  # kind budget (6/h) now exhausted
    assert rep2["budget_refusals"] == 2
    assert store.queue_depth() == 2
    assert store.inbox_count() == 6
    assert store.dead_letter_count() == 0

    audited: list[str] = []
    for row in store.audit_rows(limit=50, category="BUDGET_REFUSAL"):
        detail = json.loads(row["detail_json"])
        audited.extend(detail.get("codes") or [detail["code"]])
    assert audited.count("budget_burst_exceeded") == 5
    assert audited.count("budget_kind_exhausted") == 2

    clock.advance(hours=1)
    rep3 = svc.dispatch()
    assert rep3["delivered"] == 2  # fresh hour window drains the queue
    assert store.queue_depth() == 0


# --- 9) retry ceilings + dead-letter agree for monitoring-derived alerts -----


def test_retry_ceilings_and_dead_letter_consistent_for_monitoring_derived_alert(
    env: tuple[AlertOperationsService, AlertOpsStore, _Clock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The owner-pinned delivery-retry ceiling (3 attempts: 30 s, 120 s, then
    dead-letter) is representable as an AI-1 RetryPolicy and stays inside the
    structural retry ceiling; a monitoring-derived alert that keeps failing
    delivery is retried on exactly that schedule and dead-lettered — never
    delivered, never lost silently."""
    svc, store, clock = env

    spec = mon_spec(
        kill_switch="RELEASED",
        retry_policy=RetryPolicy(
            max_attempts=OWNER_BUDGETS.max_delivery_attempts, backoff_seconds_base=30
        ),
    )
    assert spec.retry_policy.max_attempts == OWNER_BUDGETS.max_delivery_attempts == 3
    assert OWNER_BUDGETS.max_delivery_attempts <= MAX_RETRY_ATTEMPTS
    with pytest.raises(ValidationError):
        RetryPolicy(max_attempts=MAX_RETRY_ATTEMPTS + 1, backoff_seconds_base=0)

    assert next_retry_delay_seconds(1) == 30
    assert next_retry_delay_seconds(2) == 120
    assert next_retry_delay_seconds(OWNER_BUDGETS.max_delivery_attempts) is None  # exhaustion → dead-letter

    rec = cycle_record("rec-1")
    alert = staleness_alert(
        alert_id="STALE-RETRY-SRC-A",
        source_id="SRC-A",
        evidence_ref=_evidence_ref(rec),
        run_id=rec.run_id,  # type: ignore[attr-defined]
    )
    enq = svc.enqueue_governed_alert(alert, source_event_id=_evidence_ref(rec))
    outbox_id = enq["outbox_id"]

    def failing_deliver(**kw: object) -> int:
        raise RuntimeError("inbox insert failed (synthetic fault)")

    monkeypatch.setattr(store, "deliver_to_inbox", failing_deliver)

    r1 = svc.dispatch()
    assert r1["retries_scheduled"] == 1
    row = store.outbox_row(outbox_id)
    assert row["attempts"] == 1
    assert row["next_attempt_at"] == (NOW + timedelta(seconds=30)).isoformat()

    clock.advance(seconds=30)
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
    assert store.inbox_count() == 0  # nothing ever left through the inbox


# --- 10) the composition adds no tables and no egress surface -----------------


def test_composition_adds_no_tables_and_no_egress_surface(
    env: tuple[AlertOperationsService, AlertOpsStore, _Clock],
) -> None:
    """Composing AI-1 records with the producer must leave the storage surface
    untouched: the same 7 additive ``alert_ops_*`` tables before and after a
    full enqueue→dispatch flow and a re-migration; and none of the five
    composed modules imports any outbound-transport capability."""
    svc, store, _ = env

    rec = cycle_record("rec-1")
    alert = staleness_alert(
        alert_id="STALE-SURFACE-SRC-A",
        source_id="SRC-A",
        evidence_ref=_evidence_ref(rec),
        run_id=rec.run_id,  # type: ignore[attr-defined]
    )
    svc.enqueue_governed_alert(alert, source_event_id=_evidence_ref(rec))
    rep = svc.dispatch()
    assert rep["delivered"] == 1

    before = store.table_names()
    assert ALERT_OPS_TABLES <= before
    store.migrate()
    assert store.table_names() == before  # idempotent; no new tables

    composed_modules = (
        monitoring_contracts,
        monitoring_governance_contracts,
        alert_ops_contracts,
        alert_ops_service_module,
        alert_ops_store_module,
    )
    for mod in composed_modules:
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_roots.add(node.module.split(".")[0])
        assert not (imported_roots & BANNED_EGRESS_IMPORTS), (mod.__name__, imported_roots & BANNED_EGRESS_IMPORTS)
