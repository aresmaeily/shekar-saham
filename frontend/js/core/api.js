/**
 * api.js — کلاینت HTTP واحد v3 (نشست امن کوکی‌محور)
 * - توکن نشست در کوکی HttpOnly است (غیرقابل دسترسی برای JS → کاهش سطح XSS)
 * - کوکی به‌صورت خودکار با هر درخواستِ هم‌مبدأ ارسال می‌شود؛ نیازی به هدر نیست
 * - خطای 401 → رویداد auth-required (قفل UI) · 429 → toast · سایر → toast مرکزی
 * هیچ fetch دستی خارج از این ماژول مجاز نیست.
 */
import { events } from "./events.js";

/** کلید API برای اسکریپت‌ها/اتوماسیون (اختیاری، از قبل در localStorage ذخیره شده) */
export const getApiKey = () => {
  try {
    return localStorage.getItem("shekar_api_key") || "";
  } catch {
    return "";
  }
};

export const setApiKey = (k) => {
  try {
    if (k) localStorage.setItem("shekar_api_key", k);
    else localStorage.removeItem("shekar_api_key");
  } catch {
    /* ignore */
  }
};

export function toast(text, kind = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${kind}`;
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

/**
 * درخواست واحد.
 * @param {string} path — مسیر نسبی مثل "/api/analyze?force=true"
 * @param {object} [opts] — {method, body, headers}
 */
export async function api(path, opts = {}) {
  const headers = new Headers(opts.headers || {});
  if (opts.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const apiKey = getApiKey();
  if (apiKey && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", apiKey);
  }

  let res;
  try {
    res = await fetch(path, { ...opts, headers, credentials: "same-origin" });
  } catch (e) {
    toast("ارتباط با سرور برقرار نشد", "error");
    throw e;
  }

  if (res.status === 401) {
    events.emit("auth-required", path);
    throw new Error("Unauthorized");
  }
  if (res.status === 429) {
    const retry = res.headers.get("Retry-After") || "60";
    toast(`درخواست زیاد — ${retry} ثانیه صبر کنید`, "warn");
    throw new Error("Rate limited");
  }
  if (res.status === 403) {
    toast("درخواست متقاطع مسدود شد", "error");
    throw new Error("Forbidden");
  }
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    let msg = txt;
    try {
      const j = JSON.parse(txt);
      msg = j.detail || j.error || txt;
      if (Array.isArray(msg)) msg = msg.map((m) => m.msg).join(" · ");
    } catch {
      /* keep raw */
    }
    toast(String(msg).slice(0, 120), "error");
    throw new Error(msg);
  }
  // MASTER-RADAR WAVE-2 (2026-11-04): پاسخ غیر-JSON (مثل پیوست text/csv خروجی
  // بک‌تست) به‌صورت متن خام برگردانده می‌شود — پاسخ JSON مثل قبل parse می‌شود؛
  // رفتار همه مسیرهای JSON دست‌نخورده است.
  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return res.text();
  }
  return res.json();
}
