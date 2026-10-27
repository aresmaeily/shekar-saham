export async function updateVersionFromApi() {
  // WS-HARDEN-1/W4: تک‌منبع حقیقت نسخه = settings.version بک‌اند (از طریق /api/health).
  // اگر API در دسترس نبود، DOM دست‌نخورده می‌ماند — هیچ fallback نسخه‌ی کد‌شده‌ای وجود ندارد.
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const ver = data.version;
    if (!ver) return;
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
      footerVer.textContent = `رادار بورس v${ver} — معماری Meta · WebSocket · حالت خصوصی · فارکس/طلا`;
    }
    // Update title ver badge
    const verBadge = document.querySelector(".ver");
    if (verBadge) verBadge.textContent = `v${ver}`;
  } catch {}
}
