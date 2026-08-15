"""P3.89: Gemini credential stays out of the request URL. Not a live LLM claim."""

from __future__ import annotations

import httpx

from app.core.config import build_data_trust_context
from app.domain.ai_provider import _build_provider_http, https_transport, invoke_ai_provider


def test_gemini_uses_header_not_query_string():
    url, headers, body = _build_provider_http("gemini", "secret-gemini-key", "hi")
    assert url.startswith("https://")
    assert "key=" not in url
    assert "secret-gemini-key" not in url
    assert headers.get("x-goog-api-key") == "secret-gemini-key"
    assert "secret-gemini-key" not in str(body)


def test_openai_and_anthropic_still_use_headers():
    o_url, o_headers, _ = _build_provider_http("openai", "secret-openai-key", "hi")
    assert o_url.startswith("https://")
    assert "secret-openai-key" not in o_url
    assert "secret-openai-key" in o_headers["Authorization"]
    a_url, a_headers, _ = _build_provider_http("anthropic", "secret-anthropic-key", "hi")
    assert a_url.startswith("https://")
    assert "secret-anthropic-key" not in a_url
    assert a_headers["x-api-key"] == "secret-anthropic-key"


def test_gemini_transport_exception_does_not_surface_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_API_KEY", "secret-gemini-key")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_MODEL", "gemini-1.5-flash")

    class _Client:
        def __init__(self, verify=True, timeout=None):
            assert verify is True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            assert "key=" not in url
            assert "secret-gemini-key" not in url
            assert (headers or {}).get("x-goog-api-key") == "secret-gemini-key"
            raise httpx.ConnectError(f"failed {url}")

    monkeypatch.setattr(httpx, "Client", _Client)
    try:
        https_transport({"requested": "gemini", "prompt": "hi", "timeout_sec": 5})
    except ConnectionError as exc:
        assert str(exc) == "connect_failed"
        assert "secret-gemini-key" not in str(exc)
        cause = exc.__cause__
        assert cause is None or "secret-gemini-key" not in str(cause)
    else:
        raise AssertionError("expected connect_failed")

    out = invoke_ai_provider(
        {"task": "assistant", "data_trust": build_data_trust_context("mock"), "prompt": "hi"}
    )
    assert out["status"] == "unavailable"
    assert out["live_llm"] is False
    assert "secret-gemini-key" not in str(out)
