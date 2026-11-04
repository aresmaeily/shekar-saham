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

MASTER-RADAR W3-3AB (additive): POST /api/v10/chartpro/{symbol}/derived —
derived chart constructions (RENKO / RANGE / KAGI / PNF / LINEBREAK) built
from the SAME deterministic seeded OHLCV by engines.derived_charts (registry
DERIVED_TYPES; no construction math is reimplemented here). Fail-closed
params validation per type (honest 422 with English + Persian detail
fields), the same _TIMEFRAME_PATTERN grid (manual re-check — it is a body
field), the same trust envelope, and a dedicated honest ``labeling`` object.
The constructions are derived visual-analytic shapes computed from the
seeded bars: NOT real market bars, NOT a new/independent data source, and
always deterministic under identical arguments.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.data.mock_market import generate_mock_market
from app.data.seeded_candles import candles_for
from app.engines.chart_builder import calculate_ema, calculate_ma, calculate_rsi
from app.engines.derived_charts import DERIVED_TYPES  # W3-3AB (additive)
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


# ===========================================================================
# MASTER-RADAR W3-3AB (additive): POST /api/v10/chartpro/{symbol}/derived
#
# Derived chart constructions (RENKO / RANGE / KAGI / PNF / LINEBREAK) over
# the SAME deterministic seeded OHLCV as the series endpoints. The
# constructions live in app.engines.derived_charts (single source of truth —
# DERIVED_TYPES registry; no math reimplemented here). This surface only
# validates the request fail-closed and wraps the engine output in the
# standard trust envelope + honest labeling. The outputs are derived
# visual-analytic constructions: not real market bars, not an independent
# data source, deterministic under identical arguments.
# ===========================================================================
class DerivedBody(BaseModel):
    """Body for the derived-construction endpoint (W3-3AB).

    ``type`` is pinned to the registry's construction set (Literal; the
    registry contract is cross-checked by tests/test_chart_pro_derived_api.py).
    ``timeframe`` is a body field, so the GET endpoints' Query-pattern grid is
    re-checked manually with re + _TIMEFRAME_PATTERN (-> 422 on mismatch).
    Unknown extra body fields are ignored (pydantic default, documented).
    """

    type: Literal["RENKO", "RANGE", "KAGI", "PNF", "LINEBREAK"]
    timeframe: str = "1m"
    limit: int = 300
    params: Dict[str, Any] = {}


def _derived_422(en: str, fa: str) -> HTTPException:
    """Honest bilingual refusal: English + Persian note fields in detail."""
    return HTTPException(422, {"en": en, "fa": fa})


