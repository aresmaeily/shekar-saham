"""
test_indicators.py - v1.2 تست اندیکاتورهای کلاسیک (مثل فراز / تریدینگ ویو)
"""
import math

from app.engines.indicators import (
    macd, bollinger, stochastic, atr, adx, cci, obv, williams, vwap,
)
from app.data.forex_provider import build_range_bars, is_range_timeframe


def _make_data(n=100, start=100.0, step=0.5):
    """مسیر صعودی ساده با حجم ثابت."""
    data = []
    p = start
    for i in range(n):
        data.append({
            "time": 1700000000 + i * 60,
            "open": p,
            "high": p + 1,
            "low": p - 1,
            "close": p + step,
            "volume": 1000.0,
        })
        p += step
    return data


def test_macd_shape():
    d = _make_data(120)
    r = macd(d)
    assert "macd" in r and "signal" in r and "histogram" in r
    n = len(d)
    assert len(r["macd"]) == n
    assert len(r["histogram"]) == n
    # histogram = macd - signal
    for i in range(n):
        assert abs(r["histogram"][i]["value"] - (r["macd"][i]["value"] - r["signal"][i]["value"])) < 1e-6


def test_bollinger_order():
    d = _make_data(60)
    r = bollinger(d)
    assert len(r["upper"]) == len(r["basis"]) == len(r["lower"])
    for u, b, l in zip(r["upper"], r["basis"], r["lower"]):
        assert u["value"] >= b["value"] >= l["value"]


def test_stochastic_range():
    d = _make_data(80)
    r = stochastic(d)
    assert r["k"] and r["d"]
    for p in r["k"] + r["d"]:
        assert 0 <= p["value"] <= 100


def test_williams_range():
    d = _make_data(80)
    r = williams(d)
    assert r
    for p in r:
        assert -100 <= p["value"] <= 0


def test_atr_positive():
    d = _make_data(80)
    r = atr(d)
    assert r
    for p in r:
        assert p["value"] > 0


def test_adx_range():
    d = _make_data(120)
    r = adx(d)
    assert r["adx"]
    for p in r["adx"]:
        assert 0 <= p["value"] <= 100


def test_obv_cumulative():
    d = _make_data(50)
    r = obv(d)
    assert len(r) == 50
    # مسیر صعودی -> OBV باید صعودی باشد
    assert r[-1]["value"] > r[0]["value"]


def test_cci_finite():
    d = _make_data(80)
    r = cci(d)
    assert r
    for p in r:
        assert math.isfinite(p["value"])


def test_vwap_between_low_high():
    d = _make_data(50)
    r = vwap(d)
    assert r
    for p in r:
        assert p["value"] > 0


def test_range_timeframe_detection():
    assert is_range_timeframe("10R")
    assert is_range_timeframe("1000R")
    assert not is_range_timeframe("1m")
    assert not is_range_timeframe("5m")
    assert not is_range_timeframe("1D")


def test_range_bars_up_trend():
    """مسیر صعودی 100->150 با رنج 10 باید ۵ رنج بار بدهد."""
    data = []
    p = 100.0
    for i in range(50):
        data.append({
            "time": 1700000000 + i * 60,
            "open": p, "high": p + 1.2, "low": p - 0.5, "close": p + 1.2,
            "volume": 100.0,
        })
        p += 1.2
    bars = build_range_bars(data, 10)
    assert len(bars) >= 5
    closed = [b for b in bars[:-1]]  # آخرین کندل ممکن است ناقص باشد
    for b in closed:
        assert abs((b["high"] - b["low"]) - 10) < 1e-6
    # زمان‌ها اکیداً صعودی
    times = [b["time"] for b in bars]
    assert all(times[i] < times[i + 1] for i in range(len(times) - 1))
    # منبع
    assert bars[0]["source"] == "range-10"


def test_range_bars_empty_input():
    assert build_range_bars([], 10) == []
    assert build_range_bars(_make_data(10), -5) == []
