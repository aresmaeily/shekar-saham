# MASTER-RADAR CAPABILITY MATRIX (supersedes WDA_CAPABILITY_MATRIX_2026-11-03 additively) — 2026-11-04

> ## ⚠️ CURRENCY ADDENDUM — 2026-11-08 (completion stage; original rows below PRESERVED verbatim)
>
> The table in §1 is the 2026-11-04 snapshot. Rows whose state moved SINCE then are
> superseded here (history kept below; per the documentation-currency rule):
>
> | # (old row) | Old state (2026-11-04) | Current state (2026-11-08) | Evidence |
> |---|---|---|---|
> | 7 AI proposal generation | NOT-VERIFIED → OWNER-GATED seam (disconnected) | **UNCHANGED — OWNER-GATED seam (disconnected)**; governed surface shipped + browser-verified refusal (`gated_not_executed`, ledger total unchanged); `AI2_ENABLED=0` | config.py:118; E2E 2026-11-08 S21a |
> | 15 LLM narration | OWNER-GATED seam (disconnected) | **UNCHANGED — OWNER-GATED**; provider-activation decision packet P-1..P-10 delivered; nothing activated | AIMA_PROVIDER_ACTIVATION_DECISION_PACKET.md |
> | 19 Data Quality Center UI | MISSING | **EXISTS** — DQ Center tab shipped; markets/coverage/audit + DECLARED calendars + session-state panels browser-RUNTIME-VERIFIED (WAVE-E) and re-verified 2026-11-08 (screenshot) | WAVE-E record; S09_dataquality.png |
> | 20 Multi-chart layouts / detachable monitors | PARTIAL | **EXISTS (grid + cross-window sync)** — layouts ۱/۲/۴ + range/crosshair/symbol-follow sync browser-RUNTIME-VERIFIED both directions at channel level (WAVE-S2); popup-class detach INTEGRATION-VERIFIED (same-origin popup + two-way sync; OS placement/multi-monitor visual check = owner R-2) | WAVE-S record; WAVE-AD J11; parity audit §1 |
> | 21 Renko/range/Kagi/LineBreak/PnF | MISSING | **EXISTS** — derived chart types shipped (`derived_charts.py`, `/chartpro/{symbol}/derived`); RENKO browser-RUNTIME-VERIFIED; 32 tests | parity audit §1 row «Derived chart types»; test_derived_charts |
> | 23 Windows installer/upgrade/rollback/signing | NOT-VERIFIED | **ARTIFACT BUILT (repository-side)** — unsigned NSIS artifact built in CI from exact SHAs, provenance recorded (latest: id 13607633922 @ run 42456810887, SHA 2e6d0fb4); actual install/upgrade/rollback = still **OWNER-GATED (R-1/R-2)** = NOT-VERIFIED until owner device evidence; signing = owner decision | manifest COMPLETION-STAGE-2026-11-08; install guide 2026-11-08 |
> | 11 Walk-forward (product-level) | EXISTS (engine) | **EXISTS + UI TRIGGER CLOSED** — the WAVE-AF parity-audit row «UI trigger NOT PRESENT» described the pre-cbfa028 tree; WAVE-AB2 commit `cbfa028` wired the full walk-forward section into the Forward Center (static gates `test_master_waveab_walkforward_ui.py`), browser journey + exports verified (WAVE-AI WP-B; re-verified 2026-11-08: POST /walkforward 3 folds + digest + csv/pdf exports 200) | cbfa028; test_master_waveab_walkforward_ui.py; E2E S15 2026-11-08 |
> | 24 Version chain | EXISTS (v3-0-6) | **EXISTS** — sw chain advanced through v3-0-19 with recorded counter-pin bumps | STATUS chain |
>
> ### Three-way classification of the old open items (directive §2.4)
>
> 1. **تکمیل‌شده با شواهد معتبر (completed with valid evidence):** rows 5, 6, 8, 9, 10, 11, 12, 14, 16, 17, 18, 19, 20 (grid/sync/popup subset), 21, 22 (in-product inbox), 24 — each carries code+tests and, where marked, browser-RUNTIME-VERIFIED evidence.
> 2. **ناقص و قابل رفع توسط مهندسی (partial, engineering-fixable):** P2 liquidity pinning (honestly NOT ADDRESSED — ROADMAP_TRACEABILITY_DELTA_2026-11-03 line 12); per-fundamental-line PIT module (event/membership-layer PIT DONE; the per-line module remains PARTIAL); popup detach beyond popup scope (multi-monitor OS placement cannot be verified from a headless sandbox — test-bundle prepared, needs a Windows session).
> 3. **نیازمند تصمیم/دسترسی/اقدام مالک (owner-gated):** 13 live forward observation (R-6 deliberate); real symbol catalog + provider entitlement (R-3/R-7 Two-Key); live source admission (R-3 KEEP-DENIED); 7/15 AI-2 + LLM provider activation (D-A2-1..7 / P-1..P-10 + OA-3); 23 target-machine install/upgrade/rollback + Windows signing (R-1/R-2 + signing decision); interactive Electron testing on the owner's device; scheduler operational enablement (OA-4); Vercel housekeeping (OA-6); branch-protection ruleset (Administration scope).
>
> Nothing PARTIAL/MISSING/NOT-VERIFIED is re-labelled COMPLETE without new evidence. Global
> completion remains NOT CALCULATED (OA-8).

