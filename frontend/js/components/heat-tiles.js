/**
 * heat-tiles.js — کاشی‌های هیت‌مپ (پول داغ / تحرکات بزرگان)
 * tiles: [{symbol, value, side:'buy'|'inflow'|'sell'|'outflow', title}]
 */
import { esc, fmtMoney } from "../core/format.js";

export function HeatTiles(host, { tiles = [], max = 36, kind = "hot" }) {
  if (!tiles.length) {
    host.innerHTML = `<div class="muted">داده‌ای نیست.</div>`;
    return;
  }
  const maxAbs = Math.max(...tiles.map((t) => Math.abs(t.value || 0)), 1);
  const positive = (t) => t.side === "buy" || t.side === "inflow";

  host.innerHTML = `<div class="${kind === "hot" ? "heat-h" : "heat-g"}">${tiles
    .slice(0, max)
    .map((t) => {
      const heat = Math.abs(t.value || 0) / maxAbs;
      const bg = positive(t)
        ? `rgba(52,211,153,${(0.25 + heat * 0.7).toFixed(3)})`
        : `rgba(251,113,133,${(0.25 + heat * 0.7).toFixed(3)})`;
      const arrow = positive(t) ? "⬆" : "⬇";
      return `<div class="heat-tile" data-symbol="${esc(t.symbol)}" title="${esc(t.title || "")}" style="background:${bg}">
        <b>${esc(t.symbol)}</b>
        <span>${arrow} ${fmtMoney(t.value)}</span>
      </div>`;
    })
    .join("")}</div>`;
}
