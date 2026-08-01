"""
anomaly.py - v0.7.0 Excellent - Creative: Anomaly detection for market manipulation
"""
from __future__ import annotations

from typing import Any, Dict, List
from app.models.schemas import SymbolSnapshot

class AnomalyDetector:
    def detect_price_jump(self, current: SymbolSnapshot, prev_tick: Dict[str, Any] = None) -> Dict[str, Any]:
        if not prev_tick:
            return {"anomaly": False, "score": 0}
        
        prev_pl = prev_tick.get("pl") or current.pl
        if prev_pl == 0:
            return {"anomaly": False, "score": 0}
        
        change_pct = abs((current.pl - prev_pl) / prev_pl * 100)
        
        # >5% jump in one tick is suspicious (except after halt)
        if change_pct > 5:
            return {
                "anomaly": True,
                "type": "price_jump",
                "score": min(100, change_pct * 10),
                "details": f"Price jumped {change_pct:.2f}% from {prev_pl} to {current.pl}",
                "severity": "high" if change_pct > 10 else "medium"
            }
        return {"anomaly": False, "score": 0}
    
    def detect_volume_spike(self, current: SymbolSnapshot, avg_vol: float = None) -> Dict[str, Any]:
        if not avg_vol or avg_vol == 0:
            return {"anomaly": False}
        
        ratio = current.tvol / avg_vol if avg_vol else 0
        if ratio > 10:
            return {
                "anomaly": True,
                "type": "volume_spike",
                "score": min(100, ratio * 5),
                "details": f"Volume {ratio:.1f}x avg ({current.tvol} vs {avg_vol})",
                "severity": "high"
            }
        return {"anomaly": False}
    
    def detect_orderbook_imbalance(self, snapshot: SymbolSnapshot) -> Dict[str, Any]:
        # If qd1 >> qo1 (10x) -> potential buy queue manipulation
        qd1 = snapshot.qd1 or 0
        qo1 = snapshot.qo1 or 0
        if qd1 > 0 and qo1 > 0:
            ratio = qd1 / qo1 if qo1 else 0
            if ratio > 10 or ratio < 0.1:
                return {
                    "anomaly": True,
                    "type": "orderbook_imbalance",
                    "score": 70,
                    "details": f"Orderbook imbalance qd1/qo1={ratio:.1f} ({qd1} vs {qo1})",
                    "severity": "medium"
                }
        return {"anomaly": False}
    
    def scan_all(self, snapshots: List[SymbolSnapshot], history_map: Dict[str, Dict] = None) -> List[Dict[str, Any]]:
        anomalies = []
        for s in snapshots:
            prev = (history_map or {}).get(s.l18)
            for detector in [self.detect_price_jump, self.detect_volume_spike, self.detect_orderbook_imbalance]:
                try:
                    if detector == self.detect_price_jump:
                        res = detector(s, prev)
                    elif detector == self.detect_volume_spike:
                        res = detector(s, getattr(s, 'avg_vol_30d', None))
                    else:
                        res = detector(s)
                    if res.get("anomaly"):
                        anomalies.append({"symbol": s.l18, **res})
                except Exception:
                    continue
        return sorted(anomalies, key=lambda x: x.get("score", 0), reverse=True)

anomaly_detector = AnomalyDetector()
