# P3.24 — Iran Market Architecture Lock

Last updated: 2026-08-07

This document locks the current product architecture boundaries for RADAR BOURSE / رادار بورس. It does not introduce a new feature, engine, market, dashboard, AI capability, or UI redesign.

## 1. Product Direction

Primary product focus:

```text
Iran Market First
Windows Desktop as the main product surface
Global-ready architecture without global-market expansion in P3.24
```

The existing Iran market capabilities must remain intact:

- screener / entry and exit signals
- smart money and buy power metrics
- hot money
- big moves
- industry flow
- market map
- filter DSL and saved filters
- score/confluence outputs
- AI explainability
- backtest
- options calculator
- risk manager
- anomaly detection
- data quality
- WebSocket live feed
- notifications
- private mode/authentication
- chart and symbol page
- watchlist, portfolio, alerts

## 2. Locked Architecture Flow

The current architecture is locked as this product flow:

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

## 3. Layer Boundaries

| Layer | Current owner paths | Boundary |
|---|---|---|
| Market Data | `backend/app/data/providers.py`, `backend/app/data/mock_market.py`, `backend/app/data/forex_provider.py` | Fetches or generates raw market inputs. Network/disk access belongs here, not in engines. |
| Normalization / Adapters | `backend/app/data/providers.py`, `backend/app/models/schemas.py` | Converts provider data into internal snapshots and schemas. |
| Iran Market Domain | `backend/app/models/schemas.py`, `backend/app/services/market_service.py` | Iran stock market is the primary domain. Global markets remain isolated extension/scaffold. |
| Indicators / Metrics | `backend/app/engines/metrics.py`, `backend/app/engines/indicators.py`, `backend/app/engines/tablocastic.py` | Pure or mostly pure calculations; should not perform provider I/O. |
| Screening / Filters | `backend/app/engines/screener.py`, `backend/app/engines/filter_dsl.py` | Produces watchlists, entry/exit lists, market game, hot money and user filters. |
| Analysis Engines | `backend/app/engines/*.py` | Engine files remain independent and testable. No current engine is removed in P3.24. |
| Decision Support | `backend/app/engines/confluence.py`, `backend/app/services/confluence_service.py`, `/api/confluence`, frontend final/excellent surfaces | Current state is confluence-based decision support, not a complete multi-role Decision Center. |
| AI Layer | `backend/app/engines/ai_explainer.py`, `/api/v07/ai-explain/{symbol}`, `/api/v08/chart/{symbol}/ai-overlay` | Current AI is rule-based explainability and support. Future LLM/Copilot/Research Agent are not implemented in P3.24. |
| Frontend | `frontend/index.html`, `frontend/symbol.html`, `frontend/js/` | Current modular frontend is kept. Large UI redesign is out of scope. |
| Windows Desktop | `electron/main.js`, `electron/package.json` | Current Electron is a desktop shell around the local backend URL; packaging/backend lifecycle is a production gap. |

## 4. Data Trust Model

Every market-intelligence output should be interpreted through these fields where available:

| Field | Meaning |
|---|---|
| `source` / provider | Provider name or fallback source such as `tsetmc`, `brsapi`, `mock_fallback`, `synthetic`. |
| `trust_level` | `live`, `mixed`, or `synthetic` as resolved by `backend/app/core/config.py`. |
| timestamp | `as_of`, tick timestamp, snapshot timestamp, or response timestamp. |
| data quality | Quality score/output from `backend/app/engines/data_quality.py`. |
| provider health | Provider metadata and errors exposed by service/provider health paths. |

Locked interpretation:

```text
LIVE      = validated live provider data.
MIXED     = live plus fallback/unknown/partial trust.
MOCK      = development/demo market generator or mock fallback.
SYNTHETIC = generated or simulated values, not validated live market data.
```

Rules:

1. Synthetic/mock data must not be presented as live.
2. Trading/notification-oriented outputs must preserve trust context.
3. No P3.24 document may claim live TSETMC/BRSAPI validation without an executed validation result.
4. Fundamental and trade-detail outputs may include synthetic/demo behavior; UX and reports must keep that risk visible.

## 5. Plugin / Adapter Boundary

Current state:

- Iran market is the primary product domain.
- Global/forex code exists as an isolated extension/scaffold under `backend/app/api/forex.py`, `backend/app/data/forex_provider.py`, and `frontend/js/modules/forex.js`.
- There is no explicit full plugin registry yet.

Locked P3.24 rule:

```text
Do not expand global markets in this phase.
Preserve extension boundaries without adding unnecessary abstractions.
```

Future plugin work, if approved later, should define explicit provider/domain contracts before adding markets.

## 6. AI Boundary

Implemented now:

- rule-based entry/exit explainability
- chart overlay explanation
- forex explanation endpoint
- data quality/anomaly/risk helper outputs

Partial:

- Decision support through confluence outputs

Planned / future only:

- AI Copilot
- LLM integration
- Research Agent
- Multi-role AI analysis
- Filter Optimizer
- Auto Improvement
- Forward Test AI
- Full Strategy Builder

P3.24 does not implement these future items.

## 7. Decision Support Boundary

Current implemented component:

```text
Confluence board + final summary + alerts/risk/quality explanations
```

Current status:

```text
Partial Decision Support, not a complete multi-role Decision Center.
```

Future Decision Center work must be explicitly scoped and approved. It should not be assumed present because `confluence.py` exists.

## 8. Frontend/API Boundary

Current preferred boundary:

```text
frontend/js/core/api.js is the main API access utility for the modular frontend.
```

Current reality:

Direct `fetch` calls still exist in multiple modules, including auth, forex, excellent renderers, tradingview renderer, symbol page, and version utilities.

P3.24 lock:

- Direct fetch occurrences are documented as technical debt.
- No large refactor is performed in P3.24 unless required for a validated regression.
- Future frontend/API cleanup should move toward a single API access boundary without breaking auth or symbol/chart flows.

## 9. Implemented / Partial / Planned Classification

| Area | Classification |
|---|---|
| Iran screener, hot money, industry, market map, filter DSL, backtest, options, risk, data quality | Implemented |
| Fundamental/trade detail with synthetic risk, Decision Support, Data Lake, Electron Windows shell, Global-ready adapter shape | Partial |
| AI Copilot, LLM Integration, Research Agent, Multi-role AI, Filter Optimizer, Auto Improvement, Forward Test, full Strategy Builder | Planned / Not implemented |

## 10. P3.24 Architecture Decision

P3.24 locks the current architecture without expanding scope:

```text
Keep the existing Iran-market engines.
Document trust and boundaries.
Update active documentation to match GitHub reality.
Do not implement new product features.
Do not remove existing Iran market capabilities.
```
