# OWNER-DELEGATED DECISIONS — CONSOL-GOV-19 — 2026-10-24

Status: **RECORDED (append-only; created BEFORE any code or doc edit of this
cycle).**

Authority: explicit owner delegation in the CONSOL-GOV-19 directive (§
Mission; § Phase 2 steps 4–7 authorizing a versioned T6 addendum when the
governance documents authorize a narrow, safely delegable decision; §
Non-Negotiable Invariants unchanged). These are **delegated, not personal,
owner decisions**, attributed to the delegated execution authority and
honestly labelled as such everywhere. Nothing here fabricates an independent
review, an owner personal signature, or an external validation.

Scope note (unchanged from GOV-16/17): the non-delegable acts are reviewer
identity/acts (D-O2, R-A1, R-A2, D-O3, D-O4), the G2 verdict itself,
live-provider authorization (R3), `AI2_ENABLED=1` outside tests (R4), push
execution, and **any weakening of an acceptance criterion**. Neither decision
below weakens any acceptance criterion; both are additive or
integrity-strengthening, and both are revertible by a single `git revert`.

---

## D-19-1 — T6 addendum A1: evidence-manifest `.exit` rule (G18-1) — APPROVED, DELEGATED

**Finding G18-1 (LOW, disclosed GOV-18, not self-repaired there).** R2 v1.0
T2 says "the manifest itself and per-command `.exit` files are excluded from
their own manifest (fixed-point impossibility)" — but every bundle manifest
since GOV-16 (2026-10-23) INCLUDES the `.exit` files (GOV-16: 20/20 present;
GOV-17/18/19: 28/28; verified this cycle). Historical audit this cycle:
CONSOL→GOV-15 bundles excluded `.exit` (0 in manifest, matching T2's
"established convention" at v0.1/v0.2 drafting time); the g2prep bundles
(2026-10-20) already included them (18); GOV-16 onward include all of them.

**Contract analysis (recorded in `03_EVIDENCE_CONTRACT_REVIEW.md`):**
1. `.exit` files are per-command exit-code sidecars (`<name>.exit` for each
   `<name>.txt` raw capture).
2. The fixed-point impossibility justifies ONLY the manifest's own
   self-exclusion; an `.exit` sidecar has no self-reference property.
3. Inclusion strictly STRENGTHENS the bundle: exit codes become
   tamper-evident under the same SHA-256 manifest; the T2 cross-validation
   mechanism (`.exit` vs `.txt`) is unaffected and remains required.
4. No historical bundle becomes unverifiable under either reading (verified
   this cycle: 43/43, 57/57, 60/60, 57/57, 61/61, 59/59 OK).
