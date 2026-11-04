"""Shared deterministic execution-cost model for the product backtest and
paper forward-test engines (MASTER-RADAR directive, Waves 5+6).

Scope and honesty:
- Bar-based simulation ONLY. Nothing here is real-tick execution; every fill
  produced by this module is a bar-based approximation under an explicit
  ``fill_policy``. Callers must label results accordingly (NEVER
  "real-tick"/"live").
- Deterministic and side-effect free: no I/O, no network, no clock reads,
  no RNG. Same inputs -> byte-identical outputs.
- Pure contract module shared by ``backtest_product`` (Wave 5) and
  ``forward_test_paper`` (Wave 6) so both engines apply IDENTICAL fee /
  spread / slippage / latency / lot arithmetic for a given config.

Bar contract (shared with the whole product engine layer):
- A bar is a ``Mapping`` with keys ``ts`` (int epoch seconds, ascending,
  unique), ``o`` ``h`` ``l`` ``c`` ``v`` (finite floats, ``v`` >= 0).
- Validation lives in :func:`validate_bars` (fail-closed on any violation).
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_FLOOR
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "EXECUTION_MODEL_VERSION",
    "BAR_KEYS",
    "ExecutionModelConfig",
    "FillSide",
    "FillResult",
    "validate_bars",
    "bar_ts",
    "apply_spread_slippage",
    "apply_latency",
    "round_to_lot",
    "notional_of",
    "margin_ok",
    "volume_capped_quantity",
    "simulate_fill",
    "cost_breakdown",
]

EXECUTION_MODEL_VERSION = "1.0.0"

BAR_KEYS = ("ts", "o", "h", "l", "c", "v")

FillSide = Literal["buy", "sell"]


class ExecutionModelConfig(BaseModel):
    """Explicit, documented execution assumptions (directive §D2).

    Every field has a deterministic, unit-documented meaning. Defaults are
    the zero-friction model; real-world values must be supplied explicitly by
    the caller and are echoed into every report for reproducibility.
    """

    model_config = ConfigDict(frozen=True)

    initial_capital: float = Field(default=100_000.0, gt=0)
    commission_pct: float = Field(default=0.0, ge=0, description="percent of notional, per side")
    spread_pct: float = Field(default=0.0, ge=0, description="half-spread as percent of mid (applied symmetric)")
    slippage_pct: float = Field(default=0.0, ge=0, description="adverse slippage percent applied after spread")
    latency_bars: int = Field(default=0, ge=0, le=1000, description="bars between signal and execution")
    lot_size: float = Field(default=1.0, gt=0, description="minimum tradable increment in units")
    min_lot: float = Field(default=1.0, ge=0, description="minimum order size in units (0 = fractional allowed)")
    min_notional: float = Field(default=0.0, ge=0)
    leverage: float = Field(default=1.0, ge=1.0, le=1000.0)
    allow_short: bool = False
    volume_cap_pct: float = Field(default=1.0, gt=0, le=1.0, description="max fraction of bar volume takable")
    currency_multiplier: float = Field(default=1.0, gt=0, description="quote->account currency conversion")
    fill_policy: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] = "NEXT_BAR_OPEN"
    intrabar_tp_sl: bool = False

    @property
    def execution_model_version(self) -> str:
        return EXECUTION_MODEL_VERSION


class FillResult(BaseModel):
    """One simulated fill. ``filled=False`` always carries a reason."""

    model_config = ConfigDict(frozen=True)

    filled: bool
    side: FillSide
    signal_index: int
    execution_index: int
    raw_price: float
    fill_price: float
    quantity: float = 0.0
    refusal_reason: str | None = None
    latency_bars: int = 0
    volume_cap_applied: bool = False
    lot_rounded: bool = False


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def validate_bars(bars: Sequence[Mapping[str, Any]]) -> None:
    """Fail-closed bar validation: keys, finiteness, ordering, uniqueness.

    Raises ``ValueError`` with a precise machine-readable message. Used by
    both engines; stale/missing data refusal is the caller's policy decision,
    but structurally invalid data is ALWAYS refused here (directive §D3).
    """
    if not isinstance(bars, (list, tuple)):
        raise ValueError("bars_must_be_sequence")
    prev_ts: int | None = None
    for i, bar in enumerate(bars):
        try:
            missing = [k for k in BAR_KEYS if k not in bar]
        except TypeError:
            raise ValueError(f"bar[{i}]_not_a_mapping") from None
        if missing:
            raise ValueError(f"bar[{i}]_missing_keys:{','.join(missing)}")
        if not _finite(bar["ts"]) or int(bar["ts"]) != bar["ts"]:
            raise ValueError(f"bar[{i}]_ts_must_be_int_epoch_seconds")
        ts = int(bar["ts"])
        for k in ("o", "h", "l", "c", "v"):
            if not _finite(bar[k]):
                raise ValueError(f"bar[{i}]_{k}_not_finite")
        if float(bar["v"]) < 0:
            raise ValueError(f"bar[{i}]_volume_negative")
        for k in ("o", "h", "l", "c"):
            if float(bar[k]) <= 0:
                raise ValueError(f"bar[{i}]_{k}_must_be_positive")
        hi, lo = float(bar["h"]), float(bar["l"])
        if hi < lo:
            raise ValueError(f"bar[{i}]_high_below_low")
        if float(bar["o"]) > hi or float(bar["o"]) < lo or float(bar["c"]) > hi or float(bar["c"]) < lo:
            raise ValueError(f"bar[{i}]_ohlc_inconsistent")
        if prev_ts is not None and ts <= prev_ts:
            raise ValueError(f"bar[{i}]_ts_not_strictly_ascending")
        prev_ts = ts


def bar_ts(bar: Mapping[str, Any]) -> int:
    return int(bar["ts"])


def apply_spread_slippage(price: float, side: FillSide, cfg: ExecutionModelConfig) -> float:
    """Deterministic adverse-fill arithmetic (percent-based, symmetric spread).

    buy  -> pay the ask side:  price * (1 + spread/2) * (1 + slippage)
    sell -> hit the bid side:  price * (1 - spread/2) * (1 - slippage)
    """
    s = cfg.spread_pct / 100.0
    sl = cfg.slippage_pct / 100.0
    if side == "buy":
        return price * (1.0 + s / 2.0) * (1.0 + sl)
    return price * (1.0 - s / 2.0) * (1.0 - sl)


def apply_latency(signal_index: int, cfg: ExecutionModelConfig, bars_count: int) -> int:
    """Execution index for a signal first knowable at ``signal_index`` bar close.

    Structural no-look-ahead: ``NEXT_BAR_OPEN`` adds exactly one bar on top of
    the configured latency, so the fill bar is ALWAYS strictly after the
    signal bar. ``SAME_BAR_CLOSE`` keeps ``signal_index + latency_bars`` and is
    an explicit approximation that callers must label as such.
    """
    extra = 1 if cfg.fill_policy == "NEXT_BAR_OPEN" else 0
    return max(signal_index + cfg.latency_bars + extra, 0)


def round_to_lot(quantity: float, cfg: ExecutionModelConfig) -> tuple[float, bool]:
    """Floor quantity to the lot grid; returns (quantity, was_rounded)."""
    if cfg.lot_size <= 0:
        return quantity, False
    lots = (Decimal(str(quantity)) / Decimal(str(cfg.lot_size))).to_integral_value(rounding=ROUND_FLOOR)
    q = float(lots) * cfg.lot_size
    return q, abs(q - quantity) > 1e-12


def notional_of(price: float, quantity: float, cfg: ExecutionModelConfig) -> float:
    return price * quantity * cfg.currency_multiplier


def margin_ok(price: float, quantity: float, cfg: ExecutionModelConfig, free_equity: float) -> bool:
    return notional_of(price, quantity, cfg) / cfg.leverage <= free_equity + 1e-9


def volume_capped_quantity(price: float, desired_qty: float, bar: Mapping[str, Any], cfg: ExecutionModelConfig) -> tuple[float, bool]:
    """Cap the fill at ``volume_cap_pct`` of the bar volume (liquidity guard).

    Units assumption: bar ``v`` is in the same unit as quantity (shares/lots
    base units). Callers whose data differs must set volume_cap_pct=1.0 and
    document the choice.
    """
    if price <= 0:
        return 0.0, False
    max_qty = float(bar["v"]) * cfg.volume_cap_pct
    if desired_qty <= max_qty:
        return desired_qty, False
    return max_qty, True


def simulate_fill(
    *,
    bars: Sequence[Mapping[str, Any]],
    signal_index: int,
    side: FillSide,
    desired_quantity: float,
    cfg: ExecutionModelConfig,
    free_equity: float,
    current_position: float = 0.0,
) -> FillResult:
    """Deterministic single-fill simulation shared by both engines.

    Pipeline (documented order): latency -> source price (policy) -> spread +
    slippage -> liquidity cap -> lot rounding -> min-lot / min-notional /
    margin / short constraints. First refusal wins; refusals are reasons,
    never silent drops.
    """
    if signal_index < 0 or signal_index >= len(bars):
        return FillResult(filled=False, side=side, signal_index=signal_index, execution_index=signal_index,
                          raw_price=0.0, fill_price=0.0, refusal_reason="signal_index_out_of_range")
    exec_index = apply_latency(signal_index, cfg, len(bars))
    if exec_index >= len(bars):
        return FillResult(filled=False, side=side, signal_index=signal_index, execution_index=exec_index,
                          raw_price=0.0, fill_price=0.0, latency_bars=cfg.latency_bars,
                          refusal_reason="execution_index_beyond_data")
    src_bar = bars[exec_index]
    raw = float(src_bar["o"]) if cfg.fill_policy == "NEXT_BAR_OPEN" else float(src_bar["c"])
    price = apply_spread_slippage(raw, side, cfg)

    capped, cap_applied = volume_capped_quantity(price, desired_quantity, src_bar, cfg)
    qty, lot_rounded = round_to_lot(capped, cfg)

    if qty < cfg.min_lot:
        return FillResult(filled=False, side=side, signal_index=signal_index, execution_index=exec_index,
                          raw_price=raw, fill_price=price, latency_bars=cfg.latency_bars,
                          volume_cap_applied=cap_applied, refusal_reason="below_min_lot")
    if notional_of(price, qty, cfg) < cfg.min_notional:
        return FillResult(filled=False, side=side, signal_index=signal_index, execution_index=exec_index,
                          raw_price=raw, fill_price=price, latency_bars=cfg.latency_bars,
                          volume_cap_applied=cap_applied, lot_rounded=lot_rounded,
                          refusal_reason="below_min_notional")
    projected = current_position + qty if side == "buy" else current_position - qty
    if projected < 0 and not cfg.allow_short:
        short_extra = -min(projected, 0.0) + min(current_position, 0.0)
        if short_extra > 1e-12:
            return FillResult(filled=False, side=side, signal_index=signal_index, execution_index=exec_index,
                              raw_price=raw, fill_price=price, latency_bars=cfg.latency_bars,
                              volume_cap_applied=cap_applied, lot_rounded=lot_rounded,
                              refusal_reason="short_not_allowed")
    if not margin_ok(price, qty, cfg, free_equity):
        return FillResult(filled=False, side=side, signal_index=signal_index, execution_index=exec_index,
                          raw_price=raw, fill_price=price, latency_bars=cfg.latency_bars,
                          volume_cap_applied=cap_applied, lot_rounded=lot_rounded,
                          refusal_reason="margin_insufficient")
    return FillResult(filled=True, side=side, signal_index=signal_index, execution_index=exec_index,
                      raw_price=raw, fill_price=price, quantity=qty, latency_bars=cfg.latency_bars,
                      volume_cap_applied=cap_applied, lot_rounded=lot_rounded)


def cost_breakdown(notional: float, cfg: ExecutionModelConfig) -> dict[str, float]:
    """Explicit fee decomposition for one fill (percent -> absolute)."""
    commission = notional * cfg.commission_pct / 100.0
    half_spread_cash = notional * (cfg.spread_pct / 100.0) / 2.0
    slippage_cash = notional * (cfg.slippage_pct / 100.0)
    return {
        "commission": commission,
        "spread_cost": half_spread_cash,
        "slippage_cost": slippage_cash,
        "total": commission + half_spread_cash + slippage_cash,
    }
