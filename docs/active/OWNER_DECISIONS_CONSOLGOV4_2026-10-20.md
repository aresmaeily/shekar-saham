# OWNER DECISIONS — B-1, R2, AI2-F, AI3-M — RECORDED 2026-10-20 (CONSOL-GOV-4)

Status: **CANONICAL OWNER-DECISION RECORD — RECORDED**. This file records FOUR
decisions received directly from the Project Owner (second owner-decision
message of 2026-10-20, received after `OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md`
was already recorded) and maps them onto the canonical decision records. The
implementing agent acts as recording secretary ONLY: the decision text below is
quoted verbatim and carries its own provenance; no wording is paraphrased into
authority it does not have. G2 remains `NOT_PASSED`; `AI2_ENABLED=0`
(`config.py:109`); `live_verified=false` (`config.py:270`); LLM NOT EXECUTED;
no push. Self-approval is void.

## 0. Provenance of this record

| Field | Value |
|---|---|
| Decision authority | Project Owner (Role 1 A per `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md:72`) |
| Decision date (owner directive) | "CONSOL-GOV-4 — Owner Decisions for B-1, R2, AI2-F, and AI3-M; Canonical Recording and Independent Verification" |
| Received (UTC) | 2026-10-20T20:47Z (= 2026-10-21 00:17 Asia/Tehran) |
| Delivery channel | Direct owner message received in the governed execution session (IM gateway metadata: channel `zai-web`, session `web-f58053f5-02e8-43fc-b28a-601c9cd1bada`, chat `96973f39-bae3-4eec-b30c-97f02438316c`, trace `1a15b105a0662765`) |
| Pre-recording repository state | HEAD `bef3a53afca49e40e293a3d233a70129a72bd3ea` (main, ahead 32 / behind 0 vs live origin/main `c1984e7` — `git ls-remote` exit 0, NO fetch/push); tracked clean; staged 0; stash 0; 1 worktree; untracked = exactly the 4 bootstrap paths; baseline capture `consolgov4` scratch evidence `01_baseline_git_state.txt` + `02_baseline_git_env.txt` |
| Prior decision record | `OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md` (first owner message, trace `1a15ad8d626cf469`) — inspected BEFORE this recording to avoid duplicates/contradictions; this record is the SECOND dated owner decision and does not overwrite it |
| Recorded by | Implementing agent (governed execution session, CONSOL-GOV-4 cycle) — recording + explicitly authorized documentation consequences only, zero interpretive authority |

## 1. Verbatim decision text (authoritative; quoted in full)

### 1.1 Decision B-1 — Conditional Evidence Acceptance (verbatim)

> "The owner accepts independently reproducible evidence only within the scope
> directly supported by the underlying artifacts. Evidence acceptance is not
> final acceptance of a product capability, is not a G2 pass, and does not
> authorize execution of any gated capability. Each of the five B-1 blocks
> must remain `VERIFIED_PENDING_ACCEPTANCE` or `BLOCKED` until its own
> documented exit criteria and required authority are satisfied. No block is
> accepted or rejected by implication."

Required consequences stated by the owner: preserve per-block status and
decision provenance; do not convert test success or manifest validity into
product acceptance; do not infer an ACCEPT/REJECT decision for any block
unless the owner has explicitly made that block-level decision; keep
`G2=NOT_PASSED`, `AI2_ENABLED=0`, and `live_verified=false`.

### 1.2 Decision R2 — Select Option C for a Draft, Not Final Approval (verbatim core)

> "The owner selects Option C to prepare a formal, repeatable independent G2
> review-procedure draft."

Required draft topics (verbatim list, owner-stated minimum):

> "1. Required evidence and evidence-integrity criteria. 2. Reviewer
> independence and conflicts of interest. 3. Formal reviewer appointment and
> explicit acknowledgement. 4. Required review outputs, including findings,
> exceptions, and a clear verdict. 5. Recorded acceptance criteria and the
> authority responsible for approval. 6. A clear rule that the implementer's
> own audit chain cannot substitute for independent review."

Boundary sentences (verbatim):

