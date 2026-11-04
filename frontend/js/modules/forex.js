/**
 * forex.js - v1.0 Forex + Gold + Brokers like faraz.io but better
 * - نمادها: طلا XAUUSD (بروکرهای BlackBull/Pepperstone/FXCM) · GC1 کومکس · DXY (TVC)
 *           S&P500 (US500) · US100 · US30 · نفت برنت (UKOIL) — همگی از Capital.com
 * - اندیکاتور: ولیو پرفایل (POC / VAH / VAL) + MA/EMA/RSI + اندیکاتور شخصی
 */
import { ExcellentChart } from "./render/tradingview_excellent.js";
import { events } from "../core/events.js";
import { ReplayController } from "./replay.js";
import { IndicatorPane } from "./indicator_pane.js";

let forexChart = null;
let currentForexSymbol = "XAUUSD";
let currentForexBroker = "blackbull";
let currentForexTf = "1m";
let volumeProfileOn = false;
let replayCtrl = null;
let indicatorPane = null;
let srOn = false;

// برچسب‌های بروکر/مرجع — همان منبع حقیقت بک‌اند
const BROKER_LABELS = {
  blackbull: "BlackBull",
  pepperstone: "Pepperstone",
  fxcm: "FXCM",
  comex: "COMEX",
  tvc: "TVC",
  "capital.com": "Capital.com",
};

// اگر API نمادها در دسترس نبود (آفلاین) — fallback همان بک‌اند
const FALLBACK_SYMBOLS = [
  { symbol: "XAUUSD", name: "طلا", name_en: "Gold Spot", brokers: ["blackbull", "pepperstone", "fxcm"], default_broker: "blackbull", venue: "Spot / CFD" },
  { symbol: "GC1", name: "GC1", name_en: "Gold Futures", brokers: ["comex"], default_broker: "comex", venue: "COMEX" },
  { symbol: "DXY", name: "DXY", name_en: "Dollar Index", brokers: ["tvc"], default_broker: "tvc", venue: "TVC / ICE" },
  { symbol: "US500", name: "S&P 500", name_en: "US500", brokers: ["capital.com"], default_broker: "capital.com", venue: "Capital.com" },
  { symbol: "US100", name: "US100", name_en: "Nasdaq 100", brokers: ["capital.com"], default_broker: "capital.com", venue: "Capital.com" },
  { symbol: "US30", name: "US30", name_en: "Dow Jones", brokers: ["capital.com"], default_broker: "capital.com", venue: "Capital.com" },
  { symbol: "UKOIL", name: "برنت", name_en: "Brent Oil", brokers: ["capital.com"], default_broker: "capital.com", venue: "Capital.com" },
  { symbol: "EURUSD", name: "EUR/USD", name_en: "EUR/USD", brokers: [], default_broker: null, venue: "FX" },
  { symbol: "GBPUSD", name: "GBP/USD", name_en: "GBP/USD", brokers: [], default_broker: null, venue: "FX" },
  { symbol: "USDJPY", name: "USD/JPY", name_en: "USD/JPY", brokers: [], default_broker: null, venue: "FX" },
  { symbol: "BTCUSDT", name: "BTC", name_en: "Bitcoin", brokers: [], default_broker: null, venue: "Binance" },
  { symbol: "ETHUSDT", name: "ETH", name_en: "Ethereum", brokers: [], default_broker: null, venue: "Binance" },
];

let symbolList = FALLBACK_SYMBOLS;

async function loadSymbolList() {
  try {
    const res = await fetch("/api/v09/forex/symbols").then((r) => r.json());
    if (res && Array.isArray(res.symbols) && res.symbols.length) {
      symbolList = res.symbols.map((s) => ({
        symbol: s.symbol,
        name: s.name,
        name_en: s.name_en || s.symbol,
        brokers: s.brokers || [],
        default_broker: s.default_broker || (s.brokers && s.brokers[0]) || null,
        venue: s.venue || "",
      }));
    }
  } catch (e) {
    console.warn("Symbol list fetch failed, using fallback", e);
  }
}

