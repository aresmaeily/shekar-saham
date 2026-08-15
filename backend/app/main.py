from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as main_router
from app.api.chart import router as chart_router
from app.api.forex import router as forex_router
from app.api.excellent import router as excellent_router
from app.api.auth import router as auth_router
from app.core.config import ROOT, get_settings
from app.core.security import (
    is_public_path,
    is_sensitive_path,
    authorize_request,
    authorize_cookie,
    authorize_ws,
    SecurityHeadersMiddleware,
    validate_security_configuration,
)
from app.core.rate_limiter import RateLimitMiddleware
from app.core.request_id import RequestIdMiddleware
from app.core.metrics_prom import metrics
from app.domain.events import event_bus, DomainEvent
from app.services.market_service import market_service
from app.services.ws_hub import ws_hub

# Structured logging - v0.7.0 Excellent
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s | request_id=%(request_id)s",
)
# Add request_id to log record if available
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        try:
            # Try to get from contextvar if set, else default
            record.request_id = getattr(record, "request_id", "-")
        except Exception:
            record.request_id = "-"
        return True

# Apply filter to all handlers
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIdFilter())

logger = logging.getLogger("shekar")

FRONTEND_DIR = ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    validate_security_configuration(settings)
    logger.info(
        "Starting %s v%s | data_source=%s | auth=%s | phase=7-excellent | tz=%s | excellent_features=AI,Risk,Quality,Anomaly,Events,Metrics,Audit",
        settings.app_name,
        settings.version,
        settings.data_source,
        settings.auth_required,
        settings.timezone,
    )
    from app.data.store import store as _store
    from app.core.crypto import get_fernet

    # هشدار بحرانی: اگر کلید رمزنگاری موقت است (بدون FERNET_KEY/API_KEY)،
    # توکن‌های ذخیره‌شده تلگرام/بله بعد از ری‌استارت قابل رمزگشایی نیستند
    if not os.getenv("FERNET_KEY", "").strip() and not get_settings().api_key:
        if get_fernet() is not None:
            logger.critical(
                "🔴 FERNET_KEY تنظیم نشده — کلید رمزنگاری موقت (ephemeral) است. "
                "توکن‌های تلگرام/بله ذخیره‌شده بعد از ری‌استارت قابل رمزگشایی نیستند. "
                "برای پایداری: FERNET_KEY (یا API_KEY پایدار) را در .env تنظیم کنید."
            )

    _ = _store.snapshot_stats()
    # بکاپ روزانه (حداکثر ۱ بار در روز)
    try:
        last_bak = getattr(_store, "_last_backup_ts", 0.0)
        if time.time() - last_bak > 86400:
            _store.backup(keep=7)
            _store._last_backup_ts = time.time()
    except Exception as exc:
        logger.warning(f"startup backup skipped: {exc}")
    origins = settings.cors_origin_list()
    env = (os.getenv("ENV") or os.getenv("APP_ENV") or os.getenv("SHEKAR_ENV") or "").strip().lower()
    if "*" in origins and (env in {"prod", "production"} or not settings.debug):
        logger.critical("🚨 CORS wildcard * in production! Forcing localhost only")
    
    # Publish startup event
    await event_bus.publish(DomainEvent("system.startup", {"version": settings.version, "data_source": settings.data_source}))
    
    try:
        await market_service.refresh(force=True)
        metrics.inc("shekar_refresh_total", {"status": "success"})
    except Exception as exc:
        import uuid
        err_id = uuid.uuid4().hex[:8]
        logger.error(f"[{err_id}] initial refresh failed: {exc}", exc_info=False)
        metrics.inc("shekar_refresh_total", {"status": "failed"})
    
    await market_service.start_background()
    yield
    await market_service.stop_background()
    await event_bus.publish(DomainEvent("system.shutdown", {"version": settings.version}))
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="پلتفرم تابلوخوانی و تحلیل هوشمند بورس ایران — Excellent Edition v0.7.0 - با AI، مدیریت ریسک، کیفیت داده، تشخیص آنومالی، معماری رویداد-محور، متریکس پرومتئوس",
        lifespan=lifespan,
    )
    # خطای 500 یکپارچه: JSON با request_id (بدون نشت stack trace)
    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        import uuid
        err_id = uuid.uuid4().hex[:8]
        logger.error(f"[{err_id}] unhandled error on {request.method} {request.url.path}: {exc}", exc_info=False)
        return JSONResponse(
            status_code=500,
            content={"detail": "خطای داخلی سرور", "request_id": err_id},
        )

    # امنیت: خطای اعتبارسنجی بدون بازتاب ورودی کاربر (جلوگیری از نشت/DoS)
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        safe = []
        for err in exc.errors():
            safe.append(
                {
                    "loc": [str(x) for x in err.get("loc", [])],
                    "msg": err.get("msg", "خطای ورودی"),
                    "type": err.get("type", "validation"),
                }
            )
        return JSONResponse(status_code=422, content={"detail": safe})

    # Excellent: Add middlewares in correct order - outermost first
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)
    
    origins = settings.cors_origin_list()
    env = (os.getenv("ENV") or os.getenv("APP_ENV") or os.getenv("SHEKAR_ENV") or "").strip().lower()
    is_production = env in {"prod", "production"}
    if "*" in origins and (is_production or not settings.debug):
        logger.warning("Forcing CORS to localhost only due to wildcard in prod")
        origins = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]
    allow_cred = (origins != ["*"] and "*" not in origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_cred,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["X-API-Key", "X-Request-ID", "Content-Type", "Authorization"],
        max_age=600,
    )

    @app.middleware("http")
    async def audit_and_metrics_middleware(request: Request, call_next):
        start = time.time()
        path = request.url.path
        
        # Skip for static and docs
        is_api = path.startswith("/api")
        
        if "api_key" in request.query_params and is_api:
            logger.warning(f"API key in query param attempted from {request.client.host if request.client else 'unknown'} to {path}")
        
        response = await call_next(request)
        
        # Metrics
        duration = time.time() - start
        metrics.observe("shekar_http_request_duration", duration, {"path": path, "method": request.method, "status": str(response.status_code)})
        metrics.inc("shekar_http_requests_total", {"path": path, "method": request.method, "status": str(response.status_code)})
        
        # Audit for sensitive paths
        if any(path.startswith(p) for p in ("/api/notify", "/api/config", "/api/portfolio", "/api/confluence/notify-now")):
            from app.core.audit import audit
            audit.log(action=f"{request.method} {path}", user="api-user", resource=path, details={"status": response.status_code}, request=request)
        
        return response

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next):
        path = request.url.path
        s = get_settings()
        if request.method == "OPTIONS":
            return await call_next(request)
        
        need = False
        # ورود و سلامت همیشه باز — خود login احراز هویت را انجام می‌دهد
        # (P0: بدون این استثنا، فیکس is_public_path باعث 401 شدن خود login می‌شد)
        if path.startswith("/api/auth/") or path.startswith("/api/health"):
            need = False
        elif s.auth_required and path.startswith("/api") and not is_public_path(path):
            need = True
        elif s.api_key and is_sensitive_path(path):
            need = True
        elif s.private_mode and path.startswith("/api"):
            need = True

        if need:
            key = request.headers.get("X-API-Key")
            authz = request.headers.get("Authorization") or ""
            bearer = authz[7:] if authz.lower().startswith("bearer ") else None
            if not (authorize_request(key, bearer) or authorize_cookie(request)):
                metrics.inc("shekar_auth_failures_total", {"path": path})
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Unauthorized — برای دیدن خروجی‌ها ابتدا وارد شوید (رمز مالک)",
                        "auth_required": True,
                        "private_mode": bool(s.private_mode),
                        "hint": "از UI وارد شوید یا هدر Authorization: Bearer <token> / X-API-Key بفرستید",
                        "request_id": getattr(request.state, "request_id", None)
                    },
                )
        # CSRF (دفاع عمقی): روش‌های تغییردهنده با Origin خارج از هاست ممنوع
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("Origin")
            if origin:
                host = request.headers.get("Host")
                try:
                    from urllib.parse import urlparse
                    o = urlparse(origin)
                    if o.netloc and o.netloc != host:
                        metrics.inc("shekar_csrf_blocked_total", {"path": path})
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Origin ممنوع — درخواست متقاطع مسدود شد", "request_id": getattr(request.state, "request_id", None)},
                        )
                except Exception:
                    pass
        return await call_next(request)

    # Main routers
    app.include_router(main_router)
    app.include_router(excellent_router)  # v0.7.0
    app.include_router(chart_router)  # v0.8
    app.include_router(forex_router)  # v0.9 Forex like faraz.io Chart Excellent Excellent features
    app.include_router(auth_router)  # v1.5 حالت خصوصی (فقط مالک)

    @app.websocket("/ws/live")
    async def ws_live(ws: WebSocket):
        s = get_settings()
        if s.auth_required or s.private_mode:
            key = ws.headers.get("x-api-key") or ws.query_params.get("api_key")
            bearer = ws.query_params.get("token") or None
            if ws.query_params.get("api_key") or ws.query_params.get("token"):
                logger.info(f"WS auth via query param (allowed for WS) from {ws.client.host if ws.client else 'unknown'}")
            if not (authorize_request(key, bearer) or authorize_ws(ws)):
                await ws.close(code=4401)
                return
        await ws_hub.connect(ws)
        await event_bus.publish(DomainEvent("ws.connected", {"client": str(ws.client.host if ws.client else "unknown"), "count": ws_hub.count}))
        try:
            try:
                analysis = await market_service.get_analysis(force=False)
                await market_service._broadcast_live(analysis)
            except Exception:
                import uuid
                logger.debug(f"WS initial broadcast failed [{uuid.uuid4().hex[:6]}]")
            while True:
                msg = await ws.receive_text()
                low = msg.strip().lower()
                if low in {"ping", '"ping"'}:
                    await ws_hub.send_one(ws, {"type": "pong"})
                    metrics.inc("shekar_ws_ping_total")
                elif low in {"refresh", '"refresh"'}:
                    analysis = await market_service.refresh(force=True)
                    trust_ctx = market_service.data_trust_context()
                    await ws_hub.send_one(
                        ws,
                        {
                            "type": "refreshed",
                            "entry_alerts": analysis.overview.entry_alerts,
                            "exit_alerts": analysis.overview.exit_alerts,
                            "trust_level": trust_ctx.get("trust_level") or "mixed",
                            "data_trust": trust_ctx,
                        },
                    )
                    metrics.inc("shekar_ws_refresh_total")
        except WebSocketDisconnect:
            await ws_hub.disconnect(ws)
            await event_bus.publish(DomainEvent("ws.disconnected", {"count": ws_hub.count}))
        except Exception:
            import uuid
            logger.debug(f"WS disconnected [{uuid.uuid4().hex[:6]}]")
            await ws_hub.disconnect(ws)

    if FRONTEND_DIR.exists():
        assets = FRONTEND_DIR

        @app.middleware("http")
        async def cache_control_middleware(request: Request, call_next):
            resp = await call_next(request)
            p = request.url.path
            if p.startswith("/static/"):
                # استاتیک: کش ۱ ساعت (SW هم stale-while-revalidate دارد)
                if resp.headers.get("Cache-Control") is None:
                    resp.headers["Cache-Control"] = "public, max-age=3600"
            elif p == "/" or p == "/index.html":
                resp.headers["Cache-Control"] = "no-store"
            return resp

        app.mount("/static", StaticFiles(directory=str(assets)), name="static")

        @app.get("/")
        async def index():
            return FileResponse(assets / "index.html")

        @app.get("/symbol")
        @app.get("/symbol/{l18}")
        async def symbol_page(l18: str = ""):
            page = assets / "symbol.html"
            if page.exists():
                return FileResponse(page)
            return FileResponse(assets / "index.html")

        @app.get("/favicon.ico")
        async def favicon():
            ico = assets / "favicon.svg"
            if ico.exists():
                return FileResponse(ico)
            return FileResponse(assets / "index.html")

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    # امنیت: proxy_headers فقط وقتی TRUST_PROXY=1 (پشت Nginx/Caddy)
    # در غیر این صورت X-Forwarded-For قابل جعل است و rate limit دور می‌زند
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        factory=False,
        proxy_headers=bool(getattr(settings, "trust_proxy", False)),
        forwarded_allow_ips="127.0.0.1" if not getattr(settings, "trust_proxy", False) else "*",
    )


if __name__ == "__main__":
    run()
