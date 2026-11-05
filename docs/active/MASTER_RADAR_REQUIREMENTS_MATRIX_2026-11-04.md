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

---

## WAVE-2 ADDENDUM — 2026-11-04 (post-AUDIT-MR2 dispositions; execution record: `MASTER_RADAR_WAVE2_EXECUTION_RECORD_2026-11-04.md`)

| Req ID | Wave-2 disposition | Evidence |
|---|---|---|
| MR-B1-02 | PARTIAL → PARTIAL (narrower): backend `labeling` echo on chartpro series + honest per-series chip in the chart legend (server-fields-only, defensive) — the crosshair-tooltip surface does NOT exist in chart_pro and was NOT invented | test_master_radar_wave2_api (labeling rows) + test_master_radar_wave2_chartstatic |
| MR-B2-01 | unchanged PARTIAL (multi-chart sync/detach = future increment; this wave delivered the three product Centers instead) | wave-2 record §6 |
| MR-B3-02 | measured-move tool DELIVERED (3-click, persisted in primary + WDA-1 workspace snapshots, deletable/Escape-cancellable) | test_master_radar_wave2_chartstatic 7 |
| MR-B3-03 | replay ۰.۵× speed DELIVERED + parseFloat wiring fix (parseInt silently coerced 0.5→5 fallback) | test_master_radar_wave2_frontend (replay pin) |
| MR-B4-02 | independent references for adx/cci/williams DELIVERED (hand-computed fixtures + auditor-recomputed ≤1e-12; honest engine/reference separation preserved — NOT claimed dual-identical) | test_indicator_reference_wave2 13 + AUDIT-MR2 B.1 |
| MR-B5-01 | indicator-condition alerts: on-demand evaluator engine + `/alerts/evaluate` endpoint DELIVERED (request-scoped only — no scheduler R-6, no egress R-9; staleness refusal with explicit series-unit clock) | test_strategy_alerts_engine 22 + wave2 api alert rows |
| MR-C2-01 | MTF runtime plumbing INTEGRATION-VERIFIED: strict close-ts no-look-ahead alignment + fail-closed non-monotonic refusal (AUDIT-MR2 O3) + discriminating-scenario proof by the auditor | test_strategy_dsl_mtf_runtime 22 + AUDIT-MR2 B.2 |
| MR-D4-01 | optimizer API + Backtest-Center UI DELIVERED (seed required, budget guard 500, explicit JSON space, IS-only selection + OOS-once confirmation, Bonferroni echo, reproducibility digest; determinism test-pinned) | test_master_radar_wave2_api optimize rows |
| MR-D5-01 | CSV/JSON report export DELIVERED (full-report json attachment; flat csv projection with documented units; byte-identical csv) | test_master_radar_wave2_api export rows |
| MR-G-01 | Data Quality Center UI + API DELIVERED (market summaries incl. reported exclusion, per-symbol mechanical audits w/ injected as_of, 7-class legend with honest REAL_VERIFIED absence note) | test_master_radar_wave2_api dataquality rows |
| MR-H-01 | dedicated Backtest Center / Forward Test Center tabs DELIVERED (26→29 tabs, validator 29/29) | test_master_radar_wave2_frontend |
| MR-D3-01 | regime segmentation surfacing re-verified already present (`report.regime_segments`); Backtest Center renders the regime table | wave2 api regime row |
| AUDIT-MR2 | 0 FAILs; O1/O2/O3/O4/O6 fixed in-wave (strengthened/new tests); O5/O9 accepted observations w/ rationale; O1-vacuousness replaced with structural IS/OOS pins | `audits/2026-11-04-master-radar-wave2/AUDIT_MR2_REPORT.md` |
| Records O7 | wave-1 §4 dangling AUDIT-MR1 reference corrected honestly (file never committed; AUDIT-MR2 is the audit record of reference for both waves) | wave-2 record §4 |

Battery: **2499 passed / 2 skipped = 2400 + 99 exact** (skip drift vs the wave-1 "2401/1s" record audit-explained: GOV-19 bundle absent from this fresh checkout; G2 substantive-rejection test self-skips on the docs-only parent delta). Gates unchanged.

