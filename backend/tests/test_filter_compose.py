"""D-O2 filter-compose acceptance tests (approved continuation spec §12).

Independent, deterministic, offline. Every test pins recovered documentation
semantics — not reconstructed lost code. Raw expectations come from the
versioned fixture ``tests/fixtures/compose/composition_dryrun_fixture.json``
whose recovered board (6/2/1/0, ranti [AAA, BBB], market mean 130M) was
verified verbatim from TABLOKHANI_WORKSTREAM_PACKAGE_2026-11-14.
"""

from __future__ import annotations

import copy
import json
import pathlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.engines.filter_compose import (
    COMPOSE_FILTERS,
    ComposeValidationError,
    UNSUPPORTED_DISCLOSURE,
    compose_filters,
    compose_presets,
    market_buy_per_capita,
)
from app.engines.filter_dsl import validate_filter
from app.engines.golden_set_comparison import (
    ComparisonPreconditions,
    compare_symbol_sets,
    empty_metrics,
)

FIXTURE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "compose" / "composition_dryrun_fixture.json").read_text()
)


def board_rows() -> list[dict]:
    return copy.deepcopy(FIXTURE["rows"])


# --- §12.1 filter-set integrity ------------------------------------------------

def test_filter_set_integrity_provenance_and_rationale():
    assert len(COMPOSE_FILTERS) == 8
    ids = [f["filter_id"] for f in COMPOSE_FILTERS]
    assert len(set(ids)) == 8
    for f in COMPOSE_FILTERS:
        # every preset validates under the EXISTING safe DSL, unchanged
        v = validate_filter(f["expr"])
        assert v["ok"] is True
        assert f["provenance"] in (
            "DOCUMENTED_PUBLIC_SEMANTICS",
            "RADAR_NATIVE",
            "INDEPENDENT_PROPOSAL",
            "CUSTOM_OPERATOR_INPUT",
        )
        assert f["rationale"].strip()
        assert f["name_fa"].strip() and f["name_en"].strip()


def test_catalog_definition_order_matches_recovered_fixture():
    """matched[] order = catalog definition order; the recovered fixture pins it."""
    rows = board_rows()
    result = compose_filters(rows, min_matches=1)
    by_symbol = {r["symbol"]: [m["filter_id"] for m in r["matched"]] for r in result["results"]}
    for expected in FIXTURE["board"]:
        if expected["match_count"] > 0:
            assert by_symbol[expected["symbol"]] == expected["matched"]


# --- §12.2 hand-derived match counts (no tolerance) -----------------------------

def test_hand_derived_match_counts_fixture_board():
    result = compose_filters(board_rows(), min_matches=1)
    got = {r["symbol"]: r["match_count"] for r in result["results"]}
    want = {b["symbol"]: b["match_count"] for b in FIXTURE["board"]}
    # results[] carries only symbols with >=1 match: CCC (0) is honestly absent
    assert got == {s: c for s, c in want.items() if c > 0}
    assert "CCC" not in got
    assert result["symbols_matched"] == 3
    assert result["market_context"]["market_buy_per_capita"] == pytest.approx(
        FIXTURE["market_buy_per_capita"]
    )
    assert result["symbols_evaluated"] == 4
    assert result["total_matched"] == 9  # 6+2+1 hand-derived total
    assert result["ranking_rule"].startswith("match_count desc")


# --- §12.3 ranking + tie-break triple -------------------------------------------

def _tie_row(symbol: str, golden: float, entry: float, count: int) -> dict:
    return {
        "symbol": symbol,
        "buy_per_capita": 250000000,
        "volume_ratio": 3.5,
        "plp": -1.5,
        "individual_net_value": 500000000,
        "in_buy_queue": 1,
        "Buy_I_Volume": 9000000,
        "Buy_N_Volume": 1000000,
        "Sell_N_Volume": 8000000,
        "Sell_I_Volume": 2000000,
        "golden_number": golden,
        "entry_score": entry,
    }


def test_ranking_tie_break_triple():
    rows = [
        _tie_row("ZZZ", 70.0, 80.0, 6),
        _tie_row("MMM", 90.0, 10.0, 6),
        _tie_row("AAA", 90.0, 50.0, 6),
        _tie_row("BBB", 90.0, 50.0, 6),
    ]
    result = compose_filters(rows, min_matches=1)
    order = [r["symbol"] for r in result["results"]]
    # match_count equal → golden desc (90-group first) → entry desc within group
    # (AAA 50, BBB 50 tie → symbol asc) → MMM (entry 10) → ZZZ (golden 70 last)
    assert order == ["AAA", "BBB", "MMM", "ZZZ"]


