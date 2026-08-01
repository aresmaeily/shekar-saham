/**
 * volume_profile.js - اندیکاتور ولیو پرفایل (Volume Profile) v1.2
 * مثل تریدینگ ویو:
 * - محاسبه: حجم هر کندل روی محدوده قیمت آن کندل (High-Low) توزیع می‌شود
 * - حالت «محدوده نمایان» (Visible Range): با اسکرول/زوم دوباره محاسبه می‌شود (پیش‌فرض TV)
 * - حالت «کل داده» (Full Range): روی همه کندل‌های لودشده
 * - خروجی: باندهای قیمتی (bins) + POC (نقطه کنترل) + VAH / VAL (ناحیه ارزش ۷۰٪)
 * - رندر: هیستوگرام افقی روی کل ارتفاع چارت (سمت راست) + خطوط POC/VAH/VAL سراسری
 */

/** قیمت‌گذاری "خوشگل" برای عرض باندها (۱/۲/۵ × توان ۱۰) */
export function niceStep(raw) {
  if (!(raw > 0) || !isFinite(raw)) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  let step = 1;
  if (norm > 1) step = 2;
  if (norm > 2) step = 5;
  if (norm > 5) step = 10;
  return step * mag;
}

/**
 * محاسبه ولیو پرفایل از داده OHLCV
 * @param {Array<{time,open,high,low,close,volume}>} data
 * @param {{bins?: number, valueAreaPct?: number}} opts
 */
export function computeVolumeProfile(data, opts = {}) {
  const binTarget = opts.bins || 24;
  const vaPct = opts.valueAreaPct ?? 0.7;
  if (!Array.isArray(data) || data.length < 5) return null;

  let min = Infinity, max = -Infinity;
  for (const c of data) {
    if (!c || c.low == null || c.high == null) continue;
    const lo = Math.min(c.low, c.high);
    const hi = Math.max(c.low, c.high);
    if (lo < min) min = lo;
    if (hi > max) max = hi;
  }
  if (!isFinite(min) || !isFinite(max) || max <= min) return null;

  const step = niceStep((max - min) / binTarget);
  const first = Math.floor(min / step) * step;
  const n = Math.max(1, Math.round((Math.ceil(max / step) * step - first) / step));
  const vols = new Array(n).fill(0);

  for (const c of data) {
    const vol = Number(c.volume) || 0;
    if (vol <= 0) continue;
    const lo = Math.min(c.low, c.high);
    const hi = Math.max(c.low, c.high);
    const span = hi - lo || step;
    const i0 = Math.max(0, Math.floor((lo - first) / step));
    const i1 = Math.min(n - 1, Math.floor((hi - first) / step));
    if (i1 <= i0) {
      vols[i0] += vol;
      continue;
    }
    for (let i = i0; i <= i1; i++) {
      const binLo = first + i * step;
      const binHi = binLo + step;
      const overlap = Math.min(binHi, hi) - Math.max(binLo, lo);
      if (overlap > 0) vols[i] += vol * (overlap / span);
    }
  }

  let pocIdx = 0;
  for (let i = 1; i < n; i++) if (vols[i] > vols[pocIdx]) pocIdx = i;
  const total = vols.reduce((a, b) => a + b, 0);
  if (total <= 0) return null;

  // ناحیه ارزش: از POC شروع و همسایه پرحجم‌تر را اضافه کن تا ۷۰٪ حجم
  let cum = vols[pocIdx], loIdx = pocIdx, hiIdx = pocIdx;
  const target = total * vaPct;
  while (cum < target && (loIdx > 0 || hiIdx < n - 1)) {
    const below = loIdx > 0 ? vols[loIdx - 1] : -1;
    const above = hiIdx < n - 1 ? vols[hiIdx + 1] : -1;
    if (below >= above) { loIdx--; cum += below; }
    else { hiIdx++; cum += above; }
  }

  const bins = [];
  for (let i = 0; i < n; i++) {
    bins.push({
      price: first + i * step + step / 2,
      volume: vols[i],
      isPoc: i === pocIdx,
      inValueArea: i >= loIdx && i <= hiIdx,
    });
  }

  return {
    bins,
    step,
    min: first,
    max: first + n * step,
    poc: first + pocIdx * step + step / 2,
    vah: first + hiIdx * step + step / 2,
    val: first + loIdx * step + step / 2,
    valueAreaPct: Math.round((cum / total) * 1000) / 10,
    totalVolume: total,
  };
}

/**
 * اورلی ولیو پرفایل روی چارت lightweight-charts v4
 * با هر حرکت/زوم/ریسایز دوباره رسم می‌شود (همگام با مقیاس قیمت)
 */
export class VolumeProfileOverlay {
  /**
   * @param {{chart, candleSeries, container, getData: ()=>Array}} deps
   */
  constructor({ chart, candleSeries, container, getData }) {
    this.chart = chart;
    this.candleSeries = candleSeries;
    this.container = container;
    this.getData = getData || (() => []);
    this.enabled = false;
    this.mode = "visible"; // visible = محدوده نمایان (مثل TV) | full = کل داده
    this.canvas = null;
    this.ctx = null;
    this.priceLines = [];
    this.onStats = null;
    this._onVisible = () => this.refresh();
    this._ro = null;
  }

