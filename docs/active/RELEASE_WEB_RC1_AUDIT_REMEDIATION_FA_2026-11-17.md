# گزارش نهایی حسابرسی و اصلاح RC1 — شاخه release/web-rc1 (۲۰۲۶-۱۱-۱۷)

این گزارش، پاسخ نهایی به directive «RADAR BOURSE — FINAL RC1 AUDIT REMEDIATION» است.
تمام اقدامات forward-only بوده‌اند: بدون rewrite تاریخچهٔ مشترک، بدون force-push، بدون merge به main، بدون استقرار production و بدون انتشار عمومی.

## ۰) متادیتای دقیق

| عنوان | مقدار |
| --- | --- |
| مخزن | `aresmaeily/shekar-saham` |
| شاخهٔ RC | `release/web-rc1` |
| SHA پایه (origin/main) | `7a41563968dc5ac5d57f5f3d7ac3a674e735ee58` |
| SHA ممیزی‌شدهٔ کاندید | `3aa27430a956b52f67d811f0ab35b0f362979c82` |
| SHA نهایی این اصلاح | کامیت حاوی همین فایل («این کامیت»)؛ مقدار دقیق در تاریخچهٔ کامیت، read-back پس از push و بستهٔ شواهد ثبت می‌شود |
| محیط بازتولید تست | Python 3.13.5 (GCC 14.2.0)، لینوکس، وابستگی‌های پین‌شدهٔ `backend/requirements.txt` |

## ۱) قرارداد PIT سطح-خط — تصمیم، مستندسازی و پیاده‌سازی

**تصمیم قرارداد پیش از تغییر پیاده‌سازی** در سند `docs/active/RC1_LINE_PIT_CONTRACT_RECORD_2026-11-17.md` ثبت شد. خلاصهٔ پنج بند قرارداد (`resolve_line_at_cutoff`):

* **C1 انتخاب دوره**: با `reporting_period` صریح، pool دقیقاً همان دوره است — تطابق exact-key؛ کلید ناشناخته/ناقص → `NO_FACT` با ذکر کلید درخواستی در متادیتا (fail-closed، هرگز حدس فازی).
* **C2 فروپاشی**: بدون انتخاب صریح، نتیجه به **آخرین دورهٔ گزارشگری** فرو می‌ریزد (period_end، تای‌بریک با جدیدترین availability سپس fact_id).
* **C3 دامنهٔ تعارض**: تشخیص تعارض فقط در دورهٔ انتخاب‌شده اعمال می‌شود؛ تعارض یک دورهٔ قدیمی‌تر هرگز نتیجهٔ معتبر دورهٔ جدیدتر را نمی‌پوشاند. هیچ‌چیز بی‌صدا حل نمی‌شود: تعارض دوره‌های غیرانتخاب‌شده همچنان از طریق `resolve_statement_at_cutoff` (که هر جفت `(metric, reporting_period)` را مستقل حل می‌کند) سطح‌بندی می‌شود و `period_keys` همیشه دوره‌های حاضر را نشان می‌دهد.
* **C4 متادیتا**: `LineResolution.reporting_period` اکنون در **همهٔ مسیرهای بازگشت** پر می‌شود (کلید درخواستی در انتخاب صریح حتی برای NO_FACT؛ کلید انتخاب‌شده در فروپاشی؛ `None` تنها وقتی دوره‌ای قابل انتخاب نبود).
* **C5 زنجیره و معناشناسی تغییریافته‌نکردنی**: `superseded_chain` به دورهٔ انتخاب‌شده محدود است؛ قواعد cutoff انتشار/بازیابی، تقدم restatement-version و صداقت `NOT_AVAILABLE` عیناً بدون تغییر مانده‌اند و API سطح-statement بایت-به-بایت دست‌نخورده است.

دو نقص ممیزی پیش از اصلاح: (۱) بررسی تعارض روی همهٔ دوره‌ها پیش از انتخاب برنده — نقض docstring خود تابع؛ (۲) متادیتای `reporting_period` در فراخوانی مستقیم پر نمی‌شد. هر دو رفع شدند.

**تست‌های الزامی، همگی جدید و بدون دست‌کاری هیچ تست موجود** (`backend/tests/test_fundamental_line_pit.py`، ۲۰ → ۲۵ تست):

1. `test_line_collapse_older_period_conflict_does_not_mask_latest_period` — تعارض دورهٔ قدیمی + دورهٔ جدید معتبر → RESOLVED دورهٔ جدید؛ تعارض قدیمی از طریق statement-API همچنان سطح‌بندی می‌شود.
2. `test_line_conflict_in_selected_period_surfaced_with_metadata` — تعارض در دورهٔ انتخاب‌شده → CONFLICTING_SOURCES با متادیتای نام دوره (انتخاب صریح و فروپاشی).
3. `test_line_explicit_period_metadata_populated_in_every_state` — متادیتای دورهٔ انتخاب‌شده در حالت‌های RESOLVED و NOT_AVAILABLE.
4. `test_line_missing_or_ambiguous_period_fails_closed_named` — کلید ناشناخته و کلید ناقص/غم‌آلود → NO_FACT با نام کلید درخواستی؛ بدون fallback فازی.
5. پوشش زنجیره: `test_line_collapse_names_selected_period_and_scopes_chain` — نام دورهٔ انتخاب‌شده + محدود بودن زنجیره به همان دوره.

