# CONSOL-NEXT — PRODUCT COMPLETION & CONTROLLED ALPHA LAUNCH: EXECUTION RECORD (2026-11-02)

Directive: CONSOL-NEXT owner directive (2026-11-02). Temporary engineering team
(one coordinating orchestrator + bounded parallel specialists); the product's
internal AI agents were not involved. MA-1 is accepted and closed at this
baseline and was NOT reopened: the full battery was reproduced exactly
(1293 passed / 1 skipped) and no reproducible regression was found.

## 1. Baseline (verified by execution, not assumed)

- main `84f9b1b75dd2c90d9c6c98d2c808f2d93df44ec6`, tree
  `078931c31b0c1fcdf0dfcb23baa0e8a74cb83124`, branch main, tracked tree clean,
  stash 0, single worktree; remote read-back `ls-remote` exit 0 → origin/main
  identical (`84f9b1b…`).
- Full battery reproduced at baseline: 1293 passed / 1 skipped / 2 warnings.
- Gates re-verified at baseline and again at the integration HEAD:
  `AI2_ENABLED=0` (`backend/app/core/config.py:111`), `verified=False`
  (`config.py:284`), `execution_mode=SYNTHETIC_OR_PAPER`, zero `ai2`
  references under `backend/app/api/`, no purge/retention-expiry path for
  episodic research evidence, AI-5 kill-switch default ENGAGED
  (`domain/proactive_research.py:102`), no live-trading/order-execution path
  (14-pattern sweep; single hit is the negative attestation
  `backtest.py:483 "live_trading": False`).

## 2. Team and method

Wave 1 (parallel, disjoint file scopes, additive-only, no agent committed):
T1 governance auditor (read-only) · T2 P3 quantitative validation · T3 AI-2/AI-MA
runtime · T4 AI-3 persistence architect · T5 TabloKhani evidence · T6 launch
readiness. Wave 2: T7 P5/P6 alert-lifecycle integration audit. The orchestrator
performed QA-finding disposition (integration-sensitive), integration, full
validation, commits, publication, and records. Every agent output landed as a
NEW untracked file; zero tracked files were modified by any agent; the
untracked bootstrap set (`.claude/`, `CLAUDE.md`, `docs/governance/*`,
`scripts/validate_bootstrap_config.py`, `scripts/r13_owner_repo_setup.sh`) was
left untouched.

## 3. WP-1 — Remaining repository-side work

- **TabloKhani capability matrix CREATED**
  (`docs/active/TABLOKHANI_CAPABILITY_MATRIX.md`): 32 capabilities; every cell
  cites in-repo file:line/test ids; 31/32 rows are honestly
  `NOT_COMPARED_WITH_EVIDENCE` (zero measured TabloKhani comparisons exist in
  the repository) and 1 row is `UNKNOWN` (video-2 leader formula taught in the
  archive has no verbatim implementation); `AT_PARITY_EVIDENCE_BASED` is used
  nowhere. Includes the comparative-phrase claim inventory C1–C8 with exact
  loci (owner-flagged class, unchanged) and the TabloKhani-informed feature
  section (tablocastic engine, hot-money tiers, big-player game, big moves).
- **Queued MA-1 QA findings dispositioned** — see §8.
- **P5/P6 integration audit (T7)** — 10-edge producer→consumer/runtime graph
  with file:symbol evidence. Connected: governed coverage event → admission
  gates → outbox → dispatcher (kill switches → budgets → expiry drop) → inbox
  → API read surfaces; owner ops routes (API-key gated) + guarded lifespan
  loop. Disconnected by construction: governed-alert channel is the type-closed
  `Literal["IN_PRODUCT_INBOX"]` — no notifier/ws_hub edge exists (AST
  import-graph proof added as a test). The ONLY disconnected producer edge is
  E6 (confluence/screener board events → governed admission): deliberate
  design per the D-AI-30 implementation record; wiring is owner-gated future
  work, not a defect. D-AI-30 boundary re-proven: `purge_expired_records()`
  executes exactly four namespaced `DELETE FROM alert_ops_*` statements; a
  co-tenant foreign table with 3650-day-old rows in the same database survives
  purge byte-identically; episodic research evidence (in-memory append-only
  contracts, engine pending D1–D7) is structurally unreachable; no autonomous
  production mutation (zero writes outside the seven `alert_ops_*` tables; no
  imports of trading/market modules).
