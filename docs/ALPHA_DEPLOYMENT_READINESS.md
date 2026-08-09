# RADAR BOURSE — Alpha Deployment Readiness & Deferred Live Validation

Date: 2026-08-09

This document separates what is completed now from what requires the target/main system.

## Completed Now

- Repository source inspected.
- Alpha environment contract exists: `docs/ALPHA_ENV_CONTRACT.md`.
- Alpha setup guide exists: `docs/ALPHA_SETUP_GUIDE.md`.
- Offline/local validation scripts are prepared:
  - `scripts/validate_alpha_environment.py`
  - `scripts/validate_alpha_runtime.py`
  - `scripts/validate_providers.py`
- Data Trust regression tests cover live/mixed/mock/synthetic/stale/unavailable states.
- No-false-LIVE tests exist for mock/synthetic/stale/unavailable/future timestamps.
- AI and Backtest preserve `data_trust` and warnings for non-live data.

## Deferred — Target System Required

| Item | Why blocked | Exact command | Expected result | Failure interpretation | Acceptance criterion |
|---|---|---|---|---|---|
| GitHub sync | Requires secure GitHub authentication on main computer | `git push origin main && git ls-remote origin refs/heads/main` | Remote HEAD equals local HEAD | Credential/permission/network failure | Remote HEAD exactly matches final local commit |
| TSETMC live connectivity | Requires target network and live provider access | `python scripts/validate_providers.py --source tsetmc` | `data_trust.state=live`, `is_live=true`, valid rows and timestamp | mock/stale/unavailable means not live | Valid provider response, valid timestamp, no fallback |
| BRSAPI live connectivity | Requires secure `BRSAPI_KEY` in environment | `python scripts/validate_providers.py --source brsapi` | `data_trust.state=live`, `is_live=true`, valid rows and timestamp | missing key/fallback means blocked or not live | Key configured securely, valid rows, no credential output |
| Browser E2E | Requires browser/headless environment | Open `/`, `/symbol/فملی`, run filter/backtest/AI flows | No console/network errors; trust visible | UI/network/auth failure | Trust states visible and no false LIVE display |
| Electron runtime | Requires Node/Electron environment on target | `cd electron && npm install && npm start` | App window loads backend UI | dependency/runtime failure | Window loads, API works, no fatal errors |
| Docker validation | Requires Docker | `docker compose config && docker compose build` | config/build pass | Docker unavailable/config failure | Build and health pass |

## Environment Template

Use `.env.example` as the template. Do not commit `.env`.

Important variables:

```text
PRIVATE_MODE=1
PRIVATE_PASSWORD=<set-on-host>
API_KEY=<set-on-host>
FERNET_KEY=<set-on-host>
COOKIE_SECURE=1 on HTTPS
TRUST_PROXY=1 only behind trusted proxy
CORS_ORIGINS=<alpha URL>
DATA_SOURCE=auto|tsetmc|brsapi|mock
BRSAPI_KEY=<set-on-host only if brsapi is used>
DATA_STALE_AFTER_SEC=300
```

## Rollback / Recovery

1. Keep the last full backup ZIP and SHA-256.
2. Verify Git state:

```bash
git status
git log --oneline --decorate -10
git rev-parse HEAD
```

3. If a deploy fails, stop the process and restore from the last verified backup or check out the last known good commit.
4. Never force-push or reset history without explicit owner approval.

## Safety Rules

- Mock is not live.
- Synthetic is not live.
- Stale is not live.
- Unavailable is not live.
- Backtest on non-live data is not a real performance claim.
- Fallback AI is not a live LLM provider.
