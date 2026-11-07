"""AI-MA shipped specialists — the three approved runtime roles (WP-C).

WAVE-AB3 (2026-11-08, MASTER-CONTINUOUS-EXECUTION directive §6): the runtime
audit recorded a P0 gap — the governed orchestration machinery (contracts,
registry, plan/branch/trace/failure model) was complete and tested, but NO
specialist of the three approved roles existed anywhere: no contract, no
executor, no registry entry. The runtime was a generic executor seam used
only by test fixtures.

This module ships the three approved specialists as GOVERNED CONTRACTS:

- ``AIMA-HYPOTHESIS-DRAFT``  (capability ``hypothesis_draft``)
- ``AIMA-INTERPRETATION``    (capability ``interpretation``)
- ``AIMA-LEARNING-CHALLENGE``(capability ``learning_challenge``)

Design rules honoured here:

- Governance responsibilities, NOT 17 runtime LLM agents (directive §2): each
  specialist has a DISTINCT capability, a DISTINCT contract, a declared
  measurable benefit and an honest coordination-cost note (directive §6:
  "Each runtime specialist must demonstrate distinct reasoning value, a
  distinct contract, measurable benefit and acceptable coordination cost").
- Specialists NEVER independently alter financial truth or production state
  (directive §6): every contract's ``authority_boundary`` pins
  ADVISORY-ONLY / NO-FINANCIAL-TRUTH / NO-PRODUCTION-MUTATION, and the
  executors that implement them are synthetic-safe (no network, no LLM, no
  I/O, no clock) — see ``app.services.ai_ma_specialist_executors``.
- Deterministic evaluator tools are the ONLY tools specialists may use; the
  closed tool vocabulary lives here (``DETERMINISTIC_TOOLS``) so contracts
  reference exactly the tools the executor registry ships (fail-closed
  misconfiguration).
- Bounded: per-run invocation ceilings, bounded timeouts, bounded output
  shapes; AGENT_AS_TOOL interaction pattern only (no HANDOFF — no autonomous
  agent spawning; arch rule 4/6).
"""

from __future__ import annotations

from typing import Mapping

from pydantic import BaseModel

from app.domain.multi_agent import CapabilityRegistry, SpecialistContract

# ---------------------------------------------------------------------------
# Closed deterministic tool vocabulary (the evaluator-tool seam's allowlist)
# ---------------------------------------------------------------------------

DETERMINISTIC_TOOLS: tuple[str, ...] = (
    "duplicate_branch_detection",
    "trust_cap_lookup",
    "invalidation_completeness_check",
)

TOOL_DESCRIPTIONS: Mapping[str, str] = {
    "duplicate_branch_detection": (
        "flags duplicate/syndicated branch results among consumed artifacts "
        "(wraps multi_agent_failure_model.detect_duplicate_branch_results — "
        "deterministic, read-only)"
    ),
    "trust_cap_lookup": (
        "returns the confidence cap implied by a data-trust state "
        "(deterministic lookup over the state→cap table — read-only)"
    ),
    "invalidation_completeness_check": (
        "checks that a candidate statement carries explicit invalidation "
        "conditions (deterministic structural check — read-only)"
    ),
}

# ---------------------------------------------------------------------------
# The three shipped contracts
# ---------------------------------------------------------------------------

_HYPOTHESIS = SpecialistContract(
    specialist_id="AIMA-HYPOTHESIS-DRAFT",
    purpose=(
        "تبدیل پرسش پژوهش به پیش‌نویس‌های فرضیه ساختاریافته با شرایط ابطال "
        "صریح — صرفاً مشاوره‌ای؛ هیچ محاسبه مالی و هیچ تغییر وضعیت تولید."
    ),
    capability="hypothesis_draft",
    allowed_tools=("invalidation_completeness_check",),
    input_schema_ref="radar.schema.aima.hypothesis_input.v1",
    output_schema_ref="radar.schema.aima.hypothesis_output.v1",
    authority_boundary=(
        "ADVISORY_ONLY: drafts hypotheses with explicit invalidation "
        "conditions; never computes financial truth, never mutates "
        "production, never approves or promotes anything"
    ),
    max_invocations_per_run=2,
    timeout_seconds=30,
    trace_prefix="aima_hypo",
    failure_behavior="RETRY_WITHIN_BUDGET",
    measurable_benefit_ref="docs/active/AIMA_C_EXECUTION_RECORD.md#wp-c-specialists",
    coordination_cost_note=(
        "one bounded call per run (ceiling 2), artifact-first input/output, "
        "no peer-to-peer state negotiation"
    ),
)

