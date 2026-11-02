# W2-INST — INSTALLATION READINESS AUDIT (WS-E, directive §5 + §13.7)

Task ID: **W2-INST** · Date: 2026-11-02 · Auditor: Windows/DevOps installation-readiness sub-agent
Repo: `/home/z/my-project/RADAR_BOURSE/repo` · HEAD audited: **`7c225cb1ce2771473f1f646be9c4282348ea7657`** (`main`)
Scratch (all executions + artifacts): `/home/z/my-project/masterwave2_scratch/inst/`

**Binding red line (restated, verbatim source `docs/active/P343_INSTALL_CHECKLIST.md:13-14`):**
> A green `windows-validation` CI job is NOT proof of successful installation on the owner's target computer.

This audit is **REPO-SIDE installation readiness evidence only**. The owner `INSTALL`
instruction is **NOT ISSUED** (`P343_INSTALL_CHECKLIST.md:3,34` — "hard gate"); nothing in this
audit simulated, executed, or claimed a target-machine installation. No target machine exists in
this environment; every target-machine fact remains unproven and is classified **TARGET-MACHINE-ONLY**.

---

## 0. Execution environment (honest tooling inventory)

| # | Tool | Observed | Consequence for this audit |
|---|------|----------|----------------------------|
| E1 | `pwsh` | **NOT installed** (`which pwsh` empty; `/opt/microsoft` absent) | `.ps1` parse = NOT-RUN-HERE (finding F3) |
| E2 | `node` | v24.22.2 | `node --check` + JSON validation runnable |
| E3 | `docker` | **NOT available** (`docker: command not found`) | Docker build/run = NOT-RUN-HERE |
| E4 | Outer venv `/home/z/.venv/bin/python` | 3.12.16, `playwright` importable, chromium-1200 + chromium_headless_shell-1200 in `/home/z/.cache/ms-playwright/` | E2E suite runnable locally |
| E5 | Repo venv `/home/z/my-project/RADAR_BOURSE/repo/.venv/bin/python` | 3.12.16 (used read-only: interpreter execution only, `PYTHONDONTWRITEBYTECODE=1`, bytecode redirected to scratch) | py_compile, YAML, backup integrity checks |
| E6 | Network read | `git ls-remote origin main` succeeded (read-only query) | Remote read-back possible |

**Zero-repo-write method:** the tracked working tree was copied to
`masterwave2_scratch/inst/repo_copy/` (rsync excluding `.git`, `.venv`, `__pycache__`, root `/data`,
`.claude`) and proven **byte-identical**: all **497/497 tracked files** `cmp`-equal to the repo
(`git ls-files` loop, `mismatches=0`). All boots, E2E runs, and py_compile bytecode output were
executed in/against the scratch copy. `py_compile` used `cfile=` redirected into
`masterwave2_scratch/inst/pyc/` so no `__pycache__` was written in-repo.

---

## 1. Evidence table (per-item: command → observed → verdict)

Verdict classes: **PASS** (repo-side evidence produced), **FAIL**, **TARGET-MACHINE-ONLY**
(includes RUNTIME-ONLY: requires the owner's Windows machine), **NOT-RUN-HERE** (tool absent in
this sandbox), **OWNER-GATED** (requires a dated owner act).

### 1.1 Artifact inventory

