# AUDIT-MR2 — Independent Read-Only Audit Report (MASTER-RADAR WAVE-2)

Audited tree: branch `main`, HEAD `6a79ab7` + the uncommitted WAVE-2 working tree (implementation later committed as `3ec3427`). Read-only: no repo file modified, no git write command, all probes in throwaway `/tmp` scripts. Auditor: independent sub-agent (no implementation role in this wave).

## A. QA / Reproduction — PASS

**A.1 Full battery** — re-run 3×: `2494 passed, 2 skipped, 2 warnings in 18.06s` (also 18.12s / 18.37s with `-rs`) at audit time (before the audit-driven additions below; final wave count 2499/2s).

**A.2 The 2 skips — identified, both environment/repo-state conditional, neither hides a failure:**
1. `tests/test_g2_acceptance_harness.py:271` — `test_substantive_changes_since_rejected`, reason *"parent..HEAD delta is docs-only; use a synthetic case"*. `git diff --name-only HEAD~1 HEAD` = 4 docs files → the committed delta is docs-only, so this test self-skips. Precision: the docs-only-delta guard itself (`test_docs_only_since`) PASSED — it is the complementary substantive-rejection test that skips because the delta is docs-only. The test is git-based (`HEAD~1..HEAD`) and structurally blind to the uncommitted WAVE-2 tree — it cannot hide a wave-2 failure.
2. `tests/test_g2_acceptance_harness.py:367` — `test_gov19_era_bundle_is_compliant`, reason *"GOV-19 bundle not present in this checkout"* (the evidence bundle artifact is absent in this fresh checkout). Manifest-exit coverage is provided by sibling tests (phantom-exit, no-manifest, vacuous-OK — all pass). This also fully explains the skip-count drift vs the wave-1 record ("2401/1s" was recorded in a checkout where the bundle existed).

