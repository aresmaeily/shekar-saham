/**
 * tabs/forms.js — تب‌های فرمی: تنظیمات / بک‌تست / اختیار / اعلان‌ها / فیلتر / نقشه / جمع‌بندی
 * همه از core/api استفاده می‌کنند؛ هیچ fetch مستقیمی.
 */
import { api, toast } from "../core/api.js";
import { esc, fmtNum, fmtMoney } from "../core/format.js";
import { store } from "../core/store.js";
import { finalTab } from "./data.js";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const TH_META = [
  { key: "entry_score_alert", label: "آستانه هشدار ورود" },
  { key: "entry_score_strong", label: "سیگنال ورود قوی" },
  { key: "exit_score_alert", label: "آستانه هشدار خروج" },
  { key: "volume_spike_ratio", label: "نسبت حجم مشکوک" },
  { key: "volume_spike_strong", label: "حجم خیلی مشکوک" },
  { key: "buy_power_min", label: "حداقل قدرت خریدار" },
  { key: "buy_power_strong", label: "قدرت خریدار قوی" },
  { key: "smart_per_capita_min", label: "حداقل سرانه پول هوشمند" },
  { key: "hot_money_threshold", label: "آستانه پول داغ" },
  { key: "hot_money_plus_min", label: "کف پول داغ پلاس" },
  { key: "hot_money_plus_max", label: "سقف پول داغ پلاس" },
  { key: "near_buy_queue_pct", label: "نزدیکی صف خرید (٪)" },
  { key: "pe_max_attractive", label: "P/E جذاب حداکثر" },
  { key: "pe_max_ok", label: "P/E قابل قبول حداکثر" },
  { key: "big_move_window_sec", label: "پنجره تحرکات (ثانیه)" },
  { key: "big_move_min_score", label: "حداقل امتیاز تحرکات" },
  { key: "poll_seconds", label: "بازه رفرش سرور (ثانیه)" },
];

/* ----------------------------- تنظیمات ----------------------------- */
export function bindSettings() {
  const grid = $("#settingsGrid");
  if (!grid) return;

  function render() {
    const th = store.get().thresholds;
    if (!th) return;
    grid.innerHTML = TH_META.map(
      (m) => `
      <div class="setting-card">
        <label for="th_${m.key}">${esc(m.label)}</label>
        <input id="th_${m.key}" data-th="${m.key}" type="number" step="any" value="${esc(th[m.key] ?? "")}" />
      </div>`
    ).join("");
  }
  // رندر فقط وقتی thresholds برای اولین بار می‌رسد
  let rendered = false;
  store.subscribe(() => {
    if (!rendered && store.get().thresholds) {
      rendered = true;
      render();
    }
  });

  $("#btnSaveTh")?.addEventListener("click", async () => {
    const payload = {};
    $$("[data-th]").forEach((inp) => (payload[inp.dataset.th] = inp.value === "" ? null : Number(inp.value)));
    try {
      store.set({ thresholds: await api("/api/config/thresholds", { method: "PUT", body: JSON.stringify(payload) }) });
      render();
      $("#settingsMsg").textContent = "ذخیره شد — در حال اعمال…";
      await refreshApp();
      $("#settingsMsg").textContent = "تنظیمات اعمال شد.";
    } catch (e) { /* toast از api */ }
  });

  $("#btnResetTh")?.addEventListener("click", async () => {
    try {
      store.set({ thresholds: await api("/api/config/thresholds/reset", { method: "POST" }) });
      render();
      $("#settingsMsg").textContent = "به پیش‌فرض برگشت.";
      await refreshApp();
    } catch (e) { /* toast */ }
  });
}

/* ----------------------------- بک‌تست ----------------------------- */
export function bindBacktest() {
  $("#btnBtRun")?.addEventListener("click", async () => {
    $("#btNotes").textContent = "در حال اجرای بک‌تست…";
    try {
      const res = await api("/api/backtest/run", {
        method: "POST",
        body: JSON.stringify({
          entry_threshold: Number($("#btEntry").value || 65),
          exit_threshold: Number($("#btExit").value || 60),
          take_profit: Number($("#btTp").value || 4),
          stop_loss: Number($("#btSl").value || -3),
          max_hold_bars: Number($("#btHold").value || 24),
          fee_pct: Number($("#btFee").value || 0.5),
          bars: Number($("#btBars").value || 80),
        }),
      });
      store.set({ backtest: res.result });
      renderBacktest();
    } catch (e) { /* toast */ }
  });
}

