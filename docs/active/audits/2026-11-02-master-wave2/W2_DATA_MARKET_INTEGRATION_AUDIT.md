# W2-DATA — Data & Market Integration Audit (read-only)

- **Auditor:** W2-DATA (Data & Market Integration auditor, temporary engineering team)
- **Repo:** `/home/z/my-project/RADAR_BOURSE/repo`
- **HEAD audited:** `7c225cb1ce2771473f1f646be9c4282348ea7657` (main) — unchanged during audit (verified pre/post)
- **Directive basis:** §6 "Reproducible data and market integration" + §13
- **Repo modifications:** NONE (tracked tree byte-identical before/after; only pre-existing untracked governance files present; test runs touched only gitignored `/data/` runtime artifacts)
- **Test execution:** `../.venv/bin/python -m pytest` from `backend/` (read-only runner, 3 batches, **163 passed / 0 failed / 0 skipped**)

---

## 0. One-line posture verdict

**MOSTLY-SOUND, one posture gap:** the trust/verification machine is genuinely fail-closed (verified-LIVE is un-mintable in this repo) and the Q-1 false-fresh fix is correctly implemented and regression-covered; but the *default* `DATA_SOURCE=auto` network posture performs live TSETMC fetches with no owner gate (HIGH), one residual cross-cycle source-label race survives beyond Q-1 (MEDIUM), and the forex layer operates entirely outside the mock posture with mislabeled "synthetic" data derived from real market patterns (MEDIUM).

---

## 1. Provider adapter inventory

| Adapter | File | Source of truth for symbols | Fetch shape | Error taxonomy | last_source / last_error | Live enablement w/o owner decision? |
|---|---|---|---|---|---|---|
| **MarketDataProvider (TSETMC)** | `backend/app/data/providers.py:392-443` | TSETMC CDN `GetMarketWatch` + 2 fallback URLs (`providers.py:394-397`); symbols = whatever rows carry `l18` (compressed keys `lva/lvc` accepted: `providers.py:130-140`) | 3 sequential GETs, first non-empty board wins; JSON then legacy `@;`-text parse | per-URL `except` → `last_error="tsetmc: {exc}"`, `continue` (`providers.py:439-442`); empty board → `[]` | `"tsetmc"` (`:427`), `"tsetmc_legacy"` (`:434`); error at `:440` | **YES — see F-1.** No key required; reached by default via `DATA_SOURCE=auto` |
| **BrsApi** | `providers.py:332-390` | `AllSymbols.php` rows, `l18`+`pl>0` gate (`:378`) | 1 GET × 2 attempts, backoff 1s/2s (`:342-355`) | no-key early return (`:334-337`); HTTP/parse fail → `last_error="brsapi: … (after 2 attempts)"`; empty → `"brsapi: empty payload"` (`:389`) | `"brsapi"` (`:384`) | Only with `BRSAPI_KEY` env (default `""`, `config.py:36`) — **key-gated, OK** |
| **Mock generator** | `providers.py:323-330` + `backend/app/data/mock_market.py:92-288` | Hard-coded 60-symbol TSE seed list (`mock_market.py:18-80`) | In-process generation; per-symbol MD5-seeded RNG re-seeded per 30s bucket (`mock_market.py:83-85`) — pseudo-deterministic | Cannot fail by design | `"mock"` / `"mock_fallback"` (`providers.py:325`) | n/a (always available) |
| **Forex/gold/crypto provider** | `backend/app/data/forex_provider.py` | Static symbol/broker tables (`:29-198`); live: Binance mirror→OKX→KuCoin→Yahoo→synthetic chain (`:558-584`) | Per-symbol OHLCV chain; range-bars built client-side (`:441-502`) | per-host `except` → warn + `[]` (`:251-253,284-286,317-319`) | Per-candle `"source"` field (`:247,281,314,372`); **no last_source/last_error state machine** | **YES — see F-5** (not gated by `DATA_SOURCE` at all) |
| **Fundamental "provider"** | `backend/app/engines/fundamental.py` | None — synthetic RNG statements; fake "Codal" fields minted by RNG (`fundamental.py:914,968-969`) | In-process | n/a | Marked honestly: `_mark_synthetic_fundamental` sets `is_synthetic=True` + warning (`market_service.py:90-96`) | n/a. **No CODAL adapter exists** (grep: only synthetic references) |
| **Registry-uptime adapter** | `backend/app/data/registry_uptime.py:115-166` | Folds `get_uptime_metrics()` counters into SourceDescriptors; pure, no clock reads, never invents success (`:20-38`) | n/a | raises `ValueError` on malformed metrics | n/a | n/a — contract/domain only |

