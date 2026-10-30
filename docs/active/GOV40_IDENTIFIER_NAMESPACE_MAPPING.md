# CONSOL-GOV-40 — Governance Identifier Reconciliation and Legacy-ID Mapping

**Date:** 2026-10-30 (Asia/Tehran) · **Baseline HEAD:** `dec77f25072439c07bd255ec132936f482c3a892` (tree `e35a5932…`) · **Directive:** CONSOL-GOV-40 Phase 2

Purpose: resolve the R3/R4 identifier collisions between two namespaces that both use bare "R3"/"R4", WITHOUT changing historical meaning, WITHOUT rewriting any sealed record, and WITHOUT renaming any machine-pinned key.

## 1. Finding — the collision, stated exactly

CONSOL-GOV-39 deliverables reuse the same bare identifiers for two different namespaces:

| Bare ID | Meaning in the P5/P6 namespace (requirement R-IDs) | Meaning in the blocker/owner-act namespace |
|---|---|---|
| R3 | Explainable opportunity clusters with formal class definitions and the five explanation questions (06 §6) — implemented and evidence-verified | Live-provider credential provisioning for TSETMC/BRSAPI — owner act, NOT granted |
| R4 | Operational alert coverage: the nine corpus alert classes as governed amendment-class contracts (02:148–149) — the gap closed this GOV-39 cycle at the contract layer | Real-data AI-2 enablement (`AI2_ENABLED=1` outside tests) — owner act, NOT granted |

Ambiguity already materialized inside one sentence: `P5P6_ALERT_LIFECYCLE_SCOPE_DERIVATION.md` R12 (live-data alerting, externally blocked) cites "R3 (live-credential provisioning)" while R3 in the same table is the explainable-clusters requirement — two namespaces in one document.

## 2. Disposition rules applied (per directive)

1. **Original P5/P6 criterion identifiers R1–R12 are PRESERVED** — they are the authoritative requirement namespace for the P5/P6 acceptance matrix and are not renamed.
2. **Owner actions and operational blockers move to a distinct, documented namespace** with self-describing IDs:
   - `OA-AI2-LIVE-CREDENTIALS` (formerly blocker "R3" — live-provider credential provisioning)
   - `OA-AI2-ENABLEMENT` (formerly blocker "R4" — real-data AI-2 enablement)
   - `OA-ALERT-OPERATIONS` (the operational-alert cadence/delivery owner decision formerly tracked only as "D-AI-30 execution"; the formal register decision ID D-AI-30 itself is unchanged and stays)
3. **Historical reports and records stay byte-unchanged** (§4 lists the affected historical loci; the mapping below makes every old reference traceable).
4. **Machine-pinned strings are not renamed** (§3 result of the dependency probe); where a pinned string is domain-ambiguous, the alias is recorded as documentation only.
5. Only current, forward-looking registers/indexes are updated to the new namespace; the legacy table is the permanent cross-reference.

## 3. Namespace inventory and machine-key dependency probe (executed this cycle, before any change)

Five distinct namespaces use the bare `R<number>` form. None of them is a machine key in the contract/test layer except where explicitly noted:

| Namespace | Domain | Authoritative definition locus | R3 means | R4 means | Machine key? | Disposition |
|---|---|---|---|---|---|---|
| NS-A — P5/P6 requirement IDs | P5/P6 acceptance criteria (12 requirements) | `docs/active/P5P6_ALERT_LIFECYCLE_SCOPE_DERIVATION.md` §2 table (committed `dec77f2`) | Explainable clusters (06 §6) | Governed alert contract (02:148–149) | No — document table rows only; `rg` over `backend/app/domain/governed_alerts.py` and `backend/tests/test_p5p6_governed_alerts.py` → 0 hits | **PRESERVED verbatim** |
| NS-B — blocker / owner-act IDs | AI-2 integration prerequisites | `docs/active/AI2_G2_REVIEWER_CHECKLIST.md:169–170` (§8 table, committed corpus); propagated to registers | Live-provider credential provisioning | `AI2_ENABLED=1` outside tests | No — checklist table row + register prose only | **RETIRED → `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT`** in all forward-looking registers; historical loci byte-unchanged, mapped in §5 |
| NS-C — AI-1/AI-6 intake requirement IDs | External-intelligence untrusted-content boundary (15 requirements) | `backend/app/domain/external_intelligence.py` source comments (`:280` "R3 content-instruction separation", `:653` "R4 … gate functions"); `backend/tests/test_ai6_external_intelligence.py:282,517` | Content-instruction separation | Explicit trust-boundary enforcement | No — comments only (verified: no assertion, dict key, or field name carries them) | PRESERVED verbatim (different domain, documented here to prevent future confusion) |
| NS-D — G2 battery criterion text | G2 acceptance battery check descriptions | `scripts/g2_acceptance_battery.py:548` "corpus supplied + re-baselined (R1)", `:563` "R2 review procedure approved (v1.0; delegated D-16-1)" | (unnumbered beyond R1/R2 in this text) | — | **YES — pinned check-description strings inside the acceptance harness output**; renaming would churn recorded harness outputs for zero governance gain | **NOT RENAMED (contractually pinned); display alias recorded here: these are NS-D criterion labels, unrelated to NS-A/NS-B R3/R4** |
| NS-E — 2026-10-19 owner-directive artifact IDs | Companion artifacts of the 2026-10-19 owner directive (R1–R7) | `docs/governance/PROJECT_EXECUTION_STATE.md:129`; `docs/CHANGELOG.md:325–331` | `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` | `AI4_SANDBOX_LIMITS_PROPOSAL.md` | No — dated historical directive prose | PRESERVED verbatim (sealed directive history) |

