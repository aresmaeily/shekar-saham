# 🔍 گزارش بازرسی فنی سخت‌گیرانه — شکار سهام v0.6.0
**نقش بازرس:** Senior Staff Engineer (سطح متا) — بی‌رحم، دقیق، با اجرای واقعی کد  
**تاریخ:** 2026-07-31  
**محیط اجرا:** Docker Python 3.13 / FastAPI 0.115 / SQLite WAL  
**دستور اجرا:** `DATA_SOURCE=mock uvicorn app.main:app --port 8011`

---

## ۱) خلاصه اجرایی — حکم نهایی

| معیار | وضعیت v0.4 | وضعیت v0.6.0 بعد از فیکس‌های شما | حکم بازرس |
|-------|-------------|-----------------------------------|------------|
| بالا آمدن سرور | ✅ | ✅ پاس (60 نماد mock) | **قابل قبول** |
| P0-2 Flow coverage (تحرکات 10 دقیقه) | ❌ `big_moves=0` | ✅ **فیکس شد** `coverage=600s sufficient=True big_moves=9 buy_alerts=3` | پاس |
| P0-1 Trust Level برچسب | ❌ نبود | ✅ در API هست `/api/analyze` → `synthetic` ولی در UI **فقط یک pill کوچک** - کافی نیست | **نیاز به بنر بزرگتر** |
| P0-3 Security headers | ❌ | ✅ `X-Content-Type-Options, X-Frame-Options, CSP` اضافه شد | پاس |
| P0-3 CORS | ❌ `*` باز | ⚠️ نیمه‌فیکس — default الان `localhost` ولی `allow_credentials=True` با `*` اگر env اشتباه ست شود خطرناک | **باید تست مرزی انجام شود** |
| P0-3 Rate Limit | ❌ نداشت | ⚠️ **باگ جدید معرفی شد**: اول 500 می‌داد، الان بعد از فیکس من 429 می‌دهد ولی bucket مشترک برای تمام endpointهای heavy است (analyze + filter) → legit user بلاک می‌شود | **نیاز به per-endpoint bucket** |
| P0-3 Token encryption | ❌ plaintext | ⚠️ **باگ کریتیکال:** `get_fernet()` هر بار کلید ephemeral جدید می‌ساخت → encrypt/decrypt Fail شد — **من فیکس کردم با `@lru_cache`** الان OK | پاس بعد از فیکس من |
| P1-1 Lock contention | ❌ lock کل refresh | ✅ **فیکس عالی** - الان فازبندی: فاز 0 چک سریع under lock، فاز 1 fetch خارج، فاز 2 CPU خارج، فاز 3 آپدیت سریع under lock، فاز 4 broadcast خارج | **نمونه خوب مهندسی** |
| P1-4 Circuit breaker | ❌ نداشت | ✅ اضافه شد با metrics `tsetmc_success/fail` | پاس |
| P2-10 Filter injection | ⚠️ باید چک شود | ✅ الان 400 می‌دهد `{"detail":"تابع غیرمجاز"}` برای `__import__` و `eval` | پاس |
| Build | ✅ | ✅ py_compile پاس | پاس |

**نمره کلی بعد از v0.6.0:**
- Demo/MVP: **7.5/10** (از 8.0 قبلی بهتر، چون flow coverage درست شد)
- Production برای پول واقعی: **5.0/10** (از 3.5 قبلی خیلی بهتر، ولی هنوز نه - به خاطر frontend monolith و نداشتن تست)
- امنیت: **6.0/10** (از 2.5 قبلی جهش عالی، ولی هنوز CORS و rate limit per-endpoint نیاز به polish)

**حکم:** به عنوان **ابزار کمک‌تحلیلی داخلی** با `AUTH_REQUIRED=1` و `TRUST_LEVEL` مشخص قابل استفاده است. به عنوان **سرویس عمومی اینترنت با سیگنال خرید واقعی** هنوز **رد**.

---

## ۲) باگ‌های بحرانی (P0) که برنامه‌نویس باید فوراً فیکس کند

### P0-1: Trust level هنوز به اندازه کافی برجسته نیست
**مشاهده:**
- در `/api/health` دارید: `"trust_level":"synthetic"` ✅
- در فرانت: فقط `#trustPill` کوچک با متن `اعتماد: DEMO/SYNTHETIC`
- کاربر عادی متوجه نمی‌شود که P/E و SWOT ساختگی است

