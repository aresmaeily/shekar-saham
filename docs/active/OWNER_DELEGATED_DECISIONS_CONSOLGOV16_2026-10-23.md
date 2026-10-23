# OWNER-DELEGATED DECISIONS RECORD — CONSOL-GOV-16 — 2026-10-23

Status: **RECORDED under explicit owner delegation** (CONSOL-GOV-16 directive,
§1 "Explicit Owner Delegation"). Every decision below is an
**owner-DELEGATED decision exercised by the implementing developer** — the
owner did not personally perform these acts. Attribution is delegated, not
personal. Non-delegable acts (independent review, G2 verdict) are NOT claimed
and remain blocked/NOT_PASSED.

Delegation instrument: CONSOL-GOV-16 directive §1, which explicitly delegates
the broadest legitimately delegable decision authority, including verbatim:
"selecting and approving the technically and procedurally sound R2 v0.2
candidate, provided its full hash and traceability are verified"; "deciding
whether the local-only commit chain should remain private or be published";
"authorizing narrowly scoped changes covered by the owner's explicit
delegation, including the AI2-F (a) decision, after inspecting the exact
proposed change and its validation plan".

The delegation does NOT authorize: fabricated reviewer identities, fake
acceptance, false test results, risk concealment, bypassing non-delegable
independence requirements, or evidence-unsupported claims.

---

## D-16-1 (D-O1) — R2 v0.2 review procedure APPROVED via delegated authority

