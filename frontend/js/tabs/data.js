/**
 * tabs/data.js — تب‌های جدولی اسکیمامحور
 * هر تابع فقط از store می‌خواند و با renderRows رندر می‌کند.
 * هیچ fetch مستقیمی اینجا نیست.
 */
import { store } from "../core/store.js";
import { esc, fmtNum, fmtMoney, pctClass, scoreClass, gradeClass } from "../core/format.js";
import { renderRows } from "../components/data-table.js";
import { openSymbol, openDeepFundamental } from "./actions.js";

const $ = (s, el = document) => el.querySelector(s);

/* ----------------------------- helpers ----------------------------- */
const symCol = (withName = true) => ({
  key: "symbol",
  label: "نماد",
  render: (r) =>
    `<span class="sym">${esc(r.symbol)}</span>` +
    (withName && r.name ? `<span class="name">${esc(r.name)}</span>` : ""),
});
const addBtn = (r) =>
  `<button class="btn tiny" data-add="${esc(r.symbol)}" title="افزودن به پورتفو">＋</button>`;
const openBtn = (r) =>
  `<a class="btn tiny" href="/symbol?s=${encodeURIComponent(r.symbol)}" onclick="event.stopPropagation()">↗</a>`;

/* ----------------------------- تب: شکار ورود -----------------------------
 * WAVE-AB2 (2026-11-08): فیلترهای «فقط منفی / بنیادی خوب / حداقل امتیاز» که
 * همیشه در HTML بودند اما هرگز خوانده نمی‌شدند (کنترل مرده)، حالا سمت کلاینت
 * روی همان ردیف‌های analysis.entry_signals سرور اعمال می‌شوند — هیچ درخواست
 * یا داده جدیدی جعل نمی‌شود؛ فقط پالایش نمایشی همان داده سرور است. */
export function hunt() {
  let rows = store.get().analysis?.entry_signals || [];
  if ($("#fNegOnly")?.checked) rows = rows.filter((r) => Number(r.plp) < 0);
  if ($("#fFundOnly")?.checked) rows = rows.filter((r) => Array.isArray(r.tags) && r.tags.includes("بنیادی‌خوب"));
  const minScore = Number($("#fMinScore")?.value ?? 0);
  if (Number.isFinite(minScore) && minScore > 0) rows = rows.filter((r) => Number(r.entry_score) >= minScore);
  renderRows($("#entryTable tbody"), [
    { key: "_", label: "", render: (r) => `${addBtn(r)} ${openBtn(r)}` },
    { key: "entry_score", label: "امتیاز", format: "num", cls: (r) => scoreClass(r.entry_score) },
    symCol(),
    { key: "industry", label: "صنعت" },
    { key: "pl", label: "قیمت", format: "num" },
    { key: "plp", label: "٪", format: "pct" },
    { key: "buy_power", label: "قدرت", format: "num" },
    { key: "volume_ratio", label: "حجم×", format: "num" },
    { key: "pe", label: "P/E", format: "num" },
    { key: "individual_net_value", label: "خالص حقیقی", format: "money", cls: (r) => pctClass(r.individual_net_value) },
    { key: "hot_net", label: "برآیند", format: "num", cls: (r) => pctClass(r.hot_net) },
    { key: "tags", label: "تگ‌ها", format: "tags" },
    { key: "reasons", label: "دلایل", format: "reasons" },
  ], rows, "سیگنالی با این فیلترها نیست.", openSymbol);
}

/* ----------------------------- تب: خروج ----------------------------- */
export function exit() {
  const rows = store.get().analysis?.exit_signals || [];
  renderRows($("#exitTable tbody"), [
    { key: "_", label: "", render: addBtn },
    { key: "exit_score", label: "امتیاز", format: "num", cls: (r) => scoreClass(r.exit_score, true) },
    symCol(),
    { key: "industry", label: "صنعت" },
    { key: "pl", label: "قیمت", format: "num" },
    { key: "plp", label: "٪", format: "pct" },
    { key: "buy_power", label: "قدرت", format: "num" },
    { key: "volume_ratio", label: "حجم×", format: "num" },
    { key: "individual_net_value", label: "خالص حقیقی", format: "money", cls: (r) => pctClass(r.individual_net_value) },
    { key: "hot_net", label: "برآیند", format: "num", cls: (r) => pctClass(r.hot_net) },
    { key: "reasons", label: "دلایل", format: "reasons" },
  ], rows, "هشدار خروجی نیست.", openSymbol);
}

