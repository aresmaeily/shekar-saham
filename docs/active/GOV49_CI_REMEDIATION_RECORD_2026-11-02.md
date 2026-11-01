# GOV-49 — CONSOL-GOV-49: POST-PUBLICATION CI REMEDIATION RECORD (2026-11-02)

Directive: CONSOL-GOV-49. Published base (GOV-48): `1a160ce40d49bf24fa0ec06c016cc1b08f9a7399`
(tree `bdc1cd2e4a5d18464a64e0aec6ddd2295f5e5ad4`) — preserved as ancestor, not modified.
Verified failing runs on the base commit:

- Backend `test-backend` → step `Tests`: https://github.com/aresmaeily/shekar-saham/actions/runs/41328910108 (job 124914650536)
- Windows `windows-validation` → step `Health + version consistency (W2)`: https://github.com/aresmaeily/shekar-saham/actions/runs/41328910087 (job 124914650920)
- `build-docker` skipped (needs: test-backend).

## 1. Evidence retrieval and its limits

Anonymous evidence channels actually used: run/job pages, step-level conclusions and
timestamps (GitHub UI + check-runs API via an alternate egress), check-run annotations,
artifact list metadata. **Raw CI logs and artifact contents are NOT anonymously
retrievable** (GitHub requires sign-in for both; API job-log download returns 403 "Must
have admin rights to Repository", artifact zip returns 401; the sandbox egress IP is
shared and its api.github.com quota is consumed externally). Log retrieval is recorded
as a blocked step; the diagnosis below therefore rests on exact local reproduction,
step timing, and artifact-size calibration — not on log text.

Step timing (check-runs API): backend `Tests` 16:57:09→16:58:29 (80 s — full suite ran,
failures at the end). Windows: `Boot backend (W1 startup)` 16:57:37→16:58:21 (44 s,
successful 200), `Health + version consistency (W2)` 16:58:21→16:58:23 (2 s, failure),
W6/W7 skipped, artifacts uploaded 16:58:25 (1438 bytes).

Artifact-size calibration (local re-zip of equivalent payloads): with
`windows_health.json` ≈ 2659 B; without ≈ 1564 B; actual 1438 B ⇒ **`windows_health.json`
was never written ⇒ W2's `Invoke-RestMethod` threw before any assertion output existed**
(i.e. a transport-level failure on the W1→W2 step boundary, not a version mismatch — a
mismatch or missing-version failure would have produced the artifact).

## 2. Local reproduction (no causes inferred from job names)

- Environment built to CI spec: Python 3.13.5 + `backend/requirements.txt` pins
  (fastapi 0.141.1, pydantic 2.13.4, …). **Full suite on a normal (full-history)
  checkout: 938 passed / 1 skipped / 78.99 s — GREEN.** The backend failure is
  therefore environment-dependent, not code-dependent.
- **Exact reproduction: a `--depth 1` clone of `1a160ce` (exactly what
  `actions/checkout@v4` produces by default) fails 7 tests, all in
  `backend/tests/test_g2_acceptance_harness.py`** (79.29 s, 931 passed):
  1. `TestCorpusIdentity::test_live_corpus_matches_pinned_reference` —
     `docs/governance/amendment_sources_2026-10-02/` absent in a fresh checkout
     (owner-environment untracked artifact) → `all_ok False`, 7× MISSING.
  2. `TestEvidenceFreshness::test_harness_emits_freshness_check_honestly_without_evidence_dir`,
  3. `TestImplementationBinding::test_docs_only_since`,
  4. `TestImplementationBinding::test_substantive_changes_since_rejected`,
  5. `TestImplementationBinding::test_harness_emits_impl_check_honestly_without_evidence_dir`,
  6. `TestVerdictContract::test_report_shape`,
  7. `TestVerdictContract::test_machine_checkable_subset_holds_at_current_commit`
     — all crash with `git rev-parse HEAD~1` → exit 128 (no parent commit exists in a
     shallow clone; `scripts/g2_acceptance_battery.py collect()` line 416 uses
     `check=True`).
- W2: the exact step script was executed under PowerShell 7.4.6 against a locally
  booted app (Linux): passes (health 200, `version=3.0.0`, committed extraction
  `3.0.0`, equality true). Combined with the artifact-size finding, the W2 root cause
  class is: the single-shot HTTP call in the original W2 script threw (transient
  step-boundary failure); the server had answered 200 in W1 seconds earlier and no
  app-side scheduled work fires in that window (market refresh +30 s, alert_ops +60 s).

## 3. Root causes

- **RC1 (backend, 6 of 7 failures):** CI checked out depth 1; the G2 acceptance-harness
  tests legitimately require repository history (`HEAD~1`, parent diffs). The workflow
  had never executed on a real runner before the GOV-48 push, so the shallow-checkout
  incompatibility was never exposed until now.
- **RC2 (backend, 1 of 7 failures + a latent 8th):** the G2 machine-checkable subset
  REQUIRES the amendment corpus at the tested commit
  (`test_machine_checkable_subset_holds_at_current_commit` asserts
  `G2-C-iv satisfied is True`; the corpus digests are pinned in the tracked harness).
  The corpus lived only as an untracked owner-environment artifact under
  `docs/governance/`, so a fresh checkout can never satisfy G2-C-iv. Tracking the 7
  canonical files is the only non-weakening fix (a conditional skip would delete a real
  governance assertion and was rejected).
