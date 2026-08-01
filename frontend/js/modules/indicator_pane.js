/**
 * indicator_pane.js - پنل اندیکاتورها مثل فراز / تریدینگ ویو v1.2
 * - اسیلاتورها (MACD / RSI / Stoch / CCI / OBV / Williams / ADX) در پنل جدا پایین چارت
 * - اورلی‌ها (Bollinger / VWAP) روی چارت قیمت
 * - همگام‌سازی اسکرول/زوم بین چارت اصلی و پنل اندیکاتور
 */
import { chartPalette } from "./utils/chart_theme.js";

const OSC_COLORS = {
  macd: "#22d3ee",
  signal: "#fbbf24",
  hist_up: "rgba(52,211,153,0.75)",
  hist_dn: "rgba(251,113,133,0.75)",
  rsi: "#a78bfa",
  stochK: "#34d399",
  stochD: "#fbbf24",
  cci: "#f472b6",
  obv: "#38bdf8",
  williams: "#f87171",
  adx: "#a78bfa",
  diPlus: "#34d399",
  diMinus: "#fb7185",
  boll: "#818cf8",
  bollBasis: "#fbbf24",
  vwap: "#34d399",
};

export class IndicatorPane {
  /**
   * @param {{oscContainerId: string, mainChart: object}} deps
   */
  constructor({ oscContainerId, mainChart }) {
    this.oscContainerId = oscContainerId;
    this.mainChart = mainChart;
    this.oscChart = null;
    this.oscSeries = [];        // [{key, series, kind}]
    this.overlaySeries = [];    // [{key, series}]
    this.full = null;           // آخرین اندیکاتورهای کامل
    this.oscType = "RSI";       // پیش‌فرض مثل فراز
    this.overlays = { boll: false, vwap: false };
    this._syncing = false;
    this._ro = null;
  }

