"""TEST-LAYER ONLY reference adapter: JSONL file carrier for AI-3 research
memory. Pluggability proof for the ``ResearchMemoryStore`` Protocol — NOT a
production engine, NOT a persistence-backend decision (D1–D7 ALL PENDING,
``docs/active/AI3_PERSISTENCE_DECISION_PACKET.md`` lines 3–6; execution gate
packet §11). Zero production wiring: lives under ``backend/tests/``, imported
by tests only, no ``app.core``/``app.data`` reference, no config surface.

WHY THIS EXISTS (owner directive §5 WS-D, 2026-11-02): "Prepare backend
adapters and migration tests only to the extent allowed by the approved
architecture and owner decisions." The approved architecture requires every
adapter to wrap — never replace — the delivered contracts behind the
append-only ``ResearchMemoryStore`` Protocol; this module proves the
scaffold's plug-in point accepts a second, file-carried implementation so the
owner's D1 reply can be executed directly. It exercises NO owner decision.

ARCHITECTURE (composition-by-delegation, plan I-1; reuse rule 02:107-112):
the sole behavior authority is the delivered contract pair
(``EpisodicRunArchive`` + ``SemanticLessonStore``); the file leg is a
persistence CARRIER only. Every read is pure delegation through an
``InMemoryResearchMemoryStore`` view rebuilt on each commit. Records are
created only by contract validation and re-validated on load.

STORAGE DISCIPLINE (plan §4.1–§4.7):
- canonical JSON lines (``canonical_research_memory_json``), UTF-8, binary
  append mode (no OS newline translation can enter digest scope), fsync per
  line, per-line sha256 sidecar (digest over the canonical text WITHOUT the
  newline framing byte).
- APPEND-ONLY: writes create or refuse; never mutate, truncate, rewrite or
  purge. NO retention-expiry path exists (A3/A11). A torn/corrupt line is
  permanent evidence: it is ignored AS A RECORD and refused IN VERIFICATION;
  the store never heals the file (rollback/repair is owner DR under D5 —
  restoration of prior state, never rewriting).
- FAIL-CLOSED: an unverified store refuses further appends
  (``file_integrity_unverified``) before any I/O; verification refusals are
  returned records, never raised exceptions.
- ALL-OR-NOTHING: the contract pre-check runs BEFORE any I/O (idempotent
  re-append and conflict/chain refusals write nothing); the file append is
  fsync'd before the state commit, so a mid-write crash leaves the record
  absent from the API and the torn bytes refused at the next load.

CONCURRENCY CLASS (plan §4.5): SINGLE-WRITER — all writers must share one
external lock (the scaffold's harness lock); the adapter additionally
serializes its own file writes. No multi-writer guarantee is made anywhere.

Determinism note (documented deviation-with-reason): record semantics are
clock-free/RNG-free; the tmp-dir ACQUISITION is harness infrastructure (same
class as pytest's ``tmp_path``, which plan §3.1 and the decision packet
assume for file-backed adapters) and never touches store content or ordering.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import weakref
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.research_memory import (
    EpisodicRunArchive,
    EpisodicRunArtifact,
    SemanticLesson,
    SemanticLessonStore,
)
from app.domain.research_memory_store import (
    InMemoryResearchMemoryStore,
    ResearchMemoryIntegrityReport,
    ResearchMemoryStore,
    canonical_research_memory_json,
    sha256_hex,
)


class JsonlFileResearchMemoryStore:
    """Append-only JSONL-carried store behind the ``ResearchMemoryStore``
    Protocol. TEST-LAYER ONLY: pluggability proof, NOT a persistence-backend
    decision; zero production wiring (no ``app/`` import, no config surface,
    not wired into any runtime). Single-writer concurrency discipline."""

    _EPISODIC_DATA_NAME = "episodic_records.jsonl"
    _EPISODIC_SIDECAR_NAME = "episodic_records.sha256"
    _LESSONS_DATA_NAME = "lessons.jsonl"
    _LESSONS_SIDECAR_NAME = "lessons.sha256"

    def __init__(self, *, directory: str | Path | None = None) -> None:
        if directory is None:
            root = Path(tempfile.mkdtemp(prefix="ai3_jsonl_ref_"))
            # Self-owned scratch dir: deterministic cleanup when this store
            # becomes unreachable (CPython refcounting) or at interpreter
            # exit. Harness infrastructure only — never store content.
            self._finalizer = weakref.finalize(
                self, shutil.rmtree, root, ignore_errors=True
            )
        else:
            root = Path(directory)
            root.mkdir(parents=True, exist_ok=True)
            self._finalizer = None  # caller-owned directory (round-trip tests)
        self._root = root
        self._append_lock = threading.Lock()
        self._file_ok = True
        self._refusal_reasons: tuple[str, ...] = ()
        self._epi_archive = EpisodicRunArchive()
        self._lesson_store = SemanticLessonStore()
        self._load_existing_files()
        self._view = InMemoryResearchMemoryStore(
            archive=self._epi_archive, lessons=self._lesson_store
        )

    # -- carrier path helpers -------------------------------------------------

    @property
    def _episodic_data_path(self) -> Path:
        return self._root / self._EPISODIC_DATA_NAME

    @property
    def _episodic_sidecar_path(self) -> Path:
        return self._root / self._EPISODIC_SIDECAR_NAME

    @property
    def _lessons_data_path(self) -> Path:
        return self._root / self._LESSONS_DATA_NAME

    @property
    def _lessons_sidecar_path(self) -> Path:
        return self._root / self._LESSONS_SIDECAR_NAME

    # -- canonical line encoding (format authority for this carrier) ----------

    @staticmethod
    def _encode_record(record: Any) -> tuple[bytes, str]:
        """One record's on-disk bytes and its digest: canonical JSON, UTF-8,
        newline framing. The digest scope is the canonical text WITHOUT the
        newline (plan §4.1); binary encoding keeps OS newline translation out
        of digest scope (plan §4.7)."""
        text = canonical_research_memory_json(record)
        return text.encode("utf-8") + b"\n", sha256_hex(text)

    @staticmethod
    def _append_bytes(path: Path, payload: bytes) -> None:
        """Binary append + flush + fsync (crash-observable discipline)."""
        with open(path, "ab") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    @classmethod
    def _append_record(cls, data_path: Path, sidecar_path: Path, record: Any) -> None:
        line_bytes, digest = cls._encode_record(record)
        cls._append_bytes(data_path, line_bytes)
        index = cls._complete_line_count(data_path) - 1
        cls._append_bytes(sidecar_path, f"{index}\t{digest}\n".encode("ascii"))

    @staticmethod
    def _complete_line_count(path: Path) -> int:
        """Number of COMPLETE (newline-terminated) lines; a torn tail is not
        a line."""
        if not path.exists():
            return 0
        raw = path.read_bytes()
        if not raw:
            return 0
        return len(raw.split(b"\n")) - 1

    @classmethod
    def _export_records_to_directory(
        cls,
        directory: Path,
        episodic_records: tuple[EpisodicRunArtifact, ...],
        lesson_records: tuple[SemanticLesson, ...],
    ) -> None:
        """Write canonical data lines + sidecar digests for already-validated
        records (the round-trip export path; module = format authority)."""
        directory.mkdir(parents=True, exist_ok=True)
        epi_data = directory / cls._EPISODIC_DATA_NAME
        epi_side = directory / cls._EPISODIC_SIDECAR_NAME
        les_data = directory / cls._LESSONS_DATA_NAME
        les_side = directory / cls._LESSONS_SIDECAR_NAME
        for record in episodic_records:
            cls._append_record(epi_data, epi_side, record)
        for record in lesson_records:
            cls._append_record(les_data, les_side, record)

    # -- strict load (fail-closed reopen) --------------------------------------

    def _load_existing_files(self) -> None:
        """Rebuild contract state from the carrier, refusing every line that
        is not cryptographically AND contractually verifiable. The verified
        prefix commits; refusals are permanent evidence (never rewritten)."""
        refusals: list[str] = []

        epi_reasons, epi_payloads = self._load_side(
            data_path=self._episodic_data_path,
            sidecar_path=self._episodic_sidecar_path,
            prefix="epi",
        )
        refusals.extend(epi_reasons)
        entries: list[EpisodicRunArtifact] = []
        for line_ref, payload in epi_payloads:
            if payload is None:
                continue
            try:
                entries.append(EpisodicRunArtifact(**payload))
            except Exception:
                refusals.append(f"{line_ref}_contract_invalid")

        les_reasons, les_payloads = self._load_side(
            data_path=self._lessons_data_path,
            sidecar_path=self._lessons_sidecar_path,
            prefix="lesson",
        )
        refusals.extend(les_reasons)
        lessons: list[SemanticLesson] = []
        for line_ref, payload in les_payloads:
            if payload is None:
                continue
            try:
                lessons.append(SemanticLesson(**payload))
            except Exception:
                refusals.append(f"{line_ref}_contract_invalid")

        self._refusal_reasons = tuple(sorted(set(refusals)))
        self._file_ok = not self._refusal_reasons
        self._epi_archive = EpisodicRunArchive(tuple(entries))
        self._lesson_store = SemanticLessonStore(tuple(lessons))

    @staticmethod
    def _load_side(
        *, data_path: Path, sidecar_path: Path, prefix: str
    ) -> tuple[list[str], list[tuple[str, dict[str, Any] | None]]]:
        """Verify one data/sidecar pair; return (refusal_reasons, payloads).

        A complete line is accepted only when its sidecar digest matches AND
        its JSON parses. Failures never raise: they become machine-readable
        refusal reasons and the line yields NO payload (never fabricated into
        a record, never rewritten on disk). Contract re-validation of an
        accepted payload is the caller's step, so a digest-clean but
        contract-invalid line is refused with ``_contract_invalid``.
        """
        refusals: list[str] = []
        payloads: list[tuple[str, dict[str, Any] | None]] = []
        if not data_path.exists():
            return refusals, payloads
        raw = data_path.read_bytes()
        if not raw:
            return refusals, payloads
        fragments = raw.split(b"\n")
        torn_tail = fragments[-1] != b""
        complete = fragments[:-1]  # everything before the last fragment
        sidecar: dict[int, str] = {}
        if sidecar_path.exists():
            for line in sidecar_path.read_bytes().decode(
                "ascii", errors="replace"
            ).splitlines():
                if not line.strip():
                    continue
                try:
                    index_text, digest = line.split("\t", 1)
                    sidecar[int(index_text)] = digest.strip()
                except ValueError:
                    refusals.append(f"{prefix}_sidecar_unparsable")
        for index, line_bytes in enumerate(complete):
            line_ref = f"{prefix}_line_{index}"
            expected_digest = sidecar.get(index)
            if expected_digest is None:
                refusals.append(f"{line_ref}_unverified")
                payloads.append((line_ref, None))
                continue
            try:
                canonical_text = line_bytes.decode("utf-8")
            except UnicodeDecodeError:
                refusals.append(f"{line_ref}_unverified")
                payloads.append((line_ref, None))
                continue
            if sha256_hex(canonical_text) != expected_digest:
                refusals.append(f"{line_ref}_digest_mismatch")
                payloads.append((line_ref, None))
                continue
            try:
                payload = json.loads(canonical_text)
            except Exception:
                refusals.append(f"{line_ref}_unverified")
                payloads.append((line_ref, None))
                continue
            payloads.append((line_ref, payload))
        if torn_tail:
            refusals.append("torn_tail_detected")
        return refusals, payloads

    # -- fail-closed write gate -------------------------------------------------

    def _require_file_ok(self) -> None:
        if not self._file_ok:
            raise ValueError("file_integrity_unverified")

    # -- Protocol surface (append/get/index/verify ONLY) -------------------------

    def append_episodic(self, entry: EpisodicRunArtifact) -> None:
        """Contract pre-check first (idempotent no-op / conflict refusal,
        both BEFORE any I/O), then atomic file append, then state commit."""
        self._require_file_ok()
        with self._append_lock:  # single-writer discipline; belt-and-braces
            next_state = self._epi_archive.append(entry)  # contract validation
            if next_state is self._epi_archive:
                return  # identical re-append: idempotent, nothing written
            self._append_record(
                self._episodic_data_path, self._episodic_sidecar_path, entry
            )
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
        atomic file append, then state commit. Every successful register is
        a NEW version line (history never rewritten)."""
        self._require_file_ok()
        with self._append_lock:
            next_state = self._lesson_store.register(lesson)  # contract guards
            self._append_record(
                self._lessons_data_path, self._lessons_sidecar_path, lesson
            )
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

    # -- integrity ------------------------------------------------------------------

    def integrity_report(self) -> ResearchMemoryIntegrityReport:
        base = self._view.integrity_report()
        if self._file_ok:
            return base  # byte-identical to the in-memory reference report
        return ResearchMemoryIntegrityReport(
            verify_ok=False,
            entry_count=base.entry_count,
            entry_digests=base.entry_digests,
            lesson_version_counts=base.lesson_version_counts,
            refusal_reasons=tuple(
                sorted(set(base.refusal_reasons) | set(self._refusal_reasons))
            ),
        )


def _jsonl_file_reference_factory() -> ResearchMemoryStore:
    """Fresh, EMPTY file-backed reference store in a self-owned tmp dir.

    TEST-LAYER ONLY (pluggability proof, not a decision). Determinism note:
    record semantics are clock-free/RNG-free (fixture-kit discipline); the
    tmp-dir ACQUISITION is harness infrastructure (same class as pytest's
    tmp_path, which plan §3.1 / the decision packet assume) and may read
    TMPDIR — it never touches store content or ordering.
    """
    return JsonlFileResearchMemoryStore()
