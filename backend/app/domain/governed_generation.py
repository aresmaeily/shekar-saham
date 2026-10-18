"""AI-4 Governed Generation contract layer for RADAR BOURSE.

Corpus loci (2026-10-02 amendment corpus, byte-verified import):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 87-90: "AI-4 --- Governed
  Generation: AI-generated filters/indicators/strategy specifications only
  through sandbox -> deterministic evaluation -> lifecycle -> approval."
- 02 lines 158-159: hypotheses enter the governed research lifecycle "when a
  suitable deterministic evaluator exists"; "AI-generated filters, scoring
  rules, fundamental features, or software-change proposals remain candidates
  until isolated tests, evaluation gates and required human approval are
  passed. No self-modifying production logic."
- D-AI-10/D-AI-11 (05 register): bounded lifecycle mandatory; generated
  candidates only through sandbox/evaluation/lifecycle gates.
- D-AI-12/D-AI-13: no trading/production mutation/bypass; learning is
  evidence-based, not self-modifying production.
- D-AI-03/D-AI-05 (preserved): no production mutation without human approval;
  ExperimentLab production apply blocked.
- D-AI-19: financial truth, backtest, WFO, forward test, metrics, risk and
  statistical evaluation remain deterministic.
- 03_AI_GOVERNANCE_BOUNDARIES: AI may not auto-promote research, bypass
  gates, self-escalate permissions, self-modify budgets, or create
  self-modifying production logic (19-25); missing required provenance blocks
  governed acceptance (40); the Governor owns authorization, transition
  policy, run identity, provenance binding, budget/quota and audit
  integration and must not duplicate financial logic (42-47); autonomy
  ceiling and no silent escalation (78-83); acceptance requires provenance,
  failure-path evidence and an approval record (90-94).
- 00_OWNER_ROADMAP_DECISION lines 85-86: no self-modifying production logic;
  no broker order execution.
- 02 line 179: improvement proposals carry baseline, expected benefit,
  evidence, uncertainty, cost, risks, rollback plan and evaluation design;
  the system must not automatically change production, promote filters,
  alter permissions/budgets, or deploy software.
- 02 line 198: all governed actions carry traceable run identity, versions,
  human approval state and explicit limitations.
- 06 charter line 107: reproducible runs demonstrate preregistration,
  deterministic evaluation, holdout protection, versioned artifacts and
  approval gates.
- 02 line 202: pre-G2 authorized class — bounded design, schema work,
  synthetic/paper tests and safe dry-run work only.

Contract/domain only: frozen records, deterministic, clock-free (every
timestamp is passed in as an argument), no I/O, no network, no LLM, no
scheduler. The sandbox/evaluation EXECUTION runtime does not exist and is
post-G2 work; this module defines the admission/evaluation/lifecycle/
approval CONTRACTS only (pre-G2 authorized class).

Structural no-production-mutation guarantees (D-AI-03/05/12/13; 03:19-25):
- the lifecycle vocabulary contains NO production/applied/deployed state;
- the transition table has no edge to any such state;
- this module contains no apply/deploy/promote-to-production function;
- the sandbox record cannot express production contact;
- the evaluator binding cannot express a stochastic (LLM) evaluator;
- dataset origin is closed to SYNTHETIC/PAPER — LIVE is unrepresentable;
- software-change proposals must carry the 02:179 fields (incl. a rollback
  plan) or they cannot be admitted.

An APPROVED candidate remains an ADVISORY artifact awaiting a separate human
deployment decision; approval never mutates production by construction.
"""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.run_governance import (
    RunContext,
    RunProvenance,
    assert_autonomy_permitted,
    missing_required_provenance,
)

# ---------------------------------------------------------------------------
# Closed vocabularies (02:89-90 + 02:159; 02:202; D-AI-11)
# ---------------------------------------------------------------------------

