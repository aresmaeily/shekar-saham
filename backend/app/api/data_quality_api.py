"""data_quality_api.py — MASTER-RADAR WAVE-2 (2026-11-04) §G Data Quality
Center surface (prefix /api/v10/dataquality, additive to the v10 family).

STRICTLY ADDITIVE next to /api/v10/chartpro, /api/v10/analytics and
/api/v10/strategylab. Every record served here is a declared
SYNTHETIC_FIXTURE from app.data.fixture_universes resolved through the
instrument-master allowlist; the mechanical audit/coverage math lives in
app.engines.universe_data_quality (reused via
app.services.data_quality_service — no audit math in this router).

Honesty envelope on every endpoint:
- trust envelope re-read from market_service exactly like every other v10
  router (assert-style; never a hardcoded trust label);
- a locally-defined _SYNTHETIC_NOTE in the same wording pattern as
  strategy_lab.py (deliberately NOT imported from there — private constant);
- the canonical non-live provenance block from the glue service.

Gates (unchanged): no network, no file IO, no provider calls, no wall-clock
staleness reference (the audit as_of is the fixture's injected declared-at
instant).
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services import data_quality_service as dq
from app.services.market_service import market_service

router = APIRouter(prefix="/api/v10/dataquality")


def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust": market_service.data_trust_context(),
        "trust_level": market_service.trust_level(),
    }


# Same wording pattern as strategy_lab._SYNTHETIC_NOTE, defined locally on
# purpose (the strategy-lab constant is private to that module).
_SYNTHETIC_NOTE = (
    "تمام رکوردهای این مسیر روی فیکسچر سینتتیک seed شده ساخته می‌شوند؛ "
    "زنده نیست و مبنای تصمیم واقعی قرار نگیرد"
)


@router.get("/markets")
async def list_markets() -> Dict[str, Any]:
    """Per-market coverage summary over the deterministic fixture universes."""
    return {
        "markets": dq.market_summaries(),
        "default_universe_markets": dq.default_universe_markets(),
        "provenance": dq.provenance(),
        "trust_envelope": _trust_envelope(),
        "synthetic_note": _SYNTHETIC_NOTE,
    }


@router.get("/markets/{market}/coverage")
async def market_coverage(market: str) -> Dict[str, Any]:
    """Full per-symbol audit rows + the market-level CoverageReport row."""
    try:
        payload = dq.market_coverage(market)
    except KeyError as exc:
        raise HTTPException(
            422,
            {
                "error": "UNKNOWN_MARKET",
                "message_en": f"unknown market {market!r}",
                "message_fa": "بازار ناشناخته است؛ فهرست بازارهای معتبر در valid_markets آمده است",
                "valid_markets": dq.valid_markets(),
            },
        ) from exc
    payload["trust_envelope"] = _trust_envelope()
    payload["synthetic_note"] = _SYNTHETIC_NOTE
    return payload


@router.get("/symbols/{instrument_id}/audit")
async def symbol_audit(instrument_id: str) -> Dict[str, Any]:
    """Mechanical audit of one fixture symbol at the documented 200-bar depth
    (duplicates / out-of-order / invalid-ohlcv / missing intervals / stale
    flags) with the instrument master's TrustClass and the trust envelope."""
    try:
        payload = dq.audit_symbol(instrument_id)
    except KeyError as exc:
        raise HTTPException(
            404,
            {
                "error": "UNKNOWN_INSTRUMENT",
                "message_en": f"unknown instrument_id {instrument_id!r} in the fixture universes",
                "message_fa": "نماد در فیکسچر یونیورس‌ها یافت نشد",
            },
        ) from exc
    payload["trust_envelope"] = _trust_envelope()
    payload["synthetic_note"] = _SYNTHETIC_NOTE
    return payload
