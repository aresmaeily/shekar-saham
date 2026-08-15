import pytest
from fastapi.testclient import TestClient

from app.core.config import build_data_trust_context
from app.domain.ai_intelligence import AIIntelligenceCore
from app.main import app
from app.services.ai_service import AIRequest, ai_service


def _symbol_context(entry=80, exit_score=10, buy_power=2.0, volume_ratio=2.5, value_score=75):
    return {
        "snapshot": {"l18": "فملی", "pl": 1000, "plp": 1.2},
        "metrics": {
            "entry_score": entry,
            "exit_score": exit_score,
            "buy_power": buy_power,
            "volume_ratio": volume_ratio,
            "individual_net_value": 5_000_000_000,
        },
        "tablocastic": {"golden_number": 70, "grade": "A"},
        "fundamental": {"value_score": value_score, "fund_score": value_score, "is_synthetic": False},
    }


def test_live_aligned_evidence_can_be_buy_candidate():
    core = AIIntelligenceCore()
    result = core.evaluate(
        symbol_context=_symbol_context(),
        market_context={"confluence": {"buy_alerts": 5, "sell_alerts": 0}},
        filter_context={"sample": {"count": 3}},
        backtest_context={"metrics": {"profit_factor": 1.4, "maximum_drawdown": 8}},
        data_trust={
            "state": "live",
            "is_live": True,
            "live_verified": True,
            "trust_level": "live",
            "source": "tsetmc",
            "checked_at": 1010,
            "timestamp": 1000,
        },
    )
    assert result.recommendation == "BUY_CANDIDATE"
    assert result.confidence > 0.55
    assert result.data_trust["state"] == "live"
    assert result.data_trust["live_verified"] is True
    assert result.evidence
    assert result.safety["no_autonomous_trading"] is True


def test_unverified_tsetmc_label_blocks_actionable_recommendation():
    core = AIIntelligenceCore()
    result = core.evaluate(
        symbol_context=_symbol_context(),
        market_context={"confluence": {"buy_alerts": 5, "sell_alerts": 0}},
        filter_context={"sample": {"count": 3}},
        backtest_context={"metrics": {"profit_factor": 1.4, "maximum_drawdown": 8}},
        data_trust=build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010),
    )
    assert result.data_trust["state"] == "live"
    assert result.data_trust["live_verified"] is False
    assert result.data_trust["is_live"] is False
    assert result.recommendation == "INSUFFICIENT_DATA"


def test_mock_data_blocks_actionable_live_recommendation():
    core = AIIntelligenceCore()
    result = core.evaluate(
        symbol_context=_symbol_context(),
        data_trust=build_data_trust_context("mock"),
    )
    assert result.recommendation == "INSUFFICIENT_DATA"
    assert result.confidence <= 0.35
    assert any("Non-live" in x for x in result.invalidations)


def test_conflicting_evidence_reduces_to_watch_or_no_action():
    core = AIIntelligenceCore()
    result = core.evaluate(
        symbol_context=_symbol_context(entry=85, exit_score=5, buy_power=0.4, volume_ratio=0.6, value_score=20),
        filter_context={"sample": {"count": 2}},
        backtest_context={"metrics": {"profit_factor": 0.7, "maximum_drawdown": 25}},
        data_trust={
            "state": "live",
            "is_live": True,
            "live_verified": True,
            "trust_level": "live",
            "source": "tsetmc",
        },
    )
    assert result.recommendation in {"WATCH", "NO_ACTION"}
    assert result.conflicts
    assert "EVIDENCE_CONFLICT" in result.reason_codes


def test_unavailable_data_returns_insufficient_data():
    core = AIIntelligenceCore()
    result = core.evaluate(symbol_context=_symbol_context(), data_trust=build_data_trust_context("none"))
    assert result.data_trust["state"] == "unavailable"
    assert result.recommendation == "INSUFFICIENT_DATA"
    assert result.confidence <= 0.15


def test_filter_intelligence_context_is_consumed_by_ai_brain():
    core = AIIntelligenceCore()
    result = core.evaluate(
        symbol_context=_symbol_context(),
        filter_context={"filter_intelligence": {"classification": "DEGRADING", "decay": {"status": "PERFORMANCE_DECAY"}}},
        data_trust={
            "state": "live",
            "is_live": True,
            "live_verified": True,
            "trust_level": "live",
            "source": "tsetmc",
        },
    )
    assert any(e.category == "filter_intelligence" for e in result.evidence)
    assert "FILTER_INTELLIGENCE_RISK" in result.reason_codes
    assert result.safety["requires_human_approval"] is True


class DummyMarketService:
    async def get_analysis(self, force=False):
        return None

    def status(self):
        return {"source": "mock", "trust_level": "synthetic", "symbol_count": 1, "flow_meta": {}, "confluence": {}}

    def data_trust_context(self):
        return build_data_trust_context("mock")

    def get_symbol(self, symbol):
        return _symbol_context()

    def run_user_filter(self, expr, limit=10):
        return {"ok": True, "count": 1, "rows": [{"symbol": "فملی"}], "data_trust": build_data_trust_context("mock")}


@pytest.mark.asyncio
async def test_ai_service_intelligence_uses_context_and_trust_gate():
    result = await ai_service.intelligence(AIRequest(symbol="فملی", filter_expr="buy_power > 1"), DummyMarketService())
    assert result["symbol"] == "فملی"
    assert result["recommendation"] == "INSUFFICIENT_DATA"
    assert result["data_trust"]["state"] == "mock"
    assert result["provider"] == "fallback"


def test_ai_intelligence_api_smoke():
    c = TestClient(app)
    r = c.post("/api/ai/intelligence/فملی", json={"filter_expr": "buy_power > 1"})
    assert r.status_code == 200
    data = r.json()
    assert "recommendation" in data
    assert "evidence" in data
    assert "data_trust" in data
    assert data["safety"]["no_autonomous_trading"] is True
