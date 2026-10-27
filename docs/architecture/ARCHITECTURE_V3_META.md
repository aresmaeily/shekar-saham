# 🏗️ معماری Meta — رادار بورس v3 (بازطراحی یکپارچه)

> طراحی شده توسط: طراح تراز اول · تاریخ: ۲۰۲۶-۰۸-۰۱
> هدف: حذف کامل god-file ها، یک‌سویه‌سازی جریان داده، اسکیمامحوری، بدون حتی یک شلختگی.

---

## ۱) اصول معماری (Design Principles)

| اصل | توضیح |
|-----|-------|
| **یک‌سویه بودن داده (Unidirectional)** | `API → Store → Component → DOM` — هیچ کامپوننتی مستقیم fetch نمی‌کند |
| **اسکیمامحور (Schema-Driven)** | یک کامپوننت جدول، همه تب‌های جدولی را با کانفیگ رندر می‌کند؛ بدون تکرار |
| **ثبت مرکزی تب‌ها (Registry)** | هر تب یک ماژول با `{id, label, icon, render}` — افزودن تب = یک فایل |
| **روتر واحد** | تغییر تب از طریق `hash` → قابل بوک‌مارک و بازگشت مرورگر |
| **خطای متمرکز** | همه خطاها در `api.js` → toast + قفل auth؛ هیچ `try/catch` پراکنده‌ای |
| **تزریق اعتماد (Auth Interceptor)** | توکن فقط در یک نقطه به همه fetch ها اضافه می‌شود |
| **Tokens طراحی** | همه رنگ‌ها/فاصله‌ها متغیر CSS — تم = override متغیرها |
| **کد بدون مرده** | هر فایل استفاده می‌شود؛ ایمپورت‌های بلااستفاده ممنوع (pyflakes clean) |

## ۲) ساختار فرانت‌اند (Layered)

```
frontend/
├── index.html                  ← پوسته (shell) — فقط ساختار، بدون منطق
├── css/
│   └── app.css                 ← design tokens + استایل (RTL)
└── js/
    ├── main.js                 ← بوت‌استرپ: core را سوار و تب‌ها را ثبت می‌کند
    ├── core/                   ← لایه زیرساخت (هیچ دانشی از تب‌ها ندارد)
    │   ├── store.js            ← state مرکزی + pub/sub
    │   ├── api.js              ← fetch wrapper: auth + error + retry + toast
    │   ├── format.js           ← اعداد/پول/درصد fa-IR (منبع واحد)
    │   ├── router.js           ← روتر hash (ثبت تب → فعال‌سازی)
    │   └── events.js           ← باس رویداد (auth-required, toast, ...)
    ├── components/             ← کامپوننت‌های عمومی (بدون وابستگی به تب)
    │   ├── data-table.js       ← جدول اسکیمامحور (مرتب‌سازی + CSV)
    │   ├── kpi-cards.js        ← کارت‌های خلاصه
    │   ├── thermometer.js      ← دماسنج بازار
    │   └── heat-tiles.js       ← کاشی‌های هیت‌مپ
    ├── tabs/                   ← لایه تب‌ها (هر تب یک ماژول)
    │   ├── data.js             ← ۱۲ تب جدولی اسکیمامحور
    │   ├── forms.js            ← ۶ تب فرم (تنظیمات/بک‌تست/اختیار/...)
    │   └── ...
    └── modules/                ← ماژول‌های تخصصی (فارکس/رپلای/VP/...)
```

**قانون لایه‌ها:** `core` → `components` → `tabs` → `main`. لایه‌های بالا هرگز به پایین import نمی‌کنند (جهت وابستگی یک‌طرفه).

## ۳) جریان داده (مثال تب پول داغ)

```
main.js ── boot ──► router.register({id:'hot', render: tabs.hot})
روی کلیک تب ──► router.activate('hot')
              ──► store.subscribe → tabs.hot.render(host, store)
              ──► components/data-table.render(host, {columns, rows})
rows از store.analysis.hot_money — که توسط refresh() (api.js) پر شده
```

**هیچ کامپوننتی** مستقیماً `fetch` نمی‌کند؛ همه از store می‌خوانند. refresh مرکزی در main.js همه‌چیز را پر می‌کند.

## ۴) قرارداد جدول اسکیمامحور

