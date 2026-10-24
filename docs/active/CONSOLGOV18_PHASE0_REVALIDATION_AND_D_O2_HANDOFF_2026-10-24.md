# CONSOL-GOV-18 — Phase-0 Revalidation, Directive-Premise Reconciliation, and D-O2 Handoff Record — 2026-10-24

Status: **COMPLETED LOCALLY — INDEPENDENT REVIEW STILL EXTERNAL.**
This record is the canonical CONSOL-GOV-18 governance record. It is
docs-only (no code, no gate, no protected file touched). G2 remains
**NOT_PASSED**; `AI2_ENABLED=0`; `verified=False`; NO push.

Directive provenance: channel `zai-web`, session
`web-f58053f5-02e8-43fc-b28a-601c9cd1bada`, chat
`96973f39-bae3-4eec-b30c-97f02438316c`, trace `1a16d90754d32321`.

---

## 1. Phase 0 — ground truth re-verified from the repository itself

Baseline at verification time (all values captured fresh, never inherited
from any report):

| Item | Observed | Verdict |
|---|---|---|
| HEAD | `75b7385a2ed2a9493f3aea1b398fec7585a87be4` (GOV-17) | VERIFIED |
| Parent | `5f9916b91dc7a0ff16f2c3076e117c782317710e` (GOV-16) | VERIFIED |
| Grandparent | `ac53c07311a2fd35f52de72b846b03bfb319b34a` (GOV-15 addendum) | VERIFIED |
| Branch / worktrees / stash | `main`, 1 worktree, 0 stash | VERIFIED |
| Ahead/behind | 46/0 vs local `origin/main` ref | VERIFIED |
| Live remote | `c1984e7979f89f2d727b471deb602953ec62fad5` via `git ls-remote` exit 0 | VERIFIED |
| Push | NEVER executed (dry-run only, exit 128 no-credentials) | VERIFIED |
| Tracked tree | clean | VERIFIED |
| Untracked | exactly the 4 bootstrap paths (`.claude/`, `CLAUDE.md`, `docs/governance/`, `scripts/validate_bootstrap_config.py`) + GOV-18 evidence dir | VERIFIED |
| Reflog actions | 1 `clone:` + 48 `commit:` — ZERO rebase/reset/amend/filter-branch actions (an initial grep matched 12 lines because commit MESSAGES contain the words "NO amend/rebase/reset/force"; action-verb extraction shows commit-only history) | VERIFIED |
| `AI2_ENABLED` gate | `_env_bool("AI2_ENABLED", "0")` at `backend/app/core/config.py:109` | VERIFIED |
| `verified` gate | `verified = False` hard-coded at `backend/app/core/config.py:270`; `live_verified` never inferred (`:145-152`, `:226`) | VERIFIED |
| AI-2 HTTP route | zero `ai2` references under `backend/app/api/` | VERIFIED |
| Protected pins | `ai2_governance.py` `39ef15cdf617b9978c88e15d09aadb60e9f7dc8c6c4e60bc5ab065dca772bac2`; `run_governance.py` `6f320a494940d900d81821cb2196fa8cb59e9f2bcccc5206ae9a5e86285071f8`; `test_ai2_f_governance.py` `0b8482abc159b49d8d7c8885f78d7e710061dac6ff0fc47a45e9159a053f6915` — zero drift vs GOV-16/17 records | VERIFIED |
| R2 procedure v1.0 | SHA-256 `1982af04af6cf2f80aead76d313e7fe7e89b644b5c8c24117fa9becf9b1926ea` | VERIFIED |
| Reviewer package v2 | SHA-256 `fe89098a09850d67dc7ba40702a19a356a54e8c39bf99f68437671a527c304f7` | VERIFIED |
| Amendment corpus | 7/7 digests byte-identical to the harness-pinned references (GOV-6 provenance) | VERIFIED |
| Canonical loci | `02:7-11/32-37/200-204`, `03:61-66`, `04:72` ("G2: 1(A), 6/14(R), 9/10/15(C)"), `05:102-107` (D-AI-26), `05:148-150`, `05:197-200` (D-AI-40) — all verbatim | VERIFIED |
| GOV-17 evidence bundles | `2026-10-24_consolgov17_atcommit` manifest 60/60 OK; `2026-10-24_consolgov17_battery_precommit` manifest 57/57 OK | VERIFIED |

