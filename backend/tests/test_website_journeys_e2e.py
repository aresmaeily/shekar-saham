"""test_website_journeys_e2e.py — MASTER DIRECTIVE §3.1 (2026-11-07) — WAVE-T1.

Twelve end-to-end user journeys driven over the REAL FastAPI application
(`app.main.app` — the same composition the packaged site serves) with real
HTTP semantics (status codes, headers, JSON envelopes). This file closes the
SITE-2 matrix row's backend-verifiable surface: every journey is the actual
endpoint chain the frontend module would call, in the order a user reaches it.

Honest scope (recorded deliberately):
- In-process TestClient over the real app — no network, no live provider
  (conftest pins DATA_SOURCE=mock; BRSAPI_KEY=""). Every journey asserts the
  HONEST trust surface (synthetic labels, live_verified is not True) — the
  journeys verify UX states, never a live claim.
- Journeys J11/J12 (workspace persistence, popup detach, command palette,
  deep links) are frontend-dominated by design: localStorage persistence and
  window.open popups have no backend surface. Their backend-verifiable subset
  is the SPA shell + module assets actually served (content + honesty
  markers + the WAVE-S2 sync channel tokens). DOM-level behavior evidence is
  the separate browser runtime pass (WAVE-T2), recorded in the wave record.
- Distinct rate-limit identity ("journeys-e2e", 12877) per the recorded
  suite convention (test_scheduler_api.py precedent).
- Nothing here weakens, skips, or bypasses any gate: AI-2 stays disabled
  (committed default), the scheduler stays off, alert dispatch stays
  owner-gated — each journey asserts the HONEST gate state a real user sees.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

IDENTITY = ("journeys-e2e", 12877)

VALID_SOURCE = """INPUT fast = 5
RISK stop_loss_pct = 3.0, take_profit_pct = 6.0, max_position_pct = 50.0
ENTRY close > sma(close, fast)
EXIT close < sma(close, 20)
"""

BT_BODY = {
    "source": VALID_SOURCE,
    "symbol": "FOLAD",
    "timeframe": "1D",
    "count": 200,
    "end_bar_index": 1000,
}

WF_BODY = {
    "source": VALID_SOURCE,
    "symbol": "FOLAD",
    "timeframe": "1D",
    "count": 300,
    "folds": {"n": 3, "train_bars": 60, "test_bars": 30},
    "space": {"grid": {"fast": [3, 5, 8]}},
    "budget": {"max_evals_per_fold": 9, "seed": 11},
    "objective": "SHARPE",
}

OPTIMIZE_BODY = {
    "source": VALID_SOURCE,
    "symbol": "FOLAD",
    "timeframe": "1D",
    "count": 200,
    "end_bar_index": 1000,
    "method": "grid",
    "space": {"grid": {"fast": [3, 5, 8]}},
    "budget": {"max_evals": 3, "seed": 42},
    "oos": {"enabled": False},
}

UIDL_BAND = (
    "INDICATOR api_band\n"
    "INPUT len = 20\n"
    "PLOT basis = sma(close, len)\n"
    "PLOT upper = sma(close, len) * 1.02\n"
    "PLOT lower = sma(close, len) * 0.98\n"
)

SYNTHETIC_LABEL = "SYNTHETIC / PAPER — NOT LIVE"


def _client() -> TestClient:
    return TestClient(app, client=IDENTITY)


def _not_live(trust: dict) -> None:
    """Shared honest-trust assertion for any data_trust envelope."""
    assert trust.get("is_live") is not True
    assert trust.get("live_verified") is not True


# ---------------------------------------------------------------------------
# J01 — Market overview & map
# ---------------------------------------------------------------------------
def test_j01_market_overview_and_map():
    with _client() as c:
        h = c.get("/api/health")
        assert h.status_code == 200
        _not_live(h.json()["data_trust"])

        ov = c.get("/api/overview")
        assert ov.status_code == 200
        body = ov.json()
        assert body["symbol_count"] >= 1
        assert "top_industries" in body

        mm = c.get("/api/v10/analytics/market-map")
        assert mm.status_code == 200
        mmap = mm.json()
        assert mmap["ok"] is True
        assert mmap["industry_count"] >= 1
        assert isinstance(mmap["industries"], list) and mmap["industries"]
        _not_live(mmap["data_trust"])

        sc = c.get("/api/v10/analytics/screener")
        assert sc.status_code == 200


# ---------------------------------------------------------------------------
# J02 — Symbol search → watchlist → symbol detail
# ---------------------------------------------------------------------------
def test_j02_symbol_search_watchlist_detail():
    with _client() as c:
        s = c.get("/api/v10/analytics/search", params={"q": "فملی"})
        assert s.status_code == 200
        sj = s.json()
        assert sj["ok"] is True
        assert sj["count"] >= 1
        assert sj["results"][0]["l18"] == "فملی"
        assert sj["data_trust"]["is_live"] is not True

        w = c.get("/api/watchlist")
        assert w.status_code == 200
        wl = w.json()
        assert isinstance(wl, list) and wl
        assert all("symbol" in item for item in wl)

        d = c.get("/api/symbol/فملی")
        assert d.status_code == 200
        snap = d.json()["snapshot"]
        assert snap["l18"] == "فملی"
        assert snap["isin"]


# ---------------------------------------------------------------------------
# J03 — Chart Pro: universe → candles → indicators → derived series
# ---------------------------------------------------------------------------
def test_j03_chart_pro_universe_candles_derived():
    with _client() as c:
        u = c.get("/api/v10/chartpro/universe")
        assert u.status_code == 200
        uni = u.json()
        assert uni["count"] >= 1
        assert uni["trust_level"] == "synthetic"

        cs = c.get("/api/v10/chartpro/FOLAD")
        assert cs.status_code == 200
        candles = cs.json()
        assert candles["symbol"] == "FOLAD"
        assert isinstance(candles["ohlcv"], list) and candles["ohlcv"]
        assert candles["trust_level"] == "synthetic"
        _not_live(candles["data_trust"])

        ind = c.get("/api/v10/chartpro/FOLAD/indicators")
        assert ind.status_code == 200

        dv = c.post("/api/v10/chartpro/FOLAD/derived", json={"type": "RENKO", "limit": 60})
        assert dv.status_code == 200
        dj = dv.json()
        assert dj["type"] == "RENKO"
        assert dj["derived_count"] >= 1
        assert dj["trust_level"] == "synthetic"
        # honest labeling surface present (derived series never passes as raw)
        assert dj["labeling"]


# ---------------------------------------------------------------------------
# J04 — Strategy Lab + user-indicator manager (UIDL-1 lifecycle)
# ---------------------------------------------------------------------------
def test_j04_strategy_lab_and_user_indicators():
    with _client() as c:
        v = c.post("/api/v10/strategylab/validate", json={"source": VALID_SOURCE})
        assert v.status_code == 200
        assert v.json()["ok"] is True

        sp = c.post("/api/v10/strategylab/spec", json={"source": VALID_SOURCE, "name": "journeys"})
        assert sp.status_code == 200
        assert sp.json()["spec_version"] == "RSL-1.0.0"

        uv = c.post("/api/v10/user-indicators/validate", json={"source": UIDL_BAND})
        assert uv.status_code == 200
        uvj = uv.json()
        assert uvj["ok"] is True
        assert uvj["dsl_version"] == "UIDL-1"
        assert uvj["declarations"]["lookahead_declared"] is False

        before = c.get("/api/v10/user-indicators").json()["count"]
        created = c.post("/api/v10/user-indicators", json={"source": UIDL_BAND})
        assert created.status_code in (200, 201)
        cid = created.json().get("id") or created.json().get("indicator_id")
        assert cid
        lst = c.get("/api/v10/user-indicators")
        assert lst.json()["count"] == before + 1
        exp = c.get("/api/v10/user-indicators/export")
        assert exp.status_code == 200
        dlt = c.delete(f"/api/v10/user-indicators/{cid}")
        assert dlt.status_code in (200, 204)
        assert c.get("/api/v10/user-indicators").json()["count"] == before


# ---------------------------------------------------------------------------
# J05 — Backtest Center + exports (JSON + CSV) + optimizer
# ---------------------------------------------------------------------------
def test_j05_backtest_center_exports_optimizer():
    with _client() as c:
        bt = c.post("/api/v10/strategylab/backtest", json=BT_BODY)
        assert bt.status_code == 200
        bj = bt.json()
        assert bj["engine_version"] == "BT-PRODUCT-1.0.0"
        assert bj["data_trust_label"] == "SYNTHETIC_OR_PAPER"
        assert bj["result_digest"]
        assert isinstance(bj["limitations"], list) and bj["limitations"]

        e_json = c.post("/api/v10/strategylab/backtest/export", json={**BT_BODY, "format": "json"})
        assert e_json.status_code == 200
        e_csv = c.post("/api/v10/strategylab/backtest/export", json={**BT_BODY, "format": "csv"})
        assert e_csv.status_code == 200
        assert e_csv.headers["content-type"].startswith("text/csv")
        assert len(e_csv.content) > 0

        op = c.post("/api/v10/strategylab/optimize", json=OPTIMIZE_BODY)
        assert op.status_code == 200
        oj = op.json()
        assert oj["winner"]["params"]["fast"] == 8.0
        assert oj["budget_echo"]["max_evals"] == 3


# ---------------------------------------------------------------------------
# J06 — Forward Test Center: paper replay + walk-forward + export
# ---------------------------------------------------------------------------
def test_j06_forward_center_paper_replay_walkforward():
    with _client() as c:
        pr = c.post("/api/v10/strategylab/paper-replay", json=BT_BODY)
        assert pr.status_code == 200
        prj = pr.json()
        assert prj["ledger_chain_ok"] is True
        # server-derived honest mode label (pinned literal, not a client invention)
        assert prj["mode"] == "PAPER_REPLAY_OVER_SYNTHETIC_WINDOW"
        assert prj["not_live_note"]
        assert prj["summary_digest"]

        wf = c.post("/api/v10/strategylab/walkforward", json=WF_BODY)
        assert wf.status_code == 200
        wj = wf.json()
        assert wj["ok"] is True
        assert len(wj["folds"]) == 3
        assert wj["data_trust_label"] == "SYNTHETIC_OR_PAPER"
        assert wj["reproducibility_digest"]

        wfe = c.post("/api/v10/strategylab/walkforward/export", json={**WF_BODY, "format": "json"})
        assert wfe.status_code == 200


# ---------------------------------------------------------------------------
# J07 — Data Quality Center + session calendars
# ---------------------------------------------------------------------------
def test_j07_data_quality_center_calendars():
    with _client() as c:
        mk = c.get("/api/v10/dataquality/markets")
        assert mk.status_code == 200
        markets = mk.json()["markets"]
        names = {m["market"] for m in markets}
        # §8 universe: TSE/IFB + Forex + US INDEX only; US equity EXCLUDED honestly
        assert {"IRAN_TSE", "IRAN_IFB", "FOREX", "US_INDEX", "EXCLUDED_US_EQUITY"} <= names

        cov = c.get("/api/v10/dataquality/markets/IRAN_TSE/coverage")
        assert cov.status_code == 200

        cal = c.get("/api/v10/dataquality/calendars")
        assert cal.status_code == 200
        calj = cal.json()
        assert calj["trust_class"] == "DECLARED"
        assert calj["count"] >= 1

        one = c.get("/api/v10/dataquality/calendars/IR_EQ_CAL_DECLARED_V1")
        assert one.status_code == 200

        ss = c.get(
            "/api/v10/dataquality/calendars/IR_EQ_CAL_DECLARED_V1/session-state",
            params={"as_of_utc": "2026-11-04T09:00:00Z"},
        )
        assert ss.status_code == 200
        ssj = ss.json()
        assert ssj["state"]
        assert ssj["honesty"]


# ---------------------------------------------------------------------------
# J08 — Product Intelligence + five product loops + prediction registry
# ---------------------------------------------------------------------------
def test_j08_product_intelligence_five_loops():
    with _client() as c:
        mf = c.get("/api/v10/productloops/manifest")
        assert mf.status_code == 200
        loops = mf.json()["loops"]
        assert len(loops) == 5

        dos = c.get(
            "/api/v10/productloops/intel/dossier/فملی",
            params={"cutoff_utc": "2026-01-01T00:00:00Z"},
        )
        assert dos.status_code == 200
        assert dos.json()["dossier"]["information_cutoff_utc"] == "2026-01-01T00:00:00Z"

        rs = c.get("/api/v10/productloops/research/status")
        assert rs.status_code == 200
        assert rs.json()["honesty"]

        pid = f"P-E2E-{uuid.uuid4().hex[:12]}"
        reg = c.post(
            "/api/v10/productloops/predictions/register",
            json={
                "prediction_id": pid,
                "subject": "SYNTHETIC:فملی",
                "registered_at_utc": "2026-01-01T00:00:00Z",
                "outcome_horizon_end_utc": "2026-02-01T00:00:00Z",
                "evaluation_metric": "DIRECTION_HIT",
                "event_maturity_rule": "horizon_end",
                "invalidation_rule": "subject_removed",
                "evidence_ids": ["DECLARED-PREDICTION-EVIDENCE"],
                "creator": "journeys-e2e",
            },
        )
        assert reg.status_code == 200
        regj = reg.json()
        # "registered" carries the stored record (OA-5 durable registry)
        assert regj["registered"]["prediction_id"] == pid
        assert regj["persistence_durable"] is True

        lst = c.get(
            "/api/v10/productloops/predictions",
            params={"as_of_utc": "2026-01-01T00:00:00Z"},
        )
        assert lst.status_code == 200
        rows = lst.json().get("rows", [])
        assert any(r["prediction"]["prediction_id"] == pid for r in rows)
        assert all("maturity_state" in r for r in rows)


# ---------------------------------------------------------------------------
# J09 — AI-2 Studio: honest disabled gate (nothing executed, nothing ledgered)
# ---------------------------------------------------------------------------
def test_j09_ai2_studio_honest_disabled_gate():
    with _client() as c:
        p = c.get("/api/v10/ai2/posture")
        assert p.status_code == 200
        pj = p.json()
        assert pj["ai2_enabled"] is False
        assert pj["generation_allowed"] is False
        assert pj["execution_mode"] == "SYNTHETIC_OR_PAPER"
        honesty = pj["honesty"]
        for field in (
            "data_trust_label",
            "evaluation_series",
            "model_authority",
            "model_output_surface",
            "registry_persistence",
            "egress",
            "remote_provider_policy",
        ):
            assert field in honesty, field

        runs_before = c.get("/api/v10/ai2/runs").json()["total"]

        g = c.post(
            "/api/v10/ai2/generate",
            json={"question": "تست سفر کاربر", "symbol": "FOLAD", "timeframe": "1D", "bar_count": 200},
        )
        assert g.status_code == 200
        gj = g.json()
        assert gj["ok"] is False
        assert gj["status"] == "gated_not_executed"
        assert gj["error_code"] == "ai2_disabled"

        runs_after = c.get("/api/v10/ai2/runs").json()
        assert runs_after["total"] == runs_before  # refusal ledgered NOTHING
        assert runs_after["append_only"] is True


# ---------------------------------------------------------------------------
# J10 — Alert inbox (synthetic/paper, no egress, dispatch owner-gated)
# ---------------------------------------------------------------------------
def test_j10_alert_inbox_synthetic_paper():
    with _client() as c:
        inbox = c.get("/api/alerts/inbox")
        assert inbox.status_code == 200
        ij = inbox.json()
        assert ij["ok"] is True
        assert ij["label"] == SYNTHETIC_LABEL
        assert isinstance(ij["items"], list)
        assert all(item.get("label") == SYNTHETIC_LABEL for item in ij["items"])

        st = c.get("/api/alerts/ops/status")
        assert st.status_code == 200
        health = st.json()["health"]
        assert health["mode"] == "SYNTHETIC_OR_PAPER"
        assert health["delivery_channel"] == "IN_PRODUCT_INBOX"


# ---------------------------------------------------------------------------
# J11 — Workspace save/restore + popup detach (backend-verifiable subset)
# ---------------------------------------------------------------------------
def test_j11_workspace_and_popup_detach_assets():
    with _client() as c:
        shell = c.get("/")
        assert shell.status_code == 200
        assert shell.headers["content-type"].startswith("text/html")
        assert shell.text.count('data-tab="') >= 31

        ws = c.get("/static/js/modules/workspace.js")
        assert ws.status_code == 200
        ws_text = ws.text
        assert "localStorage" in ws_text  # injected storage adapter default
        assert "بدون هیچ تماس شبکه‌ای" in ws_text  # zero-network honesty note

        cg = c.get("/static/js/modules/render/chart_grid.js")
        assert cg.status_code == 200
        cg_text = cg.text
        assert "DETACH_INTENT" in cg_text  # popup detach capture
        assert "radar.grid.sync.v1" in cg_text  # WAVE-S2 cross-window channel
        assert "pane_range" in cg_text  # WAVE-S2 range validator token


# ---------------------------------------------------------------------------
# J12 — Command palette + deep links (hash bridge + SPA fallback)
# ---------------------------------------------------------------------------
def test_j12_command_palette_and_deep_links():
    with _client() as c:
        pal = c.get("/static/js/modules/command_palette.js")
        assert pal.status_code == 200
        pal_text = pal.text
        assert "radar.palette.recent.v1" in pal_text
        assert "keydown" in pal_text

        mainjs = c.get("/static/js/main.js")
        assert mainjs.status_code == 200
        assert "location.hash" in mainjs.text  # GOV-24/WP-3 hash→tab bridge

        # deep-link surface: the dedicated symbol page route serves a page
        deep = c.get("/symbol/فملی")
        assert deep.status_code == 200
        assert deep.headers["content-type"].startswith("text/html")
