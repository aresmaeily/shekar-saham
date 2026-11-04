"""W3-3AB — hand-computed fixtures for the derived chart constructions.

Every fixture below is built BY HAND on paper (the arithmetic is shown step
by step in the comments) and every expected output is derived BY HAND from
the PINNED conventions documented in app/engines/derived_charts.py — none of
the expected values reuse the code under test. Conventions under test:

- RENKO     : anchor = first close; B = brick; while close >= last_top + B ->
              up brick {open: last_top, close: last_top + B}; while close <=
              last_bottom - B -> down brick {open: last_bottom,
              close: last_bottom - B}; 1-brick reversal; no wicks (high =
              max(o, c), low = min(o, c)); time = completing bar's time.
- RANGE     : forming bar opens at the previous completed close (first bar:
              its own open); completes at the FIRST bar where
              running_high - running_low >= range_size; fresh running
              high/low afterwards; open forming tail is dropped.
- LINEBREAK : first `lines` bars verbatim; then UP bar when C > max(close of
              the last `lines` line bars), DOWN bar when C < min(close of
              them), otherwise absorbed.
- KAGI      : direction "up", extreme = first close; extreme updates first,
              then the reversal check (close <= extreme*(1-r/100) in "up");
              turn point = the pivot extreme at the turning bar; the final
              state's extreme is appended as a terminal point unless it
              already equals the last emitted point.
- PNF       : floor(price/box)*box discretization; first column "up" at the
              first discretized close; every column starts at the triggering
              close; extend-while / switch-at rules as pinned; completed
              column time = the reversal-triggering bar; final open column
              always emitted (time = last bar).

No-look-ahead is verified per construction with prefix-stability: for several
k, constructing from ohlcv[:k] equals the prefix of constructing from the
full series restricted to units whose completing source bar index < k
(identified by the unit's completing-bar time; the times in every fixture are
distinct and increasing). PNF and KAGI need one documented adaptation each:
their TERMINAL emission (final open column / final state extreme) is a
whole-prefix artifact, so the comparison covers completed columns / turn
points (everything but the last unit of each construction), which DO complete
at their own bar. RENKO's prefix test uses the fixed brick_size mode (the
ATR brick size is, by pinned convention, a whole-series parameter); a
dedicated constant-TR fixture shows ATR mode itself is prefix-stable when the
ATR value is invariant across prefixes.

Determinism (two calls -> identical lists), honest refusals (empty input,
1 bar, non-finite prices, invalid params each way), verbatim ``time``
carrying, and the DERIVED_TYPES registry contract are pinned below too.
"""
from __future__ import annotations

import inspect
import math
from typing import Any, Dict, List

import pytest

from app.engines import derived_charts as dc
from app.engines.derived_charts import (
    DERIVED_TYPES,
    kagi_points,
    linebreak_bars,
    pnf_columns,
    range_bars,
    renko_bars,
)

T0 = 1_700_000_000
STEP = 60
TOL = 1e-12  # pinned comparison tolerance (brief): exact or 1e-12


def _t(i: int) -> int:
    return T0 + i * STEP


def _bars(rows: List[tuple], start: int = T0) -> List[Dict[str, Any]]:
    """Explicit (o, h, l, c) rows -> ohlcv dicts on a fixed 60s time grid."""
    return [
        {
            "time": start + i * STEP,
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": 1000,
        }
        for i, (o, h, l, c) in enumerate(rows)
    ]


def _close_series(closes: List[float], start: int = T0) -> List[Dict[str, Any]]:
    """Wrap hand closes: open = previous close (first: itself), ±1 wicks.

    Only the closes drive RENKO (fixed brick) / KAGI / PNF; the wicks are
    decorative but keep every bar a well-formed OHLC dict.
    """
    out: List[Dict[str, Any]] = []
    prev = closes[0]
    for i, c in enumerate(closes):
        out.append(
            {
                "time": start + i * STEP,
                "open": float(prev),
                "high": float(max(prev, c)) + 1.0,
                "low": float(min(prev, c)) - 1.0,
                "close": float(c),
                "volume": 1000,
            }
        )
        prev = c
    return out