---

## WAVE-3 ADDENDUM — 2026-11-04 (post-AUDIT-MR3 dispositions; execution record: `MASTER_RADAR_WAVE3_EXECUTION_RECORD_2026-11-04.md`)

| Req ID | Wave-3 disposition | Evidence |
|---|---|---|
| MR-B1-02 | crosshair readout surface DELIVERED (`#cpCrossReadout`: hovered-bar O/H/L/C/V from the loaded data + `bar_class`/`method` verbatim from the server labeling object; nothing fabricated; defensive container check) — per-series honest labeling now surfaced in the chart UI at the hovered bar | test_master_radar_wave3_chartstatic + integration pins |
| MR-B2-01 | multi-chart grid with configurable sync DELIVERED (layouts ۱/۲/۴, range/crosshair/symbol-follow toggles, fail-closed `radar.chartgrid.v1` persistence, per-pane symbol/TF, server-fields-only trust labels) — detachable panels/multi-monitor remain honestly NOT-IMPLEMENTED | chart_grid.js + test_master_radar_wave3_chartstatic |
| MR-B3-01 | Renko/Range/Kagi/LineBreak/PnF DELIVERED with dedicated construction semantics (pinned conventions in module docstring, hand-computed fixtures, no-look-ahead prefix stability, ATR-mode whole-series parameter resolution honestly disclosed) + `POST /chartpro/{symbol}/derived` with `method: DERIVED_*` labeling and bilingual honesty notes; derived views deliberately hide NATIVE-bar overlays | engines/derived_charts.py + test_derived_charts 32 + test_chart_pro_derived_api 23 |
| MR-D3-01 | walk-forward analysis DELIVERED (`POST /strategylab/walkforward`: pinned fold math, per-fold seed = seed+i, IS-only selection per fold, OOS confirmed EXACTLY ONCE per fold with frozen params — audit-verified with a ±1e9 flip leaving selection byte-identical; unfit windows 422 naming available vs required; deterministic digest) | engines/walk_forward.py + test_walk_forward 38 + AUDIT-MR3 §C |
| MR-H-02 | full command palette DELIVERED (Ctrl/Cmd+K + button; live-DOM action registry incl. all 29 tabs, chart types, replay speeds, grid controls; explicit-selection-only execution — test-pinned; recent actions in-product) | command_palette.js + test_master_radar_wave3_frontend |
| Integration | sw v3-0-8 (+2 precache), main.js +2 imports, index.html honest DERIVED segment + containers; counter-pins recorded ×4 | test_master_radar_wave3_integration 8 |
| AUDIT-MR3 | 7/7 PASS, 0 FAILs; Obs.3 fixed post-audit (cache hygiene symmetry); Obs.1/2/4/5/6 accepted w/ rationale; Obs.7 INFO | `audits/2026-11-04-master-radar-wave3/AUDIT_MR3_REPORT.md` |
| MR-B4-01 | user-authored indicator DSL beyond RSL-1: still NOT-IMPLEMENTED (recorded honestly — unchanged) | this addendum |
| MR-B2-01 (residual) | detach/multi-monitor: NOT-IMPLEMENTED (recorded honestly — unchanged) | this addendum |

Battery: **2625 passed / 1 skipped / 0 failed = 2500 + 125 exact** (7 new test files: 32+23+38+12+12+8). Gates unchanged.

---

## WAVE-A ADDENDUM — 2026-11-04 (directive "COMPLETE REMAINING ROADMAP" §11 WAVE-A; execution record: `MASTER_RADAR_BOURSE_WAVE_A_EXECUTION_RECORD_2026-11-04.md`)

Reconciliation statement (directive §2.5): every base row above was re-read TOGETHER WITH the WAVE-2 and WAVE-3 addenda; effective current status = base row as superseded by the latest addendum disposition. No base row was found treated as current where a later addendum supersedes it. Rows closed by addenda (MR-B1-02, MR-B2-01, MR-B3-01/02/03, MR-B4-02, MR-B5-01, MR-C2-01, MR-D3-01, MR-D4-01, MR-D5-01 partial, MR-G-01, MR-H-01, MR-H-02) carry their addendum status, not the base status. The directive's 13-field matrix layout maps onto the existing 10-column layout as documented in the WAVE-A record §5.