Vocabulary: `EXISTS` (implemented in-repo with tests) / `PARTIAL` / `MISSING` / `NOT-VERIFIED` (requires target machine / authorized data / owner act). NO parity or superiority claims against Faraz Chart / TradingView / MetaTrader are made anywhere in this file (directive §A, §N).

## 1. WDA capability matrix — updated rows

| # | Capability | WDA-1..6 prior (2026-11-03) | 2026-11-04 state | Delta evidence |
|---|---|---|---|---|
| 1 | Electron shell + security gates | EXISTS | EXISTS (byte-unchanged) | shell gates green |
| 2 | Workspace persistence + crash recovery | EXISTS | EXISTS | WDA-1 tests |
| 3 | Pro chart (candles/volume/drawings/alerts) | EXISTS | EXISTS + chart types candles/line/area/HA | `cpTypeSeg`; HA audit-verified |
| 4 | Built-in indicator set on chart | EXISTS (6 overlays/panes) | EXISTS + 14-entry audited catalog w/ compute API | `/api/v10/indicators` |
| 5 | Indicator manager (install/enable/version/import) | MISSING | EXISTS (metadata state machine, checksum, no-code-exec) | PKG-F tests |
| 6 | Restricted strategy DSL | MISSING | EXISTS (RSL-1.0.0 parser/types/validator/runtime/sandbox) | 182 DSL tests |
| 7 | AI proposal generation (NL→strategy) | MISSING | NOT-VERIFIED → OWNER-GATED seam (disconnected) | AI2 gates |
| 8 | Strategy approval workflow | MISSING | EXISTS (DRAFT→APPROVED→PROMOTED, in-memory) | API tests |
| 9 | Backtest (single/multi/portfolio, costs, full report) | PARTIAL (P3.27 primitives) | EXISTS (product engine + reproducibility digest) | 51 tests + audit B |
| 10 | Optimizer (grid/randomized/evolutionary + resume) | MISSING | EXISTS (engine-level) | 22 tests |
| 11 | Walk-forward (product-level) | PARTIAL | EXISTS (anchored/rolling windows + WF efficiency) | engine tests |
| 12 | Paper forward-test runtime | PARTIAL (P3.27 forward-test primitive) | EXISTS (ledger + maturity + comparison) | 62 tests |
| 13 | Live forward observation | MISSING | MISSING (deliberate; owner-gated wiring) | scope statement |
| 14 | AI symbol analyst (evidence-grounded) | MISSING | EXISTS (deterministic; provenance per claim) | 65 tests + audit D |
| 15 | LLM narration for analyst | MISSING | OWNER-GATED seam (disconnected) | — |
| 16 | Instrument master (multi-market taxonomy) | MISSING | EXISTS (Iran/Forex/US-index + exclusion rule) | 57 tests |
| 17 | Timeframe legality/labeling | PARTIAL | EXISTS (aggregation guard + labels) | 45 tests |
| 18 | Universe data-quality engine | PARTIAL (data_quality.py legacy) | EXISTS (coverage reports) | 28 tests |
| 19 | Data Quality Center UI | MISSING | MISSING (engine exists; tab next increment) | requirements matrix MR-G-01 |
| 20 | Multi-chart layouts / detachable monitors | MISSING | PARTIAL (single chart + osc pane; workspace persisted) | WDA matrix |
| 21 | Renko/range/Kagi/LineBreak/PnF | MISSING | MISSING (honest: construction semantics not implemented) | §B3 staged plan |
| 22 | Alerts (price/local) | EXISTS | EXISTS (+ DSL alert conditions parseable; runtime loop NOT wired) | R-9/R-6 |
| 23 | Windows installer/upgrade/rollback/signing | NOT-VERIFIED | NOT-VERIFIED (unchanged; owner target machine) | WDA-6 rows |
| 24 | Version chain 3.0.0 + SW cache discipline | EXISTS | EXISTS (bump v3-0-6 recorded) | version tests |

