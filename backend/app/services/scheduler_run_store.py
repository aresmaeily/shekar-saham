"""Durable scheduler run-history store (WAVE-M, OA-4; 2026-11-06).

Additive module — nothing existing is modified. This is the IMMUTABLE
run-history backend for the internal research scheduler, built with the
same discipline as ``app.services.prediction_store`` (OA-5, WAVE-J):

- SQLite with ``PRAGMA journal_mode=WAL`` + ``synchronous=FULL`` +
  ``busy_timeout`` + pinned schema migrations (SQL-text digest, fail-closed
  mismatch),
- APPEND-ONLY: the ``scheduler_run_events`` table is the single source of
  truth. There is NO update or delete path — every state change appends a
  new event row. Derived per-run state is computed from the event stream
  (``derive_run_state``), never stored in place,
- Row integrity digests (SHA-256 over the canonical event payload); open()
  verifies every existing row and fails closed on any mismatch,
- Unique ``event_id`` with idempotent append semantics: a byte-identical
  re-append is a no-op returning ``(appended=False, duplicate_ok=True)``;
  conflicting re-use of an ``event_id`` is rejected,
- Crash/restart safety: a run found non-terminal at startup is closed with
  an explicit ``INTERRUPTED`` event by the scheduler's recovery step
  (never silently dropped, never auto-resumed),
- Backup/restore: plain-file copy of the SQLite database plus a full
  digest re-verification on restore (fail-closed on any mismatch).

Trust discipline: this store records WHAT HAPPENED inside one local
process's scheduler. It performs no I/O beyond its own database file, no
network, no egress, and it never reads settings.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import DATA_DIR

__all__ = [
    "SchedulerRunStoreError",
    "SchedulerRunStoreCorruption",
    "RUN_EVENT_TYPES",
    "TERMINAL_RUN_STATES",
    "derive_run_state",
    "DurableSchedulerRunStore",
    "MemorySchedulerRunStore",
    "get_scheduler_run_store",
    "reset_scheduler_run_store_cache",
]

DEFAULT_DB_NAME = "scheduler_runs.sqlite3"
SCHEMA_VERSION = 1


class SchedulerRunStoreError(Exception):
    """Base error for scheduler run-history stores."""


class SchedulerRunStoreCorruption(SchedulerRunStoreError):
    """Integrity failure — the store refuses to serve (fail-closed)."""


# Closed event-type set. Any value outside this set is rejected at append
# time — the history cannot be polluted with free-form labels.
RUN_EVENT_TYPES = frozenset(
    {
        "ENQUEUED",
        "STARTED",
        "SUCCEEDED",          # attempt succeeded → run COMPLETED (final)
        "FAILED_ATTEMPT",     # attempt failed; retry decision in payload
        "RETRY_QUEUED",
        "TIMED_OUT",          # attempt exceeded its budget (kill/cancel-safe)
        "CANCELLED",          # stop(drain=False) closed a queued run
        "KILLED",             # kill-switch closed the run
        "INTERRUPTED",        # restart recovery (crash/restart detection)
        "DEAD_LETTERED",      # attempts exhausted → bounded dead-letter state
        "COMPLETED",
        "KILL_ENGAGED",       # scheduler-level (run_id == "")
        "KILL_RELEASED",      # scheduler-level
        "PAUSED",             # scheduler-level
        "RESUMED",            # scheduler-level
        "STOPPED",            # scheduler-level
    }
)

#: Terminal per-run states (derived). Terminal runs never execute again;
#: only an INTERRUPTED recovery marker or nothing can follow them.
TERMINAL_RUN_STATES = frozenset(
    {"COMPLETED", "DEAD_LETTERED", "CANCELLED", "KILLED", "INTERRUPTED"}
)


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _row_digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_rollback(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


_MIGRATION_V1 = """
CREATE TABLE IF NOT EXISTS scheduler_run_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    at_utc TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL,
    row_digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sre_run ON scheduler_run_events(run_id, seq);
CREATE TABLE IF NOT EXISTS scheduler_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_MIGRATIONS: Dict[int, Tuple[str, str]] = {
    1: (
        _MIGRATION_V1,
        hashlib.sha256(_MIGRATION_V1.encode("utf-8")).hexdigest(),
    )
}


