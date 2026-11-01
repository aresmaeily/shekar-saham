"""Runtime symbol identity resolution (paper).

P0/P1 scope (02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 134 and 141-142):
"company/symbol identity resolution" and point-in-time honesty. This module
composes fundamental_dossier.CompanyIdentity EXACTLY: ambiguity is surfaced,
never silently resolved (D-AI-33; 06 charter §3.4) — an
AMBIGUOUS_UNRESOLVED identity lists its candidate matches and is never used
as if it were a resolved company.

Verdicts (closed vocabulary):
- RESOLVED_UNIQUE: exactly one ISIN is bound to the query.
- AMBIGUOUS_MULTIPLE_ISIN: several distinct ISINs match — surfaced with
  candidates, never silently resolved.
- NOT_FOUND: no registry record matches the query (nothing is invented).
- DEGRADED_MISSING_ISIN: records match but carry no ISIN, so the identity
  cannot be bound to an instrument (degraded honesty, candidates listed).

Contract/domain only: deterministic, clock-free, no I/O. `resolved_at_utc`
is always injected by the caller (CompanyIdentity composition requires it;
this module never reads a wall clock).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.fundamental_dossier import CompanyIdentity

__all__ = [
    "IdentityRecord",
    "IdentityResolution",
    "IdentityStatus",
    "IdentityVerdict",
    "resolve_symbol",
]

IdentityStatus = Literal["ACTIVE", "DELISTED", "SUSPENDED"]
IdentityVerdict = Literal[
    "RESOLVED_UNIQUE",
    "AMBIGUOUS_MULTIPLE_ISIN",
    "NOT_FOUND",
    "DEGRADED_MISSING_ISIN",
]


class IdentityRecord(BaseModel):
    """One entry of the caller-supplied identity registry (frozen)."""

    model_config = ConfigDict(frozen=True)

    l18: str = Field(min_length=1)
    isin: str | None = None
    name: str = ""
    official_name_fa: str = ""
    status: IdentityStatus

    @field_validator("l18")
    @classmethod
    def _l18(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("l18_must_not_be_empty")
        return v

    @field_validator("isin")
    @classmethod
    def _isin(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None  # an empty ISIN is an unknown ISIN, never a value


class IdentityResolution(BaseModel):
    """Outcome of one symbol resolution attempt (frozen, honest).

    `identity` is a verbatim CompanyIdentity composition; it is None only for
    NOT_FOUND (no company is ever invented). `candidates` lists the matched
    registry records whenever the outcome is ambiguous or degraded.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    query_l18: str = Field(min_length=1)
    query_isin: str | None = None
    verdict: IdentityVerdict
    identity: CompanyIdentity | None = None
    candidates: tuple[IdentityRecord, ...] = ()
    matched_key: Literal["ISIN", "SYMBOL"] | None = None
    matched_statuses: tuple[IdentityStatus, ...] = ()
    reason_codes: tuple[str, ...] = Field(min_length=1)


def _coerce_records(records: Sequence[Any]) -> list[IdentityRecord]:
    out: list[IdentityRecord] = []
    for record in records:
        if isinstance(record, IdentityRecord):
            out.append(record)
        elif isinstance(record, Mapping):
            out.append(IdentityRecord(**record))
        else:
            raise ValueError("record_must_be_identity_record_or_mapping")
    return out


def _status_reasons(statuses: tuple[IdentityStatus, ...]) -> tuple[str, ...]:
    codes = []
    for status in sorted(set(statuses)):
        if status != "ACTIVE":
            codes.append(f"matched_status_{status.lower()}")
    return tuple(codes)


def _identity(
    *,
    company_id: str,
    symbols: tuple[str, ...],
    candidates: tuple[IdentityRecord, ...],
    ambiguity_status: Literal["UNAMBIGUOUS", "AMBIGUOUS_UNRESOLVED"],
    candidate_matches: tuple[str, ...],
    resolved_at_utc: datetime,
) -> CompanyIdentity:
    """Compose fundamental_dossier.CompanyIdentity verbatim.

    `source_evidence_ids` deterministically reference the caller-supplied
    registry records this resolution is grounded in (no evidence item is
    invented — the ids are labeled pointers into the provided records).
    """
    evidence_ids = tuple(
        sorted({f"idrec:{r.l18}:{r.isin or 'NO_ISIN'}" for r in candidates})
    ) or ("idrec:none",)
    return CompanyIdentity(
        company_id=company_id,
        symbols=symbols,
        resolution_basis="REGISTRY_MATCH",
        ambiguity_status=ambiguity_status,
        candidate_matches=candidate_matches,
        resolved_at_utc=resolved_at_utc,
        source_evidence_ids=evidence_ids,
    )


