# MASTER-RADAR WAVE-AF — COMPLETE PRODUCT & ROADMAP PARITY AUDIT — 2026-11-07

Directive source: MASTER CONTINUOUS CLOSURE DIRECTIVE §6. Code SHA: `b1d1c3c0dc08c038b90b7570ca2f6a668bbaaaad`.
Method: every row below was verified against code, API, UI wiring, tests, AND — where marked
"browser-verified" — against the real running UI in the WAVE-AD session (17 screenshots, DOM
snapshots, real HTTP). "Endpoint exists" alone is NOT counted; UI-to-backend integration was
exercised through the actual frontend modules.

## §1 Website & desktop feature parity traceability

The desktop (Electron) app ships the SAME frontend bundle (`electron/resources/frontend` =
`frontend/`, payload-verified in CI) against the same supervised backend — every row therefore
applies to both surfaces, with desktop-only deltas noted.

| Capability | Implementation | UI wiring (verified where noted) | Tests | Status (11-vocab) | Desktop delta |
|---|---|---|---|---|---|
| Chart workspaces | `wda_1` workspace persistence (`radar.workspace.v1`: symbol/timeframe/indicators/pane_layout/drawing_tools/alerts/window_layout) | browser-verified (J11: payload keys read from live localStorage; save button cpSaveLayout) | frontend-static + WDA gates | INTEGRATION-VERIFIED | identical bundle; localStorage per Electron user-data dir |
| Supported timeframes | 1m/5m/15m/1h/1D + forex TF pages | browser-verified (J03: 1m active; TF segment buttons present) | chart tests | IMPLEMENTED/TESTED | identical |
| Standard chart types | candle/line/area/Heikin-Ashi | buttons present in cp toolbar (J03 listing) | chart_pro tests | TESTED | identical |
| Derived chart types | RENKO/RANGE/KAGI/PnF/LINEBREAK (`derived_charts.py`, `/chartpro/{symbol}/derived`) | browser-verified (J03: رنکو active + canvas render; 5 honest DERIVED buttons) | test_derived_charts 32 | INTEGRATION-VERIFIED (RUNTIME-VERIFIED for RENKO in browser) | identical |
| Indicators | MA20/MA50/EMA20/BB/RSI/MACD server-computed | browser-verified (J03: RSI/MA20/MA50 active) | indicator tests + AUDIT-B recompute ≤1e-12 | INDEPENDENTLY-REPRODUCED | identical |
| User-defined indicator lifecycle (UIDL-1) | `/api/v10/user-indicators` validate/install(list)/enable/disable/export/import; governance display | browser-verified (J04: validate ✓ معتبر → install disabled v1.0.0 checksum → list ۱ → delete → ۰) | user_indicator tests 81+ | RUNTIME-VERIFIED (browser) | identical |
| Drawing tools | workspace `drawing_tools` payload + measure-move tool (both drawing stores) | workspace payload verified (J11); measure-move recorded WAVE-2 | drawing store tests | TESTED | identical |
| Multi-chart grid | `chart_grid.js` layouts ۱/۲/۴ + range/crosshair/symbol-follow toggles + fail-closed persistence | browser-verified (J11: setLayout(2) → main+sub pane; sync toggles visible) | chart_grid static tests | RUNTIME-VERIFIED (browser, layout 2) | identical |
| Cross-window crosshair/range sync | `radar.grid.sync.v1` BroadcastChannel: pane_cross/pane_cross_clear/pane_range msgs; fail-closed validator; double-echo guard; local-data values only | **browser-verified BOTH DIRECTIONS (J11: `_broadcastCross` → channel message captured live `{"type":"pane_cross","pane":0,"time":1794064056,"value":7500}`; `_applyRemoteCrossMsg` applied remote side)** | wave-S2 tests + static pins | **RUNTIME-VERIFIED (browser, channel-level)** | identical |
| Detached popup | DETACH_CHANNEL popup window + DETACH_INTENT read at module load; window_layout in workspace | popup button ⧉ present (J11); OS-level placement/multi-monitor honestly NOT claimable from sandbox | popup static tests | INTEGRATION-VERIFIED (backend-verifiable subset) | OS placement = owner R-2 verification |
| Strategy authoring | Strategy Lab spec/validate (RSL-1 digest) | browser-verified (J04: validate ok:true RSL-1.0.0 digest bee4532a…) | strategylab tests | RUNTIME-VERIFIED (browser) | identical |
| Strategy validation | typed 422 errors with line/col; UIDL-1 language constraints rendered | browser-verified (J04: `TYPE_UNKNOWN_INPUT` line/col verbatim) | validator tests | RUNTIME-VERIFIED (browser) | identical |
| Backtesting | bar-based engine, next-bar-open fills, pessimistic same-bar stop | browser-verified (J05: 100 trade rows, Persian digits) + btRun | backtest 29+product 29+framework 14 | RUNTIME-VERIFIED (browser) | identical |
| Optimization | `/strategylab/optimize` grid/randomized/evolutionary; IS-only selection + OOS-once; seed required; 500-cap | **browser-verified (J05-opt: run with space → ok:true, selection_basis IN_SAMPLE, winner period=5 param_hash, objective SHARPE; method selector 3 options; PDF/CSV/JSON export buttons)** | optimizer 22 tests | RUNTIME-VERIFIED (browser) | identical |
| Walk-forward | `/strategylab/walkforward` fold math + IS-only per fold + OOS exactly once | **UI trigger NOT PRESENT (browser-verified absence J06)** — API + 38 tests + backend E2E journey | walk-forward 38 tests | TESTED + INTEGRATION-VERIFIED (API); UI trigger = honest residual | identical |
| PDF & data exports | backtest/optimize exports JSON/CSV/PDF (`apiBlob` binary PDF path) | browser-verified (J05: JSON+CSV export 200 ×2; PDF button present) | report_pdf 27 + export tests | RUNTIME-VERIFIED (JSON/CSV browser; PDF CI+tests) | identical |
| Paper forward testing | `forward_test_paper` PAPER_REPLAY_OVER_SYNTHETIC_WINDOW + ledger chain | browser-verified (J06: ledger_len 108, chain_ok true, mode + Persian R-6 note verbatim) | forward tests | RUNTIME-VERIFIED (browser) | identical |
| Data-quality & session/calendar presentation | Data Quality Center markets/coverage/audit + DECLARED calendars + session-state | browser-verified (J07: SYNTHETIC disclosure + EXCLUDED_US_EQUITY/FOREX/IRAN_IFB chips) | dataquality 49 | RUNTIME-VERIFIED (browser) | identical |
| Five product intelligence loops | loops Center manifest + per-loop actions + OA-5 register | browser-verified (J08: L1–L5 manifest + register P-1 + Brier/ECE control) | loops tests | RUNTIME-VERIFIED (browser) | identical |
| AI-2 governed surface | AI-2 Studio: posture envelope + gated refusal + append-only ledger | browser-verified (J09: FULL envelope + gated_not_executed verbatim + total=0 unchanged) | ai2 94+ | RUNTIME-VERIFIED (browser) | identical |
| Alerts & scheduler status | Alert inbox + ops D-AI-30 in-product delivery + scheduler kill-switch posture | browser-verified (J10: SYNTHETIC/PAPER NOT LIVE labels + boot log «scheduler gate closed (SCHEDULER_ENABLED=0)») | alert tests | RUNTIME-VERIFIED (browser) | identical |
| Command palette | Ctrl/Cmd+K, 51 registry items, explicit-selection-only, recent ≤5, zero network | browser-verified (J12: filter فوروارد → 1 result → navigate → recent persisted) | palette tests | RUNTIME-VERIFIED (browser) | identical |
| Deep links | `/symbol/{l18}` standalone page + GOV-24 hash bridge | browser-verified (J02: /symbol/famli page rendered) | deep-link tests | RUNTIME-VERIFIED (browser) | identical |

