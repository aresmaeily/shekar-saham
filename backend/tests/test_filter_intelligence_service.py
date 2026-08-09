from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import build_data_trust_context
from app.data.mock_market import generate_mock_market
from app.data.store import Store
from app.domain.filter_intelligence import PerformanceRecord
from app.main import app
from app.services.filter_intelligence_service import FilterIntelligenceService


class DummyMarketService:
    def __init__(self):
        self._last_symbols = generate_mock_market(12)

    async def get_analysis(self, force=False):
        return None

    def data_trust_context(self):
        return build_data_trust_context("mock")

    def get_confluence(self):
        return {"summary": {"buy_alerts": 0, "sell_alerts": 0}}


def _service(tmp_path: Path) -> FilterIntelligenceService:
    return FilterIntelligenceService(Store(tmp_path / "p341.db"))


def test_filter_registry_has_identity_versions_and_metadata(tmp_path):
    svc = _service(tmp_path)
    rows = svc.list_filters()
    assert rows
    item = rows[0]
    assert item.filter_id
    assert item.active_version == "v1"
    assert item.versions[0].conditions
    assert item.versions[0].status == "ACTIVE"
    assert item.versions[0].safety["requires_human_approval"] is True


def test_filter_versioning_creates_immutable_new_version(tmp_path):
    svc = _service(tmp_path)
    item = svc.list_filters()[0]
    old = item.versions[0]
    new = svc.create_version(item.filter_id, old.conditions + " and entry_score >= 50", description="test version")
    updated = svc.get_filter(item.filter_id)
    assert new.version == "v2"
    assert new.parent_version == "v1"
    assert updated.latest_version == "v2"
    assert updated.active_version == "v1"
    assert updated.versions[0].conditions == old.conditions


def test_performance_record_and_data_trust_blocking(tmp_path):
    svc = _service(tmp_path)
    fv = svc.get_version(svc.list_filters()[0].filter_id)
    record = PerformanceRecord(
        record_id="r1",
        filter_id=fv.filter_id,
        version=fv.version,
        evaluation_mode="FORWARD_TEST",
        evaluation_period="unit",
        sample_size=10,
        signal_count=10,
        win_rate=70,
        average_return=1.2,
        median_return=1.0,
        profit_factor=1.8,
        max_drawdown=5,
        sharpe=1.1,
        stability_score=80,
        regime="BULLISH",
        data_trust=build_data_trust_context("mock"),
        timestamp="2026-08-09T00:00:00+00:00",
    )
    cls, reasons = svc._classification(record, live_required=True)
    assert cls == "INSUFFICIENT_DATA"
    assert "DATA_TRUST_BLOCK" in reasons


@pytest.mark.asyncio
async def test_backtest_walk_forward_forward_integration_and_analysis(tmp_path):
    svc = _service(tmp_path)
    item = svc.list_filters()[0]
    result = await svc.evaluate_filter(DummyMarketService(), item.filter_id, persist=True, bars=60)
    modes = {r["evaluation_mode"] for r in result["records"]}
    assert modes == {"BACKTEST", "WALK_FORWARD", "FORWARD_TEST"}
    assert result["analysis"]["safety"]["ai_can_modify_production"] is False
    assert all(r["data_trust"]["state"] in {"synthetic", "mock", "mixed", "unavailable", "stale", "live"} for r in result["records"])
    assert all("classification" in r for r in result["records"])


def test_decay_detection_requires_sufficient_evidence(tmp_path):
    svc = _service(tmp_path)
    item = svc.list_filters()[0]
    decay = svc.detect_decay(item.filter_id, "v1", [])
    assert decay.status == "INSUFFICIENT_DATA"
    assert "NEEDS_BACKTEST_WALK_FORWARD_FORWARD_RECORDS" in decay.reason_codes


def test_ai_analysis_detects_decay_with_forward_confirmation(tmp_path):
    svc = _service(tmp_path)
    fid = svc.list_filters()[0].filter_id
    trust = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010)
    records = [
        PerformanceRecord(record_id="b", filter_id=fid, version="v1", evaluation_mode="BACKTEST", evaluation_period="hist", sample_size=20, signal_count=30, win_rate=68, average_return=1.5, profit_factor=1.6, max_drawdown=10, stability_score=70, regime="BULLISH", data_trust=trust, timestamp="t"),
        PerformanceRecord(record_id="w", filter_id=fid, version="v1", evaluation_mode="WALK_FORWARD", evaluation_period="wf", sample_size=5, signal_count=20, win_rate=55, average_return=0.4, profit_factor=1.1, max_drawdown=12, stability_score=65, regime="NEUTRAL", data_trust=trust, timestamp="t"),
        PerformanceRecord(record_id="f", filter_id=fid, version="v1", evaluation_mode="FORWARD_TEST", evaluation_period="fwd", sample_size=20, signal_count=15, win_rate=43, average_return=-0.3, profit_factor=0.9, max_drawdown=18, stability_score=45, regime="NEUTRAL", data_trust=trust, timestamp="t"),
    ]
    analysis = svc.analyze_records(fid, "v1", records)
    assert analysis.classification == "DEGRADING"
    assert analysis.decay.status == "PERFORMANCE_DECAY"
    assert analysis.recommendation == "REVIEW_OR_PAUSE_AFTER_HUMAN_VALIDATION"


def test_proposal_creation_and_human_review_contract(tmp_path):
    svc = _service(tmp_path)
    item = svc.list_filters()[0]
    proposal = svc.create_proposal(item.filter_id)
    assert proposal.status == "PROPOSED"
    assert proposal.human_approval_required is True
    assert proposal.production_mutation is False
    review = svc.review_proposal(proposal.proposal_id, "qa", "REQUEST_RETEST", "needs larger sample")
    assert review.decision == "REQUEST_RETEST"
    assert review.safety["approval_does_not_auto_activate"] is True


def test_filter_version_comparison_contract(tmp_path):
    svc = _service(tmp_path)
    item = svc.list_filters()[0]
    svc.create_version(item.filter_id, item.versions[0].conditions + " and entry_score >= 50")
    comparison = svc.compare_versions(item.filter_id, "v1", "v2")
    assert comparison.metrics["win_rate"]["left"] == "NOT_AVAILABLE"
    assert comparison.conclusion == "INSUFFICIENT_DATA"


def test_filter_intelligence_api_smoke():
    c = TestClient(app)
    r = c.get("/api/ai/filters")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["filters"]
    fid = data["filters"][0]["filter_id"]
    for path in [f"/api/ai/filters/{fid}", f"/api/ai/filters/{fid}/versions", f"/api/ai/filters/{fid}/performance", "/api/ai/filter-intelligence?limit=1&persist=false"]:
        rr = c.get(path)
        assert rr.status_code == 200, path
        assert rr.json().get("ok") is True
    prop = c.get(f"/api/ai/filter-proposals?filter_id={fid}")
    assert prop.status_code == 200
    proposal_id = prop.json()["proposals"][0]["proposal_id"]
    review = c.post(f"/api/ai/filter-proposals/{proposal_id}/review", json={"reviewer": "qa", "decision": "REJECT", "reason": "unit test"})
    assert review.status_code == 200
    assert review.json()["review"]["resulting_status"] == "REJECTED"