def _assert_units(actual: List[Dict[str, Any]], expected: List[Dict[str, Any]]) -> None:
    """Exact structural equality; prices exact-or-1e-12, keys exact."""
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        assert set(got) == set(want), (set(got), set(want))
        for key in want:
            if isinstance(want[key], float):
                assert got[key] == pytest.approx(want[key], abs=TOL), (key, got, want)
            else:
                assert got[key] == want[key], (key, got, want)


# ===========================================================================
# RENKO — fixed brick B = 10 on closes 100, 108, 121, 96, 74, 85
# ===========================================================================
# anchor = 100 (bar 0's close); envelope starts as the point (100, 100).
#   bar1 c=108 : 108 >= 100+10=110? NO   | 108 <= 90? NO      -> absorbed
#   bar2 c=121 : 121 >= 110 -> UP {100 -> 110}, env (100, 110)
#                121 >= 120 -> UP {110 -> 120}, env (110, 120)
#                121 >= 130? NO        (two bricks, both time = t2)
#   bar3 c=96  : 96 >= 130? NO | 96 <= 110-10=100 YES -> DOWN {110 -> 100},
#                env (100, 110); 96 <= 90? NO   (one brick, time = t3)
#   bar4 c=74  : 74 <= 100-10=90 -> DOWN {100 -> 90}, env (90, 100)
#                74 <= 80  -> DOWN {90 -> 80},   env (80, 90)
#                74 <= 70?  NO          (two bricks, both time = t4)
#   bar5 c=85  : 85 >= 90+10=100? NO | 85 <= 70? NO          -> absorbed
RENKO_CLOSES = [100, 108, 121, 96, 74, 85]
RENKO_EXPECTED = [
    {"time": _t(2), "open": 100.0, "high": 110.0, "low": 100.0, "close": 110.0, "direction": "up"},
    {"time": _t(2), "open": 110.0, "high": 120.0, "low": 110.0, "close": 120.0, "direction": "up"},
    {"time": _t(3), "open": 110.0, "high": 110.0, "low": 100.0, "close": 100.0, "direction": "down"},
    {"time": _t(4), "open": 100.0, "high": 100.0, "low": 90.0, "close": 90.0, "direction": "down"},
    {"time": _t(4), "open": 90.0, "high": 90.0, "low": 80.0, "close": 80.0, "direction": "down"},
]


def test_renko_hand_fixture_fixed_brick():
    out = renko_bars(_close_series(RENKO_CLOSES), brick_size=10.0)
    _assert_units(out, RENKO_EXPECTED)
    # first emitted brick direction is "up" (close 110 > open 100) — pinned rule
    assert out[0]["direction"] == "up"
    # a source bar may complete several bricks — all carry that bar's time
    assert [b["time"] for b in out].count(_t(2)) == 2
    assert [b["time"] for b in out].count(_t(3)) == 1
    assert [b["time"] for b in out].count(_t(4)) == 2


def test_renko_first_brick_down_and_no_wicks():
    # anchor = 100; bar1 c=88: 88 <= 100-10=90 -> DOWN {100 -> 90}; 88 <= 80? NO.
    out = renko_bars(_close_series([100, 88]), brick_size=10)
    _assert_units(
        out,
        [{"time": _t(1), "open": 100.0, "high": 100.0, "low": 90.0, "close": 90.0, "direction": "down"}],
    )
    # no-wicks convention: high = max(open, close), low = min(open, close)
    for brick in out:
        assert brick["high"] == max(brick["open"], brick["close"])
        assert brick["low"] == min(brick["open"], brick["close"])


