# 📋 گزارش بازرسی نهایی — مهندس ارشد متا

**تاریخ:** ۲۰۲۶-۰۸-۰۱
**موضوع:** `shekar-saham-v1-forex-gold-brokers-volume-profile.zip` (v4 — 153 فایل)
**روش:** تست اجرایی (pytest) + اسکن امنیتی (pip-audit) + بازبینی استاتیک (pyflakes) + تست زنده جریان امنیتی با HTTP + تست مهاجرت DB + گراف ایمپورت فرانت (Node) + بازبینی HTML/CSP.

---

## ✅ وضعیت: تأیید برای استفاده (با ۶ مورد باز — در ادامه)

| گیت | ابزار | نتیجه |
|-----|-------|--------|
| تست‌ها | `pytest` | **49 پاس** ✅ |
| کد مرده | `pyflakes app/` | **صفر** ✅ |
| آسیب‌پذیری دپندنسی | `pip-audit -r` | **No known vulnerabilities** ✅ |
| مهاجرت DB | تست روی DB قدیمی | ستون اضافه شد + `user_version=1` + داده سالم ✅ |
| گراف ایمپورت | Node (27 فایل) | ۲۶/۲۷ سالم؛ `symbol.js` فقط در استاب fail (آرتیفکت تست) ✅ |

---

## 🔐 جریان امنیتی — تأیید زنده (HTTP شبیه مرورگر)

| گام | ورودی | نتیجه |
|-----|-------|--------|
| بدون نشست | `GET /api/analyze` | **401** ✅ |
| ورود | `POST /api/auth/login` | `Set-Cookie: shekar_session … HttpOnly; SameSite=strict; Max-Age=86400` ✅ |
| با کوکی | `GET /api/analyze` | **200** ✅ |
| CSRF | `POST` با `Origin: https://evil.com` | **403** ✅ |
| CSRF هم‌مبدأ | `POST` با `Origin: http://127.0.0.1:9600` | **200** ✅ |
| خروج | `POST /api/auth/logout` → `GET analyze` | کوکی حذف → **401** ✅ |
| Brute-force | ۶ تلاش رمز غلط | `401×5 + 429×1` (محدود ۵/دقیقه) ✅ |
| ورود | فقط `hmac.compare_digest` (بدون نشت زمانی) | ✅ |

**CSP v4:** `script-src 'self'` (بدون inline) · `object-src 'none'` · `base-uri 'self'` · `frame-ancestors 'none'` ✅
**HTML:** صفر inline script · صفر CDN خارجی (کتابخانه چارت وندور شده) ✅

---

## 🧾 دستاوردهای تأییدشده در این نسخه (v4)

1. **نشست امن:** توکن فقط در کوکی HttpOnly+SameSite — از `localStorage` به امنیت عمقی ارتقا یافت.
2. **CSRF دفاع عمقی** در میدلور + SameSite=Strict.
3. **مهاجرت اسکیما** (`PRAGMA user_version`) — دیتابیس‌های موجود امن ارتقا می‌یابند (تست شد).
4. **بکاپ خودکار روزانه** با `wal_checkpoint` + نگهداری ۷ نسخه.
5. **هندلر 500 یکپارچه** با `request_id` (بدون نشت stack trace).
6. **SW v3:** network-first برای HTML/API + stale-while-revalidate استاتیک (رفع کش ابدی).
7. **Cache-Control:** استاتیک 1h · HTML no-store.
8. **قفل UI کوکی‌محور:** قفل → ورود → داده → ریلود خودکار (بر اساس `logged_in` نه localStorage).
9. **چهار باگ واقعی رفع‌شده:** `#pendingActivate` در router، آکولاد اضافی forms، `url is not defined` در WS (قبلی)، race دیده‌بان (قبلی).

---

## ⚠️ موارد باز (آگاهانه فیکس‌نشده — نیاز به تصمیم خارج از سندباکس)

| # | مورد | اولویت | پیشنهاد |
|---|------|--------|---------|
| 1 | **بدون Git** — هیچ تاریخچه/rollback | P0 | `git init` + `.gitignore` (آماده است) + commit اولیه |
| 2 | **بدون CI/CD** — هیچ pipeline | P1 | GitHub Actions: ruff → mypy → pytest → pip-audit → build |
| 3 | **بدون Dockerfile** — دپلوی غیرتکرارپذیر | P1 | Dockerfile + compose (از `start.sh` الگو بگیرید) |
| 4 | **۷۹ خطای mypy** در ۱۷ فایل | P1 | `mypy --strict` تدریجی؛ آستانه صفر در CI |
| 5 | **فرانت بدون بیلد/تست** (ESM خام) | P1 | Vite + Vitest + ESLint؛ hashed filenames |
| 6 | **`symbol.js` هنوز ۵۴۴ خط (god-file)** | P2 | همان الگوی core/components/tabs |

> موارد جزئی: README از معماری v4 عقب است · `rate limiter`/WS درون‌حافظه (تک-پروسه) · fallback بی‌صدا به mock در `auto` · بدون tracing/لاگ JSON · `/metrics` مسیر غیراستاندارد.

---

## 🎯 جمع‌بندی به صاحب پروژه

**ساختار:** ✅ این محصول حالا **مغز و اسکلت دارد** — معماری لایه‌ای، امنیت عمقی (کوکی/CSRF/CSP)، مهاجرت و بکاپ، ۴۹ تست، اسکن‌ها پاک.

**پرچم قرمز باقی‌مانده:** 🔴 بدون Git، CI و Docker، این کد هنوز «قابل حمل به تولید» نیست — **هر تغییری خطرناک و غیرقابل بازگشت است**. هفته اول نقشه قبلی (git + CI + Docker) بالاترین اولویت است.

**محدودیت محیط:** مرورگر واقعی (libnspr4) در این سندباکس در دسترس نیست؛ جریان‌های HTTP دقیقاً شبیه مرورگر تست شدند و گراف ماژول‌ها با Node تأیید شد. روی سیستم شما E2E مرورگر کامل (Playwright) اجرا می‌شود — اسکریپت‌ها در workspace هستند.

**امضا:** ✅ هیچ باگ بحرانی جدیدی در این بازرسی نهایی یافت نشد؛ نسخه برای استفاده شخصی/آزمایشی تأیید است، برای production با تکمیل موارد ۱–۳.
