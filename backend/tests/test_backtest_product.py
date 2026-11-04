"""Honesty-invariant tests for the product backtest engine (MASTER-RADAR §D5).

Every test is offline-deterministic: fixed epoch timestamps, no clock reads,
no network. Reference numbers (costs, Sharpe/Sortino/Calmar, monthly rows)
are re-derived IN these tests with plain Python, independently of the engine.
"""

from __future__ import annotations

import math
import statistics

import pytest

from app.engines.backtest_product import (
    BacktestRunConfig,
    DataPolicy,
    PortfolioLimits,
    RiskModel,
    SignalDecision,
    WalkForwardProductConfig,
    run_backtest,
    run_walk_forward_product,
)
from app.engines.execution_model import ExecutionModelConfig, apply_spread_slippage

DAY = 86_400
T0 = 1_704_067_200  # 2024-01-01T00:00:00Z (fixed; no clock reads anywhere)


def bar(ts: int, o: float, h: float, l: float, c: float, v: float = 1_000_000.0) -> dict:
    return {"ts": int(ts), "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": float(v)}


def flat_bars(closes, t0: int = T0, step: int = DAY, v: float = 1_000_000.0) -> list[dict]:
    """OHLC where open == previous close (deterministic, simple)."""
    bars: list[dict] = []
    prev = float(closes[0])
    for i, c in enumerate(closes):
        c = float(c)
        bars.append(bar(t0 + i * step, prev, max(prev, c), min(prev, c), c, v))
        prev = c
    return bars


class Scripted:
    """Returns pre-set decisions per index; never looks at data."""

    strategy_id = "scripted"

    def __init__(self, decisions: dict[int, SignalDecision] | None = None):
        self._decisions = dict(decisions or {})

    def prepare(self, bars: list[dict]) -> None:
        self.n_bars = len(bars)

    def decide(self, index: int) -> SignalDecision:
        return self._decisions.get(index, SignalDecision())


class Momentum:
    """Well-behaved adapter: fixed signal indices, consults nothing ahead."""

    strategy_id = "momentum"

    def __init__(self, entry_index: int, exit_index: int, size_pct: float | None = None):
        self.entry_index = entry_index
        self.exit_index = exit_index
        self.size_pct = size_pct

    def prepare(self, bars: list[dict]) -> None:
        self.n_bars = len(bars)

    def decide(self, index: int) -> SignalDecision:
        if index == self.entry_index:
            return SignalDecision(entry=True, size_pct=self.size_pct)
        if index == self.exit_index:
            return SignalDecision(exit=True)
        return SignalDecision()


def make_config(**overrides) -> BacktestRunConfig:
    kw: dict = {"run_id": "t", "execution": ExecutionModelConfig()}
    kw.update(overrides)
    return BacktestRunConfig(**kw)


# ---------------------------------------------------------------------------
# Determinism / digest
# ---------------------------------------------------------------------------


def test_two_runs_produce_identical_digest():
    bars = flat_bars([100 + i * 0.5 for i in range(60)])
    cfg = make_config(run_id="det")

    def once():
        return run_backtest({"S": bars}, {"S": Momentum(5, 25)}, cfg)

    r1, r2 = once(), once()
    assert r1.result_digest() == r2.result_digest()
    assert r1.generated_by_digest == r1.result_digest() == r2.generated_by_digest

    cfg_other = make_config(run_id="det2")
    r3 = run_backtest({"S": bars}, {"S": Momentum(5, 25)}, cfg_other)
    assert r3.result_digest() != r1.result_digest()  # config_echo (run_id) is digest-relevant

    perturbed = flat_bars([100 + i * 0.5 for i in range(59)] + [999.0])
    r4 = run_backtest({"S": perturbed}, {"S": Momentum(5, 25)}, cfg)
    assert r4.result_digest() != r1.result_digest()  # (ts, c) pairs are digest-relevant


# ---------------------------------------------------------------------------
# No-look-ahead invariants
# ---------------------------------------------------------------------------


def trades_of(result):
    return [
        (t.symbol, t.side, t.entry_ts, t.entry_price, t.exit_ts, t.exit_price, t.qty, t.net_pnl)
        for t in result.trades
    ]


