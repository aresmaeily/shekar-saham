"""Point-in-time universe membership (P2, purely additive).

Corpus loci (2026-10-02 amendment corpus):
- 02_EXECUTION_ROADMAP lines 24-26 ("P2 --- Deterministic Measurement &
  Evidence Core"): "PIT, corporate actions, survivorship, look-ahead
  protection, ...".
- 02_EXECUTION_ROADMAP line 145 ("P3 --- Evaluation and research
  integrity"): "... survivorship/corporate-action handling ...".
- 06 Product Capability Charter, "Research and feedback": reproducible
  runs with point-in-time correctness.

Scope: a versioned (caller-supplied, inline) membership table mapping each
symbol to its listing interval(s), point-in-time membership queries over
it, and a composition with the EXISTING survivorship guard
(``app.domain.survivorship_guard`` — imported and delegated, never copied).
No I/O, no network, no wall-clock: every date is an explicit parameter.

Boundary convention (pinned, tested): intervals are HALF-OPEN
``[effective_from, effective_to)`` — a symbol is a member at ``as_of``
iff ``effective_from <= as_of`` and (``effective_to is None`` or
``as_of < effective_to``). This matches survivorship_guard.py's documented
boundary semantics exactly (listed iff ``listed_from_ts <= evaluation``;
delisted-before/at iff ``delisted_at_ts <= evaluation``): on the listing
date itself the symbol is IN; on the delist date itself it is already OUT.
``effective_to is None`` means still listed as far as the table knows
(honest unknown, never invented).

Fail-closed refusals (mirroring market_calendar / regime_slices /
holdout precedents — the module never re-sorts or repairs input):
- ``UNORDERED_MEMBERSHIP_ENTRIES``   — entries must arrive canonically
  ordered by ``(effective_from, symbol_id)`` ascending
- ``OVERLAPPING_MEMBERSHIP_INTERVALS`` — same-symbol intervals must be
  disjoint (touching is allowed: ``[a, b)`` then ``[b, None)`` is a valid
  delist→relist pair)
- ``INVALID_MEMBERSHIP_INTERVAL``    — ``effective_to <= effective_from``
- ``MULTI_INTERVAL_SYMBOL_NOT_COMPOSABLE`` — the survivorship composition
  requires exactly one lifecycle interval per symbol (survivorship_guard's
  ``UniverseMember`` carries ONE ``listed_from_ts``/``delisted_at_ts``
  pair; merging intervals would fabricate a continuous listing)
- ``SNAPSHOT_SYMBOL_NOT_IN_TABLE``   — a snapshot symbol the table does
  not know cannot be certified (fail-closed, never dropped silently)

Status vocabulary (closed): MEMBER / NOT_YET_LISTED / DELISTED /
UNKNOWN_UNCLASSIFIED. Absence from the table is NOT ``NOT_YET_LISTED`` —
an incomplete table must not manufacture listings; the honest answer is
``UNKNOWN_UNCLASSIFIED`` (fail-closed unknown). An interior gap between a
symbol's declared intervals is likewise ``UNKNOWN_UNCLASSIFIED``: a real
delist→relist gap and a data hole are indistinguishable from the table
alone, and the module claims neither.

Timestamp domain: ``date.toordinal()`` as float (day granularity,
deterministic, no clock) — chosen so the composition feeds
survivorship_guard's float-timestamp comparisons without conversion loss.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.survivorship_guard import (
    SurvivorshipVerdict,
    UniverseMember,
    UniverseSnapshot,
    survivorship_check,
)

__all__ = [
    "MembershipEntry",
    "MembershipError",
    "MembershipStatus",
    "MembershipTable",
    "members_asof",
    "status_asof",
    "survivorship_risk_verdict",
]

#: Closed membership-status vocabulary; UNKNOWN_UNCLASSIFIED is the
#: fail-closed answer whenever the table cannot honestly classify.
MembershipStatus = Literal[
    "MEMBER",
    "NOT_YET_LISTED",
    "DELISTED",
    "UNKNOWN_UNCLASSIFIED",
]


class MembershipError(ValueError):
    """Deterministic fail-closed refusal with a machine-readable reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}:{detail}" if detail else reason
        super().__init__(message)


