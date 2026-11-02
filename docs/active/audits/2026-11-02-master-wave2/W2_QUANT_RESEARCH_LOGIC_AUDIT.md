# W2-QUANT — P3 Research-Quality Layer: Quantitative / Financial Logic Audit

- **Task ID:** W2-QUANT (P3 quantitative logic audit)
- **Repo:** `/home/z/my-project/RADAR_BOURSE/repo` @ `7c225cb1ce2771473f1f646be9c4282348ea7657` (main)
- **Mode:** STRICTLY READ-ONLY. No repo file modified, no git state changed (verified post-audit; see §10).
- **Scratch probes (outside repo):** `d1_mtp_audit.py`, `d234_holdout_regime_surviv_audit.py`, `d56_golden_determinism_audit.py` (same directory as this report).
- **Interpreter:** `/home/z/my-project/RADAR_BOURSE/repo/.venv/bin/python` (3.12.16). numpy 2.2.1 available; statsmodels/scipy NOT installed (see §9 Not-verified).

**Verdict (one line):** The P3 research-quality layer is mathematically correct and honest — Bonferroni/BH are exactly standard, all four survivorship verdicts and every holdout/regime refusal behave as documented, the GS-2026-11-02 Golden Set is fully recomputable from its own synthetic mock bars with no production-market claim anywhere, and the only two findings are LOW-severity diagnostics/hardening items.

---

## 1. Multiple-testing math — `backend/app/domain/evaluation_statistics.py`

### 1.1 Bonferroni — VERIFIED CORRECT
`bonferroni_adjust` (evaluation_statistics.py:85-95): `adjusted_i = min(1.0, p_i * m)`, input order preserved, empty input → empty tuple. This is the exact standard Bonferroni adjusted p-value; the arithmetic is dyadic (one integer multiplication + one `min`), matching the module's "exact arithmetic, no rounding" claim (docstring lines 29-35, 86-92). Input validation refuses non-numeric / non-finite / out-of-range p-values with deterministic reason codes (`_validated_pvalue`, :72-82).

### 1.2 Benjamini-Hochberg — VERIFIED CORRECT (step-up adjusted-p semantics, incl. ties and monotone pull-down)
`benjamin_hochberg_adjust` (:98-128):
- :116 stable ascending sort (`sorted(range(m), key=lambda i: pvs[i])`) — ties keep input order, so tied p-values occupy consecutive ranks in index order.
- :119-124 accumulates the running minimum **from the largest rank downward**: `raw_j = p_(j) * m / j` (:121), `running = min(running, raw_j)` started at 1.0.
- :124 clips at 1.0 per element; :125-128 scatters back to input positions.

This is exactly the standard BH step-up adjusted p-value, `adjusted_(j) = min(1.0, min_{k>=j} p_(k)·m/k)` — identical to R's `p.adjust(method="BH")` (`pmin(1, cummin(n/i * p[o]))[o]` with descending order `o`; hand-decoded and cross-checked). Starting the running min at 1.0 then clipping (docstring :108-110) is exactly equivalent to clip-after-cummin: `min(1.0, x)` clipped to 1.0 == `x` clipped to 1.0.
- **Ties:** for a tie group at ranks j..j+t-1, `raw` is decreasing in rank, so the downward running min gives **every tied member the same adjusted value** — identical to R's behavior (verified: `[0.03,0.03,0.03]` → single common value; mixed-tie case `[0.5,0.01,0.5,0.2,0.01]` matches reference exactly).
- **Monotonized-downward pull-down:** hand case `[0.01, 0.5, 0.51]` → raw = (0.03, 0.75, 0.51) → adjusted = **(0.03, 0.51, 0.51)** — the 0.75 at rank 2 is correctly pulled down to 0.51. Verified.
- **m=1:** identity; **empty:** `()`; **0/1 boundaries:** exact.

### 1.3 Independent reference implementation & agreement — **AGREEMENT: 100%, ZERO MISMATCHES**
Scratch probe `d1_mtp_audit.py` implements the reference from the textbook definitions via a deliberately different code path ((p,index) tuple-sort with index tie-break; running min started at +inf; clip at end). Results on seeded randomized p-grids (`numpy` Generator, seeds 20261102/777/42/43):

