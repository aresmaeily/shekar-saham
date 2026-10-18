# AI-4 GOVERNED GENERATION — SCOPE DERIVATION AND TRACEABILITY MATRIX

Status: scope derivation published BEFORE implementation (governance precedent
AI1-GC / AI2-F / AI-MA-C / AI3-M). Block identifier: **AI-4** (official
roadmap name: "AI-4 --- Governed Generation", `02` line 87). Execution record
will be `docs/active/AI4_EXECUTION_RECORD.md`. This document is the
authorization check; nothing below invents requirements beyond the cited
corpus lines.

## 1. Official definition (verbatim corpus loci)

- `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md:87-90` — "AI-4 --- Governed
  Generation: AI-generated filters/indicators/strategy specifications only
  through sandbox → deterministic evaluation → lifecycle → approval."
- `02:158-159` — "Market, fundamental, and product-improvement hypotheses may
  enter the same governed research lifecycle when a suitable deterministic
  evaluator exists. Episodic research artifacts remain immutable; semantic
  lessons remain curated/versioned. AI-generated filters, scoring rules,
  fundamental features, or software-change proposals remain candidates until
  isolated tests, evaluation gates and required human approval are passed.
  No self-modifying production logic."
- D-AI-10 (`05:19-20`) — bounded lifecycle mandatory.
- D-AI-11 (`05:20-21`) — "generated candidates only through
  sandbox/evaluation/lifecycle gates".
- D-AI-12 (`05:21-22`) — no trading/production mutation/bypass.
- D-AI-13 (`05:22-23`) — learning is evidence-based, not self-modifying
  production.
- D-AI-03/04/05 (`05`, preserved) — no production mutation without human
  approval; no automatic AI Brain → ExperimentLab binding; ExperimentLab
  production apply blocked.
- D-AI-19 (`05`) — financial truth, backtest, WFO, forward test, metrics,
  risk and statistical evaluation remain deterministic.
- `03:19-25` — AI may not: mutate production without human approval, bypass
  gates, self-escalate permissions, self-modify budgets, auto-promote
  research, treat untrusted content as executable, create self-modifying
  production logic.
- `03:33-40` — run provenance bindings; "Missing required provenance blocks
  governed acceptance."
- `03:42-47` — Governor owns authorization, transition policy, run identity,
  provenance binding, budget/quota, audit integration; must not duplicate
  financial logic.
- `03:78-83` — autonomy levels L0–L4; L4 human-controlled only; no silent
  autonomy increase.
- `03:90-94` — acceptance requires source/test/runtime evidence as
  applicable, provenance, failure-path evidence, independent validation where
  required, and an approval record.
- `00:85-86` — no self-modifying production logic; no broker order execution.
- `02:196` — all governed actions carry traceable run identity, versions,
  human approval state and explicit limitations.
- `02:170` — improvement proposals carry baseline/expected benefit/evidence/
  uncertainty/cost/risks/rollback plan/evaluation design; must not
  automatically change production, promote filters, alter
  permissions/budgets, or deploy software.
- `06:107` — research/feedback acceptance: preregistration, deterministic
  evaluation, outcome maturity, holdout protection, error analysis, versioned
  artifacts, independent validation, approval gates.
- `02:202` — pre-G2 authorized class: "only bounded design, schema work,
  source-registry design, synthetic/paper tests and safe dry-run work".
- `AI4_AI7_P343_DEPENDENCY_MATRIX.md` (committed `45f0b8b`) — authorized-now
  work class: "AI-4 contract layer (governed-generation lifecycle contracts:
  sandbox-admission gate, deterministic-evaluator binding, candidate
  lifecycle states, human-approval binding, no-production-mutation
  guarantees) + synthetic tests — pre-G2 class."

## 2. Dependency check (roadmap order `02:5-8` / `00:63`)

