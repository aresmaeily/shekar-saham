"""Multi-agent failure model — closed nine-kind taxonomy (additive sibling, AI-MA-F).

Closing the self-disclosed residual in ``app/domain/multi_agent.py`` (module
docstring, engineering-authority notes): "FAILURE-MODEL MAPPING IS PARTIAL
(02-product §Failure model enumerates nine failure kinds): this layer
represents failures generically ... There is no kind→behavior taxonomy table
and no BranchResult duplicate-operation detection yet; a future additive
iteration may introduce one."

This module IS that additive iteration. It does NOT modify multi_agent.py;
it reuses that module's published vocabulary (``SpecialistFailureBehavior``
literals and ``isolate_failure``'s containment literals) — no parallel
vocabulary is invented.

Corpus locus (2026-10-02 amendment corpus, byte-verified):
02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE_CURRENT_2026-10-02.md §Failure model:

    Provider failure, malformed output, missing evidence, low Data Trust,
    timeout, budget exhaustion, policy violation, duplicate operation or
    unavailable specialist must safely fail, degrade or retry under
    idempotency controls.

That sentence enumerates EXACTLY NINE failure kinds. ``FailureKind`` is the
closed Literal over those nine, named consistently with the corpus nouns:

==============================  =========================================
corpus phrase                   FailureKind literal
==============================  =========================================
"Provider failure"              PROVIDER_ERROR
"malformed output"              MALFORMED_OUTPUT
"missing evidence"              MISSING_EVIDENCE
"low Data Trust"                DATA_TRUST_LOW
"timeout"                       TIMEOUT
"budget exhaustion"             BUDGET_EXHAUSTED
"policy violation"              POLICY_VIOLATION
"duplicate operation"           DUPLICATE_OPERATION
"unavailable specialist"        UNAVAILABLE_SPECIALIST
==============================  =========================================

Crosswalk to the implementation-task's illustrative kind names (engineering
authority note, recorded so the naming choice is auditable):

    TIMEOUT            -> TIMEOUT
    PROVIDER_ERROR     -> PROVIDER_ERROR
    CONTRACT_VIOLATION -> POLICY_VIOLATION
    BUDGET_EXHAUSTED   -> BUDGET_EXHAUSTED
    INVALID_ARTIFACT   -> MISSING_EVIDENCE
    CANCELLED          -> UNAVAILABLE_SPECIALIST (a cancelled specialist is
                          unavailable to the run; the precise cause stays in
                          the BranchResult failure_code / trace detail)
    DEPENDENCY_FAILED  -> UNAVAILABLE_SPECIALIST (its input was unavailable)
    RESOURCE_LIMIT     -> BUDGET_EXHAUSTED (resource budgets are budgets;
                          D-AI-24 bounded resources)
    UNKNOWN            -> MISSING_EVIDENCE (a failure with no classifiable
                          evidence is a missing-evidence case)

Behavior mappings reuse multi_agent.py's own literals:
- ``FAILURE_BEHAVIOR``: kind -> SpecialistFailureBehavior
  ("FAIL_CLOSED" | "DEGRADE" | "RETRY_WITHIN_BUDGET") — the specialist's own
  contract behavior (03 §Specialist).
- ``FAILURE_RUN_CONTAINMENT``: kind -> RunContainment
  ("CONTINUE_OTHER_BRANCHES" | "TERMINATE_RUN") — the kind-level default in
  ``isolate_failure``'s vocabulary. Advisory default only: the runtime's run
  decision is the CONJUNCTION with multi_agent.isolate_failure's dependency
  graph decision (a load-bearing failure terminates regardless of kind).

Contract/domain only: frozen records, deterministic, clock-free, no I/O,
no network, no LLM, no scheduler. Nothing silently swallows a failure: every
classification is a total, pure decision function.
"""

from __future__ import annotations

import json
from asyncio import CancelledError
from types import MappingProxyType
from typing import Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ai2_governance import BudgetVerdict
from app.domain.multi_agent import SpecialistFailureBehavior