def test_prefix_invariance_well_behaved_adapter():
    """Trades from bars[:50] and bars[:80] are identical for a well-behaved
    adapter: the engine's contribution to no-look-ahead (fills strictly after
    signals) plus the adapter contract (decide uses data <= index)."""
    bars = flat_bars([100 + i * 0.25 for i in range(80)])
    cfg = make_config(data_policy=DataPolicy(min_bars=30))
    r50 = run_backtest({"S": bars[:50]}, {"S": Momentum(10, 20)}, cfg)
    r80 = run_backtest({"S": bars[:80]}, {"S": Momentum(10, 20)}, cfg)
    assert len(r50.report.equity_curve) == 50
    assert len(r80.report.equity_curve) == 80
    trades50 = trades_of(r50)
    trades80 = trades_of(r80)
    assert trades50 == trades80
    assert len(trades50) == 1


def test_fill_ts_strictly_after_signal_ts():
    bars = flat_bars([100 + i * 0.25 for i in range(60)])
    cfg = make_config()
    result = run_backtest({"S": bars}, {"S": Momentum(10, 20)}, cfg)
    assert result.report.trade_count == 1
    t = result.trades[0]
    assert t.entry_signal_index == 10
    assert t.entry_index == 11  # NEXT_BAR_OPEN: strictly after the signal bar
    assert t.entry_ts == bars[11]["ts"] > bars[10]["ts"]
    assert t.exit_signal_index == 20
    assert t.exit_index == 21
    assert t.exit_ts == bars[21]["ts"] > bars[20]["ts"]


# ---------------------------------------------------------------------------
# Intrabar pessimism / exit semantics
# ---------------------------------------------------------------------------


def test_same_bar_stop_and_target_assumes_stop_first():
    bars = flat_bars([100.0] * 6) + [
        bar(T0 + 6 * DAY, 100, 101, 100, 101),
        bar(T0 + 7 * DAY, 101, 111, 94, 100),  # touches stop 95 AND target 110
        bar(T0 + 8 * DAY, 100, 100.5, 99.5, 100),
        bar(T0 + 9 * DAY, 100, 100.5, 99.5, 100),
    ]
    cfg = make_config(
        execution=ExecutionModelConfig(intrabar_tp_sl=True),
        risk=RiskModel(stop_loss_pct=5.0, take_profit_pct=10.0),
        data_policy=DataPolicy(min_bars=5),
    )
    result = run_backtest({"S": bars}, {"S": Scripted({5: SignalDecision(entry=True)})}, cfg)
    assert result.report.trade_count == 1
    t = result.trades[0]
    assert t.exit_reason == "STOP_LOSS"  # pessimistic ordering, not TAKE_PROFIT
    assert t.exit_index == 7
    assert t.exit_price == pytest.approx(95.0, abs=1e-9)
    assert t.entry_price == pytest.approx(100.0, abs=1e-9)


def test_trailing_stop_triggers_on_reversal():
    closes = [100, 100, 102, 104, 106, 100, 100, 100]
    bars = flat_bars(closes)
    cfg = make_config(risk=RiskModel(trailing_pct=5.0), data_policy=DataPolicy(min_bars=5))
    result = run_backtest({"S": bars}, {"S": Scripted({0: SignalDecision(entry=True)})}, cfg)
    assert result.report.trade_count == 1
    t = result.trades[0]
    assert t.exit_reason == "TRAILING_STOP"
    assert t.exit_index == 6  # close-only signal at bar 5 -> fill at bar 6 open
    assert t.exit_price == pytest.approx(100.0, abs=1e-9)


def test_close_only_mode_ignores_intrabar_wick():
    bars = [
        bar(T0 + 0 * DAY, 100, 100, 100, 100),
        bar(T0 + 1 * DAY, 100, 100.5, 99.5, 100),
        bar(T0 + 2 * DAY, 100, 101, 80, 100),  # wick through stop 95, close ABOVE it
        bar(T0 + 3 * DAY, 100, 100, 94, 94),  # close breaches stop -> signal
        bar(T0 + 4 * DAY, 94, 94.5, 93.5, 94),  # NEXT_BAR_OPEN exit fill here
        bar(T0 + 5 * DAY, 94, 94.5, 93.5, 94),
    ]
    cfg = make_config(
        risk=RiskModel(stop_loss_pct=5.0),
        data_policy=DataPolicy(min_bars=5),
    )  # intrabar_tp_sl defaults to False
    result = run_backtest({"S": bars}, {"S": Scripted({0: SignalDecision(entry=True)})}, cfg)
    assert result.report.trade_count == 1
    t = result.trades[0]
    assert t.exit_reason == "STOP_LOSS"
    assert t.exit_index == 4  # NOT bar 3-open: the wick bar must not exit early
    assert t.exit_price == pytest.approx(94.0, abs=1e-9)


