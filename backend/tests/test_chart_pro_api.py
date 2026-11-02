"""WS-10 CH-1/CH-2 acceptance battery — chart-pro backend API.

Covers:
- seeded_candles.candles_for determinism contract (same args -> byte-identical
  payload; bar N identical forever; overlapping windows agree on the shared
  tail regardless of end_bar_index).
- /api/v10/chartpro endpoints (universe / candles / indicators) shape, limit
  clamping, timeframe validation (422), and trust-badge discipline.

Synthetic/Paper ONLY: the series under test are deterministic seeded
generations, never live market data (conftest pins DATA_SOURCE=mock).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data.mock_market import SEED_SYMBOLS
from app.data.seeded_candles import TIMEFRAMES, candles_for
from app.main import app

# Honest non-live taxonomy: market_service.data_trust_context() unstubbed in
# the offline test env (no refresh ran) returns state="unavailable" and
# trust_level="mixed"; after a mock refresh it yields "mock"/"synthetic".
# "live" is unreachable through build_data_trust_context in this environment.
NON_LIVE_TRUST_STATES = {"synthetic", "mock", "stale", "unavailable", "mixed"}
NON_LIVE_TRUST_LEVELS = {"synthetic", "mixed"}

client = TestClient(app)


# ---------------------------------------------------------------------------
# CH-1: seeded candle generator
# ---------------------------------------------------------------------------

def test_timeframes_grid():
    assert TIMEFRAMES == {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1D": 86400}


def test_candles_determinism_same_args():
    a = candles_for("فملی", "1m", 100, end_bar_index=1_000_000)
    b = candles_for("فملی", "1m", 100, end_bar_index=1_000_000)
    assert a == b  # == on dicts -> byte-identical payloads


def test_candles_stability_overlap_tail():
    i = 4_242_424
    a = candles_for("فولاد", "1h", 600, end_bar_index=i)
    b = candles_for("فولاد", "1h", 600, end_bar_index=i + 500)
    # shared tail: bars [i-99..i] must be identical in both windows
    assert a[-100:] == b[:100]
    # bar i as the last bar of a short window equals bar i inside the long one
    c = candles_for("فولاد", "1h", 50, end_bar_index=i)
    assert c[-1] == a[-1]
    times = [candle["time"] for candle in a]
    assert times == sorted(times)  # oldest-first
    assert all(t % TIMEFRAMES["1h"] == 0 for t in times)  # absolute bar grid
    assert times[-1] == i * TIMEFRAMES["1h"]


def test_candles_shape_and_count_clamp():
    candles = candles_for("کگل", "15m", 5000, end_bar_index=10_000_000)
    assert len(candles) == 1000  # count clamped to the 1000 ceiling
    assert len(candles_for("کگل", "15m", 1, end_bar_index=10_000_000)) == 50  # 50 floor
    for candle in candles:
        assert set(candle) == {"time", "open", "high", "low", "close", "volume"}
        assert isinstance(candle["time"], int)
        assert isinstance(candle["volume"], int)
        assert candle["high"] >= max(candle["open"], candle["close"])
        assert candle["low"] <= min(candle["open"], candle["close"])
        assert candle["volume"] >= 1
        for field in ("open", "high", "low", "close"):
            assert round(candle[field], 2) == candle[field]  # 2-decimal rounding


def test_known_symbol_uses_seed_price_band():
    seed_price = {row[0]: row[5] for row in SEED_SYMBOLS}["فملی"]
    assert seed_price == 7800
    candles = candles_for("فملی", "1D", 300, end_bar_index=20_000)
    closes = [c["close"] for c in candles]
    # anchor wiggle (±3%) + close step (±1.2%) keep the series near the seed
    assert all(7_400 <= c <= 8_200 for c in closes)


def test_unknown_symbol_stable_pseudo_price():
    a = candles_for("ZZZ_UNKNOWN_X", "1m", 50, end_bar_index=777)
    b = candles_for("ZZZ_UNKNOWN_X", "1m", 50, end_bar_index=777)
    assert a == b  # stable pseudo-price, still deterministic
    assert all(900 <= c["close"] <= 2_000 for c in a)  # 1000..1900 base band
    with pytest.raises(ValueError):
        candles_for("فملی", "7m", 50, end_bar_index=1)  # invalid timeframe


# ---------------------------------------------------------------------------
# CH-2: /api/v10/chartpro endpoints
# ---------------------------------------------------------------------------

def test_universe_endpoint():
    r = client.get("/api/v10/chartpro/universe")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "synthetic-seeded"
    assert body["count"] == len(SEED_SYMBOLS) == len(body["symbols"])
    first = body["symbols"][0]
    assert set(first) == {"l18", "l30", "sector", "price", "change_pct"}
    assert isinstance(first["change_pct"], float)


def test_candles_endpoint_shape():
    r = client.get("/api/v10/chartpro/فملی", params={"timeframe": "15m", "limit": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "فملی"
    assert body["timeframe"] == "15m"
    assert body["source"] == "synthetic-seeded"
    assert body["note"] == "SYNTHETIC_OR_PAPER deterministic seeded series"
    assert body["count"] == len(body["ohlcv"]) == 100
    assert set(body["ohlcv"][0]) == {"time", "open", "high", "low", "close", "volume"}
    assert body["last_price"] == body["ohlcv"][-1]["close"]


def test_limit_clamp():
    r = client.get("/api/v10/chartpro/فملی", params={"limit": 5000})
    assert r.status_code == 200
    assert r.json()["count"] == 1000  # 5000 -> clamped to the 1000 ceiling
    r2 = client.get("/api/v10/chartpro/فملی", params={"limit": 10})
    assert r2.json()["count"] == 50  # clamped to the generator 50 floor


def test_invalid_timeframe_422():
    assert client.get("/api/v10/chartpro/فملی", params={"timeframe": "2h"}).status_code == 422
    assert client.get(
        "/api/v10/chartpro/فملی/indicators", params={"timeframe": "7m"}
    ).status_code == 422


def test_unknown_symbol_endpoint_ok():
    r = client.get("/api/v10/chartpro/ZZZ_UNKNOWN_X", params={"limit": 60})
    assert r.status_code == 200  # unknown symbols never 404 on synthetic charts
    assert r.json()["count"] == 60
    assert r.json()["source"] == "synthetic-seeded"


def test_indicators_endpoint():
    r = client.get("/api/v10/chartpro/وبملت/indicators", params={"timeframe": "1h", "limit": 300})
    assert r.status_code == 200
    body = r.json()
    ohlcv = body["ohlcv"]
    assert body["count"] == len(ohlcv) == 300
    ind = body["indicators"]
    assert set(ind) == {"ma20", "ma50", "ema20", "rsi14", "macd", "bollinger"}
    assert set(ind["macd"]) == {"macd", "signal", "hist"}
    assert set(ind["bollinger"]) == {"upper", "mid", "lower"}

    ohlcv_times = [c["time"] for c in ohlcv]
    overlay_keys = ("ma20", "ma50", "ema20", "rsi14")
    macd_keys = ("macd", "signal", "hist")
    boll_keys = ("upper", "mid", "lower")
    for group, keys in (
        (ind, overlay_keys),
        (ind["macd"], macd_keys),
        (ind["bollinger"], boll_keys),
    ):
        for key in keys:
            series = group[key]
            assert len(series) == len(ohlcv), key
            # aligned: every point sits on the ohlcv time grid (times subset)
            assert {p["time"] for p in series} <= set(ohlcv_times), key
            # tail window is full (all warm-up nulls live at the head only)
            assert all(p["value"] is not None for p in series[-30:]), key

    # warm-up heads null-padded for the rolling windows (lightweight-charts
    # skips nulls): calculate_ma skips i < period-1 -> exactly period-1 nulls
    assert sum(1 for p in ind["ma20"] if p["value"] is None) == 19
    assert sum(1 for p in ind["ma50"] if p["value"] is None) == 49
    assert sum(1 for p in ind["rsi14"] if p["value"] is None) == 14


def test_trust_badges_never_live():
    for path in (
        "/api/v10/chartpro/universe",
        "/api/v10/chartpro/فملی",
        "/api/v10/chartpro/فملی/indicators",
    ):
        body = client.get(path).json()
        # Trust fields must be the market_service verdict — never a hardcoded
        # "live" label. Unstubbed offline env: state="unavailable".
        assert body["data_trust"]["state"] in NON_LIVE_TRUST_STATES
        assert body["data_trust"]["is_live"] is False
        assert body["data_trust"]["live_verified"] is False
        assert body["trust_level"] in NON_LIVE_TRUST_LEVELS