# ---------------------------------------------------------------------------
# RENKO — ATR brick, hand-computed Wilder ATR, period 3
# ---------------------------------------------------------------------------
# rows (o, h, l, c); TR = max(h-l, |h-prev_close|, |l-prev_close|), first TR = h-l:
#   i0 (10,12,8,10)   TR0 = 12-8 = 4
#   i1 (10,15,9,12)   prev_close = 10: TR1 = max(6, |15-10|=5, |9-10|=1) = 6
#   i2 (12,13,10,11)  prev_close = 12: TR2 = max(3, |13-12|=1, |10-12|=2) = 3
#   ATR seed at index period-1 = 2: (4+6+3)/3 = 13/3
#   i3 (11,22,13,20)  prev_close = 11: TR3 = max(9, |22-11|=11, |13-11|=2) = 11
#                     ATR3 = (13/3*2 + 11)/3 = (26/3 + 33/3)/3 = 59/9
#   i4 (20,21,15,18)  prev_close = 20: TR4 = max(6, |21-20|=1, |15-20|=5) = 6
#                     ATR4 = (59/9*2 + 6)/3 = (118/9 + 54/9)/3 = 172/27
# brick B = ATR at the LAST warm-up-complete bar = 172/27 (~6.370370...).
# closes 10, 12, 11, 20, 18 with anchor 10:
#   t1 c=12 : 12 >= 10+172/27 = 442/27 (~16.370)? NO
#   t2 c=11 : NO
#   t3 c=20 : 20 >= 442/27? (20*27=540 >= 442) YES -> UP {10 -> 442/27},
#             env (10, 442/27); 20 >= 614/27 (~22.74)? NO
#   t4 c=18 : 18 >= 22.74? NO | 18 <= 10-172/27 = 98/27 (~3.63)? NO
RENKO_ATR_ROWS = [(10, 12, 8, 10), (10, 15, 9, 12), (12, 13, 10, 11), (11, 22, 13, 20), (20, 21, 15, 18)]


def test_renko_atr_brick_hand_computed():
    out = renko_bars(_bars(RENKO_ATR_ROWS), atr_period=3)
    assert len(out) == 1
    brick = out[0]
    assert brick["time"] == _t(3)
    assert brick["direction"] == "up"
    assert brick["open"] == pytest.approx(10.0, abs=TOL)
    assert brick["close"] == pytest.approx(442.0 / 27.0, abs=TOL)  # 10 + 172/27
    assert brick["high"] == pytest.approx(442.0 / 27.0, abs=TOL)
    assert brick["low"] == pytest.approx(10.0, abs=TOL)


def test_renko_atr_warmup_incomplete_refused():
    # series shorter than atr_period + 1 never completes Wilder warm-up
    with pytest.raises(ValueError, match="warm-up"):
        renko_bars(_bars(RENKO_ATR_ROWS[:5]), atr_period=5)  # 5 bars < 5+1
    with pytest.raises(ValueError, match="warm-up"):
        renko_bars(_bars(RENKO_ATR_ROWS[:2]), atr_period=2)  # 2 bars < 2+1


def test_renko_param_refusals():
    bars = _close_series([100, 108, 121])
    with pytest.raises(ValueError, match="neither"):
        renko_bars(bars)  # brick_size and atr_period both missing
    with pytest.raises(ValueError, match="both"):
        renko_bars(bars, brick_size=10.0, atr_period=14)  # both given
    for bad in (0, -5.0, math.inf, -math.inf, math.nan, "10", True):
        with pytest.raises(ValueError):
            renko_bars(bars, brick_size=bad)
    for bad in (1, 201, 2.5, "3", True, None):
        with pytest.raises(ValueError):
            renko_bars(bars, atr_period=bad)


def test_renko_prefix_stability_fixed_brick():
    ohlcv = _close_series(RENKO_CLOSES)
    full = renko_bars(ohlcv, brick_size=10.0)
    for k in (2, 3, 4, 5):
        first_k_times = {bar["time"] for bar in ohlcv[:k]}
        expected = [unit for unit in full if unit["time"] in first_k_times]
        _assert_units(renko_bars(ohlcv[:k], brick_size=10.0), expected)


# ---------------------------------------------------------------------------
# RENKO — ATR mode is prefix-stable when the ATR value is prefix-invariant
# ---------------------------------------------------------------------------
# Constant-TR construction: bar_i (i>=1) = (prev_close, prev_close+2,
# prev_close-2, close_i) -> TR = max(4, 2, 2) = 4 for EVERY bar (bar0's
# h-l = 4 as well). Wilder ATR(3): seed (4+4+4)/3 = 4, recursion keeps 4 —
# so the ATR brick equals exactly 4.0 on ANY prefix of >= 4 bars.
CONSTANT_TR_CLOSES = [10, 13, 11, 14, 12, 15]


def _constant_tr_bars(closes: List[float]) -> List[Dict[str, Any]]:
    rows = [(float(closes[0]), float(closes[0] + 2), float(closes[0] - 2), float(closes[0]))]
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        rows.append((float(prev), float(prev + 2), float(prev - 2), float(closes[i])))
    return _bars(rows)


