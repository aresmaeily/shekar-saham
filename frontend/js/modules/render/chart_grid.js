/**
 * chart_grid.js — MASTER-RADAR WAVE-3 (2026-11-04) / MR-B2-01: گرید چندنموداری «چارت حرفه‌ای»
 *
 * - فضای کاری چندچارتی: چیدمان ۱ (پیش‌فرض — بدون هیچ UI و بدون هیچ تداخلی با
 *   چارت تک‌نمودی موجود)، ۲ (اصلی + یک پنل فرعی)، ۴ (اصلی + سه پنل فرعی).
 * - چارت «اصلی» هم همان نمونه ChartProChart داخل #cpChart است — این ماژول
 *   هرگز آن را بازسازی/دستکاری نمی‌کند؛ پنل‌های فرعی همیشه چارت‌های خطی سبک
 *   جدیدِ خود این ماژول‌اند (داخل #cpGridRoot که مرحله ادغام اضافه می‌کند).
 * - پنل فرعی = حداقل: ورودی نماد + انتخاب تایم‌فریم (همان شبکه 1m/5m/15m/1h/1D)
 *   + سری خطی close از GET /api/v10/chartpro/{symbol}?timeframe=...&limit=300
 *   + برچسب اعتماد کوچک فقط از فیلدهای سرور (بدون هیچ برچسب ساختگی).
 *   بدون رسم، بدون هشدار، بدون polling — هیچ تایمری جز debounce ذخیره نیست.
 * - همگام‌سازی‌ها (هر سه قابل خاموش‌کردن):
 *     «همگام‌سازی بازه»     → دوسویه، الگوی _syncScales چارت اصلی با فلگ بازگشت
 *     «همگام‌سازی کراس‌هیر» → از کراس‌هیر اصلی به پنل‌ها؛ API امکان‌سنجی‌شده —
 *       در نسخه وندور v4.2.0 هر دو متد setCrosshairPosition(price,time,series)
 *       و clearCrosshairPosition() موجودند (بررسی‌شده در
 *       frontend/vendor/lightweight-charts.standalone.production.js)؛ با این حال
 *       هر فراخوانی با typeof + try/catch محافظت شده تا با تغییر وندور در آینده
 *       صادقانه no-op شود، نه خطا و نه رفتار ساختگی.
 *     «همگام‌سازی نماد»     → محدودیت مستندشده: بدون شنونده/تایمر پس‌زمینه،
 *       دنبال‌کردنِ تغییرِ نماد اصلی خودکار نیست؛ نماد فعال اصلی فقط در لحظه
 *       تعامل کاربر با گرید (کلیک toggle یا تغییر چیدمان) روی پنل‌ها اعمال
 *       می‌شود. این تصمیم آگاهانه و صادقانه است — نه حلقه پس‌زمینه.
 * - ماندگاری: کلید radar.chartgrid.v1 با پاکت {schema, saved_at_iso, payload}؛
 *   اعتبارسنجی fail-closed به سبک workspace.js (فیلد ناشناخته دور ریخته، نوع
 *   غلط → پیش‌فرض، خراب → قرنطینه نسخه خام زیر radar.chartgrid.corrupted و
 *   بازنشانی) — هرگز throw نمی‌کند.
 * - داده فقط از core/api.js — هیچ درخواست شبکه‌ای مستقیم از خود این ماژول
 *   نیست (قرارداد اجباری مرز HTTP) و هیچ ارزیابی کد پویا در کار نیست.
 */
import { api } from "../../core/api.js";
import { chartPalette } from "../utils/chart_theme.js"; // همان تم چارت اصلی — بدون وابستگی جدید
import { getActiveChartPro } from "./chart_pro.js"; // WAVE-3: دسترسی فقط-خواندنی به singleton

