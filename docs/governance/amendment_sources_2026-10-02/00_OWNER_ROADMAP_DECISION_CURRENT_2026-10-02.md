# RADAR_BOURSE --- FINAL OWNER ROADMAP & ARCHITECTURE DECISION

Revision: 2026-09-29 Status: FINAL OWNER-DIRECTED BASELINE

## Final Owner Decision

**KEEP MULTI-AGENT WITH CONTROLLED TOPOLOGY**

Multi-Agent remains a target capability. No desired capability is
removed or downgraded.

The implementation path is:

Human Authority → Thin Governor / Policy Gate → Central Orchestrator /
AI Brain → Bounded Specialist Agents / Deterministic Tools & Services →
Evidence / Artifact / Memory → Advisory Result → Human Approval.

### Binding principles

1.  17 Governance Roles are governance lenses, not 17 runtime LLM
    agents.
2.  Research responsibilities are logical responsibilities, not
    automatically separate agents.
3.  Financial truth and evaluation truth remain deterministic.
4.  Reasoning is delegated to agents only where independent reasoning
    materially adds value.
5.  Peer-to-peer agent communication is not the backbone.
6.  Initial hierarchy depth is two levels: Orchestrator → Specialist.
7.  Specialist agents are bounded, contract-driven and observable.
8.  Agent-as-tool is the default specialist pattern; handoff requires
    justification.
9.  One RunContext / RunProvenance is minted per governed research run.
10. Large intermediate state is exchanged as artifact references.
11. Governor is thin and does not duplicate existing guards or financial
    logic.
12. G2 remains the hard gate for real-data AI-2 execution.
13. Paper/synthetic implementation and dry-run work may proceed before
    G2.
14. LIVE remains unproven until Data Trust and validation are
    demonstrated.
15. External intelligence, proactive autonomy and continuous learning
    remain gated maturity tracks.

## Why this option

It preserves the intended Multi-Agent capability without paying the
coordination cost of a 17-agent or peer-to-peer system before repository
evidence justifies it.

External production systems support this direction: Anthropic uses an
orchestrator-worker pattern with parallel specialized subagents;
Microsoft Magentic-One uses a lead Orchestrator and modular specialists;
OpenAI documents manager + agents-as-tools and handoffs as core
patterns; AWS emphasizes bounded agents, traceability, explicit
contracts, human oversight and controlled parallelism.

## Final execution spine

P0-C Contract Freeze → P0-V Baseline Verification → P1 Real-Data
Vertical Slice → P2 Deterministic Measurement/Evidence → P3 Evaluation
Harness → G2 Independent Validation → AI-1 Central Brain → AI-2 Research
Loop Hardening / MVRL → AI-MA Orchestrator + Specialist Runtime → AI-3
Memory/Learning → AI-4 Governed Generation → AI-5 Proactive Intelligence
→ AI-6 External Intelligence → AI-7 Continuous Learning/Productization

### Work that may proceed in parallel

Provenance contracts, deterministic evaluation evidence, repository/test
baseline, specialist contracts and observability design may proceed
concurrently where they have no shared lifecycle dependency.

## Final architecture requirements

-   Existing Research Loop is reused and hardened; rewrite is not the
    default.
-   `RunContext/RunProvenance` becomes canonical.
-   Existing lifecycle guards remain authoritative.
-   Governor adds a central policy choke point without reimplementing
    those guards.
-   Deterministic engines remain source of financial truth.
-   Multi-Agent runtime is introduced incrementally.
-   No autonomous agent spawning.
-   No unbounded hierarchy.
-   No peer-to-peer global state.
-   No self-modifying production logic.
-   No broker order execution.

## Completion rule

No phase is complete from code presence alone. Acceptance requires
appropriate source, test, runtime, provenance, failure/recovery and
human-approval evidence.

## Owner decision

This document is the **FINAL OWNER-DIRECTED ROADMAP AND ARCHITECTURE
BASELINE** as of 2026-09-29. Historical records remain unchanged.


---

## Additive owner direction — 2026-10-02

The product capability scope is expanded, not reduced. The current baseline must explicitly include:
1. governed continuous market and approved-source web monitoring beyond user prompts;
2. multi-source company disclosures, financial statements and point-in-time fundamental dossiers with verification/conflict reporting;
3. TabloKhani-style market-board interpretation as the initial benchmark, followed by evidence-based improvements that can be shown to exceed the benchmark only through measured evaluation;
4. recurring AI Product Intelligence and whole-product audits, including filter/strategy Backtest/WFO/Forward Test where appropriate and domain-appropriate software, reliability, security and UX tests elsewhere;
5. timestamped prediction-to-outcome feedback, error analysis, calibration and drift review;
6. explicit coverage, freshness, source failure, budget, privacy and kill-switch controls.

These requirements are additive to the 2026-09-29 Multi-Agent and Research Loop decisions. They do not authorize unrestricted crawling, bypass source access restrictions, claim universal web coverage, waive G2, or permit automatic production changes or trading. The 2026-09-29 historical records remain unchanged; the 2026-10-02 amendment supersedes only the current product-scope omissions described above.

**Application status:** this is a prepared governance amendment bundle based on the supplied 2026-09-29 final baseline. It is not a claim that the local repository has been edited, committed, or released. The canonical repository files must be reconciled and updated under repository change control.
