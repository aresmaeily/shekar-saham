# AI-5 EXECUTION RECORD — Proactive-Research Job Contracts (Pre-G2 Contract Class)

**Block:** AI-5 (official roadmap name "AI-5 — Proactive Intelligence", `02:92-95`).
**Executed:** 2026-10-28 UTC. **Scope derivation published BEFORE implementation:**
`docs/active/AI5_SCOPE_DERIVATION_2026-10-28.md` (delegated decision D-28-1),
committed as `18f702ebf223bdbbc68eba54b53d0bacd9a044a5` BEFORE the code commit.
**Work class:** pre-G2 authorized contracts + synthetic tests (`02:202`;
dependency matrix §AI-5 "contract extension only"). Independent audit: NOT
PERFORMED (D-O2 NOT_APPOINTED) — this is a developer claim, not independent
approval.

## 1. Baseline and authorization

- Block started at HEAD `b245fdfa1e3a37e2528b5976a0522f656afa49a2` (GOV-24
  final target; tracked clean; 54/0 ahead of `origin/main c1984e7…`).
- This cycle (CONSOL-GOV-28) first verified the target per directive: all
  four reported GOV-24 commits resolved in-object (`78aafc0c` WP-1,
  `35e0cf85` WP-2, `d5f4ab30` WP-3, `b245fdfa` docs), `b2f5e6e` ancestor
  chain exact (4 commits), reflog commit-only (57 = 1 clone + 56 commits).
- Authorization: `AI4_AI7_P343_DEPENDENCY_MATRIX.md` §AI-5 "Authorized NOW:
  contract extension only … reusing the P0 monitoring schema"; `02:202`
  pre-G2 class; P3.60 respected (no runtime capability added).

## 2. What was implemented (additive only)

New module `backend/app/domain/proactive_research.py` (frozen pydantic
records; deterministic; no I/O, no network, no LLM, no scheduler, no clock
read) + test module `backend/tests/test_ai5_proactive_contracts.py`
(38 tests). No existing module modified; no route, no config change, no
`AI2_ENABLED` change.

Contract surface:

1. **`ProactiveResearchJobSpec`** — composes the P0 monitoring schema
   (`TriggerSpec` / `RetryPolicy` / `BudgetSpec` imported directly, no fork);
   kill switch defaults to ENGAGED (fail-closed); explicit
   research-question bounds (1..16 — enforced in-validator because pydantic
   v2 does not bound variadic tuples); `production_mutation: Literal[False]`
   and `financial_authority: DETERMINISTIC_ONLY` (D-AI-19: financial truth
   stays deterministic; research output is candidate material);
   `coverage_honesty_required: Literal[True]` (D-AI-38); `output_binding`
   pinned to episodic research artifacts.
2. **`ProactiveResearchJobState`** — mirrors the P0 `MonitoringJobState`
   honesty rules (HEALTHY ⇒ zero consecutive failures; HALTED ⇒ failure
   alert sent) + bounded distinct `last_run_artifact_ids` +
   `coverage_report_ref`.
3. **`CoverageFreshnessStatement`** — D-AI-38 record: declared coverage,
   last successful retrieval, freshness age, known gaps, source failures,
   unresolved conflicts; `universal_coverage_claimed` structurally
   unrepresentable (`Literal[False]`); incomplete coverage requires ≥1 gap.
4. **`effective_research_run_permission(spec, state, context, provenance,
   autonomy_ceiling)`** — deterministic permission gate REUSING the P0
   `effective_run_permission` semantics (kill switch RELEASED + state not
   HALTED + job-id match) AND canonical
   `missing_required_provenance` (research additionally requires
   `dataset_version`) AND canonical `assert_autonomy_permitted`; returns
   `(bool, stable refusal tags)`; refusals are machine-readable and ordered.
   Nothing is executed anywhere.

## 3. Verification ledger (exact commands → results)

| Check | Command | Result |
|---|---|---|
| Focused suite | `backend: pytest tests/test_ai5_proactive_contracts.py -q` | **38 passed** (0.21s) |
| pyflakes | repo-venv pyflakes over module + tests | 0 findings |
| Whitespace | `git diff --check` (staged) | exit 0 |
| Full battery at block HEAD `1fab95d9…` | `.venv/bin/python scripts/g2_acceptance_battery.py --full-battery --json …/28_harness_report_ai5.json` | **736 passed / 1 skipped / 2 warnings / 78.71s = 698+38 EXACT**; harness exit 0; `"g2_verdict": "NOT_PASSED"` |

Test-during-development honesty: the first suite run was 15 failed / 23
passed (three test-side issues against canonical rules and one module-side
gap): `run_kind` must match `^[A-Z][A-Z0-9_]*$` (canonical pattern);
`ensure_utc` REJECTS naive timestamps (canonical fail-closed behavior —
test re-pinned to that contract); `RunContext` L4 requires recorded human
approval (canonical); `model_copy` bypasses validation (tests re-pinned via
`model_validate`); and variadic-tuple bounds are NOT applied by pydantic v2
(module-side gap — explicit validator added). Final: 38/38.

## 4. Honest limitations

- Contract layer only: no scheduler runtime, no trigger firing, no retry
  execution, no network/provider contact (D-AI-30 runtime remains
  DEFERRED UNTIL CORE STABILITY — owner judgment gate; cadence/budget
  approval owner-gated per `06 §9`).
- No independent review performed or claimed; AI-5 remains subject to the
  same reviewer chain (D-O2/R-A1/R-A2) as the rest of the pre-G2 surface.
- Completion percentage: NOT_CALCULATED (no canonical roadmap weights).

## 5. Governance state at block HEAD

`G2=NOT_PASSED` (harness verdict literal, pinned) · `AI2_ENABLED=0`
(config.py:109) · `verified=False` (config.py:270) · zero ai2 refs under
`backend/app/api` · protected pins `39ef15cd…`/`6f320a49…` zero-drift ·
bootstrap 4 paths untouched · NO push · NO amend/rebase/reset.