#: Exactly the artifact kinds the corpus names for AI-4 (02:89-90 filters /
#: indicators / strategy specifications; 02:159 scoring rules, fundamental
#: features, software-change proposals). Closed Literal: unknown kinds are
#: unrepresentable by construction.
GeneratedCandidateKind = Literal[
    "FILTER",
    "INDICATOR",
    "STRATEGY_SPEC",
    "SCORING_RULE",
    "FUNDAMENTAL_FEATURE",
    "SOFTWARE_CHANGE_PROPOSAL",
]

#: Pre-G2 dataset scope (02:202 synthetic/paper class). LIVE is structurally
#: inexpressible — G2 blocks all real-data evaluation (02:201).
DatasetOrigin = Literal["SYNTHETIC", "PAPER"]

#: Candidate lifecycle states (D-AI-10/D-AI-11; 02:87-90). There is NO
#: production/applied/deployed state: approval terminates the lifecycle with
#: an advisory artifact; promotion to production is not expressible.
CandidateLifecycleState = Literal[
    "DRAFT",
    "SANDBOX_ADMITTED",
    "EVALUATED",
    "APPROVAL_PENDING",
    "APPROVED",
    "REJECTED",
]

#: Human approval decisions (02:159 "required human approval"). Subset of the
#: canonical ApprovalState vocabulary (run_governance); PENDING lives in the
#: lifecycle state APPROVAL_PENDING, never in this record.
CandidateApprovalDecision = Literal["APPROVED", "REJECTED"]

#: Verdict recorded by the deterministic evaluator (D-AI-19). The gate never
#: computes metric math or thresholds — that is deterministic financial truth
#: owned by the evaluator service (03:42-47).
EvaluationVerdict = Literal["PASS", "FAIL"]

#: Structural D-AI-19 marker: the only service class an evaluator binding can
#: declare. A stochastic/LLM evaluator is unrepresentable.
DeterministicServiceClass = Literal["DETERMINISTIC"]

BudgetVerdict = Literal["WITHIN_BUDGET", "BUDGET_EXHAUSTED"]

_ALLOWED_LIFECYCLE_STATES: frozenset[str] = frozenset(
    {
        "DRAFT",
        "SANDBOX_ADMITTED",
        "EVALUATED",
        "APPROVAL_PENDING",
        "APPROVED",
        "REJECTED",
    }
)

#: Transition policy (03 §Governor owns transition policy). Terminal states
#: have empty outgoing sets; no edge reaches any production-like state.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"SANDBOX_ADMITTED"}),
    "SANDBOX_ADMITTED": frozenset({"EVALUATED"}),
    "EVALUATED": frozenset({"APPROVAL_PENDING"}),
    "APPROVAL_PENDING": frozenset({"APPROVED", "REJECTED"}),
    "APPROVED": frozenset(),
    "REJECTED": frozenset(),
}


# ---------------------------------------------------------------------------
# Candidate record (02:159 "remain candidates"; 02:198 explicit limitations)
# ---------------------------------------------------------------------------


class SoftwareChangeProposalFields(BaseModel):
    """Mandatory content fields for SOFTWARE_CHANGE_PROPOSAL candidates.

    02:179 requires improvement proposals to carry baseline, expected
    benefit, evidence, uncertainty, cost, risks, rollback plan and
    evaluation design. All eight fields are mandatory and non-empty; a
    software-change proposal without a rollback plan cannot be admitted
    (D-AI-12/13 no-production-mutation discipline).
    """

    model_config = ConfigDict(frozen=True)

    baseline: str = Field(min_length=1)
    expected_benefit: str = Field(min_length=1)
    evidence_summary: str = Field(min_length=1)
    uncertainty: str = Field(min_length=1)
    cost: str = Field(min_length=1)
    risks: str = Field(min_length=1)
    rollback_plan: str = Field(min_length=1)
    evaluation_design: str = Field(min_length=1)


