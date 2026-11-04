"""strategy_lab.py — MASTER-RADAR directive §C1/§C4/§D/§E API surface
(prefix /api/v10/strategylab, additive to the v10 family).

STRICTLY ADDITIVE next to /api/v10/chartpro and /api/v10/analytics. No
existing endpoint contract is changed. All series are the deterministic
seeded SYNTHETIC candles (same source as chartpro); the trust envelope is
re-read from market_service exactly like every other v10 router.

Workflow (§C1) as implemented TODAY, honestly scoped:
1. ambiguity/clarification questions: NOT part of this endpoint family yet —
   the AI-proposal seam (NL -> spec -> code) is owner-gated (AI2_ENABLED=0,
   verified=False) and DISCONNECTED. The user authors RSL-1 source directly.
2. formal versioned spec: POST /spec returns the compiled, versioned
   specification (inputs, risk, expressions, digest, DSL contract).
3. spec before code: the spec IS derived from the user's own source; the
   generated-artifact digest is the source digest (no separate codegen step
   without the AI seam).
4-7. validation: POST /validate runs parser + typechecker + semantic
   validator + resource budgets; errors are machine-readable and safe.
8. chart rendering: chart rendering of computed indicators exists via
   /api/v10/indicators/{id}/compute (see indicator_api.py).
9. user-approved backtest / paper forward test: POST /backtest and
   POST /paper-replay run ONLY on synthetic seeded series.
10. versioned report + reproducibility metadata: every run returns a
   result digest; versions are tracked by the in-memory registry (§C3
   approval state machine; explicitly NOT persistent until an owner-approved
   persistence decision exists).

Gates (unchanged): no live trading, no broker egress, no scheduler, no
autonomous activation (R-6/R-8), no external notification (R-9).

MASTER-RADAR WAVE-2 (2026-11-04) additive endpoints (no existing contract
changed):
- POST /optimize — deterministic parameter search (app.engines.backtest_optimizer)
  over the SAME seeded synthetic series path as POST /backtest. Selection is
  IN-SAMPLE only; the optional OOS holdout is evaluated exactly ONCE after the
  winner is fixed (engine select_then_confirm). Server-side budget guard:
  max_evals <= 500, seed REQUIRED, method in {grid, randomized, evolutionary}.
- POST /backtest/export — the FULL /backtest report as a downloadable
  attachment (json = full report; csv = a flat projection documented below).
- Regime surfacing finding: the existing POST /backtest response ALREADY
  surfaces the regime segmentation block as ``report.regime_segments`` (it is
  computed by the engine for every run; it stays empty unless the caller
  supplies ``regime_labels`` — the seeded-lab path passes none). Left as-is
  per the additive-only mandate; no duplicate top-level field was added.
"""
from __future__ import annotations

import csv
import dataclasses
import io
from typing import Any, Dict, List, Mapping, Optional, Tuple

import orjson
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.engines.backtest_optimizer import (
    Objective,
    OptimizationBudget,
    ParameterSpace,
    evolutionary_search,
    grid_search,
    randomized_search,
    select_then_confirm,
)
from app.engines.backtest_product import (
    BacktestRunConfig,
    DataPolicy,
    PortfolioLimits,
    RiskModel,
    run_backtest,
)
from app.services import strategy_lab_service as svc
from app.services.market_service import market_service

router = APIRouter(prefix="/api/v10/strategylab")


def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust": market_service.data_trust_context(),
        "trust_level": market_service.trust_level(),
    }


_SYNTHETIC_NOTE = (
    "تمام محاسبات این مسیر روی داده سینتتیک seed شده است؛ زنده نیست و مبنای تصمیم واقعی قرار نگیرد"
)

# MASTER-RADAR WAVE-2 (2026-11-04): server-side optimizer budget guard.
_MAX_EVALS_LIMIT = 500
_EVALUATIONS_ROWS_CAP = 50  # ranked rows returned in the /optimize response
_OPTIMIZE_METHODS = ("grid", "randomized", "evolutionary")

# IS objectives exposed over HTTP; OOS_SHARPE is walk-forward-only (engine
# contract) and is deliberately NOT reachable from this endpoint.
_OBJECTIVE_METRIC_ATTR = {
    Objective.SHARPE: "sharpe",
    Objective.CALMAR: "calmar",
    Objective.PROFIT_FACTOR: "profit_factor",
}