| Check | Scope | Result |
|---|---|---|
| BH + Bonferroni exact float equality (repo vs reference) | 400 grids, m=1..48, 4 distributions (uniform / heavy-tie / heavy-tail-small / boundary-mixture with exact 0.0/1.0) | **PASS, 0 mismatches** |
| repr-identical (exact IEEE double, not merely `==`) | 200 grids | PASS |
| Input-order invariance (multiset of adjusted values) | same 400 grids | PASS |
| **Procedure equivalence:** `{i: adj_i <= q}` == BH step-up rejection set defined by `k* = max{i: p_(i) <= (i/m)·q}` (monotone step-up, ties share fate) | 300 grids × q ∈ {0.01, 0.05, 0.10, 0.25} | **PASS** |
| Rejection set closed under smaller p (monotone boundary) | 100 grids | PASS |
| Adjusted values monotone nondecreasing over sorted p | 200 trials | PASS |
| Deterministic edge cases (ties, pull-down, empty, m=1, zeros, ones, invalid inputs refused with reason codes) | 22 hand cases | PASS |
| Order-invariance of `adjusted_acceptance` family verdicts | 24 permutations | PASS |

The procedure-equivalence check is the strongest evidence: the code's adjusted p-values implement **exactly** the BH step-up *procedure* (`k_i = max{i: p_(i) <= i/m·q}` form), not merely a look-alike formula. No third-party BH library existed in the venv for a second external reference (statsmodels/scipy absent) — see §9.

### 1.4 NONE-method refusal in mixed batches — VERIFIED
`adjusted_acceptance` (:178-267) groups members by `family_id` (first-appearance group order; dict insertion order is deterministic, :210-215). For method NONE:
- family size m>1 → every member gets `verdict="REFUSED"`, `accepted=None`, `adjusted_pvalue=None`, reason `UNADJUSTED_ACCEPTANCE_IS_FORBIDDEN_FOR_FAMILIES_OVER_ONE`, `unadjusted=False` (:218-234) — fail-closed honesty via DATA, not exceptions.
- family size m==1 → allowed with `unadjusted=True` and reason `UNADJUSTED_SINGLE_ATTEMPT` (:239-245, :243-245).
Verified on a mixed batch (family F1 with 3 attempts + family F2 with 1 attempt): size-3 refused, size-1 allowed with the honesty flag. Acceptance rule is exactly `adjusted <= alpha` (never rounded); `alpha` must lie strictly in (0,1) — 0.0/1.0/nan/inf/negative all refused with `alpha_out_of_range` (:202-207). BONFERRONI and BENJAMIN_HOCHBERB wiring per family verified numerically (F1 p=(0.01,0.04,0.03) → Bonf (0.03,0.12,0.09); BH matches reference exactly).

### 1.5 FP/FN accounting — VERIFIED
`confusion_counts` (:320-345) and `precision_recall_fp_rate` (:348-381): 500 random (signal, matured) sequences vs brute-force reference — exact integer agreement. Undefined rates are `None` + reason codes, never faked 0.0 (e.g., no signal negatives → `false_positive_rate=None` with `FALSE_POSITIVE_RATE_UNDEFINED_NO_SIGNAL_NEGATIVES`); defined-but-zero rates (0/1) are honestly 0.0. `format_rate` (:384-400) is the only rounding point, `None`-passthrough verified.

**D1 findings: none.** (All probe "failures" encountered during the audit were errors in my own probe expectations, hand re-derived and corrected; each correction is documented in the probe file comments.)

---

## 2. Holdout logic — `backend/app/engines/holdout.py`

### 2.1 Split boundaries / no leakage — VERIFIED
- `split_holdout` (:95-135): holdout is the TAIL, `holdout_count = int(n·fraction)` (:128), `insample = bars[:-h]`, `holdout = bars[-h:]` (:133-134) → **train indices strictly < test indices**; segments partition the input; verified `ins[-1].ts < hold[0].ts`.
- `require_sorted_unique_bars` (:68-92): strictly increasing timestamps enforced (`UNSORTED_BARS` on decrease, `DUPLICATE_TIMESTAMPS` on repeat); bool/non-numeric/non-finite `ts` refused (`bar_timestamp` :52-65).
- Fraction domain: open interval (0, 0.5) — 0.0, 0.5, 0.75, negative, nan, inf, bool, str all refused with `HOLDOUT_FRACTION_NOT_IN_OPEN_INTERVAL` (:116-124). Empty bars refused; `floor(n·f) < 1` → `HOLDOUT_SEGMENT_EMPTY` (:129-132) — a zero-bar holdout can never be attested.
- IEEE floor semantics are **documented and honest** (:28-31): `int(1000·0.29)` = 290 (IEEE product rounds up to exactly 290.0), `int(3·0.1)` = 0 (0.3000…4) → refused. Deterministic for fixed inputs. NOT-A-DEFECT.

