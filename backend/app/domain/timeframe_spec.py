"""Timeframe specification, legality of aggregation, bar labeling and gap math.

MASTER-RADAR directive Wave 2, §B1. Honest scope:

- A ``TimeframeSpec`` is a DECLARED timeframe; the standard table below is a
  fixed, versioned constant. ``1M`` seconds are NOMINAL (2628000): calendar
  month aggregation is calendar-aware, NOT fixed-seconds — this module has no
  declared calendar table, so monthly aggregation is REFUSED, never guessed
  (same philosophy as app/domain/market_calendar.py: unrepresentable != 0).
- THE CORE HONESTY RULE (§B1): producing lower-timeframe bars from
  higher-timeframe data is ILLEGAL — ``assert_aggregation_legal`` fails
  closed with ``lower_timeframe_from_higher_timeframe_forbidden``. Only
  integer-multiple, equal-or-higher targets are legal aggregations.
- ``aggregate_bars`` is pure deterministic OHLCV bucketing over pre-validated
  bars; outputs are re-validated.
- ``session_aware_gaps`` is MECHANICAL interval math only: market-session and
  holiday nuance is the caller's concern (no calendar table here).
- Bar labeling records how a series was produced (native/resampled/synthetic/
  delayed/provider). Nothing here claims real, verified or live data.

Contract/domain only: no I/O, no network, no clock reads — ``now_utc`` is
always injected. Persian strings appear only in user-facing label fields
(``label_fa``).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.evidence import ensure_utc
from app.engines.execution_model import validate_bars

__all__ = [
    "TIMEFRAME_SPEC_VERSION",
    "CUSTOM_TIMEFRAME_MIN_SECONDS",
    "CUSTOM_TIMEFRAME_MAX_SECONDS",
    "TimeframeKind",
    "TimeframeSpec",
    "STANDARD_TIMEFRAMES",
    "TIMEFRAME_BY_CODE",
    "get_standard_timeframe",
    "custom_timeframe",
    "aggregation_legal",
    "assert_aggregation_legal",
    "ResampleLabel",
    "BarLabeling",
    "label_series",
    "aggregate_bars",
    "session_aware_gaps",
]

TIMEFRAME_SPEC_VERSION = "TF-1.0.0"

CUSTOM_TIMEFRAME_MIN_SECONDS = 60
CUSTOM_TIMEFRAME_MAX_SECONDS = 2628000  # nominal month; see module docstring

TimeframeKind = Literal["INTRADAY", "DAILY", "WEEKLY", "MONTHLY", "CUSTOM"]


class TimeframeSpec(BaseModel):
    """Declared timeframe: a code, its nominal seconds and semantic kind."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    seconds: int = Field(gt=0)
    kind: TimeframeKind
    label_fa: str
    label_en: str


# The standard declared table (directive §B1). 1M seconds are NOMINAL only:
# month aggregation is calendar-aware, never fixed-seconds arithmetic.
STANDARD_TIMEFRAMES: tuple[TimeframeSpec, ...] = (
    TimeframeSpec(code="1m", seconds=60, kind="INTRADAY", label_fa="۱ دقیقه", label_en="1 minute"),
    TimeframeSpec(code="5m", seconds=300, kind="INTRADAY", label_fa="۵ دقیقه", label_en="5 minutes"),
    TimeframeSpec(code="15m", seconds=900, kind="INTRADAY", label_fa="۱۵ دقیقه", label_en="15 minutes"),
    TimeframeSpec(code="30m", seconds=1800, kind="INTRADAY", label_fa="۳۰ دقیقه", label_en="30 minutes"),
    TimeframeSpec(code="1h", seconds=3600, kind="INTRADAY", label_fa="۱ ساعت", label_en="1 hour"),
    TimeframeSpec(code="1d", seconds=86400, kind="DAILY", label_fa="روزانه", label_en="1 day"),
    TimeframeSpec(code="1w", seconds=604800, kind="WEEKLY", label_fa="هفتگی", label_en="1 week"),
    TimeframeSpec(
        code="1M",
        seconds=2628000,
        kind="MONTHLY",
        label_fa="ماهانه",
        label_en="1 month (nominal seconds; calendar-aware aggregation required)",
    ),
)

TIMEFRAME_BY_CODE: dict[str, TimeframeSpec] = {tf.code: tf for tf in STANDARD_TIMEFRAMES}


def get_standard_timeframe(code: str) -> TimeframeSpec:
    """Look up a standard timeframe by code; raises ``unknown_timeframe_code``."""
    try:
        return TIMEFRAME_BY_CODE[code]
    except KeyError:
        raise ValueError(f"unknown_timeframe_code:{code}") from None


def custom_timeframe(
    seconds: int,
    *,
    code: str | None = None,
    label_en: str = "custom",
    label_fa: str = "سفارشی",
) -> TimeframeSpec:
    """Declared CUSTOM timeframe bounded to ``60..2628000`` seconds inclusive."""
    if not isinstance(seconds, int) or isinstance(seconds, bool):
        raise ValueError("custom_timeframe_seconds_must_be_int")
    if seconds < CUSTOM_TIMEFRAME_MIN_SECONDS or seconds > CUSTOM_TIMEFRAME_MAX_SECONDS:
        raise ValueError("custom_timeframe_out_of_bounds")
    return TimeframeSpec(
        code=code if code is not None else f"{seconds}s",
        seconds=seconds,
        kind="CUSTOM",
        label_fa=label_fa,
        label_en=label_en,
    )