| Req ID | WAVE-A disposition | Evidence |
|---|---|---|
| MR-B2-01 (operational) | FIRST in-browser operational evidence for the multi-chart/UI surface: real browser session on the running app — 29 tabs enumerated, Chart Pro golden path (فملی 1m) with canvas + crosshair readout + chartpro/indicators API 200s, RTL/fa verified, 0 console errors | WAVE-A record §3.2 + screenshot |
| MR-H-01 (operational) | same-session evidence: full 29-tab navigation registry live-DOM verified through the right-side preview transport | WAVE-A record §3.2 |
| MR-A2-01 | trust disclosure verified in the running UI (`source=mock_fallback`, `کلاس بازار: SYNTHETIC`, `trust_class: SYNTHETIC` in dataquality API) — synthetic-as-real misclassification absent; R-3 intact | WAVE-A record §3.2 |
| MR-B4-01 | user-authored indicator DSL: still NOT-IMPLEMENTED → WAVE-B primary package | WAVE-A record §5 |
| MR-B2-01 (residual) | detach/multi-monitor: still NOT-IMPLEMENTED → WAVE-B secondary package (popup-class detach; OS placement not claimable) | WAVE-A record §5 |
| MR-D5-01 (residual) | PDF export: still NOT-IMPLEMENTED (CSV/JSON delivered wave-2) → WAVE-D | WAVE-A record §5 |
| MR-B1-01 (residual) | session calendars: declared-calendar model with honest DECLARED trust class → WAVE-E; sourced holiday tables stay owner-gated (R-3/R-7) | WAVE-A record §5 |
| MR-C1-02 | AI Studio steps 1–3 stay disconnected/owner-gated; WAVE-C = evidence package only, no runtime caller added | WAVE-A record §5 |
| MR-I-01 (residual) | repository-side packaging readiness (electron-builder NSIS config exists at `electron/package.json`; no signing claims) → WAVE-G | WAVE-A record §5 |
| NEW: SITE-PREVIEW | actual site startup + right-side preview DELIVERED and browser-verified (real FastAPI backend, verbatim preview transport outside the repo, 0 console errors); Vercel investigated separately = owner-credentials-required, remains FAILURE classification | WAVE-A record §3–§4 |

Battery at WAVE-A baseline (re-run in the WAVE-A checkout): **2625 passed / 1 skipped / 0 failed in 26.59s** — exact match to the WAVE-3 record. Gates unchanged.

---

## WAVE-B ADDENDUM — 2026-11-04 (directive §11 WAVE-B; execution record: `MASTER_RADAR_WAVEB_EXECUTION_RECORD_2026-11-04.md`; audit: `audits/2026-11-04-master-radar-waveb/AUDIT_MR4_REPORT.md`)

