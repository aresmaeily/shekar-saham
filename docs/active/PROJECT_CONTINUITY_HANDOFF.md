# PROJECT CONTINUITY HANDOFF — RADAR BOURSE / رادار بورس

Date: 2026-08-09  
Scope: P3.46 — Repository Synchronization & Project Continuity Handoff  
Repository root: `/home/user/repo`  
Continuity role: this file is an operational handoff dossier and must be updated after every significant phase.

---

## 1. PROJECT IDENTITY

| Item | Value |
|---|---|
| Project Name | RADAR BOURSE |
| Persian Name | رادار بورس |
| Historical / technical repository slug | Shekar-Saham / `shekar-saham` |
| Product purpose | تحلیل و هوشمندی بازار بورس ایران |
| Current product identity | RADAR BOURSE / رادار بورس |
| Market scope | Iranian Stock Market |
| Current architecture | Existing FastAPI backend + static frontend + Electron shell + SQLite/store + market/data/AI/filter intelligence layers |

Rules:

- Do not redesign the architecture from scratch.
- Do not create parallel engines or duplicate services.
- Do not use historical product names for new/current product-facing surfaces.
- Historical names may remain only in historical archive records or real technical URLs/slugs.

---

## 2. REPOSITORY IDENTITY

### Paths

| Component | Path |
|---|---|
| Project Root | `/home/user/repo` |
| Backend | `/home/user/repo/backend` |
| Backend app | `/home/user/repo/backend/app` |
| Frontend | `/home/user/repo/frontend` |
| Electron | `/home/user/repo/electron` |
| Android scaffold | `/home/user/repo/android-app` |
| Scripts | `/home/user/repo/scripts` |
| Active docs | `/home/user/repo/docs/active` |
| Architecture docs | `/home/user/repo/docs/architecture` |
| Archive docs | `/home/user/repo/docs/archive` |
| Tests | `/home/user/repo/backend/tests` |
| Configuration files | `/home/user/repo/.env.example`, `/home/user/repo/Dockerfile`, `/home/user/repo/docker-compose.yml`, `/home/user/repo/install.sh`, `/home/user/repo/start.sh` |

### Git identity

Verified by command output during P3.46 handoff:

```text
Branch: main
Current HEAD: 4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce
Current commit message: P3.44: Pre-Installation Repository Hardening and RADAR BOURSE Integrity
Working tree before creating this handoff file: CLEAN
Remote URL: https://github.com/aresmaeily/shekar-saham.git
Remote branch: refs/heads/main
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Local vs remote: 21 commits ahead, 0 commits behind
GitHub push status: BLOCKED BY AUTHENTICATION
```

### Important recent commits

| Phase | Commit SHA | Commit Message | Purpose | Status |
|---|---|---|---|---|
| P3.35 | `7f306000df0cc55e54a8977967d8960ceb22dfdc` | `P3.35: Alpha Target Validation and Controlled Launch` | Alpha target validation and controlled launch gate | Complete locally; target launch deferred |
| P3.36 | `76b35c17fa0f57cda8d27fb27a6ac4f4026d5572` | `P3.36: Target Validation and Controlled Alpha Launch` | Target-system final validation gate | Complete locally; target validation deferred |
| P3.37 | `11d376a517ed21125ce979ec26bf30f93bf0377b` | `P3.37: Alpha Gate Closure Validation` | Alpha gate closure validation | Complete locally; target validation deferred |
| P3.38 | `ca5bcb9031aeb93c33f61134e16124c2ae9cb7d0` | `P3.38: Product Direction and AI Intelligence Architecture Lock` | Product/AI/filter/market architecture lock | Complete locally |
| P3.39 | `3b7d6ca044e0d9f151bcd320949b496c777fe968` | `P3.39: AI Intelligence Core` | AIIntelligenceCore implementation | Complete locally; tests passed in later regression |
| P3.40 | `5aa8b7e54154305cfe18950e34068eb23177e214` | `P3.40: Market Intelligence and Continuous Monitoring` | Market intelligence service and APIs | Complete locally; scheduler not enabled |
| P3.41 | `0bfcee5ab66b177b70f217d26032b1559a783cc7` | `P3.41: Filter Intelligence and Self-Optimization Engine` | Filter registry/versioning/performance/proposals | Complete locally |
| P3.42 | `fe3d1616cc081fd85d69b668f08faf3ba11e9abc` | `P3.42: Repository Completion and Release Readiness` | Repository audit + AI/Filter integration hardening | Complete locally |
| P3.43 | `795db6975399fd7827b76229d298f6b46c65583e` | `P3.43: Repository Completion and RADAR BOURSE Hardening` | Product terminology hardening | Complete locally |
| P3.44 | `4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce` | `P3.44: Pre-Installation Repository Hardening and RADAR BOURSE Integrity` | Pre-install hardening and second-pass terminology | Complete locally |

---

## 3. PHASE HISTORY