__all__ = [
    "FailureKind",
    "NINE_FAILURE_KINDS",
    "FAILURE_BEHAVIOR",
    "FAILURE_RUN_CONTAINMENT",
    "RunContainment",
    "classify_step_failure",
    "branch_result_dedup_key",
    "detect_duplicate_branch_results",
    "BranchResultDuplicateGroup",
]


# ---------------------------------------------------------------------------
# The closed nine-kind taxonomy (02-product §Failure model)
# ---------------------------------------------------------------------------

FailureKind = Literal[
    "PROVIDER_ERROR",
    "MALFORMED_OUTPUT",
    "MISSING_EVIDENCE",
    "DATA_TRUST_LOW",
    "TIMEOUT",
    "BUDGET_EXHAUSTED",
    "POLICY_VIOLATION",
    "DUPLICATE_OPERATION",
    "UNAVAILABLE_SPECIALIST",
]

#: Canonical order of the nine kinds (closed set; total over the Literal).
NINE_FAILURE_KINDS: tuple[FailureKind, ...] = (
    "PROVIDER_ERROR",
    "MALFORMED_OUTPUT",
    "MISSING_EVIDENCE",
    "DATA_TRUST_LOW",
    "TIMEOUT",
    "BUDGET_EXHAUSTED",
    "POLICY_VIOLATION",
    "DUPLICATE_OPERATION",
    "UNAVAILABLE_SPECIALIST",
)

#: kind -> specialist contract behavior. Values are multi_agent.py's own
#: SpecialistFailureBehavior literals — no parallel vocabulary.
FAILURE_BEHAVIOR: Mapping[FailureKind, SpecialistFailureBehavior] = MappingProxyType(
    {
        "PROVIDER_ERROR": "RETRY_WITHIN_BUDGET",
        "MALFORMED_OUTPUT": "RETRY_WITHIN_BUDGET",
        "TIMEOUT": "RETRY_WITHIN_BUDGET",
        "MISSING_EVIDENCE": "FAIL_CLOSED",
        "DATA_TRUST_LOW": "FAIL_CLOSED",
        "BUDGET_EXHAUSTED": "FAIL_CLOSED",
        "POLICY_VIOLATION": "FAIL_CLOSED",
        "DUPLICATE_OPERATION": "DEGRADE",
        "UNAVAILABLE_SPECIALIST": "DEGRADE",
    }
)

#: kind-level run containment default, in ``isolate_failure``'s vocabulary.
#: Rationale: retryable/degradable kinds stay contained (independent branches
#: continue); fail-closed kinds terminate the run. The runtime must CONJOIN
#: this with multi_agent.isolate_failure's dependency-graph decision — a
#: load-bearing failure terminates regardless of kind (dependents can never
#: run honestly).
RunContainment = Literal["CONTINUE_OTHER_BRANCHES", "TERMINATE_RUN"]

FAILURE_RUN_CONTAINMENT: Mapping[FailureKind, RunContainment] = MappingProxyType(
    {
        "PROVIDER_ERROR": "CONTINUE_OTHER_BRANCHES",
        "MALFORMED_OUTPUT": "CONTINUE_OTHER_BRANCHES",
        "TIMEOUT": "CONTINUE_OTHER_BRANCHES",
        "DUPLICATE_OPERATION": "CONTINUE_OTHER_BRANCHES",
        "UNAVAILABLE_SPECIALIST": "CONTINUE_OTHER_BRANCHES",
        "MISSING_EVIDENCE": "TERMINATE_RUN",
        "DATA_TRUST_LOW": "TERMINATE_RUN",
        "BUDGET_EXHAUSTED": "TERMINATE_RUN",
        "POLICY_VIOLATION": "TERMINATE_RUN",
    }
)


# ---------------------------------------------------------------------------
# Deterministic classification
# ---------------------------------------------------------------------------

#: Exception type names treated as deterministic contract/policy breaches
#: (retrying the same input reproduces them) -> POLICY_VIOLATION.
_CONTRACT_EXCEPTION_NAMES = frozenset(
    {
        "ValueError",
        "TypeError",
        "KeyError",
        "AttributeError",
        "LookupError",
        "IndexError",
        "AssertionError",
        "ValidationError",  # pydantic
        "JSONDecodeError",  # subclasses ValueError; listed for str-based input
        "UnicodeDecodeError",
    }
)

