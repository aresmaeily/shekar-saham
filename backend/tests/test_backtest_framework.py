from app.core.config import build_data_trust_context
from app.engines.backtest import (
    ExecutionConfig,
    WalkForwardConfig,
    run_filter_strategy_backtest,
    run_forward_test,
    run_walk_forward,
)


def _paths():
    return {
        "فملی": [
            {"ts": 1, "symbol": "فملی", "pl": 100, "entry_score": 80, "exit_score": 0, "buy_power": 2, "volume_ratio": 3, "sma_20": 90, "rsi_14": 30},
            {"ts": 2, "symbol": "فملی", "pl": 102, "entry_score": 10, "exit_score": 0, "buy_power": 1, "volume_ratio": 1, "sma_20": 90, "rsi_14": 40},
            {"ts": 3, "symbol": "فملی", "pl": 108, "entry_score": 0, "exit_score": 0, "buy_power": 1, "volume_ratio": 1},
            {"ts": 4, "symbol": "فملی", "pl": 104, "entry_score": 0, "exit_score": 90, "buy_power": 0.5, "volume_ratio": 2},
            {"ts": 5, "symbol": "فملی", "pl": 103, "entry_score": 0, "exit_score": 0},
            {"ts": 6, "symbol": "فملی", "pl": 110, "entry_score": 80, "exit_score": 0, "buy_power": 2, "volume_ratio": 3, "sma_20": 100, "rsi_14": 28},
            {"ts": 7, "symbol": "فملی", "pl": 112, "entry_score": 0, "exit_score": 0},
            {"ts": 8, "symbol": "فملی", "pl": 115, "entry_score": 0, "exit_score": 0},
        ]
    }


def test_backtest_entry_executes_next_bar_no_lookahead():
    report = run_filter_strategy_backtest(
        _paths(),
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=0, slippage_pct=0, take_profit_pct=50, stop_loss_pct=-50, max_hold_bars=2),
        data_trust=build_data_trust_context("mock"),
    )
    assert report["trades"] >= 1
    first = report["trades_sample"][0]
    assert first["entry_ts"] == 2
    assert first["entry_price"] == 102
    assert report["quant_safety"]["no_future_bar_for_entry"] is True


def test_backtest_commission_and_slippage_reduce_pnl():
    no_cost = run_filter_strategy_backtest(
        _paths(),
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=0, slippage_pct=0, max_hold_bars=2, take_profit_pct=50, stop_loss_pct=-50),
        data_trust=build_data_trust_context("mock"),
    )
    with_cost = run_filter_strategy_backtest(
        _paths(),
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=1, slippage_pct=1, max_hold_bars=2, take_profit_pct=50, stop_loss_pct=-50),
        data_trust=build_data_trust_context("mock"),
    )
    assert with_cost["metrics"]["net_profit_loss"] < no_cost["metrics"]["net_profit_loss"]


def test_no_trade_scenario():
    report = run_filter_strategy_backtest(_paths(), "entry_score > 999", data_trust=build_data_trust_context("mock"))
    assert report["trades"] == 0
    assert report["metrics"]["number_of_trades"] == 0


def test_multiple_trades_and_equity_curve():
    report = run_filter_strategy_backtest(
        _paths(),
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=0, slippage_pct=0, max_hold_bars=1, take_profit_pct=50, stop_loss_pct=-50),
        data_trust=build_data_trust_context("mock"),
    )
    assert report["trades"] >= 2
    assert len(report["equity_curve"]) == report["trades"] + 1
    assert "maximum_drawdown" in report["metrics"]


def test_walk_forward_uses_out_of_sample_windows():
    paths = {"فملی": [{"ts": i, "symbol": "فملی", "pl": 100 + i, "entry_score": 80 if i % 3 == 0 else 0} for i in range(40)]}
    res = run_walk_forward(
        paths,
        "entry_score >= 70",
        config=WalkForwardConfig(train_bars=10, test_bars=5, step_bars=5),
        data_trust=build_data_trust_context("mock"),
    )
    assert res["summary"]["windows"] > 0
    for w in res["windows"]:
        assert w["train"]["end_index"] < w["test"]["start_index"]
    assert "excluded from each test slice" in res["leakage_policy"]


def test_forward_test_uses_later_boundary():
    paths = {"فملی": [{"ts": i, "symbol": "فملی", "pl": 100 + i, "entry_score": 80 if i >= 8 else 0} for i in range(12)]}
    res = run_forward_test(paths, "entry_score >= 70", start_ts=8, data_trust=build_data_trust_context("mock"))
    assert res["mode"] == "forward_test"
    assert res["forward_boundary"]["start_ts"] == 8
    assert res["bars"] <= 4


def test_filter_to_strategy_to_backtest_indicator_path():
    report = run_filter_strategy_backtest(
        _paths(),
        "close > sma(20) and rsi(14) < 35",
        data_trust=build_data_trust_context("mock"),
    )
    assert report["data_trust"]["state"] == "mock"
    assert report["trades"] >= 1


def test_data_trust_is_preserved_in_backtest_report():
    report = run_filter_strategy_backtest(_paths(), "entry_score >= 70", data_trust=build_data_trust_context("synthetic"))
    assert report["data_trust"]["state"] == "synthetic"
    assert report["data_trust"]["is_live"] is False
    assert report["warnings"]


