from __future__ import annotations
import contextvars
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# WS-HARDEN-1/W2: پل contextvar — شناسه درخواست برای همه لاگ‌های داخل scope درخواست
# قابل مشاهده می‌شود (قبلاً فقط روی request.state بود و فیلتر لاگ هرگز آن را نمی‌دید).
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def get_current_request_id() -> str | None:
    """Return the request_id bound to the current async context, or None outside a request."""
    return _request_id_var.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = req_id
        token = _request_id_var.set(req_id)
        try:
            response = await call_next(request)
        finally:
            # بدون ریست، شناسه درخواست فعلی به کانتکست‌های بعدی نشت می‌کند.
            _request_id_var.reset(token)
        response.headers["X-Request-ID"] = req_id
        return response
