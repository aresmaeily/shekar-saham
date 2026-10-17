# AI-2 G2 READINESS EVIDENCE PACKAGE (AI2-D, 2026-10-17)

Purpose: consolidate every locally reproducible piece of evidence about the AI-2
implementation into one package so that the owner and an independent G2 reviewer
can evaluate readiness **without re-deriving anything**, while keeping a hard
separation between (a) locally reproducible software checks and (b) independent
G2 acceptance, which only the owner can grant.

**This package is NOT G2 approval and does not imply it.** G2 remains
`NOT_PASSED`. Nothing here authorizes live execution, `live_verified=true`,
real-market-data AI-2, or publication. The authoritative AI-2 definition and the
authoritative G2 procedure remain owner property (see §3: amendment corpus
NOT_SYNCED); no G2 acceptance criteria are invented here.

## 1. Repository state at packaging time

> Packaging provenance: this package was prepared and the audit executed at
> `0834b19`. It is committed as part of the **AI2-D** commit — the commit that
> contains this file is that commit (`git log --oneline -1 --
> docs/active/AI2_G2_READINESS_EVIDENCE_PACKAGE.md` resolves the exact SHA).

```text
Branch:    main
HEAD:      0834b198864f8a5c06b07df777a9ad200111822f (AI2-C: Harden AI-2 async boundaries, context integrity, and input bounds)
Ancestry:  0834b19 (AI2-C) → 6cf2d93 (AI2-B) → 0af6d06 (AI2-A) → 48c1e2b (REM-1)
           → a578abe (P3.92) → 6ff6b07 (P3.93) → c1984e7 (P3.91 verified GitHub baseline)
Remote:    origin = https://github.com/aresmaeily/shekar-saham
Live check 2026-10-17 (read-only `git ls-remote origin refs/heads/main`):
           refs/heads/main = c1984e7979f89f2d727b471deb602953ec62fad5 (exit 0)
           → local main ahead 6 / behind 0; divergence = the 6 unpushed local commits listed above.
Worktree:  0 tracked modifications, 0 stashes, 1 worktree.
Untracked (bootstrap governance set, intentionally uncommitted, owner review PENDING):
           .claude/ , CLAUDE.md , docs/governance/ , scripts/validate_bootstrap_config.py
Raw evidence dirs cited by this package (all untracked, preserved):
           docs/governance/evidence/raw/2026-10-17_rem1_ai2a/
           docs/governance/evidence/raw/2026-10-17_ai2b/
           docs/governance/evidence/raw/2026-10-17_ai2c/
           docs/governance/evidence/raw/2026-10-17_ai2c_independent_verification/
           docs/governance/evidence/raw/2026-10-17_ai2d/   (battery for this package, recorded in §5)
```

## 2. What AI-2 is here (scope statement, from the implementation itself)

`backend/app/services/ai2_service.py` implements a **second-stage interpretive
analysis service** over the existing deterministic financial core: bounded typed
request contracts, deterministic stage-1 context (existing `AIContextBuilder` +
`FallbackAIProvider`), strict model-output schema validation, provenance with
verifiable hashes, deterministic failure mapping, fail-closed gates, and an
off-event-loop provider seam reusing the existing P3.83/P3.85/P3.86
`invoke_ai_provider` boundary. Model output is advisory only; deterministic
financial values come exclusively from the domain layer and are never
overwritten by model text. No HTTP route is exposed for AI-2; the owner-facing
surface is defined by the NOT_SYNCED amendments and was not invented.

## 3. Authoritative-source status (classification inputs)

| Source | Status | Consequence |
|---|---|---|
| In-repo governance (STATUS/CHANGELOG/INDEX/handoff/record §1–§7, P3.87–P3.91 audits) | Available | Category A scope established and implemented (matrix §4) |
| 5 owner amendment files expected under `docs/governance/amendment_sources_2026-10-02/` (`02_EXECUTION_ROADMAP_CURRENT…`, `02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE…`, `03_AI_GOVERNANCE_BOUNDARIES…`, `04_17_ROLE_GOVERNANCE_CHARTER…`, `05_GOVERNANCE_DECISION_REGISTER…`) | **NOT_SYNCED** — directory absent, verified 2026-10-17 (`ls` exit 2) | The authoritative AI-2 task list, route/UX surface, output-schema fields, and the authoritative G2 procedure CANNOT be established from this repository. Not reconstructed. All criteria they alone define are classified BLOCKED (B). |
| Live provider credentials / infrastructure | Absent | Real provider contract tests and any live path BLOCKED (B/C) |
| G2 independent validation + owner acceptance | NOT_PASSED | Real-data AI-2 execution BLOCKED (C); enabling `AI2_ENABLED=1` outside tests BLOCKED (D) |

