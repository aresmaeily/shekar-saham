# Amendment Corpus Import & Governance Audit — 2026-10-18

Mission: "Import the Owner-Supplied Governance Amendments, Verify Their Integrity, and Resume Roadmap Execution" (Steps A–C of the owner mandate; Step D derivation is published separately in `docs/active/P0_AMENDMENT_CONTRACTS_SCOPE_DERIVATION_REPORT.md`).

Baseline verified fresh this session before any action: HEAD `42587fa` on `main` (AI3-A), tracked tree clean, untracked = 4 bootstrap governance paths preserved, stash 0, single worktree, live `git ls-remote origin` exit 0 → `origin/main = c1984e7`, ahead 9 / behind 0.

## 1. Step A — Source inventory (owner-supplied files)

Source location: `/home/z/my-project/upload/` (owner upload channel; the files were NOT assumed to be anywhere else). Seven files supplied — the five mandated filenames **plus two additional owner-supplied originals** (`00_*`, `06_*`), which are part of the same amendment bundle and were imported and documented with identical treatment. Raw manifest with hashes: `docs/governance/evidence/raw/2026-10-18_amendment_import/import_manifest.txt`.

| File | Bytes | SHA-256 (source == destination) |
|---|---|---|
| `00_OWNER_ROADMAP_DECISION_CURRENT_2026-10-02.md` | 5618 | `be2f08366666320c4e0b16ac9d2d9db0c48449b47c2d7f637b8b299e8e68bca0` |
| `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` | 14806 | `1c44ebe114d42fbe06aeb06db43aeb50b4a8766017800e53a426990878004c8f` |
| `02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE_CURRENT_2026-10-02.md` | 6925 | `80b09728e5b7a11b041ccc31e09feca6065f9da5fa7377e54dcdd620fd65cf3b` |
| `03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md` | 4975 | `e824e1ef2e068acb0f2d138644993d3a5b3a7d955c1a44df73546e6babd727a0` |
| `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md` | 5284 | `61c413b8c6ebcc5499aaefd3609045fa9b4726a1b32f20344d04dc8b9c3d1176` |
| `05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md` | 8414 | `2cdb57efd02e8c26860a521199aaa0d365e03e77424c17637526a0dfacaa71a7` |
| `06_PRODUCT_CAPABILITY_CHARTER_CONTINUOUS_INTELLIGENCE_2026-10-02.md` | 10299 | `2bfbbf05065e303d2c64836268b489f1e1ad7c06d3ecb1f8af3c36fa5f3e5080` |

All seven readable and non-empty. All five mandated filenames present. No duplicates, no name collisions with existing repository files (the destination directory did not exist before this mission — prior sessions verified `ls` exit 2, most recently 2026-10-18 earlier this day).

## 2. Step B — Import integrity verification

Destination: `docs/governance/amendment_sources_2026-10-02/`. Copies made with `cp` (byte copy; no editor, no normalization, no reformatting, no combining, no metadata injection). Independent verification of each destination copy: SHA-256 recomputed and compared to source, byte sizes compared, and `cmp -s` byte-identity — **7/7 IDENTICAL, 0 mismatches** (`IMPORT_FAIL=0` in the manifest). The five mandated files are present at their exact expected paths and non-empty.

Integrity acceptance criterion: **MET**. No byte-preservation constraint was encountered; nothing was altered, reconstructed, or substituted. The originals in `/home/z/my-project/upload/` remain untouched as the owner's source copies.

## 3. Step C — Corpus audit

All seven files were read in full from the repository copies. Document identity: files `00`, `02-roadmap`, `02-architecture`, `03`, `04`, `05` each carry a base revision `2026-09-29` ("FINAL OWNER-DIRECTED BASELINE/ARCHITECTURE/GOVERNANCE") followed by a "Binding additive … amendment — 2026-10-02" section; file `06` is wholly dated `2026-10-02` ("OWNER-DIRECTED PRODUCT REQUIREMENTS; IMPLEMENTATION NOT PROVEN"). The corpus is internally consistent: the additive sections repeatedly preserve the 2026-09-29 baseline and all gates.

### 3.1 Binding roadmap revision and dependency graph

The binding execution roadmap is `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` ("Final Dependency-First Execution Roadmap", Revision 2026-09-29 + additive 2026-10-02). Its dependency graph (§Dependency graph, lines 7–8):

`P0-C → P0-V → P1 → P2 → P3 → G2 → P4/P5/P6 → AI-1 → AI-2 → AI-MA → AI-3 → AI-4 → AI-5 → AI-6 → AI-7`

