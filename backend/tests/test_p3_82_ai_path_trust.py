"""P3.82: remaining AI-path data-trust closures."""

from fastapi.testclient import TestClient

from app.core.config import is_verified_live
from app.main import app


def test_chart_ai_overlay_carries_data_trust():
    client = TestClient(app)
    client.get("/api/analyze")
    res = client.get("/api/v08/chart/فملی/ai-overlay")
    assert res.status_code == 200
    body = res.json()
    assert body.get("provider") == "fallback"
    assert body.get("live_llm") is False
    assert body.get("verified_live") is False
    assert is_verified_live(body.get("data_trust") or {}) is False
    assert "confidence" in body
    assert "warnings" in body
    assert "source" in body


def test_stop_loss_and_portfolio_opt_carry_data_trust():
    client = TestClient(app)
    client.get("/api/analyze")
    sl = client.get("/api/v07/risk/stop-loss/فملی")
    assert sl.status_code == 200
    assert is_verified_live(sl.json().get("data_trust") or {}) is False
    po = client.get("/api/v07/portfolio/optimization")
    assert po.status_code == 200
    assert is_verified_live(po.json().get("data_trust") or {}) is False
    assert po.json().get("live_llm") is False
