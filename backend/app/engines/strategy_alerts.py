"""strategy_alerts.py — MASTER-RADAR WAVE-2 (MR2-A): on-demand alert evaluation.

Evaluates one RSL-1.0.0 strategy condition over one caller-supplied bar
series, ON DEMAND. There is deliberately NO scheduler, NO background loop,
NO worker threads or task loops, NO egress and NO storage here: the caller
decides when (and whether) to invoke :func:`evaluate_condition`; this module
only turns (series, source, optional as_of) into one deterministic result
dict and returns. The strategy source is executed exclusively by the
restricted ``app.engines.strategy_dsl`` interpreter (its own AST walker —
never compiled to Python), so hostile sources stay sandboxed exactly like
everywhere else in the strategy engine.

Semantics of :func:`evaluate_condition` (all documented, deterministic):

- The source is compiled with the strategy-DSL public pipeline
  (parse + typecheck + validate). Compile failures are RETURNED as
  machine-readable error dicts reusing the DSL error shape
  ``{"code", "message", "line", "col"}`` — never raised, never logged.
- ``series`` is a list of bar dicts, oldest first, in either the shared
  contract shape ``{"ts","o","h","l","c","v"}`` or the legacy engine shape
  ``{"time","open","high","low","close","volume"}`` (per-bar alias
  precedence: shared-contract key first). Volume is optional and defaults to
  0.0. Malformed bars are reported, not raised.
- The program runs over the whole series and the result describes the LAST
  CLOSED BAR (the newest supplied bar): ``triggered`` is the program's ENTRY
  decision at that bar (RSL-1's ENTRY section is the strategy's boolean
  condition; EXIT/ALERT sections are not consulted by this evaluator),
  ``last_value`` is the same boolean condition value, ``bar_ts`` the bar's
  timestamp, ``bars_evaluated`` the sweep length, ``program_digest`` the
  DSL's sha256 source digest of the compiled program.
- Staleness refusal: with ``as_of`` (epoch seconds, caller-injected wall
  clock — this module itself never reads any clock) the newest bar must not
  be older than ``STALENESS_WINDOW_BARS`` times the series' median inter-bar
  interval (median of the positive consecutive ``ts`` deltas of the supplied
  series itself; fewer than two bars or no positive deltas give a zero
  window, i.e. any positive age is stale). The refusal happens BEFORE
  compilation and returns ``{"triggered": False, "stale": True, ...}`` with
  ``program_digest=None`` and ``bars_evaluated=0``. Age exactly equal to the
  window is accepted; only a strictly older bar is refused.
- The function is total over its documented inputs: it never raises for bad
  source or bad series, contains no I/O, no network, no logging, no clock
  access, and no dynamic code evaluation primitives.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.engines.strategy_dsl import (
    DSLError,
    SeriesContext,
    compile_source,
    run_over_series,
)

# Staleness window: the newest bar may be at most this many "typical bars"
# old, where one typical bar is the series' own median inter-bar interval.
STALENESS_WINDOW_BARS = 3

# Result-only error codes (machine-readable; the dict SHAPE reuses the DSL
# error shape {"code","message","line","col"}).
_EMPTY_SERIES_CODE = "ALERT_EMPTY_SERIES"
_BAD_SERIES_CODE = "ALERT_BAD_SERIES"

# Bar-dict alias precedence: shared contract keys first, legacy engine keys
# second (same two shapes indicator_reference.py documents).
_FIELD_ALIASES: Dict[str, tuple[str, ...]] = {
    "open": ("o", "open"),
    "high": ("h", "high"),
    "low": ("l", "low"),
    "close": ("c", "close"),
    "volume": ("v", "volume"),
}
_TS_ALIASES: tuple[str, ...] = ("ts", "time")


def _error(code: str, message: str) -> Dict[str, Any]:
    """One machine-readable error in the strategy-DSL error shape."""
    return {"code": code, "message": message, "line": None, "col": None}


def _result(
    *,
    triggered: bool,
    last_value: Optional[bool],
    bar_ts: Optional[int],
    bars_evaluated: int,
    program_digest: Optional[str],
    errors: List[Dict[str, Any]],
    stale: bool = False,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "triggered": triggered,
        "last_value": last_value,
        "bar_ts": bar_ts,
        "bars_evaluated": bars_evaluated,
        "program_digest": program_digest,
        "errors": errors,
    }
    if stale:
        out["stale"] = True
    return out


def _median_interval(stamps: Sequence[int]) -> int:
    """Median of the positive consecutive ts deltas (0 when undefined)."""
    diffs = sorted(
        stamps[i] - stamps[i - 1] for i in range(1, len(stamps)) if stamps[i] > stamps[i - 1]
    )
    if not diffs:
        return 0
    mid = len(diffs) // 2
    if len(diffs) % 2 == 1:
        return int(diffs[mid])
    return int((diffs[mid - 1] + diffs[mid]) // 2)


def _series_arrays(
    series: Sequence[Mapping[str, Any]],
) -> tuple[List[int], Dict[str, List[float]]] | Dict[str, Any]:
    """Extract ts + OHLCV lists, or a single machine-readable error dict."""
    stamps: List[int] = []
    arrays: Dict[str, List[float]] = {name: [] for name in _FIELD_ALIASES}
    for pos, bar in enumerate(series):
        if not isinstance(bar, Mapping):
            return _error(
                _BAD_SERIES_CODE,
                f"bar {pos} is {type(bar).__name__}, expected a mapping of bar fields",
            )
        for name, keys in _FIELD_ALIASES.items():
            value: Any = 0.0  # volume may be omitted; OHLC may not (checked below)
            present = False
            for key in keys:
                if key in bar:
                    value = bar[key]
                    present = True
                    break
            if not present and name != "volume":
                return _error(
                    _BAD_SERIES_CODE,
                    f"bar {pos} lacks a {name!r} value (accepted keys: {', '.join(keys)})",
                )
            try:
                arrays[name].append(float(value))
            except (TypeError, ValueError):
                return _error(
                    _BAD_SERIES_CODE,
                    f"bar {pos} has a non-numeric {name!r} value: {type(value).__name__}",
                )
        try:
            ts_value = bar[_TS_ALIASES[0]] if _TS_ALIASES[0] in bar else bar[_TS_ALIASES[1]]
            stamps.append(int(ts_value))
        except (KeyError, TypeError, ValueError):
            return _error(
                _BAD_SERIES_CODE,
                f"bar {pos} lacks an integer timestamp (accepted keys: "
                f"{', '.join(_TS_ALIASES)})",
            )
    return stamps, arrays


def evaluate_condition(
    source: str,
    series: Sequence[Mapping[str, Any]],
    *,
    as_of: Optional[int] = None,
) -> Dict[str, Any]:
    """Evaluate one RSL-1.0.0 strategy condition over one bar series, on demand.

    Returns the LAST CLOSED BAR result
    ``{"triggered": bool, "last_value": bool|None, "bar_ts": int|None,
    "bars_evaluated": int, "program_digest": str|None, "errors": []}``,
    or a stale refusal ``{"triggered": False, "stale": True, ...}`` when
    ``as_of`` is supplied and the newest bar is strictly older than
    ``STALENESS_WINDOW_BARS * median_interval(series)`` seconds. Compile and
    series-shape failures are returned in ``errors`` using the strategy-DSL
    error shape; this function never raises for such inputs, never touches
    the filesystem/network, reads no clock (``as_of`` is caller-injected),
    and never logs the strategy source.
    """
    if not isinstance(series, Sequence) or isinstance(series, (str, bytes)):
        return _result(
            triggered=False,
            last_value=None,
            bar_ts=None,
            bars_evaluated=0,
            program_digest=None,
            errors=[_error(_BAD_SERIES_CODE, "series must be a sequence of bar mappings")],
        )
    if len(series) == 0:
        return _result(
            triggered=False,
            last_value=None,
            bar_ts=None,
            bars_evaluated=0,
            program_digest=None,
            errors=[_error(_EMPTY_SERIES_CODE, "series must contain at least one bar")],
        )

    extracted = _series_arrays(series)
    if isinstance(extracted, dict):
        return _result(
            triggered=False,
            last_value=None,
            bar_ts=None,
            bars_evaluated=0,
            program_digest=None,
            errors=[extracted],
        )
    stamps, arrays = extracted

    # Staleness gate BEFORE any compilation work (documented refusal order):
    # age strictly greater than window -> refuse, nothing is evaluated.
    last_ts = stamps[-1]
    window = STALENESS_WINDOW_BARS * _median_interval(stamps)
    if as_of is not None and int(as_of) - last_ts > window:
        return _result(
            triggered=False,
            last_value=None,
            bar_ts=last_ts,
            bars_evaluated=0,
            program_digest=None,
            errors=[],
            stale=True,
        )

    if not isinstance(source, str):
        return _result(
            triggered=False,
            last_value=None,
            bar_ts=last_ts,
            bars_evaluated=0,
            program_digest=None,
            errors=[_error("ALERT_BAD_SOURCE", "strategy source must be a string")],
        )

    try:
        program = compile_source(source)
    except DSLError as exc:
        return _result(
            triggered=False,
            last_value=None,
            bar_ts=last_ts,
            bars_evaluated=0,
            program_digest=None,
            errors=[
                {
                    "code": str(exc.code),
                    "message": str(exc.message),
                    "line": exc.line,
                    "col": exc.col,
                }
            ],
        )

    ctx = SeriesContext(
        open=arrays["open"],
        high=arrays["high"],
        low=arrays["low"],
        close=arrays["close"],
        volume=arrays["volume"],
    )
    try:
        decisions = run_over_series(program, ctx)
    except DSLError as exc:
        return _result(
            triggered=False,
            last_value=None,
            bar_ts=last_ts,
            bars_evaluated=0,
            program_digest=None,
            errors=[
                {
                    "code": str(exc.code),
                    "message": str(exc.message),
                    "line": exc.line,
                    "col": exc.col,
                }
            ],
        )

    last = decisions[-1]
    return _result(
        triggered=bool(last.entry),
        last_value=bool(last.entry),
        bar_ts=last_ts,
        bars_evaluated=len(decisions),
        program_digest=program.source_digest,
        errors=[],
    )