function renderBacktest() {
  const r = store.get().backtest;
  const cards = $("#btCards");
  if (!cards) return;
  if (!r) {
    cards.innerHTML = `<div class="icard"><h4>آماده</h4><div class="meta">پارامترها را تنظیم و اجرا کنید.</div></div>`;
    return;
  }
  cards.innerHTML = [
    ["حالت", r.mode], ["معاملات", r.trades], ["برد٪", r.win_rate], ["میانگین بازده", r.avg_return],
    ["میانه", r.median_return], ["جمع بازده", r.total_return_sum], ["Max DD", r.max_drawdown],
    ["Profit Factor", r.profit_factor], ["Sharpe~", r.sharpe_like], ["نگهداری میانگین", r.avg_holding_bars],
  ]
    .map(([l, v]) => `<div class="icard"><h4>${l}</h4><div class="big" style="font-size:1.15rem">${typeof v === "number" ? fmtNum(v, 2) : esc(v)}</div></div>`)
    .join("");
  const eq = r.equity_curve || [];
  const maxAbs = Math.max(...eq.map((x) => Math.abs(x.equity)), 0.1);
  $("#btEquity").innerHTML = eq
    .map((p) => `<i class="${p.equity < 0 ? "neg" : ""}" style="height:${Math.max(4, (Math.abs(p.equity) / maxAbs) * 70)}px" title="${p.equity}"></i>`)
    .join("");
  $("#btTrades tbody").innerHTML = (r.trades_sample || [])
    .map((t) => `<tr data-symbol="${esc(t.symbol)}"><td><span class="sym">${esc(t.symbol)}</span></td><td>${fmtNum(t.entry_price)}</td><td>${fmtNum(t.exit_price)}</td><td class="${t.ret_pct >= 0 ? "pct-up" : "pct-down"}">${fmtNum(t.ret_pct, 2)}</td><td>${fmtNum(t.holding_bars)}</td><td>${esc(t.exit_reason)}</td><td>${fmtNum(t.entry_score, 1)}</td></tr>`)
    .join("") || `<tr><td colspan="7" class="empty">معامله‌ای نیست</td></tr>`;
  $("#btNotes").textContent = (r.notes || []).join(" · ");
}

/* ----------------------------- اختیار معامله ----------------------------- */
export function bindOptions() {
  $("#btnOptLoad")?.addEventListener("click", async () => {
    const sym = ($("#optSymbol").value || "فملی").trim();
    try {
      store.set({ options: await api("/api/options/" + encodeURIComponent(sym)) });
      renderOptions();
    } catch (e) { /* toast */ }
  });
  $("#btnOptPrice")?.addEventListener("click", async () => {
    try {
      const res = await api("/api/options/price", {
        method: "POST",
        body: JSON.stringify({
          spot: Number($("#opSpot").value), strike: Number($("#opStrike").value),
          days: Number($("#opDays").value || 30), vol: Number($("#opVol").value || 0.35),
          rate: Number($("#opRate").value || 0.25), option_type: $("#opType").value, side: "buy",
        }),
      });
      const g = res.greeks || {};
      $("#optPriceOut").innerHTML = [
        ["قیمت تئوریک", g.price], ["Delta", g.delta], ["Gamma", g.gamma], ["Vega", g.vega],
        ["Theta", g.theta], ["Intrinsic", g.intrinsic], ["Time value", g.time_value], ["Implied move", res.implied_move],
      ]
        .map(([k, v]) => `<div><span>${k}</span><b>${fmtNum(v, 4)}</b></div>`)
        .join("");
      const payoff = res.payoff || [];
      const maxAbs = Math.max(...payoff.map((p) => Math.abs(p.pnl)), 0.1);
      $("#optPayoff").innerHTML = payoff
        .map((p) => `<i class="${p.pnl < 0 ? "neg" : ""}" style="height:${Math.max(3, (Math.abs(p.pnl) / maxAbs) * 70)}px" title="${p.spot}:${p.pnl}"></i>`)
        .join("");
    } catch (e) { /* toast */ }
  });
}

