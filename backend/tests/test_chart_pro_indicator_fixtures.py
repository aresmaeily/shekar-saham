"""WDA-2 — independent hand-computed indicator fixtures for chart-pro engines.

Complements tests/test_indicators.py (property-style checks on generated
ramps) and tests/test_chart_pro_api.py (endpoint shape/determinism): this file
pins the chart-pro indicator math against HAND-COMPUTED literals on tiny fixed
series, calling exactly the public functions the /api/v10/chartpro router
calls — app.engines.chart_builder.calculate_ma / calculate_ema /
calculate_rsi and app.engines.indicators.macd / bollinger (chart_pro.py
reimplements none of the math). Every expected value is derived from the
standard textbook formula with explicit arithmetic in the comments; nothing is
copied from observed production output.

Documented engine variants being pinned:
- MA(n)      : simple mean of the last n closes; first point at bar n-1.
- EMA(n)     : chart_builder variant — k = 2/(n+1), SEEDED WITH THE FIRST
               CLOSE and emitted from bar 0 (no warm-up):
               ema[0] = close[0]; ema[i] = close[i]*k + ema[i-1]*(1-k).
               (Distinct from the SMA-seeded variant in indicators._ema_series.)
- RSI(n)     : Wilder 1978 — first averages are simple means of the first n
               close-to-close changes; then avg = (prev*(n-1) + curr)/n;
               first point at bar n; values rounded to 2 decimals.
- MACD(12,26,9): indicators._ema_series variant — EMA seeded with the SMA of
               the first `period` values (flat head), recursion from index
               `period` with k = 2/(period+1); macd = ef - es,
               signal = EMA9(macd), hist = macd - signal; rounded to 8.
- Bollinger(20, 2): population stddev (divide by n): mid = mean of the last
               20 closes, band = mean ± 2*sd; rounded to 6.

Identical operation order on identical inputs makes the float comparisons
exact (IEEE-754 determinism); pure-rational hand values are cross-checked
with pytest.approx.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engines.chart_builder import calculate_ema, calculate_ma, calculate_rsi
from app.engines.indicators import bollinger, macd
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixed fixtures (hand-written literals)
# ---------------------------------------------------------------------------

# Fixture A — 25 closes, a symmetric "mountain": rise 100->110, fall 110->100,
# then 101..104. Hand property used throughout: EVERY 20-close window of this
# series sums to exactly 2100 (sliding drops one rung and adds its mirror:
# 110<->100, 109<->101, ...) and its squared deviations from 105 sum to 170.
CLOSES_A = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
            109, 108, 107, 106, 105, 104, 103, 102, 101,
            100, 101, 102, 103, 104]

# Fixture B — 35 closes, arithmetic ramp 100..168 step 2: the SMA seeds are
# exact integers (mean(100..122) = 111, mean(100..150) = 125), which makes the
# MACD head hand-checkable.
CLOSES_B = [100 + 2 * i for i in range(35)]


def _ohlcv(closes, start_time=1_700_000_000, step_sec=60):
    """Wrap hand closes into ohlcv dicts (engines read only close/time here)."""
    out = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i else c
        out.append({
            "time": start_time + i * step_sec,
            "open": float(prev),
            "high": float(max(prev, c)) + 0.5,
            "low": float(min(prev, c)) - 0.5,
            "close": float(c),
            "volume": 1000,
        })
    return out


OHLCV_A = _ohlcv(CLOSES_A)
OHLCV_B = _ohlcv(CLOSES_B)


def _sma_seeded_ema(values, period):
    """SMA-seeded EMA re-derived from the documented _ema_series variant:
    the first `period` outputs are the flat SMA seed, then the standard
    k = 2/(period+1) recursion takes over."""
    seed = values[:period]
    ema = [sum(seed) / len(seed)] * len(seed)
    k = 2 / (period + 1)
    prev = ema[-1]
    for v in values[period:]:
        prev = v * k + prev * (1 - k)
        ema.append(prev)
    return ema


def _align(series, ohlcv):
    """Router-style alignment re-derived (not imported): project an engine
    series onto the ohlcv time grid, padding the warm-up head with None."""
    by_time = {p["time"]: p.get("value") for p in series}
    return [{"time": c["time"], "value": by_time.get(c["time"])} for c in ohlcv]


# ---------------------------------------------------------------------------
# MA (chart_builder.calculate_ma)
# ---------------------------------------------------------------------------

def test_ma20_hand_computed():
    # Hand arithmetic for the boundary windows (the identical-sum argument
    # covers the rest):
    #   window at bar 19 = CLOSES_A[0:20] = 100..110 then 109..101:
    #     sum = (100+109)*10/2 + (101+110)*10/2 = 1045 + 1055 = 2100 -> 105.0
    #   window at bar 24 = CLOSES_A[5:25] = 105..110,109..100,101..104:
    #     sum = 105+106+107+108+109+110+109+108+107+106+105
    #         + 104+103+102+101+100+101+102+103+104 = 2100 -> 105.0
    # Sliding by one swaps a rung for its mirror (110<->100, 109<->101, ...),
    # so ALL six 20-windows average 105.0.
    ma = calculate_ma(OHLCV_A, 20)
    assert [p["time"] for p in ma] == [bar["time"] for bar in OHLCV_A[19:]]
    assert [p["value"] for p in ma] == [105.0] * 6


def test_ma_warmup_and_min_period_semantics():
    # First point exactly at bar index period-1; nothing before it.
    assert len(calculate_ma(OHLCV_A[:19], 20)) == 0  # 19 bars: window never full
    single = calculate_ma(OHLCV_A[:20], 20)  # exactly 20 bars: one point
    assert [p["value"] for p in single] == [105.0]  # mean(100..110,109..101) = 2100/20
    assert len(calculate_ma(OHLCV_A, 50)) == 0  # ma50 needs 50 bars: none on 25


# ---------------------------------------------------------------------------
# EMA (chart_builder.calculate_ema — first-close seed variant)
# ---------------------------------------------------------------------------

def test_ema20_first_close_seed_variant():
    # Documented variant: k = 2/(n+1) = 2/21, seeded with the FIRST close and
    # emitted from bar 0 (no warm-up nulls):
    #   ema[0] = 100
    #   ema[1] = 101*k + 100*(1-k) = (101*2 + 100*19)/21 = 2102/21 ≈ 100.0952381
    k = 2 / 21
    ema = calculate_ema(OHLCV_A, 20)
    assert len(ema) == 25  # emitted from the first bar — zero warm-up
    assert ema[0]["value"] == 100.0  # seed = first close
    assert ema[1]["value"] == 101 * k + 100 * (1 - k)
    assert ema[1]["value"] == pytest.approx(2102 / 21, abs=1e-12)  # rational check
    # Full series equals the documented recurrence, re-derived independently.
    expected = [OHLCV_A[0]["close"]]
    prev = OHLCV_A[0]["close"]
    for bar in OHLCV_A[1:]:
        prev = bar["close"] * k + prev * (1 - k)
        expected.append(prev)
    assert [p["value"] for p in ema] == expected


# ---------------------------------------------------------------------------
# RSI (chart_builder.calculate_rsi — Wilder 1978)
# ---------------------------------------------------------------------------

def test_rsi14_wilder_hand_computed():
    # Changes on CLOSES_A: bars 1..10 are +1 (100->110), bars 11..20 are -1
    # (110->100), bars 21..24 are +1 (100->104).
    # First point at bar 14 averages changes 1..14: 10 gains, 4 losses:
    #   avg_gain = 10/14, avg_loss = 4/14 -> RS = 2.5
    #   RSI = 100 - 100/(1 + 2.5) = 71.428571... -> 71.43
    # Bar 15 (Wilder smoothing, period 14):
    #   avg_gain = (10/14*13 + 0)/14 = 130/196
    #   avg_loss = (4/14*13 + 1)/14 = 66/196
    #   RSI = 100*avg_gain/(avg_gain + avg_loss) = 100*130/196 = 66.3265... -> 66.33
    rsi = calculate_rsi(OHLCV_A, 14)
    assert len(rsi) == 11  # bars 14..24 (first point at bar == period)
    assert [p["time"] for p in rsi] == [bar["time"] for bar in OHLCV_A[14:]]
    assert rsi[0]["value"] == 71.43
    assert rsi[1]["value"] == 66.33
    assert all(0.0 <= p["value"] <= 100.0 for p in rsi)
    assert len(calculate_rsi(OHLCV_A[:14], 14)) == 0  # needs period+1 closes
    # Full series equals the documented Wilder recurrence, re-derived independently.
    closes = [bar["close"] for bar in OHLCV_A]
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    avg_gain = sum(gains[:14]) / 14
    avg_loss = sum(losses[:14]) / 14
    expected = []
    for i in range(14, len(closes)):
        if i > 14:
            avg_gain = (avg_gain * 13 + max(closes[i] - closes[i - 1], 0)) / 14
            avg_loss = (avg_loss * 13 + max(closes[i - 1] - closes[i], 0)) / 14
        rsi_i = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
        expected.append(round(rsi_i, 2))
    assert [p["value"] for p in rsi] == expected


# ---------------------------------------------------------------------------
# Bollinger (indicators.bollinger — population stddev, 20, 2)
# ---------------------------------------------------------------------------

def test_bollinger_hand_computed():
    # Every 20-window of CLOSES_A: sum 2100 (mid = 105.0) and squared
    # deviations from 105 sum to exactly 170 (boundary windows hand-checked;
    # the mirror-swap slide preserves both sums). Population variance:
    #   var = 170/20 = 8.5, sd = sqrt(8.5) ≈ 2.9154759474226504
    #   upper = 105 + 2*sd ≈ 110.830952, lower = 105 - 2*sd ≈ 99.169048
    bol = bollinger(OHLCV_A)
    sd = (170 / 20) ** 0.5
    assert [p["time"] for p in bol["basis"]] == [bar["time"] for bar in OHLCV_A[19:]]
    assert [p["value"] for p in bol["basis"]] == [105.0] * 6
    assert {p["value"] for p in bol["upper"]} == {round(105 + 2 * sd, 6)}
    assert {p["value"] for p in bol["lower"]} == {round(105 - 2 * sd, 6)}
    assert len(bollinger(OHLCV_A[:19])["upper"]) == 0  # warm-up: no full window


# ---------------------------------------------------------------------------
# MACD (indicators.macd — SMA-seeded EMA, 12/26/9)
# ---------------------------------------------------------------------------

def test_macd_hand_computed():
    # CLOSES_B = 100, 102, ..., 168 (35 bars). SMA-seeded heads are exact:
    #   ef head = mean(100..122) = (100+122)*12/2/12 = 1332/12 = 111.0 (bars 0..11)
    #   es head = mean(100..150) = (100+150)*26/2/26 = 3250/26 = 125.0 (bars 0..25)
    #   macd head = 111 - 125 = -14.0 (bars 0..11, both EMAs still flat)
    #   signal head = mean(macd[0:9]) = -126/9 = -14.0 (bars 0..8)
    #   hist head  = macd - signal = 0.0 (bars 0..8)
    m = macd(OHLCV_B)
    assert len(m["macd"]) == len(m["signal"]) == len(m["histogram"]) == 35
    assert [p["value"] for p in m["macd"][:12]] == [-14.0] * 12
    assert [p["value"] for p in m["signal"][:9]] == [-14.0] * 9
    assert {p["value"] for p in m["histogram"][:9]} == {0.0}
    # Rational spot-checks past the seeds (hand arithmetic):
    #   ef[12] = 124*(2/13) + 111*(11/13) = (248 + 1221)/13 = 1469/13 = 113.0
    #   es[26] = 152*(2/27) + 125*(25/27) = (304 + 3125)/27 = 3429/27 = 127.0
    closes = [bar["close"] for bar in OHLCV_B]
    ef = _sma_seeded_ema(closes, 12)
    es = _sma_seeded_ema(closes, 26)
    assert ef[12] == pytest.approx(113.0, abs=1e-9)
    assert es[26] == pytest.approx(127.0, abs=1e-9)
    macd_line = [ef[i] - es[i] for i in range(35)]
    signal = _sma_seeded_ema(macd_line, 9)
    assert [p["value"] for p in m["macd"]] == [round(v, 8) for v in macd_line]
    assert [p["value"] for p in m["signal"]] == [round(v, 8) for v in signal]
    assert [p["value"] for p in m["histogram"]] == [round(macd_line[i] - signal[i], 8) for i in range(35)]


def test_macd_min_data_contract():
    # Engine contract: fewer than 2 closes -> empty series (never crashes).
    assert macd(OHLCV_B[:1]) == {"macd": [], "signal": [], "histogram": []}
    assert macd([])["macd"] == []


# ---------------------------------------------------------------------------
# Endpoint == engine consistency + trust envelope (offline synthetic only)
# ---------------------------------------------------------------------------

def test_endpoint_indicators_equal_engines():
    # The router must expose engine outputs verbatim, aligned onto the ohlcv
    # grid with None warm-up padding — verified here against the SAME engine
    # functions called directly on the response's own series (the endpoint
    # window is wall-clock-resolved, but both sides consume identical bars).
    r = client.get("/api/v10/chartpro/فملی/indicators", params={"timeframe": "1h", "limit": 60})
    assert r.status_code == 200
    body = r.json()
    ohlcv = body["ohlcv"]
    assert body["count"] == len(ohlcv) == 60
    ind = body["indicators"]
    macd_out = macd(ohlcv)
    bol = bollinger(ohlcv)
    assert ind["ma20"] == _align(calculate_ma(ohlcv, 20), ohlcv)
    assert ind["ma50"] == _align(calculate_ma(ohlcv, 50), ohlcv)
    assert ind["ema20"] == _align(calculate_ema(ohlcv, 20), ohlcv)
    assert ind["rsi14"] == _align(calculate_rsi(ohlcv, 14), ohlcv)
    assert ind["macd"]["macd"] == _align(macd_out["macd"], ohlcv)
    assert ind["macd"]["signal"] == _align(macd_out["signal"], ohlcv)
    assert ind["macd"]["hist"] == _align(macd_out["histogram"], ohlcv)
    assert ind["bollinger"]["upper"] == _align(bol["upper"], ohlcv)
    assert ind["bollinger"]["mid"] == _align(bol["basis"], ohlcv)
    assert ind["bollinger"]["lower"] == _align(bol["lower"], ohlcv)


def test_endpoint_trust_envelope_never_live():
    body = client.get("/api/v10/chartpro/فملی/indicators", params={"limit": 50}).json()
    trust = body["data_trust"]
    # No source-ish field may claim "live" in this offline synthetic env, and
    # the trust verdict must never carry live flags (conftest pins mock).
    assert trust["state"] != "live"
    assert trust["source"] != "live"
    assert trust["provider"] != "live"
    assert trust["data_source_config"] != "live"
    assert trust["is_live"] is False
    assert trust["live_verified"] is False
    assert body["trust_level"] != "live"
