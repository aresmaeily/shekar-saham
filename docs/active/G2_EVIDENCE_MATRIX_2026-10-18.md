# G2 EVIDENCE MATRIX — 2026-10-18 (prepared for the authorized G2 review)

Status: REVIEW-PREPARATION EVIDENCE, NOT G2 APPROVAL. G2 remains `NOT_PASSED`.
`AI2_ENABLED=0` (config.py:109), `live_verified=false`, LLM NOT EXECUTED.
Companion to `AI2_G2_REVIEWER_CHECKLIST.md` (AI2-E) and
`AI2_G2_READINESS_EVIDENCE_PACKAGE.md` (AI2-D); this matrix re-baselines their
state to HEAD `37c529d` and adds the post-AI2-E blocks (AI2-F/Fa corpus-derived
required-items layer). RACI for G2 per the 17-role charter: **Role 1 (A);
Roles 6/14 (R); Roles 9/10/15 (C)**. Self-approval is void.

## 0. What changed since the AI2-E checklist

1. The amendment corpus arrived: 7 owner files, byte-identical (SHA-256
   manifest `evidence/raw/2026-10-18_amendment_import/import_manifest.txt`;
   re-verified against upload originals 2026-10-18). Checklist §10
   (NOT_SYNCED) and decision R1's precondition are therefore superseded —
   **R1 is now decidable**.
2. AI2-F/Fa (`6aeeaa2`+`17ef611`) implemented the eight `02:44-53` required
   items as contracts (matrix §C2 below).
3. AI1-GC, AI-MA-C, AI3-M delivered the upstream contract chain (AI-1 → AI-2 →
   AI-MA → AI-3 all delivered at the pre-G2 contract class).
4. Full battery independently re-run at `37c529d`: 512 passed / 2 pre-existing
   warnings / 78.24s (raw: `evidence/raw/2026-10-18_acceptance/`).
5. The authoritative G2 PROCEDURE (owner property, `05`/owner-defined) has
   still not arrived — G2 exit criteria remain BLOCKED on it, not invented.

## C1 — Category A implementation criteria A1–A14 (ai2_service.py)

Current result: **PASS** (14/14) — packaged at AI2-D, checklist §3 with
implementation line ranges and named tests (40/40). Re-verified indirectly at
`37c529d` by the full battery (the service file is untouched since AI2-E:
`git log --oneline -- backend/app/services/ai2_service.py` → AI2-A/B/C
commits only — AI2-D/E were docs-only and never modified the file, so the
file is unchanged since AI2-C). Evidence: checklist §3;
`evidence/raw/2026-10-17_ai2*` packs.
Responsible: Role 14 (R) with Roles 6/10/15 (C). Blocker: **No** (for review
entry; G2 verdict itself stays owner-gated).

## C2 — AI-2 required-items layer (`02:44-53`, AI2-F/Fa)

| Required item | Contract evidence (file:line) | Tests | Result |
|---|---|---|---|
| Immutable run identity + whitelist | `ai2_governance.py:286-291,315-320` (frozen; `unknown_ai2_task`) | `test_ai2_f_governance.py:84-87,90-94` | PASS (contract class) |
| Provenance | `governed_acceptance` → `provenance_complete` (`:413-418`; run_governance `:213-262`) | `:290-306` | PASS (contract) |
| Budget/time/iteration limits | `AI2BudgetSpec` `:91-93` (≤16/≤64/≤86400); ceiling-inclusive clock-free verdict `:109-121` | `:109-132` | PASS (contract) |
| Evidence artifacts | `AI2EvidenceArtifact` `:137-157` + status consistency `:322-328` | `:136-158` | PASS (contract) |
| Duplicate detection (append-only) | `classify_duplicate` `:331-351`; `AI2RunLedger` `:354-385` (no update/delete path) | `:160-188` | PASS (contract) |
| Failure/recovery | `recovery_decision` `:167-184` (deterministic gate ⇒ `ESCALATE_FAIL_CLOSED`, never retried) | `:196-210` | PASS (contract) |
| Invalidation | `invalidates` `:244-269` + canonical trust rank `:234-241` (matches `config.py:191-196` for all 6 canonical states) | `:223-272` | PASS (contract) |
| Human approval state | `governed_acceptance` `:407-422` (pending/escalated/rejected blocked) | `:275-306` | PASS (contract) |

