# AI2-F CONDITION (a) — EVIDENCE-BASED DECISION BRIEF — 2026-10-20

Status: **DECISION SUPPORT — prepared under explicit owner authorization**
(second owner decision of 2026-10-20, recorded in
`OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §1.3: "The implementing agent may
prepare an evidence-based decision brief describing the exact condition,
available options, dependencies, risks, reversibility, tests, and gate
impact."). This brief implements exactly that authorization. It does NOT
remediate, does NOT close, does NOT reinterpret the condition, and does NOT
select an option. **AI2-F condition (a) remains OPEN.** Any remediation or
closure requires a separate explicit owner authorization that identifies the
selected option and scope. Self-approval is void.

## 1. The exact condition — precise terminology preserved (no redefinition)

Canonical definition (authoritative source:
`OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md`, Item 3, "Recommended decision";
reproduced verbatim in `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §1.1):

> "Recommended decision: ACCEPT WITH CONDITIONS — conditions: (a) the residual
> observations (status-consultation gap, record-level approver binding,
> unknown-trust-string folding) are dispositioned in the next AI-2 contract
> touch (they are one-commit remediable); (b) nothing here implies AI-2 runtime
> readiness — G2 + owner acceptance (checklist R3/R4) remain prerequisites."

The three named residual observations (same source, Item 3 "Unverified /
incomplete", verbatim):

1. "`governed_acceptance` does not consult `record.status` (a FAILED-status
   record with clean identity and NOT_REQUIRED acceptance would pass —
   undisclosed choice)".
2. "record-level APPROVED has no approver field (the docstring delegates to
   RunContext, but the record's own approval is taken at face value; a test
   kwarg is silently ignored under pydantic v2 `extra=ignore`)".
3. "unknown trust strings rank −1 (below mock) where config folds them to
   synthetic — fail-closed direction but a residual divergence".

**Fresh code verification this cycle (HEAD `bef3a53`, 2026-10-20T20:52Z; raw
capture in the auditor scratch `consolgov4_audit_scratch/06_ai2f_residuals_fresh.txt`):**

| # | Residual | Fresh code evidence (still PRESENT, zero drift) |
|---|---|---|
| 1 | No `record.status` consultation | `backend/app/domain/ai2_governance.py:393-423` — `governed_acceptance(context, record, ...)` checks run_id/run_kind binding, provenance, approval PENDING/ESCALATED/REJECTED; no reference to `record.status` anywhere in the function body |
| 2 | Record-level APPROVED without approver binding | `ai2_governance.py:277-297` — `AI2RunRecord` carries `approval_state: ApprovalState` and NO approver field; the approver requirement lives on the RunContext: `backend/app/domain/run_governance.py:109` (`raise ValueError("approved_state_requires_approver")`) |
| 3 | Unknown trust strings rank −1 vs config folding | `ai2_governance.py:234-241` — `_TRUST_RANK` = {live:2, mixed:1, stale:1, unavailable:1, mock:0, synthetic:0}; unknown strings rank −1 (below mock); `backend/app/core/config.py:191-196` folds anything not in {live, mixed, stale, unavailable} to `"synthetic"` (rank 0) — divergence confirmed, fail-closed direction |

## 2. Available options — reproduced EXACTLY from the canonical owner-decision intake (no invented labels)

The canonical intake (`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §2,
"Evidence needed to dispose condition (a)") offers ONE specified disposal
scope, quoted verbatim, with ONE embedded sub-choice. No option labels are
invented here; the decision outcomes below are framed exactly as the intake
frames them.

**Specified disposal scope (verbatim from the intake):**

> "one remediation commit touching `backend/app/domain/ai2_governance.py`
> (+ its test file) that (i) makes `governed_acceptance` block
> non-COMPLETED/non-terminal statuses (positive + negative tests: FAILED
> record refused even with clean identity); (ii) binds record-level APPROVED
> to a named approver consistent with AI1-GC `ApprovalState` approver
> semantics (test: record without approver refused); (iii) either adopts the
> config folding for unknown trust strings or documents the stricter −1
> ranking as the canonical contract choice with the divergence test-pinned —
> followed by the affected focused tests, an independent re-audit, and a
> fresh at-commit full battery."

**Implications of each element (as recorded in the intake and the decision
record — reproduced, not reinterpreted):**

- **(i) status consultation** — closes residual 1. Positive + negative tests
  required: a FAILED-status record MUST be refused even with clean identity
  and NOT_REQUIRED acceptance. Contract-behavior change: `governed_acceptance`
  becomes strictly stricter (new blocking condition); fail-closed direction
  preserved.
- **(ii) record-level approver binding** — closes residual 2 by binding the
  record's own APPROVED to a named approver, consistent with the AI1-GC
  `ApprovalState` approver semantics already enforced on the RunContext
  (`run_governance.py:109`). Test required: record without approver refused.
  Contract-behavior change: constructing an APPROVED record without an
  approver becomes invalid at the record level.
- **(iii) trust-folding sub-choice (owner selects ONE of the two)** —
  closes residual 3 EITHER by adopting the config folding
  (`config.py:191-196`: unknown → `"synthetic"`, rank 0) OR by documenting
  the stricter −1 ranking as the canonical contract choice with the
  divergence test-pinned. Both sub-choices are fail-closed; they differ in
  whether the contract layer converges with the legacy config mapping or
  deliberately stays stricter. The intake does not pre-select; the owner must.
- **Follow-through (verbatim):** "the affected focused tests, an independent
  re-audit, and a fresh at-commit full battery."

**Decision outcomes the intake supports (exhaustive, as framed by the intake
and the governing records):** (A) authorize the disposal at the specified
scope (owner identifies the (iii) sub-choice in the authorization); or (B)
defer (condition stays OPEN; no work happens). The register review
(`OWNER_DECISION_REGISTER_REVIEW_2026-10-19.md` §D-1) classifies the disposal
as class 3 ("evidence or testing gap rather than an owner decision") and
"one-commit remediable" — but the second owner decision of 2026-10-20
explicitly requires a separate explicit owner authorization; the stricter
rule governs (precedent recorded in `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §1.5).

