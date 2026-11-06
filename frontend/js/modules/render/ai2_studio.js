/**
 * render/ai2_studio.js — MASTER-RADAR WAVE-O (2026-11-06): استودیو AI-2
 *
 * افزودنی (additive-only): تب جدید «استودیو AI-2» — سطح UX برای خط لولهٔ
 * تولید حاکمیت‌شدهٔ AI-2 از مسیر /api/v10/ai2/* (WAVE-K/L):
 *   GET  /posture                    — وضعیت صادقانهٔ گیت‌ها (فقط-خواندنی)
 *   POST /generate                   — پرسش → شفاف‌سازی → spec تایپ‌شده → RSL-1
 *   GET  /candidates[/id]            — فهرست نسخه‌دار نامزدها + حکم دستکاری
 *   POST /candidates/{id}/approve    — تأیید انسانی (تأییدکنندهٔ نام‌دار)
 *   POST /candidates/{id}/promote    — ارتقا (فقط کاغذی؛ هیچ‌گاه لایو)
 *   GET  /runs                       — دفتر کل اجراها (فقط-الحاقی)
 *
 * قرارداد صداقت (هم‌الگو با product_loops_ui.js و strategy_lab.js):
 * - همه HTTP از core/api.js (api()) می‌گذرد — هیچ واکشی مستقیمی مجاز نیست.
 * - هیچ اجرای پویای کد مجاز نیست — فقط innerHTML از متن فرارکننده‌شده (esc).
 * - هیچ برچسبی سمت کلاینت ارتقا یا جعل نمی‌شود: وضعیت/حکم/اعتماد فقط از
 *   فیلدهای سرور خوانده می‌شود و مقدار ناشناخته عیناً (خام) رندر می‌شود.
 * - «AI2_ENABLED=0» (پیش‌فرض مخزن) یعنی هر generate نتیجهٔ صادقانهٔ
 *   gated_not_executed می‌گیرد — همین عیناً نمایش داده می‌شود؛ هیچ پنهان‌سازی
 *   یا دورزدن سمت کلاینت وجود ندارد.
 * - تأیید/ارتقا فقط با نام تأییدکنندهٔ انسانی (حداقل ۴ کاراکتر) انجام می‌شود؛
 *   مدل هیچ اختیاری روی تأیید/ارتقا ندارد (پیام صادقانهٔ سرور نمایش داده می‌شود).
 * - هیچ زمان‌بندی/polling/درخواست خودکاری وجود ندارد؛ هر فراخوان با کنش صریح
 *   کاربر انجام می‌شود.
 * - بدون خروج به بیرون (egress): هیچ آدرس بیرونی، WebSocket، ارسال داده به
 *   هیچ مقصد دیگری — فقط همان مبدأ خود برنامه.
 */
import { api, toast } from "../../core/api.js";
import { esc } from "../../core/format.js";

let bound = false;
let loaded = false;

function $(id) {
  return document.getElementById(id);
}

function on(id, fn) {
  const el = $(id);
  if (el) el.addEventListener("click", fn);
}

function setOut(id, html) {
  const el = $(id);
  if (el) el.innerHTML = html;
}

function failText(err) {
  const d = err && err.detail ? err.detail : err;
  if (d && typeof d === "object") {
    const fa = d.message_fa || d.reason || d.message_en || d.error || "";
    return `${esc(String(d.error || "خطا"))} — ${esc(String(fa))}`;
  }
  // api() throws Error(msg) where msg may be the server's detail payload
  const msg = (err && err.message) || "";
  let inner = msg;
  try {
    const parsed = JSON.parse(msg);
    if (parsed && typeof parsed === "object") {
      inner = parsed.message_fa || parsed.reason || parsed.message_en || parsed.error || msg;
    }
  } catch {
    /* not JSON — use the raw message */
  }
  return esc(String(inner || err || "خطای ناشناخته"));
}

