"""Evidence item contracts for RADAR BOURSE.

P0 addendum scope (Binding additive amendment 2026-10-02, "P0 — Contracts and
source-universe design", 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md line 135):
"evidence item schema with source URL/identifier, publisher, retrieval time,
publication time, effective period, source tier, document/version hash where
appropriate, extraction method/model version, corroboration/conflict status,
trust status and citations".

Contract/domain only. No network, no I/O, no clock reads, no LLM, no trading,
no production mutation. Deterministic functions only; timestamps and cutoffs
are always passed in as arguments. Unknown values are represented explicitly
(UNAVAILABLE / NOT_AVAILABLE) and are never invented or silently defaulted.

Governance references:
- D-AI-33 (05 register): facts keep source, publication time, reporting period,
  units/currency, version/restatement state, trust and conflict status;
  missing or contradictory data is surfaced, not invented or silently reconciled.
- 06 charter §3: publication time recorded separately from retrieval time and
  reporting period; syndicated copies are not independent corroboration;
  contradictions remain explicit until a deterministic rule or human review
  resolves them; restatements create new versions.
- 02 roadmap line 142: every conclusion must identify its information cutoff.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"

UNAVAILABLE = "UNAVAILABLE"
NOT_AVAILABLE = "NOT_AVAILABLE"

CorroborationStatus = Literal["CORROBORATED", "UNVERIFIED", "SYNDICATED_COPY", "CONFLICTING"]
TrustStatus = Literal["VERIFIED", "UNVERIFIED", "DISPUTED"]
PublicationStatus = Literal["KNOWN", "UNAVAILABLE"]
ConflictStatus = Literal["OPEN", "RESOLVED_DETERMINISTIC", "RESOLVED_HUMAN"]


def ensure_utc(value: datetime) -> datetime:
    """Validate that a timestamp is timezone-aware and normalize it to UTC.

    Naive timestamps are rejected (deterministic comparisons require an
    unambiguous instant). Normalization is deterministic: same input, same
    output.
    """
    if not isinstance(value, datetime):
        raise ValueError("timestamp_must_be_datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("timestamp_must_be_timezone_aware")
    return value.astimezone(timezone.utc)


class Period(BaseModel):
    """Generic effective period. Boundaries may be explicitly unknown."""

    model_config = ConfigDict(frozen=True)

    period_start: datetime | None = None
    period_end: datetime | None = None

    @field_validator("period_start", "period_end")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @model_validator(mode="after")
    def _ordered(self) -> "Period":
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_start > self.period_end
        ):
            raise ValueError("period_start_after_period_end")
        return self


class EvidenceItem(BaseModel):
    """Immutable, source-grounded evidence record.

    Publication time is recorded separately from retrieval time
    (06 charter §3.5). When the publication time is unknown it stays
    explicitly unknown via publication_status=UNAVAILABLE; it is never
    defaulted from the retrieval time or any other value.
    """

    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_identifier: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    retrieval_time_utc: datetime
    publication_time_utc: datetime | None = None
    publication_status: PublicationStatus
    effective_period: Period | None = None
    source_tier: str = Field(min_length=1)
    document_sha256: str | None = None
    extraction_method: str = Field(min_length=1)
    extraction_model_version: str | None = None
    corroboration_status: CorroborationStatus
    trust_status: TrustStatus
    citations: tuple[str, ...] = Field(min_length=1)
    conflicting_with: tuple[str, ...] = ()
    notes: str = ""

    @field_validator("retrieval_time_utc", "publication_time_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("document_sha256")
    @classmethod
    def _sha256_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("document_sha256_must_be_64_hex")
        return v.lower()

    @model_validator(mode="after")
    def _publication_consistency(self) -> "EvidenceItem":
        if self.publication_status == "KNOWN" and self.publication_time_utc is None:
            raise ValueError("known_publication_requires_timestamp")
        if self.publication_status == "UNAVAILABLE" and self.publication_time_utc is not None:
            raise ValueError("unavailable_publication_forbids_timestamp")
        if len(set(self.conflicting_with)) != len(self.conflicting_with):
            raise ValueError("conflicting_with_duplicates")
        if self.evidence_id in self.conflicting_with:
            raise ValueError("evidence_conflicts_with_itself")
        return self


class EvidenceConflict(BaseModel):
    """An explicit, unresolved-or-resolved contradiction between evidence items.

    Contradictions remain explicit until a deterministic rule or human review
    resolves them (06 charter §3.4; D-AI-33). There is no silent reconciliation:
    a resolution must name the deterministic rule or the human reviewer.
    """

    model_config = ConfigDict(frozen=True)

    conflict_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    evidence_ids: tuple[str, ...] = Field(min_length=2)
    description: str = Field(min_length=1)
    status: ConflictStatus
    resolution_rule: str | None = None
    resolved_by: str | None = None
    resolved_at_utc: datetime | None = None
    notes: str = ""

    @field_validator("resolved_at_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("evidence_ids")
    @classmethod
    def _distinct(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("evidence_ids_duplicates")
        return v

    @model_validator(mode="after")
    def _resolution_consistency(self) -> "EvidenceConflict":
        if self.status == "OPEN":
            if any(
                f is not None for f in (self.resolution_rule, self.resolved_by, self.resolved_at_utc)
            ):
                raise ValueError("open_conflict_cannot_carry_resolution")
        else:
            if not self.resolution_rule or not self.resolved_by or self.resolved_at_utc is None:
                raise ValueError("resolved_conflict_requires_rule_reviewer_and_time")
        return self


def availability_time(item: EvidenceItem) -> datetime:
    """Deterministic instant at which the evidence became available.

    Rule (02 roadmap line 142; 06 charter §3.5–3.6): when the publication time
    is known, information becomes available no earlier than the *later* of
    publication and retrieval (retrieval confirms possession). When the
    publication time is explicitly unknown, the retrieval time is the
    conservative earliest availability. Never invented; never defaulted from
    anything except the item's own recorded fields.
    """
    if item.publication_status == "KNOWN" and item.publication_time_utc is not None:
        return max(item.publication_time_utc, item.retrieval_time_utc)
    return item.retrieval_time_utc


def is_eligible_at(item: EvidenceItem, cutoff: datetime) -> bool:
    """Point-in-time eligibility of an evidence item for an information cutoff.

    Historical analyses must use only information available at their cutoff
    (02 roadmap line 142; 06 charter §3.6). A later-published or later-retrieved
    item is ineligible for an earlier cutoff.
    """
    return availability_time(item) <= ensure_utc(cutoff)


def independent_corroboration_count(items: Sequence[EvidenceItem]) -> int:
    """Count independent corroborating sources.

    06 charter §3.3: "Duplicate reports should be clustered; copied
    syndications must not be mistaken for independent corroboration."
    Only CORROBORATED items count; each distinct source_id counts once;
    SYNDICATED_COPY and UNVERIFIED items never count.
    """
    return len({i.source_id for i in items if i.corroboration_status == "CORROBORATED"})


def filter_eligible(items: Iterable[EvidenceItem], cutoff: datetime) -> tuple[EvidenceItem, ...]:
    """Deterministically filter evidence items to those eligible at a cutoff."""
    return tuple(item for item in items if is_eligible_at(item, cutoff))


def _finite_decimal(value: Any) -> Decimal:
    """Shared guard for financial values: finite decimals only (deterministic)."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("value_not_decimal_representable") from exc
    if not d.is_finite():
        raise ValueError("value_must_be_finite")
    return d
