"""MASTER-RADAR directive §C2 — deterministic interpreter for RSL-1.

This module IS the execution path of the restricted strategy language: a
tree-walking interpreter over the AST in :mod:`ast_nodes` with a hand-written
whitelisted indicator library. Strategy text is never turned into Python code;
there is no eval/exec/compile anywhere in this package.

Deterministic definitions (documented behaviour, identical for every run):

- ``sma(v, p)``: rolling mean of the last ``p`` values including the current
  bar; ``0.0`` for indices ``< p - 1`` (warm-up).
- ``ema(v, p)``: seed at index ``p - 1`` is the plain mean of the first ``p``
  values; ``0.0`` before; afterwards ``ema_i = prev + k * (x - prev)`` with
  ``k = 2 / (p + 1)``.
- ``rsi(v, p)`` (p >= 2): Wilder RSI. Gains ``g_i = max(v_i - v_{i-1}, 0)``,
  losses ``l_i = max(v_{i-1} - v_i, 0)`` for ``i >= 1``. Seed at index ``p``:
  simple mean of ``g``/``l`` over ``i in [1, p]``; ``0.0`` for ``i < p``;
  afterwards Wilder smoothing ``avg = (prev * (p - 1) + cur) / p``.
  ``RSI = 100 - 100 / (1 + RS)``; if ``avg_loss == 0`` the result is ``100.0``
  (this includes a perfectly flat series; a rising-only series is 100.0, a
  falling-only series gives ``RS = 0`` hence RSI ``0.0``).
- ``stdev(v, p)``: rolling *population* standard deviation; ``0.0`` before
  warm-up.
- ``highest``/``lowest(v, p)``: rolling max/min over the last ``p`` values
  including the current bar; before warm-up the PARTIAL window from index 0
  is used (honest, documented partial-window behaviour).
- ``atr(h, l, c, p)``: true range ``tr_0 = h_0 - l_0`` and
  ``tr_i = max(h_i - l_i, |h_i - c_{i-1}|, |l_i - c_{i-1}|)``; Wilder
  smoothing exactly like RSI with seed at index ``p``; ``0.0`` before.
- ``crossover(a, b)``: ``a[i-1] <= b[i-1] and a[i] > b[i]``; ``False`` at
  index 0. ``crossunder`` mirrors with ``>=`` / ``<``.
- ``ref(v, n)``: value ``n`` bars ago; ``0.0`` when ``i - n < 0`` (documented
  warm-up). Negative ``n`` is a validator error and re-checked at runtime.
- Division: any ``x / 0`` evaluates to ``0.0`` (deterministic, documented;
  no exception is raised).
- Scalar arguments to ``crossover``/``crossunder``/``min``/``max`` act as
  constant series broadcast to the primary length.

Structural no-look-ahead guarantee: evaluation at index ``i`` reads only
series positions ``i`` and ``i - 1`` (crossover) and pre-computed indicator
values that are themselves backward-looking. Appending future bars to the
context therefore cannot change decisions at earlier indices — this property
is pinned by a dedicated regression test.

Multi-timeframe context (``mtf_context``, MR2-A WAVE-2): ``prepare``,
``evaluate`` and ``run_over_series`` accept an OPTIONAL ``mtf_context`` mapping
timeframe label -> a sequence of higher-timeframe BAR DICTS (not float lists).
Each referenced ``<TF>.<base>`` node is resolved to a primary-length float
series under a STRICT no-look-ahead alignment rule, enforced in code:

- Base timestamps come from the optional ``SeriesContext.ts`` field (epoch
  seconds, one per primary bar, ascending per the shared bar contract);
  ``mtf_context`` without ``ctx.ts`` is a ``RUN_MTF_MISSING_BASE_TS`` error.
- A higher-TF bar is readable at base bar ``i`` (timestamp ``t_i``) only when
  its CLOSE timestamp is ``<= t_i``. The close timestamp of higher-TF bar ``j``
  is derived from bar keys as follows: (1) the explicit ``close_ts`` key when
  present (a caller assertion that the bar is complete); (2) otherwise the
  next supplied bar's open timestamp ``ts[j+1]`` (bar ``j`` provably closed no
  later than the moment bar ``j+1`` opened); (3) otherwise — the final
  supplied bar without an explicit ``close_ts`` — the bar is treated as NOT
  YET CLOSED (callers who know a tail bar is complete must pass ``close_ts``).
  This makes the rule safe (a bar is only ever exposed after it provably
  closed) and future-append invariant: appending a higher-TF bar whose
  timestamps lie beyond every base timestamp cannot change any earlier
  decision (pinned by a dedicated regression test).
- When no higher-TF bar is closed yet at ``t_i`` (warm-up), the aligned value
  is ``0.0`` — the same documented warm-up fill every other series in this
  runtime uses; consumers must treat it exactly like other warm-up zeros.
- The most recent closed higher-TF bar wins. Aligned values override any
  equal-length series previously supplied through ``ctx.mtf`` for the same
  ``<TF>.<base>`` pair; timeframes absent from ``mtf_context`` keep failing
  closed with ``RUN_MISSING_MTF_SERIES``.

A :class:`PreparedProgram` is bound to exactly one context; it carries a
``ctx_digest`` (sha256 over every provided series, including ``ts`` and the
effective MTF series) so callers can assert they are not reusing a prepared
object across mutated contexts.
"""
from __future__ import annotations

