# AI-3 PERSISTENCE IMPLEMENTATION PLAN — CONDITIONAL ON OWNER DECISIONS D1–D7 (PREPARE ONLY)

> ## ⚠️ CURRENCY UPDATE — 2026-11-08 (completion stage; historical text below PRESERVED verbatim)
>
> **This document's "D1–D7 ALL PENDING / Adapter BLOCKED" statements describe the state
> as of 2026-11-02 BEFORE the owner's decisions were recorded. They are kept below as
> history; the current state is:**
>
> | Item | Current state (2026-11-08) | Evidence (date + SHA) |
> |---|---|---|
> | D1 engine class | **DECIDED 2026-11-02: SQLite-WAL + content-addressed blobs** (the Option-1 incumbent candidate WAS selected by the owner's explicit 2026-11-02 delegation) | `docs/active/OWNER_DECISIONS_RECORDED_2026-11-02.md` (answer key `D1=A`), recorded on top of `209ec620…` chain; implementation commit `ad5d978` (2026-11-08) |
> | D2 deployment target | **DECIDED 2026-11-02: DEFER, dated 2026-11-02** — target-machine evidence collection stays owner-executed (R-2) | same register, `D2=DEFER-2026-11-02` |
> | D3 immutability class | **DECIDED 2026-11-02: per-class retention table** — episodic PERMANENT (no-purge), lesson history PERMANENT (retire ≠ delete) | same register, `D3=TABLE-BELOW` |
> | D4 access control + key | **DECIDED 2026-11-02: OS keyring + AES-256-GCM at rest**, env override `RADAR_RESEARCH_MEMORY_KEY`, fail-closed without a key | same register, `D4=OS-KEYRING+AESGCM` |
> | D5 backup/retention/DR | **DECIDED 2026-11-02: local destination `data/backups/research-memory/`, daily cadence, keep=14**; offsite deferred until owner provides destination | same register, `D5=LOCAL-DAILY-KEEP14` |
> | D6 access model | **DECIDED 2026-11-02: single-user** | same register, `D6=SINGLE-USER` |
> | D7 RPO/RTO | **DECIDED 2026-11-02: RPO ≤ 24h, RTO ≤ 15 min** | same register, `D7=RPO24h-RTO15m` |
> | Adapter implementation | **IMPLEMENTED** — `app/data/research_memory_sqlite.py` (`SqliteWalResearchMemoryStore`: WAL, `synchronous=FULL`-class discipline, per-row SHA-256 tamper evidence verified at open, AES-256-GCM payloads, verified backup + fail-closed restore drill, restart recovery, no delete/update/purge — AST-pinned) registered in the acceptance-scaffold factory | commit `ad5d978`; suite `test_research_memory_sqlite_adapter.py` |
> | Audit-trail carrier | **IMPLEMENTED** — `app/data/memory_access_audit_sqlite.py` (`DurableMemoryAccessAuditTrail`: append-only hash-chained ledger, row digests, full-chain re-verification at open, corruption ⇒ typed `MemoryAuditStoreCorruption`, verified backup/restore) | WAVE-AI WP-G commit `14836a4`; suite `test_memory_audit_sqlite.py` |
> | REAL application-path integration | **DONE** — `app/services/research_memory_service.py` factory defaults to the DURABLE sqlite backend on the real app cycle; `/api/v10/memory` router (posture/episodic/lessons/integrity/audit/backup); every operation audited OK-or-REFUSED | owner directive 2026-11-08 §3 is the explicit dated act ordering real integration; commit `ad5d978` |
> | Runtime verification at HEAD `2e6d0fb4…` | **RE-VERIFIED 2026-11-08** — clean-checkout AI-3 suite 186 passed; independent behavioral probe 10/10 PASS (cross-process restart recovery, verified backup → destroy → restore, per-row tamper ⇒ gate CLOSED + row refused, keyless ⇒ typed refusal, invalid key ⇒ fail-closed, garbage DB file ⇒ typed `db_unreadable` refusal, SIGKILL mid-process ⇒ WAL recovery, two-directory isolation, audit-chain tamper ⇒ reopen refused) | completion-stage execution record §AI-3 |
> | Still OWNER-GATED (unchanged) | D2 target-machine evidence drill (R-2); D5 automated daily cadence (needs scheduler authorisation OA-4/R-6 — nothing scheduled) and offsite destination/credentials | OA register |
>
> **Everything below the horizontal rule is the original pre-decision plan, preserved
> byte-for-byte as history (per the documentation-currency rule: never delete past
> status statements — supersede them with a dated pointer).** Sections 3–5 below were
> the decision→variant mapping used to implement the selected variants; the implemented
> adapter matches the Option-1/D1 column of §3.1 plus the §4 cross-cutting requirements.

---

**D1–D7 ALL PENDING.** Per `AI3_PERSISTENCE_DECISION_PACKET.md` line 3:
"**ALL SEVEN DECISIONS PENDING — no owner decision recorded as of 2026-11-02;
none assumed; the PREFERRED-CANDIDATE ranking in
`AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` is an engineering ranking, not a
decision.**"

**Execution gate (binding):** `AI3_PERSISTENCE_DECISION_PACKET.md` §11
(lines 452–455): "Implementation of the persistence adapter starts ONLY
after the required decisions are recorded by the owner in the decision
register. Until then: the contract layer, the in-memory reference store,
the fixture/acceptance kit above, and the PREFERRED-CANDIDATE evidence
stand as prepared material — none of it constitutes, upgrades to, or
presumes a decision."

This plan is therefore a CONDITIONAL plan only. Section 3 maps every option
of every decision axis (D1–D7) to what the implementation branch would look
like **if** that option is chosen — a decision → variant mapping, with no
option selected, assumed, or pre-recorded, and no new engineering
recommendation beyond what the decision brief, the candidate evaluation,
and the packet already record. Section 4 states the cross-cutting
requirements that bind every variant identically. Section 5 maps each
acceptance criterion to exact test ids in the executable acceptance scaffold
(`backend/tests/test_ai3_acceptance_scaffold.py`), which runs **today**
against the in-memory reference adapter only.

Companion files (this task, additive only — no existing file modified):
- `backend/tests/test_ai3_acceptance_scaffold.py` — parameterized
  acceptance suite over the `ResearchMemoryStore` Protocol (plug-in point
  for any future adapter; see §6).
- This document.

---

## 1. Status and execution gate

| Item | State | Source |
|---|---|---|
| D1 engine class | PENDING | packet line 3; packet §1 |
| D2 AI-runtime deployment target | PENDING (additionally blocked upstream at P3.43) | packet line 3; packet §2 (lines 116–126) |
| D3 immutability guarantee class (+ periodic-audit sub-question) | PENDING | packet line 3; packet §3 |
| D4 access-control model + episodic readers | PENDING | packet line 3; packet §4 |
| D5 backup/retention/DR policy | PENDING (operational gate, not waivable) | packet line 3; packet §5; evaluation §7 D5 |
| D6 blob-store location + size ceilings | PENDING (non-blocking for candidate designation only) | packet line 3; packet §6; evaluation §7 D6 |
| D7 adapter timing | PENDING (deferral carries no identified risk) | packet line 3; packet §7; evaluation §7 D7 |
| Persistence adapter implementation | **BLOCKED — starts ONLY after owner decisions are recorded in the decision register** | packet §11 (lines 452–458); brief §D closing (lines 178–180) |
| Contract layer (`research_memory.py`), store interface + reference adapter (`research_memory_store.py`), fixture kit, store-level tests, THIS plan + acceptance scaffold | delivered as pre-decision kit; unchanged by any pending decision | packet §9 (lines 388–431) |

Currency (recorded in the packet, lines 46–51): G2 formally PASSED
(owner-recorded 2026-10-29T19:58:32Z, CONSOL-GOV-37); binding AI-2
restrictions unchanged (`AI2_ENABLED=0`, `verified=False`,
`execution_mode=SYNTHETIC_OR_PAPER`; live credentials/enablement CLOSED AS
NOT GRANTED, GOV-41 Phase 2). That reconciliation assumes none of D1–D7.

## 2. Sources and citation discipline

Every claim below carries its source: brief §A constraints (A1–A12), brief
§B option analysis (B-labelled), brief §C unknowns (C1–C5), brief §D
decision definitions, candidate evaluation §N, decision packet §N with line
numbers. Where no source states something, the text says
UNKNOWN-WITH-REASON. No numbers are invented anywhere in this plan; any
future numeric threshold is an owner-ratifiable numeric-ceiling-class
decision (same class as D6 and the P0 numeric-ceiling ratification, packet
§6 lines 306–310).

The seven comparison dimensions used throughout (packet §0 fact 6, lines
52–57): (a) operating cost, (b) Windows/Electron compatibility,
(c) immutability strength, (d) point-in-time query behavior, (e)
backup/restore impact, (f) concurrency limits, (g) migration+test cost.
They are the owner-facing reorganization of the brief's §B comparison rows
and the evaluation's §2 requirement table; they add no new engineering
claims.

## 3. Per-decision-axis conditional plan (D1–D7) — decision → variant mapping

Binding invariants for EVERY variant of EVERY decision (packet §0 facts
2–3, lines 32–40; §8 lines 377–384; brief §B preamble):

- I-1 Any adapter WRAPS — never replaces — the delivered in-memory
  contracts (`EpisodicRunArchive`, `SemanticLessonStore`) behind the
  append-only `ResearchMemoryStore` Protocol (reuse rule 02:107-112).
- I-2 No update/delete/retention-purge/rewrite path may exist for episodic
  evidence (A3), and nothing expires out of the archive (A11) — regardless
  of engine. Any option placing episodic artifacts under a
  retention/purge policy is non-viable outright (packet lines 32–36).
- I-3 Network/replicated stores, cloud object storage, and any shared
  production database remain non-viable today (presuppose deployment facts
  no source establishes — brief §B "Explicitly non-viable today"; packet §8).
  If the owner names an option from this class, a new evidence pass (not
  this packet, not this plan) is required first (packet §8, lines 383–384).
- I-4 Fail-closed honesty: explicit misses (`None`/empty, never
  fabricated records), refused conflicting appends (contract `ValueError`),
  digest verification returning refusal records that never raise raw
  exceptions (`research_memory_store.py` structural guarantees; §4.2 here).

### 3.1 D1 — Engine class: embedded single-operator store vs server-class

Decision question (brief §D1, verbatim, packet lines 63–65): "single-operator
embedded store (Option 1 or 2) vs server-class deployment (Option 3) —
driven by the deployment target decision below."

| Variant | Adapter topology | Storage layout | Migration surface |
|---|---|---|---|
| **Option 1 — Embedded SQLite (incumbent engine) + filesystem blob store** (packet lines 69–74; evaluation §1; PREFERRED CANDIDATE — a ranking, NOT a decision) | Adapter module implementing the `ResearchMemoryStore` Protocol over SQLite + blobs, wrapping the in-memory contracts (evaluation §5 M1 names `app/data/research_memory_store.py` as the planned module location); in-memory classes remain the canonical behavior reference | Artifacts content-addressed on disk (sha256 filename, matching the `ArtifactRef`/`input_snapshot_sha256` contract); append-only index tables in the existing `shekar.db` (WAL, `synchronous=NORMAL`); planned tables: episodic_artifacts, semantic_lessons, lesson_versions (evaluation §5 M2) | Schema via the established `PRAGMA user_version` migration mechanism (M2); optional deny-triggers (M3, = D3 variant); append-only audit-ledger table (M5); backup integration reusing the existing WAL-consistent routine (M6); testable in-place with tmp-path fixtures (packet line 93) |
| **Option 2 — Pure filesystem: append-only JSONL + content-addressed blobs** (packet lines 75–78; brief §B Opt 2) | Same Protocol adapter; engine-specific carrier is files only — no DB engine anywhere; matches the event-log option noted as a future additive option in the AI3-M audit (AI3M-02, packet lines 77–78) | Episodic records appended to per-run JSONL segments; lessons in an append-only log; blobs content-addressed on disk; indexes rebuilt or kept as sidecar files (brief §B Opt 2) | No DB migration; instead a writer discipline (fsync policy, rotation) and segment format-version marker (brief §B Opt 2; §4.6 here); query performance and integrity tooling hand-rolled (packet line 93) |
| **Option 3 — Server DB (PostgreSQL) (+ object store for blobs)** (packet line 79; brief §B Opt 3) | Adapter over a server-class DB plus object store for blobs; same Protocol surface | Relational tables + object-store blobs; content addressing preserved by the same sha256 discipline (§4.1) | Heaviest: service provisioning, schema creation, grants/roles (D4 interacts), test containers or a live server in CI (packet line 93; brief §B Opt 3) |

Non-viable regardless of engine (brief §B; packet lines 80–83): network/
replicated stores, cloud object storage, any shared production database,
and anything placing episodic artifacts under retention/purge (I-2/I-3).

Deferral consequence (packet lines 105–110): adapter stays BLOCKED;
contract layer, tests, and G2 readiness of AI-3's delivered scope
unaffected; per evaluation §7, D1-class finalization also waits on D2.

### 3.2 D2 — Deployment target of the AI runtime

Decision question (brief §D2, verbatim, packet lines 116–118): "deployment
target for the AI runtime (Windows host? Docker? Electron-bundled?) —
currently BLOCKED upstream at P3.43 launch gates."

The brief and evaluation do NOT compare the targets against storage
dimensions target-by-target; most cells are honestly UNKNOWN-WITH-REASON
(packet lines 120–126). The binding recorded facts: D2 is upstream-blocked
at P3.43; it "determines engine class, access-control model, and whether
the embedded candidate is final" (evaluation §7 D2, packet lines 125–126);
Option 1/2 engines carry "low" Windows deploy burden, Option 3 "high"
(packet lines 88–93); the Electron runtime is named among the P3.43 launch
gates (packet line 131).

| Variant | Conditional implementation branch (no new claims; per-target work = executing §4 cross-cutting verification on that target) |
|---|---|
| Windows host | Owner-gated target class (brief A12, packet line 131). Branch: §4.7 Windows path/packaging verification executed on the Windows host; embedded engines (Opt 1/2) carry recorded "low" deploy burden; D4 default class is file-permission single-operator unless the owner says otherwise in D4 |
| Docker | UNKNOWN-WITH-REASON: no source establishes container deployment for this runtime (packet line 130). Branch: §4.7 executed inside the container image; volume/backup policy for containers UNKNOWN-WITH-REASON (packet line 134) — owner must state it (D5) |
| Electron-bundled | Electron runtime is named among the P3.43 launch gates (packet line 131). Branch: §4.7 executed for the packaged app (bundle data directory, long-path policy); bundle-data backup policy UNKNOWN-WITH-REASON (packet line 134) |

Deferral consequence (packet lines 142–146): persistence adapter stays
BLOCKED; D2 additionally blocked upstream at P3.43 today, so no AI-3 scope
beyond the delivered contract layer is held up by D2 alone.

### 3.3 D3 — Immutability guarantee class (+ periodic hash-audit sub-question)

Decision question (brief §D3, verbatim, packet lines 152–154):
"immutability guarantee class required (application-enforced vs
storage-enforced vs format-enforced) and whether hash-verification audits
should be periodic."

