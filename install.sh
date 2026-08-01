#!/usr/bin/env bash
# ===== نصب و اجرای آسان شکار سهام v4 =====
# روش‌ها:
#   ./install.sh              → نصب بومی (Python venv) + اجرا
#   ./install.sh --docker     → ساخت و اجرا با Docker Compose
#   ./install.sh --check      → فقط بررسی پیش‌نیازها
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "🎯 شکار سهام v4 — نصب آسان"
echo "────────────────────────────────"

check_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 پیدا نشد — ابتدا Python 3.10+ نصب کنید"
    exit 1
  fi
  local v
  v=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  echo "✅ Python $v"
}

setup_env() {
  if [ ! -f .env ] && [ -f .env.example ]; then
    cp .env.example .env
    echo "✅ .env از روی نمونه ساخته شد — قبل از اجرا رمزها را تغییر دهید"
  fi
}

run_native() {
  check_python
  setup_env
  cd backend
  echo "📦 نصب وابستگی‌ها..."
  python3 -m venv .venv 2>/dev/null || true
  source .venv/bin/activate 2>/dev/null || true
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
  echo "🚀 اجرا روی http://localhost:8000  (Ctrl+C برای توقف)"
  # بارگذاری .env
  set -a; [ -f ../.env ] && source ../.env; set +a
  exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-proxy-headers
}

run_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "❌ docker پیدا نشد"
    exit 1
  fi
  setup_env
  echo "🐳 ساخت تصویر و اجرا..."
  docker compose up --build -d
  echo "✅ اجرا روی http://localhost:8000  — لاگ‌ها: docker compose logs -f"
}

case "${1:-}" in
  --docker) run_docker ;;
  --check) check_python; command -v docker >/dev/null 2>&1 && echo "✅ docker" || echo "⚠️ docker نصب نیست (اختیاری)"; echo "✅ آماده است" ;;
  *) run_native ;;
esac
