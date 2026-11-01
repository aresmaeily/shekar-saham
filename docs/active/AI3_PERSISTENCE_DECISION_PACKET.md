# AI-3 PERSISTENCE OWNER DECISION PACKET — D1–D7 (consolidated)

**ALL SEVEN DECISIONS PENDING — no owner decision recorded as of 2026-11-02;
none assumed; the PREFERRED-CANDIDATE ranking in
`AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` is an engineering ranking, not a
decision.**

Status: OWNER DECISION PACKET. This document is ADDITIVE. It does not edit,
restate-over, or supersede `AI3_PERSISTENCE_DECISION_BRIEF.md` (neutral
brief, 2026-10-18, with its 2026-11-02 currency note) or
`AI3_PERSISTENCE_CANDIDATE_EVALUATION.md` (preferred-candidate designation
under owner directive 2026-10-19 Decision R3). It consolidates the D1–D7
decision list from the brief §D, sets each decision's options beside the
brief's §B engineering analysis and the candidate evaluation's §2/§4/§5/§6
verdicts, and adds the pre-decision engineering kit that has now been
prepared so that the owner's reply can be executed directly.

Labels: every claim below carries its source — brief §A constraint (A1–A12),
brief §B option analysis (B-labelled engineering analysis), brief §C
unknowns (C1–C5), brief §D decision definitions, candidate evaluation §N.
Where no source in those documents states anything for a cell, the cell
says **UNKNOWN-WITH-REASON**. No numbers are invented anywhere in this
packet.

---

## 0. Reading order and framing facts (source-backed)

1. The corpus specifies NO storage engine, format, or service for AI-3 —
   persistence is an owner-environment decision by deliberate isolation
   (brief §A closing paragraph; `AI3_M_SCOPE_DERIVATION.md §3`).
2. Immutability is structural for episodic evidence: no
   update/delete/retention-purge path may exist (A3), and nothing expires
   out of the archive (A11). ANY option that would place episodic artifacts
   under a retention/purge policy is non-viable regardless of engine (brief
   §B "Explicitly non-viable today").
3. All viable options must wrap — not replace — the delivered in-memory
   contracts (`EpisodicRunArchive`, `SemanticLessonStore`); persistence is
   an adapter behind the same append-only API (brief §B preamble; reuse rule
   02:107-112).
4. Deployment facts, recorded honestly (A12): Windows-target deployment is
   owner-gated (P3.43 blocked); dev sandbox = Linux + Python venv; incumbent
   storage = embedded SQLite (`data/shekar.db`, WAL, `synchronous=NORMAL`,
   `user_version` migrations, WAL-consistent backups) + JSON/JSONL files
   (`app/data/store.py`, `app/core/config.py:126-128`).
5. Currency (brief header currency note, 2026-11-02): G2 is formally PASSED
   (owner-recorded 2026-10-29T19:58:32Z, CONSOL-GOV-37); the binding AI-2
   restrictions are unchanged (`AI2_ENABLED=0`, `verified=False`,
   `execution_mode=SYNTHETIC_OR_PAPER`; live credentials/enablement CLOSED
   AS NOT GRANTED, GOV-41 Phase 2). D1–D7 remain PENDING and none is assumed
   by that reconciliation.
6. The seven evaluation dimensions used in this packet — (a) operating
   cost, (b) Windows/Electron compatibility, (c) immutability strength,
   (d) point-in-time query behavior, (e) backup/restore impact,
   (f) concurrency limits, (g) migration+test cost — are the owner-facing
   reorganization of the brief's §B comparison rows and the evaluation's §2
   requirement table. They add NO new engineering claims.

---

## 1. D1 — Engine class: embedded single-operator store vs server-class

**Decision question (brief §D1, verbatim):** "single-operator embedded store
(Option 1 or 2) vs server-class deployment (Option 3) — driven by the
deployment target decision below."

**Options on the table** (brief §B; evaluation §1):

