"""P3.76 adversarial follow-up: no mintable LIVE, primary UI triple-gate."""

from pathlib import Path

from app.core.config import build_data_trust_context, is_verified_live
from app.domain.market_session import infer_iran_market_session
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]


def test_build_context_cannot_mint_live_verified():
    ctx = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010, live_verified=True)
    assert ctx["live_verified"] is False
    assert ctx["is_live"] is False
    assert is_verified_live(ctx) is False


def test_session_open_is_not_verified_live():
    session = infer_iran_market_session(datetime(2026, 8, 15, 6, 30, tzinfo=timezone.utc))
    ctx = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010)
    assert session.is_open is True
    assert is_verified_live(ctx) is False


def test_main_js_primary_trust_pill_requires_live_verified():
    js = (ROOT / "frontend/js/main.js").read_text(encoding="utf-8")
    assert "live_verified === true" in js
    assert "isVerifiedLive" in js
    assert "renderTrustBanner" in js
    assert 'text.textContent = "LIVE"' in js
    assert "زنده · " not in js


def test_trust_js_and_forms_remain_triple_gated():
    trust = (ROOT / "frontend/js/modules/render/trust.js").read_text(encoding="utf-8")
    forms = (ROOT / "frontend/js/tabs/forms.js").read_text(encoding="utf-8")
    assert "liveVerified === true" in trust or "live_verified === true" in trust
    assert "live_verified === true" in forms
