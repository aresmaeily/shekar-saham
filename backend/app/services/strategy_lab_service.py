"""strategy_lab_service.py — MASTER-RADAR directive §C1/§C3/§D/§E glue layer.

Bridges the restricted Strategy DSL (app.engines.strategy_dsl, RSL-1) to the
product backtest engine (app.engines.backtest_product) and the paper
forward-test runtime (app.engines.forward_test_paper), over the deterministic
seeded-candle series (app.data.seeded_candles, SYNTHETIC class only).

Honesty contract (this file is the integration seam, so it repeats it):
- Every series here is SYNTHETIC_OR_PAPER. Nothing in this module can mint a
  "live" or "real" label; the trust envelope is re-read from market_service.
- The AI-proposal path of the §C1 workflow (natural-language -> spec -> code)
  is an OWNER-GATED, DISCONNECTED seam: this service only accepts user-authored
  DSL source. The clarification/spec/backtest/approval steps run on whatever
  source the user provides; no LLM is called anywhere.
- User approval (§C3) is modelled by an explicit state machine:
  DRAFT -> (approve) -> APPROVED -> (promote) -> PROMOTED. Backtests and paper
  replays run on synthetic data for any state; PROMOTED only records that the
  user approved promotion to paper forward testing. There is NO live trading,
  NO broker egress, NO scheduler, NO autonomous activation (R-6/R-8).
- The version registry is IN-MEMORY ONLY: process restart clears it, by
  design, until an owner-approved persistence decision exists. This is stated
  in every API response that lists versions.

Offline-deterministic: bar content depends only on (symbol, timeframe, count,
end_bar_index). Tests pass explicit end_bar_index; when omitted the seeded
generator's current bucket is used (same convention as /api/v10/chartpro).
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, Field

from app.data.seeded_candles import candles_for
from app.engines.backtest_product import (
    BacktestRunConfig,
    DataPolicy,
    PortfolioLimits,
    RiskModel,
    SignalDecision,
    run_backtest,
)
from app.engines.execution_model import (
    ExecutionModelConfig,
    validate_bars,
)
from app.engines.forward_test_paper import (
    ForwardTestConfig,
    ForwardTestRuntime,
    MaturityRules,
    PaperDecision,
    PaperLedger,
)
from app.engines.strategy_dsl import (
    DSL_VERSION,
    Decision,
    PreparedProgram,
    Program,
    SeriesContext,
    compile_source,
    prepare,
    evaluate_at,
)
from app.engines.strategy_dsl.errors import DSLError

SERVICE_VERSION = "STRATEGY-LAB-1.0.0"

# From seeded candles (lightweight-charts keys) to the shared engine bar keys.
_SEEDED_TO_ENGINE = {
    "time": "ts",
    "open": "o",
    "high": "h",
    "low": "l",
    "close": "c",
    "volume": "v",
}


def seeded_to_engine_bars(seeded: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Convert seeded-candle rows to the shared {ts,o,h,l,c,v} bar contract."""
    out: List[Dict[str, Any]] = []
    for row in seeded:
        bar = {_SEEDED_TO_ENGINE[k]: row[k] for k in _SEEDED_TO_ENGINE}
        bar["v"] = float(bar["v"])
        out.append(bar)
    return out