function buildSymbolButtons() {
  const container = document.getElementById("forexSymbols");
  if (!container) return;
  container.innerHTML = symbolList.map((s) => `
    <button class="${s.symbol === currentForexSymbol ? "active" : ""}" data-sym="${s.symbol}" title="${s.name_en || ""}">${s.name}</button>
  `).join("");

  container.querySelectorAll("button").forEach((btn) => {
    btn.onclick = () => {
      container.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentForexSymbol = btn.dataset.sym;
      currentForexBroker = getSymbolMeta(currentForexSymbol).default_broker || null;
      buildBrokerButtons();
      if (forexChart) {
        forexChart.broker = currentForexBroker;
        forexChart.setSymbol(currentForexSymbol);
      }
    };
  });
}

function getSymbolMeta(sym) {
  return symbolList.find((s) => s.symbol === sym) || FALLBACK_SYMBOLS[0];
}

function buildBrokerButtons() {
  const container = document.getElementById("forexBrokers");
  if (!container) return;
  const meta = getSymbolMeta(currentForexSymbol);
  const brokers = meta.brokers || [];

  if (!brokers.length) {
    container.innerHTML = `<span class="muted" style="align-self:center">منبع: ${meta.venue || "—"}</span>`;
    return;
  }

  if (!currentForexBroker || !brokers.includes(currentForexBroker)) {
    currentForexBroker = meta.default_broker || brokers[0];
  }

  container.innerHTML = brokers.map((b) => `
    <button class="${b === currentForexBroker ? "active" : ""}" data-broker="${b}">${BROKER_LABELS[b] || b}</button>
  `).join("");

  container.querySelectorAll("button").forEach((btn) => {
    btn.onclick = () => {
      container.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      btn.classList.add("active");
      currentForexBroker = btn.dataset.broker;
      if (forexChart) {
        forexChart.broker = currentForexBroker;
        forexChart.loadData(); // same symbol, different broker -> reload
      }
    };
  });
}

function fmtPrice(p) {
  if (p == null || Number.isNaN(+p)) return "—";
  const abs = Math.abs(p);
  let dec = 2;
  if (abs < 0.01) dec = 6;
  else if (abs < 0.1) dec = 5;
  else if (abs < 1) dec = 4;
  else if (abs < 10) dec = 3;
  else if (abs < 200) dec = 2;
  else dec = 1;
  return Number(p).toLocaleString("fa-IR", { maximumFractionDigits: dec, minimumFractionDigits: 0 });
}

function renderVolumeProfileInfo(profile) {
  const infoEl = document.getElementById("vpInfo");
  if (!infoEl) return;
  if (!profile) {
    infoEl.textContent = "";
    return;
  }
  infoEl.innerHTML =
    `<span class="chip" style="border-color:rgba(251,191,36,.4);color:#fbbf24">POC ${fmtPrice(profile.poc)}</span> ` +
    `<span class="chip" style="border-color:rgba(129,140,248,.4);color:#a5b4fc">VAH ${fmtPrice(profile.vah)}</span> ` +
    `<span class="chip" style="border-color:rgba(129,140,248,.4);color:#a5b4fc">VAL ${fmtPrice(profile.val)}</span> ` +
    `<span class="muted">ناحیه ارزش ${profile.valueAreaPct}٪ · ${profile.bins.length} باند</span>`;
}

function bindVolumeProfileToggle() {
  const btn = document.getElementById("vpToggle");
  if (!btn) return;
  btn.onclick = () => {
    volumeProfileOn = !volumeProfileOn;
    btn.classList.toggle("active", volumeProfileOn);
    btn.style.opacity = volumeProfileOn ? "1" : "";
    const mode = document.getElementById("vpMode");
    if (mode) mode.style.display = volumeProfileOn ? "" : "none";
    applyVolumeProfileState();
  };

  // حالت محاسبه: محدوده نمایان (مثل TV) / کل داده
  const modeSeg = document.getElementById("vpMode");
  if (modeSeg) {
    modeSeg.querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        modeSeg.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        if (forexChart && forexChart.volumeProfileOverlay) {
          forexChart.volumeProfileOverlay.setMode(b.dataset.mode);
        }
      };
    });
  }
}

function applyVolumeProfileState() {
  if (!forexChart || !forexChart.chart) return;
  forexChart.toggleVolumeProfile(volumeProfileOn, {
    onStats: volumeProfileOn ? renderVolumeProfileInfo : null,
    getData: () => (replayCtrl && replayCtrl.active ? replayCtrl.getVisibleCandles() : forexChart.currentData || []),
  });
  if (!volumeProfileOn) renderVolumeProfileInfo(null);
}

/* ===================== حمایت/مقاومت خودکار (ایده ۴.۱) ===================== */