**Uptime/circuit-breaker state:** `CircuitBreaker` (tsetmc 3-fail/180s, brsapi 2-fail/120s — `providers.py:208-229,238-239`); cumulative counters + `success_rate` + CB-open flags exposed via `get_uptime_metrics()` (`providers.py:312-321`).

**Live-provider posture check (directive §6):** the *verification* posture is DENIED and correctly un-mintable (`config.py:156-167` `is_verified_live` triple gate; `config.py:284` `verified=False` unconditional; `config.py:286-287` live→mixed downgrade; AI-2 requires `is_verified_live` + owner enablement — `config.py:105-111`). However the *network* posture is NOT owner-gated: `DATA_SOURCE` defaults to `"auto"` (`config.py:34`), which on every startup runs `market_service.refresh(force=True)` (`main.py:108`) and a poll loop (`main.py:116`, `market_service.py:111-119`) that fetch live TSETMC. **F-1 below.**

---

## 2. MarketService pipeline (`backend/app/services/market_service.py`, HEAD line-by-line)

**Phase structure — verified as documented** (docstring `market_service.py:354-362`):
- **Phase 0** fast-path under lock (`:363-369`): returns cached analysis if `now - _last_fetch_ts < poll_seconds` and not forced.
- **Phase 1** fetch OUTSIDE lock (`:371-401`); on success stamps the observability mirror `_fetch_degraded=False` under lock (`:384-385`); on exception falls back to `self._last_symbols` and sets the **per-cycle local token `cycle_degraded=True`** (`:398`) + mirror (`:399`); re-raises only if no recycled board exists (`:400-401`).
- **Phase 2/2b** heavy CPU outside lock (`:407-476`): `analyze_market` (`:409-411`), big_moves+flow (`:419-423`), tablocastic (`:426-429`), row_cache (`:432-435`), confluence board incl. flow-coverage insufficiency downgrade to `watch_buy` (`:443-472`).
- **Phase 3** commit under lock (`:478-516`): state swap; **Q-1 false-fresh guard** — degraded cycle keeps the previous `_last_fetch_ts` (`:482-487`, `self._last_fetch_ts = self._last_fetch_ts or time.time()`), fresh cycle stamps `time.time()` (`:489`); canonical trust context computed under lock and persisted into `_trust_level` and the board (`:507-515`).
- **Phase 4** broadcast + notifier outside lock (`:517-543`).

**Q-1 fix — CORRECT.** The degraded marker is a per-cycle local (`cycle_degraded`, `:381`) immune to cross-cycle clobber; the instance attribute `_fetch_degraded` is demoted to a one-cycle observability mirror consumed at Phase 3 (`:487`). Reproduced and pinned by `tests/test_refresh_degraded_token_concurrency.py` (SeamLock injects a yield point into the Phase-1→Phase-3 span; 3 tests, green).

