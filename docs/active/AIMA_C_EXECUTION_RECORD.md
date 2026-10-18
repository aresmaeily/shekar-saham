# AI-MA-C Execution Record — Multi-Agent Runtime Contract Layer

Date: 2026-10-18 · Block: **AI-MA-C** (AI-MA-1..6 contract layer; dependency successor of AI2-F per `02` line 7) · Baseline at mission start: `17ef611` (AI2-Fa) on `main`, ahead 15/behind 0 vs live `origin/main` `c1984e7`, tracked tree clean, 4 untracked bootstrap paths preserved, amendment corpus byte-identical.

## 1. Scope derivation (published before implementation)

Report: `docs/active/AIMA_C_SCOPE_DERIVATION.md`. Authoritative definition: `02` lines 55–81 — AI-MA-1 thin central orchestrator, AI-MA-2 capability registry + specialist contract, AI-MA-3 first bounded specialist, AI-MA-4 second specialist + bounded parallel execution, AI-MA-5 artifact-first branch exchange, AI-MA-6 tracing/observability/failure isolation; "No fixed agent count. No peer-to-peer backbone. No autonomous spawning." Gate class: pre-G2 bounded design/schema/synthetic work (`02` line 202) — the RUNTIME is NOT instantiated (it requires the AI-2 research-loop runtime and G2-passed real-data execution); the 17 governance roles stay lenses (D-AI-17/18). This block also carries the AI2F-06 residual docs correction.

## 2. Implementation (additive contracts + tests, nothing else)

