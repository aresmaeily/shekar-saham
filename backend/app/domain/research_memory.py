"""Research Memory contracts for RADAR BOURSE (AI-3-M).

Corpus loci (2026-10-02 amendment corpus, byte-verified):
- 02_EXECUTION_ROADMAP lines 83–85: "AI-3 --- Research Memory — Episodic
  immutable run artifacts plus curated/versioned semantic memory."
- 02 line 159: "Episodic research artifacts remain immutable; semantic
  lessons remain curated/versioned."
- 02 line 142: "Every conclusion must identify its information cutoff."
- 02 line 198: governed actions carry "traceable run identity, versions,
  human approval state and explicit limitations".
- 06 §7: "All results link to code/config/data versions and immutable run
  artifacts."
- 02_PRODUCT… §Memory + rule 12; 03 §Memory; D-AI-22/D-AI-28.

Relationship to prior contract layers: AI1-GC `memory_interfaces` delivered
the memory INTERFACE contracts; AI-3-M delivers the research-memory SYSTEM
contracts (episodic run-artifact archive + curated semantic lessons derived
FROM that archive). Persistence technology is deliberately NOT specified by
the corpus — the stores here are deterministic in-memory structures; the
persistence integration is an owner-environment decision (see the AI-3-M
scope derivation §3).

Contract/domain only: frozen records, deterministic, clock-free (timestamps
passed in), no I/O, no network, no LLM, no route, no config change, no
existing module modified.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.run_governance import ArtifactRef

CurationBasis = Literal["DETERMINISTIC_RULE", "HUMAN_REVIEW"]
LessonStatus = Literal["ACTIVE", "SUPERSEDED", "RETIRED"]

#: Closed lifecycle-operation set (03 §Memory): memory operations are
#: epistemic only — no operation kind that could express a production
#: change exists.
MemoryLifecycleOperation = Literal[
    "APPEND_EPISODIC",
    "DERIVE_LESSON",
    "SUPERSEDE_LESSON",
    "RETIRE_LESSON",
]


# ---------------------------------------------------------------------------
# D1 — episodic immutable run artifacts
# ---------------------------------------------------------------------------


class EpisodicRunArtifact(BaseModel):
    """Immutable archive record of one research run's artifact (02:83,159).

    Binds the artifact reference to its full provenance: run identity,
    hypothesis (when preregistered), input snapshot, trust state, and the
    code/config/data version linkage required by 06 §7. The information
    cutoff is MANDATORY (02 line 142): every archived conclusion states the
    instant up to which its information was available.
    """

    model_config = ConfigDict(frozen=True)

    entry_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=128)
    run_kind: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    hypothesis_id: str | None = None
    artifact: ArtifactRef
    input_snapshot_sha256: str = Field(min_length=64, max_length=64)
    trust_state: str = Field(min_length=1, max_length=64)
    code_commit: str | None = None
    dataset_version: str | None = None
    policy_version: str = Field(min_length=1)
    information_cutoff_utc: datetime
    recorded_at_utc: datetime
    notes: str = ""

    @field_validator("information_cutoff_utc", "recorded_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("input_snapshot_sha256")
    @classmethod
    def _hex64(cls, v: str) -> str:
        if any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("input_snapshot_sha256_must_be_hex")
        return v.lower()

    @field_validator("code_commit")
    @classmethod
    def _commit_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) != 40 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("code_commit_must_be_40_hex")
        return v.lower()

    @model_validator(mode="after")
    def _provenance_honesty(self) -> "EpisodicRunArtifact":
        # 06 §7: results link to code/config/data versions — when a version
        # is unknown it stays explicitly None; it is never invented. And per
        # 02:142 the cutoff states up to which information was available:
        # an artifact whose cutoff lies AFTER its own recording would claim
        # awareness of information beyond its existence — refused
        # (anti-look-ahead; AI3M-01 comment-direction fix, behavior
        # unchanged and test-pinned).
        if self.information_cutoff_utc > self.recorded_at_utc:
            raise ValueError("information_cutoff_after_recording")
        return self


class EpisodicRunArchive:
    """Append-only archive of episodic run artifacts (02:83,159; D-AI-28).

    Immutability is structural: the only operations are append/get/index —
    there is NO update, delete, retention-purge or rewrite path (episodic
    research evidence is immutable; nothing "expires out" of the archive).
    """

    def __init__(self, entries: tuple[EpisodicRunArtifact, ...] = ()) -> None:
        self._entries: tuple[EpisodicRunArtifact, ...] = entries

    @property
    def entries(self) -> tuple[EpisodicRunArtifact, ...]:
        return self._entries

    def get(self, entry_id: str) -> EpisodicRunArtifact | None:
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    def for_run(self, run_id: str) -> tuple[EpisodicRunArtifact, ...]:
        return tuple(e for e in self._entries if e.run_id == run_id)

    def for_hypothesis(self, hypothesis_id: str) -> tuple[EpisodicRunArtifact, ...]:
        return tuple(e for e in self._entries if e.hypothesis_id == hypothesis_id)

    def available_at(self, cutoff: datetime) -> tuple[EpisodicRunArtifact, ...]:
        """Point-in-time view (02 line 142): artifacts recorded at or
        before the cutoff. Deterministic; clock-free."""
        c = ensure_utc(cutoff)
        return tuple(e for e in self._entries if e.recorded_at_utc <= c)

    def append(self, entry: EpisodicRunArtifact) -> "EpisodicRunArchive":
        existing = self.get(entry.entry_id)
        if existing is not None:
            if existing == entry:
                return self
            raise ValueError("episodic_archive_conflict")
        return EpisodicRunArchive(self._entries + (entry,))


# ---------------------------------------------------------------------------
# D2 — curated, versioned semantic lessons derived from episodic evidence
# ---------------------------------------------------------------------------


class SemanticLesson(BaseModel):
    """One curated, versioned lesson (02:83,159; D-AI-28).

    A lesson MUST cite the episodic artifacts it was derived from
    (traceability: lessons never appear from nothing). Curation names its
    basis — a deterministic rule or a human reviewer. Version 1 supersedes
    nothing; later versions must name their parent version.
    """

    model_config = ConfigDict(frozen=True)

    lesson_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    version: int = Field(ge=1)
    supersedes_version: int | None = None
    statement: str = Field(min_length=1, max_length=2000)
    source_artifact_ids: tuple[str, ...] = Field(min_length=1)
    curated_by: str = Field(min_length=1, max_length=128)
    curation_basis: CurationBasis
    status: LessonStatus = "ACTIVE"
    created_at_utc: datetime
    run_id: str | None = None
    notes: str = ""

    @field_validator("created_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("source_artifact_ids")
    @classmethod
    def _distinct_sources(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("source_artifact_ids_duplicates")
        return v

    @model_validator(mode="after")
    def _version_chain(self) -> "SemanticLesson":
        if self.version == 1 and self.supersedes_version is not None:
            raise ValueError("version_one_must_not_supersede")
        if self.version > 1:
            if self.supersedes_version is None:
                raise ValueError("later_version_requires_superseded_version")
            if self.supersedes_version >= self.version:
                raise ValueError("superseded_version_must_be_earlier")
        return self


def derive_lesson(
    archive: EpisodicRunArchive,
    *,
    lesson_id: str,
    statement: str,
    source_artifact_ids: tuple[str, ...],
    curated_by: str,
    curation_basis: CurationBasis,
    at_utc: datetime,
    run_id: str | None = None,
) -> SemanticLesson:
    """Deterministic curation factory (D-AI-28; 03 §Memory).

    Every cited source artifact MUST exist in the archive — a lesson can
    only be derived from archived episodic evidence (traceability; nothing
    is invented). All timestamps are passed in; nothing is read from a
    clock.
    """
    missing = [a for a in source_artifact_ids if archive.get(a) is None]
    if missing:
        raise ValueError(f"lesson_cites_unknown_artifacts:{','.join(missing)[:200]}")
    return SemanticLesson(
        lesson_id=lesson_id,
        version=1,
        statement=statement,
        source_artifact_ids=tuple(dict.fromkeys(source_artifact_ids)),
        curated_by=curated_by,
        curation_basis=curation_basis,
        created_at_utc=at_utc,
        run_id=run_id,
    )


class SemanticLessonStore:
    """Versioned store of curated lessons (02:83,159; D-AI-28).

    Same append-only discipline as the AI1-GC semantic store, extended with
    the archive-citation rule and an explicit RETIRE lifecycle (retirement
    is a NEW terminal version — history is never rewritten; no delete
    path exists).
    """

    def __init__(self, lessons: tuple[SemanticLesson, ...] = ()) -> None:
        self._lessons: tuple[SemanticLesson, ...] = lessons

    @property
    def lessons(self) -> tuple[SemanticLesson, ...]:
        return self._lessons

    def latest(self, lesson_id: str) -> SemanticLesson | None:
        best: SemanticLesson | None = None
        for l in self._lessons:
            if l.lesson_id == lesson_id and (best is None or l.version > best.version):
                best = l
        return best

    def history(self, lesson_id: str) -> tuple[SemanticLesson, ...]:
        return tuple(
            sorted(
                (l for l in self._lessons if l.lesson_id == lesson_id),
                key=lambda l: l.version,
            )
        )

    def register(self, lesson: SemanticLesson) -> "SemanticLessonStore":
        current = self.latest(lesson.lesson_id)
        if current is not None:
            if current.version >= lesson.version:
                raise ValueError("lesson_version_not_increasing")
            if current.status != "ACTIVE":
                raise ValueError("cannot_extend_non_active_lesson")
            if lesson.supersedes_version != current.version:
                raise ValueError("lesson_supersession_parent_mismatch")
            superseded = SemanticLesson(**{**current.model_dump(), "status": "SUPERSEDED"})
            kept = tuple(
                l
                for l in self._lessons
                if not (l.lesson_id == lesson.lesson_id and l.version == current.version)
            )
            return SemanticLessonStore(kept + (superseded, lesson))
        if lesson.version != 1:
            raise ValueError("first_registered_lesson_version_must_be_one")
        return SemanticLessonStore(self._lessons + (lesson,))

    def retire(
        self, lesson_id: str, *, retired_by: str, at_utc: datetime
    ) -> "SemanticLessonStore":
        """Explicit retirement (lifecycle honesty): appends a NEW terminal
        RETIRED version carrying the same statement; nothing is deleted."""
        current = self.latest(lesson_id)
        if current is None:
            raise ValueError("retire_unknown_lesson")
        if current.status != "ACTIVE":
            raise ValueError("retire_requires_active_lesson")
        retired = SemanticLesson(
            **{
                **current.model_dump(),
                "version": current.version + 1,
                "supersedes_version": current.version,
                "status": "RETIRED",
                "curated_by": retired_by,
                "created_at_utc": ensure_utc(at_utc),
            }
        )
        return self.register(retired)


def lessons_active_at(store: SemanticLessonStore, cutoff: datetime) -> tuple[SemanticLesson, ...]:
    """Point-in-time view of active lessons (02 line 142).

    Returns the latest version ≤ cutoff of every lesson whose current
    status (at that latest version) is ACTIVE. Superseded and retired
    lessons are excluded; lessons created after the cutoff are excluded.
    Deterministic; clock-free.
    """
    c = ensure_utc(cutoff)
    active: list[SemanticLesson] = []
    lesson_ids = {l.lesson_id for l in store.lessons}
    for lesson_id in lesson_ids:
        eligible = [
            l for l in store.history(lesson_id) if l.created_at_utc <= c
        ]
        if not eligible:
            continue
        latest = eligible[-1]
        if latest.status == "ACTIVE":
            active.append(latest)
    return tuple(sorted(active, key=lambda l: (l.lesson_id, l.version)))
