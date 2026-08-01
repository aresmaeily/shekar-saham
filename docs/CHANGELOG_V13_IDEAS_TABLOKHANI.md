# CHANGELOG v1.3 — پیاده‌سازی ایده‌های بهبود (بر اساس تحلیل تابلوخوانی)

ایده‌های پیشنهادی از تحلیل تصاویر سایت تابلوخوانی، اینجا پیاده‌سازی شدند:

## ۱) نمره ترکیبی «جریان هوشمند» (ایده ۱.۳) ✅
- هر ردیف پول داغ حالا `flow_score` (۰-۱۰۰) دارد: ترکیب سرانه، قدرت خریدار، حجم غیرعادی، هم‌سویی قیمت با جهت پول و خالص حقیقی.
- در جدول پول داغ ستون «جریان» با نوار رنگی اضافه شد.
- `backend/app/engines/screener.py::_flow_score`

## ۲) نمای هیتمپ پول داغ (ایده ۱.۱) ✅
- دکمه «🔥 هیتمپ» در تب پول داغ: کاشی‌های رنگی که اندازه = شدت جریان و رنگ = جهت (سبز خرید / قرمز فروش).
- `frontend/js/app.js::renderHot` + استایل `#hotHeatmap`

## ۳) قهرمانان شکار — ورود پول در قیمت منفی (ایده ۲.۱) ✅
- در بازی بازار، `hunt_champion` محاسبه می‌شود: ورود پول هوشمند/حقیقی در قیمت منفی + حجم غیرعادی + خالص حقیقی مثبت → کاندید صف خرید.
- کارت‌های برجسته بالای جدول + هایلایت ردیف‌ها.
- `backend/app/engines/screener.py::build_market_game`

## ۴) ماتریس گرمایی تحرکات بزرگان (ایده ۳.۱) ✅
- دکمه «🌡 ماتریس گرمایی» در تب تحرکات بزرگان: کاشی‌های رنگی بر اساس شدت تغییر خالص پول.
- `frontend/js/app.js::renderBig`

## ۵) دماسنج بازار (ایده ۵.۱) ✅
- `thermometer` در overview: نمره -100..+100 از ترکیب عرض بازار، ارزش معاملات، پول داغ، هشدارها و خالص حقیقی.
- نوار رنگی در stats bar (صعودی/نزولی/خنثی).
- `backend/app/engines/screener.py::build_thermometer`

## ۶) حمایت/مقاومت خودکار روی چارت فارکس (ایده ۴.۱) ✅
- دکمه «🛡 حمایت/مقاومت»: تشخیص نقاط چرخش (swing high/low) و رسم خطوط حمایت/مقاومت افقی + خوشه‌بندی.
- `frontend/js/modules/support_resistance.js` + متد `toggleSupportResistance` در `tradingview_excellent.js`

## فایل‌های تغییر یافته
- `backend/app/models/schemas.py` (flow_score, hunt_champion, thermometer)
- `backend/app/engines/screener.py` (نمره جریان، قهرمان شکار، دماسنج)
- `frontend/js/app.js` (renderThermo, renderHot+هیتمپ, renderBig+ماتریس, renderGame+قهرمانان)
- `frontend/js/modules/forex.js`, `frontend/js/modules/render/tradingview_excellent.js`
- `frontend/js/modules/support_resistance.js` (جدید)
- `frontend/index.html`, `frontend/css/app.css`

## اسکرین‌شات‌ها
- ۲۸ اسکرین‌شات از همه منوها در `screenshots/` + `gallery.html`
- نکته: داده mock است (فقط ۲ ردیف پول داغ داغ و ۶ با پلاس) — با داده زنده TSETMC تعداد بیشتر می‌شود.
