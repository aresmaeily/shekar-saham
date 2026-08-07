# Alpha Setup Guide — RADAR BOURSE / Shekar Saham

Last updated: 2026-08-07

This guide is for restoring and running the current local Alpha candidate on the main computer. It contains no secrets.

## 1. Prerequisites

- Python 3.13+
- Git
- Optional: Docker + Docker Compose
- Optional: Node.js/npm for Electron desktop shell
- Optional: GitHub CLI or Git Credential Manager for pushing to GitHub

## 2. Restore Project

Extract the full project backup ZIP into a working folder, then enter the project directory:

```bash
cd shekar-saham
```

If the backup contains `.git`, verify history:

```bash
git status
git log --oneline --decorate -8
git branch --show-current
```

## 3. Environment Setup

Copy `.env.example` to `.env` if needed:

```bash
cp .env.example .env
```

Set strong local values only on your machine. Do not commit secrets.

Important variables:

```text
PRIVATE_MODE=1
PRIVATE_PASSWORD=<local strong password>
API_KEY=<local random key>
FERNET_KEY=<local fernet key>
DATA_SOURCE=auto
```

## 4. Install Backend Dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

## 5. Run Backend + Frontend

The FastAPI backend serves the frontend from `/`:

```bash
cd backend
PYTHONPATH=. python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Open:

```text
http://127.0.0.1:8000
```

Symbol page:

```text
http://127.0.0.1:8000/symbol/فملی
```

## 6. Electron Desktop Shell

Electron currently loads the local backend URL. Start backend first.

```bash
cd electron
npm install
npm start
```

Windows package build, when environment is ready:

```bash
npm run build
```

## 7. Tests

From repository root:

```bash
python -m compileall -q backend/app backend/tests
PYTHONPATH=backend pytest -q backend/tests
cd backend
python -m pyflakes app
```

## 8. Optional Docker

If Docker is available:

```bash
docker compose up --build
```

If Docker is not installed, mark Docker validation as Blocked/Not Executed.

## 9. Alpha Smoke Checklist

- `/api/health`
- `/api/analyze`
- `/api/filter/presets`
- `/api/backtest/run`
- `/api/ai/assistant`
- `/api/ai/analyze`
- `/api/ai/optimize`
- `/api/v08/chart/فملی`
- `/symbol/فملی`
- `/`

## 10. GitHub Recovery / Push

Current GitHub may lag behind local commits. Verify before pushing:

```bash
git remote -v
git branch --show-current
git rev-parse HEAD
git status
git log --oneline --decorate -8
git ls-remote origin refs/heads/main
```

Push only with secure credentials:

```bash
git push origin main
```

Never force push unless a human maintainer explicitly approves after reviewing history.

## 11. Known Alpha Limitations

- Live TSETMC/BRSAPI validation may require a suitable network/environment.
- AI is deterministic fallback unless future external provider is configured.
- Electron is a desktop shell around the backend and needs packaging/lifecycle work.
- Docker/browser E2E may be unavailable depending on the machine.
- Outputs based on mock/synthetic data must not be treated as live trading advice.
