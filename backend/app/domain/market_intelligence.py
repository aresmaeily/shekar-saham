"""Market Intelligence contracts for RADAR BOURSE.

P3.40 scope: market-level intelligence, opportunity ranking, change detection
and lightweight history. No autonomous trading, global expansion or scheduler is
implemented here.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.ai_intelligence import IntelligenceResult

MarketRegime = Literal[
    "BULLISH",
    "BEARISH",
    "NEUTRAL",
    "HIGH_VOLATILITY",
    "LOW_LIQUIDITY",
    "RISK_OFF",
    "INSUFFICIENT_DATA",
]
EventType = Literal[
    "REGIME_CHANGED",
    "OPPORTUNITY_APPEARED",
    "OPPORTUNITY_LOST",
    "RECOMMENDATION_CHANGED",
    "RISK_INCREASED",
    "RISK_DECREASED",
    "INDUSTRY_LEADERSHIP_CHANGED",
    "MONEY_FLOW_SHIFTED",
]
Severity = Literal["low", "medium", "high"]


class MarketIntelligenceSnapshot(BaseModel):
    timestamp: float
    market: str = "iran"
    market_status: str = "open_unknown"
    total_symbols: int = 0
    positive_symbols: int = 0
    negative_symbols: int = 0
    unchanged_symbols: int = 0
    total_trade_value: float = 0.0
    total_volume: float = 0.0
    market_money_flow: float = 0.0
    buyer_power: float = 0.0
    seller_power: float = 0.0
    market_regime: MarketRegime = "INSUFFICIENT_DATA"
    confidence: float = 0.0
    risk_level: str = "UNKNOWN"
    industry_summary: list[dict[str, Any]] = Field(default_factory=list)
    top_opportunities: list[dict[str, Any]] = Field(default_factory=list)
    top_risks: list[dict[str, Any]] = Field(default_factory=list)
    data_trust: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IndustryIntelligence(BaseModel):
    industry: str
    score: float = 0.0
    breadth: float = 0.0
    money_flow: float = 0.0
    opportunity: float = 0.0
    risk: float = 0.0
    confidence: float = 0.0
    symbol_count: int = 0
    data_trust: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "INSUFFICIENT_DATA"


class OpportunityRank(BaseModel):
    rank: int
    symbol: str
    name: str = ""
    industry: str = ""
    overall_score: float = 0.0
    confidence: float = 0.0
    money_flow_score: float = 0.0
    technical_score: float = 0.0
    fundamental_score: float = 0.0
    filter_score: float = 0.0
    strategy_score: float = 0.0
    risk_score: float = 100.0
    recommendation: str = "INSUFFICIENT_DATA"
    data_trust: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IntelligenceEvent(BaseModel):
    event_id: str
    timestamp: float
    event_type: EventType
    market: str = "iran"
    symbol: str = ""
    industry: str = ""
    severity: Severity = "low"
    previous_state: dict[str, Any] = Field(default_factory=dict)
    current_state: dict[str, Any] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    data_trust: dict[str, Any] = Field(default_factory=dict)


class MarketMonitoringResult(BaseModel):
    snapshot: MarketIntelligenceSnapshot
    industries: list[IndustryIntelligence] = Field(default_factory=list)
    opportunities: list[OpportunityRank] = Field(default_factory=list)
    events: list[IntelligenceEvent] = Field(default_factory=list)
    symbol_intelligence: list[IntelligenceResult] = Field(default_factory=list)
    history_count: int = 0
