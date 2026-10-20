# AI-6 EXTERNAL INTELLIGENCE — SCOPE DERIVATION AND TRACEABILITY MATRIX

Status: scope derivation published BEFORE implementation (governance precedent
AI1-GC / AI2-F / AI-MA-C / AI3-M / AI-4). Block identifier: **AI-6** (official
roadmap name: "AI-6 --- External Intelligence", `02` line 97). Execution
record will be `docs/active/AI6_EXECUTION_RECORD.md`. This document is the
authorization check; nothing below invents requirements beyond the cited
corpus lines. Owner directive 2026-10-19 (R2) authorizes "the full authorized
pre-G2 AI-6 scope covering untrusted-content boundaries and prompt-injection
isolation" and explicitly states its implementation areas are "to verify
against the official AI-6 specification, not permission to invent
requirements beyond it".

## 1. Official definition (verbatim corpus loci)

- `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md:97-100` — "AI-6 --- External
  Intelligence: Only after untrusted-content boundaries, provenance,
  verification, injection controls and Two-Key Rule." (five mandatory
  pre-conditions)
- `02:161-170` — AI-6/P8 required capabilities: discovery/monitoring of
  approved public source classes; official filing/report ingestion and
  document version tracking; extraction; cross-source corroboration,
  contradiction tracking, duplicate detection and source-quality weighting;
  point-in-time fundamental dossier and change-over-time analysis;
  evidence-linked fundamental interpretation and risk flags; source
  coverage, freshness, failure and unresolved-conflict reporting.
  "All external content is untrusted input. Prompt-injection and
  content-instruction isolation, provenance, tool boundaries and the
  Two-Key Rule remain mandatory. AI must never invent missing financial
  values or silently reconcile contradictory sources."
- `02:194` — acceptance requirements for external/fundamental
  intelligence: point-in-time source records, cross-check/conflict examples,
  citation completeness, restatement handling and missing-source behavior.
- `02:201-203` — G2 preserved; pre-G2 authorized class "bounded design,
  schema work, source-registry design, synthetic/paper tests and safe
  dry-run work"; "External intelligence is not automatically
  production-ready because it is specified here; source permissions,
  provenance, untrusted-content isolation and Two-Key Rule must be
  implemented and validated."
- `03_AI_GOVERNANCE_BOUNDARIES:19-25` — AI may not "treat untrusted content
  as executable".
- `03:73-76` — "## External intelligence — Untrusted by default. Before
  AI-6: provenance, source verification, injection defense, tool boundary,
  Two-Key Rule and human escalation."
- `03:33-40` — run provenance bindings; "Missing required provenance blocks
  governed acceptance."
- `03:85-88` — Security: "Secrets, credentials and private keys are never
  opened, copied, displayed or hashed during forensic work."
- `03:113-114` — preserved gates: external intelligence remains untrusted by
  default and requires provenance, verification, injection defense, approved
  tools and Two-Key Rule.
- D-AI-29 (`05:123-128`) — "DEFERRED BY GATE. Requires untrusted-content
  boundary, provenance, verification and Two-Key Rule."
- D-AI-40 (`05:197-200`) — D-AI-01..31 remain in force; external
  intelligence remains untrusted and gated; no self-escalation.
- D-AI-33 (`05:162-165`) — every fact retains source, publication time,
  reporting period, units/currency, version/restatement state, trust and
  conflict status; missing or contradictory data surfaced, not invented or
  silently reconciled.
- D-AI-38 (`05:187-190`) — coverage/freshness/source-access honesty.
- `06_PRODUCT_CAPABILITY_CHARTER:88-90` — §10: "External documents and web
  content are untrusted data, never executable instructions. Use approved
  tools only; preserve provenance and source references; apply
  prompt-injection isolation and the Two-Key Rule where required."
- `06 §3` (lines 16-30) — versioned source registry; source hierarchy and
  reconciliation rules 1-7 (primary preference; secondary corroborates not
  replaces; duplicate clustering; syndicated copies are not independent
  corroboration; contradictions explicit until deterministic rule or human
  review; publication time separate from retrieval time and reporting
  period; restatements create new versions; units/currency/auditor status
  explicit).
- `06 §11` (lines 100-101) — fundamental-intelligence acceptance gate:
  primary-source extraction, PIT correctness, version/restatement handling,
  cross-source corroboration, contradiction visibility, citation
  completeness, unit/currency normalization, safe behavior when a source is
  missing.
