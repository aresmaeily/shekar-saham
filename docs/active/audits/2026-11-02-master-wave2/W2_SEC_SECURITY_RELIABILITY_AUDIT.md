# W2-SEC — SECURITY & RELIABILITY AUDIT (Task W2-SEC, MASTER-WAVE-2)

- **Repository:** `/home/z/my-project/RADAR_BOURSE/repo`
- **Baseline audited:** `main` @ `7c225cb1ce2771473f1f646be9c4282348ea7657` (HEAD verified at cycle open AND at cycle close; tree hash of tracked files unchanged)
- **Auditor:** W2-SEC Security & Reliability auditor (read-only mandate; directive §7 + §13.8)
- **Method:** every claim below carries file:line evidence read at HEAD; targeted greps over `git ls-files` (497 tracked files); focused read-only pytest runs via the repo venv (`backend/`), counts recorded verbatim.
- **Repo-side mutation:** NONE (verified before/after: `git status --porcelain` identical — only the pre-existing untracked bootstrap set `.claude/`, `CLAUDE.md`, `docs/governance/PROJECT_EXECUTION_STATE.md`, `docs/governance/evidence/`, `scripts/r13_owner_repo_setup.sh`, `scripts/validate_bootstrap_config.py`; zero tracked modifications; HEAD byte-identical).

**Overall posture verdict: SOUND / GOVERNANCE-ENFORCED.** All owner directive boundaries audited are mechanically enforced at HEAD, not assumed. Zero CRITICAL, zero HIGH findings. Two MEDIUM hardening findings (default all-interfaces binding in launchers; missing explicit least-privilege blocks in GitHub workflows). The product remains Synthetic/Paper-only by construction: verified-LIVE is un-mintable in this repository, AI-2 is gated at four independent layers, alert egress is in-product-only with default-ENGAGED kill switches, and the only retention-delete paths in the codebase are the four namespaced `alert_ops_*` D-AI-30 deletes.

---

## Dimension 1 — Secrets hygiene

**Verdict: PASS (no committed secrets). Findings: 2 LOW, 3 INFO.**

| # | Severity | Finding | Evidence |
|---|---|---|---|
| 1.1 | INFO | No high-signal secret formats in any tracked file: AKIA, PEM/PRIVATE-KEY blocks, Slack/Discord/Telegram webhook URLs with real tokens, OpenAI `sk-`, Google `AIza`, GitHub `ghp_`/`github_pat_` — **zero hits** across 497 tracked files | pattern sweep over `git ls-files -z | xargs grep` at HEAD (empty result) |
| 1.2 | INFO | No literal credential assignments in tracked non-test code (`(password\|secret\|token\|api_key)\s*=\s*"…≥12 chars"` sweep, placeholder/env-call filtered) — zero hits | same sweep; test-file literals are clearly synthetic fixtures (e.g. `backend/tests/test_ai2_service.py:305` `"super-secret-ai2-key-987"` — test-only, previously documented in CONSOLGOV13 record) |
| 1.3 | INFO | Only env-shaped file tracked is `.env.example` with empty/placeholder values (`BRSAPI_KEY=your_key_here` commented, `FERNET_KEY=` empty, `PRIVATE_PASSWORD=change-me-strong-password`) | `.env.example` lines 13, 26, 28, 38 |
| 1.4 | INFO | `.gitignore` covers `.env`, `*.env.local`, and repo-root `/data/` runtime artifacts (`.db`, `-wal`, `-shm`, `.json`) | `.gitignore` lines 10–11, 19–24 |
| 1.5 | LOW | `.gitignore` does not cover sibling env variants (`.env.production`, `.env.local` without the `*.env.local` shape) nor key-material patterns (`*.key`, `*.pem`). Additive gap only — no such file is tracked today (verified by `git ls-files \| grep -iE '\.env\|\.key\|\.pem'` → only `.env.example`) | `.gitignore` whole file; `git ls-files` scan |
| 1.6 | PASS | **FERNET_KEY ephemeral default is WARNING+CRITICAL logged, not silent**: `crypto.py:49` `logger.warning("No FERNET_KEY/API_KEY - using ephemeral singleton key")` at first use; `main.py:84-88` `logger.critical("🔴 FERNET_KEY تنظیم نشده — کلید رمزنگاری موقت (ephemeral) است…")` at every startup. Production additionally **fail-closed**: `security.py:254-255` raises `RuntimeError("Production requires stable FERNET_KEY or API_KEY…")` | `backend/app/core/crypto.py:44-51`; `backend/app/main.py:80-88`; `backend/app/core/security.py:251-257` |
| 1.7 | LOW | `decrypt_token` legacy-plain heuristic can return a plaintext token that was never encrypted (documented migration behavior; `len>10 and ("bot" in … or ":" in … or len>30)`) — fail-open only for pre-encryption records; new writes are always Fernet-encrypted (`notifier.py:167-175` encrypt-on-save) | `backend/app/core/crypto.py:78-90`; `backend/app/services/notifier.py:167-175` |
| 1.8 | INFO | High-entropy 64-hex literals in `scripts/g2_acceptance_battery.py:64-76` are SHA-256 evidence digests, not credentials | inspected in context |

