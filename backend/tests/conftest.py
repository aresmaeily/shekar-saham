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
os.environ.setdefault("DATA_SOURCE", "mock")
os.environ.setdefault("BRSAPI_KEY", "")
