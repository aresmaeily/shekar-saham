"""Backtest, walk-forward and forward-test primitives for Iran-market strategies.

P3.27 scope: simulated execution only. No broker integration, live trading,
paper trading account, AI, or UI feature is implemented here.
"""

from __future__ import annotations

import hashlib
import math
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app.core.config import Settings, build_data_trust_context, get_settings
from app.data.store import Store
from app.domain.strategy import FilterStrategy, StrategyContext, StrategyMetadata, StrategySignalSide
from app.models.schemas import SymbolSnapshot


@dataclass
class TradeResult:
    symbol: str
    entry_ts: float
    exit_ts: float
    entry_price: float
    exit_price: float
    ret_pct: float
    holding_bars: int
    entry_score: float
    exit_reason: str
    quantity: float = 0.0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    commission: float = 0.0
    slippage_cost: float = 0.0


@dataclass
class BacktestReport:
    mode: str
    bars: int
    symbols_tested: int
    trades: int
    win_rate: float
    avg_return: float
    median_return: float
    total_return_sum: float
    max_drawdown: float
    profit_factor: float
    sharpe_like: float
    avg_holding_bars: float
    best_trade: Optional[dict] = None
    worst_trade: Optional[dict] = None
    equity_curve: list[dict] = field(default_factory=list)
    trades_sample: list[dict] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    data_trust: dict[str, Any] = field(default_factory=dict)
    quant_safety: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionConfig:
    initial_capital: float = 100_000_000.0
    position_size_pct: float = 10.0
    commission_pct: float = 0.5
    slippage_pct: float = 0.0
    max_hold_bars: int = 24
    take_profit_pct: float = 4.0
    stop_loss_pct: float = -3.0


@dataclass(frozen=True)
class WalkForwardConfig:
    train_bars: int = 40
    test_bars: int = 20
    step_bars: int = 20
    min_train_bars: int = 10


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16))


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _bar_price(bar: dict[str, Any], fallback: float = 0.0) -> float:
    return max(0.0, _safe_float(bar.get("pl") or bar.get("close") or bar.get("pc"), fallback))


def _bar_levels(bar: dict[str, Any], fallback: float = 0.0) -> tuple[float, float, float, bool]:
    """Return (high, low, close, has_intrabar_range).

    Close-only bars (no high/low) keep historical close-only TP/SL behavior.
    """
    close = _bar_price(bar, fallback)
    has_hl = (("high" in bar) or ("pmax" in bar)) and (("low" in bar) or ("pmin" in bar))
    if not has_hl:
        return close, close, close, False
    high = _safe_float(bar.get("high") if bar.get("high") is not None else bar.get("pmax"), close)
    low = _safe_float(bar.get("low") if bar.get("low") is not None else bar.get("pmin"), close)
    if high < close:
        high = close
    if close > 0 and (low <= 0 or low > close):
        low = close
    return high, low, close, True


def resolve_same_bar_tp_sl(
    entry_price: float,
    high: float,
    low: float,
    close: float,
    take_profit_pct: float,
    stop_loss_pct: float,
    *,
    has_intrabar_range: bool,
) -> tuple[str | None, float | None]:
    """Deterministic TP/SL on one bar. Conservative when both levels are reachable.

    Returns (reason, raw_exit_price) or (None, None) if neither level is hit.
    Close-only bars use close vs thresholds (TP and SL cannot both trigger).
    OHLC bars that touch both TP and SL take the stop (do not assume the win).
    """
    if entry_price <= 0:
        return None, None
    tp_level = entry_price * (1.0 + float(take_profit_pct) / 100.0)
    sl_level = entry_price * (1.0 + float(stop_loss_pct) / 100.0)
    if not has_intrabar_range:
        close_ret = (close / entry_price - 1.0) * 100.0
        if close_ret >= take_profit_pct:
            return "take_profit", close
        if close_ret <= stop_loss_pct:
            return "stop_loss", close
        return None, None
    hit_tp = high >= tp_level
    hit_sl = low <= sl_level
    if hit_tp and hit_sl:
        return "stop_loss_same_bar_ambiguous", sl_level
    if hit_sl:
        return "stop_loss", sl_level
    if hit_tp:
        return "take_profit", tp_level
    return None, None


