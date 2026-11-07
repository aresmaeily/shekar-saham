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
import { api, apiBlob, toast } from "../../core/api.js";
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

/* ------------------- تحلیل walk-forward (MASTER-2 WP-J) -------------------
 * WAVE-AB2 (2026-11-08): افزودن تریگر UI برای تحلیل walk-forward — گپ ثبت‌شده
 * WAVE-AD («تریگر UI walk-forward صادقانه غایب») همین‌جا بسته می‌شود.
 * پشتوانه: POST /api/v10/strategylab/walkforward + /walkforward/export
 * (موتور walk_forward.py — ۳۸ آزمون) که از قبل موجود و آزموده بود؛ این بخش
 * فقط مسیر UI را به همان API می‌بندد. هیچ رفتار موجودی تغییر نمی‌کند.
 * قرارداد همان بقیه مرکز است: همه HTTP از api()/apiBlob()؛ esc برای هر متن
 * درون‌یابی‌شده؛ برچسب اعتماد فقط از trust_envelope سرور؛ اجرا فقط با کنش
 * صریح کاربر؛ انتخاب درون‌نمونه‌ای در هر فولد و ارزیابی OOS دقیقاً یک‌بار —
 * عیناً همان که سرور گزارش می‌کند، بدون تزئین.
 */

let lastWalkforwardBody = null; // آخرین بدنه walk-forward برای خروجی گزارش (همان بدنه، همان digest)

function wfParams() {
  const intOr = (id, fallback) => {
    const v = parseInt($(id)?.value || "", 10);
    return Number.isInteger(v) ? v : fallback;
  };
  return {
    n: Math.max(2, Math.min(12, intOr("fcWfN", 3))),
    train_bars: Math.max(30, intOr("fcWfTrain", 60)),
    test_bars: Math.max(10, intOr("fcWfTest", 20)),
    max_evals_per_fold: Math.max(1, Math.min(100, intOr("fcWfMaxEvals", 9))),
  };
}

function wfBody() {
  // الزام بذر سمت کلاینت (همان انضباط §D4 بهینه‌ساز): بدون بذر درخواستی ارسال نمی‌شود.
  const seedRaw = String($("fcWfSeed")?.value || "").trim();
  if (seedRaw === "") {
    showOut("بذر (seed) الزامی است — بدون بذر walk-forward تکرارپذیر نیست و درخواستی ارسال نشد.");
    toast("بذر (seed) الزامی است", "error");
    return null;
  }
  const seed = Number(seedRaw);
  if (!Number.isInteger(seed) || seed < 0) {
    showOut("بذر باید یک عدد صحیح نامنفی باشد — درخواستی ارسال نشد.");
    toast("بذر نامعتبر است", "error");
    return null;
  }
  const source = ($("fcDslSource")?.value || "").trim();
  if (!source) {
    toast("منبع DSL خالی است — استراتژی را وارد کنید", "error");
    showOut("منبع DSL خالی است — هیچ درخواستی ارسال نشد.");
    return null;
  }
  let space = null;
  const spaceRaw = String($("fcWfSpace")?.value || "").trim();
  if (!spaceRaw) {
    showOut("فضای جست‌وجو (space) الزامی است — مثال: {\"grid\": {\"len\": [5, 10, 20]}}");
    toast("فضای جست‌وجو الزامی است", "error");
    return null;
  }
  try {
    space = JSON.parse(spaceRaw);
  } catch (e) {
    showOut(`JSON فضای جست‌وجو نامعتبر است — درخواستی ارسال نشد:\n${errText(e)}`);
    toast("JSON فضای جست‌وجو نامعتبر است", "error");
    return null;
  }
  const p = wfParams();
  const objective = String($("fcWfObjective")?.value || "SHARPE");
  return {
    source,
    symbol: runParams().symbol,
    timeframe: runParams().timeframe,
    count: runParams().count,
    folds: { n: p.n, train_bars: p.train_bars, test_bars: p.test_bars },
    space,
    budget: { max_evals_per_fold: p.max_evals_per_fold, seed },
    objective,
  };
}

function wfStatusOf(fold) {
  // وضعیت هر فولد عیناً از پرچم‌های سرور — هیچ تفسیر اضافه‌ای جعل نمی‌شود.
  const flags = [];
  if (fold.budget_exhausted) flags.push("پایان بودجه");
  if (fold.cancelled) flags.push("لغوشده");
  if (fold.oos_evaluated_once) flags.push("OOS یک‌بار");
  return flags.length ? esc(flags.join(" · ")) : "—";
}

