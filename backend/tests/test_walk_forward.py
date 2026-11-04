"""W3-3C tests — POST /api/v10/strategylab/walkforward + the walk_forward engine.

Mirrors test_master_radar_wave2_api.py conventions (offline-deterministic,
frozen end_bar_index, honest 422 surfaces, trust envelope asserted not
hardcoded). Two layers are pinned:

- ENGINE (app.engines.walk_forward): the pinned window math, the pinned
  per-fold seed derivation fold_seed(i) = seed + i, the aggregation, the
  reproducibility digest, and the OOS-confirmed-once discipline via a spy
  evaluator (the test window receives EXACTLY ONE evaluation per fold, with
  the already-frozen best params, AFTER that fold's IS evaluations — and an
  absurd OOS value provably cannot change selection).
- API: valid run shape, aggregate consistency, determinism (identical bodies
  -> identical folds + digest), evaluated-count accounting, and every 422
  refusal (seed missing, per-fold budget guard, fold geometry bounds, unfit
  windows with available-vs-required named, space validation, invalid RSL-1
  source) plus hostile bodies that must never produce a 500.

The OOS-once guarantee at the API layer comes from the engine's use of the
optimizer's ``select_then_confirm`` (its API shape invokes the OOS closure
exactly once, after the winner is fixed, and the value has no code path into
ranking); the spy tests below pin that structure observably.
"""

from __future__ import annotations

import statistics

import pytest
from fastapi.testclient import TestClient

from app.engines import walk_forward as wf
from app.engines.backtest_optimizer import Objective, ParameterSpace
from app.main import create_app

END_BAR = 1000  # frozen seeded window for determinism

VALID_SOURCE = """INPUT fast = 5
RISK stop_loss_pct = 3.0, take_profit_pct = 6.0, max_position_pct = 50.0
ENTRY close > sma(close, fast)
EXIT close < sma(close, 20)
"""

# n=3, train=60, test=20 over count=300: required = 60 + 60 = 120 <= 300 (fit).
WF_BASE = {
    "source": VALID_SOURCE,
    "symbol": "FOLAD",
    "timeframe": "1D",
    "count": 300,
    "end_bar_index": END_BAR,
    "folds": {"n": 3, "train_bars": 60, "test_bars": 20},
    "space": {"grid": {"fast": [3, 5, 8]}},
    "budget": {"max_evals_per_fold": 10, "seed": 42},
}


@pytest.fixture(scope="module")
def client():
    # Same convention as test_master_radar_wave2_api.py: NO context manager
    # (the app lifespan never runs in tests) and a DISTINCT client identity
    # so this module's requests stay in their own rate-limiter bucket.
    # HYGIENE (order-dependence guard, mirrors test_ws_harden1_request_id.py):
    # env-patching modules elsewhere in the suite can leave the get_settings
    # lru_cache holding PRIVATE_MODE/AUTH_REQUIRED settings after their
    # monkeypatch teardown; clearing here makes this module immune to that
    # upstream residue without touching any other test.
    from app.core.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    get_settings.cache_clear()
    yield TestClient(app, client=("wf-w3c-test", 12347))


# ---------------------------------------------------------------------------
# Engine: pinned window math + seed derivation
# ---------------------------------------------------------------------------


def test_fold_windows_pinned_math():
    # Pinned formula: fold i -> train [i*tb, i*tb+tr), test [i*tb+tr, i*tb+tr+tb).
    assert wf.fold_windows(300, 3, 60, 20) == [
        ((0, 60), (60, 80)),
        ((20, 80), (80, 100)),
        ((40, 100), (100, 120)),
    ]
    # Exact-fit boundary (available == required) is accepted.
    assert wf.fold_windows(50, 2, 30, 10) == [((0, 30), (30, 40)), ((10, 40), (40, 50))]
    # Test windows are non-overlapping and chronological; train lengths exact.
    windows = wf.fold_windows(500, 5, 70, 25)
    test_ranges = [t for _, t in windows]
    for (s0, e0), (s1, _) in zip(test_ranges, test_ranges[1:]):
        assert e0 <= s1  # disjoint, in order
    for (train, test) in windows:
        assert train[1] - train[0] == 70 and test[1] - test[0] == 25
        assert train[1] == test[0]  # test starts exactly at train end


