/**
 * render/forward_center.js — MASTER-RADAR WAVE-2 directive (2026-11-04): مرکز فوروارد تست
 *
 * افزودنی (additive-only): تب جدید «مرکز فوروارد تست» — بازپخش کاغذی (paper
 * replay) روی داده سینتتیک seed شده با دفتر رخدادها (ledger)، دلتاهای
 * انتظار/واقعیت (expected-vs-realized) و جدول مقایسه با بک‌تست. هیچ مسیر،
 * رندر یا رفتار موجودی تغییر نمی‌کند؛ بایند-on-demand با الگوی
 * MutationObserver (مثل strategy_lab/chart_pro).
 *
 * قرارداد صداقت:
 * - همه HTTP از core/api.js (api()) می‌گذرد — هیچ واکشی مستقیمی مجاز نیست.
 * - هیچ اجرای پویای کد مجاز نیست — فقط innerHTML از متن فرارکننده‌شده (esc).
 * - این مرکز فقط «بازپخش کاغذی» است — نه معامله زنده، نه اتصال بروکر، نه
 *   زمان‌بند؛ یادداشت رسمی سرور (not_live_note) بدون تغییر نشان داده می‌شود.
 * - برچسب اعتماد فقط از trust_envelope سرور خوانده می‌شود؛ هیچ برچسبی — از
 *   جمله «زنده» — اینجا جعل نمی‌شود.
 * - سلامت زنجیره دفتر (ledger_chain_ok) عیناً و بدون رنگ‌آمیزی گزارش می‌شود.
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
let activated = false;

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
  const out = $("fcOut");
  if (!out) return;
  out.textContent = typeof objOrText === "string" ? objOrText : JSON.stringify(objOrText, null, 2);
}

function trustFrom(payload) {
  const el = $("fcTrustBadge");
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

/* ------------------------- اجرای بازپخش کاغذی ------------------------- */

function runParams() {
  return {
    symbol: ($("fcSymbol")?.value || "FOLAD").trim().slice(0, 32),
    timeframe: $("fcTimeframe")?.value || "1D",
    count: Math.max(50, Math.min(1000, parseInt($("fcCount")?.value || "200", 10) || 200)),
    name: (($("fcName")?.value || "dsl.strategy").trim() || "dsl.strategy").slice(0, 64),
  };
}

async function fcRun() {
  const btn = $("fcRun");
  const source = ($("fcDslSource")?.value || "").trim();
  if (!source) {
    toast("منبع DSL خالی است — استراتژی را وارد کنید", "error");
    showOut("منبع DSL خالی است — هیچ درخواستی ارسال نشد.");
    return;
  }
  busy(btn, true, "در حال بازپخش…");
  showOut("در حال اجرای بازپخش کاغذی روی داده سینتتیک سرور…");
  try {
    const res = await api("/api/v10/strategylab/paper-replay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, ...runParams() }),
    });
    trustFrom(res);
    renderPaper(res);
    showOut(res);
    toast("بازپخش کاغذی کامل شد (نه زنده)", "success");
  } catch (e) {
    showOut(`بازپخش کاغذی ناموفق بود:\n${errText(e)}`);
    toast("بازپخش ناموفق — جزئیات در خروجی", "error");
  } finally {
    busy(btn, false);
  }
}

function summaryOf(res) {
  const s = res && typeof res.summary === "object" && res.summary ? res.summary : {};
  return { ...res, ...s, expected_vs_realized: s.expected_vs_realized || res.expected_vs_realized || null };
}

const SUMMARY_ROWS = [
  ["کندل‌های پردازش‌شده", (s) => s.bars_processed, 0],
  ["کل سیگنال‌ها", (s) => s.signals_total, 0],
  ["سیگنال‌های پرشده", (s) => s.signals_filled, 0],
  ["بالغ‌شده", (s) => s.matured_count, 0],
  ["نابالغ (خارج از همه تجمیع‌ها)", (s) => s.immature_count, 0],
  ["نتیجه کهنه", (s) => s.stale_outcomes, 0],
  ["بازده محقق‌شده ٪", (s) => s.realized_return_pct],
  ["نرخ برد (بالغ‌شده) ٪", (s) => s.win_rate_matured],
  ["بیشینه افت سرمایه ٪", (s) => s.max_drawdown_pct],
  ["کارمزد کل", (s) => s.fees_total],
  ["شکاف داده", (s) => s.data_gaps, 0],
  ["میانگین تأخیر (کندل)", (s) => s.total_delay_bars_mean],
];

function renderPaper(res) {
  const s = summaryOf(res);
  renderSummary(s);
  renderDeltas(s.expected_vs_realized);
  renderLedger(res);
  renderComparison(res.comparison || res.vs_backtest || null);
  const noteEl = $("fcNotLiveNote");
  if (noteEl) noteEl.textContent = res.not_live_note || "یادداشت not_live_note در پاسخ سرور نبود.";
}