**Residual hazards found beyond Q-1:**
- **F-2 (source-label race):** `source = self.provider.last_source` at `:402` is read *after* the lock is released and is not atomic with this cycle's `provider.fetch()`. Two concurrent cycles (poll loop `force=True` + `POST /api/refresh` `routes.py:116-118`; there is **no in-flight dedupe**, `start_background` only guards the poll task `:98-101`) can interleave fetches; `provider.last_source/last_error/_cache` are shared mutable provider state written by both (`providers.py:325,384,427-430`). Cycle A can commit its board labeled with cycle B's source — including the upward direction (mock rows labeled `tsetmc` → state `live` → `trust_level "mixed"`, never "verified", but the label lies). Same family: `trust_ctx = self.data_trust_context()` at `:507` reads `provider.last_error` which may belong to the other cycle.
- **F-6 (I/O under lock):** `_persist_snapshot` (SQLite writes) runs *inside* the Phase-3 lock (`:498-503`), contradicting the phase docstring ("Phase 4: I/O outside lock"). Contention, not correctness.
- **F-7 (no in-flight dedupe):** concurrent `refresh(force=True)` calls duplicate full fetch+CPU work (see F-2 for the observable consequence).
- Benign-by-inspection: `_row_cache`/`_fund_cache`/`_seen_alert_keys` mutations are all in synchronous sections (no `await` inside), atomic on the single event loop; `board` dict is per-cycle local until commit.

**Boundaries:**
- `big_moves`: `allow_history_bootstrap` only when trust ≠ live (`:338`); synthetic bootstrap ticks recorded under a `"mock"` source hint (`:345`) — honest.
- `tablocastic`: computed per-symbol outside lock (`:426-429`), failures degrade to `[]`.
- `confluence`: flow coverage < `flow_min_coverage_sec` (120s default, `config.py:70`) strips all buy alerts and forces `watch_buy` with an explanatory reason (`:459-472`); board trust re-stamped from canonical context (`:510-515`).
- `_row_cache`: rebuilt every refresh cycle (`:495`), lazily on filter use (`:790-794`); size bounded by board size (no separate cap needed).
- `_fund_cache`: LRU-ish, max 200 entries, oldest-20% eviction on overflow (`:66-69,171-175`), TTL from `FUND_CACHE_TTL` (300s, `config.py:126`). Eviction sorts by insertion ts — stale-hit entries are refreshed before eviction, acceptable.
- Prune: hourly (`_prune_interval=3600`, `:69,323-331`) calling `store.prune_old(history_keep_hours=36)` (`store.py:335-342`; alerts kept 7 days).
- `_seen_alert_keys` capped 5000→arbitrary-2000 (`:321-322`) — set-iteration-order eviction; keys are 15-min time-bucketed (`:286`), so stale keys expire naturally (cosmetic, see F-10).

---

## 3. Data-trust state machine

- **States:** `DataTrustState = Literal["live","mixed","mock","synthetic","stale","unavailable"]` (`config.py:16`); legacy trust level `synthetic|mixed|live` via `_legacy_trust_level_from_state` (`config.py:205-210`: live→live; mixed/stale/unavailable→mixed; else synthetic).
- **Where `data_trust_state=mock` is set:** classification is purely source-label based — any source containing `"mock"` → `"mock"` (`config.py:194-195`). The label is minted in exactly two places: `DATA_SOURCE=mock` direct path (`providers.py:254-255` → `_from_mock` `:323-330` sets `last_source="mock"`) and any live failure fallback (`last_source="mock_fallback"`, `providers.py:260,269,274,283,310`). **What flips it:** a subsequent successful live fetch sets `last_source="tsetmc"/"brsapi"/"tsetmc_legacy"` with `last_error=""` (`providers.py:384-385,427-428,434-435`) → next `data_trust_context()` classifies live/mixed/stale. No other writer of `_source` exists (`market_service.py:490,499` commit only mirrors the provider).
- **Freshness overrides** in `build_data_trust_context` (`config.py:228-333`): missing ts + empty/unknown source → `unavailable` (`:272-273`); live-class without usable ts → downgraded `mixed` (`:274-275`); future timestamp (beyond `data_clock_skew_tolerance_sec`, default 0 — `config.py:44`) → `mixed` (`:276-277`); age > `data_stale_after_sec` (300s default, `config.py:43`) → `stale` (`:278-279`).
- **Fail-closed verification:** `verified=False` unconditionally (`config.py:284` — "This environment has no live-verification boundary"); `live_verified` argument accepted but ignored (`:249-253`); `state=="live"` with `verified=False` → `trust_level="mixed"` (`:286-287`); `is_live = verified` (`:288`). `is_verified_live` requires the exact triple `state=="live" AND is_live is True AND live_verified is True` (`config.py:156-167`) — which `build_data_trust_context` can never produce. `TRUST_LEVEL=live` override is explicitly discarded ("Configuration ≠ market evidence", `config.py:183-185`); only downgrade overrides (mixed/synthetic) are honored (`:186-189`).
- **Two-shape /api/health + /api/status contract:** full shape = `market_service.status()` merged (`routes.py:87-105,108-113`; status body `market_service.py:925-959` incl. `data_trust`, `last_fetch_ts`, `last_error`, store stats). Unauthorized/private-mode visitors get `_redacted_probe` (`routes.py:40-45,48-70`): `symbol_count=None`, `store/flow_meta/confluence/notifier/ws={}`, keeps only `ok/redacted/auth_required/source/trust_level/data_trust/version/poll_seconds/market_session`. See F-12 for the residual `source`+`data_trust.timestamp` disclosure.
- **Regression coverage:** refusal matrix pinned by `tests/test_p3_75_data_trust_hardening.py` (10 tests: live-label+fresh-ts not verified, triple-gate only, override cannot fabricate, notifier blocks unverified live-class), `tests/test_data_trust_hardening.py` (12 tests: full state mapping, mock-fallback metadata not live, API propagation, future-ts not live, brsapi no-key metadata), `tests/test_data_domain.py` (9 tests incl. session-open does not mark data live).

