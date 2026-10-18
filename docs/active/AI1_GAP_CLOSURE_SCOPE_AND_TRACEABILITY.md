# AI-1 Gap Closure — Scope Derivation, Gap Matrix & Requirement Traceability

Published BEFORE implementation (governance precedent: `P0_AMENDMENT_CONTRACTS_SCOPE_DERIVATION_REPORT.md`).
Baseline: HEAD `b3cbeb1` (P0-AMD-1a) on `main`, ahead 11/behind 0 vs live `origin/main` `c1984e7`, tracked tree clean, untracked bootstrap governance set preserved. Amendment corpus re-verified byte-identical this session (7/7 SHA-256 + `cmp` against `docs/governance/amendment_sources_2026-10-02/` and the owner upload originals).

## 1. Authoritative AI-1 definition (corpus loci)

- `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` lines 39–42: "**AI-1 --- Central Brain Foundation** — Observer, interpreter, regime, opportunity, filter intelligence, risk context, memory interfaces and governed orchestration."
- Dependency position: `02` line 7 — `P0-C → P0-V → P1 → P2 → P3 → G2 → P4/P5/P6 → AI-1 → AI-2 → AI-MA → AI-3 …`.
- Additive amendment §AI-1/AI-5 (`02` lines 155–156): the product "must support governed scheduled and event-triggered monitoring of the configured source universe and approved watchlists … Coverage gaps and inaccessible sources must be reported."
- Governance boundaries (`03`): §Run provenance (run_id, parent_run_id, hypothesis_id, dataset_version, code_commit, model_version, prompt_version, evaluation_version, policy_version, approval_state, timestamps, artifact references; "Missing required provenance blocks governed acceptance"); §Memory ("Episodic research evidence is immutable. Semantic learning is versioned and curated. No memory operation may silently modify production logic."); §Autonomy levels (L0–L4; "Agents cannot silently increase their autonomy level").
- Architecture (`02_PRODUCT…`): §Memory ("Run Context = execution state. Episodic Memory = immutable research evidence. Semantic Memory = curated, versioned knowledge."); rule 10 ("One canonical RunContext/RunProvenance binds each governed run"); rule 12 ("Every agent/tool/handoff/artifact/memory operation is traceable to run_id").
- Owner decision register (`05`): D-AI-22 ("Governance-grade RunContext/RunProvenance precedes Multi-Agent scale"), D-AI-28 (memory split), D-AI-19 (deterministic truth boundary), D-AI-41 (capability ≠ implementation evidence).
- Owner decision `00` §Binding principles 9 ("One RunContext / RunProvenance is minted per governed research run") and additive §AI-1/AI-5 monitoring honesty (D-AI-38).
- Opportunity detail loci: `02` lines 148–153 (four-way opportunity-object distinction; "never conflated with a stock-buy signal"; each object needs "evidence, timestamp, confidence semantics, data trust, risk, invalidation/expiry, and reason-for-now"); `06_PRODUCT_CAPABILITY_CHARTER` §4 (three-concept non-conflation; M&A requires own evidence) and §6 (explainable clusters; candidate classes; the five explanation questions).

## 2. Verified in-repo state per component (evidence: actual files, not reports)

| # | Corpus AI-1 component | In-repo implementation (verified) | Gap vs corpus |
|---|---|---|---|
| 1 | Observer | `backend/app/services/market_intelligence_service.py` (`run_market_monitoring_cycle`, P3.40) + `MarketMonitoringResult`/`IntelligenceEvent` (`backend/app/domain/market_intelligence.py:95–117`); callable, testable, no scheduler | Governed binding of a monitoring cycle to a job identity, run context, permission decision and honest coverage record — **contract seam missing** (additive `02`:155–156; D-AI-32/38) |
| 2 | Interpreter | `backend/app/domain/ai_intelligence.py` `AIIntelligenceCore` (P3.39) + `POST /api/ai/intelligence/{symbol}` + `engines/ai_explainer.py`; deterministic, data-trust gated | None at paper scope |
| 3 | Regime | `MarketRegime` 7-state literal (`market_intelligence.py:16–24`); `market_regime` RISK_ON/RISK_OFF/UNKNOWN derivation (`ai_intelligence.py:230–235`) | None at paper scope |
| 4 | Opportunity | `OpportunityRank` ranked top-N list (`market_intelligence.py:76–92`) | **Additive gaps**: no four-way opportunity-kind objects (`02`:148–153), no M&A non-conflation guard (`06` §4), no explainable clusters with the five required explanations (`06` §6) |
| 5 | Filter intelligence | P3.41 complete: `backend/app/domain/filter_intelligence.py` + `services/filter_intelligence_service.py` (+ P3.42 AI-core integration) | None |
| 6 | Risk context | `risk_score`/risk evidence in `IntelligenceResult`; `engines/risk_manager.py`; snapshot `top_risks` | None at paper scope |
| 7 | Memory interfaces | **Absent** — no episodic/semantic memory contract anywhere in `backend/app` (rg verified) | **Gap**: D-AI-28; `02_PRODUCT…` §Memory; `03` §Memory |
| 8 | Governed orchestration | **Absent** — no canonical `RunContext`/`RunProvenance` in `backend/app` (rg verified; only AI-2-scoped `AI2Provenance` in `ai2_service.py:153`) | **Gap**: `00` principle 9; `02_PRODUCT…` rule 10; `03` §Run provenance; D-AI-22 |

