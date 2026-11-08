"""Offline-determinism guard for the backend test suite.

Roadmap basis: deterministic services and reproducible synthetic/paper tests
(02:110-112); tests must never depend on — or perform — live network fetches
(P3.4x local-hardening precedent; GOV-28/49 battery discipline).

Why this file exists (finding of the 2026-11-02 consolidated multi-agent
audit, Agent 2 / WS-1): with no pytest configuration at all, the default
``DATA_SOURCE=auto`` lets TestClient-based tests that touch market endpoints
reach the REAL TSETMC CDN whenever the CI/sandbox host has internet access.
The suite passed in both conditions only because its assertions are
network-agnostic — the run itself was still non-deterministic (variable
latency, variable row data, external availability dependency).

This conftest pins the suite to the deterministic offline path:
- ``DATA_SOURCE=mock``  → MarketDataProvider.fetch() routes straight to the
  in-repo synthetic board generator (providers.py `_from_mock`), never
  constructing outbound HTTP clients for market data.
- ``BRSAPI_KEY=""``     → the brsapi leg stays in its documented no-key
  early-return path (no credential, no network).

Explicitly preserved:
- Tests that set their own DATA_SOURCE (e.g. the brsapi no-key test via
  monkeypatch.setenv) are unaffected — setdefault never overrides.
- AI-provider HTTP tests keep monkeypatching ``httpx`` transports exactly as
  before; this file changes nothing about the AI provider seam.
- Nothing here touches AI2_ENABLED / verified / execution_mode, and nothing
  weakens or skips any test: it removes an environmental nondeterminism only.
"""

from __future__ import annotations

import os

# Must run before any test module imports the app (pytest imports conftest.py
# first within the tests package).
#
# MASTER-WAVE-2 hardening (W2-DATA F-4): the previous `setdefault` pin FAILED
# OPEN — a host-exported DATA_SOURCE (e.g. DATA_SOURCE=auto in the shell that
# launched pytest) silently survived and up to 14 TestClient suites could
# reach the live TSETMC provider. The guard below is FAIL-CLOSED: any
# pre-set DATA_SOURCE other than "mock" aborts the session before any test
# imports, unless the operator sets RADAR_ALLOW_LIVE_TESTS=1 (deliberate,
# explicit opt-in for live-provider tests — none exist today).
_data_source = os.environ.get("DATA_SOURCE")
if _data_source is not None and _data_source != "mock":
    if os.environ.get("RADAR_ALLOW_LIVE_TESTS") != "1":
        raise RuntimeError(
            "TEST-ISOLATION GUARD (fail-closed): DATA_SOURCE="
            f"{_data_source!r} would let tests reach live providers. "
            "Unset DATA_SOURCE (the suite pins mock), set it to 'mock', or "
            "export RADAR_ALLOW_LIVE_TESTS=1 for deliberate live-provider "
            "tests."
        )
os.environ.setdefault("DATA_SOURCE", "mock")
os.environ.setdefault("BRSAPI_KEY", "")


# ---------------------------------------------------------------------------
# OA-5 / WAVE-J (owner directive 2026-11-05): durable prediction-store
# isolation. The application default backend is the DURABLE SQLite store;
# tests get a throwaway DB per test and never write into the repository's
# DATA_DIR, and the store cache is reset so env changes take effect. This
# fixture changes nothing about DATA_SOURCE/AI gates and skips nothing.
# ---------------------------------------------------------------------------
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _prediction_store_isolation(tmp_path, monkeypatch):
    from app.services.prediction_store import reset_prediction_store_cache

    monkeypatch.setenv("PREDICTION_DB_PATH", str(tmp_path / "predictions_registry.sqlite3"))
    monkeypatch.setenv("PREDICTION_STORE_BACKEND", "sqlite")
    reset_prediction_store_cache()
    yield
    reset_prediction_store_cache()


# ---------------------------------------------------------------------------
# AI-3 research-memory durable integration (owner directive 2026-11-08 §3):
# the application default backend is the DURABLE SQLite/WAL + AES-256-GCM
# carrier; tests get a throwaway directory per test, an explicit test key
# via the D4 env override (keyring is never touched in tests), and the
# service cache is reset so env changes take effect. Skips nothing.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _research_memory_isolation(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.services.research_memory_service import (
        reset_research_memory_service_cache,
    )

    monkeypatch.setenv("RESEARCH_MEMORY_DB_DIR", str(tmp_path / "research_memory"))
    monkeypatch.setenv(
        "RADAR_RESEARCH_MEMORY_KEY", "aa" * 32
    )  # 64-hex test key (D4 env override)
    monkeypatch.delenv("RESEARCH_MEMORY_BACKEND", raising=False)
    # settings-cache hygiene (same discipline as the prediction-store suite):
    # env changes must be visible to the cached settings object.
    get_settings.cache_clear()
    reset_research_memory_service_cache()
    yield
    get_settings.cache_clear()
    reset_research_memory_service_cache()
