"""chart_pro.py - v1.0 chart-pro - WS-10 CH-1/CH-2 backend chart API

Deterministic seeded chart endpoints (SYNTHETIC class only) on the v1.0
prefix, styled after the v0.8 chart router: same Query-pattern timeframe
validation, same trust-badge envelope discipline.

Endpoints:
- GET /api/v10/chartpro/universe           — seeded TSE universe board
- GET /api/v10/chartpro/{symbol}           — deterministic seeded OHLCV
- GET /api/v10/chartpro/{symbol}/indicators — same series + MA/EMA/RSI/MACD/Bollinger

Indicator math is NEVER reimplemented here: engines.chart_builder /
engines.indicators remain the single source of truth; this module only aligns
their outputs onto the ohlcv time grid, padding the warm-up head with
value=None (lightweight-charts skips nulls).

MASTER-RADAR WAVE-2 (2026-11-04), additive only: the series responses
(/chartpro/{symbol} and /chartpro/{symbol}/indicators) carry an additive
``labeling`` echo object whose bar class is derived from the canonical
market_service trust context (no hardcoded trust word anywhere; the notes
state the deterministic seeded synthetic nature of the bars).
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.data.mock_market import generate_mock_market
from app.data.seeded_candles import candles_for
from app.engines.chart_builder import calculate_ema, calculate_ma, calculate_rsi
from app.engines.indicators import bollinger, macd
from app.services.market_service import market_service

router = APIRouter(prefix="/api/v10")

_TIMEFRAME_PATTERN = "^(1m|5m|15m|1h|1D)$"  # same grid as chart.py v0.8


# ASSERT-STYLE: data_trust / trust_level MUST come from market_service.
# Hardcoding "live" (or any trust label) in this module is forbidden — these
# series are SYNTHETIC-class and the trust fields must stay the canonical
# market_service verdict for the current runtime.
def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust": market_service.data_trust_context(),
        "trust_level": market_service.trust_level(),
    }


def _clamp_limit(limit: int) -> int:
    """Clamp requested bars onto the generator's 50..1000 contract."""
    return max(50, min(1000, int(limit)))


# MASTER-RADAR WAVE-2 (2026-11-04): additive ``labeling`` echo on the series
# responses. The bar class is DERIVED from the canonical market_service trust
# context, never asserted as a hardcoded trust word: the canonical context has
# no live-verification boundary (``is_live`` can never be minted True there,
# see app.core.config.build_data_trust_context), so seeded-generator series are
# labeled SYNTHETIC; if a future context ever verified its source, the echo
# would surface that state's verdict instead of a synthetic claim.
def _labeling_echo() -> Dict[str, Any]:
    ctx = market_service.data_trust_context()
    if ctx.get("is_live") or ctx.get("live_verified"):
        bar_class = str(ctx.get("state") or "UNKNOWN").upper()
    else:
        bar_class = "SYNTHETIC"
    return {
        "bar_class": bar_class,
        "method": "NATIVE",
        "trust_state": ctx.get("state"),
        "note_en": (
            "Deterministic seeded synthetic bars (NATIVE labeling): identical "
            "arguments always reproduce identical bars; not real market data "
            "and never a basis for real decisions."
        ),
        "note_fa": (
            "کندل‌ها قطعی و seed-شدهٔ سینتتیک هستند (برچسب‌گذاری بومی bars)؛ "
            "با آرگومان‌های یکسان همیشه خروجی یکسان تولید می‌شود و دادهٔ بازار "
            "واقعی نیست و مبنای تصمیم واقعی قرار نمی‌گیرد."
        ),
    }


def _load_ohlcv(symbol: str, timeframe: str, limit: int) -> List[Dict]:
    try:
        return candles_for(symbol, timeframe, _clamp_limit(limit))
    except ValueError as exc:  # belt-and-braces: pattern above already 422s
        raise HTTPException(422, str(exc)) from exc


def _align_series(series: List[Dict[str, Any]], ohlcv: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project an engine series onto the ohlcv time grid.

    Where the indicator window is not yet full the engine simply emits no
    point; the gap is padded with value=None (lightweight-charts skips nulls).
    """
    by_time = {point["time"]: point.get("value") for point in series}
    return [{"time": candle["time"], "value": by_time.get(candle["time"])} for candle in ohlcv]


def _build_indicators(ohlcv: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reuse engines indicator math — no local reimplementation."""
    macd_out = macd(ohlcv)
    boll_out = bollinger(ohlcv)
    return {
        "ma20": _align_series(calculate_ma(ohlcv, 20), ohlcv),
        "ma50": _align_series(calculate_ma(ohlcv, 50), ohlcv),
        "ema20": _align_series(calculate_ema(ohlcv, 20), ohlcv),
        "rsi14": _align_series(calculate_rsi(ohlcv, 14), ohlcv),
        "macd": {
            "macd": _align_series(macd_out["macd"], ohlcv),
            "signal": _align_series(macd_out["signal"], ohlcv),
            "hist": _align_series(macd_out["histogram"], ohlcv),
        },
        "bollinger": {
            "upper": _align_series(boll_out["upper"], ohlcv),
            "mid": _align_series(boll_out["basis"], ohlcv),
            "lower": _align_series(boll_out["lower"], ohlcv),
        },
    }


@router.get("/chartpro/universe")
async def chartpro_universe() -> Dict[str, Any]:
    """Seeded TSE universe board (SYNTHETIC — mock_market generator)."""
    rows = generate_mock_market()
    symbols = [
        {
            "l18": row.l18,
            "l30": row.l30,
            "sector": row.cs,
            "price": row.pl,
            "change_pct": float(getattr(row, "plp", 0.0) or 0.0),
        }
        for row in rows
    ]
    return {
        **_trust_envelope(),
        "source": "synthetic-seeded",
        "count": len(symbols),
        "symbols": symbols,
    }


@router.get("/chartpro/{symbol}")
async def chartpro_candles(
    symbol: str,
    timeframe: str = Query("1m", pattern=_TIMEFRAME_PATTERN),
    limit: int = Query(300, ge=1),
) -> Dict[str, Any]:
    """Deterministic seeded OHLCV — unknown symbols still resolve to a stable
    pseudo-price series (never 404; the series is synthetic by contract)."""
    ohlcv = _load_ohlcv(symbol, timeframe, limit)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        **_trust_envelope(),
        "source": "synthetic-seeded",
        "count": len(ohlcv),
        "ohlcv": ohlcv,
        "last_price": ohlcv[-1]["close"] if ohlcv else 0.0,
        "labeling": _labeling_echo(),  # MASTER-RADAR WAVE-2: additive echo
        "note": "SYNTHETIC_OR_PAPER deterministic seeded series",
    }


@router.get("/chartpro/{symbol}/indicators")
async def chartpro_indicators(
    symbol: str,
    timeframe: str = Query("1m", pattern=_TIMEFRAME_PATTERN),
    limit: int = Query(300, ge=1),
) -> Dict[str, Any]:
    """Seeded OHLCV + overlay/oscillator indicator series (engines-reused)."""
    ohlcv = _load_ohlcv(symbol, timeframe, limit)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        **_trust_envelope(),
        "source": "synthetic-seeded",
        "count": len(ohlcv),
        "ohlcv": ohlcv,
        "last_price": ohlcv[-1]["close"] if ohlcv else 0.0,
        "indicators": _build_indicators(ohlcv),
        "labeling": _labeling_echo(),  # MASTER-RADAR WAVE-2: additive echo
        "note": "SYNTHETIC_OR_PAPER deterministic seeded series",
    }