| Variant | Enforcement mechanism | Adapter topology delta | Migration surface |
|---|---|---|---|
| Application-enforced (Option 1 baseline) | INSERT-only code paths behind the append-only Protocol API; SQLite cannot structurally forbid UPDATE without triggers (packet lines 159–161; brief §B Opt 1 — "the only inherent tension"; eval L1) | None beyond the D1 adapter | None beyond the adapter itself (packet line 175) |
| Trigger-enforced inside SQLite (evaluation §5 M3) | Deny-triggers (`CREATE TRIGGER ... BEFORE UPDATE/DELETE → RAISE`) on episodic tables; closes L1 at storage level inside SQLite; plus hash columns verified by an audit query (packet lines 162–165; eval §2 Immutability mitigation stack) | Same D1 Option-1 adapter; triggers are the additive layer | One additive trigger migration step + trigger tests (packet lines 175, 181; eval §5 M3, §6 test 1); trigger definitions live in schema dumps (packet line 179) |
| Format-enforced (Option 2) | Append-only is the file format itself — "strongest natural fit"; rewriting requires deliberate, visible, diffable file replacement (packet lines 166–168; brief §B Opt 2) | Same D1 Option-2 adapter | Simplest mechanism; hand-rolled integrity tooling (packet lines 166–168, 181) |
| Storage-enforced server-class (Option 3) | REVOKE UPDATE/DELETE + append-only grants — strongest of the three classes; requires the Option 3 deployment the owner has not made (packet lines 169–171; brief §B Opt 3) | Same D1 Option-3 adapter | Grants + roles shipped with the Option-3 provisioning surface (packet lines 169–171, 175–181) |

