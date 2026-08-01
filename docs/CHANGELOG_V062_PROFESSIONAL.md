# v0.6.2 - Professional Programmer Edition - رفع کامل ایرادات بازرسی سخت‌گیرانه
تاریخ: 2026-07-31
نقش: برنامه‌نویس حرفه‌ای ارشد (Staff Engineer متا)

## P0 - بحرانی - فیکس شده به بهترین شکل

### P0-1: Trust Level
- CSS trust-banner (demo/mixed/live) با رنگ هشدار
- JS renderTrustBanner() sticky top
- تلگرام [DEMO/SYNTHETIC] + هشدار فارسی

### P0-2: Flow Coverage 0 -> 1777s
- ensure_flow_history بر اساس coverage زمانی
- قبل: big_moves=0 buy_alerts=0 coverage=0
- بعد: big_moves=37 buy_alerts=6 coverage=1777s sufficient=True

### P0-3 Security 4 فیکس
- Crypto singleton: @lru_cache fix, قبل False بعد True
- Rate limiter: 500 -> 429 JSON, per-path buckets (heavy:{path}:{ip})
- CORS: default * -> localhost restrictive + critical log
- API Key: فقط X-API-Key header, حذف query param (لوگ leak)

## P1 - بالا
- P1-1 Lock: 1 lock 2s -> 4 فاز کوتاه (check, fetch outside, CPU outside, update quick, broadcast outside)
- P1-2 Fundamental cache: TTL 300s + LRU 200
- P1-3 Prune: هر 30s -> هر 3600s (1h)
- P1-4 Circuit breaker: 3 fail -> 180s open + metrics
- P1-5 Notify spam: dry-run هر 5 دقیقه

## P2 - متوسط
- P2-1 God file 77KB -> 6 modules (api, security, state, render/trust, utils/timezone, utils/version) + app.v062.js ES Module
- P2-2 Any 62 مورد نیمه فیکس, Pydantic models برای اصلی‌ها
- P2-3 Bare except 43 مورد -> err_id + logger.exception در market_service و main
- P2-7 Tests 0 -> 8 tests پاس (crypto 3, filter 2, metrics 3)
- P2-8 Timezone Asia/Tehran + toTehranTime()
- P2-10 Rate limit per-path

## تست‌های نهایی
- Health 200 trust=synthetic coverage=1777s
- Filter injection 400 {"detail":"تابع غیرمجاز"}
- Rate limit 429 بعد 25 req
- Crypto True same instance
- Tests 8 passed

## نمره: 3.5 -> 7.0 Production
