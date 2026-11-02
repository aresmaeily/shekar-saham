# CONTROLLED ALPHA LAUNCH READINESS RECORD — WP-5 (T6, CONSOL-NEXT Wave 1)

Date: 2026-11-02 · Agent: T6 (Windows/DevOps & Installation Specialist + browser QA) ·
Repo: `main` @ `84f9b1b75dd2c90d9c6c98d2c808f2d93df44ec6` (tracked tree clean; no existing file modified; nothing committed/pushed).

Scope: REPO-SIDE launch readiness only. The actual install is owner-gated and
was NOT executed and NOT prepared beyond what already exists in the repo.

> **Binding red line (verbatim, `P343_INSTALL_CHECKLIST.md §0`):** a green
> `windows-validation` CI job is NOT proof of successful installation on the
> owner's target computer. Everything in this record is repository evidence;
> target-machine facts remain unproven until the owner executes §7 below.

---

## 1. Health / version / data-trust verification — VERIFIED

Exact routes located (no guessing; read from code):

| Contract | Location | Behavior |
|---|---|---|
| `GET /api/health` | `backend/app/api/routes.py:87-105` (router prefix `/api`, routes.py:18) | 200; full probe when authorized; `_redacted_probe` shape (routes.py:48-70) when not — two shipped shapes, both pinned in tests |
| `GET /api/status` | `backend/app/api/routes.py:108-113` | version via `market_service.status()` (`backend/app/services/market_service.py:928` = `get_settings().version`) |
| `GET /api/live/status` | `backend/app/api/routes.py:832` | exists (referenced by `validate_alpha.ps1:13`) |
| Data-trust context | `backend/app/core/config.py:228-333` `build_data_trust_context`; served via `market_service.data_trust_context()` (`market_service.py:77-88`) | `verified` is **hardcoded False** (config.py:284); `is_live = verified` (False); live-CLASS state downgrades legacy `trust_level` to `mixed` (config.py:286-287); `live_verified=True` argument is an unused compatibility argument — no caller can mint verified LIVE |
| Independent LIVE gate | `backend/app/core/config.py:156-167` `is_verified_live` | requires state==live AND is_live AND live_verified — all three, never inferred |
| Config override honesty | `backend/app/core/config.py:183-185` | `TRUST_LEVEL=live` override is IGNORED (configuration ≠ market evidence) |

Additive tests (NEW file `backend/tests/test_wp5_launch_readiness.py`, 10 tests, all passing):
health 200 + per-shape key contracts; health/status version == `settings.version`;
version chain equality; frontend no-hardcoded-fallback; data-trust
verified-False markers; `live_verified=True` argument ignored;
`is_verified_live` refusal matrix; non-live sources report non-verified
markers; served `/api/health` `data_trust` block carries honest non-verified
markers. **Status: VERIFIED (repo-side).**

## 2. Version contract chain — VERIFIED (all 3.0.0)

| Node | Location | Value |
|---|---|---|
| Backend settings | `backend/app/core/config.py:28` | `3.0.0` |
| Served (health/status) | `market_service.py:928` → `/api/health` | `3.0.0` (asserted by tests + local E2E + CI W2) |
| Electron | `electron/package.json:3` | `3.0.0` |
| PWA manifest | `frontend/manifest.json:34` | `3.0.0` |
| Frontend display | `frontend/js/modules/utils/version.js:1-25` | single source of truth = backend `/api/health`; NO hardcoded fallback version (pinned by test) |

**Status: VERIFIED — equality pinned in `test_version_chain_backend_electron_frontend_manifest` and `test_frontend_version_display_single_source_no_hardcoded_fallback`.**

## 3. Backup / restore / rollback audit — runbook vs code

Read fully: `docs/active/BACKUP_RESTORE_RUNBOOK.md` (all 6 sections). Item-by-item:

