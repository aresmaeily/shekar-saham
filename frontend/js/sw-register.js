/* sw-register.js — ثبت Service Worker (نسخه v3) */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker
      .register("/static/sw.js")
      .catch(function (e) { console.warn("SW registration failed", e); });
  });
}
