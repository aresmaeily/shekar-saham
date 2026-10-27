"""GOV-24/WP-3 — E2E smoke contracts (real user-visible capabilities).

Each test maps to a user-facing guarantee:
1. health/readiness endpoint answers with a version (the UI's single source).
2. every response carries X-Request-ID (WS-HARDEN-1/W2 correlation contract).
3. the UI version badge matches the API version (W4 sync, no fabricated version).
4. hash routing deep-links open the intended tab (GOV-24/WP-1 link targets).
5. the symbol page serves and renders its shell.
6. no uncaught page errors on the main dashboard.
"""
from __future__ import annotations

import json
import urllib.request

from conftest import page_errors


def test_health_ok_and_version_present(base_url):
    with urllib.request.urlopen(base_url + "/api/health", timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
    assert data.get("ok") is True
    assert isinstance(data.get("version"), str) and data["version"]


def test_responses_carry_request_id(base_url):
    """W2: RequestIdMiddleware is outermost — every response has X-Request-ID."""
    with urllib.request.urlopen(base_url + "/api/health", timeout=10) as resp:
        rid = resp.headers.get("X-Request-ID")
    assert rid, "missing X-Request-ID response header"
    assert rid != "-"


def test_ui_version_badge_matches_api(base_url, api_version, page):
    """W4: index.html initial paint is settings.version; updateVersionFromApi()
    re-syncs it from /api/health — the badge must equal the API version."""
    page.goto("/")
    page.wait_for_function(
        "() => (document.querySelector('.ver')?.textContent || '').trim().length > 0"
    )
    badge = page.locator(".ver").inner_text().strip()
    assert badge == f"v{api_version}", f"UI badge {badge!r} != API v{api_version!r}"


def test_hash_routing_opens_intended_tab(base_url, page):
    """GOV-24/WP-1 contract: #/<tab> deep links open that tab (first-tab fallback
    for unknown ids was the bug class fixed in symbol.js)."""
    page.goto("/#/forex")
    page.wait_for_selector("#tab-forex.active")
    active = page.locator(".panel.active").get_attribute("id")
    assert active == "tab-forex"


def test_unknown_tab_falls_back_safely(base_url, page):
    page.goto("/#/definitely-not-a-tab")
    page.wait_for_selector(".panel.active")
    active = page.locator(".panel.active").get_attribute("id")
    assert active and active.startswith("tab-")


def test_symbol_page_serves(base_url, page):
    page.goto("/symbol")
    assert page.title(), "symbol page rendered an empty title"
    assert page_errors(page) == []


def test_main_dashboard_has_no_uncaught_errors(base_url, page):
    page.goto("/")
    page.wait_for_selector(".panel.active")
    page.wait_for_timeout(1000)
    assert page_errors(page) == [], f"uncaught page errors: {page_errors(page)}"
