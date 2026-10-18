"""Fundamental intelligence dossier contracts for RADAR BOURSE.

P0 addendum scope (Binding additive amendment 2026-10-02,
02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 134 and 136):
- "company/symbol identity resolution, corporate actions, filing periods,
  publication timestamps, restatements, currency/unit normalization and
  point-in-time semantics";
- "company fundamental dossier schema; explicit distinction between investment
  candidate, user-watchlisted company, and possible M&A/acquisition-target
  intelligence".

Design references:
- 06 charter §3.5–3.7: publication time recorded separately from retrieval
  time and reporting period; restatements create new versions; currency,
  units, fiscal calendars, consolidation status, auditor opinion, missing
  notes and uncertainty must be explicit.
- 06 charter §4: dossier content list; the three concepts (stock/investment
  candidate, user-watchlisted company, M&A/acquisition-target signal) must
  never be conflated; an acquisition-target signal requires its own evidence
  and must not be inferred solely from a stock opportunity score; no
  financial fact may be invented to fill a gap.
- D-AI-33 (05 register): every fact retains source, publication time,
  reporting period, units/currency, version/restatement state, trust and
  conflict status; missing or contradictory data is surfaced.
- 02 roadmap line 142: every conclusion must identify its information cutoff.

Contract/domain only: deterministic, clock-free, no I/O, no LLM. Financial
values are finite Decimals (deterministic financial truth; never floats).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import (
    SCHEMA_VERSION,
    EvidenceConflict,
    Period,
    _finite_decimal,
    ensure_utc,
)

CompanyResolutionBasis = Literal["OFFICIAL_SYMBOL_MAP", "REGISTRY_MATCH", "MANUAL_OWNER_INPUT"]
IdentityAmbiguity = Literal["UNAMBIGUOUS", "AMBIGUOUS_UNRESOLVED"]
AuditorStatus = Literal["AUDITED", "REVIEWED", "UNAUDITED", "UNKNOWN"]
FactValueStatus = Literal["REPORTED", "NOT_AVAILABLE"]
PublicationStatus = Literal["KNOWN", "UNAVAILABLE"]
CompanyRole = Literal["INVESTMENT_CANDIDATE", "WATCHLIST_COMPANY", "MA_TARGET_SIGNAL"]


class CompanyIdentity(BaseModel):
    """Company/symbol identity resolution record.

    Ambiguity is surfaced, never silently resolved (D-AI-33; 06 charter §3.4):
    an AMBIGUOUS_UNRESOLVED identity must list its candidate matches and must
    not be used as if it were a resolved company.
    """

    model_config = ConfigDict(frozen=True)

    company_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    symbols: tuple[str, ...] = Field(min_length=1)
    resolution_basis: CompanyResolutionBasis
    ambiguity_status: IdentityAmbiguity
    candidate_matches: tuple[str, ...] = ()
    resolved_at_utc: datetime
    source_evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("resolved_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _ambiguity_consistency(self) -> "CompanyIdentity":
        if self.ambiguity_status == "AMBIGUOUS_UNRESOLVED" and not self.candidate_matches:
            raise ValueError("ambiguous_identity_requires_candidate_matches")
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols_duplicates")
        return self


class CorporateActionRecord(BaseModel):
    """Immutable corporate-action record with its own evidence.

    Financial values are finite Decimals with an explicit unit; a value that
    is not known stays NOT_AVAILABLE and is never estimated.
    """

    model_config = ConfigDict(frozen=True)

    action_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    company_id: str = Field(min_length=1)
    action_type: Literal[
        "DIVIDEND",
        "CAPITAL_INCREASE",
        "CAPITAL_DECREASE",
        "STOCK_SPLIT",
        "BONUS_SHARE",
        "RIGHTS_ISSUE",
        "NAME_CHANGE",
        "DELISTING",
        "OTHER",
    ]
    publication_time_utc: datetime | None = None
    publication_status: PublicationStatus
    effective_date_utc: datetime | None = None
    value: Decimal | None = None
    value_status: FactValueStatus
    value_unit: str | None = None
    source_evidence_ids: tuple[str, ...] = Field(min_length=1)
    restatement_of: str | None = None
    notes: str = ""

    @field_validator("publication_time_utc", "effective_date_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("value")
    @classmethod
    def _finite(cls, v: Decimal | None) -> Decimal | None:
        return None if v is None else _finite_decimal(v)

    @model_validator(mode="after")
    def _consistency(self) -> "CorporateActionRecord":
        if self.publication_status == "KNOWN" and self.publication_time_utc is None:
            raise ValueError("known_publication_requires_timestamp")
        if self.publication_status == "UNAVAILABLE" and self.publication_time_utc is not None:
            raise ValueError("unavailable_publication_forbids_timestamp")
        if self.value_status == "REPORTED":
            if self.value is None or not self.value_unit:
                raise ValueError("reported_value_requires_value_and_unit")
        else:
            if self.value is not None:
                raise ValueError("not_available_value_forbids_value")
        return self


class FilingPeriod(BaseModel):
    """Reporting period + publication semantics for a filing version.

    Restatements create NEW versions: `restatement_of` chains to the
    superseded filing id; the superseded record is retained, never edited
    (06 charter §3.6).
    """

    model_config = ConfigDict(frozen=True)

    filing_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    company_id: str = Field(min_length=1)
    reporting_period: Period
    fiscal_calendar: str = Field(min_length=1)
    publication_time_utc: datetime | None = None
    publication_status: PublicationStatus
    retrieval_time_utc: datetime | None = None
    restatement_of: str | None = None
    source_evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("publication_time_utc", "retrieval_time_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @model_validator(mode="after")
    def _consistency(self) -> "FilingPeriod":
        if self.publication_status == "KNOWN" and self.publication_time_utc is None:
            raise ValueError("known_publication_requires_timestamp")
        if self.publication_status == "UNAVAILABLE" and self.publication_time_utc is not None:
            raise ValueError("unavailable_publication_forbids_timestamp")
        return self


class FundamentalFact(BaseModel):
    """One source-grounded fundamental value.

    A REPORTED fact must carry value + unit + currency + period + evidence
    (units/currency explicit, 06 charter §3.7; D-AI-33). A missing value is
    NOT_AVAILABLE — never invented to fill a gap (06 charter §4).
    """

    model_config = ConfigDict(frozen=True)

    fact_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    company_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: Decimal | None = None
    value_status: FactValueStatus
    unit: str | None = None
    currency: str | None = None
    period: FilingPeriod
    auditor_status: AuditorStatus = "UNKNOWN"
    restatement_version: int = Field(default=1, ge=1)
    supersedes_fact_id: str | None = None
    source_evidence_ids: tuple[str, ...] = Field(min_length=1)
    notes: str = ""

    @field_validator("value")
    @classmethod
    def _finite(cls, v: Decimal | None) -> Decimal | None:
        return None if v is None else _finite_decimal(v)

    @model_validator(mode="after")
    def _consistency(self) -> "FundamentalFact":
        if self.value_status == "REPORTED":
            if self.value is None or not self.unit or not self.currency:
                raise ValueError("reported_fact_requires_value_unit_currency")
        else:
            if self.value is not None:
                raise ValueError("not_available_fact_forbids_value")
        if self.restatement_version > 1 and not self.supersedes_fact_id:
            raise ValueError("restatement_requires_superseded_fact")
        return self


class RoleClassification(BaseModel):
    """One of the three never-conflated company roles (06 charter §4).

    An M&A/acquisition-target signal requires its own evidence references;
    it cannot be inferred solely from a stock opportunity score — the
    `opportunity_score_ref` alone is structurally insufficient.
    """

    model_config = ConfigDict(frozen=True)

    role: CompanyRole
    schema_version: str = SCHEMA_VERSION
    company_id: str = Field(min_length=1)
    supporting_evidence_ids: tuple[str, ...] = ()
    opportunity_score_ref: str | None = None
    rationale: str = Field(min_length=1)
    assigned_at_utc: datetime

    @field_validator("assigned_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _role_consistency(self) -> "RoleClassification":
        if self.role == "MA_TARGET_SIGNAL":
            if not self.supporting_evidence_ids:
                raise ValueError("ma_target_signal_requires_own_evidence")
        return self


class CompanyDossier(BaseModel):
    """Point-in-time company dossier (06 charter §4 content list).

    The dossier is bound to an information cutoff (`information_cutoff_utc`):
    it may only contain facts whose filings were published (or, when
    publication is unknown, retrieved) at or before the cutoff — 02 roadmap
    line 142. Conflicts are carried explicitly; missing data is listed, not
    filled (D-AI-33).
    """

    model_config = ConfigDict(frozen=True)

    dossier_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    company_id: str = Field(min_length=1)
    information_cutoff_utc: datetime
    identity: CompanyIdentity
    facts: tuple[FundamentalFact, ...] = ()
    corporate_actions: tuple[CorporateActionRecord, ...] = ()
    roles: tuple[RoleClassification, ...] = ()
    conflicts: tuple[EvidenceConflict, ...] = ()
    missing_data: tuple[str, ...] = ()
    auditor_opinion: str | None = None
    going_concern_warning: bool = False
    data_trust_ref: str = Field(min_length=1)
    pit_eligible: bool
    limitations: tuple[str, ...] = Field(min_length=1)
    notes: str = ""

    @field_validator("information_cutoff_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _consistency(self) -> "CompanyDossier":
        company = self.company_id
        for fact in self.facts:
            if fact.company_id != company:
                raise ValueError("fact_company_mismatch")
        for action in self.corporate_actions:
            if action.company_id != company:
                raise ValueError("corporate_action_company_mismatch")
        for role in self.roles:
            if role.company_id != company:
                raise ValueError("role_company_mismatch")
        if self.identity.company_id != company:
            raise ValueError("identity_company_mismatch")
        fact_ids = {f.fact_id for f in self.facts}
        if len(fact_ids) != len(self.facts):
            raise ValueError("duplicate_fact_ids")
        return self

    def facts_at_cutoff(self) -> tuple[FundamentalFact, ...]:
        """Facts whose filing is point-in-time eligible at the dossier cutoff.

        A fact is eligible when its filing publication time is known and at or
        before the cutoff, or when publication is explicitly unknown and the
        filing retrieval time is at or before the cutoff. Later-published
        filings are excluded so historical analysis cannot use future
        information (02 roadmap line 142; 06 charter §3.6).
        """
        cutoff = self.information_cutoff_utc
        eligible: list[FundamentalFact] = []
        for fact in self.facts:
            filing = fact.period
            if filing.publication_status == "KNOWN":
                available = filing.publication_time_utc
            else:
                available = filing.retrieval_time_utc
            if available is not None and available <= cutoff:
                eligible.append(fact)
        return tuple(eligible)
