# G2 REVIEW PROCEDURE — FINAL v1.0 (approved) — 2026-10-23

Status: **APPROVED — v1.0 (effective 2026-10-23).** Approved as the exact
v0.2 consolidation candidate (SHA-256
`0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed9b88a9b2cc65dafc`, approval
block EMPTY at approval time) via the explicit owner delegation recorded in
`OWNER_DELEGATED_DECISIONS_CONSOLGOV16_2026-10-23.md` (decision D-16-1,
2026-10-23T15:34Z): the owner delegated the D-O1 approval decision to the
implementing developer under CONSOL-GOV-16 §1/§4, conditional on full-hash
and traceability verification — both verified and recorded there. This is a
DELEGATED approval: the owner did not personally sign; the approving-authority
field records the delegation chain verbatim. Self-approval did NOT occur
(the delegation instrument is external to the implementing side). Absence of
response is not approval; a later owner decision may supersede this one via
append-only addendum. The reviewer, acknowledgement, COI, and scheduling acts
(D-O2, R-A1, R-A2, D-O3, D-O4) remain separate, NON-delegable, and are NOT
implied by this approval; the G2 verdict itself remains owner authority at a
convened review.

Provenance and precedence:

- The canonical source of every clause below is v0.1 and its addenda at
  commit `c661a617b9f3fba2b70c1ea232f19f389115c8ce` (CONSOL-GOV-10).
- v0.1 and its addenda remain UNTOUCHED canonical historical records under
  the append-only discipline; this v0.2 file is additive and does not
  rewrite them.
- If any wording below were ever found to diverge from v0.1 + addenda, the
  v0.1 + addenda text GOVERNS and the divergence is a defect of this
  consolidation to be corrected before approval — never a licence to
  reinterpret a requirement.
- Upon owner approval of this exact version, the procedure versions to
  **v1.0** (this text with the approval block filled by or for the owner).

Canonical inputs (verified current 2026-10-22): `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md:7-11,32-37,200-204`;
`03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md:61-66`;
`04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md:72`;
`05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md:102-107,148-150,197-200`
(D-AI-26, engineering-authority clause, D-AI-40);
`AI2_G2_REVIEWER_CHECKLIST.md` §8 (R-rows) + §9 (E1–E6) + §11 (sign-off);
`G2_EVIDENCE_MATRIX_2026-10-18.md`; `G2_REVIEW_PACKAGE_2026-10-20.md`
(§A1–§A9 currency chain); nomination record §3; GOV-6 resolution table
(`OWNER_DECISIONS_CONSOLGOV6_2026-10-21.md` §2/§2.1).

## T1. Scope and prerequisites

- **Scope of a G2 review:** the five delivered pre-G2 block groups
  (P0-AMD-1/P0-AMD-1a, AI1-GC/AI1-GCa, AI2-F/AI2-Fa, AI-MA-C/AI-MA-Ca,
  AI3-M/AI3-Ma) at their contract class (`02:202`), their audit chains, and
  the evidence packages binding them. Runtime capability is OUT of scope
  (D-AI-41) until a separately authorized runtime review. [v0.1 T1]
