/**
 * workspace.js — WDA-1: ماندگاری فضای کاری «چارت حرفه‌ای» (رادار بورس)
 *
 * هدف: بازیابی وضعیت چارت حرفه‌ای پس از ری‌استارت برنامه — نماد فعال،
 * تایم‌فریم، اندیکاتورهای روشن، چیدمان پنل‌ها، وضعیت ابزار رسم، فهرست
 * هشدارهای قیمتی و نشانه‌های چیدمان پنجره — در یک کلید namespaced
 * (radar.workspace.v1) با نسخه‌بندی اسکیما.
 *
 * قراردادها (برای backend/tests/test_wda_workspace_persistence.py پین شده):
 * - پاکت ذخیره: { schema: 1, saved_at_iso, payload }
 * - اسکیمای ناشناخته/آینده → {ok:false, reason:"schema_unsupported"} و داده
 *   دست‌نخورده می‌ماند (بدون حذف، بدون قرنطینه).
 * - payload خراب (پارس ناموفق / ساختار نامعتبر) → نسخهٔ خام زیر کلید
 *   «radar.workspace.corrupted» به‌عنوان شواهد حفظ می‌شود، کلید اصلی به
 *   پیش‌فرض بازنشانی می‌شود و {ok:false, reason:"corrupted_quarantined"}
 *   برگردانده می‌شود — بازیابی همیشه به «چیزی معتبر» می‌رسد.
 * - اعتبارسنجی فیلدبه‌فیلد؛ فیلدهای ناشناخته دور ریخته می‌شوند؛ نوع‌های
 *   اشتباه یا تبدیل یا رد می‌شوند و در فهرست «issues» جمع می‌شوند.
 * - این ماژول هرگز به فراخواننده throw نمی‌کند.
 * - همهٔ دسترسی به storage پشت آداپتور تزریقی است (پیش‌فرض
 *   window.localStorage) — بدون هیچ تماس شبکه‌ای؛ کاملاً درون‌محصولی.
 */

// >>> WDA-1 PURE LOGIC BEGIN
/* همهٔ منطق این‌جا «خالص» است: هر تابع، storage را به‌صورت پارامتر صریح
   می‌گیرد و به window/document/DOM دسترسی ندارد. این بلوک مرز قرارداد
   ایستای تست‌هاست — ساختارش را بدون هماهنگی با تست‌ها تغییر ندهید. */

const WORKSPACE_SCHEMA_VERSION = 1;
const WORKSPACE_KEY = "radar.workspace.v1";
const WORKSPACE_CORRUPTED_KEY = "radar.workspace.corrupted";

/* همان شبکهٔ تایم‌فریم بک‌اند (app/api/chart_pro.py: ^(1m|5m|15m|1h|1D)$) */
const WORKSPACE_TIMEFRAMES = ["1m", "5m", "15m", "1h", "1D"];
/* کلیدهای اندیکاتور = data-ind های سگمنت cpIndSeg در index.html */
const WORKSPACE_INDICATORS = ["ma20", "ma50", "ema20", "bb", "rsi", "macd"];
/* کلیدهای ابزار رسم = data-draw های سگمنت cpDrawSeg */
const WORKSPACE_DRAW_TOOLS = ["trend", "hline", "fib", "delete"];
/* انواع رسم قابل ماندگاری (ابزار «حذف» وضعیت گذرا است و ذخیره نمی‌شود) */
const WORKSPACE_DRAWING_TYPES = ["trend", "hline", "fib"];

const WORKSPACE_MAX_SYMBOL_LEN = 64;
const WORKSPACE_MAX_DRAWINGS = 500;
const WORKSPACE_MAX_ALERTS = 100;
const WORKSPACE_OSC_HEIGHT_MIN = 80;
const WORKSPACE_OSC_HEIGHT_MAX = 400;
const WORKSPACE_WINDOW_DIM_MAX = 8192;

function _isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function _finiteNumber(v) {
  return typeof v === "number" && isFinite(v);
}

function _clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, v));
}

/** وضعیت پیش‌فرض — دقیقاً هم‌خوان با سازندهٔ ChartProChart */
function wsDefaultState() {
  return {
    symbol: "",
    timeframe: "1m",
    indicators: { ma20: true, ma50: true, ema20: false, bb: false, rsi: false, macd: false },
    pane_layout: { osc_visible: false, osc_height: 150 },
    drawing_tools: { active_tool: null, drawings: [] },
    alerts: [],
    window_layout: { width: 0, height: 0, maximized: false },
  };
}

/**
 * اعتبارسنجی فیلدبه‌فیلد payload. فیلدهای ناشناخته دور ریخته می‌شوند؛
 * نوع‌های اشتباه یا تبدیل می‌شوند یا رد و در «issues» ثبت می‌شوند.
 * خروجی: { payload, issues } — payload همیشه یک وضعیت کامل معتبر است.
 */