def test_renko_atr_constant_tr_prefix_stable():
    ohlcv = _constant_tr_bars(CONSTANT_TR_CLOSES)
    full = renko_bars(ohlcv, atr_period=3)
    # hand check: closes 10,13,11,14,12,15 with B=4 -> only bar3 (c=14) crosses
    _assert_units(
        full,
        [{"time": _t(3), "open": 10.0, "high": 14.0, "low": 10.0, "close": 14.0, "direction": "up"}],
    )
    for k in (4, 5, 6):
        first_k_times = {bar["time"] for bar in ohlcv[:k]}
        expected = [unit for unit in full if unit["time"] in first_k_times]
        _assert_units(renko_bars(ohlcv[:k], atr_period=3), expected)


# ===========================================================================
# RANGE — range_size = 5, explicit (o, h, l, c) rows
# ===========================================================================
#   i0 (100,102,99,101): run (102, 99) range 3 < 5 -> open (forming open = own open 100)
#   i1 (101,103,100,102): run (103, 99) range 4 < 5 -> open
#   i2 (102,106,101,105): run (106, 99) range 7 >= 5 -> COMPLETE
#       {open 100, high 106, low 99, close 105, time t2, up}; next forming open = 105
#   i3 (105,107,104,106): run (107, 104) range 3 < 5 -> open
#   i4 (106,108,103,104): run (108, 103) range 5 >= 5 -> COMPLETE
#       {open 105, high 108, low 103, close 104, time t4, down}; next forming open = 104
#   i5 (104,105,102,103): run (105, 102) range 3 < 5 -> still open -> DROPPED
RANGE_ROWS = [
    (100, 102, 99, 101),
    (101, 103, 100, 102),
    (102, 106, 101, 105),
    (105, 107, 104, 106),
    (106, 108, 103, 104),
    (104, 105, 102, 103),
]


def test_range_hand_fixture():
    out = range_bars(_bars(RANGE_ROWS), range_size=5.0)
    _assert_units(
        out,
        [
            {"time": _t(2), "open": 100.0, "high": 106.0, "low": 99.0, "close": 105.0, "direction": "up"},
            {"time": _t(4), "open": 105.0, "high": 108.0, "low": 103.0, "close": 104.0, "direction": "down"},
        ],
    )


def test_range_first_bar_completion_and_flat():
    # range_size = 2: bar0 (50,51,49,50) has range 2 >= 2 -> completes on the
    # very first bar with ITS OWN open (50); close == open -> "flat".
    # bar1 (50,52,51,52): run (52, 51) range 1 < 2 -> open.
    # bar2 (52,52,49,50): run (52, 49) range 3 >= 2 -> COMPLETE
    #   {open 50, high 52, low 49, close 50, flat} (fresh running extremes).
    out = range_bars(_bars([(50, 51, 49, 50), (50, 52, 51, 52), (52, 52, 49, 50)]), range_size=2.0)
    _assert_units(
        out,
        [
            {"time": _t(0), "open": 50.0, "high": 51.0, "low": 49.0, "close": 50.0, "direction": "flat"},
            {"time": _t(2), "open": 50.0, "high": 52.0, "low": 49.0, "close": 50.0, "direction": "flat"},
        ],
    )


def test_range_prefix_stability():
    ohlcv = _bars(RANGE_ROWS)
    full = range_bars(ohlcv, range_size=5.0)
    for k in (2, 3, 4, 5):
        first_k_times = {bar["time"] for bar in ohlcv[:k]}
        expected = [unit for unit in full if unit["time"] in first_k_times]
        _assert_units(range_bars(ohlcv[:k], range_size=5.0), expected)


def test_range_param_refusals():
    bars = _bars(RANGE_ROWS)
    for bad in (None, 0, -1.0, math.inf, math.nan, "5", True):
        with pytest.raises(ValueError):
            range_bars(bars, range_size=bad)
    with pytest.raises(TypeError):
        range_bars(bars)  # range_size is a required keyword-only argument


