# MASTER-RADAR REQUIREMENTS & ACCEPTANCE MATRIX — 2026-11-04

Directive source: MASTER DIRECTIVE §A–§N (2026-11-04). Vocabulary (per §M): `IMPLEMENTED`, `TESTED`, `INTEGRATION-VERIFIED`, `RUNTIME-VERIFIED`, `OPERATIONALLY-VERIFIED`, `INDEPENDENTLY-REPRODUCED`, `OWNER-GATED`, `PARTIAL`, `NOT-IMPLEMENTED`, `NOT-APPLICABLE`. Test success is NOT equated with operational readiness. Columns: `Req ID | Source | Implementation | Tests | Runtime caller | Data dependency | Owner gate | Status | Evidence | Remaining work`.

## A. Product scope & market universe

| Req ID | Source | Implementation | Tests | Runtime caller | Data dependency | Owner gate | Status | Evidence | Remaining work |
|---|---|---|---|---|---|---|---|---|---|
| MR-A1-01 | §A1.1–1.3 | `instrument_master.py`: Market/InstrumentType/Status/Entitlement enums; canonical IDs; membership intervals | test_instrument_master 57 | none (domain) | none (declared fixtures) | — | TESTED | WS §2 PKG-A | full symbol catalog per market needs authorized sources |
| MR-A1-02 | §A1.4 US-individual-equity exclusion | non-overridable spec invariant + hardened model_copy + reason-coded exclusion | test_instrument_master (3 exclusion + 3 copy tests); AUDIT-MR1 D | /api none (domain) | fixture records | — | INDEPENDENTLY-REPRODUCED | audit D: 32→30 included, 2 excluded w/ reason | real universe admission = provider entitlement (R-3/R-7) |
| MR-A1-03 | §A1 "source-backed, no pseudo-symbols" | `register_instrument` unsourced/pseudo rejection | test_instrument_master | none | — | — | TESTED | execution record §2 | — |
| MR-A2-01 | §A2 provider governance | provider seams left disabled; NO live activation; synthetic fixtures only | battery + AUDIT-MR1 C (no network imports) | none new | SYNTHETIC | R-3 OWNER-GATED | OWNER-GATED | STATUS gates block | dated R-3 amendment proposal (owner-side) |
| MR-A2-02 | §A2 historical-vs-live separation | `DataPolicy.adjustment_semantics` declared UNADJUSTED/ADJUSTED, never silent | test_backtest_product | backtest API | declared by caller | R-3 | TESTED | backtest spec doc | historical source entitlement decision |

## B. Charting platform (WDA-CHART)

| Req ID | Source | Implementation | Tests | Runtime caller | Data dependency | Owner gate | Status | Evidence | Remaining work |
|---|---|---|---|---|---|---|---|---|---|
| MR-B1-01 | §B1 timeframes | seeded 1m/5m/15m/1h/1D grid + `timeframe_spec` 8 standard + custom + legality guard | test_timeframe_spec 45 | chartpro (existing) | seeded | — | TESTED | timeframe spec doc | session calendars for real exchanges (calendar tables owner-admitted) |
| MR-B1-02 | §B1 honest labeling | `ResampleLabel`/`BarLabeling`; analyst weekly = RESAMPLED_FROM_1D_SYNTHETIC; HA = visual re-representation note | test_master_radar_api (analyst rows); test_master_radar_frontend_static (HA) | /api/v10/analyst | seeded | — | TESTED | analyst API docstring | per-series label surfacing in chart UI tooltips |
| MR-B2-01 | §B2 multi-chart workspaces | existing workspace.js (schema-versioned, corruption quarantine) preserved; chart grid = PARTIAL (single chart + oscillator pane) | WDA-1 tests (existing) | chartpro | seeded | — | PARTIAL | WDA matrix 2026-11-04 | detachable panels, multi-monitor, multi-chart sync = next increment |
| MR-B3-01 | §B3 chart types | candles/line/area/Heikin-Ashi selector in chart_pro (HA formula audit-verified) | test_master_radar_frontend_static 8 + node --check | chartpro tab | seeded | — | TESTED | execution record §2 | Renko/range/Kagi/LineBreak/PnF (require dedicated construction semantics — NOT-IMPLEMENTED honestly) |
| MR-B3-02 | §B3 drawing tools | existing trend/hline/fib/delete/lock-persist preserved | existing chartpro gates | chartpro | — | — | INTEGRATION-VERIFIED | WS-10 record | measured-move tool |
| MR-B3-03 | §B3 bar replay | existing replay.js preserved; deterministic seeded cursor via end_bar_index APIs | existing battery | replay tab | seeded | — | INTEGRATION-VERIFIED | baseline map | replay speed-control UI increment |
| MR-B4-01 | §B4 indicator manager | catalog (14 entries, 6 categories) + manager state machine + import/export validation + no-code-execution | test_indicator_catalog 34 + test_indicator_manager 35 | /api/v10/indicators | seeded compute | — | TESTED | indicator spec doc | user-authored indicator DSL (beyond RSL-1 indicators) = NOT-IMPLEMENTED |
| MR-B4-02 | §B4 per-indicator declarations | math definition/warm-up/missing-data/repaint/lookahead/permissions on all 14 | test_indicator_catalog | /api/v10/indicators/{id} | — | — | TESTED | catalog endpoint responses | independent numeric reference for adx/cci/williams (engine-only today, honest) |
| MR-B5-01 | §B5 alerts | existing local price alerts (in-product only) + alert ops inbox preserved | existing P5/P6 + D-AI-30 tests | chartpro + alert_ops | seeded | R-9 | INTEGRATION-VERIFIED | baseline map | indicator-condition alerts (needs DSL alert runtime in poll loop — NOT-IMPLEMENTED, R-6-adjacent) |

