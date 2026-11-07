# AI-2 PERSISTENCE OWNER DECISION PACKET — D-A2-1 … D-A2-7 (consolidated)

**ALL SEVEN DECISIONS PENDING — no owner decision recorded as of this
packet's preparation (WAVE-B / WP-B wave, following the recorded
2026-11-08 wave); none is assumed anywhere in the kit below, and the
RECOMMENDED markers are engineering rankings, not decisions.**

Status: OWNER DECISION PACKET. This document is ADDITIVE. It mirrors the
AI-3 precedent (`docs/active/AI3_PERSISTENCE_DECISION_PACKET.md`) — a
decision list with options, exact technical consequences, risks, one-sentence
owner statements, and deferral consequences — for the production persistence
of the AI-2 governed generation loop's two in-memory stores:

- `GenerationCandidateRegistry` (versioned candidates, human-approval
  surface; `backend/app/services/ai2_generation.py`),
- `AI2RunLedger` (append-only run records, duplicate detection;
  `backend/app/domain/ai2_governance.py`).

**EXPLICIT SCOPE STATEMENT: NO production persistence is activated by this
wave.** The wave only (a) records the current-state honesty facts, (b) lists
the decisions the owner must take, and (c) prepares a DORMANT prototype
adapter + tests (`backend/app/data/ai2_ledger_sqlite.py`,
`backend/tests/test_ai2_persistence_kit.py`) so the owner's reply can be
executed directly. Nothing in `app/services` or `app/api` imports the
adapter (test-pinned dormancy); `AI2_ENABLED` (default `0`) is untouched and
remains the execution gate.

---

## 0. Current state and framing facts (source-backed)

1. **Current state — in-memory, disclosed everywhere, lost on restart.**
   The generation module's own contract states it (`ai2_generation.py`
   docstring, "Storage honesty" bullet, lines ~71-74 at HEAD be4efcf):
   "the candidate registry and run ledger are IN-MEMORY ONLY (bounded);
   process restart clears them by design until an owner-approved persistence
   decision exists — same honesty posture as the strategy-lab version
   registry (recorded in every listing payload)." The posture report repeats
   it per call (`registry_persistence: "in-memory-only; restart clears
   (owner-gated persistence decision)"`).
2. **Bounded by design.** The registry holds at most 128 candidates
   (oldest-evicted, `_REGISTRY_CAPACITY`) and the snapshot/idempotency maps
   are bounded at 256 (`_LEDGER_SNAPSHOT_BOUND`); the in-memory
   `AI2RunLedger` is append-only with idempotent re-append and conflict
   refusal (`AI2RunLedger.append`), and duplicate detection is a LABEL
   (`classify_duplicate`: identical (task, input-snapshot) pair =
   `DUPLICATE_IDENTICAL`, other repeats of the same task =
   `DUPLICATE_REPEATED_QUESTION`, else `NEW`) that never blocks ledgering.
   Any persistence option must preserve these exact semantics, not change
   them.
3. **Execution is double-gated today.** AI-2 generation executes nothing
   unless `AI2_ENABLED=1` (default `0`, `backend/app/core/config.py` line
   ~118) AND the trust-state/provider-policy gates pass; everything runs on
   the deterministic seeded synthetic series (`SYNTHETIC_OR_PAPER` labels).
   Persisting run/candidate RECORDS does not change what may EXECUTE.
4. **Precedent — AI-3.** The identical decision class was prepared for AI-3
   (`AI3_PERSISTENCE_DECISION_PACKET.md`, D1–D7) and later recorded by the
   owner (`OWNER_DECISIONS_RECORDED_2026-11-02.md`; production adapter
   `app/data/research_memory_sqlite.py`, explicitly NOT auto-wired).
   AI-2's packet reuses that structure and the repo's proven SQLite/WAL
   discipline (`backend/app/services/prediction_store.py`: WAL +
   `synchronous=FULL` + pinned schema digests + per-row SHA-256 + verified
   backup / restore-refuses-unverified).
