# W2-QA — INDEPENDENT QA REPRODUCTION REPORT (MASTER-WAVE-1 + CONSOL-NEXT §3–§5)

- **Auditor:** Independent QA agent (W2-QA), temporary engineering team; not the implementer.
- **Repo:** `/home/z/my-project/RADAR_BOURSE/repo`
- **HEAD under audit:** `7c225cb1ce2771473f1f646be9c4282348ea7657` (branch `main`) — verified unchanged at session start and session end.
- **Method:** every acceptance claim re-executed from the committed tree; the implementer's narration was treated as unproven. All commands run via the repo venv (`repo/.venv/bin/python -m pytest`, cwd `backend`) unless stated.
- **Mutation discipline:** repo is READ-ONLY except the single authorized stash round-trip (see Item 2 for what actually happened — the tree was already clean, so the stash push was a no-op). The pre-fix (false-fresh) direction was reproduced in an **isolated disposable copy** of the committed tree under `/tmp` (`git archive HEAD | tar -x`), so the real repo was never modified. Copy deleted after the run.

---

## ITEM 1 — Full battery

**Command:** `cd backend && ../.venv/bin/python -m pytest tests/ -q`

**Observed:**
```
1436 passed, 1 skipped, 2 warnings in 12.27s
EXIT=0
```
Warnings = 2 framework deprecations (`fastapi/testclient.py` StarletteDeprecationWarning httpx2; `starlette/testclient.py:53` anyio BlockingPortal alias) — environmental, not test failures. The single skip is at the 60% progress mark, consistent with the long-standing 1-skip baseline.

**Claim under test:** MASTER-WAVE-1 §5: "1436 passed / 1 skipped / 2 warnings in 12.69 s, exit 0".

**Verdict: REPRODUCED** (exact counts and exit code; duration 12.27 s vs 12.69 s — immaterial). Delta arithmetic also holds: 1404 (CONSOL-NEXT battery) + 3 (Q-1 concurrency) + 9 (JSONL adapter) + (44 − 24) (scaffold factory parameterization) = 1436.

---

## ITEM 2 — Q-1 reproduction, both directions

### (a) Fix present (HEAD tree) — `backend && ../.venv/bin/python -m pytest tests/test_refresh_degraded_token_concurrency.py -q`
```
3 passed in 0.64s
```
Targeted run of the decisive node: `tests/test_refresh_degraded_token_concurrency.py::test_interleaved_fresh_cycle_must_not_steal_degraded_cycle_marker` → `1 passed in 0.43s`.

**Verdict: REPRODUCED** (3/3, matching MASTER-WAVE-1 §5 "Q-1 concurrency file 3/3").

### (b) Pre-fix direction (expect the false-fresh FAILURE) — procedure deviation, honestly recorded

**Literal instruction executed:** from repo ROOT:
```
git stash push -- backend/app/services/market_service.py
→ "No local changes to save"  (exit 0)
```
`git stash list` before and after: **0 entries**. Reason: **the tracked tree at HEAD is CLEAN — the wave work (fix + tests + records) is already COMMITTED as `7c225cb` itself.** There is no uncommitted `market_service.py` modification for stash to operate on, so the instructed "stash → expect FAILURE → pop" round-trip is unexecutable at this HEAD as literally specified. The briefing's expected post-pop `git diff --stat` ("market_service.py +18/−4 and test_ai3_acceptance_scaffold.py") cannot exist at `7c225cb`; the equivalent diff exists only between `HEAD~1` and `HEAD` (`git diff HEAD~1 HEAD --numstat` → `market_service.py 14 4`; `test_ai3_acceptance_scaffold.py 8 4`). This is **FINDING F-1 (MEDIUM, briefing-premise)** — details in Findings.

**Compensating reproduction (authorized in spirit, zero repo mutation):** the committed tree was exported to a disposable copy (`git archive HEAD | tar -x -C /tmp/qa_w2_prefix`), and in that copy ONLY, `backend/app/services/market_service.py` was replaced with the pre-fix version (`git show HEAD~1:backend/app/services/market_service.py`) — i.e. exactly the record's "working tree without the hardening" shape (HEAD's test files + pre-fix service). The real repo was not touched.

