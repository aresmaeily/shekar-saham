/**
 * timezone.js - v0.6.2 - P2-8 Fix: Asia/Tehran handling
 */

export const TEHRAN_TZ = "Asia/Tehran";

export function toTehranTime(utcIso) {
  try {
    const date = new Date(utcIso);
    return new Intl.DateTimeFormat("fa-IR", {
      timeZone: TEHRAN_TZ,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    }).format(date);
  } catch {
    return new Date(utcIso).toLocaleString("fa-IR");
  }
}

export function formatRelativeTehran(isoString) {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);
    if (diffSec < 60) return "همین الان";
    if (diffSec < 3600) return `${Math.floor(diffSec/60)} دقیقه پیش`;
    if (diffSec < 86400) return `${Math.floor(diffSec/3600)} ساعت پیش`;
    return toTehranTime(isoString);
  } catch {
    return "—";
  }
}
