"""D-AI-30 additive storage: outbox / inbox / dead-letter / counters / kill
switches / audit (CONSOL-GOV-41 decision 3/5/6/7).

Migration contract (decision 3 + 10):
- ADDITIVE ONLY: ``migrate()`` uses ``CREATE TABLE IF NOT EXISTS`` on new,
  namespaced ``alert_ops_*`` tables. No existing table is altered or dropped.
- REVERSIBLE: ``rollback()`` renames the alert-ops tables to
  ``*_rollback_archive`` — queued and historical records are PRESERVED (owner
  decision 10), never destroyed. ``restore_from_archive()`` reverses it.
- No destructive database migration anywhere in this module.

All timestamps are ISO-8601 UTC strings; all SQL is parameterized; no
credential, token, or sensitive user content is ever written (decision 7) —
alert JSON lives only in the internal outbox/inbox/dead-letter tables, audit
details carry references and codes only.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import DATA_DIR
from app.domain.alert_operations import SYNTHETIC_PAPER_LABEL

DB_PATH = DATA_DIR / "shekar.db"

_lock = threading.RLock()

_ALERT_OPS_TABLES: tuple[str, ...] = (
    "alert_ops_outbox",
    "alert_ops_inbox",
    "alert_ops_dead_letter",
    "alert_ops_budget_counters",
    "alert_ops_kill_switches",
    "alert_ops_job_state",
    "alert_ops_audit",
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS alert_ops_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT NOT NULL,
    dedup_window TEXT NOT NULL,
    alert_json TEXT NOT NULL,
    alert_kind TEXT NOT NULL,
    subject TEXT NOT NULL,
    binding_id TEXT NOT NULL,
    source_event_id TEXT,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_error_code TEXT,
    label TEXT NOT NULL,
    channel TEXT NOT NULL,
    UNIQUE(dedup_key, dedup_window)
);
CREATE INDEX IF NOT EXISTS idx_alert_ops_outbox_status_next ON alert_ops_outbox(status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_alert_ops_outbox_kind ON alert_ops_outbox(alert_kind);

CREATE TABLE IF NOT EXISTS alert_ops_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outbox_id INTEGER NOT NULL UNIQUE,
    dedup_key TEXT NOT NULL,
    alert_kind TEXT NOT NULL,
    subject TEXT NOT NULL,
    summary TEXT NOT NULL,
    label TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    expires_at TEXT,
    alert_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_ops_inbox_delivered ON alert_ops_inbox(delivered_at);

CREATE TABLE IF NOT EXISTS alert_ops_dead_letter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outbox_id INTEGER NOT NULL UNIQUE,
    dedup_key TEXT NOT NULL,
    alert_json TEXT NOT NULL,
    alert_kind TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    last_error_code TEXT,
    reason TEXT NOT NULL,
    dead_lettered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_ops_budget_counters (
    scope TEXT NOT NULL,
    window_start TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(scope, window_start)
);

CREATE TABLE IF NOT EXISTS alert_ops_kill_switches (
    scope TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_ops_job_state (
    job_id TEXT PRIMARY KEY,
    last_run_at TEXT,
    last_success_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    failure_state TEXT NOT NULL DEFAULT 'HEALTHY',
    last_error_code TEXT
);

CREATE TABLE IF NOT EXISTS alert_ops_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    category TEXT NOT NULL,
    ref TEXT NOT NULL,
    detail_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_ops_audit_ts ON alert_ops_audit(ts);
"""


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class AlertOpsStore:
    """Owns the additive alert-ops tables inside the shared SQLite database."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with _lock:
            conn = sqlite3.connect(str(self.path), timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # --- migration / rollback -------------------------------------------------
    def migrate(self) -> None:
        """Idempotent additive migration (safe to call on every startup)."""
        with self._conn() as c:
            c.executescript(_SCHEMA_SQL)
            # Fail-closed defaults (decision 5): the GLOBAL dispatch switch and
            # the two approved jobs' per-job switches are seeded ENGAGED —
            # explicit rows, so a defined job can never be denied as "missing"
            # while still defaulting fail-closed. Any other job id has no row
            # and is denied as missing (fail-closed for unapproved jobs).
            now_iso = _iso(datetime.now(timezone.utc))
            for scope in ("GLOBAL", "OA-ALERT-OPS-DISPATCHER", "OA-ALERT-OPS-FRESHNESS-30MIN"):
                c.execute(
                    "INSERT OR IGNORE INTO alert_ops_kill_switches(scope, state, updated_at, updated_by) VALUES(?,?,?,?)",
                    (scope, "ENGAGED", now_iso, "schema-default"),
                )

    def rollback(self) -> dict[str, int]:
        """Reversible rollback: archive (rename) every alert-ops table.

        Records are preserved in ``*_rollback_archive`` tables (decision 10);
        nothing is dropped. Existing product tables are never touched.
        """
        counts: dict[str, int] = {}
        with self._conn() as c:
            for table in _ALERT_OPS_TABLES:
                row = c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if row is None:
                    continue
                counts[table] = int(
                    c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                c.execute(f"DROP TABLE IF EXISTS {table}_rollback_archive")
                c.execute(f"ALTER TABLE {table} RENAME TO {table}_rollback_archive")
        return counts

    def restore_from_archive(self) -> None:
        """Reverse of ``rollback()``: archived tables become live again."""
        with self._conn() as c:
            for table in _ALERT_OPS_TABLES:
                row = c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (f"{table}_rollback_archive",)
                ).fetchone()
                if row is None:
                    continue
                c.execute(f"DROP TABLE IF EXISTS {table}")
                c.execute(f"ALTER TABLE {table}_rollback_archive RENAME TO {table}")

    def table_names(self) -> set[str]:
        with self._conn() as c:
            rows = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {r["name"] for r in rows}

    # --- outbox ----------------------------------------------------------------
    def enqueue(
        self,
        *,
        dedup_key: str,
        dedup_window: str,
        alert: Any,
        alert_json: str,
        source_event_id: str | None,
        fingerprint: str,
        now: datetime,
    ) -> int | None:
        """Insert a queued alert; returns the row id, or None when the
        (dedup_key, window) pair already exists (durable idempotency)."""
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO alert_ops_outbox
                    (dedup_key, dedup_window, alert_json, alert_kind, subject, binding_id,
                     source_event_id, fingerprint, status, attempts, next_attempt_at,
                     created_at, updated_at, label, channel)
                VALUES(?,?,?,?,?,?,?,?,'QUEUED',0,?,?,?,?,'IN_PRODUCT_INBOX')
                """,
                (
                    dedup_key,
                    dedup_window,
                    alert_json,
                    alert.alert_kind,
                    alert.subject,
                    _binding_of(alert),
                    source_event_id,
                    fingerprint,
                    _iso(now),
                    _iso(now),
                    _iso(now),
                    SYNTHETIC_PAPER_LABEL,
                ),
            )
            return int(cur.lastrowid) if cur.lastrowid is not None else None

    def find_outbox_by_key(self, dedup_key: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM alert_ops_outbox WHERE dedup_key=? ORDER BY id DESC LIMIT 1", (dedup_key,)
            ).fetchone()
        return dict(row) if row else None

    def due_outbox_rows(self, now: datetime, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT * FROM alert_ops_outbox
                WHERE status='QUEUED' AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                ORDER BY id LIMIT ?
                """,
                (_iso(now), limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def outbox_row(self, outbox_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM alert_ops_outbox WHERE id=?", (outbox_id,)).fetchone()
        return dict(row) if row else None

    def update_outbox(
        self,
        outbox_id: int,
        *,
        status: str,
        attempts: int,
        next_attempt_at: datetime | None,
        last_error_code: str | None,
        now: datetime,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                UPDATE alert_ops_outbox
                SET status=?, attempts=?, next_attempt_at=?, last_error_code=?, updated_at=?
                WHERE id=?
                """,
                (status, attempts, None if next_attempt_at is None else _iso(next_attempt_at), last_error_code, _iso(now), outbox_id),
            )

    def queue_depth(self) -> int:
        with self._conn() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM alert_ops_outbox WHERE status='QUEUED'").fetchone()
        return int(row["n"])

    def outbox_counts_by_status(self) -> dict[str, int]:
        with self._conn() as c:
            rows = c.execute("SELECT status, COUNT(*) AS n FROM alert_ops_outbox GROUP BY status").fetchall()
        return {r["status"]: int(r["n"]) for r in rows}

    # --- inbox -------------------------------------------------------------------
    def deliver_to_inbox(
        self,
        *,
        outbox_id: int,
        dedup_key: str,
        alert: Any,
        alert_json: str,
        summary: str,
        now: datetime,
    ) -> int:
        from app.domain.alert_operations import SYNTHETIC_PAPER_LABEL

        expires = getattr(alert, "expiry_utc", None)
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO alert_ops_inbox
                    (outbox_id, dedup_key, alert_kind, subject, summary, label, delivered_at, expires_at, alert_json)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    outbox_id,
                    dedup_key,
                    alert.alert_kind,
                    alert.subject,
                    summary,
                    SYNTHETIC_PAPER_LABEL,
                    _iso(now),
                    None if expires is None else _iso(expires),
                    alert_json,
                ),
            )
            return int(cur.lastrowid) if cur.lastrowid is not None else 0

    def inbox_rows(self, limit: int = 50, kind: str | None = None) -> list[dict[str, Any]]:
        """Product-visible rows: minimum-necessary fields ONLY (decision 7).

        ``alert_json`` / evidence ids are deliberately NOT selected here —
        they stay internal references in the database.
        """
        q = "SELECT id, outbox_id, alert_kind, subject, summary, label, delivered_at, expires_at FROM alert_ops_inbox"
        params: list[Any] = []
        if kind:
            q += " WHERE alert_kind=?"
            params.append(kind)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def inbox_count(self) -> int:
        with self._conn() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM alert_ops_inbox").fetchone()
        return int(row["n"])

    # --- dead letter ---------------------------------------------------------------
    def dead_letter(
        self,
        *,
        outbox_id: int,
        dedup_key: str,
        alert_json: str,
        alert_kind: str,
        attempts: int,
        last_error_code: str | None,
        reason: str,
        now: datetime,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO alert_ops_dead_letter
                    (outbox_id, dedup_key, alert_json, alert_kind, attempts, last_error_code, reason, dead_lettered_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (outbox_id, dedup_key, alert_json, alert_kind, attempts, last_error_code, reason, _iso(now)),
            )
            return int(cur.lastrowid) if cur.lastrowid is not None else 0

    def dead_letter_count(self) -> int:
        with self._conn() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM alert_ops_dead_letter").fetchone()
        return int(row["n"])

    def dead_letter_rows(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, outbox_id, alert_kind, attempts, last_error_code, reason, dead_lettered_at"
                " FROM alert_ops_dead_letter ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- budget counters -------------------------------------------------------------
    def counter_value(self, scope: str, window_start: datetime) -> int:
        with self._conn() as c:
            row = c.execute(
                "SELECT count FROM alert_ops_budget_counters WHERE scope=? AND window_start=?",
                (scope, _iso(window_start)),
            ).fetchone()
        return int(row["count"]) if row else 0

    def increment_counter(self, scope: str, window_start: datetime, by: int = 1) -> int:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO alert_ops_budget_counters(scope, window_start, count) VALUES(?,?,?)
                ON CONFLICT(scope, window_start) DO UPDATE SET count = count + excluded.count
                """,
                (scope, _iso(window_start), by),
            )
            row = c.execute(
                "SELECT count FROM alert_ops_budget_counters WHERE scope=? AND window_start=?",
                (scope, _iso(window_start)),
            ).fetchone()
        return int(row["count"])

    def prune_counters(self, now: datetime, keep: timedelta = timedelta(hours=2)) -> None:
        cutoff = _iso(now - keep)
        with self._conn() as c:
            c.execute("DELETE FROM alert_ops_budget_counters WHERE window_start < ?", (cutoff,))

    # --- kill switches ------------------------------------------------------------------
    def kill_switch_state(self, scope: str) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT state FROM alert_ops_kill_switches WHERE scope=?", (scope,)).fetchone()
        return row["state"] if row else None

    def set_kill_switch(self, scope: str, state: str, now: datetime, updated_by: str) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO alert_ops_kill_switches(scope, state, updated_at, updated_by) VALUES(?,?,?,?)
                ON CONFLICT(scope) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at, updated_by=excluded.updated_by
                """,
                (scope, state, _iso(now), updated_by),
            )

    def kill_switch_rows(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT scope, state, updated_at, updated_by FROM alert_ops_kill_switches ORDER BY scope").fetchall()
        return [dict(r) for r in rows]

    # --- job state ---------------------------------------------------------------------
    def job_state(self, job_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM alert_ops_job_state WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def upsert_job_state(
        self,
        job_id: str,
        *,
        last_run_at: datetime | None = None,
        last_success_at: datetime | None = None,
        consecutive_failures: int | None = None,
        failure_state: str | None = None,
        last_error_code: str | None = None,
    ) -> None:
        current = self.job_state(job_id) or {}
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO alert_ops_job_state(job_id, last_run_at, last_success_at, consecutive_failures, failure_state, last_error_code)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET
                    last_run_at=excluded.last_run_at,
                    last_success_at=COALESCE(excluded.last_success_at, alert_ops_job_state.last_success_at),
                    consecutive_failures=COALESCE(excluded.consecutive_failures, alert_ops_job_state.consecutive_failures),
                    failure_state=COALESCE(excluded.failure_state, alert_ops_job_state.failure_state),
                    last_error_code=COALESCE(excluded.last_error_code, alert_ops_job_state.last_error_code)
                """,
                (
                    job_id,
                    _iso(last_run_at) if last_run_at else current.get("last_run_at"),
                    _iso(last_success_at) if last_success_at else None,
                    consecutive_failures if consecutive_failures is not None else int(current.get("consecutive_failures") or 0),
                    failure_state or current.get("failure_state") or "HEALTHY",
                    last_error_code,
                ),
            )

    def all_job_states(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM alert_ops_job_state ORDER BY job_id").fetchall()
        return [dict(r) for r in rows]

    # --- audit --------------------------------------------------------------------------
    def audit(self, category: str, ref: str, detail: dict[str, Any], now: datetime) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO alert_ops_audit(ts, category, ref, detail_json) VALUES(?,?,?,?)",
                (_iso(now), category, ref, json.dumps(detail, sort_keys=True, separators=(",", ":"), ensure_ascii=False)),
            )
            return int(cur.lastrowid) if cur.lastrowid is not None else 0

    def audit_rows(self, limit: int = 50, category: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT id, ts, category, ref, detail_json FROM alert_ops_audit"
        params: list[Any] = []
        if category:
            q += " WHERE category=?"
            params.append(category)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def audit_count(self, category: str | None = None) -> int:
        q = "SELECT COUNT(*) AS n FROM alert_ops_audit"
        params: list[Any] = []
        if category:
            q += " WHERE category=?"
            params.append(category)
        with self._conn() as c:
            row = c.execute(q, params).fetchone()
        return int(row["n"])

    # --- retention (decision 7) ----------------------------------------------------------
    def purge_expired_records(self, now: datetime, retention_days: int) -> dict[str, int]:
        cutoff = _iso(now - timedelta(days=retention_days))
        purged: dict[str, int] = {}
        with self._conn() as c:
            for table, col in (
                ("alert_ops_outbox", "created_at"),
                ("alert_ops_inbox", "delivered_at"),
                ("alert_ops_dead_letter", "dead_lettered_at"),
                ("alert_ops_audit", "ts"),
            ):
                cur = c.execute(f"DELETE FROM {table} WHERE {col} < ?", (cutoff,))
                purged[table] = int(cur.rowcount or 0)
        return purged


def _binding_of(alert: Any) -> str:
    from app.domain.alert_operations import binding_id

    return binding_id(alert)
