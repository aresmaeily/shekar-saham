"""
indicators.py - v1.2 اندیکاتورهای کلاسیک مثل فراز / تریدینگ ویو
MACD, Bollinger Bands, Stochastic, ATR, ADX/DMI, CCI, OBV, Williams %R, VWAP

همه توابع لیست کندل [{time, open, high, low, close, volume}] می‌گیرند و
لیست [{time, value}] برمی‌گردانند (بعد از دوره گرم‌شدن).
"""
from __future__ import annotations

from typing import Dict, List

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _ema_series(values: List[float], period: int) -> List[float]:
    """EMA با seed از SMA دوره اول (دقیق‌تر از seed با اولین مقدار)."""
    n = len(values)
    if n == 0 or period <= 0:
        return []
    seed_vals = values[: min(period, n)]
    ema = [sum(seed_vals) / len(seed_vals)] * len(seed_vals)
    if n <= period:
        return ema
    k = 2 / (period + 1)
    prev = ema[-1]
    for v in values[period:]:
        prev = v * k + prev * (1 - k)
        ema.append(prev)
    return ema


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return default if b == 0 else a / b


# ---------------------------------------------------------------------------
# MACD (12, 26, 9)
# ---------------------------------------------------------------------------
def macd(data: List[Dict], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[Dict]]:
    closes = [c["close"] for c in data]
    n = len(closes)
    times = [c["time"] for c in data]
    if n < 2:
        return {"macd": [], "signal": [], "histogram": []}
    ef = _ema_series(closes, fast)
    es = _ema_series(closes, slow)
    macd_line = [ef[i] - es[i] for i in range(n)]
    sig = _ema_series(macd_line, signal)
    hist = [macd_line[i] - sig[i] for i in range(n)]
    return {
        "macd": [{"time": times[i], "value": round(macd_line[i], 8)} for i in range(n)],
        "signal": [{"time": times[i], "value": round(sig[i], 8)} for i in range(n)],
        "histogram": [{"time": times[i], "value": round(hist[i], 8)} for i in range(n)],
    }


# ---------------------------------------------------------------------------
# Bollinger Bands (20, 2)
# ---------------------------------------------------------------------------
def bollinger(data: List[Dict], period: int = 20, mult: float = 2.0) -> Dict[str, List[Dict]]:
    n = len(data)
    basis, upper, lower = [], [], []
    for i in range(n):
        if i < period - 1:
            continue
        window = [c["close"] for c in data[i - period + 1 : i + 1]]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        sd = var ** 0.5
        t = data[i]["time"]
        basis.append({"time": t, "value": round(mean, 6)})
        upper.append({"time": t, "value": round(mean + mult * sd, 6)})
        lower.append({"time": t, "value": round(mean - mult * sd, 6)})
    return {"basis": basis, "upper": upper, "lower": lower}


# ---------------------------------------------------------------------------
# Stochastic (14, 3, 3)
# ---------------------------------------------------------------------------
def stochastic(data: List[Dict], k_period: int = 14, d_period: int = 3, smooth: int = 3) -> Dict[str, List[Dict]]:
    n = len(data)
    k_raw: List[float] = []
    for i in range(n):
        if i < k_period - 1:
            k_raw.append(float("nan"))
            continue
        window = data[i - k_period + 1 : i + 1]
        hh = max(c["high"] for c in window)
        ll = min(c["low"] for c in window)
        rng = hh - ll
        k_raw.append(50.0 if rng == 0 else (data[i]["close"] - ll) / rng * 100.0)

    k_smooth: List[float] = []
    for i in range(n):
        if k_raw[i] != k_raw[i]:  # nan
            k_smooth.append(float("nan"))
            continue
        vals = [k for k in k_raw[max(0, i - smooth + 1) : i + 1] if k == k]
        k_smooth.append(sum(vals) / len(vals) if vals else float("nan"))

    d_out: List[float] = []
    for i in range(n):
        if k_smooth[i] != k_smooth[i] or i < d_period - 1:
            d_out.append(float("nan"))
            continue
        vals = [k for k in k_smooth[i - d_period + 1 : i + 1] if k == k]
        d_out.append(sum(vals) / d_period if len(vals) >= d_period else float("nan"))

    times = [c["time"] for c in data]
    return {
        "k": [{"time": times[i], "value": round(k_smooth[i], 4)} for i in range(n) if k_smooth[i] == k_smooth[i]],
        "d": [{"time": times[i], "value": round(d_out[i], 4)} for i in range(n) if d_out[i] == d_out[i]],
    }


# ---------------------------------------------------------------------------
# ATR (14) — وایلدر
# ---------------------------------------------------------------------------
def atr(data: List[Dict], period: int = 14) -> List[Dict]:
    n = len(data)
    if n < period + 1:
        return []
    trs = []
    for i in range(n):
        hi, lo = data[i]["high"], data[i]["low"]
        if i == 0:
            tr = hi - lo
        else:
            pc = data[i - 1]["close"]
            tr = max(hi - lo, abs(hi - pc), abs(lo - pc))
        trs.append(tr)
    out = []
    atr_prev = sum(trs[:period]) / period
    out.append({"time": data[period - 1]["time"], "value": round(atr_prev, 6)})
    for i in range(period, n):
        atr_prev = (atr_prev * (period - 1) + trs[i]) / period
        out.append({"time": data[i]["time"], "value": round(atr_prev, 6)})
    return out


