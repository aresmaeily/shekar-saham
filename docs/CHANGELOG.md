# Changelog — RADAR BOURSE

## 2026-10-18 — AI3-A AI-3 scope derivation and blocker evidence (no implementation authorized)

- Mandate "complete AI-3 as one end-to-end delivery" resolved by derivation evidence: the official AI-3 block is defined only by the NOT_SYNCED 2026-10-02 amendment corpus. Exhaustive reproducible search — `rg "AI-3|AI3"` across the entire working tree (tracked + untracked) → 0 files; `git log --all -S "AI-3"` and `-S "AI3"` → 0 commits; variant naming ("third stage", "stage 3") → 0 hits; authoritative-source traversal per CLAUDE.md order (execution state, master handoff, PRODUCT_ROADMAP_LOCK, STATUS/INDEX/CHANGELOG, `docs/architecture` incl. the P3.38 AI Brain lock and its Future Architecture Gate, amendment corpus `ls` → exit 2) → no AI-3 definition in any available source.
- New `docs/active/AI3_SCOPE_DERIVATION_AND_BLOCKER_RECORD.md`: methodology + 11 reproducible searches (§2); empty requirement inventory → every AI-3 requirement BLOCKED (class B — missing authoritative definition, §3); no-invention governance citations (§4 — mandate rule, P3.60 gate, CLAUDE.md stop conditions, developer scope rule, AI-2 Category B precedent); owner handoff for the 5 amendment files with AI-3-specific impact (§6); task acceptance matrix (§8); next-roadmap-action analysis (§9 — the post-AI-3 roadmap position is owner-owned, not invented).
- No application code changed; no AI-3 feature invented; no AI-4 substitution; roadmap not redefined. Pre-commit battery green at clean `54626ee` (348 passed / 2 warnings in 77.38s; AI-2 40/40; compileall 0; pyflakes `app tests` 0; pip-audit clean; validator 8/8; `git diff --check` 0); battery re-run at the committed AI3-A SHA (raw: `docs/governance/evidence/raw/2026-10-18_ai3a/`).
- Governance unchanged: no AI-2/AI-3 HTTP route; `AI2_ENABLED` default off; G2 NOT_PASSED (not self-approved); `live_verified=false`; LLM NOT EXECUTED; no push.

## 2026-10-17 — AI2-E AI-2 G2 reviewer checklist and handoff staleness fixes

