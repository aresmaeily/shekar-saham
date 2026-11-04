/**
 * command_palette.js — MASTER-RADAR WAVE-3 (2026-11-04) / MR-H-02: پالت فرمان
 *
 * - بازشدن: Ctrl+K / Cmd+K (یک شنونده keydown سند — passive:false و
 *   preventDefault فقط وقتی پالت خودش کلید را مصرف می‌کند) و با دکمه
 *   #paletteBtn اگر در DOM باشد (بایند تدافعی — نبودش خطا نیست).
 * - بسته‌شدن: Esc / کلیک روی پس‌زمینه / اجرای هر فرمان.
 * - فهرست فرمان‌ها در «لحظه بازشدن» از خود DOM ساخته می‌شود — هیچ فهرست
 *   هاردکدی از تب‌ها وجود ندارد:
 *     (۱) همه دکمه‌های tab. با data-tab → «رفتن به <متن دکمه>»
 *     (۲) انواع نمودار [data-ctype] داخل #cpTypeSeg (اگر باشد) → کلیک واقعی
 *     (۳) سرعت‌های رپلای #rpSpeeds button[data-sp] (اگر باشند) → کلیک واقعی
 *     (۴) اکشن‌های گرید فقط اگر window.chartGrid زنده باشد (چیدمان + سه toggle)
 *   تب «مرکز کیفیت داده» هم از همین شمارش (۱) می‌آید — مسیر جداگانه‌ای لازم
 *   نبود. هیچ فرمانی خودکار اجرا نمی‌شود؛ فقط با Enter/کلیک صریح کاربر.
 * - جستجو: زیررشته‌ای غیرحساس به بزرگی/کوچکی روی برچسب فارسی؛ ↑/↓ حرکت،
 *   Enter اجرا، Esc بستن؛ مورد انتخابی scrollIntoView می‌شود؛ ARIA:
 *   role="listbox"/"option" + aria-activedescendant + aria-selected.
 * - اخیرها: ۵ شناسه آخر زیر radar.palette.recent.v1 (فقط شناسه) — با جستجوی
 *   خالی در بالای فهرست شناور می‌شوند.
 * - امنیت: هیچ ارزیابی کد پویا و هیچ کانال شبکه‌ای مستقیم — این ماژول اصلاً
 *   درخواست شبکه‌ای ندارد (حتی api() هم صدا نمی‌زند؛ همه رجیستری از DOM زنده است).
 *   هیچ ساخت HTML از رشته — همه متن‌های پویا فقط با textContent روی گره‌های
 *   ساخته‌شده با createElement.
 * - DOM: اگر #paletteRoot باشد داخل آن، وگرنه روی document.body — تدافعی؛
 *   سبک حداقلی یک‌بار با شناسه پایدار تزریق می‌شود (فایل CSS جدید ممنوع) و
 *   کلاس‌های موجود app.css (modal/modal-card/text-input/muted) بازاستفاده
 *   می‌شوند.
 */

const PALETTE_STYLE_ID = "radar-palette-style";
const PALETTE_OVERLAY_ID = "radarPaletteOverlay";
const PALETTE_LIST_ID = "radarPaletteList";
const PALETTE_RECENT_KEY = "radar.palette.recent.v1";
const PALETTE_RECENT_MAX = 5;

/* وضعیت ماژول — یک پالت سراسری */
let overlay = null;
let inputEl = null;
let listEl = null;
let actions = [];
let filtered = [];
let selected = 0;
let lastFocus = null;
let recentIds = loadRecent();

/* ---------------- اخیرها (localStorage fail-closed — هرگز throw نمی‌کند) ---------------- */

function loadRecent() {
  try {
    const raw = localStorage.getItem(PALETTE_RECENT_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr)
      ? arr.filter((x) => typeof x === "string" && x).slice(0, PALETTE_RECENT_MAX)
      : [];
  } catch (e) {
    return [];
  }
}

