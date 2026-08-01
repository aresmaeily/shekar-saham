/**
 * menu_customizer.js - v0.9 - قابلیت تغییر نام منوها برای استفاده شخصی
 * کاربر گفت منوهای قبلی بهتره ولی امکان تغییر داشته باشه
 */

export class MenuCustomizer {
  constructor() {
    this.storageKey = "shekar_custom_menus";
    this.defaultMenus = null;
  }

  async loadDefaults() {
    try {
      const res = await fetch("/static/config/menus.json");
      const data = await res.json();
      this.defaultMenus = data.menus;
      return data.menus;
    } catch {
      // fallback to DOM
      const tabs = [...document.querySelectorAll("#mainTabs .tab")];
      return tabs.map(btn => ({
        id: btn.dataset.tab,
        label: btn.textContent.replace(/^[^\w\u0600-\u06FF]+/, "").trim(),
        icon: (btn.textContent.match(/^[^\w\u0600-\u06FF]+/) || [""])[0],
        original: btn.textContent.replace(/^[^\w\u0600-\u06FF]+/, "").trim()
      }));
    }
  }

  loadCustom() {
    try {
      const saved = localStorage.getItem(this.storageKey);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  }

  saveCustom(menus) {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(menus));
      return true;
    } catch {
      return false;
    }
  }

  async applyCustom() {
    const custom = this.loadCustom();
    if (!custom) return;
    
    custom.forEach(item => {
      const btn = document.querySelector(`#mainTabs .tab[data-tab="${item.id}"]`);
      if (btn && item.label) {
        btn.textContent = `${item.icon || ""} ${item.label}`.trim();
      }
    });
  }

  async renderEditor() {
    let container = document.getElementById("menuCustomizerEditor");
    if (!container) {
      container = document.createElement("div");
      container.id = "menuCustomizerEditor";
      container.className = "guide";
      container.style.marginTop = "1.5rem";
      
      const settingsPanel = document.getElementById("tab-settings");
      if (settingsPanel) {
        settingsPanel.appendChild(container);
      }
    }

    const defaults = await this.loadDefaults();
    const custom = this.loadCustom() || defaults;

    container.innerHTML = `
      <h3>🎨 شخصی‌سازی نام منوها - قابلیت درخواستی شما</h3>
      <p class="muted">اینجا می‌تونی نام هر منو رو به سلیقه خودت تغییر بدی. تغییرات فقط برای تو و در همین مرورگر ذخیره میشه (localStorage). هر وقت خواستی می‌تونی به حالت اولیه برگردونی.</p>
      <div class="settings-grid" id="menuEditGrid" style="margin-top:1rem">
        ${custom.map(item => `
          <div class="setting-card">
            <label>${item.icon || ""} ${item.original} (شناسه: ${item.id})</label>
            <input data-menu-id="${item.id}" data-field="label" class="text-input" value="${(item.label||"").replace(/"/g,'&quot;')}" placeholder="${item.original}" />
            <input data-menu-id="${item.id}" data-field="icon" class="text-input" style="margin-top:.4rem;width:60px" value="${(item.icon||"").replace(/"/g,'&quot;')}" placeholder="🎯" />
          </div>
        `).join("")}
      </div>
      <div class="filters" style="margin-top:1rem">
        <button class="btn primary" id="saveMenusBtn">💾 ذخیره نام‌های جدید</button>
        <button class="btn ghost" id="resetMenusBtn">↩️ بازگشت به قبلی‌ها (که گفتی بهترند)</button>
        <button class="btn ghost" id="exportMenusBtn">📋 خروجی JSON</button>
      </div>
      <p class="muted" id="menuCustomizerMsg" style="margin-top:.5rem"></p>
    `;

    container.querySelector("#saveMenusBtn").onclick = () => {
      const inputs = container.querySelectorAll("input[data-field='label']");
      const iconInputs = container.querySelectorAll("input[data-field='icon']");
      const newMenus = [];
      inputs.forEach(inp => {
        const id = inp.dataset.menuId;
        const iconInp = container.querySelector(`input[data-menu-id="${id}"][data-field="icon"]`);
        newMenus.push({
          id,
          label: inp.value.trim() || inp.placeholder,
          icon: iconInp ? iconInp.value.trim() : "",
          original: defaults.find(d => d.id === id)?.original || id
        });
      });
      this.saveCustom(newMenus);
      this.applyCustom();
      document.getElementById("menuCustomizerMsg").textContent = "✅ ذخیره شد - منوها با نام جدید اعمال شد. صفحه رو رفرش کن تا ببینی.";
    };

    container.querySelector("#resetMenusBtn").onclick = () => {
      localStorage.removeItem(this.storageKey);
      document.getElementById("menuCustomizerMsg").textContent = "✅ به حالت اولیه برگشت - همون قبلی‌ها که گفتی بهترند. صفحه رو رفرش کن.";
      setTimeout(() => location.reload(), 800);
    };

    container.querySelector("#exportMenusBtn").onclick = () => {
      const custom = this.loadCustom() || defaults;
      const json = JSON.stringify(custom, null, 2);
      navigator.clipboard?.writeText(json).then(() => {
        document.getElementById("menuCustomizerMsg").textContent = "📋 JSON کپی شد - می‌تونی به کسی بدی یا نگه داری";
      }).catch(() => {
        prompt("JSON منوها:", json);
      });
    };
  }
}

export const menuCustomizer = new MenuCustomizer();

// Auto apply on load
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    menuCustomizer.applyCustom();
    setTimeout(() => menuCustomizer.renderEditor(), 1500);
  });
} else {
  menuCustomizer.applyCustom();
  setTimeout(() => menuCustomizer.renderEditor(), 1500);
}

window.MenuCustomizer = MenuCustomizer;
window.menuCustomizer = menuCustomizer;
