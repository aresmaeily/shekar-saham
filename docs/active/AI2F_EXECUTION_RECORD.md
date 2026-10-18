# AI2-F Execution Record — AI-2 Required-Items Completion

Date: 2026-10-18 · Block: **AI2-F** (AI-2 required-items completion; follows AI2-A…AI2-E) · Baseline at mission start: `2f86c4a` (AI1-GCa) on `main`, ahead 13/behind 0 vs live `origin/main` `c1984e7`, tracked tree clean, 4 untracked bootstrap paths preserved, amendment corpus byte-identical.

## 1. Scope derivation (published before implementation)

Report: `docs/active/AI2_F_SCOPE_DERIVATION.md`. Authoritative requirement: `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` lines 44–53 — eight required items for AI-2. Item-by-item audit of the existing Category A service (`backend/app/services/ai2_service.py`, AI2-A…AI2-E) against each item, cross-checked with import-audit finding F5: present = provenance (+ provider failure mapping, bounded request/seam limits, global G2 gate reporting); absent = first-class immutable run identity, run-level budget/time/iteration contract, evidence artifacts, duplicate detection, invalidation, per-run human-approval state; partial = recovery. The service itself is NOT modified (its Category A residual audit closed with zero unblocked gaps); the completion is a run-governance contract layer that wraps/labels/ledgers/budgets/invalidates/gates AI-2 runs, reusing the AI1-GC canonical run identity.

## 2. Implementation (additive contracts + tests, nothing else)

`backend/app/domain/ai2_governance.py` (frozen, deterministic, clock-free; no network, no LLM, no route, no config change, no existing module modified):

| Corpus required item (02:50–53) | Contract |
|---|---|
| immutable run identity | `AI2RunRecord` (frozen; binds run_id/run_kind/policy_version + task whitelist + input digest + trust + approval + status; structural status rules: COMPLETED requires evidence artifact; non-terminal statuses cannot carry one) |
| provenance | Record fields projected onto the AI1-GC `provenance_complete` gate (`03` §Run provenance); `governed_acceptance` blocks `provenance_incomplete` |
| budget/time/iteration limits | `AI2BudgetSpec` (structurally bounded ceilings: invocations ≤16, iterations ≤64, wall ≤86400s) + `budget_verdict` (clock-free; ceiling-inclusive refusal) |
| evidence artifacts | `AI2EvidenceArtifact` (binds AI1-GC `ArtifactRef` + input snapshot SHA-256 + trust state; D-AI-23 artifact-first) |
| duplicate detection | `AI2RunLedger` (append-only, idempotent/conflict rules, NO update/delete/invalidate path) + `classify_duplicate` → `DUPLICATE_IDENTICAL` / `DUPLICATE_REPEATED_QUESTION` / `NEW` — labels, never silently accepts |
| failure/recovery | `recovery_decision` — deterministic-gate refusals NEVER retried; provider failures retry only while the invocation budget allows (ceiling-inclusive), else ESCALATE_FAIL_CLOSED |
| invalidation | `AI2InvalidationRule` (explicit reason codes; declared_by mandatory) + `invalidates()` — TRUST_STATE_CHANGED / TRUST_DOWNGRADED / DATASET_SUPERSEDED; None version never silently equal; invalidation is a NEW ledger record, never a rewrite |
| human approval state | `AI2RunRecord.approval_state` (AI1-GC ApprovalState) + `governed_acceptance` blocking PENDING/ESCALATED/REJECTED |

Tests: `backend/tests/test_ai2_f_governance.py` (23 tests) — one or more per required item plus an end-to-end composition walkthrough of all eight items (`test_composition_end_to_end_all_eight_required_items`). Development-time defect note (honest record): two initial test expectations were unconstructible/uniformly-too-strict (empty-string policy_version is model-rejected; mismatched identity fires BOTH run_id_binding and provenance_incomplete blockers — the dual firing is correct behavior) — fixed in tests, no implementation change.

## 3. Validation battery (raw `docs/governance/evidence/raw/2026-10-18_ai2f/`)

| Check | Result |
|---|---|
| `pytest -q tests` (repo venv, `backend/`) | **473 passed, 2 warnings** (450 + 23; pre-existing deprecations only) in 77.63s — exit 0 |
| `pytest -q tests/test_ai2_f_governance.py` | **23 passed** in 0.19s — exit 0 |
| `pyflakes app tests` | 0 findings — exit 0 |
| `compileall app tests` | 0 — exit 0 |
| `pip-audit` | "No known vulnerabilities found" — exit 0 |
| `validate_alpha_environment.py` / `validate_alpha_runtime.py` / `validate_frontend_static.py` | all exit 0 |
| `validate_bootstrap_config.py` | 8 checks, 0 FAIL — exit 0 |
| `git diff --check` | 0 |
| Tracked tree | clean pre/post battery; HEAD unchanged at `2f86c4a` during battery |

## 4. Governance reconciliation

Tracked updates committed: STATUS row, CHANGELOG entry, INDEX entries, master-handoff appendix, scope-derivation report, execution record, the domain module, the test file. Untracked (bootstrap-governance set): state-file reconciliation, audit reports, raw evidence. Commit message cites untracked evidence per the established precedent.

## 5. Statuses after this block (separated, not conflated)

- AI-2 required-items completion: **IMPLEMENTED (contract layer, paper/synthetic scope)** — all eight `02` lines 50–53 items now have contracts + deterministic tests; the Category A service is unchanged and remains default-off.
- NOT claimed (D-AI-41): AI-2 runtime/real-data execution stays BLOCKED (G2 NOT_PASSED; owner acceptance of G2 outstanding); `AI2_ENABLED` default off; no route; LLM NOT EXECUTED; `live_verified=false`.
- Research-loop runtime instantiation: NOT attempted (requires G2-passed real-data execution per `02` lines 10–11/201; out of AI2-F scope by design).
- Push: owner-gated (14 local commits after this block).
- Next authorized block (dependency graph `02` line 7): **AI-MA-1..6** — contract-level orchestration/specialist/registry/artifact/traceability layer reusing AI1-GC run-governance + artifact contracts.