## 4. Criterion-by-criterion acceptance matrix

Vocabulary per mandate: PASS = implementation + adequate evidence verified here;
FAIL = reproducible defect (none found — see §6); BLOCKED = requires missing
authoritative documents / owner approval / credentials / external access / G2;
NOT_VERIFIED = evidence insufficient to decide. Evidence = implementation
location + named tests (all in `backend/tests/test_ai2_service.py`, 40 tests)
+ battery runs in §5. Every named test was executed at HEAD `0834b19` in this
session (40/40 passed) and its body was inspected, not just its name.

### 4a. Category A implementation criteria — PASS

| # | Criterion | Implementation | Evidence (tests) | Status |
|---|---|---|---|---|
| A1 | Bounded request contract: question ≤2000, symbol ≤64, filter_expr ≤2048, language ≤16; `backtest_result` JSON-serializable ≤64 KiB, fail-closed at construction | `AI2Request` + `_bounded_payload` (`ai2_service.py:88-134`) | `test_ai2_request_bounds_enforced` | **PASS** |
| A2 | Payload nesting depth bound (iterative, no recursion on attacker input); NaN/Infinity rejected as non-RFC-8259 | `_check_depth` (`:104-115`), `allow_nan=False` (`:127`), `RecursionError` belt (`:128-129`) | `test_ai2_request_rejects_deep_nesting` (25/100/1000 rejected, 24 accepted, wide-shallow legal), `test_ai2_request_rejects_non_json_values_without_payload_echo` | **PASS** |
| A3 | Strict model-output schema: `extra="forbid"` (unknown/forged fields fail), item bounds ≤500×20, confidence ∈ [0,1] | `AI2Interpretation` (`:137-150`) | `test_ai2_interpretation_rejects_unknown_fields`, `test_ai2_boundary_limits_accepted`, `test_ai2_confidence_bounds_enforced`, `test_ai2_schema_rejects_wrong_types` | **PASS** |
| A4 | Deterministic stage-1 integration: `FallbackAIProvider` analysis feeds the prompt, recorded as `deterministic_context.stage1`, recorded-not-raised degradation (unsupported task / exception → `available=False` + error code, type name only) | `_stage1_analysis`, `_bounded_stage1` (`:263-289`) | `test_ai2_stage1_present_traceable_and_idempotent`, `test_ai2_stage1_failure_degrades_deterministically`, `test_ai2_missing_symbol_context_recorded_hashed_and_prompted` | **PASS** |
| A5 | Fail-closed trust-state enforcement before any provider invocation; gate ordering AI2_ENABLED → trust-state → G2/`is_verified_live` | run() Gates 1–3 (`:345-403`) | `test_ai2_unavailable_data_gated_fail_closed`, `test_ai2_missing_trust_state_gated`, `test_ai2_disabled_by_default_gates_before_transport`, `test_ai2_production_path_blocked_by_g2_gate` (spy transport proves gated paths invoke nothing) | **PASS** |
| A6 | Input hash covers the exact stage-1-aware deterministic context; prompt hash covers the exact prompt payload | `_input_digest` over `deterministic_context` (`:214-219`), `prompt_sha256` over built prompt (`:419`) | **Mandatory integrity review — PASS**: `test_ai2_input_hash_verifiable_from_returned_context` (re-digests the returned context; idempotent), `test_ai2_prompt_hash_rebuilds_from_recorded_inputs` (rebuilds via `build_controlled_provider_prompt` from recorded task/trust/stage-1 + question, incl. degraded missing-symbol shape), `test_ai2_input_hash_sensitive_to_backtest_and_question` | **PASS** |
| A7 | Model output cannot mutate deterministic facts (advisory only) | structural (model text never enters context) + strict schema | `test_ai2_model_output_cannot_override_deterministic_values` (claiming `entry_score=999` leaves context bit-for-bit identical to gated run; domain value 75 stands) | **PASS** |
| A8 | Provenance completeness on every outcome path: 64-hex input hash, parseable UTC timestamp, trust state, provider identity, full gate dict; prompt hash iff prompt built; `provider_attempts` iff seam reached | `AI2Provenance` + `_base_provenance` (`:153-258`) | `test_ai2_provenance_complete_on_every_outcome` (8 outcome paths: disabled / unavailable / missing trust / G2 gate / timeout / failed schema / executed_shadow / future executed), `test_ai2_provider_attempts_recorded_or_none` (valid/invalid/missing) | **PASS** |
| A9 | Async invocation off the event loop; cancellation containment: late provider success/failure after caller cancellation is discarded (no fabricated result, no downstream state, instance reusable); cancellation before seam reaches no invocation | `asyncio.to_thread` seam call (`:421-426`); stateless singleton | **Mandatory cancellation review — PASS**: `test_ai2_cancellation_during_slow_provider_late_success_discarded` (threading.Event proves the worker completes LATE; `task.cancelled()`; `vars(svc).keys()=={"_context_builder"}`; reuse), `test_ai2_cancellation_late_provider_failure_discarded_and_reusable`, `test_ai2_cancellation_before_seam_no_invocation` (spy seam), `test_ai2_cancellation_propagates_no_fabricated_result`. **Limitation honestly documented** (§6): cancellation does NOT terminate the worker thread — tests prove the opposite. | **PASS** |
| A10 | Deterministic failure mapping: timeout → `provider_timeout`-class code, HTTP 4xx no-retry, seam non-dict contract violation → `provider_contract_violation`, empty/whitespace/non-object/malformed model output → `failed_schema` with bounded error codes (no payload echo) | run() failure branches (`:428-490`), `_parse_interpretation` (`:221-237`, records count + field paths only) | `test_ai2_timeout_maps_deterministically`, `test_ai2_http_4xx_no_retry`, `test_ai2_seam_contract_violation_non_dict_maps_failed_provider` (None/list/str), `test_ai2_schema_rejects_malformed_json`, `test_ai2_empty_output_from_ok_seam_maps_failed_schema`, `test_ai2_whitespace_only_output_maps_empty_output`, `test_ai2_non_object_output_maps_schema_not_object`, `test_ai2_missing_required_fields_maps_schema_error` | **PASS** |
| A11 | Secret-free logs and errors incl. exception paths | `_log` (`:331-343`, structured fields only: status/task/error_code/gate states/hash prefix/transport flag); stage-1 exceptions record `type(exc).__name__` only; seam `warning` field is a static bounded string (verified `ai_provider.py:224,238,258,403` — no exception text, no secrets) | `test_ai2_no_secret_material_in_result_or_logs` (question text and stage-1 content asserted absent from records) | **PASS** |
| A12 | Concurrency isolation and idempotency on the shared singleton | stateless design (only `_context_builder` attribute) | `test_ai2_concurrent_runs_isolated` (no cross-contamination of context/warnings/hashes), input-hash idempotency assertions in A6 tests | **PASS** |
| A13 | Test-transport isolation: injected transport can only yield `executed_shadow`; "executed" unreachable with mock output; accidental live-call prevention | run() shadow branch (`:493-504`); every seam-reaching test mocks the seam (injected transport or monkeypatched `ai2_module.invoke_ai_provider`); gated paths use raising spy transports | `test_ai2_test_transport_never_yields_executed_status`, `test_ai2_future_live_gated_path_maps_executed` (trust fixture crafted + seam monkeypatched — provenance records `live_verified=True` **only inside this unit-test fixture**; `build_data_trust_context` cannot mint it in the product) | **PASS** |
| A14 | Exact inter-stage value transfer (not mock call-counting): transport receives task, trust STATE, exact prompt (≤2000 chars, contains task line, trust state, `live_verified: false`, question, stage-1 summary + first observation); model values pass through unchanged | run() prompt/payload construction (`:409-426`) | `test_ai2_inter_stage_values_exact` | **PASS** |