function renderWfFolds(res) {
  const body = $("fcWfFoldsBody");
  if (!body) return;
  body.innerHTML = "";
  const folds = Array.isArray(res.folds) ? res.folds : [];
  if (!folds.length) {
    body.innerHTML = `<tr><td colspan="9" class="muted">پاسخ سرور فهرست فولدها نداشت — چیزی جعل نمی‌شود</td></tr>`;
    return;
  }
  folds.forEach((f) => {
    const train = f.train ? `${cell(f.train.start, 0)}..${cell(f.train.end, 0)}` : "—";
    const test = f.test ? `${cell(f.test.start, 0)}..${cell(f.test.end, 0)}` : "—";
    const params = f.best_params && typeof f.best_params === "object"
      ? esc(Object.entries(f.best_params).map(([k, v]) => `${k}=${v}`).join(", "))
      : "—";
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td style="direction:ltr">${cell(f.fold_index, 0)}</td>` +
      `<td style="direction:ltr">${train}</td>` +
      `<td style="direction:ltr">${test}</td>` +
      `<td style="direction:ltr">${cell(f.fold_seed, 0)}</td>` +
      `<td style="direction:ltr">${params}</td>` +
      `<td style="direction:ltr">${cell(f.is_objective)}</td>` +
      `<td style="direction:ltr">${cell(f.oos_objective)}</td>` +
      `<td style="direction:ltr">${cell(f.evaluated_count, 0)}</td>` +
      `<td>${wfStatusOf(f)}</td>`;
    body.appendChild(tr);
  });
}

function renderWfAggregate(res) {
  const body = $("fcWfAggregateBody");
  if (!body) return;
  body.innerHTML = "";
  const a = res.aggregate && typeof res.aggregate === "object" ? res.aggregate : null;
  if (!a) {
    body.innerHTML = `<tr><td colspan="2" class="muted">پاسخ سرور بخش تجمیع نداشت — چیزی جعل نمی‌شود</td></tr>`;
    return;
  }
  const rows = [
    ["تعداد فولدها", a.n_folds, 0],
    ["فولدهای تأییدشده (OOS)", a.confirmed_folds, 0],
    ["فولدهای با OOS مثبت", a.positive_folds, 0],
    ["میانگین OOS", a.oos_mean],
    ["میانه OOS", a.oos_median],
    ["کمینه OOS", a.oos_min],
    ["بیشینه OOS", a.oos_max],
    ["مبنای انتخاب", a.selection_basis],
    ["OOS در هر فولد دقیقاً یک‌بار ارزیابی شد", a.oos_evaluated_once_per_fold],
  ];
  rows.forEach(([label, v, digits]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${esc(String(label))}</td><td style="direction:ltr">${cell(v, digits === undefined ? 2 : digits)}</td>`;
    body.appendChild(tr);
  });
  const digestRow = document.createElement("tr");
  digestRow.innerHTML =
    `<td>خلاصه تکرارپذیری</td><td style="direction:ltr">${esc(String(res.reproducibility_digest || "—"))}</td>`;
  body.appendChild(digestRow);
}

function renderWalkforward(res) {
  renderWfFolds(res);
  renderWfAggregate(res);
  const noteEl = $("fcWfNote");
  if (noteEl && res.bonferroni_note) noteEl.textContent = String(res.bonferroni_note);
  const [jbtn, cbtn, pbtn] = [$("fcWfExportJson"), $("fcWfExportCsv"), $("fcWfExportPdf")];
  [jbtn, cbtn, pbtn].forEach((b) => { if (b) b.disabled = false; });
}

function downloadBlobLocal(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function downloadTextLocal(filename, text, mime) {
  downloadBlobLocal(filename, new Blob([text], { type: mime }));
}

async function fcWalkforward() {
  const btn = $("fcWfRun");
  const body = wfBody();
  if (!body) return;
  busy(btn, true, "در حال walk-forward…");
  showOut("در حال اجرای walk-forward (انتخاب IS در هر فولد + تأیید OOS یک‌بار) روی داده سینتتیک سرور…");
  try {
    const res = await api("/api/v10/strategylab/walkforward", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    lastWalkforwardBody = body;
    trustFrom(res);
    renderWalkforward(res);
    showOut(res);
    toast("walk-forward کامل شد — انتخاب فقط درون‌نمونه‌ای، OOS یک‌بار", "success");
  } catch (e) {
    showOut(`walk-forward ناموفق بود:\n${errText(e)}`);
    toast("walk-forward ناموفق بود — جزئیات در خروجی", "error");
  } finally {
    busy(btn, false);
  }
}

async function fcWfExport(format) {
  if (!lastWalkforwardBody) {
    toast("ابتدا walk-forward را اجرا کنید — خروجی بدون اجرا معنا ندارد", "warn");
    return;
  }
  try {
    if (format === "json") {
      const res = await api("/api/v10/strategylab/walkforward/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...lastWalkforwardBody, format }),
      });
      downloadTextLocal(
        `walkforward-report-${String(res.reproducibility_digest || "").slice(0, 8) || "nodigest"}.json`,
        JSON.stringify(res, null, 2),
        "application/json;charset=utf-8"
      );
      toast("خروجی JSON walk-forward دانلود شد", "success");
      return;
    }
    const att = await apiBlob("/api/v10/strategylab/walkforward/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...lastWalkforwardBody, format }),
    });
    const safeName = String(att.filename || "").replace(/[^\w.\-]/g, "");
    downloadBlobLocal(safeName || "walkforward-report.pdf", att.blob);
    toast(`خروجی ${format === "pdf" ? "PDF" : "CSV"} walk-forward دانلود شد`, "success");
  } catch (e) {
    showOut(`خروجی ${format} walk-forward ناموفق بود:\n${errText(e)}`);
    toast("خروجی walk-forward ناموفق بود — جزئیات در خروجی", "error");
  }
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
  on("fcWfRun", fcWalkforward);
  on("fcWfExportJson", () => fcWfExport("json"));
  on("fcWfExportCsv", () => fcWfExport("csv"));
  on("fcWfExportPdf", () => fcWfExport("pdf"));

  // فعال‌سازی هنگام باز شدن تب (الگوی strategy_lab) — بدون هیچ درخواست خودکار:
  // بازپخش کاغذی فقط با کنش صریح کاربر اجرا می‌شود.
  const observer = new MutationObserver(() => {
    const panel = $("tab-forwardcenter");
    if (panel && panel.classList.contains("active") && !activated) {
      activated = true;
      const out = $("fcOut");
      if (out) {
        out.textContent =
          "آماده — منبع DSL (RSL-1) را وارد و «اجرای بازپخش کاغذی» یا «اجرای walk-forward» را بزنید. این مرکز فقط بازپخش کاغذی و تحلیل walk-forward روی داده سینتتیک است؛ نه معامله زنده، نه بروکر، نه زمان‌بند.";
      }
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindForwardCenter);
  else bindForwardCenter();
}
