"""Durable storage for the AI-3 memory ACCESS/OPERATION audit trail
(2026-11-08 owner directive §3 AI-3: «تکمیل audit trail پایدار» + next-stage
directive item 2, now owner-ordered to be WIRED into the real application
cycle — «پیاده‌سازی مستقل یک ماژول به معنی اتصال آن به محصول نیست»).

Mirrors the prediction-store precedent (``app.services.prediction_store``,
OA-5) exactly:

- SQLite with ``journal_mode=WAL`` + ``synchronous=FULL`` + ``busy_timeout``
  + ``foreign_keys=ON``; append-only INSERT path; a process RLock plus
  ``BEGIN IMMEDIATE`` serialise writers; ``UNIQUE(sequence)`` is the
  cross-thread hard guarantee (a lost race becomes the same typed refusal);
- pinned-digest migrations: versioned DDL whose applied ``sql_digest`` must
  match forever, else fail closed (``memory_audit_schema_digest_mismatch``);
- per-row SHA-256 tamper evidence verified at open/restore time;
- the SHA-256 HASH CHAIN of the domain trail (``MemoryAccessAuditTrail``)
  is re-verified on every open: a single-byte storage tamper closes the
  gate permanently (fail-closed, never healed, never re-opened) — appends
  refuse while the gate is closed and ``first_broken_sequence`` reports the
  honest break point;
- verified backup via the SQLite backup API (integrity-checked) and
  fail-closed restore that verifies the source BEFORE swapping it in;
- restart recovery: the full chain is rebuilt from disk and re-verified at
  construction;
- clock-free: NO wall-clock read anywhere in this module — every entry's
  instant is the caller-supplied one already carried by the domain entry.

The domain vocabulary, entry validation and chain semantics live in
``app.domain.memory_access_audit`` and are NEVER re-implemented here: the
durable store composes the domain trail (composition, not replacement).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.domain.memory_access_audit import (
    MemoryAccessAuditChainBroken,
    MemoryAccessAuditEntry,
    MemoryAccessAuditTrail,
)

SCHEMA_VERSION = "MEMORY-AUDIT-STORE-V1"
RETENTION_POLICY = "APPEND_ONLY_NO_SILENT_DELETION__PURGE_IS_OWNER_GATED"


class MemoryAuditStoreError(Exception):
    """Typed durable-audit failure (reason string carried on ``reason``)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class MemoryAuditStoreCorruption(MemoryAuditStoreError):
    """Fail-closed corruption detection (integrity/digest/schema/chain)."""