Residual (disclosed in the acceptance package, one-commit remediable):
`governed_acceptance` does not consult `record.status`; record-level APPROVED
has no approver binding; unknown trust strings rank −1 vs config's synthetic
folding. Result at RUNTIME level: **BLOCKED** (the runtime does not consume
this layer yet; consumption is post-G2 work).
Responsible: Roles 6/14 (R), 10/15 (C). Blocker for G2 review: **No** (as
contract evidence); Blocker for G2 PASS: **Yes** (runtime integration +
procedure).

## C3 — Governance gates (entry criteria E4)

| Gate | Evidence | Result |
|---|---|---|
| `AI2_ENABLED` default off | `backend/app/core/config.py:109` (`_env_bool("AI2_ENABLED","0")`) | PASS |
| No AI-2/AI-3/AI-MA HTTP route | zero imports in `app/api/*`, `app/services/*` of the five contract modules (grep 2026-10-18) | PASS |
| `live_verified=false` | `config.py` trust builder cannot mint verified LIVE (`build_data_trust_context` hard-codes verified=False, `:214`) | PASS |
| Production path structurally unreachable | Gate 1→2→3 ordering `ai2_service.py:345-403`; tests A5/A13 | PASS |
| LLM NOT EXECUTED | no credentials in environment; no live transport | PASS |
| Tree state | tracked clean; untracked = 4 bootstrap paths + governance set (preserved); ahead 19 / behind 0 at the matrix baseline `37c529d` (re-verified 2026-10-20 at HEAD `a8d6e19`: ahead 26 / behind 0, tracked clean, live remote unchanged — currency addendum §A1); push owner-gated | PASS |

## C4 — Runtime / production / operational criteria

Result: **BLOCKED** (8 rows, unchanged from the AI2-E package §4b): real-data
execution (G2 NOT_PASSED), live provider credentials (absent), owner acceptance
to enable AI-2 outside tests (PENDING), scheduled/production deployment
(owner environment). No new runtime claims made by AI2-F/AI-MA-C/AI3-M
(contracts only, D-AI-41 respected).

## C5 — Environment items

Result: **NOT_VERIFIED** (3 rows, unchanged): Windows-target validation,
Python 3.13 parity, native Claude CLI recognition. All batteries to date ran
Linux sandbox / Python 3.12.x. No evidence exists; none invented.

## Entry criteria E1–E6 (checklist §9) — current status

- E1 reviewed SHA: checklist fixed `56deaff`; **update needed** → recommend the
  reviewer re-fixes the reviewed SHA at the G2 review start (current HEAD
  `37c529d`, chain ancestry verified 2026-10-18). Owner/reviewer action, not a
  defect.
- E2 evidence package + checklist present and internally consistent: **PASS**
  (AI2-E integrity audit `54626ee`; paths resolve).
- E3 battery reproducible: **PASS** — re-executed at `37c529d` (512/2
  warnings), matching recorded baselines; raw outputs preserved.
- E4 gates in code: **PASS** (matrix §C3).
- E5 limitations acknowledged: **PENDING reviewer** (§5 cancellation
  containment + §6 isolation/credentials/environment of the checklist).
- E6 amendment-corpus status: **SUPERSEDED — now SYNCED** (7 files verified);
  the owner-defined exit criteria supersede checklist §9-exit on arrival,
  exactly as the checklist anticipated.

## Explicit owner decisions required (checklist §8, updated)

| # | Decision | Holder | State |
|---|---|---|---|
| R1 | Accept the 7 imported originals as authoritative sources | Owner | **Ready to decide** — corpus present + byte-verified; acceptance matrix re-baselined (this document) |
| R2 | Authorize + schedule the G2 review; supply the authoritative G2 procedure | Owner + independent validator | **Blocked on owner** — procedure still NOT_SYNCED; reviewer assignment open |
| R3 | Authorize live-credential provisioning + live validation run | Owner | Blocked on owner; only then may `live_verified` transition |
| R4 | Enable `AI2_ENABLED=1` outside tests | Owner | Blocked on G2 pass + explicit acceptance |
| R5 | Push / publish the 19-commit local chain | Owner | Blocked on owner (push auth also a P3.43 launch blocker) |
| R6 | Verify Windows / Py3.13 / CLI recognition in owner environment | Owner | Blocked on owner environment access |

Blocker summary: the ONLY non-owner blocker class remaining before a G2 review
can convene is **R2's procedure document**; everything else is owner scheduling
or post-G2 sequencing. No criterion in this matrix may be self-approved.

---

# ADDENDUM — 2026-10-19 (owner directive R6: continue G2 package preparation; NOT an approval)

Status: REVIEW-PREPARATION EVIDENCE ONLY. G2 remains `NOT_PASSED`; this
addendum refreshes evidence currency for the future authorized review; it
is not a review and not a decision. Self-approval remains void.