- **Option 1 — Embedded SQLite (incumbent engine) + filesystem blob store.**
  Artifacts content-addressed on disk (sha256 filename, matching the
  `ArtifactRef`/`input_snapshot_sha256` contract); append-only index tables
  in the existing `shekar.db`; schema via the established `user_version`
  migration mechanism. This is the stack designated PREFERRED CANDIDATE
  (evaluation §1/§3 — a candidate ranking, NOT a decision).
- **Option 2 — Pure filesystem: append-only JSONL + content-addressed
  blobs.** Episodic records appended to per-run JSONL segments; lessons in
  an append-only log (matches the event-log option noted as a future
  additive option in the AI3-M audit, AI3M-02); blobs on disk.
- **Option 3 — Server DB (PostgreSQL) (+ object store for blobs).**
- **(Non-viable regardless of engine, brief §B):** network/replicated
  stores, cloud object storage, any shared production database (presuppose
  deployment facts no source establishes — brief §C), and anything placing
  episodic artifacts under retention/purge (violates A3/A11 outright).

| Dimension | Opt 1 SQLite+blobs | Opt 2 JSONL+blobs | Opt 3 Postgres |
|---|---|---|---|
| (a) Operating cost | **Lowest delta** — engine already shipped, backed up, no new service (brief §B Opt 1; eval §3.1) | Minimal ops; zero new dependencies; trivially inspectable (brief §B Opt 2) | **Highest delta** — new service to install/operate; adds surface P3.43 does not budget (brief §B Opt 3; eval §3.1) |
| (b) Windows/Electron compatibility | Low burden; single-file portability to Windows (brief §B Opt 1; brief §B comparison "Windows/Electron deploy burden: low") | Low burden; trivially portable (brief §B Opt 2; comparison "low") | High burden; largest Windows-installation burden given P3.43 blockers (brief §B Opt 3; comparison "high") |
| (c) Immutability strength | App-level (INSERT-only paths; triggers possible) — "the only inherent tension" (brief §B Opt 1; eval §2 Immutability SUPPORTED-WITH-LIMITATION; L1) | **Format-level (strongest natural)** — rewriting requires deliberate file replacement, visible/diffable (brief §B Opt 2) | Storage-level (REVOKE UPDATE/DELETE + grants) — strongest of the three (brief §B Opt 3) |
| (d) PIT query behavior | Indexed, native — 1:1 map to `available_at`/`lessons_active_at` (brief §B Opt 1; eval §2 PIT SUPPORTED) | Scan-based; fine at research scale, needs segmentation at large scale (brief §B Opt 2) | Indexed, native (brief §B comparison) |
| (e) Backup/restore impact | Existing WAL-consistent routine; crash recovery engine-native (brief §B Opt 1; eval §2 Recovery SUPPORTED-WITH-LIMITATION, L4: restore drill never executed) | As good as filesystem + host backups; needs fsync/rotation writer discipline (brief §B Opt 2) | Engine-class (PITR, replication) — beyond current requirement evidence (brief §B Opt 3) |
| (f) Concurrency limits | Single-writer class (WAL lock); adequate for the single-operator research runtime (brief §B comparison; eval L5) | Single-writer; explicit single-writer discipline needed (brief §B Opt 2) | Full multi-writer — relevant only for a runtime that does not exist yet (brief §B Opt 3) |
| (g) Migration+test cost | Minimal; testable in-place with tmp-path fixtures (brief §B Opt 1; comparison "Test complexity: low") | Simplest; but query performance and integrity tooling hand-rolled (brief §B Opt 2; comparison "Test complexity: low") | Heaviest; test containers or live server in CI (brief §B Opt 3; comparison "high") |

Scale note (brief §C1): actual artifact volume/retention horizon is
unmeasurable today — no runtime exists (G2-gated class; live feeding remains
restricted per framing fact 5). UNKNOWN-WITH-REASON: any scale-driven
argument between the options has no measured basis yet.

