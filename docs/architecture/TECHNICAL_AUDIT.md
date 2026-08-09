# بازرسی فنی سخت‌گیرانه — رادار بورس v0.4

تاریخ بازرسی: 2026-07-31  
نقش: بازرس فنی / Senior Staff Engineer  
محدوده: کل ریپوی `radar-bourse` (بک‌اند FastAPI + فرانت RTL + موتورها)

---

## ۱) خلاصه اجرایی

| مورد | نتیجه |
|------|--------|
| کامپایل/ایمپورت پایتون | ✅ پاس |
| تست دود موتورها (۲۴ مورد) | ✅ ۲۴/۲۴ پاس |
| API HTTP روی پورت 8010 | ✅ مسیرهای اصلی 200؛ فیلتر مخرب 400؛ 404 صحیح |
| WebSocket | ✅ hello + market_update + ping/pong |
| آمادگی production | ❌ **خیر** |
| صحت مالی/داده‌ای برای تصمیم واقعی | ❌ **خیر** |

**حکم:** به‌عنوان **نمونه اولیه (MVP/Demo)** قابل‌اجرا و از نظر مهندسی «سر هم شده» است.  
به‌عنوان **سامانه معاملاتی/هشدار واقعی بورس** با استاندارد سخت‌گیرانه: **رد صلاحیت production** تا رفع باگ‌های داده، امنیت، و جداسازی داده synthetic از سیگنال واقعی.

---

## ۲) آنچه واقعاً اجرا و تأیید شد

### ۲.۱ موتورها (بدون سرور)
- تولید mock بازار ≥ ۵۰ نماد
- `compute_metrics` محدود ۰..۱۰۰ و finite
- `analyze_market` بدون crash
- بنیادی عمیق: ۵ بخش + SWOT دقیقاً ۵/۵/۵
- `rank_value_stocks` مرتب نزولی
- DSL فیلتر: `__import__` بلاک می‌شود؛ منطق AND کار می‌کند
- Black–Scholes: put-call parity در حد خطای ۰.۵
- backtest روی path مصنوعی
- `MarketService.refresh` + confluence + deep fundamental

### ۲.۲ API (سرور واقعی `127.0.0.1:8010`)
نمونه نتایج:
- `GET /api/health` → 200
- `GET /api/analyze` → 200 (~35KB)
- `GET /api/confluence` → 200
- `GET /api/fundamental/فملی/deep` → 200
- `POST /api/filter/run` معتبر → 200؛ payload مخرب → **400**
- `POST /api/backtest/run` → 200
- `GET /api/options/فملی` → 200
- `WS /ws/live` → hello سپس market_update

---

## ۳) فهرست نقاط ضعف (اولویت‌بندی)

### بحرانی (P0) — قبل از هر استفاده واقعی

#### P0-1. داده «بنیادی» و «ریزمعامله» عمدتاً synthetic است ولی UX شبیه داده واقعی است
- `fundamental.py` و `trade_detail.py` در نبود کدال/TSETMC عدد می‌سازند.
- disclaimer در JSON هست، اما در تب‌های اصلی/هشدار تلگرام برجسته و غیرقابل‌نادیده‌گرفتن نیست.
- **ریسک:** کاربر روی P/E+CFO+SWOT ساختگی تصمیم خرید بگیرد.
- **رفع:**  
  - فلگ اجباری `DATA_TRUST_LEVEL=synthetic|mixed|live` در تمام پاسخ‌ها و UI  
  - اگر live نیست، ارسال notify خرید/فروش **ممنوع** یا فقط با پیشوند `[DEMO]`  
  - جدا کردن endpointهای demo از live

#### P0-2. آبشار خرابی: بدون تاریخچه ۱۰دقیقه‌ای واقعی، «جمع‌بندی نهایی» عملاً بی‌اثر می‌شود
مشاهده در بازرسی:
```
big_moves_count: 0
store.big_moves: 0
confluence.buy_alerts: 0
confluence.sell_alerts: 0
```
علت ریشه‌ای:
- `bootstrap_history_if_empty` فقط وقتی ticks کم است کار می‌کند.
- بعد از چند refresh، ticks زیاد است ولی **عمق زمانی** تا ۱۰ دقیقه نیست (فقط ده‌ها ثانیه).
- `get_ticks_near(now-600)` خالی → big_moves خالی → شرط جریان ۱۰′ برای خرید ترکیبی برقرار نمی‌شود.
- **رفع:**  
  - bootstrap بر اساس «پوشش زمانی» نه فقط تعداد ردیف  
  - اگر window ناقص است در API صریح: `flow_coverage: insufficient`  
  - برای live: صبر/هشدار «حداقل N دقیقه تاریخچه لازم است»

#### P0-3. امنیت استقرار: CORS باز + بدون احراز هویت + توکن نوتیف در API
- `allow_origins=["*"]` در `main.py`
- هیچ Auth/API-Key برای endpoints حساس (`notify/config`, `thresholds`, `portfolio`, `filter/saved`)
- `PUT /api/notify/config` می‌تواند توکن تلگرام را بگیرد و در SQLite بگذارد (بدون encryption)
- **رفع:** HTTPS + auth + CORS محدود + secret store + هرگز برنگرداندن secret به کلاینت

