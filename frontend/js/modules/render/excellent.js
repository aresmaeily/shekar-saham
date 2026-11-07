/**
 * excellent.js — رندر امکانات «نسخه عالی» (تب ✨)
 * WAVE-AB2 (2026-11-08): این ماژول از قبل موجود بود اما هیچ‌کس آن را import
 * نمی‌کرد و پنل‌هایش برای همیشه «در حال بارگذاری…» می‌ماندند (کنترل مرده ثبت‌شده
 * در ممیزی WP-J). اکنون main.js هنگام باز شدن تب آن را صدا می‌زند.
 *
 * مهاجرت مرز HTTP: همه واکشی‌ها از core/api.js (api()) می‌گذرند — هیچ واکشی مستقیم بومی مرورگر باقی نمی‌ماند
 * مستقیمی باقی نمی‌ماند (همان مرزی که بقیه ماژول‌های مدرن دارند؛ ۴۰۱ قفل auth،
 * ۴۲۹ toast مرکزی). همه متن‌های درون‌یابی‌شده esc/escapeHtml می‌شوند و برچسب
 * اعتماد فقط از فیلدهای سرور می‌آید — هیچ برچسب «زنده» اینجا جعل نمی‌شود.
 */
import { api } from "../../core/api.js";
import { escapeHtml } from "../security.js";

function failBox(container, where, e) {
  container.innerHTML = `<p class="muted">خطا در ${escapeHtml(where)}: ${escapeHtml(String(e && e.message ? e.message : e))}</p>`;
}

export async function renderDataQuality() {
  const container = document.getElementById("excellentQuality");
  if (!container) return;
  try {
    const data = await api("/api/v07/data-quality");
    container.innerHTML = `
      <div class="cards">
        <div class="icard"><h4>میانگین کیفیت داده</h4><div class="big">${escapeHtml(String(data.avg_score ?? "-"))}%</div><div class="meta">از 100</div></div>
        <div class="icard"><h4>کل نمادها</h4><div class="big">${escapeHtml(String(data.total ?? "-"))}</div></div>
        <div class="icard"><h4>توزیع اعتماد</h4><div class="meta">${escapeHtml(JSON.stringify(data.trust_distribution || {}))}</div></div>
      </div>
      <div class="table-wrap" style="margin-top:1rem"><table class="data-table"><thead><tr><th>نماد</th><th>امتیاز</th><th>اعتماد</th><th>مشکلات</th></tr></thead>
      <tbody>${(data.low_quality||[]).slice(0,10).map(s=>`<tr><td>${escapeHtml(String(s.symbol))}</td><td>${escapeHtml(String(s.score ?? "-"))}</td><td>${escapeHtml((s.state === "live" && s.is_live === true && s.live_verified === true) ? "LIVE" : (s.trust === "live" ? "NOT LIVE" : (s.trust || "NOT LIVE")))}</td><td>${escapeHtml((s.issues||[]).join(", "))}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">فهرست خالی است — چیزی جعل نمی‌شود</td></tr>`}</tbody></table></div>
    `;
  } catch(e) {
    failBox(container, "کیفیت داده", e);
  }
}

export async function renderAnomalies() {
  const container = document.getElementById("excellentAnomalies");
  if (!container) return;
  try {
    const data = await api("/api/v07/anomalies?limit=20");
    if (!Array.isArray(data) || !data.length) {
      container.innerHTML = `<p class="muted">آنومالی خاصی یافت نشد - بازار نرمال</p>`;
      return;
    }
    container.innerHTML = `<div class="table-wrap"><table class="data-table"><thead><tr><th>نماد</th><th>نوع</th><th>امتیاز</th><th>شدت</th><th>جزئیات</th></tr></thead>
      <tbody>${data.map(a=>`<tr data-symbol="${escapeHtml(String(a.symbol))}"><td><b>${escapeHtml(String(a.symbol))}</b></td><td>${escapeHtml(String(a.type ?? "-"))}</td><td>${escapeHtml(String(a.score ?? "-"))}</td><td>${escapeHtml(String(a.severity ?? ""))}</td><td>${escapeHtml(String(a.details ?? ""))}</td></tr>`).join("")}</tbody></table></div>`;
  } catch(e) {
    failBox(container, "تشخیص آنومالی", e);
  }
}

export async function renderRisk(symbol = "فملی") {
  const container = document.getElementById("excellentRisk");
  if (!container) return;
  try {
    const pos = await api("/api/v07/risk/position-size?portfolio_value=100000000&entry_price=1000&stop_loss=970&risk_pct=1");
    container.innerHTML = `
      <div class="cards">
        <div class="icard"><h4>موقعیت پیشنهادی</h4><div class="big">${escapeHtml(String(pos.shares ?? 0))} سهم</div><div class="meta">${escapeHtml(String(pos.position_pct ?? "-"))}% پرتفو</div></div>
        <div class="icard"><h4>ریسک</h4><div class="big">${escapeHtml(String(pos.risk_amount ?? 0))}</div><div class="meta">${escapeHtml(String(pos.risk_pct ?? "-"))}%</div></div>
      </div>
      <p class="muted" style="margin-top:.5rem">${escapeHtml(String(pos.reward_risk_hint ?? ""))}</p>
    `;
  } catch(e) {
    failBox(container, "مدیریت ریسک", e);
  }
}

/* WAVE-AB2: پنل «بهینه‌سازی پرتفو (MPT)» — قبلاً هیچ رندری نداشت؛ اکنون از
 * همان API آزموده (/api/v07/portfolio/optimization) می‌خواند و عیناً نمایش
 * می‌دهد؛ خالی/خطا صادقانه. */
export async function renderPortfolioOptimization() {
  const container = document.getElementById("excellentPortfolio");
  if (!container) return;
  try {
    const data = await api("/api/v07/portfolio/optimization");
    const rows = Array.isArray(data?.optimized_portfolio) ? data.optimized_portfolio : [];
    if (!rows.length) {
      container.innerHTML = `<p class="muted">پاسخ سرور برای بهینه‌سازی پرتفو خالی بود — چیزی جعل نمی‌شود.</p>`;
      return;
    }
    container.innerHTML = `
      <div class="table-wrap"><table class="data-table">
        <thead><tr><th>نماد</th><th>نام</th><th>صنعت</th><th>دلیل</th></tr></thead>
        <tbody>${rows.map((w) => `<tr><td>${escapeHtml(String(w.symbol ?? "-"))}</td><td>${escapeHtml(String(w.name ?? ""))}</td><td>${escapeHtml(String(w.industry ?? "-"))}</td><td>${escapeHtml(String(w.reason ?? w.reasons ?? "").slice(0, 200))}</td></tr>`).join("")}</tbody>
      </table></div>
      <p class="muted" style="margin-top:.5rem">${escapeHtml(String(data.principle ?? ""))}</p>
      <p class="muted" style="margin-top:.25rem">${escapeHtml(String(data.risk_note ?? ""))}</p>
    `;
  } catch(e) {
    failBox(container, "بهینه‌سازی پرتفو", e);
  }
}
