# Changelog — Shekar Saham

## 2026-08-09 — P3.36 Target-System Final Validation & Controlled Alpha Launch Gate

- Re-ran all locally executable alpha validation checks: backend tests, pyflakes, JS syntax, alpha environment, alpha runtime, provider mock/BRSAPI fallback, and frontend static validation.
- Added `docs/active/P3.36_TARGET_VALIDATION_REPORT.md` documenting local validation, deferred target-system gates, GitHub blocker, and alpha launch decision.
- No feature development, runtime architecture change, provider rewrite, live trading, Cloudflare deployment, or production launch was performed.
- Alpha remains not launched because the target Windows system, browser E2E, Electron runtime, live provider validation, and GitHub sync are still deferred/blocked.

## 2026-08-09 — P3.35 Alpha Target Validation and Controlled Launch Gate

- Re-ran offline/local alpha validation suite and confirmed `110 passed, 1 warning`.
- Verified alpha environment, runtime, provider mock fallback, BRSAPI missing-key handling, and frontend static checks through prepared validation scripts.
- Added `docs/active/P3.35_ALPHA_TARGET_VALIDATION_REPORT.md` documenting local pass, deferred target-system requirements, GitHub blocker, and alpha launch decision.
- Produced a full project archive for target-system handoff.
- No feature development, Cloudflare deployment, live provider claim, live AI, broker integration, UI redesign, or trading logic change was performed.

## 2026-08-09 — P3.34 Alpha Target Validation Preparation

- Added `docs/active/P3.34_ALPHA_TARGET_VALIDATION_AND_LAUNCH_CHECKLIST.md` as the target-system runbook and alpha launch checklist.
- Consolidated offline-ready checks, deferred target-system validations, GitHub sync requirements, browser E2E checklist, Electron validation, provider validation, data-trust acceptance criteria, rollback and recovery instructions.
- Re-ran available regression suite and validation scripts; no runtime feature code was changed.
- No Alpha launch, Cloudflare deployment, live provider claim, browser E2E pass, Electron runtime pass, or GitHub sync was claimed.

## 2026-08-09 — P3.33 Alpha Gate Audit & Target-System Handoff Preparation

- Audited the local phase chain through P3.32 and clarified the dual P3.31 commits: `10bb770` initial implementation and `6046347` corrective hardening.
- Verified alpha handoff artifacts and documented completed-now versus deferred target-system validation.
- Added `docs/active/P3.33_ALPHA_GATE_AUDIT.md` with Alpha Gate Matrix, target-system handoff checklist, and deferred validation boundaries.
- No runtime code, provider logic, AI, frontend, Electron, Docker, or trading logic was changed.
- No GitHub sync or deployment was claimed.

## 2026-08-09 — P3.32 Alpha Deployment Readiness & Deferred Live Validation

- Added offline/target-system validation scripts for Alpha environment, local API smoke, and provider validation.
- Added `docs/ALPHA_DEPLOYMENT_READINESS.md` with completed-now versus deferred target-system validation matrix.
- Added tests for validation scripts, safe BRSAPI missing-key handling, provider mock fallback, and alpha runtime smoke.
- Updated `.env.example` with `DATA_STALE_AFTER_SEC=300` to align with P3.31 freshness gates.
- No live data claim, Cloudflare deployment, broker integration, live trading, UI redesign, global expansion, or new feature expansion was performed.

## 2026-08-09 — P3.31 Live Data & Data Trust Hardening

- Extended canonical data trust states with `stale` and `unavailable` while preserving legacy `trust_level` compatibility.
- Added freshness metadata to `data_trust`: `checked_at`, `age_sec`, `stale_after_sec`, and `stale`.
- Propagated safe provider failure/fallback metadata through `MarketService.data_trust_context()`.
- Added explicit synthetic labels for current fundamental output: `fundamental_source=synthetic`, `is_synthetic=true`.
- Extended AI and backtest warnings for stale/unavailable data without adding a new LLM or changing trading math.
- Extended the existing frontend trust renderer to represent live/mixed/mock/synthetic/stale/unavailable.
- Added focused regression tests for data trust hardening and no-false-live behavior.

## 2026-08-09 — P3.30 Alpha Completion Gate

- Cleaned repository health by removing the temporary `security.py.backup` verification artifact.
- Finalized minimal security hardening already identified by audit: fail-closed private-mode API key behavior, production security configuration validation, route-level protection for sensitive endpoints, and WebSocket private-mode auth enforcement.
- Added security hardening regression tests for private mode, wrong/valid API key, health public access, and production config validation.
- Added `docs/ALPHA_ENV_CONTRACT.md` to document safe Alpha environment variables without secrets.
- Preserved Iran-market core, Filter DSL, Strategy, Backtest, AI, Chart, Windows/Electron, and Forex scaffold without adding large new features.
- No Cloudflare deployment, live data claim, live LLM provider, UI redesign, or global market expansion was performed.

## 2026-08-07 — P3.28 AI Assistant / Analyst / Optimizer & Alpha Transfer