#### P0-4. کلید پیش‌فرض BrsApi داخل کد
- `config.py`: کلید Free... به‌صورت default
- **رفع:** حذف default secret؛ اجبار env؛ rotate key

---

### بالا (P1)

#### P1-1. قفل سراسری `asyncio.Lock` در `refresh` بیش‌ازحد نگه داشته می‌شود
داخل `async with self._lock:` انجام می‌شود:
- fetch شبکه
- analyze
- persist DB
- big_moves
- tablocastic
- row cache
- **confluence (سنگین؛ fundamental per symbol)**  
- broadcast WS  
- notify HTTP

**اثر:** در زمان market open با چند کلاینت، latency و احتمال timeout بالا می‌رود؛ refreshهای موازی صف می‌شوند.

**رفع:** lock فقط دور به‌روزرسانی state؛ I/O و notify بیرون lock؛ debounce.

#### P1-2. هزینه CPU: `build_deep_fundamental` برای همه نمادها در confluence هر refresh
- fundamental عمیق + metrics + tablocastic برای ~۶۰+ نماد (در live صدها نماد) هر ۳۰s
- **رفع:** کش fundamental روزانه؛ محاسبه lazy؛ فقط universe کاندید

#### P1-3. SQLite همزمانی و مقیاس
- یک فایل DB، WAL روشن است (خوب) ولی backup/migration/retention سیاست ضعیف
- payload JSON بزرگ در snapshots
- **رفع:** جدا کردن hot ticks از snapshot سنگین؛ partition روزانه؛ Postgres برای multi-instance

#### P1-4. Provider زنده شکننده است
- چند endpoint حدسی TSETMC
- parse legacy CSV شکننده
- در sandbox عملاً همیشه mock
- **رفع:** قرارداد رسمی/پایدار؛ circuit breaker؛ متریک uptime منبع؛ تست integration شبانه

#### P1-5. هشدارها در حالت enabled بدون توکن = spam در لاگ dry-run
- اگر `enabled=True` و توکن نباشد، هر refresh تعدادی dry-run می‌نویسد
- **رفع:** enabled واقعی فقط وقتی حداقل یک کانال configure شده

---

### متوسط (P2)

#### P2-1. معماری فرانت: God file
- `frontend/js/app.js` ~76KB / monolith
- `index.html` بسیار بزرگ با ده‌ها تب
- بدون bundler/test/linter
- **رفع:** تفکیک ماژول/تب‌ها؛ حداقل vitest برای renderهای حساس

#### P2-2. تایپ‌دهی سست
- `Any` زیاد (~۲۰۰ نقطه)
- dictهای بدون schema در confluence/fundamental deep
- **رفع:** Pydantic models برای همه پاسخ‌های API

#### P2-3. مدیریت خطای یکنواخت «بلعیدن» exception
- `except Exception` حدود ۲۸ مورد؛ بعضی فقط debug log
- خطای کاربر نهایی مبهم می‌ماند
- **رفع:** طبقه‌بندی خطا + error_id

#### P2-4. بک‌تست گمراه‌کننده
- path مصنوعی + fee ساده + بدون صف/حجم/لغزش واقعی بورس ایران
- win_rate در UI ممکن است جدی گرفته شود
- **رفع:** برچسب DEMO؛ نیاز به tick واقعی برای report رسمی

#### P2-5. اختیار معامله آموزشی است
- زنجیره synthetic BS نه بازار آپشن TSE
- short strategies بدون هشدار ریسک کافی در پیام‌ها
- **رفع:** جدا کردن «ماشین‌حساب آموزشی» از «بازار واقعی»

#### P2-6. فیلتر DSL
- sandbox نسبتاً خوب است (AST)
- ولی Unicode/اعداد فارسی فقط تا حدی؛ فیلدهای string injection از طریق داده (نه کد) ممکن است گیج‌کننده باشد
- عملکرد: روی row_cache خطی O(n)

#### P2-7. نبود تست خودکار در ریپو
- هیچ `tests/` یا CI دیده نشد
- بازرسی دستی پاس شد؛ رگرسیون فردا تضمین ندارد

#### P2-8. بین‌المللی‌سازی/زمان
- timezone UTC مخلوط با local
- تاریخ‌های مالی 1403 ثابت در synthetic

#### P2-9. صفحه نماد وابسته CDN
- Lightweight Charts از unpkg — در شبکه داخلی/ایران ممکن است fail شود

#### P2-10. عدم وجود rate limit
- endpointهای سنگین (analyze/confluence/backtest) بدون throttle

---

### پایین (P3) / بدهی فنی