/* ----------------------------- تب: پول داغ ----------------------------- */
function flowBar(score) {
  const v = Math.max(0, Math.min(100, score || 0));
  const cls = v >= 70 ? "high" : v >= 45 ? "mid" : "low";
  return `<div class="flow-cell ${cls}"><i style="width:${v}%"></i><span>${fmtNum(score, 0)}</span></div>`;
}

export function hot() {
  const s = store.get();
  const a = s.analysis;
  if (!a) return;
  let rows = [];
  if (s.hotTier === "hot") rows = a.hot_money || [];
  else if (s.hotTier === "plus") rows = a.hot_money_plus || [];
  else rows = [...(a.hot_money || []), ...(a.hot_money_plus || [])].sort((x, y) => y.score - x.score);

  const showHeat = s.hotView === "heat";
  const wrap = $("#hotTableWrap");
  const hm = $("#hotHeatmap");
  if (wrap) wrap.style.display = showHeat ? "none" : "";
  if (hm) {
    hm.style.display = showHeat ? "flex" : "none";
    if (showHeat && rows.length) {
      const maxFlow = Math.max(...rows.map((r) => r.flow_score || 0), 1);
      hm.innerHTML = rows
        .slice(0, 36)
        .map((r) => {
          const heat = (r.flow_score || 0) / maxFlow;
          const bg = r.side === "buy"
            ? `rgba(52,211,153,${(0.25 + heat * 0.7).toFixed(3)})`
            : `rgba(251,113,133,${(0.25 + heat * 0.7).toFixed(3)})`;
          return `<div class="heat-tile" data-symbol="${esc(r.symbol)}" title="${esc(r.symbol)} — ${r.side === "buy" ? "خرید" : "فروش"} · جریان ${fmtNum(r.flow_score, 0)}" style="background:${bg}">
            <b>${esc(r.symbol)}</b><span>${r.side === "buy" ? "⬆" : "⬇"} ${fmtNum(r.flow_score, 0)}</span></div>`;
        })
        .join("");
    }
  }

  renderRows($("#hotTable tbody"), [
    { key: "tier", label: "سطح", render: (r) => (r.tier === "hot" ? "🔥 داغ" : "✨ پلاس") },
    symCol(),
    { key: "side", label: "سمت", render: (r) => `<span class="${r.side === "buy" ? "side-buy" : "side-sell"}">${r.side === "buy" ? "خرید" : "فروش"}</span>` },
    { key: "industry", label: "صنعت" },
    { key: "per_capita", label: "سرانه", format: "money" },
    { key: "buy_power", label: "قدرت", format: "num" },
    { key: "plp", label: "٪", format: "pct" },
    { key: "volume_ratio", label: "حجم×", format: "num" },
    { key: "hot_net", label: "برآیند", format: "num", cls: (r) => pctClass(r.hot_net) },
    { key: "flow_score", label: "جریان", render: (r) => flowBar(r.flow_score) },
    { key: "score", label: "امتیاز", format: "num", cls: (r) => scoreClass(r.score) },
  ], rows, "موردی نیست.", openSymbol);
}

