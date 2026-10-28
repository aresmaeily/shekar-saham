"""AI-5 Proactive Intelligence — proactive-research job contracts for RADAR BOURSE.

Corpus loci (2026-10-02 amendment corpus, byte-verified import):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 92-95: "AI-5 — Proactive
  Intelligence: Scheduled/event-triggered bounded research with budget,
  observability, recovery and kill switch."
- 02 lines 155-156: governed scheduled/event-triggered monitoring of the
  configured source universe and approved watchlists; "Coverage gaps and
  inaccessible sources must be reported"; respect source terms, rate limits,
  resource budgets and kill switches.
- 02 line 186: "Cadence, thresholds and budgets require explicit
  configuration, observability, idempotency, retry ceilings and a kill
  switch." 02 line 203: live-data scans/backtests must not be run merely to
  prove a document change.
- 02 line 202: pre-G2 authorized class — bounded design, schema work,
  source-registry design, synthetic/paper tests and safe dry-run work only.
- AI4_AI7_P343_DEPENDENCY_MATRIX.md §AI-5: "Authorized NOW: contract
  extension only (e.g. proactive-research job contracts reusing the P0
  monitoring schema); scheduler runtime is owner-gated (D-AI-30 +
  cadence/budget approval)."
- 05 register D-AI-30 "DEFERRED UNTIL CORE STABILITY — Requires budget,
  observability, recovery and kill switch"; D-AI-38: monitoring outputs must
  state coverage, last successful retrieval, freshness, known gaps, source
  failures and unresolved conflicts; "Do not imply universal web coverage";
  05:200: D-AI-32..39 authorize no live behavior.
- 06 charter §9: every job needs idempotency, retry ceilings, run identity,
  audit trace, failure alert, kill switch; cadence must not be hard-coded
  before operational requirements and budgets are approved.
- 03 boundaries / D-AI-19: financial truth (backtest, WFO, forward test,
  metrics, risk) remains deterministic; AI research output is candidate
  material, never financial authority; no production mutation, no
  self-modifying logic.

Contract/domain ONLY (reuses the P0 monitoring schema by direct import —
no fork): no scheduler runs here, no trigger evaluation, nothing is
executed, nothing touches the network, no LLM call, no clock read. The kill
switch defaults to ENGAGED (fail-closed): a proactive-research job may not
run until explicitly released by configuration. ``production_mutation`` and
``universal_coverage_claimed`` are structurally unrepresentable as True.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.monitoring import (
    BudgetSpec,
    JobFailureState,
    KillSwitchState,
    RetryPolicy,
    TriggerSpec,
    effective_run_permission,
)
from app.domain.run_governance import (
    AutonomyLevel,
    RunContext,
    RunProvenance,
    assert_autonomy_permitted,
    missing_required_provenance,
)

#: Structural invariants (D-AI-19/03; D-AI-38) — unrepresentable states.
PRODUCTION_MUTATION_ALLOWED: Literal[False] = False
FINANCIAL_AUTHORITY = Literal["DETERMINISTIC_ONLY"]
OUTPUT_BINDING = Literal["EPISODIC_RESEARCH_ARTIFACT"]

#: Bounded research-question set per job (defensive ceiling; owner sets the
#: operative budget at construction — no cadence or volume value is baked in).
MAX_RESEARCH_QUESTIONS = 16
MAX_TRACKED_ARTIFACT_IDS = 32


class ProactiveResearchJobSpec(BaseModel):
    """Immutable specification of one governed proactive-research job.

    Composes the P0 monitoring job schema (trigger/retry/budget/kill-switch)
    with research-specific honesty and authority fields. Construction does
    NOT schedule, evaluate or execute anything; it only freezes the declared
    contract. Cadence lives in the owner-configured ``trigger`` — no
    schedule value exists in this module.
    """

    model_config = ConfigDict(frozen=True)

    research_job_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    trigger: TriggerSpec
    retry_policy: RetryPolicy
    budget: BudgetSpec
    research_questions: tuple[str, ...] = Field(min_length=1, max_length=MAX_RESEARCH_QUESTIONS)
    evidence_ref: str = Field(min_length=1)
    observability_ref: str = Field(min_length=1)
    alerting_ref: str = Field(min_length=1)
    output_binding: OUTPUT_BINDING = "EPISODIC_RESEARCH_ARTIFACT"
    production_mutation: Literal[False] = False
    financial_authority: FINANCIAL_AUTHORITY = "DETERMINISTIC_ONLY"
    coverage_honesty_required: Literal[True] = True
    kill_switch: KillSwitchState = "ENGAGED"
    notes: str = ""

    @field_validator("research_questions")
    @classmethod
    def _distinct_nonempty_questions(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        # Explicit bounds: pydantic v2 does not apply min_length/max_length
        # to variadic tuples, so the ceiling is enforced here instead.
        if not 1 <= len(v) <= MAX_RESEARCH_QUESTIONS:
            raise ValueError("research_questions_count_out_of_bounds")
        if any(not q.strip() for q in v):
            raise ValueError("research_questions_must_be_nonempty")
        if len(set(v)) != len(v):
            raise ValueError("research_questions_duplicates")
        return v

    def run_allowed(self) -> bool:
        """Deterministic permission-to-run check (policy, not execution)."""
        return self.kill_switch == "RELEASED"


class ProactiveResearchJobState(BaseModel):
    """Operational state of a proactive-research job (honesty fields).

    Mirrors the P0 ``MonitoringJobState`` consistency rules: a HEALTHY state
    requires zero consecutive failures and a HALTED state requires a sent
    failure alert. Recovery from HALTED is an explicit owner action, never
    an automatic retry.
    """

    model_config = ConfigDict(frozen=True)

    research_job_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    last_success_utc: datetime | None = None
    last_attempt_utc: datetime | None = None
    consecutive_failures: int = Field(default=0, ge=0)
    failure_state: JobFailureState = "HEALTHY"
    failure_alert_sent: bool = False
    coverage_report_ref: str | None = None
    last_run_artifact_ids: tuple[str, ...] = ()
    notes: str = ""

    @field_validator("last_success_utc", "last_attempt_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("last_run_artifact_ids")
    @classmethod
    def _bounded_distinct_artifacts(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(v) > MAX_TRACKED_ARTIFACT_IDS:
            raise ValueError("last_run_artifact_ids_exceeds_ceiling")
        if len(set(v)) != len(v):
            raise ValueError("last_run_artifact_ids_duplicates")
        return v

    @model_validator(mode="after")
    def _state_consistency(self) -> "ProactiveResearchJobState":
        if self.failure_state == "HEALTHY" and self.consecutive_failures != 0:
            raise ValueError("healthy_state_requires_zero_consecutive_failures")
        if self.failure_state == "HALTED" and not self.failure_alert_sent:
            raise ValueError("halted_state_requires_failure_alert")
        return self


class CoverageFreshnessStatement(BaseModel):
    """D-AI-38 honesty record for a proactive-research cycle.

    Every monitoring/research output must state source coverage, last
    successful retrieval, freshness, known gaps, source failures and
    unresolved conflicts, and must NOT imply universal web coverage. The
    universal-claim state is structurally unrepresentable; an incomplete
    coverage declaration MUST list at least one known gap.
    """

    model_config = ConfigDict(frozen=True)

    research_job_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    coverage_declared: bool
    coverage_complete: bool
    universal_coverage_claimed: Literal[False] = False
    last_successful_retrieval_utc: datetime | None = None
    freshness_age_seconds: float | None = Field(default=None, ge=0)
    known_gaps: tuple[str, ...] = ()
    source_failures: tuple[str, ...] = ()
    unresolved_conflicts: tuple[str, ...] = ()
    notes: str = ""

    @field_validator("last_successful_retrieval_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @model_validator(mode="after")
    def _honesty_consistency(self) -> "CoverageFreshnessStatement":
        if not self.coverage_complete and not self.known_gaps:
            raise ValueError("incomplete_coverage_requires_known_gaps")
        return self


def effective_research_run_permission(
    spec: ProactiveResearchJobSpec,
    state: ProactiveResearchJobState,
    context: RunContext,
    provenance: RunProvenance,
    *,
    autonomy_ceiling: AutonomyLevel,
) -> tuple[bool, tuple[str, ...]]:
    """Deterministic permission decision for a proactive-research cycle.

    Returns ``(permitted, refusals)`` and NEVER executes anything. A cycle is
    permitted only when ALL of the following hold:

    1. the P0 monitoring permission semantics pass (kill switch RELEASED,
       state not HALTED, matching job id — reused via
       :func:`app.domain.monitoring.effective_run_permission` through the
       spec/state mapping below);
    2. run identity/provenance binding is complete (canonical
       ``missing_required_provenance``, research additionally requires
       ``dataset_version``);
    3. the run's recorded autonomy level does not exceed the declared
       ceiling (canonical ``assert_autonomy_permitted``).

    Each failed condition contributes a stable refusal tag so callers can
    record the reason verbatim in audit evidence.
    """

    refusals: list[str] = []

    # 1. Kill switch / failure state / job-id match (P0 semantics, mapped).
    spec_view = _SpecView(spec)
    state_view = _StateView(state)
    if not effective_run_permission(spec_view, state_view, job_id_must_match=True):
        if spec.kill_switch != "RELEASED":
            refusals.append("kill_switch_engaged")
        if state.failure_state == "HALTED":
            refusals.append("failure_state_halted")
        if spec.research_job_id != state.research_job_id:
            refusals.append("job_id_mismatch")

    # 2. Canonical provenance completeness (research requires dataset_version).
    missing = missing_required_provenance(context, provenance, additionally_required=("dataset_version",))
    if missing:
        refusals.extend(f"missing_provenance:{name}" for name in missing)

    # 3. Autonomy ceiling (canonical guard; refusal tag instead of raise here).
    try:
        assert_autonomy_permitted(context, autonomy_ceiling)
    except ValueError:
        refusals.append("autonomy_level_exceeds_declared_ceiling")

    return (not refusals, tuple(refusals))


class _SpecView:
    """Structural adapter: maps the research spec onto the P0 spec surface
    (job_id/run_allowed) without copying or mutating anything."""

    __slots__ = ("job_id", "_spec")

    def __init__(self, spec: ProactiveResearchJobSpec) -> None:
        self.job_id = spec.research_job_id
        self._spec = spec

    def run_allowed(self) -> bool:
        return self._spec.run_allowed()


class _StateView:
    """Structural adapter onto the P0 state surface (job_id/failure_state)."""

    __slots__ = ("job_id", "failure_state")

    def __init__(self, state: ProactiveResearchJobState) -> None:
        self.job_id = state.research_job_id
        self.failure_state = state.failure_state