function pushRecent(id) {
  recentIds = [id, ...recentIds.filter((x) => x !== id)].slice(0, PALETTE_RECENT_MAX);
  try {
    localStorage.setItem(PALETTE_RECENT_KEY, JSON.stringify(recentIds));
  } catch (e) { /* نوشتن حیاتی نیست */ }
}

/* ---------------- سبک حداقلی (یک‌بار، شناسه پایدار) ---------------- */

function injectStyle() {
  if (document.getElementById(PALETTE_STYLE_ID)) return;
  const st = document.createElement("style");
  st.id = PALETTE_STYLE_ID;
  /* فقط چیدمان پالت — رنگ/فونت از متغیرها و کلاس‌های app.css می‌آید */
  st.textContent = [
    `#${PALETTE_OVERLAY_ID} { z-index: 80; }`,
    `#${PALETTE_OVERLAY_ID} .radar-palette-card { width: min(560px, 100%); max-height: 70vh; display: flex; flex-direction: column; gap: .5rem; }`,
    `.radar-palette-list { overflow: auto; display: flex; flex-direction: column; gap: 2px; min-height: 120px; }`,
    `.radar-palette-opt { padding: .45rem .6rem; border-radius: 10px; cursor: pointer; border: 1px solid transparent; }`,
    `.radar-palette-opt[aria-selected="true"] { background: var(--surface2, rgba(148,163,184,.12)); border-color: var(--primary, #3b82f6); }`,
    `.radar-palette-hint { color: var(--muted, #94a3b8); font-size: .72rem; margin-top: .3rem; }`,
  ].join("\n");
  document.head.appendChild(st);
}

/* ---------------- رجیستری فرمان‌ها (ساخت در لحظه بازشدن، از خود DOM) ---------------- */

/** یک اکشن: {id, label_fa, hint_fa?, run} — run فقط با Enter/کلیک صریح اجرا می‌شود */
function buildActions() {
  const acts = [];

  /* (۱) همه تب‌ها — عنوان = متن خود دکمه؛ هیچ فهرست هاردکدی از تب‌ها نیست.
     «مرکز کیفیت داده» و بقیه هم از همین شمارش می‌آیند. */
  document.querySelectorAll(".tab[data-tab]").forEach((btn) => {
    const title = String(btn.textContent || "").trim();
    if (!title) return;
    acts.push({
      id: "tab:" + btn.dataset.tab,
      label_fa: "رفتن به " + title,
      run: () => btn.click(),
    });
  });

  /* (۲) انواع نمودار چارت حرفه‌ای — اگر سگمنت در DOM باشد؛ کلیک واقعی دکمه */
  document.querySelectorAll("#cpTypeSeg button[data-ctype]").forEach((btn) => {
    const t = String(btn.textContent || "").trim();
    if (!t) return;
    acts.push({
      id: "ctype:" + btn.dataset.ctype,
      label_fa: "نوع نمودار: " + t,
      run: () => btn.click(),
    });
  });

  /* (۳) سرعت‌های رپلای — همان دکمه‌های data-sp داخل #rpSpeeds (اگر باشند) */
  document.querySelectorAll("#rpSpeeds button[data-sp]").forEach((btn) => {
    const t = String(btn.textContent || "").trim();
    if (!t) return;
    acts.push({
      id: "replay-speed:" + btn.dataset.sp,
      label_fa: "سرعت رپلای: " + t,
      run: () => btn.click(),
    });
  });

  /* (۴) اکشن‌های گرید — فقط اگر window.chartGrid زنده باشد؛ هیچ API جدیدی صدا
     زده نمی‌شود، فقط متدهای عمومی خود ماژول گرید (setLayout/toggleSync) */
  const grid = (typeof window !== "undefined") ? window.chartGrid : null;
  if (grid && typeof grid.setLayout === "function") {
    const layoutFa = { 1: "۱", 2: "۲", 4: "۴" };
    for (const n of [1, 2, 4]) {
      acts.push({
        id: "grid-layout:" + n,
        label_fa: `چیدمان گرید: ${layoutFa[n]} پنل`,
        run: () => grid.setLayout(n),
      });
    }
    if (grid.state && grid.state.sync) {
      const syncFa = {
        range: "همگام‌سازی بازه",
        crosshair: "همگام‌سازی کراس‌هیر",
        symbol_follow: "همگام‌سازی نماد",
      };
      Object.keys(syncFa).forEach((k) => {
        acts.push({
          id: "grid-sync:" + k,
          label_fa: "گرید — " + syncFa[k],
          run: () => grid.toggleSync(k),
        });
      });
    }
  }

  /* (۵) میان‌برهای مفید محصول — فقط پیمایش تب از طریق خود دکمه‌های tab؛
     هر اقدامی که API جدید لازم داشت عمداً حذف شده است. */

  return acts;
}

