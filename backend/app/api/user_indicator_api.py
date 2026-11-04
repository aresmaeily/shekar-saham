"""user_indicator_api.py — MASTER-RADAR directive §B4 (WAVE-B) API surface
(prefix /api/v10/user-indicators, additive to the v10 family).

Governed lifecycle + deterministic computation for UIDL-1 user indicators:

- POST /api/v10/user-indicators/validate         — compile-only dry run
- POST /api/v10/user-indicators                  — install (disabled, checksummed)
- GET  /api/v10/user-indicators                  — installed list + manifest digest
- GET  /api/v10/user-indicators/export           — versioned package document
- POST /api/v10/user-indicators/import           — verify + re-compile + install
- GET  /api/v10/user-indicators/{id}             — one record incl. source
- DELETE /api/v10/user-indicators/{id}           — uninstall
- POST /api/v10/user-indicators/{id}/enable      — explicit enable (fail-closed default off)
- POST /api/v10/user-indicators/{id}/disable     — disable
- GET  /api/v10/user-indicators/{id}/compute     — deterministic series over seeded bars

Honesty contract (mirrors indicator_api):
- The ONLY execution path for a user indicator is the audited RSL-1
  interpreter (app.engines.strategy_dsl) — user DSL text is never executed
  as Python/JS; there is no eval/exec/compile and no dynamic import.
- computed values are SYNTHETIC-class (seeded generator); the trust envelope
  is re-read from market_service exactly like every v10 router.
- every response declares warm-up, missing-data behaviour, repaint and the
  enforced no-look-ahead rule; install/import never enables by default.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from app.data.seeded_candles import candles_for
from app.engines.strategy_dsl.errors import DSLError
from app.engines.strategy_dsl.indicator_program import (
    UIDL_VERSION,
    compile_indicator_source,
    evaluate_indicator,
    validation_advisories,
)
from app.engines.strategy_dsl.runtime import SeriesContext
from app.engines.user_indicator_store import (
    UIDL_PACKAGE_VERSION,
    USER_DSL_PREFIX,
    UserIndicatorStore,
)
from app.services.market_service import market_service

router = APIRouter(prefix="/api/v10/user-indicators")

_store = UserIndicatorStore()


def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust": market_service.data_trust_context(),
        "trust_level": market_service.trust_level(),
    }


_SYNTHETIC_NOTE = "محاسبه اندیکاتور کاربر روی داده سینتتیک seed شده انجام می‌شود؛ زنده نیست"

_TIMEFRAMES = ("1m", "5m", "15m", "1h", "1D")


class ValidateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    source: str = Field(min_length=1, max_length=8192)


class InstallRequest(BaseModel):
    model_config = {"extra": "forbid"}

    source: str = Field(min_length=1, max_length=8192)
    version: str = Field(default="1.0.0", max_length=16)
    name_fa: str = Field(default="", max_length=120)
    author: str = Field(default="operator", max_length=64)


def _dsl_http_error(exc: DSLError) -> HTTPException:
    """Map a typed DSL error onto a 422 with machine-readable fields."""
    return HTTPException(
        422,
        {
            "error": "DSL_COMPILE_FAILED",
            "code": str(getattr(exc, "code", "")),
            "kind": type(exc).__name__,
            "message": str(exc)[:300],
            "line": getattr(exc, "line", None),
            "col": getattr(exc, "col", None),
            "dsl_version": UIDL_VERSION,
        },
    )


def _compile_or_422(source: str):
    try:
        return compile_indicator_source(source)
    except DSLError as exc:
        raise _dsl_http_error(exc) from exc


def _record_public(rec) -> Dict[str, Any]:
    return {
        "id": rec.id,
        "name": rec.name,
        "name_fa": rec.name_fa,
        "author": rec.author,
        "dsl_version": rec.dsl_version,
        "version": rec.version,
        "inputs": dict(rec.inputs),
        "plots": [dict(p) for p in rec.plots],
        "warmup_bars": rec.warmup_bars,
        "declarations": dict(rec.declarations),
        "checksum": rec.checksum,
        "enabled": rec.enabled,
        "source_digest": rec.source_digest,
    }


@router.post("/validate")
async def validate_source(body: ValidateRequest) -> Dict[str, Any]:
    """Compile-only dry run: no install, no state change, full diagnostics."""
    prog = _compile_or_422(body.source)
    return {
        "ok": True,
        "dsl_version": UIDL_VERSION,
        "name": prog.name,
        "inputs": dict(prog.inputs),
        "plots": [
            {"name": p.name, "warmup_bars": p.warmup_bars} for p in prog.plots
        ],
        "warmup_bars": prog.warmup_bars,
        "source_digest": prog.source_digest,
        "advisories": validation_advisories(prog),
        "declarations": {
            "repaint": "NONE_DECLARED",
            "lookahead_declared": False,
            "missing_data": "WARMUP_ZERO",
        },
        "trust_envelope": _trust_envelope(),
    }


@router.post("")
async def install_indicator(body: InstallRequest) -> Dict[str, Any]:
    report = _store.install(
        body.source,
        version=body.version,
        name_fa=body.name_fa,
        author=body.author,
        allow_upgrade=False,
    )
    if not report.ok:
        rej = report.rejected[0] if report.rejected else None
        status = 409 if (rej is not None and rej.code == "DUPLICATE_ID") else 422
        raise HTTPException(
            status,
            {
                "error": rej.code if rej is not None else "INSTALL_FAILED",
                "detail": rej.detail if rej is not None else "",
                "manifest_digest": report.manifest_digest,
            },
        )
    return {
        "ok": True,
        "id": report.id,
        "checksum": report.checksum,
        "manifest_digest": report.manifest_digest,
        "enabled": False,
        "dsl_version": UIDL_VERSION,
        "trust_envelope": _trust_envelope(),
    }


@router.get("")
async def list_installed() -> Dict[str, Any]:
    recs = [_record_public(_store.get_record(rid)) for rid in _store.installed_ids()]
    return {
        "dsl_version": UIDL_VERSION,
        "package_version": UIDL_PACKAGE_VERSION,
        "count": len(recs),
        "indicators": recs,
        "manifest_digest": _store.manifest_digest(),
        "trust_envelope": _trust_envelope(),
    }


@router.get("/export")
async def export_package() -> Dict[str, Any]:
    """Versioned package document (caller persists it; server state is memory-only)."""
    return {
        "package": _store.export_package(),
        "manifest_digest": _store.manifest_digest(),
        "trust_envelope": _trust_envelope(),
    }


@router.post("/import")
async def import_package(
    body: Dict[str, Any] = Body(...),
    allow_upgrade: bool = Query(default=False),
) -> Dict[str, Any]:
    report = _store.import_package(body, allow_upgrade=allow_upgrade)
    if not report.ok:
        raise HTTPException(
            422,
            {
                "error": "IMPORT_REJECTED",
                "installed": report.installed,
                "rejected": [r.model_dump() for r in report.rejected],
                "manifest_digest": report.manifest_digest,
            },
        )
    return {
        "ok": True,
        "installed": report.installed,
        "manifest_digest": report.manifest_digest,
        "trust_envelope": _trust_envelope(),
    }


@router.get("/{indicator_id}")
async def record_detail(indicator_id: str) -> Dict[str, Any]:
    rec = _store.get_record(indicator_id)
    if rec is None:
        raise HTTPException(404, {"error": "user_indicator_not_found", "id": indicator_id})
    payload = _record_public(rec)
    payload["source"] = rec.source
    payload["trust_envelope"] = _trust_envelope()
    return payload


@router.delete("/{indicator_id}")
async def uninstall_indicator(indicator_id: str) -> Dict[str, Any]:
    result = _store.uninstall(indicator_id)
    if not result.ok:
        raise HTTPException(
            404, {"error": result.code, "id": indicator_id, "detail": result.detail}
        )
    return {
        "ok": True,
        "id": indicator_id,
        "code": result.code,
        "manifest_digest": result.manifest_digest,
        "trust_envelope": _trust_envelope(),
    }


@router.post("/{indicator_id}/enable")
async def enable_indicator(indicator_id: str) -> Dict[str, Any]:
    result = _store.set_enabled(indicator_id, True)
    if not result.ok:
        raise HTTPException(404, {"error": result.code, "id": indicator_id})
    return {
        "ok": True,
        "id": indicator_id,
        "code": result.code,
        "manifest_digest": result.manifest_digest,
        "trust_envelope": _trust_envelope(),
    }


@router.post("/{indicator_id}/disable")
async def disable_indicator(indicator_id: str) -> Dict[str, Any]:
    result = _store.set_enabled(indicator_id, False)
    if not result.ok:
        raise HTTPException(404, {"error": result.code, "id": indicator_id})
    return {
        "ok": True,
        "id": indicator_id,
        "code": result.code,
        "manifest_digest": result.manifest_digest,
        "trust_envelope": _trust_envelope(),
    }


def _coerce_inputs(rec, params_raw: Optional[str]) -> Dict[str, float]:
    """Validate caller INPUT overrides against the compiled defaults."""
    if not params_raw:
        return {}
    try:
        given = json.loads(params_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, {"error": "PARAMS_NOT_JSON", "message": str(exc)}) from exc
    if not isinstance(given, dict):
        raise HTTPException(422, {"error": "PARAMS_MUST_BE_OBJECT"})
    out: Dict[str, float] = {}
    for k, v in given.items():
        if k not in rec.inputs:
            raise HTTPException(
                422,
                {"error": "UNKNOWN_PARAM", "param": k, "declared": sorted(rec.inputs)},
            )
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise HTTPException(422, {"error": "PARAM_TYPE", "param": k, "expected": "number"})
        fv = float(v)
        if not math.isfinite(fv):
            raise HTTPException(422, {"error": "PARAM_NOT_FINITE", "param": k})
        out[k] = fv
    return out


@router.get("/{indicator_id}/compute")
async def compute_user_indicator(
    indicator_id: str,
    symbol: str = Query(default="FOLAD", max_length=32),
    timeframe: str = Query(default="1D", pattern="^(1m|5m|15m|1h|1D)$"),
    count: int = Query(default=200, ge=50, le=1000),
    end_bar_index: Optional[int] = Query(default=None, ge=0),
    params: Optional[str] = Query(default=None, description="JSON object of INPUT overrides"),
) -> Dict[str, Any]:
    rec = _store.get_record(indicator_id)
    if rec is None:
        raise HTTPException(404, {"error": "user_indicator_not_found", "id": indicator_id})
    overrides = _coerce_inputs(rec, params)

    # Recompile from the record's stored source (fail closed: never evaluate
    # anything that the CURRENT UIDL-1 rules cannot compile).
    try:
        prog = compile_indicator_source(rec.source)
    except DSLError as exc:
        raise HTTPException(
            422,
            {
                "error": "STORED_SOURCE_NO_LONGER_COMPILES",
                "code": str(getattr(exc, "code", "")),
                "message": str(exc)[:200],
            },
        ) from exc

    seeded = candles_for(symbol, timeframe, count, end_bar_index=end_bar_index)
    ctx = SeriesContext(
        open=[float(b["open"]) for b in seeded],
        high=[float(b["high"]) for b in seeded],
        low=[float(b["low"]) for b in seeded],
        close=[float(b["close"]) for b in seeded],
        volume=[float(b["volume"]) for b in seeded],
    )
    try:
        evaluation = evaluate_indicator(prog, ctx, inputs=overrides)
    except DSLError as exc:
        raise _dsl_http_error(exc) from exc

    plots_out: Dict[str, List[Dict[str, Any]]] = {}
    for name, values in evaluation.plots.items():
        plots_out[name] = [
            {"time": seeded[i]["time"], "value": values[i]} for i in range(len(seeded))
        ]

    warmup = evaluation.warmup_bars
    return {
        "id": rec.id,
        "name": rec.name,
        "dsl_version": UIDL_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": len(seeded),
        "warmup_bars": warmup,
        "valid_from_index": warmup,  # bars < this index are warm-up zeros (documented)
        "params_used": dict(evaluation.inputs),
        "plots": plots_out,
        "output_digest": evaluation.digest,
        "declarations": {
            "warmup_bars": warmup,
            "missing_data": "WARMUP_ZERO",
            "repaint": "NONE_DECLARED",
            "lookahead_declared": False,
            "lookahead_enforced": "ref offsets >= 0 (compile-time refusal)",
        },
        "data_class": "SYNTHETIC_SEEDED",
        "synthetic_note": _SYNTHETIC_NOTE,
        "trust_envelope": _trust_envelope(),
    }


__all__ = ["router", "_store", "USER_DSL_PREFIX"]
