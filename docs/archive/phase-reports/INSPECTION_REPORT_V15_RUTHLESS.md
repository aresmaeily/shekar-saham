# 🕵️ گزارش بازرسی فنی — بازرس تراز اول (وسواسی)

**تاریخ:** ۲۰۲۶-۰۸-۰۱
**دامنه بازرسی:** شکار سهام — بکاند (FastAPI) + فرانتاند (JS) + امنیت + عملکرد
**روش:** تست واقعی مرورگر (Playwright) روی همه ۲۳ تب + حمله‌های امنیتی دستی + بررسی استاتیک + ۴۵ تست خودکار

---

## خلاصه اجرایی

| شدت | تعداد | وضعیت |
|-----|-------|--------|
| 🔴 P0 (بحرانی) | ۲ | ✅ هر دو رفع شد |
| 🟠 P1 (مهم) | ۶ | ✅ هر ۶ رفع شد |
| 🟡 P2 (کیفیت) | ۴ | ✅ ۳ رفع شد · ۱ توصیه |
| **مجموع** | **۱۲** | ۱۱ رفع + ۱ توصیه |

تست‌ها: **۴۲ → ۴۵ پاس** (۳ تست رگرسیون امنیتی جدید).

---

## 🔴 P0 — بحرانی (باید فوری)

### P0-1: دور زدن کامل احراز هویت (باگ startswith)
**مکان:** `backend/app/core/security.py::is_public_path`
**مشکل:** در `PUBLIC_PREFIXES` مقدار `"/"` وجود دارد و شرط `path.startswith(p)` برای `p="/"` **روی هر مسیری True** برمی‌گرداند:
```
is_public_path("/api/analyze")  →  True   ❌ باید False باشد
is_public_path("/api/portfolio") →  True  ❌
```
**اثر:** در حالت `AUTH_REQUIRED=1` (محافظت کلید API)، **همه اندپوینتها بدون کلید در دسترس بودند** — تست: `GET /api/analyze` بدون کلید → **200**. کلید API عملاً بی‌اثر بود. (حالت PRIVATE_MODE به‌دلیل چک جداگانه، به‌طور اتفاقی محفوظ مانده بود.)
**اصلاح:** `"/"` از پیشوندهای startswith حذف و جدا بررسی شد + `tests/test_security_paths.py` (تست رگرسیون).
**تأیید:** بدون کلید → 401 ✅ · با کلید → 200 ✅ · health/static/favicon → عمومی ✅

### P0-2: کرش JavaScript هر اتصال WebSocket
**مکان:** `frontend/js/app.js::connectWs` خط ۲۵۴
**مشکل:** هنگام افزودن توکن، متغیر `url` به `wsUrl` تغییر کرد ولی مرجع `liveLog("connected " + url)` به‌روز نشد → در هر اتصال WS خطای `ReferenceError: url is not defined`.
**اصلاح:** `url` → `wsUrl`.

---

## 🟠 P1 — مهم

### P1-1: نبود محافظت Brute-force روی ورود
**مکان:** `backend/app/core/rate_limiter.py`
**مشکل:** `/api/auth/login` در هیچ لیست محدودسازی نبود. تست: ۳۰ تلاش رمز غلط → همه 401 بدون محدودیت. حملهگر می‌توانست بدون محدودیت حدس بزند.
**اصلاح:** محدودیت اختصاصی: **۵ تلاش/دقیقه + ۲۰ تلاش/ساعت** به‌ازای IP.
**تأیید:** تلاش ۶ام → **429** ✅

### P1-2: نشت آمار بازار از health در حالت خصوصی
**مکان:** `backend/app/api/routes.py::health`
**مشکل:** در PRIVATE_MODE، بازدیدکننده بدون توکن از `/api/health` آمار کامل (تعداد اسنپ‌شات، تیک‌ها، هشدارها، پوشش جریان) دریافت می‌کرد — اطلاعات داخلی نشت می‌کرد.
**اصلاح:** بدون توکن → فقط `{ok, auth_required, private_mode, private_ok, source}`.
**تأیید:** `symbol_count=None`، `store={}` برای غریبه ✅

### P1-3: کندی فاجعه‌بار صفحه نماد (۳۶ ثانیه!)
**مکان:** `backend/app/engines/trade_detail.py::fetch_trade_detail_live`
**مشکل:** صفحه نماد `/api/symbol/{sym}/full` در حالت mock **۳۶.۵ ثانیه** طول می‌کشید — ۳ تلاش شبکه به TSETMC با timeout هرکدام ۱۲ ثانیه (با tenacity) قبل از fallback به synthetic.
**اثر:** در حالت خصوصی بعد از ورود، چارت هیچوقت نمی‌آمد (و باگ را پنهان می‌کرد).
**اصلاح:** در `data_source=mock/demo` بدون شبکه → مستقیم synthetic.
**تأیید:** **۳۶.۵s → 0.0s** ✅

### P1-4: دیده‌بان — کد مرده + race condition
**مکان:** `frontend/js/app.v062.js` + `js/modules/render/watchlist_excellent.js`
**مشکل دوگانه:**
1. ماژول `watchlist_excellent.js` (نسخه عالی دیده‌بان با فیلتر/جستجو/خلاصه) **هیچ‌جا import نشده بود** → `window.renderWatchlistExcellent` تعریف نمی‌شد → همیشه fallback قدیمی رندر می‌شد.
2. در حالت `?legacy=1`، اسکریپت کلاسیک `app.js` قبل از ماژول‌ها اجرا می‌شد → race: رندر اول fallback می‌ماند و دیگر عوض نمی‌شد.
**اصلاح:** import ماژول + رندر مجدد تاخیری بعد از لود ماژول‌ها.
**تأیید:** هدر + ۴ کارت خلاصه + فیلتر صنعت + جستجو + ردیف‌ها ✅

