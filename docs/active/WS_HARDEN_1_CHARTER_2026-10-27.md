# WS-HARDEN-1 — Hardening & Consistency Workstream Charter (W1–W4)

- Date: 2026-10-27 (Asia/Tehran)
- Executor: governed execution session (owner-ordered)
- Applies to baseline: `cd89a8adc72309e88712375f11199fb38a3e033d` (CONSOL-GOV-19; parent `300ca7a`; 48/0 vs live `origin/main` `c1984e7` = P3.91, ls-remote exit 0, NO push)
- Classification: SUBSTANTIVE change cycle — infrastructure hardening + observability bridge + frontend architecture completion + version-label consistency. No AI2/AI3 subsystem file touched; no gate predicate touched; no governance boundary moved.
- Authority: explicit owner directive received 2026-10-27 (verbatim, Persian):

> «یافته‌های واقعی گزارش (سخت‌سازی compose/Dockerfile، پل contextvar برای request_id، تکمیل ماژولارسازی فرانت‌اند، همگام‌سازی نسخه UI) به یک workstream شماره‌دار (بعد از P3.91/GOV-22) تبدیل شود، دستور میدهم تا طبق روند کامل حاکمیتی اجرا کن»

Translation: "Turn the report's verified findings (compose/Dockerfile hardening, the contextvar bridge for request_id, completing frontend modularization, UI version sync) into a numbered workstream (after P3.91/GOV-22); ordered to execute per the full governance process."

Provenance of the four findings: EXTAUDIT-1 cycle (2026-10-27, worklog `EXTAUDIT-1`) adjudicated the external 360-audit claim; the four items below were the observations CONFIRMED against this repository at `cd89a8a` and recorded as "candidate future workstream items requiring proper numbering (>P3.91/GOV-22) + full change control". This charter is that numbering; the owner directive is that authorization.

## 1. Numbering decision (recorded, not silent)

- P3.92 (`a578abe`) and P3.93 (`6ff6b07`) are already used locally (2026-10-17 docs cycles).
- P3.94 is deliberately avoided per `docs/CHANGELOG.md` (REM-1/AI2-A entry): "a reported P3.94 exists only in a second workspace whose commits are absent from this repository" (see `docs/governance/PROJECT_EXECUTION_STATE.md` §2: eight reported foreign commits `db16a2c…f538806` = reported P3.92/P3.93/P3.94/security follow-ups, all NOT_PRESENT here).
- Foreign "security follow-ups" may have consumed further P3.9x numbers (unknown). Reusing them locally would create cross-workspace ID collisions before the owner names the authoritative lineage (EXEC_STATE decision packet item 1, still open).
- Therefore this workstream uses a distinct task-ID namespace, per the REM-1/AI2-A precedent: **WS-HARDEN-1**, items **W1–W4**. If the owner later rules the foreign workspace non-authoritative, a P3.9x alias may be recorded additively.

## 2. Work items, evidence base, and acceptance criteria

### W1 — compose/Dockerfile hardening (owner-secret placeholders + hardcoded port)

Evidence (fresh at `cd89a8a`, scratch `00/02_findings_fresh.txt`):
- `docker-compose.yml:11-12`: `PRIVATE_PASSWORD: ${PRIVATE_PASSWORD:-change-me-strong-password}`, `API_KEY: ${API_KEY:-change-me-api-key}` — insecure literal placeholders become the EFFECTIVE credentials when the operator runs compose unedited. `backend/app/core/security.py:225` `validate_security_configuration()` requires a non-empty owner secret in PRIVATE_MODE but does NOT reject placeholder values, so the placeholder passes validation.
- `docker-compose.yml:13`: `FERNET_KEY: ${FERNET_KEY:-}` — consistent with the app's deliberate warn-and-ephemeral design (`backend/app/main.py:76-83`, `backend/app/core/crypto.py:49`); production already fail-closes on missing FERNET_KEY. Kept, with an explicit warning comment added.
- `Dockerfile:35`: `CMD … --port 8000` hardcoded while `backend/app/core/config.py` reads `PORT` from env and `Dockerfile:10` already declares `ENV PORT=8000` — the container ignores operator `PORT`.

