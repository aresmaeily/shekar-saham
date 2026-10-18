# AI-4 GOVERNED GENERATION — EXECUTION RECORD

Block: **AI-4** (official roadmap name "AI-4 --- Governed Generation", `02`
lines 87-90). Execution date: 2026-10-18 (Asia/Tehran). Scope derivation
published BEFORE implementation: `docs/active/AI4_SCOPE_DERIVATION.md`.
Work class: pre-G2 authorized contracts + synthetic tests (`02:202`).

## 1. What was implemented (additive only)

New module `backend/app/domain/governed_generation.py` (frozen pydantic
records, deterministic, clock-free, no I/O, no network, no LLM, no
scheduler) + test module `backend/tests/test_ai4_governed_generation.py`
(51 tests). No existing module was modified; no route, no config change, no
`AI2_ENABLED` change.

Contract surface (exactly the five dependency-matrix groups):

1. **Sandbox-admission gate** — `SandboxAdmissionRecord` (isolation
   declaration required — `False` refused at construction; production
   contact structurally forbidden; dataset origin closed to
   SYNTHETIC/PAPER, LIVE unrepresentable per `02:202`; mandatory
   `dataset_version`/`policy_version`) + `sandbox_admission_gate()`
   (identity binding, provenance completeness via the canonical
   `missing_required_provenance` with `dataset_version` additionally
   required, autonomy ceiling via canonical `assert_autonomy_permitted`,
   evaluator availability) + `SandboxBudgetSpec`/`SandboxBudgetUsage`/
   `sandbox_budget_verdict()` (structurally bounded ceilings, ceiling-
   inclusive, clock-free — 03 §Governor budget/quota).
2. **Deterministic-evaluator binding** — `DeterministicEvaluatorBinding`
   (`service_class: Literal["DETERMINISTIC"]`; NO model/prompt fields exist
   in the schema, so a stochastic/LLM evaluator is unrepresentable —
   D-AI-19), `EvaluatorRegistry` (deterministic first-match resolution,
   additive `with_binding`, duplicate-id refusal),
   `evaluation_gate()` (run/admission/binding/kind/dataset coherence),
   `EvaluationMetric` (finite values only, distinct names),
   `CandidateEvaluationRecord` (preregistration + holdout-protection
   declarations per `06:107`).
3. **Candidate lifecycle states** — closed `CandidateLifecycleState`
   (DRAFT → SANDBOX_ADMITTED → EVALUATED → APPROVAL_PENDING →
   APPROVED/REJECTED), `ALLOWED_TRANSITIONS` policy table,
   `transition_candidate()` (unknown states and illegal edges refused with
   deterministic codes; terminal states have empty outgoing sets).
4. **Human-approval binding** — `CandidateApprovalRecord` (decision
   APPROVED/REJECTED; mandatory human `decided_by` + `approval_ref`; same
   discipline as the canonical L4 rule), `approval_gate()` (candidate
   binding + APPROVAL_PENDING-state requirement), `approval_entry_gate()`
   (FAIL evaluation cannot enter approval — `02:159`).
5. **No-production-mutation guarantees** — structural: the lifecycle
   vocabulary contains NO production/applied/deployed state and the
   transition table has no edge to one (test-enforced); the module contains
   no apply/deploy/promote function; `GeneratedCandidate.kind` is a closed
   six-member Literal (`02:89-90` filters/indicators/strategy specifications +
   `02:159` scoring rules/fundamental features/software-change proposals);
   `SOFTWARE_CHANGE_PROPOSAL` candidates must carry the eight `02:179`
   fields (baseline, expected benefit, evidence, uncertainty, cost, risks,
   rollback plan, evaluation design) via `SoftwareChangeProposalFields` or
   they are unrepresentable; non-proposal kinds cannot carry proposal
   fields; `rationale` is mandatory (explainable generation, `02:198`).
   `governed_candidate_acceptance()` composes every gate end-to-end and
   returns explicit blocking codes (failure-path evidence, `03:90-94`).

Reuse (no duplication): run identity/provenance/autonomy from canonical
`run_governance.py`; schema/UTC discipline from `evidence.py`; gate-function
shape mirrors `ai2_governance.governed_acceptance`; the existing
`engines/filter_dsl.py` remains the referenced deterministic evaluator
example (bound by contract string, never wrapped or altered); research
memory, multi-agent and monitoring modules untouched.

## 2. Traceability outcome (vs `AI4_SCOPE_DERIVATION.md` R1-R14)

