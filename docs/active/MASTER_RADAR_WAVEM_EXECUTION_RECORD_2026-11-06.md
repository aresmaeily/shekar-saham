# MASTER-RADAR WAVE-M EXECUTION RECORD — INTERNAL SCHEDULER (OA-4) — 2026-11-06

Directive: OWNER AUTHORIZATION & CONTINUOUS EXECUTION DIRECTIVE (2026-11-05,
OA-1..OA-8). This record covers **WAVE-M**: the bounded LOCAL internal
research scheduler, executed per directive §2 (15-agent ownership protocol,
ownership table published BEFORE any file edit) and §3 WAVE-M. Baseline:
`a944620` (origin/main == local, 0/0; doc HEAD `6d78a842` and WAVE-H code
anchor `86f28c24` re-verified as ancestors; tracked tree clean; untracked
governance artifacts preserved; battery 2904/1s/0f at baseline).

## 0. Task ownership table (published before any edit — directive §2)

| # | Agent role | File ownership this wave | Status |
|---|---|---|---|
| 1 | Chief Execution Orchestrator | coordination, final review, merge authority, STATUS currency | executed |
| 2 | AI-2 Architecture | `app/services/ai2_generation.py`, `app/api/ai2_generation_api.py` | read-only (WAVE-K/L accepted; NOT reopened) |
| 3 | AI Provider | `app/services/ai_service.py` | read-only (OA-2: real providers stay disabled) |
| 4 | DSL/Sandbox | RSL-1/UIDL-1 engines | read-only |
| 5 | AI-2 QA | `backend/tests/test_ai2_*.py` | read-only regression watch |
| 6 | Prediction Persistence | `app/services/prediction_store.py` | read-only (pattern donor) |
| 7 | Research Scheduler | NEW `app/services/scheduler_run_store.py`, `app/services/internal_scheduler.py`, `app/services/scheduler_jobs.py`, `app/api/scheduler_api.py`; NEW `backend/tests/test_internal_scheduler.py`, `backend/tests/test_scheduler_api.py`; additive edits `app/core/config.py`, `app/main.py` | **executed (wave core)** |
| 8 | Windows Packaging | `electron/`, `windows-installer.yml` | standby (WAVE-N remainder) |
| 9 | Windows Security | electron security review | standby |
| 10 | Market Data | providers / data quality | read-only (OA-2 disabled) |
| 11 | Frontend | `frontend/` | standby (WAVE-O) |
| 12 | Integration | cross-surface battery run | executed (verification) |
| 13 | Independent QA/Audit | fresh adversarial audit (read-only) | executed — verdict PASS, 4 MEDIUM findings, ALL remediated in-wave |
| 14 | Documentation | this record + CHANGELOG section | executed (docs-only) |
| 15 | Release | commit/push + exact-SHA CI evidence (OA-7) | executed at push time |

## 1. Architecture (what was built — additive only, zero existing-code deltas)

- **`app/services/scheduler_run_store.py`** — durable append-only run history
  (the OA-4 analogue of the WAVE-J OA-5 discipline): SQLite/WAL,
  `synchronous=FULL`, pinned schema migration v1 with SQL-text digest
  (mismatch fails closed), row integrity digests verified on open
  (tamper fails closed), closed event-type set, unique `event_id` with
  idempotent byte-identical re-append (conflicting reuse rejected),
  timestamped backup rotation with verified restore (fail-closed),
  `MemorySchedulerRunStore` = process-local adapter for UNIT TESTS ONLY
  (never a default; `SCHEDULER_STORE_BACKEND=memory` is an explicit test
  choice). Scheduler-level lifecycle events (PAUSED/RESUMED/STOPPED/KILL_*)
  carry the sentinel `run_id=""` and are excluded from the run index —
  no phantom pseudo-runs.
- **`app/services/internal_scheduler.py`** — the bounded LOCAL scheduler:
  fail-closed `enabled` flag injected ONCE by the composition root (the
  service NEVER reads/writes settings after construction — structurally
  pinned: `get_settings` appears exactly twice, both inside
  `get_scheduler()`; `AI2_ENABLED`/`os.getenv` zero); bounded queue
  (queue-depth cap), run identity (uuid), idempotency keys (identical
  key+job_type+payload → replay with NO re-execution; any difference →
  `idempotency_conflict`), max-concurrency cap, per-run wall-time budget
  with late-completion containment (a result after timeout/kill is
  DISCARDED, never committed), pause/resume/stop (graceful; queued runs
  cancelled immutably), kill-switch (ENGAGE cancels BOTH the wrapper and
  the inner handler task, blocks enqueue, records KILLED; RELEASE re-arms),
  bounded retries (exhausted attempts → immutable DEAD_LETTERED), restart
  recovery (non-terminal runs closed INTERRUPTED at startup — never
  silently dropped, never auto-resumed), per-run provenance (actor,
  payload digest, attempts, injected-clock durations, config fingerprint,
  `execution_domain=SYNTHETIC_OR_PAPER`), honest posture envelope.
  NO network client anywhere (structurally pinned); NO egress, NO broker,
  NO notification surface, NO promotion or production-mutation authority;
  handlers run UNDER their own governance — the scheduler cannot open a
  gate the underlying seam does not already open.