**Command (in the copy):** `.venv/bin/python -m pytest tests/test_refresh_degraded_token_concurrency.py -q`
```
FAILED tests/test_refresh_degraded_token_concurrency.py::test_interleaved_fresh_cycle_must_not_steal_degraded_cycle_marker
1 failed, 2 passed in 0.48s
```
Decisive assertion, verbatim from the run:
```
AssertionError: Q-1 FALSE-FRESH REPRODUCED: the degraded cycle re-stamped its
recycled data as fresh (a_stamp=1793621488.9846501 != old_ts=1793611488.9756927)
— the shared _fetch_degraded marker was clobbered by the interleaved fresh
cycle's Phase-1 write before the degraded Phase-3 read
```
The two companion tests (`test_sequential_cycles_unchanged_no_interleaving`, `test_mirrored_attribute_matches_cycle_outcome_after_completion`) **passed on the pre-fix shape**, exactly as the record claims ("sequential-semantics pin that must hold before AND after the fix"; mirror contract byte-identical).

**Verdict: REPRODUCED** — the false-fresh defect is real, deterministic, and the test is load-bearing: it fails on the shared-attribute shape and passes with the per-cycle local token. Both directions of MASTER-WAVE-1 §2 are independently confirmed.

### Stash round-trip integrity statement
The authorized round-trip was attempted literally and turned out to be a **no-op** ("No local changes to save"; no stash entry created; nothing to pop). Post-attempt integrity, all verified in-session and again at session end:
- `git diff --stat` → **empty (0 lines)**
- `git status --short` → **byte-identical to session start** (compared via sorted snapshots `/tmp/qa_status_before.txt` vs final; `diff` → identical)
- `git stash list` → **0 entries** (before and after)
- `git rev-parse HEAD` → `7c225cb1ce2771473f1f646be9c4282348ea7657` (unchanged)
- single worktree; no commit/checkout/reset performed anywhere in the real repo.

---

## ITEM 3 — Focused suites (exact counts)

| Suite (glob) | Command result | Claim | Verdict |
|---|---|---|---|
| `tests/test_ai3_jsonl_reference_adapter.py` | `9 passed in 0.30s` | 9 | REPRODUCED |
| `tests/test_ai3_acceptance_scaffold.py` | `44 passed in 0.30s` | 44 (22 tests × 2 factories via `STORE_FACTORIES`, scaffold.py:100) | REPRODUCED |
| `tests/test_p3_quality_validation_*.py` | `34 passed in 0.41s` (5 files: evaluation_statistics, golden_set, holdout, regime_slices, survivorship_guard) | 34 | REPRODUCED |
| `tests/test_ai_runtime_integration_*.py` | `27 passed in 1.52s` (3 files) | 27 | REPRODUCED |
| `tests/test_p5p6_integration_*.py` | `16 passed, 2 warnings in 0.97s` (3 files) | 16 | REPRODUCED |

Per-file P5/P6 split: `test_p5p6_integration_alert_ops_api.py` 4 passed · `test_p5p6_integration_delivery_surfaces.py` 8 passed · `test_p5p6_integration_store_purge_boundary.py` 4 passed = 16.

**Verdict: ALL REPRODUCED, exact counts.**

---

## ITEM 4 — Gates sweep (all re-derived at HEAD, with line numbers)

| Gate | Command / locus | Observed | Verdict |
|---|---|---|---|
| AI2_ENABLED default "0" | `sed -n '111p' backend/app/core/config.py` | `ai2_enabled: bool = _env_bool("AI2_ENABLED", "0")` — **exactly line 111** | REPRODUCED |
| verified=False | `sed -n '284p' backend/app/core/config.py` | `verified = False` (hardcoded; "Independent verification is never inferred … This environment has no live-verification boundary.") — **exactly line 284** | REPRODUCED |
| zero `ai2` refs under `backend/app/api/` | `git grep -n "ai2" backend/app/api/` → **exit 1, zero hits**; case-insensitive `rg -ni "ai2" backend/app/api/` → **exit 1, zero hits** | empty | REPRODUCED |
| AI-5 kill switch default ENGAGED | `backend/app/domain/proactive_research.py:102` | `kill_switch: KillSwitchState = "ENGAGED"` (default field value in the contract model) — **exactly line 102**, matching the "~:102" claim | REPRODUCED |
| execution_mode SYNTHETIC_OR_PAPER posture | `backend/app/domain/g2_gate.py:277` `ExecutionMode = Literal["LIVE","SYNTHETIC_OR_PAPER"]`; `:287` `return "LIVE" if live_verified else "SYNTHETIC_OR_PAPER"` | Since `verified` is structurally `False` (config.py:284) and cannot be minted, the effective mode is always `SYNTHETIC_OR_PAPER`; `ai2_research_loop.py:456` also force-labels `execution_label = "SYNTHETIC_OR_PAPER"` | REPRODUCED |
| no live-trading/order path | pattern sweep `rg -ni "live_trading\|place_order\|submit_order\|order_execution\|execute_order\|send_order\|create_order\|real_money\|broker_api\|trading_api" backend/app/` | **exactly ONE hit:** `backend/app/engines/backtest.py:483: "live_trading": False,` — a negative attestation inside the `quant_safety` block of the backtest report | REPRODUCED (single hit = the negative attestation, as claimed) |

