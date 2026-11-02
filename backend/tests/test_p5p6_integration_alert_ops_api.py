"""T7 P5/P6 integration audit — alert-ops API runtime-chain gaps.

Covers ONLY the connected runtime paths that the existing D-AI-30 battery
(``test_dai30_alert_operations.py``) leaves uncovered:

1. ``POST /api/alerts/ops/dispatch`` — the manual dispatcher route (route →
   ``service.tick()`` → freshness no-op + dispatch → inbox persistence).
   No existing test exercises this route at all.
2. ``GET /api/alerts/ops/dead-letter`` — the SUCCESS path (rows surfaced
   after a real retry-exhaustion flow). Only the 401/403 gating was tested.
3. The dispatch route's API-key gate: 401 without the key when configured,
   200 with the exact header (only the dead-letter GET had a negative test).
4. Full chain trigger → admission → persist → API-read with everything
   flowing THROUGH the route (existing e2e calls ``svc.dispatch()``
   directly and only reads via API).

Deterministic clocks + tmp-path stores ONLY; the real app is used for
routing but the service is swapped exactly like the existing e2e test does
(so no runtime DB is written by these tests beyond the additive idempotent
singleton migrate that every existing app-importing test already performs).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data.alert_ops_store import AlertOpsStore
from app.domain.alert_operations import (
    JOB_DISPATCHER,
    JOB_FRESHNESS_CHECK,
    SYNTHETIC_PAPER_LABEL,
)
from app.domain.governed_alerts import GovernedAlertObject
from app.services.alert_operations import AlertOperationsService

UTC = timezone.utc
NOW = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)


class _Clock:
    def __init__(self, start: datetime = NOW) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: object) -> None:
        self.now = self.now + timedelta(**kw)  # type: ignore[arg-type]


def _alert(subject: str = "api-chain", **over: object) -> GovernedAlertObject:
    d: dict[str, object] = {
        "alert_id": "ALERT-API-1",
        "alert_kind": "SOURCE_CONFLICT",
        "subject": subject,
        "created_at_utc": NOW - timedelta(minutes=1),
        "reason_for_now": "two primary sources disagree on the same figure",
        "confidence": Decimal("0.5"),
        "confidence_basis": "declared by the detecting governed run",
        "data_trust_state": "synthetic",
        "risk_semantics": "informational; no position implication",
        "evidence_ids": ("E1", "E2"),
        "invalidation_conditions": ("conflict resolved with reviewer + rule",),
        "expiry_utc": NOW + timedelta(days=7),
        "run_id": "RUN-API-1",
        "conflict_id": "CONFLICT-API-1",
    }
    d.update(over)
    return GovernedAlertObject(**d)


@pytest.fixture()
def api_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Real app routing + tmp-path-backed service swapped into the API module."""
    from app.api import alert_ops as api_mod

    clock = _Clock()
    store = AlertOpsStore(path=tmp_path / "ops.db")
    svc = AlertOperationsService(store=store, clock=clock)
    svc.set_kill_switch("GLOBAL", "RELEASED", actor="audit", reason="release")
    svc.set_kill_switch(JOB_DISPATCHER, "RELEASED", actor="audit", reason="release")
    svc.set_kill_switch(JOB_FRESHNESS_CHECK, "RELEASED", actor="audit", reason="release")
    monkeypatch.setattr(api_mod, "service", svc)
    client = TestClient(_make_client_app())
    return svc, store, clock, client


def _make_client_app():
    from app.main import app

    return app


def test_full_chain_trigger_to_api_dispatch_to_inbox_read(api_env) -> None:
    """trigger(GovernedAlertObject) → enqueue gate → outbox persist →
    POST /api/alerts/ops/dispatch (tick) → inbox persist → GET /api/alerts/inbox."""
    svc, store, _clock, client = api_env

    admitted = svc.enqueue_governed_alert(_alert(), source_event_id="EV-API-1")
    assert admitted["status"] == "QUEUED"
    assert store.queue_depth() == 1

    # The dispatch happens THROUGH the API route (route → tick → freshness
    # no-op + dispatcher), never by calling svc.dispatch() directly.
    r = client.post("/api/alerts/ops/dispatch")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["freshness"]["note"].startswith("no coverage provider")
    assert body["result"]["dispatch"]["delivered"] == 1
    assert body["result"]["dispatch"]["allowed"] is True
    assert body["result"]["dispatch"]["queue_depth_after"] == 0

    row = store.outbox_row(admitted["outbox_id"])
    assert row["status"] == "DELIVERED"

    inbox = client.get("/api/alerts/inbox")
    assert inbox.status_code == 200
    payload = inbox.json()
    assert payload["label"] == SYNTHETIC_PAPER_LABEL
    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["alert_kind"] == "SOURCE_CONFLICT"
    assert item["subject"] == "api-chain"
    assert item["label"] == SYNTHETIC_PAPER_LABEL
    # decision 7: minimum-necessary fields only — no evidence ids, no alert JSON.
    assert "evidence" not in json.dumps(payload)
    assert "alert_json" not in item

    status = client.get("/api/alerts/ops/status")
    assert status.status_code == 200
    health = status.json()["health"]
    assert health["delivery_success_total"] == 1
    assert health["dispatcher"]["failure_state"] == "HEALTHY"
    assert health["mode"] == "SYNTHETIC_OR_PAPER"


