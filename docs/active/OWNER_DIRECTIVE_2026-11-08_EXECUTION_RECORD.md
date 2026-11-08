# OWNER-DIRECTIVE-2026-11-08 — EXECUTION RECORD

Directive: **دستور رسمی مالک پروژه RADAR_BOURSE — «تکمیل تمام کارهای
باقی‌مانده، فعال‌سازی قابلیت‌های مجاز و آماده‌سازی انتشار نهایی»**
(2026-11-08), executed continuously on top of the WAVE-AI-ACCEPTANCE stage.
Every claim carries an exact evidence pointer; nothing is inferred across
commits; nothing is converted.

---

## §1 — Startup audit (directive §2)

| Item | Value |
|---|---|
| Owner-declared baseline | `209ec620d718c8bcae06928b9a86ba438d370c76` |
| Local HEAD before recovery | `3b6f15d` (stale; 46 commits behind) |
| Recovery | ff-only merge `3b6f15d..209ec620` after byte-comparison: ALL colliding untracked governance/evidence files **byte-identical** to their origin/main blobs; `CLAUDE.md`, `scripts/r13_owner_repo_setup.sh`, `scripts/validate_bootstrap_config.py`, `.claude/` are NOT tracked upstream and were preserved untouched in place (byte backup also taken out-of-tree: `/home/z/my-project/owner_untracked_backup_209ec62/`) |
| Ancestry | `209ec62` ✓, `2b038a1` ✓, `373623f` ✓, `b773aee2` ✓ — all ANCESTOR (merge-base verified) |
| Gate postures verified in code | `AI2_ENABLED=0` (app/core/config.py:118), `SCHEDULER_ENABLED=0` (:158), `verified=False` mint-block (:329), `is_verified_live` never mintable (:201-211) |
| Full battery at baseline | 3193 passed / 1 skipped / 0 failed (51.97s) — exact reproduction of the recorded WAVE-AI totals |
| Records read | `WAVE_AI_ACCEPTANCE_EXECUTION_RECORD_2026-11-08.md` (complete), `WAVE_AI_NEXT_STAGE_DIRECTIVE_EN_2026-11-08.md`, `OWNER_DECISIONS_RECORDED_2026-11-02.md` (D1–D7 + R-1..R-11), STATUS.md, AI-2/AI-3 persistence decision packets |

## §2 — Exact-SHA CI at the baseline

**ALL 4 REQUIRED CHECKS SUCCESS at `209ec620`** (GitHub API, token-authenticated,
exact-SHA check-runs — never inferred from badges or parent commits):

| Required check | Run | Job | Conclusion | Started (UTC) |
|---|---|---|---|---|
| test-backend | 42418554511 | 128541825841 | SUCCESS | 2026-11-07T22:00:49Z |
| build-docker | 42418554511 | 128542070354 | SUCCESS | 2026-11-07T22:01:46Z |
| windows-validation | 42418554504 | 128541825721 | SUCCESS | 2026-11-07T22:00:49Z |
| build-installer | 42418554470 | 128541825630 | SUCCESS | 2026-11-07T22:00:49Z |

## §3 — Implementation increment (commit `ad5d978`)

One coherent unit closing the non-owner-gated gaps of the standing next-stage
directive + the 2026-11-08 owner directive §3/§4:

1. **AI-3 REAL integration (owner act §3: «اتصال واقعی و تست runtime
   الزامی است»)** — the D1–D7 recorded decisions' durable carrier is now on
   the real application path:
   - NEW `app/data/memory_access_audit_sqlite.py`: durable SQLite/WAL
     append-only carrier for the tamper-evident access/operation audit chain
     (pinned-digest migrations, per-row SHA-256, full-chain re-verification at
     open with fail-closed CLOSED-GATE posture, verified backup, restore
     refuses unverified sources, restart recovery, no wall clock, no
     delete/update — AST-pinned);
   - NEW `app/services/research_memory_service.py`: factory with DEFAULT
     DURABLE sqlite backend (D1 adapter + AES-256-GCM + D4 key source:
     env override → OS keyring; keyless = fail-closed typed REFUSAL posture,
     never an unencrypted or silent in-memory downgrade) wrapping the store in
     `AuditedResearchMemoryStore` whose trail IS the durable chain;
   - NEW `/api/v10/memory` router (posture / episodic / lessons / integrity /
     audit / backup): every operation audited OK or REFUSED-with-reason,
     caller-supplied instants only, typed 422s, D3 no-purge surface;
   - additive config fields (`RESEARCH_MEMORY_BACKEND`, `RESEARCH_MEMORY_DB_DIR`)
     with D1..D7 provenance comments; conftest autouse isolation fixture with
     settings-cache hygiene.
