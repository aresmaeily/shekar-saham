# P3.25 — Iran Market Data & Domain Stabilization

Last updated: 2026-08-07

This document records the stabilized data/domain boundary for the Iran market core. It does not define a new product feature.

## 1. Canonical Data Flow

```text
Provider
  ↓
Adapter
  ↓
Normalization
  ↓
Iran Market Domain
  ↓
Data Quality
  ↓
Market Service
  ↓
API Contract
  ↓
Consumer
```

## 2. Current Owners

| Boundary | Current paths | Notes |
|---|---|---|
| Provider | `backend/app/data/providers.py` | TSETMC/BRSAPI/mock fallback selection and provider health metrics. |
| Mock generator | `backend/app/data/mock_market.py` | Development/demo data. Must never be represented as live. |
| Normalized snapshot | `backend/app/models/schemas.py::SymbolSnapshot` | Current internal market-watch snapshot model. |
| Instrument domain | `backend/app/models/schemas.py::IranInstrument` | Stable symbol/instrument representation derived from `SymbolSnapshot`. |
| OHLCV domain | `backend/app/models/schemas.py::OHLCVBar` | Normalized candle contract for chart/history boundaries. |
| Session metadata | `backend/app/models/schemas.py::MarketSession` | Explicit placeholder for Iran market session metadata. Current code does not infer live open/closed state. |
| Data trust | `backend/app/core/config.py`, `backend/app/models/schemas.py::DataTrustState`, `MarketDataProvenance` | LIVE/MIXED/MOCK/SYNTHETIC separation. |
| Data quality | `backend/app/engines/data_quality.py` | Scores completeness/freshness and now respects the snapshot source. |
| Service/API propagation | `backend/app/services/market_service.py`, `backend/app/api/routes.py` | Adds `data_trust` metadata to key market-intelligence outputs without breaking existing `trust_level`. |

## 3. Data Trust States

| State | Definition | User-facing implication |
|---|---|---|
| `live` | Validated live provider data from TSETMC/BRSAPI-style sources. | Can be labelled live only after provider validation. |
| `mixed` | Cached, partial, unknown, or mixed provenance. | Must show caution. |
| `mock` | Demo/mock fallback market generator. | Must not be treated as live. |
| `synthetic` | Generated/simulated values, including bootstrap/demo computations. | Must not be treated as live. |

Backward compatibility:

```text
trust_level = live | mixed | synthetic
```

`mock` maps to legacy `trust_level=synthetic` so existing notification and UI safeguards still work. New code should inspect `data_trust.state` when it needs to distinguish mock from synthetic.

## 4. API Contract Rule

Market-intelligence responses should preserve both fields when possible:

```json
{
  "trust_level": "synthetic",
  "data_trust": {
    "state": "mock",
    "trust_level": "synthetic",
    "source": "mock_fallback",
    "provider": "mock_fallback",
    "timestamp": 1786111749.0,
    "is_live": false,
    "is_generated": true,
    "warning": "MOCK data: development/demo fallback, not validated live market data."
  }
}
```

## 5. Stabilized Contracts

### `DataTrustState`

```text
live | mixed | mock | synthetic
```

### `IranInstrument`

Stable Iran-market instrument model:

```text
symbol, name, isin, instrument_id, industry, industry_id, market, source, updated_at
```

### `OHLCVBar`

Normalized candle model:

```text
time, open, high, low, close, volume, source, trust_state
```

### `MarketSession`

Session metadata boundary:

```text
timezone, session_date, is_open, status
```

## 6. P3.25 Non-goals

P3.25 does not implement:

- new provider
- new market
- new dashboard
- AI Copilot or LLM
- Research Agent
- Multi-role AI
- Forward Test
- Strategy Builder
- Filter DSL feature expansion
- large frontend refactor
- Windows packaging

## 7. Remaining Gaps

- Live TSETMC/BRSAPI validation still needs a suitable environment.
- Full historical data contract remains partial and SQLite-backed.
- Market session open/closed inference is explicitly not implemented yet.
- Frontend can consume new `data_trust` metadata later; P3.25 keeps UI behavior unchanged.
