"""AI-2 second-stage analysis service — Category A offline scaffold.

Governance position (see docs/active/REM1_AI2A_IMPLEMENTATION_RECORD.md):
- The authoritative AI-2 definition lives in the 2026-10-02 owner amendment
  corpus (NOT_SYNCED in this repository). This module implements ONLY the
  Category A scope that is safe to build and test offline: typed and bounded
  request contracts, deterministic-domain integration (the deterministic
  stage-1 analysis feeds the provider prompt), strict output-schema
  validation, provenance metadata, deterministic failure handling,
  trust-state enforcement, and fail-closed gates.
- Real-data AI-2 execution is blocked behind three independent gates:
    1. ``is_verified_live(data_trust)`` — the repository-wide LIVE gate.
       No caller can mint ``live_verified=True`` here
       (config.build_data_trust_context hard-codes verified=False), so the
       production path is structurally unreachable until a future
       independent provider-verification boundary exists AND G2 independent
       validation + owner acceptance are recorded by the owner.
    2. ``AI2_ENABLED`` configuration (default: off).
    3. data-trust state enforcement — missing or ``unavailable`` market data
       is refused before any provider invocation (fail-closed).
- Model output is interpretive/advisory ONLY and must validate against
  ``AI2Interpretation``. Deterministic financial values come exclusively
  from the existing domain layer (AIContextBuilder over market_service plus
  the deterministic stage-1 FallbackAIProvider analysis) and are never
  overwritten by model text. ``AI2Interpretation`` forbids unknown fields.
- Provider invocation reuses the existing P3.83/P3.85/P3.86 seam
  (app.domain.ai_provider.invoke_ai_provider): client secrets rejected,
  HTTPS-only transport, explicit timeouts, bounded retries, and
  ``live_llm=False`` semantics preserved. No new architecture is introduced.
  The sync seam is executed off the event loop (``asyncio.to_thread``); an
  injected ``test_transport`` runs in a worker thread and must be
  thread-safe. Provenance records both the input-snapshot hash and the
  exact prompt hash for stable traceability.
- Cancellation containment (async boundary contract): ``asyncio.to_thread``
  cannot terminate a running worker thread. Cancelling the awaiting task
  delivers ``CancelledError`` to the caller; a late provider completion in
  the worker thread is discarded — it can never be returned to a cancelled
  caller or committed to downstream state, because the service keeps no
  cross-run state and a result object is only ever handed back to the
  awaited caller.
- No HTTP route is exposed for AI-2: the owner-facing surface for AI-2 is
  defined in the NOT_SYNCED amendments and must not be invented here.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import ROOT, Settings, get_settings, is_verified_live
from app.domain.ai_provider import invoke_ai_provider, resolve_ai_provider
from app.domain.g2_gate import G2GateState, evaluate_g2_gate, execution_mode
from app.services.ai_service import (
    AIContextBuilder,
    AIRequest,
    AITaskType,
    FallbackAIProvider,
    build_controlled_provider_prompt,
)

logger = logging.getLogger("shekar.ai2")

AI2Status = Literal[
    "gated_not_executed",
    "executed_shadow",
    "executed",
    "failed_provider",
    "failed_schema",
]

AI2Transport = Callable[[dict[str, Any]], Any]

# Interpretive list items are individually bounded (bounded-output contract).
BoundedStr = Annotated[str, Field(max_length=500)]

# Bounded request payload nesting depth. Demonstrated risk being contained:
# payloads legal under the 64 KiB size cap but nested ~1000 deep crash
# pydantic-core serialization ("Circular reference detected") and ~10.9k
# deep overflow json.dumps recursion; real backtest results are far shallower.
_MAX_BACKTEST_DEPTH = 24


class AI2Request(BaseModel):
    """Bounded AI-2 request contract (implementation hardening).

    Bounds prevent unbounded memory amplification through context building,
    canonical hashing, and prompt construction. The authoritative request
    schema, if it differs, is defined by the NOT_SYNCED 2026-10-02 amendment
    corpus and supersedes these bounds when the owner supplies it.
    """

    task: AITaskType = "analyst"
    question: str = Field(default="", max_length=2000)
    symbol: str | None = Field(default=None, max_length=64)
    filter_expr: str | None = Field(default=None, max_length=2048)
    backtest_result: dict[str, Any] | None = None
    language: str = Field(default="fa", max_length=16)

    @staticmethod
    def _check_depth(value: Any, max_depth: int = _MAX_BACKTEST_DEPTH) -> None:
        """Iteratively bound container nesting (no recursion on attacker input)."""
        stack: list[tuple[Any, int]] = [(value, 0)]
        while stack:
            node, depth = stack.pop()
            if depth > max_depth:
                raise ValueError("backtest_result_too_deep")
            if isinstance(node, dict):
                stack.extend((v, depth + 1) for v in node.values())
            elif isinstance(node, (list, tuple)):
                stack.extend((v, depth + 1) for v in node)

    @model_validator(mode="after")
    def _bounded_payload(self) -> "AI2Request":
        if self.backtest_result is None:
            return self
        # Depth first: it makes the json.dumps recursion overflow below
        # unreachable for any accepted payload.
        self._check_depth(self.backtest_result)
        try:
            # allow_nan=False: NaN/Infinity are not RFC 8259 JSON; reject them
            # deterministically instead of emitting non-standard JSON downstream.
            raw = json.dumps(self.backtest_result, ensure_ascii=False, allow_nan=False)
        except RecursionError as exc:  # belt-and-braces; depth bound above caps this
            raise ValueError("backtest_result_too_deep") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError("backtest_result_not_json_serializable") from exc
        if len(raw.encode("utf-8")) > 65536:
            raise ValueError("backtest_result_too_large")
        return self


class AI2Interpretation(BaseModel):
    """Strict schema for model output. Interpretive/advisory content only.

    ``extra="forbid"``: unspecified structured fields emitted by the model
    fail validation instead of being silently ignored, so unvalidated model
    content can never enter an AI-2 result. All strings are bounded.
    """

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    observations: list[BoundedStr] = Field(default_factory=list, max_length=20)
    risks: list[BoundedStr] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)


class AI2Provenance(BaseModel):
    """Explicit provenance for every AI-2 outcome, including gated ones."""

    stage: Literal["ai2"] = "ai2"
    input_snapshot_sha256: str
    prompt_sha256: str = ""
    deterministic_source: str = (
        "market_service(status,data_trust_context,symbol,filter,backtest) via AIContextBuilder "
        "+ FallbackAIProvider deterministic stage-1 analysis"
    )
    data_trust_state: str
    live_verified: bool
    provider_mode: str
    provider_label: str
    provider_status: str | None = None
    provider_error_code: str | None = None
    provider_attempts: int | None = None
    schema_valid: bool = False
    test_only_transport: bool = False
    gate: dict[str, Any] = Field(default_factory=dict)
    created_at_utc: str


class AI2Result(BaseModel):
    ok: bool = False
    status: AI2Status
    task: AITaskType
    error_code: str | None = None
    deterministic_context: dict[str, Any] = Field(default_factory=dict)
    interpretation: AI2Interpretation | None = None
    provenance: AI2Provenance | None = None
    warnings: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)


# Default location of the tracked formal G2 gate-state document (GOV-32
# Phase 3C). Overridable via the G2_GATE_STATE_PATH setting for deployments;
# the override changes WHERE the state is read from, never WHAT it says.
_DEFAULT_G2_GATE_STATE_PATH = ROOT / "docs" / "active" / "G2_GATE_STATE.json"


def _load_g2_gate_state(
    settings: Settings,
) -> tuple[G2GateState | None, str | None, "Path"]:
    """Read-only G2 gate-state load — fail-closed (GOV-32 §3C).

    Returns ``(state, load_error_tag, state_path)``. Any read/parse/schema
    failure yields ``(None, tag, path)``; the evaluator then denies with the
    corresponding tag (``gate_state_missing`` / ``gate_state_malformed``).
    Never raises.
    """
    raw = (getattr(settings, "g2_gate_state_path", "") or "").strip()
    path = Path(raw) if raw else _DEFAULT_G2_GATE_STATE_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, "gate_state_missing", path
    try:
        state = G2GateState.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValueError, ValidationError):
        return None, "gate_state_malformed", path
    return state, None, path


def _load_owner_decision_document(state: G2GateState | None, state_path: "Path") -> str | None:
    """Read the owner-decision document referenced by a gate state.

    Repo-relative references resolve against the repository root implied by the
    state-document location (``docs/active/x.json`` -> ``parents[2]``).
    Absolute references are used verbatim. Any read failure returns ``None``
    (the evaluator then denies with ``owner_decision_unverifiable``).
    """
    if state is None or state.owner_decision is None:
        return None
    ref = state.owner_decision.decision_document
    candidate = Path(ref)
    if not candidate.is_absolute():
        base = state_path.parents[2] if len(state_path.parents) >= 3 else state_path.parent
        candidate = base / ref
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError:
        return None


class AI2Service:
    """Second-stage analysis orchestration with fail-closed governance gates."""

    def __init__(self) -> None:
        self._context_builder = AIContextBuilder()

    # ------------------------------------------------------------------
    # Gate reporting
    # ------------------------------------------------------------------
    @staticmethod
    def gate_report(data_trust: dict[str, Any] | None, settings: Settings | None = None) -> dict[str, Any]:
        s = settings or get_settings()
        info = resolve_ai_provider()
        live_verified = is_verified_live(data_trust if isinstance(data_trust, dict) else None)
        return {
            "ai2_enabled": bool(s.ai2_enabled),
            "live_verified": live_verified,
            "g2_owner_acceptance": "NOT_RECORDED",
            "g2_independent_validation": "NOT_PASSED",
            "provider_invocation_ready": bool(info.get("invocation_ready")),
            "real_data_ai2_allowed": False,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _input_digest(ctx_dump: dict[str, Any]) -> tuple[str, int]:
        canonical = json.dumps(
            ctx_dump, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest(), len(canonical)

    @staticmethod
    def _parse_interpretation(text: str) -> tuple[AI2Interpretation | None, str | None]:
        raw = (text or "").strip()
        if not raw:
            return None, "empty_output"
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return None, "invalid_json"
        if not isinstance(obj, dict):
            return None, "schema_not_object"
        try:
            return AI2Interpretation.model_validate(obj), None
        except ValidationError as exc:
            # Record only the count and field paths — never echo the payload.
            paths = ",".join(sorted({str(e.get("loc", ["?"])[0]) for e in exc.errors()}))
            return None, f"schema_validation_failed:{len(exc.errors())}:{paths[:120]}"

    def _base_provenance(
        self,
        *,
        deterministic_context: dict[str, Any],
        data_trust: dict[str, Any],
        gates: dict[str, Any],
        transport: AI2Transport | None,
    ) -> AI2Provenance:
        digest, _ = self._input_digest(deterministic_context)
        info = resolve_ai_provider()
        return AI2Provenance(
            input_snapshot_sha256=digest,
            data_trust_state=str(data_trust.get("state") or "unknown"),
            live_verified=bool(gates.get("live_verified")),
            provider_mode=str(info.get("mode") or "fallback"),
            provider_label=str(info.get("provider_label") or "deterministic-rule-based-fallback"),
            test_only_transport=transport is not None,
            gate=gates,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Deterministic stage-1 analysis (AI-1 fallback core)
    # ------------------------------------------------------------------
    _STAGE1_TASKS = ("assistant", "analyst", "optimizer", "research", "strategy", "risk")

    @staticmethod
    def _bounded_stage1(result: Any) -> dict[str, Any]:
        dump = result.model_dump(mode="json")
        return {
            "available": True,
            "summary": str(dump.get("summary") or "")[:800],
            "key_observations": [str(o)[:240] for o in (dump.get("key_observations") or [])[:8]],
            "confidence": float(dump.get("confidence") or 0.0),
        }

    def _stage1_analysis(self, ctx: Any) -> dict[str, Any]:
        """Run the deterministic stage-1 (AI-1 fallback core) for this task.

        Purely in-process; never invokes a provider. Failure is recorded, not
        raised: AI-2 degrades to raw-context interpretation with an explicit
        ``stage1.available=False`` record (deterministic failure handling).
        """
        task = str(ctx.task)
        if task not in self._STAGE1_TASKS:
            return {"available": False, "error_code": "stage1_task_unsupported"}
        try:
            method = getattr(FallbackAIProvider(), task)
            return self._bounded_stage1(method(ctx))
        except Exception as exc:
            return {"available": False, "error_code": f"stage1_unavailable:{type(exc).__name__}"}

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------
    async def run(
        self,
        request: AI2Request,
        market_service: Any,
        *,
        transport: AI2Transport | None = None,
    ) -> AI2Result:
        s = get_settings()
        ctx = await self._context_builder.build(
            AIRequest(
                question=request.question,
                symbol=request.symbol,
                filter_expr=request.filter_expr,
                backtest_result=request.backtest_result,
                language=request.language,
            ),
            request.task,
            market_service,
        )
        stage1 = self._stage1_analysis(ctx)
        ctx_dump = ctx.model_dump(mode="json")
        deterministic_context = {**ctx_dump, "stage1": stage1}
        gates = self.gate_report(ctx.data_trust, s)

        # Runtime G2 gate evaluation (GOV-32 Phase 3C; 02:37 "Runtime G2 is
        # not yet implemented" closed; 02:201-202; D-AI-26). Read-only,
        # fail-closed: missing/malformed/stale/contradictory/unverifiable
        # state denies real-data execution. Synthetic/paper execution stays
        # explicitly labeled and is never represented as LIVE.
        g2_state, g2_load_tag, g2_state_path = _load_g2_gate_state(s)
        owner_decision_text = _load_owner_decision_document(g2_state, g2_state_path)
        g2_allowed, g2_refusals = evaluate_g2_gate(
            g2_state,
            current_commit=(getattr(s, "runtime_commit", "") or None),
            owner_decision_text=owner_decision_text,
            load_error=g2_load_tag,
        )
        gates["g2_gate_verdict"] = g2_state.verdict if g2_state is not None else None
        gates["g2_gate_refusals"] = list(g2_refusals)
        gates["g2_gate_load_error"] = g2_load_tag
        gates["execution_mode"] = execution_mode(bool(gates["live_verified"]))

        warnings = list(ctx.warnings)
        if not stage1.get("available"):
            warnings.append(
                "Deterministic stage-1 analysis was unavailable; "
                f"interpretation context is limited ({stage1.get('error_code')})."
            )
        safety = FallbackAIProvider._safety()
        provenance = self._base_provenance(
            deterministic_context=deterministic_context,
            data_trust=ctx.data_trust,
            gates=gates,
            transport=transport,
        )

        def _log(status: str, error_code: str | None) -> None:
            # Structured, secret-free logging: statuses, codes, gate states only.
            logger.info(
                "ai2 status=%s task=%s error_code=%s ai2_enabled=%s live_verified=%s "
                "input_sha256=%s test_transport=%s",
                status,
                request.task,
                error_code or "-",
                gates.get("ai2_enabled"),
                gates.get("live_verified"),
                provenance.input_snapshot_sha256[:12],
                transport is not None,
            )

        # Gate 1 — explicit configuration (default off).
        if not s.ai2_enabled:
            warnings.append("AI-2 is disabled (AI2_ENABLED=0); nothing was executed.")
            result = AI2Result(
                ok=False,
                status="gated_not_executed",
                task=request.task,
                error_code="ai2_disabled",
                deterministic_context=deterministic_context,
                provenance=provenance,
                warnings=warnings,
                safety=safety,
            )
            _log(result.status, result.error_code)
            return result

        # Gate 2 — trust-state enforcement (fail-closed).
        # Missing or unavailable market data gives the model nothing
        # deterministic to interpret; execution is refused before any
        # provider invocation.
        trust_state = str((ctx.data_trust or {}).get("state") or "").strip()
        if not trust_state or trust_state == "unavailable":
            warnings.append(
                "Data trust state is missing or unavailable; AI-2 refused to execute."
            )
            result = AI2Result(
                ok=False,
                status="gated_not_executed",
                task=request.task,
                error_code="data_trust_unavailable",
                deterministic_context=deterministic_context,
                provenance=provenance,
                warnings=warnings,
                safety=safety,
            )
            _log(result.status, result.error_code)
            return result

        # Gate 3 — G2 / owner acceptance for real-data execution (runtime
        # gate, GOV-32 Phase 3C). A run is REAL-DATA when it uses the
        # production provider seam (no injected transport) or when the trust
        # context is independently verified LIVE — the synthetic-transport
        # labeling can never launder real verified-live data into a test
        # execution. The formal recorded gate state must ALLOW and the
        # production path additionally requires verified LIVE trust; the
        # refusal keeps the reviewed error code with the gate refusals
        # recorded for audit.
        real_data_run = transport is None or gates["live_verified"]
        if real_data_run and (not g2_allowed or not gates["live_verified"]):
            if g2_refusals:
                warnings.append(
                    "Runtime G2 gate refused real-data AI-2 execution "
                    f"({', '.join(g2_refusals)}); nothing was executed."
                )
            warnings.append(
                "AI-2 execution on real data requires G2 independent validation and "
                "owner acceptance (NOT_PASSED); nothing was executed."
            )
            result = AI2Result(
                ok=False,
                status="gated_not_executed",
                task=request.task,
                error_code="g2_independent_validation_required",
                deterministic_context=deterministic_context,
                provenance=provenance,
                warnings=warnings,
                safety=safety,
            )
            _log(result.status, result.error_code)
            return result

        # Provider invocation through the existing fail-closed seam. The
        # prompt carries the deterministic stage-1 analysis (summary and key
        # observations) so the model interprets domain-owned values; when
        # stage-1 is unavailable the prompt degrades to task + trust + rules.
        prompt = build_controlled_provider_prompt(
            {
                "task": ctx.task,
                "data_trust": ctx.data_trust,
                "summary": str(stage1.get("summary") or ""),
                "key_observations": stage1.get("key_observations") or [],
            },
            question=request.question,
        )
        payload = {"task": ctx.task, "data_trust": ctx.data_trust, "prompt": prompt}
        provenance.prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        # The seam is synchronous; execute it off the event loop.
        if transport is not None:
            execution = await asyncio.to_thread(
                invoke_ai_provider, payload, test_transport=transport
            )
        else:
            execution = await asyncio.to_thread(invoke_ai_provider, payload)

        if not isinstance(execution, dict):
            # Defense in depth: the seam contract guarantees a dict on every
            # path; a violating payload is mapped to a deterministic failure
            # instead of crashing the service with AttributeError.
            warnings.append(
                "Provider execution violated the seam contract (non-dict payload); "
                "mapped to a deterministic provider failure."
            )
            result = AI2Result(
                ok=False,
                status="failed_provider",
                task=request.task,
                error_code="provider_contract_violation",
                deterministic_context=deterministic_context,
                provenance=provenance,
                warnings=warnings,
                safety=safety,
            )
            _log(result.status, result.error_code)
            return result

        provenance.provider_status = str(execution.get("status") or "")
        provenance.provider_error_code = (
            str(execution.get("error_code")) if execution.get("error_code") else None
        )
        attempts = execution.get("attempts")
        provenance.provider_attempts = (
            attempts if isinstance(attempts, int) and attempts >= 0 else None
        )

        if not execution.get("ok"):
            warnings.append(str(execution.get("warning") or "Provider execution failed."))
            result = AI2Result(
                ok=False,
                status="failed_provider",
                task=request.task,
                error_code=provenance.provider_error_code or "provider_unavailable",
                deterministic_context=deterministic_context,
                provenance=provenance,
                warnings=warnings,
                safety=safety,
            )
            _log(result.status, result.error_code)
            return result

        interpretation, schema_error = self._parse_interpretation(str(execution.get("text") or ""))
        if interpretation is None:
            warnings.append(
                "Model output did not validate against the AI-2 interpretation schema; "
                "no interpretation was attached."
            )
            result = AI2Result(
                ok=False,
                status="failed_schema",
                task=request.task,
                error_code=schema_error,
                deterministic_context=deterministic_context,
                provenance=provenance,
                warnings=warnings,
                safety=safety,
            )
            _log(result.status, result.error_code)
            return result

        provenance.schema_valid = True
        if transport is not None:
            warnings.append(
                "TEST ONLY transport: interpretation is a mock-based offline result, "
                "not a live LLM and not market advice."
            )
            status: AI2Status = "executed_shadow"
        else:
            warnings.append(
                "Interpretation is advisory only. Deterministic financial values above "
                "come from the domain layer and were not altered by the model."
            )
            status = "executed"
        result = AI2Result(
            ok=True,
            status=status,
            task=request.task,
            deterministic_context=deterministic_context,
            interpretation=interpretation,
            provenance=provenance,
            warnings=list(dict.fromkeys(warnings)),
            safety=safety,
        )
        _log(result.status, None)
        return result


ai2_service = AI2Service()
