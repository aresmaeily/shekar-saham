# OWNER DECISION RECORD — B-1 and R2 — RECORDED 2026-10-20

Status: **CANONICAL OWNER-DECISION RECORD — RECORDED**. This file records a
decision received directly from the Project Owner and maps it onto the
canonical decision records. The implementing agent acts as recording secretary
ONLY: the decision text below is quoted verbatim and carries its own
provenance; no wording is paraphrased into authority it does not have. G2
remains `NOT_PASSED`; `AI2_ENABLED=0` (`config.py:109`); `live_verified=false`
(`config.py:270`); LLM NOT EXECUTED; no push. Self-approval is void.

## 0. Provenance of this record

| Field | Value |
|---|---|
| Decision authority | Project Owner (Role 1 A per `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md:72`) |
| Decision date (owner-stated) | 2026-10-20 |
| Owner-stated status | "Owner-directed decision; canonical repository recording pending" — this file performs that recording |
| Delivery channel | Direct owner message received in the governed execution session (IM gateway metadata: channel `zai-web`, session `web-f58053f5-02e8-43fc-b28a-601c9cd1bada`, chat `96973f39-bae3-4eec-b30c-97f02438316c`, trace `1a15ad8d626cf469`) |
| Pre-recording repository state | HEAD `a3030dbbb01d5c409d83b0994b000a2bfd40b3ba` (main); tracked clean; no prior record of this decision in any repository file (all four canonical decision files unchanged since 13:39–14:27Z — pre-recording capture `docs/governance/evidence/raw/2026-10-20_ownerb1r2_baseline/13_decision_files_state.txt` shows `OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md` absent) |
| Recorded by | Implementing agent (governed execution session, 2026-10-20 cycle) — recording only, zero interpretive authority |
| Prior intake finding | CONSOL-GOV-3 audit (same day, HEAD `a3030db`) had found NO owner decision; this message is the first B-1/R2 decision received and post-dates that intake |

## 1. Verbatim decision text (authoritative; quoted in full)

> # Owner Decision — B-1 and R2
> **Project:** RADAR_BOURSE
> **Decision date:** 2026-10-20
> **Authority:** Project Owner
> **Status:** Owner-directed decision; canonical repository recording pending
>
> ## Decision B-1 — Conditional Evidence Acceptance
>
> The owner accepts the independently reproduced test and documentation evidence only within the scope directly supported by the recorded artifacts. This does not constitute final acceptance of any block whose explicit exit criteria remain unmet, does not grant production or live-data authorization, and does not pass G2.
>
> Each of the five B-1 blocks must retain its own evidence-based status. A block may be marked accepted only if its canonical acceptance criteria are satisfied and the required approval authority is recorded. Otherwise, retain `VERIFIED_PENDING_ACCEPTANCE`, `BLOCKED`, or the existing more specific status, as supported by its governing record.
>
> No historical audit result may be rewritten to imply that acceptance existed earlier than it did.
>
> ## Decision R2 — Independent, Documented Review Required
>
> The owner directs R2 to use a formally documented, repeatable procedure with explicit evidence requirements, reviewer independence, reviewer appointment and acknowledgement, review outputs, and recorded acceptance criteria.
>
> The canonical A/B/C options must first be inspected. Select the option that actually implements this decision without weakening independence or required evidence. Do not assign an option letter by inference.
>
> Until the required procedure is formally approved and the independent reviewer is appointed and acknowledges the assignment, R2 remains open and E5 remains `NOT_VERIFIED`.
>
> ## Preserved Governance Boundaries
>
> - `G2 = NOT_PASSED`
> - `AI2_ENABLED = 0`
> - `live_verified = false`
> - No real-data AI-2 execution, runtime integration, production mutation, push, or consequential permission change is authorized by these decisions.
> - AI2-F condition (a) remediation and AI3-M persistence decisions D1–D7 remain unauthorized unless separately and explicitly decided through their canonical owner-decision records.
> - Silence, missing fields, test success, and programmer recommendations do not constitute owner approval.
>
> **Required implementation:** Record this decision in the canonical B-1/R2 and governance decision records, preserve provenance, and report the exact files and diffs. Stop at any boundary that requires an additional owner decision.

