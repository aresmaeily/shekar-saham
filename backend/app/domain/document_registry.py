"""AI-6 append-only ingested-document version ledger for RADAR BOURSE.

Corpus loci (2026-10-02 amendment corpus; see also
AI4_AI7_P343_DEPENDENCY_MATRIX.md §AI-6):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 161-170: AI-6/P8 required
  capabilities include "filing ingestion + document version tracking" and
  restatement handling; "AI must never invent missing financial values or
  silently reconcile contradictory sources."
- 02 line 194: acceptance evidence for external/fundamental intelligence —
  point-in-time source records and restatement handling.
- 06 charter §3: publication time recorded separately from retrieval time;
  "restatements create new versions."
- 03_AI_GOVERNANCE_BOUNDARIES / D-AI-33: facts keep version/restatement
  state; contradictory sources stay explicit.
- Dependency matrix §AI-6 "Authorized NOW": contract design (pre-G2 class).

Design (additive to the delivered AI-6 contract layer):
- ``DocumentVersion`` reuses ``external_intelligence.TrustLabel`` directly —
  no parallel trust vocabulary; trust is structurally UNTRUSTED at this
  layer and no upgrade path exists here.
- ``DocumentLedger`` is an append-only value object (``register`` /
  ``register_re_retrieval`` return NEW ledgers; no update, delete, edit or
  purge/retention path exists — episodic evidence is never purged here);
- duplicate sha256 per doc_key is refused UNLESS an honest re-retrieval is
  recorded via the explicit ``DocumentReRetrieval`` record class (same
  bytes re-fetched — filed as a retrieval fact, never as a new version);
- supersede chain validation: a restatement must reference an existing
  earlier version of the same doc_key;
- point-in-time retrieval: ``versions_as_of(ts)`` filters by
  ``published_at_utc`` (publication time, never retrieval time — 06 §3);
- unknown doc_key is fail-closed (``unknown_doc_key``), never an empty list;
- ``integrity_digest()`` is a deterministic SHA-256 over the canonical
  serialization of the whole ledger.

No network, no I/O, no clock reads, no LLM. All timestamps are arguments.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import ensure_utc
from app.domain.external_intelligence import TrustLabel

__all__ = [
    "DocumentVersion",
    "DocumentReRetrieval",
    "DocumentLedger",
]

_SHA256_ALPHABET = "0123456789abcdef"


def _sha256_shape(v: str, code: str) -> str:
    if len(v) != 64 or any(c not in _SHA256_ALPHABET for c in v.lower()):
        raise ValueError(code)
    return v.lower()


class DocumentVersion(BaseModel):
    """One immutable version of one ingested document (AI-6 contract).

    ``trust_label`` is the canonical AI-6 vocabulary (``UNTRUSTED`` only —
    re-imported, not forked). ``supersedes_version_index`` is mandatory for
    a restatement and forbidden otherwise (06 §3: restatements create new
    versions); the referenced index is validated against the ledger at
    registration time (ledger-level chain discipline).
    """

    model_config = ConfigDict(frozen=True)

    doc_key: str = Field(min_length=1, max_length=128)
    version_index: int = Field(ge=1)
    sha256_hex: str
    source_ref: str = Field(min_length=1, max_length=512)
    published_at_utc: datetime
    retrieved_at_utc: datetime
    supersedes_version_index: int | None = Field(default=None, ge=1)
    is_restatement: bool = False
    trust_label: TrustLabel = "UNTRUSTED"
    notes: str = ""

    @field_validator("published_at_utc", "retrieved_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("sha256_hex")
    @classmethod
    def _sha256(cls, v: str) -> str:
        return _sha256_shape(v, "sha256_hex_must_be_64_hex")

    @model_validator(mode="after")
    def _restatement_discipline(self) -> "DocumentVersion":
        if self.is_restatement and self.supersedes_version_index is None:
            raise ValueError("restatement_requires_supersedes_version")
        if not self.is_restatement and self.supersedes_version_index is not None:
            raise ValueError("supersedes_requires_restatement")
        return self


class DocumentReRetrieval(BaseModel):
    """Honest re-retrieval record: the SAME document bytes re-fetched.

    The only sanctioned way to encounter a sha256 that the ledger already
    holds for a doc_key. A re-retrieval is a retrieval FACT appended to the
    ledger — it never creates a new version, never mutates an existing one,
    and never upgrades trust.
    """

    model_config = ConfigDict(frozen=True)

    doc_key: str = Field(min_length=1, max_length=128)
    sha256_hex: str
    retrieved_at_utc: datetime
    retrieval_ref: str = Field(min_length=1, max_length=512)
    notes: str = ""

    @field_validator("retrieved_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("sha256_hex")
    @classmethod
    def _sha256(cls, v: str) -> str:
        return _sha256_shape(v, "sha256_hex_must_be_64_hex")


def _canonical_version_line(v: DocumentVersion) -> str:
    return "|".join(
        (
            "V",
            v.doc_key,
            str(v.version_index),
            v.sha256_hex,
            v.source_ref,
            v.published_at_utc.isoformat(),
            v.retrieved_at_utc.isoformat(),
            "-" if v.supersedes_version_index is None else str(v.supersedes_version_index),
            "R" if v.is_restatement else "-",
            v.trust_label,
            v.notes,
        )
    )


def _canonical_re_retrieval_line(r: DocumentReRetrieval) -> str:
    return "|".join(
        (
            "X",
            r.doc_key,
            r.sha256_hex,
            r.retrieved_at_utc.isoformat(),
            r.retrieval_ref,
            r.notes,
        )
    )


class DocumentLedger:
    """Append-only version ledger per ``doc_key`` (value object).

    Deterministic rules:
    - ``register`` demands contiguous 1..n version indices per doc_key
      (``version_index_out_of_order``), refuses a sha256 already held for
      the same doc_key (``duplicate_sha256_refused``) and validates the
      supersede chain: a restatement must reference an EXISTING earlier
      version of the same doc_key (``supersedes_unknown_version``);
    - ``register_re_retrieval`` demands a known doc_key
      (``unknown_doc_key``) whose registered bytes match the re-retrieval's
      sha256 (``re_retrieval_unknown_sha256``); an identical record is an
      idempotent no-op; a different record for the same (doc_key, sha256,
      retrieved_at) is a conflict;
    - ``versions_as_of`` / ``latest`` are fail-closed on unknown doc_key;
    - history is never rewritten: appends return NEW ledgers, existing
      entries are immutable, and the class exposes no update/delete/purge
      method (structural absence — append-only by construction).
    """

    def __init__(
        self,
        versions: tuple[DocumentVersion, ...] = (),
        re_retrievals: tuple[DocumentReRetrieval, ...] = (),
    ) -> None:
        self._versions: tuple[DocumentVersion, ...] = versions
        self._re_retrievals: tuple[DocumentReRetrieval, ...] = re_retrievals

    @property
    def versions(self) -> tuple[DocumentVersion, ...]:
        return self._versions

    @property
    def re_retrievals(self) -> tuple[DocumentReRetrieval, ...]:
        return self._re_retrievals

    # -- internal lookups ----------------------------------------------------
    def _for_doc(self, doc_key: str) -> tuple[DocumentVersion, ...]:
        return tuple(v for v in self._versions if v.doc_key == doc_key)

    def _require_known(self, doc_key: str) -> tuple[DocumentVersion, ...]:
        found = self._for_doc(doc_key)
        if not found:
            raise ValueError("unknown_doc_key")
        return found

    def _next_index(self, doc_key: str) -> int:
        existing = self._for_doc(doc_key)
        return max((v.version_index for v in existing), default=0) + 1

    # -- append-only API -----------------------------------------------------
    def register(self, version: DocumentVersion) -> "DocumentLedger":
        expected = self._next_index(version.doc_key)
        if version.version_index != expected:
            raise ValueError("version_index_out_of_order")
        if any(v.sha256_hex == version.sha256_hex for v in self._for_doc(version.doc_key)):
            raise ValueError("duplicate_sha256_refused")
        if version.supersedes_version_index is not None:
            prior = next(
                (
                    v
                    for v in self._for_doc(version.doc_key)
                    if v.version_index == version.supersedes_version_index
                ),
                None,
            )
            if prior is None or prior.version_index >= version.version_index:
                raise ValueError("supersedes_unknown_version")
        return DocumentLedger(self._versions + (version,), self._re_retrievals)

    def register_re_retrieval(self, record: DocumentReRetrieval) -> "DocumentLedger":
        registered = self._require_known(record.doc_key)
        if not any(v.sha256_hex == record.sha256_hex for v in registered):
            raise ValueError("re_retrieval_unknown_sha256")
        key = (record.doc_key, record.sha256_hex, record.retrieved_at_utc)
        for existing in self._re_retrievals:
            existing_key = (
                existing.doc_key,
                existing.sha256_hex,
                existing.retrieved_at_utc,
            )
            if existing_key == key:
                if existing == record:
                    return self  # idempotent re-append
                raise ValueError("re_retrieval_conflict")
        return DocumentLedger(self._versions, self._re_retrievals + (record,))

    # -- point-in-time reads (fail-closed) ------------------------------------
    def versions_as_of(self, doc_key: str, ts: datetime) -> tuple[DocumentVersion, ...]:
        """Versions published at or before ``ts`` (publication-time PIT).

        Unknown ``doc_key`` is refused (fail-closed) rather than returning
        an empty list — a missing document must never be mistaken for an
        empty history.
        """
        known = self._require_known(doc_key)
        cutoff = ensure_utc(ts)
        return tuple(v for v in known if v.published_at_utc <= cutoff)

    def latest(self, doc_key: str) -> DocumentVersion:
        known = self._require_known(doc_key)
        return max(known, key=lambda v: v.version_index)

    # -- integrity -------------------------------------------------------------
    def integrity_digest(self) -> str:
        """Deterministic SHA-256 over the canonical ledger serialization.

        Same entries (in the same append order) ⇒ same digest, always.
        """
        lines = [_canonical_version_line(v) for v in self._versions]
        lines += [_canonical_re_retrieval_line(r) for r in self._re_retrievals]
        payload = "\n".join(lines).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DocumentLedger):
            return NotImplemented
        return (
            self._versions == other._versions
            and self._re_retrievals == other._re_retrievals
        )

    def __hash__(self) -> int:  # pragma: no cover - value-object nicety
        return hash((self._versions, self._re_retrievals))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"DocumentLedger(versions={len(self._versions)}, "
            f"re_retrievals={len(self._re_retrievals)})"
        )
