# R2 T6 ADDENDUM A1 — Evidence-Manifest `.exit` Rule — 2026-10-24

Procedure identity: G2 REVIEW PROCEDURE — FINAL (R2), approved v1.0
2026-10-23, file
`docs/active/G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md`,
SHA-256 `1982af04af6cf2f80aead76d313e7fe7e89b644b5c8c24117fa9becf9b1926ea`.

Status: **ADOPTED — ADDENDUM A1 (delegated owner decision D-19-1,
2026-10-24, recorded in
`docs/active/OWNER_DELEGATED_DECISIONS_CONSOLGOV19_2026-10-24.md` BEFORE
any edit).** Versioning authority: R2 §T6 ("this procedure, once approved,
is versioned (v1.0 at approval), change-controlled through owner-recorded
decisions … amendments re-version and re-date the document"). A1 amends the
**T2 evidence-manifest rule** only. The R2 v1.0 file itself is NOT modified
and remains byte-identical to `1982af04…`; this addendum is the versioned
amendment document. With A1, the procedure's effective T2 rule text is
v1.0-T2 **as amended by A1**; every other section (T1, T3–T6, Annex A,
Annex B) is unchanged.

Effective date: **2026-10-24 (adoption).** Rule applicability is
date-of-bundle-creation based (see §Migration).

---

## 1. Problem being resolved (finding G18-1, LOW, disclosed CONSOL-GOV-18)

T2 (v1.0) reads, in the part concerned here:

> "…protected by a SHA-256 manifest; the manifest itself and per-command
> `.exit` files are excluded from their own manifest (fixed-point
> impossibility); `.exit` values are cross-validated against the
> hash-protected `.txt` outputs — the established repository convention."

Practice diverged from that sentence: every bundle manifest since
CONSOL-GOV-16 (2026-10-23) INCLUDES the `.exit` files (GOV-16: 20/20 of the
`.exit` files present; GOV-17: 28/28 in two bundles; GOV-18: 28/28 in two
bundles; GOV-19: 28/28 — all verified `sha256sum -c` OK this cycle).
Historical audit: CONSOL→GOV-15 manifests excluded `.exit` (0 entries),
matching the convention at T2's drafting time; the g2prep bundles
(2026-10-20) already included them (18 entries). The v1.0 text therefore
describes a superseded convention, and its stated rationale does not cover
the practice that replaced it.

## 2. Contract analysis (binding findings)

1. **What `.exit` files are.** A `.exit` file (`<name>.txt.exit`, stored as
   `<name>.exit`) is the per-command exit-code sidecar of exactly one raw
   capture `<name>.txt` in the same evidence directory. It is written once,
   at execution time, by the capture harness.
2. **The fixed-point impossibility covers ONLY the manifest itself.** A
   manifest cannot contain its own digest; that argument has no analogue
   for an `.exit` sidecar, which is a distinct file with no
   self-reference property. Listing `alpha_env.exit` in the manifest
   creates no paradox.
3. **Inclusion strengthens the bundle; it changes nothing else about the
   bundle's meaning.** Under exclusion, an `.exit` value is protected only
   indirectly, via T2's cross-validation against the hash-protected
   `.txt`. Under inclusion, the `.exit` value is itself hash-protected:
   any tampering is cryptographically detectable by `sha256sum -c`
   directly, in addition to cross-validation. The qualifying-artifact
   definition (raw captures with exit codes and UTC timestamps,
   append-only directories, SHA-256 manifest) is unchanged; the bundle
   proves the same facts, more strongly.
4. **No existing bundle is invalidated.** `sha256sum -c` verifies exactly
   the listed entries. Exclusion-era bundles verify OK (their `.exit`
   values remain cross-validatable against `.txt` outputs, the original
   T2 mechanism); inclusion-era bundles verify OK. Verified this cycle:
   GOV-16 43/43, GOV-17 57/57 + 60/60, GOV-18 57/57 + 61/61, GOV-19
   59/59.
5. **Authority.** The evidence-manifest rule is defined by R2 T2; R2 §T6
   supplies the amendment mechanism used here. The amendment corpus
   (documents 00–06) imposes no conflicting norm (it is silent on
   `.exit` handling). No acceptance criterion is weakened by this
   addendum; the evidence contract is strictly tightened.

## 3. Resolved rule (normative)

For every evidence bundle created **on or after** the effective date:

- **A1-R1 (self-exclusion, unchanged).** `SHA256SUMS.manifest` MUST NOT
  list itself (fixed-point rule, carried over from v1.0 T2 unchanged).
- **A1-R2 (`.exit` coverage, mandatory).** Every `.exit` file present in
  the bundle directory MUST be listed in the bundle's
  `SHA256SUMS.manifest`. Partial listing (some `.exit` files listed,
  others not) is prohibited.
- **A1-R3 (no phantom entries).** Every `.exit` file listed in the
  manifest MUST exist in the bundle directory. (General manifest
  integrity — listed entries must match — already follows from
  `sha256sum -c`; this clause makes the `.exit` case explicit.)
- **A1-R4 (cross-validation retained).** T2's cross-validation of `.exit`
  values against the `.txt` outputs remains mandatory; hash protection is
  additive to it, not a replacement.
- **A1-R5 (mixed/ambiguous bundles are invalid as A1-era evidence).** A
  bundle that violates A1-R2 or A1-R3 is an invalid evidence bundle for
  work performed after the effective date: it must be regenerated or
  completed (re-listing and re-verifying the whole bundle) before it may
  be relied on. It is NOT acceptable to "spot-verify" a mixed bundle.

Machine reporting: the G2 acceptance harness reports bundle state as check
`G2-C-v-exit` (additive predicate `manifest_exit_coverage`): `COMPLIANT` /
`NONCOMPLIANT_MIXED` / `LISTED_EXIT_MISSING` / `NO_EXIT_FILES` /
`NO_EVIDENCE_DIR_SELECTED`. The predicate is data for the reviewer; it
never flips a gate and never relaxes `G2-C-v`, `G2-C-v-fresh`, or
`G2-C-v-impl`.

## 4. Migration and backward compatibility

- **Historical bundles are never rewritten.** Bundles created before the
  effective date remain valid under the convention of their era. A
  pre-A1 bundle reporting `NONCOMPLIANT_MIXED` on `G2-C-v-exit` is
  expected (its `.exit` files are deliberately unlisted); this is
  information for the reviewer, not retroactive invalidation — mirroring
  the v1.0 T2 principle that environment/time-dependent findings are
  recorded and classified without invalidating correctly-labelled earlier
  evidence.
- **Verification command is unchanged.** `sha256sum -c SHA256SUMS.manifest`
  inside the bundle directory remains the verification procedure for all
  eras.
- **Reviewer guidance.** For any bundle, the reviewer verifies (i)
  `sha256sum -c` OK for listed entries; (ii) for A1-era bundles,
  `G2-C-v-exit = COMPLIANT`; (iii) for pre-A1 bundles, `.exit` values
  cross-validate against `.txt` content (T2 mechanism).

## 5. Provenance

- Finding: G18-1 (CONSOL-GOV-18, LOW, disclosed and NOT self-repaired
  there).
- Decision: D-19-1 (delegated, not personal; CONSOL-GOV-19 directive
  §Phase-2 authorizes exactly this narrow act; recorded BEFORE any edit).
- Historical facts audited this cycle (2026-10-24, HEAD `300ca7a…`):
  manifest-level `.exit` census across all 70+ bundles in
  `docs/governance/evidence/raw/` (see `03_EVIDENCE_CONTRACT_REVIEW.md`
  §3 for the full table).
- Regression tests: `backend/tests/test_g2_acceptance_harness.py`,
  class `TestManifestExitCoverage` (compliant / mixed / phantom /
  vacuous / report-shape cases).
