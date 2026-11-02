# MASTER EXECUTION DIRECTIVE — WAVE 1 EXECUTION RECORD (2026-11-02)

Directive: "MASTER EXECUTION DIRECTIVE — COMPLETE PROJECT FROM CURRENT
BASELINE TO 100%" (2026-11-02). Temporary engineering team in the developer's
execution environment; the product's internal AI agents were not involved.

## 1. Baseline (verified by execution, not assumed)

- At cycle open the remote HEAD had ADVANCED beyond the directive's expected
  `84f9b1b…`/`078931c3…`: actual baseline = `main`
  `69a75bf0d6d03a6bbf02452cbd5b9e8a75e2f975`, tree
  `010f72f298bc42de5ff4e1011cf4ba8a1ac868fa` (local == `origin/main`, 0/0
  divergence after fetch; `ls-remote` exit 0). Per directive §2 the newer
  HEAD was adopted as the actual baseline and nothing was overwritten.
- CI on the exact baseline SHA `69a75bf` re-verified via the GitHub checks
  API: `test-backend` SUCCESS, `build-docker` SUCCESS, `windows-validation`
  SUCCESS (3/3 required jobs green on the exact published SHA).
- Full battery at baseline: 1404 passed / 1 skipped / 2 warnings (recorded
  from the CONSOL-NEXT cycle and re-established below at the wave HEAD).
- Inherited workspace state: the CONSOL-NEXT publication (`69a75bf`) was
  already pushed and CI-verified; the working tree carried an interrupted
  follow-on wave (2 modified tracked files + 3 new test files) that this
  wave reconciled, completed, validated, and published.

## 2. Work in this wave — WS-C (MA-1 QA finding Q-1: per-cycle degraded token)

Directive §5 WS-C: "Prioritize the reported LOW finding concerning per-cycle
degraded tokens during concurrent refresh. Reproduce the condition before
changing code. Add concurrency and regression tests."

- **REPRODUCED BEFORE CHANGING CODE** (evidence-bound, both directions
  observed in this cycle):
  - Pre-fix code shape (working tree without the hardening): `pytest
    tests/test_refresh_degraded_token_concurrency.py::test_interleaved_fresh_cycle_must_not_steal_degraded_cycle_marker`
    → **FAILED** at the decisive assertion — cycle A's degraded marker was
    clobbered by interleaved cycle B's Phase-1 fresh-flag write and A's
    RECYCLED board was re-stamped as fresh (false-fresh reproduced).
  - Post-fix: the same test **PASSES**; the fix is the per-cycle local token.
- **Fix** (`backend/app/services/market_service.py`, +18/−4): the degraded
  marker is now a PER-CYCLE local token (`cycle_degraded`); the instance
  attribute `self._fetch_degraded` is retained ONLY as an observability
  mirror with byte-identical sequential semantics (set on degrade, consumed
  in Phase 3, `False` after any completed cycle). Sequential behavior is
  unchanged by construction and pinned by test.
- **Concurrency + regression tests** (`backend/tests/test_refresh_degraded_token_concurrency.py`,
  3 tests):
  1. `test_interleaved_fresh_cycle_must_not_steal_degraded_cycle_marker` —
     THE reproduction: two orchestrated refresh cycles; the yield point is
     injected through the service's own lock seam (`SeamLock`: one pure
     `asyncio.sleep(0)` control yield per acquisition + a one-shot hook);
     cycle B is driven to its Phase-1 fresh write INSIDE cycle A's
     Phase-1→Phase-3 span, then stalls before its own Phase 3; a Phase-4
     broadcast spy snapshots cycle A's `_last_fetch_ts` (decisive
     observable). Fails on the shared-attribute shape (proven above),
     passes with the per-cycle token.
  2. `test_sequential_cycles_unchanged_no_interleaving` — sequential-
     semantics pin that must hold before AND after the fix (fresh cycle
     stamps; subsequent degraded cycle preserves the timestamp untouched).
  3. `test_mirrored_attribute_matches_cycle_outcome_after_completion` —
     observability-mirror contract (attribute `False` after any completed
     cycle, byte-identical to the pre-fix sequential semantics pinned by
     the existing `test_refresh_false_fresh.py`).
- Determinism: no network (provider stub with manually-resolved futures;
  `DATA_SOURCE=mock` pinned by conftest), injected timestamps only, loop
  ordering driven by explicit future resolutions + the one-yield seam +
  observable-state polling; no sleeps > 0.
- Disposition delta vs the CONSOL-NEXT record: Q-1 was ANALYZED_AND_DEFERRED
  there because "no deterministic failing reproduction exists without
  altering production code shape". THIS wave found the deterministic
  reproduction (the lock-seam injection makes the latent hazard observable
  without any production test-hook) and the owner directive explicitly
  ordered the fix prioritized — so the deferred state is superseded by a
  FIXED_AND_REGRESSION-PINNED disposition with the reproduction evidence
  above. The prior record text is preserved verbatim (forward-only
  discipline); this section is the currency correction.

## 3. Work in this wave — WS-D (AI-3 persistence readiness, no owner decision)

Directive §5 WS-D: prepare adapters/migration tests only to the extent the
approved architecture and owner decisions allow; do NOT select a production
backend; do NOT enable destructive retention/purge.