def aggregation_legal(source: TimeframeSpec, target: TimeframeSpec) -> bool:
    """True iff ``target`` is an integer multiple of ``source`` and >= it.

    THE CORE HONESTY RULE: any target strictly finer than the source is an
    illegal lower-timeframe fabrication from higher-timeframe data.
    """
    return target.seconds % source.seconds == 0 and target.seconds >= source.seconds


def assert_aggregation_legal(source: TimeframeSpec, target: TimeframeSpec) -> None:
    """Fail-closed version of :func:`aggregation_legal`.

    Raises ``ValueError("lower_timeframe_from_higher_timeframe_forbidden")``
    for the illegal direction and ``target_seconds_not_integer_multiple`` for
    non-multiple targets.
    """
    if target.seconds < source.seconds:
        raise ValueError("lower_timeframe_from_higher_timeframe_forbidden")
    if target.seconds % source.seconds != 0:
        raise ValueError("target_seconds_not_integer_multiple_of_source")


class ResampleLabel(str, Enum):
    """How a bar series was produced (trust labeling, directive §B1)."""

    NATIVE = "NATIVE"
    RESAMPLED = "RESAMPLED"
    SYNTHETIC = "SYNTHETIC"
    DELAYED = "DELAYED"
    PROVIDER = "PROVIDER"


class BarLabeling(BaseModel):
    """Per-series provenance label; ``declared_at_utc`` is always injected."""

    model_config = ConfigDict(frozen=True)

    resample_label: ResampleLabel
    source_label: str = ""
    declared_by: str
    declared_at_utc: datetime

    @field_validator("declared_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


def label_series(
    resample_label: ResampleLabel,
    source_label: str = "",
    declared_by: str = "system",
    now_utc: datetime | None = None,
) -> BarLabeling:
    """Build a :class:`BarLabeling`; ``now_utc`` MUST be injected (no clock)."""
    if now_utc is None:
        raise ValueError("now_utc_must_be_injected")
    return BarLabeling(
        resample_label=resample_label,
        source_label=source_label,
        declared_by=declared_by,
        declared_at_utc=ensure_utc(now_utc),
    )


def aggregate_bars(
    bars: Sequence[Mapping[str, Any]],
    source_tf: TimeframeSpec,
    target_tf: TimeframeSpec,
) -> list[dict[str, float]]:
    """Deterministic OHLCV aggregation into ``target_tf`` buckets.

    open=first o, high=max h, low=min l, close=last c, volume=sum v, and the
    bucket's ``ts`` is the bucket start (``ts // target.seconds * target.seconds``).
    Fail-closed: input bars are validated (strictly ascending, finite,
    consistent OHLCV), aggregation must be legal, and MONTHLY targets are
    refused FIRST (``monthly_aggregation_requires_calendar_table`` — the
    honesty policy holds even when nominal seconds would divide: this module
    has no declared calendar table).
    """
    if target_tf.kind == "MONTHLY":
        raise ValueError("monthly_aggregation_requires_calendar_table")
    assert_aggregation_legal(source_tf, target_tf)
    validate_bars(bars)
    if not bars:
        return []
    bucket_seconds = target_tf.seconds
    out: list[dict[str, float]] = []
    current_bucket: int | None = None
    o = h = l = c = 0.0
    v = 0.0
    for bar in bars:
        ts = int(bar["ts"])
        bucket = ts // bucket_seconds * bucket_seconds
        if bucket != current_bucket:
            if current_bucket is not None:
                out.append({"ts": current_bucket, "o": o, "h": h, "l": l, "c": c, "v": v})
            current_bucket = bucket
            o = float(bar["o"])
            h = float(bar["h"])
            l = float(bar["l"])
            c = float(bar["c"])
            v = float(bar["v"])
        else:
            h = max(h, float(bar["h"]))
            l = min(l, float(bar["l"]))
            c = float(bar["c"])
            v += float(bar["v"])
    if current_bucket is not None:
        out.append({"ts": current_bucket, "o": o, "h": h, "l": l, "c": c, "v": v})
    validate_bars(out)  # output re-check: strictly ascending, unique buckets
    return out


def session_aware_gaps(
    bars: Sequence[Mapping[str, Any]],
    expected_interval_seconds: int,
    tolerance: int = 0,
) -> list[dict[str, int]]:
    """Mechanical gap detection between consecutive bar timestamps.

    A gap is any consecutive delta ``d`` with ``d - expected_interval > tolerance``.
    Returns intervals as ``{"start_ts", "end_ts", "bars_missing"}`` where
    ``start_ts`` is the first expected-but-missing slot (``prev_ts + expected``),
    ``end_ts`` is the next observed bar (interval is ``[start_ts, end_ts)``),
    and ``bars_missing = d // expected_interval - 1``. Pairs with
    ``d <= 0`` (duplicates/out-of-order — the auditor's separate concern) are
    skipped; market-calendar nuance is the caller's concern.
    """
    if not isinstance(expected_interval_seconds, int) or expected_interval_seconds <= 0:
        raise ValueError("expected_interval_seconds_must_be_positive_int")
    if not isinstance(tolerance, int) or tolerance < 0:
        raise ValueError("tolerance_must_be_non_negative_int")
    gaps: list[dict[str, int]] = []
    prev_ts: int | None = None
    for bar in bars:
        ts = int(bar["ts"])
        if prev_ts is not None:
            delta = ts - prev_ts
            if delta > 0 and delta - expected_interval_seconds > tolerance:
                gaps.append(
                    {
                        "start_ts": prev_ts + expected_interval_seconds,
                        "end_ts": ts,
                        "bars_missing": delta // expected_interval_seconds - 1,
                    }
                )
        prev_ts = ts
    return gaps
