# P3.43 — CONTROLLED ALPHA LAUNCH: INSTALL CHECKLIST (consolidated)

Status line: **NOT STARTED — awaiting the owner `INSTALL` instruction.**
Created: 2026-11-02 (MA-1 consolidated multi-agent cycle, WS-11).
This checklist CONSOLIDATES; it does not replace the detailed documents it
cross-references. Nothing on this page is executed until the owner says
`INSTALL`.

---

## 0. Binding red line (verbatim rule)

> A green `windows-validation` CI job is NOT proof of successful installation
> on the owner's target computer.

CI evidence (all three required jobs green on `7c72f3d59d47435b53d83dad40a759d69377bca8`,
GOV-49; docs-only `4215ed4` published 2026-11-02 with CI re-verification
pending read-back at publication time) proves the repository builds, boots,
and passes its E2E suite on a **GitHub-hosted runner**. The canonical P3.43
acceptance conditions are target-machine facts (see `e2e/README.md`, which
states a container/dev/CI run does not satisfy the canonical P3.43-2
acceptance condition).

## 1. Pre-install (repo state — verified 2026-11-02)

| # | Item | Source | State |
|---|------|--------|-------|
| 1.1 | `main` published & CI-green | GOV-48/49 records; `git ls-remote origin main` | DONE (re-verify at install time) |
| 1.2 | App version pinned `3.0.0` | `backend/app/core/config.py:28`; `electron/package.json`; `frontend/manifest.json` | DONE |
| 1.3 | Windows install scripts present | `scripts/windows/{validate_install,install,start,validate_alpha}.ps1` | DONE |
| 1.4 | Desktop shell present | `electron/main.js` (origin allow-list, contextIsolation), `electron/icon.ico` (real ICO, 7 layers) | DONE |
| 1.5 | Docker path | `Dockerfile` (python:3.13-slim, non-root, HEALTHCHECK) + `docker-compose.yml` (fail-closed private mode) | DONE |
| 1.6 | `.env` contract | `.env.example`; mandatory keys table in `docs/active/INSTALL_GUIDE.md` | DONE (values are owner out-of-band inputs) |
| 1.7 | Owner `INSTALL` instruction | owner-only | **NOT ISSUED — hard gate** |

## 2. Target-machine install sequence (owner environment)

Follow `docs/active/ALPHA_INSTALLATION_RUNBOOK.md` (14 sections) with
`docs/active/ALPHA_INSTALLATION_CHECKLIST.md` open for row-by-row recording:

1. `scripts/windows/validate_install.ps1` — preconditions (Python, ports, paths).
2. `scripts/windows/install.ps1` — venv + dependencies + config.
3. `scripts/windows/start.ps1` — boot backend (uvicorn 127.0.0.1:8000).
4. Health gate: `GET /api/health` 200 + `version` field == `3.0.0`.
5. `scripts/windows/validate_alpha.ps1` — full local validation battery.
6. Browser E2E on the target browser (canonical P3.43-2): `e2e/` suite
   against the locally booted app (Playwright + chromium on Windows).
7. Electron interactive checks W2-icon / W3–W5 shell navigation (from
   `windows.yml` header — NOT automatable in CI; owner-runbook items).
8. Fill `docs/active/ALPHA_TARGET_VALIDATION_CHECKLIST.md` (26-row matrix).

## 3. Data-trust gates at install time (unchanged, fail-closed)

- `AI2_ENABLED=0`, `verified=False`, `execution_mode=SYNTHETIC_OR_PAPER` are
  the release posture (GOV-41 owner decisions; OA-AI2-LIVE-CREDENTIALS /
  OA-AI2-ENABLEMENT DENIED FOR CURRENT RELEASE — CLOSED).
- `windows_health.json` and W7 assert `live_verified != true` without owner
  credentials; the UI renders "UNVERIFIED LIVE-CLASS" for live-class sources.
- TSETMC reachability may be validated on the target; a successful fetch
  still yields `trust_level=mixed` until an owner-recorded verification act.

## 4. Backup / rollback at launch

- Backups: `Store.backup(keep=7)` → `data/backups/shekar-<timestamp>.db`
  (WAL-consistent). Procedure: `docs/active/BACKUP_RESTORE_RUNBOOK.md`.
- Rollback: `ALPHA_INSTALLATION_RUNBOOK.md §13`; restore runbook §4 below.

## 5. Exit criteria (all must be true, in the owner's records)

1. Owner `INSTALL` instruction issued (dated).
2. Target-machine install + start + health == `3.0.0` evidenced.
3. Target-browser E2E suite green on the target machine.
4. Electron shell navigation + icon rendering verified interactively.
5. Data-trust posture confirmed (no false-LIVE; synthetic/paper labels).
6. Backup taken and restore rehearsed (or explicitly deferred with reason).
7. Launch decision recorded: ALPHA READY / ALPHA READY WITH CONDITIONS /
   BLOCKED (per `P3.34_ALPHA_TARGET_VALIDATION_AND_LAUNCH_CHECKLIST.md §23`).

## 6. What this checklist does NOT cover

- Real-provider enablement (owner-denied for the current release; re-proposal
  requires a new dated owner act).
- Any production-trading, auto-promotion, or AI-2 real-data capability — none
  exists in this release by governance.
