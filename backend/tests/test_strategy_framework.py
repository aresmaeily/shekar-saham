import pytest

from app.domain.strategy import (
    FilterStrategy,
    StrategyContext,
    StrategyMetadata,
    StrategyRegistry,
    StrategySignalSide,
)
from app.engines.filter_dsl import FilterError


def test_filter_strategy_validate_contract():
    strategy = FilterStrategy(
        StrategyMetadata(id="smart-entry", name="Smart Entry"),
        "buy_power > 1.5 and volume_ratio > 2",
        side=StrategySignalSide.BUY,
    )
    res = strategy.validate()
    assert res["ok"] is True
    assert res["strategy"]["id"] == "smart-entry"
    assert res["filter"]["fields"] == ["buy_power", "volume_ratio"]


def test_filter_strategy_generates_signals_without_backtest():
    strategy = FilterStrategy(
        StrategyMetadata(id="smart-entry", name="Smart Entry"),
        "close > sma(20) and rsi(14) < 35",
        side=StrategySignalSide.BUY,
    )
    ctx = StrategyContext(
        rows=[
            {"symbol": "فملی", "pl": 120, "sma_20": 100, "rsi_14": 30, "entry_score": 80, "reasons": ["test"]},
            {"symbol": "فولاد", "pl": 90, "sma_20": 100, "rsi_14": 40, "entry_score": 20},
        ],
        data_trust={"state": "mock", "trust_level": "synthetic"},
    )
    signals = strategy.generate(ctx)
    assert len(signals) == 1
    assert signals[0].symbol == "فملی"
    assert signals[0].side == StrategySignalSide.BUY
    assert signals[0].score == 80
    assert signals[0].payload["data_trust"]["state"] == "mock"


def test_filter_strategy_rejects_unsafe_filter():
    strategy = FilterStrategy(StrategyMetadata(id="bad", name="Bad"), "__import__('os')")
    with pytest.raises(FilterError):
        strategy.validate()


def test_strategy_registry_contract():
    registry = StrategyRegistry()
    strategy = FilterStrategy(StrategyMetadata(id="watch", name="Watch"), "buy_power > 1")
    registry.register(strategy)
    assert registry.get("watch") is strategy
    assert registry.list_metadata()[0]["id"] == "watch"
