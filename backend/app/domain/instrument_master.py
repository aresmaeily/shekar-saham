"""Canonical instrument master and universe selection contracts (paper).

MASTER-RADAR directive Wave 2, §A1/§G: a single canonical registry of
tradable/reference instruments with EXPLICIT trust labeling and fail-closed
selection. Nothing in this module claims any instrument record is real,
verified, or live: every record carries a ``trust_class`` and a declared
``source_identity``, and the strongest trust class (REAL_VERIFIED) is
refused unless an explicitly verified entitlement and a non-synthetic
declared source back it (fail-closed cross-check).

Honest scope:
- Contract/domain only: no I/O, no network, no clock reads. Timestamps
  (``declared_at_utc``, ``last_updated_utc``) are always injected by callers.
- Selection (``build_default_universe``) is a mechanical filter over declared
  records; it never invents instruments and never upgrades trust.
- Pseudo-symbol defense: only records with a declared, non-sentinel
  ``source_identity`` may enter a universe (``register_instrument``).
- Individual US equities are excluded from universes by policy: the marker
  market ``EXCLUDED_US_EQUITY`` exists ONLY to exercise that exclusion and is
  never selectable in a ``UniverseSpec``.

Persian strings appear only in user-facing label fields (``name_fa``).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc

__all__ = [
    "INSTRUMENT_MASTER_SCHEMA_VERSION",
    "UNDECLARED_SOURCE",
    "UNSOURCED_SOURCE_IDENTITIES",
    "REASON_MARKET_NOT_IN_SPEC",
    "REASON_STATUS_NOT_INCLUDED",
    "REASON_TYPE_NOT_ALLOWED",
    "REASON_US_INDIVIDUAL_EQUITY_EXCLUDED",
    "ProxyKind",
    "TrustClass",
    "Market",
    "InstrumentType",
    "InstrumentStatus",
    "EntitlementStatus",
    "MembershipInterval",
    "InstrumentRecord",
    "UniverseSpec",
    "DEFAULT_UNIVERSE_MARKETS",
    "UniverseResolution",
    "register_instrument",
    "build_default_universe",
    "membership_status_as_of",
]

INSTRUMENT_MASTER_SCHEMA_VERSION = f"instrument-master-1.0.0+evidence-{SCHEMA_VERSION}"

UNDECLARED_SOURCE = "UNDECLARED"

# Source-identity sentinels that mean "no declared source". A record carrying
# any of these can never enter a universe (pseudo-symbol defense, allowlist
# policy). Everything not in this set is treated as a declared source.
UNSOURCED_SOURCE_IDENTITIES = frozenset({"", "UNDECLARED", "UNSOURCED", "UNKNOWN", "NONE"})

# Exact exclusion reason codes (directive §G).
REASON_MARKET_NOT_IN_SPEC = "MARKET_NOT_IN_SPEC"
REASON_STATUS_NOT_INCLUDED = "STATUS_NOT_INCLUDED"
REASON_TYPE_NOT_ALLOWED = "TYPE_NOT_ALLOWED"
REASON_US_INDIVIDUAL_EQUITY_EXCLUDED = "US_INDIVIDUAL_EQUITY_EXCLUDED"


class TrustClass(str, Enum):
    """Exhaustive data-trust labels; every series/record carries exactly one."""

    REAL_VERIFIED = "REAL_VERIFIED"
    REAL_UNVERIFIED = "REAL_UNVERIFIED"
    DELAYED = "DELAYED"
    SYNTHETIC = "SYNTHETIC"
    PAPER = "PAPER"
    STALE = "STALE"
    MISSING = "MISSING"


class Market(str, Enum):
    """Market segments. EXCLUDED_US_EQUITY is a non-default marker market used
    only to demonstrate/exercise the individual-US-equity exclusion policy; it
    is never present in a default universe and never selectable in a spec."""

    IRAN_TSE = "IRAN_TSE"
    IRAN_IFB = "IRAN_IFB"
    FOREX = "FOREX"
    US_INDEX = "US_INDEX"
    EXCLUDED_US_EQUITY = "EXCLUDED_US_EQUITY"


class InstrumentType(str, Enum):
    COMMON_STOCK = "COMMON_STOCK"
    CASH_INDEX = "CASH_INDEX"
    ETF = "ETF"
    FUTURE = "FUTURE"
    CFD = "CFD"
    CURRENCY_PAIR = "CURRENCY_PAIR"
    UNCLASSIFIED = "UNCLASSIFIED"


class InstrumentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELISTED = "DELISTED"
    UNKNOWN = "UNKNOWN"


class EntitlementStatus(str, Enum):
    ENTITLED_VERIFIED = "ENTITLED_VERIFIED"
    NOT_ENTITLED = "NOT_ENTITLED"
    UNKNOWN = "UNKNOWN"


ProxyKind = Literal["CASH", "ETF", "FUTURE", "CFD", "NONE"]


class MembershipInterval(BaseModel):
    """Half-open index-membership state ``[effective_from, effective_to)``.

    ``effective_to=None`` means the interval is open-ended. Fully-open on both
    sides is allowed. ``symbol_id`` duplicates the owning instrument id for
    standalone auditability.
    """

    model_config = ConfigDict(frozen=True)

    symbol_id: str
    status: InstrumentStatus
    effective_from: date | None = None
    effective_to: date | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "MembershipInterval":
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_from >= self.effective_to
        ):
            raise ValueError("membership_interval_must_satisfy_from_lt_to")
        return self

    def covers(self, day: date) -> bool:
        """Half-open membership test: ``from <= day < to`` (None = open side)."""
        if self.effective_from is not None and day < self.effective_from:
            return False
        if self.effective_to is not None and day >= self.effective_to:
            return False
        return True


class InstrumentRecord(BaseModel):
    """One canonical instrument with explicit identity, metadata and trust.

    ``instrument_id`` is canonical and immutable (market-prefixed dotted form
    like ``IR_TSE:FOLAD``). ``status`` is the CURRENT status;
    ``membership`` holds historical index-membership states (empty list means
    "no historical membership declared" and the current status stands).
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str = Field(pattern=r"^[A-Z0-9_]+:[A-Z0-9_.\-]+$")
    market: Market
    symbol: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    name_en: str = ""
    name_fa: str = ""
    instrument_type: InstrumentType
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    base_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    quote_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    pip_precision: int | None = Field(default=None, ge=0, le=8)
    contract_size: float | None = Field(default=None, gt=0)
    lot_size: float | None = Field(default=None, gt=0)
    tick_size: float | None = Field(default=None, gt=0)
    timezone: str = Field(min_length=3)
    calendar_id: str = Field(min_length=1)
    trading_sessions: list[str] = Field(default_factory=list)
    listing_date: date | None = None
    delisting_date: date | None = None
    source_identity: str = Field(min_length=1)
    entitlement: EntitlementStatus = EntitlementStatus.UNKNOWN
    trust_class: TrustClass = TrustClass.MISSING
    status: InstrumentStatus
    coverage_start: date | None = None
    coverage_end: date | None = None
    last_updated_utc: datetime | None = None
    # Directive §A1: cash indices are distinguished from tradable proxies.
    # Meaningful/required for US_INDEX records (validated below); the honest
    # default elsewhere is "not a benchmark, no proxy" (False / "NONE").
    is_index_benchmark: bool = False
    proxy_kind: ProxyKind = "NONE"
    membership: list[MembershipInterval] = Field(default_factory=list)

    @field_validator("last_updated_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("symbol")
    @classmethod
    def _symbol_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("symbol_must_not_be_blank")
        return v

    @model_validator(mode="after")
    def _cross_checks(self) -> "InstrumentRecord":
        # Forex: full FX metadata is mandatory (fail-closed, never partial).
        if self.market == Market.FOREX:
            if (
                self.base_currency is None
                or self.quote_currency is None
                or self.pip_precision is None
                or self.contract_size is None
            ):
                raise ValueError("forex_requires_base_quote_pip_precision_contract_size")
        else:
            if self.base_currency is not None or self.quote_currency is not None:
                raise ValueError("base_quote_currencies_only_allowed_for_forex")
        # US index market: only cash indices or ETF proxies, explicitly labeled.
        if self.market == Market.US_INDEX:
            if self.instrument_type not in (InstrumentType.CASH_INDEX, InstrumentType.ETF):
                raise ValueError("us_index_instrument_type_must_be_cash_index_or_etf")
            if self.instrument_type == InstrumentType.CASH_INDEX:
                if not self.is_index_benchmark or self.proxy_kind != "NONE":
                    raise ValueError("us_index_cash_instrument_requires_benchmark_true_proxy_none")
            else:  # ETF proxy of the index
                if self.is_index_benchmark or self.proxy_kind != "ETF":
                    raise ValueError("us_index_etf_requires_benchmark_false_proxy_etf")
        # Fail-closed trust cross-check: the strongest claim needs receipts.
        if self.trust_class == TrustClass.REAL_VERIFIED:
            if self.entitlement != EntitlementStatus.ENTITLED_VERIFIED or (
                self.source_identity == "SYNTHETIC_FIXTURE"
            ):
                raise ValueError(
                    "real_verified_requires_entitled_verifed_and_non_synthetic_source"
                )
        return self


class UniverseSpec(BaseModel):
    """Versioned, injected-time selection specification for a universe."""

    model_config = ConfigDict(frozen=True)

    spec_id: str = Field(min_length=1)
    declared_at_utc: datetime
    markets: set[Market] = Field(default_factory=lambda: set(DEFAULT_UNIVERSE_MARKETS))
    include_statuses: set[InstrumentStatus] = Field(
        default_factory=lambda: {InstrumentStatus.ACTIVE}
    )
    instrument_types_allowed: set[InstrumentType] = Field(
        default_factory=lambda: set(InstrumentType)
    )
    exclude_individual_us_equities: bool = True

    @field_validator("declared_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("markets")
    @classmethod
    def _marker_market_never_selectable(cls, v: set[Market]) -> set[Market]:
        if Market.EXCLUDED_US_EQUITY in v:
            raise ValueError("excluded_marker_market_not_selectable_in_universe_spec")
        return v

    @model_validator(mode="after")
    def _exclusion_non_overridable(self) -> "UniverseSpec":
        if not self.exclude_individual_us_equities:
            raise ValueError("exclude_individual_us_equities_is_non_overridable")
        return self

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> "UniverseSpec":
        """Hardened copy: re-run the fail-closed invariants on the RESULT.

        ``model_copy(update=...)`` bypasses field/model validators by design;
        an internal caller could otherwise flip ``exclude_individual_us_equities``
        or inject the marker market post-construction. The invariants are
        NON-OVERRIDABLE, so any copy attempt that would violate them fails
        here exactly as it would at construction.
        """
        clone = super().model_copy(update=update, deep=deep)
        if Market.EXCLUDED_US_EQUITY in clone.markets:
            raise ValueError("excluded_marker_market_not_selectable_in_universe_spec")
        if not clone.exclude_individual_us_equities:
            raise ValueError("exclude_individual_us_equities_is_non_overridable")
        return clone


DEFAULT_UNIVERSE_MARKETS: frozenset[Market] = frozenset(
    {Market.IRAN_TSE, Market.IRAN_IFB, Market.FOREX, Market.US_INDEX}
)


class UniverseResolution(BaseModel):
    """Result of resolving records against a spec; order-preserving."""

    model_config = ConfigDict(frozen=True)

    spec_id: str
    declared_at_utc: datetime
    included: list[InstrumentRecord] = Field(default_factory=list)
    excluded: list[tuple[str, str]] = Field(default_factory=list)
    considered: int = 0


def register_instrument(record: InstrumentRecord, existing_ids: Iterable[str] = ()) -> str:
    """Allowlist entry gate for a universe (pseudo-symbol defense).

    A record may only enter a universe when it carries a declared
    non-sentinel ``source_identity``. Symbols matching fabricated patterns
    (e.g. ``^[A-Z]{4,6}\\d{0,2}$``) without a declared source are exactly the
    pseudo-symbols this gate refuses; because the allowlist requires a
    declared source for EVERY record, the pattern heuristic is subsumed by
    the source check (same rejection code either way).

    Raises ``ValueError`` whose message contains ``pseudo_or_unsourced_symbol``
    for unsourced records, and ``duplicate_instrument_id`` for re-registration.
    Returns the canonical ``instrument_id``.
    """
    src = record.source_identity.strip().upper()
    if src in UNSOURCED_SOURCE_IDENTITIES:
        raise ValueError(
            f"pseudo_or_unsourced_symbol_rejected:{record.instrument_id}:"
            f"source_identity={record.source_identity!r}_not_a_declared_source"
        )
    for known in existing_ids:
        if known == record.instrument_id:
            raise ValueError(f"duplicate_instrument_id:{record.instrument_id}")
    return record.instrument_id


def membership_status_as_of(record: InstrumentRecord, as_of: date) -> InstrumentStatus | None:
    """Half-open as-of membership resolution (boundary: from inclusive, to exclusive).

    - No declared membership intervals -> the record's current ``status``.
    - Matching interval -> that interval's status (first match in list order).
    - Declared intervals but no match as of ``as_of`` -> ``None`` (honestly
      "not a member as of that date", never guessed).
    """
    if not record.membership:
        return record.status
    for interval in record.membership:
        if interval.covers(as_of):
            return interval.status
    return None


def build_default_universe(
    records: Sequence[InstrumentRecord], spec: UniverseSpec
) -> UniverseResolution:
    """Resolve records against ``spec`` (mechanical, order-preserving, fail-closed).

    Every record must first pass :func:`register_instrument` (unsourced/
    pseudo-symbol records abort the whole resolution with ``ValueError`` —
    fail-closed, never silently dropped). Exclusion precedence:
    US_INDIVIDUAL_EQUITY_EXCLUDED, then MARKET_NOT_IN_SPEC, then
    STATUS_NOT_INCLUDED, then TYPE_NOT_ALLOWED — the explicit US-equity
    exclusion is reported in preference to the generic market filter so the
    honest reason is always visible.
    """
    included: list[InstrumentRecord] = []
    excluded: list[tuple[str, str]] = []
    seen: set[str] = set()
    for record in records:
        register_instrument(record, seen)
        seen.add(record.instrument_id)
        if spec.exclude_individual_us_equities and record.market == Market.EXCLUDED_US_EQUITY:
            excluded.append((record.instrument_id, REASON_US_INDIVIDUAL_EQUITY_EXCLUDED))
            continue
        if record.market not in spec.markets:
            excluded.append((record.instrument_id, REASON_MARKET_NOT_IN_SPEC))
            continue
        if record.status not in spec.include_statuses:
            excluded.append((record.instrument_id, REASON_STATUS_NOT_INCLUDED))
            continue
        if record.instrument_type not in spec.instrument_types_allowed:
            excluded.append((record.instrument_id, REASON_TYPE_NOT_ALLOWED))
            continue
        included.append(record)
    return UniverseResolution(
        spec_id=spec.spec_id,
        declared_at_utc=spec.declared_at_utc,
        included=included,
        excluded=excluded,
        considered=len(records),
    )
