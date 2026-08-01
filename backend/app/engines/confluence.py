"""جمع‌بندی نهایی: تابلوخوانی + بنیادی + جریان نقد ۱۰دقیقه‌ای.

سهام پرپتانسیل بنیادی وقتی در سکانس‌های ۱۰ دقیقه‌ای ورود/خروج پول قوی ببینند،
سیگنال خرید/فروش ترکیبی می‌گیرند.
"""

from __future__ import annotations

from typing import Any
from app.core.config import Settings, get_settings
from app.engines.fundamental import build_deep_fundamental
from app.engines.metrics import compute_metrics
from app.engines.tablocastic import compute_tablocastic
from app.models.schemas import SignalSide, SymbolSnapshot


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def build_confluence_board(
    symbols: list[SymbolSnapshot],
    big_moves: list[dict[str, Any]],
    cfg: Settings | None = None,
    *,
    min_value_score: float = 55.0,
    min_combo_buy: float = 70.0,
    min_combo_sell: float = 65.0,
    flow_window_sec: int = 600,
    limit: int = 60,
) -> dict[str, Any]:
    cfg = cfg or get_settings()
    move_map = {m.get("symbol"): m for m in big_moves if m.get("symbol")}

    rows: list[dict[str, Any]] = []
    for s in symbols:
        if not s.l18:
            continue
        m = compute_metrics(s, cfg)
        tc = compute_tablocastic(s, cfg)
        fund = build_deep_fundamental(s, cfg)
        value_score = float(fund.get("value_score") or fund.get("fund_score") or 0)
        pe = fund.get("pe", s.pe)

        mv = move_map.get(s.l18) or {}
        flow_score = float(mv.get("score") or 0)
        flow_side = mv.get("side") or "none"  # inflow | outflow
        delta_net = float(mv.get("delta_net_value") or 0)
        delta_hot = float(mv.get("delta_hot_net") or 0)
        delta_plp = float(mv.get("delta_plp") or 0)
        flow_note = mv.get("note") or ""

        # نرمال جریان ۱۰دقیقه‌ای 0..100
        flow_norm = _clamp(flow_score * 1.1)

        # هم‌راستایی جریان
        flow_buy_boost = 0.0
        flow_sell_boost = 0.0
        if flow_side == "inflow" and flow_score >= 25:
            flow_buy_boost = _clamp(flow_norm * 0.35, 0, 35)
            if delta_net > 0 and m.individual_net_value > 0:
                flow_buy_boost += 5
            if delta_plp < 0 and delta_net > 0:
                flow_buy_boost += 4  # ورود پول در منفی
        if flow_side == "outflow" and flow_score >= 25:
            flow_sell_boost = _clamp(flow_norm * 0.35, 0, 35)
            if delta_net < 0 and m.individual_net_value < 0:
                flow_sell_boost += 5

        tablo_buy = float(m.entry_score)
        tablo_sell = float(m.exit_score)
        fund_w = value_score

        # امتیاز ترکیبی خرید: تابلو 40% + بنیادی 30% + جریان 30% (+boost)
        combo_buy = _clamp(tablo_buy * 0.40 + fund_w * 0.30 + flow_norm * 0.30 + flow_buy_boost * 0.15)
        # فروش: تابلو خروج 45% + ضعف بنیادی معکوس 15% + جریان خروجی 40%
        fund_weak = _clamp(100 - fund_w)
        combo_sell = _clamp(tablo_sell * 0.45 + fund_weak * 0.15 + flow_norm * 0.40 + flow_sell_boost * 0.15)

        # شرط بنیادی ارزنده برای خرید
        value_ok = value_score >= min_value_score and (pe is None or (pe > 0 and pe <= 18))
        strong_flow_in = flow_side == "inflow" and flow_score >= 30
        strong_flow_out = flow_side == "outflow" and flow_score >= 30

        action = "watch"
        alert = False
        reasons: list[str] = []
        tags: list[str] = []

        if value_ok and strong_flow_in and combo_buy >= min_combo_buy and tablo_buy >= 55:
            action = "buy"
            alert = True
            tags += ["خرید‌ترکیبی", "بنیادی‌ارزنده", "جریان‌۱۰دقیقه"]
            reasons.append(f"بنیادی ارزنده ({value_score:.0f}) + ورود پول ۱۰دقیقه‌ای ({flow_score:.0f})")
            if m.is_volume_spike:
                reasons.append(f"حجم مشکوک ×{m.volume_ratio:.1f}")
                tags.append("حجم‌مشکوک")
            if m.buy_power >= 1.5:
                reasons.append(f"قدرت خریدار {m.buy_power:.2f}")
            if s.plp <= 0:
                reasons.append(f"شکار در منفی ({s.plp:.1f}٪)")
                tags.append("شکار‌منفی")
            if flow_note:
                reasons.append(flow_note)
        elif strong_flow_out and combo_sell >= min_combo_sell and (tablo_sell >= 55 or not value_ok):
            action = "sell"
            alert = True
            tags += ["فروش‌ترکیبی", "خروج‌جریان‌۱۰دقیقه"]
            reasons.append(f"خروج پول ۱۰دقیقه‌ای ({flow_score:.0f}) + ریسک خروج تابلو ({tablo_sell:.0f})")
            if m.individual_net_value < 0:
                reasons.append("خالص حقیقی منفی")
            if m.buy_power < 0.9:
                reasons.append(f"ضعف قدرت خریدار ({m.buy_power:.2f})")
            if flow_note:
                reasons.append(flow_note)
        elif value_ok and tablo_buy >= 60:
            action = "watch_buy"
            tags += ["رصد‌خرید", "بنیادی‌ارزنده"]
            reasons.append("بنیادی خوب؛ منتظر تأیید جریان ۱۰دقیقه‌ای قوی")
            if flow_side == "inflow":
                reasons.append(f"جریان اولیه ورودی ({flow_score:.0f}) — هنوز به آستانه هشدار نرسیده")
        elif tablo_sell >= 60:
            action = "watch_sell"
            tags.append("رصد‌فروش")
            reasons.append("ریسک خروج تابلو؛ جریان/بنیادی را رصد کنید")

        # فقط ردیف‌های معنادار
        if action == "watch" and value_score < min_value_score - 5 and tablo_buy < 50 and tablo_sell < 50 and flow_score < 20:
            continue

        conf = combo_buy if action in {"buy", "watch_buy"} else combo_sell if action in {"sell", "watch_sell"} else max(combo_buy, combo_sell) * 0.7

        rows.append(
            {
                "symbol": s.l18,
                "name": s.l30,
                "industry": s.cs,
                "pl": s.pl,
                "plp": s.plp,
                "pe": pe,
                "action": action,
                "alert": alert,
                "combo_score": round(conf, 1),
                "combo_buy": round(combo_buy, 1),
                "combo_sell": round(combo_sell, 1),
                "entry_score": round(tablo_buy, 1),
                "exit_score": round(tablo_sell, 1),
                "value_score": round(value_score, 1),
                "value_grade": fund.get("value_grade") or fund.get("grade"),
                "fund_score": fund.get("fund_score"),
                "buy_power": round(m.buy_power, 2),
                "volume_ratio": round(m.volume_ratio, 2),
                "hot_net": round(m.hot_net, 1),
                "individual_net_value": m.individual_net_value,
                "golden_number": tc.golden_number,
                "quality_score": tc.quality_score,
                "flow_window_sec": flow_window_sec,
                "flow_score": round(flow_score, 1),
                "flow_side": flow_side,
                "flow_delta_net": delta_net,
                "flow_delta_hot": delta_hot,
                "flow_delta_plp": delta_plp,
                "flow_note": flow_note,
                "value_ok": value_ok,
                "strong_flow": strong_flow_in or strong_flow_out,
                "reasons": reasons[:6],
                "tags": list(dict.fromkeys(tags)),
                "side_signal": m.side.value if isinstance(m.side, SignalSide) else str(m.side),
            }
        )

    # اولویت: هشدار خرید، هشدار فروش، سپس امتیاز
    def _sort_key(r: dict[str, Any]):
        pri = {"buy": 0, "sell": 1, "watch_buy": 2, "watch_sell": 3, "watch": 4}.get(r["action"], 5)
        return (pri, -r["combo_score"], -r["flow_score"])

    rows.sort(key=_sort_key)
    buys = [r for r in rows if r["action"] == "buy"]
    sells = [r for r in rows if r["action"] == "sell"]
    watch = [r for r in rows if r["action"] in {"watch_buy", "watch_sell"}]

    return {
        "window_sec": flow_window_sec,
        "thresholds": {
            "min_value_score": min_value_score,
            "min_combo_buy": min_combo_buy,
            "min_combo_sell": min_combo_sell,
        },
        "summary": {
            "total": len(rows),
            "buy_alerts": len(buys),
            "sell_alerts": len(sells),
            "watch": len(watch),
        },
        "buy_alerts": buys[:limit],
        "sell_alerts": sells[:limit],
        "watchlist": watch[:limit],
        "board": rows[:limit],
        "top_potentials": [r for r in rows if r["value_ok"]][:20],
    }


