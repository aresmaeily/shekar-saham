"""MR2-A WAVE-2 tests — MTF runtime plumbing (no-look-ahead alignment).

Covers the ``mtf_context`` parameter of ``prepare`` / ``evaluate`` /
``run_over_series``: higher-timeframe BAR DICTS are aligned onto the primary
series strictly by close timestamp (a higher-TF bar is readable at base bar
``i`` only when its close timestamp ``<= t_i``; the close timestamp derives
from the explicit ``close_ts`` key, else the next supplied bar's open ts, and
an untermined tail bar is never readable).  Before the first closed higher-TF
bar the aligned value is the runtime's usual ``0.0`` warm-up fill.

The no-look-ahead regression mirrors the established
``test_future_bars_do_not_change_past_decisions`` pattern: appending a FUTURE
higher-TF bar (timestamps beyond every base timestamp) must not change a
single earlier decision, even for programs with windowed/recursive
indicators over the MTF series.
"""
from __future__ import annotations

import pytest

from app.engines.strategy_dsl import (
    DSLBudgetError,
    DSLError,
    DSLRuntimeError,
    SeriesContext,
    compile_source,
    prepare,
    run_over_series,
)

N = 12


def base_ctx() -> SeriesContext:
    """12 primary bars on a 60-second grid, ts 0..660, distinct closes."""
    ts = [i * 60 for i in range(N)]
    close = [float(i + 1) for i in range(N)]
    return SeriesContext(
        open=[v - 0.5 for v in close],
        high=[v + 0.5 for v in close],
        low=[v - 1.0 for v in close],
        close=close,
        volume=[1.0] * N,
        ts=ts,
    )


# H1 bars on the same clock: bar ts=0 closes when bar ts=360 opens; bar
# ts=360 closes when bar ts=600 opens; bar ts=600 is explicitly declared
# closed at 660 via the ``close_ts`` key.
H1_BARS = [
    {"ts": 0, "o": 99.0, "h": 101.0, "l": 98.0, "c": 100.0, "v": 5.0},
    {"ts": 360, "o": 199.0, "h": 201.0, "l": 198.0, "c": 200.0, "v": 5.0},
    {"ts": 600, "o": 299.0, "h": 301.0, "l": 298.0, "c": 300.0, "v": 5.0, "close_ts": 660},
]
# Documented aligned H1.close per base index:
#   i0..i5  (t = 0..300 < 360)      -> 0.0   (warm-up: nothing closed yet)
#   i6..i9  (360 <= t < 600)        -> 100.0 (bar ts=0)
#   i10     (t = 600)               -> 200.0 (bar ts=360, closes at 600)
#   i11     (t = 660)               -> 300.0 (bar ts=600, close_ts=660)
ALIGNED_H1_CLOSE = [0.0] * 6 + [100.0] * 4 + [200.0, 300.0]


def entry_true_indices(source: str, mtf_bars: list[dict]) -> set[int]:
    decisions = run_over_series(
        compile_source(source), base_ctx(), mtf_context={"H1": mtf_bars}
    )
    return {d.index for d in decisions if d.entry}


