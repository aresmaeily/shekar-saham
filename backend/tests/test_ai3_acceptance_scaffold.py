"""AI-3 PERSISTENCE ACCEPTANCE SCAFFOLD — executable acceptance tests that
ANY future persistence adapter must pass (T4, CONSOL-NEXT Wave 1).

STATUS: authorized PRE-DECISION work. Owner decisions D1–D7 are ALL PENDING
(``docs/active/AI3_PERSISTENCE_DECISION_PACKET.md`` line 3: "ALL SEVEN
DECISIONS PENDING — no owner decision recorded as of 2026-11-02; none
assumed"). This suite therefore runs TODAY against the in-memory reference
adapter ONLY (``InMemoryResearchMemoryStore``, which composes — never
reimplements — ``EpisodicRunArchive`` + ``SemanticLessonStore``). No storage
engine is implemented or exercised here; the execution gate (packet §11)
still binds.

WHAT THIS SUITE IS: a parameterized acceptance scaffold over the
``ResearchMemoryStore`` Protocol. The store under test comes from a
module-level factory registry (``STORE_FACTORIES`` below); every Tier A
test runs once per registered factory, so a future adapter is accepted by
adding ONE factory entry — no test body changes. The criteria encoded here
are the store-level acceptance criteria of
``docs/active/AI3_PERSISTENCE_IMPLEMENTATION_PLAN.md`` §5 (Table A, AC-1
through AC-15); each test docstring names its AC id(s).

HOW TO PLUG IN A FUTURE ADAPTER (after D1–D7 are recorded by the owner):
add one entry to ``STORE_FACTORIES``::

    ("my_adapter", my_adapter_factory)   # returns a fresh, EMPTY store

Factory contract: the callable returns a fresh, empty object satisfying the
``ResearchMemoryStore`` Protocol; construction is deterministic (no clock,
no RNG, no environment reads — the fixture-kit discipline); the suite seeds
every store exclusively through the append-only API itself
(``append_episodic`` / ``register_lesson``), which is the only seeding
discipline every Protocol-conformant adapter supports by construction.
Tier B tests (``test_acc23_*`` / ``test_acc24_*``) are scoped to the
in-memory reference adapter only (contract lifecycle retirement +
constructor seeding live outside the Protocol surface) and impose nothing
on future adapters.

STRUCTURAL RED LINE (A3/A11; packet lines 32–36 and 198–204): NO purge and
NO retention-expiry path exists here, and none may be introduced. The
tokens "purge"/"expire"/etc. appear ONLY inside negative structural
assertions that PROVE their absence on the Protocol and adapter surface
(AC-1/AC-2); there is no purge, expiry, retention, eviction or pruning
functionality anywhere in this file.

Contract/domain-only discipline: deterministic, clock-free (timestamps
passed in), no I/O, no network, no environment reads.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.research_memory import (
    EpisodicRunArchive,
    EpisodicRunArtifact,
    SemanticLesson,
    derive_lesson,
)
from app.domain.research_memory_store import (
    InMemoryResearchMemoryStore,
    ResearchMemoryIntegrityReport,
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
    UTC,
    make_episodic_entry,
    make_lesson,
    make_seeded_lesson_store,
)
from research_memory_jsonl_reference import _jsonl_file_reference_factory

# ---------------------------------------------------------------------------
# Store-factory registry — THE plug-in point for any future adapter.
# ---------------------------------------------------------------------------


def _in_memory_reference_factory() -> ResearchMemoryStore:
    """Fresh, empty in-memory reference store (deterministic construction)."""
    return InMemoryResearchMemoryStore()


#: Registry of store factories under acceptance test. The second entry is a
#: TEST-LAYER-ONLY pluggability proof (``research_memory_jsonl_reference``):
#: it is NOT a persistence-backend decision — D1–D7 remain ALL PENDING
#: (packet lines 3–6) and the §11 execution gate still binds. A future
#: production adapter is accepted by adding ONE entry here (see module
#: docstring); every Tier A test parameterizes over this registry unchanged.
STORE_FACTORIES: tuple[tuple[str, Callable[[], ResearchMemoryStore]], ...] = (
    ("in_memory_reference", _in_memory_reference_factory),
    ("jsonl_file_reference", _jsonl_file_reference_factory),
)

_FACTORY_IDS: tuple[str, ...] = tuple(name for name, _ in STORE_FACTORIES)
_FACTORY_CALLABLES: tuple[Callable[[], ResearchMemoryStore], ...] = tuple(
    factory for _, factory in STORE_FACTORIES
)


def _for_each_registered_store(test_fn: Callable[..., None]) -> Callable[..., None]:
    """Parameterize a Tier A test over every registered store factory."""
    return pytest.mark.parametrize(
        "store_factory", _FACTORY_CALLABLES, ids=_FACTORY_IDS
    )(test_fn)


#: The exact Protocol surface — append/get/index/verify ONLY. The absence of
#: any update/delete/purge/rewrite member is the structural append-only
#: proof (A3/A11). Mirrors the pinned surface in tests/test_research_memory_store.py.
EXPECTED_PROTOCOL_METHODS = frozenset(
    {
        "append_episodic",
        "get_episodic",
        "episodic_for_run",
        "episodic_for_hypothesis",
        "episodic_available_at",
        "register_lesson",
        "latest_lesson",
        "lesson_history",
        "lessons_active_at",
        "integrity_report",
    }
)

#: Tokens that must NEVER appear on the writable surface. Presence of any of
#: these as a member name would introduce an update/delete/purge/retention-
#: expiry path — structurally forbidden (A3/A11).
FORBIDDEN_MUTATION_TOKENS = (
    "update",
    "remove",
    "delete",
    "purge",
    "expire",
    "expiry",
    "retention",
    "rewrite",
    "prune",
    "evict",
    "clear",
    "pop",
    "drop",
    "truncate",
    "vacuum",
)


# ---------------------------------------------------------------------------
# Tier A — parameterized over every registered store factory (AC-1 .. AC-12)
# ---------------------------------------------------------------------------


@_for_each_registered_store
def test_acc01_protocol_surface_exact_and_append_only(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-1: append-only structural proof — the Protocol surface is EXACTLY
    the append/get/index/verify set and no update/delete path is reachable
    from an instance (packet §10 test 1, structural half; A3)."""
    store = store_factory()
    assert isinstance(store, ResearchMemoryStore)  # runtime_checkable
    observed = frozenset(getattr(ResearchMemoryStore, "__protocol_attrs__"))
    assert observed == EXPECTED_PROTOCOL_METHODS
    for token in FORBIDDEN_MUTATION_TOKENS:
        assert not any(token in method for method in observed), token
    # No update-in-place API is reachable from the instance either.
    public = {name for name in dir(store) if not name.startswith("_")}
    assert EXPECTED_PROTOCOL_METHODS <= public
    for forbidden in FORBIDDEN_MUTATION_TOKENS:
        assert not any(forbidden in name for name in public), forbidden


