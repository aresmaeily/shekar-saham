# ALPHA INSTALLATION PREPARATION FINAL REPORT — RADAR BOURSE

Date: 2026-08-09

## A. Baseline

```text
Project Root: /home/user/repo
Backend: /home/user/repo/backend
Branch: main
Current HEAD: 4e6cf722ee3a3ce214f0995ec53a4225cb2c87ce
Commit: P3.44: Pre-Installation Repository Hardening and RADAR BOURSE Integrity
Working tree at start: DIRTY only because final handoff documentation files were untracked
Remote: https://github.com/aresmaeily/shekar-saham.git
Remote HEAD: 26a2d120b596aa298a40b2ebc6952310658f45b5
Local vs Remote: 21 ahead / 0 behind
```

P3.39 through P3.45 were not redesigned or repeated.

## B. Completed Preparation

Created/updated documentation and Windows preparation scripts only:

```text
scripts/windows/install.ps1
scripts/windows/start.ps1
scripts/windows/validate_install.ps1
scripts/windows/validate_alpha.ps1
docs/active/ALPHA_INSTALLATION_CHECKLIST.md
docs/active/ALPHA_TARGET_VALIDATION_CHECKLIST.md
docs/active/ALPHA_INSTALLATION_RUNBOOK.md
docs/active/ALPHA_INSTALLATION_GAP_ANALYSIS.md
docs/active/ALPHA_INSTALLATION_PREPARATION_FINAL_REPORT.md
```

No backend feature, architecture redesign, database migration, dependency installation, service start, target installation, production deployment, push, reset, rebase, or force push was performed.

## C. Installation Surface

Audited installation surface:

```text
README.md
.env.example
install.sh
start.sh
Dockerfile
docker-compose.yml
backend/requirements.txt
backend/app/main.py
backend/app/core/config.py
backend/app/core/security.py
backend/app/api/
backend/app/data/
frontend/
electron/
scripts/
docs/active/
docs/architecture/
```

Findings:

| Item | Status | Notes |
|---|---|---|
| `install.sh` usable for Linux/native path | PASS | Linux shell helper; not Windows-native |
| `start.sh` usable for Linux/native path | PASS | Linux shell helper; not Windows-native |
| Hard-coded backend port | PASS WITH CONFIG | default 8000, configurable by PORT/start.ps1 |
| Windows native scripts | FIXED | Added PowerShell scripts under `scripts/windows/` |
| Environment file location | PASS | root `.env` / `.env.example`; scripts preserve this |
| Database directory portability | PASS | `DATA_DIR = ROOT / data`; Windows pathlib compatible |
| Frontend path portability | PASS | `ROOT / frontend` in FastAPI |
| Electron URL | PASS | `RADAR_BOURSE_URL`, legacy fallback, then localhost |
| Startup order | PASS | env -> venv/deps -> backend -> health -> frontend -> Electron optional |
| Health check | PASS | `/api/health`, `/api/status`, `/api/live/status` documented |
| Shutdown/rollback | FIXED | Runbook/checklist/gap analysis document rollback |

## D. Windows Readiness

Windows target remains unavailable from this Linux environment:

```text
WINDOWS TARGET: NOT ACCESSIBLE FROM CURRENT ENVIRONMENT
```

Repository-side Windows readiness additions:

- `scripts/windows/validate_install.ps1`: read-only prerequisite validator.
- `scripts/windows/install.ps1`: future native alpha preparation script.
- `scripts/windows/start.ps1`: future backend startup script.
- `scripts/windows/validate_alpha.ps1`: future runtime health/frontend availability validator.

PowerShell syntax validation:

```text
NOT VERIFIED — PowerShell/pwsh not available in current Linux environment
```

## E. Dependency Readiness

From repository evidence:

```text
Python: 3.13 locally; install.sh says Python 3.10+
Backend dependencies: backend/requirements.txt
Electron dependencies: electron/package.json
Docker path: Dockerfile + docker-compose.yml optional
```

Potential Windows notes:

- `cryptography` may require wheels or build tooling if wheel unavailable; not verified on target.
- `numpy` should install from wheel on supported Python/Windows; not verified on target.
- Electron requires Node/npm and network access to install npm packages; not verified on target.

No dependency changes were made.

## F. Environment Readiness

Required/important env variables are documented in runbook/checklists and `.env.example`.

Secrets must never be printed or committed:

```text
PRIVATE_PASSWORD
API_KEY
FERNET_KEY
BRSAPI_KEY
TELEGRAM_BOT_TOKEN
BALE_BOT_TOKEN
```

Target `.env` is not established in this environment.

## G. Database Readiness

Repository evidence:

```text
SQLite DB path: /home/user/repo/data/shekar.db on local layout
Store: backend/app/data/store.py::Store
Migration: PRAGMA user_version internal mechanism
Backup: Store.backup(keep=7) to data/backups/shekar-*.db
```

On Windows target, path is project-root-relative `data\shekar.db`.

No DB migration or DB modification was executed.

## H. Backend Readiness

