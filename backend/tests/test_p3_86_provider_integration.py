"""P3.86: controlled provider text integration into existing AI capabilities.

Mocked transport only. Not a live LLM claim.
"""

from __future__ import annotations

import pytest

from app.core.config import build_data_trust_context, is_verified_live
from app.domain.ai_provider import invoke_ai_provider
from app.services.ai_service import (
    AIRequest,
    apply_provider_capability_result,
    ai_service,
    build_controlled_provider_prompt,
    validated_provider_text,
)
from tests.test_p3_81_ai_contracts import DummyMarket

INTEGRATION_TASKS = ("assistant", "analyst", "research", "strategy", "risk")


def _ok_execution(text: str = "validated provider commentary") -> dict:
    return {
        "ok": True,
        "status": "executed",
        "error_code": None,
        "text": text,
        "live_llm": False,
        "test_only": False,
        "requested": "openai",
        "timeout_sec": 20,
        "retry_max": 0,
        "attempts": 1,
        "warning": "HTTPS provider returned text. This is not market LIVE data.",
    }


def _fail_execution(status: str, error_code: str) -> dict:
    return {
        "ok": False,
        "status": status,
        "error_code": error_code,
        "text": None,
        "live_llm": False,
        "test_only": False,
        "requested": "openai",
        "timeout_sec": 20,
        "retry_max": 0,
        "attempts": 1,
        "warning": f"HTTPS transport failed ({error_code}).",
    }


def _info():
    return {
        "mode": "external_not_configured",
        "provider_label": "external:openai:ready",
        "external_runtime": "NOT_EXECUTED",
        "warning": "HTTPS transport exists but is not invoked unless AI_EXECUTE=1.",
    }


@pytest.mark.parametrize("task", INTEGRATION_TASKS)
def test_validated_text_replaces_answer_and_preserves_fallback(task):
    trust = build_data_trust_context("mock")
    payload = {
        "task": task,
        "answer": "FALLBACK-ANSWER",
        "summary": "FALLBACK-SUMMARY خودکار",
        "suggestions": [{"type": "keep", "action": "manual"}],
        "confidence": 0.35,
        "data_trust": trust,
        "warnings": [],
        "safety": {"no_auto_trading": True},
    }
    out = apply_provider_capability_result(payload, _ok_execution("PROVIDER-OK"), info=_info())
    assert out["answer"] == "PROVIDER-OK"
    assert out["fallback_answer"] == "FALLBACK-ANSWER"
    assert out["summary"] == "FALLBACK-SUMMARY خودکار"
    assert out["provider_text_used"] is True
    assert out["source"] == "provider_validated"
    assert out["live_llm"] is False
    assert out["confidence"] == 0.35
    assert out["suggestions"] == [{"type": "keep", "action": "manual"}]
    assert out["data_trust"] is trust
    assert is_verified_live(out["data_trust"]) is False
    assert out["provider_status"] == "executed"
    assert out["provider_execution"]["text_used"] is True
    assert "text" not in out["provider_execution"]
    assert out["safety"]["no_live_llm_claim"] is True


def test_optimizer_never_takes_provider_text():
    payload = {
        "task": "optimizer",
        "answer": "NO AUTO CHANGE",
        "suggestions": [{"type": "filter", "action": "backtest"}],
        "confidence": 0.4,
        "data_trust": build_data_trust_context("mock"),
        "warnings": [],
        "safety": {"no_repository_changes": True},
    }
    out = apply_provider_capability_result(payload, _ok_execution("search these params"), info=_info())
    assert out["answer"] == "NO AUTO CHANGE"
    assert out["provider_text_used"] is False
    assert out["suggestions"][0]["action"] == "backtest"
    assert out["source"] != "provider_validated"


@pytest.mark.parametrize(
    "execution",
    [
        _fail_execution("timeout", "timeout"),
        _fail_execution("http_error", "http_401"),
        _fail_execution("malformed", "malformed_response"),
        _fail_execution("unavailable", "transport_unavailable"),
        _fail_execution("credential_missing", "credential_missing"),
        _fail_execution("not_executed", "execution_not_enabled"),
        _fail_execution("not_executed", "fallback_selected"),
        {"ok": True, "status": "executed", "text": "   ", "live_llm": False},
        {"ok": True, "status": "executed", "text": None, "live_llm": False},
        {"ok": True, "status": "executed", "text": "x", "live_llm": True},
    ],
)
def test_invalid_or_failed_execution_keeps_fallback(execution):
    payload = {
        "task": "assistant",
        "answer": "FALLBACK",
        "summary": "SUM",
        "data_trust": build_data_trust_context("mock"),
        "warnings": [],
        "confidence": 0.2,
    }
    out = apply_provider_capability_result(payload, execution, info=_info())
    assert out["answer"] == "FALLBACK"
    assert out["provider_text_used"] is False
    assert out["live_llm"] is False
    assert out["data_trust"]["state"] == "mock"


def test_provider_cannot_rewrite_data_trust():
    trust = build_data_trust_context("mock")
    payload = {
        "task": "analyst",
        "answer": "F",
        "data_trust": trust,
        "confidence": 0.3,
        "warnings": [],
    }
    execution = _ok_execution("claim LIVE now")
    execution["data_trust"] = {"state": "live", "is_live": True, "live_verified": True}
    out = apply_provider_capability_result(payload, execution, info=_info())
    assert out["data_trust"] is trust
    assert is_verified_live(out["data_trust"]) is False
    assert out["live_llm"] is False


