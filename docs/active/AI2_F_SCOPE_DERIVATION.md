# AI2-F Scope Derivation — AI-2 Required-Items Completion (Corpus `02` §AI-2)

Published BEFORE implementation (governance precedent). Baseline: HEAD `2f86c4a` (AI1-GCa) on `main`, ahead 13/behind 0 vs live `origin/main` `c1984e7`, tracked tree clean, 4 untracked bootstrap paths preserved, amendment corpus byte-identical.

## 1. Authoritative requirement

`02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` lines 44–53: "AI-2 --- Research Loop Hardening / MVRL. Reuse the existing bounded loop: Question → Hypothesis → Candidate → Deterministic Evaluation → Comparison → Learning → Next Hypothesis. **Required:** immutable run identity · provenance · budget/time/iteration limits · evidence artifacts · duplicate detection · failure/recovery · invalidation · human approval state."

Gate context (`02` lines 10–11, 201–202): G2 blocks real-data AI-2 execution; before G2 "only bounded design, schema work, source-registry design, synthetic/paper tests and safe dry-run work are allowed". Import-audit finding **F5** (`docs/governance/evidence/2026-10-18_AMENDMENT_IMPORT_AUDIT.md`) already inventoried the gaps; this block closes them at contract level.

## 2. Item-by-item audit of the existing AI-2 implementation (`backend/app/services/ai2_service.py`, verified in code)

| Corpus required item | Existing state (evidence) | Disposition in AI2-F |
|---|---|---|
| Immutable run identity | ABSENT as first-class field — `AI2Provenance` carries `input_snapshot_sha256` + `created_at_utc` but no run identity (ai2_service.py:153–173) | `AI2RunRecord` binds a canonical `RunContext` (AI1-GC `run_governance.py` — D-AI-22 chain) and freezes it |
| Provenance | PRESENT (`AI2Provenance`: input snapshot hash, prompt hash, provider fields, gates) | Bound into `AI2RunRecord`; verified via `bind_provenance`/`provenance_complete` |
| Budget/time/iteration limits | PARTIAL — request bounds (64 KiB, depth ≤24) + provider timeout/retry exist; no run-level budget/iteration contract | `AI2BudgetSpec` (bounded ceilings, immutable) + deterministic `budget_verdict()` (clock-free: elapsed time passed in) |
| Evidence artifacts | ABSENT (results returned in-response; no artifact contract) | `AI2EvidenceArtifact` binding `ArtifactRef` (AI1-GC) + input digest + trust state |
| Duplicate detection | ABSENT as an explicit mechanism (hash idempotency exists in tests but no detection contract) | Append-only `AI2RunLedger` with deterministic duplicate classification (`DUPLICATE_IDENTICAL` / `DUPLICATE_REPEATED_QUESTION` / `NEW`) — duplicate outputs are flagged, never silently accepted as new |
| Failure/recovery | PARTIAL — deterministic failure mapping (`gated_not_executed`/`failed_provider`/`failed_schema`), bounded retries in the seam | `AI2RecoveryDecision` (deterministic: RETRY_WITHIN_BUDGET / ESCALATE_FAIL_CLOSED) — retries stay bounded by `AI2BudgetSpec`; no automatic unbounded retry |
| Invalidation | ABSENT | `AI2InvalidationRule` — deterministic `invalidates(previous, current)`: trust-state change, data-trust downgrade, or dataset/version change invalidates prior results |
| Human approval state | PARTIAL — `gate_report` reports `g2_owner_acceptance: NOT_RECORDED` globally; no per-run approval state | `AI2RunRecord.approval_state` (reuses AI1-GC `ApprovalState`); governed acceptance requires the provenance-completeness gate |

Not touched: `AI2Request` bounds (corpus defines no conflicting schema — F5), strict output schema, trust gates, `asyncio.to_thread` seam, cancellation containment, `AI2_ENABLED` default (stays `"0"`), no route.

## 3. Deliverables (additive, paper/synthetic class — `02` line 202)

| # | Deliverable | Corpus locus | Acceptance → tests |
|---|---|---|---|
| D1 | `backend/app/domain/ai2_governance.py` — `AI2RunRecord` (frozen; binds RunContext fields + AI-2 provenance fields + approval state + status), `AI2BudgetSpec` + `budget_verdict`, `AI2EvidenceArtifact`, `AI2RunLedger` (append-only + duplicate classification), `AI2RecoveryDecision`, `AI2InvalidationRule` | `02` lines 44–53; D-AI-22/28; AI1-GC contracts | Every required item has a contract + deterministic behavior; ledger flags duplicates; budget verdict refuses exhausted budgets; invalidation fires on trust/version change; approval state required for governed acceptance → tests |
| D2 | Composition acceptance path (test-level): an `AI2Result`-shaped payload (fields copied from the service contract, service untouched) → run record → ledger append → duplicate detection → invalidation check → budget verdict → acceptance gate (`provenance_complete` + approval state) | `02` lines 50–53 | End-to-end deterministic walkthrough of all 8 required items in tests |
| D3 | Governance pointers: STATUS row, CHANGELOG, INDEX, handoff, execution record, state file (untracked) | P3.92 precedent | Consistent with battery evidence |

Out of scope: enabling AI-2 (default stays off), any HTTP route, any LLM/network execution, live data, loop runtime instantiation (the corpus "existing bounded loop" refers to the research loop that AI-2 hardens; its runtime instantiation requires G2-passed real-data execution and is NOT attempted), modification of `ai2_service.py` (composition is test-level; the service's Category A scope is complete per AI2-D residual audit — zero unblocked gaps).

## 4. Gates

Owner approval: not required for this contract class (`05` §Engineering authority). G2: NOT_PASSED — real-data AI-2 execution remains blocked; nothing in AI2-F enables it. Push: owner-gated.
