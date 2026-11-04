# MASTER-RADAR CAPABILITY MATRIX (supersedes WDA_CAPABILITY_MATRIX_2026-11-03 additively) — 2026-11-04

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