## 3. Dependencies

- **Upstream:** none for the disposal itself — the three residuals are
  self-contained in `ai2_governance.py` + its test file (verified: the module
  was last touched by remediation `17ef611` and docs fix `e385415`; no drift
  since).
- **Downstream/scope guard:** the intake binds the disposal to ONE commit
  touching exactly `backend/app/domain/ai2_governance.py` (+ its test file).
  No service, API, route, config, or gate file is in scope.
- **Sequencing within governance:** the disposal is contract work; it does
  not require and does not confer G2 progress. Condition (b) remains the
  standing no-runtime-readiness boundary regardless of (a)'s fate.

## 4. Risks

1. **Contract-behavior strictness** — (i) and (ii) add blocking conditions;
   any existing test constructing an APPROVED record without approver, or a
   non-COMPLETED record passing acceptance, would need updating (that is the
   intended effect and is exactly what the required negative tests pin).
2. **Semantic divergence choice ((iii))** — adopting config folding slightly
   WEAKENS the contract's trust strictness (unknown strings would rank 0 =
   synthetic instead of −1); documenting −1 as canonical keeps strictness but
   permanently diverges from the legacy config mapping (must then be
   test-pinned as intentional). Both are fail-closed; the choice affects
   defense-in-depth degree only, not gate state.
3. **Regression containment** — the affected focused suite is the AI2-F block
   (24 tests at HEAD `bef3a53`); the follow-through requires an independent
   re-audit and a fresh at-commit full battery (the established
   remediation→delta-re-audit→at-commit loop used by AI2-Fa, AI1-GCa,
   P0-AMD-1a, G2PREPa).

## 5. Reversibility

- Single commit, single module + test file: fully revertible with a standard
  `git revert` (no data migration, no schema change, no persisted-state
  rewrite, no runtime surface).
- The (iii) sub-choice is likewise revertible at the code level; the only
  durable artifact is documentation + test pins, which reverse with the same
  revert.
- No credential, no network, no data file, no git history rewrite involved.

## 6. Tests

- Required new tests (per the intake, verbatim): positive + negative tests
  that `governed_acceptance` refuses FAILED/non-terminal records even with
  clean identity (i); a test that a record without approver is refused (ii);
  the divergence test pin for whichever (iii) sub-choice is selected.
- Affected existing focused suite: AI2-F block tests (24 passing at HEAD
  `bef3a53`) plus any test constructing records affected by (i)/(ii).
- Follow-through battery (verbatim from the intake): "the affected focused
  tests, an independent re-audit, and a fresh at-commit full battery" — the
  established 18-component battery convention, executed pre-commit and at the
  disposal commit.

## 7. Gate impact

- **None.** The disposal touches a domain contract module only;
  `AI2_ENABLED=0` (`config.py:109`) and `verified=False` (`config.py:270`)
  are untouched; no import surface in `app/api/`/`app/services/` is created;
  `G2` remains `NOT_PASSED`; `live_verified` remains `false`; LLM remains NOT
  EXECUTED.
