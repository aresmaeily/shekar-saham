/**
 * data-table.js — جدول اسکیمامحور
 * یک کامپوننت → همه تب‌های جدولی برنامه (بدون تکرار HTML).
 *
 * schema.columns: [{ key, label, format?: 'num'|'money'|'pct'|'raw',
 *                     render?: (row)=>html, cls?: (row)=>string, sortable?: bool }]
 */
import { esc, fmtNum, fmtMoney, pctClass } from "../core/format.js";

/**
 * renderRows — رندر ردیف‌های یک جدول موجود (بدون ساخت <table>)
 * برای ادغام با تیبل‌های استاتیک index.html.
 */
export function renderRows(tbody, columns, rows = [], empty = "موردی نیست", rowClick = null) {
  const cols = columns.filter((c) => c.visible !== false);

  function cellHtml(row, col) {
    const raw = row[col.key];
    if (col.render) return col.render(row);
    switch (col.format) {
      case "num": return fmtNum(raw, 1);
      case "money": return fmtMoney(raw);
      case "pct": return `<span class="${pctClass(raw)}">${fmtNum(raw, 2)}٪</span>`;
      case "tags": return Array.isArray(raw) ? raw.map((t) => `<span class="tag">${esc(t)}</span>`).join("") : esc(raw);
      case "reasons": {
        const parts = Array.isArray(raw) ? raw.slice(0, 2) : [raw];
        return `<span class="reasons">${esc(parts.filter(Boolean).join(" · "))}</span>`;
      }
      default: return esc(raw);
    }
  }

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${cols.length}" class="empty">${esc(empty)}</td></tr>`;
    return;
  }
  tbody.innerHTML = rows
    .map((r) => {
      const rowCls = typeof cols.some((c) => c.cls && c.cls(r));
      return `<tr data-symbol="${esc(r.symbol || "")}">${cols
        .map((c) => `<td class="${typeof c.cls === "function" ? c.cls(r) : ""}">${cellHtml(r, c)}</td>`)
        .join("")}</tr>`;
    })
    .join("");

  if (rowClick) {
    tbody.onclick = (e) => {
      const tr = e.target.closest("tr[data-symbol]");
      if (tr && !e.target.closest("button,a")) rowClick(tr.dataset.symbol);
    };
  }
}

export function DataTable(host, { columns, rows = [], empty = "موردی نیست", rowClick = null }) {
  const cols = columns.filter((c) => c.visible !== false);

  host.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>${cols.map((c) => `<th data-key="${esc(c.key)}">${esc(c.label)}</th>`).join("")}</tr></thead>
        <tbody></tbody>
      </table>
    </div>`;

  const tbody = host.querySelector("tbody");

  function cellHtml(row, col) {
    const raw = row[col.key];
    if (col.render) return col.render(row);
    switch (col.format) {
      case "num": return fmtNum(raw, 1);
      case "money": return fmtMoney(raw);
      case "pct": return `<span class="${pctClass(raw)}">${fmtNum(raw, 2)}٪</span>`;
      case "tags": return Array.isArray(raw) ? raw.map((t) => `<span class="tag">${esc(t)}</span>`).join("") : esc(raw);
      case "reasons": {
        const parts = Array.isArray(raw) ? raw.slice(0, 2) : [raw];
        return `<span class="reasons">${esc(parts.filter(Boolean).join(" · "))}</span>`;
      }
      default: return esc(raw);
    }
  }

  function render() {
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="${cols.length}" class="empty">${esc(empty)}</td></tr>`;
      return;
    }
    tbody.innerHTML = rows
      .map((r) => {
        const cls = typeof cols.some((c) => c.cls && c.cls(r));
        return `<tr data-symbol="${esc(r.symbol || "")}" class="${cols.some((c) => c.cls && c.cls(r)) ? "" : ""}">${cols
          .map((c) => {
            const clsVal = typeof c.cls === "function" ? c.cls(r) : "";
            return `<td class="${clsVal}">${cellHtml(r, c)}</td>`;
          })
          .join("")}</tr>`;
      })
      .join("");
  }

  if (rowClick) {
    tbody.addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-symbol]");
      if (tr && !e.target.closest("button,a")) rowClick(tr.dataset.symbol);
    });
  }

  render();
  return { rerender: render, setRows: (r) => { rows = r; render(); } };
}