- `02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE:120` — "External source content is
  ingested as untrusted data. Extraction is separated from interpretation.
  ... AI reasoning receives evidence references, not authority to change
  source facts."
- `02_PRODUCT:126` — "Source ingestion may not bypass existing
  external-intelligence gates, Two-Key Rule, untrusted-content isolation,
  provenance, or human approval."
- `AI4_AI7_P343_DEPENDENCY_MATRIX.md:51-69` — AI-6 "Authorized NOW:
  untrusted-content boundary + injection-isolation CONTRACT design (pre-G2
  class); source-class admission schema extension." BLOCKED: any network
  ingestion, any live crawl, any provider contact. Owner decisions needed:
  source classes to admit first; Two-Key Rule operational parameters;
  credentials.

Two-Key Rule locus note: the corpus names the rule at eight loci
(`02:100`, `02:170`, `02:203`, `03:76`, `03:114`, `05:126-128`,
`06:90`, `02_PRODUCT:126`) but defines NO operational parameters (which
actions require it, key custodians, revocation). The dependency matrix
records "Two-Key Rule operational parameters" as an owner decision. This
block therefore delivers the STRUCTURAL mechanism (two distinct human
authorizers required, single-key refused) and records the operational
parameters as owner decisions — no parameters are invented.

## 2. Dependency check (roadmap order `02:5-8` / dependency matrix)

