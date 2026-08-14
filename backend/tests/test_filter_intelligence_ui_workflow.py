"""P3.58 Filter Intelligence UI approval workflow contract."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.filter_intelligence_service import filter_intelligence_service

ROOT = Path(__file__).resolve().parents[2]


def test_filter_intel_tab_and_panel_exist():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'data-tab="filter-intel"' in html
    assert 'id="tab-filter-intel"' in html
    assert 'id="fiProposalTable"' in html
    assert "فعال‌سازی خودکار" in html
    assert "Analyze → Propose → Validate → Human Review" in html


def test_filter_intel_ui_uses_existing_review_contract():
    js = (ROOT / "frontend/js/tabs/forms.js").read_text(encoding="utf-8")
    assert "bindFilterIntel" in js
    assert "/api/ai/filter-proposals" in js
    assert "APPROVE" in js and "REJECT" in js and "REQUEST_RETEST" in js
    assert "approval_does_not_auto_activate" in js
    assert "live_verified === true" in js


def test_filter_intel_compare_view_is_read_only():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/js/tabs/forms.js").read_text(encoding="utf-8")
    assert 'id="fiCompareTable"' in html
    assert 'id="fiPerfTable"' in html
    assert "مقایسه فقط‌خواندنی" in html
    assert "/api/ai/filters/compare" in js
    assert "evaluate=false" in js
    assert "loadFilterCompare" in js
    assert "production_mutation" in js
    assert "live_verified === true" in js
    assert "activate" not in js.lower() or "does not auto activate" in js.lower() or "فعال‌سازی خودکار انجام نشد" in js


def test_compare_api_is_read_only_and_not_live():
    client = TestClient(app)
    filters = client.get("/api/ai/filters").json()["filters"]
    assert filters
    item = filters[0]
    versions = [v["version"] for v in item.get("versions") or []]
    if len(versions) < 1:
        versions = [item.get("active_version") or "v1"]
    left = versions[0]
    right = versions[-1]
    active_before = filter_intelligence_service.get_filter(item["filter_id"]).active_version
    res = client.get(
        f"/api/ai/filters/compare?filter_id={item['filter_id']}&left_version={left}&right_version={right}"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    comparison = body["comparison"]
    trust = comparison.get("data_trust") or {}
    live = trust.get("state") == "live" and trust.get("is_live") is True and trust.get("live_verified") is True
    assert live is False
    after = filter_intelligence_service.get_filter(item["filter_id"])
    assert after.active_version == active_before
    perf = client.get(f"/api/ai/filters/{item['filter_id']}/performance?evaluate=false")
    assert perf.status_code == 200
    assert after.active_version == filter_intelligence_service.get_filter(item["filter_id"]).active_version


def test_review_does_not_activate_active_version():
    client = TestClient(app)
    filters = client.get("/api/ai/filters").json()["filters"]
    assert filters
    target = filters[0]["filter_id"]
    before = filter_intelligence_service.get_filter(target)
    assert before is not None
    active_before = before.active_version
    created = client.get(f"/api/ai/filter-proposals?filter_id={target}").json()["proposals"]
    assert created
    proposal_id = created[-1]["proposal_id"]
    reviewed = client.post(
        f"/api/ai/filter-proposals/{proposal_id}/review",
        json={"reviewer": "p3.58-test", "decision": "APPROVE", "reason": "ui-contract"},
    )
    assert reviewed.status_code == 200
    body = reviewed.json()
    assert body["ok"] is True
    assert body["review"]["resulting_status"] == "APPROVED"
    assert body["review"]["safety"]["approval_does_not_auto_activate"] is True
    after = filter_intelligence_service.get_filter(target)
    assert after is not None
    assert after.active_version == active_before
