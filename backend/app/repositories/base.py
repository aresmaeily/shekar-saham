from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict
class SymbolRepository(ABC):
    @abstractmethod
    def save_snapshot(self, source: str, symbols: List[Dict], ticks: List[Dict], ts: float = None) -> int: pass
    @abstractmethod
    def get_ticks_since(self, since_ts: float, symbol: str = None) -> List[Dict]: pass

class AlertRepository(ABC):
    @abstractmethod
    def save_alerts(self, alerts: List[Dict]) -> int: pass