| Item | Command / source | Observed | Verdict |
|---|---|---|---|
| A1 `docs/active/P343_INSTALL_CHECKLIST.md` | `ls` | present, 85 lines; owner INSTALL gate at :3,:34 | PASS |
| A2 `docs/active/ALPHA_INSTALLATION_RUNBOOK.md` | `ls` | present, 14 sections, currency note :19-30 (21-commit blocker SUPERSEDED) | PASS |
| A3 `docs/active/ALPHA_INSTALLATION_CHECKLIST.md` | `ls` | present, 117 lines, row-by-row target checklist | PASS |
| A4 `docs/active/BACKUP_RESTORE_RUNBOOK.md` | `ls` | present, 6 sections | PASS |
| A5 `start.sh` | `ls` | present; exports `PYTHONPATH=$ROOT/backend` (:6), boots `app.main:app` (:24) | PASS |
| A6 `install.sh` | `ls` | present (native + `--docker` + `--check` modes) | PASS |
| A7 Windows scripts | `ls scripts/windows/` | `install.ps1`, `start.ps1`, `validate_install.ps1`, `validate_alpha.ps1` — all 4 present (P343:30 claim exact) | PASS |
| A8 `electron/package.json` + main | `ls electron/` | `main.js` + `package.json` + `icon.ico`; **no `preload.js` in repo** (`"main": "main.js"` package.json:5; `contextIsolation:true`, `nodeIntegration:false` main.js:15-17) | PASS (inventory note) |
| A9 Docker artifacts | `ls` | `Dockerfile` (python:3.13-slim :3, non-root :36-37, HEALTHCHECK :32-33), `docker-compose.yml` (fail-closed private-mode comments :11-19, `./data` volume :25) | PASS |
| A10 Workflows | `ls .github/workflows/` | `ci.yml` (jobs: test-backend, build-docker), `windows.yml` (job: windows-validation; W1 boot :50-64, W2 health+version :66-121, W6 E2E :123-155, W7 log posture :157-177) | PASS |
| A11 E2E suite | `ls e2e/` | `conftest.py` + `test_smoke.py` + `README.md`; 7 test functions | PASS |

### 1.2 Script validity

| Item | Command | Observed | Verdict |
|---|---|---|---|
| S1 bash syntax | `bash -n start.sh install.sh entrypoint.sh scripts/run.sh scripts/r13_owner_repo_setup.sh` | exit 0 on all 5 | PASS (5/5) |
| S2 PowerShell parse | pwsh `[scriptblock]::Create(...)` / PSParser | **pwsh not installed** (E1); no repo-side or CI automation parses the 4 `.ps1` files (windows.yml uses inline pwsh only) | **NOT-RUN-HERE** (finding F3) |
| S3 Electron JS | `node --check electron/main.js` | exit 0 | PASS |
| S4 JSON contracts | `node -e JSON.parse(...)` on `electron/package.json`, `frontend/manifest.json` | both parse OK | PASS |
| S5 Python compile | `py_compile.compile(<file>, cfile=<scratch>, doraise=True)` on 6 × `scripts/*.py` + `backend/app/main.py` | exit 0 on all 7 | PASS (7/7) |
| S6 Workflow YAML | `yaml.safe_load` (repo venv) | both load; jobs as listed in A10 | PASS |
| S7 Electron CLI | `which electron`; `ls electron/node_modules` | both absent | PASS (proves Electron runtime is target-only) |

### 1.3 Canonical boot-form (directive item 3) — executed in byte-identical scratch copy

| Item | Command | Observed | Verdict |
|---|---|---|---|
| B1 Literal form `backend.app.main:app` from repo-copy root | `.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18099` (timeout 25) | **exit 1** — `ModuleNotFoundError: No module named 'app'` at `backend/app/main.py:15` (`from app.api.routes import router as main_router`) — the app package uses absolute `app.*` imports. Claim from `CONTROLLED_ALPHA_LAUNCH_READINESS_RECORD.md:111-117` re-verified verbatim. Log: `boot_literal_backend_form.log` | PASS (claim verified: literal form FAILS) |
| B2 Canonical form `PYTHONPATH=backend` + `app.main:app` | `env -u FERNET_KEY DATA_SOURCE=mock PYTHONPATH=<copy>/backend python -m uvicorn app.main:app --host 127.0.0.1 --port 18099 --no-proxy-headers`; curl `/api/health` | health reachable after 2s; **HTTP 200**; `version='3.0.0'`; `ok=True`; `data_trust.state=mock`; `trust_level=synthetic`; `data_trust.live_verified=False`; `is_live=False`; `redacted=False`; header `x-request-id` present. Boot log carries the expected ephemeral-key `WARNING` (`shekar.crypto`) **and** `CRITICAL` (`main.py:82-88`) — honest local-only disclosure. `kill` → exit 143; post-kill connection refused; `pgrep` → none | PASS |
| B3 `validate_alpha.ps1`-equivalent battery (its exact check list, ps1:11-16) | single-shot boot + curl ×5 | `/api/health` 200, `/api/status` 200, `/api/live/status` 200 (`routes.py:832`), `/` 200, `/symbol/فملی` 200 | PASS (with kill-hiccup note, finding F9: stray PID 9001 lingered ~40s, then killed + verified `PORT_18099_CLOSED=OK`, `ORPHAN_CHECK=NO_UVICORN_ANYWHERE`) |

