# G2 REVIEW PROCEDURE — DRAFT v0.1 — 2026-10-20 — **NOT APPROVED**

Status: **DRAFT** prepared under the owner decision of 2026-10-20 ("R2 —
Independent, Documented Review Required") via **Option C** of
`G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md` (approve a procedure drafted
from the six minimum topics, through a recorded owner decision naming the
approving authority and version). This document is a PROPOSAL ONLY: it has
**no effect**, binds no one, and does not authorize any review conclusion,
gate decision, or status change until it is formally approved by the owner
with the approving authority and effective version recorded. Until that
approval: R2 remains OPEN, E5 remains `NOT_VERIFIED`, G2 remains
`NOT_PASSED`. Self-approval is void.

Authoritative inputs (all verified current 2026-10-20): `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md:7-11,32-37,200-204`;
`03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md:61-66`;
`04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md:72`;
`05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md:102-107,148-150,197-200` (D-AI-26, engineering-authority clause, D-AI-40);
`AI2_G2_REVIEWER_CHECKLIST.md` §8 (R-rows) + §9 (E1–E6);
`G2_EVIDENCE_MATRIX_2026-10-18.md`; `G2_REVIEW_PACKAGE_2026-10-20.md`.
Items marked **[OWNER TO CONFIRM]** have no corpus basis and are proposed
defaults for the owner to ratify or amend at approval time.

## T1. Scope and prerequisites (PROPOSAL)

- **Scope of a G2 review:** the five delivered pre-G2 block groups
  (P0-AMD-1/P0-AMD-1a, AI1-GC/AI1-GCa, AI2-F/AI2-Fa, AI-MA-C/AI-MA-Ca,
  AI3-M/AI3-Ma) at their contract class (`02:202` — "bounded design, schema
  work, source-registry design, synthetic/paper tests and safe dry-run
  work"), their audit chains, and the evidence packages binding them
  (`G2_REVIEW_PACKAGE_2026-10-20.md`). Runtime capability is OUT of scope
  (D-AI-41: product capability is not implementation evidence) until a
  separately authorized runtime review.
- **Entry prerequisites:** E1–E6 per `AI2_G2_REVIEWER_CHECKLIST.md` §9 (or
  owner-approved equivalents); E5 requires a designated reviewer's
  acknowledgement (see T4) and therefore cannot be pre-satisfied by the
  implementing side.
- **Reviewed-SHA fixing:** the review binds to a single full commit SHA
  recorded at review start (checklist §1 convention); any tree change after
  fixing requires re-fixing or an explicitly scoped delta review.

## T2. Required evidence and evidence provenance (PROPOSAL)

- **Qualifying artifacts:** raw command captures with exit codes and UTC
  timestamps, stored in append-only evidence directories
  (`docs/governance/evidence/raw/<date>_<label>/`), protected by a SHA-256
  manifest; the manifest itself and per-command `.exit` files are excluded
  from their own manifest (fixed-point impossibility for the manifest;
  `.exit` values cross-validated against the hash-protected `.txt` outputs)
  — the established repository convention.
- **Verification batteries:** the established 18-component battery (full
  pytest; seven focused per-block runs; pyflakes; compileall; pip-audit;
  alpha environment/runtime; frontend static; two provider validators
  fail-closed; `git diff --check`; bootstrap structural validator) executed
  pre-commit AND at-commit at the reviewed SHA.
- **Weighting:** current-run evidence produced at the reviewed SHA governs;
  historical evidence is admissible as lineage (battery lineage tables)
  but never substitutes for a current run; inherited claims must be labeled
  as such. Environment/time-dependent findings (e.g., dependency advisories
  surfacing after a clean earlier run) are recorded, classified, and do not
  retroactively invalidate correctly-labeled earlier evidence.

## T3. Objective pass/fail and exception criteria (PROPOSAL)

- **Objective criteria (all must hold for a PASS verdict recommendation):**
  (i) full battery green with zero unexplained discrepancy from recorded
  counts; (ii) every independent audit finding CRITICAL/HIGH/MEDIUM
  dispositioned (remediated or owner-accepted) per the established
  MEDIUM⇒FAIL-narrow precedent; (iii) gate invariants verified in code
  (`AI2_ENABLED=0`, `live_verified=false`, no unauthorized routes); (iv)
  corpus byte-identity 7/7; (v) evidence manifests verify OK.
- **Exceptions:** only the owner may grant an exception; each exception is
  recorded in the review output with its scope, rationale, and expiry; no
  self-granted exceptions. **[OWNER TO CONFIRM: exception record form]**

## T4. Independent reviewer qualifications and conflict-of-interest (PROPOSAL)

- **Competence profile:** Roles 6/14 responsibilities per `04:72` (evidence
  and QA validation) — able to execute the checklist §8 R-rows and §9 E1–E6.
- **Independence:** not a member of the implementing-agent chain; not an
  author or remediator of any work under review; the implementing side's own
  audit chain (independent read-only audits) is EVIDENCE for the review, not
  a substitute for any part of it.
- **Appointment and acknowledgement:** appointment authority rests solely
  with the owner (`04:72` Role 1 A); the appointed reviewer must explicitly
  acknowledge the assignment in writing before the review starts
  (acknowledgement completes E5); the implementing agent must never fill
  appointment fields.
- **COI disclosure:** the reviewer discloses relevant interests at
  acknowledgement; disclosed COIs are adjudicated by the owner.
  **[OWNER TO CONFIRM: disclosure form]**

## T5. Review execution, findings, remediation, and re-review (PROPOSAL)

- **Classification:** CRITICAL / HIGH / MEDIUM / LOW / INFO (the established
  scheme); verdict rules follow the established precedent — any open
  CRITICAL/HIGH, or an open MEDIUM, yields FAIL (or FAIL-narrow where the
  defect is localized and dispositioned); LOW/INFO are recorded and
  dispositioned without blocking.
- **Remediation loop:** findings → remediation commits (scoped, minimal) →
  delta re-audit of the delta; a full re-review (new reviewed-SHA fixing,
  fresh battery) is required when remediation touches the reviewed block's
  code, gate surfaces, or evidence lineage. **[OWNER TO CONFIRM: threshold
  examples]**
- **Review outputs:** a dated review record with: reviewed SHA; per-criterion
  E1–E6 outcomes; findings with classifications and dispositions; verdict
  recommendation; the reviewer's sign-off block. The verdict (pass/fail of
  G2) is recorded by the owner only (T6).

## T6. Approval authority, sign-off, version control, and audit trail (PROPOSAL)

- **Verdict authority:** G2 verdict = owner authority (Role 1 A per `04:72`;
  owner approval reserved per `05:148-150`; D-AI-26 gate definition). A
  convened review NEVER passes the gate by itself.
- **Sign-off block (review output):** reviewed full SHA; procedure identity +
  version; reviewer name/role + acknowledgement date; findings census;
  verdict recommendation; owner decision block (verdict + date + authority).
  **[OWNER TO CONFIRM: exact form]**
- **Versioning:** this procedure, once approved, is versioned
  (`v1.0` at approval), change-controlled through owner-recorded decisions,
  and stored in the governance corpus alongside the byte-verified amendment
  corpus; amendments re-version and re-date the document.
- **Audit trail:** complete review trail (packages, raw captures, manifests,
  findings, verdict records) under `docs/governance/evidence/` (append-only)
  with the reviewed-SHA chain recorded in `docs/STATUS.md` rows and the
  state file.

## Approval block (EMPTY — owner only)

```text
Approving authority:        ______________________
Approved version:           ______________________  (effective on approval)
Approval date (UTC):        ______________________
Approval evidence / locus:  ______________________
```

No field above may be filled by the implementing agent. Absence of response
is not approval. Until this block is filled by the owner, this document is a
draft proposal with no governing force.

## ADDENDUM 2026-10-20 (CONSOL-GOV-4 cycle) — Option C now EXPLICITLY owner-selected; six-topic coverage re-verified; still NOT APPROVED

A second owner decision on 2026-10-20 (trace `1a15b105a0662765`; recorded
verbatim in `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §1.2) states directly:
"The owner selects Option C to prepare a formal, repeatable independent G2
review-procedure draft." The selection previously documented in the approval
request addendum (owner instruction + implementing inspection) is therefore
now grounded in an explicit owner statement — same outcome, stronger
provenance.

- **Six-topic coverage re-verified section-by-section this cycle** (mapping
  table in the canonical record §4.2): owner topics 1–6 map onto T2, T4, T4,
  T5+T3, T3+T6, and the T4 independence clause respectively. All covered;
  items without corpus basis remain marked [OWNER TO CONFIRM].
- **Status UNCHANGED: DRAFT / NOT APPROVED.** The owner's decision prepares a
  draft — it is NOT the formal approval Option C requires (a recorded owner
  decision naming the approving authority and effective version). The
  approval block above remains EMPTY.
- R2 remains OPEN; E5 remains `NOT_VERIFIED`; G2 remains `NOT_PASSED`. The
  implementing agent has not approved this procedure, has not appointed a
  reviewer, and does not declare R2 closed.

## ADDENDUM 2026-10-21 (CONSOL-GOV-6 cycle) — seven [OWNER TO CONFIRM] entries RESOLVED from canonical records; status UNCHANGED: DRAFT / NOT APPROVED

The CONSOL-GOV-6 owner directive authorizes resolving "all implementer-
owned drafting and evidence gaps, including the seven [OWNER TO CONFIRM]
entries identified in CONSOL-GOV-5, wherever the required value can be
established from existing canonical records or the approved governance
framework. For each unresolved item, record the exact source and the
evidence supporting the resolution. Do not invent owner intent, approval
authority, or approval signatures."

The seven resolutions, each grounded in an exact source (full table with
evidence in `OWNER_DECISIONS_CONSOLGOV6_2026-10-21.md` §2):

1. **Exception record form (T3)** — ADOPTED (scope + rationale + expiry +
   granting authority + evidence locus), grounded in the established
   disposition-recording precedent of the independent audit records
   (AI4-06..08, AI6-10..12 ACCEPTED dispositions).
2. **COI disclosure form (T4)** — ADOPTED: field set per the GOV-5
   nomination form §3; owner adjudicates (`04:72`).
3. **Re-review threshold examples (T5)** — ADOPTED with concrete examples
   from the repository's own remediation history (docs-only → delta;
   module-code touch → focused re-verification + delta; gate/evidence-
   lineage touch → full re-review): precedents AI1-GCa `2f86c4a`,
   G2PREPa `d380ee5`, ACCPKGa `a3165c4`, AI2-Fa `17ef611`, AI-4a `cc98c64`,
   AI-6a `1d9030c`.
4. **Sign-off block exact form (T6)** — ADOPTED (reviewed SHA; procedure
   identity+version; reviewer identity+acknowledgement date; E1–E6
   outcomes; findings census; verdict recommendation; owner decision
   block), per `AI2_G2_REVIEWER_CHECKLIST.md` §11 + draft T6 contents.
5. **Entry-prerequisites equivalence (T1)** — TIGHTENED: entry binds to
   E1–E6 exactly; any substitution requires a recorded owner decision
   naming the substituted criterion, replacement, and source (D-AI-40,
   `05:197-200`).
6. **Verdict-rule precedent (T5)** — CODIFIED from six applied audit
   precedents (open CRITICAL/HIGH ⇒ FAIL; open MEDIUM ⇒ FAIL / FAIL-narrow
   only when localized AND dispositioned; LOW/INFO non-blocking).
7. **Approval-act criteria** — ALREADY FIXED by the owner's Option C
   selection (recorded verbatim, trace `1a15b105a0662765`): approval = a
   recorded owner decision naming approving authority + effective version.

- **Status UNCHANGED: DRAFT / NOT APPROVED.** The resolutions are drafting
  completions under implementer authority expressly granted by the
  directive; the approval act remains owner-only. **The approval block
  above remains EMPTY.** No owner intent, approval authority, or approval
  signature is invented.
- R2 remains OPEN; E5 remains `NOT_VERIFIED`; G2 remains `NOT_PASSED`.
- Directive-required topic coverage (7 topics incl. implementer-audit
  separation + approval provenance): verified COVERED — mapping table in
  `OWNER_DECISIONS_CONSOLGOV6_2026-10-21.md` §2.1.