Sub-question (packet lines 183–189): whether hash-verification audits are
PERIODIC is an owner answer; the cadence is UNKNOWN-WITH-REASON (no cadence
exists in any source; inventing one would violate the no-invented-numbers
rule). `verify_integrity` (store kit) is the deterministic primitive such
audits would call.

Engine-level negatives required for whichever class is chosen (packet §10
test 1): UPDATE/DELETE on episodic tables refused (by trigger / by grant /
by visible-format check / by code-path audit) and the adapter exposes no
update/delete path (structural — scaffold AC-1/AC-2 prove the structural
half today; the engine half is adapter-module scope, §5 table B here).

Deferral consequence (packet lines 196–199): adapter stays BLOCKED; without
D3 the adapter's acceptance claim cannot name its own guarantee class
(evaluation §6 test 1 depends on the chosen class).

### 3.4 D4 — Access-control model and who may read episodic evidence

Decision question (brief §D4, verbatim, packet lines 205–206): "access-control
model + who may read episodic evidence (A8 approval state interacts with
this)."

| Variant | Enforcement | Adapter topology delta | Migration surface |
|---|---|---|---|
| File-permission class, single-operator (incumbent assumption) | File perms + sha256-column verification; "adequate for the single-operator deployment the repo actually targets (A12, Windows/Electron single host); weak for any multi-user/remote deployment" (packet lines 211–214; eval §2 Access control) | None — the Protocol surface stays authorization-free; enforcement lives at the environment layer | Minimal (packet line 230); documented file-permission enforcement = packet §10 test 8 reality check |
| Server-class roles/RLS (Option 3) | "strongest (roles, row-level security, audit extensions) — relevant only if multi-user/remote deployment is actually decided" (packet lines 215–217; brief §B Opt 3) | Roles/RLS layered on the Option-3 carrier | Heaviest (packet line 230); permission state adds restore surface (UNKNOWN-WITH-REASON: no source details it, packet line 228) |