def load_seeded_bars(
    symbol: str,
    timeframe: str,
    count: int,
    end_bar_index: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Deterministic SYNTHETIC series for the lab (see module docstring)."""
    seeded = candles_for(symbol, timeframe, count, end_bar_index=end_bar_index)
    bars = seeded_to_engine_bars(seeded)
    validate_bars(bars)
    return bars


class DslErrorView(BaseModel):
    """Machine-readable, safe DSL error surface (no raw tracebacks)."""

    code: str
    message: str
    line: Optional[int] = None
    col: Optional[int] = None


class CompileOutcome(BaseModel):
    ok: bool
    dsl_version: str = DSL_VERSION
    digest: Optional[str] = None
    errors: List[DslErrorView] = Field(default_factory=list)
    program_inputs: Dict[str, float] = Field(default_factory=dict)
    risk: Optional[Dict[str, Optional[float]]] = None
    expressions: Dict[str, str] = Field(default_factory=dict)


def compile_or_errors(source: str) -> CompileOutcome:
    try:
        program = compile_source(source)
    except DSLError as exc:
        return CompileOutcome(
            ok=False,
            errors=[
                DslErrorView(
                    code=getattr(exc, "code", "DSL_ERROR"),
                    message=str(exc),
                    line=getattr(exc, "line", None),
                    col=getattr(exc, "col", None),
                )
            ],
        )
    return _program_view(program)


def _program_view(program: Program) -> CompileOutcome:
    from app.engines.strategy_dsl.ast_nodes import (
        And,
        BinOp,
        Call,
        Cmp,
        InputRef,
        MtfRef,
        Not,
        Num,
        Or,
        SeriesBase,
        SymbolRef,
        UnaryOp,
    )

    def render(node: Any) -> str:
        if isinstance(node, Num):
            return repr(node.v)
        if isinstance(node, SeriesBase):
            return node.name
        if isinstance(node, MtfRef):
            return f"{node.tf}.{node.base}"
        if isinstance(node, SymbolRef):
            return f'sym("{node.symbol}").{node.base}'
        if isinstance(node, InputRef):
            return node.name
        if isinstance(node, BinOp):
            return f"{render(node.l)} {node.op} {render(node.r)}"
        if isinstance(node, Call):
            return f"{node.fn}({', '.join(render(a) for a in node.args)})"
        if isinstance(node, Cmp):
            return f"{render(node.l)} {node.op} {render(node.r)}"
        if isinstance(node, And):
            return f"({render(node.l)} AND {render(node.r)})"
        if isinstance(node, Or):
            return f"({render(node.l)} OR {render(node.r)})"
        if isinstance(node, Not):
            return f"NOT ({render(node.x)})"
        if isinstance(node, UnaryOp):
            return f"(-{render(node.x)})"
        return type(node).__name__

    risk_view: Optional[Dict[str, Optional[float]]] = None
    if program.risk is not None:
        risk_view = {
            "stop_loss_pct": program.risk.stop_loss_pct,
            "take_profit_pct": program.risk.take_profit_pct,
            "trailing_pct": program.risk.trailing_pct,
            "max_position_pct": program.risk.max_position_pct,
        }
    expressions = {
        "entry": render(program.entry),
        "exit": render(program.exit),
        "alert": render(program.alert),
    }
    return CompileOutcome(
        ok=True,
        digest=program.source_digest,
        program_inputs=dict(program.inputs),
        risk=risk_view,
        expressions=expressions,
    )


class DslBacktestAdapter:
    """StrategyAdapter implementation backed by a compiled DSL program.

    decide(index) uses ONLY the prepared series (data <= index is structural
    in the DSL runtime); fills are applied by the backtest engine with the
    configured no-look-ahead fill policy.
    """

    def __init__(self, program: Program, strategy_id: str = "dsl.strategy"):
        self.program = program
        self.strategy_id = strategy_id
        self._prepared: Optional[PreparedProgram] = None

    def prepare(self, bars: List[Mapping[str, Any]]) -> None:
        ctx = SeriesContext(
            open=[float(b["o"]) for b in bars],
            high=[float(b["h"]) for b in bars],
            low=[float(b["l"]) for b in bars],
            close=[float(b["c"]) for b in bars],
            volume=[float(b["v"]) for b in bars],
        )
        self._prepared = prepare(self.program, ctx)

    def decide(self, index: int) -> SignalDecision:
        if self._prepared is None:
            return SignalDecision()
        d: Decision = evaluate_at(self._prepared, index)
        risk = self.program.risk
        return SignalDecision(
            entry=bool(d.entry),
            exit=bool(d.exit),
            stop_loss_pct=risk.stop_loss_pct if risk else None,
            take_profit_pct=risk.take_profit_pct if risk else None,
            trailing_pct=risk.trailing_pct if risk else None,
            size_pct=risk.max_position_pct if risk else None,
        )


class DslForwardAdapter:
    """PaperAdapter implementation backed by a compiled DSL program."""

    def __init__(self, program: Program, strategy_id: str = "dsl.strategy"):
        self.program = program
        self.strategy_id = strategy_id
        self._prepared: Optional[PreparedProgram] = None

    def prepare(self, bars: List[Mapping[str, Any]]) -> None:
        ctx = SeriesContext(
            open=[float(b["o"]) for b in bars],
            high=[float(b["h"]) for b in bars],
            low=[float(b["l"]) for b in bars],
            close=[float(b["c"]) for b in bars],
            volume=[float(b["v"]) for b in bars],
        )
        self._prepared = prepare(self.program, ctx)

    def decide(self, index: int) -> PaperDecision:
        if self._prepared is None:
            return PaperDecision()
        d = evaluate_at(self._prepared, index)
        risk = self.program.risk
        # UNIT CONVENTION (documented cross-engine difference): the backtest
        # engine's SignalDecision.size_pct is a PERCENT (0..100) while the
        # paper runtime's PaperDecision.size_pct is a FRACTION (0..1). The DSL
        # risk block is percent-denominated (max_position_pct), so this adapter
        # converts. Both engines apply IDENTICAL fee/spread/slippage arithmetic
        # via the shared execution_model for a given config.
        frac = (risk.max_position_pct / 100.0) if risk and risk.max_position_pct else None
        if frac is not None:
            frac = max(0.0, min(1.0, frac))
        return PaperDecision(
            entry=bool(d.entry),
            exit=bool(d.exit),
            stop_loss_pct=risk.stop_loss_pct if risk else None,
            take_profit_pct=risk.take_profit_pct if risk else None,
            trailing_pct=risk.trailing_pct if risk else None,
            size_pct=frac,
        )


class ExecutionOverrides(BaseModel):
    """Caller-tunable execution assumptions (§D2) — all optional, documented."""

    model_config = {"frozen": True}

    initial_capital: float = Field(default=100_000.0, gt=0)
    commission_pct: float = Field(default=0.0, ge=0, le=10)
    spread_pct: float = Field(default=0.0, ge=0, le=10)
    slippage_pct: float = Field(default=0.0, ge=0, le=10)
    latency_bars: int = Field(default=0, ge=0, le=100)
    lot_size: float = Field(default=1.0, gt=0)
    leverage: float = Field(default=1.0, ge=1.0, le=100.0)
    fill_policy: str = Field(default="NEXT_BAR_OPEN", pattern="^(NEXT_BAR_OPEN|SAME_BAR_CLOSE)$")
    intrabar_tp_sl: bool = False

    def to_config(self) -> ExecutionModelConfig:
        return ExecutionModelConfig(
            initial_capital=self.initial_capital,
            commission_pct=self.commission_pct,
            spread_pct=self.spread_pct,
            slippage_pct=self.slippage_pct,
            latency_bars=self.latency_bars,
            lot_size=self.lot_size,
            leverage=self.leverage,
            fill_policy=self.fill_policy,  # type: ignore[arg-type]
            intrabar_tp_sl=self.intrabar_tp_sl,
        )


def run_backtest_on_seeded(
    program: Program,
    *,
    symbol: str = "FOLAD",
    timeframe: str = "1D",
    count: int = 200,
    end_bar_index: Optional[int] = None,
    execution: ExecutionOverrides | None = None,
    run_id: str = "strategylab",
) -> Dict[str, Any]:
    """Compile-checked program + synthetic series -> full product backtest."""
    bars = load_seeded_bars(symbol, timeframe, count, end_bar_index)
    exec_cfg = (execution or ExecutionOverrides()).to_config()
    risk_view = program.risk
    risk = RiskModel(
        stop_loss_pct=risk_view.stop_loss_pct if risk_view else None,
        take_profit_pct=risk_view.take_profit_pct if risk_view else None,
        trailing_pct=risk_view.trailing_pct if risk_view else None,
        max_position_pct=(risk_view.max_position_pct if risk_view and risk_view.max_position_pct else 100.0),
    )
    config = BacktestRunConfig(
        run_id=run_id,
        execution=exec_cfg,
        risk=risk,
        portfolio=PortfolioLimits(),
        data_policy=DataPolicy(min_bars=50),
        data_trust_label="SYNTHETIC_OR_PAPER",
        notes="strategy-lab seeded-candle backtest; bar-based simulation, never real-tick",
    )
    adapter = DslBacktestAdapter(program, strategy_id=f"dsl:{program.source_digest[:12]}")
    result = run_backtest({symbol: bars}, {symbol: adapter}, config)
    return {
        "run_id": result.run_id,
        "engine_version": result.engine_version,
        "execution_model_version": result.execution_model_version,
        "result_digest": result.result_digest(),
        "symbol": symbol,
        "timeframe": timeframe,
        "bars_used": len(bars),
        "report": result.report.model_dump(mode="json"),
        "trades_count": len(result.trades),
        "limitations": result.limitations,
        "data_quality": [
            {
                "symbol": dq.symbol if hasattr(dq, "symbol") else dq.get("symbol"),
                "refusals": dq.refusals if hasattr(dq, "refusals") else dq.get("refusals"),
            }
            for dq in result.data_quality
        ],
        "data_trust_label": result.data_trust_label,
    }


def run_paper_replay_on_seeded(
    program: Program,
    *,
    symbol: str = "FOLAD",
    timeframe: str = "1D",
    count: int = 200,
    end_bar_index: Optional[int] = None,
    execution: ExecutionOverrides | None = None,
    strategy_name: str = "dsl.strategy",
) -> Dict[str, Any]:
    """§E paper forward test replayed over a synthetic window.

    HONESTY: this is a paper SIMULATION over historical synthetic bars, NOT a
    live forward observation. Live forward observation requires owner-gated
    runtime wiring and stays disconnected (R-6 dormant scheduler).
    """
    bars = load_seeded_bars(symbol, timeframe, count, end_bar_index)
    exec_cfg = (execution or ExecutionOverrides()).to_config()
    config = ForwardTestConfig(
        run_id=f"paper-{program.source_digest[:12]}",
        strategy_id=strategy_name,
        strategy_version=f"dsl-{program.source_digest[:12]}",
        dsl_version=DSL_VERSION,
        execution=exec_cfg,
        data_trust_label="SYNTHETIC_OR_PAPER",
        maturity=MaturityRules(min_bars_after_signal=20),
    )
    ledger = PaperLedger()
    runtime = ForwardTestRuntime(config, ledger)
    adapter = DslForwardAdapter(program, strategy_id=strategy_name)
    runtime.process_bars(symbol, bars, adapter)
    summary = runtime.summary()
    return {
        "summary": summary.model_dump(mode="json"),
        "summary_digest": summary.digest(),
        "ledger_len": len(ledger),
        "ledger_chain_ok": ledger.verify_chain()[0],
        "mode": "PAPER_REPLAY_OVER_SYNTHETIC_WINDOW",
        "not_live_note": (
            "بازپخش کاغذی روی داده سینتتیک است؛ مشاهده forward زنده نیاز به "
            "اتصال runtime دارد و عمداً قطع مانده است (R-6)"
        ),
    }


class VersionRecord(BaseModel):
    version_id: str
    name: str
    source_digest: str
    dsl_version: str
    status: str = Field(pattern="^(DRAFT|APPROVED|PROMOTED)$")
    created_at_ts: int
    approved_at_ts: Optional[int] = None
    promoted_at_ts: Optional[int] = None


class StrategyVersionRegistry:
    """In-memory §C3 approval state machine (see module docstring honesty)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, VersionRecord] = {}
        self._counter = 0

    def register(self, name: str, source_digest: str, approve: bool, now_ts: int) -> VersionRecord:
        with self._lock:
            self._counter += 1
            rec = VersionRecord(
                version_id=f"v{self._counter:04d}-{source_digest[:8]}",
                name=name,
                source_digest=source_digest,
                dsl_version=DSL_VERSION,
                status="APPROVED" if approve else "DRAFT",
                created_at_ts=now_ts,
                approved_at_ts=now_ts if approve else None,
            )
            self._records[rec.version_id] = rec
            return rec

    def promote(self, version_id: str, now_ts: int) -> VersionRecord:
        with self._lock:
            rec = self._records.get(version_id)
            if rec is None:
                raise KeyError("version_not_found")
            if rec.status != "APPROVED":
                raise ValueError("promotion_requires_user_approved_state")
            rec.status = "PROMOTED"
            rec.promoted_at_ts = now_ts
            return rec

    def list(self) -> List[VersionRecord]:
        with self._lock:
            return sorted(self._records.values(), key=lambda r: r.version_id)

    def get(self, version_id: str) -> Optional[VersionRecord]:
        with self._lock:
            return self._records.get(version_id)


version_registry = StrategyVersionRegistry()