def test_same_bar_reentry_policy():
    base_closes = [100 + i * 0.1 for i in range(10)]
    bars = flat_bars(base_closes)
    decisions = {
        0: SignalDecision(entry=True),
        5: SignalDecision(entry=True, exit=True),
    }
    adapter = Scripted(decisions)
    refused_cfg = make_config(
        execution=ExecutionModelConfig(fill_policy="SAME_BAR_CLOSE"),
        data_policy=DataPolicy(min_bars=5),
    )
    r1 = run_backtest({"S": bars}, {"S": adapter}, refused_cfg)
    assert r1.report.event_counters.get("same_bar_reentry_refused") == 1
    assert r1.report.trade_count == 1

    allowed_cfg = make_config(
        execution=ExecutionModelConfig(fill_policy="SAME_BAR_CLOSE"),
        portfolio=PortfolioLimits(allow_same_bar_reentry=True),
        data_policy=DataPolicy(min_bars=5),
    )
    r2 = run_backtest({"S": bars}, {"S": Scripted(decisions)}, allowed_cfg)
    assert r2.report.trade_count == 2
    assert r2.trades[1].entry_ts == bars[5]["ts"]
    assert r2.trades[1].exit_reason == "END_OF_DATA"


# ---------------------------------------------------------------------------
# Data-policy refusals (recorded, never raised away)
# ---------------------------------------------------------------------------


def test_refusals_recorded_other_symbol_still_tested():
    symbol_bars = {
        "AAA": flat_bars([100.0] * 10),
        "BBB": flat_bars([100 + i * 0.1 for i in range(60)]),
    }
    cfg = make_config()  # default min_bars=50
    result = run_backtest(symbol_bars, {"BBB": Momentum(5, 25)}, cfg)
    dq = {d.symbol: d for d in result.data_quality}
    assert dq["AAA"].refusals == ["insufficient_history"]
    assert dq["AAA"].bars_used == 0 and dq["AAA"].bars_refused == 10
    assert dq["BBB"].refusals == [] and dq["BBB"].bars_used == 60
    assert dq["BBB"].trust_note == "bar-based simulation; never real-tick"
    assert dq["BBB"].adjustment_semantics == "UNADJUSTED"
    assert result.data_trust_label == "SYNTHETIC_OR_PAPER"
    assert any("synthetic/fixture" in note for note in result.limitations)
    assert result.report.trade_count == 1


def test_all_symbols_refused_raises():
    symbol_bars = {
        "AAA": flat_bars([100.0] * 10),
        "BBB": flat_bars([100.0] * 10),
    }
    cfg = make_config()
    with pytest.raises(ValueError, match="all_symbols_refused"):
        run_backtest(symbol_bars, {}, cfg)


def test_stale_data_refusal():
    as_of = T0 + 69 * DAY
    symbol_bars = {
        "STALE": flat_bars([100.0] * 60),  # last ts = T0+59D, as_of-last = 10D
        "FRESH": flat_bars([100.0] * 60, t0=T0 + 10 * DAY),  # last ts = T0+69D
    }
    cfg = make_config(
        as_of_ts=as_of,
        data_policy=DataPolicy(min_bars=50, max_staleness_seconds=5 * DAY),
    )
    result = run_backtest(symbol_bars, {"FRESH": Momentum(5, 25)}, cfg)
    dq = {d.symbol: d for d in result.data_quality}
    assert dq["STALE"].refusals == ["stale_data"]
    assert dq["FRESH"].refusals == []
    assert result.report.trade_count == 1


