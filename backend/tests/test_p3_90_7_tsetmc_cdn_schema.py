"""P3.90.7: CDN GetMarketWatch schema (no l18) must map to SymbolSnapshot.

Owner Windows P3.90.6: marketwatch=1507, parser output=0 because mapper
required lval18AFC/l18/symbol. Real items use lva/lvc + closing-price keys.
"""

from app.data.providers import MarketDataProvider, tsetmc_mw_to_snapshot


def _cdn_item(*, ticker: str, name: str, last: float, close: float, yesterday: float) -> dict:
    return {
        "lva": ticker,
        "lvc": name,
        "eps": 12.5,
        "pe": 8.0,
        "pmd": 90,
        "pmo": 110,
        "qtj": 0,
        "pdv": 0,
        "ztt": 10,
        "qtc": 1000,
        "bv": 5000,
        "pc": close,
        "pcpc": 1.0,
        "pmn": 95,
        "pmx": 105,
        "py": yesterday,
        "pf": 99,
        "pcl": close,
        "vc": 0,
        "csv": "",
        "insID": "INS1",
        "pMax": 105,
        "pMin": 95,
        "ztd": 0,
        "blDs": None,
        "id": 0,
        "insCode": "35425587644337450",
        "dEven": 20260816,
        "hEven": 123000,
        "pClosing": close,
        "iClose": False,
        "yClose": False,
        "pDrCotVal": last,
        "zTotTran": 10,
        "qTotTran5J": 2000,
        "qTotCap": 3000,
    }


def test_cdn_schema_without_l18_is_accepted():
    item = _cdn_item(ticker="SYM1", name="NAME1", last=101, close=100, yesterday=98)
    assert "l18" not in item
    snap = tsetmc_mw_to_snapshot(item)
    assert snap is not None
    assert snap.l18 == "SYM1"
    assert snap.l30 == "NAME1"
    assert snap.id == "35425587644337450"
    assert snap.pl == 101
    assert snap.pc == 100
    assert snap.py == 98
    assert snap.tvol == 2000
    assert snap.tval == 3000
    assert snap.tno == 10
    assert snap.bvol == 5000
    assert snap.pmin == 95
    assert snap.pmax == 105
    assert snap.source == "tsetmc"


def test_legacy_l18_schema_still_works():
    snap = tsetmc_mw_to_snapshot({"l18": "OLD1", "pl": 50, "pc": 49, "py": 48, "tvol": 7})
    assert snap is not None
    assert snap.l18 == "OLD1"
    assert snap.pl == 50


def test_missing_ticker_still_rejected():
    assert tsetmc_mw_to_snapshot({"pDrCotVal": 10, "pClosing": 9, "insCode": "1"}) is None


def test_parse_tsetmc_json_accepts_cdn_marketwatch():
    payload = {
        "marketwatch": [
            _cdn_item(ticker="AAA", name="A", last=10, close=9, yesterday=8),
            _cdn_item(ticker="BBB", name="B", last=20, close=19, yesterday=18),
        ]
    }
    provider = MarketDataProvider.__new__(MarketDataProvider)
    rows = MarketDataProvider._parse_tsetmc_json(provider, payload)
    assert len(payload["marketwatch"]) == 2
    assert len(rows) == 2
    assert {r.l18 for r in rows} == {"AAA", "BBB"}
    assert all(r.source == "tsetmc" for r in rows)


def test_yclose_boolean_is_not_used_as_yesterday_price():
    item = _cdn_item(ticker="SYM2", name="N", last=11, close=10, yesterday=9)
    item["yClose"] = True
    snap = tsetmc_mw_to_snapshot(item)
    assert snap is not None
    assert snap.py == 9
