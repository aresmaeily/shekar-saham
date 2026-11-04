"""MASTER-RADAR directive §C2 — recursive-descent parser for RSL-1.

Produces the immutable AST from :mod:`ast_nodes`. The parser is a pure
tree-builder: it never evaluates, never imports anything user-controlled and
never compiles strategy text to Python. Known-function arity is enforced by
the type checker (``types.py``) — the parser stays shape-generic so that both
layers agree on a single source of truth.

Two structural guarantees worth noting:

- A recursion-depth guard (``PARSE_DEPTH_LIMIT``) bounds parser recursion so
  deeply nested hostile sources raise a clean DSLError instead of a Python
  ``RecursionError``.
- ``compile_source`` checks the source-length budget *before* tokenizing, so
  oversized payloads are rejected with ``BUDGET_SOURCE_LEN`` without any
  parsing work at all.

Deviations (documented): ``MTFBUDGET``/``SYMBUDGET`` appear in the directive
grammar sketch but have no specified syntax and no effect on the fixed
validator budgets, so they are reserved-but-unimplemented: sources using them
fail with a precise parse error.
"""
from __future__ import annotations

import hashlib

from . import ast_nodes as A
from .ast_nodes import DEFAULT_FALSE, Expr, Program, RiskSpec
from .errors import DSLBudgetError, DSLParseError, DSLTypeError
from .lexer import Token, tokenize
from .types import typecheck
from .validator import MAX_SOURCE_LEN, validate

# Parser recursion guard. The worst case costs about eight Python frames per
# nesting level; 80 keeps the parser far away from the interpreter recursion
# limit while still allowing programs deeper than the validator's 64-level
# budget (so BUDGET_DEPTH, not the parser guard, is what users normally hit).
_PARSER_MAX_DEPTH = 80

_MAX_INPUTS = 16
_INPUT_NAME_MAX = 32

_RISK_KEYS = ("stop_loss_pct", "take_profit_pct", "trailing_pct", "max_position_pct")

_CMP_KINDS = {
    "GT": ">",
    "LT": "<",
    "GE": ">=",
    "LE": "<=",
    "EQEQ": "==",
    "NE": "!=",
}

_ADD_KINDS = {"PLUS": "+", "MINUS": "-"}
_MUL_KINDS = {"STAR": "*", "SLASH": "/"}


