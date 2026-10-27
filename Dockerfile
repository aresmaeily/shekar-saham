# ===== Dockerfile — رادار بورس v4 =====
# تک‌مرحله‌ای: Python + اجرای مستقیم (بدون بیلد جدا)
FROM python:3.13-slim

# جلوگیری از فایل‌های .pyc و خروجی‌های غیرتعاملی
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_SOURCE=auto \
    PORT=8000

WORKDIR /app

# وابستگی‌ها اول (بهره‌مندی از کش لایه‌ای داکر)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# کد پروژه
COPY backend/ ./backend/
COPY frontend/ ./frontend/
RUN mkdir -p ./data

# WS-HARDEN-1/W1: entrypoint — HOST/PORT از env (پیش‌فرض 0.0.0.0:8000)؛ پورت دیگر سخت‌کدشده نیست
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod 0755 /app/entrypoint.sh

ENV PYTHONPATH=/app/backend

EXPOSE 8000

# healthcheck — با هندلر health عمومی؛ پورت از env خوانده می‌شود (WS-HARDEN-1/W1)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health')" || exit 1

# اجرا با PYTHONPATH صحیح و غیرroot
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["/app/entrypoint.sh"]
