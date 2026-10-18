# AI3-M Execution Record — Research Memory (Episodic + Semantic)

Date: 2026-10-18 · Block: **AI3-M** (AI-3 Research Memory; dependency successor of AI-MA-C per `02` line 7) · Baseline at mission start: `aa86c3c` (AI-MA-Ca) on `main`, ahead 17/behind 0 vs live `origin/main` `c1984e7`, tracked tree clean, 4 untracked bootstrap paths preserved, amendment corpus byte-identical.

## 1. Scope derivation (published before implementation)

Report: `docs/active/AI3_M_SCOPE_DERIVATION.md`. Authoritative definition: `02` lines 83–85 — "Episodic immutable run artifacts plus curated/versioned semantic memory" (supporting: `02`:142 information cutoff, `02`:159 immutability+curation, `02`:198 traceable identity/versions, `06` §7 version linkage, `03` §Memory, D-AI-28). Blocker history: AI3-A proved the definition lived only in the then-NOT_SYNCED corpus; the P0-AMD-1 import resolved it; AI1-GC delivered the memory interfaces; AI3-M delivers the system contracts.

## 2. Implementation (additive contracts + tests, nothing else)

`backend/app/domain/research_memory.py` (frozen, deterministic, clock-free; no network/LLM/thread/scheduler; no existing module modified; no route; no config change):

| Corpus requirement | Contract |
|---|---|
| Episodic immutable run artifacts (02:83,159; D-AI-28) | `EpisodicRunArtifact` — frozen; binds `ArtifactRef` + run identity + hypothesis id + input snapshot sha256 + trust state + code-commit/dataset-version/policy-version linkage (06 §7) + MANDATORY information cutoff (02:142; cutoff-after-recording refused); `EpisodicRunArchive` — append-only (idempotent/conflict), NO update/delete/purge/expire/rewrite path, indexed by run and hypothesis, PIT `available_at(cutoff)` |
| Curated/versioned semantic memory (02:83,159; D-AI-28) | `SemanticLesson` — version chain (v1 cannot supersede; later versions name their parent), curation names deterministic rule or human reviewer, **source-artifact citation mandatory**; `derive_lesson()` factory — refuses lessons citing artifacts absent from the archive (lessons derive FROM episodic evidence, never from nothing); `SemanticLessonStore` — register/supersede/retire with history never rewritten; retirement is an explicit NEW terminal version (no delete path) |
| Point-in-time honesty (02:142) | `lessons_active_at(store, cutoff)` — deterministic PIT view (latest version ≤ cutoff whose current status is ACTIVE; documented conservative semantics: superseded/retired lessons are never presented as active, and the store keeps current status flags rather than a full status history — explicitly documented in the test) |
| No silent production modification (03 §Memory) | Closed `MemoryLifecycleOperation` set (APPEND_EPISODIC / DERIVE_LESSON / SUPERSEDE_LESSON / RETIRE_LESSON) — structurally cannot express a production mutation |

Tests: `backend/tests/test_ai3_research_memory.py` (13 tests) — provenance freezing/shapes, cutoff logic, archive no-delete-path + indexes + PIT availability, lesson chain guards, archive-citation requirement, register/supersede/retire lifecycle, PIT honesty incl. the superseded-before-cutoff nuance, closed-operation lock. Development-time defect notes (honest record): three initial test expectations were wrong (a malformed drafted expression; a leaked base-field in an index test; supersession assumed to REMOVE a lesson and retirement counted wrong versions — supersession keeps the lesson ACTIVE via its new version and retirement appends a terminal version) — fixed in tests; plus one genuine semantic decision made explicit: `lessons_active_at` uses current-status-at-latest-version ≤ cutoff (documented in test + docstring), because the store keeps no status history.

## 3. Blocked integration (isolated precisely per the execution directive)

- **Persistence technology**: the corpus specifies no storage engine/format/service for AI-3. The deterministic in-memory stores are delivered; actual persistence is an owner-environment deployment decision. Everything else in the AI-3 scope is unblocked and delivered.
- **Live research-run feeding**: episodic artifacts are produced by governed research runs; the research-loop runtime requires G2-passed real-data execution (`02` lines 10–11/201). AI3-M accepts/archives; it does not execute research. Smallest owner action: authorize G2 (reviewer-ready package exists) — then the loop runtime + persistence integration become the next decisions.

## 4. Statuses after this block (separated, not conflated)

- AI-3 Research Memory: **IMPLEMENTED (contract layer, paper/synthetic scope)** — episodic immutable archive + curated/versioned lessons + PIT honesty + closed lifecycle operations.
- NOT claimed (D-AI-41): memory persistence/live feeding NOT PROVEN; AI-3 acceptance evidence beyond contracts NOT PROVEN; no production storage exists.
- G2: NOT_PASSED (owner-executed; reviewer-ready). `AI2_ENABLED` default off; no route; LLM NOT EXECUTED; `live_verified=false`.
- Push: owner-gated (local commits recorded in the state file).
- Dependency-chain position: AI-1 (gap closure) → AI-2 (required items) → AI-MA (contracts) → **AI-3 (this block)** — all delivered at the pre-G2-authorized contract class; the roadmap's remaining blocks (AI-4 Governed Generation … AI-7) and G2 remain owner-gated.
