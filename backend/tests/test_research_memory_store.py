"""AI-3 store-level acceptance tests — ResearchMemoryStore protocol + kit.

Store-level mirror of the AI-3-M contract acceptance tests
(``tests/test_ai3_research_memory.py``): every protocol method is exercised
through ``InMemoryResearchMemoryStore``, which composes — never reimplements
— ``EpisodicRunArchive`` + ``SemanticLessonStore``. Derived from the same
corpus anchors as the contract layer (02:83-85, 02:159, 02:142, 06 §7,
03 §Memory, D-AI-28) plus the persistence decision brief constraints
A3/A11 (no update/delete/purge path; nothing expires out of the archive).

Scope honesty: this is the authorized PRE-DECISION kit for owner decisions
D1–D7 (all PENDING, none assumed). No concrete storage engine is exercised
here — the in-memory reference is the only implementation, by design.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.research_memory import EpisodicRunArtifact
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
    make_artifact_ref,
    make_episodic_entry,
    make_lesson,
    make_seeded_lesson_store,
    make_store,
)

#: The exact protocol surface — append/get/index/verify ONLY. The absence of
#: any update/delete/purge/rewrite member here is the structural append-only
#: proof at interface level (A3/A11).
EXPECTED_PROTOCOL_METHODS = {
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


# ---------------------------------------------------------------------------
# Protocol conformance + structural append-only proof
# ---------------------------------------------------------------------------


def test_store_satisfies_protocol_and_protocol_surface_is_exact() -> None:
    store = make_store()
    assert isinstance(store, ResearchMemoryStore)  # runtime_checkable
    observed = set(getattr(ResearchMemoryStore, "__protocol_attrs__"))
    assert observed == EXPECTED_PROTOCOL_METHODS
    for token in ("update", "delete", "purge", "expire", "rewrite", "prune", "remove"):
        assert not any(token in method for method in observed)


def test_store_public_surface_has_no_mutation_path() -> None:
    store = make_store(entries=(make_episodic_entry("ra-1"),))
    public = {name for name in dir(store) if not name.startswith("_")}
    assert EXPECTED_PROTOCOL_METHODS <= public
    for forbidden in (
        "update",
        "remove",
        "delete",
        "purge",
        "expire",
        "rewrite",
        "prune",
        "clear",
        "pop",
        "drop",
        "truncate",
        "vacuum",
    ):
        assert forbidden not in public


# ---------------------------------------------------------------------------
# Episodic view through the store (mirrors contract behaviors)
# ---------------------------------------------------------------------------


def test_episodic_append_get_roundtrip_and_frozen_records() -> None:
    store = make_store()
    entry = make_episodic_entry("ra-1")
    store.append_episodic(entry)
    got = store.get_episodic("ra-1")
    assert got == entry
    assert got is not None and got.entry_id == "ra-1"
    with pytest.raises(ValidationError):
        assert got is not None
        got.trust_state = "mutated"  # type: ignore[misc]
    assert store.integrity_report().entry_count == 1


def test_episodic_index_views_by_run_and_hypothesis() -> None:
    store = make_store(
        entries=(
            make_episodic_entry("ra-1"),
            make_episodic_entry("ra-2", run_id="run-r2", hypothesis_id=None),
            make_episodic_entry("ra-3", run_id="run-r1", hypothesis_id="hyp-8"),
        )
    )
    assert [e.entry_id for e in store.episodic_for_run("run-r1")] == ["ra-1", "ra-3"]
    assert [e.entry_id for e in store.episodic_for_hypothesis("hyp-7")] == ["ra-1"]
    assert [e.entry_id for e in store.episodic_for_hypothesis("hyp-8")] == ["ra-3"]
    assert store.episodic_for_hypothesis("hyp-7") == store.episodic_for_run("run-r1")[:1]


def test_episodic_available_at_point_in_time() -> None:
    store = make_store(
        entries=(
            make_episodic_entry("ra-1", recorded_at_utc=T1),
            make_episodic_entry("ra-2", recorded_at_utc=T2),
        )
    )
    assert [e.entry_id for e in store.episodic_available_at(T1)] == ["ra-1"]
    assert [e.entry_id for e in store.episodic_available_at(T2)] == ["ra-1", "ra-2"]
    assert store.episodic_available_at(T0) == ()  # nothing recorded before T1


def test_episodic_append_idempotent() -> None:
    store = make_store()
    entry = make_episodic_entry("ra-1")
    store.append_episodic(entry)
    store.append_episodic(entry)  # identical re-append: no-op, not a conflict
    report = store.integrity_report()
    assert report.entry_count == 1
    assert report.entry_digests == (("ra-1", sha256_hex(canonical_research_memory_json(entry))),)


def test_episodic_append_conflict_refused_state_unchanged() -> None:
    store = make_store(entries=(make_episodic_entry("ra-1"),))
    with pytest.raises(ValueError, match="episodic_archive_conflict"):
        store.append_episodic(make_episodic_entry("ra-1", trust_state="stale"))
    # Refused append rewrote nothing: the original record stands (history is
    # never rewritten), and the entry count did not grow.
    got = store.get_episodic("ra-1")
    assert got is not None and got.trust_state == "live"
    assert store.integrity_report().entry_count == 1


def test_unknown_ids_are_explicit_misses_fail_closed() -> None:
    # Documented honest wrap of the CONTRACT behavior: the contracts express
    # an unknown id as None / empty (NOT KeyError); the store mirrors that
    # exactly — an explicit miss, never a fabricated record.
    store = make_store()
    assert store.get_episodic("ghost") is None
    assert store.episodic_for_run("ghost") == ()
    assert store.episodic_for_hypothesis("ghost") == ()
    assert store.episodic_available_at(T3) == ()
    assert store.latest_lesson("ghost") is None
    assert store.lesson_history("ghost") == ()
    assert store.lessons_active_at(T3) == ()
    assert store.integrity_report().verify_ok is True
    assert store.integrity_report().entry_count == 0


# ---------------------------------------------------------------------------
# Semantic-lesson view through the store (mirrors contract behaviors)
# ---------------------------------------------------------------------------


def test_lesson_register_latest_history_supersede() -> None:
    store = make_store(entries=(make_episodic_entry("ra-1"),))
    store.register_lesson(make_lesson(lesson_id="l1"))
    latest = store.latest_lesson("l1")
    assert latest is not None and latest.version == 1 and latest.status == "ACTIVE"
    store.register_lesson(
        make_lesson(
            lesson_id="l1",
            version=2,
            statement="Refined after review.",
            created_at_utc=T2,
        )
    )
    latest = store.latest_lesson("l1")
    assert latest is not None and latest.version == 2
    history = store.lesson_history("l1")
    assert [l.version for l in history] == [1, 2]
    assert history[0].status == "SUPERSEDED"
    assert history[1].status == "ACTIVE"
    # History never rewritten: v1's statement survived supersession.
    assert history[0].statement == "Money-flow regime shifts precede breadth expansion by ~2 sessions."


def test_lesson_register_conflict_refused_state_unchanged() -> None:
    store = make_store(entries=(make_episodic_entry("ra-1"),))
    store.register_lesson(make_lesson(lesson_id="l1"))
    with pytest.raises(ValueError, match="lesson_version_not_increasing"):
        store.register_lesson(make_lesson(lesson_id="l1"))
    latest = store.latest_lesson("l1")
    assert latest is not None and latest.version == 1
    assert len(store.lesson_history("l1")) == 1
    with pytest.raises(ValueError, match="first_registered_lesson_version_must_be_one"):
        store.register_lesson(
            make_lesson(lesson_id="l9", version=2, supersedes_version=1)
        )
    assert store.latest_lesson("l9") is None  # refused registration stored nothing


def test_lessons_active_at_point_in_time_through_store() -> None:
    store = make_store(entries=(make_episodic_entry("ra-1"), make_episodic_entry("ra-2")))
    store.register_lesson(make_lesson(lesson_id="l1", created_at_utc=T1))
    store.register_lesson(
        make_lesson(lesson_id="l2", source_artifact_ids=("ra-2",), created_at_utc=T2)
    )
    # At T1: l1 active, l2 does not exist yet.
    assert [l.lesson_id for l in store.lessons_active_at(T1)] == ["l1"]
    # At T2: both active.
    assert {l.lesson_id for l in store.lessons_active_at(T2)} == {"l1", "l2"}
    # Supersede l1 with v2 at T2 (supersession is a content update via a NEW
    # version, not a removal): both lessons active at T2 ...
    store.register_lesson(
        make_lesson(lesson_id="l1", version=2, created_at_utc=T2)
    )
    assert {l.lesson_id for l in store.lessons_active_at(T2)} == {"l1", "l2"}
    # ... and at T1 the store honestly reports l1 as NOT active: its latest
    # version <= T1 carries the CURRENT status SUPERSEDED while its ACTIVE
    # v2 did not exist at T1 (conservative documented semantics, mirrored
    # from the contract-level PIT honesty test).
    assert [l.lesson_id for l in store.lessons_active_at(T1)] == []


def test_retired_lesson_history_preserved_through_store() -> None:
    # Retirement is exercised by seeding the store with contract-state built
    # through SemanticLessonStore's own lifecycle (the store protocol exposes
    # append/register only; retirement is a contract lifecycle operation that
    # appends a NEW terminal version — the store delegates it, never hides it).
    contract_store = make_seeded_lesson_store(make_lesson(lesson_id="l1"))
    contract_store = contract_store.register(
        make_lesson(lesson_id="l2", source_artifact_ids=("ra-1",))
    )
    contract_store = contract_store.retire("l2", retired_by="reviewer-1", at_utc=T3)
    store = make_store(entries=(make_episodic_entry("ra-1"),), lessons=contract_store)
    latest = store.latest_lesson("l2")
    assert latest is not None and latest.status == "RETIRED" and latest.version == 2
    history = store.lesson_history("l2")
    assert [l.version for l in history] == [1, 2]  # history preserved, not deleted
    assert history[0].status == "SUPERSEDED"
    assert history[-1].statement == history[0].statement  # retirement rewrote nothing
    assert {l.lesson_id for l in store.lessons_active_at(T3)} == {"l1"}


# ---------------------------------------------------------------------------
# Canonical serialization — determinism
# ---------------------------------------------------------------------------


def test_canonical_json_deterministic_across_constructions() -> None:
    a = make_episodic_entry("ra-1")
    b = make_episodic_entry("ra-1")  # independent construction, same content
    text_a1 = canonical_research_memory_json(a)
    text_a2 = canonical_research_memory_json(a)  # pure: byte-identical twice
    text_b = canonical_research_memory_json(b)
    assert text_a1 == text_a2
    assert text_a1 == text_b
    digest = sha256_hex(text_a1)
    assert digest == sha256_hex(text_a1.encode("utf-8").decode("utf-8"))
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    # Different content ⇒ different canonical bytes (digest is a real check).
    assert canonical_research_memory_json(make_episodic_entry("ra-1", trust_state="stale")) != text_a1
    assert sha256_hex(canonical_research_memory_json(make_episodic_entry("ra-1", trust_state="stale"))) != digest


def test_canonical_json_insertion_order_independent() -> None:
    # Pydantic model path: field order is schema-defined, so two artifacts
    # built with different kwarg orders canonically agree.
    base: dict[str, object] = dict(
        entry_id="ra-1",
        run_id="run-r1",
        run_kind="RESEARCH_HYPOTHESIS",
        hypothesis_id="hyp-7",
        artifact=make_artifact_ref(artifact_id="ra-1"),
        input_snapshot_sha256="c" * 64,
        trust_state="live",
        code_commit="d" * 40,
        dataset_version="ds-2026-10-18",
        policy_version="gov-1",
        information_cutoff_utc=T0,
        recorded_at_utc=T1,
    )
    e1 = EpisodicRunArtifact(**base)  # type: ignore[arg-type]
    e2 = EpisodicRunArtifact(**dict(reversed(list(base.items()))))  # type: ignore[arg-type]
    assert canonical_research_memory_json(e1) == canonical_research_memory_json(e2)
    assert sha256_hex(canonical_research_memory_json(e1)) == sha256_hex(
        canonical_research_memory_json(e2)
    )
    # Raw-dict path: nested key insertion order must not leak into output.
    left = canonical_research_memory_json({"x": 1, "y": {"b": 2, "a": 3}})
    right = canonical_research_memory_json({"y": {"a": 3, "b": 2}, "x": 1})
    assert left == right == '{"x":1,"y":{"a":3,"b":2}}'


def test_canonical_json_decimal_and_refusal_policy() -> None:
    # DECIMAL_AS_STRING policy: no binary-float drift may enter a digest.
    text = canonical_research_memory_json({"amount": Decimal("1.500"), "t": T1})
    assert text == '{"amount":"1.500","t":"%s"}' % T1.isoformat()
    # Fail-closed: NaN/Infinity refused (allow_nan=False), not silently
    # serialized into a lossy digest; non-serializable content refused too.
    with pytest.raises(ValueError):
        canonical_research_memory_json({"bad": float("nan")})
    with pytest.raises(TypeError):
        canonical_research_memory_json({"bad": object()})


# ---------------------------------------------------------------------------
# Integrity report + fail-closed verification
# ---------------------------------------------------------------------------


def test_integrity_report_shape_frozen_and_verify_ok() -> None:
    entry1 = make_episodic_entry("ra-1")
    entry2 = make_episodic_entry("ra-2", run_id="run-r2", hypothesis_id=None)
    store = make_store(entries=(entry1, entry2))
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
    assert report.lesson_version_counts == (("l0", 1), ("l1", 2))  # sorted, version-counted
    assert report.mismatched_entry_ids == () and report.missing_entry_ids == ()
    assert report.refusal_reasons == ()
    with pytest.raises(ValidationError):
        report.verify_ok = False  # type: ignore[misc]


def test_verify_integrity_ok_path_and_append_legality() -> None:
    store = make_store(entries=(make_episodic_entry("ra-1"), make_episodic_entry("ra-2")))
    expected = dict(store.integrity_report().entry_digests)
    result = verify_integrity(store, expected)
    assert result.verify_ok is True
    assert result.mismatched_entry_ids == () and result.missing_entry_ids == ()
    # Appends after the snapshot are LEGAL (append is the only legal change):
    # they grow the store but are not refusals.
    store.append_episodic(make_episodic_entry("ra-3", recorded_at_utc=T2))
    result_after = verify_integrity(store, expected)
    assert result_after.verify_ok is True
    assert result_after.entry_count == 3
    assert result_after.mismatched_entry_ids == () and result_after.missing_entry_ids == ()


def test_verify_integrity_refusal_on_tampered_digest() -> None:
    store = make_store(entries=(make_episodic_entry("ra-1"), make_episodic_entry("ra-2")))
    expected = dict(store.integrity_report().entry_digests)
    tampered = dict(expected)
    tampered["ra-2"] = ("0" if tampered["ra-2"][0] != "0" else "1") + tampered["ra-2"][1:]
    result = verify_integrity(store, tampered)  # returns a refusal — no exception
    assert result.verify_ok is False
    assert result.mismatched_entry_ids == ("ra-2",)
    assert result.missing_entry_ids == ()
    assert "digest_mismatch" in result.refusal_reasons
    # Untampered entry stays clean and the store content is untouched.
    assert ("ra-1", expected["ra-1"]) in result.entry_digests
    assert result.entry_count == 2


def test_verify_integrity_refusal_on_missing_entry() -> None:
    store = make_store(entries=(make_episodic_entry("ra-1"),))
    # Expectation recorded when ra-2 existed → its absence now is a DELETION
    # (append-only violation) and must be refused, not silently tolerated.
    expected = {
        "ra-1": sha256_hex(canonical_research_memory_json(make_episodic_entry("ra-1"))),
        "ra-2": sha256_hex(canonical_research_memory_json(make_episodic_entry("ra-2"))),
    }
    result = verify_integrity(store, expected)
    assert result.verify_ok is False
    assert result.missing_entry_ids == ("ra-2",)
    assert result.mismatched_entry_ids == ()
    assert "expected_entry_missing_from_store" in result.refusal_reasons


def test_verify_integrity_never_raises_on_store_failure() -> None:
    class _CorruptAdapter:
        def integrity_report(self) -> ResearchMemoryIntegrityReport:
            raise RuntimeError("corrupt_record")

    result = verify_integrity(_CorruptAdapter(), {"ra-1": "0" * 64})
    assert result.verify_ok is False
    assert result.refusal_reasons == ("verify_refused:RuntimeError",)
    assert result.entry_count == 0
    assert result.mismatched_entry_ids == () and result.missing_entry_ids == ()


# ---------------------------------------------------------------------------
# Composition honesty — the store IS the contracts underneath
# ---------------------------------------------------------------------------


def test_store_views_are_contract_records_not_copies() -> None:
    # The in-memory reference delegates: returned records are the contracts'
    # own frozen models, and episodic ordering equals the archive's
    # insertion order (append-only growth, deterministic views).
    store = InMemoryResearchMemoryStore()
    entries = (make_episodic_entry("ra-1"), make_episodic_entry("ra-2", run_id="run-r2"))
    for e in entries:
        store.append_episodic(e)
    assert all(isinstance(e, EpisodicRunArtifact) for e in store.episodic_available_at(T3))
    assert [e.entry_id for e in store.episodic_available_at(T3)] == ["ra-1", "ra-2"]
    report = store.integrity_report()
    assert isinstance(report, ResearchMemoryIntegrityReport)
    assert [eid for eid, _ in report.entry_digests] == ["ra-1", "ra-2"]