  /** تعیین حالت محاسبه: 'visible' (محدوده نمایان) یا 'full' (کل داده) */
  setMode(mode) {
    this.mode = mode === "full" ? "full" : "visible";
    if (this.enabled) this.refresh();
  }

  /** داده‌های داخل محدوده نمایان فعلی چارت */
  _visibleData() {
    let range = null;
    try {
      range = this.chart.timeScale().getVisibleRange();
    } catch (e) {}
    const all = this.getData() || [];
    if (!range || !range.from || !range.to) return all;
    const from = Number(range.from);
    const to = Number(range.to);
    return all.filter((c) => c && c.time >= from && c.time <= to);
  }

  enable(opts = {}) {
    if (this.enabled) return;
    this.enabled = true;
    if (opts.onStats) this.onStats = opts.onStats;

    if (!this.canvas) {
      this.canvas = document.createElement("canvas");
      this.canvas.className = "vp-canvas";
      this.canvas.style.cssText =
        "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:5;";
      this.container.appendChild(this.canvas);
      this.ctx = this.canvas.getContext("2d");
    }

    try { this.chart.timeScale().subscribeVisibleTimeRangeChange(this._onVisible); } catch (e) {}
    try { this.candleSeries.priceScale().subscribeVisibleLogicalRangeChange(this._onVisible); } catch (e) {}
    if (typeof ResizeObserver !== "undefined") {
      this._ro = new ResizeObserver(() => this.draw());
      this._ro.observe(this.container);
    }
    this.refresh();
  }

  disable() {
    if (!this.enabled) return;
    this.enabled = false;
    try { this.chart.timeScale().unsubscribeVisibleTimeRangeChange(this._onVisible); } catch (e) {}
    try { this.candleSeries.priceScale().unsubscribeVisibleLogicalRangeChange(this._onVisible); } catch (e) {}
    if (this._ro) { try { this._ro.disconnect(); } catch (e) {} this._ro = null; }
    if (this.canvas) {
      try { this.container.removeChild(this.canvas); } catch (e) {}
      this.canvas = null; this.ctx = null;
    }
    this.clearPriceLines();
    if (this.onStats) { try { this.onStats(null); } catch (e) {} }
  }

  refresh() {
    if (!this.enabled) return;
    this._rebuildPriceLines();
    this.draw();
    if (this.onStats) {
      try { this.onStats(this._compute()); } catch (e) {}
    }
  }

  _compute() {
    const src = this.mode === "visible" ? this._visibleData() : this.getData() || [];
    return computeVolumeProfile(src);
  }

  _rebuildPriceLines() {
    this.clearPriceLines();
    const prof = this._compute();
    if (!prof) return;
    const add = (price, color, title) => {
      try {
        this.priceLines.push(this.candleSeries.createPriceLine({
          price, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title,
        }));
      } catch (e) {}
    };
    add(prof.poc, "rgba(251,191,36,0.95)", "POC");
    add(prof.vah, "rgba(129,140,248,0.9)", "VAH");
    add(prof.val, "rgba(129,140,248,0.9)", "VAL");
  }

  clearPriceLines() {
    this.priceLines.forEach((l) => { try { this.candleSeries.removePriceLine(l); } catch (e) {} });
    this.priceLines = [];
  }

  draw() {
    if (!this.enabled || !this.canvas || !this.ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = this.container.clientWidth || 0;
    const h = this.container.clientHeight || 0;
    if (!w || !h) return;

    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    const ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const prof = this._compute();
    if (!prof) return;

    const priceScale = this.candleSeries.priceScale();
    const yOf = (p) => {
      try { return priceScale.priceToCoordinate(p); } catch (e) { return null; }
    };
    const yA = yOf(prof.min);
    const yB = yOf(prof.max);
    if (yA == null || yB == null) return;
    const yStep = Math.abs(yA - yB) / prof.bins.length;

    let maxVol = 0;
    for (const b of prof.bins) if (b.volume > maxVol) maxVol = b.volume;
    if (maxVol <= 0) return;

    const barMaxW = Math.min(170, Math.round(w * 0.26));
    const margin = 6;
    const right = w - 2;
    const left = right - barMaxW;

    for (const b of prof.bins) {
      const y = yOf(b.price);
      if (y == null) continue;
      const barW = Math.max(3, Math.round((b.volume / maxVol) * barMaxW));
      const x = right - barW;

      let fill;
      if (b.isPoc) fill = "rgba(251,191,36,0.85)";
      else if (b.inValueArea) {
        const t = b.volume / maxVol;
        fill = `rgba(99,102,241,${(0.25 + t * 0.45).toFixed(3)})`;
      } else {
        const t = b.volume / maxVol;
        fill = `rgba(148,163,184,${(0.10 + t * 0.18).toFixed(3)})`;
      }

      ctx.fillStyle = fill;
      const yTop = y - yStep / 2;
      const hh = Math.max(1, yStep - 1);
      if (typeof ctx.roundRect === "function") {
        ctx.beginPath();
        ctx.roundRect(x, yTop, barW, hh, 2);
        ctx.fill();
      } else {
        ctx.fillRect(x, yTop, barW, hh);
      }
    }

    // خط پایه سمت راست
    ctx.fillStyle = "rgba(148,163,184,0.25)";
    ctx.fillRect(right - 1, 0, 1, h);
    ctx.fillRect(right - barMaxW - margin / 2, 0, 1, h);
  }
}
