# RADAR BOURSE MASTER HANDOFF

Date: 2026-08-09  
Project: RADAR BOURSE / رادار بورس  
Purpose: master operational handoff for continuation in a new chat, new developer session, or Windows target pre-install process.

## 1. Project Identity

| Item | Current Value |
|---|---|
| Product Name | RADAR BOURSE |
| Persian Name | رادار بورس |
| Historical/technical repository slug | `shekar-saham` |
| Primary market | Iranian Stock Market |
| Product class | AI-powered market intelligence / decision-support platform |
| Main platforms | Web Application + Windows/Electron Application |

The official product identity is RADAR BOURSE / رادار بورس. Historical old names may remain only in archived historical documents.

## 2. Product Objective

RADAR BOURSE is intended to combine market/symbol/filter/strategy/risk/data-trust evidence into structured intelligence for the Iranian stock market. AI is the system brain and must not fabricate live data, profitability, market state, backtest result, or confidence.

## 3. Current Roadmap

Completed local chain:

```text
P3.39 AI Intelligence Core
P3.40 Market Intelligence
P3.41 Filter Intelligence
P3.42 AI ↔ Filter Intelligence Integration / Repository Completion
P3.43 RADAR BOURSE Terminology Hardening
P3.44 Pre-Installation Repository Hardening
P3.45 Target Validation / Installation Readiness docs
P3.46 Handoff / Alpha Installation Preparation docs
P3.47 Final Pre-Installation Repository Closure
P3.49 Repository Readiness and Windows Pre-Install Hardening
P3.52 Final Project Package and Master Handoff
```

P3.48/P3.50/P3.51 were audit/inspection/validation phases, not feature implementation phases.

## 4. Completed Stages

| Stage | Status | Evidence |
|---|---|---|
| P3.39 | Complete locally | `backend/app/domain/ai_intelligence.py`, commit `3b7d6ca` |
| P3.40 | Complete locally | `market_intelligence.py`, `market_intelligence_service.py`, commit `5aa8b7e` |
| P3.41 | Complete locally | `filter_intelligence.py`, `filter_intelligence_service.py`, commit `0bfcee5` |
| P3.42 | Complete locally | AI context to filter intelligence integration, commit `fe3d161` |
| P3.43 | Complete locally | RADAR BOURSE terminology cleanup, commit `795db69` |
| P3.44 | Complete locally | Pre-install hardening, commit `4e6cf72` |
| P3.45 | Repository-side inspection/docs complete | active P3.45 report exists |
| P3.46 | Handoff/prep docs complete | handoff docs exist |
| P3.47 | Complete locally with target blockers | commits `b83819c`, `4c4af55`, `a39af16` |
| P3.49 | Complete locally with blockers | commit `7ddcd76` |
| P3.52 | Complete locally with blockers | final package and this handoff |

## 5. Current Stage

Current stage is P3.52 final repository package and handoff. It does not authorize installation.

## 6. Architecture

Primary architecture chain:

```text
Market Intelligence
+
Filter Intelligence
+
Strategy Evidence
+
Backtest
+
Walk-Forward
+
Forward Test
+
Risk
+
Data Trust
    ↓
AIContextBuilder / AIService
    ↓
AIIntelligenceCore
    ↓
Structured Intelligence
```

Do not create parallel engines or rewrite architecture without owner approval.

## 7. Backend

Key backend files:

```text
backend/app/main.py
backend/app/core/config.py
backend/app/core/security.py
backend/app/data/providers.py
backend/app/data/store.py
backend/app/domain/ai_intelligence.py
backend/app/domain/filter_intelligence.py
backend/app/domain/market_intelligence.py
backend/app/services/ai_service.py
backend/app/services/filter_intelligence_service.py
backend/app/services/market_intelligence_service.py
backend/app/engines/backtest.py
backend/app/engines/filter_dsl.py
```

Important API routes include `/api/health`, `/api/status`, `/api/live/status`, `/api/ai/intelligence/{symbol}`, `/api/ai/market-intelligence`, `/api/ai/filter-intelligence`, `/api/ai/filters`, `/api/ai/filter-proposals`, `/api/backtest/run`, and `/api/filter/run`.

## 8. Frontend

Frontend is static HTML/JS under `frontend/` and is served by FastAPI. It uses relative `/api` calls and same-host WebSocket `/ws/live`. Browser E2E is not verified on target.

## 9. Electron

Electron files:

