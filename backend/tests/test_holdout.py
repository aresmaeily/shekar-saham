"""Tests for app.engines.holdout (dataset-level holdout isolation).

Every refusal path has a dedicated fail-closed test with the exact reason
code; happy-path expectations (segment sizes, boundary timestamps) are
hand-derived from the split rule floor(n * fraction).
"""

import pytest
from pydantic import ValidationError

from app.engines.holdout import (
    HoldoutAttestation,
    HoldoutViolation,
    SelectionWindow,
    assert_no_selection_on_holdout,
    bar_timestamp,
    boundary_ts_of,
    require_sorted_unique_bars,
    split_holdout,
)


def _bars(count: int, start: int = 1) -> list[dict]:
    return [{"ts": i, "pl": 100.0 + i} for i in range(start, start + count)]


# ---------------------------------------------------------------------------
# split_holdout
# ---------------------------------------------------------------------------


def test_split_holdout_minority_tail_segment_hand_computed():
    # n = 10, fraction = 0.4 -> floor(10 * 0.4) = 4 holdout bars (the TAIL):
    # insample ts 1..6, holdout ts 7..10. Holdout stays a minority (4 < 6).
    bars = _bars(10)
    insample, holdout = split_holdout(bars, 0.4)
    assert [b["ts"] for b in insample] == [1, 2, 3, 4, 5, 6]
    assert [b["ts"] for b in holdout] == [7, 8, 9, 10]
    # The split returns the SAME bar mappings (no copies, no mutation).
    assert insample[0] is bars[0]
    assert holdout[-1] is bars[-1]


def test_split_holdout_boundary_is_timestamp_frontier():
    bars = _bars(10)
    insample, holdout = split_holdout(bars, 0.4)
    boundary = boundary_ts_of(holdout)
    assert boundary == 7.0
    assert bar_timestamp(insample[-1]) < boundary <= bar_timestamp(holdout[0])


def test_split_holdout_refuses_fraction_outside_open_interval():
    bars = _bars(10)
    for bad in (0.0, -0.1, 0.5, 0.75, 1.0):
        with pytest.raises(HoldoutViolation, match="HOLDOUT_FRACTION_NOT_IN_OPEN_INTERVAL"):
            split_holdout(bars, bad)


def test_split_holdout_refuses_non_numeric_and_nan_fraction():
    bars = _bars(10)
    with pytest.raises(HoldoutViolation, match="HOLDOUT_FRACTION_NOT_IN_OPEN_INTERVAL"):
        split_holdout(bars, "0.3")  # type: ignore[arg-type]
    with pytest.raises(HoldoutViolation, match="HOLDOUT_FRACTION_NOT_IN_OPEN_INTERVAL"):
        split_holdout(bars, float("nan"))


def test_split_holdout_refuses_empty_bars():
    with pytest.raises(HoldoutViolation, match="EMPTY_BAR_SEQUENCE"):
        split_holdout([], 0.3)


def test_split_holdout_refuses_unsorted_bars():
    bars = [{"ts": 3}, {"ts": 1}, {"ts": 2}]
    with pytest.raises(HoldoutViolation, match="UNSORTED_BARS"):
        split_holdout(bars, 0.3)


def test_split_holdout_refuses_duplicate_timestamps():
    bars = [{"ts": 1}, {"ts": 2}, {"ts": 2}, {"ts": 3}]
    with pytest.raises(HoldoutViolation, match="DUPLICATE_TIMESTAMPS"):
        split_holdout(bars, 0.25)


def test_split_holdout_refuses_degenerate_zero_bar_holdout():
    # floor(10 * 0.04) = 0 -> a zero-bar holdout would be a fake attestation
    # surface: refused.
    with pytest.raises(HoldoutViolation, match="HOLDOUT_SEGMENT_EMPTY"):
        split_holdout(_bars(10), 0.04)


def test_require_sorted_unique_bars_reports_exact_reason_codes():
    assert require_sorted_unique_bars(_bars(3)) == (1.0, 2.0, 3.0)
    with pytest.raises(HoldoutViolation, match="EMPTY_BAR_SEQUENCE"):
        require_sorted_unique_bars([])
    with pytest.raises(HoldoutViolation, match="UNSORTED_BARS"):
        require_sorted_unique_bars([{"ts": 2}, {"ts": 1}])
    with pytest.raises(HoldoutViolation, match="DUPLICATE_TIMESTAMPS"):
        require_sorted_unique_bars([{"ts": 1}, {"ts": 1}])


def test_bar_timestamp_refuses_missing_boolean_and_nonfinite():
    with pytest.raises(HoldoutViolation, match="BAR_TS_MISSING_OR_NON_NUMERIC"):
        bar_timestamp({"pl": 100})
    with pytest.raises(HoldoutViolation, match="BAR_TS_MISSING_OR_NON_NUMERIC"):
        bar_timestamp({"ts": "7"})  # strings are not timestamps
    with pytest.raises(HoldoutViolation, match="BAR_TS_MISSING_OR_NON_NUMERIC"):
        bar_timestamp({"ts": True})  # a truth flag is not a timestamp
    with pytest.raises(HoldoutViolation, match="BAR_TS_NOT_FINITE"):
        bar_timestamp({"ts": float("nan")})


# ---------------------------------------------------------------------------
# assert_no_selection_on_holdout
# ---------------------------------------------------------------------------