2. **AI-MA UI iteration (owner §4)** — runtime threads bounded per-step
   artifact CONTENT (executor → `SpecialistOutcome.content` → cross-chunk
   accumulation → `RuntimeRunResult.artifact_contents` → API
   `artifact_contents`); UI per-step artifact content viewers (verbatim
   server payloads, esc'd); session run-history panel (client-session only,
   bounded 8, no localStorage/sessionStorage, no server persistence);
   command-palette keyboard integration (`[data-palette-label]` hook).
3. **Product-loop consolidation (next-stage item 5)** — product loops tab
   gains: §6 durable research-memory posture/integrity/audit-rows/backup
   (read-only, action-only, no purge surface, write paths deliberately NOT
   exposed client-side) + §7 Golden Set v2 versioned read-only report via NEW
   `GET /api/v10/productloops/goldenset/v2/report` (corpora shipped as module
   resources `backend/app/data/golden_set/`, digests pinned fail-closed ==
   the suite pins; v2 cases run against the REAL deterministic engines;
   baseline v1 and candidate v2 reported SEPARATELY; FP/FN totals;
   structural `superiority_claimed=False`; deterministic double-run equality;
   route-surface counter-pin 12→13 recorded).
4. **AI-MA provider seam — OWNER-GATED prep only** —
   `SYNTHETIC_PROVIDER_TRANSPORT` contract tests prove same-protocol
   compatibility through the REAL runtime, fail-closed ToolNotPermitted
   allowlist, invocation ceilings, deadline-jump straggler discard (TIMEOUT),
   honest SYNTHETIC_OR_PAPER labeling; NEW
   `docs/active/AIMA_PROVIDER_ACTIVATION_DECISION_PACKET.md` (P-1..P-10 owner
   decisions, Two-Key coupling). NO provider activated.

Tests: +38 exact (9 audit-adapter + 11 runtime + 4 contents + 6 UI-static +
2 gs2-endpoint + 6 provider-seam) = **3231 passed / 1 skipped / 0 failed**
(54.8s) = 3193 baseline + 38 exact. pyflakes clean (runtime modules); node
--check green; workflow YAML 3/3 valid; secret scan of the diff clean; sw
v3-0-18→v3-0-19 ×9 files recorded.

## §4 — Browser-level acceptance (REAL browser, screenshots)

Environment: sandbox Chromium (agent-browser 0.41.1, headless, 1440×900),
real uvicorn `127.0.0.1:8000` behind the same-origin preview transport
(`127.0.0.1:3000`), `DATA_SOURCE=mock` (trust `synthetic`), durable research
memory enabled via the D4 env key; exact tested commits `ad5d978`+`b17e108`.
Evidence: `download/owner_directive_browser_evidence/` (7 screenshots).

