# AI-2 G2 REVIEWER CHECKLIST (AI2-E, 2026-10-17)

Purpose: the reviewer-facing working document for the authorized G2 review of
AI-2. It accompanies — and never replaces —
`docs/active/AI2_G2_READINESS_EVIDENCE_PACKAGE.md` (AI2-D), which holds the full
evidence text for every row summarized here.

**This checklist is not G2 approval and grants nothing.** G2 remains
`NOT_PASSED`. The authoritative G2 procedure is owner property and has NOT
arrived (amendment corpus `NOT_SYNCED`, §10 below); no G2 acceptance criterion
is invented in this document. Where a criterion cannot be established from
sources actually available in this repository, it is labeled `BLOCKED` or
`NOT_VERIFIED` — never assumed.

## 1. Reviewed commit and repository state

- Reviewed commit: `56deaff772c90c68c325edb292533717d9360660` (AI2-D: Close
  AI-2 residual audit and add G2 readiness evidence package) on `main`.
- Ancestry: `56deaff` (AI2-D) → `0834b19` (AI2-C) → `6cf2d93` (AI2-B) →
  `0af6d06` (AI2-A) → `48c1e2b` (REM-1) → `a578abe` (P3.92) → `6ff6b07`
  (P3.93) → `c1984e7` (P3.91 = live GitHub `main`).