def test_gap_refusal_only_when_enabled():
    bars = flat_bars([100.0 + i * 0.1 for i in range(60)])
    gapped = bars[:30] + [bar(b["ts"] + 10 * DAY, b["o"], b["h"], b["l"], b["c"]) for b in bars[30:]]
    healthy = {"Z": flat_bars([100.0 + i * 0.1 for i in range(60)])}
    cfg_gap = make_config(data_policy=DataPolicy(min_bars=50, refuse_gaps=True))
    result = run_backtest({"S": gapped, **healthy}, {"Z": Momentum(5, 25)}, cfg_gap)
    dq = {d.symbol: d for d in result.data_quality}
    assert dq["S"].refusals == ["ts_gap_gt_3x_expected_interval"]
    assert dq["Z"].refusals == []
    assert result.report.trade_count == 1

    cfg_ok = make_config(data_policy=DataPolicy(min_bars=50, refuse_gaps=False))
    # both symbols get adapters: inclusion without refusal must let S trade too
    result_ok = run_backtest({"S": gapped, **healthy}, {"S": Momentum(5, 25), "Z": Momentum(5, 25)}, cfg_ok)
    assert result_ok.data_quality[0].refusals == []
    assert result_ok.report.trade_count == 2


# ---------------------------------------------------------------------------
# Cost accounting (hand-derived, execution_model used for PRICES only)
# ---------------------------------------------------------------------------


def test_cost_accounting_hand_computed():
    exec_cfg = ExecutionModelConfig(
        initial_capital=100_000.0, commission_pct=1.0, spread_pct=0.2, slippage_pct=0.1
    )
    closes = [100, 101, 102, 103, 104, 110, 110, 110, 110, 110]
    bars = flat_bars(closes)
    cfg = make_config(execution=exec_cfg, data_policy=DataPolicy(min_bars=5))
    result = run_backtest({"S": bars}, {"S": Momentum(0, 5)}, cfg)
    assert result.report.trade_count == 1
    t = result.trades[0]

    # prices recomputed via execution_model (allowed for PRICE only)
    p_entry = apply_spread_slippage(100.0, "buy", exec_cfg)
    p_exit = apply_spread_slippage(110.0, "sell", exec_cfg)
    assert t.entry_price == p_entry
    assert t.exit_price == p_exit

    # sizing hand-derived: floor(initial / (close0 * (1+s/2) * (1+sl))) to lot 1
    est_factor = (1.0 + 0.2 / 200.0) * (1.0 + 0.1 / 100.0)
    qty_expected = math.floor(100_000.0 / (100.0 * est_factor))
    assert qty_expected == 998
    assert t.qty == pytest.approx(qty_expected, abs=1e-9)

    # pnl arithmetic fully hand-derived here (no engine helpers)
    notional_e = p_entry * 998.0
    notional_x = p_exit * 998.0
    gross_expected = (p_exit - p_entry) * 998.0
    commission_expected = notional_e * 0.01 + notional_x * 0.01
    net_expected = gross_expected - commission_expected
    fees_expected = (notional_e + notional_x) * (0.01 + 0.002 / 2.0 + 0.001)

    assert t.gross_pnl == pytest.approx(gross_expected, abs=1e-9)
    assert t.commission_cash == pytest.approx(commission_expected, abs=1e-9)
    assert t.net_pnl == pytest.approx(net_expected, abs=1e-9)
    assert result.report.fees_total == pytest.approx(fees_expected, abs=1e-9)
    # no double counting: spread/slippage cash reported but not re-deducted
    assert t.spread_cash == pytest.approx((notional_e + notional_x) * 0.001, abs=1e-9)
    assert t.slippage_cash == pytest.approx((notional_e + notional_x) * 0.001, abs=1e-9)


# ---------------------------------------------------------------------------
# Risk metrics vs independent references
# ---------------------------------------------------------------------------