- Condition (b) ("nothing here implies AI-2 runtime readiness — G2 + owner
  acceptance (checklist R3/R4) remain prerequisites") is INDEPENDENT of (a)
  and remains standing regardless of the (a) outcome.
- Completing (a) would NOT, by itself, make AI2-F block-eligible for owner
  acceptance; per-block acceptance remains the owner's separate §4-template
  decision.

## 8. Decision request (owner only — no self-authorization)

To resolve condition (a), the owner records a separate explicit owner-decision
that identifies: (1) AUTHORIZED or DEFERRED; (2) if AUTHORIZED — the selected
(iii) sub-choice (config-folding adoption vs stricter-−1-canonical
documentation) and the confirmed one-commit scope; (3) any additional
constraints. Absence of response is not approval. Until that decision:
condition (a) stays OPEN and no code in `ai2_governance.py` is touched.

## ADDENDUM 2026-10-21 (CONSOL-GOV-6 cycle) — residuals re-verified PRESENT at `d59ce3e`; for/against option evidence added; condition (a) OPEN

The CONSOL-GOV-6 directive authorizes completing the decision package
("Complete all independent evidence-gathering and documentation now") while
expressly withholding option selection ("the option definitions and their
consequences have not been included in the directive itself" — so the owner
has NOT selected an option).

- **Fresh residual verification at `d59ce3e`** (`consolgov6_audit_scratch/06_ai2f_residuals_fresh.txt`):
  all three residuals PRESENT, zero drift — (1) `record.status` hits in
  `governed_acceptance` (`ai2_governance.py:393-423`) = 0; (2) approver
  hits in `AI2RunRecord` (`:277-297`) = 0 (RunContext enforcement
  `run_governance.py:109` unchanged); (3) `_TRUST_RANK` `:234` + unknown→−1
  `:259` vs `config.py:191-196` folding unchanged. **No AI-2 contract touch
  since `17ef611`** (fresh git log) — the "next AI-2 contract touch" has
  not occurred.
- **For/against option evidence added** (full tables in
  `OWNER_DECISIONS_CONSOLGOV6_2026-10-21.md` §4): for each (iii) sub-choice
  and each decision outcome (A authorize at specified scope / B defer),
  with code-grounded FOR and AGAINST entries. Both (iii) sub-choices are
  fail-closed; they differ in defense-in-depth degree only. Zero gate
  impact for every option.
- **Status UNCHANGED: condition (a) OPEN.** No option selected; no code in
  `ai2_governance.py` touched; no closure, no bypass, no remediation. The
  §8 decision request stands (AUTHORIZED/DEFERRED + (iii) sub-choice +
  scope).

## ADDENDUM 2026-10-21 (CONSOL-GOV-7 cycle) — loci re-verified at `3b61795`; decision-ready option map recorded; condition (a) OPEN (no option authorized)

The CONSOL-GOV-7 directive required the exact canonical options (no
paraphrasing), a per-option map (prerequisites / technical consequences /
required authority / risks / available evidence), fresh code-loci and test
verification, and — absent an exact owner authorization — the condition left
OPEN. Full map: `CONSOLGOV7_R2_READINESS_EVIDENCE_CLOSURE_2026-10-21.md` §3.

- **Authorization check:** no owner record and no GOV-7 directive text
  selects an option (the directive's own branch applies: "produce a
  decision-ready comparison and leave the condition open"). **NO remediation
  executed; condition (a) OPEN.**
- **Fresh loci at `3b61795`** (`consolgov7_audit_scratch/05_ai2f_residuals_fresh.txt`):
  residual 1 — `record.status` hits in `governed_acceptance`
  (`ai2_governance.py:393-423`) = 0; residual 2 — approver hits in
  `AI2RunRecord` (`:277-297`) = 0 (RunContext enforcement
  `run_governance.py:109` unchanged); residual 3 — `_TRUST_RANK` (`:234-241`)
  + unknown→−1 (`.get(state, -1)` `:259`) vs `config.py:191-196` folding
  unchanged. Module+test SHA-256 pinned in the GOV-7 record §3. Touch
  history: only `6aeeaa2` + `17ef611` — no AI-2 contract touch since
  `17ef611`. AI2-F focused tests: 24 passed, exit 0 (GOV-7 battery).
- **Option map (terminology preserved):** the ONE specified disposal scope
  (verbatim intake §2: one commit touching `backend/app/domain/
  ai2_governance.py` + its test file) with elements (i)/(ii)/(iii); TWO
  outcomes (A authorize at the specified scope / B defer) and the embedded
  (iii) sub-choice (A: adopt config folding — rank 0 — vs B: keep stricter
  −1 canonical, test-pinned). Each carries prerequisites, consequences,
  required authority (OWNER for every variant — the stricter rule governs
  over the register's class-3 classification), risks, and code-grounded
  evidence (GOV-6 §4 for/against tables stand). Gate impact: ZERO for every
  option; condition (b) stands regardless.
- **Decision request unchanged (brief §8):** AUTHORIZED/DEFERRED + the (iii)
  sub-choice + scope confirmation. Absence of response is not approval.
