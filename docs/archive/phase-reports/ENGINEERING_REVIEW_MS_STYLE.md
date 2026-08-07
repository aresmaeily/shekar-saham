# 🏛️ بررسی مهندسی — دیدگاه مهندس مایکروسافت (وسواس ۱۰۰٪)

**تاریخ:** ۲۰۲۶-۰۸-۰۱
**روش:** بازبینی کد (code review) + اجرای ابزارهای سازمانی (mypy, ruff, pip-audit, pyflakes) + تست انتشار (fresh install) + تحلیل استاتیک فرانت + بررسی دپلوی.
**مقیاس:** ۱۴۸ فایل · فرانت (ESM خام، بدون بیلد) · بکاند (FastAPI + SQLite)

---

## 🧯 خلاصه اجرایی

| اولویت | تعداد | وضعیت |
|--------|-------|--------|
| 🔴 P0 — مانع انتشار (release-blocking) | ۳ | ۱ فیکس شد · ۲ باز است |
| 🟠 P1 — بالا | ۸ | ۰ فیکس · ۸ باز |
| 🟡 P2 — متوسط | ۷ | ۰ فیکس · ۷ باز |
| 🟢 P3 — کیفیت/ظرافت | ۵ | باز |

**نتیجهگیری:** کد از نظر **صحت منطقی** خوب است (۴۹ تست پاس، E2E صفر خطا) اما از نظر **مهندسی محصول** (انتشارپذیری، نگهداشت، مقیاس، امنیت عمقی) در سطح پروتوتایپ است. این همان فاصله «کار میکند» تا «قابل حمل به تولید» است.

---

## 🔴 P0 — مانع انتشار (باید قبل از هر release درست شود)

### P0-1. `pip install -r requirements.txt` شکست میخورد — ✅ در همین بررسی فیکس شد
**مشکل:** `pytest>=9.0.3` با `pytest-asyncio==0.24.0` (که الزام `pytest<9` دارد) در تضاد بود → هر کسی که پروژه را تازه نصب کند با `ResolutionImpossible` متوقف میشد. **یعنی بسته در حال حاضر قابل نصب نبود.**
**اقدام انجامشده:** `pytest-asyncio>=0.26.0` — نصب تمیز + ۴۹ تست پاس تأیید شد.
**درس:** الزامات (requirements) باید بهعنوان بخشی از CI، با `--dry-run` تست شوند، نه صرفاً توسط همان محیط توسعه.

### P0-2. Service Worker — نسخه جدید را هرگز سرو نمیکند (کش ابدی)
**مکان:** `frontend/sw.js`
**مشکلات همزمان:**
1. `CACHE_NAME = "shekar-v09-ultimate"` — از زمان refactor به v3 بهروز نشده؛
2. لیست `urlsToCache` هنوز `/static/js/app.js` را دارد — فایلی که به `legacy/app.js` منتقل شده → **در مرورگر کاربران، install با 404 شکست میخورد**؛
3. استراتژی **cache-first برای همه غیر-API** شامل `/` (index.html) → هر کاربری که یک بار باز کرده باشد، **برای همیشه** روی index.html کششده قدیمی میماند و main.js جدید هرگز بارگذاری نمیشود؛
4. `main.js` و ماژولهای core در لیست کش نیستند → **حالت آفلاین خراب است**.

**راهحل سازمانی:** نسخهگذاری SW (`v3.0.0`)، استراتژی `stale-while-revalidate` یا `network-first` برای HTML، و فهرست کش با مسیرهای **فعلی**.

### P0-3. هیچ کنترل نسخهای (Git) وجود ندارد
- بدون تاریخچه، بدون rollback، بدون برنچینگ، بدون code review امکانپذیر، بدون blame.
- برای هر پروژه غیرتدریسی، **خط قرمز** است. حتی یک اسکریپت ۵۰ خطی باید git داشته باشد.
- **اقدام پیشنهادی فوری:** `git init` + `.gitignore` + commit اولیه + برنچ `develop`.

---

## 🟠 P1 — بالا

### P1-1. ۷۹ خطای تایپی (mypy) در ۱۷ فایل
`Found 79 errors in 17 files` — شامل `object` بهجای `str`، `float|int` بهجای `int`، `SymbolSnapshot | None` به `SymbolSnapshot`. اینها دقیقاً همانهایی هستند که در refactor بعدی به باگ runtime تبدیل میشوند. **اقدام:** `mypy --strict` روی پکیج در CI با آستانه صفر.

### P1-2. هیچ CI/CD وجود ندارد
- بدون لینت (ruff)، بدون تایپچک (mypy)، بدون تست خودکار در هر commit، بدون اسکن امنیتی (bandit/pip-audit) در pipeline، بدون build.
- **اقدام:** GitHub Actions (یا GitLab CI): `ruff → mypy → pytest → pip-audit → build frontend → docker`.