# CSV export: flat projection column order (English keys, documented below).
_CSV_METRIC_KEYS = [
    "run_id", "result_digest", "engine_version", "execution_model_version",
    "symbol", "timeframe", "bars_used", "trades_count", "data_trust_label",
    "total_return_pct", "annualized_return_pct", "cagr_pct", "max_drawdown_pct",
    "max_drawdown_duration_bars", "sharpe", "sortino", "calmar",
    "profit_factor", "expectancy", "win_rate", "avg_win", "avg_loss",
    "trade_count", "exposure_pct", "avg_holding_bars", "turnover", "fees_total",
]
_CSV_TRADE_COLUMNS = [
    "symbol", "side", "entry_signal_index", "entry_index", "entry_ts",
    "entry_price", "exit_signal_index", "exit_index", "exit_ts", "exit_price",
    "qty", "gross_pnl", "net_pnl", "commission_cash", "spread_cash",
    "slippage_cash", "holding_bars", "exit_reason", "mae_pct", "mfe_pct",
    "regime_label", "closed_at_end_of_data",
]


class SourceBody(BaseModel):
    source: str = Field(min_length=1, max_length=8192)
    name: str = Field(default="dsl.strategy", max_length=64)


class ValidateBody(SourceBody):
    pass


class BacktestBody(SourceBody):
    """AUDIT-MR2 O6 note: `symbol` is NOT validated against a symbol
    universe here — ANY string receives a deterministic SYNTHETIC seeded
    series (the lab is a synthetic-only research surface; an unknown symbol
    never means real data and is never silently mapped to another symbol).
    Universe-validated symbols live in /api/v10/dataquality and the
    instrument master fixtures."""

    symbol: str = Field(default="FOLAD", max_length=32)
    timeframe: str = Field(default="1D", pattern="^(1m|5m|15m|1h|1D)$")
    count: int = Field(default=200, ge=50, le=1000)
    end_bar_index: Optional[int] = Field(default=None, ge=0)
    execution: svc.ExecutionOverrides = Field(default_factory=svc.ExecutionOverrides)


class OptimizeBudgetBody(BaseModel):
    """WAVE-2 optimizer budget. ``seed`` is REQUIRED (absent -> 422) — the
    engine itself has no default and neither does this API surface."""

    max_evals: int = Field(ge=1)
    time_ms: Optional[int] = Field(default=None, gt=0)
    seed: int


class OosSpec(BaseModel):
    """Explicit out-of-sample intent (required in /optimize so the caller
    always states it). Holdout is chronological (newest bars) and evaluated
    exactly once AFTER selection."""

    enabled: bool
    holdout_fraction: float = Field(default=0.3, gt=0.0, lt=1.0)


class OptimizeBody(SourceBody):
    """WAVE-2 /optimize body. ``space``/``method``/``budget``/``oos`` are
    required (explicit honesty); ``end_bar_index``/``objective`` are additive
    optional fields consistent with BacktestBody / the engine's IS objectives."""

    symbol: str = Field(default="FOLAD", max_length=32)
    timeframe: str = Field(default="1D", pattern="^(1m|5m|15m|1h|1D)$")
    count: int = Field(default=200, ge=50, le=1000)
    end_bar_index: Optional[int] = Field(default=None, ge=0)
    execution: svc.ExecutionOverrides = Field(default_factory=svc.ExecutionOverrides)
    space: Dict[str, Any]
    method: str
    budget: OptimizeBudgetBody
    oos: OosSpec
    objective: str = Field(default="SHARPE")


class ExportBody(BacktestBody):
    """WAVE-2 /backtest/export body: BacktestBody shape + format."""

    format: str = Field(default="json", pattern="^(csv|json)$")


class RegisterBody(SourceBody):
    approve: bool = False
    now_ts: Optional[int] = Field(default=None, ge=0)


class PromoteBody(BaseModel):
    now_ts: Optional[int] = Field(default=None, ge=0)


class AlertEvaluateBody(BacktestBody):
    """WAVE-2 on-demand strategy-alert evaluation body (§B5).

    ``staleness_as_of`` is an OPTIONAL injected reference clock for the
    evaluator's freshness refusal. When absent, NO staleness check runs: the
    seeded series uses COMPRESSED SYNTHETIC timestamps (its own time unit),
    so no real wall clock can be compared against them without a unit guess —
    the caller supplies an explicit reference in the series' own unit to
    activate the refusal path."""

    staleness_as_of: Optional[int] = Field(default=None, ge=0)


def _dsl_http_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": "DSL_ERROR",
            "code": getattr(exc, "code", "DSL_ERROR"),
            "message": str(exc),
            "line": getattr(exc, "line", None),
            "col": getattr(exc, "col", None),
        },
    )


@router.post("/validate")
async def validate_strategy(body: ValidateBody) -> Dict[str, Any]:
    outcome = svc.compile_or_errors(body.source)
    return {
        "ok": outcome.ok,
        "dsl_version": outcome.dsl_version,
        "digest": outcome.digest,
        "inputs": outcome.program_inputs,
        "risk": outcome.risk,
        "expressions": outcome.expressions,
        "errors": [e.model_dump() for e in outcome.errors],
        "trust_envelope": _trust_envelope(),
        "synthetic_note": _SYNTHETIC_NOTE,
    }


