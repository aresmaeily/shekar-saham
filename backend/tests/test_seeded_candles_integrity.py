"""WDA-2 — OHLCV integrity + semantics battery for the seeded candle generator.

Complements tests/test_chart_pro_api.py (which pins the determinism
fingerprints and endpoint shape — deliberately not repeated here): this file
pins the *integrity and semantics of the bars themselves* — OHLC invariants,
ordering, index/time continuity, boundary timestamps, clamp behavior,
perturbation sensitivity, and the explicit price-semantics tag.

Pinned contract (read off app/data/seeded_candles.py):
- n = max(50, min(1000, int(count))): out-of-range lengths are CLAMPED, never
  refused; n governs the window: start = end_bar_index - n + 1.
- Bar i carries time = i * tf_sec on a CONTINUOUS arithmetic grid — no
  market-closed buckets are skipped (synthetic series; even 1D weekends sit
  exactly 86400s apart).
- Bar values are pure functions of (symbol, timeframe, bar_index); the wall
  clock is consulted ONLY to resolve a None end_bar_index, so every call here
  passes an explicit end_bar_index and stays frozen offline (no wall clock,
  no network).
- Volume floor is 1 (max(1, int(base * (1 + inc4 * 0.6)))); prices are floats
  rounded to 2 decimals, strictly positive by construction (all step/wiggle
  factors stay within (0.988, 1.03) of a positive base).
"""
from __future__ import annotations

import math

import pytest

from app.data import seeded_candles
from app.data.seeded_candles import PRICE_SEMANTICS, TIMEFRAMES, candles_for

SYMBOLS = ["فملی", "فولاد", "ZZZ_UNKNOWN_X"]  # seed-price, seed-price, pseudo-price

# Fixed absolute end indices per timeframe (explicit everywhere: never wall-clock).
END_BY_TF = {"1m": 1_000_000, "5m": 500_000, "15m": 200_000, "1h": 100_000, "1D": 20_000}

BOUNDARY_COUNTS = [50, 51, 999, 1000]  # clamp floor / floor+1 / ceiling-1 / ceiling


# ---------------------------------------------------------------------------
# OHLCV integrity invariants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("symbol", SYMBOLS)
@pytest.mark.parametrize("timeframe", sorted(TIMEFRAMES))
@pytest.mark.parametrize("count", BOUNDARY_COUNTS)
def test_ohlcv_integrity_invariants(symbol, timeframe, count):
    candles = candles_for(symbol, timeframe, count, end_bar_index=END_BY_TF[timeframe])
    assert len(candles) == max(50, min(1000, count))
    for bar in candles:
        assert set(bar) == {"time", "open", "high", "low", "close", "volume"}
        o, h, low, c, v = bar["open"], bar["high"], bar["low"], bar["close"], bar["volume"]
        # Candle geometry: the wick factors only ever widen the body.
        assert h >= max(o, c)
        assert low <= min(o, c)
        assert h >= low
        for price in (o, h, low, c):
            assert isinstance(price, float)
            assert price > 0  # positive base * factor in (0.988, 1.03)
            assert math.isfinite(price)
        assert isinstance(v, int)
        assert v >= 1  # generator floor is max(1, ...) — implies the >= 0 bound


# ---------------------------------------------------------------------------
# Ordering / uniqueness / grid continuity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("timeframe", sorted(TIMEFRAMES))
def test_strict_ordering_unique_times_continuous_grid(timeframe):
    tf_sec = TIMEFRAMES[timeframe]
    candles = candles_for("فملی", timeframe, 137, end_bar_index=END_BY_TF[timeframe])
    times = [bar["time"] for bar in candles]
    assert len(times) == 137
    assert all(t2 > t1 for t1, t2 in zip(times, times[1:]))  # strictly increasing
    assert len(set(times)) == len(times)  # no duplicate (symbol, timeframe, time) rows
    # Continuous arithmetic grid — NO skipped buckets, market-closed periods
    # included by construction (documented synthetic behavior; time = index * tf_sec).
    assert all(b - a == tf_sec for a, b in zip(times, times[1:]))
    assert all(t % tf_sec == 0 for t in times)


@pytest.mark.parametrize("count", [50, 137, 999, 1000])
def test_index_continuity_requested_window(count):
    # Real contract: start = end - n + 1 with n = clamp(count); bar i has
    # time = i * tf_sec, so a requested length N inside 50..1000 yields exactly
    # the contiguous absolute indices [end-N+1 .. end] (indices are implicit,
    # observable through the times).
    tf_sec = TIMEFRAMES["1h"]
    end = 100_000
    candles = candles_for("فولاد", "1h", count, end_bar_index=end)
    assert len(candles) == count  # interior of the clamp band: exact, no clamping
    assert [bar["time"] for bar in candles] == [(end - count + 1 + k) * tf_sec for k in range(count)]


# ---------------------------------------------------------------------------
# Boundary timestamps (hand-derived from the module's own arithmetic)
# ---------------------------------------------------------------------------

