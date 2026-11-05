# WAVE-F EXECUTION RECORD — Five Product Loops Runtime Surface (2026-11-05)

Directive: MASTER DIRECTIVE — RADAR BOURSE "COMPLETE REMAINING ROADMAP" (§11 WAVE-F):
"实现授权的 Market/Company/Research/Product Intelligence 与 Prediction Feedback"
— audit the five product loops' effective status vs §5 and close the closable
residuals, with no scheduler/egress (R-6/R-9) and no gate change.

Baseline: `origin/main == local == 35e44f8bfbacd5b5f2a3509a6f98931ff85b1617`
(tree `2dfc4bf9…`), fast-forwarded forward-only; WAVE-A..E records re-read.
Baseline battery re-run in THIS checkout before any change:
**2808 passed / 1 skipped / 0 failed in 27.14s — exact match to the WAVE-E record.**

---

## 1. Effective-status audit of the five loops (pre-wave, evidence-based)

| Loop | Directive §5 content | Pre-wave effective status | Missing runtime caller |
|---|---|---|---|
| ① Market Intelligence | auditable source universe, coverage, freshness, monitoring, evidence, alert lifecycle | domain + service + API `/api/ai/market-*` + `/api/v10/dataquality/*` + alert ops `/api/alerts/ops/*` — INTEGRATION-VERIFIED (WAVE-A browser evidence) | loop-consolidated visibility only |
| ② Company/External Intelligence | filings, financials, profiles, publication timing, restatements, currency/unit normalization, source conflicts, PIT | domain (`fundamental_dossier`, `evidence_conflicts`, `document_registry`, `external_intelligence` two-key gates) + tests; NO HTTP surface | dossier/PIT/conflict runtime surface |
| ③ Governed Research | governed hypotheses, deterministic evaluation, independent reproduction, evidence artifacts, lifecycle | domain (`proactive_research` permission machinery, `evaluation_statistics` multiplicity-controlled acceptance, ledger) + tests; NO HTTP surface | status/permission + deterministic evaluation surface |
| ④ Product Intelligence | TabloKhani per-capability benchmarks, measured gaps, privacy-bounded telemetry, on-demand quality audits, evidence-based proposals | domain (`product_audit` charter/telemetry/proposal, `product_audit_records` run records + drift) + tests; NO HTTP surface | on-demand audit run over real capabilities |
| ⑤ Prediction Feedback | prediction registration, pre-registered outcomes, maturity rules, Brier/ECE/calibration, drift, no label leakage | domain (`prediction` registry with leakage guards, `calibration_metrics` Brier/ECE) + tests; NO HTTP surface | registry lifecycle surface |

Closable-within-gates definition used: a runtime surface over ALREADY-TESTED
deterministic domain machinery, fed by DECLARED/SYNTHETIC fixtures, requiring
caller-supplied instants (no wall clock), with zero new external data paths,
zero scheduler, zero egress, zero gate change. Owner-gated residuals (real
filings via Two-Key admission, live data, persistent registries, released
kill-switches) stay owner-gated and are DISCLOSED on every payload — not
worked around.

## 2. Implementation package (explicit file ownership, no overlaps)

| File | Owner | Content |
|---|---|---|
| `backend/app/domain/declared_product_loops.py` | NEW | versioned manifest (5 loops, 11-word vocabulary, owner-gate notes), declared dossiers (2 companies: restatement chain v1→v2, KNOWN/UNAVAILABLE publication, NOT_AVAILABLE facts, dividend action), declared quote boards (2 sources), declared research job (kill-switch ENGAGED, DETERMINISTIC_ONLY, no schedule), declared audit charter + baseline window (measured values pinned) |
| `backend/app/api/product_loops_api.py` | NEW | `/api/v10/productloops` — 10 routes: manifest; dossier/{symbol} (PIT cutoff REQUIRED, live `detect_quote_conflicts`); research/status (LIVE `effective_research_run_permission` per request + AI-2 gate posture); hypotheses/evaluate (`adjusted_acceptance`, digest-bound replay); product-audit/run (3 REAL in-process probes: tablokhani rows via `get_tablocastic`, dataquality coverage IRAN_TSE, chartpro candles 120; `compare_windows` vs declared baseline; advisory proposals only); predictions register/outcome/list/evaluate/calibration (`PredictionRegistry` + `build_calibration_record` with prediction binding) |
| `backend/app/main.py` | additive 2 lines | router registration with wave comment |
| `frontend/index.html` | additive | tab #30 «🔄 حلقه‌های محصول» + `tab-loops` panel (5 sections, trust text from server fields) |
| `frontend/js/modules/render/product_loops_ui.js` | NEW | bind-on-demand module; api() only; esc() everywhere; no eval/Function/dynamic-import; caller-supplied instants only |
| `frontend/js/main.js` | additive 1 line | import |
| `frontend/sw.js` | bump | v3-0-13 → **v3-0-14** + precache product_loops_ui.js |
| 8 pin test files | pins only | tabs 29→30 (×5) + sw v3-0-14 (×6) with recorded counter-pin comments |

## 3. Tests — +18 = battery 2826/1s/0f exact