R1 kind closure → `GeneratedCandidateKind` (test: lifecycle-vocabulary and
kind-schema tests). R2 sandbox gate → admission record + gate + budget.
R3 deterministic evaluation → binding/registry/evaluation gate. R4
lifecycle → state machine. R5 approval → approval record/gate. R6
candidates-until-gates → preregistration/holdout declarations +
`approval_entry_gate` + `governed_candidate_acceptance`. R7 lifecycle entry
→ `generation_admission_verdict`. R8 provenance blocking → canonical
completeness check wired into admission and acceptance. R9 no-production-
mutation → structural (schema + transition table + absence of promotion
functions + `02:179` proposal fields). R10 budget/quota → sandbox budget
spec/verdict; gates never compute metric math (D-AI-19 financial truth
stays in deterministic services). R11 autonomy ceiling → canonical guard
wired into admission. R12 explicit limitations → mandatory rationale,
notes fields, explicit refusal codes. R13 acceptance evidence →
`governed_candidate_acceptance` + per-gate refusal-path tests. R14
synthetic/paper class → closed `DatasetOrigin`. All 14 rows closed; 0
unresolved requirements.

## 3. Validation battery (pre-commit raw `docs/governance/evidence/raw/2026-10-18_ai4/`; at-commit raw `docs/governance/evidence/raw/2026-10-18_ai4a/`)

- pytest full suite: **563 passed / 2 pre-existing warnings** in 78.26s
  (512 baseline + 51 new), exit 0 (`pytest_full.txt`).
- AI-4 block: **51/51 passed** in 0.18s, exit 0 (`pytest_new_block.txt`).
- At-commit battery at the committed SHA (`6a10e5a`), raw
  `docs/governance/evidence/raw/2026-10-18_ai4a/`: pytest full suite
  **563 passed / 2 pre-existing warnings in 78.38s**, exit 0
  (`pytest_full.txt`); AI-4 block **51/51 in 0.23s**
  (`pytest_new_block.txt`); compileall 0; pyflakes `app tests` 0;
  pip-audit clean (`pip_audit_summary.txt`); alpha env/runtime/frontend
  validators 0; bootstrap validator 0; providers tsetmc+brsapi exit 0
  with `"live_verified": false`; `git diff --check` 0; SHA-256 manifest
  `00_evidence_sha256.txt`.
- compileall exit 0 (`compileall.txt`); pyflakes `app` exit 0; pyflakes
  `app tests` exit 0; pyflakes new files exit 0 (`pyflakes_app.txt`,
  `pyflakes_app_tests.txt`, `pyflakes_new.txt`).
- pip-audit: "No known vulnerabilities found", exit 0
  (`pip_audit_summary.txt`).
- validate_alpha_environment exit 0; validate_alpha_runtime exit 0;
  validate_frontend_static exit 0; bootstrap validator exit 0.
- validate_providers tsetmc + brsapi exit 0 with `"live_verified": false`
  (correct fail-closed; `validate_providers_tsetmc.txt`,
  `validate_providers_brsapi.txt`).
- `git diff --check` exit 0 (`git_diff_check.txt`).
- Evidence SHA-256 manifest: `00_evidence_sha256.txt`.
- The 2 warnings are the pre-existing Starlette/httpx TestClient
  deprecation warnings recorded since the P3.91 baseline.

## 4. Honest defect notes (pre-battery, fixed, history preserved)

1. Three initial test-expectation defects (not module defects): two tests
   expected a single refusal code where the gate deterministically emits a
   fixed multi-code sequence (`admission_run_id_mismatch` +
   `candidate_run_id_mismatch`), and one test expected
   `dataset_origin_not_accepted_by_evaluator` from a binding that actually
   accepted the origin. Fixed by correcting the expectations; both gate
   behaviors were already correct and deterministic.
2. One pyflakes finding pair (two unused locals in a test after the
   expectation refactor) — removed before the recorded battery run.
3. The first full-suite capture preserved only the tail lines; it was
   immediately re-run with complete raw output preserved
   (`pytest_full.txt` = the complete 78.26s run). No battery claim in this
   record relies on the discarded tail-only capture.

## 5. Explicitly NOT done (gates and deferred integrations)

- No sandbox/evaluation EXECUTION runtime — does not exist; post-G2 work
  (`02:202`; dependency matrix "sandbox runtime does not exist"). The exact
  gate blocking it: G2 independent validation + owner acceptance, plus the
  runtime-integration owner decisions (numeric sandbox budgets, deployment
  environment — `AI3_PERSISTENCE_DECISION_BRIEF.md` D-series applies to any
  persistence choice for candidate records).
- No live generation run, no real-data evaluation, no promotion execution
  (dependency matrix BLOCKED rows; `02:201`). Gate: G2 NOT_PASSED.
- No LLM/provider invocation (LLM NOT EXECUTED); no AI-2 activation
  (`AI2_ENABLED` default off, `config.py:109`); no new HTTP route; no push
  (owner-gated).

## 6. Governance status after this block

- Gates unchanged: G2 NOT_PASSED (not self-approved); `AI2_ENABLED=0`;
  `live_verified=false`; LLM NOT EXECUTED; no route; push owner-gated.
- Independent read-only audit: `docs/governance/evidence/
  2026-10-18_AI4_independent_audit.md` (verdict recorded there; any
  remediation recorded in a follow-up commit AI-4a with FAIL history
  preserved in the audit file).
- Owner acceptance of this block: PENDING (nothing accepted on the owner's
  behalf).
