/**
 * render/strategy_lab.js — MASTER-RADAR directive (2026-11-04): آزمایشگاه استراتژی
 *
 * افزودنی (additive-only): تب جدید «آزمایشگاه استراتژی» — استودیو استراتژی
 * (DSL نسخه RSL-1) + مدیر اندیکاتور. هیچ مسیر، رندر یا رفتار موجودی تغییر
 * نمی‌کند؛ بایند-on-demand با الگوی MutationObserver (مثل chart_pro/forex).
 *
 * قرارداد صداقت:
 * - همه HTTP از core/api.js (api()) می‌گذرد — هیچ fetch مستقیمی مجاز نیست.
 * - هیچ اجرای پویای کد مجاز نیست — فقط innerHTML از متن فرارکننده‌شده (esc).
 * - برچسب اعتماد فقط از data_trust سرور خوانده می‌شود؛ هیچ برچسبی — از جمله
 *   «زنده» — اینجا جعل نمی‌شود.
 * - بک‌تست/بازپخش کاغذی فقط روی داده سینتتیک سرور (SYNTHETIC) است و پاسخ
 *   سرور خودش این را با synthetic_note اعلام می‌کند.
 * - مسیر پیشنهاد استراتژی توسط AI عمداً قطع است (AI2_ENABLED=0؛ دروازه مالک).
 */
import { api, toast } from "../../core/api.js";
import { esc, fmtNum } from "../../core/format.js";

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

const LS_SOURCE_KEY = "strategylab.source.v1";

const SAMPLE_SOURCE = [
  "# نمونه: ورود بالای میانگین سریع، خروج زیر میانگین کند",
  "INPUT fast = 5",
  "RISK stop_loss_pct = 3.0, take_profit_pct = 6.0, max_position_pct = 50.0",
  "ENTRY close > sma(close, fast)",
  "EXIT close < sma(close, 20)",
].join("\n");

let bound = false;

function $(id) {
  return document.getElementById(id);
}

function showOut(objOrText) {
  const out = $("slOut");
  if (!out) return;
  out.textContent = typeof objOrText === "string" ? objOrText : JSON.stringify(objOrText, null, 2);
}

function trustFrom(payload) {
  const el = $("slTrustBadge");
  if (el && payload && payload.trust_envelope) el.textContent = trustText(payload.trust_envelope.data_trust);
}

/* ------------------------- استودیو استراتژی ------------------------- */

async function runAction(path, body) {
  try {
    const res = await api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    trustFrom(res);
    return res;
  } catch (e) {
    // api() خطاها را با متن سرور پرتاب می‌کند؛ پیام امن نمایش داده می‌شود
    return { ok: false, error: String(e && e.message ? e.message : e) };
  }
}

function labParams() {
  return {
    symbol: ($("slSymbol")?.value || "FOLAD").trim().slice(0, 32),
    timeframe: $("slTimeframe")?.value || "1D",
    count: Math.max(50, Math.min(1000, parseInt($("slCount")?.value || "200", 10) || 200)),
  };
}

async function slValidate() {
  const res = await runAction("/api/v10/strategylab/validate", { source: $("slDslSource").value });
  if (res.ok) {
    showOut(res);
    toast("اعتبارسنجی موفق — DSL سالم است", "success");
  } else {
    showOut(res);
    toast("اعتبارسنجی ناموفق — جزئیات در خروجی", "error");
  }
}

async function slSpec() {
  const res = await runAction("/api/v10/strategylab/spec", { source: $("slDslSource").value, name: $("slName")?.value || "dsl.strategy" });
  showOut(res);
  toast(res.ok ? "مشخصات رسمی نسخه‌دار تولید شد" : "خطا در تولید مشخصات", res.ok ? "success" : "error");
}

async function slBacktest() {
  const res = await runAction("/api/v10/strategylab/backtest", { source: $("slDslSource").value, ...labParams() });
  showOut(res);
  toast(res.ok ? "بک‌تست کامل شد (داده سینتتیک)" : "بک‌تست ناموفق", res.ok ? "success" : "error");
}

async function slPaper() {
  const res = await runAction("/api/v10/strategylab/paper-replay", { source: $("slDslSource").value, ...labParams() });
  showOut(res);
  toast(res.ok ? "بازپخش کاغذی کامل شد (نه زنده)" : "بازپخش ناموفق", res.ok ? "success" : "error");
}