### 1.4 Version chain 3.0.0 (directive item 4) — byte-level

| Node | Location | Observed bytes | Verdict |
|---|---|---|---|
| V1 Backend settings | `backend/app/core/config.py:28` → `    version: str = "3.0.0"` | `"3.0.0"` = `33 2e 30 2e 30` (od) | PASS |
| V2 Electron | `electron/package.json:3` → `  "version": "3.0.0",` | `"3.0.0"` = `33 2e 30 2e 30` (od) | PASS |
| V3 PWA manifest | `frontend/manifest.json:34` → `  "version": "3.0.0"` | `"3.0.0"` = `33 2e 30 2e 30` (od) | PASS |
| V4 Served | `/api/health` response (boot B2) | `version` bytes `b'3.0.0'` = `332e302e30`; assertion script exited True (`VERSION_CHAIN_BYTES_MATCH=True`) | PASS |

### 1.5 Backup/restore runbook currency (directive item 5)

All 8 prior **VERIFIED_PATH_EXISTS** claims re-verified (prior record `CONTROLLED_ALPHA_LAUNCH_READINESS_RECORD.md:53-65`):

| # | Runbook item | Fresh evidence (this audit) | Verdict |
|---|---|---|---|
| BR1 | `Store.backup(keep=7)` | `backend/app/data/store.py:62` (`def backup(self, keep: int = 7)`) | PASS |
| BR2 | `PRAGMA wal_checkpoint(TRUNCATE)` before copy | `store.py:71` | PASS |
| BR3 | copy2 → `data/backups/shekar-<YYYYmmdd-HHMMSS>.db` | `store.py:74` (copy2), stamp `%Y%m%d-%H%M%S` (`store.py:67-68`) | PASS |
| BR4 | `data/backups/` created on demand + prune beyond keep | `store.py:65-66` (mkdir), `store.py:77` (`baks[:-keep]` unlink) | PASS |
| BR5 | WAL mode throughout | `store.py:36` (`PRAGMA journal_mode=WAL`) | PASS |
| BR6 | `PRAGMA user_version` guarded additive migrations | `store.py:47-60`; guard `if current < version` at `store.py:55` | PASS |
| BR7 | Alert-ops reversible rollback = archive rename | `backend/app/data/alert_ops_store.py:173` (`def rollback`), `:190-191` (DROP `*_rollback_archive` + `ALTER TABLE ... RENAME TO ..._rollback_archive`), `:194` (`def restore_from_archive`); same DB file `:31` (`DB_PATH = DATA_DIR / "shekar.db"`) | PASS |
| BR8 | Referenced docs exist | `GOV41_DAI30_IMPLEMENTATION_RECORD_2026-10-30.md`, `AI3_PERSISTENCE_DECISION_PACKET.md`, `ALPHA_INSTALLATION_CHECKLIST.md` — all in `docs/active/` | PASS |
| BR9 | **Runtime rehearsal (scratch)** — startup backup path fired during boots (`main.py:94-96` → `_store.backup(keep=7)`) | 3 real backups produced in scratch `data/backups/`: `shekar-20261102-123742.db`, `-123831.db`, `-123849.db`; each `integrity_check=ok`, `user_version=1`, 17 tables; sha256 recorded (26724a63…, 8ffc9218…, 961d0a4d…) | PASS (repo-side rehearsal in scratch) |
| BR10 | keep=7 rotation observable | repo gitignored `/data/backups/` holds exactly 7 `.db` files (2026-10-29 → 2026-11-02) — rotation consistent with keep=7 (incidental, pre-existing workspace state) | PASS |
| BR11 | Restore shell ops (`mv data/shekar.db …`, `cp` backup into place) — runbook §3 | target-machine operations; requires the real data dir | TARGET-MACHINE-ONLY |
| BR12 | `sqlite3 … "PRAGMA integrity_check;"` — runbook §2.2 | requires sqlite3 CLI on target (equivalent verified via python sqlite3 in BR9) | TARGET-MACHINE-ONLY |
| BR13 | Offsite copy (§2.3) + drills recorded in checklist (§6) | owner policy; not executable from repo | OWNER-GATED |

### 1.6 Windows prerequisites (directive item 6)