# ===========================================================================
# LINEBREAK — lines = 3, explicit seeds
# ===========================================================================
# Seeds (verbatim): L0 (100,104,98,102) up | L1 (102,107,101,106) up |
#                   L2 (106,108,103,104) down.
#   bar3 c=110 : W=[L0,L1,L2] max close 106 -> 110 > 106 -> UP
#       {open min low 98, high max(108, 110)=110, low min(98,110)=98, close 110}
#   bar4 c=108 : W=[L1,L2,U3] max close 110, min close 104 -> absorbed
#   bar5 c=100 : W=[L1,L2,U3] min close 104 -> 100 < 104 -> DOWN
#       {open max high(107,108,110)=110, high max(110,100)=110,
#        low min(110,100)=100, close 100}
#   bar6 c=95  : W=[L2,U3,D5] closes 104,110,100 -> 95 < 100 -> DOWN
#       {open max high(108,110,110)=110, high 110, low 95, close 95}
#   bar7 c=96  : W=[U3,D5,D6] closes 110,100,95 -> absorbed
LINEBREAK_ROWS = [
    (100, 104, 98, 102),
    (102, 107, 101, 106),
    (106, 108, 103, 104),
    (104, 111, 103, 110),
    (110, 112, 107, 108),
    (108, 109, 99, 100),
    (100, 101, 94, 95),
    (95, 97, 95, 96),
]
LINEBREAK_EXPECTED = [
    {"time": _t(0), "open": 100.0, "high": 104.0, "low": 98.0, "close": 102.0, "direction": "up"},
    {"time": _t(1), "open": 102.0, "high": 107.0, "low": 101.0, "close": 106.0, "direction": "up"},
    {"time": _t(2), "open": 106.0, "high": 108.0, "low": 103.0, "close": 104.0, "direction": "down"},
    {"time": _t(3), "open": 98.0, "high": 110.0, "low": 98.0, "close": 110.0, "direction": "up"},
    {"time": _t(5), "open": 110.0, "high": 110.0, "low": 100.0, "close": 100.0, "direction": "down"},
    {"time": _t(6), "open": 110.0, "high": 110.0, "low": 95.0, "close": 95.0, "direction": "down"},
]


def test_linebreak_hand_fixture_lines3():
    out = linebreak_bars(_bars(LINEBREAK_ROWS), lines=3)
    _assert_units(out, LINEBREAK_EXPECTED)
    # default `lines` is 3 — same fixture without the kwarg must agree
    _assert_units(linebreak_bars(_bars(LINEBREAK_ROWS)), LINEBREAK_EXPECTED)


