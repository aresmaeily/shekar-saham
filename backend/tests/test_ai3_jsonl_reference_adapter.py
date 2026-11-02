"""AI-3 reference-adapter migration / round-trip tests (RT-1 .. RT-8).

Owner directive §5 WS-D (2026-11-02): "Prepare backend adapters and
migration tests only to the extent allowed by the approved architecture and
owner decisions." These tests pin the migration-relevant behavior of the
TEST-LAYER-ONLY ``JsonlFileResearchMemoryStore`` pluggability proof:

- RT-1  in-memory → canonical JSONL → rebuild: byte-identical records, all
        PIT views identical, integrity report identical, delegation honesty.
- RT-2  tamper one data/sidecar byte → fail-closed: the line is refused,
        never fabricated into a record; further appends refuse;
        file bytes unchanged by the refused append.
- RT-3  crash-partial last line (no newline) → ignored AS A RECORD, refused
        IN VERIFICATION; verified prefix fully present; appends refuse;
        file never rewritten.
- RT-4  two-thread concurrent append under the documented single-writer
        discipline → file-level invariants (line parity, per-writer order,
        sidecar verification) and byte-identical reopen.
- RT-5  reopen over the SAME directory → every record byte-identical,
        digest-clean, PIT views identical.
- RT-6  zero production wiring: test-layer placement, no ``app.core`` /
        ``app.data`` import, no production-namespace registration,
        TEST-LAYER-ONLY disclaimer present.
- RT-7  scaffold factory-contract conformance BEFORE registration semantics:
        Protocol-conformant, exact public surface, no forbidden mutation
        tokens, fresh-empty per call.
- RT-8  refusal records and appends are file-atomic: idempotent re-append
        and conflict refusal leave BOTH files byte-identical.

DEVIATION NOTE (honest, stricter than the design draft): a digest-verified
line whose payload fails contract re-validation, a digest-mismatched line,
and a torn tail are all REFUSED — the refusing store reports
``verify_ok=False`` and REFUSES FURTHER APPENDS (``file_integrity_unverified``).
Consequently any ``verify_integrity`` over a refusing store also returns
``verify_ok=False`` (the refusal propagates — fail-closed by design).

Governance: D1–D7 ALL PENDING (decision packet lines 3–6); this module
exercises NO owner decision and implements NO production persistence.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import pytest

from app.domain.research_memory import (
    EpisodicRunArchive,
    EpisodicRunArtifact,
    SemanticLesson,
)
from app.domain.research_memory_store import (
    ResearchMemoryStore,
    canonical_research_memory_json,
    sha256_hex,
    verify_integrity,
)
from helpers_research_memory_fixtures import (
    T1,
    T2,
    T3,
    make_episodic_entry,
    make_lesson,
)
from research_memory_jsonl_reference import (
    JsonlFileResearchMemoryStore,
    _jsonl_file_reference_factory,
)

_DATA_NAME = "episodic_records.jsonl"
_SIDECAR_NAME = "episodic_records.sha256"


def _file_bytes(directory: Path, name: str) -> bytes:
    path = directory / name
    return path.read_bytes() if path.exists() else b""


def _dir_digest(directory: Path) -> str:
    """Digest over both carrier files' bytes (tamper-evidence for 'unchanged')."""
    blob = _file_bytes(directory, _DATA_NAME) + _file_bytes(directory, _SIDECAR_NAME)
    return hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------
# RT-1 — round-trip byte-identity + PIT identity + delegation honesty
# ---------------------------------------------------------------------------


