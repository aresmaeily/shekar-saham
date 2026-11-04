"""indicator_reference.py — PKG-F (MASTER-RADAR directive §B4, Wave 3).

Independent, textbook reference implementations for the built-in indicator
catalog. These functions are deliberately written from scratch and NEVER call
``app.engines.indicators``: the whole point is cross-validation of the legacy
engine against an independent second implementation (directive §B4).

Conventions (documented per §B4 honesty requirements):

* Bars use the shared contract ``{"ts": int epoch-sec ascending unique,
  "o","h","l","c","v": float}``.  The legacy engine module uses its own
  ``{"time","open","high","low","close","volume"}`` shape; adapters live in
  the caller (tests), never here.
* All value-series functions are pure, deterministic, and free of I/O, clock
  access, and any dynamic code evaluation (no eval/exec/compile anywhere —
  directive §B4 "do not execute arbitrary downloaded code").
* Warm-up policy per function is stated in its docstring.  For functions with
  no natural zero fill (EMA family) the pre-warm-up slots carry the SMA seed
  as a documented carry-over artifact so that compositions (MACD signal line)
  remain bit-identical to the legacy engine they cross-validate; consumers
  must ignore indices below the declared ``warmup_bars``.
"""

from __future__ import annotations

from typing import Dict, List

# Fixed rolling-high window for ref_new_high_rate (directive §B4 wording:
# "rolling 20-bar highs").  Kept as a named constant, not a parameter, so the
# public signature stays exactly ref_new_high_rate(closes, lookback=20).
NEW_HIGH_WINDOW = 20


# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------
def ref_sma(values: List[float], period: int) -> List[float]:
    """Simple Moving Average.

    Formula: ``SMA[i] = (1/period) * sum(values[i-period+1 .. i])``.

    Warm-up policy: output is ``0.0`` for every index ``i < period - 1``;
    the first valid value sits at index ``period - 1`` (so
    ``warmup_bars == period - 1``).  Requires ``period >= 1`` and a non-empty
    ``values`` list.
    """
    if period <= 0:
        raise ValueError("ref_sma: period must be >= 1")
    if not values:
        raise ValueError("ref_sma: values must be non-empty")
    n = len(values)
    out = [0.0] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        out[i] = sum(window) / period
    return out


def ref_ema(values: List[float], period: int) -> List[float]:
    """Exponential Moving Average with classic SMA seed.

    Formula: ``EMA[i] = values[i]*k + EMA[i-1]*(1-k)`` with ``k = 2/(period+1)``.
    The series is seeded at index ``period - 1`` with the SMA of the first
    ``period`` values.

    Warm-up policy: the first *valid* EMA value is the seed at index
    ``period - 1`` (``warmup_bars == period - 1``).  Indices ``0..period-2``
    repeat the seed value as a documented carry-over artifact (this matches
    the legacy engine convention and keeps MACD compositions bit-identical);
    consumers must ignore them.
    """
    if period <= 0:
        raise ValueError("ref_ema: period must be >= 1")
    if not values:
        raise ValueError("ref_ema: values must be non-empty")
    n = len(values)
    if n <= period:
        seed = sum(values[:n]) / n
        return [seed] * n
    seed = sum(values[:period]) / period
    out = [seed] * period
    k = 2 / (period + 1)
    prev = seed
    for v in values[period:]:
        prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------
def ref_rsi(closes: List[float], period: int = 14) -> List[float]:
    """Relative Strength Index (Wilder).

    Formula: deltas ``d[i] = closes[i] - closes[i-1]``; ``up[i] = max(d,0)``,
    ``dn[i] = max(-d,0)``.  First averages at index ``period`` are the SMA of
    the first ``period`` deltas; afterwards Wilder smoothing
    ``avg = (prev_avg*(period-1) + next)/period``.
    ``RSI = 100 - 100/(1 + avg_up/avg_dn)``; when ``avg_dn == 0`` the result
    is defined as ``100.0`` (directive §B4 policy; a fully flat window
    therefore also maps to 100.0).

    Warm-up policy: ``0.0`` for every index ``i < period``; the first valid
    value sits at index ``period`` (so ``warmup_bars == period``).
    """
    if period <= 0:
        raise ValueError("ref_rsi: period must be >= 1")
    n = len(closes)
    out = [0.0] * n
    if n <= period:
        return out
    ups: List[float] = []
    dns: List[float] = []
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        ups.append(max(d, 0.0))
        dns.append(max(-d, 0.0))
    avg_up = sum(ups[:period]) / period
    avg_dn = sum(dns[:period]) / period

    def _rsi(au: float, ad: float) -> float:
        if ad == 0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + au / ad)

    out[period] = _rsi(avg_up, avg_dn)
    for i in range(period + 1, n):
        avg_up = (avg_up * (period - 1) + ups[i - 1]) / period
        avg_dn = (avg_dn * (period - 1) + dns[i - 1]) / period
        out[i] = _rsi(avg_up, avg_dn)
    return out


