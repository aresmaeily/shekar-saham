"""Directive §D4 tests for the deterministic parameter-search engine.

Covers: grid enumeration order, constraint-skip accounting, budget and
cancellation honesty, injected-clock time budget, seeded reproducibility,
evolutionary determinism/bounds, IS-only selection with one-shot OOS
confirmation, Bonferroni note, param-hash/digest stability, journal resume
equality, and the walk-forward integration (mean OOS sharpe, OOS objective
enforcement). All offline and deterministic; the only "clock" is injected.
"""

from __future__ import annotations

import pytest

from app.engines.backtest_optimizer import (
    EvaluationRecord,
    Objective,
    OptimizationBudget,
    OptimizationJournal,
    ParameterSpace,
    evolutionary_search,
    grid_search,
    optimize_with_walk_forward,
    param_hash,
    randomized_search,
    select_then_confirm,
)
from app.engines.backtest_product import (
    BacktestRunConfig,
    DataPolicy,
    WalkForwardProductConfig,
)
from app.engines.execution_model import ExecutionModelConfig
from tests.test_backtest_product import Momentum, flat_bars

DAY = 86_400
T0 = 1_704_067_200


def budget(seed: int, max_evaluations: int = 200, time_budget_seconds: float | None = None):
    return OptimizationBudget(
        max_evaluations=max_evaluations, seed=seed, time_budget_seconds=time_budget_seconds
    )


# ---------------------------------------------------------------------------
# Grid search
# ---------------------------------------------------------------------------


def test_grid_enumeration_is_lexicographic_deterministic():
    space = ParameterSpace(grid={"b": [1, 2], "a": [10, 20]})
    seen: list[dict] = []
    result = grid_search(space, lambda p: seen.append(dict(p)) or float(p["a"]) + p["b"], budget(1))
    assert [e.params for e in result.evaluations] == [
        {"a": 10, "b": 1},
        {"a": 10, "b": 2},
        {"a": 20, "b": 1},
        {"a": 20, "b": 2},
    ]
    assert [e.params for e in result.ranked_top] == [
        {"a": 20, "b": 2},
        {"a": 20, "b": 1},
        {"a": 10, "b": 2},
        {"a": 10, "b": 1},
    ]
    assert result.best is not None and result.best.params == {"a": 20, "b": 2}
    assert result.cancelled is False and result.budget_exhausted is False


def test_constraint_violations_skipped_and_counted():
    space = ParameterSpace(
        grid={"a": [10, 20], "b": [1, 2]},
        constraints=["documented only: a=20 requires b=2"],
        dependency_rules=(lambda p: not (p["a"] == 20 and p["b"] == 1),),
    )
    result = grid_search(space, lambda p: float(p["a"]) * p["b"], budget(1))
    assert result.n_constraint_skips == 1
    assert len(result.evaluations) == 3
    assert all(e.params != {"a": 20, "b": 1} for e in result.evaluations)
    assert result.best is not None and result.best.params == {"a": 20, "b": 2}


def test_budget_exhaustion_flags():
    space = ParameterSpace(grid={"a": [1, 2, 3, 4, 5], "b": [1, 2, 3, 4, 5]})
    result = grid_search(space, lambda p: 1.0, budget(1, max_evaluations=7))
    assert len(result.evaluations) == 7
    assert result.budget_exhausted is True
    assert result.cancelled is False


def test_cancellation_midrun_flags():
    space = ParameterSpace(grid={"a": [1, 2, 3, 4, 5], "b": [1, 2, 3, 4, 5]})
    calls = {"n": 0}

    def objective(p):
        calls["n"] += 1
        return 1.0

    def cancel():
        return calls["n"] >= 3

    result = grid_search(space, objective, budget(1, max_evaluations=25), cancel=cancel)
    assert len(result.evaluations) == 3
    assert result.cancelled is True
    assert result.budget_exhausted is False