### 2.2 Attestation boundary checks — VERIFIED STRICT
`assert_no_selection_on_holdout` (:186-245): insample last ts **<** boundary (`>=` raises, :222-225); holdout first ts **>=** boundary (:226-229); selection window end **strictly <** boundary (`>=` raises `SELECTION_WINDOW_OVERLAPS_HOLDOUT`, :230-234) — "touching the boundary is already a violation" is true as documented (:205-207). Empty segments refused (:216-219); boundary numeric/finite checks (:209-215). Attestation fields (first/last ts, counts, boundary) verified consistent and complete on the happy path. Since `insample_last < boundary <= holdout_first` is implied, cross-segment ordering is guaranteed by construction.

### 2.3 The F1 finding (cross-field consistency not type-enforced) — CONFIRMED, honestly rated
- **Confirmed:** `HoldoutAttestation` (:166-184) carries **no cross-field `model_validator`** — a scratch probe directly constructed an attestation with `insample_last_ts=999.0 > holdout_boundary_ts=100.0` and `holdout_bar_count=0` (both impossible from the constructor) and the model accepted it with `isolated=True`.
- **Type-pinning is real:** `isolated: Literal[True]` is enforced — constructing with `isolated=False` is refused (verified; also pinned by tests/test_p3_quality_validation_holdout.py:215-217).
- **Constructor paths (adversarial read):** the ONLY `HoldoutAttestation(...)` construction site in `app/` is holdout.py:235, inside `assert_no_selection_on_holdout` after all checks pass. No other app/test code mints attestations (grep across backend: only holdout.py:235 + the two test files). The module docstring (:24-26) states exactly this guarantee.
- **Exploitability rating: LOW.** No code path can emit a false attestation; exploitation requires a *future caller* to bypass the documented API and hand-construct the frozen model with lying field values. This is a constructor-path honesty contract (stated in the docstring), not an active defect.
- **Classification:** NOT-A-DEFECT as recorded (prior record accurate); **optional hardening AUTHORIZED-REPO-SIDE, LOW**: add a cross-field `model_validator` so the model itself is self-certifying (defense-in-depth against future callers).
- Minor: `SelectionWindow` permits a zero-length window (end == start; only end < start refused, :159-163) — harmless given the strict boundary check; NOT-A-DEFECT.

---

## 3. Regime slices — `backend/app/engines/regime_slices.py`

- **Closed vocabulary:** `RegimeLabel` Literal (:47-53) + `REGIME_LABELS` tuple (:55-61); tuple-form windows checked against the tuple (:125-128, `UNKNOWN_REGIME_LABEL`); `RegimeWindow` records are pydantic-Literal-enforced (:79). Free-form labels refused (verified with "PUMP"). VERIFIED.
- **Overlap refusals:** windows sorted by `(start_ts, end_ts, label)` (:233); any `current.start < previous.end` refused `OVERLAPPING_REGIME_WINDOWS` (:234-240). Verified: nested, exact duplicate, partial overlap, and same-start containment are ALL refused; touching half-open windows (`current.start == previous.end`) correctly accepted; bar exactly at `end_ts` belongs to the next window (verified). Zero/negative-length windows refused (`INVALID_WINDOW_BOUNDS`, :143-147).
- **Determinism guard:** caller aggregate called exactly twice per non-empty window; any drift refused `AGGREGATE_NOT_DETERMINISTIC` (:154-168); non-tuple/bool/non-callable refused; empty metric tuples allowed (:158-187, verified).
- **Module determinism:** same input in different window order → byte-identical reports (verified via sorted-key JSON dumps). Gaps (`gap_labels`) and uncovered bars (`uncovered_bar_count/first/last`) surfaced, never silently dropped (verified counts).
- **FINDING (AUTHORIZED-REPO-SIDE, LOW):** a *deterministic* aggregate returning NaN is refused with `AGGREGATE_NOT_DETERMINISTIC` instead of `AGGREGATE_RETURN_NON_FINITE`, because the equality guard `first != second` (:167) is always true for NaN-containing tuples; `inf` (which compares equal) correctly gets `AGGREGATE_RETURN_NON_FINITE`. Behavior is fail-closed in every case and the docstring's refusal list (:227) promises both codes without specifying which fires for NaN — only the diagnostic reason code is misleading for NaN. Suggested fix: check finiteness independently of (or before) equality. No correctness impact.
- Observation (NOT-A-DEFECT): uncovered-bar scan (:286) is O(n·m) — performance note only.

