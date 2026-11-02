"""WP-5 (CONSOL-NEXT / T6) — Controlled Alpha launch readiness, repo-side pins.

Additive-only regression tests (no existing file modified) verifying, offline
via FastAPI TestClient (no network):

1. ``GET /api/health`` answers 200 with the expected contract keys.
2. Version contract chain: backend ``settings.version`` == served version on
   ``/api/health`` and ``/api/status`` == ``electron/package.json`` ==
   ``frontend/manifest.json``; the frontend version display has a single
   source of truth (backend ``/api/health``) with NO hardcoded fallback.
3. Data-trust markers: in this repository ``verified`` is always False —
   a live-CLASS source is never marked verified (legacy ``trust_level``
   downgrades to ``mixed``), ``is_live``/``live_verified`` stay False even
   when a caller passes ``live_verified=True`` (compatibility-only argument),
   and ``is_verified_live()`` refuses every context minted here.

These pins record the exact shipped behavior so the Controlled Alpha posture
(no false LIVE) cannot silently regress. Target-machine install success is a
separate, owner-gated fact that these repo-side tests do NOT prove.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import (
    ROOT,
    build_data_trust_context,
    get_settings,
    is_verified_live,
)
from app.main import app

client = TestClient(app)

EXPECTED_VERSION = "3.0.0"
# Full (authorized) probe shape — routes.py `health()`.
HEALTH_FULL_KEYS = {
    "ok",
    "version",
    "source",
    "trust_level",
    "data_trust",
    "symbol_count",
    "last_fetch_ts",
    "has_analysis",
    "data_source_config",
    "poll_seconds",
    "store",
    "auth_required",
    "private_mode",
    "private_ok",
    "redacted",
    "market_session",
}
# Redacted (unauthorized) probe shape — routes.py `_redacted_probe()`: market
# payload is withheld (counts None, containers empty) but the trust/version
# contract stays visible. Both shapes are shipped behavior; the battery may
# run with an auth-enabled settings posture, so the exact contract is pinned
# per shape instead of assuming the full one.
HEALTH_REDACTED_KEYS = {
    "ok",
    "version",
    "source",
    "trust_level",
    "data_trust",
    "auth_required",
    "private_mode",
    "private_ok",
    "redacted",
    "poll_seconds",
    "symbol_count",
    "store",
    "flow_meta",
    "confluence",
    "notifier",
    "ws",
    "portfolio_count",
    "market_session",
}


# ---------------------------------------------------------------------------

def test_health_endpoint_responds_200_with_expected_keys():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    if body["redacted"] is False:
        missing = HEALTH_FULL_KEYS - set(body)
        assert not missing, f"/api/health full-probe keys missing: {sorted(missing)}"
        assert body["private_ok"] is True
    else:
        missing = HEALTH_REDACTED_KEYS - set(body)
        assert not missing, f"/api/health redacted-probe keys missing: {sorted(missing)}"
        # Privacy-by-design: unauthenticated probe gets no market payload.
        assert body["private_ok"] is False
        assert body["symbol_count"] is None
        assert body["store"] == {}


def test_health_version_matches_backend_settings():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["version"] == get_settings().version
    assert get_settings().version == EXPECTED_VERSION


def test_status_endpoint_version_matches_settings():
    res = client.get("/api/status")
    assert res.status_code == 200
    assert res.json()["version"] == get_settings().version


def test_version_chain_backend_electron_frontend_manifest():
    """Version contract chain: backend == electron == PWA manifest == 3.0.0."""
    backend_version = get_settings().version

    electron_pkg = json.loads(
        (ROOT / "electron" / "package.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "frontend" / "manifest.json").read_text(encoding="utf-8")
    )

    assert backend_version == EXPECTED_VERSION
    assert electron_pkg["version"] == backend_version, (
        "electron/package.json version drifted from backend settings.version"
    )
    assert manifest["version"] == backend_version, (
        "frontend/manifest.json version drifted from backend settings.version"
    )


def test_frontend_version_display_single_source_no_hardcoded_fallback():
    """WS-HARDEN-1/W4 contract: the frontend version display reads the backend
    /api/health response and ships NO hardcoded fallback version literal."""
    version_js = (
        ROOT / "frontend" / "js" / "modules" / "utils" / "version.js"
    ).read_text(encoding="utf-8")
    assert '/api/health' in version_js, (
        "frontend version display must fetch /api/health (single source of truth)"
    )
    assert EXPECTED_VERSION not in version_js, (
        "frontend version display must not hardcode the version string"
    )


# ---------------------------------------------------------------------------
# Data-trust markers: verified=False posture, pinned exactly as shipped.


def test_data_trust_live_class_source_is_never_marked_verified():
    now = 1_000_000.0
    ctx = build_data_trust_context(
        "tsetmc", timestamp=now - 10, checked_at=now, stale_after_sec=300
    )
    assert ctx["state"] == "live"  # live-CLASS source label...
    assert ctx["live_verified"] is False  # ...but never verified here
    assert ctx["is_live"] is False
    assert ctx["trust_level"] == "mixed"  # legacy marker downgraded
    assert "not independently verified" in ctx["warning"]


def test_data_trust_live_verified_argument_is_ignored():
    """``live_verified=True`` is an unused compatibility argument — no caller,
    including tests, can mint verified LIVE through build_data_trust_context."""
    now = 1_000_000.0
    ctx = build_data_trust_context(
        "tsetmc",
        timestamp=now - 10,
        checked_at=now,
        stale_after_sec=300,
        live_verified=True,
    )
    assert ctx["live_verified"] is False
    assert ctx["is_live"] is False
    assert ctx["trust_level"] == "mixed"


def test_is_verified_live_refuses_repo_minted_contexts():
    now = 1_000_000.0
    ctx = build_data_trust_context(
        "tsetmc", timestamp=now - 10, checked_at=now, stale_after_sec=300
    )
    assert is_verified_live(ctx) is False
    assert is_verified_live(None) is False
    assert is_verified_live({}) is False
    # Even a hand-crafted "state=live + is_live" dict without the explicit
    # live_verified flag is refused (all three markers must be true).
    assert (
        is_verified_live({"state": "live", "is_live": True, "live_verified": False})
        is False
    )


def test_non_live_sources_report_non_verified_markers():
    now = 1_000_000.0
    for source in ("mock", "synthetic_bootstrap", "cache", "none"):
        ctx = build_data_trust_context(
            source, timestamp=now - 10, checked_at=now, stale_after_sec=300
        )
        assert ctx["live_verified"] is False, source
        assert ctx["is_live"] is False, source
        assert ctx["state"] != "live", source


def test_health_data_trust_marks_reflect_non_verified_posture():
    """The served /api/health data_trust block must carry the honest, non-verified
    markers (no false LIVE), whatever the offline source state is."""
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    trust = body["data_trust"]
    assert trust["live_verified"] is False
    assert trust["is_live"] is False
    assert body["trust_level"] != "live"
    assert trust["state"] in {"live", "mixed", "mock", "synthetic", "stale", "unavailable"}
    if trust["state"] == "live":
        # Even in the live-CLASS case the served legacy marker stays "mixed".
        assert trust["trust_level"] == "mixed"
        assert "not independently verified" in trust["warning"]
