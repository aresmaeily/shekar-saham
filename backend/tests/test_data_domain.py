from datetime import datetime, timezone

from app.core.config import build_data_trust_context, classify_data_trust_state, resolve_trust_level
from app.engines.data_quality import quality_scorer
from app.models.schemas import DataTrustState, IranInstrument, OHLCVBar, SymbolSnapshot


def test_data_trust_state_classification():
    assert classify_data_trust_state("tsetmc") == "live"
    assert classify_data_trust_state("brsapi") == "live"
    assert classify_data_trust_state("mock_fallback") == "mock"
    assert classify_data_trust_state("synthetic_bootstrap") == "synthetic"
    assert classify_data_trust_state("cache") == "mixed"


def test_legacy_trust_level_compatibility():
    assert resolve_trust_level("tsetmc") == "live"
    assert resolve_trust_level("mock") == "synthetic"
    assert resolve_trust_level("synthetic_bootstrap") == "synthetic"
    assert resolve_trust_level("cache") == "mixed"


def test_data_trust_context_never_marks_mock_live():
    ctx = build_data_trust_context("mock_fallback", timestamp=123.0)
    assert ctx["state"] == "mock"
    assert ctx["trust_level"] == "synthetic"
    assert ctx["is_live"] is False
    assert ctx["is_generated"] is True
    assert "MOCK" in ctx["warning"]


def test_iran_instrument_from_snapshot_preserves_farsi_and_ids():
    snap = SymbolSnapshot(
        l18="فملی",
        l30="ملی صنایع مس ایران",
        isin="IRO1MSMI0001",
        id="123456",
        cs="فلزات اساسی",
        cs_id="01",
        source="tsetmc",
        updated_at=datetime.now(timezone.utc),
    )
    instrument = IranInstrument.from_snapshot(snap)
    assert instrument.symbol == "فملی"
    assert instrument.industry == "فلزات اساسی"
    assert instrument.market == "TSE"
    assert instrument.source == "tsetmc"


def test_ohlcv_bar_contract_accepts_iran_market_candle():
    bar = OHLCVBar(time=1786111749, open=1000, high=1050, low=990, close=1020, volume=1_000_000)
    assert bar.close == 1020
    assert bar.trust_state == DataTrustState.MIXED


def test_data_quality_uses_snapshot_source_for_mock():
    snap = SymbolSnapshot(
        l18="فملی",
        pl=1000,
        pc=995,
        py=990,
        tvol=1_000_000,
        Buy_I_Volume=500_000,
        Sell_I_Volume=300_000,
        source="mock",
        updated_at=datetime.now(timezone.utc),
    )
    score = quality_scorer.score_symbol(snap)
    assert score["trust_state"] == "mock"
    assert score["trust"] == "synthetic"
    assert any("MOCK" in issue for issue in score["issues"])
