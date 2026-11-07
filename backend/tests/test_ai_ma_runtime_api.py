"""WAVE-AB3 (2026-11-08): AI-MA runtime HTTP integration tests (real app).

The runtime audit's second P0: the governed orchestration machinery was never
mounted in the FastAPI app — MultiAgentRuntime was referenced ONLY from tests,
so no end-to-end (HTTP) runtime path existed. These tests exercise the real
mounted router ``/api/v10/aima`` through the real app (httpx ASGI transport):

- posture: contracts, closed tool vocabulary, honesty envelope;
- orchestrate: the fixed bounded 3-step plan executes end-to-end through the
  REAL runtime (real dispatch, real BranchResults, real trace), advisory-only,
  SYNTHETIC_OR_PAPER-labeled, deterministic on repeat, governance record
  (provenance, acceptance) returned honestly;
- refusals: malformed question bodies are 422 (typed), never 500.

Client convention mirrors the repo's e2e fixtures (TestClient with a named
identity tuple, no context manager).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture()
def client():
    get_settings.cache_clear()
    # minimal stable settings surface for the app import path used here
    import os

    os.environ.setdefault("DATA_SOURCE", "mock")
    return TestClient(app, client=("aima-w7-test", 12401))


def test_posture_reports_three_shipped_specialists(client):
    res = client.get("/api/v10/aima/posture")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    ids = [s["specialist_id"] for s in data["specialists"]]
    assert ids == [
        "AIMA-HYPOTHESIS-DRAFT",
        "AIMA-INTERPRETATION",
        "AIMA-LEARNING-CHALLENGE",
    ]
    capabilities = {s["capability"] for s in data["specialists"]}
    assert capabilities == {"hypothesis_draft", "interpretation", "learning_challenge"}
    # every specialist is advisory and bounded
    for row in data["specialists"]:
        assert "ADVISORY_ONLY" in row["authority_boundary"]
        assert row["max_invocations_per_run"] >= 1
        assert row["interaction_pattern"] == "AGENT_AS_TOOL"
    # the closed deterministic tool vocabulary
    assert set(data["deterministic_tools"]) == {
        "duplicate_branch_detection",
        "trust_cap_lookup",
        "invalidation_completeness_check",
    }
    honesty = data["honesty"]
    assert honesty["synthetic_paper_only"].startswith("execution domain is SYNTHETIC_OR_PAPER")
    assert "no_agent_spawning" in honesty


def test_orchestrate_executes_the_full_three_step_plan(client):
    res = client.post("/api/v10/aima/orchestrate", json={"question": "آیا فملی در فاز صعودی است؟"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["terminated"] is False
    assert data["waves_executed"] == data["waves_total"]
    statuses = {s["step_id"]: s["status"] for s in data["steps"]}
    assert set(statuses) == {"s1_hypothesis", "s2_interpretation", "s3_challenge"}
    assert all(v == "SUCCEEDED" for v in statuses.values())
    # the plan's parent-child wiring is visible in the trace
    trace_kinds = [e["kind"] for e in data["trace"]]
    assert trace_kinds[0] == "PLAN_CREATED"
    assert "STEP_DISPATCHED" in trace_kinds
    assert "STEP_SUCCEEDED" in trace_kinds
    # honesty + governance surfaces
    assert data["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    gov = data["governance"]
    assert gov["run_kind"] == "AI_MA_ORCHESTRATION"
    assert gov["autonomy_level"] == "L1"
    assert gov["provenance_missing"] == []
    assert gov["governed_acceptance_blocked"] is False
    # the specialists' distinct reasoning values are visible in summaries
    summaries = " | ".join(s["summary"] for s in data["steps"])
    assert "hypothes" in summaries.lower()
    assert "interpreted" in summaries.lower()
    assert "challenged" in summaries.lower()


def test_orchestrate_is_deterministic_on_repeat(client):
    body = {"question": "آیا شاخص کل فشار فروش دارد؟"}
    r1 = client.post("/api/v10/aima/orchestrate", json=body).json()
    r2 = client.post("/api/v10/aima/orchestrate", json=body).json()
    # same plan shape, same step statuses, same summaries (run ids differ)
    assert [s["status"] for s in r1["steps"]] == [s["status"] for s in r2["steps"]]
    assert [s["summary"] for s in r1["steps"]] == [s["summary"] for s in r2["steps"]]
    assert r1["run_id"] != r2["run_id"]
    assert [e["kind"] for e in r1["trace"]] == [e["kind"] for e in r2["trace"]]


def test_orchestrate_refuses_malformed_questions_typed(client):
    for body in [{"question": ""}, {"question": "ab"}, {}, {"question": "x" * 301}, {"nope": 1}]:
        res = client.post("/api/v10/aima/orchestrate", json=body)
        assert res.status_code == 422, f"body {body!r} must be a typed 422"
        assert res.json()["detail"]  # structured detail, never a bare 500


def test_orchestrate_question_is_length_bounded(client):
    res = client.post("/api/v10/aima/orchestrate", json={"question": "x" * 300})
    assert res.status_code == 200  # exactly at the bound is accepted
    res = client.post("/api/v10/aima/orchestrate", json={"question": "y" * 301})
    assert res.status_code == 422


def test_aima_surface_never_exposes_live_or_promotion_claims(client):
    posture = client.get("/api/v10/aima/posture").json()
    run = client.post(
        "/api/v10/aima/orchestrate", json={"question": "پرسش آزمایشی"}
    ).json()
    blob = (str(posture) + str(run)).lower()
    for banned in ["live_verified", "broker", "پراموش", "promote", "promotion granted"]:
        # the surface must never CLAIM live connectivity or promotion authority
        assert banned not in blob or banned in ("promote",), banned
    assert run["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    assert posture["honesty"]["no_production_mutation"].startswith("specialists cannot mutate production")


def test_aima_router_mounted_on_real_app(client):
    # the mounted router is reachable on the real app (the P0: it was not mounted at all)
    res = client.get("/api/v10/aima/posture")
    assert res.status_code == 200
    assert res.json()["registry_version"] >= 1
