# MASTER-RADAR: BACKTEST ENGINE + EXECUTION MODEL + FORWARD TEST — ARCHITECTURE & EVIDENCE — 2026-11-04

## Part 1 — Backtest engine architecture & execution model (directive §D; M8)

`backend/app/engines/backtest_product.py` (`BT-PRODUCT-1.0.0`) on the shared `app/engines/execution_model.py` (`EXECUTION_MODEL_VERSION 1.0.0`).

**Execution model (§D2), one arithmetic point for BOTH engines:**
- Fill pipeline: latency → policy price (`NEXT_BAR_OPEN` = bar AFTER the signal bar — structural no-look-ahead; `SAME_BAR_CLOSE` = explicit labeled approximation) → symmetric half-spread + adverse slippage → liquidity volume cap → lot flooring → min-lot / min-notional / short-constraint / margin checks. Refusals are RECORDED REASONS, never silent drops.
- Cost decomposition per fill: commission + spread cost + slippage cost; equity impact comes from fill PRICES (no double count — test-pinned); `fees_total` echoes the decomposition (documented second-order cross-term ≈0.02 per ~232k notional, audit note).
- Every assumption is a caller-supplied, echoed config field: `commission_pct, spread_pct, slippage_pct, latency_bars, lot_size, min_lot, min_notional, leverage, allow_short, volume_cap_pct, currency_multiplier, fill_policy, intrabar_tp_sl`.
- Bar-based simulation ONLY; nothing claims real-tick. Intrabar TP/SL (optional) uses PESSIMISTIC stop-first ordering when both levels are touched in one bar (test-pinned).

**Engine structure (§D1):** multi-symbol portfolio simulation in deterministic sorted-symbol order; shared equity; max-open-positions gate; `RiskModel` sizing (FIXED_PCT_EQUITY / RISK_BASED with stop distance); trailing stops on running peak; END_OF_DATA honest close; same-bar re-entry refusal by default; benchmark buy-and-hold with the same cost model; optional per-bar regime labels → per-regime stats.

**Research validity (§D3):** fail-closed `validate_bars` (OHLC consistency, strict ts ordering); `DataPolicy` refusals (`insufficient_history`, `stale_data` with injected as_of, gap refusal, `all_symbols_refused` abort) recorded per symbol; declared `adjustment_semantics` (engine NEVER silently adjusts); PIT/survivorship provided by the existing `universe_membership` + `survivorship_guard` + `corporate_actions` domain modules (prior-wave, reused); the engine's own no-look-ahead contribution is structural (fill bar strictly after signal bar) plus the adapter contract, regression-tested with appended future bars.

**Report (§D5):** total/annualized return, CAGR (None + note when span < 1y), maxDD + duration, Sharpe/Sortino/Calmar with documented `sqrt(252), rf=0` assumption (annualization_assumption field), Profit Factor, expectancy, win rate, avg win/loss, trade count, exposure %, avg holding, turnover, fees, equity+underwater curves, UTC monthly/yearly returns, trade distribution histogram, long/short decomposition, regime segments, benchmark comparison, data-quality/refusals echo, `limitations[]` auto-honesty notes, `result_digest()` reproducibility digest. Persisted via the API response (run_id, engine/execution-model versions, config echo, digests).

**Optimizer (§D4):** `backtest_optimizer.py` — grid (deterministic lexicographic), randomized (seeded uniform), bounded evolutionary (seeded, tournament/gaussian mutation/elite); dependency-rule skips counted; REQUIRED seed; max-eval + injected-clock time budgets; cancellation via token; journal RESUME proven to reach the identical final evaluation set; deterministic ranking (−objective, param_hash); Bonferroni note recording n_trials; **winner selected on IN-SAMPLE only** (`selection_basis: "IN_SAMPLE"`), out-of-sample evaluated ONCE afterwards as confirmation — a hostile OOS function cannot change ranking (test-pinned). Walk-forward integration via per-window OOS objective; product-level `run_walk_forward_product` reports per-window IS/OOS stats + WF efficiency.

## Part 2 — Backtest & optimizer test evidence (M9)

- `test_backtest_product.py` (29): determinism/digest identity + config-sensitivity; no-look-ahead invariants (fill ts strictly after signal; prefix decisions stable under appended data); refusal paths; hand-derived cost accounting (prices via shared model, pnl arithmetic written IN the test); Sharpe/Sortino vs independent in-test formulas; pessimistic same-bar rule; END_OF_DATA; monthly rows; long/short decomposition; portfolio; benchmark; walk-forward.
- `test_backtest_optimizer.py` (22): enumeration order; constraint skips; budget flags; cancel+resume equality; seeded reproducibility + seed-sensitivity; evolutionary determinism; selection-basis invariant + OOS-not-used-in-ranking; Bonferroni note; hash/digest stability; injected-clock budget.
- `test_execution_model.py` (19): shared arithmetic pinned independently of both engines.
- Independent audit (AUDIT-MR1 §B): full 60-bar scenario recomputed from scratch — every quantity matched to ≤3.6e-15 (entry/exit indices and prices, qty, gross/net pnl, fees, win rate, total return, final equity); DSL sma/crossover hand truth tables matched.

## Part 3 — Forward-test runtime & paper evidence (directive §E; M10)

`backend/app/engines/forward_test_paper.py` (`FT-PAPER-1.0.0`), 62 tests:
- **Immutable ledger:** sha256-chained entries (`LedgerEntry`: seq/kind/ts_utc(injected)/payload/prev_hash/entry_hash); `verify_chain()` + module-level `verify_entry_chain` for doctored-copy tamper tests; NO delete/clear/truncate method exists (asserted).
- **State machine:** RUNNING/PAUSED/STOPPED with ledgered transitions; paused processing = 0 bars, no spam; STOPPED terminal.
- **Consistency with backtest:** same `ExecutionModelConfig` → same fill arithmetic (tested by invoking `simulate_fill` independently); stop-before-take pessimistic ordering; refusal taxonomy shared.
- **Signal quality measurement:** every intent recorded (filled or refused with reason); DELAY_OBSERVATION with expected-vs-realized prices (documented as model-vs-execution divergence, NOT market impact); DATA_GAP detection vs 3× median interval.
- **Maturity (§E):** `min_bars_after_signal`; matured outcomes only in aggregate stats; immature counted separately and EXCLUDED; stale outcomes excluded; **no Brier/ECE/drift implemented** (they would require mature outcome distributions — deliberately out of scope until real observation exists).
- **Comparison:** `compare_with_backtest` honest table builder (missing keys skipped with note).
- **No egress:** no requests/httpx/websocket/urllib/socket imports (source-scan test).
- **Runtime surface today:** `/api/v10/strategylab/paper-replay` = paper SIMULATION over a synthetic window (labeled `PAPER_REPLAY_OVER_SYNTHETIC_WINDOW`, Persian not-live note). LIVE forward observation (consuming an authorized stream over wall-clock time, pause/resume across sessions) is deliberately NOT wired — it requires owner decisions on data admission (R-3/R-7) and any scheduler (R-6 dormancy). Audit D verified the endpoint's labels and chain integrity end-to-end.
