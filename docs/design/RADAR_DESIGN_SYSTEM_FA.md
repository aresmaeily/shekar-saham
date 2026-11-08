# سیستم طراحی RADAR (RADAR Design System) — v1.0

**تاریخ:** 2026-11-08 | **پیاده‌سازی در کد:** `frontend/css/tokens.css` (منبع یگانه)، `frontend/css/app.css` (اجزا)، `frontend/css/chart_pro.css` و `frontend/css/symbol.css` (مصرف توکن‌ها)
**الهام:** اصول Apple Human Interface Guidelines (Clarity، Deference، Depth، Consistency، Simplicity، Flexibility، Craft، Accessibility) — بازطراحی مستقل برای وب‌اپ تخصصی بازار سرمایه؛ **بدون کپی‌برداری از لوگو/رابط اپل.**
**قاعدهٔ انضباطی:** هیچ فایل CSS دیگری مجاز به تعریف رنگ literal جدید نیست؛ همهٔ رنگ‌ها/فاصله‌ها/حرکت‌ها از `tokens.css` مصرف می‌شوند.

---

## ۱. هویت برند

- **شخصیت بصری:** «رادارِ دقیق» — ابزار حرفه‌ای رصد بازار: آرام، دقیق، داده‌محور؛ بدون تزئین نمایشی. محتوا و داده همیشه جلوتر از پوسته (Deference).
- **زبان بصری:** سطوح خنثیِ مرکب (ink)، یک رنگ کنش مطمئن (آبی)، و یک لهجهٔ هویتی «رادار» (فیروزه‌ای) که فقط در سه جا ظاهر می‌شود: نشانگر تب/خوشهٔ فعال، حلقهٔ فوکوس، و نقطهٔ زنده/سوئیپ لوگو. رنگ‌های بازار (سبز/سرخ) فقط برای معنای صعود/نزول.
- **نشان (لوگو):** مارک SVG داخلی `#i-logo` — رادار چهارجهته با سوئیپ قطری (sprite در `index.html`)؛ زمینهٔ مرکب تیره در هر دو تم، بدون گرادیان تزئینی.
- **ضدقالب:** حذف گرادیان‌های چندرنگ (قبلاً روی تب فعال/کارت‌ها/بنرها)، حذف Emoji به‌عنوان آیکون، یکسان‌سازی چیپ‌ها/دکمه‌ها/کارت‌ها.

## ۲. Typography

| توکن | مقدار | کاربرد |
|---|---|---|
| `--font` | Vazirmatn (+ Segoe UI/system-ui fallback) — باندل محلی woff2، ۵ وزن | همهٔ متن‌ها |
| `--font-mono` | ui-monospace/Cascadia/Consolas | DSL فیلترنویسی، کد |
| `--fs-11 … --fs-28` | 11/12/13/14/15/16/18/22/28px | مقیاس کامل؛ عنوان پنل 22/800، بدنه 14، برچسب 11–12/600 |
| `--lh-tight / --lh-base` | 1.35 / 1.6 | تیتر / بدنه |
| اعداد مالی | `font-variant-numeric: tabular-nums` روی `.num`، سلول‌های جدول، `.stat strong`، `.icard .big`، `.kv b`، قیمت hero | تراز عمودی ارقام در مقایسه‌ها |

- ارقام فارسی به‌عنوان محتوای داده (از بک‌اند/فرمت‌کننده) حفظ شد؛ قاعدهٔ جدید: **هیچ mixes لاتین/فارسی در یک ستون عددی** — واحدهای لاتین فنی (`x` ضریب) فقط با ارقام tabular.

## ۳. Color System

**Primitives** (`--p-*`): ink-950…700، slate-400…900، radar-300…700، brand-300…500، up-300…500، down-300…500، warn-300…500، info-400/500، violet-400/500.

**Semantic tokens (هر تم):**

