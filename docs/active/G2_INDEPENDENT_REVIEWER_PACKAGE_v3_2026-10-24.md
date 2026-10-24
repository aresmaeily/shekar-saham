# G2 INDEPENDENT REVIEWER PACKAGE — v3 — 2026-10-24

Status: **REVIEWER-READY — awaiting one real, qualified, conflict-free
independent reviewer (D-O2). Nothing in this package appoints anyone,
fabricates a review, or implies any reviewer act has occurred.**

Supersedes: `G2_INDEPENDENT_REVIEWER_PACKAGE_v2_2026-10-24.md` (kept in
place, append-only untouched) **for freshness only** — the repository
advanced after v2 was issued; v3 re-binds the package to the current HEAD
and enumerates the exact delta (§4) so the reviewed SHA is fixed with full
knowledge of what changed. Authority: delegated decisions D-19-1/D-19-2 in
`OWNER_DELEGATED_DECISIONS_CONSOLGOV19_2026-10-24.md`.

Binding: this file is part of the reviewed commit itself. The reviewed SHA
is the first commit containing this file:

```
git log --diff-filter=A --format=%H -- docs/active/G2_INDEPENDENT_REVIEWER_PACKAGE_v3_2026-10-24.md
```

and is cross-bound by the evidence bundle
`docs/governance/evidence/raw/2026-10-24_consolgov19_atcommit/SHA256SUMS.manifest`
(harness reports inside it record the exact commit they ran at).

---

## 1. Who may review (qualification — Q1–Q5, unchanged from v2/DRAFT)

- **Q1 Independence:** not the author of any commit in the reviewed range
  (authorship census available; every local-chain commit is
  implementer-authored, so any implementer-side identity is disqualified).
- **Q2 Qualification:** able to run and read a Python/pytest codebase, git,
  SHA-256 manifests; able to judge evidence freshness and test honesty.