#: Exception type names treated as resource-budget exhaustion -> BUDGET_EXHAUSTED
#: (resource budgets are budgets; D-AI-24 bounded resources).
_RESOURCE_EXCEPTION_NAMES = frozenset({"MemoryError", "RecursionError"})


def _classify_exception_type(exc_type: type[BaseException]) -> FailureKind:
    """Deterministic exception-type -> kind table (documented order)."""
    if issubclass(exc_type, CancelledError):
        # A cancelled specialist is unavailable to the run (corpus kind);
        # the precise cancellation cause stays in the failure_code/detail.
        return "UNAVAILABLE_SPECIALIST"
    if issubclass(exc_type, TimeoutError):
        return "TIMEOUT"
    if exc_type.__name__ in _RESOURCE_EXCEPTION_NAMES:
        return "BUDGET_EXHAUSTED"
    if exc_type.__name__ in _CONTRACT_EXCEPTION_NAMES:
        return "POLICY_VIOLATION"
    # Any other exception (OSError, ConnectionError, RuntimeError, generic
    # Exception, ...) is a capability-provider failure (corpus: "Provider
    # failure"). BaseException stragglers map here too — fail visible.
    return "PROVIDER_ERROR"


def classify_step_failure(
    exc_type: type[BaseException] | BaseException | str | tuple[type[BaseException], ...] | None,
    timeout_elapsed: bool = False,
    budget_state: BudgetVerdict | None = None,
    *,
    cancelled: bool = False,
    duplicate_operation: bool = False,
    specialist_unavailable: bool = False,
    dependency_failed: bool = False,
    data_trust_low: bool = False,
    artifact_invalid: bool = False,
    malformed_output: bool = False,
) -> FailureKind:
    """Deterministic step-failure classification (total, pure, clock-free).

    Precedence (first match wins; the order below is the documented policy):
        1. ``cancelled``                      -> UNAVAILABLE_SPECIALIST
        2. ``duplicate_operation``            -> DUPLICATE_OPERATION
        3. ``specialist_unavailable`` or
           ``dependency_failed``              -> UNAVAILABLE_SPECIALIST
        4. ``timeout_elapsed``                -> TIMEOUT
        5. ``budget_state == "BUDGET_EXHAUSTED"`` -> BUDGET_EXHAUSTED
        6. ``data_trust_low``                 -> DATA_TRUST_LOW
        7. ``artifact_invalid``               -> MISSING_EVIDENCE
        8. ``malformed_output``               -> MALFORMED_OUTPUT
        9. exception-type table:
             CancelledError                  -> UNAVAILABLE_SPECIALIST
             TimeoutError                    -> TIMEOUT
             MemoryError / RecursionError    -> BUDGET_EXHAUSTED
             contract family (ValueError,
               TypeError, KeyError, ...,
               pydantic ValidationError)     -> POLICY_VIOLATION
             anything else                   -> PROVIDER_ERROR
        10. no exception and no signal        -> MISSING_EVIDENCE (a failure
             with no classifiable evidence is a missing-evidence case)

    ``exc_type`` accepts an exception class, an exception instance, an
    exception-name string, an except-style tuple (the FIRST member's
    classification wins — tuple order is the caller's precedence), or None.
    """
    if cancelled:
        return "UNAVAILABLE_SPECIALIST"
    if duplicate_operation:
        return "DUPLICATE_OPERATION"
    if specialist_unavailable or dependency_failed:
        return "UNAVAILABLE_SPECIALIST"
    if timeout_elapsed:
        return "TIMEOUT"
    if budget_state == "BUDGET_EXHAUSTED":
        return "BUDGET_EXHAUSTED"
    if data_trust_low:
        return "DATA_TRUST_LOW"
    if artifact_invalid:
        return "MISSING_EVIDENCE"
    if malformed_output:
        return "MALFORMED_OUTPUT"

    if exc_type is None:
        return "MISSING_EVIDENCE"
    if isinstance(exc_type, str):
        name = exc_type.rsplit(".", 1)[-1]
        if name == "CancelledError":
            return "UNAVAILABLE_SPECIALIST"
        if name == "TimeoutError":
            return "TIMEOUT"
        if name in _RESOURCE_EXCEPTION_NAMES:
            return "BUDGET_EXHAUSTED"
        if name in _CONTRACT_EXCEPTION_NAMES:
            return "POLICY_VIOLATION"
        return "PROVIDER_ERROR"
    if isinstance(exc_type, tuple):
        if not exc_type:
            return "MISSING_EVIDENCE"
        return _classify_exception_type(exc_type[0])
    if isinstance(exc_type, type):
        return _classify_exception_type(exc_type)
    # Exception instance.
    return _classify_exception_type(type(exc_type))