def test_fold_windows_unfit_message_names_both_numbers():
    with pytest.raises(ValueError) as ei:
        wf.fold_windows(49, 2, 30, 10)  # required 50 > available 49
    message = str(ei.value)
    assert "50" in message and "49" in message
    assert "required" in message and "available" in message


@pytest.mark.parametrize(
    "args",
    [(50, 0, 30, 10), (50, -1, 30, 10), (50, 2, 0, 10), (50, 2, 30, 0), (-5, 2, 30, 10)],
)
def test_fold_windows_degenerate_args_raise(args):
    with pytest.raises(ValueError):
        wf.fold_windows(*args)


def test_per_fold_seed_derivation_is_pinned():
    # PINNED (do not change): fold_seed(i) = seed + i.
    assert [wf.per_fold_seed(42, i) for i in range(4)] == [42, 43, 44, 45]
    assert wf.per_fold_seed(-7, 3) == -4


# ---------------------------------------------------------------------------
# Engine: aggregation + digest
# ---------------------------------------------------------------------------


def test_aggregate_fold_stats_values_are_consistent():
    rows = [
        {"oos_objective": 1.0, "best_params": {"a": 1.0}, "oos_eval_count": 1},
        {"oos_objective": -2.0, "best_params": {"a": 2.0}, "oos_eval_count": 1},
        {"oos_objective": 3.5, "best_params": {"a": 3.0}, "oos_eval_count": 1},
        {"oos_objective": None, "best_params": None, "oos_eval_count": 0},
    ]
    stats = wf.aggregate_fold_stats(rows, Objective.SHARPE)
    assert stats["n_folds"] == 4
    assert stats["confirmed_folds"] == 3  # the None fold never confirmed
    vals = [1.0, -2.0, 3.5]
    assert stats["oos_mean"] == pytest.approx(sum(vals) / 3, abs=1e-12)
    assert stats["oos_median"] == statistics.median(vals)
    assert stats["oos_min"] == -2.0
    assert stats["oos_max"] == 3.5
    assert stats["positive_folds"] == 2
    assert stats["objective"] == "SHARPE"
    assert stats["selection_basis"] == "IN_SAMPLE_PER_FOLD"
    assert stats["oos_evaluated_once_per_fold"] is True


def test_aggregate_fold_stats_empty_and_objective_string_form():
    stats = wf.aggregate_fold_stats([], "SHARPE")
    assert stats["n_folds"] == 0
    assert stats["oos_mean"] is None and stats["oos_median"] is None
    assert stats["oos_min"] is None and stats["oos_max"] is None
    assert stats["positive_folds"] == 0
    assert stats["selection_basis"] == "IN_SAMPLE_PER_FOLD"
    assert stats["objective"] == "SHARPE"


def test_reproducibility_digest_stable_and_sensitive():
    body = {"symbol": "FOLAD", "budget": {"seed": 42}}
    rows = [{"fold_index": 0, "oos_objective": 1.5}]
    d1 = wf.reproducibility_digest(body, rows)
    d2 = wf.reproducibility_digest(body, list(rows))
    assert d1 == d2
    assert len(d1) == 64
    assert wf.reproducibility_digest(body, [{"fold_index": 0, "oos_objective": 1.6}]) != d1
    assert wf.reproducibility_digest({"symbol": "FOLAD", "budget": {"seed": 43}}, rows) != d1


# ---------------------------------------------------------------------------
# Engine: OOS-confirmed-once discipline (spy evaluator — observable, no
# monkeypatching of any other module needed)
# ---------------------------------------------------------------------------


def _spy_result(test_window_value: float):
    bars = [{"ts": 1000 + i} for i in range(120)]  # engine never inspects content
    calls = []

    def spy(params, window):
        calls.append({"params": dict(params), "start": window[0]["ts"], "len": len(window)})
        if len(window) == 10:  # every fold's test window (train windows are 30)
            return test_window_value
        return float(params["fast"]) + len(window) * 1e-9

    result = wf.run_walk_forward(
        bars,
        n=3,
        train_bars=30,
        test_bars=10,
        space=ParameterSpace(grid={"fast": [1.0, 2.0, 3.0]}),
        objective=Objective.SHARPE,
        seed=5,
        max_evals_per_fold=10,
        evaluate=spy,
        digest_body={"endpoint": "walkforward", "seed": 5},
    )
    return result, calls


