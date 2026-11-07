"""test_wpa_opportunity_runtime.py — WAVE-AB5 (WP-A) acceptance tests.

Covers the three WP-A deliverables:

1. runtime opportunity clustering
   (app/services/opportunity_clustering.py): deterministic clustering of
   market-intelligence ``OpportunityRank`` rows into governed
   ``OpportunityObject``/``OpportunityCluster`` records with ALL FIVE corpus
   explanations, declared-rule classification (4 kinds, 7 classes), run_id
   governance binding, and typed refusal of unclassified ranks;
2. GET /api/ai/opportunity-clusters (additive API surface): clusters in the
   payload, typed 422s, deterministic repeat;
3. the AI-7 recommendation vocabulary 6-label behavior: a direct
   SELL_CANDIDATE path test and the additive HOLD emission under the
   deterministic single technical-vs-fundamental conflict condition.

No network, no clock reads (every instant is caller-supplied), no LLM.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

import pytest
from fastapi.testclient import TestClient

from app.domain.ai_intelligence import AIIntelligenceCore
from app.domain.market_intelligence import (
    MarketIntelligenceSnapshot,
    MarketMonitoringResult,
    OpportunityRank,
)
from app.domain.opportunity import OpportunityCluster, OpportunityObject
from app.services.opportunity_clustering import (
    OPPORTUNITY_CLUSTERING_VERSION,
    OpportunityClusteringRefusal,
    build_opportunity_clusters,
)
from app.main import app

UTC = timezone.utc
T0 = datetime(2026, 11, 8, 9, 0, 0, tzinfo=UTC)

# Distinct client identity (rate-limiter symmetry with the other suites).
client = TestClient(app, client=("waveab5-wpa", 12700))


def rank(
    sym: str,
    ind: str,
    overall: float,
    tech: float,
    mf: float,
    fund: float,
    *,
    risk: float = 45.0,
    rec: str = "BUY_CANDIDATE",
    confidence: float = 0.6,
    evidence: List[dict[str, Any]] | None = None,
    warnings: List[str] | None = None,
) -> OpportunityRank:
    return OpportunityRank(
        rank=1,
        symbol=sym,
        name=sym,
        industry=ind,
        overall_score=overall,
        confidence=confidence,
        money_flow_score=mf,
        technical_score=tech,
        fundamental_score=fund,
        filter_score=70,
        strategy_score=0,
        risk_score=risk,
        recommendation=rec,
        data_trust={"state": "synthetic", "is_live": False},
        evidence=evidence or [],
        warnings=warnings or [],
    )


CONTEXT = {"watchlist_symbols": ["خودرو"]}


def _ranks() -> List[OpportunityRank]:
    return [
        rank("فملی", "فلزات", 72.0, 68.0, 72.0, 55.0),
        rank("فولاد", "فلزات", 62.0, 50.0, 58.0, 62.0),
        rank("خودرو", "خودرو", 58.0, 35.0, 50.0, 61.0),
    ]


# ---------------------------------------------------------------------------
# 1) Runtime clustering — five explanations, declared rules, refusals
# ---------------------------------------------------------------------------


def test_clusters_built_from_ranks_with_all_five_explanations() -> None:
    evidence_negative = [
        {"category": "technical", "name": "entry_score", "direction": "negative", "value": 40},
        {"category": "money_flow", "name": "buy_power", "direction": "positive", "value": 2.4},
    ]
    ranks = _ranks()
    ranks[0].evidence = evidence_negative
    ranks[0].warnings = ["volume spike without follow-through"]
    result = build_opportunity_clusters(
        ranks, run_id="RUN-WPA-1", created_at_utc=T0, declared_context=CONTEXT
    )
    assert result.objects and result.clusters
    # every object: one declared kind + concrete class + governance binding
    for obj in result.objects:
        assert isinstance(obj, OpportunityObject)
        assert obj.opportunity_kind in {
            "MARKET_STOCK_INVESTMENT_CANDIDATE",
            "USER_WATCHLIST_COMPANY_INTELLIGENCE",
            "EVENT_NEWS_DRIVEN_CANDIDATE",
            "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
        }
        assert obj.class_label != "UNCLASSIFIED"
        assert obj.class_definition is not None
        assert obj.class_definition.formal_definition
        assert obj.class_definition.data_prerequisites
        assert obj.class_definition.historical_evaluation_ref is None  # never fabricated
        assert obj.run_id == "RUN-WPA-1"
        assert obj.evidence_ids  # deterministic references into the rank payload
        assert obj.invalidation_conditions
        assert obj.reason_for_now
        assert obj.risk_semantics
        assert obj.data_trust_state == "synthetic"
    for cluster in result.clusters:
        assert isinstance(cluster, OpportunityCluster)
        # FIVE mandatory corpus explanations (06 §6), all present and honest:
        assert cluster.why_now  # 1) why now
        assert cluster.invalidation_conditions  # 2) what could invalidate
        assert cluster.risk_adjusted_interpretation  # 4) risk-adjusted reading
        assert cluster.missing_information  # 5) what is missing — explicit, never fabricated
        assert any(
            "not available in the rank payload" in note
            for note in cluster.missing_information
        )
        assert cluster.run_id == "RUN-WPA-1"
        assert cluster.class_definition.label == cluster.class_label
        # 3) disagreeing evidence — derived from the negative-direction item
    by_label = {c.class_label: c for c in result.clusters}
    volume_cluster = by_label["VOLUME_EXPANSION"]
    assert volume_cluster.disagreeing_evidence_ids, "negative-direction evidence must surface"
    assert any("technical" in ref for ref in volume_cluster.disagreeing_evidence_ids)
    # cluster invalidations include the member warnings verbatim
    assert "volume spike without follow-through" in volume_cluster.invalidation_conditions
    # grouping is by (industry, class): فملی and فولاد are both فلزات but different classes
    assert len(result.clusters) == 3
    assert by_label["EARLY_ACCUMULATION"].member_object_ids == ("OPP-RUN-WPA-1-فولاد",)
    assert by_label["OVERSOLD_RECOVERY"].member_object_ids == ("OPP-RUN-WPA-1-خودرو",)


def test_kind_classification_follows_declared_rules() -> None:
    # score-threshold rule: overall>=60 AND money_flow>=55 → stock candidate
    result = build_opportunity_clusters(
        [rank("الف", "صنعت", 60.0, 40.0, 55.0, 50.0)],
        run_id="RUN-2",
        created_at_utc=T0,
    )
    obj = result.objects[0]
    assert obj.opportunity_kind == "MARKET_STOCK_INVESTMENT_CANDIDATE"
    assert obj.basis == "OPPORTUNITY_SCORE_ONLY"
    # just below the declared score threshold → refused (no loose classification)
    with pytest.raises(OpportunityClusteringRefusal, match="rank_unclassified_kind"):
        build_opportunity_clusters(
            [rank("ب", "صنعت", 59.9, 40.0, 55.0, 50.0)], run_id="RUN-2", created_at_utc=T0
        )
    # watchlist membership comes ONLY from the declared context
    result = build_opportunity_clusters(
        [rank("خودرو", "خودرو", 58.0, 35.0, 50.0, 61.0)],
        run_id="RUN-3",
        created_at_utc=T0,
        declared_context={"watchlist_symbols": ["خودرو"]},
    )
    assert result.objects[0].opportunity_kind == "USER_WATCHLIST_COMPANY_INTELLIGENCE"
    assert result.objects[0].company_role == "WATCHLIST_COMPANY"
    assert any("DECLARED-WATCHLIST-MEMBERSHIP" in e for e in result.objects[0].evidence_ids)
    # event/news evidence → event-driven kind
    result = build_opportunity_clusters(
        [rank("ج", "صنعت", 30.0, 20.0, 20.0, 30.0, rec="WATCH",
              evidence=[{"category": "news", "name": "disclosure", "direction": "positive"}])],
        run_id="RUN-4",
        created_at_utc=T0,
    )
    assert result.objects[0].opportunity_kind == "EVENT_NEWS_DRIVEN_CANDIDATE"
    assert result.objects[0].class_label == "MATERIAL_FUNDAMENTAL_EVENT_CHANGE"


def test_ma_signal_only_from_declared_dedicated_evidence_never_from_score() -> None:
    # a strong score with NO declared MA evidence is never an MA signal
    result = build_opportunity_clusters(
        [rank("قوی", "صنعت", 90.0, 90.0, 90.0, 90.0)],
        run_id="RUN-5",
        created_at_utc=T0,
    )
    assert result.objects[0].opportunity_kind == "MARKET_STOCK_INVESTMENT_CANDIDATE"
    assert result.objects[0].ma_signal_evidence_ids == ()
    # MA classification requires the caller-declared dedicated evidence ids
    result = build_opportunity_clusters(
        [rank("هدف", "صنعت", 30.0, 20.0, 20.0, 30.0, rec="WATCH")],
        run_id="RUN-6",
        created_at_utc=T0,
        declared_context={"ma_signal_evidence": {"هدف": ["MA-EV-1", "MA-EV-2"]}},
    )
    obj = result.objects[0]
    assert obj.opportunity_kind == "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL"
    assert obj.company_role == "MA_TARGET_SIGNAL"
    assert obj.basis == "EVIDENCE_BASED"
    assert obj.ma_signal_evidence_ids == ("MA-EV-1", "MA-EV-2")
    # declared MA ids are part of the object's evidence (dedicated, own basis)
    assert {"MA-EV-1", "MA-EV-2"} <= set(obj.evidence_ids)


def test_unclassified_and_duplicate_ranks_refused_run_id_required() -> None:
    # kind-level refusal
    with pytest.raises(OpportunityClusteringRefusal, match="rank_unclassified_kind"):
        build_opportunity_clusters(
            [rank("ضعیف", "صنعت", 20.0, 10.0, 10.0, 10.0, rec="WATCH")],
            run_id="RUN-7",
            created_at_utc=T0,
        )
    # class-level refusal: kind matches via watchlist but no class rule does
    with pytest.raises(OpportunityClusteringRefusal, match="rank_unclassified_class"):
        build_opportunity_clusters(
            [rank("خودرو", "خودرو", 10.0, 10.0, 10.0, 10.0, rec="WATCH")],
            run_id="RUN-7",
            created_at_utc=T0,
            declared_context={"watchlist_symbols": ["خودرو"]},
        )
    # duplicate symbol refused (deterministic fail-closed)
    with pytest.raises(OpportunityClusteringRefusal, match="duplicate_rank_symbol"):
        build_opportunity_clusters(
            [rank("الف", "صنعت", 70.0, 40.0, 60.0, 50.0),
             rank("الف", "صنعت", 71.0, 41.0, 61.0, 51.0)],
            run_id="RUN-7",
            created_at_utc=T0,
        )
    # governance binding: run_id is REQUIRED
    with pytest.raises(OpportunityClusteringRefusal, match="run_id_required"):
        build_opportunity_clusters(_ranks(), run_id="", created_at_utc=T0)
    with pytest.raises(OpportunityClusteringRefusal, match="run_id_required"):
        build_opportunity_clusters(_ranks(), run_id="   ", created_at_utc=T0)


def test_clustering_is_deterministic() -> None:
    args = dict(run_id="RUN-DET", created_at_utc=T0, declared_context=CONTEXT)
    first = build_opportunity_clusters(_ranks(), **args).model_dump(mode="json")
    second = build_opportunity_clusters(_ranks(), **args).model_dump(mode="json")
    assert first == second
    # different run_id → same structure, different ids (governance binding shows)
    other = build_opportunity_clusters(_ranks(), run_id="RUN-DET-2", created_at_utc=T0,
                                       declared_context=CONTEXT).model_dump(mode="json")
    assert other["clusters"][0]["cluster_id"] != first["clusters"][0]["cluster_id"]
    assert other["clusters"][0]["why_now"] == first["clusters"][0]["why_now"]
    assert first["clustering_version"] == OPPORTUNITY_CLUSTERING_VERSION


# ---------------------------------------------------------------------------
# 2) API surface — GET /api/ai/opportunity-clusters
# ---------------------------------------------------------------------------


def _fake_cycle(monkeypatch, ranks: List[OpportunityRank]) -> None:
    snapshot = MarketIntelligenceSnapshot(
        timestamp=1000.0,
        market_regime="NEUTRAL",
        data_trust={"state": "synthetic", "is_live": False},
    )

    async def fake_cycle(self, market_service, *, limit=20, persist=True):
        return MarketMonitoringResult(
            snapshot=snapshot,
            opportunities=ranks,
            industries=[],
            events=[],
            symbol_intelligence=[],
            history_count=0,
        )

    from app.services.market_intelligence_service import MarketIntelligenceService

    monkeypatch.setattr(MarketIntelligenceService, "run_market_monitoring_cycle", fake_cycle)


QUERY = {
    "run_id": "RUN-API-1",
    "created_at_utc": "2026-11-08T09:00:00Z",
    "limit": 10,
    "declared_context": '{"watchlist_symbols": ["خودرو"]}',
}


def test_api_surface_returns_clusters_deterministically(monkeypatch) -> None:
    _fake_cycle(monkeypatch, _ranks())
    res = client.get("/api/ai/opportunity-clusters", params=QUERY)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["clustering_version"] == OPPORTUNITY_CLUSTERING_VERSION
    assert body["run_id"] == "RUN-API-1"
    assert body["cluster_count"] == len(body["opportunity_clusters"]) == 3
    assert body["object_count"] == len(body["opportunity_objects"]) == 3
    for cluster in body["opportunity_clusters"]:
        assert cluster["why_now"]
        assert cluster["invalidation_conditions"]
        assert cluster["risk_adjusted_interpretation"]
        assert cluster["missing_information"]
        assert cluster["run_id"] == "RUN-API-1"
    assert body["governance"]["run_id_required"] is True
    assert body["governance"]["unclassified_refused"] is True
    assert body["governance"]["ma_signal_requires_declared_evidence"] is True
    assert body["honesty"]["advisory_only"] is True
    # deterministic repeat: identical payload for identical inputs
    res2 = client.get("/api/ai/opportunity-clusters", params=QUERY)
    assert res2.status_code == 200
    assert res2.json() == body


def test_api_surface_typed_refusals(monkeypatch) -> None:
    _fake_cycle(monkeypatch, [rank("ضعیف", "صنعت", 20.0, 10.0, 10.0, 10.0, rec="WATCH")])
    res = client.get("/api/ai/opportunity-clusters", params=QUERY)
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["error"] == "OPPORTUNITY_CLUSTERING_REFUSED"
    assert detail["reason"] == "rank_unclassified_kind"
    # missing run_id → required-param refusal
    res = client.get(
        "/api/ai/opportunity-clusters",
        params={"created_at_utc": "2026-11-08T09:00:00Z"},
    )
    assert res.status_code == 422
    # naive instant refused (no wall clock; caller must be explicit)
    _fake_cycle(monkeypatch, _ranks())
    res = client.get(
        "/api/ai/opportunity-clusters",
        params={**QUERY, "created_at_utc": "2026-11-08T09:00:00"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "NAIVE_INSTANT_REFUSED"
    # malformed declared_context refused
    res = client.get(
        "/api/ai/opportunity-clusters",
        params={**QUERY, "declared_context": "not-json"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "MALFORMED_DECLARED_CONTEXT"


# ---------------------------------------------------------------------------
# 3) SELL_CANDIDATE path + HOLD emission (6-label vocabulary)
# ---------------------------------------------------------------------------


def _symbol_context(entry=80, exit_score=10, buy_power=2.0, volume_ratio=2.5, value_score=75):
    return {
        "snapshot": {"l18": "فملی", "pl": 1000, "plp": 1.2},
        "metrics": {
            "entry_score": entry,
            "exit_score": exit_score,
            "buy_power": buy_power,
            "volume_ratio": volume_ratio,
            "individual_net_value": 5_000_000_000,
        },
        "tablocastic": {"golden_number": 70, "grade": "A"},
        "fundamental": {"value_score": value_score, "fund_score": value_score, "is_synthetic": False},
    }


VERIFIED_LIVE = {
    "state": "live",
    "is_live": True,
    "live_verified": True,
    "trust_level": "live",
    "source": "tsetmc",
}


def test_sell_candidate_path_is_reachable_directly() -> None:
    core = AIIntelligenceCore()
    # exit pressure high (exit_score >= 65) with NO conflicts and healthy flow:
    # entry 50/golden 70 → technical 57 (< 60, no entry/exit conflict);
    # money_flow = 22.5 + 15 + 25 = 62.5 (>= 35, no money-flow conflict)
    result = core.evaluate(
        symbol_context=_symbol_context(entry=50, exit_score=70, buy_power=2.0, volume_ratio=2.0, value_score=60),
        filter_context={"sample": {"count": 2}},
        data_trust=VERIFIED_LIVE,
    )
    assert result.recommendation == "SELL_CANDIDATE"
    assert result.conflicts == []
    assert "DATA_TRUST_BLOCK" not in result.reason_codes


def test_hold_emitted_for_genuine_technical_vs_fundamental_conflict() -> None:
    core = AIIntelligenceCore()
    # technical supports entry (entry 85/golden 70 → technical 79.75 >= 65)
    # while fundamental opposes (value 20 < 35), money flow healthy (62.5 >= 35),
    # exit 30 (< 60 → no entry/exit conflict) → the ONLY conflict is
    # technical-vs-fundamental, with comparable weight (composite < 75):
    # HOLD is the honest recommendation (previously collapsed into WATCH).
    result = core.evaluate(
        symbol_context=_symbol_context(entry=85, exit_score=30, buy_power=2.0, volume_ratio=2.0, value_score=20),
        filter_context={"sample": {"count": 2}},
        data_trust=VERIFIED_LIVE,
    )
    assert result.recommendation == "HOLD"
    assert result.conflicts == [
        "Technical evidence is positive but fundamental evidence is weak."
    ]
    assert "TECHNICAL_FUNDAMENTAL_CONFLICT_HOLD" in result.reason_codes
    assert result.safety["requires_human_approval"] is True
    # control: a SECOND conflict (weak money flow) keeps the generic WATCH
    control = core.evaluate(
        symbol_context=_symbol_context(entry=85, exit_score=5, buy_power=0.4, volume_ratio=0.6, value_score=20),
        filter_context={"sample": {"count": 2}},
        data_trust=VERIFIED_LIVE,
    )
    assert control.recommendation == "WATCH"
    assert len(control.conflicts) == 2
    assert "TECHNICAL_FUNDAMENTAL_CONFLICT_HOLD" not in control.reason_codes


def test_hold_reserved_band_does_not_disturb_buy_or_sell_paths() -> None:
    core = AIIntelligenceCore()
    # strong aligned evidence (no conflicts) still resolves to BUY_CANDIDATE
    buy = core.evaluate(
        symbol_context=_symbol_context(),
        market_context={"confluence": {"buy_alerts": 5, "sell_alerts": 0}},
        filter_context={"sample": {"count": 3}},
        backtest_context={"metrics": {"profit_factor": 1.4, "maximum_drawdown": 8}},
        data_trust=VERIFIED_LIVE,
    )
    assert buy.recommendation == "BUY_CANDIDATE"
    # trust-blocked data still resolves to INSUFFICIENT_DATA (never HOLD)
    blocked = core.evaluate(
        symbol_context=_symbol_context(entry=85, exit_score=30, value_score=20),
        data_trust={"state": "mock", "is_live": False},
    )
    assert blocked.recommendation == "INSUFFICIENT_DATA"


def test_recommendation_vocabulary_has_exactly_six_labels() -> None:
    from typing import get_args

    from app.domain.ai_intelligence import Recommendation

    assert set(get_args(Recommendation)) == {
        "BUY_CANDIDATE",
        "HOLD",
        "SELL_CANDIDATE",
        "WATCH",
        "NO_ACTION",
        "INSUFFICIENT_DATA",
    }