function wsValidatePayload(raw) {
  const def = wsDefaultState();
  const issues = [];
  const payload = def;

  if (!_isPlainObject(raw)) {
    issues.push("payload: not an object -> defaults");
    return { payload, issues };
  }

  /* فیلدهای ناشناختهٔ سطح بالا — دور ریختن با ثبت موضوع */
  const KNOWN_FIELDS = ["symbol", "timeframe", "indicators", "pane_layout", "drawing_tools", "alerts", "window_layout"];
  const unknownFields = Object.keys(raw).filter((k) => !KNOWN_FIELDS.includes(k));
  if (unknownFields.length) {
    issues.push("unknown fields dropped: " + unknownFields.join(","));
  }

  /* نماد */
  if (raw.symbol !== undefined) {
    if (typeof raw.symbol === "string") {
      payload.symbol = raw.symbol.trim().slice(0, WORKSPACE_MAX_SYMBOL_LEN);
      if (raw.symbol.trim().length > WORKSPACE_MAX_SYMBOL_LEN) {
        issues.push("symbol: truncated to " + WORKSPACE_MAX_SYMBOL_LEN);
      }
    } else {
      issues.push("symbol: wrong type refused -> default");
    }
  }

  /* تایم‌فریم — فقط مقادیر شبکهٔ بک‌اند */
  if (raw.timeframe !== undefined) {
    if (typeof raw.timeframe === "string" && WORKSPACE_TIMEFRAMES.includes(raw.timeframe)) {
      payload.timeframe = raw.timeframe;
    } else {
      issues.push("timeframe: refused -> default 1m");
    }
  }

  /* اندیکاتورها — فقط کلیدهای شناخته‌شده، مقدار بولی (تبدیل 0/1 مجاز) */
  if (raw.indicators !== undefined) {
    if (_isPlainObject(raw.indicators)) {
      const unknownInd = Object.keys(raw.indicators).filter((k) => !WORKSPACE_INDICATORS.includes(k));
      if (unknownInd.length) issues.push("indicators: unknown keys dropped: " + unknownInd.join(","));
      for (const k of WORKSPACE_INDICATORS) {
        if (raw.indicators[k] === undefined) continue;
        const v = raw.indicators[k];
        if (typeof v === "boolean") payload.indicators[k] = v;
        else if (v === 0 || v === 1) payload.indicators[k] = !!v;
        else issues.push("indicators." + k + ": wrong type refused -> default");
      }
    } else {
      issues.push("indicators: not an object refused -> defaults");
    }
  }

  /* چیدمان پنل‌ها */
  if (raw.pane_layout !== undefined) {
    if (_isPlainObject(raw.pane_layout)) {
      const pl = raw.pane_layout;
      if (pl.osc_visible === undefined) { /* پیش‌فرض می‌ماند */ }
      else if (typeof pl.osc_visible === "boolean") payload.pane_layout.osc_visible = pl.osc_visible;
      else if (pl.osc_visible === 0 || pl.osc_visible === 1) payload.pane_layout.osc_visible = !!pl.osc_visible;
      else issues.push("pane_layout.osc_visible: wrong type refused");
      if (pl.osc_height === undefined) { /* پیش‌فرض می‌ماند */ }
      else if (_finiteNumber(pl.osc_height)) {
        payload.pane_layout.osc_height = _clamp(Math.round(pl.osc_height), WORKSPACE_OSC_HEIGHT_MIN, WORKSPACE_OSC_HEIGHT_MAX);
        if (pl.osc_height < WORKSPACE_OSC_HEIGHT_MIN || pl.osc_height > WORKSPACE_OSC_HEIGHT_MAX) {
          issues.push("pane_layout.osc_height: clamped");
        }
      } else {
        issues.push("pane_layout.osc_height: wrong type refused");
      }
      const knownPane = Object.keys(raw.pane_layout).filter((k) => !["osc_visible", "osc_height"].includes(k));
      if (knownPane.length) issues.push("pane_layout: unknown keys dropped: " + knownPane.join(","));
    } else {
      issues.push("pane_layout: not an object refused -> defaults");
    }
  }

  /* ابزار رسم */
  if (raw.drawing_tools !== undefined) {
    if (_isPlainObject(raw.drawing_tools)) {
      const dt = raw.drawing_tools;
      if (dt.active_tool === undefined || dt.active_tool === null) { /* null مجاز */ }
      else if (typeof dt.active_tool === "string" && WORKSPACE_DRAW_TOOLS.includes(dt.active_tool)) {
        payload.drawing_tools.active_tool = dt.active_tool;
      } else {
        issues.push("drawing_tools.active_tool: refused -> null");
      }
      if (dt.drawings === undefined) { /* پیش‌فرض می‌ماند */ }
      else if (Array.isArray(dt.drawings)) {
        const kept = dt.drawings.filter(
          (d) => _isPlainObject(d) && typeof d.type === "string" && WORKSPACE_DRAWING_TYPES.includes(d.type)
        );
        if (kept.length < dt.drawings.length) {
          issues.push("drawing_tools.drawings: " + (dt.drawings.length - kept.length) + " invalid item(s) dropped");
        }
        if (kept.length > WORKSPACE_MAX_DRAWINGS) {
          kept.length = WORKSPACE_MAX_DRAWINGS;
          issues.push("drawing_tools.drawings: truncated to " + WORKSPACE_MAX_DRAWINGS);
        }
        payload.drawing_tools.drawings = kept;
      } else {
        issues.push("drawing_tools.drawings: not an array refused -> default");
      }
    } else {
      issues.push("drawing_tools: not an object refused -> defaults");
    }
  }

  /* هشدارهای قیمتی — فقط {price} با عدد متناهی مثبت */
  if (raw.alerts !== undefined) {
    if (Array.isArray(raw.alerts)) {
      const kept = [];
      for (const a of raw.alerts) {
        if (kept.length >= WORKSPACE_MAX_ALERTS) {
          issues.push("alerts: truncated to " + WORKSPACE_MAX_ALERTS);
          break;
        }
        if (_isPlainObject(a) && _finiteNumber(a.price) && a.price > 0) {
          kept.push({ price: a.price });
        } else {
          issues.push("alerts: one invalid item dropped");
        }
      }
      payload.alerts = kept;
    } else {
      issues.push("alerts: not an array refused -> default");
    }
  }

  /* نشانه‌های چیدمان پنجره — فقط hint؛ اعداد بیرون از بازه کم می‌شوند */
  if (raw.window_layout !== undefined) {
    if (_isPlainObject(raw.window_layout)) {
      const wl = raw.window_layout;
      for (const dim of ["width", "height"]) {
        if (wl[dim] === undefined) continue;
        if (_finiteNumber(wl[dim]) && wl[dim] >= 0) {
          payload.window_layout[dim] = Math.round(_clamp(wl[dim], 0, WORKSPACE_WINDOW_DIM_MAX));
        } else {
          issues.push("window_layout." + dim + ": wrong type refused");
        }
      }
      if (wl.maximized !== undefined) {
        if (typeof wl.maximized === "boolean") payload.window_layout.maximized = wl.maximized;
        else issues.push("window_layout.maximized: wrong type refused");
      }
    } else {
      issues.push("window_layout: not an object refused -> defaults");
    }
  }

  return { payload, issues };
}