## 2. Decision B-1 — effect mapping (recorded per verbatim scope)

**What IS accepted:** the independently reproduced test and documentation
evidence, ONLY within the scope directly supported by the recorded artifacts —
i.e., the captured battery runs, SHA-256 manifests, corpus-integrity checks,
gate captures, and independent audit records at the SHAs they were produced
(evidence lineage: `docs/governance/evidence/raw/2026-10-20_g2prep_battery/`,
`..._consol_precommit/`, `..._consolgov2_battery/`, `..._consolgov2_atcommit/`,
`..._consolgov2_baseline/`, and the independent audit records
`2026-10-18_*_independent_audit.md`, `2026-10-19_AI6_independent_audit.md`,
`2026-10-20_POSTAI3_independent_verification.md`,
`2026-10-20_CONSOLGOV3_independent_audit.md`).

**What is NOT granted by B-1:** final acceptance of any block whose explicit
exit criteria remain unmet; production or live-data authorization; G2 pass;
runtime integration; `AI2_ENABLED=1`; push.

**Per-block status disposition (UNCHANGED, per the decision's own rule):**

| Block | Retained status (evidence-based, per governing record) | Reason |
|---|---|---|
| P0-AMD-1 | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | Evidence accepted conditionally; block acceptance criteria (owner's per-block ACCEPT) not exercised by this decision; exit criteria unmet status preserved |
| AI1-GC | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | Same rule |
| AI2-F | `VERIFIED_PENDING_ACCEPTANCE` with conditions (a)/(b) recorded | Condition (a) disposal remains unauthorized (see §4); condition (b) standing |
| AI-MA-C | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | Same rule |
| AI3-M | `VERIFIED_PENDING_ACCEPTANCE` with persistence routed to owner | D1–D7 remain unauthorized (see §4) |

No historical audit result is rewritten; all audit histories
(FAIL→remediation→PASS chains, G2P-01/G2P-02, E5 = `NOT_VERIFIED`) remain
verbatim-preserved. Every block ledger statement "owner acceptance must be
recorded by the owner" is now partially satisfied at the EVIDENCE level only;
block-level acceptance remains open and requires a per-block recorded decision
(`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §4 remains the per-block
decision form).

## 3. Decision R2 — procedure-option inspection and selection (owner-directed, documented)

**Owner directive (verbatim §1):** formally documented, repeatable procedure
with explicit evidence requirements, reviewer independence, reviewer
appointment and acknowledgement, review outputs, and recorded acceptance
criteria; inspect the canonical A/B/C options first; select the option that
implements the decision without weakening independence or required evidence.

**Inspection record (options locus: `G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md` §1):**

| Option | Documented content | Evaluated against the owner's five required elements |
|---|---|---|
| **A** | Owner supplies the authoritative G2 procedure document into the governance corpus | Not implementable today: no owner procedure document exists (Path B verification `R2_G2_PROCEDURE_VERIFICATION_2026-10-20.md` — NOT_FOUND). Selecting A would leave R2 without any executable path and does not itself produce the required documented procedure |
| **B** | Owner records that the corpus text (`02:32-37` + `04:72` + D-AI-26) IS the whole procedure | **Rejected — weakens required elements**: the corpus text contains participants, RACI, and the gate definition, but NOT explicit evidence requirements, review outputs, or recorded acceptance criteria; adopting it as "the whole procedure" would formalize a thinner procedure than the owner demanded |
| **C** | Approve a procedure drafted FROM the six minimum topics (§3 of the request), through a recorded owner decision naming the approving authority and version; draft prepared on explicit owner instruction | **SELECTED**: the six topics resolve exactly the owner's five required elements (evidence+provenance; objective pass/fail+exceptions; reviewer independence+COI with "implementer's audit chain is evidence, not the review"; execution/findings/remediation/re-review; approval authority/sign-off/versioning/audit trail) and the owner's message IS the explicit instruction contemplated by Option C |

**Selection basis:** the owner's own criteria in the decision text; the
option texts are quoted from the canonical request; no option letter assigned
by inference.

**Execution of Option C to date (stopping exactly at the approval boundary):**

1. Draft prepared: `G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md` —
   status **DRAFT / NOT APPROVED**; resolves the six minimum topics as
   proposals grounded in established repository practice and authoritative
   corpus loci; every section marked PROPOSAL; no effect until formally
   approved.
2. **STOP BOUNDARY (owner action required):** formal approval of the
   procedure — a recorded owner decision naming the approving authority and
   the effective version (Option C's own terms). Until then the draft is a
   proposal only and R2 remains OPEN.
3. Reviewer: the owner decision does NOT designate a reviewer.
   `G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` §3 fields remain blank;
   status stays **NOT_APPOINTED — BLOCKED**; the implementing agent did not
   and will not fill them.
4. Acknowledgement: none possible until a reviewer is designated; E5 remains
   **NOT_VERIFIED** (deliberately preserved in
   `G2_REVIEW_PACKAGE_2026-10-20.md` A5 / `G2_EVIDENCE_MATRIX_2026-10-18.md`
   A5).

## 4. Preserved governance boundaries (affirmed, unchanged)

- `G2 = NOT_PASSED`; `AI2_ENABLED = 0` (`config.py:109`);
  `live_verified = false` (`config.py:270`); LLM NOT EXECUTED; no route to
  any contract module; no push (origin/main = `c1984e7`).
- Not authorized by this decision (remains blocked): real-data AI-2
  execution; runtime integration of any contract module; production
  mutation; push of the 31-commit local chain; consequential permission
  changes.
- **AI2-F condition (a)** remediation: remains unauthorized — the owner
  decision explicitly lists it as requiring separate, explicit decision
  through `AI2F_AI3M_DECISION_RECORD_2026-10-20.md`; no disposal executed.
- **AI3-M persistence D1–D7**: remain unauthorized/unanswered; no adapter
  work.
- Silence, missing fields, test success, and programmer recommendations do
  not constitute owner approval (affirmed and applied in this record).

## 5. Implementation ledger (exact files of this recording cycle)

| File | Action |
|---|---|
| `docs/active/OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md` | NEW — this canonical record |
| `docs/active/G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md` | NEW — Option C draft, NOT APPROVED |
| `docs/active/B1_OWNER_DECISION_MATRIX_2026-10-20.md` | ADDENDUM appended (decision received; statuses unchanged) |
| `docs/active/G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md` | ADDENDUM appended (Option C selected; open until formal approval) |
| `docs/active/R2_G2_PROCEDURE_VERIFICATION_2026-10-20.md` | ADDENDUM appended (Path B + owner direction; still not approved) |
| `docs/active/G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` | ADDENDUM appended (no designation; fields blank; NOT_APPOINTED) |
| `docs/active/AI2F_AI3M_DECISION_RECORD_2026-10-20.md` | ADDENDUM appended ((a) + D1–D7 remain unauthorized) |
| `docs/STATUS.md`, `docs/CHANGELOG.md`, `docs/active/INDEX.md` | Currency rows/entries (+2 index lines) |
| `docs/governance/PROJECT_EXECUTION_STATE.md` | State reconciliation (untracked per evidence convention) |
| Evidence | `docs/governance/evidence/raw/2026-10-20_ownerb1r2_baseline/` (18 captures + manifest), `..._ownerb1r2_battery/` (pre-commit at `a3030db`), `..._ownerb1r2_atcommit/` (at-commit), manifests per convention |
| Commit | Local docs-only commit on `main` (SHA recorded in `docs/STATUS.md` row + CHANGELOG after creation); NO push |

## 6. Remaining owner inputs (blockers after this recording)

1. Formal approval of `G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md`
   (approving authority + effective version), or an owner-supplied procedure
   document (Option A), or an explicit Option B statement — one of the three
   closes the procedure input.
2. Independent reviewer designation (name + role, independent of the
   implementing agent) + the reviewer's acknowledgement → only then E5 can
   move beyond `NOT_VERIFIED`.
3. Review scheduling (date/window) under the approved procedure.
4. Per-block B-1 acceptance decisions, if and when the owner intends block
   acceptance (`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §4 form).
5. AI2-F condition-(a) disposal authorization (explicit, via
   `AI2F_AI3M_DECISION_RECORD_2026-10-20.md`).
6. AI3-M persistence D1–D7 answers (or explicit deferral with date).
7. Push authorization for the unpublished local chain (B-2 / matrix R5) —
   separate decision.
