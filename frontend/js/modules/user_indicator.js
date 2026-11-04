/**
 * user_indicator.js — MASTER-RADAR WAVE-B (2026-11-04) / MR-B4-01
 * کلاینت حکمرانی‌شدهٔ «اندیکاتور کاربر (UIDL-1)» — موتور واقعی سمت سرور.
 *
 * قراردادهای اجباری این ماژول (الگوی chart_grid/command_palette):
 * - تمام HTTP فقط از core/api.js — هیچ fetch دستی، هیچ دامنهٔ دیگری.
 * - هیچ eval/Function/dynamic-import پویا — چیزی که از سرور می‌آید فقط داده است؛
 *   اجرای DSL فقط و فقط روی بک‌اند (تفسیر محدود RSL-1) انجام می‌شود.
 * - هیچ تایمر/polling — فقط تعامل صریح کاربر.
 * - هیچ برچسب اعتماد ساختگی — برچسب فقط از فیلدهای سرور.
 * - منطق خالص (بدون DOM/شبکه) در بخش «PURE LOGIC» برای تست ایستا پین شده.
 */
import { api, toast } from "../core/api.js";
import { esc, fmtNum } from "../core/format.js";

export const USER_IND_CHANNEL = "radar.userind.v1";
export const USER_IND_MAX_SOURCE = 8192;
export const UIDL_DOC_EXAMPLES = [
  {
    label: "باند SMA ±۲٪",
    source:
      "INDICATOR my_band\nINPUT len = 20\nPLOT basis = sma(close, len)\nPLOT upper = sma(close, len) * 1.02\nPLOT lower = sma(close, len) * 0.98",
  },
  {
    label: "مومنتوم ۱ کندلی",
    source: "INDICATOR momentum\nPLOT mom = close - ref(close, 1)",
  },
  {
    label: "نسبت به سقف ۳ کندل",
    source: "INDICATOR hi_ratio\nPLOT ratio = close / highest(close, 3)",
  },
];

/* >>> WAVE-B PURE LOGIC BEGIN — مرز پین ایستای تست‌ها (بدون DOM/شبکه) */

/** اعتبارسنجی سمت کلاینتِ متن منبع — فقط طول و نوع؛ «کامپایل» فقط سرور */
export function clientValidateSource(source) {
  if (typeof source !== "string" || !source.trim()) {
    return { ok: false, error: "متن برنامه خالی است" };
  }
  if (source.length > USER_IND_MAX_SOURCE) {
    return { ok: false, error: `متن برنامه بلندتر از ${USER_IND_MAX_SOURCE} نویسه است` };
  }
  return { ok: true };
}

/** سری رسم‌شدنی: فقط ناحیهٔ معتبر — برچسب گرم‌شدن از سرور (valid_from_index)
 *  می‌آید؛ هیچ مقدار ساختگی‌ای جای آن نمی‌نشیند. صفرهای میان‌سری واقعی
 *  حذف نمی‌شوند (حذف صفر = دستکاری داده)؛ مرز فقط برشی اعلان‌شدهٔ سرور است. */
export function plottableSeries(rows, validFromIndex) {
  const from = Math.max(0, Math.floor(Number(validFromIndex) || 0));
  const arr = Array.isArray(rows) ? rows : [];
  return arr
    .slice(from)
    .filter((r) => r && r.time != null && r.value != null && isFinite(+r.value))
    .map((r) => ({ time: r.time, value: Number(r.value) }));
}

/** ساخت پیام همگام‌سازی — fail-closed (هر فیلد نامعتبر → null) */
export function buildSyncMessage(msg) {
  if (!msg || typeof msg !== "object") return null;
  if (msg.type !== "params_changed") return null;
  const id = typeof msg.id === "string" && msg.id.length <= 96 ? msg.id : null;
  if (!id) return null;
  const params = msg.params && typeof msg.params === "object" ? msg.params : null;
  if (!params) return null;
  return { type: "params_changed", id, params };
}

/* <<< WAVE-B PURE LOGIC END */

export class UserIndicatorClient {
  constructor() {
    this.mounted = new Map(); // id -> {series[], chartRef, indicatorName}
    this._channel = null;
    try {
      if (typeof BroadcastChannel === "function") {
        this._channel = new BroadcastChannel(USER_IND_CHANNEL);
      }
    } catch (e) { /* محیط بدون BroadcastChannel — همگام‌سازی صادقانه غیرفعال */ }
  }

  async list() {
    return api("/api/v10/user-indicators");
  }

  async validate(source) {
    const v = clientValidateSource(source);
    if (!v.ok) throw new Error(v.error);
    return api("/api/v10/user-indicators/validate", {
      method: "POST",
      body: JSON.stringify({ source }),
    });
  }

  async install(source, { version = "1.0.0", name_fa = "", author = "operator" } = {}) {
    const v = clientValidateSource(source);
    if (!v.ok) throw new Error(v.error);
    return api("/api/v10/user-indicators", {
      method: "POST",
      body: JSON.stringify({ source, version, name_fa, author }),
    });
  }

  async detail(id) {
    return api(`/api/v10/user-indicators/${encodeURIComponent(id)}`);
  }

  async remove(id) {
    return api(`/api/v10/user-indicators/${encodeURIComponent(id)}`, { method: "DELETE" });
  }

  async setEnabled(id, enabled) {
    return api(`/api/v10/user-indicators/${encodeURIComponent(id)}/${enabled ? "enable" : "disable"}`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  }

  async exportPackage() {
    const res = await api("/api/v10/user-indicators/export");
    return res && res.package ? res.package : { package_version: "UIDL-PKG-1", indicators: [] };
  }

  async importPackage(doc) {
    return api("/api/v10/user-indicators/import", {
      method: "POST",
      body: JSON.stringify(doc),
    });
  }

  async compute(id, { symbol, timeframe, count = 300, params = {} } = {}) {
    const q = new URLSearchParams({
      symbol: String(symbol || "").slice(0, 64),
      timeframe: String(timeframe || "1m"),
      count: String(Math.max(50, Math.min(1000, Number(count) || 300))),
    });
    if (params && Object.keys(params).length) {
      q.set("params", JSON.stringify(params));
    }
    return api(`/api/v10/user-indicators/${encodeURIComponent(id)}/compute?${q.toString()}`);
  }

  /** انتشار تغییر پارامتر به پنجره‌های دیگر (بدون تایمر — فقط رویداد) */
  broadcastParams(id, params) {
    const msg = buildSyncMessage({ type: "params_changed", id, params });
    if (!msg || !this._channel) return false;
    try {
      this._channel.postMessage(msg);
      return true;
    } catch (e) {
      return false;
    }
  }

  onParamsChanged(handler) {
    if (!this._channel) return false;
    try {
      this._channel.onmessage = (ev) => {
        const msg = buildSyncMessage(ev && ev.data);
        if (msg) handler(msg);
      };
      return true;
    } catch (e) {
      return false;
    }
  }
}

export const userIndicatorClient = new UserIndicatorClient();
