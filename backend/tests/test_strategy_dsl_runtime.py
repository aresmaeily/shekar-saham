"""MASTER-RADAR directive §C2 — runtime tests for the RSL-1 interpreter.

All expected values below are hand-derived in the comments from the
definitions documented in ``runtime.py``; none of them reuse runtime code.
The probe pattern used throughout: compile a program whose ENTRY compares the
function under test against the hand-computed value and assert the resulting
per-bar decisions.
"""
from __future__ import annotations

import math

import pytest

from app.engines.strategy_dsl import (
    Decision,
    DSLError,
    Program,
    RiskSpec,
    SeriesContext,
    compile_source,
    evaluate,
    evaluate_at,
    prepare,
    run_over_series,
)


def ctx_of(
    close: list[float],
    *,
    volume: list[float] | None = None,
    high: list[float] | None = None,
    low: list[float] | None = None,
) -> SeriesContext:
    n = len(close)
    return SeriesContext(
        open=[0.0] * n,
        high=high if high is not None else list(close),
        low=low if low is not None else list(close),
        close=list(close),
        volume=volume if volume is not None else [1.0] * n,
    )


def entry_flags(source: str, ctx: SeriesContext) -> list[bool]:
    program = compile_source(source)
    return [d.entry for d in run_over_series(program, ctx)]


def probe_indices(fn_expr: str, ctx: SeriesContext) -> set[int]:
    """Indices where the given boolean expression evaluates true."""
    program = compile_source(f"ENTRY {fn_expr}")
    return {d.index for d in run_over_series(program, ctx) if d.entry}


class TestSma:
    def test_sma_period3_hand_computed(self) -> None:
        # close = [1,2,3,4,5,6]; sma(3) = [0, 0, 2, 3, 4, 5]
        # idx2: (1+2+3)/3 = 2.0; idx3: (2+3+4)/3 = 3.0; etc. Warm-up: 0.0.
        ctx = ctx_of([1.0, 2, 3, 4, 5, 6])
        expected = [0.0, 0.0, 2.0, 3.0, 4.0, 5.0]
        for i, exp in enumerate(expected):
            assert evaluate(
                compile_source(f"ENTRY sma(close, 3) == {exp!r}"), ctx, i
            ).entry is True, f"sma index {i}"

    def test_sma_matches_none_of_wrong_values(self) -> None:
        ctx = ctx_of([1.0, 2, 3, 4, 5, 6])
        # at index 4 sma is exactly 4.0, not 3.999 or 4.001
        assert evaluate(compile_source("ENTRY sma(close, 3) == 3.999"), ctx, 4).entry is False
        assert evaluate(compile_source("ENTRY sma(close, 3) == 4.001"), ctx, 4).entry is False


class TestEma:
    def test_ema_seed_and_steps_exact(self) -> None:
        # close = [1..6], period 3: k = 2/(3+1) = 0.5
        # seed at idx2 = (1+2+3)/3 = 2.0
        # idx3: 2 + 0.5*(4-2) = 3.0
        # idx4: 3 + 0.5*(5-3) = 4.0
        # idx5: 4 + 0.5*(6-4) = 5.0  (exact in binary floating point)
        ctx = ctx_of([1.0, 2, 3, 4, 5, 6])
        expected = [None, None, 2.0, 3.0, 4.0, 5.0]
        for i, exp in enumerate(expected):
            if exp is None:
                # warm-up: exactly 0.0
                assert evaluate(compile_source("ENTRY ema(close, 3) == 0.0"), ctx, i).entry
            else:
                ok = evaluate(
                    compile_source(
                        f"ENTRY abs(ema(close, 3) - {exp!r}) < 0.000000000001"
                    ),
                    ctx,
                    i,
                ).entry
                assert ok, f"ema index {i}"

    def test_ema_period5_seed(self) -> None:
        # [2,4,6,8,10,12], period 5: seed idx4 = (2+4+6+8+10)/5 = 6.0
        # idx5: 6 + (1/3)*(12-6) = 8.0
        ctx = ctx_of([2.0, 4, 6, 8, 10, 12])
        assert evaluate(compile_source("ENTRY ema(close, 5) == 6.0"), ctx, 4).entry
        assert evaluate(
            compile_source("ENTRY abs(ema(close, 5) - 8.0) < 0.000000000001"), ctx, 5
        ).entry


