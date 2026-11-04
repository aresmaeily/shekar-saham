"""WDA-1 — cross-artifact version consistency gate.

Chain checked (artifact-level, import-free — complements
``test_wp5_launch_readiness.py`` / ``test_ws_harden1_version_sync.py`` which
assert the same chain through ``get_settings()``):

    backend/app/core/config.py ``version``  (single source of truth, 3.0.0)
      == electron/package.json ``version``
      == frontend/manifest.json (PWA) ``version``
      == frontend/index.html header paint ``<span class="ver">v…</span>``

The sw.js cache token is verified for internal consistency only — it is an
independent cache-bust counter (see the test docstring below), not a member
of the semantic-version chain.

Honest notes (do-not-invent-artifacts):
- The config module lives at ``backend/app/core/config.py`` (not
  ``backend/app/config.py``) — the single source of truth documented by
  WS-HARDEN-1/W4 and GOV-24/WP-2.
- The frontend has NO ``package.json`` and no own version constant; its
  authoritative version display is fetched from ``/api/health``
  (``modules/utils/version.js``), i.e. backend ``settings.version``. That
  documented single-source relationship is asserted here instead of an
  invented frontend version artifact.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CONFIG_PY = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
ELECTRON_PKG = json.loads((ROOT / "electron" / "package.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "frontend" / "manifest.json").read_text(encoding="utf-8"))
SW_JS = (ROOT / "frontend" / "sw.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

EXPECTED_VERSION = "3.0.0"


def _backend_version() -> str:
    m = re.search(r'version:\s*str\s*=\s*"([^"]+)"', CONFIG_PY)
    assert m, "backend settings.version literal not found in app/core/config.py"
    return m.group(1)


def test_backend_config_version_is_expected():
    """backend/app/core/config.py carries the expected 3.0.0 literal."""
    assert _backend_version() == EXPECTED_VERSION


def test_electron_package_version_matches_backend():
    assert ELECTRON_PKG["version"] == _backend_version()


def test_pwa_manifest_version_matches_backend():
    assert MANIFEST["version"] == _backend_version()


def test_sw_cache_token_is_consistent_within_sw_js():
    """Honest finding (WDA-1, 2026-11-03): the sw.js CACHE_NAME token is an
    INDEPENDENT cache-bust counter (``radar-bourse-static-v3-0-N``, bumped on
    precache-list changes per WS-10 / MASTER-RADAR) — it is deliberately NOT
    derived from the app semantic version, so no version-chain equality is
    asserted for it. What is pinned here: the token family/format is
    consistent between the CACHE_NAME literal and the sw.js header comment,
    and the pinned literal matches the one test_p3_80_local_closure.py
    enforces (currently v3-0-7, MASTER-RADAR WAVE-2 2026-11-04 bump)."""
    m = re.search(r'const CACHE_NAME = "([^"]+)"', SW_JS)
    assert m, "CACHE_NAME not found in sw.js"
    token = m.group(1)
    assert re.fullmatch(r"radar-bourse-static-v\d+-\d+-\d+", token), token
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR 2026-11-04): v3-0-5 -> v3-0-6 —
    # precache list extended with strategy_lab.js (new authorized Strategy Lab
    # tab); same recorded bump discipline as WS-10 (v3-0-4 -> v3-0-5).
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-2 2026-11-04): v3-0-6 -> v3-0-7 —
    # precache list extended with the three new render modules
    # (backtest_center.js / forward_center.js / data_quality_center.js).
    assert token == "radar-bourse-static-v3-0-7"
    # Header comment must tell the same story (dots variant), no drift.
    assert "Service Worker v3.0.7" in SW_JS


def test_index_html_header_paint_shows_backend_version():
    ver = _backend_version()
    assert f'<span class="ver">v{ver}</span>' in INDEX_HTML


def test_frontend_has_no_own_version_package_json():
    """No frontend/package.json exists — the frontend derives its version from
    the backend single source (/api/health via modules/utils/version.js).
    Asserted as documented absence; nothing is invented here."""
    assert not (ROOT / "frontend" / "package.json").exists()
    version_js = (ROOT / "frontend" / "js" / "modules" / "utils" / "version.js").read_text(encoding="utf-8")
    assert "/api/health" in version_js
