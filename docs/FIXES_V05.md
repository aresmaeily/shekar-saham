# اصلاحات v0.5.0 — رفع نقاط ضعف بازرسی

## P0
- **Trust level** (`synthetic|mixed|live`) در status/analyze/confluence/UI
- **Notify روی synthetic پیش‌فرض مسدود** مگر `NOTIFY_ALLOW_SYNTHETIC=1` یا `allow_synthetic`
- پیشوند `[DEMO/SYNTHETIC]` روی پیام‌ها وقتی live نیست
- **Flow coverage زمانی**: `ensure_flow_history` بر اساس عمق ثانیه نه فقط count تیک
- اگر coverage < حداقل: buy ترکیبی از حالت alert خارج و watch می‌شود
- حذف کلید پیش‌فرض BrsApi از کد
- **API Key middleware** برای مسیرهای حساس / حالت AUTH_REQUIRED
- CORS از env (`CORS_ORIGINS`) — دیگر فقط hardcode بدون گزینه نیست

## P1
- **خروج notify/WS از زیر lock طولانی** در refresh
- **کش fundamental** با TTL (پیش‌فرض ۳۰۰s)
- bootstrap تاریخچه فقط وقتی trust/live نیست (جلوگیری از آلودگی DB زنده)
- متادیتای `flow_meta` در health و جمع‌بندی

## نسخه
`0.5.0` / phase 5
