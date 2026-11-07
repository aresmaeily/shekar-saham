/**
 * main.js — بوت‌استرپ معماری v3 (Meta)
 * وظایف: سوار کردن core، ثبت تب‌ها، refresh مرکزی، رویدادهای سراسری.
 * هیچ منطق رندر جدولی اینجا نیست؛ همه در tabs/ و components/.
 */
import { store } from "./core/store.js";
import { api, toast } from "./core/api.js";
import { esc, fmtNum } from "./core/format.js";
import { events } from "./core/events.js";
import { renderThermometer } from "./components/thermometer.js";
import { renderTrustBanner } from "./modules/render/trust.js";
import { updateVersionFromApi } from "./modules/utils/version.js";

/* ماژول‌های تخصصی (اثر جانبی: بایند خودکار) */
import "./modules/theme.js";
import { initAlertInbox } from "./modules/alert_inbox.js"; // GOV-41 D-AI-30 in-product inbox
import "./modules/auth.js";
import "./modules/forex.js";
import "./modules/render/chart_pro.js"; // WS-10 CH-3: چارت حرفه‌ای — بایند-on-demand مثل forex
import "./modules/render/strategy_lab.js"; // MASTER-RADAR (2026-11-04): آزمایشگاه استراتژی + مدیر اندیکاتور — بایند-on-demand
import "./modules/render/backtest_center.js"; // MASTER-RADAR WAVE-2 (2026-11-04): مرکز بک‌تست — بایند-on-demand
import "./modules/render/forward_center.js"; // MASTER-RADAR WAVE-2 (2026-11-04): مرکز فوروارد تست — بایند-on-demand
import "./modules/render/data_quality_center.js"; // MASTER-RADAR WAVE-2 (2026-11-04): مرکز کیفیت داده — بایند-on-demand
import "./modules/render/chart_grid.js"; // MASTER-RADAR WAVE-3 (2026-11-04): شبکه چندچارتی با همگام‌سازی پیکربندی‌پذیر — بایند-on-demand
import "./modules/command_palette.js"; // MASTER-RADAR WAVE-3 (2026-11-04): پالت فرمان (Ctrl+K) — فقط اجرای صریح کاربر
import "./modules/render/user_indicator_ui.js"; // MASTER-RADAR WAVE-B (2026-11-04): اندیکاتور شخصی UIDL-1 — بایند-on-demand، اجرا فقط سمت سرور
import "./modules/render/product_loops_ui.js"; // MASTER-RADAR WAVE-F (2026-11-05): حلقه‌های محصول §5 — بایند-on-demand، همه داده SYNTHETIC/DECLARED
import "./modules/render/ai2_studio.js"; // MASTER-RADAR WAVE-O (2026-11-06): استودیو AI-2 — سطح UX خط لوله تولید حاکمیت‌شده /api/v10/ai2 — بایند-on-demand، برچسب‌ها فقط از سرور، بدون polling
import { bindAiMa } from "./modules/render/ai_ma_ui.js"; // WAVE-AI (2026-11-08): هوش چندعاملی AI-MA — وضعیت و اجرای ارکستراسیون مشورتی /api/v10/aima — بایند-on-demand، اجرای موازی محدود، برچسب‌ها فقط از سرور
import "./modules/render/watchlist_excellent.js";
import { renderAnalyticsFlow } from "./modules/render/analytics_flow.js"; // WDA-3 (2026-11-02): پنل افزودنی جمع‌بندی جریان در تب تحرکات بزرگان

/* لایه تب‌ها */
import * as T from "./tabs/data.js";
import { bindSettings, bindBacktest, bindOptions, bindNotify, bindFilter, bindFilterIntel, bindMap, bindFinal, setRefreshFn, renderFormOutputs } from "./tabs/forms.js";
import { addPortfolio, removePortfolio, openSymbol, openDeepFundamental } from "./tabs/actions.js";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

/* اگر حالت legacy خواسته شد، اسکریپت قدیمی خودش لود می‌شود */
// در حالت legacy، index.html main.js را حذف و اسکریپت‌های قدیمی را لود می‌کند
const isLegacyMode = new URLSearchParams(location.search).has("legacy");

