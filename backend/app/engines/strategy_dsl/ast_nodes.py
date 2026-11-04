"""MASTER-RADAR directive §C2 — immutable AST for the RSL-1 strategy language.

Every node is a frozen dataclass carrying a ``line``/``col`` position (1-based)
into the strategy source. The interpreter in ``runtime.py`` walks these nodes
directly; nothing in this package ever turns strategy text into Python code.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Union

# The five primary series bases (lowercase), aligned to the bar sequence.
SERIES_BASES: tuple[str, ...] = ("open", "high", "low", "close", "volume")

# The only multi-timeframe prefixes accepted by the language.
VALID_TIMEFRAMES: tuple[str, ...] = ("D1", "W1", "M1", "H4", "H1")


@dataclass(frozen=True)
class RiskSpec:
    """Optional per-strategy risk parameters; ``None`` means "not set".

    Range enforcement is the validator's job (``SEM_RISK_RANGE``) so that the
    parser can build the object first and report one precise error later.
    """

    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_pct: float | None = None
    max_position_pct: float | None = None


@dataclass(frozen=True)
class Num:
    """Numeric literal. ``v`` is ``int`` when the source had no decimal point."""

    v: float | int
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class SeriesBase:
    """A primary series base such as ``close``."""

    name: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class MtfRef:
    """A multi-timeframe series reference such as ``D1.close``."""

    tf: str
    base: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class SymbolRef:
    """A cross-symbol series reference such as ``sym("TEHRAN.X").close``."""

    symbol: str
    base: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class InputRef:
    """A reference to a declared INPUT value; resolves to a number."""

    name: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class Call:
    """A whitelisted function call; ``args`` is a tuple of expression nodes."""

    fn: str
    args: tuple["Expr", ...]
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class BinOp:
    """Arithmetic binary operator: ``+``, ``-``, ``*`` or ``/``."""

    op: str
    l: "Expr"
    r: "Expr"
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class UnaryOp:
    """Unary minus."""

    op: str
    x: "Expr"
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class Cmp:
    """Numeric comparison: ``>``, ``<``, ``>=``, ``<=``, ``==`` or ``!=``."""

    op: str
    l: "Expr"
    r: "Expr"
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class Not:
    """Logical negation of a boolean expression."""

    x: "Expr"
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class And:
    """Logical conjunction of two boolean expressions."""

    l: "Expr"
    r: "Expr"
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class Or:
    """Logical disjunction of two boolean expressions."""

    l: "Expr"
    r: "Expr"
    line: int = 0
    col: int = 0


Expr = Union[
    Num,
    SeriesBase,
    MtfRef,
    SymbolRef,
    InputRef,
    Call,
    BinOp,
    UnaryOp,
    Cmp,
    Not,
    And,
    Or,
]

# Sentinel used by the parser for an absent EXIT/ALERT section: the documented
# "default constant False". Identity-checked (``is``) by the type checker so a
# user-written ``EXIT 0`` is still rejected as a non-boolean section.
DEFAULT_FALSE = Num(v=0.0, line=0, col=0)


@dataclass(frozen=True)
class Program:
    """A fully parsed RSL-1 program.

    ``inputs`` preserves the literal kinds from the source (an integer literal
    stays an ``int``); ``mtf_refs``/``symbol_refs`` collect every MTF/symbol
    reference in encounter order; ``source_digest`` is the sha256 hex digest of
    the exact source string.
    """

    inputs: dict[str, float]
    risk: RiskSpec | None
    entry: Expr
    exit: Expr
    alert: Expr
    mtf_refs: tuple
    symbol_refs: tuple
    source_digest: str


def walk_expr(node: Expr) -> Iterator[Expr]:
    """Yield ``node`` and every descendant expression node (pre-order)."""
    yield node
    if isinstance(node, Call):
        for arg in node.args:
            yield from walk_expr(arg)
    elif isinstance(node, (BinOp, Cmp, And, Or)):
        yield from walk_expr(node.l)
        yield from walk_expr(node.r)
    elif isinstance(node, (UnaryOp, Not)):
        yield from walk_expr(node.x)
