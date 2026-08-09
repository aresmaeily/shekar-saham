# ALPHA INSTALLATION CHECKLIST — RADAR BOURSE

Status marker legend:

```text
[PASS] = verified on target
[FAIL] = executed and failed
[NOT VERIFIED] = not executed / target unavailable
[BLOCKED] = cannot proceed until dependency/credential/access exists
```

Current state at creation: Windows target is not accessible from the current Linux environment. This checklist is READY for target use, but target statuses must be filled on the Windows machine.

## PRE-INSTALL

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| Owner approved installation | [NOT VERIFIED] | verbal/project approval | Do not install before explicit approval |
| Windows target accessible | [BLOCKED] | N/A | Current Linux environment cannot validate |
| Repository source selected | [NOT VERIFIED] | GitHub or P3.44 archive | GitHub is stale until sync completed |
| P3.44 archive available | [PASS] | `/home/user/deliverables/P3.44_RADAR_BOURSE_FULL_PROJECT_4e6cf72.zip` | SHA documented in artifact manifest |
| Disk space >= 5GB | [NOT VERIFIED] | `Get-PSDrive` | Target required |
| Memory >= 4GB recommended | [NOT VERIFIED] | `Get-CimInstance Win32_OperatingSystem` | Target required |
| Python installed | [NOT VERIFIED] | `python --version` | Python 3.13 used locally; 3.10+ minimum from script |
| Git installed | [NOT VERIFIED] | `git --version` | Required for Git acquisition path |
| Node/npm installed | [NOT VERIFIED] | `node --version`, `npm --version` | Required only for Electron path |
| PowerShell available | [NOT VERIFIED] | `$PSVersionTable` | Required for Windows scripts |
| Browser available | [NOT VERIFIED] | manual | Required for UI validation |

## INSTALL

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| Extract or clone repository | [NOT VERIFIED] | `git clone ...` or unzip archive | Prefer synced GitHub; otherwise use archive |
| Run prerequisite validation | [NOT VERIFIED] | `powershell -ExecutionPolicy Bypass -File scripts/windows/validate_install.ps1` | Read-only |
| Create `.env` | [NOT VERIFIED] | copy `.env.example` to `.env` | Never commit `.env` |
| Configure secrets | [NOT VERIFIED] | edit `.env` manually | Do not print secrets |
| Create venv | [NOT VERIFIED] | `scripts/windows/install.ps1` | Target only |
| Install backend dependencies | [NOT VERIFIED] | `scripts/windows/install.ps1` | Target only |
| Prepare data directory | [NOT VERIFIED] | `data/` exists | Installer script creates if missing |

## FIRST START

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| Backend starts | [NOT VERIFIED] | `scripts/windows/start.ps1` | Not run here |
| Port 8000 listening | [NOT VERIFIED] | `Get-NetTCPConnection -LocalPort 8000` | Unless custom PORT |
| No startup guard failure | [NOT VERIFIED] | backend logs | PRIVATE_MODE requires secret |
| SQLite initializes | [NOT VERIFIED] | data/shekar.db created | Startup behavior |

## HEALTH CHECK

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| `/api/health` | [NOT VERIFIED] | `Invoke-WebRequest http://127.0.0.1:8000/api/health` | App up |
| `/api/status` | [NOT VERIFIED] | `Invoke-WebRequest http://127.0.0.1:8000/api/status` | Market status |
| `/api/live/status` | [NOT VERIFIED] | `Invoke-WebRequest http://127.0.0.1:8000/api/live/status` | Distinguish live vs fallback |
| App availability validation | [NOT VERIFIED] | `scripts/windows/validate_alpha.ps1` | Does not prove live data |

## AUTH CHECK

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| Private mode enabled if intended | [NOT VERIFIED] | `.env` status only | Do not print password |
| Login page appears | [NOT VERIFIED] | Browser | Target/manual |
| Owner login succeeds | [NOT VERIFIED] | Browser/TestClient | Requires PRIVATE_PASSWORD |
| Protected endpoints reject unauthenticated | [NOT VERIFIED] | `/api/portfolio` | Expected 401 if private/auth |
| Protected endpoints allow authenticated | [NOT VERIFIED] | API key/session | Requires secret configured |

## DATA TRUST CHECK

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| DATA_SOURCE=mock behavior | [NOT VERIFIED] | provider validator | Non-live expected |
| DATA_SOURCE=tsetmc behavior | [NOT VERIFIED] | provider validator | Live only if data_trust live |
| DATA_SOURCE=brsapi behavior | [BLOCKED] | requires BRSAPI_KEY | Missing currently |
| DATA_SOURCE=auto behavior | [NOT VERIFIED] | provider validator | Must label fallback truthfully |
| No false live claim | [PASS] | repository rules | Must preserve |

## FRONTEND CHECK

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| `/` loads | [NOT VERIFIED] | Browser | Target required |
| `/symbol/فملی` loads | [NOT VERIFIED] | Browser | Target required |
| API calls use same origin | [PASS] | frontend source | Relative `/api` paths |
| WebSocket URL is same host | [PASS] | frontend source | `/ws/live` |
| Browser console free of critical errors | [NOT VERIFIED] | Browser devtools | Target required |

## ELECTRON CHECK

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| Electron mandatory for Alpha | [NOT VERIFIED] | product decision | Treat optional unless owner requires |
| npm install succeeds | [NOT VERIFIED] | `cd electron; npm install` | Target required |
| Electron starts | [NOT VERIFIED] | `npm start` | Backend must be running |
| RADAR_BOURSE_URL works | [NOT VERIFIED] | env var + app launch | Optional override |
| Build package succeeds | [NOT VERIFIED] | `npm run build` | Packaging not required for native alpha unless decided |

## POST-INSTALL

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| Save installation report | [NOT VERIFIED] | target report file | Include no secrets |
| Capture backend logs | [NOT VERIFIED] | log file | Required for support |
| Confirm backup path | [NOT VERIFIED] | `data/backups` | DB backup strategy |
| Confirm rollback procedure | [NOT VERIFIED] | runbook | Do not test destructively unless approved |

## ROLLBACK

| Item | Status | Evidence / Command | Notes |
|---|---|---|---|
| Stop backend | [NOT VERIFIED] | Ctrl+C/process stop | No service installed by default |
| Preserve `.env` securely | [NOT VERIFIED] | manual | Never publish secrets |
| Restore archive | [NOT VERIFIED] | unzip P3.44/P3.45 package | Use verified archive |
| Restore DB backup | [NOT VERIFIED] | copy from `data/backups` | Only if DB modified |
| No Git history rewrite | [PASS] | policy | Use revert commits if needed |
