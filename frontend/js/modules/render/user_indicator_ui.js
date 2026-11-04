/**
 * user_indicator_ui.js — MASTER-RADAR WAVE-B (2026-11-04) / MR-B4-01
 * پنل «اندیکاتور شخصی (UIDL-1)» — نسخهٔ حکمرانی‌شدهٔ واقعی، جانشین مسیر
 * قدیمیِ regex-محور (که بی‌صدا SMA-۲۰ برمی‌گرداند — غیرصادقانه و حذف‌شدنی).
 *
 * رفتار صادقانهٔ پنل:
 * - اجرای فرمول هرگز در مرورگر انجام نمی‌شود؛ فقط سرور (مفسر محدود RSL-1).
 * - سری رسم‌شدنی از valid_from_index شروع می‌شود (ناحیهٔ گرم‌شدن رسم
 *   نمی‌شود — برچسب شفاف کنار چارت).
 * - برچسب اعتماد فقط از فیلدهای سرور (data_class/SYNTHETIC_SEEDED).
 * - هر خطا صادقانه در همان پنل نمایش داده می‌شود؛ هیچ fallback ساختگی.
 * - بایند-on-demand (الگوی chart_grid): فقط وقتی تب چارت حرفه‌ای فعال شود.
 */
import { toast } from "../../core/api.js";
import { esc, fmtNum } from "../../core/format.js";
import {
  userIndicatorClient,
  plottableSeries,
  UIDL_DOC_EXAMPLES,
  clientValidateSource,
} from "../user_indicator.js";
import { getActiveChartPro } from "./chart_pro.js";

const PANEL_ROOT_ID = "cpUserIndRoot";
const STYLE_ID = "cp-userind-style";
const SERIES_COLORS = [
  "rgba(34,211,238,0.95)",
  "rgba(251,191,36,0.95)",
  "rgba(52,211,153,0.95)",
  "rgba(244,114,182,0.95)",
  "rgba(129,140,248,0.95)",
  "rgba(248,113,113,0.95)",
  "rgba(167,139,250,0.95)",
  "rgba(56,189,248,0.95)",
];

let initialized = false;

function injectStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const st = document.createElement("style");
  st.id = STYLE_ID;
  st.textContent = [
    ".cp-ui-card { border: 1px solid var(--border); border-radius: 12px; padding: .6rem; background: var(--surface2); margin-top:.5rem; }",
    ".cp-ui-src { width: 100%; min-height: 120px; font-family: monospace; direction: ltr; text-align: left; }",
    ".cp-ui-row { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }",
    ".cp-ui-badge { font-size: .72rem; }",
    ".cp-ui-srcout { max-height: 180px; overflow: auto; direction: ltr; text-align: left; font-family: monospace; font-size: .78rem; }",
  ].join("\n");
  document.head.appendChild(st);
}

function activeChart() {
  try {
    const inst = getActiveChartPro ? getActiveChartPro() : null;
    return inst && inst.chart ? inst : null;
  } catch (e) {
    return null;
  }
}

function unmountSeries(id) {
  const rec = userIndicatorClient.mounted.get(id);
  if (!rec) return;
  const inst = activeChart();
  for (const s of rec.series || []) {
    try {
      if (inst) inst.chart.removeSeries(s);
    } catch (e) { /* نمونه چارت عوض شده — هیچ */ }
  }
  userIndicatorClient.mounted.delete(id);
}

