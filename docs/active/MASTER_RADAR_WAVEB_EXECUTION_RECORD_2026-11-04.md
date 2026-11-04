# MASTER-RADAR BOURSE — WAVE-B EXECUTION RECORD (2026-11-04)

Directive: "COMPLETE REMAINING ROADMAP…" §11 WAVE-B (primary: user-indicator DSL MR-B4-01;
secondary: popup-class detach, MR-B2-01 residual). Scope taken from the WAVE-A addendum
gap list (`MASTER_RADAR_REQUIREMENTS_MATRIX_2026-11-04.md`).

## 1. Baseline & reconciliation

- Session start: remote `origin/main == 688a77e…` (WAVE-A reconciliation) — re-fetched, verified
  equal to local; **not** assumed from any prior record (directive §2).
- Fresh WAVE-B checkout cloned from GitHub at `688a77e…`.
- Baseline battery in this checkout: **2624 passed / 2 skipped / 0 failed**. Both skips are the
  documented environmental G2-harness conditionals (`test_g2_acceptance_harness.py:271`
  parent..HEAD docs-only delta; `:367` GOV-19 bundle absent in a fresh checkout) — same class
  as the drift recorded and audit-explained since WAVE-2. Zero failures; zero tests weakened.

## 2. Implementation (disjoint-ownership packages, one checkout, integration by the main agent)

### Package W-B-ENG — UIDL-1 user-indicator DSL engine (MR-B4-01)

- `backend/app/engines/strategy_dsl/indicator_program.py` (NEW): UIDL-1 grammar
  `INDICATOR <name>` / `INPUT <name> = <number>` / `PLOT <name> = <expr>` over the **shared
  RSL-1 lexer + expression parser** (`INDICATOR`/`PLOT` deliberately NOT added to the lexer
  keyword table — zero collision risk for existing RSL-1 sources). Every PLOT must statically
  infer to a numeric `series` — boolean expressions (comparisons, AND/OR/NOT,
  crossover/crossunder) are refused (`SEM_PLOT_NOT_SERIES`), so a plot can never smuggle a
  signal channel. Budgets inherited from the RSL-1 validator and enforced across ALL plots
  (nodes ≤ 512, depth ≤ 64, source ≤ 4096, MTF ≤ 3, symbols ≤ 2, plots ≤ 8, inputs ≤ 16).
  No-look-ahead: `ref(x, n<0)` refused at compile (`LOOKAHEAD_NEGATIVE_REF`); periods integer
  literal/INPUT with per-function minimums. Structural warm-up = first fully-determined bar
  (catalog parity: `sma(20)` → 19); re-computed at evaluation time under merged INPUT
  overrides. Evaluation digests (sha256 over version|source-digest|inputs|values) are
  deterministic and pinned input/plot/source-sensitive.
- `backend/app/engines/strategy_dsl/runtime.py` (EDIT, semantics-preserving): the per-bar
  closure inside `evaluate_at` extracted verbatim to module-level `_value_at(prepared, node, i)`
  + `_cross_at(prepared, call, i)`; new public `expression_series(prepared, expr)`. Purpose:
  UIDL-1 plots share the EXACT RSL-1 per-bar semantics (one source of truth, including the
  documented `x/0 → 0.0` rule). **Independently A/B-verified against the HEAD runtime**:
  2415 decisions + 18 matching error-path pairs across 5 programs × 6 deterministic contexts
  (plain + MTF alignment) — **0 mismatches**.
- `backend/app/engines/strategy_dsl/__init__.py` (EDIT, additive exports only).

### Package W-B-STORE — lifecycle store

- `backend/app/engines/user_indicator_store.py` (NEW): `user.dsl.*` id namespace (builtin.*
  untouchable), semver X.Y.Z with the recorded upgrade policy (same/lower always rejected;
  higher only with `allow_upgrade=True`; upgrades install disabled), per-record SHA-256
  checksum over canonical-JSON definition fields, package budgets (256 KiB / 64 entries),
  forbidden-key scan at any depth (reuses the audited `indicator_manager` scanner), and
  **import re-compiles every source under the CURRENT UIDL-1 rules before storing** (a package
  is data until it compiles — fail closed). No `re.compile` in the module (mirrors
  `indicator_catalog.parse_semver` hygiene). In-memory by design — persistence is the caller's
  export/import, the same contract as `indicator_manager`.

### Package W-B-API — governed API surface

