/**
 * modules/api.js - Centralized API with error handling, rate limit, auth
 */

export function getApiKey() {
  return localStorage.getItem("shekar_api_key") || "";
}

export function setApiKey(key) {
  if (key) localStorage.setItem("shekar_api_key", key);
  else localStorage.removeItem("shekar_api_key");
}

export async function apiFetch(path, opts = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(opts.headers || {})
  };
  const apiKey = getApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  
  const res = await fetch(path, { ...opts, headers });
  
  if (res.status === 429) {
    const data = await res.json().catch(() => ({ detail: "Rate limit" }));
    showToast(data.detail, "error");
    throw new Error(data.detail);
  }
  if (res.status === 401) {
    const data = await res.json().catch(() => ({ detail: "Unauthorized" }));
    throw new Error(data.detail);
  }
  if (!res.ok) {
    const text = await res.text();
    try {
      const json = JSON.parse(text);
      throw new Error(json.detail || json.error || text);
    } catch (e) {
      if (e.message && !text.includes("{")) throw e;
      throw new Error(text);
    }
  }
  return res.json();
}

function showToast(msg, type = "info") {
  let existing = document.querySelector(".rate-limit-toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "rate-limit-toast";
  toast.style.borderColor = type === "error" ? "rgba(251,113,133,.5)" : "rgba(52,211,153,.5)";
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

export const Api = {
  health: () => apiFetch("/api/health"),
  analyze: (force = false) => apiFetch(`/api/analyze?force=${force}`),
  confluence: (force = false) => apiFetch(`/api/confluence?limit=80${force ? "&force=true" : ""}`),
  bigMoves: (windowSec = 600) => apiFetch(`/api/big-moves?window_sec=${windowSec}&limit=100`),
  filterRun: (expr, limit = 100) => apiFetch("/api/filter/run", { method: "POST", body: JSON.stringify({ expr, limit }) }),
  search: (q) => apiFetch(`/api/search?q=${encodeURIComponent(q)}`),
};
