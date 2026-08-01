/**
 * store.js — state مرکزی + pub/sub (منبع واحد حقیقت)
 * هیچ کامپوننتی state را مستقیم تغییر نمی‌دهد؛ همه از set/subscribe استفاده می‌کنند.
 */
export function createStore(initial = {}) {
  let state = { ...initial };
  const listeners = new Set();

  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...patch };
      listeners.forEach((fn) => fn(state));
      return state;
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    reset() {
      state = { ...initial };
      listeners.forEach((fn) => fn(state));
    },
  };
}

export const store = createStore({
  analysis: null,
  bigMoves: [],
  tablocastic: [],
  portfolio: [],
  alerts: [],
  marketMap: null,
  fundamentals: [],
  valueStocks: [],
  valueScoring: null,
  confluence: null,
  thresholds: null,
  filterPresets: [],
  filterFields: [],
  savedFilters: [],
  filterRows: [],
  backtest: null,
  options: null,
  notifyCfg: null,
  live: null,
  wsStatus: "connecting",
  trustLevel: "mixed",
  source: "…",
  bigWindow: 600,
  bigSide: "all",
  hotTier: "hot",
  hotView: "table",
  bigView: "table",
  tabloGrade: "all",
  finalAction: "all",
  auto: true,
});