## C. AI indicator & strategy studio

| Req ID | Source | Implementation | Tests | Runtime caller | Data dependency | Owner gate | Status | Evidence | Remaining work |
|---|---|---|---|---|---|---|---|---|---|
| MR-C1-01 | §C1 workflow steps 4–10 | DSL authoring + validate + spec + backtest + paper replay + versioned reports/digests | test_master_radar_api 21 (strategylab rows) | /api/v10/strategylab + UI tab | seeded | — | INTEGRATION-VERIFIED | DSL/AI doc | AI clarification+codegen steps 1–3 = OWNER-GATED seam (below) |
| MR-C1-02 | §C1 AI proposal path | NOT IMPLEMENTED as live path; seam documented disconnected | source guards (no provider calls) | none | — | AI2_ENABLED=0, verified=False | OWNER-GATED | DSL/AI doc §safety | owner AI enablement decision |
| MR-C2-01 | §C2 DSL | RSL-1.0.0: lexer/parser/AST/types/validator/runtime, budgets, versioning, migration policy | test_strategy_dsl_* 182 | strategy_lab service | series ctx | — | INDEPENDENTLY-REPRODUCED (audit B: hand truth tables) | DSL spec doc | MTF/symbol runtime contexts = parse+validate ready, runtime plumbing PARTIAL |
| MR-C2-02 | §C2 sandbox | no eval/exec/compile/__import__; 39 sandbox tests + 9 fresh audit hostiles rejected | test_strategy_dsl_sandbox 39; AUDIT-MR1 C | — | — | — | INDEPENDENTLY-REPRODUCED | audit record | — |
| MR-C3-01 | §C3 approval workflow | DRAFT→APPROVED→PROMOTED state machine; promote 409-guarded; in-product only | test_master_radar_api (state machine rows) | /api/v10/strategylab/versions* | — | R-8/R-9 preserved | INTEGRATION-VERIFIED | execution record §2 | persistent approval log (owner decision) |
| MR-C3-02 | §C3 no live/self-modification | no broker/live path anywhere; gates unchanged | battery + AUDIT-MR1 C | — | — | R-8 | TESTED | STATUS gates block | — |

## D. Backtest engine

