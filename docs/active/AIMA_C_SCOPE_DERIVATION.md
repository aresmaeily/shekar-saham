# AI-MA-C Scope Derivation — Multi-Agent Runtime Contract Layer (`02` §AI-MA, lines 55–81)

Published BEFORE implementation (governance precedent). Baseline: HEAD `17ef611` (AI2-Fa) on `main`, ahead 15/behind 0 vs live `origin/main` `c1984e7`, tracked tree clean, 4 untracked bootstrap paths preserved, amendment corpus byte-identical. This block also carries the AI2F-06 residual docs correction (CHANGELOG/handoff 24/24 attribution).

## 1. Authoritative definition

`02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` lines 55–81: AI-MA-1 Thin Central Orchestrator around the existing Research Loop · AI-MA-2 Capability registry and specialist contract · AI-MA-3 First bounded specialist as a tool/capability · AI-MA-4 Second specialist + bounded parallel execution · AI-MA-5 Artifact-first branch exchange · AI-MA-6 Tracing, observability and failure isolation. "No fixed agent count. No peer-to-peer backbone. No autonomous spawning."

Architecture rules (`02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE`): rules 1–12 (orchestrator owns coordination; governor owns authorization/transition policy/run identity/provenance binding/budget/audit; hierarchy depth two; no peer-to-peer global state; agent-as-tool default; handoff only when materially required; deterministic financial services; artifact exchange; one RunContext; bounded parallelism; everything traceable to run_id). §Complexity budget: one orchestrator, two agent levels maximum, no autonomous spawning, bounded specialist count, bounded parallelism, one RunContext, one trace fabric, one artifact protocol, one policy authority. §Agent qualification: reasoning stays agent-side, calculation stays deterministic-tool-side. §"A new runtime agent requires: distinct capability, distinct contract, explicit tools/permissions, measurable benefit, acceptable coordination cost, owner-approved change record where required." §Failure model: "Provider failure, malformed output, missing evidence, low Data Trust, timeout, budget exhaustion, policy violation, duplicate operation or unavailable specialist must safely fail, degrade or retry under idempotency controls."

Boundaries (`03`): §Orchestrator (owns decomposition, bounded delegation, specialist selection, bounded parallelism, synthesis, termination; does NOT own financial truth); §Specialist (must have purpose, capability, allowed tools, schemas, authority boundary, budget/timeout, trace identity, failure behavior); D-AI-20 (orchestrator control, no peer-to-peer), D-AI-21 (agent-as-tool default; handoff requires justification), D-AI-23 (artifact-first), D-AI-24 (bounded parallelism within explicit budget/rate/resource limits).

Gate class: `02` lines 10–11/202 — pre-G2 work = bounded design/schema/synthetic tests. AI-MA at contract level is exactly that: the RUNTIME (actual orchestrator execution loop, real specialists) is NOT instantiated — it requires the AI-2 research-loop runtime and G2-passed real-data execution. No runtime agent is created; the 17 roles stay governance lenses (D-AI-17/18).

## 2. Deliverable → sub-block traceability (one additive module)

| # | Sub-block | Contract | Acceptance → tests |
|---|---|---|---|
| D1 | AI-MA-2 | `SpecialistContract` (03 §Specialist: purpose, capability, allowed tools, schemas, authority boundary, budget/timeout, trace identity, failure behavior) + agent-as-tool default + handoff-justification rule (D-AI-21) + admission requirements (distinct capability/contract, measurable benefit ref, coordination cost, owner change record where required) | Frozen; handoff without justification refused; admission fields enforced → tests |
| D2 | AI-MA-2 | `CapabilityRegistry` (append-only, idempotent re-register, conflict rejection, distinct-capability enforcement, NO fixed count) | Registry semantics mirror SourceRegistry/EpisodicMemoryLog discipline → tests |
| D3 | AI-MA-1 | `OrchestrationPlan` + `OrchestrationStep` (decomposition bound to one RunContext; two-level depth; bounded fan-out ceiling; deterministic acyclicity check) | Cycle refused; fan-out above ceiling refused; steps traceable to run_id → tests |
| D4 | AI-MA-4 | `execution_waves()` — deterministic bounded-parallel scheduling of a plan's steps (topological waves; refuses ceiling violation; clock-free) | Wave computation pure; parallelism bounded (D-AI-24) → tests |
| D5 | AI-MA-5 | `BranchResult` (artifact-first exchange: large results ONLY by ArtifactRef; inline payload forbidden beyond small explicit summary; addressed to the orchestrator — peer addressing structurally rejected) | Peer-to-peer refusal; artifact-or-summary rule → tests |
| D6 | AI-MA-6 | `TraceEvent` + `TraceLog` (append-only single trace fabric) + `isolate_failure()` (deterministic CONTINUE_OTHER_BRANCHES/TERMINATE_RUN; failure model of 02-product §Failure model) | Trace traceable to run_id/step_id; isolation deterministic → tests |

Cross-cutting: reuses AI1-GC `RunContext`/`ArtifactRef` and AI2-F budget discipline; frozen models; clock-free; no network/LLM/scheduler/thread; no existing module modified; no route; `AI2_ENABLED` untouched; no runtime agent instantiated (D-AI-17/18/41).

## 3. Explicitly out of scope

- Any actual orchestrator/specialist runtime execution, LLM invocation, thread/process spawning, scheduler.
- Financial calculations (stay in deterministic engines, D-AI-19).
- Any HTTP route or config change.
- Any claim that AI-MA runtime exists (D-AI-41): this block delivers the contract layer only.

## 4. Gates

Owner approval: not required for this contract class (`05` §Engineering authority). G2: NOT_PASSED; real-data AI-2/AI-MA execution remains blocked. Push: owner-gated.
