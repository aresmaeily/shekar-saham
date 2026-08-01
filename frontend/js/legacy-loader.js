/* legacy-loader.js — حالت legacy برای عیب‌یابی؛ main.js را حذف و نسخه قدیمی را بارگذاری می‌کند */
(function () {
  if (!new URLSearchParams(location.search).has("legacy")) return;
  var main = document.querySelector('script[src="/static/js/main.js"]');
  if (main) main.remove();
  var m = document.createElement("script");
  m.type = "module";
  m.src = "/static/js/app.v062.js";
  document.body.appendChild(m);
  var s = document.createElement("script");
  s.src = "/static/js/legacy/app.js";
  document.body.appendChild(s);
})();