class TestBasicAlignedRead:
    def test_point_read_per_index(self) -> None:
        for i, expected in enumerate(ALIGNED_H1_CLOSE):
            fired = entry_true_indices(f"ENTRY H1.close == {expected!r}", H1_BARS)
            assert (i in fired) is True, f"index {i} should read {expected}"

    def test_warmup_indices_exactly_zero(self) -> None:
        assert entry_true_indices("ENTRY H1.close == 0.0", H1_BARS) == {0, 1, 2, 3, 4, 5}

    def test_latest_closed_bar_wins(self) -> None:
        # at t=660 both bar ts=360 (closes 600) and bar ts=600 (closes 660)
        # are closed; the most recent one must be read.
        assert entry_true_indices("ENTRY H1.close == 300.0", H1_BARS) == {11}

    def test_aligned_series_feeds_indicators(self) -> None:
        # sma(H1.close, 2) over [0,0,0,0,0,0,100,100,100,100,200,300]:
        # i6 -> (0+100)/2 = 50; i10 -> (100+200)/2 = 150; i11 -> (200+300)/2 = 250
        assert entry_true_indices("ENTRY sma(H1.close, 2) == 50.0", H1_BARS) == {6}
        assert entry_true_indices("ENTRY sma(H1.close, 2) == 150.0", H1_BARS) == {10}
        assert entry_true_indices("ENTRY sma(H1.close, 2) == 250.0", H1_BARS) == {11}

    def test_legacy_engine_shape_bar_keys_accepted(self) -> None:
        legacy = [
            {"time": 0, "close": 100.0},
            {"time": 360, "close": 200.0},
            {"time": 600, "close": 300.0, "close_ts": 660},
        ]
        decisions = run_over_series(
            compile_source("ENTRY H1.close == 100.0"), base_ctx(), mtf_context={"H1": legacy}
        )
        assert {d.index for d in decisions if d.entry} == {6, 7, 8, 9}

    def test_evaluate_one_shot_matches_sweep(self) -> None:
        from app.engines.strategy_dsl import evaluate

        program = compile_source("ENTRY H1.close == 200.0")
        for i in range(N):
            one = evaluate(program, base_ctx(), i, mtf_context={"H1": H1_BARS})
            sweep = run_over_series(program, base_ctx(), mtf_context={"H1": H1_BARS})[i]
            assert one == sweep


class TestNotYetClosedBar:
    def test_tail_bar_without_close_ts_never_readable(self) -> None:
        # a single supplied H1 bar has no derivable close timestamp -> it is
        # treated as not yet closed everywhere (strict warm-up 0.0).
        decisions = run_over_series(
            compile_source("ENTRY H1.close == 0.0"),
            base_ctx(),
            mtf_context={"H1": [{"ts": 0, "c": 100.0}]},
        )
        assert all(d.entry for d in decisions)
        assert not any(
            d.entry for d in run_over_series(
                compile_source("ENTRY H1.close > 0"),
                base_ctx(),
                mtf_context={"H1": [{"ts": 0, "c": 100.0}]},
            )
        )

    def test_tail_bar_close_ts_beyond_base_is_warmup(self) -> None:
        # declared close at 10_000s, base ends at 660s -> the tail bar is
        # never readable, and the EARLIER closed bar (ts=0, closes at 360)
        # simply remains the latest closed bar for the whole base range.
        bars = [{"ts": 0, "c": 100.0}, {"ts": 360, "c": 200.0, "close_ts": 10_000}]
        assert entry_true_indices("ENTRY H1.close == 100.0", bars) == {6, 7, 8, 9, 10, 11}
        assert entry_true_indices("ENTRY H1.close == 200.0", bars) == set()
        assert entry_true_indices("ENTRY H1.close == 0.0", bars) == {0, 1, 2, 3, 4, 5}


class TestNoLookAheadAppendInvariance:
    PROGRAM = (
        "INPUT p = 2\n"
        "ENTRY crossover(H1.close, sma(H1.close, p)) AND ref(H1.close, 1) > 0\n"
        "EXIT crossunder(H1.close, sma(H1.close, p))\n"
        "ALERT H1.close > highest(H1.close, 3) * 0.5"
    )

    def _check_invariant(self, tail_bars: list[dict]) -> None:
        program = compile_source(self.PROGRAM)
        ctx = base_ctx()
        short = run_over_series(program, ctx, mtf_context={"H1": tail_bars})
        extended = tail_bars + [{"ts": 100_000, "o": 1.0, "h": 2.0, "l": 0.5, "c": 999.0, "v": 1.0}]
        long_ = run_over_series(program, ctx, mtf_context={"H1": extended})
        assert short == long_

    def test_future_append_invariant_with_declared_tail(self) -> None:
        # tail bar declares its close ts explicitly -> appending a far-future
        # bar cannot change ANY close timestamp of earlier bars
        self._check_invariant(H1_BARS)

    def test_future_append_invariant_with_undeclared_tail(self) -> None:
        # tail bar without close_ts is not readable; after the append it
        # would close only at ts=100_000, which is beyond every base ts, so
        # still nothing changes
        self._check_invariant(H1_BARS[:2])

    def test_prefix_property_also_holds_for_base_series(self) -> None:
        # established pattern: extending the PRIMARY series must not change
        # earlier decisions either (guard that mtf plumbing did not break it)
        program = compile_source("ENTRY crossover(H1.close, sma(H1.close, 2))")
        ctx = base_ctx()
        short = run_over_series(program, ctx, mtf_context={"H1": H1_BARS})
        grown = SeriesContext(
            open=ctx.open + [6.0],
            high=ctx.high + [7.0],
            low=ctx.low + [5.0],
            close=ctx.close + [6.0],
            volume=[1.0] * (N + 1),
            ts=[i * 60 for i in range(N + 1)],
        )
        long_ = run_over_series(program, grown, mtf_context={"H1": H1_BARS})
        assert short == long_[:N]


