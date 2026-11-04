# MASTER-RADAR WAVE-2 EXECUTION RECORD — 2026-11-04

Directive: **MASTER DIRECTIVE — RADAR WINDOWS PROFESSIONAL TRADING, AI INDICATOR/STRATEGY STUDIO, MULTI-MARKET DATA, BACKTEST & FORWARD-TEST PLATFORM** (continuation wave closing the non-owner-gated "Remaining work" rows of `MASTER_RADAR_REQUIREMENTS_MATRIX_2026-11-04.md`). Baseline verified before start: remote `main` == local HEAD == `269f149…`; a records-only CI-currency commit `6a79ab7` (WS1 §11 backfill) was published first. All prior accepted work preserved; forward-only; no amend/rebase/reset/force.

## 1. Package plan and disjoint ownership (4 parallel packages + main-agent integration)

| Package | Scope | Ownership (disjoint) |
|---|---|---|
| MR2-A | engines: independent ADX/CCI/Williams references, catalog wiring, DSL MTF runtime plumbing, on-demand alert evaluator | `indicator_reference.py`, `indicator_catalog.py`, `strategy_dsl/runtime.py`, NEW `strategy_alerts.py` + 3 new test files |
| MR2-B | API: `/optimize`, `/backtest/export`, data-quality router+service, chartpro labeling echo, main.py registration | `strategy_lab.py`, NEW `data_quality_api.py`/`data_quality_service.py`, `chart_pro.py`, `main.py` + 1 new test file |
| MR2-C | frontend: 3 product tabs (Backtest Center / Forward Test Center / Data Quality Center), SW bump, recorded counter-pins | `index.html`, `main.js`, `sw.js`, 3 new modules, the 5 pin files + 1 new test file |
| MR2-D | chart increments: measure-move tool, per-series labeling chip (defensive consumer) | `chart_pro.js` only + 1 new test file |
| Integration (main agent) | contract syncs across packages, `/alerts/evaluate` endpoint, workspace allowlist, api.js content-type, replay 0.5×, audit-fix wave | recorded below |

## 2. Implementation inventory (all additive)

**Wave-2 API surface (backend):**
- `POST /api/v10/strategylab/optimize` — §D4 optimizer wiring over the SAME seeded-series path as `/backtest` (no new data path): `method ∈ {grid, randomized, evolutionary}`, REQUIRED `seed` (422 otherwise), server-side budget guard `max_evals ≤ 500` (422 with honest Persian+English note), `space` = explicit JSON `{grid|bounds}` (no hidden default space), `objective ∈ {SHARPE, CALMAR, PROFIT_FACTOR}`, **`selection_basis` always "IN_SAMPLE"**; OOS block evaluated EXACTLY ONCE post-selection via the engine's `select_then_confirm` (`oos_evaluated_once` echoed); Bonferroni note echoed; refusals/constraint-skips counted and echoed; ranked rows capped at 50 with full counts; `reproducibility_digest` deterministic; `cancelled`/`budget_exhausted` partial-honesty notes.
- `POST /api/v10/strategylab/backtest/export` — `format=json` (FULL report attachment `backtest-report-<digest8>.json`) or `format=csv` (flat projection: `## METRICS` line-pairs + `## TRADES` section; English keys; documented pct units; byte-identical for identical inputs; the json embeds the canonical trust envelope whose `checked_at` is wall-clock by design — non-byte-identity honestly documented).
- `POST /api/v10/strategylab/alerts/evaluate` — §B5 ON-DEMAND indicator/strategy-condition evaluation of an RSL-1.0.0 program's ENTRY decision at the last closed bar. **Manual/request-scoped ONLY: no scheduler, no background loop (R-6 intact); result stays in the response — no notification egress (R-9 intact).** Staleness refusal (engine capability `STALENESS_WINDOW_BARS=3 × median interval`) activates ONLY with an explicit caller-supplied `staleness_as_of` IN THE SERIES' OWN TIME UNIT — the seeded series uses compressed synthetic timestamps, so no wall clock is read and none is guessed (a real-clock default would be a unit mismatch; recorded as a design decision).
- `GET /api/v10/dataquality/markets`, `GET /markets/{market}/coverage`, `GET /symbols/{instrument_id}/audit` — §G Data Quality Center surface over the deterministic fixture universes: per-market summaries (incl. `EXCLUDED_US_EQUITY` with `in_default_universe=false` — exclusion REPORTED, never hidden), full per-symbol mechanical audits (duplicates/out-of-order/invalid-OHLCV/missing-intervals/stale with INJECTED as_of, never wall clock), TrustClass per row, canonical non-live trust envelope everywhere.
- `chart_pro.py` — additive `labeling` echo on series responses (`{bar_class: "SYNTHETIC", method: "NATIVE", note_en, note_fa}`) derived from `market_service.data_trust_context()`; hardcoding any trust label is forbidden and absent.
- `main.py` — exactly ONE new router registration + import (2-line diff; all 11 pre-existing registrations byte-identical).