const GRID_KEY = "radar.chartgrid.v1";
const GRID_CORRUPTED_KEY = "radar.chartgrid.corrupted";
const GRID_SCHEMA = 1;
/* همان شبکه تایم‌فریم بک‌اند (app/api/chart_pro.py) و سگمنت cpTfSeg */
const GRID_TIMEFRAMES = ["1m", "5m", "15m", "1h", "1D"];
const GRID_LAYOUTS = [1, 2, 4];
const GRID_MAX_PANES = 3;
const GRID_PANE_LIMIT = 300;
const GRID_SYMBOL_MAX_LEN = 64;
const GRID_STYLE_ID = "cp-grid-style";
const GRID_SAVE_DEBOUNCE_MS = 600; // مثل _queueWorkspaceSave چارت اصلی

/* برچسب فارسی toggles — متن نمایشی است، نه برچسب اعتماد */
const GRID_SYNC_LABELS = {
  range: "همگام‌سازی بازه",
  crosshair: "همگام‌سازی کراس‌هیر",
  symbol_follow: "همگام‌سازی نماد",
};
const GRID_SYNC_KEYS = ["range", "crosshair", "symbol_follow"];
/* ارقام فارسی چیدمان */
const GRID_LAYOUT_LABELS_FA = { 1: "۱", 2: "۲", 4: "۴" };

/* >>> WAVE-3 PURE LOGIC BEGIN — منطق خالص ماندگاری (مرز پین ایستای تست‌ها) */

function _isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/** وضعیت پیش‌فرض — هر سه همگام‌سازی روشن (طبق مشخصه MR-B2-01) */
function gridDefaultState() {
  return {
    layout: 1,
    sync: { range: true, crosshair: true, symbol_follow: true },
    panes: [],
  };
}

/**
 * اعتبارسنجی فیلدبه‌فیلد — فیلد ناشناخته دور ریخته؛ نوع غلط → پیش‌فرض و ثبت
 * در issues. خروجی همیشه یک وضعیت کامل معتبر است (هرگز throw نمی‌کند).
 */
function gridValidateState(raw) {
  const def = gridDefaultState();
  const state = def;
  const issues = [];
  if (!_isPlainObject(raw)) {
    issues.push("state: not an object -> defaults");
    return { state, issues };
  }
  const KNOWN_FIELDS = ["layout", "sync", "panes"];
  const unknown = Object.keys(raw).filter((k) => !KNOWN_FIELDS.includes(k));
  if (unknown.length) issues.push("unknown fields dropped: " + unknown.join(","));

  /* چیدمان — فقط 1/2/4 */
  if (raw.layout !== undefined) {
    if (GRID_LAYOUTS.includes(raw.layout)) state.layout = raw.layout;
    else issues.push("layout: refused -> default 1");
  }

  /* toggles همگام‌سازی — بولی (تبدیل 0/1 مجاز) */
  if (raw.sync !== undefined) {
    if (_isPlainObject(raw.sync)) {
      for (const k of GRID_SYNC_KEYS) {
        if (raw.sync[k] === undefined) continue;
        if (typeof raw.sync[k] === "boolean") state.sync[k] = raw.sync[k];
        else if (raw.sync[k] === 0 || raw.sync[k] === 1) state.sync[k] = !!raw.sync[k];
        else issues.push("sync." + k + ": wrong type refused -> default");
      }
    } else {
      issues.push("sync: not an object refused -> defaults");
    }
  }

  /* پنل‌های فرعی — حداکثر 3 مورد {symbol, timeframe} معتبر */
  if (raw.panes !== undefined) {
    if (Array.isArray(raw.panes)) {
      const kept = [];
      for (const p of raw.panes) {
        if (kept.length >= GRID_MAX_PANES) {
          issues.push("panes: truncated to " + GRID_MAX_PANES);
          break;
        }
        if (_isPlainObject(p) && typeof p.symbol === "string" && p.symbol.trim() &&
            GRID_TIMEFRAMES.includes(p.timeframe)) {
          kept.push({ symbol: p.symbol.trim().slice(0, GRID_SYMBOL_MAX_LEN), timeframe: p.timeframe });
        } else {
          issues.push("panes: one invalid item dropped");
        }
      }
      state.panes = kept;
    } else {
      issues.push("panes: not an array refused -> default");
    }
  }
  return { state, issues };
}