| Journey | Result |
|---|---|
| Home (32 tabs) | renders; **0 console messages, 0 page errors** across the whole session |
| Product loops → §6 memory posture | backend=sqlite, durable=true, AES-GCM=true, audit-trail durable=true, trust from server (screenshot 03) |
| Product loops → §6 integrity | verify_ok=true, chain verdict **INTACT**, head digest shown |
| Product loops → §6 backup (D5) | verified backup parts for BOTH carriers (memory store + audit trail) written to `data/backups/research-memory/` |
| Product loops → §7 Golden Set v2 | GS2-2026-11-08: 8/8 passed, FP 0, FN 0, no-superiority banner rendered |
| AI-MA orchestrate (real UI→API) | 2 waves bounded-parallel; 3/3 per-step artifact content viewers; trust SYNTHETIC_OR_PAPER (screenshot 04) |
| AI-MA run history | **DEFECT FOUND + FIXED** (`b17e108`): the panel did not refresh after a run; after the fix: run#1 → 1 row, run#2 → 2 rows, manual refresh → 2 rows |
| Command palette (Ctrl+K) | opens; 8 new `data-palette-label` actions registered (AI-MA ×3, memory ×4, GS2 ×1) |
| AI-MA empty question | typed 422 rendered verbatim («String should have at least 3 characters») |
| XSS probe | `<img src=x onerror=…>` submitted as question: **never executed** (`pwned=false`; esc discipline holds) |
| Walk-Forward full journey | valid RSL-1 source + seed + grid space → run → 16 fold/aggregate rows + reproducibility digest → JSON/CSV/PDF exports all 3 fired (verified in resource timing) (screenshot 05); the earlier refusal path («منبع DSL خالی است») is the honest client-side validation working |
| Excellent tab | activates with real content (21 panels/elements) (screenshot 06) |
| Dashboard | renders (screenshot 07) |

Honest incident recorded: modules are served under `/static/js/...` with
`Cache-Control: max-age=3600` (the known stale-module class from WAVE-AI);
the fix verification required priming the correct paths with
`cache:'reload'` — same transport behavior as the recorded precedent, no code
change (SW v3-0-19 bump covers future loads).

## §5 — Publication + CI truth chain (nothing converted)

| SHA | Pushed | CI result at that exact SHA |
|---|---|---|
| `ad5d978` (implementation) | with `b17e108` | — (parent; not separately CI-verified; superseded below) |
| `b17e108` (browser fix) | `209ec62..b17e108` | **test-backend FAILURE** (job 128652069268 — pyflakes `GoldenSetIntegrityError imported but unused` in golden_set_service.py:37; the local pyflakes sweep had covered touched runtime modules but missed this file — process gap recorded); build-docker SKIPPED (needs-gated dependency of the lint step, not an independent fault); windows-validation SUCCESS (128652070210); build-installer SUCCESS (128652069368) |
| `0b6190f` (lint fix) | `b17e108..0b6190f` | **test-backend FAILURE** (job 128653357978 — `test_service_module_has_no_delete_or_purge_path` asserted on raw `app.routes` introspection which is VERSION-FRAGILE: starlette 1.3.1 wraps included routers in composite objects without `.path`); build-docker SKIPPED (dependency); windows-validation SUCCESS (128653357821); build-installer SUCCESS (128653357995) |
| `1aa0eea` (introspection fix) | `0b6190f..1aa0eea` | **ALL 4 REQUIRED CHECKS SUCCESS** — test-backend 42456154101/job 128655496776 (06:47:16Z) · build-docker 42456154101/job 128655781272 (06:48:44Z) · windows-validation 42456154165/job 128655496750 (06:47:15Z) · build-installer 42456154126/job 128655496804 (06:47:16Z) |

Both failures remain ON RECORD, root-caused, fixed by forward-only commits;
nothing was converted, nothing skipped, no assertion weakened. The fix for
`0b6190f` was verified under the EXACT CI dependency matrix (clean venv from
requirements.txt: fastapi 0.141.1 / starlette 1.3.1 / pydantic 2.13.4 /
pytest 9.2.0) — FULL battery there: **3231 passed / 1 skipped / 0 failed
(47.75s)**, identical to the local matrix (3231/1s/0f at fastapi 0.128.0).

## §6 — Installer artifact (exact source SHA `1aa0eea`)

Built in the authorized CI environment from the exact pushed SHA (public
build log, run 42456154126):

| Field | Value |
|---|---|
| artifact_name | `رادار بورس Setup 3.0.0.exe` |
| artifact_size_bytes | 114,603,344 |
| artifact_sha256 | `9D32124B93A11D890B42FC6DDDB6BEF953E893BBD6A4A390F1FDF030070A04D6` |
| label | `INSTALLER_ARTIFACT_READY_UNSIGNED_TARGET_INSTALL_PENDING` |
| signing | UNSIGNED_NO_CERTIFICATE (CSC discovery disabled; `--claim-signed` refused by the readiness validator, exit 2 semantics preserved) |
| runtime smoke | python_runtime_import_smoke=PASS (fastapi uvicorn pydantic numpy orjson httpx tzdata); frontend_files_bundled=66 |
| install/upgrade/rollback/uninstall | **NOT EXECUTED** — target-machine acts are owner R-1/R-2 (no Windows machine in this environment; never claimed) |

