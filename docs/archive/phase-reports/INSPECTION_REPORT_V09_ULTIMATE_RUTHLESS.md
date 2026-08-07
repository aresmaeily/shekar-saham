# 🔍 گزارش بازرسی بی‌رحم و بی‌طرف - نسخه Ultimate v0.9 - بهتر از نوآوران، فراز، تابلوخوانی

**بازرس:** Senior Staff Engineer - سخت‌گیر، بی‌رحم، با اجرای واقعی کد
**تاریخ:** 2026-07-31
**نسخه بازرسی شده:** v0.9 Ultimate (forex + custom indicator + windows/android)
**دستور اجرا:** `DATA_SOURCE=mock pytest + uvicorn + curl`

---

## خلاصه اجرایی - حکم بی‌رحم

| معیار | v0.4 اولیه | v0.9 Ultimate فعلی | حکم بازرس بی‌رحم |
|-------|------------|-------------------|------------------|
| بالا آمدن | ✅ | ✅ 60 نماد mock + 6 نماد فارکس | پاس |
| تست‌ها | 0 | 17 passed | **پاس ولی کم** - برای 9 باید 50+ تست |
| Flow coverage | 0s | 3655s sufficient True | ✅ **فیکس عالی** از 0 به 3655s |
| Rate limit per-path | ❌ | ✅ 25/min per path - بعد 26 تحلیل، analyze 429 ولی forex 200 | ✅ **فیکس عالی** - قبل global بود الان per-path |
| Security headers | ❌ | ✅ X-Request-ID, X-Frame, CSP | پاس |
| Chart API v0.8 | ❌ | ✅ 200 OK ohlcv 8 کندل + MA + markers + risk | پاس |
| Forex API v0.9 | ❌ | ✅ 200 OK با fallback synthetic وقتی Binance 451 بلاکه | ⚠️ با ارفاق پاس برای استفاده شخصی - برای prod باید TwelveData API Key |
| PWA manifest | ❌ | ⚠️ وجود داره ولی icon-192.png و 512.png نداره - نصب اندروید Fail میشه | **مردود** - باید آیکون بسازی |
| Electron Windows | ❌ | ⚠️ main.js و package.json داره ولی electron در node_modules نیست - کاربر باید npm install بزنه | با ارفاق پاس برای شخصی |
| Any usage | 200 | 143 | ❌ **مردود** - باید <20 باشه برای 9 |
| Bare except | 60 | 50 | ❌ **مردود** - باید <10 با err_id |
| God file | 77KB | 80KB + 12 ماژول جدید | ⚠️ نیمه فیکس - ماژولار کردی ولی god file هنوز 80KBه و لود میشه - باید lazy load یا حذفش کنی |

**نمره فعلی v0.9 با دید بی‌رحم:** **7.8/10** (از 9.3 قبلی افت کرد چون فیچر جدید اضافه کردی ولی باگ جدید هم آوردی)

**حکم:** برای استفاده شخصی **عالی و قابل قبول**، برای ارائه به عنوان محصول تجاری با پول واقعی **نیاز به 1 اسپرینت پولیش**.

---

## P0 - بحرانی - باید همین الان فیکس شود قبل از فایل نهایی

### P0-1: PWA Icons Missing - نصب اندروید Fail
**مشاهده:**
```
frontend/manifest.json:
  "icons": [{"src": "/static/icon-192.png"}, {"src": "/static/icon-512.png"}]
ls frontend/ -> icon-192.png وجود ندارد
```
**نتیجه:** Chrome روی اندروید میگه "Cannot install - no icon"

**تذکر بی‌رحم:** این اشتباه مبتدیانه‌ست - manifest نوشتی ولی آیکون نساختی.

**فیکس:**
```bash
# باید 2 تا PNG بسازی از SVG
convert favicon.svg -resize 192x192 icon-192.png
convert favicon.svg -resize 512x512 icon-512.png
# یا برای شخصی: کپی favicon به عنوان PNG
```

### P0-2: Forex Binance 451 Blocked in Iran
**مشاهده:**
```
Binance fetch failed for PAXGUSDT: Client error '451' - For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/451
```
**دلیل:** Binance ایران و بعضی کشورها رو بلاک کرده (451 Unavailable For Legal Reasons)

**تذکر:** برای استفاده شخصی fallback synthetic ساختی که خوبه ولی trust_level رو `live` برمیگردونی در حالی که syntheticه - گمراه‌کننده.

**فیکس حرفه‌ای:**
```python
# در forex_provider.py
if "synthetic" in source:
    trust = "synthetic"
    source = "synthetic-personal-demo"
else:
    trust = "live"
```

### P0-3: Version Inconsistent
- `config.py version = 0.7.0-excellent`
- `/api/health` → `version=0.7.0-excellent` ولی `phase=6`
- باید `phase=9` و `version=0.9.0-ultimate` باشه

**تذکر:** ورژن را از یک جا بخوان - نه hardcode در 3 جا.

### P0-4: Custom Indicator Engine - Security Risk (Low but P0 for creative feature)
در `custom_indicator.js`:
```javascript
// تو از Function constructor استفاده نکردی ولی eval-like parsing داری
// اگر کسی فرمول `while(true){}` بفرسته، می‌تونه حلقه بینهایت بسازه و UI freeze
```
باید timeout و iteration limit بگذاری.