| Item | Evidence | Observed | Verdict |
|---|---|---|---|
| W1 Python pin matrix | `ci.yml:22` = `"3.13"`; `windows.yml:43` = `"3.12"`; `Dockerfile:3` = `python:3.13-slim`; `install.ps1:58` = min 3.10; repo/outer venv = 3.12.16 | **CI-vs-Windows pin drift CONFIRMED** (3.13 vs 3.12); installer floor 3.10 | PASS (drift documented, finding F2) |
| W2 Playwright for W6 | `windows.yml:151-152` (`playwright==1.57.0`, `playwright install chromium`); outer venv has playwright + chromium-1200 | requirement explicit and satisfiable | PASS |
| W3 FERNET_KEY persistent-key on target | `.env.example:24` (`FERNET_KEY=`); runbook §5 (`ALPHA_INSTALLATION_RUNBOOK.md:101,107-111` generate-persistent command); `main.py:82-88` CRITICAL when unset; compose `:17-19` documents ephemeral fail-closed warning | persistent key **mandatory on target** (CRITICAL must NOT appear); ephemeral allowed local-only — observed honestly in B2 | PASS |
| W4 HostAddress nuance | `P343_INSTALL_CHECKLIST.md:43` says "boot backend (uvicorn **127.0.0.1**:8000)" vs `start.ps1:5` default `$HostAddress = "0.0.0.0"` | STALE nuance re-confirmed verbatim; §7 step 4 of the readiness record already mandates explicit `-HostAddress 127.0.0.1` | PASS (finding F1) |
| W5 Pre-MA-1 CI pin currency | `P343_INSTALL_CHECKLIST.md:16-22` pins CI evidence to `7c72f3d…`/`4215ed4`; audited HEAD is `7c225cb…` | currency note stands; checklist item 1.1 mandates re-verify at install time — **re-verified repo-side now**: `git ls-remote origin main` → `7c225cb1ce2771473f1f646be9c4282348ea7657` == local HEAD | PASS (finding F6) |
| W6 Node/npm for Electron | `electron/package.json:14-16` (electron ^28.0.0, electron-builder ^24.0.0 devDeps); runbook §2 marks Node optional unless Electron validation | consistent | PASS |

### 1.7 CI jobs (what each does — separation evidence)

| Job | Does | Verdict for this audit |
|---|---|---|
| `test-backend` (ci.yml:9-42, ubuntu, py3.13, fetch-depth 0 for G2 harness) | pip install, pyflakes, full backend battery, pip-audit | NOT-RUN-HERE (GitHub-hosted; repo-side equivalent evidence exists from prior records) |
| `build-docker` (ci.yml:44-50, needs test-backend) | `docker build` only — **never boots or installs** | NOT-RUN-HERE (no docker in sandbox) |
| `windows-validation` (windows.yml:26-200, windows-latest, py3.12) | W1 boot app.main:app on 127.0.0.1:8000; W2 health+version consistency vs `config.py`; W6 playwright 7/7 E2E vs locally booted server; W7 fail-closed log posture (Traceback absence, ephemeral/FERNET warning presence, `live_verified != true`); artifact upload; Shutdown kills pid | NOT-RUN-HERE here; by design it is **validation on a hosted runner, not installation** (`windows.yml:5-13`, `P343:13-14`) |

### 1.8 10-step `PROPOSED_SEQUENCE_PENDING_OWNER_INSTALL` (directive item 7)
Source: `docs/active/CONTROLLED_ALPHA_LAUNCH_READINESS_RECORD.md:152-185`.

