"""P3.83 fail-closed provider execution seam. TEST ONLY transports are labelled."""

from __future__ import annotations

import pytest

from app.core.config import build_data_trust_context, is_verified_live
from app.domain.ai_provider import invoke_ai_provider, resolve_ai_provider
from app.services.ai_service import AIRequest, ai_service


def _req(**extra):
    payload = {"task": "analyst", "data_trust": build_data_trust_context("mock")}
    payload.update(extra)
    return payload


def test_fallback_is_not_executed():
    out = invoke_ai_provider(_req())
    assert out["status"] == "not_executed"
    assert out["error_code"] == "fallback_selected"
    assert out["live_llm"] is False
    assert out["text"] is None
    assert out["ok"] is False


def test_missing_data_trust_blocks_execution():
    out = invoke_ai_provider({"task": "analyst"})
    assert out["status"] == "not_executed"
    assert out["error_code"] == "data_trust_required"


def test_client_secret_in_invoke_request_rejected():
    out = invoke_ai_provider(_req(api_key="sk-leak"))
    assert out["status"] == "not_executed"
    assert out["error_code"] == "client_secret_rejected"
    assert "sk-leak" not in str(out)


def test_invalid_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "not-a-real-vendor")
    monkeypatch.setenv("AI_API_KEY", "present-but-must-not-be-logged")
    out = invoke_ai_provider(_req())
    assert out["status"] == "invalid_provider"
    assert out["live_llm"] is False
    assert "present-but-must-not-be-logged" not in str(out)
    info = resolve_ai_provider()
    assert info["invocation_ready"] is False
    assert info["live_llm"] is False


def test_credential_missing(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    out = invoke_ai_provider(_req())
    assert out["status"] == "credential_missing"
    assert out["text"] is None
    assert out["live_llm"] is False


def test_production_path_never_executes_even_with_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "must-not-be-used")
    out = invoke_ai_provider(_req())
    assert out["status"] == "not_executed"
    assert out["error_code"] == "adapter_not_invoked"
    assert out["live_llm"] is False
    assert "must-not-be-used" not in str(out)


def test_timeout_test_only_transport(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "test-only-not-a-real-call")

    def boom(_payload):
        raise TimeoutError("timeout")

    out = invoke_ai_provider(_req(), test_transport=boom)
    assert out["status"] == "timeout"
    assert out["test_only"] is True
    assert out["live_llm"] is False


def test_unavailable_test_only_transport(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_API_KEY", "test-only-not-a-real-call")

    def boom(_payload):
        raise RuntimeError("down")

    out = invoke_ai_provider(_req(), test_transport=boom)
    assert out["status"] == "unavailable"
    assert out["test_only"] is True


def test_malformed_and_valid_test_only_transport(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "test-only-not-a-real-call")
    bad = invoke_ai_provider(_req(), test_transport=lambda p: "not-a-dict")
    assert bad["status"] == "malformed"
    assert bad["test_only"] is True
    good = invoke_ai_provider(_req(), test_transport=lambda p: {"text": "MOCK TEST ONLY sentence"})
    assert good["status"] == "executed_test_only"
    assert good["test_only"] is True
    assert good["live_llm"] is False
    assert "MOCK" in good["text"]


@pytest.mark.asyncio
async def test_assistant_records_execution_gate_without_llm_text():
    from tests.test_p3_81_ai_contracts import DummyMarket

    res = await ai_service.assistant(AIRequest(symbol="فملی"), DummyMarket())
    assert res["live_llm"] is False
    assert res["provider_execution"]["status"] == "not_executed"
    assert res["provider_execution"]["live_llm"] is False
    assert "text" not in res["provider_execution"]
    assert is_verified_live(res["data_trust"]) is False
