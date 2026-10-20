# B-1 OWNER DECISION MATRIX — 2026-10-20 (Consolidated Governance Directive §3)

Status: prepared under the Consolidated Governance Directive — B-1, R2, G2
Procedure, and Independent Review (§3). This matrix is a DECISION AID for the
owner: it records the proposed decisions as RECOMMENDATIONS ONLY. **No decision
below is an owner decision.** Absence of response is not approval. G2 remains
`NOT_PASSED`; `AI2_ENABLED=0` (`config.py:109`); `live_verified=false`
(`config.py:270`); LLM NOT EXECUTED; no push. Self-approval is void.

Companion documents: `OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` (exact
decision statements, condition dispositions, outcome consequences, owner
fill-in template), `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` (source-backed
conditions), `OWNER_ACCEPTANCE_PACKAGE_2026-10-18.md` (per-block detail +
2026-10-20 currency addendum), `G2_REVIEW_PACKAGE_2026-10-20.md` (reviewer
evidence binding).

Fresh verification basis (this cycle, 2026-10-20, at HEAD `d380ee5`): all five
blocks' 10 commits re-verified ancestors of HEAD (evidence
`docs/governance/evidence/raw/2026-10-20_consolidated_baseline/06_ancestry.txt`);
full battery re-executed **621 passed / 2 pre-existing warnings / 77.94s**,
18/18 components exit 0, per-block focused counts 44/58/24/25/13/51/58
(`raw/2026-10-20_consol_precommit/`, SHA-256 manifest 20/20 OK); gates
re-verified in code (`08_gates_source.txt`); amendment corpus 7/7 byte-identical
(`09_corpus_integrity.txt`). The historical per-block audit chains are preserved
verbatim at `docs/governance/evidence/2026-10-18_*_independent_audit.md`.

## Matrix — all five pre-G2 blocks

