/**
 * render/ai_ma_ui.js — WAVE-AI (2026-11-08, WP-C): هوش چندعاملی AI-MA
 *
 * افزودنی (additive-only): تب «هوش چندعاملی» — وضعیت واقعی زمان اجرای
 * ارکستراسیون مشورتی حاکمیت‌شده از /api/v10/aima (posture + orchestrate).
 *
 * قرارداد صداقت (هم‌الگو با product_loops_ui.js):
 * - همه HTTP از core/api.js (api()) می‌گذرد — هیچ واکشی مستقیمی مجاز نیست.
 * - هیچ اجرای پویای کد مجاز نیست — فقط innerHTML از متن فرارکننده‌شده (esc).
 * - برچسب اعتماد فقط از فیلدهای سرور خوانده می‌شود (data_trust_label)؛
 *   هیچ کلاسی ارتقا یا جعل نمی‌شود. اجرای AI-MA فقط SYNTHETIC_OR_PAPER است.
 * - پلن ثابت سرور است (فرضیه → {تفسیر ∥ چالش})؛ کلاینت فقط پرسش را می‌فرستد
 *   و نمی‌تواند گام/متخصص/بودجه تزریق کند.
 * - هیچ اجرای خودکاری وجود ندارد؛ هر فراخوان با کنش صریح کاربر انجام می‌شود.
 * - محدودیت‌های مشورتی همیشه با پاسخ سرور اعلام می‌شود (honesty envelope).
 */
import { api, toast } from "../../core/api.js";
import { esc } from "../../core/format.js";

let bound = false;
// 2026-11-08 owner directive (§4): تاریخچه اجرا فقط در نشست کلاینت (حافظه
// ماژول) — هیچ persist و هیچ ledger سمت کلاینت وجود ندارد؛ سرور هم چیزی
// ذخیره نمی‌کند (no_persistence در پاکت صداقت).
const runHistory = [];
const RUN_HISTORY_MAX = 8;

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
  // api() throws Error(msg) where msg is already the server's extracted
  // detail (array details are joined by core/api.js) — prefer err.message.
  const raw = err && err.message ? String(err.message) : "";
  if (raw) {
    let inner = raw;
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length) {
        const e0 = parsed[0] || {};
        inner = `${e0.msg || ""} (${(e0.loc || []).join(".")})` || raw;
      } else if (parsed && typeof parsed === "object") {
        inner = parsed.message_fa || parsed.reason || parsed.message_en || parsed.error || raw;
      }
    } catch {
      /* not JSON — use the raw server detail */
    }
    return esc(inner || raw);
  }
  const d = err && err.detail ? err.detail : null;
  if (d && typeof d === "object") {
    const fa = d.message_fa || d.reason || d.message_en || d.error || "";
    return `${esc(String(d.error || "خطا"))} — ${esc(String(fa))}`;
  }
  return esc(String(d || err || "خطای ناشناخته"));
}

function statusChip(status) {
  const s = String(status || "—");
  const cls = s === "SUCCEEDED" ? "ok" : s === "DEGRADED" ? "warn" : "err";
  return `<span class="cp-badge ${cls}">${esc(s)}</span>`;
}

function renderHonesty(honesty) {
  if (!honesty || typeof honesty !== "object") return "";
  const rows = Object.entries(honesty)
    .map(
      ([k, v]) =>
        `<li><b>${esc(k)}</b>: ${esc(String(v))}</li>`
    )
    .join("");
  return `<ul class="muted" style="font-size:12px">${rows}</ul>`;
}

async function loadPosture() {
  setOut("amPostureOut", `<p class="muted">⏳ در حال خواندن وضعیت زمان اجرا…</p>`);
  try {
    const data = await api("/api/v10/aima/posture");
    const specialists = Array.isArray(data.specialists) ? data.specialists : [];
    const rows = specialists
      .map(
        (s) => `
        <tr>
          <td>${esc(s.specialist_id)}</td>
          <td>${esc(s.capability)}</td>
          <td style="max-width:280px;font-size:11px">${esc(s.authority_boundary)}</td>
          <td>${esc((s.allowed_tools || []).join("، "))}</td>
          <td>${esc(String(s.max_invocations_per_run))}</td>
          <td>${esc(String(s.timeout_seconds))}s</td>
          <td>${esc(s.interaction_pattern)}</td>
        </tr>`
      )
      .join("");
    const tools = data.deterministic_tools || {};
    const toolRows = Object.entries(tools)
      .map(([k, v]) => `<li><b>${esc(k)}</b> — ${esc(String(v))}</li>`)
      .join("");
    setOut(
      "amPostureOut",
      `
      <p class="muted" style="font-size:12px">registry_version: ${esc(String(data.registry_version))}</p>
      <div style="overflow:auto"><table class="cp-table">
        <thead><tr><th>متخصص</th><th>توانایی</th><th>مرز اختیار</th><th>ابزارهای مجاز</th><th>سقف فراخوانی/اجرا</th><th>timeout</th><th>الگوی تعامل</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
      <h4 style="margin:8px 0 4px">ابزارهای قطعی بسته (تنها مسیر دسترسی متخصص‌ها)</h4>
      <ul class="muted" style="font-size:12px">${toolRows}</ul>
      <h4 style="margin:8px 0 4px">پاکت صداقت سرور</h4>
      ${renderHonesty(data.honesty)}`
    );
  } catch (err) {
    setOut("amPostureOut", `<p class="err-text">خطا در خواندن وضعیت: ${failText(err)}</p>`);
  }
}

