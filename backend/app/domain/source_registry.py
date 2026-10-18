"""Source registry contracts for RADAR BOURSE.

P0 addendum scope (Binding additive amendment 2026-10-02,
02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md line 133): "source registry and
source tiers; coverage/limitations report; source ownership, permitted access,
rate limits and refresh policy".

Design references:
- 06 charter §3: versioned source registry that can expand over time; the
  product must report configured coverage, discovery status, inaccessible
  sources, freshness, last successful retrieval, failures and known gaps; it
  must not claim literal coverage of the entire internet.
- D-AI-32, D-AI-38 (05 register): governed monitoring of an explicit, versioned,
  auditable source universe; coverage honesty is mandatory.
- 03 boundaries (additive): "All web" is a governed source-coverage system,
  not a literal guarantee of universal crawling.

Contract/domain only: no crawling, no network, no scheduler, no I/O. The
registry is an immutable value object; registration returns a new versioned
instance (append-only history by construction).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc

SourceTier = Literal[
    "PRIMARY_REGULATOR",
    "ISSUER_ANNOUNCEMENT",
    "OFFICIAL_COMPANY_IR",
    "AUDITED_FINANCIAL_STATEMENTS",
    "CORPORATE_ACTION_NOTICE",
    "REPUTABLE_FINANCIAL_NEWS",
    "SECTOR_INDUSTRY",
    "MACROECONOMIC",
    "APPROVED_PUBLIC_OTHER",
]

PrecedenceClass = Literal["PRIMARY", "SECONDARY"]
SourceStatus = Literal["CONFIGURED", "ACTIVE", "INACCESSIBLE", "RETIRED"]
RefreshPolicy = Literal["EVENT_DRIVEN", "SCHEDULED", "ON_DEMAND"]

#: 06 charter §3 source hierarchy: primary official/regulatory/issuer documents
#: are preferred; secondary sources corroborate, never silently replace.
_PRIMARY_TIERS: frozenset[str] = frozenset(
    {
        "PRIMARY_REGULATOR",
        "ISSUER_ANNOUNCEMENT",
        "OFFICIAL_COMPANY_IR",
        "AUDITED_FINANCIAL_STATEMENTS",
        "CORPORATE_ACTION_NOTICE",
    }
)


def default_precedence_for_tier(tier: str) -> PrecedenceClass:
    """Deterministic tier→precedence mapping (06 charter §3.1–3.2)."""
    return "PRIMARY" if tier in _PRIMARY_TIERS else "SECONDARY"


class RateLimit(BaseModel):
    """Declared, bounded access ceilings. Zero/absent means 'not yet set',
    which is represented explicitly rather than guessed."""

    model_config = ConfigDict(frozen=True)

    max_requests_per_minute: int | None = Field(default=None, ge=1, le=10_000)
    max_retrievals_per_day: int | None = Field(default=None, ge=1, le=1_000_000)
    notes: str = ""


class SourceDescriptor(BaseModel):
    """One declared source in the registry.

    Credentials are never part of a source descriptor: the descriptor records
    THAT authentication is required, never any secret material (03 boundaries
    §Security; CLAUDE.md security rules).
    """

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    name: str = Field(min_length=1, max_length=256)
    tier: SourceTier
    precedence_class: PrecedenceClass
    ownership: str = Field(min_length=1)
    permitted_access: str = Field(min_length=1)
    access_terms_version: str = Field(min_length=1)
    refresh_policy: RefreshPolicy
    respects_robots: bool = True
    credentials_required: bool = False
    rate_limit: RateLimit = Field(default_factory=RateLimit)
    freshness_target: timedelta | None = None
    status: SourceStatus = "CONFIGURED"
    last_success_utc: datetime | None = None
    last_failure_utc: datetime | None = None
    notes: str = ""

    @field_validator("last_success_utc", "last_failure_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("freshness_target")
    @classmethod
    def _positive_freshness(cls, v: timedelta | None) -> timedelta | None:
        if v is not None and v <= timedelta(0):
            raise ValueError("freshness_target_must_be_positive")
        return v

    @model_validator(mode="after")
    def _consistency(self) -> "SourceDescriptor":
        if self.precedence_class != default_precedence_for_tier(self.tier):
            raise ValueError("precedence_class_inconsistent_with_tier")
        return self


class CoverageReport(BaseModel):
    """Honest coverage/limitations report (D-AI-38; 06 charter §3).

    `universal_coverage_claimed` is structurally locked to False: the
    platform must never claim to monitor the entire internet
    (06 charter §3; 02-arch additive §Continuous monitoring architecture).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    as_of_utc: datetime
    registry_version: int = Field(ge=1)
    total_configured: int = Field(ge=0)
    active: int = Field(ge=0)
    inaccessible: tuple[str, ...] = ()
    stale_sources: tuple[str, ...] = ()
    never_retrieved: tuple[str, ...] = ()
    uncovered_source_classes: tuple[str, ...] = ()
    known_gaps: tuple[str, ...] = ()
    universal_coverage_claimed: Literal[False] = False

    @field_validator("as_of_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


class SourceRegistry(BaseModel):
    """Immutable, versioned, append-only source registry.

    `with_source()` returns a NEW registry with an incremented version;
    re-registering a byte-identical descriptor is an idempotent no-op;
    a conflicting re-registration is rejected. History is never rewritten.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    registry_version: int = Field(default=1, ge=1)
    entries: tuple[SourceDescriptor, ...] = ()

    def get(self, source_id: str) -> SourceDescriptor | None:
        for entry in self.entries:
            if entry.source_id == source_id:
                return entry
        return None

    def sources_by_tier(self, tier: SourceTier) -> tuple[SourceDescriptor, ...]:
        return tuple(e for e in self.entries if e.tier == tier)

    def with_source(self, descriptor: SourceDescriptor) -> "SourceRegistry":
        existing = self.get(descriptor.source_id)
        if existing is not None:
            if existing == descriptor:
                return self  # idempotent re-registration
            raise ValueError("source_registry_conflict")
        return self.model_copy(
            update={
                "registry_version": self.registry_version + 1,
                "entries": self.entries + (descriptor,),
            }
        )

    def coverage_report(
        self,
        as_of: datetime,
        *,
        required_source_classes: tuple[str, ...] = (),
        known_gaps: tuple[str, ...] = (),
    ) -> CoverageReport:
        """Build the honest coverage report at a point in time.

        A source is stale when its last success is older than its declared
        freshness target (or it has never succeeded). Uncovered source classes
        are the required classes with zero configured sources. Nothing is
        inferred beyond the recorded fields.
        """
        as_of = ensure_utc(as_of)
        inaccessible = tuple(e.source_id for e in self.entries if e.status == "INACCESSIBLE")
        stale: list[str] = []
        never: list[str] = []
        for e in self.entries:
            if e.last_success_utc is None:
                never.append(e.source_id)
                continue
            if e.freshness_target is not None and as_of - e.last_success_utc > e.freshness_target:
                stale.append(e.source_id)
        configured_classes = {e.tier for e in self.entries}
        uncovered = tuple(c for c in required_source_classes if c not in configured_classes)
        return CoverageReport(
            as_of_utc=as_of,
            registry_version=self.registry_version,
            total_configured=len(self.entries),
            active=len(tuple(e for e in self.entries if e.status == "ACTIVE")),
            inaccessible=inaccessible,
            stale_sources=tuple(stale),
            never_retrieved=tuple(never),
            uncovered_source_classes=uncovered,
            known_gaps=tuple(known_gaps),
        )