- `backend/app/api/user_indicator_api.py` (NEW): `POST /validate` (compile-only dry run),
  `POST ""` (install, disabled by default), `GET ""` (list + manifest digest),
  `GET /export`, `POST /import`, `GET/DELETE /{id}`, `POST /{id}/enable|disable`,
  `GET /{id}/compute`. Honesty on every payload: `data_class=SYNTHETIC_SEEDED`,
  Persian synthetic note, `valid_from_index` (server-declared warm-up boundary),
  `declarations` (repaint NONE_DECLARED, lookahead enforced-off, missing-data WARMUP_ZERO),
  trust envelope re-read from `market_service` exactly like every v10 router. Typed DSL error
  taxonomy on 422 (`DSL_COMPILE_FAILED` + machine-readable `code/kind/line/col`). Compute
  re-compiles the stored source (fail closed) and evaluates through the audited interpreter
  ONLY. No scheduler, no background task, no egress imports, no live path.
- `backend/app/main.py` (EDIT): one import + one `include_router` line, additive.

### Package W-B-FE — frontend (governed panel + popup detach)

- `frontend/js/modules/user_indicator.js` (NEW) + `frontend/js/modules/render/user_indicator_ui.js`
  (NEW): the governed user-indicator panel (bind-on-demand in the Chart Pro tab). All HTTP
  through `core/api.js` (statically pinned), **no eval / new Function / dynamic import**, no
  timers, `esc()` on every interpolated server string, trust labels only from server fields,
  drawing starts at the server-declared `valid_from_index` (warm-up region never drawn and
  never faked), package export via Blob download and import via `JSON.parse` → POST
  (parsed as data, never executed). The legacy regex demo (`custom_indicator.js` with its
  dishonest silent SMA-20 fallback) is unmounted dead code — the governed panel is the only
  mounted user-indicator path (recorded as audit observation; not touched in this commit).
- `frontend/js/modules/render/chart_grid.js` (EDIT): popup-class detach — per-sub-pane `⧉`
  button → `window.open` same-origin popup with fail-closed hash `#cpGridDetach=<0..2>`;
  detached window boots chrome-less (`body.cp-grid-detached`), restores the saved pane
  config, and syncs symbol/timeframe BOTH WAYS over `BroadcastChannel("radar.grid.sync.v1")`
  with message validation and an echo/loop guard (`_applyingRemote`). Honest scope, stated
  in-UI and here: same-origin browser windows the user can drag to another monitor; **no OS
  window-placement claim**; crosshair/range sync across detached windows is NOT claimed in v1.
- Integration: `index.html` (+`#cpUserIndRoot` container; tabs stay **29/29**), `main.js`
  (+1 import), `sw.js` v3-0-8 → **v3-0-9** (+2 precache) with **5 recorded counter-pin
  bumps** (`test_wda_version_consistency`, `test_p3_80_local_closure`,
  `test_master_radar_wave3_integration`, `test_master_radar_frontend_static`,
  `test_master_radar_wave2_frontend` — pins only, no assertion weakened).

## 3. Tests (+115 = 2624 + 115 = 2739 exact)

- `tests/test_user_indicator_dsl.py` (60): grammar/rejections (every typed code incl.
  `BUDGET_PLOTS`, `BUDGET_INPUTS`, `BUDGET_DEPTH`, `SEM_PLOT_NOT_SERIES`), hand-computed
  fixtures on a pinned 12-bar OHLCV, an **independent naive recomputation battery**
  (test-local evaluator, does not import the DSL) matched bar-for-bar, warm-up coherence
  (structural == runtime zero/partial-window regions, 11 cases), MTF close-provable
  alignment, prefix stability at every truncation, determinism/digest sensitivity, input
  guards (NaN/Inf/bool/str rejected), sandbox resistance (8 hostile payloads + a static
  no-eval/exec/compile/`__import__` scan over the three new modules; store refuses
  non-compiling source).
- `tests/test_user_indicator_api.py` (29): full lifecycle over HTTP, error taxonomy,
  duplicate→409, export/import round-trip + tamper rejections (checksum mismatch, forbidden
  field, wrong namespace, non-compiling source, wrong package version), compute honesty/
  determinism/prefix-stability/param errors, governance boundaries (scoped route surface, no
  scheduler/egress imports, frozen `end_bar_index` byte-stability, manifest digest).
  Includes the **autouse settings-cache hygiene fixture** (per-test
  `get_settings.cache_clear()` both sides) — durable fix for the recorded AUDIT-MR3 Obs.3
  residue class (a module-scope clear runs at collection time and does not survive
  mid-session poisoning by `test_security_hardening`).