**Verdict: ALL GATES REPRODUCED.**

---

## ITEM 5 — WS-B spot-check: TabloKhani capability matrix (8 of 32 rows sampled)

Doc: `docs/active/TABLOKHANI_CAPABILITY_MATRIX.md` (213 lines; capability table = 32 rows at lines 74–105; claims inventory C1–C8 at lines 118–125). For each sampled row, at least one cited `file:line` (existence + content match) and one cited test id (existence) were re-verified at HEAD, and the status label was checked for honesty (no superiority claim in `NOT_COMPARED_WITH_EVIDENCE` rows).

| Row (matrix line) | Capability | Citations re-verified (observed content) | Status label | Verdict |
|---|---|---|---|---|
| 1 (:74) | Market data ingestion (TSETMC) | `providers.py:232` = `class MarketDataProvider:` ✓; `:250` = `async def fetch(...)` ✓; test `test_p3_90_7_tsetmc_cdn_schema.py::test_cdn_schema_without_l18_is_accepted` exists at :51 ✓ | NOT_COMPARED_WITH_EVIDENCE (reference mechanism NOT_DESCRIBED_IN_SOURCES) | **SUPPORTED** |
| 3 (:76) | Technical indicators | `indicators.py:39` `def macd(...)` ✓, `:60` bollinger ✓, `:80` stochastic ✓, `:119` atr ✓, `:144` adx ✓; `test_indicators.py::test_macd_shape` at :29 ✓ | NOT_COMPARED_WITH_EVIDENCE | **SUPPORTED** |
| 7 (:80) | Backtest engine | `backtest.py:70` `class ExecutionConfig:` ✓, `:329` `def run_filter_strategy_backtest(` ✓, `:494` `def run_backtest(` ✓; `test_backtest_framework.py:26` `test_backtest_entry_executes_next_bar_no_lookahead` ✓ | NOT_COMPARED_WITH_EVIDENCE | **SUPPORTED** |
| 10 (:83) | Multi-testing controls | `evaluation_statistics.py:85` `def bonferroni_adjust(...)` ✓, `:98` `def benjamin_hochberg_adjust(...)` ✓; `test_evaluation_statistics.py:32` `test_bonferroni_hand_computed` ✓ | NOT_COMPARED_WITH_EVIDENCE | **SUPPORTED** |
| 16 (:89) | AI research loop (synthetic/paper) | `ai2_research_loop.py:284` `class AI2ResearchLoopRunner:` ✓; `config.py:111` AI2_ENABLED="0" ✓ (re-verified in Item 4); `test_ai2_research_loop.py:182` `test_outcome_status_map_pins_shadow_to_non_completed` ✓ | NOT_COMPARED_WITH_EVIDENCE | **SUPPORTED** |
| 21 (:94) | Hot money | `screener.py:154` `def _flow_score(` ✓, `:187` `def build_hot_money(` ✓; `config.py:47` `hot_money_threshold: float = 200_000_000` ✓, `:54` `smart_per_capita_min: float = 25_000_000` ✓; `schemas.py:272` `flow_score` field ✓ | NOT_COMPARED_WITH_EVIDENCE — row explicitly says RADAR thresholds match the *taught* thresholds but "whether the runtime behaviour matches the reference site itself is unmeasured" | **SUPPORTED** |
| 24 (:97) | Rant/leader/growth filters — **the single UNKNOWN row (31/32 NOT_COMPARED + 1 UNKNOWN per CONSOL §3)** | `screener.py:293` `def build_industry_flow(` ✓ exists; the video-2 leader pseudocode `tval*0.1 + buy_power*10 + volume_ratio*5 + plp*2` exists **verbatim in the archive** (`docs/archive/phase-reports/summary-of-tablokhani-videos.md:39–44`) ✓; a leader-formula sweep over `backend/app/engines/` found **no verbatim implementation** (grep exit 1) ✓ — so the row's UNKNOWN(partial implementation) honesty is correct | UNKNOWN(reason given) — makes no superiority claim | **SUPPORTED** |
| 32 (:105) | Heatmap tiles | `frontend/js/components/heat-tiles.js:1–3` exists with the claimed Persian header "کاشی‌های هیت‌مپ (پول داغ / تحرکات بزرگان)" ✓; `frontend/js/tabs/data.js` big-moves tab with `bigView === "matrix"` present in the cited range ✓; the row's "path note" is honest: `frontend/js/app.js` **does not exist** (ls → "No such file or directory"), exactly as the row discloses ✓ | NOT_COMPARED_WITH_EVIDENCE | **SUPPORTED** |