---

## 4. Freshness

- **`_last_fetch_ts` semantics:** stamped ONLY at Phase-3 commit of a non-degraded cycle (`market_service.py:489`); degraded cycles preserve the previous value (`:486`, `or time.time()` only covers the never-fetched 0.0 case); Phase-0 fast path and `data_trust_context()` both consume it (`:368`, `:83`); exposed via `status()["last_fetch_ts"]` (`:934`).
- **Staleness thresholds:** `DATA_STALE_AFTER_SEC` default 300 (`config.py:43`); clock-skew tolerance default 0 (`config.py:44`); flow coverage minimum 120s (`config.py:70`).
- **`market_cache.json`:** path `DATA_DIR/market_cache.json` where `DATA_DIR = repo-root/data` (`config.py:11-13,140`); written on EVERY successful fetch/mock (`providers.py:507-518`) with `{source, as_of, count, symbols[]}`; **`load_cache()` (`providers.py:520-530`) is dead code — never called anywhere in backend** (grep: single definition). Cache is fully rebuildable (regenerated every cycle) and gitignored. See F-8.
- **`history_snapshots.jsonl`:** declared `config.py:141` (`history_path`), **referenced nowhere else** — declared-but-unused confirmed (F-9).
- **TTL constants inventory:** `REQUEST_TIMEOUT=12` (`config.py:42`), `POLL_SECONDS=30` (`:41`), `FUND_CACHE_TTL=300` (`:126`), `BIG_MOVE_WINDOW_SEC=600` (`:65`), `HISTORY_KEEP_HOURS=36` (`:67`), `NOTIFY_COOLDOWN_SEC=900` (`:84`), CB resets 180s/120s (`providers.py:238-239`), prune 3600s (`market_service.py:69`).

---

## 5. Offline determinism (test suite cannot reach TSETMC)