تست‌های موجود سطح-statement (چنددوره‌ای، restatement، ایزوله‌سازی تعارض، cutoff) بدون هیچ تغییری و سبز باقی ماندند: فایل PIT کامل = **۲۵/۲۵ PASS**.

## ۲) هم‌نمیِ نتیجهٔ تست در SHA دقیق (بخش ۲ directive)

اندازه‌گیری‌های واقعی در محیط Python 3.13.5 لینوکس (همسان CI) روی درخت ممیزی‌شدهٔ `3aa2743`:

| اجرا | نتیجه | توضیح |
| --- | --- | --- |
| محلی، `pytest tests/ -q -rs` | **3315 passed / 1 skipped / 0 failed** (41.23s) | skip: `tests/test_g2_acceptance_harness.py::TestImplementationBinding::test_substantive_changes_since_rejected` — خط ۲۹۴، دلیل: «parent..HEAD delta is docs-only; use a synthetic case» (HEAD ممیزی‌شده docs-only است) |
| شبیه‌سازی دقیق CI (همان محیط با پنهان‌سازی pdftotext — تنها تفاوت شرطی با runner) | **3314 passed / 2 skipped / 0 failed**، ۲ warning (41.10s) | مطابق **دقیق** با نتیجهٔ CI در run `43816058690` |
| CI واقعی (run `43816058690`، job `133128255235`، `python -m pytest tests/ -q`) | 3314 passed / 2 skipped / 2 warnings | طبق شواهد ممیز مستقل |

دو skip و شناسه‌های دقیق:

1. **هر دو محیط**: `tests/test_g2_acceptance_harness.py::TestImplementationBinding::test_substantive_changes_since_rejected` — skip شرطیِ وضعیت-repo (HEAD docs-only نسبت به والد)؛ یکسان در محلی و CI.
2. **فقط CI**: `tests/test_report_pdf.py::test_pdf_third_party_parser_roundtrip` — `@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="poppler pdftotext not available in this environment")`؛ runner استاندارد ubuntu-latest فاقد poppler-utils است، محلی موجود بود.

**هم‌نمیِ حسابی**: هر دو اجرا روی همان مجموعهٔ ۳۳۱۶تایی می‌شمارند؛ اختلاف دقیقاً یک تست است که در CI skip و در محلی (با pdftotext) pass می‌شود. شبیه‌سازی CI با پنهان‌سازی همان یک ابزار، توزیع CI را **بایت-به-بایت** بازتولید کرد (3314/2s/2w). شناسه‌گذاری شرطی‌های کل مجموعه: node (روی runner و محلی هر دو موجود — بدون واگرایی)، keyring (در هر دو غایب)، GOV-19 bundle (در هر دو غایب)، شرطی‌های وضعیت-repo G2 (برای SHA یکسان، رفتار یکسان) — تنها pdftotext با CI سازگار است.

**هیچ تستی حذف، تضعیف، deselect یا شرطی-دور زده نشد**؛ skipif یادشده کدِ از-پیش-کامیت‌شدهٔ مخزن است و صرفاً رفتار شرطیِ محیطیِ صادقانه را نشان می‌دهد. نسخه‌ها: Python 3.13.5؛ وابستگی‌ها عیناً پین‌شدهٔ requirements (fastapi 0.141.1، pydantic 2.13.4، numpy 2.2.1، cryptography 50.0.0، pytest 9.x، …) — فهرست کامل `pip freeze` در بستهٔ شواهد.

## ۳) شواهد CI در SHA دقیق ممیزی‌شده (حفظ بدون جایگزینی)

هر سه اجرای ثبت‌شده روی `3aa2743` (push، شاخهٔ release/web-rc1، 2026-11-16 06:20 UTC) — راستی‌آزمایی‌شده از صفحات عمومی run:

| بررسی الزامی | Run ID | Workflow | وضعیت | مدت |
| --- | --- | --- | --- | --- |
| test-backend + build-docker | `43816058690` | ci.yml | **SUCCESS** (هر دو job) | 1m48s |
| windows-validation | `43816058680` | windows.yml | **SUCCESS** | 4m06s |
| build-installer | `43816058717` | windows-installer.yml | **SUCCESS** | 2m21s |

