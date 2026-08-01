# CHANGELOG v1.0 — فارکس: طلا + بروکرها + شاخص‌های جهانی + ولیو پرفایل

## ۱) نمادهای جدید در بخش فارکس

| نماد | توضیح | بروکر / مرجع | منبع داده واقعی |
|------|-------|--------------|------------------|
| `XAUUSD` | طلا / دلار (اسپات) | **BlackBull** / **Pepperstone** / **FXCM** | PAXGUSDT از data-api.binance.vision (پشتیبان: OKX، KuCoin، Yahoo GC=F) |
| `GC1` | طلا فیوچرز | **COMEX** | Yahoo `GC=F` (بازار کومکس) |
| `DXY` | شاخص دلار | **TVC** | Yahoo `DX-Y.NYB` (ICE) |
| `US500` | S&P 500 | **Capital.com** | Yahoo `^GSPC` |
| `US100` | نزدک ۱۰۰ | **Capital.com** | Yahoo `^NDX` |
| `US30` | داو جونز | **Capital.com** | Yahoo `^DJI` |
| `UKOIL` | نفت برنت | **Capital.com** | Yahoo `BZ=F` |

> نکته: در درخواست «us100, us100» نوشته شده بود؛ چون Capital.com هر سه شاخص US500 / US100 / US30 را دارد، هر سه اضافه شدند (US100 + US30 + US500).

## ۲) بروکرها (مانند faraz.io)

- برای نماد طلا (`XAUUSD`) سه بروکر **BlackBull، Pepperstone، FXCM** انتخاب می‌شود.
- دکمه‌های بروکر به‌صورت پویا بر اساس نماد انتخابی ساخته می‌شوند (برای GC1 فقط COMEX، برای DXY فقط TVC، برای شاخص‌ها و برنت فقط Capital.com).
- بروکر در درخواست API ارسال می‌شود: `/api/v09/forex/XAUUSD?broker=fxcm`

## ۳) دیتای واقعی بدون API Key (رفع مسدودیت Binance)

- منبع اصلی طلا/کریپتو از `data-api.binance.vision` (آینه عمومی) است — چون `api.binance.com` در برخی مناطق 451 می‌دهد.
- زنجیره پشتیبان: Binance → OKX → KuCoin → Yahoo → سنتتیک (آفلاین).
- جفت‌ارزها (EURUSD/GBPUSD/USDJPY) هم حالا دیتای واقعی Yahoo دارند.
- اگر هیچ منبعی در دسترس نبود، داده سنتتیک با الگوی واقعی طلا/بیت‌کوین ساخته می‌شود (بدون کرش).

## ۴) اندیکاتور ولیو پرفایل (Volume Profile)

- فایل جدید: `frontend/js/modules/volume_profile.js`
- دکمه «📊 ولیو پرفایل» در هدر بخش فارکس.
- محاسبه: توزیع حجم هر کندل روی محدوده قیمت آن کندل → باندهای قیمتی.
- خروجی: **POC** (نقطه کنترل)، **VAH/VAL** (ناحیه ارزش ۷۰٪) + درصد ناحیه ارزش.
- رندر: هیستوگرام افقی سمت راست چارت (همگام با محور قیمت) + خطوط قیمتی POC/VAH/VAL.
- با هر تغییر نماد / تایم‌فریم / اسکرول / زوم دوباره محاسبه و رسم می‌شود.
- در صفحه نماد (`symbol.html`) هم اگر از ExcellentChart استفاده کند فعال است.

## ۵) تایم‌فریم‌ها

- دکمه‌های جدید: `30m` و `1h` (مجموع: 1m / 5m / 15m / 30m / 1h / 1D)

## ۶) رفع باگ

- `index.html` حالا کتابخانه `lightweight-charts` را لود می‌کند (قبلاً نبود و چارت فارکس کرش می‌کرد).

## ۷) فایل‌های تغییر یافته

- `backend/app/data/forex_provider.py` — بازنویسی: نمادها، بروکرها، یاهو/OKX/KuCoin، سنتتیک
- `backend/app/api/forex.py` — broker query + متادیتا + تایم‌فریم 30m
- `backend/tests/test_forex.py` — جدید (۸ تست)
- `frontend/js/modules/volume_profile.js` — جدید
- `frontend/js/modules/forex.js` — بازنویسی (بروکر + ولیو پرفایل)
- `frontend/js/modules/render/tradingview_excellent.js` — پشتیبانی ولیو پرفایل
- `frontend/index.html` — CDN لایبرری + پنل جدید فارکس
- `frontend/css/app.css` / `frontend/css/symbol.css` — استایل‌ها
