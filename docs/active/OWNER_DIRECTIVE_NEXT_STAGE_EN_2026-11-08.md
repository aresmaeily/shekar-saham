# NEXT DEVELOPER DIRECTIVE (EN, 2026-11-08) — after OWNER-DIRECTIVE-2026-11-08

Repository `aresmaeily/shekar-saham` · canonical branch `main`.
Baseline for the next stage: the final HEAD of the OWNER-DIRECTIVE-2026-11-08
stage (see `docs/active/OWNER_DIRECTIVE_2026-11-08_EXECUTION_RECORD.md`).

## Standing rules (non-negotiable, unchanged)

- Startup: fetch `origin/main`, resolve the exact 40-hex HEAD, verify
  ancestry, byte-compare and preserve untracked owner artifacts, ff-only
  recovery, never force-push/reset/rebase. Never overwrite newer work.
- Gates byte-pinned: `AI2_ENABLED=0`, `SCHEDULER_ENABLED=0`,
  `verified=False`, `SYNTHETIC_OR_PAPER` (until a dated owner act changes
  one), G2 fail-closed, R-3/R-7 KEEP-DENIED, Two-Key Rule, no broker/live
  trading, no autonomous promotion, no production mutation, no external
  notification egress, no credential exposure, no owner-gate bypass.
- CI discipline: never transfer a check result across SHAs; docs-only
  discriminator procedure for the recorded windows flake class; record every
  failure verbatim and fix forward.
- Test discipline: never weaken assertions, never delete historical failures,
  never add unexplained skips; counter-pin bumps recorded only; pyflakes over
  the WHOLE `app/` is a CI step — run it locally over `app/` (not just touched
  files) before every push; new tests must not introspect raw `app.routes`
  (use `app.openapi()['paths']` — starlette-version-stable).
- Status vocabulary: IMPLEMENTED / TESTED / INTEGRATION-VERIFIED /
  RUNTIME-VERIFIED / OPERATIONALLY-VERIFIED / OWNER-GATED / PARTIAL /
  NOT-VERIFIED. Global completion % stays NOT CALCULATED (OA-8).

## Work packages (dependency order, continuous execution)

1. **Branch protection (owner item carried from §8 of the execution
   record).** When the owner grants a PAT with the Administration repo
   permission (or applies the ruleset in the web UI), verify: required
   checks = `test-backend`, `build-docker`, `windows-validation`,
   `build-installer`; force-push blocked; deletions blocked. Record the
   ruleset ID and a timestamped read-back.
2. **R-1/R-2 installer evidence.** When the owner executes the installer on
   the Windows target machine per `WINDOWS_PACKAGING_RUNBOOK_2026-11-05.md`,
   record the evidence bundle verbatim (install/upgrade/rollback/uninstall/
   reinstall; SHA-256 of the executed artifact must equal the CI provenance;
   never convert a failure).
3. **AI-2 persistence activation prep (D-A2-1..7).** The owner decision
   packet stands; if the owner answers it, mirror the research-memory
   integration pattern of this stage (factory default durable, audited,
   runtime-tested, conftest isolation, settings-cache hygiene) and keep
   `AI2_ENABLED=0` until the SEPARATE activation decision.
4. **AI-MA provider adapter (only after P-1..P-10 answers).** Implement the
   adapter behind `AIMA_PROVIDER_ENABLED` (default 0), synthetic-first
   contract tests, budget/cost telemetry, audit-trail wiring, honest
   labeling; staging verification with synthetic/paper data only.
5. **Golden Set corpus growth** (more interpretation conflicts, resolver
   edges, extraction units/currencies, regime gaps, calibration maturity) —
   keep digest pinning; keep baseline/candidate separation; still NO
   superiority claim (owner-approved benchmark protocol first).
6. **Scheduler production enablement** — only after a dated owner act
   (R-6/OA-4); the env-override staging path is documented; the default
   stays 0 until then.
7. **Recurring AI-7 audits (OA-4)** — infrastructure exists; scheduling
   requires the owner act; nothing runs autonomously.

## Final deliverables for the next stage

Execution record with exact baseline/final SHAs; commit-by-commit summary;
file-level evidence; test commands and counts (both dependency matrices if
versions drift); browser screenshots; exact-SHA CI run/job IDs; 17-role
matrix currency; owner-gated register; residual gaps; invariant verification.
Persian final report + English next directive. Verify every claim against
the real files before publication.