def _plain_date(value: object, name: str) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise MembershipError(f"{name.upper()}_MUST_BE_PLAIN_DATE", f"value={value!r}")
    return value


def _ordinal(day: date) -> float:
    """Deterministic day-granularity timestamp (no clock, no locale)."""
    return float(day.toordinal())


class MembershipEntry(BaseModel):
    """One listing interval ``[effective_from, effective_to)``.

    ``effective_to is None`` means still listed as far as the table knows.
    """

    model_config = ConfigDict(frozen=True)

    symbol_id: str = Field(min_length=1, max_length=64)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def _nonempty_interval(self) -> "MembershipEntry":
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("invalid_membership_interval")
        return self


class MembershipTable(BaseModel):
    """Frozen, versioned-by-input membership table (value object).

    Construction refuses unordered or overlapping input — the caller's
    chronological declaration is data, never something the module silently
    repairs (market_calendar's duplicate-date refusal precedent).
    """

    model_config = ConfigDict(frozen=True)

    entries: tuple[MembershipEntry, ...]

    @field_validator("entries")
    @classmethod
    def _ordered_and_disjoint(
        cls, v: tuple[MembershipEntry, ...]
    ) -> tuple[MembershipEntry, ...]:
        previous: MembershipEntry | None = None
        # per-symbol previous interval end; None encodes an open-ended
        # interval [a, None) which any further same-symbol entry overlaps.
        prior_end: dict[str, date | None] = {}
        for index, entry in enumerate(v):
            key = (entry.effective_from, entry.symbol_id)
            if previous is not None:
                previous_key = (previous.effective_from, previous.symbol_id)
                if key < previous_key:
                    raise ValueError(f"unordered_membership_entries:index={index}")
                if key == previous_key:
                    # same symbol, same start — the intervals overlap
                    raise ValueError(f"overlapping_membership_intervals:index={index}")
            if entry.symbol_id in prior_end:
                prior = prior_end[entry.symbol_id]
                if prior is None or entry.effective_from < prior:
                    raise ValueError(
                        f"overlapping_membership_intervals:index={index}"
                    )
            prior_end[entry.symbol_id] = entry.effective_to
            previous = entry
        return v


def _intervals_for(table: MembershipTable, symbol_id: str) -> tuple[MembershipEntry, ...]:
    return tuple(e for e in table.entries if e.symbol_id == symbol_id)


def _covers(entry: MembershipEntry, day: date) -> bool:
    if day < entry.effective_from:
        return False
    if entry.effective_to is None:
        return True
    return day < entry.effective_to  # half-open: effective_to is EXCLUSIVE


def members_asof(table: MembershipTable, as_of: date) -> tuple[str, ...]:
    """Point-in-time member set: every symbol whose interval covers ``as_of``.

    Boundary (pinned): ``effective_from <= as_of < effective_to`` (or
    ``effective_to is None``). Returns a deterministically sorted tuple.
    """
    day = _plain_date(as_of, "as_of")
    return tuple(sorted({e.symbol_id for e in table.entries if _covers(e, day)}))


def status_asof(table: MembershipTable, symbol_id: str, as_of: date) -> MembershipStatus:
    """Closed-status classification of one symbol at one date (fail-closed).

    Deterministic precedence:
    1. symbol has NO entries in the table      → UNKNOWN_UNCLASSIFIED
       (absence from an incomplete table proves nothing — never
       NOT_YET_LISTED)
    2. some interval covers ``as_of``          → MEMBER
    3. ``as_of < first effective_from``        → NOT_YET_LISTED (declared data)
    4. ``as_of >= last effective_to``          → DELISTED (declared data)
    5. otherwise (interior gap)                → UNKNOWN_UNCLASSIFIED
       (delist→relist gap vs data hole is indistinguishable here)
    """
    day = _plain_date(as_of, "as_of")
    entries = _intervals_for(table, symbol_id)
    if not entries:
        return "UNKNOWN_UNCLASSIFIED"
    for entry in entries:
        if _covers(entry, day):
            return "MEMBER"
    if day < entries[0].effective_from:
        return "NOT_YET_LISTED"
    last = entries[-1]
    if last.effective_to is not None and day >= last.effective_to:
        return "DELISTED"
    return "UNKNOWN_UNCLASSIFIED"