def ref_macd(
    closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, List[float]]:
    """Moving Average Convergence/Divergence.

    Formula: ``macd[i] = EMA_fast(closes)[i] - EMA_slow(closes)[i]``;
    ``signal = EMA_signal(macd)``; ``histogram[i] = macd[i] - signal[i]``.
    EMAs use :func:`ref_ema` semantics (SMA seed).

    Warm-up policy: ``macd`` is valid from index ``slow - 1``; ``signal`` and
    ``histogram`` from index ``slow - 1 + signal - 1``.  Earlier slots are
    seed carry-over artifacts (full-length lists, legacy-engine alignment);
    consumers must ignore indices below ``warmup_bars = slow + signal - 2``.
    """
    if fast <= 0 or slow <= 0 or signal <= 0:
        raise ValueError("ref_macd: periods must be >= 1")
    ef = ref_ema(closes, fast)
    es = ref_ema(closes, slow)
    macd_line = [a - b for a, b in zip(ef, es)]
    sig = ref_ema(macd_line, signal)
    hist = [a - b for a, b in zip(macd_line, sig)]
    return {"macd": macd_line, "signal": sig, "histogram": hist}


# ---------------------------------------------------------------------------
# Volatility / bands
# ---------------------------------------------------------------------------
def ref_bollinger(
    closes: List[float], period: int = 20, mult: float = 2.0
) -> Dict[str, List[float]]:
    """Bollinger Bands (population standard deviation, ddof=0).

    Formula over each window ``W = closes[i-period+1 .. i]``:
    ``mid = mean(W)``; ``sd = sqrt(mean((x - mid)^2))`` (population);
    ``upper = mid + mult*sd``; ``lower = mid - mult*sd``.

    Warm-up policy: ``0.0`` for indices ``i < period - 1``; first valid value
    at index ``period - 1`` (``warmup_bars == period - 1``).
    """
    if period <= 1:
        raise ValueError("ref_bollinger: period must be >= 2")
    if not closes:
        raise ValueError("ref_bollinger: closes must be non-empty")
    n = len(closes)
    mid = [0.0] * n
    upper = [0.0] * n
    lower = [0.0] * n
    for i in range(period - 1, n):
        window = closes[i - period + 1 : i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        sd = var ** 0.5
        mid[i] = mean
        upper[i] = mean + mult * sd
        lower[i] = mean - mult * sd
    return {"upper": upper, "mid": mid, "lower": lower}


def ref_atr(bars: List[dict], period: int = 14) -> List[float]:
    """Average True Range (Wilder).

    Formula: ``TR[0] = h[0] - l[0]``;
    ``TR[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))``.
    ATR is seeded with ``SMA(TR[0..period-1])`` at index ``period - 1`` and
    then Wilder-smoothed: ``ATR[i] = (ATR[i-1]*(period-1) + TR[i]) / period``.

    Warm-up policy: ``0.0`` for indices ``i < period - 1``; first valid value
    at index ``period - 1`` (``warmup_bars == period - 1``, matching the
    legacy engine's first output row).  Requires ``len(bars) >= period``.
    """
    if period <= 0:
        raise ValueError("ref_atr: period must be >= 1")
    n = len(bars)
    out = [0.0] * n
    if n == 0:
        return out
    trs: List[float] = []
    for i in range(n):
        hi, lo = bars[i]["h"], bars[i]["l"]
        if i == 0:
            tr = hi - lo
        else:
            pc = bars[i - 1]["c"]
            tr = max(hi - lo, abs(hi - pc), abs(lo - pc))
        trs.append(tr)
    if n < period:
        return out
    atr_prev = sum(trs[:period]) / period
    out[period - 1] = atr_prev
    for i in range(period, n):
        atr_prev = (atr_prev * (period - 1) + trs[i]) / period
        out[i] = atr_prev
    return out


# ---------------------------------------------------------------------------
# Oscillators on full bars
# ---------------------------------------------------------------------------
def ref_stochastic(
    bars: List[dict], k_period: int = 14, d_period: int = 3, smooth: int = 3
) -> Dict[str, List[float]]:
    """Stochastic Oscillator (%K smoothed, %D).

    Formula: raw ``%K[i] = 100*(c[i] - LL)/(HH - LL)`` where HH/LL are the
    highest high / lowest low of the last ``k_period`` bars (flat window →
    50.0); ``K[i] = mean`` of the raw %K values available in the clipped
    window ``[i-smooth+1 .. i]`` (partial windows allowed during warm-up);
    ``D[i] = mean`` of the last ``d_period`` K values, emitted only once
    ``d_period`` K values exist (divided by ``d_period`` exactly).

    Warm-up policy: ``k`` is ``0.0`` before index ``k_period - 1`` and fully
    smoothed from index ``k_period + smooth - 2``; ``d`` is ``0.0`` before
    index ``k_period + d_period - 2`` (catalog ``warmup_bars``).  The
    partial-window behaviour during warm-up matches the legacy engine so the
    two stay cross-comparable.
    """
    if k_period <= 1 or d_period <= 0 or smooth <= 0:
        raise ValueError("ref_stochastic: periods must be positive (k_period >= 2)")
    n = len(bars)
    k_out = [0.0] * n
    d_out = [0.0] * n
    k_raw: List[float | None] = [None] * n
    for i in range(k_period - 1, n):
        window = bars[i - k_period + 1 : i + 1]
        hh = max(b["h"] for b in window)
        ll = min(b["l"] for b in window)
        rng = hh - ll
        k_raw[i] = 50.0 if rng == 0 else (bars[i]["c"] - ll) / rng * 100.0
    for i in range(n):
        vals = [v for v in k_raw[max(0, i - smooth + 1) : i + 1] if v is not None]
        if vals:
            k_out[i] = sum(vals) / len(vals)
    for i in range(d_period - 1, n):
        vals = [k_out[j] for j in range(i - d_period + 1, i + 1) if j >= k_period - 1]
        if len(vals) >= d_period:
            d_out[i] = sum(vals) / d_period
    return {"k": k_out, "d": d_out}


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------
def ref_obv(bars: List[dict]) -> List[float]:
    """On-Balance Volume (cumulative signed volume).

    Formula: ``OBV[0] = v[0]``; for ``i > 0``: ``OBV[i] = OBV[i-1] + v[i]``
    if ``c[i] > c[i-1]``; ``OBV[i-1] - v[i]`` if ``c[i] < c[i-1]``; otherwise
    unchanged.

    Warm-up policy: none — valid from the first bar (``warmup_bars == 0``).
    """
    if not bars:
        return []
    out: List[float] = []
    prev = 0.0
    for i, b in enumerate(bars):
        v = b["v"]
        if i == 0:
            prev = v
        elif b["c"] > bars[i - 1]["c"]:
            prev += v
        elif b["c"] < bars[i - 1]["c"]:
            prev -= v
        out.append(prev)
    return out


def ref_vwap(bars: List[dict]) -> List[float]:
    """Volume Weighted Average Price (cumulative over the supplied window).

    Formula: ``typical = (h + l + c) / 3``;
    ``VWAP[i] = sum(typical[j]*v[j] for j<=i) / sum(v[j] for j<=i)``.
    Session-anchored: the cumulative sums reset whenever the caller supplies
    a new session slice (declared SESSION_DEPENDENT in the catalog).

    Warm-up policy: none (``warmup_bars == 0``); a bar is emitted for every
    input row, with ``0.0`` only while the cumulative volume is still zero
    (zero-volume leading bars), which consumers must skip.
    """
    out: List[float] = []
    cum_pv = 0.0
    cum_v = 0.0
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3
        v = b["v"]
        cum_pv += tp * v
        cum_v += v
        out.append(cum_pv / cum_v if cum_v > 0 else 0.0)
    return out


# ---------------------------------------------------------------------------
# Market structure / breadth (PKG-F additions, directive §B4)
# ---------------------------------------------------------------------------
def ref_new_high_rate(closes: List[float], lookback: int = 20) -> List[float]:
    """Fraction of the last ``lookback`` bars that are rolling 20-bar highs.

    Formula: bar ``j`` is a rolling high when
    ``closes[j] >= max(closes[j-19 .. j])`` (ties count as highs; the window
    is the fixed 20-bar trailing close window, see ``NEW_HIGH_WINDOW``).
    Output at index ``i`` is ``count / lookback`` where the count runs over
    ``j`` in ``[i-lookback+1 .. i]`` restricted to ``j >= 19``.

    Warm-up policy: ``0.0`` for indices below ``NEW_HIGH_WINDOW - 1 +
    lookback - 1`` (default ``38``) — the 20-bar high test plus the lookback
    fraction window must both be fully available.
    """
    if lookback <= 0:
        raise ValueError("ref_new_high_rate: lookback must be >= 1")
    if not closes:
        raise ValueError("ref_new_high_rate: closes must be non-empty")
    n = len(closes)

    def _is_rolling_high(j: int) -> bool:
        if j < NEW_HIGH_WINDOW - 1:
            return False
        window = closes[j - NEW_HIGH_WINDOW + 1 : j + 1]
        return closes[j] >= max(window)

    first = (NEW_HIGH_WINDOW - 1) + (lookback - 1)
    out = [0.0] * n
    for i in range(first, n):
        cnt = sum(1 for j in range(i - lookback + 1, i + 1) if _is_rolling_high(j))
        out[i] = cnt / lookback
    return out


def ref_advance_decline_line(advances: List[int], declines: List[int]) -> List[int]:
    """Advance-Decline Line (cumulative breadth).

    Formula: ``ADL[i] = ADL[i-1] + advances[i] - declines[i]`` starting from
    ``ADL = 0`` before the first session.

    Breadth inputs differ from OHLCV series: ``advances``/``declines`` are
    two provider-dependent per-session integer counts of advancing and
    declining symbols (hence the catalog entry declares ``series_inputs=[]``,
    ``requires_volume=False`` and carries a ``custom_inputs_doc``).
    Warm-up policy: none (``warmup_bars == 0``).
    """
    if len(advances) != len(declines):
        raise ValueError(
            "ref_advance_decline_line: advances and declines must have equal length"
        )
    out: List[int] = []
    running = 0
    for a, d in zip(advances, declines):
        running += int(a) - int(d)
        out.append(running)
    return out