@router.post("/spec")
async def strategy_spec(body: SourceBody) -> Dict[str, Any]:
    """Formal versioned specification (§C1 step 2-3) for user-authored source."""
    outcome = svc.compile_or_errors(body.source)
    if not outcome.ok:
        raise HTTPException(422, {"error": "DSL_ERROR", "errors": [e.model_dump() for e in outcome.errors]})
    from app.engines.strategy_dsl import CONTRACT

    return {
        "ok": True,
        "spec_version": outcome.dsl_version,
        "api_contract": CONTRACT.model_dump(mode="json"),
        "digest": outcome.digest,
        "name": body.name,
        "inputs": outcome.program_inputs,
        "risk": outcome.risk,
        "expressions": outcome.expressions,
        "generated_by": "user-authored RSL source; AI-proposal seam owner-gated and disconnected",
        "trust_envelope": _trust_envelope(),
    }


def _backtest_payload(body: BacktestBody) -> Dict[str, Any]:
    """Shared compile+run path for POST /backtest and POST /backtest/export
    (WAVE-2): one seeded-series data path (strategy_lab_service.load_seeded_bars
    + DslBacktestAdapter), one honesty envelope.

    WAVE-2 (2026-11-04) additive change only: the payload now also carries the
    full ``trades`` rows (needed by the csv export projection). Every
    pre-existing field keeps its value and the engine result_digest is
    IDENTICAL to the service-path digest (the run config mirrors
    run_backtest_on_seeded exactly; pinned by tests).
    """
    outcome = svc.compile_or_errors(body.source)
    if not outcome.ok:
        raise HTTPException(422, {"error": "DSL_ERROR", "errors": [e.model_dump() for e in outcome.errors]})
    from app.engines.strategy_dsl import compile_source

    try:
        program = compile_source(body.source)
    except Exception as exc:  # pragma: no cover - compile_or_errors already gated
        raise _dsl_http_error(exc) from exc
    try:
        bars = svc.load_seeded_bars(body.symbol, body.timeframe, body.count, body.end_bar_index)
        exec_cfg = (body.execution or svc.ExecutionOverrides()).to_config()
        risk_view = program.risk
        risk = RiskModel(
            stop_loss_pct=risk_view.stop_loss_pct if risk_view else None,
            take_profit_pct=risk_view.take_profit_pct if risk_view else None,
            trailing_pct=risk_view.trailing_pct if risk_view else None,
            max_position_pct=(risk_view.max_position_pct if risk_view and risk_view.max_position_pct else 100.0),
        )
        config = BacktestRunConfig(
            run_id="strategylab",
            execution=exec_cfg,
            risk=risk,
            portfolio=PortfolioLimits(),
            data_policy=DataPolicy(min_bars=50),
            data_trust_label="SYNTHETIC_OR_PAPER",
            notes="strategy-lab seeded-candle backtest; bar-based simulation, never real-tick",
        )
        adapter = svc.DslBacktestAdapter(program, strategy_id=f"dsl:{program.source_digest[:12]}")
        result = run_backtest({body.symbol: bars}, {body.symbol: adapter}, config)
    except ValueError as exc:
        raise HTTPException(422, {"error": "BACKTEST_INPUT_ERROR", "message": str(exc)}) from exc
    payload = {
        "run_id": result.run_id,
        "engine_version": result.engine_version,
        "execution_model_version": result.execution_model_version,
        "result_digest": result.result_digest(),
        "symbol": body.symbol,
        "timeframe": body.timeframe,
        "bars_used": len(bars),
        "report": result.report.model_dump(mode="json"),
        "trades_count": len(result.trades),
        "trades": [t.model_dump(mode="json") for t in result.trades],  # WAVE-2 additive
        "limitations": result.limitations,
        "data_quality": [
            {"symbol": dq.symbol, "refusals": dq.refusals} for dq in result.data_quality
        ],
        "data_trust_label": result.data_trust_label,
    }
    payload["synthetic_note"] = _SYNTHETIC_NOTE
    payload["trust_envelope"] = _trust_envelope()
    return payload


@router.post("/backtest")
async def backtest_strategy(body: BacktestBody) -> Dict[str, Any]:
    return _backtest_payload(body)


# ---------------------------------------------------------------------------
# MASTER-RADAR WAVE-2 (2026-11-04): /optimize + /backtest/export (additive)
# ---------------------------------------------------------------------------