---

## P1 - بالا - برای نمره 9 باید فیکس شود

### P1-1: Any Usage 143
```
grep -rn "Any" app/engines/*.py | wc -l = 143
```
در `chart_builder.py`:
```python
def build_ohlcv_from_ticks(ticks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
```
این `Any` باید `Tick` TypedDict باشه.

**تذکر:** برای 9 باید <20 باشه - الان 143 یعنی typing نکردی.

### P1-2: Bare Except 50
```
except Exception:
  pass
```
هنوز 50 تا داری - در `providers.py`, `store.py`, etc.

**تذکر:** هر کدام باید:
```python
except Exception as exc:
    err_id = uuid.hex[:8]
    logger.exception(f"[{err_id}] provider failed: {exc}")
```

### P1-3: God File 80KB هنوز لود میشه
تو 12 ماژول جدید ساختی (عالی) ولی `index.html` هنوز هم `<script src="/static/js/app.js">` 80KB رو لود می‌کنه **به علاوه** ماژولارها.

**تذکر:** باید یا god file رو حذف کنی و فقط modular لود کنی، یا با `type="module"` و dynamic import lazy load کنی.

### P1-4: Electron - node_modules نیست
`electron/package.json` داره `electron` به عنوان devDependency ولی در zip نیست - کاربر بعد از unzip باید `npm install` بزنه که 200MB دانلود می‌کنه.

**تذکر:** برای شخصی اشکال نداره ولی باید در README بنویسی.

### P1-5: Forex Tab Binding - Race Condition
در `forex.js` از `MutationObserver` برای تشخیص active شدن تب استفاده کردی - این race داره. بهتره مستقیم به `mainTabs` click listener وصل شی.

---

## P2 - متوسط - برای عالی شدن

- Custom indicator parser فقط `SMA(close,20) * 1.02` رو ساپورت می‌کنه - Pine Script کامل نیست - برای 9 کافیه ولی باید بنویسی محدوده چیه
- Menu customizer در settings tab رندر میشه ولی بعد از save نیاز به reload داره - باید reactive باشه
- PWA sw.js cache-first برای API هم هست - باید network-first برای API باشه (که هست ولی تست نشده)
- No JWT - فقط API key - برای excellent باید JWT option هم باشه
- No audit log table جدا - داری notify_log رو reuse می‌کنی

---

## ✅ چیزهایی که عالی فیکس کردی (تحسین بی‌طرف)

- **Rate limit per-path:** قبل اگر 20 بار analyze می‌زدی، forex هم 429 می‌شد. الان:
  ```
  After 26 analyze, analyze 429, forex 200, health 200 - Perfect per-path
  ```
  این فیکس **عالی** بود.

- **Chart API:** `200 OK` با OHLCV + MA + markers + risk - بهتر از نوآوران که فقط کندل ساده داره

- **Forex fallback:** وقتی Binance 451 میده، synthetic با الگوی واقعی می‌سازی - برای استفاده شخصی هوشمندانه

- **Security headers:** `X-Request-ID` اضافه شد - برای trace عالی

- **EventBus:** `system.startup` event منتشر میشه - برای debug عالی

---

## دستورات فوری به برنامه‌نویس قبل از فایل نهایی

**P0 - همین الان:**
1. [ ] PWA icons بساز: `icon-192.png` و `icon-512.png` از `favicon.svg`
2. [ ] Version را به `0.9.0-ultimate` یکسان کن در همه جا + phase=9
3. [ ] Forex trust_level: اگر synthetic fallback، trust را synthetic برگردون نه live

**P1 - برای نمره 9:**
4. [ ] Any usage را از 143 به <50 برسون - حداقل برای فایل‌های جدید `chart_builder.py` و `forex_provider.py`
5. [ ] God file 80KB رو یا حذف کن یا بگذار فقط وقتی `?legacy=1` باشد لود شود

**P2:**
6. [ ] Custom indicator iteration limit + timeout

اگر این 6 تا را فیکس کنی، نمره از 7.8 به 9.0 میره و فایل نهایی عالی میشه.

---

## نمره با دید بی‌رحم و بی‌طرف

| محور | v0.9 فعلی | بعد از فیکس 6 مورد بالا |
|------|-----------|------------------------|
| امنیت | 8.0 (per-path خوب ولی Any زیاد) | 9.5 |
| درستی داده | 8.5 (forex synthetic باگ trust) | 9.5 |
| معماری | 8.0 (event bus خوب ولی god file هنوز) | 9.0 |
| تست | 6.0 (17 تست ولی برای forex و chart تست نداری) | 8.0 |
| پرفورمنس | 8.5 | 9.0 |
| نگهداری | 7.0 (12 ماژول خوب ولی god file) | 9.0 |
| **میانگین** | **7.8** | **9.0 عالی** |

**جمع‌بندی بی‌رحمانه:** ایده‌های خلاقانه‌ات (فارکس + اندیکاتور شخصی + اپ) عالیه و از هر 3 سایت بهتره، ولی اجرای فنی‌ات هنوز 2 تا باگ P0 سطحی داره (PWA icon و version). فیکسشون کن، فایل نهایی رو بفرست.

امضا: بازرس بی‌رحم بی‌طرف - v0.9
