"""MASTER-RADAR directive §C2 — semantic validation and resource budgets.

Enforces the directive's "resource and complexity limits" for RSL-1 strategy
programs:

- AST node budget:          <= 512 nodes                (``BUDGET_NODES``)
- Expression depth budget:  <= 64                       (``BUDGET_DEPTH``)
- Source length budget:     <= 4096 chars               (``BUDGET_SOURCE_LEN``,
                              checked in ``parser.compile_source`` before any
                              parsing work happens)
- Single call arglist:      <= 8 arguments              (``BUDGET_ARGLIST``)
- Distinct MTF timeframes:  <= 3                        (``BUDGET_MTF``)
- Distinct referenced sym.: <= 2                        (``BUDGET_SYMBOLS``)

Hard semantic rules: every call must be whitelisted (``SEM_UNKNOWN_FN``,
defensive — the type checker also enforces this), ``ref(x, n)`` must never
look into the future (``LOOKAHEAD_NEGATIVE_REF``), division by a literal
constant zero is rejected up front (``SEM_DIV_BY_ZERO_CONSTANT``; note the
runtime still guards any *dynamic* x/0 to a deterministic 0.0), indicator
periods must be integer literals or integer INPUTs within their minimum
bounds (``SEM_PERIOD_INVALID``), and RISK values must fall inside their
documented ranges (``SEM_RISK_RANGE``).

``validate`` returns advisory findings (currently: unused INPUT names,
absent EXIT/ALERT sections) without raising; hard violations raise the
corresponding :class:`DSLError` subclass. Budget checks run in a fixed
order: NODES, DEPTH, then the AST walk, then MTF/SYMBOL budgets, then risk.
"""
from __future__ import annotations

from . import ast_nodes as A
from .ast_nodes import DEFAULT_FALSE, Program
from .errors import DSLBudgetError, DSLLookaheadError, DSLSemanticError
from .types import FUNCTION_ARITY

MAX_NODES = 512
MAX_DEPTH = 64
MAX_SOURCE_LEN = 4096
MAX_ARGLIST = 8
MAX_MTF_TIMEFRAMES = 3
MAX_SYMBOL_REFS = 2

# Inclusive documented ranges for the RISK section.
RISK_RANGES: dict[str, tuple[float, float]] = {
    "stop_loss_pct": (0.0, 100.0),
    "take_profit_pct": (0.0, 1000.0),
    "trailing_pct": (0.0, 100.0),
    "max_position_pct": (0.1, 100.0),
}

_RISK_KEYS = ("stop_loss_pct", "take_profit_pct", "trailing_pct", "max_position_pct")

# Minimum period per windowed indicator (rsi/stdev need at least 2 points).
_PERIOD_MIN = {"sma": 1, "ema": 1, "rsi": 2, "stdev": 2, "highest": 1, "lowest": 1, "atr": 1}


def _sections(program: Program) -> tuple[A.Expr, A.Expr, A.Expr]:
    return (program.entry, program.exit, program.alert)


def count_nodes(program: Program) -> int:
    """Total AST node count: Program + optional RiskSpec + all expression nodes."""
    total = 1
    if program.risk is not None:
        total += 1
    for expr in _sections(program):
        total += sum(1 for _ in A.walk_expr(expr))
    return total


def expression_depth(expr: A.Expr) -> int:
    """Nesting depth of an expression tree (a leaf counts as 1)."""
    if isinstance(expr, A.Call):
        return 1 + max((expression_depth(a) for a in expr.args), default=0)
    if isinstance(expr, (A.BinOp, A.Cmp, A.And, A.Or)):
        return 1 + max(expression_depth(expr.l), expression_depth(expr.r))
    if isinstance(expr, (A.UnaryOp, A.Not)):
        return 1 + expression_depth(expr.x)
    return 1


def _literal_number(node: A.Expr) -> float | None:
    """Return the numeric value of a literal (``Num`` or negated ``Num``)."""
    if isinstance(node, A.Num):
        return float(node.v)
    if isinstance(node, A.UnaryOp) and node.op == "-" and isinstance(node.x, A.Num):
        return -float(node.x.v)
    return None


def _constant_value(node: A.Expr) -> float | None:
    """Fold a constant-only arithmetic subtree; None when not constant."""
    literal = _literal_number(node)
    if literal is not None:
        return literal
    if isinstance(node, A.BinOp):
        lv = _constant_value(node.l)
        rv = _constant_value(node.r)
        if lv is None or rv is None:
            return None
        if node.op == "+":
            return lv + rv
        if node.op == "-":
            return lv - rv
        if node.op == "*":
            return lv * rv
        if node.op == "/":
            return 0.0 if rv == 0.0 else lv / rv
    return None


def _check_ref_offset(call: A.Call, program: Program) -> None:
    n_arg = call.args[1]
    literal = _literal_number(n_arg)
    if literal is not None:
        if not float(literal).is_integer():
            raise DSLSemanticError(
                f"ref(...) offset must be an integer, got {literal!r}",
                line=call.line,
                col=call.col,
                code="SEM_PERIOD_INVALID",
            )
        offset = int(literal)
    elif isinstance(n_arg, A.InputRef):
        if n_arg.name not in program.inputs:
            raise DSLSemanticError(
                f"ref(...) offset INPUT {n_arg.name!r} is not declared",
                line=call.line,
                col=call.col,
                code="SEM_UNKNOWN_INPUT",
            )
        value = program.inputs[n_arg.name]
        if not float(value).is_integer():
            raise DSLSemanticError(
                f"ref(...) offset INPUT {n_arg.name!r} must be an integer, got {value!r}",
                line=call.line,
                col=call.col,
                code="SEM_PERIOD_INVALID",
            )
        offset = int(value)
    else:
        raise DSLSemanticError(
            "ref(...) offset must be an integer literal or an integer INPUT",
            line=call.line,
            col=call.col,
            code="SEM_PERIOD_INVALID",
        )
    if offset < 0:
        raise DSLLookaheadError(
            f"ref(close, {offset}) looks into the future; look-ahead is forbidden",
            line=call.line,
            col=call.col,
            code="LOOKAHEAD_NEGATIVE_REF",
        )


