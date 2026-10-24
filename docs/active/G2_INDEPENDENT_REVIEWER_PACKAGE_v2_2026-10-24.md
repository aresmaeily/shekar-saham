# G2 INDEPENDENT REVIEWER PACKAGE — v2 — 2026-10-24

Status: **REVIEWER-READY — awaiting one real, qualified, conflict-free
independent reviewer (D-O2). Nothing in this package appoints anyone,
fabricates a review, or implies any reviewer act has occurred.**

Supersedes: `G2_INDEPENDENT_REVIEWER_PACKAGE_DRAFT_2026-10-22.md`
(DRAFT, kept in place, append-only untouched) **for freshness only**.
Authority for this refresh: delegated decision D-17-2 in
`OWNER_DELEGATED_DECISIONS_CONSOLGOV17_2026-10-24.md`.

Binding: this file is part of the reviewed commit itself. The reviewed SHA
is the first commit containing this file:

```
git log --diff-filter=A --format=%H -- docs/active/G2_INDEPENDENT_REVIEWER_PACKAGE_v2_2026-10-24.md
```

and is cross-bound by the evidence bundle
`docs/governance/evidence/raw/2026-10-24_consolgov17_atcommit/SHA256SUMS.manifest`
(harness reports inside it record the exact commit they ran at).

---

## 1. Who may review (qualification — Q1–Q5, unchanged from the DRAFT)

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
   2026-10-23). SHA-256 at package time:
   `1982af04af6cf2f80aead76d313e7fe7e89b644b5c8c24117fa9becf9b1926ea`.
   You review the implementation against it; you may also challenge the
   procedure itself via findings (T5 rules).
2. **The reviewed SHA:** the commit identified above (HEAD at handoff).
3. **Evidence inventory:** all bundles under
   `docs/governance/evidence/raw/` (latest:
   `2026-10-24_consolgov17_battery_precommit/` and
   `2026-10-24_consolgov17_atcommit/`), each with SHA256SUMS.manifest.
4. **Gates and governance records:** `docs/STATUS.md` (top row),
   `docs/CHANGELOG.md` (top section), `docs/active/INDEX.md`,
   decision records `OWNER_DELEGATED_DECISIONS_CONSOLGOV16_2026-10-23.md`
   and `OWNER_DELEGATED_DECISIONS_CONSOLGOV17_2026-10-24.md`,
   the canonical amendment corpus
   `docs/governance/amendment_sources_2026-10-02/` (7 documents).
5. **Canonical criteria:** roadmap 02:7-11/32-37/200-204; boundaries
   03:61-66; charter 04:72 (Role 1 A — G2 verdict is the owner's alone);
   register 05:102-107/148-150/197-200; D-AI-26; checklist §8/§9/§11.

## 3. Exact reviewer runbook (all commands from the repo root)

```bash
# 0. Fix and record the reviewed SHA
git rev-parse HEAD                      # record full 40-hex output
git status --porcelain | wc -l          # expect 4 untracked bootstrap dirs + evidence dirs

# 1. Corpus byte-identity (G2-C-iv)
sha256sum docs/governance/amendment_sources_2026-10-02/*.md
#   compare against the digests embedded in scripts/g2_acceptance_battery.py

# 2. Evidence-bundle integrity (G2-C-v)
cd docs/governance/evidence/raw/2026-10-24_consolgov17_atcommit
sha256sum -c SHA256SUMS.manifest        # expect every line OK
cd -

# 3. Freshness + implementation binding (G2-C-v-fresh / G2-C-v-impl)
.venv/bin/python scripts/g2_acceptance_battery.py --json /tmp/reviewer_r1.json

# 4. Full battery reproduction at the reviewed SHA (G2-C-i, ~80 s)
( cd backend && ../.venv/bin/python -m pytest tests/ -q )
#   expect: 658 passed, 1 skipped, 2 warnings (1 skip = docs-only-since
#   honesty pair by HEAD shape; explain any other deviation)

# 5. Static + security set
.venv/bin/python -m pyflakes backend/app backend/tests scripts   # expect 0
.venv/bin/python -m compileall -q backend/app scripts && echo OK
.venv/bin/python -m pip_audit -r backend/requirements.txt --no-deps

# 6. Gate invariants in code (G2-C-iii-1/2/3, E4)
grep -n 'ai2_enabled: bool = _env_bool("AI2_ENABLED", "0")' backend/app/core/config.py
grep -n 'verified = False' backend/app/core/config.py
grep -rni 'ai2' backend/app/api/ || echo "zero ai2 refs under app/api"

# 7. Entry criteria E1–E6 (checklist §9) + D-O1 predicate state
#    read the harness JSON checks array from step 3
```

## 4. What the implementing side does NOT claim

- No independent review has occurred. D-O2 NOT_APPOINTED; R-A1/R-A2 not
  obtained; E5 NOT_VERIFIED since GOV-10 §A9.
- The G2 verdict is **NOT_PASSED** and can only be moved by the owner at a
  convened review (charter 04:72 Role 1 A; register 05:148-150; D-AI-26;
  procedure T6). A green harness run is evidence, never a gate decision.
- The R2 v1.0 approval is a **delegated** approval (D-16-1) — recorded as
  such, not an owner personal signature.
- P3.43 gates 1–5 remain BLOCKED (no Windows OS / no browser+playwright /
  no Electron runtime / no live credentials / no push credentials here);
  `live_verified=false` fail-closed; the 45+-commit chain is local-only.

## 5. Findings, verdict, sign-off (procedure T5/T6)

- Classify findings per T5; implementer-side dispositions only within
  delegated authority; genuine re-review (T5 precedent) where required.
- Sign-off block exact form (GOV-6 #4): reviewed full SHA; procedure
  identity + version; reviewer identity + acknowledgement date; E1–E6
  outcomes; findings census; verdict recommendation to the owner.
- The review report goes to `docs/governance/evidence/` (append-only) with
  the reviewed-SHA chain recorded in `docs/STATUS.md`.
