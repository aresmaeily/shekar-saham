"""
metrics_prom.py - v0.7.0 Excellent - Prometheus metrics for observability - Meta standard
"""
from __future__ import annotations

import time
from typing import Dict
from collections import Counter

class MetricsRegistry:
    def __init__(self):
        self.counters: Dict[str, int] = Counter()
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = {}
        self.start_time = time.time()
    
    def inc(self, name: str, labels: Dict[str, str] = None, value: int = 1):
        key = f"{name}{self._label_str(labels)}"
        self.counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        key = f"{name}{self._label_str(labels)}"
        self.gauges[key] = value
    
    def observe(self, name: str, value: float, labels: Dict[str, str] = None):
        key = f"{name}{self._label_str(labels)}"
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
        # Keep only last 1000
        if len(self.histograms[key]) > 1000:
            self.histograms[key] = self.histograms[key][-1000:]
    
    def _label_str(self, labels):
        if not labels:
            return ""
        return "{" + ",".join(f'{k}="{v}"' for k,v in labels.items()) + "}"
    
    def to_prometheus(self) -> str:
        lines = []
        lines.append("# HELP shekar_uptime_seconds Uptime")
        lines.append("# TYPE shekar_uptime_seconds gauge")
        lines.append(f"shekar_uptime_seconds {time.time() - self.start_time}")
        
        for key, val in self.counters.items():
            lines.append(f"# TYPE {key.split('{')[0]} counter")
            lines.append(f"{key} {val}")
        
        for key, val in self.gauges.items():
            lines.append(f"# TYPE {key.split('{')[0]} gauge")
            lines.append(f"{key} {val}")
        
        for key, vals in self.histograms.items():
            if vals:
                avg = sum(vals)/len(vals)
                lines.append(f"# TYPE {key.split('{')[0]} histogram")
                lines.append(f"{key}_avg {avg}")
                lines.append(f"{key}_count {len(vals)}")
        return "\n".join(lines)

metrics = MetricsRegistry()
