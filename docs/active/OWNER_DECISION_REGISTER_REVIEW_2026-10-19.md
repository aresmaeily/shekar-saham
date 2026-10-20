# OWNER DECISION REGISTER REVIEW — 2026-10-19 (R7)

Status: prepared under owner directive 2026-10-19 Decision R7. Sources
inspected: `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md` (5 items + recommended
decisions), `G2_EVIDENCE_MATRIX_2026-10-18.md` (R1–R6 decisions, E1–E6
criteria), `AI4_AI7_P343_DEPENDENCY_MATRIX.md` (owner decisions per block),
`AI3_PERSISTENCE_DECISION_BRIEF.md` D1–D7 +
`AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` §7, `AI4_SCOPE_DERIVATION.md` §7,
`AI6_SCOPE_DERIVATION.md` §7, `AI4_SANDBOX_LIMITS_PROPOSAL.md` §5, and the
2026-10-02 governance corpus (05 register D-AI-29/30/31/40/41). Every open
decision is classified per the directive's five classes; NO approval is
fabricated, NO governance rule is silently changed, NO gate is claimed
closed because a recommendation exists.

Classes: (1) owner decision genuinely required before further work ·
(2) engineering decision safely resolvable within existing authority ·
(3) evidence or testing gap rather than an owner decision ·
(4) operational gate that cannot be waived by a general instruction ·
(5) non-blocking decision that can remain open while independent work
proceeds.

## A. Decisions resolved or advanced under THIS directive (evidence recorded)

| ID | Decision | Disposition under directive | Evidence |
|---|---|---|---|
| A-1 | AI-4 contractual acceptance (class 1 → RESOLVED-PROVISIONAL by owner) | Owner granted provisional contractual acceptance (directive R1); this cycle VERIFIED `6a10e5a`+`cc98c64` in history, scope matrix R1–R14, FAIL→remediation→delta-PASS chain, and found NO remaining defect within AI-4 scope. Contractual acceptance ≠ operational readiness (recorded). | This cycle's R1 verification; `2026-10-18_AI4_independent_audit.md` (delta PASS) |
| A-2 | AI-3 persistence candidate (D1 engine-class leaning) | R3 authorized evaluation: incumbent SQLite WAL + JSONL designated PREFERRED CANDIDATE with limitations/migration plan/acceptance tests; final architecture decision stays with owner (D2/D3/D4 open) | `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` |
| A-3 | AI-4 sandbox numeric limits (dependency-matrix "later at runtime integration") | R4 executed: grounded proposals + missing-evidence register; runtime stays disabled; values remain proposals | `AI4_SANDBOX_LIMITS_PROPOSAL.md` |
| A-4 | Publication readiness (G2-matrix R5 input) | R5 executed: 23-commit chain inventoried, target/risks/checks documented; NO push | `PUBLICATION_READINESS_REPORT_2026-10-19.md` |
| A-5 | D7 persistence-adapter timing | Resolved as engineering (class 2): defer adapter until D2/D3/D4 answered; contract layer unaffected | Evaluation §7 |

## B. Class 1 — owner decisions genuinely required before further work

| ID | Decision | Affected scope | Recommended disposition | Consequence of deferral |
|---|---|---|---|---|
| B-1 | Acceptance of the five delivered pre-G2 blocks (P0-AMD-1, AI1-GC, AI2-F, AI-MA-C, AI3-M — package recommends ACCEPT; AI2-F/AI3-M WITH CONDITIONS) | Whole pre-G2 contract class; G2 entry | Follow package recommendations; dispose AI-2 residual conditions in next AI-2 contract touch (one-commit remediable). Decision package with exact criteria/consequences: `OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md`. Currency 2026-10-20 (Consolidated Governance Directive): per-block decision matrix `B1_OWNER_DECISION_MATRIX_2026-10-20.md` (all five blocks: evidence, gaps, conditions, scope-permitted); recommendation reframed as conditional acceptance for bounded contract/documentation/audit work — NOT product acceptance/operational readiness/G2 approval | Work continues lawfully (contract class authorized by corpus), but G2 package stays "owner acceptance PENDING" |
| B-2 | Push authorization for the unpublished local chain (G2-matrix R5) | Everything (publication) | Authorize fast-forward push after the readiness-report checks; or defer | 27 commits remain local-only (count re-verified 2026-10-20 at HEAD `7490ad4`, ahead 27 / behind 0, live remote unchanged; readiness-report §11 currency note — push-time count re-derived per its §6 procedure); no remote backup |
| B-3 | Source classes to admit first (AI-6) + Two-Key Rule operational parameters + source credentials (dependency matrix) | AI-6 operationalization (D-AI-29) | Decide after reviewing AI-6 contract layer; parameters needed before ANY runtime ingestion | Contract layer stands; AI-6 runtime stays blocked (as it already is, G2-class) |
| B-4 | D-AI-30 core-stability declaration + AI-5 cadence/budget approval | AI-5 | Owner judgment call when core stability is declared | AI-5 contract extensions remain the only lawful work; scheduler runtime stays blocked |
| B-5 | D-AI-31 autonomy-expansion evidence thresholds | AI-7 | Defer until evidence exists (register already says "DEFERRED UNTIL EVIDENCE") | None today (no evidence exists to expand on) |
| B-6 | P3.43 launch: issue `INSTALL` + provide target environments (handoff blocker list) | Controlled Alpha Launch | Owner issues when ready; launch package is reviewer-ready | Launch stays blocked (Windows/browser-E2E/Electron/live-provider checks unverified) |