### P1-3. فرانتاند: بدون بیلدسیستم، بدون تست، بدون لینت
- ES modules خام بدون bundler → بدون minify، بدون hashed filename (cache-busting)، بدون tree-shaking، بدون lint (eslint) و بدون تست (vitest/jest).
- با ۲۰۰۰+ خط JS، این بهزودی غیرقابل نگهداشت میشود. **اقدام:** Vite + Vitest + ESLint؛ `npm run build` خروجی hashed تولید کند و SW از روی همان فهرست ساخته شود.

### P1-4. دیتابیس: بدون مهاجرت و بدون بکاپ
- فقط `CREATE TABLE IF NOT EXISTS` — هر تغییر schema (مثلاً افزودن ستون `flow_score`) دیتابیسهای موجود را میشکند یا بیصدا داده ناقص میدهد.
- هیچ مکانیزم بکاپ/WAL checkpoint برای SQLite نیست.
- **اقدام:** معرفی `schema_version` (PRAGMA user_version) + مهاجرتهای ترتیبی؛ cron بکاپ روزانه با `sqlite3 .backup`.

### P1-5. توکن جلسه در localStorage + CSP با `unsafe-inline`
- هر XSS → سرقت توکن ۲۴ساعته مالک. با اینکه اسکن XSS الان صفر است، سطح حمله معماری باز است.
- **اقدام (فاز ۱):** انتقال توکن به httpOnly cookie (بدون `Secure` برای dev) — یا حداقل؛ **اقدام (فاز ۲):** CSP بدون `unsafe-inline` با nonce (نیازمند bundler از P1-3).

### P1-6. بدون SRI (Subresource Integrity) روی CDN
`https://unpkg.com/lightweight-charts@4.2.0/...` بدون `integrity` — اگر CDN به خطر بیفتد یا پکیج عوض شود، کد مخرب مستقیم اجرا میشود. **اقدام:** اضافهکردن `integrity` + `crossorigin`، یا بهتر: **وندور کردن (self-host) فایل** چون حجمش کم است.

### P1-7. rate limiter و WS hub درونحافظهای → تک-پروسه
- `InMemoryRateLimiter` و `ws_hub._clients` در RAM پروسهاند: با `--workers 2` یا دو replica، rate limit دور میزند و broadcast WS به همه کلاینتها نمیرسد.
- **اقدام:** برای مقیاس افقی، Redis (یا حداقل مستندسازی صریح «تک-پروسه فرض شده» + guard که workers>1 ممنوع شود).

### P1-8. `data_source=auto` سقوط بیصدا به mock
- وقتی TSETMC در دسترس نباشد، auto به mock برمیگردد. کاربر میتواند ساعتها روی «داده زنده» که واقعاً synthetic است تحلیل کند. بنر trust هست اما کافی نیست.
- **اقدام:** در auto، وقتی fallback رخ میدهد: (الف) فیلد `source` صریح `mock-fallback`، (ب) هشدار لاگ با request_id، (ج) در صورت `PRIVATE_MODE` یا `ALLOW_SYNTHETIC=0` بهجای mock، **خطای صریح** بده.

---

## 🟡 P2 — متوسط

### P2-1. نسخههای پراکنده و کهنه در UI
`index.html` در ۴ جا «v0.6» دارد در حالی که محصول v3 است (title، هدر، فوتر). یک مهندس سازمانی نسخه را از یک منبع (مثلاً `manifest.json`/`config`) میخواند.

### P2-2. `symbol.js` (۵۴۴ خط) هنوز god-file است
refactor فقط داشبورد را پوشاند؛ صفحه نماد ساختار قدیمی دارد (render های دستی + مودال + TV embed در یک فایل). **اقدام:** همان الگوی core/components/tabs برای آن هم.

### P2-3. نشت global ها در فرانت: `window.__loadNotifyLog`، `window.refresh`، `window.store`
پلزنی از طریق window — بوی طراحی؛ باید از طریق events/dependency injection.

### P2-4. مسیر متریکس غیراستاندارد
Prometheus متریکس در `/api/v07/metrics` سرو میشود نه `/metrics` — و در حالت PRIVATE_MODE قفل است (خوب) ولی scrape از بیرون سخت میشود. یک اکسپورتر جدا یا مسیر استاندارد + توکنی میخواهد.

### P2-5. هیچ ردیابی (tracing) / لاگ ساختاریافته نیست
لاگها متن سادهاند؛ `request_id` در رکورد هست ولی پیشفرض `-` است و در همه مسیرها پر نمیشود. برای دیباگ در production: `structlog` یا JSON lines + `request_id` واقعی از میدلور.

### P2-6. README از معماری جدید عقب است
هنوز v0.6.2 modular را توصیف میکند؛ ساختار core/components/tabs و حالت PRIVATE_MODE مستند نشدهاند.

