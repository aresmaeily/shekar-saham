"""پول داغ دقیق‌تر بر اساس ریزمعاملات (Trade Detail).

اگر endpoint زنده TSETMC در دسترس نباشد، ریزمعاملات واقع‌گرایانه از روی تابلو ساخته می‌شود.
"""

from __future__ import annotations

import hashlib
import random
import time
from datetime import datetime
from typing import Any
import httpx

from app.core.config import Settings, get_settings
from app.models.schemas import SymbolSnapshot

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _rng(symbol: str) -> random.Random:
    seed = int(hashlib.md5(f"{symbol}:{int(time.time()//60)}".encode()).hexdigest()[:8], 16)
    return random.Random(seed)


async def fetch_trade_detail_live(ins_code: str, settings: Settings) -> list[dict[str, Any]]:
    if not ins_code:
        return []
    # در حالت دمو/mock به‌هیچ‌وجه به شبکه وصل نشو — مستقیم synthetic ساخته شود
    # (جلوگیری از ۳× timeout ≈ ۳۶ ثانیه آویزانی صفحه نماد)
    if getattr(settings, "data_source", "auto") in ("mock", "demo"):
        return []
    urls = [
        f"{settings.tsetmc_cdn}/api/Trade/GetTrade/{ins_code}",
        f"https://cdn.tsetmc.com/api/Trade/GetTrade/{ins_code}",
        f"https://cdn.tsetmc.com/api/Trade/GetTradeHistory/{ins_code}/0",
    ]
    headers = {"User-Agent": UA, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.request_timeout, headers=headers, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                trades = data.get("trade") or data.get("trades") or data.get("Trade") or data
                if isinstance(trades, dict):
                    trades = trades.get("trade") or trades.get("list") or []
                if not isinstance(trades, list):
                    continue
                out = []
                for t in trades:
                    if not isinstance(t, dict):
                        continue
                    price = float(t.get("pDrCotVal") or t.get("price") or t.get("p") or 0)
                    vol = float(t.get("qTitTran") or t.get("volume") or t.get("q") or 0)
                    if price <= 0 or vol <= 0:
                        continue
                    h = t.get("hEven") or t.get("time") or 0
                    out.append(
                        {
                            "time": str(h),
                            "price": price,
                            "volume": vol,
                            "value": price * vol,
                            "source": "tsetmc",
                        }
                    )
                if out:
                    return out
            except Exception:  # noqa: BLE001
                continue
    return []


def synthesize_trades(s: SymbolSnapshot, n: int = 80) -> list[dict[str, Any]]:
    r = _rng(s.l18)
    trades: list[dict[str, Any]] = []
    if s.pl <= 0 or s.tvol <= 0:
        return trades
    remain = float(s.tvol)
    base_price = float(s.pl)
    # تعدادی معامله درشت برای حس پول داغ
    big_n = r.randint(2, 8)
    for i in range(n):
        is_big = i < big_n or r.random() < 0.08
        if is_big:
            # ارزش حدود 100M تا 800M
            value = r.uniform(80_000_000, 900_000_000)
            price = base_price * r.uniform(0.997, 1.003)
            vol = max(1, int(value / max(price, 1)))
        else:
            vol = max(1, int(r.lognormvariate(6.5, 1.1)))
            price = base_price * r.uniform(0.995, 1.005)
            value = vol * price
        remain -= vol
        side = "buy" if r.random() < (0.62 if (s.Buy_I_Volume >= s.Sell_I_Volume) else 0.4) else "sell"
        # زمان ساختگی HHMMSS
        sec = 9 * 3600 + int((i / max(n - 1, 1)) * 3.5 * 3600)
        hh, mm, ss = sec // 3600, (sec % 3600) // 60, sec % 60
        trades.append(
            {
                "time": f"{hh:02d}{mm:02d}{ss:02d}",
                "time_fmt": f"{hh:02d}:{mm:02d}:{ss:02d}",
                "price": round(price, 0),
                "volume": vol,
                "value": value,
                "side": side,
                "source": "synthetic",
            }
        )
        if remain <= 0:
            break
    return trades


def analyze_hot_from_trades(
    trades: list[dict[str, Any]],
    s: SymbolSnapshot,
    cfg: Settings | None = None,
) -> dict[str, Any]:
    cfg = cfg or get_settings()
    hot_th = cfg.hot_money_threshold
    plus_min = cfg.hot_money_plus_min

    hot_buys = []
    hot_sells = []
    plus_buys = []
    plus_sells = []

    for t in trades:
        val = float(t.get("value") or 0)
        side = t.get("side") or "buy"
        # اگر side نداشت، از مقایسه با pl حدس بزن
        if "side" not in t and s.pl:
            side = "buy" if float(t.get("price") or 0) >= s.pl else "sell"
        row = {**t, "side": side, "tier": "hot" if val >= hot_th else "plus" if val >= plus_min else "normal"}
        if val >= hot_th:
            (hot_buys if side == "buy" else hot_sells).append(row)
        elif val >= plus_min:
            (plus_buys if side == "buy" else plus_sells).append(row)

    def _sum(rows: list[dict]) -> float:
        return float(sum(x.get("value") or 0 for x in rows))

    hot_buy_val = _sum(hot_buys)
    hot_sell_val = _sum(hot_sells)
    plus_buy_val = _sum(plus_buys)
    plus_sell_val = _sum(plus_sells)
    net_hot = hot_buy_val - hot_sell_val
    net_plus = plus_buy_val - plus_sell_val

    # امتیاز
    score = 0.0
    if net_hot > 0:
        score += min(40, net_hot / hot_th * 8)
    else:
        score -= min(40, abs(net_hot) / hot_th * 8)
    score += min(15, len(hot_buys) * 3)
    score -= min(15, len(hot_sells) * 3)
    if net_plus > 0:
        score += min(10, net_plus / plus_min * 2)

    largest = sorted(trades, key=lambda x: float(x.get("value") or 0), reverse=True)[:12]

    return {
        "symbol": s.l18,
        "name": s.l30,
        "trade_count": len(trades),
        "hot_buy_count": len(hot_buys),
        "hot_sell_count": len(hot_sells),
        "plus_buy_count": len(plus_buys),
        "plus_sell_count": len(plus_sells),
        "hot_buy_value": hot_buy_val,
        "hot_sell_value": hot_sell_val,
        "plus_buy_value": plus_buy_val,
        "plus_sell_value": plus_sell_val,
        "net_hot": net_hot,
        "net_plus": net_plus,
        "net_all_large": net_hot + net_plus,
        "score": round(max(-100, min(100, score)), 1),
        "threshold_hot": hot_th,
        "threshold_plus": plus_min,
        "largest_trades": largest,
        "hot_buys": hot_buys[:20],
        "hot_sells": hot_sells[:20],
        "source": trades[0].get("source") if trades else "none",
        "as_of": datetime.now().isoformat(timespec="seconds"),
    }


async def get_trade_hot_money(s: SymbolSnapshot, cfg: Settings | None = None) -> dict[str, Any]:
    cfg = cfg or get_settings()
    trades = await fetch_trade_detail_live(str(s.id or ""), cfg)
    if not trades:
        trades = synthesize_trades(s)
        # side already set
    else:
        # annotate side roughly
        for t in trades:
            if "side" not in t:
                t["side"] = "buy" if float(t.get("price") or 0) >= (s.pl or 0) else "sell"
            t["time_fmt"] = _fmt_time(t.get("time"))
    return analyze_hot_from_trades(trades, s, cfg)


def _fmt_time(h: Any) -> str:
    s = str(h or "").zfill(6)
    if len(s) >= 6 and s.isdigit():
        return f"{s[-6:-4]}:{s[-4:-2]}:{s[-2:]}"
    return str(h or "")


def build_ohlcv_from_ticks(ticks: list[dict[str, Any]], snapshot: SymbolSnapshot) -> list[dict[str, Any]]:
    """OHLCV تقریبی روزانه/درون‌روزی از تیک‌ها + کندل‌های مصنوعی تاریخچه."""
    r = _rng(snapshot.l18 + "-ohlc")
    candles: list[dict[str, Any]] = []
    # 60 روز گذشته مصنوعی
    price = float(snapshot.py or snapshot.pl or 1000)
    now = int(time.time())
    day = 86400
    for i in range(60, 0, -1):
        ts = now - i * day
        drift = r.uniform(-0.03, 0.03)
        o = price
        c = max(1, price * (1 + drift))
        h = max(o, c) * (1 + r.uniform(0, 0.015))
        l = min(o, c) * (1 - r.uniform(0, 0.015))
        v = float(snapshot.avg_vol_30d or snapshot.tvol or 1e6) * r.uniform(0.4, 1.8)
        candles.append(
            {
                "time": ts,
                "open": round(o, 0),
                "high": round(h, 0),
                "low": round(l, 0),
                "close": round(c, 0),
                "volume": int(v),
            }
        )
        price = c
    # امروز از snapshot
    o = float(snapshot.pf or snapshot.py or snapshot.pl)
    h = float(snapshot.pmax or max(o, snapshot.pl))
    l = float(snapshot.pmin or min(o, snapshot.pl))
    c = float(snapshot.pl or o)
    candles.append(
        {
            "time": now,
            "open": round(o, 0),
            "high": round(h, 0),
            "low": round(l, 0),
            "close": round(c, 0),
            "volume": int(snapshot.tvol or 0),
        }
    )
    # اگر تیک intraday داریم، سری جدا
    return candles


def build_intraday_series(ticks: list[dict[str, Any]], snapshot: SymbolSnapshot) -> list[dict[str, Any]]:
    if ticks:
        out = []
        for t in ticks:
            out.append(
                {
                    "time": t.get("ts"),
                    "value": t.get("pl"),
                    "plp": t.get("plp"),
                    "tvol": t.get("tvol"),
                    "buy_power": t.get("buy_power"),
                    "hot_net": t.get("hot_net"),
                    "entry_score": t.get("entry_score"),
                }
            )
        return out
    # synthetic intraday points
    r = _rng(snapshot.l18 + "-intra")
    out = []
    now = time.time()
    price = float(snapshot.py or snapshot.pl or 1000)
    for i in range(48):
        ts = now - (48 - i) * 300
        price = price * (1 + r.uniform(-0.004, 0.004))
        out.append({"time": ts, "value": round(price, 0), "plp": round((price / (snapshot.py or price) - 1) * 100, 2)})
    out.append({"time": now, "value": snapshot.pl, "plp": snapshot.plp})
    return out