def test_run_walk_forward_oos_window_evaluated_exactly_once_after_selection():
    result, calls = _spy_result(test_window_value=0.0)
    assert [f["fold_index"] for f in result.folds] == [0, 1, 2]
    for fold in result.folds:
        i = fold["fold_index"]
        train_start, test_start = 1000 + i * 10, 1000 + i * 10 + 30
        train_calls = [c for c in calls if c["start"] == train_start and c["len"] == 30]
        test_calls = [c for c in calls if c["start"] == test_start and c["len"] == 10]
        # IS selection: 3 grid trials (lexicographic) + 1 select_then_confirm
        # re-evaluation of the frozen winner — all on the TRAIN window only.
        assert [c["params"]["fast"] for c in train_calls[:3]] == [1.0, 2.0, 3.0]
        assert len(train_calls) == 4
        assert train_calls[3]["params"] == fold["best_params"]
        # OOS confirmation: EXACTLY ONE test-window call, with the frozen
        # best params, AFTER every train-window call of this fold.
        assert len(test_calls) == 1
        assert test_calls[0]["params"] == fold["best_params"]
        assert calls.index(test_calls[0]) > calls.index(train_calls[3])
        # Accounting: evaluated_count counts IS selection trials only and
        # never includes the single OOS evaluation.
        assert fold["evaluated_count"] == 3
        assert fold["oos_eval_count"] == 1
        assert fold["oos_evaluated_once"] is True
        assert fold["fold_seed"] == 5 + i  # pinned derivation echoed per fold
    assert result.aggregate["oos_evaluated_once_per_fold"] is True
    assert result.aggregate["selection_basis"] == "IN_SAMPLE_PER_FOLD"


def test_run_walk_forward_oos_value_cannot_influence_selection():
    # The strongest structural pin: an absurd OOS value (great or terrible)
    # provably never changes any fold's selection outcome.
    bad_oos, bad_calls = _spy_result(test_window_value=-1_000_000.0)
    good_oos, good_calls = _spy_result(test_window_value=+1_000_000.0)
    for fold_bad, fold_good in zip(bad_oos.folds, good_oos.folds):
        assert fold_bad["best_params"] == fold_good["best_params"]
        assert fold_bad["is_objective"] == fold_good["is_objective"]
        assert fold_bad["evaluated_count"] == fold_good["evaluated_count"]
    assert len(bad_calls) == len(good_calls)


def test_run_walk_forward_all_refused_is_recorded_not_silent():
    bars = [{"ts": i} for i in range(80)]

    def always_refused(params, window):
        raise ValueError("objective_sharpe_unavailable (no trades / degenerate run)")

    result = wf.run_walk_forward(
        bars,
        n=2,
        train_bars=30,
        test_bars=10,
        space=ParameterSpace(grid={"fast": [1.0, 2.0, 3.0]}),
        objective=Objective.SHARPE,
        seed=1,
        max_evals_per_fold=10,
        evaluate=always_refused,
        digest_body={"seed": 1},
    )
    assert len(result.folds) == 2
    for fold in result.folds:
        assert fold["best_params"] is None
        assert fold["is_objective"] is None
        assert fold["oos_objective"] is None
        assert fold["evaluated_count"] == 3  # refusals recorded, never silent
        assert fold["oos_eval_count"] == 0  # test window never touched
        assert "no evaluable candidates" in fold["note"]
    agg = result.aggregate
    assert agg["confirmed_folds"] == 0
    assert agg["oos_mean"] is None and agg["positive_folds"] == 0
    assert "n_trials=0" in result.bonferroni_note


def test_run_walk_forward_digest_tracks_seed_and_folds():
    bars = [{"ts": i} for i in range(80)]
    kwargs = dict(
        n=2,
        train_bars=30,
        test_bars=10,
        space=ParameterSpace(grid={"fast": [1.0]}),
        objective=Objective.SHARPE,
        max_evals_per_fold=10,
        evaluate=lambda params, window: float(params["fast"]),
    )
    r1 = wf.run_walk_forward(bars, seed=7, digest_body={"seed": 7}, **kwargs)
    r2 = wf.run_walk_forward(bars, seed=7, digest_body={"seed": 7}, **kwargs)
    r3 = wf.run_walk_forward(bars, seed=8, digest_body={"seed": 8}, **kwargs)
    assert r1.reproducibility_digest == r2.reproducibility_digest
    assert r1.reproducibility_digest != r3.reproducibility_digest
    assert [f["fold_seed"] for f in r1.folds] == [7, 8]
    assert [f["fold_seed"] for f in r3.folds] == [8, 9]