def _describe(token: Token) -> str:
    if token.kind == "EOF":
        return "end of input"
    if token.kind == "NEWLINE":
        return "end of line"
    return f"{token.kind} {token.value!r}"


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._depth = 0

    # -- token plumbing -------------------------------------------------
    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        token = self._tokens[self._pos]
        if token.kind != "EOF":
            self._pos += 1
        return token

    def _expect(self, kind: str, what: str) -> Token:
        token = self._peek()
        if token.kind != kind:
            raise DSLParseError(
                f"expected {what}, found {_describe(token)}",
                line=token.line,
                col=token.col,
                code="PARSE_UNEXPECTED_TOKEN",
            )
        return self._advance()

    def _enter(self) -> None:
        self._depth += 1
        if self._depth > _PARSER_MAX_DEPTH:
            token = self._peek()
            raise DSLParseError(
                f"expression nesting exceeds the parser limit of {_PARSER_MAX_DEPTH}",
                line=token.line,
                col=token.col,
                code="PARSE_DEPTH_LIMIT",
            )

    def _leave(self) -> None:
        self._depth -= 1

    # -- statements ------------------------------------------------------
    def parse_program(self) -> Program:
        inputs: dict[str, float] = {}
        risk: RiskSpec | None = None
        entry: Expr | None = None
        exit_expr: Expr | None = None
        alert: Expr | None = None
        seen_sections: set[str] = set()
        last = self._peek()

        while True:
            while self._peek().kind == "NEWLINE":
                self._advance()
            token = self._peek()
            if token.kind == "EOF":
                last = token
                break
            if token.kind != "KEYWORD":
                raise DSLParseError(
                    f"expected a section keyword (INPUT/RISK/ENTRY/EXIT/ALERT), "
                    f"found {_describe(token)}",
                    line=token.line,
                    col=token.col,
                    code="PARSE_UNEXPECTED_TOKEN",
                )
            last = token
            keyword = str(token.value)
            if keyword == "INPUT":
                self._parse_input(inputs)
            elif keyword == "RISK":
                if "RISK" in seen_sections:
                    raise DSLParseError(
                        "duplicate RISK section",
                        line=token.line,
                        col=token.col,
                        code="PARSE_DUPLICATE_SECTION",
                    )
                seen_sections.add("RISK")
                risk = self._parse_risk()
            elif keyword in ("ENTRY", "EXIT", "ALERT"):
                if keyword in seen_sections:
                    raise DSLParseError(
                        f"duplicate {keyword} section",
                        line=token.line,
                        col=token.col,
                        code="PARSE_DUPLICATE_SECTION",
                    )
                seen_sections.add(keyword)
                self._advance()
                expr = self._parse_or()
                if keyword == "ENTRY":
                    entry = expr
                elif keyword == "EXIT":
                    exit_expr = expr
                else:
                    alert = expr
            else:
                raise DSLParseError(
                    f"unexpected {_describe(token)} at statement level; RSL-1 "
                    "statements are INPUT, RISK, ENTRY, EXIT or ALERT",
                    line=token.line,
                    col=token.col,
                    code="PARSE_UNEXPECTED_TOKEN",
                )

            end = self._peek()
            if end.kind not in ("NEWLINE", "EOF"):
                raise DSLParseError(
                    f"unexpected {_describe(end)} after statement",
                    line=end.line,
                    col=end.col,
                    code="PARSE_UNEXPECTED_TOKEN",
                )

        if entry is None:
            raise DSLParseError(
                "program requires exactly one ENTRY section",
                line=last.line,
                col=last.col,
                code="PARSE_MISSING_ENTRY",
            )

        exit_final = exit_expr if exit_expr is not None else DEFAULT_FALSE
        alert_final = alert if alert is not None else DEFAULT_FALSE

        mtf_refs = tuple(
            node
            for expr in (entry, exit_final, alert_final)
            for node in A.walk_expr(expr)
            if isinstance(node, A.MtfRef)
        )
        symbol_refs = tuple(
            node
            for expr in (entry, exit_final, alert_final)
            for node in A.walk_expr(expr)
            if isinstance(node, A.SymbolRef)
        )
        return Program(
            inputs=inputs,
            risk=risk,
            entry=entry,
            exit=exit_final,
            alert=alert_final,
            mtf_refs=mtf_refs,
            symbol_refs=symbol_refs,
            source_digest="",
        )

    def _parse_number_literal(self, what: str) -> Token:
        """Parse ``NUMBER`` or a negative literal ``- NUMBER``."""
        token = self._peek()
        if token.kind == "MINUS":
            self._advance()
            num = self._expect("NUMBER", what)
            value = num.value
            if not isinstance(value, (int, float)):
                raise DSLParseError(
                    f"expected {what}, found {_describe(num)}",
                    line=num.line,
                    col=num.col,
                    code="PARSE_UNEXPECTED_TOKEN",
                )
            return Token("NUMBER", -value, num.line, num.col)
        return self._expect("NUMBER", what)

    def _parse_input(self, inputs: dict[str, float]) -> None:
        self._advance()  # INPUT keyword
        if len(inputs) >= _MAX_INPUTS:
            token = self._peek()
            raise DSLParseError(
                f"at most {_MAX_INPUTS} INPUT declarations are allowed",
                line=token.line,
                col=token.col,
                code="PARSE_TOO_MANY_INPUTS",
            )
        name_tok = self._expect("IDENT", "an input name")
        name = str(name_tok.value)
        if len(name) > _INPUT_NAME_MAX:
            raise DSLParseError(
                f"input name {name!r} is longer than {_INPUT_NAME_MAX} characters",
                line=name_tok.line,
                col=name_tok.col,
                code="PARSE_BAD_INPUT_NAME",
            )
        if name in inputs:
            raise DSLParseError(
                f"duplicate INPUT {name!r}",
                line=name_tok.line,
                col=name_tok.col,
                code="PARSE_DUPLICATE_INPUT",
            )
        self._expect("EQ", "'='")
        num = self._parse_number_literal("a number literal")
        inputs[name] = num.value  # type: ignore[assignment]

    def _parse_risk(self) -> RiskSpec:
        self._advance()  # RISK keyword
        values: dict[str, float] = {}
        while True:
            key_tok = self._expect("IDENT", "a risk key")
            key = str(key_tok.value)
            if key not in _RISK_KEYS:
                raise DSLParseError(
                    f"unknown risk key {key!r}; allowed keys: "
                    + ", ".join(_RISK_KEYS),
                    line=key_tok.line,
                    col=key_tok.col,
                    code="PARSE_RISK_KEY",
                )
            if key in values:
                raise DSLParseError(
                    f"duplicate risk key {key!r}",
                    line=key_tok.line,
                    col=key_tok.col,
                    code="PARSE_DUPLICATE_RISK_KEY",
                )
            self._expect("EQ", "'='")
            num = self._parse_number_literal("a number literal")
            values[key] = float(num.value)  # type: ignore[arg-type]
            if self._peek().kind == "COMMA":
                self._advance()
                continue
            break
        return RiskSpec(
            stop_loss_pct=values.get("stop_loss_pct"),
            take_profit_pct=values.get("take_profit_pct"),
            trailing_pct=values.get("trailing_pct"),
            max_position_pct=values.get("max_position_pct"),
        )

    # -- expressions -----------------------------------------------------
    def _parse_or(self) -> Expr:
        self._enter()
        try:
            node = self._parse_and()
            while self._peek().kind == "KEYWORD" and self._peek().value == "OR":
                tok = self._advance()
                node = A.Or(node, self._parse_and(), line=tok.line, col=tok.col)
            return node
        finally:
            self._leave()

    def _parse_and(self) -> Expr:
        self._enter()
        try:
            node = self._parse_not()
            while self._peek().kind == "KEYWORD" and self._peek().value == "AND":
                tok = self._advance()
                node = A.And(node, self._parse_not(), line=tok.line, col=tok.col)
            return node
        finally:
            self._leave()

    def _parse_not(self) -> Expr:
        self._enter()
        try:
            token = self._peek()
            if token.kind == "KEYWORD" and token.value == "NOT":
                self._advance()
                return A.Not(self._parse_not(), line=token.line, col=token.col)
            return self._parse_cmp()
        finally:
            self._leave()

    def _parse_cmp(self) -> Expr:
        self._enter()
        try:
            node = self._parse_add()
            token = self._peek()
            if token.kind in _CMP_KINDS:
                self._advance()
                right = self._parse_add()
                return A.Cmp(
                    _CMP_KINDS[token.kind], node, right, line=token.line, col=token.col
                )
            return node
        finally:
            self._leave()

    def _parse_add(self) -> Expr:
        self._enter()
        try:
            node = self._parse_mul()
            while self._peek().kind in _ADD_KINDS:
                tok = self._advance()
                node = A.BinOp(
                    _ADD_KINDS[tok.kind], node, self._parse_mul(), line=tok.line, col=tok.col
                )
            return node
        finally:
            self._leave()

    def _parse_mul(self) -> Expr:
        self._enter()
        try:
            node = self._parse_unary()
            while self._peek().kind in _MUL_KINDS:
                tok = self._advance()
                node = A.BinOp(
                    _MUL_KINDS[tok.kind], node, self._parse_unary(), line=tok.line, col=tok.col
                )
            return node
        finally:
            self._leave()

    def _parse_unary(self) -> Expr:
        self._enter()
        try:
            token = self._peek()
            if token.kind == "MINUS":
                self._advance()
                return A.UnaryOp("-", self._parse_unary(), line=token.line, col=token.col)
            return self._parse_primary()
        finally:
            self._leave()

    def _parse_primary(self) -> Expr:
        self._enter()
        try:
            token = self._peek()
            if token.kind == "NUMBER":
                self._advance()
                return A.Num(token.value, line=token.line, col=token.col)  # type: ignore[arg-type]
            if token.kind == "LPAREN":
                self._advance()
                node = self._parse_or()
                self._expect("RPAREN", "')'")
                return node
            if token.kind == "IDENT":
                self._advance()
                nxt = self._peek()
                if nxt.kind == "DOT":
                    self._advance()
                    base_tok = self._expect("IDENT", "a series base (open/high/low/close/volume)")
                    base = str(base_tok.value)
                    if base not in A.SERIES_BASES:
                        raise DSLParseError(
                            f"unknown series base {base!r} after timeframe prefix; "
                            "allowed: " + ", ".join(A.SERIES_BASES),
                            line=base_tok.line,
                            col=base_tok.col,
                            code="PARSE_INVALID_SERIES_BASE",
                        )
                    return A.MtfRef(
                        str(token.value).upper(), base, line=token.line, col=token.col
                    )
                if nxt.kind == "LPAREN":
                    return self._parse_call(str(token.value), token)
                if token.value in A.SERIES_BASES:
                    return A.SeriesBase(str(token.value), line=token.line, col=token.col)
                return A.InputRef(str(token.value), line=token.line, col=token.col)
            if token.kind == "KEYWORD" and token.value == "SYM":
                return self._parse_symref()
            if token.kind == "STRING":
                raise DSLParseError(
                    'string literals are only allowed as the symbol of sym("...")',
                    line=token.line,
                    col=token.col,
                    code="PARSE_UNEXPECTED_STRING",
                )
            raise DSLParseError(
                f"expected an expression, found {_describe(token)}",
                line=token.line,
                col=token.col,
                code="PARSE_UNEXPECTED_TOKEN",
            )
        finally:
            self._leave()

    def _parse_call(self, fn: str, fn_tok: Token) -> Expr:
        self._expect("LPAREN", "'('")
        args: list[Expr] = []
        first = True
        while self._peek().kind != "RPAREN":
            if self._peek().kind == "EOF":
                token = self._peek()
                raise DSLParseError(
                    f"unterminated argument list for {fn!r}",
                    line=token.line,
                    col=token.col,
                    code="PARSE_UNEXPECTED_TOKEN",
                )
            if not first:
                self._expect("COMMA", "','")
            token = self._peek()
            if token.kind == "STRING":
                if first:
                    raise DSLTypeError(
                        f"function {fn!r} does not accept a string literal; strings "
                        'are only allowed as the symbol of sym("...")',
                        line=token.line,
                        col=token.col,
                        code="TYPE_REF_INVALID_BASE",
                    )
                raise DSLParseError(
                    'string literals are only allowed as the symbol of sym("...")',
                    line=token.line,
                    col=token.col,
                    code="PARSE_UNEXPECTED_STRING",
                )
            args.append(self._parse_or())
            first = False
        self._advance()  # RPAREN
        return A.Call(fn, tuple(args), line=fn_tok.line, col=fn_tok.col)

    def _parse_symref(self) -> Expr:
        tok = self._advance()  # SYM keyword
        self._expect("LPAREN", "'('")
        str_tok = self._peek()
        if str_tok.kind != "STRING":
            raise DSLParseError(
                f'sym(...) requires a string literal symbol, found {_describe(str_tok)}',
                line=str_tok.line,
                col=str_tok.col,
                code="PARSE_EXPECTED_SYMBOL_STRING",
            )
        self._advance()
        symbol = str(str_tok.value)
        if not symbol or len(symbol) > 24:
            raise DSLParseError(
                "symbol identifier must be 1..24 characters",
                line=str_tok.line,
                col=str_tok.col,
                code="PARSE_BAD_SYMBOL",
            )
        self._expect("RPAREN", "')'")
        self._expect("DOT", "'.'")
        base_tok = self._expect("IDENT", "a series base (open/high/low/close/volume)")
        base = str(base_tok.value)
        if base not in A.SERIES_BASES:
            raise DSLParseError(
                f"unknown series base {base!r} after symbol reference; allowed: "
                + ", ".join(A.SERIES_BASES),
                line=base_tok.line,
                col=base_tok.col,
                code="PARSE_INVALID_SERIES_BASE",
            )
        return A.SymbolRef(symbol, base, line=tok.line, col=tok.col)


