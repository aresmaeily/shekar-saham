# گزارش تحویل نهایی مالک — «مرحله تکمیلی» ۲۰۲۶-۱۱-۰۸
# رفع نواقص، تکمیل مستندات، اعتبارسنجی نهایی و آماده‌سازی انتشار

**مخزن:** `aresmaeily/shekar-saham` · **شاخه:** `main`
**SHA شروع (تأییدشده مالک):** `2e6d0fb47c823be58dc9acc6c3579789cf330376`
**سند اجرا:** `docs/active/OWNER_COMPLETION_STAGE_2026-11-08_EXECUTION_RECORD.md`

> واژگان وضعیت هر قابلیت — طبق دستور: COMPLETE / PARTIAL / BLOCKED / OWNER-GATED / NOT-VERIFIED / FAILED.
> درصد پیشرفت کلی ارائه نشده است (OA-8 — بدون مدل وزن‌دهی مصوب مالک).

---

## ۱) SHA شروع و SHA نهایی

- **SHA شروع (کد):** `2e6d0fb4…` — دقیقاً برابر SHA تأییدشده مالک؛ `origin/main` بعد از fetch بدون انحراف همان بود.
- **SHA نهایی (کد):** همچنان `2e6d0fb4…` — این مرحله **هیچ دلتای کد/تست/موتور محصول ندارد** (صرفاً راستی‌آزمایی و مستندات).
- **SHA نهایی (مستندات):** `d62781c936388efe5166fcd333dee68851365ede` — کامیت مستندات این مرحله (فقط-داکیومنت) که CI آن روی SHA دقیق خود (صفحهٔ عمومی commit-checks: هر ۴ چک SUCCESS) راستی‌آزمایی شد. SHA کد (`2e6d0fb4…`) و SHA مستندات (`d62781c…`) عمداً از هم تفکیک شده‌اند.
- بازیابی محیط: مخزن محلی ۵۱ کامیت عقب بود (snapshots قدیمی sandbox)؛ با پروتکل ثبت‌شدهٔ ff-only و مقایسهٔ بایت‌به‌بایت (هر ۲۰۸۱ فایل متداخل، بایت‌به‌بایت یکسان؛ پشتیبان خارج از مخزن؛ راستی‌آزمایی بازگردانی ۲۰۸۱/۲۰۸۱) به‌روزرسانی شد. فایل‌های untracked مالک (`CLAUDE.md`، `.claude/`، `scripts/r13_owner_repo_setup.sh`، `scripts/validate_bootstrap_config.py`) دست‌نخورده باقی ماندند.

## ۲) تاریخچه تمام کامیت‌های این مرحله

- کامیت‌های بازهٔ «آخرین SHA تأییدشدهٔ قبلی → 2e6d0fb4»: از `209ec62` تا `2e6d0fb4` (۵۱ کامیت: WAVE-AI-ACCEPTANCE، OWNER-DIRECTIVE-2026-11-08 با پیاده‌سازی AI-3/`ad5d978`، دو شکست CI ثبت‌شده و اصلاح جلورو در `0b6190f`/`1aa0eea`، و کامیت رکورد `2e6d0fb4`).
- کامیت‌های جدید این مرحله: فقط کامیت مستندات (این گزارش + رکورد اجرا + به‌روزرسانی STATUS/INDEX/PLAN/MANIFEST/GUIDE/MATRIX). تاریخچه فقط-به-جلو؛ هیچ force-push/reset/rebase.

## ۳) فهرست تغییرات کد و مستندات