# ---------------------------------------------------------------------------
# API: POST /api/v10/strategylab/walkforward
# ---------------------------------------------------------------------------


def test_walkforward_happy_path_full_shape(client):
    r = client.post("/api/v10/strategylab/walkforward", json=WF_BASE)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    folds = body["folds"]
    assert [f["fold_index"] for f in folds] == [0, 1, 2]  # n rows, in order
    for i, fold in enumerate(folds):
        assert fold["train"] == {"start_index": i * 20, "end_index": i * 20 + 60}
        assert fold["test"] == {"start_index": i * 20 + 60, "end_index": i * 20 + 80}
        assert fold["best_params"] is not None and "fast" in fold["best_params"]
        assert isinstance(fold["is_objective"], float)
        assert isinstance(fold["oos_objective"], float)
        assert fold["fold_seed"] == 42 + i  # pinned derivation
        assert fold["evaluated_count"] == 3
        assert fold["constraint_skips"] == 0
    aggregate = body["aggregate"]
    oos_vals = [f["oos_objective"] for f in folds]
    assert aggregate["n_folds"] == 3
    assert aggregate["objective"] == "SHARPE"
    assert aggregate["oos_mean"] == pytest.approx(sum(oos_vals) / len(oos_vals), abs=1e-12)
    assert aggregate["oos_median"] == statistics.median(oos_vals)
    assert aggregate["oos_min"] == min(oos_vals)
    assert aggregate["oos_max"] == max(oos_vals)
    assert aggregate["positive_folds"] == sum(1 for v in oos_vals if v > 0)
    assert aggregate["selection_basis"] == "IN_SAMPLE_PER_FOLD"
    assert aggregate["oos_evaluated_once_per_fold"] is True
    assert "multiple_testing" in body["bonferroni_note"]
    assert "n_trials=9" in body["bonferroni_note"]  # 3 folds x 3 evaluable trials
    assert body["reproducibility_digest"]
    assert body["notes"] and body["synthetic_note"]
    assert body["search_method"] == "grid"
    assert body["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    assert body["trust_envelope"]["data_trust"]["is_live"] is False
    assert body["budget_echo"]["seed"] == 42 and body["budget_echo"]["limit"] == 100


def test_walkforward_fold_windows_match_pinned_formula(client):
    body = {
        **WF_BASE,
        "folds": {"n": 2, "train_bars": 90, "test_bars": 30},
        "budget": {"max_evals_per_fold": 10, "seed": 7},
    }
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 200
    folds = r.json()["folds"]
    assert [f["fold_index"] for f in folds] == [0, 1]
    assert folds[0]["train"] == {"start_index": 0, "end_index": 90}
    assert folds[0]["test"] == {"start_index": 90, "end_index": 120}
    assert folds[1]["train"] == {"start_index": 30, "end_index": 120}
    assert folds[1]["test"] == {"start_index": 120, "end_index": 150}
    assert r.json()["bars_used"] == 300


def test_walkforward_determinism_identical_bodies(client):
    r1 = client.post("/api/v10/strategylab/walkforward", json=WF_BASE)
    r2 = client.post("/api/v10/strategylab/walkforward", json=WF_BASE)
    assert r1.status_code == 200 and r2.status_code == 200
    b1, b2 = r1.json(), r2.json()
    assert b1["folds"] == b2["folds"]
    assert b1["aggregate"] == b2["aggregate"]
    assert b1["reproducibility_digest"] == b2["reproducibility_digest"]
    assert b1["bonferroni_note"] == b2["bonferroni_note"]


def test_walkforward_oos_once_accounting_observable(client):
    # API-level observable of the structural guarantee: the fold rows carry
    # the frozen best_params, the IS trial count excludes the single OOS
    # confirmation, and the OOS flag is pinned per fold. The guarantee itself
    # comes from the engine's select_then_confirm usage (pinned by the spy
    # tests above at the engine layer).
    r = client.post("/api/v10/strategylab/walkforward", json=WF_BASE)
    assert r.status_code == 200
    for fold in r.json()["folds"]:
        assert fold["best_params"] is not None
        assert fold["oos_eval_count"] == 1
        assert fold["oos_evaluated_once"] is True
        assert fold["evaluated_count"] == 3  # IS trials only (3 grid points)
        assert "in-sample" in fold["note"]


def test_walkforward_missing_seed_422(client):
    body = {**WF_BASE, "budget": {"max_evals_per_fold": 10}}  # seed REQUIRED
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 422


def test_walkforward_max_evals_per_fold_zero_422(client):
    body = {**WF_BASE, "budget": {"max_evals_per_fold": 0, "seed": 42}}
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 422


def test_walkforward_max_evals_per_fold_101_422_honest_note(client):
    body = {**WF_BASE, "budget": {"max_evals_per_fold": 101, "seed": 42}}
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "BUDGET_LIMIT"
    assert "۱۰۰" in detail["message_fa"]
    assert "max_evals_per_fold must be <= 100" in detail["message_en"]
    assert detail["limit"] == 100 and detail["requested"] == 101


@pytest.mark.parametrize("n", [1, 13])
def test_walkforward_folds_n_bounds_422(client, n):
    body = {**WF_BASE, "folds": {"n": n, "train_bars": 60, "test_bars": 20}}
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 422


@pytest.mark.parametrize(
    "folds",
    [
        {"n": 3, "train_bars": 29, "test_bars": 20},
        {"n": 3, "train_bars": 60, "test_bars": 9},
    ],
)
def test_walkforward_fold_geometry_bounds_422(client, folds):
    body = {**WF_BASE, "folds": folds}
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 422


def test_walkforward_unfit_windows_422_names_available_and_required(client):
    # required = 200 + 3*100 = 500 > available 300 -> honest 422 with BOTH numbers.
    body = {**WF_BASE, "folds": {"n": 3, "train_bars": 200, "test_bars": 100}}
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "UNFIT_FOLD_WINDOWS"
    assert "500" in detail["message_en"] and "300" in detail["message_en"]
    assert "۵۰۰" in detail["message_fa"] and "۳۰۰" in detail["message_fa"]
    assert detail["available"] == 300 and detail["required"] == 500


def test_walkforward_empty_grid_space_422(client):
    r = client.post("/api/v10/strategylab/walkforward", json={**WF_BASE, "space": {}})
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "GRID_REQUIRED"


def test_walkforward_bounds_only_space_422(client):
    body = {**WF_BASE, "space": {"bounds": {"fast": [2.0, 12.0]}}}
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "BOUNDS_UNSUPPORTED"


def test_walkforward_unknown_space_param_422(client):
    body = {**WF_BASE, "space": {"grid": {"not_declared": [1, 2]}}}
    r = client.post("/api/v10/strategylab/walkforward", json=body)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "UNKNOWN_OPTIMIZATION_PARAM"
    assert "fast" in detail["declared_inputs"]


def test_walkforward_invalid_source_422_dsl_error(client):
    bad_source = "ENTRY close >"  # compile failure -> 422 exactly like /backtest
    r = client.post("/api/v10/strategylab/walkforward", json={**WF_BASE, "source": bad_source})
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "DSL_ERROR"


def test_walkforward_oos_objective_rejected_422(client):
    r = client.post(
        "/api/v10/strategylab/walkforward", json={**WF_BASE, "objective": "OOS_SHARPE"}
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "INVALID_OBJECTIVE"


@pytest.mark.parametrize(
    "overrides",
    [
        {"space": ["not", "a", "dict"]},  # space as list
        {"budget": ["not", "a", "dict"]},  # budget as list
        {"folds": "nope"},  # folds as string
        {"count": 10**9},  # huge count
        {"timeframe": "7D"},  # invalid timeframe enum
        {"unexpected_extra": {"x": 1}},  # unknown extra field (ignored, not 500)
    ],
)
def test_walkforward_hostile_bodies_never_500(client, overrides):
    r = client.post("/api/v10/strategylab/walkforward", json={**WF_BASE, **overrides})
    assert r.status_code != 500
