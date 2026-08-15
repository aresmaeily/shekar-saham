#!/usr/bin/env python3
"""Provider validation harness for TSETMC/BRSAPI/mock fallback.

Safe credential handling:
- Prints only whether BRSAPI_KEY is configured, never its value.
- Reports provider source, row count, sanitized error, and data_trust.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import build_data_trust_context, get_settings  # noqa: E402
from app.data.providers import MarketDataProvider  # noqa: E402


def _sanitize_error(err: str) -> str:
    if not err:
        return ""
    # Keep semantic errors but avoid accidentally leaking long URLs/tokens.
    redacted = err.replace(os.getenv("BRSAPI_KEY", "__NO_KEY__"), "<redacted>") if os.getenv("BRSAPI_KEY") else err
    return redacted[:240]


async def _run(source: str) -> dict:
    old = os.environ.get("DATA_SOURCE")
    os.environ["DATA_SOURCE"] = source
    get_settings.cache_clear()
    provider = MarketDataProvider()
    rows = await provider.fetch()
    ts = rows[0].updated_at.timestamp() if rows and rows[0].updated_at else None
    fallback = "mock" if "mock" in (provider.last_source or "").lower() else ""
    ctx = build_data_trust_context(
        provider.last_source or "unknown",
        timestamp=ts,
        provider=provider.last_source or "unknown",
        fallback_source=fallback,
        error_code=_sanitize_error(provider.last_error),
    )
    if old is None:
        os.environ.pop("DATA_SOURCE", None)
    else:
        os.environ["DATA_SOURCE"] = old
    get_settings.cache_clear()
    return {
        "requested_source": source,
        "brsapi_key_status": "configured" if os.getenv("BRSAPI_KEY") else "missing",
        "row_count": len(rows),
        "last_source": provider.last_source,
        "last_error": _sanitize_error(provider.last_error),
        "first_symbol": rows[0].l18 if rows else None,
        "first_updated_at": rows[0].updated_at.isoformat() if rows and rows[0].updated_at else None,
        "data_trust": ctx,
        "live_verified": bool(ctx.get("live_verified") is True),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate market data provider behavior safely.")
    parser.add_argument("--source", choices=["auto", "tsetmc", "brsapi", "mock"], default="auto")
    args = parser.parse_args()
    result = asyncio.run(_run(args.source))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    # Non-live is not a script failure: it is a truthful validation result.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