def _build_space(raw: Dict[str, Any]) -> Tuple[ParameterSpace, Dict[str, Any]]:
    """Validate the JSON search space onto the engine's ParameterSpace.

    Accepted keys: ``grid`` (name -> non-empty list of finite numbers) and
    ``bounds`` (name -> [low, high]). The engine's ``constraints`` strings and
    ``dependency_rules`` callables are engine-side seams that a JSON body
    cannot carry and are deliberately NOT exposed here.
    """
    if not isinstance(raw, dict):
        raise HTTPException(422, {"error": "INVALID_SPACE", "message_en": "space must be an object"})
    unknown = sorted(set(raw) - {"grid", "bounds"})
    if unknown:
        raise HTTPException(
            422,
            {
                "error": "UNKNOWN_SPACE_KEYS",
                "message_en": "space accepts only 'grid' and 'bounds' keys",
                "message_fa": "کلیدهای مجاز فضای جست‌وجو فقط grid و bounds هستند",
                "unknown_keys": unknown,
            },
        )
    grid_raw = raw.get("grid") or {}
    bounds_raw = raw.get("bounds") or {}
    if not isinstance(grid_raw, dict) or not isinstance(bounds_raw, dict):
        raise HTTPException(422, {"error": "INVALID_SPACE", "message_en": "space.grid/space.bounds must be objects"})
    grid: Dict[str, List[float]] = {}
    for name, values in grid_raw.items():
        if not isinstance(name, str) or not name or not isinstance(values, list) or not values:
            raise HTTPException(
                422,
                {"error": "INVALID_SPACE", "message_en": f"space.grid[{name!r}] must be a non-empty list of numbers"},
            )
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
            raise HTTPException(
                422,
                {"error": "INVALID_SPACE", "message_en": f"space.grid[{name!r}] values must be numbers"},
            )
        grid[name] = [float(v) for v in values]
    bounds: Dict[str, Tuple[float, float]] = {}
    for name, pair in bounds_raw.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in pair)
        ):
            raise HTTPException(
                422,
                {"error": "INVALID_SPACE", "message_en": f"space.bounds[{name!r}] must be [low, high] numbers"},
            )
        lo, hi = float(pair[0]), float(pair[1])
        if lo > hi:
            raise HTTPException(
                422,
                {"error": "INVALID_SPACE", "message_en": f"space.bounds[{name!r}] low must be <= high"},
            )
        bounds[name] = (lo, hi)
    space = ParameterSpace(grid=grid, bounds=bounds or None)
    space_echo: Dict[str, Any] = {"grid": grid, "bounds": {k: [v[0], v[1]] for k, v in bounds.items()}}
    return space, space_echo


def _program_with_inputs(program: Any, params: Mapping[str, float | int]) -> Any:
    """Frozen-AST copy of the program with the optimizer params overriding the
    declared INPUT defaults — the only sanctioned params->strategy seam (the
    DSL interpreter resolves INPUT refs from ``program.inputs``)."""
    merged = {**program.inputs, **{str(k): float(v) for k, v in params.items()}}
    return dataclasses.replace(program, inputs=merged)


def _objective_on_bars(
    program: Any,
    bars: List[Dict[str, Any]],
    symbol: str,
    execution: svc.ExecutionOverrides,
    objective: Objective,
) -> float:
    """One candidate evaluation = one product backtest over the given slice of
    the SAME seeded series loaded by strategy_lab_service.load_seeded_bars
    (the /backtest data path). Mirrors run_backtest_on_seeded's config exactly
    (this module cannot modify the service, so the config glue is repeated
    here and pinned by tests). A missing objective metric (e.g. no trades)
    raises — the optimizer records it as a refusal, never silently."""
    exec_cfg = (execution or svc.ExecutionOverrides()).to_config()
    risk_view = program.risk
    risk = RiskModel(
        stop_loss_pct=risk_view.stop_loss_pct if risk_view else None,
        take_profit_pct=risk_view.take_profit_pct if risk_view else None,
        trailing_pct=risk_view.trailing_pct if risk_view else None,
        max_position_pct=(risk_view.max_position_pct if risk_view and risk_view.max_position_pct else 100.0),
    )
    config = BacktestRunConfig(
        run_id=f"strategylab-optimize-{program.source_digest[:12]}",
        execution=exec_cfg,
        risk=risk,
        portfolio=PortfolioLimits(),
        data_policy=DataPolicy(min_bars=50),
        data_trust_label="SYNTHETIC_OR_PAPER",
        notes="strategy-lab optimizer candidate evaluation over the seeded /backtest series",
    )
    adapter = svc.DslBacktestAdapter(program, strategy_id=f"dsl:{program.source_digest[:12]}")
    result = run_backtest({symbol: bars}, {symbol: adapter}, config)
    value = getattr(result.report, _OBJECTIVE_METRIC_ATTR[objective])
    if value is None:
        raise ValueError(f"objective_{objective.value.lower()}_unavailable (no trades / degenerate run)")
    return float(value)


