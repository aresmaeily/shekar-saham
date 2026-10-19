# AI-4 SANDBOX LIMITS — GROUNDED PROPOSAL AND MISSING-EVIDENCE REGISTER

Status: engineering proposal under owner directive 2026-10-19 Decision R4
("Do not invent numeric resource limits. Inspect the official governance
corpus and existing configuration to derive defensible proposals..."). This
document is NOT an owner-approved runtime configuration. Runtime execution
remains disabled: the sandbox execution runtime does not exist and is
post-G2 work (`AI4_AI7_P343_DEPENDENCY_MATRIX.md`; `02:202`).

## 1. Current structural state (verified at HEAD `cc98c64`)

- `backend/app/domain/governed_generation.py` `SandboxBudgetSpec` —
  `max_evaluator_invocations: int = Field(ge=1, le=64)`,
  `max_wall_seconds: int = Field(ge=1, le=86400)` — structural caps with
  NO default values; a caller must supply explicit ceilings and no
  unbounded budget is expressible. The docstring records: "ceiling VALUES
  are engineering-authority defaults with structural bounds; operational
  numbers are owner decisions at runtime integration".
- `sandbox_budget_verdict` is deterministic and ceiling-inclusive
  (`usage.wall_seconds >= spec.max_wall_seconds` refuses); test
  `test_sandbox_budget_verdict_within_and_exhausted`
  (`backend/tests/test_ai4_governed_generation.py:302-316`) asserts the
  ceiling-inclusive refusal at `wall_seconds == max`.
- No sandbox/evaluation runner, no scheduler, no process isolation, no
  resource monitor exists anywhere in the repository (grep-verified in the
  AI-4 scope derivation §3 and audit).

## 2. Governance requirements any limit set must satisfy

| Requirement | Corpus locus |
|---|---|
| Bounded budget/quota owned by the Governor; no self-modified budgets | `03:42-47` (Governor owns budget/quota), `03:19-25` (AI may not self-modify budgets) |
| Bounded parallelism within explicit budget/rate/resource limits | D-AI-24 (`05:88-93`) |
| Sandbox must declare isolation; production contact forbidden | `02:159` "isolated tests"; `governed_generation.py` validators |
| Every job: idempotency, retry ceilings, timeout, concurrency/rate limits, run identity, audit trace, kill switch | `06 §9` (lines 97-102) |
| Cadence/budgets not hard-coded before operational requirements and budgets are approved | `06 §9` line 104; `02:186` |
| Numeric sandbox budgets are owner decisions at runtime integration | `AI4_AI7_P343_DEPENDENCY_MATRIX.md:29-30` |

## 3. Grounded precedents in the existing configuration (no values invented)

| Limit class | Existing grounded precedent | Value & structural cap |
|---|---|---|
| Evaluator/model invocations per run | AI-2 `AI2BudgetSpec.max_provider_invocations` | le=16 (per research run) |
| Iterations per run | AI-2 `AI2BudgetSpec.max_iterations` | le=64 |
| Wall clock per run | AI-2 `AI2BudgetSpec.max_wall_seconds`; AI-4 `SandboxBudgetSpec.max_wall_seconds` | le=86400 s (24 h) in both contracts |
| Evaluator invocations (sandbox) | AI-4 `SandboxBudgetSpec.max_evaluator_invocations` | le=64 |
| Retry attempts | Monitoring `RetryPolicy.max_attempts` / `MAX_RETRY_ATTEMPTS` | le=10 |
| Timeout | Monitoring `BudgetSpec.max_timeout_seconds` / `MAX_TIMEOUT_SECONDS` | le=3600 s |
| Concurrency | Monitoring `BudgetSpec.max_concurrency` / `MAX_CONCURRENCY`; D-AI-24 | le=8 |
| Scheduled runs rate | Monitoring `BudgetSpec.max_runs_per_hour` / `MAX_RUNS_PER_HOUR` | le=60 |

These caps are the project's own previously shipped, audit-passed structural
bounds — the proposal below stays inside them.

## 4. Bounded engineering proposal (PROPOSAL ONLY — NOT owner-approved)

For the future sandbox runtime, per one governed candidate evaluation:

| Parameter | Proposed operational value | Structural cap | Rationale |
|---|---|---|---|
| max_evaluator_invocations | 8 | 64 (existing field cap) | One candidate needs one deterministic evaluator pass per lifecycle attempt; 8 leaves headroom for re-runs after deterministic failure without approaching the AI-2 iteration envelope |
| max_wall_seconds | 3600 | 86400 (existing field cap) | Matches the monitoring per-job timeout ceiling (3600 s); a single synthetic evaluation should not outlive a monitoring job |
| retry_attempts (evaluator invocation) | 3 | 10 (monitoring cap) | Deterministic evaluators fail deterministically; retries only cover transient infrastructure faults, not verdict changes |
| concurrency (candidates in sandbox) | 2 | 8 (monitoring cap / D-AI-24) | Sandbox evaluations are isolated per candidate; parallelism only for genuinely independent work (speed rule `02:106-107`) |
| kill switch | ENGAGED default | — | Monitoring `KillSwitchState` precedent: never released without explicit owner action |

All five proposals reuse EXISTING field caps; none requires widening any
contract. The proposal changes no code: `SandboxBudgetSpec` already accepts
these values within its structural bounds.

## 5. Missing evidence register (why the values stay PROPOSALS)

| Missing item | Consequence | Owner decision / evidence needed |
|---|---|---|
| No deployment environment decision (R3 linkage: `AI3_PERSISTENCE_DECISION_BRIEF.md` D1-D7) | Cannot size wall-clock/memory ceilings for real hardware | Deployment environment decision |
| No measured evaluator cost (no evaluator runtime exists) | Invocation/time ceilings are order-of-magnitude guesses, not evidence | First sandbox runtime measurements under G2-passed data |
| No owner budget approval | `06 §9` forbids hard-coding budgets before operational requirements/budget approval | Owner budget approval at runtime integration |
| No G2 passage | Any real-data evaluation is blocked regardless of limits | G2 owner gate (NOT_PASSED) |
| No sandbox isolation technology decision | CPU/memory/network limits cannot be specified without the isolation mechanism | Runtime-integration design decision (post-G2) |

## 6. Runtime-disabled guarantee (R4)

- The sandbox execution runtime does not exist; no code path in the
  repository can execute a sandbox evaluation (AI-4 audit R4 checkpoint;
  this proposal changes nothing).
- `AI2_ENABLED` default remains off (`config.py:109`); G2 remains
  NOT_PASSED; `live_verified` remains false. No directive in this cycle
  activates any runtime.
- When the runtime is built (post-G2), the monitoring kill-switch-default
  ENGAGED precedent applies, and the operational numbers in §4 require
  owner approval before first release.

## 7. Acceptance tests that already constrain this proposal

- `backend/tests/test_ai4_governed_generation.py`: budget spec field caps
  (unbounded values unrepresentable), ceiling-inclusive verdict refusal
  (`:302-316`), admission gate requires a budget spec on every sandbox
  record; dataset origin closed to SYNTHETIC/PAPER.
- This proposal introduces no new code and therefore no new tests; it
  binds future runtime-integration work to the §4 table and the §5
  register as its acceptance precondition.