def derive_run_state(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive the honest current state of one run from its event stream.

    Pure function — no I/O. The last relevant event wins; events are
    ordered by ``seq`` (append order), not by wall-clock timestamps.
    """
    state = "UNKNOWN"
    attempts = 0
    last_error: Optional[str] = None
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    retry_queued = 0
    outcome_digest: Optional[str] = None
    for ev in events:
        et = ev.get("event_type")
        at = ev.get("at_utc")
        payload = ev.get("payload") or {}
        if et == "ENQUEUED":
            state, enqueued_at = "QUEUED", at
        elif et == "STARTED":
            state, started_at = "RUNNING", at
        elif et == "SUCCEEDED":
            state = "COMPLETED"
            finished_at = at
            outcome_digest = payload.get("outcome_digest")
            attempts = max(attempts, int(payload.get("attempt", attempts)))
        elif et == "FAILED_ATTEMPT":
            attempts = max(attempts, int(payload.get("attempt", attempts + 1)))
            last_error = payload.get("error")
            state = "RUNNING"
        elif et == "RETRY_QUEUED":
            retry_queued += 1
            state = "QUEUED"
        elif et == "TIMED_OUT":
            attempts = max(attempts, int(payload.get("attempt", attempts + 1)))
            last_error = payload.get("error", "run_timeout")
            state = "RUNNING"
        elif et == "CANCELLED":
            state, finished_at = "CANCELLED", at
        elif et == "KILLED":
            state, finished_at = "KILLED", at
        elif et == "INTERRUPTED":
            state, finished_at = "INTERRUPTED", at
        elif et == "DEAD_LETTERED":
            state, finished_at = "DEAD_LETTERED", at
        elif et == "COMPLETED":
            state, finished_at = "COMPLETED", at
            attempts = max(attempts, int(payload.get("attempts", attempts)))
    return {
        "state": state,
        "attempts": attempts,
        "retry_queued": retry_queued,
        "last_error": last_error,
        "enqueued_at_utc": enqueued_at,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "outcome_digest": outcome_digest,
        "terminal": state in TERMINAL_RUN_STATES,
    }


class _RunStoreBase:
    """Shared semantics for both backends (durable + memory test adapter)."""

    persistence_durable = False
    backend_label = "abstract"

    def append_event(
        self,
        *,
        event_id: str,
        run_id: str,
        event_type: str,
        at_utc: str,
        actor: str,
        payload: Dict[str, Any],
    ) -> Tuple[bool, bool]:
        raise NotImplementedError

    def events_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def all_events(self, limit: int) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def runs_index(self, limit: int) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def verify_all_rows(self) -> int:
        raise NotImplementedError

    def backup(self, target_dir: Path | str, keep: int = 5) -> Path:
        raise NotImplementedError

    def restore_from(self, backup_path: Path | str) -> int:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class DurableSchedulerRunStore(_RunStoreBase):
    """SQLite/WAL append-only scheduler run-history store (OA-4)."""

    persistence_durable = True
    backend_label = "sqlite-wal"

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection = self._open()
        self.persistence_note = (
            "تاریخچه اجرای زمان‌بند ماندگار است (SQLite/WAL، ضمیمه-فقط، "
            f"هش صحت سطر): {self._db_path}"
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
            row = conn.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                conn.close()
                raise SchedulerRunStoreCorruption(
                    f"integrity_check_failed:{row[0] if row else 'no-result'}"
                )
        except sqlite3.DatabaseError as exc:
            raise SchedulerRunStoreCorruption(f"open_failed:{exc}") from exc
        self._migrate(conn)
        self._verify_conn_rows(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS scheduler_migrations ("
            "version INTEGER PRIMARY KEY,"
            "sql_digest TEXT NOT NULL)"
        )
        applied = {
            int(r[0]): r[1]
            for r in conn.execute(
                "SELECT version, sql_digest FROM scheduler_migrations"
            ).fetchall()
        }
        for version in sorted(_MIGRATIONS):
            sql, digest = _MIGRATIONS[version]
            if version in applied:
                if applied[version] != digest:
                    raise SchedulerRunStoreCorruption("schema_digest_mismatch")
                continue
            statements = [st.strip() for st in sql.split(";") if st.strip()]
            try:
                conn.execute("BEGIN IMMEDIATE")
                for statement in statements:
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO scheduler_migrations(version, sql_digest) "
                    "VALUES (?, ?)",
                    (version, digest),
                )
                conn.execute("COMMIT")
            except sqlite3.Error:
                _safe_rollback(conn)
                raise SchedulerRunStoreCorruption(f"migration_failed:v{version}")

    def _verify_conn_rows(self, conn: sqlite3.Connection) -> None:
        for payload, digest in conn.execute(
            "SELECT payload, row_digest FROM scheduler_run_events"
        ).fetchall():
            if _row_digest(payload) != digest:
                raise SchedulerRunStoreCorruption("row_digest_mismatch:scheduler_run_events")

    # ------------------------------------------------------------- internals
    @staticmethod
    def _decode(payload: str) -> Dict[str, Any]:
        return json.loads(payload)

    @staticmethod
    def _row_to_event(row: Tuple[Any, ...]) -> Dict[str, Any]:
        _seq, event_id, run_id, event_type, at_utc, actor, payload, _digest = row
        return {
            "event_id": event_id,
            "run_id": run_id,
            "event_type": event_type,
            "at_utc": at_utc,
            "actor": actor,
            "payload": json.loads(payload),
        }

    # ---------------------------------------------------------------- public
    def append_event(
        self,
        *,
        event_id: str,
        run_id: str,
        event_type: str,
        at_utc: str,
        actor: str,
        payload: Dict[str, Any],
    ) -> Tuple[bool, bool]:
        """Append one event. Returns (appended, duplicate_ok).

        Byte-identical re-append (same event_id AND same canonical payload
        AND same metadata) is an idempotent no-op. Conflicting re-use of an
        event_id (different content) is rejected — history cannot be
        rewritten under a known id.
        """
        if event_type not in RUN_EVENT_TYPES:
            raise SchedulerRunStoreError(f"unknown_event_type:{event_type}")
        body = {
            "event_id": event_id,
            "run_id": run_id,
            "event_type": event_type,
            "at_utc": at_utc,
            "actor": actor,
            "payload": payload,
        }
        canonical = _canonical(body)
        digest = _row_digest(canonical)
        with self._lock:
            existing = self._conn.execute(
                "SELECT payload, row_digest FROM scheduler_run_events "
                "WHERE event_id=?",
                (event_id,),
            ).fetchone()
            if existing is not None:
                if existing[1] == digest:
                    return (False, True)
                raise SchedulerRunStoreError("event_id_conflict")
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    "INSERT INTO scheduler_run_events("
                    "event_id, run_id, event_type, at_utc, actor, payload, "
                    "row_digest) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        event_id,
                        run_id,
                        event_type,
                        at_utc,
                        actor,
                        canonical,
                        digest,
                    ),
                )
                self._conn.execute("COMMIT")
            except sqlite3.Error as exc:
                _safe_rollback(self._conn)
                raise SchedulerRunStoreError(f"append_failed:{exc}") from exc
            return (True, False)

    def events_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, event_id, run_id, event_type, at_utc, actor, "
                "payload, row_digest FROM scheduler_run_events "
                "WHERE run_id=? ORDER BY seq ASC",
                (run_id,),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def all_events(self, limit: int) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 2000))
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, event_id, run_id, event_type, at_utc, actor, "
                "payload, row_digest FROM scheduler_run_events "
                "ORDER BY seq DESC LIMIT ?",
                (bounded,),
            ).fetchall()
        return [self._row_to_event(r) for r in reversed(rows)]

    def runs_index(self, limit: int) -> List[Dict[str, Any]]:
        """One derived-state entry per REAL run, newest run first (bounded).

        Scheduler-level events (PAUSED/RESUMED/STOPPED/KILL_*) carry the
        sentinel run_id ``""`` — they are lifecycle records, not runs, and
        are excluded here so no phantom pseudo-run can appear in the index
        or in restart recovery.
        """
        with self._lock:
            run_ids = [
                r[0]
                for r in self._conn.execute(
                    "SELECT DISTINCT run_id FROM scheduler_run_events "
                    "WHERE run_id != '' ORDER BY seq DESC"
                ).fetchall()
            ]
        bounded = max(1, min(int(limit), 200))
        out: List[Dict[str, Any]] = []
        for run_id in run_ids[:bounded]:
            events = self.events_for_run(run_id)
            derived = derive_run_state(events)
            derived["run_id"] = run_id
            job_type = None
            for ev in events:
                if ev["event_type"] == "ENQUEUED":
                    job_type = (ev.get("payload") or {}).get("job_type")
                    break
            derived["job_type"] = job_type
            out.append(derived)
        return out

    def find_run_by_idempotency_key(self, key: str) -> Optional[str]:
        """Exact-match scan for the ENQUEUED event carrying this key.

        Bounded tables make the scan honest and cheap; the match is exact
        on the canonical JSON field, never a LIKE approximation.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload, run_id FROM scheduler_run_events "
                "WHERE event_type='ENQUEUED' ORDER BY seq ASC"
            ).fetchall()
        for payload, run_id in rows:
            body = json.loads(payload)
            inner = body.get("payload") or {}
            if inner.get("idempotency_key") == key:
                return run_id
        return None

    def verify_all_rows(self) -> int:
        with self._lock:
            self._verify_conn_rows(self._conn)
            return int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM scheduler_run_events"
                ).fetchone()[0]
            )

    def backup(self, target_dir: Path | str, keep: int = 5) -> Path:
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        stamp = self._db_path.stem
        # Timestamped filename: keep=N actually retains N distinct backups.
        dest = target / f"{stamp}_backup_{int(time.time())}.sqlite3"
        with self._lock:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            shutil.copy2(self._db_path, dest)
        # rotate (lexicographic order == chronological for this stamp)
        backups = sorted(target.glob(f"{stamp}_backup_*.sqlite3"))
        for old in backups[:-keep] if keep > 0 else []:
            try:
                old.unlink()
            except OSError:
                pass
        return dest

    def restore_from(self, backup_path: Path | str) -> int:
        """Replace the live database with a verified backup (fail-closed).

        The backup is first opened standalone and every row digest is
        re-verified; only then is the live file replaced and reopened.
        """
        src = Path(backup_path)
        if not src.is_file():
            raise SchedulerRunStoreError("backup_file_missing")
        try:
            probe = sqlite3.connect(str(src))
            probe.execute("PRAGMA journal_mode=WAL")
            row = probe.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                probe.close()
                raise SchedulerRunStoreCorruption("backup_integrity_failed")
            probe.close()
        except sqlite3.DatabaseError as exc:
            raise SchedulerRunStoreCorruption(f"backup_open_failed:{exc}") from exc
        tmp_probe = DurableSchedulerRunStore.__new__(DurableSchedulerRunStore)
        tmp_probe._db_path = src
        tmp_probe._lock = threading.RLock()
        conn = tmp_probe._open()
        count = int(
            conn.execute("SELECT COUNT(*) FROM scheduler_run_events").fetchone()[0]
        )
        conn.close()
        with self._lock:
            self._conn.close()
            shutil.copy2(src, self._db_path)
            for suffix in ("-wal", "-shm"):
                side = Path(str(self._db_path) + suffix)
                if side.exists():
                    side.unlink()
            self._conn = self._open()
        return count

    @property
    def db_path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass


