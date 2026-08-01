"""محاسبه متریک‌های مشتق‌شده از تابلو."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.models.schemas import (
    AlertLevel,
    DerivedMetrics,
    SignalSide,
    SymbolSnapshot,
)


def _div(a: float, b: float, default: float = 0.0) -> float:
    if not b:
        return default
    return a / b


def compute_metrics(s: SymbolSnapshot, cfg: Settings | None = None) -> DerivedMetrics:
    cfg = cfg or get_settings()
    m = DerivedMetrics(symbol=s.l18)

    # --- سرانه خرید/فروش حقیقی (ریال/تومان تقریبی روی حجم*قیمت) ---
    buy_val_i = s.Buy_I_Volume * s.pl
    sell_val_i = s.Sell_I_Volume * s.pl
    m.buy_per_capita = _div(buy_val_i, s.Buy_CountI)
    m.sell_per_capita = _div(sell_val_i, s.Sell_CountI)
    m.buy_power = _div(m.buy_per_capita, m.sell_per_capita, default=1.0)

    m.individual_net_volume = s.Buy_I_Volume - s.Sell_I_Volume
    m.individual_net_value = m.individual_net_volume * s.pl
    # جابجایی تقریبی حقوقی->حقیقی
    m.legal_to_individual = (s.Sell_N_Volume - s.Buy_N_Volume) * s.pl

    avg_vol = s.avg_vol_30d or max(s.bvol * 3, 1)
    m.volume_ratio = _div(s.tvol, avg_vol)
    avg_val = s.avg_val_30d or avg_vol * max(s.py, s.pl, 1)
    m.value_ratio = _div(s.tval, avg_val)
    m.is_volume_spike = m.volume_ratio >= cfg.volume_spike_ratio
    m.is_strong_volume_spike = m.volume_ratio >= cfg.volume_spike_strong

    # فاصله تا سقف/کف مجاز
    if s.tmax > 0 and s.pl > 0:
        m.dist_to_ceiling_pct = (s.tmax - s.pl) / s.tmax * 100
    if s.tmin > 0 and s.pl > 0:
        m.dist_to_floor_pct = (s.pl - s.tmin) / s.tmin * 100

    m.in_buy_queue = (
        s.tmax > 0
        and s.pl >= s.tmax * 0.998
        and s.qd1 > 0
        and (s.qo1 <= 0 or s.po1 >= s.tmax * 0.999)
    )
    m.in_sell_queue = (
        s.tmin > 0
        and s.pl <= s.tmin * 1.002
        and s.qo1 > 0
        and (s.qd1 <= 0 or s.pd1 <= s.tmin * 1.001)
    )
    m.near_buy_queue = (not m.in_buy_queue) and (
        m.dist_to_ceiling_pct <= cfg.near_buy_queue_pct
        or (s.plp >= 4.0 and s.qd1 > s.qo1 * 2)
    )
    m.near_sell_queue = (not m.in_sell_queue) and (
        m.dist_to_floor_pct <= cfg.near_buy_queue_pct
        or (s.plp <= -4.0 and s.qo1 > s.qd1 * 2)
    )

    # پول داغ تقریبی از سرانه
    # اگر سرانه خرید بالا و قدرت خریدار قوی → امتیاز خرید داغ
    hot_buy = 0.0
    hot_sell = 0.0
    if m.buy_per_capita >= cfg.hot_money_threshold:
        hot_buy += min(100, m.buy_per_capita / cfg.hot_money_threshold * 40)
    elif m.buy_per_capita >= cfg.hot_money_plus_min:
        hot_buy += min(60, m.buy_per_capita / cfg.hot_money_plus_min * 20)
    if m.sell_per_capita >= cfg.hot_money_threshold:
        hot_sell += min(100, m.sell_per_capita / cfg.hot_money_threshold * 40)
    elif m.sell_per_capita >= cfg.hot_money_plus_min:
        hot_sell += min(60, m.sell_per_capita / cfg.hot_money_plus_min * 20)

    # تقویت با نسبت حجم و ارزش خرید حقیقی
    if m.is_volume_spike and m.buy_power >= cfg.buy_power_min:
        hot_buy += 15
    if m.is_volume_spike and m.buy_power > 0 and m.buy_power < 0.8:
        hot_sell += 15
    if m.individual_net_value > 0:
        hot_buy += min(20, m.individual_net_value / 1e10)
    else:
        hot_sell += min(20, abs(m.individual_net_value) / 1e10)

    m.hot_buy_score = min(100.0, hot_buy)
    m.hot_sell_score = min(100.0, hot_sell)
    m.hot_net = m.hot_buy_score - m.hot_sell_score

    # بازی بازار: تقسیم فرضی بر اساس سرانه
    # سرانه خیلی بالا → بزرگان، متوسط → mid، پایین → خرد
    big = mid = retail = 0.0
    if m.buy_per_capita >= cfg.hot_money_threshold:
        big += 0.6
    elif m.buy_per_capita >= cfg.hot_money_plus_min:
        mid += 0.5
    else:
        retail += 0.4
    if m.sell_per_capita >= cfg.hot_money_threshold:
        big -= 0.6
    elif m.sell_per_capita >= cfg.hot_money_plus_min:
        mid -= 0.5
    else:
        retail -= 0.4
    # جریان خالص
    net_sign = 1 if m.individual_net_value >= 0 else -1
    if abs(m.buy_per_capita) >= cfg.hot_money_threshold:
        big += 0.3 * net_sign
    elif abs(m.buy_per_capita) >= cfg.hot_money_plus_min:
        mid += 0.3 * net_sign
    else:
        retail += 0.3 * net_sign

    def _clamp_bias(x: float) -> float:
        return max(-1.0, min(1.0, x))

    m.big_player_bias = _clamp_bias(big)
    m.mid_player_bias = _clamp_bias(mid)
    m.retail_bias = _clamp_bias(retail)

    # بنیادی
    pe = s.pe
    pe_score = 0.0
    fund_ok = False
    note = ""
    if pe is not None and pe > 0:
        if pe <= cfg.pe_max_attractive:
            pe_score = 90 - pe * 2
            fund_ok = True
            note = f"P/E جذاب ({pe:.1f})"
        elif pe <= cfg.pe_max_ok:
            pe_score = 55 - (pe - cfg.pe_max_attractive) * 2
            fund_ok = True
            note = f"P/E قابل قبول ({pe:.1f})"
        elif pe < 40:
            pe_score = max(5, 40 - pe)
            note = f"P/E بالا ({pe:.1f})"
        else:
            pe_score = 0
            note = f"P/E بسیار بالا ({pe:.1f})"
    elif pe is not None and pe < 0:
        pe_score = 5
        note = "زیان‌ده (EPS منفی)"
    else:
        note = "بدون P/E"
    if s.eps and s.eps > 0 and fund_ok:
        pe_score = min(100, pe_score + 5)
    m.pe_score = max(0, min(100, pe_score))
    m.fundamental_ok = fund_ok
    m.fundamental_note = note

    # -------- امتیاز ورود (اولویت اصلی شما) --------
    entry = 0.0
    reasons: list[str] = []
    tags: list[str] = []

    # 1) حجم مشکوک
    if m.is_strong_volume_spike:
        entry += 22
        reasons.append(f"حجم خیلی مشکوک ×{m.volume_ratio:.1f}")
        tags.append("حجم‌مشکوک")
    elif m.is_volume_spike:
        entry += 14
        reasons.append(f"حجم مشکوک ×{m.volume_ratio:.1f}")
        tags.append("حجم‌مشکوک")
    elif m.volume_ratio >= 1.3:
        entry += 6

    # 2) قدرت خریدار / سرانه
    if m.buy_power >= cfg.buy_power_strong and m.buy_per_capita >= cfg.smart_per_capita_min:
        entry += 22
        reasons.append(f"قدرت خریدار قوی {m.buy_power:.2f} | سرانه {_fmt_money(m.buy_per_capita)}")
        tags.append("پول‌هوشمند")
    elif m.buy_power >= cfg.buy_power_min:
        entry += 12
        reasons.append(f"قدرت خریدار {m.buy_power:.2f}")
        tags.append("قدرت‌خریدار")
    elif m.buy_per_capita >= cfg.smart_per_capita_min:
        entry += 8
        reasons.append(f"سرانه خرید بالا {_fmt_money(m.buy_per_capita)}")

    # 3) ورود پول حقیقی
    if m.individual_net_value > 0:
        entry += min(15, 5 + m.individual_net_value / 5e10)
        if m.individual_net_value > 1e10:
            reasons.append("ورود پول حقیقی خالص")
            tags.append("ورود‌پول")
    else:
        entry -= min(12, abs(m.individual_net_value) / 5e10)

    # 4) جابجایی حقوقی به حقیقی
    if m.legal_to_individual > 0 and m.buy_power >= 1.2:
        entry += 10
        reasons.append("جابجایی حقوقی→حقیقی")
        tags.append("حقوقی‌به‌حقیقی")

    # 5) شکار در منفی + احتمال صف خرید
    if s.plp <= cfg.negative_plp_max:
        if m.buy_power >= cfg.buy_power_min and m.is_volume_spike:
            entry += 18
            reasons.append(f"شکار در منفی ({s.plp:.1f}٪) با حجم و قدرت")
            tags.append("شکار‌منفی")
        elif m.buy_power >= cfg.buy_power_min:
            entry += 10
            reasons.append(f"تحرک در منفی ({s.plp:.1f}٪)")
            tags.append("منفی‌قوی")
        if s.plp <= cfg.deep_negative_plp and m.buy_power >= cfg.buy_power_strong:
            entry += 6
            reasons.append("جمع‌آوری در منفی عمیق")

    # تقاضا سنگین در بهترین خرید
    demand_pressure = _div(s.qd1 * s.pd1, max(s.qo1 * s.po1, 1))
    if demand_pressure >= 2 and s.plp < 2:
        entry += 8
        reasons.append("فشار تقاضا روی تابلو")
        tags.append("فشار‌تقاضا")

    if m.near_buy_queue and m.buy_power >= 1.2:
        entry += 10
        reasons.append("نزدیک صف خرید")
        tags.append("نزدیک‌صف‌خرید")
    if m.in_buy_queue:
        entry += 4
        tags.append("صف‌خرید")

    # 6) بنیادی
    if m.fundamental_ok:
        bonus = m.pe_score * 0.12
        entry += bonus
        reasons.append(m.fundamental_note)
        tags.append("بنیادی‌خوب")
    elif pe is not None and pe > 25:
        entry -= 5

    # پول داغ
    if m.hot_net >= 25:
        entry += 10
        reasons.append("برآیند پول داغ مثبت")
        tags.append("پول‌داغ")
    if m.big_player_bias >= 0.4:
        entry += 8
        reasons.append("ورود بزرگان")
        tags.append("بزرگان")

    # -------- امتیاز خروج --------
    exit_s = 0.0
    if m.individual_net_value < 0:
        exit_s += min(25, 8 + abs(m.individual_net_value) / 4e10)
    if m.buy_power > 0 and m.buy_power < 0.75:
        exit_s += 18
    if m.sell_per_capita >= cfg.hot_money_threshold:
        exit_s += 15
    if m.hot_net <= -20:
        exit_s += 15
    if m.is_volume_spike and m.individual_net_value < 0:
        exit_s += 12
    if m.near_sell_queue or m.in_sell_queue:
        exit_s += 12
    if s.plp > 3 and m.buy_power < 1 and m.individual_net_value < 0:
        exit_s += 10  # توزیع در مثبت
    if m.big_player_bias <= -0.4:
        exit_s += 10
    if demand_pressure > 0 and demand_pressure < 0.5 and s.plp > 0:
        exit_s += 8

    exit_reasons: list[str] = []
    if exit_s >= 20:
        if m.individual_net_value < 0:
            exit_reasons.append("خروج پول حقیقی")
        if m.buy_power < 0.85:
            exit_reasons.append(f"ضعف قدرت خریدار ({m.buy_power:.2f})")
        if m.hot_net < 0:
            exit_reasons.append("برآیند پول داغ منفی")
        if m.is_volume_spike and m.individual_net_value < 0:
            exit_reasons.append("حجم بالا با خروج پول")
        if m.big_player_bias < 0:
            exit_reasons.append("خروج بزرگان")

    m.entry_score = max(0.0, min(100.0, entry))
    m.exit_score = max(0.0, min(100.0, exit_s))
    m.watch_score = max(0.0, m.entry_score * 0.6 + (100 - m.exit_score) * 0.2)

    # تصمیم سمت
    if m.exit_score >= cfg.exit_score_alert and m.exit_score >= m.entry_score + 5:
        m.side = SignalSide.EXIT
        m.reasons = exit_reasons or ["ریسک خروج پول / عرضه"]
        m.tags = list(dict.fromkeys(tags + ["خروج"]))
        if m.exit_score >= 80:
            m.alert_level = AlertLevel.CRITICAL
        elif m.exit_score >= 70:
            m.alert_level = AlertLevel.HIGH
        else:
            m.alert_level = AlertLevel.MEDIUM
    elif m.entry_score >= cfg.entry_score_alert:
        m.side = SignalSide.ENTRY
        m.reasons = reasons[:6]
        m.tags = list(dict.fromkeys(tags))
        if m.entry_score >= cfg.entry_score_strong:
            m.alert_level = AlertLevel.CRITICAL if m.entry_score >= 90 else AlertLevel.HIGH
        else:
            m.alert_level = AlertLevel.MEDIUM
    elif m.entry_score >= 45 or m.hot_buy_score >= 40:
        m.side = SignalSide.WATCH
        m.reasons = reasons[:4] or ["نیاز به رصد"]
        m.tags = list(dict.fromkeys(tags + ["رصد"]))
        m.alert_level = AlertLevel.LOW
    else:
        m.side = SignalSide.NEUTRAL
        m.reasons = []
        m.tags = []
        m.alert_level = AlertLevel.LOW

    return m


def _fmt_money(v: float) -> str:
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:.0f}"
