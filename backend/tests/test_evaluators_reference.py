"""AI-4 deterministic reference evaluators — acceptance tests.

Sources: 02:87-90 (sandbox -> deterministic evaluation -> lifecycle),
02:158-159 ("when a suitable deterministic evaluator exists"; candidates
until gates passed), D-AI-19 (deterministic financial truth; no LLM),
dependency matrix §AI-4. Synthetic tests only — no network, no LLM, no
I/O, no clock reads.
"""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from app.engines.evaluators_reference import (
    REFERENCE_EVALUATOR_VERSION,
    evaluate_filter_dsl,
    evaluate_pass_rate,
    evaluate_signal_pairs,
    reference_evaluator_registry,
)
from app.domain.governed_generation import (
    DatasetOrigin,
    DeterministicServiceClass,
    EvaluationMetric,
    EvaluatorRegistry,
)

ROWS = [
    {"pl": 10.5, "buy_power": 3.0, "volume_ratio": 2.5},
    {"pl": 9.8, "buy_power": 1.2, "volume_ratio": 1.1},
    {"pl": 10.1, "buy_power": 0.4, "volume_ratio": 0.8},
]


# ---------------------------------------------------------------------------
# Registry factory (canonical bindings)
# ---------------------------------------------------------------------------


def test_reference_registry_bindings() -> None:
    registry: EvaluatorRegistry = reference_evaluator_registry()
    ids = [b.evaluator_id for b in registry.bindings]
    assert ids == [
        "reference.filter_dsl",
        "reference.signal_pairs",
        "reference.pass_rate",
    ]
    assert all(b.service_class == "DETERMINISTIC" for b in registry.bindings)
    assert set(get_args(DeterministicServiceClass)) == {"DETERMINISTIC"}
    assert all(
        b.evaluator_version == REFERENCE_EVALUATOR_VERSION for b in registry.bindings
    )


def test_registry_resolution_is_deterministic_and_honest_about_gaps() -> None:
    registry = reference_evaluator_registry()
    assert registry.resolve("FILTER").evaluator_id == "reference.filter_dsl"
    assert registry.resolve("STRATEGY_SPEC").evaluator_id == "reference.signal_pairs"
    assert registry.resolve("SCORING_RULE").evaluator_id == "reference.pass_rate"
    # Kinds with NO reference evaluator resolve to None — an honest gap,
    # never a placeholder evaluator.
    assert registry.resolve("SOFTWARE_CHANGE_PROPOSAL") is None
    assert registry.resolve("FUNDAMENTAL_FEATURE") is None


def test_registry_dataset_origins_closed_to_pre_g2_class() -> None:
    registry = reference_evaluator_registry()
    for binding in registry.bindings:
        assert set(binding.accepted_dataset_origins) <= set(get_args(DatasetOrigin))
        assert binding.accepted_dataset_origins == ("SYNTHETIC", "PAPER")
        assert "LIVE" not in binding.accepted_dataset_origins


# ---------------------------------------------------------------------------
# evaluate_filter_dsl (public safe evaluator of filter_dsl)
# ---------------------------------------------------------------------------


def test_filter_dsl_happy_path_exact_hit_rate() -> None:
    outcome = evaluate_filter_dsl("buy_power >= 2", ROWS)
    assert outcome.accepted is True
    assert outcome.refusal_code is None
    assert outcome.evaluated_rows == 3
    assert outcome.matched_rows == 1
    assert outcome.hit_rate == 1 / 3  # 1 matched of 3, exact rational 1/3
    names = {m.name for m in outcome.metrics}
    assert {"hit_rate", "matched_rows", "evaluated_rows"} <= names


def test_filter_dsl_third_exact_ratio() -> None:
    outcome = evaluate_filter_dsl("volume_ratio >= 2", ROWS)
    assert outcome.matched_rows == 1
    # exact rational 1/3 -> nearest double, deterministic
    assert outcome.hit_rate == 1 / 3
    assert outcome.hit_rate == 0.3333333333333333


def test_filter_dsl_deterministic_identical_records() -> None:
    first = evaluate_filter_dsl("buy_power >= 2 and volume_ratio >= 2", ROWS)
    second = evaluate_filter_dsl("buy_power >= 2 and volume_ratio >= 2", ROWS)
    assert first == second
    assert first.metrics == second.metrics


