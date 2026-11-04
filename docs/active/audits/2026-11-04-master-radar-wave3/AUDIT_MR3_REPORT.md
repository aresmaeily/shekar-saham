# AUDIT-MR3 — Independent Pre-Publication Audit Report (MASTER-RADAR WAVE-3) — 2026-11-04

Auditor: independent read-only audit agent (no repo mutation; throwaway checks via `python -c`/heredocs only; `pytest -p no:cacheprovider`; working tree verified byte-identical before/after the audit: 10 modified / 16 untracked, unchanged).

Scope: the uncommitted WAVE-3 wave at HEAD `d7b2df8` — (1) derived chart constructions `RENKO/RANGE/KAGI/PNF/LINEBREAK` (`backend/app/engines/derived_charts.py` + `POST /api/v10/chartpro/{symbol}/derived`), (2) walk-forward analysis with per-fold IS-selection + OOS-confirmed-once (`backend/app/engines/walk_forward.py` + `POST /api/v10/strategylab/walkforward`), (3) frontend crosshair readout + multi-chart grid + command palette + integration (`chart_pro.js`, `chart_grid.js`, `command_palette.js`, `index.html`, `main.js`, `sw.js`).

## Dimensions

**A. REPRODUCTION — PASS.** Full battery run twice consecutively: **2625 passed / 1 skipped / 0 failed** (24.8s / 25.3s). Exactly the claimed counts; stable.

**B. DERIVED-CHARTS HONESTY — PASS.**
- RENKO (brick=2; closes 10, 12.5, 14, 11.5, 9.5): hand-derived 3 bricks `[(t1,10→12,up),(t2,12→14,up),(t4,12→10,down)]` (t3 close 11.5 correctly absorbed) → engine output identical.
- KAGI (reversal_pct=10; closes 100,110,105,90,95): hand-derived `[{t3,110},{t4,90}]` (turn at t3 on 90 ≤ 110×0.9=99; no turn at t4) → identical, including terminal-point logic.
- LINEBREAK (lines=3, 6 bars): 3 verbatim seeds; t3 UP bar open=9=min low of window; t4 absorbed; t5 DOWN bar open=12=max high of window → identical. Bonus PNF (box=2, rev=2) hand-matched exactly (floor discretization, touch-reversal at exactly 10 ≤ 14−4, final open down-column 10→4).
- No-look-ahead prefix stability (independent `python -c`, RENKO/LINEBREAK/KAGI/RANGE): `construction(bars[:k])` == prefix of `construction(bars)` restricted to units completing in the prefix — exact at every k (KAGI terminal-aware against an independent docstring-only reimplementation).
- API labels: single code path always emits `method: "DERIVED_"+type`; observed live `DERIVED_KAGI`/`DERIVED_RENKO` with honest bilingual notes ("not real market bars; not an independent data source; identical arguments reproduce identical output"); `bar_class` reused verbatim from the canonical `_labeling_echo()`.
- No hardcoded trust labels: word-boundary grep for `LIVE|REAL_VERIFIED|REAL|VERIFIED` across the four backend files → 0 hits (substring hits are comments and the pre-existing canonical `ctx.get("is_live")` read-through, unchanged).

**C. WALK-FORWARD NO-LOOK-AHEAD + OOS-ONCE — PASS.**
- Test window never in the selection path: `grid_search` receives only the IS objective closure over `train_slice`; `select_then_confirm` ranks IS records before invoking the OOS closure. Empirically confirmed with a logging evaluator: every selection-phase evaluation saw exactly a train window (len 30, starts 0/10/20); len-10 test windows appeared exactly once per fold.
- Seed derivation `per_fold_seed(seed,i)=seed+i` docstring-pinned; fold rows echoed 777/778/779 for seed 777; digests track seed changes.
- OOS exactly once per fold with frozen params: 3 OOS calls for 3 folds, each with `best_params`, ordered after all train calls; discriminating probe flipping the OOS return from +1e9 to −12345 left every fold's `best_params`/`is_objective` byte-identical; `oos_eval_count` never enters `evaluated_count` (IS trials only). `select_then_confirm`'s extra IS call identified as the documented frozen-winner re-evaluation.
- Unfit refusal names both numbers: `fold_windows(50,3,30,10)` → "required train_bars + n*test_bars = 60 bars > available 50 bars"; API 422 carries `available`/`required` + FA numerals.
- Window math: `fold_windows(100,3,30,10)` → `[((0,30),(30,40)),((10,40),(40,50)),((20,50),(50,60))]` — exactly the pinned expectation.

**D. HOSTILE PROBES — PASS.** ~45 probes against both endpoints via `create_app()` + distinct client identity `("audit-mr3", 5999)`: **zero 500s**. Derived: 422 for empty body, `type:123`, `type:"DROP TABLE"`, params-as-list, nested dict/list values, negative/zero brick, both-RENKO-params, atr_period 1/"14", missing/negative range_size, lines=999, reversal_boxes=0, timeframe "2h", string limit — all bilingual honest detail; raw NaN/Infinity JSON → 422; honest 200s: limit clamps (999999→1000, −50→50), huge finite brick (1e308), unknown symbol, unicode symbol, unknown extra field ignored (documented); one 404 for URL-encoded `<script>` symbol (routing rejection, acceptable). Walkforward: 422 for null/XSS/SQLi source (DSL parse/lex error codes, no reflection), `objective:"MAKE_MONEY"`/`"OOS_SHARPE"` (INVALID_OBJECTIVE), space-as-list, nested grid values, NaN seed/n, negative max_evals/n, count 999999, timeframe "7D", negative end_bar_index, max_evals 999999 (BUDGET_LIMIT); honest 200s: seed=10³⁰, unknown/unicode symbol, and NaN grid values → recorded as a refusal candidate (`evaluated 2, evaluable 1`), never ranked, never silent.