# ---------------------------------------------------------------------------
# ADX / DMI (14)
# ---------------------------------------------------------------------------
def adx(data: List[Dict], period: int = 14) -> Dict[str, List[Dict]]:
    n = len(data)
    empty = {"adx": [], "plus_di": [], "minus_di": []}
    if n < period + 2:
        return empty
    trs, pdm, mdm = [], [], []
    for i in range(1, n):
        hi, lo = data[i]["high"], data[i]["low"]
        pc, ph, pl = data[i - 1]["close"], data[i - 1]["high"], data[i - 1]["low"]
        trs.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
        up, dn = hi - ph, pl - lo
        pdm.append(up if (up > dn and up > 0) else 0.0)
        mdm.append(dn if (dn > up and dn > 0) else 0.0)

    atr_w = sum(trs[:period]) / period
    pdi_w = sum(pdm[:period]) / period
    mdi_w = sum(mdm[:period]) / period

    def di(pi: float, ai: float) -> float:
        return 0.0 if ai == 0 else pi / ai * 100.0

    def dx(pdi: float, mdi: float) -> float:
        s = pdi + mdi
        return 0.0 if s == 0 else abs(pdi - mdi) / s * 100.0

    out, plus, minus, adxs = [], [], [], []
    # اولین نقطه در داده[period] (لیست‌ها از داده[1] شروع شده‌اند)
    t0 = data[period]["time"]
    d0 = dx(di(pdi_w, atr_w), di(mdi_w, atr_w))
    adx_val = d0
    out.append({"time": t0, "value": round(d0, 4)})
    plus.append({"time": t0, "value": round(di(pdi_w, atr_w), 4)})
    minus.append({"time": t0, "value": round(di(mdi_w, atr_w), 4)})
    adxs.append({"time": t0, "value": round(adx_val, 4)})

    for i in range(period, len(pdm)):
        atr_w = (atr_w * (period - 1) + trs[i]) / period
        pdi_w = (pdi_w * (period - 1) + pdm[i]) / period
        mdi_w = (mdi_w * (period - 1) + mdm[i]) / period
        t = data[i + 1]["time"]
        d = dx(di(pdi_w, atr_w), di(mdi_w, atr_w))
        adx_val = (adx_val * (period - 1) + d) / period
        out.append({"time": t, "value": round(d, 4)})
        plus.append({"time": t, "value": round(di(pdi_w, atr_w), 4)})
        minus.append({"time": t, "value": round(di(mdi_w, atr_w), 4)})
        adxs.append({"time": t, "value": round(adx_val, 4)})

    return {"adx": adxs, "plus_di": plus, "minus_di": minus}


# ---------------------------------------------------------------------------
# CCI (20)
# ---------------------------------------------------------------------------
def cci(data: List[Dict], period: int = 20) -> List[Dict]:
    n = len(data)
    out = []
    for i in range(n):
        if i < period - 1:
            continue
        window = data[i - period + 1 : i + 1]
        tp = [(c["high"] + c["low"] + c["close"]) / 3 for c in window]
        mean = sum(tp) / period
        md = sum(abs(x - mean) for x in tp) / period
        cur = tp[-1]
        val = 0.0 if md == 0 else (cur - mean) / (0.015 * md)
        out.append({"time": data[i]["time"], "value": round(val, 4)})
    return out


# ---------------------------------------------------------------------------
# OBV (حجم انباشته)
# ---------------------------------------------------------------------------
def obv(data: List[Dict]) -> List[Dict]:
    out = []
    prev = 0.0
    for i, c in enumerate(data):
        v = c.get("volume") or 0
        if i == 0:
            prev = v
        elif c["close"] > data[i - 1]["close"]:
            prev += v
        elif c["close"] < data[i - 1]["close"]:
            prev -= v
        out.append({"time": c["time"], "value": round(prev, 4)})
    return out


# ---------------------------------------------------------------------------
# Williams %R (14)
# ---------------------------------------------------------------------------
def williams(data: List[Dict], period: int = 14) -> List[Dict]:
    n = len(data)
    out = []
    for i in range(n):
        if i < period - 1:
            continue
        window = data[i - period + 1 : i + 1]
        hh = max(c["high"] for c in window)
        ll = min(c["low"] for c in window)
        rng = hh - ll
        val = -50.0 if rng == 0 else -100.0 * (hh - data[i]["close"]) / rng
        out.append({"time": data[i]["time"], "value": round(val, 4)})
    return out


# ---------------------------------------------------------------------------
# VWAP (انباشته روی کل داده)
# ---------------------------------------------------------------------------
def vwap(data: List[Dict]) -> List[Dict]:
    out = []
    cum_pv = 0.0
    cum_v = 0.0
    for c in data:
        tp = (c["high"] + c["low"] + c["close"]) / 3
        v = c.get("volume") or 0
        cum_pv += tp * v
        cum_v += v
        if cum_v > 0:
            out.append({"time": c["time"], "value": round(cum_pv / cum_v, 6)})
    return out


# ---------------------------------------------------------------------------
# جدول اندیکاتورها برای رفرنس
# ---------------------------------------------------------------------------
INDICATOR_CATALOG = {
    "macd": {"name": "MACD", "kind": "oscillator", "fn": macd},
    "bollinger": {"name": "Bollinger Bands", "kind": "overlay", "fn": bollinger},
    "stochastic": {"name": "Stochastic", "kind": "oscillator", "fn": stochastic},
    "atr": {"name": "ATR", "kind": "oscillator", "fn": atr},
    "adx": {"name": "ADX", "kind": "oscillator", "fn": adx},
    "cci": {"name": "CCI", "kind": "oscillator", "fn": cci},
    "obv": {"name": "OBV", "kind": "oscillator", "fn": obv},
    "williams": {"name": "Williams %R", "kind": "oscillator", "fn": williams},
    "vwap": {"name": "VWAP", "kind": "overlay", "fn": vwap},
}
