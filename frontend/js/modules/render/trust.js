/**
 * render/trust.js - Trust banner rendering - P0-1 fix
 */
import { escapeHtml } from "../security.js";

export function renderTrustBanner(level, source) {
  const banner = document.getElementById("trustBanner");
  const pill = document.getElementById("trustPill");
  const textEl = document.getElementById("trustText");
  if (!banner || !pill || !textEl) return;
  
  const lv = String(level || "mixed").toLowerCase();
  const bannerText = document.getElementById("trustBannerText");
  const bannerIcon = document.getElementById("trustBannerIcon");
  
  pill.classList.remove("live", "mock");
  banner.classList.remove("hidden", "demo", "mixed", "live");
  
  if (lv === "live") {
    pill.classList.add("live");
    textEl.textContent = "اعتماد: LIVE - داده زنده";
    banner.classList.add("live", "hidden");
  } else if (lv === "synthetic") {
    pill.classList.add("mock");
    textEl.textContent = "اعتماد: DEMO/SYNTHETIC - آزمایشی";
    banner.className = "trust-banner demo";
    if (bannerText) bannerText.textContent = "🚨 هشدار: داده DEMO/SYNTHETIC است - تمام اعداد بنیادی و ریزمعامله ساختگی هستند - مبنای خرید/فروش قرار ندهید - فقط برای تست UI [source=" + escapeHtml(source || "mock") + "]";
    if (bannerIcon) bannerIcon.textContent = "🚨";
  } else {
    pill.classList.add("mock");
    textEl.textContent = "اعتماد: MIXED - ترکیبی";
    banner.className = "trust-banner mixed";
    if (bannerText) bannerText.textContent = "⚠️ توجه: داده MIXED است - بخشی synthetic - با احتیاط [source=" + escapeHtml(source || "mixed") + "]";
    if (bannerIcon) bannerIcon.textContent = "⚠️";
  }
}