def _full_payload(entry: MemoryAccessAuditEntry) -> str:
    """FULL canonical serialization INCLUDING ``entry_digest`` — the stored
    row must reconstruct the entry verbatim (the domain model re-validates
    the chain digest on every load, so a tampered row fails closed twice)."""
    return json.dumps(
        entry.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _row_digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_rollback(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


_MIGRATION_V1 = """
CREATE TABLE IF NOT EXISTS audit_entries (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER NOT NULL UNIQUE,
    entry_digest TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    row_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_meta (
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


class DurableMemoryAccessAuditTrail:
    """SQLite/WAL append-only carrier for the tamper-evident audit chain.

    Composes the domain ``MemoryAccessAuditTrail``: the domain object remains
    the ONLY chain-semantics authority; this class persists its entries,
    re-verifies them at open (row digests + full chain), and refuses appends
    when anything fails verification (fail-closed closed-gate posture).
    """

    backend_label = "sqlite-wal"
    persistence_durable = True

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.RLock()
        self._gate_closed_reason: Optional[str] = None
        self._conn: sqlite3.Connection = self._open()
        self.persistence_note = (
            "ردیف حسابرسی دسترسی به حافظه پژوهش ماندگار است (SQLite/WAL، "
            f"ضمیمه-فقط، زنجیره SHA-256، هش صحت سطر): {self._db_path}"
        )

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
                raise MemoryAuditStoreCorruption(
                    f"integrity_check_failed:{row[0] if row else 'no-result'}"
                )
        except sqlite3.DatabaseError as exc:
            raise MemoryAuditStoreCorruption(f"open_failed:{exc}") from exc
        self._migrate(conn)
        self._verify_all_rows(conn)
        conn2_trail, broken = self._rebuild_trail(conn)
        if broken is not None:
            # The persisted chain does not verify: the gate opens CLOSED
            # (fail-closed posture; never healed, never re-opened here).
            self._gate_closed_reason = broken
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
                    raise MemoryAuditStoreCorruption("memory_audit_schema_digest_mismatch")
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
        for payload, digest in conn.execute(
            "SELECT payload, row_digest FROM audit_entries"
        ).fetchall():
            if _row_digest(payload) != digest:
                raise MemoryAuditStoreCorruption("memory_audit_row_digest_mismatch")

    # ------------------------------------------------------------- chain view
    def _rebuild_trail(
        self, conn: sqlite3.Connection
    ) -> Tuple[Optional[MemoryAccessAuditTrail], Optional[str]]:
        """Rebuild the domain chain from disk; classify an unverifiable chain
        as a CLOSED GATE (never healed, never re-opened) instead of crashing
        the whole application surface."""
        rows = conn.execute(
            "SELECT payload, sequence FROM audit_entries ORDER BY sequence ASC"
        ).fetchall()
        entries: List[MemoryAccessAuditEntry] = []
        for payload, _seq in rows:
            raw = json.loads(payload)
            entries.append(MemoryAccessAuditEntry(**raw))
        try:
            return MemoryAccessAuditTrail(tuple(entries)), None
        except (ValueError, MemoryAccessAuditChainBroken) as exc:
            return None, f"memory_audit_chain_broken:{exc}"

    # ---------------------------------------------------------------- append
    def append(self, entry: MemoryAccessAuditEntry) -> Dict[str, Any]:
        """Verify-before-accept, then persist one entry (append-only)."""
        with self._lock:
            if self._gate_closed_reason is not None:
                raise MemoryAuditStoreError(self._gate_closed_reason)
            current, broken = self._rebuild_trail(self._conn)
            if broken is not None or current is None:
                self._gate_closed_reason = broken or "memory_audit_chain_broken"
                raise MemoryAuditStoreCorruption(self._gate_closed_reason)
            try:
                current.append(entry)  # domain chain validates (fail-closed)
            except (ValueError, MemoryAccessAuditChainBroken) as exc:
                raise MemoryAuditStoreError(f"memory_audit_append_refused:{exc}") from exc
            payload = _full_payload(entry)
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    "INSERT INTO audit_entries(sequence, entry_digest, payload, row_digest)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        entry.sequence,
                        entry.entry_digest,
                        payload,
                        _row_digest(payload),
                    ),
                )
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError:
                _safe_rollback(self._conn)
                raise MemoryAuditStoreError("memory_audit_sequence_already_recorded")
            except sqlite3.Error as exc:
                _safe_rollback(self._conn)
                raise MemoryAuditStoreError(f"memory_audit_write_failed:{exc}") from exc
            return {
                "sequence": entry.sequence,
                "entry_digest": entry.entry_digest,
                "head_digest": current.head_digest,
                "verified": True,
            }

    # ------------------------------------------------------------- read side
    def entries(self) -> Tuple[MemoryAccessAuditEntry, ...]:
        with self._lock:
            trail, broken = self._rebuild_trail(self._conn)
            if trail is None:
                return ()
            return trail.entries

    def head_digest(self) -> Optional[str]:
        with self._lock:
            trail, _broken = self._rebuild_trail(self._conn)
            return trail.head_digest if trail is not None else None

    def first_broken_sequence(self) -> Optional[int]:
        with self._lock:
            trail, _broken = self._rebuild_trail(self._conn)
            if trail is None:
                return -1  # closed gate: chain itself could not be rebuilt
            return trail.first_broken_sequence()

    def gate_closed_reason(self) -> Optional[str]:
        return self._gate_closed_reason

    def counts(self) -> Dict[str, int]:
        with self._lock:
            n = int(
                self._conn.execute("SELECT COUNT(*) FROM audit_entries").fetchone()[0]
            )
            return {"entries": n}

    def record(
        self,
        *,
        actor: str,
        authorization_context: str,
        operation: str,
        object_ref: str,
        at_utc: Any,
        run_id: Optional[str] = None,
        outcome: str = "OK",
        refusal_reason: Optional[str] = None,
        detail: str = "",
    ) -> Dict[str, Any]:
        """Mint (domain vocabulary) + persist in one step."""
        with self._lock:
            current, broken = self._rebuild_trail(self._conn)
            if broken is not None or current is None:
                self._gate_closed_reason = broken or "memory_audit_chain_broken"
                raise MemoryAuditStoreCorruption(self._gate_closed_reason)
            try:
                current.record(
                    actor=actor,
                    authorization_context=authorization_context,
                    operation=operation,  # type: ignore[arg-type]
                    object_ref=object_ref,
                    at_utc=at_utc,
                    run_id=run_id,
                    outcome=outcome,  # type: ignore[arg-type]
                    refusal_reason=refusal_reason,
                    detail=detail,
                )
            except (ValueError, MemoryAccessAuditChainBroken) as exc:
                raise MemoryAuditStoreError(f"memory_audit_record_refused:{exc}") from exc
            entry = current.entries[-1]
            payload = _full_payload(entry)
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    "INSERT INTO audit_entries(sequence, entry_digest, payload, row_digest)"
                    " VALUES (?, ?, ?, ?)",
                    (entry.sequence, entry.entry_digest, payload, _row_digest(payload)),
                )
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError:
                _safe_rollback(self._conn)
                raise MemoryAuditStoreError("memory_audit_sequence_already_recorded")
            except sqlite3.Error as exc:
                _safe_rollback(self._conn)
                raise MemoryAuditStoreError(f"memory_audit_write_failed:{exc}") from exc
            return {
                "sequence": entry.sequence,
                "entry_digest": entry.entry_digest,
                "head_digest": current.head_digest,
                "verified": True,
            }

    # ---------------------------------------------------------- backup/restore
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
                    raise MemoryAuditStoreCorruption(
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
            raise MemoryAuditStoreCorruption("memory_audit_restore_source_missing")
        check = sqlite3.connect(str(source), isolation_level=None)
        try:
            row = check.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise MemoryAuditStoreCorruption(
                    f"memory_audit_restore_source_corrupt:{row[0] if row else 'no-result'}"
                )
            migrations = {
                int(r[0]): r[1]
                for r in check.execute(
                    "SELECT version, sql_digest FROM schema_migrations"
                ).fetchall()
            }
            for version, (_, digest) in _MIGRATIONS.items():
                if migrations.get(version) != digest:
                    raise MemoryAuditStoreCorruption(
                        "memory_audit_restore_schema_digest_mismatch"
                    )
            for payload, d in check.execute(
                "SELECT payload, row_digest FROM audit_entries"
            ).fetchall():
                if _row_digest(payload) != d:
                    raise MemoryAuditStoreCorruption(
                        "memory_audit_restore_row_digest_mismatch"
                    )
            raw_rows = check.execute(
                "SELECT payload FROM audit_entries ORDER BY sequence ASC"
            ).fetchall()
            try:
                seeded = MemoryAccessAuditTrail(
                    tuple(MemoryAccessAuditEntry(**json.loads(p)) for (p,) in raw_rows)
                )
            except (ValueError, MemoryAccessAuditChainBroken) as exc:
                raise MemoryAuditStoreCorruption(
                    f"memory_audit_restore_chain_broken:{exc}"
                ) from exc
            counts = {"entries": len(seeded.entries)}
        except sqlite3.DatabaseError as exc:
            raise MemoryAuditStoreCorruption(
                f"memory_audit_restore_source_unreadable:{exc}"
            ) from exc
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
            rebuilt, broken = self._rebuild_trail(self._conn)
            if broken is not None or rebuilt is None:
                self._gate_closed_reason = broken or "memory_audit_chain_broken"
            return {"restored_counts": counts, "verified": True}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
