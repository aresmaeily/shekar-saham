/**
 * app.v062.js - v0.6.2 Professional Modular Entry - P2-1 Fix
 * Split god file into modules: api, security, state, render/trust, utils
 */
import { Api } from "./modules/api.js";
import { escapeHtml } from "./modules/security.js";
import { store } from "./modules/state.js";
import { renderTrustBanner } from "./modules/render/trust.js";
import { toTehranTime } from "./modules/utils/timezone.js";
import { updateVersionFromApi } from "./modules/utils/version.js";
import "./modules/forex.js";
import "./modules/menu_customizer.js";
import "./modules/theme.js";
import "./modules/auth.js";
import "./modules/render/watchlist_excellent.js";
import { renderDataQuality, renderAnomalies, renderRisk } from "./modules/render/excellent.js";

console.log("%cShekar Saham v0.6.2 Professional Edition - Modular", "color:#34d399;font-weight:bold");

async function init() {
  try {
    const health = await Api.health();
    console.log("Health:", health, "Trust:", health.trust_level, "Coverage:", health.flow_meta);
    renderTrustBanner(health.trust_level, health.source);
    store.set({ trustLevel: health.trust_level });
    await updateVersionFromApi();

    // رندر بخش‌های تب «عالی» (کیفیت داده / آنومالی / ریسک)
    try {
      renderDataQuality();
      renderAnomalies();
      renderRisk();
    } catch (e) {
      console.error("Excellent sections failed:", e);
    }
    
    // Update lastUpdate with Tehran time
    const lastUpdateEl = document.getElementById("lastUpdate");
    if (lastUpdateEl && health.store) {
      lastUpdateEl.title = `Tehran time: ${toTehranTime(new Date().toISOString())}`;
    }
  } catch (e) {
    console.error("Modular init failed:", e);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

window.ShekarModular = { Api, escapeHtml, store, renderTrustBanner, toTehranTime };
