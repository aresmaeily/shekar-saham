# WINDOWS PACKAGING RUNBOOK — WAVE-G (2026-11-05)

MASTER-RADAR WAVE-G deliverable: repository-side Windows packaging
READINESS. This runbook makes the NSIS build reproducible and documents
upgrade/rollback/backup/health procedures. It deliberately makes **no**
claims that cannot be evidenced from this repository state:

- **NOT SIGNED:** no code-signing certificate exists in this project. The
  artifact produced below is an **unsigned NSIS installer**; Windows
  SmartScreen will warn. Any future signing step requires an owner-provided
  certificate and is out of scope here.
- **NOT EXECUTED ON A TARGET MACHINE:** the build below is a repository-side
  procedure. Installing/verifying on a Windows target machine is the owner's
  R-1/R-2 gate (recorded in the owner-action register) and is NOT claimed.
- The Electron shell security gates (`nodeIntegration: false`,
  `contextIsolation: true`, `enableRemoteModule: false`) are pinned by
  `backend/tests/test_wda_electron_shell_gates.py`; any packaging change
  that weakens them must fail that test.

---

## 1. Reproducible build (repository-side procedure)

Prerequisites (pinned, no floating ranges at build time):
- Node.js 20 LTS + npm 10 (Electron 28 / electron-builder 24 class of tools).
- A clean checkout at an exact SHA: `git checkout <40-hex-SHA>`; record the
  SHA next to the artifact.

Steps (from the repository root):

```bash
cd electron
npm ci                 # installs the exact devDependency tree from package-lock.json
npm run build          # electron-builder --win --x64  → dist/ نور جدول زیر
```

Electron-builder emits (at least):
- `dist/radar-bourse-desktop Setup <version>.exe` — the NSIS installer
  (`win.target: nsis`, `appId: com.radarbourse.desktop`,
  `directories.output: dist`, files list includes `main.js` only);
- `dist/latest.yml` — builder metadata used for future differential updates.

Integrity recording (mandatory step, not optional):

```bash
sha256sum dist/*.exe dist/latest.yml > dist/SHA256SUMS.txt
```

The recorded SHA-256 values are the artifact's identity. **Reproducibility
disclosure (honest):** NSIS installers embed timestamps/COM GUIDs; byte-for-byte
reproducibility across machines is NOT claimed. What IS required: one build
per exact-SHA checkout, with the checksums recorded — re-running the build for
the same SHA and comparing checksums tells you whether the environment drifted.

## 2. Startup health verification (post-install, same machine)

The desktop shell loads the backend origin (`RADAR_BOURSE_URL` env or the
default `http://127.0.0.1:8000`). Before starting the shell:

```bash
curl http://127.0.0.1:8000/api/health   # expect {"ok":true, ...}
```

The backend must be started with the documented run configuration
(`PYTHONPATH=backend DATA_SOURCE=auto python3 -m uvicorn app.main:app
--host 127.0.0.1 --port 8000 --no-proxy-headers`).

**WAVE-N remainder update (2026-11-06, OA-1): the shell now SUPERVISES the
bundled backend itself** — `electron/backend_service.js` (wired in
`electron/main.js`) starts the backend as a LOCAL loopback-only child
process (`--host 127.0.0.1`) with a bounded startup window (90 s) polling
`/api/health` on 127.0.0.1 only, graceful shutdown on quit (bounded grace
window, then forced kill), bounded crash recovery (max 3 restarts with
backoff, then an honest degraded state), and an honest local status page
(`data:` URL, zero remote content) for every degraded state
(`python-not-found` / `startup-timeout` / `restart-budget-exhausted`).
The recorded "shell does not spawn the backend" limitation is RESOLVED as
of this increment; the §2 manual curl check remains as the human
verification step after install. The narrower residual: the packaged
payload carries the backend SOURCE (backend/app + requirements.txt) — a
Python 3.11+ interpreter must exist on the target machine; if none is
found, the shell shows the honest `python-not-found` status page instead
of failing silently. Static contract pins:
`backend/tests/test_wda_electron_shell_gates.py` (WAVE-N remainder section)
+ `scripts/windows_package_readiness.py` section 3b (SUPERVISED_BACKEND_*).

Dependency/asset checks are automated repo-side:
`python3 scripts/windows_package_readiness.py` (green = NSIS config,
security gates, icon, build scripts, runbook disclosures all present).

## 3. Upgrade procedure

1. Record the currently installed version (Help → About or the UI header).
2. Build/obtain the NEW installer for the NEW exact-SHA (§1) with checksums.
3. Run the new installer; NSIS (electron-builder default) upgrades in place
   into the same install directory.
4. Re-run §2 health verification and confirm the reported version changed.
5. Data note: the backend's on-disk stores (see §4) live OUTSIDE the install
   directory; an in-place upgrade must not touch them. If an upgrade ever
   changes the store layout, the migration must be declared in the release
   notes — silent layout changes are forbidden.

## 4. Rollback procedure

1. Keep the previous installer + its `SHA256SUMS.txt` (checksum-verified
   before use: `sha256sum -c SHA256SUMS.txt`).
2. Uninstall the current version (Windows Apps) — NSIS uninstaller removes
   the install directory only.
3. Install the previous checksum-verified installer.
4. Re-run §2 health verification; confirm the reported version matches the
   previous release.
5. The backend data stores are NOT removed by uninstallation (they live
   outside the install directory) — verify before reinstalling if a data
   reset is actually intended.

## 5. Backup / restore (data, not the binary)

Backend-local state that matters (process-local unless documented otherwise):

| Item | Location / origin | Backup action |
|---|---|---|
| FERNET_KEY | env / `.env` (ephemeral CRITICAL warning if unset) | persist the owner-provided key material OFFLINE; losing it makes existing encrypted session tokens unreadable |
| user stores (portfolio/alerts/filters) | backend process storage as documented in the operators' docs | follow the existing operators' backup procedure; the prediction registry and product-loops state are process-local by declaration (no file to back up) |
| research-memory JSONL/SQLite adapters | as configured by their adapters | use the existing `test_research_memory_backup_cli`-documented CLI path |
| logs | backend log destination | copy with timestamps; never edit |

Restore = restore the store files + set the same FERNET_KEY + start the
backend + §2 health check. Restore is NOT verified on a Windows target
machine from this repository state (R-2 gate) — the procedure is documented,
not executed.

## 6. Diagnostics

- Backend: startup banner (`Starting رادار بورس v3.0.0 | …`), `/api/health`
  payload, request logs with `request_id`.
- Shell: load failures are visible in the window; the allowed origin is
  derived from `RADAR_BOURSE_URL` (default `http://127.0.0.1:8000`).
- Packaging: `scripts/windows_package_readiness.py --claim-signed` is
  REFUSED by design (exit 2) — the tool can never mint a signing claim.

## 7. Sign-off matrix (honest statuses)

| Item | Status |
|---|---|
| NSIS config complete + version-consistent + shell gates pinned | READY (machine-validated repo-side) |
| Reproducible build runbook (exact steps + checksum recording) | READY (documented) |
| Unsigned installer artifact | NOT BUILT HERE (requires Windows/wine toolchain — owner-side step) |
| Install / upgrade / rollback executed on Windows | NOT EXECUTED (owner R-1/R-2) |
| Code signing | NOT AVAILABLE (no certificate; never claimed) |
| Backup/restore procedure | DOCUMENTED (target-machine execution owner-gated) |
