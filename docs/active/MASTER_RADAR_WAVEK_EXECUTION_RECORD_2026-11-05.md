# MASTER-RADAR WAVE-K EXECUTION RECORD — AI-2 GOVERNED GENERATION SEAM (OA-3) — 2026-11-05

Directive: OWNER AUTHORIZATION & CONTINUOUS EXECUTION DIRECTIVE (2026-11-05,
OA-1..OA-8, waves I–P). This record covers **WAVE-K**: the complete
NL → clarification → typed spec → restricted RSL generation path, wired into
the EXISTING governance pipeline (validation, sandbox, deterministic
backtest, paper replay, report, human approval, versioning). Baseline:
`3b6f15d` (origin/main verified == local, 0/0 ahead/behind; battery 2847/1s/0f
re-run exact before any edit).

## 0. Task ownership table (directive §2, published before edits)

| Package | Owner | Files (exclusive) |
|---|---|---|
| K1 governed-generation core | chief orchestrator session | `backend/app/services/ai2_generation.py` (NEW) |
| K2 API + wiring + config | chief orchestrator session | `backend/app/api/ai2_generation_api.py` (NEW), `backend/app/main.py` (additive import + include_router), `backend/app/core/config.py` (additive knobs) |
| K3 service-level adversarial battery | subagent K3 (disjoint) | `backend/tests/test_ai2_generation.py` (NEW) |
| K4 API-level battery | subagent K4 (disjoint) | `backend/tests/test_ai2_generation_api.py` (NEW) |
| Counter-pin (recorded, see §4) | chief orchestrator session | `scripts/g2_acceptance_battery.py`, `backend/tests/test_g2_acceptance_harness.py` |
| Explicitly untouched | — | `ai2_service.py`, `ai2_research_loop.py`, `ai2_governance.py`, `run_governance.py`, `strategy_dsl/*`, `strategy_lab*`, `prediction_store.py`, notifier/ws_hub, `g2_gate.py`, `G2_GATE_STATE.json`, all existing tests except the recorded counter-pin pair |

## 1. Architecture (composition-only; zero parallel AI path)

`app/services/ai2_generation.py` (service `AI2GenerationService`) composes the
EXISTING primitives and adds NO new execution machinery:

1. **Gates (fail-closed, ordered)** — `AI2_ENABLED` (default 0 →
   `gated_not_executed`/`ai2_disabled`; NOT ledgered while disabled to keep
   the immutable ledger bounded — the outcome itself carries full
   provenance); trust-state (`unavailable`/empty → refused); provider policy
   — generation is SYNTHETIC/PAPER-ONLY: a TEST transport is always
   acceptable; without one, a configured remote provider refuses
   (`real_provider_generation_not_permitted`) — real-provider generation
   stays a future owner act; duplicate suppression (identical snapshot →
   `duplicate_generation`); idempotency-key conflict
   (`idempotency_key_conflict`; same key + same payload = idempotent replay,
   no re-execution); sliding-window rate limit (injected clock); per-event-
   loop bounded concurrency semaphore (bounded 1s acquire wait);
   output-size cap; outer timeout with cancellation containment.
2. **Deterministic clarification** — intent/risk dimensions detected by
   bounded token rules (EN+FA); missing dimensions return
   `needs_clarification` with the typed question list and NO provider call.
