"""Deterministic research-proposal DRAFTS from prediction evaluations (WP-I).

WAVE-AB5 scope: 06 charter §7 / D-AI-37 — "after maturity the prediction is
compared to reality and error categories/calibration/drift produce research
proposals" that "cannot directly change production logic". This module is
the deterministic draft producer for that clause:

- :func:`derive_research_proposal_draft` maps a ``PredictionEvaluation``'s
  ``error_category`` (closed declared vocabulary below) to a research-
  question draft. Unknown categories map to ``None`` — a draft is never
  invented for an unrecognized error class.
- The draft carries the SAME 10-field discipline as the audit's
  ``ImprovementProposal`` (baseline / observed-problem-as-evidence /
  expected_benefit / uncertainty / cost / risks / rollback_plan /
  evaluation_design / approval_state / advisory_only=True) plus the
  preregistration discipline of 06 §7: ``preregistered`` is type-locked to
  ``False`` — it is a DRAFT until a human preregisters it.

NEVER auto-registered anywhere: this module is PURE. It holds no global
state, exposes no registration/adoption/promotion function, persists
nothing, and the draft's ``approval_state`` is pinned ``DRAFT`` — a state
that cannot represent acceptance. The only runtime surface is the additive
``research_proposal_draft`` field on the
``/api/v10/productloops/predictions/{id}/evaluate`` response (derived from
the returned evaluation; existing response fields untouched).

Evidence discipline: the draft's ``evidence_ids`` reference the evaluation's
own linked records by id (the durable prediction record and the recorded
outcome) — the evaluation's evidence — never synthesized content.

No network, no I/O, no clock reads (the evaluation carries the caller-
supplied instant), no LLM, no RNG.
"""

from __future__ import annotations

from typing import Dict, Literal, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION
from app.domain.prediction import PredictionEvaluation

__all__ = [
    "KNOWN_ERROR_CATEGORIES",
    "PredictionResearchProposalDraft",
    "derive_research_proposal_draft",
]

#: Closed declared mapping of error categories to research-question drafts.
#: Extending this tuple is a deliberate, reviewed change — unknown caller-
#: supplied categories produce NO draft (honest refusal to invent).
KNOWN_ERROR_CATEGORIES: Tuple[str, ...] = (
    "direction-miss",
    "maturity-mismatch",
)

_DIRECTION_MISS_QUESTION = (
    "آیا کالیبراسیون احتمالِ جهتِ سیگنال در پنجره‌های اعلامی بعدی با بازتئین "
    "آستانه جهت بهبود می‌یابد؟ (پیش‌نویس؛ تا پیش‌ثبت انسانی اجرا نمی‌شود)"
)

_MATURITY_MISMATCH_QUESTION = (
    "آیا افق بلوغ اعلامی با زمان واقعی بلوغ برون‌داد هم‌تراز است و تنظیم افق، "
    "خطای ارزیابی را کاهش می‌دهد؟ (پیش‌نویس؛ تا پیش‌ثبت انسانی اجرا نمی‌شود)"
)

_RESEARCH_QUESTION_DRAFTS: Dict[str, Tuple[str, str]] = {
    # error_category -> (research_question, expected_benefit)
    "direction-miss": (
        _DIRECTION_MISS_QUESTION,
        "کاهش نرخ جهت-خطا با کالیبراسیون مجدد آستانه جهت سیگنال",
    ),
    "maturity-mismatch": (
        _MATURITY_MISMATCH_QUESTION,
        "کاهش خطای ارزیابی با هم‌ترازسازی افق بلوغ و زمان واقعی برون‌داد",
    ),
}

_NO_AUTO_ADOPTION_NOTE = (
    "این یک پیش‌نویس تحقیقاتی است؛ هیچ‌گاه به‌طور خودکار ثبت یا اجرا نمی‌شود "
    "(D-AI-37) و تنها با پیش‌ثبت انسانی به یک فرضیه preregistered تبدیل می‌شود"
)


