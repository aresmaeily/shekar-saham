"""Per-symbol history audit and market-level coverage reporting (paper).

MASTER-RADAR directive Wave 2, §G (Data Quality Center coverage engine).
Honest scope:

- ``audit_symbol_history`` is a MECHANICAL audit of one bar series: it counts
  duplicates, out-of-order timestamps, structurally invalid bars (missing
  keys, non-finite, non-positive, high<low, OHLC range violations), stale
  bars (against an INJECTED ``now_ts`` — never a wall clock) and mechanically
  detectable missing intervals (via ``session_aware_gaps``). Market-calendar
  and session nuance is the caller's declared concern.
- Honesty fields never guess: ``corporate_actions_declared=None`` ->
  ``UNKNOWN``, ``pit_available=None`` -> ``UNKNOWN``; staleness without an
  injected ``now_ts`` is reported as 0 WITH the explicit note that it was not
  assessable (``stale_reference_ts`` stays None). Provider conflicts are not
  observable from a single series: callers must supply the reconciled count,
  otherwise 0 ("none observed here") is reported.
- Every numeric derived here is reproducible: same inputs -> identical report.
- No I/O, no network, no clock reads, no RNG.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.instrument_master import TrustClass
from app.domain.timeframe_spec import session_aware_gaps

__all__ = [
    "UNIVERSE_DQ_VERSION",
    "MAX_EXAMPLES",
    "CorporateActionCoverage",
    "PitAvailability",
    "SymbolCoverage",
    "CoverageReport",
    "audit_symbol_history",
    "build_market_coverage",
]

UNIVERSE_DQ_VERSION = "UDQ-1.0.0"

MAX_EXAMPLES = 5

CorporateActionCoverage = Literal["DECLARED", "NOT_DECLARED", "UNKNOWN"]
PitAvailability = Literal["AVAILABLE", "NOT_AVAILABLE", "UNKNOWN"]

_BAR_PRICE_KEYS = ("o", "h", "l", "c")


def _valid_ts(value: Any) -> int | None:
    """Integral, finite epoch-seconds or None (unusable for time math)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    if float(value) != int(value):
        return None
    return int(value)


def _structural_reason(bar: Mapping[str, Any]) -> str | None:
    """First structural defect of one bar, or None if structurally valid."""
    missing = [k for k in ("ts", *_BAR_PRICE_KEYS, "v") if k not in bar]
    if missing:
        return f"missing_keys:{','.join(missing)}"
    if _valid_ts(bar["ts"]) is None:
        return "ts_not_int_epoch_seconds"
    for k in (*_BAR_PRICE_KEYS, "v"):
        val = bar[k]
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(float(val)):
            return f"{k}_not_finite"
    if float(bar["v"]) < 0:
        return "volume_negative"
    for k in _BAR_PRICE_KEYS:
        if float(bar[k]) <= 0:
            return f"{k}_non_positive"
    hi, lo = float(bar["h"]), float(bar["l"])
    if hi < lo:
        return "high_below_low"
    if not (lo <= float(bar["o"]) <= hi and lo <= float(bar["c"]) <= hi):
        return "ohlc_outside_high_low_range"
    return None


class SymbolCoverage(BaseModel):
    """Mechanical audit result for ONE symbol's bar history."""

    model_config = ConfigDict(frozen=True)

    symbol_id: str
    bar_count: int = 0
    valid_history_count: int = 0
    start_date: date | None = None
    end_date: date | None = None
    missing_intervals: list[dict[str, int]] = Field(default_factory=list)
    duplicate_bars: int = 0
    duplicate_examples: list[dict[str, Any]] = Field(default_factory=list)
    out_of_order_bars: int = 0
    out_of_order_examples: list[dict[str, Any]] = Field(default_factory=list)
    invalid_bars: int = 0
    invalid_examples: list[dict[str, Any]] = Field(default_factory=list)
    stale_bars: int = 0
    stale_reference_ts: int | None = None
    provider_conflicts: int = 0
    corporate_action_coverage: CorporateActionCoverage = "UNKNOWN"
    pit_availability: PitAvailability = "UNKNOWN"
    trust_class: str = TrustClass.MISSING.value
    max_staleness_seconds: int = 0
    expected_interval_seconds: int = 0


class CoverageReport(BaseModel):
    """Market-level aggregation of per-symbol coverage (§G report row)."""

    model_config = ConfigDict(frozen=True)

    market: str
    symbol_count: int = 0
    valid_history_count: int = 0
    start_date: date | None = None
    end_date: date | None = None
    missing_intervals: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_bars: int = 0
    invalid_bars: int = 0
    stale_bars: int = 0
    provider_conflicts: int = 0
    corporate_action_coverage: CorporateActionCoverage = "UNKNOWN"
    pit_availability: PitAvailability = "UNKNOWN"
    trust_class: str = TrustClass.MISSING.value