## 2. Market universe & provider-entitlement matrix (directive M3)

| Market segment | Coverage in repo TODAY | Source class | Entitlement | Trust class ceiling | Owner gate |
|---|---|---|---|---|---|
| Iranian TSE/IFB symbols | fixture identities (10 well-known l18s) + mock board generator; NO complete symbol catalog | SYNTHETIC_FIXTURE / mock | NOT_ENTITLED | SYNTHETIC | R-3/R-7: authorized source admission required |
| Iranian historical corporate actions | closed taxonomy engine + PIT publish-time (no admitted dataset) | — | — | — | data admission |
| Forex majors/minors/exotics | 16 fixture pairs with pip/contract/session metadata; provider adapters DISABLED | SYNTHETIC_FIXTURE | NOT_ENTITLED | SYNTHETIC | R-3 |
| US equity indices (cash vs proxy) | 6 cash indices + 1 ETF proxy fixture; type distinction enforced | SYNTHETIC_FIXTURE | NOT_ENTITLED | SYNTHETIC | R-3 + source entitlement |
| US individual equities | EXCLUDED by non-overridable invariant (2 marker records prove exclusion) | — | — | — | exclusion is product policy per directive |
| Live provider (any market) | interfaces only, disabled/unconfigured; no credentials; no scraping | — | — | — | R-3 KEEP-DENIED + dated amendment proposal (owner) |
| Historical data source (any market) | contract + quality gates ready (`DataPolicy`, `universe_data_quality`) | — | — | — | evaluated SEPARATELY from R-3 live denial per §A2 — owner decision required |

## 3. Timeframe & market-calendar specification (directive M4, summary — full semantics in `timeframe_spec.py` docstrings)

- Standard codes: `1m/5m/15m/30m/1h` (INTRADAY), `1d` (DAILY), `1w` (WEEKLY), `1M` (MONTHLY, calendar-aware aggregation REFUSES without a declared table — nominal seconds documented as nominal only).
- Custom intervals: 60..2,628,000 s, kind CUSTOM.
- Legality: target must be an integer multiple ≥ source; lower-from-higher FORBIDDEN (raises `lower_timeframe_from_higher_timeframe_forbidden`).
- Labels: NATIVE / RESAMPLED / SYNTHETIC / DELAYED / PROVIDER — every produced series carries a declared label; the analyst API demonstrates the RESAMPLED path honestly.
- Calendars: the repo's fail-closed holiday philosophy is preserved — holiday status is representable ONLY against a declared, versioned table (`market_calendar.py`); TSE holiday tables remain NOT DECLARED (honest `*_UNDECLARED` calendar ids in fixtures). Session/weekday semantics remain `market_session.py`'s concern.
- Gaps: `session_aware_gaps` reports mechanical intervals; callers pass calendar tables when available.

## 4. Milestones (honest)

- M1 (this wave): product engine layer + DSL + analyst + catalog + UX entry points — DONE, TESTED, independently audited on synthetic data.
- M2: real-data admission path — BLOCKED on owner (R-3/R-7 + entitlement evidence).
- M3: Data Quality Center UI + optimizer UI + multi-chart grid — next repository-side increment (no owner dependency).
- M4: Windows installer/signing/target-machine evidence — OWNER-GATED (R-1/R-2).
- M5: live forward observation + AI proposal/narration — OWNER-GATED (AI2 enablement + runtime wiring decisions).