class TestRsi:
    def test_rsi_rising_is_100(self) -> None:
        # strictly rising: avg_loss == 0 from the seed on -> RSI = 100.0
        # period 2: seed at index 2; indices 0..1 warm-up -> 0.0
        ctx = ctx_of([1.0, 2, 3, 4, 5, 6])
        fired = probe_indices("rsi(close, 2) == 100.0", ctx)
        assert fired == {2, 3, 4, 5}

    def test_rsi_falling_is_0(self) -> None:
        # strictly falling: avg_gain == 0 -> RS = 0 -> RSI = 100 - 100/1 = 0.0
        ctx = ctx_of([6.0, 5, 4, 3, 2, 1])
        fired = probe_indices("rsi(close, 2) == 0.0", ctx)
        assert fired == {0, 1, 2, 3, 4, 5}

    def test_rsi_mixed_hand_computed(self) -> None:
        # close = [1,3,2,5,4,6]; period 3
        # changes: +2,-1,+3,-1,+2 -> gains g1..g5 = 2,0,3,0,2; losses = 0,1,0,1,0
        # seed idx3: avg_gain=(2+0+3)/3=5/3; avg_loss=(0+1+0)/3=1/3; RS=5
        #   RSI = 100 - 100/6 = 83.3333...
        # idx4: avg_gain=(5/3*2+0)/3=10/9; avg_loss=(1/3*2+1)/3=5/9; RS=2
        #   RSI = 100 - 100/3 = 66.6666...
        # idx5: avg_gain=(10/9*2+2)/3=38/27; avg_loss=(5/9*2+0)/3=10/27; RS=3.8
        #   RSI = 100 - 100/4.8 = 79.1666...
        ctx = ctx_of([1.0, 3, 2, 5, 4, 6])
        r3 = 100.0 - 100.0 / 6.0
        r4 = 100.0 - 100.0 / 3.0
        r5 = 100.0 - 100.0 / 4.8
        for i, exp in ((3, r3), (4, r4), (5, r5)):
            ok = evaluate(
                compile_source(f"ENTRY abs(rsi(close, 3) - {exp!r}) < 0.000000001"),
                ctx,
                i,
            ).entry
            assert ok, f"rsi index {i}"
        # warm-up indices are exactly 0.0
        assert probe_indices("rsi(close, 3) == 0.0", ctx) == {0, 1, 2}


class TestStdev:
    def test_stdev_population_hand_computed(self) -> None:
        # close = [1..6], period 3: every window [k-1,k,k+1] has population
        # stddev sqrt(2/3) ~= 0.816496580927726; warm-up -> 0.0
        ctx = ctx_of([1.0, 2, 3, 4, 5, 6])
        exp = math.sqrt(2.0 / 3.0)
        for i in (2, 3, 4, 5):
            ok = evaluate(
                compile_source(
                    f"ENTRY abs(stdev(close, 3) - {exp!r}) < 0.000000000001"
                ),
                ctx,
                i,
            ).entry
            assert ok, f"stdev index {i}"
        assert probe_indices("stdev(close, 3) == 0.0", ctx) == {0, 1}


class TestHighestLowest:
    def test_highest_partial_window(self) -> None:
        # close = [1,3,2,5,4], period 3:
        # idx0 partial window [1] -> 1; idx1 [1,3] -> 3; idx2 [1,3,2] -> 3;
        # idx3 [3,2,5] -> 5; idx4 [2,5,4] -> 5
        ctx = ctx_of([1.0, 3, 2, 5, 4])
        expected = [1.0, 3.0, 3.0, 5.0, 5.0]
        for i, exp in enumerate(expected):
            assert evaluate(
                compile_source(f"ENTRY highest(close, 3) == {exp!r}"), ctx, i
            ).entry, f"highest index {i}"

    def test_lowest_partial_window(self) -> None:
        # close = [1,3,2,5,4], period 3: lowest = [1, 1, 1, 2, 2]
        ctx = ctx_of([1.0, 3, 2, 5, 4])
        expected = [1.0, 1.0, 1.0, 2.0, 2.0]
        for i, exp in enumerate(expected):
            assert evaluate(
                compile_source(f"ENTRY lowest(close, 3) == {exp!r}"), ctx, i
            ).entry, f"lowest index {i}"


