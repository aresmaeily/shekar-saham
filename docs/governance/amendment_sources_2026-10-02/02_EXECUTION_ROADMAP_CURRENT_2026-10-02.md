# RADAR_BOURSE --- Final Dependency-First Execution Roadmap

Revision: 2026-09-29 Status: FINAL OWNER-DIRECTED BASELINE

## Dependency graph

P0-C → P0-V → P1 → P2 → P3 → G2 → P4/P5/P6 → AI-1 → AI-2 → AI-MA → AI-3
→ AI-4 → AI-5 → AI-6 → AI-7

G2 blocks all real-data AI-2 execution until formally passed. Design,
contracts, paper/synthetic tests and dry-runs may proceed before G2.

## P0 --- Baseline Verification & Architecture Decisions

Outputs: - repository truth - Git state - runtime/test evidence -
contract inventory - architecture decisions - open-decision closure

## P1 --- Data Foundation + One Real Vertical Slice

Launch → symbol → trusted market data → deterministic measurement/chart.

## P2 --- Deterministic Measurement & Evidence Core

PIT, corporate actions, survivorship, look-ahead protection,
costs/slippage, liquidity, versioning and evidence lineage.

## P3 --- Evaluation Harness

Backtest, OOS, WFO, forward test, statistical evaluation,
reproducibility, holdout and multiple-testing controls.

## G2 --- Independent Validation

Formal human gate requiring the designated evidence, quant and QA
validation roles plus owner authority.

Governance G2 is verified. Runtime G2 is not yet implemented.

## AI-1 --- Central Brain Foundation

Observer, interpreter, regime, opportunity, filter intelligence, risk
context, memory interfaces and governed orchestration.

## AI-2 --- Research Loop Hardening / MVRL

Reuse the existing bounded loop:

Question → Hypothesis → Candidate → Deterministic Evaluation →
Comparison → Learning → Next Hypothesis

Required: - immutable run identity - provenance - budget/time/iteration
limits - evidence artifacts - duplicate detection - failure/recovery -
invalidation - human approval state

## AI-MA --- Multi-Agent Runtime

### AI-MA-1

Thin Central Orchestrator around the existing Research Loop.

### AI-MA-2

Capability registry and specialist contract.

### AI-MA-3

First bounded specialist as a tool/capability.

### AI-MA-4

Second specialist + bounded parallel execution.

### AI-MA-5

Artifact-first branch exchange.

### AI-MA-6

Tracing, observability and failure isolation.

No fixed agent count. No peer-to-peer backbone. No autonomous spawning.

## AI-3 --- Research Memory

Episodic immutable run artifacts plus curated/versioned semantic memory.

## AI-4 --- Governed Generation

AI-generated filters/indicators/strategy specifications only through
sandbox → deterministic evaluation → lifecycle → approval.

## AI-5 --- Proactive Intelligence

Scheduled/event-triggered bounded research with budget, observability,
recovery and kill switch.

## AI-6 --- External Intelligence

Only after untrusted-content boundaries, provenance, verification,
injection controls and Two-Key Rule.

## AI-7 --- Continuous Learning/Productization

Calibration, model/prompt evaluation, recovery, rollback, observability
and evidence-based autonomy expansion.

## Speed rule

Prefer reuse over rewrite; additive contracts over replacement; one
shared context over distributed identities; deterministic services over
LLM duplication; manager-controlled specialists over peer-to-peer; and
parallel execution only for genuinely independent work.


---

## Binding owner-directed additive amendment — 2026-10-02

Status: CURRENT PRODUCT REQUIREMENT / ADDITIVE TO THE 2026-09-29 BASELINE
This amendment expands the target capabilities. It does not remove or downgrade any earlier requirement, claim implementation, waive G2, or authorize production mutation.

### Product capability charter
The final product is an **Evidence-Driven Market Intelligence, Fundamental Intelligence, Research, and Product Improvement Platform**. The system must support the following coordinated loops:

1. **Market loop:** observe → detect anomalies → interpret → regime/context → opportunity clusters → risk context → explain with evidence.
2. **External/company intelligence loop:** monitor an explicit, versioned source universe across market data, exchange/regulatory disclosures, issuer reports, financial statements, audited reports, official company sources, reputable news, and other approved public sources → extract facts/events → cross-check → resolve or surface conflicts → build point-in-time company dossiers → feed fundamental analysis and opportunity context.
3. **Research loop:** question → preregistered hypothesis → candidate filter/strategy → deterministic backtest → WFO/OOS → forward test → statistical/robustness/risk evaluation → compare → learn → next hypothesis.
4. **Product intelligence loop:** observe privacy-safe product-quality and UX signals → audit filters/models/data/services and user journeys → propose improvement hypotheses → test in an isolated evaluation path → report expected impact, risks, and evidence → human approval before any consequential change.
5. **Prediction feedback loop:** timestamped prediction → predefined outcome horizon → actual result → error decomposition/calibration/drift analysis → research proposal → isolated evaluation → approval-controlled adoption.

### P0 — Contracts and source-universe design
P0 must define and version:
- source registry and source tiers; coverage/limitations report; source ownership, permitted access, rate limits and refresh policy;
- company/symbol identity resolution, corporate actions, filing periods, publication timestamps, restatements, currency/unit normalization and point-in-time semantics;
- evidence item schema with source URL/identifier, publisher, retrieval time, publication time, effective period, source tier, document/version hash where appropriate, extraction method/model version, corroboration/conflict status, trust status and citations;
- company fundamental dossier schema; explicit distinction between investment candidate, user-watchlisted company, and possible M&A/acquisition-target intelligence;
- monitoring job identity, schedules/triggers, retry/idempotency, freshness SLAs, budget, observability, alerting and kill switch;
- product audit charter, privacy-safe telemetry boundaries, test cadence, baseline metrics, and improvement proposal contract;
- prediction registry and outcome-maturity rules to prevent look-ahead and label leakage.

### P1/P2 — Trusted market and fundamental evidence
P1/P2 must treat company filings and fundamental information as versioned, time-aware evidence—not as unqualified text. Primary sources should be preferred where available (exchange/regulator filings, issuer disclosures, audited/official financial statements and official company materials). Secondary sources may enrich context but must not silently override primary evidence. Conflicting figures, stale documents, restatements, missing periods, units/currencies and unknown audit status must be surfaced. Every conclusion must identify its information cutoff so historical research cannot use information published later.

### P3 — Evaluation and research integrity
In addition to existing backtest/WFO/forward-test requirements, the evaluation layer must support point-in-time fundamental snapshots, no-look-ahead checks, survivorship/corporate-action handling, costs/slippage/liquidity, holdout isolation, multiple-testing controls, regime-sliced evaluation, baseline comparisons, calibration, and matured outcome labels. AI may summarize results; deterministic evaluation services remain authoritative.

### P5/P6 — Alerts, company coverage and opportunity lifecycle
Operational alerts must cover market anomalies, material company disclosures, filing/report publication, source conflicts, source staleness, significant financial-statement changes, watchlist changes, opportunity creation/expiry, and research-result maturity. Opportunity objects must distinguish at minimum:
- market/stock investment candidate;
- user-watchlist company intelligence;
- event/news-driven candidate;
- possible corporate M&A/acquisition-target signal (only when supported by evidence; never conflated with a stock-buy signal).
Each object needs evidence, timestamp, confidence semantics, data trust, risk, invalidation/expiry, and reason-for-now.

### AI-1 / AI-5 — Active intelligence and continuous monitoring
The product must not depend solely on user prompts. It must support governed scheduled and event-triggered monitoring of the configured source universe and approved watchlists, including market-wide signals and company-specific disclosures. “Monitor the web” means continuous coverage of a declared, expanding, auditable source universe—not a claim that every URL on the public internet is covered. Coverage gaps and inaccessible sources must be reported. Monitoring must respect source terms, access controls, robots/rate limits where applicable, privacy, resource budgets, and kill switches.

### AI-2 / AI-3 / AI-4 — Research, memory and governed generation
Market, fundamental, and product-improvement hypotheses may enter the same governed research lifecycle when a suitable deterministic evaluator exists. Episodic research artifacts remain immutable; semantic lessons remain curated/versioned. AI-generated filters, scoring rules, fundamental features, or software-change proposals remain candidates until isolated tests, evaluation gates and required human approval are passed. No self-modifying production logic.

