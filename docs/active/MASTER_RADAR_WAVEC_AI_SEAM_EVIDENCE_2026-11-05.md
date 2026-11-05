# MASTER-RADAR WAVE-C — AI Studio Governed Generation Path: Seam Evidence Package

Date: 2026-11-05 · Baseline SHA: `446be3560a599c1151e301b178c3f697793d6e68` (origin/main, re-fetched this session) ·
Requirement: **MR-C1-02 (OWNER-GATED)** · Wave scope: §11 WAVE-C — evidence package only, **no runtime caller added**.

---

## 1. Scope and honesty frame

The directive (§4.4) requires the AI Indicator & Strategy Studio governed generation pipeline:
natural-language → clarification → structured spec → constrained DSL → parsing/static validation →
sandboxed testing → deterministic evaluation → backtest → forward/paper → report → explicit human
approval → versioned promotion.

What is implemented and operating today (verified live this session): **steps 4–10** — the governed
pipeline from user-authored RSL-1 source through validation, spec, backtest, paper replay, versioning
and the approval state machine. What is NOT implemented and stays disconnected (owner-gated):
**steps 1–3** — the AI generation seam (NL → clarification → spec → codegen producing RSL-1 source).

This wave adds **evidence only**: it does not add any runtime caller, any API route, any frontend call,
and does not touch any gate. `AI2_ENABLED=0` unchanged; `verified=False` posture unchanged;
`SYNTHETIC_OR_PAPER` unchanged. Global completion remains **NOT CALCULATED** (no approved
weighted model).

## 2. Static disconnection proof (collected this session against the live runtime and the working tree)

| # | Check | Method | Result |
|---|---|---|---|
| 2.1 | No AI-proposal endpoint on the live API surface | `GET /openapi.json` (live uvicorn, 124 paths), filter for proposal/ai-generate/nl/codegen | Only `/api/ai/filter-proposals*` matches — the pre-existing **deterministic filter-intelligence** feature (routes.py:683/696), which is a different, already-governed product surface, NOT the AI Studio NL→spec→codegen seam. No strategy-proposal path exists. |
| 2.2 | No route imports the AI services | `grep -rn "ai2_service\|ai2_research" backend/app/api/` | **NONE** — zero API-route references to AI-2 modules. |
| 2.3 | Frontend has no NL strategy input and no AI generation call | `grep` over `frontend/js/` for proposal/generate/NL targeting the strategy lab | `strategy_lab.js` sends **user-authored source only** (`$("slDslSource").value`) to `/validate`, `/spec`, `/backtest`, `/paper-replay`, `/versions/*`. No textarea for natural language, no fetch to any generation endpoint. |
| 2.4 | The seam is labelled disconnected at the API contract level | `backend/app/api/strategy_lab.py` lines 11–12 and 255 | "the AI-proposal seam (NL -> spec -> code) is owner-gated (AI2_ENABLED=0, verified=False) and DISCONNECTED. The user authors RSL-1 source directly." Every spec response carries `"generated_by": "user-authored RSL source; AI-proposal seam owner-gated and disconnected"`. |
| 2.5 | AI-2 service exposes no HTTP route by construction | `backend/app/services/ai2_service.py` module contract (lines 42–43) | "No HTTP route is exposed for AI-2: the owner-facing surface for AI-2 is defined in the NOT_SYNCED amendments and must not be invented here." |

## 3. Gate triple integrity (all three independent gates verified in the working tree at `446be35`)

| Gate | Evidence | Status |
|---|---|---|
| 1. LIVE gate | `config.py:156-166` `is_verified_live()` requires `live_verified is True`; `build_data_trust_context()` (config.py:248–252): "No caller — including tests — can mint verified LIVE through this function." | **ENGAGED — structurally unreachable** |
| 2. Config gate | `config.py:111` `ai2_enabled: bool = _env_bool("AI2_ENABLED", "0")` — default off; no `.env` in the repo sets it on (repo `.env` is untracked local, `AI2_ENABLED` not present) | **ENGAGED** |
| 3. Data-trust fail-closed | `ai2_service.py` refuses missing/`unavailable` market data before any provider invocation | **ENGAGED** |

