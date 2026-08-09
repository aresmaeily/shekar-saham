# PROJECT CHAT CONTINUITY RECORD — RADAR BOURSE

Date: 2026-08-09

Purpose: This file preserves the decision/context trail needed for a future developer or a new ChatGPT chat to continue RADAR BOURSE without relying on the previous conversation. It is a structured continuity record, not a verbatim chat transcript.

Important limitation: Full raw chat transcript is not stored in this repository. This record is based on available repository evidence, Git history, phase reports, validation outputs already documented, and known artifact records. If an item is not verifiable from available records, it is marked accordingly.

---

## A. Project History

RADAR BOURSE is an AI-powered market intelligence platform focused on the Iranian stock market. The repository technical slug remains `shekar-saham`, but the product identity was locked as `RADAR BOURSE / رادار بورس` in P3.43/P3.44.

Relevant completed phase chain:

| Phase | Status | Evidence |
|---|---|---|
| P3.35 | Complete locally | Commit `7f306000df0cc55e54a8977967d8960ceb22dfdc`, archive exists |
| P3.36 | Complete locally | Commit `76b35c17fa0f57cda8d27fb27a6ac4f4026d5572`, archive exists |
| P3.37 | Complete locally | Commit `11d376a517ed21125ce979ec26bf30f93bf0377b`, archive exists |
| P3.38 | Complete locally | Commit `ca5bcb9031aeb93c33f61134e16124c2ae9cb7d0`, architecture lock docs |
| P3.39 | Complete locally | Commit `3b7d6ca044e0d9f151bcd320949b496c777fe968`, AI Intelligence Core |
| P3.40 | Complete locally | Commit `5aa8b7e54154305cfe18950e34068eb23177e214`, Market Intelligence |
| P3.41 | Complete locally | Commit `0bfcee5ab66b177b70f217d26032b1559a783cc7`, Filter Intelligence |
| P3.42 | Complete locally | Commit `fe3d1616cc081fd85d69b668f08faf3ba11e9abc`, AI ↔ Filter integration hardening |
| P3.43 | Complete locally | Commit `795db6975399fd7827b76229d298f6b46c65583e`, RADAR BOURSE terminology hardening |
| P3.44 | Complete locally | Commit `4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce`, pre-install hardening |
| P3.45 | Repository-side inspection complete; target validation blocked | No commit; no code/config/db/install changes; Windows target inaccessible |

---

## B. Product Direction

Current product identity:

```text
RADAR BOURSE
رادار بورس
```

Primary market scope:

```text
Iranian Stock Market
```

North-star direction:

```text
Market + Symbol + Filter + Strategy + Risk + Data Trust + Performance
  ↓
AI Brain
  ↓
Evidence
  ↓
Proposal
  ↓
Validation
  ↓
Human Approval
```

The product is not an autonomous trading system. It is decision support / market intelligence.

---

## C. Architecture Decisions

Final / strongly established decisions:

1. Use existing FastAPI backend as application core.
2. Preserve static frontend served by backend.
3. Preserve Electron as desktop shell over backend URL.
4. Use SQLite Store for current persistence; do not introduce new DB layer without evidence.
5. Use Data Trust on all live/mock/synthetic/stale/unavailable outputs.
6. AI must be structured evidence/decision support, not just chatbot.
7. Filter Intelligence must be versioned, auditable, and human-approved before production activation.
8. No broker integration / no live trading / no autonomous trading.
9. Installation remains locked until explicit owner instruction.
10. GitHub sync must not be claimed until remote SHA equals local SHA.

Open/provisional decisions:

- Whether to migrate technical legacy names like DB/cookie/localStorage keys.
- Whether to add formal migration framework later.
- Whether to add browser E2E framework.
- When target Windows installation will be authorized.
- How GitHub authentication will be configured.

---

## D. Completed Phases

### P3.39 — AI Intelligence Core

Implemented:

- `backend/app/domain/ai_intelligence.py`
- Structured `IntelligenceResult` and evidence model.
- Deterministic recommendation logic.
- Data Trust gate for non-live data.
- API endpoint: `POST /api/ai/intelligence/{symbol}`.

Do not repeat:

- Do not rebuild AIIntelligenceCore.
- Do not add live LLM provider without explicit phase/scope.

### P3.40 — Market Intelligence

Implemented:

- `backend/app/domain/market_intelligence.py`
- `backend/app/services/market_intelligence_service.py`
- Market snapshot, regime, industries, opportunities, events.
- API endpoints for market intelligence.

Deferred:

- 24/7 scheduler not enabled.

### P3.41 — Filter Intelligence

Implemented:

- `backend/app/domain/filter_intelligence.py`
- `backend/app/services/filter_intelligence_service.py`
- Filter registry, immutable versions, performance records.
- Backtest/walk-forward/forward-test integration.
- Decay detection, proposals, review contract.
- API endpoints for filters and proposals.

Do not repeat:

- Do not create parallel filter registry or backtest engine.
- AI must not directly mutate production filters.

### P3.42 — AI ↔ Filter Intelligence Integration

Implemented:

- Read-only `build_ai_filter_context(...)` in FilterIntelligenceService.
- AIContextBuilder/AIService wiring into `filter_context.filter_intelligence`.
- Regression test for filter intelligence evidence.

Do not repeat:

- Do not create a second AI context integration path unless a verified defect exists.

### P3.43 — Repository Completion and RADAR BOURSE Hardening

Implemented:

- Product-facing terminology cleanup to RADAR BOURSE / رادار بورس.
- Backend/frontend/Electron/docs naming hardening.
- P3.43 archive created and verified.

Remaining historical exceptions:

- Old Persian product phrase remains only in `docs/archive/phase-reports/*` as historical records.

### P3.44 — Pre-Installation Repository Hardening

Implemented:

- Second-pass terminology and pre-install hardening.
- CI/Docker/WS/Electron/Android active references hardened.
- P3.44 archive created and verified.

Not done:

- Installation not started.
- GitHub sync still blocked by auth.

### P3.45 — Target Validation & Installation Readiness

Performed:

- Repository-side inspection.
- Target readiness analysis.
- Dependency/environment/startup/security/database audit.

Not performed:

- No install.
- No service start.
- No DB migration.
- No dependency installation.
- No target Windows validation.

---

## E. Important Decisions

- Product name is now RADAR BOURSE / رادار بورس.
- Technical repository URL remains `https://github.com/aresmaeily/shekar-saham.git`; do not rename remote without explicit plan.
- Installation is not allowed until owner explicitly says INSTALL / شروع نصب.
- Mock/fallback/synthetic data must never be reported as live.
- GitHub push must be normal only; force push/reset/rebase/history rewrite are forbidden.
- Secrets must never be stored in docs or committed.
- Handoff files are documentation-only and may remain uncommitted until owner review.

---

## F. Rejected / Deferred Decisions

Deferred:

- GitHub synchronization: blocked by missing authentication.
- Windows installation and target validation.
- Browser E2E target validation.
- Electron runtime/package target validation.
- Live TSETMC verification.
- Live BRSAPI verification.
- Cloud deployment.
- Production deployment.
- 24/7 scheduler.
- Live LLM provider.
- Broker integration / live trading.

Rejected/prohibited:

- Force push.
- Reset hard.
- Rebase/history rewrite.
- Fake live data.
- Fake profitability.
- AI direct production filter mutation.

---

## G. Current Blockers

P0:

- GitHub authentication unavailable; local is 21 commits ahead of remote.
- Windows target not accessible from current Linux environment.

P1:

- BRSAPI_KEY missing.
- Target environment `.env` not configured.
- TSETMC live data not verified.

P2:

- Browser E2E not run.
- Electron target runtime not validated.
- Docker unavailable in current environment.

---

## H. Current Technical Baseline

```text
Project root: /home/user/repo
Backend: /home/user/repo/backend
Branch: main
Current local HEAD: 4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce
Remote: https://github.com/aresmaeily/shekar-saham.git
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Local vs remote: 21 ahead / 0 behind
Working tree after delivery docs: DIRTY only because handoff documentation files are untracked
```

---

## I. Installation Status

```text
Installation: NOT STARTED
Windows target: NOT ACCESSIBLE FROM CURRENT ENVIRONMENT
Target-machine validation: DEFERRED
Electron installation: NOT STARTED
Browser E2E: NOT STARTED
Production deployment: NOT STARTED
Database migration: NOT STARTED
Service start: NOT STARTED in this final delivery phase
```

---

## J. Data Trust Rules

Absolute rules:

```text
mock != live
synthetic != live
fallback != live
stale != live
unavailable != live
```

Current provider status:

```text
TSETMC: mock_fallback, live_verified=false
BRSAPI: missing API key, mock_fallback, live_verified=false
```

Live validation requires actual command output showing:

```text
data_trust.state == live
is_live == true
no fallback
not stale
not unavailable
```

---

## K. Security Rules

Security surfaces:

- `PRIVATE_MODE`
- `AUTH_REQUIRED`
- `API_KEY`
- `PRIVATE_PASSWORD`
- `FERNET_KEY`
- HttpOnly session cookie
- WebSocket authentication
- Security headers
- CORS
- Rate limiting
- CSRF Origin check
- Production startup guard

Never print or store secret values.

---

## L. Git Rules

```text
NO FORCE PUSH
NO RESET --HARD
NO REBASE
NO HISTORY REWRITE
NO BRANCH DELETION
NO COMMIT AMEND unless explicitly approved
NO GitHub sync claim until remote SHA == local SHA
```

Current GitHub status:

```text
GitHub sync: BLOCKED — authentication unavailable
```

---

## M. Next Phase Constraints

Before any development:

1. Review handoff documents.
2. Verify actual repository state.
3. Resolve or explicitly defer GitHub sync.
4. Preserve installation lock.
5. Do not repeat completed phases.
6. Do not make code/config/db/dependency changes unless specifically authorized.

Recommended next safe action:

```text
Review the handoff documentation package and, if accepted, commit the documentation-only handoff files.
```

---

## N. Known Risks

- GitHub is stale by 21 commits.
- Target installation cannot proceed until owner authorizes and Windows target is accessible.
- Live market data not verified.
- BRSAPI key missing.
- Browser/Electron target validations are deferred.
- Some technical legacy slugs remain for compatibility/real remote URL.

---

## O. Developer Handoff Notes

For a new developer:

1. Start with `HANDOFF_README.md`.
2. Then read `PROJECT_CONTINUITY_HANDOFF.md`.
3. Then read `P3.45_RADAR_BOURSE_TARGET_VALIDATION_AND_INSTALLATION_READINESS_FINAL_REPORT.md`.
4. Then inspect `PROJECT_ARTIFACT_MANIFEST.md` and `PROJECT_LINK_MANIFEST.md`.
5. Verify Git state before doing anything.
6. Do not assume GitHub is current.
7. Do not run installation.
8. Do not claim live data.
9. Do not change architecture without explicit approval.
10. If chat context is missing, use repository + active docs + artifacts as the source of truth.

If information is unavailable from repository/docs/artifacts, mark it:

```text
NOT VERIFIED FROM AVAILABLE RECORD
```
