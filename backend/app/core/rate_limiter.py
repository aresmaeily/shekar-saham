"""
Rate limiter - v0.6.2 Professional Fix
- Per-path buckets (not global heavy)
- Returns 429 JSON properly
- Sliding window with deque
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Dict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger("shekar.ratelimit")


class InMemoryRateLimiter:
    def __init__(self):
        self.general: Dict[str, deque] = defaultdict(deque)
        self.path_specific: Dict[str, deque] = defaultdict(deque)

    def _clean(self, bucket: deque, window_sec: int):
        now = time.time()
        while bucket and now - bucket[0] > window_sec:
            bucket.popleft()

    def check_limit(self, ip: str, path: str) -> tuple[bool, str, int]:
        """
        Returns (is_limited, message, limit)
        Professional per-path logic (matches enforcement below):
        - General: 150/min global per IP
        - Heavy paths: 25/min per path per IP
        - Sensitive: 15/min per path per IP
        - Login (/api/auth/login): 5/min + 20/hour per IP
        """
        # Define limits per path type
        heavy_paths = ("/api/analyze", "/api/confluence", "/api/backtest", "/api/filter/run", "/api/market-map", "/api/fundamentals", "/api/big-moves", "/api/tablocastic")
        sensitive_paths = ("/api/notify", "/api/config", "/api/portfolio", "/api/filter/saved")
        # مسیرهای ورود — بسیار سخت‌گیرانه برای جلوگیری از Brute-force
        auth_paths = ("/api/auth/login",)

        is_heavy = any(path.startswith(p) for p in heavy_paths)
        is_sensitive = any(path.startswith(p) for p in sensitive_paths)
        is_auth = any(path.startswith(p) for p in auth_paths)

        # Check general
        g_key = f"gen:{ip}"
        self._clean(self.general[g_key], 60)
        if len(self.general[g_key]) >= 150:  # Increased from 120 to 150 for better UX
            return True, "درخواست زیاد است (150/min). لطفا 1 دقیقه صبر کنید", 60

        # Check per-path heavy
        if is_heavy:
            p_key = f"heavy:{path}:{ip}"
            self._clean(self.path_specific[p_key], 60)
            if len(self.path_specific[p_key]) >= 25:
                return True, f"این endpoint سنگین است ({path}). حداکثر 25 درخواست در دقیقه", 60

        # Check per-path sensitive
        if is_sensitive:
            p_key = f"sens:{path}:{ip}"
            self._clean(self.path_specific[p_key], 60)
            if len(self.path_specific[p_key]) >= 15:
                return True, f"درخواست‌های حساس {path} محدود شده (15/min)", 60

        # ورود: حداکثر 5 تلاش در دقیقه + 20 در ساعت
        if is_auth:
            p_key = f"auth:{path}:{ip}"
            self._clean(self.path_specific[p_key], 60)
            if len(self.path_specific[p_key]) >= 5:
                return True, "تلاش بیش از حد برای ورود (5/min). 1 دقیقه صبر کنید", 60
            h_key = f"auth_hour:{path}:{ip}"
            self._clean(self.path_specific[h_key], 3600)
            if len(self.path_specific[h_key]) >= 20:
                return True, "تلاش بیش از حد برای ورود (20/hour). 1 ساعت صبر کنید", 3600

        return False, "", 0

    def record(self, ip: str, path: str):
        now = time.time()
        self.general[f"gen:{ip}"].append(now)
        heavy_paths = ("/api/analyze", "/api/confluence", "/api/backtest", "/api/filter/run", "/api/market-map", "/api/fundamentals", "/api/big-moves", "/api/tablocastic")
        sensitive_paths = ("/api/notify", "/api/config", "/api/portfolio", "/api/filter/saved")
        auth_paths = ("/api/auth/login",)
        is_heavy = any(path.startswith(p) for p in heavy_paths)
        is_sensitive = any(path.startswith(p) for p in sensitive_paths)
        is_auth = any(path.startswith(p) for p in auth_paths)
        if is_heavy:
            self.path_specific[f"heavy:{path}:{ip}"].append(now)
        if is_sensitive:
            self.path_specific[f"sens:{path}:{ip}"].append(now)
        if is_auth:
            self.path_specific[f"auth:{path}:{ip}"].append(now)
            self.path_specific[f"auth_hour:{path}:{ip}"].append(now)

    def get_client_ip(self, request: Request) -> str:
        """
        امن: فقط اگر TRUST_PROXY=1 (پشت Nginx/Caddy) به X-Forwarded-For اعتماد کن.
        در غیر این صورت کلاینت می‌تواند XFF را جعل کند و rate limit را دور بزند.
        """
        from app.core.config import get_settings
        if getattr(get_settings(), "trust_proxy", False):
            xff = request.headers.get("x-forwarded-for")
            if xff:
                return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(("/ws", "/static", "/docs", "/openapi", "/favicon", "/redoc", "/symbol")):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        client_ip = limiter.get_client_ip(request)
        limited, msg, retry = limiter.check_limit(client_ip, path)
        if limited:
            logger.warning(f"Rate limit hit for {client_ip} on {path}: {msg}")
            return JSONResponse(
                status_code=429,
                content={"detail": msg, "code": "RATE_LIMIT", "path": path, "retry_after": retry},
                headers={"Retry-After": str(retry)}
            )
        
        limiter.record(client_ip, path)
        return await call_next(request)
