import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.config import build_data_trust_context, classify_data_trust_state, resolve_trust_level
from app.main import app


def test_all_data_trust_states_and_legacy_mapping():
    cases = {
        "tsetmc": ("live", "live"),
        "cache": ("mixed", "mixed"),
        "mock_fallback": ("mock", "synthetic"),
        "synthetic_bootstrap": ("synthetic", "synthetic"),
        "unavailable": ("unavailable", "mixed"),
    }
    for source, (state, legacy) in cases.items():
        assert classify_data_trust_state(source) == state
        assert resolve_trust_level(source) == legacy


def test_fresh_live_context_not_stale():
    now = time.time()
    ctx = build_data_trust_context("tsetmc", timestamp=now - 10, checked_at=now, stale_after_sec=300)
    assert ctx["state"] == "live"
    assert ctx["stale"] is False
    assert ctx["age_sec"] >= 10
    # Source label + freshness is not independent verification.
    assert ctx["live_verified"] is False
    assert ctx["is_live"] is False
    assert ctx["trust_level"] == "mixed"


def test_stale_live_context_maps_to_mixed_legacy():
    now = time.time()
    ctx = build_data_trust_context("tsetmc", timestamp=now - 1000, checked_at=now, stale_after_sec=300)
    assert ctx["state"] == "stale"
    assert ctx["trust_level"] == "mixed"
    assert ctx["stale"] is True
    assert ctx["is_live"] is False
    assert "STALE" in ctx["warning"]


def test_missing_timestamp_unavailable_without_fallback():
    ctx = build_data_trust_context("none", timestamp=None, checked_at=1000, stale_after_sec=300)
    assert ctx["state"] == "unavailable"
    assert ctx["trust_level"] == "mixed"
    assert ctx["timestamp"] is None
    assert ctx["age_sec"] is None
    assert ctx["is_live"] is False


def test_invalid_timestamp_does_not_create_fake_live():
    ctx = build_data_trust_context("tsetmc", timestamp="not-a-timestamp", checked_at=1000, stale_after_sec=300)
    assert ctx["timestamp"] is None
    assert ctx["age_sec"] is None
    assert ctx["state"] == "mixed"
    assert ctx["is_live"] is False
    assert ctx["checked_at"] == 1000


def test_mock_fallback_metadata_is_not_live():
    ctx = build_data_trust_context(
        "mock_fallback",
        timestamp=1000,
        checked_at=1010,
        fallback_source="mock",
        error_code="brsapi: no API key configured",
    )
    assert ctx["state"] == "mock"
    assert ctx["trust_level"] == "synthetic"
    assert ctx["is_live"] is False
    assert ctx["is_generated"] is True
    assert ctx["fallback_source"] == "mock"
    assert "API key" in ctx["warning"]


def test_api_propagates_data_trust_and_no_false_live():
    c = TestClient(app)
    r = c.get("/api/analyze")
    assert r.status_code == 200
    data = r.json()
    ctx = data["data_trust"]
    assert "state" in ctx
    assert "checked_at" in ctx
    assert "stale_after_sec" in ctx
    assert ctx.get("live_verified") is not True
    assert ctx["is_live"] is False
    if ctx["state"] in {"mock", "synthetic", "stale", "unavailable"}:
        assert ctx["is_live"] is False


def test_fundamental_output_labels_synthetic():
    c = TestClient(app)
    c.get("/api/analyze")
    r = c.get("/api/fundamental/فملی/deep")
    assert r.status_code == 200
    data = r.json()
    assert data["fundamental_source"] == "synthetic"
    assert data["is_synthetic"] is True
    assert data["data_trust"]["state"] != "live"


def test_ai_stale_and_unavailable_warnings():
    from app.services.ai_service import AIRequest, ai_service

    class Dummy:
        def __init__(self, ctx):
            self.ctx = ctx
        async def get_analysis(self, force=False):
            return None
        def status(self):
            return {"source": self.ctx["source"], "trust_level": self.ctx["trust_level"], "symbol_count": 0}
        def data_trust_context(self):
            return self.ctx
        def get_symbol(self, symbol):
            return {}

    import asyncio
    stale = build_data_trust_context("tsetmc", timestamp=1, checked_at=1000, stale_after_sec=300)
    unavailable = build_data_trust_context("none", checked_at=1000)
    stale_res = asyncio.run(ai_service.assistant(AIRequest(question="?"), Dummy(stale)))
    unavailable_res = asyncio.run(ai_service.assistant(AIRequest(question="?"), Dummy(unavailable)))
    assert stale_res["data_trust"]["state"] == "stale"
    assert unavailable_res["data_trust"]["state"] == "unavailable"
    assert stale_res["confidence"] < 0.35
    assert unavailable_res["confidence"] < 0.35
    assert stale_res["warnings"]
    assert unavailable_res["warnings"]


def test_backtest_stale_and_unavailable_warnings():
    from app.engines.backtest import run_filter_strategy_backtest

    paths = {"فملی": [{"ts": 1, "symbol": "فملی", "pl": 100, "entry_score": 80}, {"ts": 2, "symbol": "فملی", "pl": 101}]}
    stale = build_data_trust_context("tsetmc", timestamp=1, checked_at=1000, stale_after_sec=300)
    unavailable = build_data_trust_context("none", checked_at=1000)
    r1 = run_filter_strategy_backtest(paths, "entry_score > 1", data_trust=stale)
    r2 = run_filter_strategy_backtest(paths, "entry_score > 1", data_trust=unavailable)
    assert r1["data_trust"]["state"] == "stale"
    assert r2["data_trust"]["state"] == "unavailable"
    assert r1["warnings"]
    assert r2["warnings"]


def test_future_timestamp_is_not_live():
    ctx = build_data_trust_context("tsetmc", timestamp=2000, checked_at=1000, stale_after_sec=300)
    assert ctx["state"] == "mixed"
    assert ctx["trust_level"] == "mixed"
    assert ctx["is_live"] is False
    assert ctx["future_timestamp"] is True
    assert "future" in ctx["warning"].lower()


def test_brsapi_missing_key_fallback_metadata_does_not_expose_secret(monkeypatch):
    import asyncio
    from app.core.config import get_settings
    from app.data.providers import MarketDataProvider

    monkeypatch.delenv("BRSAPI_KEY", raising=False)
    monkeypatch.setenv("DATA_SOURCE", "brsapi")
    get_settings.cache_clear()

    async def run():
        provider = MarketDataProvider()
        rows = await provider.fetch()
        return provider, rows

    provider, rows = asyncio.run(run())
    ctx = build_data_trust_context(
        provider.last_source,
        timestamp=rows[0].updated_at.timestamp() if rows and rows[0].updated_at else None,
        provider=provider.last_source,
        fallback_source="mock" if "mock" in provider.last_source else "",
        error_code=provider.last_error,
    )
    assert provider.last_error == "brsapi: no API key configured"
    assert ctx["state"] == "mock"
    assert ctx["trust_level"] == "synthetic"
    assert ctx["is_live"] is False
    assert "no API key configured" in ctx["warning"]
    assert "BRSAPI_KEY" not in ctx["warning"]