| Req ID | Source | Implementation | Tests | Runtime caller | Data dependency | Owner gate | Status | Evidence | Remaining work |
|---|---|---|---|---|---|---|---|---|---|
| MR-D1-01 | §D1 modes | single + multi-symbol/portfolio + all standard TFs + NEXT_BAR_OPEN/SAME_BAR_CLOSE policies | test_backtest_product 29 | /api/v10/strategylab/backtest | seeded | — | TESTED | backtest spec | intrabar/tick fidelity = honest bar-based only (declared) |
| MR-D2-01 | §D2 realism | shared ExecutionModelConfig: fees/spread/slippage/latency/lot/margin/leverage/short/volume-cap/currency; refusals recorded | test_execution_model 19 + backtest 29 | both engines | config | — | INDEPENDENTLY-REPRODUCED (audit B ≤3.6e-15) | audit record | exchange-specific fee schedules (owner/provider data) |
| MR-D3-01 | §D3 validity | no-look-ahead structural fill policy + appended-future-bars regression; min-bars/staleness refusals; declared adjustment semantics; PIT hooks (universe membership + corporate actions exist from prior waves) | runtime no-look-ahead test + DataPolicy tests | engines | PIT domain modules (existing) | — | TESTED | backtest spec §bias | walk-forward regime segmentation UI |
| MR-D4-01 | §D4 optimizer | grid/randomized/evolutionary + budgets + seeds + cancel/resume + IS-only selection + OOS confirmation + Bonferroni note | test_backtest_optimizer 22 | none yet (engine-level; API wiring next increment) | seeded | — | TESTED | backtest spec | UI for optimization runs |
| MR-D5-01 | §D5 report | full metric set + curves + monthly/yearly + distribution + long/short + regimes + benchmark + limitations + digest | test_backtest_product + api rows | /api/v10/strategylab/backtest | seeded | — | INDEPENDENTLY-REPRODUCED | audit B | PDF/CSV export of reports |

## E–G. Forward test, analyst, data quality

| Req ID | Source | Implementation | Tests | Runtime caller | Data dependency | Owner gate | Status | Evidence | Remaining work |
|---|---|---|---|---|---|---|---|---|---|
| MR-E-01 | §E paper runtime | hash-chained ledger + state machine + consistent cost model + expected-vs-realized + delay/gap measurement + maturity rules + comparison | test_forward_test_paper 62 | /api/v10/strategylab/paper-replay | seeded | R-6/R-9 | TESTED | forward spec | LIVE forward observation wiring = NOT-IMPLEMENTED (deliberate, owner-gated) |
| MR-F-01 | §F analyst | deterministic evidence-grounded report; 5-kind claims; provenance on every claim; scenarios+invalidation; missing-data honesty; forbidden-claims self-scan | test_symbol_analyst 65 | /api/v10/analyst/{symbol} | seeded + existing indicator engines | — | INDEPENDENTLY-REPRODUCED | analyst provenance doc | fundamentals/sector/signal context wiring (sources not admitted) |
| MR-G-01 | §G data quality center | per-symbol audit engine + market coverage reports + trust taxonomy | test_universe_data_quality 28 | none yet (engine-level) | injected series | — | TESTED | universe spec doc | Data Quality Center UI tab (next increment) |

## H–I. UX & Windows

| Req ID | Source | Implementation | Tests | Runtime caller | Data dependency | Owner gate | Status | Evidence | Remaining work |
|---|---|---|---|---|---|---|---|---|---|
| MR-H-01 | §H workspaces | new Strategy Lab tab (studio + indicator manager sub-views); 26-tab orchestrator green; RTL Persian UI | test_master_radar_frontend_static 8 + validator ok:true | UI tab | seeded | — | INTEGRATION-VERIFIED | UI doc | dedicated Backtest Center/Forward Center tabs (current: inside Strategy Lab) |
| MR-H-02 | §H command palette / shortcuts | existing menu customizer preserved | existing | UI | — | — | PARTIAL | baseline map | full palette |
| MR-I-01 | §I Electron security | shell gates byte-unchanged (contextIsolation, no node integration, no IPC); new module honors api-boundary | test_wda_electron_shell_gates (existing) + new static gates | electron | — | — | INTEGRATION-VERIFIED | WDA matrix | installer/upgrade/rollback artifacts + signing = NOT-VERIFIED (owner target machine) |

## Publication & governance

| Req ID | Source | Implementation | Tests | Runtime caller | Data dependency | Owner gate | Status | Evidence | Remaining work |
|---|---|---|---|---|---|---|---|---|---|
| MR-N-01 | §N forward-only + exact-SHA CI | forward-only commits; exact-SHA check-runs recorded post-push | CI | CI | — | — | recorded in WS1 §11 after publication | CI record | — |
| MR-N-02 | §N no parity/coverage claims | matrices use honest vocabulary only; scope statement §5 | — | — | — | — | ENFORCED | this matrix | — |
| MR-L-01 | §L owner gates | R-1..R-11 + AI2 gates unchanged | battery gates rows | — | — | R-1..R-11 | PRESERVED | STATUS gates block | owner actions list (M18) |

**Aggregate honesty:** this matrix deliberately contains PARTIAL/NOT-IMPLEMENTED/NOT-VERIFIED rows. Nothing here claims 100% roadmap completion, real-market coverage, TradingView parity, installer readiness, or live forward observation.
