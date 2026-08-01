"""
test_forex.py - v1.0 Forex + Gold + Brokers + COMEX/TVC/Capital.com
"""
import pytest

from app.data.forex_provider import (
    FOREX_SYMBOLS,
    BROKERS,
    get_forex_symbols_list,
    get_broker_list,
    resolve_broker,
)


def test_gold_has_three_brokers():
    info = FOREX_SYMBOLS["XAUUSD"]
    assert set(info["brokers"]) == {"blackbull", "pepperstone", "fxcm"}
    assert info["default_broker"] == "blackbull"
    assert info["type"] == "commodity"


def test_gc1_comex():
    info = FOREX_SYMBOLS["GC1"]
    assert info["brokers"] == ["comex"]
    assert info["venue"] == "COMEX"
    assert info["yahoo"] == "GC=F"


def test_dxy_tvc():
    info = FOREX_SYMBOLS["DXY"]
    assert info["brokers"] == ["tvc"]
    assert info["venue"].startswith("TVC")
    assert info["yahoo"] == "DX-Y.NYB"


def test_capital_com_indices_and_oil():
    for sym, yahoo in [("US500", "^GSPC"), ("US100", "^NDX"), ("US30", "^DJI"), ("UKOIL", "BZ=F")]:
        info = FOREX_SYMBOLS[sym]
        assert info["brokers"] == ["capital.com"]
        assert info["yahoo"] == yahoo


def test_resolve_broker_validation():
    assert resolve_broker("XAUUSD", "blackbull") == "blackbull"
    assert resolve_broker("XAUUSD", "pepperstone") == "pepperstone"
    assert resolve_broker("XAUUSD", "fxcm") == "fxcm"
    # unknown broker -> fallback to default
    assert resolve_broker("XAUUSD", "saxo") == "blackbull"
    assert resolve_broker("GC1", "blackbull") == "comex"
    # symbols without broker concept
    assert resolve_broker("EURUSD", "blackbull") is None
    assert resolve_broker("UNKNOWN", None) is None


def test_broker_list_complete():
    ids = {b["id"] for b in get_broker_list()}
    assert ids == {"blackbull", "pepperstone", "fxcm", "comex", "tvc", "capital.com"}
    assert BROKERS["capital.com"]["symbols"] == ["US500", "US100", "US30", "UKOIL"]


def test_symbols_list_contains_all_new_symbols():
    symbols = {s["symbol"] for s in get_forex_symbols_list()}
    assert {"XAUUSD", "GC1", "DXY", "US500", "US100", "US30", "UKOIL"} <= symbols


@pytest.mark.asyncio
async def test_fetch_unknown_symbol_returns_empty():
    from app.data.forex_provider import fetch_forex_ohlcv
    assert await fetch_forex_ohlcv("ZZZ_NOT_A_REAL_SYMBOL", "1m", limit=10) == []
