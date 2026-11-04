"""MASTER-RADAR directive §C2 — RADAR Strategy Language v1 (RSL-1) engine.

A RESTRICTED strategy language for the RADAR BOURSE product. Strategy source
is never executed as Python: the only execution path is this package's own
interpreter walking its own AST over a whitelisted, self-contained indicator
set. Sandbox-escape resistance is a first-class deliverable of this package.

Typical integration flow::

    from app.engines import strategy_dsl as rsl

    program = rsl.compile_source(source)            # parse+typecheck+validate
    prepared = rsl.prepare(program, ctx)            # bind one SeriesContext
    decision = rsl.evaluate_at(prepared, index)     # deterministic, per bar
    decisions = rsl.run_over_series(program, ctx)   # whole-series sweep
"""
from __future__ import annotations

from .ast_nodes import (
    And,
    BinOp,
    Call,
    Cmp,
    InputRef,
    MtfRef,
    Not,
    Num,
    Or,
    Program,
    RiskSpec,
    SeriesBase,
    SymbolRef,
    UnaryOp,
)
from .errors import (
    DSLBudgetError,
    DSLError,
    DSLLexError,
    DSLLookaheadError,
    DSLParseError,
    DSLRuntimeError,
    DSLSemanticError,
    DSLTypeError,
)
from .lexer import Token, tokenize
from .parser import compile_source, parse
from .runtime import (
    Decision,
    PreparedProgram,
    SeriesContext,
    context_digest,
    evaluate,
    evaluate_at,
    prepare,
    run_over_series,
)
from .types import FUNCTION_ARITY, infer, typecheck
from .validator import validate
from .versioning import (
    CONTRACT,
    DSL_VERSION,
    MIGRATION_POLICY,
    MigrationPolicy,
    StrategyApiContract,
    check_version_compat,
)

__all__ = [
    # versioning / contract
    "DSL_VERSION",
    "CONTRACT",
    "StrategyApiContract",
    "MigrationPolicy",
    "MIGRATION_POLICY",
    "check_version_compat",
    # pipeline
    "compile_source",
    "parse",
    "tokenize",
    "Token",
    "typecheck",
    "infer",
    "validate",
    "FUNCTION_ARITY",
    # runtime
    "PreparedProgram",
    "prepare",
    "evaluate",
    "evaluate_at",
    "run_over_series",
    "Decision",
    "SeriesContext",
    "context_digest",
    # AST
    "Program",
    "RiskSpec",
    "Num",
    "SeriesBase",
    "MtfRef",
    "SymbolRef",
    "InputRef",
    "Call",
    "BinOp",
    "UnaryOp",
    "Cmp",
    "Not",
    "And",
    "Or",
    # errors
    "DSLError",
    "DSLLexError",
    "DSLParseError",
    "DSLTypeError",
    "DSLSemanticError",
    "DSLBudgetError",
    "DSLLookaheadError",
    "DSLRuntimeError",
]
