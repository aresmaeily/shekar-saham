# راهنمای بهره‌بردار (Operator Guide) — وب RC1 رادار بورس

- **تاریخ:** 2026-11-15 (Asia/Tehran) — مکمل «راهنمای نصب» (`RELEASE_WEB_RC1_INSTALL_GUIDE_FA_2026-11-15.md`).

## ۱. شروع/توقف/سلامت

```bash
docker compose up -d --build      # شروع
docker compose logs -f radar-bourse   # لاگ زنده
curl -s http://127.0.0.1:8000/api/health   # سلامت: {"ok":true,...}
docker compose down               # توقف (داده در ./data می‌ماند)
```

- سلامت/آمادگی: `GET /api/health` (liveness) و `GET /api/status` (وضعیت کامل؛ در حالت خصوصی خروجی بسته می‌شود).
- در لاگ راه‌اندازی، posture حکمرانی چاپ می‌شود؛ هشدار FERNET_KEY موقت را جدی بگیرید (§ نصب).

## ۲. چرخهٔ داده و برچسب اعتماد

- با `DATA_SOURCE=mock` هیچ تماس بیرونی رخ نمی‌دهد؛ همهٔ خروجی‌ها `mock/synthetic/live_verified=false`.
- سطح اعتماد هر پاسخ در `data_trust` است؛ UI آن را رندر می‌کند. **هیچ مسیری برچسب LIVE نمی‌سازد** (`verified=False` در هستهٔ trust ثابت است).
- رفتار stale: پس از `DATA_STALE_AFTER_SEC` بدون تازه‌سازی، state به `stale` می‌رود و UI صادقانه نشان می‌دهد؛ هیچ داده‌ای از کش سرویس‌ورکر برای API سرو نمی‌شود (API همیشه network-only).

## ۳. وظایف دوره‌ای

| وظیفه | دستور/مرجع | توالی پیشنهادی |
|---|---|---|
| بکاپ SQLite + تنظیمات | `docs/active/BACKUP_RESTORE_RUNBOOK.md` | روزانه پیش از بازار |
| بررسی مصرف rate-limit/خطاها | لاگ کانتینر؛ `GET /api/v07/metrics` | روزانه |
| به‌روزرسانی وابستگی‌ها | `pip-audit` در CI روی هر SHA | هر RC |
| چرخهٔ تغییر رمز/FERNET | چرخش با ری‌استارت؛ نشست‌ها بی‌اعتبار می‌شوند | هر ۹۰ روز |

## ۴. ارتقا و بازگشت (فقط-رو به جلو)

1. **ارتقا:** checkout کامیت جدید → `docker compose up -d --build` → سلامت → اثبات SHA در لاگ.
2. **بازگشت:** تصویر قبلی با SHA ثبت‌شده اجرا شود (تگ/دایجست در لاگ build-docker CI)؛ بازگشت تصمیم مالک است، نه عمل خودکار.
3. **ممنوع:** force-push، بازنویسی تاریخچه، حذف انشعاب موجود، دور زدن branch protection.

## ۵. امنیت عملیاتی

- تمام تغییردهنده‌ها پشت احراز هویت + CSRF Origin-check + rate limit لایه‌ای (۱۵۰/min عمومی، ۲۵/min سنگین، ۱۵/min حساس، ورود ۵/min).
- سرصفحه‌های امنیتی: X-Frame-Options DENY، CSP، HSTS روی HTTPS، Permissions-Policy.
- لاگ‌ها شناسهٔ درخواست دارند و مقدار حساس (رمز/توکن) در لاگ نمی‌رود؛ اسرار فقط از env.
- سرویس‌ورکر: HTML network-first، استاتیک stale-while-revalidate، API network-only — دادهٔ احراز/بازار هرگز کش نمی‌شود.
- عملیات kill-switch در `/api/alerts/ops/kill-switch` و postureهای AI-2/زمان‌بند در `/api/v10/ai2/posture` و `/api/v10/scheduler/posture` قابل مشاهده‌اند (پیش‌فرض: خاموش).

## ۶. عیب‌یابی سریع

| نشانه | بررسی اول | اقدام |
|---|---|---|
| بالا نیامدن با خطای امنیتی | `validate_security_configuration` در لاگ | placeholderهای .env را با مقادیر واقعی عوض کنید |
| `health` پاسخ نمی‌دهد | پورت/HOST؛ `docker compose ps` | تداخل پورت؛ `PORT` را عوض کنید |
| دادهٔ stale ماند | posture `data_trust` | در mock طبیعی است؛ در منبع زنده اتصال/مجوز را بررسی کنید |
| UI به‌روز نشد | نسخهٔ سرویس‌ورکر (v3-0-21) | یک بار hard-reload؛ SW جدید با cache:reload نصب می‌شود |
