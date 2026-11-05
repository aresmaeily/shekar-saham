"""test_prediction_store_sqlite.py — MASTER-RADAR WAVE-J (2026-11-05)

OA-5 (owner directive 2026-11-05): durable prediction registry.

Acceptance coverage (directive WAVE-J list, mapped):
- process restart preserves registered predictions and matured outcomes;
- concurrent duplicate writes produce ONE valid record (idempotent);
- a second outcome is rejected;
- an outcome before registration is rejected (look-ahead);
- immature predictions cannot be evaluated (label-leakage guard);
- corrupted database fails closed and is recoverable from a verified backup;
- migration from the process-local adapter invents NO historical records;
- existing deterministic calibration results are unchanged (exact Brier/ECE
  pins flow through the durable backend via the API test below);
- retention policy: append-only, no silent deletion, purge owner-gated.

The suite exercises the REAL SQLite/WAL store (the application default),
never just the memory adapter.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domain.prediction import OutcomeRecord, PredictionRecord, PredictionRegistry
from app.main import app
from app.services.prediction_store import (
    RETENTION_POLICY,
    DurablePredictionStore,
    MemoryPredictionStore,
    PredictionStoreCorruption,
    get_prediction_store,
    reset_prediction_store_cache,
)

client = TestClient(app, client=("mr-wavej-predstore", 12421))

PREFIX = "/api/v10/productloops"

REG_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
PRE_REG_T = datetime(2025, 12, 15, tzinfo=timezone.utc)  # BEFORE registration
HORIZON_T = datetime(2026, 2, 1, tzinfo=timezone.utc)
AFTER_T = datetime(2026, 2, 3, tzinfo=timezone.utc)
BEFORE_T = datetime(2026, 1, 15, tzinfo=timezone.utc)


def _record(pid: str, notes: str = "") -> PredictionRecord:
    return PredictionRecord(
        prediction_id=pid,
        subject="SYNTHETIC:فملی",
        registered_at_utc=REG_T,
        outcome_horizon_end_utc=HORIZON_T,
        evaluation_metric="DIRECTION_HIT",
        event_maturity_rule="horizon_end",
        invalidation_rule="subject_removed",
        evidence_ids=("DECLARED-PREDICTION-EVIDENCE",),
        creator="wave-j-tests",
        notes=notes,
    )


def _outcome(oid: str, pid: str, observed_at=AFTER_T, numeric: float = 1.0) -> OutcomeRecord:
    return OutcomeRecord(
        outcome_id=oid,
        prediction_id=pid,
        observed_at_utc=observed_at,
        observed_numeric=numeric,
        source_evidence_ids=("DECLARED-OUTCOME-EVIDENCE",),
    )


# ---------------------------------------------------------------------------
# restart recovery
# ---------------------------------------------------------------------------


def test_restart_preserves_predictions_outcomes_and_evaluations(tmp_path: Path) -> None:
    db = tmp_path / "reg.sqlite3"
    store1 = DurablePredictionStore(db)
    store1.register_prediction(_record("P-RS-1"))
    store1.attach_outcome(_outcome("OUT-RS-1", "P-RS-1"))
    evaluation, version1 = store1.evaluate("P-RS-1", as_of=AFTER_T, matched_expectation=True)
    v_after = store1.registry_version
    store1.close()

    store2 = DurablePredictionStore(db)  # simulate process restart
    assert store2.counts() == {"predictions": 1, "outcomes": 1, "evaluations": 1}
    assert store2.get_prediction("P-RS-1") == _record("P-RS-1")
    assert store2.get_outcome("P-RS-1") == _outcome("OUT-RS-1", "P-RS-1")
    assert store2.registry_version == v_after
    # identical re-evaluation after restart: idempotent, no version bump
    evaluation2, version2 = store2.evaluate("P-RS-1", as_of=AFTER_T, matched_expectation=True)
    assert evaluation2 == evaluation
    assert version2 == v_after
    store2.close()


# ---------------------------------------------------------------------------
# idempotency / duplicates / guards
# ---------------------------------------------------------------------------


def test_identical_duplicate_registration_is_idempotent(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    first = store.register_prediction(_record("P-IDEM-1"))
    second = store.register_prediction(_record("P-IDEM-1"))
    assert first["duplicate_of_existing"] is False
    assert second["duplicate_of_existing"] is True
    assert first["registry_version"] == second["registry_version"]
    assert store.counts()["predictions"] == 1


def test_conflicting_duplicate_registration_refused(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    store.register_prediction(_record("P-CONF-1"))
    with pytest.raises(ValueError, match="duplicate_prediction_id"):
        store.register_prediction(_record("P-CONF-1", notes="different-payload"))
    assert store.counts()["predictions"] == 1


def test_concurrent_duplicate_writes_produce_one_record(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    record = _record("P-RACE-1")
    results: list = []
    errors: list = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        try:
            barrier.wait()
            results.append(store.register_prediction(record))
        except ValueError as exc:
            errors.append(str(exc))
        except BaseException as exc:  # diagnostic: never silently swallow
            errors.append(f"UNCAUGHT:{type(exc).__name__}:{exc}")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.counts()["predictions"] == 1
    # every call either appended exactly once or was translated to the typed
    # duplicate refusal — never a corrupt second row, never a 5xx-class error
    assert all(
        str(exc) == "duplicate_prediction_id" for exc in errors
    ), errors
    successes = [r for r in results if r["duplicate_of_existing"] is False]
    idempotent = [r for r in results if r["duplicate_of_existing"] is True]
    # total outcomes across all racers: one real append + idempotent no-ops
    # + typed refusals — exactly 8, with AT MOST one real insert
    assert len(successes) + len(idempotent) + len(errors) == 8
    assert len(successes) <= 1
    # registry_version advanced exactly once for the single real append
    assert store.registry_version == 2


def test_second_outcome_refused(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    store.register_prediction(_record("P-OUT-1"))
    store.attach_outcome(_outcome("OUT-1", "P-OUT-1"))
    with pytest.raises(ValueError, match="prediction_already_has_outcome"):
        store.attach_outcome(_outcome("OUT-2", "P-OUT-1", numeric=0.0))
    assert store.counts()["outcomes"] == 1


def test_outcome_predating_registration_refused(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    store.register_prediction(_record("P-PRE-1"))
    with pytest.raises(ValueError, match="outcome_predates_prediction_registration"):
        store.attach_outcome(
            _outcome("OUT-PRE", "P-PRE-1", observed_at=PRE_REG_T)
        )
    assert store.counts()["outcomes"] == 0


def test_outcome_for_unknown_prediction_refused(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    with pytest.raises(ValueError, match="unknown_prediction_id"):
        store.attach_outcome(_outcome("OUT-GHOST", "P-GHOST"))
    # outcome_id uniqueness across predictions is also enforced
    store.register_prediction(_record("P-A-1"))
    store.register_prediction(_record("P-B-1"))
    store.attach_outcome(_outcome("OUT-SHARED", "P-A-1"))
    with pytest.raises(ValueError, match="duplicate_outcome_id_conflict"):
        store.attach_outcome(_outcome("OUT-SHARED", "P-B-1"))


def test_immature_evaluation_refused_and_evaluation_needs_outcome(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    store.register_prediction(_record("P-MAT-1"))
    with pytest.raises(ValueError, match="prediction_not_matured"):
        store.evaluate("P-MAT-1", as_of=BEFORE_T, matched_expectation=True)
    store.attach_outcome(_outcome("OUT-MAT", "P-MAT-1"))
    evaluation, version = store.evaluate("P-MAT-1", as_of=AFTER_T, matched_expectation=False)
    assert evaluation.outcome_id == "OUT-MAT"
    assert evaluation.matched_expectation is False
    assert version == store.registry_version
    # conflicting rewrite refused — history is never rewritten
    with pytest.raises(ValueError, match="prediction_already_evaluated"):
        store.evaluate("P-MAT-1", as_of=AFTER_T, matched_expectation=True)


# ---------------------------------------------------------------------------
# corruption fail-closed + verified backup/restore
# ---------------------------------------------------------------------------


def test_corruption_fails_closed_and_backup_restores(tmp_path: Path) -> None:
    db = tmp_path / "reg.sqlite3"
    store = DurablePredictionStore(db)
    store.register_prediction(_record("P-BK-1"))
    store.attach_outcome(_outcome("OUT-BK", "P-BK-1"))
    backup = store.backup(tmp_path / "reg.bak.sqlite3")
    assert backup["verified"] is True and backup["byte_size"] > 0
    store.close()

    # external tampering with a stored payload must be DETECTED
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE predictions SET payload='tampered'")
    conn.commit()
    conn.close()
    with pytest.raises(PredictionStoreCorruption, match="row_digest_mismatch"):
        DurablePredictionStore(db)

    # recovery path: discard the corrupt file (operator step, verified backup
    # exists), reopen, verified-restore — records come back byte-identical
    db.unlink()
    recovered = DurablePredictionStore(db)
    restored = recovered.restore(tmp_path / "reg.bak.sqlite3")
    assert restored["verified"] is True
    assert restored["restored_counts"] == {"predictions": 1, "outcomes": 1, "evaluations": 0}
    assert recovered.get_prediction("P-BK-1") == _record("P-BK-1")
    assert recovered.get_outcome("P-BK-1") == _outcome("OUT-BK", "P-BK-1")
    recovered.close()


def test_restore_refuses_unverified_or_missing_source(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    with pytest.raises(PredictionStoreCorruption, match="restore_source_missing"):
        store.restore(tmp_path / "missing.sqlite3")
    # a garbage file must be refused as a restore source
    bad = tmp_path / "bad.sqlite3"
    bad.write_bytes(b"not a database at all")
    with pytest.raises(PredictionStoreCorruption):
        store.restore(bad)
    store.close()


# ---------------------------------------------------------------------------
# migration from the process-local adapter (no invented history)
# ---------------------------------------------------------------------------


def test_migration_from_value_object_invents_nothing(tmp_path: Path) -> None:
    registry = PredictionRegistry()
    registry = registry.register_prediction(_record("P-MIG-1"))
    registry = registry.register_prediction(_record("P-MIG-2", notes="second"))
    registry = registry.attach_outcome(_outcome("OUT-MIG", "P-MIG-1"))

    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    result = store.migrate_from_registry(registry)
    assert result["no_invention"] is True and result["parity_verified"] is True
    assert result["predictions"] == 2 and result["outcomes"] == 1
    rebuilt = store.snapshot_registry()
    assert rebuilt.predictions == registry.predictions
    assert rebuilt.outcomes == registry.outcomes
    assert store.counts() == {"predictions": 2, "outcomes": 1, "evaluations": 0}
    # re-migration is idempotent (no duplicates invented on retry)
    again = store.migrate_from_registry(registry)
    assert again["predictions"] == 0 and again["outcomes"] == 0
    assert store.counts() == {"predictions": 2, "outcomes": 1, "evaluations": 0}
    store.close()


# ---------------------------------------------------------------------------
# export / retention
# ---------------------------------------------------------------------------


def test_export_jsonl_and_retention_policy(tmp_path: Path) -> None:
    store = DurablePredictionStore(tmp_path / "reg.sqlite3")
    store.register_prediction(_record("P-EX-1"))
    store.attach_outcome(_outcome("OUT-EX", "P-EX-1"))
    lines = [json.loads(line) for line in store.export_jsonl().splitlines()]
    tables = {line["table"] for line in lines}
    assert tables == {"predictions", "outcomes"}
    for line in lines:
        from app.services.prediction_store import _row_digest

        assert _row_digest(json.dumps(line["record"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))) == line["row_digest"]
    # retention: append-only, no silent deletion, purge owner-gated
    assert RETENTION_POLICY == "APPEND_ONLY_NO_SILENT_DELETION__PURGE_IS_OWNER_GATED"
    assert not hasattr(store, "delete_prediction")
    assert not hasattr(store, "purge")
    assert not hasattr(store, "delete_outcome")
    store.close()


# ---------------------------------------------------------------------------
# factory: durable is the DEFAULT application backend
# ---------------------------------------------------------------------------


def test_factory_default_is_durable_sqlite(tmp_path: Path, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("PREDICTION_DB_PATH", str(tmp_path / "reg.sqlite3"))
    get_settings.cache_clear()
    try:
        store = get_prediction_store()
        assert isinstance(store, DurablePredictionStore)
        assert store.backend_label == "sqlite-wal"
        assert store.persistence_durable is True
    finally:
        get_settings.cache_clear()
        reset_prediction_store_cache()


def test_memory_adapter_is_explicit_unit_test_choice(tmp_path: Path, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("PREDICTION_STORE_BACKEND", "memory")
    get_settings.cache_clear()
    try:
        store = get_prediction_store()
        assert isinstance(store, MemoryPredictionStore)
        assert store.backend_label == "memory-adapter"
        memory_note = store.persistence_note
        assert "غیرماندگار" in memory_note  # honesty: memory adapter discloses non-durability
    finally:
        get_settings.cache_clear()
        reset_prediction_store_cache()


def test_factory_refuses_unknown_backend(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.services.prediction_store import PredictionStoreError

    monkeypatch.setenv("PREDICTION_STORE_BACKEND", "redis")
    get_settings.cache_clear()
    try:
        with pytest.raises(PredictionStoreError, match="unknown_prediction_store_backend"):
            get_prediction_store()
    finally:
        get_settings.cache_clear()
        reset_prediction_store_cache()


# ---------------------------------------------------------------------------
# API wiring: the REAL application path uses the durable backend
# ---------------------------------------------------------------------------


def test_api_predictions_use_durable_backend_and_calibration_unchanged(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "reg.sqlite3"
    monkeypatch.setenv("PREDICTION_DB_PATH", str(db))
    reset_prediction_store_cache()
    try:
        res = client.post(
            f"{PREFIX}/predictions/register",
            json={
                "prediction_id": "P-API-1",
                "subject": "SYNTHETIC:فملی",
                "registered_at_utc": "2026-01-01T00:00:00Z",
                "outcome_horizon_end_utc": "2026-02-01T00:00:00Z",
                "evaluation_metric": "DIRECTION_HIT",
                "event_maturity_rule": "horizon_end",
                "invalidation_rule": "subject_removed",
                "evidence_ids": ["DECLARED-PREDICTION-EVIDENCE"],
                "creator": "wave-j-api",
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["persistence_backend"] == "sqlite-wal"
        assert body["persistence_durable"] is True
        assert body["retention_policy"] == RETENTION_POLICY

        res = client.post(
            f"{PREFIX}/predictions/P-API-1/outcome",
            json={
                "outcome_id": "OUT-API-1",
                "observed_at_utc": "2026-02-02T00:00:00Z",
                "observed_numeric": 1.0,
                "source_evidence_ids": ["DECLARED-OUTCOME-EVIDENCE"],
            },
        )
        assert res.status_code == 200

        # the durable file actually holds the rows (independent read)
        check = sqlite3.connect(str(db))
        rows = check.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        outs = check.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
        check.close()
        assert (rows, outs) == (1, 1)

        # calibration over the durable rows: exact pinned values unchanged
        res = client.post(
            f"{PREFIX}/predictions/calibration",
            params={"measured_at_utc": "2026-02-03T00:00:00Z"},
            json={"pairs": [{"prediction_id": "P-API-1", "predicted_probability": 0.9, "observed": 1.0}]},
        )
        assert res.status_code == 200, res.text
        calibration = res.json()["calibration"]
        assert calibration["brier_score"] == pytest.approx(0.01)
        assert calibration["expected_calibration_error"] == pytest.approx(0.1)
    finally:
        reset_prediction_store_cache()


def test_api_duplicate_conflict_and_second_outcome_via_http() -> None:
    res = client.post(
        f"{PREFIX}/predictions/register",
        json={
            "prediction_id": "P-HTTP-1",
            "subject": "S",
            "registered_at_utc": "2026-01-01T00:00:00Z",
            "outcome_horizon_end_utc": "2026-02-01T00:00:00Z",
            "evaluation_metric": "M",
            "event_maturity_rule": "r",
            "invalidation_rule": "i",
            "evidence_ids": ["E"],
            "creator": "t",
        },
    )
    assert res.status_code == 200
    res = client.post(
        f"{PREFIX}/predictions/register",
        json={
            "prediction_id": "P-HTTP-1",
            "subject": "S-different",
            "registered_at_utc": "2026-01-01T00:00:00Z",
            "outcome_horizon_end_utc": "2026-02-01T00:00:00Z",
            "evaluation_metric": "M",
            "event_maturity_rule": "r",
            "invalidation_rule": "i",
            "evidence_ids": ["E"],
            "creator": "t",
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "duplicate_prediction_id"
    res = client.post(
        f"{PREFIX}/predictions/P-HTTP-1/outcome",
        json={
            "outcome_id": "OUT-HTTP-1",
            "observed_at_utc": "2026-02-02T00:00:00Z",
            "source_evidence_ids": ["E"],
        },
    )
    assert res.status_code == 200
    res = client.post(
        f"{PREFIX}/predictions/P-HTTP-1/outcome",
        json={
            "outcome_id": "OUT-HTTP-2",
            "observed_at_utc": "2026-02-03T00:00:00Z",
            "source_evidence_ids": ["E"],
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "prediction_already_has_outcome"
    # pre-maturity evaluation still refused over the durable backend
    res = client.post(
        f"{PREFIX}/predictions/P-HTTP-1/evaluate",
        params={"as_of_utc": "2026-01-15T00:00:00Z"},
        json={"matched_expectation": True},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "prediction_not_matured"