  /* ---------- سری اسیلاتور ---------- */
  _makeOscSeries(type) {
    const chart = this.oscChart;
    const out = [];
    if (type === "MACD") {
      const hist = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false });
      const macd = chart.addLineSeries({ color: OSC_COLORS.macd, lineWidth: 1.5, priceLineVisible: false, title: "MACD" });
      const sig = chart.addLineSeries({ color: OSC_COLORS.signal, lineWidth: 1.2, priceLineVisible: false, title: "Signal" });
      out.push({ key: "hist", series: hist, kind: "hist" }, { key: "macd", series: macd, kind: "line" }, { key: "signal", series: sig, kind: "line" });
    } else if (type === "RSI") {
      const s = chart.addLineSeries({ color: OSC_COLORS.rsi, lineWidth: 1.6, priceLineVisible: false, title: "RSI" });
      [70, 30].forEach((p) => {
        s.createPriceLine({ price: p, color: "rgba(148,163,184,0.45)", lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: String(p) });
      });
      out.push({ key: "rsi", series: s, kind: "line" });
    } else if (type === "Stoch") {
      const k = chart.addLineSeries({ color: OSC_COLORS.stochK, lineWidth: 1.4, priceLineVisible: false, title: "%K" });
      const d = chart.addLineSeries({ color: OSC_COLORS.stochD, lineWidth: 1.4, priceLineVisible: false, title: "%D" });
      out.push({ key: "k", series: k, kind: "line" }, { key: "d", series: d, kind: "line" });
    } else if (type === "CCI") {
      const s = chart.addLineSeries({ color: OSC_COLORS.cci, lineWidth: 1.5, priceLineVisible: false, title: "CCI" });
      [100, -100, 0].forEach((p) => {
        s.createPriceLine({ price: p, color: "rgba(148,163,184,0.35)", lineStyle: 2, lineWidth: 1, axisLabelVisible: false });
      });
      out.push({ key: "cci", series: s, kind: "line" });
    } else if (type === "OBV") {
      const s = chart.addLineSeries({ color: OSC_COLORS.obv, lineWidth: 1.5, priceLineVisible: false, title: "OBV" });
      out.push({ key: "obv", series: s, kind: "line" });
    } else if (type === "Williams") {
      const s = chart.addLineSeries({ color: OSC_COLORS.williams, lineWidth: 1.5, priceLineVisible: false, title: "Williams %R" });
      [-20, -80].forEach((p) => {
        s.createPriceLine({ price: p, color: "rgba(148,163,184,0.4)", lineStyle: 2, lineWidth: 1, axisLabelVisible: false });
      });
      out.push({ key: "williams", series: s, kind: "line" });
    } else if (type === "ADX") {
      const a = chart.addLineSeries({ color: OSC_COLORS.adx, lineWidth: 1.6, priceLineVisible: false, title: "ADX" });
      const dp = chart.addLineSeries({ color: OSC_COLORS.diPlus, lineWidth: 1, priceLineVisible: false, title: "+DI" });
      const dm = chart.addLineSeries({ color: OSC_COLORS.diMinus, lineWidth: 1, priceLineVisible: false, title: "-DI" });
      out.push({ key: "adx", series: a, kind: "line" }, { key: "plus_di", series: dp, kind: "line" }, { key: "minus_di", series: dm, kind: "line" });
    }
    return out;
  }

  /* ---------- داده سری اسیلاتور از اندیکاتورهای کامل ---------- */
  _oscData(key, maxTime) {
    if (!this.full) return [];
    let arr = null;
    switch (key) {
      case "hist": arr = this.full.macd && this.full.macd.histogram; break;
      case "macd": arr = this.full.macd && this.full.macd.macd; break;
      case "signal": arr = this.full.macd && this.full.macd.signal; break;
      case "rsi": arr = this.full.rsi; break;
      case "k": arr = this.full.stochastic && this.full.stochastic.k; break;
      case "d": arr = this.full.stochastic && this.full.stochastic.d; break;
      case "cci": arr = this.full.cci; break;
      case "obv": arr = this.full.obv; break;
      case "williams": arr = this.full.williams; break;
      case "adx": arr = this.full.adx && this.full.adx.adx; break;
      case "plus_di": arr = this.full.adx && this.full.adx.plus_di; break;
      case "minus_di": arr = this.full.adx && this.full.adx.minus_di; break;
      default: arr = [];
    }
    if (!Array.isArray(arr)) return [];
    if (maxTime == null) return arr;
    return arr.filter((p) => p.time <= maxTime);
  }

  _paintOsc(maxTime) {
    if (!this.oscChart) return;
    this.oscSeries.forEach(({ key, series, kind }) => {
      let data = this._oscData(key, maxTime);
      if (kind === "hist") {
        data = data.map((p) => ({ time: p.time, value: p.value, color: p.value >= 0 ? OSC_COLORS.hist_up : OSC_COLORS.hist_dn }));
      }
      try { series.setData(data); } catch (e) {}
    });
    try { this.oscChart.timeScale().fitContent(); } catch (e) {}
    // همگام با چارت اصلی
    try {
      const r = this.mainChart.timeScale().getVisibleLogicalRange();
      if (r) this.oscChart.timeScale().setVisibleLogicalRange(r);
    } catch (e) {}
  }

  /* ---------- اورلی (Bollinger / VWAP) روی چارت اصلی ---------- */
  _overlayData(key, maxTime) {
    if (!this.full) return [];
    let arr = null;
    if (key === "vwap") arr = this.full.vwap;
    else if (key === "boll_upper") arr = this.full.bollinger && this.full.bollinger.upper;
    else if (key === "boll_basis") arr = this.full.bollinger && this.full.bollinger.basis;
    else if (key === "boll_lower") arr = this.full.bollinger && this.full.bollinger.lower;
    if (!Array.isArray(arr)) return [];
    if (maxTime == null) return arr;
    return arr.filter((p) => p.time <= maxTime);
  }

  _paintOverlays(maxTime) {
    this.overlaySeries.forEach(({ key, series }) => {
      try { series.setData(this._overlayData(key, maxTime)); } catch (e) {}
    });
  }

  /* ---------- API عمومی ---------- */

  /** اندیکاتورهای کامل جدید (بعد از هر لود داده) */
  setData(indicators, maxTime) {
    this.full = indicators || null;
    this._paintOsc(maxTime == null ? null : maxTime);
    this._paintOverlays(maxTime == null ? null : maxTime);
  }

  /** برای رپلای: فقط نقاط تا زمان مشخص */
  sliceTo(maxTime) {
    this._paintOsc(maxTime);
    this._paintOverlays(maxTime);
  }

  /** انتخاب اسیلاتور (null = خاموش) */
  setOscillator(type) {
    this.oscType = type || null;
    const container = document.getElementById(this.oscContainerId);
    if (!container) return;

    // حذف سری‌های قبلی
    this.oscSeries.forEach(({ series }) => {
      try { this.oscChart && this.oscChart.removeSeries(series); } catch (e) {}
    });
    this.oscSeries = [];

    if (!this.oscType) {
      container.style.display = "none";
      return;
    }

    if (!this.oscChart) {
      const pal = chartPalette();
      this.oscChart = LightweightCharts.createChart(container, {
        layout: { background: { color: pal.bg }, textColor: pal.text, fontFamily: "Vazirmatn, sans-serif" },
        grid: { vertLines: { color: pal.grid }, horzLines: { color: pal.grid } },
        rightPriceScale: { borderColor: pal.axis, scaleMargins: { top: 0.12, bottom: 0.12 } },
        timeScale: { borderColor: pal.axis, timeVisible: true },
        localization: { locale: "fa-IR" },
        autoSize: false,
      });
      if (typeof ResizeObserver !== "undefined") {
        this._ro = new ResizeObserver(() => {
          try {
            this.oscChart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
          } catch (e) {}
        });
        this._ro.observe(container);
      }
      this._syncScales();
    }

    container.style.display = "";
    this.oscChart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    this.oscSeries = this._makeOscSeries(this.oscType);
    this._paintOsc(null);
  }

  /** روشن/خاموش اورلی */
  toggleOverlay(key) {
    this.overlays[key] = !this.overlays[key];
    this._renderOverlay(key);
  }

  _renderOverlay(key) {
    const on = this.overlays[key];
    // حذف سری‌های قبلی این اورلی
    this.overlaySeries = this.overlaySeries.filter((item) => {
      if (item.key === key || (key === "boll" && item.key.startsWith("boll_"))) {
        try { this.mainChart.removeSeries(item.series); } catch (e) {}
        return false;
      }
      return true;
    });
    if (!on) return;
    if (key === "vwap") {
      const s = this.mainChart.addLineSeries({ color: OSC_COLORS.vwap, lineWidth: 1.5, priceLineVisible: false, title: "VWAP" });
      this.overlaySeries.push({ key: "vwap", series: s });
    } else if (key === "boll") {
      const up = this.mainChart.addLineSeries({ color: OSC_COLORS.boll, lineWidth: 1, priceLineVisible: false, title: "BB+", lineStyle: 1 });
      const basis = this.mainChart.addLineSeries({ color: OSC_COLORS.bollBasis, lineWidth: 1.2, priceLineVisible: false, title: "BB mid", lineStyle: 2 });
      const lo = this.mainChart.addLineSeries({ color: OSC_COLORS.boll, lineWidth: 1, priceLineVisible: false, title: "BB-", lineStyle: 1 });
      this.overlaySeries.push(
        { key: "boll_upper", series: up },
        { key: "boll_basis", series: basis },
        { key: "boll_lower", series: lo }
      );
    }
    this._paintOverlays(null);
  }

  /** همگام‌سازی دوطرفه زمان بین چارت اصلی و پنل */
  _syncScales() {
    try {
      this.mainChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (this._syncing || !this.oscChart) return;
        this._syncing = true;
        try { this.oscChart.timeScale().setVisibleLogicalRange(range); } catch (e) {}
        this._syncing = false;
      });
      this.oscChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (this._syncing) return;
        this._syncing = true;
        try { this.mainChart.timeScale().setVisibleLogicalRange(range); } catch (e) {}
        this._syncing = false;
      });
    } catch (e) {}
  }

  /** پاکسازی کامل (موقع بستن رپلای یا لود نماد جدید) */
  clear() {
    this.full = null;
    this.overlaySeries.forEach(({ series }) => {
      try { this.mainChart.removeSeries(series); } catch (e) {}
    });
    this.overlaySeries = [];
    this.oscSeries.forEach(({ series }) => {
      try { this.oscChart && this.oscChart.removeSeries(series); } catch (e) {}
    });
    this.oscSeries = [];
  }
}