### 4b. Runtime / production / governance criteria — BLOCKED (real causes, not invented around)

| Criterion | Status | Blocker class | Exact blocker |
|---|---|---|---|
| AI-2 execution against real market data | **BLOCKED** | C (G2) + B | G2 NOT_PASSED; production path additionally structurally unreachable (`is_verified_live` cannot be minted — `config.build_data_trust_context` hard-codes verified=False) |
| `live_verified=true` transition | **BLOCKED** | C + owner | No authorized live verification has occurred; changing it would violate §8 boundaries |
| Owner-facing AI-2 route / UX surface | **BLOCKED** | B (NOT_SYNCED) | Defined by the 5 absent amendment files; not invented here (no route exists by design) |
| Authoritative AI-2 task list, request/response schema fields, language requirements | **BLOCKED** | B (NOT_SYNCED) | Amendment corpus absent; current Category A contract explicitly marked as superseded when the owner supplies the amendments (`AI2Request` docstring) |
| Real provider contract tests (live OpenAI/Gemini-class) | **BLOCKED** | B (credentials) | No LLM credentials in this environment |
| Enabling `AI2_ENABLED=1` outside tests; any use of AI-2 output beyond advisory | **BLOCKED** | D (owner acceptance) | Owner decision PENDING (packet item) |
| Authoritative G2 procedure / acceptance criteria | **BLOCKED** | B + owner | Owner-defined; cannot be established from this repository; not invented here |
| Python 3.13 CI parity, Windows-target validation, Claude CLI recognition | **NOT_VERIFIED** | Environment | Never verified in this environment (pre-existing, unchanged) |

