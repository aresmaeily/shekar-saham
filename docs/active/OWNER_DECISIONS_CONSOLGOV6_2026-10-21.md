# OWNER DECISIONS AND EXECUTION RECORD — CONSOL-GOV-6 — 2026-10-21

Status: **GOVERNED EXECUTION RECORD** — prepared and executed under the
CONSOL-GOV-6 owner directive ("Execute Owner-Authorized Decisions, Close
B-1, Remediate pip-audit, and Verify All Outcomes"). This record applies the
directive's BINDING dispositions, records every outcome with its exact
canonical source and evidence, and changes NOTHING the directive does not
authorize. Safeguards that remain binding: `G2=NOT_PASSED`;
`AI2_ENABLED=0` (`backend/app/core/config.py:109`); `live_verified=false`
(`config.py:270` hard-coded); `R2=OPEN` (procedure draft remains NOT
APPROVED); `E5=NOT_VERIFIED`; reviewer NOT_APPOINTED; no real-data AI-2
execution; no production mutation; no push. Self-approval is void. Absence
of response is not approval.

## 0. Directive provenance (verbatim capture)

- **Directive:** CONSOL-GOV-6 — "Execute Owner-Authorized Decisions, Close
  B-1, Remediate pip-audit, and Verify All Outcomes" — received 2026-10-21
  in the governed session (channel `zai-web`, session
  `web-f58053f5-02e8-43fc-b28a-601c9cd1bada`, trace `1a15daf17e9d1fc5`).
- **Authority:** Project Owner (Role 1 A per
  `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md:72`). The directive
  explicitly authorizes: per-block B-1 final disposition under a binding
  rule; resolution of the seven `[OWNER TO CONFIRM]` drafting entries in the
  R2 procedure draft; execution of the reviewer nomination workflow
  (short of fabricating an appointment); preparation of the AI2-F condition-
  (a) comparison (no closure, no remediation); preparation of seven AI3-M
  D1–D7 decision records; and controlled remediation of the `certifi`
  advisory in the project-controlled tooling environment.
- **Binding B-1 rule (recorded verbatim from the directive; this rule
  governs every §1 disposition):**
  > "ACCEPT only if every mandatory acceptance criterion is explicitly
  > satisfied by traceable, reproducible evidence. REJECT if any mandatory
  > criterion is unmet, contradictory, or not verifiable. State exactly what
  > is rejected and cite the supporting artifact. Do not use DEFER merely to
  > avoid making a decision. If the acceptance criteria themselves are
  > missing, ambiguous, or contradictory, record REJECT — acceptance
  > criteria not established, identify the exact defect, and do not invent
  > replacement criteria."
- **Directive limits honored:** "B-1 block decisions do not constitute G2
  passage, real-data AI-2 authorization, or production acceptance." No
  option is selected for AI2-F condition (a); no D1–D7 option is selected;
  the procedure draft is NOT marked approved; no reviewer is appointed or
  fabricated; no push; no global Python installation mutated.

Verification basis (all fresh 2026-10-21 at HEAD
`d59ce3eb5421ef95f5ff5022631e01efcb9526c7` unless stated; raw captures in
the auditor scratch `consolgov6_audit_scratch/` outside the repo):
baseline `01_baseline_git_state.txt` + `02_baseline_git_env.txt`; CONSOL-GOV-5
commit audit `03_consolgov5_commit_audit.txt`; gates `04_gates_fresh_capture.txt`;
canonical inventory `05_canonical_inventory.txt`; AI2-F residuals
`06_ai2f_residuals_fresh.txt`; AI-MA-C residuals `07_aimac_residuals_fresh.txt`;
P0-AMD-1 evidence `08_p0amd1_evidence.txt`; AI1-GC evidence
`09_ai1gc_evidence.txt`; AI3-M evidence `10_ai3m_evidence.txt`; corpus
integrity `11_corpus_integrity.txt`; prior manifests `12_prior_manifests_recheck.txt`;
pip-audit remediation `pip_remediation/01_before_state.txt` +
`02_pip_audit_pre_exit.txt` + `03_after_state.txt`; battery
`docs/governance/evidence/raw/2026-10-21_consolgov6_battery/` (pre-change,
at `d59ce3e`) and `2026-10-21_consolgov6_atcommit/` (post-change).

## 1. B-1 — per-block final disposition (owner-authorized, binding rule applied)

Method: for each block, the canonical acceptance criteria (the
`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §1 per-block criteria + the
recorded acceptance conditions in `B1_OWNER_DECISION_MATRIX_2026-10-20.md`
"Exact acceptance conditions" row) were inspected independently, then the
binding rule was applied to fresh evidence captured at HEAD `d59ce3e`. Each
block lists what IS satisfied and exactly what is rejected. No block's
outcome is inferred from another's. Per the directive: these dispositions do
NOT constitute G2 passage, real-data AI-2 authorization, or production
acceptance, and do NOT authorize runtime integration, `AI2_ENABLED=1`, live
data/LLM, push, or AI-3 persistence integration.

### 1.1 P0-AMD-1 — REJECT (one acceptance condition not verifiable)

- **Decision: REJECT.** Exact item rejected: acceptance condition 2 —
  "numeric ceilings ratified/amended by the owner at runtime-integration
  time (authority: owner; evidence: owner ratification record)". **No owner
  ratification record exists.** Fresh search across both canonical owner
  decision records finds zero ratification of the deployment constants
  (retry 10 / timeout 3600s / concurrency 8 / 60 runs/h; rate caps
  10,000/min — engineering-authority values per
  `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md:57-58`); the only "ratif" hits in
  the decision records are the AI3-M D6 row *citing* the P0 numeric-ceiling
  ratification as an OPEN same-class owner decision
  (`OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md:276`). A criterion whose
  mandated evidence (an owner ratification record) does not exist is not
  verifiable under the binding rule.
- **What is NOT rejected (satisfied, traceable):** corpus import byte-identity
  7/7 (fresh `11_corpus_integrity.txt`); contract semantics match `02:131-139`
  (44 focused tests exit 0 in the fresh battery); no wiring (no import
  surface — gates capture `04_gates_fresh_capture.txt`); residual honesty
  notes recorded; acceptance condition 1 ("residual notes scheduled into the
  next contract hardening pass") IS satisfied — traceable to register review
  D-2, class 3 (`OWNER_DECISION_REGISTER_REVIEW_2026-10-19.md:58`).
- **Supporting artifacts:** `B1_OWNER_DECISION_MATRIX_2026-10-20.md` (condition
  row); `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md:57-58`;
  `consolgov6_audit_scratch/08_p0amd1_evidence.txt`; battery focused run
  `pytest_p0amd1.txt` (44 passed).
- **Remediation path (smallest):** the owner ratifies or amends the numeric
  ceilings by recorded decision (the condition's own terms evaluate it at
  runtime-integration time; an early ratification is lawful and closes the
  condition). After disposal, the disposition may be re-applied under the
  then-governing rule. The delivered contract layer is not defective and
  remains in tree; no rework of delivered code is implied by this REJECT.
- **Consequence mapping (package §3 REJECT row):** ledger status → REJECTED
  (recorded in §1.6); G2-review acceptance input for this block = rejection
  recorded with the exact open condition; all gates unchanged.

### 1.2 AI1-GC — REJECT (condition evidence does not exist)

- **Decision: REJECT.** Exact item rejected: acceptance condition —
  "runtime integration must CALL the gates (binding requirement carried into
  AI-4/AI-5 contracts — engineering; evidence: future runtime block tests)".
  Two components are not verifiable today: **(i)** the AI-5 carrying cannot
  be verified because no AI-5 contract extension has been delivered (AI-5 is
  DEFERRED UNTIL CORE STABILITY per D-AI-30; no AI-5 block exists in the
  tree); **(ii)** the condition's own evidence — "future runtime block
  tests" — does not exist: there is no runtime caller of the AI1-GC gates
  (fresh search: zero non-domain, non-test importers of
  `run_governance`/`monitoring_governance`/`memory_interfaces`;
  `consolgov6_audit_scratch/09_ai1gc_evidence.txt`, `runtime_caller_hits: 0`
  — enforcement-by-invocation, exactly as recorded in the B-1 matrix).
- **What is NOT rejected (satisfied, traceable):** four capability contracts
  implement the `02:39-42` nouns (58 focused tests exit 0, fresh battery);
  gap-matrix honesty (`AI1_GAP_CLOSURE_SCOPE_AND_TRACEABILITY.md`); gates
  unchanged; independent audit FAIL-narrow → docs-only remediation `2f86c4a`
  → PASS (history preserved); the AI-4 half of the carry-forward IS
  traceable: the AI-4 contract layer's gates call AI1-GC primitives
  (`governed_generation.py` imports `run_governance`;
  `sandbox_admission_gate`/`governed_candidate_acceptance` call
  `missing_required_provenance` and `assert_autonomy_permitted` — scope
  derivation rows R8/R11, `AI4_SCOPE_DERIVATION.md`).
- **Supporting artifacts:** `B1_OWNER_DECISION_MATRIX_2026-10-20.md` (condition
  row); `AI4_AI7_P343_DEPENDENCY_MATRIX.md` §AI-5 (D-AI-30 deferral);
  `consolgov6_audit_scratch/09_ai1gc_evidence.txt`; battery
  `pytest_ai1gc.txt` (58 passed).
- **Remediation path (smallest):** deliver the AI-5 contract extension
  carrying the gate-calling requirement (lawful pre-G2 contract class), and
  the runtime block that calls the gates post-G2; then re-apply the
  disposition. Code stays in tree.
- **Consequence mapping:** ledger status → REJECTED (§1.6); G2-review input
  recorded; gates unchanged.

### 1.3 AI2-F — REJECT (condition (a) unmet; residuals present)

- **Decision: REJECT.** Exact item rejected: acceptance condition (a) — "the
  residual observations (status-consultation gap, record-level approver
  binding, unknown-trust-string folding) are dispositioned in the next AI-2
  contract touch". Fresh evidence at `d59ce3e`: all three residuals remain
  PRESENT with zero drift (`consolgov6_audit_scratch/06_ai2f_residuals_fresh.txt`):
  (1) `record.status` hits in `governed_acceptance`
  (`ai2_governance.py:393-423`) = **0**; (2) approver hits in `AI2RunRecord`
  (`:277-297`) = **0** (approver enforced only on the RunContext,
  `run_governance.py:109`); (3) `_TRUST_RANK` unknown→−1 (`:234`, `:259`)
  vs `config.py:191-196` folding to `synthetic`. And **no AI-2 contract
  touch has occurred** since remediation `17ef611` (fresh
  `git log -- backend/app/domain/ai2_governance.py`: only `6aeeaa2`,
  `17ef611`) — so the "next AI-2 contract touch" in which the residuals
  were to be dispositioned has not happened. The disposal additionally
  requires explicit owner authorization identifying the (iii) sub-choice;
  CONSOL-GOV-6 authorizes PREPARATION ONLY and selects no option (§4
  below), so the condition cannot be disposed in this cycle.
- **What is NOT rejected (satisfied, traceable):** all eight `02:44-53`
  required items enforced (24 focused tests exit 0, fresh battery); trust
  ranking canonical (audit remediation `17ef611`); service untouched, gates
  unchanged; condition (b) ("nothing implies AI-2 runtime readiness") is
  disposed by construction and remains standing — `AI2_ENABLED=0`
  (`config.py:109`), `verified=False` (`config.py:270`), no route (import
  grep exit 1), all fresh.
- **Supporting artifacts:** `AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md`;
  `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §1;
  `consolgov6_audit_scratch/06_ai2f_residuals_fresh.txt`; battery
  `pytest_ai2f.txt` (24 passed); gates capture `04_gates_fresh_capture.txt`.
- **Remediation path (smallest):** owner authorization selecting AUTHORIZED
  + the (iii) sub-choice (config-folding adoption vs stricter −1 canonical)
  → one-commit disposal per the intake scope (`ai2_governance.py` + its
  test file) → focused tests + independent re-audit + fresh at-commit
  battery → re-apply the disposition. Until then no code in
  `ai2_governance.py` is touched.
- **Consequence mapping:** ledger status → REJECTED (§1.6); condition (b)
  standing unchanged; G2-review input recorded; gates unchanged.

### 1.4 AI-MA-C — REJECT (fold-in condition outstanding)

- **Decision: REJECT.** Exact item rejected: acceptance condition —
  "DEGRADED-exchange docstring line + dead-code removal folded into the
  next AI-MA touch (class 2/3)". Fresh evidence at `d59ce3e`: **no AI-MA
  touch has occurred** since dispositions commit `aa86c3c` (fresh
  `git log -- backend/app/domain/multi_agent.py`: only `e385415`,
  `aa86c3c`); the owed fold-in therefore never happened: (i) AIMAC-03 dead
  code still present — `MAX_HIERARCHY_DEPTH = 2` (`multi_agent.py:56`) and
  the dead conditional's `_shape` validator (`:101`); (ii) the AIMAC-06
  partial-failure-model disclosure line (DEGRADED-exchange / free-string
  failure codes / `failure_behavior` non-consultation) is still absent from
  the module docstring (fresh `grep -n DEGRADED multi_agent.py`: only the
  status Literal `:327` and `TraceEvent` kind `:368` — no disclosure
  sentence). `consolgov6_audit_scratch/07_aimac_residuals_fresh.txt`.
- **What is NOT rejected (satisfied, traceable):** AI-MA-1..6 contracts
  present and enforced (25 focused tests exit 0, fresh battery); prohibition
  set `02:81` structurally enforced (audit §verification: no count cap,
  peer addressing structurally refused, no spawn/scheduler/thread
  mechanics); runtime NOT instantiated (no runtime exists — D-AI-41
  respected); independent audit PASS with dispositions in `aa86c3c`.
- **Supporting artifacts:**
  `docs/governance/evidence/2026-10-18_AIMAC_independent_audit.md`
  (AIMAC-03, AIMAC-06 — preserved verbatim);
  `consolgov6_audit_scratch/07_aimac_residuals_fresh.txt`; battery
  `pytest_aimac.txt` (25 passed).
- **Remediation path (smallest):** execute the fold-in at the next AI-MA
  contract touch (docstring disclosure line + dead-code removal; class 2/3
  engineering per the register review) → delta re-audit → re-apply the
  disposition. Code otherwise stays in tree.
- **Consequence mapping:** ledger status → REJECTED (§1.6); G2-review input
  recorded; gates unchanged.

### 1.5 AI3-M — REJECT (owner persistence decision record absent)

- **Decision: REJECT.** Exact item rejected: acceptance condition — "owner
  persistence decision record (select approach or defer with date) +
  ratifying D3 immutability class + ratifying/amending D4/D6
  (`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §2 'Evidence needed to
  dispose')". **No owner persistence decision record exists.** Fresh search
  of both canonical owner-decision records: "persistence" appears only as
  routed-to-owner / unauthorized; D1–D7 are recorded OPEN in
  `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §6,
  `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §2, and the CONSOL-GOV-5 matrix
  §5 (`consolgov6_audit_scratch/10_ai3m_evidence.txt`). The mandated
  evidence (the owner decision record) does not exist → not verifiable.
- **What is NOT rejected (satisfied, traceable):** episodic immutability
  structural (`research_memory.py:119-158`, append/get/index only;
  A3/A11 test-pinned); semantic curation/versioning/retirement (A4,
  `:247-318`); PIT honesty (conservative `lessons_active_at` semantics,
  AI3M-02 INFO disclosed); 13 focused tests exit 0 (fresh battery); blocker
  isolation delivered (`AI3_PERSISTENCE_DECISION_BRIEF.md` +
  `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` §7); independent audit PASS
  (AI3M-01 fixed `37c529d`; AI3M-02/03 INFO disclosed).
- **Supporting artifacts:** `OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §2
  (AI3-M evidence-to-close); `AI3_PERSISTENCE_DECISION_BRIEF.md` §D;
  `consolgov6_audit_scratch/10_ai3m_evidence.txt`; battery
  `pytest_ai3m.txt` (13 passed).
- **Remediation path (smallest):** the owner answers D1–D7 (D1/D3/D4/D5/D6/D7
  decidable now; D2 upstream-blocked at P3.43 — §5.2 below) or records an
  explicit deferral with a date → the §5 decision records then carry the
  selected options. Persistence-adapter implementation lands post-G2
  regardless (D-AI-28 discipline). Code stays in tree.
- **Consequence mapping:** ledger status → REJECTED (§1.6); G2-review input
  recorded; gates unchanged; AI-3 persistence integration remains
  PROHIBITED.

### 1.6 B-1 ledger effect and boundary restatement

| Block | Prior status | Disposition (2026-10-21, binding rule) | Exact open acceptance item | Remediation authority |
|---|---|---|---|---|
| P0-AMD-1 | VERIFIED_PENDING_ACCEPTANCE | **REJECTED** | Owner ratification of numeric ceilings (evidence: owner ratification record — absent) | Owner |
| AI1-GC | VERIFIED_PENDING_ACCEPTANCE | **REJECTED** | Gate-calling evidence (future runtime block tests — absent); AI-5 carrying undeliverable until AI-5 exists | Engineering (AI-5 extension) + owner (runtime) |
| AI2-F | VERIFIED_PENDING_ACCEPTANCE | **REJECTED** | Condition (a): three residuals undispositioned; no AI-2 contract touch since `17ef611` | Owner (authorization + (iii) sub-choice), then engineering |
| AI-MA-C | VERIFIED_PENDING_ACCEPTANCE | **REJECTED** | Fold-in (docstring line + dead-code removal) not executed; no AI-MA touch since `aa86c3c` | Engineering (next AI-MA touch) |
| AI3-M | VERIFIED_PENDING_ACCEPTANCE | **REJECTED** | Owner persistence decision record (D1–D7) absent | Owner |

Restated verbatim from the directive: "B-1 block decisions do not
constitute G2 passage, real-data AI-2 authorization, or production
acceptance." REJECT consequences follow package §3: the rejected scope's
G2-review acceptance input is the recorded rejection; remediation paths are
as listed; **the code remains in the tree** (no destructive action, no
removal, no rewrite); all gates unchanged (`G2=NOT_PASSED`,
`AI2_ENABLED=0`, `live_verified=false`). A REJECT here records that the
block's OWN exit criteria are not fully satisfied today — four of the five
rejects turn on evidence/decisions that do not yet exist (owner
ratification, runtime tests, condition-(a) authorization, D1–D7 answers),
not on defects in the delivered contract layers, whose criteria ARE
satisfied and verified fresh as listed per block.

## 2. R2 — seven `[OWNER TO CONFIRM]` entries resolved from canonical records; draft stays NOT APPROVED

The CONSOL-GOV-5 owner-review checklist
(`OWNER_ACTION_PACKAGE_CONSOLGOV5_2026-10-21.md` §2.2) listed seven open
content items in `G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md`. Per the
directive, each was resolved ONLY where the required value can be
established from existing canonical records or the approved governance
framework; every resolution names its exact source. **The draft's status
remains DRAFT / NOT APPROVED; its approval block remains EMPTY; R2 remains
OPEN; E5 remains `NOT_VERIFIED`; G2 remains `NOT_PASSED`.** The resolutions
are recorded as a dated addendum to the draft file (append-only) and
summarized here.

| # | Open item (draft locus) | Resolution | Exact source establishing the value |
|---|---|---|---|
| 1 | Exception record form (T3) | ADOPTED as proposed, now corpus-grounded: each owner-granted exception is recorded in the review output with scope, rationale, expiry, granting authority, and evidence locus. Grounded in the repository's established disposition-recording precedent (classified findings + explicit dispositions with rationale in the independent audit records). | `docs/governance/evidence/2026-10-18_AI4_independent_audit.md` (AI4-06..08 ACCEPTED with rationale); `docs/governance/evidence/2026-10-19_AI6_independent_audit.md` (AI6-10..12 ACCEPTED dispositions); draft T3 proposal |
| 2 | COI disclosure form (T4) | ADOPTED: the reviewer discloses at acknowledgement using the field set already published in the GOV-5 nomination form (independence YES/NO; not author/remediator of reviewed work; stake in early/late G2 outcome; other interests); owner adjudicates disclosed COIs (appointment authority Role 1 A). | `G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` §2–§3; `OWNER_ACTION_PACKAGE_CONSOLGOV5_2026-10-21.md` §2.3 form §3; `04:72` |
| 3 | Re-review threshold examples (T5) | ADOPTED as proposed, with concrete examples drawn from the repository's own remediation history: docs-only remediation → delta re-audit (AI1-GCa `2f86c4a`, G2PREPa `d380ee5`, ACCPKGa `a3165c4`); remediation touching reviewed module code → focused re-verification + delta audit (AI2-Fa `17ef611`, AI-4a `cc98c64`, AI-6a `1d9030c`); any change to gate surfaces or evidence lineage → full re-review with new SHA fixing. | The six audit-remediation pairs in `docs/governance/evidence/2026-10-18_*` and `2026-10-19_AI6_*`, `2026-10-20_G2PREP_*`; draft T5 rule |
| 4 | Sign-off block exact form (T6) | ADOPTED: reviewed full SHA; procedure identity + version; reviewer name/role + acknowledgement date; E1–E6 outcome summary; findings census by classification; verdict recommendation; owner decision block (verdict + date + authority). | `AI2_G2_REVIEWER_CHECKLIST.md` §11 (sign-off scaffolding) + draft T6 proposed contents; GOV-6 directive §1 R2 topic 7 |
| 5 | Entry-prerequisites equivalence (T1) | TIGHTENED (corpus-grounded): entry prerequisites are E1–E6 per `AI2_G2_REVIEWER_CHECKLIST.md` §9 exactly; any substitution requires a recorded owner decision naming the substituted criterion, its replacement, and its source (decision-provenance discipline D-AI-40, `05:197-200`). The vague "or owner-approved equivalents" is superseded by this rule. | `AI2_G2_REVIEWER_CHECKLIST.md` §9; D-AI-40 `05:197-200`; `05:148-150` (owner approval reserved) |
| 6 | Verdict-rule precedent (T5) | CODIFIED as rule, grounded in six applied precedents: any open CRITICAL/HIGH → FAIL; open MEDIUM → FAIL (FAIL-narrow only where the defect is localized AND dispositioned); LOW/INFO recorded and dispositioned without blocking. | Applied precedents: `2026-10-18_P0AMD1_independent_audit.md`, `2026-10-18_AI1GC_independent_audit.md`, `2026-10-18_AI2F_independent_audit.md`, `2026-10-18_AI4_independent_audit.md`, `2026-10-18_ACCPKG_independent_audit.md`, `2026-10-19_AI6_independent_audit.md` (all FAIL-narrow with localized, dispositioned defects) |
| 7 | Acceptance criteria for the approval act itself (Option C terms) | ALREADY FIXED by the owner's own Option C selection (no drafting needed): formal approval = a recorded owner decision naming (i) the approving authority and (ii) the effective version. The approval block stays EMPTY until that decision exists; nothing else is required for approval. | `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §1.2 (verbatim Option C selection, trace `1a15b105a0662765`); `G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md` Option C terms |

### 2.1 Directive-required topic coverage of the final proposal (re-verified)

| Directive-required topic (verbatim intent) | Draft coverage (post-resolution) |
|---|---|
| 1. Required evidence and integrity checks | T2 (qualifying artifacts, append-only evidence dirs, SHA-256 manifests with declared self/`.exit` exclusion, 18-component battery pre-commit AND at-commit, current-run weighting) |
| 2. Reviewer independence and conflicts of interest | T4 + resolution #2 (COI form fields; adjudication by owner) |
| 3. Appointment authority, reviewer identity, role, acknowledgement | T4 + nomination record + GOV-5 form (appointment = owner-only; written acknowledgement completes E5) |
| 4. Mandatory review outputs | T5 + resolution #4 (dated review record, E1–E6 outcomes, classified findings, verdict recommendation, sign-off block) |
| 5. Explicit acceptance/rejection criteria and gate outcomes | T3 (objective criteria i–v + exceptions) + T6 (verdict authority) + resolution #6 (verdict rule codified) |
| 6. Separation between implementer self-audit and independent review | T4 independence clause (implementing side's audit chain is EVIDENCE, never a substitute) + nomination record §2 disqualification analysis |
| 7. Owner approval authority, document version, immutable decision provenance | T6 (versioning v1.0 at approval; owner-recorded change control; audit trail) + resolution #7 (Option C approval criteria) |

**Status after resolution: the proposal is content-complete; NOTHING is
marked approved.** The seven resolutions are drafting completions under
implementer authority expressly granted by the directive; the approval act
itself remains owner-only (Option C terms, resolution #7). No owner intent,
approval authority, or approval signature is invented anywhere.

## 3. Independent reviewer — nomination workflow executed (no appointment fabricated)

Directive authorization: complete the reviewer nomination workflow; inspect
actual project records for eligible candidates; never fabricate identity,
role, independence, or acknowledgement; the implementer must not appoint
itself; never fabricate an appointment to make E5 pass.

- **Fresh candidate inspection (2026-10-21, at `d59ce3e`):** re-searched the
  governance records for any named eligible candidate — personnel registry,
  role-holder roster, named-validator record: **none exists** (same result
  as the two prior cycles; fresh capture
  `consolgov6_audit_scratch/` candidate search — zero named individuals in
  `docs/active/` governance records). The only real-world actor evidenced
  anywhere in the records is the Project Owner (directive channel `zai-web`;
  prior recorded decisions carry traces `1a15ad8d626cf469`,
  `1a15b105a0662765`, `1a15daf17e9d1fc5`).
- **Conclusion of the inspection:** no eligible real person with a written
  acknowledgement is available in any project record. Per the directive's
  own branch rule ("Otherwise, produce a complete, actionable nomination
  record identifying precisely what real-world input is missing"), the
  workflow output is the actionable nomination record — NOT an appointment.
- **What already exists (complete and current):** the candidate-class
  analysis, independence/COI rules, competence profile, the two-class
  eligibility model, the disqualification analysis (implementing-agent chain
  and audit sub-agent chain), and the ready-to-use blank form —
  `G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` (§1–§4) +
  `OWNER_ACTION_PACKAGE_CONSOLGOV5_2026-10-21.md` §2.3. A dated GOV-6
  addendum has been appended to the nomination record.
- **Precisely what real-world input is missing (exhaustive):**
  1. An **owner designation record** naming the reviewer — either Class 1
     (a named independent human validator: name, role, organizational
     affiliation, competence verification) or Class 2 (the owner acting
     directly with consulted roles 9/10/15, electing itself as reviewer with
     a named sign-off identity). No record can substitute for this act.
  2. The designated reviewer's **written acknowledgement** with UTC date and
     artifact locus (this is what completes E5).
  3. The reviewer's **COI declaration** on the adopted form (§2 resolution
     #2 above), adjudicated by the owner.
- **Smallest next action:** one owner message designating the reviewer (or
  electing Class 2) with the §3 form fields completed; the acknowledgement
  then completes E5 mechanically. Nothing else blocks E5.
- **Status UNCHANGED: NOT_APPOINTED — BLOCKED on owner designation;**
  `R2=OPEN`; `E5=NOT_VERIFIED`; `G2=NOT_PASSED`. The implementing agent did
  not and cannot fill any designation field.

## 4. AI2-F condition (a) — option comparison completed; condition OPEN; no remediation

The canonical condition text, the specified disposal scope (verbatim, with
its (i)/(ii)/(iii) elements and the (iii) sub-choice), dependencies, risks,
reversibility, tests, and gate impact are recorded in
`AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md` (terminology preserved
verbatim from the canonical intake; no invented labels). This cycle adds
what the directive asked for beyond the brief: the **for/against evidence
for each option**, grounded in fresh code facts at `d59ce3e`.

- **Fresh residual verification:** all three residuals PRESENT, zero drift
  (`consolgov6_audit_scratch/06_ai2f_residuals_fresh.txt`; §1.3 above).
  The three previously reported residual loci are confirmed at exactly the
  recorded lines.
- **Evidence FOR/AGAINST each (iii) sub-choice** (the only open sub-decision
  inside the specified scope):

| Sub-choice | Evidence FOR | Evidence AGAINST |
|---|---|---|
| (iii)-A: adopt the config folding (`config.py:191-196` — unknown → `"synthetic"`, rank 0) | Converges the contract layer with the operative legacy runtime mapping (single folding rule across layers); the config mapping is the value the runtime would actually apply today; eliminates the recorded divergence | Weakens contract strictness: an unknown/typo'd trust string ranks 0 (= synthetic) instead of −1 (below mock); the AI2-Fa audit deliberately established −1 as the canonical contract ranking (remediation `17ef611`) — adopting folding reverses that recorded engineering decision without a corpus basis |
| (iii)-B: keep the stricter −1 ranking as canonical, test-pin the divergence | Preserves the strictest fail-closed behavior; consistent with the audit-established ranking; the divergence becomes documented + test-pinned (honesty preserved) | Permanent divergence between contract layer and `config.py` mapping; two folding rules coexist (operational confusion risk for future runtime consumers); requires the divergence test to be maintained |

- **Evidence FOR/AGAINST the two decision outcomes:**

| Outcome | Evidence FOR | Evidence AGAINST |
|---|---|---|
| (A) AUTHORIZE the disposal at the specified scope (one commit: `ai2_governance.py` + its test file) | Closes all three residuals in one commit (register review D-1: class 3, "one-commit remediable"); `governed_acceptance` becomes strictly stricter (new blocking conditions — fail-closed direction preserved); fully revertible (`git revert`; single module + test file; no migration, no runtime surface); no runtime consumer exists yet (zero importers — §1.2 evidence), so blast radius is contained; follow-through is fully specified (focused tests + independent re-audit + fresh at-commit battery) | Contract-behavior change invalidates any test constructing APPROVED-without-approver or a non-COMPLETED record passing acceptance (test updates required — that IS the intended effect); a code change to the acceptance gate during the REJECT remediation window should be sequenced deliberately, not bundled silently |
| (B) DEFER (condition stays OPEN) | Zero code-change risk; no sequencing interaction with the B-1 REJECT remediation paths | The three residuals persist as known gaps in the acceptance gate (a FAILED-status record with clean identity would still pass; record-level APPROVED stays approver-free; divergence stays unpinned); condition (a) remains an open acceptance item blocking any future ACCEPT disposition for AI2-F |

- **Code and configuration scope (exact):** `backend/app/domain/ai2_governance.py`
  (+ `backend/tests/test_ai2_f_governance.py`). Nothing else — no service,
  API, route, config, or gate file (intake scope guard, verbatim).
- **Security/reliability implications:** both (iii) sub-choices are
  fail-closed; they differ only in defense-in-depth degree. (i) and (ii)
  ADD blocking conditions (reliability of the acceptance gate increases).
- **Downstream gate effects: none** — `AI2_ENABLED=0` (`config.py:109`) and
  `verified=False` (`config.py:270`) untouched; no import surface created;
  condition (b) standing regardless of (a).
- **Status: condition (a) OPEN.** No option selected (the directive
  explicitly authorizes preparation only); no code touched; no closure, no
  bypass. The owner decision request remains exactly as in brief §8
  (AUTHORIZED/DEFERRED + (iii) sub-choice + scope confirmation).

## 5. AI3-M — seven decision records D1–D7 (preparation only; no option selected)

Canonical definitions locus: `AI3_PERSISTENCE_DECISION_BRIEF.md` §D
(verified present and unchanged at `d59ce3e`). Per-item status/provenance:
`OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §6 +
`AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §2. Directive rule applied: no
option is invented or selected; nothing is implemented (persistence
integration remains PROHIBITED, D-AI-28); each record states the exact
disposition permitted under existing owner decisions. Option analysis
source: brief §B + `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` §7
(PREFERRED CANDIDATE label = engineering recommendation, NOT a decision).

### 5.1 D1 — Engine class (single-operator embedded vs server-class)

- **Canonical wording (brief §D verbatim):** "single-operator embedded store
  (Option 1 or 2) vs server-class deployment (Option 3) — driven by the
  deployment target decision below."
- **State:** OPEN (provenance: brief 2026-10-18 → AI2F_AI3M §2.2 → first
  owner decision → second owner decision; unchanged).
- **Options + provenance:** Opt 1 SQLite+blobs (incumbent engine, brief §B);
  Opt 2 JSONL+blobs (brief §B); Opt 3 PostgreSQL (brief §B). No other option
  exists in any record; network/replicated/cloud stores recorded as
  "explicitly non-viable today" (brief §B, unknowns presupposed).
- **Consequences:** architecture — adapter behind the delivered in-memory
  contracts either way (reuse rule `02:107-112`); persistence — engine
  class determines schema/index strategy; autonomy — none (memory ops
  epistemic only, A7); runtime — none until post-G2 adapter; permission —
  access-control class differs per option (Opt 3 strongest); security —
  immutability guarantee class differs (app/format/storage-level); ops —
  Windows-deploy burden low/low/high.
- **Evidence/dependencies/reversibility:** evaluation §7 comparison
  (B-labelled); contract layer test-pinned (13 tests, fresh battery);
  depends on D2 (upstream-blocked); decision reversible on paper until the
  adapter lands.
- **Required tests + authority:** adapter acceptance tests per evaluation
  §7 (post-G2 block); decision authority: OWNER.
- **Disposition permitted now:** record the decision or defer with a date.
  NOT executable by the implementer. Missing information: actual artifact
  volume (no runtime exists — unmeasurable pre-G2).

### 5.2 D2 — Deployment target (Windows host / Docker / Electron-bundled) — upstream-BLOCKED at P3.43

- **Canonical wording (brief §D verbatim):** "deployment target for the AI
  runtime (Windows host? Docker? Electron-bundled?) — currently BLOCKED
  upstream at P3.43 launch gates."
- **State:** OPEN + upstream-BLOCKED (unchanged).
- **P3.43 dependency — exact gates verified this cycle** (fresh reads):
  `AI4_AI7_P343_DEPENDENCY_MATRIX.md` §P3.43 — (1) owner-issued `INSTALL`
  (NOT issued — no `INSTALL` authorization exists in any owner record);
  (2) Windows-target validation (NOT_STARTED — state file §7);
  (3) browser E2E + Electron runtime verification (NOT_VERIFIED);
  (4) live provider verification (`live_verified=false` — fresh validator
  captures, fail-closed); (5) GitHub push authorization for the unpublished
  chain (state file §7: local main 34 ahead; B-2/R5). **D2 cannot be
  decided while its mandatory dependency is unsatisfied** — deciding it
  today would embed unverifiable deployment assumptions (brief §D verbatim).
- **Options + provenance:** Windows host / Docker / Electron-bundled /
  other (brief §D). No option is selectable now.
- **Consequences:** constrains D1 engine class and D6 blob placement;
  premature selection embeds unverifiable assumptions; no code, runtime, or
  permission effect while blocked.
- **Evidence/reversibility/tests/authority:** dependency matrix (above);
  nothing reversible-or-not (decision not taken); acceptance tests defined
  at adapter time; authority: OWNER.
- **Disposition permitted now:** NONE except recording the upstream blocker.
  **D2 is NOT declared complete** — its mandatory dependency (P3.43 launch
  gates) remains unsatisfied, exactly as the directive requires.

### 5.3 D3 — Immutability guarantee class + hash-audit cadence

- **Canonical wording (brief §D verbatim):** "immutability guarantee class
  required (application-enforced vs storage-enforced vs format-enforced)
  and whether hash-verification audits should be periodic."
- **State:** OPEN (unchanged).
- **Options + provenance:** app-enforced / storage-enforced /
  format-enforced (brief §B comparison rows); register review D-3 records
  the engineering recommendation "trigger-level (M3) as default; owner
  ratifies with D2/D4" (class 2). A3/A11 verified structural in
  `research_memory.py:119-158` (append/get/index only; "nothing expires"
  test-pinned).
- **Consequences:** persistence — which guarantee class the adapter must
  implement; security — anti-hidden-mutation strength; ops — over-spec
  adds deploy burden (e.g. Opt 3 for storage-level); architecture —
  available classes differ per D1 engine.
- **Evidence/reversibility/tests/authority:** evaluation §7 (M3 default,
  B-labelled); re-decidable until adapter lands; adapter tests pin the
  chosen class; authority: OWNER (ratification).
- **Disposition permitted now:** owner ratification or amendment. Not
  executable by the implementer.

### 5.4 D4 — Access-control model + episodic-evidence readers

- **Canonical wording (brief §D verbatim):** "access-control model + who may
  read episodic evidence (A8 approval state interacts with this)."
- **State:** OPEN (unchanged).
- **Options + provenance:** strongest (Opt 3 roles/RLS) / file-perms+hash
  (Opt 1) / weakest (Opt 2 file perms only) (brief §B rows); A8 locus
  `02:198` (governed actions carry approval state).
- **Consequences:** permission/security — governs research-artifact
  confidentiality; wrong choice leaks artifacts; interacts with governed-
  approval semantics; persistence — access model per engine; ops —
  multi-user support only in Opt 3.
- **Evidence/reversibility/tests/authority:** option comparison rows
  (B-labelled); re-decidable until adapter lands; adapter tests pin the
  model; authority: OWNER.
- **Disposition permitted now:** owner decision. Missing information:
  single-operator vs multi-user deployment (unknown C-2; tied to D2).

### 5.5 D5 — Backup/retention/DR policy

- **Canonical wording (brief §D verbatim):** "backup/retention/DR policy
  (cadence, copies, offsite?) — noting the archive itself must never be
  purged (A3/A11); backups are replication, not retention."
- **State:** OPEN (unchanged).
- **Options + provenance:** any policy that respects A3/A11 (brief §D —
  purge-based retention violates them outright regardless of engine);
  incumbent mechanism exists for SQLite (`app/data/store.py` WAL-consistent
  backups to `data/backups`); policy itself is the owner's (brief §C-4).
- **Consequences:** persistence/ops — durability of the immutable archive;
  security — recovery capability; untested recovery if no policy.
- **Evidence/reversibility/tests/authority:** A3/A11 test pins
  (`research_memory.py:120-125`); policy changeable anytime pre-runtime;
  DR drill tests at adapter time; authority: OWNER.
- **Disposition permitted now:** owner decision (policy facts are owner-
  environment facts). Not executable by the implementer.

### 5.6 D6 — Blob-store location + size ceilings

- **Canonical wording (brief §D verbatim):** "blob-store location
  (inside/outside repo tree) and any size ceilings the owner wants to
  ratify (the P0 numeric-ceiling ratification in the acceptance package is
  the same class of decision)."
- **State:** OPEN (unchanged); engineering default PROPOSED (outside repo
  tree, content-addressed — register review D-4; ratification is the
  owner's).
- **Consequences:** architecture/ops — repo hygiene; push implications
  (push itself owner-gated); persistence — artifact integrity addressing
  (`ArtifactRef`/`input_snapshot_sha256` already test-pinned); security —
  content-addressing gives tamper-evidence.
- **Evidence/reversibility/tests/authority:** register review D-4; contract
  test pins; re-decidable until adapter lands; adapter tests pin the
  convention; authority: OWNER.
- **Disposition permitted now:** owner ratification/amendment. Missing
  information: size ceilings (no measurable volumes pre-runtime).

### 5.7 D7 — Timing (decide now vs after G2)

- **Canonical wording (brief §D verbatim):** "timing — decide now (pre-G2,
  to make the adapter testable in synthetic runs) vs after G2 (risk: none
  identified for deferral, since the contract layer is complete and the
  adapter is additive either way)."
- **State:** OPEN as an owner decision; the ENGINEERING-class resolution is
  already recorded — register review A-5: "Resolved as engineering
  (class 2): defer adapter until D2/D3/D4 answered; contract layer
  unaffected". The owner-facing question (when to answer D1–D7) remains the
  owner's.
- **Options + provenance:** decide-now / after-G2 (brief §D); deferral risk
  explicitly assessed NONE (brief §D verbatim).
- **Consequences:** sequencing only — early adapter work would be
  unauthorized runtime-adjacent work under current gates; no architecture/
  persistence/permission effect from the choice itself.
- **Evidence/reversibility/tests/authority:** register review A-5/D-7;
  execution record §3 (deterministic in-memory stores delivered; NO
  migration performed); authority: OWNER.
- **Disposition permitted now:** owner decision on timing. The engineering
  defer-resolution stands regardless.

### 5.8 Execution statement for D1–D7

**Nothing was executed against D1–D7 in this cycle.** The directive
authorizes executing only changes that are "explicitly authorized,
objectively testable, reversible where appropriate, and independent of
blocked gates" — no D1–D7 option is selected by any owner record or by
CONSOL-GOV-6 itself, and the persistence adapter is post-G2 work under
D-AI-28 discipline. The seven records above are the complete preparation;
the exact disposition permitted under existing owner decisions is, for
every item: owner decides (or defers with a date). **D2 explicitly remains
incomplete while its P3.43 dependency is unsatisfied** (§5.2).

## 6. pip-audit — authorized controlled remediation EXECUTED (certifi)

Directive authorization: investigate and remediate the reported `certifi`
advisory in the project-controlled tooling environment; upgrade/pin the
fixed version in the narrowest project-controlled scope; no global Python
installation or unrelated environment mutated; exact before/after recorded;
rollback procedure stated; re-run pip-audit + regression tests; confirm the
advisory is gone; report blockers if any (none occurred).

| Item | Value |
|---|---|
| Environment | `RADAR_BOURSE/repo/.venv` (project-controlled tooling venv; git-ignored per `.gitignore:33`; Python 3.12 venv) |
| Dependency source | transitive (no direct pin in any requirements file — fresh grep: zero `certifi` mentions in `backend/requirements*.txt`); installed via pip from PyPI |
| Version BEFORE | certifi **2026.7.22** (`pip show`, capture `pip_remediation/01_before_state.txt`) |
| Advisory mapping | pip-audit 2.10.1: **PYSEC-2026-4320**, fix **2026.10.19** (current-run attribution; the earlier recorded GHSA-6q48-6c7w-9gw2 ID and CG5-01 attribution-evolution note remain preserved history) |
| Fixed-version verification | authoritative metadata check: `pip download certifi==2026.10.19 --no-deps` succeeded (wheel fetched; SHA-256 `42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b` — capture `pip_remediation/01_before_state.txt`) |
| Change executed | `.venv/bin/pip install certifi==2026.10.19` (exact pin; exit 0; capture `pip_remediation/03_upgrade.txt`) |
| Version AFTER | certifi **2026.10.19** |
| Dependency-consistency check | `.venv/bin/pip check` → "No broken requirements found." (exit 0) |
| Tracked dependency files changed | **NONE** — certifi is unpinned/transitive; the venv is git-ignored; therefore this remediation produces **zero tracked-tree changes** (recorded explicitly) |
| Post-fix pip-audit | **exit 0 — "No known vulnerabilities found"** (capture `pip_remediation/04_after_pip_audit.txt`) — the advisory is no longer reported for the affected package/version |
| Post-fix regression | provider validators exit 0 ×2 (fail-closed, `live_verified=false` both — `pip_remediation/05_regression_*.txt`); full pytest **621 passed / 2 warnings / 78.46s, exit 0** (`pip_remediation/06_regression_pytest_full.txt`) — zero test drift vs the pre-change battery (621/2W/78.13s) |
| Scope guard | no global Python installation touched; no other package upgraded; no unrelated environment changed; no repo code/config changed by the remediation |
| Rollback procedure | `.venv/bin/pip install certifi==2026.7.22` (restores the exact prior version; then re-run `pip-audit` — the advisory will re-appear, which is the honest prior state) |
| Blockers | none |

Battery-discipline consequence: the pre-change battery at `d59ce3e`
recorded **17/18 exit 0 + pip-audit exit 1** (certifi — the advisory this
section remediates); the at-commit battery after the docs commit records
**18/18 exit 0** — the first fully-green battery since OWNERSB1R2-01
surfaced. Per the directive, product test success (621 passed, unchanged
before and after) and dependency-audit success (pip-audit 1 → 0) are
reported as SEPARATE facts.

## 7. Findings ledger (preserved + new this cycle)

| Finding | Origin | Status this cycle |
|---|---|---|
| Manifest citation 25/25 vs 29/29 | CG3-02 (INFO, historical) | PRESERVED unrewritten; fresh recheck: `2026-10-20_consolgov2_baseline/MANIFEST_SHA256.txt` = 29 entries, current truth recorded (see §7.1 recheck below) |
| consolgov3 scratch manifest stale entries | OWNERSB1R2-00 (LOW) | PRESERVED unrewritten; fresh recheck: 26/28 reconfirmed (exact stale set: `00_exit_codes.txt`, `00_session.txt`); the prior "28/28" claim remains not reproducible |
| ownerb1r2_baseline manifest self-listing | CG4-01 (INFO) | PRESERVED; fresh recheck: self-line fails by construction, 21/21 content entries OK |
| certifi advisory attribution evolution | OWNERSB1R2-01 (LOW) + CG5-01 (INFO) | **RESOLVED by authorized remediation** (§6): certifi 2026.7.22 → 2026.10.19; pip-audit exit 1 → 0. The historical finding records (time-dependent advisory; ID attribution evolution) remain verbatim-preserved; resolution is recorded additively, no history rewritten |
| Corpus integrity | E6 / multiple cycles | Fresh: **7/7 IDENTICAL** vs `/home/z/my-project/upload/` originals (`consolgov6_audit_scratch/11_corpus_integrity.txt`) |
| Scratch-manifest race discipline | OWNERSB1R2-00 lesson | Applied: this cycle's battery manifests are generated AFTER all captures complete (no stale-entry race; see §7.1) |

### 7.1 Fresh verification results (this cycle, at `d59ce3e`)

- Corpus: 7/7 byte-identical (per-file `cmp` + SHA-256; digests match the
  g2prep-baseline record).
- `2026-10-20_consolgov2_baseline` manifest: **29/29 OK** (29 entries).
- `consolgov3_audit_scratch` manifest: **26/28** — exactly the two recorded
  stale entries; OWNERSB1R2-00 preserved.
- `2026-10-20_ownerb1r2_baseline` manifest: self-listing reconfirmed
  (CG4-01); **21/21 content entries OK**.
- Gates: `AI2_ENABLED=0` (`backend/app/core/config.py:109`);
  `verified = False` hard-coded (`config.py:270`); contract-module import
  grep over `app/api`+`app/services`: no match (exit 1); provider
  validators `live_verified=false` both (fail-closed).
- Pre-change battery at `d59ce3e`: 621 passed / 2 warnings / 78.13s;
  per-block 44/58/24/25/13/51/58; 17/18 exit 0 + pip-audit exit 1
  (certifi, remediated in §6).

## 8. Remaining owner-only actions (updated set)

1. ~~B-1 per-block decisions~~ — **EXECUTED this cycle** under the
   directive's binding rule (§1: REJECT ×5 with exact open items). The
   owner may still record superseding per-block decisions at any time
   (e.g., ratifying the P0 numeric ceilings, which would close the P0-AMD-1
   open item and permit re-disposition).
2. R2 formal procedure approval — the draft is now content-complete
   (§2); approval remains owner-only per Option C's own terms (recorded
   decision naming approving authority + effective version).
3. Reviewer designation (Class 1 with name/role/COI, or Class 2 election)
   + the reviewer's written acknowledgement → completes E5. Smallest next
   action: one owner message (§3).
4. Review scheduling under the approved procedure.
5. AI2-F condition-(a) authorization: AUTHORIZED/DEFERRED + the (iii)
   sub-choice + scope confirmation (§4 decision request unchanged).
6. AI3-M D1–D7 answers (or explicit deferral with dates); D2 remains
   blocked upstream at P3.43 (§5.2).
7. Push authorization for the unpublished chain (now 35 commits after this
   cycle's commit; B-2/R5).
8. Optional superseding decisions: P0 numeric-ceiling ratification (closes
   the P0-AMD-1 open item); AI-5 contract extension authorization (closes
   the AI1-GC open item's carrying half); next AI-MA touch scheduling
   (closes the AI-MA-C fold-in item).