## A1. Evidence currency refresh (supersedes matrix §86 E1 note)

- Reviewed-SHA chain extended: `37c529d` (matrix baseline) → `a3165c4`
  (ACCPKGa) → `6a10e5a` (AI-4) → `cc98c64` (AI-4a) → `adf8cdf` (AI-6
  block commit; SHA resolved 2026-10-20) → `1d9030c` (AI-6a) →
  `a8d6e19` (AI-6b, current HEAD). Battery re-executed pre-commit at
  HEAD `cc98c64` + AI-6 working tree: **621 passed / 2 pre-existing
  warnings / 78.31s** (raw `docs/governance/evidence/raw/2026-10-19_ai6/`,
  all components exit 0; providers `live_verified=false` fail-closed;
  bootstrap 8/8). **Battery re-executed at the current HEAD `a8d6e19`
  2026-10-20 (first full at-HEAD run for this commit): 621 passed / 2
  warnings / 77.65s, all 18 battery components exit 0** (raw
  `docs/governance/evidence/raw/2026-10-20_postai3_battery/`, SHA
  manifest 38/38 OK). E1/E3 currency: refreshed 2026-10-20.
- E2 (package + checklist present, internally consistent): unchanged
  PASS; AI-2 criteria A1–A14 and the eight `02:44-53` required items are
  untouched by later blocks (additive-only discipline, audit-verified
  per block).
- E4 (gates in code): re-verified this cycle — `AI2_ENABLED=0`
  (`config.py:109` untouched by AI-4/AI-6), no new route in either new
  module (import-surface tests enforce), G2 NOT_PASSED, `live_verified=false`.
- E5 (limitations acknowledged): cancellation-containment and
  environment limitations unchanged; AI-6 adds none (no runtime exists).
- E6 (corpus SYNCED): unchanged (7 files byte-verified).

## A2. New block evidence available to the reviewer (adds to §C-class rows)

| Block | Contract evidence | Test evidence | Audit evidence |
|---|---|---|---|
| AI-4 (`6a10e5a`+`cc98c64`) | `AI4_SCOPE_DERIVATION.md` R1–R14; `governed_generation.py` | 51 tests; battery 563 (raw `_ai4`, `_ai4a`) | initial FAIL (narrow) → remediation AI-4a → delta re-audit **PASS** (history preserved) |
| AI-6 (`adf8cdf`+`1d9030c`+`a8d6e19`) | `AI6_SCOPE_DERIVATION.md` R1–R17; `external_intelligence.py` | 58 tests; battery 621 (raw `2026-10-19_ai6`; at-HEAD re-run 2026-10-20 `_postai3_battery`) | completed chain: initial FAIL (narrow, preserved verbatim) → remediation AI-6a `1d9030c` → delta re-audit **PASS** → AI-6b `a8d6e19` closure (AI6-13/14) |

## A3. Owner decisions R1–R6 currency (unchanged; see `OWNER_DECISION_REGISTER_REVIEW_2026-10-19.md` for the full five-class register)

- R1 (corpus authority): corpus SYNCED since 2026-10-18; formal
  acceptance can ride the next owner review (class 5).
- R2 (G2 procedure + scheduling): STILL BLOCKED — the authoritative G2
  procedure is not among the 7 synced corpus files; reviewer assignment
  open (class 1/4).
- R3/R4 (live credentials; `AI2_ENABLED=1`): blocked, unchanged.
- R5 (push): publication-readiness report delivered 2026-10-19; push
  remains owner-gated; NO push performed.
- R6 (owner-environment verification): Windows / Python 3.13 / CLI
  recognition remain NOT_VERIFIED.

---

# ADDENDUM A4 — 2026-10-20 (Consolidated Governance Directive cycle; NOT an approval)

Status: currency refresh under the Consolidated Governance Directive §6.
Prior content preserved unchanged. G2 remains `NOT_PASSED`;
`AI2_ENABLED=0` (`config.py:109`); `live_verified=false` (`config.py:270`);
LLM NOT EXECUTED; no push (live remote `c1984e7` re-verified via `ls-remote`
exit 0 this cycle). Self-approval void.

- **E1/E3 currency**: fresh read-only baseline at HEAD `d380ee5` — ahead 29 /
  behind 0; tracked clean; `git diff --check` 0; stash 0; single worktree;
  untracked = exactly the 4 bootstrap paths; all block commits ancestors;
  corpus 7/7 byte-identical; full battery reproduced **621 passed / 2
  pre-existing warnings / 77.94s**, 18/18 components exit 0, per-block
  44/58/24/25/13/51/58 (raw `docs/governance/evidence/raw/2026-10-20_consol_precommit/`,
  manifest 20/20 OK; baseline `.../2026-10-20_consolidated_baseline/`,
  manifest 10/10 OK). Zero discrepancy from every preserved baseline.