Windows packaging readiness validator: **all_ok=True (47/47 checks)**;
`--claim-signed` correctly REFUSED.

## §7 — Security review (directive §6)

| Check | Result |
|---|---|
| Dependency vulnerabilities | `pip-audit -r requirements.txt`: **No known vulnerabilities found** |
| Secrets scan (repo-wide, tracked files) | clean — the only pattern hits are the audit-trail test's DOCUMENTED fake credential markers (intentional refusal-path fixtures, same precedent as WAVE-AI) |
| Credentials in code/git/logs | none; FERNET_KEY via env only; RADAR_RESEARCH_MEMORY_KEY via env/keyring only (D4 fail-closed) |
| Sensitive-value logging | none — notifier logs key NAMES only, never values |
| Auth/CORS/CSRF | posture unchanged from the shipped audited state (CORS default localhost-only; CSRF Origin-vs-Host middleware verified in prior waves and unchanged; AUTH_REQUIRED default 0 with X-API-Key path) |
| XSS (REAL browser probe) | `<img onerror>` injection through the AI-MA question field: NOT executed; all rendering esc()'d |
| SQL injection | all persistence goes through parameterized SQL with pinned DDL; no dynamic table/identifier from user input |
| File access | memory surfaces expose NO delete/purge path (D3); backup writes only into the designated backups directory |
| Digital signing | honestly NOT CLAIMED (no certificate; claim-signed refused) |
| Backup/recovery | D5 verified backup live-verified through the real UI; audit-trail backup verified; restore refuses unverified sources (tests) |

## §8 — Branch protection / ruleset (directive §8) — OWNER ITEM

- The provided token authenticates as `aresmaeily` with repo `admin:true`,
  BUT the fine-grained PAT lacks the **Administration** repo permission:
  `GET /branches/main/protection` → 403 "Resource not accessible by personal
  access token"; `GET /rulesets` → 200 with EMPTY list (no rulesets exist).
- Therefore branch protection could NOT be read or set from here — recorded
  as an OWNER action, exactly:
  1. GitHub → Settings → Branches → Add branch ruleset for `main`;
  2. Require a pull request before merging (or keep direct-push policy per
     owner preference — the repo's standing R-10 grant authorizes
     forward-only pushes; the ruleset MUST still block force-push);
  3. Require status checks to pass: `test-backend`, `build-docker`,
     `windows-validation`, `build-installer`;
  4. Block force pushes and deletions.
- History protection observed in practice: all pushes this stage were
  forward-only (fast-forward `209ec62..b17e108..0b6190f..1aa0eea`); no
  force-push/reset/rebase anywhere.

## §9 — Gate / activation decisions taken (and NOT taken)

| Gate | Decision this stage | Basis |
|---|---|---|
| AI-3 durable integration | **WIRED into the real app cycle** (durable default, audited, runtime-tested) | owner directive 2026-11-08 §3 is the explicit dated act ordering real integration; D1–D7 recorded 2026-11-02 define the implementation |
| AI-2 (`AI2_ENABLED`) | **UNCHANGED = 0** | R-3 KEEP-DENIED stands (no credentials exist; live provider = next-version governed item); the directive itself forbids flipping it merely to green tests |
| Scheduler (`SCHEDULER_ENABLED`) | **UNCHANGED = 0** | R-6: scheduled operation requires a separate dated owner act ON the owner machine; the directive's permission is conditional and OA-4 standing; staging activation without production default change is the safe reading — recorded as owner-ready |
| R-3/R-7 live providers | **KEEP-DENIED** | no credentials delivered; Two-Key unassigned |
| R-1/R-2 installer install | **NOT ISSUED** | no Windows target machine here; CI artifact built + provenance recorded instead |
| AI-MA provider activation | **OWNER-GATED** (packet P-1..P-10 delivered) | directive §4: synthetic executor must never be presented as real LLM execution |
| OA-6 Vercel | optional, non-gating; preview re-established locally instead | unchanged |
| OA-8 | global completion **NOT CALCULATED** | no approved weighting model |

