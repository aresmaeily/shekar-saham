"""Tests for app.domain.timeframe_spec (MASTER-RADAR directive Wave 2, §B1).

Offline and deterministic: the standard timeframe table, custom bounds, the
aggregation-legality matrix (incl. the core honesty rule forbidding
lower-timeframe bars from higher-timeframe data), hand-computed OHLCV
aggregation, monthly refusal, labeling defaults, and exact gap detection.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.timeframe_spec import (
    CUSTOM_TIMEFRAME_MAX_SECONDS,
    CUSTOM_TIMEFRAME_MIN_SECONDS,
    STANDARD_TIMEFRAMES,
    ResampleLabel,
    TimeframeSpec,
    aggregate_bars,
    aggregation_legal,
    assert_aggregation_legal,
    custom_timeframe,
    get_standard_timeframe,
    label_series,
    session_aware_gaps,
)

_UTC = timezone.utc


def _tf(code: str, seconds: int, kind: str = "INTRADAY") -> TimeframeSpec:
    return TimeframeSpec(code=code, seconds=seconds, kind=kind, label_fa="کد", label_en=code)


def _bar(ts: int, o: float, h: float, l: float, c: float, v: float) -> dict:
    return {"ts": ts, "o": o, "h": h, "l": l, "c": c, "v": v}


# ------------------------------------------------------------ standard table


def test_standard_table_codes_and_seconds() -> None:
    assert [(tf.code, tf.seconds) for tf in STANDARD_TIMEFRAMES] == [
        ("1m", 60),
        ("5m", 300),
        ("15m", 900),
        ("30m", 1800),
        ("1h", 3600),
        ("1d", 86400),
        ("1w", 604800),
        ("1M", 2628000),
    ]


def test_standard_table_kinds() -> None:
    kinds = {tf.code: tf.kind for tf in STANDARD_TIMEFRAMES}
    assert kinds == {
        "1m": "INTRADAY",
        "5m": "INTRADAY",
        "15m": "INTRADAY",
        "30m": "INTRADAY",
        "1h": "INTRADAY",
        "1d": "DAILY",
        "1w": "WEEKLY",
        "1M": "MONTHLY",
    }


def test_monthly_entry_carries_nominal_caveat() -> None:
    monthly = get_standard_timeframe("1M")
    assert monthly.kind == "MONTHLY"
    assert "calendar" in monthly.label_en  # documented nominal-seconds caveat


def test_labels_present_bilingual() -> None:
    for tf in STANDARD_TIMEFRAMES:
        assert tf.label_en and tf.label_fa


def test_get_standard_timeframe_unknown_code_raises() -> None:
    with pytest.raises(ValueError, match="unknown_timeframe_code:2m"):
        get_standard_timeframe("2m")


def test_timeframe_spec_frozen() -> None:
    tf = _tf("1m", 60)
    with pytest.raises(ValidationError):
        tf.seconds = 120


# ------------------------------------------------------------ custom bounds


def test_custom_timeframe_ok() -> None:
    tf = custom_timeframe(90)
    assert tf.kind == "CUSTOM" and tf.seconds == 90
    assert tf.code == "90s"


def test_custom_timeframe_bounds_inclusive() -> None:
    assert custom_timeframe(CUSTOM_TIMEFRAME_MIN_SECONDS).seconds == 60
    assert custom_timeframe(CUSTOM_TIMEFRAME_MAX_SECONDS).seconds == 2628000


def test_custom_timeframe_below_bounds_raises() -> None:
    with pytest.raises(ValueError, match="custom_timeframe_out_of_bounds"):
        custom_timeframe(59)


def test_custom_timeframe_above_bounds_raises() -> None:
    with pytest.raises(ValueError, match="custom_timeframe_out_of_bounds"):
        custom_timeframe(2628001)


def test_custom_timeframe_non_int_raises() -> None:
    with pytest.raises(ValueError, match="custom_timeframe_seconds_must_be_int"):
        custom_timeframe(90.5)  # type: ignore[arg-type]


# ------------------------------------------------------- aggregation legality


@pytest.mark.parametrize(
    ("src", "tgt", "expected"),
    [
        ("1m", "5m", True),
        ("1m", "1h", True),
        ("5m", "15m", True),
        ("15m", "1h", True),
        ("1h", "1d", True),
        ("1d", "1w", True),
        ("1h", "1h", True),  # identity aggregation is legal
        ("5m", "1m", False),
        ("1h", "5m", False),
        ("1d", "1h", False),
        ("1w", "1d", False),
    ],
)
def test_aggregation_legal_matrix(src: str, tgt: str, expected: bool) -> None:
    by_code = {tf.code: tf for tf in STANDARD_TIMEFRAMES}
    assert aggregation_legal(by_code[src], by_code[tgt]) is expected


def test_illegal_lower_from_higher_message() -> None:
    one_hour = _tf("1h", 3600)
    five_min = _tf("5m", 300)
    with pytest.raises(ValueError, match="lower_timeframe_from_higher_timeframe_forbidden"):
        assert_aggregation_legal(one_hour, five_min)


def test_non_integer_multiple_raises_distinct_message() -> None:
    with pytest.raises(ValueError, match="target_seconds_not_integer_multiple"):
        assert_aggregation_legal(_tf("5m", 300), _tf("7m", 420))


def test_aggregate_bars_rejects_illegal_direction() -> None:
    with pytest.raises(ValueError, match="lower_timeframe_from_higher_timeframe_forbidden"):
        aggregate_bars([_bar(0, 1, 1, 1, 1, 1)], _tf("1h", 3600), _tf("1m", 60))


# ------------------------------------------------------------ aggregate_bars


def test_aggregate_bars_1h_to_2h_hand_computed() -> None:
    source = _tf("1h", 3600)
    target = _tf("2h", 7200)
    bars = [
        _bar(36000, 100.0, 110.0, 95.0, 105.0, 10.0),  # 10:00Z
        _bar(39600, 105.0, 120.0, 100.0, 115.0, 20.0),  # 11:00Z -> bucket 36000
        _bar(43200, 115.0, 125.0, 90.0, 95.0, 5.0),  # 12:00Z
        _bar(46800, 95.0, 100.0, 85.0, 99.0, 15.0),  # 13:00Z -> bucket 43200
    ]
    out = aggregate_bars(bars, source, target)
    assert out == [
        {"ts": 36000, "o": 100.0, "h": 120.0, "l": 95.0, "c": 115.0, "v": 30.0},
        {"ts": 43200, "o": 115.0, "h": 125.0, "l": 85.0, "c": 99.0, "v": 20.0},
    ]


def test_aggregate_bars_1m_to_5m_partial_last_bucket() -> None:
    bars = [
        _bar(0, 1.0, 2.0, 0.5, 1.5, 1.0),
        _bar(60, 1.5, 3.0, 1.0, 2.5, 2.0),
        _bar(120, 2.5, 2.6, 2.4, 2.55, 3.0),
        _bar(180, 2.55, 2.7, 2.5, 2.6, 4.0),
        _bar(240, 2.6, 2.8, 2.55, 2.7, 5.0),
        _bar(300, 2.7, 2.9, 2.65, 2.8, 6.0),
        _bar(360, 2.8, 3.0, 2.75, 2.9, 7.0),
    ]
    out = aggregate_bars(bars, _tf("1m", 60), _tf("5m", 300))
    assert out == [
        {"ts": 0, "o": 1.0, "h": 3.0, "l": 0.5, "c": 2.7, "v": 15.0},
        {"ts": 300, "o": 2.7, "h": 3.0, "l": 2.65, "c": 2.9, "v": 13.0},
    ]


def test_aggregate_bars_identity_returns_equivalent_series() -> None:
    bars = [_bar(0, 1, 2, 0.5, 1.5, 1), _bar(60, 1.5, 2.5, 1.0, 2.0, 2)]
    out = aggregate_bars(bars, _tf("1m", 60), _tf("1m", 60))
    assert out == bars


def test_aggregate_bars_empty_input() -> None:
    assert aggregate_bars([], _tf("1m", 60), _tf("5m", 300)) == []


def test_aggregate_bars_fail_closed_on_invalid_bar() -> None:
    bad = [_bar(0, 1.0, 2.0, 3.0, 1.5, 1.0)]  # high < low
    with pytest.raises(ValueError):
        aggregate_bars(bad, _tf("1m", 60), _tf("5m", 300))


def test_aggregate_bars_fail_closed_on_out_of_order() -> None:
    with pytest.raises(ValueError):
        aggregate_bars([_bar(60, 1, 2, 0.5, 1.5, 1), _bar(0, 1, 2, 0.5, 1.5, 1)], _tf("1m", 60), _tf("5m", 300))


def test_aggregate_bars_monthly_refused() -> None:
    bars = [_bar(0, 1, 2, 0.5, 1.5, 1)]
    with pytest.raises(ValueError, match="monthly_aggregation_requires_calendar_table"):
        aggregate_bars(bars, _tf("1d", 86400, kind="DAILY"), get_standard_timeframe("1M"))


# ------------------------------------------------------------------ labeling


def test_resample_label_exact_values() -> None:
    assert [e.value for e in ResampleLabel] == [
        "NATIVE",
        "RESAMPLED",
        "SYNTHETIC",
        "DELAYED",
        "PROVIDER",
    ]


def test_label_series_defaults() -> None:
    now = datetime(2026, 1, 1, tzinfo=_UTC)
    labeling = label_series(ResampleLabel.NATIVE, now_utc=now)
    assert labeling.source_label == ""
    assert labeling.declared_by == "system"
    assert labeling.resample_label is ResampleLabel.NATIVE
    assert labeling.declared_at_utc == now


def test_label_series_explicit_fields_and_utc_normalization() -> None:
    now = datetime(2026, 1, 1, 3, 30, tzinfo=timezone.utc)
    labeling = label_series(
        ResampleLabel.RESAMPLED,
        source_label="1m@TSETMC",
        declared_by="PKG-A engine",
        now_utc=now,
    )
    assert labeling.source_label == "1m@TSETMC"
    assert labeling.declared_at_utc == now


def test_label_series_requires_injected_now() -> None:
    with pytest.raises(ValueError, match="now_utc_must_be_injected"):
        label_series(ResampleLabel.NATIVE)


def test_label_series_rejects_naive_now() -> None:
    with pytest.raises(ValueError):
        label_series(ResampleLabel.NATIVE, now_utc=datetime(2026, 1, 1))


def test_bar_labeling_frozen() -> None:
    labeling = label_series(ResampleLabel.SYNTHETIC, now_utc=datetime(2026, 1, 1, tzinfo=_UTC))
    with pytest.raises(ValidationError):
        labeling.resample_label = ResampleLabel.NATIVE  # type: ignore[misc]


# ------------------------------------------------------------------- gaps


def test_gap_detection_single_gap_exact() -> None:
    bars = [_bar(t, 1, 2, 0.5, 1.5, 1) for t in (0, 3600, 7200, 14400, 18000)]
    gaps = session_aware_gaps(bars, 3600)
    assert gaps == [{"start_ts": 10800, "end_ts": 14400, "bars_missing": 1}]


def test_gap_detection_no_gaps() -> None:
    bars = [_bar(t, 1, 2, 0.5, 1.5, 1) for t in (0, 3600, 7200)]
    assert session_aware_gaps(bars, 3600) == []


def test_gap_detection_empty_and_single_bar() -> None:
    assert session_aware_gaps([], 3600) == []
    assert session_aware_gaps([_bar(0, 1, 2, 0.5, 1.5, 1)], 3600) == []


def test_gap_detection_tolerance_absorbs_jitter() -> None:
    # delta == expected + tolerance -> NOT a gap; one second more -> gap.
    bars_ok = [_bar(0, 1, 2, 0.5, 1.5, 1), _bar(3610, 1, 2, 0.5, 1.5, 1)]
    assert session_aware_gaps(bars_ok, 3600, tolerance=10) == []
    bars_over = [_bar(0, 1, 2, 0.5, 1.5, 1), _bar(3611, 1, 2, 0.5, 1.5, 1)]
    gaps = session_aware_gaps(bars_over, 3600, tolerance=10)
    assert len(gaps) == 1 and gaps[0]["bars_missing"] == 0


def test_gap_detection_multiple_gaps_counts() -> None:
    ts = [0, 3600, 10800, 14400, 28800]
    bars = [_bar(t, 1, 2, 0.5, 1.5, 1) for t in ts]
    gaps = session_aware_gaps(bars, 3600)
    assert [(g["start_ts"], g["end_ts"], g["bars_missing"]) for g in gaps] == [
        (7200, 10800, 1),  # delta 7200 -> one missing slot
        (18000, 28800, 3),  # delta 14400 -> three missing slots
    ]


def test_gap_detection_skips_non_positive_deltas() -> None:
    bars = [_bar(0, 1, 2, 0.5, 1.5, 1), _bar(0, 1, 2, 0.5, 1.5, 1), _bar(7200, 1, 2, 0.5, 1.5, 1)]
    gaps = session_aware_gaps(bars, 3600)
    # delta 0 skipped; delta 7200 from the duplicate's ts -> one gap
    assert gaps == [{"start_ts": 3600, "end_ts": 7200, "bars_missing": 1}]


def test_gap_detection_invalid_params() -> None:
    bars = [_bar(0, 1, 2, 0.5, 1.5, 1)]
    with pytest.raises(ValueError, match="expected_interval_seconds_must_be_positive"):
        session_aware_gaps(bars, 0)
    with pytest.raises(ValueError, match="tolerance_must_be_non_negative"):
        session_aware_gaps(bars, 3600, tolerance=-1)
