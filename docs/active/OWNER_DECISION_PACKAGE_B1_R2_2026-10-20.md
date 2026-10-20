# OWNER DECISION PACKAGE — B-1 and R2 — 2026-10-20

Status: prepared under the G2 REVIEW CONVENING AND OWNER-DECISION READINESS
directive (Step 2). This package identifies the exact owner decisions, their
authoritative sources and acceptance criteria, the evidence needed to dispose
of each recorded condition, and the consequences of each outcome. It records
NO decision, grants NO approval, and changes NO gate. G2 remains
`NOT_PASSED`; `AI2_ENABLED=0`; `live_verified=false`; LLM NOT EXECUTED; no
push. Self-approval is void.

Sources inspected (all re-verified fresh 2026-10-20): `05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md`
(D-AI-26, D-AI-40, engineering-authority clause), `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md`
(lines 7–11, 32–37, 200–204), `03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md`
(§G2), `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md` (§72 RACI),
`OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md` (items 1–5 + 2026-10-20 currency
addendum), `G2_EVIDENCE_MATRIX_2026-10-18.md` (+ addendum),
`AI2_G2_REVIEWER_CHECKLIST.md` (§8 R-rows, §9 E1–E6),
`OWNER_DECISION_REGISTER_REVIEW_2026-10-19.md` (B/C/D/E classes),
`AI2F_EXECUTION_RECORD.md` §6–§7, `AI3M_EXECUTION_RECORD.md` §3b,
`AI3_PERSISTENCE_DECISION_BRIEF.md` + `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md`,
`AI4_AI7_P343_DEPENDENCY_MATRIX.md`. The 7-file amendment corpus was
re-verified byte-identical against the owner upload originals (fresh `cmp` +
SHA-256, 7/7 IDENTICAL — `docs/governance/evidence/raw/2026-10-20_g2prep_baseline/corpus_byte_integrity.txt`).

---

## 1. The exact owner decisions

### B-1 — Acceptance of the five delivered pre-G2 blocks

**Exact decision (from `OWNER_DECISION_REGISTER_REVIEW_2026-10-19.md` §B B-1):**
whether the owner accepts the five delivered pre-G2 contract blocks —
P0-AMD-1 (`357f4b6`+`b3cbeb1`), AI1-GC (`ea3277e`+`2f86c4a`), AI2-F
(`6aeeaa2`+`17ef611`), AI-MA-C (`e385415`+`aa86c3c`), AI3-M (`80585c8`+`37c529d`)
— at the **pre-G2 contract class** ("bounded design, schema work,
source-registry design, synthetic/paper tests and safe dry-run work",
`02:202`), as packaged with recommendations in
`OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md`.

**What the owner is deciding, precisely:** that each block's contract-layer
deliverable (module + corpus-derived tests + audit chain) meets its stated
acceptance criteria. Acceptance is contract-class only: it does NOT assert
runtime readiness, operational capability, or implementation evidence beyond
contracts (D-AI-41: "Product capability is not implementation evidence").

**Per-block acceptance criteria and recommendation (package items 1–5):**

| Block | Exact acceptance criteria (package §"Exact acceptance criteria") | Recommendation |
|---|---|---|
| P0-AMD-1 | corpus import byte-identity; contract semantics match `02:131-139`; 44 tests pass; no wiring; honesty (D-AI-41) | ACCEPT |
| AI1-GC | four capability contracts implement the `02:39-42` nouns; 58 tests pass; gap-matrix honesty; gates unchanged | ACCEPT |
| AI2-F | all eight `02:44-53` required items enforced; 24 tests pass; trust ranking canonical; service untouched, gates unchanged | **ACCEPT WITH CONDITIONS** (§2 below) |
| AI-MA-C | AI-MA-1..6 contracts present and enforced; 25 tests pass; prohibition set `02:81` structurally enforced; runtime NOT instantiated | ACCEPT |
| AI3-M | episodic immutability structural (no mutation API); semantic curation/versioning/retirement; PIT honesty; 13 tests pass; blocker isolation (persistence brief delivered) | ACCEPT, **persistence routed to owner** (§2 below) |