function versionRow(v) {
  const tr = document.createElement("tr");
  const canPromote = v.status === "APPROVED";
  tr.innerHTML =
    `<td>${esc(v.version_id)}</td>` +
    `<td>${esc(v.name)}</td>` +
    `<td>${esc(v.status)}</td>` +
    `<td style="direction:ltr">${esc(String(v.source_digest || "").slice(0, 12))}</td>` +
    `<td>${canPromote ? `<button class="btn tiny" data-promote="${esc(v.version_id)}">ارتقا به آزمون کاغذی</button>` : "—"}</td>`;
  const btn = tr.querySelector("[data-promote]");
  if (btn) btn.addEventListener("click", () => slPromote(btn.getAttribute("data-promote")));
  return tr;
}

async function slPromote(versionId) {
  const res = await runAction(`/api/v10/strategylab/versions/${encodeURIComponent(versionId)}/promote`, {});
  showOut(res);
  if (res.version) toast("ارتقا انجام شد — فقط آزمون کاغذی؛ هیچ مسیر زنده‌ای وجود ندارد", "success");
  await slRefreshVersions();
}

async function slRefreshVersions() {
  try {
    const res = await api("/api/v10/strategylab/versions");
    trustFrom(res);
    const body = $("slVersionsBody");
    if (!body) return;
    body.innerHTML = "";
    const list = Array.isArray(res.versions) ? res.versions : [];
    if (!list.length) {
      body.innerHTML = `<tr><td colspan="5" class="muted">فهرست خالی است</td></tr>`;
      return;
    }
    list.forEach((v) => body.appendChild(versionRow(v)));
  } catch (e) {
    toast("دریافت نسخه‌ها ناموفق بود", "error");
  }
}

async function slRegister(approve) {
  const name = ($("slName")?.value || "dsl.strategy").trim() || "dsl.strategy";
  const res = await runAction("/api/v10/strategylab/versions", {
    source: $("slDslSource").value,
    name,
    approve: !!approve,
  });
  showOut(res);
  toast(res.version ? (approve ? "نسخه با تأیید کاربر ثبت شد" : "نسخه پیش‌نویس ثبت شد") : "ثبت نسخه ناموفق", res.version ? "success" : "error");
  await slRefreshVersions();
}

/* ------------------------- مدیر اندیکاتور ------------------------- */

const CATEGORY_FA = {
  trend: "روند",
  momentum: "مومنتوم",
  volatility: "نوسان",
  volume: "حجم",
  breadth: "گستره بازار",
  market_structure: "ساختار بازار",
};

const REPAINT_FA = {
  non_repainting: "بدون بازترسیم",
  repaints_last_bar: "بازترسیم کندل آخر",
  session_dependent: "وابسته به سشن",
};

let catalogCache = null;

