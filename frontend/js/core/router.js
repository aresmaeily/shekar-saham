/**
 * router.js — روتر تب‌ها (hash-based)
 * تب فعال از location.hash خوانده می‌شود: #/hot → قابل بوک‌مارک.
 * ثبت تب: register({id, render}) — render یک کامپوننت پنل را برمی‌گرداند.
 */
import { events } from "./events.js";

export class Router {
  #tabs = new Map();
  #current = null;
  #navEl = null;
  #pendingActivate = null;

  constructor(navSelector = "#mainTabs") {
    this.#navEl = document.querySelector(navSelector);
    window.addEventListener("hashchange", () => this.#apply());
  }

  /** ثبت تب + ساخت دکمه در ناوبری */
  register({ id, label, icon = "", render }) {
    this.#tabs.set(id, { id, label, icon, render });
    const btn = document.createElement("button");
    btn.className = "tab";
    btn.dataset.tab = id;
    btn.innerHTML = `${icon} ${label}`;
    btn.addEventListener("click", () => this.activate(id));
    this.#navEl?.appendChild(btn);
  }

  has(id) {
    return this.#tabs.has(id);
  }

  /** فعال‌سازی تب (کلیک / hash / لینک) */
  activate(id) {
    if (!this.#tabs.has(id)) return;
    if (location.hash !== `#/${id}`) {
      // setHash باعث hashchange → #apply می‌شود؛ با flag از رندر دوباره جلوگیری می‌کنیم
      this.#pendingActivate = id;
      location.hash = `#/${id}`;
      return;
    }
    this.#apply();
  }

  #apply() {
    const id = (location.hash || "").replace(/^#\/?/, "") || this.#firstTab();
    if (!this.#tabs.has(id)) {
      this.activate(this.#firstTab());
      return;
    }
    if (this.#pendingActivate === id) this.#pendingActivate = null;
    this.#current = id;

    // هایلایت ناوبری
    this.#navEl?.querySelectorAll(".tab").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === id);
    });
    // پنل‌ها
    document.querySelectorAll(".panel").forEach((p) => {
      p.classList.toggle("active", p.id === `tab-${id}`);
    });
    events.emit("tab:activated", id);
  }

  #firstTab() {
    return this.#tabs.keys().next().value || "";
  }

  get current() {
    return this.#current;
  }
}
