"""
derived_charts.py — MASTER-RADAR W3-3AB — derived chart constructions.

(a) WHAT THESE ARE — and what they are NOT. The five constructions below
(RENKO, RANGE, LINEBREAK, KAGI, PNF) are DERIVED visual-analytic constructions
computed from an input OHLC series. They are NOT real market bars and NOT a
new/independent data source: every output unit is a deterministic re-shaping
of the very bars passed in, inherits their ``time`` values verbatim, and
inherits the input's data class (here: deterministic seeded synthetic bars).
«این سازه‌ها کندل بازار واقعی نیستند و منبع دادهٔ مستقلی هم نیستند؛ فقط بازسازی‌های
قطعی از همان سری ورودی‌اند.»

(b) PINNED CONVENTIONS — fixed BEFORE the test fixtures were derived; each
function's docstring restates its convention exactly and the tests in
tests/test_derived_charts.py pin them against hand-computed arithmetic:

RENKO — anchor = first close; brick size B. A new brick completes when the
  source close reaches beyond the pending boundary by B:
    while close >= last_top + B    -> emit up brick   {open: last_top, close: last_top + B}
    while close <= last_bottom - B -> emit down brick {open: last_bottom, close: last_bottom - B}
  maintaining last_top/last_bottom as the running envelope of the last emitted
  brick (before the first brick the envelope is the degenerate point
  last_top = last_bottom = anchor). Classic 1-brick reversal (no 2-brick
  filter). high = max(open, close), low = min(open, close) (no wicks — renko
  convention). ``time`` = the source bar's ``time`` at which the brick
  completed (a source bar may complete multiple bricks — each emitted brick
  carries that same time). The FIRST brick direction: "up" if its close > open
  else "down". Exactly one of ``brick_size`` (finite > 0) / ``atr_period``
  (int 2..200) must be provided; with ``atr_period`` the brick is the Wilder
  ATR of that period on the source bars (True Range =
  max(h-l, |h-prev_close|, |l-prev_close|); first TR = h-l; seed = mean of the
  first ``atr_period`` TRs, then atr = (prev*(p-1) + TR)/p) taken at the LAST
  warm-up-complete bar (the series' final bar); a series shorter than
  ``atr_period + 1`` bars never completes ATR warm-up -> ValueError.

RANGE — ``range_size`` (finite > 0) required. The forming bar opens at the
  previous completed bar's close (very first bar: its own open); running
  high/low accumulate over source bars while the forming bar is open; the bar
  COMPLETES at the first source bar where running_high - running_low >=
  range_size; the completed bar is {open: forming open, high: running high,
  low: running low, close: that source bar's close, time: that source bar's
  time}; a new forming bar then starts at that close with FRESH running
  high/low (the completing bar's extremes are consumed by the completed bar).
  A still-open forming bar at the end of the input is never emitted
  half-formed. direction = "up" if close > open, "down" if close < open,
  "flat" otherwise.

LINEBREAK — ``lines`` (int 2..10). The first ``lines`` source bars become the
  first ``lines`` line bars VERBATIM (their own OHLC; direction = close vs
  open). Then for each subsequent source bar close C with W = the last
  ``lines`` line bars:
    C > max(close of W) -> UP bar   {open: min(low of W), high: max(high of W, C),
                                     low: min(min(low of W), C), close: C}
    C < min(close of W) -> DOWN bar {open: max(high of W), high: max(max(high of W), C),
                                     low: min(max(high of W), C), close: C}
    otherwise the source bar is absorbed (no new bar).
  Every emitted bar carries the source bar's ``time`` and a ``direction``
  ("up"/"down" for constructed bars, close-vs-open for the verbatim seeds).
  Fewer than ``lines`` bars -> ValueError.

KAGI — ``reversal_pct`` (finite > 0, percent). Track current direction + last
  pivot extreme (start: direction "up", extreme = first close). Walking the
  closes: in "up", extreme = max(extreme, close); if close <= extreme *
  (1 - reversal_pct/100) emit the turn point {time: this bar's time,
  value: extreme} then flip to "down" with extreme = close. Symmetric in
  "down" (extreme = min(extreme, close); turn when close >= extreme *
  (1 + reversal_pct/100)). The FINAL state's extreme is additionally emitted
  as a terminal point {time: last bar time, value: extreme} UNLESS it already
  equals the last emitted point (same time AND value) — this terminal is what
  guarantees even a reversal-free series produces exactly one point.

PNF — ``box_size`` (finite > 0), ``reversal_boxes`` (int 1..20). Prices are
  discretized onto the box grid by floor(price / box_size) * box_size (float
  floor — grid arithmetic, NOT rounding to nearest). The first column is "up"
  and starts at the first discretized close (top = bottom = it); every later
  column also starts at the discretized close that triggered its reversal.
  While "up": the column top extends box-by-box while close >= column_top +
  box_size, and the column switches to "down" when close <= column_top -
  reversal_boxes * box_size; symmetric while "down" (column bottom extends
  while close <= column_bottom - box_size; switch to "up" when close >=
  column_bottom + reversal_boxes * box_size). Each COMPLETED column becomes
  ONE projection bar {time: the source bar whose close triggered the reversal
  that ended the column, open: first price of the column, close: last price of
  the column, high: max of the column, low: min of the column,
  direction: "up"|"down"}; the final still-open column is ALSO emitted, with
  time = last bar time. (In an up column prices only ratchet up, so open = low
  = first price and close = high = top; symmetric for down columns.)

(c) DETERMINISM + NO LOOK-AHEAD — every function is pure: stdlib only
(math + typing), no wall clock, no randomness, no environment access;
identical arguments always produce identical output. Construction state at
any output unit depends only on source bars up to the completing bar (the
walk is strictly forward): renko/range/linebreak units are functions of the
bars up to their completing bar, kagi turn points of bars up to the turn bar,
pnf completed columns of bars up to the reversal-triggering bar. The one
pinned whole-series PARAMETER resolution (not look-ahead in the walk) is
renko's ATR brick size: by convention it is the ATR at the series' last
warm-up-complete bar.

Validation is fail-closed everywhere: every bar must be a dict-like object
with a ``time`` field (carried through verbatim — no timestamps are ever
minted) and finite numeric open/high/low/close (volume is ignored). Empty
input, fewer than 2 usable bars, non-finite numbers and non-positive/invalid
parameters raise ValueError with a clear English message — an honest refusal,
never a silent guess.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

# ---------------------------------------------------------------------------
# shared fail-closed validation helpers (exact ValueError messages, English)
# ---------------------------------------------------------------------------
def _require_finite_number(value: Any, label: str, *, positive: bool = False) -> float:
    """Accept int/float (not bool), require finite (+ strictly positive)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: expected a finite number, got {type(value).__name__}")
    num = float(value)
    if not math.isfinite(num):
        raise ValueError(f"{label}: expected a finite number, got {num!r}")
    if positive and num <= 0:
        raise ValueError(f"{label}: expected a positive number, got {num!r}")
    return num


