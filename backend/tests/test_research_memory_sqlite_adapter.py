"""Focused tests for the PRODUCTION AI-3 research-memory adapter
(``app/data/research_memory_sqlite.py`` — SQLite-WAL + AES-256-GCM carrier,
owner decisions D1/D3/D4/D5/D6/D7 recorded 2026-11-02).

Mirrors the acceptance-scaffold fixtures style: deterministic fixture-kit
builders, fixed timeline (T0 < T1 < T2 < T3), seeding exclusively through
the append-only API. The behavioral authority remains the contract pair
(``EpisodicRunArchive`` + ``SemanticLessonStore``); these tests prove the
SQLite leg carries it faithfully, encrypts it at rest, refuses tampered
state fail-closed, and supports the D5/D7 backup + restore drill.

TEST-ONLY KEY: ``TEST_ONLY_STATIC_KEY`` below is a FIXED, PUBLIC, 32-byte
constant clearly labeled TEST-ONLY. It is NOT a real secret and must never
be used outside this test module (production keys come from
``select_key_provider`` / ``env_key_provider`` — D4).

TAMPER MECHANICS: the raw-SQL row-tamper ``UPDATE episodic SET enc ...``
lives HERE, in the TEST file (simulating an out-of-band attacker), NOT in
the adapter — the adapter's own source is pinned row-mutation-SQL-free by
``test_adapter_source_has_no_row_mutation_sql``.
"""

from __future__ import annotations

import base64
import hashlib
import shutil
import sqlite3
import tempfile
import weakref
from pathlib import Path

import pytest

import app.data.research_memory_sqlite as adapter_module
from app.data.research_memory_sqlite import (
    RETENTION_POLICY,
    SqliteWalResearchMemoryStore,
    env_key_provider,
    select_key_provider,
)
from app.domain.research_memory_store import (
    InMemoryResearchMemoryStore,
    ResearchMemoryStore,
    canonical_research_memory_json,
    sha256_hex,
    verify_integrity,
)
from helpers_research_memory_fixtures import (
    T0,
    T1,
    T2,
    T3,
    make_episodic_entry,
    make_lesson,
)

#: TEST-ONLY — a fixed, public, throwaway 32-byte key. NOT A REAL SECRET.
TEST_ONLY_STATIC_KEY = bytes(range(32))


def _make_store(directory: str | Path | None = None) -> tuple[
    SqliteWalResearchMemoryStore, Path
]:
    """Fresh store + its root directory (self-owned tmp dir by default).

    Determinism note (same class as the JSONL reference factory): record
    semantics are clock-free/RNG-free; the tmp-dir ACQUISITION and the
    AES-GCM per-record nonces are operational infrastructure that never
    touches record content or ordering.
    """
    root = Path(tempfile.mkdtemp(prefix="ai3_sqlite_test_")) if directory is None else Path(directory)
    store = SqliteWalResearchMemoryStore(
        directory=root, key_provider=lambda: TEST_ONLY_STATIC_KEY
    )
    weakref.finalize(store, shutil.rmtree, str(root), ignore_errors=True)
    return store, root


# ---------------------------------------------------------------------------
# Protocol surface, roundtrip, refusals, misses
# ---------------------------------------------------------------------------


def test_protocol_isinstance() -> None:
    """The production adapter satisfies the runtime-checkable Protocol."""
    store, _ = _make_store()
    assert isinstance(store, ResearchMemoryStore)


