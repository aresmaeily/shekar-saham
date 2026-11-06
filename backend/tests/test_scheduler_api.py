"""test_scheduler_api.py — WAVE-M (OA-4, owner directive 2026-11-05)

API-level battery for the bounded LOCAL internal scheduler
(prefix /api/v10/scheduler, router app/api/scheduler_api.py). Coverage:

- honest read-only posture while the committed gate is OFF
  (SCHEDULER_ENABLED absent → 0): enabled False, state created, honesty
  envelope, kill-switch RELEASED (test_posture_endpoint_honest,
  test_posture_honesty_envelope_fields);
- enqueue gated fail-closed by default: HTTP 503 with the honest code
  scheduler_disabled and NOTHING recorded
  (test_enqueue_gated_by_default_503, test_enqueue_refusal_records_nothing);
- bounded request contracts enforced at the API edge (FastAPI 422)
  (test_enqueue_request_validation_422);
- with the gate enabled (a dev/paper environment choice, not a committed
  default): unknown job type 400, governed research-loop job enqueues 200
  and completes honestly gated (the delegated runner's own fail-closed
  gates decide — the scheduler cannot open them), idempotent replay
  without re-execution, idempotency conflict 409, queue cap 429, run
  detail 404/200, bounded list, control pause/resume, kill-switch 423
  engage/release, history verification 200 (test_* family below);
- route-shape pin: every scheduler path lives under the ONE governed
  prefix /api/v10/scheduler (test_openapi_path_prefix_pin);
- rate-limit identity isolation per the WAVE-3 convention: this file uses
  the DISTINCT client identity ("scheduler-api", 12441).

Client discipline: every HTTP interaction runs inside
``with TestClient(app)`` — ONE persistent lifespan/portal loop per test
(the production shape; a bare TestClient spins a throwaway loop per
request, which would cancel the scheduler worker — a test-environment
artifact, not a product property).

Honesty note: nothing in this battery constructs a network transport or
asserts a live/verified posture; the enabled-path runs execute ONLY the
governed research-loop handler whose own gates refuse real execution
(gated_not_executed) under the committed defaults.
"""
from __future__ import annotations

import hashlib
import os
import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.services.internal_scheduler import reset_scheduler_cache
from app.services.scheduler_run_store import reset_scheduler_run_store_cache

app = create_app()

PREFIX = "/api/v10/scheduler"

# Process-local memory backend for the WHOLE battery (unit-test choice,
# disclosed in the store docstring; the real application path stays durable).
os.environ.setdefault("SCHEDULER_STORE_BACKEND", "memory")


def _reset_all() -> None:
    reset_scheduler_cache()
    reset_scheduler_run_store_cache()
    get_settings.cache_clear()


def _client() -> TestClient:
    return TestClient(app, client=("scheduler-api", 12441))


