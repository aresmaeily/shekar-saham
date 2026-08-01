/**
 * tradingview_excellent.js - v1.0 Excellent + Volume Profile - Better than Novin/Arshan
 */
import { escapeHtml } from "../security.js";
import { toTehranTime } from "../utils/timezone.js";
import { VolumeProfileOverlay } from "../volume_profile.js";
import { findSupportResistance } from "../support_resistance.js";
import { chartPalette } from "../utils/chart_theme.js";

export class ExcellentChart {
  constructor(containerId, symbol = "فملی") {
    this.containerId = containerId;
    this.symbol = symbol;
    this.timeframe = "1m";
    this.chart = null;
    this.candleSeries = null;
    this.volumeSeries = null;
    this.ma20Series = null;
    this.ma50Series = null;
    this.emaSeries = null;
    this.riskLines = [];
    this.currentData = [];
    this.volumeProfileOverlay = null;
    this.srLines = [];
    this.srEnabled = false;
  }

  /** حمایت/مقاومت خودکار (ایده ۴.۱) */
  toggleSupportResistance(enabled, onStats = null) {
    if (!this.chart) return;
    this.srEnabled = enabled;
    this.clearSrLines();
    if (!enabled) {
      if (onStats) onStats(null);
      return;
    }
    const { supports, resistances } = findSupportResistance(this.currentData || []);
    const all = [
      ...supports.map((p) => ({ p, cls: "sup" })),
      ...resistances.map((p) => ({ p, cls: "res" })),
    ];
    for (const item of all) {
      try {
        const line = this.candleSeries.createPriceLine({
          price: item.p,
          color: item.cls === "sup" ? "rgba(52,211,153,0.75)" : "rgba(251,113,133,0.75)",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: item.cls === "sup" ? "حمایت" : "مقاومت",
        });
        this.srLines.push(line);
      } catch (e) {}
    }
    if (onStats) {
      onStats({ supports: supports.length, resistances: resistances.length });
    }
  }

  clearSrLines() {
    this.srLines.forEach((l) => {
      try { this.candleSeries.removePriceLine(l); } catch (e) {}
    });
    this.srLines = [];
  }

  async init() {
    const el = document.getElementById(this.containerId);
    if (!el) return;
    el.innerHTML = "";
    el.style.position = "relative"; // needed for the Volume Profile overlay canvas
    
    const pal = chartPalette();
    this.chart = LightweightCharts.createChart(el, {
      width: el.clientWidth,
      height: 500,
      layout: { background: { color: pal.bg }, textColor: pal.text, fontFamily: "Vazirmatn, sans-serif" },
      grid: { vertLines: { color: pal.grid }, horzLines: { color: pal.grid } },
      rightPriceScale: { borderColor: pal.axis, scaleMargins: { top: 0.1, bottom: 0.2 } },
      timeScale: { borderColor: pal.axis, timeVisible: true },
      crosshair: { mode: 1 },
      localization: { locale: "fa-IR" }
    });

    const ro = new ResizeObserver(() => {
      this.chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    });
    ro.observe(el);

    this.candleSeries = this.chart.addCandlestickSeries({
      upColor: pal.up, downColor: pal.down, borderVisible: false,
      wickUpColor: pal.up, wickDownColor: pal.down
    });

    this.volumeSeries = this.chart.addHistogramSeries({
      priceFormat: { type: "volume" }, priceScaleId: "", priceLineVisible: false
    });
    this.volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    this.ma20Series = this.chart.addLineSeries({ color: "rgba(251,191,36,0.9)", lineWidth: 1.5, priceLineVisible: false, title: "MA20" });
    this.ma50Series = this.chart.addLineSeries({ color: "rgba(129,140,248,0.9)", lineWidth: 1.5, priceLineVisible: false, title: "MA50" });
    this.emaSeries = this.chart.addLineSeries({ color: "rgba(34,211,238,0.8)", lineWidth: 1, lineStyle: 2, priceLineVisible: false, title: "EMA20" });

    await this.loadData();
    this.setupRealtime();
  }