Additional governance constants re-verified this session: no scheduler activation anywhere on the AI
path (R-6), no external notification egress (R-9), no broker/live-trading path, no purge path, Two-Key
Rule intact for any external-intelligence admission. **Gate sweep: config.py byte-diff zero** (no gate
changed by this wave).

## 4. Governed steps 4–10 readiness — live functional demonstration (synthetic data only, this session)

Executed against the real running backend (uvicorn `app.main:app`, `DATA_SOURCE=auto`, trust state
`mock`/`synthetic` throughout):

| Step | Endpoint | Live result |
|---|---|---|
| Validation | `POST /api/v10/strategylab/validate` | `ok: true`, zero errors; hostile input (`INDICATOR demo_spec…`) correctly refused with typed `PARSE_UNEXPECTED_TOKEN` (422, line/col, machine-readable) |
| Versioned spec | `POST /api/v10/strategylab/spec` | `ok: true`, `spec_version: RSL-1.0.0`, `digest: 63ae677e…167569`, inputs/risk/expressions captured, `generated_by` = user-authored + seam-disconnected label |
| Deterministic backtest | `POST /api/v10/strategylab/backtest` | HTTP 200, `engine_version: BT-PRODUCT-1.0.0`, `result_digest: 0f1ae1c0…5ababf`, 37 trades, full metric report (Sharpe 0.333, Sortino 0.487, profit factor 1.166, max DD 6.64%, win rate 48.65%) over 200 synthetic bars |
| Paper forward replay | `POST /api/v10/strategylab/paper-replay` | HTTP 200, `mode: PAPER_REPLAY_OVER_SYNTHETIC_WINDOW`, `not_live_note` present, ledger integrity `ledger_chain_ok`, `summary_digest`, `trust_envelope` |
| Version promotion surface | `/versions` + `/versions/{id}/promote` | wired in the frontend and exercised by the test battery; in-memory registry — persistence stays an owner decision (recorded §C3) |

Interpretation: **everything downstream of AI generation is operational and governed**. When the owner
enables the seam, generated candidates will flow into this exact existing chain — they will not create a
parallel path.

## 5. Interface contract for the future AI proposal path (what the owner-gated seam MUST implement when enabled)

Fixed now so the future implementation cannot bypass governance:

1. **Input**: natural-language description + clarification answers (bounded; typed schema).
2. **Output**: RSL-1 source text ONLY — the same grammar the user writes by hand. No side-channel
   execution, no direct metric access, no dynamic imports.
3. **Mandatory flow**: generated source enters the SAME `POST /spec → /validate → (sandbox) →
   /backtest → /paper-replay → report → explicit human approval → versioned promotion` chain.
   No new evaluation path may be added.
4. **Provenance**: every artifact produced from a generated source must carry `generated_by` =
   AI-proposal provenance (distinguishable from user-authored), the source digest, and the seam
   configuration fingerprint — so backtest/forward reports never blend the two origins.
5. **Status semantics**: a generated strategy is `SYNTHETIC_OR_PAPER` and `verified=False` until an
   explicit human approval AND the owner enablement decision exist. The approval state machine
   (§C3) is the ONLY promotion authority; autonomous promotion is forbidden (R-8).
6. **Budgets and refusal**: NL length, clarification rounds, codegen output size and validation
   attempts are bounded; failures are fail-closed typed errors, never silent fallbacks.

## 6. Owner decision brief (what changes / what stays blocked if the owner enables the seam)

| On owner AI enablement | Effect |
|---|---|
| Steps 1–3 become implementable | NL → clarification → spec → codegen component may be built and wired into `/spec` as an alternative source author |
| What does NOT unlock | live trading (R-3), broker egress, scheduler activation (R-6), autonomous promotion (R-8), external notification (R-9), live-verified data (independent provider-verification boundary + G2 + owner acceptance), any Two-Key-Rule external-intelligence admission |
| Required companion decisions | persistence decision for the version registry; retention policy for generated candidates; audit-log scope for generation events |
| Owner actions already registered | AI enablement (existing register entry), AI-2 authoritative procedure sync (NOT_SYNCED corpus), Vercel housekeeping, INSTALL R-1/R-2 target-machine authorization |

