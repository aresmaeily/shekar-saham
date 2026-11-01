"""AI-7 additive product-audit run / drift / prompt-evaluation records.

Corpus loci (2026-10-02 amendment corpus; see also
AI4_AI7_P343_DEPENDENCY_MATRIX.md §AI-7):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 102-105: AI-7 —
  "Calibration, model/prompt evaluation, recovery, rollback, observability
  and evidence-based autonomy expansion."
- 02 lines 172-179: AI-7/P10 Product Intelligence & Improvement Loop —
  domain-matched evaluation; ranked proposals "must not automatically
  change production, promote filters, alter permissions/budgets, or deploy
  software."
- 06 charter §8: "The evaluator must match the domain"; audits produce
  ranked proposals with baseline, evidence, expected impact, uncertainty,
  cost, risk, experiment design, rollback and human approval state.
- 06 charter §7: calibration and drift are computed over matured,
  point-in-time windows; later windows never look ahead of earlier ones.
- Dependency matrix §AI-7 "Authorized NOW: contract extension only".

This module is ADDITIVE to ``app.domain.product_audit`` (whose schemas are
consumed verbatim, never forked or modified):

- ``ProductAuditRunRecord`` binds one audit run to a charter version and
  per-domain evaluator results that reference the canonical
  ``product_audit.EvaluatorKind`` vocabulary; ``advisory_only`` is
  structurally True and ``data_class`` is locked to the AI-7 closed
  SYNTHETIC/PAPER set;
- ``DriftRecord`` bundles two calibration-window digests with their window
  bounds, point-in-time ordered (the later window must start at or after
  the earlier window ends); it carries NO drift verdict — the verdict is
  deferred to :func:`compare_windows`;
- ``PromptModelEvaluationRecord`` records a prompt/model evaluation with a
  synthetic-labeled model id and ``production_mutation`` structurally
  False;
- :func:`compare_windows` is the pure comparison producer: a frozen
  ``DriftAssessment`` from explicit, caller-supplied thresholds — no
  threshold is a module constant.

No network, no I/O, no clock reads, no LLM, no execution of anything.
"""

from __future__ import annotations

import math
from datetime import datetime
from fractions import Fraction
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.calibration import DATA_CLASS
from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.product_audit import (
    EvaluatorKind,
    ProductAuditDomain,
    evaluator_allowed_for_domain,
)

__all__ = [
    "DomainEvaluatorResult",
    "ProductAuditRunRecord",
    "WindowMetric",
    "CalibrationWindowDigest",
    "DriftRecord",
    "DriftMetricVerdict",
    "DriftVerdict",
    "DriftMetricAssessment",
    "DriftAssessment",
    "PromptModelEvaluationRecord",
    "compare_windows",
]

DATA_CLASS_MEMBERS: frozenset[str] = frozenset({"SYNTHETIC", "PAPER"})

_METRIC_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


# ---------------------------------------------------------------------------
# Product audit run record (charter-bound, advisory-only)
# ---------------------------------------------------------------------------


