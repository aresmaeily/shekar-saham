"""P3.88 residual classification. Locks proven non-impact. Not a live LLM claim."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import build_data_trust_context, is_verified_live
from app.domain.ai_provider import _build_provider_http, invoke_ai_provider
from app.main import app
from app.services.ai_service import AIRequest, ai_service, build_controlled_provider_prompt
from tests.test_p3_81_ai_contracts import DummyMarket

REPO = Path(__file__).resolve().parents[2]


def test_frontend_and_electron_do_not_consume_runtime_labels():
    needles = ("external_runtime", "provider_status", "provider-status", "live_llm", "external_not_configured")
    hits = []
    for folder in (REPO / "frontend", REPO / "electron"):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.suffix not in {".js", ".html"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in needles:
                if needle in text:
                    hits.append(f"{path}:{needle}")
    assert hits == []


def test_gemini_url_key_is_not_returned_by_invoke(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_API_KEY", "secret-gemini-key")
    monkeypatch.setenv("AI_EXECUTE", "1")
    monkeypatch.setenv("AI_MODEL", "gemini-1.5-flash")
    built = _build_provider_http("gemini", "secret-gemini-key", "hi")
    assert built is not None
    assert "secret-gemini-key" not in built[0]
    assert "key=" not in built[0]
    assert built[1].get("x-goog-api-key") == "secret-gemini-key"

    class _Client:
        def __init__(self, verify=True, timeout=None):
            assert verify is True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            raise httpx.ConnectError(f"failed {url}")

    monkeypatch.setattr(httpx, "Client", _Client)
    out = invoke_ai_provider(
        {"task": "assistant", "data_trust": build_data_trust_context("mock"), "prompt": "hi"}
    )
    blob = str(out)
    assert out["status"] == "unavailable"
    assert out["live_llm"] is False
    assert "secret-gemini-key" not in blob
    assert "generativelanguage" not in blob


def test_capability_prompt_never_degrades_to_ping():
    for task in ("assistant", "analyst", "research", "strategy", "risk", None):
        payload = {"data_trust": {"state": "mock"}}
        if task:
            payload["task"] = task
        prompt = build_controlled_provider_prompt(payload, question="q")
        assert prompt.strip()
        assert prompt.strip() != "ping"
        assert "live_verified: false" in prompt


@pytest.mark.asyncio
async def test_capability_response_does_not_branch_away_from_fallback_labels():
    res = await ai_service.assistant(AIRequest(symbol="فملی"), DummyMarket())
    assert res["external_runtime"] == "NOT_EXECUTED"
    assert res["live_llm"] is False
    assert res["provider_text_used"] is False
    assert res["fallback_answer"] == res["answer"]
    assert is_verified_live(res["data_trust"]) is False


def test_provider_status_probe_is_not_an_execution_claim():
    client = TestClient(app)
    res = client.get("/api/ai/provider-status")
    assert res.status_code == 200
    body = res.json()
    assert body["live_llm"] is False
    assert body["external_runtime"] == "NOT_EXECUTED"
    assert body["invocation_ready"] is False
    assert body["accepts_client_secrets"] is False
