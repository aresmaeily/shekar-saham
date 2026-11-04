/**
 * render/analytics_flow.js — WDA-3 (2026-11-02): جمع‌بندی جریان پول تحلیلی
 *
 * افزودنی (additive-only): فقط داخل تب موجود «تحرکات بزرگان» (#tab-big) از طریق
 * #analyticsFlowPanel رندر می‌شود؛ هیچ تب، مسیر API یا رندر موجودی تغییر نمی‌کند.
 * - همه HTTP از core/api.js (api()) می‌گذرد — هیچ fetch مستقیمی مجاز نیست.
 * - برچسب اعتماد از data_trust سرور خوانده می‌شود (همان پاکت canonical بازار)؛
 *   هیچ برچسب اعتمادی — از جمله «زنده» — اینجا جعل نمی‌شود.
 * - fetch-once در هر بارگذاری صفحه: پنل خلاصه است، نه جریان زنده.
 */
import { api } from "../../core/api.js";
import { esc, fmtNum, fmtMoney } from "../../core/format.js";

let loaded = false;

const TRUST_STATE_LABELS = {
  synthetic: "SYNTHETIC — شبیه‌سازی‌شده",
  mock: "MOCK — داده آزمایشی",
  stale: "STALE — داده قدیمی",
  unavailable: "UNAVAILABLE — داده ناموجود",
  mixed: "MIXED — ترکیبی/تأییدنشده",
};

function trustText(trust) {
  const state = String(trust?.state || trust?.trust_level || "mixed").toLowerCase();
  return TRUST_STATE_LABELS[state] || `اعتماد: ${state}`;
}

export async function renderAnalyticsFlow() {
  const el = document.getElementById("analyticsFlowPanel");
  if (!el || loaded) return;
  loaded = true;
  try {
    const d = await api("/api/v10/analytics/flow");
    const cards = [
      ["حرکت‌های شناسایی‌شده", fmtNum(d.moves_count || 0)],
      ["ورود پول", fmtNum(d.inflow_count || 0)],
      ["خروج پول", fmtNum(d.outflow_count || 0)],
      ["جریان خالص", fmtMoney(d.net_flow_value || 0)],
      ["پوشش پنجره", `${fmtNum(Math.round((d.coverage_sec || 0) / 60))} دقیقه`],
    ]
      .map(
        ([label, value]) =>
          `<div class="icard"><h4>${esc(label)}</h4><div class="big">${esc(value)}</div></div>`
      )
      .join("");
    const suff = d.sufficient === false
      ? `<div class="meta">⚠️ پوشش زمانی پنجره کامل نیست — اعداد خلاصه‌اند</div>`
      : "";
    el.innerHTML = `
      <div class="panel-head">
        <div>
          <h3>جمع‌بندی جریان پول (تحلیلی · WDA-3)</h3>
          <p class="muted">خلاصه تجمیعی از مسیر تحرکات بزرگان — پنجره ${fmtNum(d.window_sec || 0)} ثانیه · ${esc(trustText(d.data_trust))} · داده آزمایشی، مبنای خرید/فروش قرار ندهید</p>
        </div>
      </div>
      <div class="cards">${cards}</div>
      ${suff}`;
  } catch (e) {
    loaded = false; // اجازه تلاش مجدد در رفرش بعدی
    console.warn("analytics flow panel failed", e);
  }
}
