"""P0-AMD-1 acceptance tests: identity/PIT semantics (D2), fundamental dossier
and the 3-way role distinction (D4), product audit charter + proposals (D6),
prediction registry and outcome maturity (D7).

Tests are derived from the amendment corpus acceptance criteria
(docs/active/P0_AMENDMENT_CONTRACTS_SCOPE_DERIVATION_REPORT.md §3), not from
the implementation: each test cites its corpus requirement.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import get_args

import pytest
from pydantic import ValidationError

from app.domain.evidence import Period
from app.domain.fundamental_dossier import (
    CompanyDossier,
    CompanyIdentity,
    CorporateActionRecord,
    FilingPeriod,
    FundamentalFact,
    RoleClassification,
)
from app.domain.prediction import (
    OutcomeRecord,
    PredictionEvaluation,
    PredictionRecord,
    PredictionRegistry,
    maturity_state,
)
from app.domain.product_audit import (
    AuditCadence,
    ImprovementProposal,
    PrivacyTelemetryBoundary,
    ProductAuditCharter,
    ProposalApprovalState,
    evaluator_allowed_for_domain,
)

T0 = datetime(2025, 12, 31, tzinfo=timezone.utc)  # filing publication
T1 = datetime(2026, 1, 15, tzinfo=timezone.utc)   # retrieval
T_CUT = datetime(2026, 3, 1, tzinfo=timezone.utc)  # information cutoff
T_LATE = datetime(2026, 8, 1, tzinfo=timezone.utc)  # later restatement publication


def _identity(**over) -> CompanyIdentity:
    base = dict(
        company_id="co-1", symbols=("فملی",), resolution_basis="OFFICIAL_SYMBOL_MAP",
        ambiguity_status="UNAMBIGUOUS", resolved_at_utc=T1,
        source_evidence_ids=("ev-id-1",),
    )
    base.update(over)
    return CompanyIdentity(**base)


def _filing(**over) -> FilingPeriod:
    base = dict(
        filing_id="f-1", company_id="co-1",
        reporting_period=Period(period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
                                period_end=datetime(2025, 12, 31, tzinfo=timezone.utc)),
        fiscal_calendar="iran-fiscal-1404", publication_status="KNOWN",
        publication_time_utc=T0, retrieval_time_utc=T1,
        source_evidence_ids=("ev-f-1",),
    )
    base.update(over)
    return FilingPeriod(**base)


def _fact(**over) -> FundamentalFact:
    base = dict(
        fact_id="fact-1", company_id="co-1", metric="revenue", value=Decimal("1000.5"),
        value_status="REPORTED", unit="billion-IRR", currency="IRR", period=_filing(),
        source_evidence_ids=("ev-f-1",),
    )
    base.update(over)
    return FundamentalFact(**base)


def _dossier(**over) -> CompanyDossier:
    base = dict(
        dossier_id="dos-1", company_id="co-1", information_cutoff_utc=T_CUT,
        identity=_identity(), facts=(_fact(),), pit_eligible=True,
        data_trust_ref="data-trust-context-v1",
        limitations=("single primary source",),
    )
    base.update(over)
    return CompanyDossier(**base)


# ---------------------------------------------------------------------------
# D2 — identity, corporate actions, filing periods, restatements
# ---------------------------------------------------------------------------


def test_identity_ambiguity_is_surfaced_not_resolved() -> None:
    """D-AI-33 / 06 §3.4: ambiguous identity stays explicit with candidates."""
    amb = _identity(ambiguity_status="AMBIGUOUS_UNRESOLVED", candidate_matches=("co-1", "co-2"))
    assert amb.ambiguity_status == "AMBIGUOUS_UNRESOLVED"
    with pytest.raises(ValidationError, match="ambiguous_identity_requires_candidate_matches"):
        _identity(ambiguity_status="AMBIGUOUS_UNRESOLVED")


def test_publication_time_never_defaulted_in_filing_or_action() -> None:
    with pytest.raises(ValidationError, match="known_publication_requires_timestamp"):
        _filing(publication_time_utc=None, publication_status="KNOWN")
    unknown = _filing(publication_time_utc=None, publication_status="UNAVAILABLE")
    assert unknown.publication_time_utc is None
    with pytest.raises(ValidationError, match="unavailable_publication_forbids_timestamp"):
        CorporateActionRecord(
            action_id="ca-1", company_id="co-1", action_type="DIVIDEND",
            publication_time_utc=T0, publication_status="UNAVAILABLE",
            value_status="NOT_AVAILABLE", source_evidence_ids=("ev-ca",),
        )


def test_corporate_action_requires_value_with_unit_when_reported() -> None:
    ok = CorporateActionRecord(
        action_id="ca-1", company_id="co-1", action_type="CAPITAL_INCREASE",
        publication_status="KNOWN", publication_time_utc=T0, value=Decimal("20"),
        value_status="REPORTED", value_unit="percent", source_evidence_ids=("ev-ca",),
    )
    assert ok.value_unit == "percent"
    with pytest.raises(ValidationError, match="reported_value_requires_value_and_unit"):
        CorporateActionRecord(action_id="ca-2", company_id="co-1", action_type="DIVIDEND",
                              publication_status="UNAVAILABLE", value=Decimal("1"),
                              value_status="REPORTED", source_evidence_ids=("ev-ca",))
    with pytest.raises(ValidationError, match="not_available_value_forbids_value"):
        CorporateActionRecord(action_id="ca-3", company_id="co-1", action_type="DIVIDEND",
                              publication_status="UNAVAILABLE", value=Decimal("1"),
                              value_status="NOT_AVAILABLE", source_evidence_ids=("ev-ca",))


def test_restatements_create_new_versions_and_keep_history() -> None:
    """06 §3.6: restatements create new versions; history is never edited."""
    restated = _fact(
        fact_id="fact-2", value=Decimal("1200"), restatement_version=2,
        supersedes_fact_id="fact-1",
        period=_filing(filing_id="f-2", restatement_of="f-1",
                       publication_time_utc=T_LATE),
    )
    assert restated.restatement_version == 2 and restated.supersedes_fact_id == "fact-1"
    with pytest.raises(ValidationError, match="restatement_requires_superseded_fact"):
        _fact(fact_id="fact-3", restatement_version=2)


# ---------------------------------------------------------------------------
# D4 — fundamental facts, dossier, 3-way role distinction
# ---------------------------------------------------------------------------


def test_reported_fact_requires_value_unit_and_currency() -> None:
    """06 §3.7 / D-AI-33: units/currency explicit; missing value never invented."""
    with pytest.raises(ValidationError, match="reported_fact_requires_value_unit_currency"):
        _fact(currency=None)
    with pytest.raises(ValidationError, match="reported_fact_requires_value_unit_currency"):
        _fact(unit=None)
    na = _fact(value=None, value_status="NOT_AVAILABLE", unit=None, currency=None)
    assert na.value is None and na.value_status == "NOT_AVAILABLE"
    with pytest.raises(ValidationError, match="not_available_fact_forbids_value"):
        _fact(value_status="NOT_AVAILABLE")


def test_financial_values_are_finite_decimals() -> None:
    with pytest.raises(ValidationError, match="finite"):
        _fact(value=Decimal("NaN"))
    with pytest.raises(ValidationError, match="finite"):
        _fact(value=Decimal("Infinity"))


def test_ma_target_signal_requires_own_evidence_not_opportunity_score() -> None:
    """06 §4: M&A signal requires its own evidence; never inferred solely from
    a stock opportunity score."""
    with pytest.raises(ValidationError, match="ma_target_signal_requires_own_evidence"):
        RoleClassification(role="MA_TARGET_SIGNAL", company_id="co-1",
                           opportunity_score_ref="score-9", rationale="high score",
                           assigned_at_utc=T1)
    ok = RoleClassification(role="MA_TARGET_SIGNAL", company_id="co-1",
                            supporting_evidence_ids=("ev-ma-1", "ev-ma-2"),
                            rationale="disclosure-based signal", assigned_at_utc=T1)
    assert ok.supporting_evidence_ids == ("ev-ma-1", "ev-ma-2")
    # The other two roles are representable without M&A-grade evidence:
    assert RoleClassification(role="WATCHLIST_COMPANY", company_id="co-1",
                              rationale="user list", assigned_at_utc=T1)


def test_dossier_company_consistency_and_explicit_limitations() -> None:
    with pytest.raises(ValidationError, match="fact_company_mismatch"):
        _dossier(facts=(_fact(company_id="co-2"),))
    with pytest.raises(ValidationError, match="role_company_mismatch"):
        _dossier(roles=(RoleClassification(role="WATCHLIST_COMPANY", company_id="co-2",
                                          rationale="x", assigned_at_utc=T1),))
    with pytest.raises(ValidationError, match="identity_company_mismatch"):
        _dossier(identity=_identity(company_id="co-2"))
    with pytest.raises(ValidationError, match="limitations"):
        _dossier(limitations=())
    with pytest.raises(ValidationError, match="duplicate_fact_ids"):
        _dossier(facts=(_fact(), _fact()))


def test_dossier_pit_cutoff_excludes_later_published_facts() -> None:
    """02:142: the dossier carries its information cutoff and historical
    analysis cannot use later-published filings."""
    late_fact = _fact(fact_id="fact-late", period=_filing(filing_id="f-late",
                                                          publication_time_utc=T_LATE))
    dossier = _dossier(facts=(_fact(), late_fact))
    eligible = dossier.facts_at_cutoff()
    assert tuple(f.fact_id for f in eligible) == ("fact-1",)
    before_any_publication = _dossier(information_cutoff_utc=datetime(2025, 12, 30,
                                                                     tzinfo=timezone.utc))
    assert before_any_publication.facts_at_cutoff() == ()


def test_dossier_pit_cutoff_includes_unknown_publication_retrieved_early() -> None:
    unk = _fact(fact_id="fact-unk", period=_filing(filing_id="f-unk",
                                                   publication_status="UNAVAILABLE",
                                                   publication_time_utc=None,
                                                   retrieval_time_utc=T1))
    dossier = _dossier(facts=(unk,))
    assert tuple(f.fact_id for f in dossier.facts_at_cutoff()) == ("fact-unk",)


# ---------------------------------------------------------------------------
# D6 — product audit charter, telemetry boundary, advisory proposals
# ---------------------------------------------------------------------------


def test_backtest_evaluators_apply_only_to_financial_hypotheses() -> None:
    """06 §8 / 02-arch additive: backtest is not a universal test."""
    assert evaluator_allowed_for_domain("FILTERS_STRATEGIES", "BACKTEST") is True
    assert evaluator_allowed_for_domain("SOFTWARE_QUALITY", "BACKTEST") is False
    assert evaluator_allowed_for_domain("PRODUCT_UX", "BACKTEST") is False
    assert evaluator_allowed_for_domain("SOFTWARE_QUALITY", "REGRESSION") is True
    assert evaluator_allowed_for_domain("PRODUCT_UX", "UX_REVIEW") is True


def test_proposal_rejects_domain_mismatched_evaluator() -> None:
    with pytest.raises(ValidationError, match="evaluator_not_allowed_for_domain"):
        ImprovementProposal(
            proposal_id="pr-1", domain="PRODUCT_UX", evaluator_kind="BACKTEST",
            expected_benefit="fewer errors", evidence_ids=("ev-1",),
            uncertainty="medium", cost="low", rollback_plan="revert",
            evaluation_design="usability study",
        )


def test_proposal_is_structurally_advisory_and_cannot_represent_production_change() -> None:
    """02:179 / D-AI-35: proposals must not mutate production — the contract
    cannot even represent it."""
    proposal = ImprovementProposal(
        proposal_id="pr-1", domain="FILTERS_STRATEGIES", evaluator_kind="BACKTEST",
        baseline={"hit_rate": 0.55}, expected_benefit="+2pp", evidence_ids=("ev-1",),
        uncertainty="medium", cost="low", risks=("false positives",),
        rollback_plan="revert filter version", evaluation_design="WFO + forward",
    )
    assert proposal.advisory_only is True
    states = get_args(ProposalApprovalState)
    assert states == ("PROPOSED", "UNDER_REVIEW", "APPROVED_FOR_EVALUATION",
                      "EVALUATED", "REJECTED")
    assert not any(w in s for s in states for w in ("APPLIED", "DEPLOY", "PROMOT"))
    with pytest.raises(ValidationError):
        ImprovementProposal(
            proposal_id="pr-2", domain="FILTERS_STRATEGIES", evaluator_kind="BACKTEST",
            expected_benefit="x", evidence_ids=("ev-1",), uncertainty="x", cost="x",
            rollback_plan="x", evaluation_design="x", advisory_only=False,  # type: ignore[arg-type]
        )


def test_telemetry_boundary_is_privacy_locked() -> None:
    """D-AI-39: minimum-necessary, aggregation-only, no sensitive repurposing;
    retention/access/deletion rules documented."""
    boundary = PrivacyTelemetryBoundary(
        data_classes=("task_completion_counts", "error_path_counts"),
        lawful_basis="aggregate product-quality analytics",
        access_control="role-restricted dashboard", retention_rule="90 days",
        deletion_rule="purge after retention",
    )
    assert boundary.aggregation_only is True
    assert boundary.sensitive_content_repurposing is False
    with pytest.raises(ValidationError):
        PrivacyTelemetryBoundary(
            data_classes=("x",), lawful_basis="x", access_control="a",
            retention_rule="r", deletion_rule="d",
            sensitive_content_repurposing=True,  # type: ignore[arg-type]
        )


def test_audit_charter_cadence_and_domain_rules() -> None:
    boundary = PrivacyTelemetryBoundary(
        data_classes=("aggregate",), lawful_basis="quality analytics",
        access_control="restricted", retention_rule="90d", deletion_rule="purge",
    )
    with pytest.raises(ValidationError, match="owner_configured_cadence_requires_expression"):
        AuditCadence(domain="PRODUCT_UX", mode="OWNER_CONFIGURED")
    cadence = AuditCadence(domain="PRODUCT_UX", mode="MONTHLY",
                           cadence_expression="owner-set")
    with pytest.raises(ValidationError, match="duplicate_cadence_domains"):
        ProductAuditCharter(
            charter_version="1", domains=("PRODUCT_UX",),
            cadences=(cadence, cadence.model_copy()), telemetry_boundary=boundary,
            baseline_metrics_ref="metrics-ref",
        )
    with pytest.raises(ValidationError, match="cadence_domain_not_in_charter"):
        ProductAuditCharter(
            charter_version="1", domains=("SOFTWARE_QUALITY",), cadences=(cadence,),
            telemetry_boundary=boundary, baseline_metrics_ref="metrics-ref",
        )
    charter = ProductAuditCharter(
        charter_version="1", domains=("PRODUCT_UX", "SOFTWARE_QUALITY"),
        cadences=(cadence,), telemetry_boundary=boundary,
        baseline_metrics_ref="metrics-ref",
    )
    assert "PRODUCT_UX" in charter.domains


# ---------------------------------------------------------------------------
# D7 — prediction preregistration, outcome maturity, anti-look-ahead
# ---------------------------------------------------------------------------


def _prediction(**over) -> PredictionRecord:
    base = dict(
        prediction_id="p-1", subject="symbol-فملی", registered_at_utc=T1,
        outcome_horizon_end_utc=datetime(2026, 7, 1, tzinfo=timezone.utc),
        evaluation_metric="directional_hit", event_maturity_rule="horizon-end",
        invalidation_rule="regime-flip", evidence_ids=("ev-p-1",), creator="research",
    )
    base.update(over)
    return PredictionRecord(**base)


def test_prediction_horizon_must_end_after_registration() -> None:
    with pytest.raises(ValidationError, match="horizon_must_end_after_registration"):
        _prediction(outcome_horizon_end_utc=T1 - timedelta(minutes=1))


def test_prediction_record_is_immutable_after_registration() -> None:
    """06 §7: never change the original prediction record."""
    record = _prediction()
    with pytest.raises(ValidationError):
        record.evaluation_metric = "mutated"  # type: ignore[misc]


def test_prediction_registry_is_append_only_and_versioned() -> None:
    reg = PredictionRegistry()
    reg2 = reg.register_prediction(_prediction())
    assert reg2.registry_version == 2 and len(reg2.predictions) == 1
    assert reg.registry_version == 1 and reg.predictions == ()  # original untouched
    with pytest.raises(ValueError, match="duplicate_prediction_id"):
        reg2.register_prediction(_prediction())


def test_outcome_predating_registration_is_rejected_label_leakage() -> None:
    """D-AI-37 / 02:139 — prevent look-ahead and label leakage."""
    reg = PredictionRegistry().register_prediction(_prediction())
    with pytest.raises(ValueError, match="outcome_predates_prediction_registration"):
        reg.attach_outcome(OutcomeRecord(
            outcome_id="o-1", prediction_id="p-1",
            observed_at_utc=T1 - timedelta(minutes=1),
            source_evidence_ids=("ev-o-1",),
        ))


def test_outcome_recorded_once_and_maturity_is_deterministic() -> None:
    reg = PredictionRegistry().register_prediction(_prediction())
    outcome = OutcomeRecord(outcome_id="o-1", prediction_id="p-1", observed_at_utc=T_LATE,
                            observed_numeric=0.0, source_evidence_ids=("ev-o-1",))
    reg2 = reg.attach_outcome(outcome)
    with pytest.raises(ValueError, match="prediction_already_has_outcome"):
        reg2.attach_outcome(OutcomeRecord(outcome_id="o-2", prediction_id="p-1",
                                          observed_at_utc=T_LATE,
                                          source_evidence_ids=("ev-o-1",)))
    assert maturity_state(_prediction(), T_LATE) == "MATURED"
    assert maturity_state(_prediction(), T1) == "PENDING"


def test_evaluation_before_maturity_is_refused() -> None:
    """02:139 — evaluation requires a matured outcome; no label leakage."""
    reg = PredictionRegistry().register_prediction(_prediction()).attach_outcome(
        OutcomeRecord(outcome_id="o-1", prediction_id="p-1", observed_at_utc=T_LATE,
                      source_evidence_ids=("ev-o-1",))
    )
    with pytest.raises(ValueError, match="prediction_not_matured"):
        reg.evaluate("p-1", as_of=T1, matched_expectation=False)


def test_evaluation_requires_recorded_outcome() -> None:
    reg = PredictionRegistry().register_prediction(_prediction())
    with pytest.raises(ValueError, match="outcome_not_recorded"):
        reg.evaluate("p-1", as_of=T_LATE, matched_expectation=True)
    with pytest.raises(ValueError, match="unknown_prediction_id"):
        reg.evaluate("p-unknown", as_of=T_LATE, matched_expectation=True)


def test_matured_evaluation_produces_advisory_feedback() -> None:
    """D-AI-37: error/calibration/drift → research proposal, advisory only."""
    reg = (PredictionRegistry().register_prediction(_prediction()).attach_outcome(
        OutcomeRecord(outcome_id="o-1", prediction_id="p-1", observed_at_utc=T_LATE,
                      source_evidence_ids=("ev-o-1",))))
    evaluation = reg.evaluate(
        "p-1", as_of=T_LATE, matched_expectation=False,
        error_category="direction-miss", calibration_note="overconfident",
        research_proposal_ref="prop-77",
    )
    assert isinstance(evaluation, PredictionEvaluation)
    assert evaluation.research_proposal_ref == "prop-77"
    assert evaluation.evaluated_at_utc == T_LATE  # deterministic: caller-provided time