async function imLoadCatalog() {
  try {
    const res = await api("/api/v10/indicators");
    trustFrom(res);
    catalogCache = res;
    const body = $("imBody");
    const count = $("imCount");
    if (!body) return;
    body.innerHTML = "";
    const list = Array.isArray(res.indicators) ? res.indicators : [];
    if (count) count.textContent = `${fmtNum(res.count)} اندیکاتور داخلی — نسخه کاتالوگ ${esc(String(res.catalog_version))}`;
    list.forEach((ind) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td><a href="#" data-ind-id="${esc(ind.id)}">${esc(ind.name_fa)}</a><br /><span class="muted" style="font-size:10px;direction:ltr">${esc(ind.id)}</span></td>` +
        `<td>${esc(CATEGORY_FA[ind.category] || ind.category)}</td>` +
        `<td>${fmtNum(ind.warmup_bars)}</td>` +
        `<td>${esc(REPAINT_FA[ind.repaint] || ind.repaint)}</td>`;
      tr.querySelector("[data-ind-id]").addEventListener("click", (e) => {
        e.preventDefault();
        imShowDetail(ind.id);
      });
      body.appendChild(tr);
    });
  } catch (e) {
    toast("بارگذاری کاتالوگ ناموفق بود", "error");
  }
}

async function imShowDetail(id) {
  const detail = $("imDetail");
  if (!detail) return;
  try {
    const res = await api(`/api/v10/indicators/${encodeURIComponent(id)}`);
    const decl = [];
    decl.push(`گرم‌شدن: ${fmtNum(res.warmup_bars)} کندل`);
    decl.push(`داده گمشده: ${esc(String(res.missing_data))}`);
    decl.push(`بازترسیم: ${esc(REPAINT_FA[res.repaint] || String(res.repaint))}`);
    decl.push(`نگاه به آینده: ${res.lookahead_declared ? "دارد" : "ندارد (اعلام‌شده)"}`);
    decl.push(`دسترسی‌ها: ${esc((res.permissions || []).join("، "))}`);
    detail.innerHTML =
      `<h3>${esc(res.name_fa)} — <span style="direction:ltr">${esc(res.id)}</span></h3>` +
      `<p class="muted">${esc(res.math_definition)}</p>` +
      `<p class="muted">${decl.join(" • ")}</p>`;
    // نمونه محاسبه روی داده سینتتیک
    const preview = $("imPreview");
    if (preview) {
      preview.textContent = "در حال محاسبه نمونه روی داده سینتتیک…";
      const q = new URLSearchParams({ symbol: "FOLAD", timeframe: "1D", count: "100", end_bar_index: "1000" });
      try {
        const comp = await api(`/api/v10/indicators/${encodeURIComponent(id)}/compute?${q.toString()}`);
        const seriesNames = Object.keys(comp.series || {});
        const first = seriesNames.length ? comp.series[seriesNames[0]] : [];
        const tail = first.slice(-5).map((r) => `${r.time}: ${r.value}`).join("\n");
        preview.textContent =
          `کلاس داده: ${esc(String(comp.data_class))} — ${esc(String(comp.synthetic_note || ""))}\n` +
          `سری‌ها: ${seriesNames.join("، ")}\nآخرین مقادیر:\n${tail}`;
      } catch (e) {
        preview.textContent = `محاسبه این اندیکاتور از OHLCV ممکن نیست: ${esc(String(e && e.message ? e.message : e))}`;
      }
    }
  } catch (e) {
    detail.textContent = "دریافت جزئیات ناموفق بود";
  }
}

/* ------------------------- بایند-on-demand ------------------------- */

function switchView(view) {
  const studio = $("slStudioView");
  const inds = $("slIndicatorsView");
  if (!studio || !inds) return;
  studio.style.display = view === "indicators" ? "none" : "";
  inds.style.display = view === "indicators" ? "" : "none";
  document.querySelectorAll("#slViewSeg [data-slab-view]").forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-slab-view") === view);
  });
  if (view === "indicators" && !catalogCache) imLoadCatalog();
}

function bindStrategyLab() {
  if (bound || !$("slDslSource")) return;
  bound = true;

  // بازیابی منبع ذخیره‌شده کاربر (localStorage — همان الگوی چارت حرفه‌ای)
  try {
    const saved = localStorage.getItem(LS_SOURCE_KEY);
    $("slDslSource").value = saved || SAMPLE_SOURCE;
  } catch (e) {
    $("slDslSource").value = SAMPLE_SOURCE;
  }
  $("slDslSource").addEventListener("change", () => {
    try {
      localStorage.setItem(LS_SOURCE_KEY, $("slDslSource").value);
    } catch (e) {
      /* ignore */
    }
  });

  const on = (id, fn) => {
    const el = $(id);
    if (el) el.addEventListener("click", fn);
  };
  on("slValidate", slValidate);
  on("slSpec", slSpec);
  on("slBacktest", slBacktest);
  on("slPaper", slPaper);
  on("slRegisterDraft", () => slRegister(false));
  on("slRegisterApproved", () => slRegister(true));
  on("slRefreshVersions", slRefreshVersions);
  on("imRefresh", imLoadCatalog);

  document.querySelectorAll("#slViewSeg [data-slab-view]").forEach((b) => {
    b.addEventListener("click", () => switchView(b.getAttribute("data-slab-view")));
  });

  // فعال‌سازی هنگام باز شدن تب (الگوی chart_pro)
  const observer = new MutationObserver(() => {
    const panel = $("tab-strategylab");
    if (panel && panel.classList.contains("active")) {
      slRefreshVersions();
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
  document.querySelectorAll('[data-tab="strategylab"]').forEach((btn) => {
    btn.addEventListener("click", () => setTimeout(slRefreshVersions, 100));
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindStrategyLab);
  else bindStrategyLab();
}
