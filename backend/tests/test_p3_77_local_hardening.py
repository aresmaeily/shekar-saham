"""P3.77 adversarial tests: remaining local trust/security/volume holes."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from app.core.config import build_data_trust_context, is_verified_live
from app.data.providers import brsapi_row_to_snapshot, tsetmc_mw_to_snapshot
from app.domain.ai_intelligence import AIIntelligenceCore
from app.engines.metrics import compute_metrics
from app.services.filter_intelligence_service import _trust_live
from app.services.notifier import Notifier


ROOT = Path(__file__).resolve().parents[2]


def _verified_live_test_object() -> dict:
    """TEST-CONSTRUCTED VERIFIED LIVE — not produced by production builders."""
    return {
        "state": "live",
        "is_live": True,
        "live_verified": True,
        "trust_level": "live",
        "source": "tsetmc",
    }


def test_tsetmc_plus_fresh_timestamp_is_not_verified_live():
    now = time.time()
    ctx = build_data_trust_context("tsetmc", timestamp=now - 5, checked_at=now)
    assert ctx["state"] == "live"
    assert ctx["is_live"] is False
    assert ctx["live_verified"] is False
    assert ctx["trust_level"] != "live"
    assert is_verified_live(ctx) is False


def test_brsapi_plus_fresh_timestamp_is_not_verified_live():
    now = time.time()
    ctx = build_data_trust_context("brsapi", timestamp=now - 5, checked_at=now)
    assert ctx["live_verified"] is False
    assert ctx["is_live"] is False
    assert is_verified_live(ctx) is False


def test_source_label_alone_is_not_verified_live():
    ctx = build_data_trust_context("tsetmc")
    assert is_verified_live(ctx) is False
    assert ctx["live_verified"] is False


def test_timestamp_alone_is_not_verified_live():
    now = time.time()
    ctx = build_data_trust_context("unknown", timestamp=now - 1, checked_at=now)
    assert ctx["state"] != "live" or ctx["live_verified"] is False
    assert is_verified_live(ctx) is False


def test_trust_level_live_alone_is_not_verified_live():
    assert is_verified_live({"trust_level": "live"}) is False
    assert is_verified_live({"state": "live", "trust_level": "live"}) is False


def test_production_builder_cannot_mint_live_verified():
    ctx = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010, live_verified=True)
    assert ctx["live_verified"] is False
    assert ctx["is_live"] is False
    assert is_verified_live(ctx) is False


def test_fallback_synthetic_stale_unavailable_remain_non_live():
    now = time.time()
    cases = [
        build_data_trust_context("mock_fallback", timestamp=now - 5, checked_at=now),
        build_data_trust_context("synthetic", timestamp=now - 5, checked_at=now),
        build_data_trust_context("tsetmc", timestamp=now - 10_000, checked_at=now, stale_after_sec=300),
        build_data_trust_context("none", checked_at=now),
    ]
    for ctx in cases:
        assert ctx["is_live"] is False
        assert ctx["live_verified"] is False
        assert is_verified_live(ctx) is False
        assert ctx["state"] in {"mock", "synthetic", "stale", "unavailable", "mixed"}


def test_missing_avg_vol_30d_does_not_fabricate_or_spike():
    snap = tsetmc_mw_to_snapshot(
        {"l18": "فملی", "pl": 1000, "pc": 990, "py": 980, "tvol": 500_000, "bvol": 10_000, "baseVol": 10_000}
    )
    assert snap is not None
    assert snap.avg_vol_30d == 0.0
    metrics = compute_metrics(snap)
    assert metrics.volume_ratio == 0.0
    assert metrics.is_volume_spike is False
    assert metrics.is_strong_volume_spike is False
    brs = brsapi_row_to_snapshot({"l18": "فولاد", "pl": 800, "tvol": 1000, "bvol": 200})
    assert brs.avg_vol_30d == 0.0


def test_frontend_live_requires_triple_gate():
    files = [
        ROOT / "frontend/js/main.js",
        ROOT / "frontend/js/modules/render/trust.js",
        ROOT / "frontend/js/tabs/data.js",
        ROOT / "frontend/js/tabs/forms.js",
        ROOT / "frontend/js/legacy/app.js",
        ROOT / "frontend/js/modules/forex.js",
    ]
    for path in files:
        js = path.read_text(encoding="utf-8")
        assert "live_verified === true" in js or "liveVerified === true" in js, path.name
    forex = (ROOT / "frontend/js/modules/forex.js").read_text(encoding="utf-8")
    assert "زنده ✅" not in forex
    legacy = (ROOT / "frontend/js/legacy/app.js").read_text(encoding="utf-8")
    assert "زنده · " not in legacy
    assert "isVerifiedLive" in legacy
    main = (ROOT / "frontend/js/main.js").read_text(encoding="utf-8")
    assert "isVerifiedLive" in main
    assert "خودکار" in main


def test_ws_and_confluence_use_canonical_context():
    service = (ROOT / "backend/app/services/market_service.py").read_text(encoding="utf-8")
    assert 'board["data_trust"] = trust_ctx' in service
    main_py = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert '"data_trust": trust_ctx' in main_py
    routes = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
    assert "data_trust=trust_ctx" in routes


def test_notifier_blocks_unverified_live_class_even_if_trust_level_live(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("NOTIFY_ENABLED", "1")
    get_settings.cache_clear()
    ctx = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010)
    notifier = Notifier()
    sent = asyncio.run(
        notifier.process_alerts([], [], trust_level="live", data_trust=ctx)
    )
    get_settings.cache_clear()
    assert sent == 0
    assert is_verified_live(ctx) is False


def test_notifier_format_does_not_treat_trust_level_live_as_verified():
    notifier = Notifier()
    text = notifier.format_alert(
        {
            "symbol": "فملی",
            "side": "buy",
            "score": 90,
            "trust_level": "live",
            "data_trust": build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010),
        }
    )
    assert "داده زنده" not in text
    assert "تأییدنشده" in text or "آزمایشی" in text
    verified_text = notifier.format_alert(
        {
            "symbol": "فملی",
            "side": "buy",
            "score": 90,
            "trust_level": "live",
            "data_trust": _verified_live_test_object(),
        }
    )
    assert "تأییدنشده" not in verified_text
    assert "آزمایشی/تأییدنشده" not in verified_text


def test_ai_and_filter_block_unverified_live_class():
    ctx = {
        "state": "live",
        "is_live": False,
        "live_verified": False,
        "source": "tsetmc",
        "trust_level": "mixed",
    }
    assert _trust_live(ctx) is False
    core = AIIntelligenceCore()
    result = core.evaluate(
        symbol_context={
            "snapshot": {"l18": "فملی"},
            "metrics": {"entry_score": 90, "exit_score": 5, "buy_power": 3, "volume_ratio": 3, "individual_net_value": 1},
            "tablocastic": {},
            "fundamental": {},
        },
        data_trust=ctx,
    )
    assert result.recommendation == "INSUFFICIENT_DATA"
    assert is_verified_live(ctx) is False


def test_forex_api_source_label_cannot_mint_live():
    src = (ROOT / "backend/app/api/forex.py").read_text(encoding="utf-8")
    assert "trust_level = \"live\"" not in src
    assert "build_data_trust_context" in src
    assert "data_trust" in src


def test_backtest_metrics_name_sharpe_as_per_trade():
    from app.engines.backtest import run_filter_strategy_backtest

    paths = {
        "فملی": [
            {"ts": 1, "symbol": "فملی", "pl": 100, "entry_score": 80},
            {"ts": 2, "symbol": "فملی", "pl": 101},
            {"ts": 3, "symbol": "فملی", "pl": 102},
        ]
    }
    report = run_filter_strategy_backtest(paths, "entry_score > 1", data_trust=build_data_trust_context("synthetic"))
    assert report["metrics"]["sharpe_basis"] == "per_trade_return_not_annualized"
    assert report["quant_safety"]["same_bar_tp_sl"].startswith("close_of_decision_bar")
    assert report["data_trust"]["is_live"] is False
    assert report["data_trust"]["live_verified"] is False
