# RADAR_BOURSE --- 17-Role Governance Charter

Revision: 2026-09-29 Status: FINAL OWNER-DIRECTED BASELINE

## Fundamental rule

17 governance roles are responsibility/governance lenses, not 17 runtime
LLM agents.

  ----------------------------------------------------------------------------
  \#                      Role                    Final responsibility
  ----------------------- ----------------------- ----------------------------
  1                       Chief Project           Owner authority and
                          Supervisor / Governor   consequential gates

  2                       CTO / Chief System      Architecture
                          Architect               

  3                       Roadmap & PM            Sequencing and dependencies

  4                       Release & Change        Change/release gates
                          Control                 

  5                       Independent Repository  Repository truth
                          Auditor                 

  6                       Evidence & Forensics    Provenance/evidence
                          Auditor                 

  7                       Web Reverse Engineering External/reference analysis
                          & Forensics Lead        

  8                       Reference-System Logic  Workflow comparison
                          Analyst                 

  9                       Data & Market           Data trust
                          Integration Auditor     

  10                      Quant / Financial Logic Quant correctness
                          Auditor                 

  11                      AI Systems Architect /  AI/Multi-Agent boundaries
                          Intelligence Lead       

  12                      Developer Technical     Implementation
                          Director / Agent        
                          Supervisor              

  13                      Windows / DevOps &      Runtime/recovery/resources
                          Environment Owner       

  14                      QA / Validation &       Acceptance
                          Parity Lead             

  15                      Security / Reliability  Security/fail-closed
                          Auditor                 

  16                      Prompt & Context        Prompt/context/version
                          Engineer                integrity

  17                      Technical Documentation Canonical specifications
                          Lead                    
  ----------------------------------------------------------------------------

## Final RACI

Multi-Agent architecture: 1(A), 2/11(R), 5/6/10/15(C)

Research Loop implementation: 1(A for authorization), 12(R),
2/10/11/13(C)

G2: 1(A), 6/14(R), 9/10/15(C)

Runtime Agent admission: 1(A), 11(R), 6/10/14/15(C)

Production promotion: 1(A), 4(R), 6/10/14/15(C)

Provenance/prompt/model versioning: 1(A), 16/17(R), 6/11(C)

## Agent-count rule

Role count must never determine agent count.

A runtime agent is admitted independently by capability, contract,
authority, evidence and measured value.

## Independent reproduction

Consequential/high-risk Research Loop outputs require independent
reproduction/validation.


---

## Additive responsibility mapping — 2026-10-02

The 17 governance roles remain responsibility lenses, not a fixed runtime-agent count. The following work is added to existing responsibilities; no new mandatory runtime agent is implied.

- **Data & Market Integration Auditor (Role 9):** source registry, company identity, source freshness/coverage, filing provenance, point-in-time data, unit/currency/restatement handling and unresolved-source conflicts.
- **Quant / Financial Logic Auditor (Role 10):** fundamental-data PIT correctness, regime-sliced tests, prediction outcome maturity, holdout isolation, calibration, multiple-testing and risk-adjusted evaluation.
- **AI Systems Architect / Intelligence Lead (Role 11):** market/web monitoring control plane, fundamental intelligence flow, Product Intelligence and prediction-feedback contracts.
- **Windows / DevOps & Environment Owner (Role 13):** scheduler operations, rate/budget ceilings, idempotency, retry policy, monitoring health, recovery, observability and kill switch.
- **QA / Validation & Parity Lead (Role 14):** Golden Set for board interpretation, source-conflict tests, filing/restatement tests, monitoring failure tests, product audit acceptance and independent reproduction.
- **Security / Reliability Auditor (Role 15):** external content isolation, prompt injection, source access policy, privacy-safe product telemetry, tool boundaries and fail-closed behavior.
- **Prompt & Context Engineer (Role 16):** versioned source-grounded prompts, citation completeness, prediction preregistration and model/prompt drift evaluation.
- **Technical Documentation Lead (Role 17):** maintain capability contracts, source coverage claims, audit cadence, decision register and acceptance evidence without upgrading status beyond proof.

Owner authority and change-control responsibilities remain unchanged. All product-improvement proposals and financial candidates remain advisory until their appropriate evaluation and approval gates are passed.