function renderOptions() {
  const o = store.get().options;
  if (!o) return;
  $("#optCards").innerHTML = [
    ["نماد", o.symbol], ["Spot", o.spot], ["Vol", o.vol], ["حرکت ضمنی ۳۰روز", o.implied_move_30d],
    ["امتیاز ورود", o.entry_score], ["امتیاز خروج", o.exit_score],
  ]
    .map(([l, v]) => `<div class="icard"><h4>${l}</h4><div class="big">${typeof v === "number" ? fmtNum(v, 2) : esc(v)}</div></div>`)
    .join("");
  $("#optStrategies").innerHTML = (o.strategies || [])
    .map((s) => `<div class="icard"><h4>${esc(s.name)} <span class="score ${s.score >= 65 ? "mid" : "low"}">${fmtNum(s.score, 0)}</span></h4><div class="meta">${esc(s.summary || "")}<br/>bias: ${esc(s.bias || "")}</div></div>`)
    .join("");
  const exp = (o.expiries || [])[0];
  const rows = exp?.strikes || [];
  $("#optChainTable tbody").innerHTML = rows
    .map((r) => `<tr><td><b>${fmtNum(r.strike)}</b></td><td>${fmtNum(r.call?.market ?? r.call?.price, 1)}</td><td>${fmtNum(r.call?.delta, 3)}</td><td>${fmtNum(r.put?.market ?? r.put?.price, 1)}</td><td>${fmtNum(r.put?.delta, 3)}</td><td>${fmtNum(r.moneyness, 3)}</td></tr>`)
    .join("");
  if (!$("#opSpot").value) $("#opSpot").value = o.spot;
  if (!$("#opStrike").value) $("#opStrike").value = Math.round(o.spot / 10) * 10;
  if (o.vol) $("#opVol").value = o.vol;
}

/* ----------------------------- اعلان‌ها ----------------------------- */
export function bindNotify() {
  $("#btnNotifySave")?.addEventListener("click", async () => {
    const payload = {
      enabled: $("#nfEnabled").value === "1",
      telegram_chat_id: $("#nfTgChat").value.trim(),
      bale_chat_id: $("#nfBaleChat").value.trim(),
      min_entry_score: Number($("#nfMinEntry").value || 80),
      min_exit_score: Number($("#nfMinExit").value || 70),
      min_combo_buy: Number($("#nfMinComboBuy")?.value || 70),
      min_combo_sell: Number($("#nfMinComboSell")?.value || 65),
      cooldown_sec: Number($("#nfCool").value || 900),
      portfolio_only: $("#nfPfOnly").value === "1",
      confluence_enabled: $("#nfCombo")?.value !== "0",
      legacy_tablo_alerts: $("#nfLegacy")?.value === "1",
    };
    if ($("#nfTgToken").value.trim()) payload.telegram_token = $("#nfTgToken").value.trim();
    if ($("#nfBaleToken").value.trim()) payload.bale_token = $("#nfBaleToken").value.trim();
    try {
      store.set({ notifyCfg: await api("/api/notify/config", { method: "PUT", body: JSON.stringify(payload) }) });
      fillNotifyForm();
      $("#notifyMsg").textContent = "تنظیمات اعلان ذخیره شد.";
      loadNotifyLog();
    } catch (e) { /* toast */ }
  });

  $("#btnNotifyTest")?.addEventListener("click", async () => {
    try {
      const res = await api("/api/notify/test", {
        method: "POST",
        body: JSON.stringify({ text: "تست هشدار شکار سهام ✅ " + new Date().toLocaleString("fa-IR") }),
      });
      store.set({ notifyCfg: res.config });
      fillNotifyForm();
      $("#notifyMsg").textContent = "نتیجه تست: " + JSON.stringify(res.result);
      loadNotifyLog();
    } catch (e) { /* toast */ }
  });

  let notifyReady = false;
  store.subscribe(() => {
    if (!notifyReady && store.get().notifyCfg) {
      notifyReady = true;
      fillNotifyForm();
    }
  });
}

function fillNotifyForm() {
  const c = store.get().notifyCfg || {};
  if ($("#nfEnabled")) $("#nfEnabled").value = c.enabled ? "1" : "0";
  if ($("#nfTgChat")) $("#nfTgChat").value = c.telegram_chat_id || "";
  if ($("#nfBaleChat")) $("#nfBaleChat").value = c.bale_chat_id || "";
  if ($("#nfMinEntry")) $("#nfMinEntry").value = c.min_entry_score ?? 80;
  if ($("#nfMinExit")) $("#nfMinExit").value = c.min_exit_score ?? 70;
  if ($("#nfMinComboBuy")) $("#nfMinComboBuy").value = c.min_combo_buy ?? 70;
  if ($("#nfMinComboSell")) $("#nfMinComboSell").value = c.min_combo_sell ?? 65;
  if ($("#nfCool")) $("#nfCool").value = c.cooldown_sec ?? 900;
  if ($("#nfPfOnly")) $("#nfPfOnly").value = c.portfolio_only ? "1" : "0";
  if ($("#nfCombo")) $("#nfCombo").value = c.confluence_enabled === false ? "0" : "1";
  if ($("#nfLegacy")) $("#nfLegacy").value = c.legacy_tablo_alerts ? "1" : "0";
  const msg = $("#notifyMsg");
  if (msg) msg.textContent = `تلگرام: ${c.telegram_configured ? "پیکربندی‌شده" : "خیر"} · بله: ${c.bale_configured ? "پیکربندی‌شده" : "خیر"} · ارسال‌ها: ${c.sent_count ?? 0}`;
}