@_for_each_registered_store
def test_acc02_no_purge_no_retention_expiry_structural_absence(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-2: NO purge / NO retention-expiry path exists anywhere on the
    surface — Protocol members, instance public members, and the integrity
    refusal-record fields are all scanned (A3/A11: nothing expires out of
    the archive; packet lines 32–36 and 198–204)."""
    store = store_factory()
    protocol_attrs = set(getattr(ResearchMemoryStore, "__protocol_attrs__"))
    public = {name for name in dir(store) if not name.startswith("_")}
    report_fields = set(ResearchMemoryIntegrityReport.model_fields)
    for surface_name, surface in (
        ("protocol", protocol_attrs),
        ("instance", public),
        ("integrity_report_fields", report_fields),
    ):
        for token in FORBIDDEN_MUTATION_TOKENS:
            offenders = [name for name in surface if token in name]
            assert offenders == [], (surface_name, token, offenders)


@_for_each_registered_store
def test_acc03_append_only_idempotent_and_conflict_refused_state_unchanged(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-3: append-only write semantics — identical re-append is an
    idempotent no-op; conflicting content under the same id is refused with
    the contract's ``ValueError`` and leaves the store byte-unchanged
    (refusal is an atomic no-op)."""
    store = store_factory()
    entry = make_episodic_entry("ra-1")
    store.append_episodic(entry)
    store.append_episodic(entry)  # identical re-append: not a conflict
    report = store.integrity_report()
    assert report.entry_count == 1
    assert report.entry_digests == (
        ("ra-1", sha256_hex(canonical_research_memory_json(entry))),
    )
    digests_before = report.entry_digests
    with pytest.raises(ValueError, match="episodic_archive_conflict"):
        store.append_episodic(make_episodic_entry("ra-1", trust_state="stale"))
    # Refused append rewrote nothing: original record stands, ledger identical.
    got = store.get_episodic("ra-1")
    assert got is not None and got.trust_state == "live"
    assert store.integrity_report().entry_digests == digests_before


@_for_each_registered_store
def test_acc04_records_frozen_no_update_in_place(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-13 (record level): retrieved records are frozen — in-place
    mutation of episodic records, lesson records, and integrity reports is
    refused, so no update-in-place is reachable even through a record."""
    store = store_factory()
    entry = make_episodic_entry("ra-1")
    store.append_episodic(entry)
    store.register_lesson(make_lesson(lesson_id="l1"))
    got = store.get_episodic("ra-1")
    assert got is not None
    with pytest.raises(ValidationError):
        got.trust_state = "mutated"  # type: ignore[misc]
    lesson = store.latest_lesson("l1")
    assert lesson is not None
    with pytest.raises(ValidationError):
        lesson.statement = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        store.integrity_report().verify_ok = False  # type: ignore[misc]
    # Store content untouched by the refused mutations.
    assert store.get_episodic("ra-1") == entry


@_for_each_registered_store
def test_acc05_canonical_roundtrip_byte_stability_through_store(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-4: canonical serialization round-trip byte-stability — the record
    retrieved from the store canonically serializes byte-identically to the
    record appended (Unicode-safe, digest-stable), and the store's own
    integrity digest equals the digest of the canonical text."""
    entry = make_episodic_entry("ra-1", notes="µ € 😀 evidence")
    text_before = canonical_research_memory_json(entry)
    digest_before = sha256_hex(text_before)
    store = store_factory()
    store.append_episodic(entry)
    got = store.get_episodic("ra-1")
    assert got is not None
    assert canonical_research_memory_json(got) == text_before  # byte-stable
    assert canonical_research_memory_json(got) == canonical_research_memory_json(got)
    report = store.integrity_report()
    assert report.entry_digests == (("ra-1", digest_before),)
    # Unicode survives verbatim in the canonical form (UTF-8, not escaped).
    assert "µ € 😀 evidence" in text_before


@_for_each_registered_store
def test_acc06_integrity_report_shape_and_insertion_order(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-13 (report level): the integrity report is frozen, reports the
    entry digests in append (insertion) order, and counts lesson versions
    per id in sorted order."""
    entry1 = make_episodic_entry("ra-1")
    entry2 = make_episodic_entry("ra-2", run_id="run-r2", hypothesis_id=None)
    store = store_factory()
    store.append_episodic(entry1)
    store.append_episodic(entry2)
    store.register_lesson(make_lesson(lesson_id="l1"))
    store.register_lesson(
        make_lesson(lesson_id="l1", version=2, created_at_utc=T2)
    )
    store.register_lesson(make_lesson(lesson_id="l0", created_at_utc=T1))
    report = store.integrity_report()
    assert report.verify_ok is True
    assert report.entry_count == 2
    assert report.entry_digests == (
        ("ra-1", sha256_hex(canonical_research_memory_json(entry1))),
        ("ra-2", sha256_hex(canonical_research_memory_json(entry2))),
    )
    assert report.lesson_version_counts == (("l0", 1), ("l1", 2))
    assert report.mismatched_entry_ids == () and report.missing_entry_ids == ()
    assert report.refusal_reasons == ()
    with pytest.raises(ValidationError):
        report.verify_ok = False  # type: ignore[misc]


@_for_each_registered_store
def test_acc07_verify_integrity_ok_and_later_appends_legal(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-5 (OK path): digests verify against an earlier snapshot; appends
    AFTER the snapshot are legal (append is the only legal change) and are
    not refusals."""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-1"))
    store.append_episodic(make_episodic_entry("ra-2", run_id="run-r2"))
    expected = dict(store.integrity_report().entry_digests)
    result = verify_integrity(store, expected)
    assert result.verify_ok is True
    assert result.mismatched_entry_ids == () and result.missing_entry_ids == ()
    store.append_episodic(make_episodic_entry("ra-3", recorded_at_utc=T2))
    result_after = verify_integrity(store, expected)
    assert result_after.verify_ok is True
    assert result_after.entry_count == 3
    assert result_after.mismatched_entry_ids == ()
    assert result_after.missing_entry_ids == ()


@_for_each_registered_store
def test_acc08_verify_integrity_tamper_refused_fail_closed(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-5 (tamper): a mutated digest is caught — verify returns a
    fail-closed refusal record (never raises), naming the mismatched id."""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-1"))
    store.append_episodic(make_episodic_entry("ra-2", run_id="run-r2"))
    expected = dict(store.integrity_report().entry_digests)
    tampered = dict(expected)
    tampered["ra-2"] = ("0" if tampered["ra-2"][0] != "0" else "1") + tampered["ra-2"][1:]
    result = verify_integrity(store, tampered)  # refusal record, no exception
    assert result.verify_ok is False
    assert result.mismatched_entry_ids == ("ra-2",)
    assert result.missing_entry_ids == ()
    assert "digest_mismatch" in result.refusal_reasons
    assert ("ra-1", expected["ra-1"]) in result.entry_digests
    assert result.entry_count == 2


@_for_each_registered_store
def test_acc09_verify_integrity_missing_entry_refused_fail_closed(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-5 (deletion detection): an expected entry absent from the store is
    an append-only violation and is refused as ``missing_entry_ids`` —
    deletion cannot hide from verification."""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-1"))
    expected = {
        "ra-1": sha256_hex(canonical_research_memory_json(make_episodic_entry("ra-1"))),
        "ra-2": sha256_hex(canonical_research_memory_json(make_episodic_entry("ra-2"))),
    }
    result = verify_integrity(store, expected)
    assert result.verify_ok is False
    assert result.missing_entry_ids == ("ra-2",)
    assert result.mismatched_entry_ids == ()
    assert "expected_entry_missing_from_store" in result.refusal_reasons


@_for_each_registered_store
def test_acc10_pit_episodic_available_at_ordering_and_lookahead_guard(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-6 (episodic PIT): ``episodic_available_at`` is a pure cutoff view
    over ``recorded_at_utc`` — boundary-inclusive, insertion-ordered, and
    look-ahead-proof: records recorded AFTER the cutoff are invisible even
    when their information cutoff lies before it (packet §10 test 3)."""
    store = store_factory()
    ra4 = make_episodic_entry("ra-4", recorded_at_utc=T2)
    for entry in (
        make_episodic_entry("ra-1", recorded_at_utc=T1),
        make_episodic_entry("ra-2", recorded_at_utc=T2),
        make_episodic_entry("ra-3", run_id="run-r2", hypothesis_id=None,
                            recorded_at_utc=T2),
        ra4,
    ):
        store.append_episodic(entry)
    assert store.episodic_available_at(T0) == ()  # nothing recorded before T1
    assert [e.entry_id for e in store.episodic_available_at(T1)] == ["ra-1"]
    assert [e.entry_id for e in store.episodic_available_at(T2)] == [
        "ra-1",
        "ra-2",
        "ra-3",
        "ra-4",
    ]
    # Look-ahead guard: ra-2/ra-3/ra-4 recorded after T1 stay invisible at T1
    # even though their information_cutoff_utc (T0) precedes T1.
    at_t1 = store.episodic_available_at(T1)
    assert [e.entry_id for e in at_t1] == ["ra-1"]
    # Index views preserve insertion order (append-only growth).
    assert [e.entry_id for e in store.episodic_for_run("run-r1")] == [
        "ra-1",
        "ra-2",
        "ra-4",
    ]
    assert store.episodic_for_run("run-r1")[-1] == ra4


@_for_each_registered_store
def test_acc11_pit_lessons_active_at_ordering(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-6 (lessons PIT): ``lessons_active_at`` mirrors the contract
    semantics exactly — created-after-cutoff lessons excluded; superseded
    history conservative at earlier cutoffs; result sorted deterministically."""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-1"))
    store.append_episodic(make_episodic_entry("ra-2", run_id="run-r2"))
    store.register_lesson(make_lesson(lesson_id="l1", created_at_utc=T1))
    store.register_lesson(
        make_lesson(
            lesson_id="l2", source_artifact_ids=("ra-2",), created_at_utc=T2
        )
    )
    assert [l.lesson_id for l in store.lessons_active_at(T1)] == ["l1"]
    assert {l.lesson_id for l in store.lessons_active_at(T2)} == {"l1", "l2"}
    assert store.lessons_active_at(T0) == ()
    # Supersede l1 via a NEW version (history never rewritten).
    store.register_lesson(
        make_lesson(lesson_id="l1", version=2, created_at_utc=T2)
    )
    assert {l.lesson_id for l in store.lessons_active_at(T2)} == {"l1", "l2"}
    # Conservative documented semantics at T1 (mirrors the contract-level
    # PIT honesty test): l1's latest version <= T1 is SUPERSEDED while its
    # ACTIVE v2 did not exist yet.
    assert [l.lesson_id for l in store.lessons_active_at(T1)] == []
    # Deterministic ordering by (lesson_id, version).
    active = store.lessons_active_at(T2)
    assert [(l.lesson_id, l.version) for l in active] == sorted(
        (l.lesson_id, l.version) for l in active
    )


@_for_each_registered_store
def test_acc12_promotion_flow_episodic_to_lesson_citation_gate_and_supersession(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-7: episodic append → archive → semantic-lesson promotion — lessons
    cite ONLY archived artifacts (traceability gate), promotion registers v1
    through the store, supersession creates a NEW version and history is
    never rewritten (packet §10 tests 4–5, store-level flow; D-AI-28)."""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-1"))
    store.append_episodic(make_episodic_entry("ra-2", run_id="run-r2",
                                             hypothesis_id=None))
    # Build the contract archive FROM the store's own honest views, then
    # derive the lesson through the contract factory (citation gate active).
    archive = EpisodicRunArchive(store.episodic_available_at(T3))
    lesson = derive_lesson(
        archive,
        lesson_id="l1",
        statement="Money-flow regime shifts precede breadth expansion by ~2 sessions.",
        source_artifact_ids=("ra-1", "ra-2"),
        curated_by="deterministic-rule:lesson-r1",
        curation_basis="DETERMINISTIC_RULE",
        at_utc=T2,
    )
    store.register_lesson(lesson)
    latest = store.latest_lesson("l1")
    assert latest is not None and latest.version == 1
    assert latest.status == "ACTIVE"
    assert latest.source_artifact_ids == ("ra-1", "ra-2")
    # Citation gate: a lesson citing an unknown artifact is refused by the
    # contract factory — nothing is registered (nothing is invented).
    with pytest.raises(ValueError, match="lesson_cites_unknown_artifacts"):
        derive_lesson(
            archive,
            lesson_id="l9",
            statement="Never derived.",
            source_artifact_ids=("ghost",),
            curated_by="deterministic-rule:x",
            curation_basis="DETERMINISTIC_RULE",
            at_utc=T2,
        )
    assert store.latest_lesson("l9") is None
    # Supersession via NEW terminal-free version (HUMAN_REVIEW basis).
    store.register_lesson(
        make_lesson(
            lesson_id="l1",
            version=2,
            supersedes_version=1,
            curation_basis="HUMAN_REVIEW",
            curated_by="reviewer-1",
            created_at_utc=T3,
        )
    )
    history = store.lesson_history("l1")
    assert [l.version for l in history] == [1, 2]
    assert history[0].status == "SUPERSEDED"
    assert history[1].status == "ACTIVE" and history[1].curation_basis == "HUMAN_REVIEW"
    # History never rewritten: v1's original statement survived verbatim.
    assert history[0].statement == lesson.statement
    report = store.integrity_report()
    assert report.lesson_version_counts == (("l1", 2),)


@_for_each_registered_store
def test_acc13_provenance_completeness_blocks_acceptance_at_boundary(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-11: records with missing/invalid mandatory provenance are refused
    at the storage boundary (validation precedes any mutation) — missing
    input snapshot, malformed code commit, empty policy version, and
    anti-look-ahead cutoff ordering all refuse with NOTHING stored
    (packet §10 test 5; 03:40; A6)."""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-ok"))
    good_report = store.integrity_report()
    with pytest.raises(ValidationError):
        make_episodic_entry("ra-bad", input_snapshot_sha256=None)
    with pytest.raises(ValidationError):
        make_episodic_entry("ra-bad", code_commit="not-hex")
    with pytest.raises(ValidationError):
        make_episodic_entry("ra-bad", policy_version="")
    with pytest.raises(ValidationError, match="information_cutoff_after_recording"):
        make_episodic_entry("ra-bad", information_cutoff_utc=T2, recorded_at_utc=T1)
    # Nothing partial was ever stored: ledger unchanged by every refusal.
    assert store.integrity_report() == good_report
    assert store.get_episodic("ra-bad") is None


@_for_each_registered_store
def test_acc14_crash_consistency_refused_write_leaves_no_partial_state(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-8 (crash-consistency, engine-neutral): a refused/invalid write
    leaves the store byte-unchanged — no torn or partially-formed record is
    ever observable. (The engine-level kill-during-write drill is packet
    §10 test 7, executed in the adapter's own module once D1–D7 allow an
    engine; the all-or-nothing CONTRACT it must satisfy is pinned here.)"""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-1"))
    digests_before = store.integrity_report().entry_digests
    with pytest.raises(ValueError, match="episodic_archive_conflict"):
        store.append_episodic(make_episodic_entry("ra-1", trust_state="torn"))
    with pytest.raises(ValidationError):
        make_episodic_entry("ra-partial", information_cutoff_utc=T2,
                            recorded_at_utc=T1)
    got = store.get_episodic("ra-1")
    assert got is not None and got.trust_state == "live"
    assert store.get_episodic("ra-partial") is None
    assert store.integrity_report().entry_digests == digests_before


@_for_each_registered_store
class _CrashProbe:
    """Protocol-conformant adapter probe: delegates every operation to an
    inner store and injects a simulated crash (``RuntimeError``) around the
    append of ONE designated entry id — before the commit or after it. Used
    to prove the all-or-nothing observable contract (AC-8)."""

    def __init__(
        self,
        inner: ResearchMemoryStore,
        *,
        crash_on_id: str,
        after_commit: bool,
    ) -> None:
        self._inner = inner
        self._crash_on_id = crash_on_id
        self._after_commit = after_commit

    def append_episodic(self, entry: EpisodicRunArtifact) -> None:
        if not self._after_commit and entry.entry_id == self._crash_on_id:
            raise RuntimeError("simulated_crash_during_append")
        self._inner.append_episodic(entry)
        if self._after_commit and entry.entry_id == self._crash_on_id:
            raise RuntimeError("simulated_crash_after_commit")

    def get_episodic(self, entry_id: str) -> EpisodicRunArtifact | None:
        return self._inner.get_episodic(entry_id)

    def episodic_for_run(self, run_id: str) -> tuple[EpisodicRunArtifact, ...]:
        return self._inner.episodic_for_run(run_id)

    def episodic_for_hypothesis(
        self, hypothesis_id: str
    ) -> tuple[EpisodicRunArtifact, ...]:
        return self._inner.episodic_for_hypothesis(hypothesis_id)

    def episodic_available_at(
        self, cutoff: datetime
    ) -> tuple[EpisodicRunArtifact, ...]:
        return self._inner.episodic_available_at(cutoff)

    def register_lesson(self, lesson: SemanticLesson) -> None:
        self._inner.register_lesson(lesson)

    def latest_lesson(self, lesson_id: str) -> SemanticLesson | None:
        return self._inner.latest_lesson(lesson_id)

    def lesson_history(self, lesson_id: str) -> tuple[SemanticLesson, ...]:
        return self._inner.lesson_history(lesson_id)

    def lessons_active_at(self, cutoff: datetime) -> tuple[SemanticLesson, ...]:
        return self._inner.lessons_active_at(cutoff)

    def integrity_report(self) -> ResearchMemoryIntegrityReport:
        return self._inner.integrity_report()


@_for_each_registered_store
def test_acc15_crash_consistency_injected_adapter_failure_all_or_nothing(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-8 (all-or-nothing): whatever point a crash injects around an
    append, the observable outcome is ALL of the record (fully present and
    digest-clean) or NONE of it (absent, no partial trace) — never a
    partially-formed record."""
    inner = store_factory()
    inner.append_episodic(make_episodic_entry("ra-1"))
    inner.append_episodic(make_episodic_entry("ra-2", run_id="run-r2"))
    expected = dict(inner.integrity_report().entry_digests)
    crash_entry = make_episodic_entry("ra-crash", run_id="run-crash")

    # Crash BEFORE commit → record absent, nothing partial, snapshot intact.
    probe = _CrashProbe(inner, crash_on_id="ra-crash", after_commit=False)
    assert isinstance(probe, ResearchMemoryStore)
    with pytest.raises(RuntimeError, match="simulated_crash_during_append"):
        probe.append_episodic(crash_entry)
    assert probe.get_episodic("ra-crash") is None
    assert probe.episodic_for_run("run-crash") == ()
    assert all(
        entry_id != "ra-crash" for entry_id, _ in probe.integrity_report().entry_digests
    )
    result = verify_integrity(probe, expected)
    assert result.verify_ok is True  # nothing expected is missing or mismatched

    # Crash AFTER commit → record FULLY present and digest-clean (a complete
    # record is the only acceptable post-commit observable — never torn).
    probe2 = _CrashProbe(store_factory(), crash_on_id="ra-crash", after_commit=True)
    with pytest.raises(RuntimeError, match="simulated_crash_after_commit"):
        probe2.append_episodic(crash_entry)
    assert probe2.get_episodic("ra-crash") == crash_entry
    assert probe2.integrity_report().entry_digests == (
        ("ra-crash", sha256_hex(canonical_research_memory_json(crash_entry))),
    )
    assert verify_integrity(
        probe2,
        {"ra-crash": sha256_hex(canonical_research_memory_json(crash_entry))},
    ).verify_ok is True


@_for_each_registered_store
def test_acc16_crash_consistency_reopen_all_records_digest_clean(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-8 (reopen): a fresh store rebuilt through the same append-only API
    from the same record sequence (the engine-neutral expression of "reopen
    after crash between appends") holds every prior record byte-identical
    and digest-clean — no record is lost, none is partial."""
    entries = (
        make_episodic_entry("ra-1", recorded_at_utc=T1),
        make_episodic_entry("ra-2", recorded_at_utc=T2),
        make_episodic_entry("ra-3", run_id="run-r2", hypothesis_id=None,
                            recorded_at_utc=T2),
    )
    first = store_factory()
    for entry in entries:
        first.append_episodic(entry)
    expected = dict(first.integrity_report().entry_digests)
    reopened = store_factory()
    for entry in entries:
        reopened.append_episodic(entry)
    assert dict(reopened.integrity_report().entry_digests) == expected
    result = verify_integrity(reopened, expected)
    assert result.verify_ok is True
    for entry in entries:
        got = reopened.get_episodic(entry.entry_id)
        assert got == entry
        assert canonical_research_memory_json(got) == canonical_research_memory_json(
            entry
        )


@_for_each_registered_store
def test_acc17_concurrent_append_two_threads_all_events_preserved(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-9: appends driven from two threads through the documented
    single-writer discipline boundary (a harness-owned lock — the Protocol's
    documented concurrency class, §4.5 of the plan) preserve ALL events:
    no lost updates, per-writer submission order preserved, digests all
    verify, and the PIT split by recorded time is exact. No multi-writer
    guarantee is asserted or implied (multi-user requirement UNRESOLVED,
    brief §C2)."""
    store = store_factory()
    lock = threading.Lock()
    per_thread = 20
    errors: list[Exception] = []

    def _append_all(prefix: str, at_utc: datetime) -> None:
        for i in range(per_thread):
            try:
                with lock:  # single-writer discipline boundary
                    store.append_episodic(
                        make_episodic_entry(
                            f"ra-{prefix}-{i}",
                            run_id=f"run-{prefix}",
                            recorded_at_utc=at_utc,
                        )
                    )
            except Exception as exc:  # surfaced below — never swallowed
                errors.append(exc)

    threads = (
        threading.Thread(target=_append_all, args=("A", T1), name="writer-A"),
        threading.Thread(target=_append_all, args=("B", T2), name="writer-B"),
    )
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    # Every event preserved exactly once.
    for prefix in ("A", "B"):
        for i in range(per_thread):
            entry_id = f"ra-{prefix}-{i}"
            got = store.get_episodic(entry_id)
            assert got is not None and got.entry_id == entry_id
    assert store.integrity_report().entry_count == 2 * per_thread
    # Per-writer submission order preserved inside each run view.
    assert [e.entry_id for e in store.episodic_for_run("run-A")] == [
        f"ra-A-{i}" for i in range(per_thread)
    ]
    assert [e.entry_id for e in store.episodic_for_run("run-B")] == [
        f"ra-B-{i}" for i in range(per_thread)
    ]
    # PIT split by recorded time is exact regardless of interleaving.
    assert {e.entry_id for e in store.episodic_available_at(T1)} == {
        f"ra-A-{i}" for i in range(per_thread)
    }
    assert len(store.episodic_available_at(T2)) == 2 * per_thread
    # Full digest verification over everything appended.
    constructed = {
        f"ra-{p}-{i}": make_episodic_entry(
            f"ra-{p}-{i}", run_id=f"run-{p}",
            recorded_at_utc=T1 if p == "A" else T2,
        )
        for p in ("A", "B")
        for i in range(per_thread)
    }
    expected = {
        entry_id: sha256_hex(canonical_research_memory_json(entry))
        for entry_id, entry in constructed.items()
    }
    assert verify_integrity(store, expected).verify_ok is True


@_for_each_registered_store
def test_acc18_concurrent_conflicting_append_refused_state_unchanged(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-9 (conflicts under concurrency): two threads racing to append
    conflicting content under the same id BOTH get the contract refusal and
    the store state is unchanged — no last-writer-wins rewrite is possible."""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-1"))
    digests_before = store.integrity_report().entry_digests
    lock = threading.Lock()
    conflicts: list[str] = []

    def _attempt_conflict(variant: str) -> None:
        with lock:  # single-writer discipline boundary
            try:
                store.append_episodic(
                    make_episodic_entry("ra-1", trust_state=f"variant-{variant}")
                )
            except ValueError as exc:
                conflicts.append(str(exc))

    threads = (
        threading.Thread(target=_attempt_conflict, args=("1",)),
        threading.Thread(target=_attempt_conflict, args=("2",)),
    )
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(conflicts) == 2
    assert all("episodic_archive_conflict" in message for message in conflicts)
    got = store.get_episodic("ra-1")
    assert got is not None and got.trust_state == "live"
    assert store.integrity_report().entry_digests == digests_before


@_for_each_registered_store
def test_acc19_integrity_refusal_records_frozen_and_append_only(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-10: integrity refusal records are themselves append-only —
    frozen (no mutation), byte-stable under pure re-derivation from the
    same state, collectable in a ledger that only grows (earlier refusals
    are never rewritten), and a refusal never shrinks the store's own
    record ledger."""
    store = store_factory()
    store.append_episodic(make_episodic_entry("ra-1"))
    store.append_episodic(make_episodic_entry("ra-2", run_id="run-r2"))
    good = dict(store.integrity_report().entry_digests)
    tampered = dict(good)
    tampered["ra-1"] = ("0" if tampered["ra-1"][0] != "0" else "1") + tampered["ra-1"][1:]

    ledger: list[ResearchMemoryIntegrityReport] = []
    refusal1 = verify_integrity(store, tampered)
    assert refusal1.verify_ok is False
    ledger.append(refusal1)
    # Refusal left the store unchanged, and a legal append still works.
    store.append_episodic(make_episodic_entry("ra-3", recorded_at_utc=T2))
    # Second, different refusal (expected-but-absent id → deletion detection).
    refusal2 = verify_integrity(store, {**good, "ra-ghost": "0" * 64})
    assert refusal2.verify_ok is False
    assert refusal2.missing_entry_ids == ("ra-ghost",)
    ledger.append(refusal2)

    # Ledger only grows; earlier refusal records are byte-unchanged in it.
    texts = [canonical_research_memory_json(r) for r in ledger]
    assert len(ledger) == 2
    # Purity: re-deriving a refusal from the SAME (state, expectation)
    # reproduces it byte-identically — refusals are derived, never mutated.
    fresh = store_factory()
    fresh.append_episodic(make_episodic_entry("ra-1"))
    fresh.append_episodic(make_episodic_entry("ra-2", run_id="run-r2"))
    assert canonical_research_memory_json(verify_integrity(fresh, tampered)) == texts[0]
    # Frozen: a refusal record cannot be rewritten in place.
    with pytest.raises(ValidationError):
        ledger[0].verify_ok = True  # type: ignore[misc]
    # A refusal never removes records: the store ledger only grew.
    assert [entry_id for entry_id, _ in store.integrity_report().entry_digests] == [
        "ra-1",
        "ra-2",
        "ra-3",
    ]


@_for_each_registered_store
def test_acc20_explicit_miss_fail_closed_no_fabricated_records(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-12: unknown ids are EXPLICIT misses — ``None`` / empty tuples,
    never fabricated substitute records, never ``KeyError`` (the contracts'
    honest miss semantics, wrapped verbatim)."""
    store = store_factory()
    assert store.get_episodic("ghost") is None
    assert store.episodic_for_run("ghost") == ()
    assert store.episodic_for_hypothesis("ghost") == ()
    assert store.episodic_available_at(T3) == ()
    assert store.latest_lesson("ghost") is None
    assert store.lesson_history("ghost") == ()
    assert store.lessons_active_at(T0) == ()
    report = store.integrity_report()
    assert report.verify_ok is True and report.entry_count == 0
    # Misses stay explicit after content exists.
    store.append_episodic(make_episodic_entry("ra-1", recorded_at_utc=T1))
    assert store.get_episodic("ghost") is None
    assert store.episodic_available_at(T0) == ()


# ---------------------------------------------------------------------------
# Tier B — engine-neutral pure functions + reference-adapter composition pins
# (not parameterized: these do not depend on which store factory runs)
# ---------------------------------------------------------------------------


def test_acc21_canonical_serialization_pure_determinism() -> None:
    """AC-4 (pure-function half): canonical JSON is byte-stable across
    repeated calls and independent constructions, key-insertion-order
    independent, renders Decimal as string, refuses NaN/Infinity and
    non-serializable objects (fail-closed, never coerces)."""
    left = canonical_research_memory_json({"x": 1, "y": {"b": 2, "a": 3}})
    right = canonical_research_memory_json({"y": {"a": 3, "b": 2}, "x": 1})
    assert left == right == '{"x":1,"y":{"a":3,"b":2}}'
    assert canonical_research_memory_json(left) == '"{\\"x\\":1,\\"y\\":{\\"a\\":3,\\"b\\":2}}"'
    entry_a = make_episodic_entry("ra-1")
    entry_b = make_episodic_entry("ra-1")  # independent construction
    text = canonical_research_memory_json(entry_a)
    assert text == canonical_research_memory_json(entry_a)
    assert text == canonical_research_memory_json(entry_b)
    # DECIMAL_AS_STRING: no binary-float drift may enter a digest.
    assert canonical_research_memory_json(
        {"amount": Decimal("1.500"), "t": T1}
    ) == '{"amount":"1.500","t":"%s"}' % T1.isoformat()
    with pytest.raises(ValueError):
        canonical_research_memory_json({"bad": float("nan")})
    with pytest.raises(TypeError):
        canonical_research_memory_json({"bad": object()})


def test_acc22_verify_integrity_never_raises_on_corrupt_adapter() -> None:
    """AC-5 (fail-closed boundary): a corrupt/failing adapter produces a
    returned refusal record — ``verify_integrity`` NEVER raises raw
    exceptions, whatever the adapter does."""

    class _CorruptAdapter:
        def integrity_report(self) -> ResearchMemoryIntegrityReport:
            raise RuntimeError("corrupt_record")

    result = verify_integrity(_CorruptAdapter(), {"ra-1": "0" * 64})
    assert result.verify_ok is False
    assert result.refusal_reasons == ("verify_refused:RuntimeError",)
    assert result.entry_count == 0
    assert result.mismatched_entry_ids == () and result.missing_entry_ids == ()


def test_acc23_retirement_terminal_history_never_rewritten() -> None:
    """AC-14 (reference-adapter tier): retirement is a NEW terminal RETIRED
    version — history is preserved, statements never rewritten, a retired
    lesson cannot be extended or re-retired, and PIT views honor the
    retirement honestly. Uses the contract lifecycle
    (``SemanticLessonStore.retire``), which lives OUTSIDE the Protocol
    surface by design; scoped to the in-memory reference adapter."""
    contract_store = make_seeded_lesson_store(make_lesson(lesson_id="l1"))
    contract_store = contract_store.register(
        make_lesson(lesson_id="l2", source_artifact_ids=("ra-1",))
    )
    contract_store = contract_store.retire(
        "l2", retired_by="reviewer-1", at_utc=T3
    )
    store = InMemoryResearchMemoryStore(lessons=contract_store)
    store.append_episodic(make_episodic_entry("ra-1"))  # seed via append-only API
    latest = store.latest_lesson("l2")
    assert latest is not None and latest.status == "RETIRED" and latest.version == 2
    history = store.lesson_history("l2")
    assert [l.version for l in history] == [1, 2]  # history preserved, not deleted
    assert history[0].status == "SUPERSEDED"
    assert history[-1].statement == history[0].statement  # nothing rewritten
    # Retirement is terminal: extending or re-retiring is refused by the
    # contract lifecycle; nothing can un-retire it through the store.
    with pytest.raises(ValueError, match="retire_requires_active_lesson"):
        contract_store.retire("l2", retired_by="reviewer-1", at_utc=T3)
    with pytest.raises(ValueError, match="cannot_extend_non_active_lesson"):
        store.register_lesson(
            make_lesson(lesson_id="l2", version=3, supersedes_version=2,
                        created_at_utc=T3)
        )
    assert {l.lesson_id for l in store.lessons_active_at(T3)} == {"l1"}


def test_acc24_reference_adapter_composes_contracts_by_delegation() -> None:
    """AC-15 (reference tier): the in-memory reference adapter DELEGATES to
    the delivered contracts — views return the contracts' own frozen records
    in append (insertion) order, and the integrity view is the kit's frozen
    report. The contracts remain the canonical behavior reference
    (reuse rule 02:107-112)."""
    store = InMemoryResearchMemoryStore()
    entries = (
        make_episodic_entry("ra-1", recorded_at_utc=T1),
        make_episodic_entry("ra-2", run_id="run-r2", hypothesis_id=None,
                            recorded_at_utc=T2),
    )
    for entry in entries:
        store.append_episodic(entry)
    view = store.episodic_available_at(T3)
    assert all(isinstance(e, EpisodicRunArtifact) for e in view)
    assert [e.entry_id for e in view] == ["ra-1", "ra-2"]  # insertion order
    # The episodic view IS contract state: an EpisodicRunArchive built from
    # the store's view answers exactly as the store does.
    archive = EpisodicRunArchive(view)
    assert archive.get("ra-1") == store.get_episodic("ra-1")
    assert archive.available_at(T1) == store.episodic_available_at(T1)
    report = store.integrity_report()
    assert isinstance(report, ResearchMemoryIntegrityReport)
    assert [entry_id for entry_id, _ in report.entry_digests] == ["ra-1", "ra-2"]


# ---------------------------------------------------------------------------
# Tier A enrichment (WS5-T2) — additional parameterized negative/edge cases
# (acc25..acc30). Same registry, same discipline: every case runs once per
# registered store factory, so any future production adapter must pass them
# too. Each docstring names the AC id(s) it pins and any honest adaptation
# to the contracts' ACTUAL behavior. Decision-free: D1–D7 remain ALL
# PENDING; nothing here assumes or exercises an owner decision.
# ---------------------------------------------------------------------------

#: Fixed far-future instant on the fixture timeline (deterministic; strictly
#: after T3) — used to prove clock-free timestamp discipline (acc29).
_T_FUTURE = datetime(2026, 10, 18, 23, 0, 0, tzinfo=UTC)


@_for_each_registered_store
def test_acc25_duplicate_identity_conflicts_all_views_unchanged(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-3 (WS5-T2 enrichment, beyond acc03/acc14): duplicate-identity
    appends are refused whenever ANY canonical field differs — including a
    field outside every index/PIT surface (``notes``) and the PIT-relevant
    ``recorded_at_utc`` itself — while a VALUE-EQUAL record freshly
    constructed (independent object, identical content) stays an idempotent
    no-op: identity is by content, never object identity. Every refusal
    leaves ALL views unchanged — digest ledger, run/hypothesis indexes, and
    the PIT view (a refused timestamp-shift cannot migrate a record's PIT
    position)."""
    store = store_factory()
    entry = make_episodic_entry("ra-1")
    store.append_episodic(entry)
    before = store.integrity_report()
    # Value-equal fresh construction: idempotent, no duplication, no refusal.
    store.append_episodic(make_episodic_entry("ra-1"))
    assert store.integrity_report() == before
    # Conflict on a non-indexed field (notes): refused.
    with pytest.raises(ValueError, match="episodic_archive_conflict"):
        store.append_episodic(
            make_episodic_entry("ra-1", notes="late annotation attempt")
        )
    # Conflict on the PIT-relevant recording timestamp: refused.
    with pytest.raises(ValueError, match="episodic_archive_conflict"):
        store.append_episodic(make_episodic_entry("ra-1", recorded_at_utc=T2))
    # Refused attempts rewrote NOTHING — the original record stands in
    # every view.
    assert store.integrity_report() == before
    got = store.get_episodic("ra-1")
    assert got is not None and got == entry and got.notes == ""
    assert store.episodic_available_at(T1) == (entry,)  # PIT position unmoved
    assert store.episodic_available_at(T2) == (entry,)  # exactly one record
    assert store.episodic_for_run("run-r1") == (entry,)
    assert store.episodic_for_hypothesis("hyp-7") == (entry,)


@_for_each_registered_store
def test_acc26_promotion_gate_pit_invisible_source_refused_stable_reason(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-7 + AC-6 (WS5-T2 enrichment): the promotion/citation gate refuses
    a source artifact that is PIT-INVISIBLE at the derivation instant — a
    record already appended but RECORDED after the cutoff is as unavailable
    as a missing one (lookahead-proof promotion; mirrors acc10's episodic
    guard at the semantic gate). The refusal names EXACTLY the invisible id
    (stable machine-readable reason) and leaves no partial semantic state;
    once both sources are visible the same citation set derives and
    registers cleanly. HONEST ADAPTATION: the gate lives in the contract
    curation factory (``derive_lesson``) over the store's own PIT view, and
    episodic sources have NO retirement lifecycle (append-only, acc01/acc02
    structural proof) — so the source-refusal classes at promotion are
    exactly unknown-id (acc12) and PIT-invisible (pinned here)."""
    store = store_factory()
    early = make_episodic_entry("ra-early", recorded_at_utc=T1)
    late = make_episodic_entry(
        "ra-late", run_id="run-r2", information_cutoff_utc=T0,
        recorded_at_utc=T2,
    )
    store.append_episodic(early)
    store.append_episodic(late)
    # At T1 the store's honest PIT view holds ONLY ra-early: even though
    # ra-late's information cutoff (T0) precedes T1, it was RECORDED later.
    assert store.episodic_available_at(T1) == (early,)
    with pytest.raises(
        ValueError, match="lesson_cites_unknown_artifacts:ra-late"
    ):
        derive_lesson(
            EpisodicRunArchive(store.episodic_available_at(T1)),
            lesson_id="l1",
            statement="Never derived early.",
            source_artifact_ids=("ra-early", "ra-late"),
            curated_by="deterministic-rule:x",
            curation_basis="DETERMINISTIC_RULE",
            at_utc=T1,
        )
    # Refusal left no partial semantic state.
    assert store.latest_lesson("l1") is None
    assert store.integrity_report().lesson_version_counts == ()
    # At T3 both sources are visible: the same citation set derives and
    # registers cleanly (the earlier refusal was purely temporal).
    lesson = derive_lesson(
        EpisodicRunArchive(store.episodic_available_at(T3)),
        lesson_id="l1",
        statement="Derived only after both sources were recorded.",
        source_artifact_ids=("ra-early", "ra-late"),
        curated_by="deterministic-rule:x",
        curation_basis="DETERMINISTIC_RULE",
        at_utc=T3,
    )
    store.register_lesson(lesson)
    latest = store.latest_lesson("l1")
    assert latest is not None and latest.status == "ACTIVE"
    assert latest.source_artifact_ids == ("ra-early", "ra-late")
    assert store.integrity_report().lesson_version_counts == (("l1", 1),)


@_for_each_registered_store
def test_acc27_insertion_order_honesty_and_cross_order_verification(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-4/AC-5/AC-13 (WS5-T2 enrichment): per-record digests are
    insertion-order-INDEPENDENT as a mapping (cross-order verification
    succeeds in both directions), while the report's ``entry_digests``
    SEQUENCE and the PIT views are honestly insertion-order-DEPENDENT —
    each store reflects ITS OWN append order and is never silently
    re-sorted (complements acc06, which pins one store's insertion order).
    ``lesson_version_counts`` and ``lessons_active_at`` are sorted and
    therefore identical across orders."""
    entries = (
        make_episodic_entry("ra-1", recorded_at_utc=T1),
        make_episodic_entry("ra-2", run_id="run-r2", recorded_at_utc=T2),
        make_episodic_entry("ra-3", run_id="run-r3", hypothesis_id=None,
                            recorded_at_utc=T3),
    )
    store_a = store_factory()
    store_a.append_episodic(entries[0])
    store_a.append_episodic(entries[1])
    store_a.append_episodic(entries[2])
    store_a.register_lesson(make_lesson(lesson_id="l1", created_at_utc=T2))
    store_a.register_lesson(make_lesson(lesson_id="l0", created_at_utc=T1))

    store_b = store_factory()
    store_b.append_episodic(entries[2])
    store_b.append_episodic(entries[1])
    store_b.append_episodic(entries[0])
    store_b.register_lesson(make_lesson(lesson_id="l0", created_at_utc=T1))
    store_b.register_lesson(make_lesson(lesson_id="l1", created_at_utc=T2))

    report_a = store_a.integrity_report()
    report_b = store_b.integrity_report()
    # Mapping equality: digests are content-derived, order-independent.
    assert dict(report_a.entry_digests) == dict(report_b.entry_digests)
    # Sequence honesty: each report lists ITS OWN insertion order.
    assert [eid for eid, _ in report_a.entry_digests] == ["ra-1", "ra-2", "ra-3"]
    assert [eid for eid, _ in report_b.entry_digests] == ["ra-3", "ra-2", "ra-1"]
    # Cross-order verification succeeds both ways; the returned digest
    # sequence is the STORE's order, never the expectation's.
    cross = verify_integrity(store_a, dict(report_b.entry_digests))
    assert cross.verify_ok is True
    assert [eid for eid, _ in cross.entry_digests] == ["ra-1", "ra-2", "ra-3"]
    assert verify_integrity(store_b, dict(report_a.entry_digests)).verify_ok
    # Sorted views are order-independent.
    assert report_a.lesson_version_counts == report_b.lesson_version_counts == (
        ("l0", 1),
        ("l1", 1),
    )
    assert [(l.lesson_id, l.version) for l in store_a.lessons_active_at(T3)] == [
        (l.lesson_id, l.version) for l in store_b.lessons_active_at(T3)
    ] == [("l0", 1), ("l1", 1)]
    # PIT views are pure cutoff FILTERS over insertion order — not re-sorted
    # by recorded time (deterministic per store, honestly order-dependent).
    assert [e.entry_id for e in store_a.episodic_available_at(T2)] == [
        "ra-1",
        "ra-2",
    ]
    assert [e.entry_id for e in store_b.episodic_available_at(T2)] == [
        "ra-2",
        "ra-1",
    ]
    assert [e.entry_id for e in store_a.episodic_available_at(T3)] == [
        "ra-1",
        "ra-2",
        "ra-3",
    ]
    assert [e.entry_id for e in store_b.episodic_available_at(T3)] == [
        "ra-3",
        "ra-2",
        "ra-1",
    ]


class _SemanticCrashProbe:
    """Protocol-conformant adapter probe mirroring ``_CrashProbe`` for the
    SEMANTIC half (AC-8): delegates every operation to an inner store and
    injects a simulated crash (``RuntimeError``) around the registration of
    ONE designated lesson id — before the commit or after it."""

    def __init__(
        self,
        inner: ResearchMemoryStore,
        *,
        crash_on_lesson_id: str,
        after_commit: bool,
    ) -> None:
        self._inner = inner
        self._crash_on_lesson_id = crash_on_lesson_id
        self._after_commit = after_commit

    def append_episodic(self, entry: EpisodicRunArtifact) -> None:
        self._inner.append_episodic(entry)

    def get_episodic(self, entry_id: str) -> EpisodicRunArtifact | None:
        return self._inner.get_episodic(entry_id)

    def episodic_for_run(self, run_id: str) -> tuple[EpisodicRunArtifact, ...]:
        return self._inner.episodic_for_run(run_id)

    def episodic_for_hypothesis(
        self, hypothesis_id: str
    ) -> tuple[EpisodicRunArtifact, ...]:
        return self._inner.episodic_for_hypothesis(hypothesis_id)

    def episodic_available_at(
        self, cutoff: datetime
    ) -> tuple[EpisodicRunArtifact, ...]:
        return self._inner.episodic_available_at(cutoff)

    def register_lesson(self, lesson: SemanticLesson) -> None:
        if not self._after_commit and lesson.lesson_id == self._crash_on_lesson_id:
            raise RuntimeError("simulated_crash_during_register")
        self._inner.register_lesson(lesson)
        if self._after_commit and lesson.lesson_id == self._crash_on_lesson_id:
            raise RuntimeError("simulated_crash_after_commit")

    def latest_lesson(self, lesson_id: str) -> SemanticLesson | None:
        return self._inner.latest_lesson(lesson_id)

    def lesson_history(self, lesson_id: str) -> tuple[SemanticLesson, ...]:
        return self._inner.lesson_history(lesson_id)

    def lessons_active_at(self, cutoff: datetime) -> tuple[SemanticLesson, ...]:
        return self._inner.lessons_active_at(cutoff)

    def integrity_report(self) -> ResearchMemoryIntegrityReport:
        return self._inner.integrity_report()


@_for_each_registered_store
def test_acc28_semantic_mutation_failure_all_or_nothing(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-8 (WS5-T2 enrichment — semantic half of acc15): whatever point a
    crash injects around a lesson registration, the observable outcome is
    ALL of the version (fully present, complete history, counts updated) or
    NONE of it (absent, no partial trace) — and an interrupted SUPERSESSION
    never leaves v1 marked SUPERSEDED with its successor absent (no torn
    version chain); the retried registration succeeds cleanly."""
    inner = store_factory()
    inner.append_episodic(make_episodic_entry("ra-1"))
    inner.register_lesson(make_lesson(lesson_id="l1"))
    expected_digests = dict(inner.integrity_report().entry_digests)

    # Crash BEFORE commit → version absent, nothing partial, ledger intact.
    probe = _SemanticCrashProbe(
        inner, crash_on_lesson_id="l2", after_commit=False
    )
    assert isinstance(probe, ResearchMemoryStore)
    with pytest.raises(RuntimeError, match="simulated_crash_during_register"):
        probe.register_lesson(make_lesson(lesson_id="l2", created_at_utc=T2))
    assert probe.latest_lesson("l2") is None
    assert probe.lesson_history("l2") == ()
    assert probe.integrity_report().entry_digests == (
        ("ra-1", expected_digests["ra-1"]),
    )
    assert probe.integrity_report().lesson_version_counts == (("l1", 1),)
    assert verify_integrity(probe, expected_digests).verify_ok is True

    # Crash AFTER commit → version FULLY present and history-complete.
    probe2 = _SemanticCrashProbe(
        store_factory(), crash_on_lesson_id="l2", after_commit=True
    )
    probe2.append_episodic(make_episodic_entry("ra-1"))
    lesson_l2 = make_lesson(lesson_id="l2", created_at_utc=T2)
    with pytest.raises(RuntimeError, match="simulated_crash_after_commit"):
        probe2.register_lesson(lesson_l2)
    assert probe2.latest_lesson("l2") == lesson_l2
    assert probe2.lesson_history("l2") == (lesson_l2,)
    assert probe2.integrity_report().lesson_version_counts == (("l2", 1),)

    # Interrupted SUPERSESSION: v1 is NOT half-superseded; the retried
    # registration (no injected failure) succeeds cleanly.
    inner3 = store_factory()
    inner3.append_episodic(make_episodic_entry("ra-1"))
    inner3.register_lesson(make_lesson(lesson_id="l1"))
    probe3 = _SemanticCrashProbe(
        inner3, crash_on_lesson_id="l1", after_commit=False
    )
    v2 = make_lesson(
        lesson_id="l1", version=2, curation_basis="HUMAN_REVIEW",
        curated_by="reviewer-1", created_at_utc=T3,
    )
    with pytest.raises(RuntimeError, match="simulated_crash_during_register"):
        probe3.register_lesson(v2)
    latest = probe3.latest_lesson("l1")
    assert latest is not None and latest.version == 1 and latest.status == "ACTIVE"
    assert probe3.lesson_history("l1") == (latest,)
    assert probe3.integrity_report().lesson_version_counts == (("l1", 1),)
    # Retry with NO injected failure — directly on the store the probe
    # wraps; the crashed attempt left no residue blocking it.
    inner3.register_lesson(v2)
    history = probe3.lesson_history("l1")
    assert [l.version for l in history] == [1, 2]
    assert history[0].status == "SUPERSEDED" and history[1].status == "ACTIVE"
    assert probe3.integrity_report().lesson_version_counts == (("l1", 2),)


@_for_each_registered_store
def test_acc29_timestamp_discipline_boundary_future_no_expiry(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-6 + A3/A11 (WS5-T2 enrichment): temporal discipline at the store
    boundary. The ONLY temporal refusal at the record level is
    cutoff-after-recording (acc13); the boundary cutoff == recording
    instant is LEGAL. The store is clock-free: a record dated BEYOND every
    cutoff used here is neither refused nor flagged by any wall-clock
    comparison — accepting it at all is the proof that no clock is
    consulted — and its only honest treatment is PIT invisibility before
    its own recording instant. No retention window ages anything out: the
    oldest record stays fully retrievable after later appends (behavioral
    half of the no-expiry guarantee, alongside acc02's structural proof)."""
    store = store_factory()
    # Boundary-equal cutoffs are honest (knowing exactly up to the instant
    # of recording) and legal.
    boundary = make_episodic_entry(
        "ra-boundary", information_cutoff_utc=T1, recorded_at_utc=T1
    )
    store.append_episodic(boundary)
    # Far-future-dated record: legal; its cutoff (T3) precedes its recording.
    future = make_episodic_entry(
        "ra-future", information_cutoff_utc=T3, recorded_at_utc=_T_FUTURE
    )
    store.append_episodic(future)
    store.append_episodic(make_episodic_entry("ra-late", recorded_at_utc=T2))
    # The future-dated record is invisible at every earlier cutoff…
    assert [e.entry_id for e in store.episodic_available_at(T3)] == [
        "ra-boundary",
        "ra-late",
    ]
    # …and fully visible at its own instant (boundary-inclusive, insertion
    # order preserved).
    assert [e.entry_id for e in store.episodic_available_at(_T_FUTURE)] == [
        "ra-boundary",
        "ra-future",
        "ra-late",
    ]
    # No retention window: nothing ages out; every record — the oldest
    # included — remains fully retrievable through get and index views.
    for entry_id in ("ra-boundary", "ra-late", "ra-future"):
        got = store.get_episodic(entry_id)
        assert got is not None and got.entry_id == entry_id
    assert len(store.episodic_for_run("run-r1")) == 3
    # The ledger grew by appends only and verifies clean.
    expected = dict(store.integrity_report().entry_digests)
    assert verify_integrity(store, expected).verify_ok is True


@_for_each_registered_store
def test_acc30_empty_store_integrity_semantics_explicit(
    store_factory: Callable[[], ResearchMemoryStore],
) -> None:
    """AC-5/AC-12 (WS5-T2 enrichment): empty-store verification is
    EXPLICIT, not vacuous — an empty store's own report carries every field
    at its honest empty default (never None/missing) and is byte-identical
    across fresh empty stores; empty-vs-empty expectation verifies OK; an
    expectation over an empty store refuses EVERY expected id as missing
    (emptiness cannot hide a deletion); and an empty expectation over a
    POPULATED store is not a refusal (acc07's later-appends principle at
    the degenerate extreme — the report still honestly counts the store)."""
    store = store_factory()
    report = store.integrity_report()
    assert report.verify_ok is True
    assert report.entry_count == 0
    assert report.entry_digests == ()
    assert report.lesson_version_counts == ()
    assert report.mismatched_entry_ids == ()
    assert report.missing_entry_ids == ()
    assert report.refusal_reasons == ()
    # Empty vs empty: honestly OK, with the full explicit empty shape.
    empty_ok = verify_integrity(store, {})
    assert empty_ok.verify_ok is True
    assert empty_ok.entry_count == 0 and empty_ok.refusal_reasons == ()
    # Deterministic: two fresh empty stores report byte-identically.
    other = store_factory()
    assert canonical_research_memory_json(other.integrity_report()) == (
        canonical_research_memory_json(report)
    )
    # Expectation over an empty store: every expected id is a refusal —
    # emptiness never hides an append-only violation.
    refused = verify_integrity(
        store,
        {
            "ra-1": sha256_hex(
                canonical_research_memory_json(make_episodic_entry("ra-1"))
            )
        },
    )
    assert refused.verify_ok is False
    assert refused.missing_entry_ids == ("ra-1",)
    assert refused.mismatched_entry_ids == ()
    assert refused.refusal_reasons == ("expected_entry_missing_from_store",)
    # Empty expectation over a POPULATED store: not a refusal; the report
    # still honestly reflects the store's own records.
    store.append_episodic(make_episodic_entry("ra-1"))
    lax = verify_integrity(store, {})
    assert lax.verify_ok is True
    assert lax.entry_count == 1
    assert lax.entry_digests == store.integrity_report().entry_digests
