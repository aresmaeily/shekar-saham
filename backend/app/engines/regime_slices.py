"""Regime-sliced deterministic evaluation (P3, purely additive).

Corpus loci (2026-10-02 amendment corpus):
- 02_EXECUTION_ROADMAP line 145 ("P3 --- Evaluation and research
  integrity"): the evaluation layer must support "... regime-sliced
  evaluation ..." alongside holdout isolation and multiple-testing
  controls.
- 02_EXECUTION_ROADMAP lines 27-30 ("P3 --- Evaluation Harness").

Design (explicit-in, explicit-out, NO inferred regimes): regime windows are
SUPPLIED BY THE CALLER as explicit ``(label, start_ts, end_ts)`` tuples —
this module never labels a regime from data (no look-ahead, no hidden
model, no discretion). Windows are HALF-OPEN intervals ``[start_ts,
end_ts)``: a bar exactly at ``end_ts`` belongs to the NEXT window, so
touching windows are valid and overlap is impossible by construction
(overlapping declarations are refused).

Closed label vocabulary (documented set, Literal-enforced):
  BULLISH / BEARISH / NEUTRAL / HIGH_VOLATILITY / LOW_VOLATILITY.
Gaps (periods covered by no window) are ALLOWED and REPORTED, never
silently dropped: both windows containing zero bars and bars lying in no
window are surfaced in the report.

Aggregation is a CALLER-SUPPLIED pure function (``report_key_fn``) mapping
a regime's bar slice to a tuple of floats; the module verifies determinism
by invoking it twice and refusing on any difference, and refuses non-finite
or non-numeric aggregates.

No I/O, no network, no wall-clock: timestamps come only from the input
bars and windows. No rounding anywhere. No claim of superiority over any
external system is made or implied anywhere in this module.
"""

from __future__ import annotations

import math
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engines.holdout import HoldoutViolation, require_sorted_unique_bars

#: Closed regime-label vocabulary. Chosen to cover the directional
#: (BULLISH/BEARISH/NEUTRAL) and volatility (HIGH_VOLATILITY/LOW_VOLATILITY)
#: axes named by the P3 charter; extending this set is a deliberate,
#: reviewed change to the Literal below — never a free-form string.
RegimeLabel = Literal[
    "BULLISH",
    "BEARISH",
    "NEUTRAL",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
]

REGIME_LABELS: tuple[str, ...] = (
    "BULLISH",
    "BEARISH",
    "NEUTRAL",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
)


class RegimeSliceViolation(ValueError):
    """Deterministic refusal carrying a machine-readable reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}:{detail}" if detail else reason
        super().__init__(message)


class RegimeWindow(BaseModel):
    """One caller-declared half-open regime window ``[start_ts, end_ts)``."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    label: RegimeLabel
    start_ts: float
    end_ts: float

    @model_validator(mode="after")
    def _ordered(self) -> "RegimeWindow":
        if self.end_ts <= self.start_ts:
            raise ValueError("invalid_window_bounds")
        return self


class RegimeSlice(BaseModel):
    """One regime's bar slice plus its caller-aggregated metric tuple."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    label: RegimeLabel
    start_ts: float
    end_ts: float
    bar_count: int = Field(ge=0)
    first_bar_ts: float | None
    last_bar_ts: float | None
    metrics: tuple[float, ...]
    gap: bool  # True exactly when the window contains zero bars


class RegimeSlicesReport(BaseModel):
    """Frozen report over all windows; gaps and uncovered bars are explicit."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    slices: tuple[RegimeSlice, ...]
    gap_labels: tuple[str, ...] = ()  # windows with zero bars, in report order
    uncovered_bar_count: int = Field(ge=0)  # bars lying in NO window
    uncovered_first_ts: float | None
    uncovered_last_ts: float | None


