"""
auth.py - v3 حالت خصوصی (فقط مالک) — نشست امن مبتنی بر کوکی HttpOnly
- POST /api/auth/login  : ورود با رمز → کوکی HttpOnly SameSite=Strict (بدون دسترسی JS به توکن)
- POST /api/auth/logout : پاک‌کردن نشست
- GET  /api/auth/status : وضعیت قفل + ورود (بر اساس کوکی)
- همه /api در PRIVATE_MODE با کوکی/Bearer/X-API-Key محافظت می‌شوند (در main.py)
"""
from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Request, Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import (
    SESSION_COOKIE,
    authorize_cookie,
    issue_session_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_TTL = 86400  # ۲۴ ساعت


class LoginBody(BaseModel):
    password: str = ""


@router.post("/login")
async def login(body: LoginBody = Body(default_factory=LoginBody), response: Response = None) -> Dict[str, Any]:
    """ورود مالک — رمز = PRIVATE_PASSWORD یا API_KEY در env. نتیجه: کوکی HttpOnly."""
    s = get_settings()
    expected = (s.private_password or s.api_key or "").strip()
    if not expected:
        return {"ok": False, "detail": "حالت خصوصی فعال نیست", "auth_required": False}

    if not body.password:
        raise HTTPException(status_code=422, detail="رمز الزامی است")
    # فقط مقایسه زمان‌ثابت (بدون مقایسه مستقیم که نشت زمانی دارد)
    import hmac
    if not hmac.compare_digest(body.password.strip(), expected):
        raise HTTPException(status_code=401, detail="رمز اشتباه است")

    token = issue_session_token(secret=expected, payload={"sub": "owner", "iat": int(time.time())}, ttl_sec=SESSION_TTL)
    if response:
        response.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            max_age=SESSION_TTL,
            httponly=True,
            samesite="strict",
            secure=bool(getattr(s, "cookie_secure", False)),
            path="/",
        )
    return {
        "ok": True,
        "expires_in": SESSION_TTL,
        "app_name": s.app_name,
        "auth_required": True,
        # توکن در کوکی HttpOnly است؛ برای اسکریپت‌ها فقط از X-API-Key استفاده کنید
        "session": "cookie-httponly",
    }


@router.post("/logout")
async def logout(response: Response = None) -> Dict[str, Any]:
    """خروج — پاک‌کردن کوکی نشست."""
    if response:
        response.delete_cookie(key=SESSION_COOKIE, path="/")
    return {"ok": True, "logged_in": False}


@router.get("/status")
async def auth_status(request: Request = None) -> Dict[str, Any]:
    """وضعیت قفل و ورود — بر اساس کوکی/کلید (نه localStorage)."""
    s = get_settings()
    required = bool(s.auth_required and (s.private_password or s.api_key))
    logged_in = False
    if request is not None:
        logged_in = authorize_cookie(request)
    return {
        "auth_required": required,
        "private_mode": bool(s.private_mode),
        "logged_in": logged_in,
        "app_name": s.app_name,
        "session": "cookie-httponly",
    }