async function mountOnChart(rec) {
  const inst = activeChart();
  if (!inst) {
    toast("چارت فعال پیدا نشد — ابتدا چارت حرفه‌ای را باز کنید", "warn");
    return;
  }
  if (userIndicatorClient.mounted.has(rec.id)) unmountSeries(rec.id);
  let comp;
  try {
    comp = await userIndicatorClient.compute(rec.id, {
      symbol: inst.symbol,
      timeframe: inst.timeframe,
      count: 500,
      params: {},
    });
  } catch (e) {
    toast("محاسبه ناموفق بود: " + (e && e.message ? e.message : "خطا"), "error");
    return;
  }
  const validFrom = Number(comp.valid_from_index) || 0;
  const mounted = [];
  const plotNames = Object.keys(comp.plots || {});
  let pi = 0;
  for (const plot of plotNames) {
    const rows = comp.plots[plot];
    const data = plottableSeries(rows, validFrom);
    if (!data.length) continue;
    const color = SERIES_COLORS[pi % SERIES_COLORS.length];
    try {
      const line = inst.chart.addLineSeries({
        color,
        lineWidth: 1.6,
        priceLineVisible: false,
        title: `${rec.name}:${plot}`,
      });
      line.setData(data);
      mounted.push(line);
    } catch (e) { /* پنل عوض شده — صداقت: ادامه بدون این سری */ }
    pi += 1;
  }
  userIndicatorClient.mounted.set(rec.id, {
    series: mounted,
    indicatorName: rec.name,
  });
  const msgEl = document.getElementById("cpUserIndMsg");
  if (msgEl) {
    msgEl.textContent =
      `${rec.name}: ${mounted.length} سری رسم شد (از کندل ${fmtNum(validFrom)} — ` +
      `کلاس داده: ${esc(String(comp.data_class || ""))})`;
  }
}

function renderList(host) {
  const listEl = host.querySelector("#cpUserIndList");
  const msgEl = host.querySelector("#cpUserIndMsg");
  userIndicatorClient
    .list()
    .then((res) => {
      const items = Array.isArray(res.indicators) ? res.indicators : [];
      const cnt = host.querySelector("#cpUserIndCount");
      if (cnt) {
        cnt.textContent = `${fmtNum(res.count)} اندیکاتور کاربر — نسخه DSL ${esc(String(res.dsl_version))}`;
      }
      if (!items.length) {
        listEl.innerHTML = `<div class="muted">هنوز اندیکاتور کاربر ندارید — از بخش «افزودن» یکی بنویسید.</div>`;
        return;
      }
      listEl.innerHTML = items
        .map(
          (ind) => `
        <div class="cp-ui-card" data-uid="${esc(ind.id)}">
          <div class="cp-ui-row">
            <strong>${esc(ind.name_fa || ind.name)}</strong>
            <span class="muted" style="direction:ltr">${esc(ind.id)} · v${esc(String(ind.version))}</span>
            <span class="cp-badge cp-ui-badge ${ind.enabled ? "live" : "synthetic"}">${ind.enabled ? "فعال" : "غیرفعال"}</span>
          </div>
          <div class="muted" style="font-size:.78rem">
            پلات‌ها: ${ind.plots.map((p) => esc(p.name)).join("، ")} · گرم‌شدن: ${fmtNum(ind.warmup_bars)} کندل ·
            checksum: <span style="direction:ltr">${esc(String(ind.checksum).slice(0, 12))}…</span>
          </div>
          <div class="pf-actions cp-ui-row" style="margin-top:.4rem">
            <button class="btn tiny" data-act="mount">نمایش روی چارت</button>
            <button class="btn tiny" data-act="src">متن برنامه</button>
            <button class="btn tiny" data-act="toggle">${ind.enabled ? "غیرفعال" : "فعال"}</button>
            <button class="btn tiny danger-outline" data-act="del">حذف</button>
          </div>
          <pre class="cp-ui-srcout" data-srcfor="${esc(ind.id)}" style="display:none"></pre>
        </div>`,
        )
        .join("");
      listEl.querySelectorAll("[data-act]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const card = btn.closest("[data-uid]");
          const id = card ? card.getAttribute("data-uid") : "";
          if (!id) return;
          const act = btn.getAttribute("data-act");
          try {
            if (act === "mount") {
              const detail = await userIndicatorClient.detail(id);
              await mountOnChart(detail);
            } else if (act === "toggle") {
              const cur = btn.textContent.trim() === "فعال";
              await userIndicatorClient.setEnabled(id, !cur);
              renderList(host);
            } else if (act === "del") {
              unmountSeries(id);
              await userIndicatorClient.remove(id);
              toast("اندیکاتور کاربر حذف شد", "info");
              renderList(host);
            } else if (act === "src") {
              const pre = card.querySelector("[data-srcfor]");
              if (pre.style.display === "none") {
                const detail = await userIndicatorClient.detail(id);
                pre.textContent = detail.source || "";
                pre.style.display = "";
              } else {
                pre.style.display = "none";
              }
            }
          } catch (e) {
            toast("عملیات ناموفق بود: " + (e && e.message ? e.message : "خطا"), "error");
          }
        });
      });
    })
    .catch(() => {
      if (msgEl) msgEl.textContent = "دریافت فهرست اندیکاتورهای کاربر ناموفق بود";
    });
}