No real provider credentials exist anywhere in the tracked tree.

---

## Dimension 2 — External attack surface

**Verdict: ACCEPTABLE with 1 MEDIUM. Findings: 1 MEDIUM, 2 LOW, 4 INFO.**

### 2.a Full route enumeration (backend/app/api/* + main.py)

Routers: `routes.py` (main `/api/*`), `excellent.py`, `chart.py`, `forex.py`, `auth.py` (`/api/auth/*`), `alert_ops.py` (`/api/alerts/*`); plus in `main.py`: `GET /`, `GET /symbol[/{l18}]`, `GET /favicon.ico`, `WS /ws/live`, static mount `/static`.

**Auth posture (defense in depth = global middleware `main.py:226-280` + route-level `require_api_key`):**

| Group | Routes | Posture |
|---|---|---|
| Always-public | `/api/health` (routes.py:87), `/api/status` (108), `/api/live/status` (832), `/docs` `/openapi.json` `/redoc` (disabled in prod, main.py:147-149), `/static`, `/`, `/symbol*` | `PUBLIC_PREFIXES` security.py:23-34; probe handlers redact details (main.py:238-239) |
| Open by default, auth-gated when API_KEY/PRIVATE_MODE set | all read routes: overview/analyze/signals/hot-money/market-game/industries/symbol/history/market-map/fundamentals/filter*/search/trade-hot/confluence/alerts, `/api/alerts/inbox` (alert_ops.py:43), `/api/alerts/ops/status` (58), excellent.py reads, chart.py reads, forex.py reads, ai/* GET reads | middleware `need` logic main.py:233-246 |
| **API-key/session gated always when configured** (route-level `SENSITIVE_DEPENDENCIES`) | portfolio CRUD (routes.py:274-299), config/thresholds (301-318), filter/saved CRUD (428-451), notify config/test/log (804-827), backtest run/history (748-775), confluence/notify-now (889), ai/* POST (556-607 `AI_DEPENDENCIES`), **alert ops kill-switch/dispatch/dead-letter (alert_ops.py:63-83)** | `SENSITIVE_PREFIXES` security.py:37-45 incl. `/api/alerts/ops` (GOV-41 D-AI-30 comment); `require_api_key` security.py:191-223 |
| Login | `POST /api/auth/login` (auth.py:32) — always open by design; timing-safe compare (auth.py:44), HttpOnly SameSite=Strict cookie (auth.py:49-57), secure flag per config | auth.py |
| WebSocket | `/ws/live` (main.py:290) — auth enforced only when `auth_required`/`private_mode`; per-message ping/refresh handled | main.py:290-336 |

**No route binds its own host; the binding question is 2.b.** No route performs file-writes from user input; portfolio symbols/filter names are plain strings persisted via parameterized SQL.

### 2.b Binding defaults

| # | Severity | Finding | Evidence |
|---|---|---|---|
| 2.1 | **MEDIUM** | **0.0.0.0 default binding in four launcher surfaces** (prior-record finding CONFIRMED still present at HEAD): `config.py:29` `host: str = os.getenv("HOST", "0.0.0.0")` (used by `main.py:390-398` uvicorn.run); `start.sh:9` `export HOST="${HOST:-0.0.0.0}"`; `scripts/windows/start.ps1` param `$HostAddress = "0.0.0.0"` (documented nuance in `P343_INSTALL_CHECKLIST.md:43`, which mandates `-HostAddress 127.0.0.1`); `install.sh:44` `--host 0.0.0.0`. Combined with the auth-off default (`auth_required` False unless `API_KEY`/`PRIVATE_MODE`, config.py:99), a naive launch exposes the API to the network with read surfaces open. Mitigations present: rate limiter on (default), CORS localhost-only, security headers, login brute-force caps. `entrypoint.sh` default `0.0.0.0` is container-appropriate (Docker port mapping governs exposure). | cited inline |
| 2.2 | LOW | Windows boot path used by CI boots `127.0.0.1` (windows.yml:54,93,140) — good; only the interactive `start.ps1` default is all-interfaces | `.github/workflows/windows.yml` |
| 2.3 | LOW | **WS auth accepts `api_key`/`token` as query parameters** (main.py:294-297, logged at 296-297) — query strings leak into proxy/access logs; HTTP paths deliberately removed query-param keys (security.py:67-84 "no query param leak"). WS needs it for browser clients; keep, but document as accepted risk | `backend/app/main.py:294-297` |
| 2.4 | INFO | Electron shell hardened: `nodeIntegration: false`, `contextIsolation: true`, `enableRemoteModule: false` (electron/main.js:14-18); navigation/redirects/window-open restricted to the configured backend origin with external targets punted to OS browser (main.js:33-63). DevTools menu enabled (main.js:77) — acceptable for owner desktop build | `electron/main.js` |

### 2.c CORS & headers & rate limiting

- Default CORS = localhost only (`config.py:101`); wildcard forced back to localhost outside debug with WARNING (`main.py:188-190`) and CRITICAL log at startup (`main.py:102`); `allow_credentials` only when origins are explicit (`main.py:191`).
- OWASP headers + strict CSP (`security.py:260-290`): `default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`; HSTS only on HTTPS.
- Rate limiting default ON (`config.py:132`), per-path buckets incl. login 5/min + 20/hour (`rate_limiter.py:70-79`); `TRUST_PROXY` default 0 with XFF spoofing warning (`config.py:93-95`, `rate_limiter.py:100-110`).
- CSRF depth-defense: cross-origin POST/PUT/PATCH/DELETE with mismatched Origin blocked (`main.py:264-279`).
- **Input validation:** user-facing query params bounded via pydantic `Query(ge/le/pattern)` (routes.py:163-166, 198, 242-244, 254-256, 267-269, 322, 344-346, 354-355, 375-377, 463; alert_ops.py:45-46, 78; KillSwitchRequest `Field(pattern="^(ENGAGED\|RELEASED)$")` alert_ops.py:37-40); filter DSL validated before evaluation (`market_service.py:795-799` via `validate_filter`); validation errors returned without echoing user input (`main.py:163-174`).

---

## Dimension 3 — Fail-closed behavior

**Verdict: PASS — all ladders enforced mechanically. Findings: 0 above INFO.**

| # | Severity | Finding | Evidence |
|---|---|---|---|
| 3.1 | PASS/INFO | **Trust/verification ladder**: `verified=False` hardcoded — "This environment has no live-verification boundary" (`config.py:284`, context 281-289); `is_verified_live` requires state==live AND is_live AND live_verified all explicitly true (`config.py:156-167`); `TRUST_LEVEL=live` override is ignored ("Configuration ≠ market evidence", `config.py:183-185`); live-class source without verification is downgraded to `trust_level=mixed` (`config.py:286-287`); future timestamps and stale age force mixed/stale (`config.py:265-279`). `live_verified=True` passed as an argument is ignored by design (`config.py:249-253`). | cited |
| 3.2 | PASS/INFO | **G2 runtime gate fail-closed** (`domain/g2_gate.py:206-274`): MISSING/MALFORMED/STALE/CONTRADICTORY/UNVERIFIABLE all deny; the evaluator is pure, never flips a gate, never executes (module docstring 1-59). Tracked state `docs/active/G2_GATE_STATE.json` verdict=PASSED binds `convened_review_commit=9e7c6a2…` ≠ running HEAD 7c225cb… and `RADAR_RUNTIME_COMMIT` defaults empty (`config.py:117-123`) → at this baseline the gate refuses any real-data execution as `gate_state_stale` (fail-closed), and the state's own notes state AI-2 is NOT enabled. `execution_mode()` returns SYNTHETIC_OR_PAPER unless `live_verified` (`g2_gate.py:280-287`). | cited |
| 3.3 | PASS/INFO | **False-fresh guard at HEAD = per-cycle token (Q-1 fix shape verified)**: `cycle_degraded = False` local token per refresh cycle (`market_service.py:381`), set only when a fetch exception falls back to recycled symbols (`:398`), consumed in Phase 3 under lock so the PREVIOUS fetch timestamp is preserved (`:482-487` "False-fresh guard… instead of masking the failure with a fresh stamp"); `self._fetch_degraded` retained only as an observability mirror (`:385,399,487`). Proven by `tests/test_refresh_degraded_token_concurrency.py` (3 tests, SeamLock one-yield injection) — **green at HEAD**. | `backend/app/services/market_service.py:373-401,478-489` |
| 3.4 | PASS/INFO | **Provider outage path**: fetch exception → recycled last symbols + degraded cycle (3.3); no symbols at all → raise (`market_service.py:400-401`); cache fallback loads `market_cache.json` with source "cache" → classified `mixed` (`providers.py:503-529`; `config.py:200-202`); mock fallback labeled `mock_fallback` (`providers.py:325-327`). Trust labels honestly degraded (stale/unavailable) rather than fresh-stamped. | cited |
| 3.5 | PASS/INFO | **AI-2 gated at four independent layers**: (1) config default `AI2_ENABLED=0` (`config.py:111`); (2) service refuses when disabled (`ai2_service.py:417-418` "AI-2 is disabled (AI2_ENABLED=0); nothing was executed"); (3) real-data execution additionally requires `is_verified_live(data_trust)` (`ai2_service.py:12,253`) which is un-mintable (3.1); (4) **API absence — zero `ai2` references under `backend/app/api/`** (grep empty). The AI-2 research loop forces `execution_label = "SYNTHETIC_OR_PAPER"` for `executed_shadow` outcomes and LEDGERs (never COMPLETED) them (`ai2_research_loop.py:449-458`, docstring 14-18). D-AI-29/30/31 posture: not activated by inference — no config surface exists for any of them (grep over `config.py`/`runtime_settings.py` empty; §6 below). | cited |
| 3.6 | PASS/INFO | **AI-5 kill switch default ENGAGED**: `kill_switch: KillSwitchState = "ENGAGED"` (`domain/proactive_research.py:102`), `production_mutation: Literal[False] = False` (:100), `financial_authority="DETERMINISTIC_ONLY"` (:101). | cited |
| 3.7 | PASS/INFO | **Alert-ops kill switches default ENGAGED and fail closed**: both job switches seeded `"ENGAGED"` at migration (`alert_ops_store.py:162,170`); `kill_switch_gate` refuses on missing/malformed/inconsistent states and on ENGAGED (`domain/alert_operations.py:245-261`); every background tick and manual dispatch passes through it (`alert_operations.py` dispatch/freshness paths). | cited |

---

## Dimension 4 — Data-trust & integrity

**Verdict: PASS. Findings: 0 above INFO.**

| # | Severity | Finding | Evidence |
|---|---|---|---|
| 4.1 | PASS/INFO | **SQLite store**: WAL + `synchronous=NORMAL` per connection (`store.py:36-37`); global `threading.RLock` serializes all access (`store.py:18,31-45`); commit/rollback discipline with close in `finally`. All SQL parameterized (no string-interpolated user input found anywhere in `store.py`/`alert_ops_store.py`). | `backend/app/data/store.py` |
| 4.2 | PASS/INFO | **Backup path**: `Store.backup(keep=7)` — `wal_checkpoint(TRUNCATE)` then locked `copy2` to `data/backups/shekar-<stamp>.db`, prune to keep=7 (`store.py:62-86`); daily-at-startup trigger with 86400s guard (`main.py:91-98`). | cited |
| 4.3 | PASS/INFO | **user_version-guarded migrations**: `PRAGMA user_version` read; ordered migration list executed only when `current < version`; version stamped after each (`store.py:48-60`). Additive-only migration surface. | cited |
| 4.4 | PASS/INFO | **Alert-ops archive-rename rollback**: `rollback()` renames each `alert_ops_*` table to `*_rollback_archive` — records PRESERVED, never destroyed (decision 10); `restore_from_archive()` reverses (`alert_ops_store.py:7-9,173-204`). | cited |
| 4.5 | PASS/INFO | **AI-3 append-only + fail-closed + no-purge**: protocol structurally forbids update/delete/purge/rewrite members and any retention-expiry for episodic research evidence (`research_memory_store.py:27-56,188-247`); `verify_integrity` returns refusal records, never raises; missing expected entries are treated as append-only violations (`:385-443`). **New test-layer JSONL adapter has ZERO production wiring**: lives at `backend/tests/research_memory_jsonl_reference.py` ("TEST-LAYER ONLY… Zero production wiring… no `app.core`/`app.data` reference, no config surface", lines 1-9, 81); grep confirms `research_memory_store`/`research_memory_jsonl_reference` are imported only by files under `backend/tests/`; AST-level proof pinned by test RT-6 (`test_ai3_jsonl_reference_adapter.py`, green). D1–D7 remain PENDING — no engine decision exercised (`docs/active/AI3_PERSISTENCE_DECISION_PACKET.md` per MASTER_WAVE1 §3). | cited |
| 4.6 | PASS/INFO | **Purge boundary (historical evidence preservation)**: the ONLY retention-delete paths in the codebase are the four namespaced D-AI-30 deletes — `DELETE FROM alert_ops_outbox/alert_ops_inbox/alert_ops_dead_letter/alert_ops_audit` (`alert_ops_store.py:526-537`), invoked solely by `AlertOperationsService.purge_expired_records` (`alert_operations.py:527-531`) which is not wired to any route or the background loop (no caller besides tests). `Store.prune_old` (`store.py:335-342`) deletes only market-runtime tables (symbol_ticks/snapshots/big_moves at `HISTORY_KEEP_HOURS`; alerts at 7d) — **no research/episodic evidence table exists in SQLite at all** (in-memory contracts only), so evidence preservation is structural. | cited |
| 4.7 | PASS/INFO | **Market cache rebuildability**: `market_cache.json` is a write-through convenience cache; on live-source failure it is read back as source "cache"→mixed (`providers.py:503-529`) and is rebuilt by every successful refresh; its loss degrades nothing structural. | cited |
| 4.8 | PASS/INFO | **`history_snapshots.jsonl` declared-but-unused**: the setting exists (`config.py:141` `history_path`) and nothing in `backend/app/` reads or writes it (grep: single hit). Honest dead surface. | cited |

---

## Dimension 5 — Reliability / concurrency

**Verdict: PASS with 3 LOW. Findings: 3 LOW, 3 INFO.**

| # | Severity | Finding | Evidence |
|---|---|---|---|
| 5.1 | PASS/INFO | **refresh() lock discipline**: 4-phase — Phase 0 fast check under `self._lock` (`market_service.py:364-369`); network fetch OUTSIDE lock (`:382-401`); heavy CPU outside (`:407-476`); Phase 3 quick state update under lock incl. degraded-token consumption and persist (`:478-515`); broadcast/notifier outside (`:517-543`). Per-cycle degraded token proven under interleaving (SeamLock test, §3.3). | cited |
| 5.2 | PASS/INFO | **Fund cache bounded**: `_fund_cache_max = 200` with oldest-20% eviction and TTL 300s (`market_service.py:66-67,152-177`; `config.py:126`). | cited |
| 5.3 | PASS/INFO | **Prune interval**: hourly (`_prune_interval=3600`, `market_service.py:69,323-331`) instead of per-refresh; `_seen_alert_keys` bounded 5000→2000 (`:321-322`). | cited |
| 5.4 | PASS/INFO | **Outbox dispatcher budgets/kill switches/expiry drop**: budgets enforced BEFORE any delivery with audited refusals (`alert_operations.py:143-207`); expiry drop before delivery (`:185-191`); OWNER_BUDGETS owner-pinned with deviation `ValueError` guards — freshness 1800s, global jobs 30/h, kind 6/h, channel 10/h, burst 3/min, dedup 24h, **max attempts 3, retry delays (30,120)s**, retention 90d, channel `IN_PRODUCT_INBOX` (`domain/alert_operations.py:59-139`); dispatcher self-failure visible, never self-alerts (`:318-325,346-352,589-596`). | cited |
| 5.5 | PASS/INFO | **Retry/dedup semantics verified**: 3 attempts with 30s/120s backoff then dead-letter (`alert_operations.py:246-263`; refusal of any deviation from `(30,120)` and 24h dedup at `domain/alert_operations.py:119-121`). | cited |
| 5.6 | PASS/INFO | **Background task shutdown paths**: lifespan stops alert-ops loop and market poll loop with cancel+await (`main.py:120-134`; `market_service.py:98-109`; `alert_operations.py:574-586`); alert-ops loop additionally kill-switch/budget-gated every tick and `ALERT_OPS_LOOP` env opt-out (`alert_operations.py:546-555`). | cited |
| 5.7 | LOW | **Rate-limiter outer dicts are unbounded across distinct client IPs**: `defaultdict(deque)` buckets are cleaned per-key only when the same key is hit again; stale IP keys are never evicted from `general`/`path_specific` (`rate_limiter.py:23-29,83-98`). Under internet exposure with spoofed/rotated IPs this grows without bound (TRUST_PROXY=0 mitigates trivial XFF spoofing; the gap is sustained distinct-socket IP diversity). Additive bound (periodic sweep) is a safe hardening candidate. | `backend/app/core/rate_limiter.py` |
| 5.8 | LOW | **`notify_log` and `backtest_runs` tables have no prune path** (`store.py:180-196` create; `prune_old` :335-342 does not cover them) — slow unbounded growth. NOTE: adding retention deletes for these tables would create NEW purge paths, which is owner-gated under the "only alert_ops_* deletes" boundary (see §6/candidates). | cited |
| 5.9 | LOW | Notifier dedupe dict bounded (2000, `notifier.py:172-175`) — bounded, but its cleanup filter `t >= now - cooldown*2` can keep keys whose cooldown was raised via config; negligible. Noted for completeness with 5.7 as the pattern-class. | cited |
| 5.10 | INFO | ws_hub `_clients` is a live-socket set pruned on disconnect/dead-send (`ws_hub.py:27-68`) — bounded by actual connections; broadcast serializes under lock, sends outside lock snapshot. | cited |

---

## Dimension 6 — Governance-boundary mechanical sweep

**Verdict: PASS — every boundary enforced at HEAD. Findings: 0.**

| Boundary | Mechanical proof at HEAD |
|---|---|
| No live trading / order execution | 14-pattern sweep (`place_order|submit_order|buy_order|sell_order|execute_trade|order_execution|market_order|limit_order|open_position|close_position|broker_(api\|client)|brokerage|trade_execution|real_money|wallet|payment|checkout`) over `backend/app` → **zero functional hits**; single `live_trading` occurrence repo-wide is the negative attestation `quant_safety{"live_trading": False}` at **`app/engines/backtest.py:483`** (with sibling notes "No broker/live trading integration is included", backtest.py:476). |
| No autonomous production mutation | AI-5 model pins `production_mutation: Literal[False]` (`proactive_research.py:100`); alert-ops writes only the seven `alert_ops_*` tables (`alert_ops_store.py` schema; purge = the four deletes, 4.6); no imports of trading/market modules in alert_ops/research paths. |
| No self-modifying production logic / no autonomous promotion | Runtime settings surface is a numeric-threshold whitelist with int/float coercion only (`runtime_settings.py:66-90` EDITABLE_KEYS); no env/var/config gate can be flipped from any route; G2 gate "NEVER flips a gate and NEVER executes anything" (`g2_gate.py:17-19`); `governed_acceptance` refuses non-COMPLETED runs and COMPLETED is un-mintable without an artifact (CONSOL_NEXT §6, test-pinned). |
| No permission self-escalation | No route creates/changes credentials; auth is read-only against env-provided secrets; kill-switch RELEASED transitions require the API key (route-gated, alert_ops.py:63) — i.e. an owner act, audited (`alert_operations.py:494-513` audit `KILL_SWITCH_TRANSITION`). |
| No external alert egress unless authorized | Egress inventory at HEAD: market-data GETs (tsetmc/brsapi `providers.py:344,415`; forex okx/kucoin `forex_provider.py:265,298`), AI provider HTTPS only when `AI_EXECUTE=1` AND server-side key present (`ai_provider.py:85,239,313`; default off), and notifier Telegram/Bale — gated by `notify_enabled=0` default (`config.py:75`; `notifier.py:87-90,346`) AND the un-mintable verified-live / explicit `allow_synthetic` trust gate (`notifier.py:356-365`). `ws_hub` is purely in-process fan-out (`ws_hub.py`). D-AI-30 governed-alert channel is the type-closed `Literal["IN_PRODUCT_INBOX"]` — no notifier/ws_hub edge (AST no-edge proof test, `test_p5p6_integration_delivery_surfaces.py`, green). |
| D-AI-29/30/31 not activated by inference | No config surface for D-AI-29/31 (grep over `config.py`/`runtime_settings.py`: zero toggles; full env-var inventory in `config.py:19-138` contains no AI-29/31/autonomy flags); D-AI-30 is implemented exactly as delivered (in-product only, kill switches default ENGAGED) and its remaining wiring (E6 confluence→governed-admission, scheduler runtime) is recorded OWNER-GATED, not invented (CONSOL_NEXT §3, §11). |

---

## Dimension 7 — Dependency & supply-chain

**Verdict: ACCEPTABLE with 1 MEDIUM + 3 LOW. Findings: 1 MEDIUM, 3 LOW, 2 INFO.**

| # | Severity | Finding | Evidence |
|---|---|---|---|
| 7.1 | PASS/INFO | `backend/requirements.txt`: 16 runtime deps pinned exact (`fastapi==0.141.1`, `cryptography==50.0.0`, `numpy==2.2.1`, …); only dev tools use `>=` (pytest/pytest-asyncio/pyflakes). Comment records `pip-audit → No known vulnerabilities`. | `backend/requirements.txt:1-21` |
| 7.2 | **MEDIUM** | **Neither workflow declares a `permissions:` block** → jobs run with the repository default GITHUB_TOKEN permissions (potentially read/write depending on repo settings) instead of least-privilege `contents: read`. No secrets are used and no deploy steps exist, which caps the exposure, but the least-privilege expectation in the audit mandate is NOT met. | `.github/workflows/ci.yml` (whole file — no `permissions:` key), `.github/workflows/windows.yml` (same) |
| 7.3 | LOW | Third-party (here: first-party GitHub) actions pinned by tag, not SHA: `actions/checkout@v4`, `actions/setup-python@v5` (ci.yml:12,20; windows.yml:30,41), `actions/upload-artifact@v4` (windows.yml:190). Tag pinning is mutable; SHA pinning is the hardening step. | cited |
| 7.4 | LOW | Docker base `python:3.13-slim` pinned by tag only, not digest (`Dockerfile:4`). | cited |
| 7.5 | INFO | **Python 3.12/3.13 drift note CONFIRMED**: ci.yml uses 3.13 (`ci.yml:22`), windows.yml uses 3.12 (`windows.yml:43`), Dockerfile is 3.13-slim, local venv is 3.12 (`repo/.venv`, python3.12 site-packages observed). Suites pass on both in evidence, but Windows validation never exercises 3.13. No root `pyproject.toml`/`uv.lock` exists in this repo (checked; not present — the drift lives in workflow/job matrices only). | cited |
| 7.6 | INFO | Electron `devDependencies` are caret ranges (`electron ^28.0.0`, `electron-builder ^24.0.0`) with **no committed lockfile** → non-reproducible desktop builds; runtime `dependencies: {}` (no third-party runtime code shipped). | `electron/package.json` |
| 7.7 | PASS/INFO | CI runs pip-audit on every push (ci.yml:38-42) and pyflakes gate (ci.yml:28-32); windows.yml is fail-closed on boot logs and trust posture (windows.yml:157-177 asserts ephemeral-key warning present and `live_verified` not true). | cited |

---

## Dimension 8 — Known-findings ledger check

**Verdict: CONSISTENT — Q-1 FIXED with supersede note; F1 open by design; no regression on closed items.**

| Item | Status at HEAD | Evidence |
|---|---|---|
| **Q-1** (per-cycle degraded token) | **FIXED at HEAD** — CONSOL_NEXT §8 disposition (ANALYZED_AND_DEFERRED) is preserved verbatim and explicitly **superseded** by MASTER_WAVE1 §2: "the deferred state is superseded by a FIXED_AND_REGRESSION-PINNED disposition" with pre-fix reproduction (test FAILED on shared-attribute shape) and post-fix PASS; fix shape = per-cycle local token + observability mirror; +3 concurrency tests green at HEAD in this audit run. | `docs/active/CONSOL_NEXT_EXECUTION_RECORD_2026-11-02.md:241` (superseded text preserved); `docs/active/MASTER_WAVE1_EXECUTION_RECORD_2026-11-02.md:25-75` (reproduction + supersede note at :67-75); `market_service.py:373-401,478-489`; `test_refresh_degraded_token_concurrency.py` 3/3 green |
| **F1** (HoldoutAttestation cross-field consistency not type-enforced) | **STILL OPEN, correctly** — recorded as LOW hardening candidate in CONSOL_NEXT §5 and queued in §11.7; per directive this audit does NOT fix it. No regression: the attestation-only-via-passing-path sweep remains green in the full-battery record. | CONSOL_NEXT §5 (:148-151), §11 (:285-288) |
| **F4** (MA-1 "real runs" phrasing = runs of the real engine over synthetic inputs) | Documented currency correction, record preserved verbatim (forward-only). | CONSOL_NEXT §5 (:151-155) |
| Closed items Q-2..Q-7 | No regression: Q-2 CLOSED_NO_CHANGE, Q-3..Q-5 NOT_VERIFIED identity preserved, Q-6/Q-7 OWNER-GATED comparative phrasing unchanged (README.md:3; watchlist_excellent.js:2,53 — confirmed still owner-flagged, not "fixed" repo-side). | CONSOL_NEXT §8 (:242-244) |

---

## Test evidence (read-only runs this audit, exact counts)

Environment: `/home/z/my-project/RADAR_BOURSE/repo/.venv/bin/python` (3.12), `backend/` cwd, `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`, conftest pins `DATA_SOURCE=mock`/`BRSAPI_KEY=""` (offline-deterministic, no network).

| Suite | Result |
|---|---|
| **D-AI-30 acceptance**: `tests/test_dai30_alert_operations.py` | **79 passed** (2 warnings: starlette deprecation) |
| **P5/P6 integration (4 files)**: `test_p5p6_governed_alerts.py` + `test_p5p6_integration_alert_ops_api.py` + `test_p5p6_integration_delivery_surfaces.py` + `test_p5p6_integration_store_purge_boundary.py` | **56 passed** (40 + 4 + 8 + 4) |
| Combined run of the five files above | **135 passed**, 0 failed, 0 skipped, 2 warnings, in 1.67s |
| Q-1 fix + false-fresh + AI-3 adapter/scaffold: `test_refresh_degraded_token_concurrency.py` (3) + `test_refresh_false_fresh.py` (3) + `test_ai3_jsonl_reference_adapter.py` (9) + `test_ai3_acceptance_scaffold.py` (44) | **59 passed** |

Full-battery counts cited from the records (not re-run whole in this audit to keep the run read-only and bounded): 1436 passed / 1 skipped at the wave HEAD (MASTER_WAVE1 §5).

---

## Findings requiring code change

| # | Finding | Severity | Class | Note |
|---|---|---|---|---|
| C-1 | Add explicit `permissions: contents: read` to both workflow jobs (and `packages: none`) | MEDIUM | **AUTHORIZED-REPO-SIDE** | Purely additive workflow YAML hardening; no behavior change to app code; directly satisfies the mandate's least-privilege expectation |
| C-2 | Flip launcher default binding to `127.0.0.1` with explicit `HOST=0.0.0.0`/`-HostAddress 0.0.0.0` opt-in (config.py:29 + start.sh:9 + start.ps1 + install.sh:44) | MEDIUM | **OWNER-GATED** | Technically repo-side, but it changes the documented launch posture that `P343_INSTALL_CHECKLIST.md` and prior evidence runs are bound to; needs a dated owner decision (checklist currently mandates explicit `127.0.0.1` override instead) |
| C-3 | Pin GitHub Actions by commit SHA (checkout/setup-python/upload-artifact) | LOW | **AUTHORIZED-REPO-SIDE** | Additive hardening; keep version comments |
| C-4 | Digest-pin Docker base image (`python:3.13-slim@sha256:…`) | LOW | **AUTHORIZED-REPO-SIDE** | Additive; requires one-time digest resolution at fix time |
| C-5 | Additive `.gitignore` entries: `.env.*`, `*.key`, `*.pem` (+ optionally `data/backups/` explicit) | LOW | **AUTHORIZED-REPO-SIDE** | Additive ignore patterns only |
| C-6 | Rate-limiter: periodic stale-key sweep or max-IP bound for `general`/`path_specific` dicts | LOW | **AUTHORIZED-REPO-SIDE** | Additive in-memory bound; no governance surface touched |
| C-7 | Retention/prune for `notify_log` + `backtest_runs` tables | LOW | **OWNER-GATED** | Introduces NEW `DELETE` paths — the directive currently allows ONLY the `alert_ops_*` retention deletes; requires an owner ruling that these runtime logs are not preserved evidence |
| C-8 | WS `api_key`/`token` query-param auth (main.py:294-297) | LOW | **OWNER-GATED** | Deprecation changes browser-client capability; document-as-accepted-risk alternative |
| C-9 | `crypto.decrypt_token` legacy plain-token heuristic | LOW | **OWNER-GATED** | Tightening breaks legacy token migration path; needs owner decision + migration plan |
| C-10 | F1 holdout-attestation type-level validator | LOW | **OWNER-GATED** | Explicitly recorded hardening candidate (CONSOL_NEXT §11.7); directive says audit-only this cycle — NOT fixed here |
| C-11 | Electron lockfile (`package-lock.json`) + caret→exact pins | LOW | **AUTHORIZED-REPO-SIDE** | Reproducibility only; no runtime deps affected |
| C-12 | Reconcile Python version drift (CI 3.13 vs Windows 3.12 vs Docker 3.13) | INFO | **AUTHORIZED-REPO-SIDE** | Add one 3.13 leg or align windows.yml; documentation-level |

Explicitly **not** candidates: anything touching the verified=False constant, AI2_ENABLED default, kill-switch defaults, purge surface, G2 gate semantics, or episodic-evidence preservation — all are owner-authority surfaces functioning as designed.

---

## Not verified (out of reach of this sandbox)

1. **Windows hosted-runner internals** — windows.yml has NOT executed on the remote for this baseline (blocker B8 note, windows.yml:15-17); CI-green ≠ target-machine validation; runbook W2 icon/W3-W5 shell steps require the owner machine (windows.yml:11-13).
2. **Electron runtime sandbox on real hardware** — code-level hardening verified (main.js:14-18,33-63); actual packaging (`electron-builder` NSIS), auto-update absence, and OS-level behavior on a real Windows machine not executable here.
3. **Target-machine alpha installation** — INSTALL instruction is OWNER-GATED and NOT ISSUED (CONSOL_NEXT §11.1); not simulated.
4. **GitHub repo-level settings** — actual default workflow token permissions, branch protection, and deploy-key scope on the remote (cannot query GitHub from this sandbox); finding 7.2 is judged from workflow files alone.
5. **Live-provider behavior** — tsetmc/brsapi/okx/kucoin endpoints were never contacted (offline-deterministic conftest; read-only mandate); egress inventory is code-level.
6. **Production CORS/proxy deployment** — `CORS_ORIGINS`, reverse-proxy, and TLS termination in any real deployment are environment-owned, not in-repo.
7. **Full battery re-run** — the 1436/1s full-battery count is cited from the wave record, not re-executed end-to-end in this audit (focused mandated suites were run: 135 + 59 green).
8. **`docs/governance/evidence/` untracked corpus contents** — present in workspace but untracked; integrity of the historical evidence corpus itself was not re-hashed (its protection is the no-purge boundary verified in §4.6).

---

## Appendix — severity roll-up

| Dimension | Worst finding | Findings (C/H/M/L/I) |
|---|---|---|
| D1 Secrets hygiene | LOW (.gitignore variants gap; decrypt heuristic) | 0/0/0/2/3+ |
| D2 External attack surface | **MEDIUM (0.0.0.0 default binding, 4 launchers)** | 0/0/1/2/2 |
| D3 Fail-closed behavior | INFO (all enforced) | 0/0/0/0/7 |
| D4 Data-trust & integrity | INFO (all enforced) | 0/0/0/0/8 |
| D5 Reliability/concurrency | LOW (rate-limiter dict growth; unpruned log tables) | 0/0/0/3/4 |
| D6 Governance boundaries | INFO (all enforced) | 0/0/0/0/6 |
| D7 Dependency & supply-chain | **MEDIUM (no `permissions:` block in workflows)** | 0/0/1/3/2 |
| D8 Known-findings ledger | INFO (consistent) | 0/0/0/0/5 |

**Totals: CRITICAL 0 · HIGH 0 · MEDIUM 2 · LOW 8 · INFO 32** (counts as row-items above; PASS/INFO evidence rows included in INFO where applicable).

**Authorized-repo-side fixable now (additive, no governance surface touched):** C-1 (workflow permissions), C-3 (action SHA pins), C-4 (base-image digest pin), C-5 (.gitignore additions), C-6 (rate-limiter stale-key bound), C-11 (electron lockfile), C-12 (Python version alignment).

**Repo untouched: CONFIRMED** — `git rev-parse HEAD` = `7c225cb1ce2771473f1f646be9c4282348ea7657` before and after; `git status --porcelain` identical before/after (untracked bootstrap set only); zero tracked-file modifications; no git state changes (no add/commit/checkout/stash). Suites green: D-AI-30 acceptance **79 passed**; P5/P6 integration **56 passed** (135 combined); Q-1/AI-3 evidence suites **59 passed**.