## 7. Honest status after WAVE-C

| Item | Status |
|---|---|
| MR-C1-02 (AI Studio steps 1–3 as live path) | **OWNER-GATED / NOT-IMPLEMENTED** — unchanged by design; evidence package delivered |
| Governed steps 4–10 (user-authored path) | **OPERATIONALLY VERIFIED** this session on the live runtime (synthetic data) |
| Runtime caller added to the seam | **NONE** (static proof §2) |
| Gates | **UNCHANGED** — AI2_ENABLED=0, verified=False, SYNTHETIC_OR_PAPER, config byte-diff zero |
| Code delta of this wave | **zero** (docs/evidence only) |
| Global completion | **NOT CALCULATED** (no approved weighted model) |

---

## Appendix A — Session continuity facts (2026-11-05, this session)

1. **Repository re-sync**: local working clone had been snapshotted at `29a63cb…`; re-fetched origin/main = `446be35…`; fast-forwarded (forward-only, no history rewrite, no force push). The 6 deliberately-untracked governance artifacts (`.claude/`, `CLAUDE.md`, `docs/governance/PROJECT_EXECUTION_STATE.md`, `docs/governance/evidence/`, `scripts/r13_owner_repo_setup.sh`, `scripts/validate_bootstrap_config.py`) preserved untouched, same disposition as WAVE-3/WAVE-A.
2. **Baseline battery re-established in THIS checkout**: `cd backend && python3 -m pytest tests -q -p no:cacheprovider` → **2741 passed / 1 skipped / 0 failed in 27.89s** — total 2742 exactly matches the WAVE-B record (2740+2). Delta honesty: one env-conditional skip (the recorded G2-harness conditional class) transitions to PASS in this environment's configuration; zero test files changed; zero failures.
3. **Mandatory site preview re-established** (the sandbox recycled the previous session's preview transport, which by design lives OUTSIDE the repo): a fresh transparent verbatim proxy (Next.js `src/app/[[...path]]/route.ts` in the sandbox workspace, forwarding every method/path/query/body header unchanged to 127.0.0.1:8000; adds nothing, rewrites nothing; repository untouched) + a keepalive supervisor (double-fork daemonized, also outside the repo) holding both the real backend (uvicorn :8000, documented run config, DATA_SOURCE=auto) and the preview origin (:3000).
4. **Preview-origin verification evidence (browser, fresh session, cleared storage)**: title «رادار بورس v3.0 | تابلوخوانی هوشمند»; `dir=rtl`/`lang=fa`; **29 tabs**; ALL static assets same-origin via the preview origin (css/lightweight-charts/main.js/fonts/manifest 200); **zero** direct :8000 requests from the page; zero page errors / zero console errors; Chart Pro golden path → activeTab «چارت حرفه‌ای», 9 canvases, `/api/v10/chartpro/universe` 200 with honest `data_trust {state: mock, trust_level: synthetic, source: mock_fallback}`; trust chips «اعتماد: MOCK - داده آزمایشی», «کلاس بازار: SYNTHETIC · روش: NATIVE», banner "MOCK data: development/demo fallback, not validated live market data" — R-3 intact, no synthetic-as-real misclassification.
5. **Startup commands (reproducible)**: backend `cd RADAR_BOURSE/repo/backend && PYTHONPATH=$PWD DATA_SOURCE=auto python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers`; preview transport `cd <sandbox-workspace> && bun run dev` (port 3000). The externally reachable URL is assigned by the platform through the preview panel; no unverified Vercel URL is used anywhere.
6. **Environment limitation stated explicitly**: sandbox processes do not deterministically survive between tool-call messages; the keepalive supervisor mitigates this within a session, and the commands above re-establish both services deterministically. The preview panel renders the platform preview origin (:3000) which serves the REAL application bytes through the verbatim proxy — the repository under audit is untouched by this wiring.