class MemorySchedulerRunStore(_RunStoreBase):
    """Process-local adapter for UNIT TESTS ONLY — never a default.

    Same append-only/idempotency semantics as the durable store; content
    vanishes with the process, which is exactly why the real application
    path must use the durable implementation (OA-4/OA-5 contract style).
    """

    persistence_durable = False
    backend_label = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: List[Dict[str, Any]] = []
        self._seq = 0

    def append_event(
        self,
        *,
        event_id: str,
        run_id: str,
        event_type: str,
        at_utc: str,
        actor: str,
        payload: Dict[str, Any],
    ) -> Tuple[bool, bool]:
        if event_type not in RUN_EVENT_TYPES:
            raise SchedulerRunStoreError(f"unknown_event_type:{event_type}")
        body = {
            "event_id": event_id,
            "run_id": run_id,
            "event_type": event_type,
            "at_utc": at_utc,
            "actor": actor,
            "payload": payload,
        }
        canonical = _canonical(body)
        digest = _row_digest(canonical)
        with self._lock:
            for ev in self._events:
                if ev["event_id"] == event_id:
                    if ev["_digest"] == digest:
                        return (False, True)
                    raise SchedulerRunStoreError("event_id_conflict")
            self._seq += 1
            self._events.append({**body, "_seq": self._seq, "_digest": digest})
        return (True, False)

    @staticmethod
    def _view(ev: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_id": ev["event_id"],
            "run_id": ev["run_id"],
            "event_type": ev["event_type"],
            "at_utc": ev["at_utc"],
            "actor": ev["actor"],
            "payload": ev["payload"],
        }

    def events_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = [e for e in self._events if e["run_id"] == run_id]
        return [self._view(e) for e in sorted(rows, key=lambda e: e["_seq"])]

    def all_events(self, limit: int) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 2000))
        with self._lock:
            rows = sorted(self._events, key=lambda e: e["_seq"])
        return [self._view(e) for e in rows[-bounded:]]

    def runs_index(self, limit: int) -> List[Dict[str, Any]]:
        with self._lock:
            ordered = sorted(self._events, key=lambda e: e["_seq"])
            run_ids: List[str] = []
            for e in reversed(ordered):
                if e["run_id"] and e["run_id"] not in run_ids:
                    run_ids.append(e["run_id"])
        bounded = max(1, min(int(limit), 200))
        out: List[Dict[str, Any]] = []
        for run_id in run_ids[:bounded]:
            events = self.events_for_run(run_id)
            derived = derive_run_state(events)
            derived["run_id"] = run_id
            job_type = None
            for ev in events:
                if ev["event_type"] == "ENQUEUED":
                    job_type = (ev.get("payload") or {}).get("job_type")
                    break
            derived["job_type"] = job_type
            out.append(derived)
        return out

    def find_run_by_idempotency_key(self, key: str) -> Optional[str]:
        with self._lock:
            for e in self._events:
                if (
                    e["event_type"] == "ENQUEUED"
                    and e["payload"].get("idempotency_key") == key
                ):
                    return e["run_id"]
        return None

    def verify_all_rows(self) -> int:
        with self._lock:
            for e in self._events:
                body = {
                    k: e[k]
                    for k in ("event_id", "run_id", "event_type", "at_utc", "actor", "payload")
                }
                if _row_digest(_canonical(body)) != e["_digest"]:
                    raise SchedulerRunStoreCorruption("row_digest_mismatch:memory")
            return len(self._events)

    def backup(self, target_dir: Path | str, keep: int = 5) -> Path:
        raise SchedulerRunStoreError("backup_not_supported_on_memory_backend")

    def restore_from(self, backup_path: Path | str) -> int:
        raise SchedulerRunStoreError("restore_not_supported_on_memory_backend")

    def close(self) -> None:
        with self._lock:
            self._events.clear()