def synthesize_price_path(
    symbols: list[SymbolSnapshot],
    bars: int = 80,
    seed: str = "bt",
) -> dict[str, list[dict[str, Any]]]:
    """Synthetic price/board path when DB history is insufficient.

    The result is explicitly synthetic and must never be used as proof of live
    performance.
    """
    paths: dict[str, list[dict[str, Any]]] = {}
    now = time.time()
    step = 300  # 5 min bars
    for s in symbols:
        r = _rng(seed + s.l18)
        price = float(s.py or s.pl or 1000)
        avg_vol = float(s.avg_vol_30d or s.tvol or 1e6)
        series = []
        pump_start = r.randint(10, max(11, bars - 20))
        for i in range(bars):
            ts = now - (bars - i) * step
            drift = r.uniform(-0.012, 0.012)
            if pump_start <= i <= pump_start + 8:
                drift += r.uniform(0.005, 0.02)
            if i > pump_start + 12 and pump_start <= i <= pump_start + 20:
                drift -= r.uniform(0.0, 0.01)
            price = max(1.0, price * (1 + drift))
            plp = (price / float(s.py or price) - 1) * 100
            buy_power = max(0.3, 1.0 + drift * 40 + r.uniform(-0.3, 0.3))
            vol_ratio = max(0.3, 1.0 + abs(drift) * 50 + r.uniform(-0.2, 0.8))
            if pump_start <= i <= pump_start + 6:
                buy_power = max(buy_power, r.uniform(1.8, 3.5))
                vol_ratio = max(vol_ratio, r.uniform(2.0, 4.5))
            net = (buy_power - 1) * price * avg_vol * 0.01
            hot = (buy_power - 1) * 30 + (vol_ratio - 1) * 10
            entry = 0.0
            if vol_ratio >= 2:
                entry += 20
            if buy_power >= 1.5:
                entry += 25
            if net > 0:
                entry += 15
            if plp <= 0 and buy_power >= 1.5:
                entry += 20
            if hot > 15:
                entry += 10
            entry = min(100, entry + r.uniform(-5, 5))
            exit_s = 0.0
            if buy_power < 0.85:
                exit_s += 30
            if net < 0:
                exit_s += 25
            if hot < -10:
                exit_s += 20
            if vol_ratio >= 2 and net < 0:
                exit_s += 15
            exit_s = min(100, exit_s + r.uniform(-5, 5))
            series.append(
                {
                    "ts": ts,
                    "symbol": s.l18,
                    "pl": round(price, 2),
                    "close": round(price, 2),
                    "plp": round(plp, 2),
                    "tvol": avg_vol * vol_ratio * r.uniform(0.8, 1.2),
                    "buy_power": round(buy_power, 3),
                    "volume_ratio": round(vol_ratio, 3),
                    "individual_net_value": net,
                    "hot_net": round(hot, 2),
                    "entry_score": round(entry, 1),
                    "exit_score": round(exit_s, 1),
                    "rsi": max(5, min(95, 50 + drift * 1000 + r.uniform(-8, 8))),
                    "sma_20": round(price * (1 - r.uniform(-0.02, 0.02)), 2),
                }
            )
        paths[s.l18] = series
    return paths


def paths_from_store(store: Store, symbols: list[str], hours: float = 24) -> dict[str, list[dict[str, Any]]]:
    since = time.time() - hours * 3600
    paths: dict[str, list[dict[str, Any]]] = {sym: [] for sym in symbols}
    for sym in symbols:
        ticks = store.get_ticks_since(since, symbol=sym)
        for t in ticks:
            price = t.get("pl")
            paths[sym].append(
                {
                    "ts": t.get("ts"),
                    "symbol": sym,
                    "pl": price,
                    "close": price,
                    "plp": t.get("plp"),
                    "tvol": t.get("tvol"),
                    "buy_power": t.get("buy_power") or 1,
                    "volume_ratio": t.get("volume_ratio") or 1.0,
                    "individual_net_value": t.get("individual_net_value") or 0,
                    "hot_net": t.get("hot_net") or 0,
                    "entry_score": t.get("entry_score") or 0,
                    "exit_score": t.get("exit_score") or 0,
                }
            )
    return {k: sorted(v, key=lambda x: x.get("ts") or 0) for k, v in paths.items() if len(v) >= 5}


