"""Integration tests for the MASTER-RADAR WAVE-2 API surfaces (2026-11-04).

Covers (all additive to the 2026-11-04 wave, mirroring
test_master_radar_api.py conventions):
- /api/v10/strategylab/optimize — deterministic parameter search (grid happy
  path, OOS confirmation block, seed REQUIRED, 500-eval server budget guard,
  method whitelist, deterministic reproducibility digest);
- /api/v10/strategylab/backtest/export — downloadable full report (json) and
  its documented flat csv projection (## METRICS / ## TRADES, byte-identical
  for identical inputs);
- /api/v10/dataquality/* — fixture-universe market coverage summary, full
  coverage rows, per-symbol mechanical audit, honest 422/404 surfaces;
- /api/v10/chartpro series labeling echo (WAVE-2 additive field);
- regime segmentation field presence on the existing /backtest response.

All offline-deterministic: fixed end_bar_index pins the seeded series; the
trust envelope is the canonical market_service verdict (assert-style, never a
hardcoded "live" label).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

END_BAR = 1000  # frozen seeded window for determinism

VALID_SOURCE = """INPUT fast = 5
RISK stop_loss_pct = 3.0, take_profit_pct = 6.0, max_position_pct = 50.0
ENTRY close > sma(close, fast)
EXIT close < sma(close, 20)
"""

OPTIMIZE_BASE = {
    "source": VALID_SOURCE,
    "symbol": "FOLAD",
    "timeframe": "1D",
    "count": 200,
    "end_bar_index": END_BAR,
    "method": "grid",
    "space": {"grid": {"fast": [3, 5, 8]}},
    "budget": {"max_evals": 3, "seed": 42},
    "oos": {"enabled": False},
}

BACKTEST_BASE = {
    "source": VALID_SOURCE,
    "symbol": "FOLAD",
    "timeframe": "1D",
    "count": 200,
    "end_bar_index": END_BAR,
}


@pytest.fixture(scope="module")
def client():
    # Same convention as test_master_radar_api.py: NO context manager (the app
    # lifespan never runs in tests) and a DISTINCT client identity so this
    # module's requests stay in their own rate-limiter bucket.
    app = create_app()
    yield TestClient(app, client=("mr-wave2-test", 12346))


# ---------------------------------------------------------------------------
# /api/v10/strategylab/optimize
# ---------------------------------------------------------------------------


def test_optimize_grid_happy_path(client):
    r = client.post("/api/v10/strategylab/optimize", json=OPTIMIZE_BASE)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["method"] == "grid"
    assert body["selection_basis"] == "IN_SAMPLE"
    # deterministic grid over fast=[3,5,8]: winner must be the best IS sharpe
    assert body["winner"] is not None
    assert body["winner"]["params"] == {"fast": 8.0}
    assert body["winner"]["is_refused"] is False
    assert body["total_evaluations"] == 3
    assert body["evaluations_returned"] == 3
    assert len(body["evaluations"]) <= 50
    assert body["evaluable_count"] == 3
    assert body["refused_count"] == 0
    assert "n_trials=3" in body["bonferroni_note"]
    assert body["budget_echo"]["seed"] == 42
    assert body["budget_echo"]["max_evals"] == 3
    assert body["budget_echo"]["limit"] == 500
    assert body["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    assert body["synthetic_note"]
    assert "data_trust" in body["trust_envelope"]
    assert body["partial_notes"] == []
    assert body["oos"]["enabled"] is False


def test_optimize_oos_confirmation_block(client):
    body = {**OPTIMIZE_BASE, "oos": {"enabled": True, "holdout_fraction": 0.3}}
    r = client.post("/api/v10/strategylab/optimize", json=body)
    assert r.status_code == 200
    payload = r.json()
    assert payload["selection_basis"] == "IN_SAMPLE"
    oos = payload["oos"]
    assert oos["enabled"] is True
    assert oos["selection_basis"] == "IN_SAMPLE"
    assert oos["is_bars"] == 140 and oos["oos_bars"] == 60
    assert oos["oos_evaluated_once"] is True
    assert oos["oos_objective_value"] is not None
    assert "in-sample" in oos["note"]
    # The confirmation never overrides the IS winner (AUDIT-MR2 O1 fix: the
    # previous form was vacuous — the oos block has no params key; the real
    # guarantee is pinned structurally: the winner's objective value IS the
    # in-sample value the confirmation reports, and OOS ran exactly once
    # AFTER selection with its own separate value).
    assert payload["winner"]["objective_value"] == oos["is_objective_value"]
    assert oos["oos_evaluated_once"] is True
    assert oos["is_objective_value"] != oos["oos_objective_value"] or oos["oos_bars"] == oos["is_bars"]


def test_optimize_randomized_bounds_path(client):
    body = {
        **OPTIMIZE_BASE,
        "method": "randomized",
        "space": {"bounds": {"fast": [2.0, 12.0]}},
        "budget": {"max_evals": 4, "seed": 7},
    }
    r = client.post("/api/v10/strategylab/optimize", json=body)
    assert r.status_code == 200
    payload = r.json()
    assert payload["method"] == "randomized"
    assert payload["total_evaluations"] == 4
    for row in payload["evaluations"]:
        assert 2.0 <= row["params"]["fast"] <= 12.0


def test_optimize_missing_seed_422(client):
    body = {**OPTIMIZE_BASE, "budget": {"max_evals": 3}}  # seed REQUIRED
    r = client.post("/api/v10/strategylab/optimize", json=body)
    assert r.status_code == 422


def test_optimize_over_budget_422_with_honest_note(client):
    body = {**OPTIMIZE_BASE, "budget": {"max_evals": 501, "seed": 1}}
    r = client.post("/api/v10/strategylab/optimize", json=body)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "BUDGET_LIMIT"
    assert "بودجه بهینه‌سازی محدود است" in detail["message_fa"]
    assert "max_evals must be <= 500" in detail["message_en"]


def test_optimize_bad_method_422(client):
    body = {**OPTIMIZE_BASE, "method": "genetic"}
    r = client.post("/api/v10/strategylab/optimize", json=body)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "INVALID_METHOD"
    assert detail["valid_methods"] == ["grid", "randomized", "evolutionary"]


def test_optimize_unknown_param_422(client):
    body = {**OPTIMIZE_BASE, "space": {"grid": {"not_declared": [1, 2]}}}
    r = client.post("/api/v10/strategylab/optimize", json=body)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "UNKNOWN_OPTIMIZATION_PARAM"
    assert "fast" in detail["declared_inputs"]


def test_optimize_deterministic_reproducibility_digest(client):
    r1 = client.post("/api/v10/strategylab/optimize", json=OPTIMIZE_BASE)
    r2 = client.post("/api/v10/strategylab/optimize", json=OPTIMIZE_BASE)
    assert r1.status_code == 200 and r2.status_code == 200
    b1, b2 = r1.json(), r2.json()
    assert b1["reproducibility_digest"]
    assert b1["reproducibility_digest"] == b2["reproducibility_digest"]
    assert b1["evaluations"] == b2["evaluations"]


# ---------------------------------------------------------------------------
# /api/v10/strategylab/backtest/export
# ---------------------------------------------------------------------------


def test_export_json_full_report_attachment(client):
    body = {**BACKTEST_BASE, "format": "json"}
    r1 = client.post("/api/v10/strategylab/backtest/export", json=body)
    assert r1.status_code == 200
    assert r1.headers["content-type"] == "application/json"
    disposition = r1.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    payload = json.loads(r1.content)
    digest8 = payload["result_digest"][:8]
    assert f'filename="backtest-report-{digest8}.json"' in disposition
    # the FULL report: metrics + trades + honesty envelope
    assert "sharpe" in payload["report"]
    assert "max_drawdown_pct" in payload["report"]
    assert isinstance(payload["trades"], list)
    assert len(payload["trades"]) == payload["trades_count"]
    assert payload["trust_envelope"]["data_trust"]["is_live"] is False
    assert payload["synthetic_note"]
    # deterministic: identical inputs -> identical report bytes and digest
    # (the canonical trust envelope's checked_at is the trust-check wall-clock
    # instant by design, so byte-identity is asserted on everything except it)
    r2 = client.post("/api/v10/strategylab/backtest/export", json=body)
    p2 = json.loads(r2.content)
    assert p2["result_digest"] == payload["result_digest"]
    p1_wo = {k: v for k, v in payload.items() if k != "trust_envelope"}
    p2_wo = {k: v for k, v in p2.items() if k != "trust_envelope"}
    assert p1_wo == p2_wo


def test_export_csv_two_sections_deterministic(client):
    body = {**BACKTEST_BASE, "format": "csv"}
    r1 = client.post("/api/v10/strategylab/backtest/export", json=body)
    assert r1.status_code == 200
    assert r1.headers["content-type"].startswith("text/csv")
    text = r1.content.decode("utf-8")
    assert text.startswith("## METRICS")
    assert "## TRADES" in text
    # metrics section is line-pairs with English keys
    assert "run_id,strategylab" in text
    assert "sharpe," in text
    assert "data_trust_label,SYNTHETIC_OR_PAPER" in text
    # trades section: header row + one row per closed trade
    trades_section = text.split("## TRADES", 1)[1].strip().splitlines()
    header, rows = trades_section[0], [ln for ln in trades_section[1:] if ln.strip()]
    assert header.startswith("symbol,side,")
    trades_count = int(dict(
        line.split(",", 1) for line in text.split("## METRICS", 1)[1]
        .split("## TRADES", 1)[0].strip().splitlines() if "," in line
    )["trades_count"])
    assert len(rows) == trades_count
    # deterministic: byte-identical for identical inputs, same digest8 filename
    r2 = client.post("/api/v10/strategylab/backtest/export", json=body)
    assert r2.content == r1.content
    digest8 = r1.headers["content-disposition"].split("backtest-report-")[1][:8]
    rj = client.post("/api/v10/strategylab/backtest/export", json={**BACKTEST_BASE, "format": "json"})
    assert f'filename="backtest-report-{digest8}.csv"' in r1.headers["content-disposition"]
    assert rj.json()["result_digest"][:8] == digest8  # same run -> same digest8


def test_export_rejects_unknown_format(client):
    r = client.post(
        "/api/v10/strategylab/backtest/export",
        json={**BACKTEST_BASE, "format": "xlsx"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/v10/dataquality
# ---------------------------------------------------------------------------


def test_dataquality_markets_summary(client):
    r = client.get("/api/v10/dataquality/markets")
    assert r.status_code == 200
    body = r.json()
    assert body["markets"], "market list must be non-empty"
    for market in body["markets"]:
        assert market["symbol_count"] > 0
        assert market["audited_count"] == market["symbol_count"]
        assert market["trust_class"] == "SYNTHETIC"
        for key in ("duplicate_bars", "out_of_order_bars", "invalid_bars", "stale_bars", "missing_intervals"):
            assert key in market["worst_issues"]
        assert market["coverage_report"]["market"] == market["market"]
    by_market = {m["market"]: m for m in body["markets"]}
    assert by_market["IRAN_TSE"]["in_default_universe"] is True
    assert by_market["EXCLUDED_US_EQUITY"]["in_default_universe"] is False
    assert body["trust_envelope"]["data_trust"]["is_live"] is False
    assert body["synthetic_note"]
    assert body["provenance"]["canonical"] == "NON_LIVE_FIXTURE"


def test_dataquality_unknown_market_422_lists_valid(client):
    r = client.get("/api/v10/dataquality/markets/NOT_A_MARKET/coverage")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "UNKNOWN_MARKET"
    assert "IRAN_TSE" in detail["valid_markets"]
    assert "FOREX" in detail["valid_markets"]


def test_dataquality_market_coverage_rows_have_trust_fields(client):
    r = client.get("/api/v10/dataquality/markets/IRAN_TSE/coverage")
    assert r.status_code == 200
    body = r.json()
    assert body["market"] == "IRAN_TSE"
    assert body["report"]["market"] == "IRAN_TSE"
    assert body["symbols"], "coverage rows must be non-empty"
    for row in body["symbols"]:
        assert row["trust_class"] == "SYNTHETIC"
        for key in (
            "duplicate_bars", "duplicate_examples", "out_of_order_bars",
            "invalid_bars", "invalid_examples", "missing_intervals",
            "stale_bars", "stale_reference_ts", "corporate_action_coverage",
            "pit_availability", "max_staleness_seconds", "expected_interval_seconds",
        ):
            assert key in row, key
        # honesty mapping: fixtures declare no CA/PIT claims -> UNKNOWN
        assert row["corporate_action_coverage"] == "UNKNOWN"
        assert row["pit_availability"] == "UNKNOWN"
        # injected as_of pattern (never a wall clock)
        assert row["stale_reference_ts"] == body["as_of_ts"]
    assert body["trust_envelope"]["data_trust"]["is_live"] is False


def test_dataquality_symbol_audit_flags(client):
    r = client.get("/api/v10/dataquality/symbols/IR_TSE:FOLAD/audit")
    assert r.status_code == 200
    body = r.json()
    assert body["instrument_id"] == "IR_TSE:FOLAD"
    assert body["trust_class"] == "SYNTHETIC"
    assert body["audit"]["bar_count"] == 200
    for key in ("duplicates", "out_of_order", "invalid_ohlcv", "missing_intervals", "stale_bars"):
        assert key in body["flags"], key
    assert body["flags"]["duplicates"] == body["audit"]["duplicate_bars"]
    # deterministic staleness against the INJECTED fixture as_of (2026-01-01Z)
    assert body["as_of_ts"] == 1767225600
    assert body["flags"]["stale_bars"] == 200
    assert "SYNTHETIC_FIXTURE" in body["provenance"]["note_en"]
    assert body["trust_envelope"]["data_trust"]["is_live"] is False


def test_dataquality_unknown_symbol_404(client):
    r = client.get("/api/v10/dataquality/symbols/NOPE:DOESNOTEXIST/audit")
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "UNKNOWN_INSTRUMENT"


def test_dataquality_nonlive_envelope_on_every_endpoint(client):
    paths = [
        "/api/v10/dataquality/markets",
        "/api/v10/dataquality/markets/FOREX/coverage",
        "/api/v10/dataquality/symbols/FX:EURUSD/audit",
    ]
    for path in paths:
        r = client.get(path)
        assert r.status_code == 200, path
        body = r.json()
        assert body["trust_envelope"]["data_trust"]["is_live"] is False, path
        assert body["trust_envelope"]["data_trust"]["live_verified"] is False, path
        assert body["provenance"]["canonical"] == "NON_LIVE_FIXTURE", path
        assert body["synthetic_note"], path


# ---------------------------------------------------------------------------
# /api/v10/chartpro labeling echo (WAVE-2 additive field)
# ---------------------------------------------------------------------------


def test_chartpro_candles_labeling_echo(client):
    r = client.get("/api/v10/chartpro/FOLAD", params={"timeframe": "1D", "limit": 60})
    assert r.status_code == 200
    body = r.json()
    # pre-existing contract untouched
    assert body["symbol"] == "FOLAD"
    assert body["timeframe"] == "1D"
    assert len(body["ohlcv"]) == 60
    assert "last_price" in body and "note" in body
    # additive labeling echo
    labeling = body["labeling"]
    assert labeling["bar_class"] == "SYNTHETIC"
    assert labeling["method"] == "NATIVE"
    assert "synthetic" in labeling["note_en"]
    assert labeling["note_fa"]
    # chart_pro spreads the trust envelope at the top level (pre-existing shape)
    assert body["data_trust"]["is_live"] is False
    assert body["trust_level"] in {"synthetic", "mixed", "live"}


def test_chartpro_indicators_labeling_echo(client):
    r = client.get("/api/v10/chartpro/FOLAD/indicators", params={"timeframe": "1D", "limit": 60})
    assert r.status_code == 200
    body = r.json()
    assert "indicators" in body  # pre-existing contract untouched
    labeling = body["labeling"]
    assert labeling["bar_class"] == "SYNTHETIC"
    assert labeling["method"] == "NATIVE"
    assert "identical" in labeling["note_en"]  # deterministic seeded statement


# ---------------------------------------------------------------------------
# Regime surfacing on the existing /backtest response
# ---------------------------------------------------------------------------


def test_backtest_regime_segments_field_present(client):
    r = client.post("/api/v10/strategylab/backtest", json=BACKTEST_BASE)
    assert r.status_code == 200
    body = r.json()
    # The regime segmentation block is ALREADY surfaced by the existing
    # /backtest response as report.regime_segments (computed every run; empty
    # unless the caller passes regime_labels — the seeded lab passes none).
    # Verified present; left as-is per the additive-only mandate.
    assert "regime_segments" in body["report"]
    assert isinstance(body["report"]["regime_segments"], list)


# ---------------------------------------------------------------------------
# WAVE-2 integration (main-agent): on-demand strategy-alert evaluation (§B5)
# — manual/request-scoped only; no scheduler behind the endpoint (R-6);
# result stays in the response — no notification egress (R-9).
# ---------------------------------------------------------------------------


def test_alerts_evaluate_triggered_shape_and_determinism(client):
    body = {**BACKTEST_BASE}
    r1 = client.post("/api/v10/strategylab/alerts/evaluate", json=body)
    assert r1.status_code == 200
    p1 = r1.json()
    assert p1["ok"] is True
    assert p1["evaluation_mode"] == "ON_DEMAND"
    assert "زمان‌بند" in p1["scheduler_note"]  # honesty: no scheduler (R-6)
    assert "R-9" in p1["no_egress_note"]  # honesty: no egress
    assert p1["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    result = p1["result"]
    assert isinstance(result["triggered"], bool)
    assert result["errors"] == []
    assert result["bars_evaluated"] == body["count"]
    assert result["program_digest"]
    assert "bar_ts" in result and "last_value" in result
    r2 = client.post("/api/v10/strategylab/alerts/evaluate", json=body)
    assert r2.status_code == 200
    assert r2.json()["result"] == result  # deterministic: identical inputs → identical verdict


def test_alerts_evaluate_staleness_refusal_with_injected_clock(client):
    # The seeded series uses COMPRESSED SYNTHETIC timestamps (bar N = N days
    # in its own unit) — a real wall clock would be a unit mismatch, so the
    # reference clock is supplied IN THE SERIES' OWN UNIT: last-ts + 4 days
    # exceeds the documented 3-bar-median freshness window → honest stale
    # refusal; last-ts + 1 day is fresh → normal verdict. Never a guess.
    from app.services import strategy_lab_service as svc

    bars = svc.load_seeded_bars("FOLAD", "1D", 200, end_bar_index=END_BAR)
    day = int(bars[1]["ts"] - bars[0]["ts"])
    stale_body = {**BACKTEST_BASE, "staleness_as_of": int(bars[-1]["ts"]) + 4 * day}
    r = client.post("/api/v10/strategylab/alerts/evaluate", json=stale_body)
    assert r.status_code == 200
    result = r.json()["result"]
    assert result.get("stale") is True
    assert result["triggered"] is False
    assert result["bars_evaluated"] == 0
    assert result["program_digest"] is None
    fresh_body = {**BACKTEST_BASE, "staleness_as_of": int(bars[-1]["ts"]) + 1 * day}
    r2 = client.post("/api/v10/strategylab/alerts/evaluate", json=fresh_body)
    assert r2.status_code == 200
    fresh = r2.json()["result"]
    assert fresh.get("stale") is not True
    assert fresh["bars_evaluated"] == 200


def test_alerts_evaluate_dsl_error_is_safe_422(client):
    bad_source = "ENTRY close >"  # local malformed source (same shape as the wave-1 BAD_SOURCE)
    r = client.post("/api/v10/strategylab/alerts/evaluate", json={**BACKTEST_BASE, "source": bad_source})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "DSL_ERROR"


def test_alerts_evaluate_explicit_reference_clock_is_echoed(client):
    body = {**BACKTEST_BASE, "staleness_as_of": 1700000000}
    r = client.post("/api/v10/strategylab/alerts/evaluate", json=body)
    assert r.status_code == 200
    assert r.json()["staleness_as_of"] == 1700000000
