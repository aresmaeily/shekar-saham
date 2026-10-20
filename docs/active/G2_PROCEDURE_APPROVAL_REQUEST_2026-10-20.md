# FORMAL G2 PROCEDURE APPROVAL REQUEST — 2026-10-20 (Consolidated Governance Directive §4, Path B)

Status: FORMAL GOVERNANCE CHANGE REQUEST to the authorized owner / governing
body, required because no valid approved G2 procedure can be established
(companion verification: `R2_G2_PROCEDURE_VERIFICATION_2026-10-20.md` —
NOT_FOUND/NOT_VERIFIED, Path B). **The topics below are a PROPOSAL for formal
consideration — not an existing policy, not an approved procedure, and not a
reconstruction represented as one.** Nothing in this request passes G2, waives
a gate, or self-authorizes anything. G2 remains `NOT_PASSED`.

## 1. What is requested

That the owner (or governing body), as the authority that owns the G2 gate
(D-AI-26 `05:102-107`; owner approval reserved `05:148-150`; RACI Role 1
Accountable `04:72`), either:

- **(A)** supply the authoritative G2 procedure document (owner-authored or
  owner-adopted), placing it in the governance corpus with its approval
  evidence; or
- **(B)** record an explicit owner statement that the existing corpus text
  (`02:32-37` participants + `04:72` RACI + D-AI-26 gate definition) IS the
  whole G2 procedure, with any additional rules the owner wishes to bind; or
- **(C)** approve a procedure drafted FROM the minimum topic set below, through
  a recorded owner decision that names the approving authority and version —
  the draft itself would be prepared only on explicit owner instruction.

Until one of (A)/(B)/(C) is recorded, G2 exit criteria stay BLOCKED and the
review cannot formally conclude — even if convened.

## 2. Why informal reconstruction is insufficient

1. **Authority**: G2 pass is an owner-reserved approval (`05:148-150`); a
   procedure authored by the implementing side and treated as approved would
   be self-approval, which is void under every governance source (decision
   package §3; acceptance ledger; each directive).
2. **Provenance**: the directive requires identity, source, approval status,
   applicable version, and governing authority to be evidenced for a document
   to be authoritative. Scattered definitions in agent-authored worklogs and
   checklists cannot carry that evidence.
3. **Stability**: an unapproved checklist can drift with each cycle; a gate
   decision of this consequence (it gates real-data AI-2 and every downstream
   AI block) requires a version-controlled, change-controlled reference.
4. **Precedent**: the corpus itself is byte-verified, owner-supplied material
   — the same standard applies to any G2 procedure.

## 3. Minimum topics a formally approved G2 procedure must resolve

Proposed for formal consideration (each topic lists what must be decided, not
the decision):

1. **Scope and prerequisites** — what the review covers (contract layers?
   runtime? environment?), mandatory entry prerequisites (E1–E6 or their
   owner-approved equivalents), and the reviewed-SHA fixing convention.
2. **Required evidence and evidence provenance** — which artifacts qualify,
   their required integrity protection (SHA-256 manifests, append-only
   evidence dirs, at-commit batteries), and how historical vs current-run
   evidence are weighted.
3. **Objective pass/fail and exception criteria** — numerical and structural
   criteria (e.g., full-battery green with zero discrepancy, audit-verdict
   requirements, gate-invariant checks), what counts as an exception, who may
   grant one, and how exceptions are recorded.
4. **Independent reviewer qualifications and conflict-of-interest
   requirements** — competence profile (Roles 6/14 per `04:72`), independence
   from the implementing agent and from remediation of the work under review,
   COI disclosure, and whether the implementer's own audit chain (independent
   read-only audits) may substitute for any part of the review (recommended:
   it may not — it is evidence, not the review).
5. **Review execution, findings, remediation, and re-review** — how findings
   are classified (CRITICAL/HIGH/MEDIUM/LOW/INFO or the owner's scheme),
   verdict rules (e.g., the established MEDIUM⇒FAIL-narrow precedent), the
   remediation→delta-re-audit loop, and when a full re-review vs delta
   re-audit is required.
6. **Approval authority, sign-off, version control, and audit trail** — who
   records the verdict (owner, Role 1 A + owner authority), the sign-off block
   contents, document versioning and effective dates, and where the complete
   review trail lives.

## 4. Interim state while this request is open (unchanged, for the record)

- G2 = `NOT_PASSED`; `AI2_ENABLED=0`; `live_verified=false`; LLM NOT EXECUTED;
  no push; no runtime integration of any contract module.
- Review preparation continues lawfully (participant facts + RACI + evidence
  packages are in place and current).
- The decision to convene a review — with or without this request resolved —
  is NOT a decision to pass the gate; the exit decision requires the owner's
  recorded verdict under the authoritative procedure.

## ADDENDUM 2026-10-20 — owner direction received; Option C selected; request OPEN until formal approval

An owner decision on R2 was received 2026-10-20 and is recorded verbatim with
provenance in `OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md`. The owner directs
R2 to use a formally documented, repeatable procedure (explicit evidence
requirements; reviewer independence; reviewer appointment and acknowledgement;
review outputs; recorded acceptance criteria) and directs that the canonical
A/B/C options be inspected and the implementing option selected without
weakening independence or required evidence.

- **Inspection outcome (documented in the canonical record §3):** Option A is
  not implementable today (no owner procedure document exists — Path B
  verification stands); Option B is REJECTED because declaring the corpus
  text the whole procedure would formalize a thinner procedure than the
  owner's five required elements; **Option C is SELECTED** — the owner's
  message constitutes the explicit owner instruction contemplated by C, and
  the six minimum topics resolve exactly the required elements.
- **Draft prepared:** `G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md` —
  status DRAFT / NOT APPROVED; resolves the six topics as proposals with
  authoritative loci; items without corpus basis are marked
  **[OWNER TO CONFIRM]**; approval block intentionally EMPTY.
- **This request remains OPEN** until the owner records formal approval of
  the procedure (approving authority + effective version — Option C's own
  terms), supplies an owner procedure (A), or records an explicit Option B
  statement. Until then: G2 exit criteria remain BLOCKED; R2 remains OPEN;
  E5 remains `NOT_VERIFIED`; G2 = `NOT_PASSED`; all gates unchanged.

## ADDENDUM 2026-10-20 (CONSOL-GOV-4 cycle) — Option C selection now EXPLICIT; request still OPEN

A second owner decision on 2026-10-20 (trace `1a15b105a0662765`; canonical
record `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §1.2) states verbatim:
"The owner selects Option C to prepare a formal, repeatable independent G2
review-procedure draft." This upgrades the Option C selection from
implementing-side inspection (prior addendum) to an explicit owner
statement. The owner also imposed six minimum topics for the draft and the
boundaries: draft remains `NOT APPROVED` until owner-only formal approval;
no reviewer appointment by the implementing agent; R2 stays OPEN,
E5 `NOT_VERIFIED`, G2 `NOT_PASSED` until formal approval AND reviewer
appointment/acknowledgement are evidenced.

- **Request disposition: still OPEN.** Selecting Option C prepares the
  draft; it is not the formal approval that closes this request (that
  requires approving authority + effective version in a recorded owner
  decision), nor an Option A supply, nor an Option B statement.
- Draft coverage of the six topics re-verified this cycle (canonical record
  §4.2). Draft identity unchanged:
  `G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md` (NOT APPROVED; approval
  block EMPTY).