- **Decision:** APPROVE the G2 review procedure candidate v0.2 and version it
  to v1.0 (the document's own clause: "Upon owner approval of this exact
  version, the procedure versions to v1.0").
- **Authority:** owner-delegated per CONSOL-GOV-16 §1/§4. The procedure's own
  approval-block clause permits filling "by the owner (directly or via
  verbatim transcription explicitly authorized in the owner's decision)" —
  this record is that transcription, authorized by the GOV-16 directive.
- **Date (UTC):** 2026-10-23T15:34Z.
- **Approved candidate identity:** `docs/active/G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md`
  SHA-256 = `0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed9b88a9b2cc65dafc`
  (214 lines / 12,328 bytes; approval block EMPTY ×4 at lines 181–184 at the
  moment of approval — computed fresh this cycle at HEAD `ac53c07`).
- **Verification performed before approval (all PASS):**
  1. Full SHA-256 computed fresh = the hash recorded by GOV-13 R1–R23,
     GOV-14, GOV-15 — zero drift.
  2. Traceability: every canonical locus cited by the procedure verified
     verbatim at the byte-verified corpus: 02:7-11 (dependency chain; G2
     blocks real-data AI-2), 02:32-37 (G2 = independent validation, formal
     human gate), 02:200-204 (gates preserved), 03:61-66 (governance/runtime
     G2 split), 04:72 (G2: 1(A), 6/14(R), 9/10/15(C)), 05:102-107 (D-AI-26
     OWNER-APPROVED/FINAL), 05:148-150 (owner approval for G2 pass),
     05:197-200 (D-AI-40 gates binding); checklist §8/§9(E1–E6)/§11 present;
     G2_EVIDENCE_MATRIX_2026-10-18.md + G2_REVIEW_PACKAGE_2026-10-20.md +
     nomination record §3 + GOV-6 resolution table present.
  3. All six T5 re-review precedents verified in git history (2f86c4a,
     d380ee5, a3165c4, 17ef611, cc98c64, 1d9030c).
  4. No invented acceptance criteria: the procedure contains ZERO G1/G3/G4/G5
     references (grep = 0 hits); the G1/G3/G4/G5 defect remains honestly
     NOT_DEFINED with the narrowest PROPOSAL pending (owner-optional).
  5. Consolidation fidelity: GOV-13 R1–R23 verification stands; change
     summary (8 items) re-read this cycle; precedence rule (v0.1 + addenda
     govern) present; no [OWNER TO CONFIRM] item resolved beyond GOV-6
     records; no owner-only field pre-filled.
- **Scope of what this approval does:** the review procedure becomes the
  operative procedure for the G2 review (D-O2/D-O3/D-O4 may now proceed
  under an approved procedure). It does NOT: pass G2, appoint a reviewer,
  constitute a review, or enable AI-2.
- **Explicitly NOT approved / still required (non-delegable):** reviewer
  appointment (D-O2 — owner names a real reviewer), written acknowledgement
  (R-A1), scheduling (R-A2), COI adjudication (D-O3), convened review at a
  fixed SHA, and the G2 verdict itself (05:148-150 reserves the G2 pass to
  owner approval; 04:72 Role 1 A).
- **Resulting changes:** the procedure file is versioned in place to
  `G2_REVIEW_PROCEDURE_FINAL_v1.0_2026-10-23.md`-equivalent state per its own
  versioning clause (title/status/approval block updated; v0.2 text otherwise
  byte-preserved; pre-approval hash recorded above and in STATUS/INDEX).
- **Reversibility:** a recorded owner decision can supersede this delegated
  approval (append-only addendum); the pre-approval artifact is recoverable
  from git history at the recorded hash.

## D-16-2 (D-O8) — Publication decision: KEEP LOCAL-ONLY PENDING INDEPENDENT REVIEW

- **Decision:** the 44-commit local-only chain (origin/main `c1984e7` → HEAD)
  REMAINS PRIVATE. No push. Publication becomes executable only after
  independent review (D-O2 reviewer → R-A1/R-A2 → D-O3/D-O4 → convened
  review) completes on a fixed reviewed SHA.
- **Authority:** owner-delegated per CONSOL-GOV-16 §1/§6.
- **Date (UTC):** 2026-10-23T15:34Z.
- **Rationale (evidence-based):**
  1. Release readiness is NOT established: the roadmap's release chain
     requires independent validation (G2 chain); no independent reviewer
     exists (D-O2 NOT_APPOINTED ×15 fields); a clean secret scan is necessary
     but NOT sufficient evidence of release readiness (GOV-16 §6 preamble).
  2. Publication-scan evidence (re-verified fresh this cycle over the full
     44-commit range): 0 real secret findings (5 candidates all verified
     false-positive: 4 prose self-reference lines in GOV-14/15 disposition
     text; 1 pre-existing origin/main doc placeholder whose VALUE line has 0
     added/0 removed lines across the entire chain); 0 binary files; linear
     single-parent chain; merge-base == live origin/main.
  3. Both release-blocking external facts: (a) independent review not yet
     obtainable; (b) authenticated push capability does not exist in this
     environment (GOV-12 Block A: anonymous receive-pack → 401; no
     credentials in the environment; P3.43 gate 5 BLOCKED). Publication is
     therefore not executable by the developer today REGARDLESS of the
     decision — the decision fixes the intent so no later ambiguity exists.
  4. Option comparison (re-run this cycle): keep-private = zero exposure,
     fully reversible, consistent with the unreviewed state (SELECTED);
     publish-now = exposes unreviewed work as if release-ready (REJECTED —
     integrity risk, misrepresents readiness); patch-series = provenance
     loss across 44 commits (REJECTED); separate release branch without
     review = misrepresents provenance/readiness (REJECTED); publish-after-
     review = remains the PREPARED next action once D-O2 chain completes.
- **Prepared publication runbook (execute only after review completes):**
  `git push origin main` (fast-forward from c1984e7; the chain is linear and
  rooted at the live origin/main — NO force, NO rewrite). Rollback: GitHub
  branch reset to c1984e7 by the owner + local no-op (local chain is the
  master copy; nothing local depends on the remote).
- **Risk acceptance:** the only risk of keeping private is single-machine
  loss of history; mitigated by the existing recovery archives (GOV-14
  4cf3f93b…/GOV-15 6dcdb782… + this cycle's fresh archive) and the local
  git object store. Accepted under delegation.

## D-16-3 (AI2-F (a) / D-O5) — Disposal authorized: ONE-commit remediation with sub-choice (iii-B)

- **Decision:** AUTHORIZE the AI2-F condition (a) disposal at exactly the
  canonical intake scope (`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §2,
  quoted verbatim in `AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md` §2):
  ONE remediation commit touching `backend/app/domain/ai2_governance.py`
  (+ its test file) that (i) makes `governed_acceptance` block
  non-COMPLETED/non-terminal statuses (positive + negative tests: FAILED
  record refused even with clean identity); (ii) binds record-level APPROVED
  to a named approver consistent with AI1-GC `ApprovalState` approver
  semantics (test: record without approver refused); (iii) **sub-choice
  (iii-B) SELECTED:** the stricter −1 ranking for unknown trust strings is
  DOCUMENTED as the canonical contract choice with the divergence
  test-pinned (NOT the config-folding adoption).
- **Authority:** owner-delegated per CONSOL-GOV-16 §1/§7 ("authorizing
  narrowly scoped changes covered by the owner's explicit delegation,
  including the AI2-F (a) decision, after inspecting the exact proposed
  change and its validation plan").
- **Date (UTC):** 2026-10-23T15:34Z (authorization recorded BEFORE any edit
  to the protected file).
- **Exact change inspected and authorized (validation plan):**
  1. `governed_acceptance` gains one blocking condition:
     `record.status != "COMPLETED"` → append `"run_status_not_completed"`
     (strictest reading of the intake's "non-COMPLETED/non-terminal": only a
     COMPLETED run has acceptable outputs; FAILED/INVALIDATED/LEDGERED/
     BUDGET_EXHAUSTED/GATED_NOT_EXECUTED/DUPLICATE_FLAGGED all refused).
     Fail-closed direction; two existing tests updated to construct
     COMPLETED records where they asserted full acceptance (the brief's
     risk note #1 anticipates exactly this).
  2. `AI2RunRecord` gains `approved_by: str | None = None` + a model
     validator mirroring `run_governance.py:107-109` verbatim
     (`approved_state_requires_approver`) so record-level APPROVED binds a
     named approver (the pydantic v2 silently-ignored-kwarg residual closes).
  3. (iii-B) doc note added to the module's engineering-authority notes +
     `_TRUST_RANK` comment; new divergence-pin tests on BOTH sides:
     contract `_TRUST_RANK.get("unknown", -1) == -1 < synthetic == 0` AND
     `config._legacy_trust_level_from_state("unknown") == "synthetic"`.
  4. Test-file comment state verified byte-level (md5-verified): both
     `type: ignore[misc]` comments correct; zero malformed bytes (an earlier
     terminal rendering dropped the `[misc]` content — rendering artifact
     only, zero file impact; recorded for audit honesty).
- **Why (iii-B) (smallest safe reversible change):** zero production
  behavior change for the trust ranking (the code already ranks unknown −1);
  resolves the residual by documenting + pinning it; strictly stricter than
  (iii-A) which would WEAKEN contract strictness (unknown would rank 0);
  both are revertible but (iii-B) changes no behavior at all.
- **Validation plan:** affected focused suite (AI2-F block), the three new
  positive/negative test groups, pyflakes + compileall, gates re-verified
  (AI2_ENABLED=0 config.py:109, verified=False config.py:270, zero ai2 refs
  under app/api), pins re-verified (run_governance.py:109 zero-drift;
  protected-file pin TRANSITIONS 43d0912b… → post-change hash, recorded),
  fresh at-commit full battery. **Independent re-audit (intake follow-through)
  remains BLOCKED_EXTERNAL_DEPENDENCY** — no real reviewer exists; it is NOT
  claimed and is recorded as the standing external action.
- **Gate impact: NONE.** This disposal is contract work; it does not enable
  real-data AI-2, does not change G2, does not touch config gates, API
  surfaces, or service defaults. AI2_ENABLED stays 0; G2 stays NOT_PASSED.
- **Reversibility:** single commit, two files, standard `git revert`; no
  migration, no persisted state, no runtime surface.

---

## Non-delegable acts — honest status after this record

- **D-O2 / R-A1 / R-A2 / D-O3 / D-O4 (reviewer chain):** NOT OBTAINED.
  `BLOCKED_EXTERNAL_DEPENDENCY`. The owner must name a real, qualified,
  conflict-free reviewer; the prepared package
  (`G2_INDEPENDENT_REVIEWER_PACKAGE_DRAFT_2026-10-22.md`) is ready for
  handoff. Nothing was fabricated.
- **E5:** NOT_VERIFIED (requires the reviewer's written acknowledgement).
- **G2 verdict:** NOT_PASSED (owner authority at a convened review; delegated
  procedure approval does NOT move it).
- **Independent re-audit of the AI2-F (a) disposal:** BLOCKED_EXTERNAL_DEPENDENCY.
