# P0 Addendum (2026-10-02 Amendment) — Scope Derivation & Execution Contract

Mission step D: derive the next authorized roadmap block from the imported authoritative corpus and the verified repository state. Published BEFORE implementation, per the owner mandate. Import basis: `docs/governance/evidence/2026-10-18_AMENDMENT_IMPORT_AUDIT.md` (7 files byte-verified; findings F1–F10). Baseline: HEAD `42587fa` + this mission's import changes; all gates unchanged.

## 1. Derivation

### 1.1 Candidates considered, in dependency order

| Candidate | Graph position | Verified status | Assessment |
|---|---|---|---|
| G2 (runtime) | after P3 | NOT_PASSED; handoff reviewer-ready | **Owner-executed human gate** (RACI `04` §Final RACI: 1(A), 6/14(R)) — not agent-executable; remains owner-gated |
| P4/P5/P6 | after G2 | P4 not defined in corpus; P5/P6 alerts/coverage/opportunity defined additively | Acceptance sits after G2; P5/P6 objects depend on the P0-additive schemas below |
| **P0 addendum — Contracts and source-universe design** | **first node (P0)** | **7 defined contract groups; none implemented** | **SELECTED** — see §1.2 |
| AI-1 Central Brain Foundation | after P4/P5/P6 | Components exist (P3.38–41, P3.81–89); additive monitoring scope depends on source registry + monitoring job identity | Its additive scope has an **unmet prerequisite**: the P0 addendum |
| AI-2 completion (Category A remainder) | after AI-1 | Scaffold done (AI2-A…E); roadmap-required items missing (evidence artifacts, budget/iteration limits, duplicate detection, recovery, invalidation, approval state — Import Audit F5) | Depends on AI-1 settlement and consumes the P0-additive evidence/artifact schemas |
| AI-MA / AI-3 / AI-4… | after AI-2 | Not started | Later in graph; AI-3 definition now exists (Import Audit F1) but remains after AI-MA |

### 1.2 Why the P0 addendum is the next authorized block

1. **Dependency-first**: the imported roadmap's first node is P0, and the additive amendment imposes NEW P0 obligations — "P0 must define and version: …" (`02` additive §P0, lines 131–139). P0 is complete in-repo only for the 2026-09-29 outputs; the 2026-10-02 contract groups are absent. Unresolved P0 obligations precede AI-1 work.
2. **Explicit pre-G2 authorization**: "Before G2, only bounded design, schema work, source-registry design, synthetic/paper tests and safe dry-run work are allowed under existing policy" (`02` additive §Gates preserved, line 202). Every deliverable below is design/contract/schema work with synthetic tests only.
3. **Prerequisite-free**: no missing input — the amendment enumerates the required content itself; engineering authority covers schema/module/API choices (`05` §Engineering authority) provided D-AI-15…31 are respected.
4. **Unblocking power**: AI-1's additive monitoring scope, AI-6/P8 fundamental intelligence, P5/P6 opportunity objects, AI-7/P10 product audit and the prediction feedback loop all consume these schemas (Import Audit F4/F6).
5. **No invention**: every field-level requirement below is traceable to corpus text (§3 matrix). Nothing is added "because it seems reasonable".

Block identifier (as titled by the corpus itself): **"P0 — Contracts and source-universe design"**, Binding additive amendment, `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` line 131. This report's execution of it is labelled **P0-AMD-1** for traceability only; the authoritative definition is the corpus text.

## 2. Prerequisites and their verified statuses