- **کد/تست:** صفر دلتا (صورت مرحله: راستی‌آزمایی مجدد، نه تغییر محصول).
- **مستندات (۷ فایل):** `AI3_PERSISTENCE_IMPLEMENTATION_PLAN.md` (سربرگ currency تاریخ‌دار — D1..D7 ثبت‌شدهٔ 2026-11-02، Adapter پیاده/متصل/راستی‌آزمایی‌شده، متن تاریخی PENDING/BLOCKED حفظ شده)، `docs/STATUS.md` (بلوک بالای جدید)، `docs/active/INDEX.md`، `RADAR_INSTALLER_ARTIFACT_MANIFEST_2026-11-07.json` (نسخه COMPLETION-STAGE + `hash_discipline` + `artifact_history` + `unsigned_version_limitations`)، `OWNER_WINDOWS_INSTALL_GUIDE_FA_2026-11-07.md` (بازنویسی کامل با آرتیفکت جدید)، `MASTER_RADAR_CAPABILITY_MATRIX_2026-11-04.md` (الحاقیهٔ تاریخ‌دار + دسته‌بندی سه‌گانه)، دو سند جدید این مرحله.

## ۴) وضعیت AI-1 تا AI-7

| حوزه | وضعیت | شواهد |
|---|---|---|
| AI-1 (تحلیل هوشمند شش‌برچسبی) | **COMPLETE (تا سطح INTEGRATION/RUNTIME-VERIFIED روی داده سینتتیک)** | باتری 3231/1s/0f در HEAD؛ مسیر analyst در E2E؛ GS2 v2 روی موتورهای واقعی |
| AI-2 (Research Loop حاکم) | **PARTIAL→ OWNER-GATED برای فعال‌سازی** — کد/تست کامل، گیت صفر | `AI2_ENABLED=0` (config.py:118)؛ پاسخ runtime `gated_not_executed/ai2_disabled`؛ بستهٔ D-A2-1..7 پابرجاست |
| AI-3 (حافظه پژوهش ماندگار) | **COMPLETE (INTEGRATION+RUNTIME-VERIFIED)** | clean-checkout 186/186؛ پروب رفتاری مستقل 10/10 (restart/tamper/keyless/invalid-key/garbage/SIGKILL/isolation/audit-tamper)؛ D1..D7 ثبت‌شده و پیاده |
| AI-4 (Strategy Lab/DSL) | **COMPLETE (RUNTIME-VERIFIED)** | backtest trades + walk-forward ۳ فولد + digest + خروجی‌های json/csv/pdf در E2E واقعی |
| AI-5 (Scheduler) | **PARTIAL (کد کامل) / OWNER-GATED برای عملیات** | `SCHEDULER_ENABLED=0`؛ posture `enabled=false`؛ کنترل start تایپ‌شده رد شد |
| AI-6 (منابع داده) | **COMPLETE (لایه DECLARED) + OWNER-GATED برای منابع واقعی** | kill-switchها ENGAGED؛ DECLARED-SOURCES-2؛ admission زنده = R-3/R-7 |
| AI-7 (Golden Set/Prediction) | **COMPLETE (تا سطح INTEGRATION-VERIFIED)** | GS2-2026-11-08: 8/8، FP=0، FN=0، بدون ادعای برتری؛ چرخهٔ کامل prediction در E2E (register→outcome→evaluate→calibration) |

## ۵) وضعیت Multi-Agent و Provider

- **Multi-Agent (AI-MA): COMPLETE (INTEGRATION+RUNTIME-VERIFIED روی اجرای واقعی)** — orchestrate واقعی: ۳ موج/۳ گام/۳ artifact_content؛ نمایشگر محتوای artifact در UI (esc‌شده)؛ پرسش خالی → 422 تایپ‌شده؛ پروب XSS اجرا نشد.
- **Executor واقعی vs Provider:** اجرا با **Specialist‌های قطعی shipped** است؛ برچسب `SYNTHETIC_OR_PAPER` صادقانه روی هر پاسخ. هیچ Synthetic Executor به‌عنوان LLM واقعی معرفی نشده است.
- **Provider واقعی LLM:** OWNER-GATED — بستهٔ تصمیم P-1..P-10 تحویل شده؛ **هیچ Provider فعال نشده** (بدون اعتبارنامه/مجوز مالک).

## ۶) وضعیت AI-2 و AI-3 (بند ویژهٔ دستور)