@router.post("/optimize")
async def optimize_strategy(body: OptimizeBody) -> Dict[str, Any]:
    """WAVE-2 §D4 deterministic parameter search over the /backtest series.

    Honesty scope (mirrors the engine contract in app.engines.backtest_optimizer):
    - Ranking uses IN-SAMPLE objective values only (``selection_basis`` is
      always "IN_SAMPLE"); when ``oos.enabled`` the chronological holdout is
      evaluated EXACTLY ONCE after the winner is fixed via the engine's
      ``select_then_confirm`` and can never influence ranking.
    - Server-side budget guard: ``max_evals`` > 500 is rejected with an honest
      Persian+English note; ``seed`` is REQUIRED; ``method`` must be one of
      grid | randomized | evolutionary.
    - Multiple-testing honesty: the engine's Bonferroni note is echoed
      (alpha_effective = alpha/n_trials recorded, no p-values fabricated).
    - Refusals and constraint skips are recorded and echoed — never silent.
    - The wall-clock budget (``budget.time_ms``) is optional, best-effort, and
      injected as time.monotonic (the engine itself never reads a clock); it
      can make a run partial/cancelled, which is then declared in the
      response.
    """
    outcome = svc.compile_or_errors(body.source)
    if not outcome.ok:
        raise HTTPException(422, {"error": "DSL_ERROR", "errors": [e.model_dump() for e in outcome.errors]})
    from app.engines.strategy_dsl import compile_source

    try:
        program = compile_source(body.source)
    except Exception as exc:  # pragma: no cover - compile_or_errors already gated
        raise _dsl_http_error(exc) from exc

    if body.method not in _OPTIMIZE_METHODS:
        raise HTTPException(
            422,
            {
                "error": "INVALID_METHOD",
                "message_fa": "روش بهینه‌سازی نامعتبر است؛ یکی از grid/randomized/evolutionary را انتخاب کنید",
                "message_en": "method must be one of: grid, randomized, evolutionary",
                "valid_methods": list(_OPTIMIZE_METHODS),
            },
        )
    if body.budget.max_evals > _MAX_EVALS_LIMIT:
        raise HTTPException(
            422,
            {
                "error": "BUDGET_LIMIT",
                "message_fa": "بودجه بهینه‌سازی محدود است؛ حداکثر تعداد ارزیابی مجاز ۵۰۰ است",
                "message_en": "Optimization budget is limited: max_evals must be <= 500",
                "limit": _MAX_EVALS_LIMIT,
                "requested": body.budget.max_evals,
            },
        )
    try:
        objective = Objective(body.objective)
    except ValueError as exc:
        raise HTTPException(
            422,
            {
                "error": "INVALID_OBJECTIVE",
                "message_en": "objective must be one of: SHARPE, CALMAR, PROFIT_FACTOR",
                "valid": sorted(m.value for m in _OBJECTIVE_METRIC_ATTR),
            },
        ) from exc
    if objective not in _OBJECTIVE_METRIC_ATTR:
        raise HTTPException(
            422,
            {
                "error": "INVALID_OBJECTIVE",
                "message_en": "OOS_SHARPE is walk-forward-only and not reachable from this endpoint",
                "valid": sorted(m.value for m in _OBJECTIVE_METRIC_ATTR),
            },
        )

    space, space_echo = _build_space(body.space)
    space_names = set(space.grid) | set(space.bounds or {})
    if not space_names:
        raise HTTPException(
            422,
            {
                "error": "EMPTY_SPACE",
                "message_en": "space must define a non-empty 'grid' (grid) or 'bounds' (randomized/evolutionary)",
                "message_fa": "فضای جست‌وجو خالی است؛ grid یا bounds را اعلام کنید",
            },
        )
    if body.method == "grid" and not space.grid:
        raise HTTPException(
            422,
            {"error": "GRID_REQUIRED", "message_en": "method 'grid' requires a non-empty space.grid"},
        )
    if body.method in ("randomized", "evolutionary") and not space.bounds:
        raise HTTPException(
            422,
            {
                "error": "BOUNDS_REQUIRED",
                "message_en": f"method '{body.method}' requires a non-empty space.bounds",
            },
        )
    unknown_params = sorted(space_names - set(program.inputs))
    if unknown_params:
        raise HTTPException(
            422,
            {
                "error": "UNKNOWN_OPTIMIZATION_PARAM",
                "message_en": "space parameters must reference declared INPUT names of the strategy",
                "message_fa": "پارامترهای فضای جست‌وجو باید نام INPUT اعلام‌شده در استراتژی باشند",
                "unknown_params": unknown_params,
                "declared_inputs": sorted(program.inputs),
            },
        )

    try:
        bars = svc.load_seeded_bars(body.symbol, body.timeframe, body.count, body.end_bar_index)
    except ValueError as exc:
        raise HTTPException(422, {"error": "SERIES_INPUT_ERROR", "message": str(exc)}) from exc

    is_bars, oos_bars = bars, []
    if body.oos.enabled:
        split = int(round(len(bars) * (1.0 - body.oos.holdout_fraction)))
        is_bars, oos_bars = bars[:split], bars[split:]
        if len(is_bars) < 50 or len(oos_bars) < 50:
            raise HTTPException(
                422,
                {
                    "error": "OOS_SPLIT_TOO_SMALL",
                    "message_en": "both in-sample and holdout slices need >= 50 bars (engine min_bars policy)",
                    "message_fa": "هر دو بخش درون‌نمونه و نگه‌داشته باید حداقل ۵۰ کندل داشته باشند",
                    "is_bars": len(is_bars),
                    "oos_bars": len(oos_bars),
                },
            )
    search_bars = is_bars

    def is_objective(params: Mapping[str, float | int]) -> float:
        return _objective_on_bars(
            _program_with_inputs(program, params), search_bars, body.symbol, body.execution, objective
        )

    def oos_objective(params: Mapping[str, float | int]) -> float:
        return _objective_on_bars(
            _program_with_inputs(program, params), oos_bars, body.symbol, body.execution, objective
        )

    budget = OptimizationBudget(
        max_evaluations=body.budget.max_evals,
        time_budget_seconds=(body.budget.time_ms / 1000.0 if body.budget.time_ms is not None else None),
        seed=body.budget.seed,
    )
    clock = None
    if body.budget.time_ms is not None:
        import time  # local import: only the injected monotonic clock, matching file style

        clock = time.monotonic

    search_fn = {
        "grid": grid_search,
        "randomized": randomized_search,
        "evolutionary": evolutionary_search,
    }[body.method]
    try:
        result = search_fn(
            space,
            is_objective,
            budget,
            objective=objective,
            clock=clock,
            strategy_id=f"dsl:{program.source_digest[:12]}",
        )
    except ValueError as exc:
        raise HTTPException(422, {"error": "OPTIMIZATION_INPUT_ERROR", "message": str(exc)}) from exc
    except Exception as exc:  # honesty: engine failures are surfaced, never silent
        raise HTTPException(
            500,
            {
                "error": "OPTIMIZATION_FAILED",
                "message_en": "optimizer failed; nothing was silently dropped",
                "message_fa": "بهینه‌سازی با خطا متوقف شد؛ هیچ خطایی بی‌صدا نادیده گرفته نشد",
                "detail": str(exc),
            },
        ) from exc

    oos_block: Dict[str, Any]
    if body.oos.enabled:
        confirmation = select_then_confirm(result, is_objective, oos_objective)
        oos_conf = confirmation.oos_confirmation
        oos_block = {
            "enabled": True,
            "selection_basis": confirmation.selection_basis,
            "holdout_fraction": body.oos.holdout_fraction,
            "is_bars": len(is_bars),
            "oos_bars": len(oos_bars),
            "is_objective_value": confirmation.is_objective_value,
            "oos_objective_value": oos_conf.objective_value if oos_conf is not None else None,
            "oos_evaluated_once": bool(oos_conf and oos_conf.evaluated_once),
            "note": confirmation.note,
        }
    else:
        oos_block = {
            "enabled": False,
            "selection_basis": "IN_SAMPLE",
            "note": "OOS confirmation disabled by request; the winner is ranked on the in-sample objective only.",
        }

    # Deterministic ranking identical to the engine's documented key
    # (-objective, param_hash) over evaluable records; capped rows in the
    # response, full count always echoed.
    evaluable = [e for e in result.evaluations if not e.is_refused and e.objective_value is not None]
    ranked = sorted(evaluable, key=lambda e: (-float(e.objective_value), e.param_hash))
    rows = [e.model_dump(mode="json") for e in ranked[:_EVALUATIONS_ROWS_CAP]]
    refused = [e for e in result.evaluations if e.is_refused]

    partial_notes: List[str] = []
    if result.cancelled:
        partial_notes.append("search cancelled before completion; results are partial")
    if result.budget_exhausted:
        if body.method == "grid":
            total_combos = 1
            for values in space.grid.values():
                total_combos *= max(1, len(values))
            covered = len(result.evaluations) + result.n_constraint_skips
            if covered < total_combos:
                partial_notes.append(
                    f"grid not fully covered within the budget "
                    f"({covered}/{total_combos} points evaluated or skipped); results are partial"
                )
        else:
            partial_notes.append(
                "evaluation budget reached; randomized/evolutionary sampling stopped "
                "at the declared budget edge (sampling has no finite full space)"
            )

    response: Dict[str, Any] = {
        "ok": True,
        "method": body.method,
        "objective": objective.value,
        "selection_basis": "IN_SAMPLE",
        "winner": result.best.model_dump(mode="json") if result.best is not None else None,
        "evaluations": rows,
        "evaluations_returned": len(rows),
        "total_evaluations": len(result.evaluations),
        "evaluable_count": len(evaluable),
        "refused_count": len(refused),
        "refused_examples": [e.model_dump(mode="json") for e in refused[:10]],
        "n_constraint_skips": result.n_constraint_skips,
        "cancelled": result.cancelled,
        "budget_exhausted": result.budget_exhausted,
        "partial_notes": partial_notes,
        "bonferroni_note": result.corrected_alpha_note,
        "reproducibility_digest": result.reproducibility_digest,
        "budget_echo": {
            "max_evals": body.budget.max_evals,
            "time_ms": body.budget.time_ms,
            "seed": body.budget.seed,
            "limit": _MAX_EVALS_LIMIT,
            "engine_echo": result.budget_echo,
        },
        "oos": oos_block,
        "space_echo": space_echo,
        "symbol": body.symbol,
        "timeframe": body.timeframe,
        "count": body.count,
        "bars_used": len(bars),
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "synthetic_note": _SYNTHETIC_NOTE,
        "trust_envelope": _trust_envelope(),
    }
    if result.best is None:
        response["winner_note"] = (
            "no evaluable candidates (all trials refused or non-finite); selection impossible — recorded, not silent"
        )
    return response


