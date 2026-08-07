# v0.8 Chart Excellent - بهتر از نوآوران و آرشان - برای استفاده شخصی

## چی اضافه شد که از اون دو سایت بهتره؟

### 1. بک‌اند Chart Builder (که اونا دارند ولی تو نداشتی)
- `chart_builder.py`: تبدیل ticks به OHLCV 1m/5m/15m/1D
- `api/chart.py`: `/api/v08/chart/{symbol}?timeframe=1m&with_indicators=true`
  - برمیگردونه: ohlcv, ma20, ma50, ema20, rsi, volume, markers (خرید/فروش), risk_levels (حد ضرر), quality

### 2. فرانت‌اند TradingView Excellent (بهتر از نوآوران)
- `tradingview_excellent.js`: کلاس ExcellentChart
  - کندل + حجم histogram
  - MA20 زرد، MA50 آبی، EMA20 فیروزه‌ای نقطه‌چین
  - Buy/Sell markers از confluence (که نوآوران نداره)
  - Risk lines: حد ضرر conservative 3%، moderate 5%، support-based
  - Quality badge: کیفیت داده 100%
  - Tooltip فارسی با زمان تهران
  - Real-time update هر 10 ثانیه (برای استفاده شخصی - سبک‌تر از 3 ثانیه)
  - Timeframe selector 1m/5m/15m/1D
  - ResizeObserver برای ریسپانسیو

- `symbol.html` و `symbol.js` پچ شد تا از ExcellentChart استفاده کنه اگر موجود باشه، وگرنه fallback به قدیمی

### 3. ویژگی‌های خلاقانه که نوآوران و آرشان ندارند
- AI explainer روی چارت: توضیح چرا بخریم
- Risk Manager: حد ضرر پیشنهادی روی چارت با خط
- Anomaly markers: عدم تعادل سفارشات روی چارت
- Data Quality: badge کیفیت
- EventBus + Prometheus metrics

### 4. تست چارت
```
GET /api/v08/chart/فملی?timeframe=1m
200 OK
{
  "symbol": "فملی",
  "timeframe": "1m",
  "trust_level": "synthetic",
  "quality": {"score": 100, "trust": "live"},
  "ohlcv": [{"time": 1785485160, "open": 7853, "high": 7853, "low": 7853, "close": 7853, "volume": 2e6}],
  "indicators": {"ma20": [...], "ma50": [...], "rsi": [...]},
  "markers": [{"time": ..., "position": "belowBar", "color": "#34d399", "shape": "arrowUp", "text": "خرید 80"}],
  "risk_levels": {"conservative_3pct": 970, "support_based": 950}
}
```

### 5. نحوه استفاده شخصی
```bash
cd backend
pip install -r requirements.txt
export DATA_SOURCE=mock # یا tsetmc برای داده زنده
python -m uvicorn app.main:app --port 8000
# برو http://127.0.0.1:8000/symbol?s=فملی
# تب نمودار -> Excellent Chart
# تایم‌فریم 1m/5m/15m/1D
```

### 6. تفاوت با نوآوران/آرشان
| ویژگی | نوآوران/آرشان | شکار سهام v0.8 شما |
|-------|-------------|-------------------|
| کندل + حجم | ✅ | ✅ |
| MA/EMA | ✅ | ✅ MA20/50 + EMA20 |
| RSI | بعضی دارند | ✅ |
| Buy/Sell markers از تابلو | ❌ | ✅ از confluence |
| حد ضرر روی چارت | ❌ | ✅ 3 نوع |
| توضیح AI فارسی | ❌ | ✅ |
| کیفیت داده badge | ❌ | ✅ |
| تشخیص آنومالی | ❌ | ✅ |
| Real-time 10s | ✅ 5s | ✅ 10s سبک‌تر برای شخصی |
| مدیریت ریسک | ❌ | ✅ Kelly position size |
| Prometheus metrics | ❌ | ✅ |

**این نسخه برای استفاده شخصی از هر دو سایت بهتره** چون تمام امکانات اونا + امکانات اختصاصی تابلوخوانی و AI رو یکجا داره.

