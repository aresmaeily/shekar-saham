#!/usr/bin/env bash
# اجرای پلتفرم شکار سهام
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"
export DATA_SOURCE="${DATA_SOURCE:-auto}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"

# امنیت: فقط وقتی پشت پروکسی معکوس هستید (TRUST_PROXY=1) هدر X-Forwarded-For را بپذیر
# در غیر این صورت با --no-proxy-headers اجرا شو تا IP واقعی کلاینت حفظ شود و rate limit دور نزند
PROXY_FLAG="--no-proxy-headers"
if [ "${TRUST_PROXY:-0}" = "1" ]; then
  PROXY_FLAG="--proxy-headers"
fi

if ! python3 -c "import fastapi,uvicorn,httpx,pydantic_settings" 2>/dev/null; then
  echo "Installing dependencies..."
  pip install -r requirements.txt
fi

echo "Starting Shekar Saham on http://${HOST}:${PORT}  (DATA_SOURCE=${DATA_SOURCE} ${PROXY_FLAG})"
exec python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT" $PROXY_FLAG
