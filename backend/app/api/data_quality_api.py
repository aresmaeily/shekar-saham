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


# ---------------------------------------------------------------------------
# MASTER-RADAR WAVE-E (2026-11-05): DECLARED session/calendar model for the
# supported markets (MR-B1-01 residual). Pure repository declarations with a
# calendar-level DECLARED trust marker; sourced authoritative holiday tables
# stay owner-gated (R-3/R-7, Two-Key Rule). No network, no file IO, and NO
# server wall clock: /session-state REQUIRES the caller to state as_of_utc.
# See app/domain/market_calendar.py for the pinned honesty contract.
# ---------------------------------------------------------------------------


@router.get("/calendars")
async def declared_calendars() -> Dict[str, Any]:
    """All declared calendars with their session windows, fixed-date holiday
    rules, declared_version and the honesty block (owner-gated sourced tables;
    disclosed scope gaps)."""
    from app.domain import declared_calendars as mc

    payload = mc.list_calendars()
    payload["trust_envelope"] = _trust_envelope()
    payload["synthetic_note"] = _SYNTHETIC_NOTE
    return payload


@router.get("/calendars/{calendar_id}")
async def declared_calendar_detail(calendar_id: str) -> Dict[str, Any]:
    """One declared calendar in full detail. Unknown calendar_id -> 404 (never
    guessed, never defaulted)."""
    from app.domain import declared_calendars as mc

    try:
        payload = mc.get_calendar(calendar_id)
    except mc.CalendarNotDeclared as exc:
        raise HTTPException(
            404,
            {
                "error": "CALENDAR_NOT_DECLARED",
                "message_en": f"no declared calendar {calendar_id!r}; the declared set is exact",
                "message_fa": "تقویم اعلامی با این شناسه وجود ندارد؛ مجموعه اعلامی دقیق است",
                "declared_calendar_ids": sorted(mc.list_calendars()["count"] and [
                    c["calendar_id"] for c in mc.list_calendars()["calendars"]
                ]),
            },
        ) from exc
    payload["trust_envelope"] = _trust_envelope()
    payload["synthetic_note"] = _SYNTHETIC_NOTE
    return payload


@router.get("/calendars/{calendar_id}/session-state")
async def declared_calendar_session_state(calendar_id: str, as_of_utc: str) -> Dict[str, Any]:
    """Deterministic declared session state at the CALLER-SUPPLIED instant.

    ``as_of_utc`` is REQUIRED (query parameter, ISO-8601 with an explicit UTC
    offset) — the server never reads a wall clock for calendar decisions.
    Malformed instants -> 422; unknown calendar_id -> 404."""
    from datetime import datetime as _dt

    from app.domain import declared_calendars as mc

    try:
        moment = _dt.fromisoformat(as_of_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            422,
            {
                "error": "INVALID_AS_OF",
                "message_en": "as_of_utc must be an ISO-8601 instant with an explicit UTC offset, e.g. 2026-11-05T09:00:00Z (a '+' in a query string must be percent-encoded as %2B)",
                "message_fa": "as_of_utc باید یک لحظه ISO-8601 با آفست صریح UTC باشد؛ علامت + در کوئری باید %2B کدگذاری شود",
            },
        ) from exc
    try:
        payload = mc.session_state(calendar_id, moment)
    except mc.CalendarNotDeclared as exc:
        raise HTTPException(
            404,
            {
                "error": "CALENDAR_NOT_DECLARED",
                "message_en": f"no declared calendar {calendar_id!r}",
                "message_fa": "تقویم اعلامی با این شناسه وجود ندارد",
            },
        ) from exc
    except mc.InvalidAsOf as exc:
        raise HTTPException(422, {"error": "INVALID_AS_OF", "message_en": str(exc)}) from exc
    payload["trust_envelope"] = _trust_envelope()
    payload["synthetic_note"] = _SYNTHETIC_NOTE
    return payload