def test_linebreak_lines2_hand_fixture():
    # lines = 2: seeds L0 (10,11,9,10) FLAT (close == open), L1 (10,12,10,11) up.
    #   bar2 c=15 : W=[L0,L1] max close 11 -> UP {open min low 9, high max(12,15)=15, low 9, close 15}
    #   bar3 c=9  : W=[L1,U2] closes 11,15 -> 9 < 11 -> DOWN
    #       {open max high(12,15)=15, high 15, low min(15,9)=9, close 9}
    rows = [(10, 11, 9, 10), (10, 12, 10, 11), (11, 15, 11, 15), (15, 16, 8, 9)]
    out = linebreak_bars(_bars(rows), lines=2)
    _assert_units(
        out,
        [
            {"time": _t(0), "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "direction": "flat"},
            {"time": _t(1), "open": 10.0, "high": 12.0, "low": 10.0, "close": 11.0, "direction": "up"},
            {"time": _t(2), "open": 9.0, "high": 15.0, "low": 9.0, "close": 15.0, "direction": "up"},
            {"time": _t(3), "open": 15.0, "high": 15.0, "low": 9.0, "close": 9.0, "direction": "down"},
        ],
    )


def test_linebreak_seeds_verbatim_and_absorbed():
    bars = _bars(LINEBREAK_ROWS)
    out = linebreak_bars(bars, lines=3)
    # the first `lines` output bars are the source bars VERBATIM (OHLC + time)
    for i in range(3):
        assert out[i]["time"] == bars[i]["time"]
        for key in ("open", "high", "low", "close"):
            assert out[i][key] == bars[i][key]
    # every emitted bar's time is some source bar's time (no minted times)
    source_times = {bar["time"] for bar in bars}
    assert all(unit["time"] in source_times for unit in out)


def test_linebreak_prefix_stability():
    ohlcv = _bars(LINEBREAK_ROWS)
    full = linebreak_bars(ohlcv, lines=3)
    for k in (3, 4, 6, 7):
        first_k_times = {bar["time"] for bar in ohlcv[:k]}
        expected = [unit for unit in full if unit["time"] in first_k_times]
        _assert_units(linebreak_bars(ohlcv[:k], lines=3), expected)


def test_linebreak_param_refusals():
    bars = _bars(LINEBREAK_ROWS)
    for bad in (1, 11, 2.5, "3", True, None):
        with pytest.raises(ValueError):
            linebreak_bars(bars, lines=bad)
    with pytest.raises(ValueError, match="seed"):
        linebreak_bars(bars[:2], lines=3)  # fewer bars than `lines`


# ===========================================================================
# KAGI — reversal_pct = 10, closes 100, 108, 115, 100, 89, 95, 92, 101
# ===========================================================================
# start: up, extreme = 100 (t0)
#   t1 c=108: extreme 108; 108 <= 108*0.9 = 97.2? NO
#   t2 c=115: extreme 115; 115 <= 103.5? NO
#   t3 c=100: extreme stays 115; 100 <= 103.5 -> TURN {t3, 115}; down, extreme=100
#   t4 c=89 : extreme 89; 89 >= 89*1.1 = 97.9? NO
#   t5 c=95 : extreme stays 89; 95 >= 97.9? NO (absorbed)
#   t6 c=92 : extreme stays 89; 92 >= 97.9? NO (absorbed)
#   t7 c=101: extreme stays 89; 101 >= 97.9 -> TURN {t7, 89}; up, extreme=101
# terminal: {t7, 101} != last emitted {t7, 89} (same time, different value)
#           -> appended
KAGI_CLOSES = [100, 108, 115, 100, 89, 95, 92, 101]


def test_kagi_hand_fixture():
    out = kagi_points(_close_series(KAGI_CLOSES), reversal_pct=10.0)
    _assert_units(
        out,
        [
            {"time": _t(3), "value": 115.0},
            {"time": _t(7), "value": 89.0},
            {"time": _t(7), "value": 101.0},
        ],
    )


def test_kagi_no_reversal_terminal_only():
    # monotonic rise: no turn ever fires; the pinned terminal point is the
    # ONLY output — {last bar time, final extreme}.
    out = kagi_points(_close_series([100, 101, 102, 103]), reversal_pct=10.0)
    _assert_units(out, [{"time": _t(3), "value": 103.0}])


def test_kagi_terminal_skip_guard_degenerate_zero():
    # all-zero prices: every bar satisfies the (degenerate) reversal check,
    # so turn points are emitted every bar; the final state's extreme point
    # {t2, 0.0} would DUPLICATE the last emitted point -> correctly skipped.
    out = kagi_points(_close_series([0.0, 0.0, 0.0]), reversal_pct=3.0)
    _assert_units(
        out,
        [{"time": _t(1), "value": 0.0}, {"time": _t(2), "value": 0.0}],
    )


def test_kagi_prefix_stability():
    # Documented adaptation: the terminal point completes at the LAST bar of
    # its own input (a whole-prefix artifact), so the no-look-ahead comparison
    # covers TURN POINTS — points[:-1] on each construction — which complete
    # at their own (turning) bar.
    ohlcv = _close_series(KAGI_CLOSES)
    full = kagi_points(ohlcv, reversal_pct=10.0)
    for k in (2, 3, 5, 7):
        first_k_times = {bar["time"] for bar in ohlcv[:k]}
        expected = [p for p in full[:-1] if p["time"] in first_k_times]
        prefix = kagi_points(ohlcv[:k], reversal_pct=10.0)
        _assert_units(prefix[:-1], expected)


def test_kagi_param_refusals():
    bars = _close_series(KAGI_CLOSES)
    for bad in (0, -3.0, math.inf, math.nan, "3", True, None):
        with pytest.raises(ValueError):
            kagi_points(bars, reversal_pct=bad)


# ===========================================================================
# PNF — box_size = 1.0, reversal_boxes = 3 (integer closes -> exact grid)
# ===========================================================================
# closes 100, 101, 104, 97, 94, 96, 99, 103 (discretization = identity):
#   init: up column [100, 100] at t0
#   t1 c=101: extend top -> 101; switch? 101 <= 100-3=97? NO
#   t2 c=104: extend -> 102, 103, 104; switch? 104 <= 101? NO
#   t3 c=97 : extend? 97 >= 105? NO; switch? 97 <= 104-3=101 YES
#       -> UP column completed {t3, open 100, close 104, high 104, low 100};
#          down column starts [97, 97]
#   t4 c=94 : extend bottom -> 96, 95, 94; switch? 94 >= 97? NO
#   t5 c=96 : extend? NO; switch? 96 >= 94+3=97? NO -> absorbed
#   t6 c=99 : switch? 99 >= 97 YES
#       -> DOWN column completed {t6, open 97, close 94, high 97, low 94};
#          up column starts [99, 99]
#   t7 c=103: extend -> 100..103; end of series
#   final open column {t7, open 99, close 103, high 103, low 99, up}
PNF_CLOSES = [100, 101, 104, 97, 94, 96, 99, 103]


def test_pnf_hand_fixture():
    out = pnf_columns(_close_series(PNF_CLOSES), box_size=1.0, reversal_boxes=3)
    _assert_units(
        out,
        [
            {"time": _t(3), "open": 100.0, "high": 104.0, "low": 100.0, "close": 104.0, "direction": "up"},
            {"time": _t(6), "open": 97.0, "high": 97.0, "low": 94.0, "close": 94.0, "direction": "down"},
            {"time": _t(7), "open": 99.0, "high": 103.0, "low": 99.0, "close": 103.0, "direction": "up"},
        ],
    )


def test_pnf_exact_threshold_switch():
    # closes 100, 103, 100 with rev = 3: bar2's close 100 EQUALS the switch
    # threshold top-3 = 100 -> the pinned <= / >= rules fire ON equality.
    out = pnf_columns(_close_series([100, 103, 100]), box_size=1.0, reversal_boxes=3)
    _assert_units(
        out,
        [
            {"time": _t(2), "open": 100.0, "high": 103.0, "low": 100.0, "close": 103.0, "direction": "up"},
            {"time": _t(2), "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "direction": "down"},
        ],
    )


def test_pnf_floor_discretization():
    # box 2.0: floor(100.9/2)*2 = 100.0, floor(103.7/2)*2 = 102.0,
    #          floor(97.2/2)*2 = 96.0 (floor — NOT rounding to nearest).
    # up column [100 -> 102]; bar2 d=96 <= 102-6=96 (exact) -> switch.
    out = pnf_columns(_close_series([100.9, 103.7, 97.2]), box_size=2.0, reversal_boxes=3)
    _assert_units(
        out,
        [
            {"time": _t(2), "open": 100.0, "high": 102.0, "low": 100.0, "close": 102.0, "direction": "up"},
            {"time": _t(2), "open": 96.0, "high": 96.0, "low": 96.0, "close": 96.0, "direction": "down"},
        ],
    )


def test_pnf_prefix_stability():
    # Documented adaptation: the final still-open column is a whole-prefix
    # artifact (always emitted, time = last input bar), so the no-look-ahead
    # comparison covers COMPLETED columns — units[:-1] on each construction —
    # whose time is their own reversal-triggering bar.
    ohlcv = _close_series(PNF_CLOSES)
    full = pnf_columns(ohlcv, box_size=1.0, reversal_boxes=3)
    for k in (2, 3, 4, 7):
        first_k_times = {bar["time"] for bar in ohlcv[:k]}
        expected = [u for u in full[:-1] if u["time"] in first_k_times]
        prefix = pnf_columns(ohlcv[:k], box_size=1.0, reversal_boxes=3)
        _assert_units(prefix[:-1], expected)


def test_pnf_param_refusals():
    bars = _close_series(PNF_CLOSES)
    for bad in (0, -1.0, math.inf, math.nan, "1", True):
        with pytest.raises(ValueError):
            pnf_columns(bars, box_size=bad)
    for bad in (0, 21, 2.5, "3", True):
        with pytest.raises(ValueError):
            pnf_columns(bars, box_size=1.0, reversal_boxes=bad)


# ===========================================================================
# common contract: determinism, refusals, verbatim time, purity, registry
# ===========================================================================
def test_all_constructions_deterministic():
    bars_lb = _bars(LINEBREAK_ROWS)
    cases = [
        lambda: renko_bars(_close_series(RENKO_CLOSES), brick_size=10.0),
        lambda: renko_bars(_bars(RENKO_ATR_ROWS), atr_period=3),
        lambda: range_bars(_bars(RANGE_ROWS), range_size=5.0),
        lambda: linebreak_bars(bars_lb, lines=3),
        lambda: kagi_points(_close_series(KAGI_CLOSES), reversal_pct=10.0),
        lambda: pnf_columns(_close_series(PNF_CLOSES), box_size=1.0, reversal_boxes=3),
    ]
    for build in cases:
        assert build() == build()  # identical args -> identical lists (== on dicts)


def test_empty_and_single_bar_refused_everywhere():
    one_bar = _close_series([100.0])[:1]
    for build in (
        lambda series: renko_bars(series, brick_size=10.0),
        lambda series: range_bars(series, range_size=5.0),
        lambda series: linebreak_bars(series, lines=2),
        lambda series: kagi_points(series, reversal_pct=3.0),
        lambda series: pnf_columns(series, box_size=1.0, reversal_boxes=3),
    ):
        with pytest.raises(ValueError, match="empty"):
            build([])
        with pytest.raises(ValueError, match="at least 2"):
            build(one_bar)
        with pytest.raises(ValueError):
            build(None)  # not a sequence at all


def test_nonfinite_prices_refused_everywhere():
    base = _close_series([100.0, 105.0, 104.0])
    for key in ("open", "high", "low", "close"):
        for bad in (math.nan, math.inf, -math.inf):
            bars = [dict(bar) for bar in base]
            bars[1][key] = bad
            for build in (
                lambda series: renko_bars(series, brick_size=10.0),
                lambda series: range_bars(series, range_size=5.0),
                lambda series: linebreak_bars(series, lines=2),
                lambda series: kagi_points(series, reversal_pct=3.0),
                lambda series: pnf_columns(series, box_size=1.0, reversal_boxes=3),
            ):
                with pytest.raises(ValueError, match="finite"):
                    build(bars)


def test_time_carried_verbatim():
    # ``time`` is opaque and carried through verbatim — string times pass
    # through untouched (no timestamps are ever minted by the engine).
    bars = [
        {"time": "s0", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
        {"time": "s1", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
        {"time": "s2", "open": 100.0, "high": 112.0, "low": 100.0, "close": 111.0},
    ]
    out = renko_bars(bars, brick_size=10.0)
    assert len(out) == 1
    assert out[0]["time"] == "s2"  # the completing bar's time, verbatim


def test_derived_types_registry_contract():
    assert set(DERIVED_TYPES) == {"RENKO", "RANGE", "KAGI", "PNF", "LINEBREAK"}
    fn_by_name = {
        "RENKO": renko_bars,
        "RANGE": range_bars,
        "KAGI": kagi_points,
        "PNF": pnf_columns,
        "LINEBREAK": linebreak_bars,
    }
    for name, entry in DERIVED_TYPES.items():
        assert entry["fn"] is fn_by_name[name]
        assert isinstance(entry["required_params"], list)
        assert isinstance(entry["optional_params"], list)
        assert not set(entry["required_params"]) & set(entry["optional_params"])
        assert isinstance(entry["doc"], str) and entry["doc"]
    assert DERIVED_TYPES["RANGE"]["required_params"] == ["range_size"]
    assert DERIVED_TYPES["RENKO"]["optional_params"] == ["brick_size", "atr_period"]
    assert DERIVED_TYPES["KAGI"]["optional_params"] == ["reversal_pct"]
    assert DERIVED_TYPES["PNF"]["optional_params"] == ["box_size", "reversal_boxes"]
    assert DERIVED_TYPES["LINEBREAK"]["optional_params"] == ["lines"]


def test_engine_module_pure_stdlib_no_clock_no_random():
    # governance hygiene: the engine imports ONLY stdlib math/typing and
    # contains no clock, randomness, network, filesystem, or dynamic-eval
    # primitive anywhere in its source.
    src = inspect.getsource(dc)
    import_lines = [ln for ln in src.splitlines() if ln.startswith(("import ", "from "))]
    assert import_lines, "sanity: engine module has imports"
    allowed_modules = {"__future__", "math", "typing"}
    for ln in import_lines:
        parts = ln.split()
        module = parts[1] if parts[0] == "from" else parts[1].rstrip(".").split(".")[0]
        assert module in allowed_modules, ln
    for token in (
        "import random",
        "from random",
        "import time",
        "from time",
        "datetime",
        "perf_counter",
        "monotonic",
        "eval(",
        "exec(",
        "compile(",
        "__import__",
        "os.environ",
        "open(",
        "subprocess",
        "socket",
        "urllib",
        "requests",
        "httpx",
    ):
        assert token not in src, token