| Field | P0-AMD-1 | AI1-GC | AI2-F | AI-MA-C | AI3-M |
|---|---|---|---|---|---|
| **Block ID + authoritative source** | P0-AMD-1 (amendment import + P0 addendum contracts); source: owner amendment corpus `00`–`06` + `02:131-139`; requirement directive P0-AMD-1 | AI1-GC (AI-1 Central Brain gap closure); source: `02:39-42` nouns + `03` (AI governance boundaries) | AI2-F (AI-2 required-items layer); source: `02:44-53` eight required items | AI-MA-C (multi-agent runtime contracts); source: `02:55-81` (AI-MA-1..6) + `02:81` prohibition set + `03` attributes | AI3-M (Research Memory); source: `02:83-85` + `02:142/159/198` + `06 §7` + D-AI-28 |
| **Commits** | `357f4b6` + `b3cbeb1` (P0-AMD-1a) | `ea3277e` + `2f86c4a` (AI1-GCa) | `6aeeaa2` + `17ef611` (AI2-Fa) | `e385415` + `aa86c3c` (AI-MA-Ca) | `80585c8` + `37c529d` (AI3-Ma) |
| **Delivered scope (evidence paths)** | 6 additive P0 contract modules: `source_registry.py`, `evidence.py`, `fundamental_dossier.py`, `monitoring.py`, `product_audit.py`, `prediction.py` + byte-identical corpus import (`docs/governance/amendment_sources_2026-10-02/`, 7/7 identical vs owner upload) | 4 additive modules: `run_governance.py`, `memory_interfaces.py`, `opportunity.py`, `monitoring_governance.py`; gap matrix `docs/active/AI1_GAP_CLOSURE_SCOPE_AND_TRACEABILITY.md` | 1 additive module `ai2_governance.py` enforcing all eight `02:44-53` items; record `docs/active/AI2F_EXECUTION_RECORD.md` | 1 additive module `multi_agent.py` (AI-MA-1..6, contracts only; runtime NOT instantiated); record `docs/active/AIMA_C_EXECUTION_RECORD.md` | 1 additive module `research_memory.py` (episodic immutable archive + curated/versioned semantic lessons + PIT views); record `docs/active/AI3M_EXECUTION_RECORD.md` |
| **Tests executed (current-run evidence)** | 44 focused, exit 0 (this cycle, `raw/2026-10-20_consol_precommit/pytest_p0amd1.txt`) | 58 focused, exit 0 (`pytest_ai1gc.txt`) | 24 focused, exit 0 (`pytest_ai2f.txt`) | 25 focused, exit 0 (`pytest_aimac.txt`) | 13 focused, exit 0 (`pytest_ai3m.txt`) |
| **Independent audits (results + refs)** | `2026-10-18_P0AMD1_independent_audit.md`: FAIL (narrow, P0AMD1-01..05) → remediation `b3cbeb1` → PASS; history preserved | `2026-10-18_AI1GC_independent_audit.md`: FAIL (narrow, AI1GC-01..06) → docs-only `2f86c4a` → PASS; history preserved | `2026-10-18_AI2F_independent_audit.md`: FAIL (narrow, AI2F-01..06) → `17ef611` → PASS; AI2F-06 residual fixed in `e385415`; history preserved | `2026-10-18_AIMAC_independent_audit.md`: PASS with dispositions in `aa86c3c` | `2026-10-18_AI3M_independent_audit.md`: PASS (AI3M-01 fixed in `37c529d`; AI3M-02/03 INFO disclosed); history preserved |
| **Known gaps / unverified claims / dependencies** | Runtime integration of all six schemas does NOT exist (no scheduler/ingestion/telemetry); deployment constants (retry 10 / timeout 3600s / concurrency 8 / 60 runs/h; rate caps 10,000/min) are engineering-authority values, never owner-ratified; residual notes: `pit_eligible` self-declared, `source_tier` free string, `publication>retrieval` neutralized not rejected, mid-horizon attach permitted, `evaluate()` ordering (acceptance package Item 1; register review D-2) | Enforcement-by-invocation: no runtime caller of the provenance/autonomy gates; opportunity evidence ids lack referential integrity to the evidence layer; `MemoryOperationKind` dead schema (AI1GC-06); monitoring cycle does not check `sources_attempted` vs `spec.target_source_ids`; budget ceilings inherited not cycle-enforced (Item 2) | Runtime consumption BLOCKED (post-G2 by design, matrix §C2); three residual observations verified STILL PRESENT in code this cycle (see `AI2F_AI3M_DECISION_RECORD_2026-10-20.md` §2: `governed_acceptance` :393-423 no `record.status`; record-level APPROVED without approver field; unknown trust strings rank −1 vs `config.py:191-196` folding) | No runtime exists (D-AI-41 respected by design); DEGRADED-exchange docstring line owed; dead code `_shape` + `MAX_HIERARCHY_DEPTH`; `isolate_failure` ignores `failure_behavior` (structural containment only); partial failure-model mapping (Item 4) | Persistence = owner deployment decision (D1–D7 brief; evaluation prefers SQLite WAL + JSONL as PREFERRED CANDIDATE); live feeding of episodic artifacts G2-gated; `lessons_active_at` one-sided conservative PIT semantics (AI3M-02 INFO); memory acceptance beyond contracts NOT PROVEN (D-AI-41) |
| **Proposed owner decision (RECOMMENDATION ONLY)** | **ACCEPT CONDITIONALLY** (contract class) — conditional acceptance for continued bounded contract work, documentation, and audit preparation; NOT full product acceptance, NOT operational readiness, NOT G2 approval | Same | **ACCEPT CONDITIONALLY** with the two recorded conditions (a)/(b) below | Same (P0-AMD-1-style) | **ACCEPT CONDITIONALLY** with the persistence decision explicitly routed to the owner |
| **Exact acceptance conditions + responsible authority + evidence to close** | Condition: residual notes scheduled into the next contract hardening pass (D-2, class 3 — engineering); numeric ceilings ratified/amended by the owner at runtime-integration time (authority: owner; evidence: owner ratification record) | Condition: runtime integration must CALL the gates (binding requirement carried into AI-4/AI-5 contracts — engineering; evidence: future runtime block tests) | **(a)** three residual observations dispositioned in the next AI-2 contract touch — class 3 per register review D-1, one-commit remediable; per the governing directive §7 the disposal now additionally requires explicit owner authorization (absent today); evidence to close: remediation commit + targeted tests + independent re-audit + fresh at-commit battery. **(b)** standing boundary: nothing implies AI-2 runtime readiness — disposed by construction while gates hold (evidence: `config.py:109`/:270 captures, fresh) | Condition: DEGRADED-exchange docstring line + dead-code removal folded into the next AI-MA touch (class 2/3 — engineering) | Condition: owner persistence decision record selecting the approach (or deferring with a date), ratifying D3 immutability class (M3 trigger-level recommended), ratifying/amending D4/D6 — authority: owner; evidence: owner decision record; adapter implementation lands post-G2 |
| **Scope the decision permits** | Contract/documentation work + audit preparation ONLY. Does NOT authorize runtime integration, wiring, scheduling, or any gated capability | Same | Contract/documentation work ONLY; condition (a) disposal (one contract commit in `ai2_governance.py` + tests) ONLY if the owner explicitly authorizes it under directive §7. Does NOT authorize runtime consumption of the layer by `ai2_service.py` (post-G2) | Same as P0-AMD-1 | Contract/documentation work ONLY. Does NOT authorize persistence-adapter implementation (post-G2 even after the owner decision), any storage migration, or live feeding |