def test_roundtrip_and_in_memory_reference_equivalence() -> None:
    """Append/get/query views are byte-equivalent to the in-memory
    reference store seeded with the same records through the same API."""
    entries = (
        make_episodic_entry("ra-1", recorded_at_utc=T1),
        make_episodic_entry("ra-2", run_id="run-r2", recorded_at_utc=T2),
        make_episodic_entry(
            "ra-3", run_id="run-r3", hypothesis_id=None, recorded_at_utc=T3
        ),
    )
    lessons = (
        make_lesson(lesson_id="l1", created_at_utc=T1),
        make_lesson(
            lesson_id="l1",
            version=2,
            supersedes_version=1,
            curation_basis="HUMAN_REVIEW",
            curated_by="reviewer-1",
            created_at_utc=T2,
        ),
    )
    store, _ = _make_store()
    reference = InMemoryResearchMemoryStore()
    for target in (store, reference):
        for entry in entries:
            target.append_episodic(entry)
        for lesson in lessons:
            target.register_lesson(lesson)
    for entry_id in ("ra-1", "ra-2", "ra-3"):
        assert store.get_episodic(entry_id) == reference.get_episodic(entry_id)
    assert store.episodic_for_run("run-r2") == reference.episodic_for_run("run-r2")
    assert store.episodic_for_run("run-r3") == reference.episodic_for_run("run-r3")
    assert store.episodic_for_hypothesis("hyp-7") == reference.episodic_for_hypothesis(
        "hyp-7"
    )
    assert store.episodic_available_at(T2) == reference.episodic_available_at(T2)
    assert store.episodic_available_at(T3) == reference.episodic_available_at(T3)
    assert store.latest_lesson("l1") == reference.latest_lesson("l1")
    assert store.lesson_history("l1") == reference.lesson_history("l1")
    assert store.lessons_active_at(T1) == reference.lessons_active_at(T1)
    assert store.lessons_active_at(T3) == reference.lessons_active_at(T3)
    assert canonical_research_memory_json(store.integrity_report()) == (
        canonical_research_memory_json(reference.integrity_report())
    )


def test_fresh_store_integrity_and_reference_equality() -> None:
    """Fresh/empty and lightly-seeded stores report byte-identically to the
    in-memory reference; domain ``verify_integrity`` is clean."""
    store, _ = _make_store()
    reference = InMemoryResearchMemoryStore()
    assert store.integrity_report().verify_ok is True
    assert canonical_research_memory_json(store.integrity_report()) == (
        canonical_research_memory_json(reference.integrity_report())
    )
    entry = make_episodic_entry("ra-1")
    lesson = make_lesson(lesson_id="l1")
    store.append_episodic(entry)
    store.register_lesson(lesson)
    reference.append_episodic(entry)
    reference.register_lesson(lesson)
    assert canonical_research_memory_json(store.integrity_report()) == (
        canonical_research_memory_json(reference.integrity_report())
    )
    expected = dict(store.integrity_report().entry_digests)
    assert verify_integrity(store, expected).verify_ok is True


def test_conflict_refusals_verbatim_idempotent_and_explicit_misses() -> None:
    """Contract ValueErrors propagate verbatim; refused writes leave the
    store (and the disk row count) unchanged; unknown ids are explicit
    misses (None / empty tuples), never fabricated records."""
    store, root = _make_store()
    entry = make_episodic_entry("ra-1")
    store.append_episodic(entry)
    store.append_episodic(entry)  # identical re-append: idempotent no-op
    with pytest.raises(ValueError, match="episodic_archive_conflict"):
        store.append_episodic(make_episodic_entry("ra-1", trust_state="stale"))
    assert store.get_episodic("ra-1") == entry  # refusal rewrote nothing
    store.register_lesson(make_lesson(lesson_id="l1"))
    with pytest.raises(ValueError, match="lesson_version_not_increasing"):
        store.register_lesson(make_lesson(lesson_id="l1", version=1))
    store.register_lesson(
        make_lesson(lesson_id="l1", version=2, created_at_utc=T2)
    )
    with pytest.raises(ValueError, match="lesson_supersession_parent_mismatch"):
        store.register_lesson(
            make_lesson(
                lesson_id="l1", version=3, supersedes_version=1, created_at_utc=T3
            )
        )
    # Disk truth: exactly one episodic row (idempotent re-append wrote nothing).
    conn = sqlite3.connect(str(root / "research_memory.sqlite"))
    try:
        assert conn.execute("SELECT COUNT(*) FROM episodic").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 2
    finally:
        conn.close()
    # Explicit misses (AC-12 semantics, wrapped verbatim).
    assert store.get_episodic("ghost") is None
    assert store.episodic_for_run("ghost") == ()
    assert store.episodic_for_hypothesis("ghost") == ()
    assert store.episodic_available_at(T0) == ()
    assert store.latest_lesson("ghost") is None
    assert store.lesson_history("ghost") == ()
    assert store.lessons_active_at(T0) == ()