function renderWaveSchedule(plan) {
  if (!plan || !Array.isArray(plan.wave_schedule)) return "";
  const waves = plan.wave_schedule
    .map((w, i) => `<b>موج ${i + 1}:</b> ${esc((w || []).join(" ∥ "))}`)
    .join(" · ");
  return `<p class="muted" style="font-size:12px">برنامه موج‌ها (پلن ثابت سرور): ${waves} — max_parallel=${esc(
    String(plan.max_parallel)
  )} / سقف زمان اجرا=${esc(String(plan.runtime_parallel_ceiling))}</p>`;
}

function renderSynthesis(syn) {
  if (!syn) return "";
  const sources = Array.isArray(syn.sources) ? syn.sources : [];
  const refused = Array.isArray(syn.refused) ? syn.refused : [];
  const srcRows = sources
    .map(
      (s) =>
        `<li><b>${esc(s.step_id)}</b> ← ${esc(s.specialist_id)} — artifact: ${esc(
          (s.artifact && s.artifact.artifact_id) || "—"
        )} · sha256: <code>${esc((s.artifact && s.artifact.sha256) || "—")}</code></li>`
    )
    .join("");
  const refRows = refused.length
    ? refused
        .map(
          (r) =>
            `<li class="err-text">رد شده: ${esc(r.branch_id)} (${esc(
              r.step_id || "—"
            )}) — ${esc(r.reason)}</li>`
        )
        .join("")
    : `<li class="muted">هیچ ردیفی رد نشده است</li>`;
  return `
    <h4 style="margin:8px 0 4px">سنتز قطعی (${esc(syn.authority)})</h4>
    <ul class="muted" style="font-size:12px">${srcRows}</ul>
    <h4 style="margin:8px 0 4px">ردیف‌های ردِ سنتز</h4>
    <ul class="muted" style="font-size:12px">${refRows}</ul>`;
}

