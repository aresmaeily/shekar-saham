# P3.41 — Filter Intelligence Architecture

Date: 2026-08-09

## Purpose

Filters are now treated as measurable, versioned and auditable intelligence units for the Iran market. P3.41 turns the earlier architecture into backend contracts and services that can evaluate filter versions through the existing Backtest, Walk-Forward and Forward-Test primitives.

## Implemented Loop

```text
Filter Version
  ↓
Backtest
  ↓
Walk-Forward
  ↓
Forward Test
  ↓
Performance Record
  ↓
Evaluation / Decay Detection
  ↓
AI Filter Analysis
  ↓
Optimization Proposal
  ↓
Human Review Contract
```

Production mutation is not automatic. AI can analyze and propose; it cannot activate or overwrite production filters.

## Repository Evidence

Implemented in P3.41:

- Domain contracts: `backend/app/domain/filter_intelligence.py`
- Service: `backend/app/services/filter_intelligence_service.py`
- API endpoints under `/api/ai/...`
- Persistence through existing `settings_kv` in `backend/app/data/store.py`
- Tests: `backend/tests/test_filter_intelligence_service.py`
- AI Brain consumption hook: `filter_context.filter_intelligence` in `backend/app/domain/ai_intelligence.py`

Reused from earlier phases:

- Safe Filter DSL: `backend/app/engines/filter_dsl.py`
- Strategy adapter: `backend/app/domain/strategy.py`
- Backtest / Walk-Forward / Forward-Test: `backend/app/engines/backtest.py`
- Data Trust: `backend/app/core/config.py`
- Market regime context: `backend/app/services/market_intelligence_service.py`

## Filter Registry

Each filter has a stable identity and immutable versions:

- `filter_id`
- `name`
- `version`
- `description`
- `market`
- `status`
- `conditions`
- `created_at`
- `updated_at`
- `owner`
- `tags`

Statuses:

```text
DRAFT
ACTIVE
PAUSED
DEPRECATED
ARCHIVED
```

The current DSL presets are migrated into the registry as ACTIVE `v1` records. Creating a new version appends `v2`, `v3`, etc. and preserves earlier versions.

## Performance Records

`PerformanceRecord` captures:

- filter id and version
- evaluation mode: `BACKTEST`, `WALK_FORWARD`, `FORWARD_TEST`, `MONITORING`
- evaluation period
- sample size and signal count
- win rate, average/median return, profit factor, drawdown, Sharpe
- precision and false-positive rate as `NOT_AVAILABLE` when unsupported by the current engine
- stability score
- regime and regime performance
- data trust
- classification and reason codes

If data trust is non-live, records are not presented as live performance.

## Evaluation Classes

The deterministic evaluator emits:

```text
EXCELLENT
GOOD
STABLE
DEGRADING
WEAK
INVALID
INSUFFICIENT_DATA
```

Classification uses multiple dimensions: sample size, signal count, win rate, average return, profit factor, drawdown, stability and data trust. It is not a win-rate-only optimizer.

## Decay Detection

Decay detection compares historical/backtest evidence against recent and forward-test evidence. It considers sample size before emitting `PERFORMANCE_DECAY`.

A short weak period alone is not enough for removal. The output is proposal/review oriented, not automatic deactivation.

## Optimization Proposal

`OptimizationProposal` includes:

- proposal id
- current and proposed version labels
- changes
- reasoning
- expected effect
- evidence
- backtest/walk-forward/forward result placeholders
- confidence
- risk
- status

Statuses:

```text
PROPOSED
BACKTESTED
VALIDATED
APPROVED
REJECTED
ROLLED_BACK
```

P3.41 creates proposals only. Version activation remains a separate explicit human-controlled action.

## Human Approval Contract

`ProposalReview` supports:

```text
APPROVE
REJECT
REQUEST_RETEST
```

Approval does not automatically activate or mutate a production filter.

## Deferred

- 24/7 scheduler: DEFERRED.
- UI approval workflow: DEFERRED; backend API contract exists.
- Real live profitability validation: NOT EXECUTED.
- Automatic composite-filter deployment: DEFERRED; proposal concept only.
- Broker/live trading integration: out of scope and not implemented.