class TestAtr:
    def test_atr_hand_computed(self) -> None:
        # high=[2,3,4,5], low=[1,2,3,4], close=[1.5,2.5,3.5,4.5], period 2
        # tr0 = 2-1 = 1.0
        # tr1 = max(3-2, |3-1.5|, |2-1.5|) = 1.5
        # tr2 = max(4-3, |4-2.5|, |3-2.5|) = 1.5
        # tr3 = 1.5
        # seed idx2 = mean(tr[1..2]) = 1.5; idx3 Wilder: (1.5*1+1.5)/2 = 1.5
        ctx = SeriesContext(
            open=[0.0] * 4,
            high=[2.0, 3, 4, 5],
            low=[1.0, 2, 3, 4],
            close=[1.5, 2.5, 3.5, 4.5],
            volume=[1.0] * 4,
        )
        expected = [0.0, 0.0, 1.5, 1.5]
        for i, exp in enumerate(expected):
            assert evaluate(
                compile_source(f"ENTRY atr(high, low, close, 2) == {exp!r}"), ctx, i
            ).entry, f"atr index {i}"


class TestCrossover:
    def test_crossover_truth_table(self) -> None:
        # close = [0,1,0,1] vs volume = [0.5,0.5,0.5,0.5]
        # i0: False (no previous bar)
        # i1: 0<=0.5 and 1>0.5 -> True
        # i2: 1<=0.5 false -> False
        # i3: 0<=0.5 and 1>0.5 -> True
        ctx = ctx_of([0.0, 1, 0, 1], volume=[0.5, 0.5, 0.5, 0.5])
        assert probe_indices("crossover(close, volume)", ctx) == {1, 3}

    def test_crossunder_truth_table(self) -> None:
        # crossunder: a[i-1] >= b[i-1] and a[i] < b[i]
        # i1: 0>=0.5 false; i2: 1>=0.5 and 0<0.5 -> True; i3: false
        ctx = ctx_of([0.0, 1, 0, 1], volume=[0.5, 0.5, 0.5, 0.5])
        assert probe_indices("crossunder(close, volume)", ctx) == {2}

    def test_crossover_scalar_broadcast(self) -> None:
        ctx = ctx_of([0.0, 1, 0, 1])
        assert probe_indices("crossover(close, 0.5)", ctx) == {1, 3}


class TestRef:
    def test_ref_warmup_zero(self) -> None:
        # close = [5,6,7,8,9]; ref(close,3): i0..i2 -> 0.0 (warm-up);
        # i3 -> close[0]=5; i4 -> close[1]=6
        ctx = ctx_of([5.0, 6, 7, 8, 9])
        assert probe_indices("ref(close, 3) == 0.0", ctx) == {0, 1, 2}
        assert evaluate(compile_source("ENTRY ref(close, 3) == 5.0"), ctx, 3).entry
        assert evaluate(compile_source("ENTRY ref(close, 3) == 6.0"), ctx, 4).entry