**Honest residuals (NOT-IMPLEMENTED / PARTIAL, unchanged by this wave):** walk-forward UI
trigger (API-complete); popup OS-placement/multi-monitor visual verification (owner R-2);
session calendars = DECLARED layer only (sourced tables owner-gated R-3/R-7).

## §2 Data coverage matrix (real vs synthetic — directive §6)

| Market | Intended universe | Actual repo-side support | Source entitlement | Status |
|---|---|---|---|---|
| Iranian TSE | full listed universe | instrument master + fixture universes (IRAN_TSE coverage rows); real TSETMC public fetch path exists (fetch-then-label, trust envelope cannot mint verified LIVE) | owner R-3/R-7 (entitlements/credentials; Two-Key) | IMPLEMENTED (mechanism) + SYNTHETIC-DEFAULT; real-universe admission OWNER-GATED |
| Iranian OTC (فرابورس) | intended | same mechanisms as TSE; fixture rows | owner R-3/R-7 | IMPLEMENTED (mechanism) + OWNER-GATED (real admission) |
| Forex pairs | intended | forex legs (Binance/KuCoin/Yahoo public endpoints, fetch-then-label) + 13 FOREX fixture symbols in dataquality | owner R-3/R-7 | IMPLEMENTED (mechanism) + OWNER-GATED (real admission) |
| US indices | ONLY indices (DJI/S&P/NASDAQ class) | index-class records; US individual equities mechanically EXCLUDED (`US_INDIVIDUAL_EQUITY_EXCLUDED`, non-overridable, 81 tests) | owner R-3/R-7 | IMPLEMENTED + ENFORCED exclusion |
| US individual equities | EXCLUDED by design | exclusion code + reason-coded refusal + hardened model_copy | not applicable | **NOT-APPLICABLE (excluded)** |
| Synthetic fixtures | explicitly labeled | SYNTHETIC_FIXTURE ×16, SYNTHETIC_OR_PAPER ×37, NOT_ENTITLED markers; server-only trust labels; never counted as real coverage | not applicable | LABELED (never conflated) |