def test_boundary_timestamps_smallest_timeframe():
    # 1m (60s), count 50, end 1000: n = 50, start = 1000 - 50 + 1 = 951
    #   first time = 951 * 60 = 57060; last time = 1000 * 60 = 60000
    candles = candles_for("فملی", "1m", 50, end_bar_index=1000)
    assert candles[0]["time"] == 951 * 60 == 57_060
    assert candles[-1]["time"] == 1000 * 60 == 60_000
    assert all(t % 60 == 0 for t in (bar["time"] for bar in candles))


def test_boundary_timestamps_largest_timeframe():
    # 1D (86400s), count 51, end 20000: n = 51, start = 20000 - 51 + 1 = 19950
    #   first time = 19950 * 86400 = 1723680000; last = 20000 * 86400 = 1728000000
    candles = candles_for("فملی", "1D", 51, end_bar_index=20_000)
    assert candles[0]["time"] == 19_950 * 86_400 == 1_723_680_000
    assert candles[-1]["time"] == 20_000 * 86_400 == 1_728_000_000
    # Daily grid is continuous: consecutive buckets sit exactly 86400s apart
    # (weekends/holidays are NOT skipped — pinned synthetic-grid semantics).
    gaps = {b - a for a, b in zip((bar["time"] for bar in candles), (bar["time"] for bar in candles[1:]))}
    assert gaps == {86_400}


# ---------------------------------------------------------------------------
# Determinism + perturbation sensitivity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("timeframe", sorted(TIMEFRAMES))
def test_same_args_double_run_exact(timeframe):
    end = END_BY_TF[timeframe]
    a = candles_for("فملی", timeframe, 60, end_bar_index=end)
    b = candles_for("فملی", timeframe, 60, end_bar_index=end)
    assert a == b  # == on dicts: byte-identical payloads for all 5 grids


@pytest.mark.parametrize("other_symbol", ["فولاد", "ZZZ_UNKNOWN_X"])
def test_perturbation_symbol_changes_output(other_symbol):
    base = candles_for("فملی", "1m", 50, end_bar_index=777)
    other = candles_for(other_symbol, "1m", 50, end_bar_index=777)
    fields = ("open", "high", "low", "close", "volume")
    assert any(base[i][f] != other[i][f] for i in range(50) for f in fields)


def test_perturbation_timeframe_changes_output():
    a = candles_for("فملی", "1m", 50, end_bar_index=1000)
    b = candles_for("فملی", "5m", 50, end_bar_index=1000)
    assert [x["time"] for x in a] != [x["time"] for x in b]  # bucket spacing differs
    assert a != b  # digest key includes the timeframe, so values differ too


def test_perturbation_end_index_shifts_window():
    a = candles_for("فملی", "1h", 50, end_bar_index=10_000)
    b = candles_for("فملی", "1h", 50, end_bar_index=10_000 + 250)
    assert a[-1]["time"] == 10_000 * 3600
    assert b[-1]["time"] == 10_250 * 3600
    assert a[0]["time"] != b[0]["time"]


# ---------------------------------------------------------------------------
# Clamp behavior (clamped, never refused)
# ---------------------------------------------------------------------------

def test_count_clamp_is_clamp_not_refuse():
    # n = max(50, min(1000, int(count))): 49 and 1001 are clamped onto the band.
    assert len(candles_for("فملی", "5m", 49, end_bar_index=1000)) == 50
    assert len(candles_for("فملی", "5m", 1001, end_bar_index=1000)) == 1000
    assert len(candles_for("فملی", "5m", 0, end_bar_index=1000)) == 50
    assert len(candles_for("فملی", "5m", -5, end_bar_index=1000)) == 50
    for count in (50, 51, 999, 1000):  # interior: exact pass-through
        assert len(candles_for("فملی", "5m", count, end_bar_index=1000)) == count


def test_clamped_length_governs_window_start():
    # The clamped n (not the requested length) fixes the window start.
    # 49 -> n = 50 -> start = 1000 - 50 + 1 = 951; 5m: time = index * 300.
    clamped_low = candles_for("فملی", "5m", 49, end_bar_index=1000)
    assert clamped_low[0]["time"] == 951 * 300 == 285_300
    # 1001 -> n = 1000 -> start = 1000 - 1000 + 1 = 1.
    clamped_high = candles_for("فملی", "5m", 1001, end_bar_index=1000)
    assert clamped_high[0]["time"] == 1 * 300 == 300


# ---------------------------------------------------------------------------
# Price semantics tag
# ---------------------------------------------------------------------------

def test_price_semantics_constant_pinned():
    # Explicit unadjusted-by-construction tag (added WDA-2): synthetic prices
    # never represent corporate-action-adjusted history.
    assert PRICE_SEMANTICS == "UNADJUSTED_SYNTHETIC"
    assert "UNADJUSTED_SYNTHETIC" in seeded_candles.__doc__  # docstring stays in sync