`backend/app/domain/multi_agent.py` (frozen, deterministic, clock-free; structurally imports AI1-GC `ArtifactRef`/`RunContext` and binds plans to the canonical identity via `bind_run_context`; the AI2-F budget discipline is aligned conceptually — specialist budgets use this module's own bounded fields; no network/LLM/thread/scheduler; no existing module modified; no route; no config change):

| Sub-block | Contract |
|---|---|
| AI-MA-2 | `SpecialistContract` — all 03 §Specialist attributes (purpose, capability, allowed tools, schema refs, authority boundary, max invocations/timeout, trace prefix, failure behavior) + admission rules (measurable-benefit ref, coordination cost, consequential⇒owner change record) + D-AI-21 (agent-as-tool default; HANDOFF requires justification); `CapabilityRegistry` — append-only, idempotent/conflict, distinct-capability enforcement, no fixed count, deterministic `resolve()` |
| AI-MA-3 | `bind_specialist_to_step()` — the first-bounded-specialist-as-tool/capability composition rule made explicit and testable: a plan step delegates to a REGISTERED specialist contract owning the step's capability (agent-as-tool, D-AI-21); demonstrated by registry resolve + step binding tests |
| AI-MA-1 | `OrchestrationPlan`+`OrchestrationStep` — decomposition bound to one RunContext; two-level depth structurally enforced; deterministic iterative-DFS cycle detection; unknown-dependency and self-dependency refusal; bounded fan-out ceiling (engineering bound `MAX_PARALLEL_BRANCHES=4`, documented) |
| AI-MA-4 | `execution_waves()` — pure deterministic bounded-parallel scheduling (topological waves; wide levels split to the ceiling, never merged/reordered); D-AI-24 |
| AI-MA-5 | `BranchResult` — artifact-first exchange (large results ONLY by ArtifactRef; inline travel limited to a small declared summary; failed branches carry failure codes and NO payload); peer-to-peer addressing structurally refused (must address `orchestrator:<run_id>`; D-AI-20/02:81) |
| AI-MA-6 | `TraceEvent`+`TraceLog` — one append-only trace fabric, every event bound to run_id and the specialist trace prefix (02-product rule 12); `isolate_failure()` — deterministic load-bearing-vs-independent decision (a step with dependents ⇒ TERMINATE_RUN; independent branch failure ⇒ CONTINUE_OTHER_BRANCHES; 02-product §Failure model) |

Tests: `backend/tests/test_ai_ma_contracts.py` (25 tests; 22 original + 3 audit-disposition tests) — contract freezing, handoff justification, admission rules, registry semantics (idempotent/conflict/distinct-capability/no-fixed-count), plan graph checks (cycles/unknown/self-dep/depth/duplicates/fan-out ceiling), wave determinism + ceiling splitting, artifact-first + peer-refusal + failed-payload-free exchange rules, trace fabric append/filter, deterministic failure isolation.

## 3. Validation battery (raw `docs/governance/evidence/raw/2026-10-18_aimac/`)

| Check | Result |
|---|---|
| `pytest -q tests` (repo venv, `backend/`) | **496 passed, 2 warnings** (474 + 22 at the pre-commit battery; 499 = 474+25 after the dispositions, re-verified in the AI-MA-Ca battery) — exit 0 |
| `pytest -q tests/test_ai_ma_contracts.py` | **22 passed** (pre-commit) / **25 passed** (post-dispositions) — exit 0 |
| `pyflakes app tests` / `compileall app tests` | 0 / 0 — exit 0 |
| `pip-audit` | clean — exit 0 |
| alpha env/runtime/frontend validators + bootstrap validator | all exit 0 (bootstrap 8/8) |
| `git diff --check` | 0 |

## 4. Governance reconciliation

Tracked updates committed: STATUS row, CHANGELOG entry (incl. the AI2F-06 attribution correction), INDEX entries, master-handoff appendix (incl. AI2F-06 correction), scope report, execution record, the domain module, the test file. Untracked (bootstrap set): state-file reconciliation, audit reports, raw evidence.

## 4b. Independent audit (AIMAC-audit) and dispositions

Audit: `docs/governance/evidence/2026-10-18_AIMAC_independent_audit.md` — verdict **PASS** (0 MEDIUM; 5 LOW + 2 INFO disclosed; auditor's own battery at the exact `e385415` tree = 496 passed / 2 warnings 77.62s). Dispositions applied by remediation commit **AI-MA-Ca**:

- **AIMAC-01 (LOW)**: AI-MA-3 had no traceability row → explicit AI-MA-3 row added (§2) and the composition rule materialized as `bind_specialist_to_step()` with tests.
- **AIMAC-02 (LOW)**: state file §2i said tracked_dirty=0 — actual pre/post was 2 (the block's own in-flight pointer edits) → corrected to 2/2.
- **AIMAC-03 (LOW)**: dead conditional in `isolate_failure` (both arms returned CONTINUE) → code shape cleaned; semantics unchanged and now documented (containment is structural; failures stay visible records).
- **AIMAC-04 (LOW)**: "reuses AI2-F budget discipline / RunContext" was partially narrative → `RunContext` is now structurally imported and `bind_run_context()` provides the tested plan↔identity binding; budget wording made honest (alignment is conceptual; specialist budgets are this module's own bounded fields).
- **AIMAC-05 (LOW)**: `BranchResult.summary` unbounded → schema-bounded to 500 (test added).
- **AIMAC-06 (LOW) / AIMAC-07 (INFO)**: failure-model partial mapping + undisclosed engineering choices (lowercase patterns, max_parallel default, addressed_to string-convention nature) → disclosed in the module docstring's engineering-authority notes; no behavior change.

## 5. Statuses after this block (separated, not conflated)

- AI-MA contract layer: **IMPLEMENTED (paper/synthetic scope)** — all six AI-MA sub-blocks have contracts + deterministic tests.
- NOT claimed (D-AI-41): no runtime agent instantiated; no orchestrator/specialist execution; AI-MA runtime acceptance (`02` §Acceptance requirements) NOT PROVEN; multi-agent runtime execution requires the AI-2 research loop and G2-passed real data (blocked).
- G2: NOT_PASSED; `AI2_ENABLED` default off; no route; LLM NOT EXECUTED; `live_verified=false`.
- Push: owner-gated (16 local commits after this block).
- Next authorized block (dependency graph `02` line 7): **AI-3 Research Memory** — episodic immutable run artifacts + curated/versioned semantic memory (`02` lines 83–85), building on the AI1-GC memory interfaces and AI2-F ledger.