| Phase | Title | Commit | Purpose | Implemented | Validated | Deferred | Important Notes |
|---|---|---|---|---|---|---|---|
| P3.35 | Alpha Target Validation and Controlled Launch | `7f30600` | Local alpha gate validation | Reports/docs/archive | Local validation only | Target Windows launch | No production/target install claimed |
| P3.36 | Target Validation and Controlled Alpha Launch | `76b35c1` | Prepare final target validation gate | Reports/docs/archive | Local validation only | Target Windows validation | Installation not executed |
| P3.37 | Alpha Gate Closure Validation | `11d376a` | Close alpha gate locally | Reports/docs/archive | Local validation only | Browser/Electron/Windows target | No GitHub sync claim |
| P3.38 | Product Direction and AI Intelligence Architecture Lock | `ca5bcb9` | Lock product direction and AI/filter/market architecture | Architecture docs | Documentation-level validation | Runtime feature work | No runtime code added |
| P3.39 | AI Intelligence Core | `3b7d6ca` | Deterministic structured intelligence core | `domain/ai_intelligence.py`, API endpoint, tests | Later regression passed | Live LLM provider | Non-live data blocks actionable live recommendation |
| P3.40 | Market Intelligence and Continuous Monitoring | `5aa8b7e` | Market snapshot/regime/industries/opportunities/events | `market_intelligence.py`, service, endpoints, tests | Later regression passed | 24/7 scheduler | Callable monitoring cycle only |
| P3.41 | Filter Intelligence and Self-Optimization Engine | `0bfcee5` | Registry/version/performance/evaluation/proposals/human review | Domain/service/API/tests/docs | Later regression passed | UI approval, scheduler, real live performance | AI cannot modify production filters |
| P3.42 | Repository Completion and Release Readiness | `fe3d161` | Close AI ↔ Filter Intelligence service integration | `build_ai_filter_context`, AIService wiring, tests | Later regression passed | GitHub sync | GitHub push blocked by auth |
| P3.43 | Repository Completion and RADAR BOURSE Hardening | `795db69` | Product terminology cleanup | Backend/frontend/electron/docs naming hardening | Later regression passed | GitHub sync, installation | Old product name only in archive history |
| P3.44 | Pre-Installation Repository Hardening and RADAR BOURSE Integrity | `4e6cf72` | Pre-install repo hardening, artifacts, second-pass terminology | CI/Docker/WS/Electron/Android/docs hardening | `132 passed, 1 warning` in P3.44 | Installation, Windows target, GitHub sync | P3.44 archive verified |
| P3.45 | Target Validation & Controlled Installation Readiness | No commit; inspection only | Repository-side target readiness inspection | No file changes | Baseline/target/dependency/env/startup/security/database audit | Windows target validation, installation, GitHub sync | Repository-side inspection COMPLETE; Windows target NOT ACCESSIBLE; installation NOT STARTED; GitHub sync BLOCKED BY AUTHENTICATION |
| P3.46 | Repository Synchronization & Project Continuity Handoff | This document currently uncommitted until review | Create continuity source-of-truth handoff file and check GitHub sync status | This file only | `git diff --check` required after creation | GitHub sync if auth absent | No code/config/db/dependency/install changes allowed |

---

## 4. ARCHITECTURE MAP

### High-level runtime path

```text
Frontend
  ↓ relative /api + /ws/live
FastAPI app in backend/app/main.py
  ↓
API routers in backend/app/api
  ↓
Services in backend/app/services
  ↓
Domain contracts in backend/app/domain
  ↓
Store / SQLite in backend/app/data/store.py
  ↓
Providers in backend/app/data/providers.py + mock_market.py + forex_provider.py
```

### AI / Intelligence integration path

```text
AIContextBuilder
  ↓
FilterIntelligenceService.build_ai_filter_context(...)
  ↓
filter_context.filter_intelligence
  ↓
AIIntelligenceCore.evaluate(...)
  ↓
Structured IntelligenceResult
```

### Market + Filter + Backtest + AI path

```text
MarketService
  ↓
MarketIntelligenceService
  +
FilterIntelligenceService
  ↓
Filter Registry / Versions / Performance Records
  ↓
Backtest / Walk-Forward / Forward Test
  ↓
Data Trust + Risk + Evidence
  ↓
AIIntelligenceCore
  ↓
Recommendation / Decision Support
```

### Component map

| Area | File | Class / Function / API | Responsibility | Dependencies | Current Status |
|---|---|---|---|---|---|
| FastAPI app | `backend/app/main.py` | `create_app`, `lifespan`, `app`, `/ws/live` | App creation, security middleware, routers, static frontend, WS | core, routers, market_service, ws_hub | Implemented |
| Security | `backend/app/core/security.py` | `authorize_request`, `authorize_cookie`, `authorize_ws`, `require_api_key`, `SecurityHeadersMiddleware` | Auth, sessions, headers, public/sensitive path rules | config | Implemented |
| Config/Data Trust | `backend/app/core/config.py` | `Settings`, `build_data_trust_context`, `classify_data_trust_state` | Env config and trust states | none | Implemented |
| Store | `backend/app/data/store.py` | `Store`, singleton `store` | SQLite persistence, settings_kv, snapshots, filters, alerts, backtest history | sqlite3, config | Implemented |
| Providers | `backend/app/data/providers.py` | `MarketDataProvider.fetch`, `_from_tsetmc`, `_from_brsapi`, `_from_mock` | Market data fetch and fallback | config, mock_market, schemas | Implemented; live not verified |
| Mock provider | `backend/app/data/mock_market.py` | `generate_mock_market` | Demo/fallback data | schemas | Implemented |
| Market service | `backend/app/services/market_service.py` | `MarketService`, singleton `market_service` | Data refresh, analysis orchestration, frontend/API service methods | providers, store, engines, notifier, ws_hub | Implemented |
| AI service | `backend/app/services/ai_service.py` | `AIContextBuilder`, `FallbackAIProvider`, `AIService` | AI assistant/analyst/optimizer/intelligence and context building | AIIntelligenceCore, Filter DSL, FilterIntelligenceService | Implemented |
| AI core | `backend/app/domain/ai_intelligence.py` | `AIIntelligenceCore.evaluate` | Deterministic evidence aggregation and recommendations | none | Implemented |
| Market intelligence | `backend/app/services/market_intelligence_service.py` | `run_market_monitoring_cycle`, `list_events` | Regime/snapshot/opportunities/industries/events | Store, domain models, AI core | Implemented |
| Market intelligence domain | `backend/app/domain/market_intelligence.py` | `MarketIntelligenceSnapshot`, `IndustryIntelligence`, `OpportunityRank`, `IntelligenceEvent` | P3.40 contracts | AI intelligence domain | Implemented |
| Filter intelligence | `backend/app/services/filter_intelligence_service.py` | `FilterIntelligenceService` | Registry/version/performance/eval/decay/proposals/review/AI context | Store, Filter DSL, Backtest, Market Intelligence | Implemented |
| Filter intelligence domain | `backend/app/domain/filter_intelligence.py` | `FilterVersion`, `PerformanceRecord`, `OptimizationProposal`, etc. | P3.41 contracts | none | Implemented |
| Filter DSL | `backend/app/engines/filter_dsl.py` | `validate_filter`, `run_filter`, `eval_filter` | Safe screen/filter expression language | none | Implemented |
| Strategy | `backend/app/domain/strategy.py` | `FilterStrategy`, `StrategyRegistry` | Strategy contracts/adapters | Filter DSL | Implemented |
| Backtest | `backend/app/engines/backtest.py` | `run_filter_strategy_backtest`, `run_walk_forward`, `run_forward_test`, `backtest_from_market` | Backtest/walk-forward/forward-test simulation | Store, strategy, config | Implemented |
| Screener | `backend/app/engines/screener.py` | `analyze_market` | Market analysis/signals | metrics, config, schemas | Implemented |
| Confluence | `backend/app/engines/confluence.py` | `build_confluence_board`, `pick_notify_alerts` | Combined technical/fundamental/flow board | fundamental, metrics, tablocastic | Implemented |
| Fundamental | `backend/app/engines/fundamental.py` | `build_deep_fundamental`, `rank_value_stocks` | Synthetic/demo fundamental scoring | config, schemas | Implemented as synthetic/demo |
| Chart | `backend/app/api/chart.py`, `backend/app/engines/chart_builder.py` | `/api/chart/{symbol}`, OHLCV/indicators | Chart data and overlays | store, market_service, chart engine | Implemented |
| Frontend | `frontend/index.html`, `frontend/js/main.js`, `frontend/js/core/api.js` | static dashboard, relative `/api` calls, `/ws/live` | Browser UI | backend static serving | Static validation passed; browser E2E deferred |
| Electron | `electron/main.js`, `electron/package.json` | `RADAR_BOURSE_URL` / legacy `SHEKAR_URL` fallback | Desktop shell | running backend | Runtime validation deferred |