def _derived_positive_number(raw: Any, key: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise _derived_422(
            f"param {key!r} must be a number, got {type(raw).__name__}",
            f"پارامتر {key!r} باید عدد باشد؛ مقدار ارسالی از نوع {type(raw).__name__} است",
        )
    num = float(raw)
    if not math.isfinite(num) or num <= 0:
        raise _derived_422(
            f"param {key!r} must be a finite positive number, got {raw!r}",
            f"پارامتر {key!r} باید عددی متناهی و مثبت باشد؛ مقدار ارسالی {raw!r} است",
        )
    return num


def _derived_bounded_int(raw: Any, key: str, lo: int, hi: int) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise _derived_422(
            f"param {key!r} must be an integer in [{lo}, {hi}], got {raw!r}",
            f"پارامتر {key!r} باید عدد صحیح در بازهٔ [{lo}، {hi}] باشد؛ مقدار ارسالی {raw!r} است",
        )
    if not lo <= raw <= hi:
        raise _derived_422(
            f"param {key!r} must be an integer in [{lo}, {hi}], got {raw!r}",
            f"پارامتر {key!r} باید عدد صحیح در بازهٔ [{lo}، {hi}] باشد؛ مقدار ارسالی {raw!r} است",
        )
    return raw


def _canonical_derived_params(derived_type: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Per-type params canonicalization, fail-closed (W3-3AB).

    Unknown keys are IGNORED (documented forward compatibility); known keys
    with wrong types or out-of-range values are refused with an honest 422.
    Returns exactly the canonical params the engine function is called with
    (also echoed verbatim in the response ``params`` field).
    """
    if not isinstance(raw, dict):  # belt-and-braces: pydantic already enforces
        raise _derived_422(
            "params must be a JSON object",
            "پارامترها باید یک شیء JSON باشند",
        )
    if derived_type == "RENKO":
        has_brick = "brick_size" in raw
        has_atr = "atr_period" in raw
        if has_brick and has_atr:
            raise _derived_422(
                "RENKO accepts exactly one of brick_size / atr_period (both given)",
                "رنکو فقط یکی از دو پارامتر brick_size یا atr_period را می‌پذیرد؛ هر دو ارسال شده است",
            )
        if not has_brick and not has_atr:
            return {"atr_period": 14}  # documented default
        if has_brick:
            return {"brick_size": _derived_positive_number(raw["brick_size"], "brick_size")}
        return {"atr_period": _derived_bounded_int(raw["atr_period"], "atr_period", 2, 200)}
    if derived_type == "RANGE":
        if "range_size" not in raw:
            raise _derived_422(
                "RANGE requires a positive range_size param (missing)",
                "ساخت RANGE به پارامتر مثبت range_size نیاز دارد؛ این پارامتر ارسال نشده است",
            )
        return {"range_size": _derived_positive_number(raw["range_size"], "range_size")}
    if derived_type == "KAGI":
        if "reversal_pct" in raw:
            return {"reversal_pct": _derived_positive_number(raw["reversal_pct"], "reversal_pct")}
        return {"reversal_pct": 3.0}
    if derived_type == "PNF":
        box = (
            _derived_positive_number(raw["box_size"], "box_size")
            if "box_size" in raw
            else 1.0
        )
        boxes = (
            _derived_bounded_int(raw["reversal_boxes"], "reversal_boxes", 1, 20)
            if "reversal_boxes" in raw
            else 3
        )
        return {"box_size": box, "reversal_boxes": boxes}
    if derived_type == "LINEBREAK":
        if "lines" in raw:
            return {"lines": _derived_bounded_int(raw["lines"], "lines", 2, 10)}
        return {"lines": 3}
    # unreachable: the body Literal + registry check above pin the type set
    raise _derived_422(
        f"unknown derived type {derived_type!r}",
        f"نوع ساخت مشتق {derived_type!r} شناخته‌شده نیست",
    )


def _derived_labeling(derived_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Honest labeling echo for a derived construction (W3-3AB).

    ``bar_class`` is REUSED verbatim from the canonical ``_labeling_echo()``
    logic — never re-asserted or hardcoded here. Construction summaries state
    the exact arguments so identical outputs stay reproducible by inspection.
    """
    bar_class = _labeling_echo()["bar_class"]  # canonical derivation, reused
    if derived_type == "RENKO":
        if "brick_size" in params:
            construction_en = (
                f"Renko bricks from the seeded bars; brick_size={params['brick_size']}"
            )
            construction_fa = (
                f"کندل‌های رنکو روی کندل‌های سینتتیک seed-شده؛ اندازهٔ آجر {params['brick_size']}"
            )
        else:
            construction_en = (
                "Renko bricks from the seeded bars; brick = Wilder ATR"
                f"({params['atr_period']}) at the last warm-up-complete bar"
            )
            construction_fa = (
                "کندل‌های رنکو روی کندل‌های سینتتیک seed-شده؛ آجر برابر ATR وایلدری دورهٔ "
                f"{params['atr_period']} در آخرین ستون کامل گرم‌شدن"
            )
    elif derived_type == "RANGE":
        construction_en = (
            f"Range bars from the seeded bars; range_size={params['range_size']}"
        )
        construction_fa = (
            f"کندل‌های رنج روی کندل‌های سینتتیک seed-شده؛ اندازهٔ رنج {params['range_size']}"
        )
    elif derived_type == "KAGI":
        construction_en = (
            f"Kagi turn points from the seeded bars; reversal_pct={params['reversal_pct']}"
        )
        construction_fa = (
            f"نقاط چرخش کاگی روی کندل‌های سینتتیک seed-شده؛ درصد بازگشت {params['reversal_pct']}"
        )
    elif derived_type == "PNF":
        construction_en = (
            "Point-and-Figure columns from the seeded bars; "
            f"box_size={params['box_size']}, reversal_boxes={params['reversal_boxes']}"
        )
        construction_fa = (
            "ستون‌های نقطه‌وخط (PnF) روی کندل‌های سینتتیک seed-شده؛ اندازهٔ جعبهٔ "
            f"{params['box_size']} و بازگشت {params['reversal_boxes']} جعبه‌ای"
        )
    else:  # LINEBREAK
        construction_en = f"Line-break bars from the seeded bars; lines={params['lines']}"
        construction_fa = (
            f"کندل‌های خط‌شکن روی کندل‌های سینتتیک seed-شده؛ تعداد خط {params['lines']}"
        )
    return {
        "bar_class": bar_class,
        "method": "DERIVED_" + derived_type,
        "construction_en": construction_en,
        "construction_fa": construction_fa,
        "note_en": (
            "Derived visual-analytic construction computed from the "
            "deterministic seeded synthetic bars; not real market bars; not an "
            "independent data source; identical arguments always reproduce "
            "identical output."
        ),
        "note_fa": (
            "ساختار تحلیل-دیداری مشتق‌شده از کندل‌های سینتتیک seed-شدهٔ قطعی است؛ "
            "کندل بازار واقعی نیست؛ منبع دادهٔ مستقلی نیست؛ با آرگومان‌های یکسان "
            "همیشه خروجی یکسان تولید می‌شود."
        ),
    }


@router.post("/chartpro/{symbol}/derived")
async def chartpro_derived(symbol: str, body: DerivedBody) -> Dict[str, Any]:
    """Derived chart construction over the seeded OHLCV (W3-3AB).

    Fail-closed flow: body ``type`` is pinned by the Literal AND checked
    against the DERIVED_TYPES registry; ``timeframe`` is re-checked manually
    against the same _TIMEFRAME_PATTERN grid as the GET endpoints (body field
    -> 422 on mismatch); per-type params are canonicalized fail-closed
    (unknown keys ignored, wrong types/values -> honest 422); engine
    ValueError -> honest 422. Unknown symbols still resolve to the stable
    seeded pseudo-price series (synthetic contract, same as the GET series).
    """
    if not re.fullmatch(_TIMEFRAME_PATTERN, body.timeframe):
        raise _derived_422(
            f"invalid timeframe {body.timeframe!r} (allowed: 1m|5m|15m|1h|1D)",
            f"بازهٔ زمانی {body.timeframe!r} نامعتبر است؛ مقادیر مجاز: 1m، 5m، 15m، 1h، 1D",
        )
    if body.type not in DERIVED_TYPES:  # registry is the single source of the type set
        raise _derived_422(
            f"unknown derived type {body.type!r} (allowed: {sorted(DERIVED_TYPES)})",
            f"نوع ساخت مشتق {body.type!r} شناخته‌شده نیست؛ انواع مجاز: {sorted(DERIVED_TYPES)}",
        )
    params = _canonical_derived_params(body.type, body.params)
    ohlcv = _load_ohlcv(symbol, body.timeframe, body.limit)
    try:
        units = DERIVED_TYPES[body.type]["fn"](ohlcv, **params)
    except ValueError as exc:
        raise _derived_422(
            f"derived construction refused: {exc}",
            f"موتور ساخت مشتق این درخواست را رد کرد: {exc}",
        ) from exc
    payload_units: Dict[str, Any] = (
        {"points": units} if body.type == "KAGI" else {"bars": units}
    )
    return {
        "symbol": symbol,
        "timeframe": body.timeframe,
        "type": body.type,
        "params": params,
        "source_count": len(ohlcv),
        "derived_count": len(units),
        **payload_units,
        "labeling": _derived_labeling(body.type, params),
        **_trust_envelope(),
        "source": "synthetic-seeded",
        "note": "SYNTHETIC_OR_PAPER deterministic derived construction",
    }