def test_ranking_symbol_asc_final_tiebreak():
    rows = [_tie_row("B2", 90.0, 50.0, 6), _tie_row("A9", 90.0, 50.0, 6)]
    result = compose_filters(rows, min_matches=1)
    assert [r["symbol"] for r in result["results"]] == ["A9", "B2"]


# --- §12.4 رانتی rule -----------------------------------------------------------

def test_ranti_min_matches_two_shortlist():
    result = compose_filters(board_rows(), min_matches=FIXTURE["ranti_min_matches"])
    assert [r["symbol"] for r in result["results"]] == FIXTURE["ranti_expected"]
    assert result["symbols_matched"] == 2


# --- §12.5 band boundaries -------------------------------------------------------

@pytest.mark.parametrize("case", FIXTURE["hot_money_band_boundaries"]["cases"])
def test_hot_money_band_boundaries(case):
    rows = [_tie_row("TST", 50.0, 50.0, 1)]
    rows[0]["buy_per_capita"] = case["buy_per_capita"]
    # remove queue/red-board flags so only the per-capita bands fire
    rows[0]["plp"] = 1.0
    rows[0]["in_buy_queue"] = 0
    rows[0]["volume_ratio"] = 1.0
    result = compose_filters(rows, min_matches=1)
    got = {m["filter_id"] for m in result["results"][0]["matched"]} if result["results"] else set()
    assert (("hot_money" in got) == case["hot_money"]), case
    assert (("hot_money_plus" in got) == case["hot_money_plus"]), case


# --- §12.6 invalid custom expression recorded, not silent ------------------------

def test_invalid_expr_recorded_not_silent():
    # full catalog + one invalid custom expression: the invalid unit is
    # RECORDED (never silent), contributes zero matches, and the board continues.
    catalog_ids = [f["filter_id"] for f in COMPOSE_FILTERS]
    result = compose_filters(board_rows(), filter_ids=catalog_ids, exprs=["plp >"])
    assert result["ok"] is True
    customs = [f for f in result["filters"] if f["is_custom"]]
    assert len(customs) == 1 and customs[0]["error"]
    assert customs[0]["matched_count"] == 0
    # the board continues: preset results unaffected
    got = {r["symbol"]: r["match_count"] for r in result["results"]}
    assert got == {"AAA": 6, "BBB": 2, "DDD": 1}


def test_custom_only_board_is_the_requested_set():
    """exprs-only request composes EXACTLY the requested units (honest semantics)."""
    result = compose_filters(board_rows(), exprs=["plp >"])  # invalid on purpose
    assert [f["filter_id"] for f in result["filters"]] == ["custom_1"]
    assert result["results"] == []  # the only unit errored — honest empty board
    assert result["symbols_evaluated"] == 4


def test_custom_expr_evaluates_deterministically():
    result = compose_filters(board_rows(), exprs=["volume_ratio >= 3"])
    customs = [f for f in result["filters"] if f["is_custom"]]
    assert customs[0]["error"] is None
    assert customs[0]["matched_count"] == 1  # AAA only


# --- §12.7 empty board / blank symbols / degenerate context ----------------------

def test_empty_board_honest():
    result = compose_filters([], min_matches=1)
    assert result["ok"] is True
    assert result["symbols_evaluated"] == 0
    assert result["results"] == []
    assert result["market_context"]["market_buy_per_capita"] == 0.0
    assert result["market_context"]["degenerate"] is True
    assert result["market_context"]["degenerate_note"]


def test_blank_symbols_never_ranked_or_counted():
    rows = board_rows() + [
        {"symbol": "", "buy_per_capita": 900000000, "volume_ratio": 99, "plp": -9, "individual_net_value": 1, "in_buy_queue": 1, "golden_number": 100.0, "entry_score": 100.0},
        {"symbol": "   ", "buy_per_capita": 900000000, "volume_ratio": 99, "plp": -9, "individual_net_value": 1, "in_buy_queue": 1, "golden_number": 100.0, "entry_score": 100.0},
    ]
    result = compose_filters(rows, min_matches=1)
    assert result["symbols_evaluated"] == 4  # blanks skipped entirely
    # blank rows contributed zero matches to every filter
    by_id = {f["filter_id"]: f["matched_count"] for f in result["filters"]}
    assert by_id["hot_money"] == 1  # AAA only; blanks never counted
    assert "AAA" in {r["symbol"] for r in result["results"]}


