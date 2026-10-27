# WS-HARDEN-1 — Hardening & Consistency Workstream Report (W1–W4)

- Date: 2026-10-27 (Asia/Tehran)
- Executor: governed execution session (owner-ordered)
- Baseline: `cd89a8adc72309e88712375f11199fb38a3e033d` (CONSOL-GOV-19; parent `300ca7a`; 48/0 vs live `origin/main` `c1984e7` = P3.91)
- Charter: `docs/active/WS_HARDEN_1_CHARTER_2026-10-27.md` (owner directive verbatim + numbering decision + per-item acceptance criteria — recorded BEFORE edits)
- Classification: SUBSTANTIVE change cycle (infrastructure + observability + frontend architecture + version consistency). No protected file touched; no gate predicate touched.

## 1. Numbering decision (summary)

P3.92/P3.93 taken locally (`a578abe`/`6ff6b07`); P3.94 deliberately avoided per `docs/CHANGELOG.md` (REM-1/AI2-A entry — a reported foreign-workspace P3.94 whose commits are NOT_PRESENT here); further P3.9x numbers carry unknown foreign consumption ("security follow-ups"). Per the REM-1/AI2-A precedent the workstream uses a distinct namespace: **WS-HARDEN-1**, items W1–W4. GOV-23 remains reserved for the next governance cycle.

## 2. What changed (per item)