- **Integration tests where gaps demonstrated**: 16 new tests
  (`test_p5p6_integration_alert_ops_api.py` — full chain through the dispatch
  route, fail-closed kill-switch codes, dead-letter success path, API-key
  401/200; `test_p5p6_integration_delivery_surfaces.py` — ws_hub
  connect/broadcast/prune, notifier fake-transport seam with credential-gated
  partial channel and dry-run, AST no-edge proof; `test_p5p6_integration_store_purge_boundary.py`
  — purge removes exactly the expired alert-ops rows and provably cannot touch
  research/episodic evidence). Existing coverage enumerated first (119 tests
  re-verified green); no duplication.
- **Docs currency completed (additive)**: the MA-1 CHANGELOG/INDEX entries were
  frozen at the pre-publication `b7b954c` state; this cycle adds the
  publication-completion entries (`1832b75` lint fix, CI 3/3 SUCCESS runs
  `41353897849`/`41353897802`, `84f9b1b` publication record, WS-12 ACCEPT
  verdict) without altering any historical text.

## 4. WP-2 — AI-3 persistence (PREPARE ONLY; implementation OWNER-GATED)

- **D1–D7 status re-confirmed ALL PENDING**
  (`docs/active/AI3_PERSISTENCE_DECISION_PACKET.md:3` — "ALL SEVEN DECISIONS
  PENDING — no owner decision recorded as of 2026-11-02; none assumed"). No
  option was selected, assumed, or pre-recorded anywhere in this cycle.
- **Implementation plan CREATED** (`docs/active/AI3_PERSISTENCE_IMPLEMENTATION_PLAN.md`,
  486 lines): execution gate table; per-decision conditional plan §3.1–§3.7
  (each D1–D7 verbatim question → per-option adapter topology / storage layout
  / migration surface, source-cited, UNKNOWN-WITH-REASON preserved);
  decision-independent cross-cutting requirements §4.1–§4.9 (canonical JSON +
  sha256 content addressing; append-only + fail-closed refusal records; PIT
  retrieval by `recorded_at_utc`/`created_at_utc`; backup/restore +
  crash-recovery rehearsal; single-writer-class concurrency semantics;
  forward+back migration/rollback-as-restoration rehearsal; Windows path +
  Electron packaging compatibility — hex-only names, reserved-character
  avoidance, path-depth budget, long-path policy, case-collision safety;
  performance measurement points P-1..P-6, values measured-not-asserted with
  thresholds = owner numeric-ceiling class); acceptance-criteria table §5
  (AC-1..AC-15 mapped to executable test ids; packet §10 engine-level drills
  stay BINDING on the future adapter); explicit statement that
  SQLite + content-addressed-FS remains an engineering CANDIDATE, not a
  decision.
- **Acceptance-test scaffold CREATED** (`backend/tests/test_ai3_acceptance_scaffold.py`,
  24 tests): parameterized over a `STORE_FACTORIES` registry so ANY future
  adapter must pass the identical suite (today driven by
  `InMemoryResearchMemoryStore`; a future engine adapter plugs in by adding
  one factory entry — no test-body changes). Covers: protocol-surface
  exactness (no update/delete path), structural no-purge/no-retention-expiry
  absence, idempotent append + conflict refusal, canonical round-trip byte
  stability, integrity verify/tamper/missing/corrupt fail-closed, PIT
  ordering + look-ahead guard, episodic→archive→lesson promotion with
  citation gate, crash-consistency observables, two-thread concurrent append
  under the documented single-writer discipline, frozen refusal records,
  provenance completeness, explicit misses, retirement terminality,
  composition-by-delegation honesty.
- **No-purge self-audit**: 39 token hits across the two new AI-3 files — every
  one a prohibition or negative structural assertion; zero functionality.

## 5. WP-3 — P3 research quality

- **Independent validation, +34 tests** (5 files under
  `test_p3_quality_validation_*`): hand-computed Bonferroni/Benjamini-Hochberg
  cross-checks in exact dyadic arithmetic (incl. the BH pull-down case where a
  raw value is monotonized downward, ties, clipping, exact alpha-boundary
  acceptance, NONE-method refusal inside a mixed batch, the all-FP case where
  precision is genuinely 0.0 while recall is None); holdout no-leakage +
  partition-completeness proofs, `inf`/`bool` fraction refusal, empty-segment
  boundary, and the adversarial isolated-attestation-only-via-passing-path
  sweep (7 failing scenarios, none escapes an attestation); regime-slice
  closed vocabulary at model level, adversarial overlaps (nested, duplicate,
  order-scrambled), determinism guard catching a later-window drift,
  aggregate-call-count pinning; survivorship all four verdicts reachable with
  1–2-member minimal universes plus boundary and conflict cases; Golden Set
  metric-level double-run determinism, tamper-evidence proven on a tmp-dir
  COPY (repo fixture byte-identical afterwards), every pinned key proven
  non-vacuous (exists in engine output), fixture self-labeling pinned
  (synthetic/mock/no-superiority).
- **Provenance audit (honest classification)**: all pinned Golden Set metrics
  are `REPRODUCIBLE-SYNTHETIC-RUN` — exactly recomputed from the fixture's own
  hand-written bars + pinned `ExecutionConfig` via the in-repo deterministic
  engine (probe reproduced every value; digests re-derived independently,
  including without app code); there is NO production-market evidence in the
  fixture and none is claimed; `data_trust_state=mock`. The fixture is not
  `SYNTHETIC-SCHEMA-ONLY` (values recompute exactly) and not real-market
  evidence — it is deterministic synthetic by design.
- **Findings recorded, not fixed** (out-of-mandate to change published
  artifacts): F1 LOW — `HoldoutAttestation` cross-field consistency is not
  enforced at the type level (forgery requires bypassing the module API; all
  API paths proven safe; hardening candidate for a future additive validator);
  F4 LOW — MA-1 record §3 WS-2 phrase "metrics pinned from real
  backtest/WFO/forward runs" means real RUNS of the real engine over
  synthetic hand-written inputs (recomputable), not real-market evidence; the
  MA-1 record is a published historical record and is preserved verbatim per
  forward-only discipline; this note is the currency correction.
- **No superiority claim** was made, strengthened, or newly asserted anywhere.

## 6. WP-4 — AI runtime integration (Synthetic/Paper only)

- **E2E verification, +27 tests** (3 files under `test_ai_runtime_integration_*`):
  full AI-2 synthetic session — candidate → `executed_shadow` (exactly one
  stage-2 transport invocation) → LEDGERED (never COMPLETED) →
  `governed_acceptance` refuses with `run_status_not_completed` (all 6
  non-COMPLETED statuses refused exhaustively; COMPLETED un-mintable without
  an artifact); duplicate refused pre-execution (zero transport calls);
  repeated-question `DUPLICATE_FLAGGED`; `BUDGET_EXHAUSTED` session refusal;
  episodic artifact appended on service-OK runs only; injected clocks only
  (wall-clock reads patched to raise); `AI2_ENABLED=0` default gates the loop
  even when a transport is offered. AI-MA runtime — event-choreographed
  reverse completion order never leaks into results/trace; hung executor
  actually cancelled + late result discarded (`deadline_exceeded`); straggler
  discard; load-bearing failure terminates the run before dispatching the
  dependent; independent failures contained; `deterministic_synthesis` refuses
  mixed run ids with authority `DETERMINISTIC_ONLY`; all nine failure kinds
  driven at the runtime boundary, each landing on exactly
  `FAILURE_RUN_CONTAINMENT[kind]`. AI-4/5/6/7 connected-edge compositions
  (evaluator registry → governed gates; permission semantics → tick ledger;
  scanner → canonical injection records; calibration metrics →
  `CalibrationRecord` with maturity guard; audit records → product-audit
  vocabulary).
- **Producer→consumer map recorded** (feeds future integration work): five
  edges are DISCONNECTED by current design (contract/producer-complete, no
  runtime consumer): AI-2 loop → runtime caller/route; AI-MA runtime → plan
  producer/caller; AI-4 governed generation → runtime consumer; AI-6 scan
  verdicts → `DocumentLedger` registration; AI-7 `CalibrationRecord`/
  `DriftAssessment` → runtime consumers. Three edges are OWNER-GATED (AI-5
  scheduler runtime per D-AI-30; AI-6 retrieval/scanning runtime; AI-3
  persistence adapter per D1–D7). No wiring was invented to force edges
  closed; the gaps are recorded as the remaining integration backlog.
- **Defects found in tracked code: none.** Three INFO observations documented
  and test-pinned (artifact archived for DUPLICATE_FLAGGED service-OK runs
  while the ledger record correctly drops it; per-wave specialist budget
  charging semantics; quarantine-scope redundancy refusal).

## 7. WP-5 — Controlled Alpha launch readiness (repo-side only)

- **Local browser E2E re-run: 7/7 PASSED** (closes the MA-1 §7 honesty-register
  deferral): canonical boot `app.main:app` with `PYTHONPATH=backend`, health
  200 in ~2 s (`version=3.0.0`, `trust_state=mock`, `live_verified=False`);
  outer-venv playwright + chromium; 7 passed in 5.45 s. Ephemeral
  `FERNET_KEY` WARNING+CRITICAL recorded honestly — acceptable for local
  verification ONLY; must not appear on a target machine (persistent
  `FERNET_KEY` mandatory). Boot-command currency finding recorded: literal
  `backend.app.main:app` from repo root fails (`ModuleNotFoundError`); every
  committed launcher (`start.sh`, `start.ps1`, Docker entrypoint) already uses
  the canonical form.
- **Version chain verified 3.0.0 end-to-end**: `config.py:28` = `/api/health`
  = `/api/status` = `electron/package.json:3` = `frontend/manifest.json:34`;
  the frontend display is single-source from `/api/health` with no hardcoded
  fallback — pinned by the new tests, including the two-shape health contract
  (full vs `_redacted_probe`) and the `verified=False` trust posture
  (state `live` ⇒ `trust_level=mixed`; `live_verified=True` argument ignored;
  `is_verified_live` refusal matrix).
- **Backup/restore runbook audit**: all 8 code/doc references
  VERIFIED_PATH_EXISTS (`Store.backup(keep=7)` + `wal_checkpoint(TRUNCATE)` +
  copy2 + prune; `user_version` guarded additive migrations; alert-ops
  archive-rename reversible rollback; referenced docs present). Runtime-only
  items classified (`mv/cp` restore, `sqlite3` integrity_check); offsite copy
  = OWNER-GATED. Runtime persistence inventory: gitignored `/data/`
  (`shekar.db` + WAL/SHM, `market_cache.json` rebuildable, declared-but-unused
  `history_snapshots.jsonl`, `data/backups/shekar-*.db`). No stale path, no
  invented behavior.
- **Windows currency findings (recorded, not edited)**:
  `P343_INSTALL_CHECKLIST.md:43` — start.ps1 defaults `$HostAddress="0.0.0.0"`,
  so the sequence must pass `-HostAddress 127.0.0.1` (checklist nuance);
  `P343_INSTALL_CHECKLIST.md:16-22` — CI pins reference pre-MA-1 SHAs (the
  checklist itself mandates re-verification at install time, so this is a
  currency note, not a defect).
- **`docs/active/CONTROLLED_ALPHA_LAUNCH_READINESS_RECORD.md` created**:
  per-item verification statuses, honest E2E evidence, owner-gate register,
  and the 10-step `PROPOSED_SEQUENCE_PENDING_OWNER_INSTALL` built solely from
  verified scripts with per-step exit criteria.
- **Red line restated**: Windows CI green ≠ target-machine installation
  success. The INSTALL instruction remains OWNER-GATED and NOT ISSUED; no
  installation was performed or simulated as performed.

## 8. Queued MA-1 QA findings — disposition (WP-1)

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| Q-1 | LOW | Per-cycle degraded token for `market_service.refresh()` concurrency (single shared `_fetch_degraded` bool) | **ANALYZED_AND_DEFERRED.** Technical analysis: `refresh()`'s only await is the provider fetch (`market_service.py:374`); between the degraded-flag set (`:389`) and the Phase-3 read (`:472`) the code path contains zero await points (line-scan verified), so the span is cycle-atomic under the single asyncio event loop and the cross-cycle race cannot interleave today. The hazard is LATENT: any future await introduced in Phase 2 would open it. Hardening path defined (per-cycle local token with the attribute retained as an observability mirror — sequential semantics byte-identical). Not fixed in this cycle because no deterministic failing reproduction exists without altering production code shape, and a behavior-invisible change to the Phase-3 trust path violates the evidence-bound change policy. |
| Q-2 | INFO | Defensive-comment nits | **CLOSED_NO_CHANGE** — no itemized locus exists in any tracked doc (identity NOT_VERIFIED already in T1's ledger); cosmetic only. |
| Q-3..Q-5 | — | 3 of the 5 WS-12 non-blocking findings from the MA-1 publication commit message are not enumerated in any tracked doc | **NOT_VERIFIED identity** — not reconstructed or invented; the independent QA pass of this cycle re-derives what is reproducible (§10); the two enumerated findings (Q-1, Q-2) are dispositioned above. |
| Q-6/Q-7 | owner-flagged | Comparative phrasing "بهینه‌تر از/بهتر از tablokhani.com" at `README.md:3`, `frontend/js/modules/render/watchlist_excellent.js:2` and `:53` | **OWNER-GATED (03:111 evidence rule; MA-1 §6)** — unchanged; full inventory now at `TABLOKHANI_CAPABILITY_MATRIX.md` §4 (C1–C8 incl. archived records and the adjacent "Better than Novin/Arshan" class at `api/chart.py:2,30,117`, `engines/chart_builder.py:2,151`). |

## 9. Integration verification (orchestrator, at the integration HEAD)

- Full battery: **1404 passed / 1 skipped / 2 warnings in 12.22 s, exit 0**
  (1293 baseline + 111 new: WP-3 34 + WP-4 27 + WP-2 24 + WP-5 10 + P5/P6 16).
- pyflakes `backend/app/`: exit 0 (empty). pyflakes over all 13 new test
  files: exit 0 (empty).
- Secret-pattern scan over all new files: clean. No-purge token scan over the
  new AI-3 files: prohibitions only.
- Workspace before commit: zero tracked modifications; all agent outputs are
  new files; untracked bootstrap set untouched; no stash; single worktree.
- Existing tests: none modified, none weakened, none skipped, none deleted
  (additive delta = exactly the 13 new test files + 3 new docs + 4 updated
  current-facing records: this record, STATUS, CHANGELOG, INDEX).
- No owner decision recorded or fabricated; D1–D7 PENDING; AI-2 invariants
  byte-unchanged; no network/LLM in any new module; clocks injected.

## 10. Independent verification (in-cycle)

The independent QA agent reproduced the cycle's acceptance claims from the
committed tree: baseline-battery parity, per-WP test-node arithmetic
(111-node delta), gates sweep, no-purge enumeration, producer→consumer
spot-checks, Golden Set recompute probe, E2E evidence, and the disposition
rationale for Q-1/Q-2. Verdict and any findings are recorded in the
publication record that follows this cycle (STATUS/CHANGELOG rows bound to
the final SHA).

## 11. Remaining owner-gated register (unchanged in kind, single consolidated view)

1. INSTALL instruction (dated, explicit) — P3.43 Controlled Alpha launch.
2. Windows target-machine validation access (CI green ≠ target install).
3. AI-3 D1–D7 decisions via `AI3_PERSISTENCE_DECISION_PACKET.md` templates
   (implementation starts only after they are recorded).
4. Live-provider posture (DENIED for the current release; re-openable only by
   a dated owner act).
5. AI-4 runtime numeric budgets (proposal-only); AI-5 scheduler runtime
   (D-AI-30 core stability + cadence/budget); AI-6 source-class admission +
   Two-Key parameters; AI-7 autonomy expansion (D-AI-31, evidence-gated).
6. Comparative-phrasing rulings (README.md:3; watchlist_excellent.js:2,53;
   adjacent archived/UI loci) per the 03:111 evidence rule.
7. Optional hardening backlog recorded this cycle: F1 holdout-attestation
   type-level validator; E6 confluence→governed-admission wiring decision;
   AI runtime disconnected-edge wiring (§6 map); dedicated unit tests for
   tablocastic/screener/big_moves math (currently indirect-only coverage).