- **RC3 (windows):** W2 performed a single unguarded HTTP request immediately after a
  step boundary. First remediation added a bounded retry (15 × (5 s + 2 s)) — **run
  41335202370 (job 124933446176) falsified the transient hypothesis: W2 failed again
  after ~100 s of retries with the server unreachable the whole step** (job 2 m 36 s ≈
  44 s W1 + ~105 s retry window + overhead), i.e. the W1-started uvicorn process does
  NOT survive the W1→W2 step boundary on Windows runners (deterministic per-step
  process cleanup on the hosted runner). The design defect is a step consuming a
  server owned by a PREVIOUS step — with no diagnostics when it fails (raw log
  sign-in-gated ⇒ undebuggable post-hoc).

## 4. Changes (smallest justified correction; no test modified, no assertion weakened)

1. `.github/workflows/ci.yml` — `test-backend` checkout now `fetch-depth: 0` with an
   explanatory comment (RC1). `build-docker` untouched (does not run the suite).
2. `docs/governance/amendment_sources_2026-10-02/` — the 7 canonical amendment-source
   documents are now TRACKED (RC2). Staged-blob SHA-256 verified 7/7 against
   `CORPUS_REFERENCE_DIGESTS` in `scripts/g2_acceptance_battery.py` BEFORE commit
   (byte-identity preserved by git; repo has no `.gitattributes` and no eol
   normalization applies to these paths). Secret-pattern scan over the 7 files: 1
   prose-only match (a policy sentence), 0 credential-shaped strings. Effect: G2-C-iv
   becomes verifiable in CI at full strength — the pinned digests now check
   repository content, giving the governance baseline public tamper-evidence. The
   remaining bootstrap untracked set (`PROJECT_EXECUTION_STATE.md`,
   `docs/governance/evidence/`, `.claude/`, `CLAUDE.md`, `scripts/r13_owner_repo_setup.sh`,
   `scripts/validate_bootstrap_config.py`) is unchanged and stays untracked.
3. `.github/workflows/windows.yml` — W2 step made SELF-SUFFICIENT (RC3, revised after
   run 41335202370): bounded health re-verification (5 × (5 s + 2 s); zero added
   latency when healthy); **if unreachable, boots the same app the same way W1 does**
   (`Start-Process python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   -WorkingDirectory backend`, absolute-path redirects, pid file updated) and polls up
   to 60 × 2 s before asserting; defensive committed-version extraction (explicit
   not-found error instead of an obscure null dereference); full failure diagnostics
   into the step log and `windows_run_provenance.txt` (exception message + both
   uvicorn stderr tails). W6 likewise ensures the server is reachable (boots if
   needed) before the E2E suite. The boot event is recorded in the provenance file —
   honest evidence, not masking: a genuinely dead app still fails the step. ALL
   original assertions preserved verbatim (no-version-field error, version-mismatch
   error, provenance line, artifact writes); all step names unchanged.

Not changed (recorded as observations): the pre-existing `pytest>=9.0.3` float pin and
the `on.push.branches` lines are byte-unchanged; no gate file touched
(`AI2_ENABLED=0` config.py:109, `verified=False` config.py:282,
`execution_mode=SYNTHETIC_OR_PAPER`), no notifier/ws_hub change, no history operation.

## 5. Validation executed (this cycle, at the post-commit HEAD unless stated)

- Full backend suite, Python 3.13 + exact requirement pins, full-history checkout:
  938 passed / 1 skipped (green) — pre-commit at `1a160ce` and re-run at the GOV-49 HEAD.
- Focused G2 harness suite green at the GOV-49 HEAD.
- W2 exact step body (revised, self-sufficient version) executed under PowerShell
  7.4.6 against a locally booted app — BOTH paths: server-dead → boots its own server
  via Start-Process (provenance records "existing server unreachable … booting the app
  in this step"), assertions pass (`3.0.0 == committed`, `windows_health.json`
  written); server-alive → immediate pass, no second boot. The first version
  (retry-only) was validated the same way and then falsified in CI by run
  41335202370 — recorded, not discarded.
- Fresh shallow-clone spot check at the GOV-49 HEAD: corpus present from the clone ⇒
  corpus-identity test green even without history; the remaining shallow-clone failures
  are exactly the history-dependent ones, which `fetch-depth: 0` removes in CI (the
  full-history checkout is the CI-equivalent environment and is green).
- `python -m pyflakes app/` clean; `git diff --check` clean; both workflow YAMLs parse
  (PyYAML); corpus digest re-verification 7/7 from the committed blobs.

## 6. Publication

Forward-only fast-forward commit on top of `1a160ce…` (no amend/rebase/reset/force),
pushed through the authorized deploy-key path (`GIT_SSH` paramiko wrapper, pinned host
keys, repo-scoped Ed25519 key). Final SHA and CI run URLs are sealed in
`download/GOV49_CI_REMEDIATION_EVIDENCE_2026-11-02/` (exact-SHA check-runs evidence;
completion criterion: test-backend + build-docker + windows-validation all pass on the
exact new SHA).
