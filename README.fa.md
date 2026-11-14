<div align="center">

# رادار بورس (RADAR BOURSE)

**پلتفرم تحت‌وب تابلوخوانی و رصد حرفه‌ای سهام بورس ایران** — الهام‌گرفته از [tablokhani.com](https://tablokhani.com)

[![CI](https://github.com/aresmaeily/shekar-saham/actions/workflows/ci.yml/badge.svg)](https://github.com/aresmaeily/shekar-saham/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/aresmaeily/shekar-saham)](https://github.com/aresmaeily/shekar-saham/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](README.md) | **فارسی**

</div>

## هدف

شناسایی به‌موقع:

- **ورود پول هوشمند** و افزایش حجم غیرعادی
- سهم‌هایی که در **قیمت‌های منفی** احتمال ورود به **صف خرید** دارند
- فیلتر **بنیادی** (P/E پایین، EPS مناسب، گزارش‌محور)
- **هشدار خروج** بر اساس خروج پول، عرضه سنگین و تضعیف قدرت خریدار

## معماری فازبندی

| فاز | محتوا | وضعیت |
|-----|--------|--------|
| **۱** | هسته شکار: پول هوشمند، حجم مشکوک، سیگنال ورود/خروج، بنیادی ساده، داشبورد | Done |
| **۲** | اسنپ‌شات SQLite، تحرکات بزرگان، تابلو کستیک، پورتفو، هشدارها، تنظیمات UI | Done |
| **۳** | صفحه نماد + نمودار، نقشه بازار، فیلترنویسی DSL، بنیادی، پول داغ ریزمعاملات | Done |
| **۴** | WebSocket، تلگرام/بله، بک‌تست، اختیار معامله | Done |
| **۵** | رفع P0/P1 بازرسی: trust level، flow coverage، امنیت API Key، قفل refresh، کش بنیادی | Done |
| **۶** | فارکس پرو: طلا با بروکرهای BlackBull/Pepperstone/FXCM، GC1 (COMEX)، DXY (TVC)، S&P500/US100/US30/نفت برنت (Capital.com) + اندیکاتور ولیو پرفایل | Done |

## شروع سریع

### گزینه الف — نصب‌کننده ویندوز (دسکتاپ)

آخرین نسخه نصب‌کننده را از صفحه [**Releases**](https://github.com/aresmaeily/shekar-saham/releases) دانلود کنید. این نصب‌کننده به‌صورت خودکار توسط CI از یک SHA دقیق سورس ساخته می‌شود (اطلاعات ساخت — SHA سورس، حجم و SHA-256 — در لاگ عمومی ساخت و در فایل `RELEASE_PROVENANCE.json` داخل برنامه ثبت می‌شود).

> نصب‌کننده **امضای دیجیتال ندارد**؛ ممکن است Windows SmartScreen هشدار دهد — گزینه «More info → Run anyway» را انتخاب کنید. پوسته دسکتاپ، بک‌اند FastAPI را همراه خود باندل می‌کند و داشبورد را به‌صورت محلی سرو می‌کند.

### گزینه ب — داکر

```bash
./install.sh --docker        # ساخت و اجرا با Docker Compose
# یا
docker compose up --build
```

سپس `http://localhost:8000` را باز کنید.

### گزینه ج — اجرا از سورس

```bash
# نصب وابستگی‌ها
cd backend && pip install -r requirements.txt

# اجرای سرور (با داده دمو اگر TSETMC در دسترس نباشد)
python -m app.main

# مرورگر
open http://127.0.0.1:8000
```

### متغیرهای محیطی (اختیاری)

```bash
export DATA_SOURCE=mock          # mock | tsetmc | brsapi
export BRSAPI_KEY=your_key
export TSETMC_BASE=https://cdn.tsetmc.com
export POLL_SECONDS=30
```

## ابزارهای اصلی (مشابه تابلوخوانی)

1. **پول داغ** — معاملات حقیقی درشت > ۲۰۰ میلیون تومان  
2. **پول داغ پلاس** — بازه ۱۰۰–۲۰۰ میلیون  
3. **بازی بازار** — رفتار حقیقی بزرگ / متوسط / خرد  
4. **تحرکات بزرگان** — ورود/خروج پول داغ در بازه‌های ۱۰ دقیقه‌ای  
5. **شکار ورود** — ترکیب حجم مشکوک + قدرت خریدار + قیمت منفی نزدیک صف  
6. **هشدار خروج** — خروج پول، نسبت فروش بالا، تضعیف سرانه  
7. **فیلتر بنیادی** — P/E، EPS، ارزش بازار  
8. **شکار صنعت** — جریان نقدینگی گروهی  

## منبع داده

- **اولویت ۱:** اتصال مستقیم به APIهای عمومی `cdn.tsetmc.com` / MarketWatch  
- **اولویت ۲:** BrsApi (کلید رایگان)  
- **حالت توسعه:** ژنراتور دمو با ساختار واقعی نمادهای بورس تهران  

> در محیط‌هایی که به اینترنت ایران/TSETMC دسترسی نیست، سیستم به‌صورت خودکار روی **داده دمو** سوئیچ می‌کند تا UI و الگوریتم‌ها کامل تست شوند؛ بنر trust در UI همیشه سطح اعتماد داده (زنده یا دمو) را شفاف اعلام می‌کند.

## ساختار پروژه

```
radar-bourse/
├── backend/          # FastAPI + موتورهای تحلیلی
│   └── app/
│       ├── api/      # REST endpoints
│       ├── engines/  # الگوریتم‌های تابلوخوانی و سیگنال
│       ├── data/     # منابع داده (TSETMC / Mock)
│       ├── models/   # مدل‌های داده
│       ├── core/     # تنظیمات
│       └── services/ # سرویس‌های کسب‌وکار
├── frontend/         # داشبورد RTL فارسی
├── electron/         # پوسته دسکتاپ ویندوز + ساخت نصب‌کننده
├── android-app/      # پوسته آزمایشی Capacitor
├── e2e/              # تست‌های انتها به انتها
├── data/             # کش و داده نمونه
├── docs/             # مستندات ساختاریافته: STATUS، معماری، active و archive
└── scripts/          # اسکریپت‌های کمکی
```

## مستندات

| سند | محتوا |
|-----|--------|
| [README.md](README.md) | همین سند به زبان انگلیسی |
| [docs/STATUS.md](docs/STATUS.md) | وضعیت فعلی پروژه |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | رکورد تفصیلی تغییرات مرحله‌به‌مرحله |
| [CHANGELOG.md](CHANGELOG.md) | خلاصه تاریخچه انتشارها |
| [docs/design/](docs/design/) | سیستم طراحی، ممیزی‌های UI/UX و شواهد مرورگر |
| [CONTRIBUTING.md](CONTRIBUTING.md) | راهنمای مشارکت در پروژه |
| [SECURITY.md](SECURITY.md) | سیاست امنیتی و گزارش آسیب‌پذیری |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | اصول رفتاری جامعه |

## هشدار مهم

این نرم‌افزار **ابزار کمکی تحلیل** است و سیگنال قطعی خرید/فروش نیست. مسئولیت معاملات با کاربر است.

## مجوز

این پروژه تحت [مجوز MIT](LICENSE) منتشر می‌شود.
