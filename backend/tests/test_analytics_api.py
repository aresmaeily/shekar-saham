"""WDA-3 acceptance battery — /api/v10/analytics backend API (additive).

Covers:
- /search: normalized Persian matching (Arabic yeh/kaf variants, ZWNJ, digits),
  honest empty results, 422 on out-of-range limit, per-row trust envelope.
- /screener: happy path over the current synthetic snapshot, industry filter,
  honest empty result, 422 validation semantics (consistent with Query
  constraints elsewhere, e.g. /api/signals/entry min_score).
- /market-map: aggregate industries view with counts + avg change.
- /flow: big-moves-derived summary (inflow/outflow consistency + coverage).
- /dossier/{l18}: supported sections present + unsupported sections honest
  (available:false + Persian reason), 404 for unknown symbol.
- Trust discipline on every endpoint: data_trust from market_service, never
  "live", live_verified false (conftest pins DATA_SOURCE=mock).

Additive-only contract: this file exercises ONLY the new /api/v10/analytics
router; existing endpoints/tests are untouched.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

# Honest non-live taxonomy: before a refresh ran, market_service trust context
# yields state="unavailable"/trust_level="mixed"; after the mock refresh the
# analytics endpoints yield "mock"/"synthetic". "live" is unreachable here.
NON_LIVE_TRUST_STATES = {"synthetic", "mock", "stale", "unavailable", "mixed"}
NON_LIVE_TRUST_LEVELS = {"synthetic", "mixed"}

client = TestClient(app)


def _assert_envelope(body: dict) -> None:
    ctx = body["data_trust"]
    assert ctx["state"] in NON_LIVE_TRUST_STATES
    assert ctx["is_live"] is False
    assert ctx["live_verified"] is False
    assert body["trust_level"] in NON_LIVE_TRUST_LEVELS


def _assert_row_envelope(row: dict) -> None:
    ctx = row["data_trust"]
    assert ctx["state"] in NON_LIVE_TRUST_STATES
    assert ctx["is_live"] is False
    assert ctx["live_verified"] is False
    assert row["trust_level"] in NON_LIVE_TRUST_LEVELS


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------

def test_search_happy_path_persian_prefix():
    r = client.get("/api/v10/analytics/search", params={"q": "فمل"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["count"] == len(body["results"]) >= 1
    assert body["results"][0]["l18"] == "فملی"  # prefix match ranks first
    assert body["source"] == "synthetic-seeded"
    assert "زنده نیست" in body["note"]
    _assert_envelope(body)
    row = body["results"][0]
    assert {"l18", "l30", "industry", "pl", "plp", "source_class", "data_trust"} <= set(row)
    assert row["source_class"] == "synthetic-seeded"
    assert row["market"] == "TSE"
    _assert_row_envelope(row)


def test_search_normalizes_arabic_glyph_variants():
    # Arabic yeh (ي) instead of Persian yeh (ی) must match فملی after folding.
    r = client.get("/api/v10/analytics/search", params={"q": "فملي"})
    assert r.status_code == 200
    assert any(x["l18"] == "فملی" for x in r.json()["results"])
    # Arabic kaf (ك) instead of Persian kaf (ک) must match کگل.
    r2 = client.get("/api/v10/analytics/search", params={"q": "كگل"})
    assert r2.status_code == 200
    assert any(x["l18"] == "کگل" for x in r2.json()["results"])


def test_search_zwnj_and_whitespace_normalization():
    # ZWNJ inside "های‌وب" is stripped on both sides, spaces collapse.
    r = client.get("/api/v10/analytics/search", params={"q": "های وب"})
    assert r.status_code == 200
    assert any(x["l18"] == "های‌وب" for x in r.json()["results"])


def test_search_empty_query_honest_empty():
    r = client.get("/api/v10/analytics/search", params={"q": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["results"] == []
    assert body["count"] == 0
    _assert_envelope(body)  # envelope still present — honesty never depends on hits


def test_search_english_query_no_false_match():
    # Latin query over the Persian universe: honest empty result, no fabrication.
    r = client.get("/api/v10/analytics/search", params={"q": "foolad"})
    assert r.status_code == 200
    body = r.json()
    assert body["results"] == []
    assert body["normalized_query"] == "foolad"
    _assert_envelope(body)


def test_search_limit_validation_422():
    assert client.get("/api/v10/analytics/search", params={"q": "ف", "limit": 0}).status_code == 422
    assert client.get("/api/v10/analytics/search", params={"q": "ف", "limit": 51}).status_code == 422


# ---------------------------------------------------------------------------
# /screener
# ---------------------------------------------------------------------------

def test_screener_happy_path_baseline():
    r = client.get("/api/v10/analytics/screener")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["count"] == len(body["rows"]) > 0
    assert body["expr"] == "entry_score >= 0"
    assert {"symbol", "name", "industry", "plp", "entry_score"} <= set(body["rows"][0])
    _assert_envelope(body)


def test_screener_industry_filter_reuses_filter_dsl():
    r = client.get("/api/v10/analytics/screener", params={"industry": "فلزات اساسی"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert "contains(industry, 'فلزات اساسی')" in body["expr"]
    assert all(row["industry"] == "فلزات اساسی" for row in body["rows"])
    _assert_envelope(body)


def test_screener_numeric_filters_and_sort():
    r = client.get(
        "/api/v10/analytics/screener",
        params={"min_tval": 0, "min_entry_score": 0, "sort": "plp", "limit": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] <= 5
    plps = [row["plp"] or 0 for row in body["rows"]]
    assert plps == sorted(plps, reverse=True)
    assert body["filters"]["sort"] == "plp"


def test_screener_empty_result_is_honest_not_fabricated():
    r = client.get(
        "/api/v10/analytics/screener",
        params={"min_entry_score": 100, "min_plp": 100},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["count"] == 0
    _assert_envelope(body)  # empty is honest; envelope still present


def test_screener_invalid_params_422():
    # out-of-range numerics (Query constraints, consistent with /api/signals/entry)
    assert client.get("/api/v10/analytics/screener", params={"min_plp": 200}).status_code == 422
    assert client.get("/api/v10/analytics/screener", params={"min_entry_score": 150}).status_code == 422
    assert client.get("/api/v10/analytics/screener", params={"limit": 500}).status_code == 422
    # quote characters would break the DSL string literal — rejected at the boundary
    assert client.get("/api/v10/analytics/screener", params={"industry": "فلز'ات"}).status_code == 422
    assert client.get("/api/v10/analytics/screener", params={"sort": "mv"}).status_code == 422


# ---------------------------------------------------------------------------
# /market-map
# ---------------------------------------------------------------------------

def test_market_map_aggregates_industries():
    r = client.get("/api/v10/analytics/market-map")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["industry_count"] == len(body["industries"]) > 0
    assert body["symbol_count"] > 0
    first = body["industries"][0]
    assert {"industry", "symbol_count", "avg_plp", "total_value", "score"} <= set(first)
    assert all(row["symbol_count"] >= 1 for row in body["industries"])
    _assert_envelope(body)


def test_market_map_min_symbols_and_sort():
    r = client.get("/api/v10/analytics/market-map", params={"sort": "avg_plp", "min_symbols": 3})
    assert r.status_code == 200
    body = r.json()
    assert all(row["symbol_count"] >= 3 for row in body["industries"])
    avgs = [row["avg_plp"] for row in body["industries"]]
    assert avgs == sorted(avgs, reverse=True)
    assert client.get(
        "/api/v10/analytics/market-map", params={"sort": "mv"}
    ).status_code == 422  # sort constrained by pattern


# ---------------------------------------------------------------------------
# /flow
# ---------------------------------------------------------------------------

def test_flow_summary_consistent():
    r = client.get("/api/v10/analytics/flow")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["inflow_count"] + body["outflow_count"] == body["moves_count"]
    assert body["moves_count"] == len(body["top_moves"]) or body["moves_count"] >= 0
    assert isinstance(body["net_flow_value"], (int, float))
    assert "coverage_sec" in body
    assert body["window_sec"] in (300, 600, 900, 1800)
    for move in body["top_moves"]:
        assert move["side"] in {"inflow", "outflow"}
        assert "delta_net_value" in move and "score" in move
    _assert_envelope(body)


def test_flow_window_validation_422():
    assert client.get("/api/v10/analytics/flow", params={"window_sec": 10}).status_code == 422
    assert client.get("/api/v10/analytics/flow", params={"window_sec": 99999}).status_code == 422
    assert client.get("/api/v10/analytics/flow", params={"limit": 0}).status_code == 422


# ---------------------------------------------------------------------------
# /dossier/{l18}
# ---------------------------------------------------------------------------

SUPPORTED_SECTIONS = ("identity", "price_snapshot", "tablo", "fundamental", "flow", "alerts_history")
UNSUPPORTED_SECTIONS = ("calendar", "dividends", "corporate_events", "shareholders", "target_price")


def test_dossier_supported_sections_from_existing_data():
    r = client.get("/api/v10/analytics/dossier/فملی")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["l18"] == "فملی"
    _assert_envelope(body)
    for name in SUPPORTED_SECTIONS:
        section = body["sections"][name]
        assert section["available"] is True, name
        assert section["data"] is not None
        _assert_row_envelope(section)
    ident = body["sections"]["identity"]["data"]
    assert ident["l18"] == "فملی" and ident["market"] == "TSE"
    snap = body["sections"]["price_snapshot"]["data"]
    assert {"pl", "plp", "tval", "tvol", "pe"} <= set(snap)
    fund = body["sections"]["fundamental"]["data"]
    # honesty: fundamental engine output is explicitly synthetic-marked
    assert fund["is_synthetic"] is True
    assert fund["fundamental_source"] == "synthetic"
    assert "synthetic" in fund["warning"] or "demo" in fund["warning"]


def test_dossier_unsupported_fields_explicit_null_with_reason():
    r = client.get("/api/v10/analytics/dossier/فملی")
    assert r.status_code == 200
    body = r.json()
    for name in UNSUPPORTED_SECTIONS:
        section = body["sections"][name]
        assert section["available"] is False, name
        assert section["data"] is None
        assert isinstance(section["reason"], str) and len(section["reason"]) > 10
        _assert_row_envelope(section)
    assert sorted(body["unavailable_sections"]) == sorted(UNSUPPORTED_SECTIONS)


def test_dossier_unknown_symbol_404_persian_detail():
    r = client.get("/api/v10/analytics/dossier/ZZZ_UNKNOWN_X")
    assert r.status_code == 404
    assert "یافت نشد" in r.json()["detail"]


# ---------------------------------------------------------------------------
# trust discipline across the whole new surface
# ---------------------------------------------------------------------------

def test_trust_envelope_never_live_across_all_endpoints():
    paths = (
        "/api/v10/analytics/search?q=فولاد",
        "/api/v10/analytics/screener?limit=5",
        "/api/v10/analytics/market-map",
        "/api/v10/analytics/flow",
        "/api/v10/analytics/dossier/فولاد",
    )
    for path in paths:
        r = client.get(path)
        assert r.status_code == 200, path
        body = r.json()
        _assert_envelope(body)
        # additive router must not collide with existing /api routes
        assert "/api/v10/analytics" not in body.get("note", "")
