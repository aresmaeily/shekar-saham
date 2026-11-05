# MASTER-RADAR WAVE-L EXECUTION RECORD — AI-2 CONTROLLED ACTIVATION (OA-3) — 2026-11-05

Directive: OWNER AUTHORIZATION & CONTINUOUS EXECUTION DIRECTIVE (2026-11-05,
OA-1..OA-8). This record covers **WAVE-L**: the controlled activation of the
WAVE-K governed generation seam in an ISOLATED dev/paper runtime, executed
strictly per the directive's activation checklist. Baseline: `504f19b`
(origin/main == local, 0/0; battery 2903/1s/0f after the L-QA remediation).

## 0. Activation checklist (directive §5 for WAVE-L) — item by item

| # | Item | Evidence |
|---|---|---|
| 1 | Corpus reconciliation | WAVE-I requirement-to-code matrix + WAVE-K record §1 (AI2_GENERATION composes the corpus contracts; no parallel AI path) |
| 2 | No unresolved crit/high | L-QA audit (§1 below): D-1 MEDIUM + D-2 LOW **both FIXED in-wave and pinned** (commit 504f19b); zero open findings |
| 3 | All tests pass | battery **2904 passed / 1 skipped / 0 failed** (2903 + 1 cross-surface pin exact); pyflakes clean |
| 4 | Independent QA pass | L-QA read-only audit at 46274a3: battery ×2 reproduced, 31 hostile probes zero 500s, gate sweep clean, counter-pin verified biting, provenance hashes independently re-derived; verdict PASS after remediation |
| 5 | Runtime caller verified | `/api/v10/ai2/*` registered in `create_app` (main.py, additive); posture/generate/candidates/approve/promote/runs all exercised over the REAL app stack in the activation session |
| 6 | Generated output goes through the governed DSL path | emitter → `compile_source` (existing parser/typechecker/validator/sandbox); NO other path exists (structural) |
| 7 | Synthetic/paper trust visible in UI/reports | honesty envelope on every `/api/v10/ai2` payload (data_trust_label SYNTHETIC_OR_PAPER, model-authority, in-memory registry, no-egress disclosures); `execution_mode=SYNTHETIC_OR_PAPER` + `test_only_transport=true` in every provenance; Strategy Lab display verified (step 07/08/09 of the session) |
| 8 | LIVE gate closed | G2 untouched (`g2_gate.py`/`G2_GATE_STATE.json` diff 0 bytes vs 3b6f15d); `verified=False` mint-block untouched; harness verdict NOT_PASSED |
| 9 | Broker/external egress unreachable | module constructs no network client (source-scan test); remote provider refuses without TEST transport (`real_provider_generation_not_permitted`, demonstrated in session step 11); no notifier/ws_hub/broker/scheduler import |
| 10 | Human approval mandatory | both transitions require a NAMED approver (server-enforced); model has zero authority; approved/promoted events append NEW ledger records |
| 11 | Budget & kill-switch tested | timeout/rate/concurrency/output-cap/duplicate/idempotency tests green (K3) + session step 10: disabling blocks IMMEDIATELY in the activated runtime |

## 1. Independent QA (gate for activation) — summary

Full report summarized in the WAVE-K record §7. Key facts: battery
reproduced twice (2897/1s/0f both, order probes green both directions); 31
hostile probe scenarios with ZERO 500s (fenced JSON, NUL in names,
input-without-default, digest determinism across fresh services, backward
clock, approval conflicts, 1 MB question via API, XSS path probes, 9+
clarifications, wrong types, path traversal); counter-pin proven to bite
(ungated/foreign/missing seam detected; G2 verdict stays NOT_PASSED);
provenance hashes re-derived independently (all four match). Findings D-1
(concurrent duplicate TOCTOU, MEDIUM) and D-2 (unadvertised-enforced period
bound, LOW) FIXED in-wave with 6 regression pins; K4 loose assertion
tightened; status tautology made structurally meaningful.