## What acceptance is NOT (applies to every block)

Contract-class acceptance (per `02:202` pre-G2 work class and D-AI-41 "product
capability is not implementation evidence") does NOT assert: runtime readiness,
operational capability, real-data or live execution, implementation evidence
beyond contracts, or G2 approval. Per the governing directive §1, acceptance
also does NOT authorize publication (push) or activation of any gated
functionality. Every block remains `VERIFIED_PENDING_ACCEPTANCE` in the ledger
until the owner records a decision in
`OWNER_DECISION_PACKAGE_B1_R2_2026-10-20.md` §4 (the owner fill-in template —
the authoritative decision form).

## ADDENDUM 2026-10-20 — owner decision received (recording only; matrix rows remain RECOMMENDATIONS)

An owner decision on B-1 was received 2026-10-20 and is recorded verbatim with
provenance in `OWNER_DECISION_B1_R2_RECORDED_2026-10-20.md` (canonical record;
recording performed this cycle). Effect mapping applied by that record:

- **Decision B-1 = Conditional Evidence Acceptance**: the owner accepts the
  independently reproduced test and documentation evidence ONLY within the
  scope directly supported by the recorded artifacts. It does NOT constitute
  final acceptance of any block whose explicit exit criteria remain unmet,
  does NOT grant production or live-data authorization, and does NOT pass G2.
- **Per-block statuses UNCHANGED** per the decision's own rule: P0-AMD-1,
  AI1-GC, AI2-F, AI-MA-C, AI3-M each retain `VERIFIED_PENDING_ACCEPTANCE`
  (with the recorded conditions for AI2-F (a)/(b) and AI3-M persistence
  routing). No matrix row above is converted into an accepted status; the
  RECOMMENDATION column remains a recommendation; per-block ACCEPT/REJECT/
  DEFER decisions remain open via the §4 template.
- No historical audit result was rewritten. All audit histories (FAIL→
  remediation→PASS chains; G2P-01/G2P-02; E5 = `NOT_VERIFIED`) remain
  verbatim-preserved.
- The decision affirmatively restates: silence, missing fields, test success,
  and programmer recommendations do not constitute owner approval.

## ADDENDUM 2026-10-20 (CONSOL-GOV-4 cycle) — B-1 reaffirmed and sharpened by the second owner decision; all statuses UNCHANGED

A second owner decision on 2026-10-20 (trace `1a15b105a0662765`; recorded
verbatim in `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §1.2/§1.3) restates
B-1 with sharpened wording: "Each of the five B-1 blocks must remain
`VERIFIED_PENDING_ACCEPTANCE` or `BLOCKED` until its own documented exit
criteria and required authority are satisfied. No block is accepted or
rejected by implication."

- **Per-block statuses UNCHANGED** (all five rows above keep
  `VERIFIED_PENDING_ACCEPTANCE` with their recorded conditions); the
  RECOMMENDATION column remains a recommendation; the §4 template remains
  the per-block decision instrument.
- The new wording is consistent with the first decision recorded above
  (same rule; adds the no-implication clause and names the two retained
  statuses) — recorded as a consistency analysis, not a rewrite, in
  `OWNER_DECISIONS_CONSOLGOV4_2026-10-20.md` §2.
- No historical audit result rewritten; E5 remains `NOT_VERIFIED`;
  `G2 = NOT_PASSED`.
