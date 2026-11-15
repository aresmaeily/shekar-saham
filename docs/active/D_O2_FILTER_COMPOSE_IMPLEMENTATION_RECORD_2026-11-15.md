# D-O2 FILTER-COMPOSE IMPLEMENTATION RECORD — 2026-11-15

Owner decision **D-O2** (RADAR BOURSE consolidated mission, 2026-11-15): APPROVED the
filter-compose continuation as an ADDITIVE implementation on the existing Filter DSL.
This record documents (1) the spec-verification pass required by D-O2 before
implementation, (2) every correction/decision made against the approved spec, and
(3) the provenance labels carried into the implementation.

Baseline: `release/web-rc1` branched from origin/main `7a41563968dc5ac5d57f5f3d7ac3a674e735ee58`.
Baseline battery at the exact base SHA: **3231 passed / 1 skipped** (re-run fresh, matches
the recorded evidence). Post-implementation battery: **3303 passed / 1 skipped / 0 failed**.

## 1. Spec verification against the exact current source (D-O2 precondition)

Approved spec: `TABLOKHANI_FILTER_COMPOSE_CONTINUATION_SPEC.md` (2026-11-15,
SHA-256 `cf96cb35c56b4ea13b59a2335154df190e400954bbffe5ed706210ddccfd8170`).
Each §-claim verified against the `7a41563` tree before coding:

| spec claim | verdict at 7a41563 |
|---|---|
| §1 DSL public API + budgets (MAX_EXPR_LEN=1000/MAX_AST_NODES=160/MAX_AST_DEPTH=24), no eval/exec | VERIFIED (`app/engines/filter_dsl.py`) |
| §1 exactly 8 built-in presets | VERIFIED (`PRESETS`, 8 ids) |
| §2 row universe keys (pl/plp/…/smart_flow/fund_*/queue/flags) | VERIFIED (`market_service._build_filter_row`, ~80 keys; every field used by the 8 composed filters exists) |
| §2 read-only accessor `build_filter_rows()` | ADJUSTED — implemented as the public read-only accessor `MarketService.get_filter_rows()` (naming follows the live codebase; recovered name preserved in docstring) |
| §4 validation pipeline normalize→parse→compile; FilterError structured | VERIFIED |
| §6 ranking rule `match_count desc → golden_number desc → entry_score desc → symbol asc` | VERIFIED against recovered formulas doc §3; implemented verbatim |
| §7 market context = arithmetic mean incl. zero rows; empty ⇒ 0.0 | VERIFIED against recovered §2.5; implemented |
| §11 recovered fixture board 6/2/1/0, mean 130M, ranti [AAA, BBB], dry-run metrics | VERIFIED bit-for-bit from the recovered package (`composition_dryrun_fixture.json`, package SHA `34e0f274…`); re-derived raw rows reproduce the board exactly through the real engine |
| §12.11 existing `test_filter_dsl.py` passes unchanged | VERIFIED (17/17, suite untouched) |

## 2. Corrections and implementation decisions (all recorded, none silent)

1. **Default selection (spec did not specify):** a request with neither `filter_ids`
   nor `exprs` runs the WHOLE 8-filter catalog in definition order — the documented
   reference behavior B-6 («تحلیل چندبعدی» over the whole market with 8 filters).
2. **exprs-only semantics (spec did not specify):** an exprs-only request composes
   EXACTLY the requested units (no implicit catalog merge); a fully-invalid unit set
   yields an honest empty board (`ok=true`, `results=[]`).
3. **matched[] order:** catalog definition order (recovered fixture pins it verbatim:
   hot_money → sus_volume → legal_sell_retail_buy → per_capita_vs_market → buy_queue →
   smart_inflow_red_board → hot_money_plus → retail_exit). Request ordering never
   changes the output (determinism).
4. **HTTP 400 vs pydantic 422 (spec §9 requires 400):** range/limit validation is
   performed by the compose engine (`ComposeValidationError`/`UnknownFilterError` →
   HTTP 400); the request model intentionally carries no range constraints so limits
   return 400, not 422 (pinned by tests).
5. **double_run_identical scope (§12.9):** the compose engine is a pure function and
   byte-identical across runs at library AND API level. The `data_trust` envelope is
   a documented passthrough whose `checked_at` is the wall-clock of the trust check
   itself (existing pinned behavior, unchanged) — API-level identity is asserted over
   the engine-owned payload, with the trust fields asserted separately.