| Step | Referenced script/command | Exists? | Exit criterion mechanically checkable? | Classification |
|---|---|---|---|---|
| 1 Preconditions | `scripts/windows/validate_install.ps1` | yes | yes — `OK: True`, exit 0 (script `exit 0/1` at :169) | TARGET-MACHINE-ONLY |
| 2 Install | `scripts/windows/install.ps1` | yes | yes — venv + requirements + `.env` from `.env.example` (script :74-86) | TARGET-MACHINE-ONLY |
| 3 Secrets (owner) | edit `.env` (persistent FERNET_KEY) | n/a (owner act) | yes — file saved; env status SET via validate_install.ps1:57-64 (values never printed) | TARGET-MACHINE-ONLY / OWNER-GATED |
| 4 Start (loopback) | `start.ps1 -HostAddress 127.0.0.1` — param exists (start.ps1:4-5) | yes | yes — "Uvicorn running" + grep NO ephemeral CRITICAL in boot log | TARGET-MACHINE-ONLY |
| 5 Health gate | `GET http://127.0.0.1:8000/api/health` | yes (routes.py:87) | yes — 200, `version=="3.0.0"`, `live_verified==false`, `ok==true` | criterion REPRODUCED repo-side (B2); target execution TARGET-MACHINE-ONLY |
| 6 Availability battery | `scripts/windows/validate_alpha.ps1` | yes | yes — `ok=true`, exit 0 (:40), `live_data_verified=false` hardcoded (:35) | criterion REPRODUCED repo-side (B3); target execution TARGET-MACHINE-ONLY |
| 7 Canonical target-browser E2E (P3.43-2) | `RADAR_E2E_BASE_URL=… python -m pytest e2e -q` from repo root | yes (7 tests) | yes — 7/7 passed **on the target machine** (containers/CI excluded per e2e/README.md:37-44) | suite REPRODUCED repo-side 7/7 (§1.9); canonical gate TARGET-MACHINE-ONLY |
| 8 Electron interactive (W2-icon, W3–W5) | `cd electron; npm install; npm start` + windows.yml:11-13 header | yes | partially — owner-verdict recorded (not automatable, per windows.yml:11-13) | TARGET-MACHINE-ONLY |
| 9 Backup & restore drills | runbook §2/§3 | yes | yes — sha256 + integrity ok + POST-INSTALL rows filled | backup mechanism REPRODUCED repo-side (BR9); restore drill TARGET-MACHINE-ONLY; offsite OWNER-GATED |
| 10 Records | fill `ALPHA_INSTALLATION_CHECKLIST.md` + `ALPHA_TARGET_VALIDATION_CHECKLIST.md`; launch decision per P343 §5 | yes | yes — row states updated; 7 P343 §5 exit criteria | OWNER-GATED (doc edit records target facts) |

**No step references a missing script or an uncheckable exit criterion.** One precision defect:
step 10 (and P343 §2.8) call the target-validation matrix a "26-row matrix" — the actual table in
`ALPHA_TARGET_VALIDATION_CHECKLIST.md:7-36` has **30 rows** (finding F7, LOW).

### 1.9 E2E evidence (directive item 8)

| Item | Command | Observed | Verdict |
|---|---|---|---|
| E2E-a Suite inventory | read `e2e/test_smoke.py` (72 lines) | exactly 7 tests: health+version, X-Request-ID, UI badge==API version, hash-routing tab, unknown-tab fallback, symbol page, dashboard no-errors | PASS |
| E2E-b Local run | `RADAR_E2E_BASE_URL=http://127.0.0.1:18099 /home/z/.venv/bin/python -m pytest e2e -q` against the B2-booted app | **7 passed in 5.07s, exit 0** (`pytest_e2e_out.txt`); server killed after; connection refused; no orphan | PASS |
| E2E-c Canonical P3.43-2 gate | e2e/README.md:37-44 — dev/CI run is *test-of-the-suite*, target-system E2E stays externally blocked | consistent | TARGET-MACHINE-ONLY |
| E2E-d Electron runtime | `which electron` → absent; no `electron/node_modules` | no Electron CLI/toolchain in this Linux sandbox | TARGET-MACHINE-ONLY |

### 1.10 Repo integrity (auditor hygiene)

| Item | Command | Observed | Verdict |
|---|---|---|---|
| R1 Tracked tree unchanged | `git diff --stat` (start + end) | empty both times | PASS |
| R2 HEAD unchanged | `git rev-parse HEAD` (start + end) | `7c225cb1…` both times | PASS |
| R3 Untracked set unchanged | `git status --porcelain` | same 6 pre-existing entries at start and end (`.claude/`, `CLAUDE.md`, `docs/governance/PROJECT_EXECUTION_STATE.md`, `docs/governance/evidence/`, `scripts/r13_owner_repo_setup.sh`, `scripts/validate_bootstrap_config.py`) | PASS |
| R4 No git state change | no add/commit/push/checkout/stash issued | none | PASS |
| R5 Runtime writes confined to scratch | backup timestamps in scratch (`12:37:42/12:38:31/12:38:49`) == my three boot times; repo `data/` untouched by my processes (gitignored runtime dir; pre-existing churn from other workspace activity observed at 12:38:19/24 — not attributable to any process of this audit; see F8) | PASS |

