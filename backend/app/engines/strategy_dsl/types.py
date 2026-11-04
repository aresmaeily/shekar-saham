"""MASTER-RADAR directive §C2 — static type checker for RSL-1 expressions.

The language has three static types: ``number`` (Python int/float), ``series``
(list of floats aligned to bars) and ``bool``. Series bases, MTF refs and
symbol refs are series; INPUTs are numbers; indicator calls are series;
comparisons and ``crossover``/``crossunder`` are bool; boolean operators only
accept bools. ``abs``/``min``/``max`` are polymorphic: the result is a series
when any argument is a series, otherwise a number.

All failures are raised as :class:`DSLTypeError` with machine-readable codes.
The parser may raise a small subset of the same ``TYPE_*`` codes for
statically-obvious argument-shape violations (string literals outside
``sym(...)``); the checks below are the single source of truth and are
repeated defensively so both layers stay consistent.
"""
from __future__ import annotations

from collections.abc import Iterable

from . import ast_nodes as A
from .ast_nodes import DEFAULT_FALSE, Expr, Program
from .errors import DSLTypeError

TYPE_NUMBER = "number"
TYPE_SERIES = "series"
TYPE_BOOL = "bool"

# Exact arities of the whitelisted function set.
FUNCTION_ARITY: dict[str, int] = {
    "sma": 2,
    "ema": 2,
    "rsi": 2,
    "stdev": 2,
    "highest": 2,
    "lowest": 2,
    "atr": 4,
    "abs": 1,
    "min": 2,
    "max": 2,
    "crossover": 2,
    "crossunder": 2,
    "ref": 2,
}

# Functions that produce a series from series input(s).
INDICATOR_FNS = frozenset({"sma", "ema", "rsi", "stdev", "highest", "lowest", "atr", "ref"})


