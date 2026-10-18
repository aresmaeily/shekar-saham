# AI-3 PERSISTENCE DECISION BRIEF — 2026-10-18 (neutral; owner decides)

Status: ENGINEERING DECISION SUPPORT. This brief does NOT select a persistence
technology. It separates (A) source-backed constraints, (B) engineering
analysis of viable options against those constraints, (C) unknowns, and
(D) owner decisions that are missing. Labels are explicit per claim.

## A. Source-backed constraints (verbatim loci in the imported corpus)

| # | Constraint | Source |
|---|---|---|
| A1 | AI-3 = "Episodic immutable run artifacts plus curated/versioned semantic memory" | `02:83-85` |
| A2 | "Episodic research artifacts remain immutable; semantic lessons remain curated/versioned" | `02:159`; D-AI-28; `03 §Memory` |
| A3 | Immutability is structural: no update/delete/retention-purge path may exist for episodic evidence | `03 §Memory`; implementation `research_memory.py:119-158` (append/get/index only) |
| A4 | Semantic memory: version history never rewritten; supersession and retirement are NEW terminal versions | D-AI-28; `research_memory.py:247-318` |
| A5 | "Every conclusion must identify its information cutoff" → point-in-time retrieval over both stores | `02:142`; `available_at()` / `lessons_active_at()` |
| A6 | Results link to code/config/data versions + immutable run artifacts; provenance fields mandatory, unknown ⇒ explicit None, never invented | `06 §7`; D-AI-22; `research_memory.py:57-116` |
| A7 | "No memory operation may silently modify production logic" (memory ops are epistemic only) | `03 §Memory`; closed operation vocabulary `:44-49` |
| A8 | Governed actions carry traceable run identity, versions, human approval state, explicit limitations | `02:198` |
| A9 | Deployment gates: G2 blocks real-data research runtime; live feeding of episodic artifacts is G2-gated; no live providers today | `02:10-11,201`; `AI3_M_SCOPE_DERIVATION.md §3` |
| A10 | Failure/recovery honesty: provider failure, low trust, budget exhaustion must fail closed or degrade explicitly | `06 §10`; `02-product §Failure model` |
| A11 | Coverage/retention honesty: episodic archive has no expiry — "nothing expires out of the archive" | `research_memory.py:120-125` docstring, pinned by tests |
| A12 | Environment facts (NOT_VERIFIED class, recorded honestly): Windows-target deployment owner-gated (P3.43 blocked); dev sandbox = Linux + Python 3.12 venv; incumbent storage = embedded SQLite (`data/shekar.db`, WAL, `synchronous=NORMAL`, user_version migrations, WAL-consistent backups to `data/backups`) + JSON/JSONL files (`market_cache.json`, `history_snapshots.jsonl`) — `app/data/store.py`, `app/core/config.py:126-128` | repo inspection 2026-10-18 |

The corpus specifies NO storage engine, format, or service for AI-3 — this
silence is itself source-backed (`AI3_M_SCOPE_DERIVATION.md §3`): persistence
is an owner-environment decision, deliberately isolated so the remaining owner
action stays small.

## B. Engineering analysis — viable options vs the constraints

All options must wrap — not replace — the delivered in-memory contracts
(`EpisodicRunArchive`, `SemanticLessonStore`): persistence is an adapter behind
the same append-only API. This is (B)-labelled analysis, not a corpus
requirement, but it follows from A1–A5 and the reuse rule (`02:107-112`).

### Option 1 — Embedded SQLite (incumbent engine) + filesystem blob store

Artifacts stored content-addressed on disk (`sha256` filename, exactly the
`ArtifactRef`/`input_snapshot_sha256` contract); index tables in the existing
`shekar.db` (append-only tables; INSERT-only grants; no UPDATE/DELETE paths;
schema via the established `user_version` migration mechanism).

- Deployment/ops (A12): **lowest delta** — engine already shipped, backed up
  (WAL-consistent backups exist), single-file portability to Windows; no new
  service.
- Durability/backup/recovery (A10): WAL + existing backup routine; crash
  recovery is engine-native. (B)
- PIT retrieval (A5): index queries by `recorded_at_utc` / `created_at_utc`
  map 1:1 to `available_at` / `lessons_active_at`. (B)
- Immutability (A2/A3/A11): enforcement is by convention (INSERT-only code
  paths, triggers optional) — SQLite cannot *structurally* forbid UPDATE on a
  table without triggers; achievable, but the guarantee is application-level,
  not storage-level. (B; the only inherent tension)
- Semantic versioning (A4): natural fit (versioned rows, supersede = insert
  new row + status flip of old row expressed as a NEW row view; retire = new
  terminal row). (B)
- Access control / auditability (A8): file-permission level; concurrent
  multi-process writers serialize on the WAL lock; hidden-mutation protection
  depends on file integrity (sha256-column verification possible) — adequate
  for single-operator deployment, weak for multi-user. (B)
- Migration/complexity/testability (A12): minimal; testable in-place with
  tmp-path fixtures. (B)

### Option 2 — Pure filesystem: append-only JSONL + content-addressed blobs