---

## 4. Survivorship guard — `backend/app/domain/survivorship_guard.py` (adversarial read)

- **Four verdicts reachable (all verified):** OK (:227-229), SURVIVORSHIP_BIAS_RISK (:221-222), ANACHRONISTIC_MEMBER (:223-224, both via listed-after-as_of member AND via `snapshot.as_of_ts > evaluation_as_of_ts` :206-209), INCOMPLETE_UNIVERSE (:225-226). Minimal universes work (single-member OK verified at the `listed_from == as_of` boundary).
- **Cannot silently pass a missing member (adversarial):** the expected-member loop (:195-203) classifies EVERY registry symbol absent from the snapshot: `listed_from > as_of` → correctly skipped (did not exist yet); `delisted_at <= as_of` → `excluded_delisted`; **else → `missing`** — this catches the tricky case "delisted AFTER the evaluation point and missing" as INCOMPLETE_UNIVERSE (verified), so no lifecycle combination escapes. Verified: a member still listed at eval + missing → INCOMPLETE; a member listed after eval + missing → correctly not flagged.
- **Precedence cannot hide findings:** when bias + incompleteness both fire, headline = SURVIVORSHIP_BIAS_RISK but `missing_symbols` remains populated (:120-122, :231-240) — verified.
- **Fail-closed refusals (all verified):** snapshot member absent from registry → `SNAPSHOT_MEMBER_NOT_IN_EXPECTED_UNIVERSE` (:169-174); conflicting lifecycle record → `CONFLICTING_MEMBER_RECORD` (:175-184); duplicate expected symbol → `DUPLICATE_EXPECTED_SYMBOL` (:162-167); duplicate snapshot symbols → model validator `duplicate_symbol_ids` (:96-102); `delisted < listed` → `delisted_before_listing` (:81-85); non-numeric/non-finite/bool `as_of` refused (:127-133, verified).
- Boundary semantics match the docstring exactly (`exists iff listed_from <= as_of`; `delisted-before/at iff delisted_at <= as_of`) — verified incl. an epsilon-straddle case (`listed_from = as_of + ε` → anachronistic).
- `known_from_start` mismatch alone is tolerated (documented informational provenance, :69-71) — verified; it is deliberately excluded from the conflict check (:175-184 compares only `listed_from_ts`/`delisted_at_ts`).
- **D4 findings: none.**

---

## 5. Golden Set — `backend/app/domain/golden_set.py` + fixture `GS-2026-11-02` — **RECOMPUTE VERDICT: PASS**

Fixture: `backend/tests/fixtures/golden_set/golden_set_v1.json` — version `GS-2026-11-02`, schema `golden_set_v1`, 3 cases (BACKTEST / WALK_FORWARD / FORWARD_TEST), each bound to the same 3 hand-written 40-bar synthetic paths (GSAAA/GSBBB/GSCCC).

### 5.1 Digests independently reproduced
- Scratch canonical-JSON + SHA-256 reimplementation (NO `app` import; sorted keys, `(",", ":")`, ASCII — mirroring `canonical_json` :66-77) reproduces the embedded `version_sha256` = `acefd2e7baf47d55050cb1c7f8496745847fcb10a91d71b0f4d38d14231d7850` — the digest construction is not self-referential.
- Raw file digest = `d1560dfadc1f8136ca805501dc68a5c00d86bcbd668aa9854414b31902bdc214` — matches the independent validation-layer pin (test_p3_quality_validation_golden_set.py:45-48).
- Each case's `bars_sha256` recomputed from that case's own `bars` — all three match (tamper binding intact; parse-time refusal verified in-repo at golden_set.py:263-268).
- `created_at_utc` (`2026-11-02T00:00:00+00:00`) is an explicit constructor parameter and is EXCLUDED from the cases digest (golden_set.py:148-151, 173-176) — verified structurally (digest covers only `case.canonical_payload()`).

