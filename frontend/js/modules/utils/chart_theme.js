/**
 * chart_theme.js - انتخاب رنگ چارت بر اساس تم صفحه (تیره/روشن)
 * چارت‌های lightweight-charts باید با تم هماهنگ شوند (مثل تابلوخوانی)
 */
export function isLightTheme() {
  try {
    return document.documentElement.dataset.theme === "light";
  } catch (e) {
    return false;
  }
}

export function chartPalette() {
  return isLightTheme()
    ? {
        bg: "#ffffff",
        text: "#334155",
        grid: "rgba(37, 99, 235, 0.08)",
        border: "rgba(37, 99, 235, 0.18)",
        up: "#16a34a",
        down: "#dc2626",
        volUp: "rgba(22,163,74,0.45)",
        volDn: "rgba(220,38,38,0.45)",
        axis: "rgba(37, 99, 235, 0.18)",
      }
    : {
        bg: "#0b1220",
        text: "#9fb0c7",
        grid: "rgba(148,163,184,0.08)",
        border: "rgba(148,163,184,0.15)",
        up: "#34d399",
        down: "#fb7185",
        volUp: "rgba(52,211,153,0.4)",
        volDn: "rgba(251,113,133,0.4)",
        axis: "rgba(148,163,184,0.15)",
      };
}