**What the owner must state (one sentence):** `D1: embedded single-operator
store — Option 1 (SQLite WAL + JSONL + content-addressed blobs) | Option 2
(JSONL + content-addressed blobs) | server-class Option 3 (Postgres +
object store).`

**Consequence of deferral:** the persistence adapter stays BLOCKED; the
contract layer, tests, and G2 readiness of AI-3's delivered scope are
unaffected (brief §D closing; dependency-isolated by design,
`AI3_M_SCOPE_DERIVATION.md §3`). Per evaluation §7, D1-class finalization
also waits on D2 ("determines engine class ... and whether the embedded
candidate is final").

---

## 2. D2 — Deployment target of the AI runtime

**Decision question (brief §D2, verbatim):** "deployment target for the AI
runtime (Windows host? Docker? Electron-bundled?) — currently BLOCKED
upstream at P3.43 launch gates."

**Options on the table** (brief §D2; evaluation §7 D2 row): Windows host /
Docker / Electron-bundled. These are the targets named in the sources; the
brief and evaluation do NOT compare them against storage dimensions
target-by-target, so most cells below are honestly UNKNOWN — the binding
fact the docs DO record is that the target decision is upstream-blocked
(P3.43) and that it "determines engine class, access-control model, and
whether the embedded candidate is final" (evaluation §7 D2).

| Dimension | Windows host | Docker | Electron-bundled |
|---|---|---|---|
| (a) Operating cost | UNKNOWN-WITH-REASON: no source compares host-ops cost for the AI runtime; P3.43 gates are the recorded blocker (brief §D2, A12) | UNKNOWN-WITH-REASON: no source establishes container deployment for this runtime (brief §B: shared/container facts presuppose undetermined deployment) | UNKNOWN-WITH-REASON: no source compares bundled-ops cost |
| (b) Windows/Electron compatibility | Recorded as the owner-gated target class (brief A12: "Windows-target deployment owner-gated (P3.43 blocked)"); Option 1/2 engines carry "low" Windows deploy burden (brief §B comparison) | UNKNOWN-WITH-REASON: no source states Docker-on-Windows compatibility for this stack | Electron runtime is named among the P3.43 launch gates (evaluation §3.1); per-engine burden on this target: UNKNOWN-WITH-REASON |
| (c) Immutability strength | Independent of target at the guarantee-class level — decided by D3, not D2 (brief §D3) | Same — decided by D3 | Same — decided by D3 |
| (d) PIT query behavior | Follows the D1 engine, not the target (brief §B comparison rows) | Follows D1 | Follows D1 |
| (e) Backup/restore impact | UNKNOWN-WITH-REASON: no source states host-backup policy for the AI runtime (brief §C4: backup cadence/retention "policy is owner's") | UNKNOWN-WITH-REASON: no source states volume/backup policy for containers here | UNKNOWN-WITH-REASON: no source states bundle-data backup policy |
| (f) Concurrency limits | Single-operator class assumed by incumbent analysis; multi-user requirement UNRESOLVED (brief §C2; eval §2 access control, L3) | UNKNOWN-WITH-REASON: no source establishes multi-writer need | UNKNOWN-WITH-REASON: no source establishes multi-writer need |
| (g) Migration+test cost | P3.43 gates already the binding constraints; adding server-class deps "would enlarge the exact surface that is currently blocked" (evaluation §3.1) | UNKNOWN-WITH-REASON: no source compares container test cost for this runtime | UNKNOWN-WITH-REASON: no source compares bundle test cost |

**What the owner must state (one sentence):** `D2: AI runtime deployment
target = Windows host | Docker | Electron-bundled (decided by <owner>,
<date>, recorded in <register location>).`

**Consequence of deferral:** persistence adapter stays BLOCKED (brief §D
closing); D2 is additionally blocked upstream at P3.43 launch gates today
(brief §D2), so no AI-3 scope beyond the already-delivered contract layer
is held up by D2 alone (evaluation §7: D2 is "Owner decision genuinely
required before final architecture").

---

## 3. D3 — Immutability guarantee class

**Decision question (brief §D3, verbatim):** "immutability guarantee class
required (application-enforced vs storage-enforced vs format-enforced) and
whether hash-verification audits should be periodic."

**Options on the table** (brief §B options + evaluation §2 Immutability row,
§4 L1, §5 M3):

- **Application-enforced** (Option 1 baseline): INSERT-only code paths
  behind the in-memory contracts' append-only API; SQLite cannot
  structurally forbid UPDATE without triggers (brief §B Opt 1; eval L1).
- **Trigger-enforced inside SQLite** (evaluation §5 M3): deny-triggers
  (`CREATE TRIGGER ... BEFORE UPDATE/DELETE → RAISE`) on episodic tables —
  closes L1 at storage level inside SQLite; plus hash columns verified by a
  periodic audit query (evaluation §2 Immutability mitigation stack).
- **Format-enforced** (Option 2): append-only is the file format itself —
  "strongest natural fit"; rewriting requires deliberate, visible,
  diffable file replacement (brief §B Opt 2).
- **Storage-enforced server-class** (Option 3): REVOKE UPDATE/DELETE +
  append-only grants — strongest, but requires the Option 3 deployment the
  owner has not made (brief §B Opt 3; evaluation §2 Immutability row).

| Dimension | App-enforced | Trigger-enforced (SQLite) | Format-enforced (JSONL) | Storage-enforced (Postgres) |
|---|---|---|---|---|
| (a) Operating cost | Lowest (no extra mechanism; brief §B Opt 1) | Low — additive trigger migration step (evaluation §5 M3) | Low (brief §B Opt 2) | High — implies Option 3 service (brief §B Opt 3) |
| (b) Windows/Electron compatibility | Low burden | UNKNOWN-WITH-REASON: no source states SQLite trigger behavior differences on the Windows target; engine already shipped on this stack (A12) | Low (brief §B Opt 2 portability) | High (brief §B comparison) |
| (c) Immutability strength | Weakest of the four — app-level only (brief §B Opt 1; eval L1) | Storage-level inside SQLite; closes L1 (evaluation §5 M3) | Format-level, "strongest natural" for append-only (brief §B Opt 2) | Strongest — grants at the engine (brief §B Opt 3) |
| (d) PIT query behavior | Per carrier engine (D1) | Indexed, native (brief §B Opt 1) | Scan/segments (brief §B Opt 2) | Indexed, native (brief §B Opt 3) |
| (e) Backup/restore impact | Per carrier engine (D1); triggers are schema → carried by `user_version` migrations (A12, evaluation §5 M2/M3) | Same, plus trigger definitions live in schema dumps | Host-level backups; format is trivially restorable (brief §B Opt 2) | Engine-class PITR (brief §B Opt 3) |
| (f) Concurrency limits | Per carrier engine (D1) | Single-writer class (brief §B comparison) | Single-writer discipline required (brief §B Opt 2) | Full multi-writer (brief §B comparison) |
| (g) Migration+test cost | None beyond adapter | One additive migration step + trigger tests (evaluation §5 M3; §6 test 1) | Simplest mechanism, hand-rolled integrity tooling (brief §B Opt 2) | Heaviest (brief §B Opt 3) |

Sub-question the owner must also answer (brief §D3): whether
hash-verification audits should be PERIODIC. Source basis: evaluation §2
Immutability mitigation ("hash columns verified by a periodic audit query");
the periodicity itself is unstated in the sources — UNKNOWN-WITH-REASON (no
cadence exists in any document; inventing one would violate the no-invented-
numbers rule). Note: `verify_integrity` (prepared kit, §9 below) is the
deterministic primitive such audits would call.

**What the owner must state (one sentence):** `D3: immutability guarantee
class = application-enforced | trigger-enforced (M3) | format-enforced
(JSONL) | storage-enforced (Postgres grants); hash-verification audits
periodic: yes/no (cadence to be stated if yes).`

**Consequence of deferral:** adapter stays BLOCKED (brief §D closing);
evaluation §7: D3 "determines whether M3 deny-triggers are sufficient" —
without it the adapter's acceptance claim cannot name its own guarantee
class (evaluation §6 test 1 depends on the chosen class).

---

## 4. D4 — Access-control model and who may read episodic evidence

**Decision question (brief §D4, verbatim):** "access-control model + who may
read episodic evidence (A8 approval state interacts with this)."

**Options on the table** (brief §B access-control rows; evaluation §2
Access control row, L3; brief §C2):

- **File-permission class, single-operator** (incumbent assumption): file
  perms + sha256-column verification; "adequate for the single-operator
  deployment the repo actually targets (A12, Windows/Electron single host);
  weak for any multi-user/remote deployment" (evaluation §2).
- **Server-class roles/RLS** (Option 3): "strongest (roles, row-level
  security, audit extensions) — relevant only if multi-user/remote
  deployment is actually decided" (brief §B Opt 3).
- Multi-user vs single-operator deployment is an open unknown (brief §C2);
  "whether multi-user is ever required is UNRESOLVED (D2/D4) — this is the
  candidate's main conditional dependency" (evaluation §2).

| Dimension | File-permission single-operator | Server-class roles/RLS |
|---|---|---|
| (a) Operating cost | Lowest (no service; brief §B Opt 1) | High — service + role administration (brief §B Opt 3) |
| (b) Windows/Electron compatibility | Consistent with A12 single-host target | UNKNOWN-WITH-REASON: no source states Windows/Electron burden of a role model here |
| (c) Immutability strength | Anti-hidden-mutation via file perms + hashes (brief §B comparison) | Strongest anti-hidden-mutation (brief §B comparison) |
| (d) PIT query behavior | Per carrier engine (D1) | Per carrier engine (D1) |
| (e) Backup/restore impact | Per carrier engine (D1) | Per carrier engine (D1); permission state adds restore surface (UNKNOWN-WITH-REASON: no source details it) |
| (f) Concurrency limits | Single-writer class (brief §B comparison; eval L5) | Full multi-writer — "relevant only for a runtime that does not exist yet (G2-gated)" (brief §B Opt 3) |
| (g) Migration+test cost | Minimal (brief §B Opt 1) | Heaviest (brief §B Opt 3) |

A8 interaction (brief §D4; A8: governed actions carry approval state): the
sources record that approval state is carried by the records themselves
(`02:198`; provenance fields, A6); no source specifies reader-level
permissions for evidence — UNKNOWN-WITH-REASON: the reader-authorization
matrix does not exist in any document and must come from the owner.

**What the owner must state (one sentence):** `D4: access-control model =
file-permission single-operator | server-class roles/RLS; readers of
episodic evidence = <explicit list/role set>.`

**Consequence of deferral:** adapter stays BLOCKED (brief §D closing);
evaluation §7: D4 — "Multi-user requirements would reopen Option 3";
brief §C2 keeps the multi-user question open until stated.

---

## 5. D5 — Backup / retention / DR policy

**Decision question (brief §D5, verbatim):** "backup/retention/DR policy
(cadence, copies, offsite?) — noting the archive itself must never be purged
(A3/A11); backups are replication, not retention."

**Options on the table** (bounded by what the sources record):

- **Ratify the incumbent routine as the baseline**: WAL-consistent backups
  to `data/backups` exist as shipped code (A12; evaluation §1/§2 Recovery);
  restore drill becomes a required acceptance test (evaluation §5 M6, §6
  test 6; L4: "Recovery is designed-in but UNDEMONSTRATED — no restore
  drill, no backup artifact yet").
- **Stricter owner policy** (cadence/copies/offsite): the VALUES are pure
  owner policy — brief §C4 records that backup cadence/retention policy
  "exists as code for SQLite; policy is owner's". No cadence, copy-count,
  or offsite requirement exists in any source; any number would be invented.
- **Deferral** is recorded as an operational gate, not waivable by general
  instruction (evaluation §7 D5 class).

Binding constraint on every variant: the episodic archive itself is never
purged — backups are replication, not retention (brief §D5; A3/A11;
framing fact 2).

| Dimension | Incumbent routine + restore drill | Stricter owner policy (values TBD by owner) |
|---|---|---|
| (a) Operating cost | Existing routine, zero new mechanism (A12) | UNKNOWN-WITH-REASON: cost follows the owner's unstated cadence/copies/offsite values (brief §C4) |
| (b) Windows/Electron compatibility | Follows the D1/D2 carrier (A12: backups exist on the incumbent stack) | UNKNOWN-WITH-REASON: offsite/DR tooling on the Windows target is unstated in sources |
| (c) Immutability strength | Neutral — replication does not weaken append-only (brief §D5 note) | Neutral, same principle |
| (d) PIT query behavior | Neutral (backup mechanism, not query path) | Neutral |
| (e) Backup/restore impact | Designed-in, UNDEMONSTRATED until drill executed (eval L4; §6 test 6 closes it) | Stronger by owner's definition; drill still required as acceptance evidence (eval §5 M6) |
| (f) Concurrency limits | WAL-consistent backup of a single-writer store (A12; eval L5) | Same carrier limits apply |
| (g) Migration+test cost | Restore drill = one required acceptance test (eval §6 test 6) | UNKNOWN-WITH-REASON: test cost scales with the owner's DR requirements (unstated) |

**What the owner must state (one sentence):** `D5: backup/DR policy —
cadence <stated>, copies <stated>, offsite <yes/no + location>, restore
drill acceptance required: yes; archive purge/retention-expiry: NONE
(A3/A11).`

**Consequence of deferral:** adapter stays BLOCKED for OPERATIONS (brief §D
closing; evaluation §7: adapter "remains BLOCKED on D2/D3/D4 (+D5 for
operations)"); no AI-3 contract-layer scope is affected.

---

## 6. D6 — Blob-store location and size ceilings

**Decision question (brief §D6, verbatim):** "blob-store location
(inside/outside repo tree) and any size ceilings the owner wants to ratify
(the P0 numeric-ceiling ratification in the acceptance package is the same
class of decision)."

**Options on the table** (brief §C5/§D6; evaluation §7 D6 row):

- **Inside the repo tree** — corpus position: SILENT. Brief §C5: "whether
  episodic artifacts must live outside the repo tree (blob store location)
  or be admissible inside it — corpus is silent."
- **Outside the repo tree** — same silence; the choice is the owner's
  environment decision (brief §D6).
- **Size ceilings** — no numeric ceiling exists in any source; ratifying
  one is the owner's numeric-ceiling-class decision (brief §D6, cross-ref
  P0 numeric-ceiling ratification class). Evaluation §7 classifies D6 as
  "Non-blocking for candidate designation".

| Dimension | Inside repo tree | Outside repo tree |
|---|---|---|
| (a) Operating cost | UNKNOWN-WITH-REASON: no source weighs repo-tree growth/maintenance (brief §C5 silence) | UNKNOWN-WITH-REASON: no source weighs separate-location ops (brief §C5 silence) |
| (b) Windows/Electron compatibility | UNKNOWN-WITH-REASON: no source | UNKNOWN-WITH-REASON: no source |
| (c) Immutability strength | UNKNOWN-WITH-REASON: no source compares tamper-visibility by location; content-addressing (sha256 naming) applies in both (brief §B Opt 1; eval §5 M4) | Same mechanism; same UNKNOWN for location-specific differences |
| (d) PIT query behavior | Neutral — indexing is a D1 concern | Neutral |
| (e) Backup/restore impact | UNKNOWN-WITH-REASON: no source states whether repo backups would cover blobs | UNKNOWN-WITH-REASON: no source states the backup pairing |
| (f) Concurrency limits | Per carrier engine (D1) | Per carrier engine (D1) |
| (g) Migration+test cost | UNKNOWN-WITH-REASON: no source | UNKNOWN-WITH-REASON: no source |

**What the owner must state (one sentence):** `D6: blob store lives
inside | outside the repo tree (path to be stated); size ceilings ratified:
<values or "none at this time">.`

**Consequence of deferral:** adapter stays BLOCKED (brief §D closing) but
D6 is explicitly non-blocking for the candidate designation (evaluation §7
D6 class) — deferral delays adapter implementation, not the standing
candidate evidence.

---

## 7. D7 — Timing: decide now (pre-G2 class) vs after G2

**Decision question (brief §D7, verbatim):** "timing — decide now (pre-G2,
to make the adapter testable in synthetic runs) vs after G2 (risk: none
identified for deferral, since the contract layer is complete and the
adapter is additive either way)."