| Prerequisite | Status | Evidence |
|---|---|---|
| Amendment corpus imported & verified | DONE (this mission) | Import audit §1–§2, `IMPORT_FAIL=0` |
| G2 gate | NOT_PASSED — **not a prerequisite for schema/design work** per `02` lines 10–11 and 202 | Import audit F2 |
| Owner approval for contract/schema work | NOT REQUIRED — engineering authority covers it (`05` §Engineering authority); no architecture-boundary change, no autonomy change, no production mutation, no live integration | Import audit §3.2.4 |
| Architecture locks compatibility | VERIFIED — additive contracts+tests match the Future Architecture Gate pattern (`AI_BRAIN_ARCHITECTURE.md` §Future Architecture Gate) | Import audit §3.4 |
| Existing test baseline green | VERIFIED — 348 passed / 2 warnings at `42587fa` (`docs/governance/evidence/raw/2026-10-18_ai3a/`) | prior at-commit battery |

## 3. In-scope deliverables and traceability matrix

All deliverables are **additive versioned domain contracts (Pydantic schemas) + deterministic pure functions + synthetic tests**. No HTTP route, no scheduler execution, no network I/O, no LLM call, no live data, no config behavior change, no modification of existing modules.

| # | Corpus requirement (quote locus) | Deliverable | Acceptance criterion → test |
|---|---|---|---|
| D1 | "source registry and source tiers; coverage/limitations report; source ownership, permitted access, rate limits and refresh policy" (`02`:133); source classes + "must not claim literal coverage of the entire internet" (`06` §3); coverage/freshness/gaps honesty (D-AI-38) | `SourceTier`, `SourceDescriptor`, versioned append-only `SourceRegistry`, `CoverageReport` (explicit gaps/inaccessible/freshness; universal-coverage claim structurally refused) | Registry versions immutably; coverage report exposes gaps; universal-coverage assertion rejected → tests |
| D2 | "company/symbol identity resolution, corporate actions, filing periods, publication timestamps, restatements, currency/unit normalization and point-in-time semantics" (`02`:134); publication vs retrieval vs reporting period recorded separately (`06` §3.5); "Every conclusion must identify its information cutoff" (`02`:142) | `CompanyIdentity` (unresolved ambiguity stays explicit), `CorporateActionRecord`, `FilingPeriod`, PIT cutoff helpers (`is_eligible_at`) | Later-published evidence excluded from earlier cutoffs; identity ambiguity surfaced, not guessed → tests |
| D3 | "evidence item schema with source URL/identifier, publisher, retrieval time, publication time, effective period, source tier, document/version hash where appropriate, extraction method/model version, corroboration/conflict status, trust status and citations" (`02`:135); syndication ≠ corroboration (`06` §3.3); contradictions remain explicit (`06` §3.4; D-AI-33) | `EvidenceItem` (publication time optional-but-explicit when unknown — never defaulted from retrieval time), `EvidenceConflict`, `independent_corroboration_count` | Missing publication time → explicit `UNAVAILABLE`; syndicated copies excluded from corroboration count; conflicts persist until deterministic rule or human review → tests |
| D4 | "company fundamental dossier schema; explicit distinction between investment candidate, user-watchlisted company, and possible M&A/acquisition-target intelligence" (`02`:136); dossier content list; "No financial fact may be invented to fill a gap" (`06` §4); M&A "requires its own evidence and should not be inferred solely from a stock opportunity score" (`06` §4) | `FundamentalFact` (unit/currency/period/restatement/auditor status explicit), `CompanyDossier`, `CompanyRole` 3-way distinction + validator | Missing values → `NOT_AVAILABLE`; M&A role rejected without independent evidence refs; units mandatory → tests |
| D5 | "monitoring job identity, schedules/triggers, retry/idempotency, freshness SLAs, budget, observability, alerting and kill switch" (`02`:137); "Every job needs idempotency, retry ceilings, timeout, concurrency/rate limits, run identity, audit trace, last-success status, failure alert, kill switch" (`06` §9); per-source declared coverage/refresh/ceilings (`02-arch` additive §Continuous monitoring architecture) | `MonitoringJobSpec` (bounded, kill switch default engaged/safe), `MonitoringJobState` (last-success, failure state) — **spec/state contracts only; no scheduler** | Spec validation enforces ceilings + idempotency key + kill switch; default state fails closed → tests |
| D6 | "product audit charter, privacy-safe telemetry boundaries, test cadence, baseline metrics, and improvement proposal contract" (`02`:138); domain-matched evaluation — "Backtest is not a universal test" (`06` §8); proposals advisory, "It must not automatically change production…" (`02`:179; D-AI-35/36); telemetry minimum-necessary/retention (D-AI-39) | `ProductAuditDomain`, `AuditCadence` (owner-configurable), `PrivacyTelemetryBoundary`, `ImprovementProposal` (approval-state machine that cannot reach an "applied" state) | Backtest-family evaluator rejected for non-financial domains; proposal cannot encode production mutation; telemetry boundary mandatory → tests |
| D7 | "prediction registry and outcome-maturity rules to prevent look-ahead and label leakage" (`02`:139); preregistration before outcome observation; "Never change the original prediction record or use future data in the original assessment" (`06` §7; D-AI-37) | `PredictionRecord` (frozen at creation), `OutcomeRecord`, deterministic `maturity_state()`; append-only registry helper | Mutation of a registered prediction rejected; evaluation before maturity rejected; outcome observation predating registration rejected → tests |

