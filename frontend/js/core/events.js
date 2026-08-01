/**
 * events.js — باس رویداد مرکزی
 * ارتباط بین لایه‌ها بدون وابستگی مستقیم (loose coupling).
 */
class EventBus {
  #listeners = new Map();

  on(type, fn) {
    if (!this.#listeners.has(type)) this.#listeners.set(type, new Set());
    this.#listeners.get(type).add(fn);
    return () => this.off(type, fn);
  }

  off(type, fn) {
    this.#listeners.get(type)?.delete(fn);
  }

  emit(type, payload) {
    this.#listeners.get(type)?.forEach((fn) => {
      try {
        fn(payload);
      } catch (e) {
        console.error(`[events] handler for "${type}" failed`, e);
      }
    });
  }
}

export const events = new EventBus();