/** قرنطینه خرابی — نسخه خام به‌عنوان شواهد، کلید اصلی بازنشانی؛ هرگز throw نمی‌کند */
function gridQuarantine(storage, raw, cause) {
  try {
    storage.setItem(
      GRID_CORRUPTED_KEY,
      JSON.stringify({
        quarantined_at_iso: new Date().toISOString(),
        cause: String(cause || "unknown"),
        raw: String(raw).slice(0, 20000),
      })
    );
  } catch (err) { /* نوشتن شواهد بهترین‌تلاش است */ }
  try { storage.removeItem(GRID_KEY); } catch (err) { /* بازنشانی بهترین‌تلاش است */ }
  return { ok: false, reason: "corrupted_quarantined", state: gridDefaultState(), issues: [] };
}

/** بارگذاری و اعتبارسنجی — همیشه وضعیت معتبر می‌دهد؛ هرگز throw نمی‌کند */
function gridLoadState(storage) {
  if (!storage || typeof storage.getItem !== "function") {
    return { ok: false, reason: "storage_unavailable", state: gridDefaultState(), issues: [] };
  }
  let raw = null;
  try {
    raw = storage.getItem(GRID_KEY);
  } catch (err) {
    return { ok: false, reason: "storage_unavailable", state: gridDefaultState(), issues: [] };
  }
  if (raw === null || raw === "") {
    return { ok: true, restored: false, state: gridDefaultState(), issues: [] };
  }
  let parsed = null;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    return gridQuarantine(storage, raw, "json_parse_failed");
  }
  if (!_isPlainObject(parsed)) {
    return gridQuarantine(storage, raw, "envelope_not_object");
  }
  /* اسکیمای ناشناخته/آینده: داده حفظ می‌شود — بدون قرنطینه (مثل workspace.js) */
  if (parsed.schema !== GRID_SCHEMA) {
    return { ok: false, reason: "schema_unsupported", state: gridDefaultState(), issues: [] };
  }
  if (!_isPlainObject(parsed.payload)) {
    return gridQuarantine(storage, raw, "payload_not_object");
  }
  const v = gridValidateState(parsed.payload);
  return { ok: true, restored: true, state: v.state, issues: v.issues };
}

/** ذخیره — پاکت نسخه‌دار {schema, saved_at_iso, payload}؛ هرگز throw نمی‌کند */
function gridSaveState(storage, state) {
  if (!storage || typeof storage.setItem !== "function") {
    return { ok: false, reason: "storage_unavailable", issues: [] };
  }
  const v = gridValidateState(state);
  try {
    storage.setItem(
      GRID_KEY,
      JSON.stringify({ schema: GRID_SCHEMA, saved_at_iso: new Date().toISOString(), payload: v.state })
    );
    return { ok: true, issues: v.issues };
  } catch (err) {
    return { ok: false, reason: "storage_write_failed", issues: [] };
  }
}

/** مقایسه زمان — عددی یا رشته (تایم‌فریم 1D می‌تواند business-day رشته‌ای باشد) */
function gridSameTime(a, b) {
  if (a == null || b == null) return false;
  const na = Number(a);
  const nb = Number(b);
  if (isFinite(na) && isFinite(nb)) return na === nb;
  return String(a) === String(b);
}

/* <<< WAVE-3 PURE LOGIC END */