- **Pin:** `tests/conftest.py:37-38` — `os.environ.setdefault("DATA_SOURCE", "mock")` + `setdefault("BRSAPI_KEY", "")`, executed before any app import. With the pin, `MarketDataProvider.fetch()` routes straight to `_from_mock()` (`providers.py:254-255`) — no outbound HTTP client is ever constructed for market data.
- **Exposure if the pin were absent:** `DATA_SOURCE` default is `"auto"` (`config.py:34`); 14 test files drive market endpoints through TestClient (lifespan performs an initial `refresh(force=True)`, `main.py:108`): `test_p3_82_ai_path_trust.py`, `test_data_trust_hardening.py`, `test_alpha_validation_scripts.py`, `test_security_hardening.py`, `test_p3_87_integration_audit.py`, `test_p3_81_ai_contracts.py`, `test_p3_77_local_hardening.py`, `test_p3_79_local_hardening.py`, `test_ws_harden1_version_sync.py`, `test_p3_80_local_closure.py`, `test_security_paths.py`, `test_ws_harden1_request_id.py`, `test_security_rate_limit.py`, `test_wp5_launch_readiness.py` — all would hit real TSETMC on an internet-connected CI host (this is exactly the pre-conftest nondeterminism documented at `conftest.py:7-13`).
- **Residual leak (F-4):** `setdefault` does not override a host-exported `DATA_SOURCE=tsetmc|auto|brsapi` — the pin is env-overridable and fails open. Test-local overrides still work as designed (`test_data_trust_hardening.py:161` sets `DATA_SOURCE=brsapi` via monkeypatch for the no-key test).
- **Forex tests never network:** `tests/test_forex.py` exercises only metadata + unknown-symbol early return (`:67-69`); `test_p3_77_local_hardening.py:197` reads `app/api/forex.py` as text. The forex *production* path is NOT covered by the mock pin (F-5).
- **E2E suite** (`e2e/`) targets a locally running app and honestly SKIPs when unreachable (`e2e/conftest.py:23-32`) — no external market dependency.
- **Good:** `DATA_SOURCE` is not runtime-editable (`runtime_settings.py:11-31` EDITABLE_KEYS excludes it; only `get_thresholds_public()` echoes it at `:66`).

---

## 6. Failure handling

| Scenario | Behavior | Verdict |
|---|---|---|
| Provider outage (exception) | Recycled board + per-cycle degraded token, previous ts preserved (`market_service.py:386-401,482-487`); no board → re-raise (`:400-401`); poll loop survives (`:115-119`) | Sound; pinned by 6 tests (`test_refresh_false_fresh.py` ×3, `test_refresh_degraded_token_concurrency.py` ×3) |
| Provider outage (empty payload) | Mock fallback with `last_source="mock_fallback"`, `last_error="live sources unavailable"` (`providers.py:323-330`) → trust state `mock` (honest) | Sound |
| Circuit breaker open | Skip hammering, straight to mock (`providers.py:257-260,271-274`) | Sound |
| Timeouts | httpx `timeout=request_timeout` (12s) on both market clients (`providers.py:344,415`); forex 10s Binance/OKX/KuCoin (`forex_provider.py:234,264,297`), 12s Yahoo (`:338`) | **Present everywhere — no missing-timeout finding** |
| Retry | brsapi 2 attempts + 1s/2s backoff (`providers.py:342-355`); Yahoo 429 → 1 retry w/ backoff (`forex_provider.py:336-343`); tsetmc = 3 distinct endpoints, no per-URL retry | Adequate; tsetmc per-URL retry absent (acceptable: 3 endpoints) |
| Malformed payload | `_safe_float/_safe_int` coerce garbage→0 (`providers.py:36-51`); tsetmc item parse wrapped, bad item → `None` (`:128-205`); non-dict rows filtered (`:447-453,461-464`); brsapi per-row try/except + `l18`+`pl>0` gate (`:373-381`); legacy needs ≥10 cols + `pl>0` (`:475-486`); **no isfinite check** and **SymbolSnapshot has no value constraints** (`schemas.py:109-189`) → NaN/inf and negative prices can pass (F-3); JSON path lacks the `pl>0` gate the legacy path has (`:461-464` vs `:485`) | Gaps → F-3 |
| Partial-symbol failures | Per-row skip; board delivered with surviving rows (`providers.py:373-381,461-464`) | Sound |
| Empty board | Live-empty → mock fallback (`providers.py:269,283,310`); `analyze_market([])` is safe (filters to empty lists, `screener.py:24-41`); empty-return stub cycle completes and re-stamps fresh (`test_refresh_false_fresh.py:50-51,153-156`) | Sound |
| brsapi key handling | Key default `""` (`config.py:36`); no-key → early return, no network, honest metadata (pinned `test_data_trust_hardening.py:155-161`) | Sound; note key travels as URL query param (`providers.py:339`) — INFO |

