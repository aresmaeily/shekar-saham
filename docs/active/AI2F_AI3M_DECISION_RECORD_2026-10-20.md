# AI2-F / AI3-M DECISION RECORD — 2026-10-20 (Consolidated Governance Directive §3)

Status: prepared under the Consolidated Governance Directive (§3 AI2-F/AI3-M
condition retrieval, §7 conditional AI2-F remediation). This record retrieves
the EXACT recorded conditions from authoritative sources, verifies them against
the sources and the code, and states the unresolved owner choices. It records
NO owner decision and executes NO remediation. G2 remains `NOT_PASSED`;
`AI2_ENABLED=0`; `live_verified=false`; LLM NOT EXECUTED; no push.

## 1. AI2-F — the exact recorded conditions (verbatim sources)

### 1.1 Condition text (authoritative source: `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md`, Item 3, "Recommended decision")

> "Recommended decision: ACCEPT WITH CONDITIONS — conditions: (a) the residual
> observations (status-consultation gap, record-level approver binding,
> unknown-trust-string folding) are dispositioned in the next AI-2 contract
> touch (they are one-commit remediable); (b) nothing here implies AI-2 runtime
> readiness — G2 + owner acceptance (checklist R3/R4) remain prerequisites."

### 1.2 The three named residual observations (Item 3 "Unverified / incomplete", verbatim)

1. "`governed_acceptance` does not consult `record.status` (a FAILED-status
   record with clean identity and NOT_REQUIRED acceptance would pass —
   undisclosed choice)".
2. "record-level APPROVED has no approver field (the docstring delegates to
   RunContext, but the record's own approval is taken at face value; a test
   kwarg is silently ignored under pydantic v2 `extra=ignore`)".
3. "unknown trust strings rank −1 (below mock) where config folds them to
   synthetic — fail-closed direction but a residual divergence".

### 1.3 Classification claim — "class 3, one-commit, ready" — verified against the source

- **"class 3"** — VERIFIED. `OWNER_DECISION_REGISTER_REVIEW_2026-10-19.md` §D,
  row D-1 (verbatim): "AI2-F residual observations (status-consultation gap,
  record-level approver binding, unknown-trust folding) | **3** | Schedule into
  next AI-2 contract touch (package condition (a)); one-commit remediable".
  Class 3 = "evidence or testing gap rather than an owner decision" (review
  header, verbatim). The classification was made under the 2026-10-19 owner
  directive R7's five-class scheme.
- **"one-commit"** — VERIFIED. Same D-1 row ("one-commit remediable") and the
  acceptance package Item 3 ("they are one-commit remediable").
- **"ready"** — VERIFIED as "specified and unchanged since delivery": the
  disposal specification exists (`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md`
  §2 "Evidence needed to dispose condition (a)": (i) `governed_acceptance`
  blocks non-COMPLETED/non-terminal statuses with positive + negative tests;
  (ii) record-level APPROVED bound to a named approver consistent with AI1-GC
  `ApprovalState` approver semantics (test: record without approver refused);
  (iii) adopt the config folding for unknown trust strings OR document the
  stricter −1 ranking as the canonical contract choice with the divergence
  test-pinned — then affected focused tests + independent re-audit + fresh
  at-commit battery). Fresh code inspection this cycle (§2) confirms the three
  residuals are still present exactly as recorded (last module touch:
  remediation `17ef611`; AI2F-06 docs fix `e385415`) — nothing has drifted.

### 1.4 Fresh code verification (this cycle, 2026-10-20, HEAD `d380ee5`) — residuals still present

| # | Residual | Code evidence (fresh) |
|---|---|---|
| 1 | No `record.status` consultation | `backend/app/domain/ai2_governance.py:393-423` — `governed_acceptance(context, record, ...)` checks run_id/run_kind binding, provenance, approval PENDING/ESCALATED/REJECTED; **no reference to `record.status` anywhere in the function body** (verified by ranged awk extraction + grep) |
| 2 | Record-level APPROVED without approver binding | `ai2_governance.py:277-297` — `AI2RunRecord` carries `approval_state: ApprovalState` and NO approver field; `governed_acceptance` docstring: "APPROVED requires an approver — enforced by the RunContext model itself"; the approver requirement lives in `run_governance.py:109` (`raise ValueError("approved_state_requires_approver")`) — i.e., on the RunContext, not the record |
| 3 | Unknown trust strings rank −1 vs config folding | `ai2_governance.py:234-241` — `_TRUST_RANK` = {live:2, mixed:1, stale:1, unavailable:1, mock:0, synthetic:0}; `invalidates()` uses `.get(state, -1)` so unknown strings rank −1 (below mock); `config.py:191-196` `_legacy_trust_level_from_state` folds anything not in {live, mixed, stale, unavailable} to `"synthetic"` (rank 0) — divergence confirmed, fail-closed direction |

