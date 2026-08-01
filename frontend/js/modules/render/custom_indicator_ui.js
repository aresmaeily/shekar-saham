/**
 * custom_indicator_ui.js - UI for adding personal indicators - Feature faraz doesn't have
 */
import { customIndicatorEngine } from "../custom_indicator.js";
import { escapeHtml } from "../security.js";

export function renderCustomIndicatorPanel(chartInstance, ohlcvData) {
  const containerId = "customIndicatorPanel";
  let container = document.getElementById(containerId);
  if (!container) {
    container = document.createElement("div");
    container.id = containerId;
    container.className = "panel";
    container.innerHTML = `
      <div class="panel-head">
        <div>
          <h3>🎨 اندیکاتور شخصی - قابلیتی که فراز نداره</h3>
          <p class="muted">فرمول خودت رو بنویس، مثل TradingView Pine Script ساده</p>
        </div>
      </div>
      <div class="settings-grid">
        <div class="setting-card">
          <label>نام اندیکاتور</label>
          <input id="ciName" class="text-input" placeholder="مثلا: بولینگر شخصی من" />
        </div>
        <div class="setting-card">
          <label>فرمول (مثال: SMA(close,20) * 1.02)</label>
          <input id="ciFormula" class="text-input" placeholder="SMA(close, 20) * 1.02" value="SMA(close, 20) * 1.02" />
          <div class="hint">توابع: SMA(close,20), EMA(close,50), RSI(close,14), STD(close,20), close*0.99</div>
        </div>
        <div class="setting-card">
          <label>رنگ</label>
          <input id="ciColor" type="color" value="#22d3ee" />
        </div>
      </div>
      <div class="filters" style="margin-top:1rem">
        <button class="btn primary" id="ciAddBtn">➕ افزودن به چارت</button>
        <button class="btn ghost" id="ciClearBtn">پاک کردن همه</button>
      </div>
      <div class="filters" style="margin:1rem 0" id="ciExamples">
        <span class="muted">نمونه‌ها:</span>
        <button class="btn tiny" data-ex="SMA(close, 20)">SMA20</button>
        <button class="btn tiny" data-ex="EMA(close, 50)">EMA50</button>
        <button class="btn tiny" data-ex="SMA(close, 20) * 1.02">بولینگر بالا</button>
        <button class="btn tiny" data-ex="SMA(close, 20) * 0.98">بولینگر پایین</button>
        <button class="btn tiny" data-ex="close * 0.99">حمایت 1%</button>
        <button class="btn tiny" data-ex="RSI(close, 14)">RSI</button>
      </div>
      <div id="ciList" class="cards" style="margin-top:1rem"></div>
      <p class="muted" id="ciMsg"></p>
    `;
    
    // Append to chart panel or excellent panel
    const chartPanel = document.getElementById("panel-chart") || document.getElementById("tab-excellent");
    if (chartPanel) {
      chartPanel.appendChild(container);
    }
  }

  const renderList = () => {
    const listEl = document.getElementById("ciList");
    const indicators = customIndicatorEngine.indicators;
    if (!indicators.length) {
      listEl.innerHTML = `<div class="muted">هنوز اندیکاتور شخصی نداری - یکی اضافه کن</div>`;
      return;
    }
    listEl.innerHTML = indicators.map(ind => `
      <div class="icard">
        <h4>${escapeHtml(ind.name)} <span style="display:inline-block;width:12px;height:12px;background:${ind.color};border-radius:50%;margin-right:5px"></span></h4>
        <div class="meta">${escapeHtml(ind.formula)}</div>
        <div class="pf-actions" style="margin-top:.5rem">
          <button class="btn tiny" data-apply="${ind.id}">نمایش</button>
          <button class="btn tiny danger-outline" data-del="${ind.id}">حذف</button>
        </div>
      </div>
    `).join("");

    listEl.querySelectorAll("[data-apply]").forEach(btn => {
      btn.onclick = () => {
        try {
          const ind = customIndicatorEngine.indicators.find(i => i.id === btn.dataset.apply);
          if (!ind) return;
          const data = customIndicatorEngine.execute(ind.formula, ohlcvData);
          if (chartInstance && data.length) {
            const series = chartInstance.chart.addLineSeries({ color: ind.color, lineWidth: ind.lineWidth, title: ind.name });
            series.setData(data);
            // Save reference for removal
            ind._series = series;
            document.getElementById("ciMsg").textContent = `اندیکاتور ${ind.name} اضافه شد (${data.length} نقطه)`;
          }
        } catch (e) {
          document.getElementById("ciMsg").textContent = "خطا: " + e.message;
        }
      };
    });

    listEl.querySelectorAll("[data-del]").forEach(btn => {
      btn.onclick = () => {
        const ind = customIndicatorEngine.indicators.find(i => i.id === btn.dataset.del);
        if (ind && ind._series) {
          try { chartInstance.chart.removeSeries(ind._series); } catch {}
        }
        customIndicatorEngine.removeIndicator(btn.dataset.del);
        renderList();
      };
    });
  };

  renderList();

  document.getElementById("ciAddBtn").onclick = () => {
    const name = document.getElementById("ciName").value.trim() || "اندیکاتور شخصی";
    const formula = document.getElementById("ciFormula").value.trim();
    const color = document.getElementById("ciColor").value;
    
    try {
      customIndicatorEngine.addIndicator({ name, formula, color });
      document.getElementById("ciName").value = "";
      document.getElementById("ciMsg").textContent = "✅ اندیکاتور ذخیره شد - حالا دکمه نمایش رو بزن";
      renderList();
    } catch (e) {
      document.getElementById("ciMsg").textContent = "❌ " + e.message;
    }
  };

  document.getElementById("ciClearBtn").onclick = () => {
    customIndicatorEngine.indicators.forEach(ind => {
      if (ind._series) {
        try { chartInstance.chart.removeSeries(ind._series); } catch {}
      }
    });
    customIndicatorEngine.indicators = [];
    customIndicatorEngine.saveToStorage();
    renderList();
    document.getElementById("ciMsg").textContent = "همه پاک شد";
  };

  document.querySelectorAll("#ciExamples [data-ex]").forEach(btn => {
    btn.onclick = () => {
      document.getElementById("ciFormula").value = btn.dataset.ex;
    };
  });
}