def test_degenerate_market_context_matches_everything_with_disclosure():
    rows = [
        {"symbol": "X1", "buy_per_capita": 0, "volume_ratio": 0.1, "plp": 5.0, "individual_net_value": 0, "golden_number": 1.0, "entry_score": 1.0},
        {"symbol": "X2", "buy_per_capita": 0, "volume_ratio": 0.1, "plp": 5.0, "individual_net_value": 0, "golden_number": 2.0, "entry_score": 2.0},
    ]
    result = compose_filters(rows, min_matches=1)
    assert result["market_context"]["degenerate"] is True
    assert result["market_context"]["degenerate_note"]
    # 1.5 * 0 = 0 ⇒ per_capita_vs_market matches every row (documented degenerate mode)
    by_id = {f["filter_id"]: f["matched_count"] for f in result["filters"]}
    assert by_id["per_capita_vs_market"] == 2


# --- §12.8 missing data fail-closed ----------------------------------------------

def test_missing_field_never_yields_negative_match():
    # ZZZ lacks volume_ratio entirely: sus_volume must record a row-evaluation
    # error (fail-closed), never coerce the missing datum to 0/false silently.
    rows = [{"symbol": "ZZZ", "buy_per_capita": 0, "plp": 5.0, "individual_net_value": 0, "golden_number": 1.0, "entry_score": 1.0}]
    result = compose_filters(rows, min_matches=1)
    sus = next(f for f in result["filters"] if f["filter_id"] == "sus_volume")
    assert sus["matched_count"] == 0
    assert sus["error"] and "fail-closed" in sus["error"]
    # missing queue/legal fields are equally fail-closed, never fabricated matches
    by_id = {f["filter_id"]: f for f in result["filters"]}
    assert by_id["buy_queue"]["matched_count"] == 0
    assert by_id["legal_sell_retail_buy"]["matched_count"] == 0
    # the ONLY match comes from the documented degenerate per-capita mode
    # (single-row universe mean = 0 ⇒ 1.5×0 = 0 ⇒ 0 >= 0) — disclosed, not hidden
    assert result["market_context"]["degenerate"] is True
    assert [m["filter_id"] for m in result["results"][0]["matched"]] == ["per_capita_vs_market"]


def test_none_valued_field_fail_closed():
    rows = [_tie_row("NNN", 50.0, 50.0, 1)]
    rows[0]["volume_ratio"] = None
    result = compose_filters(rows, min_matches=1)
    sus = next(f for f in result["filters"] if f["filter_id"] == "sus_volume")
    assert sus["matched_count"] == 0
    assert sus["error"]


# --- §12.9 double_run_identical ---------------------------------------------------

def test_double_run_identical_library_level():
    a = compose_filters(board_rows(), min_matches=2)
    b = compose_filters(board_rows(), min_matches=2)
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def test_market_mean_includes_zero_rows():
    rows = [{"symbol": "A", "buy_per_capita": 100.0}, {"symbol": "B", "buy_per_capita": 0}]
    assert market_buy_per_capita(rows) == pytest.approx(50.0)
    assert market_buy_per_capita([]) == 0.0


def test_rows_not_mutated():
    rows = board_rows()
    snapshot = copy.deepcopy(rows)
    compose_filters(rows, min_matches=1)
    assert rows == snapshot


# --- §12.10 API contract ----------------------------------------------------------

def test_unknown_filter_id_api_400():
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/filter/compose", json={"filter_ids": ["nope"]})
    assert r.status_code == 400
    assert "nope" in r.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {"filter_ids": [f"f{i}" for i in range(33)]},
        {"exprs": ["plp > 0"] * 17},
        {"min_matches": 0},
        {"min_matches": 9},
        {"limit": 0},
        {"limit": 201},
    ],
)
def test_limits_api_400(body):
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/filter/compose", json=body)
    assert r.status_code == 400


