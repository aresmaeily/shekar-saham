"""P3.80: remaining local security/quality closures."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings, is_verified_live


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
        "COOKIE_SECURE",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    get_settings.cache_clear()
    from app.main import create_app

    get_settings.cache_clear()
    return TestClient(create_app())


def test_service_worker_does_not_cache_api():
    sw = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    api_idx = sw.find('pathname.startsWith("/api/")')
    assert api_idx != -1
    api_block = sw[api_idx : api_idx + 280]
    assert "caches.open" not in api_block
    assert "cache.put" not in api_block
    assert "caches.match" not in api_block
    assert "event.respondWith(fetch(req))" in api_block


def test_service_worker_cache_name_bumped_to_drop_old_api_entries():
    sw = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    assert "shekar-v3-0-1" not in sw
    # WS-HARDEN-1/W3: cache list changed (legacy-loader entry dropped) -> bump to v3-0-3
    # WS-10 (2026-11-02): precache list extended with chart_pro.css/js -> bump to v3-0-5
    # MASTER-RADAR (2026-11-04): precache extended with strategy_lab.js -> bump to v3-0-6 (recorded counter-pin bump)
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-2 2026-11-04): v3-0-6 -> v3-0-7 —
    # precache list extended with the three new render modules
    # (backtest_center.js / forward_center.js / data_quality_center.js)
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-3 2026-11-04): v3-0-7 -> v3-0-8 —
    # precache list extended with chart_grid.js + command_palette.js
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-E 2026-11-05): v3-0-12 -> v3-0-13 (SW install cache:reload honesty fix) — prior chain v3-0-8 -> v3-0-9 -> v3-0-10 -> v3-0-11 -> v3-0-12 (WAVE-B popup fix, WAVE-D PDF export, WAVE-E declared calendars) — prior chain v3-0-8 -> v3-0-9 -> v3-0-10 -> v3-0-11 (WAVE-B popup fix, WAVE-D PDF export) — prior chain v3-0-8 -> v3-0-9 -> v3-0-10 (WAVE-B popup-detach-intent fix)
    assert "radar-bourse-static-v3-0-14" in sw
    assert "radar-bourse-static-v3-0-9" not in sw


def test_production_disables_openapi_docs(monkeypatch):
    client = _client(
        monkeypatch,
        ENV="production",
        PRIVATE_MODE="1",
        PRIVATE_PASSWORD="owner-secret",
        API_KEY="stable-key",
        FERNET_KEY="stable-fernet-not-used-at-import",
        COOKIE_SECURE="1",
    )
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_non_production_keeps_docs(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_chart_builder_has_no_bare_except():
    src = (ROOT / "backend/app/engines/chart_builder.py").read_text(encoding="utf-8")
    assert "except:" not in src
    assert "except (TypeError, ValueError):" in src


def test_sw_js_is_not_long_cached():
    from app.main import app

    client = TestClient(app)
    res = client.get("/static/sw.js")
    assert res.status_code == 200
    assert "no-store" in (res.headers.get("Cache-Control") or "")


def test_probes_still_not_verified_live():
    from app.main import app

    client = TestClient(app)
    for path in ("/api/health", "/api/status", "/api/live/status"):
        body = client.get(path).json()
        assert is_verified_live(body.get("data_trust") or {}) is False