function renderAddView(host) {
  const addEl = host.querySelector("#cpUserIndAdd");
  const listEl = host.querySelector("#cpUserIndListWrap");
  const isAdd = addEl.style.display !== "none";
  addEl.style.display = isAdd ? "none" : "";
  listEl.style.display = isAdd ? "" : "none";
  host.querySelector("#cpUserIndSegAdd").classList.toggle("active", !isAdd);
  host.querySelector("#cpUserIndSegList").classList.toggle("active", isAdd);
  if (!isAdd) renderList(host);
}

function bindPanel(host) {
  const segAdd = host.querySelector("#cpUserIndSegAdd");
  const segList = host.querySelector("#cpUserIndSegList");
  segAdd.addEventListener("click", () => renderAddView(host));
  segList.addEventListener("click", () => renderAddView(host));

  const srcTa = host.querySelector("#cpUserIndSrc");
  const valOut = host.querySelector("#cpUserIndValidate");

  host.querySelectorAll("[data-example]").forEach((b) => {
    b.addEventListener("click", () => {
      const ex = UIDL_DOC_EXAMPLES[Number(b.getAttribute("data-example"))] || null;
      if (ex) srcTa.value = ex.source;
    });
  });

  host.querySelector("#cpUserIndValidateBtn").addEventListener("click", async () => {
    valOut.textContent = "…";
    const src = srcTa.value;
    const cv = clientValidateSource(src);
    if (!cv.ok) {
      valOut.textContent = "✗ " + cv.error;
      return;
    }
    try {
      const res = await userIndicatorClient.validate(src);
      valOut.textContent =
        `✓ معتبر — «${res.name}» · پلات‌ها: ${res.plots.map((p) => `${p.name}(گرم‌شدن ${p.warmup_bars})`).join("، ")}` +
        ` · ورودی‌ها: ${Object.keys(res.inputs).length ? JSON.stringify(res.inputs) : "—"}`;
    } catch (e) {
      valOut.textContent = "✗ " + (e && e.message ? e.message : "خطا");
    }
  });

  host.querySelector("#cpUserIndInstallBtn").addEventListener("click", async () => {
    const cv = clientValidateSource(srcTa.value);
    if (!cv.ok) {
      valOut.textContent = "✗ " + cv.error;
      return;
    }
    const version = String(host.querySelector("#cpUserIndVer").value || "1.0.0").trim();
    const nameFa = String(host.querySelector("#cpUserIndFa").value || "").trim();
    try {
      const res = await userIndicatorClient.install(srcTa.value, { version, name_fa: nameFa });
      valOut.textContent = `✓ نصب شد (${res.id}) — پیش‌فرض غیرفعال؛ برای رسم، فعال و «نمایش روی چارت» بزنید`;
      toast("اندیکاتور کاربر نصب شد", "info");
      renderList(host);
    } catch (e) {
      valOut.textContent = "✗ " + (e && e.message ? e.message : "خطا");
    }
  });

  host.querySelector("#cpUserIndExportBtn").addEventListener("click", async () => {
    try {
      const pkg = await userIndicatorClient.exportPackage();
      const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "radar_user_indicators_uidl_pkg_1.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } catch (e) {
      toast("خروجی گرفتن ناموفق بود", "error");
    }
  });

  const fileInput = host.querySelector("#cpUserIndFile");
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    try {
      const text = await file.text();
      const doc = JSON.parse(text); // فقط JSON.parse داده — هرگز اجرا نمی‌شود
      const res = await userIndicatorClient.importPackage(doc);
      toast(`بسته وارد شد (${res.installed} اندیکاتور، غیرفعال)`, "info");
      renderList(host);
    } catch (e) {
      toast("واردکردن بسته ناموفق بود: " + (e && e.message ? e.message : "خطا"), "error");
    } finally {
      fileInput.value = "";
    }
  });

  renderList(host);
}

