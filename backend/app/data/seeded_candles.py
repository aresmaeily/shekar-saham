"""seeded_candles.py - WS-10 CH-1 — Deterministic seeded OHLCV generator.

Basis: CH-1 of WS10_CHART_PRO_DIRECTIVE_2026-11-02.md (chart-pro backend).

Determinism contract (hard requirement, verified by tests/test_chart_pro_api.py):
- Every bar's OHLCV is a pure function of md5 digests keyed by
  ``f"{symbol}|{timeframe}|{bar_index}"`` (plus fixed per-symbol bases).
- NO wall-clock input anywhere inside the per-bar derivation. The wall clock is
  consulted exactly once, only to resolve the *default* end_bar_index when the
  caller passes none. Therefore: bar N is identical forever, two calls with the
  same end_bar_index are byte-identical, and a bar's values do not depend on
  which window (count/end_bar_index) it was requested through — overlapping
  windows agree on their shared tail.

Random-walk construction note: the walk maintains ``prev_close`` with
``open = prev_close`` and ``close = open * (1 + inc1 * 0.012)``, but the
carried prev_close is re-anchored per bar from the previous bar's own digest
(``_reference_close``) instead of being an accumulating product. A cumulative
chain anchored at the window start would break the directive's own
overlap-equality stability contract (a bar's value would depend on the
requesting window); the per-bar anchor satisfies every stated contract while
keeping each bar O(1) computable.

Data class: SYNTHETIC only. This module NEVER returns live market data and
must only be served behind an explicit "synthetic-seeded" source label.
"""
from __future__ import annotations

import hashlib
import struct
import time
from typing import Dict, List, Optional, Tuple

from app.data.mock_market import SEED_SYMBOLS

# Directive timeframe grid — same buckets as chart.py v0.8 (tf -> seconds).
TIMEFRAMES: Dict[str, int] = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1D": 86400}

_MIN_COUNT = 50
_MAX_COUNT = 1000

# Step bounds (fixed computation constants — part of the determinism contract).
_STEP_CLOSE = 0.012   # close step: open * (1 + inc1 * 0.012)
_STEP_WICK = 0.004    # wick bound: |inc| * 0.004
_REF_WIGGLE = 0.03    # per-bar reference-close drift bound vs base price
_VOL_SWING = 0.6      # volume: base_vol * (1 + inc4 * 0.6), floor 1

# SEED_SYMBOLS row layout: (l18, l30, cs, pe, eps_base, price, shares_b, bias)
_SEED_L18_INDEX = 0
_SEED_PRICE_INDEX = 5


def _seed_price(symbol: str) -> float:
    """Stable base price: real TSE seed price when l18 matches, else a stable
    pseudo-price in [1000, 1000+900] derived from md5("base|{symbol}")."""
    stripped = symbol.strip()
    for row in SEED_SYMBOLS:
        if row[_SEED_L18_INDEX].strip() == stripped:
            return float(row[_SEED_PRICE_INDEX])
    h = int(hashlib.md5(f"base|{symbol}".encode("utf-8")).hexdigest(), 16)
    return 1000 + (h % 90000) / 100


def _seed_volume(symbol: str) -> int:
    """Stable volume base in the 1e5..9e6 band (same digest style as price)."""
    h = int(hashlib.md5(f"vol|{symbol}".encode("utf-8")).hexdigest(), 16)
    return 100_000 + (h % 8_900_000)


def _increments(symbol: str, timeframe: str, bar_index: int) -> Tuple[float, float, float, float]:
    """Four deterministic increments in [-1, 1) from the bar's own 16-byte md5.

    Digest key is exactly f"{symbol}|{timeframe}|{bar_index}" per the directive;
    unpacked as 4 uint32 and mapped via (v / 2**31 - 1).
    """
    digest = hashlib.md5(f"{symbol}|{timeframe}|{bar_index}".encode("utf-8")).digest()
    u1, u2, u3, u4 = struct.unpack(">IIII", digest)
    return (
        u1 / 2**31 - 1,
        u2 / 2**31 - 1,
        u3 / 2**31 - 1,
        u4 / 2**31 - 1,
    )


def _reference_close(symbol: str, timeframe: str, bar_index: int, base_price: float) -> float:
    """Pure per-bar anchor close for the random walk (window-independent).

    Derived from md5(f"{symbol}|{timeframe}|close|{bar_index}") — distinct salt
    from the OHLC increments so the anchor never correlates with the step.
    """
    digest = hashlib.md5(f"{symbol}|{timeframe}|close|{bar_index}".encode("utf-8")).digest()
    (u,) = struct.unpack(">I", digest[:4])
    inc = u / 2**31 - 1
    return base_price * (1 + inc * _REF_WIGGLE)


def candles_for(symbol: str, timeframe: str, count: int, end_bar_index: Optional[int] = None) -> List[Dict]:
    """Deterministic seeded OHLCV series (SYNTHETIC class only).

    Args:
        symbol: l18 symbol key (known SEED_SYMBOLS l18 -> real seed price band,
            anything else -> stable pseudo-price; unknown symbols never fail).
        timeframe: one of TIMEFRAMES keys ("1m"|"5m"|"15m"|"1h"|"1D").
        count: number of bars; clamped to 50..1000.
        end_bar_index: absolute bar-grid index of the newest bar. When None,
            the current wall-clock bucket int(time.time() // tf_sec) is used
            (the ONLY place wall-clock enters). Passing an explicit index makes
            the output fully frozen forever.

    Returns:
        list of {"time": int, "open": float, "high": float, "low": float,
        "close": float, "volume": int} oldest-first, ``count`` items, with
        ``time = bar_index * tf_sec`` (unix seconds, lightweight-charts
        compatible) and prices rounded to 2 decimals (TSE-like). Float math
        uses a fixed operation order and no random module, so identical calls
        produce byte-identical payloads.
    """
    tf_sec = TIMEFRAMES.get(timeframe)
    if tf_sec is None:
        raise ValueError(f"unsupported timeframe: {timeframe!r} (valid: {sorted(TIMEFRAMES)})")

    end = int(end_bar_index) if end_bar_index is not None else int(time.time() // tf_sec)
    n = max(_MIN_COUNT, min(_MAX_COUNT, int(count)))
    start = end - n + 1

    base_price = _seed_price(symbol)
    base_volume = _seed_volume(symbol)

    # Walk forward from the window start, maintaining prev_close per the
    # directive (open = prev_close). prev_close is re-anchored each bar from
    # the previous bar's own digest, keeping every bar window-independent.
    prev_close = _reference_close(symbol, timeframe, start - 1, base_price)
    out: List[Dict] = []
    for i in range(start, end + 1):
        inc1, inc2, inc3, inc4 = _increments(symbol, timeframe, i)
        o = prev_close
        c = o * (1 + inc1 * _STEP_CLOSE)
        h = max(o, c) * (1 + abs(inc2) * _STEP_WICK)
        low = min(o, c) * (1 - abs(inc3) * _STEP_WICK)
        v = max(1, int(base_volume * (1 + inc4 * _VOL_SWING)))
        out.append(
            {
                "time": i * tf_sec,
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(low, 2),
                "close": round(c, 2),
                "volume": v,
            }
        )
        prev_close = _reference_close(symbol, timeframe, i, base_price)
    return out
