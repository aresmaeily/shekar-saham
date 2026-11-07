"""ai2_ledger_sqlite.py — DORMANT prototype persistence adapter for the AI-2
candidate registry + run ledger (WAVE-B, WP-B work item 2b).

DORMANCY CONTRACT (read before touching this module):
- NOTHING in ``app/services`` or ``app/api`` imports this module. The
  in-memory ``GenerationCandidateRegistry`` + ``AI2RunLedger`` remain the
  ONLY runtime stores; process restart clears them BY DESIGN until the owner
  records the D-A2-1…D-A2-7 decisions
  (``docs/active/AI2_PERSISTENCE_DECISION_PACKET.md``; the in-memory honesty
  disclosure is pinned in ``ai2_generation.py``'s "Storage honesty" bullet
  and in the posture payload). Import-graph dormancy is TEST-PINNED
  (``backend/tests/test_ai2_persistence_kit.py`` walks the tree).
- ``AI2_ENABLED`` (default ``0``) stays the EXECUTION gate; persistence
  activation is a SEPARATE owner act (D-A2-5). This module reads NO settings
  and NO environment variables and exposes NO factory — activation wiring is
  itself the owner's reviewed change.
- Everything this module may ever store is synthetic/paper-only research
  evidence (SYNTHETIC_OR_PAPER labels); it never touches market data, the
  broker, or any notification surface.

Engineering discipline: mirrors ``backend/app/services/prediction_store.py``
(OA-5 production precedent) as closely as the different record family
allows:

- pragmas: ``journal_mode=WAL`` + ``synchronous=FULL`` + ``busy_timeout`` +
  ``foreign_keys=ON``; writes run under ``BEGIN IMMEDIATE`` inside a process
  lock; UNIQUE constraints are the cross-process hard guarantee — a lost
  race is translated to the same typed refusal (or to idempotent success
  when the byte-identical record already exists);
- append-only: INSERT-only paths only; there is NO update/delete/purge/
  retention API anywhere on the class surface (structural, test-pinned via
  ``dir()``); retention policy constant exported like the prediction store's;
- migrations: versioned DDL with pinned SQL digests; an applied digest that
  no longer matches fails closed (``schema_digest_mismatch``);
- integrity: ``PRAGMA integrity_check`` + per-row SHA-256 verification at
  open and restore time; any mismatch fails closed
  (:class:`AI2LedgerCorruption`) and is recoverable ONLY from a verified
  backup produced by :meth:`DurableAI2LedgerStore.backup`;
- restore-refuses-unverified: the source is fully verified (existence,
  integrity, pinned schema digests, every row digest, counts) BEFORE it
  replaces the live file;
- clock-free: no wall-clock read in this module; records carry the
  caller-supplied instants already frozen inside their payloads.

Tables (append-only; full record payloads, nothing synthesized):
- ``ai2_run_records``       — one row per ``AI2RunRecord`` (canonical JSON);
- ``ai2_candidate_records`` — one row per generation candidate (canonical
  JSON payload supplied by the caller; the candidate model lives in the
  service layer, and a DORMANT data adapter does not import services);
- ``ai2_duplicate_keys``    — the persisted ``classify_duplicate`` key space
  (task, input_snapshot_sha256) with the first claimant record id;
- ``ai2_ledger_meta``       — monotonic ledger version, mirroring the
  prediction store's registry-version bump discipline.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.domain.ai2_governance import AI2RunRecord

SCHEMA_VERSION = "AI2-LEDGER-STORE-V1"
RETENTION_POLICY = "APPEND_ONLY_NO_SILENT_DELETION__PURGE_IS_OWNER_GATED"

DORMANCY_NOTE = (
    "پروتوتایپ ذخیره‌سازی AI-2 خفته است (DORMANT): هیچ مسیر runtime آن را "
    "وارد نمی‌کند؛ فعال‌سازی مستلزم تصمیم مالک است"
)


class AI2LedgerStoreError(Exception):
    """Typed store failure (reason string carried on ``reason``)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AI2LedgerCorruption(AI2LedgerStoreError):
    """Fail-closed corruption detection (integrity/digest/schema mismatch)."""


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _row_digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_rollback(conn: sqlite3.Connection) -> None:
    """ROLLBACK that never masks the original failure (no active tx = ok)."""
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


