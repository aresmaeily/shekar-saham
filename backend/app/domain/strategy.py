"""Strategy framework contracts for future Iran-market strategy execution.

P3.26 scope is contract/framework only. This module does not implement
backtesting, forward testing, paper trading, broker integration, or live trading.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.engines.filter_dsl import FilterError, run_filter, validate_filter


class StrategySignalSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    WATCH = "watch"
    NEUTRAL = "neutral"


class StrategyMetadata(BaseModel):
    id: str
    name: str
    version: str = "0.1.0"
    description: str = ""
    market: str = "iran"
    author: str = "radar-bourse"
    tags: list[str] = Field(default_factory=list)


class StrategySignal(BaseModel):
    symbol: str
    side: StrategySignalSide = StrategySignalSide.WATCH
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class StrategyContext(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    data_trust: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class Strategy(Protocol):
    metadata: StrategyMetadata

    def validate(self) -> dict[str, Any]:
        ...

    def generate(self, context: StrategyContext) -> list[StrategySignal]:
        ...


class FilterStrategy:
    """Minimal strategy adapter backed by the existing safe Filter DSL.

    It provides the strategy contract boundary needed by future backtest,
    walk-forward and forward-test phases without implementing those phases.
    """

    def __init__(
        self,
        metadata: StrategyMetadata,
        entry_filter: str,
        *,
        side: StrategySignalSide = StrategySignalSide.WATCH,
        score_field: str = "entry_score",
    ) -> None:
        self.metadata = metadata
        self.entry_filter = entry_filter
        self.side = side
        self.score_field = score_field

    def validate(self) -> dict[str, Any]:
        result = validate_filter(self.entry_filter)
        return {"ok": True, "strategy": self.metadata.model_dump(mode="json"), "filter": result}

    def generate(self, context: StrategyContext) -> list[StrategySignal]:
        try:
            rows = run_filter(self.entry_filter, context.rows)
        except FilterError:
            raise
        signals: list[StrategySignal] = []
        for row in rows:
            score = float(row.get(self.score_field) or row.get("score") or 0.0)
            signals.append(
                StrategySignal(
                    symbol=str(row.get("symbol") or ""),
                    side=self.side,
                    score=score,
                    reasons=list(row.get("reasons") or []),
                    payload={
                        "row": row,
                        "data_trust": context.data_trust,
                        "strategy_id": self.metadata.id,
                    },
                )
            )
        return signals


class StrategyRegistry:
    """In-memory strategy registry boundary for future plugin integration."""

    def __init__(self) -> None:
        self._items: dict[str, Strategy] = {}

    def register(self, strategy: Strategy) -> None:
        sid = strategy.metadata.id.strip()
        if not sid:
            raise ValueError("strategy id is required")
        self._items[sid] = strategy

    def get(self, strategy_id: str) -> Strategy | None:
        return self._items.get(strategy_id)

    def list_metadata(self) -> list[dict[str, Any]]:
        return [s.metadata.model_dump(mode="json") for s in self._items.values()]