def _csv_cell(value: Any) -> str:
    """CSV projection cell: str() as-is; None -> empty cell (documented)."""
    if value is None:
        return ""
    return str(value)


@router.post("/backtest/export")
async def export_backtest(body: ExportBody) -> Response:
    """WAVE-2: downloadable FULL report export (deterministic filename).

    - format=json: the complete POST /backtest payload verbatim as an
      ``application/json`` attachment — this is the FULL report (equity curve,
      monthly/yearly rows, limitations, trust envelope included).
    - format=csv: a clearly separated FLAT PROJECTION — ``## METRICS``
      line-pairs (key,value), a blank line, then ``## TRADES`` header+rows.
      English keys; values rendered with str() as-is (floats keep the engine's
      shortest round-trip repr; pct fields are engine percentage units, e.g.
      total_return_pct=1.77 means +1.77%); None renders as an empty cell. The
      equity curve / calendar rows are NOT part of the csv projection — the
      json export is the full report.
    - Identical inputs produce the same result_digest, the same
      ``backtest-report-<digest8>`` filename and byte-identical csv files. The
      json attachment embeds the canonical market_service trust envelope whose
      ``checked_at`` is the trust-check instant by canonical design, so
      byte-identity is not claimed for json across calls (everything except
      that envelope is identical).
    """
    payload = _backtest_payload(body)
    digest8 = str(payload.get("result_digest") or "")[:8] or "nodigest"
    if body.format == "json":
        return Response(
            content=orjson.dumps(payload),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="backtest-report-{digest8}.json"'},
        )
    report = payload.get("report") or {}
    trades = payload.get("trades") or []
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["## METRICS"])
    for key in _CSV_METRIC_KEYS:
        value = payload[key] if key in payload else report.get(key)
        writer.writerow([key, _csv_cell(value)])
    writer.writerow([])  # blank separator line between the two sections
    writer.writerow(["## TRADES"])
    writer.writerow(_CSV_TRADE_COLUMNS)
    for trade in trades:
        writer.writerow([_csv_cell(trade.get(col)) for col in _CSV_TRADE_COLUMNS])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="backtest-report-{digest8}.csv"'},
    )