- **C2 residual note**: the three AI2-F residual observations were re-verified
  STILL PRESENT in code this cycle (`governed_acceptance` :393-423 no
  `record.status`; record-level APPROVED without approver field;
  `_TRUST_RANK` :234-241 unknown-string −1 vs `config.py:191-196` folding) —
  condition (a) OPEN, disposal-ready, owner authorization required per the
  governing directive §7 (see `AI2F_AI3M_DECISION_RECORD_2026-10-20.md`).
- **E5**: remains **NOT_VERIFIED** (reviewer acknowledgment pending) —
  deliberately preserved, not carried forward blindly; no qualifying new
  evidence exists.
- **G2 procedure**: re-verified ABSENT this cycle (fresh search — zero
  "procedure" occurrences across all 7 corpus files; every body hit outside
  the corpus classified as absence-record/unrelated-procedure/pre-import
  expectation). R2 remains BLOCKED on owner input; formal change request
  delivered (`G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md`; verification
  report `R2_G2_PROCEDURE_VERIFICATION_2026-10-20.md`).
- **Audit history**: G2PREP audit chain (FAIL narrow G2P-02 MEDIUM +
  G2P-01 LOW at `8e10e11` → remediation `d380ee5` → delta PASS) preserved
  verbatim in `docs/governance/evidence/2026-10-20_G2PREP_independent_audit.md`.
- **New companion artifacts**: `B1_OWNER_DECISION_MATRIX_2026-10-20.md`,
  `AI2F_AI3M_DECISION_RECORD_2026-10-20.md`,
  `R2_G2_PROCEDURE_VERIFICATION_2026-10-20.md`,
  `G2_PROCEDURE_APPROVAL_REQUEST_2026-10-20.md`,
  `G2_REVIEWER_NOMINATION_RECORD_2026-10-20.md` (reviewer NOT_APPOINTED —
  owner designation required).

---

# ADDENDUM A5 — 2026-10-20 (CONSOL-GOV Evidence Currency cycle @ `b12b0cf`; NOT an approval)

Status: currency refresh under the CONSOL-GOV Evidence Currency directive; no
status upgraded; no owner decision inferred.

- **Candidate-SHA currency**: HEAD now `b12b0cf` (30 ahead / 0 behind vs live
  `origin/main` `c1984e7`, ls-remote exit 0, NO push); commits after the
  package-time candidate `7490ad4` remain docs-only (8e10e11 G2PREP,
  d380ee5 G2PREPa, b12b0cf CONSOL-GOV); tracked tree clean; 4 bootstrap
  paths preserved. Evidence: `raw/2026-10-20_consolgov2_baseline/`.
- **Owner-decision intake**: NO owner decision present in any of the four
  canonical decision files (all owner fill-in fields blank at `b12b0cf`;
  no new commits; tracked tree clean). Silence is not approval.
- **Corpus (E6)**: 7/7 byte-identical fresh (cmp + SHA-256, all digests match
  the g2prep-baseline recorded values) — `raw/2026-10-20_consolgov2_baseline/26_corpus_integrity_refresh.txt`.
- **Battery (E3)**: re-run at `b12b0cf` — 621 passed / 2 pre-existing
  warnings / 77.94s, 18/18 components exit 0, per-block 44/58/24/25/13/51/58,
  zero discrepancy (raw `raw/2026-10-20_consolgov2_battery/`, manifest 19/19 OK).
- **Gates (E4)**: fresh capture at `b12b0cf` — `AI2_ENABLED=0`
  (`config.py:109`), `verified=False` (`config.py:270` region), contract-module
  import grep `app/api`+`app/services` exit 1
  (`raw/2026-10-20_consolgov2_baseline/28_gates_fresh_capture.txt`).
- **E5**: remains **NOT_VERIFIED** (reviewer acknowledgment pending) —
  deliberately preserved; no qualifying new evidence exists.
- **G2 procedure**: remains ABSENT from the corpus (Path B NOT_FOUND/NOT_VERIFIED
  stands; no owner selection among options A/B/C recorded).
- **Audit history**: G2PREP chain (FAIL narrow G2P-02 MEDIUM + G2P-01 LOW at
  `8e10e11` → remediation `d380ee5` → delta PASS) preserved verbatim —
  untouched this cycle.
