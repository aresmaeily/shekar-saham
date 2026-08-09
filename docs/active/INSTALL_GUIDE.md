# 🚀 راهنمای نصب آسان — رادار بورس v4

سه روش نصب، از ساده تا حرفه‌ای:

## روش ۱ — نصب خودکار (ساده‌ترین)

```bash
cd shekar-saham
./install.sh            # نصب بومی + اجرا
# یا
./install.sh --docker   # با Docker Compose
```

بعد از اجرا: مرورگر → `http://localhost:8000`

## روش ۲ — دستی (بومی)

```bash
cd shekar-saham/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

## روش ۳ — Docker (تکرارپذیر)

```bash
cd shekar-saham
cp .env.example .env   # رمزها را تغییر دهید
docker compose up --build -d
```

---

## ⚙️ تنظیمات اجباری قبل از استقرار (.env)

| متغیر | پیشنهاد |
|-------|---------|
| `PRIVATE_PASSWORD` | رمز قوی ۲۰+ کاراکتر |
| `API_KEY` | `openssl rand -hex 24` |
| `FERNET_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `COOKIE_SECURE` | `1` روی HTTPS |
| `TRUST_PROXY` | `1` فقط پشت Nginx/Caddy |

## 🧪 بررسی سلامت

```bash
curl http://localhost:8000/api/health   # → {"ok": true, ...}
```

## 📁 داده و بکاپ

- دیتابیس: `data/shekar.db` (SQLite)
- بکاپ خودکار روزانه: `data/backups/shekar-<date>.db` (۷ نسخه آخر)

## 🐛 راهنمای عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| `pip install` خطای resolution | `python3 -m pip install --upgrade pip` سپس دوباره |
| پورت ۸۰۰۰ اشغال | `PORT=8080 ./install.sh` |
| رمز فراموش شد | در `.env` مقدار `PRIVATE_PASSWORD` را عوض و سرور را ری‌استارت کنید |
| داده‌ها به‌روز نمی‌شوند | `DATA_SOURCE=auto` — اگر TSETMC در دسترس نباشد، `source=mock` در هدر سلام نمایش داده می‌شود |