/* ----------------------------- رندر تب‌ها ----------------------------- */
const TAB_RENDERERS = {
  final: T.finalTab,
  hunt: T.hunt,
  exit: T.exit,
  hot: T.hot,
  big: T.big,
  tablo: T.tablo,
  game: T.game,
  industry: T.industry,
  fund: T.fund,
  value: T.value,
  portfolio: T.portfolio,
  alerts: T.alerts,
  watch: T.watch,
  map: T.marketMap,
  live: renderLive,
};

function renderActiveTab() {
  const active = $(".tab.active")?.dataset.tab;
  if (active && TAB_RENDERERS[active]) {
    try {
      TAB_RENDERERS[active]();
    } catch (e) {
      console.error(`render tab "${active}" failed`, e);
    }
  }
}

function renderAll() {
  renderThermometer(store.get().analysis?.overview?.thermometer);
  Object.keys(TAB_RENDERERS).forEach((k) => {
    try {
      TAB_RENDERERS[k]();
    } catch (e) {
      console.error(`render tab "${k}" failed`, e);
    }
  });
  renderFormOutputs();
  renderStats();
  renderAnalyticsFlow(); // WDA-3 (2026-11-02): پنل افزودنی جریان تحلیلی — fetch-once داخل ماژول
}

/* ----------------------------- stats bar ----------------------------- */
function renderStats() {
  const ov = store.get().analysis?.overview;
  if (!ov) return;
  $("#stSymbols").textContent = fmtNum(ov.symbol_count);
  $("#stPos").textContent = fmtNum(ov.positive_count);
  $("#stNeg").textContent = fmtNum(ov.negative_count);
  $("#stEntry").textContent = fmtNum(ov.entry_alerts);
  $("#stExit").textContent = fmtNum(ov.exit_alerts);
  $("#stBig").textContent = fmtNum(store.get().bigMoves?.length || ov.big_moves || 0);
  $("#stHot").textContent = fmtNum(ov.hot_money_count);
  const pf = store.get().portfolio?.length || 0;
  const snaps = store.get().analysis?.store?.snapshots ?? 0;
  $("#stPort").textContent = `${fmtNum(pf)} / ${fmtNum(snaps)}`;
}

/* ----------------------------- refresh مرکزی ----------------------------- */
async function refreshApp(force = false) {
  const btn = $("#btnRefresh");
  btn?.classList.add("loading");
  try {
    const q = force ? "true" : "false";
    const sizeBy = $("#mapSize")?.value || "tval";
    const colorBy = $("#mapColor")?.value || "plp";
    const [data, big, tablo, pf, alerts, th, mmap, funds, valuePack, conf, presets, saved] = await Promise.all([
      api(`/api/analyze?force=${q}`),
      api(`/api/big-moves?window_sec=${store.get().bigWindow}&limit=100`),
      api(`/api/tablocastic?limit=120`),
      api(`/api/portfolio`),
      api(`/api/alerts?limit=150`),
      store.get().thresholds ? Promise.resolve(store.get().thresholds) : api(`/api/config/thresholds`),
      api(`/api/market-map?size_by=${sizeBy}&color_by=${colorBy}`),
      api(`/api/fundamentals?limit=120`),
      api(`/api/fundamentals/value?limit=50&max_pe=${$("#valMaxPe")?.value || 18}&min_score=${$("#valMinScore")?.value || 55}`),
      api(`/api/confluence?limit=80`),
      store.get().filterPresets.length ? Promise.resolve({ presets: store.get().filterPresets, fields: store.get().filterFields }) : api(`/api/filter/presets`),
      api(`/api/filter/saved`),
    ]);

    store.set({
      analysis: data,
      bigMoves: big,
      tablocastic: tablo,
      portfolio: pf,
      alerts,
      thresholds: store.get().thresholds || th,
      marketMap: mmap,
      fundamentals: funds,
      valueStocks: valuePack.rows || [],
      valueScoring: valuePack.scoring || null,
      confluence: conf,
      filterPresets: presets.presets || store.get().filterPresets,
      filterFields: presets.fields || store.get().filterFields,
      savedFilters: saved || [],
    });

    renderAll();
    updateSource(data.overview?.source, data.data_trust);
    updateTrust(data.data_trust || data.trust_level || data.overview?.source);

    const t = data.overview?.as_of ? new Date(data.overview.as_of).toLocaleString("fa-IR") : new Date().toLocaleString("fa-IR");
    $("#lastUpdate").textContent = `آخرین بروزرسانی: ${t} · v3-meta`;

    if (!store.get().notifyCfg) {
      try {
        store.set({ notifyCfg: await api("/api/notify/config") });
      } catch (e) { /* toast */ }
    }
  } catch (e) {
    console.error("refresh failed", e);
  } finally {
    btn?.classList.remove("loading");
  }
}

