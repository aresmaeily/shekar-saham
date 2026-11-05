# BOOTSTRAP-1 Validation Evidence — RADAR BOURSE / shekar-saham

- Date: 2026-10-16 (Asia/Tehran)
- Executor: main session (governance bootstrap continuation)
- Applies to HEAD: `c1984e7979f89f2d727b471deb602953ec62fad5` (P3.91, `main` == `origin/main`)
- Status vocabulary per skill `radar-evidence`. Raw outputs: `docs/governance/evidence/raw/*` (captured verbatim at run time).

## 1. Environment

| Item | Value | Note |
|---|---|---|
| OS | Linux sandbox (`5.10.134`, x86_64) | NOT the Windows owner target — Windows-specific behavior NOT_VERIFIED here |
| Python (project venv) | 3.12.15 at `.venv/` | CI uses 3.13; local run is NOT CI-version-parity |
| pip | 26.2.1 | venv created via `python3 -m venv .venv` (owner-authorized), exit 0 |
| Node | v24.21.0 | used only for `node --check` |
| Git | 2.47.3 | read/add/bundle operations only |
| venv creation | exit 0 | `python3 -m venv .venv && pip install -r backend/requirements.txt` → "Successfully installed …" (all pins incl. `tzdata==2026.3`) |

pip-audit note: not in `requirements.txt` but declared by the project's own CI (`.github/workflows/ci.yml` installs and runs it). Installed into the disposable gitignored venv solely for CI-parity; no credentials, no external service signup.

## 2. QA battery (baseline on HEAD `c1984e7`)

| # | Command | cwd | Exit | Duration | Verdict |
|---|---|---|---|---|---|
| 1 | `.venv/bin/python -m compileall -q app` | `backend/` | 0 | <1s | PASS |
| 2 | `.venv/bin/python -m pyflakes app` | `backend/` | 0 | <1s | PASS (0 findings, 0 output lines) |
| 3 | `PYTHONPATH=. .venv/bin/python -m pytest -q tests` | `backend/` | 0 | 77s | PASS — `308 passed, 2 warnings in 76.16s` |
| 4 | `.venv/bin/python -m pip_audit -r backend/requirements.txt` | repo root | 0 | 12s | PASS — `No known vulnerabilities found` |
| 5 | `.venv/bin/python scripts/validate_alpha_environment.py` | repo root | 0 | <1s | PASS (offline env check; secrets not printed) |
| 6 | `PYTHONPATH=. .venv/bin/python scripts/validate_alpha_runtime.py` | repo root | 0 | 37s | PASS |
| 7 | `.venv/bin/python scripts/validate_frontend_static.py` | repo root | 0 | <1s | PASS (`missing_js_imports: []`) |
| 8 | `.venv/bin/python scripts/validate_providers.py --source tsetmc` | repo root | 0 | 37s | PASS (repository-side) — `live_verified: false`, `last_source: mock_fallback` |
| 9 | `.venv/bin/python scripts/validate_providers.py --source brsapi` | repo root | 0 | <1s | PASS (repository-side) — `mock_fallback`, BRSAPI key missing |
| 10 | `node --check` × 8 files (`main.js`, `app.v062.js`, `core/api.js`, `core/router.js`, `modules/auth.js`, `modules/security.js`, `sw.js`, `symbol.js`) | repo root | 0 | <1s | PASS — 8/8 OK |

Verbatim decisive lines (pytest): `308 passed, 2 warnings in 76.16s (0:01:16)` — warnings are third-party deprecations from `starlette.testclient`/`anyio` inside installed deps, not project code.
Verbatim decisive line (pip-audit): `No known vulnerabilities found`.
Verbatim decisive line (tsetmc validator): `"live_verified": false` + `"warning": "MOCK data: development/demo fallback, not validated live market data."` — this is the correct honest result per skill `radar-testing`; it simultaneously proves LIVE is NOT verified.

Historical comparison (not a current claim): 194 passed at P3.79 → 308 now; suite grew across P3.80–P3.91.

## 3. Structural validation of bootstrap configuration

