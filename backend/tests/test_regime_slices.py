"""Tests for app.engines.regime_slices (caller-declared regime evaluation).

Expected slice memberships, half-open boundary behavior, gap reporting and
aggregates are hand-derived from the declared windows.
"""

import pytest
from pydantic import ValidationError

from app.engines.regime_slices import (
    RegimeSlice,
    RegimeSliceViolation,
    RegimeSlicesReport,
    RegimeWindow,
    slice_by_regime,
)


def _bars(count: int, start: int = 1) -> list[dict]:
    return [{"ts": i, "pl": 100.0 + i} for i in range(start, start + count)]


def _sum_close(slice_bars) -> tuple[float]:
    return (sum(b["pl"] for b in slice_bars),)


def test_slice_two_windows_basic_membership():
    bars = _bars(10)  # ts 1..10
    report = slice_by_regime(
        [("BULLISH", 0, 6), ("BEARISH", 6, 11)], bars, _sum_close
    )
    assert [(s.label, s.bar_count) for s in report.slices] == [("BULLISH", 5), ("BEARISH", 5)]
    bullish, bearish = report.slices
    assert (bullish.first_bar_ts, bullish.last_bar_ts) == (1.0, 5.0)
    assert (bearish.first_bar_ts, bearish.last_bar_ts) == (6.0, 10.0)
    # Hand-computed aggregates (pl = 100 + ts):
    # BULLISH ts 1..5 -> 101+102+103+104+105 = 515 ; BEARISH ts 6..10 -> 106+...+110 = 540.
    assert bullish.metrics == (515.0,)
    assert bearish.metrics == (540.0,)
    assert report.gap_labels == ()
    assert report.uncovered_bar_count == 0


def test_half_open_boundaries_bar_at_end_belongs_to_next_window():
    bars = [{"ts": 5}, {"ts": 10}]
    report = slice_by_regime(
        [("NEUTRAL", 0, 10), ("HIGH_VOLATILITY", 10, 20)], bars, lambda s: (len(s),)
    )
    neutral, high_vol = report.slices
    assert neutral.bar_count == 1 and neutral.first_bar_ts == 5.0
    assert high_vol.bar_count == 1 and high_vol.first_bar_ts == 10.0


def test_gap_window_is_allowed_and_reported():
    bars = _bars(4)  # ts 1..4 — no bars fall into the second window
    report = slice_by_regime(
        [("BULLISH", 0, 3), ("BEARISH", 20, 30)], bars, _sum_close
    )
    bullish, bearish = report.slices
    # Half-open [0, 3) covers ts 1 and 2 only.
    assert (bullish.bar_count, bullish.gap) == (2, False)
    assert bullish.metrics == (101.0 + 102.0,)
    assert (bearish.bar_count, bearish.gap) == (0, True)
    assert bearish.metrics == ()
    assert bearish.first_bar_ts is None and bearish.last_bar_ts is None
    assert report.gap_labels == ("BEARISH",)
    # ts 3 and 4 lie in NO declared window: uncovered bars are reported,
    # never silently dropped.
    assert report.uncovered_bar_count == 2
    assert (report.uncovered_first_ts, report.uncovered_last_ts) == (3.0, 4.0)


def test_bars_outside_all_windows_are_reported():
    bars = _bars(5)  # ts 1..5 ; window only covers [2, 4)
    report = slice_by_regime([("BULLISH", 2, 4)], bars, _sum_close)
    (bullish,) = report.slices
    assert bullish.bar_count == 2  # ts 2 and 3
    assert report.uncovered_bar_count == 3
    assert (report.uncovered_first_ts, report.uncovered_last_ts) == (1.0, 5.0)


def test_overlapping_windows_refused():
    with pytest.raises(RegimeSliceViolation, match="OVERLAPPING_REGIME_WINDOWS"):
        slice_by_regime([("BULLISH", 0, 6), ("BEARISH", 5, 9)], _bars(10), _sum_close)


def test_touching_windows_are_valid_half_open():
    report = slice_by_regime(
        [("BULLISH", 0, 5), ("BEARISH", 5, 11)], _bars(10), lambda s: (len(s),)
    )
    assert [(s.label, s.bar_count) for s in report.slices] == [("BULLISH", 4), ("BEARISH", 6)]


def test_invalid_window_bounds_refused():
    with pytest.raises(RegimeSliceViolation, match="INVALID_WINDOW_BOUNDS"):
        slice_by_regime([("BULLISH", 6, 6)], _bars(10), _sum_close)
    with pytest.raises(RegimeSliceViolation, match="INVALID_WINDOW_BOUNDS"):
        slice_by_regime([("BULLISH", 7, 6)], _bars(10), _sum_close)


def test_unknown_label_refused():
    with pytest.raises(RegimeSliceViolation, match="UNKNOWN_REGIME_LABEL"):
        slice_by_regime([("PUMP", 0, 5)], _bars(10), _sum_close)


