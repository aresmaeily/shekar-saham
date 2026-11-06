# MASTER-RADAR WAVE-N REMAINDER EXECUTION RECORD — SUPERVISED LOCAL BACKEND IN THE ELECTRON SHELL (OA-1) — 2026-11-06

Directive: OWNER AUTHORIZATION & CONTINUOUS EXECUTION DIRECTIVE (2026-11-05).
This record covers the **WAVE-N remainder**: the recorded residual from the
dd8feb1 installer increment ("the shell does NOT spawn the backend —
documented limitation, WINDOWS_PACKAGING_RUNBOOK") is RESOLVED — the shell
now STARTS and SUPERVISES the bundled backend as a local loopback-only
child process. Baseline: `e585085` (origin/main == local 0/0; battery
2967/1s/0f after WAVE-M). Same-wave file-ownership: Windows Packaging +
Windows Security roles (directive §2), executed additively; no overlap with
the WAVE-M owner set (scheduler files untouched).

## 1. What was built (additive)

- **`electron/backend_service.js` (NEW)** — supervised local backend lifecycle:
  - **bounded startup**: 90 s startup window, /api/health polled on
    `127.0.0.1` ONLY (500 ms interval); timeout ⇒ honest degraded state;
  - **graceful shutdown**: app quit ⇒ SIGTERM-equivalent, bounded 10 s grace
    window, then forced kill (`taskkill /T /F` on Windows, SIGKILL else);
    SIGINT/SIGTERM handlers in the shell;
  - **crash recovery**: unexpected backend exit ⇒ bounded restarts (max 3)
    with linear backoff; budget exhausted ⇒ honest degraded state
    (`restart-budget-exhausted`); a healthy run resets the budget;
  - **safe local binding (structural)**: the child is spawned with
    `--host 127.0.0.1` AND `HOST=127.0.0.1` env — never a wildcard interface;
  - **honest degraded surface**: every degraded state is machine-labeled
    (`python-not-found` / `startup-timeout` / `restart-budget-exhausted` /
    `spawn-failed` / `bundled-backend-directory-missing`) and surfaced via a
    LOCAL `data:` URL status page (Persian, zero remote content, zero egress)
    — never a silent failure;
  - **fail-closed inheritance**: the spawned backend receives
    `AI2_ENABLED=0` / `SCHEDULER_ENABLED=0` unless the operator explicitly
    overrode them in the environment — the shell can never silently open a
    governance gate;
  - **no remote path**: no URL literal, no updater, no fetch — the module's
    only network touch is the loopback health probe (validator-pinned as
    absent tokens).
- **`electron/main.js` (additive edits)** — wires `backend_service`: the
  window loads ONLY after the backend is healthy (bounded startup), a
  degraded state loads the honest status page, `will-quit` stops the
  supervised backend, and a non-loopback `RADAR_BOURSE_URL` override is
  refused with an error log (the supervised shell must never render a
  foreign origin).
- **`electron/package.json`** — packaging correctness: the bundled payload
  now ships via `extraResources` (REAL filesystem path outside app.asar — a
  Python child cannot execute from inside the asar archive), exposed to the
  resolver through `process.resourcesPath`; `backend_service.js` added to
  `files`.
- **`backend/app/core/config.py` (additive)** — `RADAR_DATA_DIR` env honors a
  relocated data directory; **OA-1 data contract**: the packaged shell sets
  it to `%APPDATA%/radar-bourse` so all on-disk stores (prediction registry,
  scheduler history, market cache, snapshots) live OUTSIDE the install
  directory and survive upgrade/uninstall. In-repo default `ROOT/data` is
  byte-unchanged for development/CI.
- **`scripts/windows_package_readiness.py` (additive section 3b)** — 15 new
  checks: supervised-backend byte-present gates (loopback binding, bounded
  startup, /api/health, graceful shutdown, bounded restarts, honest
  degraded), absent-token sweep (no `http(s)://`, updater, download tokens
  in the service), wiring pins (`require('./backend_service')`,
  `loadDegradedStatusPage`), NSIS files include `backend_service.js`. 33
  checks total, all green.
- **`.github/workflows/windows-installer.yml`** — the RELEASE_PROVENANCE.json
  `backend_supervision` field now records the SUPERVISED contract (label
  updated from RESIDUAL) with the narrower honest residual (a Python 3.11+
  interpreter must exist on the target machine); header comment updated.
- **`docs/active/WINDOWS_PACKAGING_RUNBOOK_2026-11-05.md` §2** — limitation
  paragraph replaced by the supervised-backend contract + the narrower
  residual; the manual `curl /api/health` check remains the human
  verification step.

## 2. Static contract pins (10 new tests in `test_wda_electron_shell_gates.py`)

wiring present · loopback-only binding (no wildcard) · bounded loopback
health check · bounded graceful shutdown (taskkill present, will-quit
wired) · bounded crash recovery (budget + backoff + exhausted label) ·
honest degraded states + local data:-URL page · no remote paths in the
service · fail-closed gate inheritance (AI2/SCHEDULER default 0) · data dir
outside install dir (RADAR_DATA_DIR end-to-end: service env + config.py
override, in-repo default preserved) · payload unpacked (extraResources +
process.resourcesPath; payload NOT inside app.asar).

## 3. Tests delta (exact)

- +10 static contract tests = **battery 2977 passed / 1 skipped / 0 failed
  = 2967 + 10 exact** (48.05s). pyflakes clean. All four validators exit 0
  (windows_package_readiness now 33/33).

## 4. Honest residuals (disclosed)

- **Python interpreter prerequisite**: the packaged payload carries the
  backend SOURCE; a Python 3.11+ interpreter must exist on the target
  machine (no bundled runtime is claimed, nothing is downloaded). Absence
  surfaces the honest `python-not-found` status page. Bundling a runtime
  (embeddable Python) is a future owner-gated packaging increment.
- **First-run dependency install**: `requirements.txt` is bundled but not
  pre-installed into a venv by the shell (no silent pip execution from the
  shell; the runbook documents the venv setup step). A future increment may
  add a supervised first-run bootstrap with explicit disclosure.
- **Real installer E2E on Windows**: per OA-1/R-1/R-2, target-machine
  install and the supervised-backend live behavior on Windows remain
  owner-gated — the artifact build (CI) validates packaging, the static
  contract pins validate the code, and nothing is claimed installed.

## 5. Gates after the WAVE-N remainder (all unchanged)

`AI2_ENABLED=0` (config.py:111 byte-unchanged) · `SCHEDULER_ENABLED=0` ·
`verified=False` · SYNTHETIC_OR_PAPER · no egress (structural, now pinned
for the shell too) · no broker · no promotion authority · G2 untouched ·
Two-Key intact · R-1..R-11 intact · installer remains UNSIGNED +
TARGET_INSTALL_PENDING (NOT installed on any machine — owner R-1/R-2) ·
global completion **NOT CALCULATED** (OA-8).

## 6. Next waves

WAVE-O (UX integration of the AI-2 surface) / WAVE-P (independent
acceptance + release). Exact-SHA CI currency for both 2026-11-06 pushes is
recorded in the WAVE-M record §8 (Release agent).
