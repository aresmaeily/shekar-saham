"""Governed monitoring-cycle record contracts for RADAR BOURSE (AI-1 observer seam).

Corpus loci (2026-10-02 amendment corpus, byte-verified):
- 02_EXECUTION_ROADMAP lines 155–156 (additive §AI-1/AI-5): the product "must
  support governed scheduled and event-triggered monitoring of the configured
  source universe and approved watchlists … Coverage gaps and inaccessible
  sources must be reported. Monitoring must respect source terms, access
  controls, robots/rate limits where applicable, privacy, resource budgets,
  and kill switches."
- 02 line 193 (acceptance): monitoring acceptance requires "schedule/trigger
  execution, source coverage/freshness, event lineage, failure/recovery,
  rate/budget enforcement and kill switch" — RUNTIME evidence, which this
  contract layer deliberately does NOT claim (D-AI-41).
- 06 charter §9: every job needs idempotency, retry ceilings, timeout,
  concurrency/rate limits, run identity, audit trace, last-success status,
  failure alert, kill switch and explicit source/data boundaries.
- D-AI-38: all monitoring outputs state coverage, last success, freshness,
  known gaps, source failures and unresolved conflicts.
- D-AI-32 / D-AI-30: monitoring requires budget, observability, recovery and
  kill switch before any proactive behavior.

Reuse (no reimplementation): permission-to-run comes exclusively from the
P0-AMD-1 ``effective_run_permission`` (``backend/app/domain/monitoring.py``);
coverage honesty comes exclusively from the P0-AMD-1 ``CoverageReport``
(``backend/app/domain/source_registry.py``); run identity comes from the
canonical ``RunContext`` (``backend/app/domain/run_governance.py``).

Contract/domain only: frozen records, deterministic, clock-free, no I/O, no
scheduler execution, no network, no LLM. A cycle record describes a cycle;
it never executes one. Fail-closed: when permission is refused the record
can carry no successes and no events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.monitoring import (
    MonitoringJobSpec,
    MonitoringJobState,
    effective_run_permission,
)
from app.domain.source_registry import CoverageReport
from app.domain.run_governance import RunContext

CycleOutcome = Literal["COMPLETED", "PARTIAL", "FAILED", "REFUSED_BY_POLICY"]


class GovernedMonitoringCycleRecord(BaseModel):
    """Observational record of one governed monitoring cycle attempt.

    Binds together (all re-used P0-AMD-1 / run-governance contracts):
    the job spec/state (permission + operational honesty), the coverage
    report (coverage honesty, D-AI-38), and the canonical run identity.
    Source-level outcomes are recorded per source — nothing is inferred
    beyond the recorded fields.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    coverage: CoverageReport
    permission_granted: bool
    outcome: CycleOutcome
    started_at_utc: datetime
    finished_at_utc: datetime | None = None
    sources_attempted: tuple[str, ...] = ()
    sources_succeeded: tuple[str, ...] = ()
    sources_failed: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    failure_notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    notes: str = ""

    @field_validator("started_at_utc", "finished_at_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("sources_attempted", "sources_succeeded", "sources_failed", "event_ids")
    @classmethod
    def _distinct(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate_items")
        return v

    @model_validator(mode="after")
    def _honesty_guards(self) -> "GovernedMonitoringCycleRecord":
        # Fail-closed: a refused cycle executed nothing.
        if self.outcome == "REFUSED_BY_POLICY":
            if self.permission_granted:
                raise ValueError("refused_cycle_cannot_claim_permission")
            if self.sources_succeeded or self.event_ids:
                raise ValueError("refused_cycle_cannot_claim_successes_or_events")
            if self.finished_at_utc is not None:
                raise ValueError("refused_cycle_has_no_finish_timestamp")
        else:
            if not self.permission_granted:
                raise ValueError("executed_cycle_requires_permission")
            if self.finished_at_utc is None:
                raise ValueError("executed_cycle_requires_finish_timestamp")
        # Failure honesty: sources recorded as failed force an honest outcome.
        if self.sources_failed and self.outcome == "COMPLETED":
            raise ValueError("failed_sources_force_partial_or_failed_outcome")
        if self.sources_succeeded and self.outcome == "FAILED":
            raise ValueError("succeeded_sources_force_partial_outcome")
        if not self.sources_succeeded and not self.sources_failed and self.outcome in (
            "COMPLETED",
            "PARTIAL",
        ):
            raise ValueError("outcome_requires_source_outcomes")
        # Lineage honesty: succeeded + failed must be within attempted.
        if not (set(self.sources_succeeded) | set(self.sources_failed)) <= set(
            self.sources_attempted
        ):
            raise ValueError("source_outcomes_outside_attempted_set")
        return self


def record_monitoring_cycle(
    *,
    record_id: str,
    spec: MonitoringJobSpec,
    state: MonitoringJobState,
    context: RunContext,
    coverage: CoverageReport,
    started_at_utc: datetime,
    finished_at_utc: datetime | None = None,
    sources_attempted: tuple[str, ...] = (),
    sources_succeeded: tuple[str, ...] = (),
    sources_failed: tuple[str, ...] = (),
    event_ids: tuple[str, ...] = (),
    failure_notes: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    notes: str = "",
) -> GovernedMonitoringCycleRecord:
    """Deterministic factory binding a cycle attempt to its permission truth.

    The permission decision is computed here from the spec/state pair via the
    P0-AMD-1 :func:`effective_run_permission` — callers cannot assert a
    permission that the job spec does not grant. When permission is refused,
    the factory forces outcome ``REFUSED_BY_POLICY`` and refuses to carry
    successes, events or a finish timestamp (fail-closed). Timestamp
    normalization/validation is delegated to the record model itself.
    """
    granted = effective_run_permission(spec, state)
    if granted:
        if sources_failed:
            outcome: CycleOutcome = "FAILED" if not sources_succeeded else "PARTIAL"
        elif sources_succeeded:
            outcome = "COMPLETED"
        else:
            raise ValueError("executed_cycle_requires_source_outcomes")
    else:
        outcome = "REFUSED_BY_POLICY"
    if context.run_kind != "MONITORING_CYCLE":
        raise ValueError("monitoring_cycle_requires_monitoring_run_kind")
    if spec.job_id != state.job_id:
        # effective_run_permission already refuses this; the explicit check
        # keeps the record's job_id bound to the actually-used spec.
        raise ValueError("job_id_mismatch")
    return GovernedMonitoringCycleRecord(
        record_id=record_id,
        schema_version=SCHEMA_VERSION,
        job_id=spec.job_id,
        run_id=context.run_id,
        coverage=coverage,
        permission_granted=granted,
        outcome=outcome,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
        sources_attempted=tuple(dict.fromkeys(sources_attempted)),
        sources_succeeded=tuple(dict.fromkeys(sources_succeeded)),
        sources_failed=tuple(dict.fromkeys(sources_failed)),
        event_ids=tuple(dict.fromkeys(event_ids)),
        failure_notes=tuple(dict.fromkeys(failure_notes)),
        warnings=tuple(dict.fromkeys(warnings)),
        notes=notes,
    )