**L-session finding (fixed before enable):** the generation path initially
labeled its engine run `ai2gen-…`, which made a candidate's
`backtest_digest` differ from the Strategy Lab's byte-identical rerun
(`run_id` is part of the engine's digest payload). FIXED: the generation
path now uses the lab's own run convention, so **a candidate's
`backtest_digest` is BYTE-REPRODUCIBLE** by any human in the Strategy Lab —
pinned by `TestCrossSurfaceReproducibility` (digest + headline metrics equal
across surfaces). The AI-2 origin lives in the candidate/ledger records, not
in the engine run label.

## 2. The activation session (checklist items 12–17)

Isolation model (honest scope):
- **AI2_ENABLED=1 was set ONLY in the isolated dev/paper session process**
  (env set before app import). The COMMITTED DEFAULT stays 0
  (config.py:111 byte-unchanged) — no repo gate moved. The session process
  is ephemeral and local; nothing was deployed.
- **The provider is the SANCTIONED TEST-ONLY deterministic transport** (the
  repository's own `executed_shadow` mechanism, identical to
  `tests/test_ai2_service.py` and the K4 API tests): the module-level
  service singleton is replaced in the session process with a subclass that
  injects the TEST transport. NO remote LLM was contacted (the session's
  provider env resolves to a configured remote provider precisely so step 11
  can prove the refusal path). Every artifact carries
  `test_only_transport=true` and the TEST-ONLY warning.

Session steps (ALL PASSED — evidence:
`download/WAVE_L_ACTIVATION_SESSION_EVIDENCE.json`):

1. `01_posture_activated` — REAL app stack (`create_app`: middleware + CSRF
   + routers): `ai2_enabled=true`, `execution_mode=SYNTHETIC_OR_PAPER`,
   `production_provider_generation_permitted=false`.
2. `02_generate_end_to_end` — real end-to-end synthetic session through the
   HTTP API: `executed_shadow`, candidate `gen-0001-…`, complete provenance
   (prompt/model-output/source SHA-256, config fingerprint, evaluation
   version, parent/hypothesis ids absent-by-default, timestamps) — recorded
   in the evidence JSON.
3. `03_candidate_visible_with_honesty` — candidate payload with the honesty
   envelope (SYNTHETIC_OR_PAPER label; DRAFT status).
4. `04_human_approval` — named approver `owner-dev-session` → APPROVED.
5. `05_human_promotion_paper_forward` — → PROMOTED with the PAPER-FORWARD
   scope disclosure.
6. `06_ledger_append_only_trail` — 3 ledger records (PENDING → APPROVED →
   APPROVED), all status LEDGERED (never COMPLETED).
7. `07_strategylab_version_registered` — the generated source registered
   through the EXISTING human Strategy-Lab flow; `source_digest` matches the
   candidate's provenance hash exactly.
8. `08_strategylab_backtest_display` — Strategy Lab backtest of the
   generated source: `result_digest` **byte-identical** to the candidate's
   `backtest_digest`; `data_trust_label=SYNTHETIC_OR_PAPER`; metrics equal.
9. `09_research_report_provenance_visible` — the research-report surface
   (candidate payload + ledger) shows full provenance and PROMOTED status.
10. `10_disable_blocks_immediately` — kill-switch semantics: flipping
    AI2_ENABLED to 0 (same process, settings cache reset) makes the very
    next generate return `gated_not_executed`/`ai2_disabled`; registry
    unchanged.
11. `11_remote_provider_generation_refused` — with a remote provider
    configured and NO test transport, generation is refused outright
    (`real_provider_generation_not_permitted`): the activated runtime cannot
    reach any live/production AI path through generation.

Session verdict: **ALL_CHECKS_PASSED**. No failure occurred; per the
directive the activation stands (in the isolated dev/paper runtime only).

## 3. Activation state (honest)

- **ENABLED nowhere in the repo**: committed default `AI2_ENABLED=0`
  (config.py:111, byte-unchanged); no env file, no workflow, no Dockerfile
  sets it to 1. The activation exists ONLY as the recorded isolated
  dev/paper session (this record + the evidence JSON).
- The LIVE gate remains CLOSED (G2 NOT_PASSED, `verified=False` mint-block,
  `SYNTHETIC_OR_PAPER` execution mode everywhere). AI-2 generation cannot
  create broker orders, external notifications, or production mutations
  (structural: no such surface is imported or reachable).
- `verified=False` posture unchanged; Two-Key intact; R-1..R-11 in force;
  INSTALL NOT ISSUED; global completion NOT CALCULATED (OA-8).
- To reproduce the session: `backend/.venv/bin/python
  scripts/...wave_l_activation_session.py` (session runner kept OUTSIDE the
  repo, in the operator workspace; the repo itself carries the pinned
  equivalents: the K3/K4 batteries + `TestCrossSurfaceReproducibility`).

## 4. Tests delta

+1 (`TestCrossSurfaceReproducibility.test_candidate_digest_reproduces_in_strategy_lab`)
= **battery 2904 passed / 1 skipped / 0 failed = 2903 + 1 exact** (36.32s).
pyflakes clean. Gates byte-unchanged.

## 5. Next waves

WAVE-M (internal scheduler — persistence acceptance landed in WAVE-J),
WAVE-N remainder (supervised local backend in the Electron shell), WAVE-O
(UX integration of the AI-2 surface), WAVE-P (independent acceptance +
release).