> "The draft must remain explicitly `NOT APPROVED` until the owner formally
> approves it through the established owner-only mechanism. The implementing
> agent must not approve the procedure on the owner's behalf, appoint the
> independent reviewer on the owner's behalf, or declare R2 closed. Until
> formal approval and reviewer appointment/acknowledgement are evidenced:
> Keep `R2=OPEN`. Keep `E5=NOT_VERIFIED`. Keep `G2=NOT_PASSED`."

Documentation duty (verbatim): "Document why Option A is not currently
actionable if its required owner-supplied artifact is absent, and why Option B
would fail to meet the full independence/evidence requirements. Base this
comparison on the actual option definitions in the repository, not on
assumptions."

### 1.3 Decision AI2-F — Keep Condition (a) Open; No Unauthorized Remediation (verbatim)

> "AI2-F condition (a) remains OPEN. No code change, remediation, bypass,
> closure, or reinterpretation of condition (a) is authorized by the B-1 or
> R2 decisions. The implementing agent may prepare an evidence-based decision
> brief describing the exact condition, available options, dependencies,
> risks, reversibility, tests, and gate impact. Any remediation or closure
> requires a separate explicit owner authorization that identifies the
> selected option and scope."

Required consequences stated by the owner: inspect the actual condition (a)
definition and preserve its precise terminology; do not invent option labels
or redefine the condition; reproduce the canonical intake's options with exact
text and implications in the decision brief before asking for a separate
decision; do not implement the remediation as part of this task; keep every
affected gate and status unchanged unless the existing governing record
explicitly requires otherwise and the owner has authorized the change.

### 1.4 Decision AI3-M — D1–D7 Remain Open and Independent (verbatim)

> "AI3-M decisions D1–D7 remain OPEN unless a specific, existing, verifiable
> owner decision explicitly resolves an individual item. No approval may be
> inferred from B-1 evidence acceptance, the R2 Option C selection, or the
> preparation of the G2 procedure draft. No architecture, persistence,
> autonomy, runtime, permission, or consequential-behavior change is
> authorized by this decision."

Required consequences stated by the owner: for each D1–D7 item read and quote
or accurately summarize the actual canonical definition; record its current
status and any existing decision provenance; identify the unresolved choice,
dependencies, impact, risk, verification evidence, and required authority; do
not invent missing decisions or change the item's status merely to make the
register appear complete; do not implement D1–D7 changes under this task.

## 2. Consistency with the prior recorded decision (no contradiction; no history rewritten)

The first owner message of 2026-10-20 (trace `1a15ad8d626cf469`, recorded in
`OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md`) and this second message are
MUTUALLY CONSISTENT; the second sharpens and makes explicit what the first
directed:

