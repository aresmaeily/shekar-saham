"""MASTER-RADAR directive §C2 — parser tests for the RSL-1 strategy DSL.

Covers: valid programs per section, case-insensitive keywords, comments,
error positions, duplicate/missing/extra sections, malformed numbers, strings
outside sym(), source digest, and AST shape checks.
"""
from __future__ import annotations

import hashlib

import pytest

from app.engines.strategy_dsl import (
    And,
    BinOp,
    Call,
    Cmp,
    DSLError,
    Not,
    Or,
    Program,
    RiskSpec,
    SeriesBase,
    UnaryOp,
    compile_source,
    parse,
    tokenize,
)

FULL_SOURCE = """\
# example strategy
INPUT fast = 10
INPUT threshold = 70.5
RISK stop_loss_pct = 2.0, take_profit_pct = 4.0, trailing_pct = 1.0, max_position_pct = 25.0
ENTRY close > sma(close, fast) AND rsi(close, 14) < threshold
EXIT crossunder(close, sma(close, fast)) OR close < highest(high, 20) * 0.97
ALERT volume > sma(volume, 20) * 2 AND NOT (rsi(close, 14) > 80)
"""


class TestValidPrograms:
    def test_full_example_parses(self) -> None:
        program = parse(FULL_SOURCE)
        assert isinstance(program, Program)
        assert program.risk == RiskSpec(
            stop_loss_pct=2.0,
            take_profit_pct=4.0,
            trailing_pct=1.0,
            max_position_pct=25.0,
        )
        assert program.inputs == {"fast": 10, "threshold": 70.5}

    def test_entry_section_ast(self) -> None:
        program = parse(FULL_SOURCE)
        entry = program.entry
        assert isinstance(entry, And)
        assert isinstance(entry.l, Cmp) and entry.l.op == ">"
        assert isinstance(entry.l.l, SeriesBase) and entry.l.l.name == "close"
        assert isinstance(entry.l.r, Call) and entry.l.r.fn == "sma"
        assert isinstance(entry.r, Cmp) and entry.r.op == "<"

    def test_exit_alert_defaults(self) -> None:
        program = parse("ENTRY close > 0")
        assert program.exit is not None
        assert program.alert is not None
        # defaults are the constant-false sentinel
        assert float(program.exit.v) == 0.0

    def test_explicit_exit_and_alert(self) -> None:
        program = parse("ENTRY close > 0\nEXIT close < 0\nALERT volume > 0")
        assert isinstance(program.exit, Cmp) and program.exit.op == "<"
        assert isinstance(program.alert, Cmp) and program.alert.op == ">"

    def test_risk_partial_keys(self) -> None:
        program = parse("ENTRY close > 0\nRISK stop_loss_pct = 3.5")
        assert program.risk == RiskSpec(stop_loss_pct=3.5)
        assert program.risk.take_profit_pct is None

    def test_risk_no_section(self) -> None:
        assert parse("ENTRY close > 0").risk is None

    def test_keywords_case_insensitive(self) -> None:
        program = parse(
            "input Fast = 2\n"
            "risk Stop_Loss_Pct = 5\n"
            "entry Close > sma(Close, FAST) and rsi(close, 3) OR NOT close < 0\n"
        )
        assert program.inputs == {"fast": 2}
        assert program.risk == RiskSpec(stop_loss_pct=5.0)
        # (Close > sma(...)) AND (rsi(...) < FAST)   OR   NOT (close < 0)
        assert isinstance(program.entry, Or)
        assert isinstance(program.entry.l, And)
        assert isinstance(program.entry.r, Not)

    def test_input_int_vs_float(self) -> None:
        program = parse("ENTRY close > 0\nINPUT a = 7\nINPUT b = 7.5")
        assert program.inputs["a"] == 7
        assert isinstance(program.inputs["a"], int)
        assert program.inputs["b"] == 7.5
        assert isinstance(program.inputs["b"], float)

    def test_comments_ignored(self) -> None:
        source = (
            "# leading comment\n"
            "INPUT p = 3 # inline comment\n"
            "\n"
            "ENTRY close > sma(close, p) # trailing\n"
        )
        program = compile_source(source)
        assert program.inputs == {"p": 3}
        assert isinstance(program.entry, Cmp)

    def test_blank_lines_and_no_trailing_newline(self) -> None:
        program = parse("ENTRY close > 0")
        assert isinstance(program.entry, Cmp)

    def test_mtf_ref_fields(self) -> None:
        program = parse("ENTRY D1.close > W1.low AND H4.volume > M1.open")
        assert [(r.tf, r.base) for r in program.mtf_refs] == [
            ("D1", "close"),
            ("W1", "low"),
            ("H4", "volume"),
            ("M1", "open"),
        ]
        assert program.mtf_refs[0].line == 1 and program.mtf_refs[0].col == 7

    def test_symbol_ref_fields(self) -> None:
        program = parse('ENTRY sym("TEHRAN.IRO1X").close > sym("B.2").volume')
        assert [(r.symbol, r.base) for r in program.symbol_refs] == [
            ("TEHRAN.IRO1X", "close"),
            ("B.2", "volume"),
        ]

    def test_symbol_charset_allowed(self) -> None:
        program = parse('ENTRY sym("A-z_0-9.").close > 0')
        assert program.symbol_refs[0].symbol == "A-z_0-9."

    def test_call_shape(self) -> None:
        program = parse("ENTRY atr(high, low, close, 14) > 1.5")
        call = program.entry.l
        assert isinstance(call, Call)
        assert call.fn == "atr"
        assert len(call.args) == 4
        assert call.line == 1 and call.col == 7

    def test_unary_minus_chain_shape(self) -> None:
        program = parse("ENTRY -(-close) > 0")
        node = program.entry.l
        assert isinstance(node, UnaryOp)
        assert isinstance(node.x, UnaryOp)
        assert isinstance(node.x.x, SeriesBase)

    def test_precedence_shape(self) -> None:
        # a + b * c  ==>  a + (b * c)
        program = parse("ENTRY close + high * low > 0")
        add = program.entry.l
        assert isinstance(add, BinOp) and add.op == "+"
        assert isinstance(add.l, SeriesBase)
        assert isinstance(add.r, BinOp) and add.r.op == "*"

    def test_not_binds_tighter_than_and(self) -> None:
        # NOT a AND b  ==>  (NOT a) AND b
        program = parse("ENTRY NOT close > 0 AND volume > 0")
        assert isinstance(program.entry, And)
        assert isinstance(program.entry.l, Not)

    def test_parenthesized_grouping(self) -> None:
        program = parse("ENTRY (close > 0 OR volume > 0) AND high > 0")
        assert isinstance(program.entry, And)
        assert isinstance(program.entry.l, Or)