- Remote relationship: `origin/main` = `c1984e7979f89f2d727b471deb602953ec62fad5`
  (read-only `git ls-remote origin refs/heads/main` re-verified 2026-10-17);
  local ahead (7 + this checklist's commit) / behind 0; push owner-gated.
- Tracked working tree clean at verification (0 modified, 0 staged); stash 0;
  single worktree. Untracked = the intentionally uncommitted bootstrap
  governance set + raw evidence directories (preserved; owner review PENDING).
- State verification timestamp: **2026-10-17T13:37Z** (development sandbox).

Reviewer checks:
- [ ] Confirm `git rev-parse HEAD` equals the reviewed commit.
- [ ] Confirm `git status --porcelain` shows only the expected untracked set.
- [ ] Confirm ancestry with `git log --oneline -8`.

## 2. Acceptance matrix — classification summary

Classification executed on actual code and test bodies at `0834b19` (packaging
audit, AI2-D record §8) and re-checked at `56deaff` (no application-code change
between the two; AI2-D is docs-only). Full evidence text: package §4.

| Group | Count | Meaning |
|---|---|---|
| Category A implementation criteria — **PASS** | 14 (A1–A14) | Implementation + named-test evidence verified in the packaging audit |
| **FAIL** | 0 | No reproducible defect found |
| Runtime / production / governance criteria — **BLOCKED** | 8 rows | Exact causes: G2 NOT_PASSED, NOT_SYNCED amendments, absent credentials, owner acceptance PENDING |
| Environment items — **NOT_VERIFIED** | 3 rows | Windows validation, Python 3.13 parity, Claude CLI recognition (never verified in this environment) |

## 3. PASS evidence — implementation and test references (A1–A14)

All tests live in `backend/tests/test_ai2_service.py` (40 tests; 40/40 passed
at `0834b19` and at committed `56deaff`). Line numbers refer to
`backend/app/services/ai2_service.py` unless noted.

| # | Criterion | Implementation | Named tests | Status |
|---|---|---|---|---|
| A1 | Bounded request contract (question ≤2000, symbol ≤64, filter_expr ≤2048, language ≤16; `backtest_result` JSON ≤64 KiB, fail-closed) | `AI2Request` + `_bounded_payload` (`:88-134`) | `test_ai2_request_bounds_enforced` | **PASS** |
| A2 | Nesting-depth bound (iterative); NaN/Infinity rejected | `_check_depth` (`:104-115`), `allow_nan=False` (`:127`), `RecursionError` belt (`:128-129`) | `test_ai2_request_rejects_deep_nesting`, `test_ai2_request_rejects_non_json_values_without_payload_echo` | **PASS** |
| A3 | Strict model-output schema (`extra="forbid"`, item bounds, confidence ∈ [0,1]) | `AI2Interpretation` (`:137-150`) | `test_ai2_interpretation_rejects_unknown_fields`, `test_ai2_boundary_limits_accepted`, `test_ai2_confidence_bounds_enforced`, `test_ai2_schema_rejects_wrong_types` | **PASS** |
| A4 | Deterministic stage-1 integration; recorded-not-raised degradation | `_stage1_analysis`, `_bounded_stage1` (`:263-289`) | `test_ai2_stage1_present_traceable_and_idempotent`, `test_ai2_stage1_failure_degrades_deterministically`, `test_ai2_missing_symbol_context_recorded_hashed_and_prompted` | **PASS** |
| A5 | Fail-closed gates + ordering (AI2_ENABLED → trust-state → G2) | run() Gates 1–3 (`:345-403`) | `test_ai2_unavailable_data_gated_fail_closed`, `test_ai2_missing_trust_state_gated`, `test_ai2_disabled_by_default_gates_before_transport`, `test_ai2_production_path_blocked_by_g2_gate` | **PASS** |
| A6 | Hash derived from exact payloads, verifiable from returned artifacts | `_input_digest` (`:214-219`), `prompt_sha256` (`:419`) | `test_ai2_input_hash_verifiable_from_returned_context`, `test_ai2_prompt_hash_rebuilds_from_recorded_inputs`, `test_ai2_input_hash_sensitive_to_backtest_and_question` | **PASS** |
| A7 | Model output cannot mutate deterministic facts | structural + strict schema | `test_ai2_model_output_cannot_override_deterministic_values` | **PASS** |
| A8 | Provenance completeness on 8 outcome paths (+`provider_attempts`) | `AI2Provenance` + `_base_provenance` (`:153-258`) | `test_ai2_provenance_complete_on_every_outcome`, `test_ai2_provider_attempts_recorded_or_none` | **PASS** |
| A9 | Cancellation containment (late results discarded; pre-seam cancellation reaches nothing) | `asyncio.to_thread` seam (`:421-426`); stateless singleton | `test_ai2_cancellation_during_slow_provider_late_success_discarded`, `test_ai2_cancellation_late_provider_failure_discarded_and_reusable`, `test_ai2_cancellation_before_seam_no_invocation`, `test_ai2_cancellation_propagates_no_fabricated_result` | **PASS** |
| A10 | Deterministic failure mapping (timeout / 4xx no-retry / seam non-dict / malformed / empty / whitespace / non-object / missing fields) | failure branches (`:428-490`), `_parse_interpretation` (`:221-237`) | `test_ai2_timeout_maps_deterministically`, `test_ai2_http_4xx_no_retry`, `test_ai2_seam_contract_violation_non_dict_maps_failed_provider`, `test_ai2_schema_rejects_malformed_json`, `test_ai2_empty_output_from_ok_seam_maps_failed_schema`, `test_ai2_whitespace_only_output_maps_empty_output`, `test_ai2_non_object_output_maps_schema_not_object`, `test_ai2_missing_required_fields_maps_schema_error` | **PASS** |
| A11 | Secret-free logs and errors incl. exception paths | `_log` (`:331-343`); seam warnings are static bounded strings (`app/domain/ai_provider.py:224,238,258,403`) | `test_ai2_no_secret_material_in_result_or_logs` | **PASS** |
| A12 | Concurrency isolation + idempotency on shared singleton | stateless design (only `_context_builder`) | `test_ai2_concurrent_runs_isolated` (+ A6 idempotency assertions) | **PASS** |
| A13 | Test-transport isolation; "executed" unreachable with mock output | shadow branch (`:493-504`); production path structurally unreachable (`app/core/config.py:214` — `build_data_trust_context` cannot mint verified LIVE) | `test_ai2_test_transport_never_yields_executed_status`, `test_ai2_future_live_gated_path_maps_executed` | **PASS** |
| A14 | Exact inter-stage value transfer (task, trust state, exact prompt) | prompt/payload construction (`:409-426`) | `test_ai2_inter_stage_values_exact` | **PASS** |

Reviewer checks:
- [ ] Spot-read at least A1, A5, A6, A9, A10 implementation and test bodies.
- [ ] Run the focused suite: `cd backend && ../.venv/bin/python -m pytest tests/test_ai2_service.py -q` → expect `40 passed`.

## 4. Reproducible commands and exact results

Primary packaging battery — HEAD `0834b19`, 2026-10-17T05:24Z, Python 3.12.15
(raw incl. per-command exit codes and durations:
`docs/governance/evidence/raw/2026-10-17_ai2c_independent_verification/`):

| Command (cwd `backend/` unless noted) | Exit | Result |
|---|---|---|
| `.venv/bin/python -m pytest -q` | 0 | 348 passed, 2 warnings in 77.30s |
| `.venv/bin/python -m pytest tests/test_ai2_service.py -q` | 0 | 40 passed in 0.94s |
| `.venv/bin/python -m compileall -q app tests` | 0 | clean |
| `PYTHONPATH=. .venv/bin/python -m pyflakes app tests` | 0 | 0 findings |
| `.venv/bin/python -m pip_audit` | 0 | No known vulnerabilities found |
| `git diff --check` (repo root) | 0 | clean |
| `.venv/bin/python scripts/validate_bootstrap_config.py` (repo root) | 0 | 8/8 PASS |

AI2-D at-commit battery — HEAD `56deaff` (raw:
`docs/governance/evidence/raw/2026-10-17_ai2d/`; `00_context.txt` records
`head=56deaff…`, `tracked_dirty=0` pre/post): pytest 348 passed / 2 warnings in
77.51s; AI-2 focused 40 passed in 0.93s; all static/dep/validator/diff checks
exit 0.

Baseline lineage (each at its committed tree): 308 (`c1984e7`) → 320
(`2026-10-17_rem1_ai2a/`) → 331 (`2026-10-17_ai2b/`) → 348 (`2026-10-17_ai2c/`,
`2026-10-17_ai2d/`). The 2 warnings are pre-existing starlette/anyio
environment deprecations (identical across all baselines; not introduced by
AI-2 work).

Reviewer checks:
- [ ] Re-run the full battery at the reviewed SHA and compare to the recorded
      results; investigate any deviation, never suppress it.

## 5. Known cancellation limitation and containment evidence

**Limitation (honest):** `asyncio.to_thread` cannot terminate the worker thread
executing the synchronous provider call. Cancelling the awaiting task does NOT
stop the underlying thread; the worker finishes in the background.

**Containment (proven by tests, not asserted):** a late provider
success/failure after caller cancellation is discarded — it can never be
returned to the cancelled caller or committed to downstream state, because the
service is a stateless singleton (`vars(svc).keys() == {"_context_builder"}` in
the tests) and the result object is only ever handed to the awaited caller.

Evidence (package §4a A9; package §8.1): the four named cancellation tests in
§3 row A9 — `threading.Event` proves the worker completes LATE; `task.cancelled()`;
late success discarded; late failure discarded and instance reusable;
pre-seam cancellation proven by spy seam to reach zero invocations; no
fabricated result. The contract is also documented in the module docstring.

Reviewer checks:
- [ ] Read the four cancellation tests and the module docstring contract.
- [ ] Confirm the limitation statement above matches the tests (tests prove
      the thread is NOT terminated).

## 6. Provider, network, credential, OS, and runtime limitations

- **Provider/network isolation is structural, not socket-enforced**: no
  `conftest.py` socket guard exists in this repo. Isolation holds because every
  seam-reaching test injects a mock transport or monkeypatches the module-level
  seam symbol, and every gated path uses a raising spy transport. The
  production (transport-less) path is additionally unreachable (Gate 3 cannot
  pass — `build_data_trust_context` hard-codes `verified=False`,
  `app/core/config.py:214`).
- **Credentials**: no LLM credentials exist in this environment → real
  provider contract tests and any live path BLOCKED.
- **Windows-target validation**: NOT_VERIFIED (battery executed on Linux
  sandbox; Windows INSTALL owner-gated).
- **Python 3.13 parity**: NOT_VERIFIED (all recorded batteries ran Python
  3.12.15).
- **Claude CLI recognition**: NOT_VERIFIED (owner environment).

Reviewer checks:
- [ ] Confirm no test in the suite opens network connections (structural
      review of seam usage).
- [ ] Confirm the interpreter version of any re-run matches the recorded
      3.12.15 or is explicitly re-baselined.

## 7. Explicit separation: local testing vs independent G2 validation

Everything in §2–§6 is **locally reproducible software checking** executed in
the development sandbox by the implementing agent. These results establish
code-level properties only. They are **not** G2 acceptance. G2 is independent
validation, granted only by the owner per the authoritative procedure — which
is itself NOT_SYNCED (§10). **348 passing tests ≠ G2 approval.** No result in
this repository may be represented as G2 approval, `live_verified=true`, or
authorization to enable `AI2_ENABLED` outside tests.

## 8. Required reviewer / owner decisions and evidence expected

| # | Decision | Decision holder | Evidence expected before/for the decision |
|---|---|---|---|
| R1 | Accept the 5 amendment originals as the authoritative AI-2 + roadmap + boundaries + charter + decision-register sources | Owner | The 5 originals arrive intact under `docs/governance/amendment_sources_2026-10-02/`; acceptance matrix re-baselined against them |
| R2 | Authorize and schedule the G2 review; supply the authoritative G2 procedure | Owner (+ independent validator) | Owner-defined procedure document; reviewer assignment; reviewed SHA fixed (§1) |
| R3 | Authorize live-credential provisioning and the live validation run | Owner | Credentials in a owner-controlled environment; authorized run logs; only then may `live_verified` transition |
| R4 | Enable `AI2_ENABLED=1` outside tests (any use of AI-2 output beyond advisory) | Owner | G2 passed per the authoritative procedure + explicit owner acceptance (packet §8 items PENDING) |
| R5 | Push / publish the local commit chain | Owner | Owner-authenticated push of the ahead chain (§1) when publication is authorized |
| R6 | Verify Windows / Python 3.13 / CLI recognition in the owner environment | Owner | Environment run logs from owner machines |

## 9. G2 entry and exit criteria (from available authoritative sources only)

**Entry criteria (all checkable today from in-repo sources):**
- [ ] E1 — Reviewed SHA fixed and tree state matches §1.
- [ ] E2 — Evidence package (AI2-D) and this checklist present and internally
      consistent; every evidence path in §3–§6 resolves on disk.
- [ ] E3 — Verification battery reproducible by the reviewer (§4 commands) at
      the reviewed SHA with matching results.
- [ ] E4 — Governance gates verified in code: `AI2_ENABLED` default off;
      `live_verified=false`; no AI-2 HTTP route; production path structurally
      unreachable.
- [ ] E5 — Known limitations (§5–§6) read and acknowledged by the reviewer.
- [ ] E6 — Amendment-corpus status acknowledged: NOT_SYNCED (or supplied and
      re-baselined per R1).

**Exit criteria:** `BLOCKED` — the authoritative G2 procedure and its exit
criteria are owner-defined and have not arrived (NOT_SYNCED); they are NOT
invented here. What existing in-repo governance already establishes: the G2
outcome must be recorded by the owner with an independent validator; a
`live_verified=true` transition may follow only an authorized live validation
run (R3); self-approval is void; `AI2_ENABLED` stays off outside tests until
owner acceptance (R4). Upon arrival of the amendment corpus, the owner-defined
exit criteria supersede this section without rewrite of the recorded evidence.

## 10. Owner handoff — missing amendment sources (NOT_SYNCED) and their impact

Verified absent on 2026-10-17 (`ls docs/governance/amendment_sources_2026-10-02/`
→ exit 2, directory does not exist). Required originals, exactly:

| Expected file (exact name) | Impact of absence |
|---|---|
| `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` | Authoritative execution roadmap position and next-phase definition cannot be re-baselined from source |
| `02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE_CURRENT_2026-10-02.md` | Authoritative AI-2 task list, agent boundaries, and architecture requirements cannot be confirmed; the implemented Category A scope remains **provisional by design** (`AI2Request` docstring: amendments supersede it when supplied) |
| `03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md` | Authoritative governance boundaries for AI-2 (gates, advisory-only limits) cannot be cross-checked against the owner's current text |
| `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md` | Role/authority mapping for the four-agent model and review authority cannot be re-verified from source |
| `05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md` | The authoritative decision register (incl. G2 procedure and acceptance decisions) is unavailable; G2 exit criteria cannot be defined without invention |

Delivery rule: owner supplies the originals into
`docs/governance/amendment_sources_2026-10-02/`. They are never reconstructed,
paraphrased as authoritative, or substituted with inferred content. On arrival,
the acceptance matrix is re-baselined against them and only evidence-backed
discrepancies are reported — existing governance decisions are not silently
overridden.

## 11. Reviewer sign-off

```text
Reviewer (name / role):  ______________________   independent of the implementing agent
Reviewed commit:         56deaff772c90c68c325edb292533717d9360660 (+ AI2-E docs commit if review starts later; resolve via git log)
Battery re-run result:   ______________________
Matrix disputes (rows):  ______________________
Limitations acknowledged (§5–§6):  [ ] yes
Entry criteria E1–E6:    [ ] all met   Exceptions: ______________
G2 verdict:              ______________________   (owner + independent validator only)
Date:                    ______________________
```
