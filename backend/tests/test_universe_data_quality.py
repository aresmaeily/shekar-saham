"""Tests for app.engines.universe_data_quality (MASTER-RADAR directive Wave 2, §G).

Offline, deterministic, no clock: duplicate/out-of-order detection, invalid
OHLCV counting, stale counting against an INJECTED now, exact missing-interval
math, market-level aggregation, and UNKNOWN honesty defaults.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.domain.instrument_master import TrustClass
from app.engines.universe_data_quality import (
    MAX_EXAMPLES,
    CoverageReport,
    SymbolCoverage,
    audit_symbol_history,
    build_market_coverage,
)

_UTC = timezone.utc


def _bar(ts: int, o: float = 1.0, h: float = 2.0, l: float = 0.5, c: float = 1.5, v: float = 1.0) -> dict:
    return {"ts": ts, "o": o, "h": h, "l": l, "c": c, "v": v}


def _audit(bars: list, **overrides: object) -> SymbolCoverage:
    kwargs: dict = {
        "symbol_id": "TEST:X",
        "max_staleness_seconds": 86400,
        "expected_interval_seconds": 3600,
        "corporate_actions_declared": None,
        "pit_available": None,
    }
    kwargs.update(overrides)
    return audit_symbol_history(bars, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------- duplicates


def test_duplicate_detection_counts_extra_occurrences() -> None:
    bars = [_bar(0), _bar(3600), _bar(3600), _bar(3600), _bar(7200)]
    cov = _audit(bars)
    assert cov.duplicate_bars == 2  # two repeats beyond the first occurrence
    assert cov.out_of_order_bars == 0


def test_duplicate_examples_capped_at_max() -> None:
    bars = [_bar(t) for t in (0, 0, 0, 0, 0, 0, 0)]
    cov = _audit(bars)
    assert cov.duplicate_bars == 6
    assert len(cov.duplicate_examples) == MAX_EXAMPLES


def test_duplicates_are_not_invalid_bars() -> None:
    cov = _audit([_bar(0), _bar(0)])
    assert cov.invalid_bars == 0
    assert cov.valid_history_count == 2


# -------------------------------------------------------------- out-of-order


def test_out_of_order_detection_exact() -> None:
    bars = [_bar(7200), _bar(3600), _bar(0), _bar(10800)]
    cov = _audit(bars)
    assert cov.out_of_order_bars == 2
    assert cov.out_of_order_examples[0] == {"index": 1, "ts": 3600, "prev_ts": 7200}


def test_out_of_order_regression_not_counted_as_duplicate() -> None:
    cov = _audit([_bar(7200), _bar(3600)])
    assert cov.out_of_order_bars == 1
    assert cov.duplicate_bars == 0


# ------------------------------------------------------------- invalid bars


def test_invalid_high_below_low_counted() -> None:
    bars = [_bar(0), {"ts": 3600, "o": 1.0, "h": 0.5, "l": 2.0, "c": 1.0, "v": 1.0}]
    cov = _audit(bars)
    assert cov.invalid_bars == 1
    assert cov.invalid_examples[0]["reason"] == "high_below_low"
    assert cov.valid_history_count == 1


def test_invalid_ohlc_outside_range_counted() -> None:
    bars = [{"ts": 0, "o": 5.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 1.0}]
    cov = _audit(bars)
    assert cov.invalid_bars == 1
    assert cov.invalid_examples[0]["reason"] == "ohlc_outside_high_low_range"


def test_invalid_non_finite_and_non_positive_counted() -> None:
    bars = [
        {"ts": 0, "o": float("nan"), "h": 2.0, "l": 0.5, "c": 1.5, "v": 1.0},
        {"ts": 3600, "o": 0.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 1.0},
        {"ts": 7200, "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": -1.0},
        {"ts": 10800, "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 1.0},
    ]
    cov = _audit(bars)
    assert cov.invalid_bars == 3
    reasons = [e["reason"] for e in cov.invalid_examples]
    assert reasons[0] == "o_not_finite"
    assert reasons[1] == "o_non_positive"
    assert reasons[2] == "volume_negative"
    assert cov.valid_history_count == 1


def test_invalid_bar_examples_capped() -> None:
    bars = [{"ts": i, "o": -1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 1.0} for i in range(0, 3600 * 10, 3600)]
    cov = _audit(bars)
    assert cov.invalid_bars == 10
    assert len(cov.invalid_examples) == MAX_EXAMPLES


def test_missing_keys_counted_not_raised() -> None:
    cov = _audit([{"ts": 0, "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5}])  # no "v"
    assert cov.invalid_bars == 1
    assert cov.invalid_examples[0]["reason"].startswith("missing_keys")


# ------------------------------------------------------------------- staleness


def test_stale_counting_with_injected_now() -> None:
    bars = [_bar(0), _bar(3600), _bar(13600), _bar(86400)]
    cov = _audit(bars, now_ts=100000, max_staleness_seconds=86400)
    assert cov.stale_bars == 2  # ts 0 and 3600 < 100000-86400 = 13600
    assert cov.stale_reference_ts == 100000


def test_stale_without_injected_now_reports_zero_and_not_assessed() -> None:
    cov = _audit([_bar(0), _bar(3600)])
    assert cov.stale_bars == 0
    assert cov.stale_reference_ts is None  # honesty: never assessed, not "fresh"


# ------------------------------------------------------------ missing intervals


def test_missing_interval_exactness() -> None:
    bars = [_bar(t) for t in (0, 3600, 7200, 14400, 18000)]
    cov = _audit(bars, expected_interval_seconds=3600)
    assert cov.missing_intervals == [
        {"start_ts": 10800, "end_ts": 14400, "bars_missing": 1}
    ]


def test_missing_interval_multiple_exact_counts() -> None:
    bars = [_bar(t) for t in (0, 10800, 14400, 43200)]
    cov = _audit(bars, expected_interval_seconds=3600)
    assert cov.missing_intervals == [
        {"start_ts": 3600, "end_ts": 10800, "bars_missing": 2},
        {"start_ts": 18000, "end_ts": 43200, "bars_missing": 7},
    ]


def test_missing_intervals_empty_when_dense() -> None:
    bars = [_bar(t) for t in (0, 3600, 7200)]
    assert _audit(bars).missing_intervals == []


def test_missing_intervals_ignore_duplicate_ts_pairs() -> None:
    bars = [_bar(0), _bar(0), _bar(7200)]
    cov = _audit(bars)
    assert cov.duplicate_bars == 1
    assert cov.missing_intervals == [{"start_ts": 3600, "end_ts": 7200, "bars_missing": 1}]


# ------------------------------------------------------- honesty / defaults


def test_corporate_action_and_pit_unknown_when_none() -> None:
    cov = _audit([_bar(0)])
    assert cov.corporate_action_coverage == "UNKNOWN"
    assert cov.pit_availability == "UNKNOWN"


def test_corporate_action_and_pit_explicit_labels() -> None:
    cov = _audit([_bar(0)], corporate_actions_declared=True, pit_available=False)
    assert cov.corporate_action_coverage == "DECLARED"
    assert cov.pit_availability == "NOT_AVAILABLE"


def test_trust_class_carried_through() -> None:
    cov = _audit([_bar(0)], trust_class=TrustClass.SYNTHETIC.value)
    assert cov.trust_class == "SYNTHETIC"


def test_valid_history_and_dates_math() -> None:
    base = int(datetime(2025, 1, 1, tzinfo=_UTC).timestamp())
    bars = [_bar(base), _bar(base + 3600), _bar(base + 86400 * 2)]
    cov = _audit(bars)
    assert cov.valid_history_count == 3
    assert cov.bar_count == 3
    assert cov.start_date == date(2025, 1, 1)
    assert cov.end_date == date(2025, 1, 3)


def test_empty_history_zeros_and_none_dates() -> None:
    cov = _audit([])
    assert cov.bar_count == 0
    assert cov.valid_history_count == 0
    assert cov.start_date is None and cov.end_date is None
    assert cov.missing_intervals == []


def test_audit_rejects_non_positive_intervals() -> None:
    with pytest.raises(ValueError, match="expected_interval_seconds_must_be_positive"):
        _audit([_bar(0)], expected_interval_seconds=0)
    with pytest.raises(ValueError, match="max_staleness_seconds_must_be_positive"):
        _audit([_bar(0)], max_staleness_seconds=0)


def test_audit_deterministic_repeat() -> None:
    bars = [_bar(0), _bar(3600), _bar(7200), _bar(99999)]
    a = _audit(bars, now_ts=200000)
    b = _audit(bars, now_ts=200000)
    assert a == b


# ------------------------------------------------------ market aggregation


def _fixed_cov(
    symbol_id: str,
    *,
    valid: int = 3,
    start: date | None = date(2025, 1, 1),
    end: date | None = date(2025, 1, 5),
    duplicates: int = 0,
    invalid: int = 0,
    stale: int = 0,
    ca: str = "DECLARED",
    pit: str = "AVAILABLE",
    conflicts: int = 0,
) -> SymbolCoverage:
    return SymbolCoverage(
        symbol_id=symbol_id,
        bar_count=valid,
        valid_history_count=valid,
        start_date=start,
        end_date=end,
        duplicate_bars=duplicates,
        invalid_bars=invalid,
        stale_bars=stale,
        provider_conflicts=conflicts,
        corporate_action_coverage=ca,  # type: ignore[arg-type]
        pit_availability=pit,  # type: ignore[arg-type]
        trust_class="SYNTHETIC",
    )


def test_build_market_coverage_aggregation_math() -> None:
    forex = [
        _fixed_cov("FX:EURUSD", valid=3, duplicates=1, invalid=2, stale=1, start=date(2025, 1, 1), end=date(2025, 1, 3)),
        _fixed_cov("FX:USDJPY", valid=2, invalid=1, start=date(2025, 1, 2), end=date(2025, 1, 5), conflicts=4),
    ]
    reports = build_market_coverage({"FOREX": forex}, {"FOREX": "SYNTHETIC"})
    assert len(reports) == 1
    report = reports[0]
    assert report.market == "FOREX"
    assert report.symbol_count == 2
    assert report.valid_history_count == 5
    assert report.duplicate_bars == 1
    assert report.invalid_bars == 3
    assert report.stale_bars == 1
    assert report.provider_conflicts == 4
    assert report.start_date == date(2025, 1, 1)
    assert report.end_date == date(2025, 1, 5)
    assert report.trust_class == "SYNTHETIC"
    assert report.corporate_action_coverage == "DECLARED"
    assert report.pit_availability == "AVAILABLE"


def test_build_market_coverage_missing_intervals_tagged_with_symbol() -> None:
    cov = _audit([_bar(t) for t in (0, 7200)])
    assert cov.missing_intervals  # one gap guaranteed
    reports = build_market_coverage({"FOREX": [cov]}, {})
    tagged = reports[0].missing_intervals
    assert tagged == [{"symbol_id": "TEST:X", **cov.missing_intervals[0]}]


def test_build_market_coverage_mixed_honesty_labels_unknown() -> None:
    forex = [
        _fixed_cov("FX:A", ca="DECLARED"),
        _fixed_cov("FX:B", ca="UNKNOWN"),
    ]
    report = build_market_coverage({"FOREX": forex}, {})[0]
    assert report.corporate_action_coverage == "UNKNOWN"  # mixed -> never guessed
    assert report.trust_class == "MISSING"  # missing trust entry -> MISSING


def test_build_market_coverage_empty_market() -> None:
    report = build_market_coverage({"FOREX": []}, {"FOREX": "SYNTHETIC"})[0]
    assert report.symbol_count == 0
    assert report.valid_history_count == 0
    assert report.start_date is None and report.end_date is None
    assert report.corporate_action_coverage == "UNKNOWN"


def test_build_market_coverage_sorted_deterministic() -> None:
    reports = build_market_coverage(
        {"FOREX": [_fixed_cov("FX:A")], "IRAN_TSE": [_fixed_cov("IR_TSE:FOLAD")]},
        {},
    )
    assert [r.market for r in reports] == ["FOREX", "IRAN_TSE"]
    assert all(isinstance(r, CoverageReport) for r in reports)
