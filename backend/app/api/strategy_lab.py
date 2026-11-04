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
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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


class SourceBody(BaseModel):
    source: str = Field(min_length=1, max_length=8192)
    name: str = Field(default="dsl.strategy", max_length=64)


class ValidateBody(SourceBody):
    pass


class BacktestBody(SourceBody):
    symbol: str = Field(default="FOLAD", max_length=32)
    timeframe: str = Field(default="1D", pattern="^(1m|5m|15m|1h|1D)$")
    count: int = Field(default=200, ge=50, le=1000)
    end_bar_index: Optional[int] = Field(default=None, ge=0)
    execution: svc.ExecutionOverrides = Field(default_factory=svc.ExecutionOverrides)


class RegisterBody(SourceBody):
    approve: bool = False
    now_ts: Optional[int] = Field(default=None, ge=0)


class PromoteBody(BaseModel):
    now_ts: Optional[int] = Field(default=None, ge=0)


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


@router.post("/backtest")
async def backtest_strategy(body: BacktestBody) -> Dict[str, Any]:
    outcome = svc.compile_or_errors(body.source)
    if not outcome.ok:
        raise HTTPException(422, {"error": "DSL_ERROR", "errors": [e.model_dump() for e in outcome.errors]})
    from app.engines.strategy_dsl import compile_source

    try:
        program = compile_source(body.source)
    except Exception as exc:  # pragma: no cover - compile_or_errors already gated
        raise _dsl_http_error(exc) from exc
    try:
        payload = svc.run_backtest_on_seeded(
            program,
            symbol=body.symbol,
            timeframe=body.timeframe,
            count=body.count,
            end_bar_index=body.end_bar_index,
            execution=body.execution,
        )
    except ValueError as exc:
        raise HTTPException(422, {"error": "BACKTEST_INPUT_ERROR", "message": str(exc)}) from exc
    payload["synthetic_note"] = _SYNTHETIC_NOTE
    payload["trust_envelope"] = _trust_envelope()
    return payload


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