**E. FRONTEND SECURITY & HONESTY — PASS.**
- No `fetch`/`XMLHttpRequest`/`WebSocket`/`eval`/`new Function`/`importScripts`/`innerHTML`/`document.write`/`insertAdjacentHTML` tokens in `chart_grid.js` (675 lines), `command_palette.js` (380 lines), or any added `chart_pro.js` hunk. Benign tokens only: `localStorage` (fail-closed persistence w/ quarantine) and two `setTimeout` (600ms save debounce; 100ms tab-click bind — no polling).
- All HTTP via `api()` (chart_grid: one GET; palette: zero network; chart_pro derived: POST via `api()`).
- Trust labels: the only `LIVE (تأییدشده)` string in `chart_grid.js:505` is byte-identical to the pre-existing `cpSourceBadge` rule in `chart_pro.js` (856/867) and renders only when the server asserts all three fields (`state==="live" && is_live===true && live_verified===true`) — strictly-gated server-field passthrough identical to the shipped WAVE-2 pattern; the canonical backend context can never mint `is_live:true`. Crosshair readout echoes `bar_class`/`method` verbatim from the server labeling object only.
- Dynamic text exclusively via `textContent` on `createElement` nodes; palette executes actions ONLY on explicit selection (option click or Enter-on-selection; pinned by `test_palette_actions_run_only_on_explicit_activation`).
- `index.html`: honest DERIVED titles on `cpTypeSeg` + all 5 new buttons; `cpCrossReadout`, `cpGridBar`/`cpGridRoot`, palette button/root present. `scripts/validate_frontend_static.py` → `ok:true`, tabs_count 29, panels 29, no missing/orphan/duplicates, no stale version literals, exit 0.

**F. GATES SWEEP — PASS.** `git diff backend/app/core/config.py` = 0 bytes; `AI2_ENABLED` default `"0"` at line 111; `verified=False` posture untouched; zero diffs under `app/core`, `app/services`, `app/data`, tracked `app/engines`; no notifier/ws_hub/g2_gate changes; modified tests = exactly the 4 recorded counter-pin files (SW cache-name bump v3-0-7→v3-0-8 with recorded comments); new files = the 2 engines + 2 API edits + 7 new test files + 3 new/edited frontend modules + 3 integration files. Six untracked non-wave governance/tooling artifacts noted (see Obs. 6) — excluded from the wave's commit boundary by decision.

**G. RATE-LIMIT HYGIENE — PASS.** Suite-wide identity census: `mradar-lab-test:12345`, `mr-wave2-test:12346`, `wf-w3c-test:12347`, `mr-wave3-derived:12348` — all distinct. `test_walk_forward.py` clears `get_settings` cache before+after `create_app()` (order-dependence hygiene); `test_chart_pro_derived_api.py` gained the same hygiene post-audit (Obs. 3 fix). Battery green twice; new modules green in isolation.

## Observations (all LOW / non-blocking)

1. **LOW** — RENKO `atr_period` brick size resolves at the series' last warm-up-complete bar (whole-series parameter resolution); the ATR-mode construction is prefix-stable only for a fixed brick and re-renders wholesale as new bars arrive. Explicitly pinned and disclosed in the module docstring and tests. Accepted w/ rationale; UI note optional.
2. **LOW** — Derived endpoint ignores unknown `params` keys (documented forward-compat); a typo like `bricksize` is silently dropped, mitigated by the response echoing the exact canonical params applied. Accepted.
3. **LOW** — `test_chart_pro_derived_api.py` lacked the settings-cache hygiene its sibling has (asymmetric). **FIXED POST-AUDIT** (module-scope `get_settings.cache_clear()` added; 23/23 still green).
4. **LOW** — KAGI returns `{"points": ...}` while the other four return `{"bars": ...}` — deliberate, documented, test-pinned asymmetry. Accepted.
5. **LOW** — The walkforward endpoint keeps an explicit honest-500 surface (`WALK_FORWARD_FAILED`, "nothing silently dropped") for genuine engine failures; unreachable from malformed input (pydantic gates first). Accepted.
6. **LOW** — Six untracked governance/tooling artifacts (`.claude/`, `CLAUDE.md`, `docs/governance/PROJECT_EXECUTION_STATE.md`, `docs/governance/evidence/`, `scripts/r13_owner_repo_setup.sh`, `scripts/validate_bootstrap_config.py`) sit in the working tree, dated before this wave, with no runtime/test impact. Disposition: deliberately EXCLUDED from the wave's commit boundary (not products of this wave; leaving them untracked preserves their provenance for the owner).
7. **INFO** — Grid symbol-follow sync is honestly non-automatic (applies at user-interaction time, documented in-file and in the UI); crosshair/range syncs re-entrancy-guarded; vendor API calls `typeof`-guarded to degrade to no-op.

## Verdict

| Dimension | Verdict |
|---|---|
| A. Reproduction | **PASS** (2625/1/0 ×2) |
| B. Derived-charts honesty | **PASS** |
| C. Walk-forward no-look-ahead + OOS-once | **PASS** |
| D. Hostile probes | **PASS** (0 500s / ~45 probes) |
| E. Frontend security & honesty | **PASS** |
| F. Gates sweep | **PASS** |
| G. Rate-limit hygiene | **PASS** |

**FINAL: 7/7 PASS — 0 FAILs — publication may proceed.** No HIGH observations; no publication blocker.
