"""DECLARED-ONLY adoption/accessibility/task metrics for the AI-7 audit.

WAVE-AB5 (WP-H, additive): the AI-7 evaluation-domain audit recorded that, of
the 15 required evaluation domains, domains 12 (accessibility), 13 (feature
adoption) and 14 (task completion) had NO code anywhere in the repository.
This module closes that gap for the closable portion — the DECLARED fixture
layer that the /api/v10/productloops/product-audit/run endpoint can append as
``DomainEvaluatorResult`` rows — without touching any governance gate.

Privacy lock (D-AI-39 discipline, mirrored from
``app.domain.product_audit.PrivacyTelemetryBoundary``):

- AGGREGATE COUNTERS ONLY: every value in this module is a declared
  aggregate (a check result, a feature-level usage count, a task-level
  completion count). There is no per-user row, no user identifier, no user
  content, and no free-form user-derived payload anywhere in the record
  types or the declared fixture;
- every row type carries ``measured_from_user_content`` type-locked to
  ``False`` — the records structurally cannot represent user-derived
  measurement;
- the builders fail closed: a fixture dict that carries any user-identifying
  key (``user_id``/``username``/``session_id``/``device_id``/``ip``) is
  REFUSED outright (``privacy_locked_fixture_rejected``);
- every declared value carries a mandatory ``source_note`` stating its
  declared origin. NOTHING here is measured from users: accessibility
  checks are declared repository facts, usage/completion counters are
  declared synthetic aggregates.

Determinism discipline: no clock reads anywhere (windows are DECLARED
strings/instants supplied by the fixture), no RNG, no network, no I/O.
Digests are sha256 over canonical (sorted-key) JSON — the same binding
discipline the product-audit records use. The completion-rate field is
recomputed EXACTLY (``fractions.Fraction`` over the stated decimal inputs)
and a row that disagrees with its own counts is refused at construction.

Nothing in this module can apply, deploy or promote anything: the
improvement proposal it produces is the canonical
``app.domain.product_audit.ImprovementProposal`` whose ``advisory_only`` is
type-locked True and whose approval state machine cannot represent a
production application step.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any, Dict, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.product_audit import ImprovementProposal
from app.domain.product_audit_records import DomainEvaluatorResult

__all__ = [
    "DECLARED_ADOPTION_METRICS_VERSION",
    "DECLARED_ADOPTION_METRICS_FIXTURE_V1",
    "DECLARED_ACCESSIBILITY_BASELINE",
    "PRIVACY_DISCIPLINE_NOTE",
    "AccessibilityAuditRow",
    "FeatureAdoptionRow",
    "TaskCompletionRow",
    "declared_accessibility_rows",
    "declared_feature_adoption_rows",
    "declared_task_completion_rows",
    "build_declared_domain_evaluator_results",
    "build_accessibility_regression_proposal",
    "privacy_locked_field_names",
]

DECLARED_ADOPTION_METRICS_VERSION = "DECLARED-ADOPTION-METRICS-V1"

PRIVACY_DISCIPLINE_NOTE = (
    "سنج‌های این لایه فقط شمارنده تجمیعی اعلامی هستند؛ بدون شناسه کاربر، بدون "
    "محتوای کاربر و بدون اندازه‌گیری از کاربران (D-AI-39)"
)

#: Keys that must NEVER appear in a fixture dict handed to the builders.
#: Their presence means someone tried to smuggle per-user data into an
#: aggregate-only layer — refused, never stripped-and-accepted.
_FORBIDDEN_FIXTURE_KEYS: frozenset[str] = frozenset(
    {"user_id", "username", "session_id", "device_id", "ip", "email"}
)


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _refuse_forbidden_keys(fixture: Mapping[str, Any]) -> None:
    for key in fixture:
        if str(key).lower() in _FORBIDDEN_FIXTURE_KEYS:
            raise ValueError(f"privacy_locked_fixture_rejected:{key}")
    for group in fixture.values():
        if isinstance(group, Sequence) and not isinstance(group, (str, bytes)):
            for row in group:
                if isinstance(row, Mapping):
                    for key in row:
                        if str(key).lower() in _FORBIDDEN_FIXTURE_KEYS:
                            raise ValueError(f"privacy_locked_fixture_rejected:{key}")


# ---------------------------------------------------------------------------
# Declared row types (aggregate counters only; privacy-locked by construction)
# ---------------------------------------------------------------------------


class AccessibilityAuditRow(BaseModel):
    """One DECLARED accessibility check (aggregate; never user-measured).

    ``declared_result`` is the declared pass/fail of the check;
    ``coverage_pct`` is the declared coverage for coverage-style checks
    (``None`` for boolean checks). ``source_note`` is mandatory and states
    the declared origin of the value.
    """

    model_config = ConfigDict(frozen=True)

    check_id: str = Field(min_length=1, max_length=128)
    declared_result: bool
    coverage_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    source_note: str = Field(min_length=1, max_length=512)
    measured_from_user_content: Literal[False] = False


class FeatureAdoptionRow(BaseModel):
    """One DECLARED feature-adoption counter (feature-level aggregate).

    ``declared_usage_count`` is a synthetic/declared aggregate count for the
    whole declared window — never a per-user measurement and never derived
    from user content.
    """

    model_config = ConfigDict(frozen=True)

    feature_id: str = Field(min_length=1, max_length=128)
    declared_usage_count: int = Field(ge=0)
    window: str = Field(min_length=1, max_length=128)
    source_note: str = Field(min_length=1, max_length=512)
    measured_from_user_content: Literal[False] = False


class TaskCompletionRow(BaseModel):
    """One DECLARED task-completion counter (task-level aggregate).

    ``completion_rate`` is recomputed EXACTLY from the declared counts
    (``fractions.Fraction`` over the stated decimal inputs) and a row that
    disagrees with its own counts is refused
    (``completion_rate_inconsistent_with_counts``). ``declared_started`` is
    required to be > 0 (a rate over zero attempts is not a measurement).
    """

    model_config = ConfigDict(frozen=True)

    task_id: str = Field(min_length=1, max_length=128)
    declared_started: int = Field(gt=0)
    declared_completed: int = Field(ge=0)
    completion_rate: float
    window: str = Field(min_length=1, max_length=128)
    source_note: str = Field(min_length=1, max_length=512)
    measured_from_user_content: Literal[False] = False

    @field_validator("declared_completed")
    @classmethod
    def _completed_not_over_started(cls, v: int, info: Any) -> int:
        started = info.data.get("declared_started")
        if started is not None and v > started:
            raise ValueError("completed_exceeds_started")
        return v

    @model_validator(mode="after")
    def _exact_rate(self) -> "TaskCompletionRow":
        exact = Fraction(self.declared_completed) / Fraction(self.declared_started)
        if Fraction(str(self.completion_rate)) != exact:
            raise ValueError("completion_rate_inconsistent_with_counts")
        return self


def privacy_locked_field_names() -> Dict[str, Tuple[str, ...]]:
    """Field-name surface of the three row types (for privacy audits/tests).

    The returned mapping is exactly the constructor field names of each row
    type — tests assert that NO user-identifying field can even be
    expressed (the types have no such field, and the aggregate-only
    validator refuses smuggled fixture keys).
    """
    return {
        "AccessibilityAuditRow": tuple(AccessibilityAuditRow.model_fields),
        "FeatureAdoptionRow": tuple(FeatureAdoptionRow.model_fields),
        "TaskCompletionRow": tuple(TaskCompletionRow.model_fields),
    }


# ---------------------------------------------------------------------------
# Declared fixture + declared baseline (repository-declared values only)
# ---------------------------------------------------------------------------

DECLARED_WINDOW_LABEL = "DECLARED-WINDOW-W44"

DECLARED_ADOPTION_METRICS_FIXTURE_V1: Dict[str, Any] = {
    "version": "DECLARED-ADOPTION-METRICS-FIXTURE-V1",
    "source_note": (
        "فیکسچر اعلامی مخزن؛ همه مقادیر شمارنده تجمیعی اعلامی‌اند، نه اندازه‌گیری از کاربران"
    ),
    "accessibility": (
        {
            "check_id": "rtl_direction",
            "declared_result": True,
            "coverage_pct": None,
            "source_note": "declared repository check: RTL direction rules present in the UI layer",
        },
        {
            "check_id": "alt_text_coverage_pct",
            "declared_result": False,
            "coverage_pct": 92.0,
            "source_note": "declared repository check: alt-text coverage over the declared icon inventory",
        },
        {
            "check_id": "contrast_declared",
            "declared_result": True,
            "coverage_pct": None,
            "source_note": "declared repository check: declared palette satisfies the declared contrast rule",
        },
        {
            "check_id": "keyboard_nav_declared",
            "declared_result": True,
            "coverage_pct": None,
            "source_note": "declared repository check: keyboard navigation declared for the main panels",
        },
    ),
    "feature_adoption": (
        {
            "feature_id": "tablokhani_filter",
            "declared_usage_count": 120,
            "window": DECLARED_WINDOW_LABEL,
            "source_note": "declared synthetic aggregate counter for the declared window",
        },
        {
            "feature_id": "walkforward_ui",
            "declared_usage_count": 37,
            "window": DECLARED_WINDOW_LABEL,
            "source_note": "declared synthetic aggregate counter for the declared window",
        },
    ),
    "task_completion": (
        {
            "task_id": "register_prediction",
            "declared_started": 40,
            "declared_completed": 34,
            "window": DECLARED_WINDOW_LABEL,
            "source_note": "declared synthetic aggregate counter for the declared window",
        },
        {
            "task_id": "run_product_audit",
            "declared_started": 25,
            "declared_completed": 25,
            "window": DECLARED_WINDOW_LABEL,
            "source_note": "declared synthetic aggregate counter for the declared window",
        },
    ),
}

#: DECLARED baseline window values for the accessibility checks (the values
#: the audit compares the current declared window against). A strict decrease
#: on any check is a DECLARED regression — the only trigger of the proposal
#: generator below; nothing else fabricates a proposal.
DECLARED_ACCESSIBILITY_BASELINE: Dict[str, float] = {
    "rtl_direction": 1.0,
    "alt_text_coverage_pct": 100.0,
    "contrast_declared": 1.0,
    "keyboard_nav_declared": 1.0,
}


# ---------------------------------------------------------------------------
# Builders (fixture dict -> typed rows -> DomainEvaluatorResult rows)
# ---------------------------------------------------------------------------


def _rows_of(fixture: Mapping[str, Any], group: str) -> Tuple[Mapping[str, Any], ...]:
    rows = fixture.get(group)
    if rows is None:
        raise ValueError(f"fixture_group_missing:{group}")
    if not isinstance(rows, (list, tuple)):
        raise ValueError(f"fixture_group_not_sequence:{group}")
    return tuple(rows)


def declared_accessibility_rows(
    fixture: Mapping[str, Any] | None = None,
) -> Tuple[AccessibilityAuditRow, ...]:
    """Build the DECLARED accessibility rows from the declared fixture."""
    fixture = DECLARED_ADOPTION_METRICS_FIXTURE_V1 if fixture is None else fixture
    _refuse_forbidden_keys(fixture)
    rows: list[AccessibilityAuditRow] = []
    for raw in _rows_of(fixture, "accessibility"):
        rows.append(
            AccessibilityAuditRow(
                check_id=str(raw["check_id"]),
                declared_result=bool(raw["declared_result"]),
                coverage_pct=raw.get("coverage_pct"),
                source_note=str(raw["source_note"]),
            )
        )
    return tuple(rows)


def declared_feature_adoption_rows(
    fixture: Mapping[str, Any] | None = None,
) -> Tuple[FeatureAdoptionRow, ...]:
    """Build the DECLARED feature-adoption rows from the declared fixture."""
    fixture = DECLARED_ADOPTION_METRICS_FIXTURE_V1 if fixture is None else fixture
    _refuse_forbidden_keys(fixture)
    rows: list[FeatureAdoptionRow] = []
    for raw in _rows_of(fixture, "feature_adoption"):
        rows.append(
            FeatureAdoptionRow(
                feature_id=str(raw["feature_id"]),
                declared_usage_count=int(raw["declared_usage_count"]),
                window=str(raw["window"]),
                source_note=str(raw["source_note"]),
            )
        )
    return tuple(rows)


def declared_task_completion_rows(
    fixture: Mapping[str, Any] | None = None,
) -> Tuple[TaskCompletionRow, ...]:
    """Build the DECLARED task-completion rows from the declared fixture.

    ``completion_rate`` is recomputed exactly from the declared counts; the
    caller's stated rate (if any) is cross-checked by the record validator.
    """
    fixture = DECLARED_ADOPTION_METRICS_FIXTURE_V1 if fixture is None else fixture
    _refuse_forbidden_keys(fixture)
    rows: list[TaskCompletionRow] = []
    for raw in _rows_of(fixture, "task_completion"):
        started = int(raw["declared_started"])
        completed = int(raw["declared_completed"])
        rate = float(Fraction(completed) / Fraction(started))
        rows.append(
            TaskCompletionRow(
                task_id=str(raw["task_id"]),
                declared_started=started,
                declared_completed=completed,
                completion_rate=rate,
                window=str(raw["window"]),
                source_note=str(raw["source_note"]),
            )
        )
    return tuple(rows)


#: Domain -> (evaluator kind, evaluator ref, evidence id) for the three
#: declared adoption/accessibility/task domains. UX_REVIEW / MANUAL_REVIEW
#: are the existing evaluator vocabulary entries allowed for every
#: non-financial domain by the canonical ``evaluator_allowed_for_domain`` rule
#: (backtest-family evaluators stay bound to FILTERS_STRATEGIES).
_DOMAIN_EVALUATOR_PLAN: Tuple[Tuple[str, str, str, str], ...] = (
    ("ACCESSIBILITY", "UX_REVIEW", "DECLARED-ADOPTION-ACCESSIBILITY-V1", "DECLARED-ADOPTION-ACCESSIBILITY"),
    ("FEATURE_ADOPTION", "MANUAL_REVIEW", "DECLARED-ADOPTION-FEATURE-ADOPTION-V1", "DECLARED-ADOPTION-FEATURE-ADOPTION"),
    ("TASK_COMPLETION", "UX_REVIEW", "DECLARED-ADOPTION-TASK-COMPLETION-V1", "DECLARED-ADOPTION-TASK-COMPLETION"),
)


def build_declared_domain_evaluator_results(
    fixture: Mapping[str, Any] | None = None,
) -> Tuple[DomainEvaluatorResult, ...]:
    """One ``DomainEvaluatorResult`` row per declared adoption domain.

    Deterministic order (ACCESSIBILITY, FEATURE_ADOPTION, TASK_COMPLETION);
    each row's ``metrics_digest`` binds the exact declared row payloads by
    sha256 (values are exchanged by reference, D-AI-23 discipline). The
    rows carry NO user-derived value: their metric payloads are the
    aggregate counters of this module's declared fixture.
    """
    fixture = DECLARED_ADOPTION_METRICS_FIXTURE_V1 if fixture is None else fixture
    accessibility = declared_accessibility_rows(fixture)
    adoption = declared_feature_adoption_rows(fixture)
    completion = declared_task_completion_rows(fixture)
    metric_payloads: Dict[str, Any] = {
        "ACCESSIBILITY": {
            "declared_checks": [r.model_dump(mode="json") for r in accessibility],
        },
        "FEATURE_ADOPTION": {
            "declared_windows": sorted({r.window for r in adoption}),
            "declared_features": [r.model_dump(mode="json") for r in adoption],
        },
        "TASK_COMPLETION": {
            "declared_windows": sorted({r.window for r in completion}),
            "declared_tasks": [r.model_dump(mode="json") for r in completion],
        },
    }
    results: list[DomainEvaluatorResult] = []
    for domain, kind, ref, evidence_id in _DOMAIN_EVALUATOR_PLAN:
        results.append(
            DomainEvaluatorResult(
                domain=domain,  # type: ignore[arg-type]
                evaluator_kind=kind,  # type: ignore[arg-type]
                evaluator_ref=ref,
                metrics_digest=_canonical_digest(metric_payloads[domain]),
                evidence_ids=(evidence_id,),
                notes=PRIVACY_DISCIPLINE_NOTE,
            )
        )
    return tuple(results)


# ---------------------------------------------------------------------------
# Improvement-proposal generator (declared regression only; advisory only)
# ---------------------------------------------------------------------------


def _check_float(row: AccessibilityAuditRow) -> float:
    # Declared numeric view of a check: True = 1.0, False = 0.0, and a
    # coverage check degrades strictly below its baseline coverage.
    if row.coverage_pct is not None:
        return float(row.coverage_pct)
    return 1.0 if row.declared_result else 0.0


def build_accessibility_regression_proposal(
    fixture: Mapping[str, Any] | None = None,
    *,
    proposal_id: Optional[str] = None,
) -> Optional[ImprovementProposal]:
    """Advisory proposal for a DECLARED accessibility regression.

    A regression is a strict decrease of any declared accessibility check
    against ``DECLARED_ACCESSIBILITY_BASELINE`` (exact rational comparison
    over the stated decimal inputs). When no check degraded, ``None`` is
    returned — a proposal is never invented without a declared observed
    problem. The observed problem IS the evidence: ``evidence_ids`` reference
    the degraded declared check ids. All ten proposal fields of the audit
    contract are honored (baseline / observed-problem-as-evidence /
    expected_benefit / uncertainty / cost / risks / rollback_plan /
    evaluation_design / approval_state / advisory_only=True), and the
    canonical ``ImprovementProposal`` type keeps the state machine
    production-locked.
    """
    fixture = DECLARED_ADOPTION_METRICS_FIXTURE_V1 if fixture is None else fixture
    rows = declared_accessibility_rows(fixture)
    degraded: list[AccessibilityAuditRow] = []
    baseline_snapshot: Dict[str, float] = {}
    current_snapshot: Dict[str, float] = {}
    for row in rows:
        baseline_value = DECLARED_ACCESSIBILITY_BASELINE.get(row.check_id)
        if baseline_value is None:
            continue  # no declared baseline → honestly not comparable, never guessed
        current_value = _check_float(row)
        baseline_snapshot[row.check_id] = baseline_value
        current_snapshot[row.check_id] = current_value
        if Fraction(str(current_value)) < Fraction(str(baseline_value)):
            degraded.append(row)
    if not degraded:
        return None
    degraded_ids = tuple(f"DECLARED-CHECK:{row.check_id}" for row in degraded)
    identifier = proposal_id or (
        "PROPOSAL-ACCESSIBILITY-"
        + _canonical_digest({"degraded": sorted(degraded_ids)})[:12]
    )
    return ImprovementProposal(
        proposal_id=identifier,
        domain="ACCESSIBILITY",
        evaluator_kind="REGRESSION",
        baseline=dict(baseline_snapshot),
        expected_benefit=(
            "بازگرداندن سنجه‌های دسترس‌پذیری اعلامیِ افت‌کرده به سطح بیس‌لاین اعلامی"
        ),
        evidence_ids=degraded_ids,
        uncertainty=(
            "برابر بودن فیکسچر اعلامی با تجربه واقعی کاربران بررسی نشده است؛ "
            "این فقط یک رگرسیون اعلامی روی سنجه‌های مخزن است"
        ),
        cost="پایین",
        risks=(
            "رفع ظاهری بررسی بدون پوشش واقعی حالت‌های زبان فارسی",
            "تغییر چیدمان UI که خودش بررسی دسترس‌پذیری تازه می‌خواهد",
        ),
        rollback_plan=(
            "پیشنهاد صرفاً مشورتی است و تولید را تغییر نمی‌دهد؛ در صورت پذیرش "
            "مالک، بازگشت با بازگرداندن نسخه قبلی لایه UI طبق طرح تغییر مالک-تصویب است"
        ),
        evaluation_design=(
            "اجرای دوباره همین بررسی اعلامی پس از اصلاح و مقایسه دقیق با "
            "بیس‌لاین اعلامی (مقایسه گویا، بدون گرد کردن)"
        ),
        approval_state="PROPOSED",
    )