```text
electron/main.js
electron/package.json
```

Backend URL selection:

```text
RADAR_BOURSE_URL || SHEKAR_URL || http://127.0.0.1:8000
```

Electron runtime and packaging are not verified on Windows target.

## 10. Windows Installation State

```text
INSTALLATION = NOT STARTED
WINDOWS INSTALLATION = NOT STARTED
TARGET INSTALLATION = NOT STARTED
PRODUCTION DEPLOYMENT = NOT STARTED
```

Windows target validation is still required. PowerShell scripts are repository-side prepared but not Windows-runtime verified.

## 11. Dependency State

Current environment audit found no `.venv`. System Python has only partial dependencies:

```text
pydantic = available
httpx = available
pytest = available
fastapi = missing
pydantic_settings = missing
uvicorn = missing
cryptography = missing
pyflakes = missing
```

Dependency installation requires explicit owner approval.

## 12. Data Trust

Non-negotiable rules:

```text
mock != live
fallback != live
synthetic != live
stale != live
unavailable != live
```

Current live state:

```text
LIVE DATA = NOT VERIFIED
TSETMC = last known mock_fallback / live_verified=false
BRSAPI = missing key / last known mock_fallback / live_verified=false
```

## 13. Security

Security model includes `PRIVATE_MODE`, `AUTH_REQUIRED`, `API_KEY`, `PRIVATE_PASSWORD`, `FERNET_KEY`, HttpOnly session cookie, WebSocket authentication, production guard, security headers, rate limiting, and CSRF Origin check. Never commit `.env`, credentials, tokens, keys, private keys, or secrets.

## 14. Database

SQLite via `backend/app/data/store.py`.

```text
DB path: data/shekar.db
Backup path: data/backups/shekar-*.db
Migration mechanism: PRAGMA user_version internal mechanism
```

No target DB migration has been executed.

## 15. Git State

At P3.52 audit start:

```text
Branch: main
HEAD before P3.52 commit: 7ddcd766413784e8ada2d06e17f624f04f1e9edf
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Local vs remote: 25 ahead / 0 behind
GitHub sync: BLOCKED by missing remote config/authentication
```

After P3.52, use actual `git rev-parse HEAD` from repository as authoritative.

## 16. GitHub State

Direct remote URL is reachable for read checks. Push/sync has not been completed because authentication is unavailable. Do not claim GitHub sync until remote SHA equals local SHA after a normal push.

## 17. Artifacts

Latest before P3.52:

```text
/home/user/deliverables/P3.49_RADAR_BOURSE_REPOSITORY_READY_7ddcd76.zip
SHA-256: 8456a4263ea164c78a07795ee9c09e54d263338edacca1f9a77af91490f429de
```

P3.52 produces the final project package from the latest repository state.

## 18. Known Blockers

- GitHub authentication unavailable / remote config not persisted.
- Windows target not verified.
- Dependency environment missing locally (`.venv` absent).
- BRSAPI key missing.
- TSETMC live validation not verified.
- Browser E2E and Electron runtime not verified on target.

## 19. Remaining Work

Repository-side:

- Restore or approve dependency environment if full runtime validation is required locally.
- Configure GitHub authentication and push normally.

Target-side:

- Transfer final package to Windows target.
- Run pre-install checklist only.
- Configure `.env` securely.
- Validate PowerShell, Python, Node/npm, port, firewall, browser, backend, frontend, Electron as applicable.

## 20. Installation Gate

```text
CAN INSTALL = NO
```

Reason: owner has not issued explicit `INSTALL` instruction. Target validation is incomplete.

## 21. Exact Next Safe Action

Transfer the P3.52 final project package to the Windows target and run only the PRE-INSTALL CHECKLIST without installation.

## 22. Important Historical Decisions

- Product name is RADAR BOURSE / رادار بورس.
- Iran market remains priority.
- AI is decision-support intelligence brain, not autonomous trader.
- Human approval required for sensitive filter/strategy production changes.
- Mock/fallback/synthetic data must never be treated as live.
- Git history rewrite and force push are forbidden.

## 23. Contradictions Between Reports

Earlier reports sometimes listed old HEAD values or claimed GitHub sync readiness. Current repository state always wins. Current GitHub remote remains behind local. Current dependency environment is incomplete.

## 24. Actual vs Reported State

Reported state must be re-verified before every phase. Current authoritative state is the repository state and the final P3.52 package contents.