### W1 — compose/Dockerfile hardening
- `docker-compose.yml`: insecure literal defaults removed — `PRIVATE_PASSWORD`/`API_KEY` are now `${VAR:-}` with an explicit fail-closed comment; `ports` interpolated `"${PORT:-8000}:${PORT:-8000}"`; FERNET_KEY empty-default kept (matches the app's deliberate warn-and-ephemeral design, production already fail-closes) with warning comments.
- `backend/app/core/security.py`: `validate_security_configuration()` now rejects insecure compose-style placeholders (`change-me*`, case-insensitive) as PRIVATE_MODE owner secrets — RuntimeError with remediation text. Non-private default configs unaffected; all 7 pre-existing hardening tests unchanged and green.
- `Dockerfile`: new root `entrypoint.sh` (`sh`, `set -eu`, `exec python -m uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --no-proxy-headers`), `COPY` + `chmod 0755` before `USER appuser`, `CMD ["/app/entrypoint.sh"]`; `HEALTHCHECK` probe reads `PORT` from env. The `--no-proxy-headers` flag kept deliberately (TRUST_PROXY is handled at app level; changing proxy semantics was out of scope).
- Tests: `backend/tests/test_ws_harden1_compose.py` (7: placeholder rejection ×2, strong-secret pass, compose no-insecure-literals, port interpolation, Dockerfile entrypoint/healthcheck, `sh -n` entrypoint).
- Honest limitation: **docker build/compose runtime NOT executed** (no docker daemon in this environment) — validation is static only (YAML content assertions, `sh -n`, Dockerfile content asserts). Recorded as NOT_VERIFIED:docker-runtime.

### W2 — request_id contextvar bridge
- `backend/app/core/request_id.py`: module-level `ContextVar("request_id")` + `get_current_request_id()`; `RequestIdMiddleware.dispatch` sets the token after computing `req_id` and resets it in `finally` (no cross-request bleed). `request.state.request_id` write and `X-Request-ID` echo preserved.
- `backend/app/main.py`: `RequestIdFilter` now reads `get_current_request_id()` (fallback: record attribute, then `-`). The old comment claimed a contextvar existed — it did not; every log line rendered `request_id=-`. Comment corrected with WS-HARDEN-1/W2 attribution.
- **Middleware reorder (found during testing):** `RequestIdMiddleware` moved from first-registered to LAST-registered (`add_middleware` immediately before `return app`) — i.e. OUTERMOST. Starlette registers middleware so the last-added runs first; previously the 401 short-circuit of `api_key_middleware` produced responses with NO `X-Request-ID` and its JSON body `request_id` was `null` (request.state never set on that path). Now: every response carries `X-Request-ID`, the 401 body `request_id` is populated, and ALL outer-middlewares' logs (auth/audit/rate-limit) see the contextvar.
- Tests: `backend/tests/test_ws_harden1_request_id.py` (7: generated-ID shape + ctx visibility, X-Request-ID honored, sequential no-bleed, contextvar None outside request, filter `-` default, real-app 401 bridge, real-app audit-warning log carries the header's request_id via caplog + filter).

### W3 — frontend modularization completion (legacy debug path retired)
- Deleted (via `git rm`, hashes captured pre-deletion in evidence `03_deleted_file_hashes.txt`):
  - `frontend/js/legacy/app.js` (87,658 B, `fe292050…`) — the god file, reachable only via `?legacy`
  - `frontend/js/app.v062.js` (2,008 B, `0e9721a7…`) — superseded v0.6.2 entry loaded only by the same debug path
  - `frontend/js/legacy-loader.js` (`207eca41…`) — the `?legacy` loader
- `frontend/index.html`: legacy-loader `<script>` tag removed (default path untouched: `main.js` + `core/` + `modules/` + `tabs/`).
- `frontend/sw.js`: legacy-loader cache entry removed; `CACHE_NAME` `radar-bourse-static-v3-0-2` → `v3-0-3` (cache-list change must re-cache).
- `backend/tests/test_p3_77_local_hardening.py`: legacy file removed from the live-verified triple-gate scan (intent preserved over remaining modular files).
- `backend/tests/test_p3_80_local_closure.py`: SW cache-name pin updated `v3-0-2` → `v3-0-3` + old name asserted absent (test intent preserved: cache list changed ⇒ name bumped).
- `docs/architecture/ARCHITECTURE_V3_META.md`: legacy row → "removed by WS-HARDEN-1/W3".
- `docs/active/SECURITY_PRIVATE_MODE.md`: v1.6 → **v1.7** — the `?legacy` debug row marked removed, append-only change-history entry added (no security control changed; the mode never bypassed auth).
- Zero remaining references to the removed files in frontend/ (grep-captured). Residual documented: untracked bootstrap skill file (`radar-coding-standards` SKILL.md:26) still mentions `js/legacy/` in prose — bootstrap set stays FROZEN pending owner review (path validator unaffected; verified via its prefix regex).
- `main.js` `isLegacyMode` flag intentionally left (always-false defensive constant; keeps the default-path diff minimal).

### W4 — UI version sync (single source of truth: `settings.version` = `3.0.0`)
- `frontend/js/main.js`: imports + calls `updateVersionFromApi()` on boot — the default UI path now syncs the version from `/api/health` (previously only the removed v062 entry did).
- `frontend/js/modules/utils/version.js`: stale hardcoded fallback `"0.6.2"` removed (API failure now leaves the DOM untouched); footer copy modernized to the current architecture description without a hardcoded phase number; `.ver` badge + `#lastUpdate` behavior kept.
- `frontend/index.html`: initial paint aligned exactly to `v3.0.0` (badge + footer — no visible flip after sync); divergent `v0.7` strings removed from the Excellent tab + heading (edition branding kept, stale version number dropped); stale `v0.6.2` HTML comment cleaned.
- `frontend/symbol.html`: footer `v0.3` → API-aligned `v3.0.0` badge structure.
- Header comments: `frontend/js/modules/render/excellent.js`, `modules/security.js`, `modules/utils/timezone.js` — stale version numbers dropped (annotations kept).
- `backend/app/main.py`: FastAPI description drops the conflicting `v0.7.0` number ("Excellent Edition" branding kept). Historical route comments (`# v0.7.0`/`# v0.8`/`# v0.9` on include_router lines) deliberately kept — they annotate when routes were added, not the app version.
- `scripts/validate_frontend_static.py`: NEW additive check `stale_version_literals` — rejects `v0.[0-7]` literals in `index.html`/`symbol.html`/`js/**/*.js` (vendor + `sw.js` internal cache version excluded); validator `ok` goes False on any hit.
- Tests: `backend/tests/test_ws_harden1_version_sync.py` (5: app.version==settings.version, description no `v0.7.0`, `/api/health` payload version==settings, index.html initial paint + no `v0.7`, main.js sync call + no `"0.6.2"` fallback).

## 3. Pre-commit battery at dirty tree (evidence: scratch `01_battery_precommit/`)

- **pytest full: 687 passed / 1 skipped / 2 warnings / 78.19s** = 668 baseline + 19 new tests EXACTLY (7 W1 + 7 W2 + 5 W4). One first-run failure (`test_p3_80` SW cache pin) fixed by the W3 test update above, then full re-run green.
- Focused, exact match to the GOV baseline: ai1=27, ai1gov=31, ai2f=29, ai3m=13, ai4=51, ai6=58, aimac=25; p0amd1=44 (both P0-AMD-1 files combined; the historical "23" figure corresponds to a single-file selection); g2h=42 passed + 1 env-conditional skip (GOV-19/22 state reproduced).
- pyflakes (app+tests+scripts) 0; compileall 0; pip-audit `-r requirements.txt --no-deps` "No known vulnerabilities found"; validate_alpha_environment 0; validate_alpha_runtime 0; validate_frontend_static 0 (with the NEW check active); validate_providers ×2 `--source {tsetmc,brsapi}` 0 (live_verified=false fail-closed preserved); bootstrap validator 8/8; corpus integrity 7/7 (hashes byte-identical to the GOV-19 pinned corpus); node --check 35 files / 0 failures (was 20-checked subset historically; this cycle checks ALL remaining js files); `git diff --check` clean; gate-flip scan (added lines, code scope config.py+app/api) **0 hits**; secret scan (added lines, full diff) **0 candidates**; protected pins zero-drift (`39ef15cd…` / `6f320a49…` / `aba4d66f…`); `ls-remote` = `c1984e7…` unchanged (NO push); gates captured: `AI2_ENABLED=0` (config.py:109), `verified=False` (config.py:270), `ai2_refs_in_app_api=0`.

## 4. Gates and boundaries (unchanged)

- G2 **NOT_PASSED** (owner-only at a convened review; this workstream neither moves nor pre-empts any G2 criterion — the G2 reviewer package v3 stays bound to `cd89a8a` and the reviewer may pin that SHA).
- `AI2_ENABLED=0`; `verified=False`; `live_verified=false`; zero `ai2` references under `backend/app/api/`.
- Protected files untouched: `backend/app/domain/ai2_governance.py`, `backend/app/domain/run_governance.py`, `backend/app/services/ai2_service.py`.
- Recovery archive of the 4 bootstrap paths taken BEFORE staging (scratch `02_bootstrap_recovery/`, 2,103 files, aggregate SHA-256 `199bce48…`).
- NO push (D-16-2 keep-private stands; push also credential-blocked — P3.43 gate 5). NO amend/rebase/reset/force. No credential touched. No owner-only field populated. D1–D7 and D-O2 remain open owner inputs.

## 5. Honest disclosures

1. Docker/compose runtime validation NOT executed (no docker daemon) — static validation only.
2. First battery run had 1 failure (p3_80 SW cache pin) + 2 command errors (validate_providers argument form; pip-audit `-l` instead of `-r`; secret-scan grep needed `-e`) — all corrected and the full battery re-run clean; both runs' artifacts retained.
3. One 16-line inline python edit (stale-version literals) was applied via heredoc before the script-persistence rule was re-checked; content identical to the charter plan, result re-verified by the validator; recorded here for completeness.
4. The external audit's proposed `read_only:true`+tmpfs hardening remains NOT applied (untested against sqlite WAL) — rejected for this cycle as recorded in the charter.
5. The external report's code packages remain NOT APPLIED; this workstream is an independent, tested re-implementation of only the four owner-confirmed findings.