function bindSrToggle() {
  const btn = document.getElementById("srToggle");
  if (!btn) return;
  btn.onclick = () => {
    srOn = !srOn;
    btn.classList.toggle("active", srOn);
    if (!forexChart || !forexChart.chart) return;
    forexChart.toggleSupportResistance(srOn, (stats) => {
      const infoEl = document.getElementById("srInfo");
      if (infoEl) {
        infoEl.textContent = stats
          ? `حمایت: ${stats.supports} · مقاومت: ${stats.resistances}`
          : "";
      }
    });
  };
}

/* ===================== رپلای (بازپخش کندل به کندل) ===================== */

function updateReplayUI(status) {
  const bar = document.getElementById("replayBar");
  if (!bar) return;
  const slider = document.getElementById("rpSlider");
  const statusEl = document.getElementById("rpStatus");
  const playBtn = document.getElementById("rpPlay");

  if (slider && status && status.total) {
    slider.max = status.total;
    slider.value = status.step;
  }
  if (statusEl) {
    if (status.ended) {
      statusEl.textContent = `پایان — ${status.step} کندل`;
    } else if (status.price != null) {
      statusEl.textContent = `کندل ${status.step} / ${status.total} · قیمت ${fmtPrice(status.price)}`;
    } else {
      statusEl.textContent = `کندل ${status.step} / ${status.total}`;
    }
  }
  if (playBtn) playBtn.textContent = status.playing ? "⏸" : "▶";

  // ولیو پرفایل همگام با رپلای
  if (volumeProfileOn && forexChart && forexChart.volumeProfileOverlay && forexChart.volumeProfileOverlay.enabled) {
    try { forexChart.volumeProfileOverlay.refresh(); } catch (e) {}
  }

  // حمایت/مقاومت همگام با رپلای
  if (srOn && forexChart && forexChart.chart) {
    try { forexChart.toggleSupportResistance(true, null); } catch (e) {}
  }

  // پنل اندیکاتور همگام با رپلای (فقط نقاط تا کندل فعلی)
  if (indicatorPane && status.step > 0 && forexChart && forexChart.currentData) {
    const bar = forexChart.currentData[Math.min(status.step, forexChart.currentData.length) - 1];
    if (bar) {
      try { indicatorPane.sliceTo(bar.time); } catch (e) {}
    }
  }
}

function startReplay() {
  if (!forexChart || !forexChart.chart || !replayCtrl) return;
  const bar = document.getElementById("replayBar");
  const toggle = document.getElementById("replayToggle");
  replayCtrl.start();
  if (bar) bar.classList.remove("hidden");
  if (toggle) toggle.textContent = "⏹ پایان رپلای";
}

function stopReplay(silent = false) {
  if (!replayCtrl || !replayCtrl.active) return;
  replayCtrl.stop();
  const bar = document.getElementById("replayBar");
  const toggle = document.getElementById("replayToggle");
  if (bar) bar.classList.add("hidden");
  if (toggle) toggle.textContent = "⏪ رپلای";
  if (!silent) {
    // چارت کامل از قبل توسط controller برگردانده شده
  }
}