_MIGRATION_V1 = """
CREATE TABLE IF NOT EXISTS ai2_run_records (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    row_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai2_candidate_records (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    row_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai2_duplicate_keys (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    input_snapshot_sha256 TEXT NOT NULL,
    record_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    row_digest TEXT NOT NULL,
    UNIQUE(task, input_snapshot_sha256)
);
CREATE TABLE IF NOT EXISTS ai2_ledger_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# (sql, sha256 of the exact SQL text) — a mismatch fails closed.
_MIGRATIONS: Dict[int, Tuple[str, str]] = {
    1: (
        _MIGRATION_V1,
        hashlib.sha256(_MIGRATION_V1.encode("utf-8")).hexdigest(),
    )
}

_ROW_TABLES: Tuple[str, ...] = ("ai2_run_records", "ai2_candidate_records", "ai2_duplicate_keys")


class DurableAI2LedgerStore:
    """DORMANT SQLite/WAL append-only store for AI-2 run + candidate records.

    No runtime caller exists (see module docstring); the class is exercised
    only by its own battery so the owner's D-A2 decisions can be executed
    directly once recorded.
    """

    backend_label = "sqlite-wal-dormant-prototype"
    persistence_durable = True

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection = self._open()
        self.persistence_note = DORMANCY_NOTE

    # ------------------------------------------------------------------ open
    def _open(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(
                str(self._db_path),
                isolation_level=None,
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA foreign_keys=ON")
            row = conn.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                conn.close()
                raise AI2LedgerCorruption(
                    f"integrity_check_failed:{row[0] if row else 'no-result'}"
                )
        except sqlite3.DatabaseError as exc:
            raise AI2LedgerCorruption(f"open_failed:{exc}") from exc
        self._migrate(conn)
        self._verify_all_rows(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY,"
            "sql_digest TEXT NOT NULL)"
        )
        applied = {
            int(r[0]): r[1]
            for r in conn.execute(
                "SELECT version, sql_digest FROM schema_migrations"
            ).fetchall()
        }
        for version in sorted(_MIGRATIONS):
            sql, digest = _MIGRATIONS[version]
            if version in applied:
                if applied[version] != digest:
                    raise AI2LedgerCorruption("schema_digest_mismatch")
                continue
            statements = [st.strip() for st in sql.split(";") if st.strip()]
            try:
                conn.execute("BEGIN IMMEDIATE")
                for statement in statements:
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations(version, sql_digest) VALUES (?, ?)",
                    (version, digest),
                )
                conn.execute("COMMIT")
            except sqlite3.Error:
                _safe_rollback(conn)
                raise

    def _verify_all_rows(self, conn: sqlite3.Connection) -> None:
        for table in _ROW_TABLES:
            for payload, digest in conn.execute(
                f"SELECT payload, row_digest FROM {table}"  # noqa: S608 (pinned tables)
            ).fetchall():
                if _row_digest(payload) != digest:
                    raise AI2LedgerCorruption(f"row_digest_mismatch:{table}")

    # ------------------------------------------------------------- internals
    @property
    def ledger_version(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM ai2_ledger_meta WHERE key='ledger_version'"
            ).fetchone()
            return int(row[0]) if row else 0

    def _bump_version_locked(self, conn: sqlite3.Connection) -> int:
        next_version = self.ledger_version + 1
        conn.execute(
            "INSERT INTO ai2_ledger_meta(key, value) VALUES ('ledger_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(next_version),),
        )
        return next_version

    def _get_row(
        self, conn: sqlite3.Connection, table: str, id_column: str, record_key: str
    ) -> Optional[Tuple[str, str]]:
        return conn.execute(
            f"SELECT payload, row_digest FROM {table} WHERE {id_column}=?",  # noqa: S608 (pinned tables/columns)
            (record_key,),
        ).fetchone()

    # ---------------------------------------------------------------- public
    def append_run_record(self, record: AI2RunRecord) -> Dict[str, Any]:
        """Append one ``AI2RunRecord``; byte-identical re-append is a no-op.

        Mirrors ``AI2RunLedger.append``: identical record = idempotent
        success; a DIFFERENT payload under the same record_id = typed
        conflict refusal (``ai2_ledger_record_conflict``).
        """
        payload = _canonical_json(record.model_dump(mode="json"))
        digest = _row_digest(payload)
        with self._lock:
            existing = self._get_row(
                self._conn, "ai2_run_records", "record_id", record.record_id
            )
            if existing is not None:
                if existing[1] == digest:
                    return {
                        "ledger_version": self.ledger_version,
                        "duplicate_of_existing": True,
                    }
                raise AI2LedgerStoreError("ai2_ledger_record_conflict")
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._get_row(
                    self._conn, "ai2_run_records", "record_id", record.record_id
                )
                if row is not None:  # lost a race: same typed semantics
                    _safe_rollback(self._conn)
                    if row[1] == digest:
                        return {
                            "ledger_version": self.ledger_version,
                            "duplicate_of_existing": True,
                        }
                    raise AI2LedgerStoreError("ai2_ledger_record_conflict")
                self._conn.execute(
                    "INSERT INTO ai2_run_records(record_id, payload, row_digest) "
                    "VALUES (?, ?, ?)",
                    (record.record_id, payload, digest),
                )
                version = self._bump_version_locked(self._conn)
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                _safe_rollback(self._conn)
                raise AI2LedgerStoreError("ai2_ledger_record_conflict") from exc
            return {"ledger_version": version, "duplicate_of_existing": False}

    def append_candidate_record(self, candidate_id: str, payload: str) -> Dict[str, Any]:
        """Append one candidate record from its CANONICAL JSON payload.

        The caller (at activation time) passes
        ``_canonical_json(candidate.model_dump(mode="json"))``; the adapter
        digests exactly what it stores, so a byte-identical re-append is an
        idempotent no-op and a different payload under the same candidate_id
        is refused (``ai2_candidate_record_conflict``).
        """
        payload = str(payload)
        digest = _row_digest(payload)
        with self._lock:
            existing = self._get_row(
                self._conn, "ai2_candidate_records", "candidate_id", candidate_id
            )
            if existing is not None:
                if existing[1] == digest:
                    return {
                        "ledger_version": self.ledger_version,
                        "duplicate_of_existing": True,
                    }
                raise AI2LedgerStoreError("ai2_candidate_record_conflict")
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._get_row(
                    self._conn, "ai2_candidate_records", "candidate_id", candidate_id
                )
                if row is not None:
                    _safe_rollback(self._conn)
                    if row[1] == digest:
                        return {
                            "ledger_version": self.ledger_version,
                            "duplicate_of_existing": True,
                        }
                    raise AI2LedgerStoreError("ai2_candidate_record_conflict")
                self._conn.execute(
                    "INSERT INTO ai2_candidate_records(candidate_id, payload, row_digest) "
                    "VALUES (?, ?, ?)",
                    (candidate_id, payload, digest),
                )
                version = self._bump_version_locked(self._conn)
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                _safe_rollback(self._conn)
                raise AI2LedgerStoreError("ai2_candidate_record_conflict") from exc
            return {"ledger_version": version, "duplicate_of_existing": False}

    def record_duplicate_key(
        self, task: str, input_snapshot_sha256: str, record_id: str
    ) -> Dict[str, Any]:
        """Persist one ``classify_duplicate`` key (task, input snapshot).

        Idempotent for the identical (task, snapshot, record) triple; the
        same (task, snapshot) pair claimed by a DIFFERENT record is refused
        (``duplicate_key_conflict``) — the key space stays append-only.
        """
        key_payload = _canonical_json(
            {
                "task": task,
                "input_snapshot_sha256": input_snapshot_sha256,
                "record_id": record_id,
            }
        )
        digest = _row_digest(key_payload)
        with self._lock:
            existing = self._conn.execute(
                "SELECT payload, row_digest FROM ai2_duplicate_keys "
                "WHERE task=? AND input_snapshot_sha256=?",
                (task, input_snapshot_sha256),
            ).fetchone()
            if existing is not None:
                if existing[1] == digest:
                    return {
                        "ledger_version": self.ledger_version,
                        "duplicate_of_existing": True,
                    }
                raise AI2LedgerStoreError("duplicate_key_conflict")
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute(
                    "SELECT payload, row_digest FROM ai2_duplicate_keys "
                    "WHERE task=? AND input_snapshot_sha256=?",
                    (task, input_snapshot_sha256),
                ).fetchone()
                if row is not None:
                    _safe_rollback(self._conn)
                    if row[1] == digest:
                        return {
                            "ledger_version": self.ledger_version,
                            "duplicate_of_existing": True,
                        }
                    raise AI2LedgerStoreError("duplicate_key_conflict")
                self._conn.execute(
                    "INSERT INTO ai2_duplicate_keys("
                    "task, input_snapshot_sha256, record_id, payload, row_digest) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (task, input_snapshot_sha256, record_id, key_payload, digest),
                )
                version = self._bump_version_locked(self._conn)
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                _safe_rollback(self._conn)
                raise AI2LedgerStoreError("duplicate_key_conflict") from exc
            return {"ledger_version": version, "duplicate_of_existing": False}

    # ----------------------------------------------------------------- reads
    def read_run_records(self) -> Tuple[AI2RunRecord, ...]:
        """Decode every stored run record verbatim (nothing synthesized)."""
        with self._lock:
            return tuple(
                AI2RunRecord.model_validate_json(payload)
                for (payload,) in self._conn.execute(
                    "SELECT payload FROM ai2_run_records ORDER BY seq ASC"
                ).fetchall()
            )

    def read_candidate_payloads(self) -> List[Dict[str, Any]]:
        """Decode every stored candidate payload (canonical JSON dicts)."""
        with self._lock:
            return [
                json.loads(payload)
                for (payload,) in self._conn.execute(
                    "SELECT payload FROM ai2_candidate_records ORDER BY seq ASC"
                ).fetchall()
            ]

    def read_duplicate_keys(self) -> Tuple[Dict[str, str], ...]:
        with self._lock:
            return tuple(
                {"task": task, "input_snapshot_sha256": snapshot, "record_id": record_id}
                for task, snapshot, record_id in self._conn.execute(
                    "SELECT task, input_snapshot_sha256, record_id "
                    "FROM ai2_duplicate_keys ORDER BY seq ASC"
                ).fetchall()
            )

    def counts(self) -> Dict[str, int]:
        with self._lock:
            return {
                table: int(self._conn.execute(
                    f"SELECT COUNT(*) FROM {table}"  # noqa: S608 (pinned tables)
                ).fetchone()[0])
                for table in _ROW_TABLES
            }

    # ------------------------------------------------------- backup/restore
    def backup(self, target_path: Path | str) -> Dict[str, Any]:
        """Verified backup: SQLite backup API + integrity + digest checks."""
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            dest = sqlite3.connect(str(target), isolation_level=None)
            try:
                self._conn.backup(dest)
                row = dest.execute("PRAGMA integrity_check").fetchone()
                if not row or row[0] != "ok":
                    raise AI2LedgerCorruption(
                        f"backup_integrity_failed:{row[0] if row else 'no-result'}"
                    )
            finally:
                dest.close()
            data = target.read_bytes()
            return {
                "path": str(target),
                "sha256": hashlib.sha256(data).hexdigest(),
                "byte_size": len(data),
                "verified": True,
            }

    def restore(self, source_path: Path | str) -> Dict[str, Any]:
        """Fail-closed restore: verify source BEFORE swapping it in."""
        source = Path(source_path)
        if not source.exists():
            raise AI2LedgerCorruption("restore_source_missing")
        check = sqlite3.connect(str(source), isolation_level=None)
        try:
            row = check.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise AI2LedgerCorruption(
                    f"restore_source_corrupt:{row[0] if row else 'no-result'}"
                )
            migrations = {
                int(r[0]): r[1]
                for r in check.execute(
                    "SELECT version, sql_digest FROM schema_migrations"
                ).fetchall()
            }
            for version, (_, digest) in _MIGRATIONS.items():
                if migrations.get(version) != digest:
                    raise AI2LedgerCorruption("restore_schema_digest_mismatch")
            for table in _ROW_TABLES:
                for payload, d in check.execute(
                    f"SELECT payload, row_digest FROM {table}"  # noqa: S608 (pinned tables)
                ).fetchall():
                    if _row_digest(payload) != d:
                        raise AI2LedgerCorruption(
                            f"restore_row_digest_mismatch:{table}"
                        )
            counts = {
                table: int(check.execute(
                    f"SELECT COUNT(*) FROM {table}"  # noqa: S608 (pinned tables)
                ).fetchone()[0])
                for table in _ROW_TABLES
            }
        except sqlite3.DatabaseError as exc:
            raise AI2LedgerCorruption(f"restore_source_unreadable:{exc}") from exc
        finally:
            check.close()
        with self._lock:
            self._conn.close()
            for suffix in ("-wal", "-shm"):
                stale = Path(str(self._db_path) + suffix)
                if stale.exists():
                    stale.unlink()
            os.replace(source, self._db_path)
            self._conn = self._open()
            return {"restored_counts": counts, "verified": True}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
