# WDA CAPABILITY MATRIX + MILESTONES — 2026-11-03

Directive §4: "Continue WDA — Windows Desktop Analytics … in independently
testable increments." Statuses: IMPLEMENTED (this cycle, with test evidence) /
AUDITED-EXISTS / PARTIAL / MISSING / NOT-VERIFIED. No parity/superiority
claims; every comparison row against فراز چارت / TradingView is bounded by
observed public-interface evidence only (WDA-5).

## WDA-1 — Desktop shell and workspace

| Item | Status | Evidence |
|---|---|---|
| chartpro route + menu item + lifecycle | AUDITED-EXISTS (WS-10) | menu «📈 چارت حرفه‌ای» → `/#/chartpro`; hash router; MutationObserver singleton bind; `window-all-closed`/`activate` (static tests) |
| Renderer security | AUDITED-EXISTS, pinned | `contextIsolation: true`, `nodeIntegration: false`, `enableRemoteModule: false`, sandbox not disabled, no preload, zero IPC surface; navigation guards (`will-navigate`/`will-redirect`/`setWindowOpenHandler`) pre-existing — all pinned in `test_wda_electron_shell_gates.py` (10 tests) |
| App-level error handling | **IMPLEMENTED (this cycle)** | `render-process-gone` (log + rate-limited 5s guarded reload), `child-process-gone`, `uncaughtException`, `unhandledRejection` — additive in `electron/main.js`, pinned statically |
| Persistent chart workspace/layout | **IMPLEMENTED** | `frontend/js/modules/workspace.js` — `{schema:1, saved_at_iso, payload}` envelope, unknown-schema refusal (data preserved), corruption quarantine (`radar.workspace.corrupted`) + reset-to-defaults, field validation with issues list, injectable storage adapter |
| Restart restoration + corrupted-workspace recovery | **IMPLEMENTED** | `chart_pro.js` init restores workspace (symbol/timeframe/indicators + UI sync, non-fatal warn); recovery branch pinned by 14 static contract tests (`test_wda_workspace_persistence.py`) |
| Window lifecycle tests | IMPLEMENTED (static class) | shell gates tests; behavioral Electron tests are TARGET-MACHINE-ONLY (recorded honestly) |

## WDA-2 — Charting core

| Item | Status | Evidence |
|---|---|---|
| OHLCV integrity/candle ordering/gaps/boundaries | **IMPLEMENTED** | `test_seeded_candles_integrity.py` (83 tests): invariants, strict ordering, contiguous index grid (`time = i × tf_sec`), clamp (49→50, 1001→1000; clamped, never refused), boundary timestamps hand-derived, determinism + perturbation |
| Timeframe aggregation semantics | AUDITED-EXISTS | 1m/5m/15m/1h/1D on one absolute arithmetic grid — no market-closed bucket skipping (documented synthetic behavior, pinned) |
| Adjusted/unadjusted price semantics | **IMPLEMENTED** | `PRICE_SEMANTICS = "UNADJUSTED_SYNTHETIC"` constant + docstring in `seeded_candles.py`, pinned by test |
| Independent indicator fixtures | **IMPLEMENTED** | `test_chart_pro_indicator_fixtures.py` (9 tests): hand-computed MA20/EMA20/RSI14/MACD/Bollinger against the exact public functions the router calls; two EMA variants documented (chart_builder first-close seed vs indicators SMA seed); Bollinger population-σ; endpoint==engine consistency + trust envelope never "live" |
| Multi-chart layout + synchronized symbol/time navigation | MISSING (recorded) | not implemented this cycle; single-chart per tab; recorded for a future increment |
| Drawing-tool editing/selection/deletion/persistence | PARTIAL | per-symbol persistence + delete/پاک‌سازی exist (WS-10); editing/selection UX unchanged this cycle |
| Loading/empty/stale/disconnected/provider-error states | PARTIAL | trust badges + fetch-fail handling exist from WS-10; explicit per-state UI surfacing for chartpro recorded as future increment |

## WDA-3 — Iran-market analytics (audit → additive implementation)

Audit verdicts BEFORE this cycle → action:

| Path | Before | Now |
|---|---|---|
| Symbol search | PARTIAL (existing `/api/search` without trust envelope/normalization) | **NEW `/api/v10/analytics/search`** — Persian normalization (Arabic yeh/kaf, ZWNJ, digits), ranking, per-row source_class + trust envelope; existing route untouched |
| Watchlists | EXISTS | unchanged |
| Screener/filters | EXISTS (DSL) + parametric one-click MISSING | **NEW `/api/v10/analytics/screener`** — composes DSL expression, evaluated only by existing `run_user_filter`, Query-validated |
| Market map | PARTIAL (no envelope) | **NEW `/api/v10/analytics/market-map`** — industry aggregates reused verbatim + envelope |
| Sector/industry views | PARTIAL | covered by market-map aggregation; dedicated sector drill recorded future |
| Volume & liquidity | EXISTS (analyze/tablocastic) | unchanged |
| Market flow | PARTIAL (rows unlabeled) | **NEW `/api/v10/analytics/flow`** — big-moves + flow_meta aggregation, labeled; additive panel `analytics_flow.js` wired into existing «تحرکات بزرگان» tab (25 tabs unchanged, validator green) |
| Company/fundamental dossier | EXISTS (deep fundamental + symbol full) + unified MISSING | **NEW `/api/v10/analytics/dossier/{l18}`** — supported sections `available:true`, unsupported sections `{available:false, reason}` (calendar/dividends/corporate_events/shareholders/target_price honest — never fabricated) |

Evidence: `backend/app/api/analytics.py`; tests `test_analytics_api.py` (19) +
`test_wda_analytics_static.py` (6); every response carries
`market_service.data_trust_context()` envelope; SYNTHETIC labeling everywhere;
nothing claims "live".

## WDA-4 — RADAR integration (audit recorded; increments scoped)

| Surface | UI exposure | Drill-down | Feedback capture | E6 posture |
|---|---|---|---|---|
| Market Intelligence (`/api/ai/*`) | NONE (backend-only) | in-payload evidence lists | none | never reaches notifier (read-only cycle) |
| Research | NONE | data_trust provenance | none | offline-deterministic, no egress |
| P6 opportunities | inbox labels only | evidence fields present | none (lifecycle domain-side) | inbox labeled SYNTHETIC/PAPER |
| Confluence | FULL tab wiring | reasons column | none (filter-proposal review is the only human-review surface) | notify gated by `is_verified_live` OR explicit allow; dedupe; honest synthetic-block |
| **Gaps (recorded, not implemented this cycle)** | MI/Research/P6 UI panels; outcome/feedback capture endpoint | — | — | E6 stays disconnected (R-9) — unchanged |

These are UI/contract decisions larger than a safe additive increment; recorded
honestly as the next WDA increments (NOT hidden).

## WDA-5 — Reference benchmark (فراز چارت / TradingView)

- Vocabulary enforced: `EXISTS / PARTIAL / MISSING / NOT-VERIFIED`.
- TabloKhani-class capability matrix delivered with direct repo evidence:
  `TABLOKHANI_CAPABILITY_MATRIX_2026-11-03.md` (24 rows: EXISTS 13 · PARTIAL 8
  · MISSING 1 · NOT-VERIFIED 2; explicit out-of-scope statement for
  parity/superiority claims without vendor public-interface evidence; direct
  capability tests: `test_tablokhani_capability.py`, 12 tests).
- Faraz/TradingView-class desktop charting rows (WS-10 CH-matrix): chartpro
  candlestick+volume/indicators/drawing tools/alerts/watchlist = EXISTS;
  multi-chart synced layouts = MISSING; vendor-behavior-identical claims =
  NOT-VERIFIED (no lawful public-interface evidence gathered — out of scope
  without owner-authorized sourcing). No parity or superiority claim is made.

## WDA-6 — Windows packaging

| Item | Status | Evidence/Note |
|---|---|---|
| Version consistency across Electron/frontend/backend | **IMPLEMENTED (test)** | `test_wda_version_consistency.py` (6 tests) — cross-artifact chain pinned; honest single-source documentation (sw cache token is an independent cache-bust counter, not a derived version) |
| Reproducible installer generation | NOT-VERIFIED (target-machine-only) | no installer build in CI; recorded as owner-machine execution item |
| Upgrade/rollback/uninstall/data-preservation | NOT-VERIFIED | target-machine checklist rows; CI green ≠ install (standing rule) |
| Code-signing readiness | PREPARED, NOT SIGNED | no signing certificate exists; no signed status claimed |
| Target-machine-only tests separate from CI | PRESERVED | all new tests are offline-deterministic CI-safe; Electron behavioral tests recorded as target-machine-only |

## Milestones (honest ledger)

- This cycle (+200 tests = 1794/1): WDA-1 workspace+shell hardening, WDA-2
  determinism battery, WDA-3 five new analytics endpoints + flow panel,
  WDA-5 matrix docs, WDA-6 version-consistency gate, AI-3 CLI trigger.
- NOT claimed: WDA-4 UI panels/feedback capture; multi-chart layouts;
  installer reproducibility; signing; any live/vendor comparison.