function buildReplayUI() {
  const bar = document.getElementById("replayBar");
  const toggle = document.getElementById("replayToggle");
  if (!bar || !toggle) return;

  toggle.onclick = () => {
    if (replayCtrl && replayCtrl.active) stopReplay();
    else startReplay();
  };

  const playBtn = document.getElementById("rpPlay");
  if (playBtn) {
    playBtn.onclick = () => {
      if (replayCtrl && replayCtrl.active) replayCtrl.togglePlay();
    };
  }

  bar.querySelectorAll("#rpSpeeds button").forEach((b) => {
    b.onclick = () => {
      bar.querySelectorAll("#rpSpeeds button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      // MASTER-RADAR WAVE-2 (2026-11-04): parseFloat تا ۰.۵× هم کار کند (parseInt «0.5» را 0 می‌خواند و به ۵ برمی‌گشت)
      if (replayCtrl) replayCtrl.setSpeed(parseFloat(b.dataset.sp) || 5);
    };
  });

  const slider = document.getElementById("rpSlider");
  if (slider) {
    slider.oninput = () => {
      if (replayCtrl && replayCtrl.active) replayCtrl.setStep(parseInt(slider.value, 10) || 0);
    };
  }

  const closeBtn = document.getElementById("rpClose");
  if (closeBtn) closeBtn.onclick = () => stopReplay();
}

/* ===================== اندیکاتورها (مثل فراز) ===================== */

/** اگر رپلای فعال است، پنل اندیکاتور را به کندل فعلی برگردان */
function resliceForReplay() {
  if (!replayCtrl || !replayCtrl.active || !forexChart || !forexChart.currentData || !indicatorPane) return;
  const bar = forexChart.currentData[Math.min(replayCtrl.step, forexChart.currentData.length) - 1];
  if (bar) {
    try { indicatorPane.sliceTo(bar.time); } catch (e) {}
  }
}

function bindIndicatorControls() {
  // اسیلاتورها (یک مورد هم‌زمان، مثل فراز)
  const oscSeg = document.getElementById("indOsc");
  if (oscSeg) {
    oscSeg.querySelectorAll("button").forEach((btn) => {
      btn.onclick = () => {
        const type = btn.dataset.osc;
        const same = indicatorPane && indicatorPane.oscType === type;
        oscSeg.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
        if (!same) {
          btn.classList.add("active");
          if (indicatorPane) indicatorPane.setOscillator(type);
        } else {
          if (indicatorPane) indicatorPane.setOscillator(null);
        }
        resliceForReplay();
      };
    });
  }

  // اورلی‌ها (چند مورد هم‌زمان)
  const ovSeg = document.getElementById("indOverlay");
  if (ovSeg) {
    ovSeg.querySelectorAll("button").forEach((btn) => {
      btn.onclick = () => {
        const key = btn.dataset.ov;
        btn.classList.toggle("active");
        if (indicatorPane) indicatorPane.toggleOverlay(key);
        resliceForReplay();
      };
    });
  }
}


export async function initForexChart() {
  const container = document.getElementById("forexChart");
  if (!container || forexChart) return;

  forexChart = new ExcellentChart("forexChart", currentForexSymbol);
  forexChart.broker = currentForexBroker;

  // Override data source to use forex API (with broker)
  forexChart.loadData = async function () {
    // اگر رپلای فعال است، با داده جدید قطعش کن
    if (replayCtrl && replayCtrl.active) stopReplay(true);

    try {
      const brokerQ = this.broker ? `&broker=${encodeURIComponent(this.broker)}` : "";
      const res = await fetch(
        `/api/v09/forex/${encodeURIComponent(this.symbol)}?timeframe=${this.timeframe}&with_indicators=true${brokerQ}`
      ).then((r) => r.json());

      if (res.error) {
        const infoEl = document.getElementById("forexInfo");
        if (infoEl) infoEl.innerHTML = `<div class="icard"><h4>خطا</h4><div class="meta">${res.error}</div></div>`;
        return;
      }

      this.currentData = res.ohlcv || [];
      this._indicatorData = res.indicators || null;
      if (!this.currentData.length) {
        const infoEl = document.getElementById("forexInfo");
        if (infoEl) infoEl.innerHTML = `<div class="icard"><h4>هشدار</h4><div class="meta">برای این رنج، کندل کافی ساخته نشد — رنج بزرگ‌تری انتخاب کنید (مثلاً ۱۰R به جای ۱۰۰۰R)</div></div>`;
        return;
      }
      if (indicatorPane) indicatorPane.setData(res.indicators);
      this.candleSeries.setData(this.currentData);
      if (res.indicators) {
        if (res.indicators.volume) this.volumeSeries.setData(res.indicators.volume);
        if (res.indicators.ma20) this.ma20Series.setData(res.indicators.ma20);
        if (res.indicators.ma50) this.ma50Series.setData(res.indicators.ma50);
        if (res.indicators.ema20) this.emaSeries.setData(res.indicators.ema20);
      }
      this.chart.timeScale().fitContent();

      // Info
      const infoEl = document.getElementById("forexInfo");
      if (infoEl) {
        const dt = res.data_trust || {};
        const verifiedLive = dt.state === "live" && dt.is_live === true && dt.live_verified === true;
        const trustFa = verifiedLive
          ? "تأییدشده"
          : (res.trust_level === "synthetic" || dt.state === "synthetic" || dt.state === "mock")
            ? "سنتتیک ⚠️"
            : "تأییدنشده";
        infoEl.innerHTML = `
          <div class="icard"><h4>نماد</h4><div class="big">${res.display_symbol || res.symbol}</div>
            <div class="meta">${res.name_fa || ""} — ${res.name_en || ""}</div></div>
          <div class="icard"><h4>بروکر</h4><div class="big">${res.broker_name || "—"}</div>
            <div class="meta">${res.venue || ""}</div></div>
          <div class="icard"><h4>قیمت آخر</h4><div class="big">${fmtPrice(res.last_price)}</div>
            <div class="meta">منبع: ${res.source || ""} · ${trustFa}</div></div>
          <div class="icard"><h4>تعداد کندل</h4><div class="big">${res.count}</div>
            <div class="meta">تایم‌فریم ${res.timeframe || ""}</div></div>
        `;
      }
    } catch (e) {
      console.error("Forex chart failed", e);
    }

    // Volume profile recompute after data load
    if (this.volumeProfileOverlay && this.volumeProfileOverlay.enabled) {
      try { this.volumeProfileOverlay.refresh(); } catch (e) {}
    }

    // حمایت/مقاومت خودکار بعد از هر لود
    if (srOn && this.chart) {
      try { this.toggleSupportResistance(true); } catch (e) {}
    }
  };

  // init() خودش در پایان، loadData (که حالا override شده) را صدا می‌زند
  await forexChart.init();


  // پنل اندیکاتورها (اسیلاتور پایین + اورلی روی قیمت) — همگام با دکمه‌های UI
  const oscSeg = document.getElementById("indOsc");
  const activeOscBtn = oscSeg && oscSeg.querySelector("button.active");
  if (!indicatorPane) {
    indicatorPane = new IndicatorPane({ oscContainerId: "forexOscChart", mainChart: forexChart.chart });
    indicatorPane.setOscillator(activeOscBtn ? activeOscBtn.dataset.osc : null);
  } else {
    indicatorPane.mainChart = forexChart.chart;
    indicatorPane.oscChart = null; // چارت قبلی نابود شده، دوباره ساخته شود
    indicatorPane.oscSeries = [];
    indicatorPane.setOscillator(activeOscBtn ? activeOscBtn.dataset.osc : null);
  }
  const ovSeg2 = document.getElementById("indOverlay");
  if (ovSeg2) {
    ovSeg2.querySelectorAll("button.active").forEach((b) => {
      try { indicatorPane.toggleOverlay(b.dataset.ov); } catch (e) {}
    });
  }

  // کنترلر رپلای
  replayCtrl = new ReplayController({
    chart: forexChart.chart,
    candleSeries: forexChart.candleSeries,
    volumeSeries: forexChart.volumeSeries,
    ma20Series: forexChart.ma20Series,
    ma50Series: forexChart.ma50Series,
    emaSeries: forexChart.emaSeries,
    getData: () => ({ candles: forexChart.currentData || [], indicators: forexChart._indicatorData || null }),
    onStatus: updateReplayUI,
    onEnd: () => stopReplay(true),
  });

  // اگر کاربر قبل از لود چارت ولیو پرفایل را روشن کرده بود، حالا اعمال کن
  if (volumeProfileOn) applyVolumeProfileState();

}

export function bindForexTab() {
  const loadAndBuild = () =>
    loadSymbolList().then(() => {
      buildSymbolButtons();
      buildBrokerButtons();
    });
  // در حالت خصوصی، قبل از ورود درخواست نده (بدون نویز 401) — فقط با فعال‌سازی تب یا auth:ok
  events.on("auth:ok", loadAndBuild);
  events.on("tab:activated", (id) => {
    if (id === "forex") loadAndBuild();
  });

  document.querySelectorAll("#forexTf button").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll("#forexTf button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentForexTf = btn.dataset.tf;
      if (forexChart) {
        forexChart.setTimeframe(currentForexTf);
      }
    };
  });

  bindVolumeProfileToggle();
  buildReplayUI();
  bindIndicatorControls();
  bindSrToggle();

  // When forex tab is opened, init chart
  const observer = new MutationObserver(() => {
    const panel = document.getElementById("tab-forex");
    if (panel && panel.classList.contains("active")) {
      initForexChart();
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });

  // Also bind via mainTabs click
  document.querySelectorAll('[data-tab="forex"]').forEach((btn) => {
    btn.addEventListener("click", () => setTimeout(initForexChart, 100));
  });
}

// Auto bind
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindForexTab);
} else {
  bindForexTab();
}
