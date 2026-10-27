"""GOV-24/WP-3 — Playwright E2E suite for RADAR BOURSE (repo-side readiness for P3.43-2, D-24-3).

This suite exercises REAL user-visible contracts against a running instance of
the app (backend + served frontend). It is intentionally dependency-light:
only ``pytest`` + ``playwright`` are required — no pytest plugin.

Run (any machine with a running app):
    RADAR_E2E_BASE_URL=http://127.0.0.1:8000 python -m pytest e2e -q

If the app is not reachable, every test SKIPs with an honest reason — it never
fabricates a pass. NOTE (governance): a run inside the Linux container proves
the suite itself works; the canonical P3.43-2 gate is target-system E2E
validation on the owner's Windows environment and stays EXTERNALLY_BLOCKED.
"""
from __future__ import annotations

import json
import os
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("RADAR_E2E_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT_MS = int(os.environ.get("RADAR_E2E_TIMEOUT_MS", "15000"))


def _reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status < 500
    except Exception:
        return False


@pytest.fixture(scope="session")
def base_url() -> str:
    if not _reachable(BASE_URL.rstrip("/") + "/api/health"):
        pytest.skip(
            f"app under test not reachable at {BASE_URL} — start it first "
            "(e.g. uvicorn app.main:app) or set RADAR_E2E_BASE_URL; "
            "E2E never fabricates results against a missing server"
        )
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_version(base_url: str) -> str:
    with urllib.request.urlopen(base_url + "/api/health", timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ver = data.get("version")
    assert ver, f"/api/health returned no version: {data}"
    return str(ver)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context(base_url=BASE_URL)
    page = context.new_page()
    page.set_default_timeout(TIMEOUT_MS)
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page._gov24_page_errors = errors  # type: ignore[attr-defined]
    yield page
    context.close()


def page_errors(page) -> list[str]:
    return list(page._gov24_page_errors)  # type: ignore[attr-defined]