def test_prompt_is_bounded_and_has_no_secret_fields():
    prompt = build_controlled_provider_prompt(
        {
            "task": "assistant",
            "summary": "sum",
            "key_observations": ["obs1", "obs2"],
            "data_trust": {"state": "mock"},
            "api_key": "should-not-be-copied",
        },
        question="وضعیت بازار؟",
    )
    assert "Task: assistant" in prompt
    assert "Data trust state: mock" in prompt
    assert "live_verified: false" in prompt
    assert "وضعیت بازار؟" in prompt
    assert "should-not-be-copied" not in prompt
    assert "api_key" not in prompt
    assert len(prompt) <= 2000


def test_empty_data_trust_is_not_executed():
    out = invoke_ai_provider({"task": "assistant", "data_trust": {}})
    assert out["status"] == "not_executed"
    assert out["error_code"] == "data_trust_required"
    assert out["text"] is None


def test_validated_provider_text_helpers():
    assert validated_provider_text(None) is None
    assert validated_provider_text(_fail_execution("timeout", "timeout")) is None
    assert validated_provider_text(_ok_execution("hello")) == "hello"


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name", INTEGRATION_TASKS)
async def test_capability_success_and_fallback(method_name, monkeypatch):
    from app.services import ai_service as svc

    captured = {}

    def fake_success(req, test_transport=None):
        captured["req"] = req
        return _ok_execution(f"OK-{method_name}")

    monkeypatch.setattr(svc, "invoke_ai_provider", fake_success)
    method = getattr(ai_service, method_name)
    res = await method(AIRequest(symbol="فملی", question="تحلیل؟"), DummyMarket())
    assert res["answer"] == f"OK-{method_name}"
    assert res["provider_text_used"] is True
    assert res["live_llm"] is False
    assert is_verified_live(res["data_trust"]) is False
    assert res["fallback_answer"]
    assert captured["req"]["prompt"]
    assert "Task:" in captured["req"]["prompt"]
    assert captured["req"]["data_trust"]["state"]
    assert "text" not in res["provider_execution"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        ("timeout", "timeout"),
        ("http_error", "http_401"),
        ("malformed", "malformed_response"),
        ("unavailable", "transport_unavailable"),
        ("credential_missing", "credential_missing"),
        ("not_executed", "execution_not_enabled"),
    ],
)
async def test_capability_fallback_on_provider_failure(status, code, monkeypatch):
    from app.services import ai_service as svc

    monkeypatch.setattr(svc, "invoke_ai_provider", lambda req, test_transport=None: _fail_execution(status, code))
    res = await ai_service.assistant(AIRequest(symbol="فملی"), DummyMarket())
    assert res["provider_text_used"] is False
    assert res["provider_status"] == status
    assert res["live_llm"] is False
    assert res["fallback_answer"] == res["answer"]
    assert is_verified_live(res["data_trust"]) is False


@pytest.mark.asyncio
async def test_execute_enabled_without_credential_is_fallback(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AI_EXECUTE", "1")
    res = await ai_service.analyst(AIRequest(symbol="فملی"), DummyMarket())
    assert res["provider_status"] == "credential_missing"
    assert res["provider_text_used"] is False
    assert res["live_llm"] is False


@pytest.mark.asyncio
async def test_execute_disabled_with_key_is_not_executed(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "secret-should-not-leak")
    monkeypatch.delenv("AI_EXECUTE", raising=False)
    res = await ai_service.research(AIRequest(symbol="فملی"), DummyMarket())
    assert res["provider_status"] == "not_executed"
    assert res["provider_execution"]["error_code"] == "execution_not_enabled"
    assert res["provider_text_used"] is False
    assert "secret-should-not-leak" not in str(res)


@pytest.mark.asyncio
async def test_https_success_through_assistant_is_not_live(monkeypatch):
    import httpx
    from app.domain import ai_provider

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "secret-should-not-leak")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_MODEL", "gpt-4o-mini")

    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "https commentary"}}]}

    class _Client:
        def __init__(self, verify=True, timeout=None):
            assert verify is True
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            assert url.startswith("https://")
            assert "secret-should-not-leak" in (headers.get("Authorization") or "")
            assert "Task: assistant" in json["messages"][0]["content"]
            return _Resp()

    monkeypatch.setattr(httpx, "Client", _Client)
    res = await ai_service.assistant(AIRequest(symbol="فملی", question="hi"), DummyMarket())
    assert res["answer"] == "https commentary"
    assert res["provider_text_used"] is True
    assert res["live_llm"] is False
    assert res["provider_status"] == "executed"
    assert "secret-should-not-leak" not in str(res)
    assert "Authorization" not in str(res)
    assert is_verified_live(res["data_trust"]) is False
    assert ai_provider._key_value() == "secret-should-not-leak"


@pytest.mark.asyncio
async def test_client_secret_rejected_on_invoke_and_api():
    from fastapi.testclient import TestClient
    from app.main import app

    out = invoke_ai_provider(
        {
            "task": "assistant",
            "data_trust": build_data_trust_context("mock"),
            "api_key": "sk-leak",
        }
    )
    assert out["error_code"] == "client_secret_rejected"
    assert "sk-leak" not in str(out)
    client = TestClient(app)
    res = client.post("/api/ai/assistant", json={"question": "hi", "api_key": "sk-leak"})
    assert res.status_code in {400, 422}


@pytest.mark.asyncio
async def test_non_https_still_blocked_on_capability(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_BASE_URL", "http://insecure.example/v1")
    res = await ai_service.risk(AIRequest(symbol="فملی"), DummyMarket())
    assert res["provider_status"] == "blocked"
    assert res["provider_text_used"] is False
    assert res["live_llm"] is False
