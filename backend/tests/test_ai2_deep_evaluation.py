"""WAVE-B (WP-B) service-level battery for the AI-2 deep-evaluation block.

Module under test: ``app/services/ai2_deep_evaluation.py`` (the bounded
deterministic MVRL deep-evaluation composition) as wired ADDITIVELY into the
governed generation pipeline ``app/services/ai2_generation.py`` (stage 5.5,
after the existing backtest + paper-replay stages; the typed record family
lives in ``app/domain/ai2_deep_evaluation.py`` and rides the committed
``GenerationCandidate`` via the additive ``deep_evaluation`` field).

Acceptance coverage (WP-B work item 1, mapped to test names):

- Deep evaluation present on generated candidates, all four stages composed
  over the SAME seeded synthetic series
  -> ``test_deep_evaluation_present_on_generated_candidate``.
- Deterministic repeat: two identical generate runs (fresh services) produce
  byte-identical ``deep_evaluation`` records (no clock/RNG)
  -> ``test_deep_evaluation_deterministic_repeat``.
- Unfit walk-forward windows on a short series -> honest refusal row, the
  run itself still commits (200/422 contract untouched), holdout still
  attests (nothing was selected)
  -> ``test_unfit_walk_forward_records_honest_refusal_row``.
- Engine failures injected at the composition's own seams -> refusal rows on
  the record, never a raise, never a silent skip
  -> ``test_engine_failure_produces_refusal_row_not_raise``.
- Holdout attestation isolated=True for the declared evaluation-window split
  -> ``test_holdout_attestation_isolated_true``.
- Comparison rows present with the explicit float delta basis note and the
  DECLARED baseline label
  -> ``test_comparison_rows_present_with_delta_basis``.
- Walk-forward grid derived from DECLARED program inputs (non-vacuous folds)
  -> ``test_walk_forward_grid_over_declared_inputs``.
- The record stays SYNTHETIC_OR_PAPER-labeled and free of any "live" label
  -> ``test_deep_evaluation_record_is_synthetic_labeled``.

House conventions (mirroring test_ai2_generation.py): plain sync tests with
``asyncio.run``; provider env set via monkeypatch with
``get_settings.cache_clear()`` in setup AND teardown; deterministic injected
``now_utc``; ``end_bar_index`` pinned so the seeded series are stable; no
network anywhere — the transport is the explicitly injected TEST-ONLY
function. Engine-failure injection monkeypatches the composition module's
own attributes (documented injection points), never the engines themselves.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable

import pytest

from app.core.config import get_settings
from app.domain.ai2_deep_evaluation import (
    DEEP_EVALUATION_VERSION,
    AI2ComparisonRow,
    AI2DeepEvaluation,
)
from app.engines.walk_forward import WALK_FORWARD_ENGINE_VERSION
from app.services import ai2_deep_evaluation as ai2_deep_module
from app.services.ai2_deep_evaluation import (
    AI2_BASELINE_LABEL,
    AI2_HOLDOUT_FRACTION,
    AI2_WF_COVERAGE_END,
    AI2_WF_FOLDS_N,
    AI2_WF_TEST_BARS,
    AI2_WF_TRAIN_BARS,
)
from app.services.ai2_generation import (
    AI2GenerationService,
    GenerationCandidate,
    GenerationOutcome,
    GenerationRequest,
)

UTC = timezone.utc
NOW_UTC = datetime(2026, 11, 9, 12, 0, 0, tzinfo=UTC)

#: Canonical VALID typed-spec proposal (mirrors test_ai2_generation.py).
VALID_SPEC: dict[str, Any] = {
    "strategy_name": "deep-eval-smoke-cross",
    "entry": {
        "kind": "cmp",
        "op": ">",
        "children": [
            {"kind": "series", "base": "close"},
            {
                "kind": "call",
                "fn": "sma",
                "children": [
                    {"kind": "series", "base": "close"},
                    {"kind": "num", "value": 20},
                ],
            },
        ],
    },
    "exit": {
        "kind": "call",
        "fn": "crossunder",
        "children": [
            {"kind": "series", "base": "close"},
            {
                "kind": "call",
                "fn": "sma",
                "children": [
                    {"kind": "series", "base": "close"},
                    {"kind": "num", "value": 20},
                ],
            },
        ],
    },
    "risk": {"stop_loss_pct": 2.0, "max_position_pct": 25.0},
    "rationale": "audit-only free text",
}

#: Same strategy with a DECLARED input default — the walk-forward grid then
#: covers the declared input (500/1000/1500) instead of being honestly
#: empty. NOTE: the emitter requires period slots to be integer LITERALS
#: (D-2 fix), so the declared input rides a comparison threshold slot, not
#: an indicator period slot.
INPUT_SPEC: dict[str, Any] = {
    **VALID_SPEC,
    "entry": {
        "kind": "cmp",
        "op": ">",
        "children": [
            {"kind": "series", "base": "close"},
            {"kind": "input", "name": "p", "value": 1000},
        ],
    },
}

#: Satisfies the deterministic clarification (intent + risk tokens present).
HAPPY_QUESTION = (
    "I want a strategy that buys when close crosses above the 20-period sma "
    "and sells on crossunder, with 2% stop loss risk."
)


def _ok_transport(spec: dict[str, Any] | None = None) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """TEST-ONLY transport returning a valid typed-spec JSON text."""
    text = json.dumps(VALID_SPEC if spec is None else spec)

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "status": "ok", "text": text}

    return transport


def _request(question: str = HAPPY_QUESTION, **over: Any) -> GenerationRequest:
    """Bounded request; ``end_bar_index`` pinned for deterministic series."""
    base: dict[str, Any] = {
        "question": question,
        "symbol": "FOLAD",
        "timeframe": "1D",
        "bar_count": 200,
        "end_bar_index": 500,
    }
    base.update(over)
    return GenerationRequest(**base)


def _generate(svc: AI2GenerationService, request: GenerationRequest, spec: dict[str, Any] | None = None) -> GenerationOutcome:
    return asyncio.run(
        svc.generate(request, transport=_ok_transport(spec), now_utc=lambda: NOW_UTC)
    )


def _candidate_deep_eval(svc: AI2GenerationService, outcome: GenerationOutcome) -> AI2DeepEvaluation:
    candidate = svc.candidates.get(outcome.candidate_id)
    assert isinstance(candidate, GenerationCandidate)
    assert candidate.deep_evaluation is not None
    return candidate.deep_evaluation


# ---------------------------------------------------------------------------
# Env fixture (ordering-safe, mirrors test_ai2_generation.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def gen_enabled(monkeypatch):
    """AI2 enabled + external provider configured so the injected TEST
    transport is reached (no network occurs; mirrors test_ai2_generation)."""
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "unit-test-key")
    monkeypatch.setenv("AI2_ENABLED", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Composition on the happy path
# ---------------------------------------------------------------------------
class TestDeepEvaluationComposition:
    def test_deep_evaluation_present_on_generated_candidate(self, gen_enabled) -> None:
        svc = AI2GenerationService()
        outcome = _generate(svc, _request())
        assert outcome.ok is True and outcome.status == "executed_shadow"
        de = _candidate_deep_eval(svc, outcome)

        assert isinstance(de, AI2DeepEvaluation)
        assert de.deep_evaluation_version == DEEP_EVALUATION_VERSION
        assert de.data_label == "SYNTHETIC_OR_PAPER"
        assert de.refusals == ()

        # Stage 9 — pinned small walk-forward over the same seeded series.
        wf = de.walk_forward
        assert wf is not None
        assert (wf.n_folds, wf.train_bars, wf.test_bars) == (
            AI2_WF_FOLDS_N,
            AI2_WF_TRAIN_BARS,
            AI2_WF_TEST_BARS,
        )
        assert (AI2_WF_FOLDS_N, AI2_WF_TRAIN_BARS, AI2_WF_TEST_BARS) == (3, 60, 20)
        assert wf.engine_version == WALK_FORWARD_ENGINE_VERSION
        assert wf.selection_basis == "IN_SAMPLE_PER_FOLD"
        assert len(wf.reproducibility_digest) == 64

        # Stage 10 — holdout attestation summary for the declared split.
        assert de.holdout is not None
        assert de.holdout.isolated is True
        assert de.holdout.holdout_fraction == AI2_HOLDOUT_FRACTION

        # Stage 11 — declared regime slices over the synthetic window.
        robustness = de.robustness
        assert robustness is not None
        assert len(robustness.labels) == 3
        assert robustness.metric_names == ("mean_return_pct", "realized_vol_pct")
        assert all(len(row) == 2 for row in robustness.metrics)
        assert robustness.gap_labels == ()
        assert robustness.uncovered_bar_count == 0
        assert "NOT data-inferred regimes" in robustness.declaration_note

        # Stage 12 — comparison against the DECLARED baseline.
        assert len(de.comparison) == 3

    def test_deep_evaluation_deterministic_repeat(self, gen_enabled) -> None:
        """Two identical generate runs (fresh services, same request and
        transport) produce byte-identical deep_evaluation records — no
        clock, no RNG, no environment reads anywhere in the composition."""
        for spec, spec_name in ((VALID_SPEC, "no-input spec"), (INPUT_SPEC, "input spec")):
            svc_a = AI2GenerationService()
            svc_b = AI2GenerationService()
            request = _request()
            out_a = _generate(svc_a, request, spec)
            out_b = _generate(svc_b, request, spec)
            assert out_a.ok and out_b.ok, (out_a.error_code, out_b.error_code)
            de_a = _candidate_deep_eval(svc_a, out_a)
            de_b = _candidate_deep_eval(svc_b, out_b)
            assert de_a.model_dump(mode="json") == de_b.model_dump(mode="json"), spec_name
            # ...and both round-trip the canonical JSON unchanged.
            assert json.loads(json.dumps(de_a.model_dump(mode="json"))) == de_a.model_dump(mode="json")

    def test_walk_forward_grid_over_declared_inputs(self, gen_enabled) -> None:
        """A program with a DECLARED input default gets a small deterministic
        grid (500/1000/1500); the folds then evaluate for real (non-vacuous)."""
        svc = AI2GenerationService()
        outcome = _generate(svc, _request(), INPUT_SPEC)
        assert outcome.ok is True
        de = _candidate_deep_eval(svc, outcome)
        wf = de.walk_forward
        assert wf is not None
        assert wf.declared_inputs == ("p",)
        assert wf.no_grid_note == ""
        assert wf.n_folds == AI2_WF_FOLDS_N == 3
        assert wf.confirmed_folds == 3
        assert wf.oos_mean is not None
        assert de.refusals == ()


# ---------------------------------------------------------------------------
# Fail-honest behavior
# ---------------------------------------------------------------------------
class TestDeepEvaluationFailHonest:
    def test_unfit_walk_forward_records_honest_refusal_row(self, gen_enabled) -> None:
        """bar_count=60 < required 120: the walk-forward records an honest
        unfit refusal row (never raises), the run still commits with the
        pipeline's unchanged contract, and the holdout still attests (no
        selection was performed anywhere in the deep evaluation)."""
        svc = AI2GenerationService()
        outcome = _generate(svc, _request(bar_count=60))
        assert outcome.ok is True and outcome.status == "executed_shadow"
        assert outcome.error_code is None
        de = _candidate_deep_eval(svc, outcome)

        assert de.walk_forward is None  # refused stage -> summary absent
        rows = [(r.stage, r.reason) for r in de.refusals]
        assert ("walk_forward", "fold_windows_unfit") in rows
        unfit = next(r for r in de.refusals if r.reason == "fold_windows_unfit")
        assert "120" in unfit.detail and "60" in unfit.detail  # required vs available

        # The holdout still attests: zero declared selection (nothing selected).
        assert de.holdout is not None
        assert de.holdout.isolated is True
        assert de.holdout.selection_end_bar_index is None
        assert (de.holdout.insample_bar_count, de.holdout.holdout_bar_count) == (45, 15)

        # The rest of the composition is unaffected.
        assert de.robustness is not None
        assert len(de.comparison) == 3

    def test_engine_failure_produces_refusal_row_not_raise(self, gen_enabled, monkeypatch) -> None:
        """Engines injected to fail at the composition's documented seams:
        every failure becomes a refusal row; the outcome stays ok=True and
        the pipeline's 200/422 contract is untouched; nothing is silently
        skipped (each failed stage has its row)."""

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("boom-engine-failure")

        monkeypatch.setattr(ai2_deep_module, "run_walk_forward", _boom)
        monkeypatch.setattr(ai2_deep_module, "slice_by_regime", _boom)
        monkeypatch.setattr(ai2_deep_module, "compile_source", _boom)

        svc = AI2GenerationService()
        outcome = _generate(svc, _request(question=HAPPY_QUESTION + " Engine-failure variant."))
        assert outcome.ok is True and outcome.status == "executed_shadow"
        de = _candidate_deep_eval(svc, outcome)

        assert de.walk_forward is None
        assert de.robustness is None
        assert de.comparison == ()
        rows = {(r.stage, r.reason) for r in de.refusals}
        assert ("walk_forward", "engine_exception:RuntimeError") in rows
        assert ("regime_slices", "engine_exception:RuntimeError") in rows
        assert ("comparison", "engine_exception:RuntimeError") in rows
        # The holdout is independent of the injected failures and still attests.
        assert de.holdout is not None and de.holdout.isolated is True


# ---------------------------------------------------------------------------
# Stage-specific pins
# ---------------------------------------------------------------------------
class TestDeepEvaluationStages:
    def test_holdout_attestation_isolated_true(self, gen_enabled) -> None:
        """Canonical window (200 bars): the holdout is the 50-bar minority
        tail, the declared selection surface (pinned fold coverage, last
        touched bar 119) closed strictly before the boundary at bar 150."""
        svc = AI2GenerationService()
        outcome = _generate(svc, _request())
        de = _candidate_deep_eval(svc, outcome)
        holdout = de.holdout
        assert holdout is not None
        assert holdout.isolated is True  # Literal[True]-typed summary
        assert holdout.holdout_fraction == 0.25
        assert holdout.insample_bar_count == 150
        assert holdout.holdout_bar_count == 50
        assert holdout.insample_bar_count + holdout.holdout_bar_count == 200
        assert holdout.selection_end_bar_index == AI2_WF_COVERAGE_END - 1 == 119
        assert "not a selection act" in holdout.basis_note

    def test_comparison_rows_present_with_delta_basis(self, gen_enabled) -> None:
        svc = AI2GenerationService()
        outcome = _generate(svc, _request())
        de = _candidate_deep_eval(svc, outcome)
        assert [row.metric for row in de.comparison] == [
            "sharpe",
            "total_return_pct",
            "max_drawdown_pct",
        ]
        for row in de.comparison:
            assert isinstance(row, AI2ComparisonRow)
            assert row.baseline_spec == AI2_BASELINE_LABEL == "AI2-BASELINE-BUY-HOLD-1"
            assert row.delta_basis.startswith(
                "float delta (IEEE-754 subtraction) of candidate vs the declared baseline"
            )
            assert row.candidate is not None and row.baseline is not None
            assert row.delta == row.candidate - row.baseline
        total_return_row = next(r for r in de.comparison if r.metric == "total_return_pct")
        # The candidate side is exactly the pipeline's own headline number.
        assert total_return_row.candidate == outcome.metrics_headline["total_return_pct"]

    def test_deep_evaluation_record_is_synthetic_labeled(self, gen_enabled) -> None:
        svc = AI2GenerationService()
        outcome = _generate(svc, _request())
        de = _candidate_deep_eval(svc, outcome)
        dumped = json.dumps(de.model_dump(mode="json"))
        assert '"live"' not in dumped
        assert "SYNTHETIC_OR_PAPER" in dumped
        assert de.data_label == "SYNTHETIC_OR_PAPER"
