"""Golden Set v2 versioned read-only report service (2026-11-08 owner
directive §3 AI-7: «تکمیل Golden Set» + next-stage item 5b: the versioned
report surfaces at runtime behind a read-only endpoint).

Deterministic and read-only: the pinned runtime corpora (``data/golden_set/``)
are byte-verified against the SAME reference digests the test suite pins, the
v2 cases run against the REAL deterministic engines (no mocks, no network),
and the report separates baseline (v1 re-verification) from candidate (v2
run) WITHOUT any superiority claim (structural ``superiority_claimed=False``;
06:104 discipline). No wall clock, no RNG: identical bytes in → identical
report out (double-run equality pinned by test).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

# The versioned corpora ship as MODULE RESOURCES (backend/app/data/) so the
# packaged desktop app carries them — not the runtime DATA_DIR (which is
# machine state). Digests are pinned; a drifted corpus fails closed.
_CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "golden_set"
from app.domain.ai_intelligence import AIIntelligenceCore
from app.domain.calibration_metrics import build_calibration_record
from app.domain.evidence import EvidenceConflict, EvidenceItem
from app.domain.evidence_resolution import (
    ResolutionRefusal,
    resolve_conflict_by_precedence,
)
from app.domain.filing_extraction import (
    DeclaredFilingDocument,
    extract_filing_document,
)
from app.domain.golden_set import (
    GoldenSetIntegrityError,
    parse_golden_set_version,
)
from app.domain.golden_set_v2 import (
    GoldenV2CaseResult,
    GoldenV2Version,
    build_v2_report,
    classify_interpretation_result,
    parse_golden_set_v2_payload,
)
from app.engines.regime_slices import slice_by_regime


V1_PATH = _CORPUS_DIR / "golden_set_v1.json"
V2_PATH = _CORPUS_DIR / "golden_set_v2.json"

#: Runtime reference digests — MUST equal the test-suite pins (a mismatch is
#: a deliberate corpus change that failed to update one side: fail closed).
GOLDEN_SET_V2_REFERENCE_DIGESTS = {
    "golden_set_v2.json.file": "085cadd0d48324e7cd37bcb018e4ee019b68f9a740fcf19988e7d83547d8709f",
    "GS2-2026-11-08.cases": "99835a3e7add21faea15ea1f296edaa778680a84de998a822f1d1db69bcfe628",
}


class GoldenSetReportError(Exception):
    """Typed read-only report failure (reason carried)."""


def _corpus_digests() -> Dict[str, str]:
    return {
        "golden_set_v1.json.file": hashlib.sha256(V1_PATH.read_bytes()).hexdigest(),
        "golden_set_v2.json.file": hashlib.sha256(V2_PATH.read_bytes()).hexdigest(),
    }


def _compare_into(expected: Dict[str, Any], actual: Dict[str, Any], reasons: list) -> None:
    for key, wanted in expected.items():
        if key not in actual:
            reasons.append(f"MISSING:{key}")
        elif actual[key] != wanted:  # exact equality — floats too
            reasons.append(f"MISMATCH:{key}:expected={wanted!r}:actual={actual[key]!r}")
    for key in actual:
        if key not in expected:
            reasons.append(f"EXTRA:{key}")


def _run_case(case, inputs, input_id_of) -> GoldenV2CaseResult:
    """Run ONE v2 case against the REAL deterministic engine for its kind
    (faithful mirror of the pinned test-runner semantics)."""
    payload = inputs[input_id_of(case.case_id)]
    reasons: list[str] = []
    fp = fn = None
    if case.kind == "MARKET_INTERPRETATION":
        core = AIIntelligenceCore()
        result = core.evaluate(
            symbol_context=payload.get("symbol_context"),
            market_context=payload.get("market_context"),
            filter_context=payload.get("filter_context"),
            backtest_context=payload.get("backtest_context"),
            data_trust=payload.get("data_trust"),
        )
        actual = {
            "recommendation": result.recommendation,
            "confidence": result.confidence,
            "reason_codes": sorted(result.reason_codes),
        }
        _compare_into(case.expected, actual, reasons)
        fp, fn = classify_interpretation_result(
            case.expected["recommendation"], result.recommendation
        )
    elif case.kind == "SOURCE_CONFLICT":
        items = [EvidenceItem(**payload[k]) for k in ("primary", "secondary", "a", "b") if k in payload]
        conflict = EvidenceConflict(**payload["conflict"])
        try:
            resolved, record = resolve_conflict_by_precedence(
                conflict,
                items,
                tier_precedence=payload["tier_precedence"],
                resolved_by=payload["resolved_by"],
                resolved_at_utc=datetime.fromisoformat(payload["resolved_at_utc"]),
            )
            actual = {
                "status": resolved.status,
                "rule_id": record.rule_id,
                "winner_evidence_id": record.winner_evidence_id,
                "winner_precedence": record.winner_precedence,
                "loser_evidence_ids": sorted(record.loser_evidence_ids),
            }
        except ResolutionRefusal as exc:
            actual = {"refusal_reason": exc.reason, "status_stays": "OPEN"}
        _compare_into(case.expected, actual, reasons)
    elif case.kind == "FUNDAMENTAL_EXTRACTION":
        doc = DeclaredFilingDocument(**payload["document"])
        result = extract_filing_document(doc)
        restated_doc = DeclaredFilingDocument(**payload["restatement_linkage"])
        restated = extract_filing_document(restated_doc)
        actual = {
            "facts": [
                {"line_item": f.line_item, "value": str(f.value), "unit": f.unit, "currency": f.currency, "reporting_period": f.reporting_period}
                for f in result.financial_facts
            ],
            "refusal_rows": [[r.section_id, r.reason] for r in result.refusals],
            "restated_supersedes_sha256": restated_doc.supersedes_document_sha256,
            "restated_fact_count": len(restated.financial_facts),
            "restated_value": str(restated.financial_facts[0].value),
        }
        _compare_into(case.expected, actual, reasons)
    elif case.kind == "REGIME_ROBUSTNESS":
        report = slice_by_regime(
            [(w["label"], w["start_ts"], w["end_ts"]) for w in payload["windows"]],
            payload["bars"],
            lambda sl: [sum(b["close"] for b in sl) / len(sl)],
        )
        actual = {
            "slices": [
                {"label": s.label, "bar_count": s.bar_count, "metrics": list(s.metrics)}
                for s in report.slices
            ],
            "gap_labels": list(report.gap_labels),
            "uncovered_bar_count": report.uncovered_bar_count,
        }
        _compare_into(case.expected, actual, reasons)
    elif case.kind == "CALIBRATION":
        pairs = [(p, o) for p, o in payload["pairs"]]
        record = build_calibration_record(
            calibration_id=payload["calibration_id"],
            subject_kind=payload["subject_kind"],
            subject_ref=payload["subject_ref"],
            pairs=pairs,
            measured_at_utc=datetime.fromisoformat(payload["measured_at_utc"]),
            data_class=payload["data_class"],
            evidence_ref=payload["evidence_ref"],
            bucket_count=payload["bucket_count"],
        )
        actual = {
            "brier_score": record.brier_score,
            "ece": record.expected_calibration_error,
            "bucket_count": len(record.buckets),
        }
        _compare_into(case.expected, actual, reasons)
    else:
        reasons.append(f"UNKNOWN_KIND:{case.kind}")
    return GoldenV2CaseResult(
        case_id=case.case_id,
        kind=case.kind,
        passed=not reasons,
        failure_reasons=tuple(reasons),
        false_positive=fp,
        false_negative=fn,
    )


def _load_v2() -> Tuple[GoldenV2Version, Dict[str, Any]]:
    file_digest = hashlib.sha256(V2_PATH.read_bytes()).hexdigest()
    if file_digest != GOLDEN_SET_V2_REFERENCE_DIGESTS["golden_set_v2.json.file"]:
        raise GoldenSetReportError("golden_set_v2_corpus_digest_mismatch")
    payload = json.loads(V2_PATH.read_text(encoding="utf-8"))
    version = parse_golden_set_v2_payload(payload)  # verifies input digests + version digest
    if version.cases_digest != GOLDEN_SET_V2_REFERENCE_DIGESTS["GS2-2026-11-08.cases"]:
        raise GoldenSetReportError("golden_set_v2_cases_digest_mismatch")
    return version, payload


def run_golden_set_v2_report() -> Dict[str, Any]:
    """Read-only, deterministic, versioned report (no superiority claim)."""
    version, payload = _load_v2()
    input_ids = {c["case_id"]: c["input_id"] for c in payload["cases"]}
    results = tuple(_run_case(c, payload["inputs"], input_ids.get) for c in version.cases)

    # baseline = the v1 corpus re-verified against ITS pinned parse discipline
    v1_payload = json.loads(V1_PATH.read_text(encoding="utf-8"))
    v1_version = parse_golden_set_version(v1_payload)
    baseline_summary = {
        "corpus": "golden_set_v1",
        "version_id": v1_version.version_id,
        "cases": len(v1_version.cases),
        "cases_digest": v1_version.cases_digest,
        "all_pinned_digests_verified": True,
    }
    candidate_summary = {
        "corpus": "golden_set_v2",
        "version_id": version.version_id,
        "cases": len(version.cases),
        "cases_digest": version.cases_digest,
        "all_pinned_digests_verified": True,
    }
    report = build_v2_report(
        version,
        results,
        baseline_summary=baseline_summary,
        candidate_summary=candidate_summary,
    )
    return {
        "ok": True,
        "report_kind": "GOLDEN_SET_V2_READ_ONLY_REPORT",
        "corpus_file_digests": _corpus_digests(),
        "report": report,
        "cases": [
            {
                "case_id": r.case_id,
                "kind": r.kind,
                "passed": r.passed,
                "failure_reasons": list(r.failure_reasons),
                "false_positive": r.false_positive,
                "false_negative": r.false_negative,
            }
            for r in results
        ],
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "read_only": True,
        "honesty": {
            "no_superiority_claim": "baseline و candidate جدا گزارش می‌شوند؛ بدون شواهد تکرارپذیر و پروتکل مصوب مالک هیچ ادعای برتری‌ای مطرح نمی‌شود",
            "deterministic": "گزارش کاملاً قطعی است: ورودی یکسان ⇒ خروجی یکسان (بدون ساعت دیواری و بدون RNG)",
            "invalidations_pinned": "هر مورد شرایط ابطال صریح پین‌شده دارد",
        },
    }
