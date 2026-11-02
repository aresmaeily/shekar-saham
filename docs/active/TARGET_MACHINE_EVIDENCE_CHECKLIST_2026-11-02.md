# TARGET-MACHINE EVIDENCE CHECKLIST — 2026-11-02 (WS-8, installation readiness)

Directive item WS-8: keep repository/CI validation SEPARATE from
target-machine installation; prepare a complete target-machine evidence
checklist (Windows prerequisites, installation steps, version verification,
service startup and health checks, database initialization, backup/restore,
Electron/UI checks, rollback, evidence capture). **No installation is
complete, deferred, or claimed without dated target-machine evidence or a
dated owner-approved deferral.** The owner `INSTALL` instruction (R-1) is a
HARD GATE and remains NOT ISSUED (`P343_INSTALL_CHECKLIST.md:3,34`).

Principle carried over: **CI green ≠ install** (P3.43). The windows-validation
workflow (3/3 green on `47183c0…`, including first-ever real Windows W6 E2E
7/7) proves the application layer on a HOSTED runner — it is evidence FOR,
never a substitute for, the owner machine.

How to use: execute in order; for every row record command, observed output,
timestamp, and (where indicated) attach the artifact to the evidence bundle.
A row is DONE only with captured evidence; N/A needs a one-line reason.

## Phase 0 — Prerequisites (Windows)

| # | Check | Command / artifact | Exit criterion |
|---|---|---|---|
| 0.1 | Windows version + arch | `systeminfo` / `Get-ComputerInfo` | supported per runbook; record build |
| 0.2 | Python 3.13 present | `python --version` | 3.13.x (same major as CI/Docker: C-12 alignment) |
| 0.3 | Node.js present (Electron) | `node --version` | per runbook |
| 0.4 | Git present | `git --version` | any current |
| 0.5 | Disk + AV exclusions noted | dir listing of target install root | space ≥ runbook minimum; exclusions documented |
| 0.6 | PowerShell version | `$PSVersionTable.PSVersion` | 5.1+ / pwsh 7+ recorded |

## Phase 1 — Installation (owner INSTALL instruction dated R-1 required first)

| # | Step | Command / artifact | Exit criterion |
|---|---|---|---|
| 1.1 | Precondition validator | `scripts/windows/validate_install.ps1` | `OK: True`, exit 0 |
| 1.2 | Install | `scripts/windows/install.ps1` | venv + `requirements.txt` installed + `.env` created from `.env.example`; exit 0 |
| 1.3 | Owner secrets (owner act) | edit `.env` — persistent `FERNET_KEY`, `API_KEY` if private mode | file saved; `validate_install.ps1:57-64` reports SET without printing values |
| 1.4 | PowerShell syntax gate evidence | the CI gate ("PowerShell script syntax gate (W2-INST F3)") + local `Parser]::ParseFile` run | all 4 shipped scripts parse clean (record output) |
| 1.5 | Version identity pre-check | `git rev-parse HEAD` of the installed tree | equals the reviewed commit (`47183c0…` or the owner-chosen SHA) |

## Phase 2 — Version verification (chain 3.0.0, byte-level)

| # | Node | Check | Exit criterion |
|---|---|---|---|
| 2.1 | Backend settings | `backend/app/core/config.py:28` | `"3.0.0"` |
| 2.2 | Electron | `electron/package.json:3` | `"3.0.0"` |
| 2.3 | PWA manifest | `frontend/manifest.json:34` | `"3.0.0"` |
| 2.4 | Served | `/api/health` → `version` | `3.0.0` (bytes match 2.1–2.3) |

## Phase 3 — Service startup + health (loopback)

| # | Check | Command / artifact | Exit criterion |
|---|---|---|---|
| 3.1 | Start (loopback) | `scripts/windows/start.ps1 -HostAddress 127.0.0.1` | "Uvicorn running" in log; NO ephemeral-key CRITICAL (persistent key set); pid file written |
| 3.2 | Health | `GET http://127.0.0.1:8000/api/health` | 200; `ok==true`; `version=="3.0.0"`; `live_verified==false`; `data_trust.live_verified==false` |
| 3.3 | Status | `GET /api/status` | 200; `trust_level=="synthetic"` with mock source; redaction posture per mode |
| 3.4 | Live posture (red line) | `/api/live/status` | 200; `verified==false`; no live trading anywhere |
| 3.5 | Availability battery | `scripts/windows/validate_alpha.ps1` | `ok=true`, exit 0 |
| 3.6 | Canonical target E2E (P3.43-2) | `RADAR_E2E_BASE_URL=http://127.0.0.1:8000 python -m pytest e2e -q` | **7/7 passed ON THE TARGET MACHINE** (CI/containers = test-of-the-suite only) |
| 3.7 | Gates observed at runtime | boot log + health payload | `AI2_ENABLED` unset/0; no ai2 route; kill switches ENGAGED rows present in store |