| نقش | تیره | روشن |
|---|---|---|
| `--bg` | `#0b0f17` | `#f6f7f9` |
| `--surface-1/2/3` | ink-850/800/750 | #fff / #f6f7f9 / #eef0f4 |
| `--border / --border-strong` | rgba(148,163,184,.14/.26) | rgba(15,23,42,.10/.18) |
| `--text / --text-2 / --text-3` | #e7ecf3 / slate-400 / #7c8798 | slate-900 / slate-600 / **#5f6b7a** (AA) |
| `--brand` / `--brand-btn-bg` | #3b82f6 / **#1d4ed8** (متن سفید 6.7:1) | #2563eb / #1d4ed8 (6.7:1) |
| `--radar` | #22d3ee | #0891b2 |
| `--up / --down / --warn / --info / --accent` | 400-ها + نسخهٔ `-soft` (زمینهٔ ۱۳٪) | 500-ها + `-soft` |
| `--warn-strong` | **#fcd34d** (متن هشدار روی تیره 10.9:1) | **#92400e** (روشن 5.8:1) |

**معنای رنگ بازار:** سبز=فروش/ورود پول/صعود؛ سرخ=خریدِ اجباری/خروج پول/نزول (قرارداد بورس تهران)؛ کهربایی=هشدار/دمو/تأییدنشده؛ فیروزه‌ای=هویت/فعال؛ بنفش=هوش/امتیاز؛ خاکستری=خنثی/رصد. **هرگز رنگ به‌تنهایی معنا نمی‌دهد** — همیشه متن/شکل/نشان همراه است.

**کنتراست (اندازه‌گیری واقعی، WCAG 2.2 AA):** هر دو تم اندازه‌گیری شد با ترکیب آلفای واقعی لایه‌ها — دکمهٔ primary 6.7:1، بنر اعتماد 10.9:1 (تیره)/5.8:1 (روشن)، سرستون جدول 5.06:1 (روشن)/4.69:1 (تیره)، برچسب کارت 5.43:1/5.03:1، متن muted 5.98:1/7.26:1. نمونه‌گیر: `docs/design/evidence/after/` + ارقام در ماتریس HIG.

## ۴. Spacing، Grid و Layout

- **فاصله:** `--sp-1…--sp-10` = 4/8/12/16/20/24/32/40px — همهٔ پدینگ/گپ‌ها از همین مقیاس.
- **شبکه:** محتوای اصلی `max-width: 1440px` مرکز‌چین؛ نوار آمار ۹ ستونه (۵/۴/۲ ستون در 1280/1024/768px)؛ گرید کارت‌ها `auto-fill minmax(230px,1fr)`؛ جدول‌ها `min-width: 960px` با اسکرول افقی مهارشده داخل `table-wrap`.
- **تراز:** عنوان/توضیح/کنترل هر پنل در `panel-head` با خط جداکننده — سلسله‌مراتب یکسان در ۳۲ پنل.
- **Responsive:** نقطه‌های شکست 1280/1024/768/560؛ موبایل: تیتربار دو ردیفهٔ منظم، ناوبری خوشه‌ای با منوی bottom-sheet، کارت‌های ۲ ستونه؛ `env(safe-area-inset-bottom)` رعایت شده.

## ۵. Component Inventory (کتابخانهٔ اجزا)

همهٔ اجزا در `app.css` با حالت‌های `normal / hover / active / focus-visible / disabled / loading / error`:

| جزء | کلاس‌ها | نکته |
|---|---|---|
| Button | `.btn` + `.primary/.ghost/.tiny/.danger-outline/.loading` | `:active` فشار 1px؛ `.loading` اسپینر؛ disabled نیمه‌شفاف |
| Input | `.text-input`, `.setting-card input`, `.filter-editor` | hover/focus ring فیروزه‌ای؛ placeholder رنگ توکن |
| Search | `#paletteBtn` (پالت فرمان Ctrl+K)، `.search-results` | نتیجه‌ها با hover brand-soft |
| Filters | `.filters`, `.chip`, `.seg` | seg با کنداسلید سفید/سایهٔ ظریف |
| Tabs/Nav | `.nav-groups`, `.nav-group(-btn/-menu)`, `.tab(.active)` | ۶ خوشه × ۳۲ مسیر؛ نشانگر رادار زیر خوشهٔ جاری؛ Esc/کلیک بیرون می‌بندد؛ موبایل bottom-sheet |
| Cards | `.stat`, `.icard`, `.card`, `.setting-card`, `.hunt-card` | سایهٔ e-1؛ hover فقط border |
| Tables | `.table-wrap`, `.data-table` (+ `.sym/.name/.score/.grade/.tag/.pct-*/.bias/.reasons`) | سرستون sticky، ردیف ۴۴–۵۶px، tabular-nums، اسکرول داخلی |
| Dropdown/Dialog | `.nav-group-menu`, `.modal(.card/.close)` | انیمیشن t-med؛ backdrop blur |
| Tooltip | `title` + `.cp-tooltip` (چارت) | — |
| Notifications | `.toast(.error/.warn)`, `.rate-limit-toast` | گوشه، سایهٔ e-3 |
| Badges | `.score(.high/.mid/.low/.danger)`, `.grade`, `.tag(.hot/.fund/.vol)`, `.cp-badge`, `.side-pill` | همه با زمینهٔ soft هم‌خانواده |
| Charts | `.cp-*` (toolbar/layout/watchlist/osc) | توکن‌محور؛ RTL-safe |
| Empty State | `.empty`, `tbody:empty::after` («در حال دریافت داده…») | جای خالی بی‌پیام ممنوع |
| Loading | `.skeleton td::after`, `.btn.loading` | شیمر ۱.۳s |
| Error | `.toast-error`, `.trust-banner(.demo/.mixed/.live)`, `.rate-limit-toast` | متن اقدام‌پذیر |