**Wave-2 engines (backend):**
- `indicator_reference.py` — three INDEPENDENT textbook references (no import from `app.engines.indicators`): `ref_adx` (Wilder +DI/−DI/DX/ADX; ADX seed = mean of first `period` DX; first valid at `2*period−1`), `ref_cci` ((TP−SMA(TP,n))/(0.015·MD); MD=0→0), `ref_williams_r` ((HH−C)/(HH−LL)·−100; flat window→−50; +0.0 sign convention pinned via `copysign`). `indicator_catalog.py`: the existing `builtin.adx/cci/williams` entries gained `reference_ref` wiring (honesty invariant `dual == (engine_ref == reference_ref)` preserved — these stay engine+reference pairs, NOT claimed dual-identical).
- `strategy_dsl/runtime.py` — MTF runtime plumbing (keyword-only, default-None = zero behavior change): `prepare/evaluate/run_over_series(..., mtf_context={"TF": [bar dicts]})` + optional `SeriesContext.ts`. STRICT no-look-ahead alignment: a higher-TF bar is readable at base bar `i` only if its CLOSE timestamp ≤ `ts[i]` (close-ts derives from explicit `close_ts`, else the NEXT bar's open ts as a provable close bound, else the tail bar is NOT closed — never readable). Not-yet-closed reads return the documented `0.0` warm-up. New fail-closed codes: `RUN_MTF_MISSING_BASE_TS`, `RUN_MTF_BAD_BARS`, `RUN_MTF_NONMONOTONIC_CLOSE_TS` (AUDIT-MR2 O3 fix), plus the pre-existing `RUN_MISSING_MTF_SERIES`.
- `strategy_alerts.py` (NEW) — `evaluate_condition(source, series, *, as_of=None)`: compile-via-DSL + run + last-closed-bar verdict; staleness refusal BEFORE compilation (`program_digest=None`, `bars_evaluated=0`); deterministic; zero egress primitives (scan-pinned).

**Wave-2 frontend:**
- 3 new tabs (26→29, validator `ok:true`, no orphans/missing/duplicates): «مرکز بک‌تست» (run form, metrics, equity canvas, trades/regime tables, CSV/JSON export via Blob download, optimizer section with client-side seed enforcement + JSON space input + IS-winner/OOS-confirmation rendering incl. `bonferroni_note`), «مرکز فوروارد تست» (paper replay, ledger table + `ledger_len`/`ledger_chain_ok` verbatim, expected-vs-realized deltas, PAPER-only note), «مرکز کیفیت داده» (market selector populated from the server, market CoverageReport summary, per-symbol audit rows with per-row detail drill-down, 7-class trust legend with the honest "REAL_VERIFIED does not exist in this repo currently" statement).
- `chart_pro.js`: measure-move tool (`measure-move`, 3-click anchor/end/target with live provisional delta label, persisted in the existing drawings store, deletable, Escape-cancellable) + per-series labeling chip (`#cpLabelingChip`, verbatim server fields via `textContent`, rendered ONLY when the server provides `labeling` — no fallback text that could masquerade as a data claim).
- `core/api.js`: additive content-type-aware response (JSON parsed as before; non-JSON — e.g. the CSV attachment — returned as text). All JSON endpoints byte-identical in behavior.
- `workspace.js`: `WORKSPACE_DRAWING_TYPES` += `"measure-move"` (WDA-1 secondary snapshot now persists the new drawing type; existing types untouched).
- `replay 0.5×`: new speed button + `parseFloat` wiring (parseInt("0.5")===0 would have silently fallen back to 5× — pinned by test).
- `sw.js` v3-0-6→v3-0-7 with the 3 new modules precached (recorded bump).

## 3. Integration-phase contract syncs (recorded, all test-pinned)

1. Optimizer path: MR2-C guessed `POST /optimizer`; actual router is `POST /optimize` — frontend synced + test now pins the real path AND asserts the guessed path is gone.
2. Export contract: MR2-C posted `{run_id, result_digest}`; the service is stateless by design — frontend now re-sends the EXACT last `/backtest` request body (+format) so the same digest/report is regenerated.
3. Data-quality paths: MR2-C guessed `/coverage?market=`/`/audit?market=`; synced to `/markets` + `/markets/{m}/coverage` + `/symbols/{id}/audit` (coverage rows double as audit rows; drill-down per symbol).
4. `core/api.js` content-type branch (required for the CSV attachment to be downloadable through the single api() boundary; the pre-existing Prometheus text endpoint also becomes non-crashing — strict improvement, JSON behavior unchanged).
5. Optimizer body shape: `{source, symbol, timeframe, count, method, space, budget:{max_evals,seed}, oos:{enabled}}` + JSON-space textarea with client-side parse refusal.

## 4. AUDIT-MR2 (independent, read-only, pre-publication) — 0 FAILs

Full report: `docs/active/audits/2026-11-04-master-radar-wave2/AUDIT_MR2_REPORT.md`. Headlines: battery re-run 3×; 5/5 honesty-critical claims re-derived (incl. OOS-once proven BY INSTRUMENTATION); MTF no-look-ahead proven with an auditor-constructed discriminating scenario; independent CCI/Williams recomputation exact; 14 fresh hostile DSL sources + 24 abuse probes → zero 500s; source scans clean; gates verified byte-identical; DQ exclusion reporting honest. **9 observations: O1 (vacuous OOS assertion), O2 (winner-box key drift), O3 (MTF close_ts monotonicity), O4 (−0.0 sign assertion), O6 (unknown-symbol honesty note) FIXED IN-WAVE with strengthened/new tests; O5 (CSV formula-injection guard — low: local desktop product, synthetic data, user-generated attachment content) and O9 (G2 `SUBSTANTIVE_CHANGES_SINCE` runtime path uncovered in THIS checkout — repo-state-dependent, pre-existing) recorded as accepted observations; O7 corrected; O8 handled by this records commit.**

**Records defect corrected honestly (O7):** the wave-1 record §4 cites `MASTER_RADAR_INDEPENDENT_AUDIT_2026-11-04.md` — that file was NEVER committed (the reference is dangling; the audit ran in its authoring session but only its §4 summary was published). Correction: this wave's AUDIT-MR2 report (committed alongside, covering both waves' surfaces at the current tree) is the independent-audit record of reference; the dangling pointer is explicitly acknowledged here rather than silently left.