def _metrics_from_trades(trades: list[TradeResult], initial_capital: float) -> dict[str, Any]:
    rets = [t.ret_pct for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    gross_win = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    gross_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl <= 0))
    total_pnl = sum(t.net_pnl for t in trades)
    total_return = (total_pnl / initial_capital * 100) if initial_capital else 0.0
    win_rate = (len(wins) / len(rets) * 100) if rets else 0.0
    avg_ret = sum(rets) / len(rets) if rets else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    if len(rets) >= 2:
        mean = avg_ret
        var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        sharpe = mean / std if std else 0.0
        sharpe_note = "computed"
    else:
        sharpe = 0.0
        sharpe_note = "not_enough_trades"
    return {
        "total_return": round(total_return, 3),
        "net_profit_loss": round(total_pnl, 2),
        "number_of_trades": len(trades),
        "win_rate": round(win_rate, 2),
        "average_win": round(avg_win, 3),
        "average_loss": round(avg_loss, 3),
        "average_return": round(avg_ret, 3),
        "median_return": round(_median(rets), 3),
        "profit_factor": round(pf, 3),
        "sharpe_ratio": round(sharpe, 3),
        "sharpe_status": sharpe_note,
        "sharpe_basis": "per_trade_return_not_annualized",
    }


def _equity_curve(trades: list[TradeResult], initial_capital: float) -> tuple[list[dict[str, Any]], float]:
    equity = initial_capital
    peak = initial_capital
    max_dd_pct = 0.0
    curve = [{"i": 0, "equity": round(equity, 2), "drawdown_pct": 0.0}]
    for idx, t in enumerate(sorted(trades, key=lambda x: x.exit_ts), start=1):
        equity += t.net_pnl
        peak = max(peak, equity)
        dd_pct = ((peak - equity) / peak * 100) if peak else 0.0
        max_dd_pct = max(max_dd_pct, dd_pct)
        curve.append({"i": idx, "ts": t.exit_ts, "equity": round(equity, 2), "drawdown_pct": round(dd_pct, 3), "symbol": t.symbol})
    return curve, round(max_dd_pct, 3)