Currency note (brief header, 2026-11-02): G2 has since been formally PASSED
(owner-recorded 2026-10-29T19:58:32Z, CONSOL-GOV-37); the decision question
stands as written, with the recorded evaluation fact unchanged:
"Contract layer complete; deferral carries no identified risk" (evaluation
§7 D7).

**Options on the table** (brief §D7; evaluation §7 D7 row):

- **Decide now** — makes the adapter testable in synthetic runs (brief
  §D7; evaluation §5 M7: synthetic-only fixtures, no live data).
- **After G2 / later** — evaluation §7: "Engineering decision safely
  deferrable"; brief §D7: "risk: none identified for deferral".
- **Not an option:** treating the PREFERRED-CANDIDATE designation as the
  decision — R3 explicitly reserves the final architecture decision
  (evaluation header and §3 closing paragraph).

| Dimension | Decide now | After G2 / later |
|---|---|---|
| (a) Operating cost | No new ops today either way — adapter is additive; engine only materializes after D1 (evaluation §5 M1) | Same |
| (b) Windows/Electron compatibility | UNKNOWN-WITH-REASON for either timing: no source times compatibility risk; P3.43 gates bind regardless (A12) | Same UNKNOWN |
| (c) Immutability strength | Determined by D3 whenever taken — timing-neutral (brief §D7) | Same |
| (d) PIT query behavior | Determined by D1 carrier — timing-neutral | Same |
| (e) Backup/restore impact | Restore drill (eval §6 test 6) executable at adapter time whenever chosen | Same |
| (f) Concurrency limits | Timing-neutral; single-writer class incumbent (eval L5) | Same |
| (g) Migration+test cost | "the adapter is additive either way"; deferral risk: "none identified" (brief §D7) | Same; synthetic-run testability benefit is forfeited until decided (brief §D7) |

