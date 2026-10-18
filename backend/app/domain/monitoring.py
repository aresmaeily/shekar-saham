"""Monitoring job identity contracts for RADAR BOURSE.

P0 addendum scope (Binding additive amendment 2026-10-02,
02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md line 137): "monitoring job identity,
schedules/triggers, retry/idempotency, freshness SLAs, budget, observability,
alerting and kill switch".

Design references:
- 06 charter §9: every job needs idempotency, retry ceilings, timeout,
  concurrency/rate limits, run identity, audit trace, last-success status,
  failure alert, kill switch and explicit source/data boundaries. Cadence must
  not be hard-coded before operational requirements and budgets are approved.
- 02-arch additive §Continuous monitoring architecture: every source/monitor
  has declared coverage, refresh policy, permissions, rate/budget ceilings,
  retries/idempotency, freshness objective, last-success timestamp, failure
  state and kill switch.
- D-AI-32, D-AI-30 (05 register): monitoring requires budget, observability,
  recovery and kill switch before any proactive behavior.

Contract/domain only. These are SPEC and STATE records: no scheduler runs
here, nothing is executed, nothing touches the network. The kill switch
defaults to ENGAGED (fail-closed): a newly specified job may not run until it
is explicitly released by configuration.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc

TriggerKind = Literal["SCHEDULED", "EVENT_DRIVEN"]
KillSwitchState = Literal["ENGAGED", "RELEASED"]
JobFailureState = Literal["HEALTHY", "DEGRADED", "FAILING", "HALTED"]

#: Hard structural ceilings (06 charter §9 "retry ceilings"; bounded resources).
MAX_RETRY_ATTEMPTS = 10
MAX_TIMEOUT_SECONDS = 3600
MAX_CONCURRENCY = 8
MAX_RUNS_PER_HOUR = 60


class TriggerSpec(BaseModel):
    """Schedule or event trigger. Exactly one kind is declared; expressions
    stay owner-configured strings — no cadence is hard-coded here."""

    model_config = ConfigDict(frozen=True)

    kind: TriggerKind
    schedule_expression: str | None = None
    event_types: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _kind_consistency(self) -> "TriggerSpec":
        if self.kind == "SCHEDULED":
            if not self.schedule_expression:
                raise ValueError("scheduled_trigger_requires_expression")
            if self.event_types:
                raise ValueError("scheduled_trigger_forbids_event_types")
        else:
            if not self.event_types:
                raise ValueError("event_trigger_requires_event_types")
            if self.schedule_expression is not None:
                raise ValueError("event_trigger_forbids_schedule_expression")
        return self


class RetryPolicy(BaseModel):
    """Bounded retries with explicit ceilings and idempotent replay."""

    model_config = ConfigDict(frozen=True)

    max_attempts: int = Field(ge=1, le=MAX_RETRY_ATTEMPTS)
    backoff_seconds_base: int = Field(ge=0, le=3600)
    idempotency_required: Literal[True] = True


class BudgetSpec(BaseModel):
    """Declared resource ceilings. Every ceiling is bounded and explicit."""

    model_config = ConfigDict(frozen=True)

    max_runs_per_hour: int = Field(ge=1, le=MAX_RUNS_PER_HOUR)
    max_timeout_seconds: int = Field(ge=1, le=MAX_TIMEOUT_SECONDS)
    max_concurrency: int = Field(ge=1, le=MAX_CONCURRENCY)


class MonitoringJobSpec(BaseModel):
    """Immutable specification of a governed monitoring job.

    The kill switch defaults to ENGAGED: a job that has never been explicitly
    released must not run (fail-closed, D-AI-32/D-AI-38; 03 boundaries:
    monitoring specification is not proof of live monitoring).
    """

    model_config = ConfigDict(frozen=True)

    job_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    target_source_ids: tuple[str, ...] = Field(min_length=1)
    trigger: TriggerSpec
    retry_policy: RetryPolicy
    budget: BudgetSpec
    freshness_sla: timedelta | None = None
    observability_ref: str = Field(min_length=1)
    alerting_ref: str = Field(min_length=1)
    kill_switch: KillSwitchState = "ENGAGED"
    notes: str = ""

    @field_validator("freshness_sla")
    @classmethod
    def _positive_sla(cls, v: timedelta | None) -> timedelta | None:
        if v is not None and v <= timedelta(0):
            raise ValueError("freshness_sla_must_be_positive")
        return v

    @field_validator("target_source_ids")
    @classmethod
    def _distinct_targets(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("target_source_ids_duplicates")
        return v

    def run_allowed(self) -> bool:
        """Deterministic permission-to-run check (policy, not execution)."""
        return self.kill_switch == "RELEASED"


class MonitoringJobState(BaseModel):
    """Operational state of a monitoring job (last-success honesty)."""

    model_config = ConfigDict(frozen=True)

    job_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    last_success_utc: datetime | None = None
    last_attempt_utc: datetime | None = None
    consecutive_failures: int = Field(default=0, ge=0)
    failure_state: JobFailureState = "HEALTHY"
    failure_alert_sent: bool = False
    notes: str = ""

    @field_validator("last_success_utc", "last_attempt_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @model_validator(mode="after")
    def _state_consistency(self) -> "MonitoringJobState":
        if self.failure_state == "HEALTHY" and self.consecutive_failures != 0:
            raise ValueError("healthy_state_requires_zero_consecutive_failures")
        if self.failure_state == "HALTED" and not self.failure_alert_sent:
            raise ValueError("halted_state_requires_failure_alert")
        return self


def effective_run_permission(
    spec: MonitoringJobSpec, state: MonitoringJobState, *, job_id_must_match: bool = True
) -> bool:
    """Deterministic permission decision for a job spec/state pair.

    A job may run only when: the kill switch is RELEASED **and** the recorded
    failure state is not HALTED **and** (when enforced) the state belongs to
    the same job. Recovery from HALTED is an explicit owner action (new spec
    or new state), never an automatic retry.
    """
    if job_id_must_match and spec.job_id != state.job_id:
        return False
    if not spec.run_allowed():
        return False
    return state.failure_state != "HALTED"
