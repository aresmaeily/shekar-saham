# AI-6 EXECUTION RECORD — UNTRUSTED-CONTENT BOUNDARY AND INJECTION-ISOLATION CONTRACT LAYER

Status: COMPLETE at the pre-G2 contract class (owner directive 2026-10-19,
Decision R2). Independent audit: see `docs/governance/evidence/
2026-10-19_AI6_independent_audit.md` (appended after this record was
committed; verdict recorded in §6 below). Gates unchanged: `AI2_ENABLED=0`
(config.py:109), G2 NOT_PASSED, `live_verified=false`, LLM NOT EXECUTED,
no route, no push. D-AI-29 remains DEFERRED BY GATE — this block delivers
the boundary-set contracts; it does not flip the gate.

## 1. Baseline and authorization

- Started from HEAD `cc98c64` (AI-4a) on `main`; tracked tree clean;
  ahead 23 / behind 0 vs live `origin/main` `c1984e7` (ls-remote exit 0);
  stash 0; single worktree; the four untracked bootstrap paths intact.
- Fresh-baseline verification reconfirmed the AI-4 acceptance chain (R1 of
  the directive): both AI-4 commits verified in actual history; scope
  matrix present; every FAIL-audit finding has a documented disposition
  (AI4-01..05 FIXED, AI4-06..08 ACCEPTED) and the delta re-audit supports
  PASS; independent spot-checks this cycle found no remaining defect.
- Authorization: owner directive R2 (complete AI-6 contract block) +
  dependency matrix "Authorized NOW: untrusted-content boundary +
  injection-isolation CONTRACT design; source-class admission schema
  extension" + `02:202` pre-G2 class. No owner decision required to start
  (`05` §Engineering authority).

## 2. Scope derivation (published BEFORE implementation)

`docs/active/AI6_SCOPE_DERIVATION.md` — official definition from
`02:97-100`, `02:161-170`, `03:73-76`, D-AI-29, `06:88-90`,
`02_PRODUCT:120,126`; reuse audit (evidence.py / source_registry.py /
run_governance.py consumed; grep-verified zero duplication); traceability
matrix R1–R17 with per-requirement corpus loci; out-of-scope list (no
network ingestion, no crawl, no provider contact, no LLM, no runtime);
unresolved register (source-class admissions, Two-Key operational
parameters, credentials — owner decisions).

## 3. Implementation (additive; no existing module modified)

`backend/app/domain/external_intelligence.py` (880 lines; frozen,
deterministic, clock-free; imports only stdlib + pydantic +
`app.domain.{evidence,run_governance,source_registry}`):

- Closed vocabularies: `TrustLabel=Literal["UNTRUSTED"]` (no trusted
  content expressible); `ContentKind` (exactly 02:164-165 kinds);
  `TrustBoundaryFlow` (four content-side flows allowed; TOOL_EXECUTION /
  PRODUCTION_MUTATION / AUTONOMOUS_ACTION exist only as structurally
  refused members); `InjectionFindingKind` taxonomy (DIRECT_INSTRUCTION,
  INSTRUCTION_CONFLICT, TOOL_INVOCATION_ATTEMPT, PRIVILEGE_ESCALATION,
  OBFUSCATED_INSTRUCTION, NONE_DETECTED); `QuarantineReason`;
  `SourceClassAdmissionState=Literal["PENDING_OWNER_DECISION"]`.
- `assert_boundary_allowed()` — deterministic flow gate; forbidden flows
  raise with the flow name in the code.
- `UntrustedContentEnvelope` — mandatory hex-64 `content_sha256`, source
  tier from the canonical SourceTier vocabulary, UTC discipline, no
  credential field (03:85-88), trust label locked.
- `ContentSegmentation` + `EmbeddedInstructionCandidate` — content-
  instruction separation; `executable: Literal[False]` (untrusted content
  is never executable; 03:19-25; 06:89); bounded excerpts; candidate
  discipline (same content, distinct ids).
- `InjectionScanRecord` — recorded deterministic scan results;
  NONE_DETECTED must stand alone; duplicates refused; `has_findings`.
- `InstructionConflictRecord` — resolution locked to
  `GOVERNED_INSTRUCTION_PRECEDENCE` + disposition `QUARANTINED`;
  compliance with content-borne instructions unrepresentable.
- `QuarantineEvent` + `QuarantineLedger` — append-only (no update/delete/
  invalidate path; with_event returns a NEW ledger); QUARANTINE requires a
  closed-taxonomy reason and carries no release decision; RELEASE/DISCARD
  requires a named human `decided_by` + `decision_ref` (03:76); scope
  semantics (content-level covers instruction-level).
- `TwoKeyAuthorization` + `KeyGrant` — two DISTINCT human authorizers
  mandatory (same identity refused); action-bound; operational parameters
  remain owner decisions (unresolved register).