- نام‌گذاری دوگانه `fund_score` / `value_score` / `grade` / `value_grade`
- تکرار منطق سرانه/قدرت در metrics و big_moves
- `market_service.py` بیش از حد مسئول (SRP نقض شده)
- نسخه در چند جا (config/UI/footer) ممکن است ناهماهنگ شود
- `MISSING_ID` در اسکن خام JS عمدتاً false-positive به‌خاطر سلکتور `#table tbody` است؛ tabs/panels منطبق‌اند ✅
- مستندات بیشتر از تست

---

## ۴) باگ‌های رفتاری مشخص مشاهده‌شده

1. **big_moves=0 بعد از استارتاپ تازه با refreshهای نزدیک** → جمع‌بندی خرید ترکیبی صفر  
2. **وابستگی کیفیت confluence به DB residual از اجراهای قبلی** (حالت غیرقطعی/flaky)  
3. **پیام تلگرام می‌تواند از داده synthetic تغذیه شود** بدون مانع سخت  
4. در یک اجرا، سرور قبلی روی 8000 بدون routeهای جدید 404 می‌داد (عملیات deploy بدون kill صحیح) — ریسک عملیاتی  
5. `bootstrap` timestamps را جابه‌جا می‌کند؛ با داده live واقعی اگر اشتباه صدا شود تاریخچه را آلوده می‌کند

---

## ۵) امنیت — چک‌لیست

| کنترل | وضعیت |
|--------|--------|
| Authn/Authz | ❌ ندارد |
| CORS محدود | ❌ `*` |
| Secret management | ❌ ضعیف (env + SQLite plaintext) |
| Input sandbox فیلتر | ✅ نسبتاً خوب |
| SQL injection | ✅ parametrized |
| XSS | ⚠️ escape در خیلی جاها هست؛ بررسی کامل template لازم |
| SSRF از طرف سرور | ⚠️ notify به telegram/bale؛ URL ثابت است (خوب) |
| Dependency pinning | ✅ requirements پین شده |
| HTTPS فرض | خارج از برنامه |
| Audit log دسترسی | ❌ |

---

## ۶) کیفیت داده برای ادعای محصول

| ادعا | واقعیت کد |
|------|-----------|
| تشخیص پول هوشمند | تقریب از سرانه/حجم؛ نه order-level قطعی |
| پول داغ دقیق | اغلب synthetic trades |
| بنیادی ۵محوره | ساختار عالی؛ داده پیش‌فرض synthetic |
| جریان ۱۰دقیقه | فقط اگر تاریخچه واقعی کافی باشد |
| هشدار خرید ترکیبی | منطق‌اش درست طراحی شده؛ وابستگی به P0-1 و P0-2 |

---

## ۷) نمره خام (از ۱۰)

| محور | نمره | توضیح |
|------|------|--------|
| قابلیت اجرا / Demo | 8.0 | بالا می‌آید، UI کامل |
| درستی دامنه بورس ایران | 3.5 | mock/synthetic غالب |
| معماری | 5.0 | modular نسبی؛ service خداگونه |
| امنیت | 2.5 | برای اینترنت باز خطرناک |
| تست/CI | 1.5 | تقریباً صفر در ریپو |
| عملکرد/مقیاس | 4.0 | برای ۶۰ نماد ok؛ برای کل بازار نه |
| قابلیت نگهداری | 5.0 | فرانت monolith |
| **میانگین وزنی production** | **~3.5/10** | |

---

## ۸) اقدامات اصلاحی پیشنهادی (ترتیب انجام)

### اسپرینت A — درست‌کاری سیگنال (۱–۲ هفته)
1. Flow coverage واقعی + رفع bootstrap  
2. ممنوعیت notify روی synthetic  
3. برچسب trust level در UI و پیام‌ها  
4. کش fundamental  

### اسپرینت B — امنیت حداقل (۱ هفته)
1. API key / basic auth  
2. CORS allowlist  
3. حذف کلید پیش‌فرض  
4. رمزنگاری توکن‌ها at rest  

### اسپرینت C — سخت‌شدن مهندسی
1. `tests/` برای metrics/filter/confluence/store  
2. جدا کردن market_service  
3. متریک Prometheus: refresh_ms, source_up, alert_sent  
4. split فرانت  

### اسپرینت D — داده واقعی
1. کدال parser واقعی  
2. Trade detail پایدار  
3. قرارداد داده و monitoring منبع  

---

## ۹) جمع‌بندی یک‌خطی بازرس

> کد به‌عنوان **پروتوتایپ جامع محصول** قابل تقدیر است؛ به‌عنوان **سیستم هشدار پولی** هنوز به لایه «داده قابل‌اعتماد + ایمنی عملیاتی + کنترل دسترسی» نرسیده و نباید بدون رفع P0ها به کاربر نهایی پول‌دار وصل شود.

---

## ۱۰) پیوست — دستور بازتولید بازرسی

```bash
cd radar-bourse/backend
export PYTHONPATH=$PWD DATA_SOURCE=mock
python3 -m py_compile app/main.py
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8010
curl -s localhost:8010/api/health | jq .
curl -s localhost:8010/api/confluence | jq .summary
```