_STORES: Dict[Tuple[str, str], Any] = {}
_STORES_LOCK = threading.Lock()


def get_scheduler_run_store() -> Any:
    """Settings-driven store factory (cached per backend+path).

    Default backend is the DURABLE SQLite store (OA-4/OA-5 contract style:
    the real application path must be durable). The memory adapter is an
    explicit unit-test choice via SCHEDULER_STORE_BACKEND=memory.
    """
    from app.core.config import get_settings

    settings = get_settings()
    backend = (getattr(settings, "scheduler_store_backend", "") or "sqlite").strip().lower()
    if backend == "memory":
        key = ("memory", "")
        store_cls: Any = MemorySchedulerRunStore
        path = ""
    elif backend == "sqlite":
        raw = (getattr(settings, "scheduler_db_path", "") or "").strip()
        if raw:
            path = str(Path(raw).resolve())
        else:
            path = str((DATA_DIR / DEFAULT_DB_NAME).resolve())
        key = ("sqlite", path)
        store_cls = DurableSchedulerRunStore
    else:
        raise SchedulerRunStoreError(f"unknown_scheduler_store_backend:{backend}")
    with _STORES_LOCK:
        store = _STORES.get(key)
        if store is None:
            store = store_cls(path) if backend == "sqlite" else store_cls()
            _STORES[key] = store
        return store


def reset_scheduler_run_store_cache() -> None:
    """Test hook: drop cached store instances (env changes take effect)."""
    with _STORES_LOCK:
        for store in _STORES.values():
            try:
                store.close()
            except Exception:
                pass
        _STORES.clear()
