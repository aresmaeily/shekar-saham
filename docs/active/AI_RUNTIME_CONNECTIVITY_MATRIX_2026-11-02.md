# AI RUNTIME CONNECTIVITY MATRIX — 2026-11-02 (WS-5, MASTER directive)

Evidence baseline: repo `aresmaeily/shekar-saham` branch `main`, commit
`47183c0913518be1297f50c77bca0fdb3dddd9d1` (tree `18c2316cff99d08a9b19b0cb305b19e8f429ce2e`)
plus the WS-5 implementation wave committed on top of it. Authoritative inputs:
`W2_AIF_AI_BLOCKS_AUDIT.md` (10-dimension × 8-block audit at `7c225cb`),
re-verified at this baseline by import-graph greps and the gate sweep below.
This matrix separates, per block: what is CONTRACTED, what is IMPLEMENTED,
what is actually CALLED at runtime, what is CONNECTED to what, what is TESTED,
how FAILURES behave, which SECURITY gates hold, what the OWNER has authorized,
and whether the block is OPERATIONALLY READY. "Contract exists" is explicitly
NOT treated as "operational".

Legend: ✅ present/verified · ⚠️ partial · ❌ absent · 🔒 owner-gated

| Block | Contract | Implementation | Runtime caller | Producer→consumer connectivity | Tests | Failure handling | Security gates | Owner authorization | Operational readiness |
|---|---|---|---|---|---|---|---|---|---|
| AI-1 Central Brain | ✅ COMPLETE (observer/interpreter/regime/opportunity/filter-intelligence/memory interfaces/run governance/monitoring) | ✅ real modules (`ai_intelligence.py`, `monitoring*.py`, `market_intelligence.py`, `market_session.py`, `filter_intelligence.py`) | ✅ WIRED — 7 POST routes call `ai_service` (`routes.py:557-603`), market-intelligence routes `:711-745`, `/ai/provider-status` `:606+` | ✅ stage-1 → UI/WS surfaces; monitoring→alert-ops composition NEW (WS-5: `test_ai1_alertops_composition.py` 10 tests) | ✅ AI-1 82; +10 composition (WS-5) | ✅ per-route error taxonomy; fail-closed trust; composition refusal records with stable reasons | ✅ AI2_ENABLED=0 `config.py:111`, verified=False `:284`, SYNTHETIC_OR_PAPER | ⚠️ block acceptance = owner review of AI1-GC record still PENDING | ⚠️ ROUTES operational (manual invocation); scheduled monitoring runtime owner-gated (R-6 class) |
| AI-2 Research Loop / MVRL | ✅ COMPLETE (8 required items; AI2-A…F chain) | ✅ `ai2_service.py` + `ai2_governance.py` + `services/ai2_research_loop.py` (shadow runner) | ❌ **NOT WIRED — DISCONNECTED EDGE 1/5**: `AI2ResearchLoopRunner`/`ai2_service` imported only by tests; zero `ai2` refs under `app/api/`; no route by design (`ai2_service.py:48-50`) | ⚠️ internal chain complete (service↔governance↔run-governance↔episodic archive); upstream provider = gated stage-1 ctx | ✅ 176 (AI-2+AI-MA shared) + 16 loop-level invalidation/recovery composition (WS-5: `test_ai2_loop_invalidation_composition.py`) | ✅ 3 independent gates; budget/duplicate/refusal ledger; runner errors → `ESCALATE_FAIL_CLOSED`; fail-closed verified (WS-5: recovery determinism + no duplicate-laundering pinned) | 🔒 HOLD ×4 layers (AI2_ENABLED=0, verified=False, SYNTHETIC_OR_PAPER, no api surface) | 🔒 enablement owner act DENIED this release (OA-AI2-ENABLEMENT closed); credentials R-3 | ❌ NOT operational — no runtime caller exists; enablement requires owner act + caller-surface definition |
| AI-MA Multi-Agent Runtime | ✅ COMPLETE (MA-1..6; partial failure-model mapping self-declared → **now closed**: `multi_agent_failure_model.py` 9-kind taxonomy + duplicate detection, header note corrected WS-5) | ✅ `MultiAgentRuntime` (866 L), bounded-parallel wave executor, deterministic synthesis | ❌ **NOT WIRED — DISCONNECTED EDGE 2/5**: `MultiAgentRuntime` imported by nothing in `app/` outside its module; no plan producer/caller | ❌ runtime→plan-producer edge absent (by design; recorded integration backlog) | ✅ 176 shared + 16 failure-model tests; all 9 kinds land on `FAILURE_RUN_CONTAINMENT[kind]` | ✅ containment conjunction; 9-kind taxonomy; per-step timeouts; nothing swallowed | ✅ no P2P, no autonomous spawning; no config surface | 🔒 specialist qualification + caller surface = owner calls | ❌ NOT operational — no plan producer exists |
| AI-3 Research Memory | ✅ COMPLETE (episodic immutable + semantic curated + engine-neutral store Protocol) | ✅ contracts + in-memory reference adapter + TEST-LAYER-ONLY JSONL adapter (AST-pinned zero production wiring) | ❌ **NOT WIRED**: `InMemoryResearchMemoryStore` zero production callers | 🔒 **OWNER-GATED EDGE 1/3**: production persistence adapter starts ONLY after D1–D7 recorded (`AI3_PERSISTENCE_DECISION_PACKET.md` §11); producer (research runs) upstream-blocked by AI-2 | ✅ 66 → **69** collected (scaffold 44→56 with acc25–acc30 WS-5 negative enrichment; +2 unparameterized) | ✅ append-only, fail-closed integrity, no-purge structural; NEW crash-consistency + PIT-invisibility + empty-store semantics pinned (WS-5) | ✅ tests-only adapter; RT-6 AST proof no production import | 🔒 **D1–D7 ALL PENDING** (packet §D1–D7) | ❌ NOT operational — engine adapter BLOCKED on owner decisions; test-layer adapter is NOT production persistence |
| AI-4 Governed Generation | ✅ COMPLETE (5 groups; candidate lifecycle closed at approval) | ✅ `governed_generation.py` + reference evaluators; **NEW WS-5**: `evaluate_software_change_proposal` (structural completeness, 8 mandatory fields; refusal split pinned; 7 tests) — callable but deliberately UNBOUND (existing tests pin 3-binding registry + None gap; binding = recorded follow-up) | ❌ **NOT WIRED — DISCONNECTED EDGE 3/5**: `governed_generation` imported only by reference evaluators + tests | ⚠️ registry→gates edge INTEGRATION-VERIFIED in-process; generation→runtime-consumer edge absent | ✅ 51 + **7** (WS-5 `test_ai4_software_change_evaluator.py`) | ✅ admission/budget/approval gates; malformed candidate → refusal record, never scored | ✅ no self-modification; sandbox class only | 🔒 numeric sandbox budgets = R-5 (proposal only); promotion authority owner | ❌ NOT operational — no runtime consumer |
| AI-5 Proactive Intelligence | ✅ COMPLETE (job spec + ledger + kill switch) | ✅ `proactive_research.py` (kill switch default ENGAGED `:102`) + `proactive_research_ledger.py` (append-only, PIT+digest) | ❌ **NOT WIRED — OWNER-GATED EDGE 2/3**: no scheduler runtime anywhere (lifespan runs market refresh + alert-ops only) | ⚠️ alert-ops scheduler (30-min, D-AI-30 O1-b) IS live and distinct from the proactive-research scheduler | ✅ 189 shared | ✅ ENGAGED-default; refusal records; retry ceilings | ✅ kill switch ENGAGED; no config surface | 🔒 core-stability declaration + cadence/budget + environment = R-6 | ❌ NOT operational — scheduler requires owner act |
| AI-6 Ingestion & Boundary | ✅ COMPLETE (boundary + injection + ledger + dossier) | ✅ contracts + reference scanner | ❌ **NOT WIRED**: no crawler/network; **DISCONNECTED EDGE 4/5** (scan verdicts → `DocumentLedger` registration: no production wiring) + **OWNER-GATED EDGE 3/3** (retrieval/scanning runtime) | ❌ scan→ledger registration absent; intake = caller-provided content only | ✅ 189 shared | ✅ quarantine containment; fail-closed intake | ✅ D-AI-29 gate-deferred; no egress | 🔒 source classes + Two-Key params + credentials = R-7 | ❌ NOT operational — ingestion blocked on owner act |
| AI-7 Calibration & Audit | ✅ COMPLETE (calibration + audit vocabulary) | ✅ contracts + metric builders | ❌ **NOT WIRED — DISCONNECTED EDGE 5/5**: `calibration_metrics`/`calibration` imported only by tests | ❌ `CalibrationRecord`/`DriftAssessment` → runtime consumers absent | ✅ 189 shared | ✅ maturity/label-leakage guard | ✅ D-AI-31 evidence-gated | 🔒 autonomy-expansion thresholds = R-8 (evidence cannot exist until upstream loops run) | ❌ NOT operational — loop evidence-gated |
| (D-AI-30 alert-ops, for contrast) | ✅ | ✅ outbox + dispatcher + dead-letter | ✅ WIRED — router `main.py:28,288`, lifespan `:121-132`, 7 `alert_ops_*` tables | ✅ producer→`IN_PRODUCT_INBOX` (type-closed channel) | ✅ 135 focused | ✅ kill-switch→budget→expiry ordering; purge boundary = exactly 4 `alert_ops_*` DELETEs | ✅ kill switches seeded ENGAGED; API-key-gated RELEASE | ✅ GOV-41 A2 approved (restricted scope) | ✅ operational WITHIN approved restricted scope |

