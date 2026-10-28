# AI-7 SCOPE DERIVATION — Calibration-Record Contracts (Pre-G2 Contract Class)

**Recorded:** 2026-10-29 UTC, BEFORE any code edit of this block (AI-4/AI-5 precedent).
**Authority chain (verbatim loci):**
- `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` lines 102-104: "AI-7 — Continuous
  Learning/Productization: Calibration, model/prompt evaluation, recovery,
  rollback, observability and evidence-based autonomy expansion."
- `02` lines 172-179: AI-7/P10 Product Intelligence & Improvement Loop — audits
  by domain; "market/fundamental AI: Golden Set quality, source grounding,
  freshness, conflict handling, **calibration**, drift and invalidation
  quality"; ranked improvement hypotheses with baseline/evidence/uncertainty/
  cost/risk/rollback; "must not automatically change production, promote
  filters, alter permissions/budgets, or deploy software."
- `02` line 202: pre-G2 authorized class — "bounded design, schema work,
  source-registry design, synthetic/paper tests and safe dry-run work".
- `AI4_AI7_P343_DEPENDENCY_MATRIX.md` §AI-7: "**Authorized NOW:** contract
  extension only (e.g. calibration-record contracts); loop runtime BLOCKED."
  and "BLOCKED: everything operational until AI-4/AI-5 produce evidence" —
  AI-4 contracts are DELIVERED (`AI4_EXECUTION_RECORD.md`, 51 tests) and AI-5
  job contracts are DELIVERED (`AI5_EXECUTION_RECORD_2026-10-28.md`, 38
  tests), so the §AI-7 contract-extension class is the remaining authorized
  lane. D-AI-31 autonomy-expansion thresholds stay an owner call "when
  evidence exists" — this block RECORDS evidence; it grants nothing.
- `05` register D-AI-31 "DEFERRED UNTIL EVIDENCE — Autonomy expands only from
  measured evidence"; 05:200 "D-AI-01 through D-AI-31 remain in force ...
  No live trading, production mutation, auto-promotion, self-escalation or
  self-modifying production logic is authorized by D-AI-32 through D-AI-39";
  05:202 D-AI-41 "Product Capability Is Not Implementation Evidence".
- `04` charter:72 (RACI): G2/autonomy/permission changes are owner-Accountable;
  the implementing agent cannot hold that act (T6 lineage).
- P3.60 "no unauthorized feature" gate: this block adds CONTRACT RECORDS ONLY
  (the `02:202` pre-G2 class), no runtime capability.

**Delegated decision D-29-1 (delegated-not-personal, exercised under the standing
CONSOL-GOV engineering authority):** implement the AI-7 calibration-record
CONTRACT extension as one additive module composing existing canonical types —
`evidence.py` (`SCHEMA_VERSION`, `ensure_utc`) and `run_governance.py`
(`AutonomyLevel` ordering) — WITHOUT duplicating the P0 prediction
(`prediction.py`) or product-audit (`product_audit.py`) schemas: calibration
records BIND to their subjects by bounded artifact id + subject kind, they do
not re-embed them. No runtime, no scheduler, no I/O, no network, no LLM, no
clock calls inside the module.

## In scope (exactly)

1. New additive module `backend/app/domain/calibration.py`:
   - `CalibrationBucket` — one reliability-bucket measurement (bounded:
     `upper_bound` ∈ (0,1], `predicted_mean`/`observed_frequency` ∈ [0,1],
     `count` ≥ 1).
   - `CalibrationRecord` — immutable governed record binding a calibration
     measurement to a subject (`subject_kind` ∈ {PREDICTION, PRODUCT_AUDIT,
     RESEARCH_OUTPUT} + bounded `subject_ref` id); measurement timestamps
     aware-only (canonical `ensure_utc` fail-closed); `data_class` closed to
     {SYNTHETIC, PAPER} per the `02:202` pre-G2 class (LIVE unrepresentable —
     mirrors AI-4 sandbox-admission dataset-origin closure); at least one
     actual measurement required (Brier score, ECE, or ≥1 bucket — an empty
     record is refused); buckets strictly ascending, distinct, ≤ 32; bucket
     count-sum must equal `sample_size` when buckets are present (honesty
     arithmetic); D-AI-38-lineage coverage honesty (`coverage_complete` False
     requires ≥1 `coverage_gap`); `universal_calibration_claimed`
     structurally `Literal[False]`; bounded free-text `calibration_note`.
   - `AutonomyExpansionEvidence` — the D-AI-31 EVIDENCE-ONLY record:
     `from_level`/`to_level` (canonical `AutonomyLevel`, distinct), bounded
     distinct `supporting_calibration_ids` (1..64), aware-only evidence
     window with `window_end >= window_start`, `status` structurally pinned
     `Literal["EVIDENCE_ONLY"]`, `approval_state` structurally pinned
     `Literal["NOT_GRANTED"]` — an approval is unrepresentable in this
     schema (owner-only act per `04:72`/T6; D-AI-31).
   - `autonomy_expansion_permission(evidence)` — deterministic, ALWAYS-
     refusing permission gate returning `(False, stable refusal tags)`;
     records that recording evidence grants nothing and that expansion is an
     owner decision at a convened review; never executes anything.
2. New test module `backend/tests/test_ai7_calibration_contracts.py`
   (synthetic/deterministic only; target ≥ 30 tests).
3. STATUS/CHANGELOG/INDEX bookkeeping rows.

## Explicit exclusions (this block does NOT do)

- No calibration computation at runtime, no outcome-label ingestion, no
  model/prompt invocation, no evaluation execution (D-AI-31 DEFERRED UNTIL
  EVIDENCE; loop runtime BLOCKED per dependency matrix §AI-7).
- No autonomy-level change anywhere: gates, config, and `AutonomyLevel`
  defaults untouched; the expansion gate structurally refuses.
- No modification of `prediction.py`, `product_audit.py`, `monitoring.py`,
  `proactive_research.py`, or any other existing module (binding by id
  avoids schema coupling).
- No live data: `data_class` LIVE unrepresentable pre-G2 (`02:202`).
- No route registration, no config change, no `AI2_ENABLED`/`verified`
  change; protected-file pins and bootstrap paths untouched.

## Verification plan

Focused: `pytest backend/tests/test_ai7_calibration_contracts.py -q`.
Battery at block HEAD (predicted 736 + N_new; exact arithmetic recorded in
the execution record). pyflakes over new files; `git diff --check`; gates/
pins/bootstrap re-check at final HEAD. NO push; NO amend/rebase/reset.
