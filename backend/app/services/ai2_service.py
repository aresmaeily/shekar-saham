"""AI-2 second-stage analysis service — Category A offline scaffold.

Governance position (see docs/active/REM1_AI2A_IMPLEMENTATION_RECORD.md):
- The authoritative AI-2 definition lives in the 2026-10-02 owner amendment
  corpus (NOT_SYNCED in this repository). This module implements ONLY the
  Category A scope that is safe to build and test offline: typed contracts,
  deterministic-domain integration, strict output-schema validation,
  provenance metadata, deterministic failure handling, and a fail-closed gate.
- Real-data AI-2 execution is blocked behind two independent gates:
    1. ``is_verified_live(data_trust)`` — the repository-wide LIVE gate.
       No caller can mint ``live_verified=True`` here
       (config.build_data_trust_context hard-codes verified=False), so the
       production path is structurally unreachable until a future
       independent provider-verification boundary exists AND G2 independent
       validation + owner acceptance are recorded by the owner.
    2. ``AI2_ENABLED`` configuration (default: off).
- Model output is interpretive/advisory ONLY and must validate against
  ``AI2Interpretation``. Deterministic financial values come exclusively
  from the existing domain layer (AIContextBuilder over market_service)
  and are never overwritten by model text.
- Provider invocation reuses the existing P3.83/P3.85/P3.86 seam
  (app.domain.ai_provider.invoke_ai_provider): client secrets rejected,
  HTTPS-only transport, explicit timeouts, bounded retries, and
  ``live_llm=False`` semantics preserved. No new architecture is introduced.
- No HTTP route is exposed for AI-2: the owner-facing surface for AI-2 is
  defined in the NOT_SYNCED amendments and must not be invented here.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings, get_settings, is_verified_live
from app.domain.ai_provider import invoke_ai_provider, resolve_ai_provider
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


class AI2Request(BaseModel):
    task: AITaskType = "analyst"
    question: str = ""
    symbol: str | None = None
    filter_expr: str | None = None
    backtest_result: dict[str, Any] | None = None
    language: str = "fa"


class AI2Interpretation(BaseModel):
    """Strict schema for model output. Interpretive/advisory content only."""

    summary: str = Field(min_length=1, max_length=2000)
    observations: list[str] = Field(default_factory=list, max_length=20)
    risks: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)


class AI2Provenance(BaseModel):
    """Explicit provenance for every AI-2 outcome, including gated ones."""

    stage: Literal["ai2"] = "ai2"
    input_snapshot_sha256: str
    deterministic_source: str = (
        "market_service(status,data_trust_context,symbol,filter,backtest) via AIContextBuilder"
    )
    data_trust_state: str
    live_verified: bool
    provider_mode: str
    provider_label: str
    provider_status: str | None = None
    provider_error_code: str | None = None
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
        ctx_dump: dict[str, Any],
        data_trust: dict[str, Any],
        gates: dict[str, Any],
        transport: AI2Transport | None,
    ) -> AI2Provenance:
        digest, _ = self._input_digest(ctx_dump)
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
        ctx_dump = ctx.model_dump(mode="json")
        gates = self.gate_report(ctx.data_trust, s)
        warnings = list(ctx.warnings)
        safety = FallbackAIProvider._safety()
        provenance = self._base_provenance(
            ctx_dump=ctx_dump, data_trust=ctx.data_trust, gates=gates, transport=transport
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
                deterministic_context=ctx_dump,
                provenance=provenance,
                warnings=warnings,
                safety=safety,
            )
            _log(result.status, result.error_code)
            return result

        # Gate 2 — G2 / owner acceptance for real-data execution.
        # The production path (no injected transport) requires an independently
        # verified LIVE trust context, which cannot be produced in this
        # repository today. AI-2 therefore never reaches the provider seam here.
        if transport is None and not gates["live_verified"]:
            warnings.append(
                "AI-2 execution on real data requires G2 independent validation and "
                "owner acceptance (NOT_PASSED); nothing was executed."
            )
            result = AI2Result(
                ok=False,
                status="gated_not_executed",
                task=request.task,
                error_code="g2_independent_validation_required",
                deterministic_context=ctx_dump,
                provenance=provenance,
                warnings=warnings,
                safety=safety,
            )
            _log(result.status, result.error_code)
            return result

        # Provider invocation through the existing fail-closed seam.
        payload = {
            "task": ctx.task,
            "data_trust": ctx.data_trust,
            "prompt": build_controlled_provider_prompt(
                {**ctx_dump, "task": ctx.task}, question=request.question
            ),
        }
        if transport is not None:
            execution = invoke_ai_provider(payload, test_transport=transport)
        else:
            execution = invoke_ai_provider(payload)

        provenance.provider_status = str(execution.get("status") or "")
        provenance.provider_error_code = (
            str(execution.get("error_code")) if execution.get("error_code") else None
        )

        if not execution.get("ok"):
            warnings.append(str(execution.get("warning") or "Provider execution failed."))
            result = AI2Result(
                ok=False,
                status="failed_provider",
                task=request.task,
                error_code=provenance.provider_error_code or "provider_unavailable",
                deterministic_context=ctx_dump,
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
                deterministic_context=ctx_dump,
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
            deterministic_context=ctx_dump,
            interpretation=interpretation,
            provenance=provenance,
            warnings=list(dict.fromkeys(warnings)),
            safety=safety,
        )
        _log(result.status, None)
        return result


ai2_service = AI2Service()