---

## 2. Installation evidence report draft (ready to become §13.7 deliverable)

**Scope statement.** This package evidences REPOSITORY-SIDE installation readiness for RADAR
BOURSE 3.0.0 at commit `7c225cb1ce2771473f1f646be9c4282348ea7657` (main). It contains no
target-machine claims. The owner `INSTALL` instruction has NOT been issued
(`P343_INSTALL_CHECKLIST.md:3,34`); all target facts below remain **unproven** until the owner
executes `PROPOSED_SEQUENCE_PENDING_OWNER_INSTALL`
(`CONTROLLED_ALPHA_LAUNCH_READINESS_RECORD.md:152-185`).

**Evidence summary.**
1. **Package completeness** — every artifact the install sequence references exists: 4 Windows
   PowerShell scripts (`scripts/windows/`), 5 shell scripts, Docker path
   (`Dockerfile` + `docker-compose.yml` + `entrypoint.sh`), desktop shell (`electron/main.js`,
   `package.json`, real 7-layer `icon.ico` — header verified: type=1, 7 images), 4 installation
   documents, `.env.example` contract with mandatory-keys table
   (`INSTALL_GUIDE.md:36-44`, `P343:33`).
2. **Script validity** — `bash -n` 5/5 exit 0; `node --check electron/main.js` exit 0; JSON
   contracts parse; `py_compile` 7/7 exit 0 (scripts ×6 + boot module); workflow YAML valid ×2.
   PowerShell syntax: NOT parsed here (no pwsh in sandbox; no automated ps1 gate exists anywhere
   in the repo — finding F3).
3. **Canonical boot-form** — the literal `backend.app.main:app` from the root FAILS
   (`ModuleNotFoundError: No module named 'app'`, `backend/app/main.py:15`); the canonical form
   `PYTHONPATH=backend` + `app.main:app` — used identically by `start.sh:6,24`,
   `scripts/windows/start.ps1:44,51`, `entrypoint.sh:7`, `Dockerfile:27`,
   `windows.yml:54,93,140` — was booted in a byte-identical scratch copy on 127.0.0.1:18099:
   HTTP 200 in 2s, `version=3.0.0`, `ok=true`, `data_trust.state=mock`,
   `trust_level=synthetic`, `live_verified=false`, `is_live=false`; process killed; port closed;
   no orphan.
4. **Version chain** — byte-identical `3.0.0` (`332e302e30`) at `config.py:28`,
   `electron/package.json:3`, `frontend/manifest.json:34`, and the served `/api/health` payload.
5. **Data-trust posture at install time** — with mock source and no credentials: state=mock,
   `verified` hard-coded False (`config.py:284`), LIVE triple-gate `is_verified_live` requires
   all three flags (`config.py:156-167`), `TRUST_LEVEL=live` override ignored
   (`config.py:183-185`); `validate_alpha.ps1:35` reports `live_data_verified=false` by design.
   No false-LIVE path exists repo-side.
6. **Backup/restore** — runbook↔code match 8/8 re-verified (§1.5 BR1-BR8); backup mechanism
   actually exercised (3 backup files produced by the app's own startup path during this audit's
   boots; `integrity_check=ok`, `user_version=1`, sha256 recorded). Restore ops and the offsite
   copy remain TARGET-MACHINE-ONLY / OWNER-GATED respectively.
7. **Local E2E** — 7/7 passed (5.07s) against the locally booted app (outer-venv playwright +
   chromium-1200). Per `e2e/README.md:37-44` this is test-of-the-suite; the canonical P3.43-2
   acceptance is target-browser E2E on the owner machine.
8. **Remote currency** — `git ls-remote origin main` == local HEAD `7c225cb1…` (P343 item 1.1
   re-verifiable at install time; satisfied as of this audit).
9. **Red line preserved** — a green `windows-validation` run proves the repository builds, boots
   and passes E2E on a GitHub-hosted Windows runner (`windows.yml:5-9`); it is NOT installation
   evidence. CI validation and target-machine installation remain strictly separated.

