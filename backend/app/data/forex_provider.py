"""
forex_provider.py - v1.0 Forex + Gold + Brokers + Volume Profile ready
- Real data without API key:
    * Gold spot (XAUUSD, brokers: BlackBull / Pepperstone / FXCM) -> PAXGUSDT via data-api.binance.vision
      (fallback: OKX PAXG-USDT -> KuCoin PAXG-USDT -> Yahoo GC=F -> synthetic)
    * Gold futures GC1 (COMEX) -> Yahoo GC=F
    * DXY (US Dollar Index, TVC) -> Yahoo DX-Y.NYB
    * US500 / US100 / US30 (capital.com) -> Yahoo ^GSPC / ^NDX / ^DJI
    * Brent Oil UKOIL (capital.com) -> Yahoo BZ=F
    * FX pairs -> Yahoo EURUSD=X / GBPUSD=X / USDJPY=X (fallback synthetic)
    * Crypto -> data-api.binance.vision (fallback OKX / KuCoin / synthetic)
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger("shekar.forex")

# ---------------------------------------------------------------------------
# Brokers / venues (like faraz.io broker list but better)
# ---------------------------------------------------------------------------
BROKERS: Dict[str, Dict[str, Any]] = {
    "blackbull": {
        "name": "BlackBull",
        "name_fa": "بلک‌بول",
        "kind": "forex-broker",
        "symbols": ["XAUUSD"],
    },
    "pepperstone": {
        "name": "Pepperstone",
        "name_fa": "پپراستون",
        "kind": "forex-broker",
        "symbols": ["XAUUSD"],
    },
    "fxcm": {
        "name": "FXCM",
        "name_fa": "اف‌ایکس‌سی‌ام",
        "kind": "forex-broker",
        "symbols": ["XAUUSD"],
    },
    "comex": {
        "name": "COMEX",
        "name_fa": "کامکس (COMEX)",
        "kind": "exchange",
        "symbols": ["GC1"],
    },
    "tvc": {
        "name": "TVC",
        "name_fa": "تی‌وی‌سی (TradingView)",
        "kind": "exchange",
        "symbols": ["DXY"],
    },
    "capital.com": {
        "name": "Capital.com",
        "name_fa": "کپیتال‌.کام (Capital.com)",
        "kind": "broker",
        "symbols": ["US500", "US100", "US30", "UKOIL"],
    },
}

# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------
FOREX_SYMBOLS: Dict[str, Dict[str, Any]] = {
    # --- طلا (گلد) ---
    "XAUUSD": {
        "name": "طلا / دلار",
        "name_en": "Gold Spot (XAU/USD)",
        "type": "commodity",
        "brokers": ["blackbull", "pepperstone", "fxcm"],
        "default_broker": "blackbull",
        "venue": "Spot / CFD",
        "desc": "قیمت لحظه‌ای طلا — بروکر: BlackBull / Pepperstone / FXCM (دیتای واقعی از PAXG)",
        "binance": "PAXGUSDT",
    },
    "GC1": {
        "name": "طلا فیوچرز COMEX",
        "name_en": "Gold Futures (GC1)",
        "type": "commodity",
        "brokers": ["comex"],
        "default_broker": "comex",
        "venue": "COMEX",
        "desc": "قرارداد آتی طلای کومکس — نماد GC1 (دیتای واقعی Yahoo GC=F)",
        "yahoo": "GC=F",
    },
    # --- شاخص دلار ---
    "DXY": {
        "name": "شاخص دلار",
        "name_en": "US Dollar Index (DXY)",
        "type": "index",
        "brokers": ["tvc"],
        "default_broker": "tvc",
        "venue": "TVC / ICE",
        "desc": "شاخص قدرت دلار DXY — منبع TVC (دیتای واقعی Yahoo DX-Y.NYB)",
        "yahoo": "DX-Y.NYB",
    },
    # --- شاخص‌های جهانی (capital.com) ---
    "US500": {
        "name": "S&P 500",
        "name_en": "S&P 500 (US500)",
        "type": "index",
        "brokers": ["capital.com"],
        "default_broker": "capital.com",
        "venue": "Capital.com",
        "desc": "شاخص اس‌اند‌پی ۵۰۰ — US500 (دیتای واقعی Yahoo ^GSPC)",
        "yahoo": "^GSPC",
    },
    "US100": {
        "name": "NASDAQ 100",
        "name_en": "Nasdaq 100 (US100)",
        "type": "index",
        "brokers": ["capital.com"],
        "default_broker": "capital.com",
        "venue": "Capital.com",
        "desc": "شاخص نزدک ۱۰۰ — US100 (دیتای واقعی Yahoo ^NDX)",
        "yahoo": "^NDX",
    },
    "US30": {
        "name": "داوجونز ۳۰",
        "name_en": "Dow Jones 30 (US30)",
        "type": "index",
        "brokers": ["capital.com"],
        "default_broker": "capital.com",
        "venue": "Capital.com",
        "desc": "شاخص داو جونز — US30 (دیتای واقعی Yahoo ^DJI)",
        "yahoo": "^DJI",
    },
    # --- نفت برنت ---
    "UKOIL": {
        "name": "نفت برنت",
        "name_en": "Brent Oil (UKOIL)",
        "type": "commodity",
        "brokers": ["capital.com"],
        "default_broker": "capital.com",
        "venue": "Capital.com",
        "desc": "نفت خام برنت — UKOIL (دیتای واقعی Yahoo BZ=F)",
        "yahoo": "BZ=F",
    },
    # --- جفت‌ارزها ---
    "EURUSD": {
        "name": "یورو / دلار",
        "name_en": "EUR/USD",
        "type": "forex",
        "brokers": [],
        "default_broker": None,
        "venue": "FX",
        "desc": "جفت ارز اصلی (دیتای واقعی Yahoo EURUSD=X)",
        "yahoo": "EURUSD=X",
    },
    "GBPUSD": {
        "name": "پوند / دلار",
        "name_en": "GBP/USD",
        "type": "forex",
        "brokers": [],
        "default_broker": None,
        "venue": "FX",
        "desc": "جفت ارز پوند/دلار (دیتای واقعی Yahoo GBPUSD=X)",
        "yahoo": "GBPUSD=X",
    },
    "USDJPY": {
        "name": "دلار / ین",
        "name_en": "USD/JPY",
        "type": "forex",
        "brokers": [],
        "default_broker": None,
        "venue": "FX",
        "desc": "جفت ارز دلار/ین (دیتای واقعی Yahoo USDJPY=X)",
        "yahoo": "USDJPY=X",
    },
    # --- کریپتو ---
    "BTCUSDT": {
        "name": "بیت‌کوین",
        "name_en": "BTC/USDT",
        "type": "crypto",
        "brokers": [],
        "default_broker": None,
        "venue": "Binance",
        "desc": "بیت‌کوین (دیتای واقعی Binance/OKX/KuCoin)",
        "binance": "BTCUSDT",
    },
    "ETHUSDT": {
        "name": "اتریوم",
        "name_en": "ETH/USDT",
        "type": "crypto",
        "brokers": [],
        "default_broker": None,
        "venue": "Binance",
        "desc": "اتریوم (دیتای واقعی Binance/OKX/KuCoin)",
        "binance": "ETHUSDT",
    },
}

# قیمت پایه برای حالت سنتتیک (وقتی هیچ منبع زنده‌ای در دسترس نیست)
SYNTHETIC_BASE: Dict[str, float] = {
    "XAUUSD": 4000.0, "GC1": 4000.0, "DXY": 104.0,
    "US500": 6400.0, "US100": 22500.0, "US30": 46000.0,
    "UKOIL": 72.0, "EURUSD": 1.08, "GBPUSD": 1.27, "USDJPY": 149.5,
    "BTCUSDT": 95000.0, "ETHUSDT": 3500.0,
}

BINANCE_HOSTS = [
    "https://data-api.binance.vision",  # public market data mirror - not geo-blocked
    "https://api.binance.com",          # original (blocked in some regions)
]

YAHOO_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

_TIMEFRAME_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "1D": "1d"}


# ---------------------------------------------------------------------------
# Binance (public market data mirror)
# ---------------------------------------------------------------------------
async def fetch_binance_klines(symbol: str = "PAXGUSDT", interval: str = "1m", limit: int = 300) -> List[Dict]:
    """Real data from Binance public API - no key needed - via data-api.binance.vision mirror."""
    binance_interval = _TIMEFRAME_MAP.get(interval, "1m")
    params = {"symbol": symbol, "interval": binance_interval, "limit": min(limit, 1000)}

    for host in BINANCE_HOSTS:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{host}/api/v3/klines", params=params)
                r.raise_for_status()
                klines = r.json()
            result = []
            for k in klines:
                result.append({
                    "time": k[0] // 1000,  # Binance gives ms, lightweight needs seconds
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "source": "binance",
                })
            if result:
                return result
        except Exception as exc:
            logger.warning(f"Binance fetch failed for {symbol} via {host}: {exc}")
    return []


# ---------------------------------------------------------------------------
# OKX
# ---------------------------------------------------------------------------
async def fetch_okx_klines(symbol: str = "PAXG-USDT", interval: str = "1m", limit: int = 300) -> List[Dict]:
    """OKX candlesticks - fallback source for gold/crypto."""
    bar_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "1D": "1D"}
    params = {"instId": symbol, "bar": bar_map.get(interval, "1m"), "limit": str(min(limit, 300))}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://www.okx.com/api/v5/market/candles", params=params)
            r.raise_for_status()
            payload = r.json()
        if payload.get("code") != "0":
            return []
        rows = payload.get("data") or []
        result = []
        for row in reversed(rows):  # OKX returns newest first
            # [ts(ms), o, h, l, c, vol, volCcy, volCcyQuote, confirm]
            result.append({
                "time": int(row[0]) // 1000,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5] or 0),
                "source": "okx",
            })
        return result[-limit:]
    except Exception as exc:
        logger.warning(f"OKX fetch failed for {symbol}: {exc}")
        return []


# ---------------------------------------------------------------------------
# KuCoin
# ---------------------------------------------------------------------------
async def fetch_kucoin_klines(symbol: str = "PAXG-USDT", interval: str = "1m", limit: int = 300) -> List[Dict]:
    """KuCoin candlesticks - fallback source for gold/crypto."""
    type_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1hour", "1D": "1day"}
    params = {"type": type_map.get(interval, "1min"), "symbol": symbol}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.kucoin.com/api/v1/market/candles", params=params)
            r.raise_for_status()
            payload = r.json()
        if payload.get("code") != "200000":
            return []
        rows = payload.get("data") or []
        result = []
        for row in reversed(rows):  # KuCoin returns newest first
            # [time(s), open, close, high, low, volume, turnover]
            result.append({
                "time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[3]),
                "low": float(row[4]),
                "close": float(row[2]),
                "volume": float(row[5] or 0),
                "source": "kucoin",
            })
        return result[-limit:]
    except Exception as exc:
        logger.warning(f"KuCoin fetch failed for {symbol}: {exc}")
        return []


# ---------------------------------------------------------------------------
# Yahoo Finance (GC=F, DX-Y.NYB, ^GSPC, ^NDX, ^DJI, BZ=F, EURUSD=X, ...)
# ---------------------------------------------------------------------------
YAHOO_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "1D": "1d"}
YAHOO_RANGE = {"1m": "1d", "5m": "5d", "15m": "1mo", "30m": "1mo", "1h": "1mo", "1D": "1y"}


async def fetch_yahoo_ohlcv(yahoo_symbol: str, interval: str = "1m", limit: int = 300) -> List[Dict]:
    """Real data from Yahoo Finance chart API (public, no key). Filters null bars."""
    intr = YAHOO_INTERVAL.get(interval, "5m")
    rng = YAHOO_RANGE.get(interval, "5d")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(yahoo_symbol, safe='^')}"
    params = {"interval": intr, "range": rng, "includePrePost": "false"}

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.get(url, params=params, headers=YAHOO_UA)
                if r.status_code == 429:
                    logger.warning(f"Yahoo rate-limited ({yahoo_symbol}) attempt {attempt+1}, retrying...")
                    await asyncio.sleep(1.2 * (attempt + 1))
                    continue
                r.raise_for_status()
                payload = r.json()
            chart = payload.get("chart") or {}
            if chart.get("error"):
                logger.warning(f"Yahoo error for {yahoo_symbol}: {chart.get('error')}")
                return []
            row = (chart.get("result") or [None])[0]
            if not row:
                return []
            ts = row.get("timestamp") or []
            quote_list = (row.get("indicators") or {}).get("quote") or [{}]
            q = quote_list[0] if quote_list else {}
            o, h, l, c, v = q.get("open"), q.get("high"), q.get("low"), q.get("close"), q.get("volume")
            if not o or not h or not l or not c:
                return []
            result = []
            for i, t in enumerate(ts):
                if i >= len(o) or i >= len(h) or i >= len(l) or i >= len(c):
                    break
                if o[i] is None or h[i] is None or l[i] is None or c[i] is None:
                    continue  # skip incomplete/null bars (off-hours)
                result.append({
                    "time": int(t),
                    "open": float(o[i]),
                    "high": float(h[i]),
                    "low": float(l[i]),
                    "close": float(c[i]),
                    "volume": float(v[i] or 0) if v and i < len(v) else 0.0,
                    "source": "yahoo",
                })
            return result[-limit:]
        except httpx.HTTPStatusError as exc:
            logger.warning(f"Yahoo HTTP error for {yahoo_symbol}: {exc}")
            return []
        except Exception as exc:
            logger.warning(f"Yahoo fetch failed for {yahoo_symbol}: {exc}")
            return []
    return []


# ---------------------------------------------------------------------------
# Synthetic fallback (بدون اینترنت / همه منابع خطا)
# ---------------------------------------------------------------------------
async def _synthetic_ohlcv(symbol: str, interval: str = "1m", limit: int = 300) -> List[Dict]:
    base = SYNTHETIC_BASE.get(symbol, 1.0)
    now = int(time.time() // 60 * 60)

    # سعی کن الگوی واقعی PAXG/BTC رو مقیاس‌بندی کنی
    pattern = await fetch_binance_klines("PAXGUSDT", interval, limit)
    if not pattern:
        pattern = await fetch_binance_klines("BTCUSDT", interval, limit)
    if pattern:
        first_close = pattern[0]["close"] or 1
        ratio = base / first_close
        result = []
        for candle in pattern:
            result.append({
                "time": candle["time"],
                "open": candle["open"] * ratio,
                "high": candle["high"] * ratio,
                "low": candle["low"] * ratio,
                "close": candle["close"] * ratio,
                "volume": candle["volume"],
                "source": f"synthetic-{symbol}",
                "trust_level": "synthetic",
            })
        return result

    # آخرین راه: random walk
    data = []
    price = base
    for i in range(limit):
        ts = now - (limit - i) * 60
        change = random.uniform(-0.001, 0.001) * base
        price += change
        data.append({
            "time": ts,
            "open": price,
            "high": price * (1 + random.uniform(0, 0.002)),
            "low": price * (1 - random.uniform(0, 0.002)),
            "close": price + random.uniform(-0.001, 0.001) * base,
            "volume": random.uniform(1000, 10000),
            "source": f"synthetic-{symbol}-randomwalk",
            "trust_level": "synthetic",
        })
    return data


# ---------------------------------------------------------------------------
# Range bars (رنج بار مثل تریدینگ ویو - 10R / 100R / 1000R)
# کندل‌ها بر اساس حرکت قیمت ساخته می‌شوند نه زمان:
# هر بار که بازه (high-low) کندل در حال ساخت به اندازه r برسد، کندل بسته می‌شود.
# ---------------------------------------------------------------------------
def is_range_timeframe(timeframe: str) -> bool:
    return bool(timeframe) and timeframe.endswith("R") and timeframe[:-1].isdigit()


def build_range_bars(ohlcv: List[Dict], r: float) -> List[Dict]:
    """
    تبدیل OHLCV زمانی به رنج بار با اندازه r.
    الگوریتم (مثل توضیح رسمی تریدینگ ویو):
    - کندل وقتی بسته می‌شود که high-low آن به r برسد.
    - قیمت بسته‌شدن = همان قیمتی که رنج را کامل کرده (extreme).
    - کندل بعدی با open برابر close کندل قبلی شروع می‌شود.
    - برای هر کندل ورودی مسیر open -> high -> low -> close تغذیه می‌شود
      تا حرکت‌های بزرگ چند رنج بار بسازند.
    """
    r = float(r)
    if r <= 0:
        return []
    bars: List[Dict] = []
    cur: Dict = None

    def close_bar(price: float, t: int, vol: float) -> None:
        nonlocal cur
        if cur is None:
            return
        bar = {
            "time": t,
            "open": cur["open"],
            "high": max(cur["high"], price),
            "low": min(cur["low"], price),
            "close": price,
            "volume": round(float(cur["volume"]) + float(vol), 4),
        }
        # زمان‌ها باید اکیداً صعودی باشند (نیاز lightweight-charts)
        if bars and bar["time"] <= bars[-1]["time"]:
            bar["time"] = bars[-1]["time"] + 1
        bars.append(bar)
        cur = {"time": t, "open": price, "high": price, "low": price, "close": price, "volume": 0.0}

    for candle in ohlcv:
        t = candle["time"]
        vol = (candle.get("volume") or 0) / 3.0
        if cur is None:
            o = candle.get("open", candle["close"])
            cur = {"time": t, "open": o, "high": o, "low": o, "close": o, "volume": 0.0}
        for p in (candle["high"], candle["low"], candle["close"]):
            while True:
                if p >= cur["low"] + r:
                    close_bar(cur["low"] + r, t, vol)
                    continue
                if p <= cur["high"] - r:
                    close_bar(cur["high"] - r, t, vol)
                    continue
                break
            cur["close"] = p
            cur["high"] = max(cur["high"], p)
            cur["low"] = min(cur["low"], p)
            cur["volume"] = float(cur["volume"]) + vol

    # کندل آخر ناقص (در حال ساخت) هم اضافه شود تا قیمت فعلی دیده شود
    if cur is not None:
        close_bar(cur["close"], cur["time"], 0.0)

    # منبع و برچسب
    for b in bars:
        b["source"] = f"range-{int(r)}"
    return bars


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
async def fetch_forex_ohlcv(
    symbol: str = "XAUUSD",
    timeframe: str = "1m",
    limit: int = 300,
    broker: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Main entry - like faraz.io but better.
    Returns OHLCV in lightweight-charts format.
    """
    symbol = symbol.upper()
    # Allow "XAUUSD.blackbull" style composite symbols
    if "." in symbol and symbol not in FOREX_SYMBOLS:
        base, _, br = symbol.partition(".")
        symbol = base.upper()
        if not broker:
            broker = br

    info = FOREX_SYMBOLS.get(symbol, {})
    if not info:
        logger.warning(f"Unknown forex symbol: {symbol}")
        return []

    # Resolve broker (validate against symbol's broker list)
    resolved_broker = None
    if info.get("brokers"):
        resolved_broker = broker if broker in info["brokers"] else info.get("default_broker")

    # ------------------------------------------------------------------
    # Range timeframe (10R / 100R / 1000R) — قیمت‌محور مثل تریدینگ ویو
    # ------------------------------------------------------------------
    if is_range_timeframe(timeframe):
        r = int(timeframe[:-1])
        # پایه: 5 دقیقه‌ای با ۱۰۰۰ کندل (پوشش زمانی بیشتر -> رنج بار بیشتر)
        base = await fetch_forex_ohlcv(symbol, "5m", limit=1000, broker=resolved_broker)
        bars = build_range_bars(base, r)
        # اگر خیلی کم شد، با ۱ دقیقه‌ای دوباره بساز
        if len(bars) < 3:
            base1 = await fetch_forex_ohlcv(symbol, "1m", limit=1000, broker=resolved_broker)
            bars1 = build_range_bars(base1, r)
            if len(bars1) > len(bars):
                bars = bars1
        if len(bars) < 2:
            return []
        for b in bars:
            b["symbol"] = symbol
            if resolved_broker:
                b["broker"] = resolved_broker
        return bars

    data: List[Dict] = []

    # 1) Gold spot / crypto -> Binance mirror -> OKX -> KuCoin -> Yahoo -> synthetic
    if info.get("binance"):
        binance_sym = info["binance"]
        data = await fetch_binance_klines(binance_sym, timeframe, limit)
        if not data:
            okx_sym = binance_sym.replace("USDT", "-USDT")
            data = await fetch_okx_klines(okx_sym, timeframe, limit)
        if not data:
            data = await fetch_kucoin_klines(binance_sym.replace("USDT", "-USDT"), timeframe, limit)
        if not data and info.get("yahoo"):
            data = await fetch_yahoo_ohlcv(info["yahoo"], timeframe, limit)
        if not data:
            data = await _synthetic_ohlcv(symbol, timeframe, limit)

    # 2) Yahoo-based instruments (GC1, DXY, indices, Brent, FX pairs)
    elif info.get("yahoo"):
        data = await fetch_yahoo_ohlcv(info["yahoo"], timeframe, limit)
        if not data and info.get("binance"):
            data = await fetch_binance_klines(info["binance"], timeframe, limit)
        if not data:
            data = await _synthetic_ohlcv(symbol, timeframe, limit)

    # 3) Anything else -> synthetic
    else:
        data = await _synthetic_ohlcv(symbol, timeframe, limit)

    # Attach symbol + broker info to each candle so UI can show source
    for d in data:
        d["symbol"] = symbol
        if resolved_broker:
            d["broker"] = resolved_broker
    return data


def get_broker_list() -> List[Dict[str, Any]]:
    return [{"id": k, **v} for k, v in BROKERS.items()]


def get_forex_symbols_list() -> List[Dict[str, Any]]:
    return [{"symbol": k, **v} for k, v in FOREX_SYMBOLS.items()]


def resolve_broker(symbol: str, broker: Optional[str] = None) -> Optional[str]:
    """Validate broker for a symbol - returns the effective broker id or None."""
    info = FOREX_SYMBOLS.get(symbol.upper(), {})
    if not info.get("brokers"):
        return None
    if broker in info["brokers"]:
        return broker
    return info.get("default_broker")