3. **Typed-spec model surface (the ONLY model-writable area)** —
   `ModelSpecProposal` (`extra="forbid"`) over `SpecNode` expression TREES:
   whitelisted functions (the DSL's own `FUNCTION_ARITY`), whitelisted
   comparison ops, whitelisted series bases, bounded depth (≤8), node budget
   (≤48), bounded finite numerics. NO free text anywhere in the executable
   surface; `strategy_name`/`rationale` are sanitized audit-only fields.
4. **Deterministic emitter** (`EMITTER_VERSION`) — the ONLY component that
   renders RSL-1 source, from validated typed fields exclusively (INPUT
   lines sorted canonically, RISK, ENTRY, EXIT, ALERT). Prompt-injected
   content can therefore never become code — it can only fail schema
   validation or compile as an honest typed strategy.
5. **Existing compiler/sandbox** — `compile_source` (RSL-1 parser +
   typechecker + semantic validator + resource budgets) unchanged; any DSL
   error → `spec_compile_failed` (fail-closed, no auto-repair).
6. **Deterministic evaluation** — `run_backtest_on_seeded` +
   `run_paper_replay_on_seeded` on the SYNTHETIC seeded series, engines
   byte-unchanged; test-pinned that identical specs with different model
   free text produce IDENTICAL digests (model content cannot alter
   deterministic metrics), and different request symbols produce different
   digests (the caller, not the model, owns the data surface).
7. **Versioned candidate + human approval** — `GenerationCandidateRegistry`
   (in-memory, bounded 128, tamper-verifying: source SHA-256 recomputed on
   every access; tampered → approve/promote refused) with DRAFT → APPROVED →
   PROMOTED (paper-forward eligibility ONLY) — both transitions require a
   NAMED human approver; the model has no approval or promotion authority on
   any path. Approval/promotion append NEW ledger records (append-only).
8. **Append-only governance ledger** — every executed run appends an
   immutable `AI2RunRecord` (run_kind `AI2_GENERATION`, task `strategy`,
   approval_state PENDING, status LEDGERED — never COMPLETED, per the
   recorded mapping table; `governed_acceptance` therefore refuses all of
   them: the candidate registry is the approval surface).

**Provenance (OA-3 full field list — closes the WAVE-I recorded gap):**
`GenerationProvenance` carries question/clarifications/prompt/model-output/
generated-source SHA-256 hashes, model provider mode/label/identity/version,
config fingerprint (canonical JSON over schema+emitter+policy+service+DSL
versions + engine versions + data-surface params), parent_run_id,
hypothesis_id, evaluation_version (backtest+execution-model+DSL versions),
data_trust_state, execution_mode (`SYNTHETIC_OR_PAPER` via the existing
`execution_mode(False)`), test_only_transport flag, injection markers
detected, timeout budget, created_at_utc.

**Prompt-injection defense (layered):** untrusted question sanitized
(control chars stripped, bounded) + wrapped in canonical delimiters with an
explicit DATA-not-instructions preamble; strict schema (extra=forbid) as the
hard boundary; typed-only emitter path; injection-style markers detected and
RECORDED (audit flag — never compiled); secret-material scan on model output
(`suspected_secret_in_output`, value never echoed).

**Egress honesty:** the module imports no notifier/ws_hub/broker surface and
constructs no network client (test-pinned by source scan); no scheduler; the
provider seam is invoked only through the existing fail-closed
`invoke_ai_provider`.

**Runtime wiring (K2):** new router `/api/v10/ai2` (additive):
GET /posture (honest posture, honest while disabled) · POST /generate ·
GET /candidates · GET /candidates/{id} · POST /candidates/{id}/approve ·
POST /candidates/{id}/promote (response discloses PAPER-FORWARD scope) ·
GET /runs (append-only ledger tail). Every payload carries the honesty
envelope (SYNTHETIC_OR_PAPER label, model-authority disclosure, in-memory
registry disclosure, no-egress disclosure). `main.py` registration is
additive with the WAVE-K comment. `config.py` gains four additive bounded
knobs (`ai2_gen_max_concurrent=2`, `ai2_gen_timeout_sec=45`, `ai2_gen_rate_per_minute=6`,
`ai2_gen_output_max_bytes=65536`) with OA-3 provenance comments — the
fail-closed `AI2_ENABLED` gate above them is byte-unchanged (config.py:111).

## 2. The recorded counter-pin (G2-C-iii-3; NOT a weakening)

The WAVE-C-era harness predicate `G2-C-iii-3` ("no AI-2 HTTP route — zero
ai2 references under backend/app/api") mechanically pinned the OLD posture
in which the seam was disconnected by design. OA-3 authorizes exactly ONE
governed AI-2 HTTP surface, so the predicate was counter-pinned to a
STRICTER form, recorded here per the repo's established counter-pin
convention (tabs 25→26→29/30 precedent):

- OLD contract: zero ai2 references under app/api.
- NEW contract: ai2 references confined to EXACTLY `ai2_generation_api.py`
  AND that seam file must exist AND carry the fail-closed gate tokens
  (`AI2_ENABLED` + `gated_not_executed`). Any OTHER ai2 reference anywhere
  under app/api is still a violation; a missing or ungated seam is a
  violation. New harness helper `governed_seam_state()`; four negative tests
  (synthetic route detected / seam exempt from reference scan / ungated seam
  detected / missing seam detected).
- UNTOUCHED: `evaluate_g2_gate`, `g2_gate.py`, `G2_GATE_STATE.json`, the
  harness's structural never-PASSED guarantee (`test_harness_never_passes_g2`
  green), and every other harness predicate. The G2 verdict remains
  NOT_PASSED; nothing was made to "look operational" — the seam's default
  posture is DISABLED.

## 3. Tests (K3 + K4) — the OA-3 §4 acceptance mapping

K3 `tests/test_ai2_generation.py` (33 tests, subagent-authored against the
frozen interface): gated default; happy-path e2e with complete provenance;
metrics model-text independence; needs-clarification (no provider call);
clarification satisfied; prompt-injection markers recorded AND excluded from
source; oversized question (ValidationError); control-char stripping;
malformed JSON; non-RFC8259 NaN constant; unknown schema field; deep hostile
nesting (emiter depth/node budget); unknown function (`eval` refused);
fabricated data fields; data-trust unavailable; SYNTHETIC labeling
everywhere (no `"live"` substring); remote provider without transport
refused (egress structurally impossible); fallback provider honest failure;
provider failure/exception mapping; timeout refusal with nothing committed;
cancellation discards late response (nothing recorded); duplicate
generation; idempotent replay (transport invoked exactly once);
idempotency-key conflict; rate exhaustion; concurrency limit; secret
material refused (never echoed); unauthorized promotion refused;
provenance-mismatch tamper fail-closed; ledger append-only shape (no
update/delete surface); honest posture; module constructs no network client.

K4 `tests/test_ai2_generation_api.py` (14 tests): posture honesty; gated
generate with empty candidates AND zero ledger growth; request validation
422s; success path through the REAL router (TEST-only transport injected via
the service subclass pattern, disclosed `test_only_transport=True`);
duplicate refusal over the API; candidate list/get + 404; named-approver
enforcement (422 on short approver); promote-requires-APPROVED (422) then
PROMOTED with paper-forward scope disclosure; unknown candidate 404; runs
endpoint append-only shape (PENDING→APPROVED→APPROVED); no-live-label sweep;
disabled-gate-not-ledgered; honesty envelope fields; rate-limit identity
isolation (distinct TestClient identity `ai2-gen-api`:12431).

Harness counter-pin tests: +3 net (confined-surface green + 3 negative
cases replacing the superseded zero-reference pin).

**Battery: 2897 passed / 1 skipped / 0 failed = 2847 + 33 + 14 + 3 exact**
(36.46s). pyflakes clean on all new/edited files. `git diff --check` clean.
Gates byte-verified: `AI2_ENABLED` default "0" (config.py:111, additive-only
diff), `verified=False` untouched, `SYNTHETIC_OR_PAPER` untouched
(g2_gate.py:277).

## 4. Subagent deviations (verified against module source, accepted)

- `invoke_ai_provider` normalizes a transport returning `ok=False` without
  text to `malformed_response` — the deterministic-typed-mapping tests pin
  the seam's normalized codes (`malformed_response`, `transport_unavailable`)
  and monkeypatch the seam only for the `provider_exception:*` branch.
- The service clamps `timeout_sec` to ≥1.0s; the timeout test sleeps 1.6s so
  the timeout provably fires.

## 5. Gates

Unchanged: `AI2_ENABLED=0` (config.py:111 — committed default; WAVE-L may
enable it ONLY in an isolated dev/paper runtime after the §4 acceptance
review, never in the committed default) · `verified=False` mint-block ·
`SYNTHETIC_OR_PAPER` · no scheduler · no external egress · no live data path
· no purge path · Two-Key intact · R-1..R-11 in force · INSTALL NOT ISSUED.
The generation seam adds NO egress, NO scheduler, NO live path, NO broker
surface. OA-8 respected: global completion stays NOT CALCULATED.

## 6. Next waves

WAVE-L (controlled activation AFTER the §4 acceptance review — isolated
dev/paper runtime only, honest end-to-end synthetic session, provenance
recorded, Strategy-Lab display verification, disable-blocks-immediately
verification), WAVE-M (internal scheduler), WAVE-N remainder (supervised
local backend in the shell), WAVE-O (UX integration), WAVE-P (independent
acceptance + release).

## 7. Independent QA (L-QA) — findings and in-wave remediation

Independent read-only audit at HEAD 46274a3 (fresh adversarial probes; 31
probe scenarios, ZERO 500s; battery reproduced ×2 = 2897/1s/0f both; order
probes green both directions; gate sweep clean — config diff additive-only,
g2_gate.py + G2_GATE_STATE.json diff 0 bytes; counter-pin verified BITING
(ungated seam / foreign ai2 file / missing seam all detected); G2 verdict
remains NOT_PASSED; provenance hashes re-derived independently — all four
match). Findings and dispositions:

- **D-1 (MEDIUM) — concurrent duplicate-suppression TOCTOU:** six concurrent
  identical requests could each pass the gate-4 check-then-act and commit
  six candidates. **FIXED in-wave:** Stage-6 commit is now a compare-and-set
  under the snapshot lock — exactly ONE winner commits; each loser discards
  its (deterministically identical) output, is refused
  `duplicate_generation`, and is ledgered `DUPLICATE_FLAGGED` with the
  winner recorded (the invocation honestly happened; nothing rewritten).
  Pinned by 2 new tests (6-way race without/with idempotency key).
- **D-2 (LOW) — advertised period bound never enforced; docstring wrong**
  (the unchanged DSL validator's own sma/ema/highest/lowest minimum is 1, not
  the advertised 2). **FIXED in-wave:** the emitter now ENFORCES the
  advertised [2, 200] integer bound on indicator period slots
  (`sma/ema/rsi/stdev/highest/lowest` arg 1, `atr` arg 3) — deliberately
  STRICTER than the DSL validator; `ref()` offsets stay under the
  validator's own rule; docstring corrected. Pinned by 4 new tests
  (below-min, above-max, non-integer, both boundary positives).
- **LOW (K4 test) — re-promote assertion accepted a two-way disjunction:**
  tightened to the exact single error `promotion_requires_approved_state`.
- **INFO — status tautology** (`executed_shadow if transport is not None
  else executed_shadow`): made structurally meaningful — a non-test-
  transport success would honestly be `executed` (unreachable today: the
  fallback seam never yields an ok=True spec payload; kept as defense
  against future seam changes; both statuses stay LEDGERED, never
  COMPLETED).
- **INFO — raw substring grep shows `product_loops_api.py` ai2-echoes**
  (pre-existing `ai2_gate`/`ai2_enabled` settings reads, unchanged since
  before 3b6f15d): the recorded predicate scans `\bai2\b`, under which those
  identifiers do not match; noted here so the scan vocabulary is explicit.

Post-remediation battery: **2903 passed / 1 skipped / 0 failed = 2897 + 6
exact** (36.83s). pyflakes clean. Gates byte-unchanged.
