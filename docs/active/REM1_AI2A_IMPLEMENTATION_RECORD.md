# REM-1 / AI2-A — Full Remaining-Code Audit, Remediation, and AI-2 Category A Record

Date: 2026-10-17 (Asia/Tehran) · Baseline: `a578abe8296a08152dfb282839519d6d05523647` (P3.92, on top of `6ff6b07` P3.93, `c1984e7` P3.91)
Naming note: the IDs **REM-1** (remediation batch 1) and **AI2-A** (AI-2 Category A) are deliberately used instead of a next "P3.94" number, because a *reported* "P3.94" exists only in a second, unsynced workspace whose commits are absent from this repository (`db16a2c…f538806` — NOT_PRESENT, verified 2026-10-17). This avoids lineage collision.

## 1. Audit scope actually inspected

- `backend/app` — 60 modules / 14,663 lines. Full reads: `core/config.py`, `core/security.py`, `core/rate_limiter.py`, `core/audit.py`, `core/crypto.py` (head), `api/auth.py`, `api/routes.py` (all 944 lines), `main.py` (all 376 lines), `services/ai_service.py` (all 594 lines), `domain/ai_provider.py` (all 408 lines), `data/store.py` (head + concurrency paths), `services/ws_hub.py` (all). Targeted reads: `services/market_service.py` (locking, `get_analysis`, symbol path), `engines/backtest.py` (same-bar policy), `data/providers.py` + `data/forex_provider.py` + `services/notifier.py` + `engines/trade_detail.py` (HTTP timeout sweep).
- `backend/tests` — 37 files / 4,242 lines; lint sweep + targeted reads of every flagged site.
- `frontend/js` — security-sink sweep (localStorage, innerHTML, eval/document.write), `modules/custom_indicator.js` evaluator, legacy loader (prior audit reused).
- CI: `.github/workflows/ci.yml` (pyflakes `app/` only; pytest; pip-audit `-r requirements.txt`; Python 3.13).
- Prior evidence reused (not re-investigated): P3.76/P3.87/P3.88 audits, 2026-10-17 truth sweep, two-workspace reconciliation battery of the same date.
- Grep sweeps across the whole tree: TODO/FIXME/stub markers, bare `except:`, `eval/exec/pickle/yaml.load/shell=True/os.system/verify=False`, `print(`, `time.sleep` in app code, HTTP calls without timeouts, weak hashes. Results: no bare excepts, no dangerous dynamic-execution calls, no `verify=False`, no prints, no sleeps in app code; every `httpx` call carries an explicit timeout.

## 2. Findings ledger (verified)

| ID | Severity | Location | Finding | Class | Disposition |
|---|---|---|---|---|---|
| F1 | Low | `backend/app/core/rate_limiter.py:35-37` | Docstring claimed 120/min general and 20/min heavy while the code enforces 150/min (`:52`) and 25/min (`:59`); login 5/min + 20/hour undocumented in the docstring | Confirmed defect (stale doc-in-code; zero runtime impact) | **Fixed in REM-1** — docstring aligned to code; no behavior change |
| F2 | Low | `backend/tests/test_data_domain.py:77` | Unused variable `now` | Technical debt (lint) | **Fixed** — assignment removed, explanatory comment kept |
| F3 | Low | `backend/tests/test_data_trust_hardening.py:2` | Unused import `SimpleNamespace` | Technical debt (lint) | **Fixed** |
| F4 | Low | `backend/tests/test_metrics.py:1` | Unused top-level `import pytest` (local import at :26 is the used one) | Technical debt (lint) | **Fixed** — top-level import removed; local import kept |
| F5 | Low | `backend/tests/test_security_rate_limit.py:4` | Unused `import pytest` | Technical debt (lint) | **Fixed** |
| F6 | Low | `backend/tests/test_security_rate_limit.py:43` | Unused `from unittest.mock import MagicMock` | Technical debt (lint) | **Fixed** |
| F7 | Low | `backend/tests/test_auth.py:4` | Unused `import pytest` | Technical debt (lint) | **Fixed** |
| F8 | Info | `frontend/js/modules/custom_indicator.js:126` | Formula sandbox uses a blocklist (`import`, `Function(`, …) rather than an allowlist parser; iteration/timeout guards exist (P0-4) and the surface is client-side, same-origin user input | Technical debt without demonstrated failure | Recorded for owner discretion; not changed (no JS test harness; behavior risk without owner authorization) |
| F9 | Info | `backend/app/core/security.py:258` | `TODO in v0.7: move to nonce-based CSP` — planned hardening; current CSP is already `script-src 'self'` (no inline scripts) | Technical debt (planned work) | Recorded; unchanged |
| F10 | Info | Middleware surface | No test asserts the literal HTTP 429/Retry-After response for auth rate limiting (tests assert limiter decision logic) | Coverage gap (informational, pre-existing from P3.93 QA) | Recorded; owner discretion |
| F11 | — | Environment | Python 3.13 CI parity, Windows-target validation, Claude CLI recognition, live-provider verification (`live_verified=false`) | Not verified (no evidence here) | Marked NOT_VERIFIED; unchanged |

Verification-after-fix: `pyflakes app tests` → **0 findings (exit 0)**; full suite `308 passed, 2 warnings` — identical to baseline, proving the 7 lint fixes and the docstring fix introduced no regression. Raw evidence: `docs/governance/evidence/raw/2026-10-17_rem1_ai2a/`.

