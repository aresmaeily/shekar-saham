/**
 * format.js — قالب‌بندی فارسی (منبع واحد)
 * همه نمایش‌های عددی برنامه از اینجا می‌آیند؛ هیچ‌جا دیگر toLocaleString پراکنده نزنید.
 */

/** عدد با ارقام فارسی */
export function fmtNum(n, digits = 0) {
  if (n == null || Number.isNaN(+n)) return "—";
  return Number(n).toLocaleString("fa-IR", { maximumFractionDigits: digits });
}

/** پول فشرده (K/M/B/T) */
export function fmtMoney(v) {
  if (v == null || Number.isNaN(+v)) return "—";
  const a = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  if (a >= 1e12) return sign + (a / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return sign + (a / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return sign + (a / 1e6).toFixed(1) + "M";
  if (a >= 1e3) return sign + (a / 1e3).toFixed(1) + "K";
  return sign + String(Math.round(a));
}

/** کلاس رنگی بر اساس علامت (برای قیمت/درصد) */
export function pctClass(p) {
  if (p > 0) return "pct-up";
  if (p < 0) return "pct-down";
  return "";
}

/** کلاس امتیاز */
export function scoreClass(score, invert = false) {
  if (invert) {
    if (score >= 75) return "danger";
    if (score >= 60) return "mid";
    return "low";
  }
  if (score >= 80) return "high";
  if (score >= 65) return "mid";
  return "low";
}

/** کلاس گرید تابلو */
export function gradeClass(g) {
  const x = String(g || "C").toUpperCase();
  if (x.startsWith("A+")) return "ap";
  if (x.startsWith("A")) return "a";
  if (x.startsWith("B")) return "b";
  if (x.startsWith("C")) return "c";
  return "d";
}

/** escape HTML — امنیت XSS در همه رندرها */
export function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/** فرمت قیمت متناسب با بزرگی عدد (فارکس/طلا) */
export function fmtPrice(p) {
  if (p == null || Number.isNaN(+p)) return "—";
  const abs = Math.abs(p);
  let dec = 2;
  if (abs < 0.01) dec = 6;
  else if (abs < 0.1) dec = 5;
  else if (abs < 1) dec = 4;
  else if (abs < 10) dec = 3;
  else if (abs < 200) dec = 2;
  else dec = 1;
  return Number(p).toLocaleString("fa-IR", { maximumFractionDigits: dec });
}

/** تاریخ/زمان به فارسی */
export function faTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fa-IR");
  } catch {
    return "—";
  }
}