export class ChartGrid {
  constructor(opts = {}) {
    this.rootId = opts.rootId || "cpGridRoot";
    this.barId = opts.barId || "cpGridBar";
    this.state = gridDefaultState();
    this.panes = []; // [{index, chartDiv, chart, series, symbol, timeframe, trustEl, input, tfSel, data}]
    this._saveTimer = null;
    this._gridSyncing = false; // فلگ بازگشت (re-entrancy) — الگوی _syncScales
    this._primaryRangeBound = false;
    this._primaryCrosshairBound = false;
  }

  /** راه‌اندازی — false یعنی کانتینر نیست و ماژول no-op می‌ماند (تدافعی) */
  init() {
    const root = document.getElementById(this.rootId);
    if (!root) return false;
    this.state = this._loadState().state;
    this._injectStyle();
    this._renderBar();
    this._applyLayout(this.state.layout);
    window.addEventListener("resize", () => this._resizeCharts());
    return true;
  }

  /* ---------------- ماندگاری (fail-closed) ---------------- */

  _storage() {
    try {
      if (typeof window !== "undefined" && window.localStorage) return window.localStorage;
    } catch (err) { /* در بافت‌های محدودشده localStorage ممکن است throw کند */ }
    return null;
  }

  _loadState() {
    return gridLoadState(this._storage());
  }

  /** ذخیره با تأخیر 600ms — هر دنباله تغییر فقط یک نوشتن؛ هرگز UI را نمی‌شکند */
  _queueSave() {
    if (this._saveTimer) clearTimeout(this._saveTimer);
    this._saveTimer = setTimeout(() => {
      this._saveTimer = null;
      try {
        gridSaveState(this._storage(), {
          layout: this.state.layout,
          sync: { ...this.state.sync },
          panes: (this.panes.length
            ? this.panes.map((p) => ({ symbol: p.symbol, timeframe: p.timeframe }))
            : this.state.panes || []).slice(0, GRID_MAX_PANES),
        });
      } catch (e) { /* مسکوت — ماندگاری حیاتی نیست */ }
    }, GRID_SAVE_DEBOUNCE_MS);
  }

  /* ---------------- نوار کنترل (#cpGridBar — تدافعی) ---------------- */

  _injectStyle() {
    if (document.getElementById(GRID_STYLE_ID)) return;
    /* سبک حداقلی درون‌ماژول — فایل CSS جدید ممنوع است؛ کلاس‌های app.css
       (text-input/btn/muted/cp-badge) بازاستفاده می‌شوند و این‌ها فقط چیدمانگرند */
    const st = document.createElement("style");
    st.id = GRID_STYLE_ID;
    st.textContent = [
      ".cp-grid-panes { display: grid; gap: .6rem; margin-top: .6rem; }",
      ".cp-grid-cols-1 { grid-template-columns: 1fr; }",
      ".cp-grid-cols-3 { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }",
      ".cp-grid-pane { border: 1px solid var(--border); border-radius: 12px; padding: .5rem; background: var(--surface2); }",
      ".cp-grid-pane-head { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }",
      ".cp-grid-pane-head .text-input { max-width: 150px; }",
      ".cp-grid-note { font-size: .72rem; margin-top: .25rem; }",
      ".cp-grid-chart { height: 240px; margin-top: .3rem; }",
    ].join("\n");
    document.head.appendChild(st);
  }