### 4c. FAIL / NOT_VERIFIED among implementable criteria

None. No reproducible defect or unmet in-scope criterion was found in this
audit (§6). No suspected issue advanced to a fix because none reproduced a
contract violation; per mandate, no stable code was changed to create activity.

## 5. Verification battery (exact, reproducible)

Primary fresh run for this package — HEAD `0834b19`, 2026-10-17T05:24Z window,
Python 3.12.15 venv, raw evidence incl. per-command exit codes and durations:
`docs/governance/evidence/raw/2026-10-17_ai2c_independent_verification/`
(`00_context.txt` records HEAD, subject, interpreter, tracked_dirty=0 pre and
post; `00_exit_codes.txt` records every exit code and duration):

| Command (cwd `backend/` unless noted) | Exit | Result |
|---|---|---|
| `.venv/bin/python -m pytest -q` | 0 | **348 passed, 2 warnings in 77.30s** (77.95s wall) |
| `.venv/bin/python -m pytest tests/test_ai2_service.py -q` | 0 | **40 passed** in 0.94s |
| `.venv/bin/python -m compileall -q app tests` | 0 | clean |
| `PYTHONPATH=. .venv/bin/python -m pyflakes app tests` | 0 | 0 findings (was 7 pre-REM-1) |
| `.venv/bin/python -m pip_audit` | 0 | "No known vulnerabilities found" |
| `git diff --check` (repo root) | 0 | clean |
| `.venv/bin/python scripts/validate_bootstrap_config.py` (repo root) | 0 | 8/8 checks PASS, 0 FAIL |

The 2 warnings are pre-existing environment deprecations, identical to the
AI2-A/B/C baselines: `StarletteDeprecationWarning` (fastapi/testclient.py:1,
httpx/testclient) and `DeprecationWarning` (starlette/testclient.py:53,
anyio BlockingPortal alias). Not introduced by AI-2 work.

Prior batteries corroborating the chain (each at its committed tree, same

evidence format): `2026-10-17_rem1_ai2a/` (320 passed @ REM-1+AI2-A tree),
`2026-10-17_ai2b/` (331 passed @ 6cf2d93), `2026-10-17_ai2c/` (348 passed @
0834b19 pre-commit and at committed SHA). Baseline lineage: 308 (c1984e7) →
320 (AI2-A) → 331 (AI2-B) → 348 (AI2-C), zero regressions at each step.

**AI2-D re-verification battery** (this package's own governance changes are
docs-only; expected no-op for tests): the full battery is re-run pre-commit and
again at the committed AI2-D SHA, raw evidence
`docs/governance/evidence/raw/2026-10-17_ai2d/` (00_context.txt records the
exact battery HEAD; 00_exit_codes.txt records every exit code and duration).
Any deviation from the 348-passed baseline is investigated, never suppressed.

## 6. Audit findings and fixes (AI2-D)

Residual audit mandate §3 checklist was executed against the actual code and
test bodies this session (not from reports): bounded fields/size/depth/collection
and numeric edges (A1–A2), strict output validation incl. forged fields (A3),
stage-1 determinism + immutability (A4, A7), fail-closed trust gates + ordering
(A5), hash derivation from exact payloads (A6 — mandatory integrity review),
provenance completeness + provider status + attempts (A8), async invocation +
cancellation + late-result containment + timeouts (A9 — mandatory cancellation
review), retry/concurrency/idempotency (A10, A12; bounded retries live in the
existing seam and surface via `provider_attempts`), secret-free logs/errors
incl. exception paths (A11), test isolation from live providers/network (A13),
compatibility with existing provider contracts and deterministic financial
calculations (A4/A7/A14; AI-2 reuses `AIContextBuilder` + `invoke_ai_provider`
without parallel architecture).