**Authoritative source of the decision requirement:** the acceptance package
itself (prepared for owner decision, `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md`
ledger statement: "Owner acceptance must be recorded by the owner (absence of
response is not approval)") and register review B-1 ("Whole pre-G2 contract
class; G2 entry"). The underlying authority chain: `02:200-204` (gates
preserved; pre-G2 work class) and D-AI-41.

**Evidence the owner can rely on today (fresh, 2026-10-20):** all 17 block
commits verified ancestors of HEAD `7490ad4`; per-block focused tests
re-executed green (44/58/24/25/13); full battery 621 passed / 2 pre-existing
warnings / 77.97s (raw `docs/governance/evidence/raw/2026-10-20_g2prep_battery/`,
SHA-256 manifest 37/37 OK); audit chains re-confirmed with FAIL→remediation→PASS
histories preserved verbatim (P0-AMD-1, AI1-GC, AI2-F) and PASS verdicts intact
(AI-MA-C, AI3-M); gates re-verified in code
(`raw/2026-10-20_g2prep_baseline/gates_fresh_evidence.txt`).

### R2 — Authorize + schedule the G2 review; supply the authoritative G2 procedure; designate the reviewer

**Exact decision (from `G2_EVIDENCE_MATRIX_2026-10-18.md` R-row 2 and
`AI2_G2_REVIEWER_CHECKLIST.md` §8 R2):** (i) authorize the G2 review to
convene, (ii) schedule it, (iii) supply the authoritative G2 procedure, and
(iv) designate the independent reviewer/validator.

**Authoritative sources for what G2 IS (all in the synced corpus):**

| Aspect | Authoritative text | Locus |
|---|---|---|
| Gate definition | "G2 remains the independent validation gate and blocks real-data AI-2 until passed." | D-AI-26, `05:102-107` |
| Gate position | P0-C → P0-V → P1 → P2 → P3 → **G2** → P4/P5/P6 → AI-1 → AI-2 → AI-MA → AI-3 → AI-4 → AI-5 → AI-6 → AI-7 | `02:7` |
| Blocking semantics | "G2 blocks all real-data AI-2 execution until formally passed. Design, contracts, paper/synthetic tests and dry-runs may proceed before G2." | `02:10-11`; also `02:201`, `03:61-66`, `06:88`, `00:36` |
| Required participants | "Formal human gate requiring the designated evidence, quant and QA validation roles plus owner authority." | `02:32-35` |
| RACI | "G2: 1(A), 6/14(R), 9/10/15(C)" (Role 1 = owner Accountable; Roles 6/14 Responsible; 9/10/15 Consulted) | `04:72` |
| Owner approval reserved | "Owner approval remains required for … G2 pass …" | `05` engineering-authority clause, `05:148-150` |
| Reaffirmation | "G2 still blocks real-data AI-2 execution until independent validation and owner acceptance." | D-AI-40, `05:197-200` |