def run_filter_strategy_backtest(
    paths: dict[str, list[dict[str, Any]]],
    entry_filter: str,
    exit_filter: str | None = None,
    *,
    execution: ExecutionConfig | None = None,
    data_trust: dict[str, Any] | None = None,
    mode: str = "strategy",
) -> dict[str, Any]:
    """Run filter-backed strategy with next-bar execution.

    Quant safety: entry decisions are evaluated on bar ``i`` and executed at
    bar ``i+1``. Exit signal decisions are evaluated on bar ``j`` and executed
    at ``j+1`` when available. This prevents using the execution bar as signal
    input for the same timestamp.
    """
    execution = execution or ExecutionConfig()
    data_trust = data_trust or build_data_trust_context("unknown")
    strategy = FilterStrategy(
        StrategyMetadata(id="filter-strategy", name="Filter Strategy"),
        entry_filter,
        side=StrategySignalSide.BUY,
    )
    strategy.validate()
    exit_strategy = None
    if exit_filter:
        exit_strategy = FilterStrategy(StrategyMetadata(id="exit-filter", name="Exit Filter"), exit_filter, side=StrategySignalSide.SELL)
        exit_strategy.validate()

    trades: list[TradeResult] = []
    warnings: list[str] = []
    trust_state = data_trust.get("state")
    if trust_state in {"mock", "synthetic"}:
        warnings.append("Backtest uses generated/mock data; results are educational and not live-market proof.")
    elif trust_state == "stale":
        warnings.append("Backtest input data is stale; results must not be interpreted as current live-market performance.")
    elif trust_state == "unavailable":
        warnings.append("Backtest data is unavailable or incomplete; results are not suitable for performance claims.")

    for sym, raw_series in paths.items():
        series = sorted(raw_series, key=lambda x: x.get("ts") or 0)
        i = 0
        while i < len(series) - 1:
            signal_ctx = StrategyContext(rows=[{**series[i], "symbol": series[i].get("symbol") or sym}], data_trust=data_trust)
            if not strategy.generate(signal_ctx):
                i += 1
                continue
            entry_bar_idx = i + 1
            entry_bar = series[entry_bar_idx]
            raw_entry = _bar_price(entry_bar)
            if raw_entry <= 0:
                i += 1
                continue
            entry_price = raw_entry * (1 + execution.slippage_pct / 100)
            capital_used = execution.initial_capital * max(0.0, execution.position_size_pct) / 100
            qty = capital_used / entry_price if entry_price else 0.0
            entry_comm = capital_used * execution.commission_pct / 100
            entry_slip = max(0.0, entry_price - raw_entry) * qty
            exit_idx = entry_bar_idx
            exit_reason = "max_hold"
            raw_exit = raw_entry

            max_j = min(len(series) - 1, entry_bar_idx + execution.max_hold_bars)
            j = entry_bar_idx + 1
            while j <= max_j:
                decision_bar = series[j]
                high, low, decision_px, has_hl = _bar_levels(decision_bar, raw_entry)
                reason, fill = resolve_same_bar_tp_sl(
                    entry_price,
                    high,
                    low,
                    decision_px,
                    execution.take_profit_pct,
                    execution.stop_loss_pct,
                    has_intrabar_range=has_hl,
                )
                if reason:
                    exit_idx = j
                    exit_reason = reason
                    raw_exit = fill if fill is not None else decision_px
                    if reason == "stop_loss_same_bar_ambiguous":
                        warnings.append(
                            "Same-bar TP and SL both reachable; conservative stop applied (intrabar order unknown)."
                        )
                    break
                if exit_strategy and j < len(series) - 1:
                    exit_ctx = StrategyContext(rows=[{**decision_bar, "symbol": decision_bar.get("symbol") or sym}], data_trust=data_trust)
                    if exit_strategy.generate(exit_ctx):
                        exit_idx = j + 1
                        exit_reason = "exit_filter_next_bar"
                        raw_exit = _bar_price(series[exit_idx], decision_px)
                        break
                exit_idx = j
                raw_exit = decision_px
                j += 1

            exit_price = raw_exit * (1 - execution.slippage_pct / 100)
            gross_pnl = (exit_price - entry_price) * qty
            exit_comm = abs(exit_price * qty) * execution.commission_pct / 100
            exit_slip = max(0.0, raw_exit - exit_price) * qty
            total_comm = entry_comm + exit_comm
            total_slip = entry_slip + exit_slip
            net_pnl = gross_pnl - total_comm
            ret_pct = (net_pnl / capital_used * 100) if capital_used else 0.0
            trades.append(
                TradeResult(
                    symbol=sym,
                    entry_ts=_safe_float(entry_bar.get("ts")),
                    exit_ts=_safe_float(series[exit_idx].get("ts")),
                    entry_price=round(entry_price, 4),
                    exit_price=round(exit_price, 4),
                    ret_pct=round(ret_pct, 4),
                    holding_bars=max(0, exit_idx - entry_bar_idx),
                    entry_score=_safe_float(series[i].get("entry_score")),
                    exit_reason=exit_reason,
                    quantity=round(qty, 6),
                    gross_pnl=round(gross_pnl, 2),
                    net_pnl=round(net_pnl, 2),
                    commission=round(total_comm, 2),
                    slippage_cost=round(total_slip, 2),
                )
            )
            i = max(exit_idx + 1, i + 2)

    metrics = _metrics_from_trades(trades, execution.initial_capital)
    curve, max_dd = _equity_curve(trades, execution.initial_capital)
    best = max(trades, key=lambda t: t.ret_pct) if trades else None
    worst = min(trades, key=lambda t: t.ret_pct) if trades else None
    report = BacktestReport(
        mode=mode,
        bars=max((len(v) for v in paths.values()), default=0),
        symbols_tested=len(paths),
        trades=len(trades),
        win_rate=metrics["win_rate"],
        avg_return=metrics["average_return"],
        median_return=metrics["median_return"],
        total_return_sum=round(sum(t.ret_pct for t in trades), 3),
        max_drawdown=max_dd,
        profit_factor=metrics["profit_factor"],
        sharpe_like=metrics["sharpe_ratio"],
        avg_holding_bars=round(sum(t.holding_bars for t in trades) / len(trades), 2) if trades else 0.0,
        best_trade=asdict(best) if best else None,
        worst_trade=asdict(worst) if worst else None,
        equity_curve=curve[-500:],
        trades_sample=[asdict(t) for t in trades[:100]],
        params={"entry_filter": entry_filter, "exit_filter": exit_filter, "execution": asdict(execution)},
        notes=["Signals use bar t; entries execute on next bar to reduce look-ahead bias.", "No broker/live trading integration is included."],
        metrics={**metrics, "maximum_drawdown": max_dd, "equity_curve_points": len(curve)},
        warnings=warnings,
        data_trust=data_trust,
        quant_safety={
            "lookahead_policy": "entry_signal_t_executes_t_plus_1; exit_filter_t_executes_t_plus_1_when_available",
            "no_future_bar_for_entry": True,
            "walk_forward_oos_required": True,
            "live_trading": False,
            "same_bar_tp_sl": "close_only_uses_close; ohlc_both_touch_uses_conservative_stop",
            "same_bar_policy": "conservative_stop_when_tp_and_sl_both_reachable",
            "sharpe_basis": "per_trade_return_not_annualized",
            "walk_forward_mode": "rolling_oos_of_fixed_filter_not_parameter_optimization",
            "walk_forward_is_optimizer": False,
        },
    )
    return report.to_dict()


