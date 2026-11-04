"""indicator_api.py — MASTER-RADAR directive §B4 API surface
(prefix /api/v10/indicators, additive to the v10 family).

Indicator Manager catalog + deterministic computation over the seeded
SYNTHETIC candles:

- GET  /api/v10/indicators                — catalog list (metadata only)
- GET  /api/v10/indicators/{id}           — full spec incl. math definition
- GET  /api/v10/indicators/{id}/compute   — computed series over seeded bars

Honesty contract:
- The catalog declares, per indicator: mathematical definition, warm-up,
  missing-data behavior, repaint declaration, look-ahead declaration,
  permissions, and an INDEPENDENT reference implementation pointer.
- computed values are SYNTHETIC-class (seeded generator); the trust envelope
  is re-read from market_service exactly like every v10 router.
- Installation/lifecycle state (enable/disable/import) is metadata-only and
  lives in app.engines.indicator_manager; THIS router never executes any
  downloaded or user code — computation resolves ONLY the two audited
  implementations named by the catalog (engine + independent reference).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.data.seeded_candles import candles_for
from app.engines.indicator_catalog import (
    catalog_version,
    get_spec,
    list_specs,
    validate_catalog,
)
from app.engines.indicator_manager import IndicatorManager
from app.services.market_service import market_service

router = APIRouter(prefix="/api/v10/indicators")

_manager = IndicatorManager()


def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust": market_service.data_trust_context(),
        "trust_level": market_service.trust_level(),
    }


_SYNTHETIC_NOTE = (
    "محاسبه اندیکاتور روی داده سینتتیک seed شده انجام می‌شود؛ زنده نیست"
)


def _spec_summary(spec) -> Dict[str, Any]:
    return {
        "id": spec.id,
        "name_en": spec.name_en,
        "name_fa": spec.name_fa,
        "category": spec.category.value if hasattr(spec.category, "value") else str(spec.category),
        "version": spec.version,
        "author": spec.author,
        "permissions": list(spec.permissions),
        "inputs": [p.model_dump() for p in spec.inputs],
        "warmup_bars": spec.warmup_bars,
        "missing_data": spec.missing_data.value if hasattr(spec.missing_data, "value") else str(spec.missing_data),
        "repaint": spec.repaint.value if hasattr(spec.repaint, "value") else str(spec.repaint),
        "lookahead_declared": spec.lookahead_declared,
        "series_inputs": list(spec.series_inputs),
        "requires_volume": spec.requires_volume,
        "dual_implementation": bool(getattr(spec, "dual_implementation", False)),
    }


@router.get("")
async def catalog(category: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    problems = validate_catalog()
    specs = list_specs(category=category)
    return {
        "catalog_version": catalog_version(),
        "count": len(specs),
        "catalog_problems": problems,
        "indicators": [_spec_summary(s) for s in specs],
        "manager_state_digest": _manager.manifest_digest(),
        "trust_envelope": _trust_envelope(),
    }


@router.get("/{indicator_id}")
async def spec_detail(indicator_id: str) -> Dict[str, Any]:
    spec = get_spec(indicator_id)
    if spec is None:
        raise HTTPException(404, {"error": "indicator_not_found", "id": indicator_id})
    payload = _spec_summary(spec)
    payload["math_definition"] = spec.math_definition
    payload["engine_ref"] = spec.engine_ref
    payload["reference_ref"] = spec.reference_ref
    payload["custom_inputs_doc"] = getattr(spec, "custom_inputs_doc", None)
    payload["trust_envelope"] = _trust_envelope()
    return payload


def _coerce_params(spec, raw: Optional[str]) -> Dict[str, Any]:
    """Validate caller params against the spec's typed param ranges."""
    params: Dict[str, Any] = {p.name: p.default for p in spec.inputs}
    if raw:
        try:
            given = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, {"error": "PARAMS_NOT_JSON", "message": str(exc)}) from exc
        if not isinstance(given, dict):
            raise HTTPException(422, {"error": "PARAMS_MUST_BE_OBJECT"})
        for k, v in given.items():
            p = next((pp for pp in spec.inputs if pp.name == k), None)
            if p is None:
                raise HTTPException(422, {"error": "UNKNOWN_PARAM", "param": k})
            if p.type == "int":
                if not isinstance(v, int) or isinstance(v, bool):
                    raise HTTPException(422, {"error": "PARAM_TYPE", "param": k, "expected": "int"})
            else:
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise HTTPException(422, {"error": "PARAM_TYPE", "param": k, "expected": "float"})
                v = float(v)
            if v < p.minimum or v > p.maximum:
                raise HTTPException(
                    422,
                    {"error": "PARAM_RANGE", "param": k, "min": p.minimum, "max": p.maximum, "got": v},
                )
            params[k] = v
    return params


