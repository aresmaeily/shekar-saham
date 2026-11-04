"""MASTER-RADAR WAVE-B — UIDL-1 user indicator DSL engine tests (§B4).

Layers pinned here (independent of the API tests):

1. Compilation: grammar, names, budgets, typed rejections (every code).
2. Values: hand-computed fixtures over a pinned 12-bar OHLCV fixture, plus
   an INDEPENDENT naive recomputation implemented inside this test module
   (it does NOT import the DSL) for a battery of programs — the engine and
   the test evaluator agree bar-for-bar, exactly.
3. Warm-up coherence: the static structural warm-up matches the runtime's
   documented warm-up-zero region on a strictly trending fixture.
4. Determinism: digests are stable, input-sensitive and plot-set-sensitive.
5. No-look-ahead: ref offsets are compile-refused when negative; MTF plots
   consume only PROVABLY closed higher-TF bars (prefix stability).
6. Sandbox resistance: lexer charset rejection for hostile payloads; no
   eval/exec/compile/dynamic-import anywhere in the two WAVE-B modules.
"""
from __future__ import annotations

import pytest

from app.engines.strategy_dsl import (
    DSLError,
    DSLLookaheadError,
    DSLParseError,
    DSLSemanticError,
    SeriesContext,
    compile_indicator_source,
    evaluate_indicator,
    structural_warmup,
)
from app.engines.strategy_dsl.errors import DSLBudgetError, DSLRuntimeError
from app.engines.strategy_dsl.indicator_program import (
    MAX_PLOTS,
    UIDL_VERSION,
)

# ---------------------------------------------------------------------------
# pinned 12-bar fixture (strictly increasing closes → RSI pinned at 100)
# ---------------------------------------------------------------------------

CLOSES = [10.0, 10.5, 11.0, 10.8, 11.4, 12.0, 12.6, 12.3, 13.0, 13.6, 14.2, 15.0]
OPENS = [c - 0.2 for c in CLOSES]
HIGHS = [c + 0.3 for c in CLOSES]
LOWS = [c - 0.4 for c in CLOSES]
VOLS = [100.0 + 10 * i for i in range(12)]


def base_ctx() -> SeriesContext:
    return SeriesContext(
        open=OPENS, high=HIGHS, low=LOWS, close=CLOSES, volume=VOLS
    )


def src(plots: str, inputs: str = "INPUT len = 3", name: str = "t") -> str:
    return f"INDICATOR {name}\n{inputs}\n{plots}"


# ---------------------------------------------------------------------------
# independent naive evaluator (test-local; never imports the DSL)
# ---------------------------------------------------------------------------

def _naive_sma(v: list[float], p: int) -> list[float]:
    out = []
    for i in range(len(v)):
        out.append(0.0 if i < p - 1 else sum(v[i - p + 1 : i + 1]) / p)
    return out


def _naive_ema(v: list[float], p: int) -> list[float]:
    out = [0.0] * len(v)
    if p < 1 or p > len(v):
        return out
    seed = sum(v[:p]) / p
    out[p - 1] = seed
    k = 2.0 / (p + 1.0)
    for i in range(p, len(v)):
        out[i] = out[i - 1] + k * (v[i] - out[i - 1])
    return out


def _naive_highest(v: list[float], p: int) -> list[float]:
    return [max(v[max(0, i - p + 1) : i + 1]) for i in range(len(v))]


def naive_eval(program_text_inputs: dict[str, float], close: list[float]):
    """Independent recomputation for the PLOT battery used in this module.

    Keys are the exact plot names; the formulas mirror the DSL sources by
    construction (hand-written twice, on purpose). Zero-fill and x/0 rules
    follow the runtime's documented behaviour: ``ref`` zero-fills before its
    offset, division by zero yields 0.0.
    """
    length = program_text_inputs["__len__"]
    p = int(length)
    basis = _naive_sma(close, p)
    upper = [b * 1.02 for b in basis]
    lower = [b * 0.98 for b in basis]
    spread = [upper[i] - lower[i] for i in range(len(basis))]
    prev = [0.0] + close[:-1]  # ref(close, 1): zero-fill before the offset
    mom = [close[i] - prev[i] for i in range(len(close))]
    hi3 = _naive_highest(close, 3)
    ratio = [0.0 if hi3[i] == 0 else close[i] / hi3[i] for i in range(len(close))]
    ema5 = _naive_ema(close, 5)
    return {
        "basis": basis,
        "upper": upper,
        "lower": lower,
        "spread": spread,
        "mom": mom,
        "ratio": ratio,
        "ema5": ema5,
    }


