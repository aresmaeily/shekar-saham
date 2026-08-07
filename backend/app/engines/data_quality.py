"""
data_quality.py - v0.7.0 Excellent - Data correctness scoring
"""
from __future__ import annotations

from typing import Any, Dict, List
import time
from app.core.config import classify_data_trust_state
from app.models.schemas import SymbolSnapshot

class DataQualityScorer:
    def score_symbol(self, snapshot: SymbolSnapshot, ticks_history: List[Dict] = None) -> Dict[str, Any]:
        score = 100
        issues = []
        trust_state = classify_data_trust_state(getattr(snapshot, "source", "unknown"))
        trust = "live" if trust_state == "live" else ("mixed" if trust_state == "mixed" else "synthetic")
        if trust_state in {"mock", "synthetic"}:
            issues.append(f"{trust_state.upper()} source: not validated live market data")
        
        # Freshness: if updated_at > 5 min ago, degrade
        if snapshot.updated_at:
            try:
                age_sec = time.time() - snapshot.updated_at.timestamp()
                if age_sec > 300:  # 5 min
                    score -= min(30, (age_sec - 300) / 60)
                    issues.append(f"Stale data: {int(age_sec)}s old")
                    trust = "mixed"
                if age_sec > 3600:
                    trust = "synthetic"
            except Exception:
                pass
        
        # Completeness
        required = ["pl", "pc", "py", "tvol", "Buy_I_Volume", "Sell_I_Volume"]
        missing = [f for f in required if getattr(snapshot, f, None) in (None, 0)]
        if missing:
            score -= len(missing) * 5
            issues.append(f"Missing fields: {missing}")
        
        # Accuracy: price should be within tmin/tmax
        if snapshot.tmin and snapshot.tmax:
            if not (snapshot.tmin <= snapshot.pl <= snapshot.tmax * 1.1):
                score -= 20
                issues.append(f"Price {snapshot.pl} out of range [{snapshot.tmin}, {snapshot.tmax}]")
        
        # Volume anomaly: tvol should not be 0 during market hours
        if snapshot.tvol == 0:
            score -= 10
            issues.append("Zero volume")
        
        # P/E sanity
        if snapshot.pe is not None and (snapshot.pe < 0 or snapshot.pe > 1000):
            score -= 5
            issues.append(f"Unusual P/E: {snapshot.pe}")
        
        return {
            "symbol": snapshot.l18,
            "score": max(0, min(100, round(score, 1))),
            "trust": trust,
            "trust_state": trust_state,
            "issues": issues,
            "age_sec": age_sec if 'age_sec' in locals() else None,
            "completeness": round((len(required)-len(missing))/len(required)*100, 1) if required else 100
        }
    
    def score_batch(self, snapshots: List[SymbolSnapshot]) -> Dict[str, Any]:
        scores = [self.score_symbol(s) for s in snapshots]
        avg_score = sum(s["score"] for s in scores) / len(scores) if scores else 0
        trust_dist = {}
        for s in scores:
            trust_dist[s["trust"]] = trust_dist.get(s["trust"], 0) + 1
        
        return {
            "avg_score": round(avg_score, 1),
            "total": len(scores),
            "trust_distribution": trust_dist,
            "low_quality": [s for s in scores if s["score"] < 70],
            "scores": scores
        }

quality_scorer = DataQualityScorer()
