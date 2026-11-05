"""test_ai2_generation_api.py — WAVE-K (OA-3, owner directive 2026-11-05)

API-level battery for the governed AI-2 generation seam (prefix /api/v10/ai2,
router app/api/ai2_generation_api.py, service app/services/ai2_generation.py).
Acceptance coverage (OA-3 directive list, mapped):

- honest read-only posture while the committed gate is OFF (AI2_ENABLED=0):
  ai2_enabled False, execution_mode SYNTHETIC_OR_PAPER, production provider
  generation not permitted, in-memory registry disclosed, honesty envelope
  (test_posture_endpoint_honest, test_posture_and_honesty_envelope_fields);
- generation gated fail-closed by default: HTTP 200 with the typed outcome
  gated_not_executed / ai2_disabled and NOTHING executed — the candidate
  registry stays empty and the run ledger stays at zero
  (test_generate_gated_by_default, test_disabled_generate_is_not_ledgered);
- bounded request contracts enforced at the API edge (FastAPI 422)
  (test_generate_request_validation_422);
- the full governed success path through the REAL router (env-enabled gate +
  the service-sanctioned TEST-ONLY transport seam): status executed_shadow
  (the ONLY success status), versioned DRAFT candidate, complete provenance,
  SYNTHETIC_OR_PAPER labels everywhere, no "live" label anywhere
  (test_generate_success_path_via_api, test_no_live_label_in_ai2_payloads);
- duplicate suppression through the API (test_generate_duplicate_refused_via_api);
- human-approval-only state machine: a named approver (>= 4 chars) is the
  ONLY authority; DRAFT -> APPROVED -> PROMOTED (PAPER-FORWARD eligibility
  only); unknown candidates 404
  (test_candidates_list_and_get, test_approve_requires_named_approver,
  test_promote_requires_approved_state, test_approve_unknown_candidate_404);
- append-only run ledger shape on the governance transitions
  (test_runs_endpoint_append_only_shape);
- rate-limit identity isolation per the WAVE-3 convention: this file uses
  the DISTINCT client identity ("ai2-gen-api", 12431) so the global
  per-identity rate-limit bucket cannot collide with other test files
  (test_api_rate_limit_identity_isolation).

Honesty note: the success path injects an explicit TEST-ONLY transport (the
same mock-provider seam the service itself sanctions for offline tests). The
API never passes a transport and the production seam refuses remote-provider
generation without one (real_provider_generation_not_permitted) — nothing in
this battery is a live LLM product or live-market advice.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.api import ai2_generation_api
from app.core.config import get_settings
from app.main import create_app
from app.services.ai2_generation import AI2GenerationService

app = create_app()
client = TestClient(app, client=("ai2-gen-api", 12431))

PREFIX = "/api/v10/ai2"

# The mock transport's model output JSON — one strict typed spec proposal.
VALID_SPEC = {
    "strategy_name": "api-smoke-cross",
    "entry": {"kind": "cmp", "op": ">", "children": [
        {"kind": "series", "base": "close"},
        {"kind": "call", "fn": "sma", "children": [
            {"kind": "series", "base": "close"}, {"kind": "num", "value": 20}]}]},
    "exit": {"kind": "call", "fn": "crossunder", "children": [
        {"kind": "series", "base": "close"},
        {"kind": "call", "fn": "sma", "children": [
            {"kind": "series", "base": "close"}, {"kind": "num", "value": 20}]}]},
    "risk": {"stop_loss_pct": 2.0, "max_position_pct": 25.0},
}


def ok_transport(payload):
    """TEST-ONLY mock provider transport (the service-sanctioned offline seam)."""
    return {"ok": True, "status": "ok", "text": json.dumps(VALID_SPEC)}


class _TransportedService(AI2GenerationService):
    """Fresh AI2GenerationService whose generate() injects the TEST transport.

    The API layer calls generate() WITHOUT a transport and the production
    provider seam honestly refuses remote-provider generation without one
    (synthetic/paper-only policy). The API-level success path therefore uses
    the service-sanctioned TEST-transport injection while keeping every REAL
    router/pipeline code path (validation, gates, emitter, evaluation,
    registry, ledger, envelopes). Each instance is test-local, so registry,
    ledger and rate-limit state never leak between tests.
    """

    def __init__(self, transport=ok_transport) -> None:
        super().__init__()
        self._transport = transport

    async def generate(self, request, **kwargs):  # type: ignore[override]
        kwargs.setdefault("transport", self._transport)
        return await super().generate(request, **kwargs)


def _gen_body(**over):
    """A bounded generate body whose question carries intent + risk tokens."""
    body = {
        "question": "buy when close crosses above sma20 with 2 percent stop loss risk",
        "symbol": "FOLAD",
        "timeframe": "1D",
        "bar_count": 200,
        "end_bar_index": 12345,
        "clarifications": [{"key": "risk_appetite", "value": "moderate"}],
    }
    body.update(over)
    return body


# ---------------------------------------------------------------------------
# settings fixtures (lru_cached settings: env + cache_clear in setup AND
# teardown; no module-level os.environ writes — nothing leaks into the battery)
# ---------------------------------------------------------------------------
@pytest.fixture
def committed_gate(monkeypatch):
    """Pin the COMMITTED default gate (AI2_ENABLED absent → 0) for one test."""
    monkeypatch.delenv("AI2_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        yield
    finally:
        monkeypatch.delenv("AI2_ENABLED", raising=False)
        get_settings.cache_clear()


@pytest.fixture
def ai2_gate_env(monkeypatch):
    """Enable the AI-2 gate for one test (AI2_ENABLED=1; cache cleared both sides)."""
    monkeypatch.setenv("AI2_ENABLED", "1")
    get_settings.cache_clear()
    try:
        yield
    finally:
        monkeypatch.delenv("AI2_ENABLED", raising=False)
        get_settings.cache_clear()


@pytest.fixture
def transported_service(monkeypatch, ai2_gate_env):
    """Full API-level success-path harness.

    AI2_ENABLED=1 + AI_PROVIDER=openai + AI_API_KEY (a CONFIGURED remote
    provider, so the fallback seam would honestly fail) + a fresh
    _TransportedService patched into the router module — the provider
    resolution path is the real one, the transport is TEST-ONLY.
    """
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "unit-test-key")
    get_settings.cache_clear()
    service = _TransportedService(ok_transport)
    monkeypatch.setattr(ai2_generation_api, "ai2_generation_service", service)
    try:
        yield service
    finally:
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("AI_API_KEY", raising=False)
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 1. posture (honest while disabled)
# ---------------------------------------------------------------------------
def test_posture_endpoint_honest(committed_gate) -> None:
    r = client.get(f"{PREFIX}/posture")
    assert r.status_code == 200
    body = r.json()
    assert body["ai2_enabled"] is False
    assert body["generation_allowed"] is False
    assert body["execution_mode"] == "SYNTHETIC_OR_PAPER"
    assert body["production_provider_generation_permitted"] is False
    assert body["test_transport_required_for_remote_provider"] is True
    assert "in-memory" in body["registry_persistence"]
    honesty = body["honesty"]
    assert honesty["data_trust_label"] == "SYNTHETIC_OR_PAPER"


# ---------------------------------------------------------------------------
# 2. generate gated by default — nothing executes, nothing ledgered
# ---------------------------------------------------------------------------
def test_generate_gated_by_default(committed_gate) -> None:
    r = client.post(f"{PREFIX}/generate", json=_gen_body())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "gated_not_executed"
    assert body["error_code"] == "ai2_disabled"
    assert body["ok"] is False
    assert body["candidate_id"] is None
    assert body["honesty"]["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    # nothing executed: the registry stays empty ...
    rc = client.get(f"{PREFIX}/candidates")
    assert rc.status_code == 200
    assert rc.json()["count"] == 0
    # ... and the run ledger stays at zero (the disabled gate is NOT ledgered).
    rr = client.get(f"{PREFIX}/runs")
    assert rr.status_code == 200
    assert rr.json()["total"] == 0


# ---------------------------------------------------------------------------
# 3. bounded request contracts (FastAPI validation at the API edge)
# ---------------------------------------------------------------------------
def test_generate_request_validation_422(committed_gate) -> None:
    cases = [
        _gen_body(question="q" * 2001),   # question max_length=2000
        _gen_body(symbol=""),             # symbol min_length=1
        _gen_body(timeframe="2D"),        # timeframe whitelist pattern
        _gen_body(bar_count=49),          # bar_count ge=50
    ]
    for body in cases:
        r = client.post(f"{PREFIX}/generate", json=body)
        assert r.status_code == 422, body


# ---------------------------------------------------------------------------
# 4. the governed success path via the REAL router (TEST-ONLY transport)
# ---------------------------------------------------------------------------
def test_generate_success_path_via_api(transported_service) -> None:
    r = client.post(f"{PREFIX}/generate", json=_gen_body())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "executed_shadow"  # the ONLY success status
    assert body["candidate_id"]
    assert "ENTRY" in body["generated_source"]
    assert body["backtest_digest"]
    prov = body["provenance"]
    assert prov["prompt_sha256"]
    assert prov["generated_source_sha256"]
    assert prov["test_only_transport"] is True
    assert prov["execution_mode"] == "SYNTHETIC_OR_PAPER"
    assert body["honesty"]["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    # the TEST-ONLY transport is honestly disclosed in the warnings
    assert any("TEST ONLY" in w for w in body["warnings"])


# ---------------------------------------------------------------------------
# 5. duplicate suppression through the API
# ---------------------------------------------------------------------------
def test_generate_duplicate_refused_via_api(transported_service) -> None:
    body = _gen_body()
    r1 = client.post(f"{PREFIX}/generate", json=body)
    assert r1.status_code == 200
    first = r1.json()
    assert first["status"] == "executed_shadow"
    r2 = client.post(f"{PREFIX}/generate", json=body)
    assert r2.status_code == 200
    second = r2.json()
    assert second["status"] == "refused"
    assert second["error_code"] == "duplicate_generation"
    assert second["candidate_id"] == first["candidate_id"]


# ---------------------------------------------------------------------------
# 6. candidate surfaces (versioned registry)
# ---------------------------------------------------------------------------
def test_candidates_list_and_get(transported_service) -> None:
    rg = client.post(f"{PREFIX}/generate", json=_gen_body())
    assert rg.status_code == 200
    gen = rg.json()
    assert gen["status"] == "executed_shadow"

    rl = client.get(f"{PREFIX}/candidates")
    assert rl.status_code == 200
    listing = rl.json()
    assert listing["count"] >= 1
    assert "in-memory-only" in listing["note"]

    cid = gen["candidate_id"]
    rget = client.get(f"{PREFIX}/candidates/{cid}")
    assert rget.status_code == 200
    rec = rget.json()
    assert rec["status"] == "DRAFT"
    assert rec["source_sha256"] == gen["provenance"]["generated_source_sha256"]
    assert rec["honesty"]["data_trust_label"] == "SYNTHETIC_OR_PAPER"

    r404 = client.get(f"{PREFIX}/candidates/gen-9999-none")
    assert r404.status_code == 404
    assert r404.json()["detail"]["error"] == "candidate_not_found"


# ---------------------------------------------------------------------------
# 7. approval requires a NAMED approver (the model has none)
# ---------------------------------------------------------------------------
def test_approve_requires_named_approver(transported_service) -> None:
    rg = client.post(f"{PREFIX}/generate", json=_gen_body())
    cid = rg.json()["candidate_id"]

    short = client.post(f"{PREFIX}/candidates/{cid}/approve", json={"approver": "ab"})
    assert short.status_code == 422  # approver min_length=4 (named human required)

    ok = client.post(f"{PREFIX}/candidates/{cid}/approve", json={"approver": "owner-alice"})
    assert ok.status_code == 200
    rec = ok.json()
    assert rec["status"] == "APPROVED"
    assert rec["approved_by"] == "owner-alice"


# ---------------------------------------------------------------------------
# 8. promotion requires the APPROVED state (paper-forward only)
# ---------------------------------------------------------------------------
def test_promote_requires_approved_state(transported_service) -> None:
    rg = client.post(f"{PREFIX}/generate", json=_gen_body())
    cid = rg.json()["candidate_id"]

    early = client.post(f"{PREFIX}/candidates/{cid}/promote", json={"approver": "owner-alice"})
    assert early.status_code == 422
    assert early.json()["detail"]["error"] == "promotion_requires_approved_state"

    assert client.post(
        f"{PREFIX}/candidates/{cid}/approve", json={"approver": "owner-alice"}
    ).status_code == 200

    promoted = client.post(f"{PREFIX}/candidates/{cid}/promote", json={"approver": "owner-alice"})
    assert promoted.status_code == 200
    body = promoted.json()
    assert body["status"] == "PROMOTED"
    assert "PAPER-FORWARD" in body["promotion_scope"]

    again = client.post(f"{PREFIX}/candidates/{cid}/promote", json={"approver": "owner-alice"})
    assert again.status_code == 422
    # tightened per L-QA (LOW): the registry raises promotion_requires_approved_state
    # for a PROMOTED candidate — pin the exact single error.
    assert again.json()["detail"]["error"] == "promotion_requires_approved_state"


# ---------------------------------------------------------------------------
# 9. unknown candidate -> 404 (fail-closed approval surface)
# ---------------------------------------------------------------------------
def test_approve_unknown_candidate_404(committed_gate) -> None:
    r = client.post(
        f"{PREFIX}/candidates/does-not-exist/approve", json={"approver": "owner-alice"}
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "candidate_not_found"


# ---------------------------------------------------------------------------
# 10. append-only run ledger shape
# ---------------------------------------------------------------------------
def test_runs_endpoint_append_only_shape(transported_service) -> None:
    rg = client.post(f"{PREFIX}/generate", json=_gen_body())
    cid = rg.json()["candidate_id"]
    assert client.post(
        f"{PREFIX}/candidates/{cid}/approve", json={"approver": "owner-alice"}
    ).status_code == 200
    assert client.post(
        f"{PREFIX}/candidates/{cid}/promote", json={"approver": "owner-alice"}
    ).status_code == 200

    r = client.get(f"{PREFIX}/runs")
    assert r.status_code == 200
    payload = r.json()
    assert payload["append_only"] is True
    assert payload["total"] == 3  # generation + approval + promotion
    records = payload["records"]
    assert len(records) == 3
    assert all(rec["run_kind"] == "AI2_GENERATION" for rec in records)
    assert all(rec["status"] == "LEDGERED" for rec in records)
    assert [rec["approval_state"] for rec in records] == ["PENDING", "APPROVED", "APPROVED"]
    assert [rec["approved_by"] for rec in records] == [None, "owner-alice", "owner-alice"]


# ---------------------------------------------------------------------------
# 11. no "live" label anywhere in AI-2 payloads
# ---------------------------------------------------------------------------
def test_no_live_label_in_ai2_payloads(transported_service) -> None:
    r = client.post(f"{PREFIX}/generate", json=_gen_body())
    assert r.status_code == 200
    dump = json.dumps(r.json())
    assert '"live"' not in dump
    assert "SYNTHETIC_OR_PAPER" in dump


# ---------------------------------------------------------------------------
# 12. the disabled gate is NEVER ledgered (by design)
# ---------------------------------------------------------------------------
def test_disabled_generate_is_not_ledgered(committed_gate) -> None:
    for _ in range(3):
        r = client.post(f"{PREFIX}/generate", json=_gen_body())
        assert r.status_code == 200
        assert r.json()["status"] == "gated_not_executed"
    rr = client.get(f"{PREFIX}/runs")
    assert rr.status_code == 200
    assert rr.json()["total"] == 0


# ---------------------------------------------------------------------------
# 13. honesty envelope fields on the gated generate response
# ---------------------------------------------------------------------------
def test_posture_and_honesty_envelope_fields(committed_gate) -> None:
    r = client.post(f"{PREFIX}/generate", json=_gen_body())
    assert r.status_code == 200
    honesty = r.json()["honesty"]
    assert "approval" in honesty["model_authority"]
    assert "promotion" in honesty["model_authority"]
    assert "no broker" in honesty["egress"]
    assert "no external notification" in honesty["egress"]
    assert honesty["data_trust_label"] == "SYNTHETIC_OR_PAPER"


# ---------------------------------------------------------------------------
# 14. rate-limit identity isolation (WAVE-3 convention: distinct identity)
# ---------------------------------------------------------------------------
def test_api_rate_limit_identity_isolation(committed_gate) -> None:
    for _ in range(25):
        r = client.get(f"{PREFIX}/posture")
        assert r.status_code == 200