/* ----------------------------- تب: تحرکات بزرگان ----------------------------- */
export function big() {
  const s = store.get();
  let rows = s.bigMoves || [];
  if (s.bigSide !== "all") rows = rows.filter((r) => r.side === s.bigSide);

  const showMatrix = s.bigView === "matrix";
  const wrap = $("#bigTableWrap");
  const mx = $("#bigMatrix");
  if (wrap) wrap.style.display = showMatrix ? "none" : "";
  if (mx) {
    mx.style.display = showMatrix ? "grid" : "none";
    if (showMatrix) {
      mx.innerHTML = rows.length
        ? rows
            .slice(0, 48)
            .map((r) => {
              const maxAbs = Math.max(...rows.map((x) => Math.abs(x.delta_net_value || 0)), 1);
              const heat = Math.abs(r.delta_net_value || 0) / maxAbs;
              const bg =
                r.side === "inflow"
                  ? `rgba(52,211,153,${(0.2 + heat * 0.75).toFixed(3)})`
                  : `rgba(251,113,133,${(0.2 + heat * 0.75).toFixed(3)})`;
              return `<div class="heat-tile" data-symbol="${esc(r.symbol)}" style="background:${bg}">
                <b>${esc(r.symbol)}</b><span>${r.side === "inflow" ? "⬆" : "⬇"} ${fmtMoney(r.delta_net_value)}</span></div>`;
            })
            .join("")
        : `<div class="muted">تحرکی ثبت نشده.</div>`;
    }
  }

  renderRows($("#bigTable tbody"), [
    { key: "score", label: "امتیاز", format: "num", cls: (r) => scoreClass(r.score) },
    symCol(),
    { key: "side", label: "سمت", render: (r) => `<span class="${r.side === "inflow" ? "side-in" : "side-out"}">${r.side === "inflow" ? "ورود" : "خروج"}</span>` },
    { key: "industry", label: "صنعت" },
    { key: "delta_net_value", label: "تغییر پول", format: "money", cls: (r) => pctClass(r.delta_net_value) },
    { key: "delta_plp", label: "Δ٪", format: "num", cls: (r) => pctClass(r.delta_plp) },
    { key: "delta_buy_power", label: "Δقدرت", format: "num", cls: (r) => pctClass(r.delta_buy_power) },
    { key: "delta_hot_net", label: "Δداغ", format: "num", cls: (r) => pctClass(r.delta_hot_net) },
    { key: "pl", label: "قیمت", render: (r) => `${fmtNum(r.pl)} (${fmtNum(r.plp, 2)}٪)` },
    { key: "note", label: "یادداشت", format: "reasons" },
  ], rows, "تحرکی در این پنجره ثبت نشده — چند رفرش صبر کنید.", openSymbol);
}

/* ----------------------------- تب: تابلو کستیک ----------------------------- */
export function tablo() {
  const s = store.get();
  let rows = (s.tablocastic || []).filter((r) => (r.quality_score || 0) >= Number($("#fTabloQ")?.value || 0));
  if (s.tabloGrade !== "all") {
    const g = s.tabloGrade.toUpperCase();
    rows = rows.filter((r) => String(r.grade || "").toUpperCase().startsWith(g));
  }
  renderRows($("#tabloTable tbody"), [
    { key: "grade", label: "درجه", render: (r) => `<span class="grade ${gradeClass(r.grade)}">${esc(r.grade)}</span>` },
    { key: "quality_score", label: "کیفیت", format: "num", cls: (r) => scoreClass(r.quality_score) },
    symCol(),
    { key: "golden_number", label: "طلایی", format: "num" },
    { key: "d_plus", label: "D⁺", format: "num" },
    { key: "m_plus", label: "M⁺", format: "num", cls: (r) => pctClass(r.m_plus) },
    { key: "m_over_d", label: "M/D", format: "num" },
    { key: "queue_power", label: "قدرت صف", format: "num", cls: (r) => pctClass(r.queue_power) },
    { key: "plp", label: "٪", format: "pct" },
    { key: "hour_pattern", label: "ساعت", render: (r) => (r.hour_pattern ? "بله" : "—") },
    { key: "cross_minutes", label: "کراس", render: (r) => (r.cross_minutes != null ? `${fmtNum(r.cross_minutes, 0)}′` : "—") },
    { key: "notes", label: "یادداشت", format: "reasons" },
  ], rows, "موردی نیست.", openSymbol);
}

/* ----------------------------- تب: بازی بازار + قهرمانان شکار ----------------------------- */
function biasBar(v) {
  const pct = Math.min(100, Math.abs(v) * 100);
  return `<div class="bias ${v < 0 ? "neg" : ""}" title="${v}"><i style="width:${pct}%"></i></div>`;
}