async function call(path, opts) {
  try {
    return await api(path, opts);
  } catch (err) {
    throw err;
  }
}

const TRUST_STATE_LABELS = {
  synthetic: "SYNTHETIC — شبیه‌سازی‌شده",
  mock: "MOCK — داده آزمایشی",
  stale: "STALE — داده قدیمی",
  unavailable: "UNAVAILABLE — داده ناموجود",
  mixed: "MIXED — ترکیبی/تأییدنشده",
};

function trustText(v) {
  const s = String(v || "").toLowerCase();
  return TRUST_STATE_LABELS[s] || `اعتماد: ${esc(String(v || "—"))}`;
}

// برچسب‌های وضعیت — فقط نگاشت نمایشیِ مقادیر سرور؛ مقدار ناشناخته عیناً رندر می‌شود.
const OUTCOME_STATUS_LABELS = {
  gated_not_executed: "اجرا نشد — گیت بسته",
  needs_clarification: "نیاز به شفاف‌سازی",
  refused: "رد شد",
  failed_provider: "شکست فراهم‌کننده",
  failed_schema: "شکست اسکیما",
  executed: "اجرا شد",
  executed_shadow: "اجرا شد (سایه — ترابری آزمایشی)",
};

const CANDIDATE_STATUS_LABELS = {
  DRAFT: "پیش‌نویس",
  APPROVED: "تأییدشده (انسانی)",
  PROMOTED: "ارتقایافته — فقط کاغذی",
};

function label(map, v) {
  const raw = String(v ?? "");
  return map[raw] ? map[raw] : esc(raw || "—");
}

function badge(text, kind) {
  const cls = kind === "ok" ? "cp-badge" : kind === "warn" ? "cp-badge warn" : "cp-badge";
  return `<span class="${cls}">${esc(text)}</span>`;
}

function kvRows(entries) {
  return entries
    .filter(([, v]) => v !== undefined && v !== null && String(v) !== "")
    .map(
      ([k, v]) =>
        `<tr><td>${esc(String(k))}</td><td>${typeof v === "object" ? esc(JSON.stringify(v)) : esc(String(v))}</td></tr>`
    )
    .join("");
}