- **Q3 Conflict of interest:** no financial/personal stake in the review
  outcome; COI declaration form (nomination §3 field set, GOV-6 #2) required.
- **Q4 Authority:** appointed by the owner (D-O2) in writing or via the
  project's authorized channel.
- **Q5 Acknowledgement:** willing to produce the written acknowledgement
  E5 requires (R-A1) and to schedule the review (R-A2 → D-O3/D-O4).

## 2. What you review (scope, fixed)

1. **Review procedure (already approved v1.0, delegated D-16-1):**
   `docs/active/G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md`
   (file keeps its historical v0.2 name; title says FINAL v1.0 approved
   2026-10-23). SHA-256 re-verified at package time:
   `1982af04af6cf2f80aead76d313e7fe7e89b644b5c8c24117fa9becf9b1926ea`.
   **As amended by ADDENDUM A1** (§3 below) — v1.0's own file is
   byte-unchanged; A1 is a separate versioned amendment document.
2. **The reviewed SHA:** the commit identified above (HEAD at handoff).
3. **Evidence inventory:** all bundles under
   `docs/governance/evidence/raw/` (latest:
   `2026-10-24_consolgov19_battery_precommit/` and
   `2026-10-24_consolgov19_atcommit/`), each with SHA256SUMS.manifest.
4. **Gates and governance records:** `docs/STATUS.md` (top row),
   `docs/CHANGELOG.md` (top section), `docs/active/INDEX.md`,
   the CONSOL-GOV-19 execution record
   `docs/active/CONSOLGOV19_EXECUTION_RECORD_2026-10-24.md`,
   decision records `OWNER_DELEGATED_DECISIONS_CONSOLGOV16_2026-10-23.md`,
   `…_CONSOLGOV17_2026-10-24.md`, `…_CONSOLGOV19_2026-10-24.md`,
   the canonical amendment corpus
   `docs/governance/amendment_sources_2026-10-02/` (7 documents).
5. **Canonical criteria:** roadmap 02:7-11/32-37/200-204; boundaries
   03:61-66; charter 04:72 (Role 1 A — G2 verdict is the owner's alone);
   register 05:102-107/148-150/197-200; D-AI-26; checklist §8/§9/§11.

## 3. Evidence-contract in force (addendum A1 — G18-1 resolution)

- R2 v1.0 T2's `.exit` sentence is amended by
  `docs/active/R2_T6_ADDENDUM_A1_EVIDENCE_MANIFEST_EXIT_RULE_2026-10-24.md`
  (delegated D-19-1): manifest self-exclusion unchanged; **every `.exit`
  file present in a bundle created on/after 2026-10-24 MUST be
  manifest-listed**; phantom listed entries prohibited; `.exit`↔`.txt`
  cross-validation retained; mixed/ambiguous bundles are invalid as
  A1-era evidence; pre-A1 bundles (CONSOL→GOV-15) remain valid under
  their era's convention and are never rewritten.
- Machine check: harness predicate `G2-C-v-exit`
  (`manifest_exit_coverage()`); A1-era bundles must report `COMPLIANT`.

## 4. Delta since package v2 (reviewed-SHA fixing context)

v2 was bound to `75b7385a2ed2a9493f3aea1b398fec7585a87be4` (GOV-17). Two
commits followed:

1. **`300ca7a37b9263ac23c0ed25e95a3c6b8b61b7bb` (GOV-18) — DOCS-ONLY**
   (4 files, +247/−1: `docs/CHANGELOG.md`, `docs/STATUS.md`,
   `docs/active/CONSOLGOV18_PHASE0_REVALIDATION_AND_D_O2_HANDOFF_2026-10-24.md`,
   `docs/active/INDEX.md`). No code, no tests, no config.
2. **The GOV-19 commit (the SHA this package binds) — SUBSTANTIVE:**
   - `scripts/g2_acceptance_battery.py`: ADD `manifest_exit_coverage()`
     + check `G2-C-v-exit` (addendum A1 predicate); ADD
     `parse_pytest_summary()` (G18-2 fix: warnings/seconds/skips now
     parsed correctly; satisfied logic unchanged); `verify_manifest()`
     docstring corrected. NO predicate weakened; verdict ceiling
     untouched (still literal `NOT_PASSED`).
   - `backend/tests/test_g2_acceptance_harness.py`: +10 regression tests
     (6 coverage states + 4 parser shapes); battery count moves
     658 → 668 passed (1 skipped, 2 warnings unchanged).
   - NEW `docs/active/OWNER_DELEGATED_DECISIONS_CONSOLGOV19_2026-10-24.md`
     (D-19-1, D-19-2 — recorded before edits), NEW
     `docs/active/R2_T6_ADDENDUM_A1_EVIDENCE_MANIFEST_EXIT_RULE_2026-10-24.md`,
     NEW `docs/active/CONSOLGOV19_EXECUTION_RECORD_2026-10-24.md`, NEW
     this package v3, `docs/STATUS.md` + `docs/CHANGELOG.md` +
     `docs/active/INDEX.md` updated.
   - Protected files (`config.py`, `app/api`, `ai2_governance.py`,
     `run_governance.py`): untouched (pins re-verified zero-drift).

Per the reviewed-SHA-fixing rule (T1): if you fix the reviewed SHA at this
package's commit, the delta above is INSIDE the review scope and no
re-review of v2-era material is needed. If the owner instead directs a
review at `75b7385`, the two commits above become a delta review requiring
an explicit scoping decision (T1).

## 5. Exact reviewer runbook (all commands from the repo root)

```bash
# 0. Fix and record the reviewed SHA
git rev-parse HEAD                      # record full 40-hex output
git status --porcelain | wc -l          # expect 4 untracked bootstrap dirs + evidence dirs

# 1. Corpus byte-identity (G2-C-iv)
sha256sum docs/governance/amendment_sources_2026-10-02/*.md
#   compare against the digests embedded in scripts/g2_acceptance_battery.py

# 2. Evidence-bundle integrity (G2-C-v) + A1 coverage (G2-C-v-exit)
cd docs/governance/evidence/raw/2026-10-24_consolgov19_atcommit
sha256sum -c SHA256SUMS.manifest        # expect every line OK
cd -

# 3. Freshness + implementation binding (G2-C-v-fresh / G2-C-v-impl / C-v-exit)
.venv/bin/python scripts/g2_acceptance_battery.py --json /tmp/reviewer_r1.json

# 4. Full battery reproduction at the reviewed SHA (G2-C-i, ~80 s)
( cd backend && ../.venv/bin/python -m pytest tests/ -q )
#   expect: 668 passed, 1 skipped, 2 warnings (1 skip = docs-only-since
#   honesty pair by HEAD shape; explain any other deviation)

# 5. Static + security set
.venv/bin/python -m pyflakes backend/app backend/tests scripts   # expect 0
.venv/bin/python -m compileall -q backend/app scripts && echo OK
.venv/bin/python -m pip_audit -r backend/requirements.txt --no-deps

# 6. Gate invariants in code (G2-C-iii-1/2/3, E4) + A1 addendum binding
grep -n 'ai2_enabled: bool = _env_bool("AI2_ENABLED", "0")' backend/app/core/config.py
grep -n 'verified = False' backend/app/core/config.py
grep -rni 'ai2' backend/app/api/ || echo "zero ai2 refs under app/api"
sha256sum docs/active/G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md
#   expect 1982af04… (v1.0 byte-identity; A1 is a separate document)

# 7. Entry criteria E1–E6 (checklist §9) + D-O1 predicate state
#    read the harness JSON checks array from step 3
```

## 6. What the implementing side does NOT claim

- No independent review has occurred. D-O2 NOT_APPOINTED; R-A1/R-A2 not
  obtained; E5 NOT_VERIFIED since GOV-10 §A9.
- The G2 verdict is **NOT_PASSED** and can only be moved by the owner at a
  convened review (charter 04:72 Role 1 A; register 05:148-150; D-AI-26;
  procedure T6). A green harness run is evidence, never a gate decision.
- The R2 v1.0 approval is a **delegated** approval (D-16-1) — recorded as
  such, not an owner personal signature. Addendum A1 is a **delegated**
  procedure amendment (D-19-1) under the v1.0 T6 versioning clause —
  recorded as such, not an owner personal signature.
- P3.43 gates 1–5 remain BLOCKED (Linux container / Windows target absent;
  repo venv has no playwright and the Windows-target condition is unmet
  regardless of the outer-venv playwright noted honestly in the GOV-19
  record; no Electron runtime; no live credentials, `live_verified=false`
  fail-closed; no push credentials — dry-run exit 128). The 48+-commit
  chain is local-only.
- The claimed "prior independent review with 14 findings" does NOT exist
  in this environment (BLOCKED_BY_MISSING_ARTIFACTS, GOV-18 §3 +
  GOV-19 `04_FINDINGS_RECONCILIATION.md`); do not treat GOV-17/18
  implementer-side audits as a substitute for this review (T4).

## 7. Findings, verdict, sign-off (procedure T5/T6)

- Classify findings per T5; implementer-side dispositions only within
  delegated authority; genuine re-review (T5 precedent) where required.
- Sign-off block exact form (GOV-6 #4): reviewed full SHA; procedure
  identity + version (v1.0 + A1); reviewer identity + acknowledgement
  date; E1–E6 outcomes; findings census; verdict recommendation to the
  owner; owner decision block (verdict + date + authority) — left EMPTY
  for the owner.
- The review report goes to `docs/governance/evidence/` (append-only) with
  the reviewed-SHA chain recorded in `docs/STATUS.md`.