- New `docs/active/AI2_G2_REVIEWER_CHECKLIST.md`: reviewer-facing working document for the authorized G2 review — reviewed commit/ancestry/remote divergence (state verified 2026-10-17T13:37Z); compact acceptance matrix (14 Category A PASS, 0 FAIL, 8 BLOCKED rows with exact causes, 3 environment NOT_VERIFIED) with implementation + named-test references for A1–A14; exact battery commands and results with raw evidence paths; the `asyncio.to_thread` cancellation limitation with containment evidence (four named tests); provider/network/credential/Windows/Python 3.13/CLI limitations; explicit local-testing vs independent-G2-validation separation (348 passing tests ≠ G2 approval); reviewer/owner decision table R1–R6 with expected evidence; G2 entry criteria E1–E6 checkable from available sources and exit criteria explicitly BLOCKED (authoritative procedure NOT_SYNCED; nothing invented); owner handoff table for the 5 missing amendment originals with per-file impact.
- Evidence-package integrity audit (this task): every cited file, implementation line range, all 37 named tests (40 total), command results, and evidence paths verified against the committed tree; package self-resolution confirmed (`git log -1 -- docs/active/AI2_G2_READINESS_EVIDENCE_PACKAGE.md` → `56deaff`).
- One additive staleness fix in `docs/active/AI2_G2_READINESS_EVIDENCE_PACKAGE.md` §10: divergence count → "local main ahead 7 as of the AI2-E reconciliation; ahead 6 at packaging time" (the package's §1 packaging-time block is historical and unchanged).
- Governance unchanged: no AI-2 HTTP route; `AI2_ENABLED` default off; G2 NOT_PASSED (not self-approved); `live_verified=false`; LLM NOT EXECUTED; no push.

## 2026-10-17 — AI2-D AI-2 residual audit closure and G2 readiness evidence package

- Residual audit (mandate checklist) of the committed AI-2 implementation at `0834b19`, executed against actual code and test bodies (all 40 tests executed, bodies inspected): all 14 Category A criteria PASS — bounded requests incl. iterative depth bound + NaN/Infinity rejection; strict `extra="forbid"` output schema with item bounds and confidence range; deterministic stage-1 integration with recorded-not-raised degradation; model output cannot mutate deterministic facts (bit-for-bit proven); fail-closed trust gates with ordering AI2_ENABLED → trust-state → G2/`is_verified_live`; verifiable input/prompt hashes (re-derived from returned artifacts; prompt rebuilds from recorded inputs); provenance completeness on all 8 outcome paths + `provider_attempts`; cancellation/late-result containment (thread NOT terminated — honestly documented and test-proven); deterministic failure mapping incl. seam-contract non-dict violations; secret-free logs and errors incl. exception paths (stage-1 records type name only; seam warnings are static bounded strings); concurrency isolation + hash idempotency; test-transport isolation (mocked seam/transport + raising spy transports; production path structurally unreachable); exact inter-stage value transfer. **Zero FAIL; zero NOT_VERIFIED among implementable criteria; no remaining unblocked implementation gap — no application code changed; no gap manufactured.**
- New `docs/active/AI2_G2_READINESS_EVIDENCE_PACKAGE.md`: repository state + ancestry + live-remote divergence (ahead 6 vs GitHub `main` `c1984e7`, read-only re-verified); amendment corpus re-verified NOT_SYNCED (dir absent); criterion-by-criterion acceptance matrix with evidence and PASS/BLOCKED/NOT_VERIFIED classification; exact verification battery at `0834b19` (348 passed / 2 warnings in 77.30s; AI-2 focused 40/40; compileall 0; pyflakes `app tests` 0; pip-audit clean; bootstrap validator 8/8; `git diff --check` 0; raw evidence `docs/governance/evidence/raw/2026-10-17_ai2c_independent_verification/` + `2026-10-17_ai2d/`); known limitations (§8 of the package); explicit no-live-execution confirmation; outstanding G2/owner/amendment/credential dependency table. The package is locally reproducible evidence and is explicitly NOT G2 approval.
- Governance unchanged: no AI-2 HTTP route; `AI2_ENABLED` default off; G2 NOT_PASSED (not self-approved); `live_verified=false`; LLM NOT EXECUTED. Record §8: `docs/active/REM1_AI2A_IMPLEMENTATION_RECORD.md`.

## 2026-10-17 — AI2-C AI-2 async boundary, context-integrity, and bounded-input hardening

- `backend/app/services/ai2_service.py`: cancellation-containment contract documented and test-proven (`asyncio.to_thread` cannot terminate the worker thread; a late provider success/failure after caller cancellation is discarded — no fabricated result, no downstream state on the stateless singleton, instance reusable; cancellation during context building reaches no seam invocation). `backtest_result` validator now bounds nesting depth iteratively (`backtest_result_too_deep`, `_MAX_BACKTEST_DEPTH=24`) — probed demonstration: depth-1000 payloads crashed `ctx.model_dump` with pydantic-core `ValueError("Circular reference detected")` and ~10.9k depth overflowed `json.dumps` with `RecursionError`, both previously uncaught; NaN/Infinity rejected (`allow_nan=False` → `backtest_result_not_json_serializable`) as non-RFC-8259 JSON. A seam-contract-violating non-dict execution now maps to `failed_provider/provider_contract_violation` instead of crashing with `AttributeError`. `AI2Provenance` adds `provider_attempts` (seam `attempts` contract; invalid/missing → `None`).
- Hash-to-payload verifiability tests: `input_snapshot_sha256` re-derives from the returned `deterministic_context` alone (idempotent); `prompt_sha256` re-derives by rebuilding the prompt from the recorded task/data_trust/stage-1 inputs plus the question (including the degraded missing-symbol shape); a schema-valid model output claiming different facts leaves the deterministic context bit-for-bit identical to a gated run.
- Tests `backend/tests/test_ai2_service.py`: 23 → 40. Full suite 331 → 348 passed / 2 warnings (same two pre-existing starlette/anyio deprecations); pyflakes `app tests` 0; pip-audit clean; bootstrap validator 8/8; `git diff --check` 0. Raw evidence: `docs/governance/evidence/raw/2026-10-17_ai2c/`.
- Governance unchanged: no AI-2 HTTP route; `AI2_ENABLED` default off; G2 NOT_PASSED (not self-approved); `live_verified=false`; LLM NOT EXECUTED. Category B blockers unchanged (NOT_SYNCED 2026-10-02 amendments, live credentials). Record §7: `docs/active/REM1_AI2A_IMPLEMENTATION_RECORD.md`.

# Changelog — RADAR BOURSE

## 2026-10-17 — AI2-B AI-2 Category A hardening batch

- `backend/app/services/ai2_service.py` hardened within the existing contract: bounded `AI2Request` (field length caps; `backtest_result` must be JSON-serializable and ≤64 KiB — fail-closed at construction); `AI2Interpretation` now `extra="forbid"` with per-item bounds, so unspecified model-emitted fields fail validation instead of being silently ignored; new fail-closed Gate 2 (missing/`unavailable` data trust → `gated_not_executed/data_trust_unavailable` before any provider invocation); deterministic stage-1 analysis (existing `FallbackAIProvider`) now feeds the provider prompt and is recorded as `deterministic_context.stage1` with recorded-not-raised degradation; provenance adds `prompt_sha256` and stage-1-aware input-snapshot hash; provider seam executed off the event loop via `asyncio.to_thread`.
- Tests `backend/tests/test_ai2_service.py`: 12 → 23 (request bounds; unknown-field rejection incl. non-mutation of deterministic context; boundary acceptance; stage-1 presence/idempotency; stage-1 degradation; unavailable/missing trust gates; test-transport isolation; empty-output defense; concurrency isolation; cancellation). Full suite 320 → 331 passed / 2 warnings; pyflakes `app tests` 0 findings; pip-audit clean; bootstrap validator 8/8. Raw evidence: `docs/governance/evidence/raw/2026-10-17_ai2b/`.
- Governance unchanged: no AI-2 HTTP route; `AI2_ENABLED` default off; G2 NOT_PASSED (not self-approved); `live_verified=false`; LLM NOT EXECUTED. Category B blockers unchanged (NOT_SYNCED 2026-10-02 amendments, live credentials). Record: `docs/active/REM1_AI2A_IMPLEMENTATION_RECORD.md` §6.

## 2026-10-17 — REM-1 full-code audit remediation + AI2-A AI-2 Category A offline scaffold

- REM-1 (audit remediation): 7 unused-import/variable findings in `backend/tests/` fixed (behavior-neutral); `backend/app/core/rate_limiter.py` docstring aligned to the enforced limits (150/min general, 25/min heavy, 15/min sensitive, login 5/min + 20/hour). `pyflakes app tests` now exits 0 (was 7 findings); full suite unchanged at 308 passed / 2 warnings. Full audit ledger: `docs/active/REM1_AI2A_IMPLEMENTATION_RECORD.md`.
- AI2-A: new `backend/app/services/ai2_service.py` — AI-2 second-stage analysis scaffold with typed contracts, strict interpretation-schema validation, deterministic-domain integration via the existing `AIContextBuilder`/`invoke_ai_provider` seam, provenance metadata (input SHA-256, trust state, provider status, gate report), deterministic failure mapping, and secret-free structured logging. Fail-closed gates: `AI2_ENABLED` default off; the production path additionally requires `is_verified_live(data_trust)` (cannot be minted today) — real-data AI-2 stays BLOCKED behind G2 independent validation + owner acceptance. Additive config: `ai2_enabled` in `backend/app/core/config.py`. New tests: `backend/tests/test_ai2_service.py` (12, mock-based). No HTTP route exposed; no `live_verified` change; LLM NOT EXECUTED.
- Task IDs REM-1/AI2-A deliberately avoid a "P3.94" number: a reported P3.94 exists only in a second workspace whose commits are absent from this repository.

## 2026-10-17 — P3.92 Documentation state reconciliation (docs-only)

- `docs/STATUS.md`: rows added for P3.90.2 (`00e392e`, tzdata pin), P3.90.7 (`5206569`, CDN GetMarketWatch mapper), P3.91 (`c1984e7`, Filter DSL CDN-snapshot proof), and P3.92; "Last updated" bumped to 2026-10-17.
- `docs/active/INDEX.md`: P3.92 report entry + factual note that P3.90.2/P3.90.7/P3.91 evidence lives in CHANGELOG/tests/commits (no dedicated phase reports exist; none fabricated).
- `RADAR_BOURSE_MASTER_HANDOFF.md`: appendix block "P3.90–P3.93 Update" appended.
- Companion task P3.93 (`6ff6b07`, same date): `docs/active/SECURITY_PRIVATE_MODE.md` v1.5→v1.6 aligned with the HttpOnly cookie session implementation; rate limits corrected to code values (150/25/15 + login 5/min & 20/hour); CSRF origin check, fail-closed startup validation, probe redaction and `?legacy` debug mode documented; no security control changed.
- No application code change. `live_verified` stays false. LLM NOT EXECUTED. Fresh QA: 308 passed / 2 warnings (evidence: `docs/governance/evidence/raw/2026-10-17_truth_sweep/`).

## 2026-08-17 — P3.91 CDN snapshot → Filter DSL contract

- After P3.90.7 mapper, Filter DSL can consume snapshots built from CDN `lva`/`pDrCotVal` keys.
- Tests only. No filter/provider/fallback/trust change. `live_verified` stays false.

## 2026-08-16 — P3.90.7 CDN GetMarketWatch mapper

- `tsetmc_mw_to_snapshot` maps CDN keys `lva`/`lvc` (and existing `pDrCotVal`/`pClosing`/`qTotTran5J`).
- Owner runtime after apply: `source=tsetmc`, `symbol_count=1509`. Not verified LIVE.

## 2026-08-16 — P3.90.2 Windows tzdata runtime dependency

- Owner Windows `start.ps1` failed at import: `ModuleNotFoundError: tzdata` then `ZoneInfoNotFoundError: Asia/Tehran`.
- Cause: `backend/app/domain/market_session.py` uses stdlib `ZoneInfo("Asia/Tehran")`. Windows has no IANA zoneinfo database. `tzdata` was not declared in `backend/requirements.txt`.
- Fix: pin `tzdata==2026.3`. `install.ps1` already installs from that file; no installer logic change.
- No business-logic, security, AI, frontend, or `.env` change.

## 2026-08-15 — P3.90.1 Windows validation project-root resolution

- `validate_install.ps1`, `install.ps1`, and `start.ps1` no longer resolve `$PSScriptRoot` in `param()` defaults.
- Project root is resolved in the script body via `$PSScriptRoot` / `$PSCommandPath`. CWD is not used. Paths are not hard-coded.

## 2026-08-15 — P3.89 Gemini header auth

- Gemini transport now uses `x-goog-api-key` instead of a query-string key.
- Official Gemini/Google contract prefers the header. URL/proxy/exception-cause leak closed.
- Residuals A/B/D remain classification-only. No real LLM call in this environment.

## 2026-08-15 — P3.88 Residual classification

- Re-downloaded the P3.87 TempFile and re-verified SHA, ZIP, GitHub remote, and HEAD.
- Classified the four P3.87 residuals: terminology / latent transport notes, not current runtime defects.
- No product-behavior change. Gemini query-string key left unchanged (path NOT EXECUTED here).
- Added residual-classification tests. Runtime remains NOT EXECUTED.

## 2026-08-15 — P3.87 AI integration audit

- Re-downloaded the P3.86 TempFile and re-verified SHA, ZIP, GitHub remote, and HEAD.
- Re-executed fail-closed and injection cases on the real P3.86 chain. No product-behavior fix required.
- Added audit tests for 401/403/429/5xx, prompt-not-ping, and structured-field injection.
- Runtime remains NOT EXECUTED. Not market LIVE.

## 2026-08-15 — P3.86 Controlled AI provider integration

- Validated P3.85 provider text may replace Assistant / Analyst / Research / Strategy / Risk answers.
- Fallback answers are preserved. Fail-closed statuses still return the deterministic result.
- Optimizer suggestions are not replaced. Provider text cannot rewrite `data_trust` or mint LIVE.
- This environment has no LLM credential. Runtime remains NOT EXECUTED.

## 2026-08-15 — P3.85 Real HTTPS AI provider transport

- Added `https_transport` using httpx with TLS verify and a real timeout.
- Network calls require `AI_EXECUTE=1` plus a server-side key. No key → no request.
- HTTP 4xx (except 429) is not retried. Malformed JSON is fail-closed.
- This environment has no LLM credential. Runtime remains NOT EXECUTED. Not market LIVE.

## 2026-08-15 — P3.84 Real AI Provider Transport gate

- Audited P3.83 seam: no production HTTP/TLS LLM transport exists.
- Chose OPTION B: remain BLOCKED. Did not add a fake provider or fabricated LLM call.
- Documented the exact future activation gate.

## 2026-08-15 — P3.83 AI runtime readiness and provider execution gate

- Added fail-closed `invoke_ai_provider` (timeout/retry config, credential/invalid/unavailable/malformed states).
- Production never invents LLM text. TEST ONLY transport is labelled and not used by HTTP handlers.
- No GitHub push. No live LLM execution.

## 2026-08-15 — P3.82 AI path trust and roadmap audit

- Re-downloaded and verified the P3.81 TempFile SHA-256.
- Confirmed GitHub remote HEAD via `ls-remote` and `fetch`.
- Added `data_trust` to chart AI overlay, stop-loss, and portfolio-optimization responses.
- No external LLM invocation. No GitHub push.

## 2026-08-15 — P3.81 AI provider adapter and remaining intelligence contracts

- Added environment-only AI provider adapter. Client secrets are rejected. No external LLM is invoked.
- Added AI Research / Strategy / Risk tasks over controlled context with data_trust, confidence, warnings, source.
- `/api/v07/ai-explain` now carries data_trust and is labelled fallback.
- LLM runtime remains NOT_EXECUTED / UNVERIFIED.

## 2026-08-15 — P3.80 Local remaining-work closure

- Service Worker no longer caches `/api/*` (stale market data and post-logout replay).
- `/static/sw.js` is served with `Cache-Control: no-store`.
- Production disables `/docs`, `/redoc`, and `/openapi.json`.
- `chart_builder.py` no longer uses bare `except:`.
- No installation, live verification, or GitHub push.

## 2026-08-15 — P3.79 Final repository hardening

- Public `/api/status` and `/api/live/status` now redact market/confluence/notifier details when auth is required and the caller is not authorized.
- `/api/health` accepts the HttpOnly session cookie, not only API key / Bearer.
- Private-mode middleware honors documented public probe paths; handlers redact instead of leaking or blindly 401ing probes.
- Electron shell locks in-window navigation/redirects to the configured backend origin. `SHEKAR_URL` fallback remains.
- Added `backend/tests/test_p3_79_local_hardening.py`. Full suite: 194 passed, 1 warning.
- No installation, live verification, GitHub push, or feature addition.

## 2026-08-15 — P3.78 Conservative same-bar TP/SL

- Close-only bars still use close vs TP then SL (cannot both trigger).
- OHLC bars that touch both TP and SL take a conservative stop; they do not assume the win.
- Walk-forward is explicitly labeled as rolling OOS of a fixed filter, not an optimizer.
- Starlette/httpx2 warning remains test-only; dependencies not upgraded.

## 2026-08-15 — Post-P3.54 closure audit

- Reproduced P3.54–P3.77 repository state at `d6e56b2`.
- No additional authorized local P0/P1 remaining after fallback-AI trust gate.
- GitHub push still blocked (no credentials). Installation remains locked.

## 2026-08-15 — P3.77 evidence follow-up

- `DataQualityScorer` no longer emits `trust=live` from a tsetmc/brsapi source label.
- `/api/v07/data-quality` and `/api/v08/chart` now carry canonical `data_trust`.
- Behavioral API tests prove analyze/data-quality/notify-now are not verified LIVE.

## 2026-08-15 — P3.77 Local hardening and defect closure

- Closed remaining local false-LIVE paths: notifier format, notify-now, confluence rebuild, WS refresh, Forex source-label, and legacy UI.
- Production now requires `COOKIE_SECURE=1`. Wildcard CORS is rejected in production even if `DEBUG=1`.
- Auto-refresh control is labelled `خودکار` (polling), not LIVE data.
- Backtest Sharpe is documented as per-trade / not annualized. Same-bar TP/SL remains deferred.

## 2026-08-15 — P3.76 Post-P3.75 adversarial hardening

- `build_data_trust_context` can no longer mint `live_verified=true` from a caller argument.
- Primary UI `frontend/js/main.js` now uses the triple LIVE gate; source pill no longer says زنده from a non-mock label.
- Confluence/WS trust display uses canonical context, not `resolve_trust_level(source)`.

## 2026-08-15 — P3.75 Data Trust Hardening

- Added canonical `live_verified` to `build_data_trust_context()`. It is never inferred from source label or freshness.
- `is_live` is true only when independently verified. `TRUST_LEVEL=live` cannot fabricate live evidence.
- Backend AI, Filter Intelligence, notifier, and frontend trust banner use the triple LIVE gate.
- Provider mappings no longer fabricate `avg_vol_30d` from `bvol`/`tvol`. Missing 30-day history stays unknown (`0`) and does not create volume-spike evidence.

## 2026-08-15 — P3.64 Market Intelligence Session Status

- Wired existing P3.63 `infer_iran_market_session()` into P3.40 `MarketIntelligenceSnapshot.market_status`.
- Snapshot no longer stays at the placeholder `open_unknown` when session inference is available.
- Session-open still does not mark `data_trust` live. Official holidays are still not applied.

## 2026-08-15 — P3.63 Iran Market Session Inference

- Implemented weekday + Asia/Tehran clock inference for the existing `MarketSession` contract.
- Exposed `market_session` on `/api/status` / health status payload.
- Session-open does not mark `data_trust` live. Official holidays are not applied.

## 2026-08-14 — P3.61 Controlled Alpha Gate Evaluation

- Re-evaluated Product Roadmap Lock P3.43 Controlled Alpha Launch gates.
- Repository-side compile/pytest/frontend/alpha scripts passed locally.
- Windows, PowerShell, Browser E2E, Electron, live TSETMC/BRSAPI, and GitHub remain blocked or not verified.
- Application code was not changed. Installation was not started.

## 2026-08-14 — P3.60 Roadmap Gate, No Unauthorized Feature

- Inspected Master Handoff remaining work, Product Roadmap Lock, and architecture deferred lists.
- Did not implement scheduler, automatic deployment, live trading, LLM, or Windows installation.
- Application code was not changed. Next authorized product step remains blocked by target/live/GitHub gates.

## 2026-08-14 — P3.59 Filter Intelligence Performance Compare View

- Added a read-only compare/performance panel on the existing هوش فیلتر tab.
- Uses `GET /api/ai/filters/compare` and stored performance records with `evaluate=false`.
- Missing metrics display as UNAVAILABLE. Non-live data is never labelled LIVE.
- Comparison does not activate ACTIVE versions or deploy proposals.

## 2026-08-14 — P3.58 Filter Intelligence UI Approval Workflow

- Added dashboard tab `هوش فیلتر` (`filter-intel`) for registry, proposals, and human review.
- Wired APPROVE / REJECT / REQUEST_RETEST to the existing P3.41 review API.
- Approval still does not activate production filter versions.
- Non-live data trust is never displayed as LIVE unless `live_verified=true`.
- 24/7 scheduler and automatic composite deployment remain deferred.
- GitHub synchronization remains deferred.

## 2026-08-14 — P3.57 GitHub Authentication Push or Windows Pre-Install Gate

- Re-verified local HEAD `ad7e813` against GitHub `26a2d12`. GitHub is not up to date (30 ahead / 0 behind).
- Confirmed authentication still unavailable. One normal push failed: could not read Username for https://github.com.
- Re-ran full repository-side validation; results match the P3.56 baseline.
- Installation remains locked. No Windows execution, production deployment, database migration, force push, or live-data claim.

## 2026-08-14 — P3.56 GitHub Sync Verification and Windows Pre-Install Transfer

- Re-verified local HEAD `b14feea` against GitHub `26a2d12`. GitHub is not up to date (29 ahead / 0 behind).
- Confirmed authentication unavailable. A normal push failed: could not read Username for https://github.com.
- Re-ran full repository-side validation; results match the P3.55 baseline.
- Added Windows pre-install transfer instructions. Installation remains locked.
- No Windows execution, production deployment, database migration, force push, or live-data claim.

## 2026-08-14 — P3.55 Workspace Recovery and Continuation

- Recovered the empty sandbox from the verified P3.54 TempFile package (`SHA-256 5ba6e1271a12e26d7ad9d3aceebac185322edd5dbbbfe98c5aef35a21b8decd0`, 757 files, ZIP PASS).
- Restored Git history at `2d13cf3` and reconstructed a credential-free `.git/config` with the public origin URL only.
- Restored tracked `backend/app/data/` source files from Git objects after the P3.54 zip omitted them because `.gitignore` contained a broad `data/` rule.
- Narrowed `.gitignore` to `/data/` so only the repo-root runtime directory is ignored.
- Recreated the local validation `.venv` from `backend/requirements.txt` and re-ran full repository-side validation.
- Updated `RADAR_BOURSE_MASTER_HANDOFF.md` and added the P3.55 recovery report.
- Preserved installation lock: no Windows install, target execution, production deployment, database migration, or GitHub push was performed.

## 2026-08-14 — P3.54 Final Artifact External Delivery and GitHub Sync Attempt

- Re-verified actual repository state after P3.53.
- Re-ran full local repository-side validation using the recovered `.venv`.
- Updated `RADAR_BOURSE_MASTER_HANDOFF.md` and added P3.54 final artifact delivery report.
- Produced a final P3.54 project package and attempted external artifact delivery.
- Preserved installation lock: no Windows install, target execution, production deployment, database migration, or GitHub push was performed.

- Created local repository-side validation environment from `backend/requirements.txt` without target/product installation.
- Added `pyflakes>=3.4.0` to `backend/requirements.txt` because pyflakes is a required validation command and was missing from the manifest.
- Re-ran full local validation: compileall, pytest, pyflakes, Node syntax checks, shell syntax checks, alpha runtime, provider fallback validation, and frontend static validation.
- Updated `RADAR_BOURSE_MASTER_HANDOFF.md` and added P3.53 final package/handoff report.
- Preserved installation lock: no Windows install, target execution, production deployment, database migration, or GitHub push was performed.

- Added `RADAR_BOURSE_MASTER_HANDOFF.md` as a root-level master handoff for future supervisor/developer continuity.
- Added P3.52 final project package and handoff report.
- Preserved installation lock: no target installation, service start, dependency installation, database migration, production deployment, or GitHub push was performed.
- Prepared final repository package artifact from the latest local repository state.

- Closed previously untracked handoff and Alpha installation readiness documentation as repository-controlled project assets.
- Added Windows-target Alpha preparation scripts under `scripts/windows/` for prerequisite validation, native install preparation, backend startup, and runtime health validation.
- Added Alpha installation checklist, target validation checklist, runbook, gap analysis, and preparation final report.
- Preserved installation lock: no Windows installation, target execution, service start, database migration, dependency installation, or production deployment was performed.
- Re-ran local regression and validation checks: backend tests, pyflakes, node syntax checks, shell syntax checks, alpha validation scripts, provider fallback checks, and frontend static validation.
- Built a verified Alpha installation readiness artifact for Windows transfer.

- Re-audited repository baseline after P3.43 and verified P3.39 through P3.43 integration surfaces before any installation.
- Verified and re-attached the P3.43 backup artifact for delivery visibility.
- Performed a second RADAR BOURSE terminology audit and removed remaining current-product legacy slug/label usages from Docker, CI, WebSocket message, Electron URL configuration, Android scaffold metadata, and active setup path examples.
- Preserved the documented GitHub remote slug where it is the real repository URL; no remote repository rename was attempted.
- Installation remains deferred and was not started.
- GitHub push remains blocked by missing authentication; no force push or destructive git operation was performed.

- Audited the repository baseline after P3.42 and verified local history, remote read access, and P3.39/P3.40/P3.41/P3.42 integration surfaces.
- Performed RADAR BOURSE terminology cleanup across current user-facing/backend/frontend/Electron/docs surfaces while preserving old terminology only in archived historical phase reports.
- Updated backend default product names, FastAPI description, notifier text, Electron metadata, frontend titles/manifest labels, scripts, and active architecture/status/user documents to use `RADAR BOURSE` / `رادار بورس`.
- Installation remains deferred and was not started.
- GitHub push remains blocked by missing authentication; no force push or destructive git operation was performed.

- Completed repository audit after P3.41 and verified local history through P3.39, P3.40 and P3.41.
- Recovered `origin` to the documented GitHub repository URL and verified read access; push remains blocked by missing authentication.
- Closed the real integration gap between P3.41 Filter Intelligence and P3.39 AI Intelligence Core by adding read-only Filter Intelligence context into `AIContextBuilder` / `AIService.intelligence`.
- Added regression coverage proving AI Intelligence emits `filter_intelligence` evidence when a filter expression is analyzed.
- Preserved all safety gates: no production filter mutation, no autonomous trading, no Windows installation, no live-data claim and no GitHub sync claim without remote SHA verification.

- Added Filter Intelligence domain contracts for registry items, immutable filter versions, performance records, decay signals, AI analysis results, optimization proposals, proposal reviews and version comparison.
- Added `FilterIntelligenceService` using the existing Filter DSL, Strategy/Backtest stack, Walk-Forward, Forward-Test, Market Intelligence regime context and Store `settings_kv` persistence.
- Added AI endpoints for filters, versions, performance, comparison, filter intelligence summary, proposals and human review.
- Integrated P3.41 filter-intelligence context into `AIIntelligenceCore` as controlled evidence.
- Added regression tests for registry, versioning, performance records, data-trust blocking, backtest/walk-forward/forward-test integration, decay detection, AI analysis, proposals, approval/rejection/retest contract, comparison and API smoke.
- Preserved safety gates: no autonomous trading, no broker integration, no automatic production filter mutation, no live-performance claim on non-live data.
- UI approval workflow, 24/7 scheduler, real live-provider performance validation and automatic composite deployment remain deferred.

## 2026-08-09 — P3.40 Market Intelligence & Continuous Monitoring

- Added market-level intelligence contracts: `MarketIntelligenceSnapshot`, `IndustryIntelligence`, `OpportunityRank`, `IntelligenceEvent`, and `MarketMonitoringResult`.
- Added `MarketIntelligenceService` with a callable monitoring cycle for market snapshot, industry intelligence, opportunity ranking, change detection and lightweight history.
- Added AI endpoints: `/api/ai/market-intelligence`, `/api/ai/market-regime`, `/api/ai/opportunities`, `/api/ai/industries`, `/api/ai/events`.
- Added tests for market snapshot creation, industry ranking, non-live trust behavior, events, and API smoke.
- No scheduler, live trading, broker integration, global market expansion, Forex production feature, UI redesign or LLM provider was added.

## 2026-08-09 — P3.39 AI Intelligence Core

- Added deterministic `AIIntelligenceCore` for structured evidence aggregation, confidence scoring, conflict detection and recommendation mapping.
- Added structured result contracts: `IntelligenceEvidence` and `IntelligenceResult`.
- Added endpoint `POST /api/ai/intelligence/{symbol}` using controlled existing market context.
- Added tests for live aligned evidence, non-live data trust blocking, conflicting evidence, unavailable data, service integration and API smoke.
- Updated AI Brain architecture documentation to reflect the implemented core.
- No LLM, autonomous trading, broker integration, UI redesign, global market expansion or Forex expansion was added.

## 2026-08-09 — P3.38 Product Direction & AI Intelligence Architecture Lock

- Added AI Brain architecture as the future analytical core, distinct from a chatbot interface.
- Added Filter Intelligence architecture for future filter performance monitoring, self-optimization suggestions and human approval gates.
- Added Market Abstraction architecture preserving Iran Market as primary, Forex as secondary scaffold and global markets as deferred extension.
- Added Product Roadmap Lock from P3.38 onward.
- No runtime feature, provider rewrite, UI redesign, live trading, global market expansion or AI provider implementation was added.

## 2026-08-09 — P3.37 Alpha Gate Closure Validation

- Re-ran all locally executable Alpha validations, including full backend tests, pyflakes, frontend JS syntax, alpha environment, alpha runtime, provider mock/TSETMC/BRSAPI checks, and frontend static validation.
- Added `docs/active/P3.37_ALPHA_GATE_CLOSURE_REPORT.md` documenting actual local evidence and target-system deferred gates.
- Confirmed TSETMC and BRSAPI are not live-verified in this environment; both remain non-live/fallback or blocked.
- No feature development, provider rewrite, trading logic change, UI redesign, Electron runtime claim, browser E2E claim, GitHub sync claim, or Alpha launch claim was made.

## 2026-08-09 — P3.36 Target-System Final Validation & Controlled Alpha Launch Gate

- Re-ran all locally executable alpha validation checks: backend tests, pyflakes, JS syntax, alpha environment, alpha runtime, provider mock/BRSAPI fallback, and frontend static validation.
- Added `docs/active/P3.36_TARGET_VALIDATION_REPORT.md` documenting local validation, deferred target-system gates, GitHub blocker, and alpha launch decision.
- No feature development, runtime architecture change, provider rewrite, live trading, Cloudflare deployment, or production launch was performed.
- Alpha remains not launched because the target Windows system, browser E2E, Electron runtime, live provider validation, and GitHub sync are still deferred/blocked.

## 2026-08-09 — P3.35 Alpha Target Validation and Controlled Launch Gate

- Re-ran offline/local alpha validation suite and confirmed `110 passed, 1 warning`.
- Verified alpha environment, runtime, provider mock fallback, BRSAPI missing-key handling, and frontend static checks through prepared validation scripts.
- Added `docs/active/P3.35_ALPHA_TARGET_VALIDATION_REPORT.md` documenting local pass, deferred target-system requirements, GitHub blocker, and alpha launch decision.
- Produced a full project archive for target-system handoff.
- No feature development, Cloudflare deployment, live provider claim, live AI, broker integration, UI redesign, or trading logic change was performed.

## 2026-08-09 — P3.34 Alpha Target Validation Preparation

- Added `docs/active/P3.34_ALPHA_TARGET_VALIDATION_AND_LAUNCH_CHECKLIST.md` as the target-system runbook and alpha launch checklist.
- Consolidated offline-ready checks, deferred target-system validations, GitHub sync requirements, browser E2E checklist, Electron validation, provider validation, data-trust acceptance criteria, rollback and recovery instructions.
- Re-ran available regression suite and validation scripts; no runtime feature code was changed.
- No Alpha launch, Cloudflare deployment, live provider claim, browser E2E pass, Electron runtime pass, or GitHub sync was claimed.

## 2026-08-09 — P3.33 Alpha Gate Audit & Target-System Handoff Preparation

- Audited the local phase chain through P3.32 and clarified the dual P3.31 commits: `10bb770` initial implementation and `6046347` corrective hardening.
- Verified alpha handoff artifacts and documented completed-now versus deferred target-system validation.
- Added `docs/active/P3.33_ALPHA_GATE_AUDIT.md` with Alpha Gate Matrix, target-system handoff checklist, and deferred validation boundaries.
- No runtime code, provider logic, AI, frontend, Electron, Docker, or trading logic was changed.
- No GitHub sync or deployment was claimed.

## 2026-08-09 — P3.32 Alpha Deployment Readiness & Deferred Live Validation

- Added offline/target-system validation scripts for Alpha environment, local API smoke, and provider validation.
- Added `docs/ALPHA_DEPLOYMENT_READINESS.md` with completed-now versus deferred target-system validation matrix.
- Added tests for validation scripts, safe BRSAPI missing-key handling, provider mock fallback, and alpha runtime smoke.
- Updated `.env.example` with `DATA_STALE_AFTER_SEC=300` to align with P3.31 freshness gates.
- No live data claim, Cloudflare deployment, broker integration, live trading, UI redesign, global expansion, or new feature expansion was performed.

## 2026-08-09 — P3.31 Live Data & Data Trust Hardening

- Extended canonical data trust states with `stale` and `unavailable` while preserving legacy `trust_level` compatibility.
- Added freshness metadata to `data_trust`: `checked_at`, `age_sec`, `stale_after_sec`, and `stale`.
- Propagated safe provider failure/fallback metadata through `MarketService.data_trust_context()`.
- Added explicit synthetic labels for current fundamental output: `fundamental_source=synthetic`, `is_synthetic=true`.
- Extended AI and backtest warnings for stale/unavailable data without adding a new LLM or changing trading math.
- Extended the existing frontend trust renderer to represent live/mixed/mock/synthetic/stale/unavailable.
- Added focused regression tests for data trust hardening and no-false-live behavior.

## 2026-08-09 — P3.30 Alpha Completion Gate

- Cleaned repository health by removing the temporary `security.py.backup` verification artifact.
- Finalized minimal security hardening already identified by audit: fail-closed private-mode API key behavior, production security configuration validation, route-level protection for sensitive endpoints, and WebSocket private-mode auth enforcement.
- Added security hardening regression tests for private mode, wrong/valid API key, health public access, and production config validation.
- Added `docs/ALPHA_ENV_CONTRACT.md` to document safe Alpha environment variables without secrets.
- Preserved Iran-market core, Filter DSL, Strategy, Backtest, AI, Chart, Windows/Electron, and Forex scaffold without adding large new features.
- No Cloudflare deployment, live data claim, live LLM provider, UI redesign, or global market expansion was performed.

## 2026-08-07 — P3.28 AI Assistant / Analyst / Optimizer & Alpha Transfer

- Added controlled backend AI service with `AIContextBuilder`, deterministic fallback provider and structured AI result schema.
- Added AI endpoints: `/api/ai/assistant`, `/api/ai/analyze`, `/api/ai/optimize`.
- Added data-trust propagation, confidence, uncertainty, evidence, warnings and safety metadata to AI outputs.
- Added tests for AI assistant, analyst, optimizer, invalid filter handling and API smoke.
- Added `docs/architecture/AI_ASSISTANT_ANALYST_OPTIMIZER.md`.
- Added `docs/ALPHA_SETUP_GUIDE.md` for restoring, validating and running the Alpha candidate on the main computer.
- Prepared P3.28 transfer manifest and full project backup workflow.
- No live LLM provider, AI Copilot rewrite, autonomous trading, broker integration, dashboard, UI redesign or new market was added.

## 2026-08-07 — P3.27 Backtest, Walk-Forward Test & Forward Test

- Added next-bar simulated execution for filter/strategy backtests to reduce look-ahead bias.
- Added execution configuration for capital, position sizing, commission, slippage, take-profit, stop-loss and max-hold bars.
- Added performance metrics: total return, net PnL, trade count, win rate, average win/loss, profit factor, drawdown, Sharpe status and equity curve.
- Added walk-forward out-of-sample window evaluation and simulated forward-test boundary.
- Integrated P3.26 `FilterStrategy` as a consumer of Filter DSL in the backtest engine.
- Expanded existing `/api/backtest/run` additively without creating a new dashboard or rewriting frontend UI.
- Added tests for next-bar execution, commission/slippage, no-trade scenario, multiple trades, walk-forward separation, forward boundary, and data trust preservation.
- Added `docs/architecture/BACKTEST_WALK_FORWARD_FORWARD_TEST.md`.
- No live trading, broker integration, paper trading account, AI, dashboard, UI redesign, or new market was added.

## 2026-08-07 — P3.26 Filter DSL & Strategy Framework

- Stabilized the safe Filter DSL parser/validator/execution boundary.
- Added explicit filter expression contracts: `FilterExpression`, `ExpressionNode`, `parse_filter`, `validate_filter`, and `expression_tree`.
- Added bounded AST validation for expression length, node count and depth.
- Added declarative indicator references: `sma(period)`, `avg_volume(period)`, `rsi(period)`, `high(period)`, and `low(period)`.
- Preserved backward compatibility for existing saved filters and `compile_filter()` behavior.
- Added initial strategy framework contracts in `backend/app/domain/strategy.py` without implementing backtest/forward-test/paper trading.
- Added tests for parser metadata, valid/invalid expressions, injection protection, indicator references, market data aliases, and strategy contracts.
- Added `docs/architecture/FILTER_DSL_STRATEGY_FRAMEWORK.md`.
- No AI Copilot, LLM, dashboard, market, UI redesign, global expansion, broker integration, or backtest rewrite was added.

## 2026-08-07 — P3.25 Iran Market Data & Domain Stabilization

- Added canonical data-trust classification for `live`, `mixed`, `mock`, and `synthetic` sources.
- Preserved backward-compatible `trust_level` values while exposing richer `data_trust` metadata for market-intelligence outputs.
- Added Iran market domain contracts: `DataTrustState`, `MarketDataProvenance`, `IranInstrument`, `MarketSession`, and `OHLCVBar`.
- Updated data-quality scoring so mock/synthetic source snapshots cannot be scored as live trust.
- Added `data_trust` metadata to key service/API outputs without changing existing runtime behavior or removing current fields.
- Added tests for data trust classification, Persian symbol/instrument encoding, OHLCV contract, and mock trust scoring.
- Added `docs/architecture/IRAN_MARKET_DATA_DOMAIN.md`.
- No new market, dashboard, AI feature, filter feature, strategy builder, forward test, UI redesign, or mobile/global expansion was added.

## 2026-08-07 — P3.24 Core Product Consolidation & Iran Market Architecture Lock

- Verified GitHub `main` baseline at `26a2d120b596aa298a40b2ebc6952310658f45b5`.
- Updated active status documentation to mark P3.23/P3.23-R1 as completed on GitHub.
- Added `docs/architecture/IRAN_MARKET_ARCHITECTURE_LOCK.md` to document the current Iran-market-first architecture boundaries.
- Documented the Data Trust terminology: LIVE, MIXED, MOCK, SYNTHETIC.
- Documented AI boundaries: implemented rule-based explainability versus future Copilot/LLM/Research Agent/Multi-role work.
- Documented Decision Support as partial confluence-based support, not a complete multi-role Decision Center.
- Documented frontend/API boundary debt without performing a large refactor.
- No product feature, engine, dashboard, market, UI redesign, or mobile/global expansion was added.

## 2026-08-07 — P3.23-R1 Repository Consolidation Closure

- Consolidated documentation into active, architecture, and archive areas.
- Added `docs/STATUS.md` as the current status source.
- Preserved historical reports under `docs/archive/phase-reports/`.
- Confirmed `frontend-next` does not exist in the repository.
- Audited industry tabs and confirmed only `data-tab="industry"` exists in the current frontend.
- Kept Iran market focus and did not add product features.

## Historical Records

Detailed historical changelogs and inspection reports are preserved in:

- `docs/archive/phase-reports/`