**What the owner must state (one sentence):** `D7: persistence adapter
timing = decide D1–D6 now | defer until <stated milestone>.`

**Consequence of deferral:** explicitly recorded as carrying NO identified
risk (brief §D7; evaluation §7: "safely deferrable") — the contract layer,
tests, and G2 readiness of AI-3's delivered scope are unaffected; per R3,
none of D1–D7 blocks AI-6 or any other independent work (evaluation §7
closing).

---

## 8. Cross-cutting non-viable class (applies to every decision)

Brief §B "Explicitly non-viable today": network/replicated stores, cloud
object storage, and any shared production database — presuppose deployment
facts (hosting, network, multi-tenancy) that no source establishes. Also
anything placing episodic artifacts under a retention/purge policy violates
A3/A11 outright, regardless of engine. If the owner names an option from
this class, a new evidence pass (not this packet) is required first.

---

## 9. What is already prepared (this deliverable — pre-decision kit only)

Authorized pre-decision work; NO storage engine is implemented and NO owner
decision is assumed anywhere in the kit:

1. **Store interface** — `backend/app/domain/research_memory_store.py`:
   `ResearchMemoryStore` (engine-neutral `typing.Protocol`, append-only,
   structurally carrying NO update/delete/purge path; implementers MUST NOT
   add purge/retention-expiry for episodic evidence — A3/A11; fail-closed
   on missing/corrupt records with the contracts' honest miss semantics:
   unknown ids are explicit `None`/empty misses, NOT `KeyError`, because
   that is what the contracts do — documented, not invented); append-only
   docstring pinning; `InMemoryResearchMemoryStore` reference adapter that
   COMPOSES `EpisodicRunArchive` + `SemanticLessonStore` by delegation
   (idempotent appends, conflict refusals exactly as the contracts behave).