/** پاکت نسخه‌دار برای ذخیره */
function wsWrapState(state, nowIso) {
  const validated = wsValidatePayload(state);
  return {
    envelope: {
      schema: WORKSPACE_SCHEMA_VERSION,
      saved_at_iso: typeof nowIso === "string" && nowIso ? nowIso : new Date().toISOString(),
      payload: validated.payload,
    },
    issues: validated.issues,
  };
}

/**
 * قرنطینهٔ payload خراب: نسخهٔ خام به‌عنوان شواهد حفظ می‌شود، کلید اصلی
 * بازنشانی می‌شود تا بازیابی بعدی همیشه به حالت معتبر برسد. هرگز throw نمی‌کند.
 */
function wsQuarantine(storage, raw, cause) {
  let evidenceWritten = false;
  try {
    storage.setItem(
      WORKSPACE_CORRUPTED_KEY,
      JSON.stringify({
        quarantined_at_iso: new Date().toISOString(),
        cause: String(cause || "unknown"),
        raw: String(raw).slice(0, 20000),
      })
    );
    evidenceWritten = true;
  } catch (err) { /* نوشتن شواهد بهترین‌تلاش است */ }
  try {
    storage.removeItem(WORKSPACE_KEY);
  } catch (err) { /* بازنشانی بهترین‌تلاش است */ }
  return {
    ok: false,
    reason: "corrupted_quarantined",
    cause: String(cause || "unknown"),
    evidence_written: evidenceWritten,
    payload: wsDefaultState(),
    issues: [],
  };
}

/** ذخیرهٔ وضعیت — هرگز throw نمی‌کند */
function wsSave(storage, state) {
  if (!storage || typeof storage.setItem !== "function") {
    return { ok: false, reason: "storage_unavailable", issues: [] };
  }
  try {
    const wrapped = wsWrapState(state);
    storage.setItem(WORKSPACE_KEY, JSON.stringify(wrapped.envelope));
    return { ok: true, issues: wrapped.issues };
  } catch (err) {
    return { ok: false, reason: "storage_write_failed", issues: [] };
  }
}

