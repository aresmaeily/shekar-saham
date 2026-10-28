# AI-5 SCOPE DERIVATION — Proactive-Research Job Contracts (Pre-G2 Contract Class)

**Recorded:** 2026-10-28 UTC, BEFORE any code edit of this block (AI-4/AI-6 precedent).
**Authority chain (verbatim loci):**
- `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` lines 92-95: "AI-5 — Proactive Intelligence: Scheduled/event-triggered bounded research with budget, observability, recovery and kill switch."
- `02` lines 155-156: governed scheduled/event-triggered monitoring of the configured source universe; coverage gaps and inaccessible sources must be reported; respect rate limits, budgets and kill switches.
- `02` line 186: "Cadence, thresholds and budgets require explicit configuration, observability, idempotency, retry ceilings and a kill switch."
- `02` line 202: pre-G2 authorized class — "bounded design, schema work, source-registry design, synthetic/paper tests and safe dry-run work".
- `AI4_AI7_P343_DEPENDENCY_MATRIX.md` §AI-5: "Authorized NOW: contract extension only (e.g. proactive-research job contracts reusing the P0 monitoring schema); scheduler runtime is owner-gated (D-AI-30 + cadence/budget approval)."
- `05` register D-AI-30 "DEFERRED UNTIL CORE STABILITY — Requires budget, observability, recovery and kill switch"; D-AI-38 coverage/freshness/source-access honesty; D-AI-32/38 not authorizing live behavior (`05:200`).
- `06` charter §9: idempotency, retry ceilings, run identity, audit trace, failure alert, kill switch; cadence must not be hard-coded before operational requirements and budgets are approved.
- P3.60 "no unauthorized feature" gate: this block adds CONTRACT RECORDS ONLY (the `02:202` pre-G2 class), no runtime capability.

**Delegated decision D-28-1 (delegated-not-personal, exercised under the standing
CONSOL-GOV engineering authority):** implement the AI-5 proactive-research JOB
CONTRACT extension by COMPOSING the P0 monitoring schema types (`TriggerSpec`,
`RetryPolicy`, `BudgetSpec`, kill-switch/failure-state semantics from
`monitoring.py`) with the canonical run-identity/provenance/autonomy helpers
(`run_governance.py`), adding research-specific honesty fields required by
D-AI-38. No scheduler, no trigger evaluation, no I/O, no network, no LLM, no
clock calls inside the module.

## In scope (exactly)

1. New additive module `backend/app/domain/proactive_research.py`:
   - `ProactiveResearchJobSpec` — immutable job specification composing P0
     `TriggerSpec` + `RetryPolicy` + `BudgetSpec`; fields
     `research_job_id`, deduped bounded `research_questions` (1..16),
     `evidence_ref` (research-memory binding), `output_binding`
     fixed to episodic research artifacts, `production_mutation`
     structurally `Literal[False]`, `financial_authority` fixed to
     `"DETERMINISTIC_ONLY"` (D-AI-19: financial truth stays deterministic;
     research outputs are candidates, never financial truth),
     `coverage_honesty_required: Literal[True]` (D-AI-38), kill switch
     default `"ENGAGED"` (fail-closed, mirroring `MonitoringJobSpec`).
   - `ProactiveResearchJobState` — mirror of `MonitoringJobState` honesty
     fields + `coverage_report_ref` + bounded `last_run_artifact_ids`;
     same HEALTHY/HALTED consistency rules.
   - `CoverageFreshnessStatement` — D-AI-38 record: declared coverage,
     last successful retrieval, freshness age, known gaps, source failures,
     unresolved conflicts; `universal_coverage_claimed` structurally
     unrepresentable; gaps must be non-empty when coverage is not complete.
   - `effective_research_run_permission(spec, state, context, provenance,
     autonomy_ceiling)` — deterministic gate reusing `effective_run_permission`
     semantics (kill switch RELEASED + state not HALTED + job-id match) AND
     canonical `missing_required_provenance` + `assert_autonomy_permitted`;
     returns `(bool, tuple[str, ...] refusals)`; no execution anywhere.
2. New test module `backend/tests/test_ai5_proactive_contracts.py`
   (synthetic/deterministic only; target ≥ 28 tests).
3. STATUS/CHANGELOG/INDEX bookkeeping rows.

## Explicit exclusions (this block does NOT do)

- No scheduler/event runtime, no trigger firing, no retry execution.
- No network access, provider contact, live scanning, or crawl (02:203).
- No cadence/threshold/budget VALUES baked in (all owner-configured at
  construction; `06 §9`).
- No research-loop execution, no AI-2 route, no `AI2_ENABLED`/`verified`
  change, no route registration, no existing-module modification.
- Protected-file pins and bootstrap paths untouched.

## Verification plan

Focused: `pytest backend/tests/test_ai5_proactive_contracts.py -q`.
Battery at block HEAD (predicted 698 + N_new; exact arithmetic recorded in
the execution record). pyflakes over new files; `git diff --check`;
gates/pins/bootstrap re-check at final HEAD. NO push; NO amend/rebase/reset.