---

## 5. IMPORTANT FILE MAP

| Path | Purpose | Why Important | Related Components |
|---|---|---|---|
| `backend/app/main.py` | FastAPI app entry | App creation, lifespan, middleware, routers, static frontend, WebSocket | Backend startup, security, frontend serving |
| `backend/app/core/config.py` | Settings and data trust | Env vars, data source, trust state, stale/unavailable rules | Providers, services, security |
| `backend/app/core/security.py` | Security model | API key, bearer, cookie session, WS auth, headers, guards | Main middleware, auth routes |
| `backend/app/core/crypto.py` | Encryption helpers | Encrypt/decrypt notifier tokens; FERNET/API key fallback | Notifier, startup warnings |
| `backend/app/core/rate_limiter.py` | Rate limiting middleware | IP/path-based request throttling | FastAPI middleware |
| `backend/app/core/audit.py` | Audit logging | Sensitive action logging into store | main middleware/store |
| `backend/app/api/routes.py` | Main API router | Most market/filter/AI/backtest/notify endpoints | Services, store, engines |
| `backend/app/api/auth.py` | Auth router | login/logout/status with HttpOnly cookie | security, UI auth |
| `backend/app/api/chart.py` | Chart API | OHLCV/chart overlay endpoints | chart engine/store |
| `backend/app/api/excellent.py` | Excellent/risk/data-quality APIs | data quality, anomalies, risk, metrics, audit | engines/core/store |
| `backend/app/api/forex.py` | Forex scaffold API | secondary forex chart/explain endpoints | forex_provider/charts |
| `backend/app/domain/ai_intelligence.py` | AI core domain | Structured evidence/recommendation logic | AI service/market intelligence |
| `backend/app/domain/market_intelligence.py` | Market intelligence contracts | Snapshot/regime/industry/opportunity/events | MarketIntelligenceService |
| `backend/app/domain/filter_intelligence.py` | Filter intelligence contracts | Registry/version/performance/proposal/review models | FilterIntelligenceService |
| `backend/app/domain/strategy.py` | Strategy contracts | FilterStrategy adapter and registry | Backtest/filter DSL |
| `backend/app/services/market_service.py` | Core market service | Provider refresh, store writes, engine orchestration | API, WS, analysis |
| `backend/app/services/ai_service.py` | AI service/context builder | Assistant/analyst/optimizer/intelligence APIs | AI core, filter intelligence |
| `backend/app/services/market_intelligence_service.py` | P3.40 market intelligence | Monitoring cycle/regime/opportunities/events | AI core, Store |
| `backend/app/services/filter_intelligence_service.py` | P3.41/P3.42 filter intelligence | Registry/version/performance/eval/proposals/context | Backtest, Store, Market Intelligence |
| `backend/app/services/notifier.py` | Notifications | Telegram/Bale/dry-run notify config and token encryption | config/crypto/store |
| `backend/app/services/ws_hub.py` | WebSocket hub | connect/broadcast/send live events | main.py, market_service |
| `backend/app/data/providers.py` | Market providers | TSETMC/BRSAPI/mock fallback and cache | MarketService |
| `backend/app/data/mock_market.py` | Mock market data | Offline/demo fallback | providers/tests |
| `backend/app/data/store.py` | SQLite store | DB schema, settings, snapshots, filters, portfolio, backtests | services/APIs |
| `backend/app/engines/filter_dsl.py` | Safe filter DSL | Filter validation/evaluation | strategy, services, API |
| `backend/app/engines/backtest.py` | Backtest stack | Backtest/walk-forward/forward-test | Filter intelligence/backtest API |
| `backend/tests/` | Test suite | 20 test files; last baseline 132 passed | Regression |
| `frontend/` | Static UI | Dashboard/symbol page/API/WS/auth | Backend static serving |
| `electron/` | Desktop shell | Electron entry and package metadata | Windows desktop preparation |
| `scripts/` | Validation scripts | Alpha env/runtime/provider/frontend validators | Target readiness |
| `Dockerfile` | Docker backend image | Optional container startup | Docker path |
| `docker-compose.yml` | Optional compose stack | service/container/env/volumes | Docker path |
| `install.sh` | Native/Docker helper | Target install helper, not yet run in target | Installation plan |
| `start.sh` | Backend startup helper | Native backend run with proxy handling | Local/target startup |
| `.env.example` | Safe env template | Target config contract without real secrets | Install readiness |
| `README.md` | User/dev overview | Quick start and product overview | Handoff docs |
| `docs/active/` | Active phase docs | current reports/runbooks | Project continuity |

---

## 6. STARTUP FLOW

```text
Shell
  ↓
Environment (.env / exported env vars)
  ↓
Python / virtualenv
  ↓
Uvicorn
  ↓
FastAPI app.main:app
  ↓
create_app()
  ↓
lifespan()
  ↓
validate_security_configuration(settings)
  ↓
Store initialization
  ↓
SQLite data/shekar.db initialization if needed
  ↓
MarketService initial refresh
  ↓
Providers: TSETMC / BRSAPI / mock fallback
  ↓
Routers included
  ↓
Static frontend mounted
  ↓
WebSocket /ws/live
  ↓
Electron shell connects to backend URL if used
```

