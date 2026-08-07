from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.runtime_settings import (
    get_thresholds_public,
    reset_thresholds,
    update_thresholds,
)
from app.data.store import store
from app.services.market_service import market_service

router = APIRouter(prefix="/api")


class ThresholdUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class PortfolioAdd(BaseModel):
    symbol: str
    note: str = ""


class PortfolioAlertFlags(BaseModel):
    alert_entry: bool = True
    alert_exit: bool = True


@router.get("/health")
async def health(request: Request = None) -> dict[str, Any]:
    s = get_settings()
    # در حالت خصوصی، برای بازدیدکننده بدون توکن فقط حداقل اطلاعات را بده
    # (جلوگیری از نشت آمار بازار/اسنپ‌شات به غریبه‌ها)
    authorized = True
    if request and (s.auth_required or s.private_mode):
        from app.core.security import authorize_request
        key = request.headers.get("X-API-Key")
        authz = request.headers.get("Authorization") or ""
        bearer = authz[7:] if authz.lower().startswith("bearer ") else None
        authorized = authorize_request(key, bearer)

    st = market_service.status()
    if not authorized:
        return {
            "ok": True,
            "auth_required": bool(s.auth_required),
            "private_mode": bool(s.private_mode),
            "private_ok": False,
            "source": st.get("source", "unknown"),
            "symbol_count": None,
            "store": {},
            "flow_meta": {},
        }

    out: dict[str, Any] = {
        "ok": True,
        **st,
        "trust_level": st.get("trust_level") or market_service.trust_level(),
        "auth_required": bool(s.auth_required),
        "private_mode": bool(s.private_mode),
        "private_ok": True,
    }
    return out


@router.get("/status")
async def status() -> dict[str, Any]:
    return market_service.status()


@router.post("/refresh")
async def refresh() -> dict[str, Any]:
    analysis = await market_service.refresh(force=True)
    return {
        "ok": True,
        "source": analysis.overview.source,
        "trust_level": market_service.trust_level(),
        "data_trust": market_service.data_trust_context(),
        "symbol_count": analysis.overview.symbol_count,
        "entry_alerts": analysis.overview.entry_alerts,
        "exit_alerts": analysis.overview.exit_alerts,
        "big_moves": len(market_service._last_big_moves),
    }


@router.get("/overview")
async def overview(force: bool = False) -> dict[str, Any]:
    analysis = await market_service.get_analysis(force=force)
    ov = analysis.overview.model_dump(mode="json")
    ov["big_moves"] = len(market_service._last_big_moves)
    ov["portfolio_count"] = len(store.portfolio_list())
    ov["trust_level"] = market_service.trust_level()
    ov["data_trust"] = market_service.data_trust_context()
    return ov


@router.get("/analyze")
async def analyze(
    force: bool = Query(False, description="اجبار به دریافت مجدد داده"),
    include_metrics: bool = Query(False),
) -> dict[str, Any]:
    analysis = await market_service.get_analysis(force=force)
    data = analysis.model_dump(mode="json")
    if not include_metrics:
        data.pop("all_metrics", None)
    data["big_moves_preview"] = market_service.get_big_moves(limit=10)
    data["tablocastic_preview"] = market_service.get_tablocastic(limit=10)
    data["store"] = store.snapshot_stats()
    data["trust_level"] = market_service.trust_level()
    data["data_trust"] = market_service.data_trust_context()
    data["flow_meta"] = market_service.status().get("flow_meta")
    data["confluence_summary"] = (market_service.get_confluence() or {}).get("summary")
    return data


