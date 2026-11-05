"""Durable prediction registry store (OA-5, owner directive 2026-11-05).

WAVE-J scope: the L5 prediction-feedback registry becomes DURABLE. The
process-local :class:`app.domain.prediction.PredictionRegistry` value object
stays the deterministic contract layer and remains available as a unit-test
adapter (``MemoryPredictionStore``); the REAL application path
(``/api/v10/productloops/predictions*``) now uses ``DurablePredictionStore``:
SQLite with WAL, transactional append-only writes, pinned schema migrations,
row digests for tamper evidence, verified backup/restore, and restart
recovery.

Hard rules carried over from the domain contract (never weakened):
- append-only: predictions/outcomes/evaluations are INSERT-only; there is no
  UPDATE/DELETE path anywhere in this module and no purge API (purge stays
  owner-gated per the standing R-register);
- duplicate prediction ids: identical canonical payload = idempotent no-op,
  different payload = refused (``duplicate_prediction_id``);
- one outcome per prediction (``prediction_already_has_outcome``);
- an outcome may not predate its prediction's registration
  (``outcome_predates_prediction_registration`` — look-ahead/label-leakage);
- evaluation before maturity is refused (``prediction_not_matured``) and the
  evaluation instant is ALWAYS caller-supplied (no wall clock anywhere);
- a recorded evaluation is append-only too: identical re-evaluation is an
  idempotent no-op, a conflicting rewrite is refused
  (``prediction_already_evaluated``).

Operational discipline:
- ``PRAGMA journal_mode=WAL`` + ``synchronous=FULL`` + ``busy_timeout`` +
  ``foreign_keys=ON``; writes run under ``BEGIN IMMEDIATE`` inside a process
  lock; UNIQUE constraints are the cross-thread/process hard guarantee —
  a lost race is translated to the same typed refusal (or idempotent
  success when the byte-identical record already exists).
- integrity: ``PRAGMA integrity_check`` + per-row SHA-256 verification at
  open and restore time; any mismatch fails closed
  (:class:`PredictionStoreCorruption`) and is recoverable ONLY from a
  verified backup produced by :meth:`DurablePredictionStore.backup`.
- migrations: versioned DDL with pinned SQL digests; an applied digest that
  no longer matches fails closed (``schema_digest_mismatch``).
- clock-free: no wall-clock read in this module; operational timestamps are
  not recorded (the domain contract records caller instants only).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import DATA_DIR, get_settings
from app.domain.prediction import (
    OutcomeRecord,
    PredictionEvaluation,
    PredictionRecord,
    PredictionRegistry,
    maturity_state,
)

SCHEMA_VERSION = "PREDICTION-STORE-V1"
RETENTION_POLICY = "APPEND_ONLY_NO_SILENT_DELETION__PURGE_IS_OWNER_GATED"

MEMORY_NOTE = (
    "ریجستری فرایند-محلی و غیرماندگار است؛ پایداری دائمی نیازمند تصمیم مالک است"
)


class PredictionStoreError(Exception):
    """Typed store failure (reason string carried on ``reason``)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PredictionStoreCorruption(PredictionStoreError):
    """Fail-closed corruption detection (integrity/digest/schema mismatch)."""