export function game() {
  const rows = store.get().analysis?.market_game || [];
  const champions = rows.filter((r) => r.hunt_champion);
  const chEl = $("#huntChampions");
  if (chEl) {
    chEl.innerHTML = champions.length
      ? champions
          .slice(0, 8)
          .map(
            (r) => `
          <div class="icard hunt-card" data-symbol="${esc(r.symbol)}">
            <h4>🎯 ${esc(r.symbol)}</h4>
            <div class="big pct-down">${fmtNum(r.plp, 2)}٪</div>
            <div class="meta">${esc(r.industry || "—")}<br/>غالب: <b>${esc(r.dominant)}</b> · حجم×${fmtNum(r.volume_ratio, 2)}<br/><span class="tag vol">ورود پول در قیمت منفی</span></div>
          </div>`
          )
          .join("")
      : `<div class="icard"><h4>🎯 قهرمان شکار</h4><div class="meta">فعلاً نمادی با «ورود پول هوشمند در قیمت منفی» نیست.</div></div>`;
  }
  renderRows($("#gameTable tbody"), [
    { key: "symbol", label: "نماد", render: (r) => `<span class="sym">${esc(r.symbol)}</span><span class="name">${esc(r.name)}</span>${r.hunt_champion ? ' <span class="tag vol">🎯</span>' : ""}` },
    { key: "industry", label: "صنعت" },
    { key: "big_bias", label: "بزرگان", render: (r) => biasBar(r.big_bias) },
    { key: "mid_bias", label: "متوسط", render: (r) => biasBar(r.mid_bias) },
    { key: "retail_bias", label: "خرد", render: (r) => biasBar(r.retail_bias) },
    { key: "dominant", label: "غالب" },
    { key: "plp", label: "٪", format: "pct" },
    { key: "volume_ratio", label: "حجم×", format: "num" },
    { key: "buy_power", label: "قدرت", format: "num" },
    { key: "note", label: "یادداشت", format: "reasons" },
  ], rows, "موردی نیست.", openSymbol);
}

/* ----------------------------- تب: صنعت ----------------------------- */
export function industry() {
  const rows = store.get().analysis?.industries || [];
  const cards = $("#industryCards");
  if (cards) {
    cards.innerHTML = rows
      .slice(0, 6)
      .map(
        (r) => `
      <div class="icard"><h4>${esc(r.industry)}</h4><div class="big">${fmtNum(r.score, 1)}</div>
        <div class="meta">میانگین: <b class="${pctClass(r.avg_plp)}">${fmtNum(r.avg_plp, 2)}٪</b><br/>کاندید ورود: ${fmtNum(r.entry_candidates)} از ${fmtNum(r.symbol_count)}<br/>
        خالص حقیقی: <b class="${pctClass(r.net_individual_value)}">${fmtMoney(r.net_individual_value)}</b></div></div>`
      )
      .join("");
  }
  renderRows($("#industryTable tbody"), [
    { key: "score", label: "امتیاز", format: "num", cls: (r) => scoreClass(Math.min(100, r.score + 40)) },
    { key: "industry", label: "صنعت", render: (r) => `<b>${esc(r.industry)}</b>` },
    { key: "symbol_count", label: "تعداد", format: "num" },
    { key: "avg_plp", label: "میانگین٪", format: "pct" },
    { key: "total_value", label: "ارزش", format: "money" },
    { key: "net_individual_value", label: "خالص حقیقی", format: "money", cls: (r) => pctClass(r.net_individual_value) },
    { key: "avg_buy_power", label: "قدرت", format: "num" },
    { key: "avg_volume_ratio", label: "حجم×", format: "num" },
    { key: "entry_candidates", label: "کاندید ورود", format: "num" },
  ], rows, "موردی نیست.");
}

/* ----------------------------- تب: بنیادی ----------------------------- */
export function fund() {
  const s = store.get();
  const min = Number($("#fFundMin")?.value || 0);
  const rows = (s.fundamentals || []).filter((r) => (r.value_score || r.fund_score || 0) >= min);
  renderRows($("#fundTable tbody"), [
    { key: "value_score", label: "امتیاز", format: "num", cls: (r) => scoreClass(r.value_score || r.fund_score) },
    { key: "value_grade", label: "درجه", render: (r) => `<span class="grade ${gradeClass(r.value_grade || r.grade)}">${esc(r.value_grade || r.grade)}</span>` },
    { key: "symbol", label: "نماد", render: (r) => `<span class="sym">${esc(r.symbol)}</span><span class="name">${esc(r.name || "")}</span><button class="btn tiny" data-deep-sym="${esc(r.symbol)}">گزارش</button>` },
    { key: "industry", label: "صنعت" },
    { key: "pe", label: "P/E", format: "num" },
    { key: "roe", label: "ROE", format: "num" },
    { key: "profit_growth", label: "رشد سود٪", format: "num", cls: (r) => pctClass(r.profit_growth) },
    { key: "revenue_growth", label: "رشد فروش٪", format: "num", cls: (r) => pctClass(r.revenue_growth) },
    { key: "debt_ratio", label: "بدهی", format: "num" },
    { key: "current_ratio", label: "جاری", format: "num" },
    { key: "notes", label: "یادداشت", format: "reasons" },
  ], rows, "موردی نیست.", openDeepFundamental);
}