/** لود لاگ اعلان‌ها (ماژول-سطح، استفاده از bindNotify و bindFinal) */
export async function loadNotifyLog() {
  try {
    const rows = await api("/api/notify/log?limit=40");
    const tb = document.querySelector("#notifyLogTable tbody");
    if (!tb) return;
    tb.innerHTML = rows
      .map((r) => `<tr><td>${new Date(r.ts_iso).toLocaleString("fa-IR")}</td><td>${esc(r.channel || "")}</td><td>${r.ok ? "✓" : "✗"}</td><td class="reasons">${esc(String(r.payload?.text || "").slice(0, 160))}</td></tr>`)
      .join("") || `<tr><td colspan="4" class="empty">لاگی نیست</td></tr>`;
  } catch (e) { /* toast */ }
}

/* ----------------------------- فیلتر ----------------------------- */
export function bindFilter() {
  $("#btnFilterRun")?.addEventListener("click", runFilter);
  $("#btnFilterSave")?.addEventListener("click", saveFilter);

  async function runFilter() {
    const expr = $("#filterExpr")?.value || "";
    $("#filterMsg").textContent = "در حال اجرا…";
    try {
      const res = await api("/api/filter/run", { method: "POST", body: JSON.stringify({ expr, limit: 100 }) });
      store.set({ filterRows: res.rows || [] });
      $("#filterMsg").textContent = `${fmtNum(res.count)} نتیجه`;
      renderFilterTable();
    } catch (e) { /* toast */ }
  }

  async function saveFilter() {
    const expr = $("#filterExpr")?.value || "";
    const name = prompt("نام فیلتر:", "فیلتر من");
    if (!name) return;
    try {
      const res = await api("/api/filter/saved", { method: "POST", body: JSON.stringify({ name, expr }) });
      store.set({ savedFilters: res.filters || [] });
      renderFilterHelpers();
      $("#filterMsg").textContent = "ذخیره شد";
    } catch (e) { /* toast */ }
  }

  function renderFilterTable() {
    const rows = store.get().filterRows || [];
    $("#filterTable tbody").innerHTML = rows
      .map(
        (r) => `<tr data-symbol="${esc(r.symbol)}">
          <td><button class="btn tiny" data-add="${esc(r.symbol)}">＋</button> <a class="btn tiny" href="/symbol?s=${encodeURIComponent(r.symbol)}">↗</a></td>
          <td>${fmtNum(r.entry_score, 1)}</td>
          <td><span class="sym">${esc(r.symbol)}</span><span class="name">${esc(r.name || "")}</span></td>
          <td>${esc(r.industry || "—")}</td>
          <td class="${r.plp >= 0 ? "pct-up" : "pct-down"}">${fmtNum(r.plp, 2)}٪</td>
          <td>${fmtNum(r.buy_power, 2)}</td>
          <td>${fmtNum(r.volume_ratio, 2)}</td>
          <td>${r.pe != null ? fmtNum(r.pe, 1) : "—"}</td>
          <td>${(r.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</td>
        </tr>`
      )
      .join("") || `<tr><td colspan="11" class="empty">نتیجه‌ای نیست — عبارت را اجرا کنید.</td></tr>`;
  }

  function renderFilterHelpers() {
    const s = store.get();
    const presets = $("#filterPresets");
    if (presets && s.filterPresets?.length) {
      presets.innerHTML = s.filterPresets.map((p) => `<button class="btn tiny" data-preset="${esc(p.id)}">${esc(p.name)}</button>`).join("");
      $$("[data-preset]", presets).forEach((b) => {
        b.onclick = () => {
          const p = s.filterPresets.find((x) => x.id === b.dataset.preset);
          if (p) { $("#filterExpr").value = p.expr; runFilter(); }
        };
      });
    }
    const fields = $("#filterFields");
    if (fields && s.filterFields?.length) {
      fields.innerHTML = s.filterFields.slice(0, 40).map((f) => `<button type="button" data-field="${esc(f.key)}" title="${esc(f.label)}">${esc(f.key)}</button>`).join("");
      $$("[data-field]", fields).forEach((b) => {
        b.onclick = () => {
          const ta = $("#filterExpr");
          const start = ta.selectionStart || ta.value.length;
          ta.value = ta.value.slice(0, start) + b.dataset.field + ta.value.slice(start);
          ta.focus();
        };
      });
    }
    const saved = $("#savedFilters");
    if (saved) {
      saved.innerHTML = (s.savedFilters || [])
        .map((f) => `<button class="btn tiny" data-loadf="${f.id}">${esc(f.name)}</button><button class="btn tiny danger-outline" data-delf="${f.id}">×</button>`)
        .join("");
      $$("[data-loadf]", saved).forEach((b) => {
        b.onclick = () => {
          const f = s.savedFilters.find((x) => String(x.id) === String(b.dataset.loadf));
          if (f) { $("#filterExpr").value = f.expr; runFilter(); }
        };
      });
      $$("[data-delf]", saved).forEach((b) => {
        b.onclick = async () => {
          await api("/api/filter/saved/" + b.dataset.delf, { method: "DELETE" });
          store.set({ savedFilters: (await api("/api/filter/saved")) || [] });
          renderFilterHelpers();
        };
      });
    }
  }

  renderFilterHelpers();
  // به‌روزرسانی خودکار وقتی داده فیلتر از refresh می‌رسد
  let filterReady = false;
  store.subscribe(() => {
    const s = store.get();
    if (!filterReady && (s.filterPresets?.length || s.savedFilters?.length)) {
      filterReady = true;
      renderFilterHelpers();
    }
  });
}

