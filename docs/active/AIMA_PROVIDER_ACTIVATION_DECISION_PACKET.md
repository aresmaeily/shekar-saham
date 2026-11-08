# AIMA PROVIDER ACTIVATION — OWNER DECISION PACKET (2026-11-08)

**Status: OWNER-GATED — nothing is activated.** This packet is the decision
material required by the next-stage directive item 1 ("AI-MA real reasoning
seam — owner-gated prep only"). The runtime seam is READY and its contract
tests ship green (`backend/tests/test_aima_provider_seam.py`); a REAL provider
is NOT configured, NOT called, and NOT present in this release. The shipped
executors stay deterministic and synthetic-safe, and any synthetic transport
is honestly labeled `SYNTHETIC_OR_PAPER` — never presented as real LLM
execution (owner directive 2026-11-08 §4).

## What already exists (no owner decision needed)

- THREE shipped advisory specialists with closed tool allowlists, ADVISORY_ONLY
  authority, bounded budgets (invocation ceilings, per-step timeouts), bounded
  parallel plan v2, artifact-first exchange, deterministic synthesis, L2
  autonomy ceiling enforced in-runtime.
- The executor seam (`SpecialistExecutor` protocol + `SpecialistExecutorRegistry`)
  accepts a provider-backed executor implementing the SAME protocol — proven by
  the synthetic transport contract tests (no network, no LLM).
- Fail-closed tool allowlist applies to any transport (`ToolNotPermitted`).
- Budget/timeout enforcement is executor-agnostic (invocation ceiling and
  deadline tests pass for a provider-shaped transport).

## Decisions required from the owner BEFORE any activation

| # | Decision | Options (recommendation in bold) | Reasoning |
|---|---|---|---|
| P-1 | Provider identity | **none this release** / local-only (e.g. an offline model on the owner machine) / hosted API | No credentials exist in this environment (R-3 KEEP-DENIED); hosted APIs create an egress surface the current release forbids |
| P-2 | Egress posture | **no egress** (local model only) / egress allowlist + proxy + audit | The standing invariant is "no egress"; any change is a dated owner act |
| P-3 | Budgets | per-specialist invocation ceiling **≤ shipped contract values**, wall-clock cap, per-run cost cap in RIAL-equivalent tokens | Contract values are already pinned; widening is a separate act |
| P-4 | Kill switch | a dedicated `AIMA_PROVIDER_ENABLED` env gate, default **0 (closed)**, plus the runtime autonomy ceiling L2 unchanged | Fail-closed default matches every other gate in the repo |
| P-5 | Two-Key coupling | provider activation **requires Two-Key authorization** (`requires_two_key=True` posture, R-7) | Consistent with the external-class admission rule |
| P-6 | Data classes allowed to reach the provider | **synthetic/paper only** / declared fixtures / (never: live market data while R-3 denied) | Live data may not enter any AI path before R-3 opens |
| P-7 | Honest labeling | provider-backed branches are labeled with the provider id + trust from the underlying data class; **never labeled as verified or live** | 03:111 evidence rule |
| P-8 | Refusal handling | provider errors/malformed output stay retry-within-budget (max 1) then fail-honest refusal rows | Mirrors the shipped failure model |
| P-9 | Audit | every provider call lands in the AI-3 access/operation audit trail (actor, transport, object refs, refusal reasons) | The durable audit trail is now wired (2026-11-08) |
| P-10 | Persistence of provider outputs | **none by default** — artifacts remain verbatim-returned, not persisted; any persistence goes through a new owner packet | No-persistence is the current shipped posture |

## Standing invariants that do NOT change with activation

`AI2_ENABLED=0` · `verified=False` · `SYNTHETIC_OR_PAPER` evidence class for
live claims · no broker/live trading · no autonomous promotion · no production
mutation · no external notification egress · no credential exposure · Two-Key
Rule · autonomy ceiling L2 · no client-injected plans/budgets.

## Minimal activation checklist (when the owner decides)

1. Owner completes P-1..P-10 above with dated answers.
2. Owner delivers credentials through a secure channel (never chat/git).
3. Engineering implements the adapter behind `AIMA_PROVIDER_ENABLED` (default 0),
   contract tests for the real transport, budget/cost telemetry, and the audit
   wiring — all synthetic-first.
4. Staging verification runs with synthetic/paper data only; owner reviews.
5. Owner signs off; only then may any owner-machine activation occur.
