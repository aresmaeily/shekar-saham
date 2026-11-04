# WAVE-A EXECUTION RECORD — Repository Reconciliation, Site Startup, Right-Side Preview, Gap Matrix (2026-11-04)

Directive: MASTER DIRECTIVE — RADAR BOURSE "COMPLETE REMAINING ROADMAP" (2026-11-04, §1–§12).
Wave scope: §11 WAVE-A — repository and roadmap reconciliation, actual site startup, right-side preview, updated gap matrix. Baseline for all subsequent waves (B–H).

---

## 1. Repository reconciliation (directive §2)

| Item | Value |
|---|---|
| Remote `origin/main` after fetch | `29a63cbe4b98567e1a050ac9e212ebc1df60e5f7` (matches the directive's observed publication record — NOT assumed, re-fetched) |
| Local `main` | same SHA; `git rev-list --left-right --count main...origin/main` = `0 0`; `origin/main` IS ancestor of local main |
| HEAD commit SHA | `29a63cbe4b98567e1a050ac9e212ebc1df60e5f7` |
| Tree SHA | `60b723c19588ee19404c1d68fd2d82678723bc91` |
| Branch tracking | `main` tracks `origin/main`; after fetch, 0 ahead / 0 behind |
| Clean/dirty state | tracked files CLEAN; 6 deliberately-untracked non-wave governance artifacts preserved exactly as WAVE-3 left them: `.claude/`, `CLAUDE.md`, `docs/governance/PROJECT_EXECUTION_STATE.md`, `docs/governance/evidence/`, `scripts/r13_owner_repo_setup.sh`, `scripts/validate_bootstrap_config.py` (excluded from the WAVE-3 commit boundary by the recorded decision; NOT touched this wave) |
| Force push / history rewrite | none; forward-only chain `d7b2df8 → 11e1d4e → 9e10ded → 29a63cb` intact |

Canonical documents re-read this wave: `docs/STATUS.md` (head), `docs/CHANGELOG.md` (tail), `docs/active/INDEX.md`, `docs/active/MASTER_RADAR_REQUIREMENTS_MATRIX_2026-11-04.md` (full, including WAVE-2 and WAVE-3 addenda), `docs/active/MASTER_RADAR_EXECUTION_RECORD_2026-11-04.md`, `docs/active/MASTER_RADAR_WAVE2_EXECUTION_RECORD_2026-11-04.md`, `docs/active/MASTER_RADAR_WAVE3_EXECUTION_RECORD_2026-11-04.md`, `docs/active/ROADMAP_TRACEABILITY_DELTA_2026-11-03.md`, `docs/active/AI_RUNTIME_CONNECTIVITY_MATRIX_2026-11-02.md`, amendment sources `docs/governance/amendment_sources_2026-10-02/` (listing), decision register and governance boundaries via STATUS gates block.

## 2. Baseline battery (re-established in THIS checkout, not inherited)

`cd backend && python3 -m pytest tests -q -p no:cacheprovider`

**Result: 2625 passed / 1 skipped / 0 failed in 26.59s — exact match with the WAVE-3 record (2500 + 125 = 2625).** The single skip is the recorded env-conditional G2 substantive-rejection self-skip (docs-only parent delta), unchanged.

## 3. Mandatory right-side website preview (directive §3) — DONE, with evidence

### 3.1 What runs

1. **The real application**: FastAPI backend started with the repository's documented run configuration (`start.sh` semantics: `PYTHONPATH=backend`, `DATA_SOURCE=auto`, uvicorn `app.main:app`), host `127.0.0.1:8000`, `--no-proxy-headers` (TRUST_PROXY=0 default). Startup log line: `Starting رادار بورس v3.0.0 | data_source=auto | auth=False | phase=7-excellent | tz=Asia/Tehran`. Startup-to-serving latency ~35 s (seeding/initialization). Ephemeral FERNET_KEY CRITICAL warning emitted — expected for a non-production local run, recorded honestly.
2. **The environment's preview transport**: the development environment's right-side Preview panel can only render its own Next.js origin (port 3000). A **transparent verbatim proxy** (`src/app/[[...path]]/route.ts`, ~100 lines, in the sandbox workspace OUTSIDE the audited repository) forwards EVERY method/path/query/body/header unchanged to `127.0.0.1:8000`. It adds nothing, rewrites nothing, fabricates nothing. The repository itself is NOT modified by the preview wiring.

### 3.2 Verification evidence (all performed this session)

| Check (directive §3.6–3.7) | Result |
|---|---|
| Page loads | `GET /` → 200, 79,660 bytes (real `frontend/index.html` served by FastAPI); title «رادار بورس v3.0 | تابلوخوانی هوشمند» |
| Assets resolve | `/static/js/main.js` → 200 (16,999 B) via preview origin; `/static/css/*` 200 |
| API reaches intended backend | in-browser network log: `/api/auth/status` 200, `/api/health` 200, `/api/alerts/inbox` 200, `/api/analyze?force=true` 200, `/api/tablocastic?limit=120` 200, `/api/portfolio` 200, `/api/alerts/ops/status` 200 — all through the preview origin, served by the real backend |
| Console fatal errors | **0 page errors, 0 console error/fatal lines** (agent-browser `errors` + `console` sweep) |
| RTL / Persian layout | `document.documentElement.dir = "rtl"`, `lang = "fa"`, h1 «رادار بورس v3.0.0» |
| Main navigation | **29 tabs** enumerated live-DOM (`data-tab` registry), count matches the WAVE-3 validator pin (29/29) |
| Golden-path interactivity | Chart Pro tab activated → canvas rendered, crosshair readout container present, `/api/v10/chartpro/فملی?timeframe=1m&limit=500` → 200, `/api/v10/chartpro/فملی/indicators?…` → 200; derived chart-type controls (کندل/خط/ناحیه/هایلایت/رنکو/کاگی/PnF/لین بریکینگ) present in the served UI |
| Honest trust disclosure | app banner: `[source=mock_fallback] … MOCK data: development/demo fallback, not validated live market data … Provider status: testmode`; chart trust chips `منبع: MOCK (دمو) · synthetic-seeded`, `کلاس بازار: SYNTHETIC · روش: NATIVE`; `/api/v10/dataquality/markets` reports `trust_class: SYNTHETIC` and the `EXCLUDED_US_EQUITY` exclusion market — **R-3 intact, no live provider, no synthetic-as-real misclassification** |
| Screenshot | `download/wave_a_preview_chartpro.png` (in-chat workspace evidence copy) |
| WS badge | shows «قطع» (disconnected) — honest runtime status display in synthetic mode; NOT a console error; no scheduler/no live feed exists by governance (R-6/R-3) |

### 3.3 Preview URL and manual action (directive §3.9–3.10)

- **The site IS open in the right-side Preview panel** of this development environment (it renders the preview origin on port 3000, which now serves the real RADAR BOURSE app via the verbatim proxy). "Open in New Tab" above the panel opens the same verified site externally.
- Exact internal endpoints: app `http://127.0.0.1:8000/` (real FastAPI), preview origin `http://127.0.0.1:3000/` (transparent transport). The externally reachable URL is assigned by the platform and exposed through the panel — no unverified Vercel deployment URL is used anywhere.
- Startup commands (reproducible):
  - backend: `cd repo && PYTHONPATH=backend DATA_SOURCE=auto python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers` (equivalent to `bash start.sh` with HOST/PORT defaults; backgrounded with `setsid nohup` for session persistence)
  - preview transport (sandbox workspace, not the repo): `bun run dev` (environment-managed on port 3000)
- Limitation stated explicitly per §3.10: the Preview panel renders this environment's own origin; the real app's bytes reach it through the verbatim proxy described above. The repository code under audit is untouched by this wiring.

## 4. Vercel failure — investigated separately, NOT misclassified (directive §3)

- Recorded prior facts re-verified: Vercel posts a commit **status** (context `Vercel`), not an Actions check run; deployment `dpl_2VVFjdpMaMvY23YbY2CJ2bxkuVQy` on SHA `47183c0…` (and recurring `dpl_H4FD5RWeJrtwFUsM9P8CGifr1vU7`) = **FAILURE**; recurring "since before this program"; classified owner-connected **optional** pipeline; **no `vercel.json`, no Vercel workflow, no release-policy reference exists in the repo** (re-checked this wave: `ls vercel.json` → absent; grep of STATUS/CHANGELOG confirms classification); 10+ direct pushes landed despite the failure → empirically not a push gate.
- New investigation step this wave: `npx vercel inspect dpl_2VVFjdpMaMvY23YbY2CJ2bxkuVQy --logs` attempted from the sandbox → `Error: No existing credentials found. Please run vercel login or pass "--token"`. **The build-failure root cause lives in Vercel's authenticated build logs; no Vercel token exists in the sandbox and none may be invented.** Deeper root-cause determination requires an owner-side action (owner runs the CLI with their token, or grants a scoped read token). Recorded in the owner-action register as `OWNER-ACTION VERCEL-HOUSEKEEPING` (already listed in the owner packet as a housekeeping item).

## 5. Requirements-matrix reconciliation (directive §2.5–2.6)

Reconciliation performed row-by-row across the base matrix (§A–§N rows) and the WAVE-2 and WAVE-3 addenda of `MASTER_RADAR_REQUIREMENTS_MATRIX_2026-11-04.md`. **No base row was found stale relative to a later addendum**: each addendum row either closes a residual or re-affirms it, and the matrix's own addendum sections carry the current effective status. Column mapping to the directive's 13-field matrix (§2.6): `Implementation` = current implementation path; `Runtime caller` = actual runtime caller; `Data dependency` = dependency + trust class (SYNTHETIC/seeded everywhere; REAL_VERIFIED intentionally absent and labeled so); `Tests` = tests AND results (battery-counted per wave); `Evidence` = integration + independent-reproduction pointers (AUDIT-MR2/MR3 §B reproductions, hand-computed fixtures); `Owner gate` = owner decision/gate; `Remaining work` = exact remaining work; `Status` = final status. Operational-evidence status is asserted ONLY where a real runtime caller was exercised (preview session this wave = first in-browser operational evidence for the 29-tab UI + chartpro API surface through a real browser, recorded in §3.2).

Effective remaining gap list driving WAVE-B..H (non-owner-gated unless stated):

| # | Gap | Matrix row | Wave |
|---|---|---|---|
| 1 | User-authored indicator DSL (validation, sandboxing, install/remove, chart attachment) beyond RSL-1 strategy DSL | MR-B4-01 residual (NOT-IMPLEMENTED) | **WAVE-B** |
| 2 | Detachable panels (web/Electron-popup class; OS multi-monitor placement NOT claimable) | MR-B2-01 residual (NOT-IMPLEMENTED) | WAVE-B |
| 3 | PDF export of backtest/optimization/walk-forward reports (CSV/JSON already delivered) | MR-D5-01 residual | WAVE-D |
| 4 | Declared session/calendar model for supported markets with honest `DECLARED` trust class (real sourced holiday tables stay owner-gated R-3/R-7) | MR-B1-01 residual | WAVE-E |
| 5 | AI Studio steps 1–3 (NL→clarification→spec→codegen) remain a disconnected owner-gated seam (AI2_ENABLED=0) — WAVE-C prepares evidence only, no runtime caller added | MR-C1-02 (OWNER-GATED) | WAVE-C |
| 6 | Five product loops: audit effective status vs §5, close closable residuals, no scheduler/egress (R-6/R-9) | §5 loops | WAVE-F |
| 7 | Windows repository-side packaging readiness (electron-builder NSIS config exists; build reproducibility runbook, upgrade/rollback docs, signing-readiness WITHOUT signing claims) | MR-I-01 residual | WAVE-G |
| 8 | Owner-gated (NOT worked around): INSTALL R-1, target-machine R-2, live posture R-3, Vercel housekeeping, AI enablement, persistent approval log | R-1..R-11 | WAVE-H package |

## 6. Gates and governance (unchanged, re-verified this wave)

`AI2_ENABLED=0` (`config.py:111`), `verified=False` (`config.py:284`), `SYNTHETIC_OR_PAPER` (g2_gate), kill switches ENGAGED, no scheduler, no external egress, no live data path, no runtime caller added to any disconnected edge, no purge path, INSTALL NOT ISSUED, D1–D7/R-1..R-11 in force. The preview transport contains NO application code and NO governance-relevant behavior; the repository diff this wave is docs-only (this record + matrix addendum + STATUS/CHANGELOG/INDEX currency).

## 7. Publications

Forward-only, exact-SHA CI evidence appended post-push per the established WS1 §13 discipline. See the WAVE-A publication note appended to this record after the push completes.