def run_backtest(
    paths: dict[str, list[dict[str, Any]]],
    entry_threshold: float = 65.0,
    exit_threshold: float = 60.0,
    take_profit: float = 4.0,
    stop_loss: float = -3.0,
    max_hold_bars: int = 24,
    fee_pct: float = 0.5,
    slippage_pct: float = 0.0,
) -> BacktestReport:
    entry_filter = f"entry_score >= {float(entry_threshold)}"
    exit_filter = f"exit_score >= {float(exit_threshold)}"
    d = run_filter_strategy_backtest(
        paths,
        entry_filter,
        exit_filter,
        execution=ExecutionConfig(
            initial_capital=100_000_000,
            position_size_pct=10,
            commission_pct=fee_pct,
            slippage_pct=slippage_pct,
            max_hold_bars=max_hold_bars,
            take_profit_pct=take_profit,
            stop_loss_pct=stop_loss,
        ),
        data_trust=build_data_trust_context("mixed"),
        mode="path",
    )
    return BacktestReport(**{k: v for k, v in d.items() if k in BacktestReport.__dataclass_fields__})


def _slice_paths(paths: dict[str, list[dict[str, Any]]], start: int, end: int) -> dict[str, list[dict[str, Any]]]:
    return {sym: series[start:end] for sym, series in paths.items() if len(series[start:end]) >= 2}