### AI-6 / P8 — External intelligence and fundamental analysis
External intelligence must include more than news summarization. Required capabilities include:
- discovery/monitoring of approved public source classes;
- official filing/report ingestion and document version tracking;
- extraction of financial statements, notes, auditor opinions, guidance, material events and company disclosures where source data supports it;
- cross-source corroboration, contradiction tracking, duplicate detection and source-quality weighting;
- point-in-time fundamental dossier and change-over-time analysis;
- evidence-linked fundamental interpretation and risk flags;
- source coverage, freshness, failure and unresolved-conflict reporting.
All external content is untrusted input. Prompt-injection and content-instruction isolation, provenance, tool boundaries and the Two-Key Rule remain mandatory. AI must never invent missing financial values or silently reconcile contradictory sources.

### AI-7 / P10 — Product Intelligence and continuous product audit
The final product must include a recurring, bounded **AI Product Intelligence & Improvement Loop**. It audits the whole product by domain rather than incorrectly treating every software component as a trading strategy:
- financial filters/strategies: deterministic backtest, WFO/OOS, forward test, costs, risk, false positives, stability, regime dependence and outcome maturity;
- market/fundamental AI: Golden Set quality, source grounding, freshness, conflict handling, calibration, drift and invalidation quality;
- data/providers/operations: trust failures, latency, stale data, missing coverage, errors, retries, resource use and recovery;
- product/UX: privacy-safe usage funnels, task completion, repeated actions, error paths, accessibility/usability feedback and feature adoption where telemetry is lawful and consent/policy-compliant;
- application quality: regression, performance, reliability, security and release-readiness tests appropriate to each component.
The system should propose ranked improvement hypotheses with baseline, expected benefit, evidence, uncertainty, cost, risks, rollback plan and evaluation design. It must not automatically change production, promote filters, alter permissions/budgets, or deploy software.

### Initial cadence policy (configurable, not hard-coded as a universal SLA)
- event-driven: material filings, source changes, market anomalies and watchlist events when feeds support it;
- scheduled: periodic source freshness/coverage and market/financial intelligence scans;
- weekly or otherwise owner-configured: filter/strategy and prediction outcome review where labels have matured;
- monthly or owner-configured: cross-product capability, UX, reliability and improvement review.
Cadence, thresholds and budgets require explicit configuration, observability, idempotency, retry ceilings and a kill switch. Do not run live-data scans or backtests merely to prove a document change.

### Reference-system strategy: TabloKhani first, then evidence-based extension
TabloKhani-style board reading is the **initial behavioral/reference benchmark**, not the ceiling or source of truth. First document a lawful, observable capability matrix for market-board interpretation and reproduce the reference behaviors that are relevant to the product. Then extend using validated data, point-in-time fundamentals, multi-source company intelligence, regime/context, research memory, risk-adjusted opportunity clusters, and results from the governed Research Loop. “Beyond reference sites” may be claimed only after a versioned Golden Set and repeatable benchmark show measurable improvement; no unsupported superiority claims.

### Acceptance requirements
A capability is not accepted by document/code presence alone. Evidence must match the capability:
- monitoring: schedule/trigger execution, source coverage/freshness, event lineage, failure/recovery, rate/budget enforcement and kill switch;
- external/fundamental intelligence: point-in-time source records, cross-check/conflict examples, citation completeness, restatement handling and missing-source behavior;
- market interpretation: Golden Set results, confidence calibration where probabilities are claimed, false-positive/false-negative analysis and invalidation tests;
- research: reproducible runs, deterministic evaluation, provenance, holdout protection, budget/time enforcement, failure recovery and independent validation;
- product intelligence: recurring audit run, privacy-safe metric definitions, baseline, actionable proposals and evidence of evaluation; no production mutation;
- all governed actions: traceable run identity, versions, human approval state and explicit limitations.

### Gates preserved
- G2 continues to block all real-data AI-2 runs until independent validation and owner acceptance.
- Before G2, only bounded design, schema work, source-registry design, synthetic/paper tests and safe dry-run work are allowed under existing policy.
- External intelligence is not automatically production-ready because it is specified here; source permissions, provenance, untrusted-content isolation and Two-Key Rule must be implemented and validated.
- LIVE, continuous monitoring, multi-source completeness, financial correctness and product-wide audit status remain NOT PROVEN until matching evidence exists.