/* ----------------------------- تب: سهام ارزنده ----------------------------- */
export function value() {
  const s = store.get();
  const rows = s.valueStocks || [];
  const legend = $("#valueScoreLegend");
  if (legend) {
    const sc = s.valueScoring || {};
    legend.innerHTML = Object.entries(sc)
      .map(([k, v]) => `<div class="icard"><h4>${esc(k)}</h4><div class="meta">${esc(String(v))}</div></div>`)
      .join("");
  }
  renderRows($("#valueTable tbody"), [
    { key: "rank", label: "رتبه", render: (r) => `<b>${fmtNum(r.rank)}</b>` },
    { key: "value_score", label: "ارزندگی", format: "num", cls: (r) => scoreClass(r.value_score) },
    { key: "value_grade", label: "درجه", render: (r) => `<span class="grade ${gradeClass(r.value_grade)}">${esc(r.value_grade)}</span>` },
    { key: "symbol", label: "نماد", render: (r) => `<span class="sym">${esc(r.symbol)}</span><span class="name">${esc(r.name || "")}</span><button class="btn tiny" data-deep-sym="${esc(r.symbol)}">گزارش</button>` },
    { key: "industry", label: "صنعت" },
    { key: "pe", label: "P/E", format: "num" },
    { key: "peg", label: "PEG", format: "num" },
    { key: "roe", label: "ROE", format: "num" },
    { key: "gross_margin", label: "حاشیه", format: "num" },
    { key: "cfo_to_net", label: "CFO/سود", format: "num" },
    { key: "debt_ratio", label: "بدهی", format: "num" },
    { key: "profit_growth", label: "رشد سود٪", format: "num", cls: (r) => pctClass(r.profit_growth) },
    { key: "revenue_growth", label: "رشد فروش٪", format: "num", cls: (r) => pctClass(r.revenue_growth) },
    { key: "score_parts", label: "جزئیات", render: (r) => esc(Object.entries(r.score_parts || {}).map(([k, v]) => `${k}:${v}`).join(" · ")) },
  ], rows, "با این فیلتر سهم ارزنده‌ای نیست.", openDeepFundamental);
}

/* ----------------------------- تب: پورتفو ----------------------------- */
export function portfolio() {
  const rows = store.get().portfolio || [];
  renderRows($("#pfTable tbody"), [
    symCol(),
    { key: "plp", label: "٪", format: "pct" },
    { key: "entry_score", label: "ورود", format: "num", cls: (r) => scoreClass(r.entry_score || 0) },
    { key: "exit_score", label: "خروج", format: "num", cls: (r) => scoreClass(r.exit_score || 0, true) },
    { key: "buy_power", label: "قدرت", format: "num" },
    { key: "golden_number", label: "طلایی", format: "num" },
    { key: "d_plus", label: "D⁺", format: "num" },
    { key: "m_plus", label: "M⁺", format: "num", cls: (r) => pctClass(r.m_plus) },
    { key: "grade", label: "درجه", render: (r) => `<span class="grade ${gradeClass(r.grade)}">${esc(r.grade || "—")}</span>` },
    { key: "side", label: "سمت" },
    { key: "note", label: "یادداشت", format: "reasons" },
    { key: "_", label: "", render: (r) => `<button class="btn tiny danger-outline" data-del="${esc(r.symbol)}">حذف</button>` },
  ], rows, "پورتفو خالی است — از جدول‌ها ＋ بزنید.", openSymbol);
}