**Pending (all owner-side):** INSTALL instruction; steps 1-4, 8-10 of §1.8;
target-browser E2E (step 7); Electron interactive W2-icon/W3–W5; backup/restore drills + offsite
copy; launch decision per `P343_INSTALL_CHECKLIST.md §5` (7 exit criteria).

---

## 3. Findings (severity · disposition)

| # | Finding | Severity | Disposition |
|---|---|---|---|
| F1 | `P343_INSTALL_CHECKLIST.md:43` documents start.ps1 as binding `127.0.0.1:8000`, but `scripts/windows/start.ps1:5` defaults `$HostAddress="0.0.0.0"` (all interfaces). Mitigated: readiness-record §7 step 4 mandates explicit `-HostAddress 127.0.0.1`. | LOW (doc-vs-script nuance; loopback-only expectation) | **AUTHORIZED-REPO-SIDE** (one-line doc or default fix, owner-approved; NOT applied — read-only audit) |
| F2 | Python pin drift: CI ubuntu pins 3.13 (`ci.yml:22`), Windows runner pins 3.12 (`windows.yml:43`), Docker 3.13-slim (`Dockerfile:3`), installer floor 3.10 (`install.ps1:58`). Same codebase validated on two different minor versions. | LOW (works, but validation ≠ homogeneous runtime) | **AUTHORIZED-REPO-SIDE** (align pins in a future authorized commit; no install blocker — floor 3.10 honored everywhere) |
| F3 | No automated syntax gate for the 4 `scripts/windows/*.ps1` files: pwsh absent in sandbox (NOT-RUN-HERE) and no CI job parses or executes them (windows.yml uses inline pwsh only). First syntax proof would be the owner's step-1 execution. | MEDIUM (unverified-parse risk on the exact scripts the owner will run first) | **AUTHORIZED-REPO-SIDE** (add a pwsh parse job/step or local `PSParser` check when pwsh access exists) |
| F4 | Literal boot-form `backend.app.main:app` from root fails (ModuleNotFoundError, `main.py:15`); every shipped launcher uses the canonical `app.main:app` + `PYTHONPATH=backend`. Documented in readiness record :111-117; re-verified. | INFO (documented, consistent) | **AUTHORIZED-REPO-SIDE** (already documented; no action) |
| F5 | Icon duality: `electron/main.js:13` window icon = `../frontend/favicon.svg`, builder icon = `icon.ico` (`electron/package.json:24`). Both files exist; builder icon is a real 7-layer ICO. Window-icon rendering is covered by the owner's W2-icon interactive check. | LOW | **AUTHORIZED-REPO-SIDE** (optional: point window icon at `icon.ico`) |
| F6 | CI evidence pinned in `P343:16-22` to `7c72f3d…` predates audited HEAD `7c225cb…`; currency note already recorded. Remote read-back this audit: origin/main == HEAD. | INFO (currency note; checklist mandates re-verify at install) | **AUTHORIZED-REPO-SIDE** (refresh pin at next docs-only authorized commit) |
| F7 | "26-row matrix" (readiness record §7 step 10; P343 §2.8) vs actual **30 rows** in `ALPHA_TARGET_VALIDATION_CHECKLIST.md:7-36`. | LOW (doc precision) | **AUTHORIZED-REPO-SIDE** (correct the count) |
| F8 | Repo gitignored `/data/` showed mtime churn during the audit window (12:38:19/24) not attributable to this audit's processes (all my boots provably wrote only to the scratch copy — scratch backup timestamps exactly match my boot times). Consistent with concurrent workspace activity; tracked tree and untracked set unchanged (R1-R3). | INFO (workspace hygiene note) | NONE (recorded honestly) |
| F9 | During the endpoint battery, one backgrounded uvicorn (PID 9001) survived its in-line `kill` for ~40s; detected, killed (`kill 9001`), verified dead + port closed + no uvicorn anywhere. Probe/e2e runs used the PID-file script and shut down cleanly. | INFO (audit-process note; no repo impact) | NONE (remediated; evidence in transcript) |
| F10 | `install.sh` (Linux easy-install) creates `backend/.venv` while the Windows installer creates root `.venv` (`install.ps1:43`), and binds 0.0.0.0 (install.sh:44). Two different venv layouts across platforms. | LOW (platform split is intentional; noted for support) | **AUTHORIZED-REPO-SIDE** (document in INSTALL_GUIDE if desired) |
| G1 | Owner `INSTALL` instruction | HARD GATE — **NOT ISSUED** (`P343:3,34`) | **OWNER-GATED** |
| G2 | Target-machine install/start/health/E2E (canonical P3.43-2) | unproven here | **OWNER-GATED / TARGET-MACHINE-ONLY** |
| G3 | Electron interactive checks (W2-icon, W3–W5 shell navigation) | not automatable (`windows.yml:11-13`) | **OWNER-GATED** |
| G4 | Persistent FERNET_KEY / secrets provisioning on target | out-of-band owner inputs | **OWNER-GATED** |
| G5 | Offsite backup copy + drills recorded in checklist | owner policy (`BACKUP_RESTORE_RUNBOOK.md:29-30,69-75`) | **OWNER-GATED** |
| G6 | Live-provider enablement posture | DENIED for current release (`verified=False` always, `config.py:284`; `is_verified_live` triple gate :156-167; override ignored :183-185) | **OWNER-GATED** (re-proposal needs new dated owner act) |