class TestBudgetsAndFailClosed:
    def test_mtf_budget_still_enforced(self) -> None:
        # 4 distinct timeframes exceed BUDGET_MTF at COMPILE time, exactly as
        # before; mtf_context cannot relax it (and is not even consulted).
        with pytest.raises(DSLBudgetError) as excinfo:
            compile_source("ENTRY D1.close + W1.close + M1.close + H4.close > 0")
        assert excinfo.value.code == "BUDGET_MTF"

    def test_missing_timeframe_fails_closed(self) -> None:
        # a referenced timeframe absent from mtf_context keeps raising the
        # documented RUN_MISSING_MTF_SERIES (no silent zeros)
        with pytest.raises(DSLError) as excinfo:
            run_over_series(
                compile_source("ENTRY D1.close > 0"), base_ctx(), mtf_context={"H1": H1_BARS}
            )
        assert excinfo.value.code == "RUN_MISSING_MTF_SERIES"

    def test_missing_base_in_bars_fails_closed(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            run_over_series(
                compile_source("ENTRY H1.volume > 0"),
                base_ctx(),
                mtf_context={"H1": [{"ts": 0, "c": 1.0}]},
            )
        assert excinfo.value.code == "RUN_MISSING_MTF_SERIES"

    def test_mtf_context_without_base_ts_rejected(self) -> None:
        ctx = SeriesContext(
            open=[1.0, 2.0],
            high=[1.0, 2.0],
            low=[1.0, 2.0],
            close=[1.0, 2.0],
            volume=[1.0, 1.0],
        )  # no ts
        with pytest.raises(DSLError) as excinfo:
            run_over_series(
                compile_source("ENTRY H1.close > 0"), ctx, mtf_context={"H1": H1_BARS}
            )
        assert excinfo.value.code == "RUN_MTF_MISSING_BASE_TS"

    def test_base_ts_length_mismatch_rejected(self) -> None:
        ctx = base_ctx().model_copy(update={"ts": [0, 60]})
        with pytest.raises(DSLError) as excinfo:
            run_over_series(
                compile_source("ENTRY H1.close > 0"), ctx, mtf_context={"H1": H1_BARS}
            )
        assert excinfo.value.code == "RUN_SERIES_LENGTH_MISMATCH"

    def test_bar_without_timestamp_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            run_over_series(
                compile_source("ENTRY H1.close > 0"),
                base_ctx(),
                mtf_context={"H1": [{"c": 1.0}, {"ts": 600, "c": 2.0}]},
            )
        assert excinfo.value.code == "RUN_MTF_BAD_BARS"


class TestDeterminism:
    def test_two_runs_identical(self) -> None:
        program = compile_source(self_style_program())
        first = run_over_series(program, base_ctx(), mtf_context={"H1": H1_BARS})
        second = run_over_series(program, base_ctx(), mtf_context={"H1": H1_BARS})
        assert first == second

    def test_digest_tracks_effective_mtf_context(self) -> None:
        program = compile_source("ENTRY H1.close > 0")
        digest_a = prepare(program, base_ctx(), mtf_context={"H1": H1_BARS}).ctx_digest
        digest_b = prepare(program, base_ctx(), mtf_context={"H1": H1_BARS}).ctx_digest
        other = [dict(H1_BARS[0]), dict(H1_BARS[1]), {**H1_BARS[2], "c": 123.0}]
        digest_c = prepare(program, base_ctx(), mtf_context={"H1": other}).ctx_digest
        assert digest_a == digest_b
        assert digest_a != digest_c
        # a plain equal-length ctx.mtf series (the legacy plumbing) produces
        # yet another digest: the aligned effective series differs from it
        fallback_ctx = base_ctx().model_copy(
            update={"mtf": {"H1": {"close": [1.0] * N}}}
        )
        assert prepare(program, fallback_ctx).ctx_digest != digest_a


def self_style_program() -> str:
    return (
        "INPUT p = 2\n"
        "ENTRY crossover(H1.close, sma(H1.close, p))\n"
        "EXIT crossunder(H1.close, sma(H1.close, p))\n"
        "ALERT H1.close > 150"
    )


# ---------------------------------------------------------------------------
# AUDIT-MR2 O3 (fail closed): non-monotonic close stamps must REFUSE, not
# silently misalign. The bisect in _align_mtf_pair assumes ascending close
# timestamps; explicit non-ascending close_ts (or non-ascending bar order)
# would otherwise read the WRONG higher-TF bar without any error.
# ---------------------------------------------------------------------------


def test_mtf_nonmonotonic_explicit_close_ts_fails_closed():
    bars = [
        {"ts": 0, "c": 11.0, "close_ts": 500},
        {"ts": 120, "c": 22.0, "close_ts": 100},  # goes BACKWARDS
        {"ts": 240, "c": 33.0, "close_ts": 700},
    ]
    with pytest.raises(DSLRuntimeError) as excinfo:
        run_over_series(
            compile_source("ENTRY H1.close > 0"), base_ctx(), mtf_context={"H1": bars}
        )
    assert excinfo.value.code == "RUN_MTF_NONMONOTONIC_CLOSE_TS"


def test_mtf_nonmonotonic_bar_order_fails_closed():
    # Even without explicit close_ts, non-ascending open timestamps make the
    # derived (next-open) close stamps non-monotonic → same refusal:
    # derived stamps here = [100, 50, None] → 50 < 100 → refuse.
    bars = [
        {"ts": 0, "c": 11.0},
        {"ts": 100, "c": 22.0},
        {"ts": 50, "c": 33.0},  # out of order
    ]
    with pytest.raises(DSLRuntimeError) as excinfo:
        run_over_series(
            compile_source("ENTRY H1.close > 0"), base_ctx(), mtf_context={"H1": bars}
        )
    assert excinfo.value.code == "RUN_MTF_NONMONOTONIC_CLOSE_TS"


def test_mtf_ascending_close_ts_still_aligns():
    # Positive control: the refusal must not fire for well-formed input.
    bars = [
        {"ts": 0, "c": 11.0, "close_ts": 120},
        {"ts": 120, "c": 22.0, "close_ts": 400},
        {"ts": 400, "c": 33.0, "close_ts": 700},
    ]
    # Positive control mapping (base grid 60s, ts = 0..660):
    #   stamps 120/400/700 → 11.0 readable at 120 <= t < 400 (indices 2-6),
    #   22.0 at 400 <= t < 700 (indices 7-11); indices 0-1 warm-up 0.0.
    decisions = run_over_series(
        compile_source("ENTRY H1.close == 11.0"), base_ctx(), mtf_context={"H1": bars}
    )
    assert [d.entry for d in decisions] == [False, False] + [True] * 5 + [False] * 5
    decisions22 = run_over_series(
        compile_source("ENTRY H1.close == 22.0"), base_ctx(), mtf_context={"H1": bars}
    )
    assert [d.entry for d in decisions22] == [False] * 7 + [True] * 5
