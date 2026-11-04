/**
 * chart_pro.js — WS-10 / CH-3..CH-8 «چارت حرفه‌ای» (کلاس فرازچارت / TradingView-Lite)
 *
 * - کندل‌استیک + حجم (Lightweight Charts v4.2.0 وندورشده — بدون وابستگی npm جدید)
 * - اندیکاتورها: MA20 / MA50 / EMA20 / Bollinger (اورلی روی قیمت) + RSI14 / MACD
 *   (پنل اسیلاتور جداگانه — نمونه کوچک LightweightCharts داخل کانتینر خود این ماژول؛
 *   API ماژول indicator_pane.js با شکل داده v10 هم‌خوانی نداشت: کلیدهای macd.hist/rsi14/
 *   bollinger.mid در قرارداد v10 با macd.histogram/rsi/bollinger.basis آن فرق دارد)
 * - ابزار رسم روی canvas اورلی: خط روند، خط افقی، فیبوناچی + حذف/پاک‌سازی
 * - هشدار قیمی محلی (createPriceLine) — فقط درون‌محصولی (R-9: بدون هیچ کانال خارجی)
 * - ذخیره/بارگذاری/خروجی JSON تحلیل‌ها (localStorage)
 * - داده فقط از core/api.js — هیچ fetch دستی (قرارداد اجباری)
 * - برچسب صادقانه منبع داده: هرگز SYNTHETIC را «لایو» نشان نمی‌دهد
 */
import { api, toast } from "../../core/api.js";
import { esc } from "../../core/format.js";
import { chartPalette } from "../utils/chart_theme.js";
import { loadWorkspace, saveWorkspace } from "../workspace.js"; // WDA-1: ماندگاری فضای کاری

/* رنگ‌های ثابت ابزار رسم — طبق مشخصه WS-10 */
const DRAW_COLORS = {
  trend: "#2962FF",
  hline: "#FF9800",
  fib: "#9C27B0",
  alert: "#E91E63",
};

const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
const OSC_COLORS = {
  macd: "#22d3ee",
  signal: "#fbbf24",
  histUp: "rgba(52,211,153,0.65)",
  histDn: "rgba(251,113,133,0.65)",
  rsi: "#a78bfa",
  boll: "#818cf8",
  bollBasis: "#fbbf24",
};

const LS_LAYOUTS = "radar_chartpro_layouts";
const lsKeyDrawings = (sym) => `radar_chartpro_drawings_${sym}`;
const lsKeyAlerts = (sym) => `radar_chartpro_alerts_${sym}`;

function lsGet(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}
function lsSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

function fmtPrice(p) {
  if (p == null || Number.isNaN(+p)) return "—";
  const abs = Math.abs(+p);
  const dec = abs >= 1000 ? 0 : abs >= 100 ? 1 : abs >= 1 ? 2 : 4;
  return Number(p).toLocaleString("fa-IR", { maximumFractionDigits: dec });
}

/** نقاط اندیکاتور v10 ممکن است null باشند — قبل از setData پاک شود */
function cleanPoints(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.filter((p) => p && p.time != null && p.value != null && isFinite(+p.value));
}

export class ChartProChart {
  constructor(opts = {}) {
    this.containerId = opts.containerId || "cpChart";
    this.panelId = opts.panelId || "tab-chartpro";
    this.oscContainerId = opts.oscContainerId || "cpOscChart";
    this.symbol = opts.symbol || "فملی";
    this.timeframe = opts.timeframe || "1m";
    this.limit = 500;

    this.onIndicators = { ma20: true, ma50: true, ema20: false, bb: false, rsi: false, macd: false };

    this.chart = null;
    this.candleSeries = null;
    this.volumeSeries = null;
    this.lineSeries = {}; // ma20/ma50/ema20/bbU/bbM/bbL
    this.oscChart = null;
    this.oscSeries = []; // [{key, series, kind}]
    this._syncing = false;

    this.currentData = [];
    this.indicators = null;
    this.universe = [];

    /* ابزار رسم */
    this.drawState = { tool: null, points: [], drawings: [] };
    this.canvas = null;
    this.ctx = null;
    this._ro = null;

    /* هشدار قیمتی محلی */
    this.alerts = [];
    this.alertLines = [];
    this._prevClose = null;

    this._poll = null;
    this._activated = false;
    this._alertSymbol = null;
    this._oscKey = "";
  }

  /* ============================ چارت اصلی ============================ */