---

## 7. Reproducibility / golden data

- **No production market data committed:** `git ls-files` contains **zero** `.csv`, `.jsonl`, `.db`, `.sqlite` files and no `market_cache*`/`history_snap*` (verified by tracked-tree scan; largest tracked files all < 500KB and are fonts/vendor JS/tests fixtures).
- Runtime artifacts land in gitignored `repo-root/data/` (`.gitignore` "Runtime data" block: `/data/`, `/data/*.db`, `/data/*.json`) — current dir holds untracked `market_cache.json` (82KB) + `shekar.db` (20MB) + backups; none tracked.
- **Golden fixture bars are synthetic-by-design:** mock board is generated in-process with `source="mock"` (`mock_market.py:260`) and labeled `MOCK data … not validated live market data` (`config.py:297-298`); fundamental output is force-marked synthetic (`market_service.py:90-96`); `tests/fixtures/golden_set/golden_set_v1.json` is an AI-eval fixture, not market bars; backtests carry `demo_disclaimer`/`educational` markers (`market_service.py:871-873`).
- Determinism caveat: mock prices mutate per 30s wall-clock bucket (`mock_market.py:84`), so boards are reproducible only within a bucket — acceptable for UI/tests (tests inject timestamps/stubs rather than relying on board values; `test_refresh_false_fresh.py:13-14`).

---

## 8. P1/P2 regression suites — executed results (read-only)

Runner: `cd backend && ../.venv/bin/python -m pytest -q` — all green.

| File | Count |
|---|---|
| tests/test_refresh_false_fresh.py | 3 passed |
| tests/test_refresh_degraded_token_concurrency.py | 3 passed |
| tests/test_data_trust_hardening.py | 12 passed |
| tests/test_p3_75_data_trust_hardening.py | 10 passed |
| tests/test_p3_76_adversarial_trust.py | 4 passed |
| tests/test_p3_82_ai_path_trust.py | 2 passed |
| tests/test_p3_83_provider_execution.py | 10 passed |
| tests/test_p3_86_provider_integration.py | 36 passed |
| tests/test_p3_90_7_tsetmc_cdn_schema.py | 5 passed |
| tests/test_p3_91_cdn_snapshot_filter.py | 2 passed |
| tests/test_data_domain.py | 9 passed |
| tests/test_forex.py | 8 passed |
| tests/test_registry_uptime.py | 17 passed |
| tests/test_market_intelligence_service.py | 8 passed |
| tests/test_market_calendar.py | 14 passed |
| tests/test_p3_87_integration_audit.py | 15 passed |
| tests/test_p3_88_residual_classification.py | 5 passed |
| **Total (3 batches: 28 + 93 + 42)** | **163 passed, 0 failed, 0 skipped** (≈1s per batch) |

---

## 9. Findings register

Severity × gating. **AUTHORIZED-REPO-SIDE** = additive fix possible now without owner policy change; **OWNER-GATED** = requires owner decision; **NOT-A-DEFECT** = design, recorded for the record.

