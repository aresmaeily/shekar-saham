# P5/P6 — Alerts, Company Coverage and Opportunity Lifecycle: Scope Derivation and Gap Matrix

**Date:** 2026-10-30 (Asia/Tehran) · **Directive:** CONSOL-GOV-39 (Phase 2/3) · **Baseline HEAD at derivation:** `ca38a71b512ce8656341b25ae531b2824292fad7` (tree `5d9feed5…`)

Derivation method: requirement-by-requirement mapping of the canonical amendment text against the actual repository tree at the baseline commit, with exact file:line loci. No capability is inferred from roadmap prose, filenames, or reports alone; every classification below is anchored in source or committed test evidence. This report is published BEFORE the implementation commit it authorizes (AI1-GC precedent: scope derivation precedes implementation).

## 1. Authoritative scope (corpus loci)

- `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` line 7 — dependency position: `… G2 → P4/P5/P6 → AI-1 …`; P5/P6 acceptance sits after G2.
- Same file, additive §"P5/P6 — Alerts, company coverage and opportunity lifecycle" (lines 147–153):
  1. Operational alerts must cover market anomalies, material company disclosures, filing/report publication, source conflicts, source staleness, significant financial-statement changes, watchlist changes, opportunity creation/expiry, and research-result maturity (**nine classes**).
  2. Opportunity objects must distinguish at minimum: market/stock investment candidate; user-watchlist company intelligence; event/news-driven candidate; possible corporate M&A/acquisition-target signal (evidence-backed only; never conflated with a stock-buy signal).
  3. Each object needs evidence, timestamp, confidence semantics, data trust, risk, invalidation/expiry, and reason-for-now.
- `06_PRODUCT_CAPABILITY_CHARTER` §4 (three-concept non-conflation; M&A requires its own evidence) and §6 (explainable clusters; five explanation questions; formal class definitions).
- Amendment "Gates preserved" (`02` line 200–204): G2 blocks real-data AI-2 only; monitoring cadence/budget/kill-switch require explicit configuration and owner approval (`02` lines 181–186; register D-AI-30); `06 §9` forbids hard-coded cadences before operational approval.

**P4 status (preserved authoritative finding, not re-derived):** P4 is NOT DEFINED in the imported corpus. `docs/active/P0_AMENDMENT_CONTRACTS_SCOPE_DERIVATION_REPORT.md:12` records: "P4 not defined in corpus; P5/P6 alerts/coverage/opportunity defined additively". This cycle does not invent a P4 scope.

## 2. Gap matrix — requirement → repository reality (baseline `ca38a71b…`)

| # | P5/P6 requirement (corpus locus) | Classification | Repository evidence |
|---|---|---|---|
| R1 | Four-way opportunity-kind distinction + role binding (02:149–152; 06 §4) | **implemented and evidence-verified** | `backend/app/domain/opportunity.py:51–77` (`OpportunityKind`, `_KIND_TO_ROLE`), `:159–171` (conflation + M&A score-only refusal); 58 corpus-derived tests `backend/tests/test_ai1_opportunity_monitoring.py:87–260`; battery-verified at `ea3277e`/`2f86c4a` (PROJECT_EXECUTION_STATE §2g); zero drift since |
| R2 | Per-object honesty fields: evidence, timestamp, confidence, data trust, risk, invalidation/expiry, reason-for-now (02:153) | **implemented and evidence-verified** | `opportunity.py:105–188` (`OpportunityObject` frozen contract; expiry explicit-decision guard `:181–185`) |
| R3 | Explainable clusters with the five questions (06 §6) | **implemented and evidence-verified** | `opportunity.py:206–259` (`OpportunityCluster`; UNCLASSIFIED cluster refused `:254–259`); tests `test_ai1_opportunity_monitoring.py:237–260` |
| R4 | Operational alert coverage — the nine corpus classes (02:148–149) as **governed amendment-class contracts** bound to the existing evidence/monitoring/opportunity/prediction layers | **not implemented** (the gap this cycle closes at the contract layer) | No alert contract exists in the domain layer: `rg "class.*Alert|AlertKind" backend/app/domain/` → 0 hits at baseline; the only alert surface is the pre-amendment product notifier (`backend/app/services/notifier.py:240` legacy dict-based buy/sell formatting) and the in-process `DomainEvent`/`EventBus` (`backend/app/domain/events.py:7–47`, generic, no governed semantics) |
| R5 | Monitoring honesty seam — job spec/state, failure alert, kill switch, cycle records (02:155–156, 193; D-AI-32/38; 06 §9) | **implemented and evidence-verified** | `backend/app/domain/monitoring.py:46–160` (`MonitoringJobSpec.alerting_ref:109`, `run_allowed` kill-switch `:127`, `failure_alert_sent` HALTED guard `:155–156`); `monitoring_governance.py:53–127`; tests `test_ai1_opportunity_monitoring.py:312–479` |
| R6 | Source-conflict data model | **implemented and evidence-verified** | `backend/app/domain/evidence.py:141–183` (`EvidenceConflict` with open/resolved consistency guard); `EvidenceItem.conflicting_with` `:111` |
| R7 | Source-staleness data model (freshness SLA → stale set) | **implemented and evidence-verified** | `backend/app/domain/source_registry.py:124–220` (`CoverageReport.stale_sources:140`; staleness from declared freshness SLA `:196–211`) |
| R8 | Financial-statement change/restatement model | **implemented and evidence-verified** | `backend/app/domain/fundamental_dossier.py:181–222` (`FundamentalFact` with `restatement_version`, `supersedes_fact_id` mandatory for restatements `:219–220`) |
| R9 | Research-result maturity model | **implemented and evidence-verified** | `backend/app/domain/prediction.py:36–80` (`PredictionRecord.event_maturity_rule:52`; `OutcomeRecord` single-observation `:70–80`) |
| R10 | Product-level operational alerting (legacy, pre-amendment scope) | **implemented, out of amendment scope** | `notifier.py` (Telegram/Bale + dry-run), `backend/app/engines/anomaly.py` (`AnomalyDetector` price/volume/orderbook), `ws_hub.py` push; these do not carry governed amendment semantics and are not modified by this cycle |
| R11 | Operational alert cadence/budget/launch configuration | **owner decision required** | `02:181–186` (cadence policy requires explicit configuration); D-AI-30 (05 register: core-stability + cadence/budget approval); CONSOLGOV13 §3 records AI-5 extensions coupled to D-AI-30. NOT requested or granted by CONSOL-GOV-39 |
| R12 | Live-data alerting on real market/company sources | **externally blocked** | R3 (live-credential provisioning — owner act) not satisfied; `backend/app/core/config.py:282` hard-codes `verified=False`; provider probes fail-closed `live_verified=false` |