| Step | Entry Point / Command | File | Important Function | Failure Risks |
|---|---|---|---|---|
| Shell | `./start.sh` or manual uvicorn | `start.sh` | exports `PYTHONPATH`, `DATA_SOURCE`, `HOST`, `PORT` | Missing Python/deps, occupied port |
| Environment | `.env` from `.env.example` | `config.py`, `.env.example` | `Settings` | Missing private/API/FERNET config in secure mode |
| Python deps | `pip install -r backend/requirements.txt` | `backend/requirements.txt` | package install | dependency resolution/build failure |
| Uvicorn | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers` | `backend/app/main.py` | `app = create_app()` | import/startup error |
| FastAPI | import `app.main:app` | `backend/app/main.py` | `create_app()` | middleware/router error |
| Lifespan | automatic | `backend/app/main.py` | `lifespan` | security validation failure, provider error |
| Security validation | lifespan | `core/security.py` | `validate_security_configuration` | missing secrets in private/production |
| Store/SQLite | import/use Store | `data/store.py` | `Store._init_db` | write permission/disk/SQLite error |
| Market refresh | lifespan | `services/market_service.py` | `refresh(force=True)` | provider/network fallback |
| Providers | market refresh | `data/providers.py` | `MarketDataProvider.fetch` | TSETMC unreachable, BRSAPI key missing |
| Routers | app creation | `main.py`, `api/*.py` | `include_router` | import errors |
| Static frontend | app creation | `main.py` | `app.mount('/static', ...)` | missing frontend directory/assets |
| WebSocket | runtime | `main.py` | `ws_live` | auth failure/connection handling |
| Electron | `npm start` in `electron` | `electron/main.js` | `createWindow` | backend not running, npm deps absent |

---

## 7. INSTALLATION KNOWLEDGE

Commands are documented here but must not be run until the owner authorizes installation.

### Requirements

| Requirement | Evidence / Source | Status |
|---|---|---|
| Python | `install.sh` requires `python3`; Dockerfile uses `python:3.13-slim`; current local Python 3.13.14 | Required |
| pip | Needed for `backend/requirements.txt` | Required |
| Node.js/npm | Electron shell only | Optional for backend; required for Electron |
| Electron | `electron/package.json` declares `electron` and `electron-builder` | Not installed in repo; install later only |
| Browser | Manual frontend validation | Required for UI validation |
| Git | Repository acquisition/sync | Required |
| Docker/Docker Compose | Optional path via Dockerfile/docker-compose | Optional; not available in current env |
| Windows | Target desktop install | Deferred; not accessible here |

### Native setup commands

```bash
cd /path/to/radar-bourse
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
cd backend
pip install -r requirements.txt
```

### Environment setup

```bash
cp .env.example .env
# Edit .env securely. Never commit .env.
```

### Backend startup

```bash
cd backend
PYTHONPATH=. python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

or from repo root:

```bash
./start.sh
```

### Health checks

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/status
curl http://127.0.0.1:8000/api/live/status
```

### Frontend check

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/symbol/فملی
```

### Electron setup and runtime

```bash
cd electron
npm install
set RADAR_BOURSE_URL=http://127.0.0.1:8000
npm start
```

Electron packaging command declared but not target-validated:

```bash
npm run build
```

---

## 8. ENVIRONMENT VARIABLES

Never write secret values into this document or commits.

| NAME | Required? | Default | Used By | Secret? | Production Impact | Live-data Impact | Notes |
|---|---|---|---|---:|---|---|---|
| `DATA_SOURCE` | Yes for controlled target behavior | `auto` | config/providers/scripts/docker | No | Select provider | Controls live/mock/brsapi/tsetmc mode | Values: `mock`, `tsetmc`, `brsapi`, `auto` |
| `POLL_SECONDS` | Optional | `30` | market polling | No | Refresh interval | None direct | In `.env.example` |
| `REQUEST_TIMEOUT` | Optional | `12` | providers | No | Provider timeout | Affects provider reliability | In `.env.example` |
| `TSETMC_BASE` | Optional | `https://cdn.tsetmc.com` | providers | No | TSETMC endpoint | Needed for TSETMC provider | In `.env.example` |
| `DATA_STALE_AFTER_SEC` | Optional but important | `300` | data trust | No | Freshness gate | Stale vs current labeling | In `.env.example` |
| `DATA_CLOCK_SKEW_TOLERANCE_SEC` | Optional | `0` | data trust | No | Future timestamp tolerance | Trust gating | In `.env.example` |
| `PRIVATE_MODE` | Required for private target | `0` code; example `1` | config/security/main/auth | No | Enables private gate | None | Production/private safety |
| `PRIVATE_PASSWORD` | Required if private without API key | none | auth/security | YES | Owner login | None | Do not print value |
| `API_KEY` | Recommended / auth | none | auth/security/frontend optional | YES | API/Bearer auth; encryption fallback | None | Do not print value |
| `FERNET_KEY` | Required for stable token encryption | none | crypto/notifier | YES | Stable encrypted tokens | None | Generate securely |
| `COOKIE_SECURE` | Required on HTTPS | `0` | auth cookie | No | Secure cookie | None | Use `1` on HTTPS |
| `TRUST_PROXY` | Required behind trusted reverse proxy | `0` | main/rate limiter | No | Proxy headers/client IP | None | Avoid spoofable XFF |
| `CORS_ORIGINS` | Recommended for deployment | localhost defaults | config/main CORS | No | Browser CORS | None | Comma-separated origins |
| `BRSAPI_KEY` | Required only for BRSAPI live | none | providers | YES | BRSAPI access | Required for BRSAPI live validation | Missing currently |
| `HOST` | Optional | `0.0.0.0` | config/start.sh | No | Bind address | None | Default target bind |
| `PORT` | Optional | `8000` | config/start.sh/docker | No | Backend port | None | Default 8000 |
| `DEBUG` | Optional | `0` | config/main | No | reload/debug | None | Do not use in prod |
| `AUTH_REQUIRED` | Optional explicit auth | derived | config/security | No | Auth gate | None | Also true if API_KEY/private |
| `TELEGRAM_BOT_TOKEN` | Optional | none | notifier | YES | Telegram alerts | None | Optional |
| `TELEGRAM_CHAT_ID` | Optional | none | notifier | Maybe | Telegram alerts | None | Optional |
| `BALE_BOT_TOKEN` | Optional | none | notifier | YES | Bale alerts | None | Optional |
| `BALE_CHAT_ID` | Optional | none | notifier | Maybe | Bale alerts | None | Optional |
| `HISTORY_KEEP_HOURS` | Optional | code default | pruning | No | Retention | None | Optional |
| `BIG_MOVE_WINDOW_SEC` | Optional | code default | big moves | No | Big move window | None | Optional |
| `BIG_MOVE_MIN_SCORE` | Optional | code default | big moves | No | Filtering threshold | None | Optional |
| `FLOW_MIN_COVERAGE_SEC` | Optional | code default | flow logic | No | Flow coverage threshold | None | Optional |
| `NOTIFY_MIN_ENTRY` | Optional | code default | notifier | No | Notification threshold | None | Optional |
| `NOTIFY_MIN_EXIT` | Optional | code default | notifier | No | Notification threshold | None | Optional |
| `NOTIFY_COOLDOWN_SEC` | Optional | code default | notifier | No | Notification cooldown | None | Optional |
| `FUND_CACHE_TTL` | Optional | code default | fundamental cache | No | Cache TTL | None | Optional |
| `TRUST_LEVEL` | Legacy/compat | optional | config/trust | No | Compatibility | Can influence legacy trust level | Optional |
| `TZ` | Optional | environment default | Docker/config | No | Timezone | None | Optional |
| `RADAR_BOURSE_URL` | Optional Electron | none | electron/main.js | No | Electron backend URL | None | Preferred current env name |
| `SHEKAR_URL` | Legacy fallback | none | electron/main.js | No | Electron backend URL | None | Compatibility fallback |
| `ENV` / `APP_ENV` / `SHEKAR_ENV` | Optional production guard | none | security | No | Production guard | None | Used by `validate_security_configuration` |

---

## 9. SECURITY MODEL

### Modes and secrets

- `PRIVATE_MODE`: enables owner/private workflow.
- `AUTH_REQUIRED`: API auth requirement; derived from env or API/private mode.
- `API_KEY`: supports `X-API-Key` and Bearer-style authorization.
- `PRIVATE_PASSWORD`: owner UI login secret.
- `FERNET_KEY`: stable encryption key for stored notification tokens.

### Session cookie

- Login route: `POST /api/auth/login`.
- Cookie is HttpOnly and SameSite strict.
- Cookie name in code is `shekar_session` for compatibility.

### WebSocket authentication

- Endpoint: `/ws/live`.
- When auth/private mode is active, WS checks:
  - `x-api-key` header,
  - query `api_key`,
  - query `token`,
  - cookie via `authorize_ws`.

### Production guard

`backend/app/core/security.py::validate_security_configuration` enforces:

- `PRIVATE_MODE` requires `PRIVATE_PASSWORD` or `API_KEY`.
- Production requires `AUTH_REQUIRED`, `PRIVATE_MODE`, or `API_KEY`.
- Production requires stable `FERNET_KEY` or `API_KEY` for token encryption.

### Public paths

From `backend/app/core/security.py` and `backend/app/main.py`:

```text
/api/health
/api/status
/api/live/status
/api/auth/*
/docs
/openapi.json
/redoc
/static
/favicon
/
/symbol
```

### Protected / sensitive prefixes

```text
/api/notify
/api/config
/api/portfolio
/api/filter/saved
/api/confluence/notify-now
/api/backtest
```

Additional rule:

```text
If auth_required/private_mode is active, non-public /api routes require auth.
```

---

## 10. DATA TRUST MODEL

Absolute rules:

```text
mock != live
synthetic != live
fallback != live
stale != live
unavailable != live
```

Current verified environment/provider status from P3.44/P3.45:

```text
TSETMC:
  last_source: mock_fallback
  live_verified: false

BRSAPI:
  BRSAPI_KEY: missing
  last_source: mock_fallback
  live_verified: false
```

Live data can only be declared verified when all are true:

1. Provider validation command actually runs against the intended provider.
2. Returned `data_trust.state == "live"`.
3. Returned `data_trust.is_live is True`.
4. No stale/future/unavailable/fallback warning invalidates it.
5. The final report cites the actual command output.

Needed for live validation:

- Target network that can reach TSETMC or provider.
- If using BRSAPI: securely configured `BRSAPI_KEY`.
- Correct `DATA_SOURCE`.
- Fresh timestamp within `DATA_STALE_AFTER_SEC`.
- No fallback source.

Never claim real profitability from mock/synthetic/fallback data.

---

## 11. DATABASE

| Item | Value |
|---|---|
| Type | SQLite |
| ORM | NOT PRESENT |
| DB path | `/home/user/repo/data/shekar.db` |
| Store file | `backend/app/data/store.py` |
| Store class | `Store` |
| Singleton | `store = Store()` |
| Connection | sync `sqlite3.connect`, `row_factory=sqlite3.Row` |
| Locking | `threading.RLock` |
| WAL | `PRAGMA journal_mode=WAL` |
| Synchronous | `PRAGMA synchronous=NORMAL` |
| Transaction management | contextmanager commits/rolls back/closes |
| Migration mechanism | `PRAGMA user_version` inside `_run_migrations` |
| Formal migration framework | NOT PRESENT |

Tables created by `_init_db()`:

```text
snapshots
symbol_ticks
alerts
portfolio
settings_kv
big_moves
saved_filters
notify_log
backtest_runs
```

Known migration:

```text
user_version 1: ALTER TABLE symbol_ticks ADD COLUMN flow_score REAL DEFAULT 0
```

Backup mechanism:

- `Store.backup(keep=7)`.
- WAL checkpoint then copies DB to `data/backups/shekar-<timestamp>.db`.
- Startup may call daily backup in `backend/app/main.py` lifespan.

Required directories:

```text
/home/user/repo/data
/home/user/repo/data/backups
```

Write requirements:

- Backend process needs write access to `data/` and `data/backups/`.

No database modification was performed for this P3.46 handoff.

---

## 12. TESTING BASELINE

Latest actual full test baseline from P3.44:

```text
132 passed, 1 warning
pyflakes: PASS
Node syntax checks: PASS
Frontend static validation: PASS
Alpha environment validation: PASS
Alpha runtime validation: PASS
Provider fallback validation: PASS
```

Test paths:

```text
/home/user/repo/backend/tests
```

Important test commands:

```bash
cd /home/user/repo/backend
../.venv/bin/python -m compileall -q app tests
PYTHONPATH=. ../.venv/bin/python -m pytest -q tests
../.venv/bin/python -m pyflakes app
node --check ../frontend/js/modules/render/trust.js
node --check ../frontend/js/main.js
```

Validation scripts:

```bash
cd /home/user/repo
.venv/bin/python scripts/validate_alpha_environment.py

cd /home/user/repo/backend
PYTHONPATH=. ../.venv/bin/python ../scripts/validate_alpha_runtime.py
PYTHONPATH=. ../.venv/bin/python ../scripts/validate_providers.py --source tsetmc
PYTHONPATH=. ../.venv/bin/python ../scripts/validate_providers.py --source brsapi

cd /home/user/repo
.venv/bin/python scripts/validate_frontend_static.py
```

Tests were not re-run during P3.46 handoff file creation to avoid unintended runtime/cache/database artifacts.

---

## 13. ARTIFACTS

Artifacts discovered in `/home/user/deliverables` and verified by SHA where possible.

### Required recent artifacts

| Artifact | Path | Purpose | SHA-256 | File Count | Status |
|---|---|---|---|---:|---|
| P3.43 archive | `/home/user/deliverables/P3.43_RADAR_BOURSE_FULL_PROJECT_795db69.zip` | Full project archive after P3.43 | `e15bbdf46b65ccf80493ebe599223dbf0fe0a9640af11ff7d000b4b78fcceb63` | 644 | ZIP OK |
| P3.44 archive | `/home/user/deliverables/P3.44_RADAR_BOURSE_FULL_PROJECT_4e6cf72.zip` | Full project archive after P3.44 | `3a8618e53cefbe4ae180ddda700a40497d81c0e83a9f6fe456be045bca6aa026` | 674 | ZIP OK |
| P3.42 repository completion | `/home/user/deliverables/REPOSITORY_COMPLETION_fe3d161.zip` | Repository completion archive | `deb862e9833f80ccab7b9d973e1c2a8f005a574772dd8eb4f97de0046d2955a5` | 588 | ZIP OK |
| P3.41 archive | `/home/user/deliverables/P3.41_FILTER_INTELLIGENCE_FULL_PROJECT_0bfcee5.zip` | P3.41 full project | `e42cc54396c4a928d70e434389ab91e34436f8f0f9970179111adf36aeb7acb9` | 216 | ZIP OK |
| P3.40 archive | `/home/user/deliverables/P3.40_MARKET_INTELLIGENCE_FULL_PROJECT_5aa8b7e.zip` | P3.40 full project | `706178ab2b705e7664711c8d7d7ffe7ae0f975f358c642117a070ab0f1ae0668` | 540 | ZIP OK |
| P3.39 archive | `/home/user/deliverables/P3.39_AI_INTELLIGENCE_CORE_FULL_PROJECT_fd76164.zip` | P3.39 full project | `7d3b6c0eac6752846e07ad6148ab71e31d47f4c0ea64e5a0e06bc1c19d9f3a04` | 511 | ZIP OK |

### Other phase archives present

| Phase | Path | SHA-256 | File Count / Status |
|---|---|---|---|
| P3.24 | `/home/user/deliverables/P3.24_FULL_PROJECT_BACKUP_197c44a.zip` | `9dd1c0f00757420387df3e06bfed19d9421ded9e060889b3b6160939d53ce23c` | 168, ZIP OK |
| P3.25 | `/home/user/deliverables/P3.25_FULL_PROJECT_BACKUP_6a50653.zip` | `453e22ee7f0b44c1ebd08127bf364d863bd86cfdd695893a09602ad41106443c` | 252, ZIP OK |
| P3.26 | `/home/user/deliverables/P3.26_FULL_PROJECT_BACKUP_1586584.zip` | `f570d5be348f926565a788bdeb258de985b36c27a9700e003e7774c5bfd959f6` | 280, ZIP OK |
| P3.27 | `/home/user/deliverables/P3.27_FULL_PROJECT_BACKUP_efe37cf.zip` | `34e6bb1580606b956c2a1ea6e1163a2d74d053abb4052f1f8b222053615d7166` | 302, ZIP OK |
| P3.28 | `/home/user/deliverables/P3.28_FULL_PROJECT_BACKUP_e655464.zip` | `4ff57628afff839f657f0f6d6f03be2db0b68141ae5353094bea4f4185cde31a` | 329, ZIP OK |
| P3.30 | `/home/user/deliverables/P3.30_ALPHA_GATE_FULL_PROJECT_BACKUP_c5181ad.zip` | `b24b3fe9de30f5d57005f651e9e38bf9767ddc1cfa9717d3ce60712a5a728bd3` | 350, ZIP OK |
| P3.31 | `/home/user/deliverables/P3.31_LIVE_DATA_DATA_TRUST_FULL_PROJECT_BACKUP_6046347.zip` | `ec509eacdd2361a137f31bc03aca829a469f7f5529746d5e4b5c16510900a090` | 389, ZIP OK |
| P3.32 | `/home/user/deliverables/P3.32_ALPHA_DEPLOYMENT_READINESS_BACKUP_2524042.zip` | `a8f20a9b030d9b05534c80e9a50032f69999956139104070bfc5c19bdf888a5a` | 412, ZIP OK |
| P3.33 | `/home/user/deliverables/P3.33_ALPHA_GATE_FULL_PROJECT_1aea2a5.zip` | `28d26b53bc452f42488e996ed9718482f4b2805c360265c93d5172d5ff12a09b` | 421, ZIP OK |
| P3.34 | `/home/user/deliverables/P3.34_ALPHA_TARGET_VALIDATION_FULL_PROJECT_0c320c4.zip` | `a224db2d504d6ed0cd8f989cec17fc6a128d08ebc7b13b50d2d046baac784b91` | 440, ZIP OK |
| P3.35 | `/home/user/deliverables/P3.35_ALPHA_LAUNCH_FULL_PROJECT_7f30600.zip` | `b96a45f97f5eda5171c8906ad098a71f8dc0205a01267cf021a996b7d3f34692` | 449, ZIP OK |
| P3.36 | `/home/user/deliverables/P3.36_ALPHA_FINAL_FULL_PROJECT_76b35c1.zip` | `0f524b7da990edc684b403f6cff709879a19a8e032fe45c3b90c52f4621a8dea` | 458, ZIP OK |
| P3.37 | `/home/user/deliverables/P3.37_ALPHA_GATE_CLOSURE_FULL_PROJECT_11d376a.zip` | `08b042d42540154fc4973c4643e633195086b7b1e13dc1bce76936b69fcba527` | 467, ZIP OK |
| P3.38 | `/home/user/deliverables/P3.38_PRODUCT_AI_ARCHITECTURE_FULL_PROJECT_ca5bcb9.zip` | `93af57a48044eb61e3fa9ddecfc40b352365a85d3f1b6770d49defb6d2d15d98` | 486, ZIP OK |

### Git bundle artifacts present

Non-ZIP bundle/support files also exist, including:

```text
/home/user/deliverables/P3.23_LOCAL_COMMITS.bundle
/home/user/deliverables/shekar-saham-p3.23-r1.bundle
```

These are not ZIP files; SHA values were computed in inspection output. They are historical Git recovery artifacts.

---

## 14. EXTERNAL LINKS

Links observed in repository inspection include:

### Repository

```text
https://github.com/aresmaeily/shekar-saham
https://github.com/aresmaeily/shekar-saham.git
```

### Local runtime references

```text
http://127.0.0.1:8000
http://localhost:8000
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/status
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/symbol/فملی
ws://127.0.0.1:8000/ws/live
```

### TSETMC / market provider endpoints found in source/docs

```text
https://cdn.tsetmc.com
https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch
https://cdn.tsetmc.com/api/Trade/GetTrade/{ins_code}
https://cdn.tsetmc.com/api/Trade/GetTradeHistory/{ins_code}/0
https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0
```

### BRSAPI references

```text
https://Api.BrsApi.ir/Tsetmc
```

### Notification APIs

```text
https://api.telegram.org/bot{token}/sendMessage
https://tapi.bale.ai/bot{token}/sendMessage
```

### Forex/global scaffold API references found in code/docs

```text
https://query1.finance.yahoo.com/v8/finance/chart/{...}
https://api.binance.com
https://data-api.binance.vision
https://api.kucoin.com/api/v1/market/candles
https://www.okx.com/api/v5/market/candles
```

These are scaffolds/secondary references; Forex/global production is not currently validated.

### Frontend/chart references

```text
https://s.tradingview.com
https://www.tradingview.com/chart/?symbol=
https://tablokhani.com
```

No fake link is introduced here; entries are from repository grep results.

---

## 15. GITHUB STATUS

```text
Remote URL: https://github.com/aresmaeily/shekar-saham.git
Local HEAD: 4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Ahead/behind: 21 / 0
Authentication status: missing in current environment
```

Authentication status-only inspection:

```text
GITHUB_TOKEN: MISSING
GH_TOKEN: MISSING
GIT_ASKPASS: MISSING
SSH_AUTH_SOCK: MISSING
gh: MISSING
ssh: /usr/bin/ssh
credential.helper: MISSING
```

Last known push attempt result from P3.44/P3.45 history:

```text
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

Current blocker:

```text
GitHub synchronization is blocked by missing authentication.
```

Rules:

- Do not expose credentials.
- Do not modify Git history.
- Do not force push.
- No sync claim until remote SHA equals local SHA via `git ls-remote origin refs/heads/main`.

---

## 16. CURRENT BLOCKERS

### P0

| ID | Blocker | Status | Impact | Required Resolution |
|---|---|---|---|---|
| P0-GH-AUTH | GitHub authentication unavailable | BLOCKED | Remote is 21 commits behind; clone from GitHub is stale | Configure secure auth and push normally |
| P0-TARGET | Windows target not accessible | DEFERRED — TARGET SYSTEM REQUIRED | Cannot validate actual target install/runtime | Run target validation on Windows when available |

### P1

| ID | Blocker | Status | Impact | Required Resolution |
|---|---|---|---|---|
| P1-BRSAPI | `BRSAPI_KEY` missing | BLOCKED — CREDENTIAL REQUIRED | Cannot validate BRSAPI live data | Configure key securely on target |
| P1-ENV | Target environment not configured | NOT ESTABLISHED | Private/production startup cannot be validated | Create secure `.env` on target |
| P1-LIVE | TSETMC live data not verified | NOT VERIFIED | Cannot claim live market data | Validate from target network |

### P2

| ID | Blocker | Status | Impact | Required Resolution |
|---|---|---|---|---|
| P2-BROWSER | Browser/E2E target validation not run | DEFERRED | UI issues may remain | Run browser E2E after backend target startup |
| P2-ELECTRON | Electron target runtime not validated | DEFERRED | Desktop shell readiness unknown | Install npm deps and run on target after approval |
| P2-DOCKER | Docker unavailable in current Linux env | NOT AVAILABLE | Docker path not validated here | Validate Docker on target if used |

### P3

| ID | Blocker | Status | Impact | Required Resolution |
|---|---|---|---|---|
| P3-TECH-SLUG | Real repo URL/technical keys include historical slug | INTENTIONAL / COMPAT | Cosmetic/compatibility | Do not rename without migration plan |

---

## 17. DEFERRED WORK

```text
GitHub sync = BLOCKED BY AUTHENTICATION
Windows installation = NOT STARTED
Target validation = DEFERRED — TARGET SYSTEM REQUIRED
Electron installation = NOT STARTED
Electron runtime/package validation = DEFERRED
Browser E2E = DEFERRED
Live TSETMC verification = NOT VERIFIED
Live BRSAPI verification = BLOCKED — MISSING KEY
24/7 scheduler = NOT STARTED
Cloud deployment = NOT EXECUTED
P3.45 target validation completion = BLOCKED BY TARGET ACCESS
Future phases = NOT STARTED
```

---

## 18. DO NOT DO LIST

```text
DO NOT force push
DO NOT reset --hard
DO NOT rebase
DO NOT rewrite history
DO NOT redesign architecture
DO NOT create parallel engines
DO NOT create duplicate services
DO NOT fabricate live data
DO NOT treat mock as live
DO NOT treat fallback as live
DO NOT treat synthetic as live
DO NOT fabricate profitability
DO NOT fabricate forward test
DO NOT expose secrets
DO NOT commit .env or credentials
DO NOT modify production configuration without approval
DO NOT install target software without approved phase
DO NOT run database migration without approval
DO NOT start target installation until owner explicitly approves
DO NOT claim GitHub sync unless remote SHA equals local SHA
```

---

## 19. NEXT PHASE ROADMAP

| Phase | Goal | Prerequisites | Current Status | Blockers | Safe Entry Condition |
|---|---|---|---|---|---|
| P3.46 | Continuity handoff + optional GitHub sync | Current repo clean; handoff file review; auth if syncing | In progress through this file | GitHub auth missing | Handoff reviewed; if auth exists, normal push only |
| P3.47 | GitHub synchronization closure | Secure GitHub auth | Not started | Authentication unavailable | `git ls-remote` reachable and credentials configured |
| P3.48 | Target Windows prerequisite validation | Windows target access | Not started | Target inaccessible | Owner provides target/system access and approves validation |
| P3.49 | Controlled target installation | Explicit owner INSTALL approval, GitHub/archive source, env prepared | Not started | Installation lock | Owner says INSTALL / شروع نصب |
| P3.50 | Post-install runtime validation | Installed backend/frontend/Electron on target | Not started | Installation not done | Backend running on target |
| Future | Live provider validation | Target network + TSETMC access and/or BRSAPI_KEY | Not started | Live provider not verified | Secure env + target network |

---

## 20. RECOVERY / ROLLBACK

### Safe baseline

```text
Commit: 4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce
Message: P3.44: Pre-Installation Repository Hardening and RADAR BOURSE Integrity
```

### Main backup

```text
/home/user/deliverables/P3.44_RADAR_BOURSE_FULL_PROJECT_4e6cf72.zip
SHA-256: 3a8618e53cefbe4ae180ddda700a40497d81c0e83a9f6fe456be045bca6aa026
File count: 674
Status: ZIP OK
```

### DB backup strategy

- Store backup mechanism: `Store.backup(keep=7)`.
- Location: `/home/user/repo/data/backups/shekar-<timestamp>.db`.
- Uses WAL checkpoint before copy.
- Before target installation or migration, backup DB first.

### Git rollback strategy

Preferred:

```text
Do not rewrite history.
Use new revert commits if a committed change must be undone.
Use verified ZIP archive for full recovery if repository is damaged.
```

Forbidden unless explicitly approved:

```text
git reset --hard
git rebase
git push --force
history rewrite
```

### Target installation rollback

If future installation fails:

1. Stop backend/Electron processes.
2. Preserve logs.
3. Restore previous archive or known-good Git commit.
4. Restore DB from backup if DB changed.
5. Re-run `/api/health` and `/api/status`.
6. Do not claim recovery until verified.

---

## 21. HANDOFF CHECKLIST

For any new developer/agent:

```text
[ ] Read this file fully
[ ] Verify current HEAD
[ ] Verify git status
[ ] Verify branch
[ ] Verify remote
[ ] Verify ahead/behind
[ ] Read README.md
[ ] Read docs/STATUS.md
[ ] Read docs/CHANGELOG.md
[ ] Read docs/active/INDEX.md
[ ] Read active P3.44 report
[ ] Read architecture docs
[ ] Verify test baseline before changes
[ ] Verify P3.44 artifact if needed
[ ] Verify P3.45 status
[ ] Verify blockers
[ ] Do not repeat completed phases
[ ] Do not redesign architecture
[ ] Do not assume live data
[ ] Do not treat mock/fallback/synthetic as live
[ ] Do not install unless owner explicitly approves
[ ] Follow change control
[ ] Update this file after the next significant phase
```

---

## 22. SOURCE OF TRUTH POLICY

This file is a continuity and operational handoff document.

It must be updated after every significant phase.

It must never contain secrets.

It must never claim unverified functionality.

Git history and verified repository state remain the authoritative source for implementation state.

If this document conflicts with Git/source code:

```text
Git/source code wins for implementation facts.
```

If this document conflicts with a newer verified phase report:

```text
The newest verified phase report wins.
```

If something cannot be verified:

```text
Mark it NOT VERIFIED, BLOCKED, or DEFERRED as appropriate.
```

---

## PART A VALIDATION NOTES

After creating/updating this file, run:

```bash
git diff --check
```

Also verify:

- no secret values are included,
- commit SHA values are correct,
- remote/local divergence is current,
- P3.39 through P3.45 statuses are accurate,
- external links are from repository evidence or official runtime paths.

---

## PART B GITHUB SYNCHRONIZATION CHECKLIST

Run from `/home/user/repo`:

```bash
git status --short --branch
git rev-parse HEAD
git fetch origin
git ls-remote origin refs/heads/main
git rev-list --left-right --count HEAD...origin/main
```

Only if authentication is configured and remote is not ahead:

```bash
git push origin main
```

Then mandatory verification:

```bash
git ls-remote origin refs/heads/main
git rev-parse HEAD
```

Success condition:

```text
remote SHA == local HEAD SHA
```

If not equal:

```text
GITHUB SYNC = NOT COMPLETE
```


---

## FINAL DELIVERY ADDENDUM

This addendum records final handoff delivery files created after the P3.45 inspection and before any further development.

### Delivered handoff files

```text
docs/active/P3.45_RADAR_BOURSE_TARGET_VALIDATION_AND_INSTALLATION_READINESS_FINAL_REPORT.md
docs/active/PROJECT_CONTINUITY_HANDOFF.md
docs/active/PROJECT_ARTIFACT_MANIFEST.md
docs/active/PROJECT_LINK_MANIFEST.md
docs/active/HANDOFF_README.md
```

### Final baseline remains

```text
Branch: main
Local HEAD: 4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Local vs Remote: 21 ahead / 0 behind
GitHub Push: BLOCKED — authentication unavailable
Installation: NOT STARTED
Target validation: DEFERRED
```

### Chat history limitation

Full previous chat transcript is not stored in this repository. This continuity file uses verifiable evidence from Git history, repository files, phase reports, validation reports, and artifacts. If a future agent needs exact conversational wording not represented in repository/docs, mark it `SOURCE NOT AVAILABLE` rather than inventing it.