def pick_notify_alerts(
    board: dict[str, Any],
    *,
    min_combo_buy: float = 70,
    min_combo_sell: float = 65,
) -> list[dict[str, Any]]:
    """هشدارهای قابل ارسال به تلگرام/بله از جمع‌بندی نهایی."""
    out: list[dict[str, Any]] = []
    for r in board.get("buy_alerts") or []:
        if r.get("combo_score", 0) >= min_combo_buy and r.get("alert"):
            out.append(
                {
                    "symbol": r["symbol"],
                    "name": r.get("name"),
                    "side": "buy",
                    "action": "buy",
                    "score": r.get("combo_score"),
                    "plp": r.get("plp"),
                    "pe": r.get("pe"),
                    "value_score": r.get("value_score"),
                    "entry_score": r.get("entry_score"),
                    "flow_score": r.get("flow_score"),
                    "flow_side": r.get("flow_side"),
                    "reasons": r.get("reasons") or [],
                    "tags": r.get("tags") or [],
                }
            )
    for r in board.get("sell_alerts") or []:
        if r.get("combo_score", 0) >= min_combo_sell and r.get("alert"):
            out.append(
                {
                    "symbol": r["symbol"],
                    "name": r.get("name"),
                    "side": "sell",
                    "action": "sell",
                    "score": r.get("combo_score"),
                    "plp": r.get("plp"),
                    "pe": r.get("pe"),
                    "value_score": r.get("value_score"),
                    "exit_score": r.get("exit_score"),
                    "flow_score": r.get("flow_score"),
                    "flow_side": r.get("flow_side"),
                    "reasons": r.get("reasons") or [],
                    "tags": r.get("tags") or [],
                }
            )
    return out