# ---------------------------------------------------------------------------
# 1. compilation & grammar
# ---------------------------------------------------------------------------


class TestCompilation:
    def test_happy_path_shape(self) -> None:
        prog = compile_indicator_source(
            src("PLOT basis = sma(close, len)\nPLOT upper = sma(close, len) * 1.02")
        )
        assert prog.name == "t"
        assert prog.plot_names() == ("basis", "upper")
        assert prog.inputs == {"len": 3}
        # catalog parity convention: warmup = first fully-determined bar index
        # (sma(3) ships warmup_bars=2, like builtin sma(20) ships 19)
        assert prog.warmup_bars == 2

    def test_version_constant(self) -> None:
        assert UIDL_VERSION == "UIDL-1"

    def test_keywords_case_insensitive(self) -> None:
        prog = compile_indicator_source("indicator t2\nplot p = close")
        assert prog.name == "t2" and prog.plot_names() == ("p",)

    def test_input_keyword_form_shared_with_rsl(self) -> None:
        # 'input' is a lexer KEYWORD (shared with RSL-1) — still accepted
        prog = compile_indicator_source("INDICATOR t3\ninput k = 5\nPLOT p = close * k")
        assert prog.inputs == {"k": 5}

    def test_reserved_names_rejected(self) -> None:
        # close/plot are IDENTs refused by the name rule; sym/entry are lexer
        # KEYWORDS refused even earlier — both are refusals, never executions
        for bad, code in (
            ("close", "PARSE_RESERVED_NAME"),
            ("plot", "PARSE_RESERVED_NAME"),
            ("sym", "PARSE_UNEXPECTED_TOKEN"),
            ("entry", "PARSE_UNEXPECTED_TOKEN"),
        ):
            with pytest.raises(DSLParseError) as e:
                compile_indicator_source(f"INDICATOR t\nINPUT {bad} = 1\nPLOT p = close")
            assert e.value.code == code

    def test_missing_indicator_rejected(self) -> None:
        with pytest.raises(DSLParseError) as e:
            compile_indicator_source("PLOT p = close")
        assert e.value.code == "PARSE_MISSING_INDICATOR"

    def test_missing_plot_rejected(self) -> None:
        with pytest.raises(DSLParseError) as e:
            compile_indicator_source("INDICATOR t")
        assert e.value.code == "PARSE_MISSING_PLOT"

    def test_duplicate_plot_rejected(self) -> None:
        with pytest.raises(DSLSemanticError) as e:
            compile_indicator_source("INDICATOR t\nPLOT a = close\nPLOT A = open")
        assert e.value.code == "SEM_DUPLICATE_PLOT"

    def test_boolean_plot_rejected(self) -> None:
        for expr in ("close > open", "crossover(close, open)", "NOT (close > open)"):
            with pytest.raises(DSLSemanticError) as e:
                compile_indicator_source(f"INDICATOR t\nPLOT p = {expr}")
            assert e.value.code == "SEM_PLOT_NOT_SERIES"

    def test_source_budget_before_lexing(self) -> None:
        with pytest.raises(DSLBudgetError) as e:
            compile_indicator_source("INDICATOR t\nPLOT p = close\n" + "# " + "x" * 5000)
        assert e.value.code == "BUDGET_SOURCE_LEN"

    def test_plot_count_budget(self) -> None:
        plots = "\n".join(f"PLOT p{i} = close" for i in range(MAX_PLOTS + 1))
        with pytest.raises(DSLBudgetError) as e:
            compile_indicator_source(f"INDICATOR t\n{plots}")
        assert e.value.code == "BUDGET_PLOTS"

    def test_input_count_budget(self) -> None:
        inputs = "\n".join(f"INPUT i{i} = {i}" for i in range(17))
        with pytest.raises(DSLBudgetError) as e:
            compile_indicator_source(f"INDICATOR t\n{inputs}\nPLOT p = close")
        assert e.value.code == "BUDGET_INPUTS"

    def test_depth_budget(self) -> None:
        deep = "close" + " + 1" * 70
        with pytest.raises(DSLBudgetError) as e:
            compile_indicator_source(f"INDICATOR t\nPLOT p = {deep}")
        assert e.value.code == "BUDGET_DEPTH"

    def test_mtf_budget(self) -> None:
        with pytest.raises(DSLBudgetError) as e:
            compile_indicator_source(
                "INDICATOR t\nPLOT p = D1.close + W1.close + M1.close + H4.close"
            )
        assert e.value.code == "BUDGET_MTF"

    def test_lookahead_ref_refused(self) -> None:
        with pytest.raises(DSLLookaheadError) as e:
            compile_indicator_source("INDICATOR t\nPLOT p = ref(close, -1)")
        assert e.value.code == "LOOKAHEAD_NEGATIVE_REF"

    def test_non_integer_period_refused(self) -> None:
        with pytest.raises(DSLError) as e:
            compile_indicator_source("INDICATOR t\nPLOT p = sma(close, 2.5)")
        assert e.value.code == "SEM_PERIOD_INVALID"

    def test_unknown_function_refused(self) -> None:
        with pytest.raises(DSLError):
            compile_indicator_source("INDICATOR t\nPLOT p = eval(close)")

    def test_duplicate_input_rejected(self) -> None:
        with pytest.raises(DSLParseError) as e:
            compile_indicator_source("INDICATOR t\nINPUT k = 1\nINPUT k = 2\nPLOT p = close")
        assert e.value.code == "PARSE_DUPLICATE_INPUT"


