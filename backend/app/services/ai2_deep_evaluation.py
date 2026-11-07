"""ai2_deep_evaluation.py — the AI-2 deep-evaluation composition (WAVE-B, WP-B).

Bounded deterministic composition of the four MVRL deep-evaluation stages
(walk-forward / holdout / regime robustness / declared-baseline comparison)
over the SAME seeded synthetic series the governed generation pipeline
already evaluates on (``strategy_lab_service.load_seeded_bars`` /
``run_backtest_on_seeded`` — SYNTHETIC_OR_PAPER only; the pipeline can never
reach another data source through this module).

Called by ``app/services/ai2_generation.py`` after the existing backtest +
paper-replay stages; the returned :class:`AI2DeepEvaluation` (typed in
``app/domain/ai2_deep_evaluation.py``) is attached to the committed
``GenerationCandidate`` via the additive ``deep_evaluation`` field.

Fail-honest contract (never breaks the pipeline's 200/422 shape):
- every engine refusal — unfit fold windows, holdout violation, regime
  refusal, comparison failure, ANY unexpected exception — becomes an
  ``AI2DeepRefusal`` row on the record: never a silent skip, never a raise;
- the top-level builder is itself wrapped by an absolute fail-honest net: it
  cannot raise out to the pipeline.

Determinism: the builder is a pure function of (compiled program, request,
candidate backtest payload). No wall clock, no RNG (the optimizer budget
seed is the pinned constant ``_SEED`` and grid enumeration is
order-deterministic), no environment reads. Same inputs -> byte-identical
record (test-pinned).

ENGINE-INJECTION POINTS (test seam): every stage engine is imported into
THIS module's namespace (``run_walk_forward``, ``split_holdout``,
``assert_no_selection_on_holdout``, ``slice_by_regime``,
``compile_source``, ``run_backtest_on_seeded``) and referenced by
module-global name at call time, so tests may monkeypatch THIS module's
attributes to simulate engine failures (producing honest refusal rows)
without touching the engines themselves.

Pinned engineering-authority constants (bounded, D-AI-24 class; all
documented here and pinned by ``backend/tests/test_ai2_deep_evaluation.py``):

- fold spec ``n=3, train_bars=60, test_bars=20``: fits the pipeline's
  minimum-to-default bar surface (fit rule ``60 + 3*20 = 120 <= bars``); a
  shorter request records an honest ``fold_windows_unfit`` refusal row;
- holdout fraction ``0.25``: the holdout stays a minority tail segment;
  the declared selection surface (pinned fold-window coverage) must close
  strictly before the holdout boundary — when a short window makes the fold
  coverage reach INTO the holdout tail, the holdout engine refuses and the
  refusal is recorded (fail-honest);
- regime labels: pinned ``NEUTRAL`` declarations over three structural
  thirds of the window — positional declarations for deterministic slicing,
  never data-inferred regimes (regime_slices' explicit-in/explicit-out rule);
- baseline ``AI2-BASELINE-BUY-HOLD-1``: a fixed RSL-1 buy-and-hold reference
  program evaluated by ``run_backtest_on_seeded`` on the same seeded path;
  the comparison reports float deltas against it with the explicit basis
  note.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Sequence

from app.domain.ai2_deep_evaluation import (
    DEEP_EVALUATION_VERSION,
    AI2ComparisonRow,
    AI2DeepEvaluation,
    AI2DeepRefusal,
    AI2HoldoutSummary,
    AI2RegimeSliceSummary,
    AI2WalkForwardSummary,
)
from app.engines.backtest_optimizer import Objective, ParameterSpace
from app.engines.backtest_product import (
    BacktestRunConfig,
    DataPolicy,
    PortfolioLimits,
    RiskModel,
    run_backtest,
)
from app.engines.holdout import (
    HoldoutViolation,
    SelectionWindow,
    assert_no_selection_on_holdout,
    boundary_ts_of,
    split_holdout,
)
from app.engines.regime_slices import RegimeSliceViolation, slice_by_regime
from app.engines.strategy_dsl import compile_source
from app.engines.walk_forward import WALK_FORWARD_ENGINE_VERSION, run_walk_forward
from app.services.strategy_lab_service import (
    DslBacktestAdapter,
    ExecutionOverrides,
    load_seeded_bars,
    run_backtest_on_seeded,
)

__all__ = [
    "DEEP_EVALUATION_VERSION",
    "AI2_BASELINE_LABEL",
    "AI2_BASELINE_SOURCE",
    "AI2_HOLDOUT_FRACTION",
    "AI2_WF_TEST_BARS",
    "AI2_WF_TRAIN_BARS",
    "AI2_WF_FOLDS_N",
    "build_deep_evaluation",
]

# ---------------------------------------------------------------------------
# Pinned composition constants (engineering authority; deterministic)
# ---------------------------------------------------------------------------
AI2_WF_FOLDS_N = 3
AI2_WF_TRAIN_BARS = 60
AI2_WF_TEST_BARS = 20
#: Fold coverage end index (EXCLUSIVE) of the pinned fold spec: the last bar
#: the declared deep-evaluation selection/confirmation surface may touch.
AI2_WF_COVERAGE_END = AI2_WF_TRAIN_BARS + AI2_WF_FOLDS_N * AI2_WF_TEST_BARS
#: Grid cap: <= 2 declared inputs x 3 pinned points = <= 9 trials per fold.
AI2_WF_MAX_EVALS_PER_FOLD = 9
#: Pinned optimizer budget seed. Grid enumeration never samples, so the
#: value only has to be fixed, not meaningful; grid_search's evaluation
#: order is lexicographic and deterministic regardless of seed.
AI2_WF_SEED = 0
AI2_HOLDOUT_FRACTION = 0.25
AI2_GRID_INPUTS_MAX = 2
AI2_GRID_POINTS_PER_INPUT = 3
AI2_OBJECTIVE = Objective.SHARPE

#: The DECLARED baseline of the AI-2 generation pipeline (part of this
#: module's contract, byte-pinned): a trivial buy-and-hold reference on the
#: same seeded path. ENTRY fires immediately (close > 0 on synthetic prices)
#: and EXIT never fires (close < 0 is unreachable) — one held position.
AI2_BASELINE_SOURCE = (
    "# ai2 declared deep-evaluation baseline (buy-and-hold reference)\n"
    "ENTRY close > 0\n"
    "EXIT close < 0\n"
)
AI2_BASELINE_LABEL = "AI2-BASELINE-BUY-HOLD-1"

AI2_COMPARISON_METRICS: tuple[str, ...] = ("sharpe", "total_return_pct", "max_drawdown_pct")
AI2_DELTA_BASIS = (
    "float delta (IEEE-754 subtraction) of candidate vs the declared baseline, "
    "both from run_backtest_on_seeded over the SAME seeded synthetic path and "
    "window; not an exact-rational comparison"
)

AI2_REGIME_LABEL = "NEUTRAL"
AI2_REGIME_NOTE = (
    "caller-declared structural thirds of the synthetic window; labels are "
    "positional declarations used only for deterministic slicing, NOT "
    "data-inferred regimes"
)
AI2_REGIME_METRIC_NAMES: tuple[str, ...] = ("mean_return_pct", "realized_vol_pct")

AI2_DEEP_EVAL_DATA_LABEL = "SYNTHETIC_OR_PAPER"

_HOLDOUT_ATTESTED_NOTE = (
    "attestation scope: the deep evaluation's declared selection surface "
    "(the pinned walk-forward fold-window coverage) closed strictly before "
    "the holdout boundary; the candidate's headline backtest over the full "
    "window is reported separately (comparison stage) and is not a selection act"
)
_HOLDOUT_NO_SELECTION_NOTE = (
    "walk-forward did not run (unfit/refused); the deep evaluation performed "
    "NO selection, declared as a zero-width selection window at the series "
    "start; the holdout tail is attested untouched by any selection"
)


# ---------------------------------------------------------------------------
# Stage helpers (each returns its summary/rows or None + a refusal row)
# ---------------------------------------------------------------------------
def _grid_for(program: Any) -> ParameterSpace:
    """Small deterministic grid over the program's DECLARED INPUT defaults.

    Integer-valued defaults step by +-1 (period slots stay integers);
    non-integer defaults scale multiplicatively (0.5x / 1x / 1.5x). Only the
    first ``AI2_GRID_INPUTS_MAX`` names (sorted) enter the grid; a program
    with no declared inputs yields an EMPTY grid — the walk-forward then
    records the engine's own honest no-evaluable-candidate fold rows (the
    candidate has nothing to select).
    """
    grid: dict[str, list[float | int]] = {}
    for name in sorted(program.inputs)[:AI2_GRID_INPUTS_MAX]:
        default = float(program.inputs[name])
        if default.is_integer():
            base = int(default)
            values: list[float | int] = [base - 1, base, base + 1]
        else:
            values = [default * 0.5, default, default * 1.5]
        grid[name] = values
    return ParameterSpace(grid=grid)


def _wf_objective_on_window(
    program: Any,
    params: Mapping[str, float | int],
    window_bars: Sequence[Mapping[str, Any]],
    symbol: str,
) -> float:
    """One fold-window evaluation = one product backtest over the window.

    Mirrors the Strategy Lab walk-forward glue (config, risk projection,
    adapter, DataPolicy(min_bars=len(window))) exactly; the objective is the
    window's SHARPE and a missing metric raises (recorded by the optimizer
    as a refusal, never silent). Data: the caller-passed slice of the SAME
    seeded series (SYNTHETIC_OR_PAPER).
    """
    merged = {**program.inputs, **{str(k): float(v) for k, v in params.items()}}
    tuned = replace(program, inputs=merged)
    risk_view = tuned.risk
    risk = RiskModel(
        stop_loss_pct=risk_view.stop_loss_pct if risk_view else None,
        take_profit_pct=risk_view.take_profit_pct if risk_view else None,
        trailing_pct=risk_view.trailing_pct if risk_view else None,
        max_position_pct=(
            risk_view.max_position_pct if risk_view and risk_view.max_position_pct else 100.0
        ),
    )
    config = BacktestRunConfig(
        run_id=f"ai2deep-wf-{tuned.source_digest[:12]}",
        execution=ExecutionOverrides().to_config(),
        risk=risk,
        portfolio=PortfolioLimits(),
        data_policy=DataPolicy(min_bars=len(window_bars)),
        data_trust_label=AI2_DEEP_EVAL_DATA_LABEL,
        notes="ai2 deep-evaluation walk-forward fold-window evaluation over the seeded series",
    )
    adapter = DslBacktestAdapter(tuned, strategy_id=f"dsl:{tuned.source_digest[:12]}")
    result = run_backtest({symbol: list(window_bars)}, {symbol: adapter}, config)
    value = result.report.sharpe
    if value is None:
        raise ValueError("objective_sharpe_unavailable (no trades / degenerate run)")
    return float(value)


def _regime_metrics(slice_bars: Sequence[Mapping[str, Any]]) -> tuple[float, float]:
    """Pure deterministic per-slice market aggregates (close-to-close).

    Returns ``(mean_return_pct, realized_vol_pct)``; finite for any non-empty
    slice of the seeded series (zero-division guarded). Called twice per
    window by the engine's determinism guard — pure, so it always agrees.
    """
    closes = [float(bar["c"]) for bar in slice_bars]
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1] * 100.0
        for i in range(1, len(closes))
        if closes[i - 1] != 0.0
    ]
    if not returns:
        return (0.0, 0.0)
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return (mean, variance ** 0.5)


def _stage_walk_forward(
    program: Any,
    request: Any,
    bars: list[dict[str, Any]],
    refusals: list[AI2DeepRefusal],
) -> AI2WalkForwardSummary | None:
    grid = _grid_for(program)
    digest_body: dict[str, Any] = {
        "surface": "ai2_generation_deep_evaluation",
        "source_digest": program.source_digest,
        "symbol": request.symbol,
        "timeframe": request.timeframe,
        "bar_count": request.bar_count,
        "end_bar_index": request.end_bar_index,
        "folds": {
            "n": AI2_WF_FOLDS_N,
            "train_bars": AI2_WF_TRAIN_BARS,
            "test_bars": AI2_WF_TEST_BARS,
        },
        "grid": {name: [float(v) for v in values] for name, values in sorted(grid.grid.items())},
        "seed": AI2_WF_SEED,
    }

    def evaluate(params: Mapping[str, float | int], window_bars: list[dict[str, Any]]) -> float:
        return _wf_objective_on_window(program, params, window_bars, request.symbol)

    try:
        result = run_walk_forward(
            bars,
            n=AI2_WF_FOLDS_N,
            train_bars=AI2_WF_TRAIN_BARS,
            test_bars=AI2_WF_TEST_BARS,
            space=grid,
            objective=AI2_OBJECTIVE,
            seed=AI2_WF_SEED,
            max_evals_per_fold=AI2_WF_MAX_EVALS_PER_FOLD,
            evaluate=evaluate,
            digest_body=digest_body,
            strategy_id=f"ai2deep:{program.source_digest[:12]}",
        )
    except ValueError as exc:
        reason = (
            "fold_windows_unfit"
            if "fold_windows_unfit" in str(exc)
            else "walk_forward_value_error"
        )
        refusals.append(AI2DeepRefusal(stage="walk_forward", reason=reason, detail=str(exc)[:500]))
        return None
    except Exception as exc:  # fail-honest: any engine failure is a refusal row
        refusals.append(
            AI2DeepRefusal(
                stage="walk_forward",
                reason=f"engine_exception:{type(exc).__name__}",
                detail=str(exc)[:500],
            )
        )
        return None

    aggregate = result.aggregate
    grid_note = ""
    if not grid.grid:
        grid_note = (
            "the generated program declares no INPUT parameters; per-fold "
            "selection has no grid and the fold rows honestly record the "
            "engine's no-evaluable-candidate note (nothing was selected)"
        )
    return AI2WalkForwardSummary(
        n_folds=int(aggregate["n_folds"]),
        train_bars=AI2_WF_TRAIN_BARS,
        test_bars=AI2_WF_TEST_BARS,
        confirmed_folds=int(aggregate["confirmed_folds"]),
        positive_folds=int(aggregate["positive_folds"]),
        oos_mean=aggregate["oos_mean"],
        engine_version=WALK_FORWARD_ENGINE_VERSION,
        objective=str(aggregate["objective"]),
        selection_basis=str(aggregate["selection_basis"]),
        reproducibility_digest=str(result.reproducibility_digest),
        declared_inputs=tuple(sorted(program.inputs)),
        no_grid_note=grid_note,
    )


def _stage_holdout(
    program: Any,
    bars: list[dict[str, Any]],
    walk_forward_ran: bool,
    refusals: list[AI2DeepRefusal],
) -> AI2HoldoutSummary | None:
    try:
        insample, holdout_segment = split_holdout(bars, AI2_HOLDOUT_FRACTION)
        boundary = boundary_ts_of(holdout_segment)
        if walk_forward_ran:
            # The declared selection surface = the pinned fold-window
            # coverage [0, AI2_WF_COVERAGE_END); its last touched bar is
            # coverage_end - 1. The engine refuses (SELECTION_WINDOW_OVERLAPS
            # _HOLDOUT) when that surface reaches into the holdout tail.
            selection_end_index: int | None = AI2_WF_COVERAGE_END - 1
            selection_end_ts = float(bars[selection_end_index]["ts"])
            note = _HOLDOUT_ATTESTED_NOTE
        else:
            selection_end_index = None
            selection_end_ts = float(bars[0]["ts"])
            note = _HOLDOUT_NO_SELECTION_NOTE
        attestation = assert_no_selection_on_holdout(
            SelectionWindow(
                strategy_id=f"ai2deep:{program.source_digest[:12]}",
                selection_start_ts=float(bars[0]["ts"]),
                selection_end_ts=selection_end_ts,
            ),
            holdout_boundary_ts=boundary,
            insample_bars=insample,
            holdout_bars=holdout_segment,
        )
        return AI2HoldoutSummary(
            holdout_fraction=AI2_HOLDOUT_FRACTION,
            isolated=attestation.isolated,
            insample_bar_count=attestation.insample_bar_count,
            holdout_bar_count=attestation.holdout_bar_count,
            selection_end_bar_index=selection_end_index,
            basis_note=note,
        )
    except HoldoutViolation as exc:
        refusals.append(
            AI2DeepRefusal(stage="holdout", reason=exc.reason, detail=exc.detail[:500])
        )
        return None
    except Exception as exc:  # fail-honest: any engine failure is a refusal row
        refusals.append(
            AI2DeepRefusal(
                stage="holdout",
                reason=f"engine_exception:{type(exc).__name__}",
                detail=str(exc)[:500],
            )
        )
        return None


def _stage_regime_slices(
    bars: list[dict[str, Any]],
    refusals: list[AI2DeepRefusal],
) -> AI2RegimeSliceSummary | None:
    try:
        ts = [float(bar["ts"]) for bar in bars]
        third = len(bars) // 3
        windows = [
            (AI2_REGIME_LABEL, ts[0], ts[third]),
            (AI2_REGIME_LABEL, ts[third], ts[2 * third]),
            (AI2_REGIME_LABEL, ts[2 * third], ts[-1] + 1.0),
        ]
        report = slice_by_regime(windows, bars, _regime_metrics)
        return AI2RegimeSliceSummary(
            labels=tuple(s.label for s in report.slices),
            bar_counts=tuple(s.bar_count for s in report.slices),
            metric_names=AI2_REGIME_METRIC_NAMES,
            metrics=tuple(tuple(float(v) for v in s.metrics) for s in report.slices),
            gap_labels=report.gap_labels,
            uncovered_bar_count=report.uncovered_bar_count,
            declaration_note=AI2_REGIME_NOTE,
        )
    except RegimeSliceViolation as exc:
        refusals.append(
            AI2DeepRefusal(stage="regime_slices", reason=exc.reason, detail=exc.detail[:500])
        )
        return None
    except Exception as exc:  # fail-honest: any engine failure is a refusal row
        refusals.append(
            AI2DeepRefusal(
                stage="regime_slices",
                reason=f"engine_exception:{type(exc).__name__}",
                detail=str(exc)[:500],
            )
        )
        return None


def _stage_comparison(
    request: Any,
    backtest: Mapping[str, Any],
    refusals: list[AI2DeepRefusal],
) -> tuple[AI2ComparisonRow, ...]:
    rows: list[AI2ComparisonRow] = []
    try:
        baseline_program = compile_source(AI2_BASELINE_SOURCE)
        baseline_backtest = run_backtest_on_seeded(
            baseline_program,
            symbol=request.symbol,
            timeframe=request.timeframe,
            count=request.bar_count,
            end_bar_index=request.end_bar_index,
            run_id="strategylab",
        )
        candidate_report = dict(backtest.get("report") or {})
        baseline_report = dict(baseline_backtest.get("report") or {})
        for metric in AI2_COMPARISON_METRICS:
            candidate_value = candidate_report.get(metric)
            baseline_value = baseline_report.get(metric)
            delta: float | None = None
            if candidate_value is not None and baseline_value is not None:
                delta = float(candidate_value) - float(baseline_value)
            basis = AI2_DELTA_BASIS
            if delta is None:
                basis += "; an unavailable metric on either side is recorded as None (never silent)"
            rows.append(
                AI2ComparisonRow(
                    metric=metric,
                    candidate=float(candidate_value) if candidate_value is not None else None,
                    baseline=float(baseline_value) if baseline_value is not None else None,
                    delta=delta,
                    delta_basis=basis,
                    baseline_spec=AI2_BASELINE_LABEL,
                )
            )
        return tuple(rows)
    except Exception as exc:  # fail-honest: any engine failure is a refusal row
        refusals.append(
            AI2DeepRefusal(
                stage="comparison",
                reason=f"engine_exception:{type(exc).__name__}",
                detail=str(exc)[:500],
            )
        )
        return ()


# ---------------------------------------------------------------------------
# Top-level builder (fail-honest: cannot raise out to the pipeline)
# ---------------------------------------------------------------------------
def build_deep_evaluation(
    program: Any,
    request: Any,
    backtest: Mapping[str, Any],
) -> AI2DeepEvaluation:
    """Compose the deep-evaluation record for one generated candidate.

    Deterministic (no clock, no RNG, no environment); every engine refusal
    becomes a refusal row. The seeded series is loaded through the SAME
    ``strategy_lab_service.load_seeded_bars`` path the pipeline already uses.
    The builder CANNOT raise out to the pipeline: the composition runs inside
    an absolute fail-honest net whose fallback is a refusal-row-only record.
    """
    refusals: list[AI2DeepRefusal] = []
    try:
        return _compose(program, request, backtest, refusals)
    except Exception as exc:  # absolute fail-honest net (defense in depth)
        refusals.append(
            AI2DeepRefusal(
                stage="composition",
                reason=f"unexpected_exception:{type(exc).__name__}",
                detail=str(exc)[:500],
            )
        )
    if not refusals:  # pragma: no cover - the net above always appends
        refusals.append(AI2DeepRefusal(stage="composition", reason="deep_evaluation_internal_error"))
    return AI2DeepEvaluation(refusals=tuple(refusals))


def _compose(
    program: Any,
    request: Any,
    backtest: Mapping[str, Any],
    refusals: list[AI2DeepRefusal],
) -> AI2DeepEvaluation:
    """Stage-by-stage composition (each stage refuses into ``refusals``)."""
    try:
        bars = load_seeded_bars(
            request.symbol, request.timeframe, request.bar_count, request.end_bar_index
        )
    except Exception as exc:
        refusals.append(
            AI2DeepRefusal(
                stage="composition",
                reason=f"seeded_series_refused:{type(exc).__name__}",
                detail=str(exc)[:500],
            )
        )
        return AI2DeepEvaluation(refusals=tuple(refusals))

    walk_forward_summary = _stage_walk_forward(program, request, bars, refusals)
    holdout_summary = _stage_holdout(
        program, bars, walk_forward_summary is not None, refusals
    )
    robustness_summary = _stage_regime_slices(bars, refusals)
    comparison_rows = _stage_comparison(request, backtest, refusals)
    return AI2DeepEvaluation(
        walk_forward=walk_forward_summary,
        holdout=holdout_summary,
        robustness=robustness_summary,
        comparison=comparison_rows,
        refusals=tuple(refusals),
    )