def test_rt1_roundtrip_inmemory_to_jsonl_rebuild_byte_identical_and_pit_identical(
    tmp_path: Path,
) -> None:
    from app.domain.research_memory_store import InMemoryResearchMemoryStore

    original = InMemoryResearchMemoryStore()
    e1 = make_episodic_entry("ra-1", recorded_at_utc=T1)
    e2 = make_episodic_entry("ra-2", run_id="run-r2", hypothesis_id=None,
                             recorded_at_utc=T2, notes="µ € 😀 evidence")
    e3 = make_episodic_entry("ra-3", run_id="run-r2", recorded_at_utc=T2)
    for entry in (e1, e2, e3):
        original.append_episodic(entry)
    original.register_lesson(make_lesson(lesson_id="l1", created_at_utc=T1))
    original.register_lesson(
        make_lesson(lesson_id="l1", version=2, supersedes_version=1,
                    created_at_utc=T2)
    )
    original.register_lesson(
        make_lesson(lesson_id="l2", source_artifact_ids=("ra-2",),
                    created_at_utc=T2)
    )

    directory = tmp_path / "roundtrip"
    JsonlFileResearchMemoryStore._export_records_to_directory(
        directory,
        original._archive.entries,  # noqa: SLF001 — test-layer format authority
        original._lessons.lessons,  # noqa: SLF001
    )
    rebuilt = JsonlFileResearchMemoryStore(directory=directory)

    # Byte identity + value identity for EVERY episodic record.
    for entry in (e1, e2, e3):
        got = rebuilt.get_episodic(entry.entry_id)
        assert got == entry
        assert canonical_research_memory_json(got) == canonical_research_memory_json(
            entry
        )
    # All PIT cutoffs identical (T0 boundary is empty by fixture design).
    for cutoff in (T1, T2, T3):
        assert rebuilt.episodic_available_at(cutoff) == original.episodic_available_at(
            cutoff
        )
    assert rebuilt.episodic_for_run("run-r2") == original.episodic_for_run("run-r2")
    assert rebuilt.episodic_for_hypothesis("hyp-1") == original.episodic_for_hypothesis(
        "hyp-1"
    )
    # Lessons: history, latest, PIT actives identical.
    assert rebuilt.lesson_history("l1") == original.lesson_history("l1")
    assert rebuilt.lesson_history("l2") == original.lesson_history("l2")
    assert rebuilt.latest_lesson("l1") == original.latest_lesson("l1")
    for cutoff in (T1, T2, T3):
        assert rebuilt.lessons_active_at(cutoff) == original.lessons_active_at(cutoff)
    # Integrity report equality (frozen-record value equality).
    assert rebuilt.integrity_report() == original.integrity_report()
    # Delegation honesty (AC-15 analog): the contract archive built from the
    # store's own view answers exactly as the store does.
    archive = EpisodicRunArchive(rebuilt.episodic_available_at(T3))
    assert archive.get("ra-2") == rebuilt.get_episodic("ra-2")
    assert archive.available_at(T1) == rebuilt.episodic_available_at(T1)
    assert all(isinstance(e, EpisodicRunArtifact) for e in archive.entries)
    assert all(isinstance(l, SemanticLesson) for l in rebuilt.lesson_history("l1"))


# ---------------------------------------------------------------------------
# RT-2 — tamper detection: fail-closed refusal, nothing fabricated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tamper_sidecar", [False, True], ids=["data", "sidecar"])
def test_rt2_tamper_one_byte_verify_fails_closed_refusal_record(
    tmp_path: Path, tamper_sidecar: bool
) -> None:
    directory = tmp_path / "tamper"
    store = JsonlFileResearchMemoryStore(directory=directory)
    store.append_episodic(make_episodic_entry("ra-1", recorded_at_utc=T1))
    store.append_episodic(make_episodic_entry("ra-2", run_id="run-r2",
                                              recorded_at_utc=T2))
    expected = dict(store.integrity_report().entry_digests)
    del store  # drop the writer; reopen from the carrier

    data = bytearray(_file_bytes(directory, _DATA_NAME))
    assert data.count(b"\n") == 2
    if tamper_sidecar:
        side = bytearray(_file_bytes(directory, _SIDECAR_NAME))
        # Flip the LAST hex char of the second sidecar line's digest.
        tail_index = len(side) - 2  # skip trailing newline
        side[tail_index] = ord("0") if side[tail_index] != ord("0") else ord("1")
        (directory / _SIDECAR_NAME).write_bytes(bytes(side))
    else:
        # Flip one byte in the middle of line 2's raw JSON text.
        first_line_end = data.index(b"\n")
        second_line_start = first_line_end + 1
        mid = second_line_start + (len(data) - second_line_start) // 2
        data[mid] = data[mid] ^ 0x01  # flip one bit — canonical bytes broken
        (directory / _DATA_NAME).write_bytes(bytes(data))

    reopened = JsonlFileResearchMemoryStore(directory=directory)
    report = reopened.integrity_report()
    assert report.verify_ok is False
    assert any(
        reason.endswith("_digest_mismatch") or reason.endswith("_unverified")
        for reason in report.refusal_reasons
    )
    # The un-tampered record remains intact and digest-clean.
    assert ("ra-1", expected["ra-1"]) in report.entry_digests
    assert reopened.get_episodic("ra-1") is not None
    # The tampered line NEVER becomes a record (no fabrication).
    assert reopened.get_episodic("ra-2") is None
    assert reopened.episodic_for_run("run-r2") == ()
    # Fail-closed write policy: further appends refuse before any I/O.
    before = _dir_digest(directory)
    with pytest.raises(ValueError, match="file_integrity_unverified"):
        reopened.append_episodic(make_episodic_entry("ra-3", recorded_at_utc=T2))
    assert _dir_digest(directory) == before  # file untouched by the refusal
    # Verification never raises raw exceptions; refusal propagates.
    result = verify_integrity(reopened, expected)
    assert result.verify_ok is False
    assert result.missing_entry_ids == ("ra-2",) or result.mismatched_entry_ids == (
        "ra-2",
    )


