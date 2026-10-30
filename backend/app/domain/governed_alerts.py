"""Governed operational-alert taxonomy for RADAR_BOURSE (P5/P6).

Corpus loci (2026-10-02 amendment corpus, byte-verified):
- 02_EXECUTION_ROADMAP lines 147–153 (additive §"P5/P6 — Alerts, company
  coverage and opportunity lifecycle"): "Operational alerts must cover market
  anomalies, material company disclosures, filing/report publication, source
  conflicts, source staleness, significant financial-statement changes,
  watchlist changes, opportunity creation/expiry, and research-result
  maturity." — exactly the nine closed kinds below; unknown alert kinds are
  unrepresentable.
- 06_PRODUCT_CAPABILITY_CHARTER §4: an acquisition-target signal "requires
  its own evidence and should not be inferred solely from a stock opportunity
  score" — carried through to the alert layer via the dedicated M&A evidence
  guard.
- 06 §9 / 02 lines 181–186 / register D-AI-30: cadence, thresholds, budgets
  and delivery require explicit owner-approved configuration. This module is
  the alert CONTRACT only: no route, no scheduler, no delivery, no I/O, no
  LLM, no live data. Nothing here can dispatch, send, or schedule anything.

Reuse (read-only imports; no existing module modified — speed rule
"additive contracts over replacement"):
- ``external_intelligence.ContentKind`` — the declared document/content kinds
  that disclosure and filing alerts must anchor to.
- The trigger objects whose ids these alerts cite live in the existing
  governed layers: ``evidence.EvidenceConflict`` (source conflicts),
  ``source_registry.CoverageReport.stale_sources`` (staleness),
  ``fundamental_dossier.FundamentalFact`` restatement chain (statement
  changes), ``prediction.PredictionRecord``/``OutcomeRecord`` (maturity),
  ``opportunity.OpportunityObject`` (lifecycle), ``monitoring.MonitoringJobSpec``
  (job identity). The module references them BY ID; it never re-defines or
  fabricates their semantics (D-AI-33/41).

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
from app.domain.external_intelligence import ContentKind
from app.domain.opportunity import OpportunityKind

#: The nine corpus-mandated operational alert classes (02 lines 148–149),
#: in corpus order. Closed set: an unlisted alert kind cannot be expressed.
AlertKind = Literal[
    "MARKET_ANOMALY",
    "MATERIAL_COMPANY_DISCLOSURE",
    "FILING_REPORT_PUBLICATION",
    "SOURCE_CONFLICT",
    "SOURCE_STALENESS",
    "SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE",
    "WATCHLIST_CHANGE",
    "OPPORTUNITY_LIFECYCLE",
    "RESEARCH_RESULT_MATURITY",
]

#: Content kinds eligible to anchor each disclosure/filing alert class.
#: Filing publication alerts anchor to filing-class content; material company
#: disclosure alerts anchor to disclosure-class content. Other content kinds
#: cannot masquerade as either.
_FILING_CONTENT_KINDS: tuple[str, ...] = (
    "FILING",
    "FINANCIAL_STATEMENT",
    "NOTE",
    "AUDITOR_OPINION",
)
_DISCLOSURE_CONTENT_KINDS: tuple[str, ...] = (
    "MATERIAL_EVENT",
    "COMPANY_DISCLOSURE",
    "GUIDANCE",
)

WatchlistChangeKind = Literal["ADDED", "REMOVED", "UPDATED"]
OpportunityLifecycleTransition = Literal["CREATED", "EXPIRED"]


class GovernedAlertObject(BaseModel):
    """One governed operational alert (02 lines 147–153).

    Required per corpus for EVERY alert regardless of kind: evidence
    (``evidence_ids``), timestamp (``created_at_utc``), confidence semantics
    (``confidence`` + ``confidence_basis``), data trust (``data_trust_state``),
    risk (``risk_semantics``), invalidation (``invalidation_conditions``),
    explicit expiry decision, and reason-for-now (``reason_for_now``).

    Per-kind trigger binding (§4 of the scope derivation): the kind's own
    dedicated binding field is REQUIRED; every other kind's dedicated binding
    field MUST stay empty so two alert kinds can never share or launder a
    trigger reference.
    """

    model_config = ConfigDict(frozen=True)

    alert_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    alert_kind: AlertKind
    subject: str = Field(min_length=1, max_length=128)
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
    run_id: str = Field(min_length=1, max_length=128)
    notes: str = ""

    # --- per-kind dedicated trigger bindings -------------------------------
    # MARKET_ANOMALY
    detector_ref: str | None = None
    # MATERIAL_COMPANY_DISCLOSURE / FILING_REPORT_PUBLICATION
    content_kind: ContentKind | None = None
    # SOURCE_CONFLICT
    conflict_id: str | None = None
    # SOURCE_STALENESS
    stale_source_ids: tuple[str, ...] = ()
    # SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE
    fact_id: str | None = None
    superseded_fact_id: str | None = None
    # WATCHLIST_CHANGE
    watchlist_ref: str | None = None
    change_kind: WatchlistChangeKind | None = None
    # OPPORTUNITY_LIFECYCLE
    opportunity_object_id: str | None = None
    lifecycle_transition: OpportunityLifecycleTransition | None = None
    # OPPORTUNITY_LIFECYCLE referencing an M&A-kind opportunity (06 §4)
    referenced_opportunity_kind: OpportunityKind | None = None
    ma_signal_evidence_ids: tuple[str, ...] = ()
    # RESEARCH_RESULT_MATURITY
    prediction_id: str | None = None
    outcome_id: str | None = None

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

    @field_validator(
        "evidence_ids",
        "invalidation_conditions",
        "contradicting_evidence_ids",
        "stale_source_ids",
        "ma_signal_evidence_ids",
    )
    @classmethod
    def _distinct(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate_items")
        return v

    @model_validator(mode="after")
    def _corpus_guards(self) -> "GovernedAlertObject":
        # Expiry must be an explicit decision, never a forgotten default.
        if self.expiry_utc is None and not self.expiry_open_ended:
            raise ValueError("expiry_must_be_dated_or_explicitly_open_ended")
        if self.expiry_utc is not None and self.expiry_open_ended:
            raise ValueError("open_ended_expiry_forbids_date")
        if self.alert_id in self.evidence_ids:
            raise ValueError("alert_id_reused_as_evidence_id")
        if self.alert_id in self.ma_signal_evidence_ids:
            raise ValueError("alert_id_reused_as_ma_evidence_id")

        k = self.alert_kind
        # Required dedicated binding per kind.
        if k == "MARKET_ANOMALY" and not self.detector_ref:
            raise ValueError("market_anomaly_requires_detector_ref")
        if k == "MATERIAL_COMPANY_DISCLOSURE":
            if self.content_kind is None:
                raise ValueError("disclosure_alert_requires_content_kind")
            if self.content_kind not in _DISCLOSURE_CONTENT_KINDS:
                raise ValueError("disclosure_alert_content_kind_mismatch")
        if k == "FILING_REPORT_PUBLICATION":
            if self.content_kind is None:
                raise ValueError("filing_alert_requires_content_kind")
            if self.content_kind not in _FILING_CONTENT_KINDS:
                raise ValueError("filing_alert_content_kind_mismatch")
        if k == "SOURCE_CONFLICT" and not self.conflict_id:
            raise ValueError("source_conflict_alert_requires_conflict_id")
        if k == "SOURCE_STALENESS" and not self.stale_source_ids:
            raise ValueError("source_staleness_alert_requires_stale_source_ids")
        if k == "SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE":
            if not self.fact_id or not self.superseded_fact_id:
                raise ValueError("statement_change_alert_requires_restatement_chain")
            if self.fact_id == self.superseded_fact_id:
                raise ValueError("statement_change_fact_chain_self_reference")
        if k == "WATCHLIST_CHANGE":
            if not self.watchlist_ref:
                raise ValueError("watchlist_alert_requires_watchlist_ref")
            if self.change_kind is None:
                raise ValueError("watchlist_alert_requires_change_kind")
        if k == "OPPORTUNITY_LIFECYCLE":
            if not self.opportunity_object_id:
                raise ValueError("opportunity_alert_requires_opportunity_object_id")
            if self.lifecycle_transition is None:
                raise ValueError("opportunity_alert_requires_lifecycle_transition")
            # 06 §4: an M&A acquisition-target signal is never a stock-buy
            # signal; its dedicated evidence must be carried through to the
            # alert layer, never dropped.
            if self.referenced_opportunity_kind == "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL":
                if not self.ma_signal_evidence_ids:
                    raise ValueError("ma_lifecycle_alert_requires_dedicated_ma_evidence")
        if k == "RESEARCH_RESULT_MATURITY":
            if not self.prediction_id or not self.outcome_id:
                raise ValueError("maturity_alert_requires_prediction_and_outcome_ids")

        # Cross-kind contamination: a kind's dedicated binding field must
        # stay empty on every other kind.
        if k != "MARKET_ANOMALY" and self.detector_ref is not None:
            raise ValueError("detector_ref_outside_market_anomaly_kind")
        if k not in ("MATERIAL_COMPANY_DISCLOSURE", "FILING_REPORT_PUBLICATION") and self.content_kind is not None:
            raise ValueError("content_kind_outside_disclosure_filing_kinds")
        if k != "SOURCE_CONFLICT" and self.conflict_id is not None:
            raise ValueError("conflict_id_outside_source_conflict_kind")
        if k != "SOURCE_STALENESS" and self.stale_source_ids:
            raise ValueError("stale_source_ids_outside_source_staleness_kind")
        if k != "SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE" and (self.fact_id is not None or self.superseded_fact_id is not None):
            raise ValueError("fact_chain_outside_statement_change_kind")
        if k != "WATCHLIST_CHANGE" and (self.watchlist_ref is not None or self.change_kind is not None):
            raise ValueError("watchlist_binding_outside_watchlist_kind")
        if k != "OPPORTUNITY_LIFECYCLE":
            if self.opportunity_object_id is not None or self.lifecycle_transition is not None or self.referenced_opportunity_kind is not None:
                raise ValueError("opportunity_binding_outside_opportunity_lifecycle_kind")
            if self.ma_signal_evidence_ids:
                raise ValueError("ma_evidence_outside_opportunity_lifecycle_kind")
        if k != "RESEARCH_RESULT_MATURITY" and (self.prediction_id is not None or self.outcome_id is not None):
            raise ValueError("maturity_binding_outside_research_maturity_kind")
        return self


def is_expired(alert: GovernedAlertObject, at_utc: datetime) -> bool:
    """Deterministic expiry check (mirrors the opportunity layer)."""
    if alert.expiry_utc is None:
        return False
    return alert.expiry_utc <= ensure_utc(at_utc)


def active_at(alert: GovernedAlertObject, at_utc: datetime) -> bool:
    """True when the alert neither expires before nor is created after the cutoff."""
    cutoff = ensure_utc(at_utc)
    if alert.created_at_utc > cutoff:
        return False
    return not is_expired(alert, at_utc)


#: The complete contract surface. Nothing that can dispatch, send, publish,
#: schedule, or deliver an alert exists here (06 §9 / D-AI-30 owner-gated).
__all__ = [
    "AlertKind",
    "GovernedAlertObject",
    "OpportunityLifecycleTransition",
    "WatchlistChangeKind",
    "active_at",
    "is_expired",
]
