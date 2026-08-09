# P3.38 — Market Abstraction Architecture

Date: 2026-08-09

## Principle

RADAR BOURSE is Iran-market-first. Global markets are future extensions. Forex is preserved as a secondary scaffold for Windows, but not expanded in P3.38.

## Conceptual Model

```text
Market
  ↓
Exchange
  ↓
Instrument
  ↓
Provider
  ↓
Normalized Market Data
  ↓
Data Trust
  ↓
Engines / AI / UI
```

## Current Active Domain

```text
Iran Market = ACTIVE PRIMARY PRODUCT
```

Current evidence:

- `backend/app/data/providers.py`
- `backend/app/models/schemas.py::SymbolSnapshot`
- `backend/app/services/market_service.py`
- Iran-market engines in `backend/app/engines/`

## Current Secondary Scaffold

```text
Forex = SECONDARY SCAFFOLD
```

Evidence:

- `backend/app/api/forex.py`
- `backend/app/data/forex_provider.py`
- `frontend/js/modules/forex.js`
- `frontend/index.html` has `data-tab="forex"`

## Deferred Future Markets

- US stocks
- crypto
- commodities
- indices
- other global markets

These must not be implemented until Iran market alpha is stable.

## No Rewrite Rule

Do not rewrite existing Iran market engines to create abstraction prematurely. Add explicit adapters only when a real new market is approved.