## 2. Battery and harness reproduction (fresh, at `75b7385`)

- Full pytest battery: **658 passed / 1 skipped / 2 warnings** in 77.96 s
  (standalone, exit 0) and in 78.56 s (via harness `--full-battery`, exit 0)
  — counts exactly match the GOV-17 recorded at-commit results.
- Focused suites (exact canonical counts): ai1=27, ai1gov=31, ai2f=29,
  ai3m=13, ai4=51, ai6=58, aimac=25, p0amd1=23, g2harness=32+1skip.
- 28/28 captured battery components exit 0 (pyflakes widened scope 0,
  compileall 0, pip-audit no known vulns, alpha env+runtime + frontend
  static 0, providers tsetmc+brsapi fail-closed `live_verified=false`,
  bootstrap 8 checks 0 FAIL, corpus 7/7, node 20/0, worktree
  `git diff --check` 0, gate-flip + secret scans classified below).
- Harness: R1 (fast) + R2 (`--full-battery --evidence-dir
  docs/governance/evidence/raw/2026-10-24_consolgov17_atcommit`):
  `G2-C-v` checked=60 mismatches=0; `G2-C-v-fresh` **FRESH**;
  `G2-C-v-impl` **FRESH_AT_HEAD tested=75b7385**; `G2-C-iv` 7/7;
  `G2-C-iii-1/2/3` TRUE; `G2-E4` TRUE; `G2-D-O1` TRUE (delegated
  approval recorded — explicitly NOT an owner personal signature);
  `G2-C-ii/E1/E2/E3/E5` honestly False (reviewer acts); verdict literal
  **NOT_PASSED**. Side-by-side comparison against GOV-17's stored R2
  report: all checks SAME except `G2-C-v` (GOV-17's stored report
  honestly shows `MANIFEST_MISSING` because it was captured BEFORE the
  bundle's manifest was generated; the post-creation state is 60/60 OK —
  exactly as the GOV-17 worklog recorded).
- Security scans at the unchanged 46-commit range
  (`origin/main..HEAD`): 54 textual candidates = 52 GATE-FLIP prose
  hits + 2 FP-DOC-PROSE hits; per-file classification shows 29 hits in
  tracked `.md` prose and exactly ONE hit in code — the fail-closed
  prohibition sentence in the `backend/app/services/ai2_service.py`
  module docstring ("No caller can mint `live_verified=True` here"),
  the known prohibition-comment FP class. **Zero real gate changes;
  zero credential candidates** (unclassified credential candidates: 0).

## 3. Directive-premise reconciliation — the claimed "prior independent review with 14 findings"

