/**
 * render/backtest_center.js — MASTER-RADAR WAVE-2 directive (2026-11-04): مرکز بک‌تست
 *
 * افزودنی (additive-only): تب جدید «مرکز بک‌تست» — اجرای بک‌تست محصول روی داده
 * سینتتیک seed شده (متریکس، منحنی سرمایه، معاملات، رژیم‌ها)، خروجی CSV/JSON و
 * بهینه‌ساز (grid/randomized/evolutionary) با انتخاب درون‌نمونه‌ای (IS) و تأیید
 * OOS فقط پس از ثابت‌شدن برنده. هیچ مسیر، رندر یا رفتار موجودی تغییر نمی‌کند؛
 * بایند-on-demand با الگوی MutationObserver (مثل strategy_lab/chart_pro).
 *
 * قرارداد صداقت:
 * - همه HTTP از core/api.js (api()) می‌گذرد — هیچ واکشی مستقیمی مجاز نیست.
 * - هیچ اجرای پویای کد مجاز نیست — فقط innerHTML از متن فرارکننده‌شده (esc).
 * - برچسب اعتماد فقط از trust_envelope سرور خوانده می‌شود؛ هیچ برچسبی — از
 *   جمله «زنده» — اینجا جعل نمی‌شود.
 * - بک‌تست و بهینه‌ساز فقط روی داده سینتتیک سرور (SYNTHETIC) است و پاسخ سرور
 *   خودش این را با synthetic_note اعلام می‌کند؛ یادداشت سرور بدون تغییر نشان
 *   داده می‌شود.
 * - بذر (seed) بهینه‌ساز در سمت کلاینت الزامی می‌شود — بدون بذر درخواستی
 *   ارسال نمی‌شود (تکرارپذیری §D4) و جزئیات 422 سرور عیناً نمایش داده می‌شود.
 * - خروجی CSV/JSON فقط از متنِ پاسخ سرور ساخته می‌شود؛ هیچ سطری اینجا
 *   تولید یا بازنویسی نمی‌شود.
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
let lastRun = null; // آخرین پاسخ بک‌تست — مبنای خروجی CSV/JSON
let lastRequestBody = null; // WAVE-2 integration: دقیقاً همان بدنه‌ای که به /backtest رفت — خروجی همان اجرا را بازتولید می‌کند (بدون state سمت سرور)

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
  const out = $("bcOut");
  if (!out) return;
  out.textContent = typeof objOrText === "string" ? objOrText : JSON.stringify(objOrText, null, 2);
}

function trustFrom(payload) {
  const el = $("bcTrustBadge");
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

/* ------------------------- اجرای بک‌تست ------------------------- */

function runParams() {
  return {
    symbol: ($("bcSymbol")?.value || "FOLAD").trim().slice(0, 32),
    timeframe: $("bcTimeframe")?.value || "1D",
    count: Math.max(50, Math.min(1000, parseInt($("bcCount")?.value || "200", 10) || 200)),
  };
}

async function bcRun() {
  const btn = $("bcRun");
  const source = ($("bcDslSource")?.value || "").trim();
  if (!source) {
    toast("منبع DSL خالی است — استراتژی را وارد کنید", "error");
    showOut("منبع DSL خالی است — هیچ درخواستی ارسال نشد.");
    return;
  }
  busy(btn, true, "در حال اجرا…");
  showOut("در حال اجرای بک‌تست روی داده سینتتیک سرور…");
  try {
    const reqBody = { source, ...runParams() };
    const res = await api("/api/v10/strategylab/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reqBody),
    });
    lastRequestBody = reqBody; // برای /backtest/export — همان ورودی، همان digest
    lastRun = res;
    trustFrom(res);
    renderRun(res);
    showOut({
      run_id: res.run_id,
      result_digest: res.result_digest,
      bars_used: res.bars_used,
      trades_count: res.trades_count,
      data_trust_label: res.data_trust_label,
      synthetic_note: res.synthetic_note,
      limitations: res.limitations,
    });
    toast("بک‌تست کامل شد (داده سینتتیک)", "success");
  } catch (e) {
    showOut(`اجرای بک‌تست ناموفق بود:\n${errText(e)}`);
    toast("بک‌تست ناموفق — جزئیات در خروجی", "error");
  } finally {
    busy(btn, false);
  }
}

