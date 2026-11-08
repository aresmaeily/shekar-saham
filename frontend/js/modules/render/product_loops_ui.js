/**
 * render/product_loops_ui.js — MASTER-RADAR WAVE-F (2026-11-05): حلقه‌های محصول
 *
 * افزودنی (additive-only): تب جدید «حلقه‌های محصول» — سطح حاکمیت‌شده پنج
 * حلقه بسته §5 (نظارت بازار، هوش شرکتی، پژوهش حاکمیت‌شده، هوش محصول،
 * بازخورد پیش‌بینی) از مسیر /api/v10/productloops/*.
 *
 * قرارداد صداقت (هم‌الگو با user_indicator_ui.js):
 * - همه HTTP از core/api.js (api()) می‌گذرد — هیچ واکشی مستقیمی مجاز نیست.
 * - هیچ اجرای پویای کد مجاز نیست — فقط innerHTML از متن فرارکننده‌شده (esc).
 * - برچسب اعتماد فقط از فیلدهای سرور خوانده می‌شود؛ هیچ کلاسی ارتقا یا جعل
 *   نمی‌شود. همه داده‌ها SYNTHETIC/DECLARED هستند (فیکسچر اعلامی مخزن).
 * - هیچ زمان‌بندی یا درخواست خودکاری وجود ندارد؛ هر فراخوان با کنش صریح
 *   کاربر انجام می‌شود. لحظه‌های زمانی همیشه ورودی کاربر هستند (بدون ساعت
 *   دیواری سمت کلاینت).
 * - ریجستری پیش‌بینی سمت سرور فرایند-محلی است و همین‌جا با پیام سرور اعلام
 *   می‌شود (persistence_note).
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

// ---------------------------------------------------------------------------
// L0 — manifest
// ---------------------------------------------------------------------------

async function loadManifest() {
  setOut("plManifestOut", '<p class="muted">در حال بارگذاری…</p>');
  try {
    const j = await call("/api/v10/productloops/manifest");
    const rows = (j.loops || [])
      .map(
        (l) => `<tr>
          <td>${esc(l.loop_id)}</td>
          <td>${esc(l.title_fa)}</td>
          <td><code>${esc(l.status)}</code></td>
          <td><code>${esc(l.data_trust)}</code></td>
          <td class="muted">${l.owner_gate_note ? esc(l.owner_gate_note) : "—"}</td>
        </tr>`
      )
      .join("");
    setOut(
      "plManifestOut",
      `<div class="cp-badge">${esc(j.manifest_version)}</div>
      <table class="cp-table"><thead><tr>
        <th>شناسه</th><th>حلقه</th><th>وضعیت</th><th>کلاس اعتماد</th><th>یادداشت مالک-گیت</th>
      </tr></thead><tbody>${rows}</tbody></table>`
    );
  } catch (err) {
    setOut("plManifestOut", `<p class="err">${failText(err)}</p>`);
  }
}

// ---------------------------------------------------------------------------
// L1 — market monitoring (existing surface, loop-consolidated view)
// ---------------------------------------------------------------------------

async function loadMarketLoop() {
  setOut("plMarketOut", '<p class="muted">در حال اجرای یک چرخه نظارت…</p>');
  try {
    const mi = await call("/api/ai/market-intelligence?limit=10&persist=false");
    const ops = await call("/api/alerts/ops/status");
    const snap = mi.snapshot || {};
    const industries = (mi.industries || []).slice(0, 5);
    const events = (mi.events || []).slice(0, 5);
    setOut(
      "plMarketOut",
      `<p><span class="cp-badge">${esc(snap.data_trust?.trust_class || snap.trust_class || "SYNTHETIC")}</span>
       ${esc(NO_LIVE_NOTE)}</p>
      <p class="muted">چرخه: ${esc(String(snap.cycle_id || "—"))} · فرصت‌ها: ${esc(String((mi.opportunities || []).length))} · صنایع: ${esc(String((mi.industries || []).length))}</p>
      <p class="muted">وضعیت عملیات هشدار: ${esc(JSON.stringify(ops).slice(0, 220))}</p>
      ${industries.length ? `<ul>${industries.map((i) => `<li>${esc(i.industry || i.name || JSON.stringify(i).slice(0, 80))}</li>`).join("")}</ul>` : ""}
      ${events.length ? `<p class="muted">رویدادها: ${esc(String(events.length))}</p>` : ""}`
    );
  } catch (err) {
    setOut("plMarketOut", `<p class="err">${failText(err)}</p>`);
  }
}

const NO_LIVE_NOTE = "SYNTHETIC — چرخه‌ی نظارت فقط-در-صورت-فراخوان؛ بدون زمان‌بند و بدون داده زنده (R-6/R-9)";

// ---------------------------------------------------------------------------
// L2 — declared dossier + conflicts
// ---------------------------------------------------------------------------

async function loadDossier() {
  const symbol = $("plDossierSymbol")?.value;
  const cutoff = $("plDossierCutoff")?.value?.trim();
  if (!cutoff) {
    toast("لحظه قطع اطلاعات (cutoff_utc) را وارد کنید — بدون آن هیچ برشی ساخته نمی‌شود");
    return;
  }
  setOut("plDossierOut", '<p class="muted">در حال ساخت پرونده اعلامی…</p>');
  try {
    const j = await call(
      `/api/v10/productloops/intel/dossier/${encodeURIComponent(symbol)}?cutoff_utc=${encodeURIComponent(cutoff)}`
    );
    const d = j.dossier || {};
    const facts = (d.facts || [])
      .map((f) => {
        const eligible = (j.pit.eligible_fact_ids || []).includes(f.fact_id);
        return `<tr class="${eligible ? "" : "muted"}">
          <td>${esc(f.fact_id)}</td>
          <td>${esc(f.metric)}</td>
          <td>${esc(f.value === null || f.value === undefined ? "NOT_AVAILABLE" : String(f.value))}</td>
          <td>${esc(f.unit || "—")}</td>
          <td>${esc(f.period?.publication_status || "—")}</td>
          <td>${eligible ? "✅ در قطع" : "⛔ بعد از قطع"}</td>
        </tr>`;
      })
      .join("");
    const conflicts = (j.source_conflicts?.conflicts || [])
      .map((c) => `<li><code>${esc(c.conflict_id)}</code> — ${esc(c.description)}</li>`)
      .join("");
    const restatements = (j.restatement_chain || [])
      .map((r) => `<li><code>${esc(r.fact_id)}</code> v${esc(String(r.restatement_version))} ← جانشین ${esc(r.supersedes_fact_id || "—")}</li>`)
      .join("");
    setOut(
      "plDossierOut",
      `<p><span class="cp-badge">${esc(d.data_trust_ref || "DECLARED")}</span> ${esc(j.honesty?.synthetic_note || "")}</p>
      <p class="muted">شرکت: ${esc(d.company_id)} · قطع: ${esc(j.pit.cutoff_utc)} · واجد: ${esc(String((j.pit.eligible_fact_ids || []).length))} · حذف‌شده بعد از قطع: ${esc(String((j.pit.excluded_later_published || []).length))}</p>
      <table class="cp-table"><thead><tr><th>شناسه</th><th>سنجه</th><th>مقدار</th><th>واحد</th><th>انتشار</th><th>PIT</th></tr></thead><tbody>${facts}</tbody></table>
      ${restatements ? `<p>زنجیره بازبیانی:</p><ul>${restatements}</ul>` : ""}
      ${conflicts ? `<p>تعارض منابع (زنده):</p><ul>${conflicts}</ul>` : '<p class="muted">تعارض کوتیشن بین دو منبع اعلامی یافت نشد</p>'}
      ${(d.missing_data || []).length ? `<p class="muted">داده‌های غایب (اعلامی، پر نمی‌شود): ${d.missing_data.map((m) => esc(m)).join(" · ")}</p>` : ""}`
    );
  } catch (err) {
    setOut("plDossierOut", `<p class="err">${failText(err)}</p>`);
  }
}

// ---------------------------------------------------------------------------
// L3 — governed research
// ---------------------------------------------------------------------------

async function loadResearchStatus() {
  setOut("plResearchOut", '<p class="muted">در حال خواندن وضعیت حاکمیت…</p>');
  try {
    const j = await call("/api/v10/productloops/research/status");
    const lp = j.live_permission_check || {};
    setOut(
      "plResearchOut",
      `<p><span class="cp-badge">${esc(j.ai2_gate?.posture || "—")}</span> AI-2: ${esc(String(j.ai2_gate?.ai2_enabled))}</p>
      <p>بررسی زنده اجازه اجرا: <strong>${lp.permitted ? "مجاز" : "رد شده"}</strong></p>
      ${(lp.refusals || []).length ? `<ul>${lp.refusals.map((r) => `<li><code>${esc(r)}</code></li>`).join("")}</ul>` : "<p class=\"muted\">بدون ردیف رد</p>"}
      <p class="muted">${esc(lp.note || "")}</p>
      <p class="muted">kill-switch: ${esc(String(j.job?.kill_switch || "ENGAGED"))} — آزادسازی تصمیم مالک است</p>`
    );
  } catch (err) {
    setOut("plResearchOut", `<p class="err">${failText(err)}</p>`);
  }
}

async function evaluateHypothesis() {
  let body = null;
  try {
    body = JSON.parse($("plHypBody")?.value || "null");
  } catch {
    toast("بدنه JSON معتبر نیست");
    return;
  }
  if (!body || !Array.isArray(body.members) || !body.members.length) {
    toast("بدنه باید شامل family_id، method، alpha و members باشد");
    return;
  }
  setOut("plHypOut", '<p class="muted">در حال ارزیابی قطعی…</p>');
  try {
    const j = await call("/api/v10/productloops/research/hypotheses/evaluate", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const rows = (j.verdicts || [])
      .map(
        (v) => `<tr>
          <td>${esc(v.hypothesis_id)}</td>
          <td>${esc(v.method)}</td>
          <td>${esc(String(v.raw_pvalue))}</td>
          <td>${esc(v.adjusted_pvalue === null ? "—" : String(v.adjusted_pvalue))}</td>
          <td><strong>${esc(v.verdict)}</strong></td>
        </tr>`
      )
      .join("");
    setOut(
      "plHypOut",
      `<p class="muted">digest: <code>${esc(j.digest_sha256)}</code> (بازپخش همان ورودی، همان خروجی)</p>
      <table class="cp-table"><thead><tr><th>فرضیه</th><th>روش</th><th>p خام</th><th>p تعدیل‌شده</th><th>حکم</th></tr></thead><tbody>${rows}</tbody></table>`
    );
  } catch (err) {
    setOut("plHypOut", `<p class="err">${failText(err)}</p>`);
  }
}

// ---------------------------------------------------------------------------
// L4 — on-demand product audit
// ---------------------------------------------------------------------------

async function runAudit() {
  const s = $("plAuditStart")?.value?.trim();
  const e = $("plAuditEnd")?.value?.trim();
  if (!s || !e) {
    toast("شروع و پایان پنجره را وارد کنید (لحظه‌های صریح، بدون ساعت دیواری)");
    return;
  }
  setOut("plAuditOut", '<p class="muted">در حال اجرای یک چرخه ممیزی واقعی…</p>');
  try {
    const j = await call("/api/v10/productloops/product-audit/run", {
      method: "POST",
      body: JSON.stringify({ window_start_utc: s, window_end_utc: e }),
    });
    const rows = (j.drift?.metric_assessments || [])
      .map(
        (m) => `<tr>
          <td>${esc(m.name)}</td>
          <td>${esc(String(m.earlier_value))}</td>
          <td>${esc(String(m.later_value))}</td>
          <td>${esc(m.delta === null ? "—" : String(m.delta))}</td>
          <td><strong>${esc(m.verdict)}</strong></td>
        </tr>`
      )
      .join("");
    const pd = j.probe_details || {};
    const proposals = (j.run_record?.proposal_ids || []);
    setOut(
      "plAuditOut",
      `<p><span class="cp-badge">${esc(j.drift?.drift_verdict || "—")}</span>
       <code class="muted">digest=${esc(String(j.run_record?.run_id || ""))}</code></p>
      <table class="cp-table"><thead><tr><th>سنجه</th><th>بیس‌لاین</th><th>اندازه‌گیری</th><th>دلتا</th><th>حکم</th></tr></thead><tbody>${rows}</tbody></table>
      <p class="muted">دایجست‌های probe — تابلوخوانی: <code>${esc(String(pd.tablokhani?.digest_sha256 || "").slice(0, 16))}…</code> · کیفیت‌داده: <code>${esc(String(pd.dataquality?.digest_sha256 || "").slice(0, 16))}…</code> · چارت: <code>${esc(String(pd.chartpro?.digest_sha256 || "").slice(0, 16))}…</code></p>
      ${proposals.length ? `<p>پیشنهاد مشورتی (هرگز تولید را تغییر نمی‌دهد): ${proposals.map((p) => `<code>${esc(p)}</code>`).join(" · ")}</p>` : '<p class="muted">بدون پیشنهاد — بدون drift</p>'}
      <p class="muted">${esc(j.honesty?.no_scheduler_note || "")}</p>`
    );
  } catch (err) {
    setOut("plAuditOut", `<p class="err">${failText(err)}</p>`);
  }
}

// ---------------------------------------------------------------------------
// L5 — prediction feedback
// ---------------------------------------------------------------------------

async function registerPrediction() {
  const body = {
    prediction_id: $("plPredId")?.value?.trim(),
    subject: $("plPredSubject")?.value?.trim() || "SYNTHETIC",
    registered_at_utc: $("plPredRegAt")?.value?.trim(),
    outcome_horizon_end_utc: $("plPredHorizon")?.value?.trim(),
    evaluation_metric: $("plPredMetric")?.value?.trim() || "DIRECTION_HIT",
    event_maturity_rule: "horizon_end",
    invalidation_rule: "subject_removed",
    evidence_ids: ["DECLARED-PREDICTION-EVIDENCE"],
    creator: "product-loops-ui",
    notes: "",
  };
  if (!body.prediction_id || !body.registered_at_utc || !body.outcome_horizon_end_utc) {
    toast("شناسه، لحظه ثبت و پایان افق همه الزامی است");
    return;
  }
  try {
    const j = await call("/api/v10/productloops/predictions/register", {
      method: "POST",
      body: JSON.stringify(body),
    });
    toast(`ثبت شد — نسخه ریجستری ${j.registry_version}`);
    loadPredictionList();
  } catch (err) {
    setOut("plPredOut", `<p class="err">${failText(err)}</p>`);
  }
}

async function recordOutcome() {
  const pid = $("plOutPid")?.value?.trim();
  const observedAt = $("plOutAt")?.value?.trim();
  const observedNumeric = parseFloat($("plOutVal")?.value || "");
  if (!pid || !observedAt || Number.isNaN(observedNumeric)) {
    toast("شناسه پیش‌بینی، لحظه مشاهده و مقدار عددی همه الزامی است");
    return;
  }
  try {
    const j = await call(`/api/v10/productloops/predictions/${encodeURIComponent(pid)}/outcome`, {
      method: "POST",
      body: JSON.stringify({
        outcome_id: `OUT-${pid}-${Date.now().toString(36)}`,
        observed_at_utc: observedAt,
        observed_numeric: observedNumeric,
        source_evidence_ids: ["DECLARED-OUTCOME-EVIDENCE"],
        notes: "",
      }),
    });
    toast(`برون‌داد ثبت شد — نسخه ریجستری ${j.registry_version}`);
    loadPredictionList();
  } catch (err) {
    setOut("plPredOut", `<p class="err">${failText(err)}</p>`);
  }
}

async function loadPredictionList() {
  const asOf = $("plPredAsOf")?.value?.trim();
  if (!asOf) {
    toast("لحظه بلوغ (as_of_utc) را وارد کنید");
    return;
  }
  setOut("plPredOut", '<p class="muted">در حال خواندن ریجستری…</p>');
  try {
    const j = await call(
      `/api/v10/productloops/predictions?as_of_utc=${encodeURIComponent(asOf)}`
    );
    const rows = (j.rows || [])
      .map(
        (r) => `<tr>
          <td>${esc(r.prediction.prediction_id)}</td>
          <td>${esc(r.prediction.subject)}</td>
          <td>${esc(r.prediction.evaluation_metric)}</td>
          <td><strong>${esc(r.maturity_state)}</strong></td>
          <td>${r.has_outcome ? "✅" : "—"}</td>
        </tr>`
      )
      .join("");
    setOut(
      "plPredOut",
      `<p class="muted">${esc(j.persistence_note || "")} · نسخه: ${esc(String(j.registry_version))}</p>
      <table class="cp-table"><thead><tr><th>شناسه</th><th>موضوع</th><th>سنجه</th><th>بلوغ</th><th>برون‌داد</th></tr></thead><tbody>${rows || "<tr><td colspan=5 class=muted>خالی</td></tr>"}</tbody></table>`
    );
  } catch (err) {
    setOut("plPredOut", `<p class="err">${failText(err)}</p>`);
  }
}

async function runCalibration() {
  const measuredAt = $("plCalAt")?.value?.trim();
  let pairs = null;
  try {
    pairs = JSON.parse($("plCalPairs")?.value || "null");
  } catch {
    toast("JSON جفت‌ها معتبر نیست");
    return;
  }
  if (!measuredAt || !Array.isArray(pairs) || !pairs.length) {
    toast("لحظه اندازه‌گیری و آرایه جفت‌ها الزامی است");
    return;
  }
  setOut("plCalOut", '<p class="muted">در حال محاسبه Brier/ECE…</p>');
  try {
    const j = await call(
      `/api/v10/productloops/predictions/calibration?measured_at_utc=${encodeURIComponent(measuredAt)}`,
      { method: "POST", body: JSON.stringify({ pairs, bucket_count: 10 }) }
    );
    const cal = j.calibration || {};
    setOut(
      "plCalOut",
      `<p>Brier: <strong>${esc(String(cal.brier_score))}</strong> · ECE: <strong>${esc(String(cal.expected_calibration_error))}</strong> · n=${esc(String(cal.sample_size))}</p>
      <p class="muted">${esc(cal.coverage_complete ? "پوشش کامل" : "پوشش ناقص: " + (cal.coverage_gaps || []).join(" · "))}</p>`
    );
  } catch (err) {
    setOut("plCalOut", `<p class="err">${failText(err)}</p>`);
  }
}

// ---------------------------------------------------------------------------
// bind
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// 2026-11-08 owner directive (AI-3 real integration + AI-7 Golden Set v2):
// حافظه پژوهش ماندگار + ردیف حسابرسی دسترسی + گزارش نسخه‌دار GS2 — همه
// فقط-خواندنی/کنش-صریح؛ هیچ مسیر حذفی وجود ندارد؛ برچسب اعتماد فقط از سرور
// ---------------------------------------------------------------------------

async function loadMemoryPosture() {
  setOut("plMemOut", `<p class="muted">⏳ در حال خواندن وضعیت حافظه پژوهش…</p>`);
  try {
    const data = await api("/api/v10/memory/posture");
    const p = data.posture || {};
    const trust = String((data.trust_envelope && data.trust_envelope.data_trust_label) || "—");
    const badge = $("plTrustBadge");
    if (badge) badge.textContent = `اعتماد: ${trust}`;
    const gate = p.audit_gate_closed_reason
      ? `<span class="cp-badge err">گیت حسابرسی: بسته (${esc(String(p.audit_gate_closed_reason))})</span>`
      : `<span class="cp-badge ok">گیت حسابرسی: باز و سالم</span>`;
    setOut("plMemOut", `
      <p class="muted" style="font-size:12px">
        backend: <b>${esc(String(p.backend))}</b> · ماندگار: <b>${esc(String(p.persistence_durable))}</b> ·
        رمزنگاری در حالت سکون (AES-256-GCM/D4): <b>${esc(String(p.encryption_at_rest))}</b> ·
        زنجیره حسابرسی ماندگار: <b>${esc(String(p.audit_trail_durable))}</b> ·
        تعداد ردیف‌های حسابرسی: ${esc(String(p.audit_entries))} ·
        برچسب اعتماد (سرور): <b>${esc(String(p.data_trust_label))}</b>
        ${p.refused_reason ? ` · <span class="err-text">وضعیت رد fail-closed: ${esc(String(p.refused_reason))}</span>` : ""}
      </p>
      <p>${gate}</p>
      <p class="muted" style="font-size:12px">${esc(String(p.retention_policy || ""))}</p>
      <ul class="muted" style="font-size:12px">
        <li>${esc(String((data.disclosures && data.disclosures.no_purge_path) || ""))}</li>
        <li>${esc(String((data.disclosures && data.disclosures.audit_refs_only) || ""))}</li>
        <li>${esc(String((data.disclosures && data.disclosures.fail_closed_key) || ""))}</li>
      </ul>`);
  } catch (err) {
    setOut("plMemOut", `<p class="err-text">خطا در وضعیت حافظه پژوهش: ${failText(err)}</p>`);
  }
}

async function loadMemoryIntegrity() {
  setOut("plMemOut", `<p class="muted">⏳ در حال بررسی صحت محتوا و زنجیره حسابرسی…</p>`);
  try {
    const data = await api("/api/v10/memory/integrity");
    const integ = data.integrity || {};
    const chain = data.audit_chain || {};
    const verdictOk = chain.verdict === "INTACT";
    setOut("plMemOut", `
      <p class="muted" style="font-size:12px">صحت محتوا (هش هر رکورد): verify_ok=<b>${esc(String(integ.verify_ok))}</b> · تعداد رکوردهای اپیزودیک: ${esc(String(integ.entry_count))} · نسخه‌های درس معنایی: ${esc(String((integ.lesson_version_counts || []).length))}</p>
      <p>${verdictOk ? `<span class="cp-badge ok">زنجیره حسابرسی: INTACT</span>` : `<span class="cp-badge err">زنجیره حسابرسی: ${esc(String(chain.verdict))} — گیت بسته شد (fail-closed)</span>`}</p>
      <p class="muted" style="font-size:12px">head_digest: <code>${esc(String(chain.head_digest || "—"))}</code> · first_broken_sequence: ${esc(String(chain.first_broken_sequence))} · gate_closed_reason: ${esc(String(chain.gate_closed_reason || "—"))}</p>`);
  } catch (err) {
    setOut("plMemOut", `<p class="err-text">خطا در بررسی صحت: ${failText(err)}</p>`);
  }
}

async function loadMemoryAudit() {
  setOut("plMemOut", `<p class="muted">⏳ در حال خواندن ردیف حسابرسی دسترسی…</p>`);
  try {
    const data = await api("/api/v10/memory/audit");
    const rows = Array.isArray(data.entries) ? data.entries : [];
    const trust = String((data.trust_envelope && data.trust_envelope.data_trust_label) || "—");
    const badge = $("plTrustBadge");
    if (badge) badge.textContent = `اعتماد: ${trust}`;
    const trs = rows
      .map(
        (e) => `
        <tr>
          <td>${esc(String(e.sequence))}</td>
          <td>${esc(String(e.actor))}</td>
          <td>${esc(String(e.operation))}</td>
          <td>${esc(String(e.memory_layer))}</td>
          <td style="max-width:200px;font-size:11px">${esc(String(e.object_ref))}</td>
          <td>${e.outcome === "OK" ? `<span class="cp-badge ok">OK</span>` : `<span class="cp-badge err">REFUSED — ${esc(String(e.refusal_reason || ""))}</span>`}</td>
          <td style="font-size:10px"><code>${esc(String(e.entry_digest || "").slice(0, 16))}…</code></td>
        </tr>`
      )
      .join("");
    const chain = data.chain || {};
    setOut("plMemOut", `
      <p class="muted" style="font-size:12px">تعداد ردیف‌ها: ${esc(String(data.count))} · زنجیره ماندگار: ${esc(String(chain.durable))} · head: <code>${esc(String(chain.head_digest || "—")).slice(0, 24)}…</code>${chain.gate_closed_reason ? ` · <span class="err-text">گیت بسته: ${esc(String(chain.gate_closed_reason))}</span>` : ""}</p>
      ${rows.length ? `<div style="overflow:auto"><table class="cp-table">
        <thead><tr><th>#</th><th>فعّال</th><th>عملیات</th><th>لایه</th><th>ارجاع (بدون محتوا)</th><th>نتیجه</th><th>digest</th></tr></thead>
        <tbody>${trs}</tbody></table></div>` : `<p class="muted">هنوز ردیفی ثبت نشده است (هر عملیات واقعی یک ردیف ثبت می‌کند).</p>`}
      <p class="muted" style="font-size:11px">ردیف‌های حسابرسی فقط ارجاع دارند و محتوای خصوصی هرگز وارد دفتر نمی‌شود؛ زنجیره SHA-256 هر تغییر تک‌بایتی را کشف می‌کند.</p>`);
  } catch (err) {
    setOut("plMemOut", `<p class="err-text">خطا در ردیف حسابرسی: ${failText(err)}</p>`);
  }
}

async function runMemoryBackup() {
  setOut("plMemOut", `<p class="muted">⏳ در حال پشتیبان‌گیری تأییدشده (D5)…</p>`);
  try {
    const data = await api("/api/v10/memory/backup", { method: "POST" });
    const parts = (data.backup && data.backup.parts) || {};
    const rows = Object.entries(parts)
      .map(
        ([k, v]) =>
          `<li><b>${esc(k)}</b>: <code>${esc(String(v.path || ""))}</code> — sha256: <code>${esc(String(v.sha256 || "")).slice(0, 32)}…</code> (${esc(String(v.byte_size))} bytes، verified=${esc(String(v.verified))})</li>`
      )
      .join("");
    setOut("plMemOut", `
      <p class="muted" style="font-size:12px">${esc(String(data.destination || ""))}</p>
      <ul class="muted" style="font-size:12px">${rows || `<li>پشتوانه‌ای ماندگار برای پشتیبان‌گیری نیست (backend غیرماندگار).</li>`}</ul>`);
  } catch (err) {
    setOut("plMemOut", `<p class="err-text">خطا در پشتیبان‌گیری: ${failText(err)}</p>`);
  }
}

async function loadGoldenSetV2Report() {
  setOut("plGs2Out", `<p class="muted">⏳ در حال خواندن گزارش نسخه‌دار Golden Set v2…</p>`);
  try {
    const data = await api("/api/v10/productloops/goldenset/v2/report");
    const rep = data.report || {};
    const trust = String(data.data_trust_label || "—");
    const badge = $("plTrustBadge");
    if (badge) badge.textContent = `اعتماد: ${trust}`;
    const kinds = Object.entries(rep.per_kind || {})
      .map(
        ([k, v]) =>
          `<tr><td>${esc(k)}</td><td>${esc(String(v.cases))}</td><td>${esc(String(v.passed))}</td><td>${esc(String(v.failed))}</td><td>${esc(String(v.false_positives))}</td><td>${esc(String(v.false_negatives))}</td></tr>`
      )
      .join("");
    const cases = (Array.isArray(data.cases) ? data.cases : [])
      .map(
        (c) =>
          `<tr><td>${esc(c.case_id)}</td><td>${esc(c.kind)}</td><td>${c.passed ? `<span class="cp-badge ok">PASS</span>` : `<span class="cp-badge err">FAIL</span>`}</td><td style="font-size:10px">${esc((c.failure_reasons || []).join("؛ ") || "—")}</td></tr>`
      )
      .join("");
    setOut("plGs2Out", `
      <p class="muted" style="font-size:12px">
        نسخه: <b>${esc(String(rep.version_id))}</b> · cases_digest: <code>${esc(String(rep.cases_digest)).slice(0, 24)}…</code> ·
        مجموع: ${esc(String(rep.total_cases))} · گذرانده: <b>${esc(String(rep.passed))}</b> · رد شده: ${esc(String(rep.failed))} ·
        FP: <b>${esc(String(rep.false_positives_total))}</b> · FN: <b>${esc(String(rep.false_negatives_total))}</b>
      </p>
      <div style="overflow:auto"><table class="cp-table">
        <thead><tr><th>نوع توانایی</th><th>موارد</th><th>گذرانده</th><th>رد</th><th>FP</th><th>FN</th></tr></thead>
        <tbody>${kinds}</tbody></table></div>
      <div style="overflow:auto"><table class="cp-table">
        <thead><tr><th>مورد</th><th>نوع</th><th>نتیجه</th><th>دلایل رد</th></tr></thead>
        <tbody>${cases}</tbody></table></div>
      <p class="muted" style="font-size:12px">baseline (v1): corpus=${esc(String(rep.baseline_results && rep.baseline_results.corpus))} · version=${esc(String(rep.baseline_results && rep.baseline_results.version_id))} · cases=${esc(String(rep.baseline_results && rep.baseline_results.cases))}</p>
      <p class="muted" style="font-size:12px">candidate (v2): corpus=${esc(String(rep.candidate_results && rep.candidate_results.corpus))} · version=${esc(String(rep.candidate_results && rep.candidate_results.version_id))} · cases=${esc(String(rep.candidate_results && rep.candidate_results.cases))}</p>
      <p><span class="cp-badge warn">بدون ادعای برتری</span> <span class="muted" style="font-size:12px">${esc(String(rep.note || ""))}</span></p>`);
  } catch (err) {
    setOut("plGs2Out", `<p class="err-text">خطا در گزارش Golden Set v2: ${failText(err)}</p>`);
  }
}

function bindProductLoopsUI() {
  if (bound) return;
  bound = true;

  on("plManifestReload", loadManifest);
  on("plMarketCycle", loadMarketLoop);
  on("plDossierLoad", loadDossier);
  on("plResearchStatus", loadResearchStatus);
  on("plHypEval", evaluateHypothesis);
  on("plAuditRun", runAudit);
  on("plPredRegister", registerPrediction);
  on("plOutcomeRecord", recordOutcome);
  on("plPredList", loadPredictionList);
  on("plCalRun", runCalibration);
  on("plMemPosture", loadMemoryPosture);
  on("plMemIntegrity", loadMemoryIntegrity);
  on("plMemAudit", loadMemoryAudit);
  on("plMemBackup", runMemoryBackup);
  on("plGs2Report", loadGoldenSetV2Report);

  const observer = new MutationObserver(() => {
    const panel = $("tab-loops");
    if (panel && panel.classList.contains("active") && !loaded) {
      loaded = true;
      loadManifest();
    }
  });
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["class"] });
  document.querySelectorAll('[data-tab="loops"]').forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!loaded) setTimeout(loadManifest, 100);
    });
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindProductLoopsUI);
  else bindProductLoopsUI();
}