- Added controlled backend AI service with `AIContextBuilder`, deterministic fallback provider and structured AI result schema.
- Added AI endpoints: `/api/ai/assistant`, `/api/ai/analyze`, `/api/ai/optimize`.
- Added data-trust propagation, confidence, uncertainty, evidence, warnings and safety metadata to AI outputs.
- Added tests for AI assistant, analyst, optimizer, invalid filter handling and API smoke.
- Added `docs/architecture/AI_ASSISTANT_ANALYST_OPTIMIZER.md`.
- Added `docs/ALPHA_SETUP_GUIDE.md` for restoring, validating and running the Alpha candidate on the main computer.
- Prepared P3.28 transfer manifest and full project backup workflow.
- No live LLM provider, AI Copilot rewrite, autonomous trading, broker integration, dashboard, UI redesign or new market was added.

## 2026-08-07 — P3.27 Backtest, Walk-Forward Test & Forward Test

- Added next-bar simulated execution for filter/strategy backtests to reduce look-ahead bias.
- Added execution configuration for capital, position sizing, commission, slippage, take-profit, stop-loss and max-hold bars.
- Added performance metrics: total return, net PnL, trade count, win rate, average win/loss, profit factor, drawdown, Sharpe status and equity curve.
- Added walk-forward out-of-sample window evaluation and simulated forward-test boundary.
- Integrated P3.26 `FilterStrategy` as a consumer of Filter DSL in the backtest engine.
- Expanded existing `/api/backtest/run` additively without creating a new dashboard or rewriting frontend UI.
- Added tests for next-bar execution, commission/slippage, no-trade scenario, multiple trades, walk-forward separation, forward boundary, and data trust preservation.
- Added `docs/architecture/BACKTEST_WALK_FORWARD_FORWARD_TEST.md`.
- No live trading, broker integration, paper trading account, AI, dashboard, UI redesign, or new market was added.

## 2026-08-07 — P3.26 Filter DSL & Strategy Framework

- Stabilized the safe Filter DSL parser/validator/execution boundary.
- Added explicit filter expression contracts: `FilterExpression`, `ExpressionNode`, `parse_filter`, `validate_filter`, and `expression_tree`.
- Added bounded AST validation for expression length, node count and depth.
- Added declarative indicator references: `sma(period)`, `avg_volume(period)`, `rsi(period)`, `high(period)`, and `low(period)`.
- Preserved backward compatibility for existing saved filters and `compile_filter()` behavior.
- Added initial strategy framework contracts in `backend/app/domain/strategy.py` without implementing backtest/forward-test/paper trading.
- Added tests for parser metadata, valid/invalid expressions, injection protection, indicator references, market data aliases, and strategy contracts.
- Added `docs/architecture/FILTER_DSL_STRATEGY_FRAMEWORK.md`.
- No AI Copilot, LLM, dashboard, market, UI redesign, global expansion, broker integration, or backtest rewrite was added.

## 2026-08-07 — P3.25 Iran Market Data & Domain Stabilization

- Added canonical data-trust classification for `live`, `mixed`, `mock`, and `synthetic` sources.
- Preserved backward-compatible `trust_level` values while exposing richer `data_trust` metadata for market-intelligence outputs.
- Added Iran market domain contracts: `DataTrustState`, `MarketDataProvenance`, `IranInstrument`, `MarketSession`, and `OHLCVBar`.
- Updated data-quality scoring so mock/synthetic source snapshots cannot be scored as live trust.
- Added `data_trust` metadata to key service/API outputs without changing existing runtime behavior or removing current fields.
- Added tests for data trust classification, Persian symbol/instrument encoding, OHLCV contract, and mock trust scoring.
- Added `docs/architecture/IRAN_MARKET_DATA_DOMAIN.md`.
- No new market, dashboard, AI feature, filter feature, strategy builder, forward test, UI redesign, or mobile/global expansion was added.

## 2026-08-07 — P3.24 Core Product Consolidation & Iran Market Architecture Lock

- Verified GitHub `main` baseline at `26a2d120b596aa298a40b2ebc6952310658f45b5`.
- Updated active status documentation to mark P3.23/P3.23-R1 as completed on GitHub.
- Added `docs/architecture/IRAN_MARKET_ARCHITECTURE_LOCK.md` to document the current Iran-market-first architecture boundaries.
- Documented the Data Trust terminology: LIVE, MIXED, MOCK, SYNTHETIC.
- Documented AI boundaries: implemented rule-based explainability versus future Copilot/LLM/Research Agent/Multi-role work.
- Documented Decision Support as partial confluence-based support, not a complete multi-role Decision Center.
- Documented frontend/API boundary debt without performing a large refactor.
- No product feature, engine, dashboard, market, UI redesign, or mobile/global expansion was added.

## 2026-08-07 — P3.23-R1 Repository Consolidation Closure

- Consolidated documentation into active, architecture, and archive areas.
- Added `docs/STATUS.md` as the current status source.
- Preserved historical reports under `docs/archive/phase-reports/`.
- Confirmed `frontend-next` does not exist in the repository.
- Audited industry tabs and confirmed only `data-tab="industry"` exists in the current frontend.
- Kept Iran market focus and did not add product features.

## Historical Records

Detailed historical changelogs and inspection reports are preserved in:

- `docs/archive/phase-reports/`
