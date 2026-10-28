"""AI-7 Continuous Learning/Productization — calibration-record contracts.

Corpus loci (2026-10-02 amendment corpus, byte-verified import):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 102-104: "AI-7 —
  Continuous Learning/Productization: Calibration, model/prompt evaluation,
  recovery, rollback, observability and evidence-based autonomy expansion."
- 02 lines 172-179: AI-7/P10 Product Intelligence & Improvement Loop —
  domain-matched audits; "market/fundamental AI: Golden Set quality, source
  grounding, freshness, conflict handling, calibration, drift and
  invalidation quality"; ranked hypotheses "must not automatically change
  production, promote filters, alter permissions/budgets, or deploy
  software."
- 02 line 202: pre-G2 authorized class — bounded design, schema work,
  source-registry design, synthetic/paper tests and safe dry-run work only.
- AI4_AI7_P343_DEPENDENCY_MATRIX.md §AI-7: "Authorized NOW: contract
  extension only (e.g. calibration-record contracts); loop runtime BLOCKED";
  "everything operational until AI-4/AI-5 produce evidence" — both evidence
  prerequisites are delivered at the contract class (AI-4 51 tests, AI-5 38
  tests), so this contract extension is the remaining authorized lane.
- 05 register D-AI-31 "DEFERRED UNTIL EVIDENCE — Autonomy expands only from
  measured evidence"; D-AI-38 lineage (honest coverage/freshness reporting);
  05:200: D-AI-01..31 remain in force; no live trading, production mutation,
  auto-promotion, self-escalation or self-modifying production logic is
  authorized by D-AI-32..39; 05:202 D-AI-41: capability is not evidence.
- 04 charter:72 (RACI): G2/autonomy/permission acts are owner-Accountable;
  the implementing agent cannot hold them (T6 lineage).

Contract/domain ONLY (composes canonical types by direct import — no fork):
no calibration computation, no outcome-label ingestion, no evaluation run,
no scheduler, nothing touches the network, no LLM call, no clock read.
Calibration records bind their subjects by bounded artifact id — the P0
prediction and product-audit schemas are NOT duplicated or modified.
``data_class`` is closed to SYNTHETIC/PAPER (the 02:202 pre-G2 class; LIVE
is unrepresentable until G2-passed real-data execution), and
``AutonomyExpansionEvidence`` is EVIDENCE_ONLY with ``approval_state``
pinned NOT_GRANTED — recording evidence grants nothing; autonomy expansion
is an owner decision at a convened review (D-AI-31 + 04:72), and the
module's permission gate structurally refuses with stable refusal tags.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.run_governance import AutonomyLevel, _AUTONOMY_ORDER

#: Structural invariants (02:202 pre-G2 class; D-AI-31; 04:72) —
#: unrepresentable states.
DATA_CLASS = Literal["SYNTHETIC", "PAPER"]
UNIVERSAL_CALIBRATION_CLAIMED: Literal[False] = False
EXPANSION_STATUS = Literal["EVIDENCE_ONLY"]
EXPANSION_APPROVAL_STATE = Literal["NOT_GRANTED"]

#: Bounded sizes (defensive ceilings; no operative threshold is baked in —
#: D-AI-31 evidence thresholds are an owner call when evidence exists).
MAX_BUCKETS = 32
MAX_SUPPORTING_CALIBRATIONS = 64
MAX_SUBJECT_REF_LENGTH = 128

SubjectKind = Literal["PREDICTION", "PRODUCT_AUDIT", "RESEARCH_OUTPUT"]


class CalibrationBucket(BaseModel):
    """One reliability-bucket measurement (bounded, frozen)."""

    model_config = ConfigDict(frozen=True)

    upper_bound: float = Field(gt=0.0, le=1.0)
    predicted_mean: float = Field(ge=0.0, le=1.0)
    observed_frequency: float = Field(ge=0.0, le=1.0)
    count: int = Field(ge=1)


class CalibrationRecord(BaseModel):
    """Governed record of one calibration measurement (AI-7 contract).

    Binds a calibration measurement to a subject artifact by id and kind —
    it never embeds or re-validates the subject itself. At least one actual
    measurement is required (a Brier score, an expected calibration error,
    or at least one reliability bucket); an empty record is refused at
    construction. Coverage honesty follows the D-AI-38 lineage: an
    incomplete coverage declaration must list at least one gap, and a
    universal-calibration claim is structurally unrepresentable.
    """

    model_config = ConfigDict(frozen=True)

    calibration_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    subject_kind: SubjectKind
    subject_ref: str = Field(min_length=1, max_length=MAX_SUBJECT_REF_LENGTH)
    measured_at_utc: datetime
    data_class: DATA_CLASS
    sample_size: int = Field(ge=1)
    brier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    expected_calibration_error: float | None = Field(default=None, ge=0.0, le=1.0)
    buckets: tuple[CalibrationBucket, ...] = ()
    coverage_complete: bool
    coverage_gaps: tuple[str, ...] = ()
    universal_calibration_claimed: Literal[False] = False
    evidence_ref: str = Field(min_length=1)
    calibration_note: str = ""

    @field_validator("measured_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("buckets")
    @classmethod
    def _bounded_ascending_buckets(
        cls, v: tuple[CalibrationBucket, ...]
    ) -> tuple[CalibrationBucket, ...]:
        if len(v) > MAX_BUCKETS:
            raise ValueError("buckets_exceed_ceiling")
        upper_bounds = [b.upper_bound for b in v]
        if len(set(upper_bounds)) != len(upper_bounds):
            raise ValueError("bucket_upper_bounds_duplicates")
        if any(
            later <= earlier
            for earlier, later in zip(upper_bounds, upper_bounds[1:])
        ):
            raise ValueError("bucket_upper_bounds_not_strictly_ascending")
        return v

    @field_validator("coverage_gaps")
    @classmethod
    def _nonempty_gap_strings(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if any(not g.strip() for g in v):
            raise ValueError("coverage_gaps_must_be_nonempty")
        return v

    @model_validator(mode="after")
    def _measurement_and_honesty(self) -> "CalibrationRecord":
        has_score = self.brier_score is not None or (
            self.expected_calibration_error is not None
        )
        if not has_score and not self.buckets:
            raise ValueError("calibration_measurement_required")
        if self.buckets:
            counted = sum(b.count for b in self.buckets)
            if counted != self.sample_size:
                raise ValueError("bucket_counts_must_sum_to_sample_size")
        if not self.coverage_complete and not self.coverage_gaps:
            raise ValueError("incomplete_coverage_requires_gaps")
        return self


class AutonomyExpansionEvidence(BaseModel):
    """D-AI-31 EVIDENCE-ONLY record for autonomy expansion (AI-7 contract).

    Bundles supporting calibration records into the evidence shape the
    register requires ("Autonomy expands only from measured evidence"). The
    record itself carries NO authority: ``status`` is pinned
    ``EVIDENCE_ONLY`` and ``approval_state`` is pinned ``NOT_GRANTED`` — an
    approval is structurally unrepresentable in this schema. Acting on the
    evidence is an owner decision at a convened review (04:72 RACI; T6
    lineage); the module's permission gate refuses unconditionally.
    """

    model_config = ConfigDict(frozen=True)

    expansion_evidence_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    from_level: AutonomyLevel
    to_level: AutonomyLevel
    supporting_calibration_ids: tuple[str, ...] = Field(min_length=1)
    window_start_utc: datetime
    window_end_utc: datetime
    status: EXPANSION_STATUS = "EVIDENCE_ONLY"
    approval_state: EXPANSION_APPROVAL_STATE = "NOT_GRANTED"
    notes: str = ""

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("supporting_calibration_ids")
    @classmethod
    def _bounded_distinct_ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(v) > MAX_SUPPORTING_CALIBRATIONS:
            raise ValueError("supporting_calibration_ids_exceed_ceiling")
        if any(not i.strip() for i in v):
            raise ValueError("supporting_calibration_ids_must_be_nonempty")
        if len(set(v)) != len(v):
            raise ValueError("supporting_calibration_ids_duplicates")
        return v

    @model_validator(mode="after")
    def _evidence_consistency(self) -> "AutonomyExpansionEvidence":
        if self.window_end_utc < self.window_start_utc:
            raise ValueError("evidence_window_end_before_start")
        if self.from_level == self.to_level:
            raise ValueError("expansion_level_unchanged")
        if _AUTONOMY_ORDER[self.to_level] <= _AUTONOMY_ORDER[self.from_level]:
            raise ValueError("expansion_must_be_upward")
        return self


def autonomy_expansion_permission(
    evidence: AutonomyExpansionEvidence,
) -> tuple[bool, tuple[str, ...]]:
    """Deterministic, ALWAYS-refusing permission gate for autonomy expansion.

    Returns ``(False, refusals)`` and NEVER executes anything. Autonomy
    expansion is an owner decision made from measured evidence at a convened
    review (D-AI-31 DEFERRED UNTIL EVIDENCE; charter 04:72 Role-1
    accountability); this contract layer has no authority to grant it, so
    the gate structurally refuses and contributes stable refusal tags for
    audit evidence. The record is still accepted as EVIDENCE — refusing the
    action is not disputing the measurement.
    """

    refusals: list[str] = ["autonomy_expansion_owner_gated"]
    if not evidence.supporting_calibration_ids:
        # Defense-in-depth: unreachable via the validating constructor
        # (min_length=1) but reachable via model_construct bypasses.
        refusals.insert(0, "no_supporting_evidence")
    return (False, tuple(refusals))
