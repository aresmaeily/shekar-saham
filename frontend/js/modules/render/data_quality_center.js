/**
 * render/data_quality_center.js — MASTER-RADAR WAVE-2 directive (2026-11-04): مرکز کیفیت داده
 *
 * افزودنی (additive-only): تب جدید «مرکز کیفیت داده» — گزارش پوشش و ممیزی
 * نمادها از موتور کیفیت داده جهان-نماد (GET /api/v10/dataquality/markets، /markets/{m}/coverage، /symbols/{id}/audit) +
 * راهنمای کلاس‌های اعتماد (legend در index.html). هیچ مسیر، رندر یا رفتار
 * موجودی تغییر نمی‌کند؛ بایند-on-demand با الگوی MutationObserver (مثل
 * strategy_lab/chart_pro).
 *
 * قرارداد صداقت:
 * - همه HTTP از core/api.js (api()) می‌گذرد — هیچ واکشی مستقیمی مجاز نیست.
 * - هیچ اجرای پویای کد مجاز نیست — فقط innerHTML از متن فرارکننده‌شده (esc).
 * - در وضعیت فعلی مخزن همه داده‌های این مرکز از کلاس SYNTHETIC است (فیکسچر
 *   seed شده)؛ کلاس هر ردیف فقط از برچسب سرور خوانده می‌شود و هیچ کلاسی —
 *   از جمله REAL_VERIFIED — اینجا ارتقا یا جعل نمی‌شود.
 * - برچسب اعتماد فقط از trust_envelope سرور خوانده می‌شود.
 */
import { api, toast } from "../../core/api.js";
import { esc, fmtNum } from "../../core/format.js";

const TRUST_STATE_LABELS = {
  synthetic: "SYNTHETIC — شبیه‌سازی‌شده",
  mock: "MOCK — داده آزمایشی",
  stale: "STALE — داده قدیمی",
  unavailable: "UNAVAILABLE — داده ناموجود",
  mixed: "MIXED — ترکیبی/تأییدنشده",
};

function trustText(trust) {
  const state = String(trust?.state || trust?.trust_level || "mixed").toLowerCase();
  return TRUST_STATE_LABELS[state] || `اعتماد: ${state}`;
}

let bound = false;
let loaded = false; // بارگذاری خودکار فقط در اولین باز شدن تب

function $(id) {
  return document.getElementById(id);
}

/** خطا صادقانه: api() جزئیات 422 ساختاریافته را رشته می‌کند؛ به‌جای
 * «[object Object]» صادقانه می‌گوییم جزئیات ساختاریافته قابل نمایش نبود. */
function errText(e) {
  const m = String(e && e.message ? e.message : e);
  return m === "[object Object]" ? "خطای ۴۲۲ سرور — جزئیات ساختاریافته از طریق مرز api() قابل نمایش نبود" : m;
}

function showOut(objOrText) {
  const out = $("dqOut");
  if (!out) return;
  out.textContent = typeof objOrText === "string" ? objOrText : JSON.stringify(objOrText, null, 2);
}


/** WAVE-E pre-publication fix: این دو helper در نسخه WAVE-2 «صدا زده می‌شدند ولی
 * تعریف نشده بودند» (مسیرهای بدون-بازار/بدون-ردیف/خطا هرگز اجرا نمی‌شدند و بلوک
 * بعدیِ dqLoadAll را هم می‌شکستند). معنای موردنظر، همان حداقلِ روشن است: */
function setEmptyRow(tbody, colCount, message) {
  if (!tbody) return;
  tbody.innerHTML = "";
  const tr = document.createElement("tr");
  tr.innerHTML = `<td colspan="${colCount}" class="muted">${esc(message)}</td>`;
  tbody.appendChild(tr);
}

/** اولین آرایه موجود از بین کلیدهای کاندید در پاسخ سرور (بدون حدس) */
function rowListOf(res, keys) {
  for (const k of keys || []) {
    const v = res ? res[k] : undefined;
    if (Array.isArray(v)) return v;
  }
  return [];
}

function trustFrom(payload) {
  const el = $("dqTrustBadge");
  if (el && payload && payload.trust_envelope) el.textContent = trustText(payload.trust_envelope.data_trust);
}

/** اولین مقدار موجود از بین کلیدهای کاندید (پاسخ سرور مرجع است، نه حدس ما) */
function pick(obj, keys) {
  for (const k of keys) {
    const v = obj ? obj[k] : undefined;
    if (v !== undefined && v !== null) return v;
  }
  return null;
}

/** سلول عددی/متنی امن برای جدول‌ها */
function cell(v, digits = 2) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isNaN(v) ? "—" : fmtNum(v, digits);
  return esc(String(v));
}

