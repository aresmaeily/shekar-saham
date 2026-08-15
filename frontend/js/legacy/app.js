/* رادار بورس v0.4 — داشبورد فاز ۴ */
(() => {
  const state = {
    analysis: null,
    auto: true,
    hotTier: "hot",
    hotView: "table",
    bigView: "table",
    bigWindow: 600,
    bigSide: "all",
    alertSide: "all",
    tabloGrade: "all",
    bigMoves: [],
    tablocastic: [],
    portfolio: [],
    alerts: [],
    thresholds: null,
    marketMap: null,
    fundamentals: [],
    valueStocks: [],
    confluence: null,
    finalAction: "all",
    filterPresets: [],
    filterFields: [],
    savedFilters: [],
    filterRows: [],
    timer: null,
    ws: null,
    wsLogs: [],
    live: null,
    backtest: null,
    options: null,
    notifyCfg: null,
  };

  const TH_META = [
    { key: "entry_score_alert", label: "آستانه هشدار ورود", hint: "پیش‌فرض 65" },
    { key: "entry_score_strong", label: "سیگنال ورود قوی", hint: "پیش‌فرض 80" },
    { key: "exit_score_alert", label: "آستانه هشدار خروج", hint: "پیش‌فرض 60" },
    { key: "volume_spike_ratio", label: "نسبت حجم مشکوک", hint: "مثلاً 2 = دو برابر میانگین" },
    { key: "volume_spike_strong", label: "حجم خیلی مشکوک", hint: "پیش‌فرض 3.5" },
    { key: "buy_power_min", label: "حداقل قدرت خریدار", hint: "پیش‌فرض 1.5" },
    { key: "buy_power_strong", label: "قدرت خریدار قوی", hint: "پیش‌فرض 2.0" },
    { key: "smart_per_capita_min", label: "حداقل سرانه پول هوشمند", hint: "تومان" },
    { key: "hot_money_threshold", label: "آستانه پول داغ", hint: "تومان — پیش‌فرض 200M" },
    { key: "hot_money_plus_min", label: "کف پول داغ پلاس", hint: "تومان — 100M" },
    { key: "hot_money_plus_max", label: "سقف پول داغ پلاس", hint: "تومان — 200M" },
    { key: "near_buy_queue_pct", label: "نزدیکی صف خرید (٪)", hint: "فاصله تا سقف مجاز" },
    { key: "pe_max_attractive", label: "P/E جذاب حداکثر", hint: "پیش‌فرض 12" },
    { key: "pe_max_ok", label: "P/E قابل قبول حداکثر", hint: "پیش‌فرض 18" },
    { key: "big_move_window_sec", label: "پنجره تحرکات (ثانیه)", hint: "600 = ده دقیقه" },
    { key: "big_move_min_score", label: "حداقل امتیاز تحرکات", hint: "پیش‌فرض 25" },
    { key: "poll_seconds", label: "بازه رفرش سرور (ثانیه)", hint: "حداقل حدود 15–30" },
  ];

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  function fmtNum(n, dig = 0) {
    if (n == null || Number.isNaN(+n)) return "—";
    return Number(n).toLocaleString("fa-IR", { maximumFractionDigits: dig });
  }
  function fmtMoney(v) {
    if (v == null || Number.isNaN(+v)) return "—";
    const a = Math.abs(v);
    const sign = v < 0 ? "−" : "";
    if (a >= 1e12) return sign + (a / 1e12).toFixed(2) + "T";
    if (a >= 1e9) return sign + (a / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return sign + (a / 1e6).toFixed(1) + "M";
    if (a >= 1e3) return sign + (a / 1e3).toFixed(1) + "K";
    return sign + String(Math.round(a));
  }
  function pctClass(p) {
    if (p > 0) return "pct-up";
    if (p < 0) return "pct-down";
    return "";
  }
  function scoreClass(score, invert = false) {
    if (invert) {
      if (score >= 75) return "danger";
      if (score >= 60) return "mid";
      return "low";
    }
    if (score >= 80) return "high";
    if (score >= 65) return "mid";
    return "low";
  }
  function tagClass(t) {
    if (!t) return "";
    if (t.includes("حجم")) return "vol";
    if (t.includes("بنیادی") || t.includes("P/E")) return "fund";
    if (t.includes("داغ") || t.includes("خروج") || t.includes("هوشمند")) return "hot";
    return "";
  }
  function gradeClass(g) {
    const x = String(g || "C").toUpperCase();
    if (x.startsWith("A+")) return "ap";
    if (x.startsWith("A")) return "a";
    if (x.startsWith("B")) return "b";
    if (x.startsWith("C")) return "c";
    return "d";
  }
  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
  function reasonsHtml(list) {
    if (!list?.length) return "—";
    return `<ul class="reasons">${list
      .slice(0, 4)
      .map((r) => `<li>${escapeHtml(r)}</li>`)
      .join("")}</ul>`;
  }
  function tagsHtml(tags) {
    if (!tags?.length) return "—";
    return `<div class="tags">${tags
      .map((t) => `<span class="tag ${tagClass(t)}">${escapeHtml(t)}</span>`)
      .join("")}</div>`;
  }
  function addBtn(sym) {
    return `<button class="btn tiny" data-add="${escapeHtml(sym)}" title="افزودن به پورتفو">＋</button>`;
  }
  function openPageBtn(sym) {
    return `<a class="btn tiny" href="/symbol?s=${encodeURIComponent(sym)}" title="صفحه نماد" onclick="event.stopPropagation()">↗</a>`;
  }

  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (res.status === 429) {
      const data = await res.json().catch(()=>({detail:"Rate limit"}));
      showRateLimitToast(data.detail || "درخواست زیاد", data.retry_after);
      throw new Error(data.detail || "429 Rate Limited");
    }
    if (res.status === 401) {
      const data = await res.json().catch(()=>({detail:"Unauthorized"}));
      throw new Error(data.detail || "نیاز به API Key - هدر X-API-Key");
    }
    if (!res.ok) {
      const txt = await res.text();
      // Try to parse JSON error
      try {
        const j = JSON.parse(txt);
        throw new Error(j.detail || j.error || txt);
      } catch {
        throw new Error(txt);
      }
    }
    return res.json();
  }

  async function refresh(force = false) {
    const btn = $("#btnRefresh");
    btn?.classList.add("loading");
    try {
      const q = force ? "true" : "false";
      const sizeBy = $("#mapSize")?.value || "tval";
      const colorBy = $("#mapColor")?.value || "plp";
      const maxPe = Number($("#valMaxPe")?.value || 18);
      const minVal = Number($("#valMinScore")?.value || 55);
      const [data, big, tablo, pf, alerts, th, mmap, funds, valuePack, conf, presets, saved] = await Promise.all([
        api(`/api/analyze?force=${q}`),
        api(`/api/big-moves?window_sec=${state.bigWindow}&limit=100`),
        api(`/api/tablocastic?limit=120`),
        api(`/api/portfolio`),
        api(`/api/alerts?limit=150`),
        state.thresholds ? Promise.resolve(state.thresholds) : api(`/api/config/thresholds`),
        api(`/api/market-map?size_by=${sizeBy}&color_by=${colorBy}`),
        api(`/api/fundamentals?limit=120`),
        api(`/api/fundamentals/value?limit=50&max_pe=${maxPe}&min_score=${minVal}`),
        api(`/api/confluence?limit=80`),
        state.filterPresets.length ? Promise.resolve({ presets: state.filterPresets, fields: state.filterFields }) : api(`/api/filter/presets`),
        api(`/api/filter/saved`),
      ]);
      state.analysis = data;
      state.bigMoves = big;
      state.tablocastic = tablo;
      state.portfolio = pf;
      state.alerts = alerts;
      state.marketMap = mmap;
      state.fundamentals = funds;
      state.valueStocks = valuePack.rows || [];
      state.valueScoring = valuePack.scoring || null;
      state.confluence = conf;
      state.filterPresets = presets.presets || state.filterPresets;
      state.filterFields = presets.fields || state.filterFields;
      state.savedFilters = saved || [];
      if (!state.thresholds) {
        state.thresholds = th;
        renderSettings();
      }
      renderFilterHelpers();
      renderAll();
      updateSource(data.overview?.source, data.data_trust);
      updateTrust(data.data_trust || data.trust_level || data.overview?.source);
      const t = data.overview?.as_of
        ? new Date(data.overview.as_of).toLocaleString("fa-IR")
        : new Date().toLocaleString("fa-IR");
      const snaps = data.store?.snapshots ?? "—";
      const flow = data.flow_meta?.coverage_sec;
      $("#lastUpdate").textContent = `آخرین بروزرسانی: ${t} · اسنپ‌شات: ${snaps} · پوشش جریان: ${flow != null ? Math.round(flow) + "s" : "—"} · v0.6.2`;
      if (!state.notifyCfg) {
        try {
          state.notifyCfg = await api("/api/notify/config");
          fillNotifyForm();
        } catch (_) {}
      }
    } catch (err) {
      console.error(err);
      $("#sourceText").textContent = "خطا در دریافت داده";
    } finally {
      btn?.classList.remove("loading");
    }
  }

  function wsSetStatus(ok, text) {
    const pill = $("#wsPill");
    const el = $("#wsText");
    if (!pill || !el) return;
    pill.classList.remove("live", "mock");
    if (ok) pill.classList.add("live");
    else pill.classList.add("mock");
    el.textContent = text;
  }

  function liveLog(line) {
    state.wsLogs.unshift(`[${new Date().toLocaleTimeString("fa-IR")}] ${line}`);
    state.wsLogs = state.wsLogs.slice(0, 80);
    const pre = $("#liveLog");
    if (pre) pre.textContent = state.wsLogs.join("\n");
  }

  function connectWs() {
    try {
      if (state.ws) {
        try {
          state.ws.close();
        } catch (_) {}
      }
      const proto = location.protocol === "https:" ? "wss" : "ws";
      let wsUrl = `${proto}://${location.host}/ws/live`;
      // در حالت خصوصی، توکن را به WS بده
      try {
        const token = localStorage.getItem("shekar_auth_token");
        if (token) wsUrl += "?token=" + encodeURIComponent(token);
      } catch (e) {}
      const ws = new WebSocket(wsUrl);
      state.ws = ws;
      wsSetStatus(false, "WS در حال اتصال…");
      ws.onopen = () => {
        wsSetStatus(true, "WS متصل");
        liveLog("connected " + wsUrl);
      };
      ws.onclose = () => {
        wsSetStatus(false, "WS قطع");
        liveLog("disconnected");
        if (state.auto) setTimeout(connectWs, 4000);
      };
      ws.onerror = () => {
        wsSetStatus(false, "WS خطا");
        liveLog("error");
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          liveLog("msg " + (msg.type || "?"));
          if (msg.type === "market_update") {
            state.live = msg;
            // soft-update analysis pieces
            if (state.analysis && msg.overview) {
              Object.assign(state.analysis.overview, msg.overview);
              if (msg.entry_signals) state.analysis.entry_signals = msg.entry_signals;
              if (msg.exit_signals) state.analysis.exit_signals = msg.exit_signals;
              renderStats(state.analysis.overview);
              renderEntry();
              renderExit();
            }
            if (msg.confluence) {
              state.confluence = {
                ...(state.confluence || {}),
                summary: msg.confluence.summary,
                buy_alerts: msg.confluence.buy_alerts,
                sell_alerts: msg.confluence.sell_alerts,
                board: [
                  ...(msg.confluence.buy_alerts || []),
                  ...(msg.confluence.sell_alerts || []),
                  ...((state.confluence && state.confluence.board) || []),
                ],
              };
              renderConfluence();
            }
            renderLive();
          } else if (msg.type === "hello") {
            liveLog("hello clients=" + msg.clients);
          }
        } catch (e) {
          liveLog("parse fail");
        }
      };
    } catch (e) {
      wsSetStatus(false, "WS در دسترس نیست");
      liveLog(String(e.message || e));
    }
  }

  function renderLive() {
    const m = state.live;
    const cards = $("#liveCards");
    if (!cards) return;
    if (!m) {
      cards.innerHTML = `<div class="icard"><h4>وضعیت</h4><div class="meta">هنوز پیامی دریافت نشده — اتصال WS را چک کنید.</div></div>`;
      return;
    }
    const ov = m.overview || {};
    cards.innerHTML = [
      ["منبع", m.source || "—"],
      ["نمادها", ov.symbol_count],
      ["ورود", ov.entry_alerts],
      ["خروج", ov.exit_alerts],
      ["حجم مشکوک", ov.volume_spikes],
      ["پول داغ", ov.hot_money_count],
    ]
      .map(
        ([l, v]) =>
          `<div class="icard"><h4>${escapeHtml(l)}</h4><div class="big" style="font-size:1.2rem">${escapeHtml(v)}</div></div>`
      )
      .join("");
    const tb = $("#liveEntryTable tbody");
    const rows = m.entry_signals || [];
    if (tb) {
      tb.innerHTML =
        rows
          .map(
            (r) => `<tr data-symbol="${escapeHtml(r.symbol)}">
          <td><span class="score ${scoreClass(r.entry_score)}">${fmtNum(r.entry_score, 1)}</span></td>
          <td><span class="sym">${escapeHtml(r.symbol)}</span></td>
          <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
          <td>${fmtNum(r.buy_power, 2)}</td>
          <td>${fmtNum(r.volume_ratio, 2)}</td>
          <td>${reasonsHtml(r.reasons)}</td>
        </tr>`
          )
          .join("") || `<tr><td colspan="6" class="empty">—</td></tr>`;
    }
  }

  function renderBacktest() {
    const r = state.backtest;
    const cards = $("#btCards");
    if (!cards) return;
    if (!r) {
      cards.innerHTML = `<div class="icard"><h4>آماده</h4><div class="meta">پارامترها را تنظیم و اجرا کنید.</div></div>`;
      return;
    }
    cards.innerHTML = [
      ["حالت", r.mode],
      ["معاملات", r.trades],
      ["برد٪", r.win_rate],
      ["میانگین بازده", r.avg_return],
      ["میانه", r.median_return],
      ["جمع بازده", r.total_return_sum],
      ["Max DD", r.max_drawdown],
      ["Profit Factor", r.profit_factor],
      ["Sharpe~", r.sharpe_like],
      ["نگهداری میانگین", r.avg_holding_bars],
    ]
      .map(
        ([l, v]) =>
          `<div class="icard"><h4>${l}</h4><div class="big" style="font-size:1.15rem">${typeof v === "number" ? fmtNum(v, 2) : escapeHtml(v)}</div></div>`
      )
      .join("");
    const eq = r.equity_curve || [];
    const maxAbs = Math.max(...eq.map((x) => Math.abs(x.equity)), 0.1);
    $("#btEquity").innerHTML = eq
      .map((p) => {
        const h = Math.max(4, (Math.abs(p.equity) / maxAbs) * 70);
        return `<i class="${p.equity < 0 ? "neg" : ""}" style="height:${h}px" title="${p.equity}"></i>`;
      })
      .join("");
    $("#btTrades tbody").innerHTML =
      (r.trades_sample || [])
        .map(
          (t) => `<tr data-symbol="${escapeHtml(t.symbol)}">
        <td><span class="sym">${escapeHtml(t.symbol)}</span></td>
        <td>${fmtNum(t.entry_price)}</td>
        <td>${fmtNum(t.exit_price)}</td>
        <td class="${pctClass(t.ret_pct)}">${fmtNum(t.ret_pct, 2)}</td>
        <td>${fmtNum(t.holding_bars)}</td>
        <td>${escapeHtml(t.exit_reason)}</td>
        <td>${fmtNum(t.entry_score, 1)}</td>
      </tr>`
        )
        .join("") || `<tr><td colspan="7" class="empty">معامله‌ای نیست</td></tr>`;
    $("#btNotes").textContent = (r.notes || []).join(" · ");
  }

  function renderOptions() {
    const o = state.options;
    if (!o) return;
    $("#optCards").innerHTML = [
      ["نماد", o.symbol],
      ["Spot", o.spot],
      ["Vol", o.vol],
      ["حرکت ضمنی ۳۰روز", o.implied_move_30d],
      ["امتیاز ورود", o.entry_score],
      ["امتیاز خروج", o.exit_score],
    ]
      .map(
        ([l, v]) =>
          `<div class="icard"><h4>${l}</h4><div class="big" style="font-size:1.1rem">${typeof v === "number" ? fmtNum(v, 2) : escapeHtml(v)}</div></div>`
      )
      .join("");
    $("#optStrategies").innerHTML = (o.strategies || [])
      .map(
        (s) => `<div class="icard">
        <h4>${escapeHtml(s.name)} <span class="score ${scoreClass(s.score)}">${fmtNum(s.score, 0)}</span></h4>
        <div class="meta">${escapeHtml(s.summary || "")}<br/>bias: ${escapeHtml(s.bias || "")}
        ${s.max_loss != null ? "<br/>حداکثر زیان: " + fmtNum(s.max_loss, 2) : ""}
        ${s.max_profit != null ? " · حداکثر سود: " + fmtNum(s.max_profit, 2) : ""}
        </div></div>`
      )
      .join("");
    const exp = (o.expiries || [])[0];
    const rows = exp?.strikes || [];
    $("#optChainTable tbody").innerHTML = rows
      .map(
        (r) => `<tr>
        <td><b>${fmtNum(r.strike)}</b></td>
        <td>${fmtNum(r.call?.market ?? r.call?.price, 1)}</td>
        <td>${fmtNum(r.call?.delta, 3)}</td>
        <td>${fmtNum(r.put?.market ?? r.put?.price, 1)}</td>
        <td>${fmtNum(r.put?.delta, 3)}</td>
        <td>${fmtNum(r.moneyness, 3)}</td>
      </tr>`
      )
      .join("");
    if (!$("#opSpot").value) $("#opSpot").value = o.spot;
    if (!$("#opStrike").value) $("#opStrike").value = Math.round(o.spot / 10) * 10;
    if (o.vol) $("#opVol").value = o.vol;
  }

  function fillNotifyForm() {
    const c = state.notifyCfg || {};
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
    if (msg) {
      msg.textContent = `تلگرام: ${c.telegram_configured ? "پیکربندی‌شده" : "خیر"} · بله: ${
        c.bale_configured ? "پیکربندی‌شده" : "خیر"
      } · ترکیبی: ${c.confluence_enabled === false ? "خاموش" : "فعال"} · ارسال‌ها: ${c.sent_count ?? 0}`;
    }
  }

  async function loadNotifyLog() {
    try {
      const rows = await api("/api/notify/log?limit=40");
      const tb = $("#notifyLogTable tbody");
      if (!tb) return;
      tb.innerHTML =
        rows
          .map((r) => {
            const t = r.ts_iso ? new Date(r.ts_iso).toLocaleString("fa-IR") : "—";
            const text = r.payload?.text || "";
            return `<tr>
            <td>${escapeHtml(t)}</td>
            <td>${escapeHtml(r.channel || "")}</td>
            <td>${r.ok ? "✓" : "✗"}</td>
            <td class="reasons">${escapeHtml(String(text).slice(0, 160))}</td>
          </tr>`;
          })
          .join("") || `<tr><td colspan="4" class="empty">لاگی نیست</td></tr>`;
    } catch (_) {}
  }

  function isVerifiedLive(dt) {
    return !!(dt && typeof dt === "object"
      && String(dt.state || "").toLowerCase() === "live"
      && dt.is_live === true
      && dt.live_verified === true);
  }

  function updateSource(source, dataTrust) {
    const pill = $("#sourcePill");
    const text = $("#sourceText");
    pill.classList.remove("live", "mock");
    const s = source || "—";
    if (isVerifiedLive(dataTrust)) {
      pill.classList.add("live");
      text.textContent = "منبع تأییدشده · " + s;
    } else if (String(s).includes("mock")) {
      pill.classList.add("mock");
      text.textContent = "داده دمو (TSETMC در دسترس نیست)";
    } else {
      pill.classList.add("mock");
      text.textContent = "منبع تأییدنشده · " + s;
    }
  }

  function updateTrust(levelOrTrust) {
    const pill = $("#trustPill");
    const text = $("#trustText");
    const banner = $("#trustBanner");
    const bannerIcon = $("#trustBannerIcon");
    const bannerText = $("#trustBannerText");
    if (pill && text) {
      pill.classList.remove("live", "mock");
      const obj = typeof levelOrTrust === "object" && levelOrTrust ? levelOrTrust : {};
      const lv = obj.state
        ? String(obj.state || obj.trust_level || "mixed").toLowerCase()
        : String(levelOrTrust || "mixed").toLowerCase();
      if (isVerifiedLive(obj)) {
        pill.classList.add("live");
        text.textContent = "اعتماد: LIVE - داده زنده";
        if(banner){ banner.className = "trust-banner live"; banner.classList.add("hidden"); }
      } else if (lv === "synthetic" || lv === "mock") {
        pill.classList.add("mock");
        text.textContent = "اعتماد: DEMO/SYNTHETIC";
        if(banner){
          banner.className = "trust-banner demo";
          banner.classList.remove("hidden");
          if(bannerText) bannerText.textContent = "⚠️ هشدار: داده DEMO/SYNTHETIC است - تمام اعداد بنیادی و ریزمعامله ساختگی هستند - مبنای خرید/فروش قرار ندهید - فقط برای تست UI";
          if(bannerIcon) bannerIcon.textContent = "🚨";
        }
      } else {
        pill.classList.add("mock");
        const labels = {
          live: "UNVERIFIED LIVE-CLASS",
          stale: "STALE / قدیمی",
          unavailable: "UNAVAILABLE / ناموجود",
          mixed: "MIXED - بخشی از داده آزمایشی",
        };
        text.textContent = "اعتماد: " + (labels[lv] || "NOT LIVE");
        if(banner){
          banner.className = "trust-banner mixed";
          banner.classList.remove("hidden");
          if(bannerText) bannerText.textContent = "⚠️ توجه: داده تأییدشده زنده نیست - مبنای خرید/فروش قرار ندهید";
          if(bannerIcon) bannerIcon.textContent = "⚠️";
        }
      }
    }
  }

  function showRateLimitToast(msg, retryAfter){
    let existing = document.querySelector(".rate-limit-toast");
    if(existing) existing.remove();
    const toast = document.createElement("div");
    toast.className = "rate-limit-toast";
    toast.textContent = (msg || "درخواست زیاد") + (retryAfter ? ` - ${retryAfter}s صبر کنید` : "");
    document.body.appendChild(toast);
    setTimeout(()=> toast.remove(), 4000);
  }


  function renderThermo(t) {
    const stat = $("#thermoStat");
    if (!stat || !t || typeof t.score !== "number") return;
    const score = t.score;
    const st = t.state || "neutral";
    stat.classList.remove("bull", "bear", "neutral");
    stat.classList.add(st);
    const scoreEl = $("#thermoScore");
    if (scoreEl) scoreEl.textContent = `${t.label || "—"} ${fmtNum(Math.abs(score), 1)}`;
    const fill = $("#thermoFill");
    if (fill) {
      const pct = Math.min(100, Math.abs(score));
      fill.style.width = pct + "%";
      fill.style.background =
        st === "bull"
          ? "linear-gradient(90deg,#34d399,#22c55e)"
          : st === "bear"
            ? "linear-gradient(90deg,#fb7185,#ef4444)"
            : "linear-gradient(90deg,#fbbf24,#f59e0b)";
      fill.style.marginLeft = st === "bull" ? "auto" : "0";
    }
  }

  function renderStats(ov) {
    if (!ov) return;
    renderThermo(ov.thermometer);
    $("#stSymbols").textContent = fmtNum(ov.symbol_count);
    $("#stPos").textContent = fmtNum(ov.positive_count);
    $("#stNeg").textContent = fmtNum(ov.negative_count);
    $("#stEntry").textContent = fmtNum(ov.entry_alerts);
    $("#stExit").textContent = fmtNum(ov.exit_alerts);
    $("#stBig").textContent = fmtNum(state.bigMoves?.length || ov.big_moves || 0);
    $("#stHot").textContent = fmtNum(ov.hot_money_count);
    const pf = state.portfolio?.length || 0;
    const snaps = state.analysis?.store?.snapshots ?? 0;
    $("#stPort").textContent = `${fmtNum(pf)} / ${fmtNum(snaps)}`;
  }

  function filteredEntry() {
    const rows = state.analysis?.entry_signals || [];
    const minScore = Number($("#fMinScore").value || 0);
    const onlyNeg = $("#fNegOnly").checked;
    const onlyFund = $("#fFundOnly").checked;
    return rows.filter((r) => {
      if (r.entry_score < minScore) return false;
      if (onlyNeg && !(r.plp <= 0)) return false;
      if (onlyFund && !(r.tags || []).includes("بنیادی‌خوب")) return false;
      return true;
    });
  }

  function renderEntry() {
    const tb = $("#entryTable tbody");
    const rows = filteredEntry();
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="13" class="empty">سیگنالی با این فیلترها نیست.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td class="pf-actions">${addBtn(r.symbol)} ${openPageBtn(r.symbol)}</td>
        <td><span class="score ${scoreClass(r.entry_score)}">${fmtNum(r.entry_score, 1)}</span></td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name)}</span></td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td>${fmtNum(r.pl)}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${fmtNum(r.buy_power, 2)}</td>
        <td>${fmtNum(r.volume_ratio, 2)}</td>
        <td>${r.pe != null ? fmtNum(r.pe, 1) : "—"}</td>
        <td class="${r.individual_net_value >= 0 ? "pct-up" : "pct-down"}">${fmtMoney(r.individual_net_value)}</td>
        <td class="${r.hot_net >= 0 ? "pct-up" : "pct-down"}">${fmtNum(r.hot_net, 1)}</td>
        <td>${tagsHtml(r.tags)}</td>
        <td>${reasonsHtml(r.reasons)}</td>
      </tr>`
      )
      .join("");
  }

  function renderExit() {
    const tb = $("#exitTable tbody");
    const rows = state.analysis?.exit_signals || [];
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="11" class="empty">هشدار خروجی نیست.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td>${addBtn(r.symbol)}</td>
        <td><span class="score ${scoreClass(r.exit_score, true)}">${fmtNum(r.exit_score, 1)}</span></td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name)}</span></td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td>${fmtNum(r.pl)}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${fmtNum(r.buy_power, 2)}</td>
        <td>${fmtNum(r.volume_ratio, 2)}</td>
        <td class="${r.individual_net_value >= 0 ? "pct-up" : "pct-down"}">${fmtMoney(r.individual_net_value)}</td>
        <td class="${r.hot_net >= 0 ? "pct-up" : "pct-down"}">${fmtNum(r.hot_net, 1)}</td>
        <td>${reasonsHtml(r.reasons)}</td>
      </tr>`
      )
      .join("");
  }

  function renderBig() {
    const tb = $("#bigTable tbody");
    const mx = $("#bigMatrix");
    const wrap = $("#bigTableWrap");
    let rows = state.bigMoves || [];
    if (state.bigSide !== "all") rows = rows.filter((r) => r.side === state.bigSide);
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="10" class="empty">تحرکی در این پنجره ثبت نشده — چند رفرش صبر کنید یا تاریخچه در حال ساخت است.</td></tr>`;
      if (mx) mx.innerHTML = "";
      return;
    }
    // نمای ماتریس گرمایی (ایده ۳.۱)
    const showMatrix = state.bigView === "matrix";
    if (wrap) wrap.style.display = showMatrix ? "none" : "";
    if (mx) {
      mx.style.display = showMatrix ? "grid" : "none";
      if (showMatrix) {
        const maxAbs = Math.max(...rows.map((r) => Math.abs(r.delta_net_value || 0)), 1);
        mx.innerHTML = rows
          .slice(0, 48)
          .map((r) => {
            const heat = Math.abs(r.delta_net_value || 0) / maxAbs;
            const bg =
              r.side === "inflow"
                ? `rgba(52,211,153,${(0.2 + heat * 0.75).toFixed(3)})`
                : `rgba(251,113,133,${(0.2 + heat * 0.75).toFixed(3)})`;
            return `<div class="heat-tile" data-symbol="${escapeHtml(r.symbol)}" title="${escapeHtml(r.symbol)} — ${r.side === "inflow" ? "ورود" : "خروج"} ${fmtMoney(r.delta_net_value)} · ${escapeHtml(r.note || "")}" style="background:${bg}">
              <b>${escapeHtml(r.symbol)}</b>
              <span>${r.side === "inflow" ? "⬆" : "⬇"} ${fmtMoney(r.delta_net_value)}</span>
            </div>`;
          })
          .join("");
      }
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td><span class="score ${scoreClass(r.score)}">${fmtNum(r.score, 1)}</span></td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name || "")}</span></td>
        <td class="${r.side === "inflow" ? "side-in" : "side-out"}">${r.side === "inflow" ? "ورود" : "خروج"}</td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td class="${r.delta_net_value >= 0 ? "pct-up" : "pct-down"}">${fmtMoney(r.delta_net_value)}</td>
        <td class="${pctClass(r.delta_plp)}">${fmtNum(r.delta_plp, 2)}</td>
        <td class="${pctClass(r.delta_buy_power)}">${fmtNum(r.delta_buy_power, 2)}</td>
        <td class="${pctClass(r.delta_hot_net)}">${fmtNum(r.delta_hot_net, 1)}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.pl)} (${fmtNum(r.plp, 2)}٪)</td>
        <td class="reasons">${escapeHtml(r.note || "")}</td>
      </tr>`
      )
      .join("");
  }

  function renderTablo() {
    const tb = $("#tabloTable tbody");
    const minQ = Number($("#fTabloQ")?.value || 0);
    let rows = (state.tablocastic || []).filter((r) => (r.quality_score || 0) >= minQ);
    if (state.tabloGrade !== "all") {
      const g = state.tabloGrade.toUpperCase();
      rows = rows.filter((r) => String(r.grade || "").toUpperCase().startsWith(g));
    }
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="12" class="empty">موردی نیست.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td><span class="grade ${gradeClass(r.grade)}">${escapeHtml(r.grade)}</span></td>
        <td><span class="score ${scoreClass(r.quality_score)}">${fmtNum(r.quality_score, 1)}</span></td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name || "")}</span></td>
        <td><b>${fmtNum(r.golden_number, 1)}</b></td>
        <td>${fmtNum(r.d_plus, 1)}</td>
        <td class="${pctClass(r.m_plus)}">${fmtNum(r.m_plus, 1)}</td>
        <td>${fmtNum(r.m_over_d, 2)}</td>
        <td class="${pctClass(r.queue_power)}">${fmtNum(r.queue_power, 1)}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${r.hour_pattern ? "بله" : "—"}</td>
        <td>${r.cross_minutes != null ? fmtNum(r.cross_minutes, 0) + "′ " + (r.cross_direction === "up" ? "↑" : r.cross_direction === "down" ? "↓" : "") : "—"}</td>
        <td class="reasons">${escapeHtml((r.notes || []).slice(0, 3).join(" · "))}</td>
      </tr>`
      )
      .join("");
  }

  function flowBar(score) {
    const v = Math.max(0, Math.min(100, score || 0));
    const cls = v >= 70 ? "high" : v >= 45 ? "mid" : "low";
    return `<div class="flow-cell ${cls}"><i style="width:${v}%"></i><span>${fmtNum(score, 0)}</span></div>`;
  }

  function renderHot() {
    const tb = $("#hotTable tbody");
    const hm = $("#hotHeatmap");
    const wrap = $("#hotTableWrap");
    let rows = [];
    const a = state.analysis;
    if (!a) return;
    if (state.hotTier === "hot") rows = a.hot_money || [];
    else if (state.hotTier === "plus") rows = a.hot_money_plus || [];
    else rows = [...(a.hot_money || []), ...(a.hot_money_plus || [])].sort((x, y) => y.score - x.score);
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="11" class="empty">موردی نیست.</td></tr>`;
      if (hm) hm.innerHTML = "";
      return;
    }
    // نمای هیتمپ (ایده ۱.۱)
    const showHeat = state.hotView === "heat";
    if (wrap) wrap.style.display = showHeat ? "none" : "";
    if (hm) {
      hm.style.display = showHeat ? "flex" : "none";
      if (showHeat) {
        const maxFlow = Math.max(...rows.map((r) => r.flow_score || 0), 1);
        hm.innerHTML = rows
          .slice(0, 36)
          .map((r) => {
            const heat = (r.flow_score || 0) / maxFlow;
            const bg =
              r.side === "buy"
                ? `rgba(52,211,153,${(0.25 + heat * 0.7).toFixed(3)})`
                : `rgba(251,113,133,${(0.25 + heat * 0.7).toFixed(3)})`;
            return `<div class="heat-tile" data-symbol="${escapeHtml(r.symbol)}" title="${escapeHtml(r.symbol)} — ${r.side === "buy" ? "خرید" : "فروش"} · جریان ${fmtNum(r.flow_score, 0)}" style="background:${bg}">
              <b>${escapeHtml(r.symbol)}</b>
              <span>${r.side === "buy" ? "⬆ خرید" : "⬇ فروش"} · ${fmtNum(r.flow_score, 0)}</span>
            </div>`;
          })
          .join("");
      }
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td>${r.tier === "hot" ? "🔥 داغ" : "✨ پلاس"}</td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name)}</span></td>
        <td class="${r.side === "buy" ? "side-buy" : "side-sell"}">${r.side === "buy" ? "خرید" : "فروش"}</td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td>${fmtMoney(r.per_capita)}</td>
        <td>${fmtNum(r.buy_power, 2)}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${fmtNum(r.volume_ratio, 2)}</td>
        <td class="${r.hot_net >= 0 ? "pct-up" : "pct-down"}">${fmtNum(r.hot_net, 1)}</td>
        <td>${flowBar(r.flow_score)}</td>
        <td><span class="score ${scoreClass(r.score)}">${fmtNum(r.score, 1)}</span></td>
      </tr>`
      )
      .join("");
  }

  function biasBar(v) {
    const pct = Math.min(100, Math.abs(v) * 100);
    const cls = v < 0 ? "neg" : "";
    return `<div class="bias ${cls}" title="${v}"><i style="width:${pct}%"></i></div>`;
  }

  function renderGame() {
    const tb = $("#gameTable tbody");
    const rows = state.analysis?.market_game || [];
    // قهرمانان شکار (ایده ۲.۱): ورود پول هوشمند در قیمت منفی
    const champions = (rows || []).filter((r) => r.hunt_champion);
    const chEl = $("#huntChampions");
    if (chEl) {
      chEl.innerHTML = champions.length
        ? champions
            .slice(0, 8)
            .map(
              (r) => `
            <div class="icard hunt-card" data-symbol="${escapeHtml(r.symbol)}">
              <h4>🎯 ${escapeHtml(r.symbol)}</h4>
              <div class="big pct-down">${fmtNum(r.plp, 2)}٪</div>
              <div class="meta">${escapeHtml(r.industry || "—")}<br/>
                غالب: <b>${escapeHtml(r.dominant)}</b> · حجم×${fmtNum(r.volume_ratio, 2)}<br/>
                قدرت: ${fmtNum(r.buy_power, 2)}<br/>
                <span class="tag vol">ورود پول در قیمت منفی → کاندید صف خرید</span>
              </div>
            </div>`
            )
            .join("")
        : `<div class="icard"><h4>🎯 قهرمان شکار</h4><div class="meta">فعلاً نمادی با «ورود پول هوشمند در قیمت منفی» نیست — بازار را رصد کنید.</div></div>`;
    }
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="10" class="empty">موردی نیست.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}" class="${r.hunt_champion ? "hunt-row" : ""}">
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name)}</span>${r.hunt_champion ? ' <span class="tag vol">🎯</span>' : ""}</td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td>${biasBar(r.big_bias)}</td>
        <td>${biasBar(r.mid_bias)}</td>
        <td>${biasBar(r.retail_bias)}</td>
        <td>${escapeHtml(r.dominant)}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${fmtNum(r.volume_ratio, 2)}</td>
        <td>${fmtNum(r.buy_power, 2)}</td>
        <td class="reasons">${escapeHtml(r.note)}</td>
      </tr>`
      )
      .join("");
  }

  function renderIndustry() {
    const rows = state.analysis?.industries || [];
    $("#industryCards").innerHTML = rows
      .slice(0, 6)
      .map(
        (r) => `
      <div class="icard">
        <h4>${escapeHtml(r.industry)}</h4>
        <div class="big">${fmtNum(r.score, 1)}</div>
        <div class="meta">
          میانگین ٪: <b class="${pctClass(r.avg_plp)}">${fmtNum(r.avg_plp, 2)}</b><br/>
          کاندید ورود: <b>${fmtNum(r.entry_candidates)}</b> از ${fmtNum(r.symbol_count)}<br/>
          خالص حقیقی: <b class="${r.net_individual_value >= 0 ? "pct-up" : "pct-down"}">${fmtMoney(r.net_individual_value)}</b>
        </div>
      </div>`
      )
      .join("");
    $("#industryTable tbody").innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td><span class="score ${scoreClass(Math.min(100, r.score + 40))}">${fmtNum(r.score, 1)}</span></td>
        <td><b>${escapeHtml(r.industry)}</b></td>
        <td>${fmtNum(r.symbol_count)}</td>
        <td class="${pctClass(r.avg_plp)}">${fmtNum(r.avg_plp, 2)}٪</td>
        <td>${fmtMoney(r.total_value)}</td>
        <td class="${r.net_individual_value >= 0 ? "pct-up" : "pct-down"}">${fmtMoney(r.net_individual_value)}</td>
        <td>${fmtNum(r.avg_buy_power, 2)}</td>
        <td>${fmtNum(r.avg_volume_ratio, 2)}</td>
        <td>${fmtNum(r.entry_candidates)}</td>
      </tr>`
      )
      .join("");
  }

  function renderPortfolio() {
    const tb = $("#pfTable tbody");
    const rows = state.portfolio || [];
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="12" class="empty">پورتفو خالی است — از جدول‌ها ＋ بزنید یا نماد وارد کنید.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name || "")}</span></td>
        <td class="${pctClass(r.plp)}">${r.plp != null ? fmtNum(r.plp, 2) + "٪" : "—"}</td>
        <td><span class="score ${scoreClass(r.entry_score || 0)}">${fmtNum(r.entry_score, 1)}</span></td>
        <td><span class="score ${scoreClass(r.exit_score || 0, true)}">${fmtNum(r.exit_score, 1)}</span></td>
        <td>${fmtNum(r.buy_power, 2)}</td>
        <td>${fmtNum(r.golden_number, 1)}</td>
        <td>${fmtNum(r.d_plus, 1)}</td>
        <td class="${pctClass(r.m_plus)}">${fmtNum(r.m_plus, 1)}</td>
        <td><span class="grade ${gradeClass(r.grade)}">${escapeHtml(r.grade || "—")}</span></td>
        <td>${escapeHtml(r.side || "—")}</td>
        <td class="reasons">${escapeHtml(r.note || "")}</td>
        <td><button class="btn tiny danger-outline" data-del="${escapeHtml(r.symbol)}">حذف</button></td>
      </tr>`
      )
      .join("");
  }

  function renderAlerts() {
    const tb = $("#alertTable tbody");
    let rows = state.alerts || [];
    if (state.alertSide !== "all") rows = rows.filter((r) => r.side === state.alertSide);
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="7" class="empty">هنوز هشداری ثبت نشده.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map((r) => {
        const t = r.ts_iso ? new Date(r.ts_iso).toLocaleString("fa-IR") : "—";
        return `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td>${escapeHtml(t)}</td>
        <td class="${r.side === "entry" ? "side-in" : "side-out"}">${r.side === "entry" ? "ورود" : "خروج"}</td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span></td>
        <td><span class="score ${scoreClass(r.score || 0, r.side === "exit")}">${fmtNum(r.score, 1)}</span></td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${tagsHtml(r.tags)}</td>
        <td>${reasonsHtml(r.reasons)}</td>
      </tr>`;
      })
      .join("");
  }


  function renderWatch() {
    // v1.0 Better than tablokhani.com/stock-watchlist - try excellent version first
    if (window.renderWatchlistExcellent && state.analysis) {
      try {
        window.renderWatchlistExcellent(state.analysis);
        return;
      } catch(e) { console.warn("Excellent watchlist failed, fallback", e); }
    }

    const tb = $("#watchTable tbody");
    const rows = state.analysis?.watchlist || [];
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="9" class="empty">دیده‌بان خالی است.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td>${addBtn(r.symbol)}</td>
        <td><span class="score ${scoreClass(r.entry_score)}">${fmtNum(r.entry_score, 1)}</span></td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name)}</span></td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${fmtNum(r.buy_power, 2)}</td>
        <td>${fmtNum(r.volume_ratio, 2)}</td>
        <td>${tagsHtml(r.tags)}</td>
        <td>${reasonsHtml(r.reasons)}</td>
      </tr>`
      )
      .join("");
  }

  function renderSettings() {
    const grid = $("#settingsGrid");
    if (!grid || !state.thresholds) return;
    grid.innerHTML = TH_META.map((m) => {
      const val = state.thresholds[m.key] ?? "";
      return `
        <div class="setting-card">
          <label for="th_${m.key}">${escapeHtml(m.label)}</label>
          <input id="th_${m.key}" data-th="${m.key}" type="number" step="any" value="${escapeHtml(val)}" />
          <div class="hint">${escapeHtml(m.hint)}</div>
        </div>`;
    }).join("");
  }

  function colorForMap(val, mode) {
    // return css color
    if (mode === "plp" || mode === "hot_net" || mode === "individual_net") {
      const t = Math.max(-5, Math.min(5, +val || 0));
      if (t >= 0) {
        const a = 0.25 + (t / 5) * 0.7;
        return `rgba(52,211,153,${a})`;
      }
      const a = 0.25 + (Math.abs(t) / 5) * 0.7;
      return `rgba(251,113,133,${a})`;
    }
    if (mode === "exit_score") {
      const t = Math.max(0, Math.min(100, +val || 0)) / 100;
      return `rgba(251,113,133,${0.2 + t * 0.75})`;
    }
    if (mode === "buy_power") {
      const t = Math.max(0, Math.min(3, +val || 0)) / 3;
      return `rgba(34,211,238,${0.2 + t * 0.75})`;
    }
    // entry_score default
    const t = Math.max(0, Math.min(100, +val || 0)) / 100;
    return `rgba(52,211,153,${0.2 + t * 0.75})`;
  }

  function renderMarketMap() {
    const box = $("#marketMap");
    if (!box || !state.marketMap) return;
    const groups = state.marketMap.groups || [];
    const total = groups.reduce((a, g) => a + (g.size || 0), 0) || 1;
    const colorBy = state.marketMap.color_by || "plp";
    box.innerHTML = groups
      .slice(0, 18)
      .map((g) => {
        const pct = Math.max(8, Math.min(48, (g.size / total) * 100));
        const kids = g.children || [];
        const ksum = kids.reduce((a, k) => a + (k.size || 0), 0) || 1;
        return `<div class="tm-ind" style="flex: ${pct} 1 ${pct * 4}px; min-height:${Math.max(90, pct * 3)}px">
          <label>${escapeHtml(g.name)} (${fmtNum(g.count)})</label>
          ${kids
            .slice(0, 24)
            .map((c) => {
              const w = Math.max(12, (c.size / ksum) * 100);
              const bg = colorForMap(c.color, colorBy);
              return `<div class="tm-cell" data-symbol="${escapeHtml(c.symbol)}" title="${escapeHtml(c.symbol)} ${fmtNum(c.plp, 2)}%"
                style="flex: ${w} 1 ${Math.max(52, w)}px; background:${bg}; color:#e8fff6">
                <span class="s">${escapeHtml(c.symbol)}</span>
                <span class="p">${fmtNum(c.plp, 1)}٪</span>
              </div>`;
            })
            .join("")}
        </div>`;
      })
      .join("");
    if ($("#mapMeta")) {
      $("#mapMeta").textContent = `${fmtNum(state.marketMap.symbol_count)} نماد · ${fmtNum(state.marketMap.industry_count)} صنعت · اندازه: ${state.marketMap.size_by} · رنگ: ${state.marketMap.color_by}`;
    }
  }

  function renderFundamentals() {
    const tb = $("#fundTable tbody");
    if (!tb) return;
    const minS = Number($("#fFundMin")?.value || 0);
    const rows = (state.fundamentals || []).filter((r) => (r.value_score || r.fund_score || 0) >= minS);
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="11" class="empty">موردی نیست</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}" data-deep="1">
        <td><span class="score ${scoreClass(r.value_score || r.fund_score)}">${fmtNum(r.value_score || r.fund_score, 1)}</span></td>
        <td><span class="grade ${gradeClass(r.value_grade || r.grade)}">${escapeHtml(r.value_grade || r.grade)}</span></td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name || "")}</span>
          <button class="btn tiny" data-deep-sym="${escapeHtml(r.symbol)}">گزارش</button>
        </td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td>${r.pe != null ? fmtNum(r.pe, 1) : "—"}</td>
        <td>${fmtNum(r.roe, 1)}</td>
        <td class="${pctClass(r.profit_growth)}">${fmtNum(r.profit_growth, 1)}٪</td>
        <td class="${pctClass(r.revenue_growth)}">${fmtNum(r.revenue_growth, 1)}٪</td>
        <td>${fmtNum(r.debt_ratio, 2)}</td>
        <td>${fmtNum(r.current_ratio, 2)}</td>
        <td class="reasons">${escapeHtml((r.notes || []).slice(0, 3).join(" · "))}</td>
      </tr>`
      )
      .join("");
  }

  function actionLabel(a) {
    return (
      {
        buy: "🟢 خرید",
        sell: "🔴 فروش",
        watch_buy: "👁 رصد خرید",
        watch_sell: "👁 رصد فروش",
        watch: "—",
      }[a] || a
    );
  }
  function actionClass(a) {
    if (a === "buy") return "side-in";
    if (a === "sell") return "side-out";
    return "";
  }

  function renderConfluence() {
    const conf = state.confluence;
    const sumEl = $("#finalSummary");
    const tb = $("#finalTable tbody");
    if (!sumEl || !tb) return;
    if (!conf) {
      sumEl.innerHTML = `<div class="icard"><h4>جمع‌بندی</h4><div class="meta">در حال بارگذاری…</div></div>`;
      return;
    }
    const s = conf.summary || {};
    const fm = conf.flow_meta || {};
    const trustObj = conf.data_trust || {};
    const live = trustObj.state === "live" && trustObj.is_live === true && trustObj.live_verified === true;
    const trust = live ? "LIVE" : (conf.trust_level && conf.trust_level !== "live" ? conf.trust_level : "NOT LIVE");
    sumEl.innerHTML = [
      ["هشدار خرید", s.buy_alerts, "pct-up"],
      ["هشدار فروش", s.sell_alerts, "pct-down"],
      ["رصد", s.watch, ""],
      ["کل ردیف‌ها", s.total, ""],
      ["پنجره جریان", (conf.window_sec || 600) / 60 + " دقیقه", ""],
      ["پوشش جریان", fm.coverage_sec != null ? Math.round(fm.coverage_sec) + "s" : "—", fm.sufficient ? "pct-up" : "pct-down"],
      ["سطح اعتماد", trust, live ? "pct-up" : ""],
    ]
      .map(
        ([l, v, c]) =>
          `<div class="icard"><h4>${l}</h4><div class="big ${c || ""}" style="font-size:1.15rem">${escapeHtml(v)}</div></div>`
      )
      .join("");
    if (s.flow_insufficient || (fm.coverage_sec != null && fm.sufficient === false)) {
      sumEl.innerHTML += `<div class="icard warn-box"><h4>⚠ پوشش جریان</h4><div class="meta">تاریخچه ۱۰دقیقه‌ای هنوز کافی نیست — هشدار خرید ترکیبی تا تکمیل پوشش غیرفعال/احتیاطی است.</div></div>`;
    }
    if (String(trust).includes("synthetic")) {
      sumEl.innerHTML += `<div class="icard warn-box"><h4>⚠ DEMO</h4><div class="meta">بخشی از داده synthetic است. برای سیگنال واقعی به منبع live و NOTIFY_ALLOW_SYNTHETIC=0 نیاز است.</div></div>`;
    }

    let rows = conf.board || [];
    const act = state.finalAction || "all";
    if (act === "buy") rows = conf.buy_alerts || rows.filter((r) => r.action === "buy");
    else if (act === "sell") rows = conf.sell_alerts || rows.filter((r) => r.action === "sell");
    else if (act === "watch")
      rows = conf.watchlist || rows.filter((r) => String(r.action || "").startsWith("watch"));

    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="13" class="empty">موردی با این فیلتر نیست — بازار را رصد کنید یا آستانه را در اعلان‌ها کم کنید.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map((r) => {
        const flowTxt =
          r.flow_side === "inflow"
            ? `ورود ${fmtNum(r.flow_score, 0)}`
            : r.flow_side === "outflow"
              ? `خروج ${fmtNum(r.flow_score, 0)}`
              : fmtNum(r.flow_score, 0);
        return `<tr data-symbol="${escapeHtml(r.symbol)}">
          <td class="${actionClass(r.action)}"><b>${actionLabel(r.action)}</b>${r.alert ? " ⚡" : ""}</td>
          <td><span class="score ${scoreClass(r.combo_score)}">${fmtNum(r.combo_score, 1)}</span></td>
          <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name || "")}</span>
            <button class="btn tiny" data-deep-sym="${escapeHtml(r.symbol)}">بنیادی</button>
          </td>
          <td>${escapeHtml(r.industry || "—")}</td>
          <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
          <td>${r.pe != null ? fmtNum(r.pe, 1) : "—"}</td>
          <td>${fmtNum(r.entry_score, 1)}</td>
          <td>${fmtNum(r.exit_score, 1)}</td>
          <td><span class="score ${scoreClass(r.value_score)}">${fmtNum(r.value_score, 1)}</span>
            <span class="grade ${gradeClass(r.value_grade)}">${escapeHtml(r.value_grade || "")}</span></td>
          <td class="${r.flow_side === "inflow" ? "pct-up" : r.flow_side === "outflow" ? "pct-down" : ""}">${flowTxt}</td>
          <td>${fmtNum(r.buy_power, 2)}</td>
          <td>${fmtNum(r.volume_ratio, 2)}</td>
          <td>${reasonsHtml(r.reasons)}</td>
        </tr>`;
      })
      .join("");
  }

  function renderValueStocks() {
    const tb = $("#valueTable tbody");
    if (!tb) return;
    const legend = $("#valueScoreLegend");
    if (legend) {
      const sc = state.valueScoring || {
        pe: "۰–۳۰",
        trend: "۰–۱۵",
        profitability: "۰–۲۰",
        liquidity_debt: "۰–۱۵",
        cash_quality: "۰–۱۵",
        audit: "۰–۵",
      };
      legend.innerHTML = Object.entries(sc)
        .map(
          ([k, v]) =>
            `<div class="icard"><h4>${escapeHtml(k)}</h4><div class="meta">${escapeHtml(String(v))}</div></div>`
        )
        .join("");
    }
    const rows = state.valueStocks || [];
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="14" class="empty">با این فیلتر P/E و امتیاز، سهم ارزنده‌ای نیست.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map((r) => {
        const parts = r.score_parts || {};
        const partsTxt = Object.entries(parts)
          .map(([k, v]) => `${k}:${v}`)
          .join(" · ");
        return `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td><b>${fmtNum(r.rank)}</b></td>
        <td><span class="score ${scoreClass(r.value_score)}">${fmtNum(r.value_score, 1)}</span></td>
        <td><span class="grade ${gradeClass(r.value_grade)}">${escapeHtml(r.value_grade)}</span></td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name || "")}</span>
          <button class="btn tiny" data-deep-sym="${escapeHtml(r.symbol)}">گزارش</button>
        </td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td>${r.pe != null ? fmtNum(r.pe, 1) : "—"}</td>
        <td>${r.peg != null ? fmtNum(r.peg, 2) : "—"}</td>
        <td>${fmtNum(r.roe, 1)}</td>
        <td>${r.gross_margin != null ? fmtNum(r.gross_margin, 1) : "—"}</td>
        <td>${r.cfo_to_net != null ? fmtNum(r.cfo_to_net, 2) : "—"}</td>
        <td>${fmtNum(r.debt_ratio, 2)}</td>
        <td class="${pctClass(r.profit_growth)}">${fmtNum(r.profit_growth, 1)}٪</td>
        <td class="${pctClass(r.revenue_growth)}">${fmtNum(r.revenue_growth, 1)}٪</td>
        <td class="reasons">${escapeHtml(partsTxt)}</td>
      </tr>`;
      })
      .join("");
  }

  function evBadge(kind) {
    const k = kind || "analytical";
    const map = {
      definite: ["قطعی", "fund"],
      analytical: ["تحلیلی", "vol"],
      insufficient: ["ناکافی", "hot"],
    };
    const [label, cls] = map[k] || map.analytical;
    return `<span class="tag ${cls}">${label}</span>`;
  }

  function fmtMoneyFa(v) {
    if (v == null || Number.isNaN(+v)) return "—";
    return fmtMoney(v);
  }

  async function openDeepFundamental(sym) {
    const modal = $("#deepFundModal");
    const body = $("#deepFundBody");
    if (!modal || !body) return;
    body.innerHTML = `<p class="muted">در حال تهیه گزارش ۵محوره برای ${escapeHtml(sym)}…</p>`;
    modal.classList.remove("hidden");
    try {
      const d = await api("/api/fundamental/" + encodeURIComponent(sym) + "/deep");
      const deep = d.deep || {};
      const s1 = deep.section_trend || {};
      const s2 = deep.section_profitability || {};
      const s3 = deep.section_liquidity || {};
      const s4 = deep.section_cash_quality || {};
      const s5 = deep.section_swot || {};

      const trendTable = (s1.table || [])
        .map(
          (r) => `<tr>
          <td>${escapeHtml(r.item)}</td>
          <td>${fmtMoneyFa(r.p0)}</td>
          <td>${fmtMoneyFa(r.p1)}</td>
          <td>${fmtMoneyFa(r.p2)}</td>
          <td class="${pctClass(r.chg_p2_p0)}">${r.chg_p2_p0 != null ? fmtNum(r.chg_p2_p0, 1) + "٪" : "—"}</td>
          <td class="reasons">${escapeHtml(r.ref || "")}</td>
        </tr>`
        )
        .join("");

      const profTable = (s2.table || [])
        .map(
          (r) => `<tr>
          <td>${escapeHtml(r.period)}</td>
          <td>${fmtNum(r.gross_margin, 1)}</td>
          <td>${fmtNum(r.operating_margin, 1)}</td>
          <td>${fmtNum(r.net_margin, 1)}</td>
          <td>${fmtNum(r.roa, 1)}</td>
          <td>${fmtNum(r.roe, 1)}</td>
          <td>${fmtNum(r.non_op_to_net_abs, 1)}</td>
        </tr>`
        )
        .join("");

      const liqTable = (s3.table || [])
        .map(
          (r) => `<tr>
          <td>${escapeHtml(r.period)}</td>
          <td>${fmtNum(r.current_ratio, 2)}</td>
          <td>${fmtNum(r.quick_ratio, 2)}</td>
          <td>${fmtNum(r.debt_ratio, 2)}</td>
          <td>${fmtNum(r.debt_to_equity, 2)}</td>
          <td>${fmtMoneyFa(r.working_capital)}</td>
          <td>${fmtMoneyFa(r.receivables)}</td>
          <td>${fmtMoneyFa(r.short_term_debt)}</td>
        </tr>`
        )
        .join("");

      const cashTable = (s4.table || [])
        .map(
          (r) => `<tr>
          <td>${escapeHtml(r.period)}</td>
          <td>${fmtMoneyFa(r.net_profit)}</td>
          <td>${fmtMoneyFa(r.cfo)}</td>
          <td>${fmtNum(r.cfo_to_net, 2)}</td>
          <td>${fmtMoneyFa(r.fcf)}</td>
          <td>${fmtMoneyFa(r.capex)}</td>
        </tr>`
        )
        .join("");

      const listBlock = (items) =>
        (items || [])
          .map(
            (it) =>
              `<li>${evBadge(it.kind)} ${escapeHtml(it.text)} <span class="muted">〔${escapeHtml(it.ref || "—")}〕</span></li>`
          )
          .join("") || "<li class='muted'>—</li>";

      const analysisBlock = (items) =>
        (items || [])
          .map(
            (it) =>
              `<div class="meta" style="margin:.35rem 0">${evBadge(it.kind)} ${escapeHtml(it.text)} <span class="muted">〔${escapeHtml(it.ref || "")}〕</span></div>`
          )
          .join("");

      const periods = (s1.periods || []).join(" | ");
      const audit = s5.audit || {};

      body.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap">
          <div>
            <h2 style="margin:0">${escapeHtml(d.symbol)} — ${escapeHtml(d.name || "")}</h2>
            <p class="muted">${escapeHtml(d.industry || "")} · منبع: ${escapeHtml(d.source || "")}</p>
          </div>
          <div class="pf-actions">
            <span class="score ${scoreClass(d.value_score)}">ارزندگی ${fmtNum(d.value_score, 1)}</span>
            <span class="grade ${gradeClass(d.value_grade)}">${escapeHtml(d.value_grade || d.grade)}</span>
            <a class="btn ghost" href="/symbol?s=${encodeURIComponent(d.symbol)}">صفحه نماد</a>
          </div>
        </div>
        <p class="muted" style="margin:.5rem 0 1rem">${escapeHtml(deep.disclaimer || "")}</p>
        <div class="kv">
          <div><span>P/E · EPS</span><b>${d.pe != null ? fmtNum(d.pe, 2) : "—"} · ${fmtNum(d.eps, 1)}</b></div>
          <div><span>ROE · ROA</span><b>${fmtNum(d.roe, 1)}٪ · ${fmtNum(d.roa, 1)}٪</b></div>
          <div><span>رشد سود · فروش</span><b class="${pctClass(d.profit_growth)}">${fmtNum(d.profit_growth, 1)}٪</b> · <b class="${pctClass(d.revenue_growth)}">${fmtNum(d.revenue_growth, 1)}٪</b></div>
          <div><span>بدهی · جاری</span><b>${fmtNum(d.debt_ratio, 2)} · ${fmtNum(d.current_ratio, 2)}</b></div>
          <div><span>P/B · PEG</span><b>${d.pb != null ? fmtNum(d.pb, 2) : "—"} · ${d.peg != null ? fmtNum(d.peg, 2) : "—"}</b></div>
          <div><span>جزئیات امتیاز</span><b style="font-size:.78rem">${escapeHtml(Object.entries(d.value_score_parts || {}).map(([k,v])=>k+":"+v).join(" · "))}</b></div>
        </div>

        <h3 style="margin:1.2rem 0 .5rem">${escapeHtml(s1.title || "۱) روند")}</h3>
        <p class="muted">دوره‌ها: ${escapeHtml(periods)}</p>
        <div class="table-wrap"><table class="data-table" style="min-width:700px">
          <thead><tr><th>قلم</th><th>دوره۱</th><th>دوره۲</th><th>دوره۳</th><th>تغییر کل٪</th><th>مرجع</th></tr></thead>
          <tbody>${trendTable || '<tr><td colspan="6" class="empty">داده ناکافی</td></tr>'}</tbody>
        </table></div>
        ${analysisBlock(s1.analysis)}

        <h3 style="margin:1.2rem 0 .5rem">${escapeHtml(s2.title || "۲) سودآوری")}</h3>
        <div class="table-wrap"><table class="data-table" style="min-width:700px">
          <thead><tr><th>دوره</th><th>حاشیه ناخالص</th><th>عملیاتی</th><th>خالص</th><th>ROA</th><th>ROE</th><th>غیرعملیاتی/سود٪</th></tr></thead>
          <tbody>${profTable}</tbody>
        </table></div>
        ${analysisBlock(s2.analysis)}

        <h3 style="margin:1.2rem 0 .5rem">${escapeHtml(s3.title || "۳) بدهی/نقدینگی")}</h3>
        <div class="table-wrap"><table class="data-table" style="min-width:800px">
          <thead><tr><th>دوره</th><th>جاری</th><th>آنی</th><th>بدهی</th><th>D/E</th><th>سرمایه در گردش</th><th>مطالبات</th><th>تسهیلات ک.م</th></tr></thead>
          <tbody>${liqTable}</tbody>
        </table></div>
        ${analysisBlock(s3.analysis)}
        <div class="meta"><b>نشانه‌های فشار مالی:</b></div>
        <ul class="reasons">${listBlock(s3.pressure_signals)}</ul>

        <h3 style="margin:1.2rem 0 .5rem">${escapeHtml(s4.title || "۴) کیفیت سود")}</h3>
        <div class="table-wrap"><table class="data-table" style="min-width:700px">
          <thead><tr><th>دوره</th><th>سود خالص</th><th>CFO</th><th>CFO/سود</th><th>FCF</th><th>Capex</th></tr></thead>
          <tbody>${cashTable}</tbody>
        </table></div>
        ${analysisBlock(s4.analysis)}

        <h3 style="margin:1.2rem 0 .5rem">${escapeHtml(s5.title || "۵) قوت و ریسک")}</h3>
        <div class="guide-grid">
          <article><h3>۵ نقطه قوت</h3><ul class="reasons">${listBlock(s5.strengths)}</ul></article>
          <article><h3>۵ ریسک</h3><ul class="reasons">${listBlock(s5.risks)}</ul></article>
          <article><h3>۵ سؤال کلیدی</h3><ul class="reasons">${listBlock(s5.questions)}</ul></article>
          <article>
            <h3>حسابرس و موارد خاص</h3>
            <div class="meta">اظهارنظر: <b>${escapeHtml(audit.opinion || "—")}</b></div>
            <div class="meta">تداوم فعالیت مشکوک: <b>${audit.going_concern_doubt ? "بله" : "خیر"}</b></div>
            <div class="meta">اشخاص وابسته: <b>${audit.related_party ? "دارد" : "ندارد/ذکر نشده"}</b></div>
            <div class="meta">دعاوی/بدهی احتمالی: <b>${audit.legal_cases ? "دارد" : "ندارد/ذکر نشده"}</b></div>
            <div class="meta">تغییر روش حسابداری: <b>${audit.accounting_change ? "بله" : "خیر"}</b></div>
            <div class="muted">〔${escapeHtml(audit.ref || "")}〕 ${evBadge(audit.evidence)}</div>
          </article>
        </div>
      `;
    } catch (e) {
      body.innerHTML = `<p class="pct-down">خطا: ${escapeHtml(e.message)}</p>`;
    }
  }

  function renderFilterHelpers() {
    const presets = $("#filterPresets");
    if (presets && state.filterPresets?.length) {
      presets.innerHTML = state.filterPresets
        .map(
          (p) =>
            `<button class="btn tiny" data-preset="${escapeHtml(p.id)}">${escapeHtml(p.name)}</button>`
        )
        .join("");
      $$("[data-preset]", presets).forEach((b) => {
        b.onclick = () => {
          const p = state.filterPresets.find((x) => x.id === b.dataset.preset);
          if (p) {
            $("#filterExpr").value = p.expr;
            runFilterExpr();
          }
        };
      });
    }
    const fields = $("#filterFields");
    if (fields && state.filterFields?.length) {
      fields.innerHTML = state.filterFields
        .slice(0, 40)
        .map((f) => `<button type="button" data-field="${escapeHtml(f.key)}" title="${escapeHtml(f.label)}">${escapeHtml(f.key)}</button>`)
        .join("");
      $$("[data-field]", fields).forEach((b) => {
        b.onclick = () => {
          const ta = $("#filterExpr");
          const start = ta.selectionStart || ta.value.length;
          const v = ta.value;
          ta.value = v.slice(0, start) + b.dataset.field + v.slice(start);
          ta.focus();
        };
      });
    }
    const saved = $("#savedFilters");
    if (saved) {
      saved.innerHTML = (state.savedFilters || [])
        .map(
          (f) =>
            `<button class="btn tiny" data-loadf="${f.id}">${escapeHtml(f.name)}</button>
             <button class="btn tiny danger-outline" data-delf="${f.id}">×</button>`
        )
        .join("");
      $$("[data-loadf]", saved).forEach((b) => {
        b.onclick = () => {
          const f = state.savedFilters.find((x) => String(x.id) === String(b.dataset.loadf));
          if (f) {
            $("#filterExpr").value = f.expr;
            runFilterExpr();
          }
        };
      });
      $$("[data-delf]", saved).forEach((b) => {
        b.onclick = async () => {
          await api("/api/filter/saved/" + b.dataset.delf, { method: "DELETE" });
          state.savedFilters = (await api("/api/filter/saved")) || [];
          renderFilterHelpers();
        };
      });
    }
  }

  async function runFilterExpr() {
    const expr = $("#filterExpr")?.value || "";
    $("#filterMsg").textContent = "در حال اجرا…";
    try {
      const res = await api("/api/filter/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expr, limit: 100 }),
      });
      state.filterRows = res.rows || [];
      $("#filterMsg").textContent = `${fmtNum(res.count)} نتیجه`;
      renderFilterTable();
    } catch (e) {
      $("#filterMsg").textContent = "خطا: " + (e.message || e);
      $("#filterTable tbody").innerHTML = `<tr><td colspan="11" class="empty">خطا در فیلتر</td></tr>`;
    }
  }

  function renderFilterTable() {
    const tb = $("#filterTable tbody");
    if (!tb) return;
    const rows = state.filterRows || [];
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="11" class="empty">نتیجه‌ای نیست — عبارت را اجرا کنید.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td class="pf-actions">${addBtn(r.symbol)} ${openPageBtn(r.symbol)}</td>
        <td><span class="score ${scoreClass(r.entry_score)}">${fmtNum(r.entry_score, 1)}</span></td>
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name || "")}</span></td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${fmtNum(r.buy_power, 2)}</td>
        <td>${fmtNum(r.volume_ratio, 2)}</td>
        <td>${r.pe != null ? fmtNum(r.pe, 1) : "—"}</td>
        <td>${fmtNum(r.golden_number, 1)}</td>
        <td>${fmtNum(r.fund_score, 1)}</td>
        <td>${tagsHtml(r.tags)}</td>
      </tr>`
      )
      .join("");
  }

  function renderAll() {
    if (!state.analysis) return;
    renderStats(state.analysis.overview);
    renderEntry();
    renderExit();
    renderBig();
    renderTablo();
    renderHot();
    renderGame();
    renderIndustry();
    renderPortfolio();
    renderAlerts();
    renderWatch();
    renderMarketMap();
    renderFundamentals();
    renderValueStocks();
    renderConfluence();
    renderLive();
    renderBacktest();
    if (state.options) renderOptions();
    if (state.filterRows?.length) renderFilterTable();
  }

  function sparkHtml(history) {
    if (!history?.length) return "";
    const vals = history.map((h) => h.plp ?? 0);
    const max = Math.max(...vals.map(Math.abs), 0.1);
    return `<div class="spark" title="روند plp اسنپ‌شات‌ها">${vals
      .slice(-40)
      .map((v) => {
        const h = Math.max(4, (Math.abs(v) / max) * 36);
        return `<i class="${v < 0 ? "neg" : ""}" style="height:${h}px"></i>`;
      })
      .join("")}</div>`;
  }

  async function openSymbol(sym, opts = {}) {
    if (opts.fullPage || (opts.event && (opts.event.ctrlKey || opts.event.metaKey))) {
      location.href = "/symbol?s=" + encodeURIComponent(sym);
      return;
    }
    const modal = $("#symbolModal");
    const body = $("#modalBody");
    body.innerHTML = `<p class="muted">در حال بارگذاری ${escapeHtml(sym)}…</p>`;
    modal.classList.remove("hidden");
    try {
      const data = await api("/api/symbol/" + encodeURIComponent(sym));
      const s = data.snapshot;
      const m = data.metrics;
      const tc = data.tablocastic || {};
      const f = data.fundamental || {};
      const inPf = data.in_portfolio;
      body.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;align-items:flex-start">
          <div>
            <h2 style="margin:0 0 .25rem">${escapeHtml(s.l18)}
              <small style="color:var(--muted);font-weight:400">${escapeHtml(s.l30 || "")}</small>
              <span class="grade ${gradeClass(tc.grade)}" style="margin-right:.4rem">${escapeHtml(tc.grade || "—")}</span>
            </h2>
            <p class="muted">${escapeHtml(s.cs || "")} · منبع: ${escapeHtml(s.source || "")}</p>
          </div>
          <div class="pf-actions">
            <a class="btn primary" href="/symbol?s=${encodeURIComponent(s.l18)}">صفحه کامل ↗</a>
            ${
              inPf
                ? `<button class="btn danger-outline" id="modalPfDel">حذف از پورتفو</button>`
                : `<button class="btn ghost" id="modalPfAdd">＋ پورتفو</button>`
            }
          </div>
        </div>
        <div class="kv">
          <div><span>آخرین قیمت</span><b class="${pctClass(s.plp)}">${fmtNum(s.pl)} (${fmtNum(s.plp, 2)}٪)</b></div>
          <div><span>پایانی</span><b>${fmtNum(s.pc)} (${fmtNum(s.pcp, 2)}٪)</b></div>
          <div><span>حجم / میانگین</span><b>${fmtMoney(s.tvol)} / ×${fmtNum(m.volume_ratio, 2)}</b></div>
          <div><span>ارزش معاملات</span><b>${fmtMoney(s.tval)}</b></div>
          <div><span>قدرت خریدار</span><b>${fmtNum(m.buy_power, 2)}</b></div>
          <div><span>سرانه خرید / فروش</span><b>${fmtMoney(m.buy_per_capita)} / ${fmtMoney(m.sell_per_capita)}</b></div>
          <div><span>خالص حقیقی</span><b class="${m.individual_net_value >= 0 ? "pct-up" : "pct-down"}">${fmtMoney(m.individual_net_value)}</b></div>
          <div><span>P/E · EPS</span><b>${s.pe != null ? fmtNum(s.pe, 2) : "—"} · ${s.eps != null ? fmtNum(s.eps, 1) : "—"}</b></div>
          <div><span>امتیاز ورود / خروج</span><b><span class="pct-up">${fmtNum(m.entry_score, 1)}</span> / <span class="pct-down">${fmtNum(m.exit_score, 1)}</span></b></div>
          <div><span>عدد طلایی · D⁺ · M⁺</span><b>${fmtNum(tc.golden_number, 1)} · ${fmtNum(tc.d_plus, 1)} · ${fmtNum(tc.m_plus, 1)}</b></div>
          <div><span>کیفیت تابلو · بنیادی</span><b>${fmtNum(tc.quality_score, 1)} · ${fmtNum(f.fund_score, 1)} (${escapeHtml(f.grade || "—")})</b></div>
          <div><span>الگوی ساعت / کراس</span><b>${tc.hour_pattern ? "ساعت" : "—"} · ${tc.cross_minutes != null ? fmtNum(tc.cross_minutes, 0) + " دقیقه" : "—"}</b></div>
        </div>
        ${sparkHtml(data.history)}
        <div style="margin-top:1rem">
          <div class="muted" style="margin-bottom:.35rem">دلایل</div>
          ${reasonsHtml(m.reasons)}
          <div style="margin-top:.6rem">${tagsHtml(m.tags)}</div>
          <div class="muted" style="margin-top:.6rem">${escapeHtml((tc.notes || []).join(" · "))}</div>
        </div>
      `;
      $("#modalPfAdd")?.addEventListener("click", async () => {
        await addPortfolio(s.l18);
        openSymbol(s.l18);
      });
      $("#modalPfDel")?.addEventListener("click", async () => {
        await removePortfolio(s.l18);
        openSymbol(s.l18);
      });
    } catch (e) {
      body.innerHTML = `<p class="pct-down">خطا: ${escapeHtml(e.message)}</p>`;
    }
  }

  async function addPortfolio(symbol, note = "") {
    const data = await api("/api/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, note }),
    });
    state.portfolio = data.portfolio || [];
    renderPortfolio();
    renderStats(state.analysis?.overview || {});
  }

  async function removePortfolio(symbol) {
    const data = await api("/api/portfolio/" + encodeURIComponent(symbol), { method: "DELETE" });
    state.portfolio = data.portfolio || [];
    renderPortfolio();
    renderStats(state.analysis?.overview || {});
  }

  async function reloadBig() {
    try {
      state.bigMoves = await api(`/api/big-moves?window_sec=${state.bigWindow}&limit=100`);
      renderBig();
      renderStats(state.analysis?.overview || {});
    } catch (e) {
      console.error(e);
    }
  }

  function bind() {
    $$("#mainTabs .tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$("#mainTabs .tab").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        $$(".panel").forEach((p) => p.classList.remove("active"));
        $("#tab-" + btn.dataset.tab)?.classList.add("active");
      });
    });

    $("#btnRefresh").addEventListener("click", () => refresh(true));
    $("#btnAuto").addEventListener("click", () => {
      state.auto = !state.auto;
      $("#btnAuto").dataset.on = state.auto ? "1" : "0";
      $("#btnAuto").innerHTML = state.auto
        ? '<span class="icon">●</span> خودکار'
        : '<span class="icon">○</span> متوقف';
      setupTimer();
    });

    $("#fMinScore").addEventListener("input", (e) => {
      $("#fMinScoreVal").textContent = e.target.value;
      renderEntry();
    });
    $("#fNegOnly").addEventListener("change", renderEntry);
    $("#fFundOnly").addEventListener("change", renderEntry);
    $("#fTabloQ")?.addEventListener("input", (e) => {
      $("#fTabloQVal").textContent = e.target.value;
      renderTablo();
    });

    $$("#hotTier button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#hotTier button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.hotTier = b.dataset.tier;
        renderHot();
      });
    });
    $$("#hotView button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#hotView button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.hotView = b.dataset.view;
        renderHot();
      });
    });
    $$("#bigWindow button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#bigWindow button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.bigWindow = Number(b.dataset.w);
        reloadBig();
      });
    });
    $$("#bigView button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#bigView button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.bigView = b.dataset.view;
        renderBig();
      });
    });
    $$("#bigSide button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#bigSide button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.bigSide = b.dataset.side;
        renderBig();
      });
    });
    $$("#alertSide button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#alertSide button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.alertSide = b.dataset.side;
        renderAlerts();
      });
    });
    $$("#tabloGrade button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#tabloGrade button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.tabloGrade = b.dataset.g;
        renderTablo();
      });
    });

    $("#btnPfAdd")?.addEventListener("click", async () => {
      const sym = $("#pfSymbol").value.trim();
      if (!sym) return;
      try {
        await addPortfolio(sym, $("#pfNote").value.trim());
        $("#pfSymbol").value = "";
        $("#pfNote").value = "";
      } catch (e) {
        alert("خطا در افزودن: " + e.message);
      }
    });

    $("#btnFilterRun")?.addEventListener("click", () => runFilterExpr());
    $("#btnFilterSave")?.addEventListener("click", async () => {
      const expr = $("#filterExpr")?.value || "";
      const name = prompt("نام فیلتر:", "فیلتر من");
      if (!name) return;
      try {
        const res = await api("/api/filter/saved", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, expr }),
        });
        state.savedFilters = res.filters || [];
        renderFilterHelpers();
        $("#filterMsg").textContent = "ذخیره شد";
      } catch (e) {
        $("#filterMsg").textContent = "خطا در ذخیره: " + e.message;
      }
    });
    $("#btnMapReload")?.addEventListener("click", async () => {
      const sizeBy = $("#mapSize")?.value || "tval";
      const colorBy = $("#mapColor")?.value || "plp";
      state.marketMap = await api(`/api/market-map?size_by=${sizeBy}&color_by=${colorBy}`);
      renderMarketMap();
    });
    $("#mapSize")?.addEventListener("change", () => $("#btnMapReload")?.click());
    $("#mapColor")?.addEventListener("change", () => $("#btnMapReload")?.click());
    $("#fFundMin")?.addEventListener("input", (e) => {
      $("#fFundMinVal").textContent = e.target.value;
      renderFundamentals();
    });

    $("#btnDeepFund")?.addEventListener("click", () => {
      const sym = ($("#deepSym")?.value || "فملی").trim();
      if (sym) openDeepFundamental(sym);
    });
    $("#deepFundClose")?.addEventListener("click", () => $("#deepFundModal")?.classList.add("hidden"));
    $("#deepFundModal")?.addEventListener("click", (e) => {
      if (e.target.id === "deepFundModal") $("#deepFundModal").classList.add("hidden");
    });
    $("#btnValueReload")?.addEventListener("click", async () => {
      const maxPe = Number($("#valMaxPe")?.value || 18);
      const minVal = Number($("#valMinScore")?.value || 55);
      try {
        const pack = await api(`/api/fundamentals/value?limit=50&max_pe=${maxPe}&min_score=${minVal}`);
        state.valueStocks = pack.rows || [];
        state.valueScoring = pack.scoring || null;
        renderValueStocks();
      } catch (e) {
        alert(e.message);
      }
    });

    $("#btnWsReconnect")?.addEventListener("click", () => connectWs());
    $("#btnWsRefresh")?.addEventListener("click", () => {
      try {
        state.ws?.send("refresh");
        liveLog("sent refresh");
      } catch (_) {}
    });

    $("#btnBtRun")?.addEventListener("click", async () => {
      $("#btNotes").textContent = "در حال اجرای بک‌تست…";
      try {
        const body = {
          entry_threshold: Number($("#btEntry").value || 65),
          exit_threshold: Number($("#btExit").value || 60),
          take_profit: Number($("#btTp").value || 4),
          stop_loss: Number($("#btSl").value || -3),
          max_hold_bars: Number($("#btHold").value || 24),
          fee_pct: Number($("#btFee").value || 0.5),
          bars: Number($("#btBars").value || 80),
        };
        const res = await api("/api/backtest/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        state.backtest = res.result;
        renderBacktest();
      } catch (e) {
        $("#btNotes").textContent = "خطا: " + e.message;
      }
    });

    $("#btnOptLoad")?.addEventListener("click", async () => {
      const sym = ($("#optSymbol").value || "فملی").trim();
      try {
        state.options = await api("/api/options/" + encodeURIComponent(sym));
        renderOptions();
      } catch (e) {
        alert("خطا: " + e.message);
      }
    });
    $("#btnOptPrice")?.addEventListener("click", async () => {
      try {
        const res = await api("/api/options/price", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            spot: Number($("#opSpot").value),
            strike: Number($("#opStrike").value),
            days: Number($("#opDays").value || 30),
            vol: Number($("#opVol").value || 0.35),
            rate: Number($("#opRate").value || 0.25),
            option_type: $("#opType").value,
            side: "buy",
          }),
        });
        const g = res.greeks || {};
        $("#optPriceOut").innerHTML = [
          ["قیمت تئوریک", g.price],
          ["Delta", g.delta],
          ["Gamma", g.gamma],
          ["Vega", g.vega],
          ["Theta", g.theta],
          ["Intrinsic", g.intrinsic],
          ["Time value", g.time_value],
          ["Implied move", res.implied_move],
        ]
          .map(([k, v]) => `<div><span>${k}</span><b>${fmtNum(v, 4)}</b></div>`)
          .join("");
        const payoff = res.payoff || [];
        const maxAbs = Math.max(...payoff.map((p) => Math.abs(p.pnl)), 0.1);
        $("#optPayoff").innerHTML = payoff
          .map((p) => {
            const h = Math.max(3, (Math.abs(p.pnl) / maxAbs) * 70);
            return `<i class="${p.pnl < 0 ? "neg" : ""}" style="height:${h}px" title="${p.spot}:${p.pnl}"></i>`;
          })
          .join("");
      } catch (e) {
        alert(e.message);
      }
    });

    $$("#finalAction button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#finalAction button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.finalAction = b.dataset.act;
        renderConfluence();
      });
    });
    $("#btnFinalReload")?.addEventListener("click", async () => {
      try {
        state.confluence = await api("/api/confluence?force=true&limit=80");
        renderConfluence();
        $("#finalMsg").textContent = "جمع‌بندی بروزرسانی شد.";
      } catch (e) {
        $("#finalMsg").textContent = "خطا: " + e.message;
      }
    });
    $("#btnFinalNotify")?.addEventListener("click", async () => {
      $("#finalMsg").textContent = "در حال ارسال هشدارهای خرید/فروش…";
      try {
        const res = await api("/api/confluence/notify-now", { method: "POST" });
        if (res.preview_only) {
          $("#finalMsg").textContent =
            (res.message || "پیش‌نمایش") + ` · ${res.alerts?.length || 0} هشدار آماده`;
        } else {
          $("#finalMsg").textContent = `ارسال شد: ${res.sent} · خرید: ${res.summary?.buy_alerts ?? "—"} · فروش: ${res.summary?.sell_alerts ?? "—"}`;
        }
        await loadNotifyLog();
      } catch (e) {
        $("#finalMsg").textContent = "خطا: " + e.message;
      }
    });

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
        state.notifyCfg = await api("/api/notify/config", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        fillNotifyForm();
        $("#notifyMsg").textContent = "تنظیمات اعلان ذخیره شد.";
        await loadNotifyLog();
      } catch (e) {
        $("#notifyMsg").textContent = "خطا: " + e.message;
      }
    });
    $("#btnNotifyTest")?.addEventListener("click", async () => {
      try {
        const res = await api("/api/notify/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: "تست هشدار رادار بورس ✅ " + new Date().toLocaleString("fa-IR") }),
        });
        state.notifyCfg = res.config;
        fillNotifyForm();
        $("#notifyMsg").textContent = "نتیجه تست: " + JSON.stringify(res.result);
        await loadNotifyLog();
      } catch (e) {
        $("#notifyMsg").textContent = "خطا: " + e.message;
      }
    });

    $("#btnSaveTh")?.addEventListener("click", async () => {
      const payload = {};
      $$("[data-th]").forEach((inp) => {
        payload[inp.dataset.th] = inp.value === "" ? null : Number(inp.value);
      });
      try {
        state.thresholds = await api("/api/config/thresholds", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        $("#settingsMsg").textContent = "ذخیره شد — در حال اعمال با رفرش…";
        await refresh(true);
        $("#settingsMsg").textContent = "تنظیمات اعمال شد.";
      } catch (e) {
        $("#settingsMsg").textContent = "خطا: " + e.message;
      }
    });
    $("#btnResetTh")?.addEventListener("click", async () => {
      state.thresholds = await api("/api/config/thresholds/reset", { method: "POST" });
      renderSettings();
      $("#settingsMsg").textContent = "به پیش‌فرض برگشت.";
      await refresh(true);
    });

    document.addEventListener("click", async (e) => {
      const deepBtn = e.target.closest("[data-deep-sym]");
      if (deepBtn) {
        e.stopPropagation();
        openDeepFundamental(deepBtn.dataset.deepSym);
        return;
      }
      const add = e.target.closest("[data-add]");
      if (add) {
        e.stopPropagation();
        try {
          await addPortfolio(add.dataset.add);
        } catch (err) {
          console.error(err);
        }
        return;
      }
      const del = e.target.closest("[data-del]");
      if (del) {
        e.stopPropagation();
        try {
          await removePortfolio(del.dataset.del);
        } catch (err) {
          console.error(err);
        }
        return;
      }
      const cell = e.target.closest("[data-symbol]");
      if (cell && (cell.classList.contains("tm-cell") || cell.tagName === "TR") && !e.target.closest("button,a")) {
        if (e.detail === 2) {
          location.href = "/symbol?s=" + encodeURIComponent(cell.dataset.symbol);
          return;
        }
        // از تب بنیادی با یک کلیک هم گزارش عمیق
        if (cell.closest("#fundTable") || cell.closest("#valueTable")) {
          openDeepFundamental(cell.dataset.symbol);
          return;
        }
        openSymbol(cell.dataset.symbol, { event: e });
      }
    });

    $("#modalClose").addEventListener("click", () => $("#symbolModal").classList.add("hidden"));
    $("#symbolModal").addEventListener("click", (e) => {
      if (e.target.id === "symbolModal") $("#symbolModal").classList.add("hidden");
    });
  }

  function setupTimer() {
    if (state.timer) clearInterval(state.timer);
    if (state.auto) state.timer = setInterval(() => refresh(false), 30000);
  }

  bind();
  refresh(true);
  setupTimer();
  connectWs();
  // رندر مجدد دیده‌بان بعد از لود ماژول‌ها (رفع race در حالت legacy)
  setTimeout(() => {
    if (window.renderWatchlistExcellent && state.analysis) {
      try { window.renderWatchlistExcellent(state.analysis); } catch (e) {}
    }
  }, 1200);
  // lazy load options default
  setTimeout(() => $("#btnOptLoad")?.click(), 1200);

  // اکسپوز توابع برای ماژول‌ها (auth.js بعد از ورود رفرش می‌کند)
  window.refresh = refresh;
  window.api = api;
})();
