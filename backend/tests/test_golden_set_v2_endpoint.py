"""2026-11-08 owner directive (§3 AI-7): the Golden Set v2 versioned
read-only endpoint — deterministic, digest-pinned fail-closed, baseline and
candidate separated, structural no-superiority pin carried verbatim.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, client=("gs2-endpoint", 12411))

ENDPOINT = "/api/v10/productloops/goldenset/v2/report"


def test_golden_set_v2_report_endpoint_read_only_and_honest() -> None:
    r = client.get(ENDPOINT)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["read_only"] is True
    assert body["report_kind"] == "GOLDEN_SET_V2_READ_ONLY_REPORT"
    assert body["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    report = body["report"]
    # 8 cases across all five kinds, all passing against REAL engines
    assert report["total_cases"] == 8
    assert report["passed"] == 8 and report["failed"] == 0
    assert report["false_positives_total"] == 0
    assert report["false_negatives_total"] == 0
    assert set(report["per_kind"]) == {
        "MARKET_INTERPRETATION",
        "SOURCE_CONFLICT",
        "FUNDAMENTAL_EXTRACTION",
        "REGIME_ROBUSTNESS",
        "CALIBRATION",
    }
    # baseline and candidate reported SEPARATELY — never merged into a winner
    assert report["baseline_results"]["corpus"] == "golden_set_v1"
    assert report["candidate_results"]["corpus"] == "golden_set_v2"
    assert report["baseline_results"]["corpus"] != report["candidate_results"]["corpus"]
    assert report["superiority_claimed"] is False
    assert "no superiority claim" in report["note"]
    # structural honesty envelope
    assert body["honesty"]["no_superiority_claim"]
    assert body["honesty"]["deterministic"]
    # every case carries its result row (nothing hidden)
    assert len(body["cases"]) == 8
    assert all(c["passed"] for c in body["cases"])


def test_golden_set_v2_report_endpoint_deterministic_double_run() -> None:
    r1 = client.get(ENDPOINT).json()
    r2 = client.get(ENDPOINT).json()
    assert r1 == r2  # exact byte-level JSON equality — no wall clock, no RNG