## 3. Dependency position and authorization class

- G2 is PASSED (owner-recorded transition, `docs/active/G2_GATE_STATE.json` verdict=PASSED, commit `ca38a71b…`), so the P5/P6 execution barrier named in CONSOLGOV13 ("CONTRACT-COVERED; execution BLOCKED-BY G2") is lifted for locally executable, non-live work.
- The authorized work class executed this cycle: **additive deterministic contract + corpus-derived tests + governance bookkeeping** — the same class as P0-AMD-1/AI1-GC. No LLM execution, no live data, no route, no config change, no existing-module modification, no protected file touched, no cadence/launcher operationalization (D-AI-30 remains owner-gated).
- Work packages and parallelism: WP-1 (governed alert taxonomy contract) is the single locally executable implementation gap (R4). It reuses R6/R7/R8/R9 contracts by reference and does not touch them → no shared-contract mutation; therefore no parallelization hazard. WP-2 (bookkeeping) is sequential after WP-1 by repo convention. Dependent/downstream work (operational cadence, delivery integration into notifier/ws_hub, live-data alerting) stays owner-gated/externally blocked and is NOT started.

## 4. Acceptance criteria for the WP-1 implementation (test-derived, corpus-derived)

1. A closed nine-member `AlertKind` set exactly mirroring 02:148–149 — unknown alert kinds are unrepresentable.
2. `GovernedAlertObject` frozen contract carrying, for every alert regardless of kind: evidence ids (≥1, distinct, never self-referential), timestamp (UTC-enforced), confidence semantics (bounded [0,1] + declared basis), data trust state, risk semantics, invalidation conditions (≥1), explicit expiry decision (dated or explicitly open-ended — never a forgotten default), reason-for-now, and run identity.
3. Per-kind dedicated trigger bindings to the authoritative existing contracts — each kind MUST carry its own binding ref and MUST NOT carry another kind's binding field:
   - `MARKET_ANOMALY` → `detector_ref` (deterministic detector observation id);
   - `MATERIAL_COMPANY_DISCLOSURE` → `content_kind` ∈ {MATERIAL_EVENT, COMPANY_DISCLOSURE, GUIDANCE} (reuses `external_intelligence.ContentKind`);
   - `FILING_REPORT_PUBLICATION` → `content_kind` ∈ {FILING, FINANCIAL_STATEMENT, NOTE, AUDITOR_OPINION};
   - `SOURCE_CONFLICT` → `conflict_id` (an `EvidenceConflict.conflict_id`);
   - `SOURCE_STALENESS` → `stale_source_ids` ≥1 distinct (mirrors `CoverageReport.stale_sources`);
   - `SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE` → `fact_id` + `superseded_fact_id` (restatement chain semantics);
   - `WATCHLIST_CHANGE` → `watchlist_ref` + `change_kind` ∈ {ADDED, REMOVED, UPDATED};
   - `OPPORTUNITY_LIFECYCLE` → `opportunity_object_id` + `lifecycle_transition` ∈ {CREATED, EXPIRED};
   - `RESEARCH_RESULT_MATURITY` → `prediction_id` + `outcome_id` (a matured `OutcomeRecord` binding).
4. M&A non-conflation carried through to alerts (06 §4): an `OPPORTUNITY_LIFECYCLE` alert referencing an M&A-kind opportunity must carry dedicated M&A evidence (`ma_signal_evidence_ids` ≥1) and is refused when that evidence is absent.
5. Deterministic expiry helpers mirroring the opportunity layer (`is_expired`/`active_at`).
6. No fabrication paths: the module computes no financial truth, performs no I/O, calls no LLM, and never mints evidence or confidence values (D-AI-19/33/41).

## 5. Explicitly out of scope this cycle (preserved boundaries)

- No route, no service wiring, no notifier/ws_hub integration, no scheduler/cadence, no delivery of any alert (owner-gated D-AI-30; P3.60 no-unauthorized-feature).
- No AI-2 real-data execution, no `AI2_ENABLED` change, no `verified` change, no live-provider contact.
- No modification of `opportunity.py`, `evidence.py`, `source_registry.py`, `fundamental_dossier.py`, `prediction.py`, `monitoring*.py` — consumed read-only via imports (reuse-over-rewrite).
- No protected bootstrap path, runtime-gate, workflow, or sealed-evidence change.