### 5.2 Exact recomputation from the fixture's own bars (deterministic engine)
Recomputed exactly as the pinned engine block declares (`entry_filter "entry_score >= 70"`, execution `commission 0.5% / TP 4% / SL -3% / max_hold 6 / position 10% / capital 1e8`, WFO train 15/test 8/step 8, forward boundary ts 28.0, `data_trust_state=mock`):
- **Every pinned key is EXACTLY recomputable — all 24 pinned floats repr-identical (exact IEEE-754, not approx):**
  - BACKTEST: `total_return 0.294, win_rate 54.55, average_return 0.268, median_return 3.403, profit_factor 1.094, sharpe_ratio 0.039, maximum_drawdown 1.388`, count `trades 11`, flag `mode=strategy`. ✓
  - WFO: summary `avg_window_total_return 0.095`, counts `windows 3 / total_oos_trades 5`, flag `mode=walk_forward`, plus all 3 per-window metric tuples exact. ✓
  - FORWARD_TEST: 7 metrics incl. `total_return -0.978, win_rate 33.33`, count `trades 3`, flags `mode=forward_test / forward_boundary_type=timestamp`. ✓
- `verify_case` passes on the pinned-key projection; fed the FULL engine metrics map it reports `EXTRA_METRIC:*` for unpinned keys — **documented tamper-evidence design** (golden_set.py:205-207, 218-220: "missing and extra keys are reported"), NOT a defect.

### 5.3 Independent hand-computation of the first trade (guards against self-consistent-but-wrong engine)
From raw fixture bars, independently: first GSAAA signal at index 2 (ts 3, entry_score 80) → entry next bar ts 4 @ 102.0; close-only TP walk hits at ts 8 (close 107 ≥ threshold 106.08, engine-documented close-only semantics: trigger on close, **fill at the close** — backtest.py:147-160) → gross (107−102)·qty, commission both legs (50,000 + 52,450.98 = 102,450.98) → **net_pnl 387,745.10, ret_pct 3.8775** — matches engine `trades_sample[0]` exactly on symbol, entry/exit ts, entry/exit price, exit_reason, net_pnl, ret_pct.

### 5.4 Self-labeling and trust state — CONFIRMED
- `engine.data_trust_state = "mock"` ✓ (fixture engine block).
- `notes`: "Hand-written deterministic price paths; expected values pinned from one deterministic engine run (double-run equality verified). No superiority claim over any external system is made or implied." ✓
- No "real market"/"live market" text anywhere in the fixture (also pinned by test_p3_quality_validation_golden_set.py:297-301 so it cannot silently drift).
- Runtime honesty labels on the engine path: backtest.py:361-366 appends "…not live-market proof / not suitable for performance claims" warnings for mock/synthetic/stale/unavailable trust states.

### 5.5 No production-market evidence claimed anywhere (grep sweep)
- `rg -i "real market|live market"` over `backend/app/domain/` + `backend/app/engines/`: only NEGATIONS (market_session.py:6 "NOT live market data"; data_quality.py:25 "not validated live market data"; backtest.py:362 "not live-market proof").
- `docs/active/*` mentions of "real market" are all owner-gated BLOCKED items (REM1_AI2A_IMPLEMENTATION_RECORD.md:61; AI2_G2_READINESS_EVIDENCE_PACKAGE.md:97 "BLOCKED … is_verified_live cannot be minted"; P5P6_ALERT_LIFECYCLE_SCOPE_DERIVATION.md:34 "externally blocked"). **No doc claims the Golden Set or any TabloKhani artifact rests on production-market evidence.**
- Wording observation (NOT-A-DEFECT, LOW): CHANGELOG.md:30 "metrics pinned from real runs" and STATUS.md:12 "metrics from real backtest/WFO/forward runs" — "real" here means *actually-executed engine runs* (same sentence: "hand-written deterministic paths"), not real market data; suggest rewording to "actually-executed engine runs" to preclude misreading.

---

## 6. Backtest/WFO engine determinism — `backend/app/engines/backtest.py`

### 6.1 Double-run byte-compare — VERIFIED
Probe `d56_golden_determinism_audit.py`:
- **Same process, reused `data_trust` context:** full reports of run 1 vs run 2 (all three entry points, on the Golden Set fixture bars) are **byte-identical** (zero JSON diffs, sorted-key canonical dumps).
- **Two fresh subprocesses with different `PYTHONHASHSEED` (0 vs 12345):** outputs byte-identical **except exactly one field per case: `data_trust.checked_at`** (exhaustive diff walk over the full JSON tree — no other path differs). Metric/count/flag/trade/equity content is bit-stable across processes and hash seeds.
- Dict iteration is insertion-ordered (Python 3.7+), all sorts are stable with explicit keys, `max`/`min` first-wins — no order-dependent floating-point accumulation found in the research path.