with the gate clause (lines 10–11): "G2 blocks all real-data AI-2 execution until formally passed. Design, contracts, paper/synthetic tests and dry-runs may proceed before G2." and the pre-G2 authorization boundary (additive §Gates preserved, line 202): "Before G2, only bounded design, schema work, source-registry design, synthetic/paper tests and safe dry-run work are allowed under existing policy."

The `00` file (§Final execution spine) gives the same spine with block titles, and (§Work that may proceed in parallel) explicitly authorizes parallel pre-G2 work: "Provenance contracts, deterministic evaluation evidence, repository/test baseline, specialist contracts and observability design may proceed concurrently where they have no shared lifecycle dependency."

### 3.2 Precedence rules — as stated in the documents (none invented)

1. **Additive supersession, explicitly scoped** — `00` §Additive owner direction: "The 2026-09-29 historical records remain unchanged; the 2026-10-02 amendment supersedes only the current product-scope omissions described above" (line 112). `02` additive preamble: "It does not remove or downgrade any earlier requirement, claim implementation, waive G2, or authorize production mutation" (line 120).
2. **Decision-register continuity** — `05` D-AI-40: "D-AI-01 through D-AI-31 remain in force"; D-AI-26 re-affirms the G2 gate; D-AI-41: "Adding these requirements to the roadmap does not upgrade implementation status."
3. **Repository source order** — `CLAUDE.md` §Authoritative sources lists the amendment corpus as authoritative source #6 and defines its expected location and the five `0[2-5]_*` filenames (line 13). The corpus is owner-direct text; where it defines scope that in-repo records could not (the exact gap recorded in `docs/active/AI3_SCOPE_DERIVATION_AND_BLOCKER_RECORD.md`), the corpus is authoritative. No conflict with sources #1–#5 was found (§3.4).
4. **Engineering authority** — `05` §Engineering authority: engineering may choose modules, package layout, schemas, test framework and API contracts provided D-AI-15…D-AI-31 are respected; owner approval remains required for architecture-boundary changes, autonomy-level changes, production mutation, live integration, consequential permissions, G2 pass, fixed agent hierarchy changes.

### 3.3 Material findings (each with source)

| # | Finding | Source |
|---|---|---|
| F1 | The official AI-3 definition now exists in-repo: "AI-3 --- Research Memory: Episodic immutable run artifacts plus curated/versioned semantic memory." The AI3-A blocker (class B, missing authoritative definition) is **resolved at the definition level only**; AI-3 acceptance remains governed by the completion rule and sits after AI-MA in the graph. | `02` §AI-3 (lines 83–85); `00` §Completion rule |
| F2 | G2 status is **unchanged** by this import: "Governance G2 is VERIFIED. Runtime G2 is NOT YET IMPLEMENTED" and it "blocks all real-data AI-2 runs until independent validation and owner acceptance." Importing governance files is not G2 evidence. | `03` §G2; mission §5 |
| F3 | The G2 RACI is defined: owner Accountable; roles 6 (Evidence & Forensics Auditor) and 14 (QA/Validation & Parity Lead) Responsible; 9/10/15 Consulted — a formal human gate. The agent-side handoff (`AI2_G2_READINESS_EVIDENCE_PACKAGE.md`, `AI2_G2_REVIEWER_CHECKLIST.md`) is reviewer-ready; execution of G2 remains owner-side. | `04` §Final RACI; `02` §G2 |
| F4 | The corpus defines new **P0-level contract obligations** (7 groups: source registry/tiers; identity/corporate-action/filing/PIT semantics; evidence item schema; fundamental dossier schema with 3-way distinction; monitoring job identity; product audit charter/telemetry/proposal contract; prediction registry + outcome-maturity rules). None of these exist in the repository yet. | `02` additive §P0 (lines 131–139); `06` §3, §4, §7, §8, §9 |
| F5 | AI-2 roadmap requirements vs current scaffold: immutable-run-identity/provenance partially implemented (`AI2Provenance`: input snapshot SHA-256, prompt SHA-256, provider/gate fields, timestamp); **not** implemented: run identity as first-class field, budget/time/iteration limits, evidence artifacts, duplicate detection, recovery, invalidation, human-approval state. The scaffold's own docstring anticipated corpus supersession; the corpus does not define a conflicting request schema, so existing bounds stand. | `02` §AI-2 (lines 44–53); `backend/app/services/ai2_service.py` (AI2Request/AI2Provenance) |
| F6 | AI-1 components exist from the P3.38–P3.41/P3.81–89 series (intelligence core, market intelligence, filter intelligence, provider adapter/transport) but no in-repo record maps them to the corpus AI-1 block ("Observer, interpreter, regime, opportunity, filter intelligence, risk context, memory interfaces and governed orchestration"); the additive monitoring scope (AI-1/AI-5) depends on the F4 source-registry and monitoring contracts. | `02` §AI-1 + additive §AI-1/AI-5; `docs/active/PRODUCT_ROADMAP_LOCK.md` |
| F7 | The standing P3.60 gate is "No **Unauthorized** Feature". The corpus is owner authorization for the blocks it defines; P3.60 remains binding for anything outside it. No conflict. | `docs/active/P3.60_ROADMAP_GATE_NO_UNAUTHORIZED_FEATURE_REPORT.md`; `02` additive |
| F8 | `CLAUDE.md` line 13 records the corpus as `NOT_SYNCED` — now stale; reconciliation required (performed in this mission's governance updates; the line's "five files" expectation is met as a subset of the seven supplied). | `CLAUDE.md` §Authoritative sources #6 |
| F9 | In-repo "official next launch phase P3.43 Controlled Alpha Launch (owner-gated)" is a launch/environment axis the corpus does not modify; it remains owner-gated and BLOCKED. | `docs/governance/PROJECT_EXECUTION_STATE.md` §7; `PRODUCT_ROADMAP_LOCK.md` §Numbering Reconciliation |
| F10 | D-AI-41 binds the whole corpus: no capability may be marked IMPLEMENTED/PROVEN because its charter or contracts exist. All new work remains paper/contract-grade until its acceptance evidence exists. | `05` D-AI-41; `06` §11 closing line |

