"""تحرکات بزرگان — مقایسه اسنپ‌شات‌ها با پوشش زمانی معتبر."""

from __future__ import annotations

import random
import time
from typing import Any, Callable

from app.core.config import Settings, get_settings
from app.data.store import Store
from app.models.schemas import SymbolSnapshot


def _safe(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def flow_coverage_sec(store: Store) -> float:
    """عمق واقعی تاریخچه تیک‌ها (ثانیه)."""
    stats = store.snapshot_stats()
    mn, mx = stats.get("tick_min_ts"), stats.get("tick_max_ts")
    if not mn or not mx:
        return 0.0
    return max(0.0, float(mx) - float(mn))


def ensure_flow_history(
    store: Store,
    symbols: list[SymbolSnapshot],
    build_tick_fn: Callable[[SymbolSnapshot], dict[str, Any]],
    window_sec: int = 600,
    *,
    allow_bootstrap: bool = True,
    source_hint: str = "mock",
) -> dict[str, Any]:
    """
    تضمین پوشش زمانی برای پنجره جریان.
    - اگر پوشش < window باشد و bootstrap مجاز: نقاط گذشته را می‌سازد.
    - اگر bootstrap مجاز نباشد: فقط وضعیت coverage برمی‌گرداند.
    """
    coverage = flow_coverage_sec(store)
    meta = {
        "coverage_sec": round(coverage, 1),
        "window_sec": window_sec,
        "sufficient": coverage >= max(60.0, window_sec * 0.5),
        "bootstrapped": False,
        "bootstrap_allowed": allow_bootstrap,
    }
    need = window_sec
    if coverage >= need * 0.85:
        return meta
    if not allow_bootstrap:
        return meta
    # فقط برای mock/demo — از آلوده کردن تاریخچه live جلوگیری
    if source_hint not in {"mock", "mock_fallback", "synthetic", "bootstrap"}:
        meta["bootstrap_allowed"] = False
        return meta

    now = time.time()
    # نقاط: window, 2/3, 1/3, 0 — حتی اگر ticks زیاد ولی کم‌عمق باشند
    points = sorted({int(need), int(need * 2 / 3), int(need / 3), 0}, reverse=True)
    # برای جلوگیری از انفجار DB، اگر همین الان bootstrap شده در ۲ دقیقه اخیر، skip
    # همیشه نقاط گذشته را با ts صریح می‌نویسیم
    for back in points:
        past_syms: list[SymbolSnapshot] = []
        for s in symbols:
            s2 = s.model_copy(deep=True)
            r = random.Random((hash(s.l18) & 0xFFFFFFFF) ^ int(back) ^ int(now // 300))
            if back:
                factor = 0.50 + r.random() * 0.40
                s2.tvol = max(1.0, s.tvol * factor)
                s2.Buy_I_Volume = max(0.0, s.Buy_I_Volume * factor * (0.8 + r.random() * 0.35))
                s2.Sell_I_Volume = max(0.0, s.Sell_I_Volume * factor * (0.8 + r.random() * 0.35))
                s2.Buy_CountI = max(1, int(max(1, s.Buy_CountI) * (0.9 + r.random() * 0.3)))
                s2.Sell_CountI = max(1, int(max(1, s.Sell_CountI) * (0.9 + r.random() * 0.3)))
                s2.plp = s.plp + r.uniform(-1.5, 1.5) * 0.5
                s2.pl = max(1.0, (s.py or s.pl or 1) * (1 + s2.plp / 100.0))
                s2.tval = s2.tvol * s2.pl
            past_syms.append(s2)
        ticks = [build_tick_fn(x) for x in past_syms]
        compact = [{"l18": x.l18, "pl": x.pl, "plp": x.plp, "tvol": x.tvol} for x in past_syms]
        store.save_market_snapshot(
            "bootstrap",
            compact,
            ticks,
            ts=now - back,
        )
    meta["bootstrapped"] = True
    meta["coverage_sec"] = round(flow_coverage_sec(store), 1)
    meta["sufficient"] = meta["coverage_sec"] >= max(60.0, window_sec * 0.5)
    return meta


# سازگاری با import قدیمی
def bootstrap_history_if_empty(
    store: Store,
    symbols: list[SymbolSnapshot],
    build_tick_fn: Callable[[SymbolSnapshot], dict[str, Any]],
    windows: list[int] | None = None,
) -> None:
    w = max(windows or [600])
    ensure_flow_history(
        store,
        symbols,
        build_tick_fn,
        window_sec=w,
        allow_bootstrap=True,
        source_hint="mock",
    )


def compute_big_moves(
    store: Store,
    current_symbols: list[SymbolSnapshot],
    window_sec: int = 600,
    cfg: Settings | None = None,
    min_score: float = 25.0,
) -> list[dict[str, Any]]:
    cfg = cfg or get_settings()
    now = time.time()
    past_ts = now - window_sec
    # تحمل بزرگ‌تر برای پوشش ناقص
    tol = max(180.0, window_sec * 0.45)
    past_map = store.get_ticks_near(past_ts, tolerance=tol)

    if len(past_map) < max(3, len(current_symbols) // 15):
        # fallback: قدیمی‌ترین تیک‌های موجود در بازه
        half = now - min(window_sec * 0.5, max(flow_coverage_sec(store) * 0.8, 60))
        past_map = store.get_ticks_near(half, tolerance=tol)

    # اگر هنوز خالی: از min_ts استفاده کن
    if len(past_map) < 3:
        stats = store.snapshot_stats()
        mn = stats.get("tick_min_ts")
        if mn:
            past_map = store.get_ticks_near(float(mn), tolerance=max(tol, 300))

    coverage = flow_coverage_sec(store)
    moves: list[dict[str, Any]] = []
    for s in current_symbols:
        old = past_map.get(s.l18)
        if not old:
            continue

        buy_val = s.Buy_I_Volume * s.pl
        sell_val = s.Sell_I_Volume * s.pl
        buy_pc = buy_val / s.Buy_CountI if s.Buy_CountI else 0.0
        sell_pc = sell_val / s.Sell_CountI if s.Sell_CountI else 0.0
        buy_power = buy_pc / sell_pc if sell_pc else 1.0
        net_val = (s.Buy_I_Volume - s.Sell_I_Volume) * s.pl

        old_net = _safe(old.get("individual_net_value"))
        old_vol = _safe(old.get("tvol"))
        old_plp = _safe(old.get("plp"))
        old_bp = _safe(old.get("buy_power"), 1.0)
        old_hot = _safe(old.get("hot_net"))
        old_buy_pc = _safe(old.get("buy_per_capita"))
        old_pl = _safe(old.get("pl"))
        old_ts = _safe(old.get("ts"), now)
        actual_dt = max(1.0, now - old_ts)

        hot_now = 0.0
        if buy_pc >= cfg.hot_money_threshold:
            hot_now += 40
        elif buy_pc >= cfg.hot_money_plus_min:
            hot_now += 20
        if sell_pc >= cfg.hot_money_threshold:
            hot_now -= 40
        elif sell_pc >= cfg.hot_money_plus_min:
            hot_now -= 20
        if net_val > 0:
            hot_now += min(20, net_val / 1e10)
        else:
            hot_now -= min(20, abs(net_val) / 1e10)

        delta_net = net_val - old_net
        delta_vol = s.tvol - old_vol
        delta_plp = s.plp - old_plp
        delta_bp = buy_power - old_bp
        delta_hot = hot_now - old_hot
        delta_buy_pc = buy_pc - old_buy_pc
        delta_price = s.pl - old_pl if old_pl else 0.0

        score = 0.0
        notes: list[str] = []

        if abs(delta_net) >= 5e9:
            score += min(35, abs(delta_net) / 5e9 * 10)
            notes.append("تغییر شدید خالص حقیقی")
        elif abs(delta_net) >= 1e9:
            score += min(20, abs(delta_net) / 1e9 * 5)

        if delta_buy_pc >= cfg.hot_money_plus_min * 0.5:
            score += 18
            notes.append("رشد سرانه خرید")
        if delta_hot >= 15:
            score += 15
            notes.append("پول داغ صعودی")
        elif delta_hot <= -15:
            score += 12
            notes.append("پول داغ نزولی")

        if delta_bp >= 0.5:
            score += 12
            notes.append("تقویت قدرت خریدار")
        elif delta_bp <= -0.5:
            score += 10
            notes.append("تضعیف قدرت خریدار")

        if old_vol > 0 and delta_vol / old_vol >= 0.4:
            score += 10
            notes.append("شتاب حجم")
        elif delta_vol > 0 and s.avg_vol_30d and delta_vol > s.avg_vol_30d * 0.3:
            score += 6

        if abs(delta_plp) >= 0.8:
            score += min(12, abs(delta_plp) * 4)
            notes.append(f"تأثیر قیمت {delta_plp:+.1f}٪")

        if delta_net > 0 and delta_plp > 0:
            score += 8
            notes.append("ورود پول با رشد قیمت")
        if delta_net < 0 and delta_plp < 0:
            score += 6
            notes.append("خروج پول با افت قیمت")
        if delta_net > 1e9 and delta_plp < -0.3:
            score += 10
            notes.append("واگرایی: ورود پول در منفی")
        if delta_net < -1e9 and delta_plp > 0.5:
            score += 10
            notes.append("واگرایی: خروج پول در مثبت")

        # اگر پنجره واقعی خیلی کوتاه است، امتیاز را کمی جریمه کن
        if actual_dt < window_sec * 0.4:
            score *= 0.85
            notes.append(f"پنجره کوتاه‌تر از هدف ({int(actual_dt)}s)")

        if score < min_score:
            continue

        if delta_net >= 0 and delta_hot >= 0:
            side = "inflow"
        elif delta_net < 0 and delta_hot < 0:
            side = "outflow"
        elif delta_net >= 0:
            side = "inflow"
        else:
            side = "outflow"

        moves.append(
            {
                "symbol": s.l18,
                "name": s.l30,
                "industry": s.cs,
                "side": side,
                "window_sec": window_sec,
                "actual_window_sec": round(actual_dt, 1),
                "coverage_sec": round(coverage, 1),
                "delta_net_value": delta_net,
                "delta_volume": delta_vol,
                "delta_plp": round(delta_plp, 3),
                "delta_buy_power": round(delta_bp, 3),
                "delta_hot_net": round(delta_hot, 2),
                "delta_buy_per_capita": delta_buy_pc,
                "delta_price": delta_price,
                "pl": s.pl,
                "plp": s.plp,
                "buy_power": round(buy_power, 2),
                "score": round(score, 1),
                "note": " · ".join(notes[:4]),
                "notes": notes,
            }
        )

    moves.sort(key=lambda x: x["score"], reverse=True)
    return moves