def test_sharpe_sortino_vs_independent_reference():
    # rising then falling closes; the scripted position is held through the
    # falling leg (exit signal at 55 -> fill at 56) so the equity curve has
    # BOTH nonzero std and nonzero downside deviation
    closes = [100 + i for i in range(30)] + [128 - j for j in range(1, 31)]
    bars = flat_bars(closes)
    cfg = make_config()
    result = run_backtest({"S": bars}, {"S": Momentum(5, 55)}, cfg)
    curve = result.report.equity_curve

    # independent recomputation with plain Python (formulas written HERE)
    rets = [curve[0].equity / 100_000.0 - 1.0]
    for i in range(1, len(curve)):
        rets.append(curve[i].equity / curve[i - 1].equity - 1.0)
    assert min(rets) < 0.0  # scenario really has downside
    mean = statistics.fmean(rets)
    sd = statistics.stdev(rets)  # sample stddev (ddof=1), same convention
    sharpe_ref = mean / sd * math.sqrt(252.0)
    downside = math.sqrt(sum(min(r, 0.0) ** 2 for r in rets) / len(rets))
    sortino_ref = mean / downside * math.sqrt(252.0)

    assert result.report.sharpe == pytest.approx(sharpe_ref, rel=1e-9, abs=1e-12)
    assert result.report.sortino == pytest.approx(sortino_ref, rel=1e-9, abs=1e-12)
    assert result.report.annualization_assumption == "sqrt(252) bar-return scaling; rf=0"
    assert 0.0 <= result.report.exposure_pct <= 100.0
    assert result.report.turnover is not None and result.report.turnover > 0


def test_sortino_none_when_no_downside():
    bars = flat_bars([100 + i for i in range(60)])  # monotonic equity: no negative returns
    cfg = make_config()
    result = run_backtest({"S": bars}, {"S": Momentum(5, 25)}, cfg)
    assert result.report.sortino is None
    assert result.report.sharpe is not None


def test_calmar_and_cagr_over_one_year_span():
    closes = [100.0] * 11 + [90.0 + (i - 11) * 0.11 for i in range(11, 400)]
    bars = flat_bars(closes)
    cfg = make_config()
    result = run_backtest({"S": bars}, {"S": Momentum(10, 380)}, cfg)
    curve = result.report.equity_curve
    total_return = curve[-1].equity / 100_000.0 - 1.0
    span_seconds = curve[-1].ts - curve[0].ts
    years = span_seconds / (365.25 * 86_400.0)
    cagr_ref = ((1.0 + total_return) ** (1.0 / years) - 1.0) * 100.0

    # independent max drawdown recomputation
    peak, max_dd = 100_000.0, 0.0
    for pt in curve:
        peak = max(peak, pt.equity)
        max_dd = max(max_dd, (peak - pt.equity) / peak * 100.0)

    assert years > 1.0
    assert result.report.cagr_pct == pytest.approx(cagr_ref, rel=1e-9)
    assert result.report.max_drawdown_pct == pytest.approx(max_dd, rel=1e-9)
    assert result.report.calmar == pytest.approx(cagr_ref / max_dd, rel=1e-9)


def test_cagr_none_for_short_span_with_limitation():
    bars = flat_bars([100 + i * 0.25 for i in range(60)])
    cfg = make_config()
    result = run_backtest({"S": bars}, {"S": Momentum(5, 25)}, cfg)
    assert result.report.cagr_pct is None
    assert result.report.calmar is None
    assert any("CAGR" in note and "1 year" in note for note in result.limitations)
    assert result.report.annualized_return_pct is not None


# ---------------------------------------------------------------------------
# Calendar / distribution / decomposition reports
# ---------------------------------------------------------------------------


def test_monthly_returns_span_three_utc_months():
    closes = [100, 101, 102, 103, 104, 105, 106, 107, 108]
    bars = flat_bars(closes, step=10 * DAY)  # Jan 1 .. Mar 21, 2024 UTC
    cfg = make_config(data_policy=DataPolicy(min_bars=5))
    result = run_backtest({"S": bars}, {"S": Momentum(0, 7)}, cfg)
    rows = [(m.year, m.month) for m in result.report.monthly_returns]
    assert rows == [(2024, 1), (2024, 2), (2024, 3)]
    assert all(m.return_pct is not None for m in result.report.monthly_returns)
    assert [(y.year) for y in result.report.yearly_returns] == [2024]