AI-1 → AI-2 → AI-MA → AI-3 → AI-4 are DELIVERED at the pre-G2 contract
class. AI-6's authorized-now class per the dependency matrix is exactly:
(1) untrusted-content boundary + injection-isolation CONTRACT design;
(2) source-class admission schema extension. The ingestion/crawl runtime
does NOT exist; any network ingestion, live crawl or provider contact is
BLOCKED (dependency matrix; `02:203`; owner directive R2: "Do not enable
live execution"). D-AI-29 remains DEFERRED BY GATE: the corpus says AI-6
operationalization comes "only after" the boundary set exists AND is
validated — this block delivers the boundary-set contracts, which is the
pre-G2-authorized class; it does NOT flip D-AI-29 and does NOT claim the
gate open. No owner decision is required to start the contract class
(`05` §Engineering authority; owner directive R2).

## 3. Reuse audit of existing canonical contracts (no duplication)

| Existing contract | Reuse in AI-6 |
|---|---|
| `evidence.py` SCHEMA_VERSION / ensure_utc / EvidenceItem / EvidenceConflict / TrustStatus / CorroborationStatus / UNAVAILABLE | External content filed as evidence reuses the canonical EvidenceItem (source, publication vs retrieval time, tier, hash, trust, conflict, citations); the module adds NO new evidence schema, NO value-reconciliation API — the "never invent / never silently reconcile" requirement is served structurally by reuse (EvidenceConflict resolution requires a named rule or human reviewer) |
| `source_registry.py` SourceDescriptor / SourceTier / PrecedenceClass / SourceRegistry / CoverageReport | Source binding and source-class vocabulary are consumed, not reimplemented; coverage/freshness/failure reporting reuses CoverageReport (D-AI-38); the AI-6 admission schema EXTENDS the registry vocabulary (dependency matrix "source-class admission schema extension") without modifying the registry module |
| `run_governance.py` RunContext / RunProvenance / ArtifactRef / assert_autonomy_permitted / missing_required_provenance | Governed ingestion/analysis runs bind canonical run identity; provenance completeness and autonomy ceiling consumed, not reimplemented |
| `ai2_governance.py` gate-function shape (blocking-reason tuples), AI2BudgetSpec bounded-ceilings precedent | Gate functions return explicit deterministic refusal-code tuples; no unbounded budgets introduced |
| `governed_generation.py` SandboxBudgetSpec / sandbox_budget_verdict | Sandbox execution is AI-4's concern; AI-6 does NOT duplicate a sandbox abstraction; quarantine is a distinct, content-side concept |
| `multi_agent.py` / `research_memory.py` / `monitoring.py` / `monitoring_governance.py` | No new specialist, memory, or monitoring-job abstraction; discovery/monitoring RUNTIME is AI-5/AI-6 post-gate work |

Grep-verified before implementation: no `untrusted`, `quarantine`,
`two_key`, `TwoKey`, or `external_intelligence` contract exists anywhere in
`backend/` (only pre-existing DSL import-injection security tests in
`test_filter_dsl.py`/`test_metrics.py`, which are a different concern) —
zero duplication risk.

## 4. Requirement → implementation traceability matrix

Legend — Status: GAP = to be implemented in this block; REUSE = delivered
by an existing canonical contract and consumed. Planned implementation in
`backend/app/domain/external_intelligence.py` unless noted.

| # | Requirement (corpus locus) | Status | Planned implementation |
|---|---|---|---|
| R1 | "All external content is untrusted input" (`02:170`); "untrusted by default" (`03:75`); "untrusted data, never executable instructions" (`06:89`); "ingested as untrusted data" (`02_PRODUCT:120`) | GAP | `UntrustedContentEnvelope` with `trust_label: Literal["UNTRUSTED"]` structurally locked; no upgrade path exists in the module; content trust never inferred from scan results |
| R2 | Provenance preservation (`02:170`; D-AI-29; `03:33-40`; `06:90` "preserve provenance and source references") | GAP | Envelope binds `content_id`, `content_sha256` (hex-64), `source_id` (must resolve in a provided SourceRegistry), `retrieval_time_utc`, `source_tier`; filing to evidence consumes canonical EvidenceItem (REUSE) — provenance fields carried, never dropped |
| R3 | Content-instruction isolation (`02:170`); untrusted content is never executable (`03:19-25`; `06:89`) | GAP | `ContentSegmentation` separates `untrusted_payload` from `embedded_instruction_candidates`; `EmbeddedInstructionCandidate.executable: Literal[False]` — content-borne instructions are structurally non-executable |
| R4 | Explicit trust boundaries incl. tool boundary (`02:97-100`; `03:73-76`; `02:170` "tool boundaries"; `02_PRODUCT:126` "may not bypass") | GAP | `TrustBoundaryFlow` closed vocabulary; `assert_boundary_allowed()` deterministic gate — TOOL_EXECUTION / PRODUCTION_MUTATION / AUTONOMOUS_ACTION structurally forbidden (refused with codes); EXTRACTION_DETERMINISTIC / EVIDENCE_FILING / QUARANTINE / ADVISORY_INTERPRETATION allowed under conditions |
| R5 | Injection controls (`02:97-100`; `02:170` "Prompt-injection"; `03:76` "injection defense") | GAP | `InjectionFinding` closed taxonomy (DIRECT_INSTRUCTION, INSTRUCTION_CONFLICT, TOOL_INVOCATION_ATTEMPT, PRIVILEGE_ESCALATION, OBFUSCATED_INSTRUCTION, NONE_DETECTED); `InjectionScanRecord` (deterministic: scan results passed in, never LLM-computed); `injection_response_gate()` — any non-NONE finding ⇒ quarantine + human escalation; NONE_DETECTED does NOT raise trust |
| R6 | Instruction-conflict handling (owner directive R2; `02:170` content-instruction isolation) | GAP | `InstructionConflictRecord` — content-borne instruction vs governed instruction; resolution structurally locked: governed instructions take precedence, content instruction quarantined; compliance with content-borne instructions unrepresentable |
| R7 | Safe refusal and quarantine behavior (`03:76` "human escalation"; directive R2) | GAP | `QuarantineRecord` (closed reason taxonomy) + append-only `QuarantineLedger` (no update/delete/invalidate path); release/discarding requires named human decision + reference; quarantined content cannot re-enter any allowed flow |
| R8 | Two-Key Rule structural mechanism (`02:100`; `02:170`; `03:76,114`; D-AI-29; `06:90`; `02_PRODUCT:126`) | GAP | `TwoKeyAuthorization` — two DISTINCT human authorizers (identity, role, time, reference each); construction-time validators refuse single-key, identical-identity and missing policy version; `quarantine_release_gate()` enforces the Two-Key binding where the source class requires it; operational parameters (action classes, custodians) recorded as owner decisions (UNRESOLVED — dependency matrix) |
| R9 | Verification pre-condition (`02:97-100`; `03:75` "source verification"; D-AI-29) | GAP | `SourceVerificationRecord` (source_id, verified_by, method, verified_at_utc); `evidence_filing_gate()` requires a verification record for sources whose policy demands it; actual verification execution = network work, BLOCKED (contract records only) |
| R10 | Source-class admission schema extension (dependency matrix "Authorized NOW") | GAP | `ExternalSourceClassAdmission` — control declarations over the existing SourceTier vocabulary (verification required, injection scan required, two-key required flags); admits CONTROLS, not sources; specific source-class admission = owner decision (UNRESOLVED) |
| R11 | "AI reasoning receives evidence references, not authority to change source facts" (`02_PRODUCT:120`) | GAP | `AdvisoryInterpretationRequest` binds evidence IDs only; carries no write authority over source facts; boundary gate has no flow that mutates source facts (structural absence, test-enforced) |
| R12 | Never invent missing values; never silently reconcile (`02:170`; D-AI-33; `06 §3.4`) | REUSE | evidence.py UNAVAILABLE / EvidenceConflict (resolution requires named rule or human reviewer); module adds NO reconciliation API — structural reuse; tests assert conflicts stay explicit |
| R13 | Coverage/freshness/failure/conflict reporting (D-AI-38; `02:169`) | REUSE | `source_registry.coverage_report` / `CoverageReport` remain canonical in `source_registry.py`; not yet consumed by the AI-6 contract layer (runtime reporting is post-gate); no duplicate reporting schema introduced |
| R14 | Deterministic failure handling + auditable evidence (`03:90-94`; directive R2) | GAP | Every gate returns explicit refusal-code tuples; `governed_external_intake` end-to-end acceptance returns blocking codes; failure-path tests cover every refusal |
| R15 | Run identity + provenance on governed actions (`02:198`; `03:33-40`) | GAP | Intake/interpretation gates consume RunContext + `missing_required_provenance` (REUSE) with `dataset_version`-style required additions |
| R16 | Secrets discipline (`03:85-88`) | GAP | Module contains no secret handling; envelope hashing applies to external CONTENT only (evidence.py precedent); negative test asserts refusal when a credential-bearing field is presented as content location? — no: simply no credential fields exist; documented in module docstring |
| R17 | Pre-G2 class; no runtime (`02:202`; dependency matrix BLOCKED rows) | GAP | Frozen, deterministic, clock-free module; no network/I/O/LLM/scheduler; ingestion runtime absent (structural); docstring records NOT-PROVEN honesty (D-AI-41) |

## 5. Out of scope (explicitly NOT authorized by this block)

- Any network ingestion, crawl, fetch, or provider contact (dependency
  matrix BLOCKED; `02:203`; D-AI-29 still DEFERRED BY GATE).
- Any scheduler/event runtime for discovery or monitoring (AI-5/runtime,
  owner-gated).
- Any LLM invocation, prompt template, or live interpretation (LLM NOT
  EXECUTED; G2).
- Any modification to existing modules (additive-only): evidence.py,
  source_registry.py, run_governance.py, ai2_governance.py,
  governed_generation.py, monitoring*, multi_agent.py, research_memory.py,
  fundamental_dossier.py.
- Any new HTTP route, config flag, or `AI2_ENABLED` change.
- Specific source-class admission decisions, Two-Key Rule operational
  parameters, credentials (owner decisions — recorded UNRESOLVED).
- AI-5/AI-7 scope creep (separate owner decisions — dependency matrix).

## 6. Planned acceptance evidence

- Corpus-derived test module `backend/tests/test_ai6_external_intelligence.py`
  (positive end-to-end intake → segmentation → scan → filing/interpretation
  flows + negative coverage: boundary violations, malicious content,
  malformed inputs, attempted privilege escalation, single-key refusal,
  quarantine-release discipline).
- Full repository battery (pytest, pyflakes, compileall, pip-audit, alpha
  env/runtime/frontend validators, bootstrap validator, `git diff --check`)
  pre-commit (raw outputs under `docs/governance/evidence/raw/2026-10-19_ai6/`)
  and at the committed SHA (raw outputs under
  `docs/governance/evidence/raw/2026-10-19_ai6a/`).
- Independent read-only audit → `docs/governance/evidence/
  2026-10-19_AI6_independent_audit.md` (post-implementation).
- Execution record `docs/active/AI6_EXECUTION_RECORD.md`; pointers updated
  (INDEX / STATUS / CHANGELOG / handoff); state file reconciled.

## 7. Resolved/unresolved register

- Contract-class requirements R1-R17 are all corpus-derivable → UNRESOLVED
  count: 0 for the contract class.
- UNRESOLVED (owner decisions, do not block this block): source classes to
  admit first; Two-Key Rule operational parameters (action classes,
  custodians, revocation); source-access credentials; D-AI-29 gate
  activation (requires the boundary set to be implemented AND validated —
  this block delivers the contracts, NOT the validation of a runtime).
- Release of quarantined content and admission of source classes require
  named human decisions; the mechanism is delivered, the decisions are not
  made here.
