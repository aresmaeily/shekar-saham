"""Scheduler job registry (WAVE-M, OA-4; 2026-11-06).

Additive module — the closed registry of job handlers the internal
scheduler may run, plus the composition-root factory that builds it.

Design invariants (each is a continuation of an EXISTING governed seam —
nothing here modifies any prior wave's module):

- ONE built-in job type today: ``research_loop``. It delegates to the
  EXISTING ``AI2ResearchLoopRunner`` (AI2-B) over a transport-less
  ``AI2Service``. Because no transport is injected, the service's own
  fail-closed gates govern every run — with the committed defaults the
  outcome is an honest ``gated_not_executed`` ledger record. The scheduler
  therefore cannot open any path the AI-2 gates do not already open.
- The handler NEVER reads or writes settings, NEVER constructs a network
  transport, and NEVER touches AI2_ENABLED — the runner contract from
  REM1/AI2-F is preserved verbatim.
- The handler payload is validated into the EXISTING ``AI2ResearchRunInput``
  contract (closed task set, 64-hex input snapshot, task/request
  consistency). Anything that does not validate is refused BEFORE the
  loop is invoked; nothing is ledgered for a malformed payload.
- Returned summaries are bounded and honest: outcome label, ledger status,
  execution label, refusal reason, elapsed wall seconds — never raw model
  text, never a fabricated fact, never a live/verified claim.
- Registry construction is injectable for tests (``build_default_handlers``
  takes optional overrides); the closed job-type set refuses unknown
  names at enqueue time (scheduler-side check) and unknown BUILT-IN types
  are simply absent from the registry.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from app.domain.ai2_governance import AI2BudgetSpec, AI2RunLedger
from app.domain.run_governance import RunContext
from app.services.ai2_research_loop import AI2ResearchLoopRunner, AI2ResearchRunInput
from app.services.ai2_service import AI2Request, AI2Service

__all__ = [
    "BUILTIN_JOB_TYPES",
    "build_default_handlers",
    "research_loop_handler",
]

#: The closed built-in job-type set. The scheduler refuses any other name.
BUILTIN_JOB_TYPES = frozenset({"research_loop"})

#: Session budget for one scheduled research-loop run (engineering-authority
#: ceilings, D-AI-24 class): exactly ONE provider invocation per scheduled
#: run, honest refusals otherwise.
_SESSION_BUDGET = AI2BudgetSpec(
    max_provider_invocations=1,
    max_iterations=1,
    max_wall_seconds=60,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_str(payload: Dict[str, Any], key: str, *, max_len: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing_or_malformed:{key}")
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"oversized:{key}")
    return value


def _validate_payload(payload: Dict[str, Any]) -> AI2ResearchRunInput:
    """Validate a scheduler payload into the governed run-input contract.

    Raises ValueError (refusal codes preserved) BEFORE anything executes.
    """
    question = _require_str(payload, "question", max_len=2000)
    task = _require_str(payload, "task", max_len=64)
    record_id = _require_str(payload, "record_id", max_len=128)
    run_id = _require_str(payload, "run_id", max_len=128)
    policy_version = _require_str(payload, "policy_version", max_len=64)
    snapshot = _require_str(payload, "input_snapshot_sha256", max_len=64)
    symbol = payload.get("symbol")
    if symbol is not None and (not isinstance(symbol, str) or len(symbol) > 64):
        raise ValueError("malformed:symbol")
    language = payload.get("language", "fa")
    if not isinstance(language, str) or len(language) > 16:
        raise ValueError("malformed:language")
    request = AI2Request(
        task=task,  # type: ignore[arg-type]  # validated by AI2Request itself
        question=question,
        symbol=symbol,
        language=language,
    )
    return AI2ResearchRunInput(
        record_id=record_id,
        run_id=run_id,
        policy_version=policy_version,
        task=task,
        request=request,
        input_snapshot_sha256=snapshot,
        notes="scheduled_research_run",
    )


async def research_loop_handler(
    payload: Dict[str, Any],
    *,
    run_provenance: Optional[Dict[str, Any]] = None,
    runner: Optional[AI2ResearchLoopRunner] = None,
) -> Dict[str, Any]:
    """Execute ONE bounded governed research-loop run (synthetic/paper).

    The transport argument of ``execute_run`` is deliberately LEFT AT ITS
    DEFAULT (None): with no injected transport the AI-2 service's own
    fail-closed gates decide — production provider seams never execute
    here, and with the committed default gates the honest outcome is
    ``gated_not_executed``. This handler has no authority to change that.
    """
    prov = run_provenance or {}
    try:
        run_input = _validate_payload(payload)
    except ValueError as exc:
        return {
            "job": "research_loop",
            "executed": False,
            "outcome": "payload_refused",
            "refusal_reason": str(exc),
            "execution_domain": "SYNTHETIC_OR_PAPER",
            "note": "payload failed governed validation; nothing ran, nothing ledgered",
        }

    if runner is None:
        runner = AI2ResearchLoopRunner(
            AI2Service(),
            AI2RunLedger(),
            _SESSION_BUDGET,
            None,
            now_utc=_utcnow,
        )

    # The REAL application market-service singleton (context building only);
    # imported lazily to avoid import cycles at module import time.
    from app.services.market_service import market_service

    context = RunContext(
        run_id=run_input.run_id,
        run_kind="AI2_INTERPRETATION",
        policy_version=run_input.policy_version,
        created_at_utc=_utcnow(),
    )
    outcome = await runner.execute_run(run_input, market_service, run_context=context)
    summary: Dict[str, Any] = {
        "job": "research_loop",
        "outcome": outcome.outcome,
        "ok": outcome.ok,
        "ledger_status": outcome.ledger_status,
        "execution_label": outcome.execution_label,
        "refusal_reason": outcome.refusal_reason,
        "elapsed_wall_seconds": round(outcome.elapsed_wall_seconds, 6),
        "duplicate_class": outcome.duplicate_class,
        "record_id": outcome.record.record_id if outcome.record is not None else None,
        "execution_domain": "SYNTHETIC_OR_PAPER",
        "scheduler_run_id": prov.get("run_id"),
        "attempt": prov.get("attempt"),
        "note": (
            "delegated to the governed research-loop runner; its own fail-closed "
            "gates (synthetic/paper-only transport policy, budgets, ledger) decided "
            "the outcome — the scheduler has no authority over them"
        ),
    }
    # Bounded outcome: strip any accidental oversized content defensively.
    bounded = json.dumps(summary, ensure_ascii=False, default=str)
    if len(bounded.encode("utf-8")) > 65536:
        return {"job": "research_loop", "outcome": outcome.outcome, "truncated": True}
    return summary


def build_default_handlers(
    overrides: Optional[Dict[str, Callable[..., Awaitable[Dict[str, Any]]]]] = None,
) -> Dict[str, Callable[..., Awaitable[Dict[str, Any]]]]:
    """The closed default registry (composition-root factory).

    ``overrides`` exists ONLY for deterministic unit tests (inject a
    stub runner factory); production wiring calls it with no arguments.
    """
    if overrides:
        handlers: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {}
        for name in sorted(BUILTIN_JOB_TYPES):
            handlers[name] = overrides.get(name, research_loop_handler)
        return handlers
    return {"research_loop": research_loop_handler}
