/**
 * replay.js - رپلای (بازپخش کندل به کندل) مثل تریدینگ ویو v1.0
 * - داده لودشده را بار به بار به چارت اضافه می‌کند
 * - دکمه پخش/توقف، سرعت (۱×، ۵×، ۱۰×، ۲۵×)، اسلایدر پرش به هر لحظه
 * - در پایان، چارت کامل بازیابی می‌شود
 */
export class ReplayController {
  /**
   * @param {{
   *   chart, candleSeries, volumeSeries, ma20Series, ma50Series, emaSeries,
   *   getData: () => ({candles: Array, indicators: Object|null}),
   *   onStatus?: (status: {step, total, price, playing}) => void,
   *   onEnd?: () => void,
   * }} deps
   */
  constructor({ chart, candleSeries, volumeSeries, ma20Series, ma50Series, emaSeries, getData, onStatus, onEnd }) {
    this.chart = chart;
    this.candleSeries = candleSeries;
    this.volumeSeries = volumeSeries;
    this.ma20Series = ma20Series;
    this.ma50Series = ma50Series;
    this.emaSeries = emaSeries;
    this.getData = getData || (() => ({ candles: [], indicators: null }));
    this.onStatus = onStatus || null;
    this.onEnd = onEnd || null;

    this.active = false;
    this.playing = false;
    this.step = 0;
    this.speed = 5; // کندل در ثانیه
    this.timer = null;
  }

  get total() {
    const { candles } = this.getData();
    return Array.isArray(candles) ? candles.length : 0;
  }

  /** کندل‌های قابل‌مشاهده (برای ولیو پرفایل و ...) */
  getVisibleCandles() {
    const { candles } = this.getData();
    return Array.isArray(candles) ? candles.slice(0, Math.min(this.step, candles.length)) : [];
  }

  _apply() {
    const { candles, indicators } = this.getData();
    if (!Array.isArray(candles) || !candles.length) return;
    const n = Math.min(this.step, candles.length);
    if (n <= 0) return;
    const slice = candles.slice(0, n);
    const t = slice[n - 1].time;

    this.candleSeries.setData(slice);
    if (indicators) {
      const setIf = (series, key) => {
        if (series && Array.isArray(indicators[key])) {
          series.setData(indicators[key].filter((p) => p.time <= t));
        }
      };
      setIf(this.volumeSeries, "volume");
      setIf(this.ma20Series, "ma20");
      setIf(this.ma50Series, "ma50");
      setIf(this.emaSeries, "ema20");
    }

    // اسکرول خودکار به آخرین کندل (مثل تریدینگ ویو)
    try { this.chart.timeScale().scrollToRealTime(); } catch (e) {}

    if (this.onStatus) {
      this.onStatus({
        step: n,
        total: candles.length,
        price: slice[n - 1].close,
        playing: this.playing,
      });
    }
  }

  _tick() {
    this.step += 1;
    if (this.step > this.total) {
      // پایان داده — توقف و بازیابی کامل
      this.playing = false;
      this._clearTimer();
      this.restoreFull();
      if (this.onStatus) this.onStatus({ step: this.total, total: this.total, price: null, playing: false, ended: true });
      if (this.onEnd) this.onEnd();
      return;
    }
    this._apply();
  }

  _clearTimer() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  _schedule() {
    this._clearTimer();
    if (!this.playing) return;
    this.timer = setInterval(() => this._tick(), Math.max(30, Math.round(1000 / this.speed)));
  }

  /** شروع رپلای از ابتدا */
  start() {
    const { candles } = this.getData();
    if (!Array.isArray(candles) || !candles.length) return;
    this.active = true;
    this.step = 0;
    this.playing = true;
    this._schedule();
    this._tick(); // اولین کندل
  }

  /** توقف کامل و بازیابی چارت کامل */
  stop() {
    this.active = false;
    this.playing = false;
    this._clearTimer();
    this.restoreFull();
  }

  /** پخش/توقف */
  togglePlay() {
    if (!this.active) return;
    this.playing = !this.playing;
    this._schedule();
    if (this.playing) this._apply();
    if (this.onStatus) {
      const { candles } = this.getData();
      const n = Math.min(this.step, candles.length);
      this.onStatus({ step: n, total: candles.length, price: n ? candles[n - 1].close : null, playing: this.playing });
    }
  }

  /** پرش به کندل مشخص (اسلایدر) */
  setStep(n) {
    if (!this.active) return;
    const total = this.total;
    this.step = Math.max(0, Math.min(n, total));
    this._apply();
  }

  setSpeed(s) {
    this.speed = s;
    if (this.playing) this._schedule();
  }

  /** بازیابی کامل (بدون رپلای) */
  restoreFull() {
    const { candles, indicators } = this.getData();
    if (!Array.isArray(candles) || !candles.length) return;
    this.candleSeries.setData(candles);
    if (indicators) {
      const setIf = (series, key) => {
        if (series && Array.isArray(indicators[key])) series.setData(indicators[key]);
      };
      setIf(this.volumeSeries, "volume");
      setIf(this.ma20Series, "ma20");
      setIf(this.ma50Series, "ma50");
      setIf(this.emaSeries, "ema20");
    }
    try { this.chart.timeScale().fitContent(); } catch (e) {}
    if (this.onStatus) {
      this.onStatus({ step: candles.length, total: candles.length, price: candles[candles.length - 1].close, playing: false });
    }
  }
}