Backend startup command for Windows target:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start.ps1 -Port 8000
```

Underlying command:

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Backend readiness is repository-prepared, but target startup is not verified.

## I. Frontend Readiness

Repository evidence:

- Frontend served from `frontend/` by FastAPI static mount.
- Frontend API calls use relative `/api/...` paths.
- WebSocket uses same host `/ws/live`.

Target browser validation remains:

```text
NOT VERIFIED — WINDOWS TARGET REQUIRED
```

## J. Electron Readiness

Repository evidence:

```text
electron/package.json: electron ^28.0.0, electron-builder ^24.0.0
electron/main.js: RADAR_BOURSE_URL || SHEKAR_URL || http://127.0.0.1:8000
```

Electron is treated as optional for native Alpha unless owner requires desktop validation.

Target Electron validation remains NOT VERIFIED.

## K. Security Readiness

Security model is preserved:

```text
PRIVATE_MODE
AUTH_REQUIRED
API_KEY
PRIVATE_PASSWORD
FERNET_KEY
HttpOnly session cookie
WebSocket authentication
Production guard
Public/protected endpoint rules
```

Installation runbook requires secure `.env` configuration before backend startup.

No security settings were changed.

## L. Data Provider Readiness

Current known status preserved:

```text
TSETMC: mock_fallback / live_verified=false
BRSAPI: missing key / mock_fallback / live_verified=false
```

Alpha may proceed in non-live/mock mode, but must explicitly report:

```text
LIVE MARKET DATA: NOT VERIFIED
```

Live data can only be claimed after provider validation returns live data trust.

## M. Firewall/Network Readiness

Required target checks:

| Item | Required Rule | Current Status | Installation Step |
|---|---|---|---|
| localhost backend | Allow browser/Electron to access `127.0.0.1:8000` | NOT VERIFIED | Health/frontend checks |
| TCP 8000 | Free local port or custom PORT | NOT VERIFIED | Pre-install validation |
| LAN access | Optional, only if needed | NOT VERIFIED | Add firewall rule only with approval |
| Provider HTTPS | Outbound HTTPS to TSETMC/BRSAPI if live required | NOT VERIFIED | Provider validation |

No firewall rule was changed.

## N. Rollback Readiness

Rollback documented in:

```text
docs/active/ALPHA_INSTALLATION_RUNBOOK.md
docs/active/ALPHA_INSTALLATION_CHECKLIST.md
```

Rollback principles:

- Stop backend/Electron.
- Preserve logs.
- Restore application files from verified archive.
- Restore DB from `data/backups` if DB changed.
- Never rewrite Git history.

## O. Remaining Gaps

See:

```text
docs/active/ALPHA_INSTALLATION_GAP_ANALYSIS.md
```

Main gaps:

- GitHub auth missing.
- Windows target unavailable.
- BRSAPI key missing.
- Target `.env` not established.
- Browser/Electron target validation not executed.
- Live providers not verified.

## P. Blockers

| Severity | Blocker | Status |
|---|---|---|
| P0 | GitHub authentication unavailable | BLOCKED |
| P0 | Windows target unavailable | BLOCKED for target validation |
| P0 | Owner has not authorized installation | INSTALLATION NOT STARTED |
| P1 | BRSAPI_KEY missing | BLOCKED for BRSAPI live |
| P1 | TSETMC live not verified | NOT VERIFIED |
| P1 | Target `.env` not established | BLOCKED for private alpha |
| P2 | Browser E2E not run | DEFERRED |
| P2 | Electron target not validated | DEFERRED |

## Q. Exact Target Installation Procedure

Do not execute until owner approves installation.

```powershell
# 1. Acquire repository/archive
cd C:\RADAR_BOURSE\radar-bourse

# 2. Validate prerequisites
powershell -ExecutionPolicy Bypass -File .\scripts\windows\validate_install.ps1

# 3. Prepare venv/dependencies
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install.ps1

# 4. Edit .env securely
notepad .env

# 5. Start backend
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start.ps1 -Port 8000

# 6. Validate runtime from another terminal
powershell -ExecutionPolicy Bypass -File .\scripts\windows\validate_alpha.ps1
```

## R. Validation Procedure

After backend starts:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/api/status -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/api/live/status -UseBasicParsing
```

Browser:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/symbol/فملی
```

Electron optional:

```powershell
cd electron
npm install
$env:RADAR_BOURSE_URL="http://127.0.0.1:8000"
npm start
```

## S. Change Control

### Validation executed after documentation/script preparation

```text
python -m compileall -q app tests: PASS
PYTHONPATH=. pytest -q tests: 132 passed, 1 warning
python -m pyflakes app: PASS
node --check frontend/js/modules/render/trust.js: PASS
node --check frontend/js/main.js: PASS
bash -n install.sh: PASS
bash -n start.sh: PASS
PowerShell syntax/static validation: NOT VERIFIED — pwsh not available in current Linux environment
validate_alpha_environment.py: PASS, status-only, no secrets printed
validate_alpha_runtime.py: PASS, ok=true via FastAPI TestClient
validate_providers.py --source tsetmc: PASS as fallback validation, mock_fallback, live_verified=false
validate_providers.py --source brsapi: PASS as missing-key fallback validation, mock_fallback, live_verified=false
validate_frontend_static.py: PASS, ok=true
```

### Change control

```text
Code changes: NONE
Config changes: NONE
Database changes: NONE
Dependency changes: NONE
Installation: NOT STARTED
Production deployment: NOT STARTED
GitHub push: NOT ATTEMPTED
```

Created files are documentation/installation-preparation scripts only.

## T. Final Decision

```text
ALPHA INSTALLATION: READY WITH BLOCKERS
```

Blocking / not-verified items:

```text
Windows target validation: NOT VERIFIED — WINDOWS TARGET REQUIRED
Installation approval: NOT GRANTED IN THIS PHASE
GitHub sync: BLOCKED — AUTHENTICATION REQUIRED
BRSAPI live validation: BLOCKED — BRSAPI_KEY REQUIRED
TSETMC live validation: NOT VERIFIED
Browser/Electron target validation: NOT VERIFIED — WINDOWS TARGET REQUIRED
```

Repository-side package/runbook/checklist preparation is complete.
