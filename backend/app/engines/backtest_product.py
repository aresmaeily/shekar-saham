"""Product-grade backtest engine for RADAR BOURSE (MASTER-RADAR directive, Wave 5).

Directive coverage:
- §D1: strategy adapter protocol (``SignalDecision`` / ``StrategyAdapter``).
  The DSL from the parallel strategy package is adapted onto this protocol by
  the integrator; this module NEVER imports strategy_dsl.
- §D2: execution realism is strictly delegated to
  ``app.engines.execution_model`` (fills, spread, slippage, latency, lots,
  volume cap, margin, currency multiplier). This engine invents no costs.
- §D3: fail-closed data policy. Data problems are RECORDED per symbol into
  ``data_quality`` refusals, never silently dropped; a run aborts (ValueError)
  only when EVERY symbol is refused.
- §D4: parameter search / selection lives in ``backtest_optimizer``. The
  walk-forward in this file only EVALUATES fixed adapters — it never selects.
- §D5: the report carries every headline number together with its documented
  assumptions (``annualization_assumption``, ``limitations``), and never
  claims real-tick fidelity or verified data unless the caller asserts a
  VERIFIED ``data_trust_label``.

Honesty contracts (each covered by a test):
- Bar-based simulation ONLY; nothing here is real-tick execution.
- Engine-side no-look-ahead: under ``NEXT_BAR_OPEN`` (default) every fill
  executes at a bar STRICTLY AFTER the signal bar; ``SAME_BAR_CLOSE`` is an
  explicit, declared approximation. The adapter contract is that
  ``decide(index)`` uses only data with index <= index; the engine calls
  ``decide`` exactly once per bar in ascending order and cannot structurally
  prove adapter honesty — the tests document this contract instead.
- Same-bar pessimism: when ``intrabar_tp_sl`` is enabled and a single bar
  touches both the stop and the target, the STOP is assumed to hit first.
- Determinism: identical inputs produce an identical report and an identical
  ``result_digest()``. No clock reads, no RNG, no I/O anywhere in this module.

Accounting conventions (documented, tested):
- Cash is account-currency; ``currency_multiplier`` is applied at notional.
- Fill prices INCLUDE spread+slippage (per execution_model). Commission cash
  is deducted from cash and from net pnl; the spread/slippage cash components
  from ``cost_breakdown`` are REPORTED per trade (``spread_cash`` /
  ``slippage_cash``) but never subtracted twice.
- Long entry: cash -= notional + commission. Long exit: cash += notional -
  commission. Short entry (only when ``allow_short``): cash += notional -
  commission; short cover: cash -= notional + commission. Equity = cash +
  sum(qty * last_close * currency_multiplier) (short qty is negative).
- Margin availability passed to ``simulate_fill``: equity minus notional of
  positions that are NOT being closed (a closing trade releases its margin).
- Sizing uses the signal-bar close and is pre-capped by max_position_pct and
  by estimated margin feasibility; execution-bar drift can still refuse a
  fill via ``margin_insufficient`` (recorded, fail-closed).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.engines.execution_model import (
    EXECUTION_MODEL_VERSION,
    ExecutionModelConfig,
    FillResult,
    apply_spread_slippage,
    cost_breakdown,
    simulate_fill,
    validate_bars,
)

__all__ = [
    "ENGINE_VERSION",
    "SignalDecision",
    "StrategyAdapter",
    "RiskModel",
    "PortfolioLimits",
    "DataPolicy",
    "BacktestRunConfig",
    "WalkForwardProductConfig",
    "run_backtest",
    "run_walk_forward_product",
]

ENGINE_VERSION = "BT-PRODUCT-1.0.0"

_TRUST_NOTE = "bar-based simulation; never real-tick"
_ANNUALIZATION_ASSUMPTION = "sqrt(252) bar-return scaling; rf=0"
_EXIT_SIGNAL = "SIGNAL"
_EXIT_STOP = "STOP_LOSS"
_EXIT_TARGET = "TAKE_PROFIT"
_EXIT_TRAILING = "TRAILING_STOP"
_EXIT_END_OF_DATA = "END_OF_DATA"


# ---------------------------------------------------------------------------
# §D1 — strategy adapter protocol (DSL is adapted onto this by the integrator)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignalDecision:
    """One bar's decision from a strategy adapter.

    ``decide(index)`` MUST consult only bars with index <= ``index``
    (adapter-side no-look-ahead contract).
    """

    entry: bool = False
    exit: bool = False
    stop_loss_pct: float | None = None   # overrides run-level risk if not None
    take_profit_pct: float | None = None
    trailing_pct: float | None = None
    size_pct: float | None = None        # fraction of equity for this entry


class StrategyAdapter(Protocol):
    """Protocol every strategy must satisfy to run on this engine."""

    strategy_id: str

    def prepare(self, bars: list[dict]) -> None:
        """Precompute indicators once; receives the full bar list up front."""
        ...

    def decide(self, index: int) -> SignalDecision:
        """Decision for bar ``index``; only data <= index may be consulted."""
        ...


# ---------------------------------------------------------------------------
# Configuration models (fail-closed, frozen, fully echoed into the report)
# ---------------------------------------------------------------------------


class RiskModel(BaseModel):
    """Run-level risk/sizing model (directive §D2/§D3)."""

    model_config = ConfigDict(frozen=True)

    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_pct: float | None = None
    max_position_pct: float = Field(default=100.0, gt=0.0, le=100.0)
    sizing_mode: Literal["FIXED_PCT_EQUITY", "RISK_BASED"] = "FIXED_PCT_EQUITY"
    # RISK_BASED: qty = equity * risk_pct_of_equity/100 / stop_distance.
    risk_pct_of_equity: float = Field(default=1.0, gt=0.0, le=100.0)


class PortfolioLimits(BaseModel):
    """Account-level portfolio constraints.

    Same-bar policy (documented): by default the engine REFUSES to re-enter a
    symbol on the bar where that symbol's position was closed
    (``allow_same_bar_reentry=False``); set True to permit same-bar re-entry.
    """

    model_config = ConfigDict(frozen=True)

    max_open_positions: int = Field(default=5, ge=1)
    equal_weight: bool = True
    per_symbol_blacklist: list[str] = Field(default_factory=list)
    allow_same_bar_reentry: bool = False


class DataPolicy(BaseModel):
    """Fail-closed data-quality policy (directive §D3).

    ``adjustment_semantics`` is DECLARED and echoed — this engine never
    silently adjusts prices; corporate-action application is upstream's
    declared responsibility.
    """

    model_config = ConfigDict(frozen=True)

    min_bars: int = Field(default=50, ge=0)
    max_staleness_seconds: int | None = None
    adjustment_semantics: Literal["UNADJUSTED", "ADJUSTED"] = "UNADJUSTED"
    refuse_gaps: bool = False


class BacktestRunConfig(BaseModel):
    """Full configuration of one product backtest run; echoed verbatim."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    execution: ExecutionModelConfig
    risk: RiskModel = Field(default_factory=RiskModel)
    portfolio: PortfolioLimits = Field(default_factory=PortfolioLimits)
    data_policy: DataPolicy = Field(default_factory=DataPolicy)
    benchmark_symbol: str | None = None
    regime_labels: dict[str, list[int]] | None = None
    as_of_ts: int | None = None
    notes: str = ""
    # Honesty label asserted by the caller; echoed into the report and into
    # auto-generated limitations. Anything not starting with "VERIFIED" is
    # reported as synthetic/fixture data.
    data_trust_label: str = "SYNTHETIC_OR_PAPER"


class WalkForwardProductConfig(BaseModel):
    """Chronological walk-forward splitting (product level, no selection)."""

    model_config = ConfigDict(frozen=True)

    n_splits: int = Field(ge=2)
    anchored: bool = True
    min_train_bars: int = Field(ge=1)
    min_test_bars: int = Field(ge=1)