AI-1 → AI-2 → AI-MA → AI-3 are DELIVERED at the pre-G2 contract class
(state file §1/§3; commits `ea3277e`/`2f86c4a`, `6aeeaa2`/`17ef611`,
`e385415`/`aa86c3c`, `80585c8`/`37c529d`). AI-4's upstream contract
dependencies therefore exist. Real-data evaluation and any live generation
run remain G2-blocked (`02:201`, `02:202`); sandbox EXECUTION runtime does
not exist and is post-G2 work — this block delivers CONTRACTS ONLY, exactly
like AI2-F / AI-MA-C / AI3-M. No owner decision is required to start (`05`
§Engineering authority; dependency matrix "Owner decisions needed: none for
the contract class").

## 3. Reuse audit of existing canonical contracts (no duplication)

| Existing contract | Reuse in AI-4 |
|---|---|
| `run_governance.py` RunContext / RunProvenance / ArtifactRef / ApprovalState / assert_autonomy_permitted / missing_required_provenance | Candidate generation runs are governed runs: run identity, provenance completeness and autonomy ceiling are consumed, not reimplemented |
| `evidence.py` SCHEMA_VERSION / ensure_utc | Schema and UTC discipline reused |
| `ai2_governance.py` governed_acceptance pattern | Gate-function shape (returns blocking-reasons tuple) reused; AI-2 records NOT modified |
| `strategy.py` + `engines/filter_dsl.py` | Existing deterministic filter evaluator — a `DeterministicEvaluatorBinding` may reference it by contract string; AI-4 does NOT wrap or alter it |
| `research_memory.py` / `memory_interfaces.py` | Research-memory abstractions stay separate; AI-4 candidates may cite episodic artifacts by ID; no memory operation added here |
| `multi_agent.py` | No new specialist/orchestration abstraction; generation is a governed run kind, not a new agent type |

Grep-verified: no `GeneratedCandidate`, `governed_generation` or `sandbox`
concept exists anywhere in `backend/` — zero duplication risk.

## 4. Requirement → implementation traceability matrix

Legend — Status: GAP = to be implemented in this block. Every mandatory
corpus requirement maps to one planned contract element.

| # | Requirement (corpus locus) | Status | Planned implementation (`backend/app/domain/governed_generation.py` unless noted) |
|---|---|---|---|
| R1 | Generated artifact kinds are exactly: filters, indicators, strategy specifications (`02:88`) plus scoring rules, fundamental features, software-change proposals (`02:159`) | GAP | Closed `GeneratedCandidateKind` Literal of six members; unknown kinds unrepresentable |
| R2 | "only through sandbox" (D-AI-11; `02:88`) | GAP | `SandboxAdmissionRecord` — isolation declaration required, dataset origin closed to SYNTHETIC/PAPER (LIVE structurally inexpressible), production-contact field that cannot be True, bounded `SandboxBudgetSpec`; gate function `sandbox_admission_gate` |
| R3 | "→ deterministic evaluation" (D-AI-11; D-AI-19; `02:88`) | GAP | `DeterministicEvaluatorBinding` with `service_class: Literal["DETERMINISTIC"]` and NO model/prompt fields (stochastic evaluator unrepresentable); `EvaluatorRegistry` resolve-by-kind; `evaluation_gate` validates binding/candidate/admission coherence |
| R4 | "→ lifecycle" (D-AI-10/D-AI-11) | GAP | Closed `CandidateLifecycleState` (DRAFT → SANDBOX_ADMITTED → EVALUATED → APPROVAL_PENDING → APPROVED/REJECTED) + `transition_candidate` table; illegal transitions refused with deterministic reason codes |
| R5 | "→ approval" — required human approval (`02:159`; `03:90-94`) | GAP | `CandidateApprovalRecord` (decision APPROVED/REJECTED, human `decided_by` + `approval_ref` mandatory — same discipline as RunContext L4); approval only valid in APPROVAL_PENDING |
| R6 | Candidates "remain candidates until isolated tests, evaluation gates and required human approval are passed" (`02:159`) | GAP | `evaluation_gate` requires preregistration + holdout-protection declarations (`06:107`); EVALUATED→APPROVAL_PENDING refused unless evaluation verdict PASS; end-to-end `governed_candidate_acceptance` |
| R7 | Hypotheses enter the governed research lifecycle "when a suitable deterministic evaluator exists" (`02:158`) | GAP | `generation_admission_verdict(candidate, registry)` — refuses entry when no binding covers the candidate kind |
| R8 | Missing required provenance blocks governed acceptance (`03:40`) | GAP | `sandbox_admission_gate` and `governed_candidate_acceptance` call existing `missing_required_provenance` with `dataset_version` additionally required |
| R9 | No self-modifying production logic; no auto-promotion; ExperimentLab apply blocked (D-AI-03/05/12/13; `03:19-25`; `00:85`; `02:170`) | GAP | Structural: lifecycle vocabulary contains NO production/applied/deployed state; transition table has no edge to any such state; module contains no apply/deploy/promote function; software-change proposals must carry rollback plan + evaluation design + risks (`02:170`) or admission is refused |
| R10 | Governor owns budget/quota; must not duplicate financial logic (`03:42-47`) | GAP | `SandboxBudgetSpec` (structurally bounded ceilings) + `sandbox_budget_verdict`; gates check binding/provenance/lifecycle only — metric math and thresholds stay in deterministic evaluators (never computed here) |
| R11 | Autonomy ceiling; no silent escalation (`03:78-83`) | GAP | Admission gate calls existing `assert_autonomy_permitted` with a gate-declared ceiling |
| R12 | Explicit limitations on governed actions (`02:196`) | GAP | Candidates require non-empty `rationale`; records carry `notes`; refusal codes are explicit strings |
| R13 | Acceptance evidence: provenance, failure-path evidence, approval record (`03:90-94`; `06:107`) | GAP | `governed_candidate_acceptance` returns explicit blocking codes (failure-path evidence = deterministic refusal reasons); tests cover every refusal path |
| R14 | Pre-G2 class: synthetic/paper only (`02:202`) | GAP | Dataset origin closed Literal {SYNTHETIC, PAPER}; G2/live discipline documented in module docstring |

## 5. Out of scope (explicitly NOT authorized by this block)

- Any sandbox execution runtime, evaluation runner, or scheduler (post-G2;
  sandbox runtime "does not exist" — dependency matrix).
- Any live generation run, real-data evaluation, or promotion execution
  (dependency matrix BLOCKED rows; `02:201`).
- Any modification to `ai2_service.py`, `filter_dsl.py`, `strategy.py`,
  research-memory or monitoring modules (additive-only discipline).
- Any new HTTP route, config flag, or `AI2_ENABLED` change.
- Any LLM/provider invocation (LLM NOT EXECUTED).
- AI-5/AI-6/AI-7 scope creep (each coupled to separate owner decisions —
  dependency matrix).

## 6. Planned acceptance evidence

- Corpus-derived test module `backend/tests/test_ai4_governed_generation.py`
  (positive end-to-end lifecycle + negative refusal-path coverage for every
  gate).
- Full repository battery (pytest, pyflakes, compileall, pip-audit, alpha
  env/runtime/frontend validators, bootstrap validator, `git diff --check`)
  pre-commit and at the committed SHA, raw outputs under
  `docs/governance/evidence/raw/2026-10-18_ai4/`.
- Independent read-only audit → `docs/governance/evidence/
  2026-10-18_AI4_independent_audit.md` (post-implementation).
- Execution record `docs/active/AI4_EXECUTION_RECORD.md`; pointers updated
  (INDEX / STATUS / CHANGELOG / handoff); state file reconciled.

## 7. Resolved/unresolved register

- All five dependency-matrix contract groups (R2/R3/R4/R5/R9) are
  corpus-derivable → UNRESOLVED count: 0 for the contract class.
- Numeric sandbox budget ceilings = engineering-authority defaults with
  structural bounds; owner sets operational numbers at runtime integration
  (dependency matrix "numeric sandbox budgets later at runtime integration").
- Approval-record PERSISTENCE (where approved candidates are stored) =
  owner deployment decision, same disposition as AI-3 persistence
  (`AI3_PERSISTENCE_DECISION_BRIEF.md`); this module is in-memory contract
  records only.
