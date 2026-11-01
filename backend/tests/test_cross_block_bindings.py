"""Cross-block binding consistency pins (AI-4/AI-5/AI-6/AI-7).

Pins the field-level and vocabulary-level consistency points BETWEEN the
delivered block schemas so no future edit can silently fork them:

(a) ImprovementProposal (product_audit) <-> SoftwareChangeProposalFields
    (governed_generation): field-for-field compatibility where the corpus
    requires binding (02:179's eight mandatory proposal fields; text
    boundaries; approval-state vocabularies);
(b) kill-switch ENGAGED-default consistency across monitoring.py,
    proactive_research.py and product_audit.py — every default is
    fail-closed;
(c) calibration data_class closed set == the co-governing AI-7/AI-4
    closed set, and prediction.py carries NO conflicting data-class
    vocabulary (it exposes none — pinned honestly);
(d) document_registry trust labels are the external_intelligence
    TrustLabel vocabulary itself (no fork).

Synthetic contract tests only — no I/O, no network, no clock reads.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import get_args, get_type_hints

import pytest
from pydantic import ValidationError

from app.domain import prediction as prediction_module
from app.domain.calibration import DATA_CLASS as CALIBRATION_DATA_CLASS
from app.domain.external_intelligence import TrustLabel
from app.domain.document_registry import DocumentVersion
from app.domain.governed_generation import (
    CandidateApprovalDecision,
    CandidateLifecycleState,
    DatasetOrigin,
    SoftwareChangeProposalFields,
)
from app.domain.monitoring import (
    BudgetSpec,
    MonitoringJobSpec,
    MonitoringJobState,
    RetryPolicy,
    TriggerSpec,
    effective_run_permission,
)
from app.domain.product_audit import (
    AuditCadence,
    ImprovementProposal,
    ProposalApprovalState,
)
from app.domain.proactive_research import (
    ProactiveResearchJobSpec,
    ProactiveResearchJobState,
    effective_research_run_permission,
)
from app.domain.run_governance import ApprovalState, RunContext, RunProvenance

UTC = timezone.utc
T0 = datetime(2026, 10, 28, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# (a) ImprovementProposal <-> SoftwareChangeProposalFields
# ---------------------------------------------------------------------------


def _fields() -> SoftwareChangeProposalFields:
    return SoftwareChangeProposalFields(
        baseline="baseline-ref: golden-set-v1 hit_rate=0.61",
        expected_benefit="Raise filter precision by 3pp without recall loss.",
        evidence_summary="episodic evidence ev-1..ev-4 (synthetic run).",
        uncertainty="Wide: 40 synthetic runs only; no live data (pre-G2).",
        cost="2 engineering-days; no budget change.",
        risks="May overfit the synthetic regime; rollback trivial.",
        rollback_plan="Revert candidate; no production artifact touched.",
        evaluation_design="Isolated sandbox backtest vs golden-set baseline.",
    )


def _proposal_from_fields(fields: SoftwareChangeProposalFields) -> ImprovementProposal:
    """The corpus-required binding: the eight mandatory proposal fields of
    02:179 carry the SAME content on both schemas. The proposal-side
    `baseline` is the declared numeric view of the candidate-side
    reference string; `evidence_summary` is bound to evidence ids; the
    candidate-side `risks` string is the joined proposal-side risk list."""
    return ImprovementProposal(
        proposal_id="prop-binding-1",
        domain="SOFTWARE_QUALITY",
        evaluator_kind="REGRESSION",
        baseline={"hit_rate": 0.61},
        expected_benefit=fields.expected_benefit,
        evidence_ids=("ev-1",),
        uncertainty=fields.uncertainty,
        cost=fields.cost,
        risks=tuple(line for line in fields.risks.splitlines() if line),
        rollback_plan=fields.rollback_plan,
        evaluation_design=fields.evaluation_design,
    )


def test_shared_textual_fields_round_trip() -> None:
    fields = _fields()
    proposal = _proposal_from_fields(fields)
    # Field-for-field: the same non-empty text is accepted by BOTH schemas
    # and round-trips unchanged (02:179 eight-field binding).
    assert proposal.expected_benefit == fields.expected_benefit
    assert proposal.uncertainty == fields.uncertainty
    assert proposal.cost == fields.cost
    assert proposal.rollback_plan == fields.rollback_plan
    assert proposal.evaluation_design == fields.evaluation_design


def test_text_boundaries_agree_on_both_sides() -> None:
    # Empty proposal text is refused on BOTH sides (min_length=1 binding).
    base_fields: dict[str, str] = dict(
        baseline="b",
        expected_benefit="x",
        evidence_summary="e",
        uncertainty="u",
        cost="c",
        risks="r",
        rollback_plan="rb",
        evaluation_design="ed",
    )
    for field in ("expected_benefit", "rollback_plan", "evaluation_design"):
        bad = dict(base_fields)
        bad[field] = ""
        with pytest.raises(ValidationError):
            SoftwareChangeProposalFields(**bad)
        proposal_kwargs = {k: v for k, v in bad.items() if k != "baseline"}
        with pytest.raises(ValidationError):
            ImprovementProposal(
                proposal_id="p",
                domain="SOFTWARE_QUALITY",
                evaluator_kind="REGRESSION",
                baseline={"hit_rate": 0.6},
                evidence_ids=("ev-1",),
                **proposal_kwargs,  # type: ignore[arg-type]
            )


def test_risks_binding_via_multiline_text() -> None:
    fields = SoftwareChangeProposalFields(
        baseline="b",
        expected_benefit="x",
        evidence_summary="e",
        uncertainty="u",
        cost="c",
        risks="risk-one\nrisk-two",
        rollback_plan="rb",
        evaluation_design="ed",
    )
    proposal = _proposal_from_fields(fields)
    assert proposal.risks == ("risk-one", "risk-two")


def test_approval_state_vocabularies_bind_without_production_states() -> None:
    # No production-application state exists in EITHER vocabulary: the
    # product-audit machine ends at EVALUATED/REJECTED and the governed
    # candidate machine ends at APPROVED/REJECTED (02:179; D-AI-12/13).
    product_states = set(get_args(ProposalApprovalState))
    lifecycle_states = set(get_args(CandidateLifecycleState))
    production_states = {"APPLIED", "DEPLOYED", "PROMOTED", "PRODUCTION"}
    assert not product_states & production_states
    assert not lifecycle_states & production_states
    # The governed candidate's approval decisions are exactly the terminal
    # decision members of the canonical run-governance ApprovalState set.
    assert set(get_args(CandidateApprovalDecision)) == {"APPROVED", "REJECTED"}
    assert set(get_args(CandidateApprovalDecision)) <= set(get_args(ApprovalState))


# ---------------------------------------------------------------------------
# (b) Kill-switch ENGAGED-default consistency (fail-closed everywhere)
# ---------------------------------------------------------------------------


def test_kill_switch_defaults_engaged_across_blocks() -> None:
    assert MonitoringJobSpec.model_fields["kill_switch"].default == "ENGAGED"
    assert ProactiveResearchJobSpec.model_fields["kill_switch"].default == "ENGAGED"
    assert AuditCadence.model_fields["kill_switch"].default == "ENGAGED"


def _monitoring_spec(kill_switch: str = "ENGAGED") -> MonitoringJobSpec:
    return MonitoringJobSpec(
        job_id="m-1",
        target_source_ids=("src-1",),
        trigger=TriggerSpec(kind="SCHEDULED", schedule_expression="OWNER_CONFIGURED"),
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds_base=30),
        budget=BudgetSpec(max_runs_per_hour=4, max_timeout_seconds=600, max_concurrency=1),
        observability_ref="obs://m-1",
        alerting_ref="alerts://m-1",
        kill_switch=kill_switch,  # type: ignore[arg-type]
    )


def test_effective_permissions_fail_closed_with_defaults() -> None:
    # monitoring.py: default ENGAGED -> no run permission, even healthy.
    spec = _monitoring_spec()
    state = MonitoringJobState(job_id="m-1")
    assert spec.run_allowed() is False
    assert effective_run_permission(spec, state) is False
    # An explicitly RELEASED switch does NOT override a HALTED state
    # (recovery is an owner action, never an automatic retry).
    halted = MonitoringJobState(job_id="m-1", failure_state="HALTED", failure_alert_sent=True)
    assert effective_run_permission(_monitoring_spec("RELEASED"), halted) is False


def test_proactive_permission_fail_closed_with_defaults() -> None:
    spec = ProactiveResearchJobSpec(
        research_job_id="rj-1",
        trigger=TriggerSpec(kind="SCHEDULED", schedule_expression="OWNER_CONFIGURED"),
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds_base=30),
        budget=BudgetSpec(max_runs_per_hour=4, max_timeout_seconds=600, max_concurrency=1),
        research_questions=("Q1",),
        evidence_ref="research_memory://episodic",
        observability_ref="obs://rj-1",
        alerting_ref="alerts://rj-1",
    )
    state = ProactiveResearchJobState(research_job_id="rj-1")
    context = RunContext(
        run_id="run-1",
        run_kind="PROACTIVE_RESEARCH",
        policy_version="pv-1",
        created_at_utc=T0,
    )
    provenance = RunProvenance(
        run_id="run-1",
        policy_version="pv-1",
        started_at_utc=T0,
        finished_at_utc=T0 + timedelta(hours=1),
        dataset_version="synthetic-2026-10-28",
    )
    permitted, refusals = effective_research_run_permission(
        spec, state, context, provenance, autonomy_ceiling="L2"
    )
    assert permitted is False
    assert refusals[0] == "kill_switch_engaged"


# ---------------------------------------------------------------------------
# (c) data_class closed sets
# ---------------------------------------------------------------------------


def test_calibration_data_class_equals_governed_generation_origin_set() -> None:
    # Both AI-7/AI-4 blocks lock the pre-G2 data class to SYNTHETIC/PAPER
    # (02:202); the vocabularies must stay identical — LIVE is
    # unrepresentable in both.
    assert get_args(CALIBRATION_DATA_CLASS) == ("SYNTHETIC", "PAPER")
    assert get_args(CALIBRATION_DATA_CLASS) == get_args(DatasetOrigin)
    assert "LIVE" not in get_args(CALIBRATION_DATA_CLASS)


def test_prediction_module_exposes_no_conflicting_data_class_vocabulary() -> None:
    # prediction.py carries NO data_class field/vocabulary of its own (the
    # closed set "where both exist" therefore cannot fork: the only AI-7
    # data-class vocabularies are the identical pair pinned above).
    assert not hasattr(prediction_module, "DATA_CLASS")
    assert "data_class" not in prediction_module.PredictionRecord.model_fields


# ---------------------------------------------------------------------------
# (d) document_registry trust labels ⊆ external_intelligence TrustLabel
# ---------------------------------------------------------------------------


def test_document_trust_label_is_the_canonical_vocabulary() -> None:
    # document_registry re-imports the canonical AI-6 TrustLabel; the
    # annotation of DocumentVersion.trust_label is that exact vocabulary.
    assert get_args(DocumentVersion.model_fields["trust_label"].annotation) == get_args(
        TrustLabel
    )
    assert get_args(TrustLabel) == ("UNTRUSTED",)
    assert DocumentVersion.model_fields["trust_label"].default == "UNTRUSTED"
    with pytest.raises(ValidationError):
        DocumentVersion.model_validate(
            {
                "doc_key": "d",
                "version_index": 1,
                "sha256_hex": "0" * 64,
                "source_ref": "s",
                "published_at_utc": T0,
                "retrieved_at_utc": T0,
                "trust_label": "TRUSTED",
            }
        )