- `SourceVerificationRecord` — verification evidence contract (03:75).
- `SourceClassControls` — the dependency-matrix "source-class admission
  schema extension": per-tier control declarations (verification / scan /
  two-key) with `admission_state` locked to PENDING_OWNER_DECISION and
  `requires_injection_scan=False` structurally refused (scan cannot be
  waived).
- `AdvisoryInterpretationRequest` — evidence-reference-only reasoning
  request (02_PRODUCT:120); mandatory citations (>=1 evidence id); no
  write-authority field exists (structural absence).
- Gate functions (deterministic, fixed refusal-code order, mutate
  nothing): `external_intake_gate` (source registration, class controls,
  verification requirement, run binding, provenance completeness via
  `missing_required_provenance(..., additionally_required=("dataset_version",))`,
  autonomy ceiling via `assert_autonomy_permitted`, findings block);
  `evidence_filing_gate` (provenance preservation against the canonical
  EvidenceItem: source + document hash must match the envelope; VERIFIED
  trust requires a verification record; findings/quarantine block);
  `injection_response_gate` (findings ⇒ active quarantine required);
  `quarantine_release_gate` (two-key enforcement where the class controls
  require it); `advisory_interpretation_gate` (unknown/quarantined refs
  refused); `governed_external_intake` (end-to-end composition including
  per-candidate quarantine coverage).

## 4. Tests

`backend/tests/test_ai6_external_intelligence.py` — 58 corpus-derived
tests: positive intake/filing/interpretation flows; negative coverage for
boundary violations (forbidden flows, quarantined-content reuse),
malicious content (each injection finding kind blocking; multi-code
sequences), malformed inputs (bad hash, naive timestamps, bad
vocabularies, malformed evidence objects, duplicate ids, overlong
excerpts), attempted privilege escalation (PRIVILEGE_ESCALATION findings
quarantine-gated; autonomy-ceiling refusal; two-key single-key/collision
refusals); determinism (same inputs → same codes); frozen records;
structural hygiene (no network/IO/LLM surface; imports restricted to
canonical contracts).

Pre-battery test-expectation fixes (disclosed per AI-4 §4.1 precedent;
module behavior unchanged): 7 test expectation defects — five tests
omitted the `verification` argument (or used verification-requiring
controls) while asserting single refusal codes; two tests passed a
provenance fixture that already carried `dataset_version` while expecting
its absence code. All corrected before the recorded battery.

## 5. Validation battery (pre-commit; raw `docs/governance/evidence/raw/2026-10-19_ai6/`)

All exit codes preserved as `<name>.exit` files; SHA manifest
`00_evidence_sha256.txt` (13 evidence files, self-excluded):

| Check | Result | Exit |
|---|---|---|
| pytest full suite | **621 passed, 2 pre-existing warnings in 78.31s** (563 + 58 AI-6) | 0 |
| pytest AI-6 new block | **58 passed in 0.23s** | 0 |
| pyflakes (app + tests) | 0 findings | 0 |
| compileall (app + tests) | clean | 0 |
| pip-audit | "No known vulnerabilities found" | 0 |
| validate_alpha_environment | PASS | 0 |
| validate_alpha_runtime | PASS | 0 |
| validate_frontend_static | PASS | 0 |
| validate_providers tsetmc | PASS with `"live_verified": false` (correct fail-closed) | 0 |
| validate_providers brsapi | PASS with `"live_verified": false` (correct fail-closed) | 0 |
| validate_bootstrap_config | 8 checks, 0 FAIL | 0 |
| `git diff --check` | clean | 0 |

At-commit battery at the block commit `adf8cdf` (raw
`docs/governance/evidence/raw/2026-10-19_ai6a/`): pytest full suite
**621 passed, 2 pre-existing warnings in 78.19s**; AI-6 new block
58 passed in 0.24s; pyflakes 0; compileall 0; pip-audit clean;
validators 0; bootstrap 8/8; `git diff --check` 0; SHA manifest
`00_evidence_sha256.txt` (13 evidence files, self-excluded).
AI-6a batteries: pre-commit at the AI-6a content (raw
`docs/governance/evidence/raw/2026-10-20_ai6a/`, tracked_dirty=9,
context-labeled) and at-commit at `1d9030c` (raw
`docs/governance/evidence/raw/2026-10-20_ai6b/`, tracked_dirty=0):
**621 passed / 2 warnings / 77.63s (pre-commit) and 77.69s
(at-commit)**; AI-6 block 58 in 0.26s / 0.23s; all 12 components exit 0
in both; both SHA manifests verify 13/13 OK.

Harness disclosure (also in `00_context.txt`): the first battery pass had
two invocation defects in the harness itself (`pip_audit
--progress-terminal` unsupported; `validate_providers.py` requires
`--source KEY`); both corrected and the two components re-run to exit 0;
all other components are first-pass outputs. No project code or gate was
affected.

## 6. Independent read-only audit