def test_non_numeric_window_ts_refused():
    with pytest.raises(RegimeSliceViolation, match="REGIME_WINDOW_TS_NOT_NUMERIC"):
        slice_by_regime([("BULLISH", "0", 5)], _bars(10), _sum_close)
    with pytest.raises(RegimeSliceViolation, match="REGIME_WINDOW_TS_NOT_NUMERIC"):
        slice_by_regime([("BULLISH", 0, None)], _bars(10), _sum_close)


def test_no_windows_refused():
    with pytest.raises(RegimeSliceViolation, match="NO_REGIME_WINDOWS"):
        slice_by_regime([], _bars(10), _sum_close)


def test_window_shape_refused():
    with pytest.raises(RegimeSliceViolation, match="REGIME_WINDOW_NOT_TUPLE_OR_RECORD"):
        slice_by_regime(["BULLISH"], _bars(10), _sum_close)


def test_bar_sequence_integrity_refusals():
    with pytest.raises(RegimeSliceViolation, match="EMPTY_BAR_SEQUENCE"):
        slice_by_regime([("BULLISH", 0, 5)], [], _sum_close)
    with pytest.raises(RegimeSliceViolation, match="UNSORTED_BARS"):
        slice_by_regime([("BULLISH", 0, 5)], [{"ts": 3}, {"ts": 1}], _sum_close)
    with pytest.raises(RegimeSliceViolation, match="DUPLICATE_TIMESTAMPS"):
        slice_by_regime([("BULLISH", 0, 5)], [{"ts": 1}, {"ts": 1}], _sum_close)


def test_aggregate_receives_exact_slice_and_output_is_pinned():
    seen: list[tuple[int, ...]] = []

    def aggregate(slice_bars):
        seen.append(tuple(b["ts"] for b in slice_bars))
        return _sum_close(slice_bars)

    report = slice_by_regime([("BULLISH", 0, 4)], _bars(6), aggregate)
    # The determinism guard calls the pure aggregate TWICE on the identical
    # slice — both calls receive exactly the window's bars, nothing else.
    assert seen == [(1, 2, 3), (1, 2, 3)]
    assert report.slices[0].metrics == (101.0 + 102.0 + 103.0,)


def test_nondeterministic_aggregate_refused():
    calls = {"n": 0}

    def drifting_aggregate(slice_bars):
        calls["n"] += 1
        return (float(calls["n"]),)  # changes between the two guard calls

    with pytest.raises(RegimeSliceViolation, match="AGGREGATE_NOT_DETERMINISTIC"):
        slice_by_regime([("BULLISH", 0, 4)], _bars(6), drifting_aggregate)


def test_invalid_aggregate_returns_refused():
    with pytest.raises(RegimeSliceViolation, match="AGGREGATE_RETURN_INVALID"):
        slice_by_regime([("BULLISH", 0, 4)], _bars(6), lambda s: "not-a-sequence")
    with pytest.raises(RegimeSliceViolation, match="AGGREGATE_RETURN_INVALID"):
        slice_by_regime([("BULLISH", 0, 4)], _bars(6), lambda s: ("x",))
    with pytest.raises(RegimeSliceViolation, match="AGGREGATE_RETURN_NON_FINITE"):
        slice_by_regime([("BULLISH", 0, 4)], _bars(6), lambda s: (float("inf"),))
    # A NaN-returning aggregate is refused by the DETERMINISM guard first:
    # NaN != NaN, so a NaN result is by construction never reproducible —
    # both orders are honest refusals; the guard simply fires first.
    with pytest.raises(RegimeSliceViolation, match="AGGREGATE_NOT_DETERMINISTIC"):
        slice_by_regime([("BULLISH", 0, 4)], _bars(6), lambda s: (float("nan"),))
    with pytest.raises(RegimeSliceViolation, match="AGGREGATE_NOT_CALLABLE"):
        slice_by_regime([("BULLISH", 0, 4)], _bars(6), "not-callable")  # type: ignore[arg-type]


def test_report_slices_sorted_by_start_regardless_of_window_input_order():
    bars = _bars(10)
    report = slice_by_regime(
        [("BEARISH", 6, 11), ("BULLISH", 0, 6)], bars, lambda s: (len(s),)
    )
    assert [s.label for s in report.slices] == ["BULLISH", "BEARISH"]
    assert isinstance(report, RegimeSlicesReport)
    assert isinstance(report.slices[0], RegimeSlice)


def test_regime_window_record_accepts_tuples_and_records_equally():
    bars = _bars(4)
    via_tuple = slice_by_regime([("BULLISH", 0, 3)], bars, _sum_close)
    via_record = slice_by_regime([RegimeWindow(label="BULLISH", start_ts=0, end_ts=3)], bars, _sum_close)
    assert via_tuple == via_record


def test_records_are_frozen():
    window = RegimeWindow(label="BULLISH", start_ts=0, end_ts=1)
    with pytest.raises(ValidationError):
        window.start_ts = 5  # type: ignore[misc]
    report = slice_by_regime([window], _bars(4), _sum_close)
    with pytest.raises(ValidationError):
        report.uncovered_bar_count = 99  # type: ignore[misc]
