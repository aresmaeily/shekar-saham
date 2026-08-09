# RADAR BOURSE — Alpha Environment Contract

Last updated: 2026-08-09

This document defines the environment variables required for a safe Alpha deployment. It contains no real secrets.

## Required for private Alpha

| Variable | Required | Purpose | Safe example placeholder |
|---|---:|---|---|
| `PRIVATE_MODE` | Yes | Enables private owner-only API/UI mode. | `1` |
| `PRIVATE_PASSWORD` | Yes | Owner login password. Must be strong and local to deployment. | `<set-securely-on-host>` |
| `API_KEY` | Recommended | Automation/API key and fallback session secret. | `<set-securely-on-host>` |
| `FERNET_KEY` | Yes | Stable encryption key for notifier tokens at rest. | `<generate-on-host>` |
| `COOKIE_SECURE` | Yes on HTTPS | Marks auth cookie secure. | `1` |
| `TRUST_PROXY` | Only behind trusted reverse proxy | Controls forwarded IP/proxy behavior. | `1` behind Nginx/Caddy/Cloudflare tunnel, otherwise `0` |
| `CORS_ORIGINS` | Yes | Explicit allowed origins. Do not use `*` in production. | `https://your-alpha-domain.example` |
| `DATA_SOURCE` | Yes | Market data source selection. | `auto`, `tsetmc`, `brsapi`, or `mock` |
| `BRSAPI_KEY` | If using BrsApi | Required only for BRSAPI live data. | `<set-securely-on-host>` |

## Optional notifications

| Variable | Required | Purpose |
|---|---:|---|
| `NOTIFY_ENABLED` | Optional | Enable Telegram/Bale notifications. |
| `NOTIFY_ALLOW_SYNTHETIC` | Optional | Allow synthetic/mock alerts; should remain `0` for real alpha. |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token, secret. |
| `TELEGRAM_CHAT_ID` | Optional | Telegram chat id. |
| `BALE_BOT_TOKEN` | Optional | Bale bot token, secret. |
| `BALE_CHAT_ID` | Optional | Bale chat id. |

## Safety rules

1. Never commit `.env`.
2. Never paste secrets into reports or chat.
3. Mock/synthetic data must not be presented as live.
4. Real notification sending must be disabled unless data trust and destination are verified.
5. Production/Alpha with `ENV=production` must have stable authentication and encryption configuration.

## Generate Fernet key locally

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the result only in the deployment environment, not in Git.
