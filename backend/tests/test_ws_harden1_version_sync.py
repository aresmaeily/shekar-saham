"""WS-HARDEN-1/W4 — UI version sync regression tests.

Single source of truth: backend ``settings.version`` (config.py:28, "3.0.0").
Before this workstream the FastAPI description claimed "v0.7.0", the Excellent
tab/heading claimed "v0.7", frontend header comments claimed "v0.6.2", and the
default UI never synced the real version from the API.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "index.html"
MAIN_JS = ROOT / "frontend" / "js" / "main.js"
VERSION_JS = ROOT / "frontend" / "js" / "modules" / "utils" / "version.js"


def test_app_version_is_settings_version():
    from app.main import create_app

    assert create_app().version == get_settings().version


def test_app_description_has_no_legacy_version_literal():
    from app.main import create_app

    description = create_app().description
    assert "v0.7.0" not in description
    assert "Excellent Edition" in description  # edition branding kept


def test_health_payload_version_matches_settings():
    from app.main import create_app

    client = TestClient(create_app())
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["version"] == get_settings().version


def test_index_html_initial_paint_matches_settings_version():
    ver = get_settings().version
    idx = INDEX.read_text(encoding="utf-8")
    assert f'<span class="ver">v{ver}</span>' in idx
    assert f"رادار بورس v{ver} — معماری Meta" in idx
    assert "v0.7" not in idx  # divergent edition-version labels removed


def test_main_js_syncs_version_from_api():
    main_js = MAIN_JS.read_text(encoding="utf-8")
    assert 'from "./modules/utils/version.js"' in main_js
    assert "updateVersionFromApi();" in main_js
    version_js = VERSION_JS.read_text(encoding="utf-8")
    assert '"0.6.2"' not in version_js  # stale hardcoded fallback removed
