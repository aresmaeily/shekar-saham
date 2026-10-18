# AI-3-M Scope Derivation — Research Memory (`02` §AI-3, lines 83–85)

Published BEFORE implementation (governance precedent). Baseline: HEAD `aa86c3c` (AI-MA-Ca) on `main`, ahead 17/behind 0 vs live `origin/main` `c1984e7`, tracked tree clean, 4 untracked bootstrap paths preserved, amendment corpus byte-identical.

## 1. Authoritative definition

`02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md` lines 83–85: "**AI-3 --- Research Memory** — Episodic immutable run artifacts plus curated/versioned semantic memory." Supporting loci: `02_PRODUCT…` §Memory ("Run Context = execution state. Episodic Memory = immutable research evidence. Semantic Memory = curated, versioned knowledge.") and rule 12 (traceable to run_id); `03` §Memory ("Episodic research evidence is immutable. Semantic learning is versioned and curated. No memory operation may silently modify production logic."); D-AI-28 (memory split); D-AI-22 (provenance before scale); `06` §7 ("All results link to code/config/data versions and immutable run artifacts"); `02` line 142 ("Every conclusion must identify its information cutoff"); `02` line 159 ("Episodic research artifacts remain immutable; semantic lessons remain curated/versioned"); `02` line 198 (governed actions: traceable run identity, versions, human approval state, explicit limitations).

Blocker history: AI3-A (`42587fa`) proved AI-3 was defined ONLY by the then-NOT_SYNCED corpus; the import (P0-AMD-1, `357f4b6`) resolved the blocker at definition level. Dependency prerequisites are now satisfied at contract level: AI1-GC delivered the memory *interfaces*; AI2-F the run ledger; AI-MA-C the artifact/trace contracts. AI-3 delivers the memory SYSTEM contracts.

## 2. Deliverable → requirement traceability (one additive module: `backend/app/domain/research_memory.py`)

| # | Corpus requirement | Contract | Acceptance → tests |
|---|---|---|---|
| D1 | "Episodic immutable run artifacts" (02:83,85,159; D-AI-28) | `EpisodicRunArtifact` (frozen; binds ArtifactRef + run identity + hypothesis id + input snapshot + trust state + code commit/dataset version/policy version + **information cutoff** per 02:142) + `EpisodicRunArchive` (append-only; idempotent/conflict; NO update/delete/retention-delete path — immutability is structural) | Freezing, UTC, sha/commit shapes, archive semantics, PIT `available_at(cutoff)` → tests |
| D2 | "curated/versioned semantic memory" (02:83,85,159; D-AI-28) | `SemanticLesson` (version chain; curation names deterministic rule or human; **source artifact citation mandatory** — lessons derive FROM episodic evidence, never from nothing) + `derive_lesson()` factory (refuses lessons citing artifacts absent from the archive) + `SemanticLessonStore` (register/supersede/retire; history never rewritten; retirement is an explicit terminal version) | Chain guards, citation requirement, retire semantics → tests |
| D3 | Point-in-time honesty (02:142; 06 §3.6) | `lessons_active_at(store, cutoff)` — deterministic PIT view of active lessons | Future lessons excluded; superseded/retired excluded → tests |
| D4 | "No memory operation may silently modify production logic" (03 §Memory) | Closed `MemoryLifecycleOperation` set (APPEND_EPISODIC / DERIVE_LESSON / SUPERSEDE_LESSON / RETIRE_LESSON) — structurally cannot express a production mutation | Literal-set test → tests |
| D5 | Traceability to run identity (02-product rule 12; D-AI-22) | Every episodic artifact and lesson optionally/mandatorily binds run_id; archive indexes by run and hypothesis | `for_run`/`for_hypothesis` → tests |

## 3. Explicitly out of scope / blocked integration (isolated precisely per the execution directive)

- **Persistence/storage technology**: the corpus specifies NO storage engine, format, or service for AI-3. In-memory deterministic stores (the established contract-layer pattern) are delivered; actual persistence is a runtime integration decision that requires the owner's deployment environment — the exact blocked integration for AI-3, isolated here so the remaining owner action stays small.
- **Live research-run feeding**: episodic artifacts are produced by governed research runs; the research-loop runtime requires G2-passed real-data execution (`02` lines 10–11/201). AI-3-M accepts and archives artifacts; it does NOT execute research.
- No LLM, no network, no route, no config change, no existing module modified, no capability-status upgrade (D-AI-41): memory acceptance evidence beyond contracts NOT PROVEN.

## 4. Gates

Owner approval: not required for this contract class (`05` §Engineering authority). G2: NOT_PASSED (unchanged). Push: owner-gated.
