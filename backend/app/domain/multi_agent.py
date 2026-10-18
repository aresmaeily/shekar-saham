"""Multi-agent runtime contract layer for RADAR BOURSE (AI-MA-C).

Corpus loci (2026-10-02 amendment corpus, byte-verified):
- 02_EXECUTION_ROADMAP lines 55–81 (AI-MA-1..6): thin central orchestrator;
  capability registry + specialist contract; first/second bounded
  specialists; bounded parallel execution; artifact-first branch exchange;
  tracing, observability, failure isolation. "No fixed agent count. No
  peer-to-peer backbone. No autonomous spawning."
- 02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE rules 1–12 + §Complexity budget +
  §Agent qualification + §"A new runtime agent requires…" + §Failure model.
- 03_AI_GOVERNANCE_BOUNDARIES §Orchestrator / §Specialist / §Autonomy.
- D-AI-20 (orchestrator control, not peer-to-peer), D-AI-21 (agent-as-tool
  default; handoff requires justification), D-AI-23 (artifact-first), D-AI-24
  (bounded parallelism), D-AI-17/18 (no fixed agent count; roles are lenses).

Scope: CONTRACT LAYER ONLY (pre-G2 class, `02` line 202). No orchestrator
runtime, no specialist runtime, no threads/processes, no LLM, no scheduler,
no network. Reuses the AI1-GC canonical run identity (`RunContext`,
`ArtifactRef`) and the AI2-F budget discipline. One trace fabric, one
artifact protocol, one policy authority (02-product §Complexity budget).

Engineering-authority notes (05 §Engineering authority; choices not defined
by the corpus text, documented per the AI1-GC ambiguity-note precedent):
- the fan-out ceiling value (``MAX_PARALLEL_BRANCHES``) is an engineering
  bound, not a corpus number; the corpus only requires parallelism to be
  bounded (D-AI-24);
- peer-addressing refusal is the structural encoding of "no peer-to-peer
  backbone" (02:81; D-AI-20): BranchResults may only be addressed to the
  orchestrator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.run_governance import ArtifactRef

#: Engineering bound for D-AI-24 bounded parallelism (see module notes).
MAX_PARALLEL_BRANCHES = 4
#: Complexity budget: two agent levels maximum (02-product rule 4).
MAX_HIERARCHY_DEPTH = 2

InteractionPattern = Literal["AGENT_AS_TOOL", "HANDOFF"]
SpecialistFailureBehavior = Literal["FAIL_CLOSED", "DEGRADE", "RETRY_WITHIN_BUDGET"]


# ---------------------------------------------------------------------------
# AI-MA-2 — specialist contract + capability registry
# ---------------------------------------------------------------------------


class SpecialistContract(BaseModel):
    """Governed specialist contract (03 §Specialist; 02-product admission rules).

    Every required admission attribute is explicit: distinct purpose and
    capability, allowed tools, schema references, authority boundary,
    budget/timeout, trace identity, failure behavior. Agent-as-tool is the
    default interaction pattern; HANDOFF requires a written justification
    (D-AI-21). ``owner_change_record`` is required when the specialist is
    flagged consequential (owner-approved change record, 02-product).
    """

    model_config = ConfigDict(frozen=True)

    specialist_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    purpose: str = Field(min_length=1, max_length=1000)
    capability: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*$")
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    input_schema_ref: str = Field(min_length=1, max_length=256)
    output_schema_ref: str = Field(min_length=1, max_length=256)
    authority_boundary: str = Field(min_length=1, max_length=1000)
    max_invocations_per_run: int = Field(ge=1, le=16)
    timeout_seconds: int = Field(ge=1, le=3600)
    trace_prefix: str = Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
    failure_behavior: SpecialistFailureBehavior
    interaction_pattern: InteractionPattern = "AGENT_AS_TOOL"
    handoff_justification: str | None = None
    measurable_benefit_ref: str = Field(min_length=1, max_length=256)
    coordination_cost_note: str = Field(min_length=1, max_length=1000)
    consequential: bool = False
    owner_change_record: str | None = None

    @field_validator("allowed_tools", "measurable_benefit_ref")
    @classmethod
    def _shape(cls, v):
        return v

    @field_validator("allowed_tools")
    @classmethod
    def _distinct_tools(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("allowed_tools_duplicates")
        return v

    @model_validator(mode="after")
    def _admission_rules(self) -> "SpecialistContract":
        if self.interaction_pattern == "HANDOFF" and not (
            self.handoff_justification and self.handoff_justification.strip()
        ):
            raise ValueError("handoff_requires_justification")
        if self.interaction_pattern == "AGENT_AS_TOOL" and self.handoff_justification:
            raise ValueError("agent_as_tool_cannot_carry_handoff_justification")
        if self.consequential and not self.owner_change_record:
            raise ValueError("consequential_specialist_requires_owner_change_record")
        return self


class CapabilityRegistry:
    """Append-only registry of specialist contracts (AI-MA-2).

    Same discipline as the P0-AMD-1 ``SourceRegistry``: NEW capability
    appends and bumps the version; byte-identical re-registration is an
    idempotent no-op; conflicting re-registration is rejected. Capability
    names are distinct by construction — a new specialist MUST bring a
    distinct capability (02-product admission rules). No fixed count.
    """

    def __init__(self, entries: tuple[SpecialistContract, ...] = (), version: int = 1) -> None:
        self._entries: tuple[SpecialistContract, ...] = entries
        self._version = version

    @property
    def entries(self) -> tuple[SpecialistContract, ...]:
        return self._entries

    @property
    def registry_version(self) -> int:
        return self._version

    def get(self, specialist_id: str) -> SpecialistContract | None:
        for e in self._entries:
            if e.specialist_id == specialist_id:
                return e
        return None

    def resolve(self, capability: str) -> SpecialistContract | None:
        """Deterministic capability → specialist lookup (orchestrator's
        specialist-selection input; 03 §Orchestrator)."""
        for e in self._entries:
            if e.capability == capability:
                return e
        return None

    def with_specialist(self, contract: SpecialistContract) -> "CapabilityRegistry":
        existing = self.get(contract.specialist_id)
        if existing is not None:
            if existing == contract:
                return self
            raise ValueError("specialist_registry_conflict")
        if self.resolve(contract.capability) is not None:
            raise ValueError("capability_not_distinct")
        return CapabilityRegistry(
            self._entries + (contract,), version=self._version + 1
        )


# ---------------------------------------------------------------------------
# AI-MA-1 — thin orchestrator decomposition plan
# ---------------------------------------------------------------------------


class OrchestrationStep(BaseModel):
    """One delegated step of an orchestration plan (03 §Orchestrator).

    A step delegates to a SPECIALIST only — hierarchy depth stays at two
    (02-product rule 4); a step cannot target another orchestrator. Steps
    consume and produce artifact references (D-AI-23), never inline
    payloads.
    """

    model_config = ConfigDict(frozen=True)

    step_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    specialist_id: str = Field(min_length=1, max_length=128)
    capability: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*$")
    consumes: tuple[str, ...] = ()
    produces: str = Field(min_length=1, max_length=256)
    depends_on: tuple[str, ...] = ()
    notes: str = ""

    @field_validator("depends_on")
    @classmethod
    def _no_self_dependency(cls, v: tuple[str, ...], info) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("depends_on_duplicates")
        step_id = info.data.get("step_id")
        if step_id is not None and step_id in v:
            raise ValueError("step_cannot_depend_on_itself")
        return v

    @model_validator(mode="after")
    def _two_level_depth(self) -> "OrchestrationStep":
        if self.specialist_id.startswith("orchestrator:"):
            raise ValueError("hierarchy_depth_exceeds_two_levels")
        return self


class OrchestrationPlan(BaseModel):
    """Thin orchestrator decomposition of ONE governed run (AI-MA-1).

    Bound to exactly one canonical RunContext (02-product rule 10); the
    plan itself computes nothing and owns no financial truth (03
    §Orchestrator). Deterministic validation: acyclicity, bounded fan-out
    (D-AI-24 ceiling), dependencies must reference steps in the plan.
    """

    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=128)
    steps: tuple[OrchestrationStep, ...] = Field(min_length=1)
    max_parallel: int = Field(default=2, ge=1, le=MAX_PARALLEL_BRANCHES)
    policy_version: str = Field(min_length=1)
    notes: str = ""

    @field_validator("steps")
    @classmethod
    def _distinct_step_ids(cls, v: tuple[OrchestrationStep, ...]) -> tuple[OrchestrationStep, ...]:
        ids = [s.step_id for s in v]
        if len(set(ids)) != len(ids):
            raise ValueError("step_ids_duplicates")
        return v

    @model_validator(mode="after")
    def _deterministic_graph_checks(self) -> "OrchestrationPlan":
        ids = {s.step_id for s in self.steps}
        for s in self.steps:
            unknown = set(s.depends_on) - ids
            if unknown:
                raise ValueError("dependency_references_unknown_step")
        # Deterministic cycle detection (iterative DFS, no recursion on input).
        graph = {s.step_id: s.depends_on for s in self.steps}
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {k: WHITE for k in graph}
        for start in graph:
            if color[start] != WHITE:
                continue
            stack = [(start, iter(graph[start]))]
            color[start] = GRAY
            while stack:
                node, it = stack[-1]
                advanced = False
                for dep in it:
                    if color[dep] == GRAY:
                        raise ValueError("plan_has_dependency_cycle")
                    if color[dep] == WHITE:
                        color[dep] = GRAY
                        stack.append((dep, iter(graph[dep])))
                        advanced = True
                        break
                if not advanced:
                    color[node] = BLACK
                    stack.pop()
        return self


def execution_waves(plan: OrchestrationPlan) -> tuple[tuple[str, ...], ...]:
    """Deterministic bounded-parallel schedule (AI-MA-4; D-AI-24).

    Returns topological waves of step ids: a wave contains exactly the
    steps whose dependencies are all satisfied by earlier waves. The wave
    width never exceeds ``plan.max_parallel`` — waves are SPLIT when a
    topological level is wider than the ceiling (never merged, never
    reordered inside a level). Pure function; clock-free.
    """
    remaining = {s.step_id: set(s.depends_on) for s in plan.steps}
    order_index = {s.step_id: i for i, s in enumerate(plan.steps)}
    done: set[str] = set()
    waves: list[tuple[str, ...]] = []
    while remaining:
        ready = sorted(
            (sid for sid, deps in remaining.items() if deps <= done),
            key=lambda sid: order_index[sid],
        )
        if not ready:
            raise ValueError("plan_has_dependency_cycle")
        for chunk_start in range(0, len(ready), plan.max_parallel):
            chunk = tuple(ready[chunk_start : chunk_start + plan.max_parallel])
            waves.append(chunk)
            done.update(chunk)
            for sid in chunk:
                remaining.pop(sid)
    return tuple(waves)


# ---------------------------------------------------------------------------
# AI-MA-5 — artifact-first branch exchange (no peer-to-peer backbone)
# ---------------------------------------------------------------------------


class BranchResult(BaseModel):
    """A specialist branch's result, addressed TO the orchestrator.

    Artifact-first (D-AI-23): the large result lives behind ``artifact``;
    at most a small explicit ``summary`` may travel inline, and only when
    ``summary_only`` is declared. Peer addressing is structurally
    impossible: ``addressed_to`` must be the orchestrator of the same run
    (D-AI-20; 02:81 "No peer-to-peer backbone").
    """

    model_config = ConfigDict(frozen=True)

    branch_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=128)
    step_id: str = Field(min_length=1, max_length=128)
    specialist_id: str = Field(min_length=1, max_length=128)
    addressed_to: str = Field(min_length=1, max_length=128)
    status: Literal["SUCCEEDED", "FAILED", "DEGRADED"]
    artifact: ArtifactRef | None = None
    summary: str = ""
    summary_only: bool = False
    failure_code: str | None = None
    completed_at_utc: datetime

    @field_validator("completed_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _exchange_rules(self) -> "BranchResult":
        if self.addressed_to != f"orchestrator:{self.run_id}":
            raise ValueError("peer_to_peer_addressing_refused")
        if self.status == "SUCCEEDED":
            if self.summary_only:
                if not self.summary:
                    raise ValueError("summary_only_result_requires_summary")
            elif self.artifact is None:
                raise ValueError("artifact_first_exchange_requires_artifact")
            if self.failure_code is not None:
                raise ValueError("succeeded_result_cannot_carry_failure_code")
        else:
            if not self.failure_code:
                raise ValueError("failed_result_requires_failure_code")
            if self.artifact is not None or self.summary_only:
                raise ValueError("failed_result_cannot_carry_payload")
        return self


# ---------------------------------------------------------------------------
# AI-MA-6 — one trace fabric + failure isolation
# ---------------------------------------------------------------------------

TraceKind = Literal[
    "PLAN_CREATED",
    "STEP_DISPATCHED",
    "STEP_SUCCEEDED",
    "STEP_FAILED",
    "STEP_DEGRADED",
    "RUN_TERMINATED",
]


class TraceEvent(BaseModel):
    """One event on the single trace fabric (02-product rule 12).

    Every agent/tool/handoff/artifact/memory operation is traceable to
    run_id; trace events carry the specialist's trace prefix so the fabric
    stays one fabric (02-product §Complexity budget).
    """

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=128)
    step_id: str | None = None
    trace_prefix: str = Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
    kind: TraceKind
    at_utc: datetime
    detail: str = Field(default="", max_length=500)
    artifact_id: str | None = None

    @field_validator("at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


class TraceLog:
    """Append-only, single trace fabric (in-memory; no persistence here)."""

    def __init__(self, events: tuple[TraceEvent, ...] = ()) -> None:
        self._events: tuple[TraceEvent, ...] = events

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return self._events

    def append(self, event: TraceEvent) -> "TraceLog":
        if any(e.event_id == event.event_id for e in self._events):
            if any(e == event for e in self._events if e.event_id == event.event_id):
                return self
            raise ValueError("trace_event_conflict")
        return TraceLog(self._events + (event,))

    def for_run(self, run_id: str) -> tuple[TraceEvent, ...]:
        return tuple(e for e in self._events if e.run_id == run_id)


def isolate_failure(
    failed_step_id: str,
    plan: OrchestrationPlan,
    results: "tuple[BranchResult, ...]",
) -> Literal["CONTINUE_OTHER_BRANCHES", "TERMINATE_RUN"]:
    """Deterministic failure-isolation decision (AI-MA-6; 02-product §Failure model).

    A step whose output is consumed by another plan step is load-bearing:
    its failure terminates the run (dependents can never run honestly).
    An independent branch's failure is contained: the other branches
    continue and the failure is reported (02-product: specialists "must
    safely fail, degrade or retry"; no silent swallowing).
    """
    dependents = [
        s.step_id
        for s in plan.steps
        if failed_step_id in s.depends_on
    ]
    if dependents:
        return "TERMINATE_RUN"
    succeeded = {r.step_id for r in results if r.status == "SUCCEEDED"}
    if succeeded:
        return "CONTINUE_OTHER_BRANCHES"
    return "CONTINUE_OTHER_BRANCHES"
