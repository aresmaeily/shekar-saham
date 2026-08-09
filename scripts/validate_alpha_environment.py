#!/usr/bin/env python3
"""Offline-safe Alpha environment validator for RADAR BOURSE.

This script prints only presence/status metadata. It never prints secret values.
It is safe to run before deployment on the target/main computer.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "README.md",
    ".env.example",
    "backend/app/main.py",
    "backend/app/core/config.py",
    "backend/app/core/security.py",
    "backend/app/services/market_service.py",
    "backend/app/services/ai_service.py",
    "backend/requirements.txt",
    "frontend/index.html",
    "frontend/symbol.html",
    "electron/package.json",
    "docs/ALPHA_SETUP_GUIDE.md",
    "docs/ALPHA_ENV_CONTRACT.md",
]

ENV_VARS = {
    "PRIVATE_MODE": "recommended_required_for_alpha",
    "PRIVATE_PASSWORD": "required_when_private_mode",
    "API_KEY": "recommended",
    "FERNET_KEY": "required_for_stable_token_encryption",
    "COOKIE_SECURE": "required_on_https",
    "TRUST_PROXY": "required_only_behind_trusted_proxy",
    "CORS_ORIGINS": "recommended_for_deployment",
    "DATA_SOURCE": "required",
    "BRSAPI_KEY": "required_only_for_brsapi",
    "DATA_STALE_AFTER_SEC": "optional_default_300",
}


def status() -> dict:
    files = {p: (ROOT / p).exists() for p in REQUIRED_PATHS}
    env = {k: {"status": "configured" if os.getenv(k) else "missing", "purpose": v} for k, v in ENV_VARS.items()}
    return {
        "ok": all(files.values()),
        "root": str(ROOT),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "files": files,
        "environment": env,
        "notes": [
            "Secret values are intentionally not printed.",
            "Missing BRSAPI_KEY blocks BRSAPI live validation but does not block mock/offline alpha.",
            "PRIVATE_PASSWORD/API_KEY/FERNET_KEY must be configured on the target system, not committed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Alpha environment readiness without exposing secrets.")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()
    result = status()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Root: {result['root']}")
        print(f"Python: {result['python']}")
        print("Files:")
        for path, ok in result["files"].items():
            print(f"  {'OK' if ok else 'MISSING'} {path}")
        print("Environment variables (status only):")
        for key, meta in result["environment"].items():
            print(f"  {key}: {meta['status']} ({meta['purpose']})")
        print("Notes:")
        for note in result["notes"]:
            print(f"  - {note}")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