class TestDecisions:
    CLOSE_10 = [10.0, 11, 12, 11, 10, 9, 10, 11, 12, 13]

    def test_entry_fires_exactly_at_expected_index(self) -> None:
        # sma(3) of CLOSE_10: [0,0,11.0,11.33,11.0,10.0,9.67,10.0,11.0,12.0]
        # crossover(close, sma(close,3)) needs close[i-1] <= sma[i-1] and
        # close[i] > sma[i]. Walking i=1..9 by hand, only i=6 qualifies
        # (9 <= 10.0 and 10 > 9.67).
        ctx = ctx_of(self.CLOSE_10)
        flags = entry_flags("INPUT p = 3\nENTRY crossover(close, sma(close, p))", ctx)
        assert [i for i, f in enumerate(flags) if f] == [6]

    def test_exit_and_alert_sections(self) -> None:
        # entry close > 5 -> True everywhere; exit close < 10 -> only i=5 (9<10);
        # alert volume > sma(volume,2) AND volume > 5: volume=[1]*9+[9] ->
        # i9: sma2=(1+9)/2=5, 9>5 and 9>5 -> True. The AND volume > 5 guard
        # suppresses the sma warm-up zeros (sma=0.0 at i0 would otherwise fire).
        volume = [1.0] * 9 + [9.0]
        ctx = ctx_of(self.CLOSE_10, volume=volume)
        decisions = run_over_series(
            compile_source(
                "ENTRY close > 5\n"
                "EXIT close < 10\n"
                "ALERT volume > sma(volume, 2) AND volume > 5"
            ),
            ctx,
        )
        assert all(d.entry for d in decisions)
        assert [d.index for d in decisions if d.exit] == [5]
        assert [d.index for d in decisions if d.alert] == [9]

    def test_default_exit_alert_false(self) -> None:
        ctx = ctx_of(self.CLOSE_10)
        decisions = run_over_series(compile_source("ENTRY close > 5"), ctx)
        assert all(d.exit is False and d.alert is False for d in decisions)

    def test_risk_passthrough(self) -> None:
        ctx = ctx_of(self.CLOSE_10)
        program = compile_source(
            "ENTRY close > 5\n"
            "RISK stop_loss_pct = 2.0, take_profit_pct = 4.0, "
            "trailing_pct = 1.0, max_position_pct = 25.0"
        )
        decisions = run_over_series(program, ctx)
        assert all(
            d.risk
            == RiskSpec(
                stop_loss_pct=2.0,
                take_profit_pct=4.0,
                trailing_pct=1.0,
                max_position_pct=25.0,
            )
            for d in decisions
        )

    def test_inputs_passthrough(self) -> None:
        ctx = ctx_of(self.CLOSE_10)
        decisions = run_over_series(
            compile_source("INPUT p = 3\nENTRY close > p"), ctx
        )
        assert all(d.inputs == {"p": 3.0} for d in decisions)

    def test_decision_type_and_index(self) -> None:
        ctx = ctx_of([1.0, 2, 3])
        decisions = run_over_series(compile_source("ENTRY close > 0"), ctx)
        assert all(isinstance(d, Decision) for d in decisions)
        assert [d.index for d in decisions] == [0, 1, 2]

    def test_division_by_zero_is_deterministic_zero(self) -> None:
        # (close - close) evaluates to 0 at runtime; close/0 -> 0.0 by the
        # documented guard, so `0.0 > 0` is False everywhere, no exception.
        ctx = ctx_of([1.0, 2, 3])
        flags = entry_flags("ENTRY close / (close - close) > 0", ctx)
        assert flags == [False, False, False]

    def test_evaluate_at_matches_run_over_series(self) -> None:
        ctx = ctx_of(self.CLOSE_10)
        program = compile_source("INPUT p = 3\nENTRY crossover(close, sma(close, p))")
        prepared = prepare(program, ctx)
        sweep = run_over_series(program, ctx)
        for i in range(len(self.CLOSE_10)):
            assert evaluate_at(prepared, i) == sweep[i]


