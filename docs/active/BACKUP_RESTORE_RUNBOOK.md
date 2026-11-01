# BACKUP & RESTORE RUNBOOK — RADAR BOURSE

Created: 2026-11-02 (MA-1 consolidated multi-agent cycle, WS-11 — closing the
audited absence of a standalone backup/restore runbook).
Scope: the product SQLite database (`shekar.db`), its WAL sidecars, and the
`data/backups/` rotation. This runbook documents existing, verified code
paths; it introduces no new mechanism.

---

## 1. What exists in code (verified paths)

| Mechanism | Location | Behavior |
|---|---|---|
| Scheduled/invoked backup | `backend/app/data/store.py` → `Store.backup(keep=7)` | `PRAGMA wal_checkpoint(TRUNCATE)` then copy2 of the DB file to `data/backups/shekar-<YYYYmmdd-HHMMSS>.db`; prunes older copies beyond `keep` (default 7) |
| Backup directory | `data/backups/` | Created on demand (`mkdir -p`) |
| WAL mode | SQLite WAL throughout (`store.py` schema init) | Readers/writers safe; checkpoint before copy |
| Migrations | `PRAGMA user_version` guarded, idempotent, additive (`if current < version`) | Restoring an older file re-runs pending migrations on next open |
| Alert-ops store | `backend/app/data/alert_ops_store.py` | Separate additive SQLite tables in the SAME database file; documented reversible rollback = archive rename preserving every record |

## 2. Backup procedure (standard)

1. Ensure the backend process is running normally (or stopped cleanly — both
   are safe; WAL checkpoint is performed inside `backup()`).
2. Trigger `Store.backup()` (operator call or the existing startup/path that
   invokes it). Verify: a new file `data/backups/shekar-<stamp>.db` exists and
   `PRAGMA integrity_check` on the copy returns `ok`
   (`sqlite3 data/backups/shekar-<stamp>.db "PRAGMA integrity_check;"`).
3. Copy the newest backup OFF the machine for offsite safety (owner policy;
   the in-app rotation keeps only the last 7).
4. Record in the install checklist: timestamp, file size, sha256, integrity
   result.

Limitations (honest): `backup()` copies the main database file after a
TRUNCATE checkpoint; any external sidecar files are not bundled. The research
artifact/blob store (AI-3) does not exist yet — the persistence adapter is
BLOCKED on owner decisions D1–D7 (`docs/active/AI3_PERSISTENCE_DECISION_PACKET.md`);
when it lands, THIS runbook gains a section for its backup/restore per D5.

## 3. Restore procedure (standard)

1. Stop the backend (uvicorn / Docker container / Electron shell).
2. Move the current database aside — never delete in place:
   `mv data/shekar.db data/shekar.db.pre-restore-<stamp>` (WAL/SHM sidecars
   alongside, if present: move them too).
3. Copy the chosen backup into place: `cp data/backups/shekar-<stamp>.db data/shekar.db`.
4. Start the backend. On open, `PRAGMA user_version` drives any pending
   additive migrations automatically (verified behavior in `store.py`).
5. Health gate: `GET /api/health` returns 200 with `version == 3.0.0`;
   spot-check overview data and the alerts inbox.
6. Record the restore in the checklist (what was restored, why, evidence).

## 4. Alert-ops rollback (D-AI-30 store)

The alert-ops tables ship with a documented REVERSIBLE rollback: archive
rename preserving every record (see `GOV41_DAI30_IMPLEMENTATION_RECORD_2026-10-30.md`
and `alert_ops_store.py` docstrings). Use THAT documented path for alert-ops
schema rollback; do not hand-drop tables.

## 5. Disaster scenarios

| Scenario | Action |
|---|---|
| DB file corrupted (integrity_check fails) | Restore per §3 from the newest healthy backup; keep the corrupted file for forensics |
| Bad release / schema regression | Restore the pre-install backup per §3; the app version is pinned `3.0.0` and additive migrations re-apply idempotently |
| Lost WAL sidecars after crash | Stop backend; on next open SQLite recovers/ignores orphaned WAL; if the main file is damaged → §3 |
| `data/backups/` lost | No server-side copy exists (rotation only) — restore from the OFFSITE copy taken in §2.3; if none exists, data since the last offsite copy is unrecoverable (record honestly) |

## 6. Verification drills (recommended before alpha launch)

1. Backup drill: run §2, note sha256 + integrity_check ok.
2. Restore drill: §3 against a THROWAWAY copy of the data directory (never
   the live one), confirm health + data, discard the drill copy.
3. Record both drills in `docs/active/ALPHA_INSTALLATION_CHECKLIST.md`
   POST-INSTALL rows.
