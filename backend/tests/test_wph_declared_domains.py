"""test_wph_declared_domains.py — WAVE-AB5 (WP-H) acceptance tests.

The AI-7 evaluation-domain audit recorded that, of the 15 required
evaluation domains, domains 12 (accessibility), 13 (feature adoption) and
14 (task completion) had NO code. These tests pin the additive closure:

- the ProductAuditDomain literal gains exactly the three members (additive;
  the canonical evaluator_allowed_for_domain rule is unchanged);
- the three DECLARED row types are privacy-locked by construction
  (aggregate counters only — the field surface cannot express a per-user
  record, and smuggled user-identifying fixture keys are refused);
- the declared fixture builder produces the three DomainEvaluatorResult
  rows in a real product-audit run payload;
- the accessibility-regression proposal generator honors the full 10-field
  improvement-proposal contract (baseline / observed-problem-as-evidence /
  expected_benefit / uncertainty / cost / risks / rollback_plan /
  evaluation_design / approval_state / advisory_only=True) and is advisory
  only;
- deterministic repeat of every builder.

No network, no clock reads, no LLM; everything synthetic/declared.
"""

from __future__ import annotations

from typing import get_args

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.domain.declared_adoption_metrics import (
    DECLARED_ACCESSIBILITY_BASELINE,
    DECLARED_ADOPTION_METRICS_FIXTURE_V1,
    DECLARED_ADOPTION_METRICS_VERSION,
    AccessibilityAuditRow,
    FeatureAdoptionRow,
    TaskCompletionRow,
    build_accessibility_regression_proposal,
    build_declared_domain_evaluator_results,
    declared_accessibility_rows,
    declared_feature_adoption_rows,
    declared_task_completion_rows,
    privacy_locked_field_names,
)
from app.domain.product_audit import ProductAuditDomain, evaluator_allowed_for_domain
from app.main import app

# Distinct client identity (rate-limiter symmetry with the other v10 suites).
client = TestClient(app, client=("waveab5-wph", 12500))

WINDOW = {"window_start_utc": "2026-11-05T00:00:00Z", "window_end_utc": "2026-11-05T01:00:00Z"}

PREFIX = "/api/v10/productloops"

NEW_DOMAINS = ("ACCESSIBILITY", "FEATURE_ADOPTION", "TASK_COMPLETION")


# ---------------------------------------------------------------------------
# Domain vocabulary extension (additive; matching rule unchanged)
# ---------------------------------------------------------------------------


def test_product_audit_domain_gains_exactly_three_members() -> None:
    members = get_args(ProductAuditDomain)
    for domain in NEW_DOMAINS:
        assert domain in members
    # additive: every pre-existing member is still present
    for legacy in (
        "FILTERS_STRATEGIES",
        "MARKET_FUNDAMENTAL_AI",
        "DATA_PROVIDER_OPERATIONS",
        "PRODUCT_UX",
        "SOFTWARE_QUALITY",
    ):
        assert legacy in members


def test_evaluator_matching_rule_unchanged_for_new_domains() -> None:
    # The canonical 06 §8 rule is untouched: backtest-family evaluators stay
    # bound to FILTERS_STRATEGIES; UX_REVIEW/MANUAL_REVIEW/REGRESSION apply.
    for domain in NEW_DOMAINS:
        assert evaluator_allowed_for_domain(domain, "BACKTEST") is False
        assert evaluator_allowed_for_domain(domain, "WALK_FORWARD") is False
        assert evaluator_allowed_for_domain(domain, "UX_REVIEW") is True
        assert evaluator_allowed_for_domain(domain, "MANUAL_REVIEW") is True
        assert evaluator_allowed_for_domain(domain, "REGRESSION") is True
    assert evaluator_allowed_for_domain("FILTERS_STRATEGIES", "BACKTEST") is True


# ---------------------------------------------------------------------------
# Privacy lock by construction
# ---------------------------------------------------------------------------