| Dimension | First message (recorded) | Second message (this record) | Relationship |
|---|---|---|---|
| B-1 scope | "accepts the independently reproduced test and documentation evidence only within the scope directly supported by the recorded artifacts" | "accepts independently reproducible evidence only within the scope directly supported by the underlying artifacts" | Same rule, sharpened: adds explicit "No block is accepted or rejected by implication" and names the two retained statuses (`VERIFIED_PENDING_ACCEPTANCE` / `BLOCKED`) |
| R2 selection | Owner directed A/B/C inspection + implementing selection; the implementing agent documented Option C as selected (the message constituting Option C's contemplated explicit instruction) | Owner EXPLICITLY "selects Option C to prepare a formal, repeatable independent G2 review-procedure draft" | No change of direction: the owner now states the selection directly; the prior inference is superseded by an explicit statement (same outcome, stronger provenance) |
| R2 draft topics | Five required elements | Six minimum topics (adds the explicit implementer-audit-chain rule as its own topic) | Superset — the six topics map onto the five elements plus an explicit independence rule (§4.2 below) |
| AI2-F (a) | "AI2-F condition (a) remediation … remain[s] unauthorized unless separately and explicitly decided" | "(a) remains OPEN. No code change, remediation, bypass, closure, or reinterpretation … authorized"; decision-brief preparation AUTHORIZED | Consistent; new = the brief preparation authorization (executed: `AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md`) |
| AI3-M D1–D7 | "AI3-M persistence decisions D1–D7 remain unauthorized unless separately and explicitly decided" | "D1–D7 remain OPEN unless a specific, existing, verifiable owner decision explicitly resolves an individual item"; no approval inferable from B-1/R2/other decisions | Consistent and slightly broader: also bars inference from the Option C selection and draft preparation |

No historical audit result, no prior record, and no status value was rewritten
to produce this record. Both owner messages are preserved verbatim in their own
canonical records.

## 3. Decision B-1 — effect mapping (recorded per verbatim scope; statuses UNCHANGED)

**What IS accepted:** independently reproducible evidence, ONLY within the
scope directly supported by the underlying artifacts — the captured battery
runs, SHA-256 manifests, corpus-integrity checks, gate captures, and
independent audit records at the SHAs they were produced.

**What is NOT granted by B-1 (owner-verbatim):** final acceptance of a product
capability; a G2 pass; authorization to execute any gated capability.

**Per-block disposition (UNCHANGED, per the decision's own rule — no block
accepted or rejected by implication):**

| Block | Retained status | Governing record |
|---|---|---|
| P0-AMD-1 | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | `B1_OWNER_DECISION_MATRIX_2026-10-20.md` row 1 |
| AI1-GC | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | matrix row 2 |
| AI2-F | `VERIFIED_PENDING_ACCEPTANCE` with conditions (a) OPEN / (b) standing | matrix row 3 + `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §1 |
| AI-MA-C | `VERIFIED_PENDING_ACCEPTANCE` (contract class) | matrix row 4 |
| AI3-M | `VERIFIED_PENDING_ACCEPTANCE` with persistence routed to owner (D1–D7 OPEN) | matrix row 5 + `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §2 |

Block-level ACCEPT/REJECT/DEFER remains an owner-only per-block decision
(`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §4 fill-in form stays the
decision instrument). Test success and manifest validity remain evidence
facts only; they are not converted into product acceptance anywhere in this
recording.

## 4. Decision R2 — Option C explicitly selected; draft remains NOT APPROVED

### 4.1 Option comparison grounded in the ACTUAL option definitions

Options locus (canonical, quoted in `G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md` §1,
prepared before any owner decision existed):

- **(A)** "supply the authoritative G2 procedure document (owner-authored or
  owner-adopted), placing it in the governance corpus with its approval
  evidence"
- **(B)** "record an explicit owner statement that the existing corpus text
  (`02:32-37` participants + `04:72` RACI + D-AI-26 gate definition) IS the
  whole G2 procedure, with any additional rules the owner wishes to bind"
- **(C)** "approve a procedure drafted FROM the minimum topic set below,
  through a recorded owner decision that names the approving authority and
  version — the draft itself would be prepared only on explicit owner
  instruction"

**Why Option A is not currently actionable (artifact-based):** Option A's
required owner-supplied artifact — the authoritative G2 procedure document —
is ABSENT. Fresh verification of the complete 7-file corpus (latest:
`R2_G2_PROCEDURE_VERIFICATION_2026-10-20.md` Path B; re-confirmed this cycle
by the recorded zero-"procedure" search across all corpus files) found NO
procedure document; the upload channel delivered exactly the 7 corpus
originals and no procedure. Selecting A today would leave R2 without any
executable path until the owner supplies the document.

**Why Option B would fail the full requirements (definition-based):** the
corpus text named by B contains the required participants (`02:32-35`), the
RACI (`04:72`), and the gate definition (D-AI-26, `05:102-107`) — but NOT
explicit evidence-integrity criteria, NOT required review outputs (findings /
exceptions / verdict), NOT recorded acceptance criteria, and NOT the
implementer-audit-chain exclusion rule. Declaring that text "the whole
procedure" would formalize a procedure thinner than the owner's six minimum
topics and would weaken the independence/evidence requirements the owner
imposed — precisely what the owner's decision forbids.

**Option C selected (owner-verbatim):** prepare the formal, repeatable draft
from the six minimum topics; approval happens later through a recorded owner
decision naming the approving authority and effective version (Option C's own
terms).

### 4.2 Six required topics mapped onto the existing draft v0.1 (verified, not assumed)

Draft: `G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md` (prepared in the prior
cycle under the first owner message; re-verified this cycle section by
section).

| Owner-required topic | Draft coverage (verified) |
|---|---|
| 1. Required evidence and evidence-integrity criteria | T2 — qualifying artifacts, append-only evidence dirs, SHA-256 manifests with declared self/`.exit` exclusion, 18-component battery pre-commit AND at-commit, current-run vs lineage weighting |
| 2. Reviewer independence and conflicts of interest | T4 — competence profile (Roles 6/14 per `04:72`), independence from the implementing-agent chain and from remediation, COI disclosure adjudicated by the owner |
| 3. Formal reviewer appointment and explicit acknowledgement | T4 — appointment authority solely the owner; written acknowledgement before review start (completes E5); implementing agent never fills appointment fields |
| 4. Required review outputs, including findings, exceptions, and a clear verdict | T5 (dated review record: reviewed SHA, E1–E6 outcomes, classified findings, verdict recommendation, sign-off) + T3 (owner-only exceptions with scope/rationale/expiry) |
| 5. Recorded acceptance criteria and the authority responsible for approval | T3 (objective pass/fail criteria i–v) + T6 (verdict authority = owner, Role 1 A; owner decision block) |
| 6. Implementer's own audit chain cannot substitute for independent review | T4 independence clause: "the implementing side's own audit chain (independent read-only audits) is EVIDENCE for the review, not a substitute for any part of it" |

All six topics are covered. Items lacking a corpus basis remain marked
**[OWNER TO CONFIRM]** inside the draft; the approval block remains EMPTY.

### 4.3 Boundaries applied (owner-verbatim, unchanged)

- The draft remains explicitly **NOT APPROVED**; it is a proposal with no
  governing force until formal owner approval (approving authority + effective
  version) recorded through the established owner-only mechanism.
- The implementing agent did NOT approve the procedure, did NOT appoint a
  reviewer, and does NOT declare R2 closed.
- `R2 = OPEN`; `E5 = NOT_VERIFIED` (preserved in review-package A5 /
  evidence-matrix A5); `G2 = NOT_PASSED`.
- `G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` §3 fields remain EMPTY;
  status **NOT_APPOINTED — BLOCKED** (this decision designates no reviewer).

## 5. Decision AI2-F — condition (a) OPEN; brief prepared; NO remediation

**Condition (a) terminology preserved EXACTLY as recorded** (canonical
definition locus: `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md` Item 3; full
condition chain in `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §1 — quoted
verbatim there and reproduced in the brief):

> "(a) the residual observations (status-consultation gap, record-level
> approver binding, unknown-trust-string folding) are dispositioned in the
> next AI-2 contract touch (they are one-commit remediable)"

