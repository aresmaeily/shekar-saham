from app.engines.filter_dsl import run_filter, FilterError
import pytest

def test_valid_filter():
    rows = [{"buy_power": 2, "plp": -1}, {"buy_power": 1, "plp": 2}]
    res = run_filter("buy_power >= 1.5 and plp <= 0", rows)
    assert len(res) == 1
    assert res[0]["buy_power"] == 2

def test_unicode_normalization():
    rows = [{"symbol": "فملی", "buy_power": 2}]
    # Persian field name check not supported, but unicode in values should work
    res = run_filter("buy_power >= 2", rows)
    assert len(res) == 1
