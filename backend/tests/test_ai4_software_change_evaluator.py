"""WS-5 AI-4 coverage extension tests — reference evaluator for
SOFTWARE_CHANGE_PROPOSAL structural completeness (2026-11-02).

Authorized repo-side item (W2-AIF authorized list, item 3: "AI-4
reference-evaluator coverage extension — more kinds with deterministic
evaluators (honest gaps currently recorded in the edge-composition test);
additive"). The registry's docstring honestly recorded SOFTWARE_CHANGE_
PROPOSAL as a kind with NO reference evaluator; this wave adds the callable
deterministic evaluator ``evaluate_software_change_proposal``.

Deliberate scope decisions (each pinned by a test below):
- The evaluator measures STRUCTURAL completeness of the eight mandatory
  proposal fields (02:179) — it never judges semantic quality (no invented
  thresholds, no placeholder scoring) and never executes anything.
- The canonical ``reference_evaluator_registry()`` is NOT extended: existing
  tests (``test_evaluators_reference.py``) pin the three-binding registry
  shape and the honest ``None`` resolution for this kind, and the
  additive-only discipline forbids amending existing tests in this wave.
  The tests below pin BOTH facts — the evaluator is real and bindable, and
  the canonical registry stays byte-stable — so a future registry revision
  can flip the binding as a single deliberate act.
- Refusal split: a wrong-kind input is a caller contract error and RAISES
  (mirroring ``evaluate_pass_rate``'s input refusals); a candidate with
  ``proposal=None`` reaching the evaluator is a malformed candidate and is
  surfaced as an honest refusal RECORD (mirroring
  ``evaluate_filter_dsl``'s refusal discipline), never scored.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.governed_generation import (
    GeneratedCandidate,
    SoftwareChangeProposalFields,
)
from app.engines.evaluators_reference import (
    REFERENCE_SOFTWARE_CHANGE_EVALUATOR_ID,
    SoftwareChangeEvaluation,
    evaluate_software_change_proposal,
    reference_evaluator_registry,
)

T0 = datetime(2026, 11, 2, 9, 0, 0, tzinfo=timezone.utc)

_PROPOSAL_KWARGS = dict(
    baseline="baseline-v1",
    expected_benefit="fewer false positives",
    evidence_summary="synthetic backtest evidence",
    uncertainty="unquantified until forward test",
    cost="one evaluation run",
    risks="regime dependence",
    rollback_plan="revert to baseline-v1 spec",
    evaluation_design="WFO on synthetic corpus",
)


def _candidate(
    kind: str = "SOFTWARE_CHANGE_PROPOSAL",
    candidate_id: str = "CAND_SCP_1",
    with_proposal: bool = True,
) -> GeneratedCandidate:
    proposal = None
    if kind == "SOFTWARE_CHANGE_PROPOSAL" and with_proposal:
        proposal = SoftwareChangeProposalFields(**_PROPOSAL_KWARGS)
    return GeneratedCandidate(
        candidate_id=candidate_id,
        kind=kind,  # type: ignore[arg-type]
        specification="spec text",
        spec_version="0.1.0",
        rationale="hypothesis H-1 rationale",
        run_id="RUN_AI4_WS5",
        hypothesis_id=None,
        created_at_utc=T0,
        proposal=proposal,
    )


def test_complete_proposal_accepted_with_exact_metrics() -> None:
    outcome = evaluate_software_change_proposal(_candidate())
    assert isinstance(outcome, SoftwareChangeEvaluation)
    assert outcome.accepted is True
    assert outcome.refusal_code is None and outcome.refusal_detail is None
    assert outcome.candidate_id == "CAND_SCP_1"
    values = {m.name: m.value for m in outcome.metrics}
    assert values["mandatory_fields_present"] == 8.0
    assert values["mandatory_fields_total"] == 8.0
    assert values["completeness_ratio"] == 1.0  # exact rational 8/8
    assert values["rollback_plan_present"] == 1.0
    assert values["evaluation_design_present"] == 1.0


def test_record_is_frozen_and_deterministic() -> None:
    first = evaluate_software_change_proposal(_candidate())
    second = evaluate_software_change_proposal(_candidate())
    assert first == second
    assert repr(first) == repr(second)
    with pytest.raises(Exception):
        first.accepted = False  # type: ignore[misc]


def test_wrong_kind_is_caller_error_raised() -> None:
    for kind in ("FILTER", "INDICATOR", "STRATEGY_SPEC", "SCORING_RULE",
                 "FUNDAMENTAL_FEATURE"):
        with pytest.raises(ValueError) as excinfo:
            evaluate_software_change_proposal(_candidate(kind=kind))
        assert "kind_must_be_software_change_proposal" in str(excinfo.value)


def test_proposal_none_is_honest_refusal_record_not_scored() -> None:
    # Only reachable through a validation-bypassing constructor: the
    # GeneratedCandidate model_validator refuses kind=SCP + proposal=None.
    bypassed = GeneratedCandidate.model_construct(
        candidate_id="CAND_SCP_BYPASS",
        kind="SOFTWARE_CHANGE_PROPOSAL",
        specification="spec text",
        spec_version="0.1.0",
        rationale="rationale",
        run_id="RUN_AI4_WS5",
        hypothesis_id=None,
        created_at_utc=T0,
        proposal=None,
        notes="",
    )
    outcome = evaluate_software_change_proposal(bypassed)
    assert outcome.accepted is False
    assert outcome.refusal_code == "proposal_fields_required"
    assert outcome.refusal_detail is not None and "no proposal fields" in outcome.refusal_detail
    assert outcome.metrics == ()


def test_whitespace_only_fields_are_not_present() -> None:
    # Defense-in-depth against validation bypass: model_construct skips
    # min_length, so whitespace-only values must be honestly counted absent.
    fields = SoftwareChangeProposalFields(**_PROPOSAL_KWARGS)
    bypassed_fields = SoftwareChangeProposalFields.model_construct(**{
        **_PROPOSAL_KWARGS,
        "rollback_plan": "   ",
    })
    assert bypassed_fields.rollback_plan == "   "
    bypassed = GeneratedCandidate.model_construct(
        candidate_id="CAND_SCP_WS",
        kind="SOFTWARE_CHANGE_PROPOSAL",
        specification="spec text",
        spec_version="0.1.0",
        rationale="rationale",
        run_id="RUN_AI4_WS5",
        hypothesis_id=None,
        created_at_utc=T0,
        proposal=bypassed_fields,
        notes="",
    )
    outcome = evaluate_software_change_proposal(bypassed)
    assert outcome.accepted is False
    assert outcome.refusal_code == "mandatory_fields_incomplete"
    assert outcome.refusal_detail == "completed 7/8 mandatory proposal fields"
    values = {m.name: m.value for m in outcome.metrics}
    assert values["mandatory_fields_present"] == 7.0
    assert values["completeness_ratio"] == 7.0 / 8.0
    assert values["rollback_plan_present"] == 0.0
    # The validated path never produces this state:
    assert fields.rollback_plan.strip() != ""


def test_canonical_registry_stays_three_bound_and_honest_about_gaps() -> None:
    registry = reference_evaluator_registry()
    ids = [b.evaluator_id for b in registry.bindings]
    assert ids == [
        "reference.filter_dsl",
        "reference.signal_pairs",
        "reference.pass_rate",
    ]
    # Honest gap pins preserved exactly as recorded before this wave.
    assert registry.resolve("SOFTWARE_CHANGE_PROPOSAL") is None
    assert registry.resolve("FUNDAMENTAL_FEATURE") is None


def test_evaluator_constant_is_registry_bindable() -> None:
    # The unbound reference evaluator carries a canonical id a future
    # registry revision can bind without renaming anything.
    assert REFERENCE_SOFTWARE_CHANGE_EVALUATOR_ID == "reference.software_change_proposal"
    from app.engines import evaluators_reference

    assert callable(evaluators_reference.evaluate_software_change_proposal)
