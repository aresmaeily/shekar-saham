# HANDOFF README — RADAR BOURSE

## What is RADAR BOURSE?
RADAR BOURSE / رادار بورس is an AI-powered intelligent market analysis platform focused on the Iranian stock market.

## Repository

```text
Project Root: /home/user/repo
Backend: /home/user/repo/backend
Remote: https://github.com/aresmaeily/shekar-saham.git
Branch: main
Current commit: 4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce
Commit message: P3.44: Pre-Installation Repository Hardening and RADAR BOURSE Integrity
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Local vs Remote: 21 ahead / 0 behind
```

## What has been completed?

- P3.39 AI Intelligence Core.
- P3.40 Market Intelligence.
- P3.41 Filter Intelligence and Self-Optimization contracts/service/API/tests.
- P3.42 AI ↔ Filter Intelligence integration hardening.
- P3.43 RADAR BOURSE terminology cleanup.
- P3.44 pre-installation repository hardening.
- P3.45 repository-side target readiness inspection.

## What must not be repeated?

Do not rebuild AIIntelligenceCore, MarketIntelligenceService, FilterIntelligenceService, Filter DSL, Backtest, Walk-Forward, Forward-Test, Data Trust, or security middleware without a verified reason.

## What is blocked?

- GitHub push/sync: blocked by missing authentication.
- Windows target validation: target not accessible here.
- BRSAPI live validation: BRSAPI_KEY missing.
- Live TSETMC validation: not verified.

## What is deferred?

Installation, target validation, Electron runtime/package validation, browser E2E, production deployment, live provider validation, 24/7 scheduler.

## Current target status

```text
Windows Installation: NOT STARTED
Target Installation: NOT STARTED
Electron Installation: NOT STARTED
Browser E2E: NOT STARTED
```

## Where are the reports?

- P3.45 report: `docs/active/P3.45_RADAR_BOURSE_TARGET_VALIDATION_AND_INSTALLATION_READINESS_FINAL_REPORT.md`
- Continuity record: `docs/active/PROJECT_CONTINUITY_HANDOFF.md`
- Artifact manifest: `docs/active/PROJECT_ARTIFACT_MANIFEST.md`
- Link manifest: `docs/active/PROJECT_LINK_MANIFEST.md`
- P3.43 report: `docs/active/P3.43_RADAR_BOURSE_HARDENING_FINAL_REPORT.md`
- P3.44 report: `docs/active/P3.44_PRE_INSTALLATION_HARDENING_FINAL_REPORT.md`

## Where are the artifacts?

Primary artifact directory:

```text
/home/user/deliverables
```

Current baseline archive:

```text
/home/user/deliverables/P3.44_RADAR_BOURSE_FULL_PROJECT_4e6cf72.zip
SHA-256: 3a8618e53cefbe4ae180ddda700a40497d81c0e83a9f6fe456be045bca6aa026
```

## Secrets intentionally excluded

`.env`, passwords, API keys, tokens, private keys, Git credentials, SSH private keys, cookies, session tokens, `.netrc`, `.git-credentials`.

## Exact next safe action

Review the handoff documentation files, then commit them with a documentation-only commit if accepted. Do not push until authentication is available.
