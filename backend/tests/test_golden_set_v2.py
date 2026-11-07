"""WAVE-AI (2026-11-08, WP-F): Golden Set v2 — versioned reproducible
benchmark extension.

Pins (mirroring the v1 tamper-evidence discipline):
- fixture FILE digest and cases digest, re-verified every run;
- ALL five capability kinds re-run against the REAL deterministic engines
  with EXACT comparison (label, reason codes, confidence float, resolver
  winner, refusal reasons, extraction rows, regime slice metrics, Brier/ECE);
- FP/FN accounting over the interpretation cases (label-strength ranks);
- baseline (v1 corpus re-verification) and candidate (v2 corpus) results
  reported SEPARATELY; ``superiority_claimed`` is structurally False;
- every case carries explicit invalidation conditions (pinned non-empty);
- determinism: the whole battery is run TWICE and must agree exactly.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.ai_intelligence import AIIntelligenceCore
from app.domain.calibration_metrics import build_calibration_record
from app.domain.evidence import EvidenceConflict, EvidenceItem
from app.domain.evidence_resolution import ResolutionRefusal, resolve_conflict_by_precedence
from app.domain.filing_extraction import DeclaredFilingDocument, extract_filing_document
from app.domain.golden_set import GoldenSetIntegrityError, parse_golden_set_version
from app.domain.golden_set_v2 import (
    GoldenV2CaseResult,
    build_v2_report,
    classify_interpretation_result,
    parse_golden_set_v2_payload,
)
from app.engines.regime_slices import slice_by_regime

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_set" / "golden_set_v2.json"
V1_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_set" / "golden_set_v1.json"

#: Pinned reference digests (tamper evidence; CORPUS_REFERENCE_DIGESTS
#: precedent — file bytes + canonical case records, both pinned HERE).
GOLDEN_SET_V2_REFERENCE_DIGESTS = {
    "golden_set_v2.json.file": "085cadd0d48324e7cd37bcb018e4ee019b68f9a740fcf19988e7d83547d8709f",
    "GS2-2026-11-08.cases": "99835a3e7add21faea15ea1f296edaa778680a84de998a822f1d1db69bcfe628",
}

T0 = datetime(2026, 11, 8, 10, 0, 0, tzinfo=timezone.utc)


def _load_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _run_case(case, inputs, input_id_of) -> GoldenV2CaseResult:
    """Run ONE v2 case against the REAL deterministic engine for its kind."""
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


def _compare_into(expected: dict, actual: dict, reasons: list) -> None:
    for key, wanted in expected.items():
        if key not in actual:
            reasons.append(f"MISSING:{key}")
        elif actual[key] != wanted:  # exact equality — floats too
            reasons.append(f"MISMATCH:{key}:expected={wanted!r}:actual={actual[key]!r}")
    for key in actual:
        if key not in expected:
            reasons.append(f"EXTRA:{key}")


# ---------------------------------------------------------------------------
# tamper evidence
# ---------------------------------------------------------------------------


def test_v2_fixture_digests_pinned():
    import hashlib

    file_digest = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    assert file_digest == GOLDEN_SET_V2_REFERENCE_DIGESTS["golden_set_v2.json.file"], (
        "fixture bytes drifted — re-pin deliberately with a recorded change"
    )
    payload = _load_payload()
    version = parse_golden_set_v2_payload(payload)
    assert version.version_id == "GS2-2026-11-08"
    assert version.cases_digest == GOLDEN_SET_V2_REFERENCE_DIGESTS["GS2-2026-11-08.cases"]


def test_v2_input_digests_verified_at_parse():
    payload = _load_payload()
    # every case's input hash is verified by the parser; a tampered input is refused
    import copy as _copy

    tampered = _copy.deepcopy(payload)
    first_input_key = sorted(tampered["inputs"])[0]
    tampered["inputs"][first_input_key]["__tamper__"] = 1
    with pytest.raises(GoldenSetIntegrityError, match="CASE_INPUT_DIGEST_MISMATCH"):
        parse_golden_set_v2_payload(tampered)


def test_v2_version_digest_tamper_refused():
    payload = _load_payload()
    tampered = copy.deepcopy(payload)
    tampered["cases"][0]["description"] += " tampered"
    with pytest.raises(GoldenSetIntegrityError, match="VERSION_DIGEST_MISMATCH"):
        parse_golden_set_v2_payload(tampered)


# ---------------------------------------------------------------------------
# full corpus run (deterministic engines, exact comparison)
# ---------------------------------------------------------------------------


def _run_all():
    payload = _load_payload()
    version = parse_golden_set_v2_payload(payload)
    input_ids = {c["case_id"]: c["input_id"] for c in payload["cases"]}
    results = tuple(_run_case(c, payload["inputs"], input_ids.get) for c in version.cases)
    return version, results


def test_v2_all_cases_pass_against_real_engines():
    version, results = _run_all()
    failures = [(r.case_id, r.failure_reasons) for r in results if not r.passed]
    assert not failures, f"golden v2 drift: {failures}"
    kinds = {r.kind for r in results}
    assert kinds == {
        "MARKET_INTERPRETATION",
        "SOURCE_CONFLICT",
        "FUNDAMENTAL_EXTRACTION",
        "REGIME_ROBUSTNESS",
        "CALIBRATION",
    }
    assert len(results) == 8


def test_v2_determinism_double_run():
    _, run1 = _run_all()
    _, run2 = _run_all()
    assert run1 == run2  # exact, including float equality


def test_v2_every_case_carries_invalidation_conditions():
    payload = _load_payload()
    version = parse_golden_set_v2_payload(payload)
    for case in version.cases:
        assert case.invalidations and all(str(i).strip() for i in case.invalidations)


# ---------------------------------------------------------------------------
# FP/FN accounting
# ---------------------------------------------------------------------------


def test_v2_interpretation_fp_fn_accounting():
    _, results = _run_all()
    interp = [r for r in results if r.kind == "MARKET_INTERPRETATION"]
    assert len(interp) == 3
    # all three pass → zero FP/FN (the pinned corpus agrees with the engines)
    assert all(r.passed for r in interp)
    assert all(r.false_positive is None and r.false_negative is None for r in interp)
    # the FP/FN classifier itself: stronger-than-pinned = FP, weaker = FN
    assert classify_interpretation_result("WATCH", "BUY_CANDIDATE") == (True, None)
    assert classify_interpretation_result("BUY_CANDIDATE", "WATCH") == (None, True)
    assert classify_interpretation_result("HOLD", "HOLD") == (None, None)
    # unknown label (vocabulary drift) is not classifiable — comparison fails instead
    assert classify_interpretation_result("WATCH", "NOT_A_LABEL") == (None, None)


def test_v2_report_separates_baseline_and_candidate_and_claims_nothing():
    version, results = _run_all()
    # baseline = the v1 corpus re-verified against ITS pinned digests
    v1_payload = json.loads(V1_FIXTURE_PATH.read_text(encoding="utf-8"))
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
    assert report["false_positives_total"] == 0
    assert report["false_negatives_total"] == 0
    assert report["passed"] == len(results) and report["failed"] == 0
    # baseline and candidate reported SEPARATELY — never merged into a winner
    assert report["baseline_results"] == baseline_summary
    assert report["candidate_results"] == candidate_summary
    assert report["baseline_results"]["corpus"] != report["candidate_results"]["corpus"]
    assert report["superiority_claimed"] is False
    assert "no superiority claim" in report["note"]
    # per-kind breakdown present for all five kinds
    assert set(report["per_kind"]) == {
        "MARKET_INTERPRETATION",
        "SOURCE_CONFLICT",
        "FUNDAMENTAL_EXTRACTION",
        "REGIME_ROBUSTNESS",
        "CALIBRATION",
    }