def test_trade_distribution_bins_deterministic():
    bars = flat_bars([100 + i * 0.5 for i in range(60)])
    cfg = make_config()
    result = run_backtest({"S": bars}, {"S": Momentum(5, 25)}, cfg)
    bins = result.report.trade_distribution
    assert len(bins) == 10
    assert bins[0].bin_low < 0 < bins[9].bin_high
    assert sum(b.count for b in bins) == result.report.trade_count
    for lo, hi in zip(bins, bins[1:]):
        assert hi.bin_low == pytest.approx(lo.bin_high)


def test_long_short_decomposition_long_only_by_default():
    bars = flat_bars([100 + i * 0.25 for i in range(60)])
    cfg = make_config()
    decisions = {
        5: SignalDecision(entry=True),
        15: SignalDecision(exit=True),
        30: SignalDecision(entry=True),
        45: SignalDecision(exit=True),
    }
    result = run_backtest({"S": bars}, {"S": Scripted(decisions)}, cfg)
    dec = result.report.long_short_decomposition
    assert dec.long.trades == 2 == result.report.trade_count
    assert dec.long.wins == 2
    assert dec.short.trades == 0


def test_short_trade_when_allow_short():
    bars = flat_bars([100 - i * 0.25 for i in range(60)])  # falling market
    cfg = make_config(execution=ExecutionModelConfig(allow_short=True))
    decisions = {0: SignalDecision(exit=True), 10: SignalDecision(entry=True)}
    result = run_backtest({"S": bars}, {"S": Scripted(decisions)}, cfg)
    shorts = [t for t in result.trades if t.side == "SHORT"]
    assert len(shorts) == 1
    assert shorts[0].exit_reason == "SIGNAL"
    assert result.report.long_short_decomposition.short.trades == 1
    assert shorts[0].net_pnl > 0  # short into a falling market profits


def test_exit_without_position_counted():
    bars = flat_bars([100.0] * 20)
    cfg = make_config(data_policy=DataPolicy(min_bars=5))
    result = run_backtest({"S": bars}, {"S": Scripted({0: SignalDecision(exit=True)})}, cfg)
    assert result.report.event_counters.get("exit_without_position") == 1
    assert result.report.trade_count == 0


def test_end_of_data_exit_marks_last_close():
    bars = flat_bars([100 + i * 0.25 for i in range(60)])
    cfg = make_config()
    result = run_backtest({"S": bars}, {"S": Scripted({57: SignalDecision(entry=True)})}, cfg)
    assert result.report.trade_count == 1
    t = result.trades[0]
    assert t.exit_reason == "END_OF_DATA"
    assert t.closed_at_end_of_data is True
    assert t.exit_ts == bars[59]["ts"]
    assert t.exit_index == 59
    assert any("END_OF_DATA" in note for note in result.limitations)


# ---------------------------------------------------------------------------
# Portfolio gates and sizing
# ---------------------------------------------------------------------------


def test_max_positions_gate_in_portfolio_mode():
    symbol_bars = {s: flat_bars([100 + i * 0.1 for i in range(60)]) for s in ("AAA", "BBB", "CCC")}
    cfg = make_config(portfolio=PortfolioLimits(max_open_positions=2))
    adapters = {s: Scripted({0: SignalDecision(entry=True)}) for s in symbol_bars}
    result = run_backtest(symbol_bars, adapters, cfg)
    assert result.report.event_counters.get("max_positions") == 1
    assert result.report.trade_count == 2
    traded = {t.symbol for t in result.trades}
    assert traded == {"AAA", "BBB"}


def test_blacklisted_symbol_refused():
    bars = flat_bars([100 + i * 0.1 for i in range(60)])
    cfg = make_config(portfolio=PortfolioLimits(per_symbol_blacklist=["S"]))
    result = run_backtest({"S": bars}, {"S": Scripted({5: SignalDecision(entry=True)})}, cfg)
    assert result.report.event_counters.get("entry_refused:blacklisted") == 1
    assert result.report.trade_count == 0


def test_risk_based_sizing_quantity():
    bars = flat_bars([100.0] * 60)
    cfg = make_config(
        risk=RiskModel(sizing_mode="RISK_BASED", risk_pct_of_equity=1.0, stop_loss_pct=5.0),
    )
    result = run_backtest({"S": bars}, {"S": Scripted({5: SignalDecision(entry=True)})}, cfg)
    assert result.report.trade_count == 1
    # qty = equity * risk_pct/100 / stop_distance = 100000*0.01/5 = 200
    assert result.trades[0].qty == pytest.approx(200.0, abs=1e-9)


