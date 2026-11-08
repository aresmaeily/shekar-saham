"""product_loops_api.py — MASTER-RADAR WAVE-F (2026-11-05) §5
Governed product-loop surface (prefix /api/v10/productloops, additive to
the v10 family).

Closes the WAVE-F residual "five product loops: no runtime caller" for the
closable portion, WITHOUT touching any governance gate:

  GET  /manifest                        — five-loop versioned manifest (L0)
  GET  /intel/dossier/{symbol}          — L2 declared dossier at a caller
                                          cutoff (PIT) + live cross-source
                                          quote-conflict detection
  GET  /research/status                 — L3 declared job + LIVE permission
                                          evaluation + AI-2 gate posture
  POST /research/hypotheses/evaluate    — L3 deterministic multiplicity-
                                          controlled acceptance (digest-bound)
  POST /product-audit/run               — L4 on-demand single audit cycle:
                                          3 real in-process probes, drift vs
                                          the declared baseline, advisory
                                          proposals only
  POST /predictions/register            — L5 append-only registry
  POST /predictions/{id}/outcome        — L5 single outcome, look-ahead guarded
  GET  /predictions                     — L5 list with caller-instant maturity
  POST /predictions/{id}/evaluate       — L5 post-maturity evaluation
                                          (label-leakage refusal before it)
  POST /predictions/calibration         — L5 Brier/ECE over pairs bound to
                                          matured predictions
  GET  /predictions/calibration/by-regime — L5 per-regime Brier/ECE over
                                          caller-DECLARED regime labels
                                          (WAVE-AB5 WP-I; empty regimes are
                                          honest empty slices, never fabricated)

Honesty envelope on every payload (same wording discipline as the other
v10 routers, defined locally on purpose):
- data-trust labels come from the server's own trust context or the declared
  fixture constants — never invented client-side;
- every instant is caller-supplied and validated (the server never reads a
  wall clock; durations are monotonic perf_counter deltas only);
- no scheduler, no external egress, no purge path, no live data path
  (R-6/R-9); external source admission stays owner-gated (R-3/R-7);
- process-local state (prediction registry) is non-persistent and disclosed
  as such on every payload that exposes it.

WAVE-J (OA-5, owner directive 2026-11-05): the L5 prediction registry is now
DURABLE by default — the application path uses the SQLite/WAL append-only
store (app/services/prediction_store.py) with row digests, verified
backup/restore and restart recovery. The process-local value object remains
available ONLY as an explicit unit-test adapter (PREDICTION_STORE_BACKEND=
memory). Every L5 payload discloses the effective backend + durability.

Gates unchanged: AI2_ENABLED=0 / verified=False / SYNTHETIC_OR_PAPER.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.chart_pro import chartpro_candles
from app.domain.declared_product_loops import (
    DECLARED_POLICY_VERSION,
    DECLARED_QUOTE_BOARDS_VERSION,
    DECLARED_QUOTE_TOL_PCT,
    DECLARED_RESEARCH_JOB,
    DECLARED_RESEARCH_JOB_VERSION,
    DECLARED_RESEARCH_STATE_NOTES,
    DECLARED_RUN_CREATED_AT,
    DOSSIER_SYMBOL_INDEX,
    MANIFEST_DECLARED_AT,
    MANIFEST_VERSION,
    NO_SCHEDULER_NOTE,
    OWNER_GATE_NOTE,
    PRODUCT_LOOPS_MANIFEST_V1,
    build_declared_dossier,
    declared_conflicts_for_symbol,
)
from app.domain.evaluation_statistics import EvaluationFamily, adjusted_acceptance
from app.domain.calibration_metrics import build_calibration_record
from app.domain.prediction_regime_performance import (
    RegimeBoundPrediction,
    slice_prediction_performance_by_regime,
)
from app.domain.prediction_research_proposals import derive_research_proposal_draft
from app.engines.regime_slices import REGIME_LABELS
from app.domain.prediction import (
    OutcomeRecord,
    PredictionRecord,
    maturity_state,
)
from app.domain.product_audit import (
    AuditCadence,
    ImprovementProposal,
    PrivacyTelemetryBoundary,
    ProductAuditCharter,
)
from app.domain.declared_adoption_metrics import (
    DECLARED_ADOPTION_METRICS_VERSION,
    build_declared_domain_evaluator_results,
)
from app.domain.product_audit_records import (
    CalibrationWindowDigest,
    DomainEvaluatorResult,
    ProductAuditRunRecord,
    WindowMetric,
    compare_windows,
)
from app.domain.proactive_research import (
    ProactiveResearchJobState,
    effective_research_run_permission,
)
from app.domain.run_governance import RunContext, RunProvenance
from app.services import data_quality_service as dq
from app.services.market_service import market_service

router = APIRouter(prefix="/api/v10/productloops")

_SYNTHETIC_NOTE = (
    "تمام رکوردهای این مسیر روی فیکسچر سینتتیک/اعلامی ساخته می‌شوند؛ "
    "زنده نیست و مبنای تصمیم واقعی قرار نگیرد"
)

_DECLARED_CHARTER_VERSION = "AUDIT-CHARTER-DECLARED-V1"
_DECLARED_BASELINE_REF = "DECLARED-BASELINE-WINDOW-V1"
_DECLARED_BASELINE_END = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)
_DECLARED_BASELINE_START = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
_DECLARED_BASELINE_DIGEST = "0" * 64  # declared placeholder baseline (64-hex by schema)
# Baseline values DECLARED at WAVE-F (measured at HEAD during the wave's
# runtime verification; the benchmark test re-measures and asserts equality —
# a capability change honestly shows up as DRIFT and forces re-declaration).
_DECLARED_BASELINE_METRICS: Tuple[WindowMetric, ...] = (
    WindowMetric(name="tablokhani_ranked_rows", value=60.0),
    WindowMetric(name="dataquality_coverage_rows", value=8.0),
    WindowMetric(name="chartpro_candles_rows", value=120.0),
)
_DECLARED_DRIFT_THRESHOLDS: Dict[str, float] = {
    "tablokhani_ranked_rows": 0.0,
    "dataquality_coverage_rows": 0.0,
    "chartpro_candles_rows": 0.0,
}

PROBE_CHART_SYMBOL = "فملی"
PROBE_CHART_TIMEFRAME = "1m"
PROBE_CHART_LIMIT = 120
PROBE_DQ_MARKET = "IRAN_TSE"


def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust": market_service.data_trust_context(),
        "trust_level": market_service.trust_level(),
    }


def _honesty_envelope(*, declared_version: str, extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "declared_version": declared_version,
        "synthetic_note": _SYNTHETIC_NOTE,
        "owner_gate_note": OWNER_GATE_NOTE,
        "no_scheduler_note": NO_SCHEDULER_NOTE,
        "no_wall_clock_note": "هر لحظه زمانی ورودیِ فراخوان است؛ سرور هرگز ساعت دیواری نمی‌خواند",
        "trust_envelope": _trust_envelope(),
    }
    if extras:
        payload.update(extras)
    return payload


def _require_aware(value: Any, field: str) -> datetime:
    """Fail-closed caller-instant validation (tz-aware required)."""
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                422,
                {
                    "error": "MALFORMED_INSTANT",
                    "message_en": f"{field} is not an ISO-8601 instant",
                    "message_fa": f"{field} یک لحظه ISO-8601 معتبر نیست",
                    "field": field,
                },
            ) from None
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise HTTPException(
            422,
            {
                "error": "NAIVE_INSTANT_REFUSED",
                "message_en": f"{field} must carry an explicit UTC offset",
                "message_fa": f"{field} باید آفست صریح UTC داشته باشد",
                "field": field,
            },
        )
    return parsed


def _parse_instant(value: Any, field: str) -> datetime:
    parsed = _require_aware(value, field)
    return parsed.astimezone(timezone.utc)


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _typed_422(code: str, en: str, fa: str, **extra: Any) -> HTTPException:
    detail: Dict[str, Any] = {"error": code, "message_en": en, "message_fa": fa}
    detail.update(extra)
    return HTTPException(422, detail)


# ---------------------------------------------------------------------------
# L0 — manifest
# ---------------------------------------------------------------------------


@router.get("/manifest")
async def loop_manifest() -> Dict[str, Any]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "declared_at_utc": MANIFEST_DECLARED_AT.isoformat(),
        "loops": [dict(loop) for loop in PRODUCT_LOOPS_MANIFEST_V1],
        "honesty": _honesty_envelope(declared_version=MANIFEST_VERSION),
    }


# ---------------------------------------------------------------------------
# L2 — declared dossier + live conflict detection
# ---------------------------------------------------------------------------


@router.get("/intel/dossier/{symbol}")
async def intel_dossier(
    symbol: str,
    cutoff_utc: str = Query(..., description="caller-supplied PIT cutoff instant (ISO-8601)"),
) -> Dict[str, Any]:
    if symbol not in DOSSIER_SYMBOL_INDEX:
        raise HTTPException(
            404,
            {
                "error": "DOSSIER_NOT_DECLARED",
                "message_en": f"no declared dossier for symbol {symbol!r}",
                "message_fa": "پرونده اعلامی برای این نماد وجود ندارد",
                "declared_symbols": sorted(DOSSIER_SYMBOL_INDEX),
            },
        )
    cutoff = _parse_instant(cutoff_utc, "cutoff_utc")
    dossier = build_declared_dossier(symbol, cutoff)
    eligible = dossier.facts_at_cutoff()
    eligible_ids = {f.fact_id for f in eligible}
    excluded: List[Dict[str, Any]] = []
    unavailable: List[str] = []
    for f in dossier.facts:
        if f.fact_id in eligible_ids:
            continue
        available = (
            f.period.publication_time_utc
            if f.period.publication_status == "KNOWN"
            else f.period.retrieval_time_utc
        )
        if available is None:
            unavailable.append(f.fact_id)  # publication/retrieval unknown — disclosed, never silently dropped
        else:
            excluded.append(
                {
                    "fact_id": f.fact_id,
                    "publication_time_utc": available.isoformat(),
                }
            )
    conflicts = declared_conflicts_for_symbol(symbol, cutoff)
    return {
        "symbol": symbol,
        "dossier": dossier.model_dump(mode="json"),
        "pit": {
            "cutoff_utc": cutoff.isoformat(),
            "eligible_fact_ids": [f.fact_id for f in eligible],
            "excluded_later_published": excluded,
            "unavailable_publication_fact_ids": unavailable,
            "note": "حقایق بعد از قطع اطلاعات حذف می‌شوند و شمارشان اعلام می‌گردد؛ انتشار نامشخص در سطل خودش اعلام می‌شود؛ هرگز پرشکاف نمی‌شود",
        },
        "restatement_chain": [
            {
                "fact_id": f.fact_id,
                "restatement_version": f.restatement_version,
                "supersedes_fact_id": f.supersedes_fact_id,
                "value": str(f.value) if f.value is not None else None,
            }
            for f in dossier.facts
            if f.restatement_version > 1 or f.supersedes_fact_id
        ],
        "source_conflicts": {
            "boards_version": DECLARED_QUOTE_BOARDS_VERSION,
            "tol_pct": DECLARED_QUOTE_TOL_PCT,
            "conflicts": [c.model_dump(mode="json") for c in conflicts],
            "note": "کشف تعارض کوتیشن بین دو منبع اعلامی، همان تابع موتور آزمون‌شده است",
        },
        "honesty": _honesty_envelope(declared_version="DECLARED-DOSSIERS-V1"),
    }


# ---------------------------------------------------------------------------
# L3 — governed research status + deterministic hypothesis evaluation
# ---------------------------------------------------------------------------


def _research_job_state() -> ProactiveResearchJobState:
    return ProactiveResearchJobState(
        research_job_id=DECLARED_RESEARCH_JOB.research_job_id,
        notes=DECLARED_RESEARCH_STATE_NOTES,
    )


def _research_run_context() -> RunContext:
    return RunContext(
        run_id="RUN-DECLARED-RESEARCH-1",
        run_kind="RESEARCH_EVALUATION",
        autonomy_level="L0",
        policy_version=DECLARED_POLICY_VERSION,
        created_at_utc=DECLARED_RUN_CREATED_AT,
        notes="declared contract identity; the run was never executed",
    )


def _research_run_provenance() -> RunProvenance:
    # dataset_version deliberately None → the governed permission check
    # reports the real refusal reason (missing_provenance:dataset_version).
    return RunProvenance(
        run_id="RUN-DECLARED-RESEARCH-1",
        policy_version=DECLARED_POLICY_VERSION,
    )


@router.get("/intel/coverage")
async def intel_coverage(
    now_utc: str = Query(..., description="caller-supplied evaluation instant (ISO-8601)"),
) -> Dict[str, Any]:
    """WAVE-AB4 (WP-G/G1): the honest source-coverage report, finally surfaced.

    The audit recorded that CoverageReport/coverage_report_from had ZERO
    production callers. This endpoint folds the DECLARED fixture descriptors
    (all kill switches ENGAGED — nothing is runnable) with the (empty)
    runtime uptime evidence into the verbatim CoverageReport contract.
    Honesty: universal coverage stays structurally false; never-retrieved
    lists every declared source (no retrieval has ever happened); staleness
    is evaluated only against declared freshness targets.
    """
    from app.data.registry_uptime import coverage_report_from
    from app.domain.declared_source_fixtures import (
        DECLARED_SOURCES_VERSION,
        declared_source_descriptors,
    )

    now = _parse_instant(now_utc, "now_utc")
    descriptors = declared_source_descriptors()
    report = coverage_report_from(
        descriptors,
        {},  # no runtime uptime evidence exists — nothing is invented
        now_utc=now,
        known_gaps=(
            "real retrieval requires R-3/R-7 authorization (owner gate)",
            "all declared sources are kill-switch ENGAGED; none runnable",
        ),
    )
    return {
        "ok": True,
        "declared_sources_version": DECLARED_SOURCES_VERSION,
        "report": report.model_dump(mode="json"),
        "runnable_sources": [
            d.source_id for d in descriptors if d.is_runnable()
        ],
        "kill_switch_states": {d.source_id: d.kill_switch for d in descriptors},
        "honesty": {
            "universal_coverage_claimed": False,
            "no_uptime_evidence_invented": "the uptime map is empty; counters are never fabricated",
            "activation": "R-3/R-7 owner gate + per-source kill switch release required",
        },
        "trust_envelope": _trust_envelope(),
    }


@router.get("/goldenset/v2/report")
async def golden_set_v2_report() -> Dict[str, Any]:
    """2026-11-08 owner directive (§3 AI-7) + next-stage item 5b: the
    versioned Golden Set v2 report behind a READ-ONLY endpoint.

    Deterministic (no wall clock, no RNG — the same corpus bytes yield the
    same report), corpus digests pinned and fail-closed, v2 cases run
    against the REAL deterministic engines, baseline (v1 re-verification)
    and candidate (v2) reported SEPARATELY, FP/FN totals included, and the
    structural no-superiority pin carried verbatim (a TabloKhani
    comparative study requires the owner-approved benchmark protocol first).
    """
    from app.services.golden_set_service import GoldenSetReportError, run_golden_set_v2_report

    try:
        payload = run_golden_set_v2_report()
    except GoldenSetReportError as exc:
        raise _typed_422(
            "golden_set_corpus_digest_mismatch",
            str(exc),
            "کورپوس Golden Set با digest پین‌شده مطابقت ندارد (fail-closed)",
        )
    return payload


@router.get("/research/status")
async def research_status() -> Dict[str, Any]:
    from app.core.config import get_settings

    settings = get_settings()
    state = _research_job_state()
    permitted, refusals = effective_research_run_permission(
        DECLARED_RESEARCH_JOB,
        state,
        _research_run_context(),
        _research_run_provenance(),
        autonomy_ceiling="L0",
    )
    return {
        "job": DECLARED_RESEARCH_JOB.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "live_permission_check": {
            "permitted": permitted,
            "refusals": list(refusals),
            "note": "این بررسی زنده است و با هر فراخوان دوباره محاسبه می‌شود؛ هیچ چیزی زمان‌بندی نمی‌شود",
        },
        "ai2_gate": {
            "ai2_enabled": settings.ai2_enabled,
            "posture": "DISABLED_OWNER_GATED" if not settings.ai2_enabled else "ENABLED_UNEXPECTED",
            "note": "تولید استراتژی توسط AI مالک-گیت و قطع است؛ وضعیت WAVE-C معتبر باقی است",
        },
        "honesty": _honesty_envelope(declared_version=DECLARED_RESEARCH_JOB_VERSION),
    }


class HypothesisMemberBody(BaseModel):
    hypothesis_id: str = Field(min_length=1, max_length=128)
    attempt_index: int = Field(ge=1)
    metric_name: str = Field(min_length=1, max_length=128)
    pvalue: float = Field(ge=0.0, le=1.0)


class HypothesisEvaluateBody(BaseModel):
    family_id: str = Field(min_length=1, max_length=128)
    members: List[HypothesisMemberBody] = Field(min_length=1)
    method: Literal["BONFERRONI", "BENJAMIN_HOCHBERG", "NONE"]
    alpha: float


@router.post("/research/hypotheses/evaluate")
async def hypotheses_evaluate(body: HypothesisEvaluateBody) -> Dict[str, Any]:
    families = tuple(
        EvaluationFamily(
            family_id=body.family_id,
            hypothesis_id=m.hypothesis_id,
            attempt_index=m.attempt_index,
            metric_name=m.metric_name,
            pvalue=m.pvalue,
        )
        for m in body.members
    )
    try:
        verdicts = adjusted_acceptance(families, method=body.method, alpha=body.alpha)
    except ValueError as exc:
        raise _typed_422(
            "HYPOTHESIS_EVALUATION_REFUSED",
            str(exc),
            "ارزیابی فرضیه با این ورودی‌ها رد شد",
            reason=str(exc),
        ) from exc
    request_digest = _canonical_digest(body.model_dump(mode="json"))
    return {
        "family_id": body.family_id,
        "verdicts": [v.model_dump(mode="json") for v in verdicts],
        "digest_sha256": request_digest,
        "replay": {
            "note": "همان بدنه با همان ترتیب، همین digest و همان verdict ها را می‌دهد (ارزیابی قطعی)",
            "method": body.method,
            "alpha": body.alpha,
        },
        "honesty": _honesty_envelope(declared_version=DECLARED_RESEARCH_JOB_VERSION),
    }


# ---------------------------------------------------------------------------
# L4 — on-demand product audit run
# ---------------------------------------------------------------------------


async def _probe_tablokhani() -> Tuple[WindowMetric, Dict[str, Any]]:
    """REAL TabloKhani capability probe: ensure the seeded market snapshot is
    loaded, then count the ranked TabloKhani rows (deterministic fixture)."""
    started = time.perf_counter()
    await market_service.get_analysis(force=False)
    ranked = market_service.get_tablocastic(limit=200, min_quality=0)
    rows = float(len(ranked))
    payload_digest = _canonical_digest(ranked)
    latency_ms = (time.perf_counter() - started) * 1000.0
    return (
        WindowMetric(name="tablokhani_ranked_rows", value=rows),
        {"digest_sha256": payload_digest, "latency_ms": latency_ms},
    )


def _probe_dataquality() -> Tuple[WindowMetric, Dict[str, Any]]:
    started = time.perf_counter()
    payload = dq.market_coverage(PROBE_DQ_MARKET)
    rows = float(len(payload["symbols"]))
    payload_digest = _canonical_digest(
        {"market": PROBE_DQ_MARKET, "trust_class": payload.get("trust_class"), "n": rows}
    )
    latency_ms = (time.perf_counter() - started) * 1000.0
    return (
        WindowMetric(name="dataquality_coverage_rows", value=rows),
        {"market": PROBE_DQ_MARKET, "digest_sha256": payload_digest, "latency_ms": latency_ms},
    )


async def _probe_chartpro() -> Tuple[WindowMetric, Dict[str, Any]]:
    started = time.perf_counter()
    payload = await chartpro_candles(
        symbol=PROBE_CHART_SYMBOL, timeframe=PROBE_CHART_TIMEFRAME, limit=PROBE_CHART_LIMIT
    )
    rows = float(payload["count"])
    payload_digest = _canonical_digest(payload["ohlcv"])
    latency_ms = (time.perf_counter() - started) * 1000.0
    return (
        WindowMetric(name="chartpro_candles_rows", value=rows),
        {"digest_sha256": payload_digest, "latency_ms": latency_ms},
    )


class AuditRunBody(BaseModel):
    window_start_utc: str = Field(min_length=1)
    window_end_utc: str = Field(min_length=1)


def _declared_charter() -> ProductAuditCharter:
    # WAVE-AB5 (WP-H): the declared charter gains the three AI-7 evaluation
    # domains that had NO code (accessibility / feature adoption / task
    # completion) — additive only; cadences stay non-SCHEDULED (R-6) and the
    # telemetry boundary below is unchanged (aggregate counters only).
    return ProductAuditCharter(
        charter_version=_DECLARED_CHARTER_VERSION,
        domains=(
            "FILTERS_STRATEGIES",
            "PRODUCT_UX",
            "SOFTWARE_QUALITY",
            "ACCESSIBILITY",
            "FEATURE_ADOPTION",
            "TASK_COMPLETION",
        ),
        cadences=(
            AuditCadence(domain="FILTERS_STRATEGIES", mode="EVENT_DRIVEN"),
            AuditCadence(domain="PRODUCT_UX", mode="OWNER_CONFIGURED", cadence_expression="owner-set; unset in this declared charter"),
            AuditCadence(domain="SOFTWARE_QUALITY", mode="EVENT_DRIVEN"),
            AuditCadence(domain="ACCESSIBILITY", mode="EVENT_DRIVEN"),
            AuditCadence(domain="FEATURE_ADOPTION", mode="EVENT_DRIVEN"),
            AuditCadence(domain="TASK_COMPLETION", mode="EVENT_DRIVEN"),
        ),
        telemetry_boundary=PrivacyTelemetryBoundary(
            data_classes=("AGGREGATE_COUNTERS", "ROW_COUNTS", "LATENCY"),
            lawful_basis="declared product-quality audit over synthetic/declared data only",
            access_control="operator (same process)",
            retention_rule="process-local; never persisted",
            deletion_rule="cleared when the process exits",
        ),
        baseline_metrics_ref=_DECLARED_BASELINE_REF,
        notes="no SCHEDULED cadence is declared anywhere (R-6); runs are caller-initiated only",
    )


@router.post("/product-audit/run")
async def product_audit_run(body: AuditRunBody) -> Dict[str, Any]:
    start = _parse_instant(body.window_start_utc, "window_start_utc")
    end = _parse_instant(body.window_end_utc, "window_end_utc")
    if end < start:
        raise _typed_422(
            "WINDOW_END_BEFORE_START",
            "window_end_utc must not precede window_start_utc",
            "پایان پنجره نمی‌تواند قبل از شروع آن باشد",
        )
    baseline_window = CalibrationWindowDigest(
        window_start_utc=_DECLARED_BASELINE_START,
        window_end_utc=_DECLARED_BASELINE_END,
        digest=_DECLARED_BASELINE_DIGEST,
        metric_values=_DECLARED_BASELINE_METRICS,
    )
    if end < baseline_window.window_end_utc:
        raise _typed_422(
            "WINDOW_NOT_PIT_ORDERED",
            "window_end_utc must not precede the declared baseline window end",
            "پایان پنجره نمی‌تواند قبل از پایان پنجره بیس‌لاین اعلامی باشد",
            baseline_end_utc=baseline_window.window_end_utc.isoformat(),
        )
    probe_tab, detail_tab = await _probe_tablokhani()
    probe_dq, detail_dq = _probe_dataquality()
    probe_chart, detail_chart = await _probe_chartpro()
    metrics = (probe_tab, probe_dq, probe_chart)
    current_window = CalibrationWindowDigest(
        window_start_utc=start,
        window_end_utc=end,
        digest=_canonical_digest(
            {"tab": detail_tab, "dq": detail_dq, "chart": detail_chart}
        ),
        metric_values=metrics,
    )
    try:
        drift = compare_windows(baseline_window, current_window, thresholds=_DECLARED_DRIFT_THRESHOLDS)
    except ValueError as exc:
        raise _typed_422(
            "DRIFT_COMPARISON_REFUSED",
            str(exc),
            "مقایسه drift رد شد",
            reason=str(exc),
        ) from exc
    proposals: Tuple[ImprovementProposal, ...] = ()
    if drift.drift_verdict == "DRIFT_DETECTED":
        drifted_names = [r.name for r in drift.metric_assessments if r.verdict == "DRIFTED"]
        proposals = (
            ImprovementProposal(
                proposal_id="PROPOSAL-" + _canonical_digest({"drifted": drifted_names, "window": current_window.digest})[:12],
                domain="SOFTWARE_QUALITY",
                evaluator_kind="REGRESSION",
                expected_benefit="بازگرداندن سنجه‌های کشف‌شده به بازه بیس‌لاین اعلامی",
                evidence_ids=tuple(sorted(drifted_names)),
                uncertainty="drift روی شمارش ردیف‌های سینتتیک؛ علت نیازمند بررسی است",
                cost="پایین",
                rollback_plan="بی‌نیاز است؛ پیشنهاد صرفاً مشورتی است و تولید را تغییر نمی‌دهد",
                evaluation_design="اجرای دوباره ممیزی پس از بررسی و مقایسه با بیس‌لاین اعلامی",
            ),
        )
    # WAVE-AB5 (WP-H): the run appends the three declared adoption/accessibility/
    # task-completion DomainEvaluatorResult rows built from the DECLARED fixture
    # (aggregate counters only, no user content, no user ids). The three real
    # in-process probes above are untouched. UX_REVIEW/MANUAL_REVIEW are the
    # existing evaluator vocabulary entries allowed for these domains by the
    # canonical evaluator_allowed_for_domain rule (06 charter §8). The declared
    # accessibility-regression proposal generator stays at the module layer
    # (see declared_adoption_metrics.build_accessibility_regression_proposal) —
    # this endpoint only appends the evaluator rows, keeping the pinned
    # drift/proposal behavior of the run unchanged.
    declared_domain_results: Tuple[DomainEvaluatorResult, ...] = (
        build_declared_domain_evaluator_results()
    )
    run_record = ProductAuditRunRecord(
        run_record_id="RUNREC-" + current_window.digest[:12],
        run_id="AUDIT-RUN-" + current_window.digest[:12],
        charter_version=_DECLARED_CHARTER_VERSION,
        executed_at_utc=end,
        domain_results=declared_domain_results,
        proposal_ids=tuple(p.proposal_id for p in proposals),
        advisory_only=True,
        data_class="SYNTHETIC",
        notes=(
            "on-demand single cycle; no scheduler (R-6); executed_at_utc is the "
            "caller-supplied window end (no wall clock)"
        ),
    )
    return {
        "run_record": run_record.model_dump(mode="json"),
        "charter": _declared_charter().model_dump(mode="json"),
        "baseline_ref": _DECLARED_BASELINE_REF,
        "probe_details": {
            "tablokhani": detail_tab,
            "dataquality": detail_dq,
            "chartpro": detail_chart,
        },
        "drift": drift.model_dump(mode="json"),
        "declared_adoption_domains": {
            "declared_version": DECLARED_ADOPTION_METRICS_VERSION,
            "domains": [r.domain for r in declared_domain_results],
            "privacy_note": (
                "شمارنده‌های تجمیعی اعلامی؛ بدون شناسه کاربر و بدون محتوای کاربر"
            ),
        },
        "honesty": _honesty_envelope(declared_version=_DECLARED_CHARTER_VERSION),
    }


# ---------------------------------------------------------------------------
# L5 — prediction feedback (durable append-only registry, OA-5 / WAVE-J)
# ---------------------------------------------------------------------------

from app.services.prediction_store import (  # noqa: E402
    RETENTION_POLICY,
    get_prediction_store,
)


class PredictionRegisterBody(BaseModel):
    prediction_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    registered_at_utc: str = Field(min_length=1)
    outcome_horizon_end_utc: str = Field(min_length=1)
    evaluation_metric: str = Field(min_length=1)
    event_maturity_rule: str = Field(min_length=1)
    invalidation_rule: str = Field(min_length=1)
    evidence_ids: List[str] = Field(min_length=1)
    creator: str = Field(min_length=1)
    notes: str = ""


@router.post("/predictions/register")
async def predictions_register(body: PredictionRegisterBody) -> Dict[str, Any]:
    store = get_prediction_store()
    try:
        record = PredictionRecord(
            prediction_id=body.prediction_id,
            subject=body.subject,
            registered_at_utc=_parse_instant(body.registered_at_utc, "registered_at_utc"),
            outcome_horizon_end_utc=_parse_instant(body.outcome_horizon_end_utc, "outcome_horizon_end_utc"),
            evaluation_metric=body.evaluation_metric,
            event_maturity_rule=body.event_maturity_rule,
            invalidation_rule=body.invalidation_rule,
            evidence_ids=tuple(body.evidence_ids),
            creator=body.creator,
            notes=body.notes,
        )
        result = store.register_prediction(record)
    except ValueError as exc:
        raise _typed_422(
            "PREDICTION_REGISTRATION_REFUSED",
            str(exc),
            "ثبت پیش‌بینی رد شد",
            reason=str(exc),
        ) from exc
    return {
        "registered": record.model_dump(mode="json"),
        "registry_version": result["registry_version"],
        "duplicate_of_existing": result.get("duplicate_of_existing", False),
        "persistence_note": store.persistence_note,
        "persistence_backend": store.backend_label,
        "persistence_durable": store.persistence_durable,
        "retention_policy": RETENTION_POLICY,
        "honesty": _honesty_envelope(declared_version="PREDICTION-REGISTRY-V1"),
    }


class PredictionOutcomeBody(BaseModel):
    outcome_id: str = Field(min_length=1)
    observed_at_utc: str = Field(min_length=1)
    observed_value: Optional[str] = None
    observed_numeric: Optional[float] = None
    source_evidence_ids: List[str] = Field(min_length=1)
    notes: str = ""


@router.post("/predictions/{prediction_id}/outcome")
async def predictions_outcome(prediction_id: str, body: PredictionOutcomeBody) -> Dict[str, Any]:
    store = get_prediction_store()
    try:
        outcome = OutcomeRecord(
            outcome_id=body.outcome_id,
            prediction_id=prediction_id,
            observed_at_utc=_parse_instant(body.observed_at_utc, "observed_at_utc"),
            observed_value=body.observed_value,
            observed_numeric=body.observed_numeric,
            source_evidence_ids=tuple(body.source_evidence_ids),
            notes=body.notes,
        )
        result = store.attach_outcome(outcome)
    except ValueError as exc:
        raise _typed_422(
            "OUTCOME_REFUSED",
            str(exc),
            "ثبت برون‌داد رد شد",
            reason=str(exc),
        ) from exc
    return {
        "outcome": outcome.model_dump(mode="json"),
        "registry_version": result["registry_version"],
        "persistence_note": store.persistence_note,
        "persistence_backend": store.backend_label,
        "persistence_durable": store.persistence_durable,
        "retention_policy": RETENTION_POLICY,
        "honesty": _honesty_envelope(declared_version="PREDICTION-REGISTRY-V1"),
    }


@router.get("/predictions")
async def predictions_list(as_of_utc: str = Query(..., description="caller instant for maturity")) -> Dict[str, Any]:
    as_of = _parse_instant(as_of_utc, "as_of_utc")
    store = get_prediction_store()
    rows = []
    for entry in store.list_rows():
        record = entry["prediction"]
        outcome = entry["outcome"]
        rows.append(
            {
                "prediction": record.model_dump(mode="json"),
                "maturity_state": maturity_state(record, as_of),
                "has_outcome": outcome is not None,
                "outcome_id": outcome.outcome_id if outcome else None,
            }
        )
    return {
        "as_of_utc": as_of.isoformat(),
        "registry_version": store.registry_version,
        "count": len(rows),
        "rows": rows,
        "persistence_note": store.persistence_note,
        "persistence_backend": store.backend_label,
        "persistence_durable": store.persistence_durable,
        "retention_policy": RETENTION_POLICY,
        "honesty": _honesty_envelope(declared_version="PREDICTION-REGISTRY-V1"),
    }


class PredictionEvaluateBody(BaseModel):
    matched_expectation: bool
    error_category: Optional[str] = None
    calibration_note: Optional[str] = None
    notes: str = ""


@router.post("/predictions/{prediction_id}/evaluate")
async def predictions_evaluate(
    prediction_id: str,
    body: PredictionEvaluateBody,
    as_of_utc: str = Query(..., description="caller instant; evaluation is refused before maturity"),
) -> Dict[str, Any]:
    as_of = _parse_instant(as_of_utc, "as_of_utc")
    store = get_prediction_store()
    try:
        evaluation, registry_version = store.evaluate(
            prediction_id,
            as_of=as_of,
            matched_expectation=body.matched_expectation,
            error_category=body.error_category,
            calibration_note=body.calibration_note,
            notes=body.notes,
        )
    except ValueError as exc:
        raise _typed_422(
            "PREDICTION_EVALUATION_REFUSED",
            str(exc),
            "ارزیابی پیش‌بینی رد شد (نگهبانی نشت برچسب)",
            reason=str(exc),
        ) from exc
    # WAVE-AB5 (WP-I, additive): a DETERMINISTIC research-proposal DRAFT is
    # derived from the returned evaluation when its error_category maps to
    # the declared draft vocabulary — never auto-registered anywhere
    # (preregistered=False, advisory_only=True, approval_state pinned DRAFT).
    # Existing response fields are untouched; the field is None when no draft
    # is derivable (unknown/absent error category → no draft invented).
    research_proposal_draft = derive_research_proposal_draft(evaluation)
    return {
        "evaluation": evaluation.model_dump(mode="json"),
        "research_proposal_draft": (
            research_proposal_draft.model_dump(mode="json")
            if research_proposal_draft is not None
            else None
        ),
        "registry_version": registry_version,
        "persistence_note": store.persistence_note,
        "persistence_backend": store.backend_label,
        "persistence_durable": store.persistence_durable,
        "honesty": _honesty_envelope(declared_version="PREDICTION-REGISTRY-V1"),
    }


class CalibrationPairBody(BaseModel):
    prediction_id: str = Field(min_length=1)
    predicted_probability: float = Field(ge=0.0, le=1.0)
    observed: float = Field(ge=0.0, le=1.0)


class PredictionCalibrationBody(BaseModel):
    pairs: List[CalibrationPairBody] = Field(min_length=1)
    bucket_count: int = Field(default=10, ge=2, le=32)
    coverage_complete: bool = True
    coverage_gaps: List[str] = Field(default_factory=list)
    calibration_note: str = ""


@router.post("/predictions/calibration")
async def predictions_calibration(
    body: PredictionCalibrationBody,
    measured_at_utc: str = Query(..., description="caller instant; immature predictions are refused"),
) -> Dict[str, Any]:
    measured_at = _parse_instant(measured_at_utc, "measured_at_utc")
    store = get_prediction_store()
    pairs = []
    records = []
    for item in body.pairs:
        record = store.get_prediction(item.prediction_id)
        if record is None:
            raise _typed_422(
                "UNKNOWN_PREDICTION_ID",
                f"unknown prediction id {item.prediction_id!r}",
                "شناسه پیش‌بینی ناشناخته است",
                prediction_id=item.prediction_id,
            )
        if store.get_outcome(item.prediction_id) is None:
            raise _typed_422(
                "OUTCOME_NOT_RECORDED",
                f"prediction {item.prediction_id!r} has no recorded outcome",
                "برون‌داد این پیش‌بینی ثبت نشده است",
                prediction_id=item.prediction_id,
            )
        # PIT discipline: an outcome observed AFTER the measurement instant
        # cannot be known at that instant — refuse (no look-ahead).
        outcome = store.get_outcome(item.prediction_id)
        if outcome is not None and outcome.observed_at_utc > measured_at:
            raise _typed_422(
                "OUTCOME_AFTER_MEASUREMENT_REFUSED",
                f"outcome for {item.prediction_id!r} was observed after the measurement instant",
                "برون‌داد بعد از لحظه اندازه‌گیری مشاهده شده است (نگهبانی آینده‌نگری)",
                prediction_id=item.prediction_id,
                observed_at_utc=outcome.observed_at_utc.isoformat(),
                measured_at_utc=measured_at.isoformat(),
            )
        # parse_pairs accepts int 0/1 (or bool) as the binary outcome — a
        # float 1.0 is refused by the engine, so integral values are passed
        # as ints and anything else goes through for the engine's refusal.
        observed_raw = int(item.observed) if item.observed in (0.0, 1.0) else item.observed
        pairs.append((item.predicted_probability, observed_raw))
        records.append(record)
    try:
        calibration = build_calibration_record(
            calibration_id="CAL-" + _canonical_digest(body.model_dump(mode="json"))[:12],
            subject_kind="PREDICTION",
            subject_ref="PREDICTION-REGISTRY",
            pairs=pairs,
            measured_at_utc=measured_at,
            data_class="SYNTHETIC",
            evidence_ref="PREDICTION-REGISTRY-V1",
            bucket_count=body.bucket_count,
            coverage_complete=body.coverage_complete,
            coverage_gaps=tuple(body.coverage_gaps),
            prediction_records=tuple(records),
            calibration_note=body.calibration_note,
        )
    except ValueError as exc:
        raise _typed_422(
            "CALIBRATION_REFUSED",
            str(exc),
            "محاسبه کالیبراسیون رد شد",
            reason=str(exc),
        ) from exc
    return {
        "calibration": calibration.model_dump(mode="json"),
        "persistence_note": store.persistence_note,
        "persistence_backend": store.backend_label,
        "persistence_durable": store.persistence_durable,
        "retention_policy": RETENTION_POLICY,
        "honesty": _honesty_envelope(declared_version="PREDICTION-REGISTRY-V1"),
    }


@router.get("/predictions/calibration/by-regime")
async def predictions_calibration_by_regime(
    measured_at_utc: str = Query(..., description="caller instant; outcomes after it are refused (no look-ahead)"),
    regime_labels: str = Query(..., description="JSON array of regime labels from the closed vocabulary"),
    assignments: str = Query("[]", description="JSON array of {prediction_id, regime_label, predicted_probability, observed}"),
    bucket_count: int = Query(10, ge=2, le=32),
) -> Dict[str, Any]:
    """WAVE-AB5 (WP-I): regime-sliced prediction performance (02:145 P3).

    Per-regime Brier/ECE over matured+evaluated predictions, bound to
    CALLER-DECLARED regime labels from the closed ``regime_slices``
    vocabulary — regimes are never inferred from data. Every assignment is
    validated against the durable store exactly like ``/predictions/calibration``
    (prediction exists, outcome recorded, PIT-ordered vs the caller instant)
    PLUS the evaluated-prediction binding (``PREDICTION_NOT_EVALUATED``).
    A declared regime with no bound predictions is an honest EMPTY slice
    with a reason — never fabricated. An empty registry/assignment set
    yields the honest empty payload (empty slices, nothing invented).
    """
    measured_at = _parse_instant(measured_at_utc, "measured_at_utc")

    def _parse_json_list(raw: str, field: str, error_code: str, fa: str) -> List[Any]:
        try:
            parsed = json.loads(raw)
        except ValueError:
            raise _typed_422(error_code, f"{field} is not valid JSON", fa, field=field) from None
        if not isinstance(parsed, list):
            raise _typed_422(
                error_code, f"{field} must be a JSON array", fa, field=field
            )
        return parsed

    raw_labels = _parse_json_list(
        regime_labels,
        "regime_labels",
        "MALFORMED_REGIME_LABELS",
        "برچسب‌های رژیم JSON معتبر نیست",
    )
    for label in raw_labels:
        if not isinstance(label, str) or label not in REGIME_LABELS:
            raise _typed_422(
                "UNKNOWN_REGIME_LABEL",
                f"regime label {label!r} is outside the closed vocabulary {list(REGIME_LABELS)}",
                "برچسب رژیم خارج از واژگان بسته است",
                regime_label=label if isinstance(label, str) else None,
            )
    raw_assignments = _parse_json_list(
        assignments,
        "assignments",
        "MALFORMED_REGIME_ASSIGNMENTS",
        "تخصیص‌های رژیم JSON معتبر نیست",
    )

    store = get_prediction_store()
    evaluated_ids = {e.prediction_id for e in store.list_evaluations()}
    bound: List[RegimeBoundPrediction] = []
    for item in raw_assignments:
        if not isinstance(item, dict):
            raise _typed_422(
                "MALFORMED_REGIME_ASSIGNMENT_ROW",
                "each assignment must be a JSON object",
                "هر تخصیص باید یک شیء JSON باشد",
            )
        missing = [
            key
            for key in ("prediction_id", "regime_label", "predicted_probability", "observed")
            if key not in item
        ]
        if missing:
            raise _typed_422(
                "MALFORMED_REGIME_ASSIGNMENT_ROW",
                f"assignment missing required keys {missing}",
                "تخصیص کلیدهای لازم را ندارد",
                missing=missing,
            )
        prediction_id = str(item["prediction_id"])
        label = item["regime_label"]
        if not isinstance(label, str) or label not in REGIME_LABELS:
            raise _typed_422(
                "UNKNOWN_REGIME_LABEL",
                f"assignment regime label {label!r} is outside the closed vocabulary",
                "برچسب رژیم تخصیص خارج از واژگان بسته است",
                prediction_id=prediction_id,
            )
        if prediction_id not in evaluated_ids:
            # Honest, ordered store checks: unknown id first (same shapes as
            # /predictions/calibration), then the evaluated-prediction gate.
            if store.get_prediction(prediction_id) is None:
                raise _typed_422(
                    "UNKNOWN_PREDICTION_ID",
                    f"unknown prediction id {prediction_id!r}",
                    "شناسه پیش‌بینی ناشناخته است",
                    prediction_id=prediction_id,
                )
            raise _typed_422(
                "PREDICTION_NOT_EVALUATED",
                f"prediction {prediction_id!r} has no recorded post-maturity evaluation",
                "این پیش‌بینی پس از بلوغ ارزیابی نشده است",
                prediction_id=prediction_id,
            )
        if store.get_outcome(prediction_id) is None:
            raise _typed_422(
                "OUTCOME_NOT_RECORDED",
                f"prediction {prediction_id!r} has no recorded outcome",
                "برون‌داد این پیش‌بینی ثبت نشده است",
                prediction_id=prediction_id,
            )
        outcome = store.get_outcome(prediction_id)
        if outcome is not None and outcome.observed_at_utc > measured_at:
            raise _typed_422(
                "OUTCOME_AFTER_MEASUREMENT_REFUSED",
                f"outcome for {prediction_id!r} was observed after the measurement instant",
                "برون‌داد بعد از لحظه اندازه‌گیری مشاهده شده است (نگهبانی آینده‌نگری)",
                prediction_id=prediction_id,
                observed_at_utc=outcome.observed_at_utc.isoformat(),
                measured_at_utc=measured_at.isoformat(),
            )
        try:
            bound.append(
                RegimeBoundPrediction(
                    prediction_id=prediction_id,
                    regime_label=label,  # type: ignore[arg-type]
                    predicted_probability=float(item["predicted_probability"]),
                    observed=item["observed"],
                )
            )
        except (TypeError, ValueError) as exc:
            raise _typed_422(
                "REGIME_ASSIGNMENT_REFUSED",
                str(exc),
                "تخصیص رژیم با این مقادیر رد شد",
                prediction_id=prediction_id,
                reason=str(exc),
            ) from exc

    try:
        regime_table = slice_prediction_performance_by_regime(
            bound, raw_labels, bucket_count=bucket_count
        )
    except ValueError as exc:
        raise _typed_422(
            "REGIME_PERFORMANCE_REFUSED",
            str(exc),
            "برش رژیمی عملکرد پیش‌بینی رد شد",
            reason=str(exc),
        ) from exc

    return {
        "measured_at_utc": measured_at.isoformat(),
        "declared_labels": list(raw_labels),
        "bucket_count": bucket_count,
        "assignment_count": len(bound),
        "evaluated_predictions_in_registry": len(evaluated_ids),
        "regime_table": [row.model_dump(mode="json") for row in regime_table],
        "empty_registry_note": (
            "هیچ ارزیابی پس از بلوغ در ریجستری وجود ندارد؛ جدول رژیم خالی و صادقانه است"
            if not evaluated_ids
            else None
        ),
        "persistence_note": store.persistence_note,
        "persistence_backend": store.backend_label,
        "persistence_durable": store.persistence_durable,
        "retention_policy": RETENTION_POLICY,
        "trust_envelope": _trust_envelope(),
        "honesty": _honesty_envelope(declared_version="PREDICTION-REGISTRY-V1"),
    }