class PredictionResearchProposalDraft(BaseModel):
    """Advisory research-question DRAFT (never auto-registered).

    Field discipline mirrors the audit ``ImprovementProposal`` (10 fields)
    plus the preregistration lock:

    - ``approval_state`` is type-locked to ``DRAFT`` — this record cannot
      represent acceptance, promotion, or application;
    - ``preregistered`` is type-locked to ``False`` — the draft is not a
      preregistered hypothesis until a human preregisters it;
    - ``advisory_only`` is type-locked to ``True`` (D-AI-37: error analysis
      may generate research proposals but cannot change production logic).
    """

    model_config = ConfigDict(frozen=True)

    draft_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    prediction_id: str = Field(min_length=1, max_length=128)
    outcome_id: str = Field(min_length=1, max_length=128)
    error_category: str = Field(min_length=1, max_length=128)
    research_question: str = Field(min_length=1, max_length=2000)
    baseline: Dict[str, float] = Field(default_factory=dict)
    expected_benefit: str = Field(min_length=1)
    evidence_ids: Tuple[str, ...] = Field(min_length=1)
    uncertainty: str = Field(min_length=1)
    cost: str = Field(min_length=1)
    risks: Tuple[str, ...] = Field(min_length=1)
    rollback_plan: str = Field(min_length=1)
    evaluation_design: str = Field(min_length=1)
    approval_state: Literal["DRAFT"] = "DRAFT"
    preregistered: Literal[False] = False
    advisory_only: Literal[True] = True
    notes: str = ""

    @field_validator("error_category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        if v not in KNOWN_ERROR_CATEGORIES:
            raise ValueError("error_category_not_in_draft_vocabulary")
        return v

    @model_validator(mode="after")
    def _evidence_links_the_evaluation(self) -> "PredictionResearchProposalDraft":
        # The draft's evidence IS the evaluation's linked records (by id):
        # the durable prediction record and the recorded outcome. The draft
        # must reference both — never invent other content.
        required = (f"PREDICTION-RECORD:{self.prediction_id}", f"OUTCOME-RECORD:{self.outcome_id}")
        for ref in required:
            if ref not in self.evidence_ids:
                raise ValueError("draft_evidence_must_reference_evaluation_records")
        return self


def derive_research_proposal_draft(
    evaluation: PredictionEvaluation,
) -> PredictionResearchProposalDraft | None:
    """Deterministically draft a research question from one evaluation.

    Returns ``None`` honestly when the evaluation's ``error_category`` is
    ``None`` or outside the declared draft vocabulary — a draft is never
    fabricated for an unrecognized error class. The draft is a pure function
    of the evaluation: the same evaluation yields a byte-identical draft,
    and NOTHING is registered anywhere by this module.
    """
    category = evaluation.error_category
    if category is None or category not in _RESEARCH_QUESTION_DRAFTS:
        return None
    question, benefit = _RESEARCH_QUESTION_DRAFTS[category]
    return PredictionResearchProposalDraft(
        draft_id=f"DRAFT-{evaluation.prediction_id}-{category}",
        prediction_id=evaluation.prediction_id,
        outcome_id=evaluation.outcome_id,
        error_category=category,
        research_question=question,
        # The evaluation's own matched-expectation result is the declared
        # baseline point (single observation; window aggregates are the
        # evaluation design's job — never invented here).
        baseline={"matched_expectation": float(evaluation.matched_expectation)},
        expected_benefit=benefit,
        evidence_ids=(
            f"PREDICTION-RECORD:{evaluation.prediction_id}",
            f"OUTCOME-RECORD:{evaluation.outcome_id}",
        ),
        uncertainty=(
            "یک مشاهده منفرد است؛ تعمیم به پنجره‌های بعدی نیازمند پیش‌ثبت و "
            "گردآوری نمونه اعلامی است"
        ),
        cost="پایین (فقط طراحی پژوهش؛ بدون تغییر تولید)",
        risks=(
            "چند-آزمونی بدون کنترل تعداد فرضیه‌ها",
            "سوگیری انتخاب پس از دیدن برون‌داد (HARKing) که فقط با پیش‌ثبت انسانی مهار می‌شود",
        ),
        rollback_plan=(
            "پیش‌نویس ثبت/اجرای چیزی نیست؛ دورانداختن پیش‌نویس خودِ بازگشت است "
            "و هیچ حالت تولیدی برای بازگرداندن وجود ندارد"
        ),
        evaluation_design=(
            "پیش‌ثبت انسانی فرضیه، سپس ارزیابی روی پنجره‌های بلوغ‌یافته بعدی با "
            "کنترل چند-آزمونی و مقایسه کالیبراسیون پیش/پس"
        ),
        approval_state="DRAFT",
        notes=_NO_AUTO_ADOPTION_NOTE,
    )
