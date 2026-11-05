"""ai2_generation_api.py — WAVE-K (OA-3, owner directive 2026-11-05)

Governed AI-2 generation surface (prefix /api/v10/ai2, additive to the v10
family). Wires the WAVE-K governed generation seam
(app.services.ai2_generation) into the EXISTING governance pipeline:

  GET  /posture                            — honest read-only gate posture
  POST /generate                           — NL -> clarification -> typed spec
                                             -> RSL-1 -> deterministic eval ->
                                             versioned DRAFT candidate
  GET  /candidates                         — versioned candidate list (bounded)
  GET  /candidates/{candidate_id}          — one candidate + tamper verdict
  POST /candidates/{candidate_id}/approve  — HUMAN approval (named approver)
  POST /candidates/{candidate_id}/promote  — HUMAN promotion (paper-forward
                                             eligibility only)
  GET  /runs                               — append-only run ledger tail

Honesty envelope (same discipline as the other v10 routers):
- generation evaluation ALWAYS runs on the deterministic seeded SYNTHETIC
  series; the execution-mode label is SYNTHETIC_OR_PAPER on every payload;
- the model can NEVER approve or promote: both transitions are explicit
  human calls that require a named approver (server-enforced);
- the candidate registry and run ledger are IN-MEMORY ONLY (bounded) and
  disclosed as such on every listing; persistence is an owner-gated decision;
- no live trading, no broker egress, no external notification, no scheduler,
  no live data path (R-6/R-8/R-9); a configured remote provider refuses
  generation without an explicit TEST transport (synthetic/paper-only seam);
- with AI2_ENABLED=0 (the committed default) every generate call returns the
  honest ``gated_not_executed`` outcome (error_code ``ai2_disabled``) and
  nothing executes.

Gates unchanged: AI2_ENABLED=0 / verified=False / SYNTHETIC_OR_PAPER.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.ai2_generation import (
    ClarificationAnswer,
    GenerationRequest,
    ai2_generation_service,
)

router = APIRouter(prefix="/api/v10/ai2", tags=["ai2-generation"])

_LEDGER_TAIL = 32


class ClarificationBody(BaseModel):
    """One bounded clarification answer (server-side clarification stage)."""

    key: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]{0,39}$")
    value: str = Field(min_length=1, max_length=200)


class GenerateBody(BaseModel):
    """Bounded generation request body (mirrors the service contract)."""

    question: str = Field(min_length=1, max_length=2000)
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(default="1D", pattern=r"^(1m|5m|15m|1h|1D)$")
    bar_count: int = Field(default=200, ge=50, le=500)
    end_bar_index: Optional[int] = Field(default=None, ge=0)
    clarifications: List[ClarificationBody] = Field(default_factory=list, max_length=8)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=128)
    parent_run_id: Optional[str] = Field(default=None, max_length=128)
    hypothesis_id: Optional[str] = Field(default=None, max_length=128)
    data_trust_state: str = Field(default="synthetic", max_length=64)


class ApproverBody(BaseModel):
    """Named human approver — the ONLY authority over approve/promote."""

    approver: str = Field(min_length=4, max_length=128)


def _typed_422(code: str, en: str, fa: str, **extra: Any) -> HTTPException:
    detail: Dict[str, Any] = {"error": code, "message_en": en, "message_fa": fa}
    detail.update(extra)
    return HTTPException(422, detail)


def _honesty_envelope() -> Dict[str, Any]:
    return {
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "evaluation_series": "deterministic seeded synthetic candles (app.data.seeded_candles)",
        "model_authority": "none over approval/promotion; named human approver required",
        "model_output_surface": "typed spec schema only; deterministic emitter renders all code",
        "registry_persistence": "in-memory-only; restart clears (owner-gated persistence decision)",
        "egress": "none; no broker, no external notification, no scheduler (R-6/R-8/R-9)",
        "remote_provider_policy": "generation is synthetic/paper-only; remote providers refuse without an explicit TEST transport",
    }


def _candidate_view(rec: Any) -> Dict[str, Any]:
    view = rec.model_dump(mode="json")
    view["honesty"] = _honesty_envelope()
    return view


# ---------------------------------------------------------------------------
# Posture (read-only; honest even while disabled)
# ---------------------------------------------------------------------------
@router.get("/posture")
async def posture() -> Dict[str, Any]:
    return {**ai2_generation_service.posture(), "honesty": _honesty_envelope()}


# ---------------------------------------------------------------------------
# Generation (the governed seam; fail-closed gates inside the service)
# ---------------------------------------------------------------------------
@router.post("/generate")
async def generate(body: GenerateBody) -> Dict[str, Any]:
    request = GenerationRequest(
        question=body.question,
        symbol=body.symbol,
        timeframe=body.timeframe,
        bar_count=body.bar_count,
        end_bar_index=body.end_bar_index,
        clarifications=[
            ClarificationAnswer(key=c.key, value=c.value) for c in body.clarifications
        ],
        idempotency_key=body.idempotency_key,
        data_trust_state=body.data_trust_state,
    )
    outcome = await ai2_generation_service.generate(
        request,
        parent_run_id=body.parent_run_id,
        hypothesis_id=body.hypothesis_id,
    )
    payload = outcome.model_dump(mode="json")
    payload["honesty"] = _honesty_envelope()
    return payload


# ---------------------------------------------------------------------------
# Candidate surfaces (versioned; human approval required for transitions)
# ---------------------------------------------------------------------------
@router.get("/candidates")
async def list_candidates() -> Dict[str, Any]:
    records = ai2_generation_service.candidates.list()
    return {
        "candidates": [_candidate_view(r) for r in records],
        "count": len(records),
        "note": "in-memory-only registry; restart clears it (owner-gated persistence decision)",
        "honesty": _honesty_envelope(),
    }


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str) -> Dict[str, Any]:
    rec = ai2_generation_service.candidates.get(candidate_id)
    if rec is None:
        raise HTTPException(404, detail={"error": "candidate_not_found"})
    return _candidate_view(rec)


@router.post("/candidates/{candidate_id}/approve")
async def approve_candidate(candidate_id: str, body: ApproverBody) -> Dict[str, Any]:
    from datetime import datetime, timezone

    try:
        rec = ai2_generation_service.approve_candidate(
            candidate_id, body.approver, datetime.now(timezone.utc)
        )
    except KeyError:
        raise HTTPException(404, detail={"error": "candidate_not_found"}) from None
    except ValueError as exc:
        raise _typed_422(str(exc), str(exc), str(exc)) from None
    return _candidate_view(rec)


@router.post("/candidates/{candidate_id}/promote")
async def promote_candidate(candidate_id: str, body: ApproverBody) -> Dict[str, Any]:
    from datetime import datetime, timezone

    try:
        rec = ai2_generation_service.promote_candidate(
            candidate_id, body.approver, datetime.now(timezone.utc)
        )
    except KeyError:
        raise HTTPException(404, detail={"error": "candidate_not_found"}) from None
    except ValueError as exc:
        # promotion_requires_approved_state / candidate_tampered / approver_required
        raise _typed_422(str(exc), str(exc), str(exc)) from None
    view = _candidate_view(rec)
    view["promotion_scope"] = (
        "PAPER-FORWARD ELIGIBILITY ONLY — never live, never broker, never external "
        "notification; the promoted source may be exercised through the existing "
        "Strategy Lab paper flows by a human user."
    )
    return view


# ---------------------------------------------------------------------------
# Run ledger tail (append-only; immutable records)
# ---------------------------------------------------------------------------
@router.get("/runs")
async def list_runs() -> Dict[str, Any]:
    records = ai2_generation_service.ledger.records
    tail = records[-_LEDGER_TAIL:]
    return {
        "records": [r.model_dump(mode="json") for r in tail],
        "total": len(records),
        "truncated_to": _LEDGER_TAIL,
        "append_only": True,
        "honesty": _honesty_envelope(),
    }