def run_walk_forward(
    paths: dict[str, list[dict[str, Any]]],
    entry_filter: str,
    exit_filter: str | None = None,
    *,
    config: WalkForwardConfig | None = None,
    execution: ExecutionConfig | None = None,
    data_trust: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or WalkForwardConfig()
    max_len = max((len(v) for v in paths.values()), default=0)
    windows: list[dict[str, Any]] = []
    cursor = 0
    while cursor + config.train_bars + config.test_bars <= max_len:
        train_start = cursor
        train_end = cursor + config.train_bars
        test_start = train_end
        test_end = test_start + config.test_bars
        if train_end - train_start < config.min_train_bars:
            cursor += config.step_bars
            continue
        test_paths = _slice_paths(paths, test_start, test_end)
        result = run_filter_strategy_backtest(
            test_paths,
            entry_filter,
            exit_filter,
            execution=execution,
            data_trust=data_trust,
            mode="walk_forward_oos",
        )
        windows.append(
            {
                "train": {"start_index": train_start, "end_index": train_end - 1, "bars": train_end - train_start},
                "test": {"start_index": test_start, "end_index": test_end - 1, "bars": test_end - test_start},
                "result": {"metrics": result.get("metrics"), "trades": result.get("trades"), "warnings": result.get("warnings")},
            }
        )
        cursor += config.step_bars
    total_trades = sum(int(w["result"].get("trades") or 0) for w in windows)
    avg_return = sum(float((w["result"].get("metrics") or {}).get("total_return") or 0) for w in windows) / len(windows) if windows else 0.0
    return {
        "mode": "walk_forward",
        "config": asdict(config),
        "windows": windows,
        "summary": {"windows": len(windows), "total_oos_trades": total_trades, "avg_window_total_return": round(avg_return, 3)},
        "leakage_policy": "train indexes are excluded from each test slice; strategy parameters are not optimized in P3.27",
        "walk_forward_is_optimizer": False,
        "methodology": "rolling_out_of_sample_validation_of_fixed_filter",
        "data_trust": data_trust or build_data_trust_context("unknown"),
    }


def run_forward_test(
    paths: dict[str, list[dict[str, Any]]],
    entry_filter: str,
    exit_filter: str | None = None,
    *,
    start_ts: float | None = None,
    execution: ExecutionConfig | None = None,
    data_trust: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if start_ts is None:
        # explicit boundary: use the last third as out-of-sample forward segment
        max_len = max((len(v) for v in paths.values()), default=0)
        start_idx = max_len * 2 // 3
        fwd_paths = _slice_paths(paths, start_idx, max_len)
        boundary = {"type": "index", "start_index": start_idx}
    else:
        fwd_paths = {sym: [b for b in series if _safe_float(b.get("ts")) >= start_ts] for sym, series in paths.items()}
        fwd_paths = {sym: rows for sym, rows in fwd_paths.items() if len(rows) >= 2}
        boundary = {"type": "timestamp", "start_ts": start_ts}
    result = run_filter_strategy_backtest(
        fwd_paths,
        entry_filter,
        exit_filter,
        execution=execution,
        data_trust=data_trust,
        mode="forward_oos",
    )
    result["forward_boundary"] = boundary
    result["mode"] = "forward_test"
    return result


def backtest_from_market(
    symbols: list[SymbolSnapshot],
    store: Store,
    cfg: Settings | None = None,
    use_synthetic_if_needed: bool = True,
    bars: int = 80,
    strategy_filter: str | None = None,
    exit_filter: str | None = None,
    walk_forward: bool = False,
    forward_test: bool = False,
    commission_pct: float | None = None,
    slippage_pct: float = 0.0,
    capital: float = 100_000_000.0,
    position_size_pct: float = 10.0,
    **params: Any,
) -> dict[str, Any]:
    cfg = cfg or get_settings()
    sym_names = [s.l18 for s in symbols[:40]]
    paths = paths_from_store(store, sym_names, hours=36)
    mode = "history"
    source = "mixed"
    if len(paths) < 3 and use_synthetic_if_needed:
        paths = synthesize_price_path(symbols[:30], bars=bars)
        mode = "synthetic"
        source = "synthetic"
    data_trust = build_data_trust_context(source)
    execution = ExecutionConfig(
        initial_capital=capital,
        position_size_pct=position_size_pct,
        commission_pct=commission_pct if commission_pct is not None else float(params.get("fee_pct", 0.5)),
        slippage_pct=slippage_pct,
        max_hold_bars=int(params.get("max_hold_bars", 24)),
        take_profit_pct=float(params.get("take_profit", 4.0)),
        stop_loss_pct=float(params.get("stop_loss", -3.0)),
    )
    entry_filter = strategy_filter or f"entry_score >= {float(params.get('entry_threshold', 65.0))}"
    exit_expr = exit_filter or f"exit_score >= {float(params.get('exit_threshold', 60.0))}"
    if walk_forward:
        result = run_walk_forward(paths, entry_filter, exit_expr, execution=execution, data_trust=data_trust)
    elif forward_test:
        result = run_forward_test(paths, entry_filter, exit_expr, execution=execution, data_trust=data_trust)
    else:
        result = run_filter_strategy_backtest(paths, entry_filter, exit_expr, execution=execution, data_trust=data_trust, mode=mode)
    result["path_symbols"] = len(paths)
    result["strategy_filter"] = entry_filter
    result["exit_filter"] = exit_expr
    return result
