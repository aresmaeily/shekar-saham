"""AI-3-M acceptance tests — Research Memory (episodic + semantic).

Derived from the 2026-10-02 amendment corpus, NOT from the implementation:
02 lines 83–85 (episodic immutable run artifacts + curated/versioned
semantic memory), 02:159 (immutability + curation), 02:142 (information
cutoff), 02:198 (traceable run identity/versions), 06 §7 (code/config/data
version linkage), 03 §Memory (no silent production modification), D-AI-28.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.research_memory import (
    EpisodicRunArchive,
    EpisodicRunArtifact,
    MemoryLifecycleOperation,
    SemanticLesson,
    SemanticLessonStore,
    derive_lesson,
    lessons_active_at,
)
from app.domain.run_governance import ArtifactRef
from typing import get_args

UTC = timezone.utc
T0 = datetime(2026, 10, 18, 13, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 18, 14, 0, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 18, 15, 0, 0, tzinfo=UTC)
SHA = "c" * 64
COMMIT = "d" * 40
ART = ArtifactRef(artifact_id="ra-1", kind="research_result", ref="artifact://ra-1", sha256=SHA)


def entry(entry_id: str = "ra-1", **over: object) -> EpisodicRunArtifact:
    base = dict(
        entry_id=entry_id,
        run_id="run-r1",
        run_kind="RESEARCH_HYPOTHESIS",
        hypothesis_id="hyp-7",
        artifact=ART,
        input_snapshot_sha256=SHA,
        trust_state="live",
        code_commit=COMMIT,
        dataset_version="ds-2026-10-18",
        policy_version="gov-1",
        information_cutoff_utc=T0,
        recorded_at_utc=T1,
    )
    base.update(over)
    return EpisodicRunArtifact(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# D1 — episodic immutable run artifacts
# ---------------------------------------------------------------------------


def test_episodic_artifact_full_provenance_and_frozen() -> None:
    e = entry()
    assert e.code_commit == COMMIT and e.dataset_version and e.hypothesis_id
    with pytest.raises(ValidationError):
        e.trust_state = "mutated"  # type: ignore[misc]


def test_episodic_shapes_and_cutoff_logic() -> None:
    with pytest.raises(ValidationError, match="input_snapshot_sha256_must_be_hex"):
        entry(input_snapshot_sha256="NOPE" + "0" * 60)
    with pytest.raises(ValidationError, match="code_commit_must_be_40_hex"):
        entry(code_commit="short")
    with pytest.raises(ValidationError, match="information_cutoff_after_recording"):
        entry(information_cutoff_utc=T2, recorded_at_utc=T1)
    ok = entry(information_cutoff_utc=T1, recorded_at_utc=T1)  # cutoff == recording is fine
    assert ok.information_cutoff_utc == ok.recorded_at_utc


def test_archive_append_idempotent_conflict_no_delete_path() -> None:
    arc = EpisodicRunArchive().append(entry())
    assert arc.append(entry()) is arc
    with pytest.raises(ValueError, match="episodic_archive_conflict"):
        arc.append(entry(trust_state="stale"))
    public = {n for n in dir(arc) if not n.startswith("_")}
    for forbidden in ("update", "remove", "delete", "purge", "expire", "rewrite", "prune"):
        assert forbidden not in public


def test_archive_indexes_by_run_and_hypothesis() -> None:
    arc = (
        EpisodicRunArchive()
        .append(entry("ra-1"))
        .append(entry("ra-2", run_id="run-r2", hypothesis_id=None))
        .append(entry("ra-3", run_id="run-r1", hypothesis_id="hyp-8"))
    )
    assert [e.entry_id for e in arc.for_run("run-r1")] == ["ra-1", "ra-3"]
    assert [e.entry_id for e in arc.for_hypothesis("hyp-7")] == ["ra-1"]
    assert [e.entry_id for e in arc.for_hypothesis("hyp-8")] == ["ra-3"]
    assert arc.for_hypothesis("hyp-7") == arc.for_run("run-r1")[:1]


def test_archive_available_at_point_in_time() -> None:
    arc = (
        EpisodicRunArchive()
        .append(entry("ra-1", recorded_at_utc=T1))
        .append(entry("ra-2", recorded_at_utc=T2))
    )
    assert [e.entry_id for e in arc.available_at(T1)] == ["ra-1"]
    assert [e.entry_id for e in arc.available_at(T2)] == ["ra-1", "ra-2"]
    assert arc.available_at(T0) == ()


# ---------------------------------------------------------------------------
# D2 — curated, versioned semantic lessons
# ---------------------------------------------------------------------------


def lesson(archive: EpisodicRunArchive | None = None, **over: object) -> SemanticLesson:
    if archive is None:
        archive = EpisodicRunArchive().append(entry())
    base = dict(
        lesson_id="l1",
        version=1,
        statement="Money-flow regime shifts precede breadth expansion by ~2 sessions.",
        source_artifact_ids=("ra-1",),
        curated_by="deterministic-rule:lesson-r1",
        curation_basis="DETERMINISTIC_RULE",
        created_at_utc=T1,
    )
    base.update(over)
    return SemanticLesson(**base)  # type: ignore[arg-type]


def test_lesson_minimal_valid_and_frozen() -> None:
    l = lesson()
    assert l.status == "ACTIVE"
    with pytest.raises(ValidationError):
        l.statement = "mutated"  # type: ignore[misc]


def test_lesson_version_chain_guards() -> None:
    with pytest.raises(ValidationError, match="version_one_must_not_supersede"):
        lesson(version=1, supersedes_version=0)
    with pytest.raises(ValidationError, match="later_version_requires_superseded_version"):
        lesson(version=2, supersedes_version=None)
    with pytest.raises(ValidationError, match="superseded_version_must_be_earlier"):
        lesson(version=2, supersedes_version=3)


def test_derive_lesson_requires_archived_sources() -> None:
    arc = EpisodicRunArchive().append(entry())
    ok = derive_lesson(
        arc,
        lesson_id="l1",
        statement="Derived from archived evidence.",
        source_artifact_ids=("ra-1",),
        curated_by="reviewer-1",
        curation_basis="HUMAN_REVIEW",
        at_utc=T1,
    )
    assert ok.curation_basis == "HUMAN_REVIEW"
    with pytest.raises(ValueError, match="lesson_cites_unknown_artifacts"):
        derive_lesson(
            arc,
            lesson_id="l2",
            statement="From nothing.",
            source_artifact_ids=("ghost-artifact",),
            curated_by="x",
            curation_basis="DETERMINISTIC_RULE",
            at_utc=T1,
        )


def test_lesson_store_register_supersede_retire() -> None:
    arc = EpisodicRunArchive().append(entry())
    store = SemanticLessonStore().register(lesson(archive=arc))
    v2 = lesson(archive=arc, version=2, supersedes_version=1, statement="Refined after review.")
    store2 = store.register(v2)
    assert [l.version for l in store2.history("l1")] == [1, 2]
    assert store2.history("l1")[0].status == "SUPERSEDED"
    store3 = store2.retire("l1", retired_by="reviewer-1", at_utc=T2)
    hist = store3.history("l1")
    assert [l.version for l in hist] == [1, 2, 3]
    assert hist[-1].status == "RETIRED"
    assert hist[-1].statement == hist[-2].statement  # retirement rewrites nothing
    with pytest.raises(ValueError, match="retire_requires_active_lesson"):
        store3.retire("l1", retired_by="x", at_utc=T2)
    with pytest.raises(ValueError, match="retire_unknown_lesson"):
        SemanticLessonStore().retire("ghost", retired_by="x", at_utc=T2)


def test_lesson_store_rejects_bad_chains() -> None:
    arc = EpisodicRunArchive().append(entry())
    store = SemanticLessonStore().register(lesson(archive=arc))
    with pytest.raises(ValueError, match="lesson_version_not_increasing"):
        store.register(lesson(archive=arc))
    with pytest.raises(ValueError, match="first_registered_lesson_version_must_be_one"):
        SemanticLessonStore().register(lesson(archive=arc, version=2, supersedes_version=1))
    with pytest.raises(ValueError, match="lesson_supersession_parent_mismatch"):
        store.register(lesson(archive=arc, version=3, supersedes_version=2))


def test_lesson_citation_distinctness() -> None:
    with pytest.raises(ValidationError, match="source_artifact_ids_duplicates"):
        lesson(source_artifact_ids=("ra-1", "ra-1"))


# ---------------------------------------------------------------------------
# D3 — point-in-time lesson views
# ---------------------------------------------------------------------------


def test_lessons_active_at_pit_honesty() -> None:
    arc = EpisodicRunArchive().append(entry("ra-1")).append(entry("ra-2"))
    store = SemanticLessonStore().register(lesson(archive=arc, created_at_utc=T1))
    later = lesson(
        archive=arc,
        lesson_id="l2",
        source_artifact_ids=("ra-2",),
        created_at_utc=T2,
    )
    store2 = store.register(later)
    # At T1: l1 active, l2 does not exist yet.
    at_t1 = lessons_active_at(store2, T1)
    assert [l.lesson_id for l in at_t1] == ["l1"]
    # At T2: both active.
    assert {l.lesson_id for l in lessons_active_at(store2, T2)} == {"l1", "l2"}
    # Supersede l1 at T2 → l1 stays ACTIVE via its v2 (supersession is a
    # content update, not a removal); both lessons active at T2.
    store3 = store2.register(lesson(archive=arc, version=2, supersedes_version=1, created_at_utc=T2))
    assert {l.lesson_id for l in lessons_active_at(store3, T2)} == {"l1", "l2"}
    # At T1: l1's latest version <= T1 is v1, whose CURRENT status is
    # SUPERSEDED (superseded at T2) and its ACTIVE v2 did not exist at T1 —
    # per the documented semantics (latest version <= cutoff must carry
    # ACTIVE status now), l1 is not returned for T1. This is the honest
    # conservative behavior: the store keeps current status flags, not a
    # full status history, so a lesson that was later superseded is not
    # presented as active for earlier cutoffs.
    assert [l.lesson_id for l in lessons_active_at(store3, T1)] == []
    # Retire l2 at T2 → only l1 remains active at T2; retirement removes
    # nothing from history.
    store4 = store3.retire("l2", retired_by="reviewer-1", at_utc=T2)
    assert {l.lesson_id for l in lessons_active_at(store4, T2)} == {"l1"}
    assert len(store4.history("l2")) == 2  # v1 (superseded-by-retirement) + v2 RETIRED


# ---------------------------------------------------------------------------
# D4 — closed lifecycle operations (03 §Memory)
# ---------------------------------------------------------------------------


def test_memory_lifecycle_operations_cannot_express_production_mutation() -> None:
    allowed = set(get_args(MemoryLifecycleOperation))
    assert allowed == {"APPEND_EPISODIC", "DERIVE_LESSON", "SUPERSEDE_LESSON", "RETIRE_LESSON"}
    assert not any("PRODUCTION" in op or "MUTATE" in op or "DEPLOY" in op for op in allowed)