Cross-checks: `AT_PARITY_EVIDENCE_BASED` occurs exactly once in the whole doc — line 58, the rule text itself ("**Never used in this matrix**") — zero row uses it ✓. Sample covered beginning/middle/end of the table across data-ingestion, indicators, backtest, statistics, AI, screener, UNKNOWN-partial, and frontend domains.

**Verdict: 8/8 sampled rows SUPPORTED; no superiority claim found in any sampled row.** The 24 unsampled rows were NOT exhaustively re-verified (see "Not verified").

---

## ITEM 6 — WS-A spot-check (P5/P6 + D-AI-30 purge boundary)

1. **Three integration test files exist and run green:** `test_p5p6_integration_alert_ops_api.py` (4 passed), `test_p5p6_integration_delivery_surfaces.py` (8 passed), `test_p5p6_integration_store_purge_boundary.py` (4 passed) → 16 total, matching CONSOL §3. **REPRODUCED.**

2. **D-AI-30 purge boundary** — `backend/app/data/alert_ops_store.py:526-538` `purge_expired_records(now, retention_days)`. The method executes **exactly four DELETE statements**, all from the fixed tuple at :530-534 via `c.execute(f"DELETE FROM {table} WHERE {col} < ?", (cutoff,))` at :536:
   - `DELETE FROM alert_ops_outbox WHERE created_at < ?`
   - `DELETE FROM alert_ops_inbox WHERE delivered_at < ?`
   - `DELETE FROM alert_ops_dead_letter WHERE dead_lettered_at < ?`
   - `DELETE FROM alert_ops_audit WHERE ts < ?`
   All four targets are `alert_ops_*`-namespaced; no other table can be reached from this method. **REPRODUCED** (CONSOL §3: "exactly four namespaced `DELETE FROM alert_ops_*` statements").

3. **Co-tenant foreign-table survival:** `test_p5p6_integration_store_purge_boundary.py::test_purge_cannot_touch_cotenant_foreign_tables` (:158) seeds `episodic_research_evidence` + `document_ledger_entries` in the same shared DB with **3650-day-old** rows, runs the service purge, and asserts both tables keep both rows (`E-ANCIENT`,`E-FRESH`) — byte-identical survival. Passed as part of the 4/4. Plus structural pin `::test_store_module_deletes_only_alert_ops_namespaced_tables` (:191) asserting every `DELETE FROM` target in the whole module ⊆ {outbox, inbox, dead_letter, audit, budget_counters}. **REPRODUCED** (matches CONSOL §3 wording incl. "3650-day-old rows … survives purge byte-identically"; note the module-wide set also includes `alert_ops_budget_counters` deleted at :427, which is still alert_ops-namespaced and inside the pinned set).

