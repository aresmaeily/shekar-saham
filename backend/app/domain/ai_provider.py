"""AI provider adapter + fail-closed HTTPS execution seam.

P3.38/P3.83/P3.85:
Context Builder → Data Trust → Safety → Provider Resolver → HTTPS transport
→ Validation → Structured Result.

HTTPS runs only when AI_EXECUTE=1 and a server-side key is present.
Production never invents an LLM answer. `test_transport` is TEST ONLY.
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
    "http_error",
    "malformed",
    "blocked",
    "executed",
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
    return bool(_key_value())


def _key_value() -> str:
    return (
        os.getenv("AI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or ""
    ).strip()


def _execute_enabled() -> bool:
    return os.getenv("AI_EXECUTE", "").strip().lower() in {"1", "true", "yes", "on"}


def _runtime_limits() -> tuple[float, int]:
    try:
        timeout_sec = float(os.getenv("AI_TIMEOUT_SEC", "20") or 20)
    except (TypeError, ValueError):
        timeout_sec = 20.0
    try:
        retry_max = int(os.getenv("AI_RETRY_MAX", "0") or 0)
    except (TypeError, ValueError):
        retry_max = 0
    return max(1.0, min(timeout_sec, 120.0)), max(0, min(retry_max, 3))


def _https_endpoint(name: str) -> str | None:
    override = (os.getenv("AI_BASE_URL") or "").strip()
    if override:
        if not override.lower().startswith("https://"):
            return None
        return override
    model = (os.getenv("AI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    defaults = {
        "openai": "https://api.openai.com/v1/chat/completions",
        "anthropic": "https://api.anthropic.com/v1/messages",
        "groq": "https://api.groq.com/openai/v1/chat/completions",
        "gemini": f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "azure": "",
    }
    url = defaults.get(name, "")
    return url or None


def _build_provider_http(name: str, key: str, prompt: str) -> tuple[str, dict[str, str], dict[str, Any]] | None:
    url = _https_endpoint(name)
    if not url:
        return None
    model = (os.getenv("AI_MODEL") or "").strip()
    text = (prompt or "ping")[:2000]
    if name in {"openai", "groq", "azure"}:
        return (
            url,
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            {"model": model or "gpt-4o-mini", "messages": [{"role": "user", "content": text}], "max_tokens": 256},
        )
    if name == "anthropic":
        return (
            url,
            {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            {
                "model": model or "claude-3-haiku-20240307",
                "max_tokens": 256,
                "messages": [{"role": "user", "content": text}],
            },
        )
    if name == "gemini":
        # Official Gemini REST auth is x-goog-api-key. Query-string keys
        # leave process memory in URLs, proxy logs, and httpx exception causes.
        return (
            url,
            {"Content-Type": "application/json", "x-goog-api-key": key},
            {"contents": [{"parts": [{"text": text}]}]},
        )
    return None


def _extract_provider_text(name: str, payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("text"), str) and payload["text"].strip():
        return payload["text"].strip()
    try:
        if name in {"openai", "groq", "azure"}:
            content = payload["choices"][0]["message"]["content"]
            return str(content).strip() if content else None
        if name == "anthropic":
            content = payload["content"][0]["text"]
            return str(content).strip() if content else None
        if name == "gemini":
            content = payload["candidates"][0]["content"]["parts"][0]["text"]
            return str(content).strip() if content else None
    except (KeyError, IndexError, TypeError):
        return None
    return None


def https_transport(request: dict[str, Any]) -> dict[str, Any]:
    """Real HTTPS POST. TLS verify is always on. Never logs secrets."""
    import httpx

    name = str(request.get("requested") or _env_name())
    built = _build_provider_http(name, _key_value(), str(request.get("prompt") or request.get("task") or "ping"))
    if built is None:
        raise RuntimeError("blocked_endpoint")
    url, headers, body = built
    timeout_sec = float(request.get("timeout_sec") or _runtime_limits()[0])
    try:
        with httpx.Client(verify=True, timeout=httpx.Timeout(timeout_sec)) as client:
            response = client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise TimeoutError("timeout") from exc
    except httpx.HTTPError as exc:
        raise ConnectionError("connect_failed") from exc
    if response.status_code >= 400:
        err = RuntimeError(f"http_{response.status_code}")
        err.status_code = response.status_code  # type: ignore[attr-defined]
        raise err
    try:
        payload = response.json()
    except Exception as exc:
        raise ValueError("malformed_json") from exc
    text = _extract_provider_text(name, payload)
    if not text:
        raise ValueError("malformed_response")
    return {"text": text[:4000]}


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
    ready = bool(key_present and valid and _execute_enabled() and _https_endpoint(name))
    return {
        **base,
        "mode": "external_not_configured",
        "provider_label": f"external:{name}:{'ready' if ready else 'not_invoked'}",
        "requested": name,
        "configured": bool(key_present and valid),
        "key_present": bool(key_present),
        "model_configured": model_set,
        "invocation_ready": ready,
        "warning": (
            "HTTPS transport exists but is not invoked unless AI_EXECUTE=1 "
            "and a server-side key is present. Runtime without those is NOT_EXECUTED."
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
    """Fail-closed execution seam. Production never returns fabricated LLM text."""
    req = request if isinstance(request, dict) else {}
    if client_secret_fields_present(req):
        return _empty_execution(
            status="not_executed",
            error_code="client_secret_rejected",
            warning="Client-supplied credentials are rejected; provider was not invoked.",
        )
    trust = req.get("data_trust")
    if not isinstance(trust, dict) or not str(trust.get("state") or "").strip():
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

    timeout_sec, retry_max = _runtime_limits()
    test_only = test_transport is not None
    if test_transport is None:
        if not _execute_enabled():
            return _empty_execution(
                status="not_executed",
                error_code="execution_not_enabled",
                warning="AI_EXECUTE is not enabled; HTTPS transport was not invoked.",
                requested=requested,
            )
        if _https_endpoint(requested) is None:
            return _empty_execution(
                status="blocked",
                error_code="https_endpoint_required",
                warning="Provider endpoint must be HTTPS (set AI_BASE_URL for azure/custom).",
                requested=requested,
            )
        transport: Callable[[dict[str, Any]], Any] = https_transport
    else:
        transport = test_transport

    attempts = 0
    last_exc: Exception | None = None
    raw: Any = None
    payload = {
        "task": req.get("task"),
        "prompt": req.get("prompt"),
        "requested": requested,
        "data_trust_state": trust.get("state"),
        "timeout_sec": timeout_sec,
        "test_only": test_only,
    }
    for _ in range(retry_max + 1):
        attempts += 1
        try:
            raw = transport(payload)
            last_exc = None
            break
        except TimeoutError as exc:
            last_exc = exc
            raw = None
        except Exception as exc:
            last_exc = exc
            raw = None
            code = getattr(exc, "status_code", None)
            if isinstance(code, int) and 400 <= code < 500 and code != 429:
                break
    label = "TEST ONLY transport" if test_only else "HTTPS transport"
    if isinstance(last_exc, TimeoutError) or (last_exc is not None and "timeout" in str(last_exc).lower()):
        status: ProviderExecStatus = "timeout"
        error_code = "timeout"
    elif last_exc is not None and "blocked_endpoint" in str(last_exc):
        status = "blocked"
        error_code = "https_endpoint_required"
    elif last_exc is not None and str(last_exc).startswith("http_"):
        status = "http_error"
        error_code = str(last_exc)[:16]
    elif isinstance(last_exc, ValueError):
        status = "malformed"
        error_code = "malformed_response"
    elif last_exc is not None:
        status = "unavailable"
        error_code = "transport_unavailable"
    else:
        status = "executed"
        error_code = ""
    if last_exc is not None:
        out = _empty_execution(
            status=status,
            error_code=error_code,
            warning=f"{label} failed ({error_code}).",
            requested=requested,
        )
        out["attempts"] = attempts
        out["test_only"] = test_only
        return out
    if not isinstance(raw, dict) or not isinstance(raw.get("text"), str) or not raw["text"].strip():
        out = _empty_execution(
            status="malformed",
            error_code="malformed_response",
            warning=f"{label} returned a malformed payload.",
            requested=requested,
        )
        out["attempts"] = attempts
        out["test_only"] = test_only
        return out
    return {
        "ok": True,
        "status": "executed_test_only" if test_only else "executed",
        "error_code": None,
        "text": raw["text"].strip()[:4000],
        "live_llm": False,
        "test_only": test_only,
        "requested": requested,
        "timeout_sec": timeout_sec,
        "retry_max": retry_max,
        "attempts": attempts,
        "warning": (
            "TEST ONLY mock transport. This is not a live LLM result."
            if test_only
            else "HTTPS provider returned text. This is not market LIVE data."
        ),
    }
