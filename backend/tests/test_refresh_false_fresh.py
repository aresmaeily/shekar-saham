"""WS-1 false-fresh regression tests — market_service.refresh timestamp honesty.

Audit finding (2026-11-02 consolidated multi-agent audit, Agent 2 / WS-1):
when ``provider.fetch()`` RAISED, refresh() fell back to the recycled
``_last_symbols`` and then Phase 3 unconditionally re-stamped
``_last_fetch_ts = time.time()`` — masking the failure so the trust context
could never report ``stale`` for that cycle.

Fix under test: a degraded cycle keeps the PREVIOUS fetch timestamp (so
``build_data_trust_context`` sees the true age), and the very next successful
fetch re-enables fresh stamping. No behavior of the success path changes.

Determinism: no network (provider is a stub; conftest pins DATA_SOURCE=mock),
timestamps are injected directly onto the service instance.
"""

from __future__ import annotations

import asyncio
import time

from app.models.schemas import SymbolSnapshot
from app.services.market_service import MarketService


def _snapshot(l18: str = "فولاد") -> SymbolSnapshot:
    return SymbolSnapshot(l18=l18, l30="فولاد مبارکه", isin="IRO1", pl=100.0, py=100.0)


class RaisingProviderStub:
    """Provider stub whose fetch() always raises (no fallback inside)."""

    def __init__(self) -> None:
        self.settings = None
        self.last_source = "tsetmc"
        self.last_error = ""

    async def fetch(self):  # noqa: ANN201
        raise RuntimeError("synthetic total provider outage")


class GoodProviderStub:
    """Provider stub that returns a minimal board (fresh-fetch path)."""

    def __init__(self) -> None:
        self.settings = None
        self.last_source = "mock_fallback"
        self.last_error = ""

    async def fetch(self):  # noqa: ANN201
        return []


def _seed(service: MarketService, *, age_sec: float) -> None:
    """Seed the service with recycled symbols and an OLD fetch timestamp."""
    service._last_symbols = []
    service._last_fetch_ts = time.time() - age_sec
    service._source = "tsetmc"
    service._trust_level = "live"


def test_degraded_cycle_does_not_restamp_recycled_data_as_fresh() -> None:
    service = MarketService.__new__(MarketService)  # avoid real provider wiring
    service.provider = RaisingProviderStub()
    service.settings = None
    service._lock = asyncio.Lock()
    service._last_analysis = None
    service._last_symbols = []
    service._last_fetch_ts = 0.0
    service._last_big_moves = []
    service._last_tablocastic = []
    service._last_confluence = {}
    service._row_cache = []
    service._seen_alert_keys = set()
    service._trust_level = "mixed"
    service._source = "none"
    service._flow_meta = {}
    service._fetch_degraded = False
    service._fund_cache = {}
    service._fund_cache_max = 200
    service._last_prune_ts = 0.0
    service._prune_interval = 3600

    old_ts = time.time() - 10_000.0  # ~2.8h old — far beyond stale_after_sec
    service._last_fetch_ts = old_ts

    # A truthy recycled board so the fallback engages instead of re-raising.
    service._last_symbols = [_snapshot()]

    asyncio.run(service.refresh(force=True))
    assert service._fetch_degraded is False  # one-cycle flag consumed
    assert service._last_fetch_ts == old_ts  # NOT re-stamped


def test_degraded_cycle_reports_stale_in_trust_context() -> None:
    service = MarketService.__new__(MarketService)
    service.provider = RaisingProviderStub()
    service.settings = None
    service._lock = asyncio.Lock()
    service._last_analysis = None
    service._last_symbols = [_snapshot()]  # truthy recycled board
    service._last_fetch_ts = time.time() - 10_000.0
    service._last_big_moves = []
    service._last_tablocastic = []
    service._last_confluence = {}
    service._row_cache = []
    service._seen_alert_keys = set()
    service._trust_level = "mixed"
    service._source = "tsetmc"
    service._flow_meta = {}
    service._fetch_degraded = False
    service._fund_cache = {}
    service._fund_cache_max = 200
    service._last_prune_ts = 0.0
    service._prune_interval = 3600

    asyncio.run(service.refresh(force=True))
    ctx = service.data_trust_context()
    # The recycled data must now classify as stale — the failure is visible.
    assert ctx["stale"] is True
    assert ctx["state"] in {"stale", "unavailable"}
    assert ctx["age_sec"] >= 9_900.0


def test_successful_fetch_after_degraded_cycle_restores_fresh_stamping() -> None:
    service = MarketService.__new__(MarketService)
    service._lock = asyncio.Lock()
    service._last_analysis = None
    service._last_symbols = [_snapshot()]  # truthy board so degraded fallback engages
    service._last_fetch_ts = time.time() - 10_000.0
    service._last_big_moves = []
    service._last_tablocastic = []
    service._last_confluence = {}
    service._row_cache = []
    service._seen_alert_keys = set()
    service._trust_level = "mixed"
    service._source = "none"
    service._flow_meta = {}
    service._fetch_degraded = False
    service._fund_cache = {}
    service._fund_cache_max = 200
    service._last_prune_ts = 0.0
    service._prune_interval = 3600

    before = service._last_fetch_ts

    # First a degraded cycle (recycled data, old timestamp preserved).
    service.provider = RaisingProviderStub()
    asyncio.run(service.refresh(force=True))
    assert service._last_fetch_ts == before

    # Then a successful fetch — timestamp must advance again.
    service.provider = GoodProviderStub()
    asyncio.run(service.refresh(force=True))
    assert service._last_fetch_ts > before
    assert service._fetch_degraded is False