- **Entry prerequisites:** E1–E6 per `AI2_G2_REVIEWER_CHECKLIST.md` §9
  EXACTLY; any substitution requires a recorded owner decision naming the
  substituted criterion, replacement, and source (D-AI-40, `05:197-200`)
  — tightened per GOV-6 resolution #5. E5 requires a designated reviewer's
  written acknowledgement (T4) and cannot be pre-satisfied by the
  implementing side. [v0.1 T1 + GOV-6 #5]
- **Reviewed-SHA fixing:** the review binds to a single full commit SHA
  recorded at review start; any tree change after fixing requires re-fixing
  or an explicitly scoped delta review. [v0.1 T1]

## T2. Required evidence and evidence provenance

- **Qualifying artifacts:** raw command captures with exit codes and UTC
  timestamps, stored in append-only evidence directories
  (`docs/governance/evidence/raw/<date>_<label>/`), protected by a SHA-256
  manifest; the manifest itself and per-command `.exit` files are excluded
  from their own manifest (fixed-point impossibility); `.exit` values are
  cross-validated against the hash-protected `.txt` outputs — the
  established repository convention. [v0.1 T2]
- **Verification battery:** the established 18-component core battery
  (full pytest; seven focused per-block runs; pyflakes; compileall;
  pip-audit; alpha environment/runtime; frontend static; two provider
  validators fail-closed; `git diff --check`; bootstrap structural
  validator) executed pre-commit AND at-commit at the reviewed SHA, plus
  the documented 19th evidence component `pip_state` (certifi `pip show` +
  `pip check`) pinning the GOV-6 dependency remediation — battery-definition
  currency recorded in the GOV-8 addendum; the core 18 components are
  identical component-for-component across GOV-6/7/8/9 cycles. [v0.1 T2 +
  GOV-8 addendum currency note]
- **Weighting:** current-run evidence produced at the reviewed SHA governs;
  historical evidence is admissible as lineage but never substitutes for a
  current run; inherited claims must be labeled as such. Environment/
  time-dependent findings are recorded, classified, and do not
  retroactively invalidate correctly-labeled earlier evidence. [v0.1 T2]

## T3. Objective pass/fail and exception criteria

- **Objective criteria (all must hold for a PASS verdict recommendation):**
  (i) full battery green with zero unexplained discrepancy from recorded
  counts; (ii) every independent audit finding CRITICAL/HIGH/MEDIUM
  dispositioned (remediated or owner-accepted) per the established
  MEDIUM⇒FAIL-narrow precedent; (iii) gate invariants verified in code
  (`AI2_ENABLED=0`, `live_verified=false`, no unauthorized routes);
  (iv) corpus byte-identity 7/7; (v) evidence manifests verify OK. [v0.1 T3]
- **Exceptions:** only the owner may grant an exception; each exception is
  recorded with its scope, rationale, expiry, granting authority, and
  evidence locus (form adopted in GOV-6 resolution #1); no self-granted
  exceptions. [v0.1 T3 + GOV-6 #1]

## T4. Independent reviewer qualifications and conflict-of-interest

- **Competence profile:** Roles 6/14 responsibilities per `04:72` (evidence
  and QA validation) — able to execute checklist §8 R-rows and §9 E1–E6.
  [v0.1 T4]
- **Independence:** not a member of the implementing-agent chain; not an
  author or remediator of any work under review; the implementing side's
  own audit chain is EVIDENCE for the review, not a substitute for any part
  of it. [v0.1 T4]
- **Appointment and acknowledgement:** appointment authority rests solely
  with the owner (`04:72` Role 1 A); the appointed reviewer must explicitly
  acknowledge the assignment in writing before the review starts
  (acknowledgement completes E5); the implementing agent must never fill
  appointment fields. [v0.1 T4]
- **COI disclosure and adjudication — two distinct authorities in two
  distinct clauses (T4 `:90`):** the reviewer discloses relevant interests
  on the adopted disclosure form (field set = nomination record §3, ratified
  GOV-6 resolution #2) AT acknowledgement; disclosed COIs are adjudicated
  BY THE OWNER. The disclosure precedes and enables the adjudication; the
  two acts are tracked as separate readiness rows 2.a/2.b per the GOV-10
  status-schema addendum. [v0.1 T4 + GOV-6 #2 + GOV-10 addendum]

## T5. Review execution, findings, remediation, and re-review

- **Classification:** CRITICAL / HIGH / MEDIUM / LOW / INFO (the
  established scheme). **Verdict rule codified from six applied audit
  precedents (GOV-6 resolution #6):** any open CRITICAL/HIGH ⇒ FAIL; an
  open MEDIUM ⇒ FAIL, or FAIL-narrow only where the defect is localized
  AND dispositioned; LOW/INFO are recorded and dispositioned without
  blocking. [v0.1 T5 + GOV-6 #6]
- **Remediation loop:** findings → remediation commits (scoped, minimal) →
  delta re-audit of the delta. **Re-review thresholds (GOV-6 resolution #3,
  from the repository's own remediation history):** docs-only change ⇒
  delta review; module-code touch ⇒ focused re-verification + delta review;
  gate/evidence-lineage touch ⇒ full re-review (new reviewed-SHA fixing +
  fresh battery). Precedents: AI1-GCa `2f86c4a`, G2PREPa `d380ee5`,
  ACCPKGa `a3165c4`, AI2-Fa `17ef611`, AI-4a `cc98c64`, AI-6a `1d9030c`.
  [v0.1 T5 + GOV-6 #3]
- **Review outputs:** a dated review record with reviewed SHA; per-criterion
  E1–E6 outcomes; findings with classifications and dispositions; verdict
  recommendation; the sign-off block (T6). The G2 verdict is recorded by
  the owner only (T6). [v0.1 T5]

## T6. Approval authority, sign-off, version control, and audit trail

- **Verdict authority:** G2 verdict = owner authority (Role 1 A per
  `04:72`; owner approval reserved per `05:148-150`; D-AI-26). A convened
  review NEVER passes the gate by itself. [v0.1 T6]
- **Sign-off block exact form (GOV-6 resolution #4, per checklist §11 +
  T6):** reviewed full SHA; procedure identity + version; reviewer
  identity + acknowledgement date; E1–E6 outcomes; findings census; verdict
  recommendation; owner decision block (verdict + date + authority).
  [v0.1 T6 + GOV-6 #4]
- **Versioning:** this procedure, once approved, is versioned (v1.0 at
  approval), change-controlled through owner-recorded decisions, and stored
  in the governance corpus alongside the byte-verified amendment corpus;
  amendments re-version and re-date the document. [v0.1 T6]
- **Audit trail:** complete review trail under `docs/governance/evidence/`
  (append-only) with the reviewed-SHA chain recorded in `docs/STATUS.md`
  rows and the state file. [v0.1 T6]

## Annex A — Readiness status schema (binding for current/active readiness reporting; from GOV-10 addendum, unchanged)

1. Every checklist row carries EXACTLY ONE current status (PRIMARY STATUS)
   from the fixed vocabulary: `EVIDENCE_COMPLETE` |
   `INDEPENDENT_REVIEWER_INPUT_REQUIRED` | `OWNER_APPROVAL_REQUIRED` |
   `IMPLEMENTER_ACTION_REQUIRED`.
2. A row MAY additionally record: (i) evidence notes (prose, never status
   labels); (ii) at most one `BLOCKED-BY` reference; (iii) the authority
   that owns the next input (reviewer / owner / implementer).
3. Compound statuses are PROHIBITED. Where one checklist item contains
   requirements owned by different authorities, the item is split into
   lettered sub-rows (`2.a`, `2.b`, …); each sub-row carries exactly one
   status.
4. Sub-rows belong to their parent item; the checklist remains SEVEN items
   (eight tracked rows). All existing cross-references to items 1–7 remain
   valid.
5. This schema governs current/active readiness surfaces: procedure
   addenda, review-package currency addenda, the owner decision package,
   STATUS rows, INDEX entries, and any active review report. Historical
   records retain their original wording (append-only); superseded, not
   rewritten.

## Approval block (FILLED — delegated transcription, D-16-1)

```text
Approving authority:        PROJECT OWNER (delegated per CONSOL-GOV-16 §1/§4;
                            exercised and recorded by the implementing
                            developer in OWNER_DELEGATED_DECISIONS_CONSOLGOV16_2026-10-23.md D-16-1)
Approved version:           v1.0 (approved as v0.2 candidate
                            0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed9b88a9b2cc65dafc)
Approval date (UTC):        2026-10-23T15:34:35Z
Approval evidence / locus:  OWNER_DELEGATED_DECISIONS_CONSOLGOV16_2026-10-23.md §D-16-1
                            (full verification: hash, canonical loci,
                            consolidation fidelity, zero invented criteria)
```

The block above is a DELEGATED transcription explicitly authorized by the
owner's CONSOL-GOV-16 decision (the document's own clause permitting filling
"via verbatim transcription explicitly authorized in the owner's decision").
It is NOT an owner personal signature and is not represented as one. The
reviewer, acknowledgement, COI, and scheduling acts (D-O2, R-A1, R-A2,
D-O3, D-O4) are separate decisions and are never implied by it. The G2
verdict remains owner-only authority at a convened review (T6).

## Version history

- **v1.0 (2026-10-23):** v0.2 candidate approved via delegated owner
  authority (D-16-1); pre-approval candidate hash
  `0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed9b88a9b2cc65dafc`;
  substantive T1–T6/Annex A text byte-unchanged from v0.2; only this header,
  the status paragraph, and the approval block changed.
- **v0.2 (2026-10-22):** proposed final consolidation (not approved; DRAFT).

## Change summary v0.1 + addenda → v0.2 (consolidation only; zero semantic change)

1. T1: incorporated the GOV-6 #5 tightening (E1–E6 substitution rule).
2. T2: incorporated the GOV-8 battery-definition currency note (18-core +
   documented `pip_state` 19th evidence component).
3. T3: incorporated the GOV-6 #1 exception-record form fields.
4. T4: incorporated the GOV-6 #2 COI disclosure form (nomination §3 field
   set) and the GOV-10 two-authority 2.a/2.b articulation.
5. T5: incorporated the GOV-6 #6 codified verdict rule and the GOV-6 #3
   re-review thresholds with their six precedents.
6. T6: incorporated the GOV-6 #4 sign-off block form.
7. Added Annex A carrying the GOV-10 readiness status schema verbatim in
   substance.
8. Added the explicit precedence rule (v0.1 + addenda govern over this
   consolidation in case of divergence) and the D-O1/D-O2/R-A1/R-A2/D-O3/
   D-O4 separation in the approval block.

Nothing else was added, removed, or weakened; no [OWNER TO CONFIRM] item
was resolved beyond the GOV-6-recorded resolutions; no owner-only field is
prefilled; the draft's NOT APPROVED status is unchanged.
