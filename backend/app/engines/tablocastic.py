"""تابلو کستیک — شاخص‌های اختصاصی تابلوخوانی.

تعاریف عملیاتی (نزدیک به مفاهیم رایج تابلوخوانی):
- D+  : قدرت تقاضای لحظه‌ای (Demand Plus)
- M+  : مومنتوم پول حقیقی (Money Plus)
- M/D : نسبت مومنتوم به تقاضا
- عدد طلایی: ترکیب سرانه، قدرت خریدار و فشار صف
- زمان کراس: تخمین دقیقه تا کراس pl و pc (الگوی ساعت)
- قدرت صف / فشار عرضه
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from app.core.config import Settings, get_settings
from app.engines.metrics import compute_metrics
from app.models.schemas import SymbolSnapshot


def _div(a: float, b: float, default: float = 0.0) -> float:
    if not b:
        return default
    return a / b


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class TablocasticResult:
    symbol: str
    name: str
    industry: str
    pl: float
    plp: float
    pc: float
    pcp: float

    d_plus: float = 0.0          # 0..100
    m_plus: float = 0.0          # -100..100
    m_over_d: float = 0.0
    golden_number: float = 0.0   # 0..100
    queue_power: float = 0.0     # فشار صف خرید مثبت / فروش منفی
    supply_pressure: float = 0.0
    demand_pressure: float = 0.0
    cross_minutes: Optional[float] = None  # تخمین دقیقه تا کراس pl-pc
    cross_direction: str = "none"  # up | down | none
    hour_pattern: bool = False     # الگوی ساعت (pl زیر pc)
    smart_flow: float = 0.0
    quality_score: float = 0.0     # کیفیت کلی ورود پول
    grade: str = "C"               # A+ A B C D
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = self.notes or []
        return d


def compute_tablocastic(s: SymbolSnapshot, cfg: Settings | None = None) -> TablocasticResult:
    cfg = cfg or get_settings()
    m = compute_metrics(s, cfg)
    notes: list[str] = []

    # ---- Demand pressure from order book ----
    buy_val_ob = (s.qd1 * s.pd1) + (s.qd2 * s.pd2) + (s.qd3 * s.pd3)
    sell_val_ob = (s.qo1 * s.po1) + (s.qo2 * s.po2) + (s.qo3 * s.po3)
    demand_pressure = _div(buy_val_ob, max(sell_val_ob, 1.0))
    supply_pressure = _div(sell_val_ob, max(buy_val_ob, 1.0))

    # D+ : تقاضا + قدرت خریدار + نزدیکی به سقف
    d_plus = 0.0
    d_plus += _clamp(demand_pressure * 18, 0, 35)
    d_plus += _clamp((m.buy_power - 1) * 20, 0, 30)
    if m.buy_per_capita >= cfg.smart_per_capita_min:
        d_plus += _clamp(m.buy_per_capita / cfg.hot_money_threshold * 15, 0, 20)
    if m.near_buy_queue or m.in_buy_queue:
        d_plus += 12
        notes.append("نزدیک/در صف خرید")
    if s.plp >= 0:
        d_plus += min(8, s.plp * 1.5)
    d_plus = _clamp(d_plus)

    # M+ : مومنتوم پول حقیقی (-100..100)
    m_plus = 0.0
    if m.individual_net_value > 0:
        m_plus += _clamp(m.individual_net_value / 2e10 * 40, 0, 40)
    else:
        m_plus -= _clamp(abs(m.individual_net_value) / 2e10 * 40, 0, 40)
    m_plus += _clamp(m.hot_net * 0.35, -25, 25)
    if m.is_volume_spike:
        m_plus += 10 if m.individual_net_value >= 0 else -10
    if m.legal_to_individual > 0:
        m_plus += 8
        notes.append("حقوقی→حقیقی")
    elif m.legal_to_individual < 0:
        m_plus -= 6
    m_plus = max(-100.0, min(100.0, m_plus))

    m_over_d = _div(m_plus, max(d_plus, 1.0))

    # عدد طلایی: ترکیب سرانه نرمال، قدرت، حجم، تقاضا
    per_cap_norm = _clamp(m.buy_per_capita / cfg.hot_money_threshold * 40, 0, 40)
    power_norm = _clamp((m.buy_power / cfg.buy_power_strong) * 25, 0, 25)
    vol_norm = _clamp(m.volume_ratio / cfg.volume_spike_strong * 20, 0, 20)
    dem_norm = _clamp(demand_pressure * 8, 0, 15)
    golden = _clamp(per_cap_norm + power_norm + vol_norm + dem_norm)
    if m.fundamental_ok:
        golden = _clamp(golden + 5)
        notes.append(m.fundamental_note)

    # قدرت صف: مثبت = خرید، منفی = فروش
    queue_power = 0.0
    if m.in_buy_queue:
        queue_power = _clamp(30 + s.qd1 / max(s.tvol, 1) * 40, 0, 100)
    elif m.near_buy_queue:
        queue_power = _clamp(15 + demand_pressure * 10, 0, 80)
    elif m.in_sell_queue:
        queue_power = -_clamp(30 + s.qo1 / max(s.tvol, 1) * 40, 0, 100)
    elif m.near_sell_queue:
        queue_power = -_clamp(15 + supply_pressure * 10, 0, 80)
    else:
        queue_power = _clamp((demand_pressure - 1) * 20, -50, 50)

    # الگوی ساعت و زمان کراس
    hour_pattern = bool(s.pc and s.pl and s.pl < s.pc and (s.pcp - s.plp) >= 1.0)
    cross_minutes: Optional[float] = None
    cross_direction = "none"
    gap = (s.pc - s.pl) if s.pc and s.pl else 0.0
    # نرخ تقریبی تغییر pl در روز (از دامنه روزانه)
    day_range = max(abs(s.pmax - s.pmin), abs(s.pl - s.py), 1)
    # فرض: از شروع بازار تا الان بخشی از حرکت رخ داده — تخمین ساده
    speed = day_range / 180.0  # تومان بر دقیقه فرضی
    if abs(gap) > 0 and speed > 0:
        mins = abs(gap) / speed
        cross_minutes = round(min(mins, 240.0), 1)
        if gap > 0 and m.buy_power >= 1 and m.individual_net_value > 0:
            cross_direction = "up"  # pl می‌خواهد به pc برسد از پایین
        elif gap < 0 and m.buy_power < 1:
            cross_direction = "down"
        elif gap > 0:
            cross_direction = "up"
        else:
            cross_direction = "down"
    if hour_pattern:
        notes.append("الگوی ساعت (آخرین < پایانی)")

    # smart flow
    smart_flow = _clamp(
        (m.hot_net * 0.4)
        + (_clamp(m.buy_power * 15, 0, 40) if m.buy_power >= 1 else -20)
        + (10 if m.is_volume_spike else 0)
        + (8 if m.legal_to_individual > 0 else 0),
        -100,
        100,
    )

    # quality score
    quality = _clamp(
        golden * 0.35
        + d_plus * 0.25
        + _clamp(m_plus, 0, 100) * 0.2
        + m.entry_score * 0.2
    )

    if quality >= 85:
        grade = "A+"
    elif quality >= 75:
        grade = "A"
    elif quality >= 60:
        grade = "B"
    elif quality >= 45:
        grade = "C"
    else:
        grade = "D"

    if m_plus >= 30 and d_plus >= 50:
        notes.append("هم‌زمانی تقاضا و پول")
    if golden >= 70:
        notes.append("عدد طلایی بالا")

    return TablocasticResult(
        symbol=s.l18,
        name=s.l30,
        industry=s.cs,
        pl=s.pl,
        plp=s.plp,
        pc=s.pc,
        pcp=s.pcp,
        d_plus=round(d_plus, 1),
        m_plus=round(m_plus, 1),
        m_over_d=round(m_over_d, 3),
        golden_number=round(golden, 1),
        queue_power=round(queue_power, 1),
        supply_pressure=round(supply_pressure, 2),
        demand_pressure=round(demand_pressure, 2),
        cross_minutes=cross_minutes,
        cross_direction=cross_direction,
        hour_pattern=hour_pattern,
        smart_flow=round(smart_flow, 1),
        quality_score=round(quality, 1),
        grade=grade,
        notes=notes[:6],
    )


def rank_tablocastic(
    symbols: list[SymbolSnapshot],
    cfg: Settings | None = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    cfg = cfg or get_settings()
    rows = [compute_tablocastic(s, cfg).to_dict() for s in symbols if s.l18]
    rows.sort(key=lambda r: (r["quality_score"], r["golden_number"], r["d_plus"]), reverse=True)
    return rows[:limit]