/* ----------------------------- منبع / اعتماد ----------------------------- */
function isVerifiedLive(dt) {
  return !!(dt && typeof dt === "object"
    && String(dt.state || "").toLowerCase() === "live"
    && dt.is_live === true
    && dt.live_verified === true);
}

function updateSource(source, dataTrust) {
  const pill = $("#sourcePill");
  const text = $("#sourceText");
  if (!pill || !text) return;
  pill.classList.remove("live", "mock");
  const s = source || "—";
  if (isVerifiedLive(dataTrust)) {
    pill.classList.add("live");
    text.textContent = "منبع تأییدشده · " + s;
  } else if (String(s).includes("mock")) {
    pill.classList.add("mock");
    text.textContent = "داده دمو";
  } else {
    pill.classList.add("mock");
    text.textContent = "منبع تأییدنشده · " + s;
  }
}

function updateTrust(levelOrTrust) {
  const pill = $("#trustPill");
  const text = $("#trustText");
  if (!pill || !text) return;
  pill.classList.remove("live", "mock");
  const obj = typeof levelOrTrust === "object" && levelOrTrust ? levelOrTrust : {};
  const state = obj.state
    ? String(obj.state || obj.trust_level || "mixed").toLowerCase()
    : String(levelOrTrust || "mixed").toLowerCase();
  if (isVerifiedLive(obj)) {
    pill.classList.add("live");
    text.textContent = "LIVE";
  } else {
    pill.classList.add("mock");
    const labels = {
      live: "UNVERIFIED LIVE-CLASS",
      mock: "MOCK / آزمایشی",
      synthetic: "SYNTHETIC / شبیه‌سازی",
      stale: "STALE / قدیمی",
      unavailable: "UNAVAILABLE / ناموجود",
      mixed: "MIXED / ترکیبی",
    };
    text.textContent = labels[state] || "NOT LIVE";
  }
  try {
    renderTrustBanner(levelOrTrust);
  } catch (e) { /* banner optional */ }
}

/* ----------------------------- WebSocket + تب لایو ----------------------------- */
function renderLive() {
  const m = store.get().live;
  const cards = $("#liveCards");
  if (!cards) return;
  if (!m) {
    cards.innerHTML = `<div class="icard"><h4>وضعیت</h4><div class="meta">هنوز پیامی دریافت نشده — اتصال WS را چک کنید.</div></div>`;
    return;
  }
  const ov = m.overview || {};
  cards.innerHTML = [
    ["منبع", m.source || "—"], ["نمادها", ov.symbol_count], ["ورود", ov.entry_alerts],
    ["خروج", ov.exit_alerts], ["حجم مشکوک", ov.volume_spikes], ["پول داغ", ov.hot_money_count],
  ]
    .map(([l, v]) => `<div class="icard"><h4>${esc(l)}</h4><div class="big">${esc(v)}</div></div>`)
    .join("");
  const tb = $("#liveEntryTable tbody");
  if (tb) {
    tb.innerHTML = (m.entry_signals || [])
      .map((r) => `<tr data-symbol="${esc(r.symbol)}"><td><span class="sym">${esc(r.symbol)}</span></td><td>${fmtNum(r.plp, 2)}٪</td><td>${fmtNum(r.buy_power, 2)}</td><td>${fmtNum(r.volume_ratio, 2)}</td></tr>`)
      .join("") || `<tr><td colspan="4" class="empty">—</td></tr>`;
  }
}