function kvTable(entries) {
  const rows = kvRows(entries);
  if (!rows) return '<p class="muted">—</p>';
  return `<table class="data-table"><thead><tr><th>فیلد</th><th>مقدار</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function honestyList(h) {
  if (!h || typeof h !== "object") return '<p class="muted">—</p>';
  const rows = Object.entries(h)
    .map(([k, v]) => `<tr><td>${esc(String(k))}</td><td>${esc(String(v))}</td></tr>`)
    .join("");
  return `<table class="data-table"><thead><tr><th>بند صداقت</th><th>اعلام سرور</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// ---------------------------------------------------------------------------
// posture
// ---------------------------------------------------------------------------
async function loadPosture() {
  setOut("ai2PostureOut", '<p class="muted">در حال خواندن وضعیت…</p>');
  try {
    const j = await call("/api/v10/ai2/posture", { method: "GET" });
    const enabled = Boolean(j.ai2_enabled);
    const badgeKind = enabled ? "warn" : "ok";
    const gate = enabled
      ? "گیت AI-2 باز است (فقط محیط ایزوله dev/paper)"
      : "گیت AI-2 بسته است — هیچ تولیدی اجرا نمی‌شود";
    setOut(
      "ai2PostureOut",
      `<p>${badge(gate, badgeKind)} ${badge(`حالت اجرا: ${String(j.execution_mode || "—")}`, "warn")}</p>
      ${kvTable([
        ["service_version", j.service_version],
        ["ai2_enabled", j.ai2_enabled],
        ["generation_allowed", j.generation_allowed],
        ["production_provider_generation_permitted", j.production_provider_generation_permitted],
        ["provider_mode", j.provider_mode],
        ["provider_label", j.provider_label],
        ["test_transport_required_for_remote_provider", j.test_transport_required_for_remote_provider],
        ["execution_mode", j.execution_mode],
        ["candidates_in_memory", j.candidates_in_memory],
        ["ledger_records", j.ledger_records],
        ["registry_persistence", j.registry_persistence],
        ["promotion_authority", j.promotion_authority],
        ["egress", j.egress],
      ])}
      <h4>پاکت صداقت سرور (عیناً)</h4>
      ${honestyList(j.honesty)}`
    );
  } catch (err) {
    setOut("ai2PostureOut", `<p class="warn">${failText(err)}</p>`);
  }
}

// ---------------------------------------------------------------------------
// generate
// ---------------------------------------------------------------------------
function parseClarifications(raw) {
  // یک key=value در هر خط — حداکثر ۸ مورد؛ هر خط نامعتبر = توقف کل فراخوان.
  const lines = String(raw || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  if (lines.length > 8) {
    throw new Error("حداکثر ۸ شفاف‌سازی مجاز است");
  }
  const out = [];
  for (const line of lines) {
    const idx = line.indexOf("=");
    if (idx <= 0) throw new Error(`سطر شفاف‌سازی نامعتبر (باید key=value باشد): ${line.slice(0, 40)}`);
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (!/^[a-z][a-z0-9_]{0,39}$/.test(key)) throw new Error(`کلید نامعتبر: ${key.slice(0, 40)}`);
    if (!value || value.length > 200) throw new Error(`مقدار نامعتبر برای ${key.slice(0, 40)}`);
    out.push({ key, value });
  }
  return out;
}

async function generate() {
  const question = String($("ai2Question")?.value || "").trim();
  const symbol = String($("ai2Symbol")?.value || "").trim();
  if (!question) {
    toast("متن پرسش الزامی است");
    return;
  }
  if (!symbol) {
    toast("نماد الزامی است");
    return;
  }
  let clarifs;
  try {
    clarifs = parseClarifications($("ai2Clarifs")?.value);
  } catch (e) {
    toast(e.message || "شفاف‌سازی‌ها نامعتبر است");
    return;
  }
  const body = {
    question: question.slice(0, 2000),
    symbol: symbol.slice(0, 64),
    timeframe: String($("ai2Timeframe")?.value || "1D"),
    bar_count: Math.max(50, Math.min(500, parseInt(String($("ai2Bars")?.value || "200"), 10) || 200)),
    clarifications: clarifs,
    data_trust_state: "synthetic",
  };
  const endBar = String($("ai2EndBar")?.value || "").trim();
  if (endBar !== "") {
    const n = parseInt(endBar, 10);
    if (!Number.isFinite(n) || n < 0) {
      toast("اندیس انتهایی نامعتبر است");
      return;
    }
    body.end_bar_index = n;
  }
  const idem = String($("ai2IdemKey")?.value || "").trim();
  if (idem) {
    if (idem.length < 8) {
      toast("کلید یکسان‌سازی حداقل ۸ کاراکتر است");
      return;
    }
    body.idempotency_key = idem.slice(0, 128);
  }
  const parentRun = String($("ai2ParentRun")?.value || "").trim();
  if (parentRun) body.parent_run_id = parentRun.slice(0, 128);
  const hypId = String($("ai2HypId")?.value || "").trim();
  if (hypId) body.hypothesis_id = hypId.slice(0, 128);

  setOut("ai2GenOut", '<p class="muted">در حال ارسال درخواست تولید (گیت‌ها سمت سرور ارزیابی می‌شوند)…</p>');
  try {
    const j = await call("/api/v10/ai2/generate", {
      method: "POST",
      body: JSON.stringify(body),
    });
    renderOutcome(j);
  } catch (err) {
    setOut("ai2GenOut", `<p class="warn">${failText(err)}</p>`);
  }
}

function renderOutcome(j) {
  const status = String(j.status || "");
  const stLabel = label(OUTCOME_STATUS_LABELS, status);
  const kind = status === "executed" || status === "executed_shadow" ? "warn" : "ok";
  const prov = j.provenance || {};
  const entries = [
    ["status", `${stLabel} (${status})`],
    ["ok", j.ok],
    ["error_code", j.error_code],
    ["candidate_id", j.candidate_id],
    ["run_id", j.run_id],
    ["backtest_digest", j.backtest_digest],
    ["paper_summary_digest", j.paper_summary_digest],
    ["clarifications_needed", (j.clarifications_needed || []).join(" · ")],
  ];
  const provEntries = [
    ["schema_version", prov.schema_version],
    ["emitter_version", prov.emitter_version],
    ["policy_version", prov.policy_version],
    ["service_version", prov.service_version],
    ["model_provider_mode", prov.model_provider_mode],
    ["model_provider_label", prov.model_provider_label],
    ["model_identity", prov.model_identity],
    ["model_version", prov.model_version],
    ["evaluation_version", prov.evaluation_version],
    ["config_fingerprint", prov.config_fingerprint],
    ["parent_run_id", prov.parent_run_id],
    ["hypothesis_id", prov.hypothesis_id],
    ["data_trust_state", trustText(prov.data_trust_state)],
    ["execution_mode", prov.execution_mode],
    ["test_only_transport", prov.test_only_transport],
    ["injection_markers_detected", (prov.injection_markers_detected || []).join(" · ") || "—"],
    ["timeout_sec", prov.timeout_sec],
    ["created_at_utc", prov.created_at_utc],
  ];
  const metrics = j.metrics_headline && Object.keys(j.metrics_headline).length
    ? kvTable(Object.entries(j.metrics_headline))
    : '<p class="muted">—</p>';
  const warnings = (j.warnings || []).length
    ? `<p class="warn">هشدارها: ${esc(j.warnings.join(" · "))}</p>`
    : "";
  const src = j.generated_source
    ? `<h4>منبع تولیدشده (RSL-1 — عیناً از سرور)</h4><pre style="white-space:pre-wrap;font-size:11px">${esc(String(j.generated_source))}</pre>`
    : "";
  setOut(
    "ai2GenOut",
    `<p>${badge(`${stLabel} — ${status}`, kind)}</p>${warnings}
    ${kvTable(entries)}
    <h4>سنجه‌های تیتر (همیشه سری seed-دار SYNTHETIC)</h4>${metrics}
    <h4>شواهد مبدأ (provenance)</h4>${kvTable(provEntries)}
    ${src}
    <h4>پاکت صداقت سرور (عیناً)</h4>${honestyList(j.honesty)}`
  );
}

// ---------------------------------------------------------------------------
// candidates + human approve/promote
// ---------------------------------------------------------------------------
function candRow(c) {
  const st = String(c.status || "");
  return `<tr>
    <td>${esc(String(c.candidate_id || ""))}</td>
    <td>${esc(String(c.name || ""))}</td>
    <td>${badge(label(CANDIDATE_STATUS_LABELS, st), st === "PROMOTED" ? "warn" : "ok")}</td>
    <td>${esc(String(c.created_at_utc || "—"))}</td>
    <td>${esc(String(c.backtest_digest || "").slice(0, 16))}…</td>
    <td>${c.tampered ? badge("دستکاری‌شده!", "warn") : badge("سالم", "ok")}</td>
  </tr>`;
}

async function loadCandidates() {
  setOut("ai2CandOut", '<p class="muted">در حال خواندن فهرست نامزدها…</p>');
  try {
    const j = await call("/api/v10/ai2/candidates", { method: "GET" });
    const list = Array.isArray(j.candidates) ? j.candidates : [];
    const rows = list.map(candRow).join("");
    const table = list.length
      ? `<table class="data-table"><thead><tr><th>شناسه</th><th>نام</th><th>وضعیت</th><th>ایجاد</th><th>digest بک‌تست</th><th>حکم دستکاری</th></tr></thead><tbody>${rows}</tbody></table>`
      : '<p class="muted">هیچ نامزدی ثبت نشده است.</p>';
    setOut(
      "ai2CandOut",
      `${table}<p class="muted">${esc(String(j.note || ""))} (count=${esc(String(j.count ?? list.length))})</p>
      ${honestyList(j.honesty)}`
    );
  } catch (err) {
    setOut("ai2CandOut", `<p class="warn">${failText(err)}</p>`);
  }
}

async function loadCandidateDetail() {
  const id = String($("ai2CandId")?.value || "").trim();
  if (!id) {
    toast("شناسه نامزد را وارد کنید");
    return;
  }
  setOut("ai2CandDetailOut", '<p class="muted">در حال خواندن نامزد…</p>');
  try {
    const c = await call(`/api/v10/ai2/candidates/${encodeURIComponent(id)}`, { method: "GET" });
    renderCandidateDetail(c);
  } catch (err) {
    setOut("ai2CandDetailOut", `<p class="warn">${failText(err)}</p>`);
  }
}

function renderCandidateDetail(c) {
  const prov = c.provenance || {};
  setOut(
    "ai2CandDetailOut",
    `<p>${badge(`${label(CANDIDATE_STATUS_LABELS, c.status)} — ${String(c.status || "")}`, "warn")}
     ${c.tampered ? badge("حکم دستکاری: دستکاری‌شده", "warn") : badge("حکم دستکاری: سالم", "ok")}</p>
    ${kvTable([
      ["candidate_id", c.candidate_id],
      ["run_id", c.run_id],
      ["name", c.name],
      ["dsl_version", c.dsl_version],
      ["backtest_digest", c.backtest_digest],
      ["paper_summary_digest", c.paper_summary_digest],
      ["created_at_utc", c.created_at_utc],
      ["approved_by", c.approved_by],
      ["approved_at_utc", c.approved_at_utc],
      ["promoted_by", c.promoted_by],
      ["promoted_at_utc", c.promoted_at_utc],
      ["tampered", c.tampered],
    ])}
    <h4>شواهد مبدأ نامزد</h4>${kvTable([
      ["model_identity", prov.model_identity],
      ["model_provider_label", prov.model_provider_label],
      ["evaluation_version", prov.evaluation_version],
      ["config_fingerprint", prov.config_fingerprint],
      ["data_trust_state", trustText(prov.data_trust_state)],
      ["execution_mode", prov.execution_mode],
      ["created_at_utc", prov.created_at_utc],
    ])}
    <h4>منبع RSL-1 (عیناً)</h4><pre style="white-space:pre-wrap;font-size:11px">${esc(String(c.source || ""))}</pre>
    <h4>پاکت صداقت سرور (عیناً)</h4>${honestyList(c.honesty)}`
  );
}

async function approverOrToast() {
  const a = String($("ai2Approver")?.value || "").trim();
  if (a.length < 4) {
    toast("نام تأییدکنندهٔ انسانی الزامی است (حداقل ۴ کاراکتر) — مدل هیچ اختیاری ندارد");
    return null;
  }
  return a.slice(0, 128);
}

async function approveCandidate() {
  const approver = await approverOrToast();
  if (!approver) return;
  const id = String($("ai2CandId")?.value || "").trim();
  if (!id) {
    toast("شناسه نامزد را وارد کنید");
    return;
  }
  setOut("ai2ActionOut", '<p class="muted">در حال ارسال تأیید انسانی…</p>');
  try {
    const c = await call(`/api/v10/ai2/candidates/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ approver }),
    });
    renderCandidateDetail(c);
    setOut(
      "ai2ActionOut",
      `<p>${badge("تأیید انسانی ثبت شد (DRAFT → APPROVED) — دفتر کل فقط-الحاقی به‌روزرسانی شد", "warn")}</p>`
    );
  } catch (err) {
    setOut("ai2ActionOut", `<p class="warn">${failText(err)}</p>`);
  }
}

async function promoteCandidate() {
  const approver = await approverOrToast();
  if (!approver) return;
  const id = String($("ai2CandId")?.value || "").trim();
  if (!id) {
    toast("شناسه نامزد را وارد کنید");
    return;
  }
  setOut("ai2ActionOut", '<p class="muted">در حال ارسال درخواست ارتقا (فقط کاغذی)…</p>');
  try {
    const c = await call(`/api/v10/ai2/candidates/${encodeURIComponent(id)}/promote`, {
      method: "POST",
      body: JSON.stringify({ approver }),
    });
    renderCandidateDetail(c);
    setOut(
      "ai2ActionOut",
      `<p>${badge("ارتقا ثبت شد (APPROVED → PROMOTED)", "warn")}</p>
       <p class="muted">${esc(String(c.promotion_scope || ""))}</p>`
    );
  } catch (err) {
    setOut("ai2ActionOut", `<p class="warn">${failText(err)}</p>`);
  }
}

// ---------------------------------------------------------------------------
// runs ledger
// ---------------------------------------------------------------------------
async function loadRuns() {
  setOut("ai2RunsOut", '<p class="muted">در حال خواندن دفتر کل اجراها…</p>');
  try {
    const j = await call("/api/v10/ai2/runs", { method: "GET" });
    const recs = Array.isArray(j.records) ? j.records : [];
    const rows = recs
      .map(
        (r) => `<tr>
          <td>${esc(String(r.record_id || "").slice(0, 18))}</td>
          <td>${esc(String(r.run_id || "").slice(0, 18))}</td>
          <td>${esc(String(r.run_kind || ""))}</td>
          <td>${esc(String(r.task || ""))}</td>
          <td>${trustText(r.trust_state)}</td>
          <td>${esc(String(r.approval_state || "—"))}</td>
          <td>${esc(String(r.status || "—"))}</td>
          <td>${esc(String(r.recorded_at_utc || "—"))}</td>
        </tr>`
      )
      .join("");
    const table = recs.length
      ? `<table class="data-table"><thead><tr><th>شناسه رکورد</th><th>شناسه اجرا</th><th>نوع</th><th>وظیفه</th><th>اعتماد</th><th>وضعیت تأیید</th><th>وضعیت</th><th>زمان ثبت</th></tr></thead><tbody>${rows}</tbody></table>`
      : '<p class="muted">دفتر کل خالی است.</p>';
    setOut(
      "ai2RunsOut",
      `${table}<p class="muted">append_only=${esc(String(j.append_only))} · total=${esc(String(j.total ?? recs.length))} · truncated_to=${esc(String(j.truncated_to ?? "—"))} — رکوردها فقط-الحاقی‌اند؛ بی‌اعتب‌سازی با رکورد جدید ثبت می‌شود، هرگز بازنویسی نمی‌شود.</p>
      ${honestyList(j.honesty)}`
    );
  } catch (err) {
    setOut("ai2RunsOut", `<p class="warn">${failText(err)}</p>`);
  }
}

// ---------------------------------------------------------------------------
// bind
// ---------------------------------------------------------------------------
function bindAi2Studio() {
  if (bound) return;
  bound = true;

  on("ai2PostureReload", loadPosture);
  on("ai2Generate", generate);
  on("ai2CandidatesReload", loadCandidates);
  on("ai2CandLoad", loadCandidateDetail);
  on("ai2Approve", approveCandidate);
  on("ai2Promote", promoteCandidate);
  on("ai2RunsReload", loadRuns);

  const observer = new MutationObserver(() => {
    const panel = $("tab-aistudio");
    if (panel && panel.classList.contains("active") && !loaded) {
      loaded = true;
      loadPosture();
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
  document.querySelectorAll('[data-tab="aistudio"]').forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!loaded) setTimeout(loadPosture, 100);
    });
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindAi2Studio);
  else bindAi2Studio();
}