Episodic records appended to per-run JSONL segments; lessons in an
append-only log; blobs on disk; indexes rebuilt or kept as sidecar files.

- Deployment/ops: zero new dependencies; trivially portable; trivially
  inspectable (grep-able audit trail). (B)
- Durability: as good as the filesystem + host backups; partial-line crash
  handling needs a writer discipline (fsync policy, rotation). (B)
- PIT retrieval: scan-based (fine at research scale; needs segmentation at
  large scale). (B)
- Immutability: **strongest natural fit** — append-only is the file format
  itself; rewriting requires deliberate file replacement (visible, diffable,
  git-detectable). (B)
- Semantic versioning: same append-only log; supersede/retire are appended
  events — matches the event-log option already noted as a future additive
  option in the AI3-M audit (AI3M-02). (B)
- Access control: weakest (file perms only); concurrent writers need an
  explicit single-writer discipline. (B)
- Migration/complexity: simplest; but query performance and integrity tooling
  are hand-rolled vs Option 1. (B)

### Option 3 — Server DB (PostgreSQL) (+ object store for blobs)

- Deployment/ops (A12): **highest delta** — new service to install/operate on
  the owner's Windows/Electron target or a server; contradicts nothing in the
  corpus but adds operational surface the deployment block (P3.43) does not
  currently budget.
- Durability/backup/recovery: strongest engine-class guarantees (PITR,
  replication) — beyond current requirement evidence. (B)
- Immutability: enforceable via REVOKE UPDATE/DELETE + append-only grants —
  storage-level guarantee, stronger than Option 1. (B)
- Access control/auditability: strongest (roles, row-level security, audit
  extensions) — relevant only if multi-user/remote deployment is actually
  decided. (B)
- Concurrency: real multi-writer support — relevant only for a runtime that
  does not exist yet (G2-gated). (B)
- Migration/complexity/testability: heaviest; test containers or a live
  server in CI; largest Windows-installation burden given P3.43 blockers. (B)

### Explicitly non-viable today

Network/replicated stores, cloud object storage, and any shared production
database: (C) unknown — they presuppose deployment facts (hosting, network,
multi-tenancy) that no source in the corpus or repository establishes. Also
anything that would place episodic artifacts under a retention/purge policy
violates A3/A11 outright, regardless of engine.

### Comparison summary (B-label applies to every cell)

| Dimension | Opt 1 SQLite+blobs | Opt 2 JSONL+blobs | Opt 3 Postgres |
|---|---|---|---|
| Ops delta vs incumbent | minimal | minimal | high |
| Immutability guarantee | app-level (triggers possible) | format-level (strongest natural) | storage-level (grants) |
| PIT retrieval | indexed, native | scan/segments | indexed, native |
| Versioning/supersession/retire | natural | natural (event-log) | natural |
| Access control / anti-hidden-mutation | file perms + hashes | weakest | strongest |
| Multi-writer concurrency | single-writer class | single-writer | full |
| Backup/recovery | existing routine | host-level | engine-class (PITR) |
| Windows/Electron deploy burden | low | low | high |
| Test complexity | low | low | high |
| Scale headroom | moderate | moderate→needs segmentation | high |

## C. Unknowns (honestly listed — no requirement invented)

1. Actual artifact volume/retention horizon of research runs (no runtime
   exists; G2-gated) — scale cannot be measured yet.
2. Multi-user vs single-operator deployment (affects Option 3's relevance and
   the access-control row).
3. Whether the owner requires storage-level (not app-level) immutability
   guarantees, and any encryption-at-rest requirement (not in corpus).
4. Backup cadence/retention policy for `data/backups` and blob store (exists
   as code for SQLite; policy is owner's).
5. Whether episodic artifacts must live outside the repo tree (blob store
   location) or be admissible inside it — corpus is silent.

## D. Missing owner decisions (the actual decision list)

- **D1 (decides the engine class):** single-operator embedded store
  (Option 1 or 2) vs server-class deployment (Option 3) — driven by the
  deployment target decision below.
- **D2:** deployment target for the AI runtime (Windows host? Docker?
  Electron-bundled?) — currently BLOCKED upstream at P3.43 launch gates.
- **D3:** immutability guarantee class required (application-enforced vs
  storage-enforced vs format-enforced) and whether hash-verification audits
  should be periodic.
- **D4:** access-control model + who may read episodic evidence (A8 approval
  state interacts with this).
- **D5:** backup/retention/DR policy (cadence, copies, offsite?) — noting the
  archive itself must never be purged (A3/A11); backups are replication, not
  retention.
- **D6:** blob-store location (inside/outside repo tree) and any size ceilings
  the owner wants to ratify (the P0 numeric-ceiling ratification in the
  acceptance package is the same class of decision).
- **D7:** timing — decide now (pre-G2, to make the adapter testable in
  synthetic runs) vs after G2 (risk: none identified for deferral, since the
  contract layer is complete and the adapter is additive either way).

Any of D1–D7 unanswered leaves the persistence adapter BLOCKED; the contract
layer, tests, and G2 readiness of AI-3's delivered scope are unaffected by the
deferral (dependency-isolated by design, `AI3_M_SCOPE_DERIVATION.md §3`).