def resolve_symbol(
    l18: str,
    isin: str | None,
    records: Sequence[Any],
    *,
    resolved_at_utc: datetime,
) -> IdentityResolution:
    """Resolve a symbol/ISIN query against the supplied identity records.

    Refusals (ValueError reason codes):
    - l18_must_not_be_empty (also for whitespace-only queries)
    - record_must_be_identity_record_or_mapping
    - timestamp_must_be_timezone_aware / timestamp_must_be_datetime
      (shared ensure_utc vocabulary, for the injected resolved_at_utc)

    Matching: when `isin` is supplied the registry is queried by ISIN
    (matched_key="ISIN"); otherwise by exact stripped l18 equality
    (matched_key="SYMBOL").
    """
    at = ensure_utc(resolved_at_utc)
    if not isinstance(l18, str):
        raise ValueError("l18_must_not_be_empty")
    query = l18.strip()
    if not query:
        raise ValueError("l18_must_not_be_empty")
    query_isin = (isin or "").strip() or None
    registry = _coerce_records(records)

    if query_isin is not None:
        matches = [r for r in registry if r.isin == query_isin]
        if not matches:
            return IdentityResolution(
                query_l18=query,
                query_isin=query_isin,
                verdict="NOT_FOUND",
                matched_key="ISIN",
                reason_codes=("isin_not_found_in_records",),
            )
        symbols = tuple(sorted({r.l18 for r in matches}))
        statuses = tuple(r.status for r in matches)
        reasons = ["resolved_by_isin_unique_match"]
        if len(matches) > 1:
            reasons = ["resolved_by_isin_multiple_records_same_isin"]
        if len(symbols) > 1:
            reasons.append("multiple_symbols_share_isin")
        reasons.extend(_status_reasons(statuses))
        return IdentityResolution(
            query_l18=query,
            query_isin=query_isin,
            verdict="RESOLVED_UNIQUE",
            identity=_identity(
                company_id=query_isin,
                symbols=symbols,
                candidates=tuple(matches),
                ambiguity_status="UNAMBIGUOUS",
                candidate_matches=(),
                resolved_at_utc=at,
            ),
            candidates=tuple(matches),
            matched_key="ISIN",
            matched_statuses=statuses,
            reason_codes=tuple(reasons),
        )

    matches = [r for r in registry if r.l18 == query]
    if not matches:
        return IdentityResolution(
            query_l18=query,
            query_isin=None,
            verdict="NOT_FOUND",
            reason_codes=("symbol_not_found_in_records",),
        )
    statuses = tuple(r.status for r in matches)
    distinct_isins = tuple(sorted({r.isin for r in matches if r.isin}))
    status_reasons = _status_reasons(statuses)

    if len(distinct_isins) >= 2:
        # Ambiguity is surfaced, never silently resolved (D-AI-33): the
        # CompanyIdentity is composed with AMBIGUOUS_UNRESOLVED and its
        # candidate list; `unresolved:` prefix marks a non-resolved key.
        return IdentityResolution(
            query_l18=query,
            query_isin=None,
            verdict="AMBIGUOUS_MULTIPLE_ISIN",
            identity=_identity(
                company_id=f"unresolved:{query}",
                symbols=(query,),
                candidates=tuple(matches),
                ambiguity_status="AMBIGUOUS_UNRESOLVED",
                candidate_matches=distinct_isins,
                resolved_at_utc=at,
            ),
            candidates=tuple(matches),
            matched_key="SYMBOL",
            matched_statuses=statuses,
            reason_codes=("multiple_isins_for_symbol",) + status_reasons,
        )

    if not distinct_isins:
        # Degraded: matching records exist but none carries an ISIN.
        ambiguous = len(matches) > 1
        return IdentityResolution(
            query_l18=query,
            query_isin=None,
            verdict="DEGRADED_MISSING_ISIN",
            identity=_identity(
                company_id=f"l18:{query}",
                symbols=(query,),
                candidates=tuple(matches),
                ambiguity_status="AMBIGUOUS_UNRESOLVED" if ambiguous else "UNAMBIGUOUS",
                candidate_matches=tuple(
                    sorted({f"idrec:{r.l18}:{r.isin or 'NO_ISIN'}" for r in matches})
                )
                if ambiguous
                else (),
                resolved_at_utc=at,
            ),
            candidates=tuple(matches),
            matched_key="SYMBOL",
            matched_statuses=statuses,
            reason_codes=("isin_missing_in_all_matched_records",)
            + (("multiple_records_without_isin",) if ambiguous else ())
            + status_reasons,
        )

    reasons = ["resolved_by_symbol_unique_match"]
    if len(matches) > 1:
        reasons = ["resolved_by_symbol_multiple_records_same_isin"]
    return IdentityResolution(
        query_l18=query,
        query_isin=None,
        verdict="RESOLVED_UNIQUE",
        identity=_identity(
            company_id=distinct_isins[0],
            symbols=(query,),
            candidates=tuple(matches),
            ambiguity_status="UNAMBIGUOUS",
            candidate_matches=(),
            resolved_at_utc=at,
        ),
        candidates=tuple(matches),
        matched_key="SYMBOL",
        matched_statuses=statuses,
        reason_codes=tuple(reasons) + status_reasons,
    )