### 6.2 Wall-clock / RNG inventory on the research path (grep `time.time|datetime.now|random` over `app/engines/` + `app/domain/`), each classified:

| Locus | What it is | Classification |
|---|---|---|
| `backtest.py:183` `time.time()` in `synthesize_price_path` | synthetic-fallback path generator (mode="synthetic"; docstring :179-180: "must never be used as proof of live performance"); RNG at :186 is **seeded** (`_rng`, md5(seed+symbol), :99-100) → deterministic series, wall-clock only in the synthetic `ts` values | Synthetic/demo generator; NOT on the deterministic research/recompute path. Acceptable; not injected-clock but clock confined to synthetic timestamps |
| `backtest.py:252` `time.time()` in `paths_from_store` | live-store tick windowing (live integration path only) | Live-ops; not research path |
| `app/core/config.py:257` `checked = _coerce_ts(checked_at) or time.time()` inside `build_data_trust_context` | **INJECTABLE** (`checked_at` parameter exists, config.py:237) with wall-clock default; lands ONLY in the `data_trust` provenance block of reports; Golden Set pins deliberately exclude it | Injected-clock pattern OK (parameter exists); default wall-clock — metric determinism unaffected (proven by 6.1) |
| `trade_detail.py:25` RNG seeded `int(time.time()//60)` | minute-bucketed seed → NOT reproducible across minutes; also :191 `datetime.now()`, :223/:282 `time.time()` | Mock trade-tape presentation engine; NOT research path. Observation: must never be reused for research without redesign |
| `big_moves.py:64,125` `time.time()`; `:73` seed `hash(s.l18) ^ int(back) ^ int(now//300)` | `hash()` is PYTHONHASHSEED-randomized across processes + 5-minute bucket → cross-process non-reproducible **by design**; confined to `ensure_flow_history` mock/demo bootstrap, guarded `source_hint in {mock, mock_fallback, synthetic, bootstrap}` (:60), writes snapshots labeled "bootstrap" (:87-92). `compute_big_moves` itself has NO RNG, only wall-clock windowing vs store ticks | Live/demo data-prep; not research path |
| `screener.py:68` `datetime.now(timezone.utc)` | `MarketOverview.as_of` provenance stamp only | Live-ops provenance; not research path |
| `options.py:102`, `fundamental.py:26-28` | md5-seeded RNG for synthetic option/fundamental data — deterministic per symbol | Synthetic generators (labeled); not research path |
| `domain/events.py:12` `time.time()` + uuid | runtime event bus (used by api/excellent.py, main.py) | Live-ops; not research path |
| `domain/market_session.py:27` `datetime.now(TEHRAN)` | live session state | Live-ops |
| `chart_builder.py:22,72,159` `or time.time()` | rendering fallback stamps | Live-ops |

- The P3 research/evaluation modules themselves are clean: `evaluation_statistics.py` (no time/random; docstring :37-39), `golden_set.py` (datetime only as an explicit parameter type; `created_at_utc` never read from a clock), `holdout.py`, `regime_slices.py`, `survivorship_guard.py` — no wall-clock, no RNG.
- **D6 verdict: offline determinism of the research layer CONFIRMED** — metric-level always; full-report level given a fixed trust context; the single cross-process variable is the documented, injectable `checked_at` provenance stamp.

---

## 7. Provenance & claims honesty

- **C1–C8 inventory loci verified UNCHANGED at HEAD** (exact file:line AND exact content):
  - C1 `README.md:3` ✓ (بهینه‌تر از tablokhani.com), C2 `frontend/js/modules/render/watchlist_excellent.js:2` ✓, C3 `…watchlist_excellent.js:53` ✓ (user-visible UI), C4 `docs/archive/phase-reports/INSPECTION_REPORT_V09_ULTIMATE_RUTHLESS.md:1` ✓, C5 `docs/archive/phase-reports/CHART_EXCELLENT_V08.md:73` ✓, C6 `docs/archive/phase-reports/summary-of-tablokhani-videos.md:28` ✓, C7 `…summary-of-tablokhani-videos.md:138` ✓, C8 `README.md:65` ✓ (similarity, not superiority).
  - Status per `docs/active/TABLOKHANI_CAPABILITY_MATRIX.md` §4 (:118-125) and §5 (:211 "Owner-gated: C1–C3 (and archive items C4–C6) remain in place pending the owner's") — all remain **OWNER-GATED**; the matrix is the evidence-based, no-superiority inventory (header :1, §1 :15, §3 :46).