### 3.4 Contradiction check (corpus vs repository)

Checked against: `CLAUDE.md`, `docs/active/ROADMAP.md`, `docs/active/PRODUCT_ROADMAP_LOCK.md`, `docs/governance/PROJECT_EXECUTION_STATE.md`, `docs/STATUS.md`, `docs/CHANGELOG.md`, `docs/active/INDEX.md`, `RADAR_BOURSE_MASTER_HANDOFF.md`, the AI-2/AI-3 records, and the architecture locks. **No unresolved contradiction found.** Reconciliation notes:

- The corpus is additive and explicitly preserves all gates (F2, F10) — consistent with `CLAUDE.md` hard invariants and stop conditions.
- The corpus's "Governance G2 VERIFIED / Runtime G2 NOT YET IMPLEMENTED" wording is consistent with in-repo "G2 NOT_PASSED (runtime, not self-approved)" once the governance/runtime distinction is applied (F2).
- The four-agent delegation model (`.claude/agents`) is a process mechanism; the corpus's 17 roles are governance lenses (D-AI-18) — no conflict.
- The Persian product roadmap `docs/active/ROADMAP.md` (Phases 1–4) describes shipped product scope; the corpus extends target capability without removing anything — no conflict.
- Architecture locks unaffected: new work must be additive contracts + tests, matching the Future Architecture Gate ("Context Builder → Provider Adapter → Structured Result → Safety Gate → Human Approval" — contracts and tests before new behavior). | `docs/architecture/AI_BRAIN_ARCHITECTURE.md` §Future Architecture Gate

### 3.5 Unresolved owner decisions / missing evidence after import

1. **G2 runtime pass** — owner-executed formal gate (RACI per `04`). The evidence package and reviewer checklist are ready at `54626ee`+; G2 remains NOT_PASSED.
2. **Publication (push)** — local main ahead 9 (+ this mission's commit when created); push owner-gated.
3. **P3.43 Controlled Alpha Launch** — owner environment gates (Windows/Electron/browser E2E/live providers/push auth); unchanged.
4. **Live TSETMC/BRSAPI verification** — requires keys + owner-authorized live run; remains `live_verified=false`.
5. Prior owner-decision packet items (`docs/governance/evidence/2026-10-17_TWO_WORKSPACE_RECONCILIATION_OWNER_PACKET.md`) — still PENDING unless superseded by the corpus; the corpus itself is now the owner's freshest direct direction and takes precedence as owner-direct text where it speaks.

## 4. Verdict

Import: **PASS** (7/7 byte-identical, 5/5 mandated files at exact paths). Audit: **PASS** with the findings F1–F10 recorded. Gates after import: unchanged — G2 NOT_PASSED, `AI2_ENABLED` default off, `live_verified=false`, no AI runtime route, LLM NOT EXECUTED, push owner-gated. The blocker that produced `AI3_SCOPE_DERIVATION_AND_BLOCKER_RECORD.md` is resolved by this import; that record is preserved unchanged as history per the owner mandate ("preserve the history of blockers").