class _TypeChecker:
    def __init__(self, input_names: Iterable[str]) -> None:
        self._inputs = frozenset(input_names)
        self.types: dict[int, str] = {}

    def check(self, node: Expr) -> str:
        kind = self._check(node)
        self.types[id(node)] = kind
        return kind

    def _err(self, code: str, message: str, node: Expr) -> DSLTypeError:
        return DSLTypeError(
            message,
            line=getattr(node, "line", None),
            col=getattr(node, "col", None),
            code=code,
        )

    def _check(self, node: Expr) -> str:
        if isinstance(node, A.Num):
            return TYPE_NUMBER
        if isinstance(node, A.SeriesBase):
            return TYPE_SERIES
        if isinstance(node, A.MtfRef):
            if node.tf not in A.VALID_TIMEFRAMES:
                raise self._err(
                    "TYPE_MTF_INVALID_TF",
                    f"unknown timeframe prefix {node.tf!r}; allowed: "
                    + ", ".join(A.VALID_TIMEFRAMES),
                    node,
                )
            if node.base not in A.SERIES_BASES:
                raise self._err(
                    "TYPE_REF_INVALID_BASE",
                    f"unknown series base {node.base!r} after timeframe prefix",
                    node,
                )
            return TYPE_SERIES
        if isinstance(node, A.SymbolRef):
            if node.base not in A.SERIES_BASES:
                raise self._err(
                    "TYPE_REF_INVALID_BASE",
                    f"unknown series base {node.base!r} after symbol reference",
                    node,
                )
            return TYPE_SERIES
        if isinstance(node, A.InputRef):
            if node.name not in self._inputs:
                raise self._err(
                    "TYPE_UNKNOWN_INPUT",
                    f"reference to undeclared INPUT {node.name!r}",
                    node,
                )
            return TYPE_NUMBER
        if isinstance(node, A.Call):
            return self._check_call(node)
        if isinstance(node, A.BinOp):
            lt = self.check(node.l)
            rt = self.check(node.r)
            if lt == TYPE_BOOL or rt == TYPE_BOOL:
                raise self._err(
                    "TYPE_MISMATCH_ARITH",
                    f"boolean operand is not allowed in arithmetic ({node.op!r})",
                    node,
                )
            return TYPE_SERIES if TYPE_SERIES in (lt, rt) else TYPE_NUMBER
        if isinstance(node, A.UnaryOp):
            xt = self.check(node.x)
            if node.op != "-" or xt == TYPE_BOOL:
                raise self._err(
                    "TYPE_MISMATCH_ARITH",
                    "unary '-' requires a numeric or series operand",
                    node,
                )
            return xt
        if isinstance(node, A.Cmp):
            lt = self.check(node.l)
            rt = self.check(node.r)
            if lt == TYPE_BOOL or rt == TYPE_BOOL:
                raise self._err(
                    "TYPE_COMPARISON_NON_NUMERIC",
                    f"comparison {node.op!r} requires numeric or series operands",
                    node,
                )
            return TYPE_BOOL
        if isinstance(node, A.Not):
            if self.check(node.x) != TYPE_BOOL:
                raise self._err("TYPE_BOOL_OP_NON_BOOL", "NOT requires a boolean operand", node)
            return TYPE_BOOL
        if isinstance(node, (A.And, A.Or)):
            lt = self.check(node.l)
            rt = self.check(node.r)
            op = "AND" if isinstance(node, A.And) else "OR"
            if lt != TYPE_BOOL or rt != TYPE_BOOL:
                raise self._err(
                    "TYPE_BOOL_OP_NON_BOOL",
                    f"{op} requires boolean operands (got {lt}, {rt})",
                    node,
                )
            return TYPE_BOOL
        raise self._err(
            "TYPE_INTERNAL",
            f"unsupported AST node {type(node).__name__}",
            node,
        )

    def _check_call(self, node: A.Call) -> str:
        fn = node.fn
        if fn not in FUNCTION_ARITY:
            raise self._err(
                "TYPE_UNKNOWN_FUNCTION",
                f"function {fn!r} is not in the RSL-1 whitelist",
                node,
            )
        if len(node.args) != FUNCTION_ARITY[fn]:
            raise self._err(
                "TYPE_ARITY_MISMATCH",
                f"{fn} expects exactly {FUNCTION_ARITY[fn]} argument(s), "
                f"got {len(node.args)}",
                node,
            )
        arg_types = [self.check(arg) for arg in node.args]

        if fn in ("sma", "ema", "highest", "lowest"):
            if arg_types[0] != TYPE_SERIES:
                raise self._err(
                    "TYPE_ARG_NOT_SERIES", f"{fn} first argument must be a series", node
                )
            if arg_types[1] != TYPE_NUMBER:
                raise self._err(
                    "TYPE_ARG_NOT_NUMBER", f"{fn} period must be a number", node
                )
            return TYPE_SERIES
        if fn in ("rsi", "stdev"):
            if arg_types[0] != TYPE_SERIES:
                raise self._err(
                    "TYPE_ARG_NOT_SERIES", f"{fn} first argument must be a series", node
                )
            if arg_types[1] != TYPE_NUMBER:
                raise self._err(
                    "TYPE_ARG_NOT_NUMBER", f"{fn} period must be a number", node
                )
            return TYPE_SERIES
        if fn == "atr":
            for pos in (0, 1, 2):
                if arg_types[pos] != TYPE_SERIES:
                    raise self._err(
                        "TYPE_ARG_NOT_SERIES",
                        "atr arguments 1..3 must be series (high, low, close)",
                        node,
                    )
            if arg_types[3] != TYPE_NUMBER:
                raise self._err("TYPE_ARG_NOT_NUMBER", "atr period must be a number", node)
            return TYPE_SERIES
        if fn == "ref":
            if arg_types[0] != TYPE_SERIES:
                raise self._err(
                    "TYPE_REF_INVALID_BASE",
                    'ref(...) first argument must be a series (a string literal '
                    'such as "close" is not a series; write ref(close, n))',
                    node,
                )
            if arg_types[1] != TYPE_NUMBER:
                raise self._err("TYPE_ARG_NOT_NUMBER", "ref offset must be a number", node)
            return TYPE_SERIES
        if fn == "abs":
            if arg_types[0] == TYPE_BOOL:
                raise self._err("TYPE_MISMATCH_ARITH", "abs() requires a numeric argument", node)
            return arg_types[0]
        if fn in ("min", "max"):
            for t in arg_types:
                if t == TYPE_BOOL:
                    raise self._err(
                        "TYPE_MISMATCH_ARITH",
                        f"{fn}() requires numeric or series arguments",
                        node,
                    )
            return TYPE_SERIES if TYPE_SERIES in arg_types else TYPE_NUMBER
        # crossover / crossunder
        for t in arg_types:
            if t == TYPE_BOOL:
                raise self._err(
                    "TYPE_MISMATCH_ARITH",
                    f"{fn}() requires numeric or series arguments",
                    node,
                )
        return TYPE_BOOL


def infer(node: Expr, input_names: Iterable[str]) -> str:
    """Infer the static type of a single expression node."""
    return _TypeChecker(input_names).check(node)


def typecheck(program: Program) -> dict[int, str]:
    """Type-check every section expression of ``program``.

    Returns a map of ``id(node) -> type`` for every visited node. ENTRY, EXIT
    and ALERT sections must be boolean; the parser-inserted DEFAULT_FALSE
    sentinel for absent EXIT/ALERT sections is treated as bool.
    """
    checker = _TypeChecker(program.inputs.keys())
    for label, expr in (
        ("ENTRY", program.entry),
        ("EXIT", program.exit),
        ("ALERT", program.alert),
    ):
        if expr is DEFAULT_FALSE:
            checker.types[id(expr)] = TYPE_BOOL
            continue
        kind = checker.check(expr)
        if kind != TYPE_BOOL:
            raise DSLTypeError(
                f"{label} section must evaluate to a boolean condition, got {kind}",
                line=getattr(expr, "line", None),
                col=getattr(expr, "col", None),
                code="TYPE_SECTION_NOT_BOOL",
            )
    return dict(checker.types)