# ---------------------------------------------------------------------------
# Report models (directive §D5 — every field with its assumption)
# ---------------------------------------------------------------------------


class EquityPoint(BaseModel):
    """One account mark-to-market point on the equity curve."""

    model_config = ConfigDict(frozen=True)

    ts: int
    equity: float
    drawdown_pct: float
    underwater_pct: float  # explicit alias of drawdown_pct


class ProductTrade(BaseModel):
    """One closed round-trip trade with full cost attribution."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    side: Literal["LONG", "SHORT"]
    entry_signal_index: int
    entry_index: int
    entry_ts: int
    entry_price: float          # fill price incl. spread/slippage
    exit_signal_index: int
    exit_index: int
    exit_ts: int
    exit_price: float           # fill price incl. spread/slippage
    qty: float
    gross_pnl: float
    net_pnl: float
    commission_cash: float      # deducted from cash and from net pnl
    spread_cash: float          # embedded in fill prices (reported, not re-deducted)
    slippage_cash: float        # embedded in fill prices (reported, not re-deducted)
    holding_bars: int
    exit_reason: str
    mae_pct: float
    mfe_pct: float
    regime_label: int | None = None
    closed_at_end_of_data: bool = False


class SymbolDataQuality(BaseModel):
    """Per-symbol data-quality record (refusals recorded, never raised away)."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    bars_used: int
    bars_refused: int
    refusals: list[str]
    adjustment_semantics: str
    trust_note: str = _TRUST_NOTE


class BenchmarkComparison(BaseModel):
    """Buy-and-hold benchmark with the SAME cost model, single entry at bar 0."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    strategy_total_return_pct: float | None
    benchmark_total_return_pct: float | None
    strategy_max_drawdown_pct: float
    benchmark_max_drawdown_pct: float
    benchmark_equity_curve: list[EquityPoint]


class MonthlyReturn(BaseModel):
    model_config = ConfigDict(frozen=True)
    year: int
    month: int
    return_pct: float | None


class YearlyReturn(BaseModel):
    model_config = ConfigDict(frozen=True)
    year: int
    return_pct: float | None


class TradeBin(BaseModel):
    model_config = ConfigDict(frozen=True)
    bin_low: float
    bin_high: float
    count: int


class SideStats(BaseModel):
    model_config = ConfigDict(frozen=True)
    trades: int = 0
    wins: int = 0
    net_pnl: float = 0.0


class LongShortDecomposition(BaseModel):
    model_config = ConfigDict(frozen=True)
    long: SideStats = Field(default_factory=SideStats)
    short: SideStats = Field(default_factory=SideStats)


class RegimeSegment(BaseModel):
    model_config = ConfigDict(frozen=True)
    regime: int
    trades: int
    win_rate: float | None
    total_return_pct: float | None


class ReportMetrics(BaseModel):
    """All directive §D5 report numbers and series."""

    model_config = ConfigDict(frozen=True)

    total_return_pct: float | None = None
    annualized_return_pct: float | None = None
    cagr_pct: float | None = None
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_bars: int = 0
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    win_rate: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    trade_count: int = 0
    exposure_pct: float = 0.0
    avg_holding_bars: float | None = None
    turnover: float | None = None
    fees_total: float = 0.0
    annualization_assumption: str = _ANNUALIZATION_ASSUMPTION
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    monthly_returns: list[MonthlyReturn] = Field(default_factory=list)
    yearly_returns: list[YearlyReturn] = Field(default_factory=list)
    trade_distribution: list[TradeBin] = Field(default_factory=list)
    long_short_decomposition: LongShortDecomposition = Field(default_factory=LongShortDecomposition)
    regime_segments: list[RegimeSegment] = Field(default_factory=list)
    event_counters: dict[str, int] = Field(default_factory=dict)


class BacktestResult(BaseModel):
    """Complete, reproducible result of one product backtest run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    engine_version: str
    execution_model_version: str
    generated_by_digest: str
    config_echo: dict[str, Any]
    data_quality: list[SymbolDataQuality]
    data_trust_label: str
    trades: list[ProductTrade] = Field(default_factory=list)
    report: ReportMetrics
    benchmark: BenchmarkComparison | None = None
    multiple_testing_note: str = ""
    limitations: list[str] = Field(default_factory=list)

    _symbol_digest_inputs: dict[str, Any] = PrivateAttr(default_factory=dict)

    def result_digest(self) -> str:
        """sha256 over the canonical reproducibility payload.

        Payload (directive-mandated): engine_version, execution_model_version,
        config_echo, per-symbol bar counts + first/last ts + sha256 of each
        symbol's (ts, c) pairs, and the final report numbers rounded to 10
        decimals. Identical inputs -> identical digest (tested).
        """
        return _sha256_of_json(
            _digest_payload(
                self.engine_version,
                self.execution_model_version,
                self.config_echo,
                self._symbol_digest_inputs,
                self.report,
            )
        )


# ---------------------------------------------------------------------------
# Walk-forward result models
# ---------------------------------------------------------------------------


class WindowMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_return_pct: float | None = None
    sharpe: float | None = None
    trade_count: int = 0
    max_drawdown_pct: float = 0.0


class WalkForwardWindow(BaseModel):
    model_config = ConfigDict(frozen=True)
    window_index: int
    train_start_ts: int
    train_end_ts: int      # == test_start_ts (exclusive train end boundary)
    test_start_ts: int
    test_end_ts: int       # inclusive last test bar ts
    is_metrics: WindowMetrics
    oos_metrics: WindowMetrics


class WalkForwardProductResult(BaseModel):
    """Chronological walk-forward evaluation of a FIXED adapter factory."""

    model_config = ConfigDict(frozen=True)

    n_windows_requested: int
    windows: list[WalkForwardWindow]
    skipped_windows: list[dict[str, Any]]
    window_boundaries: list[list[int]]
    aggregated_oos_curve: list[EquityPoint]
    oos_total_return_pct: float | None = None
    oos_max_drawdown_pct: float | None = None
    walk_forward_efficiency: float | None = None
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Canonical-JSON / digest helpers
# ---------------------------------------------------------------------------


def _sha256_of_json(payload: Any) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _round_floats(obj: Any, ndigits: int) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


