"""AI2-F acceptance tests — AI-2 required-items governance contracts.

Derived from the 2026-10-02 amendment corpus, NOT from the implementation:
02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 44–53 require for AI-2:
immutable run identity · provenance · budget/time/iteration limits ·
evidence artifacts · duplicate detection · failure/recovery · invalidation ·
human approval state. Each test names its required item.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.ai2_governance import (
    AI2BudgetSpec,
    AI2EvidenceArtifact,
    AI2InvalidationRule,
    AI2RunLedger,
    AI2RunRecord,
    BudgetUsage,
    budget_verdict,
    classify_duplicate,
    governed_acceptance,
    invalidates,
    recovery_decision,
)
from app.domain.run_governance import RunContext

UTC = timezone.utc
T0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=UTC)
SHA1 = "a" * 64
SHA2 = "b" * 64
BUDGET = AI2BudgetSpec(max_provider_invocations=3, max_iterations=8, max_wall_seconds=1800)


def ctx(run_id: str = "run-ai2-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        run_kind="AI2_INTERPRETATION",
        policy_version="gov-1",
        created_at_utc=T0,
    )


def record(**over: object) -> AI2RunRecord:
    base = dict(
        record_id="r1",
        run_id="run-ai2-1",
        run_kind="AI2_INTERPRETATION",
        policy_version="gov-1",
        task="analyst",
        input_snapshot_sha256=SHA1,
        trust_state="live",
        approval_state="NOT_REQUIRED",
        status="LEDGERED",
        recorded_at_utc=T0,
    )
    base.update(over)
    return AI2RunRecord(**base)  # type: ignore[arg-type]


def artifact(**over: object) -> AI2EvidenceArtifact:
    from app.domain.run_governance import ArtifactRef

    base = dict(
        artifact=ArtifactRef(artifact_id="art-1", kind="ai2_result", ref="artifact://art-1"),
        run_id="run-ai2-1",
        input_snapshot_sha256=SHA1,
        data_trust_state="live",
        created_at_utc=T0,
    )
    base.update(over)
    return AI2EvidenceArtifact(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Item 1 — immutable run identity
# ---------------------------------------------------------------------------


def test_run_record_frozen_identity() -> None:
    r = record()
    with pytest.raises(ValidationError):
        r.run_id = "other"  # type: ignore[misc]


def test_run_record_rejects_unknown_task_and_bad_sha() -> None:
    with pytest.raises(ValidationError, match="unknown_ai2_task"):
        record(task="trading")
    with pytest.raises(ValidationError, match="input_snapshot_sha256_must_be_hex"):
        record(input_snapshot_sha256="NOTHEX" + "0" * 58)


def test_run_record_status_consistency() -> None:
    with pytest.raises(ValidationError, match="completed_run_requires_evidence_artifact"):
        record(status="COMPLETED")
    with pytest.raises(ValidationError, match="non_terminal_status_cannot_carry_artifact"):
        record(status="LEDGERED", artifact=artifact())


# ---------------------------------------------------------------------------
# Item 3 — budget/time/iteration limits
# ---------------------------------------------------------------------------


def test_budget_spec_structurally_bounded() -> None:
    with pytest.raises(ValidationError):
        AI2BudgetSpec(max_provider_invocations=0, max_iterations=1, max_wall_seconds=1)
    with pytest.raises(ValidationError):
        AI2BudgetSpec(max_provider_invocations=1, max_iterations=1, max_wall_seconds=999999)


@pytest.mark.parametrize(
    ("invocations", "iterations", "wall", "expected"),
    [
        (0, 0, 0.0, "WITHIN_BUDGET"),
        (2, 7, 1799.0, "WITHIN_BUDGET"),
        (3, 0, 0.0, "BUDGET_EXHAUSTED"),
        (0, 8, 0.0, "BUDGET_EXHAUSTED"),
        (0, 0, 1800.0, "BUDGET_EXHAUSTED"),
    ],
)
def test_budget_verdict_boundaries(
    invocations: int, iterations: int, wall: float, expected: str
) -> None:
    verdict = budget_verdict(
        BUDGET, BudgetUsage(provider_invocations=invocations, iterations=iterations, wall_seconds=wall)
    )
    assert verdict == expected


# ---------------------------------------------------------------------------
# Item 4 — evidence artifacts
# ---------------------------------------------------------------------------


def test_evidence_artifact_binding_and_freeze() -> None:
    a = artifact()
    assert a.run_id == "run-ai2-1" and a.input_snapshot_sha256 == SHA1
    with pytest.raises(ValidationError):
        a.data_trust_state = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        artifact(input_snapshot_sha256="zz" * 32)


def test_completed_record_carries_artifact() -> None:
    ok = record(status="COMPLETED", artifact=artifact(), approval_state="APPROVED", approved_by="owner")
    assert ok.status == "COMPLETED"


# ---------------------------------------------------------------------------
# Item 5 — duplicate detection
# ---------------------------------------------------------------------------


def test_ledger_append_idempotent_and_conflict() -> None:
    ledger = AI2RunLedger().append(record())
    assert ledger.append(record()) is ledger  # idempotent
    with pytest.raises(ValueError, match="ai2_ledger_record_conflict"):
        ledger.append(record(trust_state="stale"))
    assert len(ledger.records) == 1


def test_classify_duplicate_three_classes() -> None:
    ledger = AI2RunLedger().append(record())
    assert classify_duplicate(ledger, task="analyst", input_snapshot_sha256=SHA1) == "DUPLICATE_IDENTICAL"
    assert (
        classify_duplicate(ledger, task="analyst", input_snapshot_sha256=SHA2)
        == "DUPLICATE_REPEATED_QUESTION"
    )
    assert classify_duplicate(ledger, task="risk", input_snapshot_sha256=SHA1) == "NEW"


def test_duplicate_identical_run_can_be_flagged_and_ledgered() -> None:
    ledger = AI2RunLedger().append(record())
    dup_class = classify_duplicate(ledger, task="analyst", input_snapshot_sha256=SHA1)
    flagged = ledger.append(record(record_id="r2", status="DUPLICATE_FLAGGED"))
    assert dup_class == "DUPLICATE_IDENTICAL"
    assert flagged.records[-1].status == "DUPLICATE_FLAGGED"


def test_ledger_no_update_or_delete_path() -> None:
    public = {n for n in dir(AI2RunLedger()) if not n.startswith("_")}
    for forbidden in ("update", "remove", "delete", "pop", "clear", "rewrite", "invalidate"):
        assert forbidden not in public


# ---------------------------------------------------------------------------
# Item 6 — failure/recovery
# ---------------------------------------------------------------------------


def test_deterministic_gate_never_retried() -> None:
    assert (
        recovery_decision(
            failed_invocations=0,
            budget=BUDGET,
            failure_is_deterministic_gate=True,
        )
        == "ESCALATE_FAIL_CLOSED"
    )


def test_provider_failure_retries_within_budget_only() -> None:
    assert (
        recovery_decision(failed_invocations=1, budget=BUDGET, failure_is_deterministic_gate=False)
        == "RETRY_WITHIN_BUDGET"
    )
    assert (
        recovery_decision(failed_invocations=3, budget=BUDGET, failure_is_deterministic_gate=False)
        == "ESCALATE_FAIL_CLOSED"
    )


# ---------------------------------------------------------------------------
# Item 7 — invalidation
# ---------------------------------------------------------------------------


def test_invalidation_fires_on_trust_change_and_downgrade() -> None:
    assert invalidates("live", "stale", None, None) == ("TRUST_STATE_CHANGED", "TRUST_DOWNGRADED")
    assert invalidates("stale", "live", None, None) == ("TRUST_STATE_CHANGED",)
    assert invalidates("live", "live", None, None) == ()
    assert invalidates("live", "live", "ds-1", "ds-1") == ()
    assert invalidates("live", "live", "ds-1", "ds-2") == ("DATASET_SUPERSEDED",)
    assert invalidates("live", "live", None, "ds-2") == ()


def test_invalidation_rule_record() -> None:
    rule = AI2InvalidationRule(
        reason_codes=("TRUST_STATE_CHANGED",),
        declared_by="deterministic-rule:trust-watch",
        declared_at_utc=T0,
    )
    assert rule.schema_version
    with pytest.raises(ValidationError, match="invalidation_requires_reason"):
        AI2InvalidationRule(reason_codes=(), declared_by="x", declared_at_utc=T0)
    with pytest.raises(ValidationError):
        AI2InvalidationRule(
            reason_codes=("TRUST_STATE_CHANGED", "TRUST_STATE_CHANGED"),
            declared_by="x",
            declared_at_utc=T0,
        )


def test_invalidation_is_a_new_ledger_record_never_a_rewrite() -> None:
    ledger = AI2RunLedger().append(record())
    original = ledger.records[0]
    invalidated = ledger.append(
        record(record_id="r2", status="INVALIDATED")
    )
    assert ledger.get("r1") == original  # history unchanged
    assert invalidated.get("r2").status == "INVALIDATED"


# ---------------------------------------------------------------------------
# Item 8 — human approval state + governed acceptance
# ---------------------------------------------------------------------------


def test_governed_acceptance_blocks_pending_and_rejected() -> None:
    assert governed_acceptance(ctx(), record()) == ()
    assert governed_acceptance(ctx(), record(approval_state="PENDING")) == (
        "human_approval_outstanding",
    )
    assert governed_acceptance(ctx(), record(approval_state="REJECTED")) == (
        "human_approval_rejected",
    )


def test_governed_acceptance_blocks_identity_and_provenance_gaps() -> None:
    # A mismatched identity also leaves provenance unverifiable: both
    # blockers fire (more information, same refusal).
    assert set(governed_acceptance(ctx(), record(run_id="run-other"))) >= {"run_id_binding"}
    assert "run_kind_binding" in governed_acceptance(ctx(), record(run_kind="OTHER_KIND"))
    # Extended provenance requirement the record does not satisfy yet:
    missing = governed_acceptance(
        ctx(), record(), additionally_required_provenance=("dataset_version",)
    )
    assert "provenance_incomplete" in missing
    # Satisfying the extended requirement clears it:
    ok = governed_acceptance(
        ctx(),
        record(dataset_version="ds-9"),
        additionally_required_provenance=("dataset_version",),
    )
    assert ok == ()


def test_composition_end_to_end_all_eight_required_items() -> None:
    """Walkthrough of 02 lines 50–53: identity → provenance → budget →
    artifact → duplicate → recovery → invalidation → approval state."""
    context = ctx()
    # identity + record
    rec = record(status="COMPLETED", artifact=artifact(), approval_state="NOT_REQUIRED")
    ledger = AI2RunLedger().append(rec)
    # budget
    assert budget_verdict(BUDGET, BudgetUsage(provider_invocations=1, iterations=1, wall_seconds=12.0)) == "WITHIN_BUDGET"
    # duplicate detection on a second identical run
    assert classify_duplicate(ledger, task="analyst", input_snapshot_sha256=SHA1) == "DUPLICATE_IDENTICAL"
    # recovery on a provider failure
    assert recovery_decision(failed_invocations=1, budget=BUDGET, failure_is_deterministic_gate=False) == "RETRY_WITHIN_BUDGET"
    # invalidation when trust later degrades
    assert invalidates("live", "unavailable", None, None) == ("TRUST_STATE_CHANGED", "TRUST_DOWNGRADED")
    # acceptance gate
    assert governed_acceptance(context, rec) == ()