## ۶. Iconography

- **Sprite SVG داخلی** با ۳۵ symbol خطی 24×24، `stroke-width: 1.8`، round cap — اندازه‌های استاندارد 15px (تب/دکمه) و 22px (لوگو).
- **Emoji به‌طور کامل از ناوبری و دکمه‌های سراسری حذف شد** (۳۲ تب + تیتربار)؛ فقط متن‌های داده‌محور (مثل عنوان تب) که تست‌ها قراردادشان را پین کرده‌اند دست‌نخورده ماندند.
- هر آیکون معنای مشخص دارد (flag=جمع‌بندی، crosshair=شکار، flame=پول داغ، …) و `aria-hidden` است — برچسب متنی همیشه همراه آیکون.

## ۷. Motion

- `--t-fast/med/slow` = 120/200/320ms با `cubic-bezier(.2,.8,.2,1)`؛ فقط transform/opacity؛ هیچ انیمیشن سنگین.
- `@media (prefers-reduced-motion: reduce)` → همهٔ انیمیشن/ترنزیشن تقریباً صفر (احترام به تنظیم سیستم — HIG Motion).
- بازخورد تعامل: فشار دکمه (translateY 1px)، فید پنل 200ms، شیمر skeleton، hover border-color.

## ۸. دسترس‌پذیری (WCAG 2.2 AA)

- `:focus-visible` سراسری با `--focus-ring` (رینگ سفید + فیروزه‌ای) — آزمون Tab واقعی ✓
- کنتراست AA در هر دو تم (جدول §۳)؛ هدف تعامل ≥ 34px (دکمه‌ها) و منوی موبایل تمام‌عرض.
- ARIA: `aria-expanded/haspopup` روی خوشه‌ها، `aria-label` روی nav و گروه‌ها، `aria-hidden` روی آیکون‌های تزئینی.
- ساختار معنایی: h1/h2، nav، thead/tbody؛ جدول‌ها با سرستون sticky.

## ۹. Token Reference سریع

```css
/* رنگ */ --bg --surface-1/2/3 --panel(--solid) --border(--strong)
         --text(--2/--3) --muted --brand(--strong/-soft/-contrast/-btn-bg)
         --radar(-soft) --up(--soft) --down(--soft) --warn(--soft/--strong)
         --info(--soft) --accent(--soft) --neutral-soft
/* تایپو */ --font --font-mono --fs-11…28 --lh-tight --lh-base
/* فضا */ --sp-1…10 /* شکل */ --r-sm/md/lg/xl/full --e-1/2/3
/* حرکت */ --t-fast/med/slow /* لایه */ --z-nav/topbar/dropdown/modal/toast
/* legacy aliases */ --surface1/2/3 --primary --radius (map به توکن‌های جدید)
```

## ۱۰. قواعد RTL و تم

- کل محصول `dir=rtl`؛ اعداد با `tabular-nums` بدون تغییر جهت؛ فقط بلوک‌های فنی (DSL، کد، قیمت) `direction:ltr`.
- تم روی `html[data-theme]` (پیش‌فرض light در مارکاپ برای حذف FOUC؛ `theme.js` ذخیره/بازیابی می‌کند)؛ هر دو تم از یک مجموعهٔ کامپوننت استفاده می‌کنند — هیچ کامپوننتی تم-محور دستی ندارد.
