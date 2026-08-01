/**
 * tabs/actions.js — اکشن‌های مشترک بین تب‌ها
 * (پورتفو، مودال نماد، گزارش عمیق بنیادی) — همگی از core/api و core/format استفاده می‌کنند.
 */
import { api } from "../core/api.js";
import { esc, fmtNum, fmtMoney, pctClass, scoreClass, gradeClass } from "../core/format.js";
import { store } from "../core/store.js";
import { events } from "../core/events.js";

const $ = (s, el = document) => el.querySelector(s);

/* ----------------------------- پورتفو ----------------------------- */
export async function addPortfolio(symbol) {
  const data = await api("/api/portfolio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
  store.set({ portfolio: data.portfolio || [] });
  events.emit("data:changed");
}

export async function removePortfolio(symbol) {
  const data = await api("/api/portfolio/" + encodeURIComponent(symbol), { method: "DELETE" });
  store.set({ portfolio: data.portfolio || [] });
  events.emit("data:changed");
}

/* ----------------------------- مودال نماد ----------------------------- */
export async function openSymbol(symbol, opts = {}) {
  if (opts.fullPage) {
    location.href = "/symbol?s=" + encodeURIComponent(symbol);
    return;
  }
  const modal = $("#symbolModal");
  const body = $("#modalBody");
  if (!modal || !body) return;
  body.innerHTML = `<p class="muted">در حال بارگذاری ${esc(symbol)}…</p>`;
  modal.classList.remove("hidden");
  try {
    const data = await api("/api/symbol/" + encodeURIComponent(symbol));
    const s = data.snapshot;
    const m = data.metrics;
    const tc = data.tablocastic || {};
    const f = data.fundamental || {};
    const inPf = data.in_portfolio;
    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;align-items:flex-start">
        <div>
          <h2 style="margin:0 0 .25rem">${esc(s.l18)} <small style="color:var(--muted);font-weight:400">${esc(s.l30 || "")}</small>
            <span class="grade ${gradeClass(tc.grade)}">${esc(tc.grade || "—")}</span></h2>
          <p class="muted">${esc(s.cs || "")} · منبع: ${esc(s.source || "")}</p>
        </div>
        <div class="pf-actions">
          <a class="btn primary" href="/symbol?s=${encodeURIComponent(s.l18)}">صفحه کامل ↗</a>
          ${inPf ? `<button class="btn danger-outline" id="modalPfDel">حذف از پورتفو</button>` : `<button class="btn ghost" id="modalPfAdd">＋ پورتفو</button>`}
        </div>
      </div>
      <div class="kv">
        <div><span>آخرین قیمت</span><b class="${pctClass(s.plp)}">${fmtNum(s.pl)} (${fmtNum(s.plp, 2)}٪)</b></div>
        <div><span>پایانی</span><b>${fmtNum(s.pc)} (${fmtNum(s.pcp, 2)}٪)</b></div>
        <div><span>حجم / میانگین</span><b>${fmtMoney(s.tvol)} / ×${fmtNum(m.volume_ratio, 2)}</b></div>
        <div><span>ارزش معاملات</span><b>${fmtMoney(s.tval)}</b></div>
        <div><span>قدرت خریدار</span><b>${fmtNum(m.buy_power, 2)}</b></div>
        <div><span>سرانه خرید / فروش</span><b>${fmtMoney(m.buy_per_capita)} / ${fmtMoney(m.sell_per_capita)}</b></div>
        <div><span>خالص حقیقی</span><b class="${pctClass(m.individual_net_value)}">${fmtMoney(m.individual_net_value)}</b></div>
        <div><span>P/E · EPS</span><b>${s.pe != null ? fmtNum(s.pe, 2) : "—"} · ${s.eps != null ? fmtNum(s.eps, 1) : "—"}</b></div>
        <div><span>امتیاز ورود / خروج</span><b><span class="pct-up">${fmtNum(m.entry_score, 1)}</span> / <span class="pct-down">${fmtNum(m.exit_score, 1)}</span></b></div>
        <div><span>عدد طلایی · D⁺ · M⁺</span><b>${fmtNum(tc.golden_number, 1)} · ${fmtNum(tc.d_plus, 1)} · ${fmtNum(tc.m_plus, 1)}</b></div>
      </div>
      <div style="margin-top:1rem"><div class="muted" style="margin-bottom:.35rem">دلایل</div>
        <ul class="reasons">${(m.reasons || []).slice(0, 4).map((r) => `<li>${esc(r)}</li>`).join("") || "—"}</ul></div>`;
    $("#modalPfAdd")?.addEventListener("click", async () => { await addPortfolio(s.l18); openSymbol(s.l18); });
    $("#modalPfDel")?.addEventListener("click", async () => { await removePortfolio(s.l18); openSymbol(s.l18); });
  } catch (e) {
    body.innerHTML = `<p class="pct-down">خطا: ${esc(e.message)}</p>`;
  }
}

/* ----------------------------- گزارش عمیق بنیادی ----------------------------- */
export async function openDeepFundamental(sym) {
  const modal = $("#deepFundModal");
  const body = $("#deepFundBody");
  if (!modal || !body) return;
  body.innerHTML = `<p class="muted">در حال تهیه گزارش ۵محوره برای ${esc(sym)}…</p>`;
  modal.classList.remove("hidden");
  try {
    const d = await api("/api/fundamental/" + encodeURIComponent(sym) + "/deep");
    const deep = d.deep || {};
    const s1 = deep.section_trend || {};
    const s2 = deep.section_profitability || {};
    const s3 = deep.section_liquidity || {};
    const s4 = deep.section_cash_quality || {};
    const s5 = deep.section_swot || {};
    const audit = s5.audit || {};

    const block = (items) =>
      (items || []).map((it) => `<li>${esc(it.kind === "definite" ? "✅" : "🔎")} ${esc(it.text)} <span class="muted">〔${esc(it.ref || "—")}〕</span></li>`).join("") || "<li class='muted'>—</li>";

    const table = (cols, rows) =>
      `<div class="table-wrap"><table class="data-table"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${r.map((v) => `<td>${v}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${cols.length}" class="empty">داده ناکافی</td></tr>`}</tbody></table></div>`;

    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap">
        <div><h2 style="margin:0">${esc(d.symbol)} — ${esc(d.name || "")}</h2>
          <p class="muted">${esc(d.industry || "")} · منبع: ${esc(d.source || "")}</p></div>
        <div class="pf-actions">
          <span class="score ${scoreClass(d.value_score)}">ارزندگی ${fmtNum(d.value_score, 1)}</span>
          <span class="grade ${gradeClass(d.value_grade)}">${esc(d.value_grade || d.grade)}</span>
          <a class="btn ghost" href="/symbol?s=${encodeURIComponent(d.symbol)}">صفحه نماد</a>
        </div>
      </div>
      <p class="muted">${esc(deep.disclaimer || "")}</p>
      <div class="kv">
        <div><span>P/E · EPS</span><b>${d.pe != null ? fmtNum(d.pe, 2) : "—"} · ${fmtNum(d.eps, 1)}</b></div>
        <div><span>ROE · ROA</span><b>${fmtNum(d.roe, 1)}٪ · ${fmtNum(d.roa, 1)}٪</b></div>
        <div><span>رشد سود · فروش</span><b class="${pctClass(d.profit_growth)}">${fmtNum(d.profit_growth, 1)}٪</b> · <b class="${pctClass(d.revenue_growth)}">${fmtNum(d.revenue_growth, 1)}٪</b></div>
        <div><span>بدهی · جاری</span><b>${fmtNum(d.debt_ratio, 2)} · ${fmtNum(d.current_ratio, 2)}</b></div>
      </div>
      <h3 style="margin:1.2rem 0 .5rem">۱) روند</h3>
      ${table(["قلم", "دوره۱", "دوره۲", "دوره۳", "تغییر٪"], (s1.table || []).map((r) => [esc(r.item), fmtMoney(r.p0), fmtMoney(r.p1), fmtMoney(r.p2), r.chg_p2_p0 != null ? fmtNum(r.chg_p2_p0, 1) + "٪" : "—"]))}
      <h3 style="margin:1.2rem 0 .5rem">۲) سودآوری</h3>
      ${table(["دوره", "حاشیه ناخالص", "عملیاتی", "خالص", "ROA", "ROE"], (s2.table || []).map((r) => [esc(r.period), fmtNum(r.gross_margin, 1), fmtNum(r.operating_margin, 1), fmtNum(r.net_margin, 1), fmtNum(r.roa, 1), fmtNum(r.roe, 1)]))}
      <h3 style="margin:1.2rem 0 .5rem">۳) نقدینگی/بدهی</h3>
      ${table(["دوره", "جاری", "آنی", "بدهی", "D/E"], (s3.table || []).map((r) => [esc(r.period), fmtNum(r.current_ratio, 2), fmtNum(r.quick_ratio, 2), fmtNum(r.debt_ratio, 2), fmtNum(r.debt_to_equity, 2)]))}
      <h3 style="margin:1.2rem 0 .5rem">۴) کیفیت سود</h3>
      ${table(["دوره", "سود خالص", "CFO", "CFO/سود", "FCF"], (s4.table || []).map((r) => [esc(r.period), fmtMoney(r.net_profit), fmtMoney(r.cfo), fmtNum(r.cfo_to_net, 2), fmtMoney(r.fcf)]))}
      <h3 style="margin:1.2rem 0 .5rem">۵) قوت و ریسک</h3>
      <div class="guide-grid">
        <article><h3>۵ نقطه قوت</h3><ul class="reasons">${block(s5.strengths)}</ul></article>
        <article><h3>۵ ریسک</h3><ul class="reasons">${block(s5.risks)}</ul></article>
        <article><h3>۵ سؤال کلیدی</h3><ul class="reasons">${block(s5.questions)}</ul></article>
        <article><h3>حسابرس</h3><div class="meta">اظهارنظر: <b>${esc(audit.opinion || "—")}</b></div>
          <div class="meta">تداوم فعالیت مشکوک: <b>${audit.going_concern_doubt ? "بله" : "خیر"}</b></div>
          <div class="meta">دعاوی/بدهی احتمالی: <b>${audit.legal_cases ? "دارد" : "ندارد"}</b></div></article>
      </div>`;
  } catch (e) {
    body.innerHTML = `<p class="pct-down">خطا: ${esc(e.message)}</p>`;
  }
}