  async loadData() {
    try {
      const res = await fetch(`/api/v08/chart/${encodeURIComponent(this.symbol)}?timeframe=${this.timeframe}&with_indicators=true`).then(r=>r.json());
      this.currentData = res.ohlcv || [];
      if (!this.currentData.length) return;

      this.candleSeries.setData(this.currentData);
      
      if (res.indicators) {
        if (res.indicators.volume) this.volumeSeries.setData(res.indicators.volume);
        else this.volumeSeries.setData(this.currentData.map(c => ({
          time: c.time, value: c.volume || 0,
          color: c.close >= c.open ? "rgba(52,211,153,0.4)" : "rgba(251,113,133,0.4)"
        })));
        if (res.indicators.ma20) this.ma20Series.setData(res.indicators.ma20);
        if (res.indicators.ma50) this.ma50Series.setData(res.indicators.ma50);
        if (res.indicators.ema20) this.emaSeries.setData(res.indicators.ema20);
      }

      if (res.markers && res.markers.length) {
        this.candleSeries.setMarkers(res.markers.map(m => ({
          time: m.time, position: m.position, color: m.color, shape: m.shape, text: m.text
        })));
      }

      this.clearRiskLines();
      if (res.risk_levels) {
        Object.entries(res.risk_levels).forEach(([key, price]) => {
          if (typeof price === "number" && price > 0) {
            const line = this.candleSeries.createPriceLine({
              price: price,
              color: key.includes("conservative") ? "#fb7185" : key.includes("support") ? "#818cf8" : "#fbbf24",
              lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: key
            });
            this.riskLines.push(line);
          }
        });
      }

      this.chart.timeScale().fitContent();
    } catch (e) {
      console.error("Chart load failed:", e);
    }

    // If Volume Profile is enabled, recompute after every data load
    if (this.volumeProfileOverlay && this.volumeProfileOverlay.enabled) {
      try { this.volumeProfileOverlay.refresh(); } catch (e) {}
    }
  }

  /**
   * اندیکاتور ولیو پرفایل (Volume Profile) - POC / VAH / VAL
   * @param {boolean} enabled
   * @param {{onStats?: (profile|null)=>void, getData?: ()=>Array}} [opts]
   */
  toggleVolumeProfile(enabled, opts = {}) {
    if (!this.chart) return;
    if (enabled) {
      if (!this.volumeProfileOverlay) {
        this.volumeProfileOverlay = new VolumeProfileOverlay({
          chart: this.chart,
          candleSeries: this.candleSeries,
          container: document.getElementById(this.containerId),
          getData: opts.getData || (() => this.currentData),
        });
      }
      this.volumeProfileOverlay.enable(opts);
    } else if (this.volumeProfileOverlay) {
      this.volumeProfileOverlay.disable();
    }
  }

  clearRiskLines() {
    this.riskLines.forEach(line => {
      try { this.candleSeries.removePriceLine(line); } catch {}
    });
    this.riskLines = [];
  }

  setupRealtime() {
    setInterval(async () => {
      try {
        const res = await fetch(`/api/symbol/${encodeURIComponent(this.symbol)}/full`).then(r=>r.json());
        if (res && res.snapshot) {
          const last = res.snapshot;
          const now = Math.floor(Date.now() / 60) * 60;
          const lastCandle = this.currentData[this.currentData.length - 1];
          if (lastCandle && lastCandle.time === now) {
            this.candleSeries.update({
              time: now, open: lastCandle.open, high: Math.max(lastCandle.high, last.pl),
              low: Math.min(lastCandle.low, last.pl), close: last.pl
            });
          } else if (lastCandle && now > lastCandle.time) {
            const newCandle = { time: now, open: last.pl, high: last.pl, low: last.pl, close: last.pl };
            this.candleSeries.update(newCandle);
            this.currentData.push(newCandle);
          }
        }
      } catch {}
    }, 10000);
  }

  setTimeframe(tf) { this.timeframe = tf; this.loadData(); }
  setSymbol(sym) { this.symbol = sym; this.loadData(); }
}

window.ExcellentChart = ExcellentChart;
