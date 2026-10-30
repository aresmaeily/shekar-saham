/**
 * alert_inbox.js — GOV-41 / D-AI-30 in-product alert inbox (Synthetic/Paper ONLY).
 *
 * - منبع: /api/alerts/inbox (درون‌محصولی؛ بدون هیچ ارسال خارجی)
 * - هر ردیف برچسب اجباری «SYNTHETIC / PAPER — NOT LIVE» دارد (تصمیم مالک ۸)
 * - فقط خلاصه حداقلی نمایش داده می‌شود؛ شناسه‌های شاهد ارجاع داخلی می‌مانند (تصمیم ۷)
 * - وضعیت عملیات: /api/alerts/ops/status (بودجه، صف، kill switch، خطای self دیسپچر)
 * هیچ fetch دستی — همه درخواست‌ها از core/api.js
 */
import { api } from "../core/api.js";
import { esc } from "../core/format.js";

const KIND_FA = {
  MARKET_ANOMALY: "ناهنجاری بازار",
  MATERIAL_COMPANY_DISCLOSURE: "افشای مهم شرکت",
  FILING_REPORT_PUBLICATION: "انتشار اطلاعیه/گزارش",
  SOURCE_CONFLICT: "تعارض منابع",
  SOURCE_STALENESS: "کهنگی منبع",
  SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE: "تغییر مهم صورت‌های مالی",
  WATCHLIST_CHANGE: "تغییر فهرست تحت‌نظر",
  OPPORTUNITY_LIFECYCLE: "چرخه حیات فرصت",
  RESEARCH_RESULT_MATURITY: "بلوغ نتیجه پژوهش",
};

const MANDATORY_LABEL = "SYNTHETIC / PAPER — NOT LIVE";

function el(id) {
  return document.getElementById(id);
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export async function refreshAlertOps() {
  const body = el("alertOpsInboxBody");
  const status = el("alertOpsStatus");
  if (!body) return;
  try {
    const data = await api("/api/alerts/inbox?limit=20");
    const items = Array.isArray(data.items) ? data.items : [];
    body.innerHTML = items
      .map(
        (it) => `<tr>
          <td>${esc(fmtTime(it.delivered_at))}</td>
          <td>${esc(KIND_FA[it.alert_kind] || it.alert_kind || "—")}</td>
          <td>${esc(it.subject || "—")}</td>
          <td class="muted">${esc(it.summary || "")}</td>
          <td><span class="ops-label">${esc(MANDATORY_LABEL)}</span></td>
        </tr>`
      )
      .join("") || `<tr><td colspan="5" class="muted">هشدار عملیاتی صف‌شده‌ای وجود ندارد.</td></tr>`;
    if (status) status.textContent = `رکورد زنده: ${items.length} — همه برچسب‌دار: ${MANDATORY_LABEL}`;
  } catch (e) {
    if (status) status.textContent = "دریافت صندوق هشدارها ناموفق بود.";
  }
  try {
    const st = await api("/api/alerts/ops/status");
    const h = st.health || {};
    const chip = el("alertOpsChip");
    if (chip) {
      const sw = (h.kill_switches || []).find((s) => s.scope === "GLOBAL");
      chip.textContent = `کلید اصلی: ${sw ? sw.state : "ENGAGED (پیش‌فرض)"}`;
    }
  } catch {
    /* وضعیت اختیاری است */
  }
}

export function initAlertInbox() {
  if (!el("alertOpsInboxBody")) return;
  el("btnAlertOpsRefresh")?.addEventListener("click", refreshAlertOps);
  refreshAlertOps();
}

if (typeof window !== "undefined") {
  window.alertInboxRefresh = refreshAlertOps;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initAlertInbox);
  else initAlertInbox();
}