## 25. Instructions for the Next Supervisor / Prompt Writer Chat

1. Verify `git status --short --branch`.
2. Verify `git rev-parse HEAD`.
3. Verify GitHub remote state using direct URL if `origin` is missing.
4. Do not install until owner says `INSTALL`.
5. Do not treat mock/fallback data as live.
6. If dependencies are missing, request approval before installing.
7. Start next phase with target pre-install validation only.

---

## P3.53 Update — Dependency Recovery, Validation, Final Artifact Delivery Attempt

Authoritative stage: P3.53 repository-side final package and handoff.

Actual baseline before P3.53 changes:

```text
HEAD: ca6d3fc8f7f4127a610618547f396860e3a8eca8
Commit: P3.52: Final Project Package and Master Handoff
Working tree: clean
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Local vs remote: 26 ahead / 0 behind
```

Dependency recovery:

```text
Local validation venv: /home/user/repo/.venv
Source manifest: backend/requirements.txt
Result: dependency environment recovered for repository-side validation
```

Dependency consistency change:

```text
backend/requirements.txt now includes pyflakes>=3.4.0 because pyflakes is a required validation command and was missing from the dependency manifest.
```

Validation results:

```text
compileall: PASS
pytest: 132 passed, 1 warning
pyflakes: PASS
node syntax checks: PASS
shell syntax checks: PASS
validate_alpha_environment.py: PASS
validate_alpha_runtime.py: PASS
validate_frontend_static.py: PASS
validate_providers.py --source tsetmc: PASS as fallback validation; live_verified=false
validate_providers.py --source brsapi: PASS as missing-key fallback validation; live_verified=false
```

Data trust remains:

```text
LIVE DATA = NOT VERIFIED
TSETMC = mock_fallback / live_verified=false
BRSAPI = missing key / mock_fallback / live_verified=false
```

Installation remains:

```text
INSTALLATION = NOT STARTED
WINDOWS INSTALLATION = NOT STARTED
TARGET INSTALLATION = NOT STARTED
PRODUCTION = NOT STARTED
```

GitHub remains blocked unless authentication is configured. Do not claim sync until remote SHA equals local HEAD.

External artifact URL: recorded in final P3.53 response and/or current artifact delivery metadata if upload succeeds. If external upload is blocked, use internal artifact path as backup only.

---

## P3.54 Update — Final External Artifact Delivery and GitHub Sync Attempt

P3.54 continues from P3.53. Repository-side dependency environment is available and local validation passed again.

Actual baseline before P3.54 commit:

```text
HEAD: 3557f9f12b6e443dbe4c7d3a55c55fc60b1119b9
Commit: P3.53: Dependency Recovery and Final Artifact Delivery
Working tree: clean
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Local vs remote: 27 ahead / 0 behind
```

P3.54 validation summary:

```text
compileall: PASS
pytest: 132 passed, 1 warning
pyflakes: PASS
node syntax: PASS
shell syntax: PASS
alpha environment: PASS
alpha runtime: PASS
frontend static: PASS
TSETMC provider validation: PASS as mock_fallback, live_verified=false
BRSAPI provider validation: PASS as missing-key mock_fallback, live_verified=false
```

Installation remains locked:

```text
INSTALLATION = NOT STARTED
WINDOWS INSTALLATION = NOT STARTED
TARGET INSTALLATION = NOT STARTED
PRODUCTION = NOT STARTED
```

GitHub remains blocked unless authentication is provided. External artifact details are recorded in the P3.54 final report and final response.

---

## P3.55 Update — Workspace Recovery and Continuation

P3.55 is a recovery phase, not a feature phase.

The previous sandbox had an empty `/home/user`. The project was restored from the verified P3.54 TempFile artifact:

```text
https://tempfile.org/j334zfL2F2t/download
SHA-256: 5ba6e1271a12e26d7ad9d3aceebac185322edd5dbbbfe98c5aef35a21b8decd0
FILE COUNT: 757
ZIP TEST: PASS
ARTIFACT VERIFICATION: PASS
```

Recovery results:

```text
PROJECT ROOT: /home/user/repo
Recovered HEAD: 2d13cf3e62fd51490f7f6afdccefd619f024d07c
GIT HISTORY: RESTORED
.git/config: reconstructed credential-free with public origin only
backend/app/data/*: restored from Git objects (omitted from P3.54 zip by overly broad data/ gitignore)
.gitignore: data/ narrowed to /data/ so future packages keep backend/app/data/
Local vs remote after recovery: 28 ahead / 0 behind
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
GITHUB SYNC: BLOCKED
```