5. **Corpus position.** The AI-2 MVRL requirement (02 lines 44–53: immutable
   run identity, provenance, budget limits, evidence artifacts, duplicate
   detection, failure/recovery, invalidation, human approval state) implies
   durable run evidence; it does NOT name a storage engine, format, or
   service. Persistence is an owner-environment decision by deliberate
   isolation (same posture the AI-3 brief recorded). No numbers are invented
   in this packet; where a source states nothing, the cell says
   **UNKNOWN-WITH-REASON**.
6. **The seven decisions below are independent of G2/data trust.** They
   govern RECORDS of synthetic/paper research runs only. Nothing here
   enables live data, live execution, or provider egress.

---

## 1. D-A2-1 — Storage engine for the AI-2 registry + ledger

**Decision question:** "Which storage engine carries the persisted
`GenerationCandidateRegistry` + `AI2RunLedger` records?"

**Options on the table:**

- **Option 1 (RECOMMENDED — engineering ranking, not a decision) — embedded
  SQLite, WAL journal mode.** One database file (repo convention:
  `DATA_DIR`, e.g. `data/ai2_generation_ledger.sqlite3`), mirroring the
  AI-3 recorded decision (D1) and the shipped `prediction_store.py`
  discipline (`PRAGMA journal_mode=WAL`, `synchronous=FULL`,
  `busy_timeout`, `foreign_keys=ON`; `BEGIN IMMEDIATE` writes under a
  process lock; UNIQUE constraints as the cross-process hard guarantee).
  The prepared dormant prototype already implements this shape.
- **Option 2 — append-only JSONL files** (one line per record, canonical
  JSON, content-addressed overflow artifacts). Simplest inspectability;
  loses indexed lookups, atomic multi-statement appends, and the
  integrity_check machinery that SQLite gives for free.
- **Option 3 — server-class DB (PostgreSQL).** New service to install and
  operate; adds surface the deployment gates do not budget (P3.43-class
  blockers recorded for the AI-3 packet apply unchanged).

| Consequence | Opt 1 SQLite/WAL | Opt 2 JSONL | Opt 3 Postgres |
|---|---|---|---|
| Operating-cost delta | **Lowest** — engine already shipped and backed up on this stack (framing facts 3–4) | Low ops, hand-rolled integrity tooling | **Highest** — new service class |
| Immutability strength | App-level INSERT-only paths + UNIQUE constraints (+ optional deny-triggers at activation) | Format-level (strongest natural) | Storage-level grants (strongest, requires Opt 3 deployment) |
| Crash behavior | WAL recovery; committed appends survive | fsync discipline is the caller's job | Engine-class durability |
| Concurrency | Single-writer class (WAL lock) — matches the single-operator research runtime | Single-writer discipline required | Multi-writer — relevant only for a runtime that does not exist |
| Windows/Electron burden | Low (single-file portability) | Low | High (P3.43-class blockers) |
| Risk | App-level-only immutability unless triggers are added (mitigable at activation, D-A2-3) | Corruption detection hand-rolled | Operating surface the repo does not have |

**What the owner must state (one sentence):** `D-A2-1: engine = SQLite/WAL
(recommended) | JSONL | server-class; file path = <stated>; activation
handler = <stated owner act reference>.`

**Consequence of deferral:** the stores stay IN-MEMORY ONLY with the current
honest disclosure; restart loss continues BY DESIGN and is disclosed in
every listing/posture payload. Nothing else in the AI-2 loop is affected.

---

## 2. D-A2-2 — Schema / migration strategy

**Decision question:** "How are the in-memory record shapes mapped to
tables, and how are schema changes governed?"

**RECOMMENDED shape (mirrors `prediction_store.py` byte-for-byte in
discipline; the dormant prototype implements exactly this):**

- `ai2_run_records(record_id UNIQUE, payload, row_digest)` — one row per
  `AI2RunRecord`; `payload` = canonical JSON of the full frozen record
  (`model_dump(mode="json")`, sorted keys, explicit separators); `row_digest`
  = SHA-256 of the payload, computed at write, verified at open/restore.
