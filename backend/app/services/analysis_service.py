"""
analysis_service.py - v0.7.0 Excellent - Single Responsibility
"""
from __future__ import annotations

from typing import List
from app.models.schemas import SymbolSnapshot, AnalyzeResponse
from app.engines.screener import analyze_market
from app.core.runtime_settings import get_effective_settings
import logging

logger = logging.getLogger("shekar.analysis")

class AnalysisService:
    def analyze(self, symbols: List[SymbolSnapshot], source: str) -> AnalyzeResponse:
        cfg = get_effective_settings()
        return analyze_market(symbols, cfg=cfg, source=source, include_all_metrics=False)
    
analysis_service = AnalysisService()