def parse(source: str) -> Program:
    """Parse RSL-1 ``source`` into a :class:`Program` (no typing/semantics)."""
    if not isinstance(source, str):
        raise DSLParseError(
            "strategy source must be a string",
            code="PARSE_BAD_SOURCE",
        )
    try:
        tokens = tokenize(source)
        program = _Parser(tokens).parse_program()
    except RecursionError:  # defensive: never leak raw interpreter failures
        raise DSLParseError(
            "strategy source is too deeply nested to parse",
            code="PARSE_TOO_COMPLEX",
        ) from None
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return A.Program(
        inputs=program.inputs,
        risk=program.risk,
        entry=program.entry,
        exit=program.exit,
        alert=program.alert,
        mtf_refs=program.mtf_refs,
        symbol_refs=program.symbol_refs,
        source_digest=digest,
    )


def compile_source(source: str) -> Program:
    """Full pipeline: parse + typecheck + validate (budgets, semantics).

    The source-length budget is enforced before any parsing work so that
    oversized hostile payloads are rejected immediately.
    """
    if len(source) > MAX_SOURCE_LEN:
        raise DSLBudgetError(
            f"strategy source is {len(source)} characters; budget is {MAX_SOURCE_LEN}",
            code="BUDGET_SOURCE_LEN",
        )
    program = parse(source)
    typecheck(program)
    validate(program)
    return program