def _canonical_payload(model_dump: Dict[str, Any]) -> str:
    return json.dumps(
        model_dump, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _row_digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_rollback(conn: sqlite3.Connection) -> None:
    """ROLLBACK that never masks the original failure (no active tx = ok)."""
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


_MIGRATION_V1 = """
CREATE TABLE IF NOT EXISTS predictions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    row_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    outcome_id TEXT NOT NULL UNIQUE,
    prediction_id TEXT NOT NULL UNIQUE REFERENCES predictions(prediction_id),
    payload TEXT NOT NULL,
    row_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT NOT NULL UNIQUE REFERENCES predictions(prediction_id),
    payload TEXT NOT NULL,
    row_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS registry_meta (
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


class DurablePredictionStore:
    """SQLite/WAL append-only prediction/outcome/evaluation store."""

    backend_label = "sqlite-wal"
    persistence_durable = True

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection = self._open()
        self.persistence_note = (
            f"ریجستری پیش‌بینی ماندگار است (SQLite/WAL، ضمیمه-فقط، هش صحت سطر): "
            f"{self._db_path}؛ پاک‌سازی/حذف مالک-گیت است"
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
                raise PredictionStoreCorruption(
                    f"integrity_check_failed:{row[0] if row else 'no-result'}"
                )
        except sqlite3.DatabaseError as exc:
            raise PredictionStoreCorruption(f"open_failed:{exc}") from exc
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
                    raise PredictionStoreCorruption("schema_digest_mismatch")
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
        for table in ("predictions", "outcomes", "evaluations"):
            for payload, digest in conn.execute(
                f"SELECT payload, row_digest FROM {table}"  # noqa: S608 (pinned table)
            ).fetchall():
                if _row_digest(payload) != digest:
                    raise PredictionStoreCorruption(
                        f"row_digest_mismatch:{table}"
                    )

    # ------------------------------------------------------------- internals
    @property
    def registry_version(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM registry_meta WHERE key='registry_version'"
            ).fetchone()
            return int(row[0]) if row else 1

    def _bump_version_locked(self, conn: sqlite3.Connection) -> int:
        next_version = self.registry_version + 1
        conn.execute(
            "INSERT INTO registry_meta(key, value) VALUES ('registry_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(next_version),),
        )
        return next_version

    def _get_prediction_row(
        self, conn: sqlite3.Connection, prediction_id: str
    ) -> Optional[Tuple[str, str]]:
        return conn.execute(
            "SELECT payload, row_digest FROM predictions WHERE prediction_id=?",
            (prediction_id,),
        ).fetchone()

    @staticmethod
    def _decode_prediction(payload: str) -> PredictionRecord:
        return PredictionRecord.model_validate_json(payload)

    @staticmethod
    def _decode_outcome(payload: str) -> OutcomeRecord:
        return OutcomeRecord.model_validate_json(payload)

    # ---------------------------------------------------------------- public
    def get_prediction(self, prediction_id: str) -> Optional[PredictionRecord]:
        with self._lock:
            row = self._get_prediction_row(self._conn, prediction_id)
            return None if row is None else self._decode_prediction(row[0])

    def get_outcome(self, prediction_id: str) -> Optional[OutcomeRecord]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM outcomes WHERE prediction_id=?",
                (prediction_id,),
            ).fetchone()
            return None if row is None else self._decode_outcome(row[0])

    def register_prediction(
        self, record: PredictionRecord, *, payload: Optional[str] = None
    ) -> Dict[str, Any]:
        payload = payload or _canonical_payload(record.model_dump(mode="json"))
        digest = _row_digest(payload)
        with self._lock:
            existing = self._get_prediction_row(self._conn, record.prediction_id)
            if existing is not None:
                if existing[1] == digest:
                    return {
                        "registry_version": self.registry_version,
                        "duplicate_of_existing": True,
                    }
                raise ValueError("duplicate_prediction_id")
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._get_prediction_row(self._conn, record.prediction_id)
                if row is not None:
                    # lost a race: translate to the same typed semantics
                    _safe_rollback(self._conn)
                    if row[1] == digest:
                        return {
                            "registry_version": self.registry_version,
                            "duplicate_of_existing": True,
                        }
                    raise ValueError("duplicate_prediction_id")
                self._conn.execute(
                    "INSERT INTO predictions(prediction_id, payload, row_digest) "
                    "VALUES (?, ?, ?)",
                    (record.prediction_id, payload, digest),
                )
                version = self._bump_version_locked(self._conn)
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                _safe_rollback(self._conn)
                raise ValueError("duplicate_prediction_id") from exc
            return {"registry_version": version, "duplicate_of_existing": False}

    def attach_outcome(
        self, outcome: OutcomeRecord, *, payload: Optional[str] = None
    ) -> Dict[str, Any]:
        payload = payload or _canonical_payload(outcome.model_dump(mode="json"))
        digest = _row_digest(payload)
        with self._lock:
            prow = self._get_prediction_row(self._conn, outcome.prediction_id)
            if prow is None:
                raise ValueError("unknown_prediction_id")
            prediction = self._decode_prediction(prow[0])
            if outcome.observed_at_utc < prediction.registered_at_utc:
                raise ValueError("outcome_predates_prediction_registration")
            existing = self._conn.execute(
                "SELECT payload FROM outcomes WHERE prediction_id=?",
                (outcome.prediction_id,),
            ).fetchone()
            if existing is not None:
                raise ValueError("prediction_already_has_outcome")
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                dup = self._conn.execute(
                    "SELECT prediction_id FROM outcomes WHERE outcome_id=?",
                    (outcome.outcome_id,),
                ).fetchone()
                if dup is not None:
                    _safe_rollback(self._conn)
                    raise ValueError("duplicate_outcome_id_conflict")
                still = self._conn.execute(
                    "SELECT prediction_id FROM outcomes WHERE prediction_id=?",
                    (outcome.prediction_id,),
                ).fetchone()
                if still is not None:
                    _safe_rollback(self._conn)
                    raise ValueError("prediction_already_has_outcome")
                self._conn.execute(
                    "INSERT INTO outcomes(outcome_id, prediction_id, payload, row_digest) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        outcome.outcome_id,
                        outcome.prediction_id,
                        payload,
                        digest,
                    ),
                )
                version = self._bump_version_locked(self._conn)
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                _safe_rollback(self._conn)
                raise ValueError("prediction_already_has_outcome") from exc
            return {"registry_version": version}

    def evaluate(
        self,
        prediction_id: str,
        *,
        as_of,
        matched_expectation: bool,
        error_category: Optional[str] = None,
        calibration_note: Optional[str] = None,
        research_proposal_ref: Optional[str] = None,
        notes: str = "",
    ) -> Tuple[PredictionEvaluation, int]:
        """Evaluate a MATURED prediction and durably record the evaluation.

        The evaluation instant is the caller-supplied ``as_of`` (never a wall
        clock). Re-evaluating with identical semantic content is an
        idempotent no-op; a conflicting rewrite is refused
        (``prediction_already_evaluated``) — history is never rewritten.
        """
        with self._lock:
            prow = self._get_prediction_row(self._conn, prediction_id)
            if prow is None:
                raise ValueError("unknown_prediction_id")
            record = self._decode_prediction(prow[0])
            if maturity_state(record, as_of) != "MATURED":
                raise ValueError("prediction_not_matured")
            outcome = self.get_outcome(prediction_id)
            if outcome is None:
                raise ValueError("outcome_not_recorded")
            evaluation = PredictionEvaluation(
                prediction_id=prediction_id,
                outcome_id=outcome.outcome_id,
                evaluated_at_utc=as_of,
                matched_expectation=matched_expectation,
                error_category=error_category,
                calibration_note=calibration_note,
                research_proposal_ref=research_proposal_ref,
                notes=notes,
            )
            payload = _canonical_payload(evaluation.model_dump(mode="json"))
            digest = _row_digest(payload)
            existing = self._conn.execute(
                "SELECT payload, row_digest FROM evaluations WHERE prediction_id=?",
                (prediction_id,),
            ).fetchone()
            if existing is not None:
                if existing[1] == digest:
                    return evaluation, self.registry_version
                raise ValueError("prediction_already_evaluated")
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                dup = self._conn.execute(
                    "SELECT prediction_id FROM evaluations WHERE prediction_id=?",
                    (prediction_id,),
                ).fetchone()
                if dup is not None:
                    _safe_rollback(self._conn)
                    raise ValueError("prediction_already_evaluated")
                self._conn.execute(
                    "INSERT INTO evaluations(prediction_id, payload, row_digest) "
                    "VALUES (?, ?, ?)",
                    (prediction_id, payload, digest),
                )
                version = self._bump_version_locked(self._conn)
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                _safe_rollback(self._conn)
                raise ValueError("prediction_already_evaluated") from exc
            return evaluation, version

    def list_rows(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows: List[Dict[str, Any]] = []
            for payload, in self._conn.execute(
                "SELECT payload FROM predictions ORDER BY seq ASC"
            ).fetchall():
                record = self._decode_prediction(payload)
                outcome_row = self._conn.execute(
                    "SELECT payload FROM outcomes WHERE prediction_id=?",
                    (record.prediction_id,),
                ).fetchone()
                rows.append(
                    {
                        "prediction": record,
                        "outcome": (
                            self._decode_outcome(outcome_row[0])
                            if outcome_row
                            else None
                        ),
                    }
                )
            return rows

    def snapshot_registry(self) -> PredictionRegistry:
        """Rebuild the deterministic value object from durable rows.

        Used for calibration and for byte-identical migration parity tests —
        the rows are decoded verbatim, nothing is synthesized.
        """
        registry = PredictionRegistry()
        with self._lock:
            for payload, in self._conn.execute(
                "SELECT payload FROM predictions ORDER BY seq ASC"
            ).fetchall():
                registry = registry.register_prediction(
                    self._decode_prediction(payload)
                )
            for payload, in self._conn.execute(
                "SELECT payload FROM outcomes ORDER BY seq ASC"
            ).fetchall():
                registry = registry.attach_outcome(self._decode_outcome(payload))
        return registry

    def export_jsonl(self) -> str:
        """Canonical JSONL export (predictions, outcomes, evaluations)."""
        lines: List[str] = []
        with self._lock:
            for table in ("predictions", "outcomes", "evaluations"):
                for payload, digest in self._conn.execute(
                    f"SELECT payload, row_digest FROM {table} ORDER BY seq ASC"  # noqa: S608
                ).fetchall():
                    lines.append(
                        json.dumps(
                            {"table": table, "row_digest": digest, "record": json.loads(payload)},
                            sort_keys=True,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
        return "\n".join(lines) + ("\n" if lines else "")

    def migrate_from_registry(self, registry: PredictionRegistry) -> Dict[str, Any]:
        """Explicit migration from the process-local value object.

        OA-5 acceptance: migration must NOT invent historical records — every
        row is inserted verbatim through the same guarded append path, and
        the resulting durable snapshot must equal the input registry exactly
        (model equality on records and outcomes). No timestamps, digests, or
        ids are synthesized.
        """
        inserted_predictions = 0
        inserted_outcomes = 0
        for record in registry.predictions:
            result = self.register_prediction(record)
            if not result.get("duplicate_of_existing"):
                inserted_predictions += 1
        for outcome in registry.outcomes:
            existing = self.get_outcome(outcome.prediction_id)
            if existing == outcome:
                continue  # idempotent re-migration inserts nothing twice
            self.attach_outcome(outcome)
            inserted_outcomes += 1
        rebuilt = self.snapshot_registry()
        if rebuilt.predictions != registry.predictions or rebuilt.outcomes != registry.outcomes:
            raise PredictionStoreError("migration_parity_failed")
        return {
            "predictions": inserted_predictions,
            "outcomes": inserted_outcomes,
            "evaluations": 0,  # the value object carries no evaluation history
            "parity_verified": True,
            "no_invention": True,
        }

    def counts(self) -> Dict[str, int]:
        with self._lock:
            return {
                table: int(self._conn.execute(
                    f"SELECT COUNT(*) FROM {table}"  # noqa: S608
                ).fetchone()[0])
                for table in ("predictions", "outcomes", "evaluations")
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
                    raise PredictionStoreCorruption(
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
            raise PredictionStoreCorruption("restore_source_missing")
        check = sqlite3.connect(str(source), isolation_level=None)
        try:
            row = check.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise PredictionStoreCorruption(
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
                    raise PredictionStoreCorruption("restore_schema_digest_mismatch")
            for table in ("predictions", "outcomes", "evaluations"):
                for payload, d in check.execute(
                    f"SELECT payload, row_digest FROM {table}"  # noqa: S608
                ).fetchall():
                    if _row_digest(payload) != d:
                        raise PredictionStoreCorruption(
                            f"restore_row_digest_mismatch:{table}"
                        )
            counts = {
                table: int(check.execute(
                    f"SELECT COUNT(*) FROM {table}"  # noqa: S608
                ).fetchone()[0])
                for table in ("predictions", "outcomes", "evaluations")
            }
        except sqlite3.DatabaseError as exc:
            raise PredictionStoreCorruption(f"restore_source_unreadable:{exc}") from exc
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


class MemoryPredictionStore:
    """Process-local adapter over the domain value object (unit tests only).

    OA-5: the existing process-local registry may remain as an adapter for
    unit tests — it is NEVER the default application backend. Semantics and
    typed refusal reasons mirror the durable store exactly.
    """

    backend_label = "memory-adapter"
    persistence_durable = False

    def __init__(self) -> None:
        self._registry = PredictionRegistry()
        self.persistence_note = MEMORY_NOTE

    @property
    def registry_version(self) -> int:
        return self._registry.registry_version

    def get_prediction(self, prediction_id: str) -> Optional[PredictionRecord]:
        return self._registry.get_prediction(prediction_id)

    def get_outcome(self, prediction_id: str) -> Optional[OutcomeRecord]:
        return self._registry.get_outcome(prediction_id)

    def register_prediction(
        self, record: PredictionRecord, *, payload: Optional[str] = None
    ) -> Dict[str, Any]:
        existing = self._registry.get_prediction(record.prediction_id)
        if existing is not None:
            if existing == record:
                return {
                    "registry_version": self._registry.registry_version,
                    "duplicate_of_existing": True,
                }
            raise ValueError("duplicate_prediction_id")
        self._registry = self._registry.register_prediction(record)
        return {"registry_version": self._registry.registry_version}

    def attach_outcome(
        self, outcome: OutcomeRecord, *, payload: Optional[str] = None
    ) -> Dict[str, Any]:
        self._registry = self._registry.attach_outcome(outcome)
        return {"registry_version": self._registry.registry_version}

    def evaluate(
        self,
        prediction_id: str,
        *,
        as_of,
        matched_expectation: bool,
        error_category: Optional[str] = None,
        calibration_note: Optional[str] = None,
        research_proposal_ref: Optional[str] = None,
        notes: str = "",
    ) -> Tuple[PredictionEvaluation, int]:
        evaluation = self._registry.evaluate(
            prediction_id,
            as_of=as_of,
            matched_expectation=matched_expectation,
            error_category=error_category,
            calibration_note=calibration_note,
            research_proposal_ref=research_proposal_ref,
            notes=notes,
        )
        return evaluation, self._registry.registry_version

    def list_rows(self) -> List[Dict[str, Any]]:
        return [
            {
                "prediction": p,
                "outcome": self._registry.get_outcome(p.prediction_id),
            }
            for p in self._registry.predictions
        ]

    def snapshot_registry(self) -> PredictionRegistry:
        return self._registry

    def export_jsonl(self) -> str:
        lines = []
        for p in self._registry.predictions:
            lines.append(
                _canonical_payload(
                    {
                        "table": "predictions",
                        "record": p.model_dump(mode="json"),
                    }
                )
            )
        for o in self._registry.outcomes:
            lines.append(
                _canonical_payload(
                    {"table": "outcomes", "record": o.model_dump(mode="json")}
                )
            )
        return "\n".join(lines) + ("\n" if lines else "")

    def counts(self) -> Dict[str, int]:
        return {
            "predictions": len(self._registry.predictions),
            "outcomes": len(self._registry.outcomes),
            "evaluations": 0,
        }

    def close(self) -> None:  # pragma: no cover - nothing to release
        return


_STORES: Dict[Tuple[str, str], Any] = {}
_STORES_LOCK = threading.Lock()


def get_prediction_store() -> Any:
    """Settings-driven store factory (cached per resolved backend+path).

    Default backend is the DURABLE SQLite store (OA-5: the real application
    path must use the durable implementation); the memory adapter is an
    explicit unit-test choice via PREDICTION_STORE_BACKEND=memory.
    """
    settings = get_settings()
    backend = (settings.prediction_store_backend or "sqlite").strip().lower()
    if backend == "memory":
        key = ("memory", "")
        store_cls: Any = MemoryPredictionStore
        path = ""
    elif backend == "sqlite":
        raw = (settings.prediction_db_path or "").strip()
        if raw:
            path = str(Path(raw).resolve())
        else:
            # repo convention (config.py): DATA_DIR = ROOT/data
            path = str((DATA_DIR / "predictions_registry.sqlite3").resolve())
        key = ("sqlite", path)
        store_cls = DurablePredictionStore
    else:
        raise PredictionStoreError(f"unknown_prediction_store_backend:{backend}")
    with _STORES_LOCK:
        store = _STORES.get(key)
        if store is None:
            store = store_cls(path) if backend == "sqlite" else store_cls()
            _STORES[key] = store
        return store


def reset_prediction_store_cache() -> None:
    """Test hook: drop cached store instances (env changes take effect)."""
    with _STORES_LOCK:
        for store in _STORES.values():
            try:
                store.close()
            except Exception:  # pragma: no cover - close is best-effort
                pass
        _STORES.clear()
