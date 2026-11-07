# MASTER-RADAR WAVE-AD — 12-JOURNEY BROWSER-RUNTIME EVIDENCE + DEPLOYMENT READINESS — 2026-11-07

Directive source: MASTER CONTINUOUS CLOSURE DIRECTIVE §4. Exact SHA of the code under test:
`b1d1c3c0dc08c038b90b7570ca2f6a668bbaaaad` (same tree as the WAVE-AC audit; tracked clean).

## §1 What this wave added (honest delta vs the WAVE-T baseline)

WAVE-T recorded 12/12 backend journey tests + **7 journeys at browser DOM level**. This wave did
NOT rerun backend journeys to inflate counts (the fleet E2E remains the regression baseline) and
extended the **browser-level** evidence to the full set: **12/12 journeys exercised in a real
headless browser against the real FastAPI app serving the real frontend** (uvicorn 127.0.0.1,
real HTTP, real tab clicks, real form inputs, real network).

Evidence inventory (17 screenshots 1440×900 + 16 DOM snapshots + per-journey error captures,
all at `/home/z/my-project/wavead_scratch/`, recorded in-repo in this document):

| Journey | Browser-level actions actually performed | Key honest-surface assertions observed in the DOM | Console errors |
|---|---|---|---|
| J01 overview + market map + screener | shell load; نقشه بازار tab (size/color comboboxes live); فیلترنویسی tab with pre-filled DSL + result table | treemap controls render; screener table columns (ورود/نماد/صنعت/%/قدرت/حجم×/P/E/طلایی/بنیادی/تگ‌ها) | 0 |
| J02 Persian search → watchlist → symbol detail | دیدهبان tab; typed «فملی» into searchWatch; 7 matched rows rendered in Persian; deep-link `/symbol/famli` page (standalone symbol.html) with chart tabs + honest TradingView-availability note | watch rows Persian digits (exit score ۸۴۰٫۲۵); symbol page heading FAMLI; internal chart labeled primary | 0 |
| J03 Chart Pro → candles → indicators → derived RENKO | chartpro tab; typed فملی + change event; real `/api/v10/chartpro/فملی` 200s; canvas 1058×412 rendered; clicked RSI + رنکو | active buttons 1m/رنکو/MA20/MA50/RSI; symbol header «فملی ۷٬۹۶۵ +0.75٪» Persian digits; grid sync toggles visible | 0 |
| J04 Strategy Lab validate + UIDL-1 FULL lifecycle | slValidate with `ENTRY close > sma(close, 5)` → **ok:true RSL-1.0.0 digest bee4532a…**; UIDL add-segment; invalid source (`PLOT upper = basis * 1.02`) → typed 422 error with line/col (`TYPE_UNKNOWN_INPUT: reference to undeclared INPUT 'basis'`); corrected source → **✓ معتبر «waveac_band» پلات‌ها basis/upper/lower ورودی‌ها {len:5}**; install → **۱ اندیکاتور کاربر · v1.0.0 · غیرفعال · checksum fb9085a99a4a…**; export endpoint exercised (429 under saturated identity — honest rate-limit surface recorded); delete → ۰ اندیکاتور | honest rate-limit toast «✗ Rate limited»; disabled-state install (governance default); UIDL-1 language constraints rendered verbatim | 0 |
| J05 Backtest Center + exports | btRun → 100 trade rows (فملی ۷٬۷۵۲→۷٬۵۶۶ −۳٫۳۹٪ ۲۴-day hold, Persian digits); bcRun (product center) → result_digest a2ef610139c7e564; JSON export 200 + CSV export 200 (`/api/v10/strategylab/backtest/export` ×2) | trade table + digest; byte-level export re-send of the same body (reproducibility by design) | 0 |
| J06 Forward Center paper replay + walk-forward honesty | fcRun → `ledger_len 108 · ledger_chain_ok true · mode PAPER_REPLAY_OVER_SYNTHETIC_WINDOW` + Persian not_live_note «…مشاهده forward زنده نیاز به اتصال runtime دارد و عمداً قطع مانده است (R-6)» + full trust_envelope rendered; walk-forward UI control searched → **NOT PRESENT** (honest parity finding: API+38 tests, no dedicated UI panel) | chain_ok=true; synthetic mode label verbatim; trust envelope from server only | 0 |
| J07 Data Quality Center | dataquality tab → panel disclosure «همه داده‌های این مرکز از کلاس SYNTHETIC است (فیکسچر seed شده)… برچسب کلاس اعتماد فقط از پاسخ سرور خوانده می‌شود»; market chips MOCK — EXCLUDED_US_EQUITY · 2 نماد (خارج از یونیورس پیش‌فرض), FOREX · 13 نماد, IRAN_IFB · 2 نماد | SYNTHETIC/EXCLUDED labels ×9 in DOM; server-only trust label | 0 |
| J08 Product Loops + OA-5 register | loops tab → بارگذاری فهرست → **L1_MARKET_INTELLIGENCE … L5_PREDICTION_FEEDBACK** manifest rendered; فهرست پیش‌بینی‌ها → register `[{prediction_id P-1, predicted_probability 0.9, observed 1.0}]`; Brier/ECE control present; 10 loop action buttons | 5/5 loops; INTEGRATION-VERIFIED status label; owner-gate column rendered | 0 |
| J09 AI-2 Studio honest disabled gate | posture reload → FULL envelope (ai2_enabled false, generation_allowed false, SYNTHETIC_OR_PAPER, deterministic-rule-based-fallback, candidates_in_memory 0); filled question+symbol; generate → POST `/api/v10/ai2/generate` 200 → **refusal rendered verbatim: «اجرا نشد — گیت بسته — gated_not_executed» + «AI-2 is disabled (AI2_ENABLED=0); nothing was executed» + error_code ai2_disabled + run_id genrun-d71acd69ccc34750**; runs reload → **«append_only=true · total=0»** — the refusal added NOTHING to the ledger | closed-gate UX exactly as designed; zero ledger mutation by refusal | 0 |
| J10 Alert inbox | alerts tab → history empty state «هنوز هشداری ثبت نشده»; ops inbox D-AI-30 «فقط Synthetic/Paper · تحویل درون‌محصولی · بدون ارسال خارجی» + record «همه برچسب‌دار: SYNTHETIC / PAPER — NOT LIVE» | empty state honest; mandatory SYNTHETIC/PAPER label column | 0 |
| J11 Workspace + grid sync channel + popup intent | localStorage `radar.workspace.v1` (364B: symbol فملی, timeframe, indicators, pane_layout, drawing_tools, alerts, window_layout); grid setLayout(2) → main+sub pane («پنل فرعی: نمای خطی close»); **BroadcastChannel probe on `radar.grid.sync.v1` captured the real runtime message `{"type":"pane_cross","pane":0,"time":1794064056,"value":7500}` published by `_broadcastCross` AND `_applyRemoteCrossMsg` applied the remote side** — both directions of the WAVE-S2 sync verified at runtime; popup button ⧉ present | workspace payload keys verbatim; sync channel real traffic captured; 0 errors | 0 |
| J12 Command palette + deep-link | paletteBtn → 51 registry items; typed «فوروارد» → filtered to exactly «رفتن به ⏩ مرکز فوروارد تست»; click → tab-forwardcenter active; `radar.palette.recent.v1` = `["tab:forwardcenter"]`; `/symbol/famli` deep-link page covered in J02 | explicit-selection-only navigation; recent persistence | 0 |