`backend/tests/test_product_loops_api.py` (18 tests):
manifest vocabulary/5-loops/trust; dossier PIT early/late cutoff with
excluded-count disclosure + UNAVAILABLE-publication bucket; live conflict
detection (فملی 1 conflict / فولاد 0); hostile instants/symbols typed 4xx;
research status live refusals (`kill_switch_engaged`,
`missing_provenance:*`) + AI-2 disabled posture; BONFERRONI exact adjustment
(0.01→0.02 ACCEPTED, 0.5→1.0 REJECTED) + digest-stable replay + NONE-over-one
REFUSED verdicts + alpha-out-of-range; audit run == declared baseline
exactly (60/8/120 STABLE, NO_DRIFT_DETECTED) + repeat determinism +
hostile windows (end<start, pre-baseline, naive instant) + charter with NO
SCHEDULED cadence + telemetry boundary (aggregation_only, repurposing
locked False); prediction lifecycle (pre-maturity evaluate →
`prediction_not_matured`, duplicate outcome refused, list maturity by
caller instant); registration guards (duplicate id, horizon order,
outcome-predates-registration, unknown prediction); calibration Brier/ECE
exact (0.9/1.0 → 0.01/0.1) + non-binary refusal + immature-prediction
refusal + **OUTCOME_AFTER_MEASUREMENT_REFUSED** (router-level no-look-ahead
guard added during the wave) + 10-route prefix scoping + gates + honesty
envelope on every payload.

Full battery after the wave: **2826 passed / 1 skipped / 0 failed in
30.36s = 2808 + 18 exact.** pyflakes clean; node --check green; static
validator green (tabs 30/30).

### 3.1 Pre-publication integration findings (found & fixed in-wave)

1. **Rate-limit identity interference:** the suite's default TestClient
   identity shared the global 150/min budget with other suites → 11
   cross-suite failures (my 3 + security/wp5/ws_harden1 8). Root-caused,
   fixed with a distinct client identity (the recorded WAVE-B pattern);
   battery returned to exact 2808+18 with zero other-suite impact. Without
   my file, the battery is byte-identical to the recorded 2808/1s/0f.
2. **Settings-cache residue:** same suite poisoned by the AUDIT-MR3 Obs.3
   get_settings-cache class; adopted the recorded autouse hygiene fixture.
3. **Binary-outcome contract:** `parse_pairs` refuses float 1.0 (int 0/1
   only); the router converts integral floats to ints and lets the engine
   refuse everything else — pinned by test.
4. **Look-ahead gap closed:** outcome observed AFTER the measurement
   instant was not engine-guarded; the router now refuses
   (`OUTCOME_AFTER_MEASUREMENT_REFUSED`) — pinned by test.

## 4. Runtime browser verification (real server, real browser, preview origin)

- Backend restarted with the WAVE-F code; `/api/health` 200; manifest via
  the preview origin 200.
- Tab registry: **30 tabs** incl. «🔄 حلقه‌های محصول»; activating the tab
  fetches `/api/v10/productloops/manifest` (200) and renders 5 loops with
  the manifest version badge.
- Dossier panel (فملی, cutoff 2025-12-25): renders the declared dossier
  with the `SYNTHETIC/DECLARED (repo fixture; not real filings)` trust
  label and honesty text.
- Research panel: renders `DISABLED_OWNER_GATED`, AI-2: false, live
  refusal tags (`kill_switch_engaged`,
  `missing_provenance:started_at_utc/finished_at_utc/dataset_version`).
- Audit panel (window 2026-11-05T00:00Z→01:00Z): **NO_DRIFT_DETECTED**
  with all three metrics STABLE at the declared baseline (120/8/60) and a
  run digest.
- Prediction panel: register → outcome → list (registry version 2,
  MATURED) → calibration **Brier 0.01 · ECE 0.1 · n=1** rendered.
- Zero fresh console errors/page errors after the fix below.
- Evidence screenshots: `download/wave_f_loops_tab_manifest.png`,
  `download/wave_f_loops_tab_panels.png`.

### 4.1 Preview-transport finding (outside the repo, recorded honestly)

The environment's preview transport (a minimal verbatim proxy outside the
audited repository, rebuilt this session after the sandbox recycle) initially
STRIPPED the request Host header; the backend's CSRF origin check compares
Origin against Host and therefore blocked same-origin POSTs through the
preview (403). The transport was corrected to forward the original Host
(verbatim reverse-proxy behavior); POSTs then return 200. The repository's
CSRF middleware is CORRECT and unchanged — the defect was in the sandbox
transport only, and the finding is recorded here because it was observed
during runtime verification.

## 5. Governance gates (re-verified post-wave)

`AI2_ENABLED=0` (config.py:111 — asserted by test), verified=False posture,
SYNTHETIC_OR_PAPER, no scheduler (every loop is caller-initiated; the
charter declares NO SCHEDULED cadence; the research job kill-switch is
ENGAGED and its LIVE permission check refuses), no external egress, no live
data path, no purge path, no runtime caller added to any owner-gated edge
(external source admission stays fail-closed R-3/R-7 Two-Key; AI-2 stays
disabled), INSTALL NOT ISSUED. Global completion stays **NOT CALCULATED**.

## 6. Owner-action register (deltas)

- OWNER-ACTION VERCEL-HOUSEKEEPING — unchanged (still owner-credentials-gated).
- NEW disclosure: the prediction registry is process-local; durable
  persistence is available as a follow-up but needs an owner decision
  (disclosed on every payload via `persistence_note`).
- Unchanged: INSTALL R-1, target-machine R-2, live posture R-3, AI
  enablement, scheduler release (R-6), external notification (R-9),
  persistent approval log.

## 7. Publication

Forward-only single implementation commit (code+tests+frontend+pins) then a
records-only commit (this record + matrix WAVE-F addendum + Persian §41 +
STATUS/CHANGELOG/INDEX). CI exact-SHA evidence to be appended post-push per
WS1 §13 (GitHub API rate-limit window permitting, same as WAVE-C/D).
