# OWNER ACTION PACKAGE — CONSOL-GOV-5 — 2026-10-21

Status: **DECISION SUPPORT PACKAGE — prepared under the CONSOL-GOV-5 owner
directive** ("Owner Action Package, Independent Reviewer Readiness, and
Open-Decision Evidence"). This package reconciles the four recorded owner
decisions (B-1, R2, AI2-F, AI3-M) against their canonical records, verifies
every cited fact fresh at HEAD `33107cc73802890a46cd0742838341eb28fd164a`,
and assembles the owner-review instruments (reconciliation table, R2
approval checklist, reviewer nomination form, B-1 five-block matrix,
AI2-F brief currency, AI3-M D1–D7 matrix). It records NO decision, approves
NOTHING, appoints NO ONE, and executes NO remediation. Every field that
belongs to the owner remains EMPTY. G2 remains `NOT_PASSED`;
`AI2_ENABLED=0` (`config.py:109`); `live_verified=false` (`config.py:270`);
LLM NOT EXECUTED; no push. Self-approval is void. Absence of response is
not approval.

Verification basis (all fresh 2026-10-21, raw captures in the auditor
scratch `consolgov5_audit_scratch/`, outside the repo): baseline
`01_baseline_git_state.txt` + `02_baseline_git_env.txt`; CONSOL-GOV-4
commit audit `03_consolgov4_commit_audit.txt`; gates `04_gates_fresh_capture.txt`
+ `12_gates_fresh.txt`; corpus `10_corpus_integrity.txt` (7/7 IDENTICAL);
AI2-F residuals `11_ai2f_residuals_fresh.txt` (all three PRESENT, zero
drift); prior manifests `13_prior_manifests_recheck.txt`; pip-audit
`14_pip_audit_fresh.txt` + battery `2026-10-21_consolgov5_battery/`
(manifest 19/19 OK); charter loci `15_charter_loci.txt`.

## §1. Four-decision reconciliation table (Phase 2 deliverable)

| Decision | Canonical source (exact path) | Current recorded wording & status | Owner authority required | Required evidence | Ready for owner review? | Contradictory / duplicate / stale / unverified records |
|---|---|---|---|---|---|---|
| **B-1** — Conditional Evidence Acceptance (reaffirmed + sharpened) | `docs/active/OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md` (first message, trace `1a15ad8d626cf469`) + `docs/active/OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §1.1/§3 (second message, trace `1a15b105a0662765`) | Recorded VERBATIM in both canonical records; "accepts independently reproducible evidence only within the scope directly supported by the underlying artifacts"; "No block is accepted or rejected by implication"; all five blocks retain `VERIFIED_PENDING_ACCEPTANCE`; statuses UNCHANGED | Per-block ACCEPT / REJECT / DEFER (Role 1 A, `04:72`) via `OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §4 fill-in template | Evidence accepted (battery runs, manifests, corpus checks, gate captures, audit records at their SHAs); block-level acceptance needs the §4 template filled by the owner | **READY** — decision package + per-block matrix + §4 template complete and current; nothing missing | None. Two decision records are SEQUENTIAL (first + second message), not duplicates; consistency analysis in `OWNER_DECISIONS_CONSOLGOV4` §2. Stale citation preserved as historical finding CG3-02 (see §6) |
| **R2** — Independent, Documented Review Required; Option C owner-selected for a DRAFT | Same two canonical records (§3 of the first record; §1.2/§4 of the second) + `docs/active/G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md` (DRAFT / **NOT APPROVED**) + `docs/active/G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md` (request OPEN) + `docs/active/R2_G2_PROCEDURE_VERIFICATION_2026-10-20.md` (Path B NOT_FOUND/NOT_VERIFIED) | Draft v0.1 covers all six owner-required topics (T1–T6 mapping re-verified); approval block EMPTY; `R2=OPEN`; `E5=NOT_VERIFIED`; reviewer NOT_APPOINTED — BLOCKED | (1) Formal procedure approval naming approving authority + effective version (Option C's own closing act), OR Option A supply, OR explicit Option B statement; (2) reviewer designation (name + role + §3 form fields); (3) reviewer written acknowledgement | Owner approval record; completed nomination form; reviewer acknowledgement (completes E5) | **READY** — draft + checklist (§2 below) + nomination form (§2.3) assembled; blocked ONLY on owner acts | None. Path B verification stands unrewritten; no record claims approval. [OWNER TO CONFIRM] markers inside the draft are flagged in the checklist (§2.2), not hidden |
| **AI2-F** — condition (a) OPEN; condition (b) standing | `docs/active/AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §1 + `docs/active/AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md` (owner-authorized brief) + `OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §2 (disposal scope) | "(a) the residual observations (status-consultation gap, record-level approver binding, unknown-trust-string folding) are dispositioned in the next AI-2 contract touch (they are one-commit remediable)" — **OPEN**; no remediation executed; residuals fresh-verified PRESENT at `33107cc` this cycle (zero drift) | Separate explicit owner authorization identifying AUTHORIZED/DEFERRED + the selected (iii) sub-choice (config-folding adoption vs stricter −1 canonical) + confirmed one-commit scope | Owner decision record; on AUTHORIZED: disposal commit + focused tests + independent re-audit + fresh at-commit battery (intake-specified follow-through) | **READY** — brief complete (terminology verbatim; options reproduced from the canonical intake with no invented labels; dependencies/risks/reversibility/tests/gate impact) | None. Register review D-1 class-3 classification preserved but superseded by the stricter explicit-authorization rule (recorded in AI2F_AI3M §1.5) |
| **AI3-M** — persistence decisions D1–D7 OPEN and independent | `docs/active/AI3_PERSISTENCE_DECISION_BRIEF.md` §D (canonical definitions) + `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §6 (per-item register) + `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §2 | D1–D7 all OPEN with provenance chains intact (brief 2026-10-18 → AI2F_AI3M record §2.2 → first decision → second decision); no approval inferable from B-1/Option C/draft preparation; persistence integration PROHIBITED | Per-item owner answers (D1/D3/D4/D5/D6/D7 decidable now; D2 blocked upstream at P3.43 launch gates) or explicit deferral with date; then post-G2 adapter block | Owner decision record selecting/deferring each item; ratification of D3 class and D4/D6 defaults | **PARTIALLY READY** — D1/D3/D4/D5/D6/D7 fully briefed with options + recommendations (evaluation §7 PREFERRED CANDIDATE SQLite WAL + JSONL, B-labelled); **D2 NOT ready**: upstream-blocked at P3.43 launch gates (Windows-target validation NOT_STARTED) — deciding it today would be speculative (brief §D verbatim) | None. No missing decision invented; no status changed to make the register appear complete |

Duplicate/stale sweep performed this cycle: INDEX lists each deliverable
exactly once; the two owner-decision records carry distinct traces and do
not overlap in scope; no record contradicts the verbatim decision texts;
no historical audit result rewritten.

## §2. R2 approval and independent-reviewer package (Phase 3 deliverable)

### §2.1 Six-topic coverage of draft v0.1 — re-verified fresh at `33107cc`

Draft `G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md`: status line reads
"**NOT APPROVED**"; approval block EMPTY; R2 OPEN; E5 `NOT_VERIFIED`;
G2 `NOT_PASSED` — all confirmed by direct read this cycle. Topic mapping
(owner-required topics 1–6 → draft sections):

| Owner-required topic (verbatim intent) | Draft coverage | Verified |
|---|---|---|
| 1. Required evidence and evidence-integrity criteria | T2 (qualifying artifacts, append-only evidence dirs, SHA-256 manifests with declared self/`.exit` exclusion, 18-component battery pre-commit AND at-commit, current-run weighting) | COVERED |
| 2. Reviewer independence and conflicts of interest | T4 (competence profile Roles 6/14; independence from implementing-agent chain and remediation; COI disclosure adjudicated by owner) | COVERED |
| 3. Formal reviewer appointment and explicit acknowledgement | T4 (appointment authority solely the owner; written acknowledgement before review start completes E5; implementing agent never fills appointment fields) | COVERED |
| 4. Required review outputs (findings, exceptions, clear verdict) | T5 (dated review record: reviewed SHA, E1–E6 outcomes, classified findings, verdict recommendation, sign-off) + T3 (owner-only exceptions with scope/rationale/expiry) | COVERED |
| 5. Recorded acceptance criteria and approval authority | T3 (objective pass/fail criteria i–v) + T6 (verdict authority = owner Role 1 A; owner decision block) | COVERED |
| 6. Implementer's own audit chain cannot substitute for independent review | T4 independence clause: the implementing side's own audit chain is EVIDENCE for the review, not a substitute for any part of it | COVERED |

### §2.2 Owner-review checklist (missing content, ambiguities, acceptance criteria)

The following items are the ONLY open content decisions inside the draft.
Each is already marked **[OWNER TO CONFIRM]** in the draft itself; none
blocks reading or approving the draft's structure:

1. **Exception record form** (T3) — proposed: scope + rationale + expiry,
   recorded in the review output, owner-granted only. Owner may ratify or
   replace the form.
2. **COI disclosure form** (T4) — proposed: disclosure at acknowledgement,
   adjudicated by the owner. No form exists in the corpus; owner decides.
3. **Re-review threshold examples** (T5) — proposed rule: full re-review
   when remediation touches the reviewed block's code, gate surfaces, or
   evidence lineage; delta re-audit otherwise. Owner may add concrete
   examples or tighten/loosen the threshold.
4. **Sign-off block exact form** (T6) — proposed contents listed (reviewed
   full SHA; procedure identity + version; reviewer name/role +
   acknowledgement date; findings census; verdict recommendation; owner
   decision block). Owner may amend.
5. **Entry-prerequisites equivalence** — draft binds entry to E1–E6
   (`AI2_G2_REVIEWER_CHECKLIST.md` §9) "or owner-approved equivalents".
   Owner should either ratify E1–E6 as-is or define equivalents.
6. **Verdict-rule precedent** — T5 adopts the established
   MEDIUM⇒FAIL-narrow precedent; this is a proposal, not corpus policy;
   owner ratifies or amends.
7. **Acceptance criteria for the approval act itself** — per Option C's
   own terms, formal approval = a recorded owner decision naming (i) the
   approving authority and (ii) the effective version. The draft is
   otherwise complete; nothing else is required for approval.

No other missing content was found: the six topics are fully specified as
proposals with authoritative loci; corpus-grounded items cite exact loci
(`02:7-11,32-37,200-204`; `03:61-66`; `04:72`; `05:102-107,148-150,197-200`).

### §2.3 Independent-reviewer nomination form (ready-to-use; ALL fields blank)

Owner-completed only. No reviewer name, role, acknowledgement, or approval
is invented, assumed, or pre-filled anywhere. Appointment status remains
**NOT_APPOINTED — BLOCKED on owner designation**
(`G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md`; both addenda confirm no
designation was made by either owner decision).

```text
INDEPENDENT G2 REVIEWER — NOMINATION AND APPOINTMENT FORM (owner fills)

1. Reviewer identity
   Name:                            ______________________________
   Role / title:                    ______________________________
   Organizational affiliation:      ______________________________

2. Class (per nomination record §2)
   [ ] Class 1 — independent human validator designated by the owner
   [ ] Class 2 — owner acting directly with designated role-holders (9/10/15 consulted)

3. Independence / conflict-of-interest declaration (reviewer completes; owner adjudicates)
   Is independent of the implementing-agent chain:  [ YES / NO ]
   Not an author/remediator of any work under review: [ YES / NO ]
   Stake in an early/late G2 outcome (disclose):    ______________________________
   Other relevant interests:                        ______________________________

4. Competence verification method (Roles 6/14 nouns per 04:72):
   ______________________________

5. Appointment authority (pre-printed; not editable)
   Sole authority: Project Owner (Role 1 A, 04_17_ROLE_GOVERNANCE_CHARTER:72).
   The implementing agent cannot and did not fill any field of this form.

6. Acknowledgement (completes entry criterion E5)
   Reviewer written acknowledgement received (YES/NO): ____
   Acknowledgement date (UTC):      ______________________________
   Acknowledgement locus / artifact: ______________________________

7. Review scope granted
   Reviewed-SHA fixing convention (checklist §1) accepted: [ YES / NO ]
   Access grant (repo read; evidence dirs; owner-machine items if any): ____
   Scope boundaries (contract-class review per 02:202; runtime OUT of scope
   until separately authorized runtime review):  [ CONFIRMED / AMENDED: ____ ]

8. Required review outputs (per draft T5, as proposed)
   [ ] dated review record with reviewed SHA
   [ ] per-criterion E1–E6 outcomes
   [ ] classified findings (CRITICAL/HIGH/MEDIUM/LOW/INFO) with dispositions
   [ ] verdict recommendation
   [ ] reviewer sign-off block
   Amendments to the output set: ______________________________

9. Confidentiality / authorization terms: ______________________________
10. Availability / review window:     ______________________________
11. Appointment recorded by (owner only): ______________________________
12. Approving authority for the appointment: Owner (Role 1 A per 04:72)
```

Until this form is completed by the owner AND the reviewer's written
acknowledgement exists: `R2=OPEN`, `E5=NOT_VERIFIED`, `G2=NOT_PASSED` —
unchanged.

## §3. B-1 five-block acceptance matrix (Phase 4 deliverable)

Per-block dispositions are NOT selected or implied here. All five blocks
retain `VERIFIED_PENDING_ACCEPTANCE` per the governing records. The owner's
decision instrument remains `OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §4.

| Field | P0-AMD-1 | AI1-GC | AI2-F | AI-MA-C | AI3-M |
|---|---|---|---|---|---|
| Block ID + scope | Amendment import + P0 addendum contracts (`357f4b6`+`b3cbeb1`); 6 additive contract modules + byte-identical corpus import | AI-1 Central Brain gap closure (`ea3277e`+`2f86c4a`); 4 additive modules | AI-2 required-items layer (`6aeeaa2`+`17ef611`); `ai2_governance.py` enforcing all eight `02:44-53` items | Multi-agent runtime contracts (`e385415`+`aa86c3c`); `multi_agent.py`, AI-MA-1..6, contracts only | Research Memory (`80585c8`+`37c529d`); `research_memory.py`, episodic immutable archive + curated semantic lessons + PIT views |
| Required exit criteria (canonical) | Residual notes scheduled into next contract hardening pass (register D-2, class 3); numeric ceilings ratified/amended by owner at runtime-integration time | Runtime integration must CALL the gates (carried into AI-4/AI-5 contracts) | (a) three residuals dispositioned in next AI-2 contract touch — now additionally requires explicit owner authorization; (b) standing no-runtime-readiness boundary | DEGRADED-exchange docstring line + dead-code removal folded into next AI-MA touch (class 2/3) | Owner persistence decision record (select approach or defer with date) + D3 class ratification + D4/D6 ratification/amendment |
| Existing evidence (exact artifacts) | 44 focused tests exit 0 (latest: `2026-10-21_consolgov5_battery/pytest_p0amd1.txt`); audit `evidence/2026-10-18_P0AMD1_independent_audit.md` FAIL-narrow→remediation→PASS; corpus 7/7 byte-identical (fresh `10_corpus_integrity.txt`) | 58 focused tests exit 0 (`pytest_ai1gc.txt`); audit `2026-10-18_AI1GC_independent_audit.md` FAIL-narrow→docs-only remediation→PASS | 24 focused tests exit 0 (`pytest_ai2f.txt`); audit `2026-10-18_AI2F_independent_audit.md` FAIL-narrow→`17ef611`→PASS (AI2F-06 fixed `e385415`); residuals fresh-verified PRESENT (§5 below) | 25 focused tests exit 0 (`pytest_aimac.txt`); audit `2026-10-18_AIMAC_independent_audit.md` PASS with dispositions in `aa86c3c` | 13 focused tests exit 0 (`pytest_ai3m.txt`); audit `2026-10-18_AI3M_independent_audit.md` PASS (AI3M-01 fixed `37c529d`; AI3M-02/03 INFO disclosed) |
| Evidence gaps / contradictory findings | Runtime integration of all six schemas does NOT exist; deployment constants are engineering-authority values never owner-ratified; residual honesty notes (`pit_eligible` self-declared, `source_tier` free string, `publication>retrieval` neutralized, mid-horizon attach permitted, `evaluate()` ordering) | Enforcement-by-invocation (no runtime caller of the gates); opportunity evidence ids lack referential integrity; `MemoryOperationKind` dead schema (AI1GC-06); monitoring cycle gap on `sources_attempted`; budget ceilings inherited not cycle-enforced | Three residual observations OPEN (condition (a)); runtime consumption BLOCKED post-G2 by design | No runtime exists (D-AI-41 respected); DEGRADED-exchange docstring line owed; dead code `_shape` + `MAX_HIERARCHY_DEPTH`; `isolate_failure` structural containment only; partial failure-model mapping | Persistence = owner decision (D1–D7); live feeding G2-gated; `lessons_active_at` one-sided conservative PIT semantics (AI3M-02 INFO); memory acceptance beyond contracts NOT PROVEN (D-AI-41) |
| Current status | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | `VERIFIED_PENDING_ACCEPTANCE` with (a) OPEN / (b) standing | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | `VERIFIED_PENDING_ACCEPTANCE` with persistence routed to owner (D1–D7 OPEN) |
| Owner decision required | ACCEPT / REJECT / DEFER (§4 template) | Same | ACCEPT_WITH_CONDITIONS / ACCEPT / REJECT / DEFER | ACCEPT / REJECT / DEFER | ACCEPT / REJECT / DEFER (+ persistence decision routed or inline) |
| Consequences (from the decision package §3, summarized) | ACCEPT: ledger status → ACCEPTED (contract class) in the owner record; G2 package owner-acceptance input resolved; does NOT authorize runtime wiring, `AI2_ENABLED=1`, live data/LLM, push, or G2 pass. REJECT: remediation-or-rework cycle per owner's stated findings; G2 review of affected scope postponed; code stays in tree unless owner directs removal. DEFER: package stays PENDING; review may still be prepared/convened; reviewer records PENDING; lawful pre-G2 work continues | Same | Same; ACCEPT clears the block-level path while condition (a) remains its own separate owner authorization (completing (a) alone does NOT make the block accepted) | Same | Same; even after ACCEPT + D1–D7 answers, the persistence adapter lands post-G2 (D-AI-28 discipline) |
| Required authority + downstream gate impact | Owner (Role 1 A, `04:72`). Block acceptance does NOT move G2; G2 remains owner-reserved (`05:148-150`) | Same | Same | Same | Same |

No disposition is recommended, selected, or implied by this package.

## §4. AI2-F condition (a) — brief currency (Phase 5 deliverable)

The owner-authorized decision brief `AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md`
was re-verified against the code at HEAD `33107cc` this cycle — no re-write
was needed; the brief remains accurate and current. Fresh verification
(`consolgov5_audit_scratch/11_ai2f_residuals_fresh.txt`):

| # | Residual (verbatim name) | Fresh code evidence at `33107cc` | Status |
|---|---|---|---|
| 1 | Status-consultation gap | `backend/app/domain/ai2_governance.py:393-423` — `governed_acceptance` checks run_id/run_kind binding, provenance, approval PENDING/ESCALATED/REJECTED; `record.status` hits in range: **0** | PRESENT (zero drift) |
| 2 | Record-level approver binding | `ai2_governance.py:277-297` — `AI2RunRecord` carries `approval_state: ApprovalState`, NO approver field (hits: **0**); approver enforced on the RunContext at `backend/app/domain/run_governance.py:109` (`approved_state_requires_approver`) | PRESENT (zero drift) |
| 3 | Unknown-trust-string folding | `ai2_governance.py:230-241` `_TRUST_RANK` + `:259` `_TRUST_RANK.get(current_trust_state, -1)` (unknown ranks −1, below mock); `backend/app/core/config.py:191-196` folds unknown to `"synthetic"` — divergence confirmed, fail-closed direction | PRESENT (zero drift) |

Condition (a) remains **OPEN**. The brief's option analysis stands as
delivered: the canonical intake offers ONE specified disposal scope
(one commit touching `ai2_governance.py` + its test file; elements (i)
status-consultation blocking, (ii) record-level approver binding, (iii)
trust-folding sub-choice owned by the decision) with TWO decision outcomes
(authorize at specified scope / defer). No remediation executed; no gate
touched; condition (b) standing unchanged.

## §5. AI3-M D1–D7 decision matrix (Phase 6 deliverable)

Canonical definitions locus: `AI3_PERSISTENCE_DECISION_BRIEF.md` §D
(verified present and unchanged at `33107cc`). Statuses and provenance:
`OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §6 (per-item register). This
matrix adds the owner-facing readiness view only; no choice is made.

| ID | Canonical definition (accurate summary of brief §D) | Status | Available options (documented) | Key consequences (arch/persistence/autonomy/runtime/permission/security/ops) | Evidence & tests | Rollback/reversibility | Dependencies | Authority | Missing information (explicit) |
|---|---|---|---|---|---|---|---|---|---|
| D1 | Engine class: single-operator embedded (Option 1 SQLite+blobs / Option 2 JSONL+blobs) vs server-class (Option 3 Postgres) | OPEN | Opt1 / Opt2 / Opt3 | Ops delta (minimal/minimal/high); immutability class (app-level/format-level/storage-level); access-control class; concurrency model; Windows-deploy burden (low/low/high) | `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` §7 comparison (B-labelled); contract layer test-pinned (13 tests) | Decision reversible on paper; adapter itself post-G2 additive | D2 (blocked upstream) | Owner | Actual artifact volume (no runtime exists — cannot be measured yet) |
| D2 | Deployment target for the AI runtime (Windows host / Docker / Electron-bundled) | OPEN (upstream-BLOCKED at P3.43 launch gates) | Windows host / Docker / Electron-bundled / other | Constrains D1 engine class and D6 blob placement; premature selection embeds unverifiable deployment assumptions | `AI4_AI7_P343_DEPENDENCY_MATRIX.md`; state file §7 (Windows validation NOT_STARTED) | N/A (decision not taken) | P3.43 launch gates resolve first | Owner | Target-environment facts (owner machine inventory) — NOT_STARTABLE until P3.43 prerequisites |
| D3 | Immutability guarantee class (application- vs storage- vs format-enforced) + periodic hash audits | OPEN | App-enforced / storage-enforced / format-enforced (+ audit cadence) | Which option satisfies the owner's guarantee bar (A2/A3/A11); over-specification adds deploy burden | Evaluation §7 recommends trigger-level (M3) default for Option 1 (B-labelled); A3/A11 verified structural in `research_memory.py:119-158` | Re-decidable until adapter lands | D1 (classes available differ per engine) | Owner | Whether storage-level guarantees are REQUIRED (unknown C-3) |
| D4 | Access-control model + who may read episodic evidence (A8 interaction) | OPEN | Strongest (Opt3) / file-perms+hash (Opt1) / weakest (Opt2) | Governs research-artifact confidentiality; wrong choice leaks artifacts; interacts with governed-approval semantics (A8, corpus `02:198`) | Option comparison rows; A8 locus verified | Re-decidable until adapter lands | D1 | Owner | Single-operator vs multi-user deployment (unknown C-2) |
| D5 | Backup/retention/DR policy (cadence, copies, offsite) — archive NEVER purged (A3/A11); backups are replication, not retention | OPEN | Any policy that respects A3/A11 (purge-based retention violates them outright regardless of engine) | Durability of the immutable archive; untested recovery if no policy | A3/A11 constraints test-pinned (`research_memory.py:120-125`); incumbent WAL-consistent backup routine `app/data/store.py` | Policy changeable anytime pre-runtime | D1 (mechanism engine-specific) | Owner | Backup cadence/offsite requirements (owner environment facts) |
| D6 | Blob-store location (inside/outside repo tree) + size ceilings | OPEN | Inside repo / outside repo (engineering default PROPOSED: outside, content-addressed — register review D-4; ratification is the owner's) | Repo hygiene; push implications (push itself owner-gated); artifact integrity addressing (`ArtifactRef`/`input_snapshot_sha256` contract already test-pinned) | Register review D-4; contract test pins | Re-decidable until adapter lands | D1/D2 | Owner | Size ceilings (no measured volumes possible pre-runtime) |
| D7 | Timing: decide now (pre-G2; adapter testable in synthetic runs) vs after G2 | OPEN | Decide-now / after-G2 | Deferral risk explicitly assessed NONE (brief §D verbatim: contract layer complete; adapter additive either way); early adapter work would be unauthorized runtime-adjacent work under current gates | Register review D-7 resolution (defer adapter until D2/D3/D4 answered); execution record §3 (deterministic in-memory stores delivered; NO migration performed) | N/A (sequencing choice) | D2/D3/D4 | Owner | — |

Register-integrity note: no item status changed this cycle; no missing
decision invented; even after D1–D7 are answered, AI-3 persistence
integration remains PROHIBITED until the post-G2 adapter block is
separately authorized (D-AI-28 discipline; decision package §2).

## §6. Findings recheck ledger (Phase 7 deliverable — all re-verified fresh 2026-10-21)

| Finding | Recorded origin | Fresh recheck result at `33107cc` / tooling venv | Disposition |
|---|---|---|---|
| certifi advisory (tooling venv) | OWNERSB1R2-01 (LOW, time-dependent): certifi 2026.7.22 GHSA-6q48-6c7w-9gw2, fix 2026.10.19; advisory DB updated after same-day clean runs | pip-audit exit 1 again (fresh run 05:41Z + battery run): certifi 2026.7.22, **ID now reported as PYSEC-2026-4320**, fix 2026.10.19 — SAME package+version+fix; the DB attribution evolved from the GHSA ID recorded earlier. NOT suppressed, NOT remediated (venv mutation unauthorized; no repo/code impact; no runtime deployed) | Preserved + NEW INFO observation **CG5-01** (advisory-ID attribution evolution; same underlying advisory) |
| Manifest citation 25/25 vs 29/29 | CG3-02 (INFO, inherited): CONSOLGOV3 report §4 cited the `2026-10-20_consolgov2_baseline` manifest as 25/25; the append-only manifest evolved to 29 entries | Re-verified: `MANIFEST_SHA256.txt` = **29 entries, 29/29 OK** (30 files in dir incl. manifest itself, self+ nothing excluded — no self-line present) | Historical finding PRESERVED unrewritten; current truth recorded |
| consolgov3 scratch manifest stale entries | OWNERSB1R2-00 (LOW): prior session claimed 28/28; actual 26/28 — creation race (manifest written 19:00:29.774, `00_exit_codes.txt`/`00_session.txt` re-written .777/.778) | Re-verified: **26/28** — exactly `00_exit_codes.txt` + `00_session.txt` FAILED; the prior "28/28" claim remains NOT reproducible | PRESERVED unrewritten |
| ownerb1r2_baseline manifest self-listing | CG4-01 (INFO): `MANIFEST_SHA256.txt` lists itself; its own line fails self-check by construction | Re-verified: 22 entries incl. self-line; self-check of that one line FAILS by construction; **21/21 content entries OK** | PRESERVED |
| Corpus integrity | E6 / multiple cycles | Fresh: **7/7 IDENTICAL** vs `/home/z/my-project/upload/` originals (per-file `cmp` + SHA-256) | VERIFIED |
| Gates | config captures | `AI2_ENABLED=0` (`backend/app/core/config.py:109`); `verified = False` hard-coded (`config.py:270`); contract-module import grep over `app/api`+`app/services`: **no match** (exit 1); `live_verified=false` preserved in provider validator outputs (both fail-closed) | VERIFIED unchanged |
| Battery | Established 18-component convention | Fresh pre-commit run at `33107cc` (`2026-10-21_consolgov5_battery/`, manifest 19/19 OK): **621 passed / 2 warnings / 78.14s** (2 pre-existing starlette/anyio deprecation warnings); per-block **44/58/24/25/13/51/58**; compileall 0; pyflakes 0; alpha env/runtime/frontend 0; providers both 0 fail-closed; bootstrap 8/8; `git diff --check` 0/0; **17/18 exit 0 + pip-audit exit 1** (certifi, above) | The battery is NOT claimed "fully green" — one component exits non-zero and is reported |

No warnings were suppressed, no old evidence deleted, no prior report
rewritten. All historical findings remain verbatim-preserved with their
original identifiers.

## §7. Remaining owner-only actions (unchanged set; nothing resolvable by the implementing agent)

1. B-1 per-block ACCEPT/REJECT/DEFER via the §4 template.
2. R2 formal procedure approval (authority + version) — or Option A / Option B.
3. Reviewer designation via the §2.3 form + reviewer written acknowledgement (→ E5).
4. Review scheduling under the approved procedure.
5. AI2-F condition-(a) authorization (AUTHORIZED/DEFERRED + (iii) sub-choice + scope).
6. AI3-M D1–D7 answers (or explicit deferral with date).
7. Push authorization for the 33-commit unpublished chain (B-2/R5).
8. Optional: venv certifi refresh (hardening; would change the tooling environment — requires explicit authorization).
