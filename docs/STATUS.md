# Project Status — Shekar Saham

Last updated: 2026-08-07

## Current Phase Status

| Phase | Status | Evidence |
|---|---|---|
| P3.23 | Completed | GitHub `main` contains `a00a0f4befb5582829b7fae2a8e248eaa7f4c4b8` and the closing P3.23-R1 commit. |
| P3.23-R1 | Completed | GitHub `main` verified at `26a2d120b596aa298a40b2ebc6952310658f45b5`. |
| P3.24 | Validated Locally — GitHub Closure Pending | Core product consolidation and Iran market architecture lock completed as documentation-only work; available validations passed; external runtime validations remain blocked/not executed as documented. |
| P3.25 | Accepted Locally — GitHub Closure Pending | Iran market data/domain stabilization completed locally with verified backup; GitHub push remains credential-dependent. |
| P3.26 | Accepted Locally — GitHub Closure Pending | Filter DSL and Strategy Framework completed locally with verified backup; GitHub push remains credential-dependent. |
| P3.27 | Accepted Locally — GitHub Closure Pending | Backtest, Walk-Forward and Forward Test completed locally with verified backup; GitHub push remains credential-dependent. |
| P3.28 | Accepted Locally — GitHub Closure Pending | Controlled AI Assistant/Analyst/Optimizer plus Alpha readiness and transfer package completed locally. |
| P3.30 | Accepted Locally — GitHub Closure Pending | Alpha Completion Gate completed locally; security hardening validated; GitHub push remains credential-dependent. |
| P3.31 | Accepted Locally — GitHub Closure Pending | Live Data & Data Trust Hardening completed locally; stale/unavailable states and no-false-LIVE tests passed. |
| P3.32 | Accepted Locally — GitHub Closure Pending | Alpha Deployment Readiness & Deferred Live Validation completed locally with scripts, tests, and backup; target-system validations remain deferred. |
| P3.33 | In Progress | Alpha Gate Audit & Target-System Handoff Preparation; no feature development.

## Baseline

```text
Repository: https://github.com/aresmaeily/shekar-saham
Branch: main
Baseline commit: 26a2d120b596aa298a40b2ebc6952310658f45b5
Baseline title: P3.23-R1: Close repository consolidation validation
```

## Product Priorities

1. Iran stock market / تابلوخوانی
2. Existing AI explainability and decision-support context
3. Windows desktop via Electron
4. Global markets remain scaffold/future-extension only

## Active Application Surfaces

- Backend: `backend/app`
- Main API routers: `backend/app/api/routes.py`, `backend/app/api/excellent.py`, `backend/app/api/chart.py`, `backend/app/api/forex.py`, `backend/app/api/auth.py`
- Iran market engines: `backend/app/engines/screener.py`, `metrics.py`, `filter_dsl.py`, `tablocastic.py`, `big_moves.py`, `market_map.py`, `confluence.py`
- Data layer: `backend/app/data/providers.py`, `backend/app/data/mock_market.py`, `backend/app/data/store.py`
- Frontend entry point: `frontend/index.html` with module entry `frontend/js/main.js`
- Symbol page: `frontend/symbol.html` with `frontend/js/symbol.js`
- Desktop shell: `electron/main.js`
- Android scaffold: `android-app/`

## Current Architecture Lock

P3.24 locks the current flow as:

```text
Market Data
  ↓
Normalization / Provider Adapters
  ↓
Iran Market Domain
  ↓
Indicators / Metrics
  ↓
Screening / Filters
  ↓
Analysis Engines
  ↓
Decision Support
  ↓
AI Explainability Layer
  ↓
Frontend
  ↓
Windows Desktop Shell
```

Details: `docs/architecture/IRAN_MARKET_ARCHITECTURE_LOCK.md`.

## Documentation Layout

- `docs/STATUS.md`: current phase and repository status
- `docs/CHANGELOG.md`: consolidated high-level changelog
- `docs/architecture/`: active architecture/reference documents
- `docs/active/`: active user/operator and phase documents
- `docs/archive/phase-reports/`: historical reports, changelogs, audits, and superseded phase reports

## Known Production Gaps

- Live TSETMC/BRSAPI validation has not been executed in the current baseline.
- Docker runtime validation depends on Docker availability in the execution environment.
- Full Electron runtime/package validation requires Electron dependencies and a backend packaging/lifecycle strategy.
- Windows is the main product surface, but current Electron is still a desktop shell around a local backend URL.
- Current AI is mostly rule-based explainability; AI Copilot, LLM integration, Research Agent, Multi-role AI, Filter Optimizer and Auto Improvement are future/planned, not implemented.
- Frontend still contains direct `fetch` calls outside the preferred API boundary.
