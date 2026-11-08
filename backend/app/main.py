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
from app.api.chart_pro import router as chart_pro_router  # WS-10 CH-1/CH-2 chart-pro (SYNTHETIC seeded series)
from app.api.analytics import router as analytics_router  # WDA-3 (2026-11-02): additive /api/v10/analytics — search/screener/market-map/flow/dossier, market_service trust envelope, SYNTHETIC-labeled only
from app.api.forex import router as forex_router
from app.api.excellent import router as excellent_router
from app.api.auth import router as auth_router
from app.api.alert_ops import router as alert_ops_router  # GOV-41 D-AI-30 (in-product alert operations)
from app.api.strategy_lab import router as strategy_lab_router  # MASTER-RADAR (2026-11-04): /api/v10/strategylab — RSL DSL validate/spec/backtest/paper-replay/versions on SYNTHETIC seeded series; AI-proposal seam owner-gated & disconnected
from app.api.indicator_api import router as indicator_api_router  # MASTER-RADAR (2026-11-04): /api/v10/indicators — audited built-in catalog + deterministic compute (metadata lifecycle only, no code execution)
from app.api.analyst_api import router as analyst_api_router  # MASTER-RADAR (2026-11-04): /api/v10/analyst — deterministic evidence-grounded symbol analyst, every claim provenanced, no LLM call
from app.api.user_indicator_api import router as user_indicator_api_router  # MASTER-RADAR WAVE-B (2026-11-04): /api/v10/user-indicators — UIDL-1 governed user indicator DSL (compile/install/lifecycle/compute; single execution path = audited RSL-1 interpreter, no eval/exec)
from app.api.data_quality_api import router as data_quality_api_router  # MASTER-RADAR WAVE-2 (2026-11-04): /api/v10/dataquality — fixture-universe coverage/audit center (declared SYNTHETIC_FIXTURE, canonical non-live provenance, no network)
from app.api.product_loops_api import router as product_loops_api_router  # MASTER-RADAR WAVE-F (2026-11-05): /api/v10/productloops — governed five product-loop surface (declared dossiers + research permission + on-demand audit + prediction registry); SYNTHETIC/DECLARED only, no scheduler/egress
from app.api.ai2_generation_api import router as ai2_generation_api_router  # WAVE-K (OA-3, 2026-11-05): /api/v10/ai2 — governed AI-2 generation seam (NL→clarification→typed spec→RSL-1→deterministic eval→versioned candidate); fail-closed AI2_ENABLED gate, synthetic/paper-only, human-approval-only transitions
from app.api.scheduler_api import router as scheduler_api_router
from app.api.research_memory_api import router as research_memory_api_router  # 2026-11-08 owner directive (AI-3 real integration): /api/v10/memory — DURABLE research memory (SQLite/WAL + AES-256-GCM, D1/D4) + durable tamper-evident access audit trail; caller-instants only, no purge path, no egress
from app.api.ai_ma_api import router as ai_ma_api_router  # WAVE-AB3 (WP-C, 2026-11-08): /api/v10/aima — governed multi-agent runtime surface (three shipped advisory specialists, fixed bounded plan, deterministic executors, L2 autonomy ceiling enforced in-runtime, SYNTHETIC_OR_PAPER, no mutation/no promotion/no egress)  # WAVE-M (OA-4, 2026-11-06): /api/v10/scheduler — bounded LOCAL internal scheduler (fail-closed SCHEDULER_ENABLED default 0, append-only run history, pause/resume/stop/kill-switch, no egress, no broker, no promotion authority)
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
from app.core.request_id import RequestIdMiddleware, get_current_request_id
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
# WS-HARDEN-1/W2: مقدار از contextvar پل‌شده توسط RequestIdMiddleware خوانده می‌شود
# (قبلاً این کامنت «contextvar» را ادعا می‌کرد ولی هیچ contextvari وجود نداشت و
#  همه خطوط لاگ request_id=- چاپ می‌کردند).
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        try:
            current = get_current_request_id()
            record.request_id = current or getattr(record, "request_id", "-") or "-"
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
    # WAVE-M (OA-4): bounded LOCAL internal scheduler — fail-closed. With the
    # committed default (SCHEDULER_ENABLED=0) start() refuses and NOTHING is
    # scheduled; the /api/v10/scheduler posture stays honestly readable.
    # The scheduler has no egress/broker/notification surface and cannot
    # bypass AI-2 or Two-Key gates (handlers run under their own governance).
    try:
        from app.services.internal_scheduler import get_scheduler

        _scheduler = get_scheduler()
        if get_settings().scheduler_enabled:
            _start_result = await _scheduler.start()
            logger.info(f"scheduler started: {_start_result}")
        else:
            logger.info("scheduler gate closed (SCHEDULER_ENABLED=0) — not started")
    except Exception as exc:  # scheduler must never block product startup
        logger.warning(f"scheduler not started: {exc}")
    # GOV-41 D-AI-30: explicit, observable alert-operations heartbeat. The
    # 30-minute freshness cadence lives in OwnerBudgets + recorded last-success
    # state; every tick stays gated by the fail-closed kill switches and budgets.
    try:
        from app.services import alert_operations as _alert_ops

        await _alert_ops.start_background_loop(interval_seconds=60)
    except Exception as exc:  # loop must never block product startup
        logger.warning(f"alert_ops background loop not started: {exc}")
    yield
    try:
        from app.services.internal_scheduler import get_scheduler

        _s = get_scheduler()
        # Stop ONLY a scheduler that actually started (WAVE-M QA M2): with
        # the committed gate off, shutdown records nothing in the history.
        if _s.state in {"running", "paused"}:
            await _s.stop(actor="lifespan_shutdown", drain=False)
    except Exception:
        pass
    try:
        from app.services import alert_operations as _alert_ops

        await _alert_ops.stop_background_loop()
    except Exception:
        pass
    await market_service.stop_background()
    await event_bus.publish(DomainEvent("system.shutdown", {"version": settings.version}))
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    env = (os.getenv("ENV") or os.getenv("APP_ENV") or os.getenv("SHEKAR_ENV") or "").strip().lower()
    is_production = env in {"prod", "production"}
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="پلتفرم تابلوخوانی و تحلیل هوشمند بورس ایران — Excellent Edition - با AI، مدیریت ریسک، کیفیت داده، تشخیص آنومالی، معماری رویداد-محور، متریکس پرومتئوس",
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
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
    # WS-HARDEN-1/W2: RequestIdMiddleware در انتهای create_app اضافه می‌شود تا OUTERMOST باشد؛
    # در غیر این صورت پاسخ‌های short-circuit (مثل 401 مهمان ناخواجه) بدون X-Request-ID و
    # لاگ‌های middleware های بیرونی بدون contextvar می‌مانند.
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
        elif path.startswith("/api") and is_public_path(path):
            # Probe routes stay reachable; handlers redact market/notifier details.
            need = False
        elif s.auth_required and path.startswith("/api") and not is_public_path(path):
            need = True
        elif s.api_key and is_sensitive_path(path):
            need = True
        elif s.private_mode and path.startswith("/api") and not is_public_path(path):
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
    app.include_router(chart_pro_router)  # v1.0 chart-pro (WS-10) — deterministic seeded series, SYNTHETIC/Paper only
    app.include_router(analytics_router)  # WDA-3 (2026-11-02) — additive analytics router next to chart_pro; reuses market_service trust envelope, never "live"
    app.include_router(forex_router)  # v0.9 Forex router (capability description; no vendor-comparative claim)
    app.include_router(auth_router)  # v1.5 حالت خصوصی (فقط مالک)
    app.include_router(alert_ops_router)  # GOV-41 D-AI-30 — Synthetic/Paper in-product alert inbox (no external egress)
    app.include_router(strategy_lab_router)  # MASTER-RADAR (2026-11-04) — additive Strategy Lab; synthetic-only, approval state machine, no live egress
    app.include_router(indicator_api_router)  # MASTER-RADAR (2026-11-04) — additive indicator catalog/compute; no downloaded-code execution
    app.include_router(analyst_api_router)  # MASTER-RADAR (2026-11-04) — additive deterministic symbol analyst; provenance on every claim
    app.include_router(user_indicator_api_router)  # MASTER-RADAR WAVE-B (2026-11-04) — additive UIDL-1 user-indicator DSL lifecycle + deterministic compute; SYNTHETIC-seeded only, no code execution beyond the restricted interpreter
    app.include_router(data_quality_api_router)  # MASTER-RADAR WAVE-2 (2026-11-04) — additive data-quality center; fixture-universe audit/coverage only, canonical non-live provenance on every endpoint
    app.include_router(product_loops_api_router)  # MASTER-RADAR WAVE-F (2026-11-05) — additive five product-loop surface; declared fixtures + live governed checks, no scheduler/egress, gates unchanged
    app.include_router(ai2_generation_api_router)  # WAVE-K (OA-3, 2026-11-05) — additive governed AI-2 generation seam; fail-closed gates (AI2_ENABLED default 0), typed-spec-only model surface, deterministic emitter, human-approval-only transitions, no egress
    app.include_router(scheduler_api_router)  # WAVE-M (OA-4, 2026-11-06) — additive bounded LOCAL internal scheduler; fail-closed (SCHEDULER_ENABLED default 0), append-only run history, pause/resume/stop/kill-switch, no egress/no broker/no promotion authority
    app.include_router(research_memory_api_router)  # 2026-11-08 owner directive (AI-3 real integration) — additive durable research-memory surface; fail-closed key posture, durable audited chain, no purge/no egress
    app.include_router(ai_ma_api_router)  # WAVE-AB3 (WP-C, 2026-11-08) — additive governed AI-MA orchestration; fixed 3-step advisory plan, deterministic synthetic-safe executors, autonomy ceiling L2, no egress/no mutation/no promotion

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
            if p.endswith("/sw.js") or p.endswith("/sw-register.js"):
                resp.headers["Cache-Control"] = "no-store"
            elif p.startswith("/static/"):
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

    # WS-HARDEN-1/W2: آخرین add_middleware = بیرونی‌ترین لایه؛ پل request_id همه‌ی
    # middleware ها (auth/CORS/audit/rate-limit) و همه پاسخ‌ها را پوشش می‌دهد.
    app.add_middleware(RequestIdMiddleware)

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
