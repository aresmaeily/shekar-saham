"""Multi-agent failure-model tests (additive sibling closing multi_agent.py residuals).

Pins: the closed nine-kind taxonomy (02-product §Failure model), the total
kind→behavior and kind→containment tables over multi_agent.py's OWN
vocabulary, the deterministic classify_step_failure decision function
(precedence + exception table), and BranchResult duplicate-operation
detection (idempotency controls).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.multi_agent import BranchResult
from app.domain.multi_agent_failure_model import (
    FAILURE_BEHAVIOR,
    FAILURE_RUN_CONTAINMENT,
    NINE_FAILURE_KINDS,
    BranchResultDuplicateGroup,
    branch_result_dedup_key,
    classify_step_failure,
    detect_duplicate_branch_results,
)
from app.domain.run_governance import ArtifactRef

UTC = timezone.utc
T0 = datetime(2026, 10, 18, 12, 30, 0, tzinfo=UTC)
RUN = "run-ma-1"
ART = ArtifactRef(artifact_id="a1", kind="analysis", ref="artifact://a1")


def branch(branch_id: str, step_id: str, status: str = "SUCCEEDED", run_id: str = RUN) -> BranchResult:
    return BranchResult(
        branch_id=branch_id,
        run_id=run_id,
        step_id=step_id,
        specialist_id=f"spec-{step_id}",
        addressed_to=f"orchestrator:{run_id}",
        status=status,  # type: ignore[arg-type]
        artifact=ART if status == "SUCCEEDED" else None,
        failure_code=None if status == "SUCCEEDED" else "PROVIDER_ERROR:x",
        completed_at_utc=T0,
    )


# ---------------------------------------------------------------------------
# The closed taxonomy + total behavior tables
# ---------------------------------------------------------------------------


def test_taxonomy_is_the_closed_corpus_nine() -> None:
    """Exactly the nine kinds enumerated by 02-product §Failure model."""
    assert set(NINE_FAILURE_KINDS) == {
        "PROVIDER_ERROR",        # "Provider failure"
        "MALFORMED_OUTPUT",      # "malformed output"
        "MISSING_EVIDENCE",      # "missing evidence"
        "DATA_TRUST_LOW",        # "low Data Trust"
        "TIMEOUT",               # "timeout"
        "BUDGET_EXHAUSTED",      # "budget exhaustion"
        "POLICY_VIOLATION",      # "policy violation"
        "DUPLICATE_OPERATION",   # "duplicate operation"
        "UNAVAILABLE_SPECIALIST",  # "unavailable specialist"
    }
    assert len(NINE_FAILURE_KINDS) == 9


def test_behavior_table_is_total_and_reuses_ma_vocabulary() -> None:
    assert set(FAILURE_BEHAVIOR) == set(NINE_FAILURE_KINDS)
    assert set(FAILURE_BEHAVIOR.values()) <= {"FAIL_CLOSED", "DEGRADE", "RETRY_WITHIN_BUDGET"}
    # Spot-pins of the documented policy:
    assert FAILURE_BEHAVIOR["TIMEOUT"] == "RETRY_WITHIN_BUDGET"
    assert FAILURE_BEHAVIOR["PROVIDER_ERROR"] == "RETRY_WITHIN_BUDGET"
    assert FAILURE_BEHAVIOR["MALFORMED_OUTPUT"] == "RETRY_WITHIN_BUDGET"
    assert FAILURE_BEHAVIOR["POLICY_VIOLATION"] == "FAIL_CLOSED"
    assert FAILURE_BEHAVIOR["BUDGET_EXHAUSTED"] == "FAIL_CLOSED"
    assert FAILURE_BEHAVIOR["MISSING_EVIDENCE"] == "FAIL_CLOSED"
    assert FAILURE_BEHAVIOR["DATA_TRUST_LOW"] == "FAIL_CLOSED"
    assert FAILURE_BEHAVIOR["DUPLICATE_OPERATION"] == "DEGRADE"
    assert FAILURE_BEHAVIOR["UNAVAILABLE_SPECIALIST"] == "DEGRADE"


def test_containment_table_is_total_and_uses_isolate_vocabulary() -> None:
    assert set(FAILURE_RUN_CONTAINMENT) == set(NINE_FAILURE_KINDS)
    assert set(FAILURE_RUN_CONTAINMENT.values()) <= {
        "CONTINUE_OTHER_BRANCHES",
        "TERMINATE_RUN",
    }
    # Retryable/degradable kinds stay contained; fail-closed kinds terminate.
    for kind in ("PROVIDER_ERROR", "MALFORMED_OUTPUT", "TIMEOUT", "DUPLICATE_OPERATION", "UNAVAILABLE_SPECIALIST"):
        assert FAILURE_RUN_CONTAINMENT[kind] == "CONTINUE_OTHER_BRANCHES"
    for kind in ("POLICY_VIOLATION", "BUDGET_EXHAUSTED", "MISSING_EVIDENCE", "DATA_TRUST_LOW"):
        assert FAILURE_RUN_CONTAINMENT[kind] == "TERMINATE_RUN"


# ---------------------------------------------------------------------------
# classify_step_failure — deterministic decision function
# ---------------------------------------------------------------------------


def test_classify_timeout_paths() -> None:
    assert classify_step_failure(TimeoutError, True) == "TIMEOUT"
    assert classify_step_failure(TimeoutError, timeout_elapsed=True) == "TIMEOUT"
    assert classify_step_failure(None, timeout_elapsed=True) == "TIMEOUT"
    assert classify_step_failure("TimeoutError") == "TIMEOUT"
    assert classify_step_failure(asyncio.TimeoutError()) == "TIMEOUT"  # 3.11+: same type


def test_classify_cancellation_and_unavailability() -> None:
    assert classify_step_failure(asyncio.CancelledError()) == "UNAVAILABLE_SPECIALIST"
    assert classify_step_failure(asyncio.CancelledError, cancelled=True) == "UNAVAILABLE_SPECIALIST"
    assert classify_step_failure(None, specialist_unavailable=True) == "UNAVAILABLE_SPECIALIST"
    assert classify_step_failure(None, dependency_failed=True) == "UNAVAILABLE_SPECIALIST"
    assert classify_step_failure("asyncio.CancelledError") == "UNAVAILABLE_SPECIALIST"


def test_classify_budget_trust_and_signal_flags() -> None:
    assert classify_step_failure(None, budget_state="BUDGET_EXHAUSTED") == "BUDGET_EXHAUSTED"
    assert classify_step_failure(None, budget_state="WITHIN_BUDGET") == "MISSING_EVIDENCE"
    assert classify_step_failure(None, data_trust_low=True) == "DATA_TRUST_LOW"
    assert classify_step_failure(None, artifact_invalid=True) == "MISSING_EVIDENCE"
    assert classify_step_failure(None, malformed_output=True) == "MALFORMED_OUTPUT"
    assert classify_step_failure(None, duplicate_operation=True) == "DUPLICATE_OPERATION"


def test_classify_exception_table() -> None:
    assert classify_step_failure(ValueError("x")) == "POLICY_VIOLATION"
    assert classify_step_failure(TypeError) == "POLICY_VIOLATION"
    assert classify_step_failure(KeyError("k")) == "POLICY_VIOLATION"
    assert classify_step_failure("ValidationError") == "POLICY_VIOLATION"
    assert classify_step_failure(RuntimeError("transport down")) == "PROVIDER_ERROR"
    assert classify_step_failure(ConnectionError) == "PROVIDER_ERROR"
    assert classify_step_failure(OSError("io")) == "PROVIDER_ERROR"
    assert classify_step_failure(MemoryError()) == "BUDGET_EXHAUSTED"
    assert classify_step_failure("RecursionError") == "BUDGET_EXHAUSTED"


def test_classify_no_evidence_falls_to_missing_evidence() -> None:
    assert classify_step_failure(None) == "MISSING_EVIDENCE"


def test_classify_precedence_is_deterministic() -> None:
    # Documented policy: explicit signal flags beat the exception table.
    # A CancelledError INSTANCE alone classifies as unavailable-specialist,
    # but combined with the timeout flag the flag wins.
    assert classify_step_failure(asyncio.CancelledError(), True) == "TIMEOUT"
    # Duplicate-operation signal dominates the exception table.
    assert classify_step_failure(ValueError("x"), duplicate_operation=True) == "DUPLICATE_OPERATION"
    # Timeout dominates budget.
    assert classify_step_failure(None, True, "BUDGET_EXHAUSTED") == "TIMEOUT"
    # Budget dominates the exception table (a ValueError under exhaustion is
    # governed by the exhausted budget, not the exception type).
    assert classify_step_failure(ValueError("x"), False, "BUDGET_EXHAUSTED") == "BUDGET_EXHAUSTED"
    # Tuple input: first member's classification wins (caller precedence).
    assert classify_step_failure((TimeoutError, ValueError)) == "TIMEOUT"
    assert classify_step_failure((ValueError, TimeoutError)) == "POLICY_VIOLATION"


def test_classify_is_total_and_pure_over_all_kinds() -> None:
    """Every kind is reachable and the function never raises on its domain."""
    seen = set()
    for exc in (None, TimeoutError, asyncio.CancelledError, ValueError, RuntimeError, MemoryError):
        for timeout in (False, True):
            for budget in (None, "WITHIN_BUDGET", "BUDGET_EXHAUSTED"):
                seen.add(classify_step_failure(exc, timeout, budget))
    assert seen <= set(NINE_FAILURE_KINDS)
    assert {"TIMEOUT", "BUDGET_EXHAUSTED", "POLICY_VIOLATION", "PROVIDER_ERROR", "MISSING_EVIDENCE"} <= seen


# ---------------------------------------------------------------------------
# BranchResult dedup key + duplicate-operation detection
# ---------------------------------------------------------------------------


def test_dedup_key_is_canonical_and_deterministic() -> None:
    k1 = branch_result_dedup_key("run-1", "s1", 1)
    assert k1 == branch_result_dedup_key("run-1", "s1", 1)
    assert k1 != branch_result_dedup_key("run-1", "s1", 2)
    assert k1 != branch_result_dedup_key("run-1", "s2", 1)
    assert k1 != branch_result_dedup_key("run-2", "s1", 1)
    # Collision-proof for ids containing separator characters (JSON array).
    assert branch_result_dedup_key("run|1", "s|1", 1) != branch_result_dedup_key(
        "run", "1|s|1", 1
    )


def test_detect_duplicate_branch_results_groups_same_operation() -> None:
    b1 = branch("b1", "s1")
    b2 = branch("b2", "s1")
    b3 = branch("b3", "s2")
    groups = detect_duplicate_branch_results((b1, b2, b3))
    assert len(groups) == 1
    g = groups[0]
    assert isinstance(g, BranchResultDuplicateGroup)
    assert (g.run_id, g.step_id) == (RUN, "s1")
    assert g.branch_ids == ("b1", "b2")
    assert g.statuses == ("SUCCEEDED", "SUCCEEDED")
    assert g.dedup_key == branch_result_dedup_key(RUN, "s1", 1)


def test_detect_respects_attempts_and_is_order_independent() -> None:
    b1 = branch("b1", "s1")
    b2 = branch("b2", "s1")
    # Same step, different attempts = legitimate retry chain, NOT duplicates.
    assert detect_duplicate_branch_results((b1, b2), attempts={"b2": 2}) == ()
    # Same attempt across shuffled input order → same groups.
    g1 = detect_duplicate_branch_results((branch("b1", "s1"), branch("b2", "s1"), branch("b3", "s2"), branch("b4", "s2")))
    g2 = detect_duplicate_branch_results((branch("b4", "s2"), branch("b1", "s1"), branch("b3", "s2"), branch("b2", "s1")))
    assert g1 == g2
    assert [g.step_id for g in g1] == ["s1", "s2"]  # sorted by dedup key


def test_detect_ignores_unique_and_mixed_run_ids() -> None:
    single = detect_duplicate_branch_results((branch("b1", "s1"), branch("b2", "s2")))
    assert single == ()
    # Different run_ids are different operations — never grouped together.
    mixed = detect_duplicate_branch_results(
        (branch("b1", "s1", run_id=RUN), branch("b2", "s1", run_id="run-other"))
    )
    assert mixed == ()


def test_duplicate_group_model_is_frozen() -> None:
    g = BranchResultDuplicateGroup(
        dedup_key=branch_result_dedup_key(RUN, "s1", 1),
        run_id=RUN,
        step_id="s1",
        attempt=1,
        branch_ids=("b1", "b2"),
        statuses=("SUCCEEDED", "SUCCEEDED"),
    )
    with pytest.raises(ValidationError):
        g.run_id = "other"  # type: ignore[misc]


def test_detect_needs_two_branch_results_with_same_shape() -> None:
    # Degenerate input (non-BranchResult objects) is ignored, never raised on.
    assert detect_duplicate_branch_results((object(), "not-a-result", None)) == ()  # type: ignore[list-item]
