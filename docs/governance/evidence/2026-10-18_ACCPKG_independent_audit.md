# ACC-PKG Independent Read-Only Audit — 2026-10-18 (FAIL narrow → dispositioned)

Auditor: independent read-only sub-agent audit at commit `45f0b8b` (parent
`37c529d`), adversarial mandate. This file preserves the ORIGINAL FAIL verdict
verbatim (governance rule: audit history is never rewritten), followed by the
dispositions.

## Original verdict (verbatim)

**FAIL (narrow)** — driven solely by Findings 1 and 2 (two undispositioned
MEDIUM docs-accuracy defects in the new acceptance package / G2 matrix). No
CRITICAL findings; **no gate drift** (AI2_ENABLED=0, G2 NOT_PASSED,
live_verified=false, no route, no code change, FAIL history intact, no
owner-acceptance marking, no technology selected, no invented completion
state); commit shape, parentage, test counts, and the overwhelming majority of
file:line citations verified exact. Remediation is two one-line docs edits
(78.30s→78.24s; re-cite the focused run as the 5-file/164-passed run or
preserve the 62-run output) plus optionally the LOW pointer fixes — after
which the commit is PASS-worthy with no re-run of the battery required.

## Verified-clean summary (from the audit)

Commit integrity exact (8 files +710/−1, parent `37c529d`, zero application
code); battery counts recomputed (44+58+24+25+13=164 collected; full chain
496→512 consistent; `pytest_full.txt` = 512 passed / 2 warnings / 78.24s /
exit 0); 30+ file:line citation spot-checks all landed (incl.
`ai2_governance.py:91-93/234-241/354-385/407-422`, `config.py:109/191-196/214`,
`02`/`03`/D-AI corpus quotes verbatim); gates unchanged (AI2_ENABLED=0 at
`config.py:109`; zero contract-module imports in `app/api`+`app/services`; G2
NOT_PASSED; `live_verified=false`; LLM NOT EXECUTED); honesty clean (no
Windows/Py3.13/CLI claims; no owner-acceptance marking; no persistence
technology selected; no completion percentage); evidence SHA-256 8/8 recomputed
match.

## Findings and dispositions

| # | Severity | Finding | Disposition |
|---|---|---|---|
| ACCPKG-01 | MEDIUM | Battery duration mis-transcribed as "78.30s" in `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md:14` and `G2_EVIDENCE_MATRIX_2026-10-18.md:23` vs raw evidence 78.24s | **FIXED** in remediation commit ACC-PKGa — both lines corrected to 78.24s matching `pytest_full.txt` |
| ACCPKG-02 | MEDIUM | Focused-run row cites the 3-file command → "62 passed" but the preserved raw output was the 5-file run (164 passed); no raw output of the 62-run existed | **FIXED** — the 3-file focused run re-executed and preserved (`raw/2026-10-18_acceptance/pytest_focused_new_blocks_3file.txt`, 62 passed / 0.28s / exit 0, run context labeled post-`45f0b8b` docs-only delta) AND the row now cites both raw files (62-run + 164-run) |
| ACCPKG-03 | LOW | `G2_EVIDENCE_MATRIX:32` log citation "AI2-A/B/C/D/E only" — actual log shows AI2-A/B/C only (AI2-D/E docs-only); operative claim ("untouched since AI2-E") TRUE | **FIXED** — citation corrected to "AI2-A/B/C commits only — AI2-D/E were docs-only… unchanged since AI2-C" |
| ACCPKG-04 | LOW | Test-pointer drift: `test_ai2_f_governance.py:157-158` (blank; whitelist test is :90-94) and `:232-272` (first invalidation test starts :223) | **FIXED** — pointers corrected to `:84-87,90-94` and `:223-272` |
| ACCPKG-05 | LOW | Stale "19 ahead"/"Nineteen local commits" counters in untracked state file §7/§8 contradicting its own §1 (ahead 20) | **FIXED** — §7 row and §8 items 1/3 refreshed to ahead 20 incl. `45f0b8b` (untracked file; no commit needed) |
| ACCPKG-06 | LOW | Evidence fidelity: `00_evidence_sha256.txt` lists `00_context.txt` twice; compileall/pyflakes evidence is exit-code-only | **PARTIALLY FIXED** — manifest regenerated without the duplicate entry; exit-code-only form RETAINED for compileall/pyflakes as the honest raw form (clean runs produce empty output; noted here rather than fabricating stdout); the earlier preserved failed-first-invocation line in `bootstrap_validator.txt` is kept as honest history |
| ACCPKG-07 | INFO | Committed docs cite untracked `docs/governance/` evidence (bootstrap-policy hold) | Known project-wide condition, disclosed; resolves when the owner accepts the governance set |
| ACCPKG-08 | INFO | Pre-existing cosmetic defect `backend/tests/test_ai2_f_governance.py:87` malformed trailing comment (`# type: ignoreisc]`) — NOT introduced by `45f0b8b` | Out of scope for this docs-only block; queued for the next code-touching block (AI-4 contract layer) |

## Post-remediation status

All MEDIUM findings fixed and preserved-with-evidence; LOWs fixed or
explicitly dispositioned. The FAIL verdict above stands as history; per the
established re-audit rule, a delta re-check of the two corrected docs plus the
new evidence file suffices to flip the verdict on this block. No battery
re-run required (docs-only delta; application code untouched — verified by
`git diff 37c529d 45f0b8b --stat` touching only docs).
