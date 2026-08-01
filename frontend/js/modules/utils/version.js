export async function updateVersionFromApi() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const ver = data.version || "0.6.2";
    const lastUpdateEl = document.getElementById("lastUpdate");
    const footerVer = document.querySelector(".footer span:first-child");
    if (lastUpdateEl) {
      // Keep existing logic but show version
      const current = lastUpdateEl.textContent;
      if (!current.includes(ver)) {
        lastUpdateEl.textContent = current + ` · v${ver}`;
      }
    }
    if (footerVer) {
      footerVer.textContent = `شکار سهام v${ver} — فاز ۶.۲: امن، ماژولار، Production Hardened`;
    }
    // Update title ver badge
    const verBadge = document.querySelector(".ver");
    if (verBadge) verBadge.textContent = `v${ver}`;
  } catch {}
}