def test_filter_dsl_malformed_surfaced_honestly() -> None:
    # filter_dsl's safety layer refuses the expression; the evaluator must
    # surface that refusal (accepted=False + stable code), not swallow it
    # and not convert it into a metric.
    outcome = evaluate_filter_dsl('__import__("os").system("ls")', ROWS)
    assert outcome.accepted is False
    assert outcome.refusal_code == "filter_dsl_refused"
    assert outcome.refusal_detail  # the DSL layer's message is preserved
    assert outcome.metrics == ()
    assert outcome.hit_rate is None


def test_filter_dsl_unknown_field_refused() -> None:
    outcome = evaluate_filter_dsl("no_such_field > 1", ROWS)
    assert outcome.accepted is False
    assert outcome.refusal_code == "filter_dsl_refused"


def test_filter_dsl_empty_row_set_refused() -> None:
    with pytest.raises(ValueError, match="empty_row_set"):
        evaluate_filter_dsl("buy_power >= 2", [])


# ---------------------------------------------------------------------------
# evaluate_signal_pairs (exact arithmetic)
# ---------------------------------------------------------------------------


def test_signal_pairs_hand_computed() -> None:
    # hit_rate = 2/3; mean_entered = (0.10 + (-0.02))/2 = 0.04 exactly;
    # mean_flat = 0.01; return_spread = 0.04 - 0.01 = 0.03 exactly.
    outcome = evaluate_signal_pairs([(True, 0.10), (True, -0.02), (False, 0.01)])
    assert outcome.accepted is True
    assert (outcome.pair_count, outcome.entered_count) == (3, 2)
    values = {m.name: m.value for m in outcome.metrics}
    assert values["hit_rate"] == 0.6666666666666666
    assert values["mean_return_when_entered"] == 0.04
    assert values["mean_return_when_flat"] == 0.01
    assert values["return_spread"] == 0.03


def test_signal_pairs_one_sided_metrics_omitted_honestly() -> None:
    outcome = evaluate_signal_pairs([(True, 0.05)])
    names = {m.name for m in outcome.metrics}
    assert "hit_rate" in names and "mean_return_when_entered" in names
    assert "mean_return_when_flat" not in names
    assert "return_spread" not in names  # nothing invented for absent side


def test_signal_pairs_refusals() -> None:
    with pytest.raises(ValueError, match="empty_pairs"):
        evaluate_signal_pairs([])
    with pytest.raises(ValueError, match="entered_must_be_boolean"):
        evaluate_signal_pairs([(1, 0.1)])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="return_must_be_finite"):
        evaluate_signal_pairs([(True, float("nan"))])
    with pytest.raises(ValueError, match="return_must_be_finite"):
        evaluate_signal_pairs([(True, float("inf"))])


def test_signal_pairs_deterministic() -> None:
    pairs = [(True, 0.10), (True, -0.02), (False, 0.01)]
    assert evaluate_signal_pairs(pairs) == evaluate_signal_pairs(pairs)


# ---------------------------------------------------------------------------
# evaluate_pass_rate
# ---------------------------------------------------------------------------


def test_pass_rate_exact_and_deterministic() -> None:
    outcome = evaluate_pass_rate(3, 4)
    values = {m.name: m.value for m in outcome.metrics}
    assert values["pass_rate"] == 0.75
    assert evaluate_pass_rate(3, 4) == evaluate_pass_rate(3, 4)


def test_pass_rate_refusals() -> None:
    with pytest.raises(ValueError, match="total_must_be_positive"):
        evaluate_pass_rate(0, 0)
    with pytest.raises(ValueError, match="passed_out_of_range"):
        evaluate_pass_rate(5, 4)
    with pytest.raises(ValueError, match="passed_out_of_range"):
        evaluate_pass_rate(-1, 4)


# ---------------------------------------------------------------------------
# Canonical metric channel discipline
# ---------------------------------------------------------------------------


def test_metrics_are_canonical_evaluation_metric_records() -> None:
    outcome = evaluate_pass_rate(2, 4)
    for metric in outcome.metrics:
        assert isinstance(metric, EvaluationMetric)
    with pytest.raises(ValidationError):
        EvaluationMetric(name="Not_Snake_Case", value=1.0)
    with pytest.raises(ValidationError):
        EvaluationMetric(name="ok_name", value=float("nan"))
