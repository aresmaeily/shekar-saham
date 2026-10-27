#!/bin/sh
# WS-HARDEN-1/W1: entrypoint — پورت/هاست از env می‌آید (هم‌راستا با config.py)؛ دیگر --port 8000 سخت‌کدشده نیست.
# exec برای اینکه سیگنال‌ها (SIGTERM) مستقیم به uvicorn برسند.
set -eu
HOST_VALUE="${HOST:-0.0.0.0}"
PORT_VALUE="${PORT:-8000}"
exec python -m uvicorn app.main:app --host "$HOST_VALUE" --port "$PORT_VALUE" --no-proxy-headers