- **`app/services/scheduler_jobs.py`** — closed job registry: exactly ONE
  built-in job type `research_loop`, delegating to the EXISTING governed
  research-loop runner (`AI2ResearchLoopRunner` over a transport-less
  `AI2Service()`): with the committed defaults the honest outcome is
  `gated_not_executed` → ledger `GATED_NOT_EXECUTED` — scheduling CANNOT
  execute anything the AI-2 gates do not open. Payload validation into the
  existing `AI2ResearchRunInput` contract happens BEFORE anything executes;
  malformed payloads are refused with nothing run and nothing ledgered.
- **`app/api/scheduler_api.py`** — generic HTTP surface `/api/v10/scheduler`
  (posture / runs enqueue+list+detail / control pause·resume·stop /
  kill-switch / history-verify) with honesty envelope on every payload and
  gate-first refusal codes (503 `scheduler_disabled`, 409 conflicts,
  423 kill engaged, 429 queue full, 413 oversized). **G2 counter-pin
  discipline preserved: the file contains ZERO `ai2` tokens
  (`\bai2\b` case-insensitive = no hits) and spawns no background task —
  the AI-2 HTTP surface remains EXACTLY `ai2_generation_api.py`; the G2
  gate itself is untouched (NOT_PASSED guarantee intact).**
- **`app/core/config.py`** — additive knob block: `SCHEDULER_ENABLED`
  default **0** (fail-closed), `SCHEDULER_MAX_QUEUE=32`,
  `SCHEDULER_MAX_CONCURRENT=1`, `SCHEDULER_RUN_TIMEOUT_SEC=60`,
  `SCHEDULER_MAX_ATTEMPTS=2`, `SCHEDULER_STORE_BACKEND=sqlite`,
  `SCHEDULER_DB_PATH=""` (repo DATA_DIR default `scheduler_runs.sqlite3`).
- **`app/main.py`** — additive wiring only: router registration + lifespan
  start (refuses while the gate is closed — honest log line, product
  startup never blocks) + lifespan shutdown stop ONLY if the scheduler
  actually started (QA M2 fix: the committed gate off ⇒ shutdown records
  nothing).

## 2. Independent QA — findings and in-wave remediation

Fresh read-only adversarial audit at the untracked working tree over HEAD
`a944620` (13th agent role): **verdict PASS — no gate bypass, no egress, no
immutability/idempotency violation, recovery works, counter-pin intact**;
4 MEDIUM + 7 LOW findings, of which the MEDIUMs and L1–L3 were remediated
IN-WAVE (directive discipline: fix and re-run, never ship half-fixed):

| ID | Sev | Finding | Remediation |
|---|---|---|---|
| M1 | MEDIUM | honesty envelope claimed "every mutating endpoint refuses while the gate is closed" but `stop`/kill-switch succeeded (and wrote scheduler-level history rows) while disabled | `stop()`/`set_kill_switch()` now refuse `scheduler_disabled` when the gate is closed (zero history writes); API control endpoint returns gate-first 503; pinned by `test_stop_refused_while_disabled`, `test_kill_switch_refused_while_disabled`, `test_control_and_kill_switch_gated_by_default_503` (asserts `events_verified==0` after every refused mutation) |
| M2 | MEDIUM | lifespan shutdown unconditionally called `stop()` → a `STOPPED` row was appended on every disabled-gate shutdown | shutdown stops ONLY a scheduler whose state is running/paused; pinned implicitly by M1 service pins (disabled ⇒ refuse ⇒ nothing recorded) |
| M3 | MEDIUM | durable `runs_index` did not exclude sentinel `run_id=""` → phantom pseudo-runs (state UNKNOWN, non-terminal) appeared in the index AND in restart recovery counts | SQL filters `run_id != ''`; pinned by `test_durable_runs_index_excludes_scheduler_level_events` + `test_durable_restart_recovery_no_phantom` (real SQLite: exactly 1 real run recovered, zero phantoms) |
| M4 | MEDIUM | kill-switch cancelled the wrapper task only → the governed handler kept running detached after KILL (timeout supervision lost) | kill cancels BOTH wrapper and inner handler task; `_inner` registry added with cleanup; pinned by `test_kill_cancels_inner_handler` (cancellation flag observed, `_inner` empty) |
| L1 | LOW | idempotency identity omitted `job_type` (same key+payload+different job_type silently replayed the old run) | identity now includes job_type; different job_type under same key ⇒ `idempotency_conflict`; pinned by `test_idempotency_conflict_different_job_type` |
| L2 | LOW | dead-code `idempotency_key_exists` used a LIKE substring match contradicting the exact-match docstring | removed from all three classes (zero callers) |
| L3 | LOW | backup rotation cosmetic (fixed filename ⇒ keep never pruned) | timestamped backup filenames; `keep` now prunes honestly |
| L4–L7, I1–I4 | LOW/INFO | residual, disclosed | see §5 residuals |

