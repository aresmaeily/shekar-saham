"""Shared execution-model contract tests (MASTER-RADAR Wave 5+6 glue).

The execution model is the single arithmetic point shared by the product
backtest engine and the paper forward-test runtime; these tests pin its
documented behavior independently of both consumers.
"""

from __future__ import annotations

import pytest

from app.engines.execution_model import (
    EXECUTION_MODEL_VERSION,
    ExecutionModelConfig,
    apply_latency,
    apply_spread_slippage,
    cost_breakdown,
    round_to_lot,
    simulate_fill,
    validate_bars,
    volume_capped_quantity,
)


def bar(ts, o, h, l, c, v=1000.0):
    return {"ts": ts, "o": o, "h": h, "l": l, "c": c, "v": v}


def series(n=10, base=100.0):
    return [bar(i * 3600, base + i, base + 1 + i, base - 1 + i, base + 0.5 + i) for i in range(n)]


def test_version_constant_present():
    assert EXECUTION_MODEL_VERSION == "1.0.0"


def test_spread_slippage_buy_side_adverse():
    cfg = ExecutionModelConfig(spread_pct=0.2, slippage_pct=0.1)
    p = apply_spread_slippage(100.0, "buy", cfg)
    assert p == pytest.approx(100.0 * (1 + 0.002 / 2) * (1 + 0.001), rel=1e-12)
    assert p > 100.0


def test_spread_slippage_sell_side_adverse():
    cfg = ExecutionModelConfig(spread_pct=0.2, slippage_pct=0.1)
    p = apply_spread_slippage(100.0, "sell", cfg)
    assert p == pytest.approx(100.0 * (1 - 0.002 / 2) * (1 - 0.001), rel=1e-12)
    assert p < 100.0


def test_next_bar_open_is_structurally_after_signal():
    cfg = ExecutionModelConfig(fill_policy="NEXT_BAR_OPEN", latency_bars=0)
    assert apply_latency(5, cfg, 10) == 6


def test_same_bar_close_keeps_index():
    cfg = ExecutionModelConfig(fill_policy="SAME_BAR_CLOSE", latency_bars=0)
    assert apply_latency(5, cfg, 10) == 5


def test_latency_adds_bars():
    cfg = ExecutionModelConfig(latency_bars=3)
    assert apply_latency(5, cfg, 20) == 9


def test_fill_uses_next_bar_open_price():
    cfg = ExecutionModelConfig(fill_policy="NEXT_BAR_OPEN")
    bars = series()
    r = simulate_fill(bars=bars, signal_index=3, side="buy", desired_quantity=10, cfg=cfg, free_equity=1e9)
    assert r.filled and r.execution_index == 4
    assert r.raw_price == pytest.approx(bars[4]["o"])


def test_fill_same_bar_close_price_labeled_policy():
    cfg = ExecutionModelConfig(fill_policy="SAME_BAR_CLOSE")
    bars = series()
    r = simulate_fill(bars=bars, signal_index=3, side="buy", desired_quantity=10, cfg=cfg, free_equity=1e9)
    assert r.filled and r.execution_index == 3
    assert r.raw_price == pytest.approx(bars[3]["c"])


def test_fill_refusal_beyond_data():
    cfg = ExecutionModelConfig(fill_policy="NEXT_BAR_OPEN", latency_bars=2)
    bars = series(5)
    r = simulate_fill(bars=bars, signal_index=4, side="buy", desired_quantity=1, cfg=cfg, free_equity=1e9)
    assert not r.filled and r.refusal_reason == "execution_index_beyond_data"


def test_fill_refusal_short_not_allowed():
    cfg = ExecutionModelConfig(allow_short=False)
    bars = series()
    r = simulate_fill(bars=bars, signal_index=1, side="sell", desired_quantity=5, cfg=cfg,
                      free_equity=1e9, current_position=0.0)
    assert not r.filled and r.refusal_reason == "short_not_allowed"


def test_fill_margin_refusal():
    cfg = ExecutionModelConfig(initial_capital=100.0, leverage=1.0)
    bars = series()
    r = simulate_fill(bars=bars, signal_index=1, side="buy", desired_quantity=1000, cfg=cfg, free_equity=50.0)
    assert not r.filled and r.refusal_reason == "margin_insufficient"


def test_volume_cap_applied():
    cfg = ExecutionModelConfig(volume_cap_pct=0.5)
    bars = [bar(0, 100, 101, 99, 100, v=100.0), bar(3600, 100, 101, 99, 100, v=100.0)]
    r = simulate_fill(bars=bars, signal_index=0, side="buy", desired_quantity=1000, cfg=cfg,
                      free_equity=1e9, current_position=0.0)
    assert r.filled
    assert r.quantity == pytest.approx(50.0)
    assert r.volume_cap_applied is True


def test_lot_rounding_floors():
    cfg = ExecutionModelConfig(lot_size=10.0)
    q, rounded = round_to_lot(95.0, cfg)
    assert q == 90.0 and rounded is True
    q2, rounded2 = round_to_lot(90.0, cfg)
    assert q2 == 90.0 and rounded2 is False


def test_min_lot_refusal():
    cfg = ExecutionModelConfig(min_lot=10.0)
    bars = series(3)
    r = simulate_fill(bars=bars, signal_index=0, side="buy", desired_quantity=5, cfg=cfg, free_equity=1e9)
    assert not r.filled and r.refusal_reason == "below_min_lot"


def test_cost_breakdown_arithmetic():
    cfg = ExecutionModelConfig(commission_pct=1.0, spread_pct=0.2, slippage_pct=0.1)
    c = cost_breakdown(1000.0, cfg)
    assert c["commission"] == pytest.approx(10.0)
    assert c["spread_cost"] == pytest.approx(1.0)
    assert c["slippage_cost"] == pytest.approx(1.0)
    assert c["total"] == pytest.approx(12.0)


def test_validate_bars_rejects_disorder_and_dupes():
    good = series(3)
    with pytest.raises(ValueError):
        validate_bars([good[0], good[0]])
    with pytest.raises(ValueError):
        validate_bars([good[1], good[0]])
    bad = dict(good[0])
    bad["h"] = 1.0
    bad["l"] = 2.0
    with pytest.raises(ValueError):
        validate_bars([bad])
    nonfinite = dict(good[0])
    nonfinite["c"] = float("inf")
    with pytest.raises(ValueError):
        validate_bars([nonfinite])
    missing = {"ts": 0, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0}
    with pytest.raises(ValueError):
        validate_bars([missing])


def test_validate_bars_accepts_valid_series():
    validate_bars(series(5))  # must not raise


def test_zero_cost_config_is_exact_price():
    cfg = ExecutionModelConfig()
    assert apply_spread_slippage(123.45, "buy", cfg) == pytest.approx(123.45)


def test_volume_cap_zero_price_guard():
    cfg = ExecutionModelConfig(volume_cap_pct=0.5)
    q, capped = volume_capped_quantity(0.0, 10.0, bar(0, 100, 101, 99, 100, 100.0), cfg)
    assert q == 0.0 and capped is False