/** زیررشته‌ای غیرحساس به بزرگی/کوچکی روی برچسب؛ با جستجوی خالی اخیرها بالا */
function computeFiltered(query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) {
    const seen = new Set();
    const head = [];
    for (const id of recentIds) {
      const a = actions.find((x) => x.id === id);
      if (a && !seen.has(a.id)) {
        head.push(a);
        seen.add(a.id);
      }
    }
    const rest = actions.filter((a) => !seen.has(a.id));
    return [...head, ...rest];
  }
  return actions.filter((a) => String(a.label_fa || "").toLowerCase().includes(q));
}

/* ---------------- رندر فهرست — همه متن‌های پویا فقط با textContent ---------------- */

function renderList() {
  if (!listEl) return;
  listEl.textContent = "";
  filtered = computeFiltered(inputEl ? inputEl.value : "");
  if (selected >= filtered.length) selected = Math.max(0, filtered.length - 1);
  filtered.forEach((a, i) => {
    const opt = document.createElement("div");
    opt.className = "radar-palette-opt";
    opt.id = `${PALETTE_LIST_ID}-opt-${i}`;
    opt.setAttribute("role", "option");
    opt.setAttribute("aria-selected", i === selected ? "true" : "false");
    opt.dataset.paletteIndex = String(i);
    const label = document.createElement("div");
    label.textContent = a.label_fa; // متن برچسب عین خود رشته است — بدون ساخت HTML از رشته
    opt.appendChild(label);
    if (a.hint_fa) {
      const hint = document.createElement("div");
      hint.className = "radar-palette-hint";
      hint.textContent = a.hint_fa;
      opt.appendChild(hint);
    }
    opt.addEventListener("click", () => runAction(i));
    listEl.appendChild(opt);
  });
  updateActiveDescendant();
  scrollSelectedIntoView();
}

function updateActiveDescendant() {
  if (!inputEl || !listEl) return;
  const current = filtered[selected];
  if (current) {
    inputEl.setAttribute("aria-activedescendant", `${PALETTE_LIST_ID}-opt-${selected}`);
  } else {
    inputEl.removeAttribute("aria-activedescendant");
  }
}

function scrollSelectedIntoView() {
  const el = listEl ? listEl.querySelector(`[data-palette-index="${selected}"]`) : null;
  if (el && typeof el.scrollIntoView === "function") {
    try { el.scrollIntoView({ block: "nearest" }); } catch (e) { /* ignore */ }
  }
}

function move(delta) {
  if (!filtered.length) return;
  selected = (selected + delta + filtered.length) % filtered.length;
  renderList();
}

function runAction(i) {
  const a = filtered[i];
  if (!a || typeof a.run !== "function") return;
  pushRecent(a.id);
  close();
  /* اجرا بعد از بستن — کلیک تب روی DOM قابل‌مشاهده اعمال می‌شود */
  try { a.run(); } catch (e) { /* فرمان خراب هرگز پالت را نمی‌شکند */ }
}

function runSelected() {
  runAction(selected);
}

/* ---------------- باز/بسته ---------------- */

