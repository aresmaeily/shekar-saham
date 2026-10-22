# G2 INDEPENDENT REVIEWER PACKAGE v1.0 — DRAFT — 2026-10-22 — **NOT APPROVED**

Status: **DRAFT / NOT APPROVED.** This package is implementer-prepared reviewer-side
tooling under the CONSOL-GOV-13 remediation mandate (Section 5). It consolidates —
without semantic change — the reviewer requirements already fixed in the canonical
corpus: `G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md` (T1–T6, Annex A),
`G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` (§1–§4), `AI2_G2_REVIEWER_CHECKLIST.md`
(§1–§11), and the GOV-6 resolutions recorded in
`OWNER_DECISIONS_CONSOLGOV6_2026-10-21.md` §2. It appoints NO ONE, grants NO access,
approves NOTHING, and fills NO owner-only field. The forms below become operative
ONLY when: (1) the owner approves the procedure (D-O1, by version + SHA-256);
(2) the owner appoints a real named reviewer (D-O2, all eight §3 nomination fields);
(3) the appointed reviewer completes R-A1 (written acknowledgement → completes E5)
and R-A2 (COI declaration); (4) the owner adjudicates disclosed COIs (D-O3) and
schedules the review (D-O4). Silence is not approval. Self-approval is void.

Canonical sources (verified current 2026-10-22): procedure v0.2
(SHA-256 `0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed9b88a9b2cc65dafc`);
charter `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md:72`
("G2: 1(A), 6/14(R), 9/10/15(C)"); decision register `05:102-107` (D-AI-26),
`05:148-150` (owner-approval reservation), `05:197-200` (D-AI-40);
roadmap `02:7-11,32-37,200-204`.

## §1 Objective qualification criteria (checkable before appointment)

A reviewer candidate QUALIFIES only if every item below holds; each item is
verified from evidence the OWNER supplies with the nomination (class per
`G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` §1–§2):

- [ ] Q1 Independence — person is NOT a member of the implementing-agent chain
      (no commit in the local governance chain: all 40 local-only commits are
      authored `Z User <z@container>`; authorship census of all 103 commits
      recorded in `CONSOLGOV12_REPOSITORY_ACCESS_RESTORED_R2_REVIEW_READINESS_
      2026-10-22.md` Block E; implementing-side identities are a DISQUALIFIED
      class for reviewing their own work).
- [ ] Q2 Non-authorship — person is not an author or remediator of any of the
      five reviewed block groups (P0-AMD-1/1a, AI1-GC/GCa, AI2-F/Fa,
      AI-MA-C/Ca, AI3-M/Ma).
- [ ] Q3 Competence — able to execute `AI2_G2_REVIEWER_CHECKLIST.md` §8 R-rows
      and §9 E1–E6 (Roles 6/14 responsibilities per `04:72`: evidence and QA
      validation): reading raw command evidence, exit codes, running a Python
      test battery, verifying SHA-256 manifests, reading gate definitions in
      `backend/app/core/config.py`.
- [ ] Q4 Class — owner assigns Class 1 (independent human validator) or
      Class 2 (owner acting with designated role-holders) per the nomination
      record; the class is recorded in nomination §3 before acknowledgement.
- [ ] Q5 Willingness — the person has actually agreed in writing (recorded at
      acknowledgement; willingness is NEVER inferred from public profiles or
      third-party statements).

No candidate is evaluated, contacted, or named by the implementing side
(CONSOL-GOV-12 owner decision D-2: channel scan only; no outreach without a
separate owner authorization naming a contact mechanism).

## §2 Conflict-of-interest declaration form (R-A2; field set ratified GOV-6 resolution #2)

To be completed BY THE APPOINTED REVIEWER at acknowledgement. Field set is the
nomination-record §3 set (canonically ratified; nothing added or removed):

```text
COI DECLARATION — G2 independent review
Reviewer name / role identity:      ______________________________________
1. Financial interests relevant to  ______________________________________
   RADAR_BOURSE or its domain:      (none / describe)
2. Employment / contractual         ______________________________________
   relationships with the project,  (none / describe)
   its owner, or its data providers:
3. Prior involvement in any work    ______________________________________
   under review (P0-AMD-1/1a,       (none / describe)
   AI1-GC/GCa, AI2-F/Fa, AI-MA-C/Ca,
   AI3-M/Ma) — authorship, review,
   remediation, or otherwise:
4. Personal relationships with any  ______________________________________
   implementing-side participant:   (none / describe)
5. Any interest that could reasonably ______________________________________
   be seen to bias the review:      (none / describe)
Declaration date (UTC):             ______________________________________
Reviewer signature / attestation:   ______________________________________
```

