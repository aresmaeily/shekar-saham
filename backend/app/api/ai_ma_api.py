"""AI-MA governed orchestration HTTP surface (WAVE-AB3; WP-C, 2026-11-08).

Additive router — ``/api/v10/aima``. The governed multi-agent runtime's
posture and orchestration endpoints. Bounded, honest, synthetic/paper-only:

- The runtime behind this router executes the THREE shipped advisory
  specialists (hypothesis-draft / interpretation / learning-challenge) over
  a FIXED bounded plan — no client-supplied plan, no arbitrary specialists,
  no dynamic agent spawning (arch rule 6). Executors are deterministic and
  synthetic-safe: no network, no LLM, no production mutation.
- Every step's authority boundary is ADVISORY_ONLY: specialists never alter
  financial truth, never approve or promote anything, and deterministic
  synthesis stays pinned DETERMINISTIC_ONLY.
- The autonomy ceiling (L2) is enforced INSIDE the runtime
  (``assert_autonomy_permitted``); this endpoint mints L1 runs only.
- Trace + branch results are returned verbatim as the honest record; nothing
  is persisted, nothing is ledgered, nothing is promoted (an AI-2 posture
  is untouched; AI2_ENABLED stays irrelevant here because no model is
  invoked at all).
- No background task, no network client, no clock read beyond the injected
  runtime clock (deterministic monotonic); output is deterministic for a
  given question.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.domain.ai_ma_specialists import (
    TOOL_DESCRIPTIONS,
    shipped_capability_registry,
    shipped_specialist_posture,
)
from app.domain.run_governance import (
    RunContext,
    RunProvenance,
    missing_required_provenance,
)
from app.services.ai_ma_specialist_executors import shipped_specialist_executors
from app.services.multi_agent_runtime import (
    MultiAgentRuntime,
    SpecialistExecutorRegistry,
)

router = APIRouter(prefix="/api/v10/aima", tags=["ai-ma"])

_QUESTION_MAX = 300
_RUN_KIND = "AI_MA_ORCHESTRATION"
_POLICY_VERSION = "radar-policy-1"
_AUTONOMY_LEVEL = "L1"  # bounded advisory orchestration; ceiling L2 enforced in-runtime


class OrchestrateBody(BaseModel):
    """The ONLY client input: the research question.

    The plan shape is fixed server-side (hypothesis → interpretation →
    challenge); the client cannot inject steps, specialists, budgets or
    timeouts. This keeps the HTTP surface contract-first and bounded.
    """

    question: str = Field(min_length=3, max_length=_QUESTION_MAX)


def _honesty_envelope() -> Dict[str, Any]:
    return {
        "advisory_only": "all specialists are advisory; nothing here computes financial truth",
        "synthetic_paper_only": "execution domain is SYNTHETIC_OR_PAPER; no live data, no LLM, no provider call",
        "no_production_mutation": "specialists cannot mutate production state by construction",
        "fixed_plan": "plan shape is fixed server-side (hypothesis → interpretation → challenge); no client-supplied plans",
        "no_agent_spawning": "AGENT_AS_TOOL only; no autonomous agent spawning (arch rule 6)",
        "deterministic_synthesis": "synthesis is pinned DETERMINISTIC_ONLY by the runtime",
        "autonomy_ceiling": "L2 enforced inside the runtime via assert_autonomy_permitted; this API mints L1 runs only",
        "no_persistence": "branch results and trace are returned verbatim and not persisted or ledgered",
    }


def _build_fixed_plan(run_id: str, question: str):
    from app.domain.multi_agent import OrchestrationPlan, OrchestrationStep

    steps = (
        OrchestrationStep(
            step_id="s1_hypothesis",
            specialist_id="AIMA-HYPOTHESIS-DRAFT",
            capability="hypothesis_draft",
            produces="radar.artifact.aima.s1_hypothesis.v1",
            notes=f"question:{question}",
        ),
        OrchestrationStep(
            step_id="s2_interpretation",
            specialist_id="AIMA-INTERPRETATION",
            capability="interpretation",
            produces="radar.artifact.aima.s2_interpretation.v1",
            depends_on=("s1_hypothesis",),
            consumes=("radar.artifact.aima.s1_hypothesis.v1",),
        ),
        OrchestrationStep(
            step_id="s3_challenge",
            specialist_id="AIMA-LEARNING-CHALLENGE",
            capability="learning_challenge",
            produces="radar.artifact.aima.s3_challenge.v1",
            depends_on=("s1_hypothesis", "s2_interpretation"),
            consumes=(
                "radar.artifact.aima.s1_hypothesis.v1",
                "radar.artifact.aima.s2_interpretation.v1",
            ),
        ),
    )
    return OrchestrationPlan(
        plan_id=f"{run_id}-plan",
        run_id=run_id,
        steps=steps,
        policy_version=_POLICY_VERSION,
        max_parallel=1,  # the fixed plan is a chain; parallelism is moot
    )


@router.get("/posture")
async def aima_posture() -> Dict[str, Any]:
    """Honest AI-MA posture (read-only; always callable)."""
    registry = shipped_capability_registry()
    return {
        "ok": True,
        "registry_version": registry.registry_version,
        "specialists": [p.model_dump(mode="json") for p in shipped_specialist_posture()],
        "deterministic_tools": {name: TOOL_DESCRIPTIONS[name] for name in TOOL_DESCRIPTIONS},
        "honesty": _honesty_envelope(),
    }


@router.post("/orchestrate")
async def aima_orchestrate(body: OrchestrateBody) -> Dict[str, Any]:
    """Run the fixed bounded advisory plan and return the honest record.

    Deterministic: the same question yields the same run record modulo the
    minted run id/uuid. Bounded: 3 steps, per-specialist invocation ceilings
    and timeouts from the shipped contracts, one bounded retry per step
    (RETRY_WITHIN_BUDGET) — all enforced inside the runtime.
    """
    question = body.question.strip()
    run_id = f"aima-{uuid.uuid4().hex[:12]}"
    started = datetime.now(timezone.utc)
    context = RunContext(
        run_id=run_id,
        run_kind=_RUN_KIND,
        autonomy_level=_AUTONOMY_LEVEL,
        policy_version=_POLICY_VERSION,
        created_at_utc=started,
        notes=f"advisory orchestration for research question ({_QUESTION_MAX}-bounded)",
    )
    plan = _build_fixed_plan(run_id, question)

    contracts = shipped_capability_registry()
    executors = shipped_specialist_executors(contracts)
    registry = SpecialistExecutorRegistry(contracts, executors)

    runtime = MultiAgentRuntime()  # real monotonic clock; timeouts are bounded
    result = await runtime.execute_plan(plan, registry, context)
    finished = datetime.now(timezone.utc)

    provenance = RunProvenance(
        run_id=run_id,
        policy_version=_POLICY_VERSION,
        started_at_utc=started,
        finished_at_utc=finished,
    )
    acceptance_missing = list(missing_required_provenance(context, provenance))

    steps_payload = []
    for branch in result.results:
        steps_payload.append(
            {
                "step_id": branch.step_id,
                "specialist_id": branch.specialist_id,
                "status": branch.status,
                "summary": branch.summary,
                "failure_code": branch.failure_code,
                "branch_id": branch.branch_id,
            }
        )
    trace_payload = [
        {
            "step_id": e.step_id,
            "kind": e.kind,
            "detail": e.detail,
        }
        for e in result.trace.events
    ]
    return {
        "ok": True,
        "run_id": result.run_id,
        "plan_id": result.plan_id,
        "terminated": result.terminated,
        "termination_reason": result.termination_reason,
        "waves_executed": result.waves_executed,
        "waves_total": result.waves_total,
        "steps": steps_payload,
        "trace": trace_payload,
        "governance": {
            "run_kind": _RUN_KIND,
            "autonomy_level": _AUTONOMY_LEVEL,
            "policy_version": _POLICY_VERSION,
            "provenance_missing": acceptance_missing,
            "governed_acceptance_blocked": bool(acceptance_missing),
        },
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "honesty": _honesty_envelope(),
    }