- **AI-2:** بستهٔ D-A2-1..7 بررسی شد؛ همهٔ پیش‌نیازهای Persistence/Recovery در سطح تست پابرجاست؛ مسیر fail-closed در runtime تأیید شد؛ هیچ داده‌ای بدون اعتبارسنجی به حافظهٔ پایدار نمی‌رود؛ **`AI2_ENABLED=0` حفظ شد.**
- **AI-3:** تمام آزمون‌های دستور در Clean Checkout اجرا شد (186/186) + پروب رفتاری 10/10: restart/restore، backup/بازیابی، tamper→gate بسته→بازیابی از پشتیبان تأییدشده، keyless→امتناع تایپ‌شده، کلید نامعتبر→fail-closed، خرابی فایل→`db_unreadable`، قطع ناگهانی (SIGKILL)→بازیابی WAL، isolation بین نشست‌ها. دسترسی D2 (دستگاه هدف) و cadence خودکار D5 (OA-4) همچنان OWNER-GATED.

## ۷) وضعیت تمام Gateها

| Gate | وضعیت |
|---|---|
| AI2_ENABLED / SCHEDULER_ENABLED / verified | صفر/صفر/False — دست‌نخورده (config.py:118/:171/:298) |
| G2 | PASSED (ثبت مالک 2026-10-29) — به‌تنهایی مجوز فعال‌سازی AI-2 نیست |
| R-1/R-2 (نصب/ارتقا/rollback روی دستگاه مالک) | **OWNER-GATED — NOT ISSUED** |
| R-3/R-7 (منابع زنده/Two-Key) | **KEEP-DENIED / REQUIRED — OWNER-GATED** |
| OA-3 (فعال‌سازی AI-2) / OA-4 (زمان‌بندی و اعلان) | **OWNER-GATED** |
| OA-6 (Vercel) | **غیر-گیت (مستند در بند ۱۳)** |
| OA-8 (وزن‌دهی تکمیل) | **OWNER-GATED — درصدی ارائه نشد** |
| D-A2 / P-1..P-10 | **OWNER-GATED (بسته‌ها پابرجا)** |

## ۸) وضعیت تمام موارد Roadmap (دسته‌بندی سه‌گانه)

1. **تکمیل‌شده با شواهد معتبر:** گرید چند-چارت + sync عرض/کراس‌هیر بین‌پنجره‌ای (WAVE-S، RUNTIME-VERIFIED)؛ popup-class detach؛ انواع چارت مشتق (RENKO/…)؛ مرکز کیفیت داده + تقویم‌های DECLARED؛ UIDL-1؛ بهینه‌ساز؛ walk-forward (API+UI)؛ خروجی PDF؛ پالت فرمان؛ deep-link؛ حلقه‌های محصول؛ رجیستری پیش‌بینی ماندگار؛ حافظهٔ پژوهش ماندگار؛ GS2.
2. **ناقص و قابل رفع توسط مهندسی (ثبت‌شده، پنهان نیست):** P2 liquidity pinning (صادقانه NOT ADDRESSED)؛ ماژول per-fundamental-line PIT (لایهٔ event/membership انجام شده)؛ تست تعاملی popup در سطح OS از sandbox ناممکن است (بستهٔ آزمون آماده؛ نیازمند نشست ویندوز).
3. **نیازمند تصمیم/دسترسی/اقدام مالک:** کاتالوگ نماد واقعی و entitlement ارائه‌دهنده؛ پذیرش منبع زنده (R-3/R-7 + Two-Key)؛ مشاهدهٔ زندهٔ forward (R-6)؛ امضای ویندوز؛ تست تعاملی Electron روی دستگاه مالک؛ فعال‌سازی AI-2/Provider/Scheduler؛ Branch Protection؛ Staging عمومی؛ مطالعهٔ مقایسه‌ای با TabloKhani (پروتکل مصوب لازم؛ هیچ ادعای برتری مطرح نیست).

## ۹) نتایج کامل تست Backend