  async init() {
    const el = document.getElementById(this.containerId);
    if (!el || this.chart) return;
    const wrap = el.parentElement; // .cp-chart-wrap
    this._wrap = wrap || el;

    /* WDA-1: بازیابی فضای کاری ذخیره‌شده (نماد/تایم‌فریم/اندیکاتورها) —
       بازیابی هرگز شکست سخت ندارد؛ خروجی نامعتبر فقط به پیش‌فرض می‌رسد */
    const _ws = loadWorkspace();
    if (_ws && _ws.payload) {
      if (_ws.payload.symbol) this.symbol = _ws.payload.symbol;
      if (_ws.payload.timeframe) this.timeframe = _ws.payload.timeframe;
      if (_ws.payload.indicators) this.onIndicators = { ...this.onIndicators, ..._ws.payload.indicators };
      /* همگام‌سازی UI سگمنت‌ها با وضعیت بازیابی‌شده */
      document.querySelectorAll("#cpTfSeg button[data-tf]").forEach((b) => {
        b.classList.toggle("active", b.dataset.tf === this.timeframe);
      });
      document.querySelectorAll("#cpIndSeg button[data-ind]").forEach((b) => {
        b.classList.toggle("active", !!this.onIndicators[b.dataset.ind]);
      });
    }
    if (_ws && !_ws.ok && _ws.reason !== "storage_unavailable") {
      console.warn("WDA-1 فضای کاری:", _ws.reason, (_ws.issues || []).join("؛ "));
    }

    const pal = chartPalette();
    el.innerHTML = "";
    this.chart = LightweightCharts.createChart(el, {
      width: el.clientWidth || 800,
      height: el.clientHeight || 440,
      layout: { background: { color: pal.bg }, textColor: pal.text, fontFamily: "Vazirmatn, sans-serif" },
      grid: { vertLines: { color: pal.grid }, horzLines: { color: pal.grid } },
      rightPriceScale: { borderColor: pal.axis, scaleMargins: { top: 0.1, bottom: 0.22 } },
      timeScale: { borderColor: pal.axis, timeVisible: true, rightOffset: 6 },
      crosshair: { mode: 1 },
      localization: { locale: "fa-IR" },
    });

    this.candleSeries = this.chart.addCandlestickSeries({
      upColor: pal.up, downColor: pal.down, borderVisible: false,
      wickUpColor: pal.up, wickDownColor: pal.down,
    });

    this.volumeSeries = this.chart.addHistogramSeries({
      priceFormat: { type: "volume" }, priceScaleId: "", priceLineVisible: false,
    });
    this.volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });

    this.lineSeries.ma20 = this.chart.addLineSeries({ color: "rgba(251,191,36,0.9)", lineWidth: 1.5, priceLineVisible: false, title: "MA20" });
    this.lineSeries.ma50 = this.chart.addLineSeries({ color: "rgba(129,140,248,0.9)", lineWidth: 1.5, priceLineVisible: false, title: "MA50" });
    this.lineSeries.ema20 = this.chart.addLineSeries({ color: "rgba(34,211,238,0.85)", lineWidth: 1, lineStyle: 2, priceLineVisible: false, title: "EMA20" });
    this.lineSeries.bbU = this.chart.addLineSeries({ color: OSC_COLORS.boll, lineWidth: 1, priceLineVisible: false, title: "BB+", lineStyle: 1 });
    this.lineSeries.bbM = this.chart.addLineSeries({ color: OSC_COLORS.bollBasis, lineWidth: 1, lineStyle: 2, priceLineVisible: false, title: "BB mid" });
    this.lineSeries.bbL = this.chart.addLineSeries({ color: OSC_COLORS.boll, lineWidth: 1, priceLineVisible: false, title: "BB-", lineStyle: 1 });

    /* اورلی رسم — canvas هم‌اندازه با کانتینر چارت */
    this._buildCanvas(wrap || el);

    /* ریسایز */
    if (typeof ResizeObserver !== "undefined") {
      this._ro = new ResizeObserver(() => {
        try {
          this.chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
          this.redraw();
        } catch (e) { /* ignore */ }
      });
      this._ro.observe(el);
    }
    window.addEventListener("resize", () => this.redraw());

    /* بازرسم نقاشی با هر اسکرول/زوم */
    try {
      this.chart.timeScale().subscribeVisibleLogicalRangeChange(() => this.redraw());
    } catch (e) { /* ignore */ }

    this.bindUI();
    this.startPolling();

    await Promise.all([this.loadUniverse(), this.loadAndRender(this.symbol, this.timeframe)]);
  }

  _buildCanvas(wrap) {
    if (!wrap || this.canvas) return;
    this.canvas = document.createElement("canvas");
    this.canvas.className = "cp-canvas";
    this.canvas.setAttribute("aria-label", "بوم ابزار رسم چارت حرفه‌ای");
    wrap.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d");
    this.canvas.addEventListener("click", (e) => this._onCanvasClick(e));
    this.canvas.addEventListener("mousemove", (e) => this._onCanvasMove(e));
  }

  /* ============================ UI بایند ============================ */

  bindUI() {
    if (this._bound) return;
    this._bound = true;

    const $ = (id) => document.getElementById(id);

    /* نماد */
    const symInput = $("cpSymbolInput");
    if (symInput) {
      const go = () => {
        const v = (symInput.value || "").trim();
        if (v) this.loadAndRender(v, this.timeframe);
      };
      symInput.addEventListener("change", go);
      symInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); go(); } });
    }

    /* تایم‌فریم */
    const tfSeg = $("cpTfSeg");
    if (tfSeg) {
      tfSeg.querySelectorAll("button[data-tf]").forEach((btn) => {
        btn.addEventListener("click", () => {
          tfSeg.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          this.loadAndRender(this.symbol, btn.dataset.tf);
        });
      });
    }

    /* اندیکاتورها */
    const indSeg = $("cpIndSeg");
    if (indSeg) {
      indSeg.querySelectorAll("button[data-ind]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const key = btn.dataset.ind;
          this.onIndicators[key] = !this.onIndicators[key];
          btn.classList.toggle("active", this.onIndicators[key]);
          if (key === "rsi" || key === "macd") this._renderOsc();
          else this._applyIndicators();
          this._queueWorkspaceSave(); // WDA-1: وضعیت اندیکاتورها ذخیره شود
        });
      });
    }

    /* ابزار رسم */
    const drawSeg = $("cpDrawSeg");
    if (drawSeg) {
      drawSeg.querySelectorAll("button[data-draw]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const t = btn.dataset.draw;
          const same = this.drawState.tool === t;
          drawSeg.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
          this.drawState.tool = same ? null : t;
          this.drawState.points = [];
          if (this.drawState.tool) btn.classList.add("active");
          this.canvas?.classList.toggle("armed", !!this.drawState.tool);
          this._setStatus(this.drawState.tool
            ? { trend: "خط روند: دو نقطه روی چارت کلیک کنید",
                hline: "خط افقی: یک نقطه (قیمت) کلیک کنید",
                fib: "فیبوناچی: دو نقطه (کف و سقف) کلیک کنید",
                delete: "حذف: روی خط موردنظر کلیک کنید" }[this.drawState.tool] || ""
            : "");
          this.redraw();
        });
      });
    }
    $("cpClearDraw")?.addEventListener("click", () => {
      this.drawState.drawings = [];
      this.drawState.points = [];
      this._saveDrawings();
      this.redraw();
      toast("همه رسم‌های این نماد پاک شد", "info");
    });

    /* هشدار قیمتی */
    $("cpAddAlert")?.addEventListener("click", () => this._addAlertFromInput());

    /* ذخیره/بارگذاری/خروجی */
    $("cpSaveLayout")?.addEventListener("click", () => this.saveLayout());
    $("cpLoadLayout")?.addEventListener("click", () => this.loadLayout());
    $("cpExportLayouts")?.addEventListener("click", () => this.exportLayouts());
  }

  /* ============================ داده ============================ */

  async loadUniverse() {
    const body = document.getElementById("cpWatchBody");
    try {
      const res = await api("/api/v10/chartpro/universe");
      const list = Array.isArray(res) ? res : (Array.isArray(res?.symbols) ? res.symbols : []);
      this.universe = list.map((it) => ({
        symbol: String(it.symbol ?? it.l18 ?? it.name ?? "").trim(),
        name: String(it.name_fa ?? it.l30 ?? it.name ?? it.l18 ?? ""),
        price: it.price ?? it.last ?? it.last_price ?? null,
        change_pct: Number(it.change_pct ?? it.plp ?? it.change ?? 0) || 0,
      })).filter((it) => it.symbol);
      this._fillDatalist();
      this._renderWatchlist();
    } catch (e) {
      if (body) body.innerHTML = `<div class="cp-watch-empty muted">فهرست نمادها از سرور دریافت نشد</div>`;
    }
  }

  _fillDatalist() {
    const dl = document.getElementById("cpSymbolList");
    if (!dl) return;
    dl.innerHTML = this.universe
      .map((it) => `<option value="${esc(it.symbol)}">${esc(it.name || it.symbol)}</option>`)
      .join("");
  }

  _renderWatchlist() {
    const body = document.getElementById("cpWatchBody");
    if (!body) return;
    if (!this.universe.length) {
      body.innerHTML = `<div class="cp-watch-empty muted">فهرست نمادها خالی است</div>`;
      return;
    }
    body.innerHTML = this.universe.map((it) => {
      const cls = it.change_pct > 0 ? "up" : it.change_pct < 0 ? "down" : "flat";
      const active = it.symbol === this.symbol ? " active" : "";
      const sign = it.change_pct > 0 ? "+" : "";
      return `<button class="cp-watch-row${active}" data-cp-sym="${esc(it.symbol)}" title="${esc(it.name)}">
        <span class="cp-w-sym">${esc(it.symbol)}</span>
        <span class="cp-w-price">${fmtPrice(it.price)}</span>
        <span class="cp-w-chg ${cls}">${sign}${it.change_pct.toFixed(2)}٪</span>
      </button>`;
    }).join("");
    body.querySelectorAll("[data-cp-sym]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const input = document.getElementById("cpSymbolInput");
        if (input) input.value = btn.dataset.cpSym;
        this.loadAndRender(btn.dataset.cpSym, this.timeframe);
      });
    });
  }

  /**
   * بارگذاری و رندر نماد/تایم‌فریم.
   * @param {string} symbol
   * @param {string} timeframe
   * @param {{fit?: boolean}} [opts] — fit=false در رفرش سبک ۱۰ ثانیه‌ای (زوم کاربر حفظ می‌شود)
   */
  async loadAndRender(symbol, timeframe, opts = {}) {
    const fit = opts.fit !== false;
    this.symbol = String(symbol || this.symbol);
    this.timeframe = String(timeframe || this.timeframe);
    try {
      const res = await api(
        "/api/v10/chartpro/" + encodeURIComponent(this.symbol) +
        "?timeframe=" + encodeURIComponent(this.timeframe) + "&limit=" + this.limit
      );
      this.currentData = Array.isArray(res?.ohlcv) ? res.ohlcv : [];
      if (!this.currentData.length) {
        this._setStatus("برای این نماد/تایم‌فریم کندلی برگردانده نشد");
        return;
      }

      /* اندیکاتورها (نقطه‌ی ضعف شبکه — خطا جدی نیست، چارت بدون اندیکاتور می‌ماند) */
      try {
        this.indicators = await api(
          "/api/v10/chartpro/" + encodeURIComponent(this.symbol) + "/indicators" +
          "?timeframe=" + encodeURIComponent(this.timeframe) + "&limit=" + this.limit
        );
      } catch (e) {
        this.indicators = null;
      }

      this.candleSeries.setData(this.currentData);
      const pal = chartPalette();
      const ind = this.indicators || {};
      this.volumeSeries.setData(
        Array.isArray(ind.volume) && ind.volume.length
          ? ind.volume
          : this.currentData.map((c) => ({ time: c.time, value: c.volume || 0, color: c.close >= c.open ? pal.volUp : pal.volDn }))
      );
      this._applyIndicators();
      this._renderOsc();

      if (fit) this.chart.timeScale().fitContent();

      /* رسم‌های ذخیره‌شده و هشدارهای قیمتی این نماد */
      this.drawState.drawings = lsGet(lsKeyDrawings(this.symbol), []);
      this.drawState.points = [];
      this._loadAlerts(this.symbol);
      this.redraw();
      this._checkAlerts();

      this._setBadge(res.data_trust, res.source, res.trust_level);
      const t = new Date().toLocaleTimeString("fa-IR");
      this._setStatus(`${this.symbol} · ${this.timeframe} · ${this.currentData.length} کندل · به‌روزرسانی ${t}`);
      const input = document.getElementById("cpSymbolInput");
      if (input && input.value !== this.symbol) input.value = this.symbol;
      document.querySelectorAll("#cpWatchBody [data-cp-sym]").forEach((b) => {
        b.classList.toggle("active", b.dataset.cpSym === this.symbol);
      });
      this._queueWorkspaceSave(); // WDA-1: نماد/تایم‌فریم فعال ذخیره شود
    } catch (e) {
      this._setStatus(`خطای بارگذاری ${this.symbol}: ${String(e && e.message ? e.message : e).slice(0, 80)}`);
    }
  }

  _applyIndicators() {
    const ind = this.indicators || {};
    const bb = ind.bollinger || {};
    const put = (key, arr) => {
      try { this.lineSeries[key].setData(cleanPoints(arr)); } catch (e) { /* ignore */ }
    };
    put("ma20", this.onIndicators.ma20 ? ind.ma20 : []);
    put("ma50", this.onIndicators.ma50 ? ind.ma50 : []);
    put("ema20", this.onIndicators.ema20 ? ind.ema20 : []);
    put("bbU", this.onIndicators.bb ? bb.upper : []);
    put("bbM", this.onIndicators.bb ? bb.mid : []);
    put("bbL", this.onIndicators.bb ? bb.lower : []);
  }

  /* ---------------- پنل اسیلاتور (RSI/MACD) ----------------
   * پیاده‌سازی: نمونه‌ی کوچک دوم LightweightCharts داخل کانتینر خود ماژول
   * (#cpOscChart) با همگام‌سازی دوسویه اسکرول/زوم — ماژول indicator_pane.js
   * استفاده نشد چون شکل داده‌اش (macd.histogram/rsi/bollinger.basis) با
   * قرارداد v10 (macd.hist/rsi14/bollinger.mid) فرق دارد.
   */
  _renderOsc() {
    const container = document.getElementById(this.oscContainerId);
    if (!container) return;
    const wantRsi = !!this.onIndicators.rsi;
    const wantMacd = !!this.onIndicators.macd;
    const key = (wantRsi ? "1" : "0") + (wantMacd ? "1" : "0");

    if (!wantRsi && !wantMacd) {
      container.style.display = "none";
      this._oscKey = "00";
      this.oscSeries.forEach(({ series }) => { try { this.oscChart && this.oscChart.removeSeries(series); } catch (e) {} });
      this.oscSeries = [];
      return;
    }

    if (!this.oscChart) {
      const pal = chartPalette();
      this.oscChart = LightweightCharts.createChart(container, {
        height: 150,
        layout: { background: { color: pal.bg }, textColor: pal.text, fontFamily: "Vazirmatn, sans-serif" },
        grid: { vertLines: { color: pal.grid }, horzLines: { color: pal.grid } },
        rightPriceScale: { borderColor: pal.axis, scaleMargins: { top: 0.12, bottom: 0.12 } },
        timeScale: { borderColor: pal.axis, timeVisible: true },
        localization: { locale: "fa-IR" },
      });
      container.style.height = "150px";
      if (typeof ResizeObserver !== "undefined") {
        this._oscRo = new ResizeObserver(() => {
          try { this.oscChart.applyOptions({ width: container.clientWidth, height: container.clientHeight }); } catch (e) {}
        });
        this._oscRo.observe(container);
      }
      this._syncScales();
    }

    /* سری‌ها فقط وقتی ترکیب RSI/MACD عوض شد از نو ساخته می‌شوند (رفرش ۱۰ث سبک بماند) */
    if (this._oscKey !== key) {
      this.oscSeries.forEach(({ series }) => { try { this.oscChart.removeSeries(series); } catch (e) {} });
      this.oscSeries = [];
      if (wantMacd) {
        const hist = this.oscChart.addHistogramSeries({ priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false });
        const ml = this.oscChart.addLineSeries({ color: OSC_COLORS.macd, lineWidth: 1.5, priceLineVisible: false, title: "MACD" });
        const sl = this.oscChart.addLineSeries({ color: OSC_COLORS.signal, lineWidth: 1.2, priceLineVisible: false, title: "Signal" });
        this.oscSeries.push({ key: "hist", series: hist }, { key: "macd", series: ml }, { key: "signal", series: sl });
      }
      if (wantRsi) {
        const rs = this.oscChart.addLineSeries({ color: OSC_COLORS.rsi, lineWidth: 1.6, priceLineVisible: false, title: "RSI14" });
        [70, 30].forEach((p) => {
          try {
            rs.createPriceLine({ price: p, color: "rgba(148,163,184,0.45)", lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: String(p) });
          } catch (e) { /* ignore */ }
        });
        this.oscSeries.push({ key: "rsi", series: rs });
      }
    }

    this._setOscData();
    container.style.display = "";
    try { this.oscChart.applyOptions({ width: container.clientWidth, height: container.clientHeight }); } catch (e) {}
    /* زوم پنل فقط با تغییر ترکیب ریست شود؛ در رفرش سبک فقط با چارت اصلی همگام بماند */
    if (this._oscKey !== key) {
      try { this.oscChart.timeScale().fitContent(); } catch (e) {}
      this._oscKey = key;
    } else {
      try {
        const r = this.chart.timeScale().getVisibleLogicalRange();
        if (r) this.oscChart.timeScale().setVisibleLogicalRange(r);
      } catch (e) {}
    }
  }

  _setOscData() {
    const ind = this.indicators || {};
    const macd = ind.macd || {};
    for (const item of this.oscSeries) {
      let arr = [];
      if (item.key === "hist") {
        arr = cleanPoints(macd.hist).map((p) => ({ time: p.time, value: p.value, color: p.value >= 0 ? OSC_COLORS.histUp : OSC_COLORS.histDn }));
      } else if (item.key === "macd") {
        arr = cleanPoints(macd.macd);
      } else if (item.key === "signal") {
        arr = cleanPoints(macd.signal);
      } else if (item.key === "rsi") {
        arr = cleanPoints(ind.rsi14);
      }
      try { item.series.setData(arr); } catch (e) { /* ignore */ }
    }
  }

  _syncScales() {
    try {
      this.chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (this._syncing || !this.oscChart) return;
        this._syncing = true;
        try { this.oscChart.timeScale().setVisibleLogicalRange(range); } catch (e) {}
        this._syncing = false;
      });
      this.oscChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (this._syncing) return;
        this._syncing = true;
        try { this.chart.timeScale().setVisibleLogicalRange(range); } catch (e) {}
        this._syncing = false;
      });
    } catch (e) { /* ignore */ }
  }

  /* ============================ برچسب منبع (صداقت داده) ============================ */

  _setBadge(dataTrust, source, trustLevel) {
    const badge = document.getElementById("cpSourceBadge");
    if (!badge) return;
    const dt = (typeof dataTrust === "object" && dataTrust) || {};
    const state = String(dt.state || trustLevel || "unknown").toLowerCase();
    /* verified live فقط با هر سه نشانه — دقیقاً مثل main.js؛ وگرنه هرگز «لایو» نمایش داده نمی‌شود */
    const verifiedLive = state === "live" && dt.is_live === true && dt.live_verified === true;
    const fa = {
      synthetic: "SYNTHETIC (شبیه‌سازی‌شده)",
      mock: "MOCK (دمو)",
      stale: "STALE (قدیمی)",
      unavailable: "UNAVAILABLE (ناموجود)",
      mixed: "MIXED (ترکیبی)",
    }[state];
    badge.classList.remove("synthetic", "live");
    if (verifiedLive) {
      badge.classList.add("live");
      badge.textContent = `منبع: LIVE (تأییدشده) · ${source || state}`;
    } else {
      badge.classList.add("synthetic");
      badge.textContent = `منبع: ${fa || state.toUpperCase() + " (تأییدنشده)"}${source ? " · " + source : ""}`;
    }
  }

  /* ============================ ابزار رسم (canvas) ============================ */

  _paneWidth() {
    try {
      const w = this.chart.priceScale("right").width();
      if (w > 0) return (this._wrap?.clientWidth || 0) - w;
    } catch (e) { /* ignore */ }
    return (this._wrap?.clientWidth || 0) - 62;
  }

  _timeIndexMap() {
    if (!this._tmap || this._tmapLen !== this.currentData.length) {
      this._tmap = new Map(this.currentData.map((c, i) => [Number(c.time), i]));
      this._tmapLen = this.currentData.length;
    }
    return this._tmap;
  }

  /** زمان از مختصات x — با fallback منطقی برای فضای خالی سمت چپ آخرین کندل */
  _timeAtX(x) {
    const ts = this.chart.timeScale();
    try {
      const t = ts.coordinateToTime(x);
      if (t != null) return Number(t);
      const log = ts.coordinateToLogical(x);
      if (log == null) return null;
      const i = Math.max(0, Math.min(this.currentData.length - 1, Math.round(log)));
      return this.currentData[i] ? Number(this.currentData[i].time) : null;
    } catch (e) {
      return null;
    }
  }

  _priceAtY(y) {
    try {
      const p = this.candleSeries.priceScale().coordinateToPrice(y);
      return p == null ? null : Number(p);
    } catch (e) {
      return null;
    }
  }

  _canvasPoint(e) {
    const rect = this.canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  _onCanvasMove(e) {
    if (!this.drawState.tool || this.drawState.tool === "delete") return;
    this._hover = this._canvasPoint(e);
    if (this.drawState.points.length === 1) this.redraw(); // پیش‌نمایش خط کشیده‌شده
  }

  _onCanvasClick(e) {
    const tool = this.drawState.tool;
    if (!tool) return;
    const pt = this._canvasPoint(e);
    if (tool === "delete") { this._deleteNear(pt); return; }

    const price = this._priceAtY(pt.y);
    const time = this._timeAtX(pt.x);
    if (price == null || time == null) return;
    this.drawState.points.push({ price, time });

    if (tool === "hline") {
      this.drawState.drawings.push({ type: "hline", price });
      this.drawState.points = [];
      this._finishDrawing();
    } else if (this.drawState.points.length === 2) {
      const [p1, p2] = this.drawState.points;
      this.drawState.drawings.push(
        tool === "trend"
          ? { type: "trend", p1, p2 }
          : { type: "fib", p1, p2 }
      );
      this.drawState.points = [];
      this._finishDrawing();
    } else {
      this.redraw();
    }
  }

  _finishDrawing() {
    this._saveDrawings();
    /* پس از تکمیل هر رسم، ابزار خاموش می‌شود (تعامل چارت برمی‌گردد) */
    this.drawState.tool = null;
    this.canvas?.classList.remove("armed");
    document.querySelectorAll("#cpDrawSeg button").forEach((b) => b.classList.remove("active"));
    this._setStatus("");
    this.redraw();
  }

  _deleteNear(pt) {
    const ts = this.chart.timeScale();
    const ps = this.candleSeries.priceScale();
    let hitIdx = -1;
    for (let i = this.drawState.drawings.length - 1; i >= 0; i--) {
      const d = this.drawState.drawings[i];
      try {
        if (d.type === "hline") {
          const y = ps.priceToCoordinate(d.price);
          if (y != null && Math.abs(y - pt.y) <= 8) { hitIdx = i; break; }
        } else if (d.type === "trend") {
          const x1 = ts.timeToCoordinate(d.p1.time), x2 = ts.timeToCoordinate(d.p2.time);
          const y1 = ps.priceToCoordinate(d.p1.price), y2 = ps.priceToCoordinate(d.p2.price);
          if (x1 == null || x2 == null || y1 == null || y2 == null) continue;
          if (this._distToSegment(pt.x, pt.y, x1, y1, x2, y2) <= 8) { hitIdx = i; break; }
        } else if (d.type === "fib") {
          const x1 = ts.timeToCoordinate(d.p1.time), x2 = ts.timeToCoordinate(d.p2.time);
          if (x1 == null || x2 == null) continue;
          for (const lv of FIB_LEVELS) {
            const yy = ps.priceToCoordinate(d.p1.price + (d.p2.price - d.p1.price) * lv);
            if (yy != null && Math.abs(yy - pt.y) <= 6 && pt.x >= Math.min(x1, x2) - 4 && pt.x <= Math.max(x1, x2) + 4) {
              hitIdx = i; break;
            }
          }
          if (hitIdx >= 0) break;
        }
      } catch (e) { /* ignore */ }
    }
    if (hitIdx >= 0) {
      this.drawState.drawings.splice(hitIdx, 1);
      this._saveDrawings();
      this.redraw();
    }
  }

  _distToSegment(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1, dy = y2 - y1;
    const len2 = dx * dx + dy * dy;
    const t = len2 ? Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / len2)) : 0;
    const cx = x1 + t * dx, cy = y1 + t * dy;
    return Math.hypot(px - cx, py - cy);
  }

  _saveDrawings() {
    lsSet(lsKeyDrawings(this.symbol), this.drawState.drawings);
    this._queueWorkspaceSave(); // WDA-1: رسم‌ها بخشی از فضای کاری‌اند
  }

  redraw() {
    if (!this.canvas || !this.ctx || !this.chart) return;
    const dpr = window.devicePixelRatio || 1;
    const w = this._wrap?.clientWidth || 0;
    const h = this._wrap?.clientHeight || 0;
    if (!w || !h) return;
    const W = Math.round(w * dpr), H = Math.round(h * dpr);
    if (this.canvas.width !== W) this.canvas.width = W;
    if (this.canvas.height !== H) this.canvas.height = H;
    const ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!this.currentData.length) return;

    const ts = this.chart.timeScale();
    const ps = this.candleSeries.priceScale();
    const range = (() => { try { return ts.getVisibleLogicalRange(); } catch (e) { return null; } })();
    const paneW = this._paneWidth();

    const coord = (pt) => {
      if (!pt) return { x: null, y: null };
      let x = null;
      try { x = ts.timeToCoordinate(pt.time); } catch (e) {}
      const y = (() => { try { return ps.priceToCoordinate(pt.price); } catch (e) { return null; } })();
      return { x: x == null ? null : x, y: y == null ? null : y };
    };

    for (const d of this.drawState.drawings) {
      if (d.type === "hline") {
        let y = null;
        try { y = ps.priceToCoordinate(d.price); } catch (e) {}
        if (y == null) continue; // بیرون از محدوده عمودی — رد شود
        ctx.strokeStyle = DRAW_COLORS.hline;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath(); ctx.moveTo(0, Math.round(y) + 0.5); ctx.lineTo(paneW, Math.round(y) + 0.5); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = DRAW_COLORS.hline;
        ctx.font = "11px Vazirmatn, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(fmtPrice(d.price), 6, y - 4);
      } else if (d.type === "trend") {
        const a = coord(d.p1), b = coord(d.p2);
        if (a.x == null || b.x == null || a.y == null || b.y == null) continue; // بخش کلیپ‌شده رسم نشود
        ctx.strokeStyle = DRAW_COLORS.trend;
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        for (const p of [a, b]) {
          ctx.fillStyle = DRAW_COLORS.trend;
          ctx.beginPath(); ctx.arc(p.x, p.y, 3, 0, Math.PI * 2); ctx.fill();
        }
      } else if (d.type === "fib") {
        const a = coord(d.p1), b = coord(d.p2);
        if (a.y == null || b.y == null) continue;
        /* گستره افقی: گیره به محدوده نمایان (logical) تا خطوط بریده‌شده هم درست کشیده شوند */
        let lx1 = null, lx2 = null;
        try {
          const m = this._timeIndexMap();
          const i1 = m.get(Number(d.p1.time)), i2 = m.get(Number(d.p2.time));
          if (i1 == null || i2 == null) continue;
          const from = range ? Math.max(0, Math.floor(range.from)) : Math.min(i1, i2);
          const to = range ? Math.ceil(range.to) : Math.max(i1, i2);
          lx1 = ts.logicalToCoordinate(Math.max(from, Math.min(i1, i2)));
          lx2 = ts.logicalToCoordinate(Math.min(to, Math.max(i1, i2)));
        } catch (e) {}
        if (lx1 == null || lx2 == null) {
          lx1 = a.x; lx2 = b.x;
          if (lx1 == null || lx2 == null) continue;
        }
        const xA = Math.min(lx1, lx2), xB = Math.max(lx1, lx2);
        ctx.font = "11px Vazirmatn, sans-serif";
        ctx.textAlign = "left";
        for (const lv of FIB_LEVELS) {
          const price = d.p1.price + (d.p2.price - d.p1.price) * lv;
          let y = null;
          try { y = ps.priceToCoordinate(price); } catch (e) {}
          if (y == null) continue;
          ctx.strokeStyle = DRAW_COLORS.fib;
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 3]);
          ctx.beginPath(); ctx.moveTo(xA, Math.round(y) + 0.5); ctx.lineTo(xB, Math.round(y) + 0.5); ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = DRAW_COLORS.fib;
          ctx.fillText(`${lv} · ${fmtPrice(price)}`, xA + 4, y - 3);
        }
      }
    }

    /* پیش‌نمایش نقطه اول ابزار فعلی */
    if (this.drawState.points.length) {
      const p = coord(this.drawState.points[0]);
      if (p.x != null && p.y != null) {
        ctx.fillStyle = DRAW_COLORS.trend;
        ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2); ctx.fill();
        if (this._hover && this.drawState.tool !== "delete") {
          ctx.strokeStyle = DRAW_COLORS.trend;
          ctx.setLineDash([4, 4]);
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(this._hover.x, this._hover.y); ctx.stroke();
          ctx.setLineDash([]);
        }
      }
    }
  }

  /* ============================ هشدار قیمتی محلی ============================ */

  _loadAlerts(symbol) {
    const lastClose = this.currentData.length ? Number(this.currentData[this.currentData.length - 1].close) : null;
    /* خط پایه مقایسه فقط با تغییر نماد ریست می‌شود — وگرنه عبور بین رفرش‌ها گم می‌شود */
    if (this._alertSymbol !== symbol) {
      this.alerts = lsGet(lsKeyAlerts(symbol), []).filter((a) => a && isFinite(+a.price));
      this._prevClose = lastClose;
      this._alertSymbol = symbol;
    }
    this._recreateAlertLines();
  }

  _recreateAlertLines() {
    this.alertLines.forEach((l) => { try { this.candleSeries.removePriceLine(l); } catch (e) {} });
    this.alertLines = [];
    for (const a of this.alerts) {
      try {
        this.alertLines.push(this.candleSeries.createPriceLine({
          price: +a.price,
          color: DRAW_COLORS.alert,
          lineWidth: 1,
          lineStyle: (typeof LightweightCharts !== "undefined" && LightweightCharts.LineStyle)
            ? LightweightCharts.LineStyle.Dashed
            : 2,
          axisLabelVisible: true,
          title: "هشدار",
        }));
      } catch (e) { /* ignore */ }
    }
  }

  _addAlertFromInput() {
    const input = document.getElementById("cpAlertPrice");
    const price = parseFloat(input?.value);
    if (!input || !isFinite(price) || price <= 0) {
      toast("قیمت هشدار معتبر وارد کنید", "warn");
      return;
    }
    this.alerts.push({ price });
    lsSet(lsKeyAlerts(this.symbol), this.alerts);
    this._queueWorkspaceSave(); // WDA-1: فهرست هشدارها ذخیره شود
    this._recreateAlertLines();
    input.value = "";
    toast(`هشدار قیمتی ${fmtPrice(price)} برای ${this.symbol} ثبت شد (فقط درون‌محصولی)`, "info");
  }

  /** مقایسه آخرین بسته‌شدن با قبلی: عبور از هر قیمت هشدار → toast درون‌محصولی فقط */
  _checkAlerts() {
    if (!this.currentData.length) return;
    const last = Number(this.currentData[this.currentData.length - 1].close);
    const prev = this._prevClose;
    if (prev != null && isFinite(prev)) {
      for (const a of this.alerts) {
        const p = +a.price;
        const crossed = (prev < p && last >= p) || (prev > p && last <= p);
        if (crossed) {
          toast(`⚠ هشدار قیمتی ${this.symbol}: عبور از ${fmtPrice(p)} (آخرین: ${fmtPrice(last)}) — SYNTHETIC/PAPER`, "warn");
        }
      }
    }
    this._prevClose = last;
  }

  /* ============================ ذخیره/بارگذاری/خروجی تحلیل ============================ */

  saveLayout() {
    const name = (prompt("نام تحلیل برای ذخیره:", `${this.symbol} ${this.timeframe}`) || "").trim();
    if (!name) return;
    const layouts = lsGet(LS_LAYOUTS, {});
    layouts[name] = {
      symbol: this.symbol,
      timeframe: this.timeframe,
      indicators: Object.keys(this.onIndicators).filter((k) => this.onIndicators[k]),
      drawings: lsGet(lsKeyDrawings(this.symbol), []),
      alerts: lsGet(lsKeyAlerts(this.symbol), []),
      saved_at: new Date().toISOString(),
    };
    if (lsSet(LS_LAYOUTS, layouts)) toast(`تحلیل «${name}» ذخیره شد`, "info");
    else toast("ذخیره در localStorage ناموفق بود", "error");
  }

  async loadLayout() {
    const layouts = lsGet(LS_LAYOUTS, {});
    const names = Object.keys(layouts);
    if (!names.length) {
      toast("هنوز تحلیلی ذخیره نشده است", "warn");
      return;
    }
    const name = (prompt("نام تحلیل را وارد کنید:\n- " + names.join("\n- "), names[names.length - 1]) || "").trim();
    if (!name) return;
    const lay = layouts[name];
    if (!lay) {
      toast("تحلیلی با این نام پیدا نشد", "error");
      return;
    }

    /* اندیکاتورها */
    const on = { ma20: false, ma50: false, ema20: false, bb: false, rsi: false, macd: false };
    (lay.indicators || []).forEach((k) => { if (k in on) on[k] = true; });
    this.onIndicators = on;
    document.querySelectorAll("#cpIndSeg button[data-ind]").forEach((b) => {
      b.classList.toggle("active", !!on[b.dataset.ind]);
    });

    /* نماد/تایم‌فریم + UI */
    const input = document.getElementById("cpSymbolInput");
    if (input && lay.symbol) input.value = lay.symbol;
    document.querySelectorAll("#cpTfSeg button[data-tf]").forEach((b) => {
      b.classList.toggle("active", b.dataset.tf === lay.timeframe);
    });

    await this.loadAndRender(lay.symbol, lay.timeframe);

    /* رسم‌ها و هشدارهای ذخیره‌شده در تحلیل */
    try {
      if (Array.isArray(lay.drawings)) {
        this.drawState.drawings = lay.drawings;
        lsSet(lsKeyDrawings(this.symbol), this.drawState.drawings);
        this.redraw();
      }
      if (Array.isArray(lay.alerts)) {
        this.alerts = lay.alerts.filter((a) => a && isFinite(+a.price));
        lsSet(lsKeyAlerts(this.symbol), this.alerts);
        this._recreateAlertLines();
      }
    } catch (e) { /* ignore */ }
    toast(`تحلیل «${name}» بازیابی شد`, "info");
  }

  exportLayouts() {
    const layouts = lsGet(LS_LAYOUTS, {});
    try {
      const blob = new Blob([JSON.stringify(layouts, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "radar_chartpro_layouts.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      toast("خروجی JSON تحلیل‌ها دانلود شد", "info");
    } catch (e) {
      toast("خروجی JSON ناموفق بود", "error");
    }
  }

  /* ============================ رفرش سبک ۱۰ ثانیه‌ای ============================ */

  startPolling() {
    if (this._poll) return;
    this._poll = setInterval(() => {
      /* فقط وقتی تب چارت حرفه‌ای فعال است (و صفحه پنهان نیست) */
      const panel = document.getElementById(this.panelId);
      if (!panel || !panel.classList.contains("active")) return;
      if (document.hidden) return;
      this.loadAndRender(this.symbol, this.timeframe, { fit: false });
    }, 10000);
  }

  stopPolling() {
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
  }

  /* ============================ WDA-1: ماندگاری فضای کاری ============================ */

  /**
   * ذخیرهٔ فضای کاری با تأخیر (debounce 600ms) — هر دنبالهٔ تغییر وضعیت
   * فقط یک نوشتن به localStorage تولید می‌کند؛ ذخیره هرگز UI را نمی‌شکند.
   */
  _queueWorkspaceSave() {
    if (this._wsTimer) clearTimeout(this._wsTimer);
    this._wsTimer = setTimeout(() => {
      this._wsTimer = null;
      try {
        saveWorkspace({
          symbol: this.symbol,
          timeframe: this.timeframe,
          indicators: { ...this.onIndicators },
          pane_layout: {
            osc_visible: document.getElementById(this.oscContainerId)?.style.display !== "none",
            osc_height: 150,
          },
          drawing_tools: {
            active_tool: this.drawState.tool || null,
            drawings: Array.isArray(this.drawState.drawings) ? this.drawState.drawings : [],
          },
          alerts: (this.alerts || []).map((a) => ({ price: +a.price })),
          window_layout: { width: window.innerWidth, height: window.innerHeight, maximized: false },
        });
      } catch (e) { /* مسکوت — ماندگاری حیاتی نیست */ }
    }, 600);
  }

  /* ============================ کمکی ============================ */

  _setStatus(text) {
    const el = document.getElementById("cpStatus");
    if (el) el.textContent = text || "";
  }
}

window.ChartProChart = ChartProChart;

/* ============================ بایند-on-demand (الگوی تب forex) ============================ */

let singleton = null;

function ensureChartPro() {
  if (!singleton) {
    singleton = new ChartProChart();
    singleton.init().catch((e) => console.error("chart_pro init failed", e));
  }
}

function bindChartProTab() {
  if (singleton || document.getElementById("cpChart") === null) return;

  // فعال‌سازی با تغییر کلاس پنل (MutationObserver — مثل forex)
  const observer = new MutationObserver(() => {
    const panel = document.getElementById("tab-chartpro");
    if (panel && panel.classList.contains("active")) ensureChartPro();
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });

  // و با کلیک روی دکمه تب (دپ‌لینک #/chartpro از روتر main.js هم همین کلیک را می‌زند)
  document.querySelectorAll('[data-tab="chartpro"]').forEach((btn) => {
    btn.addEventListener("click", () => setTimeout(ensureChartPro, 100));
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindChartProTab);
  else bindChartProTab();
}