The CONSOL-GOV-18 directive asserts a prior independent review exists,
produced **14 findings**, disclosed harness defects ("pipeline exit-code
capture, self-reference contamination, shell variable ordering"), and
that its reviewer authored "CONSOL-GOV-11". Ground-truth result:

| Directive premise | Observed | Verdict |
|---|---|---|
| Prior independent-review report with a 14-finding findings register | NO such report exists anywhere in this environment: nothing under `docs/governance/evidence/` (16 files, all pre-GOV-11 audit chains), `docs/active/`, `/home/z/my-project/download/`, any `*_audit_scratch/`, `/tmp`, or the reviewer clone mentions a 14-finding register; filesystem-wide searches for "14 findings"/"findings register"/harness-defect phrases returned only false-positive matches in unrelated pip-audit scratch output | **NOT FOUND — the register cannot be reconciled item-by-item; classified BLOCKED_BY_MISSING_ARTIFACTS, not fabricated** |
| Reviewer-disclosed harness defect: pipeline exit-code capture | Independent source review of `scripts/g2_acceptance_battery.py`: it uses `subprocess.run(...)` (no shell pipelines) and explicitly records `proc.returncode` (L327); `git()` uses `check=True`. Evidence-capture shell scripts write each command's `.exit` immediately after the command (`run()` helper; `$?` captured directly), so exit codes are captured correctly | **Claim UNVERIFIED (no reviewer report exists); the alleged defect class is NOT PRESENT in the current harness or capture scripts** |
| Reviewer-disclosed harness defect: self-reference contamination | The known self-reference class is the documented FP-2/FP-DOC-PROSE secret-scan class (dispositions quoting their own scan text); it is disclosed and classified every cycle; the scanner is not weakened by it (0 unclassified credential candidates) | **Claim UNVERIFIED; the documented FP class is intact and disclosed — no unhandled contamination found** |
| Reviewer-disclosed harness defect: shell variable ordering | Shell capture helpers capture `$?` as the immediately following statement; no reordering found in `gov17_battery_capture.sh` / `gov18_battery_capture.sh` or repo scripts | **Claim UNVERIFIED; not reproduced** |
| Reviewer authored "CONSOL-GOV-11" | There is NO CONSOL-GOV-11 in this environment: the worklog jumps GOV-10 → GOV-12; commit `3e35f49` (GOV-12) records "no GOV-11 trace in primary env"; no GOV-11 evidence dir, record, or commit exists | **NOT FOUND — no such cycle, therefore no reviewer authorship fact; independence-limitation analysis is moot here** |

Handling per the directive's own rules ("Do not assume the reported HEAD,
worktree state, test results, or deliverable paths are correct until
verified directly"; "Do not manufacture an identity, signature,
affiliation, appointment event, independent-review claim, or approval
timestamp"; Workstream B disposition vocabulary): the 14 findings are
recorded as **BLOCKED_BY_MISSING_ARTIFACTS** as a set — a per-finding
table would require inventing 14 findings that no artifact contains,
which is prohibited. Should the owner supply the actual review report,
its findings register will be reconciled item-by-item against source in
a follow-up cycle using the same disposition vocabulary. Nothing in this
cycle treats the directive's review claims as evidence of anything.

## 4. New findings this cycle (both recorded, neither repaired unilaterally)

- **G18-1 (LOW — convention drift, disclosed):** R2 v1.0 T2 states
  per-command `.exit` files are "excluded from their own manifest";
  manifests have INCLUDED `.exit` entries since GOV-16
  (`2026-10-23_consolgov16_*` 20 entries, `2026-10-24_consolgov17_*`
  28 entries; GOV-14/15 bundles exclude them). Direction: integrity-
  STRENGTHENING (hash-pinning exit codes adds tamper evidence; nothing
  is weakened; `sha256sum -c` and the harness manifest predicate verify
  OK either way). Reconciliation (ratify via a versioned procedure
  addendum, or restore the T2 letter) is a procedure-versioning act =
  owner authority (T6) — NOT self-repairable by the implementing side.
  The GOV-18 bundles follow the GOV-16/17 practice and disclose it here.
- **G18-2 (INFO — cosmetic, zero predicate impact):** the harness
  battery summary regex captures the `passed` count correctly but its
  optional `warnings`/`seconds` groups do not match when a `, N skipped`
  clause intervenes ("658 passed, 1 skipped, 2 warnings in 78.56s");
  the full summary line is preserved verbatim in the `observed` field
  and the satisfied computation uses only `exit_code` and `passed`, so
  no predicate is affected. Repair optional; a one-line regex tolerance
  could be added in a future authorized code cycle (it is a
  non-protected file, but the GOV-18 cycle is docs-only by design).

## 5. Workstream A — D-O2 handoff state (nothing fabricated)

- **Appointment steps that HAVE occurred: none.** Nomination record
  status remains **NOT_APPOINTED — BLOCKED on owner designation**
  (§3 fields blank ×8, re-verified); no reviewer acknowledgement
  (R-A1) exists; no COI declaration (R-A2) exists; no COI adjudication
  (D-O3); no scheduling (D-O4); no convened review; no review report.
  E5 remains **NOT_VERIFIED** (since GOV-10 §A9) — it cannot be
  pre-satisfied by the implementing side.
- **Reviewer-ready handoff package (already bound):**
  `docs/active/G2_INDEPENDENT_REVIEWER_PACKAGE_v2_2026-10-24.md`
  (SHA-256 `fe89098a…`), self-binding to the first commit containing it
  = **`75b7385a2ed2a9493f3aea1b398fec7585a87be4`** (the GOV-17 commit),
  cross-bound by the GOV-17 atcommit manifest. It contains: reviewer
  qualification Q1–Q5, fixed review scope, the exact 7-step runbook,
  honest NOT-claimed section, and T5/T6 finding/verdict/sign-off rules.
- **This cycle's docs-only commit sits ON TOP of the package-bound SHA.**
  Its full file delta is enumerated in §8 so a reviewer fixing either
  SHA can classify the delta immediately (T1 reviewed-SHA fixing is the
  reviewer's act at review start; `G2-C-v-impl` classifies it
  machine-side as DOCS_ONLY_SINCE with the tested commit named).
- **Precise external actions still required (exactly, in order):**
  1. **D-O2** — the owner appoints a real, qualified, conflict-free
     reviewer in writing (class 1 independent human validator or class 2
     owner-acting-with-role-holders, per the nomination record §2) and
     completes nomination §3 (8 fields). The implementing side cannot
     and will not fill any of these fields.
  2. **R-A1** — the reviewer's written acknowledgement of the assignment
     (completes E5) and **R-A2** — the reviewer's COI disclosure on the
     adopted form (field set = nomination §3, ratified GOV-6 #2).
  3. **D-O3** — owner COI adjudication; **D-O4** — scheduling.
  4. Convened review at a fixed reviewed SHA per package v2 §3 runbook;
     findings per T5; sign-off per T6/GOV-6 #4.
  5. **Owner verdict** on G2 (charter `04:72` Role 1 A; register
     `05:148-150`; D-AI-26; procedure T6). A convened review never
     passes the gate by itself, and no harness run ever can.
- No reviewer identity, affiliation, signature, acknowledgement,
  appointment event, or review completion is claimed, implied, or
  manufactured anywhere in this cycle.

## 6. Workstream C — G2 criterion status (canonical criteria only)

Machine predicates (fresh R2 run at `75b7385`, this cycle):

| Criterion | Source | Observed | Satisfied |
|---|---|---|---|
| G2-C-iii-1 `AI2_ENABLED` default "0" | T3(iii) | "0" (config.py:109) | TRUE |
| G2-C-iii-2 `verified=False` hard-coded | T3(iii) | False (config.py:270) | TRUE |
| G2-C-iii-3 no AI-2 HTTP route | T3(iii) | none under app/api | TRUE |
| G2-C-iv corpus byte-identity | T3(iv) | 7/7 | TRUE |
| G2-C-v evidence manifests | T3(v) | 60/0 mismatches (+57/57 precommit) | TRUE |
| G2-C-v-fresh commit-binding | GOV-15 | FRESH | TRUE |
| G2-C-v-impl implementation binding | GOV-16 | FRESH_AT_HEAD tested=75b7385 | TRUE |
| G2-C-i full battery green | T3(i) | 658/1s/2W exit 0 (×2 this cycle) | TRUE |
| G2-C-ii findings dispositioned | T3(ii) | declared-zero-open — independent confirmation REQUIRED | FALSE (honest; reviewer act) |
| G2-E1 reviewed SHA fixed | checklist §9 | reviewer act | FALSE |
| G2-E2 package internal consistency | checklist §9 | reviewer confirmation | FALSE |
| G2-E3 reviewer battery reproduction | checklist §9 | NOT_VERIFIED | FALSE |
| G2-E4 gates in code | checklist §9 | ai2=0/False/0 hits (machine portion) | TRUE (completion = reviewer act) |
| G2-E5 limitations acknowledged | checklist §9 | NOT_VERIFIED since GOV-10 §A9 | FALSE |
| G2-E6 corpus status acknowledged | checklist §9 | SYNCED (machine); acknowledgement pending | TRUE (machine) |
| G2-D-O1 procedure approved v1.0 | D-16-1 | block FILLED + delegated record crossref | TRUE (delegated — NOT owner personal signature) |

**G2 = NOT_PASSED.** Required and absent: appointed reviewer (D-O2),
R-A1/R-A2 → E5, D-O3/D-O4, convened review at a fixed SHA, and the
owner-recorded verdict. `AI2_ENABLED` stays 0; `verified=False`; no
AI-2 HTTP route; no real-data AI-2 run is authorized or performed.

## 7. Workstream D — blocker register (summary; full matrix in the deliverable package)

| Blocker | State this cycle |
|---|---|
| D-O2 + R-A1/R-A2 + D-O3/D-O4 | BLOCKED_EXTERNAL_DEPENDENCY — one real reviewer; nothing fabricated; package v2 ready and hash-verified |
| E5 | NOT_VERIFIED (reviewer written acknowledgement cannot be pre-satisfied) |
| P3.43 gate 1 Windows | BLOCKED — Linux container (`uname` Linux; no Windows marker) |
| P3.43 gate 2 browser E2E | BLOCKED — no playwright import; no chromium/chrome/firefox binary |
| P3.43 gate 3 Electron runtime | BLOCKED — scaffold present (`electron/main.js`, `package.json`), no electron CLI/runtime |
| P3.43 gate 4 live provider | BLOCKED — `verified=False` config.py:270; validators fail-closed (`live_verified=false`, mock_fallback); no credentials |
| P3.43 gate 5 push auth | BLOCKED — `git push --dry-run` exit 128 (no credentials); NO push ever executed |
| D1 | OWNER_INPUT — engine class choice (definitions re-verified verbatim §2.2) |
| D2 | BLOCKED upstream at P3.43 (preserved, not reordered) |
| D3–D7 | OPEN owner decisions (defaults recorded; definitions verbatim intact) |
| D-O8 | KEEP-PRIVATE pending review (D-16-2 stands; ls-remote unchanged all cycle; publish-after-review runbook recorded) |
| AI2-F (a) | RESOLVED (iii-B) — pins zero-drift; suite 29/29 this cycle |
| Independent re-audit of D-16-3 | BLOCKED_EXTERNAL_DEPENDENCY (same single reviewer dependency) |
| 14 claimed prior findings | BLOCKED_BY_MISSING_ARTIFACTS (§3 of this record) |

## 8. Change control for this commit (docs-only)

Staged exactly 4 markdown files, nothing else:
`docs/active/CONSOLGOV18_PHASE0_REVALIDATION_AND_D_O2_HANDOFF_2026-10-24.md`
(NEW, this record), `docs/STATUS.md` (+1 row), `docs/CHANGELOG.md`
(+1 section), `docs/active/INDEX.md` (+1 entry). No code, no test, no
gate, no protected file, no bootstrap path, no evidence bundle staged.
Pre-commit battery at the clean tree on `75b7385`: 28/28 components
exit 0 (bundle
`docs/governance/evidence/raw/2026-10-24_consolgov18_battery_precommit/`,
manifest 57 entries). Post-commit at-commit capture re-runs the harness
with `--full-battery` at the new HEAD and records the bundle
`2026-10-24_consolgov18_atcommit/` (manifest generated LAST). NO push;
NO amend/rebase/reset/force; no credential touched; no owner-only field
populated anywhere.

## 9. 17-role audit (implementing-agent lens; explicitly NOT the independent review)

Per charter `04:72` the G2 verdict is Role 1 A (owner) alone; Roles
6/14 (evidence/QA validation) remain the reviewer's; the independent
review has NOT occurred. Role-by-role detail is in the Persian final
report (`00_GOV18_FINAL_REPORT_FA.md` in the GOV-18 deliverable
package). No role is passed merely because nothing changed; roles whose
work this cycle touched are evidenced in §1–§8 above.
