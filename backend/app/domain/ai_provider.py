"""AI provider adapter + fail-closed execution seam.

P3.38/P3.83 gate:
Context Builder → Data Trust → Safety → Provider Resolver → (optional authenticated transport)
→ Validation → Structured Result.

Production never invents an LLM answer. A real HTTP transport is not invoked here.
`test_transport` is TEST ONLY and must be labelled as such by callers.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Literal

AIProviderMode = Literal["fallback", "external_not_configured"]
ProviderExecStatus = Literal[
    "not_executed",
    "credential_missing",
    "invalid_provider",
    "unavailable",
    "timeout",
    "malformed",
    "executed_test_only",
]

KNOWN_EXTERNAL = frozenset({"openai", "anthropic", "azure", "gemini", "groq"})
FALLBACK_NAMES = frozenset({"", "fallback", "none", "local", "rule", "deterministic", "rule_based"})

CLIENT_SECRET_FIELDS = frozenset(
    {
        "api_key",
        "apikey",
        "openai_api_key",
        "openai_key",
        "llm_key",
        "llm_api_key",
        "anthropic_api_key",
        "anthropic_key",
        "authorization",
        "token",
        "secret",
        "fernet_key",
        "brsapi_key",
        "private_password",
        "password",
        "access_token",
        "bearer",
    }
)


def client_secret_fields_present(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    found: list[str] = []
    for key in payload:
        norm = str(key).strip().lower().replace("-", "_")
        if norm in CLIENT_SECRET_FIELDS:
            found.append(norm)
    return found


def _env_name() -> str:
    return (os.getenv("AI_PROVIDER") or os.getenv("LLM_PROVIDER") or "fallback").strip().lower()


def _key_present() -> bool:
    return bool(
        (
            os.getenv("AI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or ""
        ).strip()
    )


def _runtime_limits() -> tuple[float, int]:
    try:
        timeout_sec = float(os.getenv("AI_TIMEOUT_SEC", "20") or 20)
    except (TypeError, ValueError):
        timeout_sec = 20.0
    try:
        retry_max = int(os.getenv("AI_RETRY_MAX", "0") or 0)
    except (TypeError, ValueError):
        retry_max = 0
    timeout_sec = max(1.0, min(timeout_sec, 120.0))
    retry_max = max(0, min(retry_max, 3))
    return timeout_sec, retry_max


def resolve_ai_provider() -> dict[str, Any]:
    """Describe the active AI provider without revealing secrets or calling a network LLM."""
    name = _env_name()
    model_set = bool((os.getenv("AI_MODEL") or "").strip())
    timeout_sec, retry_max = _runtime_limits()
    base = {
        "timeout_sec": timeout_sec,
        "retry_max": retry_max,
        "invocation_ready": False,
        "live_llm": False,
        "accepts_client_secrets": False,
        "external_runtime": "NOT_EXECUTED",
    }
    if name in FALLBACK_NAMES:
        return {
            **base,
            "mode": "fallback",
            "provider_label": "deterministic-rule-based-fallback",
            "requested": name or "fallback",
            "configured": False,
            "key_present": False,
            "model_configured": model_set,
            "warning": "No external LLM is invoked. Output is deterministic fallback intelligence.",
        }
    key_present = _key_present()
    valid = name in KNOWN_EXTERNAL
    return {
        **base,
        "mode": "external_not_configured",
        "provider_label": f"external:{name}:adapter_not_invoked",
        "requested": name,
        "configured": bool(key_present and valid),
        "key_present": bool(key_present),
        "model_configured": model_set,
        "warning": (
            "An external AI provider name is set but production invocation is not enabled; "
            "fallback intelligence is used. Runtime is NOT_EXECUTED / UNVERIFIED."
        ),
    }


def _empty_execution(*, status: ProviderExecStatus, error_code: str, warning: str, requested: str = "") -> dict[str, Any]:
    timeout_sec, retry_max = _runtime_limits()
    return {
        "ok": False,
        "status": status,
        "error_code": error_code,
        "text": None,
        "live_llm": False,
        "test_only": False,
        "requested": requested or _env_name() or "fallback",
        "timeout_sec": timeout_sec,
        "retry_max": retry_max,
        "attempts": 0,
        "warning": warning,
    }


def invoke_ai_provider(
    request: dict[str, Any] | None,
    *,
    test_transport: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Fail-closed execution seam. Production never returns fabricated LLM text.

    `test_transport` is TEST ONLY. It must not be wired from HTTP handlers.
    """
    req = request if isinstance(request, dict) else {}
    if client_secret_fields_present(req):
        return _empty_execution(
            status="not_executed",
            error_code="client_secret_rejected",
            warning="Client-supplied credentials are rejected; provider was not invoked.",
        )
    trust = req.get("data_trust")
    if not isinstance(trust, dict):
        return _empty_execution(
            status="not_executed",
            error_code="data_trust_required",
            warning="Provider execution requires a data_trust object.",
        )
    info = resolve_ai_provider()
    requested = str(info.get("requested") or "fallback")
    if requested in FALLBACK_NAMES:
        return _empty_execution(
            status="not_executed",
            error_code="fallback_selected",
            warning="Fallback provider selected; external LLM was not invoked.",
            requested=requested,
        )
    if requested not in KNOWN_EXTERNAL:
        return _empty_execution(
            status="invalid_provider",
            error_code="unknown_provider",
            warning=f"Provider '{requested}' is not a supported external adapter.",
            requested=requested,
        )
    if not info.get("key_present"):
        return _empty_execution(
            status="credential_missing",
            error_code="credential_missing",
            warning="External provider credential is missing; LLM was not invoked.",
            requested=requested,
        )

    # Production: even with a key present, no HTTP adapter is implemented.
    if test_transport is None:
        return _empty_execution(
            status="not_executed",
            error_code="adapter_not_invoked",
            warning="Authenticated transport is not implemented; LLM runtime remains NOT_EXECUTED.",
            requested=requested,
        )

    timeout_sec, retry_max = _runtime_limits()
    attempts = 0
    last_exc: Exception | None = None
    raw: Any = None
    payload = {
        "task": req.get("task"),
        "data_trust_state": trust.get("state"),
        "timeout_sec": timeout_sec,
        "test_only": True,
    }
    for _ in range(retry_max + 1):
        attempts += 1
        try:
            raw = test_transport(payload)
            last_exc = None
            break
        except TimeoutError as exc:
            last_exc = exc
            raw = None
        except Exception as exc:  # TEST ONLY transport failures
            last_exc = exc
            raw = None
    if isinstance(last_exc, TimeoutError) or (last_exc is not None and "timeout" in str(last_exc).lower()):
        out = _empty_execution(
            status="timeout",
            error_code="timeout",
            warning="TEST ONLY transport timed out; production LLM was not called.",
            requested=requested,
        )
        out["attempts"] = attempts
        out["test_only"] = True
        return out
    if last_exc is not None:
        out = _empty_execution(
            status="unavailable",
            error_code="transport_unavailable",
            warning="TEST ONLY transport unavailable; production LLM was not called.",
            requested=requested,
        )
        out["attempts"] = attempts
        out["test_only"] = True
        return out
    if not isinstance(raw, dict) or "text" not in raw:
        out = _empty_execution(
            status="malformed",
            error_code="malformed_response",
            warning="TEST ONLY transport returned a malformed payload.",
            requested=requested,
        )
        out["attempts"] = attempts
        out["test_only"] = True
        return out
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        out = _empty_execution(
            status="malformed",
            error_code="empty_text",
            warning="TEST ONLY transport returned empty text.",
            requested=requested,
        )
        out["attempts"] = attempts
        out["test_only"] = True
        return out
    return {
        "ok": True,
        "status": "executed_test_only",
        "error_code": None,
        "text": text.strip()[:4000],
        "live_llm": False,
        "test_only": True,
        "requested": requested,
        "timeout_sec": timeout_sec,
        "retry_max": retry_max,
        "attempts": attempts,
        "warning": "TEST ONLY mock transport. This is not a live LLM result.",
    }