Additional §4-required behaviors verified in the same session:

- **Reload/state**: browser reload after palette navigation → active panel restored
  (`tab-forwardcenter`), title intact, 0 errors; 1788 API requests logged 200 across the session.
- **Empty states**: watchlist empty-search, alerts history, UIDL list before install — all render
  honest Persian empty-state copy (no blank panels).
- **Error surfaces**: UIDL typed 422 (line/col precision), rate-limit 429 toasts — rendered
  verbatim, no silent failures.
- **Recovery**: after the 150/min identity window cleared, the same UIDL validate flow returned
  ✓ معتبر — rate limiting is a recoverable, honestly-signaled condition.
- **Dead-control sweep**: every visible tab button (31) resolved to an active panel; the only
  not-found control class was the walk-forward UI trigger (recorded as an honest API-level
  capability, J06) — no dead buttons observed.
- **Service worker**: `/static/sw.js` serves 200, `CACHE_NAME radar-bourse-static-v3-0-16`
  (matches the counter-pinned version byte-exactly); API responses network-only by design; the
  browser context in this run reported no active registration (fresh profile; the SW install path
  is covered by the WAVE-T2 evidence and the static gates) — recorded AS-IS, not inflated.
- **Asset freshness**: index 200, manifest 200, sw 200; SW header comment carries the v3-0-16
  cross-window sync note.

## §2 Deployment model verification (website vs the exact Docker/FastAPI deployment)

The product's required deployment model is the **single FastAPI monolith serving the static
frontend** (exactly what was exercised above) with the Docker artifact as the packaged form:

1. `Dockerfile`: python:3.13-slim pinned by multi-arch manifest digest (registry read-back
   2026-11-02); non-root `appuser`; `HEALTHCHECK` against `/api/health` on `$PORT`; entrypoint
   honors `HOST/PORT` env; `DATA_SOURCE`, `PRIVATE_MODE` posture envs declared.
2. `docker-compose.yml`: fail-closed security posture (`PRIVATE_MODE=1` without a real
   `PRIVATE_PASSWORD`/`API_KEY` → startup aborts by `validate_security_configuration`); persistent
   `./data` volume; no secret defaults.
3. The exact-SHA CI `build-docker` job (SUCCESS at `b1d1c3c`, job 128419844457) builds this
   artifact in the authorized environment — the deployment artifact is CI-proven, not assumed.
4. The local uvicorn boot used for §1 is the same `app.main:create_app()` surface the container
   runs (`entrypoint.sh` → uvicorn), so the browser evidence above applies to the Docker model's
   runtime behavior modulo the container boundary (which CI exercises).

## §3 Deployment runbook (Docker/FastAPI — owner-executable)

**Prerequisites**: Docker + compose; a host with 2 GB free RAM; no external credentials required
for the synthetic default posture.

1. **Configure** (create `.env` next to `docker-compose.yml`):
   - `PORT=8000` (or any host port; container listens on the same).
   - `PRIVATE_MODE=1` + a strong `PRIVATE_PASSWORD` (required in private mode; startup fails
     closed without it) OR `PRIVATE_MODE=0` for an open dashboard on a trusted LAN.
   - `API_KEY=<random>` if API-key auth on sensitive routes is wanted.
   - `FERNET_KEY=<fernet key>` — REQUIRED for stable operation (without it the runtime encrypts
     with an ephemeral key and warns CRITICAL: stored Telegram/Bale tokens cannot be decrypted
     after restart).
   - `DATA_SOURCE=auto` (public TSE/OTC + forex legs, fetch-then-label) or `mock` to force the
     synthetic board.
   - `TRUST_PROXY=1` ONLY behind a reverse proxy; `COOKIE_SECURE=1` when serving over TLS.
2. **Build & run**: `docker compose up -d --build` → wait for `healthy`
   (`docker inspect --format '{{.State.Health.Status}}' radar-bourse`).
3. **Verify**: `curl -f http://127.0.0.1:8000/api/health` → `{"ok":true,...}`; open
   `http://127.0.0.1:8000/` and confirm the dashboard shell + SYNTHETIC trust badge.
4. **Backups**: data volume `./data` holds the SQLite DBs + snapshots; stop the container (or use
   SQLite WAL-safe copy) and archive `./data`; restore = stop, replace `./data`, start.
   `docs/active/BACKUP_RESTORE_RUNBOOK.md` remains the canonical procedure.
5. **TLS/reverse proxy**: terminate TLS at nginx/Caddy, proxy to `127.0.0.1:8000`, set
   `TRUST_PROXY=1` + `COOKIE_SECURE=1`; keep the rate limiter effective by forwarding
   `X-Forwarded-For` only from trusted proxies (the limiter ignores spoofed XFF unless
   `TRUST_PROXY=1`).
6. **Rollback**: the image is tagged by build; `docker compose down` → rebuild at the previous
   git SHA → `up -d`. Data volume is not touched by image rollback.
7. **Health/ops**: `/api/health` (liveness+trust posture); container `HEALTHCHECK` every 30s;
   logs via `docker compose logs -f`.
8. **Vercel**: remains the optional owner-connected pipeline; NOT the required deployment model;
   do not disconnect without owner authorization (OA-6).

**What this runbook does NOT claim**: a public deployment exists (it does not — no host is
authorized/provisioned; §4 of the directive records this as owner-gated). Everything above is
repository-side readiness verified at the artifact and code level + CI build-docker SUCCESS.

## §4 Honest status lines (directive §14 Persian-report separation, stated here in English)

- Website implementation status: IMPLEMENTED/TESTED (31 tabs, 12 journeys backend + browser).
- Website browser-runtime status: **RUNTIME-VERIFIED (this wave, 12/12 browser journeys, 0
  console errors)** — extends WAVE-T's 7 to the full set.
- Public deployment status: **NOT DEPLOYED — owner-gated** (no authorized host; Vercel optional
  pipeline remains disconnected/failed-state by design; Docker artifact CI-proven).
- Desktop implementation status: IMPLEMENTED (Electron shell + payload, CI-proven steps).
- Installer artifact status: BUILT in CI (114.4 MB, identity recorded); binary hash verification
  + payload unzip = owner-verifiable (authenticated download), not claimed here.
- Actual Windows installation status: **NOT INSTALLED (owner R-1/R-2) — correctly so.**
