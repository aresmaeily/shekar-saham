# AI-2 Real-Data Transition — Evidence-Based Prerequisite Checklist (prepared, NOT executed)

**Date:** 2026-10-30 (Asia/Tehran) · **Directive:** CONSOL-GOV-40 Phase 5 · **Prepared for:** a FUTURE owner-authorized AI-2 transition only

**Status of every item below today: UNSATISFIED or OWNER-GATED. This checklist authorizes nothing and changes no gate.**

Safety gates verified this cycle (fresh probes, `gov40_evidence/40_gate_probes.txt`): `AI2_ENABLED` default `0` (`config.py:109`); `verified=False` (`config.py:282`); `execution_mode` SYNTHETIC_OR_PAPER; runtime evaluator refuses the current running commit (`dec77f2…`) with `gate_state_stale` while accepting only the convened review commit `9e7c6a21…` with the unmodified owner decision document.

## Checklists that must ALL be satisfied before any real-data AI-2 execution

### A. Separate owner decisions (three distinct acts — never bundled)
- [ ] **A1. `OA-AI2-LIVE-CREDENTIALS`** — owner provisions live-provider credentials (TSETMC/BRSAPI) in an owner-controlled environment and authorizes the live-validation run. Not granted. (Legacy ID "R3" per the mapping table.)
- [ ] **A2. `OA-AI2-ENABLEMENT`** — owner enables `AI2_ENABLED=1` outside tests for any AI-2 output use beyond advisory. Not granted. (Legacy ID "R4".)
- [ ] **A3. G2 ≠ authorization** — recorded acknowledgment that G2 PASSED (owner-recorded 2026-10-29T19:58:32Z) lifted the review-gate prerequisite only; it does NOT by itself authorize real-data AI-2. This acknowledgment is inherent in the runtime gate design but must be understood, not waived.

### B. Runtime gate binding (fail-closed evaluator, unchanged)
- [ ] **B1.** A gate-state binding exists for the commit that will actually run. Today the tracked state (`docs/active/G2_GATE_STATE.json`) binds `convened_review_commit = 9e7c6a21b8b61e2ccb4dc5f1d2249e6af8773242`; running source at any later commit (including `dec77f2…` and this cycle's HEAD) denies with `gate_state_stale`.
- [ ] **B2.** If the owner intends AI-2 to run at a NEWER commit, a fresh owner-recorded gate-state transition (full verifying chain: decision document + exact hash + complete approval block + running-commit binding) must be recorded first — the transition mechanism exists, the owner act has not occurred.
- [ ] **B3.** Tamper check passes: the owner decision document matches its recorded SHA-256 and carries the complete approval block (probe `owner_decision_unverifiable` refuses otherwise).

### C. Run identity, provenance, evidence
- [ ] **C1.** `run_id` present and unique for the intended run (governed run-identity contracts).
- [ ] **C2.** Provenance completeness satisfied via the canonical `missing_required_provenance` predicate (no missing required fields).
- [ ] **C3.** Evidence chain: every AI-2 input/output carries its evidence referents; no self-referential evidence; no fabricated confidence.
- [ ] **C4.** Data trust states declared for all inputs; synthetic data can never be presented as live (trust-rank precedence pinned).

### D. Budget, time, iteration limits (fail-closed ceilings)
- [ ] **D1.** Explicit budget/time/iteration caps configured for the run — defaults are not authorization; absent caps deny.
- [ ] **D2.** Resource ceilings within the contract hard limits (retry ≤10, timeout ≤3600s, concurrency ≤8, runs/hour ≤60 where monitoring jobs are involved).

### E. Failure, recovery, invalidation, human approval
- [ ] **E1.** Failure-recovery path declared (HALTED semantics + failure alert per monitoring contracts).
- [ ] **E2.** Invalidation conditions declared for every produced object (≥1, per the honesty contracts).
- [ ] **E3.** Named human approver recorded for the run (`approved_by` — zero approvers is a refusal state per the AI-2 governance validators).
- [ ] **E4.** Kill switch ENGAGED-default posture verified for every job involved; RELEASED only by explicit owner configuration.

### F. Environment and provider
- [ ] **F1.** Live-validation completed and recorded (provider probes returning `live_verified=true` ONLY after `OA-AI2-LIVE-CREDENTIALS`; today they are fail-closed `false`).
- [ ] **F2.** `execution_mode` transitions to LIVE only when verified-live data is actually in use (g2_gate `execution_mode()`); SYNTHETIC_OR_PAPER otherwise.
- [ ] **F3.** Secrets never enter the repository, logs, evidence, or this checklist (credential handling stays owner-side).

### G. Post-run discipline
- [ ] **G1.** All artifacts (run records, refusals, warnings) land in dated evidence with hashes.
- [ ] **G2.** No auto-promotion, no self-upgrade, no production mutation (AI-2 output stays advisory until separately governed acceptance).
- [ ] **G3.** Topology preserved: Human Authority → Thin Governor → Central Orchestrator → bounded specialists/deterministic tools → evidence/memory → advisory results → human approval.

**Current tally: 0 of the above items satisfied in their enabling form** (A1/A2 not granted; B1 binds only the convened commit; C/D/E/F/G depend on the owner acts). The checklist is intentionally exhaustive so that the eventual transition is a verification exercise, not a design exercise.