## 5. Test evidence (exact)

- Full battery: **2499 passed / 2 skipped / 0 failed = 2400 + 99 exact**, ~18.3s. The 2 skips are environment/repo-state conditional and audit-verified (G2 substantive-rejection test self-skips against the docs-only committed parent delta; GOV-19 evidence bundle absent from this fresh checkout) — neither hides a failure. NOTE on skip-count drift vs the wave-1 record ("2401/1s"): that checkout contained the GOV-19 bundle; this fresh checkout does not (audit A.2).
- New test files (6) and exact counts: `test_indicator_reference_wave2` **13**, `test_strategy_dsl_mtf_runtime` **22** (19 + 3 audit O3 regressions), `test_strategy_alerts_engine` **22**, `test_master_radar_wave2_api` **24**, `test_master_radar_wave2_frontend` **11** (8 + O2-contract pin + replay-0.5× pin), `test_master_radar_wave2_chartstatic` **7**. Total **99**.
- Recorded counter-pin bumps (5 files, established discipline, dated comments): tabs 26→29 in `test_wda_analytics_static.py` + `test_frontend_static_script.py`; SW v3-0-6→v3-0-7 in `test_wda_version_consistency.py` + `test_p3_80_local_closure.py` + `test_master_radar_frontend_static.py`. Structural invariants unchanged; no assertion weakened beyond the recorded numeric bumps (audit A.4).
- `pyflakes app tests`: zero NEW findings (3 pre-existing notes in old files unchanged). `git diff --check` clean. `node --check` green on all 9 touched/created JS files. `scripts/validate_frontend_static.py` → `ok:true`, tabs 29 = panels 29, no orphans/duplicates/missing imports.

## 6. Honest scope statement (what this wave does NOT claim)

- No real/live market data anywhere; every value SYNTHETIC/PAPER-labeled; R-3 intact; the alert endpoint evaluates SEEDED data only.
- No scheduler/background task of any kind was added (R-6); the alert evaluation is request-scoped by design.
- No notification egress was added (R-9); the evaluation result stays in the HTTP response.
- Chart crosshair-tooltip data-class was SKIPPED honestly (chart_pro has no OHLC crosshair readout; nothing invented) — MR-B1-02 remains PARTIAL (backend labeling + legend chip delivered; tooltip surface does not exist).
- Multi-chart synchronized workspaces (MR-B2-01) and Renko/Kagi/PnF chart types (MR-B3-01) remain NOT-IMPLEMENTED — recorded honestly.
- Installer/signing/upgrade artifacts remain owner-gated (R-1/R-2, target machine); the version registry remains in-memory pending an owner persistence decision.
- No parity/superiority claims; the capability vocabulary stays EXISTS/PARTIAL/MISSING/NOT-VERIFIED.

## 7. Gates and governance (unchanged, re-verified)

`AI2_ENABLED=0` (config.py:111) · `verified=False` (config.py:284) · `SYNTHETIC_OR_PAPER` (g2_gate.py) · kill switches ENGAGED · no ai2 imports under app/api · no runtime caller added to any disconnected edge · no purge path · no scheduler · no external egress · R-1..R-11 untouched · D1-D7 recorded decisions in force · INSTALL NOT ISSUED.

## 8. Publication chain (recorded after push)

`6a79ab7` (CI-currency records, WS1 §11) → `3ec3427` (WAVE-2 implementation) → this records commit. Exact-SHA CI conclusions for the published SHAs are appended to `WS1_EXACT_SHA_EVIDENCE_2026-11-02.md` §12 after CI completes (established WS1 discipline).