Probe method (executed before any rename): `git grep -nE '\bR3\b|\bR4\b'` over the tracked tree, plus `rg` over the new alert module and its tests. Result: every occurrence is either (a) documentation prose / table rows, (b) source comments, or (c) the two NS-D pinned harness strings. No dict key, JSON field, pydantic field, evaluator tag, refusal code, DB column, or test ID depends on NS-A or NS-B "R3"/"R4". Therefore the OA-* introduction changes zero machine behavior.

## 4. Historical loci that retain the bare NS-B identifiers (byte-unchanged, mapped here)

Every locus below keeps its original text forever; this table is the traceability link. The right-hand column is the unambiguous modern reading.

| Historical locus (byte-unchanged) | Bare ID used | Modern unambiguous ID |
|---|---|---|
| `docs/active/AI2_G2_REVIEWER_CHECKLIST.md:169` (§8) | R3 | `OA-AI2-LIVE-CREDENTIALS` |
| `docs/active/AI2_G2_REVIEWER_CHECKLIST.md:170` (§8) | R4 | `OA-AI2-ENABLEMENT` |
| `docs/active/AI2F_AI3M_DECISION_RECORD_2026-10-20.md:18`; `AI2F_CONDITION_A_DECISION_BRIEF_2026-10-20.md:24,164` ("G2 + owner acceptance (checklist R3/R4)") | R3/R4 | `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT` |
| `download/GOV39_DECISION_BLOCKER_REGISTER.md` §1 row "R3 / R4", §2 rows R3, R4 | R3, R4 | `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT` |
| `download/GOV39_P5P6_EVIDENCE_MATRIX.md` R12 row "externally blocked … R3 (live-credential provisioning)" and Part B "AI-2 real-data (R3+R4…)" | R3, R4 (NS-B inside an NS-A document) | `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT` |
| `download/00_GOV39_FINAL_REPORT_FA.md` lines 21, 41–42, 67 (بلاک خارجی R12; اقلام R3/R4) | R3, R4 (NS-B) | `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT` |
| `docs/active/P5P6_ALERT_LIFECYCLE_SCOPE_DERIVATION.md:34` (R12 evidence cell: "R3 (live-credential provisioning — owner act)") | R3 (NS-B inside NS-A table) | `OA-AI2-LIVE-CREDENTIALS` |
| `docs/CHANGELOG.md` GOV-39 entry (line 6: "externally blocked (R3, R12)"; line 16: "R3 (live-credential provisioning) and R4 (AI2_ENABLED=1 outside tests)") | R3, R4 (NS-B) | `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT` |
| `docs/STATUS.md` GOV-37 row ("R3/R4 remain separate owner acts") | R3/R4 (NS-B) | `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT` |
| `docs/governance/PROJECT_EXECUTION_STATE.md` §2w line 241 ("R12 … externally blocked (R3)") and §3 line 249 ("R3/R4 owner acts") | R3, R4 (NS-B) | `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT` |
| `download/GOV39_P5P6_EVIDENCE_MATRIX.md` Part B "R11 cadence/delivery integration (D-AI-30 owner decision)" | (decision tracked under D-AI-30) | execution action now `OA-ALERT-OPERATIONS` (decision ID D-AI-30 unchanged) |