- `ai2_candidate_records(candidate_id UNIQUE, payload, row_digest)` — one
  row per `GenerationCandidate` (same canonical-JSON discipline).
- `ai2_duplicate_keys(task, input_snapshot_sha256, record_id,
  UNIQUE(task, input_snapshot_sha256), row_digest)` — the persisted
  `classify_duplicate` key space (see D-A2-4).
- `ai2_ledger_meta(key, value)` — monotonically bumped ledger version,
  mirroring the prediction store's `registry_version`.
- **Migrations: versioned DDL with PINNED SQL digests** stored in
  `schema_migrations(version, sql_digest)`; an applied digest that no longer
  matches the shipped SQL fails closed (`schema_digest_mismatch`) — the
  exact `prediction_store.py` mechanism. There is NO auto-migration beyond
  applying the pinned, reviewed migrations themselves (see D-A2-7).

| Consequence | Detail |
|---|---|
| Schema evolution | Additive migrations only; each new version = a new pinned digest reviewed with the wave that ships it |
| Tamper evidence | Per-row SHA-256 verified at open AND at restore; any mismatch fails closed (`AI2LedgerCorruption`) and is recoverable ONLY from a verified backup (D-A2-6) |
| Record fidelity | Full frozen-record payloads, decoded verbatim on read — nothing synthesized (mirrors the prediction store's migration-parity rule) |
| Risk | Schema-drift refusal is DELIBERATE: an operator editing the SQL breaks open with a typed corruption error — this is the fail-closed direction and must be kept |

**What the owner must state (one sentence):** `D-A2-2: ratify the four-table
append-only schema + pinned-digest migrations as specified; changes to the
pinned SQL require a new recorded owner act.`

**Consequence of deferral:** no tables are created at runtime; the in-memory
stores keep their exact current shapes.

---

## 3. D-A2-3 — Retention policy

**Decision question:** "May anything ever be deleted or expire?"

**RECOMMENDED (and the only option consistent with the repo's own
contracts): append-only, NO silent deletion.** Exported constant:
`RETENTION_POLICY = "APPEND_ONLY_NO_SILENT_DELETION__PURGE_IS_OWNER_GATED"`
(identical wording to `prediction_store.py`). Invalidation stays a LABEL
recorded as a NEW ledger record (`AI2RunRecord` status `INVALIDATED`), never
a rewrite or delete — this is already the in-memory contract (`AI2RunLedger`
has no update/delete path; `test_ledger_append_only_shape` pins it) and
persistence must not weaken it.

| Consequence | Detail |
|---|---|
| Growth | Unbounded file growth is ACCEPTED BY DESIGN (research evidence); the only size lever is the owner's backup/archival policy (D-A2-6), never in-place deletion |
| Invalidated runs | Remain in the ledger forever with their invalidation record attached — the audit trail is the point |
| Registry eviction | The in-memory 128-candidate bounded capacity is a REGISTRY behavior; if persisted, eviction must be replaced by explicit owner-approved archival, not silent deletion |
| Risk | Disk exhaustion if the owner never archives; mitigated by monitoring, not by silent purging |

**What the owner must state (one sentence):** `D-A2-3: retention = append-only,
no silent deletion (purge owner-gated); archival policy = <stated or "none
at this time">.`

**Consequence of deferral:** append-only is the default the prototype ships
with; no purge path exists in code regardless.

---

## 4. D-A2-4 — Idempotency / duplicate-detection persistence

**Decision question:** "Is the `classify_duplicate` key space persisted, so
duplicate detection survives restart?"

**RECOMMENDED: persist it.** Table `ai2_duplicate_keys` carries the
(task, input_snapshot_sha256) pairs with the first claimant `record_id`:
- identical re-append (same key + same record) = idempotent no-op;
- same key claimed by a DIFFERENT record = typed refusal
  (`duplicate_key_conflict`);
- `classify_duplicate` semantics are UNCHANGED (labels only, never blocks);
  persistence only makes the label input durable across restarts.
Consequences: duplicate detection becomes restart-stable (the current
in-memory behavior resets every process start — an honest gap disclosed
today); risk: the duplicate-key table grows one row per distinct question
snapshot (bounded by real usage; no purge per D-A2-3).

**What the owner must state (one sentence):** `D-A2-4: persist the
duplicate-detection keys as specified; on conflict the store refuses
fail-closed.`

**Consequence of deferral:** duplicate detection stays process-local
(current behavior, currently disclosed).

---

## 5. D-A2-5 — Activation authority (separate from the execution gate)

**Decision question:** "Who may turn persistence on, and does it interact
with `AI2_ENABLED`?"

**RECOMMENDED: two independent gates, explicitly named.**
1. `AI2_ENABLED` (default `0`, config.py line ~118) remains THE execution
   gate — untouched by this wave and by any persistence decision. It
   governs whether generation RUNS, never where records go.
2. Persistence activation is a SEPARATE owner act (a recorded decision row +
   an explicit wiring change), mirroring the AI-3 precedent's "no runtime
   auto-wiring" rule: the dormant adapter has NO factory, NO settings
   binding, NO environment read; nothing in `app/services` or `app/api`
   imports it (test-pinned). Activation = one recorded owner act + one
   reviewed wiring patch that introduces the import.

| Consequence | Detail |
|---|---|
| Blast radius | Activation cannot silently enable execution, and enabling AI-2 cannot silently enable persistence |
| Dormancy proof | Structural (import-graph test) + behavioral (no settings/env reads in the adapter), both pinned by tests |
| Risk | An operator may believe persistence is active when it is not — mitigated by the posture disclosure string, which must keep saying "in-memory-only" until activation is recorded |

**What the owner must state (one sentence):** `D-A2-5: persistence
activation = <owner act reference, date>; AI2_ENABLED remains the sole
execution gate; the two gates stay independent.`

**Consequence of deferral:** adapter stays dormant; execution stays gated by
`AI2_ENABLED=0` by default; nothing changes.

---

## 6. D-A2-6 — Backup / restore policy

**Decision question:** "What backup/restore discipline is ratified?"

**RECOMMENDED (mirrors `prediction_store.py`, implemented in the dormant
prototype):**
- **Verified backup:** SQLite backup API → `PRAGMA integrity_check` on the
  copy → SHA-256 + byte size recorded with the artifact → `verified: True`.
- **Restore-refuses-unverified:** the source is verified BEFORE it replaces
  the live file: existence → integrity check → pinned schema-digest match →
  every row digest re-verified → counts captured; any failure raises
  `AI2LedgerCorruption` with a stable reason (`restore_source_missing`,
  `restore_source_corrupt`/`restore_source_unreadable`,
  `restore_schema_digest_mismatch`, `restore_row_digest_mismatch:<table>`)
  and the live store is left untouched. Restore drills are a required
  acceptance test (AI-3 evaluation L4 lesson carried over).
- Backup cadence/copies/offsite are OWNER POLICY VALUES — no source states
  them; inventing one is forbidden (UNKNOWN-WITH-REASON, as the AI-3 packet
  recorded for the same question).

**What the owner must state (one sentence):** `D-A2-6: ratify verified
backup + restore-refuses-unverified as implemented; backup cadence/copies/
offsite = <stated values>.`

**Consequence of deferral:** the discipline exists in code (dormant) but no
backup schedule exists; restart loss (D-A2-1 deferral) remains the standing
recovery story.

---

## 7. D-A2-7 — Rollback and migration reversal

**Decision question:** "How is persistence rolled back, and who may drop
tables?"

**RECOMMENDED: rollback is owner-only; there is NO auto-migration and NO
automatic reversal.**
- Dropping/truncating any `ai2_*` table is an OWNER-ONLY act performed
  directly on the database file with a recorded decision; the adapter
  exposes NO drop/truncate/purge API (structural: not in `dir()`).
- Un-wiring persistence (reverting the activation wiring) must be a recorded
  owner act too; the data file is left intact for re-attachment (append-only
  means a re-opened store resumes, never rebuilds).
- Schema rollback = restoring a verified backup taken before the offending
  migration (D-A2-6 discipline); forward migrations are pinned-digest and
  additive, so they are never auto-reversed.
- Risks: an operator with file access can still destroy data outside the
  API — file-permission discipline is part of the D-A2-5 activation act;
  WAL sidecar files (`-wal`/`-shm`) must travel with the main file in any
  manual move (the restore path removes stale sidecars itself).

**What the owner must state (one sentence):** `D-A2-7: rollback/drop =
owner-only manual acts with recorded decisions; no auto-migration reversal;
restore-from-backup is the sanctioned recovery path.`

**Consequence of deferral:** nothing to roll back — the adapter stays
dormant.

---

## 8. Cross-cutting non-viable class (applies to every decision)

Same as the AI-3 packet's recorded class: network/replicated stores, cloud
object storage, and any shared production database — they presuppose
deployment facts (hosting, network, multi-tenancy) that no source
establishes. Anything placing AI-2 run records under a retention/purge
policy contradicts D-A2-3 and the ledger's own append-only contract. If the
owner names an option from this class, a new evidence pass (not this
packet) is required first.

---

## 9. What is already prepared (this wave — pre-decision kit only)

Authorized pre-decision work; NO storage engine is ACTIVATED and NO owner
decision is assumed anywhere in the kit:

1. **Dormant prototype adapter** — `backend/app/data/ai2_ledger_sqlite.py`
   (`DurableAI2LedgerStore`): SQLite WAL + `synchronous=FULL` +
   `busy_timeout` + `foreign_keys=ON`; pinned-digest migrations; append-only
   inserts for run records, candidate records, and duplicate keys, each with
   a per-row SHA-256; full-row verification fail-closed at open; verified
   backup; restore-refuses-unverified; typed errors
   (`AI2LedgerStoreError`, `AI2LedgerCorruption`); NO settings/env reads,
   NO factory, NO runtime caller.
2. **Dormancy pins** — `backend/tests/test_ai2_persistence_kit.py`: import
   -graph walk proving no `app/services/*.py` or `app/api/*.py` file imports
   the adapter; `AI2_ENABLED` default-byte pin (`_env_bool("AI2_ENABLED",
   "0")`); adapter exposes no update/delete/purge surface.
3. **Roundtrip/tamper/backup drills** — same test file: append-reopen-read
   equality, per-row digest tamper → fail-closed reopen refusal, verified
   backup → destructive restore → byte-identical read-back, restore refuses
   missing/corrupt/tampered/schema-mismatched sources.
4. **This packet** — the D-A2-1…D-A2-7 decision list itself.

The kit deliberately stops at the adapter boundary: wiring it into the
service (and choosing the file path) is exactly what D-A2-1 + D-A2-5 gate.

## 10. Acceptance tests ANY activated adapter must pass

1. Append-only round-trip: record → store → reopen → byte-identical decode
   (model equality) across process restart.
2. Immutability negatives: no update/delete/purge path exists on the adapter
   surface; UPDATE/DELETE via raw SQL is an operator act outside the contract.
3. Tamper evidence: any row payload/digest mutation → fail-closed reopen
   refusal naming the table.
4. Duplicate semantics preserved: `classify_duplicate` labels unchanged;
   persisted keys idempotent on identical re-append, conflicting on
   different records.
5. Backup/restore drill: verified backup → destructive restore → full
   re-verification (closes the AI-3 L4 lesson for AI-2).
6. Gate independence: with `AI2_ENABLED=0` nothing executes and nothing is
   written; persistence state changes never flip the execution gate.

## 11. Execution gate

Implementation of ACTIVATION (wiring, path selection, operational cutover)
starts ONLY after D-A2-1…D-A2-7 are recorded by the owner. Until then: the
in-memory stores, this packet, the dormant adapter, and its tests stand as
prepared material — none of it constitutes, upgrades to, or presumes a
decision, and NO production persistence is activated by this wave.
