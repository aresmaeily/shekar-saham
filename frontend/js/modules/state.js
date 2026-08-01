/**
 * modules/state.js - Centralized state management (Zustand-like simple)
 */
const createStore = (initial) => {
  let state = { ...initial };
  const listeners = new Set();
  
  return {
    get: () => state,
    set: (partial) => {
      state = { ...state, ...(typeof partial === "function" ? partial(state) : partial) };
      listeners.forEach(fn => fn(state));
    },
    subscribe: (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    }
  };
};

export const store = createStore({
  analysis: null,
  trustLevel: "mixed",
  auto: true,
  bigWindow: 600,
  confluence: null,
  bigMoves: [],
  // ... other state
});

export const TrustLevel = {
  SYNTHETIC: "synthetic",
  MIXED: "mixed",
  LIVE: "live"
};

export function isSynthetic(trust) {
  return String(trust).toLowerCase() === "synthetic";
}

export function shouldBlockNotify(trust, allowSynthetic) {
  return trust === "synthetic" && !allowSynthetic;
}
