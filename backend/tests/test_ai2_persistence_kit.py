"""WAVE-B (WP-B) battery for the DORMANT AI-2 persistence kit.

Module under test: ``app/data/ai2_ledger_sqlite.py``
(``DurableAI2LedgerStore`` — SQLite/WAL append-only prototype for the AI-2
run ledger + candidate registry, mirroring the ``prediction_store.py``
discipline) plus the owner decision packet
``docs/active/AI2_PERSISTENCE_DECISION_PACKET.md`` (D-A2-1…D-A2-7).

Acceptance coverage (WP-B work item 2, mapped to test names):

- adapter roundtrip: append N run records + M candidate payloads + duplicate
  keys, close, reopen, read back byte-identical (model equality for run
  records; canonical-JSON equality for candidate payloads); identical
  re-append is an idempotent no-op
  -> ``test_roundtrip_append_reopen_read_identical``.
- per-row digest tamper -> fail-closed reopen refusal naming the table, for
  both row tables -> ``test_row_digest_tamper_fail_closed_on_reopen``.
- verified backup + destructive restore drill with byte-identical read-back
  -> ``test_verified_backup_and_restore_drill``.
- restore refuses unverified/missing/corrupt/tampered/schema-mismatched
  sources -> ``test_restore_refuses_missing_source``,
  ``test_restore_refuses_corrupt_source``,
  ``test_restore_refuses_tampered_row_digest``,
  ``test_restore_refuses_schema_digest_mismatch``.
- persisted ``classify_duplicate`` key space: idempotent identical claim,
  conflicting claim refused, and the in-memory duplicate classifier reads the
  SAME labels off the stored records
  -> ``test_duplicate_key_persistence_and_classifier_labels``.
- dormancy pins: no ``app/services/*.py`` or ``app/api/*.py`` file imports
  the adapter (import-graph walk); the adapter reads no settings/env and
  exposes no update/delete/purge surface; the ``AI2_ENABLED`` default byte
  is untouched in config.py
  -> ``test_dormancy_no_runtime_importer``,
  ``test_adapter_surface_is_append_only_and_gate_free``.
- migration strategy documented: the packet exists and carries the
  D-A2-1…D-A2-7 headings, the no-activation statement, and the SQLite/WAL
  recommendation -> ``test_migration_strategy_documented``.

Honesty note: this kit activates NOTHING. The adapter has no runtime caller
by design; these tests are its only caller until the owner records the
D-A2 decisions.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.data import ai2_ledger_sqlite as ai2_ledger_sqlite_module
from app.data.ai2_ledger_sqlite import (
    RETENTION_POLICY,
    SCHEMA_VERSION,
    AI2LedgerCorruption,
    AI2LedgerStoreError,
    DurableAI2LedgerStore,
)
from app.domain.ai2_governance import AI2RunLedger, AI2RunRecord, classify_duplicate

UTC = timezone.utc
NOW_UTC = datetime(2026, 11, 9, 12, 0, 0, tzinfo=UTC)

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
PACKET_PATH = REPO_ROOT / "docs" / "active" / "AI2_PERSISTENCE_DECISION_PACKET.md"


# ---------------------------------------------------------------------------
# Deterministic factories (fixed instants, fixed hex snapshots; no RNG)
# ---------------------------------------------------------------------------
def _snapshot(i: int) -> str:
    return f"{i:064x}"


def _run_record(i: int) -> AI2RunRecord:
    return AI2RunRecord(
        record_id=f"rec-{i:04d}",
        run_id=f"genrun-{i:04d}",
        run_kind="AI2_GENERATION",
        policy_version="AI2-GEN-POLICY-1.0.0",
        task="strategy",
        input_snapshot_sha256=_snapshot(i),
        trust_state="synthetic",
        approval_state="PENDING",
        status="LEDGERED",
        recorded_at_utc=NOW_UTC,
        notes=f"kit-record-{i}",
    )


def _candidate_payload(i: int) -> dict:
    return {
        "candidate_id": f"gen-{i:04d}-deadbeef",
        "source": f"ENTRY close > {i}\nEXIT close < {i}\n",
        "status": "DRAFT",
        "data_label": "SYNTHETIC_OR_PAPER",
    }


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Roundtrip + idempotency
# ---------------------------------------------------------------------------
class TestAdapterRoundtrip:
    def test_roundtrip_append_reopen_read_identical(self, tmp_path) -> None:
        db = tmp_path / "ai2_ledger.sqlite3"
        records = [_run_record(i) for i in range(1, 4)]
        payloads = [_candidate_payload(i) for i in range(1, 3)]

        store = DurableAI2LedgerStore(db)
        assert store.backend_label == "sqlite-wal-dormant-prototype"
        for rec in records:
            result = store.append_run_record(rec)
            assert result["duplicate_of_existing"] is False
        for i, payload in enumerate(payloads, start=1):
            result = store.append_candidate_record(f"gen-{i:04d}-deadbeef", _canonical(payload))
            assert result["duplicate_of_existing"] is False
        store.record_duplicate_key("strategy", _snapshot(1), "rec-0001")
        store.record_duplicate_key("strategy", _snapshot(2), "rec-0002")
        assert store.counts() == {
            "ai2_run_records": 3,
            "ai2_candidate_records": 2,
            "ai2_duplicate_keys": 2,
        }

        # Byte-identical re-append is an idempotent no-op (nothing bumps).
        version_before = store.ledger_version
        again = store.append_run_record(records[0])
        assert again["duplicate_of_existing"] is True
        again_candidate = store.append_candidate_record(
            "gen-0001-deadbeef", _canonical(payloads[0])
        )
        assert again_candidate["duplicate_of_existing"] is True
        assert store.ledger_version == version_before
        assert store.counts()["ai2_run_records"] == 3

        # Conflicting re-use of a record id is refused (ledger semantics).
        conflicting = _run_record(1).model_copy(update={"notes": "rewritten"})
        with pytest.raises(AI2LedgerStoreError, match="ai2_ledger_record_conflict"):
            store.append_run_record(conflicting)
        with pytest.raises(AI2LedgerStoreError, match="ai2_candidate_record_conflict"):
            store.append_candidate_record("gen-0001-deadbeef", _canonical({"other": 1}))
        store.close()

        # Reopen: everything reads back byte-identical.
        reopened = DurableAI2LedgerStore(db)
        assert reopened.read_run_records() == tuple(records)
        assert reopened.read_candidate_payloads() == payloads
        assert reopened.read_duplicate_keys() == (
            {"task": "strategy", "input_snapshot_sha256": _snapshot(1), "record_id": "rec-0001"},
            {"task": "strategy", "input_snapshot_sha256": _snapshot(2), "record_id": "rec-0002"},
        )
        assert reopened.counts() == {
            "ai2_run_records": 3,
            "ai2_candidate_records": 2,
            "ai2_duplicate_keys": 2,
        }
        reopened.close()

    def test_row_digest_tamper_fail_closed_on_reopen(self, tmp_path) -> None:
        """Mutating a stored payload (or its digest) makes the store refuse
        to open: per-row SHA-256 verification fails closed at open time."""
        for tamper_column in ("payload", "row_digest"):
            db = tmp_path / f"ai2_ledger_{tamper_column}.sqlite3"
            store = DurableAI2LedgerStore(db)
            store.append_run_record(_run_record(1))
            store.close()

            conn = sqlite3.connect(str(db))
            try:
                if tamper_column == "payload":
                    conn.execute(
                        "UPDATE ai2_run_records SET payload=? WHERE record_id=?",
                        (_canonical({"tampered": True}), "rec-0001"),
                    )
                else:
                    conn.execute(
                        "UPDATE ai2_run_records SET row_digest=? WHERE record_id=?",
                        ("f" * 64, "rec-0001"),
                    )
                conn.commit()
            finally:
                conn.close()

            with pytest.raises(
                AI2LedgerCorruption, match="row_digest_mismatch:ai2_run_records"
            ):
                DurableAI2LedgerStore(db)

    def test_candidate_table_tamper_fail_closed_on_reopen(self, tmp_path) -> None:
        db = tmp_path / "ai2_ledger_cand.sqlite3"
        store = DurableAI2LedgerStore(db)
        store.append_candidate_record("gen-0001-deadbeef", _canonical(_candidate_payload(1)))
        store.close()
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                "UPDATE ai2_candidate_records SET payload=? WHERE candidate_id=?",
                (_canonical({"candidate_id": "gen-0001-deadbeef", "evil": True}), "gen-0001-deadbeef"),
            )
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(
            AI2LedgerCorruption, match="row_digest_mismatch:ai2_candidate_records"
        ):
            DurableAI2LedgerStore(db)


# ---------------------------------------------------------------------------
# Verified backup / restore-refuses-unverified
# ---------------------------------------------------------------------------
class TestBackupRestore:
    def test_verified_backup_and_restore_drill(self, tmp_path) -> None:
        source_db = tmp_path / "source.sqlite3"
        target_db = tmp_path / "target.sqlite3"
        backup_path = tmp_path / "backups" / "ai2_ledger.bak"
        records = [_run_record(i) for i in range(1, 4)]
        payloads = [_candidate_payload(i) for i in range(1, 3)]

        source = DurableAI2LedgerStore(source_db)
        for rec in records:
            source.append_run_record(rec)
        for i, payload in enumerate(payloads, start=1):
            source.append_candidate_record(f"gen-{i:04d}-deadbeef", _canonical(payload))

        backup = source.backup(backup_path)
        assert backup["verified"] is True
        assert len(backup["sha256"]) == 64
        assert backup["byte_size"] > 0

        # Destructive restore into the EMPTY target store, then re-verify.
        target = DurableAI2LedgerStore(target_db)
        assert target.counts()["ai2_run_records"] == 0
        result = target.restore(backup_path)
        assert result["verified"] is True
        assert result["restored_counts"] == {
            "ai2_run_records": 3,
            "ai2_candidate_records": 2,
            "ai2_duplicate_keys": 0,
        }
        assert target.read_run_records() == tuple(records)
        assert target.read_candidate_payloads() == payloads
        target.close()

        # A fresh process (new handle on the same path) sees the same rows.
        fresh = DurableAI2LedgerStore(target_db)
        assert fresh.read_run_records() == tuple(records)
        fresh.close()
        source.close()

    def test_restore_refuses_missing_source(self, tmp_path) -> None:
        store = DurableAI2LedgerStore(tmp_path / "live.sqlite3")
        with pytest.raises(AI2LedgerCorruption, match="restore_source_missing"):
            store.restore(tmp_path / "does-not-exist.bak")
        store.close()

    def test_restore_refuses_corrupt_source(self, tmp_path) -> None:
        store = DurableAI2LedgerStore(tmp_path / "live.sqlite3")
        garbage = tmp_path / "garbage.bak"
        garbage.write_bytes(b"this is not a sqlite database at all")
        with pytest.raises(AI2LedgerCorruption, match="restore_source_unreadable"):
            store.restore(garbage)
        store.close()

    def test_restore_refuses_tampered_row_digest(self, tmp_path) -> None:
        store = DurableAI2LedgerStore(tmp_path / "live.sqlite3")
        store.append_run_record(_run_record(1))
        tampered = tmp_path / "tampered.bak"
        backup = store.backup(tampered)
        assert backup["verified"] is True
        # Tamper AFTER the verified backup was taken: the backup on disk is
        # now unverified and restore must refuse it.
        conn = sqlite3.connect(str(tampered))
        try:
            conn.execute(
                "UPDATE ai2_run_records SET payload=? WHERE record_id=?",
                (_canonical({"tampered": True}), "rec-0001"),
            )
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(
            AI2LedgerCorruption, match="restore_row_digest_mismatch:ai2_run_records"
        ):
            store.restore(tampered)
        # The live store is untouched by the refused restore.
        assert store.counts()["ai2_run_records"] == 1
        store.close()

    def test_restore_refuses_schema_digest_mismatch(self, tmp_path) -> None:
        store = DurableAI2LedgerStore(tmp_path / "live.sqlite3")
        foreign = tmp_path / "foreign.bak"
        conn = sqlite3.connect(str(foreign))
        try:
            conn.execute(
                "CREATE TABLE schema_migrations ("
                "version INTEGER PRIMARY KEY,"
                "sql_digest TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT INTO schema_migrations(version, sql_digest) VALUES (1, ?)",
                ("deadbeef" * 8,),
            )
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(AI2LedgerCorruption, match="restore_schema_digest_mismatch"):
            store.restore(foreign)
        store.close()


# ---------------------------------------------------------------------------
# Duplicate-key persistence (D-A2-4) + classifier-label parity
# ---------------------------------------------------------------------------
class TestDuplicateKeyPersistence:
    def test_duplicate_key_persistence_and_classifier_labels(self, tmp_path) -> None:
        db = tmp_path / "ai2_ledger.sqlite3"
        store = DurableAI2LedgerStore(db)
        store.append_run_record(_run_record(1))
        store.append_run_record(_run_record(2))

        first = store.record_duplicate_key("strategy", _snapshot(1), "rec-0001")
        assert first["duplicate_of_existing"] is False
        replay = store.record_duplicate_key("strategy", _snapshot(1), "rec-0001")
        assert replay["duplicate_of_existing"] is True
        with pytest.raises(AI2LedgerStoreError, match="duplicate_key_conflict"):
            store.record_duplicate_key("strategy", _snapshot(1), "rec-0002")
        store.close()

        reopened = DurableAI2LedgerStore(db)
        assert reopened.read_duplicate_keys() == (
            {"task": "strategy", "input_snapshot_sha256": _snapshot(1), "record_id": "rec-0001"},
        )

        # The in-memory classifier reads the SAME labels off the stored
        # records — persistence changes nothing about classify_duplicate.
        ledger = AI2RunLedger(reopened.read_run_records())
        assert (
            classify_duplicate(ledger, task="strategy", input_snapshot_sha256=_snapshot(1))
            == "DUPLICATE_IDENTICAL"
        )
        assert (
            classify_duplicate(ledger, task="strategy", input_snapshot_sha256=_snapshot(99))
            == "DUPLICATE_REPEATED_QUESTION"
        )
        assert classify_duplicate(ledger, task="risk", input_snapshot_sha256=_snapshot(1)) == "NEW"
        reopened.close()


# ---------------------------------------------------------------------------
# Dormancy + gate pins (structural)
# ---------------------------------------------------------------------------
class TestDormancyPins:
    def test_dormancy_no_runtime_importer(self) -> None:
        """Import-graph dormancy: NO app/services/*.py or app/api/*.py file
        references the adapter. Only tests (this file) and the adapter's own
        battery may know it exists."""
        adapter_path = Path(ai2_ledger_sqlite_module.__file__).resolve()
        assert adapter_path.parent == BACKEND_DIR / "app" / "data"
        assert adapter_path.exists()

        needle = "ai2_ledger_sqlite"
        offenders: list[str] = []
        for directory in (BACKEND_DIR / "app" / "services", BACKEND_DIR / "app" / "api"):
            for py_file in sorted(directory.rglob("*.py")):
                if needle in py_file.read_text(encoding="utf-8"):
                    offenders.append(str(py_file))
        assert offenders == []

        # Layering: the adapter never imports the service layer either.
        adapter_source = adapter_path.read_text(encoding="utf-8")
        assert "from app.services" not in adapter_source
        assert "import app.services" not in adapter_source

        # The committed execution gate is byte-untouched (AI2_ENABLED default 0).
        config_source = (BACKEND_DIR / "app" / "core" / "config.py").read_text(encoding="utf-8")
        assert '_env_bool("AI2_ENABLED", "0")' in config_source

    def test_adapter_surface_is_append_only_and_gate_free(self) -> None:
        """Structural append-only: no update/delete/purge/drop path exists on
        the class surface; no settings/env reads; no DROP statements; the
        retention policy constant matches the repo's sanctioned wording."""
        forbidden_surface = {"update", "delete", "purge", "truncate", "drop"}
        assert not forbidden_surface.intersection(dir(DurableAI2LedgerStore))

        source = Path(ai2_ledger_sqlite_module.__file__).read_text(encoding="utf-8")
        # No gate/config wiring whatsoever: no settings import, no env reads,
        # no settings-cache access (the docstring may DOCUMENT the gate
        # independence — the code must not TOUCH it).
        assert "from app.core.config" not in source
        assert "import app.core.config" not in source
        assert "get_settings" not in source
        assert "os.environ" not in source
        assert "os.getenv" not in source
        assert "DROP TABLE" not in source.upper()
        assert "DELETE FROM" not in source.upper()
        # The dormancy/authority contract is documented in the module itself.
        assert "stays the EXECUTION gate" in source

        assert RETENTION_POLICY == "APPEND_ONLY_NO_SILENT_DELETION__PURGE_IS_OWNER_GATED"
        assert SCHEMA_VERSION == "AI2-LEDGER-STORE-V1"


# ---------------------------------------------------------------------------
# Migration strategy documented (the owner decision packet)
# ---------------------------------------------------------------------------
class TestMigrationStrategyDocumented:
    def test_migration_strategy_documented(self) -> None:
        assert PACKET_PATH.exists(), "the D-A2 decision packet must exist"
        text = PACKET_PATH.read_text(encoding="utf-8")
        for decision in range(1, 8):
            assert f"D-A2-{decision}" in text
        # The explicit no-activation scope statement is pinned, word for word.
        assert "NO production persistence is activated by this wave" in text
        # The recommendation mirrors the AI-3 recorded engine class and the
        # prediction-store discipline the prototype implements.
        assert "SQLite" in text and "WAL" in text
        assert "APPEND_ONLY_NO_SILENT_DELETION" in text
        assert "synchronous=FULL" in text