| ID | Sev | Gating | Finding (file:line) |
|---|---|---|---|
| **F-1** | **HIGH** | **OWNER-GATED** | **Default network posture is live without an owner gate.** `DATA_SOURCE` defaults to `"auto"` (`config.py:34`), auto = tsetmc→brsapi→mock (`providers.py:285-310`), TSETMC needs no key, and startup + poll loop execute it immediately (`main.py:108,116`). The directive's "live posture DENIED" is enforced only at the verification layer (`config.py:156-167,284,286-287`), not at the network layer: the app ships ready to pull unverified live TSETMC data out of the box. Fix is a one-line default flip to `"mock"` (or an explicit `RADAR_LIVE_ENABLED=1` gate) — but it changes shipped behavior → owner must ratify. The mock fallback and mixed-label honesty mean blast radius is mislabeling/latency, not fake "verified live". |
| **F-2** | **MEDIUM** | AUTHORIZED-REPO-SIDE | **Residual cross-cycle race beyond Q-1: source/last_error read from shared provider state.** `market_service.py:402` reads `provider.last_source` after the Phase-1 lock is released; `providers.py:325,384,427-435,511` mutate it per fetch; concurrent cycles (poll loop + `POST /api/refresh`, no in-flight dedupe `market_service.py:98-101`) can commit a board with another cycle's source label — including upward mislabel (mock rows → "tsetmc"). Never reaches "verified live" (`config.py:284`), but the provenance label can lie. Fix: return `(source, error)` from `fetch()` or snapshot provider state inside fetch. |
| **F-3** | **MEDIUM** | AUTHORIZED-REPO-SIDE | **No finite-value/constraint boundary validation.** `_safe_float` accepts `"nan"`/`"inf"` (`providers.py:36-51`); `SymbolSnapshot` fields carry no `ge/gt/allow_inf_nan` constraints (`schemas.py:109-189`); brsapi gates `l18`+`pl>0` only (`providers.py:378`); tsetmc JSON path gates `l18` only, unlike its own legacy path which gates `pl>0` (`providers.py:461-464` vs `:485`). A poisoned payload would flow NaN into metrics/ratios silently. Fix: `math.isfinite` guard in `_safe_float/_safe_int` + non-negative price gates on both tsetmc paths. |
| **F-4** | **MEDIUM** | AUTHORIZED-REPO-SIDE | **Offline pin fails open on env leak.** `os.environ.setdefault` (`conftest.py:37-38`) is overridden by any host-exported `DATA_SOURCE`; 14 TestClient files would then hit real TSETMC (list in §5). Fix: fail-closed guard — abort suite (or force mock) unless an explicit `RADAR_ALLOW_LIVE_TESTS=1` escape hatch is set. |
| **F-5** | **MEDIUM** | OWNER-GATED (label fix repo-side) | **Forex layer sits outside the mock posture and mislabels derived-real data as "synthetic".** `/api/forex` performs live Binance/OKX/KuCoin/Yahoo calls regardless of `DATA_SOURCE` (no gate in `app/api/forex.py`; no conftest coverage); `_synthetic_ohlcv` fetches REAL PAXG/BTC patterns and rescales them, stamping rows `source="synthetic-<sym>", trust_level="synthetic"` (`forex_provider.py:387-410,552-556`) — real market microstructure under a synthetic provenance label; the pure random-walk tail (`:413-429`) is honest. Owner decision: is forex in the mock-posture scope? Repo-side minimum: relabel rescaled bars as "derived-real-pattern". |
| **F-6** | LOW | AUTHORIZED-REPO-SIDE | SQLite persistence runs inside the Phase-3 lock (`market_service.py:498-503`), contradicting the phase docstring (`:354-362`); lock-hold grows with board size. Move to Phase 4 (store has its own lock, `store.py:18,33`). |
| **F-7** | LOW | AUTHORIZED-REPO-SIDE | No in-flight refresh dedupe: concurrent `refresh(force=True)` duplicate fetch+CPU and are the precondition for F-2 (`market_service.py:354-401`; sole guard covers only the poll task, `:98-101`). A single-slot in-flight future would fix both. |
| **F-8** | LOW | AUTHORIZED-REPO-SIDE | `market_cache.json` is write-only: `_persist_cache` writes every fetch (`providers.py:507-518`) but `load_cache` (`providers.py:520-530`) is never called (grep: one hit = definition). Crash-recovery path declared but unwired — wire it (startup seed when live fetch fails and board empty) or delete it. |
| **F-9** | LOW | AUTHORIZED-REPO-SIDE | `history_snapshots.jsonl` declared-but-unused: `config.py:141` `history_path` has zero references (grep). Dead config — remove or implement. |
| **F-10** | LOW | NOT-A-DEFECT | `_seen_alert_keys` eviction `set(list(...)[-2000:])` is set-iteration-order-arbitrary (`market_service.py:321-322`); keys are 15-min time-bucketed (`:286,304`) so correctness is unaffected. |
| **F-11** | INFO | NOT-A-DEFECT | brsapi API key is transmitted as a URL query parameter (`providers.py:339`) — provider API contract; may appear in intermediary logs. Owner awareness item only. |
| **F-12** | INFO | NOT-A-DEFECT | `_redacted_probe` still discloses `source` and full `data_trust` (incl. `timestamp`/`age_sec`) to unauthorized visitors (`routes.py:48-70`). No market rows leak (`symbol_count=None`, store/confluence emptied). Deliberate transparency tradeoff; owner may wish to also null `source`. |
| **F-13** | INFO | NOT-A-DEFECT | Mock board is only bucket-deterministic (30s MD5-seeded RNG, `mock_market.py:83-85`) — by design ("حس زنده بودن", `mock_market.py:4`); tests avoid depending on board values. |
| **F-14** | INFO | NOT-A-DEFECT | Trust classification is label-driven and cannot be flipped by runtime settings (`runtime_settings.py:11-31` excludes `data_source`); downgrade-only overrides (`config.py:183-189`) — correct fail-closed design. |

