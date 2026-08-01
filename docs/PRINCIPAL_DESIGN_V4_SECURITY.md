# 🛡️ طراحی پرنسیپال v4 — بازطراحی نقاط دارای مشکل + ارتقای یکپارچگی و امنیت

> انجام‌شده توسط: طراح پرنسیپال (دیدگاه مایکروسافت) — تمرکز: امنیت عمقی، روان‌اجرا، یکپارچگی.

---

## ۱) امنیت: از «توکن در localStorage» به «نشست کوکی HttpOnly + CSRF»

### قبل (مشکل)
- توکن جلسه در `localStorage` ذخیره می‌شد → هر XSS یعنی سرقت کامل جلسه مالک.
- CSP با `'unsafe-inline'` برای script — سطح حمله باز.
- کتابخانه چارت از `unpkg.com` بدون SRI — ریسک زنجیره تأمین.
- ورود با مقایسه غیر-زمان‌ثابت (`!=`) قبل از `compare_digest`.

### بعد (طراحی جدید)
| لایه | تغییر |
|------|-------|
| **نشست** | توکن فقط در **کوکی HttpOnly + SameSite=Strict + Max-Age=24h** (`shekar_session`)؛ JS دیگر توکن را نمی‌بیند و نمی‌نگهدارد → سطح XSS به‌شدت کاهش یافت |
| **CSRF** | دفاع عمقی: روش‌های تغییردهنده (POST/PUT/PATCH/DELETE) با `Origin` خارج از هاست → **403**؛ کوکی SameSite=Strict خودش کوکی را در درخواست متقاطع نمی‌فرستد |
| **CSP v3** | `script-src 'self'` (بدون inline) · `object-src 'none'` · `base-uri 'self'` · `form-action 'self'` · فونت/استایل فقط self؛ کتابخانه چارت **محلی (vendored)** شد |
| **زنجیره تأمین** | `lightweight-charts` از CDN به `frontend/vendor/` منتقل شد → بدون SRI لازم، بدون CDN شخص ثالث |
| **ورود** | حذف مقایسه غیرزمان‌ثابت؛ فقط `hmac.compare_digest` |
| **خروج** | `POST /api/auth/logout` کوکی را پاک می‌کند |
| **WebSocket** | احراز هم از کوکی نشست (علاوه بر Bearer/API-Key) — `authorize_ws` |

**فایل‌ها:** `core/security.py` (authorize_cookie/authorize_ws) · `api/auth.py` (بازنویسی) · `main.py` (CSRF + cookie در middleware) · `core/api.js` + `modules/auth.js` (بازنویسی کوکی‌محور) · `main.js` (گیت auth بر اساس `logged_in`)

---

## ۲) روان‌اجرا و نگهداشت: مهاجرت دیتابیس + بکاپ + استاتیک

| مورد | طراحی |
|------|--------|
| **مهاجرت اسکیما** | `PRAGMA user_version` + لیست مهاجرت‌های ترتیبی در `Store._run_migrations` — دیتابیس‌های موجود با خیال راحت ارتقا می‌یابند |
| **بکاپ** | `Store.backup(keep=7)` با `wal_checkpoint(TRUNCATE)` + بکاپ خودکار روزانه در استارتاپ → `data/backups/` |
| **Cache-Control** | استاتیک: `public, max-age=3600` · HTML: `no-store` (هماهنگ با SW network-first) |
| **خطای 500** | هندلر سراسری JSON با `request_id` (بدون نشت stack trace) |
| **SW v3** | HTML/API network-first + استاتیک stale-while-revalidate + فهرست فایل‌های فعلی (رفع کش ابدی) |

---

## ۳) یکپارچگی: نسخه واحد + حذف نشت‌های global + دفاعی‌سازی

- **نسخه واحد:** بکاند `3.0.0` · manifest `3.0.0` · menus `3.0` · UI `v3.0` — همه یکجا.
- **حذف `window.__loadNotifyLog`** → ماژول‌سطح `export async function loadNotifyLog` (به‌کارگیری مستقیم).
- **رفع باگ واقعی:** فیلد خصوصی `#pendingActivate` در `router.js` اعلام نشده بود → کرش در اولین ناوبری hash.
- **رفع باگ واقعی:** آکولاد اضافی در `forms.js` (از بازسازی قبلی) → خطای parse در ESM.
- **دفاعی‌سازی:** `theme.js`/`bindNav`/`bindTopbar` با گارد null (بدون کرش وقتی DOM کامل نیست).
- **گراف ایمپورت:** ۲۳ ماژول + main.js — همگی با استاب DOM در Node لود شدند (تست خودکار).

---

## ۴) تأیید (آزمون‌های انجام‌شده)

| تست | نتیجه |
|-----|--------|
| بدون کوکی → `GET /api/analyze` | 401 ✅ |
| ورود → `Set-Cookie: shekar_session ... HttpOnly; SameSite=strict` | ✅ |
| با کوکی → `GET /api/analyze` | 200 ✅ |
| `POST /api/portfolio` با `Origin: https://evil.com` | **403** ✅ |
| `POST` با Origin هم‌مبدأ | 200 ✅ |
| `GET /api/auth/status` با کوکی معتبر | `logged_in: true` ✅ |
| `POST /api/auth/logout` → بعدش `analyze` | 401 ✅ |
| `pytest` | **49 پاس** ✅ |
| `pyflakes app/` | تمیز ✅ |
| CSP بدون `'unsafe-inline'` برای script | ✅ |
| بکاپ استارتاپ → `data/backups/shekar-*.db` | ✅ |
| گراف ایمپورت فرانت (۲۳+ ماژول) | ✅ |

> ⚠️ مرورگر واقعی در این سندباکس به‌دلیل نبود کتابخانه‌های سیستمی (`libnspr4`) قابل اجرا نبود؛ جریان‌های کوکی/CSRF با curl دقیقاً شبیه مرورگر تست شد، و گراف ماژول‌ها با Node تأیید شد. روی سیستم شما E2E مرورگر کامل می‌شود.

---

## ۵) پیکربندی پیشنهادی برای استقرار (محیط واقعی)

```bash
PRIVATE_MODE=1
PRIVATE_PASSWORD=<رمز قوی ۲۰+ کاراکتر>
API_KEY=<کلید تصادفی>
FERNET_KEY=<از .env.example>
TRUST_PROXY=1            # فقط پشت Nginx/Caddy
COOKIE_SECURE=1          # فقط روی HTTPS
```