_INTERPRETATION = SpecialistContract(
    specialist_id="AIMA-INTERPRETATION",
    purpose=(
        "تفسیر ساختاریافته و قطعیِ نتایج شاخه‌های مصرف‌شده — فقط از روی "
        "پayload artifact-first می‌خواند؛ هیچ واقعیت جدیدی نمی‌سازد."
    ),
    capability="interpretation",
    allowed_tools=("trust_cap_lookup",),
    input_schema_ref="radar.schema.aima.interpretation_input.v1",
    output_schema_ref="radar.schema.aima.interpretation_output.v1",
    authority_boundary=(
        "ADVISORY_ONLY: interprets ONLY the consumed BranchResults it was "
        "handed; never invents facts, never touches financial engines' "
        "authority, never mutates production"
    ),
    max_invocations_per_run=2,
    timeout_seconds=30,
    trace_prefix="aima_interp",
    failure_behavior="RETRY_WITHIN_BUDGET",
    measurable_benefit_ref="docs/active/AIMA_C_EXECUTION_RECORD.md#wp-c-specialists",
    coordination_cost_note=(
        "reads only its declared consumes (artifact-first), one bounded "
        "call per consumed artifact set, no cross-branch negotiation"
    ),
)

_LEARNING_CHALLENGE = SpecialistContract(
    specialist_id="AIMA-LEARNING-CHALLENGE",
    purpose=(
        "به‌چالش‌کشیدن نتایج مصرف‌شده: تشخیص تکرار/سندیکا، فقدان شرط ابطال، "
        "و کف اعتماد — خروجی فقط یادداشت چالش؛ حکم مالی صادر نمی‌کند."
    ),
    capability="learning_challenge",
    allowed_tools=("duplicate_branch_detection", "invalidation_completeness_check"),
    input_schema_ref="radar.schema.aima.learning_challenge_input.v1",
    output_schema_ref="radar.schema.aima.learning_challenge_output.v1",
    authority_boundary=(
        "ADVISORY_ONLY: challenges consumed results (duplicates, missing "
        "invalidations, trust caps); never overrules deterministic "
        "evaluators, never mutates production"
    ),
    max_invocations_per_run=2,
    timeout_seconds=30,
    trace_prefix="aima_learn",
    failure_behavior="RETRY_WITHIN_BUDGET",
    measurable_benefit_ref="docs/active/AIMA_C_EXECUTION_RECORD.md#wp-c-specialists",
    coordination_cost_note=(
        "single pass over consumed results per invocation, deterministic "
        "and bounded; no state shared across runs"
    ),
)


def shipped_specialist_contracts() -> tuple[SpecialistContract, ...]:
    """The three approved specialists, in canonical order."""
    return (_HYPOTHESIS, _INTERPRETATION, _LEARNING_CHALLENGE)


def shipped_capability_registry() -> CapabilityRegistry:
    """Build the default capability registry (append-only, versioned)."""
    registry = CapabilityRegistry()
    for contract in shipped_specialist_contracts():
        registry = registry.with_specialist(contract)
    return registry


# ---------------------------------------------------------------------------
# Honest posture record (consumed by the API surface)
# ---------------------------------------------------------------------------

class SpecialistPosture(BaseModel):
    """One specialist's honest posture row."""

    specialist_id: str
    capability: str
    authority_boundary: str
    allowed_tools: tuple[str, ...]
    max_invocations_per_run: int
    timeout_seconds: int
    interaction_pattern: str


def shipped_specialist_posture() -> tuple[SpecialistPosture, ...]:
    return tuple(
        SpecialistPosture(
            specialist_id=c.specialist_id,
            capability=c.capability,
            authority_boundary=c.authority_boundary,
            allowed_tools=c.allowed_tools,
            max_invocations_per_run=c.max_invocations_per_run,
            timeout_seconds=c.timeout_seconds,
            interaction_pattern=c.interaction_pattern,
        )
        for c in shipped_specialist_contracts()
    )