**Positives verified (evidence):** Q-1 per-cycle token implemented exactly as directed (`market_service.py:381,398,482-487`) with a genuine interleaving reproduction harness (`test_refresh_degraded_token_concurrency.py:100-127,161-234`); verified-LIVE un-mintable (`config.py:249-253,284`); mock fallback honesty incl. `mock_fallback` naming and `last_error` retention (`providers.py:323-330`); circuit breakers + timeouts + retry taxonomy complete (`providers.py:208-239,342-355,415`; `forex_provider.py:234,264,297,338`); no fabricated timestamps anywhere in the uptime adapter (`registry_uptime.py:20-38`); fundamental synthetic labeling mandatory (`market_service.py:90-96`).

---

## 10. Not verified

1. **Live endpoint behavior** — no network calls were made (read-only directive): actual TSETMC CDN/BrsApi/Yahoo/Binance payload shapes in the wild, header/anti-bot behavior, and the `z`/`zTitad` field semantics against live payloads are unverified (schema assumptions at `providers.py:165-166` rest on the fixture-pinned `test_p3_90_7_tsetmc_cdn_schema.py`).
2. **CI environment variables** — whether the external CI host exports `DATA_SOURCE` (F-4 exploitability) is unobservable from this sandbox.
3. **E2E suite execution** — requires a running app instance + Playwright chromium; only statically reviewed (`e2e/conftest.py`, `e2e/test_smoke.py`).
4. **Notifier channels** — Telegram/Bale real delivery, `notify_allow_synthetic` end-to-end behavior: static review only.
5. **Long-run memory behavior** — `_fund_cache` eviction and `_seen_alert_keys` cap reviewed statically, not under a 200+ symbol live board soak.
6. **Windows/desktop (electron) shell and `start.sh`/`install.sh` env defaults** — outside data-layer scope; whether packagers export `DATA_SOURCE` in production installs was not traced end-to-end.
7. **WS payload size/pressure** under a full live board (`_broadcast_live` caps signals at 15/10 — `market_service.py:617-626` — but total board size unmeasured live).
8. **Concurrency of SQLite under multi-process deployment** (WAL configured, `store.py:36`; single-process assumption not validated).

---

## 11. Suggested next actions (priority order)

1. **Owner decision (F-1):** ratify or flip the default `DATA_SOURCE` posture; if auto stays, record the decision in the governance register with the "mixed-not-verified" rationale.
2. **Repo-side (F-2/F-7):** make `provider.fetch()` return its own source/error snapshot; add an in-flight refresh future. Both additive, fully covered by existing test seams.
3. **Repo-side (F-3):** `isfinite` guards + price gates on both TSETMC paths.
4. **Repo-side (F-4):** fail-closed conftest guard with explicit escape hatch.
5. **Repo-side cleanup (F-6/F-8/F-9):** move persist out of lock; wire or delete `load_cache`; delete or implement `history_path`.
6. **Owner decision (F-5):** forex scope + relabel derived-real bars.

— End of report —