* **طبقه‌بندی discriminator**: windows-validation روی کامیت docs-only `3aa2743` (runtime بایت-به-بایت یکسان با `78ad314`) **PASS** شد ⇒ طبق دیسیپلین ثبت‌شدهٔ 5c04719، شکست step-10 در `78ad314` (پنجمین رخداد کلاس فقط-ویندوز) **تکرار محیطیِ کلاس flake ثبت‌شده** است، نه رگرسیون؛ هیچ چیزی به pass تبدیل نشد و شکست روی ثبت می‌ماند.
* **Artifact نصاب**: `windows-installer-unsigned-3aa27430a956b52f67d811f0ab35b0f362979c82` (~109MB، نگه‌داری ۳۰ روزه) — **UNSIGNED** (بدون گواهی امضا؛ CSC auto-discovery غیرفعال). دانلود artifact و لاگ job از این محیط مهندسی قابل استخراج نیست (404/auth-gated، سازگار با ثبت GOV-49)؛ SHA-256 دقیق artifact در `installer_provenance.txt` داخل zip و در لاگ عمومی build ثبت شده است و برای ممیزِ دارندهٔ دسترسی admin قابل استخراج است.
* **Vercel**: جدا و NON-GATING طبق OA-6؛ در هیچ گرمی از چهار بررسی الزامی ادغام نشده است.
* هشدار deprecation «Node.js 20 … forced to run on Node.js 24» به‌عنوان کار نگهداشت ثبت شد؛ **هیچ ارتقای workflow نامرتبطی** به این اصلاح مخلوط نشد (صفر تغییر در `.github/`).

## ۴) PR و محافظت شاخه (بخش ۵ directive)

* **هیچ token مجاز GitHub API در محیط مهندسی موجود نیست** (نتیجهٔ این session؛ مطابق ثبت جلسات پیشین). بنابراین طبق خود directive: **PR ساخته نشد و هیچ URL PR جعل نشد**.
* URL مقایسهٔ رسمی برای بازبینی مالک: `https://github.com/aresmaeily/shekar-saham/compare/main...release/web-rc1`
* وضعیت PR هنگام نگارش: هیچ PR بازی برای release/web-rc1 وجود ندارد.
* **محافظت شاخه فقط با session مجاز مالک قابل راستی‌آزمایی است** (نرخ سهمیهٔ API ناشناس در این محیط نیز مصرف شده است)؛ بدون تأیید مالک هیچ تنظیم امنیتی تغییر نکرده است.

## ۵) بستهٔ شواهد (بخش ۳ directive)

بستهٔ کامل شواهد به‌صورت آرشیو قابل‌دسترس تحویل مالک می‌شود (مسیر و مانیفست SHA-256 در پاسخ نهایی ثبت می‌شود) و شامل: این گزارش، آرشیو سورس SHA دقیق، مانیفست SHA-256 با لاگ تأیید واقعی (هر entry در برابر بایت‌های واقعی فایل راستی‌آزمایی شده)، لاگ‌های اجرای کامل تست و collect در هر دو SHA، متادیتای سه run CI با job-نتایج، اسکرین‌شات‌های E2E مرورگر + لاگ console/page-error، شواهد Docker CI، provenance نصاب با برچسب صریح UNSIGNED، و راهنمای نصب/عملیات فارسی. **تفکیک صریح شواهد**: artifactهای CI روی GitHub / شواهد فقط-محلی / فایل‌های کامیت‌شده در Git / فایل‌های نامتاح برای ممیز مستقل (لاگ job و artifact zip) — در فایل `PROVENANCE_CLASSIFICATION` بسته.

## ۶) مرزهای حکمرانی — بدون تغییر

`AI2_ENABLED=0` · `SCHEDULER_ENABLED=0` · `verified=False ⇒ SYNTHETIC_OR_PAPER` · بدون معامله‌گری خودکار یا سفارش بروکر · بدون ارتقای خودکار filter · بدون mutation تولیدی بدون تأیید انسانی · بدون ارتقای برچسب اعتماد · بدون وابستگی Vercel · **بدون merge به main** · **بدون استقرار تولیدی/انتشار عمومی** · نصاب ویندوز UNSIGNED تا ارائهٔ گواهی معتبر.

## ۷) محدودیت‌های باقی‌مانده و اقدامات فقط-مالک

1. ایجاد PR و بررسی branch protection نیازمند token/session مجاز مالک است.
2. نصاب UNSIGNED تا ارائهٔ گواهی امضا (R-1/R-2)؛ نصب روی ماشین هدف فقط با مالک.
3. استخراج SHA-256 دقیق artifact و لاگ کامل job CI نیازمند دسترسی admin است (ثبت GOV-49).
4. هشدار Node.js 20→24 در runnerها: کار نگهداشت آینده، خارج از دامنهٔ این اصلاح.
5. Vercel: جدا و غیرگِیت؛ housekeeping اختیاری مالک.

## verdict

با توجه به رفع کامل یافته‌های ممیزی، بازتولید دقیق و هم‌نمیشدهٔ نتایج تست، شواهد CI سه‌گانه در SHA دقیق، و بستهٔ شواهد راستی‌آزمایی‌شده — با افشای صریح محدودیت‌های بالا:

**RELEASE CANDIDATE READY WITH DISCLOSED LIMITATIONS**
