"""AI-MA specialist executors — synthetic-safe implementations (WP-C).

WAVE-AB3 (2026-11-08): deterministic, bounded, paper-only executors for the
three shipped specialists (``app.domain.ai_ma_specialists``). Each executor:

- is async, bounded, and SYNTHETIC-SAFE: no network, no LLM, no production
  mutation, no clock reads, no I/O (the SpecialistExecutor protocol's
  reference discipline);
- produces DISTINCT deterministic reasoning value (not three copies of the
  same function): hypothesis DRAFTING from a question, INTERPRETATION of
  consumed artifacts, LEARNING-CHALLENGE over consumed artifacts;
- may invoke ONLY the deterministic tools declared in its contract's
  ``allowed_tools`` — any other tool reference is a fail-closed construction
  error (the evaluator-tool seam: specialists reach deterministic evaluators
  exclusively through this closed seam, never around it);
- emits SpecialistOutcome records; the RUNTIME (not the executor) mints
  BranchResults, so addressing/status rules stay in one place.

Everything here is advisory; nothing in this module can touch financial
truth or production state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.domain.ai_intelligence import trust_confidence_cap_for_state
from app.domain.ai_ma_specialists import DETERMINISTIC_TOOLS
from app.domain.multi_agent import OrchestrationStep, SpecialistContract
from app.domain.multi_agent_failure_model import detect_duplicate_branch_results
from app.domain.run_governance import ArtifactRef
from app.services.multi_agent_runtime import SpecialistOutcome


def _artifact_ref(step: OrchestrationStep, payload, content: Mapping[str, Any]) -> ArtifactRef:
    """Mint the artifact-first reference for one specialist output.

    WAVE-AI (2026-11-08, WP-C): the shipped executors previously returned
    summary-only outcomes, so every BranchResult they produced was refused by
    ``deterministic_synthesis`` (``summary_only_without_artifact``) and the
    artifact-first branch-exchange rule (02 rule 9) was never exercised by
    the shipped specialists. Now each executor binds its payload content to
    a verifiable ArtifactRef: ``sha256`` is the digest of the canonical JSON
    of the CONTENT (never the run id or a wall clock), so the same question
    yields byte-identical artifact digests across runs (pinned by test) while
    ``artifact_id``/``ref`` keep per-run identity. Content stays small and
    bounded; the ref — not the blob — travels through BranchResults.
    """
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ArtifactRef(
        artifact_id=f"{payload.run_id}:{step.step_id}",
        kind=f"aima.{step.capability}"[:64],
        ref=f"inmem://aima/{payload.run_id}/{step.step_id}.json",
        sha256=digest,
    )

# ---------------------------------------------------------------------------
# Deterministic tools (pure functions; the closed seam's implementations)
# ---------------------------------------------------------------------------

def tool_duplicate_branch_detection(input: Mapping[str, Any]) -> Mapping[str, Any]:
    """Deterministic duplicate/syndicated-branch detection over payload
    records (read-only; wraps detect_duplicate_branch_results)."""
    from app.domain.multi_agent import BranchResult  # local import: cycle-safe

    records = input.get("branch_results") or []
    results = []
    for r in records:
        if isinstance(r, BranchResult):
            results.append(r)
        elif isinstance(r, Mapping):
            results.append(BranchResult.model_validate(r))
        else:
            raise ValueError("duplicate_branch_detection_input_not_branch_results")
    groups = detect_duplicate_branch_results(results)
    return {
        "duplicate_groups": len(groups),
        "groups": [g.model_dump(mode="json") for g in groups],
    }


def tool_trust_cap_lookup(input: Mapping[str, Any]) -> Mapping[str, Any]:
    """Deterministic trust→confidence-cap lookup (read-only)."""
    state = str(input.get("state") or "unknown")
    cap = trust_confidence_cap_for_state(state)
    return {"state": state, "confidence_cap": cap}


_INVALIDATION_MARKERS = (
    "اگر",  # Persian conditional marker
    "if ",
    "invalidate",
    "ابطال",
    "اطلا",  # bounded tolerance for common Persian typography
)


def tool_invalidation_completeness_check(input: Mapping[str, Any]) -> Mapping[str, Any]:
    """Deterministic structural check: does the statement carry an explicit
    invalidation condition? (read-only; conservative marker scan)"""
    statement = str(input.get("statement") or "")
    lowered = statement.lower()
    has_invalidation = any(marker in lowered or marker in statement for marker in _INVALIDATION_MARKERS)
    return {
        "has_invalidation": has_invalidation,
        "complete": bool(statement.strip()) and has_invalidation,
    }


TOOL_IMPLEMENTATIONS = {
    "duplicate_branch_detection": tool_duplicate_branch_detection,
    "trust_cap_lookup": tool_trust_cap_lookup,
    "invalidation_completeness_check": tool_invalidation_completeness_check,
}


# ---------------------------------------------------------------------------
# Executor base: fail-closed tool allowlist enforcement
# ---------------------------------------------------------------------------

class _ToolBoundedExecutor:
    """Base for shipped executors: enforces the contract's tool allowlist.

    The seam is closed by construction: a tool NOT in the specialist's own
    contract raises ``ToolNotPermitted`` instead of executing (fail-closed;
    no quiet fallback, no dynamic discovery).
    """

    def __init__(self, contract: SpecialistContract, tools: Mapping[str, Any] | None = None) -> None:
        self._contract = contract
        merged = dict(TOOL_IMPLEMENTATIONS)
        if tools:
            unknown = sorted(set(tools) - set(DETERMINISTIC_TOOLS))
            if unknown:
                raise ValueError(f"tool_not_in_closed_vocabulary:{','.join(unknown)[:200]}")
            merged.update(tools)
        missing = sorted(set(contract.allowed_tools) - set(merged))
        if missing:
            raise ValueError(f"tool_not_implemented:{','.join(missing)[:200]}")
        self._tools = {name: merged[name] for name in contract.allowed_tools}

    def _use_tool(self, name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if name not in self._tools:
            raise ToolNotPermitted(name, self._contract.specialist_id)
        return dict(self._tools[name](payload))


class ToolNotPermitted(Exception):
    """Raised when a specialist tries to use a tool outside its contract."""

    def __init__(self, tool: str, specialist_id: str) -> None:
        super().__init__(f"tool_not_permitted:{tool}:{specialist_id}")
        self.tool = tool
        self.specialist_id = specialist_id


def _artifact_summary(payload_summary: str, limit: int = 200) -> str:
    return payload_summary[:limit]


# ---------------------------------------------------------------------------
# 1) Hypothesis-Draft executor
# ---------------------------------------------------------------------------

class HypothesisDraftExecutor(_ToolBoundedExecutor):
    """Drafts bounded hypothesis candidates from the step's question.

    Distinct reasoning value: turns a research question into structurally
    complete drafts (mechanism + expectation + EXPLICIT invalidation), then
    self-checks each draft with the contract's own tool. Deterministic: the
    same question always yields the same drafts; nothing is invented beyond
    the two bounded framings.
    """

    _QUESTION_PREFIX = "question:"
    _FRAMINGS = (
        ("MOMENTUM", "continuation"),
        ("MEAN_REVERSION", "reversal"),
    )
    _MAX_QUESTION = 300

    async def execute(
        self, step: OrchestrationStep, payload, deadline: float
    ) -> SpecialistOutcome:
        notes = payload.notes or ""
        if not notes.startswith(self._QUESTION_PREFIX):
            return SpecialistOutcome(
                ok=False,
                failure_code="MISSING_QUESTION",
                failure_kind="MISSING_EVIDENCE",
                summary="payload.notes must carry 'question:' prefix",
            )
        question = notes[len(self._QUESTION_PREFIX):].strip()[: self._MAX_QUESTION]
        if not question:
            return SpecialistOutcome(
                ok=False,
                failure_code="EMPTY_QUESTION",
                failure_kind="MISSING_EVIDENCE",
                summary="empty research question",
            )
        drafts: list[dict[str, Any]] = []
        for framing, direction in self._FRAMINGS:
            statement = (
                f"[{framing}] برای پرسش «{question}»: فرضیه {direction} — "
                f"اگر جهت پیش‌بینی در بازه ارزیابی معکوس شود، این فرضیه ابطال می‌شود."
            )
            check = self._use_tool(
                "invalidation_completeness_check", {"statement": statement}
            )
            drafts.append(
                {
                    "framing": framing,
                    "statement": statement,
                    "invalidation_explicit": bool(check.get("has_invalidation")),
                    "preregistered": True,
                }
            )
        summary = f"drafted {len(drafts)} preregistered hypotheses (explicit invalidations)"
        return SpecialistOutcome(
            ok=True,
            summary=_artifact_summary(summary),
            artifact=_artifact_ref(step, payload, {"drafts": drafts}),
        )


# ---------------------------------------------------------------------------
# 2) Interpretation executor
# ---------------------------------------------------------------------------

class InterpretationExecutor(_ToolBoundedExecutor):
    """Deterministic structured interpretation of consumed results.

    Distinct reasoning value: reads ONLY the BranchResults handed to it
    (artifact-first), and produces a per-artifact reading: status, summary
    head, and the trust-implied confidence cap from the closed tool seam.
    No facts are invented; an empty consumption set is an honest
    MISSING_EVIDENCE failure (never a fake interpretation).
    """

    async def execute(
        self, step: OrchestrationStep, payload, deadline: float
    ) -> SpecialistOutcome:
        consumed = payload.consumed_results
        if not consumed:
            return SpecialistOutcome(
                ok=False,
                failure_code="NOTHING_TO_INTERPRET",
                failure_kind="MISSING_EVIDENCE",
                summary="no consumed results; refusing to invent an interpretation",
            )
        readings: list[dict[str, Any]] = []
        for result in consumed:
            cap_check = self._use_tool("trust_cap_lookup", {"state": "synthetic"})
            readings.append(
                {
                    "step_id": result.step_id,
                    "status": result.status,
                    "summary_head": result.summary[:120],
                    "confidence_cap": cap_check.get("confidence_cap"),
                }
            )
        ok_count = sum(1 for r in readings if r["status"] == "SUCCEEDED")
        summary = f"interpreted {len(readings)} consumed artifact(s); {ok_count} SUCCEEDED"
        return SpecialistOutcome(
            ok=True,
            summary=_artifact_summary(summary),
            artifact=_artifact_ref(step, payload, {"readings": readings}),
        )


# ---------------------------------------------------------------------------
# 3) Learning-Challenge executor
# ---------------------------------------------------------------------------

class LearningChallengeExecutor(_ToolBoundedExecutor):
    """Challenges consumed results deterministically.

    Distinct reasoning value: duplicate/syndicated detection across the
    consumed set (closed tool), plus per-artifact invalidation-completeness
    challenges on the summaries it was handed. Emits CHALLENGE notes only —
    it never overrules a deterministic evaluator nor mints a verdict.
    """

    async def execute(
        self, step: OrchestrationStep, payload, deadline: float
    ) -> SpecialistOutcome:
        consumed = payload.consumed_results
        if not consumed:
            return SpecialistOutcome(
                ok=False,
                failure_code="NOTHING_TO_CHALLENGE",
                failure_kind="MISSING_EVIDENCE",
                summary="no consumed results; nothing to challenge",
            )
        dup = self._use_tool("duplicate_branch_detection", {"branch_results": [r.model_dump(mode="json") for r in consumed]})
        challenges: list[dict[str, Any]] = []
        for result in consumed:
            check = self._use_tool(
                "invalidation_completeness_check", {"statement": result.summary or ""}
            )
            if not check.get("complete"):
                challenges.append(
                    {
                        "step_id": result.step_id,
                        "kind": "MISSING_INVALIDATION",
                        "note": "خلاصه شاخه شرط ابطال صریح ندارد — چالش ثبت شد",
                    }
                )
        duplicate_groups = int(dup.get("duplicate_groups") or 0)
        if duplicate_groups:
            challenges.append(
                {
                    "step_id": "*",
                    "kind": "DUPLICATE_OPERATION",
                    "note": f"{duplicate_groups} duplicate group(s) detected across consumed set",
                }
            )
        summary = f"challenged {len(consumed)} result(s): {len(challenges)} challenge note(s), {duplicate_groups} duplicate group(s)"
        return SpecialistOutcome(
            ok=True,
            summary=_artifact_summary(summary),
            artifact=_artifact_ref(
                step,
                payload,
                {"duplicate_groups": duplicate_groups, "challenges": challenges},
            ),
        )


# ---------------------------------------------------------------------------
# Shipped executor registry composition
# ---------------------------------------------------------------------------

def shipped_specialist_executors(
    contracts,
    *,
    extra_tools: Mapping[str, Any] | None = None,
) -> dict[str, _ToolBoundedExecutor]:
    """Compose specialist_id → executor for the shipped contracts.

    ``extra_tools`` (test seam only) may OVERRIDE implementations of the
    closed vocabulary; unknown tool names fail at construction.
    """
    from app.domain.ai_ma_specialists import shipped_specialist_contracts

    return {
        c.specialist_id: cls(c, tools=extra_tools)
        for c, cls in zip(
            shipped_specialist_contracts(),
            (HypothesisDraftExecutor, InterpretationExecutor, LearningChallengeExecutor),
        )
    }
