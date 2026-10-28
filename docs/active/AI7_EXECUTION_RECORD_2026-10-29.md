# AI-7 EXECUTION RECORD — Calibration-Record Contracts (Pre-G2 Contract Class)

**Block:** AI-7 (official roadmap name "AI-7 — Continuous Learning/Productization", `02:102-104`).
**Executed:** 2026-10-29 UTC. **Scope derivation published BEFORE implementation:**
`docs/active/AI7_SCOPE_DERIVATION_2026-10-29.md` (delegated decision D-29-1),
committed as `d7ee374` BEFORE the code commit. **Work class:** pre-G2
authorized contracts + synthetic tests (`02:202`; dependency matrix §AI-7
"Authorized NOW: contract extension only (e.g. calibration-record contracts);
loop runtime BLOCKED" — the AI-4/AI-5 evidence prerequisites named by the
matrix are delivered at the contract class, 51+38 tests). Independent audit:
NOT PERFORMED (D-O2 NOT_APPOINTED) — this is a developer claim, not
independent approval.

## 1. Baseline and authorization

- Block started at HEAD `7c2a6acb34eb465e9a1e6966b9276b1d646efd05` (GOV-28
  final; tracked clean; 58/0 ahead of `origin/main c1984e7…`).
- CONSOL-GOV-29 phase-0 verified the ancestry chain `b2f5e6e` → GOV-24
  commits → `b245fdfa` → AI-5 cycle (`18f702e`/`1fab95d`/`bb2eae5`/`7c2a6ac`)
  in-object; `b245fdfa` is a direct ancestor of the block start.
- Authorization: `AI4_AI7_P343_DEPENDENCY_MATRIX.md` §AI-7 "Authorized NOW:
  contract extension only (e.g. calibration-record contracts); loop runtime
  BLOCKED"; `02:202` pre-G2 class; P3.60 respected (no runtime capability
  added). AI-6 is untouched (external intelligence is a separate lane).

## 2. What was implemented (additive only)

New module `backend/app/domain/calibration.py` (frozen pydantic records;
deterministic; no computation run, no outcome ingestion, no I/O, no network,
no LLM, no scheduler, no clock read) + test module
`backend/tests/test_ai7_calibration_contracts.py` (42 tests). No existing
module modified; no route, no config change, no `AI2_ENABLED` change.

Contract surface:

1. **`CalibrationRecord`** — governed calibration measurement bound to a
   subject by bounded id + kind (`PREDICTION`/`PRODUCT_AUDIT`/
   `RESEARCH_OUTPUT`); does NOT duplicate the P0 prediction/product-audit
   schemas (binding by id avoids schema coupling). At least one real
   measurement required (Brier score, ECE, or ≥1 reliability bucket — an
   empty record is refused at construction). Buckets strictly ascending,
   distinct, bounded 1..32, with honesty arithmetic: bucket counts must sum
   to `sample_size`. `data_class` closed to {SYNTHETIC, PAPER} — LIVE is
   structurally unrepresentable pre-G2 (`02:202`, mirroring the AI-4
   sandbox-admission dataset-origin closure). D-AI-38-lineage coverage
   honesty: incomplete coverage requires ≥1 gap;
   `universal_calibration_claimed: Literal[False]` unrepresentable. Naive
   timestamps rejected (canonical `ensure_utc`).
2. **`AutonomyExpansionEvidence`** — the D-AI-31 EVIDENCE-ONLY record:
   upward-only canonical `AutonomyLevel` pair (`to > from`, equal refused),
   evidence window `end >= start` (aware-only), 1..64 distinct supporting
   calibration ids, `status` pinned `Literal["EVIDENCE_ONLY"]`,
   `approval_state` pinned `Literal["NOT_GRANTED"]` — an approval is
   structurally unrepresentable in this schema (owner-only act per `04:72`
   RACI / T6 lineage).
3. **`autonomy_expansion_permission(evidence)`** — deterministic,
   ALWAYS-refusing permission gate returning `(False, stable ordered refusal
   tags)`; records that recording evidence grants nothing and that expansion
   is an owner decision at a convened review. Defense-in-depth tag for
   `model_construct` bypasses (`no_supporting_evidence` before
   `autonomy_expansion_owner_gated`).

## 3. Verification ledger (exact commands → results)

| Check | Command | Result |
|---|---|---|
| Focused suite | `backend: ../.venv/bin/python -m pytest tests/test_ai7_calibration_contracts.py -q` | **42 passed** (0.20s, first run) |
| pyflakes | repo-venv pyflakes over module + tests | 0 findings |
| Whitespace | `git diff --check` | exit 0 |
| Full battery at block HEAD `9594658…` | `.venv/bin/python scripts/g2_acceptance_battery.py --full-battery --json …/29_harness_report_ai7.json` | **778 passed / 1 skipped / 2 warnings / 79.05s = 736+42 EXACT**; harness exit 0; `"g2_verdict": "NOT_PASSED"` |

No test was weakened or manipulated at any point; the suite passed on the
first run (unlike AI-5, where test-during-development findings were recorded).

## 4. Honest limitations

- Contract layer only: no calibration computation, no outcome-label
  ingestion, no model/prompt evaluation runtime, no loop runtime (dependency
  matrix §AI-7 "loop runtime BLOCKED"; D-AI-31 autonomy-expansion thresholds
  remain an owner call when evidence exists).
- The permission gate is deterministic and always refuses locally; it does
  not simulate, predict, or constrain owner authority beyond the contract
  layer.
- No independent review performed or claimed; AI-7 remains subject to the
  same reviewer chain (D-O2/R-A1/R-A2) as the rest of the pre-G2 surface.
- Completion percentage: NOT_CALCULATED (no canonical roadmap weights).

## 5. Governance state at block HEAD

`G2=NOT_PASSED` (harness verdict literal, pinned) · `AI2_ENABLED=0`
(config.py:109) · `verified=False` (config.py:270) · zero ai2 refs under
`backend/app/api` · protected pins `39ef15cd…`/`6f320a49…` zero-drift ·
bootstrap 4 paths untouched · NO push · NO amend/rebase/reset.
