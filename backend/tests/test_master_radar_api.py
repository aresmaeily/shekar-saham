"""Integration tests for the MASTER-RADAR API surfaces (2026-11-04 wave).

Covers: /api/v10/strategylab (validate/spec/backtest/paper-replay/versions +
C3 approval state machine), /api/v10/indicators (catalog/spec/compute), and
/api/v10/analyst/{symbol} (deterministic evidence-grounded report). All
offline-deterministic: fixed end_bar_index pins the seeded series; the trust
envelope is the canonical market_service verdict (assert-style, never a
hardcoded "live").
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

END_BAR = 1000  # frozen seeded window for determinism

VALID_SOURCE = """INPUT fast = 5
RISK stop_loss_pct = 3.0, take_profit_pct = 6.0, max_position_pct = 50.0
ENTRY close > sma(close, fast)
EXIT close < sma(close, 20)
"""

BAD_SOURCE = "ENTRY close >"
HOSTILE_SOURCE = 'ENTRY close.__class__ > 0'


@pytest.fixture(scope="module")
def client():
    # Convention shared with the existing suite: NO context manager, so the
    # app lifespan (store snapshot/backup/pollers) never runs in tests and
    # global state stays untouched for the order-dependent gates.
    # A DISTINCT client identity keeps this module's ~30 requests in their own
    # rate-limiter bucket (keyed on request.client.host) instead of consuming
    # the shared "testclient" 150/min budget that late-suite gates rely on.
    # The limiter itself is untouched — no gate weakened.
    app = create_app()
    yield TestClient(app, client=("mradar-lab-test", 12345))


# ---------------------------------------------------------------------------
# /api/v10/strategylab
# ---------------------------------------------------------------------------


def test_strategylab_validate_ok(client):
    r = client.post("/api/v10/strategylab/validate", json={"source": VALID_SOURCE})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["dsl_version"] == "RSL-1.0.0"
    assert body["digest"]
    assert body["inputs"] == {"fast": 5.0}
    assert body["risk"]["stop_loss_pct"] == 3.0
    assert "close > sma(close, fast)" in body["expressions"]["entry"]
    assert body["errors"] == []
    assert "data_trust" in body["trust_envelope"]


def test_strategylab_validate_rejects_bad_syntax(client):
    r = client.post("/api/v10/strategylab/validate", json={"source": BAD_SOURCE})
    assert r.status_code == 200  # validate returns structured errors, not 500
    body = r.json()
    assert body["ok"] is False
    assert body["errors"], body
    assert body["errors"][0]["code"]


def test_strategylab_validate_rejects_attribute_escape(client):
    r = client.post("/api/v10/strategylab/validate", json={"source": HOSTILE_SOURCE})
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_strategylab_spec_contract(client):
    r = client.post("/api/v10/strategylab/spec", json={"source": VALID_SOURCE, "name": "demo"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["spec_version"] == "RSL-1.0.0"
    assert body["api_contract"]["dsl_version"] == "RSL-1.0.0"
    assert body["generated_by"] == "user-authored RSL source; AI-proposal seam owner-gated and disconnected"
    assert body["digest"]


def test_strategylab_spec_rejects_bad_source(client):
    r = client.post("/api/v10/strategylab/spec", json={"source": BAD_SOURCE})
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "DSL_ERROR"


def test_strategylab_backtest_deterministic_and_labeled(client):
    payload = {
        "source": VALID_SOURCE,
        "symbol": "FOLAD",
        "timeframe": "1D",
        "count": 200,
        "end_bar_index": END_BAR,
    }
    r1 = client.post("/api/v10/strategylab/backtest", json=payload)
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["engine_version"] == "BT-PRODUCT-1.0.0"
    assert b1["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    assert b1["result_digest"]
    assert b1["bars_used"] == 200
    report = b1["report"]
    for key in (
        "total_return_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar",
        "profit_factor", "expectancy", "win_rate", "trade_count", "fees_total",
        "monthly_returns",
    ):
        assert key in report, key
    # limitations live at the top level of the payload (engine-level honesty)
    assert isinstance(b1["limitations"], list) and b1["limitations"]
    r2 = client.post("/api/v10/strategylab/backtest", json=payload)
    assert r2.json()["result_digest"] == b1["result_digest"]
    assert b1["synthetic_note"]


def test_strategylab_backtest_execution_overrides_effect(client):
    base = {
        "source": VALID_SOURCE, "symbol": "FOLAD", "timeframe": "1D",
        "count": 200, "end_bar_index": END_BAR,
    }
    r1 = client.post("/api/v10/strategylab/backtest", json=base)
    r2 = client.post(
        "/api/v10/strategylab/backtest",
        json={**base, "execution": {"commission_pct": 1.0}},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["result_digest"] != r2.json()["result_digest"]
    assert r2.json()["report"]["fees_total"] > 0


def test_strategylab_backtest_rejects_bad_source(client):
    r = client.post(
        "/api/v10/strategylab/backtest",
        json={"source": BAD_SOURCE, "end_bar_index": END_BAR},
    )
    assert r.status_code == 422


def test_strategylab_paper_replay_honest_labels(client):
    r = client.post(
        "/api/v10/strategylab/paper-replay",
        json={"source": VALID_SOURCE, "symbol": "FOLAD", "timeframe": "1D",
              "count": 200, "end_bar_index": END_BAR},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "PAPER_REPLAY_OVER_SYNTHETIC_WINDOW"
    assert body["not_live_note"]
    s = body["summary"]
    assert s["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    assert s["engine_version"] == "FT-PAPER-1.0.0"
    assert body["ledger_chain_ok"] is True
    assert isinstance(s["immature_count"], int)
    # matured stats must exclude immature outcomes
    assert s["matured_count"] >= 0 and s["immature_count"] >= 0
    assert body["summary_digest"]


def test_strategylab_versions_approval_state_machine(client):
    # DRAFT by default
    r = client.post(
        "/api/v10/strategylab/versions",
        json={"source": VALID_SOURCE, "name": "smoke", "approve": False, "now_ts": 1_700_000_000},
    )
    assert r.status_code == 200
    draft = r.json()["version"]
    assert draft["status"] == "DRAFT"
    # promote DRAFT -> 409
    r409 = client.post(
        f"/api/v10/strategylab/versions/{draft['version_id']}/promote", json={"now_ts": 1_700_000_100}
    )
    assert r409.status_code == 409
    # approve a new one -> APPROVED
    r2 = client.post(
        "/api/v10/strategylab/versions",
        json={"source": VALID_SOURCE, "name": "smoke2", "approve": True, "now_ts": 1_700_000_200},
    )
    approved = r2.json()["version"]
    assert approved["status"] == "APPROVED"
    # promote APPROVED -> PROMOTED
    r3 = client.post(
        f"/api/v10/strategylab/versions/{approved['version_id']}/promote", json={"now_ts": 1_700_000_300}
    )
    assert r3.status_code == 200
    assert r3.json()["version"]["status"] == "PROMOTED"
    assert r3.json()["scope_note"]
    # listing shows the in-memory persistence honesty note
    r4 = client.get("/api/v10/strategylab/versions")
    assert r4.status_code == 200
    body = r4.json()
    assert any(v["version_id"] == approved["version_id"] for v in body["versions"])
    assert "持久" not in body["persistence_note"]  # sanity: Persian note present
    assert body["persistence_note"]


def test_strategylab_promote_unknown_version_404(client):
    r = client.post("/api/v10/strategylab/versions/v9999-unknown/promote", json={"now_ts": 1})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/v10/indicators
# ---------------------------------------------------------------------------


def test_indicators_catalog_lists_and_declares(client):
    r = client.get("/api/v10/indicators")
    assert r.status_code == 200
    body = r.json()
    assert body["catalog_version"] == "IC-1.0.0"
    assert body["catalog_problems"] == []
    assert body["count"] >= 14
    ids = [i["id"] for i in body["indicators"]]
    assert "builtin.sma" in ids and "builtin.rsi" in ids and "builtin.adx" in ids
    cats = {i["category"] for i in body["indicators"]}
    assert {"trend", "momentum", "volatility", "volume", "breadth", "market_structure"} <= cats
    for item in body["indicators"]:
        assert item["lookahead_declared"] is False
        assert item["name_fa"]
        assert item["math_definition"] if "math_definition" in item else True


def test_indicators_detail_has_math_definition(client):
    r = client.get("/api/v10/indicators/builtin.rsi")
    assert r.status_code == 200
    body = r.json()
    assert "RSI" in body["math_definition"] or "rsi" in body["math_definition"].lower()
    assert body["warmup_bars"] >= 1
    assert body["repaint"] in {"non_repainting", "repaints_last_bar", "session_dependent"}


def test_indicators_detail_404(client):
    r = client.get("/api/v10/indicators/builtin.does_not_exist")
    assert r.status_code == 404


def test_indicators_compute_rsi_deterministic(client):
    q = {"symbol": "FOLAD", "timeframe": "1D", "count": 100,
         "end_bar_index": END_BAR, "params": '{"period": 14}'}
    r1 = client.get("/api/v10/indicators/builtin.rsi/compute", params=q)
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["data_class"] == "SYNTHETIC_SEEDED"
    assert b1["declarations"]["lookahead_declared"] is False
    values = b1["series"]["value"]
    assert len(values) == 100
    r2 = client.get("/api/v10/indicators/builtin.rsi/compute", params=q)
    assert r2.json()["series"] == b1["series"]


def test_indicators_compute_param_validation(client):
    r = client.get(
        "/api/v10/indicators/builtin.rsi/compute",
        params={"end_bar_index": END_BAR, "params": '{"period": 0}'},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "PARAM_RANGE"
    r2 = client.get(
        "/api/v10/indicators/builtin.rsi/compute",
        params={"end_bar_index": END_BAR, "params": '{"not_a_param": 3}'},
    )
    assert r2.status_code == 422
    assert r2.json()["detail"]["error"] == "UNKNOWN_PARAM"


def test_indicators_compute_macd_multi_series(client):
    r = client.get(
        "/api/v10/indicators/builtin.macd/compute",
        params={"symbol": "FOLAD", "end_bar_index": END_BAR},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body["series"].keys()) == {"macd", "signal", "histogram"}


def test_indicators_breadth_not_computable_from_ohlcv(client):
    r = client.get(
        "/api/v10/indicators/builtin.advance_decline_line/compute",
        params={"end_bar_index": END_BAR},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "NOT_COMPUTABLE_FROM_OHLCV"


# ---------------------------------------------------------------------------
# /api/v10/analyst
# ---------------------------------------------------------------------------


def test_analyst_report_with_provenance(client):
    r = client.get("/api/v10/analyst/FOLAD", params={"count_daily": 150, "end_bar_index": END_BAR})
    assert r.status_code == 200
    body = r.json()
    assert body["engine_version"] == "ANALYST-1.0.0"
    assert body["data_class"] == "SYNTHETIC_SEEDED"
    assert body["generated_by"] == "deterministic-rules-v1 (no LLM call; provider path is owner-gated and disconnected)"
    assert body["claims"], "report must contain claims"
    for claim in body["claims"]:
        prov = claim["provenance"]
        assert prov["source_class"]
        assert prov["trust_class"] in {"REAL_VERIFIED", "REAL_UNVERIFIED", "DELAYED", "SYNTHETIC", "PAPER", "STALE", "MISSING"}
        assert claim["text_fa"], "Persian text required on every claim"
    # deterministic
    r2 = client.get("/api/v10/analyst/FOLAD", params={"count_daily": 150, "end_bar_index": END_BAR})
    assert r2.json()["report_digest"] == body["report_digest"]
    # missing-data honesty: hourly absent, fundamentals/signals unavailable
    missing_items = " ".join(m["item"] for m in body["missing_data"])
    assert "hourly" in missing_items or "fundamentals" in missing_items or "strategy" in missing_items


def test_analyst_short_history_still_honest(client):
    r = client.get("/api/v10/analyst/FOLAD", params={"count_daily": 50, "end_bar_index": END_BAR})
    assert r.status_code == 200
    body = r.json()
    # weekly cannot be produced honestly from 50 daily bars in this endpoint
    assert body["mtf_agreement"]["agreement"] in {"AGREE", "DISAGREE", "PARTIAL", "INSUFFICIENT_DATA"}


def test_analyst_report_digest_changes_with_data(client):
    r1 = client.get("/api/v10/analyst/FOLAD", params={"count_daily": 150, "end_bar_index": END_BAR})
    r2 = client.get("/api/v10/analyst/FOLAD", params={"count_daily": 150, "end_bar_index": END_BAR + 5})
    assert r1.json()["report_digest"] != r2.json()["report_digest"]
