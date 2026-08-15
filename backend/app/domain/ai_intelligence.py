"""AI Intelligence Core contracts and deterministic evaluator.

P3.39 scope: structured intelligence and decision-support only.
No autonomous trading, broker integration, live order execution, or LLM provider
is implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import is_verified_live

Recommendation = Literal["BUY_CANDIDATE", "HOLD", "SELL_CANDIDATE", "WATCH", "NO_ACTION", "INSUFFICIENT_DATA"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class IntelligenceEvidence(BaseModel):
    category: str
    name: str
    value: Any = None
    score: float | None = None
    weight: float | None = None
    direction: str = "neutral"  # positive | negative | neutral
    source: str = "system"
    note: str = ""


class IntelligenceResult(BaseModel):
    symbol: str = ""
    market: str = "iran"
    timestamp: float | None = None
    data_trust: dict[str, Any] = Field(default_factory=dict)
    market_regime: str = "UNKNOWN"
    technical_score: float = 0.0
    fundamental_score: float = 0.0
    money_flow_score: float = 0.0
    filter_score: float = 0.0
    strategy_score: float = 0.0
    risk_score: float = 100.0
    confidence: float = 0.0
    recommendation: Recommendation = "INSUFFICIENT_DATA"
    evidence: list[IntelligenceEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    invalidations: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    reason_codes: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class IntelligenceWeights:
    """Documented initial weights for deterministic evidence aggregation."""

    technical: float = 0.25
    fundamental: float = 0.20
    money_flow: float = 0.25
    filter_signal: float = 0.15
    strategy: float = 0.15


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _trust_confidence_cap(data_trust: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    state = (data_trust.get("state") or "mixed").lower()
    warnings: list[str] = []
    invalidations: list[str] = []
    if is_verified_live(data_trust):
        return 1.0, warnings, invalidations
    if state == "live":
        warnings.append("Live-class source is not independently verified; output cannot be treated as a real-market signal.")
        invalidations.append("Unverified live-class data blocks actionable live recommendation.")
        return 0.35, warnings, invalidations
    if state == "mixed":
        warnings.append("Data trust is mixed; confidence is capped.")
        return 0.60, warnings, invalidations
    if state in {"mock", "synthetic"}:
        warnings.append("Data is not live; output is analysis-only and cannot be treated as a real-market signal.")
        invalidations.append("Non-live data trust blocks actionable live recommendation.")
        return 0.35, warnings, invalidations
    if state == "stale":
        warnings.append("Data is stale; output cannot be treated as current market state.")
        invalidations.append("Stale data blocks actionable live recommendation.")
        return 0.30, warnings, invalidations
    if state == "unavailable":
        warnings.append("Reliable market data is unavailable.")
        invalidations.append("Unavailable data blocks recommendation.")
        return 0.15, warnings, invalidations
    warnings.append("Unknown data trust state; confidence is capped.")
    return 0.25, warnings, invalidations


class AIIntelligenceCore:
    """Deterministic AI Brain foundation over controlled context."""

    def __init__(self, weights: IntelligenceWeights | None = None) -> None:
        self.weights = weights or IntelligenceWeights()

    def evaluate(
        self,
        *,
        symbol_context: dict[str, Any],
        market_context: dict[str, Any] | None = None,
        filter_context: dict[str, Any] | None = None,
        backtest_context: dict[str, Any] | None = None,
        data_trust: dict[str, Any] | None = None,
    ) -> IntelligenceResult:
        data_trust = data_trust or {}
        market_context = market_context or {}
        filter_context = filter_context or {}
        backtest_context = backtest_context or {}
        snapshot = symbol_context.get("snapshot") or {}
        metrics = symbol_context.get("metrics") or {}
        tablo = symbol_context.get("tablocastic") or {}
        fundamental = symbol_context.get("fundamental") or {}

        symbol = str(snapshot.get("l18") or snapshot.get("symbol") or "")
        evidence: list[IntelligenceEvidence] = []
        warnings: list[str] = []
        invalidations: list[str] = []
        reason_codes: list[str] = []

        technical_score = _clamp((_num(metrics.get("entry_score")) * 0.65) + (_num(tablo.get("golden_number")) * 0.35))
        exit_score = _num(metrics.get("exit_score"))
        value_score = _clamp(_num(fundamental.get("value_score", fundamental.get("fund_score"))))
        buy_power = _num(metrics.get("buy_power"), 1.0)
        volume_ratio = _num(metrics.get("volume_ratio"), 1.0)
        net_value = _num(metrics.get("individual_net_value"))
        money_flow_score = _clamp((min(buy_power, 4.0) / 4.0 * 45) + (min(volume_ratio, 4.0) / 4.0 * 30) + (25 if net_value > 0 else 0))
        filter_sample = filter_context.get("sample") if isinstance(filter_context, dict) else None
        filter_count = _num((filter_sample or {}).get("count"))
        filter_intelligence = filter_context.get("filter_intelligence") if isinstance(filter_context, dict) else None
        filter_score = _clamp(70 if filter_count > 0 else 0)
        if isinstance(filter_intelligence, dict):
            classification = str(filter_intelligence.get("classification") or "")
            if classification == "EXCELLENT":
                filter_score = max(filter_score, 85)
            elif classification == "GOOD":
                filter_score = max(filter_score, 72)
            elif classification == "STABLE":
                filter_score = max(filter_score, 60)
            elif classification in {"DEGRADING", "WEAK"}:
                filter_score = min(filter_score or 45, 45)
                reason_codes.append("FILTER_INTELLIGENCE_RISK")
            elif classification in {"INVALID", "INSUFFICIENT_DATA"}:
                reason_codes.append("FILTER_INTELLIGENCE_INSUFFICIENT")
        bt_metrics = (backtest_context.get("metrics") or backtest_context) if isinstance(backtest_context, dict) else {}
        pf = _num(bt_metrics.get("profit_factor"))
        dd = _num(bt_metrics.get("maximum_drawdown", bt_metrics.get("max_drawdown")))
        strategy_score = _clamp((min(pf, 2.0) / 2.0 * 75) + (25 if pf > 1 and dd < 20 else 0)) if bt_metrics else 0.0
        risk_score = _clamp(40 + exit_score * 0.35 + max(0, 1.0 - min(buy_power, 1.0)) * 25 + min(dd, 35))

        evidence.extend([
            IntelligenceEvidence(category="technical", name="entry_score", value=metrics.get("entry_score"), score=technical_score, weight=self.weights.technical, direction="positive" if technical_score >= 60 else "neutral"),
            IntelligenceEvidence(category="fundamental", name="value_score", value=fundamental.get("value_score", fundamental.get("fund_score")), score=value_score, weight=self.weights.fundamental, direction="positive" if value_score >= 60 else "neutral", note="Synthetic if fundamental_source=synthetic"),
            IntelligenceEvidence(category="money_flow", name="buy_power_volume_net", value={"buy_power": buy_power, "volume_ratio": volume_ratio, "individual_net_value": net_value}, score=money_flow_score, weight=self.weights.money_flow, direction="positive" if money_flow_score >= 60 else "negative" if money_flow_score < 35 else "neutral"),
            IntelligenceEvidence(category="filter", name="filter_sample", value=filter_count, score=filter_score, weight=self.weights.filter_signal, direction="positive" if filter_score >= 60 else "negative" if filter_score and filter_score < 50 else "neutral"),
            IntelligenceEvidence(category="filter_intelligence", name="filter_version_evaluation", value=filter_intelligence or {}, score=filter_score, weight=self.weights.filter_signal, direction="positive" if filter_score >= 60 else "negative" if filter_intelligence else "neutral", note="P3.41 filter performance/decay context when supplied."),
            IntelligenceEvidence(category="strategy", name="backtest_metrics", value=bt_metrics or {}, score=strategy_score, weight=self.weights.strategy, direction="positive" if strategy_score >= 60 else "neutral"),
            IntelligenceEvidence(category="risk", name="risk_score", value=risk_score, score=risk_score, direction="negative" if risk_score >= 65 else "neutral"),
        ])

        weighted_score = (
            technical_score * self.weights.technical
            + value_score * self.weights.fundamental
            + money_flow_score * self.weights.money_flow
            + filter_score * self.weights.filter_signal
            + strategy_score * self.weights.strategy
        )
        weight_sum = sum(self.weights.__dict__.values())
        composite = _clamp(weighted_score / weight_sum if weight_sum else 0.0)

        conflicts: list[str] = []
        if technical_score >= 65 and money_flow_score < 35:
            conflicts.append("Technical evidence is positive but money-flow evidence is weak/negative.")
        if technical_score >= 65 and value_score < 35:
            conflicts.append("Technical evidence is positive but fundamental evidence is weak.")
        if exit_score >= 60 and technical_score >= 60:
            conflicts.append("Entry and exit pressures are both elevated.")
        if strategy_score and strategy_score < 40 and filter_score >= 60:
            conflicts.append("Filter triggers but strategy/backtest evidence is weak.")

        trust_cap, trust_warnings, trust_invalidations = _trust_confidence_cap(data_trust)
        warnings.extend(trust_warnings)
        invalidations.extend(trust_invalidations)
        if fundamental.get("is_synthetic") is True:
            warnings.append("Fundamental evidence is synthetic and not verified financial statement data.")
            reason_codes.append("FUNDAMENTAL_SYNTHETIC")
        if conflicts:
            reason_codes.append("EVIDENCE_CONFLICT")

        evidence_completeness = sum(1 for score in [technical_score, value_score, money_flow_score, filter_score, strategy_score] if score > 0) / 5
        conflict_penalty = min(0.30, len(conflicts) * 0.10)
        risk_penalty = 0.20 if risk_score >= 70 else 0.10 if risk_score >= 55 else 0.0
        confidence = max(0.0, min(trust_cap, 0.25 + evidence_completeness * 0.55 - conflict_penalty - risk_penalty))

        recommendation: Recommendation
        if trust_invalidations or not symbol_context:
            recommendation = "INSUFFICIENT_DATA"
            reason_codes.append("DATA_TRUST_BLOCK")
        elif conflicts and composite < 75:
            recommendation = "WATCH"
        elif risk_score >= 75:
            recommendation = "NO_ACTION"
            reason_codes.append("RISK_HIGH")
        elif exit_score >= 65:
            recommendation = "SELL_CANDIDATE"
        elif composite >= 70 and confidence >= 0.55:
            recommendation = "BUY_CANDIDATE"
        elif composite >= 45:
            recommendation = "WATCH"
        else:
            recommendation = "NO_ACTION"

        market_regime = "UNKNOWN"
        confluence = market_context.get("confluence") or {}
        if confluence.get("buy_alerts", 0) > confluence.get("sell_alerts", 0):
            market_regime = "RISK_ON"
        elif confluence.get("sell_alerts", 0) > confluence.get("buy_alerts", 0):
            market_regime = "RISK_OFF"

        summary = (
            f"Recommendation={recommendation}, confidence={confidence:.2f}, "
            f"technical={technical_score:.1f}, fundamental={value_score:.1f}, "
            f"money_flow={money_flow_score:.1f}, risk={risk_score:.1f}."
        )

        return IntelligenceResult(
            symbol=symbol,
            market="iran",
            timestamp=data_trust.get("checked_at") or data_trust.get("timestamp"),
            data_trust=data_trust,
            market_regime=market_regime,
            technical_score=round(technical_score, 2),
            fundamental_score=round(value_score, 2),
            money_flow_score=round(money_flow_score, 2),
            filter_score=round(filter_score, 2),
            strategy_score=round(strategy_score, 2),
            risk_score=round(risk_score, 2),
            confidence=round(confidence, 3),
            recommendation=recommendation,
            evidence=evidence,
            warnings=warnings,
            invalidations=invalidations,
            reasoning_summary=summary,
            reason_codes=list(dict.fromkeys(reason_codes)),
            conflicts=conflicts,
            safety={
                "no_autonomous_trading": True,
                "no_broker_order": True,
                "requires_human_approval": True,
                "data_trust_gate_applied": True,
            },
        )