class TestMissingSeries:
    def test_missing_mtf_raises(self) -> None:
        ctx = ctx_of([1.0, 2, 3])
        program = compile_source("ENTRY D1.close > 0")
        with pytest.raises(DSLError) as excinfo:
            run_over_series(program, ctx)
        assert excinfo.value.code == "RUN_MISSING_MTF_SERIES"

    def test_missing_mtf_base_raises(self) -> None:
        ctx = SeriesContext(
            open=[1.0, 1],
            high=[1.0, 1],
            low=[1.0, 1],
            close=[1.0, 1],
            volume=[1.0, 1],
            mtf={"D1": {"close": [1.0, 1]}},
        )
        program = compile_source("ENTRY D1.volume > 0")
        with pytest.raises(DSLError) as excinfo:
            run_over_series(program, ctx)
        assert excinfo.value.code == "RUN_MISSING_MTF_SERIES"

    def test_mtf_provided_works(self) -> None:
        ctx = SeriesContext(
            open=[1.0, 1],
            high=[1.0, 1],
            low=[1.0, 1],
            close=[1.0, 1],
            volume=[1.0, 1],
            mtf={"D1": {"close": [2.0, 2]}},
        )
        decisions = run_over_series(compile_source("ENTRY D1.close > 1"), ctx)
        assert [d.entry for d in decisions] == [True, True]

    def test_missing_symbol_raises(self) -> None:
        ctx = ctx_of([1.0, 2, 3])
        program = compile_source('ENTRY sym("FAM").close > 0')
        with pytest.raises(DSLError) as excinfo:
            run_over_series(program, ctx)
        assert excinfo.value.code == "RUN_MISSING_SYMBOL_SERIES"

    def test_symbol_provided_works(self) -> None:
        ctx = SeriesContext(
            open=[1.0, 1],
            high=[1.0, 1],
            low=[1.0, 1],
            close=[1.0, 1],
            volume=[1.0, 1],
            symbols={"FAM": {"close": [3.0, 3]}},
        )
        decisions = run_over_series(
            compile_source('ENTRY sym("FAM").close > 2'), ctx
        )
        assert [d.entry for d in decisions] == [True, True]

    def test_mtf_length_mismatch_raises(self) -> None:
        ctx = SeriesContext(
            open=[1.0, 1],
            high=[1.0, 1],
            low=[1.0, 1],
            close=[1.0, 1],
            volume=[1.0, 1],
            mtf={"D1": {"close": [1.0]}},
        )
        with pytest.raises(DSLError) as excinfo:
            run_over_series(compile_source("ENTRY D1.close > 0"), ctx)
        assert excinfo.value.code == "RUN_SERIES_LENGTH_MISMATCH"

    def test_index_out_of_range(self) -> None:
        ctx = ctx_of([1.0, 2, 3])
        prepared = prepare(compile_source("ENTRY close > 0"), ctx)
        with pytest.raises(DSLError) as excinfo:
            evaluate_at(prepared, 3)
        assert excinfo.value.code == "RUN_INDEX_OUT_OF_RANGE"


class TestDeterminismAndNoLookahead:
    def test_run_twice_identical(self) -> None:
        ctx = ctx_of([3.0, 1, 4, 1, 5, 9, 2, 6, 5, 3])
        program = compile_source(
            "INPUT p = 3\n"
            "ENTRY crossover(close, sma(close, p))\n"
            "EXIT crossunder(close, sma(close, p))\n"
            "ALERT rsi(close, 4) > 60"
        )
        first = run_over_series(program, ctx)
        second = run_over_series(program, ctx)
        assert first == second

    def test_future_bars_do_not_change_past_decisions(self) -> None:
        # THE no-look-ahead regression: a 20-bar prefix and the same series
        # extended to 40 bars must produce identical decisions for bars 0..19
        # even though the program uses windowed and recursive indicators.
        base = [float(((i * 7) % 13) + 2) for i in range(40)]  # deterministic
        short_ctx = ctx_of(base[:20], high=[v + 1 for v in base[:20]],
                           low=[v - 1 for v in base[:20]])
        long_ctx = ctx_of(base, high=[v + 1 for v in base], low=[v - 1 for v in base])
        program = compile_source(
            "INPUT p = 4\n"
            "ENTRY ema(close, p) > ref(close, 2) AND close > lowest(low, 5)\n"
            "EXIT crossunder(close, sma(close, p))\n"
            "ALERT close > highest(high, 8) * 0.9"
        )
        short = run_over_series(program, short_ctx)
        long = run_over_series(program, long_ctx)
        assert short == long[:20]

    def test_prepared_carries_ctx_digest(self) -> None:
        ctx = ctx_of([1.0, 2, 3])
        prepared = prepare(compile_source("ENTRY close > 0"), ctx)
        assert prepared.ctx_digest == prepare(
            compile_source("ENTRY close > 0"), ctx
        ).ctx_digest
        other = prepare(compile_source("ENTRY close > 0"), ctx_of([1.0, 2, 4]))
        assert other.ctx_digest != prepared.ctx_digest

    def test_prepared_n_bars(self) -> None:
        prepared = prepare(compile_source("ENTRY close > 0"), ctx_of([1.0, 2, 3]))
        assert prepared.n_bars == 3
        assert isinstance(prepared.program, Program)