```js
{
  columns: [
    { key: "symbol", label: "نماد", render: (r) => `<span class="sym">${esc(r.symbol)}</span>` },
    { key: "plp",    label: "٪",    format: "pct", sortable: true },
    { key: "flow_score", label: "جریان", format: "flow", cls: (r) => r.side==="buy" ? "pct-up" : "pct-down" },
  ],
  rows: store.analysis.hot_money,
  empty: "موردی نیست",
  rowClick: (r) => openSymbol(r.symbol),
}
```

## ۵) بک‌اند (لایه‌بندی موجود + پالایش)

```
backend/app/
├── main.py        ← بوت: middleware chain + router ها + استارتاپ
├── core/          ← config, security, rate_limiter, audit, crypto, errors
├── api/           ← فقط HTTP (اعتبارسنجی ورودی + فراخوانی service)
├── services/      ← منطق کسب‌وکار (market_service, notifier, ws_hub)
├── engines/       ← الگوریتم‌های خالص (بدون I/O): screener, indicators, ...
├── data/          ← دسترسی داده (store SQLite, providers, forex_provider)
├── models/        ← Pydantic schema ها (مرز ورودی/خروجی)
└── repositories/  ← لایه ذخیره‌سازی انتزاعی
```

- `api` فقط ورودی را اعتبارسنجی می‌کند؛ `engines` خالص و تست‌پذیر؛ `data` تنها جایی که به شبکه/دیسک می‌زند.
- خطاها: یک شکل واحد (`{"detail": ...}`) — هندلر سراسری بدون بازتاب ورودی.
- دپندنسی‌ها **پین‌شده** (reproducible) + اسکن pip-audit پاک.

## ۶) امنیت یکپارچه

| لایه | مسئولیت |
|------|---------|
| `core/security.py` | توکن HMAC، `is_public_path` (بدون باگ startswith)، هدرهای OWASP |
| `core/rate_limiter.py` | ۵/min ورود، ۱۵/min حساس، ۱۵۰/min عمومی — IP امن (TRUST_PROXY) |
| `core/api/auth.py` | ورود مالک + جلسه ۲۴ساعته |
| `frontend/js/core/api.js` | interceptor توکن — هیچ fetch دستی خارج از آن ممنوع |
| `frontend/js/core/auth.js` | قفل UI + خروج — یک نقطه |

## ۷) استاندارد کیفیت (بازرسی خودکار)

1. `pytest` — ۴۹+ تست (unit + رگرسیون امنیتی)
2. `pip-audit -r requirements.txt` — صفر CVE
3. `pyflakes app/` — صفر ایمپورت مرده
4. تست مرورگر E2E — صفر console error / 404 / page error

---

## ✅ وضعیت پیاده‌سازی (تکمیل و تأییدشده)

| لایه | وضعیت |
|------|--------|
| `js/core/` (store, api, format, events, router) | ✅ پیاده‌سازی شد |
| `js/components/` (data-table اسکیمامحور, kpi-cards, thermometer, heat-tiles) | ✅ پیاده‌سازی شد |
| `js/tabs/` (data, forms, actions) | ✅ پیاده‌سازی شد — ۲۳ تب |
| `js/main.js` (بوت‌استرپ تمیز) | ✅ جایگزین god-file ۲۰۵۴ خطی |
| `js/legacy/app.js` | ✂️ حذف شد (WS-HARDEN-1/W3 — ماژولارسازی کامل شد؛ مسیر `?legacy` بازنشسته شد) |
| بک‌اند: pyflakes تمیز | ✅ **صفر** ایمپورت مرده |
| دپندنسی‌ها: پین‌شده + اسکن‌شده | ✅ `No known vulnerabilities` |
| تست‌ها | ✅ ۴۹ پاس |

### نتایج تأیید E2E (مرورگر واقعی)
- **۲۳ تب + فارکس (ولیو پرفایل/رپلای/اندیکاتور) + ۲ صفحه نماد** → صفر console error · صفر 404 · WS متصل
- حالت خصوصی: قفل → ورود → داده → ریلود خودکار، با **صفر خطای کنسول قبل و بعد از ورود** (گیت auth در main.js)
- `?legacy=1` همچنان نسخه قدیمی را اجرا می‌کند (بازیابی امن)

---

*این سند، قرارداد اجرایی است. هر فایل جدید باید از این قوانین پیروی کند؛ هر مغایرت = باگ.*