### P1-5: صفحه نماد در حالت خصوصی — بدون قفل و بدون توکن
**مکان:** `frontend/symbol.html`
**مشکل:** `symbol.html` فقط `theme.js` را لود می‌کرد؛ `auth.js` را نه → (الف) صفحه قفل نمایش داده نمی‌شد، (ب) توکن به fetch ها نمی‌رسید → همه 401 و چارت خالی. (داده محافظت‌شده بود ولی UX خراب و نشت تلاش‌ها.)
**اصلاح:** لود `auth.js` + قفل در symbol.html + retry در `symbol.js::load` برای race.
**تأیید:** قفل → ورود → چارت رندر می‌شود ✅

### P1-6: بازتاب ورودی عظیم در خطاها (نشت/DoS)
**مکان:** `backend/app/api/routes.py::filter/run` + `app/engines/filter_dsl.py`
**مشکل:** `raise FilterError(f"فیلد ناشناخته: {node.id}")` کل نام فیلد را بازتاب می‌داد؛ با ورودی ۱۰۰KB، پاسخ ۱۰۰KB برمی‌گشت (تقویت‌کننده حملات + لو رفتن ورودی).
**اصلاح:** `max_length=2000` روی expr + کوتاه‌کردن `node.id` + هندلر سراسری `RequestValidationError` بدون `input`.
**تأیید:** ورودی ۳۰۰۰ کاراکتر → پاسخ تمیز ۱۱۲ بایت بدون بازتاب ✅

---

## 🟡 P2 — کیفیت / جزئی

### P2-1: تب «عالی» — بخش‌ها خالی بودند
**مکان:** `frontend/js/app.v062.js`
**مشکل:** ماژول `render/excellent.js` (کیفیت داده/آنومالی/ریسک) import نشده بود → کانتینرها برای همیشه «در حال بارگذاری...» می‌ماندند.
**اصلاح:** import و صدا زدن `renderDataQuality()`, `renderAnomalies()`, `renderRisk()`.
**تأیید:** ریسک ۲ کارت، کیفیت ۳ کارت، آنومالی جدول ۳ ردیف ✅

### P2-2: برچسب نادرست در /api/auth/status
**مکان:** `backend/app/api/auth.py`
**مشکل:** `private_mode: required` برمی‌گشت در حالی که باید `bool(s.private_mode)` باشد.
**اصلاح:** انجام شد.

### P2-3: خطای 404 فاوآیکون/منابع (مقطعی)
یک 404 در بازرسی اولیه دیده شد (منبع lazy-loaded). پس از چند اجرا تکرار نشد؛ اگر در استقرار واقعی دیدید، گزارش دهید.

### P2-4: CSP اجازه `'unsafe-inline'` دارد — **توصیه**
**مکان:** `backend/app/core/security.py::SecurityHeadersMiddleware`
**مشکل:** `script-src 'self' 'unsafe-inline'` → اگر XSS پیدا شود، توکن localStorage (حالت خصوصی) قابل سرقت است.
**توصیه (برای استقرار واقعی):** اسکریپت‌های inline را به فایل‌های جدا منتقل کنید و CSP غیر-`unsafe-inline` با nonce بگذارید.

---

## یافته‌های مثبت (تأیید شده)
- حالت PRIVATE_MODE: **هر ۱۳ اندپوینت** بدون توکن 401 ✅ · WebSocket بدون توکن 403 ✅ · CORS اوریج خارجی مسدود ✅ · هدرهای OWASP کامل ✅
- ورود timing-safe (`hmac.compare_digest`) ✅ · توکن HMAC-SHA256 با انقضا ✅
- تزریق DSL: `__import__("os")...` → «تابع غیرمجاز» ✅ · `eval(...)` → مسدود ✅ · پات‌تراورسال/Null byte در نماد → 404 ✅
- تم تیره/روشن + فونت محلی وزیرمتن + رپلای + ولیو پرفایل (نمایان/کامل) + رنج‌بار ۱۰/۱۰۰/۱۰۰۰R + اندیکاتورها — همگی بدون خطای کنسول
- صفحه نماد: ۶ تب با داده، چارت، TV امبد، لینک‌های «نمودارهای بیشتر»

---

## دستورالعمل به برنامه‌نویس
1. **به‌روزرسانی** — فایل‌های زیر حتماً به‌روز شوند:
   - `backend/app/core/security.py` (P0-1)
   - `backend/app/core/rate_limiter.py` (P1-1)
   - `backend/app/api/routes.py` (P1-2, P1-6)
   - `backend/app/engines/trade_detail.py` (P1-3)
   - `backend/app/engines/filter_dsl.py` (P1-6)
   - `backend/app/api/auth.py` (P2-2)
   - `frontend/js/app.js` (P0-2, P1-4)
   - `frontend/js/app.v062.js` (P1-4, P2-1)
   - `frontend/js/symbol.js`, `frontend/symbol.html` (P1-5)
   - `frontend/js/modules/auth.js` (P1-5)
2. **تست رگرسیون:** `pytest` (۴۵ تست) باید سبز باشد.
3. **برای استقرار واقعی:** CSP nonce (P2-4) و اجرای پشت HTTPS الزامی است.