def survivorship_risk_verdict(
    table: MembershipTable,
    evaluation_as_of: date,
    snapshot_symbol_ids: Sequence[str],
    snapshot_as_of: date | None = None,
) -> SurvivorshipVerdict:
    """Compose the PIT membership table with the EXISTING survivorship guard.

    Delegates the verdict to ``survivorship_guard.survivorship_check``
    (imported, not copied): the table becomes the expected registry, the
    caller's snapshot symbol ids become the evaluation universe. A backtest
    universe built from TODAY'S members while the PIT set differs is thus
    classified with the guard's own semantics — ANACHRONISTIC_MEMBER for
    members listed after the evaluation point, SURVIVORSHIP_BIAS_RISK for
    delisted members silently excluded, INCOMPLETE_UNIVERSE for missing
    still-listed members, OK otherwise.

    Refusals (this module, fail-closed before delegation):
    - ``MULTI_INTERVAL_SYMBOL_NOT_COMPOSABLE`` — a symbol with more than
      one interval has no single lifecycle to hand the guard (merging
      intervals would fabricate a continuous listing)
    - ``SNAPSHOT_SYMBOL_NOT_IN_TABLE`` — an unknown snapshot symbol can
      never be certified
    ``snapshot_as_of`` defaults to the evaluation date; a LATER value is
    honestly flagged by the guard itself (SNAPSHOT_AS_OF_AFTER_EVALUATION_AS_OF).
    """
    evaluation_day = _plain_date(evaluation_as_of, "evaluation_as_of")
    snapshot_day = (
        _plain_date(snapshot_as_of, "snapshot_as_of")
        if snapshot_as_of is not None
        else evaluation_day
    )

    by_symbol: dict[str, MembershipEntry] = {}
    for entry in table.entries:
        if entry.symbol_id in by_symbol:
            raise MembershipError(
                "MULTI_INTERVAL_SYMBOL_NOT_COMPOSABLE",
                f"symbol={entry.symbol_id} (survivorship_guard consumes one "
                "lifecycle interval per symbol)",
            )
        by_symbol[entry.symbol_id] = entry

    expected_members: list[UniverseMember] = []
    for symbol_id, entry in by_symbol.items():
        expected_members.append(
            UniverseMember(
                symbol_id=symbol_id,
                listed_from_ts=_ordinal(entry.effective_from),
                delisted_at_ts=(
                    _ordinal(entry.effective_to)
                    if entry.effective_to is not None
                    else None
                ),
            )
        )

    snapshot_members: list[UniverseMember] = []
    for symbol_id in snapshot_symbol_ids:
        entry = by_symbol.get(symbol_id)
        if entry is None:
            raise MembershipError(
                "SNAPSHOT_SYMBOL_NOT_IN_TABLE",
                f"symbol={symbol_id}",
            )
        snapshot_members.append(
            UniverseMember(
                symbol_id=symbol_id,
                listed_from_ts=_ordinal(entry.effective_from),
                delisted_at_ts=(
                    _ordinal(entry.effective_to)
                    if entry.effective_to is not None
                    else None
                ),
            )
        )

    snapshot = UniverseSnapshot(
        as_of_ts=_ordinal(snapshot_day),
        members=tuple(snapshot_members),
    )
    return survivorship_check(
        snapshot,
        _ordinal(evaluation_day),
        expected_members,
    )