Audit executed AFTER this block commit by an independent read-only
auditor (governance order: battery → commit → audit → remediation →
delta re-audit): `docs/governance/evidence/2026-10-19_AI6_independent_audit.md`
(untracked governance-evidence location, same as all prior block
audits). **Initial verdict: FAIL (narrow)** — zero CRITICAL, zero gate
drift, zero test failures; 3 MEDIUM (AI6-01 corpus-locus `02:195-197` →
actual `02:194`; AI6-02 scope `06 §11 (lines 124-127)` → actual
`06 §11 (lines 100-101)`; AI6-03 `evidence_filing_gate` allowed filing
while content was BOTH finding-bearing AND actively quarantined —
contradicting the gate's own docstring and scope R7) + 6 LOW (AI6-04
locus cluster; AI6-05 sandbox-proposal loci; AI6-06 CoverageReport
"consumed" overstatement; AI6-07 `two_key_gate()` name; AI6-08
readiness-report modified-set parenthetical; AI6-09 at-commit battery
uncited) + 3 INFO (AI6-10/11/12).

Remediation (AI-6a, this commit): AI6-01/02/04/05 — corpus-locus
corrections across module docstring/comments, scope matrix, execution
record, sandbox proposal (all content was verbatim-accurate; loci
corrected); **AI6-03 — the gate was TIGHTENED to the documented rule**
(`evidence_filing_gate` now refuses whenever the content is actively
quarantined, regardless of findings; findings-without-quarantine
coverage still refuses; both refusal codes retained; test
`test_filing_gate_blocked_by_findings_and_quarantine` updated to assert
the both-set refusal — this enforces the block's own declared contract
and corpus quarantine discipline; no requirement invented); AI6-06/07 —
scope R13/R8 reworded to the actual mechanism; AI6-08 — readiness
report parenthetical corrected against `git diff --name-status`; AI6-09
— at-commit battery `_ai6a` cited in §5 (also fixes AI6-10's 880-line
count). AI6-11/12 (INFO) ACCEPTED as recorded observations: weak
same-process determinism test / freeze test covers 2 of 12 record types /
INSTRUCTION_CONFLICT not gate-exercised as a blocking kind; unbounded
`notes`/tuple fields; uncaught AttributeError on non-str hash in
`evidence_filing_gate` (deterministic loud failure, contract-level
acceptable); intake-gate docstring order list omits the 7th emitted code
`verification_source_mismatch`; redundant `controls is not None`.

Delta re-audit (same independent auditor, after the AI-6a commit):
**PASS** — AI6-01..09 verified FIXED against the actual `1d9030c` diff
(gate logic hand-traced for all four findings × quarantine combinations;
both refusal codes retained; all corrected corpus loci re-verified
verbatim); AI6-10/11/12 ACCEPTED. Two residual items from the delta
re-audit, dispositioned by the AI-6b commit: AI6-13 (LOW — the AI-6a
at-commit battery `2026-10-20_ai6b/` was cited by no tracked document)
fixed by the §5 citation above; AI6-14 (INFO — containment wording
breadth) narrowed: scope R7 and the gate docstring now say
"evidence-use flow (filing or interpretation)" with containment-aware
intake recorded as the designed precondition. Final chain verdict:
**PASS** (`docs/governance/evidence/2026-10-19_AI6_independent_audit.md`,
original FAIL verdict preserved verbatim).

## 7. Governance reconciliation

- Pointers updated in this block commit: `docs/active/INDEX.md` (+6
  entries), `docs/STATUS.md` (AI-6 row), `docs/CHANGELOG.md` (entry),
  `RADAR_BOURSE_MASTER_HANDOFF.md` (AI-6 Update section), G2 evidence
  matrix addendum (R6: E1/E3 currency refreshed; NOT an approval).
- `docs/governance/PROJECT_EXECUTION_STATE.md` (untracked working
  governance file) reconciles AFTER the commit with the actual SHAs,
  together with the remediation commit's audit-outcome recording (same
  pattern as AI-4: state-file reconciliation rode the remediation step).
- Companion directives artifacts committed in the same cycle:
  `AI4_SANDBOX_LIMITS_PROPOSAL.md` (R4), `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md`
  (R3), `PUBLICATION_READINESS_REPORT_2026-10-19.md` (R5),
  `OWNER_DECISION_REGISTER_REVIEW_2026-10-19.md` (R7).

## 8. Explicitly NOT verified / NOT claimed (D-AI-41)

- No network ingestion, crawl, or provider contact was performed or is
  now possible through this module (no such code path exists).
- D-AI-29 NOT activated: the boundary set is implemented at the contract
  class, not validated against a live runtime; operationalization needs
  owner decisions (source classes, Two-Key parameters, credentials) and
  remains post-G2 class work.
- Unverified environments unchanged: Windows targets, Python 3.13 CI
  parity, native Claude CLI recognition, live providers/LLM.
- AI-6 coverage/freshness/failure reporting at RUNTIME (02:169) remains
  NOT PROVEN; `source_registry.coverage_report` / `CoverageReport`
  remain canonical in `source_registry.py` and are not yet consumed by
  the contract layer (runtime reporting is post-gate).
