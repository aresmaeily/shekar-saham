# P3.38 — Filter Intelligence Architecture

Date: 2026-08-09

## Purpose

Filters must evolve from static screeners into measurable, versioned and auditable intelligence units for the Iran market.

## Future Filter Intelligence Loop

```text
Filter
  ↓
Backtest
  ↓
Walk-Forward
  ↓
Forward Test
  ↓
Performance Monitoring
  ↓
AI Evaluation
  ↓
KEEP / MODIFY / DISABLE / REMOVE / CREATE / COMBINE
  ↓
Human Approval
  ↓
Production Version
```

## Current Repository Evidence

Implemented now:

- Safe Filter DSL: `backend/app/engines/filter_dsl.py`
- Saved filter persistence: `backend/app/data/store.py`
- Filter API: `/api/filter/run`, `/api/filter/presets`, `/api/filter/saved`
- Strategy contract: `backend/app/domain/strategy.py`
- Backtest consumer: `backend/app/engines/backtest.py`

Not implemented now:

- persistent filter performance history
- filter versioning table
- automatic degradation detector
- production approval workflow
- AI-generated production filter activation

## Metrics Required Later

- win rate
- signal count
- false positive rate
- average return
- drawdown
- profit factor
- market regime dependency
- sector dependency
- data trust distribution
- forward performance drift

## Approval Gate

AI may recommend changes, but production filters can change only after:

```text
AI Recommendation
  ↓
Backtest
  ↓
Walk-Forward
  ↓
Forward Test
  ↓
Human Approval
  ↓
New Version
```

No automatic production mutation is allowed.
