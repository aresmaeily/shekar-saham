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
   warnings / 78.30s (raw: `evidence/raw/2026-10-18_acceptance/`).
5. The authoritative G2 PROCEDURE (owner property, `05`/owner-defined) has
   still not arrived — G2 exit criteria remain BLOCKED on it, not invented.

## C1 — Category A implementation criteria A1–A14 (ai2_service.py)

Current result: **PASS** (14/14) — packaged at AI2-D, checklist §3 with
implementation line ranges and named tests (40/40). Re-verified indirectly at
`37c529d` by the full battery (the service file is untouched since AI2-E:
`git log --oneline -- backend/app/services/ai2_service.py` → AI2-A/B/C/D/E
only). Evidence: checklist §3; `evidence/raw/2026-10-17_ai2*` packs.
Responsible: Role 14 (R) with Roles 6/10/15 (C). Blocker: **No** (for review
entry; G2 verdict itself stays owner-gated).

## C2 — AI-2 required-items layer (`02:44-53`, AI2-F/Fa)

| Required item | Contract evidence (file:line) | Tests | Result |
|---|---|---|---|
| Immutable run identity + whitelist | `ai2_governance.py:286-291,315-320` (frozen; `unknown_ai2_task`) | `test_ai2_f_governance.py:84-87,157-158` | PASS (contract class) |
| Provenance | `governed_acceptance` → `provenance_complete` (`:413-418`; run_governance `:213-262`) | `:290-306` | PASS (contract) |
| Budget/time/iteration limits | `AI2BudgetSpec` `:91-93` (≤16/≤64/≤86400); ceiling-inclusive clock-free verdict `:109-121` | `:109-132` | PASS (contract) |
| Evidence artifacts | `AI2EvidenceArtifact` `:137-157` + status consistency `:322-328` | `:136-158` | PASS (contract) |
| Duplicate detection (append-only) | `classify_duplicate` `:331-351`; `AI2RunLedger` `:354-385` (no update/delete path) | `:160-188` | PASS (contract) |
| Failure/recovery | `recovery_decision` `:167-184` (deterministic gate ⇒ `ESCALATE_FAIL_CLOSED`, never retried) | `:196-210` | PASS (contract) |
| Invalidation | `invalidates` `:244-269` + canonical trust rank `:234-241` (matches `config.py:191-196` for all 6 canonical states) | `:232-272` | PASS (contract) |
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
| Tree state | tracked clean; untracked = 4 bootstrap paths + governance set (preserved); ahead 19 / behind 0; push owner-gated | PASS |

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