- **Module-level posture:** evaluation_statistics.py:38-39, golden_set.py:9-10 and the fixture notes all carry explicit no-superiority statements; backtest.py:475 notes and :479-489 quant_safety block document look-ahead policy conservatively.
- **Recent records posture:** HEAD commit chain — db69dcc "TabloKhani capability matrix — verifiable in-repo evidence only; no superiority claims"; 7c225cb MASTER-WAVE-1 records contain no capability claims. Confirmed.

---

## 8. Test suites (run READ-ONLY; `/home/z/my-project/RADAR_BOURSE/repo/.venv/bin/python -m pytest`, cwd `backend/`)

**Command:** pytest over the 12 files below. **Result: 140 passed, 0 failed, 0 skipped, 0.80s** (offline per tests/conftest.py DATA_SOURCE=mock pin).

| Suite | Tests |
|---|---|
| test_p3_quality_validation_evaluation_statistics.py | 12 |
| test_p3_quality_validation_holdout.py | 6 |
| test_p3_quality_validation_regime_slices.py | 5 |
| test_p3_quality_validation_survivorship_guard.py | 6 |
| test_p3_quality_validation_golden_set.py | 5 |
| **P3 quality validation subtotal** | **34** (matches the directive's "(34)") |
| test_evaluation_statistics.py | 19 |
| test_golden_set.py | 16 |
| test_holdout.py | 19 |
| test_regime_slices.py | 18 |
| test_survivorship_guard.py | 16 |
| test_backtest_framework.py | 14 |
| test_strategy_framework.py | 4 |
| **Related subtotal** | **106** |
| **TOTAL** | **140 passed** |

**Indirect-only coverage of tablocastic / screener / big_moves — CONFIRMED PRECISELY (the prior backlog item is accurate):**
- `tablocastic.py`: **zero** test imports of `compute_tablocastic`/`rank_tablocastic`; all 11 grep hits in tests/ are mock payload dict-keys (e.g., test_ai_service.py:35, test_p3_81_ai_contracts.py:39, test_refresh_false_fresh.py:71,104,132) — no engine invocation.
- `screener.py`: **zero** test references (no test imports `app.engines.screener`).
- `big_moves.py`: exactly ONE direct assertion — `flow_coverage_sec` returns 0.0 on an empty store (test_metrics.py:13,20); `compute_big_moves`/`ensure_flow_history` never directly tested.
- How they ARE exercised (indirect-only): `screener.analyze_market` via `GET /api/analyze` (analysis_service.py:17) in test_p3_82_ai_path_trust.py:11,26; test_p3_87_integration_audit.py:162; test_p3_81_ai_contracts.py:160; test_data_trust_hardening.py:80,95; test_p3_77_local_hardening.py:232. `tablocastic.compute_tablocastic/rank_tablocastic` and `big_moves.ensure_flow_history/compute_big_moves` via `MarketService.refresh(force=True)` (market_service.py:339-347, 409-426) in test_refresh_false_fresh.py (stub provider, refresh at :90,:117,:149,:154), test_refresh_degraded_token_concurrency.py:57, and test_data_domain.py:7.
- This matches the repo's own record, TABLOKHANI_CAPABILITY_MATRIX.md:96 (row 23): "Tests: none dedicated; service wiring exercised via test_refresh_false_fresh.py" — the backlog item is CONFIRMED, not understated.

---

## 9. Not verified (honest scope limits)

1. **No third-party BH reference available:** statsmodels/scipy are not installed in the venv, so agreement is against my own independent implementation + a procedure-equivalence proof (§1.3) + a hand-decode of R's `p.adjust` algorithm — not against R/statsmodels executed output.
2. **Full engine reimplementation not performed:** the entire backtest engine (all 11 trades, WFO/forward windows) was not re-written from scratch; verification = all pinned values recomputed via the engine + digest bindings + ONE trade fully hand-computed from raw bars (§5.3). A systematically wrong-but-deterministic engine fully consistent across all three cases cannot be fully excluded by this alone (mitigated by the hand check and by the engine's conservative-documented TP/SL semantics).
3. **Live-path engines not executed:** `synthesize_price_path`, `paths_from_store`, `trade_detail`, `big_moves` live behaviors were classified by code reading only (no live store fixtures exercised).
4. **PYTHONHASHSEED tested with two seeds only** (0 vs 12345).
5. **Network isolation** taken from the conftest design (tests/conftest.py pins DATA_SOURCE=mock; no packet-level verification performed).
6. **Per-assertion re-derivation of the 106 related tests** not done individually; their subject matter is covered by my independent probes.
7. **Untracked working-tree files** (`.claude/`, `CLAUDE.md`, `docs/governance/PROJECT_EXECUTION_STATE.md`, `docs/governance/evidence/`, `scripts/r13_owner_repo_setup.sh`, `scripts/validate_bootstrap_config.py`) existed before the audit and were NOT audited (untracked; out of scope; untouched).
8. `evaluate "holdout F1" exploitability` is rated against the CURRENT codebase (single constructor site); future callers could change this — the LOW hardening note (§2.3) addresses exactly that.

---

## 10. Findings register (severity + classification)

| # | Finding | Locus | Severity | Classification |
|---|---|---|---|---|
| F-1 | `HoldoutAttestation` model lacks cross-field validation; internally inconsistent attestations can be hand-constructed (isolated=True pinned by type; constructor path is the only guarantee; single in-repo construction site; no emitting path can lie) | engines/holdout.py:166-184 (constructor :235) | LOW | NOT-A-DEFECT as recorded (prior F1 finding CONFIRMED accurate); optional hardening AUTHORIZED-REPO-SIDE |
| F-2 | Deterministic NaN-returning aggregate refused as `AGGREGATE_NOT_DETERMINISTIC` instead of `AGGREGATE_RETURN_NON_FINITE` (NaN-inequality in the equality guard); fail-closed either way, diagnostic code misleading for NaN only | engines/regime_slices.py:167-168 vs :182-185 | LOW | AUTHORIZED-REPO-SIDE |
| F-3 | C1–C8 comparative phrasings (README ×2, frontend ×2, archive docs ×3, + C8 benign) — no benchmark evidence in-repo; awaiting owner ruling | TABLOKHANI_CAPABILITY_MATRIX.md:118-125, :211; loci verified unchanged at HEAD | — | OWNER-GATED |
| F-4 | "real runs" wording in CHANGELOG/STATUS could be misread as real-market data (context makes it engine runs) | docs/CHANGELOG.md:30; docs/STATUS.md:12 | LOW (cosmetic) | NOT-A-DEFECT (suggested reword) |
| F-5 | Wall-clock/RNG in trade_detail (minute-bucketed seed), big_moves bootstrap (PYTHONHASHSEED-dependent seed), screener as_of, chart_builder fallback stamps | trade_detail.py:25,191,223,282; big_moves.py:64,73,125; screener.py:68; chart_builder.py:22,72,159 | INFO | NOT-A-DEFECT (outside research path; mock/live-ops labeled; big_moves bootstrap by-design non-reproducible) |
| F-6 | tablocastic/screener/big_moves have no dedicated direct unit tests (indirect service/API coverage only) | §8 | INFO (pre-existing backlog item, CONFIRMED) | AUTHORIZED-REPO-SIDE (future test debt) |
| — | Bonferroni/BH math; BH tie & pull-down semantics; NONE-refusal; FP/FN accounting; holdout split/boundaries; regime vocabulary/overlaps/determinism guard; survivorship verdicts & fail-closed refusals; Golden Set digests & exact recomputation; engine double-run determinism; C1-C8 loci; fixture self-labeling & mock trust state | §1-§7 | — | NOT-A-DEFECT (all verified correct/honest) |

---

## 11. Repo-integrity confirmation

- `git rev-parse HEAD` before and after: `7c225cb1ce2771473f1f646be9c4282348ea7657` (unchanged).
- `git status --porcelain` after audit: identical to audit start (only the six pre-existing untracked paths; no modified tracked files).
- `git diff` and `git diff --cached`: **empty**.
- Fixture re-hashed post-audit: `d1560dfadc1f8136ca805501dc68a5c00d86bcbd668aa9854414b31902bdc214` — matches the pinned value (byte-identical).
- All scratch scripts live under `/home/z/my-project/masterwave2_scratch/quant/` (outside the repo).

*Audit artifacts: `d1_mtp_audit.py` (D1), `d234_holdout_regime_surviv_audit.py` (D2-D4), `d56_golden_determinism_audit.py` (D5-D6) — each ends with a machine-checkable ALL PASS line after expectation corrections documented inline.*
