"""بک‌تست سیگنال‌های ورود/خروج روی تاریخچه اسنپ‌شات یا مسیر مصنوعی."""

from __future__ import annotations

import hashlib
import math
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app.core.config import Settings, get_settings
from app.data.store import Store
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def synthesize_price_path(
    symbols: list[SymbolSnapshot],
    bars: int = 80,
    seed: str = "bt",
) -> dict[str, list[dict[str, Any]]]:
    """مسیر قیمت/تابلوی مصنوعی برای بک‌تست وقتی تاریخچه DB کم است."""
    paths: dict[str, list[dict[str, Any]]] = {}
    now = time.time()
    step = 300  # 5 min bars
    for s in symbols:
        r = _rng(seed + s.l18)
        price = float(s.py or s.pl or 1000)
        avg_vol = float(s.avg_vol_30d or s.tvol or 1e6)
        series = []
        # regime: occasional smart money pump
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
            # fabricate flow metrics correlated with drift
            buy_power = max(0.3, 1.0 + drift * 40 + r.uniform(-0.3, 0.3))
            vol_ratio = max(0.3, 1.0 + abs(drift) * 50 + r.uniform(-0.2, 0.8))
            if pump_start <= i <= pump_start + 6:
                buy_power = max(buy_power, r.uniform(1.8, 3.5))
                vol_ratio = max(vol_ratio, r.uniform(2.0, 4.5))
            net = (buy_power - 1) * price * avg_vol * 0.01
            hot = (buy_power - 1) * 30 + (vol_ratio - 1) * 10
            # simple entry score proxy
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
                    "plp": round(plp, 2),
                    "tvol": avg_vol * vol_ratio * r.uniform(0.8, 1.2),
                    "buy_power": round(buy_power, 3),
                    "volume_ratio": round(vol_ratio, 3),
                    "individual_net_value": net,
                    "hot_net": round(hot, 2),
                    "entry_score": round(entry, 1),
                    "exit_score": round(exit_s, 1),
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
            # reconstruct volume_ratio-ish if missing
            paths[sym].append(
                {
                    "ts": t.get("ts"),
                    "symbol": sym,
                    "pl": t.get("pl"),
                    "plp": t.get("plp"),
                    "tvol": t.get("tvol"),
                    "buy_power": t.get("buy_power") or 1,
                    "volume_ratio": 1.0,
                    "individual_net_value": t.get("individual_net_value") or 0,
                    "hot_net": t.get("hot_net") or 0,
                    "entry_score": t.get("entry_score") or 0,
                    "exit_score": t.get("exit_score") or 0,
                }
            )
    # drop empty
    return {k: v for k, v in paths.items() if len(v) >= 5}