def test_row_types_are_privacy_locked_aggregate_counters_only() -> None:
    surface = privacy_locked_field_names()
    forbidden_fragments = ("user", "session", "device", "email", "ip", "identity", "person")
    lock_field = "measured_from_user_content"
    for type_name, fields in surface.items():
        assert lock_field in fields, type_name  # the structural privacy lock is present
        data_fields = tuple(f for f in fields if f != lock_field)
        lowered = tuple(f.lower() for f in data_fields)
        for fragment in forbidden_fragments:
            assert not any(fragment in f for f in lowered), (type_name, fragment)
    for row_type in (AccessibilityAuditRow, FeatureAdoptionRow, TaskCompletionRow):
        assert row_type.model_fields["measured_from_user_content"].default is False


def test_row_types_refuse_user_measured_value() -> None:
    with pytest.raises(ValidationError):
        AccessibilityAuditRow(
            check_id="c", declared_result=True, source_note="s", measured_from_user_content=True  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        FeatureAdoptionRow(
            feature_id="f", declared_usage_count=1, window="w", source_note="s",
            measured_from_user_content=True,  # type: ignore[arg-type]
        )


def test_builders_refuse_user_identifying_fixture_keys() -> None:
    hostile = {
        "accessibility": (
            {"check_id": "c", "declared_result": True, "coverage_pct": None,
             "source_note": "s", "user_id": "u-1"},
        ),
    }
    with pytest.raises(ValueError, match="privacy_locked_fixture_rejected:user_id"):
        declared_accessibility_rows(hostile)


def test_task_completion_rate_is_exact_and_fail_closed() -> None:
    rows = declared_task_completion_rows()
    by_id = {r.task_id: r for r in rows}
    assert by_id["register_prediction"].declared_started == 40
    assert by_id["register_prediction"].declared_completed == 34
    assert by_id["register_prediction"].completion_rate == pytest.approx(0.85)
    with pytest.raises(ValidationError, match="completion_rate_inconsistent_with_counts"):
        TaskCompletionRow(
            task_id="t", declared_started=4, declared_completed=3, completion_rate=0.7,
            window="w", source_note="s",
        )


# ---------------------------------------------------------------------------
# Declared fixture builder → DomainEvaluatorResult rows
# ---------------------------------------------------------------------------


def test_builder_produces_three_domain_rows_deterministically() -> None:
    rows = build_declared_domain_evaluator_results()
    assert [r.domain for r in rows] == list(NEW_DOMAINS)
    kinds = {r.domain: r.evaluator_kind for r in rows}
    assert kinds["ACCESSIBILITY"] == "UX_REVIEW"
    assert kinds["FEATURE_ADOPTION"] == "MANUAL_REVIEW"
    assert kinds["TASK_COMPLETION"] == "UX_REVIEW"
    for row in rows:
        assert len(row.metrics_digest) == 64
        assert row.evidence_ids
        assert row.notes
    # deterministic repeat: identical digests on rebuild
    again = build_declared_domain_evaluator_results()
    assert [r.metrics_digest for r in again] == [r.metrics_digest for r in rows]
    # different declared fixture content → different digest (bound by hash)
    mutated = dict(DECLARED_ADOPTION_METRICS_FIXTURE_V1)
    mutated["feature_adoption"] = (
        {"feature_id": "tablokhani_filter", "declared_usage_count": 121,
         "window": "DECLARED-WINDOW-W44", "source_note": "s"},
    )
    other = build_declared_domain_evaluator_results(mutated)
    assert other[1].metrics_digest != rows[1].metrics_digest


# ---------------------------------------------------------------------------
# Improvement-proposal generator (declared regression; 10-field contract)
# ---------------------------------------------------------------------------


def test_accessibility_regression_proposal_honors_ten_field_contract() -> None:
    proposal = build_accessibility_regression_proposal()
    assert proposal is not None
    # 1) baseline (declared baseline values, dict[str, float])
    assert proposal.baseline == DECLARED_ACCESSIBILITY_BASELINE
    # 2) observed problem AS the evidence (degraded declared check ids)
    assert "DECLARED-CHECK:alt_text_coverage_pct" in proposal.evidence_ids
    # 3..6) expected benefit / uncertainty / cost / risks — all non-empty
    assert proposal.expected_benefit
    assert proposal.uncertainty
    assert proposal.cost
    assert len(proposal.risks) >= 1
    # 7) rollback plan (non-empty, explicit)
    assert proposal.rollback_plan
    # 8) evaluation design (non-empty)
    assert proposal.evaluation_design
    # 9) approval state (PROPOSED — human-controlled)
    assert proposal.approval_state == "PROPOSED"
    # 10) advisory only — type-locked True
    assert proposal.advisory_only is True


def test_no_regression_means_no_proposal_is_invented() -> None:
    healthy = {
        "accessibility": (
            {"check_id": "rtl_direction", "declared_result": True, "coverage_pct": None,
             "source_note": "s"},
            {"check_id": "alt_text_coverage_pct", "declared_result": True,
             "coverage_pct": 100.0, "source_note": "s"},
            {"check_id": "contrast_declared", "declared_result": True, "coverage_pct": None,
             "source_note": "s"},
            {"check_id": "keyboard_nav_declared", "declared_result": True,
             "coverage_pct": None, "source_note": "s"},
        ),
    }
    assert build_accessibility_regression_proposal(healthy) is None


def test_proposal_generator_is_deterministic() -> None:
    p1 = build_accessibility_regression_proposal()
    p2 = build_accessibility_regression_proposal()
    assert p1 is not None and p2 is not None
    assert p1 == p2


# ---------------------------------------------------------------------------
# Runtime wiring — product-audit run payload carries the three rows
# ---------------------------------------------------------------------------


def test_product_audit_run_payload_contains_three_declared_domain_rows() -> None:
    res = client.post(f"{PREFIX}/product-audit/run", json=WINDOW)
    assert res.status_code == 200
    body = res.json()
    domains = [r["domain"] for r in body["run_record"]["domain_results"]]
    assert domains == list(NEW_DOMAINS)
    kinds = {r["domain"]: r["evaluator_kind"] for r in body["run_record"]["domain_results"]}
    assert kinds["ACCESSIBILITY"] == "UX_REVIEW"
    assert kinds["FEATURE_ADOPTION"] == "MANUAL_REVIEW"
    assert kinds["TASK_COMPLETION"] == "UX_REVIEW"
    for row in body["run_record"]["domain_results"]:
        assert len(row["metrics_digest"]) == 64
    # the declared adoption envelope is surfaced with its version + privacy note
    assert body["declared_adoption_domains"]["declared_version"] == DECLARED_ADOPTION_METRICS_VERSION
    assert body["declared_adoption_domains"]["domains"] == list(NEW_DOMAINS)
    # the declared charter now binds all six domains, still with no SCHEDULED cadence
    charter = body["charter"]
    assert set(NEW_DOMAINS) <= set(charter["domains"])
    assert all(c["mode"] != "SCHEDULED" for c in charter["cadences"])
    # probes untouched (the pinned row counts still hold)
    drift = body["drift"]
    metrics = {m["name"]: m["later_value"] for m in drift["metric_assessments"]}
    assert metrics["tablokhani_ranked_rows"] == 60.0
    assert metrics["dataquality_coverage_rows"] == 8.0
    assert metrics["chartpro_candles_rows"] == 120.0


def test_product_audit_run_domain_rows_deterministic_on_repeat() -> None:
    r1 = client.post(f"{PREFIX}/product-audit/run", json=WINDOW).json()
    r2 = client.post(f"{PREFIX}/product-audit/run", json=WINDOW).json()
    assert r1["run_record"]["domain_results"] == r2["run_record"]["domain_results"]
    assert (
        r1["declared_adoption_domains"]["domains"]
        == r2["declared_adoption_domains"]["domains"]
    )


# ---------------------------------------------------------------------------
# Declared fixture honesty (source notes, declared window, no fabrication)
# ---------------------------------------------------------------------------


def test_declared_rows_all_carry_source_notes_and_declared_window() -> None:
    fixture = DECLARED_ADOPTION_METRICS_FIXTURE_V1
    assert fixture["version"] == "DECLARED-ADOPTION-METRICS-FIXTURE-V1"
    for row in declared_accessibility_rows():
        assert row.source_note
    for row in declared_feature_adoption_rows():
        assert row.source_note
        assert row.window.startswith("DECLARED-WINDOW")
        assert row.declared_usage_count >= 0
    for row in declared_task_completion_rows():
        assert row.source_note
        assert row.window.startswith("DECLARED-WINDOW")
        assert 0.0 <= row.completion_rate <= 1.0
        assert row.declared_completed <= row.declared_started