2. **Canonical serialization** — same module: `canonical_research_memory_json`
   (sorted keys, explicit separators, UTF-8, `allow_nan=False`,
   DECIMAL_AS_STRING policy) + `sha256_hex`; byte-identical across repeated
   calls, across independent constructions, and across insertion order
   (test-pinned).
3. **Integrity records** — `ResearchMemoryIntegrityReport` (frozen:
   per-entry id + sha256 over canonical serialization, entry count, lesson
   version counts, `verify_ok`, refusal lists) + `verify_integrity(store,
   expected_digests)` — pure, fail-closed; returns refusal records listing
   mismatched/missing ids; NEVER raises raw exceptions; appends after a
   snapshot are legal (append is the only legal change) and are not
   refusals.
4. **Deterministic fixture kit** — `backend/tests/fixtures/research_memory/`
   (canonical builders) with stable import surface
   `backend/tests/helpers_research_memory_fixtures.py`: explicit-timestamp
   factories and fixed hex sentinels; no clock, no RNG, no environment
   reads.
5. **Acceptance tests at store level** —
   `backend/tests/test_research_memory_store.py` (21 tests): protocol
   conformance + exact-surface proof; append-only structural proof;
   idempotent append + conflict refusal with state unchanged; PIT views
   (`episodic_available_at`, `lessons_active_at`) through the store;
   canonical-JSON determinism; integrity report shape/frozenness;
   `verify_integrity` OK path + tamper refusal + missing-entry refusal +
   never-raises-on-corrupt-adapter; explicit-miss fail-closed behavior.