@router.post("/paper-replay")
async def paper_replay(body: BacktestBody) -> Dict[str, Any]:
    """§E paper forward-test replay over a synthetic window (NOT live)."""
    outcome = svc.compile_or_errors(body.source)
    if not outcome.ok:
        raise HTTPException(422, {"error": "DSL_ERROR", "errors": [e.model_dump() for e in outcome.errors]})
    from app.engines.strategy_dsl import compile_source

    try:
        program = compile_source(body.source)
    except Exception as exc:  # pragma: no cover
        raise _dsl_http_error(exc) from exc
    try:
        payload = svc.run_paper_replay_on_seeded(
            program,
            symbol=body.symbol,
            timeframe=body.timeframe,
            count=body.count,
            end_bar_index=body.end_bar_index,
            execution=body.execution,
            strategy_name=body.name,
        )
    except ValueError as exc:
        raise HTTPException(422, {"error": "PAPER_INPUT_ERROR", "message": str(exc)}) from exc
    payload["trust_envelope"] = _trust_envelope()
    return payload


@router.post("/alerts/evaluate")
async def alerts_evaluate(body: AlertEvaluateBody) -> Dict[str, Any]:
    """WAVE-2 §B5: ON-DEMAND indicator/strategy-condition alert evaluation.

    Honesty scope (recorded, test-pinned in test_master_radar_wave2_api.py):
    - Manual, request-scoped evaluation ONLY: no scheduler, no background
      loop, no polling task exists behind this endpoint (R-6 intact) — the
      caller decides when to evaluate, exactly like a chart refresh.
    - The evaluated condition is the RSL-1.0.0 program's ENTRY decision at
      the LAST CLOSED bar of the deterministic seeded series.
    - Staleness: the freshness refusal activates ONLY when the caller
      supplies ``staleness_as_of`` IN THE SERIES' OWN TIME UNIT (the seeded
      series uses compressed synthetic timestamps — no wall clock is read
      here and none is guessed); a stale series yields
      ``triggered=false, stale=true`` — never a guess.
    - No notification is sent anywhere (R-9): the result stays in THIS
      response; any inbox wiring is a separate, explicit future act.
    """
    from app.engines.strategy_alerts import evaluate_condition

    outcome = svc.compile_or_errors(body.source)
    if not outcome.ok:
        raise HTTPException(422, {"error": "DSL_ERROR", "errors": [e.model_dump() for e in outcome.errors]})
    bars = svc.load_seeded_bars(
        body.symbol,
        body.timeframe,
        body.count,
        end_bar_index=body.end_bar_index,
    )
    try:
        result = evaluate_condition(body.source, bars, as_of=body.staleness_as_of)
    except Exception as exc:  # defensive: the evaluator itself is total; keep 422 honest
        raise _dsl_http_error(exc) from exc
    return {
        "ok": True,
        "symbol": body.symbol,
        "timeframe": body.timeframe,
        "evaluation_mode": "ON_DEMAND",
        "scheduler_note": "بدون زمان‌بند — فقط ارزیابی دستی/درخواستی (R-6)",
        "staleness_as_of": body.staleness_as_of,
        "staleness_note": (
            "بررسی کهنگی فقط وقتی فعال است که staleness_as_of صریحاً و در واحد"
            "زمانی خود سری داده شود؛ هیچ ساعت دیواری خوانده یا حدس زده نمی‌شود"
        ),
        "result": result,
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "synthetic_note": _SYNTHETIC_NOTE,
        "no_egress_note": "هیچ اعلانی به بیرون محصول ارسال نمی‌شود (R-9) — نتیجه فقط در همین پاسخ است",
        "trust_envelope": _trust_envelope(),
    }