Script: `scripts/validate_bootstrap_config.py` (in-repo, re-runnable on any machine: `<venv python> scripts/validate_bootstrap_config.py`; sandbox working copy at `/home/z/my-project/scripts/bootstrap_validate.py`). Raw output: `docs/governance/evidence/raw/structural_validation.txt` and `structural_validation_inrepo.txt`.

| Check | Result | Detail |
|---|---|---|
| 1. Agents presence + frontmatter | PASS | 4/4 (`radar-chief-architect`, `radar-developer`, `radar-auditor`, `radar-qa`); `name`==filename; description present |
| 2. Skills presence + frontmatter | PASS | 8/8 SKILL.md; `name`==directory; description present |
| 3. settings.json valid + policy shape | PASS | allow=50, ask=30, deny=13; push gated (ask), force-push denied, `.env` denied, no bypassPermissions, no hooks key |
| 4. Path refs — CLAUDE.md | PASS | 10 resolved, 0 unresolved (amendment corpus excluded as known NOT_SYNCED) |
| 4. Path refs — agents | PASS | 21 resolved, 0 unresolved |
| 4. Path refs — skills | PASS | 38 resolved, 0 unresolved |
| 5. Secret scan (15 bootstrap files) | PASS | no key/token/password patterns |
| 6. CLAUDE.md cross-references | PASS (after fix) | skill index line added to CLAUDE.md; all 4 agents + 8 skills now named |

One defect found and fixed during validation: CLAUDE.md referenced only a generic skills path; `radar-coding-standards`, `radar-forensics`, `radar-testing` were not named. Fix: one additive skill-index sentence in CLAUDE.md. No other file changed.

## 4. Preservation verification

- `git status --porcelain --untracked-files=no` → EMPTY (zero modifications to tracked files).
- `git status --porcelain` → only the three pre-existing untracked bootstrap entries: `.claude/`, `CLAUDE.md`, `docs/governance/` (evidence subtree added under the latter; additive only).
- `git rev-parse HEAD` → `c1984e7979f89f2d727b471deb602953ec62fad5` (unchanged throughout).
- `git stash list` → 0 entries. No worktree changes. No commit, no `git add`, no push performed.

## 5. NOT_VERIFIED / BLOCKED items (honest register)

| Item | Status | Why |
|---|---|---|
| Claude Code CLI recognition of agents/skills (`/agents`, `/sessions` listing) | NOT_VERIFIED | `claude` CLI not installed in this sandbox; frontmatter/structure validated instead. Owner must open a Claude Code session on the target machine and confirm the 4 agents and 8 skills are listed. |
| Windows-target validation (install, Electron, browser E2E) | NOT_STARTED | Owner-gated (P3.43); wrong OS here by design |
| Live TSETMC/BRSAPI verification | BLOCKED | `live_verified=false`; keys not provided (correct fail-closed behavior) |
| LLM execution (`AI_EXECUTE=1`) | NOT_EXECUTED | Owner-gated; never set |
| pytest on Python 3.13 (CI version) | NOT_VERIFIED | Sandbox provides 3.12.15; CI will run 3.13 |
| Docker build | NOT_EXECUTED | Not part of local QA battery per skill `radar-testing` |
| GitHub push | BLOCKED | Owner-authenticated machine required; bootstrap files intentionally UNCOMMITTED |

## 6. Verdict

BOOTSTRAP-1 acceptance criteria §3 of `docs/governance/PROJECT_EXECUTION_STATE.md`:

1. Four agents + eight skills + CLAUDE.md + settings.json + state file exist and parse → **met** (structural validation PASS).
2. All repository-relative paths referenced from the new files resolve, except NOT_SYNCED amendment corpus (expected miss) → **met** (69 references resolved, 0 unexpected misses).
3. No secrets introduced; existing user work untouched → **met** (secret scan clean; zero tracked-file modifications; HEAD unchanged).
4. Baseline repo validation re-run on this tree and recorded → **met** (this file, §2).

Owner review remains required before these files are committed (bootstrap files stay uncommitted per skill `radar-git-workflow`).
