# AI-3 OPERATIONAL STATUS + D5/R-6 RECONCILIATION — 2026-11-03

Directive §3: "AI-3 operational truth and recovery evidence." Every row below
states VERIFIED FACTS at HEAD `c1f3c1210c350e2a5f859e96e763dc61b7ad620d` (tree
`9d7cf85ab6b6074489e72bdc3389ec915f8d73a3`) plus this cycle's additive CLI.
Nothing was auto-wired into the live runtime.

## 1. Implementation status — verified separately, per item

| Item | Status | Evidence |
|---|---|---|
| Adapter implementation | **IMPLEMENTED (production class)** | `app/data/research_memory_sqlite.py` — `SqliteWalResearchMemoryStore` (SQLite WAL + `synchronous=FULL`, content-addressed blobs, composition-by-delegation over the contracts; 550-line dedicated test file) |
| Factory registration | **REGISTERED (#3 of 3)** | `tests/test_ai3_acceptance_scaffold.py` `STORE_FACTORIES` entry `("sqlite_wal_encrypted_reference", …)`; scaffold 56→82 = exact ×3/2; one-entry contract |
| Encryption implementation | **IMPLEMENTED** | AES-256-GCM at rest; per-record 12-byte nonce; table+row-id as AEAD associated data; ciphertext-at-rest contains no plaintext (pinned by tests) |
| OS keyring behavior | **IMPLEMENTED, optional, fail-closed** | `keyring` import-guarded; keyring provider `create-if-missing exactly once`; if the module/backend is absent → fail-closed refusal, never plaintext |
| Env-var key override | **IMPLEMENTED, deterministic** | `RADAR_RESEARCH_MEMORY_KEY` (hex-64 or base64 → 32 bytes; else `research_memory_key_invalid` refusal); CLI tests exercise it end-to-end |
| Append-only / no-purge | **IMPLEMENTED, architectural** | `RETENTION_POLICY = {episodic: PERMANENT_NO_PURGE, semantic_lessons: PERMANENT_RETIRE_NOT_DELETE}`; no UPDATE/DELETE on store tables; digest+tamper=evidence discipline; write gate `file_integrity_unverified` |
| Backup implementation | **IMPLEMENTED + now owner-triggerable** | `backup(destination_dir, keep=14)` — SQLite backup-API snapshot, self-contained DELETE-journal file + `.sha256` sidecar; rotation of backup FILES only; **NEW this cycle: owner CLI trigger (see §2)** |
| Verification of backup | **IMPLEMENTED** | `verify_backup(path, key_provider)` classmethod — opens read-only, decrypts+digest-checks rows, returns integrity report with refusal reasons; CLI exits 2 on any refusal |
| Restore implementation | **DOCUMENTED PROCEDURE (not a coded method)** — honest | Module docstring: restore = copy the snapshot back as the DB file, then `verify_integrity`; **restore drill exists in tests repo-side (functional), NOT as a timed drill** |
| Runtime caller / activation gate | **ZERO RUNTIME CALLERS — NOT WIRED (by decision)** | grep: no importer of `research_memory_sqlite` under `app/` outside the module itself; D1 recorded "no runtime auto-wiring — engine activation stays a separate gate"; dormancy pinned by `test_research_memory_backup_cli.py::test_cli_is_dormant_no_runtime_caller` |

## 2. D5 ↔ R-6 cadence reconciliation (directive §3, resolved WITHOUT violating R-6)

**Finding:** D5 records "local destination, daily cadence, keep=14" while R-6
keeps every in-app scheduler dormant and manual-trigger-only, and no runtime
caller exists for the research-memory adapter. The only in-app "daily backup"
in the codebase is the SHIPPED PRODUCT store's startup-gated `Store.backup(keep=7)`
(`main.py` lifespan, at most once per day per boot) — a different store; it
does NOT cover AI-3 research memory.

**Resolution (two-field record, no severity inflation):**
- **Daily AUTOMATED backup of AI-3 research memory = NOT OPERATIONAL** in the
  current release posture. Nothing in the app runtime takes research-memory
  backups; nothing may, without violating R-6.
- **Activation path (exact owner actions, R-6-compatible):**
  1. **Manual trigger (works today, shipped this cycle):** the owner runs
     `python -m app.data.research_memory_sqlite backup --directory <store dir> --dest <backup dir> --keep 14`
     whenever desired (daily if the owner chooses). The trigger is DORMANT —
     zero runtime callers, cannot self-activate; fail-closed key handling
     (env override or OS keyring; invalid/missing key → exit 2, never
     plaintext). Implemented + proven by `tests/test_research_memory_backup_cli.py`
     (5 tests: end-to-end snapshot+sidecar, verify-backup exit 0, invalid-key
     refusal, missing-snapshot refusal with `backup_file_missing`, dormancy
     source guard).
  2. **Owner-issued scheduled cadence (owner machine act):** the owner creates
     a Windows Task Scheduler entry invoking the same command daily — exactly
     the "separate dated owner act on the owner machine" R-6 names. This is an
     OS-level task on the OWNER's machine, not an in-app scheduler runtime;
     R-6 stays intact.
- D5's own recorded reasoning already anticipated this ("local daily is the
  largest cadence achievable **without a scheduler runtime (R-6 posture)**") —
  this record makes the distinction explicit and executable.

## 3. RPO/RTO honesty (directive: do not claim achieved)

- **RPO ≤ 24h: NOT ACHIEVED** — it is a recorded acceptance THRESHOLD (D7),
  not a running guarantee. In the current posture (no scheduled backups
  operating on any machine), the real RPO is UNBOUNDED until the owner
  activates a cadence (§2).
- **RTO ≤ 15m: NOT PROVEN** — restore is a documented procedure with a
  functional (untimed) test repo-side; a TIMED drill on the target machine is
  required evidence.

## 4. Target-machine restore drill — prepared; exact evidence still required

Drill spec (added to `TARGET_MACHINE_EVIDENCE_CHECKLIST_2026-11-02.md` phase
table; exact steps):
1. Prereq: store with ≥1 appended artifact; key available (env or keyring).
2. `python -m app.data.research_memory_sqlite backup --directory <store> --dest <backups> --keep 14` — record wall-clock start/end (timed).
3. `python -m app.data.research_memory_sqlite verify-backup --path <snapshot>` — must exit 0 (no refusal reasons).
4. Restore step: copy snapshot back to a FRESH directory as the DB file; run `verify_integrity` against it; assert all artifacts readable and digests match.
5. **Evidence to record:** timed durations for steps 2–4 (RTO measurement ≤ 900s), snapshot sha256, sidecar verification output, integrity report text, machine identifier, date. RPO evidence additionally requires the owner's activated cadence (§2) running for ≥1 full day with two consecutive snapshots.
6. Until that bundle exists: **RPO/RTO remain "threshold recorded, NOT
   achieved/not proven"** — stated, not hidden.

## 5. Forbidden paths re-verified (directive §3 final paragraph)

No plaintext fallback (invalid/missing key refuses, exit 2); no purge path
(RETENTION_POLICY permanent; no delete/update); no external backup
transmission (snapshot lands in a local directory only; no network code in the
module); no automatic runtime activation (dormancy source guard pinned).