Conclusion: condition (a) is **OPEN and disposal-ready but NOT disposed**;
condition (b) is **disposed by construction and remains disposed** while the
gates hold (`AI2_ENABLED=0` `config.py:109`; `verified=False` `config.py:270`;
no AI-2 import surface in `app/api/`/`app/services/` — fresh captures
`raw/2026-10-20_consolidated_baseline/08_gates_source.txt`).

### 1.5 Why the disposal was NOT executed in this cycle (authority analysis, recorded honestly)

Two governance rules are in play and the stricter one governs:

1. The 2026-10-19 register review classifies the disposal as class 3
   ("evidence or testing gap rather than an owner decision") — under that
   classification alone, no owner decision would be required.
2. The CURRENT governing directive (Consolidated Governance Directive §7)
   states: "Only if the owner explicitly authorizes the work and the
   authoritative AI2-F conditions have been verified" shall remediation be
   implemented, and "If authorization or conditions are missing, do not
   implement AI2-F remediation. Continue safe documentation and decision
   preparation instead." The same directive §1 states it "does not constitute
   owner approval".

The conditions ARE verified (§1.3–1.4). The explicit owner authorization is
**ABSENT**. Therefore the remediation was **NOT implemented** in this cycle and
the exact decision request is presented to the owner: authorize the one-commit
disposal of condition (a) per the already-specified scope
(`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §2), or defer it. Either answer
unblocks or keeps blocked exactly one bounded contract commit in
`ai2_governance.py` + its test file; no other scope is affected.

## 2. AI3-M — the exact recorded condition (verbatim sources)

### 2.1 Condition text (authoritative source: `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md`, Item 5)

> "Recommended decision: ACCEPT (as pre-G2 contract deliverable) **with the
> persistence decision explicitly routed to the owner** via
> `AI3_PERSISTENCE_DECISION_BRIEF.md` (which lists the missing owner decisions;
> it does not choose for the owner)."

Execution record corroboration (`AI3M_EXECUTION_RECORD.md` §3, verbatim):
"**Persistence technology**: the corpus specifies no storage engine/format/
service for AI-3. The deterministic in-memory stores are delivered; actual
persistence is an owner-environment deployment decision."

### 2.2 The unresolved owner choices (D1–D7, from `AI3_PERSISTENCE_DECISION_BRIEF.md` §D — verbatim labels)

| ID | Unresolved choice | Consequence of each supported option (from the brief + evaluation) |
|---|---|---|
| D1 | Engine class: embedded single-operator (Option 1 SQLite+blobs / Option 2 JSONL+blobs) vs server-class (Option 3 Postgres) | Opt1: lowest ops delta, app-level immutability (triggers possible), indexed PIT; Opt2: strongest natural format-level immutability, weakest access control; Opt3: storage-level grants + full concurrency, high deploy burden |
| D2 | Deployment target for the AI runtime (Windows host / Docker / Electron-bundled) | Currently BLOCKED upstream at P3.43 launch gates; deciding D2 before P3.43 prerequisites resolve would be speculative |
| D3 | Immutability guarantee class (application-enforced / storage-enforced / format-enforced) + periodic hash audits | Determines which option satisfies the owner's guarantee bar; the evaluation recommends trigger-level (M3) as the default for Option 1 |
| D4 | Access-control model + who may read episodic evidence (A8 approval-state interaction) | Option 3 strongest; Option 1 file-permission+hash class; Option 2 weakest |
| D5 | Backup/retention/DR policy (cadence, copies, offsite) | The archive itself must never be purged (A3/A11); backups are replication, not retention — policy is owner's regardless of engine |
| D6 | Blob-store location (inside/outside repo tree) + size ceilings | Engineering default proposed: outside repo tree, content-addressed (register review D-4); ratification is the owner's (same class as the P0 numeric-ceiling ratification) |
| D7 | Timing: decide now (pre-G2, adapter testable in synthetic runs) vs after G2 | Evaluation A-5/register review D-7 resolution: defer adapter until D2/D3/D4 answered; contract layer unaffected either way; no migration performed |

### 2.3 Current engineering position (recommendation, NOT a decision)

`AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` §7 designates the incumbent
**SQLite WAL + JSONL as PREFERRED CANDIDATE** with limitations, migration plan,
and acceptance tests specified — "NO migration performed". This remains a
candidate designation only; D1–D7 remain open with the owner.

### 2.4 Evidence needed to dispose (unchanged from the decision package §2)

An owner decision record that (i) selects the persistence approach (or defers
with a date), (ii) ratifies the D3 immutability guarantee class, and (iii)
ratifies or amends D4/D6 blob-store location and ceilings. Until then,
**AI-3 persistence integration is PROHIBITED** (directive Step 5 / §8; D-AI-28
discipline). Even after the owner decision, the persistence adapter itself is
runtime work that lands **post-G2** — the decision unblocks planning, not
integration.

### 2.5 Recorded residual (no disposal required for acceptance)

`lessons_active_at` one-sided conservative PIT semantics (AI3M-02 INFO,
disclosed in docstring + test + record; status-event log noted as a future
additive option only if strict PIT reconstruction is ever needed). Live feeding
of episodic artifacts requires the G2-passed research runtime — post-G2
sequencing, not an acceptance condition.

## 3. Decision request summary (for the owner)

1. **AI2-F condition (a)**: authorize / defer the one-commit disposal of the
   three named residuals in `ai2_governance.py` (+ tests), scope exactly as
   specified in `OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §2. Conditions are
   verified (this record §1.3–1.4); only the explicit authorization is missing.
2. **AI2-F condition (b)**: acknowledge the standing no-runtime-readiness
   boundary (no action required; disposed by construction).
3. **AI3-M persistence**: answer D1–D7 (select an option per D1, or defer with
   a date and ratify D3/D4/D6), or explicitly leave them deferred — the
   delivered contract layer, its 13 tests, and G2 readiness are unaffected
   either way (dependency-isolated by design).

No field above may be filled by the implementing agent. Absence of response is
not approval. While any item is unanswered, all gates and the prohibited set
(`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §3) remain in force unchanged.

## ADDENDUM 2026-10-20 — owner decision received; AI2-F (a) and AI3-M D1–D7 remain unauthorized

The owner decision of 2026-10-20 (recorded verbatim with provenance in
`OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md`) explicitly states:

> "AI2-F condition (a) remediation and AI3-M persistence decisions D1–D7
> remain unauthorized unless separately and explicitly decided through their
> canonical owner-decision records."

Applied to this record, per the stricter-rule-governs principle already
recorded above:

1. **AI2-F condition (a)**: disposal of the three named residuals in
   `backend/app/domain/ai2_governance.py` was NOT executed in this cycle and
   remains **unauthorized** despite the earlier class-3 classification — the
   owner decision's explicit listing governs. Condition (a) status: OPEN.
2. **AI2-F condition (b)**: standing no-runtime-readiness boundary unchanged;
   disposed by construction while gates hold.
3. **AI3-M persistence D1–D7**: remain unanswered/unauthorized; no adapter,
   migration, or storage work performed or authorized. Condition status:
   OPEN.
4. The owner decision's B-1 evidence acceptance does NOT change this record:
   block-level acceptance for AI2-F and AI3-M remains open, and the per-block
   statuses retain `VERIFIED_PENDING_ACCEPTANCE` with these conditions
   recorded (canonical record §2).

## ADDENDUM 2026-10-20 (CONSOL-GOV-4 cycle) — second owner decision: (a) stays OPEN; brief preparation AUTHORIZED (prepared); D1–D7 stay OPEN with per-item register

A second owner decision on 2026-10-20 (trace `1a15b105a0662765`; recorded
verbatim in `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §1.3/§1.4) states:

> "AI2-F condition (a) remains OPEN. No code change, remediation, bypass,
> closure, or reinterpretation of condition (a) is authorized by the B-1 or
> R2 decisions. … Any remediation or closure requires a separate explicit
> owner authorization that identifies the selected option and scope."

> "AI3-M decisions D1–D7 remain OPEN unless a specific, existing, verifiable
> owner decision explicitly resolves an individual item. No approval may be
> inferred from B-1 evidence acceptance, the R2 Option C selection, or the
> preparation of the G2 procedure draft. No architecture, persistence,
> autonomy, runtime, permission, or consequential-behavior change is
> authorized by this decision."

Applied to this record:

1. **AI2-F condition (a): OPEN — unchanged.** No remediation executed. The
   owner DID authorize preparing an evidence-based decision brief; that brief
   is delivered: `AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md` (exact
   condition terminology preserved; canonical intake disposal scope quoted
   verbatim incl. the (iii) sub-choice; dependencies/risks/reversibility/
   tests/gate impact; separate explicit owner authorization required). The
   three residuals were fresh re-verified present at HEAD `bef3a53` this
   cycle (zero drift; §1.4 table stands, with the RunContext enforcement
   locus precisely `backend/app/domain/run_governance.py:109`).
2. **AI2-F condition (b): standing no-runtime-readiness boundary unchanged.**
3. **AI3-M D1–D7: OPEN — unchanged**, now with the owner-required PER-ITEM
   register (definition / status / provenance / unresolved choice /
   dependencies / impact / risk / verification evidence / required
   authority) recorded in `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §6.
   No item status was changed; no missing decision invented.
4. Per-block statuses retain `VERIFIED_PENDING_ACCEPTANCE`; B-1 evidence
   acceptance (reaffirmed and sharpened by the second decision) does not
   accept or reject any block by implication.

## ADDENDUM 2026-10-21 (CONSOL-GOV-6 cycle) — condition (a) remains OPEN; D1–D7 seven decision records delivered (preparation only; nothing executed)

- **AI2-F condition (a): OPEN** — residuals re-verified PRESENT at
  `d59ce3e` zero drift; no AI-2 contract touch since `17ef611`; the
  CONSOL-GOV-6 directive authorizes PREPARATION ONLY and selects no option
  (for/against comparison delivered in
  `OWNER_DECISIONS_CONSOLGOV6_2026-10-21.md` §4). No remediation executed;
  condition (b) standing unchanged.
- **AI3-M D1–D7: all seven remain OPEN;** seven separate decision records
  delivered (`OWNER_DECISIONS_CONSOLGOV6_2026-10-21.md` §5.1–§5.8 —
  canonical wording, options+provenance, consequences, evidence,
  dependencies, reversibility, tests, authority, permitted disposition).
  **Nothing executed** — no option is selected by any owner record or by
  CONSOL-GOV-6; persistence integration remains PROHIBITED (D-AI-28).
  **D2 explicitly NOT complete**: upstream-blocked at the P3.43 launch
  gates (INSTALL not issued; Windows validation NOT_STARTED; browser-E2E +
  Electron NOT_VERIFIED; live provider verification fail-closed
  `live_verified=false`; push authorization outstanding) — dependency
  verified fresh this cycle from `AI4_AI7_P343_DEPENDENCY_MATRIX.md` §P3.43
  + state file §7.
- Related B-1 effect recorded this cycle: per-block disposition REJECT ×5
  (owner-authorized, binding rule) — AI3-M's rejected item is the absent
  owner persistence decision record; AI2-F's rejected item is unmet
  condition (a). See `B1_OWNER_DECISION_MATRIX_2026-10-20.md` GOV-6
  addendum + `OWNER_DECISIONS_CONSOLGOV6_2026-10-21.md` §1.

## ADDENDUM 2026-10-21 (CONSOL-GOV-7 cycle) — D1–D7 evidence-reconciliation matrix recorded; nothing executed; D2 explicitly NOT complete (P3.43 dependency preserved)

The CONSOL-GOV-7 directive required a per-item evidence reconciliation
(exact requirement + canonical source; status + loci; dependency/blocking;
required evidence; work type — documentation-only / testable implementation /
owner-controlled; permitted next action; verification result) with the
P3.43 dependency of D2 preserved and no completion claimed from record
creation alone. Full matrix: `CONSOLGOV7_R2_READINESS_EVIDENCE_CLOSURE_
2026-10-21.md` §4.

- **Fresh selection search** (`consolgov7_audit_scratch/08_ai3m_owner_record_search.txt`):
  zero SELECTED/RESOLVED/DECIDED hits for any D-option across the canonical
  owner-decision records; 13 OPEN-status hits — **no owner decision record
  exists**; D1–D7 all OPEN.
- **Fresh structural verification:** episodic immutable surface in
  `research_memory.py:119-158` intact (append/get/index only; "NO update,
  delete, retention-purge or rewrite path" :123); module untouched since
  `37c529d`/`80585c8`; incumbent backup mechanism present
  (`app/data/store.py:62-66`); **13/13 AI3-M tests exit 0** (GOV-7 battery).
- **D2 upstream-blocked at P3.43 — fresh-verified** (scratch
  `10_p343_gates_fresh.txt`): (1) INSTALL — no positive authorization record;
  (2) Windows-target validation NOT_STARTED (state file :252); (3) browser-E2E
  + Electron NOT_VERIFIED; (4) live provider verification fail-closed
  (`live_verified=false`, GOV-7 battery ×2); (5) push authorization
  outstanding. **D2 is NOT complete.**
- **Nothing executed:** persistence integration remains PROHIBITED
  (D-AI-28); no option selected; work types per item are owner-controlled
  (D1/D2/D3/D4/D5/D6 ratification-or-decision; D7's engineering defer-
  resolution stands per register A-5 with the owner-facing timing question
  open).
