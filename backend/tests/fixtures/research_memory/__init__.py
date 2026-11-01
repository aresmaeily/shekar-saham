"""Deterministic research-memory fixture builders (AI-3 store kit).

Fixture-domain ONLY: these builders exist so store-level tests construct
records with explicit, deterministic inputs — every timestamp is a parameter
with a fixed default, every digest/commit is a fixed hex constant, and
nothing is read from a clock, the environment, or a RNG. Two constructions
with the same arguments are equal records, and therefore canonically
serialize byte-identically.

These fixtures reuse — never modify — the contract layer
(``app/domain/research_memory.py``) and the store interface
(``app/domain/research_memory_store.py``).

Fixed sentinel constants (NOT digests of real content — they are stable
64/40-hex fixture constants, honestly used as opaque identifiers):
- SHA_A / SHA_B : input-snapshot / artifact sha256-shaped constants;
- COMMIT_A      : 40-hex code-commit-shaped constant.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.research_memory import (
    EpisodicRunArchive,
    EpisodicRunArtifact,
    SemanticLesson,
    SemanticLessonStore,
    derive_lesson,
)
from app.domain.research_memory_store import InMemoryResearchMemoryStore
from app.domain.run_governance import ArtifactRef

UTC = timezone.utc

#: Fixed timeline (explicit, deterministic; T0 < T1 < T2 < T3).
T0 = datetime(2026, 10, 18, 13, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 18, 14, 0, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 18, 15, 0, 0, tzinfo=UTC)
T3 = datetime(2026, 10, 18, 16, 0, 0, tzinfo=UTC)

#: Fixed hex-shaped constants (opaque fixture sentinels, deterministic).
SHA_A = "c" * 64
SHA_B = "e" * 64
COMMIT_A = "d" * 40

__all__ = [
    "COMMIT_A",
    "SHA_A",
    "SHA_B",
    "T0",
    "T1",
    "T2",
    "T3",
    "UTC",
    "make_artifact_ref",
    "make_episodic_entry",
    "make_lesson",
    "make_lesson_via_derive",
    "make_seeded_lesson_store",
    "make_store",
]


def make_artifact_ref(
    artifact_id: str = "ra-1",
    *,
    kind: str = "research_result",
    ref: str | None = None,
    sha256: str | None = SHA_A,
) -> ArtifactRef:
    """Deterministic ``ArtifactRef`` (contract record)."""
    return ArtifactRef(
        artifact_id=artifact_id,
        kind=kind,
        ref=ref if ref is not None else f"artifact://{artifact_id}",
        sha256=sha256,
    )


def make_episodic_entry(entry_id: str = "ra-1", **over: object) -> EpisodicRunArtifact:
    """Deterministic ``EpisodicRunArtifact``.

    All timestamps are explicit parameters (fixed defaults); any keyword in
    ``over`` overrides the deterministic base. Unless ``artifact`` is
    explicitly overridden, the artifact reference's ``artifact_id`` tracks
    the entry id so fixtures stay internally coherent.
    """
    base: dict[str, object] = dict(
        entry_id=entry_id,
        run_id="run-r1",
        run_kind="RESEARCH_HYPOTHESIS",
        hypothesis_id="hyp-7",
        input_snapshot_sha256=SHA_A,
        trust_state="live",
        code_commit=COMMIT_A,
        dataset_version="ds-2026-10-18",
        policy_version="gov-1",
        information_cutoff_utc=T0,
        recorded_at_utc=T1,
    )
    if "artifact" not in over:
        base["artifact"] = make_artifact_ref(
            artifact_id=str(over.get("artifact_id", entry_id))
        )
    base.update(over)
    return EpisodicRunArtifact(**base)  # type: ignore[arg-type]


def make_lesson_via_derive(
    archive: EpisodicRunArchive,
    *,
    lesson_id: str = "l1",
    statement: str = "Money-flow regime shifts precede breadth expansion by ~2 sessions.",
    source_artifact_ids: tuple[str, ...] = ("ra-1",),
    curated_by: str = "deterministic-rule:lesson-r1",
    curation_basis: str = "DETERMINISTIC_RULE",
    at_utc: datetime = T1,
    run_id: str | None = None,
) -> SemanticLesson:
    """Deterministic lesson v1 derived THROUGH the contract factory
    (``derive_lesson``), so the archive-citation gate is exercised."""
    return derive_lesson(
        archive,
        lesson_id=lesson_id,
        statement=statement,
        source_artifact_ids=source_artifact_ids,
        curated_by=curated_by,
        curation_basis=curation_basis,  # type: ignore[arg-type]
        at_utc=at_utc,
        run_id=run_id,
    )


def make_lesson(
    archive: EpisodicRunArchive | None = None,
    lesson_id: str = "l1",
    **over: object,
) -> SemanticLesson:
    """Deterministic ``SemanticLesson`` (v1 by default, ACTIVE).

    ``archive`` is accepted for signature symmetry with
    ``make_lesson_via_derive`` and the contract-level test helpers; this
    builder constructs the record directly (same shapes as the contract
    acceptance tests), with every timestamp an explicit parameter. A
    ``version`` override without an explicit ``supersedes_version`` defaults
    the parent to ``version - 1`` (valid chain shape).
    """
    del archive
    base: dict[str, object] = dict(
        lesson_id=lesson_id,
        version=1,
        statement="Money-flow regime shifts precede breadth expansion by ~2 sessions.",
        source_artifact_ids=("ra-1",),
        curated_by="deterministic-rule:lesson-r1",
        curation_basis="DETERMINISTIC_RULE",
        created_at_utc=T1,
    )
    if over.get("version", 1) != 1 and "supersedes_version" not in over:
        base["supersedes_version"] = int(over["version"]) - 1  # type: ignore[arg-type]
    base.update(over)
    return SemanticLesson(**base)  # type: ignore[arg-type]


def make_seeded_lesson_store(*lessons: SemanticLesson) -> SemanticLessonStore:
    """Fold lessons through the contract store's own register lifecycle."""
    store = SemanticLessonStore()
    for lesson in lessons:
        store = store.register(lesson)
    return store


def make_store(
    *,
    entries: tuple[EpisodicRunArtifact, ...] = (),
    lessons: SemanticLessonStore | None = None,
) -> InMemoryResearchMemoryStore:
    """Deterministic ``InMemoryResearchMemoryStore`` seeded through the
    contract APIs (append/register only — the same discipline any adapter
    must support)."""
    store = InMemoryResearchMemoryStore(lessons=lessons)
    for entry in entries:
        store.append_episodic(entry)
    return store
