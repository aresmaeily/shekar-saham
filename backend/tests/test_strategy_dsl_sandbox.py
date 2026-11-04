"""MASTER-RADAR directive §C2 — sandbox escape-resistance tests for RSL-1.

Every case here is a hostile strategy source that MUST be rejected with a
DSLError subclass and never executed. The final test module also audits the
strategy_dsl package source files themselves: the tokens ``eval(``,
``exec(``, ``compile(`` and ``__import__(`` must not appear anywhere in the
package (the file read happens here in the TEST only, never in domain code).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.engines.strategy_dsl import (
    DSLError,
    SeriesContext,
    compile_source,
    parse,
    run_over_series,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "app" / "engines" / "strategy_dsl"

# (hostile source, expected DSLError code or None-for-any)
HOSTILE_SOURCES: list[tuple[str, str | None]] = [
    # python builtins / attribute escapes
    ('INPUT x = __import__("os")\nENTRY close > 0', "PARSE_UNEXPECTED_TOKEN"),
    ("ENTRY close.__class__ > 0", "PARSE_INVALID_SERIES_BASE"),
    ("ENTRY ().__class__ > 0", "PARSE_UNEXPECTED_TOKEN"),
    ('ENTRY eval("1") > 0', "TYPE_REF_INVALID_BASE"),
    ('ENTRY exec("1") > 0', "TYPE_REF_INVALID_BASE"),
    ('ENTRY open("/etc/passwd") > 0', "LEX_BAD_STRING"),
    ('ENTRY globals()["__builtins__"] > 0', "LEX_ILLEGAL_CHAR"),
    # statement-level injection
    ("ENTRY close > 0; import os", "LEX_ILLEGAL_CHAR"),
    ("INPUT close; import os\nENTRY close > 0", "LEX_ILLEGAL_CHAR"),
    ("@foo\nENTRY close > 0", "LEX_ILLEGAL_CHAR"),
    ("ENTRY lambda: 1 > 0", "LEX_ILLEGAL_CHAR"),
    ("ENTRY lambda x: x > 0", "LEX_ILLEGAL_CHAR"),
    ("ENTRY [x for x in close] > 0", "LEX_ILLEGAL_CHAR"),
    ('ENTRY f"close" > 0', "PARSE_UNEXPECTED_TOKEN"),
    ("ENTRY {1: 2} > 0", "LEX_ILLEGAL_CHAR"),
    # numeric edge cases
    ("ENTRY close > 1e9", "PARSE_UNEXPECTED_TOKEN"),
    ("ENTRY " + "(" * 10000 + "close" + ")" * 10000, "BUDGET_SOURCE_LEN"),
    ("ENTRY close > " + "0" * 100000, "BUDGET_SOURCE_LEN"),
    # unicode / control characters
    ("INPUT ورودی = 1\nENTRY close > 0", "LEX_ILLEGAL_CHAR"),
    ("ENTRY close > 0\x00", "LEX_ILLEGAL_CHAR"),
    # sym() traversal and escape attempts
    ('ENTRY sym("../../etc/passwd").close > 0', "LEX_BAD_STRING"),
    ('ENTRY sym("a\\b").close > 0', "LEX_BAD_STRING"),
    ('ENTRY sym("").close > 0', "PARSE_BAD_SYMBOL"),
    ('ENTRY sym("' + "A" * 25 + '").close > 0', "LEX_BAD_STRING"),
    # deep recursion attempts
    ("ENTRY " + "-" * 500 + "close > 0", "PARSE_DEPTH_LIMIT"),
    ("ENTRY " + "NOT " * 500 + "close > 0", "PARSE_DEPTH_LIMIT"),
]


@pytest.mark.parametrize(
    "source,expected_code",
    HOSTILE_SOURCES,
    ids=[f"hostile_{i}" for i in range(len(HOSTILE_SOURCES))],
)
def test_hostile_source_rejected(
    source: str, expected_code: str | None
) -> None:
    with pytest.raises(DSLError) as excinfo:
        compile_source(source)
    if expected_code is not None:
        assert excinfo.value.code == expected_code


def test_deeply_nested_parse_directly_also_safe() -> None:
    # even parse() alone (without the source-length pre-check) must fail with
    # a DSLError, never with a raw RecursionError.
    source = "ENTRY " + "(" * 500 + "close" + ")" * 500
    with pytest.raises(DSLError) as excinfo:
        parse(source)
    assert excinfo.value.code == "PARSE_DEPTH_LIMIT"


def test_wildly_mismatched_parens_rejected() -> None:
    with pytest.raises(DSLError):
        parse("ENTRY ((close > 0")


def test_attribute_dunder_on_call_rejected() -> None:
    with pytest.raises(DSLError):
        parse("ENTRY sma(close, 5).real > 0")


def test_import_via_risk_section_rejected() -> None:
    with pytest.raises(DSLError):
        compile_source("ENTRY close > 0\nRISK stop_loss_pct = __import__('os')")


def test_multiline_string_attempt_rejected() -> None:
    with pytest.raises(DSLError):
        parse('ENTRY sym("a\nb").close > 0')


def test_backslash_anywhere_rejected() -> None:
    with pytest.raises(DSLError):
        parse("ENTRY close > 0 \\ suspend")


def test_tab_and_spaces_are_fine() -> None:
    program = compile_source("ENTRY\tclose   >  0")
    assert program.entry is not None


def test_crlf_source_supported() -> None:
    program = compile_source("ENTRY close > 0\r\nALERT volume > 0\r\n")
    assert program.alert is not None


def test_hostile_source_never_produces_decisions() -> None:
    # a symbol that looks like a path is just an opaque dict key: resolution
    # fails closed (no filesystem access, no decision can be produced).
    ctx = SeriesContext(
        open=[1.0],
        high=[1.0],
        low=[1.0],
        close=[1.0],
        volume=[1.0],
    )
    program = compile_source('ENTRY sym("x").close > 0')
    with pytest.raises(DSLError) as excinfo:
        run_over_series(program, ctx)
    assert excinfo.value.code == "RUN_MISSING_SYMBOL_SERIES"


def test_missing_symbol_never_reads_filesystem() -> None:
    # a symbol that looks like a path is just an opaque dict key: resolution
    # fails closed with RUN_MISSING_SYMBOL_SERIES (no filesystem access).
    ctx = SeriesContext(
        open=[1.0],
        high=[1.0],
        low=[1.0],
        close=[1.0],
        volume=[1.0],
    )
    program = compile_source('ENTRY sym("etc-passwd").close > 0')
    with pytest.raises(DSLError) as excinfo:
        run_over_series(program, ctx)
    assert excinfo.value.code == "RUN_MISSING_SYMBOL_SERIES"


class TestSelfAudit:
    FORBIDDEN_TOKENS = ("eval(", "exec(", "__import__(", "compile(")

    def test_audit_no_dangerous_calls(self) -> None:
        """Scan every .py file of the strategy_dsl package for forbidden calls."""
        findings = audit_no_dangerous_calls(PACKAGE_DIR)
        assert findings == []

    def test_audit_tool_works(self) -> None:
        # sanity: the audit detects a synthetic violation in a temp file
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.py"
            path.write_text("x = eval('1')\n", encoding="utf-8")
            findings = audit_no_dangerous_calls(Path(tmp))
            assert len(findings) == 1
            assert "bad.py" in findings[0]

    def test_package_files_exist(self) -> None:
        expected = {
            "__init__.py",
            "ast_nodes.py",
            "errors.py",
            "lexer.py",
            "parser.py",
            "runtime.py",
            "types.py",
            "validator.py",
            "versioning.py",
        }
        present = {p.name for p in PACKAGE_DIR.glob("*.py")}
        assert expected <= present


def audit_no_dangerous_calls(package_dir: Path) -> list[str]:
    """Return one finding per package file containing a forbidden call token.

    Implemented here in the test suite (a file read for self-audit is
    acceptable in tests, never in domain code).
    """
    findings: list[str] = []
    for path in sorted(package_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in TestSelfAudit.FORBIDDEN_TOKENS:
            if token in text:
                findings.append(f"{path.name}: contains forbidden token {token!r}")
    return findings