def _normalize_window(
    window: RegimeWindow | tuple[Any, ...] | Sequence[Any], index: int
) -> RegimeWindow:
    """Accept a RegimeWindow record or an explicit (label, start, end) tuple."""
    if isinstance(window, RegimeWindow):
        return window
    if isinstance(window, (tuple, list)) and len(window) == 3:
        label, start_ts, end_ts = window
        if not isinstance(label, str) or label not in REGIME_LABELS:
            raise RegimeSliceViolation(
                "UNKNOWN_REGIME_LABEL", f"window_index={index} label={label!r}"
            )
        if isinstance(start_ts, bool) or not isinstance(start_ts, (int, float)):
            raise RegimeSliceViolation(
                "REGIME_WINDOW_TS_NOT_NUMERIC", f"window_index={index} start_ts={start_ts!r}"
            )
        if isinstance(end_ts, bool) or not isinstance(end_ts, (int, float)):
            raise RegimeSliceViolation(
                "REGIME_WINDOW_TS_NOT_NUMERIC", f"window_index={index} end_ts={end_ts!r}"
            )
        start = float(start_ts)
        end = float(end_ts)
        if not (math.isfinite(start) and math.isfinite(end)):
            raise RegimeSliceViolation(
                "REGIME_WINDOW_TS_NOT_FINITE", f"window_index={index}"
            )
        if end <= start:
            raise RegimeSliceViolation(
                "INVALID_WINDOW_BOUNDS",
                f"window_index={index} start={start!r} end={end!r}",
            )
        return RegimeWindow(label=label, start_ts=start, end_ts=end)  # type: ignore[arg-type]
    raise RegimeSliceViolation(
        "REGIME_WINDOW_NOT_TUPLE_OR_RECORD", f"window_index={index} value={window!r}"
    )


def _aggregate_deterministically(
    report_key_fn: Any, slice_bars: tuple[Mapping[str, Any], ...]
) -> tuple[float, ...]:
    """Call the caller-supplied pure aggregate twice; refuse any drift.

    The double-call is a determinism GUARD, not a proof: a genuinely pure
    function returns identical tuples and the guard is free; any observed
    drift is refused outright (research results must be reproducible).
    """
    if not callable(report_key_fn):
        raise RegimeSliceViolation("AGGREGATE_NOT_CALLABLE")
    first = report_key_fn(slice_bars)
    second = report_key_fn(slice_bars)
    if first != second:
        raise RegimeSliceViolation("AGGREGATE_NOT_DETERMINISTIC")
    if isinstance(first, tuple):
        values = first
    elif isinstance(first, list):
        values = tuple(first)
    else:
        raise RegimeSliceViolation("AGGREGATE_RETURN_INVALID", repr(type(first)))
    out: list[float] = []
    for position, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RegimeSliceViolation(
                "AGGREGATE_RETURN_INVALID", f"position={position} value={value!r}"
            )
        fv = float(value)
        if not math.isfinite(fv):
            raise RegimeSliceViolation(
                "AGGREGATE_RETURN_NON_FINITE", f"position={position} value={value!r}"
            )
        out.append(fv)
    return tuple(out)