**تذکر بازرس:**
```html
<!-- فعلی -->
<div id="trustPill">اعتماد: DEMO/SYNTHETIC</div> <!-- خیلی کوچک -->

<!-- باید -->
<div id="trustBanner" class="trust-banner demo" style="position:sticky;top:0;z-index:1000">
  ⚠️ هشدار: داده DEMO/SYNTHETIC است — بنیادی و ریزمعامله ساختگی، مبنای خرید قرار ندهید [data_source=mock]
</div>
```
CSS من اضافه کردم (`trust-banner`) ولی JS آن را فعال نمی‌کند. در `app.js` باید:
```js
function updateTrust(level){
  const banner = $("#trustBanner");
  if(level === "synthetic"){
    banner.classList.remove("hidden");
    banner.className = "trust-banner demo";
    banner.textContent = "⚠️ [DEMO] داده آزمایشی - بنیادی ساختگی - برای تست UI است - سیگنال واقعی نیست";
  }
}
```

### P0-2: ✅ فیکس شد - ولی یک edge باقی مانده
`ensure_flow_history` الان بر اساس `coverage_sec` کار می‌کند نه فقط count → `big_moves=9` شد.
**ولی:**
- در `store.py`، `get_ticks_near` با tolerance 300s می‌گیرد، اگر 2 refresh با فاصله 5 ثانیه باشد، `actual_window_sec` ممکن است 5s گزارش شود نه 600s، و امتیاز را 0.85 ضرب می‌کند - منطقی ولی باید در UI نشان داده شود.

**تذکر:** در API `flow_meta` برگردانید و در UI بنویسید: `پنجره واقعی: 312s / هدف 600s`

### P0-3: Security - چند باگ

#### P0-3a: CORS - `allow_credentials=True` با origin لیستی خطرناک اگر کسی `CORS_ORIGINS=*` ست کند
**کد فعلی:**
```python
allow_cred = (origins != ["*"] and "*" not in origins)
```
این درست است ولی اگر کسی `CORS_ORIGINS=http://evil.com,*` بفرستد، `*` داخل لیست هست و `allow_cred=False` می‌شود - خوب. ولی باید لاگ هشدار بدهید اگر `*` با credentials ترکیب شود.

**تذکر:** در `create_app`:
```python
if "*" in origins and settings.debug is False:
  logger.critical("CORS wildcard in production - BLOCKED")
  origins = ["http://localhost:8000"]
```

#### P0-3b: Rate limiter bucket مشترک
الان:
```python
HEAVY_PATHS = ("/api/analyze", "/api/confluence", "/api/filter/run"...)
# برای همه اینها یک bucket: heavy:{ip}
```
کاربر اگر 20 بار `/api/analyze` بزند، دیگر نمی‌تواند `/api/filter/run` بزند - 429 می‌گیرد. این DOS علیه کاربر legit است.

**تذکر:** باید per-path باشد:
```python
def is_limited(self, key: str, path: str):
  bucket_key = f"{path}:{key}"
```

من فیکس را انجام دادم ولی هنوز per-path نیست - برنامه‌نویس باید اصلاح کند.

#### P0-3c: Encryption - فیکس شد ولی نیاز به تست مهاجرت دارد
قبل از فیکس من:
```
encrypt_token -> Fernet(new_random_key)
decrypt_token -> Fernet(another_new_random_key) -> InvalidToken -> Fail
```
بعد از فیکس با `@lru_cache` درست شد.
**ولی:** توکن‌های قدیمی که plaintext در DB ذخیره شده بودند، الان `decrypt_token` آنها را به صورت heuristic برمی‌گرداند - باید یک اسکریپت migration بنویسید که تمام `settings_kv` با کلید `notifier` را بخواند، decrypt کند، دوباره encrypt کند.

#### P0-3d: API Key در query param `?api_key=` - لاگ می‌شود!
در `api_key_middleware`:
```python
key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
```
query param در access log ذخیره می‌شود - نشت secret.

**تذکر:** فقط header قبول کنید، query param را حذف کنید یا اگر هست هشدار بدهید و لاگ نکنید.

### P0-4: BrsApi key default حذف شده - ✅ پاس

---

## ۳) باگ‌های بالا (P1) - باید قبل از scale فیکس شود

#### P1-1: ✅ فیکس عالی - تحسین
قبل: 1 lock برای 2 ثانیه (fetch + analyze + DB + confluence)
بعد: 3 فاز کوتاه - نمونه کتابی.

**یک نکته:** در `refresh` هنوز `store.portfolio_list()` خارج از lock صدا زده می‌شود که OK است چون store lock داخلی دارد، ولی بهتر است در همان فاز 3 باشد.

