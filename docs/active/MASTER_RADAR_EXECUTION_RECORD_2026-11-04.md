# MASTER-RADAR EXECUTION RECORD — 2026-11-04

Directive: **MASTER DIRECTIVE — RADAR WINDOWS PROFESSIONAL TRADING, AI INDICATOR/STRATEGY STUDIO, MULTI-MARKET DATA, BACKTEST & FORWARD-TEST PLATFORM** (waves 1–9, §A–§N).
Repository: `aresmaeily/shekar-saham`. Baseline verified before start: remote `main` == local HEAD == `3bd46f419b31fd4e24af2fc116ddda8b3a132120` (the directive's known baseline; publication chain `c7d2dc1` implementation → `2023895` records → `3bd46f4` tip confirmed from `git log`). All prior accepted work preserved; forward-only commits; no amend/rebase/reset/force.

## 1. Baseline audit and architecture map (Wave 1 — verified, not assumed)

Existing product surface mapped before implementation (all reused, none duplicated):

| Layer | Existing assets (reused) | Evidence |
|---|---|---|
| Data | `seeded_candles.candles_for` (deterministic SYNTHETIC generator, bar-N-forever stability), `providers.py`/`forex_provider.py` (provider seams, disabled state), `market_service` trust envelope (canonical `data_trust_context()`/`trust_level()`) | chart_pro router + analytics router consume them today |
| Domain | `market_calendar` (declared-table holidays, fail-closed), `market_session`, `symbol_identity`, `corporate_actions` (closed 6-kind taxonomy, publish-time PIT), `universe_membership` (half-open intervals, as-of), `survivorship_guard`, `strategy.py` (FilterStrategy contract), `evidence.py` (`SCHEMA_VERSION`, `ensure_utc`) | committed at `c7d2dc1` |
| Engines | `filter_dsl` (safe expression evaluator precedent), `indicators.py` (MACD/Bollinger/ATR/ADX/CCI/OBV/Williams/Stochastic/VWAP), `backtest.py` (P3.27 simulation primitives: same-bar TP/SL policy, walk-forward, forward-test), `metrics`, `holdout`, `regime_slices`, `data_quality`, `risk_manager`, `trade_detail` | battery-covered |
| API | `/api/v10/chartpro` (seeded OHLCV + indicators + universe), `/api/v10/analytics/{search,screener,market-map,flow,dossier}` (trust envelope on every row) | `main.py` registration block |
| Frontend | `chart_pro.js` (1043-line lightweight-charts pro chart: drawings, price alerts, watchlist, analysis save/export), `workspace.js` (WDA-1 schema-versioned persistence), `replay.js`, `volume_profile.js`, `custom_indicator.js`, trust badges | Electron `main.js` shell gates |
| Gates | `AI2_ENABLED=0`, `verified=False`, `SYNTHETIC_OR_PAPER`, kill switch ENGAGED, R-1..R-11 | unchanged this wave |

Directive deltas identified (what did NOT exist): canonical multi-market instrument master; explicit US-index/US-equity taxonomy with the exclusion rule; timeframe legality/labeling contract; restricted strategy DSL; product-grade multi-symbol backtest with full §D2/§D5 realism+report; §D4 optimizer; §E paper forward-test runtime with immutable ledger; §F evidence-grounded symbol analyst; §B4 indicator catalog/manager with independent references; product UX entry points. All deltas were implemented this wave (below); nothing else was re-opened.

## 2. Implementation inventory (Waves 2–7, all additive; exact new-file list)

**Shared contract (written first, consumed by two engines):**
- `backend/app/engines/execution_model.py` — `ExecutionModelConfig` (commission/spread/slippage/latency/lot/min-lot/min-notional/leverage/short-policy/volume-cap/currency-multiplier/fill-policy/intrabar flag), fail-closed `validate_bars`, structural no-look-ahead `apply_latency` (NEXT_BAR_OPEN always fills on a bar strictly AFTER the signal bar), `simulate_fill` (latency → policy price → spread+slippage → volume cap → lot floor → min-lot/min-notional/short/margin refusals — refusals are reasons, never silent), `cost_breakdown`. Version `1.0.0`.

**Wave 2 — instrument universe & timeframe foundation (PKG-A):**
- `backend/app/domain/instrument_master.py` — `TrustClass` (`REAL_VERIFIED/REAL_UNVERIFIED/DELAYED/SYNTHETIC/PAPER/STALE/MISSING`), `Market` (IRAN_TSE/IRAN_IFB/FOREX/US_INDEX + non-selectable marker `EXCLUDED_US_EQUITY`), instrument types distinguishing CASH_INDEX from ETF/FUTURE/CFD proxies (`proxy_kind`, `is_index_benchmark`), statuses, entitlements, half-open membership intervals, canonical IDs (`IR_TSE:FOLAD`, `FX:EURUSD`, `USIDX:SPX`), `register_instrument` pseudo/unsourced-symbol rejection, `UniverseSpec` with **non-overridable** US-individual-equity exclusion (constructor AND hardened `model_copy` both fail-closed), `build_default_universe` with recorded exclusion reason codes.
- `backend/app/domain/timeframe_spec.py` — 8 standard timeframes + bounded custom intervals; `aggregation_legal` (lower-TF-from-higher-TF FORBIDDEN); `aggregate_bars` (deterministic OHLCV bucketing; MONTHLY refuses without a declared calendar table); `ResampleLabel`/`BarLabeling` (NATIVE/RESAMPLED/SYNTHETIC/DELAYED/PROVIDER); `session_aware_gaps`.
- `backend/app/data/fixture_universes.py` — deterministic fixture universes: 10+ Iran symbols (incl. a DELISTED membership case), 16 forex pairs (correct pip precision/contract size/sessions), 6 US cash indices + SPY ETF proxy + 2 US-equity records that exist ONLY to prove exclusion; sha256-seeded `synthetic_bars`.
- `backend/app/engines/universe_data_quality.py` — per-symbol mechanical audit (duplicates, out-of-order, invalid OHLCV, missing intervals, stale w/ injected now) + per-market `CoverageReport` (UNKNOWN fail-closed defaults).

**Wave 4 — Strategy DSL (PKG-B), package `app/engines/strategy_dsl/` (9 files, RSL-1.0.0):**
- Hand-written lexer/parser/AST (positions on every error), static type checker, semantic validator with resource budgets (≤512 AST nodes, depth ≤64, source ≤4096 chars, MTF refs ≤3, symbol refs ≤2), `ref(x, n<0)` = look-ahead error, constant division-by-zero guard, deterministic interpreter (sma/ema/rsi-Wilder/stdev/highest/lowest/atr/crossover/crossunder/ref/abs/min/max; documented warm-up semantics; x/0→0.0), `PreparedProgram` with ctx digest, `run_over_series` decision loop. NO eval/exec/compile/__import__ anywhere (test-enforced source scan). Sandbox: 39 tests incl. 26 hostile sources (dunder chains, `__import__`, `sym("../../etc/passwd")` traversal, deep-nesting, 1e9 literals, unicode keywords…).

**Wave 5 — product backtest engine + optimizer (PKG-C):**
- `backend/app/engines/backtest_product.py` (ENGINE_VERSION `BT-PRODUCT-1.0.0`) — multi-symbol/portfolio simulation over the shared execution model; `RiskModel` (fixed-pct-equity / risk-based sizing), `PortfolioLimits` (max open positions, same-bar re-entry refusal default), `DataPolicy` (min-bars, staleness w/ injected as_of, gap refusal, **declared** UNADJUSTED/ADJUSTED semantics — never silently adjusts), intrabar TP/SL with **pessimistic stop-first ordering** (documented bar-based approximation, never "real-tick"), trailing stops, END_OF_DATA honest close, per-fill cost decomposition, benchmark buy-and-hold comparison, regime segmentation (optional labels), full §D5 report (CAGR with <1y honesty-None, maxDD + duration, Sharpe/Sortino/Calmar with documented `sqrt(252), rf=0` assumption, PF, expectancy, win rate, avg win/loss, exposure, avg holding, turnover, fees, equity+underwater curves, monthly/yearly UTC returns, trade distribution, long/short decomposition, limitations list incl. `data_trust_label` echo), `result_digest()` reproducibility digest (config echo + bar (ts,close) digests + rounded metrics).
- `backend/app/engines/backtest_optimizer.py` — grid (deterministic lexicographic) / randomized (seeded) / bounded evolutionary (seeded) search over an explicit `ParameterSpace` with dependency-rule skips (counted, never silent), `OptimizationBudget` (max evals, injected-clock time budget, REQUIRED seed), cancellation + journal **resume** (interrupted run resumes to the identical final evaluation set), deterministic ranking by (−objective, param_hash), Bonferroni multiple-testing note recording n_trials, and `select_then_confirm` — **winner selected on IN-SAMPLE only**, OOS evaluated once as confirmation (`selection_basis: "IN_SAMPLE"` pinned by test).

**Wave 6 — paper forward-test runtime (PKG-D):**
- `backend/app/engines/forward_test_paper.py` (ENGINE_VERSION `FT-PAPER-1.0.0`) — hash-chained append-only `PaperLedger` (sha256(prev) chain, verify + tamper evidence, **no delete/clear/truncate API**), RUNNING/PAUSED/STOPPED state machine, fills via the SAME `execution_model` as the backtest (stop-before-take pessimistic ordering), SIGNAL/FILL/POSITION_UPDATE/DATA_GAP/DELAY_OBSERVATION/OUTCOME_MATURED event kinds, expected-vs-realized fill deltas (model-vs-execution divergence, honestly labeled), maturity rules (min bars after signal; immature outcomes counted separately and **excluded from all aggregate statistics**; no Brier/ECE/drift implemented at all), `summary().digest()`, `compare_with_backtest` table builder. Zero egress primitives (test-enforced).

**Wave 7 — AI market analyst (PKG-E):**
- `backend/app/engines/symbol_analyst.py` (ENGINE_VERSION `ANALYST-1.0.0`) — deterministic, rules-only, **no LLM call** (owner-gated seam documented, disconnected): per-timeframe trend/structure/volatility/volume/momentum/bollinger-position computations; five-kind claim taxonomy (`OBSERVED_FACT/CALCULATED_METRIC/MODEL_INTERPRETATION/SCENARIO/RECOMMENDATION`) where factual kinds carry confidence=None and interpretive kinds are bounded 0.35–0.65; full provenance per claim (source class, as-of, freshness bars, timeframe, evidence ref, trust class, conflicts); bull/base/bear scenarios keyed to computed swing levels with invalidation conditions (no invented levels); risk factors; missing-data & uncertainty section (every unavailable input becomes a claim); bilingual EN/FA texts; `forbidden_terms_scan` (guarantee/target-price/قطعی/تضمین…) enforced fail-closed inside `analyze_symbol` itself.

**Wave 3/B4 — indicator catalog + manager (PKG-F):**
- `backend/app/engines/indicator_reference.py` — independent textbook implementations (sma/ema/rsi/macd/bollinger/atr/stochastic/obv/vwap + new_high_rate + advance_decline_line), deliberately NOT calling `app.engines.indicators`.
- `backend/app/engines/indicator_catalog.py` — 14-entry versioned catalog (all 6 categories: trend/momentum/volatility/volume/breadth/market-structure), each with math definition, typed param ranges, warm-up, missing-data behavior, repaint declaration, look-ahead=False declaration, permissions whitelist, engine+reference dotted refs (`dual_implementation` honesty flag where engine==reference), catalog validator (resolves and asserts every ref callable).
- `backend/app/engines/indicator_manager.py` — metadata-only lifecycle (NO code execution): install/enable/disable/remove/version-check/template-compose/export-import manifest; JSON package validation with checksum, reserved `builtin.*` namespace, permission whitelist, recursive forbidden-key scanner (`code/script/exec/eval/lambda/__*`), size/entry budgets; `manifest_digest()` determinism.

**Integration (this session, direct):**
- `backend/app/services/strategy_lab_service.py` — DSL→adapter glue (backtest `StrategyAdapter` + paper `PaperAdapter`), seeded-bar conversion (lightweight-charts keys → engine keys), §C3 in-memory approval state machine `DRAFT → APPROVED (explicit user approve) → PROMOTED (paper forward only)`; documented cross-engine size_pct unit conversion (backtest percent vs paper fraction).
- `backend/app/api/strategy_lab.py` — `/api/v10/strategylab/{validate,spec,backtest,paper-replay,versions,versions/{id}/promote}` (synthetic-only; trust envelope from `market_service`; DRAFT→PROMOTED promotion 409-guarded).
- `backend/app/api/indicator_api.py` — `/api/v10/indicators{,/{id},/{id}/compute}` (catalog + typed param validation + audited-implementation compute with declarations echoed).
- `backend/app/api/analyst_api.py` — `/api/v10/analyst/{symbol}` (daily seeded SYNTHETIC + weekly honestly RESAMPLED from daily; hourly/fundamentals/sector/strategy-signals honest MISSING; trust envelope).
- `backend/app/main.py` — three additive `include_router` registrations (comment-stamped).
- Frontend: new `strategylab` tab + panel (`index.html`), `frontend/js/modules/render/strategy_lab.js` (Strategy Studio + Indicator Manager, bind-on-demand, `core/api.js` boundary only, no fetch/eval/WebSocket, trust labels from server), chart-type selector (candles/line/area/Heikin-Ashi) added to `chart_pro.js` (HA = pure visual re-representation of the SAME bars — formula verified independently), `main.js` import.
- Recorded counter-pin bumps WITH the authorized features (established discipline): tabs 25→26 in `test_wda_analytics_static.py` + `test_frontend_static_script.py`; SW cache `v3-0-5`→`v3-0-6` (+ strategy_lab.js precache) in `test_wda_version_consistency.py` + `test_p3_80_local_closure.py`. Structural invariants (panel matching, no orphans/duplicates/missing imports) unchanged.

## 3. Test evidence (exact)

- Full battery: **2401 passed / 1 skipped = 1794 + 607 exact**, 0 failed, 17.4s. The single skip is the pre-existing env-conditional G2 docs-only-delta guard (`test_g2_acceptance_harness.py`) — unchanged semantics, explained in prior records.
- New test files (17) and exact counts: instrument_master **57** (54 + 3 hardened-copy), timeframe_spec **45**, universe_data_quality **28**, strategy_dsl parser **41** / types **37** / validator **31** / runtime **34** / sandbox **39**, backtest_product **29**, backtest_optimizer **22**, forward_test_paper **62**, symbol_analyst **65**, indicator_catalog **34**, indicator_manager **35**, execution_model **19**, master_radar_api **21**, master_radar_frontend_static **8**. Total **607**.
- `pyflakes app tests` clean for all touched/new files (the 3 pre-existing unused-import notes in old test files are unchanged from baseline).
- `node --check` green on `strategy_lab.js`, `chart_pro.js`, `main.js`, `sw.js`; `scripts/validate_frontend_static.py` → `ok: true`, tabs 26 = panels 26, no orphans/duplicates/missing imports.
- `git diff --check` clean.
- Gates re-verified unchanged: `AI2_ENABLED=0`, `verified=False`, `SYNTHETIC_OR_PAPER`, kill switch ENGAGED, R-1..R-11 untouched, no live data path, no scheduler, no external egress, no runtime caller added to any disconnected edge, INSTALL NOT ISSUED.

## 4. Independent audit (AUDIT-MR1, read-only, same working tree)

Independent 4-domain audit executed BEFORE publication (full record: `MASTER_RADAR_INDEPENDENT_AUDIT_2026-11-04.md`):
- **QA**: battery reproduced 2398/0/1 at audit time (2401 after the 3 audit-closure tests); 6 sampled honesty-critical test claims all VERIFIED as genuine (real future-bar append, hand-derived pnl, independent Sharpe/Sortino, copy-then-tamper, positive-control banned-term scan, sandbox coverage).
- **Quantitative**: full 60-bar scenario recomputed from scratch matched every reported quantity to ≤3.6e-15; DSL sma/crossover matched hand truth tables; frontend HA formula verified correct.
- **Security**: 9 fresh hostile DSL sources all rejected; API robustness probes (100KB source, `fast=1e9`, null bytes) → zero 500s; zero network/exec primitives in new routers/services.
- **Data/provenance**: 12 endpoints all carry the canonical non-live trust envelope (`is_live: true` count = 0 everywhere); analyst claims 100% provenanced with correct confidence policy; US-equity exclusion mechanically enforced (32 considered → 30 included, `USEQ:AAPL`+`USEQ:MSNI` excluded with recorded reason).
- Verdict: **no FAILs**; 3 cosmetic observations, one of which (UniverseSpec `model_copy` validator bypass) was CLOSED IN-WAVE by the hardened copy + 3 regression tests; the other two are documented scale/decomposition notes (win_rate percent-scale; second-order fee-line cross-term ≈0.02 on ~232k notional — pnl itself has no double-count, test-pinned).

## 5. Honest scope statement (what this wave does NOT claim)

- No real/live market data anywhere: every value remains SYNTHETIC/PAPER-labeled; R-3 live-provider denial is intact; provider adapters stay in disabled/unconfigured state; the dated R-3 amendment proposal remains owner-side work.
- No TradingView/MetaTrader parity or superiority claim — the capability matrices use EXISTS/PARTIAL/MISSING/NOT-VERIFIED only.
- AI-proposal generation (NL→spec→code) is NOT implemented as a live path: the seam is owner-gated (AI2_ENABLED=0, verified=False) and disconnected; the delivered §C1 workflow covers user-authored DSL with validation/spec/approval/backtest/replay/report.
- The version registry is in-memory by design (persistence requires an owner decision); no scheduler exists (R-6); no broker/live egress exists; INSTALL remains owner-issued (R-1); target-machine evidence remains owner-executed (R-2).
- Windows packaging artifacts (installer/signing/upgrade) are NOT produced this wave; the Electron shell/security posture is unchanged and re-gated.

## 6. Publication chain (recorded after push)

Recorded in `docs/STATUS.md`, `docs/CHANGELOG.md`, `docs/active/INDEX.md`, Persian report §۳۴, and the CI evidence file `WS1_EXACT_SHA_EVIDENCE_2026-11-02.md` §11 (exact-SHA check-runs on the final published SHA, 3/3 required jobs, job IDs + timestamps; Vercel recorded separately as external).