## Edge re-verification at this baseline (directive: "specifically investigate the reported disconnected and owner-gated edges")

Method: import-graph greps over `backend/app/` + `backend/tests/` (excluding
`__pycache__`), plus the gate sweep. Re-run output recorded in the wave
evidence file. Results — **all 8 edges UNCHANGED from the W2-AIF map**:

- DISCONNECTED (5): AI-2 loop→runtime caller/route; AI-MA runtime→plan
  producer; AI-4 governed generation→runtime consumer; AI-6 scan→
  DocumentLedger registration; AI-7 calibration/drift records→runtime
  consumers.
- OWNER-GATED (3): AI-5 scheduler runtime; AI-6 retrieval/scanning runtime;
  AI-3 production persistence adapter (D1–D7).
- Runtime-wired today: AI-1 stage-1 routes + market-intelligence + the
  D-AI-30 alert-ops block. Nothing else has a runtime caller.

## WS-5 implementation wave — what was implemented (all authorized-repo-side, additive)

1. **AI-2 loop-level invalidation/recovery composition tests** (16 collected,
   new file) — pins: ledger-record labels feed `invalidates()`; trust
   downgrade/dataset supersession mint append-only `INVALIDATED` successors;
   recovery determinism for runner errors/gated refusals/budget exhaustion;
   invalidated results cannot be laundered into acceptance via duplicate reuse.
