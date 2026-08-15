import pytest
from fastapi.testclient import TestClient

from app.core.config import build_data_trust_context
from app.domain.market_intelligence import MarketIntelligenceSnapshot
from app.main import app
from app.services.market_intelligence_service import MarketIntelligenceService


class Overview:
    def model_dump(self, mode="json"):
        return {
            "symbol_count": 3,
            "positive_count": 2,
            "negative_count": 1,
            "total_value": 10_000_000_000,
        }


class Row:
    def __init__(self, data):
        self.data = data
    def model_dump(self, mode="json"):
        return self.data


class Analysis:
    overview = Overview()
    entry_signals = [
        Row({"symbol": "فملی", "name": "ملی مس", "industry": "فلزات", "pl": 1000, "plp": 1.2, "entry_score": 80, "exit_score": 5, "buy_power": 2.4, "volume_ratio": 3.0, "individual_net_value": 5_000_000_000, "value_score": 75, "golden_number": 70}),
        Row({"symbol": "فولاد", "name": "فولاد", "industry": "فلزات", "pl": 900, "plp": -0.5, "entry_score": 40, "exit_score": 10, "buy_power": 0.8, "volume_ratio": 1.0, "individual_net_value": -1_000_000, "value_score": 60}),
    ]
    watchlist = [Row({"symbol": "خودرو", "name": "خودرو", "industry": "خودرو", "entry_score": 55, "buy_power": 1.4, "volume_ratio": 1.8, "individual_net_value": 1_000_000})]
    industries = [
        Row({"industry": "فلزات", "symbol_count": 2, "avg_plp": 0.5, "net_individual_value": 4_000_000_000, "avg_buy_power": 1.6, "score": 72}),
        Row({"industry": "خودرو", "symbol_count": 1, "avg_plp": -1.0, "net_individual_value": -500_000_000, "avg_buy_power": 0.8, "score": 35}),
    ]


class DummyMarketService:
    _last_symbols = []
    async def get_analysis(self, force=False):
        return Analysis()
    def data_trust_context(self):
        return build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010)
    def get_confluence(self):
        return {"summary": {"buy_alerts": 2, "sell_alerts": 0}}


@pytest.mark.asyncio
async def test_market_monitoring_cycle_builds_snapshot_and_rankings():
    service = MarketIntelligenceService()
    result = await service.run_market_monitoring_cycle(DummyMarketService(), persist=False)
    assert isinstance(result.snapshot, MarketIntelligenceSnapshot)
    assert result.snapshot.market_regime == "BULLISH"
    assert result.industries[0].industry == "فلزات"
    assert result.opportunities
    assert result.opportunities[0].rank == 1
    assert result.snapshot.data_trust["state"] == "live"


@pytest.mark.asyncio
async def test_market_monitoring_first_snapshot_creates_events_when_persist_false_not_required():
    service = MarketIntelligenceService()
    result = await service.run_market_monitoring_cycle(DummyMarketService(), persist=False)
    assert result.events
    assert result.events[0].event_type == "OPPORTUNITY_APPEARED"
    assert result.events[0].data_trust["state"] == "live"


@pytest.mark.asyncio
async def test_market_monitoring_non_live_trust_caps_opportunity_confidence():
    class MockSvc(DummyMarketService):
        def data_trust_context(self):
            return build_data_trust_context("mock")
    service = MarketIntelligenceService()
    result = await service.run_market_monitoring_cycle(MockSvc(), persist=False)
    assert result.snapshot.data_trust["state"] == "mock"
    assert all(o.data_trust["is_live"] is False for o in result.opportunities)
    assert all(o.recommendation == "INSUFFICIENT_DATA" for o in result.opportunities)


def test_market_intelligence_api_smoke():
    c = TestClient(app)
    r = c.get("/api/ai/market-intelligence?limit=5&persist=false")
    assert r.status_code == 200
    data = r.json()
    assert "snapshot" in data
    assert "opportunities" in data
    assert "industries" in data
    assert "data_trust" in data["snapshot"]


def test_market_intelligence_related_api_endpoints():
    c = TestClient(app)
    for path in ["/api/ai/market-regime", "/api/ai/opportunities", "/api/ai/industries", "/api/ai/events"]:
        r = c.get(path)
        assert r.status_code == 200, path
        assert r.json().get("ok") is True


@pytest.mark.asyncio
async def test_market_intelligence_uses_iran_session_status(monkeypatch):
    from app.models.schemas import MarketSession

    monkeypatch.setattr(
        "app.services.market_intelligence_service.infer_iran_market_session",
        lambda now=None: MarketSession(
            timezone="Asia/Tehran",
            session_date="2026-08-15",
            is_open=True,
            status="open",
        ),
    )
    service = MarketIntelligenceService()
    result = await service.run_market_monitoring_cycle(DummyMarketService(), persist=False)
    assert result.snapshot.market_status == "open"
    assert result.snapshot.market_status != "open_unknown"
    assert any(e.get("name") == "market_session" for e in result.snapshot.evidence)


@pytest.mark.asyncio
async def test_market_intelligence_session_closed_is_not_unknown(monkeypatch):
    from app.models.schemas import MarketSession

    monkeypatch.setattr(
        "app.services.market_intelligence_service.infer_iran_market_session",
        lambda now=None: MarketSession(
            timezone="Asia/Tehran",
            session_date="2026-08-14",
            is_open=False,
            status="closed",
        ),
    )
    service = MarketIntelligenceService()
    result = await service.run_market_monitoring_cycle(DummyMarketService(), persist=False)
    assert result.snapshot.market_status == "closed"
    assert result.snapshot.market_status != "open_unknown"


@pytest.mark.asyncio
async def test_session_open_does_not_mark_market_intelligence_live(monkeypatch):
    from app.models.schemas import MarketSession

    monkeypatch.setattr(
        "app.services.market_intelligence_service.infer_iran_market_session",
        lambda now=None: MarketSession(
            timezone="Asia/Tehran",
            session_date="2026-08-15",
            is_open=True,
            status="open",
        ),
    )

    class MockSvc(DummyMarketService):
        def data_trust_context(self):
            return build_data_trust_context("mock")

    service = MarketIntelligenceService()
    result = await service.run_market_monitoring_cycle(MockSvc(), persist=False)
    assert result.snapshot.market_status == "open"
    assert result.snapshot.data_trust["state"] == "mock"
    assert result.snapshot.data_trust["is_live"] is False
    assert any("Session-open" in w for w in result.snapshot.warnings)
    assert all(o.data_trust["is_live"] is False for o in result.opportunities)
    assert all(o.recommendation == "INSUFFICIENT_DATA" for o in result.opportunities)
