# AI-3 IMPLEMENTATION READINESS RECORD — 2026-11-02 (WS-7, prepare-only)

Directive item: WS-7 — "AI-3 owner-gated implementation readiness: prepare
backend implementation options and migration plan, adapter contract and
failure semantics, backup/restore validation, encryption and key-management
design, retention and no-purge guarantees, access-control and recovery
acceptance tests. Do NOT select the production backend, retention policy,
encryption method, backup destination, access model or RPO/RTO on the
owner's behalf."

**Status: D1–D7 ALL PENDING. The production adapter remains BLOCKED by the
execution gate (`AI3_PERSISTENCE_DECISION_PACKET.md` §11: implementation
starts only after all seven decisions are recorded). This record prepares
 NOTHING that requires an answer; it consolidates what is ready and closes
 the one genuine preparation gap (encryption/key-management options).**

## 1. Readiness matrix (WS-7 item → prepared artifact → what fires on which answer)

| WS-7 item | Prepared where | Ready? | Fires when |
|---|---|---|---|
| Backend implementation options + migration plan | `AI3_PERSISTENCE_DECISION_PACKET.md` §1 (D1 options + consequences), `AI3_PERSISTENCE_IMPLEMENTATION_PLAN.md` §3.1 (variant mapping) + §4.6 (migration + rollback rehearsal, forward AND back) | ✅ | D1 (engine class) recorded |
| Deployment target conditioning | plan §3.2 | ✅ | D2 |
| Adapter contract + failure semantics | `domain/research_memory_store.py` Protocol + in-memory reference adapter; acceptance scaffold `test_ai3_acceptance_scaffold.py` **56 collected tests over 2 factories** (acc01–acc30; WS-5 enrichment added acc25–acc30: duplicate-identity conflicts, PIT-invisible promotion refusal, order-honesty, semantic all-or-nothing crash consistency, timestamp discipline, empty-store explicitness); failure semantics = fail-closed refusal records, append-only, no-purge structural | ✅ any future adapter plugs in via one `STORE_FACTORIES` entry and must pass all 56 | D1–D7 complete → implementation start |
| Backup/restore validation | plan §4.4 (backup/restore/crash-recovery rehearsal design); product-DB precedent exists (`Store.backup(keep=7)`, `BACKUP_RESTORE_RUNBOOK.md`) | ✅ design; execution rehearsal is post-D5 | D5 (destination + cadence) |
| **Encryption & key-management design** | **§2 of THIS record (new — was a genuine gap)** | ✅ options only | D4 (method) |
| Retention + no-purge guarantees | packet §3 (D3 immutability class), plan §4.2; structural no-purge for episodic evidence is ARCHITECTURAL regardless of D3 (append-only; the repo's only DELETE paths are the 4 namespaced `alert_ops_*`) | ✅ | D3 (per-class retention table must NOT touch episodic evidence) |
| Access-control + recovery acceptance tests | plan §5 Table A (store-level, pinned today) + Table B (binding adapter-level, packet §10 list); packet §10 full acceptance-test binding; access-control reality check = packet §10 test 8 | ✅ | D4/D6; recovery thresholds need D7 RPO/RTO numbers |
| Timing / sequencing | plan §3.7 (D7 decide-now vs post-G2), §1 execution gate | ✅ | D7 |

## 2. Encryption & key-management OPTIONS (new preparation; NO option selected)

Scope: at-rest encryption of the AI-3 research-memory store and its content-
addressed blobs, single-operator Windows-first deployment (A12) unless D2/D4
say otherwise. Every option below must compose with: append-only + sha256
content addressing (encryption sits BELOW the integrity layer — digests are
computed over canonical plaintext, then the container is encrypted; re-verify
after decrypt, never over ciphertext), the no-purge guarantee, PIT retrieval,
and the test-layer acceptance scaffold (a future encrypted adapter must still
pass all 56 scaffold tests with encryption treated as a container property).

| Option | Mechanism | Failure semantics | Backup/restore implication | Key-management surface | Main trade-off |
|---|---|---|---|---|---|
| E-A Windows DPAPI (user-scoped) | `CryptProtectData` per-file or per-container key | Undecryptable = fail-closed refusal records (honest unavailability, never plaintext fallback); files unusable under a different Windows user | Backups restorable only by the same Windows user (or with a machine/user migration blob) | No key file to manage; OS protects the user's master key | Simplest single-operator path; backups tied to the user profile — restore onto a rebuilt machine needs DPAPI key migration |
| E-B OS keyring (Windows Credential Manager / DPAPI-protected key) | Random data key per store; key (or key-wrapping secret) in the OS credential store | Same fail-closed class; keyring absent → explicit refusal record at open | Data backups portable; key export/import is a documented manual step | Key rotation = re-wrap operation (data untouched) | Separates key from data; slightly more code than E-A; still single-machine bound |
| E-C Key file with passphrase (KDF-wrapped, e.g. scrypt/argon2 → AES-GCM container) | Owner-held key file + passphrase; authenticated encryption | Wrong passphrase/missing file → fail-closed refusal records; GCM tag failure = tamper refusal (composes with integrity layer) | Fully portable backups (file + key file + passphrase) | Owner must safeguard the key file offline; passphrase recovery is owner's sole responsibility | Portable across machines/users; strongest owner-side key custody duty |
| E-D No encryption (ACL + file permissions only) | NTFS ACLs; the D4 file-permission class | n/a (no crypto failure class) | Plain backups (disk-level protection only) | None | Only honest if the owner accepts plaintext episodic evidence at rest; MUST be an explicit owner answer, not a default |

Cross-cutting guarantees for ANY chosen option (repo-side, decision-free):
- Fail-closed: an undecryptable store NEVER falls back to plaintext or to a
  synthetic substitute; it opens into refusal records.
- No key material in source, logs, reports, or chat (standing control).
- The test-layer JSONL adapter remains UNENCRYPTED and TEST-LAYER-ONLY — it
  is not a production persistence implementation and never was.
- Key rotation and lost-key behavior are documented per option BEFORE
  implementation; neither is improvised at incident time.

## 3. What starts automatically once D1–D7 are recorded

1. Variant selection per plan §3 (mechanical: each D answer maps to a
   variant row — no new analysis required).
2. Adapter implementation against the Protocol + `STORE_FACTORIES`
   registration; the 56-test scaffold (plus Table-B engine-level bindings
   from packet §10) is the acceptance gate.
3. Migration/rollback rehearsal (§4.6), backup/restore rehearsal (§4.4)
   scaled to the D5 answer, recovery drill against the D7 RPO/RTO numbers.
4. Everything remains inside the standing controls: no live data, no
   production mutation, no purge path, no owner decision fabricated.