The kit deliberately stops at the interface boundary: choosing and building
the concrete adapter (SQLite WAL + JSONL + blobs / JSONL-only / Postgres) is
exactly what D1–D7 gate.

## 10. Acceptance tests ANY adapter must pass (evaluation §6, binding list)

1. Immutability negatives: UPDATE/DELETE on episodic tables refused by
   trigger; adapter exposes no update/delete path (structural).
2. Append-only round-trip: artifact → archive → retrieve byte-identical
   (hash match) across process restart.
3. PIT correctness: records recorded after a cutoff are invisible to
   `available_at`-style queries at that cutoff (look-ahead guard).
4. Supersession chain: supersede/retire create new versions; history views
   never rewritten; retirement terminal.
5. Provenance completeness: missing required provenance blocks acceptance
   (03:40) at the storage boundary, mirroring the in-memory gates.
6. Backup/restore drill: WAL-consistent backup → destructive restore →
   full re-verification by hash (closes L4).
7. Crash-recovery: kill during write → reopen → WAL recovery → no partial
   record accepted (durability evidence).
8. Access-control reality check: file-permission enforcement documented
   for the declared deployment mode (conditional on D2/D4).

## 11. Execution gate

Implementation of the persistence adapter starts ONLY after the required
decisions are recorded by the owner in the decision register. Until then:
the contract layer, the in-memory reference store, the fixture/acceptance
kit above, and the PREFERRED-CANDIDATE evidence stand as prepared
material — none of it constitutes, upgrades to, or presumes a decision.