@router.get("/signals/entry")
async def entry_signals(
    min_score: float = Query(0, ge=0, le=100),
    only_negative: bool = False,
    fundamental_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    analysis = await market_service.get_analysis()
    rows = analysis.entry_signals
    out = []
    for r in rows:
        if r.entry_score < min_score:
            continue
        if only_negative and r.plp > 0:
            continue
        if fundamental_only and "بنیادی‌خوب" not in r.tags:
            continue
        out.append(r.model_dump(mode="json"))
        if len(out) >= limit:
            break
    return out


@router.get("/signals/exit")
async def exit_signals(
    min_score: float = Query(0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    analysis = await market_service.get_analysis()
    return [
        r.model_dump(mode="json")
        for r in analysis.exit_signals
        if r.exit_score >= min_score
    ][:limit]


@router.get("/hot-money")
async def hot_money(tier: str = Query("hot", pattern="^(hot|plus|all)$")) -> list[dict[str, Any]]:
    analysis = await market_service.get_analysis()
    if tier == "hot":
        rows = analysis.hot_money
    elif tier == "plus":
        rows = analysis.hot_money_plus
    else:
        rows = sorted(analysis.hot_money + analysis.hot_money_plus, key=lambda x: x.score, reverse=True)
    return [r.model_dump(mode="json") for r in rows]


@router.get("/market-game")
async def market_game(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    analysis = await market_service.get_analysis()
    return [r.model_dump(mode="json") for r in analysis.market_game[:limit]]


@router.get("/industries")
async def industries() -> list[dict[str, Any]]:
    analysis = await market_service.get_analysis()
    return [r.model_dump(mode="json") for r in analysis.industries]


@router.get("/symbol/{l18}")
async def symbol_detail(l18: str) -> dict[str, Any]:
    data = market_service.get_symbol(l18)
    if not data:
        await market_service.get_analysis(force=False)
        data = market_service.get_symbol(l18)
    if not data:
        raise HTTPException(status_code=404, detail=f"نماد {l18} یافت نشد")
    return data


@router.get("/watchlist")
async def watchlist(limit: int = 50) -> list[dict[str, Any]]:
    analysis = await market_service.get_analysis()
    return [r.model_dump(mode="json") for r in analysis.watchlist[:limit]]


# ---------- فاز ۲ ----------

@router.get("/big-moves")
async def big_moves(
    window_sec: Optional[int] = Query(None, ge=60, le=7200),
    limit: int = Query(80, ge=1, le=300),
    side: Optional[str] = Query(None, pattern="^(inflow|outflow)$"),
) -> list[dict[str, Any]]:
    rows = market_service.get_big_moves(window_sec=window_sec, limit=limit * 2)
    if side:
        rows = [r for r in rows if r.get("side") == side]
    return rows[:limit]


@router.get("/tablocastic")
async def tablocastic(
    limit: int = Query(80, ge=1, le=300),
    min_quality: float = Query(0, ge=0, le=100),
    grade: Optional[str] = Query(None),
) -> list[dict[str, Any]]:
    rows = market_service.get_tablocastic(limit=limit * 2, min_quality=min_quality)
    if grade:
        g = grade.upper()
        rows = [r for r in rows if str(r.get("grade", "")).upper().startswith(g[:1])]
    return rows[:limit]


@router.get("/alerts")
async def alerts(
    side: Optional[str] = Query(None, pattern="^(entry|exit)$"),
    symbol: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return store.list_alerts(side=side, symbol=symbol, limit=limit)


@router.get("/portfolio")
async def portfolio_list() -> list[dict[str, Any]]:
    return market_service.portfolio_enriched()


@router.post("/portfolio")
async def portfolio_add(body: PortfolioAdd) -> dict[str, Any]:
    if not body.symbol.strip():
        raise HTTPException(400, "نماد خالی است")
    item = store.portfolio_add(body.symbol, body.note)
    return {"ok": True, "item": item, "portfolio": market_service.portfolio_enriched()}


@router.delete("/portfolio/{symbol}")
async def portfolio_delete(symbol: str) -> dict[str, Any]:
    ok = store.portfolio_remove(symbol)
    if not ok:
        raise HTTPException(404, "نماد در پورتفو نیست")
    return {"ok": True, "portfolio": market_service.portfolio_enriched()}


@router.patch("/portfolio/{symbol}/alerts")
async def portfolio_alerts(symbol: str, body: PortfolioAlertFlags) -> dict[str, Any]:
    store.portfolio_set_alerts(symbol, body.alert_entry, body.alert_exit)
    return {"ok": True, "portfolio": market_service.portfolio_enriched()}


@router.get("/config/thresholds")
async def thresholds_get() -> dict[str, Any]:
    return get_thresholds_public()


@router.put("/config/thresholds")
async def thresholds_put(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    payload = body.get("values") if isinstance(body.get("values"), dict) else body
    if not isinstance(payload, dict):
        raise HTTPException(400, "بدنه نامعتبر")
    return update_thresholds(payload)


@router.post("/config/thresholds/reset")
async def thresholds_reset() -> dict[str, Any]:
    return reset_thresholds()


@router.get("/history/{symbol}")
async def symbol_history(
    symbol: str,
    hours: float = Query(6, ge=0.5, le=72),
) -> list[dict[str, Any]]:
    import time as _t

    return store.get_ticks_since(_t.time() - hours * 3600, symbol=symbol.strip())


# ---------- فاز ۳ ----------

class FilterRunBody(BaseModel):
    expr: str = Field(..., max_length=2000)  # محدودیت طول برای جلوگیری از بازتاب ورودی عظیم در خطا
    limit: int = Field(100, ge=1, le=200)


class FilterSaveBody(BaseModel):
    name: str = Field(..., max_length=100)
    expr: str = Field(..., max_length=2000)
    id: Optional[int] = None


@router.get("/market-map")
async def market_map(
    size_by: str = Query("tval"),
    color_by: str = Query("plp"),
    min_tval: float = Query(0, ge=0),
) -> dict[str, Any]:
    await market_service.get_analysis(force=False)
    return market_service.get_market_map(size_by=size_by, color_by=color_by, min_tval=min_tval)


@router.get("/fundamentals")
async def fundamentals(
    limit: int = Query(80, ge=1, le=300),
    min_score: float = Query(0, ge=0, le=100),
) -> list[dict[str, Any]]:
    await market_service.get_analysis(force=False)
    return market_service.get_fundamentals(limit=limit, min_score=min_score)


@router.get("/fundamental/{symbol}")
async def fundamental_one(symbol: str) -> dict[str, Any]:
    await market_service.get_analysis(force=False)
    deep = market_service.get_deep_fundamental(symbol)
    if not deep:
        data = market_service.get_symbol(symbol)
        if not data or "fundamental" not in data:
            raise HTTPException(404, f"نماد {symbol} یافت نشد")
        return data["fundamental"]
    return deep


@router.get("/fundamentals/value")
async def fundamentals_value(
    limit: int = Query(40, ge=1, le=200),
    max_pe: float = Query(18, ge=0, le=100),
    min_score: float = Query(55, ge=0, le=100),
) -> dict[str, Any]:
    """جدول سهام پرپتانسیل/ارزنده بر اساس تحلیل ۵محوره + P/E."""
    await market_service.get_analysis(force=False)
    rows = market_service.get_value_stocks(
        limit=limit, max_pe=max_pe, min_value_score=min_score
    )
    return {
        "ok": True,
        "count": len(rows),
        "max_pe": max_pe,
        "min_value_score": min_score,
        "rows": rows,
        "scoring": {
            "pe": "۰–۳۰",
            "trend": "۰–۱۵",
            "profitability": "۰–۲۰",
            "liquidity_debt": "۰–۱۵",
            "cash_quality": "۰–۱۵",
            "audit": "۰–۵",
            "total": "۰–۱۰۰ (+تعدیل PEG)",
        },
    }


@router.get("/fundamental/{symbol}/deep")
async def fundamental_deep(symbol: str) -> dict[str, Any]:
    """گزارش کامل ۵بخشی بنیادی."""
    await market_service.get_analysis(force=False)
    deep = market_service.get_deep_fundamental(symbol)
    if not deep:
        raise HTTPException(404, f"نماد {symbol} یافت نشد")
    return deep


@router.post("/filter/run")
async def filter_run(body: FilterRunBody) -> dict[str, Any]:
    await market_service.get_analysis(force=False)
    result = market_service.run_user_filter(body.expr, limit=body.limit)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "خطای فیلتر")
    return result


@router.get("/filter/presets")
async def filter_presets() -> dict[str, Any]:
    from app.engines.filter_dsl import PRESETS, fields_help

    return {"presets": PRESETS, "fields": fields_help()}


@router.get("/filter/saved")
async def filter_saved_list() -> list[dict[str, Any]]:
    return store.filters_list()


@router.post("/filter/saved")
async def filter_saved_save(body: FilterSaveBody) -> dict[str, Any]:
    if not body.name.strip() or not body.expr.strip():
        raise HTTPException(400, "نام و عبارت الزامی است")
    # validate
    check = market_service.run_user_filter(body.expr, limit=1)
    if not check.get("ok"):
        raise HTTPException(400, check.get("error") or "عبارت نامعتبر")
    item = store.filter_save(body.name.strip(), body.expr.strip(), body.id)
    return {"ok": True, "item": item, "filters": store.filters_list()}


@router.delete("/filter/saved/{filter_id}")
async def filter_saved_delete(filter_id: int) -> dict[str, Any]:
    ok = store.filter_delete(filter_id)
    if not ok:
        raise HTTPException(404, "فیلتر یافت نشد")
    return {"ok": True, "filters": store.filters_list()}


@router.get("/trade-hot/{symbol}")
async def trade_hot(symbol: str) -> dict[str, Any]:
    await market_service.get_analysis(force=False)
    data = await market_service.get_trade_hot(symbol)
    if not data:
        raise HTTPException(404, f"نماد {symbol} یافت نشد")
    return data


@router.get("/search")
async def search(q: str = Query("", min_length=0), limit: int = Query(20, ge=1, le=50)) -> list[dict[str, Any]]:
    await market_service.get_analysis(force=False)
    return market_service.search_symbols(q, limit=limit)


@router.get("/symbol/{l18}/full")
async def symbol_full(l18: str) -> dict[str, Any]:
    """جزئیات کامل صفحه نماد + پول داغ ریزمعاملات."""
    data = market_service.get_symbol(l18)
    if not data:
        await market_service.get_analysis(force=False)
        data = market_service.get_symbol(l18)
    if not data:
        raise HTTPException(404, f"نماد {l18} یافت نشد")
    try:
        hot = await market_service.get_trade_hot(l18)
        data["trade_hot"] = hot
    except Exception as exc:  # noqa: BLE001
        data["trade_hot"] = {"error": str(exc)}
    return data


# ---------- فاز ۴ ----------

class BacktestBody(BaseModel):
    entry_threshold: float = Field(65, ge=0, le=100)
    exit_threshold: float = Field(60, ge=0, le=100)
    take_profit: float = Field(4.0, ge=0, le=1000)
    stop_loss: float = Field(-3.0, ge=-1000, le=0)
    max_hold_bars: int = Field(24, ge=1, le=10000)
    fee_pct: float = Field(0.5, ge=0, le=100)
    bars: int = Field(80, ge=10, le=5000)
    use_synthetic_if_needed: bool = True


class NotifyConfigBody(BaseModel):
    enabled: Optional[bool] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    bale_token: Optional[str] = None
    bale_chat_id: Optional[str] = None
    min_entry_score: Optional[float] = None
    min_exit_score: Optional[float] = None
    cooldown_sec: Optional[int] = None
    portfolio_only: Optional[bool] = None


class NotifyTestBody(BaseModel):
    text: str = "تست هشدار شکار سهام ✅"
    channels: Optional[list[str]] = None


class OptionPriceBody(BaseModel):
    spot: float
    strike: float
    days: float = 30
    vol: float = 0.35
    rate: float = 0.25
    option_type: str = "call"
    side: str = "buy"


@router.post("/backtest/run")
async def backtest_run(body: BacktestBody = Body(default_factory=BacktestBody)) -> dict[str, Any]:
    await market_service.get_analysis(force=False)
    result = market_service.run_backtest(
        entry_threshold=body.entry_threshold,
        exit_threshold=body.exit_threshold,
        take_profit=body.take_profit,
        stop_loss=body.stop_loss,
        max_hold_bars=body.max_hold_bars,
        fee_pct=body.fee_pct,
        bars=body.bars,
        use_synthetic_if_needed=body.use_synthetic_if_needed,
    )
    return {"ok": True, "result": result}


@router.get("/backtest/history")
async def backtest_history(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    return store.list_backtest_runs(limit=limit)


@router.get("/options/{symbol}")
async def options_chain(symbol: str) -> dict[str, Any]:
    await market_service.get_analysis(force=False)
    data = market_service.get_options_chain(symbol)
    if not data:
        raise HTTPException(404, f"نماد {symbol} یافت نشد")
    return data


@router.post("/options/price")
async def options_price(body: OptionPriceBody) -> dict[str, Any]:
    ot = body.option_type.lower().strip()
    if ot not in {"call", "put"}:
        raise HTTPException(400, "option_type باید call یا put باشد")
    side = body.side.lower().strip()
    if side not in {"buy", "sell"}:
        raise HTTPException(400, "side باید buy یا sell باشد")
    return market_service.options_price(
        spot=body.spot,
        strike=body.strike,
        days=body.days,
        vol=body.vol,
        rate=body.rate,
        option_type=ot,
        side=side,
    )


@router.get("/notify/config")
async def notify_config_get() -> dict[str, Any]:
    from app.services.notifier import notifier

    return notifier.get_public_config()


@router.put("/notify/config")
async def notify_config_put(body: NotifyConfigBody) -> dict[str, Any]:
    from app.services.notifier import notifier

    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    return notifier.update_config(payload)


@router.post("/notify/test")
async def notify_test(body: NotifyTestBody) -> dict[str, Any]:
    from app.services.notifier import notifier

    result = await notifier.send_text(body.text, channels=body.channels)
    return {"ok": True, "result": result, "config": notifier.get_public_config()}


@router.get("/notify/log")
async def notify_log(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    return store.list_notify_log(limit=limit)


@router.get("/live/status")
async def live_status() -> dict[str, Any]:
    from app.services.ws_hub import ws_hub
    from app.services.notifier import notifier

    return {
        "ws": ws_hub.status(),
        "notifier": notifier.get_public_config(),
        "poll_seconds": market_service.status().get("poll_seconds"),
        "trust_level": market_service.trust_level(),
        "data_trust": market_service.data_trust_context(),
        "confluence": (market_service.get_confluence() or {}).get("summary"),
    }


@router.get("/confluence")
async def confluence_board(
    force: bool = Query(False),
    action: Optional[str] = Query(None, pattern="^(buy|sell|watch_buy|watch_sell|watch|all)$"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """جمع‌بندی نهایی: تابلو + بنیادی + جریان ۱۰دقیقه‌ای."""
    await market_service.get_analysis(force=False)
    board = market_service.get_confluence(force_rebuild=force)
    rows = board.get("board") or []
    if action and action != "all":
        rows = [r for r in rows if r.get("action") == action]
    return {
        "ok": True,
        "window_sec": board.get("window_sec"),
        "thresholds": board.get("thresholds"),
        "summary": board.get("summary"),
        "buy_alerts": (board.get("buy_alerts") or [])[:limit],
        "sell_alerts": (board.get("sell_alerts") or [])[:limit],
        "watchlist": (board.get("watchlist") or [])[:limit],
        "top_potentials": (board.get("top_potentials") or [])[:limit],
        "board": rows[:limit],
        "trust_level": market_service.trust_level(),
        "data_trust": market_service.data_trust_context(),
    }


@router.post("/confluence/notify-now")
async def confluence_notify_now() -> dict[str, Any]:
    """ارسال فوری هشدارهای خرید/فروش ترکیبی به تلگرام/بله (با dedupe)."""
    from app.engines.confluence import pick_notify_alerts
    from app.services.notifier import notifier

    await market_service.get_analysis(force=False)
    board = market_service.get_confluence(force_rebuild=True)
    ncfg = notifier.get_public_config()
    trust = market_service.trust_level()
    alerts = pick_notify_alerts(
        board,
        min_combo_buy=float(ncfg.get("min_combo_buy") or 70),
        min_combo_sell=float(ncfg.get("min_combo_sell") or 65),
    )
    if not ncfg.get("enabled"):
        texts = [notifier.format_alert(a) for a in alerts[:10]]
        return {
            "ok": True,
            "sent": 0,
            "preview_only": True,
            "trust_level": trust,
            "data_trust": market_service.data_trust_context(),
            "message": "اعلان غیرفعال است — برای ارسال واقعی enabled را روشن کنید",
            "alerts": alerts[:20],
            "previews": texts,
        }
    if trust == "synthetic" and not ncfg.get("allow_synthetic"):
        return {
            "ok": True,
            "sent": 0,
            "blocked": True,
            "trust_level": trust,
            "data_trust": market_service.data_trust_context(),
            "message": "داده synthetic است — برای ارسال، NOTIFY_ALLOW_SYNTHETIC=1 یا allow_synthetic در تنظیمات",
            "alerts": alerts[:20],
        }
    pf = {p["symbol"] for p in store.portfolio_list()}
    sent = await notifier.process_alerts(
        [],
        [],
        portfolio_symbols=pf,
        confluence_alerts=alerts,
        trust_level=trust,
    )
    return {
        "ok": True,
        "sent": sent,
        "trust_level": trust,
        "data_trust": market_service.data_trust_context(),
        "alerts": alerts[:20],
        "summary": board.get("summary"),
    }
