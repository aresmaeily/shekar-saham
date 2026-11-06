"""Internal scheduler HTTP surface (WAVE-M, OA-4; 2026-11-06).

Additive router — ``/api/v10/scheduler``. The governed local scheduler's
posture, enqueue, run-history, control (pause/resume/stop) and kill-switch
endpoints. Bounded, honest, and egress-free:

- The scheduler behind this router is LOCAL and synthetic/paper-only. It
  has NO external notification outlet, NO broker path, and NO authority to
  mutate production or promote candidates. Its only effect is to run
  registered bounded research handlers under their own governance and to
  record an append-only run history.
- Fail-closed posture: with the committed default ``SCHEDULER_ENABLED=0``
  every mutating endpoint refuses with an honest, machine-readable code
  (``scheduler_disabled``); nothing is scheduled, nothing runs.
- This file deliberately contains no token naming the governed generation
  seam (the G2 counter-pin confines such references to exactly one file);
  the router is GENERIC — job types come from the scheduler's closed
  registry, and this surface never hard-codes any particular handler.
- No background task is spawned here (the service owns its worker); no
  network client is constructed anywhere in this module.
"""

from __future__ import annotations

from typing import Any, Dict, Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.services.internal_scheduler import (
    PAYLOAD_MAX_BYTES,
    SchedulerRefused,
    get_scheduler,
)

router = APIRouter(prefix="/api/v10/scheduler", tags=["scheduler"])

_REFUSAL_STATUS = {
    "scheduler_disabled": 503,
    "scheduler_not_started": 409,
    "scheduler_stopped": 409,
    "scheduler_bounds_invalid": 400,
    "kill_switch_engaged": 423,
    "kill_switch_state_malformed": 400,
    "unknown_job_type": 400,
    "idempotency_conflict": 409,
    "idempotency_key_malformed": 400,
    "queue_full": 429,
    "payload_must_be_object": 400,
    "payload_not_canonicalizable": 400,
    "payload_oversized": 413,
    "pause_requires_running": 409,
    "resume_requires_paused": 409,
    "job_type_already_registered": 409,
}


def _honesty_envelope() -> Dict[str, Any]:
    return {
        "local_only": "زمان‌بند داخلی فقط محلی است؛ هیچ اعلان بیرونی، بروکر یا خروجی شبکه‌ای ندارد",
        "no_egress_note": "no external notification egress exists by construction",
        "synthetic_paper_only": "execution domain is SYNTHETIC_OR_PAPER; handlers run under their own governance",
        "fail_closed_gate": "SCHEDULER_ENABLED default 0 — every mutating endpoint refuses while the gate is closed",
        "history_append_only": "run history is an append-only event ledger with row digests; nothing is rewritten",
        "bounded": f"queue depth, concurrency, per-run timeout, attempts, payload (<={PAYLOAD_MAX_BYTES} bytes) and output are hard-capped",
    }


async def _ensure_started(scheduler: Any) -> None:
    """On-demand start (directive: start from on-demand execution + default
    disabled). The gate SCHEDULER_ENABLED remains the ONLY authority:
    ``start()`` itself refuses while disabled; a explicitly-stopped or
    kill-switched scheduler is never resurrected here."""
    if scheduler.state == "created" and scheduler.posture()["enabled"]:
        try:
            await scheduler.start()
        except SchedulerRefused:
            pass  # honest refusal surfaces through the normal flow


class EnqueueBody(BaseModel):
    job_type: str = Field(min_length=1, max_length=64)
    payload: Dict[str, Any]
    idempotency_key: str = Field(min_length=1, max_length=128)
    actor: str = Field(default="api-user", min_length=1, max_length=64)

    @field_validator("job_type")
    @classmethod
    def _job_type_shape(cls, v: str) -> str:
        v = v.strip()
        if not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError("job_type_malformed")
        return v


class ControlBody(BaseModel):
    action: Literal["pause", "resume", "stop"]
    drain: bool = False
    actor: str = Field(min_length=1, max_length=64)
    reason: str = Field(default="", max_length=500)


class KillSwitchBody(BaseModel):
    state: Literal["ENGAGE", "RELEASE"]
    actor: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=500)