function renderTrace(trace) {
  if (!Array.isArray(trace)) return "";
  const rows = trace
    .map(
      (e) =>
        `<tr><td>${esc(e.step_id || "—")}</td><td>${esc(e.kind)}</td><td style="max-width:420px;font-size:11px">${esc(
          String(e.detail || "")
        )}</td></tr>`
    )
    .join("");
  return `<div style="overflow:auto"><table class="cp-table">
    <thead><tr><th>گام</th><th>رخداد</th><th>جزئیات</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

async function runOrchestration() {
  const q = ($("amQuestion") && $("amQuestion").value || "").trim();
  setOut("amRunOut", `<p class="muted">⏳ در حال اجرای ارکستراسیون مشورتی (سه گام، دو شاخه موازی محدود)…</p>`);
  try {
    const data = await api("/api/v10/aima/orchestrate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    // trust label only from server fields
    const trust = String(data.data_trust_label || "—");
    const badge = $("amTrustBadge");
    if (badge) badge.textContent = `اعتماد: ${trust}`;
    // 2026-11-08 (§4): تاریخچه اجرا — فقط نشست کلاینت؛ هر رکورد فقط از
    // فیلدهای سرور (run_id, وضعیت, خلاصه، digest)؛ بدون محتوای خصوصی
    runHistory.unshift({
      run_id: String(data.run_id || "—"),
      at: new Date().toISOString(),
      status: data.terminated ? `خاتمه (${String(data.termination_reason || "")})` : "تکمیل",
      waves: `${String(data.waves_executed)}/${String(data.waves_total)}`,
      trust,
      steps: (Array.isArray(data.steps) ? data.steps : []).map((s) => ({
        step_id: String(s.step_id || ""),
        status: String(s.status || ""),
        sha256: String((s.artifact && s.artifact.sha256) || ""),
      })),
    });
    if (runHistory.length > RUN_HISTORY_MAX) runHistory.length = RUN_HISTORY_MAX;
    const steps = Array.isArray(data.steps) ? data.steps : [];
    // 2026-11-08 (§4): نمایشگر محتوای artifact هر گام — فقط payloadهای
    // فراهم‌شده از سرور (artifact_contents)؛ verbatim و esc-شده
    const contents = data.artifact_contents && typeof data.artifact_contents === "object" ? data.artifact_contents : {};
    const contentBlocks = Object.entries(contents)
      .map(([stepId, wrap]) => {
        const c = wrap && wrap.content;
        if (!c) return "";
        return `
        <details style="margin:4px 0">
          <summary style="cursor:pointer;font-size:12px">محتوای artifact گام <b>${esc(stepId)}</b> — artifact_id: <code>${esc(String((wrap && wrap.artifact_id) || "—"))}</code></summary>
          <pre style="direction:ltr;text-align:left;font-size:10px;max-height:220px;overflow:auto;background:rgba(127,127,127,0.08);padding:6px;border-radius:4px">${esc(JSON.stringify(c, null, 2))}</pre>
        </details>`;
      })
      .join("");
    const stepRows = steps
      .map(
        (s) => `
        <tr>
          <td>${esc(s.step_id)}</td>
          <td>${esc(s.specialist_id)}</td>
          <td>${statusChip(s.status)}</td>
          <td style="max-width:260px;font-size:11px">${esc(String(s.summary || ""))}</td>
          <td style="font-size:11px"><code>${esc((s.artifact && s.artifact.sha256) || "—")}</code></td>
          <td style="font-size:11px">${esc(String(s.failure_code || "—"))}</td>
        </tr>`
      )
      .join("");
    const gov = data.governance || {};
    setOut(
      "amRunOut",
      `
      <p class="muted" style="font-size:12px">
        run_id: <code>${esc(String(data.run_id || "—"))}</code> · plan_id: <code>${esc(
        String(data.plan_id || "—")
      )}</code> · برچسب اعتماد (سرور): <b>${esc(trust)}</b> · موج‌های اجراشده: ${esc(
        String(data.waves_executed)
      )}/${esc(String(data.waves_total))} · وضعیت: ${esc(
        data.terminated ? `خاتمه (${esc(String(data.termination_reason || ""))})` : "تکمیل"
      )}
      </p>
      ${renderWaveSchedule(data.plan)}
      <div style="overflow:auto"><table class="cp-table">
        <thead><tr><th>گام</th><th>متخصص</th><th>وضعیت</th><th>خلاصه</th><th>digest محتوا</th><th>کد خطا</th></tr></thead>
        <tbody>${stepRows}</tbody>
      </table></div>
      ${contentBlocks ? `<h4 style="margin:8px 0 4px">محتوای artifactها (payload سرور — فقط خواندنی)</h4>${contentBlocks}` : ""}
      ${renderSynthesis(data.synthesis)}
      <h4 style="margin:8px 0 4px">ردگیری اجرا (کامل و گام‌به‌گام)</h4>
      ${renderTrace(data.trace)}
      <h4 style="margin:8px 0 4px">رکورد حاکمیت</h4>
      <p class="muted" style="font-size:12px">run_kind=${esc(String(gov.run_kind))} · autonomy=${esc(
        String(gov.autonomy_level)
      )} · policy=${esc(String(gov.policy_version))} · provenance_missing=${esc(
        JSON.stringify(gov.provenance_missing || [])
      )} · governed_acceptance_blocked=${esc(String(gov.governed_acceptance_blocked))}</p>
      <h4 style="margin:8px 0 4px">محدودیت‌ها و صداقت (از سرور)</h4>
      ${renderHonesty(data.honesty)}`
    );
  } catch (err) {
    setOut("amRunOut", `<p class="err-text">خطا در اجرا: ${failText(err)}</p>`);
  }
}

function renderRunHistory() {
  const out = $("amHistoryOut");
  if (!out) return;
  if (!runHistory.length) {
    out.innerHTML = `<p class="muted">تاریخچه اجراهای این نشست خالی است — هر اجرا با کنش صریح شما اینجا ثبت می‌شود (فقط حافظه نشست؛ هیچ persist سمت کلاینت/سرور).</p>`;
    return;
  }
  const rows = runHistory
    .map(
      (r) => `
      <tr>
        <td style="font-size:11px"><code>${esc(r.run_id)}</code></td>
        <td style="font-size:11px">${esc(r.at)}</td>
        <td>${esc(r.status)}</td>
        <td>${esc(r.waves)}</td>
        <td>${esc(r.trust)}</td>
        <td style="font-size:10px">${r.steps
          .map((s) => `${esc(s.step_id)}:${esc(s.status)}${s.sha256 ? ` <code>${esc(s.sha256.slice(0, 10))}…</code>` : ""}`)
          .join("<br/>")}</td>
      </tr>`
    )
    .join("");
  out.innerHTML = `
    <p class="muted" style="font-size:12px">تعداد اجراهای این نشست: ${esc(String(runHistory.length))} (سقف ${esc(String(RUN_HISTORY_MAX))} — قدیمی‌ترین‌ها حذف می‌شوند)</p>
    <div style="overflow:auto"><table class="cp-table">
      <thead><tr><th>run_id</th><th>زمان نشست</th><th>وضعیت</th><th>موج‌ها</th><th>اعتماد (سرور)</th><th>گام‌ها</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
}

export function bindAiMa() {
  if (bound) return;
  bound = true;
  on("amPostureReload", loadPosture);
  on("amRunBtn", runOrchestration);
  on("amHistoryReload", renderRunHistory);
  renderRunHistory();
}
