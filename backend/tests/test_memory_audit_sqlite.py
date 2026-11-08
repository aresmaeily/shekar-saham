"""Durable memory ACCESS/OPERATION audit-trail store (2026-11-08 owner
directive §3 AI-3: «تکمیل audit trail پایدار» + real-cycle integration).

Mirrors the prediction-store adapter test discipline: restart recovery,
pinned-digest migrations, per-row digest tamper refusal, chain-tamper
closed gate, verified backup, fail-closed restore, typed refusals — and
the D3 rule that NO delete/update path exists in the module (AST-checked).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.data.memory_access_audit_sqlite import (
    DurableMemoryAccessAuditTrail,
    MemoryAuditStoreCorruption,
    MemoryAuditStoreError,
    SCHEMA_VERSION,
    _MIGRATIONS,
)
from app.domain.memory_access_audit import mint_audit_entry

T0 = datetime(2026, 11, 8, 10, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 11, 8, 10, 1, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 11, 8, 10, 2, 0, tzinfo=timezone.utc)


def _entry(seq: int, prior: str, at=T0, actor="runtime", op="EPISODIC_APPEND"):
    return mint_audit_entry(
        sequence=seq,
        actor=actor,
        authorization_context="L0-internal",
        operation=op,
        object_ref=f"entry-{seq}",
        at_utc=at,
        run_id=f"run-{seq}",
        prior_digest=prior,
    )


# ---------------------------------------------------------------------------
# Directive-item pins
# ---------------------------------------------------------------------------


def test_directive_item_pins_and_schema_version() -> None:
    assert SCHEMA_VERSION == "MEMORY-AUDIT-STORE-V1"
    sql, digest = _MIGRATIONS[1]
    assert digest == hashlib.sha256(sql.encode("utf-8")).hexdigest()
    assert "DROP TABLE" not in sql.upper()
    assert "DELETE FROM" not in sql.upper()
    assert "UPDATE " not in sql.upper()


def test_no_delete_or_update_statements_in_module_ast() -> None:
    import ast

    src = Path("app/data/memory_access_audit_sqlite.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            up = node.value.upper()
            assert "DELETE FROM" not in up, "D3 violation: delete path"
            assert not up.strip().startswith("UPDATE "), "D3 violation: update path"
            assert "DROP TABLE" not in up


# ---------------------------------------------------------------------------
# Append / restart recovery / chain semantics
# ---------------------------------------------------------------------------


def test_append_and_restart_recovery_preserves_chain(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite3"
    store = DurableMemoryAccessAuditTrail(db_path=db)
    r1 = store.record(
        actor="runtime",
        authorization_context="L0-internal",
        operation="EPISODIC_APPEND",
        object_ref="entry-1",
        at_utc=T0,
        run_id="run-1",
    )
    assert r1["sequence"] == 1 and r1["verified"] is True
    store.record(
        actor="runtime",
        authorization_context="L0-internal",
        operation="EPISODIC_APPEND",
        object_ref="entry-2",
        at_utc=T1,
        run_id="run-1",
    )
    head_before = store.head_digest()
    store.close()

    reopened = DurableMemoryAccessAuditTrail(db_path=db)
    assert reopened.counts() == {"entries": 2}
    assert reopened.head_digest() == head_before
    assert reopened.first_broken_sequence() is None
    entries = reopened.entries()
    assert [e.sequence for e in entries] == [1, 2]
    assert entries[0].at_utc == T0  # caller-supplied instants preserved exactly
    reopened.close()


def test_duplicate_sequence_refused_typed(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite3"
    store = DurableMemoryAccessAuditTrail(db_path=db)
    store.record(
        actor="runtime",
        authorization_context="L0-internal",
        operation="EPISODIC_APPEND",
        object_ref="entry-1",
        at_utc=T0,
    )
    # minting a fresh genesis-linked entry with sequence 1 → chain refuses
    # (sequence gap); minting against the current head then racing the UNIQUE
    # constraint is the storage-level duplicate path:
    e_dup = _entry(2, store.head_digest())
    store.append(e_dup)
    with pytest.raises(MemoryAuditStoreError, match="already_recorded|refused"):
        store.append(e_dup)
    store.close()


def test_secret_like_actor_refused_before_persist(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite3"
    store = DurableMemoryAccessAuditTrail(db_path=db)
    with pytest.raises(MemoryAuditStoreError, match="record_refused"):
        store.record(
            actor="sk-AAAAABBBBCCCCDDDD1111222233334444ffff",
            authorization_context="L0-internal",
            operation="EPISODIC_APPEND",
            object_ref="entry-x",
            at_utc=T0,
        )
    assert store.counts() == {"entries": 0}  # nothing entered the durable log
    store.close()


# ---------------------------------------------------------------------------
# Tamper evidence (storage-layer attacker)
# ---------------------------------------------------------------------------


def _seed_two(tmp_path: Path) -> Path:
    db = tmp_path / "audit.sqlite3"
    store = DurableMemoryAccessAuditTrail(db_path=db)
    store.record(
        actor="runtime",
        authorization_context="L0-internal",
        operation="EPISODIC_APPEND",
        object_ref="entry-1",
        at_utc=T0,
    )
    store.record(
        actor="runtime",
        authorization_context="L0-internal",
        operation="EPISODIC_GET",
        object_ref="entry-1",
        at_utc=T1,
    )
    store.close()
    return db


def test_row_digest_tamper_fails_closed_at_open(tmp_path: Path) -> None:
    db = _seed_two(tmp_path)
    # Storage-layer attacker flips a row's digest column ONLY (byte tamper
    # of the digest over the stored payload) — open must refuse fail-closed.
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE audit_entries SET row_digest=? WHERE sequence=1",
        ("f" * 64,),
    )
    conn.commit()
    conn.close()
    with pytest.raises(MemoryAuditStoreCorruption, match="row_digest_mismatch"):
        DurableMemoryAccessAuditTrail(db_path=db)


def test_chain_link_tamper_closes_gate_fail_closed(tmp_path: Path) -> None:
    db = _seed_two(tmp_path)
    # Storage-layer attacker: rewrites BOTH payload and row digest of entry 2
    # into a VALID self-consistent entry that is chained to the WRONG prior
    # (genesis instead of entry 1's digest) — the row digests all match but
    # the CHAIN is broken: open must detect it and close the gate.
    attacker_entry = _entry(2, "0" * 64, at=T2)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE audit_entries SET payload=?, entry_digest=?, row_digest=? WHERE sequence=2",
        (
            json.dumps(attacker_entry.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")),
            attacker_entry.entry_digest,
            hashlib.sha256(
                json.dumps(attacker_entry.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest(),
        ),
    )
    conn.commit()
    conn.close()
    store = DurableMemoryAccessAuditTrail(db_path=db)  # open succeeds…
    assert store.gate_closed_reason() is not None  # …but the gate is CLOSED
    assert store.first_broken_sequence() == -1  # chain not rebuildable
    assert store.entries() == ()  # honest empty view on a closed gate
    with pytest.raises(MemoryAuditStoreCorruption):
        store.record(
            actor="runtime",
            authorization_context="L0-internal",
            operation="EPISODIC_APPEND",
            object_ref="entry-3",
            at_utc=T2,
        )
    store.close()


# ---------------------------------------------------------------------------
# Verified backup + fail-closed restore
# ---------------------------------------------------------------------------


def test_backup_and_restore_round_trip(tmp_path: Path) -> None:
    db = _seed_two(tmp_path)
    store = DurableMemoryAccessAuditTrail(db_path=db)
    backup_dir = tmp_path / "backups"
    result = store.backup(backup_dir / "audit_backup.sqlite3")
    assert result["verified"] is True
    assert Path(result["path"]).exists()
    assert len(result["sha256"]) == 64
    # live store keeps working after backup
    store.record(
        actor="runtime",
        authorization_context="L0-internal",
        operation="EPISODIC_GET",
        object_ref="entry-1",
        at_utc=T2,
    )
    # a NEW store restores from the backup and recovers exactly 2 entries
    target = tmp_path / "restored" / "audit.sqlite3"
    target.parent.mkdir(parents=True)
    fresh = DurableMemoryAccessAuditTrail(db_path=target)
    restored = fresh.restore(backup_dir / "audit_backup.sqlite3")
    assert restored["verified"] is True
    assert restored["restored_counts"] == {"entries": 2}
    assert fresh.counts() == {"entries": 2}
    assert fresh.first_broken_sequence() is None
    fresh.close()
    store.close()


def test_restore_refuses_unverified_source(tmp_path: Path) -> None:
    db = _seed_two(tmp_path)
    store = DurableMemoryAccessAuditTrail(db_path=db)
    # (a) missing source
    with pytest.raises(MemoryAuditStoreCorruption, match="restore_source_missing"):
        store.restore(tmp_path / "nope.sqlite3")
    # (b) garbage source
    garbage = tmp_path / "garbage.sqlite3"
    garbage.write_bytes(b"not a sqlite database at all")
    with pytest.raises(MemoryAuditStoreCorruption):
        store.restore(garbage)
    # (c) structurally-sqlite but wrong-schema source
    wrong = tmp_path / "wrong.sqlite3"
    wc = sqlite3.connect(str(wrong))
    wc.execute("CREATE TABLE other (x INTEGER)")
    wc.commit()
    wc.close()
    with pytest.raises(MemoryAuditStoreCorruption, match="schema_digest|unreadable"):
        store.restore(wrong)
    store.close()
