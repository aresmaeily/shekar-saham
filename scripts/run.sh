#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
export DATA_SOURCE="${DATA_SOURCE:-auto}"
# proxy_headers از app.main و TRUST_PROXY خوانده می‌شود
exec python3 -m app.main