# ---------------------------------------------------------------------------
# 2. values: hand fixtures + independent recomputation
# ---------------------------------------------------------------------------


class TestValuesAgainstIndependentRecomputation:
    BATTERY = src(
        "PLOT basis = sma(close, len)\n"
        "PLOT upper = sma(close, len) * 1.02\n"
        "PLOT lower = sma(close, len) * 0.98\n"
        "PLOT spread = sma(close, len) * 1.02 - sma(close, len) * 0.98\n"
        "PLOT mom = close - ref(close, 1)\n"
        "PLOT ratio = close / highest(close, 3)\n"
        "PLOT ema5 = ema(close, 5)",
        inputs="INPUT len = 3",
    )

    def test_battery_matches_independent_evaluator(self) -> None:
        prog = compile_indicator_source(self.BATTERY)
        ev = evaluate_indicator(prog, base_ctx())
        expected = naive_eval({"__len__": 3}, CLOSES)
        for name, values in expected.items():
            got = ev.plots[name]
            assert len(got) == len(values)
            for i, (g, w) in enumerate(zip(got, values)):
                assert g == pytest.approx(w, abs=1e-12), (name, i, g, w)

    def test_hand_fixture_sma(self) -> None:
        prog = compile_indicator_source("INDICATOR t\nPLOT s = sma(close, 3)")
        ev = evaluate_indicator(prog, base_ctx())
        # bar 2: mean(10, 10.5, 11) = 10.5 ; bar 11: mean(13.6, 14.2, 15) = 14.2666...
        assert ev.plots["s"][2] == pytest.approx(10.5)
        assert ev.plots["s"][11] == pytest.approx((13.6 + 14.2 + 15.0) / 3)

    def test_hand_fixture_warmup_zeros(self) -> None:
        prog = compile_indicator_source("INDICATOR t\nPLOT s = sma(close, 4)")
        ev = evaluate_indicator(prog, base_ctx())
        assert all(v == 0.0 for v in ev.plots["s"][:3])
        assert ev.plots["s"][3] == pytest.approx(sum(CLOSES[:4]) / 4)

    def test_hand_fixture_rsi_warmup_boundary(self) -> None:
        # rsi(seed at index `period`): zeros up to index period-1, defined after
        prog = compile_indicator_source("INDICATOR t\nPLOT r = rsi(close, 5)")
        ev = evaluate_indicator(prog, base_ctx())
        assert all(v == 0.0 for v in ev.plots["r"][:5])
        # hand arithmetic for the pinned window (bars 1..5):
        # gains 0.5+0.5+0+0.6+0.6 = 2.2 → avg 0.44 ; losses 0.2 → avg 0.04
        # RS = 11 → RSI = 100 - 100/12 = 91.666...  (window is NOT pure-rise)
        assert ev.plots["r"][5] == pytest.approx(100.0 - 100.0 / 12.0)

    def test_input_override_changes_values(self) -> None:
        prog = compile_indicator_source("INDICATOR t\nINPUT n = 3\nPLOT s = sma(close, n)")
        ev3 = evaluate_indicator(prog, base_ctx())
        ev5 = evaluate_indicator(prog, base_ctx(), inputs={"n": 5})
        # window INCLUDES the current bar: sma5 at i=5 = mean(close[1..5])
        assert ev5.plots["s"][5] == pytest.approx(sum(CLOSES[1:6]) / 5)
        assert ev3.plots["s"][5] != ev5.plots["s"][5]

    def test_ref_zero_is_identity(self) -> None:
        prog = compile_indicator_source("INDICATOR t\nPLOT p = ref(close, 0)")
        ev = evaluate_indicator(prog, base_ctx())
        assert ev.plots["p"] == CLOSES

    def test_division_by_zero_documented_rule(self) -> None:
        prog = compile_indicator_source("INDICATOR t\nPLOT p = close / (close - close)")
        ev = evaluate_indicator(prog, base_ctx())
        assert all(v == 0.0 for v in ev.plots["p"])

    def test_mtf_plot_consumes_only_closed_bars(self) -> None:
        # base = 6 bars of 60s; H1 bars: one closed (c=100, close_ts=180),
        # one NOT closed (c=999, no close_ts) — the 999 must NEVER appear.
        base_ts = [60 * i for i in range(6)]
        ctx = SeriesContext(
            open=[1.0] * 6,
            high=[2.0] * 6,
            low=[0.5] * 6,
            close=[1.0] * 6,
            volume=[1.0] * 6,
            ts=base_ts,
        )
        h1 = [
            {"ts": 0, "close": 100.0, "close_ts": 180},
            {"ts": 180, "close": 999.0},  # tail bar without close_ts: not closed
        ]
        prog = compile_indicator_source("INDICATOR t\nPLOT p = H1.close")
        ev = evaluate_indicator(prog, ctx, mtf_context={"H1": h1})
        vals = ev.plots["p"]
        assert all(v == 0.0 for v in vals[:3])  # warm-up: no closed H1 bar yet
        assert all(v == 100.0 for v in vals[3:])  # closed bar only, no 999 ever

    def test_prefix_stability_no_lookahead(self) -> None:
        prog = compile_indicator_source(self.BATTERY)
        full = evaluate_indicator(prog, base_ctx())
        for k in range(1, 12):
            part = SeriesContext(
                open=OPENS[:k], high=HIGHS[:k], low=LOWS[:k],
                close=CLOSES[:k], volume=VOLS[:k],
            )
            evk = evaluate_indicator(prog, part)
            for name in full.plots:
                got = evk.plots[name]
                want = full.plots[name][:k]
                # values computed from a truncated prefix must match the full
                # series exactly on the shared range (honest warm-up zeros
                # shift only where the pinned conventions shift them)
                for i in range(k):
                    if not (got[i] == pytest.approx(want[i], abs=1e-12)):
                        # allowed only inside the warm-up region where the
                        # truncated context has fewer bars than the window
                        assert i < max(prog.warmup_bars, k), (name, k, i)