let ws = null;
function connectWs() {
  try {
    if (ws) { try { ws.close(); } catch (e) {} }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    // کوکی نشست به‌صورت خودکار در handshake WS ارسال می‌شود (هم‌مبدأ)
    ws = new WebSocket(`${proto}://${location.host}/ws/live`);
    ws.onopen = () => { $("#wsText").textContent = "WS متصل"; $("#wsPill").classList.add("live"); };
    ws.onclose = () => { $("#wsText").textContent = "WS قطع"; $("#wsPill").classList.remove("live"); if (store.get().auto) setTimeout(connectWs, 4000); };
    ws.onerror = () => { $("#wsText").textContent = "WS خطا"; };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "market_update") {
          store.set({ live: msg });
          if (store.get().analysis && msg.overview) {
            const ov = { ...store.get().analysis.overview, ...msg.overview };
            store.set({ analysis: { ...store.get().analysis, overview: ov } });
            renderThermometer(ov.thermometer);
            renderStats();
          }
          renderLive();
        }
      } catch (e) { /* ignore */ }
    };
  } catch (e) { /* ignore */ }
}

/* ----------------------------- بایند ناوبری و سراسری ----------------------------- */
function bindNav() {
  const nav = $("#mainTabs");
  if (!nav) return;
  nav.addEventListener("click", (e) => {
    const btn = e.target.closest(".tab[data-tab]");
    if (!btn) return;
    $$("#mainTabs .tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    $$(".panel").forEach((p) => p.classList.remove("active"));
    const panel = $("#tab-" + btn.dataset.tab);
    if (panel) panel.classList.add("active");
    renderActiveTab();
    // فعال‌سازی تاخیری فارکس (چارت سنگین است)
    history.replaceState(null, "", "#/" + btn.dataset.tab);
  });
  // GOV-24/WP-3 (D-24-3): پل hash → تب. تا پیش از این، هش فقط «نوشته» می‌شد (replaceState
  // در کلیک) و هیچ‌گاه «خوانده» نمی‌شد — دیپ‌لینک‌های /#/<tab> (لینک‌های صفحه نماد، منوی
  // دسکتاپ، بوکمارک‌ها) روی تب پیش‌فرض می‌ماندند. روتر.js هم هرگز import نشده بود (کد مرده).
  const activateFromHash = () => {
    const id = (location.hash || "").replace(/^#\/?/, "");
    if (!id) return;
    const btn = nav.querySelector('.tab[data-tab="' + CSS.escape(id) + '"]');
    if (btn && !btn.classList.contains("active")) btn.click();
  };
  window.addEventListener("hashchange", activateFromHash);
  activateFromHash(); // دیپ‌لینک اولیه (باز شدن مستقیم /#/forex و مانند آن)
}

function bindGlobalDelegation() {
  document.addEventListener("click", async (e) => {
    const deepBtn = e.target.closest("[data-deep-sym]");
    if (deepBtn) { e.stopPropagation(); openDeepFundamental(deepBtn.dataset.deepSym); return; }
    const add = e.target.closest("[data-add]");
    if (add) { e.stopPropagation(); try { await addPortfolio(add.dataset.add); } catch (err) {} return; }
    const del = e.target.closest("[data-del]");
    if (del) { e.stopPropagation(); try { await removePortfolio(del.dataset.del); } catch (err) {} return; }
    const cell = e.target.closest("[data-symbol]");
    if (cell && !e.target.closest("button,a")) {
      if (e.detail === 2) { location.href = "/symbol?s=" + encodeURIComponent(cell.dataset.symbol); return; }
      if (cell.closest("#fundTable") || cell.closest("#valueTable")) { openDeepFundamental(cell.dataset.symbol); return; }
      openSymbol(cell.dataset.symbol, { event: e });
    }
  });
  $("#modalClose")?.addEventListener("click", () => $("#symbolModal")?.classList.add("hidden"));
  $("#symbolModal")?.addEventListener("click", (e) => { if (e.target.id === "symbolModal") $("#symbolModal").classList.add("hidden"); });
  $("#deepFundClose")?.addEventListener("click", () => $("#deepFundModal")?.classList.add("hidden"));
  $("#deepFundModal")?.addEventListener("click", (e) => { if (e.target.id === "deepFundModal") $("#deepFundModal").classList.add("hidden"); });
  $("#btnDeepFund")?.addEventListener("click", () => { const sym = ($("#deepSym")?.value || "فملی").trim(); if (sym) openDeepFundamental(sym); });
}

function bindTopbar() {
  $("#btnRefresh")?.addEventListener("click", () => refreshApp(true));
  $("#btnAuto")?.addEventListener("click", () => {
    const on = !store.get().auto;
    store.set({ auto: on });
    $("#btnAuto").dataset.on = on ? "1" : "0";
    $("#btnAuto").innerHTML = on ? '<span class="icon">●</span> خودکار' : '<span class="icon">○</span> متوقف';
    setupTimer();
  });
  $("#btnWsReconnect")?.addEventListener("click", connectWs);
}

/* WAVE-AB2 (2026-11-08): سیم‌کشی کنترل‌های مرده ثبت‌شده در ممیزی WP-J —
 * هیچ رفتار موجودی تغییر نمی‌کند؛ فقط کنترل‌هایی که در HTML بودند اما هیچ
 * شنونده‌ای نداشتند، حالا واقعاً کار می‌کنند (صادقانه، بدون داده جعل). */
function bindDataFilters() {
  const reHunt = () => T.hunt();
  const reTablo = () => T.tablo();
  const reHot = () => T.hot();
  const reValue = () => T.value();

  // فیلترهای تب شکار (قبلاً هرگز خوانده نمی‌شدند)
  $("#fNegOnly")?.addEventListener("change", reHunt);
  $("#fFundOnly")?.addEventListener("change", reHunt);
  $("#fMinScore")?.addEventListener("input", () => {
    const el = $("#fMinScoreVal");
    if (el) el.textContent = $("#fMinScore").value;
    reHunt();
  });

  // اسلایدر تابلوکستیک (در رندر خوانده می‌شد اما هرگز رفرش نمی‌کرد)
  $("#fTabloQ")?.addEventListener("input", () => {
    const el = $("#fTabloQVal");
    if (el) el.textContent = $("#fTabloQ").value;
    reTablo();
  });

  // کنترل‌های سگمنتی درجه/تییر/نما (فقط نمایشی — بدون هیچ درخواست شبکه‌ای)
  const wireSeg = (id, key, attr, rerender) => {
    const seg = $(id);
    if (!seg) return;
    seg.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-" + attr + "]");
      if (!b) return;
      seg.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      store.set({ [key]: b.dataset[attr] });
      rerender();
    });
  };
  wireSeg("#tabloGrade", "tabloGrade", "g", reTablo);
  wireSeg("#hotTier", "hotTier", "tier", reHot);
  wireSeg("#hotView", "hotView", "view", reHot);

  // دکمه refresh تب «زنده» — POST /api/refresh سپس refresh مرکزی
  $("#btnWsRefresh")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const idle = btn.textContent;
    btn.disabled = true;
    btn.textContent = "در حال درخواست refresh…";
    try {
      await api("/api/refresh", { method: "POST" });
      await refreshApp(true);
      toast("refresh سرور انجام شد", "success");
    } catch (err) {
      toast("refresh سرور ناموفق بود — جزئیات در کنسول", "error");
      console.error("ws refresh failed", err);
    } finally {
      btn.disabled = false;
      btn.textContent = idle;
    }
  });

  // دکمه بروزرسانی تب ارزش‌گذاری — واکشی مجدد همان API ارزش‌گذاری
  $("#btnValueReload")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const idle = btn.textContent;
    btn.disabled = true;
    btn.textContent = "در حال بروزرسانی…";
    try {
      const pack = await api(`/api/fundamentals/value?limit=50&max_pe=${$("#valMaxPe")?.value || 18}&min_score=${$("#valMinScore")?.value || 55}`);
      store.set({ valueStocks: pack.rows || [], valueScoring: pack.scoring || null });
      reValue();
      toast("ارزش‌گذاری بروزرسانی شد", "success");
    } catch (err) {
      toast("بروزرسانی ارزش‌گذاری ناموفق بود", "error");
      console.error("value reload failed", err);
    } finally {
      btn.disabled = false;
      btn.textContent = idle;
    }
  });

  // فرم افزودن درون‌خطی پورتفو (کنار جدول پورتفو)
  $("#btnPfAdd")?.addEventListener("click", async () => {
    const sym = ($("#pfSymbol")?.value || "").trim();
    if (!sym) { toast("نماد را وارد کنید", "error"); return; }
    try {
      await addPortfolio(sym);
      if ($("#pfSymbol")) $("#pfSymbol").value = "";
      if ($("#pfNote")) $("#pfNote").value = "";
      toast("به پورتفو اضافه شد", "success");
    } catch (err) {
      toast("افزودن به پورتفو ناموفق بود", "error");
    }
  });
}