## 3. Roadmap mapping (code-related items)

- P0–P3 chain through P3.92/P3.93: PROVEN_COMPLETE with commit + test evidence (STATUS rows, prior audits). No new implementation gap was found in this audit that belongs to an existing roadmap row.
- P3.43 Controlled Alpha Launch: BLOCKED (owner gates: Windows INSTALL authorization, live-provider verification, push auth).
- G2: OWNER_GATE / NOT_PASSED — blocks real-data AI-2 (see §4).
- 2026-10-02 amendment corpus (authoritative AI-2 definition, G2 criteria, 17-role charter, roadmap weights): NOT_SYNCED — dependency recorded; all AI-2 work below is scoped so it does not depend on the missing corpus.

## 4. AI2-A — AI-2 Category A implementation (offline scaffold)

**Implemented** (commit recorded in CHANGELOG/STATUS; local only):

- `backend/app/services/ai2_service.py` — second-stage analysis service:
  - Typed contracts: `AI2Request`, `AI2Interpretation` (strict schema: bounded `summary`, list fields, `confidence ∈ [0,1]`), `AI2Provenance`, `AI2Result` with explicit statuses `gated_not_executed | executed_shadow | executed | failed_provider | failed_schema`.
  - Deterministic-domain integration reuses the existing `AIContextBuilder` + `build_controlled_provider_prompt` (no parallel architecture); deterministic financial values are domain-owned and never overwritten by model text.
  - Provider invocation reuses the P3.83/P3.85/P3.86 seam `invoke_ai_provider` (client-secret rejection, HTTPS-only transport, explicit timeout, bounded retries, `live_llm=False`).
  - Strict output validation: model text must parse as JSON and validate against `AI2Interpretation`; failures map to `failed_schema` (`invalid_json | schema_not_object | schema_validation_failed:<count>:<paths>`) with no payload echo.
  - Deterministic failure mapping: timeout → `failed_provider/timeout`; HTTP 4xx (non-429) no-retry → `failed_provider/http_4xx`; seam failure codes preserved.
  - Provenance on every outcome (including gated ones): SHA-256 of the canonical input snapshot, data-trust state, `live_verified`, provider mode/label/status/error code, schema validity, gate report, UTC timestamp.
  - Secret-free structured logging (`shekar.ai2`): statuses, task, error codes, gate states, truncated input hash only — never prompts, payloads, or credentials.
  - Fail-closed gates, in order: (1) `AI2_ENABLED` (default **off**); (2) production path (no injected transport) requires `is_verified_live(data_trust)` — which cannot be minted in this repository today (`build_data_trust_context` hard-codes `verified=False`) — so real-data AI-2 is **structurally unreachable** until G2 independent validation + owner acceptance are recorded by the owner.
  - No HTTP route is exposed for AI-2: the owner-facing AI-2 surface is defined in the NOT_SYNCED amendments and was not invented here.
- `backend/app/core/config.py` — additive `ai2_enabled` setting (`AI2_ENABLED`, default `0`).
- `backend/tests/test_ai2_service.py` — 12 mock-based tests: gate default-off (seam-spy proves no invocation), G2 production gate (seam-spy), shadow execution with valid schema, malformed JSON, wrong types, confidence bounds, timeout mapping, HTTP 4xx no-retry, provenance hash determinism + input sensitivity, stale-data recording/warning, secret-free result+logs, and the future live-gated mapping path (mocked seam, crafted fixture, documented).

**Gate classification of AI-2 deliverables**

- **A — implemented and tested now (offline/mock):** module, contracts, schema validation, failure paths, provenance, audit logging, security-boundary tests, config flag, documentation. All pass locally.
- **B — requires missing source material / external infrastructure:** authoritative AI-2 task definition + acceptance criteria (2026-10-02 amendments, NOT_SYNCED); owner-facing route/UX design; live provider credentials; real provider contract tests.
- **C — requires independent G2 validation:** any execution against real market data; live-provider end-to-end AI-2 runs; `live_verified` transition.
- **D — requires explicit owner acceptance/production authorization:** enabling `AI2_ENABLED=1` outside tests; production deployment; any use of AI-2 output as more than advisory.

**Explicitly not done (governance):** no route added, no `live_verified` transition, no G2 self-approval, no real-data execution, no model output promoted to authoritative financial data, no client-facing surface invented.

## 5. Verification commands (exact)

```bash
# cwd: /home/z/my-project/RADAR_BOURSE/repo/backend ; interpreter: repo .venv (Python 3.12.15)
PYTHONPATH=. ../.venv/bin/python -m pyflakes app tests          # exit 0 (was: exit 1, 7 findings)
PYTHONPATH=. ../.venv/bin/python -m pytest tests/test_ai2_service.py -q   # 12 passed
PYTHONPATH=. ../.venv/bin/python -m pytest -q                    # 308 passed, 2 warnings (baseline == final)
../.venv/bin/python -m compileall -q app tests                   # exit 0
../.venv/bin/python -m pip_audit                                 # No known vulnerabilities found
../.venv/bin/python scripts/validate_bootstrap_config.py         # 8/8 PASS (run from repo root)
git diff --check                                                 # exit 0
```

(Exit codes and durations recorded in `docs/governance/evidence/raw/2026-10-17_rem1_ai2a/00_exit_codes.txt`; tested SHA noted in `00_context.txt`.)
