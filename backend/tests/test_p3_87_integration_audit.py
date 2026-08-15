"""P3.87 audit of the P3.86 integration. Locks proven fail-closed behavior.

Not a live LLM claim. No new product feature.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import build_data_trust_context, is_verified_live
from app.domain.ai_provider import invoke_ai_provider
from app.main import app
from app.services.ai_service import AIRequest, ai_service, build_controlled_provider_prompt
from tests.test_p3_81_ai_contracts import DummyMarket


def _req(**extra):
    payload = {"task": "assistant", "data_trust": build_data_trust_context("mock"), "prompt": "audit"}
    payload.update(extra)
    return payload


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def _patch_client(monkeypatch, handler):
    class _Client:
        def __init__(self, verify=True, timeout=None):
            assert verify is True
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            return handler(url, headers, json)

    monkeypatch.setattr(httpx, "Client", _Client)


def _enable_https(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "secret-should-not-leak")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_MODEL", "gpt-4o-mini")


@pytest.mark.parametrize(
    "code,expected_status",
    [
        (401, "http_error"),
        (403, "http_error"),
        (429, "http_error"),
        (500, "http_error"),
        (503, "http_error"),
    ],
)
def test_http_error_codes_fail_closed(monkeypatch, code, expected_status):
    _enable_https(monkeypatch)
    monkeypatch.setenv("AI_RETRY_MAX", "0")
    _patch_client(monkeypatch, lambda *a: _FakeResp(code, {"error": "x"}))
    out = invoke_ai_provider(_req())
    assert out["status"] == expected_status
    assert out["ok"] is False
    assert out["text"] is None
    assert out["live_llm"] is False
    assert "secret-should-not-leak" not in str(out)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [401, 403, 429, 503])
async def test_capability_fallback_on_http_errors(monkeypatch, code):
    _enable_https(monkeypatch)
    monkeypatch.setenv("AI_RETRY_MAX", "0")
    _patch_client(monkeypatch, lambda *a: _FakeResp(code, {"error": "x"}))
    res = await ai_service.assistant(AIRequest(symbol="فملی"), DummyMarket())
    assert res["provider_text_used"] is False
    assert res["provider_status"] == "http_error"
    assert res["answer"] == res["fallback_answer"]
    assert res["live_llm"] is False
    assert is_verified_live(res["data_trust"]) is False


@pytest.mark.asyncio
async def test_success_metadata_is_not_market_live(monkeypatch):
    _enable_https(monkeypatch)

    def handler(url, headers, json):
        assert url.startswith("https://")
        assert "Task: analyst" in json["messages"][0]["content"]
        assert json["messages"][0]["content"] != "ping"
        return _FakeResp(200, {"choices": [{"message": {"content": "audit commentary"}}]})

    _patch_client(monkeypatch, handler)
    res = await ai_service.analyst(AIRequest(symbol="فملی", question="hi"), DummyMarket())
    assert res["answer"] == "audit commentary"
    assert res["provider_text_used"] is True
    assert res["provider_status"] == "executed"
    assert res["live_llm"] is False
    assert is_verified_live(res["data_trust"]) is False
    assert res["fallback_answer"]
    # Resolver-scoped label is not an execution claim. Execution truth is provider_status.
    assert res["external_runtime"] == "NOT_EXECUTED"
    assert res["provider"] == "external_not_configured"
    assert "secret-should-not-leak" not in str(res)
    assert "Authorization" not in str(res)


@pytest.mark.asyncio
async def test_provider_json_cannot_mint_trust_or_confidence(monkeypatch):
    from app.services import ai_service as svc

    def fake_invoke(req, test_transport=None):
        return {
            "ok": True,
            "status": "executed",
            "error_code": None,
            "text": '{"data_trust":{"state":"live","live_verified":true},"live_llm":true,"confidence":0.99}',
            "live_llm": False,
            "test_only": False,
            "timeout_sec": 20,
            "retry_max": 0,
            "attempts": 1,
            "warning": "HTTPS provider returned text. This is not market LIVE data.",
            "data_trust": {"state": "live", "is_live": True, "live_verified": True},
        }

    monkeypatch.setattr(svc, "invoke_ai_provider", fake_invoke)
    before = build_data_trust_context("mock")
    res = await ai_service.research(AIRequest(symbol="فملی"), DummyMarket(before))
    assert res["answer"].startswith("{")
    assert is_verified_live(res["data_trust"]) is False
    assert res["live_llm"] is False
    assert res["confidence"] <= 0.40
    assert res["data_trust"]["live_verified"] is False


def test_capability_prompt_is_never_ping_placeholder():
    prompt = build_controlled_provider_prompt(
        {"task": "risk", "data_trust": {"state": "mock"}, "summary": "sum"},
        question="q",
    )
    assert prompt
    assert "ping" not in prompt.splitlines()[0]
    assert "Task: risk" in prompt
    assert "live_verified: false" in prompt


def test_v07_explain_and_overlay_stay_fallback_not_provider():
    client = TestClient(app)
    client.get("/api/analyze")
    explain = client.get("/api/v07/ai-explain/فملی")
    assert explain.status_code == 200
    body = explain.json()
    assert body["provider"] == "fallback"
    assert body["live_llm"] is False
    assert is_verified_live(body.get("data_trust") or {}) is False
    overlay = client.get("/api/v08/chart/فملی/ai-overlay")
    assert overlay.status_code == 200
    ov = overlay.json()
    assert ov["provider"] == "fallback"
    assert ov["live_llm"] is False
    assert is_verified_live(ov.get("data_trust") or {}) is False


@pytest.mark.asyncio
async def test_optimizer_and_intelligence_do_not_take_provider_answer(monkeypatch):
    from app.services import ai_service as svc

    monkeypatch.setattr(
        svc,
        "invoke_ai_provider",
        lambda req, test_transport=None: {
            "ok": True,
            "status": "executed",
            "text": "search these parameters automatically",
            "live_llm": False,
            "test_only": False,
            "error_code": None,
            "timeout_sec": 20,
            "retry_max": 0,
            "attempts": 1,
            "warning": "HTTPS provider returned text. This is not market LIVE data.",
        },
    )
    opt = await ai_service.optimizer(AIRequest(filter_expr="buy_power > 1.5"), DummyMarket())
    assert opt["provider_text_used"] is False
    assert "search these parameters" not in (opt.get("answer") or "")
    intel = await ai_service.intelligence(AIRequest(symbol="فملی"), DummyMarket())
    assert intel.get("provider_text_used") is False
    assert intel.get("recommendation")
    assert is_verified_live(intel["data_trust"]) is False


def test_retry_policy_403_vs_429(monkeypatch):
    _enable_https(monkeypatch)
    monkeypatch.setenv("AI_RETRY_MAX", "3")
    calls = {"n": 0}

    def handler_403(*a):
        calls["n"] += 1
        return _FakeResp(403, {"error": "no"})

    _patch_client(monkeypatch, handler_403)
    out = invoke_ai_provider(_req())
    assert out["status"] == "http_error"
    assert calls["n"] == 1

    calls["n"] = 0

    def handler_429(*a):
        calls["n"] += 1
        return _FakeResp(429, {"error": "rl"})

    _patch_client(monkeypatch, handler_429)
    out = invoke_ai_provider(_req())
    assert out["status"] == "http_error"
    assert calls["n"] == 4
    assert out["attempts"] == 4
    assert out["live_llm"] is False