5. Authority: the rule lives in R2 (approved procedure v1.0, hash
   `1982af04…`); T6 provides its versioning mechanism ("amendments re-version
   and re-date the document" via owner-recorded decisions). The amendment
   corpus 00–06 is silent on `.exit` handling; no superior norm conflicts.

**Decision (delegated):** RESOLVE the contract in the
integrity-strengthening direction by a **versioned addendum**, NOT by editing
T2 in place and NOT by rewriting historical manifests:
1. New file `docs/active/R2_T6_ADDENDUM_A1_EVIDENCE_MANIFEST_EXIT_RULE_2026-10-24.md`
   (addendum A1, effective on adoption; R2 v1.0 file itself stays
   byte-untouched at hash `1982af04…`). A1 states: manifest self-exclusion
   mandatory (unchanged fixed-point rule); every `.exit` file present in the
   bundle directory MUST be listed in the bundle's manifest for bundles
   created on/after A1 adoption; `.exit` vs `.txt` cross-validation remains
   mandatory; mixed/ambiguous bundles (an `.exit` present but unlisted, or a
   manifest-listed `.exit` absent from the directory) are INVALID as
   A1-era evidence and must be regenerated or completed.
2. Migration/compatibility (in A1): bundles created before A1 remain valid
   under their era's convention and are never rewritten; their `.exit`
   values remain cross-validatable against `.txt` outputs; the machine
   predicate reports their state honestly (NONCOMPLIANT_MIXED for
   exclusion-era bundles is expected and is information, not retroactive
   invalidation, mirroring the T2 environment/time-dependent-findings
   clause).
3. Harness: ADD an additive predicate `manifest_exit_coverage()` reported as
   check id `G2-C-v-exit` (states: COMPLIANT / NONCOMPLIANT_MIXED /
   LISTED_EXIT_MISSING / NO_EXIT_FILES / NO_EVIDENCE_DIR_SELECTED), wired
   exactly like C-v/C-v-fresh/C-v-impl. The predicate is DATA for the
   reviewer; it never flips a gate, never changes the unconditional
   `NOT_PASSED` ceiling, and never relaxes C-v, C-v-fresh, or C-v-impl.
4. Regression tests in `backend/tests/test_g2_acceptance_harness.py`:
   compliant bundle → COMPLIANT; `.exit` present but unlisted →
   NONCOMPLIANT_MIXED (ok=False); manifest-listed `.exit` missing →
   LISTED_EXIT_MISSING (ok=False); no `.exit` files → NO_EXIT_FILES
   (vacuous ok=True); report-shape test updated to include `G2-C-v-exit`.

**Why safest:** the addendum resolves a real procedure/practice divergence
in the direction that makes evidence MORE tamper-evident; it weakens no
criterion, touches no protected file (`config.py`, `app/api`,
`ai2_governance.py`, `run_governance.py` untouched), is authorized by the
GOV-19 directive §Phase-2 explicitly, and follows the T6 versioning
mechanism with an owner-recorded (delegated) decision — the same path as
D-16-1. The v1.0 procedure text is preserved byte-exact so the reviewer can
diff A1 against it.

**Gate impact: NONE.** G2 stays NOT_PASSED; `AI2_ENABLED` stays 0;
`verified` stays False; R2 v1.0 approval state is not altered (A1 is an
addendum under the versioning clause, recorded here BEFORE any edit).

---

## D-19-2 — Harness cosmetic defect pair (G18-2 + docstring accuracy) — APPROVED, DELEGATED

**Finding G18-2 (INFO, disclosed GOV-18, not self-repaired there).**
`run_full_pytest()` regex `(\d+) passed(?:, (\d+) warnings?)?(?: in
([\d.]+)s)?` cannot capture the warnings/seconds groups when the pytest
summary contains an intervening ", N skipped" (actual summary: "658 passed,
1 skipped, 2 warnings in 78.14s") — `warnings` parses as 0 and `seconds` as
None. Zero predicate impact (satisfied uses exit_code + passed only; the
full summary line is preserved verbatim in `observed`), but the parsed
fields are silently inaccurate.

**Second item (same class, found re-verifying G18-1 this cycle).**
`verify_manifest()` docstring says "(self + .exit excluded by convention)"
— describing the superseded pre-GOV-16 convention, not the function's actual
behavior (it verifies every listed entry, whatever it is). Inaccurate
documentation on a governance-critical function.

**Decision (delegated):** FIX BOTH, minimally:
1. Extract the summary-line parsing into a pure function
   `parse_pytest_summary(line)` with a regex that tolerates the intervening
   skipped group: `(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) warnings?)?(
   ?: in ([\d.]+)s)?`; `run_full_pytest()` calls it. `passed` semantics
   unchanged; `warnings`/`seconds` become accurate; `skipped` is captured
   and reported (honesty improvement: skips become machine-visible, never
   relabelled).
2. Correct the `verify_manifest()` docstring to describe actual behavior
   ("verifies every entry listed in the manifest; the manifest itself is
   excluded by the fixed-point convention; `.exit` listing is governed by
   addendum A1 / check G2-C-v-exit").

**Why safest:** both are documentation-accuracy and parse-accuracy fixes in
one non-protected script (`scripts/g2_acceptance_battery.py`); no predicate
weakens (the satisfied logic is untouched; parse accuracy can only make the
report MORE faithful); skip counts become MORE visible, never less; both
revertible by one `git revert`. Regression tests pin the new parser
(including the exact GOV-16/17/18/19 summary shape) so a future regression
cannot silently reintroduce G18-2.

**Gate impact: NONE.** G2 stays NOT_PASSED; `AI2_ENABLED` stays 0;
`verified` stays False.

---

## Required validation before commit (both decisions)

1. Focused harness suite `test_g2_acceptance_harness.py` green with the new
   tests (expected: 32 + N new passed, 1 environment-conditional skip
   unchanged).
2. Full battery re-run at the dirty tree, then re-run at the commit
   (at-commit evidence bundle with manifest generated last).
3. pyflakes widened scope (`backend/app backend/tests scripts`) 0 findings;
   `git diff --check` clean; compileall 0.
4. Harness re-run R1 + R2-style (`--full-battery --evidence-dir` on the
   GOV-19 precommit bundle) at the new HEAD: verdict literal NOT_PASSED,
   harness_green False, C-v-exit COMPLIANT on A1-era bundles, all prior
   machine-checkable predicates unchanged.
5. Gates re-verified: `AI2_ENABLED=0` (config.py:109), `verified=False`
   (config.py:270), zero ai2 refs under `backend/app/api`; protected pins
   `39ef15cd…` / `6f320a49…` unchanged.
6. Staged exactly the reviewed files (NO `git add -A`); staged secret scan
   and staged `diff --cached --check` before commit.