function ensureDom() {
  if (overlay) return;
  injectStyle();
  overlay = document.createElement("div");
  overlay.id = PALETTE_OVERLAY_ID;
  /* کلاس modal/app.css: پس‌زمینه تار + center؛ hidden برای باز/بسته */
  overlay.className = "modal hidden";

  const panel = document.createElement("div");
  panel.className = "modal-card radar-palette-card";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "true");
  panel.setAttribute("aria-label", "پالت فرمان");
  panel.setAttribute("dir", "rtl");

  inputEl = document.createElement("input");
  inputEl.type = "text";
  inputEl.className = "text-input";
  inputEl.placeholder = "جستجوی فرمان… (↑/↓ حرکت، Enter اجرا، Esc بستن)";
  inputEl.setAttribute("aria-label", "جستجوی فرمان‌ها");
  inputEl.setAttribute("role", "combobox");
  inputEl.setAttribute("aria-expanded", "true");
  inputEl.setAttribute("aria-controls", PALETTE_LIST_ID);
  inputEl.setAttribute("autocomplete", "off");
  inputEl.addEventListener("input", () => {
    selected = 0;
    renderList();
  });

  listEl = document.createElement("div");
  listEl.className = "radar-palette-list";
  listEl.id = PALETTE_LIST_ID;
  listEl.setAttribute("role", "listbox");
  listEl.setAttribute("aria-label", "فرمان‌ها");

  const hint = document.createElement("div");
  hint.className = "radar-palette-hint muted";
  hint.textContent = "فرمان‌ها از همین صفحه ساخته می‌شوند — هیچ فرمانی خودکار اجرا نمی‌شود";

  panel.appendChild(inputEl);
  panel.appendChild(listEl);
  panel.appendChild(hint);
  overlay.appendChild(panel);

  /* کلیک روی پس‌زمینه (نه خود کارت) → بستن */
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  /* تدافعی: #paletteRoot اگر باشد داخل آن، وگرنه روی body (کار پیش از ادغام) */
  const host = document.getElementById("paletteRoot") || document.body;
  host.appendChild(overlay);
}

function open() {
  ensureDom();
  actions = buildActions(); // رجیستری همیشه از DOM زنده در لحظه بازشدن ساخته می‌شود
  inputEl.value = "";
  selected = 0;
  renderList();
  overlay.classList.remove("hidden");
  lastFocus = document.activeElement;
  try { inputEl.focus(); } catch (e) { /* ignore */ }
}

function close() {
  if (!overlay) return;
  overlay.classList.add("hidden");
  if (lastFocus && typeof lastFocus.focus === "function") {
    try { lastFocus.focus(); } catch (e) { /* ignore */ }
  }
}

function isOpen() {
  return !!(overlay && !overlay.classList.contains("hidden"));
}

function toggle() {
  if (isOpen()) close();
  else open();
}

/* ---------------- بایند سراسری ---------------- */

/* یک شنونده keydown برای کل سند — preventDefault فقط وقتی پالت کلید را مصرف
   می‌کند (باز/بسته‌کردن با Ctrl+K یا ناوبری وقتی پالت باز است) */
function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
    e.preventDefault();
    toggle();
    return;
  }
  if (!isOpen()) return;
  if (e.key === "Escape") {
    e.preventDefault();
    close();
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    move(1);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    move(-1);
  } else if (e.key === "Enter") {
    e.preventDefault();
    runSelected();
  }
}

function bindPaletteBtn() {
  const btn = document.getElementById("paletteBtn");
  if (!btn) return false;
  btn.addEventListener("click", () => toggle());
  return true;
}

/* دکمه هدر ممکن است بعداً توسط مرحله ادغام اضافه شود — ناظر DOM یک‌بار تلاش
   می‌کند و بعد از بایند موفق قطع می‌شود (ناظر DOM است، نه حلقه پس‌زمینه) */
function observePaletteBtn() {
  if (typeof MutationObserver === "undefined") return;
  const obs = new MutationObserver(() => {
    if (bindPaletteBtn()) obs.disconnect();
  });
  obs.observe(document.body, { childList: true, subtree: true });
}

if (typeof document !== "undefined") {
  document.addEventListener("keydown", onKeydown, { passive: false });
  const boot = () => {
    if (!bindPaletteBtn()) observePaletteBtn();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
}
