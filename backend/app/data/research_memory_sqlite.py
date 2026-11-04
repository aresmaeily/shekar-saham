"""PRODUCTION AI-3 research-memory persistence adapter (owner decisions D1–D7
recorded 2026-11-02).

AUTHORITY: ``docs/active/OWNER_DECISIONS_RECORDED_2026-11-02.md`` rows
D1 / D3 / D4 / D5 / D6 / D7; production adapter work per
``docs/active/AI3_PERSISTENCE_IMPLEMENTATION_PLAN.md``. NOT auto-wired into
app startup — engine activation remains a separate owner gate (D1 row,
"no runtime auto-wiring").

DECISIONS MIRRORED HERE (no behavior invented):
- D1  SQLite-WAL + content-addressed blobs. File
  ``<directory>/research_memory.sqlite``; ``PRAGMA journal_mode=WAL`` and
  ``PRAGMA synchronous=FULL`` (durability over speed for evidence; one
  committed transaction per append). Per-record digest =
  ``sha256_hex(canonical_research_memory_json(record))`` computed BEFORE
  encryption, stored in the row's ``digest`` column — the existing
  ``verify_integrity`` contract consumes it unchanged.
- D3  Per-class retention: episodic evidence is PERMANENT (architectural
  no-purge); semantic-lesson history is PERMANENT (retire ≠ delete —
  retirement is a version-chain state, never a deletion). Exported as
  ``RETENTION_POLICY`` and seeded once into the ``meta`` table. The store
  contains NO row-mutation SQL anywhere: the only DML statements are
  INSERT (appends) and SELECT (reads). The ``backup`` rotation in this
  module applies ONLY to backup FILES in the destination directory — it
  never touches the live store (see ``backup`` docstring).
- D4  OS keyring (Windows Credential Manager via the optional ``keyring``
  dependency) + AES-256-GCM at rest. Key is never in code or logs; the
  store is fail-closed without a valid 32-byte key
  (``ValueError("research_memory_key_invalid")``). ``keyring`` is
  import-guarded (install-time opt-in); the
  ``RADAR_RESEARCH_MEMORY_KEY`` environment variable overrides it for
  headless/CI contexts (hex or base64, must decode to exactly 32 bytes).
- D5  Local backups, ``backup(destination_dir, keep=14)``: SQLite
  backup-API snapshot into a UTC-stamped file + ``.sha256`` sidecar,
  rotation of BACKUP FILES only (keep oldest pruned beyond ``keep``).
  Matches the shipped ``Store.backup(keep=...)`` precedent.
- D6  Single-user access model: single-writer discipline (one external
  lock, like every adapter in this family); the OS file ACL is the
  boundary. No multi-writer guarantee is made anywhere.
- D7  RPO ≤ 24h / RTO ≤ 15 min: ``verify_backup`` re-opens a snapshot
  read-only and returns a fail-closed ``ResearchMemoryIntegrityReport``
  (never raises), so a restore drill is: copy the backup file back as
  ``research_memory.sqlite`` into a fresh directory, open a store on it,
  ``verify_integrity`` clean.

ARCHITECTURE (composition-by-delegation — same as the test-layer JSONL
reference ``tests/research_memory_jsonl_reference.py``, which this module
mirrors): the sole behavior authority is the delivered contract pair
(``EpisodicRunArchive`` + ``SemanticLessonStore``); the SQLite leg is a
persistence CARRIER only. Every read is pure delegation through an
``InMemoryResearchMemoryStore`` view rebuilt on each commit. Records are
created only by contract validation and re-validated on load.

STORAGE DISCIPLINE:
- APPEND-ONLY: writes create or refuse; never mutate, rewrite or purge.
  No retention-expiry path exists (A3/A11). Tables:
  ``episodic(entry_id TEXT PRIMARY KEY, digest TEXT NOT NULL, enc BLOB NOT NULL)``,
  ``lessons(lesson_id TEXT, version INTEGER, digest TEXT, enc BLOB,
  PRIMARY KEY(lesson_id, version))``,
  ``meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)``.
- ENCRYPTION AT REST: ``enc = nonce(12) || AESGCM(key).encrypt(nonce,
  canonical_utf8, aad)`` with per-record random nonce and
  ``aad = "<table>:<row-id>"`` (episodic: ``episodic:<entry_id>``; lessons:
  ``lessons:<lesson_id>:<version>``). The AAD binds each ciphertext to its
  exact row identity: a ciphertext moved to another row, or a payload
  re-written under another row's identity, fails decryption. Plaintext
  never reaches disk — every durable byte of record content is ciphertext.
- FAIL-CLOSED LOAD (mirrors the JSONL reference exactly): on open, every
  row is decrypted with the same AAD, its plaintext digest recomputed and
  compared against the stored ``digest`` column, and the payload
  re-validated through the contract constructor. ANY decrypt failure,
  undecodable plaintext, digest mismatch or contract-invalid payload is
  PERMANENT EVIDENCE: the row is never deleted, repaired or healed; the
  record yields NO view entry (never fabricated); the store closes its
  write gate and refuses all further appends/registrations with
  ``ValueError("file_integrity_unverified"``) — the JSONL reference's own
  gate reason. ``integrity_report()`` names the offending entry ids in
  ``mismatched_entry_ids`` and the machine-readable reasons in
  ``refusal_reasons``. A tamper detected at ANY later integrity
  observation (the report re-reads and re-verifies the rows from disk)
  permanently closes the gate the same way.
- ALL-OR-NOTHING: the contract pre-check runs BEFORE any I/O (idempotent
  re-append and conflict/chain refusals write nothing); the row INSERT is
  committed BEFORE the in-memory state commit, so a mid-write crash leaves
  the record absent from the API and a torn row refused at the next load.
- CONCURRENCY CLASS (D6): SINGLE-WRITER — all writers must share one
  external lock; the adapter additionally serializes its own writes.
  Connections are per-operation (never shared across threads).

SUPSESSION-STATUS RELOAD NUANCE (documented honesty, mirrors the JSONL
reference's load semantics): rows are immutable, so when lesson v2 is
registered the v1 row keeps the status it was WRITTEN with; a reopened
store re-seeds the contract view directly from the rows (constructor
seeding — never re-derived), so a non-latest version re-appears with its
written status instead of a derived SUPERSEDED marker. The effective
semantics stay correct after reload because they derive from the version
chain itself (``latest``/``lessons_active_at``/future ``register`` chains
read the highest version), and RETIRED terminal rows carry their own
status. Healing the marker would require row mutation, which D3 forbids.
The canonical SUPERSEDED evidence is the chain: any version with a
registered successor is superseded-by-construction.

Contract/domain discipline: timestamps come from the records only (the
store reads no clock for record semantics; the ONLY clock/RNG reads are
the D5 backup filename stamp, the backup-set rotation, and AES-GCM nonce
generation — operational layers, never record content).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.domain.research_memory import (
    EpisodicRunArchive,
    EpisodicRunArtifact,
    SemanticLesson,
    SemanticLessonStore,
)
from app.domain.research_memory_store import (
    InMemoryResearchMemoryStore,
    ResearchMemoryIntegrityReport,
    canonical_research_memory_json,
    sha256_hex,
    verify_integrity,
)

try:  # optional dependency (D4: Windows Credential Manager path)
    import keyring
except Exception:  # pragma: no cover — optional dep absent in headless envs
    keyring = None  # type: ignore[assignment]

__all__ = [
    "RETENTION_POLICY",
    "SqliteWalResearchMemoryStore",
    "env_key_provider",
    "select_key_provider",
]

#: D3 — per-class retention table. The live store has NO purge path:
#: episodic evidence is architecturally permanent; semantic-lesson history
#: is permanent (retirement is a version-chain state, never a deletion).
#: Backup FILES are the only rotatable artifact (D5, keep=14).
RETENTION_POLICY = {
    "episodic": "PERMANENT_NO_PURGE",
    "semantic_lessons": "PERMANENT_RETIRE_NOT_DELETE",
}

_DB_NAME = "research_memory.sqlite"
_KEY_ENV_VAR = "RADAR_RESEARCH_MEMORY_KEY"
_KEYRING_SERVICE = "shekar-saham"
_KEYRING_USERNAME = "research-memory"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS episodic (
        entry_id TEXT PRIMARY KEY,
        digest TEXT NOT NULL,
        enc BLOB NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lessons (
        lesson_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        digest TEXT NOT NULL,
        enc BLOB NOT NULL,
        PRIMARY KEY (lesson_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
)
_META_SEED: tuple[tuple[str, str], ...] = (
    ("schema", "research_memory_sqlite_v1"),
    ("retention_policy:episodic", RETENTION_POLICY["episodic"]),
    ("retention_policy:semantic_lessons", RETENTION_POLICY["semantic_lessons"]),
)


# ---------------------------------------------------------------------------
# Key handling (D4) — fail-closed, never logged
# ---------------------------------------------------------------------------


def _validated_key(material: object) -> bytes:
    """Accept only exactly-32-byte key material; refuse everything else.

    Fail-closed and silent about the material: the reason never contains
    any part of the key.
    """
    if isinstance(material, (bytes, bytearray, memoryview)):
        raw = bytes(material)
        if len(raw) == _KEY_BYTES:
            return raw
    raise ValueError("research_memory_key_invalid")


def _decode_key_material(raw: str) -> bytes:
    """Decode env/keyring key text: hex (64 chars) or base64, else refuse."""
    text = raw.strip()
    if not text:
        raise ValueError("research_memory_key_invalid")
    if len(text) == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
        try:
            return _validated_key(bytes.fromhex(text))
        except ValueError:
            raise ValueError("research_memory_key_invalid") from None
    padded = text + "=" * (-len(text) % 4)
    try:
        return _validated_key(base64.b64decode(padded, validate=True))
    except Exception:
        pass
    try:
        return _validated_key(base64.urlsafe_b64decode(padded))
    except Exception:
        pass
    raise ValueError("research_memory_key_invalid")


def env_key_provider() -> bytes:
    """Read ``RADAR_RESEARCH_MEMORY_KEY`` (hex or base64 → 32 bytes).

    Fail-closed: a missing, unparsable or wrong-length value raises
    ``ValueError("research_memory_key_invalid")``. The value is never
    logged, never echoed, never included in any exception message.
    """
    raw = os.environ.get(_KEY_ENV_VAR)
    if raw is None:
        raise ValueError("research_memory_key_invalid")
    return _decode_key_material(raw)


def _keyring_key_provider() -> bytes:
    """OS-keyring provider (D4): read once, create-if-missing exactly once.

    Stored as hex text under service ``shekar-saham`` / username
    ``research-memory``. Any keyring backend failure is fail-closed
    (``research_memory_key_invalid``); the key never appears in messages.
    """
    if keyring is None:  # pragma: no cover — guarded by select_key_provider
        raise ValueError("research_memory_key_invalid")
    try:
        stored = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
        if stored is None:
            fresh = os.urandom(_KEY_BYTES)
            keyring.set_password(
                _KEYRING_SERVICE, _KEYRING_USERNAME, fresh.hex()
            )
            return fresh
        return _decode_key_material(stored)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("research_memory_key_invalid") from exc


def select_key_provider(prefer_keyring: bool = True) -> Callable[[], bytes]:
    """Choose the D4 key source. Returns a zero-arg provider callable.

    Precedence: the ``RADAR_RESEARCH_MEMORY_KEY`` environment variable
    overrides everything (headless/CI contexts); otherwise the OS keyring
    (Windows Credential Manager via the optional ``keyring`` dependency,
    create-if-missing once); otherwise — no keyring available and no env
    key — fail closed immediately with
    ``ValueError("research_memory_key_invalid")``. The key material itself
    is fetched only when the provider is CALLED and is never logged.
    """
    if _KEY_ENV_VAR in os.environ:
        return env_key_provider
    if prefer_keyring and keyring is not None:
        return _keyring_key_provider
    raise ValueError("research_memory_key_invalid")


# ---------------------------------------------------------------------------
# Production adapter — SQLite-WAL carrier, composition-by-delegation
# ---------------------------------------------------------------------------


class SqliteWalResearchMemoryStore:
    """SQLite-WAL + AES-256-GCM carrier behind the append-only
    ``ResearchMemoryStore`` Protocol (D1). Composes — never replaces — the
    delivered contracts by delegation through ``InMemoryResearchMemoryStore``
    views, exactly like the JSONL reference adapter. Single-writer (D6);
    fail-closed on any unverifiable row; no row-mutation SQL exists in this
    module (D3). Not auto-wired into app startup — engine activation stays
    a separate owner gate."""

    def __init__(self, *, directory: str | Path, key_provider: Callable[[], bytes]) -> None:
        self._key = _validated_key(key_provider())
        self._aead = AESGCM(self._key)
        self._root = Path(directory)
        self._root.mkdir(parents=True, exist_ok=True)
        self._db_path = self._root / _DB_NAME
        self._write_lock = threading.Lock()
        self._file_ok = True
        self._refusal_reasons: tuple[str, ...] = ()
        self._epi_archive = EpisodicRunArchive()
        self._lesson_store = SemanticLessonStore()
        self._view = InMemoryResearchMemoryStore(
            archive=self._epi_archive, lessons=self._lesson_store
        )
        self._load_existing()

    # -- connection / schema helpers -----------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Fresh per-operation connection; WAL + synchronous=FULL (D1)."""
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
        except Exception:
            conn.close()
            raise
        return conn

    @staticmethod
    def _ensure_schema(conn: sqlite3.Connection) -> None:
        """Idempotent bootstrap DDL + one-time meta seeding (INSERT-only)."""
        for statement in _SCHEMA_SQL:
            conn.execute(statement)
        for key, value in _META_SEED:
            conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)", (key, value)
            )
        conn.commit()

    # -- crypto envelope -------------------------------------------------------

    def _encrypt(self, table: str, row_id: str, plaintext: bytes) -> bytes:
        nonce = os.urandom(_NONCE_BYTES)
        return nonce + self._aead.encrypt(nonce, plaintext, f"{table}:{row_id}".encode("utf-8"))

    def _decrypt(self, table: str, row_id: str, blob: bytes) -> bytes:
        return self._aead.decrypt(
            blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], f"{table}:{row_id}".encode("utf-8")
        )

    # -- fail-closed write gate (JSONL-reference mirror) -----------------------

    def _require_file_ok(self) -> None:
        if not self._file_ok:
            raise ValueError("file_integrity_unverified")

    def _close_gate(self, reasons: tuple[str, ...]) -> None:
        """Corruption is permanent evidence: the gate, once closed, stays
        closed (never healed, never re-opened)."""
        self._file_ok = False
        self._refusal_reasons = tuple(sorted(set(self._refusal_reasons) | set(reasons)))

    # -- strict row verification ------------------------------------------------

    def _verified_rows(
        self, epi_rows: list[tuple[str, str, bytes]], les_rows: list[tuple[str, int, str, bytes]]
    ) -> tuple[list[str], list[EpisodicRunArtifact], dict[str, str], list[SemanticLesson], dict[tuple[str, int], str], list[str]]:
        """Decrypt + digest-check + contract-revalidate every row.

        A row that fails ANY check yields NO record (never fabricated) and
        becomes a machine-readable refusal plus, for episodic rows, a
        mismatched entry id. Refused rows stay on disk untouched.
        """
        refusals: list[str] = []
        mismatched: list[str] = []
        entries: list[EpisodicRunArtifact] = []
        epi_digests: dict[str, str] = {}
        for entry_id, digest_col, enc in epi_rows:
            ref = f"epi_row_{entry_id}"
            record = self._verify_one(
                table="episodic",
                row_id=entry_id,
                enc=enc,
                digest_col=digest_col,
                builder=lambda payload: EpisodicRunArtifact(**payload),
                identity=lambda rec: rec.entry_id == entry_id,
                refusal_prefix=ref,
                refusals=refusals,
            )
            if record is None:
                mismatched.append(entry_id)
                continue
            entries.append(record)  # type: ignore[arg-type]
            epi_digests[entry_id] = digest_col
        lessons: list[SemanticLesson] = []
        les_digests: dict[tuple[str, int], str] = {}
        for lesson_id, version, digest_col, enc in les_rows:
            ref = f"lesson_row_{lesson_id}:v{version}"
            record = self._verify_one(
                table="lessons",
                row_id=f"{lesson_id}:{version}",
                enc=enc,
                digest_col=digest_col,
                builder=lambda payload: SemanticLesson(**payload),
                identity=lambda rec: rec.lesson_id == lesson_id
                and rec.version == version,
                refusal_prefix=ref,
                refusals=refusals,
            )
            if record is None:
                continue
            lessons.append(record)  # type: ignore[arg-type]
            les_digests[(lesson_id, version)] = digest_col
        return refusals, entries, epi_digests, lessons, les_digests, mismatched

    def _verify_one(
        self,
        *,
        table: str,
        row_id: str,
        enc: bytes,
        digest_col: str,
        builder: Callable[[dict[str, Any]], Any],
        identity: Callable[[Any], bool],
        refusal_prefix: str,
        refusals: list[str],
    ) -> Any | None:
        """One row's decrypt → digest → contract pipeline (fail-closed).

        Mirrors the JSONL reference's per-line discipline: digest first,
        then JSON parse, then contract re-validation, then an identity
        cross-check against the row's own key columns.
        """
        try:
            plaintext = self._decrypt(table, row_id, enc)
        except (InvalidTag, ValueError, TypeError):
            refusals.append(f"{refusal_prefix}_decrypt_failed")
            return None
        try:
            text = plaintext.decode("utf-8")
        except UnicodeDecodeError:
            refusals.append(f"{refusal_prefix}_undecodable")
            return None
        if sha256_hex(text) != digest_col:
            refusals.append(f"{refusal_prefix}_digest_mismatch")
            return None
        try:
            payload = json.loads(text)
            record = builder(payload)
        except Exception:
            refusals.append(f"{refusal_prefix}_contract_invalid")
            return None
        if not identity(record):
            refusals.append(f"{refusal_prefix}_identity_mismatch")
            return None
        return record

    # -- strict load (fail-closed reopen) ----------------------------------------

    def _load_existing(self) -> None:
        """Rebuild contract state from the carrier, refusing every row that
        is not cryptographically AND contractually verifiable. The verified
        prefix commits into the views; refusals are permanent evidence
        (rows never rewritten) and close the write gate."""
        try:
            conn = self._connect()
            try:
                self._ensure_schema(conn)
                epi_rows = conn.execute(
                    "SELECT entry_id, digest, enc FROM episodic ORDER BY rowid"
                ).fetchall()
                les_rows = conn.execute(
                    "SELECT lesson_id, version, digest, enc FROM lessons ORDER BY rowid"
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            self._close_gate(("db_unreadable",))
            return
        refusals, entries, _epi_d, lessons, _les_d, _mm = self._verified_rows(
            epi_rows, les_rows
        )
        if refusals:
            self._close_gate(tuple(refusals))
        self._epi_archive = EpisodicRunArchive(tuple(entries))
        self._lesson_store = SemanticLessonStore(tuple(lessons))
        self._view = InMemoryResearchMemoryStore(
            archive=self._epi_archive, lessons=self._lesson_store
        )

    # -- Protocol surface (append/get/index/verify ONLY) --------------------------

    def append_episodic(self, entry: EpisodicRunArtifact) -> None:
        """Contract pre-check first (idempotent no-op / conflict refusal,
        both BEFORE any I/O), then encrypted row INSERT committed per append
        (D1 durability), then state commit (all-or-nothing)."""
        self._require_file_ok()
        with self._write_lock:  # single-writer discipline (D6); belt-and-braces
            next_state = self._epi_archive.append(entry)  # contract validation
            if next_state is self._epi_archive:
                return  # identical re-append: idempotent, nothing written
            canonical = canonical_research_memory_json(entry)
            enc = self._encrypt(
                "episodic", entry.entry_id, canonical.encode("utf-8")
            )
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO episodic(entry_id, digest, enc) VALUES (?, ?, ?)",
                    (entry.entry_id, sha256_hex(canonical), enc),
                )
                conn.commit()  # durability over speed for evidence
            finally:
                conn.close()
            self._epi_archive = next_state  # commit last (all-or-nothing)
        self._view = InMemoryResearchMemoryStore(
            archive=self._epi_archive, lessons=self._lesson_store
        )

    def get_episodic(self, entry_id: str) -> EpisodicRunArtifact | None:
        return self._view.get_episodic(entry_id)

    def episodic_for_run(self, run_id: str) -> tuple[EpisodicRunArtifact, ...]:
        return self._view.episodic_for_run(run_id)

    def episodic_for_hypothesis(
        self, hypothesis_id: str
    ) -> tuple[EpisodicRunArtifact, ...]:
        return self._view.episodic_for_hypothesis(hypothesis_id)

    def episodic_available_at(
        self, cutoff: datetime
    ) -> tuple[EpisodicRunArtifact, ...]:
        return self._view.episodic_available_at(cutoff)

    def register_lesson(self, lesson: SemanticLesson) -> None:
        """Contract chain guards first (refusals before any I/O), then
        encrypted row INSERT committed per append, then state commit. Every
        successful register is a NEW version row (history never rewritten)."""
        self._require_file_ok()
        with self._write_lock:
            next_state = self._lesson_store.register(lesson)  # contract guards
            canonical = canonical_research_memory_json(lesson)
            enc = self._encrypt(
                "lessons",
                f"{lesson.lesson_id}:{lesson.version}",
                canonical.encode("utf-8"),
            )
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO lessons(lesson_id, version, digest, enc)"
                    " VALUES (?, ?, ?, ?)",
                    (lesson.lesson_id, lesson.version, sha256_hex(canonical), enc),
                )
                conn.commit()  # durability over speed for evidence
            finally:
                conn.close()
            self._lesson_store = next_state  # commit last (all-or-nothing)
        self._view = InMemoryResearchMemoryStore(
            archive=self._epi_archive, lessons=self._lesson_store
        )

    def latest_lesson(self, lesson_id: str) -> SemanticLesson | None:
        return self._view.latest_lesson(lesson_id)

    def lesson_history(self, lesson_id: str) -> tuple[SemanticLesson, ...]:
        return self._view.lesson_history(lesson_id)

    def lessons_active_at(self, cutoff: datetime) -> tuple[SemanticLesson, ...]:
        return self._view.lessons_active_at(cutoff)

    # -- integrity -----------------------------------------------------------------

    def integrity_report(self) -> ResearchMemoryIntegrityReport:
        """Frozen integrity report: the delegated in-memory view's report,
        cross-verified against a fresh decrypt + digest re-read of every
        disk row (so external tampering between operations is caught at the
        next observation), via domain ``verify_integrity`` over the verified
        row digests, plus a (lesson_id, version) key-set match between view
        and rows. Healthy stores return the view's report byte-identical to
        the in-memory reference. ANY detected divergence closes the write
        gate permanently and is reported as ``verify_ok=False`` with the
        mismatched episodic entry ids and machine-readable refusal reasons;
        the corrupt rows are never deleted, repaired or healed."""
        base = self._view.integrity_report()
        try:
            conn = self._connect()
            try:
                epi_rows = conn.execute(
                    "SELECT entry_id, digest, enc FROM episodic ORDER BY rowid"
                ).fetchall()
                les_rows = conn.execute(
                    "SELECT lesson_id, version, digest, enc FROM lessons ORDER BY rowid"
                ).fetchall()
            finally:
                conn.close()
            row_refusals, _entries, epi_digests, _lessons, les_digests, mismatched = (
                self._verified_rows(epi_rows, les_rows)
            )
        except sqlite3.DatabaseError:
            self._close_gate(("db_unreadable_at_report",))
            return ResearchMemoryIntegrityReport(
                verify_ok=False,
                entry_count=base.entry_count,
                entry_digests=base.entry_digests,
                lesson_version_counts=base.lesson_version_counts,
                refusal_reasons=("db_unreadable_at_report",),
            )
        reasons: set[str] = set(row_refusals) | set(self._refusal_reasons)
        cross = verify_integrity(self._view, epi_digests)
        reasons.update(cross.refusal_reasons)
        view_lesson_keys = {(l.lesson_id, l.version) for l in self._lesson_store.lessons}
        if view_lesson_keys != set(les_digests):
            reasons.add("lesson_view_row_divergence")
        if reasons or mismatched:
            self._close_gate(tuple(reasons))
            return ResearchMemoryIntegrityReport(
                verify_ok=False,
                entry_count=base.entry_count,
                entry_digests=base.entry_digests,
                lesson_version_counts=base.lesson_version_counts,
                mismatched_entry_ids=tuple(sorted(set(mismatched))),
                missing_entry_ids=cross.missing_entry_ids,
                refusal_reasons=tuple(sorted(reasons)),
            )
        return base

    # -- backup / restore (D5 + D7) -------------------------------------------------

    def backup(self, destination_dir: str | Path, *, keep: int = 14) -> Path:
        """WAL-consistent snapshot via the SQLite backup API (D5).

        Writes ``<destination_dir>/research-memory-<UTC stamp>.sqlite`` —
        a fully self-contained single-file snapshot (converted to a plain
        rollback-journal file at backup time so it opens read-only anywhere
        with no side files) — plus a ``<name>.sha256`` sidecar over the
        snapshot bytes (``sha256sum`` format). Returns the snapshot path.

        ROTATION IS OVER BACKUP FILES ONLY: the oldest snapshot files (and
        their sidecars) beyond ``keep`` are removed from the destination
        directory. This is backup-set maintenance per D5 — it is NOT a purge
        of the live store: the live store has no delete, no expiry and no
        retention path whatsoever (D3 ``RETENTION_POLICY``; episodic
        evidence is immutable and nothing expires out of the archive). The
        UTC stamp names the FILE only; record semantics remain clock-free.

        Operational-layer note (D5 cadence is daily): this method performs
        one snapshot per call; scheduling is the operator's concern. The
        snapshot may be taken even while the write gate is closed (a
        forensic snapshot of suspect evidence is legitimate; the gate governs
        record appends, and ``verify_backup`` is the fail-closed verifier).
        """
        if keep < 1:
            raise ValueError("backup_keep_must_be_at_least_one")
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = dest / f"research-memory-{stamp}.sqlite"
        with self._write_lock:  # consistent snapshot under single-writer (D6)
            src = self._connect()
            try:
                dst = sqlite3.connect(str(target))
                try:
                    src.backup(dst)
                    dst.execute("PRAGMA journal_mode=DELETE")
                    dst.commit()
                finally:
                    dst.close()
            finally:
                src.close()
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        sidecar = target.with_name(target.name + ".sha256")
        with open(sidecar, "w", encoding="ascii") as handle:
            handle.write(f"{digest}  {target.name}\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Backup-file rotation ONLY (see docstring): never the live store.
        snapshots = sorted(dest.glob("research-memory-*.sqlite"))
        for old in snapshots[:-keep]:
            try:
                old.unlink()
            except OSError:
                pass  # rotation is best-effort maintenance, never evidence loss
            try:
                old.with_name(old.name + ".sha256").unlink()
            except OSError:
                pass
        return target

    @classmethod
    def verify_backup(
        cls, path: str | Path, *, key_provider: Callable[[], bytes]
    ) -> ResearchMemoryIntegrityReport:
        """Fail-closed verification of a backup snapshot (D7 drill support).

        Opens the snapshot READ-ONLY (no schema bootstrap, no meta writes,
        nothing mutated), rebuilds the contract views from the decrypted
        rows, and returns the domain ``verify_integrity`` refusal record
        merged with any per-row verification refusals. Never raises: any
        unexpected failure becomes a ``verify_ok=False`` report. A wrong key
        fails every row's decryption and is reported, never guessed around.
        """
        try:
            key = _validated_key(key_provider())
            snapshot = Path(path)
            if not snapshot.is_file():
                return ResearchMemoryIntegrityReport(
                    verify_ok=False,
                    refusal_reasons=("backup_file_missing",),
                )
            aead = AESGCM(key)
            uri = snapshot.resolve().as_uri() + "?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            try:
                epi_rows = conn.execute(
                    "SELECT entry_id, digest, enc FROM episodic ORDER BY rowid"
                ).fetchall()
                les_rows = conn.execute(
                    "SELECT lesson_id, version, digest, enc FROM lessons ORDER BY rowid"
                ).fetchall()
            finally:
                conn.close()
            refusals: list[str] = []
            mismatched: list[str] = []
            entries: list[EpisodicRunArtifact] = []
            epi_digests: dict[str, str] = {}
            for entry_id, digest_col, enc in epi_rows:
                record = _verify_one_with(
                    aead,
                    table="episodic",
                    row_id=entry_id,
                    enc=enc,
                    digest_col=digest_col,
                    builder=lambda payload: EpisodicRunArtifact(**payload),
                    identity=lambda rec, eid=entry_id: rec.entry_id == eid,
                    refusal_prefix=f"epi_row_{entry_id}",
                    refusals=refusals,
                )
                if record is None:
                    mismatched.append(entry_id)
                    continue
                entries.append(record)
                epi_digests[entry_id] = digest_col
            lessons: list[SemanticLesson] = []
            for lesson_id, version, digest_col, enc in les_rows:
                record = _verify_one_with(
                    aead,
                    table="lessons",
                    row_id=f"{lesson_id}:{version}",
                    enc=enc,
                    digest_col=digest_col,
                    builder=lambda payload: SemanticLesson(**payload),
                    identity=lambda rec, lid=lesson_id, ver=version: (
                        rec.lesson_id == lid and rec.version == ver
                    ),
                    refusal_prefix=f"lesson_row_{lesson_id}:v{version}",
                    refusals=refusals,
                )
                if record is not None:
                    lessons.append(record)
            view = InMemoryResearchMemoryStore(
                archive=EpisodicRunArchive(tuple(entries)),
                lessons=SemanticLessonStore(tuple(lessons)),
            )
            cross = verify_integrity(view, epi_digests)
            reasons = sorted(set(refusals) | set(cross.refusal_reasons))
            return ResearchMemoryIntegrityReport(
                verify_ok=not reasons and not mismatched and not cross.missing_entry_ids,
                entry_count=cross.entry_count,
                entry_digests=cross.entry_digests,
                lesson_version_counts=view.integrity_report().lesson_version_counts,
                mismatched_entry_ids=tuple(
                    sorted(set(mismatched) | set(cross.mismatched_entry_ids))
                ),
                missing_entry_ids=cross.missing_entry_ids,
                refusal_reasons=tuple(reasons),
            )
        except Exception as exc:  # fail-closed refusal — never a raw exception
            return ResearchMemoryIntegrityReport(
                verify_ok=False,
                refusal_reasons=(f"verify_refused:{type(exc).__name__}",),
            )


def _verify_one_with(
    aead: AESGCM,
    *,
    table: str,
    row_id: str,
    enc: bytes,
    digest_col: str,
    builder: Callable[[dict[str, Any]], Any],
    identity: Callable[[Any], bool],
    refusal_prefix: str,
    refusals: list[str],
) -> Any | None:
    """Standalone one-row decrypt → digest → contract pipeline for
    ``verify_backup`` (same discipline as the instance method; the snapshot
    is verified against a caller-supplied key without a store instance)."""
    try:
        plaintext = aead.decrypt(
            enc[:_NONCE_BYTES],
            enc[_NONCE_BYTES:],
            f"{table}:{row_id}".encode("utf-8"),
        )
    except (InvalidTag, ValueError, TypeError):
        refusals.append(f"{refusal_prefix}_decrypt_failed")
        return None
    try:
        text = plaintext.decode("utf-8")
    except UnicodeDecodeError:
        refusals.append(f"{refusal_prefix}_undecodable")
        return None
    if sha256_hex(text) != digest_col:
        refusals.append(f"{refusal_prefix}_digest_mismatch")
        return None
    try:
        record = builder(json.loads(text))
    except Exception:
        refusals.append(f"{refusal_prefix}_contract_invalid")
        return None
    if not identity(record):
        refusals.append(f"{refusal_prefix}_identity_mismatch")
        return None
    return record


# -- owner-activated backup trigger CLI (D5 manual path; R-6-compatible) ------

def _cli(argv: list[str] | None = None) -> int:
    """Owner-activated research-memory backup/verify trigger — DORMANT until
    invoked.

    R-6 keeps every in-app scheduler dormant and manual-trigger-only, and no
    runtime caller exists for this adapter (verified: zero importers outside
    tests). This CLI IS the manual trigger: the owner runs it (or an
    owner-issued OS-level scheduled task on the OWNER machine runs it —
    exactly the "separate dated owner act on the owner machine" R-6 names).
    Nothing in the application runtime ever calls this; it cannot activate
    itself; there is no plaintext fallback and no external transmission —
    the snapshot lands in a local directory only (D5).

    Usage:
      python -m app.data.research_memory_sqlite backup \\
          --directory <store dir> --dest <backup dir> [--keep 14]
      python -m app.data.research_memory_sqlite verify-backup --path <snapshot>

    The key is resolved exactly like the runtime (fail-closed): env override
    ``RADAR_RESEARCH_MEMORY_KEY`` or the OS keyring; a missing/invalid key
    refuses with exit code 2 and never falls back to plaintext (D4).
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m app.data.research_memory_sqlite",
        description=(
            "AI-3 research-memory backup trigger (owner-activated; D5/D7; "
            "dormant until invoked — R-6)"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_bak = sub.add_parser(
        "backup", help="take a WAL-consistent local backup snapshot (keep=N)"
    )
    p_bak.add_argument("--directory", required=True,
                       help="store directory containing the research-memory DB")
    p_bak.add_argument("--dest", required=True,
                       help="backup destination directory (local only)")
    p_bak.add_argument("--keep", type=int, default=14,
                       help="rotation count of backup FILES (D5 keep=14)")
    p_ver = sub.add_parser(
        "verify-backup", help="fail-closed verification of a snapshot (D7)"
    )
    p_ver.add_argument("--path", required=True, help="snapshot file path")
    args = parser.parse_args(argv)
    try:
        key_provider = select_key_provider()
        if args.command == "backup":
            store = SqliteWalResearchMemoryStore(
                directory=args.directory, key_provider=key_provider
            )
            out = store.backup(args.dest, keep=args.keep)
            print(f"backup OK: {out}")
            return 0
        report = SqliteWalResearchMemoryStore.verify_backup(
            args.path, key_provider=key_provider
        )
        refusals = tuple(getattr(report, "refusal_reasons", ()) or ())
        if refusals:  # the report is fail-closed evidence — exit honestly
            print(
                f"FAILED: backup verification refusals: {refusals}",
                file=sys.stderr,
            )
            return 2
        print(f"verify-backup OK: {report}")
        return 0
    except Exception as exc:  # fail-closed refusal → honest non-zero exit
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess tests
    raise SystemExit(_cli())