function renderSummary(s) {
  const body = $("fcSummaryBody");
  if (!body) return;
  body.innerHTML = "";
  SUMMARY_ROWS.forEach(([label, get, digits]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${esc(label)}</td><td style="direction:ltr">${cell(get(s), digits === undefined ? 2 : digits)}</td>`;
    body.appendChild(tr);
  });
  // صداقت دفتر: طول و سلامت زنجیره عیناً از پاسخ سرور
  const lenRow = document.createElement("tr");
  lenRow.innerHTML =
    `<td>طول دفتر رخدادها</td><td style="direction:ltr">${cell(pick(s, ["ledger_len", "ledger_length"]), 0)}</td>`;
  body.appendChild(lenRow);
  const chainRow = document.createElement("tr");
  const chainOk = pick(s, ["ledger_chain_ok"]);
  chainRow.innerHTML =
    `<td>سلامت زنجیره دفتر</td><td>${chainOk === null ? "— (در پاسخ نبود)" : chainOk ? "سالم" : "شکسته — عیناً همان‌طور که سرور گزارش کرد"}</td>`;
  body.appendChild(chainRow);
}

function renderDeltas(evr) {
  const body = $("fcDeltasBody");
  if (!body) return;
  body.innerHTML = "";
  const rows = [
    ["میانگین قدرمطلق دلتای قیمت ٪", evr ? evr.mean_abs_delta_pct : null],
    ["بیشینه قدرمطلق دلتای قیمت ٪", evr ? evr.max_abs_delta_pct : null],
    ["تعداد مشاهده‌ها", evr ? evr.observations : null],
  ];
  rows.forEach(([label, v]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${esc(label)}</td><td style="direction:ltr">${cell(v, typeof v === "number" && Number.isInteger(v) ? 0 : 2)}</td>`;
    body.appendChild(tr);
  });
  if (!evr) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="2" class="muted">بخش انتظار/واقعیت در پاسخ سرور نبود — عددی جعل نمی‌شود</td>`;
    body.appendChild(tr);
  }
}

function renderLedger(res) {
  const body = $("fcLedgerBody");
  if (!body) return;
  body.innerHTML = "";
  const events = Array.isArray(res.ledger_events)
    ? res.ledger_events
    : Array.isArray(res.ledger)
      ? res.ledger
      : Array.isArray(res.events)
        ? res.events
        : [];
  if (!events.length) {
    body.innerHTML = `<tr><td colspan="6" class="muted">پاسخ سرور فهرست رخدادهای دفتر نداشت (فقط طول/سلامت گزارش شده است) — چیزی جعل نمی‌شود</td></tr>`;
    return;
  }
  events.forEach((ev) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td style="direction:ltr">${cell(pick(ev, ["ts", "bar_index", "index", "time", "ts_utc"]), 0)}</td>` +
      `<td>${esc(String(pick(ev, ["action", "kind", "event", "type"]) ?? "—"))}</td>` +
      `<td>${esc(String(pick(ev, ["symbol", "sym"]) || "—"))}</td>` +
      `<td style="direction:ltr">${cell(pick(ev, ["price", "fill_price", "entry_price", "exit_price"]))}</td>` +
      `<td style="direction:ltr">${cell(pick(ev, ["qty", "quantity", "size"]))}</td>` +
      `<td>${esc(String(pick(ev, ["reason", "note", "detail", "status"]) ?? "—"))}</td>`;
    body.appendChild(tr);
  });
}

function renderComparison(comp) {
  const mount = $("fcCompareMount");
  if (!mount) return;
  if (!comp) {
    mount.textContent = "پاسخ سرور بخش مقایسه با بک‌تست نداشت — چیزی جعل نمی‌شود.";
    return;
  }
  let rows = [];
  if (Array.isArray(comp)) rows = comp;
  else if (typeof comp === "object" && Array.isArray(comp.rows)) rows = comp.rows;
  else if (typeof comp === "object") {
    rows = Object.entries(comp).map(([metric, v]) =>
      typeof v === "object" && v ? { metric, ...v } : { metric, value: v }
    );
  }
  const table = document.createElement("table");
  table.className = "data-table";
  table.innerHTML =
    `<thead><tr><th>سنجه</th><th>بک‌تست</th><th>کاغذی</th><th>اختلاف</th></tr></thead>`;
  const tbody = document.createElement("tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="muted">مقایسه خالی بود — چیزی جعل نمی‌شود</td></tr>`;
  } else {
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${esc(String(pick(r, ["metric", "label", "name"]) ?? "—"))}</td>` +
        `<td style="direction:ltr">${cell(pick(r, ["backtest", "backtest_value", "is", "is_value"]))}</td>` +
        `<td style="direction:ltr">${cell(pick(r, ["paper", "paper_value", "forward", "value"]))}</td>` +
        `<td style="direction:ltr">${cell(pick(r, ["delta", "diff", "difference"]))}</td>`;
      tbody.appendChild(tr);
    });
  }
  table.appendChild(tbody);
  mount.innerHTML = "";
  mount.appendChild(table);
}

/* ------------------------- بایند-on-demand ------------------------- */

function bindForwardCenter() {
  if (bound || !$("fcRun")) return;
  bound = true;

  const on = (id, fn) => {
    const el = $(id);
    if (el) el.addEventListener("click", fn);
  };
  on("fcRun", fcRun);

  // فعال‌سازی هنگام باز شدن تب (الگوی strategy_lab) — بدون هیچ درخواست خودکار:
  // بازپخش کاغذی فقط با کنش صریح کاربر اجرا می‌شود.
  const observer = new MutationObserver(() => {
    const panel = $("tab-forwardcenter");
    if (panel && panel.classList.contains("active") && !activated) {
      activated = true;
      const out = $("fcOut");
      if (out) {
        out.textContent =
          "آماده — منبع DSL (RSL-1) را وارد و «اجرای بازپخش کاغذی» را بزنید. این مرکز فقط بازپخش کاغذی روی داده سینتتیک است؛ نه معامله زنده، نه بروکر، نه زمان‌بند.";
      }
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindForwardCenter);
  else bindForwardCenter();
}