**CRITICAL — the authoritative G2 PROCEDURE does not exist in the corpus.**
Fresh verification 2026-10-20: every "G2" locus in the 7 synced corpus files
is a gate definition or boundary statement (loci listed above); the word
"procedure" does not occur in any corpus file. The G2-matrix and checklist
statements that the procedure is owner property and has NOT arrived remain
true at HEAD `7490ad4`. Consistent with the governing directive, **no
procedure is invented, approximated, or substituted here.** What exists
in-repo is REVIEW-PREPARATION scaffolding only: E1–E6 entry criteria
(`AI2_G2_REVIEWER_CHECKLIST.md` §9, agent-authored, explicitly "from
available authoritative sources only") and the evidence matrix. The owner
procedure (if the owner has one) must arrive as an owner-supplied document;
until then the review can be *convened* only against the corpus-defined
participants + owner authority, and the *exit* decision remains the owner's
alone.

**Evidence needed before R2 can be executed:** (1) the authoritative G2
procedure document (owner-supplied, placed in the governance corpus — or an
explicit owner statement that `02:32-37` + `04:72` + D-AI-26 ARE the whole
procedure); (2) reviewer designation (a named independent validator for
Roles 6/14 responsibilities, independent of the implementing agent);
(3) reviewed-SHA fixing at review start (checklist §1 convention).

---

## 2. Recorded conditions for AI2-F and AI3-M — and the evidence needed to dispose of each

### AI2-F (ACCEPT WITH CONDITIONS — package Item 3)

**Condition (a) — residual observations dispositioned in the next AI-2
contract touch** (register review D-1, class 3, "one-commit remediable").
The three named residuals (package Item 3 "Unverified / incomplete"):

1. `governed_acceptance` does not consult `record.status` — a FAILED-status
   record with clean identity and NOT_REQUIRED acceptance would pass.
2. Record-level APPROVED has no approver binding (docstring delegates to
   RunContext; the record's own approval is taken at face value).
3. Unknown trust strings rank −1 (below mock) where `config.py:191-196`
   folds them to synthetic — fail-closed direction, but a residual divergence.

**Evidence needed to dispose condition (a):** one remediation commit touching
`backend/app/domain/ai2_governance.py` (+ its test file) that (i) makes
`governed_acceptance` block non-COMPLETED/non-terminal statuses
(positive + negative tests: FAILED record refused even with clean identity);
(ii) binds record-level APPROVED to a named approver consistent with AI1-GC
`ApprovalState` approver semantics (test: record without approver refused);
(iii) either adopts the config folding for unknown trust strings or documents
the stricter −1 ranking as the canonical contract choice with the divergence
test-pinned — followed by the affected focused tests, an independent re-audit,
and a fresh at-commit full battery. No owner decision is required for this
disposal (class 3 per the register review), but it has deliberately NOT been
executed in this cycle because the current directive scopes this session to
review preparation and evidence work; it is ready to execute as the next
authorized contract touch.

**Condition (b) — nothing implies AI-2 runtime readiness.** This is a standing
interpretation boundary, not a work item: it is disposed by construction and
stays disposed only while the gates hold. Evidence: `AI2_ENABLED=0`
(`config.py:109`, fresh 2026-10-20), G2 NOT_PASSED, no route (import-surface
grep exit 1, fresh), production path structurally unreachable
(`config.py` trust builder hard-codes `verified=False`, fresh capture).
G2 + owner acceptance (matrix R3/R4) remain prerequisites for any runtime use.

### AI3-M (ACCEPT with persistence routed to the owner — package Item 5)

**Condition — persistence decision explicitly routed to the owner.** The
corpus specifies no storage engine/format/service for AI-3
(`AI3M_EXECUTION_RECORD.md` §3). The decision package already delivered:
`AI3_PERSISTENCE_DECISION_BRIEF.md` (D1–D7) +
`AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` (§7: incumbent **SQLite WAL +
JSONL designated PREFERRED CANDIDATE** with limitations, migration plan, and
acceptance tests; NO migration performed).

**Evidence needed to dispose:** an owner decision record that (i) selects the
persistence approach (or defers with a date), (ii) ratifies the D3
immutability guarantee class (trigger-level M3 recommended by the evaluation),
and (iii) ratifies or amends D4/D6 blob-store location and ceilings. Until
then, AI-3 persistence integration is PROHIBITED (directive Step 5; D-AI-28
discipline). Post-G2 sequencing note: the persistence adapter itself is
runtime work — even after the owner decision, implementation lands post-G2.

**Recorded residual (no disposal required for acceptance):**
`lessons_active_at` one-sided conservative PIT semantics (AI3M-02 INFO,
disclosed in docstring + test + record; status-event log noted as a future
additive option only if strict PIT reconstruction is ever needed). Live
feeding of episodic artifacts requires the G2-passed research runtime —
post-G2 sequencing, not an acceptance condition.

---

## 3. Consequences of approval, rejection, or deferral

### B-1

| Outcome | Consequences |
|---|---|
| **APPROVE** (per-block or whole) | Each accepted block's ledger status moves `VERIFIED_PENDING_ACCEPTANCE` → `ACCEPTED` (contract class) in the owner record; the G2 package's owner-acceptance input for the five blocks is resolved; the G2 review loses its acceptance-pending caveat for these blocks. **Does NOT authorize:** runtime integration of any contract module, `AI2_ENABLED=1`, live data/LLM, push, G2 pass, AI-3 persistence integration. |
| **REJECT** (any block) | The rejected block enters a remediation-or-rework cycle per the owner's stated findings; the G2 review of the affected scope is postponed until re-delivery + re-audit; all gates unchanged; the code remains in the tree unless the owner directs removal (no destructive action is taken autonomously). |
| **DEFER** | Package stays "owner acceptance PENDING"; the G2 review can still be prepared and even convened, but the owner-acceptance input remains open and the reviewer must record it as PENDING; all lawful pre-G2 work continues (contract class authorized by `02:202`); no prohibited-action change. |

### R2

| Outcome | Consequences |
|---|---|
| **APPROVE** (authorize + schedule + procedure + reviewer) | The review may be convened at a fixed reviewed SHA; the designated reviewer executes the checklist/evidence matrix and records findings; the owner records the G2 verdict per the corpus participants (Role 1 A + owner authority). **A decision to convene the review is NOT a decision to pass the gate.** Does NOT authorize: `AI2_ENABLED=1`, live providers/LLM, push, or any runtime work. |
| **REJECT / DEFER** | Review not convened (or postponed); G2 stays `NOT_PASSED`; all pre-G2 lawful work continues; the prohibition set is unchanged. |

### Prohibited under EVERY outcome (until separately and explicitly authorized)

1. Push of the unpublished chain (B-2 / matrix R5) — no push, no force.
2. Live provider or LLM execution; `live_verified=true` transition (R3 / C-3).
3. `AI2_ENABLED=1` outside tests (R4 / C-2) — blocked on G2 pass + explicit acceptance.
4. AI-3 persistence integration without the required owner decision (§2; directive Step 5).
5. AI-5/AI-7 runtime work (D-AI-30 "deferred until core stability"; D-AI-31 "deferred until evidence") and P3.43 Controlled Alpha Launch (owner `INSTALL` + environment checks).
6. Production mutation, autonomous promotion, self-escalation, history rewrite
   (rebase/reset/clean/force), or gate-state changes — under every governance
   source listed in §1.

---

## 4. Decision record template (for the owner to fill)

```text
Decision date (UTC):        ______________________
B-1 (five pre-G2 blocks):   P0-AMD-1  [ ACCEPT / REJECT / DEFER ]
                            AI1-GC    [ ACCEPT / REJECT / DEFER ]
                            AI2-F     [ ACCEPT_WITH_CONDITIONS / ACCEPT / REJECT / DEFER ]
                            AI-MA-C   [ ACCEPT / REJECT / DEFER ]
                            AI3-M     [ ACCEPT / REJECT / DEFER ]  (persistence decision: routed / decided below)
AI-3 persistence (if decided now):  [ SQLite WAL + JSONL preferred candidate / other: ____ / defer ]
                                    D3 immutability class: [ M3 trigger-level / other ]
R2:                         authorize review [ YES / NO ]
                            procedure:      [ owner document supplied / corpus text (02:32-37 + 04:72 + D-AI-26) is the whole procedure ]
                            reviewer:       [ name / role — independent of the implementing agent ]
                            schedule:       [ date / window ]
Conditions acknowledged:    AI2-F (a) disposal in next AI-2 contract touch  [ ]
                            AI2-F (b) no runtime-readiness implication       [ ]
                            AI3-M persistence routed to owner                [ ]
```

No field above may be filled by the implementing agent. Absence of response
is not approval.