/* ----------------------------- تب: هشدارها ----------------------------- */
export function alerts() {
  const s = store.get();
  let rows = s.alerts || [];
  if (s.alertSide !== "all") rows = rows.filter((r) => r.side === s.alertSide);
  renderRows($("#alertTable tbody"), [
    { key: "ts_iso", label: "زمان", render: (r) => new Date(r.ts_iso).toLocaleString("fa-IR") },
    { key: "side", label: "نوع", render: (r) => `<span class="${r.side === "entry" ? "side-in" : "side-out"}">${r.side === "entry" ? "ورود" : "خروج"}</span>` },
    { key: "symbol", label: "نماد", render: (r) => `<span class="sym">${esc(r.symbol)}</span>` },
    { key: "score", label: "امتیاز", format: "num", cls: (r) => scoreClass(r.score || 0, r.side === "exit") },
    { key: "plp", label: "٪", format: "pct" },
    { key: "tags", label: "تگ‌ها", format: "tags" },
    { key: "reasons", label: "دلایل", format: "reasons" },
  ], rows, "هنوز هشداری ثبت نشده.");
}

/* ----------------------------- تب: دیده‌بان ----------------------------- */
export function watch() {
  if (window.renderWatchlistExcellent && store.get().analysis) {
    try {
      window.renderWatchlistExcellent(store.get().analysis);
      return;
    } catch (e) {
      console.warn("watchlist excellent failed", e);
    }
  }
  const rows = store.get().analysis?.watchlist || [];
  renderRows($("#watchTable tbody"), [
    { key: "_", label: "", render: addBtn },
    { key: "entry_score", label: "امتیاز", format: "num", cls: (r) => scoreClass(r.entry_score) },
    symCol(),
    { key: "industry", label: "صنعت" },
    { key: "plp", label: "٪", format: "pct" },
    { key: "buy_power", label: "قدرت", format: "num" },
    { key: "volume_ratio", label: "حجم×", format: "num" },
    { key: "tags", label: "تگ‌ها", format: "tags" },
    { key: "reasons", label: "دلایل", format: "reasons" },
  ], rows, "دیده‌بان خالی است.", openSymbol);
}

/* ----------------------------- تب: جمع‌بندی نهایی (confluence) ----------------------------- */
const actionLabel = (a) => ({ buy: "🟢 خرید", sell: "🔴 فروش", watch_buy: "👁 رصد خرید", watch_sell: "👁 رصد فروش", watch: "—" }[a] || a);
const actionClass = (a) => (a === "buy" ? "side-in" : a === "sell" ? "side-out" : "");

