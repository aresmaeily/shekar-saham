# v0.6.0 - Production Hardened - گزارش فیکس بازرسی

## P0 فیکس شده
- Flow coverage: از 0 به 600s sufficient=True -> big_moves 0 -> 9
- Trust level: در تمام APIها + banner CSS اضافه شد
- Security headers: X-Content-Type-Options, X-Frame-Options, CSP
- CORS: default از * به localhost restrictive
- Rate limit: اضافه شد (20 req/min heavy, 120 general) - قبل 500 میداد الان 429
- Crypto: singleton fix - قبل encrypt/decrypt Fail بود الان True
- BrsApi key default حذف شده بود (از v0.5)

## P1 فیکس شده
- Lock contention: از 1 lock طولانی به 3 فاز کوتاه - p95 latency کاهش
- Fundamental cache: LRU 200 + TTL 300s
- Circuit breaker: برای tsetmc/brsapi با metrics
- Notify spam: dry-run فقط هر 5 دقیقه

## P2 بهبود
- Filter DSL: injection 400 میده نه 500
- Backtest disclaimer و Options risk warning اضافه
- Frontend trust-banner CSS اضافه

## باقی‌مانده P2/P3 برای v0.7
- Frontend god file 77KB -> باید split به modules
- 62 Any usage -> باید Pydantic models
- 43 bare except -> باید err_id
- Tests: 3 تست اضافه شد (قبل 0 بود) - باید بیشتر
- Version sync: هنوز در HTML hardcode

## تست‌های بازرس
- health: 200 OK trust=synthetic coverage=600s
- injection: 400 {"detail":"تابع غیرمجاز"}
- rate limit: 429 بعد از 20 درخواست
- crypto: True

نمره: 3.5 -> 5.5/10 Production