/* WAVE-AB2: فعال‌سازی تب «عالی» — ماژول render/excellent.js از قبل موجود بود
 * اما هیچ‌کس آن را import نمی‌کرد و پنل‌ها برای همیشه «در حال بارگذاری…»
 * می‌ماندند. اکنون هنگام باز شدن تب یک‌بار رندر می‌شوند (فقط با کنش کاربر). */
function bindExcellentTab() {
  let activated = false;
  const observer = new MutationObserver(() => {
    const panel = $("#tab-excellent");
    if (panel && panel.classList.contains("active") && !activated) {
      activated = true;
      import("./modules/render/excellent.js")
        .then((m) => {
          m.renderRisk?.();
          m.renderDataQuality?.();
          m.renderAnomalies?.();
          m.renderPortfolioOptimization?.();
        })
        .catch(() => { /* رندر عالی اختیاری است — در سکوت رد نمی‌شود، خطا داخل خود ماژول صادقانه نمایش داده می‌شود */ });
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
}

/* WAVE-AI (WP-C 2026-11-08): فعال‌سازی تب «هوش چندعاملی» — بایند-on-demand
 * هنگام باز شدن تب (فقط با کنش کاربر؛ هیچ polling و هیچ درخواست خودکاری). */
function bindAiMaTab() {
  let activated = false;
  const observer = new MutationObserver(() => {
    const panel = $("#tab-aima");
    if (panel && panel.classList.contains("active") && !activated) {
      activated = true;
      bindAiMa();
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
}

function setupTimer() {
  if (window.__timer) clearInterval(window.__timer);
  if (store.get().auto) window.__timer = setInterval(() => refreshApp(false), 30000);
}

/* ----------------------------- بوت ----------------------------- */
async function boot() {
  bindTopbar();
  bindNav();
  bindGlobalDelegation();
  bindDataFilters(); // WAVE-AB2: سیم‌کشی کنترل‌های مرده (شکار/تابلو/پول داغ/زنده/ارزش‌گذاری/پورتفو)
  bindExcellentTab(); // WAVE-AB2: فعال‌سازی تب «عالی» هنگام باز شدن
  bindAiMaTab(); // WAVE-AI: فعال‌سازی تب هوش چندعاملی هنگام باز شدن
  bindSettings();
  bindBacktest();
  bindOptions();
  bindNotify();
  bindFilter();
  bindFilterIntel();
  bindMap();
  bindFinal();
  setRefreshFn(refreshApp);

  events.on("auth-required", () => { /* auth.js صفحه قفل را نشان می‌دهد */ });

  // service worker (PWA)
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  }

  // گیت auth: در حالت خصوصی، refresh اول تا ورود مالک صبر می‌کند (بدون نویز 401)
  try {
    const st = await fetch("/api/auth/status", { credentials: "same-origin" }).then((r) => r.json());
    if (st && st.auth_required && !st.logged_in) {
      events.on("auth:ok", () => {
        refreshApp(true);
        setupTimer();
        connectWs();
        setTimeout(() => $("#btnOptLoad")?.click(), 1200);
      });
      return; // قفل نمایش داده می‌شود؛ refresh بعد از ورود
    }
  } catch (e) { /* سرور در دسترس نیست */ }

  refreshApp(true);
  setupTimer();
  connectWs();
  setTimeout(() => $("#btnOptLoad")?.click(), 1200);
}

/* در دسترس ماژول‌های قدیمی‌تر (watchlist_excellent و ...) */
window.refresh = refreshApp;
window.api = api;
window.store = store;

if (!isLegacyMode) {
  updateVersionFromApi(); // WS-HARDEN-1/W4: نسخه UI از API همگام می‌شود (تک‌منبع حقیقت: settings.version)
  initAlertInbox(); // GOV-41 D-AI-30: صندوق هشدارهای عملیاتی (درون‌محصولی)
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
}