Fresh code verification THIS cycle (HEAD `bef3a53`, capture
`consolgov4_audit_scratch/06_ai2f_residuals_fresh.txt`): all three named
residuals remain PRESENT exactly as recorded — (1) no `record.status`
consultation in `governed_acceptance` (`backend/app/domain/ai2_governance.py:393-423`);
(2) no approver field on `AI2RunRecord` (`:277-297`; approver enforced on the
RunContext at `backend/app/domain/run_governance.py:109`);
(3) `_TRUST_RANK` unknown-string `−1` ranking (`:234-241`) vs config folding
(`backend/app/core/config.py:191-196`).

**Applied consequences:**

1. Condition (a) status: **OPEN** — unchanged.
2. NO code change, remediation, bypass, closure, or reinterpretation executed
   or authorized by this recording (the B-1 and R2 decisions do not authorize
   it — owner-verbatim).
3. The owner-authorized decision brief IS prepared:
   `AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md` — evidence-based; exact
   condition terminology; canonical intake options reproduced verbatim
   (no invented labels); dependencies, risks, reversibility, tests, and gate
   impact described; separate explicit owner authorization with selected
   option + scope required before ANY remediation.
4. Condition (b) standing boundary unchanged (no-runtime-readiness; disposed
   by construction while gates hold).
5. Gates unchanged: `AI2_ENABLED=0` (`config.py:109`); `live_verified=false`
   (`config.py:270`); no import surface; `G2 = NOT_PASSED`.

## 6. Decision AI3-M — D1–D7 register (per-item, canonical definitions; all OPEN)