## 3. Acceptance mapping (directive §3 WAVE-M → evidence)

| Directive requirement | Evidence |
|---|---|
| local internal scheduler, read-only over the product | scheduler's only side effects = store events + injected handler invocations; structural no-egress scan (`test_no_egress_structural`); no settings access after construction (`test_no_settings_access_after_construction`) |
| bounded queue | queue-depth cap → `queue_full` (429); `test_queue_cap_refused`, `test_queue_cap_429` |
| run identity + idempotency keys | uuid run ids; identical replay never re-executes (`test_idempotent_replay_never_reexecutes` call-count pin, `test_idempotent_replay_via_api` exactly-one-SUCCEEDED pin); conflict refusals (payload, job_type) pinned |
| max concurrency | `test_concurrency_cap_holds` (overlap never exceeds 1 at max_concurrent=1) |
| per-run time/resource budget | `test_run_timeout_budget_enforced`; payload ≤ 65536 B (`payload_oversized`), outcome cap with replacement marker, error ≤ 500 chars, history reads bounded (200/500/2000) |
| pause/resume/stop | `test_pause_holds_and_resume_dispatches`, `test_resume_requires_paused`, `test_stop_cancels_queued_and_refuses`, API pause/resume flow |
| restart recovery | durable restart test (real SQLite): non-terminal → INTERRUPTED, never auto-executed, exactly-once recovery, no phantoms |
| bounded retries | `test_retry_then_complete` (attempt 2 succeeds), `test_dead_letter_after_bounded_retries` (exactly 2 FAILED_ATTEMPT then DEAD_LETTERED) |
| dead-letter / failure records | same pins; dead-letter is a terminal immutable state |
| kill-switch | `test_kill_switch_engage_blocks_and_kills` + `test_kill_cancels_inner_handler` + API 423 engage/release; kill discards late completions (`test_kill_discards_late_completion`) |
| immutable run history | append-only ledger: no UPDATE/DELETE path (audit-verified); row digests fail closed on tamper (`test_durable_store_row_digest_tamper_fails_closed`); schema-digest mismatch fails closed; event-id conflicts rejected; byte-identical re-append = no-op; verified backup/restore roundtrip |
| no external notification egress | structural: zero httpx/requests/urllib/socket/subprocess/smtplib/telegram/webhook/aiohttp tokens in all scheduler modules; transitive delegation only to the transport-less governed runner |
| start from on-demand execution + default disabled | `SCHEDULER_ENABLED` default 0: start/enqueue/control/kill all refuse; lazy-start (on-demand) only fires when the gate is open; lifespan start refuses honestly |
| scheduler activation must pass §5 acceptance | §5-class acceptance executed via the battery + independent QA verdict (this record §2–§3); scheduler stays DEFAULT-OFF — any future activation in a real environment is an owner act with its own record |

## 4. Tests delta (exact)

- NEW `backend/tests/test_internal_scheduler.py` — **45 tests** (39 original
  + 6 QA-remediation pins)
- NEW `backend/tests/test_scheduler_api.py` — **18 tests** (17 + 1 gate-first
  M1 pin)
- Battery: **2967 passed / 1 skipped / 0 failed = 2904 + 45 + 18 exact**
  (46.33s local). pyflakes clean (`app/` + both new test files).
- G2 harness: `test_g2_acceptance_harness.py` + `test_g2_runtime_gate.py`
  86 passed / 1 skipped — `ai2_api_surface(backend/app/api)` = `[]`,
  `governed_seam_state` = `ok` (counter-pin intact, seam intact).
- Validators: `validate_alpha_environment` exit 0, `validate_alpha_runtime`
  exit 0, `validate_frontend_static` exit 0, `windows_package_readiness`
  exit 0.

## 5. Honest residuals (disclosed, NOT hidden)

- **L4**: in-process `_runs`/`_attempts` maps retain every run's payload for
  the process lifetime (unbounded memory growth over very long uptimes; a
  restart resets them — recovery closes history honestly).