def _symbol_digest_inputs(symbol_bars: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for symbol in sorted(symbol_bars):
        bars = list(symbol_bars[symbol])
        h = hashlib.sha256()
        for bar in bars:
            h.update(f"{int(bar['ts'])}:{float(bar['c'])!r};".encode("utf-8"))
        out[symbol] = {
            "bars_count": len(bars),
            "first_ts": int(bars[0]["ts"]) if bars else None,
            "last_ts": int(bars[-1]["ts"]) if bars else None,
            "ts_close_sha256": h.hexdigest(),
        }
    return out


def _utc_year_month(ts: int) -> tuple[int, int]:
    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return dt.year, dt.month


def _digest_payload(
    engine_version: str,
    execution_model_version: str,
    config_echo: dict[str, Any],
    symbol_inputs: dict[str, Any],
    report: "ReportMetrics",
) -> dict[str, Any]:
    return {
        "engine_version": engine_version,
        "execution_model_version": execution_model_version,
        "config_echo": config_echo,
        "symbols": symbol_inputs,
        "report": _round_floats(report.model_dump(mode="json"), 10),
    }


# ---------------------------------------------------------------------------
# Internal simulation state
# ---------------------------------------------------------------------------


@dataclass
class _Position:
    symbol: str
    direction: Literal["LONG", "SHORT"]
    qty: float                      # signed: + long, - short
    entry_price: float              # fill price incl. costs
    entry_index: int
    entry_ts: int
    entry_signal_index: int
    entry_notional: float
    commission_cash: float = 0.0
    spread_cash: float = 0.0
    slippage_cash: float = 0.0
    stop_price: float | None = None
    take_profit_price: float | None = None
    trailing_pct: float | None = None
    peak_close: float = 0.0
    trough_close: float = float("inf")
    mae_pct: float = 0.0
    mfe_pct: float = 0.0
    regime_label: int | None = None
    pending_exit: bool = False


@dataclass
class _ScheduledFill:
    exec_index: int
    fill: FillResult
    kind: Literal["ENTRY", "EXIT"]
    reason: str | None = None
    # entry-only risk-level snapshot (percent), resolved at SIGNAL time:
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_pct: float | None = None


@dataclass
class _RunState:
    cash: float
    positions: dict[str, _Position] = dc_field(default_factory=dict)
    last_close: dict[str, float] = dc_field(default_factory=dict)
    scheduled: dict[str, list[_ScheduledFill]] = dc_field(default_factory=dict)
    closed_at_ts: dict[str, int] = dc_field(default_factory=dict)
    trades: list[ProductTrade] = dc_field(default_factory=list)
    counters: dict[str, int] = dc_field(default_factory=dict)
    equity_curve: list[EquityPoint] = dc_field(default_factory=list)
    fees_total: float = 0.0
    transacted_notional: float = 0.0
    open_bars: int = 0


# ---------------------------------------------------------------------------
# Data-policy gate (§D3 — refusals recorded, never raised away)
# ---------------------------------------------------------------------------


def _policy_refusals(
    bars: Sequence[Mapping[str, Any]],
    policy: DataPolicy,
    as_of_ts: int | None,
) -> list[str]:
    """Structural + policy refusals for one symbol. Structural errors first."""
    try:
        validate_bars(bars)
    except ValueError as exc:
        return [str(exc)]
    reasons: list[str] = []
    if len(bars) < policy.min_bars:
        reasons.append("insufficient_history")
    if policy.max_staleness_seconds is not None and as_of_ts is not None and bars:
        last_ts = int(bars[-1]["ts"])
        if as_of_ts - last_ts > policy.max_staleness_seconds:
            reasons.append("stale_data")
    if policy.refuse_gaps and len(bars) >= 3:
        diffs = sorted(int(bars[i]["ts"]) - int(bars[i - 1]["ts"]) for i in range(1, len(bars)))
        mid = len(diffs) // 2
        expected = diffs[mid] if len(diffs) % 2 == 1 else diffs[mid - 1]
        if expected > 0 and max(diffs) > 3 * expected:
            reasons.append("ts_gap_gt_3x_expected_interval")
    return reasons


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------


def run_backtest(
    symbol_bars: Mapping[str, Sequence[Mapping[str, Any]]],
    adapters: Mapping[str, StrategyAdapter],
    config: BacktestRunConfig,
) -> BacktestResult:
    """Run one deterministic product backtest (directive §D2/§D3/§D5).

    Deterministic symbol processing order = ``sorted(symbol_bars)``. Refused
    symbols are recorded into ``data_quality``; the whole run raises
    ``ValueError("all_symbols_refused")`` only when nothing remains testable.
    """
    unknown = sorted(set(adapters) - set(symbol_bars))
    if unknown:
        raise ValueError(f"adapters_for_unknown_symbols:{','.join(unknown)}")

    exec_cfg = config.execution
    policy = config.data_policy

    data_quality: list[SymbolDataQuality] = []
    accepted: dict[str, list[Mapping[str, Any]]] = {}
    for symbol in sorted(symbol_bars):
        bars = list(symbol_bars[symbol])
        reasons = _policy_refusals(bars, policy, config.as_of_ts)
        if reasons:
            data_quality.append(
                SymbolDataQuality(
                    symbol=symbol,
                    bars_used=0,
                    bars_refused=len(bars),
                    refusals=reasons,
                    adjustment_semantics=policy.adjustment_semantics,
                )
            )
        else:
            accepted[symbol] = bars
            data_quality.append(
                SymbolDataQuality(
                    symbol=symbol,
                    bars_used=len(bars),
                    bars_refused=0,
                    refusals=[],
                    adjustment_semantics=policy.adjustment_semantics,
                )
            )
    if not accepted:
        raise ValueError("all_symbols_refused")

    regime_labels = config.regime_labels or {}
    regime_mismatch = [
        s for s in accepted if s in regime_labels and len(regime_labels[s]) != len(accepted[s])
    ]

    for symbol in sorted(accepted):
        adapter = adapters.get(symbol)
        if adapter is not None:
            adapter.prepare(list(accepted[symbol]))

    state = _RunState(cash=exec_cfg.initial_capital)
    for symbol in accepted:
        state.scheduled[symbol] = []

    multi_symbol = len(accepted) > 1
    sorted_symbols = sorted(accepted)
    ts_index = {
        symbol: {int(b["ts"]): i for i, b in enumerate(accepted[symbol])} for symbol in sorted_symbols
    }
    timeline = sorted({ts for m in ts_index.values() for ts in m})
    if not timeline:
        raise ValueError("all_symbols_refused")

    for ts in timeline:
        for symbol in sorted_symbols:
            idx = ts_index[symbol].get(ts)
            if idx is not None:
                _process_symbol_bar(
                    symbol, idx, accepted[symbol], adapters.get(symbol), config, state, multi_symbol
                )
        open_flag = bool(state.positions)
        if open_flag:
            state.open_bars += 1
        equity = _account_equity(state, exec_cfg)
        state.equity_curve.append(
            EquityPoint(ts=int(ts), equity=equity, drawdown_pct=0.0, underwater_pct=0.0)
        )

    # END_OF_DATA: close any position still open at its symbol's last bar with
    # full costs; the final equity point reflects these cash effects.
    if state.positions:
        for symbol in sorted(state.positions):
            _close_end_of_data(symbol, accepted[symbol], config, state)
        final_eq = _account_equity(state, exec_cfg)
        last = state.equity_curve[-1]
        state.equity_curve[-1] = EquityPoint(
            ts=last.ts, equity=final_eq, drawdown_pct=0.0, underwater_pct=0.0
        )

    _finalize_drawdowns(state.equity_curve, exec_cfg.initial_capital)

    report = _build_report(config, state)
    benchmark = _build_benchmark(config, accepted, report)
    limitations = _build_limitations(config, data_quality, report, regime_mismatch, state, benchmark)

    symbol_inputs = _symbol_digest_inputs(symbol_bars)
    generated = _sha256_of_json(
        _digest_payload(
            ENGINE_VERSION, EXECUTION_MODEL_VERSION, config.model_dump(mode="json"), symbol_inputs, report
        )
    )
    result = BacktestResult(
        run_id=config.run_id,
        engine_version=ENGINE_VERSION,
        execution_model_version=EXECUTION_MODEL_VERSION,
        generated_by_digest=generated,
        config_echo=config.model_dump(mode="json"),
        data_quality=data_quality,
        data_trust_label=config.data_trust_label,
        trades=state.trades,
        report=report,
        benchmark=benchmark,
        multiple_testing_note="",
        limitations=limitations,
    )
    result._symbol_digest_inputs = symbol_inputs
    return result


# ---------------------------------------------------------------------------
# Account-level helpers
# ---------------------------------------------------------------------------


def _account_equity(state: _RunState, exec_cfg: ExecutionModelConfig) -> float:
    cm = exec_cfg.currency_multiplier
    equity = state.cash
    for pos in state.positions.values():
        equity += pos.qty * state.last_close.get(pos.symbol, pos.entry_price) * cm
    return equity


def _free_equity_open(state: _RunState, exec_cfg: ExecutionModelConfig) -> float:
    """Margin available for a NEW position: equity minus open margin in use."""
    equity = _account_equity(state, exec_cfg)
    used_margin = sum(pos.entry_notional for pos in state.positions.values()) / exec_cfg.leverage
    return equity - used_margin


def _free_equity_closing(state: _RunState, exec_cfg: ExecutionModelConfig, closing: _Position) -> float:
    """Margin available for CLOSES: the closed position releases its margin,
    valued at the current mark (a closing trade is netted against its own
    position, so closing is feasible up to genuine account insolvency)."""
    cm = exec_cfg.currency_multiplier
    mark = abs(closing.qty) * state.last_close.get(closing.symbol, closing.entry_price) * cm
    equity = _account_equity(state, exec_cfg)
    used_margin = sum(
        pos.entry_notional for pos in state.positions.values() if pos.symbol != closing.symbol
    ) / exec_cfg.leverage
    return equity - used_margin + mark / exec_cfg.leverage


# ---------------------------------------------------------------------------
# Per-bar processing
# ---------------------------------------------------------------------------


def _process_symbol_bar(
    symbol: str,
    idx: int,
    bars: Sequence[Mapping[str, Any]],
    adapter: StrategyAdapter | None,
    config: BacktestRunConfig,
    state: _RunState,
    multi_symbol: bool,
) -> None:
    bar = bars[idx]
    h, l, c = float(bar["h"]), float(bar["l"]), float(bar["c"])
    ts = int(bar["ts"])
    exec_cfg = config.execution

    # 1) apply fills due at this bar (scheduling order preserved)
    due = [s for s in state.scheduled[symbol] if s.exec_index == idx]
    state.scheduled[symbol] = [s for s in state.scheduled[symbol] if s.exec_index > idx]
    for sch in due:
        if sch.kind == "ENTRY":
            _apply_entry_fill(symbol, sch, idx, bar, config, state)
        else:
            _apply_exit_fill(symbol, sch, idx, bar, config, state)

    pos = state.positions.get(symbol)

    # 2) MAE/MFE on bars where the position is open after the fill phase
    if pos is not None and pos.entry_price > 0:
        if pos.direction == "LONG":
            adverse = (l - pos.entry_price) / pos.entry_price * 100.0
            favorable = (h - pos.entry_price) / pos.entry_price * 100.0
        else:
            adverse = (pos.entry_price - h) / pos.entry_price * 100.0
            favorable = (pos.entry_price - l) / pos.entry_price * 100.0
        pos.mae_pct = min(pos.mae_pct, adverse)
        pos.mfe_pct = max(pos.mfe_pct, favorable)

    # 3) stop / take-profit / trailing evaluation for an open position
    if pos is not None and not pos.pending_exit and idx > pos.entry_index:
        if exec_cfg.intrabar_tp_sl:
            _evaluate_intrabar_exits(symbol, pos, h, l, idx, ts, config, state)
        else:
            _evaluate_close_only_exits(symbol, pos, c, idx, config, state, bars)

    # 4) adapter decisions — exit first (permits gated same-bar re-entry),
    #    then entry. decide() is called exactly once per bar.
    if adapter is not None:
        decision = adapter.decide(idx)
        if decision.exit:
            _handle_exit_decision(symbol, idx, bars, config, state)
        if decision.entry:
            _handle_entry_decision(symbol, idx, decision, config, state, ts, bars, multi_symbol)

    # 5) trailing peak/trough update (AFTER exit evaluation, so an exit on
    #    bar i uses the peak of closes strictly before bar i)
    pos = state.positions.get(symbol)
    if pos is not None:
        if pos.direction == "LONG":
            pos.peak_close = max(pos.peak_close, c)
        else:
            pos.trough_close = min(pos.trough_close, c)

    # 6) mark-to-market reference for this symbol
    state.last_close[symbol] = c


# ---------------------------------------------------------------------------
# Fill application
# ---------------------------------------------------------------------------


def _apply_entry_fill(
    symbol: str,
    sch: _ScheduledFill,
    idx: int,
    bar: Mapping[str, Any],
    config: BacktestRunConfig,
    state: _RunState,
) -> None:
    fr = sch.fill
    exec_cfg = config.execution
    cm = exec_cfg.currency_multiplier
    notional = fr.fill_price * fr.quantity * cm
    cb = cost_breakdown(notional, exec_cfg)
    state.fees_total += cb["total"]
    state.transacted_notional += notional
    if fr.side == "buy":
        state.cash -= notional + cb["commission"]
        direction: Literal["LONG", "SHORT"] = "LONG"
        qty = fr.quantity
    else:
        state.cash += notional - cb["commission"]
        direction = "SHORT"
        qty = -fr.quantity
    entry_price = fr.fill_price
    stop_price: float | None = None
    if sch.stop_loss_pct is not None:
        if direction == "LONG":
            stop_price = entry_price * (1.0 - sch.stop_loss_pct / 100.0)
        else:
            stop_price = entry_price * (1.0 + sch.stop_loss_pct / 100.0)
    tp_price: float | None = None
    if sch.take_profit_pct is not None:
        if direction == "LONG":
            tp_price = entry_price * (1.0 + sch.take_profit_pct / 100.0)
        else:
            tp_price = entry_price * (1.0 - sch.take_profit_pct / 100.0)
    regime = None
    labels = config.regime_labels or {}
    if symbol in labels and idx < len(labels[symbol]):
        regime = int(labels[symbol][idx])
    state.positions[symbol] = _Position(
        symbol=symbol,
        direction=direction,
        qty=qty,
        entry_price=entry_price,
        entry_index=idx,
        entry_ts=int(bar["ts"]),
        entry_signal_index=fr.signal_index,
        entry_notional=notional,
        commission_cash=cb["commission"],
        spread_cash=cb["spread_cost"],
        slippage_cash=cb["slippage_cost"],
        stop_price=stop_price,
        take_profit_price=tp_price,
        trailing_pct=sch.trailing_pct,
        peak_close=entry_price,
        trough_close=entry_price,
        regime_label=regime,
    )
    state.counters["entries_filled"] = state.counters.get("entries_filled", 0) + 1


def _apply_exit_fill(
    symbol: str,
    sch: _ScheduledFill,
    idx: int,
    bar: Mapping[str, Any],
    config: BacktestRunConfig,
    state: _RunState,
) -> None:
    pos = state.positions.get(symbol)
    if pos is None:
        state.counters["exit_fill_no_position"] = state.counters.get("exit_fill_no_position", 0) + 1
        return
    _close_position(
        pos,
        exit_price=sch.fill.fill_price,
        exit_index=idx,
        exit_ts=int(bar["ts"]),
        exit_signal_index=sch.fill.signal_index,
        reason=sch.reason or _EXIT_SIGNAL,
        config=config,
        state=state,
        closed_at_end=False,
    )
    state.counters["exits_filled"] = state.counters.get("exits_filled", 0) + 1


def _close_position(
    pos: _Position,
    *,
    exit_price: float,
    exit_index: int,
    exit_ts: int,
    exit_signal_index: int,
    reason: str,
    config: BacktestRunConfig,
    state: _RunState,
    closed_at_end: bool,
) -> None:
    exec_cfg = config.execution
    cm = exec_cfg.currency_multiplier
    qty_abs = abs(pos.qty)
    notional = exit_price * qty_abs * cm
    cb = cost_breakdown(notional, exec_cfg)
    state.fees_total += cb["total"]
    state.transacted_notional += notional
    if pos.direction == "LONG":
        state.cash += notional - cb["commission"]
        gross = (exit_price - pos.entry_price) * qty_abs * cm
    else:
        state.cash -= notional + cb["commission"]
        gross = (pos.entry_price - exit_price) * qty_abs * cm
    commission = pos.commission_cash + cb["commission"]
    net = gross - commission
    state.trades.append(
        ProductTrade(
            symbol=pos.symbol,
            side=pos.direction,
            entry_signal_index=pos.entry_signal_index,
            entry_index=pos.entry_index,
            entry_ts=pos.entry_ts,
            entry_price=pos.entry_price,
            exit_signal_index=exit_signal_index,
            exit_index=exit_index,
            exit_ts=exit_ts,
            exit_price=exit_price,
            qty=qty_abs,
            gross_pnl=gross,
            net_pnl=net,
            commission_cash=commission,
            spread_cash=pos.spread_cash + cb["spread_cost"],
            slippage_cash=pos.slippage_cash + cb["slippage_cost"],
            holding_bars=exit_index - pos.entry_index,
            exit_reason=reason,
            mae_pct=pos.mae_pct,
            mfe_pct=pos.mfe_pct,
            regime_label=pos.regime_label,
            closed_at_end_of_data=closed_at_end,
        )
    )
    state.positions.pop(pos.symbol, None)
    state.closed_at_ts[pos.symbol] = exit_ts


def _close_end_of_data(
    symbol: str,
    bars: Sequence[Mapping[str, Any]],
    config: BacktestRunConfig,
    state: _RunState,
) -> None:
    pos = state.positions.get(symbol)
    if pos is None:
        return
    last_idx = len(bars) - 1
    close_side = "sell" if pos.direction == "LONG" else "buy"
    exit_price = apply_spread_slippage(float(bars[last_idx]["c"]), close_side, config.execution)
    _close_position(
        pos,
        exit_price=exit_price,
        exit_index=last_idx,
        exit_ts=int(bars[last_idx]["ts"]),
        exit_signal_index=last_idx,
        reason=_EXIT_END_OF_DATA,
        config=config,
        state=state,
        closed_at_end=True,
    )
    state.counters["end_of_data_closes"] = state.counters.get("end_of_data_closes", 0) + 1


# ---------------------------------------------------------------------------
# Exit evaluation (intrabar pessimistic ordering vs close-only)
# ---------------------------------------------------------------------------


def _effective_stop(pos: _Position) -> tuple[float | None, str | None]:
    """Combine fixed stop and trailing stop; the tighter one governs."""
    stop = pos.stop_price
    reason = _EXIT_STOP if stop is not None else None
    if pos.trailing_pct is not None and pos.trailing_pct > 0:
        if pos.direction == "LONG":
            tstop = pos.peak_close * (1.0 - pos.trailing_pct / 100.0)
            if stop is None or tstop > stop:
                stop, reason = tstop, _EXIT_TRAILING
        else:
            tstop = pos.trough_close * (1.0 + pos.trailing_pct / 100.0)
            if stop is None or tstop < stop:
                stop, reason = tstop, _EXIT_TRAILING
    return stop, reason


def _evaluate_intrabar_exits(
    symbol: str,
    pos: _Position,
    h: float,
    l: float,
    idx: int,
    ts: int,
    config: BacktestRunConfig,
    state: _RunState,
) -> None:
    """Conservative intrabar semantics: when a single bar touches BOTH the
    stop and the target, the STOP is assumed to hit first (pessimistic,
    documented). Trigger-level fills carry full spread+slippage."""
    stop, stop_reason = _effective_stop(pos)
    tp = pos.take_profit_price
    if pos.direction == "LONG":
        stop_hit = stop is not None and l <= stop
        tp_hit = tp is not None and h >= tp
    else:
        stop_hit = stop is not None and h >= stop
        tp_hit = tp is not None and l <= tp
    trigger: float | None = None
    reason = None
    if stop_hit and stop is not None:
        trigger, reason = stop, stop_reason or _EXIT_STOP
    elif tp_hit and tp is not None:
        trigger, reason = tp, _EXIT_TARGET
    if trigger is None or reason is None:
        return
    side = "sell" if pos.direction == "LONG" else "buy"
    price = apply_spread_slippage(trigger, side, config.execution)
    _close_position(
        pos,
        exit_price=price,
        exit_index=idx,
        exit_ts=ts,
        exit_signal_index=idx,
        reason=reason,
        config=config,
        state=state,
        closed_at_end=False,
    )
    state.counters["intrabar_exits"] = state.counters.get("intrabar_exits", 0) + 1


def _evaluate_close_only_exits(
    symbol: str,
    pos: _Position,
    c: float,
    idx: int,
    config: BacktestRunConfig,
    state: _RunState,
    bars: Sequence[Mapping[str, Any]],
) -> None:
    """intrabar_tp_sl=False: stops/targets evaluate on the bar CLOSE only and
    route through the standard fill pipeline (latency / fill_policy honored)."""
    stop, stop_reason = _effective_stop(pos)
    tp = pos.take_profit_price
    if pos.direction == "LONG":
        stop_hit = stop is not None and c <= stop
        tp_hit = tp is not None and c >= tp
    else:
        stop_hit = stop is not None and c >= stop
        tp_hit = tp is not None and c <= tp
    if stop_hit:
        _schedule_exit(symbol, pos, idx, stop_reason or _EXIT_STOP, config, state, bars)
    elif tp_hit:
        _schedule_exit(symbol, pos, idx, _EXIT_TARGET, config, state, bars)


def _schedule_exit(
    symbol: str,
    pos: _Position,
    idx: int,
    reason: str,
    config: BacktestRunConfig,
    state: _RunState,
    bars: Sequence[Mapping[str, Any]],
) -> None:
    """Route an exit signal through simulate_fill; schedule or apply at once."""
    fr = simulate_fill(
        bars=bars,
        signal_index=idx,
        side="sell" if pos.direction == "LONG" else "buy",
        desired_quantity=abs(pos.qty),
        cfg=config.execution,
        free_equity=_free_equity_closing(state, config.execution, pos),
        current_position=pos.qty,
    )
    if not fr.filled:
        key = f"exit_refused:{fr.refusal_reason}"
        state.counters[key] = state.counters.get(key, 0) + 1
        return
    pos.pending_exit = True
    sch = _ScheduledFill(exec_index=fr.execution_index, fill=fr, kind="EXIT", reason=reason)
    if fr.execution_index == idx:
        # SAME_BAR_CLOSE with zero latency: applied at this very bar.
        _apply_exit_fill(symbol, sch, idx, bars[idx], config, state)
    else:
        state.scheduled[symbol].append(sch)


# ---------------------------------------------------------------------------
# Adapter decision handling
# ---------------------------------------------------------------------------


def _handle_exit_decision(
    symbol: str,
    idx: int,
    bars: Sequence[Mapping[str, Any]],
    config: BacktestRunConfig,
    state: _RunState,
) -> None:
    pos = state.positions.get(symbol)
    if pos is not None:
        if pos.pending_exit:
            state.counters["exit_already_pending"] = state.counters.get("exit_already_pending", 0) + 1
            return
        _schedule_exit(symbol, pos, idx, _EXIT_SIGNAL, config, state, bars)
        return
    if config.execution.allow_short:
        # Documented convention: the SignalDecision protocol has no side field;
        # with allow_short an EXIT while flat opens a SHORT (reverse stance).
        _attempt_entry(symbol, idx, SignalDecision(exit=True), config, state, "SHORT", bars)
    else:
        state.counters["exit_without_position"] = state.counters.get("exit_without_position", 0) + 1


def _handle_entry_decision(
    symbol: str,
    idx: int,
    decision: SignalDecision,
    config: BacktestRunConfig,
    state: _RunState,
    ts: int,
    bars: Sequence[Mapping[str, Any]],
    multi_symbol: bool,
) -> None:
    pos = state.positions.get(symbol)
    if pos is not None:
        if pos.direction == "SHORT":
            # Documented flip semantics: entry while short closes the short;
            # the long side requires a fresh entry signal on a later bar.
            if not pos.pending_exit:
                _schedule_exit(symbol, pos, idx, _EXIT_SIGNAL, config, state, bars)
                state.counters["entry_flip_close_short"] = state.counters.get(
                    "entry_flip_close_short", 0
                ) + 1
            else:
                state.counters["exit_already_pending"] = state.counters.get(
                    "exit_already_pending", 0
                ) + 1
        else:
            state.counters["entry_while_positioned"] = state.counters.get(
                "entry_while_positioned", 0
            ) + 1
        return
    if state.closed_at_ts.get(symbol) == ts and not config.portfolio.allow_same_bar_reentry:
        state.counters["same_bar_reentry_refused"] = state.counters.get(
            "same_bar_reentry_refused", 0
        ) + 1
        return
    _attempt_entry(symbol, idx, decision, config, state, "LONG", bars, multi_symbol)


def _sized_quantity(
    decision: SignalDecision,
    price: float,
    config: BacktestRunConfig,
    equity: float,
    free_equity: float,
    multi_symbol: bool,
) -> tuple[float, str]:
    """Deterministic target quantity (documented sizing conventions)."""
    exec_cfg = config.execution
    risk = config.risk
    portfolio = config.portfolio
    if price <= 0:
        return 0.0, "zero_price"
    max_pos_qty = equity * risk.max_position_pct / 100.0 / (price * exec_cfg.currency_multiplier)
    if decision.size_pct is not None:
        base_pct = decision.size_pct
    elif multi_symbol and portfolio.equal_weight:
        base_pct = 100.0 / portfolio.max_open_positions
    else:
        base_pct = risk.max_position_pct
    base_pct = min(base_pct, risk.max_position_pct)
    if risk.sizing_mode == "RISK_BASED":
        stop_pct = decision.stop_loss_pct if decision.stop_loss_pct is not None else risk.stop_loss_pct
        if stop_pct is not None and abs(stop_pct) > 1e-12:
            stop_distance = price * abs(stop_pct) / 100.0
            qty = equity * (risk.risk_pct_of_equity / 100.0) / stop_distance
            mode = "RISK_BASED"
        else:
            qty = equity * (base_pct / 100.0) / price
            mode = "FIXED_PCT_EQUITY(risk_based_fallback)"
    else:
        qty = equity * (base_pct / 100.0) / price
        mode = "FIXED_PCT_EQUITY"
    # Pre-cap by estimated margin feasibility at the signal-bar price; drift
    # between signal and execution bar can still refuse via margin_insufficient.
    est_factor = (1.0 + exec_cfg.spread_pct / 200.0) * (1.0 + exec_cfg.slippage_pct / 100.0)
    denom = price * est_factor * exec_cfg.currency_multiplier
    margin_cap_qty = max(0.0, free_equity * exec_cfg.leverage / denom) if denom > 0 else 0.0
    qty = min(qty, max_pos_qty, margin_cap_qty)
    return max(0.0, qty), mode


def _attempt_entry(
    symbol: str,
    idx: int,
    decision: SignalDecision,
    config: BacktestRunConfig,
    state: _RunState,
    direction: Literal["LONG", "SHORT"],
    bars: Sequence[Mapping[str, Any]],
    multi_symbol: bool = False,
) -> None:
    exec_cfg = config.execution
    portfolio = config.portfolio
    if symbol in portfolio.per_symbol_blacklist:
        state.counters["entry_refused:blacklisted"] = state.counters.get(
            "entry_refused:blacklisted", 0
        ) + 1
        return
    # Gate counts OPEN positions PLUS already-scheduled (unfilled) entries so
    # NEXT_BAR_OPEN scheduling cannot oversubscribe the portfolio.
    pending_entries = sum(
        1 for sym in state.scheduled for s in state.scheduled[sym] if s.kind == "ENTRY"
    )
    if len(state.positions) + pending_entries >= portfolio.max_open_positions:
        state.counters["max_positions"] = state.counters.get("max_positions", 0) + 1
        return
    if any(s.kind == "ENTRY" for s in state.scheduled[symbol]):
        state.counters["entry_pending_fill"] = state.counters.get("entry_pending_fill", 0) + 1
        return
    price = float(bars[idx]["c"])
    equity = _account_equity(state, exec_cfg)
    free_equity = _free_equity_open(state, exec_cfg)
    qty, mode = _sized_quantity(decision, price, config, equity, free_equity, multi_symbol)
    if qty <= 0:
        state.counters["entry_refused:zero_sizing"] = state.counters.get(
            "entry_refused:zero_sizing", 0
        ) + 1
        return
    fr = simulate_fill(
        bars=bars,
        signal_index=idx,
        side="buy" if direction == "LONG" else "sell",
        desired_quantity=qty,
        cfg=exec_cfg,
        free_equity=free_equity,
        current_position=0.0,
    )
    if not fr.filled:
        key = f"entry_refused:{fr.refusal_reason}"
        state.counters[key] = state.counters.get(key, 0) + 1
        return
    stop_pct = decision.stop_loss_pct if decision.stop_loss_pct is not None else config.risk.stop_loss_pct
    tp_pct = decision.take_profit_pct if decision.take_profit_pct is not None else config.risk.take_profit_pct
    trail_pct = decision.trailing_pct if decision.trailing_pct is not None else config.risk.trailing_pct
    sch = _ScheduledFill(
        exec_index=fr.execution_index,
        fill=fr,
        kind="ENTRY",
        reason=mode,
        stop_loss_pct=stop_pct,
        take_profit_pct=tp_pct,
        trailing_pct=trail_pct,
    )
    if fr.execution_index == idx:
        _apply_entry_fill(symbol, sch, idx, bars[idx], config, state)
    else:
        state.scheduled[symbol].append(sch)


# ---------------------------------------------------------------------------
# Drawdown finalization and report assembly (§D5)
# ---------------------------------------------------------------------------


def _finalize_drawdowns(curve: list[EquityPoint], initial_capital: float) -> None:
    peak = initial_capital
    finalized: list[EquityPoint] = []
    for pt in curve:
        if pt.equity > peak:
            peak = pt.equity
        dd = (peak - pt.equity) / peak * 100.0 if peak > 0 else 0.0
        finalized.append(EquityPoint(ts=pt.ts, equity=pt.equity, drawdown_pct=dd, underwater_pct=dd))
    curve[:] = finalized


def _build_report(config: BacktestRunConfig, state: _RunState) -> ReportMetrics:
    exec_cfg = config.execution
    initial = exec_cfg.initial_capital
    curve = state.equity_curve
    trades = state.trades
    cm = exec_cfg.currency_multiplier

    total_return: float | None = None
    annualized: float | None = None
    cagr: float | None = None
    years: float | None = None
    if len(curve) >= 2 and initial > 0:
        last_eq = curve[-1].equity
        total_return = (last_eq / initial - 1.0) * 100.0
        span_seconds = curve[-1].ts - curve[0].ts
        if span_seconds > 0:
            years = span_seconds / (365.25 * 86400.0)
            annualized = total_return / 100.0 / years * 100.0
            growth = 1.0 + total_return / 100.0
            if years >= 1.0 and growth > 0:
                cagr = (growth ** (1.0 / years) - 1.0) * 100.0

    max_dd, max_dd_duration = _drawdown_stats(curve, initial)

    returns: list[float] = []
    if curve:
        prev = initial
        for pt in curve:
            if prev > 0:
                returns.append(pt.equity / prev - 1.0)
            prev = pt.equity
    sharpe = _sharpe(returns)
    sortino = _sortino(returns)

    calmar: float | None = None
    if cagr is not None and max_dd > 1e-15:
        calmar = cagr / max_dd

    wins = [t.net_pnl for t in trades if t.net_pnl > 0]
    losses = [t.net_pnl for t in trades if t.net_pnl < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_win / gross_loss if trades and gross_loss > 1e-15 else None
    expectancy = sum(t.net_pnl for t in trades) / len(trades) if trades else None
    win_rate = len(wins) / len(trades) * 100.0 if trades else None
    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = sum(losses) / len(losses) if losses else None
    avg_holding = sum(t.holding_bars for t in trades) / len(trades) if trades else None

    exposure_pct = state.open_bars / len(curve) * 100.0 if curve else 0.0

    turnover: float | None = None
    if years is not None and years > 0 and curve:
        mean_equity = sum(pt.equity for pt in curve) / len(curve)
        if mean_equity > 0:
            turnover = state.transacted_notional / mean_equity / years

    long_trades = long_wins = short_trades = short_wins = 0
    long_pnl = short_pnl = 0.0
    for t in trades:
        if t.side == "LONG":
            long_trades += 1
            long_wins += 1 if t.net_pnl > 0 else 0
            long_pnl += t.net_pnl
        else:
            short_trades += 1
            short_wins += 1 if t.net_pnl > 0 else 0
            short_pnl += t.net_pnl
    long_dec = SideStats(trades=long_trades, wins=long_wins, net_pnl=long_pnl)
    short_dec = SideStats(trades=short_trades, wins=short_wins, net_pnl=short_pnl)

    return ReportMetrics(
        total_return_pct=total_return,
        annualized_return_pct=annualized,
        cagr_pct=cagr,
        max_drawdown_pct=max_dd,
        max_drawdown_duration_bars=max_dd_duration,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        profit_factor=profit_factor,
        expectancy=expectancy,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        trade_count=len(trades),
        exposure_pct=exposure_pct,
        avg_holding_bars=avg_holding,
        turnover=turnover,
        fees_total=state.fees_total,
        annualization_assumption=_ANNUALIZATION_ASSUMPTION,
        equity_curve=curve,
        monthly_returns=_period_returns(curve, initial, "monthly"),
        yearly_returns=_period_returns(curve, initial, "yearly"),
        trade_distribution=_trade_distribution(trades, cm),
        long_short_decomposition=LongShortDecomposition(long=long_dec, short=short_dec),
        regime_segments=_regime_segments(trades, initial),
        event_counters=dict(sorted(state.counters.items())),
    )


def _drawdown_stats(curve: list[EquityPoint], initial: float) -> tuple[float, int]:
    """Max drawdown pct and the LONGEST continuous underwater episode in bars."""
    peak = initial
    peak_idx = -1
    max_dd = 0.0
    longest = 0
    for i, pt in enumerate(curve):
        if pt.equity > peak:
            peak = pt.equity
            peak_idx = i
        if peak > 0:
            dd = (peak - pt.equity) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
            if pt.equity < peak:
                longest = max(longest, i - peak_idx)
    return max_dd, longest


def _sharpe(returns: list[float]) -> float | None:
    n = len(returns)
    if n < 2:
        return None
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(var)
    if std <= 1e-15:
        return None
    return mean / std * math.sqrt(252.0)


def _sortino(returns: list[float]) -> float | None:
    n = len(returns)
    if n < 1:
        return None
    mean = sum(returns) / n
    downside = math.sqrt(sum(min(r, 0.0) ** 2 for r in returns) / n)
    if downside <= 1e-15:
        return None
    return mean / downside * math.sqrt(252.0)


def _period_returns(
    curve: list[EquityPoint], initial: float, granularity: str
) -> list[MonthlyReturn] | list[YearlyReturn]:
    """Monthly/yearly returns from UTC timestamps; bases chain across periods."""
    if not curve:
        return []
    last_eq: dict[tuple[int, ...], float] = {}
    for pt in curve:
        year, month = _utc_year_month(pt.ts)
        key = (year, month) if granularity == "monthly" else (year,)
        last_eq[key] = pt.equity
    rows: list[Any] = []
    prev = initial
    for key in sorted(last_eq):
        eq = last_eq[key]
        ret = (eq / prev - 1.0) * 100.0 if prev > 0 else None
        if granularity == "monthly":
            rows.append(MonthlyReturn(year=key[0], month=key[1], return_pct=ret))
        else:
            rows.append(YearlyReturn(year=key[0], return_pct=ret))
        prev = eq
    return rows


def _trade_distribution(trades: list[ProductTrade], cm: float) -> list[TradeBin]:
    """10 fixed bins over a symmetric, deterministically auto-ranged span."""
    if not trades:
        return []
    pnl_pcts = [t.net_pnl / (t.entry_price * t.qty * cm) * 100.0 for t in trades if t.entry_price > 0]
    if not pnl_pcts:
        return []
    span = float(max(1.0, math.ceil(max(abs(p) for p in pnl_pcts))))
    edges = [-span + k * (2.0 * span / 10.0) for k in range(11)]
    bins: list[TradeBin] = []
    for k in range(10):
        lo, hi = edges[k], edges[k + 1]
        if k < 9:
            count = sum(1 for p in pnl_pcts if lo <= p < hi)
        else:
            count = sum(1 for p in pnl_pcts if lo <= p <= hi)
        bins.append(TradeBin(bin_low=lo, bin_high=hi, count=count))
    return bins


def _regime_segments(trades: list[ProductTrade], initial: float) -> list[RegimeSegment]:
    by_regime: dict[int, list[ProductTrade]] = {}
    for t in trades:
        if t.regime_label is None:
            continue
        by_regime.setdefault(t.regime_label, []).append(t)
    segments: list[RegimeSegment] = []
    for regime in sorted(by_regime):
        group = by_regime[regime]
        wins = sum(1 for t in group if t.net_pnl > 0)
        segments.append(
            RegimeSegment(
                regime=regime,
                trades=len(group),
                win_rate=wins / len(group) * 100.0 if group else None,
                total_return_pct=sum(t.net_pnl for t in group) / initial * 100.0 if initial > 0 else None,
            )
        )
    return segments


def _build_limitations(
    config: BacktestRunConfig,
    data_quality: list[SymbolDataQuality],
    report: ReportMetrics,
    regime_mismatch: list[str],
    state: _RunState,
    benchmark: BenchmarkComparison | None,
) -> list[str]:
    notes: list[str] = [
        "bar-based approximation: fills are simulated from OHLCV bars, never real-tick",
        f"fill_policy={config.execution.fill_policy} declared; "
        + (
            "NEXT_BAR_OPEN fills execute strictly after the signal bar"
            if config.execution.fill_policy == "NEXT_BAR_OPEN"
            else "SAME_BAR_CLOSE fills at the signal bar close (explicit approximation)"
        ),
        (
            "intrabar_tp_sl enabled: same-bar stop-before-target pessimistic ordering; "
            "trigger-level fills carry full spread+slippage"
            if config.execution.intrabar_tp_sl
            else "intrabar_tp_sl disabled: stops/targets evaluate on bar close only"
        ),
        "monthly/yearly returns derived from UTC timestamps",
    ]
    if report.cagr_pct is None:
        notes.append("CAGR not computed: span < 1 year (mathematically applicable only then)")
    else:
        notes.append("CAGR assumes 365.25-day years")
    if not config.data_trust_label.startswith("VERIFIED"):
        notes.append(
            f"data_trust_label='{config.data_trust_label}': synthetic/fixture data — "
            "results are not grounded in verified market data"
        )
    refused = [dq for dq in data_quality if dq.refusals]
    if refused:
        notes.append(
            f"{len(refused)} symbol(s) refused by data policy: "
            + ",".join(f"{dq.symbol}:{dq.refusals[0]}" for dq in refused)
        )
    if regime_mismatch:
        notes.append("regime_labels length mismatch ignored for: " + ",".join(sorted(regime_mismatch)))
    if state.counters.get("end_of_data_closes"):
        notes.append(
            "open positions at end of data were closed at the last close with full costs "
            "(exit_reason=END_OF_DATA, closed_at_end_of_data=True); END_OF_DATA cash effects "
            "land in the final equity point"
        )
    if config.benchmark_symbol is not None and benchmark is None:
        notes.append(
            f"benchmark_symbol='{config.benchmark_symbol}' unavailable or refused: "
            "benchmark comparison omitted (fail-closed)"
        )
    if config.notes:
        notes.append(f"caller notes: {config.notes}")
    return notes


def _build_benchmark(
    config: BacktestRunConfig,
    accepted: Mapping[str, Sequence[Mapping[str, Any]]],
    report: ReportMetrics,
) -> BenchmarkComparison | None:
    exec_cfg = config.execution
    cm = exec_cfg.currency_multiplier
    initial = exec_cfg.initial_capital
    bench_symbol = config.benchmark_symbol or sorted(accepted)[0]
    bars = accepted.get(bench_symbol)
    if bars is None or len(bars) < 2:
        return None
    first_close = float(bars[0]["c"])
    if first_close <= 0:
        return None
    est_factor = (1.0 + exec_cfg.spread_pct / 200.0) * (1.0 + exec_cfg.slippage_pct / 100.0)
    desired = initial / (first_close * est_factor * cm)
    fr = simulate_fill(
        bars=bars,
        signal_index=0,
        side="buy",
        desired_quantity=desired,
        cfg=exec_cfg,
        free_equity=initial,
        current_position=0.0,
    )
    if not fr.filled:
        return None
    notional = fr.fill_price * fr.quantity * cm
    cb = cost_breakdown(notional, exec_cfg)
    cash = initial - notional - cb["commission"]
    curve: list[EquityPoint] = []
    for i, bar in enumerate(bars):
        eq = initial if i < fr.execution_index else cash + fr.quantity * float(bar["c"]) * cm
        curve.append(EquityPoint(ts=int(bar["ts"]), equity=eq, drawdown_pct=0.0, underwater_pct=0.0))
    _finalize_drawdowns(curve, initial)
    bench_return = (curve[-1].equity / initial - 1.0) * 100.0 if initial > 0 else None
    bench_dd, _ = _drawdown_stats(curve, initial)
    return BenchmarkComparison(
        symbol=bench_symbol,
        strategy_total_return_pct=report.total_return_pct,
        benchmark_total_return_pct=bench_return,
        strategy_max_drawdown_pct=report.max_drawdown_pct,
        benchmark_max_drawdown_pct=bench_dd,
        benchmark_equity_curve=curve,
    )


# ---------------------------------------------------------------------------
# Product-level walk-forward (§D4 boundary: evaluation only, NO selection)
# ---------------------------------------------------------------------------


def run_walk_forward_product(
    symbol_bars: Mapping[str, Sequence[Mapping[str, Any]]],
    adapter_factory: Callable[[dict], StrategyAdapter],
    config: BacktestRunConfig,
    wf_config: WalkForwardProductConfig,
) -> WalkForwardProductResult:
    """Deterministic chronological walk-forward over the union timeline.

    Splits: the timeline is cut into ``n_splits + 1`` equal-index chunks
    (remainder distributed to the earliest chunks). Window ``i`` tests chunk
    ``i+1``; anchored training uses ALL bars before the test window, rolling
    training uses exactly the preceding chunk. Each window runs a fresh
    backtest with a fresh adapter (``adapter_factory({})``) on train (IS) and
    test (OOS) bars separately — indicators re-warm inside each window and no
    position spans a boundary. NO parameter selection happens here.
    """
    all_ts = sorted({int(b["ts"]) for bars in symbol_bars.values() for b in bars})
    n_chunks = wf_config.n_splits + 1
    if len(all_ts) < n_chunks:
        raise ValueError("timeline_too_short_for_walk_forward")
    base = len(all_ts) // n_chunks
    rem = len(all_ts) % n_chunks
    sizes = [base + (1 if i < rem else 0) for i in range(n_chunks)]
    starts = [sum(sizes[:i]) for i in range(n_chunks)]

    windows: list[WalkForwardWindow] = []
    skipped: list[dict[str, Any]] = []
    boundaries: list[list[int]] = []
    oos_curves: list[list[EquityPoint]] = []

    for w in range(wf_config.n_splits):
        test_lo, test_hi = starts[w + 1], starts[w + 1] + sizes[w + 1]
        train_lo, train_hi = (0, test_lo) if wf_config.anchored else (starts[w], test_lo)
        train_ts = all_ts[train_lo:train_hi]
        test_ts = all_ts[test_lo:test_hi]
        if len(train_ts) < wf_config.min_train_bars:
            skipped.append({"window_index": w, "reason": "insufficient_train_bars"})
            continue
        if len(test_ts) < wf_config.min_test_bars:
            skipped.append({"window_index": w, "reason": "insufficient_test_bars"})
            continue
        test_start_ts, test_end_ts = test_ts[0], test_ts[-1]
        boundaries.append([train_ts[0], train_ts[-1], test_start_ts, test_end_ts])

        train_bars = {
            s: [b for b in bars if train_ts[0] <= int(b["ts"]) < test_start_ts]
            for s, bars in symbol_bars.items()
        }
        test_bars = {
            s: [b for b in bars if test_start_ts <= int(b["ts"]) <= test_end_ts]
            for s, bars in symbol_bars.items()
        }
        try:
            is_result = run_backtest(train_bars, {s: adapter_factory({}) for s in train_bars}, config)
            oos_result = run_backtest(test_bars, {s: adapter_factory({}) for s in test_bars}, config)
        except ValueError as exc:
            skipped.append({"window_index": w, "reason": f"window_run_refused:{exc}"})
            continue
        windows.append(
            WalkForwardWindow(
                window_index=w,
                train_start_ts=train_ts[0],
                train_end_ts=test_start_ts,
                test_start_ts=test_start_ts,
                test_end_ts=test_end_ts,
                is_metrics=_window_metrics(is_result),
                oos_metrics=_window_metrics(oos_result),
            )
        )
        oos_curves.append(oos_result.report.equity_curve)

    if not windows:
        raise ValueError("all_walk_forward_windows_skipped")

    aggregated, oos_total, oos_dd = _aggregate_oos(oos_curves, config.execution.initial_capital)

    oos_sharpes = [win.oos_metrics.sharpe for win in windows if win.oos_metrics.sharpe is not None]
    is_sharpes = [win.is_metrics.sharpe for win in windows if win.is_metrics.sharpe is not None]
    efficiency: float | None = None
    if oos_sharpes and is_sharpes:
        mean_is = sum(is_sharpes) / len(is_sharpes)
        if abs(mean_is) > 1e-12:
            efficiency = (sum(oos_sharpes) / len(oos_sharpes)) / mean_is

    return WalkForwardProductResult(
        n_windows_requested=wf_config.n_splits,
        windows=windows,
        skipped_windows=skipped,
        window_boundaries=boundaries,
        aggregated_oos_curve=aggregated,
        oos_total_return_pct=oos_total,
        oos_max_drawdown_pct=oos_dd,
        walk_forward_efficiency=efficiency,
        limitations=[
            "OOS windows re-warm indicators inside the window; no state carries across boundaries",
            "no parameter selection is performed here (selection lives in backtest_optimizer)",
        ],
    )


def _window_metrics(result: BacktestResult) -> WindowMetrics:
    return WindowMetrics(
        total_return_pct=result.report.total_return_pct,
        sharpe=result.report.sharpe,
        trade_count=result.report.trade_count,
        max_drawdown_pct=result.report.max_drawdown_pct,
    )


def _aggregate_oos(
    curves: list[list[EquityPoint]], initial: float
) -> tuple[list[EquityPoint], float | None, float | None]:
    """Concatenate test-window equity CHANGES into one account-level curve."""
    aggregated: list[EquityPoint] = []
    running = initial
    for curve in curves:
        if not curve:
            continue
        w_first = curve[0].equity
        if w_first <= 0:
            continue
        for pt in curve:
            aggregated.append(
                EquityPoint(
                    ts=pt.ts,
                    equity=running * (pt.equity / w_first),
                    drawdown_pct=0.0,
                    underwater_pct=0.0,
                )
            )
        running = running * (curve[-1].equity / w_first)
    if not aggregated:
        return [], None, None
    _finalize_drawdowns(aggregated, initial)
    total = (aggregated[-1].equity / initial - 1.0) * 100.0 if initial > 0 else None
    dd, _ = _drawdown_stats(aggregated, initial)
    return aggregated, total, dd