Canonical definitions locus: `AI3_PERSISTENCE_DECISION_BRIEF.md` §D (quoted
per item). Provenance chain: brief 2026-10-18 →
`AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §2.2 → first owner decision
(recorded; explicitly unauthorized) → THIS decision (OPEN reaffirmed; no
approval inferable from B-1 / Option C / draft preparation).

| ID | Canonical definition (quote/summary of the brief §D) | Status | Existing decision provenance | Unresolved choice | Dependencies | Impact | Risk | Verification evidence | Required authority |
|---|---|---|---|---|---|---|---|---|---|
| D1 | "decides the engine class: single-operator embedded store (Option 1 SQLite+blobs or Option 2 JSONL+blobs) vs server-class deployment (Option 3 Postgres)" — driven by the deployment-target decision | OPEN | Brief §D (2026-10-18); AI2F_AI3M record §2.2; first owner decision 2026-10-20 (unauthorized); this decision (OPEN) | Option 1 vs 2 vs 3 | D2 (blocked upstream at P3.43 launch gates) | Determines ops delta, immutability-enforcement options, access-control class, concurrency model | Deciding before D2 = speculative architecture; deferral risk to delivered contract layer: none identified (dependency-isolated by design, `AI3_M_SCOPE_DERIVATION.md` §3) | `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` §7 (SQLite WAL + JSONL = PREFERRED CANDIDATE, recommendation only; NO migration performed — verified in repo); option comparison table (B-labelled) | Project Owner (Role 1 A, `04:72`), via canonical owner-decision record |
| D2 | "deployment target for the AI runtime (Windows host? Docker? Electron-bundled?)" — currently BLOCKED upstream at P3.43 launch gates | OPEN (upstream-blocked) | Same chain as D1 | Windows host / Docker / Electron-bundled / other | P3.43 launch gates resolve first; Windows target validation NOT_STARTED (state file §7) | Constrains D1 engine class and D6 blob-store placement | Premature selection would embed unverifiable deployment assumptions | `AI4_AI7_P343_DEPENDENCY_MATRIX.md`; state file §7 blockers table | Project Owner |
| D3 | "immutability guarantee class required (application-enforced vs storage-enforced vs format-enforced) and whether hash-verification audits should be periodic" | OPEN | Same chain; evaluation recommends trigger-level (M3) default for Option 1 | Guarantee class + audit cadence | D1 (class available differs per engine) | Determines which option satisfies the owner's guarantee bar (A2/A3/A11) | Under-specified class → hidden-mutation exposure; over-specified → needless deploy burden | Evaluation §7 recommendation (B-labelled); corpus constraints A2/A3/A11 verified against `research_memory.py:119-158` (append/get/index only) | Project Owner |
| D4 | "access-control model + who may read episodic evidence (A8 approval state interacts with this)" | OPEN | Same chain | Model + reader set (A8 interaction) | D1 (mechanism strength varies by engine) | Governs who may read episodic evidence; interacts with governed-approval semantics | Weakest model (pure file perms) adequate only for single-operator; wrong choice leaks research artifacts | Option comparison rows (access control / anti-hidden-mutation); A8 corpus locus `02:198` | Project Owner |
| D5 | "backup/retention/DR policy (cadence, copies, offsite?)" — noting the archive itself must never be purged (A3/A11); backups are replication, not retention | OPEN | Same chain | Cadence / copies / offsite policy | D1 (backup mechanism engine-specific) | Durability of the immutable archive | No policy → untested recovery; NOTE: any purge-based retention violates A3/A11 outright regardless of engine | A3/A11 constraints (structural, test-pinned: `research_memory.py:120-125` docstring); incumbent WAL-consistent backup routine exists (`app/data/store.py`) | Project Owner |
| D6 | "blob-store location (inside/outside repo tree) and any size ceilings the owner wants to ratify (the P0 numeric-ceiling ratification … is the same class of decision)" | OPEN | Same chain + `OWNER_DECISION_REGISTER_REVIEW_2026-10-19.md` §D-4 (engineering default proposed: outside repo tree, content-addressed; ratification is the owner's) | Location + ceilings | D1/D2 | Repo hygiene + artifact integrity addressing | Inside-repo blobs bloat the repo and complicate push (itself owner-gated); outside-repo needs an owner-confirmed path convention | Register review D-4 default (proposal, not decision); `ArtifactRef`/`input_snapshot_sha256` content-addressing contract already test-pinned | Project Owner |
| D7 | "timing — decide now (pre-G2, to make the adapter testable in synthetic runs) vs after G2 (risk: none identified for deferral, since the contract layer is complete and the adapter is additive either way)" | OPEN | Same chain + register review D-7 resolution (defer adapter until D2/D3/D4 answered; contract layer unaffected either way; no migration performed) | Decide-now vs after-G2 | D2/D3/D4 (register-review resolution) | Adapter testability in synthetic runs pre-G2 | Deferral risk explicitly assessed as none identified (brief §D verbatim); early adapter work would be unauthorized runtime-adjacent work under current gates | Register review D-7; execution record §3 (deterministic in-memory stores delivered; persistence = owner-environment deployment decision) | Project Owner |

**Register-integrity rule applied (owner-verbatim):** no missing decision was
invented; no item status was changed to make the register appear complete;
every item remains OPEN with its provenance chain intact. AI-3 persistence
integration remains PROHIBITED (`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md`
§2; D-AI-28 discipline); even after an owner decision, the adapter itself is
post-G2 runtime work.

## 7. Implementation ledger (exact files of this recording cycle)

| File | Action |
|---|---|
| `docs/active/OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` | NEW — this canonical four-decision record |
| `docs/active/AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md` | NEW — owner-authorized decision brief (condition (a) OPEN; no remediation) |
| `docs/active/G2_REVIEW_PROCEDURE_DRAFT_v0.1_2026-10-20.md` | Dated ADDENDUM appended (explicit owner selection of Option C; six-topic coverage verified; remains NOT APPROVED; approval block stays EMPTY) |
| `docs/active/G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md` | Dated ADDENDUM appended (Option C now EXPLICITLY owner-selected; request OPEN until formal approval) |
| `docs/active/R2_G2_PROCEDURE_VERIFICATION_2026-10-20.md` | Dated ADDENDUM appended (Option C explicit; Path B verification unchanged) |
| `docs/active/G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` | Dated ADDENDUM appended (no designation in this decision; fields stay blank; NOT_APPOINTED — BLOCKED) |
| `docs/active/AI2F_AI3M_DECISION_RECORD_2026-10-20.md` | Dated ADDENDUM appended ((a) OPEN + brief prepared; D1–D7 OPEN with register cross-reference) |
| `docs/active/B1_OWNER_DECISION_MATRIX_2026-10-20.md` | Dated ADDENDUM appended (B-1 reaffirmed and sharpened; per-block statuses unchanged) |
| `docs/STATUS.md`, `docs/CHANGELOG.md`, `docs/active/INDEX.md` | Currency rows/entries per established conventions |
| `docs/governance/PROJECT_EXECUTION_STATE.md` | State reconciliation (untracked per evidence convention) |
| Evidence | `consolgov4_audit_scratch/` (auditor scratch, outside repo) + in-repo raw evidence dirs per battery convention |
| Commit | Local docs-only commit on `main` (SHA recorded in `docs/STATUS.md` row + CHANGELOG after creation); NO push |

## 8. Remaining owner inputs (blockers after this recording — none resolvable by the implementing agent)

1. **Formal approval of the G2 review procedure** (Option C's own closing
   act): a recorded owner decision naming the approving authority and the
   effective version — OR an owner-supplied procedure document (Option A) —
   OR an explicit Option B statement. Until one of the three: R2 OPEN,
   exit criteria BLOCKED.
2. **Independent reviewer designation** (name + role, independent of the
   implementing agent) + the reviewer's written acknowledgement → only then
   can E5 move beyond `NOT_VERIFIED`.
3. **Review scheduling** under the approved procedure.
4. **Per-block B-1 acceptance decisions** (ACCEPT/REJECT/DEFER), if and when
   the owner intends block acceptance (`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md`
   §4 form). None is implied by evidence acceptance.
5. **AI2-F condition-(a) disposal authorization**: separate explicit owner
   authorization identifying the selected option and scope (brief delivered;
   no remediation executed).
6. **AI3-M D1–D7 answers** (or explicit deferral with date) — per-item register
   in §6 above.
7. **Push authorization** for the unpublished local chain (B-2 / matrix R5) —
   separate decision; NOT requested by this cycle.
