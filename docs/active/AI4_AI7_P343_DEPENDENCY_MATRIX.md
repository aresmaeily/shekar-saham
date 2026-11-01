# DEPENDENCY MATRIX — AI-4 → AI-7 + P3.43 — 2026-10-18

Status: preparation evidence from the official roadmap dependency graph
(`02:5-8`: P0-C → P0-V → P1 → P2 → P3 → G2 → P4/P5/P6 → AI-1 → AI-2 → AI-MA →
AI-3 → AI-4 → AI-5 → AI-6 → AI-7). Chain status: AI-1..AI-3 DELIVERED at the
pre-G2 contract class (`PROJECT_EXECUTION_STATE.md:108`); G2 = owner gate,
NOT_PASSED. Pre-G2 authorized work class: "bounded design, schema work,
source-registry design, synthetic/paper tests and safe dry-run work"
(`02:202`). P3.60 "no unauthorized feature" gate remains binding.

> **Currency note — 2026-11-02 (additive; original text preserved verbatim).**
> Two header statements are superseded by later owner actions and are kept
> above only as the 2026-10-18 record: (1) G2 is formally PASSED
> (owner-recorded 2026-10-29T19:58:32Z, CONSOL-GOV-37; convened review commit
> `9e7c6a21b8b61e2ccb4dc5f1d2249e6af8773242`; state
> `docs/active/G2_GATE_STATE.json`) — with `AI2_ENABLED=0`, `verified=False`,
> `execution_mode=SYNTHETIC_OR_PAPER` unchanged and real-provider
> credentials/enablement DENIED for the current release (GOV-41 Phase 2).
> (2) GitHub publication is no longer pending: main was published via the
> authorized deploy-key path (GOV-48, 2026-11-01) and the post-publication CI
> remediation completed with all three required jobs green on
> `7c72f3d59d47435b53d83dad40a759d69377bca8` (GOV-49). The P3.43 Controlled
> Alpha Launch gates that remain owner-side are unchanged in kind: Windows
> target validation, browser E2E, Electron runtime, live-provider
> verification, and an explicit owner `INSTALL` instruction.

## AI-4 — Governed Generation (`02:87-90`, `02:158-159`, D-AI-11)

- **Exact official scope:** "AI-generated filters/indicators/strategy
  specifications only through sandbox → deterministic evaluation → lifecycle →
  approval." Hypotheses may enter the governed research lifecycle "when a
  suitable deterministic evaluator exists"; generated artifacts "remain
  candidates until isolated tests, evaluation gates and required human approval
  are passed. No self-modifying production logic."
- **Dependencies / upstream blockers:** AI-3 contract layer (DELIVERED);
  AI-1/AI-2 contract infra (DELIVERED); real-data evaluation requires G2
  (BLOCKED); sandbox runtime does not exist (to be built post-G2 for
  execution, contracts may proceed now per `02:202`).
- **Authorized & executable NOW:** AI-4 contract layer (governed-generation
  lifecycle contracts: sandbox-admission gate, deterministic-evaluator
  binding, candidate lifecycle states, human-approval binding, no-production-
  mutation guarantees) + synthetic tests — pre-G2 class.
- **BLOCKED:** any live generation run, any real-data evaluation, any
  promotion path execution.
- **Owner decisions needed:** none for the contract class (`05` §Engineering
  authority); numeric sandbox budgets later at runtime integration.

## AI-5 — Proactive Intelligence (`02:92-95`, `02:155-156`, D-AI-30/32/38, `06 §9`)

- **Exact official scope:** "Scheduled/event-triggered bounded research with
  budget, observability, recovery and kill switch." Monitoring of a versioned
  source universe with explicit coverage/freshness honesty.
- **Dependencies:** D-AI-30 = **DEFERRED UNTIL CORE STABILITY** (owner
  judgment gate); monitoring contracts DELIVERED (P0 `monitoring.py`,
  AI1-GC `monitoring_governance.py`); a scheduler/event runtime does NOT
  exist; real-data scans G2-gated; cadences "require explicit configuration,
  observability, idempotency, retry ceilings and a kill switch" (`02:186`)
  and "must not be hard-coded before operational requirements and budgets are
  approved" (`06 §9`).
- **Authorized NOW:** contract extension only (e.g. proactive-research job
  contracts reusing the P0 monitoring schema); **scheduler runtime is
  owner-gated** (D-AI-30 + cadence/budget approval).
