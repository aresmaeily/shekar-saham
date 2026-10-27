"""لایه امنیت پیشرفته: API Key + Security Headers + Encryption awareness - v0.6.0"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Callable, Optional

from fastapi import Header, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

logger = logging.getLogger("shekar.security")

# مسیرهایی که همیشه عمومی‌اند - حتی در حالت AUTH_REQUIRED
PUBLIC_PREFIXES = (
    "/api/health",
    "/api/status",
    "/api/live/status",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/static",
    "/favicon",
    "/",  # frontend
    "/symbol",
)

# اگر auth فعال باشد، این‌ها نیاز به کلید دارند - در حالت نرم هم نیاز دارند
SENSITIVE_PREFIXES = (
    "/api/notify",
    "/api/config",
    "/api/portfolio",
    "/api/filter/saved",
    "/api/confluence/notify-now",
    "/api/backtest",
)


def is_public_path(path: str) -> bool:
    """
    P0 FIX: "/" در PUBLIC_PREFIXES با startswith باعث می‌شد همه مسیرها عمومی شوند
    (path.startswith("/") برای هر مسیری درست است). حالا "/" از startswith حذف شده
    و "/" و "/symbol" جدا بررسی می‌شوند؛ بقیه پیشوندها رفتار قبلی را دارند.
    """
    if path in {"/", "/symbol"} or path.startswith("/symbol"):
        return True
    return any(
        path == p or path.startswith(p + "/") or path.startswith(p)
        for p in PUBLIC_PREFIXES
        if p != "/"
    )


def is_sensitive_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") or path.startswith(p) for p in SENSITIVE_PREFIXES)


def verify_api_key(provided: Optional[str], settings=None) -> bool:
    """
    P0-3d Fix: Only header, timing-safe, no query param leak
    - Removed support for query param to prevent secret leakage in logs
    - Use constant time compare
    """
    settings = settings or get_settings()
    expected = (settings.api_key or "").strip()
    if not expected:
        return not settings.auth_required and not getattr(settings, "private_mode", False)
    if not provided:
        return False
    # Prevent timing attack
    if len(provided.strip()) != len(expected):
        # Still do compare_digest to not leak timing, but with dummy
        secrets.compare_digest(provided.strip(), provided.strip())
        return False
    return secrets.compare_digest(provided.strip(), expected)


# ---------------------------------------------------------------------------
# توکن جلسه کوتاه‌عمر (حالت خصوصی) — HMAC-SHA256 امضا شده
# ---------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_session_token(secret: str, payload: dict, ttl_sec: int = 86400) -> str:
    """توکن امضا‌شده با انقضا: base64(payload).base64(hmac)"""
    body = {**payload, "exp": int(time.time()) + ttl_sec}
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    b64 = _b64url(raw)
    sig = hmac.new(secret.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).digest()
    return f"{b64}.{_b64url(sig)}"


def verify_session_token(token: str, secret: str) -> Optional[dict]:
    """بررسی امضا و انقضا — برمی‌گرداند payload یا None"""
    try:
        b64, sig_b64 = token.split(".", 1)
        expected = hmac.new(secret.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).digest()
        if not secrets.compare_digest(_unb64url(sig_b64), expected):
            return None
        payload = json.loads(_unb64url(b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


SESSION_COOKIE = "shekar_session"


def authorize_cookie(request, settings=None) -> bool:
    """احراز هویت از طریق کوکی HttpOnly (نشست امن بدون دسترسی JS به توکن)."""
    settings = settings or get_settings()
    token = None
    try:
        token = request.cookies.get(SESSION_COOKIE)
    except Exception:
        token = None
    if not token:
        return False
    secret = (settings.private_password or settings.api_key or "").strip()
    if not secret:
        return False
    return verify_session_token(token, secret) is not None


def authorize_ws(ws, settings=None) -> bool:
    """احراز WebSocket: هدر API-Key یا Bearer یا کوکی نشست."""
    settings = settings or get_settings()
    key = ws.headers.get("x-api-key")
    authz = ws.headers.get("authorization") or ""
    bearer = authz[7:] if authz.lower().startswith("bearer ") else None
    if authorize_request(key, bearer, settings):
        return True
    try:
        token = ws.cookies.get(SESSION_COOKIE)
    except Exception:
        token = None
    if token:
        secret = (settings.private_password or settings.api_key or "").strip()
        if secret and verify_session_token(token, secret):
            return True
    return False


def request_is_authorized(request, settings=None) -> bool:
    """True if the HTTP request carries a valid API key, Bearer token, or session cookie."""
    if request is None:
        return False
    settings = settings or get_settings()
    key = request.headers.get("X-API-Key")
    authz = request.headers.get("Authorization") or ""
    bearer = authz[7:] if authz.lower().startswith("bearer ") else None
    return authorize_request(key, bearer, settings) or authorize_cookie(request, settings)


def authorize_request(
    api_key_header: Optional[str],
    bearer_token: Optional[str],
    settings=None,
) -> bool:
    """
    مجوز درخواست در حالت خصوصی:
    - X-API-Key معتبر  (مالک / اسکریپت)
    - یا Bearer token معتبر (نشست ورود از UI)
    """
    settings = settings or get_settings()
    if verify_api_key(api_key_header, settings):
        return True
    if bearer_token:
        secret = (settings.private_password or settings.api_key or "").strip()
        if secret and verify_session_token(bearer_token, secret):
            return True
    return False


async def require_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    """Route-level guard for sensitive API operations.

    Mirrors the global middleware and supports API key, Bearer session tokens,
    and HttpOnly cookie sessions so UI owner sessions are not broken.
    """
    settings = get_settings()
    path = request.url.path
    need = False
    if settings.auth_required and path.startswith("/api") and not is_public_path(path):
        need = True
    elif settings.api_key and is_sensitive_path(path):
        need = True
    elif settings.private_mode and path.startswith("/api"):
        need = True

    if not need:
        return

    authz = request.headers.get("Authorization") or ""
    bearer = authz[7:] if authz.lower().startswith("bearer ") else None
    if authorize_request(x_api_key, bearer, settings) or authorize_cookie(request, settings):
        return

    logger.warning(
        "Unauthorized sensitive route access attempt to %s from %s",
        path,
        request.client.host if request.client else "unknown",
    )
    raise HTTPException(status_code=401, detail="برای این عملیات احراز هویت لازم است")


def _is_insecure_placeholder_secret(value: str) -> bool:
    """WS-HARDEN-1/W1: insecure compose-style placeholders must never act as real credentials."""
    normalized = (value or "").strip().lower()
    return normalized.startswith("change-me")


def validate_security_configuration(settings=None) -> None:
    """Fail closed for unsafe production/security configurations."""
    settings = settings or get_settings()
    env = (os.getenv("ENV") or os.getenv("APP_ENV") or os.getenv("SHEKAR_ENV") or "").strip().lower()
    is_production = env in {"prod", "production"}

    private_password = (getattr(settings, "private_password", "") or "").strip()
    api_key = (getattr(settings, "api_key", "") or "").strip()
    has_owner_secret = bool(private_password or api_key)
    if getattr(settings, "private_mode", False) and not has_owner_secret:
        raise RuntimeError("PRIVATE_MODE requires PRIVATE_PASSWORD or API_KEY")
    if getattr(settings, "private_mode", False):
        for secret_name, secret_value in (("PRIVATE_PASSWORD", private_password), ("API_KEY", api_key)):
            if secret_value and _is_insecure_placeholder_secret(secret_value):
                raise RuntimeError(
                    f"PRIVATE_MODE owner secret {secret_name} is an insecure placeholder "
                    "(change-me*); set a strong PRIVATE_PASSWORD or API_KEY"
                )

    if is_production:
        if not (getattr(settings, "auth_required", False) or getattr(settings, "private_mode", False) or getattr(settings, "api_key", "")):
            raise RuntimeError("Production requires AUTH_REQUIRED, PRIVATE_MODE, or API_KEY")
        if not (getattr(settings, "fernet_key", "") or getattr(settings, "api_key", "")):
            raise RuntimeError("Production requires stable FERNET_KEY or API_KEY for token encryption")
        if not bool(getattr(settings, "cookie_secure", False)):
            raise RuntimeError("Production requires COOKIE_SECURE=1")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """P0-3: اضافه کردن هدرهای امنیتی استاندارد OWASP + Meta"""
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # HSTS only if HTTPS (check header)
        if request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Content Security Policy - relaxed for inline scripts (v0.6 still uses inline), but protect
        # TODO in v0.7: move to nonce-based CSP with bundled JS
        # CSP سخت‌گیرانه v3: اسکریپت‌ها فقط از خود سرور (بدون inline/CDN)
        # کتابخانه چارت به‌صورت محلی vendoring شده است؛ فونت‌ها هم محلی.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss: https://cdn.tsetmc.com https://Api.BrsApi.ir; "
            "frame-src https://s.tradingview.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
        return response