# ---------------------------------------------------------------------------
# Encryption at rest, digest determinism, reopen persistence
# ---------------------------------------------------------------------------


def test_encryption_at_rest_no_plaintext_bytes_on_disk() -> None:
    """D4 proof: the raw SQLite bytes (main db + WAL side files) contain NO
    canonical-JSON plaintext and no recognizable record field text of an
    appended record — every durable content byte is ciphertext."""
    store, root = _make_store()
    entry = make_episodic_entry("ra-1", notes="µ € 😀 evidence")
    store.append_episodic(entry)
    store.register_lesson(
        make_lesson(
            lesson_id="l1",
            statement="Money-flow regime shifts precede breadth expansion.",
        )
    )
    blobs = b"".join(
        path.read_bytes()
        for path in sorted(root.glob("research_memory.sqlite*"))
        if path.is_file()
    )
    canonical = canonical_research_memory_json(entry).encode("utf-8")
    assert len(blobs) > 0
    assert canonical not in blobs
    assert "µ € 😀 evidence".encode("utf-8") not in blobs
    assert "Money-flow regime shifts".encode("utf-8") not in blobs
    assert b"gov-1" not in blobs  # policy_version: record field stays encrypted


def test_digest_determinism_across_stores() -> None:
    """Canonical-JSON stability: the same record appended to two fresh
    stores yields the SAME stored digest column (content addressing, D1)."""
    store_a, root_a = _make_store()
    store_b, root_b = _make_store()
    entry = make_episodic_entry("ra-1", notes="µ € 😀")
    store_a.append_episodic(entry)
    store_b.append_episodic(entry)
    expected = sha256_hex(canonical_research_memory_json(entry))
    for root in (root_a, root_b):
        conn = sqlite3.connect(str(root / "research_memory.sqlite"))
        try:
            row = conn.execute(
                "SELECT digest FROM episodic WHERE entry_id = 'ra-1'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == expected


def test_reopen_persistence_equivalence_and_documented_supersession_nuance() -> None:
    """A store reopened on the same directory reproduces every record and
    digest cleanly; the module docstring's documented nuance is pinned: v1
    re-opens with the status it was WRITTEN with (rows are immutable) while
    the version chain stays the authoritative supersession evidence."""
    store, root = _make_store()
    entry_1 = make_episodic_entry("ra-1", recorded_at_utc=T1)
    entry_2 = make_episodic_entry(
        "ra-2", run_id="run-r2", hypothesis_id=None, recorded_at_utc=T2
    )
    store.append_episodic(entry_1)
    store.append_episodic(entry_2)
    store.register_lesson(make_lesson(lesson_id="l1"))
    store.register_lesson(make_lesson(lesson_id="l1", version=2, created_at_utc=T2))
    expected = dict(store.integrity_report().entry_digests)
    reopened, _ = _make_store(directory=root)
    assert reopened.get_episodic("ra-1") == entry_1
    assert reopened.get_episodic("ra-2") == entry_2
    assert [e.entry_id for e in reopened.episodic_available_at(T2)] == ["ra-1", "ra-2"]
    assert dict(reopened.integrity_report().entry_digests) == expected
    assert verify_integrity(reopened, expected).verify_ok is True
    latest = reopened.latest_lesson("l1")
    assert latest is not None and latest.version == 2 and latest.status == "ACTIVE"
    history = reopened.lesson_history("l1")
    assert [l.version for l in history] == [1, 2]
    assert reopened.integrity_report().lesson_version_counts == (("l1", 2),)
    # DOCUMENTED NUANCE (adapter docstring): immutable rows keep the written
    # status; the chain (v2 exists ⇒ v1 superseded) is the real evidence.
    assert history[0].status == "ACTIVE"


# ---------------------------------------------------------------------------
# Tamper → fail-closed gate (JSONL-reference mirror)
# ---------------------------------------------------------------------------


def test_tamper_detected_gate_closed_new_instance_fails_closed_row_never_healed(
    tmp_path,
) -> None:
    """Out-of-band row tampering (raw SQL HERE in the test) is caught: the
    live instance's next integrity observation refuses further writes, a
    fresh instance on the same directory fails closed too, the corrupt row
    stays on disk as permanent evidence (never healed), and the
    unverifiable record is never served or fabricated."""
    store, root = _make_store()
    entry = make_episodic_entry("ra-1")
    store.append_episodic(entry)
    db_path = root / "research_memory.sqlite"
    # --- tamper (TEST-side raw SQL; the adapter contains no such SQL) ---
    raw = sqlite3.connect(str(db_path))
    try:
        blob = raw.execute(
            "SELECT enc FROM episodic WHERE entry_id = 'ra-1'"
        ).fetchone()[0]
        tampered = blob[:20] + bytes([blob[20] ^ 0xFF]) + blob[21:]
        raw.execute(
            "UPDATE episodic SET enc = ? WHERE entry_id = 'ra-1'", (tampered,)
        )
        raw.commit()
    finally:
        raw.close()
    # Same instance: next observation detects and closes the write gate.
    report = store.integrity_report()
    assert report.verify_ok is False
    assert report.mismatched_entry_ids == ("ra-1",)
    assert any(r.endswith("_decrypt_failed") for r in report.refusal_reasons)
    with pytest.raises(ValueError, match="file_integrity_unverified"):
        store.append_episodic(make_episodic_entry("ra-2", run_id="run-r2"))
    # Fresh instance on the SAME directory: fails closed at load.
    fresh, _ = _make_store(directory=root)
    with pytest.raises(ValueError, match="file_integrity_unverified"):
        fresh.append_episodic(make_episodic_entry("ra-3", run_id="run-r3"))
    assert fresh.get_episodic("ra-1") is None  # never fabricated from a bad row
    fresh_report = fresh.integrity_report()
    assert fresh_report.verify_ok is False
    assert fresh_report.mismatched_entry_ids == ("ra-1",)
    # The corrupt row is permanent evidence: still on disk, byte-identical.
    check = sqlite3.connect(str(db_path))
    try:
        stored = check.execute(
            "SELECT enc FROM episodic WHERE entry_id = 'ra-1'"
        ).fetchone()[0]
    finally:
        check.close()
    assert stored == tampered


# ---------------------------------------------------------------------------
# Backup / verify_backup / rotation / restore drill (D5 + D7)
# ---------------------------------------------------------------------------


def test_backup_verify_rotation_wrong_key_and_restore_drill(tmp_path) -> None:
    """D5: snapshot + sha256 sidecar; rotation keeps exactly ``keep`` backup
    FILES (live store untouched). D4 fail-closed: a wrong key produces a
    refusal report, never an exception. D7 drill: copy-back restore opens,
    serves every record and verifies clean."""
    store, _ = _make_store()
    entry_1 = make_episodic_entry("ra-1", recorded_at_utc=T1)
    entry_2 = make_episodic_entry("ra-2", run_id="run-r2", recorded_at_utc=T2)
    store.append_episodic(entry_1)
    store.append_episodic(entry_2)
    store.register_lesson(make_lesson(lesson_id="l1"))
    dest = tmp_path / "backups"
    snapshot = store.backup(dest, keep=14)
    assert snapshot.is_file()
    sidecar = snapshot.with_name(snapshot.name + ".sha256")
    assert sidecar.is_file()
    digest_text, _, name = sidecar.read_text(encoding="ascii").partition("  ")
    assert name.strip() == snapshot.name
    assert digest_text == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    report = SqliteWalResearchMemoryStore.verify_backup(
        snapshot, key_provider=lambda: TEST_ONLY_STATIC_KEY
    )
    assert report.verify_ok is True
    assert report.entry_count == 2
    assert [eid for eid, _ in report.entry_digests] == ["ra-1", "ra-2"]
    assert report.lesson_version_counts == (("l1", 1),)
    assert report.refusal_reasons == ()
    # Wrong key → fail-closed refusal record (never raises, never guesses).
    wrong = SqliteWalResearchMemoryStore.verify_backup(
        snapshot, key_provider=lambda: b"\x00" * 32
    )
    assert wrong.verify_ok is False
    assert any(r.endswith("_decrypt_failed") for r in wrong.refusal_reasons)
    # Rotation: four snapshots with keep=2 → exactly the two newest remain,
    # each with its sidecar. The LIVE store keeps every record (no purge).
    for _ in range(3):
        store.backup(dest, keep=2)
    remaining = sorted(dest.glob("research-memory-*.sqlite"))
    assert len(remaining) == 2
    assert all(
        f.with_name(f.name + ".sha256").is_file() for f in remaining
    )
    newest = SqliteWalResearchMemoryStore.verify_backup(
        remaining[-1], key_provider=lambda: TEST_ONLY_STATIC_KEY
    )
    assert newest.verify_ok is True and newest.entry_count == 2
    assert store.integrity_report().entry_count == 2  # live store: no purge
    # D7 restore drill: copy-back under the canonical name, reopen, verify.
    restore_dir = tmp_path / "restored"
    restore_dir.mkdir()
    shutil.copy2(remaining[-1], restore_dir / "research_memory.sqlite")
    restored, _ = _make_store(directory=restore_dir)
    assert restored.get_episodic("ra-1") == entry_1
    assert restored.get_episodic("ra-2") == entry_2
    assert restored.latest_lesson("l1") is not None
    expected = dict(store.integrity_report().entry_digests)
    assert dict(restored.integrity_report().entry_digests) == expected
    assert verify_integrity(restored, expected).verify_ok is True


def test_verify_backup_missing_file_fails_closed(tmp_path) -> None:
    """A missing/unreadable snapshot yields a refusal record, not an
    exception (domain never-raise boundary)."""
    report = SqliteWalResearchMemoryStore.verify_backup(
        tmp_path / "does-not-exist.sqlite",
        key_provider=lambda: TEST_ONLY_STATIC_KEY,
    )
    assert report.verify_ok is False
    assert report.refusal_reasons == ("backup_file_missing",)


# ---------------------------------------------------------------------------
# Structural: no row-mutation SQL in the adapter (D3)
# ---------------------------------------------------------------------------


def test_adapter_source_has_no_row_mutation_sql() -> None:
    """D3 structural pin: the adapter source contains no ``DELETE FROM`` and
    no ``UPDATE `` SQL anywhere (appends and reads only; the backup rotation
    removes backup FILES, not store rows). The scan is non-vacuous: the
    TEST's own tamper ``UPDATE episodic SET enc`` lives in THIS file."""
    source = Path(adapter_module.__file__).read_text(encoding="utf-8")
    assert "DELETE FROM" not in source
    assert "UPDATE " not in source
    assert RETENTION_POLICY == {
        "episodic": "PERMANENT_NO_PURGE",
        "semantic_lessons": "PERMANENT_RETIRE_NOT_DELETE",
    }
    test_source = Path(__file__).read_text(encoding="utf-8")
    assert "UPDATE episodic SET enc" in test_source  # tamper lives HERE only


# ---------------------------------------------------------------------------
# Key providers (D4) — fail-closed, never logged
# ---------------------------------------------------------------------------


class _FakeKeyring:
    """Minimal in-memory keyring double — the REAL OS keyring is never
    touched by tests."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, value: str) -> None:
        self.store[(service, username)] = value


def test_env_key_provider_hex_base64_and_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("RADAR_RESEARCH_MEMORY_KEY", "ab" * 32)
    assert env_key_provider() == bytes.fromhex("ab" * 32)
    monkeypatch.setenv(
        "RADAR_RESEARCH_MEMORY_KEY",
        base64.b64encode(TEST_ONLY_STATIC_KEY).decode("ascii"),
    )
    assert env_key_provider() == TEST_ONLY_STATIC_KEY
    monkeypatch.setenv(
        "RADAR_RESEARCH_MEMORY_KEY",
        base64.urlsafe_b64encode(TEST_ONLY_STATIC_KEY).decode("ascii"),
    )
    assert env_key_provider() == TEST_ONLY_STATIC_KEY
    for bad in ("", "zz", "ab" * 31, "d" * 63):
        monkeypatch.setenv("RADAR_RESEARCH_MEMORY_KEY", bad)
        with pytest.raises(ValueError, match="research_memory_key_invalid"):
            env_key_provider()
    monkeypatch.delenv("RADAR_RESEARCH_MEMORY_KEY", raising=False)
    with pytest.raises(ValueError, match="research_memory_key_invalid"):
        env_key_provider()


def test_select_key_provider_env_override_wins(monkeypatch) -> None:
    monkeypatch.setenv("RADAR_RESEARCH_MEMORY_KEY", TEST_ONLY_STATIC_KEY.hex())
    provider = select_key_provider(prefer_keyring=True)
    assert provider() == TEST_ONLY_STATIC_KEY


def test_select_key_provider_keyring_create_once(monkeypatch) -> None:
    fake = _FakeKeyring()
    monkeypatch.setattr(adapter_module, "keyring", fake)
    monkeypatch.delenv("RADAR_RESEARCH_MEMORY_KEY", raising=False)
    provider = select_key_provider(prefer_keyring=True)
    first = provider()
    second = provider()
    assert first == second and len(first) == 32
    ((stored_service, stored_user), stored_value) = next(iter(fake.store.items()))
    assert (stored_service, stored_user) == ("shekar-saham", "research-memory")
    assert bytes.fromhex(stored_value) == first  # stored ONCE, as hex


def test_select_key_provider_no_source_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(adapter_module, "keyring", None)
    monkeypatch.delenv("RADAR_RESEARCH_MEMORY_KEY", raising=False)
    with pytest.raises(ValueError, match="research_memory_key_invalid"):
        select_key_provider(prefer_keyring=True)


def test_store_rejects_non_32_byte_keys() -> None:
    for bad_key in (b"\x00" * 31, b"\x00" * 33, "", None):
        with pytest.raises(ValueError, match="research_memory_key_invalid"):
            SqliteWalResearchMemoryStore(
                directory=tempfile.mkdtemp(prefix="ai3_sqlite_badkey_"),
                key_provider=lambda bad_key=bad_key: bad_key,  # type: ignore[arg-type,return-value]
            )


# ---------------------------------------------------------------------------
# Scaffold registry integration (one-entry addition, by design)
# ---------------------------------------------------------------------------


def _sqlite_wal_encrypted_reference_factory() -> ResearchMemoryStore:
    """Fresh, EMPTY production-adapter store in a self-owned tmp dir, with
    the TEST-ONLY static key injected (clearly labeled above — NOT a real
    secret; production keys come from ``select_key_provider``/D4).

    Determinism note (same documented deviation class as the JSONL
    reference factory): record semantics are clock-free/RNG-free; the
    tmp-dir ACQUISITION is harness infrastructure (same class as pytest's
    ``tmp_path``) and never touches store content or ordering.
    """
    root = Path(tempfile.mkdtemp(prefix="ai3_sqlite_wal_enc_"))
    store = SqliteWalResearchMemoryStore(
        directory=root, key_provider=lambda: TEST_ONLY_STATIC_KEY
    )
    weakref.finalize(store, shutil.rmtree, str(root), ignore_errors=True)
    return store


def test_factory_entry_registered_in_scaffold() -> None:
    """The scaffold's STORE_FACTORIES registry carries exactly one new entry
    (\"sqlite_wal_encrypted_reference\"); building it yields a working,
    EMPTY store (lazy import here — the scaffold imports THIS module for the
    factory, so a module-level import would be circular)."""
    from test_ai3_acceptance_scaffold import STORE_FACTORIES  # noqa: PLC0415

    names = [name for name, _factory in STORE_FACTORIES]
    assert names.count("sqlite_wal_encrypted_reference") == 1
    factory = dict(STORE_FACTORIES)["sqlite_wal_encrypted_reference"]
    store = factory()
    assert isinstance(store, ResearchMemoryStore)
    report = store.integrity_report()
    assert report.verify_ok is True and report.entry_count == 0
    store.append_episodic(make_episodic_entry("ra-1"))
    assert store.get_episodic("ra-1") is not None
    assert store.integrity_report().entry_count == 1
