"""MASTER-RADAR directive §C2 — machine-readable error hierarchy for RSL-1.

Every failure raised by the strategy-DSL engine derives from :class:`DSLError`
and carries a stable, API-safe ``code`` plus optional ``line``/``col``
positions pointing into the offending strategy source. Error codes use the
namespaces ``LEX_*``, ``PARSE_*``, ``TYPE_*``, ``SEM_*``, ``BUDGET_*``,
``LOOKAHEAD_*`` and ``RUN_*`` so callers can branch on failure classes without
parsing human-readable text.
"""
from __future__ import annotations


class DSLError(Exception):
    """Base class for every strategy-DSL failure."""

    code: str = "DSL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        if code is not None:
            self.code = code

    def __str__(self) -> str:
        if self.line is not None:
            loc = f"line {self.line}"
            if self.col is not None:
                loc += f", col {self.col}"
            return f"[{self.code}] {loc}: {self.message}"
        return f"[{self.code}] {self.message}"


class DSLLexError(DSLError):
    """Tokenizer failure (illegal character, malformed number, bad string)."""

    code = "LEX_ERROR"


class DSLParseError(DSLError):
    """Grammar failure (unexpected token, duplicate section, missing ENTRY)."""

    code = "PARSE_ERROR"


class DSLTypeError(DSLError):
    """Static type failure (arity, mismatched operand kinds, unknown name)."""

    code = "TYPE_ERROR"


class DSLSemanticError(DSLError):
    """Semantic failure (unknown function, bad period, bad risk range)."""

    code = "SEM_ERROR"


class DSLBudgetError(DSLError):
    """Resource-budget violation (nodes, depth, source length, MTF/symbols)."""

    code = "BUDGET_ERROR"


class DSLLookaheadError(DSLError):
    """Look-ahead attempt (negative ``ref`` offset) — rejected fail-closed."""

    code = "LOOKAHEAD_ERROR"


class DSLRuntimeError(DSLError):
    """Evaluation failure (missing series, out-of-range index, bad period)."""

    code = "RUN_ERROR"