Cross-cutting: every root contract carries `schema_version` ("define and version", `02`:132); domain logic is deterministic and clock-free (timestamps/`as_of` passed as arguments); sentinels `UNAVAILABLE`/`NOT_AVAILABLE` for unknowns; secrets never touched (`03` §Security).

## 4. Explicitly out of scope (this block)

- Any live/scheduled monitoring execution, crawling, provider calls, or live-data scans — even to "prove" this document change (`02`:186).
- Any HTTP route exposure, frontend change, or new config flag flipping anything on.
- Any LLM/provider execution or AI-2 behavior change; `AI2_ENABLED` stays default-off.
- AI-1/AI-2/AI-MA/AI-3 implementation (follow-on queue, §6).
- Scheduler jobs, alert dispatch, telemetry collection — contracts only.
- Any claim that a capability is IMPLEMENTED/RUNTIME_VERIFIED/LIVE_VERIFIED/PROVEN (D-AI-41).

## 5. Required approvals and gates

- **Owner approvals required: none** for this block (engineering authority, `05`) — but push remains owner-gated, and G2 remains owner-executed.
- Safety/trust gates preserved: fail-closed defaults; AI ≠ financial truth (`03` §Core principle); untrusted external content boundaries modeled as status fields only; no broker/trading/production mutation concepts admitted anywhere in the contracts (`03` §AI may not; `02-arch` additive §G2 and external-source boundaries).

## 6. Follow-on queue (NOT authorized by this report; derived for owner visibility)

1. **AI-1 gap closure** (after P0-AMD-1): map P3.38–41/P3.81–89 components to the corpus AI-1 scope; implement remaining paper/synthetic pieces (opportunity clusters need D4/D2 schemas).
2. **AI-2 Category A completion**: roadmap-required loop hardening items (F5) consuming D3 evidence-artifact contracts.
3. **AI-MA-1..6** after AI-2; **AI-3 Research Memory** after AI-MA (definition now in-repo, Import Audit F1).
4. **G2 runtime** — owner-executed at any time the owner chooses (handoff ready); P3.43 alpha launch — owner-gated.

## 7. Validation plan (Step F)

Full standard battery (from `backend/` unless noted): `PYTHONPATH=. pytest -q tests`; `python -m pyflakes app tests`; `python -m compileall app tests` (or equivalent); `pip-audit`; `python scripts/validate_alpha_environment.py` and `validate_alpha_runtime.py`, `validate_frontend_static.py` (repo root); bootstrap validator `python scripts/validate_bootstrap_config.py`; `git diff --check`; new-block tests `PYTHONPATH=. pytest -q tests -k amendment_p0`. Raw outputs → `docs/governance/evidence/raw/2026-10-18_p0amd1/`. Remaining NOT_VERIFIED unless genuinely executed: Windows parity, Python 3.13, native Claude CLI recognition, live providers, live LLM.
