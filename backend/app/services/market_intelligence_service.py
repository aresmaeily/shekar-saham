"""Market Intelligence service for P3.40.

Builds market snapshots, industry intelligence, opportunity rankings and change
events from existing MarketService outputs. It does not fetch raw providers and
it does not run an autonomous scheduler.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.data.store import store
from app.domain.ai_intelligence import AIIntelligenceCore, IntelligenceResult
from app.domain.market_intelligence import (
    IndustryIntelligence,
    IntelligenceEvent,
    MarketIntelligenceSnapshot,
    MarketMonitoringResult,
    OpportunityRank,
)


class MarketIntelligenceService:
    def __init__(self) -> None:
        self.ai_core = AIIntelligenceCore()
        self.history_key = "market_intelligence:history"
        self.events_key = "market_intelligence:events"
        self.max_history = 50
        self.max_events = 200

    @staticmethod
    def _safe_num(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _risk_from_score(score: float) -> str:
        if score >= 70:
            return "HIGH"
        if score >= 45:
            return "MEDIUM"
        return "LOW"

    def _market_regime(self, *, positive: int, negative: int, total: int, money_flow: float, total_value: float, data_trust: dict[str, Any]) -> tuple[str, float, list[dict[str, Any]], list[str]]:
        evidence: list[dict[str, Any]] = []
        warnings: list[str] = []
        if total <= 0:
            return "INSUFFICIENT_DATA", 0.0, evidence, ["No market symbols available."]
        if data_trust.get("state") in {"mock", "synthetic", "stale", "unavailable"}:
            warnings.append("Market regime is research-only because data is not verified live.")
        breadth = (positive - negative) / max(total, 1)
        evidence.append({"name": "breadth", "value": breadth, "source": "overview"})
        evidence.append({"name": "market_money_flow", "value": money_flow, "source": "metrics"})
        evidence.append({"name": "total_trade_value", "value": total_value, "source": "overview"})
        confidence = min(0.75, 0.25 + abs(breadth) * 0.35 + (0.15 if abs(money_flow) > 0 else 0))
        if total_value <= 0:
            return "LOW_LIQUIDITY", min(confidence, 0.35), evidence, warnings + ["Total trade value is unavailable/zero."]
        if breadth >= 0.25 and money_flow >= 0:
            return "BULLISH", confidence, evidence, warnings
        if breadth <= -0.25 or money_flow < 0:
            return "BEARISH", confidence, evidence, warnings
        if abs(breadth) <= 0.08:
            return "NEUTRAL", confidence, evidence, warnings
        return "RISK_OFF" if money_flow < 0 else "NEUTRAL", confidence, evidence, warnings

    def _industry_intelligence(self, rows: list[dict[str, Any]], data_trust: dict[str, Any]) -> list[IndustryIntelligence]:
        out: list[IndustryIntelligence] = []
        for r in rows:
            symbol_count = int(r.get("symbol_count") or 0)
            avg_plp = self._safe_num(r.get("avg_plp"))
            net = self._safe_num(r.get("net_individual_value"))
            buy_power = self._safe_num(r.get("avg_buy_power"))
            base_score = self._safe_num(r.get("score"))
            breadth = avg_plp
            money_flow = net
            risk = max(0.0, min(100.0, 50 - avg_plp * 4 - min(buy_power - 1, 2) * 10))
            confidence = 0.5 if symbol_count else 0.0
            if data_trust.get("state") != "live":
                confidence = min(confidence, 0.35)
            status = "READY" if symbol_count else "INSUFFICIENT_DATA"
            out.append(
                IndustryIntelligence(
                    industry=str(r.get("industry") or "—"),
                    score=round(base_score, 2),
                    breadth=round(breadth, 2),
                    money_flow=round(money_flow, 2),
                    opportunity=round(max(0, base_score), 2),
                    risk=round(risk, 2),
                    confidence=round(confidence, 3),
                    symbol_count=symbol_count,
                    data_trust=data_trust,
                    evidence=[{"name": "industry_flow", "value": r, "source": "analysis.industries"}],
                    status=status,
                )
            )
        out.sort(key=lambda x: (x.score, x.money_flow), reverse=True)
        return out

    def _symbol_context_from_card(self, card: dict[str, Any]) -> dict[str, Any]:
        return {
            "snapshot": {
                "l18": card.get("symbol"),
                "symbol": card.get("symbol"),
                "l30": card.get("name"),
                "pl": card.get("pl"),
                "plp": card.get("plp"),
            },
            "metrics": {
                "entry_score": card.get("entry_score"),
                "exit_score": card.get("exit_score"),
                "buy_power": card.get("buy_power"),
                "volume_ratio": card.get("volume_ratio"),
                "individual_net_value": card.get("individual_net_value"),
            },
            "tablocastic": {"golden_number": card.get("golden_number"), "grade": card.get("grade")},
            "fundamental": {
                "value_score": card.get("value_score") or card.get("fund_score"),
                "fund_score": card.get("fund_score"),
                "is_synthetic": True,
            },
        }

    def _opportunities(self, cards: list[dict[str, Any]], market: dict[str, Any], data_trust: dict[str, Any], limit: int) -> tuple[list[OpportunityRank], list[IntelligenceResult]]:
        ranked: list[OpportunityRank] = []
        intelligence: list[IntelligenceResult] = []
        for card in cards[: max(limit * 2, limit)]:
            result = self.ai_core.evaluate(
                symbol_context=self._symbol_context_from_card(card),
                market_context=market,
                filter_context={"sample": {"count": 1 if card.get("symbol") else 0}},
                data_trust=data_trust,
            )
            intelligence.append(result)
            overall = max(0.0, min(100.0, (result.technical_score * 0.30 + result.money_flow_score * 0.30 + result.fundamental_score * 0.20 + result.filter_score * 0.10 + (100 - result.risk_score) * 0.10)))
            ranked.append(
                OpportunityRank(
                    rank=0,
                    symbol=result.symbol,
                    name=str(card.get("name") or ""),
                    industry=str(card.get("industry") or ""),
                    overall_score=round(overall, 2),
                    confidence=result.confidence,
                    money_flow_score=result.money_flow_score,
                    technical_score=result.technical_score,
                    fundamental_score=result.fundamental_score,
                    filter_score=result.filter_score,
                    strategy_score=result.strategy_score,
                    risk_score=result.risk_score,
                    recommendation=result.recommendation,
                    data_trust=data_trust,
                    evidence=[e.model_dump(mode="json") for e in result.evidence],
                    warnings=result.warnings,
                )
            )
        ranked.sort(key=lambda x: (x.confidence, x.overall_score), reverse=True)
        for i, item in enumerate(ranked[:limit], start=1):
            item.rank = i
        return ranked[:limit], intelligence[:limit]

    def _load_history(self) -> list[dict[str, Any]]:
        rows = store.get_setting(self.history_key, []) or []
        return rows if isinstance(rows, list) else []

    def _save_history(self, snapshot: MarketIntelligenceSnapshot) -> int:
        rows = self._load_history()
        rows.append(snapshot.model_dump(mode="json"))
        rows = rows[-self.max_history :]
        store.set_setting(self.history_key, rows)
        return len(rows)

    def _load_events(self) -> list[dict[str, Any]]:
        rows = store.get_setting(self.events_key, []) or []
        return rows if isinstance(rows, list) else []

    def _save_events(self, events: list[IntelligenceEvent]) -> None:
        if not events:
            return
        rows = self._load_events()
        rows.extend([e.model_dump(mode="json") for e in events])
        store.set_setting(self.events_key, rows[-self.max_events :])

    def _detect_events(self, previous: dict[str, Any] | None, current: MarketIntelligenceSnapshot, opportunities: list[OpportunityRank]) -> list[IntelligenceEvent]:
        events: list[IntelligenceEvent] = []
        if not previous:
            for op in opportunities[:3]:
                events.append(
                    IntelligenceEvent(
                        event_id=uuid.uuid4().hex,
                        timestamp=current.timestamp,
                        event_type="OPPORTUNITY_APPEARED",
                        symbol=op.symbol,
                        industry=op.industry,
                        severity="medium" if op.confidence >= 0.5 else "low",
                        current_state=op.model_dump(mode="json"),
                        reason_codes=[op.recommendation],
                        evidence=op.evidence[:3],
                        data_trust=current.data_trust,
                    )
                )
            return events
        prev_regime = previous.get("market_regime")
        if prev_regime and prev_regime != current.market_regime:
            events.append(
                IntelligenceEvent(
                    event_id=uuid.uuid4().hex,
                    timestamp=current.timestamp,
                    event_type="REGIME_CHANGED",
                    severity="high",
                    previous_state={"market_regime": prev_regime},
                    current_state={"market_regime": current.market_regime},
                    reason_codes=["REGIME_CHANGED"],
                    evidence=current.evidence,
                    data_trust=current.data_trust,
                )
            )
        return events

    async def run_market_monitoring_cycle(self, market_service: Any, *, limit: int = 20, persist: bool = True) -> MarketMonitoringResult:
        analysis = await market_service.get_analysis(force=False)
        data_trust = market_service.data_trust_context()
        overview = analysis.overview.model_dump(mode="json")
        cards = [c.model_dump(mode="json") for c in (analysis.entry_signals + analysis.watchlist)]
        industries_raw = [i.model_dump(mode="json") for i in analysis.industries]

        total = int(overview.get("symbol_count") or 0)
        positive = int(overview.get("positive_count") or 0)
        negative = int(overview.get("negative_count") or 0)
        unchanged = max(0, total - positive - negative)
        total_value = self._safe_num(overview.get("total_value"))
        market_money_flow = sum(self._safe_num(c.get("individual_net_value")) for c in cards)
        avg_buy_power = sum(self._safe_num(c.get("buy_power"), 1.0) for c in cards) / len(cards) if cards else 0.0
        regime, regime_confidence, regime_evidence, regime_warnings = self._market_regime(
            positive=positive,
            negative=negative,
            total=total,
            money_flow=market_money_flow,
            total_value=total_value,
            data_trust=data_trust,
        )
        market_context = {"confluence": market_service.get_confluence().get("summary", {}) if hasattr(market_service, "get_confluence") else {}}
        opportunities, symbol_intel = self._opportunities(cards, market_context, data_trust, limit)
        industries = self._industry_intelligence(industries_raw, data_trust)
        top_risks = [o.model_dump(mode="json") for o in sorted(opportunities, key=lambda x: x.risk_score, reverse=True)[:5]]
        snapshot = MarketIntelligenceSnapshot(
            timestamp=time.time(),
            total_symbols=total,
            positive_symbols=positive,
            negative_symbols=negative,
            unchanged_symbols=unchanged,
            total_trade_value=total_value,
            total_volume=sum(self._safe_num(getattr(s, "tvol", 0)) for s in getattr(market_service, "_last_symbols", [])),
            market_money_flow=round(market_money_flow, 2),
            buyer_power=round(avg_buy_power, 3),
            seller_power=round(1 / avg_buy_power, 3) if avg_buy_power else 0.0,
            market_regime=regime,
            confidence=round(regime_confidence, 3),
            risk_level=self._risk_from_score(100 - regime_confidence * 100),
            industry_summary=[i.model_dump(mode="json") for i in industries[:10]],
            top_opportunities=[o.model_dump(mode="json") for o in opportunities[:10]],
            top_risks=top_risks,
            data_trust=data_trust,
            evidence=regime_evidence,
            warnings=regime_warnings,
        )
        previous = self._load_history()[-1] if self._load_history() else None
        events = self._detect_events(previous, snapshot, opportunities)
        history_count = len(self._load_history())
        if persist:
            history_count = self._save_history(snapshot)
            self._save_events(events)
        return MarketMonitoringResult(snapshot=snapshot, industries=industries[:limit], opportunities=opportunities, events=events, symbol_intelligence=symbol_intel, history_count=history_count)

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._load_events()))[:limit]


market_intelligence_service = MarketIntelligenceService()
