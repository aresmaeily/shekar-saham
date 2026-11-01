"""Versioned market holiday-table contract, fail-closed (paper).

P1 scope (02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 18-25): trusted
market data. This module completes, without contradicting it, the documented
exclusion of app/domain/market_session.py: "Official holiday calendars are NOT
applied" and "Holidays unknown". Holiday status here is representable ONLY
against an explicitly declared, versioned table; without one the honest answer
is TRADING_DAY_UNCLASSIFIED — holiday status is UNREPRESENTABLE, never
guessed (fail-closed honesty; 06 charter §3: report known gaps, claim nothing
beyond declared coverage).

A declared TRADING_DAY verdict means only "not a declared holiday in this
table version": weekday/weekend semantics remain market_session.py's concern
and are deliberately not re-derived here.

Contract/domain only: no file I/O, no network, no clock reads — tables are
passed inline (tests) or loaded by callers; timestamps are injected.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc

__all__ = [
    "HolidayEntry",
    "MarketHolidayTable",
    "TradingDayAssessment",
    "TradingDayVerdict",
    "is_trading_day",
    "load_holiday_table",
    "validate_holiday_table",
]

TradingDayVerdict = Literal["TRADING_DAY", "HOLIDAY", "TRADING_DAY_UNCLASSIFIED"]

_REQUIRED_FIELDS = ("version_id", "source_ref", "declared_by", "declared_at_utc", "entries")


class HolidayEntry(BaseModel):
    """One declared holiday: a (date, name) pair."""

    model_config = ConfigDict(frozen=True)

    day: date
    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("holiday_name_must_not_be_empty")
        return v


class MarketHolidayTable(BaseModel):
    """One versioned, declared holiday table (immutable value object).

    Two entries on the same day are refused at construction — a versioned
    declaration must be unambiguous about every date it names.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    version_id: str = Field(min_length=1)
    entries: frozenset[HolidayEntry]
    source_ref: str = Field(min_length=1)
    declared_by: str = Field(min_length=1)
    declared_at_utc: datetime

    @field_validator("declared_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _no_duplicate_dates(self) -> "MarketHolidayTable":
        ordered = sorted(self.entries, key=lambda e: (e.day, e.name))
        for prev, cur in zip(ordered, ordered[1:]):
            if prev.day == cur.day:
                raise ValueError("duplicate_holiday_date")
        return self

    def sorted_entries(self) -> tuple[HolidayEntry, ...]:
        """Deterministic (date, name) ordering — frozensets have no order."""
        return tuple(sorted(self.entries, key=lambda e: (e.day, e.name)))

    def holiday_name(self, day: date) -> str | None:
        for entry in self.entries:
            if entry.day == day:
                return entry.name
        return None


def _parse_day(raw: Any) -> date:
    if isinstance(raw, datetime):
        raise ValueError("malformed_holiday_date")  # calendar day, not an instant
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("malformed_holiday_date") from exc
    raise ValueError("malformed_holiday_date")


def _parse_entries(raw_entries: Any) -> frozenset[HolidayEntry]:
    if not isinstance(raw_entries, (list, tuple)):
        raise ValueError("holiday_entries_must_be_list")
    entries: set[HolidayEntry] = set()
    for item in raw_entries:
        if isinstance(item, Mapping):
            unknown = set(item) - {"date", "name"}
            if unknown:
                raise ValueError(f"holiday_entry_unknown_field: {sorted(unknown)[0]}")
            if "date" not in item or "name" not in item:
                raise ValueError("holiday_entry_requires_date_and_name")
            entries.add(HolidayEntry(day=_parse_day(item["date"]), name=str(item["name"])))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            entries.add(HolidayEntry(day=_parse_day(item[0]), name=str(item[1])))
        else:
            raise ValueError("holiday_entry_must_be_mapping_or_pair")
    return frozenset(entries)


def load_holiday_table(raw: Mapping[str, Any]) -> MarketHolidayTable:
    """Load + validate a holiday table from a plain inline dict (no file I/O).

    Refusals (ValueError reason codes):
    - holiday_table_payload_must_be_mapping
    - holiday_table_field_missing: <field> / holiday_table_unknown_field: <field>
    - holiday_entries_must_be_list / holiday_entry_must_be_mapping_or_pair
    - holiday_entry_requires_date_and_name / holiday_entry_unknown_field: <field>
    - malformed_holiday_date / malformed_declared_at_utc
    - holiday_name_must_not_be_empty / duplicate_holiday_date
    - timestamp_must_be_timezone_aware (declared_at_utc, shared vocabulary)
    """
    if not isinstance(raw, Mapping):
        raise ValueError("holiday_table_payload_must_be_mapping")
    for field in _REQUIRED_FIELDS:
        if field not in raw:
            raise ValueError(f"holiday_table_field_missing: {field}")
    for field in sorted(set(raw) - set(_REQUIRED_FIELDS)):
        raise ValueError(f"holiday_table_unknown_field: {field}")
    declared_at = raw["declared_at_utc"]
    if isinstance(declared_at, str):
        try:
            declared_at = datetime.fromisoformat(declared_at)
        except ValueError as exc:
            raise ValueError("malformed_declared_at_utc") from exc
    return MarketHolidayTable(
        version_id=str(raw["version_id"]),
        entries=_parse_entries(raw["entries"]),
        source_ref=str(raw["source_ref"]),
        declared_by=str(raw["declared_by"]),
        declared_at_utc=declared_at,
    )


def validate_holiday_table(table: MarketHolidayTable) -> MarketHolidayTable:
    """Re-validate a table (idempotent); refuses anything not a table."""
    if not isinstance(table, MarketHolidayTable):
        raise ValueError("not_a_market_holiday_table")
    # Construction already enforces duplicate dates, non-empty names and UTC
    # declaration time; re-validate explicitly so the guarantee is local.
    ordered = table.sorted_entries()
    for prev, cur in zip(ordered, ordered[1:]):
        if prev.day == cur.day:
            raise ValueError("duplicate_holiday_date")
    return table


class TradingDayAssessment(BaseModel):
    """Fail-closed verdict for one calendar day."""

    model_config = ConfigDict(frozen=True)

    day: date
    verdict: TradingDayVerdict
    holiday_name: str | None = None
    table_version_id: str | None = None
    reason_code: str = Field(min_length=1)


def is_trading_day(day: date, table: MarketHolidayTable | None) -> TradingDayAssessment:
    """Assess one calendar day against a declared table (or none).

    table None → TRADING_DAY_UNCLASSIFIED: holiday status is unrepresentable
    without a declared, versioned table (fail-closed; market_session.py's
    documented exclusion is honored, not papered over).
    """
    if isinstance(day, datetime) or not isinstance(day, date):
        raise ValueError("day_must_be_plain_date")
    if table is None:
        return TradingDayAssessment(
            day=day,
            verdict="TRADING_DAY_UNCLASSIFIED",
            holiday_name=None,
            table_version_id=None,
            reason_code="no_declared_table_holiday_status_unrepresentable",
        )
    name = table.holiday_name(day)
    if name is not None:
        return TradingDayAssessment(
            day=day,
            verdict="HOLIDAY",
            holiday_name=name,
            table_version_id=table.version_id,
            reason_code="date_declared_holiday",
        )
    return TradingDayAssessment(
        day=day,
        verdict="TRADING_DAY",
        holiday_name=None,
        table_version_id=table.version_id,
        reason_code="date_not_in_declared_table",  # limited claim: only declared entries
    )