class GeneratedCandidate(BaseModel):
    """Immutable record of one AI-generated candidate artifact.

    The candidate is generated under a governed run (``run_id`` binds to the
    canonical RunContext; 02:198). A non-empty ``rationale`` is mandatory
    (explainable generation; 02:198 explicit limitations). The specification
    is versioned (06:107 versioned artifacts).
    """

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    kind: GeneratedCandidateKind
    specification: str = Field(min_length=1)
    spec_version: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    run_id: str = Field(min_length=1, max_length=128)
    hypothesis_id: str | None = None
    created_at_utc: datetime
    #: Mandatory only when kind == SOFTWARE_CHANGE_PROPOSAL (02:179); must be
    #: None for every other kind (kind-specific field discipline).
    proposal: SoftwareChangeProposalFields | None = None
    notes: str = ""

    @field_validator("created_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _kind_specific_proposal(self) -> "GeneratedCandidate":
        if self.kind == "SOFTWARE_CHANGE_PROPOSAL" and self.proposal is None:
            raise ValueError("software_change_proposal_requires_proposal_fields")
        if self.kind != "SOFTWARE_CHANGE_PROPOSAL" and self.proposal is not None:
            raise ValueError("proposal_fields_only_for_software_change_proposals")
        return self


# ---------------------------------------------------------------------------
# Sandbox admission (D-AI-11 "only through sandbox"; 02:202 synthetic/paper)
# ---------------------------------------------------------------------------


class SandboxBudgetSpec(BaseModel):
    """Structurally bounded sandbox ceilings (03 §Governor budget/quota).

    The ceiling VALUES are engineering-authority defaults with structural
    bounds; operational numbers are owner decisions at runtime integration
    (dependency matrix: "numeric sandbox budgets later at runtime
    integration"). No unbounded budget is expressible.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    max_evaluator_invocations: int = Field(ge=1, le=64)
    max_wall_seconds: int = Field(ge=1, le=86400)


class SandboxBudgetUsage(BaseModel):
    """Observable usage counters (deterministic inputs only, clock-free)."""

    model_config = ConfigDict(frozen=True)

    evaluator_invocations: int = Field(ge=0)
    wall_seconds: float = Field(ge=0.0)


def sandbox_budget_verdict(spec: SandboxBudgetSpec, usage: SandboxBudgetUsage) -> BudgetVerdict:
    """Deterministic, ceiling-inclusive budget decision (03 §Governor).

    Clock-free: ``usage.wall_seconds`` is measured by the caller and passed
    in; this function never reads a clock.
    """
    if (
        usage.evaluator_invocations >= spec.max_evaluator_invocations
        or usage.wall_seconds >= spec.max_wall_seconds
    ):
        return "BUDGET_EXHAUSTED"
    return "WITHIN_BUDGET"


class SandboxAdmissionRecord(BaseModel):
    """Sandbox-admission record for one candidate (D-AI-11; 02:89-90).

    Structural guarantees enforced at construction:
    - ``isolation_declared=False`` is refused (sandbox must declare
      isolation — 02:159 "isolated tests");
    - ``production_contact=True`` is refused (no production contact);
    - ``dataset_origin`` is closed to SYNTHETIC/PAPER (02:202; G2 discipline)
      — LIVE is unrepresentable;
    - ``dataset_version`` and ``policy_version`` are mandatory (03:40).
    """

    model_config = ConfigDict(frozen=True)

    admission_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    candidate_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    sandbox_id: str = Field(min_length=1, max_length=128)
    isolation_declared: bool
    production_contact: bool
    dataset_origin: DatasetOrigin
    dataset_version: str = Field(min_length=1)
    budget: SandboxBudgetSpec
    policy_version: str = Field(min_length=1)
    admitted_at_utc: datetime
    notes: str = ""

    @field_validator("admitted_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("isolation_declared")
    @classmethod
    def _isolation_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("sandbox_isolation_must_be_declared")
        return v

    @field_validator("production_contact")
    @classmethod
    def _no_production_contact(cls, v: bool) -> bool:
        if v:
            raise ValueError("sandbox_production_contact_forbidden")
        return v


# ---------------------------------------------------------------------------
# Deterministic evaluator binding (D-AI-11; D-AI-19; 02:158)
# ---------------------------------------------------------------------------


class DeterministicEvaluatorBinding(BaseModel):
    """Binding of a candidate kind to a deterministic evaluator service.

    Structural guarantees: ``service_class`` accepts only DETERMINISTIC
    (D-AI-19); the schema has NO model/prompt fields, so a stochastic or
    LLM-based evaluator is unrepresentable. ``evaluation_contract`` names the
    deterministic service (e.g. ``app.engines.filter_dsl.validate_filter``).
    """

    model_config = ConfigDict(frozen=True)

    evaluator_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    evaluator_version: str = Field(min_length=1)
    service_class: DeterministicServiceClass = "DETERMINISTIC"
    evaluates_kinds: tuple[GeneratedCandidateKind, ...] = Field(min_length=1)
    accepted_dataset_origins: tuple[DatasetOrigin, ...] = Field(min_length=1)
    evaluation_contract: str = Field(min_length=1)
    notes: str = ""

    @field_validator("evaluates_kinds", "accepted_dataset_origins")
    @classmethod
    def _distinct(cls, v: tuple) -> tuple:
        if len(set(v)) != len(v):
            raise ValueError("binding_members_duplicates")
        return v


class EvaluatorRegistry:
    """Immutable registry of deterministic evaluator bindings.

    Resolution is deterministic: registration order, first match wins.
    ``with_binding`` returns a NEW registry (additive; refuses duplicate
    evaluator ids) — existing bindings are never mutated.
    """

    def __init__(
        self,
        bindings: tuple[DeterministicEvaluatorBinding, ...] = (),
        version: int = 1,
    ) -> None:
        ids = [b.evaluator_id for b in bindings]
        if len(set(ids)) != len(ids):
            raise ValueError("evaluator_id_already_registered")
        self._bindings = tuple(bindings)
        self._version = version

    @property
    def bindings(self) -> tuple[DeterministicEvaluatorBinding, ...]:
        return self._bindings

    @property
    def registry_version(self) -> int:
        return self._version

    def get(self, evaluator_id: str) -> DeterministicEvaluatorBinding | None:
        for binding in self._bindings:
            if binding.evaluator_id == evaluator_id:
                return binding
        return None

    def resolve(self, kind: GeneratedCandidateKind) -> DeterministicEvaluatorBinding | None:
        """First binding that evaluates ``kind`` (deterministic order)."""
        for binding in self._bindings:
            if kind in binding.evaluates_kinds:
                return binding
        return None

    def with_binding(
        self, binding: DeterministicEvaluatorBinding
    ) -> "EvaluatorRegistry":
        if self.get(binding.evaluator_id) is not None:
            raise ValueError("evaluator_id_already_registered")
        return EvaluatorRegistry(
            bindings=self._bindings + (binding,), version=self._version + 1
        )


# ---------------------------------------------------------------------------
# Evaluation record (D-AI-11 "evaluation"; 06:107; 02:159 isolated tests)
# ---------------------------------------------------------------------------


class EvaluationMetric(BaseModel):
    """One deterministic metric value produced by the evaluator."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    value: float

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not isfinite(v):
            raise ValueError("metric_value_must_be_finite")
        return v


class CandidateEvaluationRecord(BaseModel):
    """Record of one deterministic evaluation of a sandbox-admitted candidate.

    ``preregistered`` and ``holdout_protected`` implement 06:107
    (preregistration, holdout protection); the gate refuses the transition to
    approval when either is undeclared or the verdict is FAIL (02:159
    "evaluation gates ... are passed").
    """

    model_config = ConfigDict(frozen=True)

    evaluation_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    candidate_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    admission_id: str = Field(min_length=1, max_length=128)
    evaluator_id: str = Field(min_length=1, max_length=128)
    evaluator_version: str = Field(min_length=1)
    dataset_origin: DatasetOrigin
    dataset_version: str = Field(min_length=1)
    metrics: tuple[EvaluationMetric, ...] = ()
    verdict: EvaluationVerdict
    preregistered: bool = False
    holdout_protected: bool = False
    artifact_refs: tuple[str, ...] = ()
    recorded_at_utc: datetime
    notes: str = ""

    @field_validator("recorded_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("metrics")
    @classmethod
    def _distinct_metrics(cls, v: tuple[EvaluationMetric, ...]) -> tuple[EvaluationMetric, ...]:
        names = [m.name for m in v]
        if len(set(names)) != len(names):
            raise ValueError("metric_names_duplicates")
        return v

    @field_validator("artifact_refs")
    @classmethod
    def _distinct_refs(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("artifact_refs_duplicates")
        return v


# ---------------------------------------------------------------------------
# Human approval record (02:159; 03:90-94 approval record)
# ---------------------------------------------------------------------------


class CandidateApprovalRecord(BaseModel):
    """Recorded human decision on one candidate.

    Same discipline as the canonical RunContext L4 rule: a decision requires
    a human principal (``decided_by``) AND a recorded decision reference
    (``approval_ref``). There is no function in this module that produces an
    approval record from a run or agent — auto-approval is structurally
    outside the contract surface (D-AI-03; 03:19-25).
    """

    model_config = ConfigDict(frozen=True)

    approval_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    candidate_id: str = Field(min_length=1, max_length=128)
    decision: CandidateApprovalDecision
    decided_by: str = Field(min_length=1)
    approval_ref: str = Field(min_length=1)
    decided_at_utc: datetime
    notes: str = ""

    @field_validator("decided_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


# ---------------------------------------------------------------------------
# Deterministic gate functions (empty tuple = permitted; else refusal codes)
# ---------------------------------------------------------------------------


def transition_candidate(
    current: str, target: str
) -> tuple[str, ...]:
    """Deterministic lifecycle transition check (D-AI-10/D-AI-11).

    Returns an empty tuple when the transition is allowed, otherwise an
    explicit refusal code. Unknown states are refused, never guessed.
    """
    if current not in _ALLOWED_LIFECYCLE_STATES or target not in _ALLOWED_LIFECYCLE_STATES:
        return ("unknown_lifecycle_state",)
    if target not in ALLOWED_TRANSITIONS[current]:
        return ("transition_not_permitted",)
    return ()


def generation_admission_verdict(
    candidate: GeneratedCandidate,
    registry: EvaluatorRegistry,
) -> tuple[str, ...]:
    """Governed-research-lifecycle entry check (02:158).

    A hypothesis/generated candidate may enter the governed research
    lifecycle only "when a suitable deterministic evaluator exists" — no
    binding covering the candidate kind blocks entry.
    """
    reasons: list[str] = []
    if registry.resolve(candidate.kind) is None:
        reasons.append("no_suitable_deterministic_evaluator")
    return tuple(reasons)


def sandbox_admission_gate(
    candidate: GeneratedCandidate,
    admission: SandboxAdmissionRecord,
    context: RunContext,
    provenance: RunProvenance,
    *,
    autonomy_ceiling: str,
    evaluator_registry: EvaluatorRegistry,
) -> tuple[str, ...]:
    """Sandbox-admission gate (D-AI-11; 03:40/78-83).

    Deterministic refusal codes; isolation, production-contact absence,
    dataset-origin closure and bounded budget are already enforced by the
    record schemas themselves. This gate additionally checks identity
    binding, provenance completeness (with ``dataset_version`` required),
    the autonomy ceiling and evaluator availability for the kind.
    """
    reasons: list[str] = []
    if admission.candidate_id != candidate.candidate_id:
        reasons.append("admission_candidate_mismatch")
    if admission.run_id != context.run_id:
        reasons.append("admission_run_id_mismatch")
    if candidate.run_id != context.run_id:
        reasons.append("candidate_run_id_mismatch")
    if missing_required_provenance(
        context, provenance, additionally_required=("dataset_version",)
    ):
        reasons.append("provenance_incomplete")
    try:
        assert_autonomy_permitted(context, autonomy_ceiling)  # type: ignore[arg-type]
    except ValueError:
        reasons.append("autonomy_level_exceeds_declared_ceiling")
    if evaluator_registry.resolve(candidate.kind) is None:
        reasons.append("no_suitable_deterministic_evaluator")
    return tuple(reasons)


def evaluation_gate(
    evaluation: CandidateEvaluationRecord,
    candidate: GeneratedCandidate,
    binding: DeterministicEvaluatorBinding,
    admission: SandboxAdmissionRecord,
) -> tuple[str, ...]:
    """Evaluation-coherence gate (D-AI-11; D-AI-19; 06:107).

    The evaluation must belong to the admitted candidate and run, be executed
    by the bound deterministic evaluator (id + version + kind coverage), use
    a dataset origin/version consistent with the admission AND accepted by
    the binding, and declare preregistration plus holdout protection.
    """
    reasons: list[str] = []
    if evaluation.candidate_id != candidate.candidate_id:
        reasons.append("evaluation_candidate_mismatch")
    if evaluation.run_id != admission.run_id:
        reasons.append("evaluation_run_id_mismatch")
    if evaluation.admission_id != admission.admission_id:
        reasons.append("evaluation_admission_mismatch")
    if evaluation.evaluator_id != binding.evaluator_id:
        reasons.append("evaluator_binding_mismatch")
    if evaluation.evaluator_version != binding.evaluator_version:
        reasons.append("evaluator_version_mismatch")
    if candidate.kind not in binding.evaluates_kinds:
        reasons.append("evaluator_kind_mismatch")
    if evaluation.dataset_origin not in binding.accepted_dataset_origins:
        reasons.append("dataset_origin_not_accepted_by_evaluator")
    if evaluation.dataset_origin != admission.dataset_origin:
        reasons.append("dataset_origin_mismatch_with_admission")
    if evaluation.dataset_version != admission.dataset_version:
        reasons.append("dataset_version_mismatch_with_admission")
    if not evaluation.preregistered:
        reasons.append("evaluation_not_preregistered")
    if not evaluation.holdout_protected:
        reasons.append("holdout_protection_not_declared")
    return tuple(reasons)


def approval_entry_gate(evaluation: CandidateEvaluationRecord) -> tuple[str, ...]:
    """Evaluation-gate verdict check before human approval (02:159).

    A candidate whose deterministic evaluation did not PASS cannot enter the
    approval stage: it stays EVALUATED with an explicit, auditable refusal
    code (explainable failure mode).
    """
    if evaluation.verdict != "PASS":
        return ("evaluation_gate_not_passed",)
    return ()


def approval_gate(
    approval: CandidateApprovalRecord,
    candidate: GeneratedCandidate,
    current_state: str,
) -> tuple[str, ...]:
    """Human-approval binding gate (02:159; 03:90-94).

    The approval record must belong to the candidate and be applied while the
    candidate is in APPROVAL_PENDING. Human identity + reference are enforced
    by the record schema.
    """
    reasons: list[str] = []
    if approval.candidate_id != candidate.candidate_id:
        reasons.append("approval_candidate_mismatch")
    if current_state != "APPROVAL_PENDING":
        reasons.append("approval_requires_approval_pending_state")
    return tuple(reasons)


def governed_candidate_acceptance(
    context: RunContext,
    provenance: RunProvenance,
    candidate: GeneratedCandidate,
    *,
    registry: EvaluatorRegistry,
    autonomy_ceiling: str,
    admission: SandboxAdmissionRecord,
    binding: DeterministicEvaluatorBinding,
    evaluation: CandidateEvaluationRecord,
    approval: CandidateApprovalRecord,
) -> tuple[str, ...]:
    """End-to-end governed acceptance of an approved candidate (03:90-94).

    Returns the blocking reasons (empty = accepted as an ADVISORY approved
    candidate). Acceptance never means production deployment: the lifecycle
    vocabulary and transition table contain no production state, and this
    module exposes no promotion path (D-AI-03/05/12/13).
    """
    reasons: list[str] = []
    reasons += sandbox_admission_gate(
        candidate,
        admission,
        context,
        provenance,
        autonomy_ceiling=autonomy_ceiling,  # type: ignore[arg-type]
        evaluator_registry=registry,
    )
    reasons += evaluation_gate(evaluation, candidate, binding, admission)
    reasons += approval_entry_gate(evaluation)
    reasons += approval_gate(approval, candidate, "APPROVAL_PENDING")
    if approval.decision == "REJECTED":
        reasons.append("human_approval_rejected")
    return tuple(reasons)