## §10 — Honest status matrix (this stage's scope)

| Capability | Status | Evidence |
|---|---|---|
| AI-1 (six-label interpretation, fallback paths) | PRESERVED (zero engine deltas) + GS2 v2 cases re-verified against real engines | §3; battery |
| AI-2 (research loop, candidate/run registry, deep-eval, refusal paths) | TESTED (gates 0; persistence kit dormant) + prior batteries untouched | config.py:118; standing suites |
| AI-2 persistence activation | OWNER-GATED (D-A2-1..7 packet standing) | §9 |
| AI-3 research memory | **INTEGRATION-VERIFIED** (durable SQLite/WAL + AES-GCM on the real path; restart recovery, tamper fail-closed, verified backup — runtime-tested through the real HTTP surface AND browser) | §3/§4 |
| AI-3 audit trail | **INTEGRATION-VERIFIED** (durable hash-chained ledger; every op audited; browser-verified) | §3/§4 |
| AI-4 Strategy Lab / DSL | PRESERVED (walk-forward journey browser-verified end-to-end) | §4 |
| AI-5 scheduler | TESTED standing (gate 0; owner-ready; nothing scheduled) | §9 |
| AI-6 sources | PRESERVED (kill switches ENGAGED; DECLARED-SOURCES-2) | standing suites |
| AI-7 Golden Set v2 | **INTEGRATION-VERIFIED** (versioned read-only endpoint, deterministic, no-superiority) | §3/§4 |
| Multi-Agent | **INTEGRATION-VERIFIED + RUNTIME-VERIFIED (browser)** incl. content viewers, history, palette; real-LLM seam = OWNER-GATED prep complete | §3/§4 |
| CI | **OPERATIONALLY-VERIFIED at `1aa0eea`** (ALL 4 SUCCESS, exact-SHA) | §5 |
| Website (dev environment) | **RUNTIME-VERIFIED** (browser journeys, screenshots, 0 console errors) | §4 |
| Desktop installer | Artifact BUILT + provenance recorded; **install/upgrade/rollback OWNER-GATED (R-1/R-2)** | §6 |
| Global completion % | **NOT CALCULATED** (OA-8) | §9 |

## §11 — Residual register (honest, explicitly not claimed)

1. Installer install/upgrade/rollback/uninstall/reinstall on the owner's
   Windows machine — R-1/R-2 (artifact ready, provenance recorded).
2. AI-2 persistence activation (D-A2-1..7 + separate decision) — owner.
3. AI-MA real LLM provider activation — owner packet P-1..P-10 (P packet
   delivered; nothing activated).
4. Scheduler production enablement — R-6/OA-4 dated owner act (staging-safe
   env-override path documented; default stays 0).
5. Branch protection ruleset — owner (PAT lacks Administration scope; exact
   steps in §8).
6. Live external sources — R-3/R-7 (KEEP-DENIED; no credentials).
7. Recurring AI-7 audits — OA-4 (infrastructure exists, nothing scheduled).
8. Golden Set comparative study vs TabloKhani — requires owner-approved
   benchmark protocol; no superiority claim made.
9. Vercel staging (OA-6) — optional; local same-origin preview was used for
   runtime verification.

## §12 — Invariants verified unchanged

`AI2_ENABLED=0` (config.py:118 byte-pinned by test) · `SCHEDULER_ENABLED=0`
(:158) · `verified=False` mint-block (:329) · SYNTHETIC_OR_PAPER labels
everywhere · no broker/live trading · no autonomous promotion · no production
mutation · no external notification egress · no credential exposure · Two-Key
Rule intact · kill switches effective · no test bypass · no weakened
assertions · no deletion of historical failures (both CI failures recorded
and fixed forward) · forward-only history (ff-only recovery; no
force-push/reset/rebase) · counter-pin bumps recorded only (sw
v3-0-18→v3-0-19 ×9; route-surface 12→13) · zero product-engine deltas.
