#!/usr/bin/env python3
"""Offline/local API smoke validator for RADAR BOURSE Alpha.

Uses FastAPI TestClient, so it validates contracts without requiring the target
Windows runtime or a network-exposed server. It does not validate live data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

CHECKS = [
    ("GET", "/api/health", None),
    ("GET", "/api/status", None),
    ("GET", "/api/analyze", None),
    ("GET", "/api/overview", None),
    ("GET", "/api/symbol/فملی", None),
    ("POST", "/api/filter/run", {"expr": "close > sma(20) and rsi(14) < 60", "limit": 3}),
    ("POST", "/api/backtest/run", {"strategy_filter": "entry_score >= 60", "bars": 80}),
    ("POST", "/api/ai/assistant", {"question": "وضعیت بازار؟"}),
    ("POST", "/api/ai/analyze", {"symbol": "فملی"}),
    ("POST", "/api/ai/optimize", {"filter_expr": "buy_power > 1.5"}),
    ("GET", "/api/fundamental/فملی/deep", None),
    ("GET", "/", None),
    ("GET", "/symbol/فملی", None),
]


def main() -> int:
    client = TestClient(app)
    results = []
    ok = True
    for method, path, payload in CHECKS:
        response = client.get(path) if method == "GET" else client.post(path, json=payload)
        item = {"method": method, "path": path, "status": response.status_code, "bytes": len(response.content)}
        if response.headers.get("content-type", "").startswith("application/json") and response.content:
            data = response.json()
            ctx = data.get("data_trust") or (data.get("result") or {}).get("data_trust") or {}
            if ctx:
                item["data_trust"] = {
                    "state": ctx.get("state"),
                    "trust_level": ctx.get("trust_level"),
                    "is_live": ctx.get("is_live"),
                    "live_verified": ctx.get("live_verified"),
                    "stale": ctx.get("stale"),
                }
        if response.status_code >= 400:
            ok = False
            item["error"] = response.text[:300]
        results.append(item)
    print(json.dumps({"ok": ok, "checks": results}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