def audit_symbol_history(
    bars: Sequence[Mapping[str, Any]],
    *,
    symbol_id: str,
    max_staleness_seconds: int,
    expected_interval_seconds: int,
    corporate_actions_declared: bool | None,
    pit_available: bool | None,
    now_ts: int | None = None,
    trust_class: str = TrustClass.MISSING.value,
    provider_conflicts: int | None = None,
    max_examples: int = MAX_EXAMPLES,
) -> SymbolCoverage:
    """Audit one symbol's bars mechanically; honesty fields stay UNKNOWN/None
    when the corresponding input is None. No clock: staleness requires the
    injected ``now_ts``, otherwise ``stale_bars=0`` with ``stale_reference_ts=None``
    (explicitly "not assessed", not "fresh")."""
    if max_staleness_seconds <= 0:
        raise ValueError("max_staleness_seconds_must_be_positive")
    if expected_interval_seconds <= 0:
        raise ValueError("expected_interval_seconds_must_be_positive")

    valid_count = 0
    invalid_bars = 0
    invalid_examples: list[dict[str, Any]] = []
    duplicate_bars = 0
    duplicate_examples: list[dict[str, Any]] = []
    out_of_order_bars = 0
    out_of_order_examples: list[dict[str, Any]] = []
    ts_seen: set[int] = set()
    valid_ts: list[int] = []
    prev_ts: int | None = None

    for index, bar in enumerate(bars):
        reason = _structural_reason(bar)
        if reason is None:
            valid_count += 1
            ts = _valid_ts(bar["ts"])
            assert ts is not None  # guaranteed by _structural_reason
            valid_ts.append(ts)
            if ts in ts_seen:
                duplicate_bars += 1
                if len(duplicate_examples) < max_examples:
                    duplicate_examples.append({"index": index, "ts": ts})
            ts_seen.add(ts)
            if prev_ts is not None and ts < prev_ts:
                out_of_order_bars += 1
                if len(out_of_order_examples) < max_examples:
                    out_of_order_examples.append({"index": index, "ts": ts, "prev_ts": prev_ts})
            prev_ts = ts
        else:
            invalid_bars += 1
            if len(invalid_examples) < max_examples:
                invalid_examples.append({"index": index, "reason": reason})

    # Mechanical missing-interval math over timestamps (deltas <= 0 skipped
    # inside session_aware_gaps; ordering defects are counted above).
    missing_intervals = (
        session_aware_gaps([{"ts": t} for t in valid_ts], expected_interval_seconds)
        if valid_ts
        else []
    )

    stale_bars = 0
    if now_ts is not None:
        threshold = now_ts - max_staleness_seconds
        stale_bars = sum(1 for t in valid_ts if t < threshold)

    start_date: date | None = None
    end_date: date | None = None
    if valid_ts:
        start_date = datetime.fromtimestamp(min(valid_ts), tz=timezone.utc).date()
        end_date = datetime.fromtimestamp(max(valid_ts), tz=timezone.utc).date()

    return SymbolCoverage(
        symbol_id=symbol_id,
        bar_count=len(bars),
        valid_history_count=valid_count,
        start_date=start_date,
        end_date=end_date,
        missing_intervals=missing_intervals,
        duplicate_bars=duplicate_bars,
        duplicate_examples=duplicate_examples,
        out_of_order_bars=out_of_order_bars,
        out_of_order_examples=out_of_order_examples,
        invalid_bars=invalid_bars,
        invalid_examples=invalid_examples,
        stale_bars=stale_bars,
        stale_reference_ts=now_ts,
        provider_conflicts=0 if provider_conflicts is None else provider_conflicts,
        corporate_action_coverage=_bool_to_literal(
            corporate_actions_declared, "DECLARED", "NOT_DECLARED"
        ),
        pit_availability=_bool_to_literal(pit_available, "AVAILABLE", "NOT_AVAILABLE"),
        trust_class=trust_class,
        max_staleness_seconds=max_staleness_seconds,
        expected_interval_seconds=expected_interval_seconds,
    )


def _bool_to_literal(
    value: bool | None, true_label: str, false_label: str
) -> Any:
    """Map an optional boolean honesty input to its declared label or UNKNOWN."""
    if value is None:
        return "UNKNOWN"
    return true_label if value else false_label


def _aggregate_literal(labels: Sequence[str]) -> Any:
    """Shared literal across symbols, else UNKNOWN (mixed claims never guessed)."""
    distinct = set(labels)
    if len(distinct) == 1:
        return next(iter(distinct))
    return "UNKNOWN"


def build_market_coverage(
    records_by_market: dict[str, list[SymbolCoverage]],
    trust_by_market: dict[str, str],
) -> list[CoverageReport]:
    """Aggregate per-symbol coverage into per-market reports (deterministic
    order: sorted by market name). Missing trust entries default to
    MISSING (never an invented trust claim)."""
    reports: list[CoverageReport] = []
    for market in sorted(records_by_market):
        covers = records_by_market[market]
        dates = [c.start_date for c in covers if c.start_date is not None]
        end_dates = [c.end_date for c in covers if c.end_date is not None]
        flattened_intervals: list[dict[str, Any]] = []
        for cover in covers:
            for interval in cover.missing_intervals:
                flattened_intervals.append({"symbol_id": cover.symbol_id, **interval})
        reports.append(
            CoverageReport(
                market=market,
                symbol_count=len(covers),
                valid_history_count=sum(c.valid_history_count for c in covers),
                start_date=min(dates) if dates else None,
                end_date=max(end_dates) if end_dates else None,
                missing_intervals=flattened_intervals,
                duplicate_bars=sum(c.duplicate_bars for c in covers),
                invalid_bars=sum(c.invalid_bars for c in covers),
                stale_bars=sum(c.stale_bars for c in covers),
                provider_conflicts=sum(c.provider_conflicts for c in covers),
                corporate_action_coverage=_aggregate_literal(
                    [c.corporate_action_coverage for c in covers]
                ),
                pit_availability=_aggregate_literal([c.pit_availability for c in covers]),
                trust_class=trust_by_market.get(market, TrustClass.MISSING.value),
            )
        )
    return reports
