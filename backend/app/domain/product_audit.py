"""AI Product Intelligence & improvement proposal contracts for RADAR BOURSE.

P0 addendum scope (Binding additive amendment 2026-10-02,
02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md line 138): "product audit charter,
privacy-safe telemetry boundaries, test cadence, baseline metrics, and
improvement proposal contract".

Design references:
- 06 charter §8: separate audit domains; "Backtest is not a universal test for
  all software components. The evaluator must match the domain."; each audit
  produces ranked proposals with baseline, evidence, expected impact,
  uncertainty, cost, risk, experiment design, rollback and human approval
  state. Production changes and releases remain human-controlled.
- 02 roadmap line 179: the system "must not automatically change production,
  promote filters, alter permissions/budgets, or deploy software."
- D-AI-35, D-AI-36, D-AI-39 (05 register): proposals are advisory with
  baseline/evidence/uncertainty/risk/rollback; domain-appropriate evaluation;
  telemetry is minimum-necessary, privacy-safe, access-controlled with
  documented aggregation/retention/access/deletion rules.

Contract/domain only. The improvement-proposal approval state machine
structurally CANNOT represent a production application step: no state named
APPLIED/DEPLOYED/PROMOTED exists, and `advisory_only` is type-locked to True.
Recommendations remain advisory until their appropriate evaluation and
approval gates are passed (04 charter additive).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.evidence import SCHEMA_VERSION

ProductAuditDomain = Literal[
    "FILTERS_STRATEGIES",
    "MARKET_FUNDAMENTAL_AI",
    "DATA_PROVIDER_OPERATIONS",
    "PRODUCT_UX",
    "SOFTWARE_QUALITY",
    # WAVE-AB5 (WP-H, additive): the AI-7 evaluation-domain audit recorded that
    # domains 12/13/14 of the 15 required evaluation domains had NO code.
    # These three members close that gap additively; the domain/evaluator
    # matching rule below is unchanged (backtest-family evaluators stay
    # bound to FILTERS_STRATEGIES only — 06 charter §8).
    "ACCESSIBILITY",
    "FEATURE_ADOPTION",
    "TASK_COMPLETION",
]

EvaluatorKind = Literal[
    "BACKTEST",
    "WALK_FORWARD",
    "FORWARD_TEST",
    "GOLDEN_SET",
    "REGRESSION",
    "PERFORMANCE",
    "SECURITY",
    "RELIABILITY",
    "UX_REVIEW",
    "MANUAL_REVIEW",
]

CadenceMode = Literal["EVENT_DRIVEN", "SCHEDULED", "WEEKLY", "MONTHLY", "OWNER_CONFIGURED"]
KillSwitchState = Literal["ENGAGED", "RELEASED"]
ProposalApprovalState = Literal[
    "PROPOSED",
    "UNDER_REVIEW",
    "APPROVED_FOR_EVALUATION",
    "EVALUATED",
    "REJECTED",
]

#: 06 charter §8: backtest-family evaluators apply to financial hypotheses,
#: not to arbitrary UI or software components.
_FINANCIAL_EVALUATORS: frozenset[str] = frozenset({"BACKTEST", "WALK_FORWARD", "FORWARD_TEST"})


def evaluator_allowed_for_domain(domain: str, evaluator: str) -> bool:
    """Deterministic domain/evaluator matching rule (06 charter §8)."""
    if evaluator in _FINANCIAL_EVALUATORS:
        return domain == "FILTERS_STRATEGIES"
    return True


class AuditCadence(BaseModel):
    """Owner-configurable cadence for one audit domain. No universal SLA is
    hard-coded (02 roadmap additive §Initial cadence policy): the expression
    is provided by configuration or stays explicitly unset."""

    model_config = ConfigDict(frozen=True)

    domain: ProductAuditDomain
    schema_version: str = SCHEMA_VERSION
    mode: CadenceMode
    cadence_expression: str | None = None
    budget_ref: str | None = None
    kill_switch: KillSwitchState = "ENGAGED"
    notes: str = ""

    @model_validator(mode="after")
    def _consistency(self) -> "AuditCadence":
        if self.mode == "OWNER_CONFIGURED" and not self.cadence_expression:
            raise ValueError("owner_configured_cadence_requires_expression")
        return self


class PrivacyTelemetryBoundary(BaseModel):
    """Privacy-safe telemetry boundary (D-AI-39).

    `sensitive_content_repurposing` is type-locked to False at this contract
    layer: sensitive user content is never repurposed without a lawful,
    approved basis, and such a basis must be recorded by a future,
    owner-approved contract revision — never inferred here.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    data_classes: tuple[str, ...] = Field(min_length=1)
    lawful_basis: str = Field(min_length=1)
    aggregation_only: Literal[True] = True
    sensitive_content_repurposing: Literal[False] = False
    access_control: str = Field(min_length=1)
    retention_rule: str = Field(min_length=1)
    deletion_rule: str = Field(min_length=1)
    notes: str = ""


class ImprovementProposal(BaseModel):
    """Advisory improvement proposal — cannot mutate production.

    The approval state machine ends at EVALUATED/REJECTED: application to
    production is deliberately unrepresentable. `advisory_only` is
    type-locked to True (02 roadmap line 179; D-AI-35).
    """

    model_config = ConfigDict(frozen=True)

    proposal_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    domain: ProductAuditDomain
    evaluator_kind: EvaluatorKind
    baseline: dict[str, float] = Field(default_factory=dict)
    expected_benefit: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    uncertainty: str = Field(min_length=1)
    cost: str = Field(min_length=1)
    risks: tuple[str, ...] = ()
    rollback_plan: str = Field(min_length=1)
    evaluation_design: str = Field(min_length=1)
    approval_state: ProposalApprovalState = "PROPOSED"
    advisory_only: Literal[True] = True
    notes: str = ""

    @model_validator(mode="after")
    def _consistency(self) -> "ImprovementProposal":
        if not evaluator_allowed_for_domain(self.domain, self.evaluator_kind):
            raise ValueError("evaluator_not_allowed_for_domain")
        return self


class ProductAuditCharter(BaseModel):
    """Versioned audit charter binding domains, cadences and telemetry rules."""

    model_config = ConfigDict(frozen=True)

    charter_version: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    domains: tuple[ProductAuditDomain, ...] = Field(min_length=1)
    cadences: tuple[AuditCadence, ...] = ()
    telemetry_boundary: PrivacyTelemetryBoundary
    baseline_metrics_ref: str = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def _consistency(self) -> "ProductAuditCharter":
        domains = [c.domain for c in self.cadences]
        if len(domains) != len(set(domains)):
            raise ValueError("duplicate_cadence_domains")
        for cadence in self.cadences:
            if cadence.domain not in self.domains:
                raise ValueError("cadence_domain_not_in_charter")
        return self
