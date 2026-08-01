/**
 * thermometer.js — دماسنج بازار (ویجت مستقل)
 * t: {state:'bull'|'bear'|'neutral', score:-100..100, label}
 */
import { esc, fmtNum } from "../core/format.js";

export function renderThermometer(t) {
  const stat = document.getElementById("thermoStat");
  if (!stat || !t || typeof t.score !== "number") return;
  const score = t.score;
  const st = t.state || "neutral";
  stat.classList.remove("bull", "bear", "neutral");
  stat.classList.add(st);
  const scoreEl = document.getElementById("thermoScore");
  if (scoreEl) scoreEl.textContent = `${esc(t.label || "—")} ${fmtNum(Math.abs(score), 1)}`;
  const fill = document.getElementById("thermoFill");
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
