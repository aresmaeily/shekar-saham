"""MASTER-RADAR directive §C2 — type-checker tests for the RSL-1 strategy DSL.

Covers arity mismatches, arithmetic/comparison/boolean type rules, unknown
functions and inputs, invalid MTF timeframes, invalid ref bases, polymorphic
abs/min/max and INPUT int/float handling.
"""
from __future__ import annotations

import pytest

from app.engines.strategy_dsl import (
    DSLError,
    DSLTypeError,
    SeriesContext,
    compile_source,
    evaluate,
    parse,
    typecheck,
)


def compile_failing(source: str) -> DSLTypeError:
    """Compile ``source`` and return the raised DSLTypeError (fails otherwise)."""
    with pytest.raises(DSLError) as excinfo:
        compile_source(source)
    err = excinfo.value
    assert isinstance(err, DSLTypeError), f"expected TYPE_*, got {err.code}"
    return err


class TestArity:
    def test_sma_one_arg(self) -> None:
        err = compile_failing("ENTRY sma(close) > 0")
        assert err.code == "TYPE_ARITY_MISMATCH"

    def test_atr_three_args(self) -> None:
        err = compile_failing("ENTRY atr(high, low, close) > 0")
        assert err.code == "TYPE_ARITY_MISMATCH"

    def test_min_three_args(self) -> None:
        err = compile_failing("ENTRY min(1, 2, 3) == 0")
        assert err.code == "TYPE_ARITY_MISMATCH"

    def test_crossover_one_arg(self) -> None:
        err = compile_failing("ENTRY crossover(close) > 0")
        assert err.code == "TYPE_ARITY_MISMATCH"

    def test_rsi_too_many(self) -> None:
        err = compile_failing("ENTRY rsi(close, 14, 2) > 0")
        assert err.code == "TYPE_ARITY_MISMATCH"


class TestArithmeticRules:
    def test_bool_plus_number_rejected(self) -> None:
        err = compile_failing("ENTRY (close > 0) + 1 > 0")
        assert err.code == "TYPE_MISMATCH_ARITH"

    def test_series_times_bool_rejected(self) -> None:
        err = compile_failing("ENTRY close * (close > 0) > 0")
        assert err.code == "TYPE_MISMATCH_ARITH"

    def test_unary_minus_on_bool_rejected(self) -> None:
        err = compile_failing("ENTRY -(close > 0) > 0")
        assert err.code == "TYPE_MISMATCH_ARITH"

    def test_series_plus_number_ok(self) -> None:
        program = compile_source("ENTRY close + 1 > 0")
        assert program.entry is not None

    def test_number_plus_number_ok(self) -> None:
        program = compile_source("ENTRY 1 + 2 == 3")
        assert program.entry is not None


class TestComparisonRules:
    def test_bool_comparison_rejected(self) -> None:
        err = compile_failing("ENTRY (close > 0) > (volume > 0)")
        assert err.code == "TYPE_COMPARISON_NON_NUMERIC"

    def test_bool_equality_rejected(self) -> None:
        err = compile_failing("ENTRY (close > 0) == (volume > 0)")
        assert err.code == "TYPE_COMPARISON_NON_NUMERIC"

    def test_series_vs_number_ok(self) -> None:
        program = compile_source("ENTRY close >= 12.5")
        assert program.entry is not None


class TestBooleanRules:
    def test_and_on_numbers_rejected(self) -> None:
        err = compile_failing("ENTRY close > 0 AND volume + 1")
        assert err.code == "TYPE_BOOL_OP_NON_BOOL"

    def test_or_on_numbers_rejected(self) -> None:
        err = compile_failing("ENTRY close OR volume")
        assert err.code == "TYPE_BOOL_OP_NON_BOOL"

    def test_not_on_number_rejected(self) -> None:
        err = compile_failing("ENTRY NOT close")
        assert err.code == "TYPE_BOOL_OP_NON_BOOL"

    def test_section_must_be_bool(self) -> None:
        err = compile_failing("ENTRY sma(close, 5)")
        assert err.code == "TYPE_SECTION_NOT_BOOL"

    def test_and_on_bools_ok(self) -> None:
        program = compile_source("ENTRY close > 0 AND volume > 0")
        assert program.entry is not None


