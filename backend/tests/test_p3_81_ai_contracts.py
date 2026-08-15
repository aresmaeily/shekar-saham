"""P3.81 AI provider adapter and remaining intelligence contracts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import build_data_trust_context, is_verified_live
from app.domain.ai_provider import client_secret_fields_present, resolve_ai_provider
from app.main import app
from app.services.ai_service import AIRequest, ai_service


class DummyMarket:
    def __init__(self, trust: dict | None = None):
        self._data_trust = trust or build_data_trust_context("mock")

    async def get_analysis(self, force=False):
        return None

    def status(self):
        return {
            "source": self._data_trust.get("source"),
            "trust_level": self._data_trust.get("trust_level"),
            "symbol_count": 1,
            "flow_meta": {},
            "confluence": {},
        }

    def data_trust_context(self):
        return self._data_trust

    def get_symbol(self, symbol):
        if symbol != "فملی":
            return None
        return {
            "snapshot": {"l18": "فملی", "pl": 1000, "plp": -1.2},
            "metrics": {"entry_score": 70, "exit_score": 25, "buy_power": 1.8},
            "tablocastic": {"grade": "B"},
            "data_trust": self._data_trust,
        }

    def run_user_filter(self, expr, limit=10):
        return {"ok": True, "count": 1, "rows": [{"symbol": "فملی"}], "data_trust": self._data_trust}


def test_provider_default_is_fallback_not_live_llm():
    info = resolve_ai_provider()
    assert info["mode"] in {"fallback", "external_not_configured"}
    assert info["live_llm"] is False
    assert info["external_runtime"] == "NOT_EXECUTED"
    assert info["accepts_client_secrets"] is False


def test_client_secret_fields_are_detected():
    assert client_secret_fields_present({"api_key": "x"}) == ["api_key"]
    assert client_secret_fields_present({"openai_api_key": "sk"}) == ["openai_api_key"]
    assert client_secret_fields_present({"symbol": "فملی", "question": "hi"}) == []


def test_api_rejects_client_supplied_llm_key():
    client = TestClient(app)
    res = client.post("/api/ai/assistant", json={"question": "hi", "api_key": "should-not-work"})
    assert res.status_code in {400, 422}


@pytest.mark.asyncio
async def test_research_never_claims_external_or_live():
    res = await ai_service.research(AIRequest(symbol="فملی"), DummyMarket())
    assert res["task"] == "research"
    assert res["provider"] == "fallback"
    assert res["live_llm"] is False
    assert res["external_runtime"] == "NOT_EXECUTED"
    assert is_verified_live(res["data_trust"]) is False
    assert res["confidence"] <= 0.30
    joined = " ".join(res.get("warnings") or []) + " ".join(res.get("key_observations") or [])
    assert "خارجی" in joined or "LLM" in joined


@pytest.mark.asyncio
async def test_strategy_does_not_auto_apply():
    res = await ai_service.strategy(
        AIRequest(filter_expr="buy_power > 1.5", backtest_result={"metrics": {"profit_factor": 0.9, "maximum_drawdown": 18}}),
        DummyMarket(),
    )
    assert res["task"] == "strategy"
    assert res["safety"]["no_repository_changes"] is True
    assert "خودکار" in res["answer"] or "خودکار" in res["summary"]
    assert is_verified_live(res["data_trust"]) is False


@pytest.mark.asyncio
async def test_risk_includes_trust_and_is_educational():
    res = await ai_service.risk(AIRequest(symbol="فملی"), DummyMarket())
    assert res["task"] == "risk"
    assert res["data_trust"]
    assert is_verified_live(res["data_trust"]) is False
    assert res["safety"]["no_auto_trading"] is True
    assert res["confidence"] <= 0.40


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,max_conf",
    [
        ("mock", 0.35),
        ("synthetic", 0.35),
        ("none", 0.30),
    ],
)
async def test_ai_tasks_respect_non_live_trust(source, max_conf):
    market = DummyMarket(build_data_trust_context(source))
    for method in (ai_service.assistant, ai_service.analyst, ai_service.research, ai_service.risk):
        res = await method(AIRequest(symbol="فملی"), market)
        assert is_verified_live(res["data_trust"]) is False
        assert res["confidence"] <= max_conf + 0.10
        assert res.get("live_llm") is False


@pytest.mark.asyncio
async def test_stale_caps_confidence():
    import time

    now = time.time()
    trust = build_data_trust_context("tsetmc", timestamp=now - 10_000, checked_at=now, stale_after_sec=300)
    res = await ai_service.analyst(AIRequest(symbol="فملی"), DummyMarket(trust))
    assert res["data_trust"]["state"] == "stale"
    assert res["confidence"] <= 0.35
    assert is_verified_live(res["data_trust"]) is False


def test_provider_status_has_no_secret_values():
    client = TestClient(app)
    res = client.get("/api/ai/provider-status")
    assert res.status_code == 200
    body = res.json()
    blob = str(body).lower()
    assert "sk-" not in blob
    assert body["live_llm"] is False
    assert body["external_runtime"] == "NOT_EXECUTED"
    assert body["accepts_client_secrets"] is False


def test_new_ai_endpoints_smoke_and_trust():
    client = TestClient(app)
    for path in ("/api/ai/research", "/api/ai/strategy", "/api/ai/risk"):
        res = client.post(path, json={"symbol": "فملی"})
        assert res.status_code == 200, path
        data = res.json()
        assert "data_trust" in data
        assert is_verified_live(data["data_trust"]) is False
        assert data.get("live_llm") is False
        assert "confidence" in data
        assert "warnings" in data
        assert "source" in data


def test_v07_ai_explain_carries_data_trust():
    client = TestClient(app)
    client.get("/api/analyze")
    res = client.get("/api/v07/ai-explain/فملی")
    assert res.status_code == 200
    body = res.json()
    assert body.get("provider") == "fallback"
    assert is_verified_live(body.get("data_trust") or {}) is False
    assert body.get("live_llm") is False
    assert body.get("verified_live") is False


def test_unverified_constructed_live_object_is_not_used_by_provider():
    info = resolve_ai_provider()
    assert info["live_llm"] is False
    minted = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010, live_verified=True)
    assert minted["live_verified"] is False
    assert is_verified_live(minted) is False
