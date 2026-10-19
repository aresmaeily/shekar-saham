# AI-3 PERSISTENCE — INCUMBENT STACK (SQLITE WAL + JSONL) CANDIDATE EVALUATION

Status: prepared under owner directive 2026-10-19 Decision R3 ("Do not
perform a storage migration or claim a final architecture decision solely
because SQLite WAL and JSONL exist in the current stack"). This document
designates the incumbent stack as the PREFERRED CANDIDATE for the AI-3
persistence adapter, conditionally, with recorded limitations and
unresolved owner decisions. NO migration was performed; NO production
integration was performed; the AI-3 contract layer remains in-memory and
unchanged. It extends — and defers to — the neutral analysis in
`AI3_PERSISTENCE_DECISION_BRIEF.md` (constraints A1–A12, options 1–3,
unknowns C1–C5, decisions D1–D7).

## 1. Candidate under evaluation (incumbent, verified in-repo)

Embedded SQLite (WAL, `PRAGMA synchronous=NORMAL`, `user_version`
migrations, WAL-consistent backup routine) + append-only JSON/JSONL files
(`history_snapshots.jsonl`) + content-addressed artifact blobs.
Verified: `backend/app/data/store.py:36-37,47-63,127`;
`backend/app/core/config.py` data-dir settings; `data/shekar.db` +
`data/market_cache.json` present in the dev sandbox. The candidate wraps
— never replaces — the delivered in-memory contracts
(`EpisodicRunArchive`, `SemanticLessonStore`): persistence is an adapter
behind the same append-only API (`02:107-112` reuse rule; brief §B).

## 2. Evaluation against the official requirements (R3 list)

Scale: SUPPORTED / SUPPORTED-WITH-LIMITATION / NOT-SUPPORTED / EVIDENCE-MISSING.
Corpus anchors: brief A1–A12 (`AI3_PERSISTENCE_DECISION_BRIEF.md` §A).

| Requirement | Verdict | Evidence and reasoning |
|---|---|---|
| Durability | SUPPORTED-WITH-LIMITATION | SQLite WAL with `synchronous=NORMAL` is engine-native durable against process crash; the JSONL leg needs an explicit fsync/rotation writer discipline (brief Option-2 analysis). NORMAL (not FULL) trades a rare power-loss window for speed — acceptable for a single-operator research archive, recorded honestly as a limitation. |
| Recovery | SUPPORTED-WITH-LIMITATION | WAL crash recovery is engine-native; the backup routine shipped in code (`store.py` WAL-consistent backups to `data/backups`). EVIDENCE-MISSING component: no restore drill has ever been executed and no backup artifact exists in the dev sandbox yet — recovery is supported by design but NOT YET DEMONSTRATED. |
| Immutability (A2/A3/A11) | SUPPORTED-WITH-LIMITATION | Enforcement is application-level: INSERT-only code paths behind the in-memory contracts' append-only API; SQLite cannot structurally forbid UPDATE without triggers. Mitigation stack (adapter design): deny-triggers on episodic tables + hash columns verified by a periodic audit query + JSONL format-level append for event logs. The brief already identified this as "the only inherent tension" (Option 1). A storage-level guarantee would require Option 3 (Postgres grants) — a deployment-class decision the owner has not made. |
| Provenance (A6, D-AI-22) | SUPPORTED | Versioned rows + content-addressed blobs map 1:1 to the delivered provenance discipline (`ArtifactRef.sha256`, `input_snapshot_sha256`); unknown fields stay explicit `None` (A6); hash columns make provenance independently checkable. |
| Semantic versioning (A4) | SUPPORTED | Versioned rows are a natural fit: supersede/retire expressed as NEW terminal rows/views, never rewrites — mirrors `research_memory.py:247-318` exactly. |
| Supersession | SUPPORTED | Same mechanism as above; supersession chains queryable by (lesson_id, version). |
| Point-in-time retrieval (A5) | SUPPORTED | Indexed queries on `recorded_at_utc`/`created_at_utc` map 1:1 to `available_at()` / `lessons_active_at()`; SQLite indexes make PIT filters native rather than scan-based (brief comparison row). |
| Access control (A8) | SUPPORTED-WITH-LIMITATION | File-permission level; adequate for the single-operator deployment the repo actually targets (A12, Windows/Electron single host); weak for any multi-user/remote deployment. Whether multi-user is ever required is UNRESOLVED (D2/D4) — this is the candidate's main conditional dependency. |
| Auditability (A8, `02:198`) | SUPPORTED-WITH-LIMITATION | Run-identity columns + hash verification + grep-able JSONL logs give a complete audit trail; what does NOT exist yet is a dedicated append-only audit ledger table — additive at adapter time, listed in the migration strategy below. |

Summary: 6 SUPPORTED, 3 SUPPORTED-WITH-LIMITATION, 0 NOT-SUPPORTED. The
limitations are deployment-dependent (D2/D3/D4), not engine deficits; no
requirement is violated by the candidate.

## 3. Why the evidence supports PREFERRED-CANDIDATE designation (rationale)

1. Lowest deployment delta on the actual target (A12): the engine,
   migration mechanism, and backup routine are already shipped and
   audit-passed on this stack; P3.43 launch gates (Windows target,
   Electron runtime) are already the binding constraints — adding a
   server-class dependency (Option 3) would enlarge the exact surface
   that is currently blocked.
2. Requirement fit without violation (§2): every R3 requirement is
   supported; the three limitations are conditional on owner decisions,
   not on the engine.
3. Reuse rule (`02:107-112`) and speed rule: additive adapter over the
   incumbent engine beats introducing new infrastructure with zero
   requirement gain at current scale (C1: no measured volume).
4. Reversibility: the adapter is additive and isolated behind the
   in-memory contracts; choosing it now costs nothing if a later owner
   decision (D1/D2) moves to server-class storage — the contracts are
   the stability point, the adapter is replaceable.

This designation is a CANDIDATE ranking, not a final architecture
decision (R3 explicitly reserves that), and it does not upgrade AI-3
implementation status (D-AI-41: no runtime exists; live feeding is
G2-gated).

## 4. Limitations (honest register)

- L1 Immutability is application-level unless deny-triggers are added
  (migration step M3 below); storage-level guarantees need Option 3.
- L2 `synchronous=NORMAL` admits a narrow power-loss durability window;
  `FULL` remains available if the owner requires it (performance cost).
- L3 Access control is file-permission class — conditional on D2/D4.
- L4 Recovery is designed-in but UNDEMONSTRATED (no restore drill, no
  backup artifact yet); the adapter acceptance tests below close this.
- L5 Single-writer class (WAL lock) — sufficient for the roadmap's
  single-operator research runtime; insufficient for concurrent
  multi-process writers (D2-dependent).
- L6 No dedicated audit-ledger table yet — added at adapter time (M5).

## 5. Migration strategy (PLAN ONLY — nothing executed)

Additive, reversible, behind the existing contracts; production data
migration is a non-concept today because no production research runtime
exists (G2-gated):

- M1: adapter module `app/data/research_memory_store.py` implementing the
  `EpisodicRunArchive`/`SemanticLessonStore` API over SQLite + blobs;
  in-memory classes remain the canonical contract reference.
- M2: schema via the established `PRAGMA user_version` migration path;
  new tables only (episodic_artifacts, semantic_lessons, lesson_versions,
  quarantine-free; no update/delete statements anywhere).
- M3: deny-triggers (`CREATE TRIGGER ... BEFORE UPDATE/DELETE → RAISE`)
  on episodic tables — closes L1 at the storage level inside SQLite.
- M4: content-addressed blob writer (sha256 naming) with fsync-on-close.
- M5: append-only audit-ledger table for memory operations (closes L6;
  `03 §Memory` operation vocabulary).
- M6: backup-integration: reuse the existing WAL-consistent backup
  routine; restore drill becomes a required acceptance test (closes L4).
- M7: synthetic-only fixtures; no live data (02:202 pre-G2 class).

## 6. Acceptance tests the adapter must pass before any acceptance claim

1. Immutability negatives: UPDATE/DELETE on episodic tables refused by
   trigger; adapter exposes no update/delete path (structural).
2. Append-only round-trip: artifact → archive → retrieve byte-identical
   (hash match) across process restart.
3. PIT correctness: records recorded after a cutoff are invisible to
   `available_at`-style queries at that cutoff (look-ahead guard).
4. Supersession chain: supersede/retire create new versions; history
   views never rewritten; retirement terminal.
5. Provenance completeness: missing required provenance blocks acceptance
   (03:40) at the storage boundary, mirroring the in-memory gates.
6. Backup/restore drill: WAL-consistent backup → destructive restore →
   full re-verification by hash (closes L4).
7. Crash-recovery: kill during write → reopen → WAL recovery → no
   partial record accepted (durability evidence).
8. Access-control reality check: file-permission enforcement documented
   for the declared deployment mode (conditional on D2/D4).

## 7. Unresolved decisions (exact register — R3 requires this)

| ID | Unresolved decision | Why it blocks finalization | Class (R7) |
|---|---|---|---|
| D2 | Deployment target of the AI runtime (Windows host / Docker / Electron-bundled) | Determines engine class, access-control model, and whether the embedded candidate is final | Owner decision genuinely required before final architecture |
| D3 | Immutability guarantee class required (app-level vs trigger-level vs storage-level) | Determines whether M3 deny-triggers are sufficient | Engineering-recommendable; owner-ratifiable |
| D4 | Access-control model and who may read episodic evidence | Multi-user requirements would reopen Option 3 | Owner decision (single-operator assumption must be confirmed) |
| D5 | Backup/retention/DR policy (cadence, copies, offsite) | Operational policy; archive itself never purged (A3/A11) | Operational gate, not waivable by general instruction |
| D6 | Blob-store location and size ceilings | Deployment detail; no requirement evidence yet | Non-blocking for candidate designation |
| D7 | Timing: adapter now vs after G2 | Contract layer complete; deferral carries no identified risk | Engineering decision safely deferrable |

Per R3, none of these blocks AI-6 or any other independent work; the
persistence adapter remains BLOCKED on D2/D3/D4 (+D5 for operations), and
the candidate designation stands as prepared evidence for the owner's
final architecture decision.
