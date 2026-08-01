/**
 * auth.js — حالت خصوصی v3 (نشست کوکی HttpOnly)
 * - توکن در کوکی HttpOnly است؛ JS دیگر توکن را نمی‌بیند/نگهداری نمی‌کند (کاهش سطح XSS)
 * - صفحه قفل بر اساس GET /api/auth/status (logged_in از کوکی)
 * - ورود: POST /api/auth/login → کوکی ست می‌شود → auth:ok
 * - خروج: POST /api/auth/logout → ریلود
 */
import { events } from "../core/events.js";

function showLock() {
  const lock = document.getElementById("authLock");
  if (lock) lock.classList.remove("hidden");
}

function hideLock() {
  const lock = document.getElementById("authLock");
  if (lock) lock.classList.add("hidden");
}

function lockMsg(text, ok = false) {
  const el = document.getElementById("authMsg");
  if (!el) return;
  el.textContent = text || "";
  el.className = ok ? "pct-up" : "pct-down";
}

function updateLogoutBtn(show) {
  const logout = document.getElementById("btnLogout");
  if (logout) logout.style.display = show ? "" : "none";
}

async function doLogin(password) {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
      credentials: "same-origin",
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      lockMsg(data.detail || "خطا در ورود");
      return false;
    }
    lockMsg("");
    hideLock();
    updateLogoutBtn(true);
    events.emit("auth:ok", {});
    return true;
  } catch (e) {
    lockMsg("خطا در ارتباط با سرور");
    return false;
  }
}

async function logout() {
  try {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  } catch (e) { /* ignore */ }
  location.reload();
}

async function initAuth() {
  try {
    const res = await fetch("/api/auth/status", { credentials: "same-origin" }).then((r) => r.json());
    const required = !!(res && res.auth_required);
    if (!required) {
      updateLogoutBtn(false);
      return; // حالت عمومی
    }
    if (res.logged_in) {
      updateLogoutBtn(true);
      events.emit("auth:ok", {}); // اگر refresh اولیه قبل از وضعیت کوکی گیت شده بود، حالا آزاد کن
      return;
    }
    updateLogoutBtn(false);
    showLock();
  } catch (e) {
    // سرور در دسترس نیست — قفل نمایش داده نشود تا خطای اتصال طبیعی دیده شود
  }
}

function bindAuth() {
  const form = document.getElementById("authForm");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const input = document.getElementById("authPassword");
      const btn = document.getElementById("authBtn");
      if (input && btn) {
        btn.disabled = true;
        btn.textContent = "در حال بررسی…";
        doLogin(input.value).then(() => {
          btn.disabled = false;
          btn.textContent = "ورود";
          input.value = "";
        });
      }
    });
  }
  const logoutBtn = document.getElementById("btnLogout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", logout);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    bindAuth();
    initAuth();
  });
} else {
  bindAuth();
  initAuth();
}