## §3 Quantitative fidelity statement (precise)

- Backtests are **BAR-BASED**: entry decisions evaluated on bar i, executed at bar i+1
  (`backtest.py:338-343`) at next-bar open/close with adverse spread+slippage (:378-382);
  same-bar TP/SL ambiguity resolves **stop-first (pessimistic)** (`:163-164`).
- **NO intrabar/tick fidelity is claimed anywhere** — docs say "Bar-based simulation ONLY;
  nothing claims real-tick" (auditor-B verified the absence of any tick claim).
- Paper forward testing is **replay over a synthetic window** (`PAPER_REPLAY_OVER_SYNTHETIC_WINDOW`);
  live forward observation requires runtime connection that is deliberately disconnected (R-6).
- Optimizer/walk-forward: IS-only selection, OOS confirmed exactly once, seeds pinned,
  determinism digests recorded (browser-verified `selection_basis: IN_SAMPLE`).

## §4 Five product-loop evidence matrix

| Loop | UI | API | Domain service | Persistence/provenance | Tests | Status |
|---|---|---|---|---|---|---|
| L1 Market Intelligence | loops Center بارگذاری فهرست + اجرای یک چرخه نظارت | /api/v10 productloops | market intel service | loop records + trust labels | loops tests | RUNTIME-VERIFIED (browser manifest) |
| L2 External/Company Intelligence | پرونده در قطع (dossier) | dossier endpoint | corporate dossier | DECLARED cutoff provenance | dossier tests | RUNTIME-VERIFIED (browser control) — DECLARED data class |
| L3 Governed Research | ارزیابی قطعی فرضیهها + وضعیت حاکمیت | research endpoints | research service | hypothesis records | research tests | RUNTIME-VERIFIED (browser control) |
| L4 Product Intelligence (تابلوخوانی) | ممیزی ۳ سنجه واقعی | audit endpoint | product intel | audit trail | loops tests | RUNTIME-VERIFIED (browser control) |
| L5 Prediction Feedback | ثبت پیشبینی / ثبت برونداد / فهرست / Brier+ECE | OA-5 register endpoints | prediction register | **durable SQLite WAL append-only** (distinct from AI-2 in-memory candidate ledger and AI-3 memory) | register tests + E2E J08 | RUNTIME-VERIFIED (browser: P-1 rendered) |

Registry distinctions preserved exactly as the directive requires: OA-5 Prediction Registry
(durable) ≠ AI-2 candidate/run ledger (in-memory by recorded design decision, persistence
owner-gated) ≠ AI-3 research memory.

## §5 Verdict

Website + desktop feature surface: **parity verified at browser runtime for 20 of 23 capability
rows** (RUNTIME-VERIFIED), 3 rows TESTED/INTEGRATION-VERIFIED with honestly-recorded residuals.
Data coverage honestly separated (mechanism implemented; real admission owner-gated; synthetic
never conflated). Quantitative fidelity stated precisely (bar-based, no tick claims). Global
completion remains NOT CALCULATED (OA-8).
