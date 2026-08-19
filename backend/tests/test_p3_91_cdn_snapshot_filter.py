"""P3.91: Filter DSL can consume CDN-mapped TSETMC snapshots.

Does not mint LIVE. Does not call TSETMC. Does not change filter/provider code.
"""

from app.core.config import build_data_trust_context, is_verified_live
from app.data.providers import MarketDataProvider, tsetmc_mw_to_snapshot
from app.engines.filter_dsl import run_filter


def _cdn(ticker: str, last: float, close: float, yesterday: float, volume: float) -> dict:
    return {
        "lva": ticker,
        "lvc": ticker + "-NAME",
        "py": yesterday,
        "pf": yesterday,
        "pc": close,
        "pClosing": close,
        "pDrCotVal": last,
        "qTotTran5J": volume,
        "qTotCap": volume * last,
        "zTotTran": 3,
        "insCode": "1",
        "hEven": 123000,
    }


def test_cdn_snapshots_are_filterable_without_verified_live():
    payload = {
        "marketwatch": [
            _cdn("AAA", last=120, close=110, yesterday=100, volume=5000),
            _cdn("BBB", last=80, close=90, yesterday=100, volume=1000),
        ]
    }
    provider = MarketDataProvider.__new__(MarketDataProvider)
    snaps = MarketDataProvider._parse_tsetmc_json(provider, payload)
    assert len(snaps) == 2
    assert all(s.source == "tsetmc" for s in snaps)

    rows = [
        {
            "symbol": s.l18,
            "pl": s.pl,
            "pc": s.pc,
            "py": s.py,
            "tvol": s.tvol,
            "tval": s.tval,
        }
        for s in snaps
    ]
    matched = run_filter("pl > pc and tvol >= 2000", rows)
    assert [r["symbol"] for r in matched] == ["AAA"]

    trust = build_data_trust_context("tsetmc", timestamp=1000, checked_at=1010)
    assert trust["live_verified"] is False
    assert trust["is_live"] is False
    assert is_verified_live(trust) is False


def test_single_cdn_snapshot_maps_before_filter():
    snap = tsetmc_mw_to_snapshot(_cdn("CCC", last=10, close=10, yesterday=9, volume=1))
    assert snap is not None
    assert snap.l18 == "CCC"
    assert run_filter("symbol == 'CCC'", [{"symbol": snap.l18, "pl": snap.pl}])
