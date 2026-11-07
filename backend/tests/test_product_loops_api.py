"""test_product_loops_api.py — MASTER-RADAR WAVE-F (2026-11-05)

Governed five-product-loop surface /api/v10/productloops (§5 loops):
manifest, declared dossier PIT + live conflict detection, governed research
status/evaluation, on-demand product audit with drift vs the declared
baseline, append-only prediction registry with label-leakage guards and
Brier/ECE calibration binding.

Honesty discipline mirrored from the WAVE-B/WAVE-D/WAVE-E suites:
- every caller instant is required (no wall clock anywhere);
- hostile payloads get typed 4xx, never 5xx and never silent success;
- gates asserted unchanged (AI2_ENABLED=0 default posture, no scheduler);
- route surface stays under the one governed prefix.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Distinct client identity (symmetry with test_user_indicator_api.py): the
# rate limiter budgets per client identity (150/min); a unique identity
# isolates this suite's request volume from other suites sharing the
# default TestClient address, in both directions.
client = TestClient(app, client=("mr-wavef-loops", 12400))

# Settings-cache hygiene (symmetry with test_user_indicator_api.py /
# AUDIT-MR3 Obs.3): env-patching modules (e.g. test_security_hardening.py)
# cache a settings object with PRIVATE_MODE/AUTH_REQUIRED residue inside the
# get_settings() lru_cache; monkeypatch teardown restores the environment
# but NOT the cache. The autouse per-test clear rebuilds the cache from the
# restored environment before each test and clears it afterwards so THIS
# module cannot poison later ones either. No other test file is touched.
from app.core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _settings_cache_hygiene():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


PREFIX = "/api/v10/productloops"

CUTOFF_EARLY = "2025-11-10T00:00:00Z"  # only filing A v1 published by then
CUTOFF_LATE = "2025-12-25T00:00:00Z"  # v1 + v2 + free-float published


# ---------------------------------------------------------------------------
# L0 — manifest
# ---------------------------------------------------------------------------


def test_manifest_lists_five_loops_with_vocabulary_and_trust() -> None:
    res = client.get(f"{PREFIX}/manifest")
    assert res.status_code == 200
    body = res.json()
    assert body["manifest_version"] == "PRODUCT-LOOPS-MANIFEST-V1"
    loops = body["loops"]
    assert len(loops) == 5
    ids = {loop["loop_id"] for loop in loops}
    assert ids == {
        "L1_MARKET_INTELLIGENCE",
        "L2_COMPANY_EXTERNAL_INTELLIGENCE",
        "L3_GOVERNED_RESEARCH",
        "L4_PRODUCT_INTELLIGENCE",
        "L5_PREDICTION_FEEDBACK",
    }
    allowed = {
        "IMPLEMENTED", "TESTED", "INTEGRATION-VERIFIED", "RUNTIME-VERIFIED",
        "OPERATIONALLY-VERIFIED", "INDEPENDENTLY-REPRODUCED", "OWNER-ACCEPTED",
        "OWNER-GATED", "PARTIAL", "NOT-IMPLEMENTED", "NOT-APPLICABLE",
    }
    for loop in loops:
        assert loop["status"] in allowed
        assert loop["data_trust"] in {"SYNTHETIC", "DECLARED"}
        assert loop["directive_ref"]
    honesty = body["honesty"]
    assert honesty["owner_gate_note"]
    assert honesty["no_scheduler_note"]


# ---------------------------------------------------------------------------
# L2 — declared dossier + PIT + conflicts
# ---------------------------------------------------------------------------


def test_dossier_pit_eligibility_and_excluded_count_disclosed() -> None:
    res = client.get(f"{PREFIX}/intel/dossier/فملی", params={"cutoff_utc": CUTOFF_LATE})
    assert res.status_code == 200
    body = res.json()
    assert body["dossier"]["company_id"] == "DECLARED-COMPANY-A"
    eligible = set(body["pit"]["eligible_fact_ids"])
    # late cutoff: v1, v2 (restatement) and free-float are published
    assert "DECLARED-FACT-A-NI-V1" in eligible
    assert "DECLARED-FACT-A-NI-V2" in eligible
    assert "DECLARED-FACT-A-FF" in eligible
    assert body["pit"]["excluded_later_published"] == []
    # restatement chain explicitly carried
    chain = {r["fact_id"]: r for r in body["restatement_chain"]}
    assert chain["DECLARED-FACT-A-NI-V2"]["supersedes_fact_id"] == "DECLARED-FACT-A-NI-V1"
    assert chain["DECLARED-FACT-A-NI-V2"]["restatement_version"] == 2


def test_dossier_early_cutoff_excludes_later_filings_with_count() -> None:
    res = client.get(f"{PREFIX}/intel/dossier/فملی", params={"cutoff_utc": CUTOFF_EARLY})
    assert res.status_code == 200
    body = res.json()
    eligible = set(body["pit"]["eligible_fact_ids"])
    assert eligible == {"DECLARED-FACT-A-NI-V1"}
    excluded_ids = {row["fact_id"] for row in body["pit"]["excluded_later_published"]}
    assert "DECLARED-FACT-A-NI-V2" in excluded_ids
    assert "DECLARED-FACT-A-FF" in excluded_ids
    # the UNAVAILABLE-publication fact is neither eligible nor later-published:
    # it is disclosed in its own bucket, never silently dropped
    assert "DECLARED-FACT-A-AF" in set(body["pit"]["unavailable_publication_fact_ids"])
    assert "DECLARED-FACT-A-AF" not in excluded_ids


def test_dossier_live_quote_conflict_detected_for_فملی_not_for_فولاد() -> None:
    res_a = client.get(f"{PREFIX}/intel/dossier/فملی", params={"cutoff_utc": CUTOFF_LATE})
    conflicts_a = res_a.json()["source_conflicts"]["conflicts"]
    assert len(conflicts_a) == 1
    assert conflicts_a[0]["status"] == "OPEN"
    assert res_a.json()["source_conflicts"]["tol_pct"] == "2.0"
    res_b = client.get(f"{PREFIX}/intel/dossier/فولاد", params={"cutoff_utc": CUTOFF_LATE})
    assert res_b.status_code == 200
    assert res_b.json()["source_conflicts"]["conflicts"] == []
    # missing data is listed, never filled
    assert res_b.json()["dossier"]["missing_data"]


def test_dossier_hostile_inputs_typed_fail_closed() -> None:
    res = client.get(f"{PREFIX}/intel/dossier/ناشناخته", params={"cutoff_utc": CUTOFF_LATE})
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["error"] == "DOSSIER_NOT_DECLARED"
    assert detail["declared_symbols"]
    res = client.get(f"{PREFIX}/intel/dossier/فملی", params={"cutoff_utc": "garbage"})
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "MALFORMED_INSTANT"
    res = client.get(f"{PREFIX}/intel/dossier/فملی", params={"cutoff_utc": "2025-12-25T00:00:00"})
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "NAIVE_INSTANT_REFUSED"
    res = client.get(f"{PREFIX}/intel/dossier/فملi")
    assert res.status_code == 422  # missing cutoff query → FastAPI required-param


# ---------------------------------------------------------------------------
# L3 — governed research
# ---------------------------------------------------------------------------


def test_research_status_reports_live_refusal_and_ai2_gate() -> None:
    res = client.get(f"{PREFIX}/research/status")
    assert res.status_code == 200
    body = res.json()
    lp = body["live_permission_check"]
    assert lp["permitted"] is False
    assert "kill_switch_engaged" in lp["refusals"]
    assert "missing_provenance:dataset_version" in lp["refusals"]
    assert body["job"]["kill_switch"] == "ENGAGED"
    assert body["job"]["production_mutation"] is False
    assert body["job"]["financial_authority"] == "DETERMINISTIC_ONLY"
    assert body["ai2_gate"]["ai2_enabled"] is False
    assert body["ai2_gate"]["posture"] == "DISABLED_OWNER_GATED"


def test_hypothesis_evaluation_bonferroni_adjustment_exact() -> None:
    body = {
        "family_id": "FAM-1",
        "method": "BONFERRONI",
        "alpha": 0.05,
        "members": [
            {"hypothesis_id": "H1", "attempt_index": 1, "metric_name": "hit_rate", "pvalue": 0.01},
            {"hypothesis_id": "H2", "attempt_index": 2, "metric_name": "hit_rate", "pvalue": 0.5},
        ],
    }
    res = client.post(f"{PREFIX}/research/hypotheses/evaluate", json=body)
    assert res.status_code == 200
    payload = res.json()
    verdicts = {v["hypothesis_id"]: v for v in payload["verdicts"]}
    assert verdicts["H1"]["adjusted_pvalue"] == pytest.approx(0.02)
    assert verdicts["H1"]["verdict"] == "ACCEPTED"
    assert verdicts["H2"]["adjusted_pvalue"] == pytest.approx(1.0)
    assert verdicts["H2"]["verdict"] == "REJECTED"
    # deterministic replay: identical body → identical digest
    res2 = client.post(f"{PREFIX}/research/hypotheses/evaluate", json=body)
    assert res2.json()["digest_sha256"] == payload["digest_sha256"]
    # different body → different digest
    other = dict(body, alpha=0.1)
    res3 = client.post(f"{PREFIX}/research/hypotheses/evaluate", json=other)
    assert res3.json()["digest_sha256"] != payload["digest_sha256"]


def test_hypothesis_evaluation_hostile_refusals() -> None:
    base = {
        "family_id": "FAM-X",
        "method": "NONE",
        "alpha": 0.05,
        "members": [
            {"hypothesis_id": f"H{i}", "attempt_index": i, "metric_name": "m", "pvalue": 0.01}
            for i in (1, 2)
        ],
    }
    # NONE with family size > 1 must be REFUSED by the governed verdict
    # (fail-closed honesty — the refusal is a verdict, not an exception)
    res = client.post(f"{PREFIX}/research/hypotheses/evaluate", json=base)
    assert res.status_code == 200
    verdicts = res.json()["verdicts"]
    assert all(v["verdict"] == "REFUSED" for v in verdicts)
    assert all("UNADJUSTED" in " ".join(v["reason_codes"]) for v in verdicts)
    # alpha outside (0,1) refused
    res = client.post(
        f"{PREFIX}/research/hypotheses/evaluate",
        json={**base, "method": "BONFERRONI", "alpha": 1.0},
    )
    assert res.status_code == 422
    res = client.post(
        f"{PREFIX}/research/hypotheses/evaluate",
        json={**base, "method": "BONFERRONI", "alpha": 0.05, "members": [
            {"hypothesis_id": "H1", "attempt_index": 1, "metric_name": "m", "pvalue": 1.5},
        ]},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# L4 — on-demand product audit
# ---------------------------------------------------------------------------

_WINDOW = {"window_start_utc": "2026-11-05T00:00:00Z", "window_end_utc": "2026-11-05T01:00:00Z"}


def test_product_audit_run_measures_declared_baseline_exactly() -> None:
    res = client.post(f"{PREFIX}/product-audit/run", json=_WINDOW)
    assert res.status_code == 200
    body = res.json()
    drift = body["drift"]
    assert drift["drift_verdict"] == "NO_DRIFT_DETECTED"
    metrics = {m["name"]: m for m in drift["metric_assessments"]}
    assert metrics["tablokhani_ranked_rows"]["later_value"] == 60.0
    assert metrics["dataquality_coverage_rows"]["later_value"] == 8.0
    assert metrics["chartpro_candles_rows"]["later_value"] == 120.0
    for name in ("tablokhani_ranked_rows", "dataquality_coverage_rows", "chartpro_candles_rows"):
        assert metrics[name]["verdict"] == "STABLE"
    record = body["run_record"]
    assert record["advisory_only"] is True
    assert record["data_class"] == "SYNTHETIC"
    assert record["proposal_ids"] == []
    details = body["probe_details"]
    for probe in ("tablokhani", "dataquality", "chartpro"):
        assert re.fullmatch(r"[0-9a-f]{64}", details[probe]["digest_sha256"])
        assert details[probe]["latency_ms"] >= 0.0


def test_product_audit_run_is_deterministic_on_repeat() -> None:
    res1 = client.post(f"{PREFIX}/product-audit/run", json=_WINDOW)
    res2 = client.post(f"{PREFIX}/product-audit/run", json=_WINDOW)
    assert res1.status_code == res2.status_code == 200
    m1 = {m["name"]: m["later_value"] for m in res1.json()["drift"]["metric_assessments"]}
    m2 = {m["name"]: m["later_value"] for m in res2.json()["drift"]["metric_assessments"]}
    assert m1 == m2
    d1 = res1.json()["probe_details"]["chartpro"]["digest_sha256"]
    d2 = res2.json()["probe_details"]["chartpro"]["digest_sha256"]
    assert d1 == d2


def test_product_audit_hostile_windows_refused() -> None:
    res = client.post(
        f"{PREFIX}/product-audit/run",
        json={"window_start_utc": "2026-11-05T00:00:00Z", "window_end_utc": "2026-10-01T00:00:00Z"},
    )
    assert res.status_code == 422
    res = client.post(
        f"{PREFIX}/product-audit/run",
        json={"window_start_utc": "2026-09-01T00:00:00Z", "window_end_utc": "2026-09-02T00:00:00Z"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "WINDOW_NOT_PIT_ORDERED"
    res = client.post(
        f"{PREFIX}/product-audit/run",
        json={"window_start_utc": "2026-11-05T00:00:00", "window_end_utc": "2026-11-05T01:00:00Z"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "NAIVE_INSTANT_REFUSED"


def test_product_audit_charter_has_no_scheduled_cadence() -> None:
    res = client.post(f"{PREFIX}/product-audit/run", json=_WINDOW)
    charter = res.json()["charter"]
    assert charter["charter_version"] == "AUDIT-CHARTER-DECLARED-V1"
    modes = {c["domain"]: c["mode"] for c in charter["cadences"]}
    assert all(mode != "SCHEDULED" for mode in modes.values())
    tb = charter["telemetry_boundary"]
    assert tb["aggregation_only"] is True
    assert tb["sensitive_content_repurposing"] is False


# ---------------------------------------------------------------------------
# L5 — prediction feedback lifecycle
# ---------------------------------------------------------------------------


def _register(prediction_id: str) -> None:
    res = client.post(
        f"{PREFIX}/predictions/register",
        json={
            "prediction_id": prediction_id,
            "subject": "SYNTHETIC:فملی",
            "registered_at_utc": "2026-01-01T00:00:00Z",
            "outcome_horizon_end_utc": "2026-02-01T00:00:00Z",
            "evaluation_metric": "DIRECTION_HIT",
            "event_maturity_rule": "horizon_end",
            "invalidation_rule": "subject_removed",
            "evidence_ids": ["DECLARED-PREDICTION-EVIDENCE"],
            "creator": "wave-f-tests",
        },
    )
    assert res.status_code == 200, res.text


def test_prediction_full_lifecycle_happy_path() -> None:
    _register("P-LIFE-1")
    # pre-maturity evaluation refused (label-leakage guard)
    res = client.post(
        f"{PREFIX}/predictions/P-LIFE-1/evaluate",
        params={"as_of_utc": "2026-01-15T00:00:00Z"},
        json={"matched_expectation": True},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "prediction_not_matured"
    # outcome recorded once
    res = client.post(
        f"{PREFIX}/predictions/P-LIFE-1/outcome",
        json={
            "outcome_id": "OUT-P-LIFE-1",
            "observed_at_utc": "2026-02-02T00:00:00Z",
            "observed_numeric": 1.0,
            "source_evidence_ids": ["DECLARED-OUTCOME-EVIDENCE"],
        },
    )
    assert res.status_code == 200
    # second outcome refused (append-only discipline)
    res = client.post(
        f"{PREFIX}/predictions/P-LIFE-1/outcome",
        json={
            "outcome_id": "OUT-P-LIFE-1-B",
            "observed_at_utc": "2026-02-03T00:00:00Z",
            "observed_numeric": 0.0,
            "source_evidence_ids": ["DECLARED-OUTCOME-EVIDENCE"],
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "prediction_already_has_outcome"
    # post-maturity evaluation succeeds with caller instant
    res = client.post(
        f"{PREFIX}/predictions/P-LIFE-1/evaluate",
        params={"as_of_utc": "2026-02-03T00:00:00Z"},
        json={"matched_expectation": True, "calibration_note": "declared fixture"},
    )
    assert res.status_code == 200
    evaluation = res.json()["evaluation"]
    assert evaluation["matched_expectation"] is True
    assert evaluation["outcome_id"] == "OUT-P-LIFE-1"
    # list shows maturity from the caller's instant
    res = client.get(f"{PREFIX}/predictions", params={"as_of_utc": "2026-02-03T00:00:00Z"})
    rows = {r["prediction"]["prediction_id"]: r for r in res.json()["rows"]}
    assert rows["P-LIFE-1"]["maturity_state"] == "MATURED"
    assert rows["P-LIFE-1"]["has_outcome"] is True
    res = client.get(f"{PREFIX}/predictions", params={"as_of_utc": "2026-01-15T00:00:00Z"})
    rows = {r["prediction"]["prediction_id"]: r for r in res.json()["rows"]}
    assert rows["P-LIFE-1"]["maturity_state"] == "PENDING"


def test_prediction_registration_guards() -> None:
    _register("P-GUARD-1")
    # duplicate id refused
    res = client.post(
        f"{PREFIX}/predictions/register",
        json={
            "prediction_id": "P-GUARD-1",
            "subject": "S",
            "registered_at_utc": "2026-01-01T00:00:00Z",
            "outcome_horizon_end_utc": "2026-02-01T00:00:00Z",
            "evaluation_metric": "M",
            "event_maturity_rule": "r",
            "invalidation_rule": "i",
            "evidence_ids": ["E"],
            "creator": "t",
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "duplicate_prediction_id"
    # horizon ending at/before registration refused
    res = client.post(
        f"{PREFIX}/predictions/register",
        json={
            "prediction_id": "P-GUARD-2",
            "subject": "S",
            "registered_at_utc": "2026-02-01T00:00:00Z",
            "outcome_horizon_end_utc": "2026-01-01T00:00:00Z",
            "evaluation_metric": "M",
            "event_maturity_rule": "r",
            "invalidation_rule": "i",
            "evidence_ids": ["E"],
            "creator": "t",
        },
    )
    assert res.status_code == 422
    # outcome predating registration refused (look-ahead guard)
    _register("P-GUARD-3")
    res = client.post(
        f"{PREFIX}/predictions/P-GUARD-3/outcome",
        json={
            "outcome_id": "OUT-PRE",
            "observed_at_utc": "2025-12-31T00:00:00Z",
            "observed_numeric": 1.0,
            "source_evidence_ids": ["E"],
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "outcome_predates_prediction_registration"
    # outcome for unknown prediction refused
    res = client.post(
        f"{PREFIX}/predictions/P-UNKNOWN/outcome",
        json={
            "outcome_id": "OUT-X",
            "observed_at_utc": "2026-02-02T00:00:00Z",
            "observed_numeric": 1.0,
            "source_evidence_ids": ["E"],
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "unknown_prediction_id"


def test_prediction_calibration_brier_ece_exact_and_leakage_guard() -> None:
    _register("P-CAL-1")
    client.post(
        f"{PREFIX}/predictions/P-CAL-1/outcome",
        json={
            "outcome_id": "OUT-P-CAL-1",
            "observed_at_utc": "2026-02-02T00:00:00Z",
            "observed_numeric": 1.0,
            "source_evidence_ids": ["E"],
        },
    )
    res = client.post(
        f"{PREFIX}/predictions/calibration",
        params={"measured_at_utc": "2026-03-01T00:00:00Z"},
        json={"pairs": [{"prediction_id": "P-CAL-1", "predicted_probability": 0.9, "observed": 1.0}]},
    )
    assert res.status_code == 200
    cal = res.json()["calibration"]
    assert cal["brier_score"] == pytest.approx(0.01)  # (0.9 - 1.0)²
    assert cal["expected_calibration_error"] == pytest.approx(0.1)
    assert cal["data_class"] == "SYNTHETIC"
    # non-binary observed refused by the engine contract
    res = client.post(
        f"{PREFIX}/predictions/calibration",
        params={"measured_at_utc": "2026-03-01T00:00:00Z"},
        json={"pairs": [{"prediction_id": "P-CAL-1", "predicted_probability": 0.9, "observed": 0.5}]},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "outcome_must_be_binary"
    # immature prediction binding refused (label leakage): P-CAL-2 has an
    # outcome but its horizon has NOT ended by the measurement instant
    res = client.post(
        f"{PREFIX}/predictions/register",
        json={
            "prediction_id": "P-CAL-2",
            "subject": "SYNTHETIC:فولاد",
            "registered_at_utc": "2026-01-01T00:00:00Z",
            "outcome_horizon_end_utc": "2026-04-01T00:00:00Z",
            "evaluation_metric": "DIRECTION_HIT",
            "event_maturity_rule": "horizon_end",
            "invalidation_rule": "subject_removed",
            "evidence_ids": ["DECLARED-PREDICTION-EVIDENCE"],
            "creator": "wave-f-tests",
        },
    )
    assert res.status_code == 200
    res = client.post(
        f"{PREFIX}/predictions/P-CAL-2/outcome",
        json={
            "outcome_id": "OUT-P-CAL-2",
            "observed_at_utc": "2026-02-15T00:00:00Z",
            "observed_numeric": 1.0,
            "source_evidence_ids": ["E"],
        },
    )
    assert res.status_code == 200
    res = client.post(
        f"{PREFIX}/predictions/calibration",
        params={"measured_at_utc": "2026-03-01T00:00:00Z"},
        json={"pairs": [{"prediction_id": "P-CAL-2", "predicted_probability": 0.9, "observed": 1.0}]},
    )
    assert res.status_code == 422
    assert "prediction_not_matured" in res.json()["detail"]["reason"]
    # outcome-missing prediction refused
    _register("P-CAL-3")
    res = client.post(
        f"{PREFIX}/predictions/calibration",
        params={"measured_at_utc": "2026-03-01T00:00:00Z"},
        json={"pairs": [{"prediction_id": "P-CAL-3", "predicted_probability": 0.9, "observed": 1.0}]},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "OUTCOME_NOT_RECORDED"
    # outcome observed AFTER the measurement instant is refused (no look-ahead)
    client.post(
        f"{PREFIX}/predictions/P-CAL-3/outcome",
        json={
            "outcome_id": "OUT-P-CAL-3",
            "observed_at_utc": "2026-03-02T00:00:00Z",
            "observed_numeric": 1.0,
            "source_evidence_ids": ["E"],
        },
    )
    res = client.post(
        f"{PREFIX}/predictions/calibration",
        params={"measured_at_utc": "2026-03-01T00:00:00Z"},
        json={"pairs": [{"prediction_id": "P-CAL-3", "predicted_probability": 0.9, "observed": 1.0}]},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "OUTCOME_AFTER_MEASUREMENT_REFUSED"
    # the same pair measured AFTER the outcome instant is accepted
    res = client.post(
        f"{PREFIX}/predictions/calibration",
        params={"measured_at_utc": "2026-03-03T00:00:00Z"},
        json={"pairs": [{"prediction_id": "P-CAL-3", "predicted_probability": 0.9, "observed": 1.0}]},
    )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Governance invariants
# ---------------------------------------------------------------------------


def test_route_surface_scoped_to_governed_prefix() -> None:
    schema = app.openapi()
    product_paths = [p for p in schema["paths"] if "productloops" in p]
    assert product_paths, "productloops routes must be registered"
    for path in product_paths:
        assert path.startswith("/api/v10/productloops")
    # COUNTER-PIN BUMP (recorded, WAVE-AB4 2026-11-08): 10 -> 11 — NEW
    # GET /api/v10/productloops/intel/coverage (WP-G/G1): the honest
    # CoverageReport contract finally surfaced at runtime (it had ZERO
    # production callers; declared fixture descriptors, all kill switches
    # ENGAGED, no uptime evidence invented). See test_wpg_gap_closure.py.
    # COUNTER-PIN BUMP (recorded, WAVE-AB5 2026-11-08): 11 -> 12 — NEW
    # GET /api/v10/productloops/predictions/calibration/by-regime (WP-I):
    # regime-sliced prediction performance over caller-DECLARED regime
    # labels (closed regime_slices vocabulary); empty regimes are honest
    # empty slices, never fabricated. See test_wpi_regime_and_proposals.py.
    assert len(product_paths) == 12  # manifest + dossier + coverage + research(2) + audit + predictions(6)


def test_gates_unchanged_in_default_settings() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.ai2_enabled is False


def test_all_payloads_carry_honesty_envelope() -> None:
    checks = [
        ("GET", f"{PREFIX}/manifest", None),
        ("GET", f"{PREFIX}/research/status", None),
        ("GET", f"{PREFIX}/predictions?as_of_utc={CUTOFF_LATE}", None),
    ]
    for method, url, json_body in checks:
        res = client.request(method, url, json=json_body)
        assert res.status_code == 200
        body = res.json()
        assert "honesty" in body
        honesty = body["honesty"]
        assert honesty["synthetic_note"]
        assert honesty["no_scheduler_note"]
        assert honesty["no_wall_clock_note"]
