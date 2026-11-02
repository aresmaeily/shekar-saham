// Service Worker v3.0.5 — هماهنگ با معماری جدید (WS-HARDEN-1/W3: مسیر legacy حذف شد؛ WS-10: چارت حرفه‌ای)
// - HTML: network-first با fallback به کش (نسخه جدید همیشه می‌رسد)
// - استاتیک: stale-while-revalidate (سریع + به‌روز)
// - API: network-only — هرگز payload بازار/احراز را کش نکن (stale ≠ current؛ logout نباید replay شود)
const CACHE_NAME = "radar-bourse-static-v3-0-5";
const urlsToCache = [
  "/",
  "/static/css/app.css",
  "/static/css/chart_pro.css",
  "/static/js/main.js",
  "/static/js/sw-register.js",
  "/static/js/modules/render/chart_pro.js",
  "/static/vendor/lightweight-charts.standalone.production.js",
  "/static/js/core/store.js",
  "/static/js/core/api.js",
  "/static/js/core/format.js",
  "/static/js/core/events.js",
  "/static/js/components/data-table.js",
  "/static/js/components/thermometer.js",
  "/static/favicon.svg",
  "/static/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET") return;

  // API → network-only. Do not cache /api/* (sensitive GET + stale market data).
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(req));
    return;
  }

  // HTML → network-first (نسخه جدید همیشه سرو شود)
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, clone));
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // استاتیک → stale-while-revalidate
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, clone));
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
