# MASTER-RADAR WAVE-S EXECUTION RECORD — UNIFIED MATRIX + WEBSITE/DESKTOP/CHARTING CLOSURE — 2026-11-07

Directive: MASTER DIRECTIVE — COMPLETE WEBSITE, DESKTOP APPLICATION, AND PRODUCT ROADMAP GAPS (2026-11-07). 17-role ownership map published pre-edit (chat record; roles and file boundaries as listed there — identified honestly as agent roles with independent review evidence, not human auditors). Baseline: `5e56dec` (origin/main == local 0/0; doc HEAD `6d78a842` + WAVE-H anchor `86f28c24` re-verified ancestors; battery 2991/1s/0f re-run). Parallel read-only audit agents (4): Windows/packaging forensics, Vercel/deployment forensics, chart-sync integration points, journey→endpoint inventory.

## §1 Implementation increments (published `9aad512`)

- **WAVE-S2 — cross-window crosshair/range sync (MR-B2-01 residual CLOSED):** chart_grid.js syncs visible range AND crosshair across popup windows over `radar.grid.sync.v1`; 3 NEW fail-closed validators (`pane_cross`/`pane_cross_clear`/`pane_range`; sender −1=primary; finite ordered bounds); dual echo guards; sync toggles govern cross-window too; pane→primary crosshair (was primary→panes only); values ALWAYS from local data — a missing time never mints a price. 9 static gates.
- **WAVE-S2W — Windows fixes (MR-I-01 residuals):** installer payload defect CLOSED (`frontend/` → `electron/resources/frontend` per config.py ROOT=parents[3]; previously the packaged app would 404 on `/`); CI payload-verification step fails on incomplete payload + records `frontend_files_bundled`; non-loopback URL override now ENFORCED (fallback to loopback; was log-only); window origin port-consistent with `RADAR_BACKEND_PORT`; degraded page names the exact one-time dependency command (zero-egress data: URL); `electron/package-lock.json` generated (runbook `npm ci` now executable); runbook drift fixed ×3 (+ venv/bootstrap disclosure making the WAVE-N record claim true). 6 static gates.
- Counter-pin discipline: sw v3-0-15→v3-0-16 + bumps ×7 files (pins only; two injection-damaged asserts repaired in-wave to FULL strength — audited, zero weakened). 1 recorded intent-preserving bump in `test_wda_electron_shell_gates.py`.
- **Battery: 3006/1s/0f = 2991+15 exact** (42–48s ×2 runs). node --check ×3 + workflow YAML valid.

## §2 Unified requirements matrix (canonical, current — 11 status classes)

| Req | Source | Status | Remaining work |
|---|---|---|---|
| MR-A1-0x universe/schema | base+audits | TESTED / INDEPENDENTLY-REPRODUCED | real catalog = R-3/R-7 owner |
| MR-A2-0x providers | base | OWNER-GATED (admission) | entitlement + Two-Key |
| MR-B1-0x timeframes/calendars | +WAVE-E | TESTED / INTEGRATION-VERIFIED (declared) | sourced holiday tables = R-3/R-7 |
| MR-B2-01 multi-chart + detach | +W3/B/S2 | **RUNTIME-VERIFIED (grid+popup sync incl. crosshair/range, WAVE-S2)** | OS placement not claimable (honest) |
| MR-B3-0x types/drawings/replay | +W2/W3 | TESTED / INTEGRATION-VERIFIED | — |
| MR-B4-0x indicators + UIDL-1 | +WAVE-B | INDEPENDENTLY-REPRODUCED | — |
| MR-B5-01 alerts on-demand | +W2 | INTEGRATION-VERIFIED | scheduled ops = R-6 (SCHEDULER_ENABLED=0) |
| MR-C1-02 AI-2 seam | +WAVE-K/L/O | OWNER-GATED (default AI2_ENABLED=0) + INTEGRATION-VERIFIED surface | owner activation act only |
| MR-C2/C3 DSL/sandbox/approval | base+audits | INDEPENDENTLY-REPRODUCED | — |
| MR-D1–D5 backtest/optimizer/walk-forward/exports | +W2/W3/D | TESTED–INDEPENDENTLY-REPRODUCED | tick fidelity NOT claimed (bar-based declared) |
| MR-E-01 paper forward | base | TESTED | LIVE observation = OWNER-GATED (deliberate) |
| MR-F-01 analyst | base | INDEPENDENTLY-REPRODUCED | fundamentals sources not admitted |
| MR-G-01 data quality + calendars UI | +W2/E | INTEGRATION-VERIFIED | — |
| MR-H-01/02 UX/palette | +W2/W3 | INTEGRATION-VERIFIED | — |
| MR-I-01 Electron/installer | +N/S2W | INTEGRATION-VERIFIED (repo-side) | target-machine install = R-1/R-2 |
| MR-I-02 embedded Python | **NEW (this wave)** | **PARTIAL — EVALUATED** | PSF license permits redistribution + checksum verification possible; implementation+CI test = next increment; nothing downloaded/executed repo-side |
| SITE-1 deployment | WAVE-A/WS1 | OWNER-GATED (Vercel = optional pipeline) | packet below; public deploy = owner |
| SITE-2 journeys E2E | WAVE-Q (AI-2 Studio DOM) | RUNTIME-VERIFIED (AI-2 tab) / PARTIAL (fleet) | full 12-journey browser run = next increment (journey→endpoint map ready, §audit) |
| OA-5 prediction registry | WAVE-J | INTEGRATION-VERIFIED | — |
| OA-8 completion % | — | NOT CALCULATED | owner weighting |