| Req ID | WAVE-B disposition | Evidence |
|---|---|---|
| MR-B4-01 | user-authored indicator DSL: **INTEGRATION-VERIFIED** — UIDL-1 (INDICATOR/INPUT/PLOT) over the shared RSL-1 lexer/parser/typechecker/budgets/interpreter; numeric-series-only plots (bool channels refused); no-look-ahead enforced at compile; structural+evaluation-time warm-up (catalog parity); install/uninstall/enable/disable/semver-upgrade/export/import with checksums + fail-closed re-compiling import; `/api/v10/user-indicators` full surface with SYNTHETIC_SEEDED honesty + `valid_from_index`; governed frontend panel (api.js-only, no eval, server-field trust labels, warm-up-excluded drawing, package export/import) | 60 engine tests (incl. independent naive recomputation battery + 8 hostile payloads) + 29 API tests (lifecycle/tamper/boundaries) + 26 static pins; AUDIT-MR4: fresh-clone battery ×2, 43 live hostile probes 0×5xx, A/B runtime equivalence 2415 decisions + 18 error pairs 0 mismatches; owner target-machine acceptance remains R-1/R-2-gated |
| MR-B2-01 (residual) | popup-class detach: **INTEGRATION-VERIFIED (popup scope)** — per-sub-pane `window.open` same-origin popup with fail-closed hash (0..2), chrome-less boot, two-way BroadcastChannel symbol/TF sync with message validation + echo guard; OS placement NOT claimed; inter-window crosshair/range sync NOT claimed in v1 (documented in module + UI + record); multi-monitor = user drags popup to another display (browser capability) | 26 static/integration tests incl. detach pure-logic pins; AUDIT-MR4 check 7; detachable-panel residual beyond popup scope recorded honestly |
| SW/pins | sw v3-0-9 (+2 precache), 5 recorded counter-pin bumps, tabs 29/29 | `test_master_radar_waveb_frontend.py` + 4 bumped pin files |
| Battery | 2739 passed / 2 skipped / 0 failed = 2624 + 115 exact (skips = documented environmental G2-harness conditionals) | AUDIT-MR4 check 1 (×2 fresh-clone reproduction) |
| Gates | unchanged: AI2_ENABLED=0 (config.py:111), verified=False posture, SYNTHETIC_OR_PAPER, no scheduler/egress/live path, no runtime caller added to any disconnected edge; INSTALL NOT ISSUED | AUDIT-MR4 check 6 (diff 0 bytes) |

Remaining after WAVE-B (unchanged from the WAVE-A gap list): WAVE-D PDF export, WAVE-E declared session calendars, WAVE-C AI-seam evidence only, WAVE-F five product loops audit, WAVE-G repo-side packaging readiness, WAVE-H 17-role audit + owner package; legacy demo modules removal assigned to a future hygiene wave (AUDIT-MR4 O1).

## WAVE-C ADDENDUM — 2026-11-05 (directive §11 WAVE-C; evidence package: `MASTER_RADAR_WAVEC_AI_SEAM_EVIDENCE_2026-11-05.md`)

| Req ID | WAVE-C disposition | Evidence |
|---|---|---|
| MR-C1-02 | **OWNER-GATED — evidence package only, zero code delta, no runtime caller added.** Static disconnection proof delivered: (2.1) live openapi 124 paths contain NO strategy-proposal endpoint (only the pre-existing deterministic `/api/ai/filter-proposals*` filter-intelligence surface, a different governed product); (2.2) zero `ai2_service` imports under app/api; (2.3) frontend strategy lab sends user-authored source only (`slDslSource` → /validate, /spec, /backtest, /paper-replay, /versions) — no NL input, no generation call; (2.4) seam labelled disconnected in the API contract (`strategy_lab.py:11-12,255` `generated_by` provenance); (2.5) ai2_service exposes no HTTP route by construction. Gate triple verified ENGAGED: `is_verified_live` structurally unreachable (config.py:156-166, 248-252 "no caller — including tests — can mint verified LIVE"), `AI2_ENABLED=0` default (config.py:111), data-trust fail-closed. Governed steps 4–10 live-demonstrated on synthetic data: /validate ok+typed 422 refusals, /spec RSL-1.0.0 + digest 63ae677e…, /backtest BT-PRODUCT-1.0.0 + result_digest 0f1ae1c0… (37 trades, full metrics), /paper-replay PAPER_REPLAY_OVER_SYNTHETIC_WINDOW + ledger_chain_ok + not_live_note. Interface contract for the future seam pinned (generated source enters the SAME governed chain; AI-provenance `generated_by`; verified=False until human approval + owner enablement). | `MASTER_RADAR_WAVEC_AI_SEAM_EVIDENCE_2026-11-05.md` §§2–6; live runtime session 2026-11-05 at 446be35; config.py byte-diff zero |
| Gates | unchanged: AI2_ENABLED=0 · verified=False · SYNTHETIC_OR_PAPER · no scheduler/egress/live/purge path · Two-Key Rule intact · INSTALL NOT ISSUED | evidence package §3 |

Remaining after WAVE-C (unchanged): WAVE-D PDF export, WAVE-E declared session calendars, WAVE-F five product loops audit, WAVE-G repo-side packaging readiness, WAVE-H 17-role audit + owner package.