---

## 4. CI-vs-install separation statement (explicit)

Repository CI (`.github/workflows/ci.yml`, `.github/workflows/windows.yml`) validates code on
GitHub-hosted runners: unit/lint/audit on ubuntu-py3.13, docker **image build** (no run), and a
Windows-runner application-layer validation (boot → health/version → 7/7 browser E2E → log
posture). **None of these constitutes installation.** Installation is the owner-executed,
dated-instruction-gated sequence in
`CONTROLLED_ALPHA_LAUNCH_READINESS_RECORD.md:152-185` on the owner's Windows machine, recorded in
`ALPHA_INSTALLATION_CHECKLIST.md` / `ALPHA_TARGET_VALIDATION_CHECKLIST.md`, with the launch
decision per `P343_INSTALL_CHECKLIST.md §5`. This audit produced repo-side readiness evidence
only; it did not and could not execute any target-machine step, and it did not simulate the
`INSTALL` instruction. Everything labeled TARGET-MACHINE-ONLY or OWNER-GATED above is, by
construction, still open.

---

## 5. Verdict counts (evidence-table summary)

| Verdict | Count | Items |
|---|---|---|
| PASS | 47 | E2,E4,E5 · A1-A11 · S1,S3,S4,S5,S6,S7 · B1,B2,B3 · V1-V4 · BR1-BR10 · W1-W6 · E2E-a,E2E-b · R1-R5 |
| FAIL | 0 | — (B1 is a verified *expected* failure of a documented anti-pattern; the claim itself PASSes) |
| TARGET-MACHINE-ONLY (incl. RUNTIME-ONLY) | 8 | T1,T2,T3,T4,T8 (steps) · BR11,BR12 · E2E-c/E2E-d (canonical target E2E gate; Electron runtime) |
| NOT-RUN-HERE | 3 | S2 (ps1 parse ×4 files — pwsh absent) · build-docker job (no docker) · GitHub CI runs themselves |
| OWNER-GATED | 6 | BR13 (offsite) · G1-G6 register (INSTALL instruction, target install, Electron interactive, secrets, offsite/drills, live posture) |

---

## 6. Appendices — scratch evidence artifacts

| File | Content |
|---|---|
| `repo_copy/` | byte-identical copy of the tracked tree (497/497 cmp-equal) used for all executions |
| `boot_literal_backend_form.log` | B1 failure traceback (ModuleNotFoundError at `main.py:15`) |
| `uvicorn_18099.log` | canonical boot log (ephemeral WARNING + CRITICAL lines; Uvicorn running 127.0.0.1:18099) |
| `health_18099.json`, `health_headers.txt` | /api/health body (version 3.0.0, data_trust mock posture) + headers (x-request-id present) |
| `pytest_e2e_out.txt` | `7 passed in 5.07s` (E2E against booted app) |
| `boot_and_probe.sh` | reproducible single-shot boot→probe→kill→orphan-check script |
| `pyc/c1..c7.pyc` | py_compile outputs (redirected out of the repo) |
| repo `data/backups/shekar-*.db` ×3 in scratch | backup rehearsal artifacts (integrity ok, sha256 in §1.5) |

*Report generated by W2-INST; strictly read-only with respect to the repository; no git state was changed; every process started by this audit was verified terminated (final `pgrep -af uvicorn` → none; port 18099 closed).*