def _check_period(call: A.Call, program: Program, minimum: int) -> None:
    p_arg = call.args[-1]
    literal = _literal_number(p_arg)
    if literal is not None:
        if not float(literal).is_integer():
            raise DSLSemanticError(
                f"{call.fn} period must be an integer, got {literal!r}",
                line=call.line,
                col=call.col,
                code="SEM_PERIOD_INVALID",
            )
        period = int(literal)
    elif isinstance(p_arg, A.InputRef):
        if p_arg.name not in program.inputs:
            raise DSLSemanticError(
                f"{call.fn} period INPUT {p_arg.name!r} is not declared",
                line=call.line,
                col=call.col,
                code="SEM_UNKNOWN_INPUT",
            )
        value = program.inputs[p_arg.name]
        if not float(value).is_integer():
            raise DSLSemanticError(
                f"{call.fn} period INPUT {p_arg.name!r} must be an integer, got {value!r}",
                line=call.line,
                col=call.col,
                code="SEM_PERIOD_INVALID",
            )
        period = int(value)
    else:
        raise DSLSemanticError(
            f"{call.fn} period must be an integer literal or an integer INPUT",
            line=call.line,
            col=call.col,
            code="SEM_PERIOD_INVALID",
        )
    if period < minimum:
        raise DSLSemanticError(
            f"{call.fn} period must be >= {minimum}, got {period}",
            line=call.line,
            col=call.col,
            code="SEM_PERIOD_INVALID",
        )


def _check_risk(risk: A.RiskSpec) -> None:
    for key in _RISK_KEYS:
        value = getattr(risk, key)
        if value is None:
            continue
        low, high = RISK_RANGES[key]
        if not (low <= float(value) <= high):
            raise DSLSemanticError(
                f"risk {key}={value} is outside the allowed range [{low}, {high}]",
                code="SEM_RISK_RANGE",
            )


def validate(program: Program) -> list[str]:
    """Validate ``program``; return advisory findings, raise on hard violations."""
    advisories: list[str] = []

    total = count_nodes(program)
    if total > MAX_NODES:
        raise DSLBudgetError(
            f"program uses {total} AST nodes; budget is {MAX_NODES}",
            code="BUDGET_NODES",
        )

    depth = max((expression_depth(e) for e in _sections(program)), default=1)
    if depth > MAX_DEPTH:
        raise DSLBudgetError(
            f"expression nesting depth {depth}; budget is {MAX_DEPTH}",
            code="BUDGET_DEPTH",
        )

    for expr in _sections(program):
        for node in A.walk_expr(expr):
            if isinstance(node, A.Call):
                if len(node.args) > MAX_ARGLIST:
                    raise DSLBudgetError(
                        f"call to {node.fn!r} has {len(node.args)} arguments; "
                        f"budget is {MAX_ARGLIST}",
                        line=node.line,
                        col=node.col,
                        code="BUDGET_ARGLIST",
                    )
                if node.fn not in FUNCTION_ARITY:
                    raise DSLSemanticError(
                        f"function {node.fn!r} is not whitelisted in RSL-1",
                        line=node.line,
                        col=node.col,
                        code="SEM_UNKNOWN_FN",
                    )
                if node.fn == "ref":
                    _check_ref_offset(node, program)
                elif node.fn in _PERIOD_MIN:
                    _check_period(node, program, _PERIOD_MIN[node.fn])
            if (
                isinstance(node, A.BinOp)
                and node.op == "/"
            ):
                denominator = _constant_value(node.r)
                if denominator is not None and denominator == 0.0:
                    raise DSLSemanticError(
                        "division by the constant zero is rejected at compile time",
                        line=node.line,
                        col=node.col,
                        code="SEM_DIV_BY_ZERO_CONSTANT",
                    )

    distinct_tfs = {ref.tf for ref in program.mtf_refs}
    if len(distinct_tfs) > MAX_MTF_TIMEFRAMES:
        raise DSLBudgetError(
            f"program references {len(distinct_tfs)} distinct timeframes "
            f"({', '.join(sorted(distinct_tfs))}); budget is {MAX_MTF_TIMEFRAMES}",
            code="BUDGET_MTF",
        )

    distinct_symbols = {ref.symbol for ref in program.symbol_refs}
    if len(distinct_symbols) > MAX_SYMBOL_REFS:
        raise DSLBudgetError(
            f"program references {len(distinct_symbols)} distinct symbols; "
            f"budget is {MAX_SYMBOL_REFS}",
            code="BUDGET_SYMBOLS",
        )

    if program.risk is not None:
        _check_risk(program.risk)

    used_inputs: set[str] = set()
    for expr in _sections(program):
        for node in A.walk_expr(expr):
            if isinstance(node, A.InputRef):
                used_inputs.add(node.name)
    for name in program.inputs:
        if name not in used_inputs:
            advisories.append(f"unused input: {name}")
    if program.exit is DEFAULT_FALSE:
        advisories.append("no EXIT section: default constant false")
    if program.alert is DEFAULT_FALSE:
        advisories.append("no ALERT section: default constant false")
    return advisories
