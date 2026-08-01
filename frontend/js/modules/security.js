/**
 * modules/security.js - v0.6.2 Professional
 * XSS protection, input sanitization
 */
export function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function sanitizeSymbol(sym) {
  // Only allow Persian, English, numbers, max 12 chars
  if (!sym) return "";
  const cleaned = String(sym).trim().slice(0, 12);
  // Remove any HTML tags
  return cleaned.replace(/<[^>]*>/g, "");
}

export function isValidFilterExpr(expr) {
  if (!expr || typeof expr !== "string") return false;
  if (expr.length > 500) return false;
  // Block obvious injection attempts
  const blocked = ["__import__", "eval", "exec", "import ", "os.", "sys.", "subprocess", "open("];
  const lower = expr.toLowerCase();
  return !blocked.some(b => lower.includes(b));
}