/** بارگذاری و اعتبارسنجی — هرگز throw نمی‌کند و همیشه payload معتبر می‌دهد */
function wsLoad(storage) {
  if (!storage || typeof storage.getItem !== "function") {
    return { ok: false, reason: "storage_unavailable", payload: wsDefaultState(), issues: [] };
  }
  let raw = null;
  try {
    raw = storage.getItem(WORKSPACE_KEY);
  } catch (err) {
    return { ok: false, reason: "storage_unavailable", payload: wsDefaultState(), issues: [] };
  }
  if (raw === null || raw === "") {
    /* هیچ فضای کاری ذخیره نشده — بازیابی به پیش‌فرض، بدون خطا */
    return { ok: true, restored: false, payload: wsDefaultState(), issues: ["empty_workspace"] };
  }

  let parsed = null;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    return wsQuarantine(storage, raw, "json_parse_failed");
  }
  if (!_isPlainObject(parsed)) {
    return wsQuarantine(storage, raw, "envelope_not_object");
  }

  /* اسکیمای ناشناخته/آینده: داده حفظ می‌شود — بدون قرنطینه و بدون حذف */
  const schema = parsed.schema;
  if (typeof schema !== "number" || !Number.isInteger(schema) || schema !== WORKSPACE_SCHEMA_VERSION) {
    return {
      ok: false,
      reason: "schema_unsupported",
      schema: schema === undefined ? null : schema,
      payload: wsDefaultState(),
      issues: [],
    };
  }

  if (!_isPlainObject(parsed.payload)) {
    return wsQuarantine(storage, raw, "payload_not_object");
  }

  const validated = wsValidatePayload(parsed.payload);
  return { ok: true, restored: true, payload: validated.payload, issues: validated.issues };
}

/** بازنشانی صریح (اقدام کاربر) — کلید اصلی حذف می‌شود؛ شواهد قرنطینه حفظ می‌ماند */
function wsReset(storage) {
  if (!storage || typeof storage.removeItem !== "function") {
    return { ok: false, reason: "storage_unavailable", payload: wsDefaultState() };
  }
  try {
    storage.removeItem(WORKSPACE_KEY);
  } catch (err) {
    return { ok: false, reason: "storage_write_failed", payload: wsDefaultState() };
  }
  return { ok: true, payload: wsDefaultState() };
}

/* رجیستری توابع خالص — نقطهٔ پین ایستای تست‌ها و نقطهٔ تزریق برای فراخوانندگان پیشرفته */
const __workspace_internal = {
  WORKSPACE_SCHEMA_VERSION,
  WORKSPACE_KEY,
  WORKSPACE_CORRUPTED_KEY,
  WORKSPACE_TIMEFRAMES,
  WORKSPACE_INDICATORS,
  WORKSPACE_DRAW_TOOLS,
  WORKSPACE_DRAWING_TYPES,
  isPlainObject: _isPlainObject,
  defaultState: wsDefaultState,
  validatePayload: wsValidatePayload,
  wrapState: wsWrapState,
  save: wsSave,
  load: wsLoad,
  quarantine: wsQuarantine,
  reset: wsReset,
};
// >>> WDA-1 PURE LOGIC END

/* آداپتور storage تزریقی — پیش‌فرض window.localStorage؛ در نبودِ آن null
   (هر مسیر عمومیِ زیر با storage=null به reason:"storage_unavailable"
   می‌رسد، نه exception). */
function defaultStorage() {
  try {
    if (typeof window !== "undefined" && window.localStorage) return window.localStorage;
  } catch (err) { /* در بافت‌های محدودشده localStorage ممکن است throw کند */ }
  return null;
}

/** ذخیرهٔ فضای کاری چارت حرفه‌ای (storage اختیاری برای تزریق) */
export function saveWorkspace(state, storage) {
  return __workspace_internal.save(storage || defaultStorage(), state);
}

/** بازیابی فضای کاری — همیشه payload معتبر می‌دهد؛ هرگز throw نمی‌کند */
export function loadWorkspace(storage) {
  return __workspace_internal.load(storage || defaultStorage());
}

/** بازنشانی فضای کاری به پیش‌فرض (storage اختیاری برای تزریق) */
export function resetWorkspace(storage) {
  return __workspace_internal.reset(storage || defaultStorage());
}

export { __workspace_internal };
export const WORKSPACE_STORAGE_KEY = WORKSPACE_KEY;
export const WORKSPACE_SCHEMA = WORKSPACE_SCHEMA_VERSION;