**A.3 Five honesty-critical claims — all read AND independently re-derived (5/5):**
- (i) Alert staleness refusal (series' own time unit): VERIFIED — 1D ts delta = 86400 (compressed-synthetic unit), window = 3×median = 259200; `as_of = last+window` fresh (equality accepted), `+window+1` → `stale:true, bars_evaluated:0, program_digest:None`; refusal provably happens before compilation.
- (ii) Optimizer IN_SAMPLE + OOS-once: VERIFIED BY INSTRUMENTATION — wrapped `strategy_lab._objective_on_bars`; call log = 4 IS evaluations (140 bars) + **exactly 1 OOS evaluation (60 bars) with the winner's params, post-selection**; `select_then_confirm` structurally ranks IS records only.
- (iii) CSV byte-determinism: VERIFIED — two identical calls → identical 8225-byte bodies and filenames; the json docstring's non-byte-identity claim (canonical `checked_at`) is TRUE and honest.
- (iv) MTF future-bar-append invariance: VERIFIED with an auditor-constructed discriminating scenario (see B.2).
- (v) Hand-computed fixtures: re-derived by hand — CCI (+100/+100/+100/−100/−50 incl. (−2/3)/(1/75)=−50), Williams (−20/−20/−20/−87.5/−62.5/−62.5/+0.0/−50/−50), ADX period-2 (all DI/DX/ADX values ≤1e-9). All test-comment expected values are correct.

**A.4 Pin bumps** — all 5 files diffed in full: only the recorded bumps (tabs 26→29 ×2; SW v3-0-6→v3-0-7 ×3) plus explanatory comments; nothing weakened, no other test files modified.

## B. Quantitative Correctness — PASS

**B.1** Independent from-scratch CCI/Williams implementations over an auditor-constructed 7-bar set: exact match with `ref_cci`/`ref_williams_r` (≤1e-12) incl. warm-up and flat-window conventions.

**B.2** MTF no-look-ahead proven with a discriminating scenario: H1 = [A(ts=0,c=100), B(ts=120,c=999, tail, no close_ts)]; naive open-ts alignment reads 999 at i=2,3; the runtime reads A only from t=120 (`==100.0` → {2,3}; `==999` → ∅). Tail-with-future-close_ts still hidden; future-append invariance bit-identical for declared and undeclared tails; missing/mismatched `ctx.ts` fails closed with documented codes.

**B.3** Tiny `/optimize` grid (seed 42, `fast=[3,5,8]`): winner == best row re-ranked independently by (−objective, param_hash); `total_evaluations == grid size − skips`; budget-capped run honestly reports `budget_exhausted=true` + "grid not fully covered (3/5)… partial"; identical calls → identical `reproducibility_digest`; extreme bounds (1e300–1e308) → 200, finite, no 500.

## C. Security — PASS

**C.1** 14 fresh hostile DSL sources (attribute chains, `__import__('os')…`, semicolon injection, 400-deep nesting, 100000-digit literal, `1e999`, Greek/fullwidth lookalikes, **`ref(close,-1)`/`ref(close,-999999999)` look-ahead**, NUL byte, quote/dunder breakout, 60000-char `++++`): `/validate` → 200 + structured `ok:false` (look-ahead explicitly `LOOKAHEAD_NEGATIVE_REF`); `/alerts/evaluate` → 422 `DSL_ERROR`; **zero 500s, zero tracebacks, zero unexpected triggers**; >8192-char sources rejected at the field constraint.

**C.2** 24 abuse probes on the new endpoints (100KB source, `count=1e6`, negative/zero/501 `max_evals`, non-list grid values, unknown space keys/method/objective, missing oos/budget, OOS split too small, unknown export format, negative staleness, path-traversal/NUL/5000-char ids): all 422/404, no 500, no stack traces. Two intentional non-422s explained (unknown symbol → synthetic series is the pre-existing wave-1 lab contract; unknown body keys ignored by FastAPI default).

**C.3** Source scans of all 9 new/changed app files: clean of socket/urllib/requests/httpx/`eval(`/`exec(`/`compile(`/`__import__`/subprocess/`open(`. The wave-2 `main.py` diff is exactly 2 lines (1 import + 1 include_router); only `data_quality_api` added as a new router; all 11 pre-existing router lines byte-identical.

**C.4** Frontend: 3 new modules + all chart_pro.js diff areas clean of `fetch(`/`WebSocket(`/`eval(`/`XMLHttpRequest`/`document.write`/`localStorage.setItem`; every `innerHTML` interpolation passes through `esc()`; labeling chip uses `textContent`; `node --check` OK on all 7 touched JS files.

**C.5 Gates sweep:** `AI2_ENABLED` default "0" (config.py:111) ✓; `verified=False` hardwired (config.py:284) ✓; `SYNTHETIC_OR_PAPER` ExecutionMode (g2_gate.py) ✓; alert-ops kill switches ENGAGED fail-closed ✓; no ai2 imports under app/api ✓; exactly ONE new router ✓.

## D. Data / Provenance & Honesty — PASS (1 records defect)

**D.1** All 6 new endpoints carry the canonical market_service envelope (`is_live=False`, `live_verified=False`, `state=unavailable`, `trust_level=mixed`) + synthetic notes.

**D.2** Labeling echo derived from `market_service.data_trust_context()`; the live branch is unreachable today; derivation independently re-derived; no hardcoded live claim anywhere in chart_pro.py.

**D.3** DQ outputs: `EXCLUDED_US_EQUITY` listed with `in_default_universe=False` (exclusion reported, not hidden); every market/symbol row `trust_class=SYNTHETIC` (incl. `USEQ:AAPL`, `USEQ:MSNI`, `entitlement=NOT_ENTITLED`); CA/PIT honestly `UNKNOWN`; staleness counted against the injected fixture as_of (never a wall clock).

**D.4** US-individual-equity exclusion: instrument-master tests 57/57 + live probe 32 fixture records → 30 selected / 2 excluded (`USEQ:AAPL`, `USEQ:MSNI`, reason `US_INDIVIDUAL_EQUITY_EXCLUDED`).

**D.5** Frontend honesty: DQ center renders trust classes only from server fields; measure-move labels computed from the chart's own data (no data claims); chip text verbatim server fields; the three new panels carry SYNTHETIC/PAPER honest notes; the legend honestly states REAL_VERIFIED "does not exist in this repo currently"; 29/29 tabs-panels.

**D.6 Records defect — CONFIRMED:** `MASTER_RADAR_EXECUTION_RECORD_2026-11-04.md` §4 (line 70) cites `MASTER_RADAR_INDEPENDENT_AUDIT_2026-11-04.md`, which does **not** exist anywhere in the repo (dangling reference). Correction recorded in the wave-2 execution record; this AUDIT-MR2 report (committed alongside) provides the independent-audit evidence for BOTH waves at the current tree.

## Totals

- Battery: **2494 passed / 2 skipped / 0 failed** at audit time (final wave tree: 2499/2s). New wave-2 tests exactly as claimed.
- FAILs: **none.**
- Observations (9): O1 vacuous OOS assertion; O2 winner-box key drift; O3 MTF close_ts monotonicity hazard; O4 Williams −0.0 assertion cannot distinguish sign; O5 CSV formula-injection guard absent (low: local desktop, synthetic data, attachment); O6 unknown-symbol honesty note desirable; O7 dangling AUDIT-MR1 reference (D.6); O8 STATUS/CHANGELOG battery currency refresh due at commit time; O9 G2 `SUBSTANTIVE_CHANGES_SINCE` runtime path uncovered in this checkout (repo-state-dependent, pre-existing).
- Disposition (recorded in the wave-2 execution record): **O1, O2, O3, O4, O6 fixed in-wave** (with strengthened/new tests); O5, O9 recorded as accepted observations with rationale; O7 corrected honestly in the records; O8 handled by the records commit.

## What was NOT checked
`e2e/` Playwright smoke, `electron/`, `android-app/` surfaces; actual browser/DOM runtime of the new modules (static analysis + `node --check` only); `/optimize` at the 500-eval cap and `budget.time_ms` end-to-end; full wave-1 re-audit beyond the battery; external systems (CI check-runs, G2 evidence bundles — only their absence noted); exhaustive alias cross-check of every forward_center event-row field.
