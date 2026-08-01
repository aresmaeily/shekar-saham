"""موتور اسکرینر: پول داغ، بازی بازار، صنایع، سیگنال‌ها."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from app.core.config import Settings, get_settings
from app.engines.metrics import compute_metrics
from app.models.schemas import (
    AnalyzeResponse,
    DerivedMetrics,
    HotMoneyRow,
    IndustryFlow,
    MarketGameRow,
    MarketOverview,
    SignalCard,
    SignalSide,
    SymbolSnapshot,
)


def analyze_market(
    symbols: Iterable[SymbolSnapshot],
    cfg: Settings | None = None,
    source: str = "unknown",
    include_all_metrics: bool = False,
) -> AnalyzeResponse:
    cfg = cfg or get_settings()
    snaps = [s for s in symbols if s.l18 and not _is_noise_symbol(s.l18)]
    metrics_map: dict[str, DerivedMetrics] = {}
    snap_map: dict[str, SymbolSnapshot] = {}

    for s in snaps:
        snap_map[s.l18] = s
        metrics_map[s.l18] = compute_metrics(s, cfg)

    entry_signals: list[SignalCard] = []
    exit_signals: list[SignalCard] = []
    watchlist: list[SignalCard] = []

    for sym, m in metrics_map.items():
        s = snap_map[sym]
        card = _to_card(s, m)
        if m.side == SignalSide.ENTRY:
            entry_signals.append(card)
        elif m.side == SignalSide.EXIT:
            exit_signals.append(card)
        elif m.side == SignalSide.WATCH:
            watchlist.append(card)

    entry_signals.sort(key=lambda x: x.entry_score, reverse=True)
    exit_signals.sort(key=lambda x: x.exit_score, reverse=True)
    watchlist.sort(key=lambda x: x.entry_score, reverse=True)

    hot, hot_plus = build_hot_money(snaps, metrics_map, cfg)
    game = build_market_game(snaps, metrics_map, cfg)
    industries = build_industry_flow(snaps, metrics_map)

    total_value = sum(s.tval for s in snaps)
    pos = sum(1 for s in snaps if s.plp > 0)
    neg = sum(1 for s in snaps if s.plp < 0)
    vol_spikes = sum(1 for m in metrics_map.values() if m.is_volume_spike)
    net_individual = sum(m.individual_net_value for m in metrics_map.values())

    overview = MarketOverview(
        as_of=datetime.now(timezone.utc),
        source=source,
        symbol_count=len(snaps),
        positive_count=pos,
        negative_count=neg,
        total_value=total_value,
        entry_alerts=len(entry_signals),
        exit_alerts=len(exit_signals),
        volume_spikes=vol_spikes,
        hot_money_count=len(hot),
        top_industries=industries[:5],
        thermometer=build_thermometer(
            pos=pos,
            neg=neg,
            total_value=total_value,
            hot_count=len(hot),
            entry_alerts=len(entry_signals),
            exit_alerts=len(exit_signals),
            net_individual=net_individual,
            symbol_count=len(snaps),
        ),
    )

    return AnalyzeResponse(
        overview=overview,
        entry_signals=entry_signals[:50],
        exit_signals=exit_signals[:50],
        watchlist=watchlist[:50],
        hot_money=hot[:80],
        hot_money_plus=hot_plus[:80],
        market_game=game[:80],
        industries=industries,
        all_metrics=list(metrics_map.values()) if include_all_metrics else [],
        meta={
            "thresholds": {
                "entry_score_alert": cfg.entry_score_alert,
                "exit_score_alert": cfg.exit_score_alert,
                "volume_spike_ratio": cfg.volume_spike_ratio,
                "buy_power_min": cfg.buy_power_min,
                "hot_money_threshold": cfg.hot_money_threshold,
                "pe_max_attractive": cfg.pe_max_attractive,
            }
        },
    )


def build_thermometer(
    pos: int,
    neg: int,
    total_value: float,
    hot_count: int,
    entry_alerts: int,
    exit_alerts: int,
    net_individual: float,
    symbol_count: int,
) -> dict:
    """
    دماسنج بازار (ایده ۵.۱): یک نمره -100..+100 از ترکیب عرض بازار، ارزش معاملات،
    پول داغ، هشدارها و خالص حقیقی. خروجی {state, score, label, parts}.
    """
    n = max(symbol_count, 1)
    breadth = (pos - neg) / n * 45  # -45..+45
    value_part = min(15, max(-15, total_value / 4e12 * 15 - 7.5))  # حول میانگین
    hot_part = min(12, hot_count / 8 * 12) - 6
    alerts_part = min(12, max(-12, (entry_alerts - exit_alerts) * 3))
    net_part = min(16, max(-16, net_individual / 2e11 * 10))

    parts = {
        "breadth": round(breadth, 1),
        "value": round(value_part, 1),
        "hot": round(hot_part, 1),
        "alerts": round(alerts_part, 1),
        "net": round(net_part, 1),
    }
    score = round(min(100, max(-100, breadth + value_part + hot_part + alerts_part + net_part)), 1)

    if score >= 30:
        state, label = "bull", "صعودی"
    elif score <= -30:
        state, label = "bear", "نزولی"
    else:
        state, label = "neutral", "خنثی"

    return {"state": state, "score": score, "label": label, "parts": parts}


def _flow_score(
    s: SymbolSnapshot,
    m: DerivedMetrics,
    side: str,
    per_capita: float,
    cfg: Settings,
) -> float:
    """
    نمره ترکیبی «جریان هوشمند» ۰-۱۰۰ (ایده ۱.۳):
    ترکیب سرانه، قدرت خریدار، حجم غیرعادی، هم‌سویی قیمت و خالص حقیقی.
    """
    score = 0.0
    threshold = max(cfg.hot_money_threshold, 1)
    # ۱) قدرت سرانه نسبت به آستانه پول داغ
    score += min(35, per_capita / threshold * 25)
    # ۲) قدرت خریدار (هم‌سو با جهت پول)
    if side == "buy":
        score += min(20, max(0, (m.buy_power - 1.0)) * 10)
    else:
        score += min(20, max(0, (1.0 - m.buy_power)) * 10)
    # ۳) حجم غیرعادی
    score += min(15, max(0, (m.volume_ratio - 1.0)) * 12)
    # ۴) هم‌سویی قیمت با جهت پول (خرید با مثبت / فروش با منفی)
    if (side == "buy" and s.plp >= 0) or (side == "sell" and s.plp <= 0):
        score += 10
    else:
        score += 2  # واگرایی — هنوز پول هست ولی قیمت همراه نیست
    # ۵) خالص حقیقی هم‌سو
    if (side == "buy" and m.individual_net_value > 0) or (side == "sell" and m.individual_net_value < 0):
        score += 20
    return round(min(100.0, score), 1)


def build_hot_money(
    snaps: list[SymbolSnapshot],
    metrics: dict[str, DerivedMetrics],
    cfg: Settings,
) -> tuple[list[HotMoneyRow], list[HotMoneyRow]]:
    hot: list[HotMoneyRow] = []
    plus: list[HotMoneyRow] = []
    for s in snaps:
        m = metrics[s.l18]
        # خرید
        if m.buy_per_capita >= cfg.hot_money_plus_min:
            side = "buy"
            tier = "hot" if m.buy_per_capita >= cfg.hot_money_threshold else "plus"
            row = HotMoneyRow(
                symbol=s.l18,
                name=s.l30,
                industry=s.cs,
                side=side,
                estimated_value=m.buy_per_capita * max(s.Buy_CountI, 1) * 0.15,
                per_capita=m.buy_per_capita,
                buy_power=m.buy_power,
                plp=s.plp,
                volume_ratio=m.volume_ratio,
                hot_net=m.hot_net,
                score=m.hot_buy_score + m.entry_score * 0.2,
                tier=tier,
                flow_score=_flow_score(s, m, "buy", m.buy_per_capita, cfg),
            )
            (hot if tier == "hot" else plus).append(row)
        # فروش
        if m.sell_per_capita >= cfg.hot_money_plus_min:
            side = "sell"
            tier = "hot" if m.sell_per_capita >= cfg.hot_money_threshold else "plus"
            row = HotMoneyRow(
                symbol=s.l18,
                name=s.l30,
                industry=s.cs,
                side=side,
                estimated_value=m.sell_per_capita * max(s.Sell_CountI, 1) * 0.15,
                per_capita=m.sell_per_capita,
                buy_power=m.buy_power,
                plp=s.plp,
                volume_ratio=m.volume_ratio,
                hot_net=m.hot_net,
                score=m.hot_sell_score + m.exit_score * 0.2,
                tier=tier,
                flow_score=_flow_score(s, m, "sell", m.sell_per_capita, cfg),
            )
            (hot if tier == "hot" else plus).append(row)

    hot.sort(key=lambda r: r.score, reverse=True)
    plus.sort(key=lambda r: r.score, reverse=True)
    return hot, plus


def build_market_game(
    snaps: list[SymbolSnapshot],
    metrics: dict[str, DerivedMetrics],
    cfg: Settings,
) -> list[MarketGameRow]:
    rows: list[MarketGameRow] = []
    for s in snaps:
        m = metrics[s.l18]
        # فقط نمادهای با تحرک
        if abs(m.big_player_bias) < 0.15 and abs(m.mid_player_bias) < 0.15 and m.volume_ratio < 1.2:
            continue
        biases = {
            "بزرگان": m.big_player_bias,
            "متوسط": m.mid_player_bias,
            "خرد": m.retail_bias,
        }
        dominant = max(biases, key=lambda k: abs(biases[k]))
        direction = "ورود" if biases[dominant] >= 0 else "خروج"
        note = f"{direction} {dominant}"
        if m.is_volume_spike:
            note += " | حجم مشکوک"
        # قهرمان شکار (ایده ۲.۱): ورود پول هوشمند/حقیقی در قیمت منفی → صف خرید بالقوه
        inflow = direction == "ورود"
        hunt_champion = (
            inflow
            and s.plp < 0
            and (abs(biases[dominant]) >= 0.15 or m.volume_ratio >= 1.3)
            and m.individual_net_value > 0
        )
        if hunt_champion:
            note += " | 🎯 قهرمان شکار: ورود پول در منفی"
        rows.append(
            MarketGameRow(
                symbol=s.l18,
                name=s.l30,
                industry=s.cs,
                big_bias=round(m.big_player_bias, 3),
                mid_bias=round(m.mid_player_bias, 3),
                retail_bias=round(m.retail_bias, 3),
                dominant=f"{direction} {dominant}",
                plp=s.plp,
                volume_ratio=round(m.volume_ratio, 2),
                buy_power=round(m.buy_power, 2),
                note=note,
                hunt_champion=hunt_champion,
            )
        )
    rows.sort(key=lambda r: (r.hunt_champion, abs(r.big_bias) * 2 + r.volume_ratio), reverse=True)
    return rows


def build_industry_flow(
    snaps: list[SymbolSnapshot],
    metrics: dict[str, DerivedMetrics],
) -> list[IndustryFlow]:
    groups: dict[str, list[tuple[SymbolSnapshot, DerivedMetrics]]] = defaultdict(list)
    for s in snaps:
        ind = s.cs or "نامشخص"
        groups[ind].append((s, metrics[s.l18]))

    out: list[IndustryFlow] = []
    for ind, items in groups.items():
        n = len(items)
        avg_plp = sum(s.plp for s, _ in items) / n
        total_value = sum(s.tval for s, _ in items)
        net_i = sum(m.individual_net_value for _, m in items)
        avg_bp = sum(m.buy_power for _, m in items) / n
        avg_vr = sum(m.volume_ratio for _, m in items) / n
        entries = sum(1 for _, m in items if m.side == SignalSide.ENTRY)
        score = (
            (avg_plp * 3)
            + (10 if net_i > 0 else -8)
            + min(20, avg_vr * 4)
            + min(15, max(0, avg_bp - 1) * 10)
            + entries * 5
            + min(15, total_value / 1e12)
        )
        out.append(
            IndustryFlow(
                industry=ind,
                symbol_count=n,
                avg_plp=round(avg_plp, 2),
                total_value=total_value,
                net_individual_value=net_i,
                avg_buy_power=round(avg_bp, 2),
                avg_volume_ratio=round(avg_vr, 2),
                entry_candidates=entries,
                score=round(score, 2),
            )
        )
    out.sort(key=lambda x: x.score, reverse=True)
    return out


def _to_card(s: SymbolSnapshot, m: DerivedMetrics) -> SignalCard:
    return SignalCard(
        symbol=s.l18,
        name=s.l30,
        industry=s.cs,
        side=m.side,
        alert_level=m.alert_level,
        entry_score=round(m.entry_score, 1),
        exit_score=round(m.exit_score, 1),
        pl=s.pl,
        plp=s.plp,
        pe=s.pe,
        buy_power=round(m.buy_power, 2),
        volume_ratio=round(m.volume_ratio, 2),
        individual_net_value=m.individual_net_value,
        hot_net=round(m.hot_net, 1),
        near_buy_queue=m.near_buy_queue or m.in_buy_queue,
        reasons=m.reasons,
        tags=m.tags,
        updated_at=s.updated_at,
    )


def _is_noise_symbol(l18: str) -> bool:
    s = l18.strip()
    if not s:
        return True
    # حق تقدم و برخی اوراق را فعلاً فیلتر نرم
    if s.endswith("ح") and len(s) > 2:
        return True
    return False
