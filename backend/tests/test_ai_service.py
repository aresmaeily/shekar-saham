import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_service import AIRequest, ai_service


class DummyMarketService:
    def __init__(self):
        self._data_trust = {
            "state": "mock",
            "trust_level": "synthetic",
            "source": "mock_fallback",
            "provider": "mock_fallback",
            "is_live": False,
            "is_generated": True,
            "warning": "MOCK data",
        }

    async def get_analysis(self, force=False):
        return None

    def status(self):
        return {"source": "mock_fallback", "trust_level": "synthetic", "symbol_count": 1, "flow_meta": {}, "confluence": {}}

    def data_trust_context(self):
        return self._data_trust

    def get_symbol(self, symbol):
        if symbol != "فملی":
            return None
        return {
            "snapshot": {"l18": "فملی", "pl": 1000, "plp": -1.5},
            "metrics": {"entry_score": 75, "exit_score": 20, "buy_power": 2.1},
            "tablocastic": {"grade": "A"},
            "data_trust": self._data_trust,
        }

    def run_user_filter(self, expr, limit=10):
        return {"ok": True, "count": 1, "rows": [{"symbol": "فملی", "entry_score": 75}], "data_trust": self._data_trust}


@pytest.mark.asyncio
async def test_ai_assistant_fallback_never_claims_live_for_mock():
    res = await ai_service.assistant(AIRequest(question="وضعیت بازار؟"), DummyMarketService())
    assert res["provider"] == "fallback"
    assert res["data_trust"]["state"] == "mock"
    assert any("زنده نیست" in x or "live" in x.lower() for x in res["risk_flags"] + res["warnings"])
    assert res["safety"]["no_auto_trading"] is True


@pytest.mark.asyncio
async def test_ai_analyst_symbol_context_with_persian_symbol():
    res = await ai_service.analyst(AIRequest(symbol="فملی"), DummyMarketService())
    assert res["task"] == "analyst"
    assert res["symbol_context"]["snapshot"]["l18"] == "فملی"
    assert res["evidence"]
    assert "تضمین" in res["uncertainty"][0]


@pytest.mark.asyncio
async def test_ai_optimizer_filter_and_backtest_suggestions():
    req = AIRequest(
        filter_expr="buy_power > 1.5",
        backtest_result={"metrics": {"profit_factor": 0.8, "maximum_drawdown": 20}},
    )
    res = await ai_service.optimizer(req, DummyMarketService())
    assert res["task"] == "optimizer"
    assert res["suggestions"]
    assert res["safety"]["no_repository_changes"] is True
    assert any(s["action"] in {"improve_exit", "reduce_position", "backtest"} for s in res["suggestions"])


def test_ai_api_smoke_assistant():
    c = TestClient(app)
    r = c.post("/api/ai/assistant", json={"question": "وضعیت بازار؟"})
    assert r.status_code == 200
    data = r.json()
    assert data["task"] == "assistant"
    assert data["provider"] == "fallback"
    assert "data_trust" in data


@pytest.mark.asyncio
async def test_ai_intelligence_consumes_filter_intelligence_context():
    res = await ai_service.intelligence(AIRequest(symbol="فملی", filter_expr="buy_power > 1.5"), DummyMarketService())
    assert any(e["category"] == "filter_intelligence" for e in res["evidence"])
    fi = next(e for e in res["evidence"] if e["category"] == "filter_intelligence")
    assert fi["value"]["classification"] == "INSUFFICIENT_DATA"
    assert "FILTER_INTELLIGENCE_INSUFFICIENT" in res["reason_codes"]
    assert res["safety"]["requires_human_approval"] is True


def test_ai_api_invalid_filter_is_controlled():
    c = TestClient(app)
    r = c.post("/api/ai/optimize", json={"filter_expr": "__import__('os')"})
    assert r.status_code == 200
    data = r.json()
    assert data["task"] == "optimizer"
    assert any("Filter validation failed" in w for w in data["warnings"])