def _require_bounded_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    """Accept a real int (not bool) inside [minimum, maximum]."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{label}: expected an integer in [{minimum}, {maximum}], got {value!r}"
        )
    if not minimum <= value <= maximum:
        raise ValueError(
            f"{label}: expected an integer in [{minimum}, {maximum}], got {value!r}"
        )
    return value


def _validated_bars(ohlcv: Sequence[Any]) -> List[Dict[str, Any]]:
    """Materialize + validate the input series once, fail-closed.

    Uniform for every construction: open/high/low/close must all be finite
    numbers (even where a construction mathematically consumes only closes);
    ``time`` must merely be present and is carried verbatim (never checked,
    never minted); ``volume`` is ignored.
    """
    try:
        bars = list(ohlcv)
    except TypeError as exc:
        raise ValueError("ohlcv: expected a sequence of dict-like bars") from exc
    if len(bars) == 0:
        raise ValueError("ohlcv is empty: derived constructions need at least 2 usable bars")
    if len(bars) < 2:
        raise ValueError(
            f"ohlcv has {len(bars)} usable bar(s): derived constructions need at least 2"
        )
    out: List[Dict[str, Any]] = []
    for i, bar in enumerate(bars):
        row: Dict[str, Any] = {}
        for key in ("time", "open", "high", "low", "close"):
            try:
                row[key] = bar[key]
            except (KeyError, TypeError, IndexError) as exc:
                raise ValueError(f"bar {i}: missing or unreadable {key!r} field") from exc
        for key in ("open", "high", "low", "close"):
            row[key] = _require_finite_number(row[key], f"bar {i} field {key!r}")
        out.append(row)
    return out


def _wilder_atr_last(bars: List[Dict[str, Any]], period: int) -> float:
    """Wilder ATR of ``period`` on ``bars``, value at the last warm-up bar.

    Same convention as engines.indicators.atr: first TR = h-l; TR[i] =
    max(h-l, |h-prev_close|, |l-prev_close|); seed = mean of the first
    ``period`` TRs (at bar index period-1); then the Wilder recursion
    atr = (prev*(period-1) + TR)/p to the end of the series. Callers
    guarantee len(bars) >= period + 1 (renko_bars enforces it).
    """
    if len(bars) < period + 1:
        raise ValueError(
            f"renko_bars: ATR warm-up incomplete — series has {len(bars)} bar(s), "
            f"Wilder ATR period {period} needs at least {period + 1}"
        )
    trs: List[float] = []
    for i, bar in enumerate(bars):
        if i == 0:
            trs.append(bar["high"] - bar["low"])
        else:
            prev_close = bars[i - 1]["close"]
            trs.append(
                max(
                    bar["high"] - bar["low"],
                    abs(bar["high"] - prev_close),
                    abs(bar["low"] - prev_close),
                )
            )
    atr_value = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_value = (atr_value * (period - 1) + tr) / period
    return atr_value


# ---------------------------------------------------------------------------
# RENKO
# ---------------------------------------------------------------------------
def renko_bars(ohlcv: Sequence[Any], *, brick_size: Any = None, atr_period: Any = None) -> List[Dict[str, Any]]:
    """Renko bricks (pinned convention — see module docstring, section b).

    Exactly one of ``brick_size`` (finite > 0) / ``atr_period`` (int 2..200)
    must be provided; neither or both -> ValueError. With ``atr_period`` the
    brick size is the Wilder ATR of that period at the last warm-up-complete
    bar of the series (see ``_wilder_atr_last``); a series shorter than
    ``atr_period + 1`` bars -> ValueError.

    Returns bricks {time, open, high, low, close, direction: "up"|"down"} in
    completion order; ``time`` is the completing source bar's time verbatim.
    """
    bars = _validated_bars(ohlcv)
    if brick_size is None and atr_period is None:
        raise ValueError(
            "renko_bars: exactly one of brick_size / atr_period must be provided (got neither)"
        )
    if brick_size is not None and atr_period is not None:
        raise ValueError(
            "renko_bars: exactly one of brick_size / atr_period must be provided (got both)"
        )
    if brick_size is not None:
        brick = _require_finite_number(brick_size, "renko_bars brick_size", positive=True)
    else:
        period = _require_bounded_int(atr_period, "renko_bars atr_period", 2, 200)
        brick = _wilder_atr_last(bars, period)

    anchor = bars[0]["close"]
    last_top = anchor
    last_bottom = anchor
    out: List[Dict[str, Any]] = []
    for bar in bars[1:]:
        close = bar["close"]
        while close >= last_top + brick:
            brick_open = last_top
            brick_close = last_top + brick
            out.append(
                {
                    "time": bar["time"],
                    "open": brick_open,
                    "high": brick_close,  # max(open, close) — no wicks
                    "low": brick_open,
                    "close": brick_close,
                    "direction": "up",
                }
            )
            last_bottom, last_top = brick_open, brick_close
        while close <= last_bottom - brick:
            brick_open = last_bottom
            brick_close = last_bottom - brick
            out.append(
                {
                    "time": bar["time"],
                    "open": brick_open,
                    "high": brick_open,  # max(open, close) — no wicks
                    "low": brick_close,
                    "close": brick_close,
                    "direction": "down",
                }
            )
            last_top, last_bottom = brick_open, brick_close
    return out


# ---------------------------------------------------------------------------
# RANGE
# ---------------------------------------------------------------------------
def range_bars(ohlcv: Sequence[Any], *, range_size: Any) -> List[Dict[str, Any]]:
    """Range bars (pinned convention — see module docstring, section b).

    ``range_size`` (finite > 0) is required. The forming bar opens at the
    previous completed bar's close (very first bar: its own open); the bar
    completes at the FIRST source bar where running_high - running_low >=
    range_size and carries that source bar's close and time; the next forming
    bar starts at that close with fresh running high/low. An open forming bar
    at the end of the input is dropped (never emitted half-formed).

    Returns bars {time, open, high, low, close, direction} with direction
    "up" | "down" | "flat" (close vs open).
    """
    bars = _validated_bars(ohlcv)
    size = _require_finite_number(range_size, "range_bars range_size", positive=True)
    out: List[Dict[str, Any]] = []
    forming_open = bars[0]["open"]
    running_high = bars[0]["high"]
    running_low = bars[0]["low"]
    for bar in bars:
        running_high = max(running_high, bar["high"])
        running_low = min(running_low, bar["low"])
        if running_high - running_low >= size:
            close = bar["close"]
            if close > forming_open:
                direction = "up"
            elif close < forming_open:
                direction = "down"
            else:
                direction = "flat"
            out.append(
                {
                    "time": bar["time"],
                    "open": forming_open,
                    "high": running_high,
                    "low": running_low,
                    "close": close,
                    "direction": direction,
                }
            )
            forming_open = close
            running_high = -math.inf  # fresh forming bar: next bar re-seeds both
            running_low = math.inf
    return out


# ---------------------------------------------------------------------------
# LINEBREAK (three-line break, generalized to `lines`)
# ---------------------------------------------------------------------------
def linebreak_bars(ohlcv: Sequence[Any], *, lines: Any = 3) -> List[Dict[str, Any]]:
    """Line-break bars (pinned convention — see module docstring, section b).

    ``lines`` (int 2..10): the first ``lines`` source bars become the first
    ``lines`` line bars verbatim; afterwards a source bar close strictly above
    the max close (below the min close) of the last ``lines`` line bars emits
    one UP (DOWN) line bar, otherwise the bar is absorbed. Fewer than
    ``lines`` bars -> ValueError.

    Returns bars {time, open, high, low, close, direction}; ``time`` is the
    source bar's time verbatim.
    """
    bars = _validated_bars(ohlcv)
    n_lines = _require_bounded_int(lines, "linebreak_bars lines", 2, 10)
    if len(bars) < n_lines:
        raise ValueError(
            f"linebreak_bars: series has {len(bars)} bar(s), needs at least "
            f"lines = {n_lines} seed bars"
        )
    out: List[Dict[str, Any]] = []
    for bar in bars[:n_lines]:  # verbatim seeds
        open_, high_, low_, close_ = bar["open"], bar["high"], bar["low"], bar["close"]
        if close_ > open_:
            direction = "up"
        elif close_ < open_:
            direction = "down"
        else:
            direction = "flat"
        out.append(
            {
                "time": bar["time"],
                "open": open_,
                "high": high_,
                "low": low_,
                "close": close_,
                "direction": direction,
            }
        )
    for bar in bars[n_lines:]:
        close_ = bar["close"]
        window = out[-n_lines:]
        window_max_close = max(b["close"] for b in window)
        window_max_high = max(b["high"] for b in window)
        window_min_low = min(b["low"] for b in window)
        if close_ > window_max_close:
            open_ = window_min_low
            out.append(
                {
                    "time": bar["time"],
                    "open": open_,
                    "high": max(window_max_high, close_),
                    "low": min(open_, close_),
                    "close": close_,
                    "direction": "up",
                }
            )
        elif close_ < min(b["close"] for b in window):
            open_ = window_max_high
            out.append(
                {
                    "time": bar["time"],
                    "open": open_,
                    "high": max(open_, close_),
                    "low": min(open_, close_),
                    "close": close_,
                    "direction": "down",
                }
            )
        # else: absorbed — no new bar
    return out


# ---------------------------------------------------------------------------
# KAGI (turn points)
# ---------------------------------------------------------------------------
def kagi_points(ohlcv: Sequence[Any], *, reversal_pct: Any = 3.0) -> List[Dict[str, Any]]:
    """Kagi turn points (pinned convention — see module docstring, section b).

    ``reversal_pct`` (finite > 0, percent). Start direction "up" with the
    first close as pivot extreme; walk the closes updating/turning exactly as
    pinned, then append the final state's extreme as a terminal point at the
    last bar's time unless it already equals the last emitted point.

    Returns points [{time, value}].
    """
    bars = _validated_bars(ohlcv)
    pct = _require_finite_number(reversal_pct, "kagi_points reversal_pct", positive=True)
    direction = "up"
    extreme = bars[0]["close"]
    out: List[Dict[str, Any]] = []
    for bar in bars[1:]:
        close = bar["close"]
        if direction == "up":
            extreme = max(extreme, close)
            if close <= extreme * (1 - pct / 100.0):
                out.append({"time": bar["time"], "value": extreme})
                direction = "down"
                extreme = close
        else:
            extreme = min(extreme, close)
            if close >= extreme * (1 + pct / 100.0):
                out.append({"time": bar["time"], "value": extreme})
                direction = "up"
                extreme = close
    terminal = {"time": bars[-1]["time"], "value": extreme}
    if out and out[-1]["time"] == terminal["time"] and out[-1]["value"] == terminal["value"]:
        return out  # terminal already present as the last emitted point
    out.append(terminal)
    return out


# ---------------------------------------------------------------------------
# POINT & FIGURE (columns -> one projection bar per column)
# ---------------------------------------------------------------------------
def pnf_columns(ohlcv: Sequence[Any], *, box_size: Any = 1.0, reversal_boxes: Any = 3) -> List[Dict[str, Any]]:
    """Point-and-Figure columns as projection bars (pinned convention — see
    module docstring, section b).

    ``box_size`` (finite > 0), ``reversal_boxes`` (int 1..20). Prices are
    discretized by floor(price / box_size) * box_size; the first column is
    "up" at the first discretized close; extensions/reversals follow the
    pinned box rules; each completed column becomes one projection bar whose
    ``time`` is the reversal-triggering source bar's time; the final
    still-open column is also emitted (time = last bar time).

    Returns bars {time, open, high, low, close, direction: "up"|"down"}.
    """
    bars = _validated_bars(ohlcv)
    box = _require_finite_number(box_size, "pnf_columns box_size", positive=True)
    rev_boxes = _require_bounded_int(reversal_boxes, "pnf_columns reversal_boxes", 1, 20)

    def discretize(price: float) -> float:
        return math.floor(price / box) * box

    direction = "up"
    column_top = discretize(bars[0]["close"])
    column_bottom = column_top
    column_first = column_top
    out: List[Dict[str, Any]] = []
    for bar in bars[1:]:
        price = discretize(bar["close"])
        if direction == "up":
            while price >= column_top + box:
                column_top += box
            if price <= column_top - rev_boxes * box:
                out.append(
                    {
                        "time": bar["time"],  # reversal bar ends the column
                        "open": column_first,
                        "high": column_top,
                        "low": column_first,
                        "close": column_top,
                        "direction": "up",
                    }
                )
                direction = "down"
                column_top = price
                column_bottom = price
                column_first = price
        else:
            while price <= column_bottom - box:
                column_bottom -= box
            if price >= column_bottom + rev_boxes * box:
                out.append(
                    {
                        "time": bar["time"],  # reversal bar ends the column
                        "open": column_first,
                        "high": column_first,
                        "low": column_bottom,
                        "close": column_bottom,
                        "direction": "down",
                    }
                )
                direction = "up"
                column_top = price
                column_bottom = price
                column_first = price
    if direction == "up":  # final still-open column — always emitted
        out.append(
            {
                "time": bars[-1]["time"],
                "open": column_first,
                "high": column_top,
                "low": column_first,
                "close": column_top,
                "direction": "up",
            }
        )
    else:
        out.append(
            {
                "time": bars[-1]["time"],
                "open": column_first,
                "high": column_first,
                "low": column_bottom,
                "close": column_bottom,
                "direction": "down",
            }
        )
    return out


# ---------------------------------------------------------------------------
# registry consumed by the API layer (app.api.chart_pro)
# ---------------------------------------------------------------------------
DERIVED_TYPES: Dict[str, Dict[str, Any]] = {
    "RENKO": {
        "fn": renko_bars,
        "required_params": [],
        "optional_params": ["brick_size", "atr_period"],
        "doc": (
            "Renko bricks; exactly one of brick_size (finite > 0) / atr_period "
            "(int 2..200); when the API receives neither it defaults to "
            "atr_period=14 (Wilder ATR brick at the last warm-up-complete bar)."
        ),
    },
    "RANGE": {
        "fn": range_bars,
        "required_params": ["range_size"],
        "optional_params": [],
        "doc": (
            "Range bars; range_size (finite > 0) REQUIRED — a bar completes at "
            "the first source bar where running high-low >= range_size."
        ),
    },
    "KAGI": {
        "fn": kagi_points,
        "required_params": [],
        "optional_params": ["reversal_pct"],
        "doc": "Kagi turn points; reversal_pct (finite > 0, percent, default 3.0).",
    },
    "PNF": {
        "fn": pnf_columns,
        "required_params": [],
        "optional_params": ["box_size", "reversal_boxes"],
        "doc": (
            "Point-and-Figure columns; box_size (finite > 0, default 1.0), "
            "reversal_boxes (int 1..20, default 3)."
        ),
    },
    "LINEBREAK": {
        "fn": linebreak_bars,
        "required_params": [],
        "optional_params": ["lines"],
        "doc": "Line-break bars; lines (int 2..10, default 3).",
    },
}