function busy(btn, isBusy, busyLabel) {
  if (!btn) return;
  if (isBusy) {
    btn.dataset.idleText = btn.textContent;
    btn.textContent = busyLabel;
    btn.disabled = true;
  } else {
    if (btn.dataset.idleText) btn.textContent = btn.dataset.idleText;
    btn.disabled = false;
  }
}

function market() {
  return String($("dqMarket")?.value || "").trim();
}

const FALLBACK_MARKETS = [
  // فقط در صورت در دسترس نبودن GET /markets استفاده می‌شود — همان کدهای
  // کانونیک فیکسچر یونیورس (استیبل)، نه حدس درباره داده واقعی.
  ["IRAN_TSE", "ایران — بورس تهران (فیکسچر)"],
  ["IRAN_IFB", "ایران — فرابورس (فیکسچر)"],
  ["FOREX", "فارکس (فیکسچر)"],
  ["US_INDEX", "شاخص‌های آمریکا (فیکسچر)"],
];

/** انتخابگر بازار از پاسخ GET /markets پر می‌شود (سرور مرجع است)؛
 * EXCLUDED_US_EQUITY هم به‌عنوان بازارِ علامت‌گذاری‌شده نمایش داده می‌شود —
 * گزارشِ «حذف» صادقانه است، پنهان نیست. */
async function dqLoadMarkets() {
  const sel = $("dqMarket");
  if (!sel) return;
  try {
    const res = await api("/api/v10/dataquality/markets");
    trustFrom(res);
    const rows = rowListOf(res, ["markets"]);
    sel.innerHTML = "";
    if (!rows.length) throw new Error("empty market list");
    rows.forEach((m) => {
      const code = String(pick(m, ["market"]) || "");
      if (!code) return;
      const opt = document.createElement("option");
      opt.value = code;
      const inUniverse = pick(m, ["in_default_universe"]);
      const symbols = pick(m, ["symbol_count"]);
      const flag = inUniverse === false ? " — خارج از یونیورس پیش‌فرض (حذف ثبت‌شده)" : "";
      opt.textContent = `${code} · ${symbols ?? "—"} نماد${flag}`;
      sel.appendChild(opt);
    });
  } catch (e) {
    // fallback صادقانه: کدهای کانونیک فیکسچر — خطا در خروجی ثبت می‌شود
    sel.innerHTML = "";
    FALLBACK_MARKETS.forEach(([code, label]) => {
      const opt = document.createElement("option");
      opt.value = code;
      opt.textContent = `${label} — fallback محلی`;
      sel.appendChild(opt);
    });
    showOut(`بارگذاری فهرست بازارها از سرور ناموفق بود؛ انتخابگر با کدهای کانونیک فیکسچر پر شد (fallback محلی):\n${errText(e)}`);
  }
}

/* ------------------------- گزارش پوشش (خلاصه بازار از CoverageReport) ------------------------- */

const COVERAGE_COLS = 12;