A8 interaction: approval state is carried by the records themselves
(`02:198`; provenance fields A6); the reader-authorization matrix does not
exist in any document and must come from the owner (packet lines 232–236).
Multi-user vs single-operator deployment is an open unknown (brief §C2);
"whether multi-user is ever required is UNRESOLVED (D2/D4) — this is the
candidate's main conditional dependency" (evaluation §2, packet line 220).

Deferral consequence (packet lines 242–244): adapter stays BLOCKED;
evaluation §7: D4 — "Multi-user requirements would reopen Option 3."

### 3.5 D5 — Backup / retention / DR policy

Decision question (brief §D5, verbatim, packet lines 250–252): "backup/
retention/DR policy (cadence, copies, offsite?) — noting the archive itself
must never be purged (A3/A11); backups are replication, not retention."

| Variant | Content | Adapter/ops delta |
|---|---|---|
| Ratify the incumbent routine as the baseline | WAL-consistent backups to `data/backups` exist as shipped code (A12; eval §1/§2 Recovery); the restore drill becomes a required acceptance test (eval §5 M6, §6 test 6; L4: recovery designed-in but UNDEMONSTRATED — no restore drill, no backup artifact yet) (packet lines 256–260) | Zero new mechanism; drill = §4.4 |
| Stricter owner policy (values TBD by owner) | Cadence/copies/offsite are pure owner policy — brief §C4: backup cadence/retention policy "exists as code for SQLite; policy is owner's". No cadence, copy-count, or offsite requirement exists in any source; any number would be invented (packet lines 261–264) | Same drill, plus the owner's stated cadence/copies/offsite execution |

