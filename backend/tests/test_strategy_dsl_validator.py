"""MASTER-RADAR directive §C2 — validator/budget tests for the RSL-1 DSL.

Covers: AST node budget, expression depth budget, source-length budget, MTF
and symbol budgets, look-ahead rejection, constant division-by-zero, RISK
range validation and unused-input advisories (which must not raise).
"""
from __future__ import annotations

import pytest

from app.engines.strategy_dsl import (
    DSLError,
    compile_source,
    parse,
    validate,
)


def compile_failing(source: str) -> DSLError:
    with pytest.raises(DSLError) as excinfo:
        compile_source(source)
    return excinfo.value


def balanced_sum_expr(leaves: int) -> str:
    """Balanced binary ``+`` tree over ``close`` leaves (shallow depth)."""
    if leaves == 1:
        return "close"
    left = leaves // 2
    return f"({balanced_sum_expr(left)} + {balanced_sum_expr(leaves - left)})"


class TestNodeBudget:
    def test_about_520_nodes_rejected(self) -> None:
        # 260 leaves + 259 BinOps + Program = 520 nodes
        source = f"ENTRY {balanced_sum_expr(260)} > 0"
        err = compile_failing(source)
        assert err.code == "BUDGET_NODES"

    def test_512_node_boundary_accepted(self) -> None:
        # 240 leaves + 239 BinOps + Cmp + Num + Program = 482 nodes (under budget)
        source = f"ENTRY {balanced_sum_expr(240)} > 0"
        program = compile_source(source)  # must not raise
        assert program.entry is not None

    def test_validator_function_counts(self) -> None:
        from app.engines.strategy_dsl.validator import count_nodes

        program = parse("ENTRY close > 0")
        # Program + Cmp + SeriesBase + Num + two DEFAULT_FALSE sentinels
        assert count_nodes(program) == 6


class TestDepthBudget:
    def test_depth_bomb_rejected(self) -> None:
        # 70 nested unary minus => AST depth 71 > 64, node count 72 <= 512
        source = "ENTRY " + "-" * 70 + "close > 0"
        err = compile_failing(source)
        assert err.code == "BUDGET_DEPTH"

    def test_depth_within_budget_ok(self) -> None:
        source = "ENTRY " + "-" * 60 + "close > 0"
        program = compile_source(source)
        assert program.entry is not None


class TestSourceBudget:
    def test_long_source_rejected(self) -> None:
        source = "ENTRY " + "0" * 4200
        err = compile_failing(source)
        assert err.code == "BUDGET_SOURCE_LEN"

    def test_source_limit_boundary(self) -> None:
        # 4096 chars exactly: passes the length budget (then fails on syntax,
        # proving the length budget itself did not fire).
        source = "ENTRY " + "0" * 4090
        with pytest.raises(DSLError) as excinfo:
            compile_source(source)
        assert excinfo.value.code != "BUDGET_SOURCE_LEN"


class TestMtfSymbolBudgets:
    def test_four_timeframes_rejected(self) -> None:
        source = "ENTRY D1.close + W1.close + M1.close + H4.close > 0"
        err = compile_failing(source)
        assert err.code == "BUDGET_MTF"

    def test_three_timeframes_ok(self) -> None:
        program = compile_source("ENTRY D1.close + W1.close + M1.close > 0")
        assert len(program.mtf_refs) == 3

    def test_three_symbols_rejected(self) -> None:
        source = 'ENTRY sym("A").close + sym("B").close + sym("C").close > 0'
        err = compile_failing(source)
        assert err.code == "BUDGET_SYMBOLS"

    def test_two_symbols_ok(self) -> None:
        program = compile_source('ENTRY sym("A").close + sym("B").close > 0')
        assert len(program.symbol_refs) == 2


class TestLookahead:
    def test_negative_ref_literal(self) -> None:
        err = compile_failing("ENTRY ref(close, -1) > 0")
        assert err.code == "LOOKAHEAD_NEGATIVE_REF"

    def test_negative_ref_via_input(self) -> None:
        err = compile_failing("INPUT back = -2\nENTRY ref(close, back) > 0")
        assert err.code == "LOOKAHEAD_NEGATIVE_REF"

    def test_zero_ref_ok(self) -> None:
        program = compile_source("ENTRY ref(close, 0) == close")
        assert program.entry is not None