def test_dispatch_route_surfaces_fail_closed_kill_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh deployment (all switches ENGAGED): the route must surface the
    fail-closed refusal codes and NOT consume budgets or deliver anything."""
    from app.api import alert_ops as api_mod

    store = AlertOpsStore(path=tmp_path / "ops.db")
    svc = AlertOperationsService(store=store, clock=_Clock())  # defaults ENGAGED
    svc.enqueue_governed_alert(_alert(subject="held"), source_event_id="EV-HELD")
    monkeypatch.setattr(api_mod, "service", svc)
    client = TestClient(_make_client_app())

    r = client.post("/api/alerts/ops/dispatch")
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["freshness"]["codes"] == ["kill_switch_engaged_global"]
    assert result["dispatch"]["codes"] == ["kill_switch_engaged_global"]
    assert result["dispatch"]["allowed"] is False
    # A refused run is not an execution: the global job budget stays untouched.
    hour_scope = f"jobs:GLOBAL:{datetime(NOW.year, NOW.month, NOW.day, NOW.hour, tzinfo=UTC).isoformat()}"
    assert store.counter_value(hour_scope, NOW) == 0
    assert client.get("/api/alerts/inbox").json()["items"] == []


def test_dead_letter_route_after_retry_exhaustion(api_env, monkeypatch: pytest.MonkeyPatch) -> None:
    """retry_exhaustion → dead-letter rows → the gated route surfaces them
    (success path; only the 401 gating existed before) with no alert_json leak."""
    svc, store, clock, client = api_env
    enq = svc.enqueue_governed_alert(_alert(subject="dl-route"), source_event_id="EV-DL")
    outbox_id = enq["outbox_id"]

    original_deliver = store.deliver_to_inbox

    def failing_deliver(**kw: object) -> int:
        raise RuntimeError("inbox insert failed (synthetic fault)")

    monkeypatch.setattr(store, "deliver_to_inbox", failing_deliver)
    assert svc.dispatch()["retries_scheduled"] == 1
    clock.advance(seconds=30)
    assert svc.dispatch()["retries_scheduled"] == 1
    clock.advance(seconds=120)
    assert svc.dispatch()["dead_lettered"] == 1
    monkeypatch.setattr(store, "deliver_to_inbox", original_deliver)

    r = client.get("/api/alerts/ops/dead-letter")
    assert r.status_code == 200
    payload = r.json()
    assert payload["ok"] is True
    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["alert_kind"] == "SOURCE_CONFLICT"
    assert item["reason"] == "retry_exhausted"
    assert item["attempts"] == 3
    assert item["outbox_id"] == outbox_id
    # decision 7: dead-letter inspection carries refs/codes only.
    assert "alert_json" not in json.dumps(payload)
    assert store.outbox_row(outbox_id)["status"] == "DEAD_LETTERED"


def test_dispatch_route_api_key_gate_negative_and_positive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With an owner key configured, POST /api/alerts/ops/dispatch is denied
    without the header and allowed with the exact header (route-level guard,
    positive path never tested for this route)."""
    from app.api import alert_ops as api_mod
    from app.core import config, security

    stub = type("S", (), {"api_key": "k-audit", "auth_required": True, "private_mode": False})()
    monkeypatch.setattr(config, "get_settings", lambda: stub)
    monkeypatch.setattr(security, "get_settings", lambda: config.get_settings())
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "get_settings", lambda: config.get_settings())

    store = AlertOpsStore(path=tmp_path / "ops.db")
    svc = AlertOperationsService(store=store, clock=_Clock())
    svc.set_kill_switch("GLOBAL", "RELEASED", actor="audit", reason="release")
    svc.set_kill_switch(JOB_DISPATCHER, "RELEASED", actor="audit", reason="release")
    svc.set_kill_switch(JOB_FRESHNESS_CHECK, "RELEASED", actor="audit", reason="release")
    monkeypatch.setattr(api_mod, "service", svc)
    client = TestClient(_make_client_app())

    denied = client.post("/api/alerts/ops/dispatch")
    assert denied.status_code == 401

    allowed = client.post("/api/alerts/ops/dispatch", headers={"X-API-Key": "k-audit"})
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True
    assert allowed.json()["result"]["dispatch"]["allowed"] is True