async function dqLoadCoverage() {
  const body = $("dqCoverageBody");
  if (!body) return;
  const mkt = market();
  if (!mkt) {
    setEmptyRow(body, COVERAGE_COLS, "اول بازار را از انتخابگر انتخاب کنید");
    return;
  }
  try {
    const res = await api(`/api/v10/dataquality/markets/${encodeURIComponent(mkt)}/coverage`);
    trustFrom(res);
    const report = res && typeof res.report === "object" && res.report ? res.report : {};
    body.innerHTML = "";
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td style="direction:ltr">${esc(String(report.market ?? mkt))}</td>` +
      `<td style="direction:ltr">${cell(report.symbol_count, 0)}</td>` +
      `<td style="direction:ltr">${cell(report.valid_history_count, 0)}</td>` +
      `<td style="direction:ltr">${esc(String(report.start_date ?? "—"))}</td>` +
      `<td style="direction:ltr">${esc(String(report.end_date ?? "—"))}</td>` +
      `<td style="direction:ltr">${cell(report.duplicate_bars, 0)}</td>` +
      `<td style="direction:ltr">${cell(report.invalid_bars, 0)}</td>` +
      `<td style="direction:ltr">${cell(report.stale_bars, 0)}</td>` +
      `<td style="direction:ltr">${cell(report.provider_conflicts, 0)}</td>` +
      `<td style="direction:ltr">${esc(String(report.corporate_action_coverage ?? "UNKNOWN"))}</td>` +
      `<td style="direction:ltr">${esc(String(report.pit_availability ?? "UNKNOWN"))}</td>` +
      `<td style="direction:ltr">${esc(String(report.trust_class ?? res.trust_class ?? "—"))}</td>`;
    body.appendChild(tr);
  } catch (e) {
    setEmptyRow(body, COVERAGE_COLS, "بارگذاری گزارش پوشش ناموفق بود — جزئیات در خروجی");
    showOut(`گزارش پوشش ناموفق بود:\n${errText(e)}`);
    toast("گزارش پوشش ناموفق بود", "error");
  }
}

/* ------------------------- ممیزی نمادها (ردیف‌های ممیزی مکانیکی) ------------------------- */

const AUDIT_COLS = 11;

async function dqLoadAudit() {
  const body = $("dqAuditBody");
  if (!body) return;
  const mkt = market();
  if (!mkt) {
    setEmptyRow(body, AUDIT_COLS, "اول بازار را از انتخابگر انتخاب کنید");
    return;
  }
  try {
    // WAVE-2 integration: ردیف‌های ممیزی از همان GET /markets/{m}/coverage
    // می‌آیند (res.symbols = SymbolCoverage هر نماد)؛ دکمه جزئیات هر ردیف
    // GET /symbols/{id}/audit را صدا می‌زند.
    const res = await api(`/api/v10/dataquality/markets/${encodeURIComponent(mkt)}/coverage`);
    trustFrom(res);
    const rows = rowListOf(res, ["symbols"]);
    body.innerHTML = "";
    if (!rows.length) {
      setEmptyRow(body, AUDIT_COLS, "پاسخ سرور ردیفی برای ممیزی نداشت — چیزی جعل نمی‌شود");
      return;
    }
    rows.forEach((r) => {
      const sid = String(pick(r, ["symbol_id", "symbol"]) || "—");
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td style="direction:ltr">${esc(sid)}</td>` +
        `<td style="direction:ltr">${cell(pick(r, ["bar_count"]), 0)}</td>` +
        `<td style="direction:ltr">${esc(String(pick(r, ["start_date"]) ?? "—"))}</td>` +
        `<td style="direction:ltr">${esc(String(pick(r, ["end_date"]) ?? "—"))}</td>` +
        `<td style="direction:ltr">${cell(pick(r, ["duplicate_bars"]), 0)}</td>` +
        `<td style="direction:ltr">${cell(pick(r, ["out_of_order_bars"]), 0)}</td>` +
        `<td style="direction:ltr">${cell(pick(r, ["invalid_bars"]), 0)}</td>` +
        `<td style="direction:ltr">${cell(pick(r, ["stale_bars"]), 0)}</td>` +
        `<td style="direction:ltr">${cell(Array.isArray(r.missing_intervals) ? r.missing_intervals.length : null, 0)}</td>` +
        `<td style="direction:ltr">${esc(String(pick(r, ["trust_class"]) ?? "—"))}</td>` +
        `<td><button class="btn tiny" data-dqdetail="${esc(sid)}">جزئیات</button></td>`;
      body.appendChild(tr);
    });
    body.querySelectorAll("button[data-dqdetail]").forEach((btn) => {
      btn.addEventListener("click", () => dqSymbolDetail(btn.getAttribute("data-dqdetail")));
    });
  } catch (e) {
    setEmptyRow(body, AUDIT_COLS, "بارگذاری ممیزی نمادها ناموفق بود — جزئیات در خروجی");
    showOut(`ممیزی نمادها ناموفق بود:\n${errText(e)}`);
    toast("ممیزی نمادها ناموفق بود", "error");
  }
}

/** جزئیات یک نماد — GET /symbols/{instrument_id}/audit (خروجی کامل در پنل خروجی) */
async function dqSymbolDetail(instrumentId) {
  try {
    const res = await api(`/api/v10/dataquality/symbols/${encodeURIComponent(instrumentId)}/audit`);
    trustFrom(typeof res === "string" ? null : res);
    showOut(res);
    toast(`جزئیات ${instrumentId} بارگذاری شد`, "success");
  } catch (e) {
    showOut(`جزئیات ${instrumentId} ناموفق بود:\n${errText(e)}`);
    toast("جزئیات نماد ناموفق بود", "error");
  }
}

let marketsLoaded = false; // فهرست بازارها فقط یک‌بار از سرور خوانده می‌شود

async function dqLoadAll() {
  const btn = $("dqRefresh");
  busy(btn, true, "در حال بارگذاری…");
  try {
    if (!marketsLoaded) {
      await dqLoadMarkets();
      marketsLoaded = true;
    }
    await dqLoadCoverage();
    await dqLoadAudit();
    if (!calendarsLoaded) await dqLoadCalendars();
  } finally {
    busy(btn, false);
  }
}


/* ------------------- WAVE-E: تقویم‌های اعلامی (DECLARED) -------------------
 * فقط-افزودنی: جدول تقویم‌های اعلامی + بررسی وضعیت اعلامی در لحظهٔ اعلانیِ
 * کاربر (سرور هرگز ساعت خودش را نمی‌خواند — as_of_utc الزامی است). کلاس
 * اعتماد DECLARED فقط از فیلد سرور خوانده می‌شود و هیچ ارتقایی نمی‌گیرد.
 */