Dependency environment:

```text
/home/user/repo/.venv recreated from backend/requirements.txt
READY for repository-side validation
```

Validation after recovery:

```text
compileall: PASS
pytest: 132 passed, 1 warning
pyflakes: PASS
node syntax: PASS
shell syntax: PASS
alpha environment: PASS
alpha runtime: PASS
frontend static: PASS
TSETMC: mock_fallback / live_verified=false
BRSAPI: missing key / mock_fallback / live_verified=false
```

Installation remains locked:

```text
INSTALLATION = NOT STARTED
WINDOWS INSTALLATION = NOT STARTED
TARGET INSTALLATION = NOT STARTED
PRODUCTION = NOT STARTED
CAN INSTALL = NO
```

Authoritative stage after this update is P3.55 workspace recovery. Next safe action: transfer the P3.55 package to the Windows target and run only the PRE-INSTALL CHECKLIST, or wait for GitHub authentication / explicit INSTALL.

---

## P3.56 Update — GitHub Sync Verification and Windows Pre-Install Transfer

P3.56 re-verified GitHub against the actual local repository. GitHub is **not** fully up to date.

```text
LOCAL HEAD at P3.56 start: b14feea147b7db77d6808a3b341e3c7b97c3bbdb
REMOTE HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
LOCAL VS REMOTE: 29 ahead / 0 behind
GITHUB FULLY UP TO DATE: NO
GITHUB UPDATE CHECK: NOT UPDATED
GITHUB SYNC: BLOCKED
PUSH: BLOCKED
REASON: AUTHENTICATION UNAVAILABLE
ERROR: fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

Authentication flags: GITHUB_TOKEN / GH_TOKEN / GIT_ASKPASS / SSH_AUTH_SOCK unset; gh unavailable; credential.helper none.

Repository-side validation was re-executed and passed:

```text
compileall PASS
pytest 132 passed, 1 warning
pyflakes PASS
node syntax PASS
shell syntax PASS
alpha environment / runtime / frontend static PASS
TSETMC mock_fallback / live_verified=false
BRSAPI missing key / mock_fallback / live_verified=false
```

Windows pre-install transfer instructions:

```text
docs/active/P3.56_WINDOWS_PRE_INSTALL_TRANSFER.md
```

Installation remains locked:

```text
INSTALLATION = NOT STARTED
WINDOWS INSTALLATION = NOT STARTED
PRODUCTION = NOT STARTED
CAN INSTALL = NO
WINDOWS TARGET = NOT VERIFIED
```

Do not clone GitHub as the product source until LOCAL HEAD == REMOTE HEAD. Use the latest verified TempFile package.

Next safe action: provide GitHub authentication for a normal push, or transfer the P3.56 package to Windows and run only the PRE-INSTALL checklist. Do not install unless the owner says INSTALL.

---

## P3.57 Update — GitHub Authentication Push or Windows Pre-Install Gate

P3.57 re-verified the first question with live Git commands.

```text
QUESTION: Is GitHub fully up to date with the local HEAD?
ANSWER: NO
LOCAL HEAD at P3.57 start: ad7e81346a47fef49d593dcc2333773058346e07
REMOTE HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
LOCAL VS REMOTE: 30 ahead / 0 behind
GITHUB UPDATE CHECK: NOT UPDATED
GITHUB FULLY UP TO DATE: NO
GITHUB SYNC: BLOCKED
PUSH: BLOCKED
REASON: AUTHENTICATION UNAVAILABLE
ERROR: fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

Authentication is still unset: GITHUB_TOKEN / GH_TOKEN / GIT_ASKPASS / SSH_AUTH_SOCK / gh / credential.helper / SSH keys.

Repository-side validation was re-executed:

```text
compileall PASS
pytest 132 passed, 1 warning
pyflakes PASS
node syntax PASS
shell syntax PASS
alpha environment / runtime / frontend static PASS
TSETMC mock_fallback / live_verified=false
BRSAPI missing key / mock_fallback / live_verified=false
```

Installation remains locked. Windows target remains NOT VERIFIED.

Do not clone GitHub as the product source until LOCAL HEAD == REMOTE HEAD.

Next safe action: provide GitHub authentication for a normal push, or transfer the latest verified package to Windows and run only validate_install.ps1. Do not install unless the owner says INSTALL.