- `tests/test_master_radar_waveb_frontend.py` (26): node `--check` on all three touched JS
  files, security gates (banned primitives, api.js-only HTTP boundary, no client fallback
  engine, `esc()` coverage, no timers), UIDL honesty surface, detach pure-logic pins
  (fail-closed hash bounds, message validation, echo guard, chrome-hiding), SW v3-0-9 +
  precache + counter-pins, `cpUserIndRoot` present, tabs 29/29.

## 4. Integration findings (fixed pre-publication)

1. `get_settings` lru_cache residue from `test_security_hardening` poisoned later modules
   (401s) — the module-scope clear is insufficient (runs at collection); replaced with the
   autouse per-test fixture above. No other test touched.
2. Frontend import-depth bug caught by the repo's own static validator
   (`scripts/validate_frontend_static.py`): `user_indicator.js` lives in `js/modules/`, so
   `../core/*` not `../../core/*`. Validator now `ok:true`.

## 5. AUDIT-MR4 (independent read-only, pre-publication, fresh clone of the working tree)

- Battery ×2 in the fresh clone: **2739 passed / 2 skipped / 0 failed both runs**; count math
  exact (2624 + 60 + 29 + 26).
- 43 hostile probes against a REAL uvicorn server (`DATA_SOURCE=mock`): malformed/oversized/
  deeply-nested/unicode/quote-smuggling sources, prototype-pollution and oversize imports,
  NaN/Inf/list/negative/float params, bad timeframes, compute after uninstall →
  **zero 5xx** (33×422, 2×409, 1×404, 7×200 — all typed).
- Live prefix stability verified on the running server across three truncations.
- A/B runtime equivalence vs HEAD: 2415 decisions + 18 error pairs, 0 mismatches (above).
- Test integrity: `git diff` over the five modified test files = counter-pin bumps ONLY.
- Secret scan over all changed/new files: NONE. Gates: `config.py` diff **0 bytes**
  (`AI2_ENABLED=0` at config.py:111), `verified=False` posture, `SYNTHETIC_OR_PAPER`,
  no scheduler/egress/live path, no runtime caller added to any disconnected edge.
- Static validator `ok:true`, tabs 29/29, duplicate-id census clean.
- Findings: **0 FAILs**; observations O1 (legacy demo modules remain unmounted dead code —
  governed panel is the only mounted path; removal left to a hygiene wave), O2 (store
  in-memory; export/import is the persistence contract), O3 (detach sync v1 = symbol/TF only,
  documented honestly), O4 (highest/lowest warm-up region carries the runtime's documented
  partial-window values, tested as such) — all accepted with rationale.

## 6. Publication (forward-only)

- Implementation commit: **733ba96** `MASTER-RADAR WAVE-B implementation…` — pushed via the
  pinned-host-key paramiko GIT_SSH wrapper; **read-back verified**: `ls-remote` main ==
  `733ba96550f71aea04ff6595613cbf0b0e4bab90`.
- Records commit: this file + requirements-matrix addendum + `AUDIT_MR4_REPORT.md` +
  Persian report §37 + STATUS/CHANGELOG/INDEX (published immediately after; SHA recorded in
  the STATUS entry and verified by read-back).
- Exact-SHA CI on 733ba96: pending at records-push time; evidence to be appended per WS1 §13
  discipline (implementation commit is the CI-relevant SHA — records are docs-only).

## 7. Status vocabulary (no upgrade without evidence)

- MR-B4-01 user-indicator DSL: **INTEGRATION-VERIFIED** (implemented + 89 engine/API tests +
  independent recomputation + A/B runtime equivalence + fresh-clone reproduction + live
  hostile-probe battery; operational/owner acceptance on a target machine remains owner-gated
  per R-1/R-2).
- MR-B2-01 popup detach: **TESTED→INTEGRATION-VERIFIED (popup class)** — real same-origin
  popups with two-way symbol/TF sync, static-test-pinned; OS placement and inter-window
  crosshair sync honestly NOT CLAIMED; multi-monitor claim limited to "user can drag the
  popup to another display" (browser capability, not OS integration).
- Global completion: **NOT CALCULATED** (no approved weighted model; per the directive).