## C. Class 4 — operational gates that cannot be waived by general instruction

| ID | Gate | Why not waivable | Next action |
|---|---|---|---|
| C-1 | G2 (NOT_PASSED) | Requires independent validation + owner acceptance (D-AI-26; `02:201`); "a permission to conduct a review is not a decision to pass the gate" (directive R6) | Continue G2 package preparation (this cycle: E1 SHA currency refreshed; consolidated reviewer package delivered as `G2_REVIEW_PACKAGE_2026-10-20.md`); supply the authoritative G2 procedure (still missing — verified absent from the corpus 2026-10-20, not invented) + reviewer assignment |
| C-2 | `AI2_ENABLED=1` | Blocked on G2 pass + explicit acceptance (G2-matrix R4) | None until C-1 |
| C-3 | `live_verified=true` | Requires live-credential provisioning + a live validation run (G2-matrix R3) | Owner provisions credentials when ready |
| C-4 | Windows / Python 3.13 / native Claude CLI verification | Requires owner-environment access (G2-matrix R6; P3.43) | Owner-environment runs per checklists |
| C-5 | D-AI-29 activation (AI-6 operational) | Boundary set must be implemented AND validated; owner decisions B-3 | Contracts delivered this cycle; validation class requires runtime work post-G2 |

## D. Class 2/3 — engineering decisions and evidence gaps resolvable within authority

| ID | Item | Class | Disposition / next action |
|---|---|---|---|
| D-1 | AI2-F residual observations (status-consultation gap, record-level approver binding, unknown-trust folding) | 3 | Schedule into next AI-2 contract touch (package condition (a)); one-commit remediable. Currency 2026-10-20: class-3/one-commit claim verified against this row + package Item 3; residuals re-verified still present in code (`ai2_governance.py:393-423/:277-297/:234-241`); disposal NOT executed — the governing Consolidated Governance Directive §7 additionally requires explicit owner authorization (absent); see `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §1.5 |
| D-2 | P0 residual observations (pit_eligible self-declaration, free-string source_tier, publication>retrieval neutralization, mid-horizon attach, evaluate() ordering) | 3 | Schedule into next contract hardening pass (package item-1 notes) |
| D-3 | D3 immutability guarantee class (AI-3) | 2 | Recommend trigger-level (M3) as default; owner ratifies with D2/D4 |
| D-4 | D6 blob-store location/ceilings | 2/5 | Engineering default: outside repo tree, content-addressed; ratify at adapter time |
| D-5 | AI4-06/07 INFO observations (weak determinism test; hardcoded APPROVAL_PENDING in acceptance composer) | 3 | Accepted by auditor as runtime-integration notes; fold into the post-G2 runtime block |

## E. Class 5 — non-blocking decisions that can remain open

| ID | Item | Rationale |
|---|---|---|
| E-1 | Formal acceptance of the 7 imported corpus originals as authoritative (G2-matrix R1) | The corpus is already the operative authority (all directives and blocks derive from it; byte-verified); formal acceptance can ride the next owner review |
| E-2 | D-AI-31 thresholds (duplicate of B-5 for tracking) | Blocked on evidence that cannot exist pre-runtime |

## F. Register integrity statement

- No decision above was self-granted. A-1/A-2/A-3/A-4/A-5 record exactly
  what the directive authorized; B/C items remain open with their
  owners.
- Gate states after this cycle: `G2=NOT_PASSED`, `AI2_ENABLED=0`,
  `live_verified=false`, LLM NOT EXECUTED, no push — unchanged by
  construction.
- The next complete authorized roadmap block after AI-6 is assessed in
  `AI6_EXECUTION_RECORD.md` (dependency-graph inspection).