6. **missing-data fail-closed (§8):** implemented as a per-(filter,row) pre-check on
   every field the expression references (aliases resolved exactly like the
   evaluator); a missing datum records an honest per-filter error and contributes no
   match. The legacy `/api/filter/run` single-expression semantics are UNCHANGED
   (existing suite pinned; no regression).
7. **market_* runtime namespace (§7):** implemented as a bounded, numeric-only,
   strictly-namespaced registry inside `filter_dsl.py` (`register_runtime_fields`,
   `^market_[a-z0-9_]+$`, ≤32 entries, cannot override ALLOWED_FIELDS/FUNCTIONS,
   registered once at compose-module import — no per-request mutation). No new AST
   node types; the grammar is unchanged. Existing DSL suite passes unchanged.
8. **degenerate market context (§7):** value 0.0 + explicit `market_context.degenerate`
   disclosure + UI warning chip; pinned by tests so it can never pass as a market signal.
9. **composition-level AND/OR/NOT (§5.6 + D-O2 "AND/OR composition"):** D-O2 requires
   AND/OR composition and safe nesting; the approved spec confines AND/OR/nesting to
   INSIDE each expression (full boolean DSL — already supported) and explicitly defers
   second-level weighted composition as a NOT_SUPPORTED owner decision packet. Per the
   D-O2 rule "for behavior that remains unknown, expose an explicit unsupported state",
   the API/UI expose `unsupported.composition_level_and_or = NOT_SUPPORTED — …` instead
   of inventing semantics. Safe nesting inside each filter is verified by the DSL suite.
10. **Survey-artifact recorded:** an exploration pass reported the CI workflow branch
    filters as malformed (`branches: ain, develop]`). Byte-level verification proved
    the files contain the correct `branches: [main, develop]` — the report was an
    output-rendering artifact (`[m` swallowed), NOT a real defect. No "fix" was needed;
    the only workflow change in this RC is the additive `pull_request:` trigger on
    windows-installer.yml so all FOUR required checks run on the candidate SHA
    (parity with ci.yml/windows.yml which already run on PRs).

## 3. Provenance labels (carried verbatim into code/UI)

| filter | provenance | deviation recorded in rationale |
|---|---|---|
| hot_money | DOCUMENTED_PUBLIC_SEMANTICS | boundary 200M inclusive, band partition |
| sus_volume | INDEPENDENT_PROPOSAL | 30d window vs reference 3d/14d (deliberate) |
| legal_sell_retail_buy | DOCUMENTED_PUBLIC_SEMANTICS | 0.6 inclusive vs «بالای ۶۰» strict reading |
| per_capita_vs_market | DOCUMENTED_PUBLIC_SEMANTICS | «کل بازار» = evaluated universe (INDEPENDENT component) |
| buy_queue | RADAR_NATIVE | exact reference predicate unpublished |
| retail_exit | INDEPENDENT_PROPOSAL | rule unpublished; 100M sell-side scale is a proposal |
| smart_inflow_red_board | RADAR_NATIVE | rule unpublished |
| hot_money_plus | DOCUMENTED_PUBLIC_SEMANTICS | 100M inclusive / 200M exclusive |

Comparison outputs carry `OVERLAP_ONLY_NO_SUPERIORITY_CLAIM` or `NOT_MEASURED`
exclusively; no parity/superiority claim is made anywhere.

## 4. Out of scope (unchanged from the approved spec §14)

Saved filter SETS + CSV export (GM-9), rolling 3d/14d windows (GM-6), historical-array
DSL (GM-8), alert vocabulary (GM-10), per-column watchlist filters (GM-18), any live
provider activation (GM-15), any trading/broker/scheduler/AI-2/production-mutation path.

## 5. Test evidence (this implementation)

- New tests: `test_filter_compose.py` (37: fixture counts, ranking ties, band
  boundaries, fail-closed missing data, degenerate disclosure, double-run identity,
  API contract/400s, presets shape), `test_filter_compose_frontend.py` (5 static
  contract pins), `test_liquidity_pinning.py` (20), `test_fundamental_line_pit.py` (17).
- Existing DSL suite: 17/17 unchanged; SW-version counter-pins updated 20 → 21 with
  recorded comments (8 files).
- Full battery at the implementation tree: **3303 passed / 1 skipped / 0 failed**
  (`python -m pytest tests/ -q --tb=no -p no:cacheprovider`, 48.32s, Python 3.12.16).
- Governance gates unchanged: `AI2_ENABLED=0` (`config.py:118` default), 
  `SCHEDULER_ENABLED=0` (default), `verified=False ⇒ SYNTHETIC_OR_PAPER` posture,
  no scheduler/egress/broker path added; compose is read-only over the row cache.