Ambiguity note: the corpus does not define numeric thresholds for "regime" or "risk context"; the existing deterministic derivations are therefore treated as satisfying the paper-scope requirement and are NOT modified (no invention; D-AI-19 keeps them deterministic).

## 3. This block's deliverables (all additive, paper/synthetic class)

Pre-G2 authorization class: "bounded design, schema work, source-registry design, synthetic/paper tests and safe dry-run work" (`02` line 202). Engineering authority for module/schema choices: `05` §Engineering authority, within D-AI-15…31/40.

| # | Deliverable | Corpus locus | Acceptance criteria → tests |
|---|---|---|---|
| D1 | `backend/app/domain/run_governance.py` — canonical `RunContext`, `RunProvenance`, `ArtifactRef`; provenance-completeness gate; autonomy-ceiling guard; L4 human-control lock | `00` principle 9; `02_PRODUCT…` rules 10/12; `03` §Run provenance/§Autonomy; D-AI-22 | Frozen contracts; UTC-only timestamps; run-kind pattern; artifact sha256 shape; code-commit shape; provenance completeness returns explicit missing-field list (blocks acceptance); autonomy level above declared ceiling refused; L4 requires recorded human approval → tests |
| D2 | `backend/app/domain/memory_interfaces.py` — immutable `EpisodicMemoryRecord` + append-only log (idempotent re-append, conflict rejection, no update/delete API); curated/versioned `SemanticMemoryEntry` + store (supersede chain); closed `MemoryOperationKind` set that cannot express production mutation | `02_PRODUCT…` §Memory; `03` §Memory; D-AI-28; arch rule 12 (traceable to run_id) | Records bind run_id; frozen models; duplicate-append semantics deterministic; version-1 must not supersede; version>1 must supersede; curation names rule or reviewer; no operation literal can represent production mutation → tests |
| D3 | `backend/app/domain/opportunity.py` — `OpportunityObject` with four-way kind distinction (`02`:148–153) bound to P0-AMD-1 `CompanyRole`; M&A evidence guard (`06` §4); `OpportunityClassLabel` + `ClassDefinition` (`06` §6); `OpportunityCluster` requiring the five explanation fields (`06` §6); deterministic expiry helpers | `02`:148–153; `06` §4/§6; D-AI-33 | reason-for-now, invalidation, expiry explicitness enforced; M&A kind refuses score-only basis and requires dedicated evidence ids; kind↔role conflation rejected; cluster refuses UNCLASSIFIED and requires why-now/invalidation/risk-adjusted/missing-information content; expiry checks deterministic → tests |
| D4 | `backend/app/domain/monitoring_governance.py` — `GovernedMonitoringCycleRecord` binding a P0-AMD-1 `MonitoringJobSpec`/`MonitoringJobState` (reusing `effective_run_permission`), an honest `CoverageReport`, and a `RunContext`; fail-closed refusal semantics | `02`:155–156, 193; D-AI-32/38; `06` §9/§11 | Kill-switch ENGAGED / HALTED / job-id mismatch ⇒ REFUSED_BY_POLICY with no events allowed; completed cycles require finish timestamps; failed sources force PARTIAL/FAILED; coverage honesty embedded as-is (universal claim stays structurally impossible) → tests |

Cross-cutting (inherited from the P0-AMD-1 contract layer): `schema_version` on every root contract; deterministic and clock-free (all timestamps passed as arguments); frozen models; explicit sentinels; finite values; no network, no I/O, no scheduler execution, no LLM, no route, no config change, no existing module modified; secrets never touched (`03` §Security).

## 4. Explicitly out of scope (this block)

- Any live or scheduled monitoring execution, crawling, provider calls, live data scans (`02`:186).
- Any HTTP route, frontend change, config flag change; `AI2_ENABLED` stays default-off.
- Any LLM execution; AI-2 behavior change (AI-2 completion is the NEXT block, `02` line 7; consumes D1/D2 contracts).
- AI-MA runtime agents; AI-3 persistence layer (AI-1 delivers *interfaces* only; `02` line 42 vs line 83–85).
- Any capability status upgrade (D-AI-41): monitoring/fundamental/product-audit stay NOT PROVEN until matching acceptance evidence (`02`:192–198).
- Modification of existing P3.39/P3.40/P3.41 modules (reuse over rewrite, `02` §Speed rule; D-AI-27).

## 5. Gates and approvals

- Owner approvals required: none for this contract/schema class (`05` §Engineering authority); no architecture-boundary change, no autonomy change, no production mutation, no live integration.
- G2: NOT_PASSED — not a prerequisite for this work class (`02` lines 10–11, 202); real-data AI-2 execution remains blocked.
- Push: owner-gated (11 local commits outstanding before this block).

## 6. Dependency-chain position after this block

`AI-1 gap closure` (this block) → **AI-2 required completion** (`02` lines 44–53 required-items audit against `ai2_service.py`; import-audit finding F5 list) → **AI-MA-1..6** (`02` lines 55–81; `02_PRODUCT…` §Architecture rules/§Complexity budget) → **AI-3 Research Memory** (`02` lines 83–85: episodic immutable run artifacts + curated/versioned semantic memory) → G2 remains the hard gate for real-data AI-2 execution throughout (`02` lines 10–11, 201).