- **TEST-LAYER-ONLY JSONL reference adapter** (`backend/tests/research_memory_jsonl_reference.py`,
  383 lines, `JsonlFileResearchMemoryStore`): a pluggability PROOF for the
  `ResearchMemoryStore` Protocol behind the scaffold's `STORE_FACTORIES`
  registry — NOT a persistence-backend decision (D1–D7 remain ALL PENDING,
  packet lines 3–6; §11 execution gate still binds). Zero production wiring:
  lives under `backend/tests/`, imported by tests only, no `app.core`/
  `app.data`/`app.api`/`app.services` import (AST-verified by RT-6), no
  config surface, not wired into any runtime.
  - Architecture: composition-by-delegation — the sole behavior authority is
    the delivered contract pair (`EpisodicRunArchive` + `SemanticLessonStore`)
    wrapped behind an `InMemoryResearchMemoryStore` view rebuilt per commit;
    the JSONL file leg is a persistence CARRIER only.
  - Storage discipline: canonical JSON lines (UTF-8, binary append — no OS
    newline translation in digest scope), fsync per line, per-line sha256
    sidecar (digest over canonical text WITHOUT the newline framing byte).
  - APPEND-ONLY / NO-PURGE: writes create or refuse; never mutate, truncate,
    rewrite or purge; NO retention-expiry path exists. A torn/corrupt line is
    permanent evidence: ignored AS A RECORD, refused IN VERIFICATION; the
    store never heals the file (repair = owner DR under D5, restoration not
    rewriting).
  - FAIL-CLOSED: an unverified store refuses further appends
    (`file_integrity_unverified`) BEFORE any I/O; verification refusals are
    returned records, never exceptions. Contract pre-checks run before any
    I/O (idempotent re-append and conflict/chain refusals write nothing);
    fsync before state commit (all-or-nothing).
  - Concurrency class: SINGLE-WRITER (external harness lock + internal
    `threading.Lock`); no multi-writer guarantee anywhere.
- **Dedicated adapter tests** (`backend/tests/test_ai3_jsonl_reference_adapter.py`,
  9 tests): round-trip reopen with preserved PIT ordering and digest
  verification; digest-mismatch refusal; torn-tail detection + refusal +
  fail-closed write gate; idempotent re-append writes nothing; conflict
  refusal writes nothing; sidecar corruption refusal; export/import
  directory round-trip; RT-6 zero-production-wiring proof (AST import scan —
  only `app.domain.*` permitted, `app.core`/`app.data`/`app.api`/
  `app.services` structurally forbidden); RT-7 factory conformance (Protocol
  surface exactness + forbidden-method token sweep: update/remove/delete/
  purge/expire/expiry/retention/rewrite/prune/evict/clear/pop/drop/truncate/
  vacuum absent from the public surface; fresh-empty per call).
- **Scaffold registry extended** (`backend/tests/test_ai3_acceptance_scaffold.py`,
  +1 factory row, docstring updated): `STORE_FACTORIES` now drives the
  identical 22-test Tier-A suite over BOTH factories (`in_memory_reference`,
  `jsonl_file_reference`) — 44 parameterized tests, zero test-body changes.
  This is the mechanism any future production adapter (post-D1) plugs into:
  ONE factory entry, no test edits.
- **No owner decision exercised**: no D1–D7 option selected, assumed, or
  pre-recorded; the adapter is explicitly labelled NOT-a-decision in module
  docstring, class docstring, factory docstring, and test assertions.

## 4. In-cycle defect found and fixed (additive hardening, not a weakening)

- `test_rt6_reference_adapter_is_test_layer_only_zero_production_wiring`
  initially asserted raw string containment (`"app.data" not in source`),
  which false-failed on the adapter's own docstring PROSE ("no `app.core`/
  `app.data` reference"). Fixed by replacing string containment with an
  AST-level import scan (stronger AND precise: import-graph truth, immune to
  prose). No assertion was weakened — the AST check subsumes the string
  check and additionally enumerates every `app.*` subtree actually imported.

## 5. Integration verification (orchestrator, at the wave HEAD)

- Focused: Q-1 concurrency file 3/3; JSONL adapter file 9/9; scaffold
  44/44 (22 tests × 2 factories). Delta arithmetic: 3 + 9 + (44 − 24) = 32
  new test nodes → full battery 1404 + 32 = **1436 passed / 1 skipped /
  2 warnings in 12.69 s, exit 0** — reproduced at the wave HEAD.
- pyflakes: `backend/app/services/market_service.py` exit 0 (empty); all
  three new/modified test files exit 0 (empty).
- Secret-pattern sweep over the four touched files: zero hits.
- No-purge token scan over the new AI-3 adapter: prohibitions only (lines
  28–29), zero functional purge/retention/expiry path.
- Gates unchanged: `AI2_ENABLED=0` (`backend/app/core/config.py:111`),
  `verified=False` (`config.py:284`), `execution_mode=SYNTHETIC_OR_PAPER`,
  zero `ai2` references under `backend/app/api/`, AI-5 kill-switch default
  ENGAGED, no live-trading/order-execution path.
- Workspace discipline: only the five wave files staged (2 modified + 3
  new); the untracked bootstrap set (`.claude/`, `CLAUDE.md`,
  `docs/governance/PROJECT_EXECUTION_STATE.md`, `docs/governance/evidence/`,
  `scripts/r13_owner_repo_setup.sh`, `scripts/validate_bootstrap_config.py`)
  untouched; no stash left; single worktree.
- No existing test modified, weakened, skipped, or deleted. No historical
  record text altered (forward-only; the Q-1 disposition correction is
  additive in this record).

## 6. Publication

- Forward-only commit on `main` (no amend/rebase/reset/force); push via the
  authorized deploy-key path; remote read-back verified; required CI jobs
  re-verified on the exact post-wave SHA (STATUS/CHANGELOG rows bound to it).