class TestUnknowns:
    def test_unknown_function(self) -> None:
        err = compile_failing("ENTRY hullma(close, 9) > 0")
        assert err.code == "TYPE_UNKNOWN_FUNCTION"

    def test_python_builtin_not_whitelisted(self) -> None:
        # open(...) is not whitelisted; the string argument makes the rejection
        # happen even earlier (TYPE_REF_INVALID_BASE at parse time).
        err = compile_failing('ENTRY open("etc") > 0')
        assert err.code == "TYPE_REF_INVALID_BASE"

    def test_unknown_input(self) -> None:
        err = compile_failing("ENTRY close > missing_input")
        assert err.code == "TYPE_UNKNOWN_INPUT"

    def test_mtf_invalid_tf(self) -> None:
        err = compile_failing("ENTRY D2.close > 0")
        assert err.code == "TYPE_MTF_INVALID_TF"

    def test_mtf_invalid_base(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            compile_source("ENTRY D1.typical > 0")
        assert excinfo.value.code == "PARSE_INVALID_SERIES_BASE"

    def test_ref_string_literal_base_rejected(self) -> None:
        err = compile_failing('ENTRY ref("close", 1) > 0')
        assert err.code == "TYPE_REF_INVALID_BASE"

    def test_ref_number_base_rejected(self) -> None:
        err = compile_failing("ENTRY ref(5, 1) > 0")
        assert err.code == "TYPE_REF_INVALID_BASE"

    def test_ref_valid_base_ok(self) -> None:
        program = compile_source("ENTRY ref(close, 1) > 0")
        assert program.entry is not None


class TestPolymorphic:
    def test_abs_scalar_is_number(self) -> None:
        program = compile_source("ENTRY abs(0 - 3) == 3")
        assert program.entry is not None

    def test_abs_series_is_series(self) -> None:
        ctx = SeriesContext(
            open=[1, 1, 1], high=[1, 1, 1], low=[1, 1, 1], close=[-2, 3, -4], volume=[1, 1, 1]
        )
        assert evaluate(compile_source("ENTRY abs(close) == 2"), ctx, 0).entry is True

    def test_min_scalar(self) -> None:
        assert evaluate(compile_source("ENTRY min(2, 3) == 2"), _ctx(), 0).entry

    def test_max_scalar(self) -> None:
        assert evaluate(compile_source("ENTRY max(2, 3) == 3"), _ctx(), 0).entry

    def test_min_series_broadcast(self) -> None:
        ctx = SeriesContext(
            open=[1, 1, 1], high=[1, 1, 1], low=[1, 1, 1], close=[5, 1, 5], volume=[1, 1, 1]
        )
        program = compile_source("ENTRY min(close, 2) == 2")
        assert [evaluate(program, ctx, i).entry for i in range(3)] == [True, False, True]

    def test_max_series_broadcast(self) -> None:
        ctx = SeriesContext(
            open=[1, 1, 1], high=[1, 1, 1], low=[1, 1, 1], close=[5, 1, 5], volume=[1, 1, 1]
        )
        program = compile_source("ENTRY max(close, 2) == 2")
        assert [evaluate(program, ctx, i).entry for i in range(3)] == [False, True, False]


class TestInputsAndTypeMap:
    def test_input_resolves_to_number(self) -> None:
        program = compile_source("INPUT p = 4\nENTRY close > sma(close, p)")
        assert program.entry is not None

    def test_input_int_ok(self) -> None:
        program = compile_source("INPUT n = 3\nENTRY ref(close, n) == 0")
        assert program.entry is not None

    def test_input_float_period_rejected_by_validator(self) -> None:
        from app.engines.strategy_dsl import DSLSemanticError

        with pytest.raises(DSLError) as excinfo:
            compile_source("INPUT p = 2.5\nENTRY ref(close, p) == 0")
        assert excinfo.value.code == "SEM_PERIOD_INVALID"
        assert isinstance(excinfo.value, DSLSemanticError)

    def test_typecheck_map_types(self) -> None:
        program = parse("ENTRY close > sma(close, 5) AND rsi(close, 14) < 70")
        mapping = typecheck(program)
        assert set(mapping.values()) <= {"number", "series", "bool"}
        assert "bool" in set(mapping.values())

    def test_infer_single_node(self) -> None:
        from app.engines.strategy_dsl import Num, infer

        assert infer(Num(3), set()) == "number"


def _ctx() -> SeriesContext:
    return SeriesContext(
        open=[1, 1, 1], high=[1, 1, 1], low=[1, 1, 1], close=[2, 3, 4], volume=[1, 1, 1]
    )