Binding constraint on every variant (packet lines 268–270): the episodic
archive itself is NEVER purged — backups are replication, not retention
(A3/A11; framing fact 2). Deferral is recorded as an operational gate, not
waivable by general instruction (evaluation §7 D5).

Deferral consequence (packet lines 287–289): adapter stays BLOCKED for
OPERATIONS; no AI-3 contract-layer scope is affected.

### 3.6 D6 — Blob-store location and size ceilings

Decision question (brief §D6, verbatim, packet lines 295–298): "blob-store
location (inside/outside repo tree) and any size ceilings the owner wants
to ratify (the P0 numeric-ceiling ratification in the acceptance package is
the same class of decision)."

| Variant | Conditional branch |
|---|---|
| Inside the repo tree | Corpus position: SILENT (brief §C5). Branch: blob root resolved from owner configuration; content addressing (sha256 naming) identical to the outside variant (packet line 316); all other cells UNKNOWN-WITH-REASON (packet lines 314–320: repo-growth/maintenance, Windows compatibility, backup pairing, test cost) |
| Outside the repo tree | Same silence; the choice is the owner's environment decision (brief §D6). Branch: identical layout and content addressing; location recorded in configuration; backup pairing must be stated by the owner (D5) |
| Size ceilings | No numeric ceiling exists in any source; ratifying one is the owner's numeric-ceiling-class decision (packet lines 306–309). Branch: ceilings, if ratified, become pre-append admission checks at the adapter boundary — refusal (fail-closed), never a deletion |

Deferral consequence (packet lines 326–329): adapter stays BLOCKED, but D6
is explicitly non-blocking for the candidate designation (evaluation §7 D6)
— deferral delays adapter implementation, not the standing candidate
evidence.

### 3.7 D7 — Timing: decide now vs after G2

Decision question (brief §D7, verbatim, packet lines 335–338): "timing —
decide now (pre-G2, to make the adapter testable in synthetic runs) vs
after G2 (risk: none identified for deferral, since the contract layer is
complete and the adapter is additive either way)." Currency note (packet
lines 340–344): G2 has since been formally PASSED (owner-recorded
2026-10-29T19:58:32Z, CONSOL-GOV-37); the question stands as written.

| Variant | Conditional branch |
|---|---|
| Decide now | Adapter becomes testable in synthetic runs (packet lines 346–350; evaluation §5 M7: synthetic-only fixtures, no live data, `02:202` pre-G2 class). Branch: §3.1–§3.6 variants materialize immediately after the remaining decisions are recorded; acceptance scaffold gains the adapter factory (§6) |
| After G2 / later | "Engineering decision safely deferrable" (evaluation §7); deferral risk: "none identified" (brief §D7). Branch: THIS plan, the scaffold, and the contract layer stand as prepared material; nothing decays — the adapter is additive whenever taken |
| Not an option | Treating the PREFERRED-CANDIDATE designation as the decision — R3 explicitly reserves the final architecture decision (packet lines 352–354) |

Deferral consequence (packet lines 369–373): explicitly recorded as carrying
NO identified risk; the contract layer, tests, and G2 readiness of AI-3's
delivered scope are unaffected; per R3, none of D1–D7 blocks AI-6 or any
other independent work.

## 4. Cross-cutting engineering requirements (independent of D1–D7)

These bind EVERY variant selected above, identically. They are requirements,
not options; none of them pre-selects any D1–D7 option.

### 4.1 Canonical JSON serialization + sha256 content addressing

- Every persisted record is serialized ONLY through the canonical form:
  `canonical_research_memory_json` (sorted keys, explicit separators,
  UTF-8 text, `allow_nan=False`, Decimal-as-string) — byte-identical across
  repeated calls, independent constructions, and insertion orders
  (test-pinned; `research_memory_store.py` §"Canonical serialization").
- Digests are SHA-256 over the UTF-8 encoding of the canonical text only
  (`sha256_hex`); no digest is ever computed over non-canonical bytes.
- Content addressing: blob filenames and integrity columns use lowercase
  hex sha256, matching the `ArtifactRef.sha256` /
  `input_snapshot_sha256` contract fields (evaluation §2 Provenance
  SUPPORTED; §5 M4: content-addressed blob writer with fsync-on-close).
- Two records with different content must never share a digest; digest
  equality implies canonical byte equality (scaffold AC-4).

### 4.2 Append-only + integrity verification (fail-closed refusal records)

- The `ResearchMemoryStore` Protocol has NO update/delete/purge/rewrite
  member and none may be added; the only state-changing operations are
  `append_episodic` and `register_lesson` (Protocol docstring; scaffold
  AC-1/AC-2 pin this structurally).