class DomainEvaluatorResult(BaseModel):
    """One per-domain evaluator result of an audit run.

    ``domain`` / ``evaluator_kind`` come from the canonical
    ``product_audit`` vocabularies; the domain/evaluator matching rule is
    the canonical one (06 §8: backtest-family evaluators apply to
    financial hypotheses only). ``metrics_digest`` binds the evaluator's
    metric payload by hash — values are exchanged by reference.
    """

    model_config = ConfigDict(frozen=True)

    domain: ProductAuditDomain
    evaluator_kind: EvaluatorKind
    evaluator_ref: str = Field(min_length=1, max_length=256)
    metrics_digest: str
    evidence_ids: tuple[str, ...] = ()
    notes: str = ""

    @field_validator("metrics_digest")
    @classmethod
    def _digest_shape(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("metrics_digest_must_be_64_hex")
        return v.lower()

    @field_validator("evidence_ids")
    @classmethod
    def _distinct_evidence(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("evidence_ids_duplicates")
        return v

    @model_validator(mode="after")
    def _domain_match(self) -> "DomainEvaluatorResult":
        if not evaluator_allowed_for_domain(self.domain, self.evaluator_kind):
            raise ValueError("evaluator_not_allowed_for_domain")
        return self


class ProductAuditRunRecord(BaseModel):
    """Record of one product-audit run bound to a charter version.

    ``advisory_only`` is structurally True (02:179; D-AI-35): nothing in
    this record can apply, deploy or promote anything. ``data_class`` is
    locked to the AI-7 closed SYNTHETIC/PAPER set.
    """

    model_config = ConfigDict(frozen=True)

    run_record_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=128)
    charter_version: str = Field(min_length=1, max_length=128)
    executed_at_utc: datetime
    domain_results: tuple[DomainEvaluatorResult, ...] = ()
    proposal_ids: tuple[str, ...] = ()
    advisory_only: Literal[True] = True
    data_class: DATA_CLASS
    notes: str = ""

    @field_validator("executed_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("data_class")
    @classmethod
    def _closed_data_class(cls, v: str) -> str:
        if v not in DATA_CLASS_MEMBERS:
            raise ValueError("data_class_not_in_closed_set")
        return v

    @field_validator("domain_results")
    @classmethod
    def _distinct_domains(
        cls, v: tuple[DomainEvaluatorResult, ...]
    ) -> tuple[DomainEvaluatorResult, ...]:
        domains = [r.domain for r in v]
        if len(set(domains)) != len(domains):
            raise ValueError("duplicate_domain_results")
        return v

    @field_validator("proposal_ids")
    @classmethod
    def _distinct_proposals(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("proposal_ids_duplicates")
        return v


# ---------------------------------------------------------------------------
# Drift records (PIT-ordered calibration windows; verdict deferred)
# ---------------------------------------------------------------------------


class WindowMetric(BaseModel):
    """One named metric value supplied by the caller (exact float)."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=64, pattern=_METRIC_NAME_PATTERN)
    value: float

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("metric_value_must_be_finite")
        return v


class CalibrationWindowDigest(BaseModel):
    """One calibration window: bounds + integrity digest + metric values.

    The digest binds the window's underlying calibration records by hash
    (the records are exchanged by reference, D-AI-23). Metric values are
    the supplied numbers :func:`compare_windows` compares — the module
    never recomputes them.
    """

    model_config = ConfigDict(frozen=True)

    window_start_utc: datetime
    window_end_utc: datetime
    digest: str
    metric_values: tuple[WindowMetric, ...] = ()

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("digest")
    @classmethod
    def _digest_shape(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("digest_must_be_64_hex")
        return v.lower()

    @field_validator("metric_values")
    @classmethod
    def _distinct_names(cls, v: tuple[WindowMetric, ...]) -> tuple[WindowMetric, ...]:
        names = [m.name for m in v]
        if len(set(names)) != len(names):
            raise ValueError("window_metric_names_duplicates")
        return v

    @model_validator(mode="after")
    def _window_order(self) -> "CalibrationWindowDigest":
        if self.window_end_utc < self.window_start_utc:
            raise ValueError("window_end_before_start")
        return self


class DriftRecord(BaseModel):
    """Two calibration windows bound for drift comparison (AI-7 contract).

    Point-in-time discipline (06 §7): the later window must START at or
    after the earlier window ENDS. The record deliberately carries NO
    verdict field — the drift verdict is deferred to
    :func:`compare_windows` with caller-supplied thresholds.
    """

    model_config = ConfigDict(frozen=True)

    drift_record_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    subject_ref: str = Field(min_length=1, max_length=128)
    earlier_window: CalibrationWindowDigest
    later_window: CalibrationWindowDigest
    data_class: DATA_CLASS
    notes: str = ""

    @field_validator("data_class")
    @classmethod
    def _closed_data_class(cls, v: str) -> str:
        if v not in DATA_CLASS_MEMBERS:
            raise ValueError("data_class_not_in_closed_set")
        return v

    @model_validator(mode="after")
    def _pit_order(self) -> "DriftRecord":
        if self.later_window.window_start_utc < self.earlier_window.window_end_utc:
            raise ValueError("windows_not_pit_ordered")
        return self


# ---------------------------------------------------------------------------
# Pure comparison producer (explicit thresholds, never module constants)
# ---------------------------------------------------------------------------

DriftMetricVerdict = Literal["DRIFTED", "STABLE", "NOT_EVALUATED"]
DriftVerdict = Literal["DRIFT_DETECTED", "NO_DRIFT_DETECTED"]


class DriftMetricAssessment(BaseModel):
    """Per-metric deterministic comparison row (frozen).

    ``earlier_value``/``later_value``/``delta`` are ``None`` when the
    metric exists in only one of the two windows (honest NOT_EVALUATED —
    a one-sided value is never promoted to a comparison).
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=64, pattern=_METRIC_NAME_PATTERN)
    earlier_value: float | None = None
    later_value: float | None = None
    delta: float | None = None
    threshold: float | None = None
    verdict: DriftMetricVerdict


class DriftAssessment(BaseModel):
    """Frozen result of :func:`compare_windows`.

    Binds the two compared window digests, the per-metric rows (canonical
    name order) and the deterministic overall verdict with stable reason
    codes. Nothing here mutates anything or grants any authority.
    """

    model_config = ConfigDict(frozen=True)

    earlier_digest: str
    later_digest: str
    metric_assessments: tuple[DriftMetricAssessment, ...] = ()
    drift_verdict: DriftVerdict
    reason_codes: tuple[str, ...] = Field(min_length=1)


def compare_windows(
    earlier: CalibrationWindowDigest,
    later: CalibrationWindowDigest,
    *,
    thresholds: Mapping[str, float],
) -> DriftAssessment:
    """Deterministic threshold comparison over supplied metric values.

    PIT discipline is re-checked here (``windows_not_pit_ordered``): the
    later window must start at or after the earlier window ends.

    For every metric name present in EITHER window (canonical sorted
    order): when the name exists in BOTH windows,
    ``delta = later − earlier`` computed EXACTLY (rational arithmetic on
    the stated decimal inputs, converted to float once), and when the
    caller supplied a threshold for the name the verdict is ``DRIFTED``
    iff ``abs(delta) > threshold`` (strict), else ``STABLE``; when no
    threshold was supplied the row is honestly ``NOT_EVALUATED`` (never
    guessed). Metrics present in only one window are also reported as
    ``NOT_EVALUATED`` — nothing is invented. Thresholds must be finite,
    non-negative, caller-supplied values
    (``threshold_must_be_finite_nonnegative``); they are explicit
    parameters, never module constants.

    Overall verdict: ``DRIFT_DETECTED`` iff at least one evaluated row
    drifted, with one ``drift_detected:<name>`` reason per drifted metric;
    otherwise ``NO_DRIFT_DETECTED`` / ``no_drift_detected``.
    """
    if later.window_start_utc < earlier.window_end_utc:
        raise ValueError("windows_not_pit_ordered")
    for name, threshold in thresholds.items():
        if not isinstance(name, str) or not name:
            raise ValueError("threshold_name_invalid")
        if not math.isfinite(threshold) or threshold < 0:
            raise ValueError("threshold_must_be_finite_nonnegative")
    earlier_by_name = {m.name: m.value for m in earlier.metric_values}
    later_by_name = {m.name: m.value for m in later.metric_values}
    rows: list[DriftMetricAssessment] = []
    drifted: list[str] = []
    for name in sorted(set(earlier_by_name) | set(later_by_name)):
        threshold = thresholds.get(name)
        if name not in earlier_by_name or name not in later_by_name:
            rows.append(
                DriftMetricAssessment(
                    name=name,
                    earlier_value=earlier_by_name.get(name),
                    later_value=later_by_name.get(name),
                    delta=None,
                    threshold=threshold,
                    verdict="NOT_EVALUATED",
                )
            )
            continue
        # Exact delta: rational arithmetic over the stated decimal inputs.
        earlier_exact = Fraction(str(earlier_by_name[name]))
        later_exact = Fraction(str(later_by_name[name]))
        delta_exact = later_exact - earlier_exact
        delta = float(delta_exact)
        if threshold is None:
            verdict: DriftMetricVerdict = "NOT_EVALUATED"
        elif abs(delta_exact) > Fraction(str(threshold)):
            verdict = "DRIFTED"
            drifted.append(name)
        else:
            verdict = "STABLE"
        rows.append(
            DriftMetricAssessment(
                name=name,
                earlier_value=float(earlier_exact),
                later_value=float(later_exact),
                delta=delta,
                threshold=threshold,
                verdict=verdict,
            )
        )
    if drifted:
        return DriftAssessment(
            earlier_digest=earlier.digest,
            later_digest=later.digest,
            metric_assessments=tuple(rows),
            drift_verdict="DRIFT_DETECTED",
            reason_codes=tuple(f"drift_detected:{n}" for n in drifted),
        )
    return DriftAssessment(
        earlier_digest=earlier.digest,
        later_digest=later.digest,
        metric_assessments=tuple(rows),
        drift_verdict="NO_DRIFT_DETECTED",
        reason_codes=("no_drift_detected",),
    )


# ---------------------------------------------------------------------------
# Prompt/model evaluation record (synthetic-labeled; no production mutation)
# ---------------------------------------------------------------------------


class PromptModelEvaluationRecord(BaseModel):
    """Record of one prompt/model evaluation (AI-7 "model/prompt
    evaluation").

    ``model_id`` is synthetic-labeled: the label is structurally pinned and
    a live/production model id claim is not expressible here.
    ``production_mutation`` is structurally False and ``advisory_only`` is
    structurally True — the record cannot express any production change
    (02:179; D-AI-35).
    """

    model_config = ConfigDict(frozen=True)

    evaluation_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    prompt_version: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    model_id_label: Literal["SYNTHETIC_MODEL"] = "SYNTHETIC_MODEL"
    metrics_digest: str
    evaluated_at_utc: datetime
    advisory_only: Literal[True] = True
    production_mutation: Literal[False] = False
    data_class: DATA_CLASS
    notes: str = ""

    @field_validator("evaluated_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("metrics_digest")
    @classmethod
    def _digest_shape(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("metrics_digest_must_be_64_hex")
        return v.lower()

    @field_validator("data_class")
    @classmethod
    def _closed_data_class(cls, v: str) -> str:
        if v not in DATA_CLASS_MEMBERS:
            raise ValueError("data_class_not_in_closed_set")
        return v