  _renderBar() {
    const bar = document.getElementById(this.barId);
    if (!bar) return; // تدافعی: نوار کنترل نیست → گرید بدون UI می‌ماند (چیدمان ۱ همچنان بی‌اثر)
    bar.textContent = "";
    const lbl = document.createElement("span");
    lbl.className = "muted";
    lbl.textContent = "گرید چندنموداری:";
    bar.appendChild(lbl);
    for (const n of GRID_LAYOUTS) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn tiny";
      b.dataset.glayout = String(n);
      b.title = `چیدمان ${GRID_LAYOUT_LABELS_FA[n]} پنلی`;
      b.textContent = GRID_LAYOUT_LABELS_FA[n];
      b.addEventListener("click", () => this.setLayout(n));
      bar.appendChild(b);
    }
    for (const key of GRID_SYNC_KEYS) {
      const t = document.createElement("button");
      t.type = "button";
      t.className = "btn tiny";
      t.dataset.gsync = key;
      t.title = "تغییر وضعیت این همگام‌سازی";
      t.textContent = GRID_SYNC_LABELS[key];
      t.addEventListener("click", () => this.toggleSync(key));
      bar.appendChild(t);
    }
    const note = document.createElement("span");
    note.className = "muted cp-grid-note";
    note.textContent = "پنل‌های فرعی در نمای خطی close — چارت اصلی کندل می‌ماند";
    bar.appendChild(note);
    this._syncBarUI();
  }

  _syncBarUI() {
    const bar = document.getElementById(this.barId);
    if (!bar) return;
    bar.querySelectorAll("button[data-glayout]").forEach((b) => {
      const on = Number(b.dataset.glayout) === this.state.layout;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    bar.querySelectorAll("button[data-gsync]").forEach((b) => {
      const on = !!this.state.sync[b.dataset.gsync];
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  /* ---------------- چیدمان و ساخت پنل‌ها ---------------- */

  setLayout(n) {
    if (!GRID_LAYOUTS.includes(n)) return;
    this.state.layout = n;
    this._applyLayout(n);
    this._queueSave();
  }

  _applyLayout(n) {
    const root = document.getElementById(this.rootId);
    if (!root) return; // تدافعی: کانتینر نیست → هیچ
    root.textContent = "";
    this._destroyPanes();
    if (n === 1) {
      /* چیدمان ۱: بدون پنل فرعی، بدون هیچ DOM اضافه — صفر تداخل با چارت تک‌نمودی */
      this._syncBarUI();
      this._bindPrimarySync();
      return;
    }
    const count = n === 2 ? 1 : 3;
    const saved = Array.isArray(this.state.panes) ? this.state.panes.slice(0, count) : [];
    while (saved.length < count) saved.push(null);
    const primary = this._primarySnapshot();
    const wrap = document.createElement("div");
    wrap.className = "cp-grid-panes " + (count === 1 ? "cp-grid-cols-1" : "cp-grid-cols-3");
    root.appendChild(wrap);
    for (let i = 0; i < count; i++) {
      /* نماد پنل: اگر «همگام‌سازی نماد» روشن است (پیش‌فرض) نماد فعال اصلی در همین
         لحظه اعمال می‌شود؛ وگرنه پیکربندی ذخیره‌شده پنل (seed اولیه هم از اصلی) */
      const sym = this.state.sync.symbol_follow && primary.symbol
        ? primary.symbol
        : (saved[i]?.symbol || primary.symbol || "");
      const tf = saved[i]?.timeframe || primary.timeframe || "1m";
      this._buildPane(wrap, i, sym, tf);
    }
    this.state.panes = this.panes.map((p) => ({ symbol: p.symbol, timeframe: p.timeframe }));
    this._syncBarUI();
    this._resizeCharts();
    this._bindPrimarySync();
  }

  _buildPane(wrap, index, symbol, timeframe) {
    const pane = document.createElement("div");
    pane.className = "cp-grid-pane";
    pane.dataset.pane = String(index);

    const head = document.createElement("div");
    head.className = "cp-grid-pane-head";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "text-input cp-grid-sym";
    input.placeholder = "نماد پنل فرعی… مثلاً فملی";
    input.value = symbol || "";
    input.setAttribute("aria-label", "نماد پنل فرعی گرید");
    const sel = document.createElement("select");
    sel.className = "text-input cp-grid-tf";
    sel.setAttribute("aria-label", "تایم‌فریم پنل فرعی");
    for (const tf of GRID_TIMEFRAMES) {
      const o = document.createElement("option");
      o.value = tf;
      o.textContent = tf;
      if (tf === timeframe) o.selected = true;
      sel.appendChild(o);
    }
    const trust = document.createElement("span");
    trust.className = "cp-badge cp-grid-trust";
    trust.textContent = "منبع: —"; // تا پاسخ سرور برسد — هیچ برچسبی ساخته نمی‌شود
    head.appendChild(input);
    head.appendChild(sel);
    head.appendChild(trust);

    const note = document.createElement("div");
    note.className = "cp-grid-note muted";
    note.textContent = "پنل فرعی: نمای خطی close — کندل اصلی در نمای اصلی";

    const chartDiv = document.createElement("div");
    chartDiv.className = "cp-grid-chart";

    pane.appendChild(head);
    pane.appendChild(note);
    pane.appendChild(chartDiv);
    wrap.appendChild(pane);

    const pal = chartPalette();
    const chart = LightweightCharts.createChart(chartDiv, {
      width: chartDiv.clientWidth || 320,
      height: 240,
      layout: { background: { color: pal.bg }, textColor: pal.text, fontFamily: "Vazirmatn, sans-serif" },
      grid: { vertLines: { color: pal.grid }, horzLines: { color: pal.grid } },
      rightPriceScale: { borderColor: pal.axis },
      timeScale: { borderColor: pal.axis, timeVisible: true },
      crosshair: { mode: 1 },
      localization: { locale: "fa-IR" },
    });
    const series = chart.addLineSeries({ color: "rgba(34,211,238,0.9)", lineWidth: 2, priceLineVisible: false });

    const rec = {
      index,
      chartDiv,
      chart,
      series,
      symbol: String(symbol || "").trim(),
      timeframe: GRID_TIMEFRAMES.includes(timeframe) ? timeframe : "1m",
      trustEl: trust,
      input,
      tfSel: sel,
      data: [],
    };

    const go = () => this._loadPane(rec, input.value);
    input.addEventListener("change", go);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); go(); } });
    sel.addEventListener("change", () => this._loadPane(rec, rec.symbol));

    this.panes.push(rec);
    this._bindPaneSync(rec);
    if (rec.symbol) this._loadPane(rec, rec.symbol);
  }

  /** بارگذاری سری خطی close پنل فرعی — فقط از core/api.js، بدون polling */
  async _loadPane(rec, symbol) {
    const sym = String(symbol || "").trim().slice(0, GRID_SYMBOL_MAX_LEN);
    if (!sym || !rec) return;
    rec.symbol = sym;
    rec.timeframe = GRID_TIMEFRAMES.includes(rec.tfSel?.value) ? rec.tfSel.value : rec.timeframe;
    if (rec.input && rec.input.value !== sym) rec.input.value = sym;
    try {
      const res = await api(
        "/api/v10/chartpro/" + encodeURIComponent(rec.symbol) +
        "?timeframe=" + encodeURIComponent(rec.timeframe) + "&limit=" + GRID_PANE_LIMIT
      );
      const closes = (Array.isArray(res?.ohlcv) ? res.ohlcv : [])
        .filter((c) => c && c.time != null && c.close != null && isFinite(+c.close))
        .map((c) => ({ time: c.time, value: Number(c.close) }));
      rec.data = closes;
      rec.series.setData(closes);
      try { rec.chart.timeScale().fitContent(); } catch (e) { /* ignore */ }
      this._setPaneTrust(rec, res?.data_trust, res?.source, res?.trust_level);
      this.state.panes = this.panes.map((p) => ({ symbol: p.symbol, timeframe: p.timeframe }));
      this._queueSave();
    } catch (e) {
      /* خطا صادقانه فقط در خود پنل — بدون هیچ داده یا برچسب ساختگی */
      rec.data = [];
      try { rec.series.setData([]); } catch (err) { /* ignore */ }
      if (rec.trustEl) {
        rec.trustEl.classList.remove("live");
        rec.trustEl.textContent = "داده پنل فرعی دریافت نشد";
      }
    }
  }

  /** برچسب اعتماد پنل — عین قواعد cpSourceBadge چارت اصلی؛ هرگز برچسب نمی‌سازد */
  _setPaneTrust(rec, dataTrust, source, trustLevel) {
    if (!rec || !rec.trustEl) return;
    const dt = (typeof dataTrust === "object" && dataTrust) || {};
    const state = String(dt.state || trustLevel || "unknown").toLowerCase();
    /* verified live فقط با هر سه نشانه — عین قاعده chart_pro؛ وگرنه هرگز «لایو» نمایش داده نمی‌شود */
    const verifiedLive = state === "live" && dt.is_live === true && dt.live_verified === true;
    const fa = {
      synthetic: "SYNTHETIC (شبیه‌سازی‌شده)",
      mock: "MOCK (دمو)",
      stale: "STALE (قدیمی)",
      unavailable: "UNAVAILABLE (ناموجود)",
      mixed: "MIXED (ترکیبی)",
    }[state];
    rec.trustEl.classList.remove("synthetic", "live");
    if (verifiedLive) {
      rec.trustEl.classList.add("live");
      rec.trustEl.textContent = `منبع: LIVE (تأییدشده) · ${source || state}`;
    } else {
      rec.trustEl.classList.add("synthetic");
      rec.trustEl.textContent = `منبع: ${fa || state.toUpperCase() + " (تأییدنشده)"}${source ? " · " + source : ""}`;
    }
  }

  _destroyPanes() {
    for (const p of this.panes) {
      try { p.chart.remove(); } catch (e) { /* ignore */ }
    }
    this.panes = [];
  }

  _resizeCharts() {
    for (const p of this.panes) {
      try {
        p.chart.applyOptions({ width: p.chartDiv.clientWidth || 320, height: 240 });
      } catch (e) { /* ignore */ }
    }
  }

  /* ---------------- همگام‌سازی‌ها ---------------- */

  /** نماد/تایم‌فریم فعال چارت اصلی — singleton از chart_pro؛ بدون تایمر/شنونده */
  _primarySnapshot() {
    let symbol = "";
    let timeframe = "";
    try {
      const s = getActiveChartPro ? getActiveChartPro() : null;
      if (s) {
        symbol = String(s.symbol || "").trim();
        timeframe = String(s.timeframe || "").trim();
      }
    } catch (e) { /* ignore */ }
    if (!symbol) {
      const input = document.getElementById("cpSymbolInput");
      symbol = input ? String(input.value || "").trim() : "";
    }
    return { symbol, timeframe: GRID_TIMEFRAMES.includes(timeframe) ? timeframe : "1m" };
  }

  _primaryChart() {
    try {
      const s = getActiveChartPro ? getActiveChartPro() : null;
      return s && s.chart ? s.chart : null;
    } catch (e) {
      return null;
    }
  }

  /** اتصال یک‌باره به چارت اصلی — اگر singleton آماده باشد؛ در تعامل‌های بعدی دوباره تلاش می‌شود */
  _bindPrimarySync() {
    const primary = this._primaryChart();
    if (!primary) return;
    if (!this._primaryRangeBound) {
      this._primaryRangeBound = true;
      try {
        primary.timeScale().subscribeVisibleLogicalRangeChange((range) => {
          if (!this.state.sync.range || this._gridSyncing || !this.panes.length) return;
          this._gridSyncing = true;
          try {
            for (const p of this.panes) p.chart.timeScale().setVisibleLogicalRange(range);
          } catch (e) { /* ignore */ }
          this._gridSyncing = false;
        });
      } catch (e) { /* ignore */ }
    }
    if (!this._primaryCrosshairBound) {
      this._primaryCrosshairBound = true;
      try {
        primary.subscribeCrosshairMove((param) => this._syncCrosshair(param));
      } catch (e) { /* ignore */ }
    }
  }

  /** همگام‌سازی بازهٔ هر پنل فرعی با بقیه (دوسویه، فلگ بازگشت مثل _syncScales) */
  _bindPaneSync(rec) {
    try {
      rec.chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!this.state.sync.range || this._gridSyncing) return;
        this._gridSyncing = true;
        try {
          const primary = this._primaryChart();
          if (primary) primary.timeScale().setVisibleLogicalRange(range);
          for (const other of this.panes) {
            if (other !== rec) other.chart.timeScale().setVisibleLogicalRange(range);
          }
        } catch (e) { /* ignore */ }
        this._gridSyncing = false;
      });
    } catch (e) { /* ignore */ }
  }

  /** همگام‌سازی کراس‌هیر اصلی → پنل‌ها (امکان‌سنجی API — توضیح بالای فایل) */
  _syncCrosshair(param) {
    if (!this.state.sync.crosshair) return;
    for (const p of this.panes) {
      try {
        if (!param || param.time == null || !param.point) {
          if (typeof p.chart.clearCrosshairPosition === "function") p.chart.clearCrosshairPosition();
          continue;
        }
        const pt = (p.data || []).find((c) => gridSameTime(c && c.time, param.time));
        if (!pt) continue; // این زمان در داده این پنل نیست — هیچ مقدار ساختگی
        if (typeof p.chart.setCrosshairPosition === "function") {
          p.chart.setCrosshairPosition(pt.value, param.time, p.series);
        }
      } catch (e) { /* ignore */ }
    }
  }

  toggleSync(key) {
    if (!GRID_SYNC_KEYS.includes(key)) return;
    this.state.sync[key] = !this.state.sync[key];
    if (key === "crosshair" && !this.state.sync.crosshair) {
      for (const p of this.panes) {
        try {
          if (typeof p.chart.clearCrosshairPosition === "function") p.chart.clearCrosshairPosition();
        } catch (e) { /* ignore */ }
      }
    }
    if (key === "symbol_follow" && this.state.sync.symbol_follow) {
      /* محدودیت مستندشده (صداقت): دنبال‌کردنِ نماد اصلی «خودکار» نیست — بدون
         شنونده/تایمر پس‌زمینه، نماد فعال اصلی فقط در همین لحظه تعامل کاربر
         روی همه پنل‌های فرعی اعمال می‌شود. */
      const primary = this._primarySnapshot();
      if (primary.symbol) {
        for (const p of this.panes) {
          if (p.symbol !== primary.symbol) this._loadPane(p, primary.symbol);
        }
      }
    }
    this._syncBarUI();
    this._queueSave();
  }
}

/* ============================ بایند-on-demand (الگوی chart_pro) ============================ */

let instance = null;

function ensureChartGrid() {
  if (instance) return;
  /* تدافعی: بدون کانتینر (#cpGridRoot) هیچ — مرحله ادغام بعداً اضافه می‌کند */
  if (document.getElementById("cpGridRoot") === null) return;
  instance = new ChartGrid();
  /* برای command_palette — بدون این، اکشن‌های گرید در پالت فهرست نمی‌شوند */
  window.chartGrid = instance;
  instance.init();
}

function bindChartGridTab() {
  if (instance) return;
  // فعال‌سازی با تغییر کلاس پنل (MutationObserver — مثل chart_pro/forex)
  const observer = new MutationObserver(() => {
    const panel = document.getElementById("tab-chartpro");
    if (panel && panel.classList.contains("active")) ensureChartGrid();
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
  // و با کلیک روی دکمه تب (دپ‌لینک #/chartpro از روتر main.js هم همین کلیک را می‌زند)
  document.querySelectorAll('[data-tab="chartpro"]').forEach((btn) => {
    btn.addEventListener("click", () => setTimeout(ensureChartGrid, 100));
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindChartGridTab);
  else bindChartGridTab();
}