def _row_value(item: Dict[str, Any]) -> Any:
    """Engine series rows use several value-key conventions across engines."""
    for key in ("value", "k", "d", "adx", "plus_di", "minus_di", "atr", "cci", "obv", "williams", "vwap"):
        if key in item:
            return item[key]
    return None


def _compute_series(spec, bars_seeded: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Resolve the audited implementation named by the catalog and normalize
    its output shape to {series_name: [{time, value}, ...]}."""
    from app.engines.indicator_catalog import resolve_dotted

    if spec.engine_ref == spec.reference_ref:  # dual-implementation entries
        fn = resolve_dotted(spec.reference_ref)
        closes = [float(b["close"]) for b in bars_seeded]
        if spec.id == "builtin.new_high_rate":
            vals = fn(closes, int(params.get("lookback", 20)))
        else:
            vals = fn(closes, int(params["period"]))
        return {"value": [{"time": bars_seeded[i]["time"], "value": vals[i]} for i in range(len(bars_seeded))]}

    fn = resolve_dotted(spec.engine_ref)
    # Coerce declared-int params to int (defaults may be stored as floats).
    call_params: Dict[str, Any] = {}
    type_by_name = {p.name: p.type for p in spec.inputs}
    for k, v in params.items():
        call_params[k] = int(v) if type_by_name.get(k) == "int" else v
    result = fn(bars_seeded, **call_params)
    if isinstance(result, dict):
        normalized: Dict[str, List[Dict[str, Any]]] = {}
        for k, series in result.items():
            rows = []
            for item in series:
                if isinstance(item, dict):
                    rows.append({"time": item.get("time"), "value": _row_value(item)})
                else:
                    rows.append({"time": None, "value": item})
            normalized[k] = rows
        return normalized
    # list[dict] single-series engines (atr, cci, obv, williams, vwap)
    rows = []
    for item in result:
        if isinstance(item, dict):
            rows.append({"time": item.get("time"), "value": _row_value(item)})
        else:
            rows.append({"time": None, "value": item})
    return {"value": rows}


@router.get("/{indicator_id}/compute")
async def compute_indicator(
    indicator_id: str,
    symbol: str = Query(default="FOLAD", max_length=32),
    timeframe: str = Query(default="1D", pattern="^(1m|5m|15m|1h|1D)$"),
    count: int = Query(default=200, ge=50, le=1000),
    end_bar_index: Optional[int] = Query(default=None, ge=0),
    params: Optional[str] = Query(default=None, description="JSON object of indicator params"),
) -> Dict[str, Any]:
    spec = get_spec(indicator_id)
    if spec is None:
        raise HTTPException(404, {"error": "indicator_not_found", "id": indicator_id})
    if spec.custom_inputs_doc and not spec.series_inputs:
        raise HTTPException(
            422,
            {"error": "NOT_COMPUTABLE_FROM_OHLCV", "detail": spec.custom_inputs_doc},
        )
    coerced = _coerce_params(spec, params)
    seeded = candles_for(symbol, timeframe, count, end_bar_index=end_bar_index)
    try:
        series = _compute_series(spec, seeded, coerced)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, {"error": "COMPUTE_FAILED", "message": str(exc)}) from exc
    return {
        "id": spec.id,
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": len(seeded),
        "params": coerced,
        "series": series,
        "declarations": {
            "warmup_bars": spec.warmup_bars,
            "missing_data": spec.missing_data.value if hasattr(spec.missing_data, "value") else str(spec.missing_data),
            "repaint": spec.repaint.value if hasattr(spec.repaint, "value") else str(spec.repaint),
            "lookahead_declared": spec.lookahead_declared,
        },
        "data_class": "SYNTHETIC_SEEDED",
        "synthetic_note": _SYNTHETIC_NOTE,
        "trust_envelope": _trust_envelope(),
    }