- **L5**: durable idempotency lookup scans ENQUEUED events (O(n) with
  history growth). Bounded by practical run volumes; an index is a future
  engineering-authority change (schema v2, additive migration).
- **L6**: recovery window covers the newest 200 runs; a disabled process
  never closes stale non-terminal rows until the gate is opened.
- **L7**: a kill landing in the same instant as a success commit can leave
  both KILLED and SUCCEEDED events for one run (derived state follows the
  ledger order; both remain visible — nothing is rewritten).
- **I1**: scheduler endpoints follow the repo's existing API-auth
  convention (private-mode/api-key middleware); no additional auth layer
  added in this wave.
- **I2**: idempotency is per-process (single-worker assumption; the repo
  ships single-process uvicorn; multi-worker deployment would need a
  DB-level guard — not present today, honestly disclosed).
- **I3**: posture's `execution_domain` is a fixed label for the BUILT-IN
  registry; `register_handler` trust is caller-discipline (no untrusted
  code path reaches it in this repo).
- **I4**: the API battery pins `SCHEDULER_STORE_BACKEND=memory` at module
  import (unit-test choice; the committed production default remains
  durable sqlite).

## 6. Gates after WAVE-M (unchanged except the scheduler's own, which is NEW and fail-closed)

- `SCHEDULER_ENABLED=0` (committed default — NEW gate, fail-closed;
  nothing scheduled, nothing runs, nothing recorded)
- `AI2_ENABLED=0` (committed default, `config.py:111` byte-unchanged)
- `verified=False` (hardcoded, unchanged); LIVE gate CLOSED;
  execution mode `SYNTHETIC_OR_PAPER` everywhere
- G2 untouched (never-PASSED guarantee intact; counter-pin strengthened
  discipline preserved — exactly ONE ai2 HTTP surface)
- no egress (structural, pinned); no broker path; no promotion authority
  added; Two-Key intact; R-1..R-11 intact
- INSTALL NOT ISSUED (no installer action this wave; WAVE-N remainder next)
- **global completion: NOT CALCULATED (OA-8)**

## 7. Next waves

WAVE-N remainder (supervised local backend in the Electron shell — the
recorded runbook residual), WAVE-O (UX integration), WAVE-P (independent
acceptance + release).

## 8. Exact-SHA CI currency (OA-7 — recorded via the WebFetch egress path; the sandbox shared-IP API is rate-limited = the recorded WS-1/WAVE-I condition)

Push was BATCHED (code `20caaa0` + docs `e585085` in one push): the
intermediate SHA `20caaa0` was never individually published; its docs-only
delta is verified (`git diff --stat 20caaa0 e585085` = 3 files, all `.md`,
+210/−0) — covered by the head runs per the recorded 71fcf41/46274a3
convention. Recorded per-SHA, exactly as observed:

- **e585085 (WAVE-M records head; full WAVE-M delta vs a944620):**
  test-backend **SUCCESS** (check-run 127739142247) · build-docker
  **SUCCESS** (127739522393) · build-installer **SUCCESS** (127739142444) ·
  windows-validation **in_progress at recording time** (check-run
  127739142170, started_at 2026-11-06T05:54:43Z, >60 min in_progress at
  recording). HONEST DISPOSITION: recorded AS OBSERVED — nothing converted,
  nothing inferred. The successor SHA `3e40e66` (a strict SUPERSET of this
  code + 10 more tests, same windows job) concluded **SUCCESS** on the same
  job definition — bounding the hung run to the recorded windows-runner
  flake class (cf. the WAVE-I/J environmental-recurrence precedent), not to
  a scheduler-code defect; the e585085 job's own final conclusion stays on
  record in CI wherever it lands.
- **3e40e66 (WAVE-N remainder head; the published HEAD at recording):**
  **ALL 4 REQUIRED CHECKS SUCCESS** — test-backend (127748235489) /
  build-docker (127748578808) / windows-validation (127748234640) /
  build-installer (127748234649). The batched-push docs-only delta rule
  applies to the following docs-only commit (verified before push).
- Currency addendum: the docs-only CI-currency commit **c934efb**
  (published HEAD at session close) itself concluded **ALL 4 REQUIRED
  CHECKS SUCCESS** — test-backend (127755013914) / build-docker
  (127755284296) / windows-validation (127755014301) / build-installer
  (127755014050) — the third consecutive windows-validation SUCCESS on the
  same job definition (3e40e66 + c934efb), bounding the e585085 hung run
  definitively to the runner flake class.
- Nothing converted; a missing/failing/hung check is recorded as
  missing/failing/hung. Global completion **NOT CALCULATED** (OA-8).