function reportOf(res) {
  return res && typeof res.report === "object" && res.report ? res.report : {};
}

function renderRun(res) {
  const report = reportOf(res);
  renderMetrics(report);
  drawEquity($("bcEquityCanvas"), report.equity_curve || res.equity_curve || []);
  renderTrades(res.trades || report.trades || res.trades_sample || report.trades_sample || []);
  renderRegimes(report.regime_segments || res.regime_segments || res.regimes || []);
}

const METRIC_ROWS = [
  ["بازده کل ٪", (r) => r.total_return_pct],
  ["بازده سالانه ٪", (r) => r.annualized_return_pct],
  ["CAGR ٪", (r) => r.cagr_pct],
  ["بیشینه افت سرمایه ٪", (r) => r.max_drawdown_pct],
  ["طول بیشینه افت (کندل)", (r) => r.max_drawdown_duration_bars],
  ["شارپ", (r) => r.sharpe],
  ["سورتینو", (r) => r.sortino],
  ["کالمر", (r) => r.calmar],
  ["فاکتور سود", (r) => r.profit_factor],
  ["امید ریاضی هر معامله", (r) => r.expectancy],
  ["نرخ برد ٪", (r) => r.win_rate],
  ["تعداد معاملات", (r) => r.trade_count, 0],
  ["درصد حضور در بازار", (r) => r.exposure_pct],
  ["میانگین نگهداری (کندل)", (r) => r.avg_holding_bars],
  ["کارمزد کل", (r) => r.fees_total],
];

function renderMetrics(report) {
  const body = $("bcMetricsBody");
  if (!body) return;
  body.innerHTML = "";
  METRIC_ROWS.forEach(([label, get, digits]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${esc(label)}</td><td style="direction:ltr">${cell(get(report), digits === undefined ? 2 : digits)}</td>`;
    body.appendChild(tr);
  });
}

/** نمودار اولیه: خط ساده از سری سرمایه سرور — هیچ داده‌ای اینجا ساخته نمی‌شود */
function drawEquity(canvas, points) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const vals = (Array.isArray(points) ? points : [])
    .map((p) => Number(p && typeof p === "object" ? pick(p, ["equity", "value", "equity_value"]) : p))
    .filter((v) => typeof v === "number" && !Number.isNaN(v));
  if (!vals.length) {
    ctx.fillStyle = "#888";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("سری سرمایه در پاسخ سرور نبود — چیزی برای ترسیم نیست", w / 2, h / 2);
    return;
  }
  const pad = 10;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  ctx.strokeStyle = "#5b9dd9";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  vals.forEach((v, i) => {
    const x = pad + (i * (w - 2 * pad)) / Math.max(1, vals.length - 1);
    const y = h - pad - ((v - min) * (h - 2 * pad)) / span;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#888";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`بیشینه: ${fmtNum(max, 0)}`, pad, 12);
  ctx.fillText(`کمینه: ${fmtNum(min, 0)}`, pad, h - 2);
}

const SIDE_FA = { LONG: "خرید (LONG)", SHORT: "فروش (SHORT)" };

function renderTrades(trades) {
  const body = $("bcTradesBody");
  if (!body) return;
  body.innerHTML = "";
  const list = Array.isArray(trades) ? trades : [];
  if (!list.length) {
    body.innerHTML = `<tr><td colspan="5" class="muted">پاسخ سرور فهرست معاملات نداشت (فقط تعداد گزارش شده است)</td></tr>`;
    return;
  }
  list.forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${esc(String(pick(t, ["symbol", "sym"]) || "—"))}</td>` +
      `<td>${esc(SIDE_FA[pick(t, ["side", "direction"])] || String(pick(t, ["side", "direction"]) || "—"))}</td>` +
      `<td style="direction:ltr">${cell(pick(t, ["entry_price", "entry", "entry_fill_price"]))}</td>` +
      `<td style="direction:ltr">${cell(pick(t, ["exit_price", "exit", "exit_fill_price"]))}</td>` +
      `<td style="direction:ltr">${cell(pick(t, ["net_pnl", "pnl", "net_profit"]))}</td>`;
    body.appendChild(tr);
  });
}