- **BLOCKED:** any scheduled execution, any live monitoring run.
- **Owner decisions needed:** core-stability declaration; cadence/budget
  approval; deployment environment.

## AI-6 — External Intelligence (`02:97-100`, `02:161-170`, D-AI-29, `03 §External intelligence`)

- **Exact official scope:** "Only after untrusted-content boundaries,
  provenance, verification, injection controls and Two-Key Rule." Discovery/
  monitoring of approved source classes; filing ingestion + document version
  tracking; extraction; cross-source corroboration/contradiction/duplicate
  handling; PIT dossiers; evidence-linked interpretation; coverage/freshness/
  failure/conflict reporting. "All external content is untrusted input…
  AI must never invent missing financial values or silently reconcile
  contradictory sources."
- **Dependencies:** D-AI-29 = **DEFERRED BY GATE** (the boundary set must
  exist first); source-registry + evidence + dossier contracts DELIVERED
  (P0-AMD-1); ingestion/crawl runtime does NOT exist; source permissions and
  live crawling owner-gated (`02:203`).
- **Authorized NOW:** untrusted-content boundary + injection-isolation
  CONTRACT design (pre-G2 class); source-class admission schema extension.
- **BLOCKED:** any network ingestion, any live crawl, any provider contact.
- **Owner decisions needed:** source classes to admit first; Two-Key Rule
  operational parameters; credentials.

## AI-7 — Continuous Learning/Productization (`02:102-105`, `02:172-179`, D-AI-31)

- **Exact official scope:** "Calibration, model/prompt evaluation, recovery,
  rollback, observability and evidence-based autonomy expansion" + the
  recurring Product Intelligence & Improvement Loop (domain-matched
  evaluation; ranked proposals with baseline/evidence/uncertainty/cost/risk/
  rollback; "must not automatically change production").
- **Dependencies:** D-AI-31 = **DEFERRED UNTIL EVIDENCE** — "Autonomy expands
  only from measured evidence"; the required evidence (matured outcome labels,
  repeated research runs, calibration data) cannot exist until the research
  loop runs under G2-passed real-data execution. Prediction-feedback
  contracts DELIVERED (P0 `prediction.py`); product-audit contracts DELIVERED
  (P0 `product_audit.py`).
- **Authorized NOW:** contract extension only (e.g. calibration-record
  contracts); loop runtime BLOCKED.
- **BLOCKED:** everything operational until AI-4/AI-5 produce evidence.
- **Owner decisions needed:** autonomy-expansion evidence thresholds (owner
  call when evidence exists).

## P3.43 — Controlled Alpha Launch (owner-gated; numbering disambiguation)

- **Disambiguation (mandatory):** two distinct P3.43 labels exist. (1) "P3.43
  RADAR BOURSE terminology hardening" — COMPLETE locally, commit `795db69`
  (handoff §3/§4). (2) "P3.43 Controlled Alpha Launch" — the official next
  launch phase, BLOCKED (handoff: "Windows target, browser E2E, Electron
  runtime, live provider verification, GitHub push auth; owner has not issued
  `INSTALL`"). This matrix covers (2).
- **Dependencies:** owner-issued `INSTALL`; Windows-target validation
  (NOT_VERIFIED); browser E2E + Electron runtime verification; live provider
  verification (`live_verified=false`); GitHub push authorization for the
  19-commit local chain (R5).
- **Authorized NOW (repository-side):** none beyond what is already delivered
  — the launch package (handoff + checklists + runbooks) is reviewer/owner
  ready; remaining work is execution in owner environments.
- **Owner decisions needed:** issue `INSTALL`; authorize push (R5); provide
  target environments.

## Next complete authorized execution block

**AI-4 contract layer** is the next genuinely executable block: its official
dependencies (AI-3) are delivered at the contract class, its work class
(contracts + synthetic tests) is explicitly pre-G2-authorized (`02:202`), it
requires no owner decision to START (`05` §Engineering authority), and it
reuses the established pattern (scope derivation published BEFORE
implementation → additive module(s) → corpus-derived tests → battery →
independent audit). AI-5/AI-6/AI-7 contract extensions are also lawful in
principle but are each coupled to owner decisions (core stability, boundary
set, evidence) that make AI-4 the cleanest complete block. No downstream
implementation has been started by this matrix — this document is the
authorization check, and the implementation block should begin with its own
published scope derivation per governance precedent.