4. **No notifier/ws_hub edge for governed alerts (AST proof):** `test_p5p6_integration_delivery_surfaces.py::test_governed_alert_lifecycle_has_no_edge_to_legacy_delivery_surfaces` (:228) AST-parses the five governed-alert modules (`app.domain.governed_alerts`, `app.domain.alert_operations`, `app.data.alert_ops_store`, `app.services.alert_operations`, `app.api.alert_ops`) and asserts no `Import`/`ImportFrom` node roots at `app.services.notifier`, `app.services.ws_hub`, `telegram`, `bale`. Passed (within the 8/8). Channel closure confirmed independently: `backend/app/domain/alert_operations.py:42` `DeliveryChannel = Literal["IN_PRODUCT_INBOX"]`, `:43` `DELIVERY_CHANNEL: DeliveryChannel = "IN_PRODUCT_INBOX"`. **REPRODUCED** (CONSOL §3: "type-closed Literal['IN_PRODUCT_INBOX'] — no notifier/ws_hub edge exists (AST import-graph proof added as a test)").

5. **CONSOL §4 spot-checks:** `AI3_PERSISTENCE_DECISION_PACKET.md:3` = "**ALL SEVEN DECISIONS PENDING** — no owner decision recorded as of 2026-11-02; none assumed…" ✓; `AI3_PERSISTENCE_IMPLEMENTATION_PLAN.md` = **486 lines** exactly ✓; scaffold `STORE_FACTORIES` registry at `test_ai3_acceptance_scaffold.py:100` driving 44 parameterized nodes ✓. **REPRODUCED.**

---

## ITEM 7 — Workspace purity

**Command:** `git status --short` (compared byte-wise against session-start snapshot).

**Observed untracked set (exactly 6 entries, stable across the entire session):**
```
?? .claude/
?? CLAUDE.md
?? docs/governance/PROJECT_EXECUTION_STATE.md
?? docs/governance/evidence/
?? scripts/r13_owner_repo_setup.sh
?? scripts/validate_bootstrap_config.py
```
**Tracked tree: CLEAN** (`git diff --stat` empty; no modified/deleted/staged entries; HEAD `7c225cb…` unchanged; stash 0; single worktree).

**Reconciliation with the mission's expected 9-item list:** the three backend test files in that list (`backend/tests/research_memory_jsonl_reference.py`, `backend/tests/test_ai3_jsonl_reference_adapter.py`, `backend/tests/test_refresh_degraded_token_concurrency.py`) are **TRACKED at HEAD** (committed in `7c225cb`, per `git ls-files`). The actual untracked set is therefore a **strict subset** of the allowed list — the "ONLY" constraint holds; the deviation is that the briefing still described the wave files as untracked. **FINDING F-1 / F-3 applies** (briefing premise outdated; the wave was published). No untracked file outside the allowed set exists.

**Verdict: REPRODUCED (with the tracked-vs-untracked nuance recorded).**

---

## ITEM 8 — pyflakes

**Command:** `cd backend && ../.venv/bin/python -m pyflakes app/ tests/research_memory_jsonl_reference.py tests/test_ai3_jsonl_reference_adapter.py tests/test_refresh_degraded_token_concurrency.py`

**Observed:** no output; **exit 0**.

**Verdict: REPRODUCED** (MASTER-WAVE-1 §5 pyflakes claim holds; this run extends the sweep from the single touched service file to the whole `backend/app` tree, also exit 0).

---

## FINDINGS