function renderRegimes(segments) {
  const body = $("bcRegimeBody");
  if (!body) return;
  body.innerHTML = "";
  const list = Array.isArray(segments) ? segments : [];
  if (!list.length) {
    body.innerHTML = `<tr><td colspan="4" class="muted">پاسخ سرور بخش‌بندی رژیم نداشت — چیزی جعل نمی‌شود</td></tr>`;
    return;
  }
  list.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${esc(String(pick(r, ["regime", "label", "name"]) ?? "—"))}</td>` +
      `<td style="direction:ltr">${cell(pick(r, ["trades", "trade_count", "count"]), 0)}</td>` +
      `<td style="direction:ltr">${cell(pick(r, ["win_rate", "winrate"]))}</td>` +
      `<td style="direction:ltr">${cell(pick(r, ["total_return_pct", "return_pct", "total_return"]))}</td>`;
    body.appendChild(tr);
  });
}

/* ------------------------- خروجی CSV/JSON ------------------------- */

/** متن خروجی فقط از فیلدهای متنیِ پاسخ سرور استخراج می‌شود؛ پاسخ JSON بدون
 * فیلد متنی برای خروجی JSON خودِ پاسخ سری‌سازی می‌شود — هیچ چیزی بازسازی
 * نمی‌شود. */
function exportText(res, format) {
  if (typeof res === "string" && res) return res;
  for (const key of ["content", "text", "csv", "body", "data"]) {
    if (typeof res?.[key] === "string" && res[key]) return res[key];
  }
  if (format === "json") return JSON.stringify(res, null, 2);
  return "";
}

function downloadText(filename, text, mime) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // آزادسازی object URL — نشت حافظه باقی نماند
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

async function bcExport(format) {
  if (!lastRequestBody) {
    toast("ابتدا یک بک‌تست اجرا کنید — خروجی بدون اجرا معنا ندارد", "warn");
    return;
  }
  try {
    // WAVE-2 integration: سرویس خروجی بدون state است — همان بدنه‌ی آخرین اجرا
    // دوباره ارسال می‌شود تا همان result_digest و همان گزارش بازتولید شود.
    const res = await api("/api/v10/strategylab/backtest/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...lastRequestBody, format }),
    });
    trustFrom(typeof res === "string" ? null : res);
    const text = exportText(res, format);
    if (!text) {
      showOut(`خروجی ${format} پاسخ متنیِ قابل دانلود نداشت — چیزی جعل نمی‌شود.`);
      toast("خروجی ناموفق — پاسخ سرور متنی نداشت", "error");
      return;
    }
    const safeName = String((typeof res === "object" && res) ? res.filename || res.file_name || "" : "").replace(/[^\w.\-]/g, "");
    const digest8 = String(lastRun?.result_digest || "").slice(0, 8) || "nodigest";
    const filename = safeName || `backtest-report-${digest8}.${format}`;
    downloadText(filename, text, format === "csv" ? "text/csv;charset=utf-8" : "application/json;charset=utf-8");
    toast("خروجی از متن پاسخ سرور ساخته و دانلود شد", "success");
  } catch (e) {
    showOut(`خروجی ${format} ناموفق بود:\n${errText(e)}`);
    toast("خروجی گرفتن ناموفق بود — جزئیات در خروجی", "error");
  }
}

/* ------------------------- بهینه‌ساز ------------------------- */

async function bcOptimize() {
  const btn = $("bcOptRun");
  // الزام سمت کلاینت بذر (§D4): بدون بذر، درخواستی ارسال نمی‌شود
  const seedRaw = String($("bcOptSeed")?.value || "").trim();
  if (!seedRaw) {
    showOut("بذر (seed) الزامی است — بدون بذر جستجو تکرارپذیر نیست و درخواستی ارسال نشد.");
    toast("بذر (seed) الزامی است", "error");
    return;
  }
  const seed = Number(seedRaw);
  if (!Number.isInteger(seed) || seed < 0) {
    showOut("بذر باید یک عدد صحیح نامنفی باشد — درخواستی ارسال نشد.");
    toast("بذر نامعتبر است", "error");
    return;
  }
  const source = ($("bcDslSource")?.value || "").trim();
  if (!source) {
    toast("منبع DSL خالی است — استراتژی را وارد کنید", "error");
    return;
  }
  // WAVE-2 integration: فضای جست‌وجو JSON صریح کاربر است (grid یا bounds) —
  // هیچ فضای پیش‌فرض پنهانی ساخته نمی‌شود؛ JSON نامعتبر = بدون درخواست.
  let space = null;
  const spaceRaw = String($("bcOptSpace")?.value || "").trim();
  if (!spaceRaw) {
    showOut("فضای جست‌وجو (space) الزامی است — مثال: {\"grid\": {\"len\": [10, 20, 50]}}");
    toast("فضای جست‌وجو الزامی است", "error");
    return;
  }
  try {
    space = JSON.parse(spaceRaw);
  } catch (e) {
    showOut(`JSON فضای جست‌وجو نامعتبر است — درخواستی ارسال نشد:\n${errText(e)}`);
    toast("JSON فضای جست‌وجو نامعتبر است", "error");
    return;
  }
  busy(btn, true, "در حال بهینه‌سازی…");
  showOut("در حال اجرای بهینه‌سازی (انتخاب فقط درون‌نمونه‌ای)…");
  try {
    const res = await api("/api/v10/strategylab/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source,
        ...runParams(),
        method: $("bcOptMethod")?.value || "grid",
        space,
        budget: {
          max_evals: Math.max(1, Math.min(500, parseInt($("bcOptMaxEvals")?.value || "50", 10) || 50)),
          seed,
        },
        oos: { enabled: !!$("bcOptOos")?.checked },
      }),
    });
    trustFrom(res);
    renderOptResults(res);
    showOut(res);
    toast("بهینه‌سازی کامل شد (داده سینتتیک)", "success");
  } catch (e) {
    showOut(`بهینه‌سازی ناموفق بود (جزئیات 422 سرور عیناً زیر آمده):\n${errText(e)}`);
    toast("بهینه‌سازی ناموفق — جزئیات در خروجی", "error");
  } finally {
    busy(btn, false);
  }
}

function renderOptResults(res) {
  const body = $("bcOptResultsBody");
  const winnerBox = $("bcOptWinner");
  if (!body || !winnerBox) return;
  body.innerHTML = "";
  const trials = res.trials || res.results || res.evaluations || res.records || [];
  const list = Array.isArray(trials) ? trials : [];
  if (!list.length) {
    body.innerHTML = `<tr><td colspan="4" class="muted">پاسخ سرور فهرست ارزیابی‌ها نداشت — چیزی جعل نمی‌شود</td></tr>`;
  } else {
    list.forEach((t, i) => {
      const refused = !!(t.is_refused || t.refused);
      const reason = pick(t, ["refusal_reason", "refused_reason", "reason"]);
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${fmtNum(i + 1)}</td>` +
        `<td style="direction:ltr">${esc(JSON.stringify(t.params || t.param_set || {}).slice(0, 90))}</td>` +
        `<td style="direction:ltr">${cell(pick(t, ["objective", "objective_value", "value", "score"]))}</td>` +
        `<td>${refused ? `رد شد: ${esc(String(reason || "—"))}` : "ارزیابی شد"}</td>`;
      body.appendChild(tr);
    });
  }
  const winner = res.winner || res.best || (res.selection && res.selection.winner) || null;
  const oos = res.oos_confirmation || res.oos || res.confirmation || null;
  const parts = [];
  if (winner) {
    parts.push(
      `برنده درون‌نمونه‌ای (IS): <span style="direction:ltr">${esc(JSON.stringify(winner.params || winner.param_set || winner).slice(0, 90))}</span>` +
        ` — هدف IS: <span style="direction:ltr">${cell(pick(winner, ["objective", "objective_value", "value", "score"]))}</span>`
    );
  } else {
    parts.push("برنده‌ای در پاسخ سرور نبود — انتخابی جعل نمی‌شود.");
  }
  if (oos) {
    // WAVE-2 integration sync (AUDIT-MR2 O2): کلیدهای واقعِ قرارداد سرور —
    // oos_evaluated_once (ارزیابی دقیقاً یک‌بار پس از انتخاب) و
    // oos_objective_value / is_objective_value.
    const once = pick(oos, ["oos_evaluated_once"]);
    const confirmed = once === null ? null : !!once;
    parts.push(
      `تأیید OOS: ${confirmed === null ? "— " : confirmed ? "انجام شد (فقط یک‌بار، پس از انتخاب)" : "انجام نشد"} —` +
        ` هدف IS: <span style="direction:ltr">${cell(pick(oos, ["is_objective_value"]))}</span> ·` +
        ` هدف OOS: <span style="direction:ltr">${cell(pick(oos, ["oos_objective_value"]))}</span>`
    );
  } else {
    parts.push("تأیید OOS در پاسخ نبود (بدون ارزیابی برون‌نمونه).");
  }
  // AUDIT-MR2 O2: یادداشت چندآزمونی واقعی سرور bonferroni_note است.
  const mtNote = res.bonferroni_note || res.multiple_testing_note || "";
  const alpha = pick(res, ["alpha_effective"]);
  let noteLine = "";
  if (mtNote) noteLine = `<div class="muted" style="margin-top:4px">${esc(String(mtNote))}</div>`;
  else if (alpha !== null) noteLine = `<div class="muted" style="margin-top:4px">آلفای مؤثر (بونفرونی): ${esc(String(alpha))}</div>`;
  // اجزای parts از قبل با esc/cell فرارکرده‌اند — دوباره فرارکردن، مارک‌آپ
  // عمدی (span) را خراب می‌کند.
  winnerBox.innerHTML = `<div>${parts.join("<br />")}${noteLine}</div>`;
}

/* ------------------------- بایند-on-demand ------------------------- */

function bindBacktestCenter() {
  if (bound || !$("bcRun")) return;
  bound = true;

  const on = (id, fn) => {
    const el = $(id);
    if (el) el.addEventListener("click", fn);
  };
  on("bcRun", bcRun);
  on("bcExportCsv", () => bcExport("csv"));
  on("bcExportJson", () => bcExport("json"));
  on("bcOptRun", bcOptimize);

  // فعال‌سازی هنگام باز شدن تب (الگوی strategy_lab) — بدون هیچ درخواست خودکار:
  // اجرای بک‌تست/بهینه‌ساز فقط با کنش صریح کاربر انجام می‌شود.
  const observer = new MutationObserver(() => {
    const panel = $("tab-backtestcenter");
    if (panel && panel.classList.contains("active") && !activated) {
      activated = true;
      const out = $("bcOut");
      if (out) {
        out.textContent =
          "آماده — منبع DSL (RSL-1) را وارد و «اجرای بک‌تست» را بزنید. هیچ درخواست خودکاری ارسال نمی‌شود و همه اعداد از پاسخ سرور می‌آیند (داده سینتتیک).";
      }
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindBacktestCenter);
  else bindBacktestCenter();
}
