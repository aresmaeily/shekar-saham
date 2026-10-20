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
