"""AI-4 Governed Generation acceptance tests (corpus-derived).

Sources: 02:87-90 (sandbox -> deterministic evaluation -> lifecycle ->
approval), 02:158-159 (candidates remain candidates until isolated tests,
evaluation gates and required human approval; no self-modifying production
logic), D-AI-10/11/12/13, D-AI-19, 03:19-25/40/78-83/90-94, 00:85-86,
02:170 (proposal fields), 06:107 (preregistration/holdout), 02:202
(synthetic/paper pre-G2 class). Contract-level synthetic tests only — no
sandbox runtime, no real data, no LLM (02:202; G2 NOT_PASSED).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.governed_generation import (
    ALLOWED_TRANSITIONS,
    CandidateApprovalRecord,
    CandidateEvaluationRecord,
    DeterministicEvaluatorBinding,
    EvaluatorRegistry,
    EvaluationMetric,
    GeneratedCandidate,
    SandboxAdmissionRecord,
    SandboxBudgetSpec,
    SandboxBudgetUsage,
    SoftwareChangeProposalFields,
    approval_entry_gate,
    approval_gate,
    evaluation_gate,
    generation_admission_verdict,
    governed_candidate_acceptance,
    sandbox_admission_gate,
    sandbox_budget_verdict,
    transition_candidate,
)
from app.domain.run_governance import RunContext, RunProvenance

T0 = datetime(2026, 10, 18, 10, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 10, 18, 10, 5, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 10, 18, 10, 10, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 10, 18, 10, 15, 0, tzinfo=timezone.utc)


def make_context(run_id: str = "RUN_AI4_1", autonomy_level: str = "L2") -> RunContext:
    return RunContext(
        run_id=run_id,
        run_kind="AI4_GENERATION",
        autonomy_level=autonomy_level,  # type: ignore[arg-type]
        policy_version="pol-v1",
        created_at_utc=T0,
    )


def make_provenance(
    run_id: str = "RUN_AI4_1", dataset_version: str | None = "synthetic-ds-1"
) -> RunProvenance:
    return RunProvenance(
        run_id=run_id,
        policy_version="pol-v1",
        started_at_utc=T0,
        finished_at_utc=T1,
        dataset_version=dataset_version,
    )


def make_candidate(
    kind: str = "FILTER",
    run_id: str = "RUN_AI4_1",
    with_proposal: bool = True,
) -> GeneratedCandidate:
    proposal = None
    if kind == "SOFTWARE_CHANGE_PROPOSAL" and with_proposal:
        proposal = SoftwareChangeProposalFields(
            baseline="baseline-v1",
            expected_benefit="fewer false positives",
            evidence_summary="synthetic backtest evidence",
            uncertainty="unquantified until forward test",
            cost="one evaluation run",
            risks="regime dependence",
            rollback_plan="revert to baseline-v1 spec",
            evaluation_design="WFO on synthetic corpus",
        )
    return GeneratedCandidate(
        candidate_id="CAND_1",
        kind=kind,  # type: ignore[arg-type]
        specification="close > sma(close, 20)",
        spec_version="0.1.0",
        rationale="hypothesis H-1: momentum persistence on synthetic corpus",
        run_id=run_id,
        hypothesis_id="HYP-1",
        created_at_utc=T0,
        proposal=proposal,
    )


def make_binding(
    evaluator_id: str = "EVAL_FILTER_DSL",
    kinds: tuple[str, ...] = ("FILTER",),
    origins: tuple[str, ...] = ("SYNTHETIC", "PAPER"),
) -> DeterministicEvaluatorBinding:
    return DeterministicEvaluatorBinding(
        evaluator_id=evaluator_id,
        evaluator_version="1.0.0",
        evaluates_kinds=kinds,  # type: ignore[arg-type]
        accepted_dataset_origins=origins,  # type: ignore[arg-type]
        evaluation_contract="app.engines.filter_dsl.validate_filter",
    )


def make_registry(*bindings: DeterministicEvaluatorBinding) -> EvaluatorRegistry:
    return EvaluatorRegistry(bindings=tuple(bindings))


def make_admission(
    candidate: GeneratedCandidate,
    *,
    dataset_origin: str = "SYNTHETIC",
    dataset_version: str = "synthetic-ds-1",
) -> SandboxAdmissionRecord:
    return SandboxAdmissionRecord(
        admission_id="ADM_1",
        candidate_id=candidate.candidate_id,
        run_id=candidate.run_id,
        sandbox_id="SBX_1",
        isolation_declared=True,
        production_contact=False,
        dataset_origin=dataset_origin,  # type: ignore[arg-type]
        dataset_version=dataset_version,
        budget=SandboxBudgetSpec(max_evaluator_invocations=4, max_wall_seconds=600),
        policy_version="pol-v1",
        admitted_at_utc=T1,
    )


def make_evaluation(
    candidate: GeneratedCandidate,
    admission: SandboxAdmissionRecord,
    binding: DeterministicEvaluatorBinding,
    *,
    verdict: str = "PASS",
    dataset_origin: str | None = None,
    dataset_version: str | None = None,
    preregistered: bool = True,
    holdout_protected: bool = True,
) -> CandidateEvaluationRecord:
    return CandidateEvaluationRecord(
        evaluation_id="EVAL_REC_1",
        candidate_id=candidate.candidate_id,
        run_id=admission.run_id,
        admission_id=admission.admission_id,
        evaluator_id=binding.evaluator_id,
        evaluator_version=binding.evaluator_version,
        dataset_origin=(dataset_origin or admission.dataset_origin),  # type: ignore[arg-type]
        dataset_version=(dataset_version or admission.dataset_version),
        metrics=(EvaluationMetric(name="node_count", value=7.0),),
        verdict=verdict,  # type: ignore[arg-type]
        preregistered=preregistered,
        holdout_protected=holdout_protected,
        artifact_refs=("art-eval-1",),
        recorded_at_utc=T2,
    )


def make_approval(
    candidate: GeneratedCandidate, decision: str = "APPROVED"
) -> CandidateApprovalRecord:
    return CandidateApprovalRecord(
        approval_id="APR_1",
        candidate_id=candidate.candidate_id,
        decision=decision,  # type: ignore[arg-type]
        decided_by="owner",
        approval_ref="DEC-2026-10-18-01",
        decided_at_utc=T3,
    )


# ---------------------------------------------------------------------------
# Positive lifecycle: sandbox -> deterministic evaluation -> lifecycle ->
# approval (02:88-90)
# ---------------------------------------------------------------------------


def test_full_lifecycle_end_to_end_acceptance() -> None:
    ctx = make_context()
    prov = make_provenance()
    candidate = make_candidate()
    registry = make_registry(make_binding())
    binding = registry.resolve("FILTER")
    assert binding is not None
    admission = make_admission(candidate)
    evaluation = make_evaluation(candidate, admission, binding)
    approval = make_approval(candidate)

    assert transition_candidate("DRAFT", "SANDBOX_ADMITTED") == ()
    assert sandbox_admission_gate(
        candidate, admission, ctx, prov, autonomy_ceiling="L2", evaluator_registry=registry
    ) == ()
    assert transition_candidate("SANDBOX_ADMITTED", "EVALUATED") == ()
    assert evaluation_gate(evaluation, candidate, binding, admission) == ()
    assert approval_entry_gate(evaluation) == ()
    assert transition_candidate("EVALUATED", "APPROVAL_PENDING") == ()
    assert approval_gate(approval, candidate, "APPROVAL_PENDING") == ()
    assert transition_candidate("APPROVAL_PENDING", "APPROVED") == ()
    assert (
        governed_candidate_acceptance(
            ctx,
            prov,
            candidate,
            registry=registry,
            autonomy_ceiling="L2",
            admission=admission,
            binding=binding,
            evaluation=evaluation,
            approval=approval,
        )
        == ()
    )


def test_hypothesis_entry_allowed_when_suitable_evaluator_exists() -> None:
    # 02:158: hypotheses may enter the governed research lifecycle when a
    # suitable deterministic evaluator exists.
    candidate = make_candidate()
    registry = make_registry(make_binding())
    assert generation_admission_verdict(candidate, registry) == ()


def test_registry_resolution_is_deterministic_and_additive() -> None:
    first = make_binding(evaluator_id="EVAL_A", kinds=("FILTER", "INDICATOR"))
    second = make_binding(evaluator_id="EVAL_B", kinds=("FILTER",))
    registry = make_registry(first)
    assert registry.resolve("FILTER") is first
    grown = registry.with_binding(second)
    assert grown.resolve("FILTER") is first  # registration order, first match
    assert grown.resolve("INDICATOR") is first
    assert grown.registry_version == registry.registry_version + 1
    assert grown.get("EVAL_B") is second


def test_software_change_proposal_with_full_fields_is_admissible() -> None:
    # 02:170: proposals carry baseline/expected benefit/evidence/uncertainty/
    # cost/risks/rollback plan/evaluation design.
    candidate = make_candidate(kind="SOFTWARE_CHANGE_PROPOSAL")
    binding = make_binding(kinds=("SOFTWARE_CHANGE_PROPOSAL",))
    registry = make_registry(binding)
    admission = make_admission(candidate)
    ctx = make_context()
    prov = make_provenance()
    assert sandbox_admission_gate(
        candidate, admission, ctx, prov, autonomy_ceiling="L2", evaluator_registry=registry
    ) == ()


def test_gates_are_deterministic_same_inputs_same_outputs() -> None:
    ctx = make_context()
    prov = make_provenance()
    candidate = make_candidate()
    registry = make_registry(make_binding())
    binding = registry.resolve("FILTER")
    assert binding is not None
    admission = make_admission(candidate)
    evaluation = make_evaluation(candidate, admission, binding)
    first = (
        sandbox_admission_gate(
            candidate,
            admission,
            ctx,
            prov,
            autonomy_ceiling="L2",
            evaluator_registry=registry,
        ),
        evaluation_gate(evaluation, candidate, binding, admission),
        approval_entry_gate(evaluation),
        transition_candidate("DRAFT", "SANDBOX_ADMITTED"),
    )
    second = (
        sandbox_admission_gate(
            candidate,
            admission,
            ctx,
            prov,
            autonomy_ceiling="L2",
            evaluator_registry=registry,
        ),
        evaluation_gate(evaluation, candidate, binding, admission),
        approval_entry_gate(evaluation),
        transition_candidate("DRAFT", "SANDBOX_ADMITTED"),
    )
    assert first == second


def test_records_are_frozen() -> None:
    candidate = make_candidate()
    with pytest.raises(ValidationError):
        candidate.specification = "mutated"  # type: ignore[misc]


def test_sandbox_budget_verdict_within_and_exhausted() -> None:
    spec = SandboxBudgetSpec(max_evaluator_invocations=2, max_wall_seconds=100)
    assert (
        sandbox_budget_verdict(spec, SandboxBudgetUsage(evaluator_invocations=1, wall_seconds=50.0))
        == "WITHIN_BUDGET"
    )
    assert (
        sandbox_budget_verdict(spec, SandboxBudgetUsage(evaluator_invocations=2, wall_seconds=10.0))
        == "BUDGET_EXHAUSTED"
    )
    # Ceiling-inclusive refusal (same discipline as AI2 budget_verdict).
    assert (
        sandbox_budget_verdict(spec, SandboxBudgetUsage(evaluator_invocations=0, wall_seconds=100.0))
        == "BUDGET_EXHAUSTED"
    )


# ---------------------------------------------------------------------------
# Structural no-production-mutation guarantees (D-AI-03/05/12/13; 03:19-25;
# 00:85; 02:170)
# ---------------------------------------------------------------------------


def test_no_production_state_exists_in_lifecycle() -> None:
    forbidden = {"PRODUCTION", "APPLIED", "DEPLOYED", "ACTIVE", "PROMOTED", "LIVE"}
    states = set(ALLOWED_TRANSITIONS)
    assert states == {
        "DRAFT",
        "SANDBOX_ADMITTED",
        "EVALUATED",
        "APPROVAL_PENDING",
        "APPROVED",
        "REJECTED",
    }
    assert not states & forbidden
    for source, targets in ALLOWED_TRANSITIONS.items():
        assert targets <= states, f"transition target outside vocabulary from {source}"
        assert not targets & forbidden


def test_lifecycle_vocabulary_is_closed_by_schema() -> None:
    with pytest.raises(ValidationError):
        make_candidate(kind="PROMOTE_TO_PRODUCTION")


def test_dataset_origin_live_is_unrepresentable() -> None:
    # 02:202 pre-G2 class: synthetic/paper only; G2 blocks real data (02:201).
    candidate = make_candidate()
    with pytest.raises(ValidationError):
        make_admission(candidate, dataset_origin="LIVE")  # type: ignore[arg-type]


def test_evaluator_service_class_stochastic_is_unrepresentable() -> None:
    # D-AI-19: evaluation remains deterministic; an LLM evaluator cannot be
    # expressed by the binding schema.
    with pytest.raises(ValidationError):
        DeterministicEvaluatorBinding(
            evaluator_id="EVAL_LLM",
            evaluator_version="1.0.0",
            service_class="STOCHASTIC",  # type: ignore[arg-type]
            evaluates_kinds=("FILTER",),
            accepted_dataset_origins=("SYNTHETIC",),
            evaluation_contract="some.model.call",
        )


def test_sandbox_isolation_undeclared_refused() -> None:
    candidate = make_candidate()
    with pytest.raises(ValidationError, match="sandbox_isolation_must_be_declared"):
        SandboxAdmissionRecord(
            admission_id="ADM_1",
            candidate_id=candidate.candidate_id,
            run_id=candidate.run_id,
            sandbox_id="SBX_1",
            isolation_declared=False,
            production_contact=False,
            dataset_origin="SYNTHETIC",
            dataset_version="synthetic-ds-1",
            budget=SandboxBudgetSpec(max_evaluator_invocations=4, max_wall_seconds=600),
            policy_version="pol-v1",
            admitted_at_utc=T1,
        )


def test_sandbox_production_contact_refused() -> None:
    candidate = make_candidate()
    with pytest.raises(ValidationError, match="sandbox_production_contact_forbidden"):
        SandboxAdmissionRecord(
            admission_id="ADM_1",
            candidate_id=candidate.candidate_id,
            run_id=candidate.run_id,
            sandbox_id="SBX_1",
            isolation_declared=True,
            production_contact=True,
            dataset_origin="SYNTHETIC",
            dataset_version="synthetic-ds-1",
            budget=SandboxBudgetSpec(max_evaluator_invocations=4, max_wall_seconds=600),
            policy_version="pol-v1",
            admitted_at_utc=T1,
        )


def test_software_change_proposal_requires_proposal_fields() -> None:
    with pytest.raises(
        ValidationError, match="software_change_proposal_requires_proposal_fields"
    ):
        make_candidate(kind="SOFTWARE_CHANGE_PROPOSAL", with_proposal=False)


def test_software_change_proposal_requires_rollback_plan() -> None:
    # 02:170: a proposal without a rollback plan cannot even be represented.
    with pytest.raises(ValidationError):
        SoftwareChangeProposalFields(
            baseline="b",
            expected_benefit="e",
            evidence_summary="ev",
            uncertainty="u",
            cost="c",
            risks="r",
            rollback_plan="",
            evaluation_design="d",
        )


def test_proposal_fields_forbidden_for_other_kinds() -> None:
    fields = SoftwareChangeProposalFields(
        baseline="b",
        expected_benefit="e",
        evidence_summary="ev",
        uncertainty="u",
        cost="c",
        risks="r",
        rollback_plan="rb",
        evaluation_design="d",
    )
    with pytest.raises(ValidationError, match="proposal_fields_only_for_software_change_proposals"):
        GeneratedCandidate(
            candidate_id="CAND_2",
            kind="FILTER",
            specification="close > open",
            spec_version="0.1.0",
            rationale="r",
            run_id="RUN_AI4_1",
            created_at_utc=T0,
            proposal=fields,
        )


def test_candidate_requires_nonempty_rationale() -> None:
    with pytest.raises(ValidationError):
        GeneratedCandidate(
            candidate_id="CAND_3",
            kind="FILTER",
            specification="close > open",
            spec_version="0.1.0",
            rationale="",
            run_id="RUN_AI4_1",
            created_at_utc=T0,
        )


def test_empty_specification_refused() -> None:
    with pytest.raises(ValidationError):
        GeneratedCandidate(
            candidate_id="CAND_4",
            kind="FILTER",
            specification="",
            spec_version="0.1.0",
            rationale="r",
            run_id="RUN_AI4_1",
            created_at_utc=T0,
        )


def test_approval_record_requires_human_identity_and_reference() -> None:
    # 03:90-94 approval record; same discipline as the RunContext L4 rule.
    with pytest.raises(ValidationError):
        CandidateApprovalRecord(
            approval_id="APR_2",
            candidate_id="CAND_1",
            decision="APPROVED",
            decided_by="",
            approval_ref="DEC-1",
            decided_at_utc=T3,
        )
    with pytest.raises(ValidationError):
        CandidateApprovalRecord(
            approval_id="APR_3",
            candidate_id="CAND_1",
            decision="APPROVED",
            decided_by="owner",
            approval_ref="",
            decided_at_utc=T3,
        )


def test_binding_rejects_duplicate_kinds_and_registry_rejects_duplicate_ids() -> None:
    with pytest.raises(ValidationError, match="binding_members_duplicates"):
        make_binding(kinds=("FILTER", "FILTER"))
    with pytest.raises(ValueError, match="evaluator_id_already_registered"):
        make_registry(make_binding(), make_binding())


def test_metric_names_and_artifact_refs_must_be_distinct() -> None:
    with pytest.raises(ValidationError, match="metric_names_duplicates"):
        CandidateEvaluationRecord(
            evaluation_id="EVAL_REC_2",
            candidate_id="CAND_1",
            run_id="RUN_AI4_1",
            admission_id="ADM_1",
            evaluator_id="EVAL_FILTER_DSL",
            evaluator_version="1.0.0",
            dataset_origin="SYNTHETIC",
            dataset_version="synthetic-ds-1",
            metrics=(
                EvaluationMetric(name="node_count", value=1.0),
                EvaluationMetric(name="node_count", value=2.0),
            ),
            verdict="PASS",
            recorded_at_utc=T2,
        )
    with pytest.raises(ValidationError, match="artifact_refs_duplicates"):
        CandidateEvaluationRecord(
            evaluation_id="EVAL_REC_3",
            candidate_id="CAND_1",
            run_id="RUN_AI4_1",
            admission_id="ADM_1",
            evaluator_id="EVAL_FILTER_DSL",
            evaluator_version="1.0.0",
            dataset_origin="SYNTHETIC",
            dataset_version="synthetic-ds-1",
            metrics=(),
            verdict="PASS",
            artifact_refs=("a", "a"),
            recorded_at_utc=T2,
        )


def test_non_finite_metric_value_refused() -> None:
    with pytest.raises(ValidationError, match="metric_value_must_be_finite"):
        EvaluationMetric(name="score", value=float("nan"))


# ---------------------------------------------------------------------------
# Gate refusal paths (explainable failure modes; 03:90-94 failure-path
# evidence)
# ---------------------------------------------------------------------------


def test_generation_entry_blocked_without_suitable_evaluator() -> None:
    # 02:158: entry requires a suitable deterministic evaluator.
    candidate = make_candidate(kind="INDICATOR")
    registry = make_registry(make_binding(kinds=("FILTER",)))
    assert generation_admission_verdict(candidate, registry) == (
        "no_suitable_deterministic_evaluator",
    )


def test_admission_blocked_on_candidate_mismatch() -> None:
    ctx = make_context()
    prov = make_provenance()
    candidate = make_candidate()
    other = make_candidate()
    admission = make_admission(other)
    admission = admission.model_copy(update={"candidate_id": "CAND_OTHER"})
    registry = make_registry(make_binding())
    assert sandbox_admission_gate(
        candidate, admission, ctx, prov, autonomy_ceiling="L2", evaluator_registry=registry
    ) == ("admission_candidate_mismatch",)


def test_admission_blocked_on_run_id_mismatches() -> None:
    ctx = make_context(run_id="RUN_AI4_1")
    prov = make_provenance(run_id="RUN_AI4_1")
    candidate = make_candidate(run_id="RUN_OTHER")
    admission = make_admission(candidate)  # admission follows the candidate
    registry = make_registry(make_binding())
    # Deterministic multi-code refusal: admission-vs-context fires first,
    # then candidate-vs-context (fixed code order in the gate).
    assert sandbox_admission_gate(
        candidate, admission, ctx, prov, autonomy_ceiling="L2", evaluator_registry=registry
    ) == ("admission_run_id_mismatch", "candidate_run_id_mismatch")


def test_admission_blocked_on_incomplete_provenance() -> None:
    # 03:40: missing required provenance blocks governed acceptance.
    ctx = make_context()
    prov = make_provenance(dataset_version=None)
    candidate = make_candidate()
    registry = make_registry(make_binding())
    admission = make_admission(candidate)
    assert sandbox_admission_gate(
        candidate, admission, ctx, prov, autonomy_ceiling="L2", evaluator_registry=registry
    ) == ("provenance_incomplete",)


def test_admission_blocked_on_autonomy_over_ceiling() -> None:
    # 03:78-83: agents cannot silently increase autonomy.
    ctx = make_context(autonomy_level="L3")
    prov = make_provenance()
    candidate = make_candidate()
    registry = make_registry(make_binding())
    admission = make_admission(candidate)
    assert sandbox_admission_gate(
        candidate, admission, ctx, prov, autonomy_ceiling="L2", evaluator_registry=registry
    ) == ("autonomy_level_exceeds_declared_ceiling",)


def test_admission_blocked_without_evaluator_for_kind() -> None:
    ctx = make_context()
    prov = make_provenance()
    candidate = make_candidate(kind="SCORING_RULE")
    registry = make_registry(make_binding(kinds=("FILTER",)))
    admission = make_admission(candidate)
    assert sandbox_admission_gate(
        candidate, admission, ctx, prov, autonomy_ceiling="L2", evaluator_registry=registry
    ) == ("no_suitable_deterministic_evaluator",)


def test_evaluation_gate_refusal_codes() -> None:
    candidate = make_candidate()
    registry = make_registry(make_binding())
    binding = registry.resolve("FILTER")
    assert binding is not None
    admission = make_admission(candidate)

    wrong_evaluator = make_evaluation(
        candidate,
        admission,
        binding,
    ).model_copy(update={"evaluator_id": "EVAL_OTHER"})
    assert evaluation_gate(wrong_evaluator, candidate, binding, admission) == (
        "evaluator_binding_mismatch",
    )

    wrong_kind_binding = make_binding(kinds=("INDICATOR",))
    evaluation = make_evaluation(candidate, admission, binding)
    assert evaluation_gate(evaluation, candidate, wrong_kind_binding, admission) == (
        "evaluator_kind_mismatch",
    )

    paper_only_binding = make_binding(origins=("PAPER",))
    origin_rejected = make_evaluation(
        candidate, admission, paper_only_binding, dataset_origin="SYNTHETIC"
    )
    assert evaluation_gate(origin_rejected, candidate, paper_only_binding, admission) == (
        "dataset_origin_not_accepted_by_evaluator",
    )

    origin_mismatch = make_evaluation(
        candidate, admission, binding, dataset_origin="PAPER"
    )
    assert evaluation_gate(origin_mismatch, candidate, binding, admission) == (
        "dataset_origin_mismatch_with_admission",
    )

    version_mismatch = evaluation.model_copy(update={"evaluator_version": "9.9.9"})
    assert evaluation_gate(version_mismatch, candidate, binding, admission) == (
        "evaluator_version_mismatch",
    )


def test_evaluation_dataset_consistency_with_admission_enforced() -> None:
    candidate = make_candidate()
    binding = make_binding()
    admission = make_admission(candidate)
    wrong_version = make_evaluation(
        candidate, admission, binding, dataset_version="other-ds"
    )
    assert evaluation_gate(wrong_version, candidate, binding, admission) == (
        "dataset_version_mismatch_with_admission",
    )
    wrong_admission = make_evaluation(
        candidate, admission, binding
    ).model_copy(update={"admission_id": "ADM_OTHER"})
    assert evaluation_gate(wrong_admission, candidate, binding, admission) == (
        "evaluation_admission_mismatch",
    )


def test_evaluation_requires_preregistration_and_holdout_protection() -> None:
    # 06:107: preregistration and holdout protection are acceptance inputs.
    candidate = make_candidate()
    binding = make_binding()
    admission = make_admission(candidate)
    evaluation = make_evaluation(
        candidate, admission, binding, preregistered=False, holdout_protected=False
    )
    assert evaluation_gate(evaluation, candidate, binding, admission) == (
        "evaluation_not_preregistered",
        "holdout_protection_not_declared",
    )


def test_failed_evaluation_blocks_approval_entry() -> None:
    # 02:159: candidates remain candidates until evaluation gates are passed.
    candidate = make_candidate()
    binding = make_binding()
    admission = make_admission(candidate)
    failed = make_evaluation(candidate, admission, binding, verdict="FAIL")
    assert approval_entry_gate(failed) == ("evaluation_gate_not_passed",)
    passed = make_evaluation(candidate, admission, binding, verdict="PASS")
    assert approval_entry_gate(passed) == ()


def test_approval_requires_approval_pending_state() -> None:
    candidate = make_candidate()
    approval = make_approval(candidate)
    assert approval_gate(approval, candidate, "EVALUATED") == (
        "approval_requires_approval_pending_state",
    )
    assert approval_gate(approval, candidate, "APPROVAL_PENDING") == ()


def test_approval_candidate_mismatch_blocked() -> None:
    candidate = make_candidate()
    approval = make_approval(candidate).model_copy(update={"candidate_id": "CAND_OTHER"})
    assert approval_gate(approval, candidate, "APPROVAL_PENDING") == (
        "approval_candidate_mismatch",
    )


# ---------------------------------------------------------------------------
# Lifecycle transition policy (D-AI-10/D-AI-11)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("DRAFT", "EVALUATED"),
        ("DRAFT", "APPROVAL_PENDING"),
        ("SANDBOX_ADMITTED", "APPROVAL_PENDING"),
        ("EVALUATED", "APPROVED"),
        ("EVALUATED", "SANDBOX_ADMITTED"),
        ("APPROVAL_PENDING", "DRAFT"),
        ("APPROVED", "SANDBOX_ADMITTED"),
        ("APPROVED", "APPROVAL_PENDING"),
        ("REJECTED", "DRAFT"),
        ("REJECTED", "APPROVED"),
        ("DRAFT", "DRAFT"),
        ("APPROVED", "APPROVED"),
    ],
)
def test_illegal_transitions_refused(current: str, target: str) -> None:
    assert transition_candidate(current, target) == ("transition_not_permitted",)


def test_unknown_lifecycle_state_refused() -> None:
    assert transition_candidate("UNKNOWN", "DRAFT") == ("unknown_lifecycle_state",)
    assert transition_candidate("DRAFT", "PRODUCTION") == ("unknown_lifecycle_state",)


# ---------------------------------------------------------------------------
# End-to-end acceptance refusal paths (03:90-94)
# ---------------------------------------------------------------------------


def test_acceptance_rejects_rejected_human_decision() -> None:
    ctx = make_context()
    prov = make_provenance()
    candidate = make_candidate()
    registry = make_registry(make_binding())
    binding = registry.resolve("FILTER")
    assert binding is not None
    admission = make_admission(candidate)
    evaluation = make_evaluation(candidate, admission, binding)
    rejection = make_approval(candidate, decision="REJECTED")
    assert (
        governed_candidate_acceptance(
            ctx,
            prov,
            candidate,
            registry=registry,
            autonomy_ceiling="L2",
            admission=admission,
            binding=binding,
            evaluation=evaluation,
            approval=rejection,
        )
        == ("human_approval_rejected",)
    )


def test_acceptance_blocks_on_incomplete_provenance() -> None:
    ctx = make_context()
    prov = make_provenance(dataset_version=None)
    candidate = make_candidate()
    registry = make_registry(make_binding())
    binding = registry.resolve("FILTER")
    assert binding is not None
    admission = make_admission(candidate)
    evaluation = make_evaluation(candidate, admission, binding)
    approval = make_approval(candidate)
    assert (
        governed_candidate_acceptance(
            ctx,
            prov,
            candidate,
            registry=registry,
            autonomy_ceiling="L2",
            admission=admission,
            binding=binding,
            evaluation=evaluation,
            approval=approval,
        )
        == ("provenance_incomplete",)
    )


def test_acceptance_blocks_when_evaluation_failed() -> None:
    ctx = make_context()
    prov = make_provenance()
    candidate = make_candidate()
    registry = make_registry(make_binding())
    binding = registry.resolve("FILTER")
    assert binding is not None
    admission = make_admission(candidate)
    evaluation = make_evaluation(candidate, admission, binding, verdict="FAIL")
    approval = make_approval(candidate)
    assert (
        governed_candidate_acceptance(
            ctx,
            prov,
            candidate,
            registry=registry,
            autonomy_ceiling="L2",
            admission=admission,
            binding=binding,
            evaluation=evaluation,
            approval=approval,
        )
        == ("evaluation_gate_not_passed",)
    )


def test_acceptance_blocks_on_wrong_run_binding() -> None:
    # 02:196: governed actions carry traceable run identity; a candidate
    # generated under another run cannot be accepted under this one.
    ctx = make_context(run_id="RUN_AI4_1")
    prov = make_provenance(run_id="RUN_AI4_1")
    candidate = make_candidate(run_id="RUN_OTHER")
    registry = make_registry(make_binding())
    binding = registry.resolve("FILTER")
    assert binding is not None
    admission = make_admission(candidate)
    evaluation = make_evaluation(candidate, admission, binding)
    approval = make_approval(candidate)
    assert (
        governed_candidate_acceptance(
            ctx,
            prov,
            candidate,
            registry=registry,
            autonomy_ceiling="L2",
            admission=admission,
            binding=binding,
            evaluation=evaluation,
            approval=approval,
        )
        == ("admission_run_id_mismatch", "candidate_run_id_mismatch")
    )
