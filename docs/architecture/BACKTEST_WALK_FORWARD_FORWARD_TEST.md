# P3.27 — Backtest, Walk-Forward Test & Forward Test

Last updated: 2026-08-07

This document defines the controlled quant testing boundary for RADAR BOURSE. It is focused on the Iran market core and does not implement live trading, broker integration, paper trading accounts, AI, or new UI dashboards.

## 1. Backtest Flow

```text
Historical Data
  ↓
Data Normalization
  ↓
Strategy / Filter DSL
  ↓
Signal Generation at bar t
  ↓
Simulated Execution at bar t+1
  ↓
Position / Portfolio State
  ↓
PnL, Return, Drawdown
  ↓
Performance Metrics
  ↓
Backtest Result
```

## 2. Walk-Forward Flow

```text
Historical Dataset
  ↓
Train / Calibration Window
  ↓
Out-of-Sample Test Window
  ↓
Roll Forward
  ↓
Repeated Evaluation
  ↓
Aggregated Results
```

P3.27 does not optimize parameters in train windows. It only enforces train/test separation and executes out-of-sample windows.

## 3. Forward Test Flow

```text
Strategy
  ↓
Out-of-Sample Data Boundary
  ↓
Signal
  ↓
Simulated Execution
  ↓
Forward Performance Report
```

The forward test in P3.27 is simulated on a later data segment. It is not a live paper-trading account.

## 4. Runtime Owners

| Boundary | Path | Responsibility |
|---|---|---|
| Strategy contracts | `backend/app/domain/strategy.py` | P3.26 strategy metadata/context/signal/filter adapter. |
| Backtest engine | `backend/app/engines/backtest.py` | Simulated next-bar execution, metrics, walk-forward and forward-test primitives. |
| Market service adapter | `backend/app/services/market_service.py` | Calls `backtest_from_market`, preserves data trust and educational warnings. |
| API | `backend/app/api/routes.py` | Existing `/api/backtest/run` expanded additively. |
| Historical data | `backend/app/data/store.py` | SQLite tick/history source where available; synthetic fallback remains explicitly marked. |

## 5. Quant Safety Rules

- Entry signals are evaluated on bar `t` and entered on bar `t+1`.
- Exit filter signals are evaluated on bar `t` and exited on `t+1` when possible.
- Take-profit/stop-loss use only bars after entry.
- Walk-forward test windows exclude train indexes.
- Forward test uses a later index/timestamp boundary.
- Mock/synthetic data is never labelled live.

## 6. Metrics Contract

Backtest/forward reports include:

- total return
- net profit/loss
- number of trades
- win rate
- average win
- average loss
- average return
- median return
- profit factor
- maximum drawdown
- Sharpe ratio when enough trades exist
- equity curve
- trade samples
- `data_trust`
- warnings
- quant safety metadata

## 7. API Contract

Existing endpoint preserved:

```text
POST /api/backtest/run
```

Additive request fields:

```text
strategy_filter
exit_filter
slippage_pct
capital
position_size_pct
walk_forward
forward_test
```

Existing threshold-based behavior remains supported through `entry_threshold` and `exit_threshold`.

## 8. Non-goals

P3.27 does not implement:

- live trading
- broker integration
- real paper-trading account
- AI optimization
- walk-forward parameter optimization
- dashboard/UI redesign
- new market expansion
- strategy marketplace
