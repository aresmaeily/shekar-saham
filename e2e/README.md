# e2e/ — Playwright E2E Suite (GOV-24/WP-3, D-24-3)

Repo-side readiness for **P3.43-2 (browser E2E)**. The suite is committed so the
canonical *target-system* E2E validation has a real, versioned suite to run —
until now the repo had none.

## What it covers (user-visible contracts)

| Test | Contract |
|---|---|
| `test_health_ok_and_version_present` | `/api/health` answers `ok:true` with a version string |
| `test_responses_carry_request_id` | every response carries `X-Request-ID` (WS-HARDEN-1/W2 outermost middleware) |
| `test_ui_version_badge_matches_api` | UI version badge equals the API version (W4 single-source sync; no fabricated version) |
| `test_hash_routing_opens_intended_tab` | `#/<tab>` deep links open the intended tab (GOV-24/WP-1 link-target contract) |
| `test_unknown_tab_falls_back_safely` | unknown hashes fall back to a valid active tab |
| `test_symbol_page_serves` | `/symbol` renders with a title and no uncaught errors |
| `test_main_dashboard_has_no_uncaught_errors` | main dashboard loads without uncaught JS errors |

## Running

Prerequisites (target or dev machine): `pip install pytest playwright` then
`playwright install chromium` (one-time browser download).

```bash
# 1. start the app (backend + served frontend)
#    Linux/dev:   uvicorn app.main:app --host 127.0.0.1 --port 8000   (from backend/)
#    Windows:     scripts/windows/start.ps1  (see ALPHA_INSTALLATION_RUNBOOK.md)
# 2. run the suite
RADAR_E2E_BASE_URL=http://127.0.0.1:8000 python -m pytest e2e -q
#    Windows PowerShell:
#    $env:RADAR_E2E_BASE_URL='http://127.0.0.1:8000'; python -m pytest e2e -q
```

If the app is not reachable, every test **skips with an explicit reason** — the
suite never fabricates a pass against a missing server.

## Governance note (read before citing results)

- A run inside the Linux **container** (or any dev box) is *test-of-the-suite*:
  it proves the suite and the app contracts work there. It does **not**
  satisfy the canonical **P3.43-2** acceptance condition, which is E2E
  validation on the owner's **Windows target** environment.
- The suite is not part of the backend battery (`pytest backend/tests`);
  it is executed explicitly and its raw output is preserved as evidence.