#### P1-2: Fundamental cache - نیمه فیکس
الان TTL + LRU size 200 اضافه شد - خوب.
**ولی:** اگر 200 نماد cache باشد و کاربر بخواهد نماد 201 را ببیند، 20 درصد قدیمی‌ترین حذف می‌شود - ممکن است نمادهای محبوب حذف شوند. بهتر است LFU یا فقط TTL باشد، نه size.

#### P1-3: SQLite - P1 ولی خطرناک
- WAL فعال ✅
- timeout 30 ✅
- ولی `prune_old` هر refresh صدا زده می‌شود - اگر 1000 تیک باشد، DELETE سنگین می‌شود و lock می‌گیرد.
- backup نیست - اگر DB corrupt شود، از دست می‌رود.

**تذکر:** prune را به background task هر ساعت منتقل کنید، نه هر 30 ثانیه.

#### P1-4: Provider - فیکس خوب با circuit breaker
الان metrics دارید: `tsetmc_success/fail/mock_fallback` - عالی.
**ولی:** در `get_uptime_metrics` هیچ‌جا expose نمی‌شود - به `/api/health` اضافه کنید تا مانیتورینگ بشود.

#### P1-5: Notify spam - ✅ فیکس شد
قبل: dry-run هر refresh لاگ می‌کرد.
بعد: فقط هر 5 دقیقه یکبار لاگ dry-run + `_allow` برای no-channel.

---

## ۴) متوسط (P2) - بدهی فنی که بازرسی سخت‌گیر نمی‌بخشد

### P2-1: Frontend God file - **مردود**
- `app.js` 77842 بایت، یک IIFE با 1862 خط، همه چیز داخل `state` global
- بدون bundler، بدون TypeScript، بدون test
- `escapeHtml` دارید ولی در بعضی جاها `innerHTML =` با داده کاربر (مثلاً `filterFields`).

**تذکر بازرس:**
```
این فایل را به 5 ماژول تقسیم کن:
  /js/modules/api.js      -> fetch wrappers با rate limit handling
  /js/modules/state.js    -> Zustand-like store
  /js/modules/render/*.js -> entry, confluence, etc.
  /js/modules/security.js -> escapeHtml + DOMPurify
  /js/app.js              -> فقط bootstrap
```
و از ES Module استفاده کن: `<script type="module" src="/static/js/app.js">`

### P2-2: تایپ سست - 62 نقطه `Any`
```bash
grep -rn "Any" app/engines/*.py | wc -l  # 62
```
مثال:
```python
def _build_confluence(self, cfg=None) -> dict[str, Any]: # Any ممنوع
```
باید Pydantic model باشد:
```python
class ConfluenceBoard(BaseModel):
  buy_alerts: List[BoardRow]
  summary: Summary
  trust_level: TrustLevel
```

### P2-3: بلعیدن exception - 43 مورد
```python
except Exception: # noqa: BLE001
  pass
```
این anti-pattern متا است. باید:
```python
except Exception as exc:
  err_id = uuid.uuid4().hex[:8]
  logger.exception(f"[{err_id}] confluence failed: {exc}")
  return {"error": "...", "error_id": err_id}
```

### P2-4: Backtest - ⚠️ گمراه‌کننده
شما `demo_disclaimer` اضافه کردید ✅ ولی در UI:
- `#btCards` فقط `win_rate` را نشان می‌دهد، کاربر فکر می‌کند 75% win_rate واقعی است.
- باید بنر قرمز بزرگ: `این بک‌تست با داده مصنوعی و بدون صف خرید/فروش و لغزش واقعی است - برای آموزش، نه تضمین سود`.

### P2-5: Options - ✅ educational اضافه شد ولی...
`risk_warning` در payload هست ولی در `app.js` نمایش داده نمی‌شود.
در `renderOptions()` باید:
```js
if(o.educational){
  $container.innerHTML += `<div class="warn-box">⚠️ ${o.risk_warning}</div>`
}
```

### P2-7: نبود تست - **مردود سخت**
```
ls tests/ -> NO SUCH DIR
```
حتی یک `pytest` ندارید. بازرس متا بدون تست، PR را auto-reject می‌کند.

**تذکر:** حداقل 3 فایل تست:
```
tests/test_metrics.py      -> compute_metrics finite 0..100
tests/test_filter_dsl.py   -> injection blocked, unicode
tests/test_flow_coverage.py-> ensure_flow_history coverage
```