| ID | Severity | Finding |
|---|---|---|
| F-1 | **MEDIUM** (briefing-premise / process, not a code defect) | The QA briefing for Item 2(b) assumes the wave work is UNCOMMITTED (working tree carrying `market_service.py` +18/−4 and `test_ai3_acceptance_scaffold.py` modifications, recoverable via `git stash push/pop`). At HEAD `7c225cb` this is false: the wave **is** the HEAD commit and the tracked tree is clean, so `git stash push -- backend/app/services/market_service.py` is a no-op ("No local changes to save") and the instructed pre-fix reproduction cannot be performed in-repo without an unauthorized checkout/reset. Compensating reproduction in an isolated `/tmp` copy of the committed tree (pre-fix `market_service.py` from `HEAD~1` + HEAD's tests) **did** reproduce the false-fresh failure (1 failed / 2 passed) and the post-fix pass (3/3), so the record's technical claims are fully vindicated — but the specified procedure is unexecutable at this HEAD. Any future QA must either run at a pre-publication state or use the isolated-copy method. |
| F-2 | **INFO** | The record's delta notation "`market_service.py`, +18/−4" does not match numstat semantics: `git diff HEAD~1 HEAD --numstat` = **14 insertions / 4 deletions** (18 total changed lines). The notation matches the `git diff --stat` summary format (18 changed lines of which 4 deletions) but reads incorrectly as numstat. Mission briefing repeats "+18/−4". Cosmetic; no content impact. |
| F-3 | **INFO** | The mission's expected untracked set (9 items) is partially stale: 3 of its members are tracked at HEAD (committed by the wave). Actual untracked set = 6 items, a strict subset of the allowed list; no foreign untracked file exists. Workspace discipline per MASTER-WAVE-1 §5 is confirmed at HEAD. |
| F-4 | **INFO** | The authorized stash round-trip, executed literally, was a no-op; therefore the "restored byte-identically" guarantee is satisfied trivially (nothing was ever changed) — verified by empty `git diff --stat`, unchanged sorted `git status --short` snapshots (diff: identical), `git stash list` = 0 before/after, and unchanged HEAD. |

No CRITICAL or HIGH findings. No divergence was found between the records' acceptance claims and observed reality at HEAD.

---

## WHAT WAS **NOT** VERIFIED (explicit scope statement)

1. **Remote/CI claims** — MASTER-WAVE-1 §1/§6 and CONSOL §1 CI results (GitHub checks API 3/3 green, push/read-back, run ids `41353897849`/`41353897802`) were not re-fetched; no network verification was attempted in this sandbox. Only in-repo artifacts were audited.
2. **The 24 unsampled matrix rows** (rows 2, 4–6, 8–9, 11–15, 17–20, 22–23, 25–31) — per mandate only 8/32 rows were spot-checked; their citations were not exhaustively re-verified. The matrix's external grep transcripts (`/home/z/my-project/consolnext_scratch/T5/`) were not re-derived.
3. **Browser E2E 7/7** (CONSOL §7, out of the §3–§5 mandate) — requires a booted app + playwright; not run.
4. **The implementer's historical in-cycle acts** (e.g. that the reproduction was executed *before* the fix was written) — not retroactively observable; what was verified is that the defect state and the test's load-bearing property reproduce from the committed tree.
5. **Golden Set recompute probe** (mentioned in CONSOL §10 as prior in-cycle QA work) — only indirectly covered via the 34-test P3 suite; no independent recompute was performed in this session (not in the W2-QA mandate list).
6. **Secret-pattern sweep, Windows/Electron packaging checks, backup/restore runbook audit, version-chain checks** (CONSOL §7) — not in the W2-QA mandate; not executed.
7. **Runtime behaviors requiring live market data, LLM transports, or Windows target machines** — structurally out of scope (gates were verified in default posture only).
8. **MA-1 record** and any record prior to CONSOL-NEXT — out of mandate except where cited by the audited records.

---

## APPENDIX — Raw evidence snapshot

- Full battery: `1436 passed, 1 skipped, 2 warnings in 12.27s` / `EXIT=0` (log retained at `/tmp/qa_full_battery.log`).
- Q-1 post-fix file run: `3 passed in 0.64s`; decisive node alone: `1 passed in 0.43s`.
- Q-1 pre-fix (isolated copy, HEAD tree + `HEAD~1` market_service.py): `1 failed, 2 passed in 0.48s` with assertion message "Q-1 FALSE-FRESH REPRODUCED …".
- Focused: 9 / 44 / 34 / 27 / 16 (all passed).
- pyflakes (app/ + 3 new test files): exit 0, empty.
- Gates: config.py:111 `_env_bool("AI2_ENABLED","0")`; config.py:284 `verified = False`; `git grep ai2 backend/app/api/` exit 1; proactive_research.py:102 `kill_switch: KillSwitchState = "ENGAGED"`; g2_gate.py:287 else-branch SYNTHETIC_OR_PAPER; live-trading sweep single hit `backtest.py:483: "live_trading": False,`.
- Purge DELETEs: alert_ops_store.py:536 over tuple {outbox/created_at, inbox/delivered_at, dead_letter/dead_lettered_at, audit/ts}; module-wide DELETE-target pin test green.
- End-state: HEAD `7c225cb1ce2771473f1f646be9c4282348ea7657`, `git diff --stat` empty, status identical to session start, stash 0, single worktree; `/tmp` copy deleted.

*Report generated by W2-QA independent auditor. No tracked file was modified, committed, checked out, or reset; the only authorized mutation (stash round-trip) was attempted and proven a no-op on a clean tree.*
