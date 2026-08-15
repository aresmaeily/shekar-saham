/**
 * render/trust.js - Trust banner rendering - P0-1/P3.31 data-trust hardening
 */
import { escapeHtml } from "../security.js";

function normalizeTrust(input, sourceFallback = "") {
  if (input && typeof input === "object") {
    const state = String(input.state || input.trust_state || input.trust_level || "mixed").toLowerCase();
    return {
      state,
      level: String(input.trust_level || state || "mixed").toLowerCase(),
      source: input.source || input.provider || sourceFallback || "unknown",
      warning: input.warning || "",
      ageSec: input.age_sec,
      isLive: input.is_live === true,
      liveVerified: input.live_verified === true,
    };
  }
  const level = String(input || "mixed").toLowerCase();
  const state = level === "synthetic" ? "synthetic" : level;
  return { state, level, source: sourceFallback || "unknown", warning: "", ageSec: null, isLive: false, liveVerified: false };
}

function trustPresentation(trust) {
  const verifiedLive = trust.state === "live" && trust.isLive === true && trust.liveVerified === true;
  if (trust.state === "live" && !verifiedLive) {
    return {
      cls: "mixed",
      pill: "اعتماد: UNVERIFIED LIVE-CLASS - تأیید نشده",
      icon: "⚠️",
      banner: "⚠️ منبع زنده‌نما تأیید مستقل نشده است و مبنای خرید/فروش نیست",
    };
  }
  switch (trust.state) {
    case "live":
      if (!verifiedLive) {
        return {
          cls: "mixed",
          pill: "اعتماد: UNVERIFIED LIVE-CLASS - تأیید نشده",
          icon: "⚠️",
          banner: "⚠️ منبع زنده‌نما تأیید مستقل نشده است و مبنای خرید/فروش نیست",
        };
      }
      return { cls: "live", pill: "اعتماد: LIVE - داده زنده", icon: "✅", banner: "داده زنده", hide: true };
    case "mock":
      return { cls: "demo", pill: "اعتماد: MOCK - داده آزمایشی", icon: "🚨", banner: "🚨 هشدار: داده آزمایشی است و زنده نیست - مبنای خرید/فروش قرار ندهید" };
    case "synthetic":
      return { cls: "demo", pill: "اعتماد: SYNTHETIC - شبیه‌سازی‌شده", icon: "🚨", banner: "🚨 هشدار: داده شبیه‌سازی‌شده است - مبنای خرید/فروش قرار ندهید" };
    case "stale":
      return { cls: "mixed", pill: "اعتماد: STALE - داده قدیمی", icon: "⚠️", banner: "⚠️ هشدار: داده قدیمی است و وضعیت زنده بازار را نشان نمی‌دهد" };
    case "unavailable":
      return { cls: "demo", pill: "اعتماد: UNAVAILABLE - داده ناموجود", icon: "⛔", banner: "⛔ داده قابل اتکا در دسترس نیست" };
    default:
      return { cls: "mixed", pill: "اعتماد: MIXED - ترکیبی/نیازمند احتیاط", icon: "⚠️", banner: "⚠️ توجه: داده ترکیبی یا کاملاً اعتبارسنجی‌نشده است" };
  }
}

export function renderTrustBanner(levelOrTrust, source) {
  const banner = document.getElementById("trustBanner");
  const pill = document.getElementById("trustPill");
  const textEl = document.getElementById("trustText");
  if (!banner || !pill || !textEl) return;

  const trust = normalizeTrust(levelOrTrust, source);
  const ui = trustPresentation(trust);
  const bannerText = document.getElementById("trustBannerText");
  const bannerIcon = document.getElementById("trustBannerIcon");

  pill.classList.remove("live", "mock");
  banner.classList.remove("hidden", "demo", "mixed", "live");

  pill.classList.add(ui.cls === "live" ? "live" : "mock");
  textEl.textContent = ui.pill;

  if (ui.hide) {
    banner.classList.add("live", "hidden");
  } else {
    banner.className = `trust-banner ${ui.cls}`;
    const details = trust.warning || ui.banner;
    const age = typeof trust.ageSec === "number" ? ` · سن داده: ${Math.round(trust.ageSec)} ثانیه` : "";
    if (bannerText) bannerText.textContent = `${details}${age} [source=${escapeHtml(trust.source)}]`;
    if (bannerIcon) bannerIcon.textContent = ui.icon;
  }
}