def run_backtest(
    paths: dict[str, list[dict[str, Any]]],
    entry_threshold: float = 65.0,
    exit_threshold: float = 60.0,
    take_profit: float = 4.0,
    stop_loss: float = -3.0,
    max_hold_bars: int = 24,
    fee_pct: float = 0.5,
) -> BacktestReport:
    trades: list[TradeResult] = []
    notes = []
    for sym, series in paths.items():
        series = sorted(series, key=lambda x: x.get("ts") or 0)
        i = 0
        while i < len(series):
            bar = series[i]
            if float(bar.get("entry_score") or 0) >= entry_threshold and float(bar.get("pl") or 0) > 0:
                entry_price = float(bar["pl"])
                entry_ts = float(bar.get("ts") or 0)
                entry_score = float(bar.get("entry_score") or 0)
                exit_price = entry_price
                exit_ts = entry_ts
                exit_reason = "eod"
                hold = 0
                for j in range(i + 1, min(len(series), i + 1 + max_hold_bars)):
                    b2 = series[j]
                    px = float(b2.get("pl") or entry_price)
                    ret = (px / entry_price - 1) * 100
                    hold = j - i
                    exit_price, exit_ts = px, float(b2.get("ts") or 0)
                    if ret >= take_profit:
                        exit_reason = "take_profit"
                        break
                    if ret <= stop_loss:
                        exit_reason = "stop_loss"
                        break
                    if float(b2.get("exit_score") or 0) >= exit_threshold:
                        exit_reason = "exit_signal"
                        break
                else:
                    if hold == 0 and i + 1 < len(series):
                        b2 = series[min(i + max_hold_bars, len(series) - 1)]
                        exit_price = float(b2.get("pl") or entry_price)
                        exit_ts = float(b2.get("ts") or 0)
                        hold = min(max_hold_bars, len(series) - 1 - i)
                        exit_reason = "max_hold"
                ret_pct = (exit_price / entry_price - 1) * 100 - fee_pct
                trades.append(
                    TradeResult(
                        symbol=sym,
                        entry_ts=entry_ts,
                        exit_ts=exit_ts,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        ret_pct=round(ret_pct, 3),
                        holding_bars=hold,
                        entry_score=entry_score,
                        exit_reason=exit_reason,
                    )
                )
                i += max(hold, 1) + 1
            else:
                i += 1

    rets = [t.ret_pct for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    win_rate = (len(wins) / len(rets) * 100) if rets else 0.0
    avg_ret = sum(rets) / len(rets) if rets else 0.0
    gross_win = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    if math.isinf(pf):
        pf = 99.0

    # equity curve (sum of trade returns sequential)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    curve = []
    for idx, t in enumerate(sorted(trades, key=lambda x: x.exit_ts)):
        equity += t.ret_pct
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        curve.append({"i": idx + 1, "equity": round(equity, 3), "ret": t.ret_pct, "symbol": t.symbol})

    # sharpe-like
    if len(rets) >= 2:
        mean = avg_ret
        var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
        std = math.sqrt(var) if var > 0 else 1e-9
        sharpe = mean / std
    else:
        sharpe = 0.0

    best = max(trades, key=lambda t: t.ret_pct) if trades else None
    worst = min(trades, key=lambda t: t.ret_pct) if trades else None
    if not trades:
        notes.append("هیچ معامله‌ای با این آستانه‌ها ساخته نشد — آستانه ورود را کم کنید.")
    notes.append("کارمزد/اسپرد تقریبی از ret کم شده است.")
    notes.append("نتایج گذشته تضمین آینده نیست.")

    return BacktestReport(
        mode="path",
        bars=max((len(v) for v in paths.values()), default=0),
        symbols_tested=len(paths),
        trades=len(trades),
        win_rate=round(win_rate, 2),
        avg_return=round(avg_ret, 3),
        median_return=round(_median(rets), 3),
        total_return_sum=round(sum(rets), 3),
        max_drawdown=round(max_dd, 3),
        profit_factor=round(pf, 3),
        sharpe_like=round(sharpe, 3),
        avg_holding_bars=round(sum(t.holding_bars for t in trades) / len(trades), 2) if trades else 0,
        best_trade=asdict(best) if best else None,
        worst_trade=asdict(worst) if worst else None,
        equity_curve=curve[-200:],
        trades_sample=[asdict(t) for t in sorted(trades, key=lambda x: x.ret_pct, reverse=True)[:30]],
        params={
            "entry_threshold": entry_threshold,
            "exit_threshold": exit_threshold,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "max_hold_bars": max_hold_bars,
            "fee_pct": fee_pct,
        },
        notes=notes,
    )


def backtest_from_market(
    symbols: list[SymbolSnapshot],
    store: Store,
    cfg: Settings | None = None,
    use_synthetic_if_needed: bool = True,
    bars: int = 80,
    **params: Any,
) -> dict[str, Any]:
    cfg = cfg or get_settings()
    sym_names = [s.l18 for s in symbols[:40]]
    paths = paths_from_store(store, sym_names, hours=36)
    mode = "history"
    if len(paths) < 3 and use_synthetic_if_needed:
        paths = synthesize_price_path(symbols[:30], bars=bars)
        mode = "synthetic"
    report = run_backtest(paths, **params)
    report.mode = mode
    d = report.to_dict()
    d["path_symbols"] = len(paths)
    return d