def _split10():
    return split_holdout(_bars(10), 0.4)  # boundary = 7.0


def test_selection_window_model_refuses_end_before_start():
    with pytest.raises(ValidationError, match="selection_window_end_before_start"):
        SelectionWindow(strategy_id="S1", selection_start_ts=5.0, selection_end_ts=4.0)


def test_attestation_happy_path_isolated_true():
    insample, holdout = _split10()
    window = SelectionWindow(strategy_id="S1", selection_start_ts=1.0, selection_end_ts=6.0)
    attestation = assert_no_selection_on_holdout(
        window,
        holdout_boundary_ts=boundary_ts_of(holdout),
        insample_bars=insample,
        holdout_bars=holdout,
    )
    assert isinstance(attestation, HoldoutAttestation)
    assert attestation.isolated is True  # the only reachable value
    assert attestation.holdout_boundary_ts == 7.0
    assert (attestation.insample_first_ts, attestation.insample_last_ts) == (1.0, 6.0)
    assert (attestation.holdout_first_ts, attestation.holdout_last_ts) == (7.0, 10.0)
    assert (attestation.insample_bar_count, attestation.holdout_bar_count) == (6, 4)


def test_attestation_refuses_selection_touching_the_boundary():
    # Strictly-before rule: ending exactly AT the boundary is already a
    # violation (no off-by-one leniency).
    insample, holdout = _split10()
    window = SelectionWindow(strategy_id="S1", selection_start_ts=1.0, selection_end_ts=7.0)
    with pytest.raises(HoldoutViolation, match="SELECTION_WINDOW_OVERLAPS_HOLDOUT"):
        assert_no_selection_on_holdout(
            window,
            holdout_boundary_ts=7.0,
            insample_bars=insample,
            holdout_bars=holdout,
        )


def test_attestation_refuses_selection_entirely_inside_holdout():
    insample, holdout = _split10()
    window = SelectionWindow(strategy_id="S1", selection_start_ts=8.0, selection_end_ts=9.0)
    with pytest.raises(HoldoutViolation, match="SELECTION_WINDOW_OVERLAPS_HOLDOUT"):
        assert_no_selection_on_holdout(
            window,
            holdout_boundary_ts=7.0,
            insample_bars=insample,
            holdout_bars=holdout,
        )


def test_attestation_refuses_insample_crossing_the_boundary():
    # Hand-built inconsistent segments: "insample" reaches ts 9 while the
    # boundary is 7 — the insample segment leaks into the holdout window.
    insample = _bars(5, start=5)   # ts 5..9
    holdout = _bars(4, start=7)    # ts 7..10
    window = SelectionWindow(strategy_id="S1", selection_start_ts=1.0, selection_end_ts=4.0)
    with pytest.raises(HoldoutViolation, match="INSAMPLE_CROSSES_HOLDOUT_BOUNDARY"):
        assert_no_selection_on_holdout(
            window, holdout_boundary_ts=7.0, insample_bars=insample, holdout_bars=holdout
        )


def test_attestation_refuses_holdout_segment_before_declared_boundary():
    insample, holdout = _split10()
    window = SelectionWindow(strategy_id="S1", selection_start_ts=1.0, selection_end_ts=6.0)
    with pytest.raises(HoldoutViolation, match="HOLDOUT_SEGMENT_BEFORE_BOUNDARY"):
        assert_no_selection_on_holdout(
            window, holdout_boundary_ts=8.0, insample_bars=insample, holdout_bars=holdout
        )


def test_attestation_refuses_degenerate_segments():
    window = SelectionWindow(strategy_id="S1", selection_start_ts=1.0, selection_end_ts=2.0)
    with pytest.raises(HoldoutViolation, match="EMPTY_INSAMPLE_SEGMENT"):
        assert_no_selection_on_holdout(
            window, holdout_boundary_ts=7.0, insample_bars=[], holdout_bars=_bars(3, start=7)
        )
    with pytest.raises(HoldoutViolation, match="EMPTY_HOLDOUT_SEGMENT"):
        assert_no_selection_on_holdout(
            window, holdout_boundary_ts=7.0, insample_bars=_bars(6), holdout_bars=[]
        )


def test_attestation_refuses_non_numeric_boundary():
    insample, holdout = _split10()
    window = SelectionWindow(strategy_id="S1", selection_start_ts=1.0, selection_end_ts=6.0)
    with pytest.raises(HoldoutViolation, match="HOLDOUT_BOUNDARY_NOT_NUMERIC"):
        assert_no_selection_on_holdout(
            window,
            holdout_boundary_ts="7.0",  # type: ignore[arg-type]
            insample_bars=insample,
            holdout_bars=holdout,
        )
    with pytest.raises(HoldoutViolation, match="HOLDOUT_BOUNDARY_NOT_FINITE"):
        assert_no_selection_on_holdout(
            window,
            holdout_boundary_ts=float("inf"),
            insample_bars=insample,
            holdout_bars=holdout,
        )


def test_attestation_record_is_frozen():
    insample, holdout = _split10()
    window = SelectionWindow(strategy_id="S1", selection_start_ts=1.0, selection_end_ts=6.0)
    attestation = assert_no_selection_on_holdout(
        window,
        holdout_boundary_ts=boundary_ts_of(holdout),
        insample_bars=insample,
        holdout_bars=holdout,
    )
    with pytest.raises(ValidationError):
        attestation.isolated = False  # type: ignore[misc]