| # | Runbook item | Classification | Evidence |
|---|---|---|---|
| 1 | `Store.backup(keep=7)` at `backend/app/data/store.py` | **VERIFIED_PATH_EXISTS** | store.py:62-86 exactly as documented |
| 2 | `PRAGMA wal_checkpoint(TRUNCATE)` before copy | **VERIFIED_PATH_EXISTS** | store.py:71 |
| 3 | copy2 → `data/backups/shekar-<YYYYmmdd-HHMMSS>.db` | **VERIFIED_PATH_EXISTS** | store.py:66-74 (stamp `%Y%m%d-%H%M%S`, store.py:68-69) |
| 4 | `data/backups/` created on demand + prune beyond keep | **VERIFIED_PATH_EXISTS** | store.py:67, 76-81; runtime dir exists locally (gitignored `/data/`, .gitignore:23) |
| 5 | WAL mode throughout | **VERIFIED_PATH_EXISTS** | store.py:36 |
| 6 | `PRAGMA user_version` guarded, idempotent, additive migrations | **VERIFIED_PATH_EXISTS** | store.py:47-60 (guard `if current < version`, line 55) |
| 7 | Alert-ops reversible rollback = archive rename preserving records | **VERIFIED_PATH_EXISTS** | `backend/app/data/alert_ops_store.py:173-195` (`rollback()` → `*_rollback_archive`, `restore_from_archive()`); same DB file (`alert_ops_store.py:31` → `DATA_DIR/shekar.db`) |
| 8 | Referenced docs (`GOV41_DAI30_IMPLEMENTATION_RECORD_2026-10-30.md`, `AI3_PERSISTENCE_DECISION_PACKET.md`, `ALPHA_INSTALLATION_CHECKLIST.md`) | **VERIFIED_PATH_EXISTS** | all present in `docs/active/` |
| 9 | Restore shell ops (`mv data/shekar.db …`, `cp data/backups/…`) | **RUNTIME_ONLY** | target-machine operations; paths consistent with `DATA_DIR = ROOT/data` (`backend/app/core/config.py:11-14`) |
| 10 | `sqlite3 … "PRAGMA integrity_check;"` | **RUNTIME_ONLY** | requires sqlite3 CLI on target |
| 11 | Offsite copy (§2.3) + drills recorded in checklist | **OWNER-GATED** | owner policy; not executable from repo |

