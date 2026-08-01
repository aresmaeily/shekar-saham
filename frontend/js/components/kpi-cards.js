/**
 * kpi-cards.js — کارت‌های خلاصه (KPI)
 * items: [{label, value, cls?}]
 */
import { esc } from "../core/format.js";

export function KpiCards(host, items = []) {
  if (!items.length) {
    host.innerHTML = "";
    return;
  }
  host.innerHTML = `<div class="cards">${items
    .map(
      (it) => `
      <div class="icard">
        <h4>${esc(it.label)}</h4>
        <div class="big ${it.cls || ""}">${esc(String(it.value ?? "—"))}</div>
      </div>`
    )
    .join("")}</div>`;
}