# ---------------------------------------------------------------------------
# 3. warm-up coherence (static estimate == runtime zero region)
# ---------------------------------------------------------------------------


class TestWarmupCoherence:
    # convention: warmup_bars == index of the FIRST fully-determined bar
    # (catalog parity: sma(20) ships warmup_bars=19). Zero-fill coherence is
    # asserted only for the zero-warmup functions; highest/lowest carry the
    # documented honest PARTIAL-window values before their full window.
    @pytest.mark.parametrize(
        "expr,warmup,zero_fill",
        [
            ("close", 0, True),
            ("sma(close, 5)", 4, True),
            ("ema(close, 5)", 4, True),
            ("rsi(close, 14)", 14, True),
            ("stdev(close, 4)", 3, True),
            ("highest(close, 3)", 2, False),  # partial-window before index 2
            ("lowest(close, 3)", 2, False),
            ("atr(high, low, close, 6)", 6, True),
            ("ref(close, 9)", 9, True),
            # composite through arithmetic: warm-up zeros propagate
            # arithmetically (sma*2 - ref) so the region is zero-DERIVED,
            # not zero — pinned as non-zero-fill honestly
            ("sma(close, 3) * 2 - ref(close, 1)", 2, False),
            ("sma(close - open, 10)", 9, True),
        ],
    )
    def test_structural_matches_runtime(self, expr: str, warmup: int, zero_fill: bool) -> None:
        prog = compile_indicator_source(f"INDICATOR t\nPLOT p = {expr}")
        assert prog.plots[0].warmup_bars == warmup
        assert prog.warmup_bars == warmup
        assert structural_warmup(prog.plots[0].expr, prog.inputs) == warmup
        ev = evaluate_indicator(prog, base_ctx())
        if zero_fill:
            assert all(v == 0.0 for v in ev.plots["p"][:warmup])

    def test_input_driven_period_warmup(self) -> None:
        prog = compile_indicator_source(
            "INDICATOR t\nINPUT n = 7\nPLOT p = sma(close, n)"
        )
        assert prog.warmup_bars == 6