### P2-8: Timezone - UTC مخلوط با Tehran
- `as_of` در UTC ذخیره می‌شود، ولی UI `toLocaleString("fa-IR")` می‌زند که بسته به مرورگر timezone کاربر است.
- بورس تهران `Asia/Tehran` است - باید صریح:
```python
from zoneinfo import ZoneInfo
tehran = ZoneInfo("Asia/Tehran")
as_of_tehran = as_of.astimezone(tehran)
```

### P2-10: Rate limit - قبلاً گفته شد

---

## ۵) پایین (P3) - ولی بازرس متا گیر می‌دهد

- نام‌گذاری دوگانه: `fund_score` vs `value_score` vs `grade` - یک enum کنید
- `market_service.py` هنوز SRP را نقض می‌کند (70% logic) - باید به `ConfluenceService`, `PortfolioService` تقسیم شود
- ورژن در 3 جا: `config.py v0.6.0`, `index.html v0.4`, `footer` - باید از `/api/health` بخواند
- CDN: `Lightweight Charts` از `unpkg.com` - در ایران فیلتر است، باید local fallback داشته باشید:
```html
<script>window.LightweightCharts || document.write('<script src="/static/js/lightweight-charts.js"><\/script>')</script>
```

---

## ۶) تست‌های اجرایی که من انجام دادم

```bash
# 1. Health
curl /api/health -> 200, trust=synthetic, coverage=600s, big_moves=9 ✅ (قبل 0 بود)

# 2. Security headers
curl -I /api/health -> X-Content-Type-Options: nosniff, X-Frame-Options: DENY ✅

# 3. Filter injection
POST /api/filter/run {"expr":"__import__('os').system('id')"} -> 400 {"detail":"تابع غیرمجاز"} ✅

# 4. Rate limit
20 req/min heavy -> 21th -> 429 {"code":"RATE_LIMIT"} ✅ (قبل 500 می‌داد)

# 5. Crypto
encrypt_token -> decrypt_token -> True ✅ (قبل False بود)

# 6. Code quality
Any: 62 -> باید 0
except Exception: 43 -> باید <5 با err_id
app.js: 77842 bytes -> باید <20000 per module
```

---

## ۷) دستورات فوری به برنامه‌نویس (Action Items)

**فوری - قبل از هر push:**

1. [ ] **P0-1:** بنر trust را در فرانت بزرگ و sticky کن - الان فقط pill کوچک است
2. [ ] **P0-3b:** rate limiter را per-endpoint کن، نه global heavy
3. [ ] **P0-3d:** حذف `query_params.get("api_key")` - فقط header
4. [ ] **P1-3:** prune را از هر refresh به هر ساعت منتقل کن
5. [ ] **P2-7:** سه فایل تست بنویس و `pytest` را در CI اجرا کن
6. [ ] **P2-1:** `app.js` را split کن یا حداقل comment بگذار `# TODO: split into modules - tech debt`

**اسپرینت بعدی:**

7. [ ] Version را از یک جا بخوان - نه hardcode در HTML
8. [ ] Timezone را `Asia/Tehran` صریح کن
9. [ ] برای `notify` یک migration script بنویس که توکن‌های plaintext قدیمی را encrypt کند

**تحسین:**

- ✅ Lock contention فیکس عالی بود - این را در مصاحبه متا به عنوان نمونه بگو
- ✅ Circuit breaker با metrics - حرفه‌ای
- ✅ Flow coverage فیکس - الان buy_alerts=3 می‌دهد نه 0
- ✅ Filter DSL امن - injection را 400 می‌کند

---

## ۸) نمره نهایی بازرس سخت‌گیر

| محور | v0.4 | v0.6.0 بعد از فیکس |
|------|------|-------------------|
| امنیت | 2.5 | **6.0** |
| درستی داده | 3.5 | **6.5** (trust + flow) |
| معماری | 5.0 | **7.0** (lock fix) |
| تست | 1.5 | **2.0** (هنوز 0 تست) |
| پرفورمنس | 4.0 | **6.5** |
| قابلیت نگهداری | 5.0 | **5.5** (هنوز god file) |
| **میانگین Production** | **3.5** | **5.5** |

**جمع‌بندی یک‌خطی بازرس:**

> از نمونه اولیه شلخته به MVP قابل نمایش برای سرمایه‌گذار داخلی رسیدی، ولی برای اتصال به پول واقعی کاربر و اینترنت باز، هنوز 2 اسپرینت امنیتی و 1 اسپرینت تست نیاز داری. فیکس lock و flow coverage عالی بود، ولی frontend monolith و نبود تست، تو را در بازرسی نهایی متا رد می‌کند.

**امضا:** بازرس فنی v0.6 — سخت‌گیر، بی‌طرف، با اجرای کد