class TestErrors:
    def test_error_position_line_col(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("INPUT a = 1\nENTRY close > >")
        err = excinfo.value
        assert err.line == 2
        assert err.col == 15

    def test_duplicate_input_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("INPUT a = 1\nINPUT a = 2\nENTRY close > 0")
        assert excinfo.value.code == "PARSE_DUPLICATE_INPUT"
        assert excinfo.value.line == 2

    def test_seventeen_inputs_rejected(self) -> None:
        lines = [f"INPUT v{i} = {i}" for i in range(17)]
        with pytest.raises(DSLError) as excinfo:
            parse("\n".join(lines) + "\nENTRY close > 0")
        assert excinfo.value.code == "PARSE_TOO_MANY_INPUTS"

    def test_sixteen_inputs_ok(self) -> None:
        lines = [f"INPUT v{i} = {i}" for i in range(16)]
        program = parse("\n".join(lines) + "\nENTRY close > 0")
        assert len(program.inputs) == 16

    def test_missing_entry_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("INPUT a = 1\nALERT close > 0")
        assert excinfo.value.code == "PARSE_MISSING_ENTRY"

    def test_empty_source_missing_entry(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("# only a comment\n\n")
        assert excinfo.value.code == "PARSE_MISSING_ENTRY"

    def test_two_entries_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("ENTRY close > 0\nENTRY volume > 0")
        assert excinfo.value.code == "PARSE_DUPLICATE_SECTION"
        assert excinfo.value.line == 2

    def test_two_risk_sections_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("ENTRY close > 0\nRISK stop_loss_pct = 1\nRISK stop_loss_pct = 2")
        assert excinfo.value.code == "PARSE_DUPLICATE_SECTION"

    def test_bad_number_two_dots(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("ENTRY close > 1.2.3")
        assert excinfo.value.code == "LEX_MALFORMED_NUMBER"

    def test_bad_number_trailing_dot(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("ENTRY close > 1.")
        assert excinfo.value.code == "LEX_MALFORMED_NUMBER"

    def test_string_outside_sym_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse('ENTRY close > "close"')
        assert excinfo.value.code == "PARSE_UNEXPECTED_STRING"

    def test_string_as_non_sym_call_arg_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse('ENTRY ref("close", 1) > 0')
        assert excinfo.value.code == "TYPE_REF_INVALID_BASE"

    def test_unknown_statement_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("FOO close > 0")
        assert excinfo.value.code == "PARSE_UNEXPECTED_TOKEN"

    def test_trailing_garbage_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("INPUT a = 1 2\nENTRY close > 0")
        assert excinfo.value.code == "PARSE_UNEXPECTED_TOKEN"

    def test_unknown_risk_key_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("ENTRY close > 0\nRISK leverage = 10")
        assert excinfo.value.code == "PARSE_RISK_KEY"

    def test_keyword_as_input_name_rejected(self) -> None:
        with pytest.raises(DSLError):
            parse("INPUT entry = 5\nENTRY close > 0")

    def test_illegal_character_rejected(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("ENTRY close > 0; import os")
        assert excinfo.value.code == "LEX_ILLEGAL_CHAR"

    def test_illegal_char_position(self) -> None:
        with pytest.raises(DSLError) as excinfo:
            parse("ENTRY close > 0\nINPUT x = @")
        assert excinfo.value.line == 2
        assert excinfo.value.col == 11

    def test_scientific_notation_not_lexed_as_number(self) -> None:
        # plain decimals only: 1e9 lexes as NUMBER(1) then IDENT(e9) and the
        # parser rejects the stray identifier.
        with pytest.raises(DSLError):
            parse("ENTRY close > 1e9")


class TestDigestAndTokens:
    def test_digest_is_sha256_of_exact_source(self) -> None:
        source = "ENTRY close > 0\n"
        program = parse(source)
        assert program.source_digest == hashlib.sha256(source.encode("utf-8")).hexdigest()

    def test_digest_differs_for_whitespace(self) -> None:
        assert parse("ENTRY close > 0").source_digest != parse(
            "ENTRY close > 0 "
        ).source_digest

    def test_tokens_have_positions(self) -> None:
        tokens = tokenize("ENTRY close > 1.5")
        entry = tokens[0]
        assert entry.kind == "KEYWORD" and entry.value == "ENTRY"
        assert (entry.line, entry.col) == (1, 1)
        number = [t for t in tokens if t.kind == "NUMBER"][0]
        assert number.value == 1.5
        assert (number.line, number.col) == (1, 15)
        assert tokens[-1].kind == "EOF"

    def test_compile_source_returns_program(self) -> None:
        program = compile_source("ENTRY close > 0")
        assert isinstance(program, Program)
        assert program.source_digest