# ---------------------------------------------------------------------------
# RT-3 — crash-partial last line: ignored as record, refused in verification
# ---------------------------------------------------------------------------


def test_rt3_crash_partial_last_line_ignored_as_record_and_refused_in_verification(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "crash"
    store = JsonlFileResearchMemoryStore(directory=directory)
    ra1 = make_episodic_entry("ra-1", recorded_at_utc=T1)
    ra2 = make_episodic_entry("ra-2", run_id="run-r2", recorded_at_utc=T2)
    store.append_episodic(ra1)
    store.append_episodic(ra2)
    expected_two = dict(store.integrity_report().entry_digests)
    del store

    # Simulate a killed writer: HALF of a valid canonical line for a third
    # entry, no trailing newline, no sidecar line — the exact observable of
    # a crash between the data append and its fsync.
    partial = canonical_research_memory_json(
        make_episodic_entry("ra-3", run_id="run-crash", recorded_at_utc=T2)
    )[:40].encode("utf-8")
    with open(directory / _DATA_NAME, "ab") as handle:
        handle.write(partial)  # NO newline → torn tail

    reopened = JsonlFileResearchMemoryStore(directory=directory)
    # Committed records fully present and byte-identical.
    assert reopened.get_episodic("ra-1") == ra1
    assert reopened.get_episodic("ra-2") == ra2
    assert canonical_research_memory_json(reopened.get_episodic("ra-1")) == (
        canonical_research_memory_json(ra1)
    )
    # The partial line yields NO record — no partial record accepted, none
    # fabricated (all-or-nothing).
    assert reopened.get_episodic("ra-3") is None
    assert reopened.episodic_for_run("run-crash") == ()
    # Verification REFUSES: torn tail is permanent evidence.
    report = reopened.integrity_report()
    assert report.verify_ok is False
    assert "torn_tail_detected" in report.refusal_reasons
    result = verify_integrity(reopened, expected_two)
    assert result.verify_ok is False  # refusal propagates (fail-closed)
    assert "store_report_not_ok" in result.refusal_reasons
    # Committed records still digest-identical to expectation.
    assert result.missing_entry_ids == () and result.mismatched_entry_ids == ()
    # Append-only preservation: the reopen did NOT rewrite or truncate bytes.
    raw = _file_bytes(directory, _DATA_NAME)
    assert raw.endswith(partial)  # torn bytes remain exactly as written
    assert raw.count(b"\n") == 2
    # Fail-closed write policy on the refusing store.
    before = _dir_digest(directory)
    with pytest.raises(ValueError, match="file_integrity_unverified"):
        reopened.append_episodic(make_episodic_entry("ra-4", recorded_at_utc=T2))
    assert _dir_digest(directory) == before


# ---------------------------------------------------------------------------
# RT-4 — two-thread concurrent append: file-level single-writer invariants
# ---------------------------------------------------------------------------


def test_rt4_two_thread_concurrent_append_file_level_single_writer_discipline(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "concurrent"
    store = JsonlFileResearchMemoryStore(directory=directory)
    lock = threading.Lock()
    per_thread = 20
    errors: list[Exception] = []

    def _append_all(prefix: str, at_utc: object) -> None:
        for i in range(per_thread):
            try:
                with lock:  # documented single-writer discipline boundary
                    store.append_episodic(
                        make_episodic_entry(
                            f"ra-{prefix}-{i}",
                            run_id=f"run-{prefix}",
                            recorded_at_utc=at_utc,  # type: ignore[arg-type]
                        )
                    )
            except Exception as exc:  # surfaced below — never swallowed
                errors.append(exc)

    threads = (
        threading.Thread(target=_append_all, args=("A", T1), name="writer-A"),
        threading.Thread(target=_append_all, args=("B", T2), name="writer-B"),
    )
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []

    data = _file_bytes(directory, _DATA_NAME)
    side = _file_bytes(directory, _SIDECAR_NAME).decode("ascii")
    lines = data.split(b"\n")[:-1]
    side_entries = [line.split("\t") for line in side.splitlines()]
    # File-level invariant: data/sidecar line parity, per-line digest match.
    assert len(lines) == len(side_entries) == 2 * per_thread
    for index, line_bytes in enumerate(lines):
        index_text, digest = side_entries[index]
        assert int(index_text) == index
        assert sha256_hex(line_bytes.decode("utf-8")) == digest
    # Per-writer submission order preserved ON DISK.
    ids_in_file = [json.loads(line.decode("utf-8"))["entry_id"] for line in lines]
    a_positions = [i for i, eid in enumerate(ids_in_file) if eid.startswith("ra-A-")]
    b_positions = [i for i, eid in enumerate(ids_in_file) if eid.startswith("ra-B-")]
    assert [int(ids_in_file[i].rsplit("-", 1)[1]) for i in a_positions] == list(
        range(per_thread)
    )
    assert [int(ids_in_file[i].rsplit("-", 1)[1]) for i in b_positions] == list(
        range(per_thread)
    )
    # Reopen over the SAME directory: every record byte-identical, digest-clean.
    expected = {
        f"ra-{p}-{i}": sha256_hex(
            canonical_research_memory_json(
                make_episodic_entry(
                    f"ra-{p}-{i}", run_id=f"run-{p}",
                    recorded_at_utc=T1 if p == "A" else T2,
                )
            )
        )
        for p in ("A", "B")
        for i in range(per_thread)
    }
    reopened = JsonlFileResearchMemoryStore(directory=directory)
    assert verify_integrity(reopened, expected).verify_ok is True
    assert reopened.integrity_report().entry_count == 2 * per_thread


# ---------------------------------------------------------------------------
# RT-5 — reopen same directory: byte-identical records, digest-clean
# ---------------------------------------------------------------------------


def test_rt5_reopen_same_directory_all_records_digest_clean(tmp_path: Path) -> None:
    directory = tmp_path / "reopen"
    store = JsonlFileResearchMemoryStore(directory=directory)
    entries = (
        make_episodic_entry("ra-1", recorded_at_utc=T1),
        make_episodic_entry("ra-2", run_id="run-r2", recorded_at_utc=T2,
                            notes="persisted verbatim"),
        make_episodic_entry("ra-3", run_id="run-r2", hypothesis_id=None,
                            recorded_at_utc=T2),
    )
    for entry in entries:
        store.append_episodic(entry)
    store.register_lesson(make_lesson(lesson_id="l1", created_at_utc=T1))
    expected = dict(store.integrity_report().entry_digests)
    del store

    reopened = JsonlFileResearchMemoryStore(directory=directory)
    for entry in entries:
        got = reopened.get_episodic(entry.entry_id)
        assert got == entry
        assert canonical_research_memory_json(got) == canonical_research_memory_json(
            entry
        )
    assert dict(reopened.integrity_report().entry_digests) == expected
    assert verify_integrity(reopened, expected).verify_ok is True
    assert reopened.latest_lesson("l1") is not None
    for cutoff in (T1, T2, T3):
        assert reopened.episodic_available_at(cutoff) == tuple(
            e for e in entries if e.recorded_at_utc <= cutoff
        )


# ---------------------------------------------------------------------------
# RT-6 — zero production wiring (test-layer placement proof)
# ---------------------------------------------------------------------------


def test_rt6_reference_adapter_is_test_layer_only_zero_production_wiring() -> None:
    import research_memory_jsonl_reference as adapter_module
    import app.domain.research_memory_store as production_module

    adapter_path = Path(adapter_module.__file__).resolve()
    tests_dir = Path(__file__).resolve().parent
    assert tests_dir in adapter_path.parents or adapter_path.parent == tests_dir
    assert "app" not in adapter_path.relative_to(tests_dir).parts
    # Nothing registered into the production module namespace.
    assert not hasattr(production_module, "JsonlFileResearchMemoryStore")
    # No config-surface or data-layer import in the adapter source: AST-level
    # import scan (immune to prose mentions in the docstring). The ONLY
    # permitted ``app.*`` import roots are ``app.domain.*`` — the delivered
    # contract pair the adapter must wrap (never replace). ``app.core``,
    # ``app.data``, ``app.api`` and ``app.services`` are structurally
    # forbidden, as is any other ``app.*`` subtree.
    import ast as _ast

    tree = _ast.parse(adapter_path.read_text(encoding="utf-8"))
    import_roots: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                import_roots.add(alias.name.split(".")[0])
        elif isinstance(node, _ast.ImportFrom) and node.module:
            import_roots.add(node.module.split(".")[0])
    assert "app" in import_roots, "adapter must wrap the delivered app.domain contracts"
    app_submodules: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ImportFrom) and node.module and node.module.startswith("app."):
            app_submodules.add(node.module.split(".")[1])
        elif isinstance(node, _ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if len(parts) >= 2 and parts[0] == "app":
                    app_submodules.add(parts[1])
    assert app_submodules == {"domain"}, (
        f"test-layer adapter must import ONLY app.domain.* contracts; "
        f"found app.{sorted(app_submodules)}"
    )
    for forbidden_root in ("app.core", "app.data", "app.api", "app.services"):
        for node in _ast.walk(tree):
            mods = []
            if isinstance(node, _ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, _ast.Import):
                mods.extend(alias.name for alias in node.names)
            for mod in mods:
                assert not mod.startswith(forbidden_root), (
                    f"production wiring detected: {mod}"
                )
    # The not-a-decision disclaimer is present and explicit.
    source = adapter_path.read_text(encoding="utf-8")
    assert "NOT a persistence-backend decision" in source
    assert "TEST-LAYER ONLY" in source


# ---------------------------------------------------------------------------
# RT-7 — scaffold factory-contract conformance
# ---------------------------------------------------------------------------


def test_rt7_scaffold_factory_entry_conformance() -> None:
    store = _jsonl_file_reference_factory()
    assert isinstance(store, ResearchMemoryStore)
    protocol = getattr(ResearchMemoryStore, "__protocol_attrs__")
    assert set(protocol) <= {n for n in dir(store) if not n.startswith("_")}
    forbidden = (
        "update", "remove", "delete", "purge", "expire", "expiry", "retention",
        "rewrite", "prune", "evict", "clear", "pop", "drop", "truncate", "vacuum",
    )
    public = [n for n in dir(store) if not n.startswith("_")]
    for token in forbidden:
        assert not any(token in name for name in public), token
    # Fresh-empty per call: two factories → two independent, empty, ok stores.
    store_a = _jsonl_file_reference_factory()
    store_b = _jsonl_file_reference_factory()
    for fresh in (store_a, store_b):
        report = fresh.integrity_report()
        assert report.entry_count == 0 and report.verify_ok is True
        assert fresh.get_episodic("ghost") is None  # explicit miss semantics
        assert fresh.episodic_available_at(T3) == ()


# ---------------------------------------------------------------------------
# RT-8 — refusals and appends are file-atomic
# ---------------------------------------------------------------------------


def test_rt8_refusal_records_and_appends_are_file_atomic(tmp_path: Path) -> None:
    directory = tmp_path / "atomic"
    store = JsonlFileResearchMemoryStore(directory=directory)
    entry = make_episodic_entry("ra-1")
    store.append_episodic(entry)
    digest_before = _dir_digest(directory)

    # Identical re-append: idempotent — NOTHING is written.
    store.append_episodic(entry)
    assert _dir_digest(directory) == digest_before
    assert store.integrity_report().entry_count == 1

    # Conflict re-append: contract refusal — file byte-identical.
    with pytest.raises(ValueError, match="episodic_archive_conflict"):
        store.append_episodic(make_episodic_entry("ra-1", trust_state="variant"))
    assert _dir_digest(directory) == digest_before
    assert store.get_episodic("ra-1").trust_state == "live"  # type: ignore[union-attr]
    assert store.integrity_report().entry_digests == (
        ("ra-1", sha256_hex(canonical_research_memory_json(entry))),
    )

    # Lesson chain refusal: a refused register writes NOTHING (contract
    # guards run before any I/O).
    store.register_lesson(make_lesson(lesson_id="l1", created_at_utc=T1))
    lessons_path = directory / "lessons.jsonl"
    assert lessons_path.read_bytes().count(b"\n") == 1
    lessons_digest_before = _dir_digest(directory)
    with pytest.raises(ValueError, match="lesson_version_not_increasing"):
        store.register_lesson(make_lesson(lesson_id="l1", created_at_utc=T1))
    assert _dir_digest(directory) == lessons_digest_before
    assert lessons_path.read_bytes().count(b"\n") == 1
    # A non-increasing first chain attempt on an EMPTY store also refuses
    # before any file is created.
    empty_dir = tmp_path / "atomic_empty"
    empty = JsonlFileResearchMemoryStore(directory=empty_dir)
    with pytest.raises(ValueError, match="first_registered_lesson_version_must_be_one"):
        empty.register_lesson(
            make_lesson(lesson_id="lx", version=2, supersedes_version=1,
                        created_at_utc=T1)
        )
    assert not (empty_dir / "lessons.jsonl").exists()
