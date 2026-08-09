"""Filter Intelligence contracts for RADAR BOURSE.

P3.41 scope: filter registry, immutable versions, performance records,
evaluation, optimization proposals and human approval contracts. This module is
contract/domain only: it does not trade, mutate active production filters, or
claim live profitability.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FilterStatus = Literal["DRAFT", "ACTIVE", "PAUSED", "DEPRECATED", "ARCHIVED"]
EvaluationMode = Literal["BACKTEST", "WALK_FORWARD", "FORWARD_TEST", "MONITORING"]
FilterClassification = Literal["EXCELLENT", "GOOD", "STABLE", "DEGRADING", "WEAK", "INVALID", "INSUFFICIENT_DATA"]
ProposalStatus = Literal["PROPOSED", "BACKTESTED", "VALIDATED", "APPROVED", "REJECTED", "ROLLED_BACK"]
ReviewDecision = Literal["APPROVE", "REJECT", "REQUEST_RETEST"]
OptimizationAction = Literal["REVIEW", "PAUSE", "DEPRECATE", "KEEP", "OPTIMIZE", "COMBINE"]

NOT_AVAILABLE = "NOT_AVAILABLE"


class FilterVersion(BaseModel):
    filter_id: str
    name: str
    version: str
    description: str = ""
    market: str = "iran"
    status: FilterStatus = "DRAFT"
    conditions: str
    created_at: str
    updated_at: str
    owner: str = "radar-bourse"
    tags: list[str] = Field(default_factory=list)
    parent_version: str | None = None
    change_summary: str = ""
    validation: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(
        default_factory=lambda: {
            "ai_can_modify_production": False,
            "requires_human_approval": True,
            "no_autonomous_trading": True,
            "no_broker_order": True,
        }
    )


class FilterRegistryItem(BaseModel):
    filter_id: str
    name: str
    market: str = "iran"
    status: FilterStatus = "DRAFT"
    active_version: str | None = None
    latest_version: str | None = None
    description: str = ""
    owner: str = "radar-bourse"
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    versions: list[FilterVersion] = Field(default_factory=list)


class PerformanceRecord(BaseModel):
    record_id: str
    filter_id: str
    version: str
    evaluation_mode: EvaluationMode
    evaluation_period: str
    market: str = "iran"
    sample_size: int = 0
    signal_count: int = 0
    win_rate: float | str = NOT_AVAILABLE
    average_return: float | str = NOT_AVAILABLE
    median_return: float | str = NOT_AVAILABLE
    profit_factor: float | str = NOT_AVAILABLE
    max_drawdown: float | str = NOT_AVAILABLE
    sharpe: float | str = NOT_AVAILABLE
    precision: float | str = NOT_AVAILABLE
    false_positive_rate: float | str = NOT_AVAILABLE
    stability_score: float | str = NOT_AVAILABLE
    regime: str = "INSUFFICIENT_DATA"
    regime_performance: dict[str, Any] = Field(default_factory=dict)
    data_trust: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    classification: FilterClassification = "INSUFFICIENT_DATA"
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_result: dict[str, Any] = Field(default_factory=dict)


class FilterDecaySignal(BaseModel):
    filter_id: str
    version: str
    status: Literal["NO_DECAY", "PERFORMANCE_DECAY", "INSUFFICIENT_DATA"] = "INSUFFICIENT_DATA"
    severity: Literal["low", "medium", "high"] = "low"
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class FilterAnalysisResult(BaseModel):
    filter_id: str
    version: str
    classification: FilterClassification = "INSUFFICIENT_DATA"
    action: OptimizationAction = "REVIEW"
    confidence: float = 0.0
    current_regime: str = "INSUFFICIENT_DATA"
    historical: dict[str, Any] = Field(default_factory=dict)
    walk_forward: dict[str, Any] = Field(default_factory=dict)
    forward: dict[str, Any] = Field(default_factory=dict)
    decay: FilterDecaySignal
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: str = "REVIEW"
    reason_codes: list[str] = Field(default_factory=list)
    data_trust: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)


class OptimizationProposal(BaseModel):
    proposal_id: str
    filter_id: str
    current_version: str
    proposed_version: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    reasoning: str = ""
    expected_effect: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    backtest_result: dict[str, Any] = Field(default_factory=dict)
    walk_forward_result: dict[str, Any] = Field(default_factory=dict)
    forward_result: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    risk: str = "UNKNOWN"
    status: ProposalStatus = "PROPOSED"
    created_at: str
    updated_at: str
    human_approval_required: bool = True
    production_mutation: bool = False


class ProposalReview(BaseModel):
    proposal_id: str
    reviewer: str
    decision: ReviewDecision
    timestamp: str
    reason: str = ""
    resulting_status: ProposalStatus
    safety: dict[str, Any] = Field(default_factory=dict)


class FilterComparison(BaseModel):
    filter_id: str
    left_version: str
    right_version: str
    metrics: dict[str, dict[str, Any]] = Field(default_factory=dict)
    regime_performance: dict[str, Any] = Field(default_factory=dict)
    forward_performance: dict[str, Any] = Field(default_factory=dict)
    conclusion: str = "INSUFFICIENT_DATA"
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    data_trust: dict[str, Any] = Field(default_factory=dict)
