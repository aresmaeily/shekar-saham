# Project Status — Shekar Saham

Last updated: 2026-08-07

## Current Phase Status

| Phase | Status | Evidence |
|---|---|---|
| P3.23 | Conditionally Complete — Awaiting External Actions | Local consolidation and validation completed; GitHub push and unavailable runtime validations remain external blockers. |
| P3.23-R1 | Conditionally Complete — Awaiting External Actions | Closure revision implemented locally; final acceptance depends on secure GitHub push plus Docker/Electron runtime validation in a suitable environment. |
| P3.24 | Not Started | Explicitly blocked until P3.23 closure is accepted. |

## Product Priorities

1. Iran stock market / تابلوخوانی
2. Existing AI and explainability capabilities
3. Windows desktop via Electron
4. Global markets remain scaffold-only for now

## Active Application Surfaces

- Backend: `backend/app`
- Main API routers: `backend/app/api/routes.py`, `backend/app/api/excellent.py`, `backend/app/api/chart.py`, `backend/app/api/forex.py`, `backend/app/api/auth.py`
- Frontend entry point: `frontend/index.html` with module entry `frontend/js/main.js`
- Symbol page: `frontend/symbol.html` with `frontend/js/symbol.js`
- Desktop shell: `electron/main.js`

## Documentation Layout

- `docs/STATUS.md`: current phase and repository status
- `docs/CHANGELOG.md`: consolidated high-level changelog
- `docs/architecture/`: active architecture/reference documents
- `docs/active/`: active user/operator documents
- `docs/archive/phase-reports/`: historical reports, changelogs, audits, and superseded phase reports

## Known Blockers

- GitHub push requires secure credentials and cannot be completed in the current environment.
- Docker runtime validation cannot be executed because Docker is not installed in the current environment.
- Full Electron runtime/package validation requires installing Electron dependencies and, for meaningful runtime testing, a backend process or packaged backend strategy.
