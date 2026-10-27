/**
 * excellent.js - Creative features rendering (Excellent Edition)
 */
import { Api } from "../api.js";
import { escapeHtml } from "../security.js";

export async function renderDataQuality() {
  const container = document.getElementById("excellentQuality");
  if (!container) return;
  try {
    const data = await Api.health ? await fetch("/api/v07/data-quality").then(r=>r.json()) : null;
    if (!data) return;
    container.innerHTML = `
      <div class="cards">
        <div class="icard"><h4>میانگین کیفیت داده</h4><div class="big">${data.avg_score || "-"}%</div><div class="meta">از 100</div></div>
        <div class="icard"><h4>کل نمادها</h4><div class="big">${data.total || "-"}</div></div>
        <div class="icard"><h4>توزیع اعتماد</h4><div class="meta">${JSON.stringify(data.trust_distribution || {})}</div></div>
      </div>
      <div class="table-wrap" style="margin-top:1rem"><table class="data-table"><thead><tr><th>نماد</th><th>امتیاز</th><th>اعتماد</th><th>مشکلات</th></tr></thead>
      <tbody>${(data.low_quality||[]).slice(0,10).map(s=>`<tr><td>${escapeHtml(s.symbol)}</td><td>${s.score}</td><td>${escapeHtml((s.state === "live" && s.is_live === true && s.live_verified === true) ? "LIVE" : (s.trust === "live" ? "NOT LIVE" : (s.trust || "NOT LIVE")))}</td><td>${escapeHtml((s.issues||[]).join(", "))}</td></tr>`).join("")}</tbody></table></div>
    `;
  } catch(e) {
    container.innerHTML = `<p class="muted">خطا در کیفیت داده: ${e.message}</p>`;
  }
}

export async function renderAnomalies() {
  const container = document.getElementById("excellentAnomalies");
  if (!container) return;
  try {
    const data = await fetch("/api/v07/anomalies?limit=20").then(r=>r.json());
    if (!data.length) {
      container.innerHTML = `<p class="muted">آنومالی خاصی یافت نشد - بازار نرمال</p>`;
      return;
    }
    container.innerHTML = `<div class="table-wrap"><table class="data-table"><thead><tr><th>نماد</th><th>نوع</th><th>امتیاز</th><th>شدت</th><th>جزئیات</th></tr></thead>
      <tbody>${data.map(a=>`<tr data-symbol="${escapeHtml(a.symbol)}"><td><b>${escapeHtml(a.symbol)}</b></td><td>${escapeHtml(a.type)}</td><td>${a.score}</td><td>${escapeHtml(a.severity||"")}</td><td>${escapeHtml(a.details||"")}</td></tr>`).join("")}</tbody></table></div>`;
  } catch(e) {
    container.innerHTML = `<p class="muted">خطا: ${e.message}</p>`;
  }
}

export async function renderRisk(symbol = "فملی") {
  const container = document.getElementById("excellentRisk");
  if (!container) return;
  try {
    const pos = await fetch("/api/v07/risk/position-size?portfolio_value=100000000&entry_price=1000&stop_loss=970&risk_pct=1").then(r=>r.json());
    container.innerHTML = `
      <div class="cards">
        <div class="icard"><h4>موقعیت پیشنهادی</h4><div class="big">${pos.shares || 0} سهم</div><div class="meta">${pos.position_pct}% پرتفو</div></div>
        <div class="icard"><h4>ریسک</h4><div class="big">${pos.risk_amount || 0}</div><div class="meta">${pos.risk_pct}%</div></div>
      </div>
      <p class="muted" style="margin-top:.5rem">${pos.reward_risk_hint || ""}</p>
    `;
  } catch(e) {
    container.innerHTML = `<p class="muted">خطا: ${e.message}</p>`;
  }
}