class TestDivisionGuard:
    def test_constant_zero_denominator_rejected(self) -> None:
        err = compile_failing("ENTRY close / 0 > 1")
        assert err.code == "SEM_DIV_BY_ZERO_CONSTANT"

    def test_constant_zero_denominator_nested(self) -> None:
        err = compile_failing("ENTRY close / (2 * 0) > 1")
        assert err.code == "SEM_DIV_BY_ZERO_CONSTANT"

    def test_dynamic_zero_denominator_allowed_at_compile(self) -> None:
        # (close - close) is not a compile-time constant; runtime guards x/0 -> 0.0
        program = compile_source("ENTRY close / (close - close) > 0")
        assert program.entry is not None


class TestRiskRanges:
    def test_stop_loss_above_range(self) -> None:
        err = compile_failing("ENTRY close > 0\nRISK stop_loss_pct = 200")
        assert err.code == "SEM_RISK_RANGE"

    def test_take_profit_above_range(self) -> None:
        err = compile_failing("ENTRY close > 0\nRISK take_profit_pct = 1000.5")
        assert err.code == "SEM_RISK_RANGE"

    def test_trailing_negative(self) -> None:
        err = compile_failing("ENTRY close > 0\nRISK trailing_pct = -1")
        assert err.code == "SEM_RISK_RANGE"

    def test_max_position_below_range(self) -> None:
        err = compile_failing("ENTRY close > 0\nRISK max_position_pct = 0.05")
        assert err.code == "SEM_RISK_RANGE"

    def test_risk_boundary_values_ok(self) -> None:
        program = compile_source(
            "ENTRY close > 0\n"
            "RISK stop_loss_pct = 0, take_profit_pct = 1000, "
            "trailing_pct = 100, max_position_pct = 0.1"
        )
        assert program.risk is not None


class TestPeriods:
    def test_rsi_period_one_rejected(self) -> None:
        err = compile_failing("ENTRY rsi(close, 1) > 0")
        assert err.code == "SEM_PERIOD_INVALID"

    def test_sma_period_zero_rejected(self) -> None:
        err = compile_failing("ENTRY sma(close, 0) > 0")
        assert err.code == "SEM_PERIOD_INVALID"

    def test_stdev_float_period_rejected(self) -> None:
        err = compile_failing("ENTRY stdev(close, 2.5) > 0")
        assert err.code == "SEM_PERIOD_INVALID"

    def test_period_via_input_ok(self) -> None:
        program = compile_source("INPUT p = 14\nENTRY rsi(close, p) > 0")
        assert program.entry is not None

    def test_non_literal_period_rejected(self) -> None:
        # a call is not a number: caught statically by the type layer
        err = compile_failing("ENTRY sma(close, sma(close, 5)) > 0")
        assert err.code == "TYPE_ARG_NOT_NUMBER"


class TestAdvisories:
    def test_unused_input_advisory_without_raise(self) -> None:
        program = compile_source("INPUT unused = 5\nENTRY close > 0")
        findings = validate(program)
        assert "unused input: unused" in findings

    def test_default_exit_alert_advisories(self) -> None:
        program = compile_source("ENTRY close > 0")
        findings = validate(program)
        assert "no EXIT section: default constant false" in findings
        assert "no ALERT section: default constant false" in findings

    def test_no_advisories_for_full_program(self) -> None:
        program = compile_source(
            "INPUT p = 5\n"
            "ENTRY close > sma(close, p)\n"
            "EXIT close < 0\n"
            "ALERT volume > 0\n"
        )
        assert validate(program) == []

    def test_whitelist_defensive_check(self) -> None:
        # A hand-built AST with a non-whitelisted call must be caught by the
        # validator's defensive walk even if it bypassed the parser.
        from app.engines.strategy_dsl import Call, Cmp, Num, Program, SeriesBase
        from app.engines.strategy_dsl.errors import DSLSemanticError

        rogue = Call("strftime", (SeriesBase("close"), Num(0)))
        program = Program(
            inputs={},
            risk=None,
            entry=Cmp(">", rogue, Num(0)),
            exit=Num(0),
            alert=Num(0),
            mtf_refs=(),
            symbol_refs=(),
            source_digest="",
        )
        with pytest.raises(DSLSemanticError) as excinfo:
            validate(program)
        assert excinfo.value.code == "SEM_UNKNOWN_FN"