Changes:
1. `docker-compose.yml`: placeholder literals removed (`${PRIVATE_PASSWORD:-}`, `${API_KEY:-}`) + comments; `ports` mapped to `"${PORT:-8000}:${PORT:-8000}"`.
2. `backend/app/core/security.py`: `validate_security_configuration()` now fail-closes when the PRIVATE_MODE owner secret is an insecure placeholder (`change-me` prefix, case-insensitive) — RuntimeError with explicit remediation text. Non-private default config unaffected; existing passing configurations unaffected.
3. `Dockerfile`: new `entrypoint.sh` (repo root, `exec python -m uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --no-proxy-headers`), copied + chmod 0755 pre-`USER`, `CMD` switched to the entrypoint; `HEALTHCHECK` python probe reads `PORT` from env instead of the hardcoded 8000.
4. Tests: placeholder rejection (raises / passes matrix) + compose static assertions (no `change-me` literal, port interpolation present) in a new `backend/tests/test_ws_harden1_compose.py`.

Acceptance: new tests green; full battery unchanged except additive tests; `docker-compose.yml` contains no insecure literal; entrypoint `bash -n` clean; Docker/compose runtime build NOT executed (no docker daemon in this environment — recorded honestly as NOT_VERIFIED:docker-runtime; static validation only).

Explicitly NOT applied (recorded from EXTAUDIT-1): the external report's `read_only: true` + tmpfs rootfs proposal — untested against sqlite WAL write behavior; rejected for this cycle.

### W2 — request_id contextvar bridge

Evidence (fresh): `backend/app/core/request_id.py` — `RequestIdMiddleware` writes ONLY `request.state.request_id`; NO contextvars exist in the module. `backend/app/main.py:40-49` — the log format includes `%(request_id)s` and a logging filter reads `record.request_id`, but nothing ever sets it on log records → every log line renders `request_id=-` (the observed symptom). `backend/app/main.py:240,255` read `request.state.request_id` (works only inside the request scope). The external report's proposed mechanism ("bridge exists but leaks") was WRONG per EXTAUDIT-1 — no bridge exists at all; this item builds it correctly.

Changes:
1. `backend/app/core/request_id.py`: module-level `ContextVar("request_id")`; `get_current_request_id()` accessor; `RequestIdMiddleware.dispatch` sets the contextvar after computing `req_id` and resets the token in `finally` (no cross-request bleed). `request.state.request_id` write and `X-Request-ID` response header behavior preserved (existing consumers at main.py:240/255 untouched).
2. `backend/app/main.py` logging filter: reads `get_current_request_id()` with fallback to the record attribute, then `-`.
3. New `backend/tests/test_ws_harden1_request_id.py`: (a) end-to-end bridge — real app, unauthorized sensitive-route warning log carries `record.request_id == X-Request-ID response header`; (b) `X-Request-ID` honored; (c) generated ID shape; (d) `request.state.request_id` still consumed by handlers; (e) isolation across sequential requests (no bleed); (f) filter default `-` outside a request.

Acceptance: new tests green; every pre-existing log line keeps rendering (no format change); no gate file touched.

### W3 — frontend modularization completion (retire the legacy debug path)

