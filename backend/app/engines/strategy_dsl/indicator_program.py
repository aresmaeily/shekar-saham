"""MASTER-RADAR directive §B4 (WAVE-B) — UIDL-1: the user indicator DSL.

UIDL-1 is the governed user-authored indicator language of the RADAR BOURSE
indicator platform (directive §4.3). It deliberately shares EVERY security-
relevant layer with RSL-1 (the audited restricted strategy language):

- the SAME hand-written lexer (:mod:`lexer`) — a fixed character allowlist,
  no string interpolation, no attribute access;
- the SAME recursive-descent expression parser (:mod:`parser`) — a pure
  tree-builder with a recursion guard, never evaluating anything;
- the SAME whitelisted function set and static type checker (:mod:`types`);
- the SAME semantic validator budgets and no-look-ahead rules
  (:mod:`validator`) — ``ref(x, n)`` with ``n < 0`` is refused, MTF
  references align through the close-provable timestamp rule;
- the SAME deterministic tree-walking interpreter (:mod:`runtime`) — there
  is NO eval/exec/compile, NO dynamic import and NO arbitrary-code path
  anywhere in this package. The DSL text is never turned into Python.

What UIDL-1 adds on top of RSL-1 is a *program shape* for indicators rather
than trading decisions::

    INDICATOR <name>
    INPUT <name> = <number>          (0..16, optional)
    PLOT <name> = <expression>       (1..8; expression must be a numeric SERIES)

Keywords are case-insensitive. Every PLOT must statically infer to a numeric
``series`` — boolean expressions (comparisons, AND/OR/NOT,
crossover/crossunder) are rejected at compile time, so a plot can never be a
hidden signal channel. Warm-up semantics are the runtime's documented
warm-up zeros; the structural warm-up of every plot is computed here and
published with the compiled program so charts can label the honest
"not yet valid" region instead of guessing.

Determinism: the same (program, context, inputs) triple always produces the
same values and the same ``evaluation_digest`` (sha256 over the canonical
plot values), pinned by tests including prefix-stability under
``end_bar_index``-style truncation (no look-ahead, ever).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from . import ast_nodes as A
from .ast_nodes import DEFAULT_FALSE, Expr, Program
from .errors import DSLBudgetError, DSLParseError, DSLRuntimeError, DSLSemanticError
from .lexer import tokenize
from .parser import _Parser
from .runtime import (
    SeriesContext,
    expression_series,
    prepare,
)
from .types import TYPE_SERIES, infer
from .validator import (
    MAX_DEPTH,
    MAX_MTF_TIMEFRAMES,
    MAX_NODES,
    MAX_SOURCE_LEN,
    MAX_SYMBOL_REFS,
    _PERIOD_MIN,
    _check_period,
    _check_ref_offset,
    _literal_number,
    expression_depth,
)

UIDL_VERSION = "UIDL-1"

MAX_PLOTS = 8
MAX_INDICATOR_NAME = 48
MAX_PLOT_NAME = 32
MAX_INPUTS = 16

#: Names that may never be used as an indicator/plot/INPUT identifier: they
#: collide with the lexer's keywords or the five series bases.
_RESERVED_NAMES = frozenset(A.SERIES_BASES) | frozenset(
    {"plot", "indicator", "input", "risk", "entry", "exit", "alert",
     "and", "or", "not", "sym"}
)

_IDENT_FIRST = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_IDENT_REST = _IDENT_FIRST | frozenset("0123456789")

_WINDOWED_FNS = ("sma", "ema", "rsi", "stdev", "highest", "lowest", "atr")


# ---------------------------------------------------------------------------
# program model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlotSpec:
    """One named PLOT of a user indicator (a series-valued expression)."""

    name: str
    expr: Expr
    warmup_bars: int


@dataclass(frozen=True)
class IndicatorProgram:
    """A fully compiled UIDL-1 program (immutable; digest-carrying)."""

    name: str
    inputs: dict[str, float]
    plots: tuple[PlotSpec, ...]
    mtf_refs: tuple
    symbol_refs: tuple
    source: str
    source_digest: str

    @property
    def warmup_bars(self) -> int:
        """Overall structural warm-up: the maximum over all plots."""
        return max((p.warmup_bars for p in self.plots), default=0)

    def plot_names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.plots)


@dataclass(frozen=True)
class IndicatorEvaluation:
    """Deterministic result of evaluating one program over one context."""

    plots: dict[str, list[float]]
    n_bars: int
    warmup_bars: int
    digest: str
    inputs: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# name / literal helpers
# ---------------------------------------------------------------------------

def _valid_identifier(name: str, what: str, max_len: int) -> str:
    if not isinstance(name, str) or not name:
        raise DSLParseError(f"{what} must be a non-empty identifier", code="PARSE_BAD_NAME")
    if len(name) > max_len:
        raise DSLParseError(
            f"{what} {name!r} is longer than {max_len} characters",
            code="PARSE_BAD_NAME",
        )
    if name.lower() in _RESERVED_NAMES:
        raise DSLParseError(
            f"{what} {name!r} is reserved (series bases and language keywords "
            "may not be redefined)",
            code="PARSE_RESERVED_NAME",
        )
    if name[0] not in _IDENT_FIRST or any(c not in _IDENT_REST for c in name[1:]):
        raise DSLParseError(
            f"{what} {name!r} must match [A-Za-z_][A-Za-z0-9_]*",
            code="PARSE_BAD_NAME",
        )
    return name


def _period_value(arg: Expr, inputs: dict[str, float], what: str) -> int:
    """Resolve a period/offset argument (integer literal or integer INPUT)."""
    literal = _literal_number(arg)
    if literal is not None:
        if not float(literal).is_integer():
            raise DSLSemanticError(
                f"{what} must be an integer, got {literal!r}",
                code="SEM_PERIOD_INVALID",
            )
        return int(literal)
    if isinstance(arg, A.InputRef):
        if arg.name not in inputs:
            raise DSLSemanticError(
                f"{what} INPUT {arg.name!r} is not declared",
                code="SEM_UNKNOWN_INPUT",
            )
        value = inputs[arg.name]
        if not float(value).is_integer():
            raise DSLSemanticError(
                f"{what} INPUT {arg.name!r} must be an integer, got {value!r}",
                code="SEM_PERIOD_INVALID",
            )
        return int(value)
    raise DSLSemanticError(
        f"{what} must be an integer literal or an integer INPUT",
        code="SEM_PERIOD_INVALID",
    )


# ---------------------------------------------------------------------------
# structural warm-up (documented, deterministic)
# ---------------------------------------------------------------------------

def structural_warmup(expr: Expr, inputs: dict[str, float]) -> int:
    """Index of the FIRST bar whose value is fully determined (warm-up bars).

    Convention matches the shipped builtin catalog (``sma(20)`` → 19): the
    warm-up region is ``[:warmup_bars]``. Mirrors the runtime's documented
    rules exactly: ``sma/ema/stdev/highest/lowest`` first produce a (fully
    or partial-window) value at index ``period-1``; ``rsi/atr`` are seeded
    by the shared Wilder smoother at index ``period``; ``ref(x, k)`` at
    index ``k``. Composite arithmetic takes the maximum of its operands;
    bases and INPUTs need no warm-up.

    Honesty note (documented, tested): for ``highest/lowest`` the bars
    inside the warm-up region carry PARTIAL-window values (the runtime's
    documented honest partial-window behaviour), not zeros — the zero-fill
    region claim applies to the zero-warmup functions (sma/ema/rsi/atr/ref
    and composites of those).

    Defensive shape policy: a call with a malformed arity contributes 0
    here instead of raising — ``validate_indicator_program`` (which runs
    right after parsing) rejects such programs with the precise typed
    error, so a malformed program never reaches evaluation anyway.
    """
    if isinstance(expr, (A.Num, A.InputRef, A.SeriesBase, A.MtfRef, A.SymbolRef)):
        return 0
    if isinstance(expr, A.Call):
        fn = expr.fn
        try:
            if fn == "ref" and len(expr.args) == 2:
                return max(0, _period_value(expr.args[1], inputs, "ref offset"))
            if fn in ("sma", "ema", "stdev", "highest", "lowest") and len(expr.args) == 2:
                return max(
                    _period_value(expr.args[1], inputs, f"{fn} period") - 1,
                    structural_warmup(expr.args[0], inputs),
                )
            if fn in ("rsi", "atr") and len(expr.args) in (2, 4):
                period = _period_value(expr.args[-1], inputs, f"{fn} period")
                operand_warmup = max(
                    structural_warmup(a, inputs) for a in expr.args[:-1]
                )
                return max(period, operand_warmup)
        except DSLSemanticError:
            return 0  # malformed period/offset: validation reports it precisely
        # abs / min / max (and anything malformed): warm-up through operands
        return max((structural_warmup(a, inputs) for a in expr.args), default=0)
    if isinstance(expr, A.BinOp):
        return max(structural_warmup(expr.l, inputs), structural_warmup(expr.r, inputs))
    if isinstance(expr, A.UnaryOp):
        return structural_warmup(expr.x, inputs)
    return 0


# ---------------------------------------------------------------------------
# validation (budgets + semantics across ALL plots)
# ---------------------------------------------------------------------------

def _shim_program(inputs: dict[str, float]) -> Program:
    """A minimal RSL-1 Program shape for validator helpers (never evaluated
    as a strategy: ENTRY is the DEFAULT_FALSE sentinel)."""
    return Program(
        inputs=dict(inputs),
        risk=None,
        entry=DEFAULT_FALSE,
        exit=DEFAULT_FALSE,
        alert=DEFAULT_FALSE,
        mtf_refs=(),
        symbol_refs=(),
        source_digest="",
    )


def validate_indicator_program(prog: IndicatorProgram) -> dict:
    """Enforce the RSL-1 resource budgets across the WHOLE indicator.

    Hard failures raise the same typed DSL error subclasses as RSL-1.
    Returns an advisory report (currently: unused INPUT names).
    """
    if not (1 <= len(prog.plots) <= MAX_PLOTS):
        raise DSLBudgetError(
            f"an indicator declares 1..{MAX_PLOTS} PLOT sections, got {len(prog.plots)}",
            code="BUDGET_PLOTS",
        )

    total_nodes = 1
    seen_plots: set[str] = set()
    for plot in prog.plots:
        key = plot.name.lower()
        if key in seen_plots:
            raise DSLSemanticError(
                f"duplicate PLOT name {plot.name!r}", code="SEM_DUPLICATE_PLOT"
            )
        seen_plots.add(key)
        nodes = sum(1 for _ in A.walk_expr(plot.expr))
        total_nodes += 1 + nodes
        if expression_depth(plot.expr) > MAX_DEPTH:
            raise DSLBudgetError(
                f"PLOT {plot.name!r} nesting exceeds the depth budget of {MAX_DEPTH}",
                code="BUDGET_DEPTH",
            )
        kind = infer(plot.expr, prog.inputs.keys())
        if kind != TYPE_SERIES:
            raise DSLSemanticError(
                f"PLOT {plot.name!r} must evaluate to a numeric series, got {kind}; "
                "boolean expressions (comparisons, AND/OR/NOT, crossover) are "
                "not plottable",
                code="SEM_PLOT_NOT_SERIES",
            )

    if total_nodes > MAX_NODES:
        raise DSLBudgetError(
            f"indicator AST has {total_nodes} nodes; budget is {MAX_NODES}",
            code="BUDGET_NODES",
        )

    mtf_timeframes = {ref.tf for ref in prog.mtf_refs}
    if len(mtf_timeframes) > MAX_MTF_TIMEFRAMES:
        raise DSLBudgetError(
            f"indicator references {len(mtf_timeframes)} MTF timeframes; "
            f"budget is {MAX_MTF_TIMEFRAMES}",
            code="BUDGET_MTF",
        )
    symbols = {ref.symbol for ref in prog.symbol_refs}
    if len(symbols) > MAX_SYMBOL_REFS:
        raise DSLBudgetError(
            f"indicator references {len(symbols)} symbols; budget is {MAX_SYMBOL_REFS}",
            code="BUDGET_SYMBOLS",
        )

    # No-look-ahead + period minimums for every call in every plot (the same
    # validator helpers RSL-1 uses — one rule set, one source of truth).
    shim = _shim_program(prog.inputs)
    for plot in prog.plots:
        for node in A.walk_expr(plot.expr):
            if isinstance(node, A.Call):
                if node.fn == "ref":
                    _check_ref_offset(node, shim)
                elif node.fn in _WINDOWED_FNS:
                    minimum = _PERIOD_MIN[node.fn]
                    _check_period(node, shim, minimum)
                    # mirror validator: warm-up coherence with the runtime
                    _period_value(node.args[-1], prog.inputs, f"{node.fn} period")
                # whitelist/arity/argument types are enforced by infer() above

# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def _parse_indicator_source(source: str) -> IndicatorProgram:
    tokens = tokenize(source)
    p = _Parser(tokens)

    name: str | None = None
    inputs: dict[str, float] = {}
    plots: list[tuple[str, Expr]] = []

    while True:
        while p._peek().kind == "NEWLINE":
            p._advance()
        token = p._peek()
        if token.kind == "EOF":
            break
        # The shared lexer emits INPUT (like RISK/ENTRY/…) as a KEYWORD;
        # INDICATOR and PLOT are NOT lexer keywords (adding them would break
        # existing RSL-1 programs using those words as identifiers), so they
        # arrive as IDENT and are dispatched case-insensitively here.
        is_input_kw = token.kind == "KEYWORD" and token.value == "INPUT"
        is_ident_kw = token.kind == "IDENT" and str(token.value).lower() in (
            "indicator",
            "plot",
        )
        if not (is_input_kw or is_ident_kw):
            raise DSLParseError(
                "expected a statement keyword (INDICATOR/INPUT/PLOT), found "
                f"{token.value!r}",
                line=token.line,
                col=token.col,
                code="PARSE_UNEXPECTED_TOKEN",
            )
        keyword = "input" if is_input_kw else str(token.value).lower()
        if keyword == "indicator":
            if name is not None:
                raise DSLParseError(
                    "duplicate INDICATOR section",
                    line=token.line,
                    col=token.col,
                    code="PARSE_DUPLICATE_SECTION",
                )
            p._advance()
            name_tok = p._expect("IDENT", "an indicator name")
            name = _valid_identifier(
                str(name_tok.value), "indicator name", MAX_INDICATOR_NAME
            )
        elif keyword == "input":
            if name is None:
                raise DSLParseError(
                    "the INDICATOR section must come first",
                    line=token.line,
                    col=token.col,
                    code="PARSE_MISSING_INDICATOR",
                )
            if len(inputs) >= MAX_INPUTS:
                raise DSLBudgetError(
                    f"at most {MAX_INPUTS} INPUT declarations are allowed",
                    code="BUDGET_INPUTS",
                )
            # reuse the RSL-1 INPUT parsing verbatim (name = number literal)
            before = dict(inputs)
            p._parse_input(inputs)
            added = set(inputs) - set(before)
            new_name = added.pop() if added else ""
            _valid_identifier(new_name, "input name", 32)
        else:  # plot
            if name is None:
                raise DSLParseError(
                    "the INDICATOR section must come first",
                    line=token.line,
                    col=token.col,
                    code="PARSE_MISSING_INDICATOR",
                )
            p._advance()
            plot_tok = p._expect("IDENT", "a plot name")
            plot_name = _valid_identifier(
                str(plot_tok.value), "plot name", MAX_PLOT_NAME
            )
            p._expect("EQ", "'='")
            expr = p._parse_or()
            plots.append((plot_name, expr))

        end = p._peek()
        if end.kind not in ("NEWLINE", "EOF"):
            raise DSLParseError(
                f"unexpected {end.value!r} after statement",
                line=end.line,
                col=end.col,
                code="PARSE_UNEXPECTED_TOKEN",
            )

    if name is None:
        raise DSLParseError(
            "an indicator program requires exactly one INDICATOR section",
            code="PARSE_MISSING_INDICATOR",
        )
    if not plots:
        raise DSLParseError(
            "an indicator program requires at least one PLOT section",
            code="PARSE_MISSING_PLOT",
        )

    plot_specs = tuple(
        PlotSpec(name=pname, expr=expr, warmup_bars=structural_warmup(expr, inputs))
        for pname, expr in plots
    )

    mtf_refs = tuple(
        node
        for _, expr in plots
        for node in A.walk_expr(expr)
        if isinstance(node, A.MtfRef)
    )
    symbol_refs = tuple(
        node
        for _, expr in plots
        for node in A.walk_expr(expr)
        if isinstance(node, A.SymbolRef)
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return IndicatorProgram(
        name=name,
        inputs=dict(inputs),
        plots=plot_specs,
        mtf_refs=mtf_refs,
        symbol_refs=symbol_refs,
        source=source,
        source_digest=digest,
    )


def compile_indicator_source(source: str) -> IndicatorProgram:
    """Full UIDL-1 pipeline: parse → typecheck per plot → budgets/semantics.

    The source-length budget is enforced before any lexing work (same policy
    as ``parser.compile_source``).
    """
    if not isinstance(source, str):
        raise DSLParseError("indicator source must be a string", code="PARSE_BAD_SOURCE")
    if len(source) > MAX_SOURCE_LEN:
        raise DSLBudgetError(
            f"indicator source is {len(source)} characters; budget is {MAX_SOURCE_LEN}",
            code="BUDGET_SOURCE_LEN",
        )
    prog = _parse_indicator_source(source)
    validate_indicator_program(prog)
    return prog


def validation_advisories(prog: IndicatorProgram) -> dict:
    """Recompute the advisory (non-raising) findings for a compiled program."""
    used_inputs = {
        node.name
        for plot in prog.plots
        for node in A.walk_expr(plot.expr)
        if isinstance(node, A.InputRef)
    }
    return {"unused_inputs": sorted(set(prog.inputs) - used_inputs)}


# ---------------------------------------------------------------------------
# evaluation (single execution path: the RSL-1 interpreter)
# ---------------------------------------------------------------------------

def _merged_inputs(prog: IndicatorProgram, overrides: dict[str, float] | None) -> dict[str, float]:
    merged = dict(prog.inputs)
    if overrides:
        if not isinstance(overrides, dict):
            raise DSLRuntimeError("inputs override must be a mapping", code="RUN_BAD_INPUTS")
        for k, v in overrides.items():
            if k not in merged:
                raise DSLRuntimeError(
                    f"unknown INPUT {k!r} (declared: {sorted(prog.inputs)})",
                    code="RUN_UNKNOWN_INPUT",
                )
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise DSLRuntimeError(
                    f"INPUT {k!r} must be a finite number", code="RUN_BAD_INPUTS"
                )
            fv = float(v)
            if not math.isfinite(fv):
                raise DSLRuntimeError(
                    f"INPUT {k!r} must be finite (NaN/Inf rejected)",
                    code="RUN_BAD_INPUTS",
                )
            merged[k] = fv
    return merged


def _synthetic_program(prog: IndicatorProgram, plot: PlotSpec, inputs: dict[str, float]) -> Program:
    """Wrap one PLOT as an RSL-1 Program so ``prepare`` pre-computes every
    cached sub-series of that expression through the audited path."""
    return Program(
        inputs=inputs,
        risk=None,
        entry=plot.expr,
        exit=DEFAULT_FALSE,
        alert=DEFAULT_FALSE,
        mtf_refs=tuple(
            node for node in A.walk_expr(plot.expr) if isinstance(node, A.MtfRef)
        ),
        symbol_refs=tuple(
            node for node in A.walk_expr(plot.expr) if isinstance(node, A.SymbolRef)
        ),
        source_digest=prog.source_digest,
    )


def evaluation_digest(
    prog: IndicatorProgram,
    inputs: dict[str, float],
    plots: dict[str, list[float]],
) -> str:
    """Deterministic sha256 over (version, source digest, inputs, values)."""
    h = hashlib.sha256()
    h.update(UIDL_VERSION.encode("ascii"))
    h.update(b"|")
    h.update(prog.source_digest.encode("ascii"))
    h.update(b"|")
    for name in sorted(inputs):
        h.update(name.encode("utf-8"))
        h.update(b"=")
        h.update(format(float(inputs[name]), ".17g").encode("ascii"))
        h.update(b";")
    h.update(b"|")
    for pname in sorted(plots):
        h.update(pname.encode("utf-8"))
        h.update(b":[")
        for v in plots[pname]:
            h.update(format(float(v), ".17g").encode("ascii"))
            h.update(b",")
        h.update(b"];")
    return h.hexdigest()


def evaluate_indicator(
    prog: IndicatorProgram,
    ctx: SeriesContext,
    *,
    inputs: dict[str, float] | None = None,
    mtf_context: dict[str, list[dict]] | None = None,
) -> IndicatorEvaluation:
    """Deterministic whole-series evaluation of every PLOT over ``ctx``.

    The ONLY execution path is :func:`runtime.prepare` +
    :func:`runtime.expression_series` — the audited RSL-1 interpreter. Any
    error surfaces as the typed DSL exceptions; nothing is swallowed.
    """
    if not isinstance(ctx, SeriesContext):
        raise DSLRuntimeError("ctx must be a SeriesContext", code="RUN_BAD_CONTEXT")
    merged = _merged_inputs(prog, inputs)
    plots: dict[str, list[float]] = {}
    warmup = 0
    for plot in prog.plots:
        synthetic = _synthetic_program(prog, plot, merged)
        prepared = prepare(synthetic, ctx, mtf_context=mtf_context)
        plots[plot.name] = expression_series(prepared, plot.expr)
        # evaluation-time warm-up: recompute against the MERGED inputs so an
        # INPUT override (e.g. len 20 -> 5) reports the warm-up the chart
        # will ACTUALLY show, not the compile-time default's (conservative
        # but imprecise) estimate. Falls back to the static estimate when a
        # malformed override makes the structural pass impossible — the
        # runtime below raises the precise typed error for such inputs.
        try:
            warmup = max(warmup, structural_warmup(plot.expr, merged))
        except DSLSemanticError:
            warmup = max(warmup, plot.warmup_bars)
    return IndicatorEvaluation(
        plots=plots,
        n_bars=len(ctx.close),
        warmup_bars=warmup,
        digest=evaluation_digest(prog, merged, plots),
        inputs=merged,
    )