- NO purge / NO retention-expiry path may exist or be introduced for
  episodic evidence in ANY variant (A3/A11; packet lines 32–36, 198–204;
  scaffold AC-2).
- Verification is fail-closed by returning frozen refusal records
  (`ResearchMemoryIntegrityReport` with `verify_ok=False` +
  `mismatched_entry_ids` / `missing_entry_ids` / `refusal_reasons`);
  `verify_integrity` NEVER raises raw exceptions (scaffold AC-5, AC-10).
- Refused operations leave the store unchanged (conflict refusals are
  atomic no-ops — scaffold AC-3); unknown ids are explicit misses
  (`None`/empty), never fabricated records or `KeyError` (scaffold AC-20).
- Engine-level negatives (UPDATE/DELETE refused at the engine) remain
  binding per packet §10 test 1 and are executed in the adapter's own test
  module per the D3 variant chosen.

### 4.3 Point-in-time retrieval by publication/run time

- PIT views are pure cutoff filters over explicitly recorded timestamps:
  `recorded_at_utc` for episodic artifacts, `created_at_utc` for semantic
  lessons — mirroring `available_at()` / `lessons_active_at()` 1:1 (A5;
  `02:142`; eval §2 PIT SUPPORTED). No clock is ever read inside the store;
  all timestamps are passed in (contracts' clock-free discipline).
- Look-ahead guard: records recorded after a cutoff are invisible to
  PIT queries at that cutoff (packet §10 test 3; scaffold AC-6).
- The adapter must preserve the contract PIT semantics exactly — indexed
  (Option 1/3 carriers) or scan-based (Option 2 carrier) — with identical
  observable results (scaffold AC-6/AC-7 prove semantics; carrier choice
  is D1's business only).

### 4.4 Backup / restore / crash-recovery rehearsal

- Restore drill (closes evaluation L4): WAL-consistent (or carrier-
  equivalent) backup → destructive restore → full re-verification by hash
  of every record (packet §10 test 6; eval §5 M6). Required for ANY
  variant; drill evidence recorded append-only.
- Crash-recovery rehearsal: kill during write → reopen → engine recovery
  → no partial record accepted (packet §10 test 7). Engine-level;
  the engine-neutral all-or-nothing contract it must satisfy is expressed
  and pinned TODAY by the scaffold (AC-8: a refused/failed append leaves
  the store with the record fully present and digest-clean, or absent —
  never partially formed).
- Backups are replication, not retention: no backup or restore step may
  purge, expire, or rewrite archive content (§3.5 binding constraint).

### 4.5 Concurrent-writer semantics

- The incumbent concurrency class is single-writer (WAL lock for Option 1;
  explicit single-writer discipline for Option 2; full multi-writer only
  for Option 3 "relevant only for a runtime that does not exist yet" —
  brief §B comparison; eval L5; brief §C2 keeps multi-user UNRESOLVED).
- Every adapter must DOCUMENT its concurrency class in its module
  docstring; the scaffold's concurrency test (AC-9) drives two threads
  through the documented single-writer discipline boundary (a lock owned
  by the harness) and proves: all events preserved, per-writer ordering
  preserved, no lost updates, conflicting appends refused with state
  unchanged. No multi-writer guarantee is asserted anywhere — that would
  invent a requirement the sources do not establish.

### 4.6 Migration + rollback rehearsal (forward + back)

- Forward migration and a rollback rehearsal are required acceptance
  evidence for whichever carrier is chosen: forward = apply the additive
  schema/format change (user_version step for Option 1; segment
  format-version marker for Option 2; engine schema for Option 3);
  rollback = restore the pre-migration consistent backup and re-verify by
  hash. Rollback of an append-only store is RESTORATION of prior state —
  history is never rewritten and nothing is purged (I-2).
- All migrations are additive (new tables/segments only; no UPDATE/DELETE
  statements anywhere — evaluation §5 M2); rehearsal evidence recorded
  append-only.

### 4.7 Windows path / Electron packaging compatibility

- No generated path may contain Windows reserved characters
  (`< > : " / \ | ? *`) or match a reserved device name — lowercase hex
  sha256 content-addressed names satisfy this by construction (§4.1).
- Case-collision safety on case-insensitive filesystems: hex is canonical
  lowercase everywhere; adapters must never re-case names.
- Long-path policy: the directory layout must keep a bounded path-depth
  budget so record paths stay well short of `MAX_PATH` without long-path
  enablement, and the adapter must document its depth budget; the actual
  long-path enablement policy on the owner's Windows target is an owner
  environment fact (A12: Windows-target deployment owner-gated, P3.43).
- Data-directory location comes from the existing data-dir settings
  (`app/core/config.py:126-128` per A12), never hard-coded; Electron
  packaging must verify the data directory resolves outside read-only
  bundle resources — verified on the D2 target at packaging time (the
  per-target steps in §3.2).
- These are verification requirements; no engine or layout is chosen by
  this subsection.

### 4.8 Performance envelope measurement points

No numeric envelope exists in any source (brief §C1: artifact volume/
retention horizon unmeasurable — no runtime exists). Therefore: the
following MEASUREMENT POINTS are defined and their values are measured and
recorded at adapter acceptance time; asserting any numeric threshold here
would be an invented number and is not done. Ratifying numeric ceilings is
an owner numeric-ceiling-class decision (same class as D6 / P0).

| Point | What is measured |
|---|---|
| P-1 | Episodic append throughput (appends/sec) at fixture scale and at a recorded synthetic scale |
| P-2 | PIT query latency (`episodic_available_at` / `lessons_active_at`) as a function of stored-entry count |
| P-3 | Integrity verification throughput (canonical digest computations/sec; full-archive verify wall time) |
| P-4 | Supersession/history query cost (`lesson_history`, `latest_lesson`) per lesson depth |
| P-5 | Backup duration (carrier-equivalent of the WAL-consistent routine) |
| P-6 | Restore + full hash re-verification duration (§4.4 drill) |

### 4.9 Non-viable class (restated, applies to every decision)

Packet §8 (lines 377–384), verbatim constraint class: network/replicated
stores, cloud object storage, and any shared production database — they
presuppose deployment facts (hosting, network, multi-tenancy) that no
source establishes. Also anything placing episodic artifacts under a
retention/purge policy violates A3/A11 outright, regardless of engine. If
the owner names an option from this class, a new evidence pass (not this
packet, not this plan) is required first.

## 5. Acceptance criteria → acceptance-scaffold test ids

Executable scaffold: `backend/tests/test_ai3_acceptance_scaffold.py`.
Parameterized tests carry the store-factory id in brackets; today the only
factory is `in_memory_reference` (`InMemoryResearchMemoryStore`). Any
future adapter plugs in as an additional factory (§6) and must pass every
parameterized (Tier A) test unchanged.

### Table A — criteria expressible at the store level (pinned today)

| AC | Acceptance criterion (source) | Test id(s) |
|---|---|---|
| AC-1 | Append-only structural: Protocol surface is EXACTLY the append/get/index/verify set; no update/delete path reachable (packet §10 test 1 structural half; A3) | `test_acc01_protocol_surface_exact_and_append_only` |
| AC-2 | NO purge / NO retention-expiry anywhere on the surface (A3/A11; packet lines 32–36, 198–204) | `test_acc02_no_purge_no_retention_expiry_structural_absence` |
| AC-3 | Append-only write semantics: identical re-append idempotent; conflicting content refused (`episodic_archive_conflict`) with state unchanged (contract refusal honesty) | `test_acc03_append_only_idempotent_and_conflict_refused_state_unchanged` |
| AC-4 | Canonical serialization round-trip byte-stability: stored record retrieves byte-identical; digest stable across re-serialization; Unicode-safe (packet §9 item 2; §10 test 2 store-level half) | `test_acc05_canonical_roundtrip_byte_stability_through_store`, `test_acc21_canonical_serialization_pure_determinism` |
| AC-5 | sha256 integrity verify: OK path; tamper detection fail-closed (refusal record, never raw exception); missing-entry (deletion) refusal; later appends legal | `test_acc07_verify_integrity_ok_and_later_appends_legal`, `test_acc08_verify_integrity_tamper_refused_fail_closed`, `test_acc09_verify_integrity_missing_entry_refused_fail_closed`, `test_acc22_verify_integrity_never_raises_on_corrupt_adapter` |
| AC-6 | PIT retrieval by recorded/created time: cutoff ordering, look-ahead guard, insertion-order views (packet §10 test 3; A5) | `test_acc10_pit_episodic_available_at_ordering_and_lookahead_guard`, `test_acc11_pit_lessons_active_at_ordering` |
| AC-7 | Episodic append → archive → semantic-lesson promotion flow: derivation cites archived artifacts only (traceability), supersession creates NEW versions, history never rewritten (packet §10 tests 4–5 flow half; D-AI-28) | `test_acc12_promotion_flow_episodic_to_lesson_citation_gate_and_supersession` |
| AC-8 | Crash-consistency (engine-neutral, in-memory expressible): invalid record refused before mutation; injected adapter failure all-or-nothing (crash-before-commit → absent; crash-after-commit → fully present + digest-clean); reopen/replay digest-clean (packet §10 test 7's engine-neutral contract) | `test_acc14_crash_consistency_refused_write_leaves_no_partial_state`, `test_acc15_crash_consistency_injected_adapter_failure_all_or_nothing`, `test_acc16_crash_consistency_reopen_all_records_digest_clean` |
| AC-9 | Concurrent appends from two threads under the documented single-writer discipline: all events preserved, per-writer ordering preserved, conflicting appends refused with state unchanged (§4.5) | `test_acc17_concurrent_append_two_threads_all_events_preserved`, `test_acc18_concurrent_conflicting_append_refused_state_unchanged` |
| AC-10 | Integrity refusal records are themselves append-only: frozen, byte-stable under re-derivation, ledger grows without rewriting earlier refusals, store ledger never shrinks | `test_acc19_integrity_refusal_records_frozen_and_append_only` |
| AC-11 | Provenance completeness blocks acceptance at the storage boundary: records with missing/invalid provenance are refused before any mutation (packet §10 test 5; 03:40; A6) | `test_acc13_provenance_completeness_blocks_acceptance_at_boundary` |
| AC-12 | Fail-closed explicit misses: unknown ids are `None`/empty, never fabricated records (Protocol fail-closed honesty) | `test_acc20_explicit_miss_fail_closed_no_fabricated_records` |
| AC-13 | Records frozen: retrieved records reject in-place mutation; integrity report frozen (A2/A3 at record level) | `test_acc04_records_frozen_no_update_in_place`, `test_acc06_integrity_report_shape_and_insertion_order` |
| AC-14 | Retirement is a NEW terminal version; history never rewritten (packet §10 test 4; A4) — reference-adapter tier (contract lifecycle is outside the Protocol surface by design) | `test_acc23_retirement_terminal_history_never_rewritten` |
| AC-15 | Composition honesty: the reference adapter delegates to — never reimplements — the contracts; views return contract records in insertion order (packet §9 item 1) | `test_acc24_reference_adapter_composes_contracts_by_delegation` |

### Table B — binding adapter-level acceptance tests (packet §10; engine-level, NOT expressible against the in-memory reference)

These remain BINDING for any concrete adapter and are executed in the
adapter's own test module when D1–D7 are decided (they cannot run today
without an engine, which the execution gate forbids):

| Packet §10 item | Test | Conditional form |
|---|---|---|
| §10-1 engine half | UPDATE/DELETE on episodic tables refused | trigger test (D3 trigger-enforced) / grant test (D3 storage-enforced) / visible-format check (D3 format-enforced) / code-path audit (D3 app-enforced) |
| §10-2 | Append-only round-trip byte-identical (hash match) across process restart | adapter restart test on the D1 carrier |
| §10-6 | Backup/restore drill: backup → destructive restore → full re-verification by hash (closes L4) | §4.4, D5 variant |
| §10-7 | Crash-recovery: kill during write → reopen → recovery → no partial record | §4.4, engine-level |
| §10-8 | Access-control reality check: file-permission (or chosen-class) enforcement documented | conditional on D2/D4 |
| D3 sub-question | Periodic hash-audit cadence (if owner answers "periodic: yes") | audit job calling `verify_integrity`; cadence stated by owner — UNKNOWN-WITH-REASON today |

## 6. Acceptance-scaffold contract (plug-in point for any future adapter)

`backend/tests/test_ai3_acceptance_scaffold.py` parameterizes over a
module-level registry:

```
STORE_FACTORIES: tuple[tuple[str, Callable[[], ResearchMemoryStore]], ...]
```

- Today it contains exactly one entry:
  `("in_memory_reference", <factory returning a fresh InMemoryResearchMemoryStore>)`.
- When owner decisions D1–D7 are recorded and an adapter is built, the
  adapter's integration adds ONE entry —
  `("<adapter_id>", <callable returning a fresh, empty adapter instance>)`
  — to `STORE_FACTORIES` in that NEW work; every Tier A test then runs
  against the new adapter automatically. No test body changes.
- Factory contract: returns a FRESH, EMPTY store satisfying the
  `ResearchMemoryStore` Protocol; construction is deterministic (no clock,
  no RNG, no environment reads — the fixture-kit discipline); all seeding
  in tests happens through the append-only API itself (`append_episodic`,
  `register_lesson`), which is the only seeding discipline every adapter
  supports by construction.
- Tier B (`test_acc23_*`, `test_acc24_*`) is scoped to the in-memory
  reference adapter because it exercises the contract lifecycle
  (retirement) and constructor seeding — operations outside the Protocol
  surface. It is not parameterized and imposes nothing on future adapters.
- The scaffold contains NO purge/expiry functionality of any kind: the
  tokens `purge`/`expire`/etc. appear ONLY inside negative structural
  assertions that PROVE their absence (AC-1/AC-2).

## 7. Explicit candidate status statement

SQLite (WAL) + content-addressed filesystem blobs (packet §1 Option 1)
remains an engineering **CANDIDATE** — the PREFERRED-CANDIDATE designation
of `AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` §1/§3 — and is **NOT a
decision**. The packet states this at line 3 ("the PREFERRED-CANDIDATE
ranking ... is an engineering ranking, not a decision") and again at
lines 352–354 (R3 explicitly reserves the final architecture decision).
Nothing in this plan, in the scaffold, or in any prepared kit selects,
assumes, or pre-records any D1–D7 option; §3 maps options to branches and
nothing more.

## 8. Scratch evidence locations (this task)

Raw outputs are preserved append-only under
`/home/z/my-project/consolnext_scratch/T4/`:
`10_scaffold_test_run.txt`, `11_full_battery_test_run.txt`,
`12_pyflakes.txt`, `13_git_status.txt`, `14_no_purge_self_audit.txt`,
`15_test_ids.txt`.