**What the app actually persists** (from code): `data/shekar.db` (+WAL/SHM
sidecars, `config.py:142`), `data/market_cache.json` (rebuildable cache,
`config.py:140`), `data/history_snapshots.jsonl` (declared `config.py:141`;
no writer/reader found in current app code), `data/backups/shekar-*.db`
(backup rotation), alert-ops tables inside the same `shekar.db`. **Runbook
match: YES** — its scope statement (DB + WAL sidecars + `data/backups/`
rotation) matches code exactly; its honest limitation ("sidecar files not
bundled", cache/artifact store excluded) matches `backup()`'s copy2 of the
main file only. No invented behaviors found; no stale paths found.

## 4. Local E2E re-run (closes MA-1 §7 deferral) — PASSED 7/7

Boot (repo-canonical invocation, working dir repo root):

```
env -u FERNET_KEY DATA_SOURCE=mock BRSAPI_KEY= HOST=127.0.0.1 PORT=8000 \
  PYTHONPATH=/home/z/my-project/RADAR_BOURSE/repo/backend \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

- Health: 200 after 2s — `version=3.0.0, ok=True, data_trust.state=mock, trust_level=synthetic, live_verified=False`.
- **Ephemeral-key disclosure (expected for local verification only):** boot
  log recorded `WARNING | shekar.crypto | No FERNET_KEY/API_KEY - using
  ephemeral singleton key` **and** the `CRITICAL` ephemeral-crypto warning
  (`main.py:82-88`) — honest and expected here because FERNET_KEY was
  intentionally unset; on the target machine a persistent FERNET_KEY is
  mandatory and this CRITICAL must NOT appear.
- E2E runner (checked `e2e/conftest.py` first): plain pytest + playwright
  sync API; suite = `e2e/test_smoke.py` (7 contracts). `repo/.venv` has **no
  playwright**; the outer workspace venv `/home/z/.venv` has playwright +
  chromium (chromium-1200) — that runner was used:
  `cd /home/z/my-project/RADAR_BOURSE/repo && /home/z/.venv/bin/python -m pytest e2e -q`
  → **7 passed in 5.45s**.
- Server stopped cleanly (kill + pkill; post-check connection refused).
- Repo hygiene: `git status` shows no tracked modifications and no new
  untracked files beyond this task's deliverable
  (`backend/tests/test_wp5_launch_readiness.py`, this record) plus one
  concurrent Wave-1 deliverable from agent T2
  (`backend/tests/test_p3_quality_validation_evaluation_statistics.py`,
  appeared 04:55Z, not a T6 artifact) and the pre-existing untracked set
  (`.claude/`, `CLAUDE.md`, `docs/governance/*`, `scripts/r13_owner_repo_setup.sh`,
  `scripts/validate_bootstrap_config.py`). Runtime artifacts stay in
  gitignored `/data/` (mtime churn from test runs only).

**Boot-command currency finding (honest):** the literal
`.venv/bin/python -m uvicorn backend.app.main:app` from repo root FAILS
(`ModuleNotFoundError: No module named 'app'` at `backend/app/main.py:15` —
the app package uses absolute `app.*` imports). The repo-canonical boot is
`app.main:app` with `PYTHONPATH=backend` from `backend/` — exactly what
`start.sh:6-10`, `scripts/windows/start.ps1:44-51`, and the Docker
entrypoint do. §7 therefore uses the canonical invocation only.

## 5. Windows sequence currency audit

Files audited (read-only): `docs/active/P343_INSTALL_CHECKLIST.md`,
`docs/active/ALPHA_INSTALLATION_CHECKLIST.md`, `scripts/windows/install.ps1`,
`scripts/windows/start.ps1`, `scripts/windows/validate_install.ps1`,
`scripts/windows/validate_alpha.ps1`.

| Item | Status |
|---|---|
| `install.ps1:45` `.env.example`, `:85` `backend/requirements.txt`, `:89` `start.ps1`, `:47` `data/` | VERIFIED (all exist / created on demand) |
| `start.ps1:40-51` venv python + `PYTHONPATH=backend` + `uvicorn app.main:app` + HOST/PORT env | VERIFIED (matches `config.py:29-30`, import root) |
| `validate_install.ps1:130-141` env names (DATA_SOURCE, PRIVATE_MODE, PRIVATE_PASSWORD, API_KEY, FERNET_KEY, BRSAPI_KEY, COOKIE_SECURE, TRUST_PROXY, CORS_ORIGINS, RADAR_BOURSE_URL) | VERIFIED (all recognized: `config.py:34-103`; `RADAR_BOURSE_URL` consumed at `electron/main.js:24`) |
| `validate_install.ps1:84-86,116-124` paths (backend/frontend/electron/.env.example/.env/requirements) | VERIFIED (all exist) |
| `validate_alpha.ps1:10-16` checks incl. `/api/live/status` | VERIFIED (`routes.py:832`) |
| `validate_alpha.ps1:35-36` `live_data_verified=false` + availability-only note | VERIFIED (consistent with verified=False posture) |
| `P343_INSTALL_CHECKLIST.md:43` "start.ps1 — boot backend (uvicorn **127.0.0.1**:8000)" vs `start.ps1:5` default `$HostAddress = "0.0.0.0"` | **STALE(nuance): doc says loopback; script default binds all interfaces** — sequence must pass `-HostAddress 127.0.0.1` explicitly (see §7 step 4) |
| `P343_INSTALL_CHECKLIST.md:16-22` CI evidence pinned to `7c72f3d…`/`4215ed4`; HEAD is now `84f9b1b…` (post-MA-1 chain; MA-1 record §8 shows all-3-jobs green on `1832b75`) | CURRENCY NOTE: checklist already mandates re-verify at install time (item 1.1); CI green remains ≠ install proof |
| `ALPHA_INSTALLATION_CHECKLIST.md:21` P3.44 archive `/home/user/deliverables/P3.44_RADAR_BOURSE_FULL_PROJECT_4e6cf72.zip` | OWNER-EXTERNAL artifact (not in repo; unverifiable here) |
| `ALPHA_INSTALLATION_CHECKLIST.md:47,55-58,106,116` port/data/backups/live-status rows | VERIFIED as paths/commands; execution = RUNTIME_ONLY |
| Electron rows (`npm install/start`, W2/W3–W5 interactive) | RUNTIME_ONLY (target machine) |

No edits were made to any of these files.

## 6. Owner-gate register (explicit)

| Gate | State |
|---|---|
| Dated owner `INSTALL` instruction | **REQUIRED — NOT ISSUED** (`P343_INSTALL_CHECKLIST.md:3,34` hard gate; nothing may execute until issued) |
| Target-machine install + health + E2E (canonical P3.43-2) | **PENDING** — repo-side evidence (this record, CI) does not substitute |
| Electron interactive checks W2/W3–W5 | **PENDING** (owner-runbook items, not automatable) |
| Live-provider posture | **DENIED FOR CURRENT RELEASE** — `AI2_ENABLED=0`, `verified=False` always (`config.py:284`), `live_verified` cannot be minted (`config.py:249-253`), `TRUST_LEVEL=live` override ignored (`config.py:183-185`), `validate_alpha.ps1` reports `live_data_verified=false`; re-proposal requires a new dated owner act |
| Offsite backup copy + backup/restore drills | **OWNER-GATED** (runbook §2.3, §6) |

## 7. PROPOSED_SEQUENCE_PENDING_OWNER_INSTALL — Windows target machine

Built ONLY from existing, repo-verified scripts (no new mechanism proposed).
Execute top-to-bottom after the dated `INSTALL` instruction; do NOT proceed
past a failed step.

1. **Preconditions** — `powershell -ExecutionPolicy Bypass -File scripts\windows\validate_install.ps1`
   · Exit criterion: `OK: True`, exit 0 (paths, Python ≥3.10, port 8000 free).
2. **Install** — `powershell -ExecutionPolicy Bypass -File scripts\windows\install.ps1`
   · Exit criterion: venv created, `backend/requirements.txt` installed, `.env` created from `.env.example`, exit 0.
3. **Secrets (owner, out-of-band)** — edit `.env`: set persistent `FERNET_KEY`
   (mandatory), `PRIVATE_PASSWORD`/`API_KEY` per owner decision. Never print
   or commit values. · Exit criterion: file saved; no secret echoed anywhere.
4. **Start (loopback)** — `powershell -File scripts\windows\start.ps1 -HostAddress 127.0.0.1`
   (explicit `-HostAddress` closes the §5 STALE-nuance vs the script's `0.0.0.0` default).
   · Exit criterion: "Uvicorn running"; boot log contains **NO** ephemeral-FERNET CRITICAL.
5. **Health gate** — `GET http://127.0.0.1:8000/api/health`
   · Exit criterion: HTTP 200, `version == "3.0.0"`, `data_trust.live_verified == false`, `ok == true`.
6. **Availability battery** — `powershell -File scripts\windows\validate_alpha.ps1`
   · Exit criterion: `ok = true`, exit 0, `live_data_verified` stays `false`.
7. **Canonical target-browser E2E (P3.43-2)** — install Playwright + chromium
   on the target, backend running, then
   `RADAR_E2E_BASE_URL=http://127.0.0.1:8000 python -m pytest e2e -q` from repo root.
   · Exit criterion: **7/7 passed on the target machine** (CI/containers do not satisfy this).
8. **Electron interactive checks** — `cd electron; npm install; npm start` +
   W2 icon / W3–W5 shell navigation per the `windows.yml` header and
   `ALPHA_INSTALLATION_RUNBOOK.md`. · Exit criterion: owner-verdict recorded.
9. **Backup & restore drills** — runbook §2 (backup, sha256, integrity_check
   ok) and §3 against a THROWAWAY copy. · Exit criterion: drill results
   recorded in `ALPHA_INSTALLATION_CHECKLIST.md` POST-INSTALL rows.
10. **Records** — fill `docs/active/ALPHA_INSTALLATION_CHECKLIST.md` and
    `docs/active/ALPHA_TARGET_VALIDATION_CHECKLIST.md` (26-row matrix); launch
    decision per `P343_INSTALL_CHECKLIST.md §5` (its 7 exit criteria,
    including the §0 red line, are the final gate).

## 8. Evidence artifacts (scratch, outside repo)

`/home/z/my-project/consolnext_scratch/T6/`: `pytest_wp5_launch_readiness.txt`
(10 passed), `pytest_full_battery.txt` (**1303 passed, 1 skipped** = prior
1293+1 plus this task's 10), `pytest_e2e_local.txt` (**7 passed in 5.45s**),
`uvicorn_local.log` (boot incl. ephemeral-FERNET WARNING+CRITICAL),
`health_local.json`, `uvicorn_pid.txt`, `pyflakes_app_wp5.txt` (exit 0, no
output — `backend/app` + new test file clean).