def _wait_terminal(c: TestClient, run_id: str, want: str = "COMPLETED", timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    state = None
    run = None
    while time.time() < deadline:
        run = c.get(f"{PREFIX}/runs/{run_id}").json()["run"]
        state = run["state"]
        if state == want:
            return run
        time.sleep(0.05)
    raise AssertionError(f"state not reached: want={want} got={state}")


@pytest.fixture
def committed_gate(monkeypatch):
    """Pin the COMMITTED default gate (SCHEDULER_ENABLED absent → 0)."""
    monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    monkeypatch.delenv("SCHEDULER_MAX_QUEUE", raising=False)
    _reset_all()
    try:
        with _client() as c:
            yield c
    finally:
        monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
        monkeypatch.delenv("SCHEDULER_MAX_QUEUE", raising=False)
        _reset_all()


@pytest.fixture
def scheduler_gate_env(monkeypatch):
    """Enable the scheduler gate for one test (dev/paper choice)."""
    monkeypatch.setenv("SCHEDULER_ENABLED", "1")
    _reset_all()
    try:
        with _client() as c:
            yield c
    finally:
        monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
        _reset_all()


def _valid_payload() -> dict:
    snapshot = hashlib.sha256(b"api-scheduler-context").hexdigest()
    return {
        "question": "پرسش پژوهشی سنتز (paper)",
        "task": "research",
        "record_id": "api-rec-1",
        "run_id": "api-run-1",
        "policy_version": "gov-1",
        "input_snapshot_sha256": snapshot,
    }


# ---------------------------------------------------------------------------
# Default-gate posture (read-only, always honest)
# ---------------------------------------------------------------------------

def test_posture_endpoint_honest(committed_gate):
    body = committed_gate.get(f"{PREFIX}/posture").json()
    p = body["posture"]
    assert p["enabled"] is False
    assert p["state"] in {"created", "stopped"}  # lifespan start refused (gate)
    assert p["kill_switch"] == "RELEASED"
    assert p["registered_job_types"] == ["research_loop"]
    assert p["bounded_by"]["max_queue"] >= 1
    assert p["bounded_by"]["max_concurrent"] >= 1


def test_posture_honesty_envelope_fields(committed_gate):
    body = committed_gate.get(f"{PREFIX}/posture").json()
    h = body["honesty"]
    for key in (
        "local_only",
        "no_egress_note",
        "synthetic_paper_only",
        "fail_closed_gate",
        "history_append_only",
        "bounded",
    ):
        assert h[key]
    ph = body["posture"]["honesty"]
    assert ph["no_egress"]
    assert ph["execution_domain"] == "SYNTHETIC_OR_PAPER"


# ---------------------------------------------------------------------------
# Fail-closed enqueue
# ---------------------------------------------------------------------------

def test_enqueue_gated_by_default_503(committed_gate):
    resp = committed_gate.post(
        f"{PREFIX}/runs",
        json={
            "job_type": "research_loop",
            "payload": _valid_payload(),
            "idempotency_key": "gate-1",
        },
    )
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["code"] == "scheduler_disabled"
    assert detail["honesty"]["fail_closed_gate"]


def test_enqueue_refusal_records_nothing(committed_gate):
    committed_gate.post(
        f"{PREFIX}/runs",
        json={
            "job_type": "research_loop",
            "payload": _valid_payload(),
            "idempotency_key": "gate-2",
        },
    )
    runs = committed_gate.get(f"{PREFIX}/runs").json()["runs"]
    assert runs == []
    verification = committed_gate.get(f"{PREFIX}/history/verify").json()["verification"]
    assert verification["events_verified"] == 0


def test_enqueue_request_validation_422(committed_gate):
    resp = committed_gate.post(f"{PREFIX}/runs", json={"job_type": "research_loop"})
    assert resp.status_code == 422
    resp2 = committed_gate.post(
        f"{PREFIX}/runs",
        json={"job_type": "", "payload": {}, "idempotency_key": "k"},
    )
    assert resp2.status_code == 422
    resp3 = committed_gate.post(f"{PREFIX}/runs", json={"job_type": "BadType", "payload": {}, "idempotency_key": "k"})
    assert resp3.status_code == 422  # job_type shape validator


def test_control_and_kill_switch_gated_by_default_503(committed_gate):
    """WAVE-M QA M1: EVERY mutating endpoint refuses while the gate is
    closed — including stop and kill-switch — and nothing is recorded."""
    for body in (
        {"action": "pause", "actor": "owner", "reason": "x"},
        {"action": "resume", "actor": "owner", "reason": "x"},
        {"action": "stop", "actor": "owner", "reason": "x"},
    ):
        resp = committed_gate.post(f"{PREFIX}/control", json=body)
        assert resp.status_code == 503, (body, resp.status_code)
        assert resp.json()["detail"]["code"] == "scheduler_disabled"
    resp = committed_gate.post(
        f"{PREFIX}/kill-switch",
        json={"state": "ENGAGE", "actor": "owner", "reason": "drill"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "scheduler_disabled"
    verification = committed_gate.get(f"{PREFIX}/history/verify").json()["verification"]
    assert verification["events_verified"] == 0  # zero history writes


# ---------------------------------------------------------------------------
# Enabled-path flows (dev/paper choice; nothing committed)
# ---------------------------------------------------------------------------

def test_unknown_job_type_400(scheduler_gate_env):
    resp = scheduler_gate_env.post(
        f"{PREFIX}/runs",
        json={"job_type": "nope", "payload": {}, "idempotency_key": "u1"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "unknown_job_type"


def test_research_loop_enqueue_and_gated_completion(scheduler_gate_env):
    resp = scheduler_gate_env.post(
        f"{PREFIX}/runs",
        json={
            "job_type": "research_loop",
            "payload": _valid_payload(),
            "idempotency_key": "flow-1",
            "actor": "owner",
        },
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["ok"] is True and result["replayed"] is False
    run_id = result["run_id"]
    run = _wait_terminal(scheduler_gate_env, run_id)
    types = [e["event_type"] for e in run["events"]]
    assert types == ["ENQUEUED", "STARTED", "SUCCEEDED", "COMPLETED"]
    outcome = next(
        e for e in run["events"] if e["event_type"] == "SUCCEEDED"
    )["payload"]["outcome"]
    assert outcome["outcome"] == "gated_not_executed"
    assert outcome["ok"] is False
    assert outcome["execution_domain"] == "SYNTHETIC_OR_PAPER"


def test_idempotent_replay_via_api(scheduler_gate_env):
    body = {
        "job_type": "research_loop",
        "payload": _valid_payload(),
        "idempotency_key": "idem-api-1",
    }
    first = scheduler_gate_env.post(f"{PREFIX}/runs", json=body).json()["result"]
    _wait_terminal(scheduler_gate_env, first["run_id"])
    second = scheduler_gate_env.post(f"{PREFIX}/runs", json=body).json()["result"]
    assert second["replayed"] is True
    assert second["run_id"] == first["run_id"]
    # no duplicate execution: exactly ONE SUCCEEDED event for the run
    run = scheduler_gate_env.get(f"{PREFIX}/runs/{first['run_id']}").json()["run"]
    succeeded = [e for e in run["events"] if e["event_type"] == "SUCCEEDED"]
    assert len(succeeded) == 1


def test_idempotency_conflict_409(scheduler_gate_env):
    resp = scheduler_gate_env.post(
        f"{PREFIX}/runs",
        json={
            "job_type": "research_loop",
            "payload": _valid_payload(),
            "idempotency_key": "conflict-1",
        },
    )
    assert resp.status_code == 200
    payload = _valid_payload()
    payload["question"] = "پرسش متفاوت"
    resp2 = scheduler_gate_env.post(
        f"{PREFIX}/runs",
        json={
            "job_type": "research_loop",
            "payload": payload,
            "idempotency_key": "conflict-1",
        },
    )
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["code"] == "idempotency_conflict"


def test_queue_cap_429(scheduler_gate_env, monkeypatch):
    monkeypatch.setenv("SCHEDULER_MAX_QUEUE", "1")
    _reset_all()
    try:
        scheduler_gate_env.post(f"{PREFIX}/control", json={"action": "pause", "actor": "owner", "reason": "hold"})
        ok = scheduler_gate_env.post(
            f"{PREFIX}/runs",
            json={"job_type": "research_loop", "payload": _valid_payload(), "idempotency_key": "q1"},
        )
        assert ok.status_code == 200
        full = scheduler_gate_env.post(
            f"{PREFIX}/runs",
            json={"job_type": "research_loop", "payload": _valid_payload(), "idempotency_key": "q2"},
        )
        assert full.status_code == 429
        assert full.json()["detail"]["code"] == "queue_full"
    finally:
        scheduler_gate_env.post(f"{PREFIX}/control", json={"action": "stop", "actor": "owner", "reason": "cleanup"})


def test_control_pause_resume_and_run_detail_404(scheduler_gate_env):
    missing = scheduler_gate_env.get(f"{PREFIX}/runs/does-not-exist")
    assert missing.status_code == 404
    paused = scheduler_gate_env.post(f"{PREFIX}/control", json={"action": "pause", "actor": "owner", "reason": "hold"})
    assert paused.status_code == 200
    assert paused.json()["result"]["state"] == "paused"
    resp = scheduler_gate_env.post(
        f"{PREFIX}/runs",
        json={"job_type": "research_loop", "payload": _valid_payload(), "idempotency_key": "hold-1"},
    )
    run_id = resp.json()["result"]["run_id"]
    time.sleep(0.2)
    assert scheduler_gate_env.get(f"{PREFIX}/runs/{run_id}").json()["run"]["state"] == "QUEUED"
    resumed = scheduler_gate_env.post(f"{PREFIX}/control", json={"action": "resume", "actor": "owner", "reason": "go"})
    assert resumed.status_code == 200
    run = _wait_terminal(scheduler_gate_env, run_id)
    assert run["state"] == "COMPLETED"


def test_kill_switch_423_engage_release(scheduler_gate_env):
    engaged = scheduler_gate_env.post(
        f"{PREFIX}/kill-switch",
        json={"state": "ENGAGE", "actor": "owner", "reason": "safety drill"},
    )
    assert engaged.status_code == 200
    assert engaged.json()["result"]["kill_switch"] == "ENGAGED"
    blocked = scheduler_gate_env.post(
        f"{PREFIX}/runs",
        json={"job_type": "research_loop", "payload": _valid_payload(), "idempotency_key": "kb-1"},
    )
    assert blocked.status_code == 423
    assert blocked.json()["detail"]["code"] == "kill_switch_engaged"
    released = scheduler_gate_env.post(
        f"{PREFIX}/kill-switch",
        json={"state": "RELEASE", "actor": "owner", "reason": "drill over"},
    )
    assert released.status_code == 200
    ok = scheduler_gate_env.post(
        f"{PREFIX}/runs",
        json={"job_type": "research_loop", "payload": _valid_payload(), "idempotency_key": "kb-2"},
    )
    assert ok.status_code == 200
    run_id = ok.json()["result"]["run_id"]
    _wait_terminal(scheduler_gate_env, run_id)


def test_kill_switch_validation_422(scheduler_gate_env):
    bad = scheduler_gate_env.post(f"{PREFIX}/kill-switch", json={"state": "TOGGLE", "actor": "owner", "reason": "x"})
    assert bad.status_code == 422
    empty_reason = scheduler_gate_env.post(
        f"{PREFIX}/kill-switch", json={"state": "ENGAGE", "actor": "owner", "reason": ""}
    )
    assert empty_reason.status_code == 422


def test_runs_list_bounded_and_history_verify(scheduler_gate_env):
    resp = scheduler_gate_env.post(
        f"{PREFIX}/runs",
        json={"job_type": "research_loop", "payload": _valid_payload(), "idempotency_key": "list-1"},
    )
    assert resp.status_code == 200
    run_id = resp.json()["result"]["run_id"]
    _wait_terminal(scheduler_gate_env, run_id)
    listing = scheduler_gate_env.get(f"{PREFIX}/runs?limit=1").json()
    assert len(listing["runs"]) <= 1
    verification = scheduler_gate_env.get(f"{PREFIX}/history/verify").json()["verification"]
    assert verification["ok"] is True
    assert verification["events_verified"] >= 1


def test_recent_events_endpoint_shape(committed_gate):
    body = committed_gate.get(f"{PREFIX}/runs?limit=10").json()
    assert "runs" in body and isinstance(body["runs"], list)


# ---------------------------------------------------------------------------
# Route shape pin (G2 counter-pin discipline: ONE governed prefix)
# ---------------------------------------------------------------------------

def test_openapi_path_prefix_pin():
    spec_paths = app.openapi().get("paths", {})
    sched = [p for p in spec_paths if "scheduler" in p]
    assert sched and all(p.startswith("/api/v10/scheduler") for p in sched)


def test_posture_reports_no_settings_write():
    """The scheduler posture honestly reports the settings discipline."""
    with _client() as c:
        body = c.get(f"{PREFIX}/posture").json()
    assert "no_settings_access" in body["posture"]["honesty"]