/* ----------------------------- نقشه بازار + جمع‌بندی ----------------------------- */
export function bindMap() {
  $("#btnMapReload")?.addEventListener("click", loadMap);
  $("#mapSize")?.addEventListener("change", loadMap);
  $("#mapColor")?.addEventListener("change", loadMap);

  async function loadMap() {
    const sizeBy = $("#mapSize")?.value || "tval";
    const colorBy = $("#mapColor")?.value || "plp";
    try {
      store.set({ marketMap: await api(`/api/market-map?size_by=${sizeBy}&color_by=${colorBy}`) });
      renderMap();
    } catch (e) { /* toast */ }
  }
}

export function renderMap() {
  const mm = store.get().marketMap;
  const meta = $("#mapMeta");
  if (meta && mm) meta.textContent = `${fmtNum(mm.symbol_count)} نماد · ${fmtNum(mm.industry_count)} صنعت`;
}

export function bindFinal() {
  $$("#finalAction button").forEach((b) => {
    b.addEventListener("click", () => {
      $$("#finalAction button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      store.set({ finalAction: b.dataset.act });
      finalTab();
    });
  });
  $("#btnFinalReload")?.addEventListener("click", async () => {
    try {
      store.set({ confluence: await api("/api/confluence?force=true&limit=80") });
      finalTab();
      $("#finalMsg").textContent = "جمع‌بندی بروزرسانی شد.";
    } catch (e) { /* toast */ }
  });
  $("#btnFinalNotify")?.addEventListener("click", async () => {
    $("#finalMsg").textContent = "در حال ارسال هشدارها…";
    try {
      const res = await api("/api/confluence/notify-now", { method: "POST" });
      $("#finalMsg").textContent = res.preview_only
        ? (res.message || "پیش‌نمایش") + ` · ${res.alerts?.length || 0} هشدار آماده`
        : `ارسال شد: ${res.sent} · خرید: ${res.summary?.buy_alerts ?? "—"} · فروش: ${res.summary?.sell_alerts ?? "—"}`;
      loadNotifyLog();
    } catch (e) { /* toast */ }
  });
}

/* پل میان ماژول‌ها (توسط main.js مقداردهی می‌شود) */
let refreshApp = async () => {};
export function setRefreshFn(fn) {
  refreshApp = fn;
}

/* رندر خروجی‌های فرمی که بعد از refresh باید به‌روز شوند */
export function renderFormOutputs() {
  renderBacktest();
  if (store.get().options) renderOptions();
}
