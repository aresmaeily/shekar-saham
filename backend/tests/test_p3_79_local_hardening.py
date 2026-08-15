"""P3.79 adversarial tests: public-probe redaction, cookie auth, Electron origin lock."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings, is_verified_live
from app.core.security import SESSION_COOKIE, issue_session_token, request_is_authorized


ROOT = Path(__file__).resolve().parents[2]


def _client(monkeypatch, **env):
    keys = [
        "PRIVATE_MODE",
        "PRIVATE_PASSWORD",
        "API_KEY",
        "AUTH_REQUIRED",
        "ENV",
        "APP_ENV",
        "SHEKAR_ENV",
        "FERNET_KEY",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    get_settings.cache_clear()
    from app.main import create_app

    get_settings.cache_clear()
    return TestClient(create_app())


def test_request_is_authorized_requires_real_request():
    assert request_is_authorized(None) is False


def test_public_probes_never_claim_verified_live():
    from app.main import app

    client = TestClient(app)
    for path in ("/api/health", "/api/status", "/api/live/status"):
        res = client.get(path)
        assert res.status_code == 200
        body = res.json()
        trust = body.get("data_trust") or {}
        assert trust.get("live_verified") is not True
        assert trust.get("is_live") is not True
        assert is_verified_live(trust) is False
        assert body.get("trust_level") != "live" or is_verified_live(trust) is False


def test_private_mode_status_redacts_market_and_chat_ids(monkeypatch):
    client = _client(monkeypatch, PRIVATE_MODE="1", PRIVATE_PASSWORD="owner-secret")
    for path in ("/api/health", "/api/status", "/api/live/status"):
        res = client.get(path)
        assert res.status_code == 200
        body = res.json()
        assert body.get("redacted") is True
        assert body.get("private_ok") is False
        assert body.get("confluence") in ({}, None)
        assert body.get("store") in ({}, None)
        assert body.get("symbol_count") in (None, 0) or path == "/api/live/status"
        notifier = body.get("notifier") or {}
        assert "telegram_chat_id" not in notifier
        assert "bale_chat_id" not in notifier
        assert is_verified_live(body.get("data_trust") or {}) is False


def test_private_mode_status_full_with_api_key(monkeypatch):
    client = _client(
        monkeypatch,
        PRIVATE_MODE="1",
        PRIVATE_PASSWORD="owner-secret",
        API_KEY="correct-key",
    )
    res = client.get("/api/status", headers={"X-API-Key": "correct-key"})
    assert res.status_code == 200
    body = res.json()
    assert body.get("redacted") is not True
    assert "data_trust" in body
    assert is_verified_live(body.get("data_trust") or {}) is False


def test_health_accepts_cookie_session(monkeypatch):
    client = _client(monkeypatch, PRIVATE_MODE="1", PRIVATE_PASSWORD="owner-secret")
    denied = client.get("/api/health")
    assert denied.json().get("redacted") is True
    token = issue_session_token("owner-secret", {"sub": "owner"})
    client.cookies.set(SESSION_COOKIE, token)
    allowed = client.get("/api/health")
    assert allowed.status_code == 200
    body = allowed.json()
    assert body.get("ok") is True
    assert body.get("redacted") is False
    assert body.get("private_ok") is True
    assert is_verified_live(body.get("data_trust") or {}) is False


def test_live_status_does_not_leak_confluence_without_auth(monkeypatch):
    client = _client(monkeypatch, PRIVATE_MODE="1", PRIVATE_PASSWORD="owner-secret")
    res = client.get("/api/live/status")
    assert res.status_code == 200
    body = res.json()
    assert body.get("redacted") is True
    assert body.get("confluence") == {}
    assert body.get("notifier") == {}
    assert body.get("ws") == {}
    assert is_verified_live(body.get("data_trust") or {}) is False


def test_state_live_without_verification_is_not_live_on_status():
    from app.core.config import build_data_trust_context

    ctx = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010)
    assert ctx["state"] in {"live", "mixed", "stale"}
    assert ctx["is_live"] is False
    assert ctx["live_verified"] is False
    assert is_verified_live(ctx) is False


def test_electron_locks_navigation_to_configured_origin():
    src = (ROOT / "electron/main.js").read_text(encoding="utf-8")
    assert "will-navigate" in src
    assert "will-redirect" in src
    assert "isAllowedNavigation" in src
    assert "RADAR_BOURSE_URL || process.env.SHEKAR_URL" in src
    assert "nodeIntegration: false" in src
    assert "contextIsolation: true" in src


def test_public_path_contract_unchanged():
    from app.core.security import is_public_path

    assert is_public_path("/api/health") is True
    assert is_public_path("/api/status") is True
    assert is_public_path("/api/live/status") is True
    assert is_public_path("/api/analyze") is False


def test_auth_required_redacts_status_but_blocks_analyze(monkeypatch):
    client = _client(monkeypatch, AUTH_REQUIRED="1", API_KEY="correct-key")
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json().get("redacted") is True
    assert is_verified_live(status.json().get("data_trust") or {}) is False
    analyze = client.get("/api/analyze")
    assert analyze.status_code in {401, 403}
    allowed = client.get("/api/status", headers={"X-API-Key": "correct-key"})
    assert allowed.status_code == 200
    assert allowed.json().get("redacted") is not True