let calendarsLoaded = false;

async function dqLoadCalendars() {
  try {
    const res = await api("/api/v10/dataquality/calendars");
    const body = $("dqCalendarBody");
    const sel = $("dqCalSelect");
    if (!body || !sel) return;
    body.innerHTML = "";
    sel.innerHTML = "";
    for (const cal of res.calendars || []) {
      const tr = document.createElement("tr");
      const wins = (cal.sessions || [])
        .map((s) => `${esc(s.weekdays.join("، "))} ${esc(s.start_local)}–${esc(s.end_local)}`)
        .join(" · ");
      const hols = (cal.declared_holiday_rules || [])
        .map((h) => `${esc(h.name)} (${esc(h.rule)})`)
        .join(" · ") || "— (بدون قانون روز-ثابت اعلامی)";
      tr.innerHTML =
        `<td style="direction:ltr">${esc(cal.calendar_id)}</td>` +
        `<td>${esc(cal.market)}</td>` +
        `<td style="direction:ltr">${esc(cal.timezone)}</td>` +
        `<td>${wins}</td>` +
        `<td>${hols}</td>` +
        `<td style="direction:ltr">${esc(cal.declared_version)}</td>` +
        `<td>${esc(cal.trust_class)}</td>`;
      body.appendChild(tr);
      const opt = document.createElement("option");
      opt.value = cal.calendar_id;
      opt.textContent = cal.calendar_id;
      sel.appendChild(opt);
    }
    if (!(res.calendars || []).length) {
      body.innerHTML = `<tr><td colspan="7" class="muted">سرور فهرست تقویم اعلامی نداشت — چیزی جعل نمی‌شود</td></tr>`;
    }
    calendarsLoaded = true;
  } catch (e) {
    const body = $("dqCalendarBody");
    if (body) body.innerHTML = `<tr><td colspan="7" class="muted">بارگذاری تقویم‌ها ناموفق بود — هیچ داده‌ای جعل نمی‌شود</td></tr>`;
  }
}

async function dqCheckSessionState() {
  const out = $("dqCalState");
  const calId = $("dqCalSelect")?.value;
  const asOf = String($("dqCalAsOf")?.value || "").trim();
  if (!out) return;
  if (!calId || !asOf) {
    out.textContent = "تقویم و لحظه (ISO-8601 با آفست صریح، مثل 2026-11-09T12:00:00Z) هر دو الزامی‌اند — بدون آنها درخواستی ارسال نمی‌شود.";
    return;
  }
  out.textContent = "در حال بررسی…";
  try {
    const st = await api(`/api/v10/dataquality/calendars/${encodeURIComponent(calId)}/session-state?as_of_utc=${encodeURIComponent(asOf)}`);
    const det = String(st.detail || "");
    out.innerHTML =
      `<b style="direction:ltr">${esc(st.state)}</b> — ` +
      `${esc(det)} · کلاس: ${esc(st.trust_class)} · نسخه: ${esc(st.declared_version)}` +
      `<br><span class="muted">محدودیت اعلامی: ${esc(st.honesty?.declared_scope_gaps || "")}</span>`;
  } catch (e) {
    out.textContent = `بررسی ناموفق بود (ورودی را با آفست صریح بررسی کنید، مثل 2026-11-09T12:00:00Z): ${errTextSafe(e)}`;
  }
}

function errTextSafe(e) {
  return String(e?.message || e).slice(0, 160);
}

/* ------------------------- بایند-on-demand ------------------------- */

function bindDataQualityCenter() {
  if (bound || !$("dqRefresh")) return;
  bound = true;

  const on = (id, fn) => {
    const el = $(id);
    if (el) el.addEventListener("click", fn);
  };
  on("dqRefresh", dqLoadAll);
  $("dqMarket")?.addEventListener("change", dqLoadAll);
  // WAVE-E: تقویم‌های اعلامی — بررسی وضعیت فقط با کنش صریح کاربر
  on("dqCalCheck", dqCheckSessionState);

  // فعال‌سازی هنگام باز شدن تب (الگوی strategy_lab): بارگذاری فقط-یک‌بار
  // گزارش‌های فقط-خواندنی؛ هیچ درخواستی پیش از باز شدن تب ارسال نمی‌شود.
  const observer = new MutationObserver(() => {
    const panel = $("tab-dataquality");
    if (panel && panel.classList.contains("active") && !loaded) {
      loaded = true;
      dqLoadAll();
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
  document.querySelectorAll('[data-tab="dataquality"]').forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!loaded) setTimeout(dqLoadAll, 100);
    });
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindDataQualityCenter);
  else bindDataQualityCenter();
}
