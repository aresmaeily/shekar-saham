"""Prediction registry and outcome-maturity contracts for RADAR BOURSE.

P0 addendum scope (Binding additive amendment 2026-10-02,
02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md line 139): "prediction registry and
outcome-maturity rules to prevent look-ahead and label leakage".

Design references:
- 06 charter §7: every financial hypothesis must be preregistered before
  outcome observation; for each prediction, the timestamp, outcome horizon,
  evaluation metric, event-maturity rule and invalidation rule are defined in
  advance; after maturity the prediction is compared to reality and error
  categories/calibration/drift produce research proposals. "Never change the
  original prediction record or use future data in the original assessment."
- D-AI-37 (05 register): predictions are timestamped before outcomes, linked
  to predefined horizons and point-in-time evidence, then evaluated after
  outcomes mature; error analysis may generate research proposals but cannot
  directly change production logic.

Contract/domain only: deterministic, clock-free (time enters only via
arguments), no I/O, no LLM. PredictionRecords are frozen and registries are
append-only value objects; the original record can never be edited.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, _finite_decimal, ensure_utc

MaturityState = Literal["PENDING", "MATURED"]


class PredictionRecord(BaseModel):
    """Immutable preregistered prediction (06 charter §7).

    Frozen by construction: the horizon, metric, maturity rule and
    invalidation rule are fixed at registration time and can never be edited
    through this contract.
    """

    model_config = ConfigDict(frozen=True)

    prediction_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    subject: str = Field(min_length=1)
    registered_at_utc: datetime
    outcome_horizon_end_utc: datetime
    evaluation_metric: str = Field(min_length=1)
    event_maturity_rule: str = Field(min_length=1)
    invalidation_rule: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    creator: str = Field(min_length=1)
    notes: str = ""

    @field_validator("registered_at_utc", "outcome_horizon_end_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _horizon_after_registration(self) -> "PredictionRecord":
        if self.outcome_horizon_end_utc <= self.registered_at_utc:
            raise ValueError("horizon_must_end_after_registration")
        return self


class OutcomeRecord(BaseModel):
    """Observed outcome for one prediction, recorded once.

    Anti-look-ahead guards are enforced at registration into the registry:
    the outcome must not predate the prediction's registration, and each
    prediction admits at most one outcome record.
    """

    model_config = ConfigDict(frozen=True)

    outcome_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    prediction_id: str = Field(min_length=1)
    observed_at_utc: datetime
    observed_value: str | None = None
    observed_numeric: float | None = None
    source_evidence_ids: tuple[str, ...] = Field(min_length=1)
    notes: str = ""

    @field_validator("observed_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("observed_numeric")
    @classmethod
    def _finite(cls, v: float | None) -> float | None:
        return None if v is None else float(_finite_decimal(v))


def maturity_state(record: PredictionRecord, as_of: datetime) -> MaturityState:
    """Deterministic outcome-maturity check (D-AI-37; 02 roadmap line 139).

    An outcome is MATURED only when the predefined horizon has ended by
    `as_of`. Evaluation before maturity is label leakage and is refused by
    `evaluate_outcome`.
    """
    return "MATURED" if ensure_utc(as_of) >= record.outcome_horizon_end_utc else "PENDING"


class PredictionEvaluation(BaseModel):
    """Post-maturity comparison of a prediction with its observed outcome.

    Carries error decomposition/calibration/drift fields that may reference a
    research proposal — advisory only; it can never change production logic
    (D-AI-37).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    prediction_id: str = Field(min_length=1)
    outcome_id: str = Field(min_length=1)
    evaluated_at_utc: datetime
    matched_expectation: bool
    error_category: str | None = None
    calibration_note: str | None = None
    research_proposal_ref: str | None = None
    notes: str = ""

    @field_validator("evaluated_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


class PredictionRegistry(BaseModel):
    """Append-only prediction/outcome registry (value object).

    register_prediction() and attach_outcome() return NEW registries with an
    incremented version. Guards: duplicate prediction ids are rejected; an
    outcome predating its prediction's registration is rejected (look-ahead /
    label leakage); a second outcome for the same prediction is rejected
    (original records are never changed).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    registry_version: int = Field(default=1, ge=1)
    predictions: tuple[PredictionRecord, ...] = ()
    outcomes: tuple[OutcomeRecord, ...] = ()

    def get_prediction(self, prediction_id: str) -> PredictionRecord | None:
        for p in self.predictions:
            if p.prediction_id == prediction_id:
                return p
        return None

    def get_outcome(self, prediction_id: str) -> OutcomeRecord | None:
        for o in self.outcomes:
            if o.prediction_id == prediction_id:
                return o
        return None

    def register_prediction(self, record: PredictionRecord) -> "PredictionRegistry":
        if self.get_prediction(record.prediction_id) is not None:
            raise ValueError("duplicate_prediction_id")
        return self.model_copy(
            update={
                "registry_version": self.registry_version + 1,
                "predictions": self.predictions + (record,),
            }
        )

    def attach_outcome(self, outcome: OutcomeRecord) -> "PredictionRegistry":
        record = self.get_prediction(outcome.prediction_id)
        if record is None:
            raise ValueError("unknown_prediction_id")
        if self.get_outcome(outcome.prediction_id) is not None:
            raise ValueError("prediction_already_has_outcome")
        if outcome.observed_at_utc < record.registered_at_utc:
            raise ValueError("outcome_predates_prediction_registration")
        return self.model_copy(
            update={
                "registry_version": self.registry_version + 1,
                "outcomes": self.outcomes + (outcome,),
            }
        )

    def evaluate(
        self,
        prediction_id: str,
        *,
        as_of: datetime,
        matched_expectation: bool,
        error_category: str | None = None,
        calibration_note: str | None = None,
        research_proposal_ref: str | None = None,
        notes: str = "",
    ) -> PredictionEvaluation:
        """Deterministically evaluate a matured prediction.

        Raises before maturity (label-leakage guard) or when the outcome is
        missing. The evaluation timestamp recorded is the caller-provided
        `as_of`, never a wall-clock read.
        """
        record = self.get_prediction(prediction_id)
        if record is None:
            raise ValueError("unknown_prediction_id")
        if maturity_state(record, as_of) != "MATURED":
            raise ValueError("prediction_not_matured")
        outcome = self.get_outcome(prediction_id)
        if outcome is None:
            raise ValueError("outcome_not_recorded")
        return PredictionEvaluation(
            prediction_id=prediction_id,
            outcome_id=outcome.outcome_id,
            evaluated_at_utc=ensure_utc(as_of),
            matched_expectation=matched_expectation,
            error_category=error_category,
            calibration_note=calibration_note,
            research_proposal_ref=research_proposal_ref,
            notes=notes,
        )
