// Service Worker v3.0.8 — هماهنگ با معماری جدید (WS-HARDEN-1/W3: مسیر legacy حذف شد؛ WS-10: چارت حرفه‌ای؛ MASTER-RADAR: آزمایشگاه استراتژی؛ MASTER-RADAR WAVE-2: مراکز بک‌تست/فوروارد تست/کیفیت داده؛ MASTER-RADAR WAVE-3: شبکه چندچارتی + پالت فرمان؛ WAVE-B: اندیکاتور کاربر UIDL-1؛ v3-0-10: رفع نیت جداسازی popup؛ v3-0-11: خروجی PDF گزارش‌ها (بک‌تست/بهینه‌ساز)؛ v3-0-12: تقویم‌های اعلامی بازار (DECLARED)؛ v3-0-13: نصب SW با cache:reload (دور زدن تازگی-اکتشافی HTTP)؛ v3-0-14: پنل حلقه‌های محصول WAVE-F؛ v3-0-15: پنل استودیو AI-2 (WAVE-O — مسیر تولید حاکمیت‌شده)؛ v3-0-16: همگام‌سازی بازه/کراس‌هیر بین‌پنجره‌ای گرید (WAVE-S2)؛ v3-0-17: تریگر UI walk-forward در مرکز فوروارد تست (WAVE-AB2)؛ v3-0-18: پنل هوش چندعاملی AI-MA (WAVE-AI — ارکستراسیون مشورتی حاکمیت‌شده))
// - HTML: network-first با fallback به کش (نسخه جدید همیشه می‌رسد)
// - استاتیک: stale-while-revalidate (سریع + به‌روز)
// - API: network-only — هرگز payload بازار/احراز را کش نکن (stale ≠ current؛ logout نباید replay شود)
const CACHE_NAME = "radar-bourse-static-v3-0-18";
const urlsToCache = [
  "/",
  "/static/css/app.css",
  "/static/css/chart_pro.css",
  "/static/js/main.js",
  "/static/js/sw-register.js",
  "/static/js/modules/render/chart_pro.js",
  "/static/js/modules/render/strategy_lab.js",
  "/static/js/modules/render/backtest_center.js",
  "/static/js/modules/render/forward_center.js",
  "/static/js/modules/render/data_quality_center.js",
  "/static/js/modules/render/chart_grid.js",
  "/static/js/modules/command_palette.js",
  "/static/js/modules/user_indicator.js",
  "/static/js/modules/render/user_indicator_ui.js",
  "/static/js/modules/render/product_loops_ui.js",
  "/static/js/modules/render/ai2_studio.js",
  "/static/js/modules/render/ai_ma_ui.js",
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
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache.map((u) => new Request(u, { cache: "reload" }))).catch(() => {}))
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
