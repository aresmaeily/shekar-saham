# R2 G2 PROCEDURE VERIFICATION REPORT — 2026-10-20 (Consolidated Governance Directive §4)

Status: prepared under the Consolidated Governance Directive §4 (R2 —
Establish the Authoritative G2 Procedure). This report documents the search
scope, method, and result of the attempt to establish an authoritative,
approved G2 procedure. **Result: NOT_FOUND / NOT_VERIFIED — Path B applies.**
No procedure is invented, approximated, or reconstructed from scattered
definitions. G2 remains `NOT_PASSED`; `AI2_ENABLED=0`; `live_verified=false`;
no push. Self-approval is void.

## 1. Search scope and method (what was actually examined, fresh 2026-10-20)

| # | Scope | Method | Result |
|---|---|---|---|
| 1 | The 7-file owner amendment corpus (`docs/governance/amendment_sources_2026-10-02/` = the operative governance authority: owner roadmap decision, execution roadmap, multi-agent architecture, AI governance boundaries, 17-role charter, governance decision register, product capability charter) | `rg -ic "procedure"` per file (case-insensitive) | **ZERO occurrences in all 7 files.** Raw: `docs/governance/evidence/raw/2026-10-20_consolidated_baseline/11_g2_procedure_search.txt` |
| 2 | `docs/active/` and `docs/governance/` filenames | filename filter for "procedure" | No document filename contains "procedure" |
| 3 | All `docs/active/*.md` + `docs/governance/*.md` bodies | `rg -li "procedure"` | 13 files contain the word — every hit classified in §2 below; **none is an owner-approved G2 procedure** |
| 4 | The repository's governance decision register and amendment history (as required by the directive: "Search the repository, governance documents, amendment sources, decision register, and referenced document locations") | Locus re-verification of every G2 gate locus in the corpus (D-AI-26 `05:102-107`; `02:7`; `02:10-11`; `02:32-35`; `02:200-204`; `03:61-66`; `04:72`; `05:148-150`; D-AI-40 `05:197-200`; `06:88`; `00:36`) | All loci are **gate definitions / boundary statements / RACI**, not procedures (§3) |
| 5 | Prior-cycle verification cross-check | G2PREP cycle (2026-10-20, independently audited FAIL-narrow→PASS) recorded the same absence ("zero 'procedure' occurrences"; auditor-verified "procedure-absence 0×7") | Consistent — absence is stable across two independent cycles |

## 2. Classification of every "procedure" occurrence outside the corpus (fresh hits)

The 13 body hits resolve to exactly four classes — none qualifies as an
approved G2 procedure under the directive's identity/source/approval/version
test:

1. **Absence records** (documents stating the procedure is owner property and
   has NOT arrived): `AI2_G2_REVIEWER_CHECKLIST.md:9` ("The authoritative G2
   procedure is owner property and has NOT [arrived]"), `:158`, `:168`;
   `OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §1 R2 ("the authoritative G2
   PROCEDURE does not exist in the corpus"); `G2_REVIEW_PACKAGE_2026-10-20.md`
   §3; `G2_EVIDENCE_MATRIX_2026-10-18.md` §0.5/A3; state file and register
   review entries.
2. **Unrelated procedures** (not G2 review procedures): installation runbook /
   checklist (`ALPHA_INSTALLATION_RUNBOOK.md:3` — controlled Alpha
   installation procedure for the Windows target; `ALPHA_INSTALLATION_CHECKLIST.md:107`
   — rollback-procedure confirmation row); "Locked architecture procedure"
   (`AI3_SCOPE_DERIVATION_AND_BLOCKER_RECORD.md:55` — a documentation gate, not
   G2).
3. **Pre-import expectation** (`AI3_SCOPE_DERIVATION_AND_BLOCKER_RECORD.md:76`):
   describes the decision register as expected to include "gate procedures" —
   written BEFORE the corpus import; the imported register demonstrably
   contains no G2 procedure (row 1 above). The expectation was not met by the
   actual corpus.
4. **This cycle's and the prior cycle's own artifacts** (INDEX, readiness
   report): index lines describing the above.

## 3. What IS authoritative about G2 (and why it is not a procedure)

The corpus DOES authoritatively define the gate itself:

| Aspect | Verbatim authority | Locus |
|---|---|---|
| Gate definition | "G2 remains the independent validation gate and blocks real-data AI-2 until passed." | D-AI-26, `05:102-107` |
| Gate position | `02:7` chain (P0-C → … → G2 → P4/P5/P6 → AI-1…AI-7) | `02:7` |
| Blocking semantics + pre-G2 work class | "G2 blocks all real-data AI-2 execution until formally passed. Design, contracts, paper/synthetic tests and dry-runs may proceed before G2."; "only bounded design, schema work, source-registry design, synthetic/paper tests and safe dry-run work are allowed under existing policy" | `02:10-11`, `02:201-202` |
| Participants | "Formal human gate requiring the designated evidence, quant and QA validation roles plus owner authority." | `02:32-35` |
| RACI | "G2: 1(A), 6/14(R), 9/10/15(C)" | `04:72` |
| Owner approval reserved | "Owner approval remains required for … G2 pass …" | `05:148-150` |
| Reaffirmation | D-AI-40 | `05:197-200` |

These are entry-conditions and authority facts. They do NOT specify: the
procedure document, evidence-provenance rules, objective pass/fail and
exception criteria, reviewer qualification/independence rules beyond the RACI
nouns, execution steps, remediation/re-review rules, sign-off mechanics,
versioning, or audit trail of the review process itself. Per the governing
directive, a draft, implementation note, scattered definition, worklog, or
unapproved checklist is not an approved procedure — and none of the in-repo
G2 material (`AI2_G2_REVIEWER_CHECKLIST.md`, `G2_EVIDENCE_MATRIX_2026-10-18.md`,
`G2_REVIEW_PACKAGE_2026-10-20.md`) claims to be one; each is explicitly labeled
review-preparation scaffolding.

## 4. Verification conclusion

- **Path B applies**: no valid approved procedure can be established from
  verifiable evidence. The official G2 procedure status is **NOT_FOUND /
  NOT_VERIFIED** (NOT_FOUND in every authoritative location searched; the
  identity, source, approval status, applicable version, and governing
  authority required by the directive cannot be evidenced because no such
  document exists in the corpus or the repository).
- Consequences in force: G2 exit criteria remain **BLOCKED on the authoritative
  owner procedure**; the review may be *convened* only against the
  corpus-defined participants + owner authority; the exit decision remains the
  owner's alone; G2 = `NOT_PASSED`.
- The formal governance change request required by Path B is delivered as the
  companion document `G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md`.
- Owner alternative explicitly preserved (from the decision package §1 R2): the
  owner may supply their own procedure document into the governance corpus, OR
  record an explicit owner statement that the corpus text (`02:32-37` +
  `04:72` + D-AI-26) IS the whole procedure. Either resolves R2's procedure
  input; only the owner can record it.
