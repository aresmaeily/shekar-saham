# Project Status — RADAR BOURSE

Last updated: 2026-08-15

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
| P3.33 | Accepted Locally — GitHub Closure Pending | Alpha Gate Audit & Target-System Handoff Preparation completed locally; target-system validations remain deferred. |
| P3.34 | Accepted Locally — GitHub Closure Pending | Alpha Target Validation Preparation completed locally with handoff checklist, runbook, tests, and full archive. |
| P3.35 | Accepted Locally — Target Launch Deferred | Alpha target validation report and full archive completed locally; actual target-system launch remains deferred. |
| P3.36 | Accepted Locally — Target Launch Deferred | Target-System Final Validation & Controlled Alpha Launch Gate completed locally; actual target Windows launch remains deferred.
| P3.37 | Accepted Locally — Target Launch Deferred | Alpha Gate Closure validation and final handoff evidence completed locally; target launch deferred.
| P3.38 | Accepted Locally — GitHub Closure Pending | Product Direction Lock, AI Intelligence Architecture, Filter Intelligence and Market Abstraction architecture lock completed locally.
| P3.39 | Accepted Locally — GitHub Closure Pending | AI Intelligence Core implementation completed locally: evidence aggregation, confidence, conflict detection, recommendation mapping and data-trust gate.
| P3.40 | Complete Locally — GitHub Closure Pending | Market Intelligence & Continuous Monitoring layer completed locally: market snapshot, regime, industry intelligence, opportunity ranking and events. |
| P3.41 | Complete Locally — GitHub Closure Pending | Filter Intelligence & Self-Optimization Engine completed locally: registry, immutable versions, performance records, backtest/walk-forward/forward-test integration, decay detection, AI analysis, proposals and human review contract. |
| P3.42 | Complete Locally — GitHub Push Blocked | Repository completion/release readiness audit plus AI ↔ Filter Intelligence integration hardening completed locally; GitHub push remains blocked by missing authentication. |
| P3.43 | Complete Locally — GitHub Push Blocked | Repository hardening and RADAR BOURSE terminology cleanup completed locally; installation remains deferred and GitHub push remains blocked by missing authentication. |
| P3.44 | Complete Locally — GitHub Push Blocked | Pre-installation repository hardening and second-pass RADAR BOURSE terminology integrity completed locally; P3.43/P3.44 backups verified and installation remains deferred. |
| P3.52 | Complete Locally — GitHub Push Blocked | Final project package and master handoff created locally; installation remains not started and GitHub sync remains blocked by authentication/remote config. |
| P3.45 | Repository-Side Inspection Complete — Target Blocked | Target validation and installation readiness inspection completed repository-side; Windows target inaccessible, installation not started. |
| P3.46 | Handoff Delivered — GitHub Push Blocked | Final handoff documentation and developer handoff archive created; no code/config/db/install changes. |
| P3.47 | Final Pre-Install Repository Closure — Ready With Target Blockers | Handoff docs, Alpha Windows preparation scripts, installation checklists/runbook/gap analysis, tests, and artifact completed locally; target installation remains not started. |

## Baseline

```text
Repository: https://github.com/aresmaeily/shekar-saham
Branch: main
Local baseline before P3.41: 5aa8b7e54154305cfe18950e34068eb23177e214
Local baseline title: P3.40: Market Intelligence and Continuous Monitoring
GitHub verified main during P3.41 local work: 26a2d120b596aa298a40b2ebc6952310658f45b5
GitHub closure: BLOCKED / NOT SYNCED in this environment
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

| P3.53 | Complete Locally — GitHub Push Blocked | Dependency environment recovered locally for repository validation, full local validation passed, final package/handoff prepared; installation remains not started and GitHub sync remains blocked. |

| P3.54 | Complete Locally — GitHub Push Blocked | Final project package and master handoff updated; external artifact delivery attempted; installation remains not started and GitHub sync remains blocked. |
| P3.55 | Complete Locally — Recovered With Blockers | Workspace recovered from verified P3.54 TempFile artifact; Git history restored; data layer restored; local validation passed; installation remains not started and GitHub sync remains blocked. |
| P3.56 | Complete Locally — GitHub Not Updated | GitHub SHA compared and confirmed stale; push blocked by missing authentication; Windows pre-install transfer prepared; installation remains not started. |
| P3.57 | Complete Locally — GitHub Still Not Updated | Re-verified LOCAL HEAD != REMOTE HEAD; push blocked again by missing authentication; repository-side validation re-passed; installation remains not started. |
| P3.58 | Complete Locally — GitHub Deferred | Filter Intelligence UI approval workflow implemented on existing review APIs; installation remains not started; GitHub sync remains deferred. |
| P3.59 | Complete Locally — GitHub Deferred | Read-only Filter Intelligence compare/performance view added; no activation; GitHub sync remains deferred. |
| P3.60 | Complete Locally — Roadmap Gate | No non-deferred repository-side feature remained; application code unchanged; GitHub and Windows remain blocked. |
| P3.61 | Complete Locally — Alpha Launch Blocked | P3.43 Alpha gates re-evaluated; local repo/tests PASS; Windows/live/GitHub remain blocked; installation not started. |
| P3.63 | Complete Locally — GitHub Deferred | Iran TSE weekday-hours MarketSession inference added; session-open is not live data; GitHub remains blocked. |
| P3.64 | Complete Locally — GitHub Deferred | Market Intelligence snapshot.market_status now uses P3.63 session inference; session-open is not live data; GitHub remains blocked. |
| P3.75 | Complete Locally — GitHub Deferred | Canonical `live_verified` added; source label + freshness cannot claim verified LIVE; fabricated avg_vol_30d removed; GitHub remains blocked. |
| P3.76 | Complete Locally — GitHub Deferred | Adversarial follow-up: closed mintable live_verified argument; primary main.js LIVE pill triple-gated; GitHub remains blocked. |
| P3.77 | Complete Locally — GitHub Deferred | Local hardening: remaining false-LIVE paths, notifier/WS/Forex/legacy, production cookie/CORS guards; GitHub remains blocked. |
| Post-P3.54 closure | Repository-side closed — external gates blocked | Independent reconstruction through HEAD `d6e56b2`; no remaining authorized local P0/P1; GitHub/Windows/live still blocked. |
| P3.78 | Complete locally — GitHub deferred | Conservative same-bar TP/SL on OHLC; walk-forward labeled non-optimizer; GitHub still blocked. |
| P3.79 | Complete locally — GitHub deferred | Public probe redaction + cookie auth + Electron origin lock; pytest 194; GitHub still blocked. |
| P3.80 | Complete locally — GitHub deferred | SW no longer caches `/api/*`; production OpenAPI/docs disabled; chart_builder bare except removed. |
| P3.81 | Complete locally — AI contracts only | Provider adapter + Research/Strategy/Risk contracts; no live LLM invocation; GitHub still blocked. |
| P3.82 | Complete locally — AI path trust audit | Re-verified P3.81 artifact/GitHub; closed remaining AI-adjacent routes without data_trust; no LLM call. |
