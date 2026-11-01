# ALPHA INSTALLATION RUNBOOK — RADAR BOURSE

Purpose: controlled, reversible Alpha installation procedure for Windows target. This runbook is prepared repository-side. Actual target installation is NOT STARTED until owner explicitly approves.

## 1. Preconditions

- Owner explicitly approves Alpha installation.
- Target Windows machine is available.
- Current repository state or verified archive is available.
- Secrets are provided out-of-band and never pasted into reports.
- If using GitHub, remote must be synchronized; otherwise use verified archive.

Current known blocker:

```text
GitHub remote is behind local by 21 commits. If GitHub sync is not fixed, use verified P3.44 archive or newer handoff archive.
```

> **Currency note — 2026-11-02 (additive; original text above preserved
> verbatim as the historical record).** The "behind by 21 commits" blocker is
> SUPERSEDED: `main` was published through the authorized deploy-key path
> (GOV-48, 2026-11-01) and post-publication CI remediation completed with all
> three required jobs green on `7c72f3d59d47435b53d83dad40a759d69377bca8`
> (GOV-49). The current publication chain is verified by remote read-back
> (see `docs/STATUS.md` MA-1/WS-0 row and current `git ls-remote origin main`).
> Installation from the synchronized GitHub remote is the expected path; the
> verified-archive alternative above remains valid as a fallback procedure
> only. The owner-side P3.43 gates (INSTALL instruction, Windows target
> validation, browser E2E, Electron runtime, live-provider verification) are
> unchanged — see `docs/active/P343_INSTALL_CHECKLIST.md`.

## 2. Target prerequisites

Open PowerShell as a normal user unless administrator is required by your environment.

Check tools:

```powershell
$PSVersionTable
python --version
python -m pip --version
git --version
node --version
npm --version
```

Node/npm are optional unless Electron validation is required.

Run read-only prerequisite validator after repository is available:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\validate_install.ps1
```

## 3. Repository acquisition

### Option A — GitHub, only after sync is verified

```powershell
git clone https://github.com/aresmaeily/shekar-saham.git radar-bourse
cd radar-bourse
git log --oneline -5
git rev-parse HEAD
```

Expected HEAD must match the approved handoff baseline or newer approved commit.

### Option B — Verified archive

Use the verified archive if GitHub remains stale:

```text
P3.44_RADAR_BOURSE_FULL_PROJECT_4e6cf72.zip
SHA-256: 3a8618e53cefbe4ae180ddda700a40497d81c0e83a9f6fe456be045bca6aa026
```

Extract it into a directory such as:

```text
C:\RADAR_BOURSE\radar-bourse
```

## 4. Installation

From repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install.ps1
```

This script prepares venv/dependencies and copies `.env.example` to `.env` if missing. It does not create real secrets.

## 5. Configuration

Edit `.env` manually and securely. Required for private alpha:

```text
PRIVATE_MODE=1
PRIVATE_PASSWORD=<strong local password>
API_KEY=<strong random api key>
FERNET_KEY=<stable fernet key>
DATA_SOURCE=auto
COOKIE_SECURE=0 for local HTTP alpha
TRUST_PROXY=0 unless behind trusted reverse proxy
```

Generate FERNET key locally:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Do not commit `.env`.

## 6. Database

No manual migration command exists. The app initializes SQLite on first startup:

```text
data\shekar.db
```

Ensure project/data directory is writable.

## 7. Startup

Start backend:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start.ps1 -Port 8000
```

Expected:

```text
FastAPI starts on http://0.0.0.0:8000
Local browser access: http://127.0.0.1:8000
```

Shutdown:

```text
Press Ctrl+C in the backend terminal.
```

## 8. Health

In another PowerShell window:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/api/status -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/api/live/status -UseBasicParsing
```

Or use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\validate_alpha.ps1
```

Important: app availability is not the same as live data verification.

## 9. Frontend

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/symbol/فملی
```

If private mode is enabled, validate owner login with the configured password. Do not record the password.

## 10. Electron

Electron is optional for Alpha unless owner requires desktop shell validation.

```powershell
cd electron
npm install
$env:RADAR_BOURSE_URL="http://127.0.0.1:8000"
npm start
```

Packaging:

```powershell
npm run build
```

Packaging is NOT required for native alpha unless explicitly requested.

## 11. Data Trust

Run provider checks only after backend/env is configured. Never report fallback as live.

Expected possible states:

```text
mock
synthetic
mixed
stale
unavailable
live
```

Live claim is allowed only if actual validation returns:

```text
data_trust.state = live
is_live = true
live_verified = true
```

## 12. Security

Validate:

- `/api/health` public.
- Protected endpoints reject unauthenticated requests when private/auth mode enabled.
- Login sets HttpOnly cookie.
- API key works only when configured.
- WebSocket auth behavior is correct in private mode.

## 13. Rollback

1. Stop backend/Electron.
2. Preserve logs and installation report.
3. Preserve `.env` securely if needed.
4. Restore application files from verified archive.
5. Restore DB from `data\backups\shekar-*.db` if DB was changed.
6. Do not rewrite Git history.

## 14. Troubleshooting

| Symptom | Likely Cause | Action |
|---|---|---|
| Port 8000 occupied | another process | use different `-Port` or stop process |
| 401 responses | private/auth mode | login or send X-API-Key |
| Startup guard failure | missing PRIVATE_PASSWORD/API_KEY/FERNET_KEY | fix `.env` securely |
| Provider fallback | TSETMC network/BRSAPI key unavailable | report non-live; do not claim live |
| Electron blank | backend not running or wrong URL | set `RADAR_BOURSE_URL` and retry |
| pip install fails | Python/pip/compiler/network | capture exact error; do not edit deps blindly |