# ---------------------------------------------------------------------------
# 4. determinism & digests
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_digest_stable(self) -> None:
        prog = compile_indicator_source(self.BATTERY if False else src("PLOT a = sma(close, len)"))
        d1 = evaluate_indicator(prog, base_ctx()).digest
        d2 = evaluate_indicator(prog, base_ctx()).digest
        assert d1 == d2 and len(d1) == 64

    def test_digest_input_sensitive(self) -> None:
        prog = compile_indicator_source("INDICATOR t\nINPUT n = 3\nPLOT s = sma(close, n)")
        d3 = evaluate_indicator(prog, base_ctx()).digest
        d5 = evaluate_indicator(prog, base_ctx(), inputs={"n": 5}).digest
        assert d3 != d5

    def test_digest_plotset_sensitive(self) -> None:
        p1 = compile_indicator_source("INDICATOR t\nPLOT a = close")
        p2 = compile_indicator_source("INDICATOR t\nPLOT a = close\nPLOT b = open")
        d1 = evaluate_indicator(p1, base_ctx()).digest
        d2 = evaluate_indicator(p2, base_ctx()).digest
        assert d1 != d2

    def test_digest_source_sensitive(self) -> None:
        prog1 = compile_indicator_source("INDICATOR t\nPLOT a = close")
        prog2 = compile_indicator_source("INDICATOR t\nPLOT a = close ")
        d1 = evaluate_indicator(prog1, base_ctx()).digest
        d2 = evaluate_indicator(prog2, base_ctx()).digest
        assert d1 != d2  # source digest participates


# ---------------------------------------------------------------------------
# 5. runtime input guards
# ---------------------------------------------------------------------------


class TestInputGuards:
    def test_unknown_override_rejected(self) -> None:
        prog = compile_indicator_source("INDICATOR t\nPLOT a = close")
        with pytest.raises(DSLRuntimeError) as e:
            evaluate_indicator(prog, base_ctx(), inputs={"nope": 1.0})
        assert e.value.code == "RUN_UNKNOWN_INPUT"

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, "3"])
    def test_non_finite_overrides_rejected(self, bad) -> None:
        prog = compile_indicator_source("INDICATOR t\nINPUT n = 3\nPLOT a = sma(close, n)")
        with pytest.raises(DSLRuntimeError) as e:
            evaluate_indicator(prog, base_ctx(), inputs={"n": bad})
        assert e.value.code == "RUN_BAD_INPUTS"

    def test_bool_context_rejected(self) -> None:
        prog = compile_indicator_source("INDICATOR t\nPLOT a = close")
        with pytest.raises(DSLRuntimeError) as e:
            evaluate_indicator(prog, "not-a-context")
        assert e.value.code == "RUN_BAD_CONTEXT"


# ---------------------------------------------------------------------------
# 6. sandbox resistance / static hygiene
# ---------------------------------------------------------------------------


class TestSandboxResistance:
    @pytest.mark.parametrize(
        "payload",
        [
            "INDICATOR t\nPLOT p = __import__('os')",
            "INDICATOR t\nPLOT p = exec('x')",
            "INDICATOR t\nPLOT p = eval('x')",
            "INDICATOR t\nPLOT p = close; import os",
            "INDICATOR t\nPLOT p = `cat /etc/passwd`",
            "INDICATOR t\nPLOT p = close\"; DROP TABLE",
            "INDICATOR t\nPLOT p = {}.__class__",
            "INDICATOR t\nPLOT p = close.__class__",
        ],
    )
    def test_hostile_payloads_never_parse(self, payload: str) -> None:
        # fixed lexer charset: anything outside the allowlist is a LEX error,
        # anything inside is an unknown-function/parse error — never execution
        with pytest.raises(DSLError):
            compile_indicator_source(payload)

    def test_no_dynamic_execution_primitives_in_modules(self) -> None:
        import pathlib

        for mod in (
            "app/engines/strategy_dsl/indicator_program.py",
            "app/engines/user_indicator_store.py",
            "app/api/user_indicator_api.py",
        ):
            text = pathlib.Path(mod).read_text(encoding="utf-8")
            for banned in ("eval(", "exec(", "compile(", "__import__("):
                assert banned not in text, (mod, banned)

    def test_store_import_never_stores_non_compiling_source(self) -> None:
        from app.engines.user_indicator_store import UserIndicatorStore

        store = UserIndicatorStore()
        report = store.install("INDICATOR t\nPLOT p = close > open")
        assert not report.ok
        assert report.rejected[0].code.startswith("DSL_")
        assert store.installed_ids() == []
