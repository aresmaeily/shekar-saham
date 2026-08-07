import pytest

from app.engines.filter_dsl import (
    FilterError,
    compile_filter,
    expression_tree,
    functions_help,
    parse_filter,
    run_filter,
    validate_filter,
)


def test_valid_filter():
    rows = [{"buy_power": 2, "plp": -1}, {"buy_power": 1, "plp": 2}]
    res = run_filter("buy_power >= 1.5 and plp <= 0", rows)
    assert len(res) == 1
    assert res[0]["buy_power"] == 2


def test_unicode_normalization():
    rows = [{"symbol": "فملی", "buy_power": 2}]
    res = run_filter("buy_power >= ۲", rows)
    assert len(res) == 1


def test_contains_sugar_and_persian_text():
    rows = [{"symbol": "فملی", "industry": "فلزات اساسی"}, {"symbol": "خودرو", "industry": "خودرو"}]
    res = run_filter("industry contains فلز", rows)
    assert [r["symbol"] for r in res] == ["فملی"]


def test_boolean_operator_aliases():
    rows = [{"buy_power": 2, "volume_ratio": 3}, {"buy_power": 2, "volume_ratio": 1}]
    res = run_filter("buy_power >= 1.5 AND volume_ratio > 2", rows)
    assert len(res) == 1


def test_arithmetic_expression():
    rows = [{"tval": 100, "tvol": 10}, {"tval": 20, "tvol": 10}]
    res = run_filter("tval / tvol >= 5", rows)
    assert len(res) == 1


def test_indicator_references_from_row_context():
    rows = [
        {"symbol": "فملی", "pl": 120, "sma_20": 100, "rsi_14": 28, "volume_ratio": 2.5},
        {"symbol": "فولاد", "pl": 90, "sma_20": 100, "rsi_14": 45, "volume_ratio": 3.0},
    ]
    res = run_filter("close > sma(20) and rsi(14) < 30 and volume_ratio > 2", rows)
    assert [r["symbol"] for r in res] == ["فملی"]


def test_market_data_reference_aliases():
    rows = [{"pl": 1000, "tvol": 2_000_000, "avg_volume_20": 1_000_000}]
    assert run_filter("price == close and volume > avg_volume(20)", rows)


def test_invalid_unknown_field():
    with pytest.raises(FilterError):
        run_filter("unknown_field > 1", [{"buy_power": 2}])


def test_invalid_function_rejected():
    with pytest.raises(FilterError):
        run_filter("open('/etc/passwd')", [{}])


def test_security_import_injection_rejected():
    with pytest.raises(FilterError):
        run_filter("__import__('os').system('echo bad')", [{}])


def test_security_attribute_access_rejected():
    with pytest.raises(FilterError):
        run_filter("symbol.__class__ == 'x'", [{"symbol": "فملی"}])


def test_security_subscript_rejected():
    with pytest.raises(FilterError):
        run_filter("tags[0] == 'x'", [{"tags": ["x"]}])


def test_compile_filter_backward_compatible_ast():
    tree = compile_filter("buy_power > 1")
    assert tree.body is not None


def test_parse_filter_metadata():
    parsed = parse_filter("close > sma(20) and rsi(14) < 30")
    assert parsed.normalized == "close > sma(20) and rsi(14) < 30"
    assert parsed.fields == ("close",)
    assert parsed.functions == ("rsi", "sma")


def test_validate_filter_contract():
    res = validate_filter("volume_ratio > 2")
    assert res["ok"] is True
    assert res["fields"] == ["volume_ratio"]


def test_expression_tree_contract():
    tree = expression_tree("buy_power > 1 and volume_ratio > 2")
    assert tree.kind == "bool"
    assert tree.value == "and"


def test_functions_help_lists_indicator_references():
    keys = {x["key"] for x in functions_help()}
    assert {"sma", "rsi", "avg_volume", "contains"}.issubset(keys)
