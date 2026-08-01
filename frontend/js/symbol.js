/* صفحه نماد — فاز ۳ */
(() => {
  const params = new URLSearchParams(location.search);
  let symbol = decodeURIComponent(params.get("s") || location.pathname.split("/").pop() || "");
  if (!symbol || symbol === "symbol") symbol = "فملی";

  const state = { data: null, chart: null, series: null, mode: "candle" };
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];

  const fmtNum = (n, d = 0) =>
    n == null || Number.isNaN(+n) ? "—" : Number(n).toLocaleString("fa-IR", { maximumFractionDigits: d });
  const fmtMoney = (v) => {
    if (v == null || Number.isNaN(+v)) return "—";
    const a = Math.abs(v),
      s = v < 0 ? "−" : "";
    if (a >= 1e12) return s + (a / 1e12).toFixed(2) + "T";
    if (a >= 1e9) return s + (a / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return s + (a / 1e6).toFixed(1) + "M";
    if (a >= 1e3) return s + (a / 1e3).toFixed(1) + "K";
    return s + Math.round(a);
  };
  const pctClass = (p) => (p > 0 ? "pct-up" : p < 0 ? "pct-down" : "");
  const esc = (s) =>
    String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");

  async function api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  async function load() {
    // برای نمادهای جهانی (XAUUSD, GC1, ...) داده بورس تهران وجود ندارد —
    // مستقیم به حالت جهانی برو (بدون درخواست 404 به API بورس تهران)
    if (TV_MAP[symbol.toUpperCase()]) {
      document.title = symbol.toUpperCase() + " | شکار سهام";
      renderGlobalOnly();
      $("#lastUpdate").textContent = new Date().toLocaleString("fa-IR");
      return;
    }
    try {
      const data = await api("/api/symbol/" + encodeURIComponent(symbol) + "/full");
      state.data = data;
      document.title = `${data.snapshot.l18} | شکار سهام`;
      renderAll();
    } catch (e) {
      // در حالت خصوصی، شاید auth.js هنوز لود نشده — چند بار تلاش مجدد
      if (String(e).includes("401") || String(e).includes("Unauthorized")) {
        window.__symRetries = (window.__symRetries || 0) + 1;
        if (window.__symRetries <= 6) {
          setTimeout(load, 1000);
          return;
        }
      }
      console.warn("Tehran snapshot failed for", symbol, e);
      renderGlobalOnly();
    }
    $("#lastUpdate").textContent = new Date().toLocaleString("fa-IR");
  }

  function renderGlobalOnly() {
    const tvSym = TV_MAP[symbol.toUpperCase()];
    $("#symTitle").textContent = symbol.toUpperCase();
    $("#symSub").textContent = tvSym
      ? "نماد جهانی — نمودار و لینک‌های مرتبط فعال هستند"
      : "داده بورس تهران برای این نماد در دسترس نیست";
    renderTvEmbed();
    renderMoreCharts();
  }

  function renderHero() {
    const s = state.data.snapshot;
    const m = state.data.metrics;
    const tc = state.data.tablocastic || {};
    const f = state.data.fundamental || {};
    $("#symTitle").textContent = s.l18;
    $("#symSub").textContent = `${s.l30 || ""} · ${s.cs || ""}`;
    $("#hPrice").textContent = fmtNum(s.pl);
    $("#hPlp").textContent = `${fmtNum(s.plp, 2)}٪`;
    $("#hPlp").className = "plp " + pctClass(s.plp);
    $("#hGrade").textContent = "تابلو " + (tc.grade || "—");
    $("#hGrade").className = "grade " + gradeClass(tc.grade);
    $("#hFundGrade").textContent = "بنیادی " + (f.grade || "—");
    $("#hSide").textContent = sideFa(m.side);
    $("#hSide").className = "side-pill " + (m.side || "");
    $("#heroStats").innerHTML = [
      ["ورود", fmtNum(m.entry_score, 1), "pct-up"],
      ["خروج", fmtNum(m.exit_score, 1), "pct-down"],
      ["قدرت", fmtNum(m.buy_power, 2), ""],
      ["حجم×", fmtNum(m.volume_ratio, 2), ""],
      ["P/E", s.pe != null ? fmtNum(s.pe, 1) : "—", ""],
      ["طلایی", fmtNum(tc.golden_number, 1), ""],
      ["بنیادی", fmtNum(f.fund_score, 1), ""],
      ["خالص حقیقی", fmtMoney(m.individual_net_value), m.individual_net_value >= 0 ? "pct-up" : "pct-down"],
    ]
      .map(
        ([l, v, c]) =>
          `<div class="chip-stat"><span>${l}</span><b class="${c}">${v}</b></div>`
      )
      .join("");

    const inPf = state.data.in_portfolio;
    $("#btnPf").textContent = inPf ? "✓ در پورتفو" : "＋ پورتفو";
    $("#btnPf").onclick = async () => {
      if (inPf) {
        await api("/api/portfolio/" + encodeURIComponent(s.l18), { method: "DELETE" });
      } else {
        await api("/api/portfolio", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: s.l18 }),
        });
      }
      load();
    };
  }

  function gradeClass(g) {
    const x = String(g || "").toUpperCase();
    if (x.startsWith("A")) return "a";
    if (x.startsWith("B")) return "b";
    if (x.startsWith("C")) return "c";
    return "d";
  }
  function sideFa(s) {
    return { entry: "ورود", exit: "خروج", watch: "رصد", neutral: "خنثی" }[s] || s || "—";
  }

  let excellentChart = null;
  function renderChart() {
    // v0.8 Excellent - Try to use ExcellentChart if available, fallback to old
    if (window.ExcellentChart && !excellentChart) {
      try {
        const container = document.getElementById("tvChart");
        if (container) {
          excellentChart = new window.ExcellentChart("tvChart", symbol);
          excellentChart.init();
          // Add timeframe selector
          const toolbar = document.querySelector(".chart-toolbar");
          if (toolbar && !document.getElementById("tfSelector")) {
            const seg = document.createElement("div");
            seg.className = "seg";
            seg.id = "tfSelector";
            seg.innerHTML = `<button class="active" data-tf="1m">1m</button><button data-tf="5m">5m</button><button data-tf="15m">15m</button><button data-tf="1D">1D</button>`;
            toolbar.appendChild(seg);
            seg.querySelectorAll("button").forEach(btn => {
              btn.onclick = () => {
                seg.querySelectorAll("button").forEach(b=>b.classList.remove("active"));
                btn.classList.add("active");
                excellentChart.setTimeframe(btn.dataset.tf);
              };
            });
          }
          return;
        }
      } catch(e) { console.warn("Excellent chart failed, fallback", e); }
    }

    const el = $("#tvChart");
    if (!el || !window.LightweightCharts) {
      el.innerHTML = `<div class="muted" style="padding:1rem">کتابخانه نمودار لود نشد</div>`;
      return;
    }
    el.innerHTML = "";
    const chart = LightweightCharts.createChart(el, {
      layout: { background: { color: "#0b1220" }, textColor: "#9fb0c7" },
      grid: { vertLines: { color: "rgba(148,163,184,.08)" }, horzLines: { color: "rgba(148,163,184,.08)" } },
      rightPriceScale: { borderColor: "rgba(148,163,184,.15)" },
      timeScale: { borderColor: "rgba(148,163,184,.15)", timeVisible: true },
      crosshair: { mode: 0 },
    });
    state.chart = chart;
    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth, height: el.clientHeight }));
    ro.observe(el);

    if (state.mode === "line") {
      const series = chart.addAreaSeries({
        lineColor: "#22d3ee",
        topColor: "rgba(34,211,238,.35)",
        bottomColor: "rgba(34,211,238,0)",
      });
      const data = (state.data.intraday || [])
        .filter((x) => x.time && x.value)
        .map((x) => ({ time: Math.floor(x.time), value: +x.value }));
      // lightweight-charts business day vs timestamp
      series.setData(data.map((d) => ({ time: d.time, value: d.value })));
      state.series = series;
    } else {
      const series = chart.addCandlestickSeries({
        upColor: "#34d399",
        downColor: "#fb7185",
        borderVisible: false,
        wickUpColor: "#34d399",
        wickDownColor: "#fb7185",
      });
      const data = (state.data.ohlcv || []).map((c) => ({
        time: Math.floor(c.time),
        open: +c.open,
        high: +c.high,
        low: +c.low,
        close: +c.close,
      }));
      series.setData(data);
      state.series = series;
      const vol = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "",
        color: "rgba(129,140,248,.45)",
      });
      vol.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      vol.setData(
        (state.data.ohlcv || []).map((c) => ({
          time: Math.floor(c.time),
          value: +c.volume || 0,
          color: c.close >= c.open ? "rgba(52,211,153,.35)" : "rgba(251,113,133,.35)",
        }))
      );
    }
    chart.timeScale().fitContent();
  }

  function renderBoard() {
    const s = state.data.snapshot;
    const m = state.data.metrics;
    const ob = state.data.orderbook || { bids: [], asks: [] };
    let rows = "";
    for (let i = 0; i < 5; i++) {
      const b = ob.bids[i] || {};
      const a = ob.asks[i] || {};
      rows += `<tr>
        <td class="bid">${fmtNum(b.count)}</td>
        <td class="bid">${fmtMoney(b.volume)}</td>
        <td class="bid">${fmtNum(b.price)}</td>
        <td class="ask">${fmtNum(a.price)}</td>
        <td class="ask">${fmtMoney(a.volume)}</td>
        <td class="ask">${fmtNum(a.count)}</td>
      </tr>`;
    }
    $("#orderbook").innerHTML = `<table class="ob-table">
      <thead><tr><th>ت</th><th>حجم</th><th>خرید</th><th>فروش</th><th>حجم</th><th>ت</th></tr></thead>
      <tbody>${rows}</tbody></table>`;

    $("#clientType").innerHTML = [
      ["خرید حقیقی", fmtMoney(s.Buy_I_Volume)],
      ["فروش حقیقی", fmtMoney(s.Sell_I_Volume)],
      ["خرید حقوقی", fmtMoney(s.Buy_N_Volume)],
      ["فروش حقوقی", fmtMoney(s.Sell_N_Volume)],
      ["سرانه خرید", fmtMoney(m.buy_per_capita)],
      ["سرانه فروش", fmtMoney(m.sell_per_capita)],
      ["قدرت خریدار", fmtNum(m.buy_power, 2)],
      ["خالص حقیقی", fmtMoney(m.individual_net_value)],
    ]
      .map(([k, v]) => `<div><span>${k}</span><b>${v}</b></div>`)
      .join("");

    $("#signalBox").innerHTML = [
      ["امتیاز ورود", fmtNum(m.entry_score, 1)],
      ["امتیاز خروج", fmtNum(m.exit_score, 1)],
      ["پول داغ", fmtNum(m.hot_net, 1)],
      ["حجم×", fmtNum(m.volume_ratio, 2)],
      ["سمت", sideFa(m.side)],
      ["سطح هشدار", m.alert_level || "—"],
    ]
      .map(([k, v]) => `<div><span>${k}</span><b>${v}</b></div>`)
      .join("");
    $("#reasonsBox").innerHTML = `<ul class="reasons">${(m.reasons || [])
      .map((r) => `<li>${esc(r)}</li>`)
      .join("")}</ul>
      <div class="tags" style="margin-top:.5rem">${(m.tags || [])
        .map((t) => `<span class="tag">${esc(t)}</span>`)
        .join("")}</div>`;
  }

  function renderTablo() {
    const tc = state.data.tablocastic || {};
    const items = [
      ["عدد طلایی", tc.golden_number],
      ["D⁺", tc.d_plus],
      ["M⁺", tc.m_plus],
      ["M/D", tc.m_over_d],
      ["کیفیت", tc.quality_score],
      ["قدرت صف", tc.queue_power],
      ["فشار تقاضا", tc.demand_pressure],
      ["جریان هوشمند", tc.smart_flow],
    ];
    $("#tabloCards").innerHTML = items
      .map(
        ([l, v]) =>
          `<div class="icard"><h4>${l}</h4><div class="big">${fmtNum(v, 2)}</div></div>`
      )
      .join("");
    $("#tabloKv").innerHTML = [
      ["درجه", tc.grade],
      ["الگوی ساعت", tc.hour_pattern ? "بله" : "خیر"],
      ["کراس (دقیقه)", tc.cross_minutes ?? "—"],
      ["جهت کراس", tc.cross_direction || "—"],
      ["یادداشت", (tc.notes || []).join(" · ")],
    ]
      .map(([k, v]) => `<div><span>${k}</span><b>${esc(v)}</b></div>`)
      .join("");
  }

  function renderFund() {
    const f = state.data.fundamental || {};
    $("#fundCards").innerHTML = [
      ["امتیاز ارزندگی", f.value_score ?? f.fund_score, ""],
      ["درجه", f.value_grade || f.grade, ""],
      ["P/E", f.pe, ""],
      ["ROE", f.roe, ""],
      ["ROA", f.roa, ""],
      ["رشد سود٪", f.profit_growth, pctClass(f.profit_growth)],
      ["رشد فروش٪", f.revenue_growth, pctClass(f.revenue_growth)],
      ["بدهی", f.debt_ratio, ""],
      ["نسبت جاری", f.current_ratio, ""],
      ["P/B", f.pb, ""],
      ["PEG", f.peg, ""],
    ]
      .map(
        ([l, v, c]) =>
          `<div class="icard"><h4>${l}</h4><div class="big ${c || ""}">${v == null || v === "" ? "—" : typeof v === "number" ? fmtNum(v, 2) : esc(v)}</div></div>`
      )
      .join("");
    $("#quarterTable tbody").innerHTML = (f.quarters || [])
      .map(
        (q) => `<tr>
        <td>${esc(q.period)}</td>
        <td>${fmtMoney(q.revenue)}</td>
        <td>${fmtMoney(q.net_profit)}</td>
        <td>${fmtNum(q.eps, 1)}</td>
        <td>${fmtNum(q.margin, 1)}</td>
        <td class="${pctClass(q.yoy_revenue_growth)}">${q.yoy_revenue_growth != null ? fmtNum(q.yoy_revenue_growth, 1) + "٪" : "—"}</td>
        <td class="${pctClass(q.yoy_profit_growth)}">${q.yoy_profit_growth != null ? fmtNum(q.yoy_profit_growth, 1) + "٪" : "—"}</td>
      </tr>`
      )
      .join("");
    const parts = f.value_score_parts
      ? Object.entries(f.value_score_parts)
          .map(([k, v]) => `${k}:${v}`)
          .join(" · ")
      : "";
    $("#codalLine").textContent = `آخرین رویداد کدال (نمونه): ${f.last_codal_date || ""} — ${f.last_codal_title || ""} · منبع: ${f.source || ""} · اجزای امتیاز: ${parts}`;
  }

  function renderHot() {
    const h = state.data.trade_hot || {};
    if (h.error) {
      $("#hotCards").innerHTML = `<div class="icard"><h4>خطا</h4><div class="meta">${esc(h.error)}</div></div>`;
      return;
    }
    $("#hotCards").innerHTML = [
      ["امتیاز پول داغ", h.score],
      ["خرید داغ", fmtMoney(h.hot_buy_value) + ` (${fmtNum(h.hot_buy_count)})`],
      ["فروش داغ", fmtMoney(h.hot_sell_value) + ` (${fmtNum(h.hot_sell_count)})`],
      ["خالص داغ", fmtMoney(h.net_hot)],
      ["خالص پلاس", fmtMoney(h.net_plus)],
      ["تعداد معاملات", fmtNum(h.trade_count)],
      ["منبع", h.source],
    ]
      .map(
        ([l, v]) =>
          `<div class="icard"><h4>${l}</h4><div class="big" style="font-size:1.1rem">${typeof v === "number" ? fmtNum(v, 1) : esc(v)}</div></div>`
      )
      .join("");

    const rows = (h.largest_trades || []).map((t) => {
      const val = +t.value || 0;
      const tier = val >= (h.threshold_hot || 2e8) ? "داغ" : val >= (h.threshold_plus || 1e8) ? "پلاس" : "عادی";
      return `<tr>
        <td>${esc(t.time_fmt || t.time)}</td>
        <td class="${t.side === "buy" ? "side-buy" : "side-sell"}">${t.side === "buy" ? "خرید" : "فروش"}</td>
        <td>${fmtNum(t.price)}</td>
        <td>${fmtMoney(t.volume)}</td>
        <td>${fmtMoney(val)}</td>
        <td>${tier}</td>
      </tr>`;
    });
    $("#largeTrades tbody").innerHTML = rows.join("") || `<tr><td colspan="6" class="empty">معامله‌ای نیست</td></tr>`;
  }

  function renderHist() {
    const hist = state.data.history || [];
    const vals = hist.map((h) => h.plp ?? 0);
    const max = Math.max(...vals.map(Math.abs), 0.1);
    $("#histSpark").innerHTML = vals
      .slice(-60)
      .map((v) => {
        const h = Math.max(4, (Math.abs(v) / max) * 52);
        return `<i class="${v < 0 ? "neg" : ""}" style="height:${h}px"></i>`;
      })
      .join("");
    $("#histTable tbody").innerHTML =
      hist
        .slice()
        .reverse()
        .slice(0, 80)
        .map((h) => {
          const t = h.ts ? new Date(h.ts * 1000).toLocaleString("fa-IR") : "—";
          return `<tr>
          <td>${esc(t)}</td>
          <td>${fmtNum(h.pl)}</td>
          <td class="${pctClass(h.plp)}">${fmtNum(h.plp, 2)}</td>
          <td>${fmtMoney(h.tvol)}</td>
          <td>${fmtNum(h.buy_power, 2)}</td>
          <td>${fmtNum(h.hot_net, 1)}</td>
          <td>${fmtNum(h.entry_score, 1)}</td>
        </tr>`;
        })
        .join("") || `<tr><td colspan="7" class="empty">تاریخچه‌ای نیست</td></tr>`;
  }

  // نگاشت نمادهای جهانی به نماد TradingView (برای امبد واقعی مثل تابلوخوانی)
  const TV_MAP = {
    XAUUSD: "OANDA:XAUUSD",
    GC1: "COMEX:GC1!",
    GOLD: "COMEX:GC1!",
    DXY: "TVC:DXY",
    US500: "FOREXCOM:SPXUSD",
    US100: "CBOE:NDX",
    US30: "FOREXCOM:DJI",
    UKOIL: "TVC:UKOIL",
    BTCUSDT: "BINANCE:BTCUSDT",
    ETHUSDT: "BINANCE:ETHUSDT",
    EURUSD: "FX:EURUSD",
    GBPUSD: "FX:GBPUSD",
    USDJPY: "FX:USDJPY",
  };

  function renderTvEmbed() {
    const frame = $("#tvFrame");
    if (!frame) return;
    const tvSym = TV_MAP[symbol.toUpperCase()];
    if (tvSym) {
      frame.innerHTML = `
        <iframe scrolling="no" allowtransparency="true" frameborder="0"
          src="https://s.tradingview.com/embed-widget/advanced-chart/?symbol=${encodeURIComponent(tvSym)}&interval=60&theme=dark&style=1&locale=fa_IR&hide_side_toolbar=0&allow_symbol_change=1&save_image=0"
          style="width:100%;height:420px;border:0" title="TradingView ${esc(tvSym)}"></iframe>`;
      return;
    }
    frame.innerHTML = `
      <div class="muted" style="padding:1rem">
        برای نماد بورس تهران (${esc(symbol)}) امبد مستقیم TradingView محدود است.
        نمودار داخلی با MA/EMA/RSI/باند/حجم و ولیو پرفایل معیار اصلی است.
        لینک‌های مرتبط: <a href="/?legacy=1" style="color:#22d3ee">دیده‌بان</a> ·
        <a href="/?legacy=1#tab-hot" style="color:#22d3ee">پول داغ</a> ·
        <a href="/?legacy=1#tab-forex" style="color:#22d3ee">فارکس/طلا</a>
      </div>`;
  }

  // لینک‌های «نمودارهای بیشتر» مثل تابلوخوانی
  function renderMoreCharts() {
    const wrap = $("#moreCharts");
    if (!wrap) return;
    const tvSym = TV_MAP[symbol.toUpperCase()];
    const links = [
      { label: "📈 نمودار اصلی", href: "/symbol?s=" + encodeURIComponent(symbol) },
      { label: "🕐 تایم‌فریم‌های فارکس", href: "/?legacy=1#tab-forex" },
      { label: "🔥 پول داغ", href: "/?legacy=1#tab-hot" },
      { label: "👁 دیده‌بان", href: "/?legacy=1#tab-watch" },
      { label: "🏭 صنعت", href: "/?legacy=1#tab-industry" },
    ];
    if (tvSym) {
      links.unshift({ label: "🌐 TradingView باز", href: "https://www.tradingview.com/chart/?symbol=" + encodeURIComponent(tvSym) });
    }
    wrap.innerHTML = links
      .map((l) => `<a class="btn tiny" href="${esc(l.href)}" target="_blank" rel="noopener">${esc(l.label)}</a>`)
      .join(" ");
  }

  function renderAll() {
    renderHero();
    renderChart();
    renderBoard();
    renderTablo();
    renderFund();
    renderHot();
    renderHist();
    renderTvEmbed();
    renderMoreCharts();
  }

  function bind() {
    $$("#symTabs .tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$("#symTabs .tab").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        $$(".sym-main .panel").forEach((p) => p.classList.remove("active"));
        $("#panel-" + btn.dataset.panel).classList.add("active");
        if (btn.dataset.panel === "chart") setTimeout(renderChart, 30);
      });
    });
    $$("#chartMode button").forEach((b) => {
      b.addEventListener("click", () => {
        $$("#chartMode button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.mode = b.dataset.mode;
        renderChart();
      });
    });
    $("#btnRefresh").onclick = () => load();

    let st = null;
    $("#symSearch").addEventListener("input", (e) => {
      clearTimeout(st);
      const q = e.target.value.trim();
      if (q.length < 1) {
        $("#symSearchResults").classList.add("hidden");
        return;
      }
      st = setTimeout(async () => {
        try {
          const rows = await api("/api/search?q=" + encodeURIComponent(q));
          const box = $("#symSearchResults");
          if (!rows.length) {
            box.classList.add("hidden");
            return;
          }
          box.classList.remove("hidden");
          box.innerHTML = rows
            .map(
              (r) =>
                `<button data-s="${esc(r.symbol)}"><b>${esc(r.symbol)}</b> <span class="sn">${esc(r.name || "")}</span></button>`
            )
            .join("");
          $$("button", box).forEach((btn) => {
            btn.onclick = () => {
              location.href = "/symbol?s=" + encodeURIComponent(btn.dataset.s);
            };
          });
        } catch (err) {
          console.error(err);
        }
      }, 200);
    });
  }

  bind();
  load().catch((e) => {
    $("#symSub").textContent = "خطا: " + e.message;
  });
})();