def slice_by_regime(
    regime_windows: Sequence[RegimeWindow | tuple[Any, ...] | Sequence[Any]],
    bars: Sequence[Mapping[str, Any]],
    report_key_fn: Any,
) -> RegimeSlicesReport:
    """Slice bars by caller-declared regime windows and aggregate per regime.

    Parameters
    ----------
    regime_windows:
        Explicit caller-supplied windows, each a ``RegimeWindow`` record or
        a ``(label, start_ts, end_ts)`` tuple with ``label`` from the closed
        vocabulary and ``start_ts < end_ts``. Half-open semantics; the
        input order is irrelevant — the report is ordered by window start.
    bars:
        Backtest-shaped bar mappings (numeric ``"ts"``), strictly
        time-ordered with unique timestamps (checked; refuses otherwise).
    report_key_fn:
        Caller-supplied PURE function ``slice_of_bars -> sequence of
        numbers`` producing the per-regime metric tuple (e.g. mean return,
        volatility). Called exactly twice per non-empty window (equality
        guard); empty windows are never passed to it.

    Returns
    -------
    RegimeSlicesReport
        Per-window slices with bar counts, first/last bar timestamps and
        the aggregated metric tuples; gap windows (zero bars) are reported
        in ``gap_labels`` and bars covered by no window are counted in
        ``uncovered_bar_count`` with their first/last timestamps.

    Refusals (``RegimeSliceViolation`` reason codes): ``NO_REGIME_WINDOWS``,
    ``REGIME_WINDOW_NOT_TUPLE_OR_RECORD``, ``UNKNOWN_REGIME_LABEL``,
    ``REGIME_WINDOW_TS_NOT_NUMERIC``, ``REGIME_WINDOW_TS_NOT_FINITE``,
    ``INVALID_WINDOW_BOUNDS``, ``OVERLAPPING_REGIME_WINDOWS``,
    ``EMPTY_BAR_SEQUENCE``, ``UNSORTED_BARS``, ``DUPLICATE_TIMESTAMPS``,
    ``BAR_TS_MISSING_OR_NON_NUMERIC``, ``BAR_TS_NOT_FINITE``,
    ``AGGREGATE_NOT_CALLABLE``, ``AGGREGATE_NOT_DETERMINISTIC``,
    ``AGGREGATE_RETURN_INVALID``, ``AGGREGATE_RETURN_NON_FINITE``.
    """
    if len(regime_windows) == 0:
        raise RegimeSliceViolation("NO_REGIME_WINDOWS")
    windows = [_normalize_window(w, i) for i, w in enumerate(regime_windows)]
    windows.sort(key=lambda w: (w.start_ts, w.end_ts, w.label))
    for previous, current in zip(windows, windows[1:]):
        if current.start_ts < previous.end_ts:
            raise RegimeSliceViolation(
                "OVERLAPPING_REGIME_WINDOWS",
                f"prev=({previous.label},{previous.start_ts!r},{previous.end_ts!r}) "
                f"cur=({current.label},{current.start_ts!r},{current.end_ts!r})",
            )
    if len(bars) == 0:
        raise RegimeSliceViolation("EMPTY_BAR_SEQUENCE")
    try:
        bar_ts = require_sorted_unique_bars(bars)
    except HoldoutViolation as exc:
        # Uniform refusal type for this module: same reason codes
        # (EMPTY_BAR_SEQUENCE / UNSORTED_BARS / DUPLICATE_TIMESTAMPS /
        # BAR_TS_*), re-wrapped as RegimeSliceViolation.
        raise RegimeSliceViolation(exc.reason, exc.detail) from exc

    slices: list[RegimeSlice] = []
    gap_labels: list[str] = []
    bar_cursor = 0
    n_bars = len(bars)
    for window in windows:
        start_index = bar_cursor
        while start_index < n_bars and bar_ts[start_index] < window.start_ts:
            start_index += 1
        end_index = start_index
        while end_index < n_bars and bar_ts[end_index] < window.end_ts:
            end_index += 1
        slice_bars = tuple(bars[start_index:end_index])
        if len(slice_bars) == 0:
            gap_labels.append(window.label)
            metrics: tuple[float, ...] = ()
            first_ts: float | None = None
            last_ts: float | None = None
        else:
            metrics = _aggregate_deterministically(report_key_fn, slice_bars)
            first_ts = bar_ts[start_index]
            last_ts = bar_ts[end_index - 1]
        slices.append(
            RegimeSlice(
                label=window.label,
                start_ts=window.start_ts,
                end_ts=window.end_ts,
                bar_count=len(slice_bars),
                first_bar_ts=first_ts,
                last_bar_ts=last_ts,
                metrics=metrics,
                gap=len(slice_bars) == 0,
            )
        )
        bar_cursor = end_index

    uncovered_ts = [ts for ts in bar_ts if not any(w.start_ts <= ts < w.end_ts for w in windows)]
    return RegimeSlicesReport(
        slices=tuple(slices),
        gap_labels=tuple(gap_labels),
        uncovered_bar_count=len(uncovered_ts),
        uncovered_first_ts=uncovered_ts[0] if uncovered_ts else None,
        uncovered_last_ts=uncovered_ts[-1] if uncovered_ts else None,
    )