## §3 Vercel failure root-cause report + owner-ready deployment packet (§14.8)

**Root cause (recorded facts):** Vercel FAILURES on every push (deployments 7493431829/7485071086/7493297502, `Vercel` commit-status context) — the repo has NO `vercel.json`, no Vercel build config, and the product architecture is a same-origin FastAPI monolith serving the vanilla-JS frontend (api.js is relative-path-only, `credentials: same-origin`) deployed via Docker. Vercel auto-detection has no framework to build; the definitive build-log root cause is behind owner authentication (`npx vercel inspect dpl_2VVFjdpMaMvY23YbY2CJ2bxkuVQy --logs` → no credentials). **Classification: owner-connected OPTIONAL pipeline — empirically NOT a push gate (10+ pushes landed despite failures); the repo's required checks are the three Actions jobs (now 4 with installer).**

**Owner packet (exact actions):** (1) `npx vercel inspect dpl_2VVFjdpMaMvY23YbY2CJ2bxkuVQy --logs` with owner token → confirm the build error; (2) choose: **(a) disconnect** the vercel[bot] GitHub App (recommended — nothing in the product deploys through Vercel), or **(b) configure**: the only Vercel-compatible shape is static-frontend-only + separately hosted backend, which would break same-origin session/CSRF unless proxied — NOT recommended; the supported deployment model is the Docker/FastAPI monolith (docker-compose) on any VM host. (3) No domain is purchased/connected anywhere in the records — no domain action exists. No repository-side change is required or authorized (OA-6 preserved).

## §4 Owner-gated action register (delta vs WAVE-H)

Unchanged: OA-1 (target-machine install/upgrade/rollback R-1/R-2), OA-2 (real providers R-3/R-7), OA-3 (AI-2 production activation — committed default stays 0), OA-4 (scheduled operation — SCHEDULER_ENABLED=0), OA-6 (Vercel housekeeping — packet above), OA-8 (completion weighting). WAVE-Q/WAVE-S narrowed: AI-2 Studio DOM verification CLOSED; installer payload/first-run disclosure CLOSED; cross-window chart sync CLOSED.

## §5 Honest remaining work (next-wave entry points)

1. Full 12-journey browser E2E run + evidence (map ready: 31 tabs, endpoints inventoried; alert-ops dispatch/kill-switch UI absence is deliberate-safety, documented). 2. Embedded-Python bundling implementation + CI test (MR-I-02). 3. Independent 17-role audit report + clean-checkout reproduction at the published SHA. 4. Persian final report + English next-stage directive (§14.12). 5. CI-currency for the final docs-only commits (per the recorded batched-push convention). Global completion stays **NOT CALCULATED**.

## §6 Verification & publication

Battery ×2 (3006/1s/0f exact); forward-only push `5e56dec..9aad512` read-back verified; exact-SHA CI evidence appended to WS1 §17 at record time.
