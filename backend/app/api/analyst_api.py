"""analyst_api.py — MASTER-RADAR directive §F API surface
(prefix /api/v10/analyst, additive to the v10 family).

Evidence-grounded, DETERMINISTIC symbol analysis (no LLM call; the LLM
narration seam is owner-gated and disconnected). Input series are the
seeded SYNTHETIC candles:

- daily: seeded 1D series (SYNTHETIC, source SEEDED_CANDLES)
- weekly: resampled from the seeded daily series via timeframe_spec with an
  explicit RESAMPLED label (never claimed native)
- hourly: NOT loaded by this endpoint (honest MISSING entry)

Fundamentals / sector / strategy-signal contexts are passed as explicitly
UNAVAILABLE (fail-closed honesty) until their own admission decisions exist.

Every claim in the report carries full provenance (source class, timestamp,
freshness, timeframe, trust class, evidence ref, confidence policy); the
report self-scans for forbidden claim classes (guarantees / target prices).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.data.seeded_candles import candles_for
from app.engines.symbol_analyst import (
    AnalystInput,
    FundamentalsSection,
    SeriesInput,
    StrategySignalContext,
    TrustClass,
    analyze_symbol,
)
from app.domain.timeframe_spec import (
    STANDARD_TIMEFRAMES,
    aggregate_bars,
    assert_aggregation_legal,
)
from app.services.market_service import market_service

router = APIRouter(prefix="/api/v10/analyst")


def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust": market_service.data_trust_context(),
        "trust_level": market_service.trust_level(),
    }


_TF_BY_CODE = {tf.code: tf for tf in STANDARD_TIMEFRAMES}


def _seeded_series_input(
    symbol: str,
    timeframe_query: str,
    count: int,
    end_bar_index: Optional[int],
    *,
    timeframe_label: str,
    source_class: str,
) -> SeriesInput:
    seeded = candles_for(symbol, timeframe_query, count, end_bar_index=end_bar_index)
    bars = [
        {
            "ts": int(row["time"]),
            "o": float(row["open"]),
            "h": float(row["high"]),
            "l": float(row["low"]),
            "c": float(row["close"]),
            "v": float(row["volume"]),
        }
        for row in seeded
    ]
    return SeriesInput(
        bars=bars,
        timeframe=timeframe_label,
        trust_class=TrustClass.SYNTHETIC,
        source_class=source_class,
    )


@router.get("/{symbol}")
async def analyze(
    symbol: str,
    count_daily: int = Query(default=150, ge=50, le=1000),
    end_bar_index: Optional[int] = Query(default=None, ge=0),
) -> Dict[str, Any]:
    daily = _seeded_series_input(
        symbol, "1D", count_daily, end_bar_index,
        timeframe_label="1d",
        source_class="SEEDED_CANDLES",
    )
    weekly = SeriesInput(bars=[], timeframe="1w", trust_class=TrustClass.MISSING, source_class="NONE")
    if len(daily.bars) >= 30:
        src_tf = _TF_BY_CODE["1d"]
        dst_tf = _TF_BY_CODE["1w"]
        assert_aggregation_legal(src_tf, dst_tf)
        weekly_bars = aggregate_bars(daily.bars, src_tf, dst_tf)
        weekly = SeriesInput(
            bars=weekly_bars,
            timeframe="1w",
            trust_class=TrustClass.SYNTHETIC,
            source_class="RESAMPLED_FROM_1D_SYNTHETIC",
        )
    inp = AnalystInput(
        symbol=symbol,
        as_of_ts=daily.bars[-1]["ts"] if daily.bars else 0,
        daily=daily,
        weekly=weekly,
        # hourly intentionally NOT loaded here: honest MISSING, never silently
        # resampled upward (lower-timeframe-from-higher is forbidden).
        hourly=SeriesInput(bars=[], timeframe="1h", trust_class=TrustClass.MISSING, source_class="NONE"),
        fundamentals=FundamentalsSection(
            available=False,
            rows=[],
            unavailable_reason="fundamental_dossier not admitted for synthetic-universe symbols in this release",
        ),
        strategy_signals=StrategySignalContext(
            available=False,
            signals=[],
            unavailable_reason="no strategy-signal source is wired into the analyst path (owner-gated runtime integration pending)",
        ),
    )
    try:
        report = analyze_symbol(inp)
    except ValueError as exc:
        raise HTTPException(422, {"error": "ANALYST_INPUT_REJECTED", "message": str(exc)}) from exc
    payload = report.model_dump(mode="json")
    payload["data_class"] = "SYNTHETIC_SEEDED"
    payload["weekly_resample_label"] = "RESAMPLED"
    payload["synthetic_note"] = (
        "تحلیل فقط روی داده سینتتیک seed شده است؛ هیچ پیش‌بینی تضمینی یا هدف قیمتی تولید نمی‌شود"
    )
    payload["trust_envelope"] = _trust_envelope()
    return payload