**Result: no remaining unblocked implementation gap; no FAIL.** Nothing was
changed in application code. The only new artifact is this package (AI2-D)
plus the governance pointers in §7 — per the mandate, no gap was manufactured.

## 7. Governance documents reconciled by this package (AI2-D)

- `docs/active/AI2_G2_READINESS_EVIDENCE_PACKAGE.md` — new (this file).
- `docs/active/REM1_AI2A_IMPLEMENTATION_RECORD.md` — §8 pointer added.
- `docs/STATUS.md` — AI2-D row added.
- `docs/CHANGELOG.md` — AI2-D entry added.
- `docs/active/INDEX.md` — AI2-D entry added.
- `RADAR_BOURSE_MASTER_HANDOFF.md` — appendix updated (commits chain now …→ AI2-C `0834b19` → AI2-D).
- `docs/governance/PROJECT_EXECUTION_STATE.md` — already reconciled to `0834b19` earlier the same day (untracked governance set; §2d records AI2-B/C + the independent battery); no further tracked-content change required by AI2-D.

Commit: recorded in the handoff/CHANGELOG after the local commit is created
(tracked change, committed locally, NOT pushed). See handoff "Local commits"
chain for the exact SHA.

## 8. Known limitations (honest, evidence-linked)

1. **Cancellation does not terminate the worker thread.** `asyncio.to_thread`
   cannot stop a running synchronous call. Containment (proven, A9): a late
   provider completion is discarded — it can never be returned to a cancelled
   caller or committed to downstream state, because the service is a stateless
   singleton and the result object is only ever handed to the awaited caller.
   The worker thread itself finishes in the background and its result is dropped.
2. **Provider/network isolation in tests is structural, not enforced by a
   socket-blocking conftest.** There is no `conftest.py` socket guard in this
   repo. Isolation holds because every seam-reaching test injects a mock
   transport or monkeypatches the module-level seam symbol, and every gated
   path uses a raising spy transport. The production (transport-less) path is
   additionally unreachable in this repository (Gate 3 cannot pass — see §4b).
3. **Hash scope**: `input_snapshot_sha256` digests the canonical JSON of the
   returned `deterministic_context` (sorted keys, compact separators,
   `default=str` as a belt for any non-JSON-native stage-1 value); it is
   verifiable from the artifact alone (A6). It intentionally does NOT digest
   the raw request object.
4. **Category A scope is provisional by design**: the NOT_SYNCED amendment
   corpus may define a different request/response surface; the implementation
   documents that the amendments supersede it when supplied.
5. **Two pre-existing warnings** (starlette/anyio deprecations) are
   environmental and pre-date AI-2 work (§5).

## 9. No-live-execution confirmation

During every verification run recorded here (AI2-A/B/C batteries and this
package's battery at `0834b19`), **no live LLM invocation and no
real-market-data AI-2 execution occurred.** All AI-2 executions were mock-based
offline unit tests (injected test transports / monkeypatched seam); the
production path never executed because Gate 3 is structurally unreachable and
`AI2_ENABLED` defaults off. `live_verified=false` everywhere; G2 NOT_PASSED;
LLM NOT EXECUTED.

## 10. Outstanding dependencies for G2 and beyond

| Dependency | Class | Holder |
|---|---|---|
| 5 amendment files (2026-10-02) into `docs/governance/amendment_sources_2026-10-02/` | NOT_SYNCED | Owner (originals only; never reconstructed) |
| G2 independent validation of AI-2 (procedure owner-defined) | BLOCKED | Owner + independent validator |
| Owner acceptance to enable `AI2_ENABLED` outside tests | BLOCKED (D) | Owner (packet §8 items PENDING) |
| Live provider credentials + authorized live validation run | BLOCKED (B/C) | Owner |
| Push/publication authorization (local main ahead 7 as of the AI2-E reconciliation 2026-10-17; ahead 6 at packaging time) | BLOCKED | Owner |
| Windows INSTALL / Python 3.13 parity / Claude CLI recognition | NOT_VERIFIED | Owner environment |

**Next smallest authorized action** (no boundary crossed): owner supplies the
amendment corpus — that single act unblocks the authoritative AI-2 acceptance
criteria, the route/UX definition, and the authoritative G2 procedure, and
everything already built here (40 tests, verifiable provenance, containment
proofs) becomes directly checkable against the authoritative definitions.