def test_time_budget_with_injected_fake_clock():
    space = ParameterSpace(grid={"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    ticks = iter([0.0, 0.0, 0.0, 5.0])

    def clock():
        try:
            return next(ticks)
        except StopIteration:
            return 5.0

    result = grid_search(
        space, lambda p: 1.0, budget(1, max_evaluations=100, time_budget_seconds=2.0), clock=clock
    )
    # start=0; candidate 1,2 checked at 0.0; candidate 3 checked at 5.0 -> stop
    assert len(result.evaluations) == 2
    assert result.budget_exhausted is True
    assert result.cancelled is False


def test_empty_grid_yields_empty_result_with_zero_trials_note():
    space = ParameterSpace(grid={}, constraints=["nothing"])
    result = grid_search(space, lambda p: 1.0, budget(1))
    assert result.evaluations == []
    assert result.best is None
    assert "n_trials=0" in result.corrected_alpha_note


# ---------------------------------------------------------------------------
# Journal resume
# ---------------------------------------------------------------------------


def test_journal_resume_reproduces_uninterrupted_evaluation_set():
    space = ParameterSpace(grid={"a": [1, 2, 3, 4], "b": [1, 2, 3, 4]})

    def objective(p):
        return float(p["a"]) * 10.0 + p["b"]

    full = grid_search(space, objective, budget(1, max_evaluations=16))
    assert len(full.evaluations) == 16

    calls = {"n": 0}

    def objective_counting(p):
        calls["n"] += 1
        return objective(p)

    def cancel_after_six():
        return calls["n"] >= 6

    journal = OptimizationJournal()
    interrupted = grid_search(
        space, objective_counting, budget(1, max_evaluations=16), cancel=cancel_after_six,
        journal=journal,
    )
    assert interrupted.cancelled is True
    assert len(journal.records) == 6

    resumed = journal.resume(grid_search, space=space, objective_fn=objective, budget=budget(1, max_evaluations=16))
    assert resumed.cancelled is False
    assert resumed.budget_exhausted is True
    assert [e.param_hash for e in resumed.evaluations] == [e.param_hash for e in full.evaluations]
    assert {e.param_hash: e.objective_value for e in resumed.evaluations} == {
        e.param_hash: e.objective_value for e in full.evaluations
    }
    assert calls["n"] == 6  # interrupted run's evals; resumed run replayed journal hits,
    # and the resumed objective (non-counting) was the only function called afresh


def test_journal_is_append_only_first_record_wins():
    journal = OptimizationJournal()
    first = EvaluationRecord(params={"a": 1}, param_hash="h", objective_value=1.0)
    second = EvaluationRecord(params={"a": 1}, param_hash="h", objective_value=99.0)
    journal.observe(first)
    journal.observe(second)
    assert journal.get("h") is first
    assert journal.records == [first]
    assert journal.has("h") is True and journal.has("nope") is False


# ---------------------------------------------------------------------------
# Randomized search
# ---------------------------------------------------------------------------


def test_randomized_same_seed_reproducible():
    space = ParameterSpace(bounds={"x": (0.0, 1.0), "y": (-5.0, 5.0)})

    def objective(p):
        return p["x"] * 2.0 - abs(p["y"])

    r1 = randomized_search(space, objective, budget(123, max_evaluations=15))
    r2 = randomized_search(space, objective, budget(123, max_evaluations=15))
    assert [e.params for e in r1.evaluations] == [e.params for e in r2.evaluations]
    assert r1.reproducibility_digest == r2.reproducibility_digest
    assert r1.best is not None and r2.best is not None
    assert r1.best.param_hash == r2.best.param_hash


def test_randomized_different_seed_different_stream():
    space = ParameterSpace(bounds={"x": (0.0, 1.0)})
    r1 = randomized_search(space, lambda p: p["x"], budget(1, max_evaluations=5))
    r2 = randomized_search(space, lambda p: p["x"], budget(2, max_evaluations=5))
    assert [e.params for e in r1.evaluations] != [e.params for e in r2.evaluations]


def test_randomized_respects_bounds_and_requires_them():
    space = ParameterSpace(bounds={"x": (0.0, 1.0), "y": (-5.0, 5.0)})
    result = randomized_search(space, lambda p: 1.0, budget(9, max_evaluations=12))
    assert len(result.evaluations) == 12
    for e in result.evaluations:
        assert set(e.params) == {"x", "y"}
        assert 0.0 <= e.params["x"] <= 1.0
        assert -5.0 <= e.params["y"] <= 5.0
    with pytest.raises(ValueError, match="requires_bounds"):
        randomized_search(ParameterSpace(), lambda p: 1.0, budget(9))


# ---------------------------------------------------------------------------
# Evolutionary search
# ---------------------------------------------------------------------------


def test_evolutionary_deterministic_bounded_and_within_bounds():
    space = ParameterSpace(bounds={"x": (0.0, 10.0), "y": (-10.0, 10.0)})

    def objective(p):
        return -(abs(p["x"] - 7.0) + abs(p["y"] + 3.0))

    kwargs = dict(
        population_size=8, generations=5, tournament_k=3, elitism=1,
    )
    r1 = evolutionary_search(space, objective, budget(42, max_evaluations=30), **kwargs)
    r2 = evolutionary_search(space, objective, budget(42, max_evaluations=30), **kwargs)
    r3 = evolutionary_search(space, objective, budget(43, max_evaluations=30), **kwargs)
    assert [e.params for e in r1.evaluations] == [e.params for e in r2.evaluations]
    assert r1.reproducibility_digest == r2.reproducibility_digest
    assert r1.reproducibility_digest != r3.reproducibility_digest
    assert len(r1.evaluations) == 30
    assert r1.budget_exhausted is True
    for e in r1.evaluations:
        assert 0.0 <= e.params["x"] <= 10.0
        assert -10.0 <= e.params["y"] <= 10.0
    assert r1.best is not None and r1.best.objective_value is not None


def test_evolutionary_requires_bounds():
    with pytest.raises(ValueError, match="requires_bounds"):
        evolutionary_search(ParameterSpace(), lambda p: 1.0, budget(1))


# ---------------------------------------------------------------------------
# Selection honesty (§D4: IS-only selection, one-shot OOS confirmation)
# ---------------------------------------------------------------------------


def _search_result_for_selection():
    space = ParameterSpace(grid={"a": [10, 20], "b": [1, 2]})
    return grid_search(space, lambda p: float(p["a"]) + p["b"], budget(1))


def test_selection_basis_always_in_sample():
    result = _search_result_for_selection()
    confirmation = select_then_confirm(
        result,
        objective_fn_is=lambda p: float(p["a"]) + p["b"],
        objective_fn_oos=lambda p: 0.0,
    )
    assert confirmation.selection_basis == "IN_SAMPLE"
    assert confirmation.params == result.best.params
    assert confirmation.param_hash == result.best.param_hash
    assert confirmation.oos_confirmation is not None
    assert confirmation.oos_confirmation.evaluated_once is True
    assert "IN_SAMPLE" in confirmation.note or "in-sample" in confirmation.note


def test_oos_function_never_influences_ranking():
    result = _search_result_for_selection()
    oos_calls = {"n": 0}

    def absurd_oos(p):
        oos_calls["n"] += 1
        return -1_000_000.0  # absurd for ALL params: could never help ranking

    confirmation = select_then_confirm(
        result,
        objective_fn_is=lambda p: float(p["a"]) + p["b"],
        objective_fn_oos=absurd_oos,
    )
    assert confirmation.params == {"a": 20, "b": 2}  # IS ranking unchanged
    assert oos_calls["n"] == 1  # evaluated exactly once, after selection
    assert confirmation.oos_confirmation is not None
    assert confirmation.oos_confirmation.objective_value == -1_000_000.0


def test_selection_with_no_evaluable_candidates():
    space = ParameterSpace(grid={"a": [1]})
    result = grid_search(space, lambda p: (_ for _ in ()).throw(RuntimeError("boom")), budget(1))
    assert result.evaluations[0].is_refused is True
    assert "boom" in (result.evaluations[0].refuse_reason or "")
    confirmation = select_then_confirm(result, lambda p: 1.0, lambda p: 1.0)
    assert confirmation.params is None
    assert confirmation.selection_basis == "IN_SAMPLE"


# ---------------------------------------------------------------------------
# Multiple-testing note, hashes, digests
# ---------------------------------------------------------------------------


def test_bonferroni_note_records_trial_count():
    space = ParameterSpace(grid={"a": [1, 2, 3], "b": [1, 2]})
    result = grid_search(space, lambda p: float(p["a"]) + p["b"], budget(1))
    assert "n_trials=6" in result.corrected_alpha_note
    assert "alpha/6" in result.corrected_alpha_note
    assert "p-value" not in result.corrected_alpha_note.lower()


def test_param_hash_stability():
    assert param_hash({"a": 1, "b": 2}) == param_hash({"b": 2, "a": 1})
    assert param_hash({"a": 1, "b": 2}) != param_hash({"a": 2, "b": 1})
    assert param_hash({"a": 1}) != param_hash({"a": 1.0})  # int vs float distinct
    assert param_hash({"a": 1.5}) == param_hash({"a": 1.5})


def test_result_digest_stability_and_sensitivity():
    space = ParameterSpace(grid={"a": [1, 2]})
    r1 = grid_search(space, lambda p: float(p["a"]), budget(5))
    r2 = grid_search(space, lambda p: float(p["a"]), budget(5))
    r3 = grid_search(space, lambda p: float(p["a"]) + 1.0, budget(5))
    assert r1.reproducibility_digest == r2.reproducibility_digest
    assert r1.reproducibility_digest != r3.reproducibility_digest
    assert r1.budget_echo == r2.budget_echo
    assert r1.budget_echo["seed"] == 5


# ---------------------------------------------------------------------------
# Walk-forward integration
# ---------------------------------------------------------------------------


def test_optimize_with_walk_forward_mean_oos_sharpe():
    bars = flat_bars([100 + i * 0.5 for i in range(120)])
    cfg = BacktestRunConfig(
        run_id="wf-opt",
        execution=ExecutionModelConfig(),
        data_policy=DataPolicy(min_bars=5),
    )
    wf_cfg = WalkForwardProductConfig(n_splits=2, anchored=True, min_train_bars=30, min_test_bars=30)
    space = ParameterSpace(grid={"p": [1, 2]})

    def factory(params: dict):
        return Momentum(10, 10 + int(params.get("p", 1)) * 10)

    result = optimize_with_walk_forward(
        space, factory, {"S": bars}, cfg, wf_cfg, budget(7, max_evaluations=2), Objective.OOS_SHARPE
    )
    assert result.objective == "OOS_SHARPE"
    assert result.strategy_id == "momentum"
    assert len(result.evaluations) == 2
    assert all(e.objective_value is not None for e in result.evaluations)
    assert result.best is not None
    assert "n_trials=2" in result.corrected_alpha_note


def test_optimize_with_walk_forward_enforces_oos_objective():
    space = ParameterSpace(grid={"p": [1]})
    with pytest.raises(ValueError, match="OOS_SHARPE"):
        optimize_with_walk_forward(
            space,
            lambda p: Momentum(5, 10),
            {"S": flat_bars([100.0] * 60)},
            BacktestRunConfig(run_id="x", execution=ExecutionModelConfig(), data_policy=DataPolicy(min_bars=5)),
            WalkForwardProductConfig(n_splits=2, anchored=True, min_train_bars=10, min_test_bars=10),
            budget(1),
            Objective.SHARPE,
        )


def test_optimize_with_walk_forward_refused_evaluation_recorded():
    # A space whose candidate produces no OOS windows -> refused, not silent.
    bars = flat_bars([100.0] * 60)  # flat market: sharpe undefined -> refused
    cfg = BacktestRunConfig(
        run_id="wf-refused", execution=ExecutionModelConfig(), data_policy=DataPolicy(min_bars=5)
    )
    wf_cfg = WalkForwardProductConfig(n_splits=2, anchored=True, min_train_bars=10, min_test_bars=10)
    space = ParameterSpace(grid={"p": [1]})
    result = optimize_with_walk_forward(
        space, lambda p: Momentum(5, 10), {"S": bars}, cfg, wf_cfg,
        budget(3, max_evaluations=1), Objective.OOS_SHARPE,
    )
    assert len(result.evaluations) == 1
    assert result.evaluations[0].is_refused is True
    assert result.best is None