def test_close_only_tp_uses_close_not_intrabar_guess():
    from app.engines.backtest import ExecutionConfig

    paths = {
        "فملی": [
            {"ts": 1, "symbol": "فملی", "pl": 100, "entry_score": 80},
            {"ts": 2, "symbol": "فملی", "pl": 100, "entry_score": 0},
            {"ts": 3, "symbol": "فملی", "pl": 105, "entry_score": 0},
        ]
    }
    report = run_filter_strategy_backtest(
        paths,
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=0, slippage_pct=0, take_profit_pct=4, stop_loss_pct=-3, max_hold_bars=3),
        data_trust=build_data_trust_context("mock"),
    )
    assert report["trades"] == 1
    trade = report["trades_sample"][0]
    assert trade["exit_reason"] == "take_profit"
    assert trade["entry_price"] == 100
    assert trade["exit_price"] == 105


def test_close_only_sl_uses_close():
    from app.engines.backtest import ExecutionConfig

    paths = {
        "فملی": [
            {"ts": 1, "symbol": "فملی", "pl": 100, "entry_score": 80},
            {"ts": 2, "symbol": "فملی", "pl": 100, "entry_score": 0},
            {"ts": 3, "symbol": "فملی", "pl": 96, "entry_score": 0},
        ]
    }
    report = run_filter_strategy_backtest(
        paths,
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=0, slippage_pct=0, take_profit_pct=4, stop_loss_pct=-3, max_hold_bars=3),
        data_trust=build_data_trust_context("mock"),
    )
    trade = report["trades_sample"][0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["exit_price"] == 96


def test_ohlc_same_bar_tp_and_sl_is_conservative_stop():
    from app.engines.backtest import ExecutionConfig

    paths = {
        "فملی": [
            {"ts": 1, "symbol": "فملی", "pl": 100, "entry_score": 80},
            {"ts": 2, "symbol": "فملی", "pl": 100, "high": 100, "low": 100, "entry_score": 0},
            {"ts": 3, "symbol": "فملی", "pl": 101, "high": 106, "low": 96, "entry_score": 0},
        ]
    }
    report = run_filter_strategy_backtest(
        paths,
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=0, slippage_pct=0, take_profit_pct=4, stop_loss_pct=-3, max_hold_bars=3),
        data_trust=build_data_trust_context("mock"),
    )
    trade = report["trades_sample"][0]
    assert trade["exit_reason"] == "stop_loss_same_bar_ambiguous"
    assert trade["exit_price"] == 97  # 100 * (1 - 0.03)
    assert any("conservative stop" in w.lower() or "Same-bar" in w for w in report["warnings"])
    assert report["quant_safety"]["same_bar_policy"] == "conservative_stop_when_tp_and_sl_both_reachable"


def test_ohlc_tp_only_fills_at_tp_level():
    from app.engines.backtest import ExecutionConfig

    paths = {
        "فملی": [
            {"ts": 1, "symbol": "فملی", "pl": 100, "entry_score": 80},
            {"ts": 2, "symbol": "فملی", "pl": 100, "high": 100, "low": 100, "entry_score": 0},
            {"ts": 3, "symbol": "فملی", "pl": 101, "high": 106, "low": 99, "entry_score": 0},
        ]
    }
    report = run_filter_strategy_backtest(
        paths,
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=0, slippage_pct=0, take_profit_pct=4, stop_loss_pct=-3, max_hold_bars=3),
        data_trust=build_data_trust_context("mock"),
    )
    trade = report["trades_sample"][0]
    assert trade["exit_reason"] == "take_profit"
    assert trade["exit_price"] == 104


def test_ohlc_sl_only_fills_at_sl_level():
    from app.engines.backtest import ExecutionConfig

    paths = {
        "فملی": [
            {"ts": 1, "symbol": "فملی", "pl": 100, "entry_score": 80},
            {"ts": 2, "symbol": "فملی", "pl": 100, "high": 100, "low": 100, "entry_score": 0},
            {"ts": 3, "symbol": "فملی", "pl": 99, "high": 101, "low": 96, "entry_score": 0},
        ]
    }
    report = run_filter_strategy_backtest(
        paths,
        "entry_score >= 70",
        execution=ExecutionConfig(commission_pct=0, slippage_pct=0, take_profit_pct=4, stop_loss_pct=-3, max_hold_bars=3),
        data_trust=build_data_trust_context("mock"),
    )
    trade = report["trades_sample"][0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["exit_price"] == 97


def test_walk_forward_is_not_an_optimizer():
    paths = {"فملی": [{"ts": i, "symbol": "فملی", "pl": 100 + i, "entry_score": 80 if i % 3 == 0 else 0} for i in range(40)]}
    res = run_walk_forward(
        paths,
        "entry_score >= 70",
        config=WalkForwardConfig(train_bars=10, test_bars=5, step_bars=5),
        data_trust=build_data_trust_context("mock"),
    )
    assert res["walk_forward_is_optimizer"] is False
    assert res["methodology"] == "rolling_out_of_sample_validation_of_fixed_filter"
    assert "not optimized" in res["leakage_policy"]
