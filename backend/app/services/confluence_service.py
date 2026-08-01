from __future__ import annotations
from typing import Any, Dict, List
from app.models.schemas import SymbolSnapshot
from app.engines.confluence import build_confluence_board
class ConfluenceService:
    def build(self, symbols: List[SymbolSnapshot], big_moves: List[Dict], flow_meta: Dict, trust: str, source: str, window: int = 600) -> Dict[str, Any]:
        from app.data.store import store
        ncfg = store.get_setting("notifier", {}) or {}
        board = build_confluence_board(
            symbols, big_moves,
            cfg=None,
            min_value_score=float(ncfg.get("min_value_score", 55)),
            min_combo_buy=float(ncfg.get("min_combo_buy", 70)),
            min_combo_sell=float(ncfg.get("min_combo_sell", 65)),
            flow_window_sec=window, limit=80
        )
        board["trust_level"] = trust
        board["source"] = source
        board["flow_meta"] = flow_meta
        return board

confluence_service = ConfluenceService()
