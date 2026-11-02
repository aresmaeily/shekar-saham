"""T2 / CONSOL-NEXT Wave 1 — P3 independent validation of
app.engines.regime_slices (MA-1 WS-2).

ADDITIVE gap tests. Existing coverage (tests/test_regime_slices.py, not
duplicated): two-window membership + aggregates, half-open boundary bar,
gap window + uncovered bars, one overlapping pair in input order,
touching windows, invalid bounds, unknown tuple label, non-numeric
window ts, no windows, bad window shape, bar integrity refusals,
aggregate called twice with exact slice, single-window nondeterministic
aggregate, invalid/non-finite/non-callable aggregates, report sorted by
start, tuple-vs-record equivalence, frozen records.

Gaps filled here: model-level closed-vocabulary enforcement (all five
labels + a refused one), adversarial overlap shapes (nested, duplicated,
overlap hidden by scrambled input order), multi-window determinism drift
on a LATER window, list/empty-tuple/bool aggregate returns, and the
never-called-on-gap-windows + exactly-twice-per-nonempty-window
contract.
"""

import pytest
from pydantic import ValidationError

from app.engines.regime_slices import (
    REGIME_LABELS,
    RegimeSliceViolation,
    RegimeWindow,
    slice_by_regime,
)


def _bars(count: int, start: int = 1) -> list[dict]:
    return [{"ts": i, "pl": 100.0 + i} for i in range(start, start + count)]


def _sum_close(slice_bars) -> tuple[float]:
    return (sum(b["pl"] for b in slice_bars),)


# ---------------------------------------------------------------------------
# Closed label vocabulary — model-level enforcement
# ---------------------------------------------------------------------------


def test_p3_regime_label_vocabulary_is_closed_at_model_level():
    # All five documented labels construct a RegimeWindow; the tuple path
    # and REGIME_LABELS agree with this set.
    for label in ("BULLISH", "BEARISH", "NEUTRAL", "HIGH_VOLATILITY", "LOW_VOLATILITY"):
        window = RegimeWindow(label=label, start_ts=0.0, end_ts=1.0)  # type: ignore[arg-type]
        assert window.label == label
    assert set(REGIME_LABELS) == {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
    }
    # A free-form label is refused at the MODEL boundary too (the existing
    # suite only exercises the tuple normalization path with "PUMP").
    with pytest.raises(ValidationError):
        RegimeWindow(label="SIDEWAYS", start_ts=0.0, end_ts=1.0)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        RegimeWindow(label="bullish", start_ts=0.0, end_ts=1.0)  # case-sensitive


# ---------------------------------------------------------------------------
# Adversarial overlap shapes
# ---------------------------------------------------------------------------


def test_p3_overlap_refused_for_nested_duplicated_and_scrambled_windows():
    bars = _bars(10)
    # Nested: [0,10) fully contains [2,5) — overlap regardless of nesting.
    with pytest.raises(RegimeSliceViolation, match="OVERLAPPING_REGIME_WINDOWS"):
        slice_by_regime([("BULLISH", 0, 10), ("BEARISH", 2, 5)], bars, _sum_close)
    # Exact duplicates: two identical windows overlap trivially.
    with pytest.raises(RegimeSliceViolation, match="OVERLAPPING_REGIME_WINDOWS"):
        slice_by_regime([("NEUTRAL", 2, 5), ("NEUTRAL", 2, 5)], bars, _sum_close)
    # Scrambled input order hides the overlap from any naive
    # pairwise-in-input-order scan: HIGH_VOLATILITY [20,30) is given
    # FIRST, BULLISH [0,10) second, BEARISH [5,6) third. After the
    # module's own sort the offending ADJACENT pair is
    # (BULLISH [0,10), BEARISH [5,6)) — 5 < 10 — and the refusal detail
    # must name exactly that pair.
    with pytest.raises(RegimeSliceViolation) as excinfo:
        slice_by_regime(
            [("HIGH_VOLATILITY", 20, 30), ("BULLISH", 0, 10), ("BEARISH", 5, 6)],
            bars,
            _sum_close,
        )
    assert excinfo.value.reason == "OVERLAPPING_REGIME_WINDOWS"
    assert "BULLISH" in excinfo.value.detail and "BEARISH" in excinfo.value.detail
    # Same scrambled triple WITHOUT the overlap is fine (control): the
    # refusal above is caused by the overlap, not the ordering.
    report = slice_by_regime(
        [("HIGH_VOLATILITY", 20, 30), ("BULLISH", 0, 5), ("BEARISH", 5, 6)],
        bars,
        lambda s: (len(s),),
    )
    assert [s.label for s in report.slices] == ["BULLISH", "BEARISH", "HIGH_VOLATILITY"]


# ---------------------------------------------------------------------------
# Determinism guard — drift on a LATER window
# ---------------------------------------------------------------------------


def test_p3_determinism_guard_catches_drift_on_second_window():
    # Adversarial aggregate: fully deterministic for its first two calls
    # (window one passes the double-call guard), then drifts from call 3
    # onward (window two gets 3.0 then 4.0). The guard must refuse —
    # nondeterminism is not excused because an earlier window was clean.
    calls = {"n": 0}

    def late_drift(slice_bars):
        calls["n"] += 1
        if calls["n"] <= 2:
            return (7.0,)
        return (float(calls["n"]),)

    with pytest.raises(RegimeSliceViolation, match="AGGREGATE_NOT_DETERMINISTIC"):
        slice_by_regime(
            [("BULLISH", 0, 3), ("BEARISH", 3, 6)], _bars(6), late_drift
        )


def test_p3_aggregate_called_exactly_twice_per_nonempty_window_never_on_gaps():
    # Contract: "Called exactly twice per non-empty window; empty windows
    # are never passed to it." Two non-empty windows + one gap window
    # => exactly 4 calls, and NEVER with an empty slice.
    seen_sizes: list[int] = []

    def counting_aggregate(slice_bars):
        seen_sizes.append(len(slice_bars))
        return (float(sum(b["pl"] for b in slice_bars)),)

    bars = _bars(6)  # ts 1..6; window [10,20) covers nothing
    report = slice_by_regime(
        [("BULLISH", 0, 3), ("BEARISH", 3, 6), ("NEUTRAL", 10, 20)],
        bars,
        counting_aggregate,
    )
    assert seen_sizes == [2, 2, 3, 3]  # window1 twice, window2 twice, gap: none
    assert report.gap_labels == ("NEUTRAL",)
    assert report.slices[2].metrics == ()


def test_p3_aggregate_may_return_list_or_empty_tuple():
    bars = _bars(4)
    # A LIST return is accepted and normalized to a tuple of floats.
    report_list = slice_by_regime(
        [("BULLISH", 0, 3)], bars, lambda s: [float(len(s))]
    )
    assert report_list.slices[0].metrics == (2.0,)
    assert isinstance(report_list.slices[0].metrics, tuple)
    # An EMPTY tuple is a legitimate aggregate of a caller that pins no
    # numeric metric (schema-valid, deterministic).
    report_empty = slice_by_regime([("BULLISH", 0, 3)], bars, lambda s: ())
    assert report_empty.slices[0].metrics == ()
    # Boolean "numbers" are refused (bool is an int in Python — a flag is
    # not a measurement).
    with pytest.raises(RegimeSliceViolation, match="AGGREGATE_RETURN_INVALID"):
        slice_by_regime([("BULLISH", 0, 3)], bars, lambda s: (True,))
