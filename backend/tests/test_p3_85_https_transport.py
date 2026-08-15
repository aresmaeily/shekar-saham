"""P3.85 HTTPS transport — mocked network only. Not a live LLM claim."""

from __future__ import annotations

import httpx

from app.core.config import build_data_trust_context
from app.domain import ai_provider
from app.domain.ai_provider import invoke_ai_provider


def _req(**extra):
    payload = {"task": "analyst", "data_trust": build_data_trust_context("mock"), "prompt": "ping"}
    payload.update(extra)
    return payload


class _FakeResp:
    def __init__(self, status_code=200, payload=None, json_error=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("bad json")
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


def test_https_not_called_without_execute(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "secret-should-not-leak")
    monkeypatch.delenv("AI_EXECUTE", raising=False)
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("HTTP must not run")

    monkeypatch.setattr(ai_provider, "https_transport", boom)
    out = invoke_ai_provider(_req())
    assert out["status"] == "not_executed"
    assert out["error_code"] == "execution_not_enabled"
    assert called["n"] == 0
    assert "secret-should-not-leak" not in str(out)


def test_https_success_is_not_market_live(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "secret-should-not-leak")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_MODEL", "gpt-4o-mini")

    def handler(url, headers, json):
        assert url.startswith("https://")
        assert "secret-should-not-leak" in (headers.get("Authorization") or "")
        return _FakeResp(200, {"choices": [{"message": {"content": "hello from mock http"}}]})

    _patch_client(monkeypatch, handler)
    out = invoke_ai_provider(_req())
    assert out["status"] == "executed"
    assert out["ok"] is True
    assert out["live_llm"] is False
    assert out["test_only"] is False
    assert "hello" in out["text"]
    assert "secret-should-not-leak" not in str(out)
    assert "Authorization" not in str(out)


def test_https_timeout(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("AI_EXECUTE", "1")

    def handler(url, headers, json):
        raise httpx.TimeoutException("slow")

    _patch_client(monkeypatch, handler)
    out = invoke_ai_provider(_req())
    assert out["status"] == "timeout"
    assert out["live_llm"] is False


def test_https_http_error_no_retry_on_401(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_RETRY_MAX", "3")
    calls = {"n": 0}

    def handler(url, headers, json):
        calls["n"] += 1
        return _FakeResp(401, {"error": "nope"})

    _patch_client(monkeypatch, handler)
    out = invoke_ai_provider(_req())
    assert out["status"] == "http_error"
    assert calls["n"] == 1


def test_https_retry_then_success(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_RETRY_MAX", "2")
    calls = {"n": 0}

    def handler(url, headers, json):
        calls["n"] += 1
        if calls["n"] < 2:
            return _FakeResp(503, {"error": "busy"})
        return _FakeResp(200, {"choices": [{"message": {"content": "ok after retry"}}]})

    _patch_client(monkeypatch, handler)
    out = invoke_ai_provider(_req())
    assert out["status"] == "executed"
    assert calls["n"] == 2
    assert out["attempts"] == 2
    assert out["live_llm"] is False


def test_https_malformed(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("AI_EXECUTE", "1")

    def handler(url, headers, json):
        return _FakeResp(200, {"foo": "bar"})

    _patch_client(monkeypatch, handler)
    out = invoke_ai_provider(_req())
    assert out["status"] == "malformed"


def test_non_https_base_url_blocked(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_BASE_URL", "http://insecure.example/v1")
    out = invoke_ai_provider(_req())
    assert out["status"] == "blocked"
    assert out["error_code"] == "https_endpoint_required"


def test_connect_failure(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("AI_EXECUTE", "1")

    def handler(url, headers, json):
        raise httpx.ConnectError("down")

    _patch_client(monkeypatch, handler)
    out = invoke_ai_provider(_req())
    assert out["status"] == "unavailable"


def test_https_transport_requires_verify():
    # construction assertion lives in _patch_client; this checks helper mapping
    built = ai_provider._build_provider_http("openai", "abc", "hi")
    assert built is not None
    url, headers, body = built
    assert url.startswith("https://")
    assert "abc" in headers["Authorization"]
    assert body["messages"][0]["content"] == "hi"