## Phase 4 — Database initialization

| # | Check | Command / artifact | Exit criterion |
|---|---|---|---|
| 4.1 | Fresh DB created | `data/shekar.db` exists after first boot | created; `PRAGMA user_version` == 1 |
| 4.2 | Schema inventory | `sqlite3 data/shekar.db ".tables"` | 17 tables incl. the 7 namespaced `alert_ops_*` |
| 4.3 | Integrity | `PRAGMA integrity_check;` | `ok` |
| 4.4 | No unexpected DELETE paths | schema + code review pointer | retention deletes = exactly the 4 namespaced `alert_ops_*` paths (standing purge boundary) |

## Phase 5 — Backup & restore drill

| # | Check | Command / artifact | Exit criterion |
|---|---|---|---|
| 5.1 | Startup backup path fires | observe `data/backups/` after restart | new `shekar-YYYYMMDD-HHMMSS.db`; `integrity_check=ok`; sha256 recorded (repo-side rehearsal BR9 proves mechanism) |
| 5.2 | Rotation | 7-file rotation | `keep=7` respected |
| 5.3 | Restore drill (runbook §3) | stop → move live db aside → copy backup into place → start → health | health 200 post-restore; data intact; drill rows filled in runbook |
| 5.4 | Offsite copy (owner-gated) | owner-authorized destination only | dated owner decision or explicit N/A |

## Phase 6 — Electron / UI interactive checks (owner machine only)

| # | Check | Command / artifact | Exit criterion |
|---|---|---|---|
| 6.1 | Shell install | `cd electron; npm install` | lockfile-respecting install, exit 0 |
| 6.2 | Shell start | `npm start` | window opens; title version-free; version from API = 3.0.0 |
| 6.3 | Icon | taskbar/window icon | committed `icon.ico` renders (GOV-24 WP-2) |
| 6.4 | Menu navigation | click each menu item | each targets a real `/#…` tab; no dead links (GOV-24 WP-1) |
| 6.5 | Deep links | paste `#/<tab>` + unknown tab | hash→tab bridge activates; unknown id safe no-op (E2E-covered contracts) |
| 6.6 | Security posture | devtools console | contextIsolation true, nodeIntegration false |

## Phase 7 — Rollback

| # | Check | Command / artifact | Exit criterion |
|---|---|---|---|
| 7.1 | App rollback | previous install tree / tagged commit | boot + health green on previous version |
| 7.2 | Data rollback | Phase 5 restore path | integrity ok; app boots on restored db |
| 7.3 | Config rollback | `.env` backup/restore | validate_install green |

## Phase 8 — Evidence capture & bundle

| # | Item | Artifact |
|---|---|---|
| 8.1 | Per-row command outputs with timestamps | single transcript or per-phase files |
| 8.2 | Health/status payloads | JSON files |
| 8.3 | E2E junit/output | `pytest` output file |
| 8.4 | Boot logs (stdout/stderr) | log files |
| 8.5 | Backup sha256 manifest | hashes file |
| 8.6 | Screenshots (Electron W2–W5) | image set |
| 8.7 | Bundle manifest + hashes | `MANIFEST.sha256` over 8.1–8.6 |

## Status classification (inherits W2-INST)

47 items PASS repo-side (mechanism-level evidence exists); 8 classes remain
TARGET-MACHINE-ONLY (1.3 owner secrets, 3.1/3.6 canonical execution,
4-class restore drill 5.3, Electron 6.x, plus any offsite copy 5.4 which is
OWNER-GATED). Nothing here flips without the dated owner acts: R-1 INSTALL
instruction + R-2 access (or owner-executed run + returned bundle). Until
then: **INSTALL NOT ISSUED; installation completeness = NOT CLAIMED.**
