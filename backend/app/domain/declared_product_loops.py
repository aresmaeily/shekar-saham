"""declared_product_loops.py — MASTER-RADAR WAVE-F (2026-11-05) §5
DECLARED product-loop fixtures and manifest (additive, versioned).

This module is the single declared-fixture source for the governed
/api/v10/productloops surface. It closes the WAVE-F residual
"five product loops: no runtime caller" for the closable portion:

  L1 Market Intelligence      — existing /api/ai/market-intelligence surface
                                (consolidated loop view added in the router)
  L2 Company/External Intel   — declared company dossiers + declared quote
                                boards (conflict detection runs live)
  L3 Governed Research        — declared proactive-research job whose
                                permission is evaluated live per request
  L4 Product Intelligence     — declared audit charter + declared baseline
                                window (on-demand audit runs compare against it)
  L5 Prediction Feedback      — no fixture needed (in-process registry),
                                calibration binding helpers only

Honesty envelope (every constant):
- trust class DECLARED (repository-declared fixture) or SYNTHETIC; never LIVE;
- external source admission stays owner-gated (R-3/R-7 Two-Key) — the
  declared dossiers are NOT real filings and never claimed as such;
- no wall clock is read anywhere: instants are fixed declared values and
  every caller-supplied instant is validated, never defaulted;
- no scheduler, no egress, no purge path (R-6/R-9 intact).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Tuple

from app.domain.evidence import Period, SCHEMA_VERSION as EVIDENCE_SCHEMA
from app.domain.evidence_conflicts import detect_quote_conflicts
from app.domain.fundamental_dossier import (
    CompanyDossier,
    CompanyIdentity,
    CorporateActionRecord,
    FilingPeriod,
    FundamentalFact,
)
from app.domain.monitoring import BudgetSpec, RetryPolicy, TriggerSpec
from app.domain.proactive_research import ProactiveResearchJobSpec

DECLARED_SCHEMA = "1.0.0"

DECLARED_NOTE_FA = (
    "تمام داده‌های این حلقه از فیکسچر اعلامی مخزن (DECLARED) می‌آید؛ "
    "زنده نیست و مبنای تصمیم واقعی قرار نگیرد"
)
OWNER_GATE_NOTE = (
    "ورود منابع بیرونی نیازمند تصمیم مالک است (R-3/R-7 Two-Key)؛ "
    "این سطح فقط ماشین‌آلات حاکمیتی را روی فیکسچر اعلامی اجرا می‌کند"
)
NO_SCHEDULER_NOTE = (
    "بدون زمان‌بند و بدون خروج شبکه (R-6/R-9)؛ "
    "هر چرخه صرفاً با فراخوانی صریح فراخوان اجرا می‌شود"
)


def _utc(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# L0 — five-loop manifest (the WAVE-F audit as versioned data)
# ---------------------------------------------------------------------------

PRODUCT_LOOPS_MANIFEST_V1: Tuple[Dict[str, Any], ...] = (
    {
        "loop_id": "L1_MARKET_INTELLIGENCE",
        "title_fa": "نظارت و هوش بازار",
        "title_en": "Market Intelligence",
        "directive_ref": "MASTER DIRECTIVE §5 loop 1",
        "status": "INTEGRATION-VERIFIED",
        "implementation": (
            "app/domain/market_intelligence.py + app/services/"
            "market_intelligence_service.py + /api/ai/market-{intelligence,"
            "regime,opportunities,industries,events} + /api/v10/dataquality "
            "coverage/freshness + alert lifecycle /api/alerts/ops/*"
        ),
        "evidence_refs": (
            "test_market_intelligence_service.py; "
            "test_universe_data_quality.py; WAVE-A record §3.2"
        ),
        "owner_gate_note": None,
        "data_trust": "SYNTHETIC",
    },
    {
        "loop_id": "L2_COMPANY_EXTERNAL_INTELLIGENCE",
        "title_fa": "هوش شرکتی و بیرونی",
        "title_en": "Company / External Intelligence",
        "directive_ref": "MASTER DIRECTIVE §5 loop 2",
        "status": "INTEGRATION-VERIFIED",
        "implementation": (
            "declared_dossiers (this module) + app/domain/"
            "fundamental_dossier.py + app/domain/evidence_conflicts.py + "
            "app/domain/external_intelligence.py intake gates (fail-closed)"
        ),
        "evidence_refs": (
            "test_amendment_p0_dossier_audit_prediction.py; "
            "test_ai6_external_intelligence.py; WAVE-F router tests"
        ),
        "owner_gate_note": OWNER_GATE_NOTE,
        "data_trust": "DECLARED",
    },
    {
        "loop_id": "L3_GOVERNED_RESEARCH",
        "title_fa": "پژوهش حاکمیت‌شده",
        "title_en": "Governed Research",
        "directive_ref": "MASTER DIRECTIVE §5 loop 3",
        "status": "INTEGRATION-VERIFIED",
        "implementation": (
            "declared research job (this module) + app/domain/"
            "proactive_research.py live permission evaluation + app/domain/"
            "evaluation_statistics.py multiplicity-controlled acceptance"
        ),
        "evidence_refs": (
            "test_proactive_research_ledger.py; "
            "test_evaluation_statistics (battery); WAVE-F router tests"
        ),
        "owner_gate_note": (
            "اجرای خودکار چرخه پژوهش نیازمند آزادسازی صریح kill-switch توسط "
            "مالک است؛ AI-2 تولیدکننده غیرفعال و مالک-گیت باقی می‌ماند"
        ),
        "data_trust": "DECLARED",
    },
    {
        "loop_id": "L4_PRODUCT_INTELLIGENCE",
        "title_fa": "هوش محصول (تابلوخوانی)",
        "title_en": "Product Intelligence",
        "directive_ref": "MASTER DIRECTIVE §5 loop 4",
        "status": "INTEGRATION-VERIFIED",
        "implementation": (
            "declared charter + declared baseline window (this module) + "
            "on-demand audit run measuring tablokhani/dataquality/chartpro "
            "in-process + compare_windows drift + advisory proposals"
        ),
        "evidence_refs": (
            "test_product_audit.py; test_product_audit_records.py; "
            "WAVE-F router tests"
        ),
        "owner_gate_note": NO_SCHEDULER_NOTE,
        "data_trust": "DECLARED",
    },
    {
        "loop_id": "L5_PREDICTION_FEEDBACK",
        "title_fa": "بازخورد پیش‌بینی",
        "title_en": "Prediction Feedback",
        "directive_ref": "MASTER DIRECTIVE §5 loop 5",
        "status": "INTEGRATION-VERIFIED",
        "implementation": (
            "app/domain/prediction.py registry (append-only, leakage-guarded) "
            "+ app/domain/calibration_metrics.py Brier/ECE via "
            "build_calibration_record with prediction binding"
        ),
        "evidence_refs": (
            "test_ai7_calibration_contracts.py; test_calibration_metrics.py; "
            "test_amendment_p0_dossier_audit_prediction.py; WAVE-F router tests"
        ),
        "owner_gate_note": (
            "ریجستری فرایند-محلی است؛ پایداری دائمی و اتصال به داده زنده "
            "نیازمند تصمیم مالک است"
        ),
        "data_trust": "SYNTHETIC",
    },
)

MANIFEST_VERSION = "PRODUCT-LOOPS-MANIFEST-V1"
MANIFEST_DECLARED_AT = _utc(2026, 11, 5, 0, 0)


# ---------------------------------------------------------------------------
# L2 — declared company dossiers (synthetic-declared, NOT real filings)
# ---------------------------------------------------------------------------

_DECLARED_COMPANY_A = "DECLARED-COMPANY-A"
_DECLARED_COMPANY_B = "DECLARED-COMPANY-B"

_IDENTITY_A = CompanyIdentity(
    company_id=_DECLARED_COMPANY_A,
    symbols=("فملی",),
    resolution_basis="MANUAL_OWNER_INPUT",
    ambiguity_status="UNAMBIGUOUS",
    resolved_at_utc=_utc(2026, 11, 5),
    source_evidence_ids=("DECLARED-IDENTITY-A",),
)

_PERIOD_Q2_A_V1 = FilingPeriod(
    filing_id="DECLARED-FILING-A-Q2-V1",
    company_id=_DECLARED_COMPANY_A,
    reporting_period=Period(
        period_start=_utc(2025, 7, 1), period_end=_utc(2025, 9, 30)
    ),
    fiscal_calendar="IR_FISCAL_DECLARED_FIXTURE",
    publication_time_utc=_utc(2025, 11, 5, 10, 30),
    publication_status="KNOWN",
    retrieval_time_utc=_utc(2025, 11, 5, 12, 0),
    source_evidence_ids=("DECLARED-EV-A-Q2-V1",),
)

_PERIOD_Q2_A_V2 = FilingPeriod(
    filing_id="DECLARED-FILING-A-Q2-V2",
    company_id=_DECLARED_COMPANY_A,
    reporting_period=Period(
        period_start=_utc(2025, 7, 1), period_end=_utc(2025, 9, 30)
    ),
    fiscal_calendar="IR_FISCAL_DECLARED_FIXTURE",
    publication_time_utc=_utc(2025, 12, 20, 8, 0),
    publication_status="KNOWN",
    retrieval_time_utc=_utc(2025, 12, 20, 9, 0),
    restatement_of="DECLARED-FILING-A-Q2-V1",
    source_evidence_ids=("DECLARED-EV-A-Q2-V2",),
)

_FACT_A_NETINCOME_V1 = FundamentalFact(
    fact_id="DECLARED-FACT-A-NI-V1",
    company_id=_DECLARED_COMPANY_A,
    metric="NET_INCOME_QUARTERLY",
    value=Decimal("1250000000000"),
    value_status="REPORTED",
    unit="IRR",
    currency="IRR",
    period=_PERIOD_Q2_A_V1,
    auditor_status="AUDITED",
    restatement_version=1,
    source_evidence_ids=("DECLARED-EV-A-Q2-V1",),
)

_FACT_A_NETINCOME_V2 = FundamentalFact(
    fact_id="DECLARED-FACT-A-NI-V2",
    company_id=_DECLARED_COMPANY_A,
    metric="NET_INCOME_QUARTERLY",
    value=Decimal("1310000000000"),
    value_status="REPORTED",
    unit="IRR",
    currency="IRR",
    period=_PERIOD_Q2_A_V2,
    auditor_status="AUDITED",
    restatement_version=2,
    supersedes_fact_id="DECLARED-FACT-A-NI-V1",
    source_evidence_ids=("DECLARED-EV-A-Q2-V2",),
)

_FACT_A_FREEFLOAT = FundamentalFact(
    fact_id="DECLARED-FACT-A-FF",
    company_id=_DECLARED_COMPANY_A,
    metric="FREE_FLOAT_PCT",
    value=Decimal("21.4"),
    value_status="REPORTED",
    unit="PERCENT",
    currency="UNITLESS",
    period=_PERIOD_Q2_A_V2,
    auditor_status="UNKNOWN",
    restatement_version=1,
    source_evidence_ids=("DECLARED-EV-A-Q2-V2",),
)

_FACT_A_AUDITFEE_MISSING = FundamentalFact(
    fact_id="DECLARED-FACT-A-AF",
    company_id=_DECLARED_COMPANY_A,
    metric="AUDIT_FEE_TTM",
    value=None,
    value_status="NOT_AVAILABLE",
    unit=None,
    currency=None,
    period=FilingPeriod(
        filing_id="DECLARED-FILING-A-TTM",
        company_id=_DECLARED_COMPANY_A,
        reporting_period=Period(
            period_start=_utc(2025, 1, 1), period_end=_utc(2025, 12, 29)
        ),
        fiscal_calendar="IR_FISCAL_DECLARED_FIXTURE",
        publication_status="UNAVAILABLE",
        source_evidence_ids=("DECLARED-EV-A-TTM",),
    ),
    auditor_status="UNKNOWN",
    restatement_version=1,
    source_evidence_ids=("DECLARED-EV-A-TTM",),
)

_ACTION_A_DIVIDEND = CorporateActionRecord(
    action_id="DECLARED-ACTION-A-DIV1",
    company_id=_DECLARED_COMPANY_A,
    action_type="DIVIDEND",
    publication_time_utc=_utc(2025, 12, 1, 9, 0),
    publication_status="KNOWN",
    effective_date_utc=_utc(2025, 12, 15),
    value=Decimal("850"),
    value_status="REPORTED",
    value_unit="IRR_PER_SHARE",
    source_evidence_ids=("DECLARED-EV-A-DIV1",),
)

_IDENTITY_B = CompanyIdentity(
    company_id=_DECLARED_COMPANY_B,
    symbols=("فولاد",),
    resolution_basis="MANUAL_OWNER_INPUT",
    ambiguity_status="UNAMBIGUOUS",
    resolved_at_utc=_utc(2026, 11, 5),
    source_evidence_ids=("DECLARED-IDENTITY-B",),
)

_PERIOD_Q2_B = FilingPeriod(
    filing_id="DECLARED-FILING-B-Q2",
    company_id=_DECLARED_COMPANY_B,
    reporting_period=Period(
        period_start=_utc(2025, 7, 1), period_end=_utc(2025, 9, 30)
    ),
    fiscal_calendar="IR_FISCAL_DECLARED_FIXTURE",
    publication_time_utc=_utc(2025, 11, 12, 14, 0),
    publication_status="KNOWN",
    retrieval_time_utc=_utc(2025, 11, 12, 15, 0),
    source_evidence_ids=("DECLARED-EV-B-Q2",),
)

_FACT_B_REVENUE = FundamentalFact(
    fact_id="DECLARED-FACT-B-REV",
    company_id=_DECLARED_COMPANY_B,
    metric="REVENUE_QUARTERLY",
    value=Decimal("84200000000000"),
    value_status="REPORTED",
    unit="IRR",
    currency="IRR",
    period=_PERIOD_Q2_B,
    auditor_status="REVIEWED",
    restatement_version=1,
    source_evidence_ids=("DECLARED-EV-B-Q2",),
)

_FACT_B_EQUITY_MISSING = FundamentalFact(
    fact_id="DECLARED-FACT-B-EQ",
    company_id=_DECLARED_COMPANY_B,
    metric="BOOK_EQUITY_QUARTERLY",
    value=None,
    value_status="NOT_AVAILABLE",
    unit=None,
    currency=None,
    period=_PERIOD_Q2_B,
    auditor_status="UNKNOWN",
    restatement_version=1,
    source_evidence_ids=("DECLARED-EV-B-Q2",),
)

_DECLARED_LIMITATIONS: Tuple[str, ...] = (
    "فیکسچر اعلامی است؛ پرونده واقعی نیازمند ورود منابع رسمی با مجوز R-3/R-7 است",
    "طبقه‌بندی نقش‌ها و لایه صنعت در این نسخه اعلامی عرضه نشده است",
    "بدون ساعت دیواری: هر برش PIT تنها با لحظه صریح فراخوان ساخته می‌شود",
)

DOSSIER_SYMBOL_INDEX: Dict[str, str] = {
    "فملی": _DECLARED_COMPANY_A,
    "فولاد": _DECLARED_COMPANY_B,
}

DECLARED_DOSSIERS_VERSION = "DECLARED-DOSSIERS-V1"


def build_declared_dossier(symbol: str, information_cutoff_utc: datetime) -> CompanyDossier:
    """Build the declared dossier for `symbol` bound to the caller's cutoff.

    Deterministic and read-only: the fact/action fixtures are immutable and
    `facts_at_cutoff()` performs the PIT filtering; later-published filings
    are excluded and their count is reported by the router (never silently
    dropped). Unknown symbols raise KeyError.
    """
    company_id = DOSSIER_SYMBOL_INDEX[symbol]
    if company_id == _DECLARED_COMPANY_A:
        identity, facts, actions = (
            _IDENTITY_A,
            (_FACT_A_NETINCOME_V1, _FACT_A_NETINCOME_V2, _FACT_A_FREEFLOAT, _FACT_A_AUDITFEE_MISSING),
            (_ACTION_A_DIVIDEND,),
        )
        missing = ("AUDIT_FEE_TTM: NOT_AVAILABLE در فیکسچر اعلامی",)
    else:
        identity, facts, actions = (
            _IDENTITY_B,
            (_FACT_B_REVENUE, _FACT_B_EQUITY_MISSING),
            (),
        )
        missing = ("BOOK_EQUITY_QUARTERLY: NOT_AVAILABLE در فیکسچر اعلامی",)
    return CompanyDossier(
        dossier_id=f"DECLARED-DOSSIER-{company_id}",
        schema_version=EVIDENCE_SCHEMA,
        company_id=company_id,
        information_cutoff_utc=information_cutoff_utc,
        identity=identity,
        facts=facts,
        corporate_actions=actions,
        roles=(),
        conflicts=(),
        missing_data=missing,
        auditor_opinion=None,
        going_concern_warning=False,
        data_trust_ref="SYNTHETIC/DECLARED (repo fixture; not real filings)",
        pit_eligible=True,
        limitations=_DECLARED_LIMITATIONS,
        notes="WAVE-F declared dossier fixture",
    )


# Declared quote boards (two declared sources) — conflict detection runs LIVE
# in the router via app.domain.evidence_conflicts.detect_quote_conflicts.
DECLARED_QUOTE_BOARDS_VERSION = "DECLARED-QUOTE-BOARDS-V1"
DECLARED_QUOTE_TOL_PCT = "2.0"
_DECLARED_QUOTE_BOARDS: Dict[str, Tuple[Dict[str, Any], ...]] = {
    "DECLARED_SRC_1": (
        {"symbol": "فملی", "last_price": "6120"},
        {"symbol": "فولاد", "last_price": "4830"},
    ),
    "DECLARED_SRC_2": (
        {"symbol": "فملی", "last_price": "6390"},
        {"symbol": "فولاد", "last_price": "4835"},
    ),
}


def declared_conflicts_for_symbol(symbol: str, as_of_utc: datetime) -> Tuple[Any, ...]:
    """Cross-source quote conflicts for one symbol at the caller's instant.

    No wall clock: `as_of_utc` is the caller-supplied instant; the optional
    `now_utc` guard of the engine is deliberately NOT supplied (the engine
    then skips the future-check — its documented behavior).
    """
    boards = {
        source: [row for row in rows if row["symbol"] == symbol]
        for source, rows in _DECLARED_QUOTE_BOARDS.items()
    }
    return tuple(detect_quote_conflicts(boards, tol_pct=DECLARED_QUOTE_TOL_PCT, as_of_utc=as_of_utc))


# ---------------------------------------------------------------------------
# L3 — declared proactive-research job (permission evaluated LIVE per request)
# ---------------------------------------------------------------------------

DECLARED_RESEARCH_JOB_VERSION = "DECLARED-RESEARCH-JOB-V1"
_RESEARCH_RUN_ID = "RUN-DECLARED-RESEARCH-1"

DECLARED_RESEARCH_JOB = ProactiveResearchJobSpec(
    research_job_id="RESEARCH-JOB-DECLARED-1",
    trigger=TriggerSpec(kind="EVENT_DRIVEN", event_types=("OWNER_INITIATED",)),
    retry_policy=RetryPolicy(max_attempts=3, backoff_seconds_base=60),
    budget=BudgetSpec(max_runs_per_hour=2, max_timeout_seconds=60, max_concurrency=1),
    research_questions=(
        "آیا الگوی کشف‌شده روی داده سینتتیک با ارزیابی قطعی بازتولید می‌شود؟",
    ),
    evidence_ref="DECLARED-RESEARCH-EVIDENCE-V1",
    observability_ref="DECLARED-RESEARCH-OBSERVABILITY-V1",
    alerting_ref="DECLARED-RESEARCH-ALERTING-V1",
    kill_switch="ENGAGED",
    notes="WAVE-F declared job: permission evaluated live; nothing is scheduled",
)

DECLARED_RESEARCH_STATE_NOTES = (
    "job هرگز اجرا نشده؛ kill-switch ENGAGED است (R-6) و آزادسازی آن تصمیم مالک است"
)

# Caller-instant-independent fixed declared instant for the run identity
# (the run was never executed; this is the declared contract registration
# instant, not a clock read).
DECLARED_RUN_CREATED_AT = _utc(2026, 11, 5, 0, 0)
DECLARED_POLICY_VERSION = "P0-POLICY-DECLARED-V1"
