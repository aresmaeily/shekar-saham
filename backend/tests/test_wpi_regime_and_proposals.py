"""test_wpi_regime_and_proposals.py — WAVE-AB5 (WP-I) acceptance tests.

Covers the three WP-I deliverables:

1. regime-sliced prediction performance
   (app/domain/prediction_regime_performance.py): hand-computed Brier/ECE
   per caller-declared regime label, honest EMPTY slices for declared
   regimes with no bound predictions, deterministic canonical ordering,
   exact-rational results, typed refusals for malformed/unknown labels;
2. GET /api/v10/productloops/predictions/calibration/by-regime: honest
   empty payload on an empty store, typed 422s (malformed labels/JSON,
   unknown labels, unevaluated / unknown / look-ahead bindings), real
   end-to-end binding through the durable store;
3. deterministic research-proposal DRAFTS
   (app/domain/prediction_research_proposals.py): the 10-field discipline,
   preregistered=False, advisory_only=True, evidence referencing the
   evaluation's own linked records, PURE function with NO registration /
   adoption path anywhere.

No network, no clock reads, no LLM; everything synthetic/declared.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.domain.prediction import PredictionEvaluation
from app.domain.prediction_regime_performance import (
    EMPTY_SLICE_REASON,
    RegimeBoundPrediction,
    slice_prediction_performance_by_regime,
)
from app.domain.prediction_research_proposals import (
    KNOWN_ERROR_CATEGORIES,
    derive_research_proposal_draft,
)
from app.main import app

# Distinct client identity (rate-limiter symmetry with the other v10 suites).
client = TestClient(app, client=("waveab5-wpi", 12600))

# Settings-cache hygiene (symmetry with test_product_loops_api.py): the
# durable prediction-store isolation in conftest relies on get_settings()
# seeing the per-test PREDICTION_DB_PATH env; without this per-test cache
# clear a settings object cached at import time would keep pointing every
# test at the repository's runtime store. This fixture rebuilds the cache
# from the restored environment before each test — it changes nothing about
# DATA_SOURCE/AI gates and skips nothing.
from app.core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _settings_cache_hygiene():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

PREFIX = "/api/v10/productloops"

MEASURED_AT = "2026-03-01T00:00:00Z"


def _bound(prediction_id: str, label: str, p: float, y: float) -> RegimeBoundPrediction:
    return RegimeBoundPrediction(
        prediction_id=prediction_id, regime_label=label, predicted_probability=p, observed=y
    )


# ---------------------------------------------------------------------------
# 1) Domain slicing — hand-computed correctness
# ---------------------------------------------------------------------------


def test_per_regime_brier_hand_computed() -> None:
    records = [
        _bound("P1", "BULLISH", 0.9, 1),
        _bound("P2", "BULLISH", 0.2, 0),
        _bound("P3", "BEARISH", 0.8, 0),
    ]
    rows = slice_prediction_performance_by_regime(records, ["BULLISH", "BEARISH"])
    by_label = {r.regime_label: r for r in rows}
    # BULLISH: Brier = ((1-0.9)^2 + (0.2-0)^2)/2 = (0.01 + 0.04)/2 = 0.025
    assert by_label["BULLISH"].brier_score == pytest.approx(0.025)
    assert by_label["BULLISH"].prediction_count == 2
    # BULLISH ECE over 10 buckets: |0.9-1| in bucket (0.8,0.9] and |0.2-0| in
    # bucket (0.1,0.2] → 0.5*0.1 + 0.5*0.2 = 0.15
    assert by_label["BULLISH"].expected_calibration_error == pytest.approx(0.15)
    # BEARISH: single pair (0.8, 0) → Brier = 0.64, ECE = 0.8
    assert by_label["BEARISH"].brier_score == pytest.approx(0.64)
    assert by_label["BEARISH"].expected_calibration_error == pytest.approx(0.8)
    assert all(not r.empty for r in rows)


def test_empty_slice_is_explicit_and_never_fabricated() -> None:
    records = [_bound("P1", "BULLISH", 0.9, 1)]
    rows = slice_prediction_performance_by_regime(
        records, ["BULLISH", "BEARISH", "NEUTRAL"]
    )
    by_label = {r.regime_label: r for r in rows}
    for label in ("BEARISH", "NEUTRAL"):
        row = by_label[label]
        assert row.empty is True
        assert row.prediction_count == 0
        assert row.brier_score is None
        assert row.expected_calibration_error is None
        assert row.empty_reason == EMPTY_SLICE_REASON
    assert not by_label["BULLISH"].empty
    # no assignments at all → every declared regime is an honest empty slice
    rows = slice_prediction_performance_by_regime([], ["HIGH_VOLATILITY"])
    assert rows[0].empty is True and rows[0].empty_reason == EMPTY_SLICE_REASON


def test_slicing_is_deterministic_and_canonically_ordered() -> None:
    records = [
        _bound("P1", "NEUTRAL", 0.5, 1),
        _bound("P2", "BULLISH", 0.9, 0),
        _bound("P3", "LOW_VOLATILITY", 0.3, 0),
    ]
    # caller order is irrelevant: the report follows the closed vocabulary's
    # canonical order restricted to the declared labels
    rows_a = slice_prediction_performance_by_regime(
        records, ["NEUTRAL", "BULLISH", "LOW_VOLATILITY"]
    )
    rows_b = slice_prediction_performance_by_regime(
        records, ["LOW_VOLATILITY", "NEUTRAL", "BULLISH"]
    )
    assert [r.regime_label for r in rows_a] == ["BULLISH", "NEUTRAL", "LOW_VOLATILITY"]
    assert rows_a == rows_b
    # repeat call is byte-identical (same records, same declared labels)
    assert slice_prediction_performance_by_regime(records[:2], ["NEUTRAL", "BULLISH"]) == rows_a[:2]
    # a record bound to a label the caller did NOT declare is refused
    with pytest.raises(ValueError, match="bound_label_not_declared"):
        slice_prediction_performance_by_regime(records, ["NEUTRAL", "BULLISH"])


def test_domain_refusals_are_typed() -> None:
    records = [_bound("P1", "BULLISH", 0.9, 1), _bound("P2", "BULLISH", 0.4, 0)]
    with pytest.raises(ValueError, match="unknown_regime_label"):
        slice_prediction_performance_by_regime(records, ["SIDEWAYS"])
    with pytest.raises(ValueError, match="duplicate_regime_label"):
        slice_prediction_performance_by_regime(records, ["BULLISH", "BULLISH"])
    with pytest.raises(ValueError, match="no_regime_labels"):
        slice_prediction_performance_by_regime(records, [])
    with pytest.raises(ValueError, match="duplicate_prediction_binding"):
        slice_prediction_performance_by_regime(
            [records[0], records[0]], ["BULLISH"]
        )
    with pytest.raises(ValueError, match="bound_label_not_declared"):
        slice_prediction_performance_by_regime(
            [_bound("P9", "BEARISH", 0.5, 1)], ["BULLISH"]
        )
    with pytest.raises(ValueError, match="bucket_count_out_of_bounds"):
        slice_prediction_performance_by_regime(records, ["BULLISH"], bucket_count=99)
    with pytest.raises(ValueError, match="outcome_must_be_binary"):
        RegimeBoundPrediction(
            prediction_id="PX", regime_label="BULLISH", predicted_probability=0.5, observed=0.5
        )


# ---------------------------------------------------------------------------
# 2) Runtime endpoint — honest empty payload, typed 422s, real binding
# ---------------------------------------------------------------------------


def test_by_regime_endpoint_honest_empty_payload_on_empty_store() -> None:
    # conftest isolates a throwaway durable store per test → truly empty
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={
            "measured_at_utc": MEASURED_AT,
            "regime_labels": json.dumps(["BULLISH", "BEARISH"]),
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["evaluated_predictions_in_registry"] == 0
    assert body["assignment_count"] == 0
    assert body["empty_registry_note"]
    table = {r["regime_label"]: r for r in body["regime_table"]}
    assert table["BULLISH"]["empty"] is True
    assert table["BULLISH"]["brier_score"] is None
    assert table["BEARISH"]["empty_reason"] == EMPTY_SLICE_REASON
    assert body["honesty"]["synthetic_note"]
    assert body["trust_envelope"]["data_trust"]


def test_by_regime_endpoint_typed_refusals() -> None:
    base = {"measured_at_utc": MEASURED_AT, "regime_labels": json.dumps(["BULLISH"])}
    # malformed labels JSON
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={"measured_at_utc": MEASURED_AT, "regime_labels": "not-json"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "MALFORMED_REGIME_LABELS"
    # labels not a list
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={"measured_at_utc": MEASURED_AT, "regime_labels": json.dumps("BULLISH")},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "MALFORMED_REGIME_LABELS"
    # label outside the closed vocabulary
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={"measured_at_utc": MEASURED_AT, "regime_labels": json.dumps(["SIDEWAYS"])},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "UNKNOWN_REGIME_LABEL"
    # malformed assignments JSON
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={**base, "assignments": "not-json"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "MALFORMED_REGIME_ASSIGNMENTS"
    # unknown prediction id
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={
            **base,
            "assignments": json.dumps(
                [{"prediction_id": "NOPE", "regime_label": "BULLISH",
                  "predicted_probability": 0.9, "observed": 1}]
            ),
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "UNKNOWN_PREDICTION_ID"
    # naive instant refused
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={"measured_at_utc": "2026-03-01T00:00:00", "regime_labels": json.dumps(["BULLISH"])},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "NAIVE_INSTANT_REFUSED"


def _lifecycle(prediction_id: str, *, evaluate: bool = True) -> None:
    res = client.post(
        f"{PREFIX}/predictions/register",
        json={
            "prediction_id": prediction_id,
            "subject": "SYNTHETIC:فملی",
            "registered_at_utc": "2026-01-01T00:00:00Z",
            "outcome_horizon_end_utc": "2026-02-01T00:00:00Z",
            "evaluation_metric": "DIRECTION_HIT",
            "event_maturity_rule": "horizon_end",
            "invalidation_rule": "subject_removed",
            "evidence_ids": ["DECLARED-PREDICTION-EVIDENCE"],
            "creator": "waveab5-tests",
        },
    )
    assert res.status_code == 200, res.text
    res = client.post(
        f"{PREFIX}/predictions/{prediction_id}/outcome",
        json={
            "outcome_id": f"OUT-{prediction_id}",
            "observed_at_utc": "2026-02-02T00:00:00Z",
            "observed_numeric": 1.0,
            "source_evidence_ids": ["DECLARED-OUTCOME-EVIDENCE"],
        },
    )
    assert res.status_code == 200
    if evaluate:
        res = client.post(
            f"{PREFIX}/predictions/{prediction_id}/evaluate",
            params={"as_of_utc": "2026-02-03T00:00:00Z"},
            json={"matched_expectation": True},
        )
        assert res.status_code == 200


def test_by_regime_endpoint_full_binding_and_lookahead_refusal() -> None:
    _lifecycle("P-WPI-1")
    assignments = json.dumps(
        [{"prediction_id": "P-WPI-1", "regime_label": "BULLISH",
          "predicted_probability": 0.9, "observed": 1}]
    )
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={
            "measured_at_utc": "2026-03-01T00:00:00Z",
            "regime_labels": json.dumps(["BULLISH", "BEARISH"]),
            "assignments": assignments,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["assignment_count"] == 1
    table = {r["regime_label"]: r for r in body["regime_table"]}
    assert table["BULLISH"]["brier_score"] == pytest.approx(0.01)  # (0.9-1)^2
    assert table["BEARISH"]["empty"] is True
    # look-ahead: outcome observed after the measurement instant is refused
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={
            "measured_at_utc": "2026-02-01T00:00:00Z",
            "regime_labels": json.dumps(["BULLISH"]),
            "assignments": assignments,
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "OUTCOME_AFTER_MEASUREMENT_REFUSED"
    # a REGISTERED-but-UNEVALUATED prediction is refused for the regime table
    _lifecycle("P-WPI-2", evaluate=False)
    res = client.get(
        f"{PREFIX}/predictions/calibration/by-regime",
        params={
            "measured_at_utc": "2026-03-01T00:00:00Z",
            "regime_labels": json.dumps(["BULLISH"]),
            "assignments": json.dumps(
                [{"prediction_id": "P-WPI-2", "regime_label": "BULLISH",
                  "predicted_probability": 0.7, "observed": 1}]
            ),
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "PREDICTION_NOT_EVALUATED"


# ---------------------------------------------------------------------------
# 3) Research-proposal DRAFTS — 10-field discipline, never auto-registered
# ---------------------------------------------------------------------------


def _evaluation(error_category: str | None) -> PredictionEvaluation:
    return PredictionEvaluation(
        prediction_id="P-DRAFT-1",
        outcome_id="OUT-P-DRAFT-1",
        evaluated_at_utc="2026-02-03T00:00:00Z",
        matched_expectation=False,
        error_category=error_category,
        calibration_note="overconfident",
    )


def test_draft_vocabulary_and_honest_none() -> None:
    assert set(KNOWN_ERROR_CATEGORIES) == {"direction-miss", "maturity-mismatch"}
    assert derive_research_proposal_draft(_evaluation("direction-miss")) is not None
    assert derive_research_proposal_draft(_evaluation("maturity-mismatch")) is not None
    # unknown / absent error category → NO draft invented
    assert derive_research_proposal_draft(_evaluation("mystery-category")) is None
    assert derive_research_proposal_draft(_evaluation(None)) is None


def test_drafts_carry_ten_field_discipline_and_preregistered_false() -> None:
    draft = derive_research_proposal_draft(_evaluation("direction-miss"))
    assert draft is not None
    # 10-field discipline (mirroring the audit ImprovementProposal contract)
    assert isinstance(draft.baseline, dict) and draft.baseline  # 1) baseline
    assert draft.evidence_ids == (  # 2) observed problem AS evidence (linked records)
        "PREDICTION-RECORD:P-DRAFT-1",
        "OUTCOME-RECORD:OUT-P-DRAFT-1",
    )
    assert draft.expected_benefit  # 3
    assert draft.uncertainty  # 4
    assert draft.cost  # 5
    assert len(draft.risks) >= 1  # 6
    assert draft.rollback_plan  # 7
    assert draft.evaluation_design  # 8
    assert draft.approval_state == "DRAFT"  # 9 (pinned — cannot represent acceptance)
    assert draft.advisory_only is True  # 10 (type-locked)
    # preregistration discipline: a DRAFT is never preregistered by the machine
    assert draft.preregistered is False
    # direction-miss maps to a signal-direction calibration question;
    # maturity-mismatch maps to a horizon-calibration question
    direction = derive_research_proposal_draft(_evaluation("direction-miss"))
    maturity = derive_research_proposal_draft(_evaluation("maturity-mismatch"))
    assert direction is not None and maturity is not None
    assert direction.research_question != maturity.research_question
    assert "جهت" in direction.research_question
    assert "افق" in maturity.research_question


def test_drafts_are_pure_and_deterministic() -> None:
    evaluation = _evaluation("maturity-mismatch")
    d1 = derive_research_proposal_draft(evaluation)
    d2 = derive_research_proposal_draft(evaluation)
    assert d1 == d2  # same evaluation → byte-identical draft


def test_no_auto_adoption_path_exists() -> None:
    import app.domain.prediction_research_proposals as module

    # the module exposes NO registration / adoption / promotion function and
    # holds NO global draft registry — the only producer is the pure deriver
    public = {name for name in dir(module) if not name.startswith("_")}
    forbidden_verbs = ("register", "adopt", "promote", "apply", "deploy", "approve")
    for name in public:
        assert not any(verb in name.lower() for verb in forbidden_verbs), name
    assert "derive_research_proposal_draft" in public
    # the draft type structurally cannot represent acceptance
    from app.domain.prediction_research_proposals import PredictionResearchProposalDraft

    assert set(PredictionResearchProposalDraft.model_fields["approval_state"].annotation.__args__) == {"DRAFT"}
    assert set(PredictionResearchProposalDraft.model_fields["preregistered"].annotation.__args__) == {False}
    assert set(PredictionResearchProposalDraft.model_fields["advisory_only"].annotation.__args__) == {True}


def test_evaluate_response_carries_draft_and_unknown_category_is_none() -> None:
    _lifecycle("P-WPI-3", evaluate=False)
    res = client.post(
        f"{PREFIX}/predictions/P-WPI-3/evaluate",
        params={"as_of_utc": "2026-02-03T00:00:00Z"},
        json={"matched_expectation": False, "error_category": "direction-miss"},
    )
    assert res.status_code == 200
    body = res.json()
    # existing response fields untouched
    assert body["evaluation"]["matched_expectation"] is False
    assert body["evaluation"]["error_category"] == "direction-miss"
    assert body["registry_version"] >= 1
    # additive field: the deterministic DRAFT (preregistered=False)
    draft = body["research_proposal_draft"]
    assert draft is not None
    assert draft["preregistered"] is False
    assert draft["advisory_only"] is True
    assert draft["approval_state"] == "DRAFT"
    assert draft["prediction_id"] == "P-WPI-3"
    # deterministic repeat of the endpoint derivation (idempotent re-eval)
    res2 = client.post(
        f"{PREFIX}/predictions/P-WPI-3/evaluate",
        params={"as_of_utc": "2026-02-03T00:00:00Z"},
        json={"matched_expectation": False, "error_category": "direction-miss"},
    )
    assert res2.status_code == 200
    assert res2.json()["research_proposal_draft"] == draft
    # unknown error category → honest None (no draft invented); recorded on a
    # DIFFERENT prediction (a conflicting rewrite of P-WPI-3 would be refused
    # by the append-only evaluation discipline)
    _lifecycle("P-WPI-4", evaluate=False)
    res = client.post(
        f"{PREFIX}/predictions/P-WPI-4/evaluate",
        params={"as_of_utc": "2026-02-03T00:00:00Z"},
        json={"matched_expectation": False, "error_category": "mystery-category"},
    )
    assert res.status_code == 200
    assert res.json()["research_proposal_draft"] is None
