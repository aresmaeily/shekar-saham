/**
 * watchlist_excellent.js - بهتر از tablokhani.com/stock-watchlist
 * - خلاصه: تعداد کل، مثبت، منفی، ارزش کل (از overview واقعی)
 * - جدول با فیلدهای واقعی دیده‌بان (SignalCard): نماد، صنعت، ٪، قدرت، حجم×، خالص حقیقی، تگ‌ها، دلایل
 * - فیلتر صنعت + جستجو + ذخیره CSV
 */

import { escapeHtml } from "../security.js";

const FIELDS = [
  { key: "symbol", label: "نماد" },
  { key: "name", label: "نام" },
  { key: "industry", label: "صنعت" },
  { key: "plp", label: "٪" },
  { key: "buy_power", label: "قدرت" },
  { key: "volume_ratio", label: "حجم×" },
  { key: "individual_net_value", label: "خالص حقیقی" },
  { key: "tags", label: "تگ‌ها" },
  { key: "reasons", label: "دلایل" },
];

function fmtNum(n, dig = 0) {
  if (n == null || Number.isNaN(+n)) return "—";
  return Number(n).toLocaleString("fa-IR", { maximumFractionDigits: dig });
}
function fmtMoney(v) {
  if (v == null || Number.isNaN(+v)) return "—";
  const a = Math.abs(v);
  const s = v < 0 ? "−" : "";
  if (a >= 1e12) return s + (a / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return s + (a / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return s + (a / 1e6).toFixed(1) + "M";
  if (a >= 1e3) return s + (a / 1e3).toFixed(1) + "K";
  return s + String(Math.round(a));
}
function pctClass(p) {
  if (p > 0) return "pct-up";
  if (p < 0) return "pct-down";
  return "";
}

export function renderWatchlistExcellent(data) {
  const container = document.getElementById("tab-watch");
  if (!container) return;

  const overview = data.overview || {};
  const watchlist = data.watchlist || [];

  // ---------- هدر + خلاصه ----------
  const headerHtml = `
    <div class="panel-head watchlist-header">
      <div>
        <h2>👁 دیده‌بان بورس — بهتر از تابلوخوانی</h2>
        <p class="muted">نمادهای در حال شکل‌گیری قبل از آستانه هشدار · هر رفرش به‌روز می‌شود</p>
      </div>
      <div class="filters">
        <button class="btn ghost" id="btnSaveTable">📥 ذخیره CSV</button>
        <button class="btn primary" id="btnRefreshWatch">↻ به‌روزرسانی</button>
      </div>
    </div>
    <div class="cards" style="grid-template-columns: repeat(4, 1fr); margin-bottom:1rem">
      <div class="icard"><h4>تعداد دیده‌بان</h4><div class="big">${fmtNum(watchlist.length)}</div></div>
      <div class="icard"><h4>مثبت</h4><div class="big pct-up">${fmtNum(watchlist.filter(r => (r.plp||0) > 0).length)}</div></div>
      <div class="icard"><h4>منفی</h4><div class="big pct-down">${fmtNum(watchlist.filter(r => (r.plp||0) < 0).length)}</div></div>
      <div class="icard"><h4>ارزش کل بازار</h4><div class="big">${fmtMoney(overview.total_value)}</div></div>
    </div>
    <div class="filters" style="margin-bottom:1rem">
      <select id="filterIndustry" class="text-input"><option value="all">فیلتر صنعت (همه)</option></select>
      <input id="searchWatch" class="text-input" placeholder="جستجو بر اساس نام یا نماد..." style="min-width:250px" />
    </div>
  `;

  let headerEl = container.querySelector(".watchlist-header");
  if (!headerEl) {
    headerEl = document.createElement("div");
    headerEl.className = "watchlist-header";
    container.prepend(headerEl);
  }
  headerEl.innerHTML = headerHtml;

  // پر کردن فیلتر صنعت
  const indSel = document.getElementById("filterIndustry");
  if (indSel) {
    const inds = [...new Set(watchlist.map((r) => r.industry || "—"))];
    indSel.innerHTML =
      `<option value="all">فیلتر صنعت (همه)</option>` +
      inds.map((i) => `<option value="${escapeHtml(i)}">${escapeHtml(i)}</option>`).join("");
  }

  document.getElementById("btnSaveTable")?.addEventListener("click", () => exportWatchlistToCSV(watchlist));
  document.getElementById("btnRefreshWatch")?.addEventListener("click", () => {
    window.refresh && window.refresh(true);
  });

  // ---------- جدول (با querySelector درست) ----------
  const tb = document.querySelector("#watchTable tbody");
  if (!tb) return;

  const renderRows = () => {
    let rows = watchlist;
    const ind = document.getElementById("filterIndustry")?.value || "all";
    const q = (document.getElementById("searchWatch")?.value || "").trim();
    if (ind !== "all") rows = rows.filter((r) => (r.industry || "—") === ind);
    if (q) rows = rows.filter((r) => (r.symbol || "").includes(q) || (r.name || "").includes(q));

    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="9" class="empty">دیده‌بان خالی است — نمادهای در حال شکل‌گیری اینجا ظاهر می‌شوند.</td></tr>`;
      return;
    }
    tb.innerHTML = rows
      .map(
        (r) => `
      <tr data-symbol="${escapeHtml(r.symbol)}">
        <td><span class="sym">${escapeHtml(r.symbol)}</span><span class="name">${escapeHtml(r.name || "")}</span></td>
        <td>${escapeHtml(r.industry || "—")}</td>
        <td class="${pctClass(r.plp)}">${fmtNum(r.plp, 2)}٪</td>
        <td>${fmtNum(r.buy_power, 2)}</td>
        <td>${fmtNum(r.volume_ratio, 2)}</td>
        <td class="${r.individual_net_value >= 0 ? "pct-up" : "pct-down"}">${fmtMoney(r.individual_net_value)}</td>
        <td>${(r.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</td>
        <td class="reasons">${escapeHtml((r.reasons || []).slice(0, 2).join(" · "))}</td>
        <td>${r.entry_score != null ? `<span class="score ${r.entry_score >= 65 ? "mid" : "low"}">${fmtNum(r.entry_score, 1)}</span>` : "—"}</td>
      </tr>`
      )
      .join("");
  };

  renderRows();
  document.getElementById("filterIndustry")?.addEventListener("change", renderRows);
  document.getElementById("searchWatch")?.addEventListener("input", renderRows);
}

function exportWatchlistToCSV(rows) {
  const headers = ["نماد", "نام", "صنعت", "درصد", "قدرت", "حجمx", "خالص حقیقی", "امتیاز ورود"];
  const csv = [headers.join(",")].concat(
    rows.map((r) =>
      [r.symbol, r.name, r.industry, r.plp, r.buy_power, r.volume_ratio, r.individual_net_value, r.entry_score]
        .map((v) => `"${String(v ?? "")}"`)
        .join(",")
    )
  ).join("\n");

  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `watchlist-${new Date().toISOString().split("T")[0]}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

window.renderWatchlistExcellent = renderWatchlistExcellent;