import hashlib
import math
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from . import ast_nodes as A
from .ast_nodes import Expr, Program, RiskSpec
from .errors import DSLLookaheadError, DSLRuntimeError
from .types import INDICATOR_FNS

_SERIES_POLY_FNS = frozenset({"abs", "min", "max"})
_BOOL_FNS = frozenset({"crossover", "crossunder"})

_BASE_NAMES = ("open", "high", "low", "close", "volume")


class SeriesContext(BaseModel):
    """Primary OHLCV series plus optional MTF/symbol series (equal lengths).

    ``ts`` (optional, MR2-A) carries the epoch-second timestamp of every
    primary bar, ascending per the shared bar contract. It is required only
    for ``mtf_context`` alignment and participates in ``context_digest``.
    """

    model_config = ConfigDict(frozen=True)

    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]
    mtf: dict[str, dict[str, list[float]]] | None = None
    symbols: dict[str, dict[str, list[float]]] | None = None
    ts: list[int] | None = None


class Decision(BaseModel):
    """Result of evaluating one bar: three booleans plus resolved inputs."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    index: int
    entry: bool
    exit: bool
    alert: bool
    inputs: dict[str, float]
    risk: RiskSpec | None = None


@dataclass(frozen=True)
class PreparedProgram:
    """A program pre-compiled against one specific :class:`SeriesContext`.

    ``series_map`` maps ``id(node) -> list[float]`` for every series-valued
    node (bases, MTF/symbol refs, indicator calls). ``ctx_digest`` identifies
    the exact context the program was prepared against.
    """

    program: Program
    inputs: dict[str, float]
    risk: RiskSpec | None
    n_bars: int
    ctx_digest: str
    series_map: dict[int, list[float]] = field(default_factory=dict, repr=False, compare=False)


# ---------------------------------------------------------------------------
# indicator primitives (pure list -> list, deterministic)
# ---------------------------------------------------------------------------

def _sma(values: list[float], period: int) -> list[float]:
    n = len(values)
    out = [0.0] * n
    if period < 1 or period > n:
        return out
    for i in range(period - 1, n):
        out[i] = sum(values[i - period + 1 : i + 1]) / period
    return out


def _ema(values: list[float], period: int) -> list[float]:
    n = len(values)
    out = [0.0] * n
    if period < 1 or period > n:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    k = 2.0 / (period + 1.0)
    for i in range(period, n):
        prev = prev + k * (values[i] - prev)
        out[i] = prev
    return out


def _wilder_from_tr_or_gains(series: list[float], period: int) -> list[float]:
    """Shared Wilder smoothing: seed = mean(series[1..period]) at index period."""
    n = len(series)
    out = [0.0] * n
    if period < 1 or period + 1 > n:
        return out
    avg = sum(series[1 : period + 1]) / period
    out[period] = avg
    for i in range(period + 1, n):
        avg = (avg * (period - 1) + series[i]) / period
        out[i] = avg
    return out


def _rsi(values: list[float], period: int) -> list[float]:
    n = len(values)
    if period < 2:
        raise DSLRuntimeError(
            f"rsi period must be >= 2, got {period}", code="RUN_INVALID_PERIOD"
        )
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        delta = values[i] - values[i - 1]
        if delta > 0:
            gains[i] = delta
        elif delta < 0:
            losses[i] = -delta
    avg_gain = _wilder_from_tr_or_gains(gains, period)
    avg_loss = _wilder_from_tr_or_gains(losses, period)
    out = [0.0] * n
    for i in range(period, n):
        if avg_loss[i] == 0.0:
            out[i] = 100.0
        else:
            rs = avg_gain[i] / avg_loss[i]
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def _stdev(values: list[float], period: int) -> list[float]:
    n = len(values)
    out = [0.0] * n
    if period < 2 or period > n:
        return out
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        out[i] = math.sqrt(variance)
    return out


def _highest(values: list[float], period: int) -> list[float]:
    n = len(values)
    out = [0.0] * n
    for i in range(n):
        start = max(0, i - period + 1)  # partial window before warm-up
        out[i] = max(values[start : i + 1])
    return out


def _lowest(values: list[float], period: int) -> list[float]:
    n = len(values)
    out = [0.0] * n
    for i in range(n):
        start = max(0, i - period + 1)
        out[i] = min(values[start : i + 1])
    return out


def _atr(high: list[float], low: list[float], close: list[float], period: int) -> list[float]:
    n = len(close)
    tr = [0.0] * n
    if n > 0:
        tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    avg_tr = _wilder_from_tr_or_gains(tr, period)
    out = [0.0] * n
    for i in range(period, n):
        out[i] = avg_tr[i]
    return out


def _ref(values: list[float], offset: int) -> list[float]:
    n = len(values)
    out = [0.0] * n
    for i in range(n):
        j = i - offset
        if j >= 0:
            out[i] = values[j]
    return out


# ---------------------------------------------------------------------------
# structural helpers
# ---------------------------------------------------------------------------

def _is_series(node: Expr) -> bool:
    """Structurally decide whether ``node`` evaluates to a series."""
    if isinstance(node, (A.SeriesBase, A.MtfRef, A.SymbolRef)):
        return True
    if isinstance(node, A.Call):
        if node.fn in INDICATOR_FNS:
            return True
        if node.fn in _SERIES_POLY_FNS:
            return any(_is_series(arg) for arg in node.args)
        return False
    if isinstance(node, A.UnaryOp):
        return _is_series(node.x)
    if isinstance(node, A.BinOp):
        return _is_series(node.l) or _is_series(node.r)
    return False


def context_digest(ctx: SeriesContext) -> str:
    """Deterministic sha256 over every series in ``ctx`` (order-independent)."""
    digest = hashlib.sha256()

    def feed(label: str, values: list[float]) -> None:
        digest.update(label.encode("utf-8"))
        digest.update(b"[" + str(len(values)).encode("ascii") + b"]:")
        for v in values:
            digest.update(format(float(v), ".17g").encode("ascii"))
            digest.update(b",")

    for name in _BASE_NAMES:
        feed(name, list(getattr(ctx, name)))
    if ctx.ts is not None:
        feed("ts", list(ctx.ts))
    for group_name, group in (("mtf", ctx.mtf or {}), ("symbols", ctx.symbols or {})):
        for key in sorted(group):
            inner = group[key]
            for base in sorted(inner):
                feed(f"{group_name}:{key}.{base}", list(inner[base]))
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# MTF bar-dict alignment (MR2-A WAVE-2, no look-ahead)
# ---------------------------------------------------------------------------
_MTF_BAR_TS_KEYS = ("ts", "time")

# Bar-dict keys accepted for each series base (shared contract first, legacy
# engine shape second) — same alias precedence the rest of the repo documents.
_MTF_BAR_BASE_KEYS: dict[str, tuple[str, ...]] = {
    "open": ("o", "open"),
    "high": ("h", "high"),
    "low": ("l", "low"),
    "close": ("c", "close"),
    "volume": ("v", "volume"),
}


def _mtf_bar_field(bar: Mapping[str, Any], keys: tuple[str, ...], label: str) -> Any:
    for key in keys:
        if key in bar:
            return bar[key]
    raise DSLRuntimeError(
        f"mtf bar dict lacks a {label} key (accepted: {', '.join(keys)})",
        code="RUN_MTF_BAD_BARS",
    )


def _mtf_close_stamps(bars: Sequence[Mapping[str, Any]]) -> list[int | None]:
    """Close timestamp per higher-TF bar (see module docstring, rule 1..3)."""
    stamps = [int(_mtf_bar_field(b, _MTF_BAR_TS_KEYS, "timestamp")) for b in bars]
    out: list[int | None] = []
    for j, bar in enumerate(bars):
        explicit = bar.get("close_ts")
        if explicit is not None:
            out.append(int(explicit))
        elif j + 1 < len(bars):
            out.append(stamps[j + 1])  # provable close bound: next bar's open
        else:
            out.append(None)  # tail bar without close_ts: NOT yet closed
    return out


def _align_mtf_pair(
    bars: Sequence[Mapping[str, Any]], base_ts: list[int], tf: str, base: str
) -> list[float]:
    """Align one ``<TF>.<base>`` pair onto the primary timestamps, no look-ahead.

    At base timestamp ``t`` the value is the close value of the LATEST
    higher-TF bar whose close timestamp is ``<= t``; ``0.0`` (warm-up) when no
    such bar exists. Bars that are not yet closed are skipped, so a future
    bar can never be read. Base values are validated EAGERLY for every
    supplied bar (fail closed) even when no bar is readable yet.
    """
    close_stamps = _mtf_close_stamps(bars)
    keys = _MTF_BAR_BASE_KEYS[base]
    values: list[float] = []
    for j, bar in enumerate(bars):
        try:
            raw = _mtf_bar_field(bar, keys, f"{base!r} value")
        except DSLRuntimeError:
            raise DSLRuntimeError(
                f"missing MTF series {tf}.{base}: bar {j} carries none of the "
                f"accepted keys ({', '.join(keys)})",
                code="RUN_MISSING_MTF_SERIES",
            ) from None
        values.append(float(raw))
    closed_ts: list[int] = []
    closed_vals: list[float] = []
    for j in range(len(bars)):
        stamp = close_stamps[j]
        if stamp is None:
            continue
        closed_ts.append(stamp)
        closed_vals.append(values[j])
    # AUDIT-MR2 O3 fix (fail closed): the bisect below assumes ascending close
    # stamps; a non-monotonic explicit close_ts (or non-ascending bar order)
    # would otherwise misalign SILENTLY. Refuse instead — never guess.
    for j in range(1, len(closed_ts)):
        if closed_ts[j] < closed_ts[j - 1]:
            raise DSLRuntimeError(
                f"MTF series {tf}.{base}: close timestamps are not ascending "
                f"(index {j}: {closed_ts[j]} < {closed_ts[j - 1]}); "
                "non-monotonic close_ts breaks deterministic no-look-ahead alignment",
                code="RUN_MTF_NONMONOTONIC_CLOSE_TS",
            )
    out = [0.0] * len(base_ts)
    for i, t in enumerate(base_ts):
        idx = bisect_right(closed_ts, t) - 1
        if idx >= 0:
            out[i] = closed_vals[idx]
    return out


def _ctx_with_aligned_mtf(
    program: Program,
    ctx: SeriesContext,
    mtf_context: Mapping[str, Sequence[Mapping[str, Any]]],
) -> SeriesContext:
    """Return a copy of ``ctx`` whose ``mtf`` carries the aligned bar-dict series."""
    if not isinstance(mtf_context, Mapping):
        raise DSLRuntimeError(
            "mtf_context must map timeframe labels to sequences of bar dicts",
            code="RUN_BAD_CONTEXT",
        )
    n = len(ctx.close)
    if ctx.ts is None:
        raise DSLRuntimeError(
            "mtf_context requires SeriesContext.ts (per-bar epoch-second "
            "timestamps of the primary series)",
            code="RUN_MTF_MISSING_BASE_TS",
        )
    if len(ctx.ts) != n:
        raise DSLRuntimeError(
            f"ctx.ts has length {len(ctx.ts)}, primary length is {n}",
            code="RUN_SERIES_LENGTH_MISMATCH",
        )
    base_ts = [int(t) for t in ctx.ts]
    merged: dict[str, dict[str, list[float]]] = {
        tf: dict(series) for tf, series in (ctx.mtf or {}).items()
    }
    wanted: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in program.mtf_refs:
        pair = (ref.tf, ref.base)
        if pair not in seen:
            seen.add(pair)
            wanted.append(pair)
    for tf, base in wanted:
        bars = mtf_context.get(tf)
        if bars is None:
            # leave the pair unresolved: the regular prepare() path raises
            # RUN_MISSING_MTF_SERIES fail-closed for it
            continue
        merged.setdefault(tf, {})[base] = _align_mtf_pair(list(bars), base_ts, tf, base)
    return SeriesContext(
        open=list(ctx.open),
        high=list(ctx.high),
        low=list(ctx.low),
        close=list(ctx.close),
        volume=list(ctx.volume),
        mtf=merged,
        symbols=dict(ctx.symbols) if ctx.symbols is not None else None,
        ts=list(ctx.ts),
    )


# ---------------------------------------------------------------------------
# preparation (pre-compute every series-valued node once)
# ---------------------------------------------------------------------------

def prepare(
    program: Program,
    ctx: SeriesContext,
    *,
    mtf_context: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> PreparedProgram:
    """Pre-compute all series-valued nodes of ``program`` against ``ctx``.

    With ``mtf_context`` (optional mapping timeframe label -> higher-TF bar
    dicts), every declared ``<TF>.<base>`` reference is resolved through the
    documented no-look-ahead timestamp alignment instead of a plain
    equal-length list; see the module docstring for the exact rule.
    """
    if not isinstance(ctx, SeriesContext):
        raise DSLRuntimeError(
            "ctx must be a SeriesContext", code="RUN_BAD_CONTEXT"
        )
    if mtf_context is not None:
        ctx = _ctx_with_aligned_mtf(program, ctx, mtf_context)
    n = len(ctx.close)
    for name in _BASE_NAMES:
        if len(getattr(ctx, name)) != n:
            raise DSLRuntimeError(
                f"primary series {name!r} has length {len(getattr(ctx, name))}, "
                f"expected {n}",
                code="RUN_SERIES_LENGTH_MISMATCH",
            )

    primary: dict[str, list[float]] = {name: list(getattr(ctx, name)) for name in _BASE_NAMES}
    series_map: dict[int, list[float]] = {}
    inputs = dict(program.inputs)

    def check_length(values: list[float], label: str) -> list[float]:
        if len(values) != n:
            raise DSLRuntimeError(
                f"series {label} has length {len(values)}, primary length is {n}",
                code="RUN_SERIES_LENGTH_MISMATCH",
            )
        return values

    def resolve_series(node: Expr) -> list[float]:
        if isinstance(node, A.SeriesBase):
            return primary[node.name]
        if isinstance(node, A.MtfRef):
            tf_map = (ctx.mtf or {}).get(node.tf)
            if not isinstance(tf_map, dict) or node.base not in tf_map:
                raise DSLRuntimeError(
                    f"missing MTF series {node.tf}.{node.base} in context",
                    code="RUN_MISSING_MTF_SERIES",
                )
            return check_length(list(tf_map[node.base]), f"{node.tf}.{node.base}")
        if isinstance(node, A.SymbolRef):
            sym_map = (ctx.symbols or {}).get(node.symbol)
            if not isinstance(sym_map, dict) or node.base not in sym_map:
                raise DSLRuntimeError(
                    f"missing symbol series {node.symbol}.{node.base} in context",
                    code="RUN_MISSING_SYMBOL_SERIES",
                )
            return check_length(list(sym_map[node.base]), f"{node.symbol}.{node.base}")
        if isinstance(node, A.Call):
            cached = series_map.get(id(node))
            if cached is None:
                cached = compute_call_series(node)
                series_map[id(node)] = cached
            return cached
        raise DSLRuntimeError(
            f"expression {type(node).__name__} cannot produce a series",
            code="RUN_TYPE_ERROR",
        )

    def series_values(node: Expr) -> list[float]:
        """Full series of an arbitrary series-valued node (pointwise fallback
        for arithmetic combinations such as ``sma(close - open, 5)``)."""
        if isinstance(node, (A.SeriesBase, A.MtfRef, A.SymbolRef)):
            return resolve_series(node)
        if isinstance(node, A.Call):
            cached = series_map.get(id(node))
            if cached is None:
                cached = compute_call_series(node)
                series_map[id(node)] = cached
            return cached
        if isinstance(node, A.UnaryOp):
            return [-v for v in series_values(node.x)]
        if isinstance(node, A.BinOp):
            lv = series_values(node.l) if _is_series(node.l) else scalar(node.l)
            rv = series_values(node.r) if _is_series(node.r) else scalar(node.r)
            length = max(
                len(v) for v in (lv, rv) if isinstance(v, list)
            )
            out: list[float] = []
            for i in range(length):
                a = lv[i] if isinstance(lv, list) else lv
                b = rv[i] if isinstance(rv, list) else rv
                out.append(arith(node.op, a, b))
            return out
        raise DSLRuntimeError(
            f"expression {type(node).__name__} cannot produce a series",
            code="RUN_TYPE_ERROR",
        )

    def scalar(node: Expr) -> float:
        if isinstance(node, A.Num):
            return float(node.v)
        if isinstance(node, A.InputRef):
            if node.name not in inputs:
                raise DSLRuntimeError(
                    f"undeclared INPUT {node.name!r}", code="RUN_UNKNOWN_INPUT"
                )
            return float(inputs[node.name])
        if isinstance(node, A.UnaryOp):
            return -scalar(node.x)
        if isinstance(node, A.BinOp):
            return arith(node.op, scalar(node.l), scalar(node.r))
        if isinstance(node, A.Call) and node.fn in _SERIES_POLY_FNS:
            args = [scalar(arg) for arg in node.args]
            if node.fn == "abs":
                return abs(args[0])
            if node.fn == "min":
                return min(args)
            return max(args)
        raise DSLRuntimeError(
            f"expression {type(node).__name__} cannot be a scalar here",
            code="RUN_TYPE_ERROR",
        )

    def arith(op: str, lv: float, rv: float) -> float:
        if op == "/":
            if rv == 0.0:
                return 0.0  # documented deterministic x/0 -> 0.0
            return lv / rv
        if op == "+":
            return lv + rv
        if op == "-":
            return lv - rv
        return lv * rv

    def as_period(value: float, fn: str, minimum: int) -> int:
        if isinstance(value, bool) or not float(value).is_integer():
            raise DSLRuntimeError(
                f"{fn} period must be an integer, got {value!r}",
                code="RUN_INVALID_PERIOD",
            )
        period = int(value)
        if period < minimum:
            raise DSLRuntimeError(
                f"{fn} period must be >= {minimum}, got {period}",
                code="RUN_INVALID_PERIOD",
            )
        return period

    def compute_call_series(call: A.Call) -> list[float]:
        fn = call.fn
        if fn == "atr":
            high = series_values(call.args[0])
            low = series_values(call.args[1])
            close = series_values(call.args[2])
            period = as_period(scalar(call.args[3]), "atr", 1)
            return _atr(high, low, close, period)
        if fn in ("sma", "ema", "rsi", "stdev", "highest", "lowest"):
            values = series_values(call.args[0])
            minimum = 2 if fn in ("rsi", "stdev") else 1
            period = as_period(scalar(call.args[1]), fn, minimum)
            if fn == "sma":
                return _sma(values, period)
            if fn == "ema":
                return _ema(values, period)
            if fn == "rsi":
                return _rsi(values, period)
            if fn == "stdev":
                return _stdev(values, period)
            if fn == "highest":
                return _highest(values, period)
            return _lowest(values, period)
        if fn == "ref":
            values = series_values(call.args[0])
            raw = scalar(call.args[1])
            if not float(raw).is_integer():
                raise DSLRuntimeError(
                    f"ref offset must be an integer, got {raw!r}",
                    code="RUN_INVALID_PERIOD",
                )
            offset = int(raw)
            if offset < 0:
                raise DSLLookaheadError(
                    f"ref(...) offset {offset} looks into the future",
                    code="LOOKAHEAD_NEGATIVE_REF",
                )
            return _ref(values, offset)
        if fn in _SERIES_POLY_FNS:
            args: list[float | list[float]] = [
                series_values(arg) if _is_series(arg) else scalar(arg) for arg in call.args
            ]
            length = max(len(v) for v in args if isinstance(v, list))
            fn_impl = {"abs": abs, "min": min, "max": max}[fn]
            out: list[float] = []
            for i in range(length):
                point = [v[i] if isinstance(v, list) else v for v in args]
                out.append(float(fn_impl(*point)))
            return out
        raise DSLRuntimeError(
            f"function {fn!r} cannot produce a series", code="RUN_TYPE_ERROR"
        )

    for expr in (program.entry, program.exit, program.alert):
        for node in A.walk_expr(expr):
            if isinstance(node, (A.SeriesBase, A.MtfRef, A.SymbolRef)):
                series_map[id(node)] = resolve_series(node)
            elif isinstance(node, A.Call) and _is_series(node):
                resolve_series(node)

    return PreparedProgram(
        program=program,
        inputs=inputs,
        risk=program.risk,
        n_bars=n,
        ctx_digest=context_digest(ctx),
        series_map=series_map,
    )


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------

def _truthy(value: float | bool) -> bool:
    return value is True


def _num(value: float | bool, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DSLRuntimeError(
            f"expected a numeric value for {what}, got {type(value).__name__}",
            code="RUN_TYPE_ERROR",
        )
    return float(value)


def evaluate_at(prepared: PreparedProgram, index: int) -> Decision:
    """Evaluate the prepared program at exactly one bar index."""
    if (
        isinstance(index, bool)
        or not isinstance(index, int)
        or index < 0
        or index >= prepared.n_bars
    ):
        raise DSLRuntimeError(
            f"index {index!r} outside prepared range [0, {prepared.n_bars})",
            code="RUN_INDEX_OUT_OF_RANGE",
        )
    program = prepared.program
    series_map = prepared.series_map

    def value_at(node: Expr, i: int) -> float | bool:
        if isinstance(node, A.Num):
            return node.v
        if isinstance(node, (A.SeriesBase, A.MtfRef, A.SymbolRef)):
            cached = series_map.get(id(node))
            if cached is None:
                raise DSLRuntimeError(
                    "series node was not prepared", code="RUN_TYPE_ERROR"
                )
            return cached[i]
        if isinstance(node, A.InputRef):
            if node.name not in prepared.inputs:
                raise DSLRuntimeError(
                    f"undeclared INPUT {node.name!r}", code="RUN_UNKNOWN_INPUT"
                )
            return prepared.inputs[node.name]
        if isinstance(node, A.Call):
            cached = series_map.get(id(node))
            if cached is not None:
                return cached[i]
            if node.fn in _BOOL_FNS:
                return _cross(node, i)
            if node.fn == "abs":
                return abs(_num(value_at(node.args[0], i), "abs()"))
            if node.fn == "min":
                return min(_num(value_at(a, i), "min()") for a in node.args)
            if node.fn == "max":
                return max(_num(value_at(a, i), "max()") for a in node.args)
            raise DSLRuntimeError(
                f"function {node.fn!r} cannot be evaluated", code="RUN_TYPE_ERROR"
            )
        if isinstance(node, A.UnaryOp):
            return -_num(value_at(node.x, i), "unary '-'")
        if isinstance(node, A.BinOp):
            lv = _num(value_at(node.l, i), node.op)
            rv = _num(value_at(node.r, i), node.op)
            if node.op == "/":
                return 0.0 if rv == 0.0 else lv / rv
            if node.op == "+":
                return lv + rv
            if node.op == "-":
                return lv - rv
            return lv * rv
        if isinstance(node, A.Cmp):
            lv = _num(value_at(node.l, i), node.op)
            rv = _num(value_at(node.r, i), node.op)
            op = node.op
            if op == ">":
                return lv > rv
            if op == "<":
                return lv < rv
            if op == ">=":
                return lv >= rv
            if op == "<=":
                return lv <= rv
            if op == "==":
                return lv == rv
            return lv != rv
        if isinstance(node, A.Not):
            inner = value_at(node.x, i)
            if not isinstance(inner, bool):
                raise DSLRuntimeError(
                    "NOT applied to a non-boolean", code="RUN_TYPE_ERROR"
                )
            return not inner
        if isinstance(node, (A.And, A.Or)):
            lv = value_at(node.l, i)
            rv = value_at(node.r, i)
            if not isinstance(lv, bool) or not isinstance(rv, bool):
                raise DSLRuntimeError(
                    "boolean operator applied to a non-boolean", code="RUN_TYPE_ERROR"
                )
            return (lv and rv) if isinstance(node, A.And) else (lv or rv)
        raise DSLRuntimeError(
            f"cannot evaluate node {type(node).__name__}", code="RUN_TYPE_ERROR"
        )

    def _cross(call: A.Call, i: int) -> bool:
        if i == 0:
            return False  # documented: no previous bar, never a cross
        a, b = call.args
        a_prev = _num(value_at(a, i - 1), "crossover")
        b_prev = _num(value_at(b, i - 1), "crossover")
        a_now = _num(value_at(a, i), "crossover")
        b_now = _num(value_at(b, i), "crossover")
        if call.fn == "crossover":
            return a_prev <= b_prev and a_now > b_now
        return a_prev >= b_prev and a_now < b_now

    entry_value = value_at(program.entry, index)
    exit_value = value_at(program.exit, index)
    alert_value = value_at(program.alert, index)
    return Decision(
        index=index,
        entry=_truthy(entry_value),
        exit=_truthy(exit_value),
        alert=_truthy(alert_value),
        inputs=dict(prepared.inputs),
        risk=prepared.risk,
    )


def evaluate(
    program: Program,
    ctx: SeriesContext,
    index: int,
    *,
    mtf_context: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> Decision:
    """One-shot evaluation: prepare against ``ctx`` then evaluate ``index``."""
    return evaluate_at(prepare(program, ctx, mtf_context=mtf_context), index)


def run_over_series(
    program: Program,
    ctx: SeriesContext,
    *,
    mtf_context: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> list[Decision]:
    """Deterministic per-bar decision list over the whole context.

    ``mtf_context`` (optional) aligns declared higher-timeframe references
    onto the primary series under the strict no-look-ahead rule documented in
    the module docstring; it requires ``ctx.ts``.
    """
    prepared = prepare(program, ctx, mtf_context=mtf_context)
    return [evaluate_at(prepared, i) for i in range(prepared.n_bars)]