# ---------------------------------------------------------------------------
# BranchResult idempotency / duplicate-operation detection
# ---------------------------------------------------------------------------


def branch_result_dedup_key(run_id: str, step_id: str, attempt: int) -> str:
    """Canonical dedup key for one branch-operation record.

    Canonical form: a JSON array of [run_id, step_id, attempt] with compact
    separators — collision-proof for ids containing separator characters and
    byte-stable for identical inputs (deterministic idempotency fingerprint;
    02-product §Failure model "under idempotency controls").
    """
    return json.dumps([run_id, step_id, int(attempt)], ensure_ascii=False, separators=(",", ":"))


class BranchResultDuplicateGroup(BaseModel):
    """One duplicate-operation group detected over BranchResult records."""

    model_config = ConfigDict(frozen=True)

    dedup_key: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    attempt: int = Field(ge=0)
    branch_ids: tuple[str, ...] = Field(min_length=2)
    statuses: tuple[str, ...] = Field(min_length=2)


def detect_duplicate_branch_results(
    results: Iterable["object"],
    *,
    attempts: Mapping[str, int] | None = None,
) -> tuple[BranchResultDuplicateGroup, ...]:
    """Duplicate-operation detection over BranchResult records.

    Groups results by ``branch_result_dedup_key(run_id, step_id, attempt)``;
    a group with two or more members means the SAME operation
    (run, step, attempt) was recorded more than once (e.g. a double-append
    from a retried dispatcher) — exactly the corpus's "duplicate operation"
    kind made detectable. ``attempts`` optionally maps branch_id -> attempt
    number (default: every result is its own attempt 1). Results with the
    same (run_id, step_id) but DIFFERENT attempts are legitimate retry
    chains, not duplicates. Groups are fully canonical (members sorted by
    branch_id, groups sorted by dedup key) — identical inputs in any order
    produce identical output. Non-duplicate results are never returned.
    """
    buckets: dict[str, tuple[str, str, int, list[str], list[str]]] = {}
    for r in results:
        run_id = getattr(r, "run_id", None)
        step_id = getattr(r, "step_id", None)
        branch_id = getattr(r, "branch_id", None)
        status = getattr(r, "status", None)
        if not all(isinstance(x, str) and x for x in (run_id, step_id, branch_id, status)):
            continue
        attempt = int((attempts or {}).get(branch_id, 1))
        key = branch_result_dedup_key(run_id, step_id, attempt)
        entry = buckets.get(key)
        if entry is None:
            buckets[key] = (run_id, step_id, attempt, [branch_id], [status])
        else:
            entry[3].append(branch_id)
            entry[4].append(status)
    groups: list[BranchResultDuplicateGroup] = []
    for key, (run_id, step_id, attempt, branch_ids, statuses) in buckets.items():
        if len(branch_ids) < 2:
            continue
        # Canonical member order: sorted by branch_id (statuses stay aligned),
        # so the group is identical regardless of input order.
        pairs = sorted(zip(branch_ids, statuses), key=lambda p: p[0])
        groups.append(
            BranchResultDuplicateGroup(
                dedup_key=key,
                run_id=run_id,
                step_id=step_id,
                attempt=attempt,
                branch_ids=tuple(b for b, _ in pairs),
                statuses=tuple(s for _, s in pairs),
            )
        )
    return tuple(sorted(groups, key=lambda g: g.dedup_key))
