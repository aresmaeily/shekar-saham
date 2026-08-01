"""
forex.py - v1.0 Forex + Gold + Brokers (BlackBull / Pepperstone / FXCM) + COMEX + TVC + Capital.com
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Query
from app.data.forex_provider import (
    fetch_forex_ohlcv,
    get_forex_symbols_list,
    get_broker_list,
    resolve_broker,
    FOREX_SYMBOLS,
    BROKERS,
)
from app.engines.chart_builder import calculate_ma, calculate_ema, calculate_rsi
from app.engines.indicators import (
    macd as ind_macd,
    bollinger as ind_bollinger,
    stochastic as ind_stochastic,
    atr as ind_atr,
    adx as ind_adx,
    cci as ind_cci,
    obv as ind_obv,
    williams as ind_williams,
    vwap as ind_vwap,
)
from app.data.forex_provider import is_range_timeframe
from app.engines.risk_manager import risk_manager

router = APIRouter(prefix="/api/v09")

TIMEFRAMES = "^(1m|5m|15m|30m|1h|1D|10R|100R|1000R)$"


@router.get("/forex/symbols")
async def forex_symbols():
    """List all forex/gold/index symbols + brokers like faraz.io"""
    return {
        "symbols": get_forex_symbols_list(),
        "brokers": get_broker_list(),
        "count": len(FOREX_SYMBOLS),
        "note": (
            "دیتای واقعی رایگان: طلا (XAUUSD) از PAXG (BlackBull/Pepperstone/FXCM) · "
            "GC1 از COMEX (Yahoo GC=F) · DXY از TVC (Yahoo DX-Y.NYB) · "
            "S&P500/US100/US30/نفت برنت از Capital.com (Yahoo ^GSPC/^NDX/^DJI/BZ=F)"
        ),
    }


@router.get("/forex/{symbol}")
async def forex_chart(
    symbol: str,
    broker: Optional[str] = Query(None),
    timeframe: str = Query("1m", pattern=TIMEFRAMES),
    with_indicators: bool = Query(True),
):
    """
    Forex/gold/index chart - like faraz.io but better.
    - symbol: XAUUSD | GC1 | DXY | US500 | US100 | US30 | UKOIL | EURUSD | ...
    - broker: blackbull | pepperstone | fxcm | comex | tvc | capital.com
    """
    sym = symbol.upper()
    eff_broker = resolve_broker(sym, broker)
    info = FOREX_SYMBOLS.get(sym, {})

    ohlcv = await fetch_forex_ohlcv(sym, timeframe, limit=300, broker=eff_broker)

    if not ohlcv:
        if is_range_timeframe(timeframe):
            r = int(timeframe[:-1])
            suggestion = "10R" if r > 10 else "حتی 10R هم برای این نماد بزرگ است — از تایم‌فریم‌های زمانی (1m/5m/1h) استفاده کنید"
            return {
                "error": (
                    f"برای رنج {timeframe} کندل کافی ساخته نشد — حرکت قیمت این نماد در بازه موجود "
                    f"به اندازه {r} واحد نرسیده است. رنج کوچک‌تری انتخاب کنید: {suggestion}."
                ),
                "symbol": sym,
                "timeframe": timeframe,
            }
        return {"error": f"No data for {symbol}", "symbol": sym}

    indicators = {}
    if with_indicators:
        indicators["ma20"] = calculate_ma(ohlcv, 20)
        indicators["ma50"] = calculate_ma(ohlcv, 50)
        indicators["ema20"] = calculate_ema(ohlcv, 20)
        indicators["rsi"] = calculate_rsi(ohlcv, 14)
        indicators["volume"] = [
            {"time": c["time"], "value": c.get("volume", 0),
             "color": "rgba(52,211,153,0.4)" if c["close"] >= c["open"] else "rgba(251,113,133,0.4)"}
            for c in ohlcv
        ]
        # اندیکاتورهای کلاسیک مثل فراز / تریدینگ ویو
        indicators["macd"] = ind_macd(ohlcv)
        indicators["bollinger"] = ind_bollinger(ohlcv)
        indicators["stochastic"] = ind_stochastic(ohlcv)
        indicators["atr"] = ind_atr(ohlcv)
        indicators["adx"] = ind_adx(ohlcv)
        indicators["cci"] = ind_cci(ohlcv)
        indicators["obv"] = ind_obv(ohlcv)
        indicators["williams"] = ind_williams(ohlcv)
        indicators["vwap"] = ind_vwap(ohlcv)

    last_close = ohlcv[-1]["close"] if ohlcv else 0
    risk_levels = risk_manager.suggest_stop_loss(entry=last_close, atr=last_close * 0.01, support=last_close * 0.97)

    source = str(ohlcv[0].get("source", "")) if ohlcv else "unknown"
    if "synthetic" in source:
        trust_level = "synthetic"
    elif any(x in source for x in ("binance", "okx", "kucoin", "yahoo")):
        trust_level = "live"
    else:
        trust_level = "mixed"

    broker_name = None
    if eff_broker:
        broker_name = BROKERS.get(eff_broker, {}).get("name", eff_broker)

    tf_type = "range" if is_range_timeframe(timeframe) else "time"
    range_size = int(timeframe[:-1]) if is_range_timeframe(timeframe) else None

    return {
        "symbol": sym,
        "display_symbol": f"{sym}{'.' + eff_broker if eff_broker else ''}",
        "name_fa": info.get("name", sym),
        "name_en": info.get("name_en", sym),
        "broker": eff_broker,
        "broker_name": broker_name,
        "venue": info.get("venue", ""),
        "timeframe": timeframe,
        "tf_type": tf_type,
        "range_size": range_size,
        "source": source,
        "trust_level": trust_level,
        "ohlcv": ohlcv,
        "indicators": indicators,
        "risk_levels": risk_levels,
        "last_price": last_close,
        "count": len(ohlcv),
        "note": "v1.0 - Forex + Gold + Brokers + COMEX/TVC/Capital.com - real free data (Yahoo/Binance/OKX/KuCoin)",
    }


@router.get("/forex/{symbol}/ai-explain")
async def forex_ai_explain(symbol: str):
    """AI explanation for forex - feature faraz.io doesn't have"""
    ohlcv = await fetch_forex_ohlcv(symbol.upper(), "1m", limit=50)
    if not ohlcv:
        return {"error": "No data"}

    last = ohlcv[-1]
    prev = ohlcv[-2] if len(ohlcv) > 1 else last
    change_pct = ((last["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else 0

    if change_pct > 0.2:
        explanation = f"{symbol} در 1 دقیقه {change_pct:.2f}% رشد - مومنتوم صعودی - با حد ضرر {last['close'] * 0.99:.2f} می‌توان همراه شد"
    elif change_pct < -0.2:
        explanation = f"{symbol} {change_pct:.2f}% افت - فشار فروش - صبر برای حمایت {last['close'] * 0.97:.2f}"
    else:
        explanation = f"{symbol} رنج {change_pct:.2f}% - بازار خنثی - منتظر شکست"

    return {
        "symbol": symbol,
        "explanation": explanation,
        "change_pct": round(change_pct, 3),
        "last_price": last["close"],
        "educational": True,
    }