Evidence (fresh): default UI path is fully modular — `frontend/index.html:940` loads `/static/js/main.js` (module) importing `core/` + `modules/` + `tabs/`. The 87,658-byte `frontend/js/legacy/app.js` god file loads ONLY via `frontend/js/legacy-loader.js` under the `?legacy` debug query, together with the superseded entry `frontend/js/app.v062.js` (2,008 B, "v0.6.2 Professional Modular Entry"). No other loader or test exercises the legacy path. References: `frontend/index.html:941`, `frontend/sw.js:10`, `backend/tests/test_p3_77_local_hardening.py:109,117-119`, `docs/architecture/ARCHITECTURE_V3_META.md:122`, `docs/active/SECURITY_PRIVATE_MODE.md:47` (v1.6 row), and one prose line in the untracked bootstrap skill file (not matched by the bootstrap path validator's prefix regex — verified).

Changes (retirement, not rewrite — the modularization was already done by earlier phases; completion = removing the retained dead path):
1. Delete `frontend/js/legacy/app.js`, `frontend/js/app.v062.js`, `frontend/js/legacy-loader.js` (via `git rm`).
2. `frontend/index.html`: drop the legacy-loader `<script>` tag.
3. `frontend/sw.js`: drop the legacy-loader cache entry; `CACHE_NAME` bumped `radar-bourse-static-v3-0-2` → `radar-bourse-static-v3-0-3` (cache-list change must re-cache).
4. `backend/tests/test_p3_77_local_hardening.py`: remove `legacy/app.js` from the scanned-files list and the legacy-file assertions; the test's intent (no live-verified overstatement in frontend JS) is preserved over the remaining files.
5. `docs/architecture/ARCHITECTURE_V3_META.md`: legacy row updated to "removed by WS-HARDEN-1/W3".
6. `docs/active/SECURITY_PRIVATE_MODE.md`: v1.6 → v1.7 — the `?legacy` debug-mode row is replaced by a removal note (append-style; no silent rewrite of other rows).

Acceptance: zero references to the removed files outside historical/evidence/archive records (grep check captured as evidence); `node --check` green on all remaining frontend JS; `scripts/validate_frontend_static.py` exit 0; default UI path (`main.js` tree) untouched except the W4 version-sync addition; `main.js` `isLegacyMode` flag intentionally left as a harmless always-false defensive constant (documented residual — kept to keep the default-path diff minimal).

Note: the untracked bootstrap skill file's prose (`radar-coding-standards` SKILL.md line 26) becomes stale after W3. The bootstrap set stays FROZEN pending owner review (house rule) — the staleness is recorded here instead of edited.

### W4 — UI version sync (single source of truth: `settings.version`)

Evidence (fresh): canonical version = `backend/app/core/config.py:28` `version = "3.0.0"` (FastAPI `version=`, lifespan log, event bus, `/api/health` via `market_service.status()` → `backend/app/services/market_service.py:909`). Divergent labels: `backend/app/main.py:126` FastAPI description "…Excellent Edition v0.7.0…"; `frontend/index.html:92` tab "✨ عالی v0.7" and `:848` heading "…نسخه عالی v0.7…"; `frontend/js/modules/render/excellent.js:2` header comment "v0.7.0"; `frontend/js/modules/utils/version.js` fallback `"0.6.2"` + stale footer copy "فاز ۶.۲"; `frontend/js/main.js` never calls `updateVersionFromApi()` (only the removed v062 entry did) so the default UI never syncs the real version; `frontend/index.html:41` badge `v3.0` and footer `v3.0` are hardcoded initial paint (loosely matching `3.0.0` but not exactly).

Changes:
1. `frontend/js/main.js`: import + invoke `updateVersionFromApi()` on boot (default path now syncs version from `/api/health`).
2. `frontend/js/modules/utils/version.js`: remove the stale `"0.6.2"` fallback (on API failure, leave the DOM untouched); footer copy modernized to match the current footer without a hardcoded phase number; `.ver` badge and `#lastUpdate` suffix behavior kept.
3. `frontend/index.html`: initial paint aligned to `v3.0.0` (badge + footer) so pre-sync and post-sync values are identical; divergent `v0.7` strings in the Excellent tab/heading removed (edition branding kept, version number dropped).
4. `backend/app/main.py`: FastAPI description drops the conflicting "v0.7.0" number (edition name kept).
5. `frontend/js/modules/render/excellent.js`: header comment version number dropped.
6. `scripts/validate_frontend_static.py`: NEW additive static check — reject hardcoded legacy-version literals (`v0.6`/`v0.7` forms) in `frontend/index.html` and `frontend/js/**/*.js` (vendor + service worker excluded; the SW's own internal cache version is its own release artifact).
7. Tests: `backend/tests/test_ws_harden1_version_sync.py` — `create_app().version == get_settings().version`; description carries no `v0.7.0`; `/api/health` payload carries `version == settings.version`.

Acceptance: static validator exit 0 with the new check active; new tests green; no user-facing copy other than the listed labels changed.

## 3. Governance envelope for the whole workstream (binding)

- Protected files untouched: `backend/app/domain/ai2_governance.py` (pin `39ef15cd…`), `backend/app/domain/run_governance.py` (pin `6f320a49…`), `backend/app/services/ai2_service.py` (pin `aba4d66f…`) — re-verified zero-drift at commit time.
- Gates unchanged: `AI2_ENABLED=0` (`backend/app/core/config.py:109`), `verified=False` (`backend/app/core/config.py:270`), zero `ai2` references under `backend/app/api/`, `live_verified=false`, `G2 NOT_PASSED` (owner-only at a convened review; this workstream does NOT move, imply, or pre-empt any G2 criterion).
- `backend/app/core/config.py` IS edited (W4? no — config.py version line NOT edited; only security.py/main.py/frontend). Correction: config.py is NOT edited at all in this workstream; the version single-source remains `settings.version` untouched at `3.0.0`.
- NO push (D-16-2 keep-private stands; push also credential-blocked — P3.43 gate 5). NO amend/rebase/reset/force. NO owner-only field populated. NO credential touched.
- Numbering: WS-HARDEN-1 (W1–W4); GOV-23 remains reserved for the next governance cycle.
- Evidence: scratch `00/` captures; pre-commit battery at dirty tree; staged scans; commit message in house style; at-commit capture; worklog append; report `docs/active/WS_HARDEN_1_REPORT_2026-10-27.md`; STATUS/CHANGELOG/INDEX updates.
