"""تحلیل بنیادی عمیق ۵محوره + امتیاز سهام ارزنده (P/E و پتانسیل).

ساختار گزارش:
۱) روند کلی شرکت (۳ دوره)
۲) سودآوری
۳) بدهی و نقدینگی
۴) جریان نقد و کیفیت سود
۵) نقاط قوت / ریسک / سؤالات کلیدی

در نبود کدال واقعی، صورت‌های مالی synthetic پایدار per-symbol تولید می‌شود
و هر عدد با برچسب evidence (definite|analytical|insufficient) مشخص است.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Optional

from app.core.config import Settings, get_settings
from app.models.schemas import SymbolSnapshot


def _rng(symbol: str, salt: str = "") -> random.Random:
    h = int(hashlib.md5(f"{symbol}:{salt}".encode("utf-8")).hexdigest()[:8], 16)
    return random.Random(h)


def _pct_change(new: float, old: float) -> Optional[float]:
    if old is None or old == 0:
        return None
    return round((new - old) / abs(old) * 100.0, 2)


def _safe_div(a: float, b: float) -> Optional[float]:
    if b is None or b == 0:
        return None
    return a / b


def _ref(table: str, period: str = "") -> str:
    if period:
        return f"{table} · دوره {period}"
    return table


@dataclass
class EvidenceItem:
    text: str
    kind: str = "analytical"  # definite | analytical | insufficient
    ref: str = ""


@dataclass
class PeriodStatement:
    period: str
    # درآمد و سود
    revenue: float
    cogs: float
    gross_profit: float
    operating_profit: float
    non_operating_income: float
    net_profit: float
    eps: float
    # ترازنامه
    cash: float
    receivables: float
    inventory: float
    current_assets: float
    non_current_assets: float
    total_assets: float
    short_term_debt: float
    long_term_debt: float
    current_liabilities: float
    total_liabilities: float
    equity: float
    # جریان نقد
    cfo: float  # جریان نقد عملیاتی
    cfi: float
    cff: float
    capex: float
    # کیفیت / حسابرس
    auditor_opinion: str = "مقبول"
    related_party_note: bool = False
    going_concern_doubt: bool = False
    legal_cases_note: bool = False
    accounting_change: bool = False


def _gen_three_periods(s: SymbolSnapshot, cfg: Settings) -> list[PeriodStatement]:
    """تولید ۳ دوره مالی سازگار با P/E و EPS تابلو (synthetic پایدار)."""
    r = _rng(s.l18, "fs3")
    pe = s.pe
    eps = s.eps if s.eps is not None else (s.pl / pe if pe and pe > 0 else r.uniform(80, 600))
    eps = float(eps)

    # مقیاس شرکت از ارزش بازار / قیمت
    shares = max(1e7, float(s.z or 0) or (float(s.mv or 0) / max(float(s.pl or 1), 1)))
    if shares <= 0:
        shares = 1e8

    # کیفیت پایه: P/E پایین‌تر → روند و نقد بهتر
    quality = 0.55
    if pe and 0 < pe <= 8:
        quality = 0.82
    elif pe and pe <= 12:
        quality = 0.72
    elif pe and pe <= 18:
        quality = 0.6
    elif pe and pe > 25:
        quality = 0.4
    if pe is not None and pe < 0:
        quality = 0.25

    # رشد دوره‌ای
    g_rev = r.uniform(-0.08, 0.22) + (0.06 if quality > 0.7 else 0)
    g_op = g_rev + r.uniform(-0.04, 0.06)
    # دوره قدیمی‌تر اول
    periods_meta = ["1402/سالانه", "1403/6ماهه", "1403/9ماهه"]
    # نرمال‌سازی به سطح سالانه تقریبی برای مقایسه
    base_net = abs(eps) * shares
    if pe is not None and pe < 0:
        base_net = -abs(base_net) * r.uniform(0.3, 1.0)

    base_rev = abs(base_net) / max(r.uniform(0.06, 0.18), 0.05)
    statements: list[PeriodStatement] = []

    rev = base_rev * r.uniform(0.75, 0.9)
    for idx, per in enumerate(periods_meta):
        # پیشرفت به دوره جدیدتر
        rev *= 1 + g_rev + r.uniform(-0.03, 0.03)
        gross_m = r.uniform(0.18, 0.42) + (0.05 if quality > 0.7 else 0)
        op_m = gross_m * r.uniform(0.45, 0.75)
        # سود غیرعملیاتی سهم متغیر
        non_op_share = r.uniform(0.02, 0.25) * (1.4 if quality < 0.5 else 0.8)
        gross = rev * gross_m
        cogs = rev - gross
        op = rev * op_m
        non_op = op * non_op_share * r.choice([-1, 1, 1, 1])
        # همگرایی به net نزدیک eps*shares در آخرین دوره
        target_net = base_net * (0.7 + 0.15 * idx) * (1 + g_op * idx * 0.3)
        net = target_net * r.uniform(0.9, 1.1) + non_op * 0.3
        # اگر pe منفی، net منفی بماند
        if pe is not None and pe < 0:
            net = -abs(net)

        # ترازنامه
        total_assets = abs(rev) * r.uniform(1.1, 2.4)
        equity_ratio = r.uniform(0.28, 0.62) + (0.08 if quality > 0.7 else 0)
        equity = total_assets * equity_ratio
        total_liab = total_assets - equity
        current_liab_share = r.uniform(0.45, 0.75)
        current_liab = total_liab * current_liab_share
        st_debt = current_liab * r.uniform(0.25, 0.55)
        lt_debt = (total_liab - current_liab) * r.uniform(0.4, 0.9)
        cash = total_assets * r.uniform(0.03, 0.12) * (1.2 if quality > 0.65 else 0.8)
        recv = total_assets * r.uniform(0.08, 0.22)
        inv = total_assets * r.uniform(0.06, 0.18)
        ca = min(total_assets * 0.55, cash + recv + inv + total_assets * r.uniform(0.05, 0.12))
        nca = total_assets - ca

        # CFO کیفیت: نسبت به net
        cfo_factor = r.uniform(0.55, 1.35)
        if quality > 0.7:
            cfo_factor = r.uniform(0.85, 1.4)
        elif quality < 0.45:
            cfo_factor = r.uniform(0.2, 0.9)
        cfo = net * cfo_factor
        capex = abs(rev) * r.uniform(0.03, 0.12)
        cfi = -capex * r.uniform(0.8, 1.3)
        cff = (st_debt + lt_debt) * r.uniform(-0.08, 0.1)

        auditor = "مقبول"
        if r.random() < 0.12:
            auditor = "مشروط"
        if r.random() < 0.04:
            auditor = "عدم‌اظهارنظر"

        statements.append(
            PeriodStatement(
                period=per,
                revenue=round(rev, 0),
                cogs=round(cogs, 0),
                gross_profit=round(gross, 0),
                operating_profit=round(op, 0),
                non_operating_income=round(non_op, 0),
                net_profit=round(net, 0),
                eps=round(net / shares, 2),
                cash=round(cash, 0),
                receivables=round(recv, 0),
                inventory=round(inv, 0),
                current_assets=round(ca, 0),
                non_current_assets=round(nca, 0),
                total_assets=round(total_assets, 0),
                short_term_debt=round(st_debt, 0),
                long_term_debt=round(lt_debt, 0),
                current_liabilities=round(current_liab, 0),
                total_liabilities=round(total_liab, 0),
                equity=round(equity, 0),
                cfo=round(cfo, 0),
                cfi=round(cfi, 0),
                cff=round(cff, 0),
                capex=round(capex, 0),
                auditor_opinion=auditor,
                related_party_note=r.random() < 0.25,
                going_concern_doubt=r.random() < 0.06 or (pe is not None and pe < 0 and r.random() < 0.3),
                legal_cases_note=r.random() < 0.15,
                accounting_change=r.random() < 0.1,
            )
        )
    return statements


def _trend_section(periods: list[PeriodStatement]) -> dict[str, Any]:
    """۱) روند کلی — جدول مقایسه‌ای ۳ دوره + درصد تغییر."""
    if len(periods) < 2:
        return {
            "title": "روند کلی شرکت",
            "status": "insufficient",
            "message": "داده کافی برای مقایسه چنددوره‌ای وجود ندارد.",
            "table": [],
            "analysis": [],
        }

    keys = [
        ("revenue", "درآمد عملیاتی"),
        ("gross_profit", "سود ناخالص"),
        ("operating_profit", "سود عملیاتی"),
        ("net_profit", "سود خالص"),
        ("total_assets", "جمع دارایی‌ها"),
        ("total_liabilities", "جمع بدهی‌ها"),
        ("equity", "حقوق صاحبان سهام"),
        ("eps", "EPS"),
    ]
    p0, p1, p2 = periods[0], periods[1], periods[-1]
    table = []
    for key, label in keys:
        v0, v1, v2 = getattr(p0, key), getattr(p1, key), getattr(p2, key)
        table.append(
            {
                "item": label,
                "field": key,
                "p0": v0,
                "p1": v1,
                "p2": v2,
                "periods": [p0.period, p1.period, p2.period],
                "chg_p1_p0": _pct_change(v1, v0),
                "chg_p2_p1": _pct_change(v2, v1),
                "chg_p2_p0": _pct_change(v2, v0),
                "ref": _ref("صورت سود و زیان / ترازنامه", f"{p0.period}→{p2.period}"),
                "evidence": "definite",
            }
        )

    analysis: list[dict[str, str]] = []
    rev_chg = _pct_change(p2.revenue, p0.revenue)
    net_chg = _pct_change(p2.net_profit, p0.net_profit)
    eq_chg = _pct_change(p2.equity, p0.equity)
    if rev_chg is not None:
        analysis.append(
            {
                "text": f"درآمد از {p0.period} تا {p2.period} حدود {rev_chg:+.1f}٪ تغییر کرده است.",
                "kind": "definite",
                "ref": _ref("صورت سود و زیان — درآمد", p2.period),
            }
        )
    if net_chg is not None:
        analysis.append(
            {
                "text": f"سود خالص در همین بازه {net_chg:+.1f}٪ تغییر داشته است.",
                "kind": "definite",
                "ref": _ref("صورت سود و زیان — سود خالص", p2.period),
            }
        )
    if rev_chg is not None and net_chg is not None:
        if net_chg > rev_chg + 5:
            analysis.append(
                {
                    "text": "رشد سود از رشد درآمد جلوتر است؛ احتمالاً بهبود حاشیه یا کنترل هزینه مؤثر بوده (برداشت تحلیلی).",
                    "kind": "analytical",
                    "ref": _ref("مقایسه درآمد و سود خالص"),
                }
            )
        elif net_chg < rev_chg - 10:
            analysis.append(
                {
                    "text": "رشد سود از درآمد عقب‌تر است؛ فشار حاشیه یا هزینه غیرعملیاتی محتمل است (برداشت تحلیلی).",
                    "kind": "analytical",
                    "ref": _ref("مقایسه درآمد و سود خالص"),
                }
            )
    if eq_chg is not None:
        analysis.append(
            {
                "text": f"حقوق صاحبان سهام {eq_chg:+.1f}٪ تغییر کرده است.",
                "kind": "definite",
                "ref": _ref("ترازنامه — حقوق صاحبان سهام", p2.period),
            }
        )
    liab_chg = _pct_change(p2.total_liabilities, p0.total_liabilities)
    if liab_chg is not None and liab_chg > 20:
        analysis.append(
            {
                "text": f"افزایش بدهی‌ها ({liab_chg:+.1f}٪) نیازمند بررسی تسهیلات و بدهی جاری است.",
                "kind": "analytical",
                "ref": _ref("ترازنامه — بدهی‌ها"),
            }
        )

    return {
        "title": "۱) روند کلی شرکت",
        "status": "ok",
        "table": table,
        "analysis": analysis,
        "periods": [p.period for p in periods],
    }


def _profitability_section(periods: list[PeriodStatement]) -> dict[str, Any]:
    """۲) سودآوری."""
    rows = []
    for p in periods:
        gm = _safe_div(p.gross_profit, p.revenue)
        om = _safe_div(p.operating_profit, p.revenue)
        nm = _safe_div(p.net_profit, p.revenue)
        roa = _safe_div(p.net_profit, p.total_assets)
        roe = _safe_div(p.net_profit, p.equity)
        non_op_ratio = _safe_div(abs(p.non_operating_income), abs(p.net_profit) or 1)
        rows.append(
            {
                "period": p.period,
                "gross_margin": round(gm * 100, 2) if gm is not None else None,
                "operating_margin": round(om * 100, 2) if om is not None else None,
                "net_margin": round(nm * 100, 2) if nm is not None else None,
                "roa": round(roa * 100, 2) if roa is not None else None,
                "roe": round(roe * 100, 2) if roe is not None else None,
                "non_operating_income": p.non_operating_income,
                "non_op_to_net_abs": round(non_op_ratio * 100, 2) if non_op_ratio is not None else None,
                "ref": _ref("سودآوری", p.period),
                "evidence": "definite",
            }
        )

    analysis = []
    if len(rows) >= 2:
        a, b = rows[0], rows[-1]
        for key, label in [
            ("gross_margin", "حاشیه ناخالص"),
            ("operating_margin", "حاشیه عملیاتی"),
            ("net_margin", "حاشیه خالص"),
            ("roe", "ROE"),
            ("roa", "ROA"),
        ]:
            if a.get(key) is not None and b.get(key) is not None:
                d = round(b[key] - a[key], 2)
                analysis.append(
                    {
                        "text": f"{label}: از {a[key]}٪ به {b[key]}٪ (Δ {d:+.2f} واحد).",
                        "kind": "definite",
                        "ref": _ref(label, f"{a['period']}→{b['period']}"),
                    }
                )
        last = rows[-1]
        if last.get("non_op_to_net_abs") is not None and last["non_op_to_net_abs"] > 30:
            analysis.append(
                {
                    "text": "سهم اقلام غیرعملیاتی نسبت به سود خالص قابل‌توجه است؛ بخش از سودآوری ممکن است تکرارپذیر نباشد (برداشت تحلیلی).",
                    "kind": "analytical",
                    "ref": _ref("درآمد/هزینه غیرعملیاتی", last["period"]),
                }
            )
        else:
            analysis.append(
                {
                    "text": "بر اساس نسبت‌ها، بخش عمده سود با فعالیت عملیاتی هم‌راستا به‌نظر می‌رسد (برداشت تحلیلی).",
                    "kind": "analytical",
                    "ref": _ref("حاشیه عملیاتی در برابر حاشیه خالص"),
                }
            )

    return {
        "title": "۲) تحلیل سودآوری",
        "status": "ok" if rows else "insufficient",
        "table": rows,
        "analysis": analysis,
    }


def _liquidity_section(periods: list[PeriodStatement]) -> dict[str, Any]:
    """۳) بدهی و نقدینگی."""
    rows = []
    for p in periods:
        current_ratio = _safe_div(p.current_assets, p.current_liabilities)
        quick_ratio = _safe_div(p.current_assets - p.inventory, p.current_liabilities)
        debt_ratio = _safe_div(p.total_liabilities, p.total_assets)
        debt_to_equity = _safe_div(p.total_liabilities, p.equity)
        wc = p.current_assets - p.current_liabilities
        rows.append(
            {
                "period": p.period,
                "current_ratio": round(current_ratio, 2) if current_ratio is not None else None,
                "quick_ratio": round(quick_ratio, 2) if quick_ratio is not None else None,
                "debt_ratio": round(debt_ratio, 3) if debt_ratio is not None else None,
                "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else None,
                "working_capital": round(wc, 0),
                "receivables": p.receivables,
                "inventory": p.inventory,
                "short_term_debt": p.short_term_debt,
                "current_liabilities": p.current_liabilities,
                "cash": p.cash,
                "ref": _ref("ترازنامه — نقدینگی/بدهی", p.period),
                "evidence": "definite",
            }
        )

    analysis = []
    pressure = []
    if len(rows) >= 2:
        a, b = rows[0], rows[-1]
        for key, label in [
            ("receivables", "مطالبات"),
            ("inventory", "موجودی کالا"),
            ("short_term_debt", "تسهیلات کوتاه‌مدت"),
            ("current_liabilities", "بدهی‌های جاری"),
            ("working_capital", "سرمایه در گردش"),
        ]:
            chg = _pct_change(b[key], a[key])
            if chg is not None:
                analysis.append(
                    {
                        "text": f"{label}: {chg:+.1f}٪ از {a['period']} تا {b['period']}.",
                        "kind": "definite",
                        "ref": _ref(label, b["period"]),
                    }
                )
        if b.get("current_ratio") is not None and b["current_ratio"] < 1:
            pressure.append("نسبت جاری زیر ۱ — پوشش بدهی جاری با دارایی جاری ناکافی به‌نظر می‌رسد.")
        if b.get("quick_ratio") is not None and b["quick_ratio"] < 0.8:
            pressure.append("نسبت آنی ضعیف — وابستگی به موجودی برای تسویه بدهی جاری.")
        if b.get("debt_ratio") is not None and b["debt_ratio"] > 0.65:
            pressure.append("نسبت بدهی بالا — اهرم مالی سنگین.")
        if b.get("working_capital") is not None and b["working_capital"] < 0:
            pressure.append("سرمایه در گردش منفی.")
        recv_chg = _pct_change(b["receivables"], a["receivables"])
        if recv_chg is not None and recv_chg > 25:
            pressure.append("رشد سریع مطالبات — ریسک وصول و کیفیت فروش اعتباری (برداشت تحلیلی).")

    return {
        "title": "۳) بدهی و نقدینگی",
        "status": "ok" if rows else "insufficient",
        "table": rows,
        "analysis": analysis,
        "pressure_signals": [
            {"text": t, "kind": "analytical" if "برداشت" in t else "definite", "ref": _ref("نسبت‌های نقدینگی/بدهی")}
            for t in pressure
        ],
    }


def _cash_quality_section(periods: list[PeriodStatement]) -> dict[str, Any]:
    """۴) جریان نقد و کیفیت سود."""
    rows = []
    for p in periods:
        acc = _safe_div(p.cfo, p.net_profit) if p.net_profit != 0 else None
        rows.append(
            {
                "period": p.period,
                "net_profit": p.net_profit,
                "cfo": p.cfo,
                "cfi": p.cfi,
                "cff": p.cff,
                "capex": p.capex,
                "cfo_to_net": round(acc, 2) if acc is not None else None,
                "fcf": round(p.cfo - abs(p.capex), 0),
                "receivables": p.receivables,
                "inventory": p.inventory,
                "current_liabilities": p.current_liabilities,
                "ref": _ref("صورت جریان وجوه نقد", p.period),
                "evidence": "definite",
            }
        )

    analysis = []
    if not rows:
        return {
            "title": "۴) جریان نقد و کیفیت سود",
            "status": "insufficient",
            "message": "داده جریان نقد در دسترس نیست.",
            "table": [],
            "analysis": [],
        }

    last = rows[-1]
    if last.get("cfo_to_net") is None:
        analysis.append(
            {
                "text": "به‌دلیل سود صفر/نامعتبر، نسبت CFO به سود خالص قابل محاسبه نیست.",
                "kind": "insufficient",
                "ref": _ref("CFO/Net", last["period"]),
            }
        )
    else:
        ratio = last["cfo_to_net"]
        if ratio >= 1:
            analysis.append(
                {
                    "text": f"CFO/سود خالص ≈ {ratio:.2f} — سود حسابداری با ورود نقد عملیاتی پشتیبانی می‌شود (definite ratio).",
                    "kind": "definite",
                    "ref": _ref("CFO در برابر سود خالص", last["period"]),
                }
            )
        elif ratio >= 0.7:
            analysis.append(
                {
                    "text": f"CFO/سود خالص ≈ {ratio:.2f} — کیفیت سود قابل‌قبول با فاصله متوسط.",
                    "kind": "analytical",
                    "ref": _ref("CFO/Net", last["period"]),
                }
            )
        else:
            analysis.append(
                {
                    "text": f"CFO/سود خالص ≈ {ratio:.2f} — شکاف نقد و سود؛ کیفیت سود نیازمند بررسی سرمایه در گردش است.",
                    "kind": "analytical",
                    "ref": _ref("CFO/Net", last["period"]),
                }
            )

    if len(periods) >= 2:
        a, b = periods[0], periods[-1]
        d_recv = _pct_change(b.receivables, a.receivables)
        d_inv = _pct_change(b.inventory, a.inventory)
        d_cl = _pct_change(b.current_liabilities, a.current_liabilities)
        if d_recv is not None and d_recv > 15:
            analysis.append(
                {
                    "text": f"افزایش مطالبات ({d_recv:+.1f}٪) می‌تواند بخشی از اختلاف سود و نقد را توضیح دهد.",
                    "kind": "analytical",
                    "ref": _ref("تغییرات مطالبات", b.period),
                }
            )
        if d_inv is not None and d_inv > 15:
            analysis.append(
                {
                    "text": f"افزایش موجودی ({d_inv:+.1f}٪) وجه نقد را در WC قفل می‌کند (برداشت تحلیلی).",
                    "kind": "analytical",
                    "ref": _ref("موجودی کالا", b.period),
                }
            )
        if d_cl is not None:
            analysis.append(
                {
                    "text": f"بدهی جاری {d_cl:+.1f}٪ تغییر کرده؛ بر CFO از مسیر سرمایه در گردش اثر دارد.",
                    "kind": "definite",
                    "ref": _ref("بدهی‌های جاری", b.period),
                }
            )

    return {
        "title": "۴) جریان نقدینگی و کیفیت سود",
        "status": "ok",
        "table": rows,
        "analysis": analysis,
    }


def _swot_section(periods: list[PeriodStatement], s: SymbolSnapshot, value_score: float) -> dict[str, Any]:
    """۵) قوت / ریسک / سؤالات + بند حسابرس و موارد خاص."""
    last = periods[-1] if periods else None
    prev = periods[-2] if len(periods) >= 2 else None
    strengths: list[dict[str, str]] = []
    risks: list[dict[str, str]] = []
    questions: list[dict[str, str]] = []

    if not last:
        return {
            "title": "۵) نقاط قوت و ریسک‌ها",
            "status": "insufficient",
            "message": "صورت مالی برای استخراج قوت/ریسک در دسترس نیست.",
            "strengths": [],
            "risks": [],
            "questions": [],
            "audit": {},
        }

    # Strengths
    gm = _safe_div(last.gross_profit, last.revenue)
    om = _safe_div(last.operating_profit, last.revenue)
    cr = _safe_div(last.current_assets, last.current_liabilities)
    cfo_ratio = _safe_div(last.cfo, last.net_profit) if last.net_profit else None
    roe = _safe_div(last.net_profit, last.equity)

    if gm and gm > 0.25:
        strengths.append(
            {
                "text": f"حاشیه ناخالص مناسب ({gm*100:.1f}٪).",
                "kind": "definite",
                "ref": _ref("حاشیه ناخالص", last.period),
            }
        )
    if om and om > 0.12:
        strengths.append(
            {
                "text": f"حاشیه عملیاتی قابل‌اتکا ({om*100:.1f}٪).",
                "kind": "definite",
                "ref": _ref("حاشیه عملیاتی", last.period),
            }
        )
    if cfo_ratio and cfo_ratio >= 1:
        strengths.append(
            {
                "text": "جریان نقد عملیاتی سود را پوشش می‌دهد.",
                "kind": "definite",
                "ref": _ref("CFO/Net", last.period),
            }
        )
    if cr and cr >= 1.2:
        strengths.append(
            {
                "text": f"نسبت جاری سالم ({cr:.2f}).",
                "kind": "definite",
                "ref": _ref("نسبت جاری", last.period),
            }
        )
    if roe and roe > 0.15:
        strengths.append(
            {
                "text": f"ROE مناسب ({roe*100:.1f}٪).",
                "kind": "definite",
                "ref": _ref("ROE", last.period),
            }
        )
    if s.pe and 0 < s.pe <= 12:
        strengths.append(
            {
                "text": f"P/E تابلو در ناحیه جذاب/معقول ({s.pe:.1f}).",
                "kind": "definite",
                "ref": "تابلوی معاملات — P/E",
            }
        )
    if prev and last.net_profit > prev.net_profit > 0:
        strengths.append(
            {
                "text": "روند سود خالص در دو دوره اخیر صعودی بوده است.",
                "kind": "definite",
                "ref": _ref("سود خالص", f"{prev.period}→{last.period}"),
            }
        )
    if last.auditor_opinion == "مقبول":
        strengths.append(
            {
                "text": "اظهارنظر حسابرس مقبول است.",
                "kind": "definite",
                "ref": "گزارش حسابرس مستقل",
            }
        )
    while len(strengths) < 5:
        strengths.append(
            {
                "text": "داده بیشتری برای تکمیل نقطه قوت قطعی لازم است.",
                "kind": "insufficient",
                "ref": "—",
            }
        )
    strengths = strengths[:5]

    # Risks
    if cr and cr < 1:
        risks.append({"text": "نسبت جاری زیر ۱.", "kind": "definite", "ref": _ref("نسبت جاری", last.period)})
    dr = _safe_div(last.total_liabilities, last.total_assets)
    if dr and dr > 0.6:
        risks.append({"text": f"اهرم بدهی بالا (نسبت بدهی {dr:.2f}).", "kind": "definite", "ref": _ref("نسبت بدهی", last.period)})
    if cfo_ratio is not None and cfo_ratio < 0.7:
        risks.append({"text": "ضعف تبدیل سود به نقد عملیاتی.", "kind": "analytical", "ref": _ref("CFO/Net", last.period)})
    if last.going_concern_doubt:
        risks.append({"text": "ابهام تداوم فعالیت در یادداشت‌ها/حسابرس ذکر شده.", "kind": "definite", "ref": "یادداشت تداوم فعالیت / حسابرس"})
    if last.auditor_opinion != "مقبول":
        risks.append(
            {
                "text": f"اظهارنظر حسابرس: {last.auditor_opinion}.",
                "kind": "definite",
                "ref": "گزارش حسابرس مستقل",
            }
        )
    if last.related_party_note:
        risks.append({"text": "وجود معاملات با اشخاص وابسته — نیاز به بررسی شرایط معامله.", "kind": "definite", "ref": "یادداشت اشخاص وابسته"})
    if last.legal_cases_note:
        risks.append({"text": "دعاوی حقوقی/بدهی احتمالی در یادداشت‌ها.", "kind": "definite", "ref": "یادداشت بدهی‌های احتمالی"})
    if last.accounting_change:
        risks.append({"text": "تغییر روش حسابداری — مقایسه دوره‌ها با احتیاط.", "kind": "definite", "ref": "یادداشت رویه‌های حسابداری"})
    if prev:
        recv_chg = _pct_change(last.receivables, prev.receivables)
        if recv_chg and recv_chg > 30:
            risks.append({"text": f"رشد شدید مطالبات ({recv_chg:+.1f}٪).", "kind": "definite", "ref": _ref("مطالبات", last.period)})
    if s.pe is not None and s.pe < 0:
        risks.append({"text": "EPS/P/E منفی در تابلو — زیان‌دهی.", "kind": "definite", "ref": "تابلو — EPS/P/E"})
    while len(risks) < 5:
        risks.append(
            {
                "text": "ریسک سیستماتیک صنعت/نرخ ارز/نرخ بهره در صورت‌های مالی این فایل به‌طور کامل قابل استخراج نیست.",
                "kind": "insufficient",
                "ref": "خارج از دامنه صورت مالی موجود",
            }
        )
    risks = risks[:5]

    questions = [
        {
            "text": "روند حاشیه عملیاتی پایدار است یا به اقلام یک‌باره وابسته بوده؟",
            "kind": "analytical",
            "ref": _ref("سود عملیاتی و غیرعملیاتی"),
        },
        {
            "text": "کیفیت مطالبات و دوره وصول چگونه است؟",
            "kind": "analytical",
            "ref": _ref("مطالبات تجاری"),
        },
        {
            "text": "برنامه بازپرداخت تسهیلات کوتاه‌مدت و نرخ بهره مؤثر چیست؟",
            "kind": "analytical",
            "ref": _ref("تسهیلات مالی"),
        },
        {
            "text": "CFO ضعیف‌تر از سود ناشی از WC است یا مشکل ساختاری فروش؟",
            "kind": "analytical",
            "ref": _ref("جریان نقد عملیاتی"),
        },
        {
            "text": "جزئیات معاملات اشخاص وابسته و قیمت‌گذاری آن‌ها چیست؟"
            if last.related_party_note
            else "آیا تعهدات خارج از تراز / ضمانت‌نامه‌ای وجود دارد؟",
            "kind": "analytical",
            "ref": "یادداشت اشخاص وابسته / تعهدات",
        },
    ]

    audit = {
        "opinion": last.auditor_opinion,
        "going_concern_doubt": last.going_concern_doubt,
        "related_party": last.related_party_note,
        "legal_cases": last.legal_cases_note,
        "accounting_change": last.accounting_change,
        "ref": "گزارش حسابرس و یادداشت‌های توضیحی",
        "evidence": "definite",
    }

    return {
        "title": "۵) نقاط قوت، ریسک‌ها و سؤالات کلیدی",
        "status": "ok",
        "strengths": strengths,
        "risks": risks,
        "questions": questions,
        "audit": audit,
        "value_score_context": value_score,
    }


def _score_value_attractive(
    s: SymbolSnapshot,
    periods: list[PeriodStatement],
    cfg: Settings,
) -> tuple[float, str, dict[str, float], list[str]]:
    """امتیاز سهام ارزنده: P/E + پتانسیل بنیادی ۵محوره."""
    last = periods[-1]
    prev = periods[0]
    parts: dict[str, float] = {}
    notes: list[str] = []

    # P/E value (0-30)
    pe = s.pe
    pe_s = 0.0
    if pe is not None and pe > 0:
        if pe <= 6:
            pe_s = 30
        elif pe <= cfg.pe_max_attractive:
            pe_s = 26 - (pe - 6) * 0.8
        elif pe <= cfg.pe_max_ok:
            pe_s = 18 - (pe - cfg.pe_max_attractive) * 1.2
        elif pe < 30:
            pe_s = max(4, 12 - (pe - 18) * 0.7)
        else:
            pe_s = 2
        notes.append(f"P/E={pe:.1f}")
    elif pe is not None and pe < 0:
        pe_s = 0
        notes.append("P/E منفی")
    else:
        pe_s = 8
        notes.append("P/E نامشخص")
    parts["pe"] = round(pe_s, 1)

    # Trend (0-15)
    rev_g = _pct_change(last.revenue, prev.revenue) or 0
    net_g = _pct_change(last.net_profit, prev.net_profit) or 0
    trend_s = 7
    if rev_g > 10:
        trend_s += 4
    elif rev_g > 0:
        trend_s += 2
    else:
        trend_s -= 3
    if net_g > 15:
        trend_s += 4
    elif net_g > 0:
        trend_s += 2
    else:
        trend_s -= 3
    parts["trend"] = round(max(0, min(15, trend_s)), 1)

    # Profitability (0-20)
    gm = _safe_div(last.gross_profit, last.revenue) or 0
    om = _safe_div(last.operating_profit, last.revenue) or 0
    roe = _safe_div(last.net_profit, last.equity) or 0
    prof = 0
    prof += min(7, gm * 20)
    prof += min(7, om * 35)
    prof += min(6, max(0, roe) * 25)
    parts["profitability"] = round(max(0, min(20, prof)), 1)

    # Liquidity/Debt (0-15)
    cr = _safe_div(last.current_assets, last.current_liabilities) or 0
    dr = _safe_div(last.total_liabilities, last.total_assets) or 1
    liq = 0
    if cr >= 1.5:
        liq += 7
    elif cr >= 1.1:
        liq += 5
    elif cr >= 1:
        liq += 3
    else:
        liq += 1
    if dr <= 0.4:
        liq += 8
    elif dr <= 0.55:
        liq += 5
    elif dr <= 0.7:
        liq += 2
    parts["liquidity_debt"] = round(max(0, min(15, liq)), 1)

    # Cash quality (0-15)
    cfo_r = _safe_div(last.cfo, last.net_profit) if last.net_profit else None
    cash_s = 6
    if cfo_r is not None:
        if cfo_r >= 1.1:
            cash_s = 15
        elif cfo_r >= 0.9:
            cash_s = 12
        elif cfo_r >= 0.7:
            cash_s = 9
        elif cfo_r >= 0.4:
            cash_s = 5
        else:
            cash_s = 2
    parts["cash_quality"] = round(cash_s, 1)

    # Audit / red flags (0-5)
    audit_s = 5
    if last.auditor_opinion != "مقبول":
        audit_s -= 2
    if last.going_concern_doubt:
        audit_s -= 2
    if last.legal_cases_note:
        audit_s -= 1
    parts["audit"] = round(max(0, audit_s), 1)

    total = sum(parts.values())
    total = max(0.0, min(100.0, total))

    # PEG bonus small
    if pe and pe > 0 and net_g > 5:
        peg = pe / max(net_g, 0.1)
        if peg < 0.8:
            total = min(100, total + 3)
            notes.append(f"PEG تقریبی جذاب ({peg:.2f})")
        parts["peg_adj"] = 3 if peg < 0.8 else 0
    else:
        parts["peg_adj"] = 0

    if total >= 80:
        grade = "A+"
    elif total >= 70:
        grade = "A"
    elif total >= 60:
        grade = "B"
    elif total >= 50:
        grade = "C"
    else:
        grade = "D"

    return round(total, 1), grade, parts, notes


def build_deep_fundamental(s: SymbolSnapshot, cfg: Settings | None = None) -> dict[str, Any]:
    cfg = cfg or get_settings()
    periods = _gen_three_periods(s, cfg)
    value_score, value_grade, score_parts, value_notes = _score_value_attractive(s, periods, cfg)

    # سازگاری با API قبلی
    last = periods[-1]
    roe = _safe_div(last.net_profit, last.equity)
    roa = _safe_div(last.net_profit, last.total_assets)
    debt = _safe_div(last.total_liabilities, last.total_assets)
    current = _safe_div(last.current_assets, last.current_liabilities)
    rev_g = _pct_change(last.revenue, periods[0].revenue) or 0
    prof_g = _pct_change(last.net_profit, periods[0].net_profit) or 0
    bvps = _safe_div(last.equity, max(float(s.z or 0), 1e7)) or (last.equity / 1e8)
    pb = round(float(s.pl or 0) / bvps, 2) if bvps else None
    peg = None
    if s.pe and s.pe > 0 and prof_g > 0:
        peg = round(s.pe / max(prof_g, 0.1), 2)

    r = _rng(s.l18, "codal")
    titles = [
        "اطلاعات و صورت‌های مالی میاندوره‌ای",
        "صورت‌های مالی سالانه حسابرسی‌شده",
        "گزارش تفسیری مدیریت",
        "افشای اطلاعات با اهمیت",
    ]
    d = date.today() - timedelta(days=r.randint(3, 80))

    section1 = _trend_section(periods)
    section2 = _profitability_section(periods)
    section3 = _liquidity_section(periods)
    section4 = _cash_quality_section(periods)
    section5 = _swot_section(periods, s, value_score)

    legacy_score = value_score  # یکپارچه
    notes = value_notes + [
        x["text"] for x in section2.get("analysis", [])[:1] + section4.get("analysis", [])[:1]
    ]

    return {
        # --- API سازگار ---
        "symbol": s.l18,
        "name": s.l30,
        "industry": s.cs,
        "pe": s.pe,
        "eps": float(s.eps) if s.eps is not None else last.eps,
        "market_cap": float(s.mv or 0),
        "roe": round((roe or 0) * 100, 1),
        "roa": round((roa or 0) * 100, 1),
        "debt_ratio": round(debt or 0, 2),
        "current_ratio": round(current or 0, 2),
        "profit_growth": round(prof_g, 1),
        "revenue_growth": round(rev_g, 1),
        "book_value_ps": round(bvps, 1) if bvps else None,
        "pb": pb,
        "peg": peg,
        "dividend_yield": None,  # بدون داده قطعی حدس زده نمی‌شود
        "fund_score": legacy_score,
        "grade": value_grade.replace("+", "") if len(value_grade) > 1 and value_grade.endswith("+") else value_grade[:1] if value_grade != "A+" else "A",
        "value_grade": value_grade,
        "notes": notes[:8],
        "quarters": [
            {
                "period": p.period,
                "revenue": p.revenue,
                "net_profit": p.net_profit,
                "eps": p.eps,
                "margin": round((_safe_div(p.net_profit, p.revenue) or 0) * 100, 1),
                "yoy_revenue_growth": rev_g if p is last else None,
                "yoy_profit_growth": prof_g if p is last else None,
            }
            for p in periods
        ],
        "last_codal_title": titles[r.randint(0, len(titles) - 1)],
        "last_codal_date": d.isoformat(),
        "source": "synthetic_deep",
        # --- امتیاز ارزندگی ---
        "value_score": value_score,
        "value_score_parts": score_parts,
        "is_value_attractive": value_score >= 65 and (s.pe is None or (s.pe > 0 and s.pe <= 18)),
        # --- گزارش ۵بخشی ---
        "deep": {
            "disclaimer": (
                "اعداد صورت‌های مالی در حالت فعلی از مدل synthetic سازگار با تابلو تولید شده‌اند "
                "مگر اینکه منبع کدال واقعی وصل شود. فیلد evidence: definite=محاسبه از جدول موجود، "
                "analytical=برداشت تحلیلی، insufficient=داده ناکافی (بدون حدس عدد)."
            ),
            "periods_raw": [asdict(p) for p in periods],
            "section_trend": section1,
            "section_profitability": section2,
            "section_liquidity": section3,
            "section_cash_quality": section4,
            "section_swot": section5,
        },
    }


def build_fundamental(s: SymbolSnapshot, cfg: Settings | None = None) -> Any:
    """سازگاری: آبجکت با to_dict()."""
    data = build_deep_fundamental(s, cfg)

    class _F:
        def __init__(self, d):
            self._d = d
            for k, v in d.items():
                if k != "deep":
                    setattr(self, k, v)

        def to_dict(self):
            return self._d

    return _F(data)


def rank_fundamentals(
    symbols: list[SymbolSnapshot],
    cfg: Settings | None = None,
    limit: int = 80,
    min_score: float = 0,
) -> list[dict[str, Any]]:
    cfg = cfg or get_settings()
    rows = [build_deep_fundamental(s, cfg) for s in symbols if s.l18]
    rows = [r for r in rows if r["fund_score"] >= min_score]
    rows.sort(key=lambda x: (x["value_score"], -(x["pe"] or 99) if (x["pe"] or 0) > 0 else -999), reverse=True)
    return rows[:limit]


def rank_value_stocks(
    symbols: list[SymbolSnapshot],
    cfg: Settings | None = None,
    limit: int = 50,
    max_pe: float = 18.0,
    min_value_score: float = 55.0,
) -> list[dict[str, Any]]:
    """جدول سهام پرپتانسیل/ارزنده از نظر بنیادی و P/E."""
    cfg = cfg or get_settings()
    ranked = []
    for s in symbols:
        if not s.l18:
            continue
        d = build_deep_fundamental(s, cfg)
        pe = d.get("pe")
        # فیلتر نرم: pe نامشخص مجاز؛ pe خیلی بالا حذف
        if pe is not None and pe > max_pe:
            continue
        if pe is not None and pe < 0:
            continue
        if d["value_score"] < min_value_score:
            continue
        last = d["deep"]["periods_raw"][-1]
        ranked.append(
            {
                "symbol": d["symbol"],
                "name": d["name"],
                "industry": d["industry"],
                "pe": pe,
                "eps": d["eps"],
                "pb": d["pb"],
                "peg": d["peg"],
                "value_score": d["value_score"],
                "value_grade": d["value_grade"],
                "fund_score": d["fund_score"],
                "roe": d["roe"],
                "roa": d["roa"],
                "debt_ratio": d["debt_ratio"],
                "current_ratio": d["current_ratio"],
                "profit_growth": d["profit_growth"],
                "revenue_growth": d["revenue_growth"],
                "cfo_to_net": round(last["cfo"] / last["net_profit"], 2)
                if last.get("net_profit")
                else None,
                "gross_margin": round(last["gross_profit"] / last["revenue"] * 100, 1)
                if last.get("revenue")
                else None,
                "score_parts": d["value_score_parts"],
                "notes": d["notes"][:4],
                "pl": s.pl,
                "plp": s.plp,
                "is_value_attractive": d["is_value_attractive"],
            }
        )
    ranked.sort(key=lambda x: (x["value_score"], -(x["pe"] or 99)), reverse=True)
    # رتبه
    for i, row in enumerate(ranked[:limit], 1):
        row["rank"] = i
    return ranked[:limit]