function ensurePanel() {
  if (initialized) return;
  const root = document.getElementById(PANEL_ROOT_ID);
  if (!root) return; // تدافعی: کانتینر نیست → ماژول no-op می‌ماند
  initialized = true;
  injectStyle();
  root.innerHTML = `
    <div class="panel-head">
      <div>
        <h3>🧪 اندیکاتور شخصی (UIDL-1) — موتور حکمرانی‌شده سمت سرور</h3>
        <p class="muted">زبان محدود UIDL-1: INDICATOR / INPUT / PLOT — اجرا فقط با مفسر محدود RSL-1؛ بدون eval/exec؛ بدون نگاه به آینده (ref منفی رد می‌شود)</p>
      </div>
    </div>
    <div class="cp-ui-row">
      <button class="btn tiny active" id="cpUserIndSegList">فهرست</button>
      <button class="btn tiny" id="cpUserIndSegAdd">افزودن (UIDL-1)</button>
      <button class="btn tiny" id="cpUserIndExportBtn">خروجی بسته</button>
      <label class="btn tiny" for="cpUserIndFile">ورود بسته</label>
      <input type="file" id="cpUserIndFile" accept="application/json" style="display:none" />
      <span class="muted" id="cpUserIndCount"></span>
    </div>
    <div id="cpUserIndListWrap">
      <div id="cpUserIndList" class="cards" style="margin-top:.5rem"></div>
    </div>
    <div id="cpUserIndAdd" style="display:none">
      <div class="cp-ui-card">
        <textarea id="cpUserIndSrc" class="cp-ui-src" spellcheck="false">${esc(
          UIDL_DOC_EXAMPLES[0].source,
        )}</textarea>
        <div class="cp-ui-row" style="margin-top:.4rem">
          ${UIDL_DOC_EXAMPLES.map(
            (ex, i) => `<button class="btn tiny" data-example="${i}">${esc(ex.label)}</button>`,
          ).join("")}
        </div>
        <div class="cp-ui-row" style="margin-top:.4rem">
          <input id="cpUserIndVer" class="text-input" placeholder="نسخه 1.0.0" value="1.0.0" style="max-width:110px" />
          <input id="cpUserIndFa" class="text-input" placeholder="نام فارسی (اختیاری)" style="max-width:180px" />
          <button class="btn tiny" id="cpUserIndValidateBtn">اعتبارسنجی</button>
          <button class="btn tiny primary" id="cpUserIndInstallBtn">نصب (غیرفعال)</button>
        </div>
        <p class="muted" id="cpUserIndValidate" style="direction:ltr"></p>
        <p class="muted" style="font-size:.78rem">
          توابع مجاز: sma · ema · rsi · stdev · highest · lowest · atr · abs · min · max · ref ·
          پایه‌ها: open/high/low/close/volume · MTF: D1./W1./M1./H4./H1. — هر PLOT باید «سری عددی» باشد
          (مقایسه/AND/OR/کِراس پلات نمی‌شود) — همین محدودیت‌ها همان تضمین‌های امنیتی RSL-1 است.
        </p>
      </div>
    </div>
    <p class="muted" id="cpUserIndMsg"></p>
  `;
  bindPanel(root);
}

/* ---------------- بایند-on-demand (الگوی chart_grid/chart_pro) ---------------- */

function bindUserIndicatorTab() {
  if (initialized) return;
  const observer = new MutationObserver(() => {
    const panel = document.getElementById("tab-chartpro");
    if (panel && panel.classList.contains("active")) ensurePanel();
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
  document.querySelectorAll('[data-tab="chartpro"]').forEach((btn) => {
    btn.addEventListener("click", () => setTimeout(ensurePanel, 100));
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindUserIndicatorTab);
  } else {
    bindUserIndicatorTab();
  }
}
