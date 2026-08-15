"""
excellent.py - v0.7.0 Excellent - Creative endpoints
"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Query
from app.services.market_service import market_service
from app.engines.data_quality import quality_scorer
from app.engines.anomaly import anomaly_detector
from app.engines.ai_explainer import explainer
from app.engines.risk_manager import risk_manager
from app.core.metrics_prom import metrics
from app.domain.events import event_bus
router = APIRouter(prefix="/api/v07")

@router.get("/data-quality")
async def data_quality() -> Dict[str, Any]:
    """P0-1 Enhanced: Data quality per symbol"""
    await market_service.get_analysis(force=False)
    scores = quality_scorer.score_batch(market_service._last_symbols)
    return {
        "ok": True,
        **scores,
        "trust_level": market_service.trust_level(),
        "data_trust": market_service.data_trust_context(),
    }

@router.get("/anomalies")
async def anomalies(limit: int = Query(20, ge=1, le=100)) -> List[Dict[str, Any]]:
    """Creative: Detect market manipulation, pump detection"""
    await market_service.get_analysis(force=False)
    from app.data.store import store
    import time
    # Get recent ticks for comparison
    recent = store.get_ticks_since(time.time() - 3600)
    # Map symbol -> latest tick before current
    history_map = {}
    for tick in recent:
        sym = tick.get("symbol")
        if sym and sym not in history_map:
            history_map[sym] = tick
    
    result = anomaly_detector.scan_all(market_service._last_symbols, history_map)
    return result[:limit]

@router.get("/ai-explain/{symbol}")
async def ai_explain(symbol: str) -> Dict[str, Any]:
    """Creative: AI explanation for entry/exit"""
    data = market_service.get_symbol(symbol)
    if not data:
        from fastapi import HTTPException
        raise HTTPException(404, f"نماد {symbol} یافت نشد")
    
    from app.engines.metrics import compute_metrics
    from app.engines.tablocastic import compute_tablocastic
    snap = market_service.get_snapshot(symbol)
    cfg = market_service.cfg()
    m = compute_metrics(snap, cfg)
    tc = compute_tablocastic(snap, cfg)
    
    entry_exp = explainer.explain_entry(snap, m, tc, data.get("fundamental"))
    exit_exp = explainer.explain_exit(snap, m)
    
    return {
        "symbol": symbol,
        "entry_explanation": entry_exp,
        "exit_explanation": exit_exp,
        "scores": {"entry": m.entry_score, "exit": m.exit_score},
        "educational": True,
        "disclaimer": "این توضیحات توسط الگوریتم rule-based تولید شده و جایگزین تحلیل شخصی نیست"
    }

@router.get("/risk/position-size")
@router.post("/risk/position-size")
async def position_size(portfolio_value: float, entry_price: float, stop_loss: float, risk_pct: float = 1.0):
    """Creative: Position sizing calculator"""
    return risk_manager.calculate_position_size(portfolio_value, entry_price, stop_loss, risk_pct)

@router.get("/risk/stop-loss/{symbol}")
async def stop_loss_suggest(symbol: str):
    data = market_service.get_symbol(symbol)
    if not data:
        from fastapi import HTTPException
        raise HTTPException(404, f"نماد {symbol} یافت نشد")
    snap = data["snapshot"]
    pl = snap.get("pl") or snap.get("pl", 0)
    # Mock ATR as 2% of price, support as tmin
    atr = pl * 0.02
    support = snap.get("tmin") or pl * 0.95
    return {"symbol": symbol, "entry": pl, "suggestions": risk_manager.suggest_stop_loss(pl, atr, support)}

@router.get("/metrics")
async def prometheus_metrics():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(metrics.to_prometheus(), media_type="text/plain")

@router.get("/events")
async def events_history(event_type: str = Query(None), limit: int = Query(20, ge=1, le=100)):
    return event_bus.get_history(event_type, limit)

@router.get("/audit-log")
async def audit_log(limit: int = Query(20, ge=1, le=100)):
    from app.data.store import store
    return store.list_notify_log(limit=limit)  # Reuse notify log table for audit for now

@router.get("/portfolio/optimization")
async def portfolio_optimization():
    """Creative: Modern Portfolio Theory suggestion"""
    await market_service.get_analysis(force=False)
    # Simple: pick top 5 entry signals with low correlation (different industries)
    top = market_service.get_confluence().get("buy_alerts", [])[:20]
    industries = {}
    optimized = []
    for item in top:
        ind = item.get("industry") or "سایر"
        if ind not in industries:
            industries[ind] = []
        if len(industries[ind]) < 2:  # Max 2 per industry for diversification
            industries[ind].append(item)
            optimized.append(item)
        if len(optimized) >= 8:
            break
    
    return {
        "optimized_portfolio": optimized,
        "diversification": {k: len(v) for k,v in industries.items()},
        "principle": "متنوع‌سازی بر اساس صنعت - حداکثر 2 سهم از هر صنعت برای کاهش ریسک",
        "risk_note": "این پیشنهاد بر اساس تئوری پرتفوی مدرن ساده شده است - برای تصمیم نهایی ریسک شخصی را در نظر بگیرید"
    }
