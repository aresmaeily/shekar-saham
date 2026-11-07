"""
chart_builder.py - v0.8 Excellent (capability description; no vendor-comparative claim)
Converts ticks/history to OHLCV for TradingView lightweight-charts
"""
from __future__ import annotations

from typing import Any, Dict, List
from collections import defaultdict
import time

def build_ohlcv_from_ticks(ticks: List[Dict[str, Any]], timeframe_sec: int = 60) -> List[Dict[str, Any]]:
    """
    ticks: [{ts, pl, tvol, ...}] sorted by ts asc
    timeframe_sec: 60=1m, 300=5m, 900=15m, 3600=1h
    Returns: [{time, open, high, low, close, volume}] where time is unix timestamp (seconds) for lightweight-charts
    """
    if not ticks:
        return []
    
    buckets: Dict[int, List[Dict]] = defaultdict(list)
    for t in ticks:
        ts = t.get("ts") or t.get("time") or time.time()
        # Allow ts as datetime or float
        if isinstance(ts, str):
            try:
                ts = float(ts)
            except (TypeError, ValueError):
                continue
        bucket_key = int(ts // timeframe_sec * timeframe_sec)
        buckets[bucket_key].append(t)
    
    ohlcv = []
    for bucket_ts in sorted(buckets.keys()):
        group = buckets[bucket_ts]
        if not group:
            continue
        prices = [g.get("pl") or g.get("close") or 0 for g in group if (g.get("pl") or g.get("close"))]
        if not prices:
            continue
        volumes = [g.get("tvol") or g.get("volume") or 0 for g in group]
        
        ohlcv.append({
            "time": bucket_ts,
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "volume": sum(volumes) / len(volumes) if volumes else 0,  # avg volume per bucket, or sum?
            # Extra for excellent chart
            "buy_power": sum(g.get("buy_power", 0) for g in group) / len(group),
            "hot_net": sum(g.get("hot_net", 0) for g in group),
        })
    
    return ohlcv

def build_ohlcv_from_daily_snapshots(snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    For daily timeframe - snapshots already have pl/open/high/low from TSETMC
    This is mock for demo - in live, would fetch from GetClosingPriceDaily
    """
    ohlcv = []
    for s in snapshots:
        # For demo, synthesize OHLC from pl and py
        pl = s.get("pl") or 1000
        py = s.get("py") or pl * 0.98
        open_price = py
        close_price = pl
        high_price = max(open_price, close_price) * 1.02
        low_price = min(open_price, close_price) * 0.98
        
        # time as YYYY-MM-DD for daily (lightweight-charts supports BusinessDay)
        ts = s.get("ts") or time.time()
        # Convert to YYYY-MM-DD string or unix timestamp? For daily, use BusinessDay
        # We'll use unix timestamp for simplicity
        ohlcv.append({
            "time": int(ts // 86400 * 86400),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": s.get("tvol", 0)
        })
    return sorted(ohlcv, key=lambda x: x["time"])

def calculate_ma(data: List[Dict], period: int = 20) -> List[Dict]:
    """Simple MA for overlay"""
    ma = []
    for i in range(len(data)):
        if i < period - 1:
            continue
        window = data[i-period+1:i+1]
        avg = sum(d["close"] for d in window) / period
        ma.append({"time": data[i]["time"], "value": avg})
    return ma

def calculate_ema(data: List[Dict], period: int = 20) -> List[Dict]:
    """EMA"""
    if not data:
        return []
    k = 2 / (period + 1)
    ema = []
    ema_prev = data[0]["close"]
    for i, d in enumerate(data):
        if i == 0:
            ema.append({"time": d["time"], "value": d["close"]})
        else:
            ema_curr = d["close"] * k + ema_prev * (1 - k)
            ema.append({"time": d["time"], "value": ema_curr})
            ema_prev = ema_curr
    return ema

def calculate_rsi(data: List[Dict], period: int = 14) -> List[Dict]:
    """RSI 0-100"""
    if len(data) < period + 1:
        return []
    
    rsi_data = []
    gains = []
    losses = []
    
    for i in range(1, len(data)):
        change = data[i]["close"] - data[i-1]["close"]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    
    # First avg
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(data)):
        if i > period:
            # Wilder's smoothing
            curr_gain = max(data[i]["close"] - data[i-1]["close"], 0)
            curr_loss = max(-(data[i]["close"] - data[i-1]["close"]), 0)
            avg_gain = (avg_gain * (period-1) + curr_gain) / period
            avg_loss = (avg_loss * (period-1) + curr_loss) / period
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        rsi_data.append({"time": data[i]["time"], "value": round(rsi, 2)})
    
    return rsi_data

def generate_markers_from_signals(signals: List[Dict], ohlcv: List[Dict]) -> List[Dict]:
    """
    Convert entry/exit signals to TradingView markers
    Capability: show buy/sell arrows on chart
    """
    markers = []
    # Build time map for quick lookup
    time_map = {c["time"]: c for c in ohlcv}
    
    for sig in signals[:20]:
        # Find closest candle time
        sig_time = sig.get("ts") or time.time()
        # Round to nearest timeframe
        closest_time = min(time_map.keys(), key=lambda t: abs(t - sig_time)) if time_map else int(sig_time)
        
        if sig.get("side") == "entry" or sig.get("action") == "buy":
            score_val = sig.get('score', '')
            try:
                score_str = f"{float(score_val):.0f}" if score_val != '' and score_val is not None else ""
            except (TypeError, ValueError):
                score_str = str(score_val)[:8]
            markers.append({
                "time": closest_time,
                "position": "belowBar",
                "color": "#34d399",
                "shape": "arrowUp",
                "text": f"خرید {score_str}",
                "symbol": sig.get("symbol", "")
            })
        elif sig.get("side") == "exit" or sig.get("action") == "sell":
            score_val = sig.get('score', '')
            try:
                score_str = f"{float(score_val):.0f}" if score_val != '' and score_val is not None else ""
            except (TypeError, ValueError):
                score_str = str(score_val)[:8]
            markers.append({
                "time": closest_time,
                "position": "aboveBar",
                "color": "#fb7185",
                "shape": "arrowDown",
                "text": f"فروش {score_str}",
                "symbol": sig.get("symbol", "")
            })
    
    return sorted(markers, key=lambda x: x["time"])
