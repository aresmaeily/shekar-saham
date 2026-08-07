# Changelog — Shekar Saham

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
