# RADAR_BOURSE --- Final Product / AI Multi-Agent Architecture

Revision: 2026-09-29 Status: FINAL OWNER-DIRECTED ARCHITECTURE

## Target topology

Human Authority ↓ Thin Governor / Policy Gate ↓ Central Orchestrator /
AI Brain ↓ Bounded Specialist Agents ↓ Deterministic Tools / Financial
Services ↓ Evidence / Artifact / Memory / Version ↓ Advisory Result ↓
Human Approval

## Architecture rules

1.  Central Orchestrator owns workflow coordination.
2.  Governor owns authorization, transition policy, run identity,
    provenance binding, budget/quota policy and audit integration.
3.  Governor does not calculate financial truth and does not duplicate
    lifecycle guards.
4.  Initial hierarchy depth is two levels.
5.  Specialists do not negotiate global state peer-to-peer.
6.  Agent-as-tool is the default specialist pattern.
7.  Handoff is permitted only when ownership transfer is materially
    required.
8.  Financial/evaluation calculations remain deterministic services.
9.  Large intermediate results are stored as artifacts and passed by
    reference.
10. One canonical RunContext/RunProvenance binds each governed run.
11. Independent specialist branches may run in parallel within explicit
    limits.
12. Every agent/tool/handoff/artifact/memory operation is traceable to
    run_id.

## Agent qualification

Keep as Agent: - hypothesis generation - investigative reasoning -
challenge/review - synthesis - interpretation - next-hypothesis
reasoning

Keep as deterministic service/tool: - data access - calculation -
filtering - backtest - WFO - forward test - metrics - risk - comparison
mathematics - data trust - persistence - evidence serialization

## Initial specialist candidates

No fixed count is mandated.

Candidates: - Hypothesis Specialist - Learning/Challenge Specialist -
Interpretation Specialist

Planner, Candidate Builder, Evaluation Coordinator and Comparator may
remain workflow/deterministic components unless evidence demonstrates
independent reasoning value.

A new runtime agent requires: - distinct capability - distinct
contract - explicit tools/permissions - measurable benefit - acceptable
coordination cost - owner-approved change record where required

## Research Loop mapping

Logical responsibilities remain: Research Controller,
Question/Hypothesis Manager, Research Planner, Candidate Builder,
Evaluation Coordinator, Comparator/Robustness Evaluator, Learning
Synthesizer, Next-Hypothesis Generator.

They are not eight mandatory agents.

## Memory

Run Context = execution state. Episodic Memory = immutable research
evidence. Semantic Memory = curated, versioned knowledge.

## Failure model

Provider failure, malformed output, missing evidence, low Data Trust,
timeout, budget exhaustion, policy violation, duplicate operation or
unavailable specialist must safely fail, degrade or retry under
idempotency controls.

## Complexity budget

-   one Orchestrator
-   two agent levels maximum initially
-   no autonomous spawning
-   bounded specialist count
-   bounded parallelism
-   one RunContext
-   one trace fabric
-   one artifact protocol
-   one policy authority

## Final decision

**KEEP MULTI-AGENT WITH CONTROLLED TOPOLOGY.**

The architecture preserves specialist reasoning, delegation, parallel
research, handoff, agent-as-tool, memory, external intelligence and
continuous learning as capabilities without requiring all of them to
become runtime components immediately.


---

## Binding additive product capability amendment — 2026-10-02

The target topology remains Human Authority → Thin Governor/Policy Gate → Central Orchestrator/AI Brain → bounded specialist capabilities and deterministic services → evidence/artifact/memory/version → advisory result → human approval. No existing capability is removed or downgraded.

### Additional specialist capabilities (logical capabilities first; runtime agents only when justified)
- **External Source & Filing Intelligence:** source discovery/registry, scheduled/event-driven ingestion, source provenance, document versioning, corroboration/conflict handling and coverage/freshness reporting.
- **Fundamental Intelligence:** point-in-time company dossier assembly from official filings, financial statements, audit information and corroborated secondary context; no invented or silently reconciled values.
- **Market-Reference Interpreter:** initial TabloKhani-style board interpretation benchmark, then governed extension using multi-source evidence, regime, fundamentals, research results and measured Golden Set improvements.
- **Product Intelligence & Improvement:** privacy-safe product-quality/UX signals, recurring system audit, improvement hypothesis generation and evaluation proposals.
- **Prediction Feedback & Calibration:** timestamped prediction registration, matured outcomes, error decomposition, calibration/drift analysis and research proposals.

These are capabilities, not a mandate to instantiate five new LLM agents. Existing specialist admission rules remain: distinct capability/contract, allowed tools, measurable benefit, acceptable coordination cost, owner-approved record where required.

### Continuous monitoring architecture
Use a bounded source registry and job/event scheduler. Every source/monitor has declared coverage, refresh policy, permissions, rate/budget ceilings, retries/idempotency, freshness objective, last-success timestamp, failure state and kill switch. The platform must expose coverage gaps; it must never claim to monitor “the entire web” without a defined and evidenced coverage boundary.

### Fundamental dossier and evidence flow
External source content is ingested as untrusted data. Extraction is separated from interpretation. Financial facts retain source, publication time, effective reporting period, currency/unit, filing/version/restatement status and point-in-time eligibility. Contradictions remain explicit until deterministic reconciliation rules or human review resolve them. AI reasoning receives evidence references, not authority to change source facts.

### Whole-product improvement loop
Product Intelligence may evaluate software/UX/operations and market/financial capabilities, but evaluation method must match the domain. Backtest/forward test apply to financial hypotheses, not to arbitrary UI or software components. Software changes use regression, performance, reliability, security and UX evaluation as appropriate. Recommendations remain advisory and cannot mutate production or release software.

### G2 and external-source boundaries
G2 still blocks real-data AI-2 until independent validation and owner acceptance. Source ingestion may not bypass existing external-intelligence gates, Two-Key Rule, untrusted-content isolation, provenance, or human approval. No autonomous trading, broker orders, production mutation, self-escalation, or self-modifying production logic is authorized.
