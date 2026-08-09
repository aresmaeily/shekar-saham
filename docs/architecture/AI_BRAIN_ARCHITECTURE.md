# P3.38 — AI Brain Architecture

Date: 2026-08-09

## Purpose

RADAR BOURSE AI is the analytical brain of the Iran-market product, not merely a chat interface. Chat is only one possible UI over structured intelligence.

## North Star Flow

```text
Market Data
  ↓
Data Trust / Provenance
  ↓
Market Analysis Engine
  ↓
Feature / Signal Layer
  ↓
AI Brain
  ↓
Decision Support
  ↓
Risk / Trust Gate
  ↓
Recommendation
```

## Inputs

The AI Brain is allowed to consume controlled context only:

- market data and breadth
- symbol data
- money flow and liquidity
- technical indicators
- fundamental metrics
- filter results
- strategy results
- backtest, walk-forward and forward-test reports
- historical context
- market regime context
- data trust state

It must not directly bypass provider/domain services to call raw providers.

## Outputs

Structured output contract:

```text
decision: BUY | SELL | HOLD | WATCH | AVOID
confidence: 0.0..1.0
market_regime: ...
money_flow: ...
technical: ...
fundamental: ...
filter_score: ...
risk: LOW | MEDIUM | HIGH
reason_codes: []
evidence: []
invalidation: []
data_trust: {}
timestamp: ...
```

## Hard Rules

- No guaranteed profit.
- No guaranteed price prediction.
- No autonomous trading.
- No broker order.
- No production filter/strategy mutation without human approval.
- No LIVE claim unless data trust proves live.
- If data is mock/synthetic/stale/unavailable, confidence must be reduced or recommendation blocked.

## Current Implementation Status

Implemented now:

- rule-based AI explainability
- fallback AI Assistant / Analyst / Optimizer
- `AIIntelligenceCore` deterministic evidence aggregator
- structured intelligence endpoint: `POST /api/ai/intelligence/{symbol}`
- data trust propagation
- evidence/warning/confidence fields
- recommendation gate that blocks actionable live recommendations on non-live data

Not implemented now:

- live LLM provider
- AI Research Agent
- multi-agent AI
- continuous monitoring runtime
- autonomous strategy changes
- live trading

## P3.40 Market Intelligence Layer

Implemented after the first AI Core:

- `MarketIntelligenceSnapshot`
- `IndustryIntelligence`
- `OpportunityRank`
- `IntelligenceEvent`
- `MarketMonitoringResult`
- `MarketIntelligenceService.run_market_monitoring_cycle(...)`

The monitoring cycle is callable and testable, but no uncontrolled scheduler is enabled.

## Future Architecture Gate

Future AI work must add contracts and tests before new behavior:

```text
Context Builder → Provider Adapter → Structured Result → Safety Gate → Human Approval
```
