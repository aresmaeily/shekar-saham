"""AI provider adapter contract.

P3.38 future gate: Context Builder → Provider Adapter → Structured Result → Safety Gate.

This module resolves provider *configuration* from the process environment only.
It never accepts client secrets, never logs secrets, and never invokes an external
LLM. A configured key without an implemented invocation stays NOT_EXECUTED.
"""

from __future__ import annotations

import os
from typing import Any, Literal

AIProviderMode = Literal["fallback", "external_not_configured"]

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


def resolve_ai_provider() -> dict[str, Any]:
    """Describe the active AI provider without revealing secrets or calling a network LLM."""
    name = _env_name()
    model_set = bool((os.getenv("AI_MODEL") or "").strip())
    if name in {"", "fallback", "none", "local", "rule", "deterministic", "rule_based"}:
        return {
            "mode": "fallback",
            "provider_label": "deterministic-rule-based-fallback",
            "requested": name or "fallback",
            "configured": False,
            "key_present": False,
            "model_configured": model_set,
            "external_runtime": "NOT_EXECUTED",
            "live_llm": False,
            "accepts_client_secrets": False,
            "warning": "No external LLM is invoked. Output is deterministic fallback intelligence.",
        }
    key_present = _key_present()
    return {
        "mode": "external_not_configured",
        "provider_label": f"external:{name}:adapter_not_invoked",
        "requested": name,
        "configured": bool(key_present),
        "key_present": bool(key_present),
        "model_configured": model_set,
        "external_runtime": "NOT_EXECUTED",
        "live_llm": False,
        "accepts_client_secrets": False,
        "warning": (
            "An external AI provider name is set but invocation is not implemented; "
            "fallback intelligence is used. Runtime is NOT_EXECUTED / UNVERIFIED."
        ),
    }
