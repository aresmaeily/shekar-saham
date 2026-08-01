/**
 * theme.js - تغییر تم صفحه (تیره / روشن) v1.3
 * - ذخیره انتخاب کاربر در localStorage
 * - دکمه 🌓 در topbar برای چرخش تم‌ها
 */
const THEMES = ["light", "dark"];
// پیش‌فرض: روشن (سبک تابلوخوانی) — کاربر می‌تواند تیره کند
const DEFAULT_THEME = "light";

function applyTheme(theme) {
  const el = document.documentElement;
  if (!el) return;
  el.dataset.theme = theme;
  try {
    localStorage.setItem("shekar_theme", theme);
  } catch (e) {}
  const btn = document.getElementById("btnTheme");
  if (btn) {
    btn.textContent = theme === "light" ? "🌙" : "☀️";
    btn.title = theme === "light" ? "حالت تیره" : "حالت روشن";
  }
}

function currentTheme() {
  const saved = (() => {
    try {
      return localStorage.getItem("shekar_theme");
    } catch (e) {
      return null;
    }
  })();
  return saved && THEMES.includes(saved) ? saved : DEFAULT_THEME;
}

function cycleTheme() {
  const cur = document.documentElement.dataset.theme || currentTheme();
  const next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
  applyTheme(next);
}

function bindTheme() {
  // اعمال تم ذخیره‌شده قبل از رندر
  applyTheme(currentTheme());
  const btn = document.getElementById("btnTheme");
  if (btn) btn.addEventListener("click", cycleTheme);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindTheme);
} else {
  bindTheme();
}