def test_compose_api_shape_and_double_run():
    from app.main import app
    from app.services import market_service as ms_module

    rows = board_rows()
    ms = ms_module.market_service
    c = TestClient(app)
    with patch.object(ms, "get_filter_rows", return_value=rows):
        r1 = c.post("/api/filter/compose", json={"min_matches": 2})
        assert r1.status_code == 200
        payload = r1.json()
        assert payload["ok"] is True
        assert [x["symbol"] for x in payload["results"]] == FIXTURE["ranti_expected"]
        assert payload["data_trust"]["is_live"] is False
        assert payload["data_trust"]["live_verified"] is False
        assert payload["unsupported"]["composition_level_and_or"].startswith("NOT_SUPPORTED")
        r2 = c.post("/api/filter/compose", json={"min_matches": 2})
        p2 = r2.json()
        # double_run_identical (spec §12.9) covers the deterministic board;
        # the trust envelope is a documented passthrough whose checked_at is
        # the wall-clock of the trust check itself (existing pinned behavior).
        assert {k: v for k, v in p2.items() if k != "data_trust"} == {
            k: v for k, v in payload.items() if k != "data_trust"
        }


def test_compose_presets_api_shape():
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/filter/compose/presets")
    assert r.status_code == 200
    payload = r.json()
    assert [f["filter_id"] for f in payload["filters"]] == [f["filter_id"] for f in COMPOSE_FILTERS]
    assert any(rt["key"] == "market_buy_per_capita" for rt in payload["runtime_fields"])
    assert payload["unsupported"]["historical_array_dialect"].startswith("NOT_SUPPORTED")


def test_presets_helper_defensive_copy():
    presets = compose_presets()
    presets[0]["expr"] = "tampered"
    assert COMPOSE_FILTERS[0]["expr"] != "tampered"


# --- §12.12 comparison metrics (overlap-only protocol) ----------------------------

FULL = ComparisonPreconditions(True, True, True, True, True)


def test_dry_run_metrics_on_recovered_fixture():
    out = compare_symbol_sets(
        FIXTURE["dry_run_example"]["reference"],
        FIXTURE["dry_run_example"]["candidate"],
        preconditions=FULL,
    )
    assert out["status"] == "MEASURED"
    m = out["metrics"]
    assert m["true_positives"] == 2 and m["false_positives"] == 1 and m["false_negatives"] == 0
    assert m["precision"] == pytest.approx(0.6666666666666666)
    assert m["recall"] == pytest.approx(1.0)
    assert m["coverage"] == pytest.approx(1.0)
    assert m["f1"] == pytest.approx(0.8)
    assert m["jaccard"] == pytest.approx(2 / 3)
    assert out["interpretation"] == "OVERLAP_ONLY_NO_SUPERIORITY_CLAIM"


def test_empty_metrics_on_precondition_failure():
    out = compare_symbol_sets(["AAA"], ["AAA"], preconditions=ComparisonPreconditions(True, False, True, True, True))
    assert out == empty_metrics(out["reason"]) or out["status"] == "NOT_MEASURED"
    assert out["metrics"] is None


def test_no_superiority_guard_larger_candidate_never_superior():
    # recovered protocol §4 guard: candidate ⊇ reference ⇒ recall 1.0 with
    # precision 1/3 — a LARGER output is never read as superiority.
    out = compare_symbol_sets(["AAA"], ["AAA", "BBB", "DDD"], preconditions=FULL)
    assert out["metrics"]["recall"] == 1.0
    assert out["metrics"]["precision"] == pytest.approx(1 / 3)
    assert out["interpretation"] == "OVERLAP_ONLY_NO_SUPERIORITY_CLAIM"


def test_unsupported_disclosure_present():
    assert UNSUPPORTED_DISCLOSURE["composition_level_and_or"].startswith("NOT_SUPPORTED")
    assert UNSUPPORTED_DISCLOSURE["historical_array_dialect"].startswith("NOT_SUPPORTED")


def test_compose_validation_error_range():
    with pytest.raises(ComposeValidationError):
        compose_filters(board_rows(), min_matches=0)
    with pytest.raises(ComposeValidationError):
        compose_filters(board_rows(), limit=500)
    with pytest.raises(ComposeValidationError):
        compose_filters(board_rows(), exprs=["plp > 0"] * 17)
