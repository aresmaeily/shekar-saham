# P3.26 — Filter DSL & Strategy Framework

Last updated: 2026-08-07

This document stabilizes the existing Filter DSL and introduces the initial Strategy Framework contracts for future Iran-market strategy work. It does not implement backtest, walk-forward, forward-test, paper trading, broker integration, AI Copilot, LLM, or any new dashboard.

## 1. Current Filter Flow

```text
Filter Definition
  ↓
Normalize
  ↓
Parse
  ↓
Validate Safe AST
  ↓
Execute Against Market Row Context
  ↓
Filter Result
  ↓
Future Strategy / Backtest Consumer
```

## 2. Runtime Owners

| Boundary | Path | Responsibility |
|---|---|---|
| DSL fields/functions | `backend/app/engines/filter_dsl.py` | Declarative field/function allowlist and validation. |
| Filter row context | `backend/app/services/market_service.py::_build_filter_row` | Supplies market, metrics, tablocastic and fundamental fields. |
| Filter execution | `backend/app/services/market_service.py::run_user_filter` | Runs safe filter against cached rows and returns result contract. |
| Filter API | `backend/app/api/routes.py` | `/api/filter/run`, `/api/filter/presets`, `/api/filter/saved`. |
| Saved filters | `backend/app/data/store.py` | SQLite persistence of filter name and expression. |
| Strategy contracts | `backend/app/domain/strategy.py` | Strategy metadata/context/signal contracts and FilterStrategy adapter. |

## 3. DSL Syntax

Supported categories:

- Boolean: `and`, `or`, `not`, plus `AND`, `OR`, `NOT`, `&&`, `||` normalization.
- Comparison: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not in`.
- Arithmetic: `+`, `-`, `*`, `/` for numeric expressions.
- String contains: `contains(industry, 'فلز')` or sugar `industry contains فلز`.
- Indicator references: `sma(period)`, `avg_volume(period)`, `rsi(period)`, `high(period)`, `low(period)`.
- Persian/Arabic digits are normalized to English digits.

Example:

```text
close > sma(20) and rsi(14) < 35 and volume_ratio > 2
```

## 4. Security Model

The DSL is declarative and restricted:

- no `eval`
- no `exec`
- no dynamic imports
- no attributes (`x.__class__` rejected)
- no subscripts (`tags[0]` rejected)
- no filesystem access
- no network access
- no subprocess/shell access
- no arbitrary function calls
- expression length, AST node count and AST depth are bounded

Every expression is normalized, parsed and validated before execution.

## 5. Indicator Reference Boundary

Indicator functions read values already present in the row context; they do not fetch history or compute new historical series.

| Function | Row keys used |
|---|---|
| `sma(20)` | `sma_20`, `ma20`, `ma_20`, fallback `pl` |
| `avg_volume(20)` | `avg_volume_20`, `avg_vol_20`, `avg_vol_30d`, fallback `tvol` |
| `rsi(14)` | `rsi_14`, `rsi`, fallback `50.0` |
| `high(20)` | `high_20`, `pmax`, `tmax`, fallback `pl` |
| `low(20)` | `low_20`, `pmin`, `tmin`, fallback `pl` |

This keeps the DSL independent from network/disk/history side effects.

## 6. API Contract

`/api/filter/presets` now returns:

```json
{
  "presets": [],
  "fields": [],
  "functions": []
}
```

`/api/filter/run` remains backward compatible and now includes additive metadata:

```json
{
  "ok": true,
  "expr": "close > sma(20)",
  "normalized_expr": "close > sma(20)",
  "used_fields": ["close"],
  "used_functions": ["sma"],
  "rows": [],
  "trust_level": "synthetic",
  "data_trust": {}
}
```

Saved filters remain compatible because expressions are still persisted as plain strings.

## 7. Strategy Framework Boundary

P3.26 introduces contracts only:

- `StrategyMetadata`
- `StrategySignal`
- `StrategyContext`
- `Strategy` protocol
- `FilterStrategy`
- `StrategyRegistry`

The minimal `FilterStrategy` adapts a validated Filter DSL expression into future strategy signals, but it does not backtest, forward-test, paper trade or integrate with brokers.

Future chain:

```text
Strategy
  → Filter / Indicators
  → Signal
  → Backtest
  → Walk-Forward
  → Forward Test
  → Paper Trading
```

Only the first two boundaries are prepared in P3.26.

## 8. AI Boundary

AI remains a future consumer/producer of DSL expressions:

```text
Natural Language
  → Future AI
  → Filter DSL
  → Validation
  → Filter Execution
```

P3.26 does not implement AI Copilot, LLM, Research Agent, AI Optimizer or Multi-role AI.

## 9. Data Trust

Filter results inherit the current `data_trust` context from P3.25. Filters and strategies must not treat `mock` or `synthetic` data as `live`.

## 10. Compatibility

Backward compatibility preserved:

- existing filter expressions still work
- saved filters remain stored as strings
- old `/api/filter/run` fields remain present
- `compile_filter()` still returns a validated Python AST expression for existing internal callers
