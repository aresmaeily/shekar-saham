"""Opportunity object and explainable-cluster contracts for RADAR BOURSE.

Corpus loci (2026-10-02 amendment corpus, byte-verified):
- 02_EXECUTION_ROADMAP lines 148–153 (additive §P5/P6): "Opportunity objects
  must distinguish at minimum: market/stock investment candidate;
  user-watchlist company intelligence; event/news-driven candidate; possible
  corporate M&A/acquisition-target signal (only when supported by evidence;
  never conflated with a stock-buy signal). Each object needs evidence,
  timestamp, confidence semantics, data trust, risk, invalidation/expiry, and
  reason-for-now."
- 06_PRODUCT_CAPABILITY_CHARTER §4: the three concepts (stock/investment
  candidate, watchlisted company, possible M&A/acquisition-target
  intelligence) "must never be conflated. An acquisition-target signal
  requires its own evidence and should not be inferred solely from a stock
  opportunity score."
- 06 §6: "Opportunity output should be organized into explainable clusters,
  not only a top-N list. Example candidate classes include early
  accumulation, breakout candidate, relative strength, volume expansion,
  industry rotation, oversold recovery and material fundamental/event change.
  Each class requires a formal definition, data prerequisites, time horizon,
  evidence, confidence semantics, risk, invalidation, expiry and historical
  evaluation." The output must explain "why now?", "what could invalidate
  this?", "what evidence disagrees?", "what is the risk-adjusted
  interpretation?", and "what information is missing?".
- D-AI-33 (05 register): missing or contradictory data is surfaced, not
  invented. D-AI-41: capability ≠ implementation evidence.

Reuse: the kind↔role binding consumes the P0-AMD-1 ``CompanyRole`` literal
(``backend/app/domain/fundamental_dossier.py``), so an opportunity object can
never silently re-define the investment-candidate / watchlist / M&A
distinction. ``EvidenceItem`` ids from the P0-AMD-1 evidence layer are
referenced by id — evidence content itself is never fabricated here.

Contract/domain only: frozen records, deterministic, clock-free, no I/O, no
LLM, no route, no existing module modified. Confidence and risk semantics are
declared fields, not computed scores; this module computes no financial truth
(D-AI-19).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, _finite_decimal, ensure_utc
from app.domain.fundamental_dossier import CompanyRole

OpportunityKind = Literal[
    "MARKET_STOCK_INVESTMENT_CANDIDATE",
    "USER_WATCHLIST_COMPANY_INTELLIGENCE",
    "EVENT_NEWS_DRIVEN_CANDIDATE",
    "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
]

#: Formal candidate classes (06 §6). UNCLASSIFIED is the honest state of an
#: object whose evidence does not yet satisfy any published class definition.
OpportunityClassLabel = Literal[
    "EARLY_ACCUMULATION",
    "BREAKOUT_CANDIDATE",
    "RELATIVE_STRENGTH",
    "VOLUME_EXPANSION",
    "INDUSTRY_ROTATION",
    "OVERSOLD_RECOVERY",
    "MATERIAL_FUNDAMENTAL_EVENT_CHANGE",
    "UNCLASSIFIED",
]

BasisKind = Literal["EVIDENCE_BASED", "OPPORTUNITY_SCORE_ONLY"]

_KIND_TO_ROLE: dict[str, CompanyRole] = {
    "MARKET_STOCK_INVESTMENT_CANDIDATE": "INVESTMENT_CANDIDATE",
    "USER_WATCHLIST_COMPANY_INTELLIGENCE": "WATCHLIST_COMPANY",
    "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL": "MA_TARGET_SIGNAL",
}


class ClassDefinition(BaseModel):
    """Formal definition of one candidate class (06 §6).

    ``historical_evaluation_ref`` stays ``None`` when no versioned evaluation
    exists — it is never fabricated to make a class look validated
    (D-AI-41; 06 §6 "historical evaluation").
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    label: OpportunityClassLabel
    formal_definition: str = Field(min_length=1, max_length=2000)
    data_prerequisites: tuple[str, ...] = Field(min_length=1)
    time_horizon: str = Field(min_length=1, max_length=128)
    historical_evaluation_ref: str | None = None

    @field_validator("data_prerequisites")
    @classmethod
    def _distinct_prereqs(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("data_prerequisites_duplicates")
        return v


class OpportunityObject(BaseModel):
    """One governed opportunity object (02 lines 148–153; 06 §4).

    Required per corpus: evidence (``evidence_ids``), timestamp
    (``created_at_utc``), confidence semantics (``confidence`` +
    ``confidence_basis``), data trust (``data_trust_state``), risk
    (``risk_semantics``), invalidation/expiry, and reason-for-now.
    """

    model_config = ConfigDict(frozen=True)

    object_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    opportunity_kind: OpportunityKind
    company_role: CompanyRole
    subject: str = Field(min_length=1, max_length=128)
    class_label: OpportunityClassLabel = "UNCLASSIFIED"
    class_definition: ClassDefinition | None = None
    created_at_utc: datetime
    reason_for_now: str = Field(min_length=1, max_length=1000)
    confidence: Decimal
    confidence_basis: str = Field(min_length=1, max_length=256)
    data_trust_state: str = Field(min_length=1, max_length=64)
    risk_semantics: str = Field(min_length=1, max_length=1000)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    contradicting_evidence_ids: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = Field(min_length=1)
    expiry_utc: datetime | None = None
    expiry_open_ended: bool = False
    basis: BasisKind
    ma_signal_evidence_ids: tuple[str, ...] = ()
    run_id: str = Field(min_length=1, max_length=128)
    notes: str = ""

    @field_validator("created_at_utc", "expiry_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: Decimal) -> Decimal:
        d = _finite_decimal(v)
        if d < 0 or d > 1:
            raise ValueError("confidence_out_of_range")
        return d

    @field_validator("evidence_ids", "invalidation_conditions", "ma_signal_evidence_ids")
    @classmethod
    def _distinct(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate_items")
        return v

    @model_validator(mode="after")
    def _corpus_guards(self) -> "OpportunityObject":
        # 06 §4: the three concepts must never be conflated (02 lines 148–153).
        expected_role = _KIND_TO_ROLE.get(self.opportunity_kind)
        if expected_role is not None and self.company_role != expected_role:
            raise ValueError("opportunity_kind_company_role_conflation")
        # 06 §4: an acquisition-target signal requires its own evidence and
        # must not be inferred solely from a stock opportunity score.
        if self.opportunity_kind == "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL":
            if self.basis != "EVIDENCE_BASED":
                raise ValueError("ma_signal_requires_evidence_basis")
            if not self.ma_signal_evidence_ids:
                raise ValueError("ma_signal_requires_dedicated_evidence")
        # 06 §6: a labelled class must carry its formal definition; an
        # UNCLASSIFIED object must not pretend to have one.
        if self.class_label == "UNCLASSIFIED":
            if self.class_definition is not None:
                raise ValueError("unclassified_object_cannot_carry_class_definition")
        elif self.class_definition is None:
            raise ValueError("labelled_class_requires_class_definition")
        elif self.class_definition.label != self.class_label:
            raise ValueError("class_definition_label_mismatch")
        # Expiry must be an explicit decision, never a forgotten default.
        if self.expiry_utc is None and not self.expiry_open_ended:
            raise ValueError("expiry_must_be_dated_or_explicitly_open_ended")
        if self.expiry_utc is not None and self.expiry_open_ended:
            raise ValueError("open_ended_expiry_forbids_date")
        if self.object_id in self.evidence_ids:
            raise ValueError("object_id_reused_as_evidence_id")
        return self


def is_expired(object_: OpportunityObject, at_utc: datetime) -> bool:
    """Deterministic expiry check (02 line 153: invalidation/expiry)."""
    if object_.expiry_utc is None:
        return False
    return object_.expiry_utc <= ensure_utc(at_utc)


def active_at(object_: OpportunityObject, at_utc: datetime) -> bool:
    """True when the object is neither expired nor created after the cutoff."""
    cutoff = ensure_utc(at_utc)
    if object_.created_at_utc > cutoff:
        return False
    return not is_expired(object_, at_utc)


class OpportunityCluster(BaseModel):
    """Explainable opportunity cluster (06 §6).

    The five corpus questions are structurally required: why-now,
    invalidation conditions, disagreeing evidence, a risk-adjusted
    interpretation, and the always-honest missing-information list.
    Clusters organize objects BY class; an UNCLASSIFIED cluster is refused.
    """

    model_config = ConfigDict(frozen=True)

    cluster_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    class_label: OpportunityClassLabel
    class_definition: ClassDefinition
    member_object_ids: tuple[str, ...] = Field(min_length=1)
    created_at_utc: datetime
    run_id: str = Field(min_length=1, max_length=128)
    why_now: str = Field(min_length=1, max_length=2000)
    invalidation_conditions: tuple[str, ...] = Field(min_length=1)
    disagreeing_evidence_ids: tuple[str, ...] = ()
    risk_adjusted_interpretation: str = Field(min_length=1, max_length=2000)
    missing_information: tuple[str, ...] = Field(min_length=1)
    confidence: Decimal
    confidence_basis: str = Field(min_length=1, max_length=256)
    notes: str = ""

    @field_validator("created_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: Decimal) -> Decimal:
        d = _finite_decimal(v)
        if d < 0 or d > 1:
            raise ValueError("confidence_out_of_range")
        return d

    @field_validator("member_object_ids", "invalidation_conditions", "missing_information")
    @classmethod
    def _distinct(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate_items")
        return v

    @model_validator(mode="after")
    def _cluster_guards(self) -> "OpportunityCluster":
        if self.class_label == "UNCLASSIFIED":
            raise ValueError("cluster_requires_concrete_class")
        if self.class_definition.label != self.class_label:
            raise ValueError("class_definition_label_mismatch")
        return self