export function finalTab() {
  const s = store.get();
  const conf = s.confluence;
  const sumEl = $("#finalSummary");
  const tb = $("#finalTable tbody");
  if (!sumEl || !tb) return;

  if (!conf) {
    sumEl.innerHTML = `<div class="icard"><h4>جمع‌بندی</h4><div class="meta">در حال بارگذاری…</div></div>`;
    return;
  }
  const sm = conf.summary || {};
  sumEl.innerHTML = [
    ["هشدار خرید", sm.buy_alerts, "pct-up"],
    ["هشدار فروش", sm.sell_alerts, "pct-down"],
    ["رصد", sm.watch, ""],
    ["کل ردیف‌ها", sm.total, ""],
    ["پنجره جریان", ((conf.window_sec || 600) / 60) + " دقیقه", ""],
    ["سطح اعتماد", (conf.data_trust && conf.data_trust.live_verified === true && conf.data_trust.is_live === true && conf.data_trust.state === "live") ? "LIVE" : (conf.trust_level && conf.trust_level !== "live" ? conf.trust_level : "NOT LIVE"), ""],
  ]
    .map(([l, v, c]) => `<div class="icard"><h4>${esc(l)}</h4><div class="big ${c}">${esc(v)}</div></div>`)
    .join("");

  let rows = conf.board || [];
  const act = s.finalAction || "all";
  if (act === "buy") rows = conf.buy_alerts || rows.filter((r) => r.action === "buy");
  else if (act === "sell") rows = conf.sell_alerts || rows.filter((r) => r.action === "sell");
  else if (act === "watch") rows = conf.watchlist || rows.filter((r) => String(r.action || "").startsWith("watch"));

  renderRows(tb, [
    { key: "action", label: "اقدام", render: (r) => `<span class="${actionClass(r.action)}"><b>${actionLabel(r.action)}</b>${r.alert ? " ⚡" : ""}</span>` },
    { key: "combo_score", label: "امتیاز", format: "num", cls: (r) => scoreClass(r.combo_score) },
    { key: "symbol", label: "نماد", render: (r) => `<span class="sym">${esc(r.symbol)}</span><span class="name">${esc(r.name || "")}</span><button class="btn tiny" data-deep-sym="${esc(r.symbol)}">بنیادی</button>` },
    { key: "industry", label: "صنعت" },
    { key: "plp", label: "٪", format: "pct" },
    { key: "pe", label: "P/E", format: "num" },
    { key: "entry_score", label: "تابلو ورود", format: "num" },
    { key: "exit_score", label: "تابلو خروج", format: "num" },
    { key: "value_score", label: "بنیادی", render: (r) => `<span class="score ${scoreClass(r.value_score)}">${fmtNum(r.value_score, 1)}</span> <span class="grade ${gradeClass(r.value_grade)}">${esc(r.value_grade || "")}</span>` },
    { key: "flow_score", label: "جریان", render: (r) => (r.flow_side === "inflow" ? `ورود ${fmtNum(r.flow_score, 0)}` : r.flow_side === "outflow" ? `خروج ${fmtNum(r.flow_score, 0)}` : fmtNum(r.flow_score, 0)) },
    { key: "buy_power", label: "قدرت", format: "num" },
    { key: "volume_ratio", label: "حجم×", format: "num" },
    { key: "reasons", label: "دلایل", format: "reasons" },
  ], rows, "موردی با این فیلتر نیست.", openSymbol);
}

/* ----------------------------- تب: نقشه بازار ----------------------------- */
function colorForMap(val, mode) {
  const t = Math.max(-5, Math.min(5, +val || 0));
  if (mode === "plp" || mode === "hot_net" || mode === "individual_net") {
    return t >= 0 ? `rgba(52,211,153,${(0.25 + (t / 5) * 0.7).toFixed(3)})` : `rgba(251,113,133,${(0.25 + (Math.abs(t) / 5) * 0.7).toFixed(3)})`;
  }
  const tt = Math.max(0, Math.min(100, +val || 0)) / 100;
  return mode === "exit_score" ? `rgba(251,113,133,${(0.2 + tt * 0.75).toFixed(3)})` : `rgba(52,211,153,${(0.2 + tt * 0.75).toFixed(3)})`;
}

export function marketMap() {
  const box = $("#marketMap");
  const mm = store.get().marketMap;
  if (!box || !mm) return;
  const groups = mm.groups || [];
  const total = groups.reduce((a, g) => a + (g.size || 0), 0) || 1;
  const colorBy = mm.color_by || "plp";
  box.innerHTML = groups
    .slice(0, 18)
    .map((g) => {
      const pct = Math.max(8, Math.min(48, (g.size / total) * 100));
      const kids = g.children || [];
      const ksum = kids.reduce((a, k) => a + (k.size || 0), 0) || 1;
      return `<div class="tm-ind" style="flex: ${pct} 1 ${pct * 4}px; min-height:${Math.max(90, pct * 3)}px">
        <label>${esc(g.name)} (${fmtNum(g.count)})</label>
        ${kids
          .slice(0, 24)
          .map((c) => {
            const w = Math.max(12, (c.size / ksum) * 100);
            return `<div class="tm-cell" data-symbol="${esc(c.symbol)}" title="${esc(c.symbol)} ${fmtNum(c.plp, 2)}%" style="flex: ${w} 1 ${Math.max(52, w)}px; background:${colorForMap(c.color, colorBy)}; color:#e8fff6">
              <span class="s">${esc(c.symbol)}</span><span class="p">${fmtNum(c.plp, 1)}٪</span></div>`;
          })
          .join("")}
      </div>`;
    })
    .join("");
  const meta = $("#mapMeta");
  if (meta) meta.textContent = `${fmtNum(mm.symbol_count)} نماد · ${fmtNum(mm.industry_count)} صنعت · اندازه: ${mm.size_by} · رنگ: ${mm.color_by}`;
}