@router.get("/versions")
async def list_versions() -> Dict[str, Any]:
    return {
        "versions": [r.model_dump(mode="json") for r in svc.version_registry.list()],
        "persistence_note": (
            "ثبت نسخه‌ها فقط در حافظه فرآیند است؛ ماندگاری نیازمند تصمیم مالک است"
        ),
        "trust_envelope": _trust_envelope(),
    }


@router.post("/versions")
async def register_version(body: RegisterBody) -> Dict[str, Any]:
    outcome = svc.compile_or_errors(body.source)
    if not outcome.ok:
        raise HTTPException(422, {"error": "DSL_ERROR", "errors": [e.model_dump() for e in outcome.errors]})
    now_ts = body.now_ts
    if now_ts is None:
        import time

        now_ts = int(time.time())  # wall clock ONLY for the user-facing label stamp
    rec = svc.version_registry.register(body.name, outcome.digest or "", body.approve, now_ts)
    return {
        "version": rec.model_dump(mode="json"),
        "approval_note": (
            "ارتقا به PROMOTED فقط با وضعیت APPROVED (تأیید صریح کاربر) ممکن است — §C3"
        ),
        "trust_envelope": _trust_envelope(),
    }


@router.post("/versions/{version_id}/promote")
async def promote_version(version_id: str, body: PromoteBody) -> Dict[str, Any]:
    now_ts = body.now_ts
    if now_ts is None:
        import time

        now_ts = int(time.time())
    try:
        rec = svc.version_registry.promote(version_id, now_ts)
    except KeyError as exc:
        raise HTTPException(404, {"error": "version_not_found"}) from exc
    except ValueError as exc:
        raise HTTPException(409, {"error": str(exc)}) from exc
    return {
        "version": rec.model_dump(mode="json"),
        "scope_note": (
            "PROMOTED فقط مجوز paper forward test است؛ معامله زنده/بروکر وجود ندارد"
        ),
        "trust_envelope": _trust_envelope(),
    }