@router.get("/posture")
async def scheduler_posture() -> Dict[str, Any]:
    """Honest scheduler posture (read-only; always callable)."""
    scheduler = get_scheduler()
    return {
        "posture": scheduler.posture(),
        "honesty": _honesty_envelope(),
    }


@router.post("/runs")
async def scheduler_enqueue(body: EnqueueBody) -> Any:
    """Enqueue one bounded run (idempotency-key protected)."""
    scheduler = get_scheduler()
    await _ensure_started(scheduler)
    try:
        result = await scheduler.enqueue(
            body.job_type,
            body.payload,
            idempotency_key=body.idempotency_key,
            actor=body.actor,
        )
    except SchedulerRefused as exc:
        status = _REFUSAL_STATUS.get(exc.code, 400)
        return JSONResponse(
            status_code=status,
            content={
                "detail": {
                    "code": exc.code,
                    "message": exc.detail or "scheduler refused the request honestly",
                    "honesty": _honesty_envelope(),
                }
            },
        )
    return {"ok": True, "result": result, "honesty": _honesty_envelope()}


@router.get("/runs")
async def scheduler_runs(limit: int = 50) -> Dict[str, Any]:
    """Derived per-run states from the append-only history (bounded)."""
    scheduler = get_scheduler()
    bounded = max(1, min(int(limit), 200))
    return {
        "runs": scheduler.runs_index(bounded),
        "honesty": _honesty_envelope(),
    }


@router.get("/runs/{run_id}")
async def scheduler_run_detail(run_id: str) -> Any:
    """Full event history of one run (immutability is observable here)."""
    scheduler = get_scheduler()
    detail = scheduler.run_detail(run_id.strip())
    if detail is None:
        return JSONResponse(
            status_code=404,
            content={"detail": {"code": "run_not_found", "run_id": run_id.strip()[:128]}},
        )
    return {"run": detail, "honesty": _honesty_envelope()}


@router.post("/control")
async def scheduler_control(body: ControlBody) -> Any:
    """pause / resume / stop — the scheduler's bounded lifecycle controls."""
    scheduler = get_scheduler()
    await _ensure_started(scheduler)
    # Gate-first honesty (WAVE-M QA M1): the closed gate is the PRIMARY
    # refusal reason for every mutating action — including lifecycle
    # controls — not a secondary state-machine code.
    if not scheduler.posture()["enabled"]:
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "scheduler_disabled",
                    "message": "scheduler gate closed (SCHEDULER_ENABLED=0)",
                    "honesty": _honesty_envelope(),
                }
            },
        )
    try:
        if body.action == "pause":
            result = await scheduler.pause(actor=body.actor)
        elif body.action == "resume":
            result = await scheduler.resume(actor=body.actor)
        else:
            result = await scheduler.stop(actor=body.actor, drain=body.drain)
    except SchedulerRefused as exc:
        status = _REFUSAL_STATUS.get(exc.code, 400)
        return JSONResponse(
            status_code=status,
            content={
                "detail": {
                    "code": exc.code,
                    "message": exc.detail or "scheduler refused the control action honestly",
                    "honesty": _honesty_envelope(),
                }
            },
        )
    return {"ok": True, "result": result, "honesty": _honesty_envelope()}


@router.post("/kill-switch")
async def scheduler_kill_switch(body: KillSwitchBody) -> Any:
    """Kill-switch: ENGAGE kills active runs and refuses enqueue; RELEASE re-arms."""
    scheduler = get_scheduler()
    await _ensure_started(scheduler)
    try:
        result = await scheduler.set_kill_switch(
            body.state, actor=body.actor, reason=body.reason
        )
    except SchedulerRefused as exc:
        status = _REFUSAL_STATUS.get(exc.code, 400)
        return JSONResponse(
            status_code=status,
            content={
                "detail": {
                    "code": exc.code,
                    "message": exc.detail or "kill-switch refused the request honestly",
                    "honesty": _honesty_envelope(),
                }
            },
        )
    return {"ok": True, "result": result, "honesty": _honesty_envelope()}


@router.get("/history/verify")
async def scheduler_history_verify() -> Dict[str, Any]:
    """Verify every row digest in the run history (fail-closed on tamper)."""
    scheduler = get_scheduler()
    verification = scheduler.verify_history()
    return {"verification": verification, "honesty": _honesty_envelope()}
