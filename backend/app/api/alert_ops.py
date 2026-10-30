"""D-AI-30 in-product alert-operations API (CONSOL-GOV-41 A2/A3).

Routes are READ-mostly product surfaces plus owner-gated operations:
- ``GET /api/alerts/inbox`` — the in-product alert inbox. Every row carries
  the exact ``SYNTHETIC / PAPER — NOT LIVE`` label. Only the minimum-necessary
  human-readable fields are returned (decision 7): evidence IDs and full alert
  records stay internal database references.
- ``GET /api/alerts/ops/status`` — observability (decision 6): budgets, queue
  depth, delivery/dead-letter/budget-refusal/retry-exhaustion counters,
  kill-switch states and dispatcher self-failure visibility. No credentials.
- ``POST /api/alerts/ops/kill-switch`` — audited override transitions
  (decision 5); requires the API key (fail-closed), like every sensitive route.
- ``POST /api/alerts/ops/dispatch`` — one explicit dispatcher tick
  (kill switches and budgets still enforced); requires the API key.
- ``GET /api/alerts/ops/dead-letter`` — dead-letter inspection; requires the API key.

No external egress exists anywhere on this router (decision 3).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import require_api_key
from app.services.alert_operations import service as alert_ops_service

router = APIRouter(prefix="/api/alerts", tags=["alert-ops"])

SENSITIVE_DEPENDENCIES = [Depends(require_api_key)]

service = alert_ops_service


class KillSwitchRequest(BaseModel):
    scope: str = Field(min_length=1, max_length=128)
    state: str = Field(pattern="^(ENGAGED|RELEASED)$")
    reason: str = Field(default="", max_length=500)


@router.get("/inbox")
def alert_inbox(
    limit: int = Query(default=50, ge=1, le=200),
    kind: str | None = Query(default=None, max_length=64),
) -> dict[str, Any]:
    """In-product inbox: labeled, minimum-necessary rows only."""
    rows = service.store.inbox_rows(limit=limit, kind=kind)
    return {
        "ok": True,
        "label": "SYNTHETIC / PAPER — NOT LIVE",
        "count": len(rows),
        "items": rows,
    }


@router.get("/ops/status")
def alert_ops_status() -> dict[str, Any]:
    return {"ok": True, "health": service.health()}


@router.post("/ops/kill-switch", dependencies=SENSITIVE_DEPENDENCIES)
def set_kill_switch(body: KillSwitchRequest) -> dict[str, Any]:
    try:
        result = service.set_kill_switch(body.scope.strip(), body.state, actor="api", reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.post("/ops/dispatch", dependencies=SENSITIVE_DEPENDENCIES)
def manual_dispatch() -> dict[str, Any]:
    return {"ok": True, "result": service.tick()}


@router.get("/ops/dead-letter", dependencies=SENSITIVE_DEPENDENCIES)
def dead_letter(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return {
        "ok": True,
        "count": service.store.dead_letter_count(),
        "items": service.store.dead_letter_rows(limit=limit),
    }