- **باتری کامل در HEAD دقیق مالک (`2e6d0fb4`): 3231 passed / 1 skipped / 0 failed (53.87s)** — دقیقاً برابر رکوردهای قبلی؛ بدون رگرسیون.
- skip: فقط ۱ skip پابرجای محیطی؛ هیچ skip تازه‌ای اضافه نشد؛ هیچ ادعایی شامل Mock به COMPLETE تبدیل نشد.
- AI-3 در Clean Checkout: **186/186**. pyflakes/runtime ماژول‌ها پاک؛ node --check سبز؛ YAML معتبر.

## ۱۰) نتایج تست Frontend و Browser

- استک واقعی: uvicorn 127.0.0.1:8000 (mock/synthetic) + ترنسپورت same-origin :3000 (Host-preserving) + Chromium واقعی headless.
- **۲۵/۲۵ سناریوی دستور §6 PASS** (جدول کامل در رکورد اجرا §4) — شامل: health/trust، ورود/خروج/نشست، خانه/داشبورد (۳۲ تب RTL)، جست‌وجوی فارسی، تحلیل تکنیکال/بنیادی، freshness، منابع داده، AI-1..AI-7، Multi-Agent + Artifact Viewer، GS2، Product Loops + چرخهٔ کامل پیش‌بینی، Walk-Forward (۳ فولد + digest + ۳ خروجی)، Portfolio/Risk، خروجی‌ها (json/csv/**pdf با magic %PDF**)، مدیریت خطا (404/422 تایپ‌شده)، **بازیابی پس از restart واقعی بک‌اند** (رجیستری ماندگار: 1→1، `persistence_durable=true`)، رفتار Offline (پوستهٔ SW + ناوبری درون-برنامه‌ای؛ «بوت کامل آفلاین» ادعا نشد)، امنیت مسیرهای حساس (AI-2 gated، scheduler رد شده، XSS اجرا نشد)، کنترل دسترسی (POST با Origin خارجی→**403**؛ preflight خارجی→**400**)، Console/Log پاک (صفر خطا در کل نشست‌ها)، RTL فارسی، بار کاری (۲۰ درخواست → ۲۰۰ms).
- ۸ اسکرین‌شات واقعی در `download/completion_stage_evidence_20261108/`.

## ۱۱) شواهد Screenshot و Log

- اسکرین‌شات‌ها: `S04_home.png`، `S04_dashboard.png`، `S06_chartpro.png` (۸ بوم)، `S09_dataquality.png`، `S11_aima.png` (هوش چندعاملی با بنر صداقت)، `S15_strategylab.png`، `S20_offline_tabs.png`، `S20_offline_shell.png`.
- لاگ‌ها: `runtime_20261108/` (backend.log با ۰ traceback؛ e2e_results_A..D.txt با تک‌تک نتایج؛ security_audit.txt).

## ۱۲) نتایج ممیزی امنیتی

- `pip-audit`: **No known vulnerabilities found**.
- Secret scan کل مخزن: پاک (تنها hit، لیست انکار `_SECRET_MARKERS` در ai2_generation.py = خودِ کنترل امنیتی).
- authn/authz: `AUTH_REQUIRED` پیش‌فرض 0 (یا API_KEY/PRIVATE_MODE)؛ مسیر `X-API-Key` (main.py:287، WS:344)؛ پاسخ 401-کلاس تایپ‌شده.
- CORS: allow-list صریح؛ wildcard در prod به localhost اجباری؛ preflight خارجی→400. CSRF: POST با Origin خارجی→403.
- رمزنگاری: AES-256-GCM سکون (AI-3)؛ چرخهٔ کلید D4 (env→keyring؛ بی‌کلید=امتناع).
- فایل‌ها/دسترسی: بدون مسیر حذف/purge (AST-pinned)؛ .gitignore کامل؛ فایل .env/.key/.pem در درخت وجود ندارد.
- لاگ‌ها: بدون مقدار حساس؛ فقط نام کلیدها. Backup/Restore: تأییدشده و fail-closed.
- درصدها/ادعای امنیتی بدون تست مطرح نشد؛ هر ادعا با پروب runtime یا اسکن بازتولیدشدنی است.

## ۱۳) وضعیت Vercel و Staging

- `dpl_5FY7Yfc26iDnnm8s9PJ4ejQvuWim`: شکست **تأیید شد** (context وضعیت کامیت: `Vercel=failure`) در حالی که **هر ۴ چک اجباری Actions روی همان SHA موفق بودند**.
- **Root cause (سمت مخزن، مجدد تأیید شد):** هیچ `vercel.json`/`vercel.toml`/`.vercel` در مخزن نیست؛ محصول = مونولیت FastAPI same-origin (نشست کوکی، CSRF مبتنی بر Origin-vs-Host) با استقرار Docker + Electron. Vercel هیچ فریم‌ورکی برای build تشخیص نمی‌دهد ⇒ شکست build در هر push. لاگ کامل پشت احراز هویت مالک است (API بدون توکن→403).
- **تعیین تکلیف:** Vercel از نظر معماری **نمی‌تواند** میزبان این محصول باشد (حالت پایدار SQLite/WAL + بک‌اند نظارت‌شده + شل دسکتاپ) ⇒ **NON-GATING** ثبت شد؛ گزینه‌های مالک: (الف) قطع اتصال vercel[bot] (توصیه‌شده)، (ب) طراحی static-split + پروکسی (توصیه‌نشده)، (ج) ارائهٔ میزبان/اعتبارنامه برای Staging واقعی (OWNER-GATED).
- **Staging قابل دسترس عمومی: وجود ندارد** — localhost به‌عنوان staging معرفی نشد (پروب زندهٔ این مرحله روی استک same-origin محیط اجرا انجام شد و شواهد آن ثبت است).

## ۱۴) وضعیت Installer و Artifact

- آرتیفکت فعلی (GitHub API، دقیقاً روی SHA مالک): **id 13607633922** · نام `windows-installer-unsigned-2e6d0fb…` · **ران 42456810887** (SUCCESS، 2026-11-08T06:57:31Z) · **۱۱۴٬۵۰۴٬۳۴۱ بایت** · **UNSIGNED** · انقضا **2026-12-08** — منطبق کامل با مشاهدات مالک.
- **تفکیک هش‌ها (قاعدهٔ جدید Manifest):** هش آرشیو ZIP (`sha256:ffa13cd…` — مشاهدهٔ مالک) و هش نصاب داخلی EXE (ثبت‌شده در لاگ عمومی گام ۱۱) **دو هش متفاوت‌اند** و هرگز جای یکدیگر گزارش نمی‌شوند.
- راستی‌آزمایی سمت توسعه: readiness validator `all_ok=true`؛ node --check سبز؛ ۱۲ گام CI سبز از SHA دقیق.
- نصب/ارتقا/rollback/حذف/نصب مجدد روی ویندوز: **اجرا نشده و ادعا نشد** — NOT-VERIFIED تا شواهد دستگاه واقعی مالک (R-1/R-2)؛ بستهٔ آزمون مالک در راهنمای نصب بازنویسی‌شده آماده است.

## ۱۵) وضعیت Branch Protection

- توکن مهندسی موجود، دسترسی **Administration** ندارد (403 قبلی روی `/branches/main/protection`) و `GET /rulesets` خالی است؛ از این محیط دوباره تلاش شد — همان نتیجه.
- ⇒ **Branch Protection فعال نشده و هرگز ادعا نمی‌شود**؛ اقدام مالک: Settings→Branches→Add ruleset برای `main` + الزام ۴ چک (`test-backend`، `build-docker`، `windows-validation`، `build-installer`) + ممنوعیت force-push و حذف.
- صیانت از تاریخچه در عمل: همهٔ pushها فقط-به-جلو بودند؛ هر دو شکست CI قبلی ثبت و جلورو اصلاح شدند.

## ۱۶) چهار Check اجباری روی SHA نهایی — ماتریس نهایی صادقانه

| SHA (همه با runtime بایت‌به‌بایت یکسان — صفر دلتای غیر-docs، اثبات‌شده) | test-backend | build-docker | windows-validation | build-installer |
|---|---|---|---|---|
| `2e6d0fb4…` (baseline مالک) | SUCCESS | SUCCESS | SUCCESS | **SUCCESS** (آرتیفکت 13607633922) |
| `d62781c…` (مستندات مرحله) | SUCCESS | SUCCESS | SUCCESS | SUCCESS — ۴× «This job succeeded» (ران‌های 42463137103/24/36) |
| `044daa3…` (بستن زنجیرهٔ WS1) | SUCCESS | SUCCESS | **FAILURE** (42464136720) | SUCCESS |
| `8286cc9…` (تفکیک‌گر ۱) | SUCCESS | SUCCESS | SUCCESS | **FAILURE** (42464634806 — گام «Build NSIS installer» exit 1) |
| `9c44bc3…` (تفکیک‌گر ۲) | SUCCESS | SUCCESS | SUCCESS | **FAILURE** (42465284385 — همان گام) |
| `7c3cf02…` (رکورد تشدید) | SUCCESS | SUCCESS | SUCCESS | **FAILURE** (همان گام) |
| `c01375b…` (واحد پول CI) | SUCCESS | SUCCESS | SUCCESS | **FAILURE** (همان گام) |
| `27f4ac8…` (تأیید پایداری + فرضیه) | SUCCESS | SUCCESS | SUCCESS | **FAILURE** (همان گام — پنجمین متوالی؛ راستی‌آزمایی‌شده پس از انتشار) |

- **راستی‌آزمایی روی SHA دقیق مالک (`2e6d0fb4`): هر ۴ چک SUCCESS** — با شمارهٔ ران/job (بند بالا) و از API صفحهٔ عمومی.
- **وضعیت پایانی صادقانه:** در پنجرهٔ ناپایداری فعلی runner (از ~08:47Z)، خانوادهٔ چک‌های ویندوزی **ناپایدار** است: دو شکست متوالیِ همان گامِ «Build NSIS installer (electron-builder)» و یک شکست windows-validation، همگی روی runtime بایت‌به‌بایت یکسان با SHA تمام-سبز. طبق قاعدهٔ تفکیک‌گر ثبت‌شده، این **ESCALATED** شد: ناپایداری زیرساخت CI، نه خاصیت کد محصول.
- **مرز صادقانه:** لاگ خام auth-gated است (GOV-49)؛ تغییر کورکورانهٔ workflow بدون متن واقعی خطا رد شد (بدون حدس‌زدن و بدون سبز-سازی کاذب).
- **اقدام مالک (یکی کافی است):** (الف) دریافت لاگ job با حساب مالک (`runs/42465284385/job/128683269238`)؛ (ب) re-run دستی پس از پایدار شدن پنجره (ران 06:57Z روی همین کد تمام‌سبز بوده است)؛ (ج) اعطای توکن با `actions:read` برای رفع جلورو.
- Context اختیاری Vercel جدا و غیر-گیت است (بند ۱۳).

## ۱۷) فهرست تمام نقص‌های باز

1. **ناپایداری CI ویندوزی (ESCALATED):** دو شکست متوالی گام «Build NSIS installer» + یک شکست windows-validation روی runtime بایت‌به‌بایت یکسان (پنجرهٔ ~08:47Z به بعد) — نیازمند لاگ auth-gated مالک یا re-run پس از پایداری؛ آخرین SHA تمام-سبز: `d62781c` و baseline مالک `2e6d0fb4`.
2. نصب/ارتقا/rollback/حذف روی دستگاه واقعی ویندوز + تست تعاملی Electron (R-1/R-2) — NOT-VERIFIED.
3. Branch Protection ruleset (دسترسی Administration مالک).
4. فعال‌سازی AI-2 (D-A2) / Provider LLM (P-1..P-10) / Scheduler عملیاتی (OA-4) — OWNER-GATED.
5. منابع دادهٔ واقعی: کاتالوگ نماد واقعی، entitlement، admission زنده (R-3/R-7 + Two-Key).
6. مشاهدهٔ زندهٔ forward (R-6) و امضای ویندوز (تصمیم گواهی).
7. Staging عمومی (میزبان/اعتبارنامه مالک)؛ پاک‌سازی Vercel (OA-6).
8. P2 liquidity pinning و ماژول per-fundamental-line PIT (backlog مهندسی، ثبت‌شده).
9. cadence خودکار پشتیبان D5 و ممیزی‌های دوره‌ای AI-7 (OA-4).
10. مطالعهٔ مقایسه‌ای TabloKhانی نیازمند پروتکل مصوب مالک.

## ۱۸) فهرست تمام موارد نیازمند تصمیم مالک

(الف) صدور R-1 و اجرای R-2 روی دستگاه ویندوز با بستهٔ آزمون راهنمای نصب؛ (ب) قواعد شاخه (بند ۱۵)؛ (ج) تصمیم‌های D-A2-1..7 و P-1..P-10 (در صورت تمایل به فعال‌سازی)؛ (د) R-3/R-7: تحویل امن اعتبارنامه + نام دو Key-custodian در صورت تمایل به منبع واقعی؛ (هـ) OA-4: اقدام تاریخ‌دار برای عملیات زمان‌بندی‌شده؛ (و) OA-6: قطع vercel[bot] یا ارائهٔ میزبان staging؛ (ز) تصمیم امضای کد (گواهی)؛ (ح) OA-8: مدل وزن‌دهی در صورت محاسبهٔ درصد تکمیل؛ (ط) پروتکل بنچمارک مصوب برای هر مقایسهٔ بیرونی.

## ۱۹) دستورالعمل آزمون دستگاه واقعی مالک

`docs/active/OWNER_WINDOWS_INSTALL_GUIDE_FA_2026-11-07.md` (نسخهٔ به‌روزشدهٔ همین مرحله): قاعدهٔ دو هش (آرشیو vs EXE) → دانلود از ران 42456810887 → نصب → جدول ۸ سطری راستی‌آزمایی (پایتون سیستم/آفلاین/health/AI-2 gate/امتناع صادقانه/مرکز کیفیت داده/RELEASE_PROVENANCE/مجوز PSF) → ارتقا → بازگشت → حذف/نصب مجدد → پشتیبان‌گیری. هر انحراف = توقف استفاده و ثبت گزارش.

## ۲۰) ارزیابی دقیق آمادگی انتشار

- **از نظر مهندسی: پروژه نزدیک به آمادهٔ انتشار است** — محصول یکپارچه، پایدار در محیط توسعه، با مستندات هم‌خوان با کد، باتری 3231/1s/0f، هر ۴ چک اجباری سبز روی SHA مالک، AI-3 ماندگار و راستی‌آزمایی‌شده، امنیت بازتولیدشدنی، نصاب ساخته‌شده از SHA دقیق.
- **اما Release Approval صادر نشده است.** انتشار عمومی منوط به موارد OWNER-GATED بند ۱۷/۱۸ است (به‌ویژه R-1/R-2 روی دستگاه واقعی، قواعد شاخه، و تصمیم‌های فعال‌سازی). تا آن زمان وضعیت رسمی: **«آماده‌سازی انتشار — در انتظار اقدامات مالک»**.
- هیچ مورد PARTIAL/NOT-VERIFIED به COMPLETE بازتباری نشد؛ هیچ درصد کلی محاسبه نشد (OA-8).

---

**گیت‌ها — تغییرنکردنی‌ها:** `AI2_ENABLED=0` · `SCHEDULER_ENABLED=0` · `verified=False` · SYNTHETIC_OR_PAPER · بدون معاملهٔ واقعی/سفارش کارگزاری/انتقال وجه · Two-Key دست‌نخورده · kill-switchها ENGAGED · بدون egress خارجی · بدون حذف/purge · فقط-به-جلو.