Adjudication is an OWNER act (D-O3: accept / mitigate / disqualify) on the
declared content — never the reviewer's own and never the implementing side's.

## §3 Reviewer acceptance form (R-A1 — written acknowledgement; completes E5)

```text
ACKNOWLEDGEMENT OF G2 REVIEW ASSIGNMENT
I, ______________________________________ (reviewer identity as recorded in
nomination §3), acknowledge the assignment by the owner to perform the
independent G2 review of the five pre-G2 block groups at the reviewed SHA that
will be fixed at review start, under procedure version ____________________
(approved v1.0 text; identity confirmed by SHA-256
0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed9b88a9b2cc65dafc at the v0.2
draft; the approved v1.0 hash is recorded in the owner's D-O1 decision).
I confirm: (a) I have read the review scope (§4) and the known limitations of
the evidence (checklist §5–§6); (b) I will execute the review per §6 and report
per §8; (c) I declare the COI form (§2) concurrently; (d) my acknowledgement is
given in writing and dated.
Acknowledgement date (UTC):         ______________________________________
Reviewer signature / attestation:   ______________________________________
```

E5 is `VERIFIED` only after this completed form exists and the owner has
recorded it; until then E5 remains `NOT_VERIFIED` and the reviewer remains
`NOT_APPOINTED — BLOCKED`.

## §4 Review scope (from procedure v0.2 T1 — restated, no change)

- IN scope: the five delivered pre-G2 block groups — P0-AMD-1/P0-AMD-1a,
  AI1-GC/AI1-GCa, AI2-F/AI2-Fa, AI-MA-C/AI-MA-Ca, AI3-M/AI3-Ma — at their
  contract class (`02:202`), their audit chains, and the evidence packages
  binding them (`G2_REVIEW_PACKAGE_2026-10-20.md` §1–§9 currency chain).
- OUT of scope: runtime capability (D-AI-41) until a separately authorized
  runtime review; live-data AI-2 execution (blocked by G2, D-AI-26);
  production mutation of any kind.

## §5 Required evidence (from procedure v0.2 T2 — restated, no change)

- Raw command captures with exit codes and UTC timestamps in append-only
  evidence directories (`docs/governance/evidence/raw/<date>_<label>/`),
  SHA-256-manifest-protected (manifest + `.exit` excluded from their own
  manifest; `.exit` cross-validated against hashed `.txt`).
- The 18-component core verification battery executed pre-commit AND at-commit
  at the reviewed SHA, plus the documented 19th evidence component `pip_state`
  (battery definition currency per the GOV-8 addendum).
- Weighting: current-run evidence at the reviewed SHA governs; historical
  evidence is lineage only; inherited claims must be labeled as such.

## §6 Reproducible review runbook (reviewer-executed; exact commands)

Preconditions (all must hold before starting):
- P1 D-O1 approval of the procedure recorded (version + hash).
- P2 D-O2 appointment complete (eight §3 fields); R-A1/R-A2 forms (§2–§3) done;
  D-O3 COI disposition recorded; D-O4 review window scheduled.
- P3 Visibility of the reviewed material: the five block groups and the full
  governance chain live in 40 local-only commits (`6ff6b07…3e35f49`) that are
  NOT on the canonical remote (`origin/main = c1984e7`, fresh `ls-remote`
  2026-10-22). The reviewer obtains the material by (a) owner push after D-O8
  authorization, or (b) an owner-provided workspace/clone on the reviewer's
  machine. The implementing side does NOT publish anything itself.

Steps (record every command with exit code and UTC):
1. **Fix the reviewed SHA** (E1): record `git rev-parse HEAD` and
   `git status --porcelain` (tracked-clean expected; the four untracked
   bootstrap paths are expected and enumerated). Any later tree change ⇒
   re-fix or explicitly scoped delta review (v0.2 T1).
2. **Verify corpus integrity** (E2/E6): run the corpus verifier against the
   seven amendment-source digests (7/7 byte-identical expected — last fresh
   result 2026-10-22, GOV-13 scratch `08`/battery evidence); confirm the
   evidence-package paths of checklist §3–§6 resolve on disk.