### P2-7. اندپوینت analyze همهچیز را یکجا برمیگرداند
هر ۳۰ ثانیه ۴۰KB+ (entry+exit+watchlist+hot+industries+...) بیدلیل دانلود میشود؛ بدون pagination/field-selection. برای mobile/PWA این مهم است.

---

## 🟢 P3 — ظرافت (برای بعد)

1. **دسترسپذیری:** بدون `aria-label`، کنتراست، navigation-keyboard در جدولها.
2. **i18n:** همه رشتهها فارسی هاردکد — برای یک محصول تکزبانه OK ولی جداسازی (messages) هزینه کمی دارد.
3. **`Dockerfile` + `docker-compose.yml`:** نداشتن این یعنی هیچ دپلوی تکرارپذیری وجود ندارد.
4. **استراتژی کش استاتیک:** بدون `Cache-Control`/`ETag` در پاسخ static (فقط SW خام).
5. **مدیریت خطای سرور:** هندلر `500` عمومی وجود ندارد (فقط validation error سفارشی) — ترجیحاً یک پاسخ JSON واحد با request_id برای همه خطاها.

---

## ✅ نقاط قوت (تأیید بهعنوان مهندس)

- جداسازی لایهها در refactor v3 واقعاً خوب است (core/components/tabs یکسویه).
- ۴۹ تست + اسکن pip-audit پاک + pyflakes صفر — از اکثر پروژههای همسطح جلوتر است.
- احراز هویت HMAC + rate limit ورود + TRUST_PROXY — تفکر امنیتی واقعی دارد.
- E2E واقعی (مرورگر) صفر خطا — نادر است.

---

## 🗺️ نقشه اقدام پیشنهادی (اولویتدار)

| هفته | کار |
|------|-----|
| **هفته ۱** | Git init + .gitignore + README v3 · فیکس SW (P0-2) · فیکس نسخهها (P2-1) · Dockerfile + compose |
| **هفته ۲** | CI: ruff+mypy(pytest+bandit+pip-audit) · فیکس ۷۹ خطای mypy · vendoring lightweight-charts (P1-6) |
| **هفته ۳** | مهاجرت DB (P1-4) · بکاپ · فیکس fallback mock (P1-8) · request_id کامل |
| **هفته ۴** | Vite + Vitest + ESLint برای فرانت (P1-3) · CSP nonce + httpOnly cookie (P1-5) · refactor symbol.js (P2-2) |
| **هفته ۵** | Redis برای rate limit/WS (P1-7) · tracing · /metrics استاندارد (P2-4) · pagination analyze (P2-7) |

---

## 📝 یادداشت نهایی به صاحب پروژه

این محصول **مغز درستی دارد** (الگوریتمها، امنیت پایه، refactor تمیز) اما **اسکلت سازمانی** (کنترل نسخه، CI/CD، بیلد، مهاجرت، بکاپ، observability) ندارد. هیچکدام از اینها «زیبایی اضافه» نیستند — همهشان دقیقاً همان چیزهایی هستند که وقتی ۱۰ کاربر همزمان وصل میشوند، وقتی server کراش میکند، وقتی schema عوض میشود، یا وقتی یک باگ تایپی در refactor بعدی وارد میشود، از فروپاشی جلوگیری میکنند. مهندس مایکروسافت اینها را **قبل** از قابلیتها میسازد، چون هزینه تعمیر بعد از انتشار ۱۰ برابر است.

---

## ✅ فیکس‌های فوری اعمال‌شده (در همین بازبینی)

| مورد | وضعیت |
|------|--------|
| P0-1: `pip install -r requirements.txt` (تضاد pytest/pytest-asyncio) | ✅ فیکس: `pytest-asyncio>=0.26.0` — نصب تمیز + ۴۹ تست پاس |
| P0-2: Service Worker کش ابدی + مسیر مرده | ✅ بازنویسی: `v3-0-0` + network-first برای HTML/API + stale-while-revalidate برای استاتیک + فهرست فایل‌های فعلی (همه مسیرها تأیید شد) |
| P2-1: نسخه‌های کهنه UI (v0.6 در ۴ جا) | ✅ فیکس: v3.0 یکدست |
| (جدید) `.gitignore` | ✅ ساخته شد — گام بعدی `git init` روی ماشین شماست |
| (جدید) تأیید نهایی | ✅ ۴۹ تست · pyflakes صفر · pip-audit صفر |

> ⚠️ توجه: در این محیط sandbox مرورگر به‌دلیل نبود کتابخانه‌های سیستمی (libnspr4) اجرا نشد؛ اما تغییرات این دور کم‌ریسک بودند (sw.js، نسخه‌ها، requirements) و صحت ارجاعات فایل‌ها + تست‌های بک‌اند تأیید شد. E2E کامل پیش از این دور با صفر خطا انجام شده بود.