NS-A loci that keep R3 = explainable clusters and R4 = alert contract verbatim: `docs/active/P5P6_ALERT_LIFECYCLE_SCOPE_DERIVATION.md` §2 rows R3/R4; `download/GOV39_P5P6_EVIDENCE_MATRIX.md` Part A rows R3/R4; `download/00_GOV39_FINAL_REPORT_FA.md` lines 18–19; `docs/CHANGELOG.md` GOV-39 entry ("the one genuine gap (R4)…"); `docs/governance/PROJECT_EXECUTION_STATE.md` §2w ("four-way opportunity objects/fields/clusters R1–R3 … R4 (governed amendment-class alert contract …) = the single locally executable gap").

## 5. Legacy-ID mapping table (canonical cross-reference)

| Legacy bare ID (namespace) | New official ID | Status | One-line definition |
|---|---|---|---|
| R3 (NS-B — blocker/owner act) | **`OA-AI2-LIVE-CREDENTIALS`** | ACTIVE as owner-act identifier; OPEN | Provision live-provider credentials (TSETMC/BRSAPI) in an owner-controlled environment and authorize the live-validation run; until satisfied `verified=False` and `execution_mode` stay fail-closed |
| R4 (NS-B — blocker/owner act) | **`OA-AI2-ENABLEMENT`** | ACTIVE as owner-act identifier; OPEN | Enable `AI2_ENABLED=1` outside tests for any use of AI-2 output beyond advisory; requires the runtime gate's convened-commit binding to be satisfied at the running commit (or a fresh owner-recorded gate-state transition) |
| D-AI-30 (formal register ID — unchanged) + its execution actions | **`OA-ALERT-OPERATIONS`** | PENDING OWNER DECISION | Owner-approved operational-alert cadence/budget/delivery configuration (see `GOV40_DAI30_OWNER_DECISION_PACKET.md`, marked PENDING OWNER DECISION); notifier/ws_hub integration is the follow-on authorized implementation task only after the decision is recorded |
| R1–R12 (NS-A — P5/P6 criteria) | unchanged (R1–R12) | PRESERVED | P5/P6 requirement namespace; R3 = explainable clusters; R4 = governed alert contract (closed `dec77f2`); R11 = `OA-ALERT-OPERATIONS`; R12 externally blocked pending `OA-AI2-LIVE-CREDENTIALS` |
| R1–R15 (NS-C — AI-1/AI-6 intake) | unchanged (R1–R15) | PRESERVED | External-intelligence requirement namespace, comments only |
| R1/R2 in `g2_acceptance_battery.py` (NS-D) | unchanged | PRESERVED (pinned strings) | G2 battery check-description labels |
| R1–R7 (NS-E — 2026-10-19 directive artifacts) | unchanged | PRESERVED (sealed) | Dated owner-directive companion artifacts |
| B5/B6 (release blockers) | unchanged (B5/B6) | PRESERVED | Push/release external blocker — no collision |
| D-AI-29 / D-AI-31 | unchanged | PRESERVED | Formal register decision IDs — no collision |

## 6. Forward-looking registers updated this cycle (complete list)

1. `docs/active/GOV40_BLOCKER_REGISTER_2026-10-30.md` — NEW canonical forward-looking register in the OA-* namespace (supersedes `download/GOV39_DECISION_BLOCKER_REGISTER.md` for future reference only; the GOV-39 file stays as sealed cycle history).
2. `docs/active/GOV40_DAI30_OWNER_DECISION_PACKET.md` — NEW owner decision packet referencing `OA-ALERT-OPERATIONS`; PENDING OWNER DECISION.
3. `docs/active/GOV40_RELEASE_WINDOWS_CI_STATUS_2026-10-30.md` — NEW release/Windows CI status record (B5/B6 namespace unchanged).
4. `docs/active/GOV40_AI2_PREREQUISITE_CHECKLIST.md` — NEW AI-2 prerequisite checklist using `OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT`.
5. `docs/governance/PROJECT_EXECUTION_STATE.md` §3 — additive CURRENCY note added in the working tree per bootstrap policy (untracked file, never staged), pointing to this mapping.
6. `docs/STATUS.md` top row + `docs/CHANGELOG.md` + `docs/active/INDEX.md` — GOV-40 bookkeeping rows in the new namespace.

Nothing else was changed. No historical file was edited, no machine key renamed, no harness string touched.