3. **Reproduce the battery** (E3): execute the 19-component battery exactly as
   recorded (`scripts/gov9_battery.sh` pattern; GOV-13 fresh reproduction at
   `3e35f49`: 621 passed / 2 pre-existing warnings / 77.84s; focused blocks
   44/58/24/25/13/51/58; all 19 exit 0 — evidence dir
   `docs/governance/evidence/raw/2026-10-22_consolgov13_fullbattery/`).
   Compare component-for-component with the recorded counts; ANY discrepancy
   is a finding.
4. **Verify gate invariants in code** (E4): read `backend/app/core/config.py:109`
   (ai2_enabled default "0"), `:264-272` (verified=False hard-coded, comment
   "no caller can mint live_verified=True"), `backend/app/services/
   ai2_service.py:13`; confirm no AI-2 HTTP route is registered; run the
   focused AI2-F contract tests (24 passed expected).
5. **Read known limitations** (E5): checklist §5–§6; acknowledge via §3 form
   (done at acknowledgement).
6. **Audit the evidence chain** (E2): verify SHA-256 manifests of the evidence
   directories you rely on; `.exit` files cross-validated.
7. **Classify findings** (§7 rules) and **complete the report** (§8 template).
8. **Sign off** (§8/T6 form) and hand the review record to the owner; the G2
   verdict itself is recorded by the owner ONLY (v0.2 T6; D-AI-26).

## §7 Findings classification and verdict rule (procedure v0.2 T5 — restated)

- Classification: CRITICAL / HIGH / MEDIUM / LOW / INFO.
- Verdict rule (codified GOV-6 #6): any open CRITICAL/HIGH ⇒ FAIL; an open
  MEDIUM ⇒ FAIL, or FAIL-narrow only where the defect is localized AND
  dispositioned; LOW/INFO recorded and dispositioned without blocking.
- Re-review thresholds (GOV-6 #3): docs-only ⇒ delta review; module-code ⇒
  focused re-verification + delta review; gate/evidence-lineage touch ⇒ full
  re-review. Precedents: AI1-GCa `2f86c4a`, G2PREPa `d380ee5`, ACCPKGa
  `a3165c4`, AI2-Fa `17ef611`, AI-4a `cc98c64`, AI-6a `1d9030c`.

## §8 Review report template (procedure v0.2 T5 outputs + T6 sign-off form)

```text
G2 INDEPENDENT REVIEW RECORD
Reviewed full SHA:              ______________________________________
Procedure identity + version:   ______________________________________
Reviewer identity + ack date:   ______________________________________
E1 outcome: __________________  E2 outcome: __________________
E3 outcome: __________________  E4 outcome: __________________
E5 outcome: __________________  E6 outcome: __________________
Findings census (C/H/M/L/INFO): ______________________________________
Per-finding classification, evidence locus, disposition: (appendix)
Verdict recommendation (PASS / FAIL / FAIL-narrow + rationale):
                                ______________________________________
--- SIGN-OFF (procedure v0.2 T6 / GOV-6 #4 / checklist §11) ---
Reviewer attestation + date:    ______________________________________
--- OWNER DECISION BLOCK (owner only) ---
G2 verdict: __________________  Date (UTC): ____________________
Granting authority: __________  Evidence locus: ________________
```

## §9 Reviewer decision record (hand-off record; owner files it)

The completed §8 record + the §2/§3 forms + the reviewer's raw command captures
are filed by the owner under `docs/governance/evidence/` (append-only) and
cross-referenced in `docs/STATUS.md` and the execution-state file (procedure
v0.2 T6 audit-trail clause).

## §10 Dependencies and exact missing real-world inputs (honest blocker list)

| Dependency | Owning act | Status 2026-10-22 |
|---|---|---|
| Procedure approval (D-O1) | owner | OPEN — v0.2 DRAFT, approval block EMPTY |
| Reviewer appointment (D-O2, 8 fields) | owner | OPEN — NOT_APPOINTED — BLOCKED |
| Written acknowledgement (R-A1 → E5) | reviewer | OPEN — no reviewer exists |
| COI declaration (R-A2) + disposition (D-O3) | reviewer → owner | OPEN |
| Scheduling (D-O4) | owner | OPEN |
| Material visibility for the reviewer | owner (D-O8 push OR owner-provided workspace) | OPEN — 40-commit chain local-only; NO push by implementing side |
| Package/tooling ratification | owner | THIS PACKAGE = DRAFT; forms operative only after the acts above |

Nothing in this package substitutes for any owner or reviewer act. If the
authorized review cannot be obtained in the current environment, the procedure
stays DRAFT / NOT APPROVED, R2 stays OPEN, E5 stays NOT_VERIFIED, G2 stays
NOT_PASSED, and real-data AI-2 stays blocked.