2. **AI-3 acceptance-kit enrichment** (scaffold 44→56 collected; acc25–acc30
   over both factories) — duplicate-identity conflicts leave all views
   unchanged; PIT-invisible source refuses promotion with stable reason;
   order-honesty of digests vs sequences; semantic-mutation all-or-nothing;
   timestamp discipline (far-future accepted but PIT-invisible; no expiry);
   empty-store integrity explicitness. Any future production adapter must
   pass all of it via one `STORE_FACTORIES` entry.
3. **AI-1↔alert-ops composition tests** (10 collected, new file) — released
   monitoring cycle's staleness trigger delivered exactly once to
   IN_PRODUCT_INBOX; ENGAGED kill switch refuses on both sides with recorded
   reasons; dedup via canonical fingerprint; budget/retry/dead-letter parity;
   composition adds no tables and no egress (AST import-level scan).
4. **P6 internal lifecycle tests** (14 collected, new file) — closed 4-kind
   vocabulary + kind↔role bindings; M&A own-evidence rule; UNCLASSIFIED
   honesty; why-now/invalidation mandatory fields; expiry terminality;
   cluster discipline; no fabricated historical evaluations.
5. **AI-4 evaluator extension** — `evaluate_software_change_proposal`
   (structural completeness of the 8 mandatory fields; wrong-kind raises;
   `proposal=None` via bypass constructor → honest refusal record; whitespace
   defense-in-depth; frozen deterministic records) + 7 tests. Registry stays
   byte-stable (existing pins honored); binding recorded as follow-up.
6. **AI-MA stale-header currency correction** — `multi_agent.py` docstring
   no longer claims the taxonomy/duplicate-detection gap is open; it now
   cites the existing `multi_agent_failure_model.py` sibling (the gap was
   closed by commit 771c525; the docstring predate it) with the historical
   wording preserved in that module's header quote.

## What was NOT done and why (explicit, not silent)

- **No runtime caller was added for any of the 5 disconnected edges** —
  wiring decisions are product/feature owner calls (W2-AIF owner-gated
  list item 7; CONSOL-NEXT §6/§11 integration backlog). Adding a route or
  scheduler would flip an owner-gated boundary.
- **AI-3 production adapter NOT implemented** — D1–D7 all pending
  (owner-only). The test-layer JSONL adapter remains test-layer-only.
- **AI-4 registry binding NOT added** — existing tests pin the 3-binding
  registry and the None gap; amending them would violate the no-test-
  modification control. Recorded as follow-up requiring a deliberate
  test amendment.
- **No gate flip, no AI2 enablement, no scheduler, no external channel,
  no purge path** — all remain exactly as audited.

## Battery arithmetic

1535 passed / 1 skipped / 2 warnings = 1471 (pre-wave) + 64 exact:
16 (AI-2 composition) + 12 (AI-3 scaffold 44→56) + 10 (AI-1/alert-ops)
+ 14 (P6 lifecycle) + 7 (AI-4 evaluator) + 5 (Windows workflow gates).
