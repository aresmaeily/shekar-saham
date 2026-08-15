"""P3.75 adversarial tests: no fake LIVE, no fabricated 30-day volume."""

import time

from app.core.config import build_data_trust_context, is_verified_live
from app.data.providers import brsapi_row_to_snapshot, tsetmc_mw_to_snapshot
from app.domain.ai_intelligence import AIIntelligenceCore
from app.engines.metrics import compute_metrics
from app.models.schemas import SymbolSnapshot
from app.services.filter_intelligence_service import _trust_live
from app.services.notifier import Notifier


def test_tsetmc_label_plus_fresh_timestamp_is_not_verified_live():
    now = time.time()
    ctx = build_data_trust_context("tsetmc", timestamp=now - 5, checked_at=now)
    assert ctx["live_verified"] is False
    assert ctx["is_live"] is False
    assert is_verified_live(ctx) is False


def test_brsapi_label_plus_fresh_timestamp_is_not_verified_live():
    now = time.time()
    ctx = build_data_trust_context("brsapi", timestamp=now - 5, checked_at=now)
    assert ctx["live_verified"] is False
    assert ctx["is_live"] is False
    assert is_verified_live(ctx) is False


def test_state_live_is_live_true_without_live_verified_is_not_valid_live():
    ctx = {
        "state": "live",
        "is_live": True,
        "live_verified": False,
        "source": "tsetmc",
    }
    assert is_verified_live(ctx) is False
    assert _trust_live(ctx) is False
    core = AIIntelligenceCore()
    result = core.evaluate(
        symbol_context={
            "snapshot": {"l18": "فملی"},
            "metrics": {"entry_score": 80, "exit_score": 5, "buy_power": 2, "volume_ratio": 2, "individual_net_value": 1},
            "tablocastic": {},
            "fundamental": {"is_synthetic": True},
        },
        data_trust=ctx,
    )
    assert result.recommendation == "INSUFFICIENT_DATA"


def test_only_triple_gate_is_verified_live():
    ctx = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010, live_verified=True)
    assert ctx["state"] == "live"
    assert ctx["is_live"] is True
    assert ctx["live_verified"] is True
    assert is_verified_live(ctx) is True
    assert _trust_live(ctx) is True


def test_trust_level_live_override_cannot_fabricate_verification(monkeypatch):
    from app.core.config import Settings, classify_data_trust_state

    settings = Settings(trust_level_override="live")
    assert classify_data_trust_state("mock_fallback", settings) == "mock"
    ctx = build_data_trust_context("mock_fallback", timestamp=1000, checked_at=1010, settings=settings)
    assert ctx["live_verified"] is False
    assert ctx["is_live"] is False
    assert is_verified_live(ctx) is False


def test_missing_avg_vol_30d_is_not_fabricated_from_bvol():
    snap = tsetmc_mw_to_snapshot(
        {
            "l18": "فملی",
            "pl": 1000,
            "pc": 990,
            "py": 980,
            "tvol": 500_000,
            "bvol": 10_000,
            "baseVol": 10_000,
        }
    )
    assert snap is not None
    assert snap.avg_vol_30d == 0.0
    metrics = compute_metrics(snap)
    assert metrics.volume_ratio == 0.0
    assert metrics.is_volume_spike is False


def test_brsapi_missing_avg_vol_30d_is_not_fabricated():
    snap = brsapi_row_to_snapshot({"l18": "فولاد", "pl": 800, "tvol": 1000, "bvol": 200})
    assert snap.avg_vol_30d == 0.0


def test_explicit_avg_vol_30d_is_preserved():
    snap = brsapi_row_to_snapshot({"l18": "فولاد", "pl": 800, "tvol": 2000, "avg_vol_30d": 1000})
    assert snap.avg_vol_30d == 1000
    metrics = compute_metrics(snap)
    assert metrics.volume_ratio == 2.0


def test_notifier_blocks_unverified_live_class(monkeypatch):
    import asyncio

    from app.core.config import get_settings

    monkeypatch.setenv("NOTIFY_ENABLED", "1")
    get_settings.cache_clear()
    notifier = Notifier()
    ctx = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010)
    sent = asyncio.run(
        notifier.process_alerts(
            [],
            [],
            trust_level="live",
            data_trust=ctx,
        )
    )
    get_settings.cache_clear()
    assert sent == 0
    assert is_verified_live(ctx) is False


def test_mock_snapshot_still_has_declared_average():
    snap = SymbolSnapshot(l18="تست", pl=100, tvol=200, avg_vol_30d=100, source="mock")
    metrics = compute_metrics(snap)
    assert metrics.volume_ratio == 2.0