def test_regime_segment_from_labels():
    bars = flat_bars([100 + i * 0.25 for i in range(60)])
    labels = [0] * 6 + [1] * 54  # entry fills at index 6 -> regime 1
    cfg = make_config(regime_labels={"S": labels})
    result = run_backtest({"S": bars}, {"S": Momentum(5, 25)}, cfg)
    segs = result.report.regime_segments
    assert len(segs) == 1
    assert segs[0].regime == 1
    assert segs[0].trades == 1
    assert segs[0].win_rate == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


def test_benchmark_buy_and_hold_with_same_costs():
    closes = [100.0] * 55 + [110.0] * 5
    bars = flat_bars(closes)
    cfg = make_config()
    result = run_backtest({"S": bars}, {"S": Momentum(5, 25)}, cfg)
    bench = result.benchmark
    assert bench is not None
    assert bench.symbol == "S"
    # qty = 100000/100 = 1000 at zero cost, marked at last close 110 -> +10%
    assert bench.benchmark_total_return_pct == pytest.approx(10.0, abs=1e-9)
    assert bench.benchmark_max_drawdown_pct >= 0.0
    assert len(bench.benchmark_equity_curve) == 60
    assert result.report.total_return_pct is not None


# ---------------------------------------------------------------------------
# Walk-forward (product level: evaluation only, no selection)
# ---------------------------------------------------------------------------


def test_walk_forward_anchored_windows_and_aggregation():
    bars = flat_bars([100 + i * 0.5 for i in range(120)])
    cfg = make_config(data_policy=DataPolicy(min_bars=5))
    wf_cfg = WalkForwardProductConfig(n_splits=2, anchored=True, min_train_bars=30, min_test_bars=30)
    calls = {"n": 0}

    def factory(params: dict):
        calls["n"] += 1
        return Momentum(10, 30)

    wf = run_walk_forward_product({"S": bars}, factory, cfg, wf_cfg)
    assert [w.window_index for w in wf.windows] == [0, 1]
    ts = [b["ts"] for b in bars]
    assert wf.windows[0].test_start_ts == ts[40] and wf.windows[0].test_end_ts == ts[79]
    assert wf.windows[1].test_start_ts == ts[80] and wf.windows[1].test_end_ts == ts[119]
    assert wf.windows[0].train_end_ts == ts[40]  # anchored: everything before test
    assert wf.windows[1].train_end_ts == ts[80]
    assert wf.window_boundaries == [[ts[0], ts[39], ts[40], ts[79]], [ts[0], ts[79], ts[80], ts[119]]]
    assert len(wf.aggregated_oos_curve) == 80
    assert wf.oos_total_return_pct is not None
    assert wf.oos_max_drawdown_pct is not None
    assert wf.walk_forward_efficiency is not None
    assert calls["n"] > 0
    assert any("no parameter selection" in note for note in wf.limitations)


def test_walk_forward_skips_undersized_windows():
    bars = flat_bars([100 + i * 0.5 for i in range(100)])
    cfg = make_config(data_policy=DataPolicy(min_bars=5))
    # 100 bars / 4 chunks = 25: window 0 trains on 25 < 30 -> skipped; 1,2 valid
    wf_cfg = WalkForwardProductConfig(n_splits=3, anchored=True, min_train_bars=30, min_test_bars=20)
    wf = run_walk_forward_product({"S": bars}, lambda p: Momentum(5, 10), cfg, wf_cfg)
    assert [w.window_index for w in wf.windows] == [1, 2]
    assert wf.skipped_windows == [{"window_index": 0, "reason": "insufficient_train_bars"}]

    # every window undersized -> fail-closed ValueError, nothing silently empty
    with pytest.raises(ValueError, match="all_walk_forward_windows_skipped"):
        run_walk_forward_product(
            {"S": flat_bars([100.0] * 60)},
            lambda p: Momentum(5, 10),
            cfg,
            WalkForwardProductConfig(n_splits=3, anchored=True, min_train_bars=20, min_test_bars=20),
        )
