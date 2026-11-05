"""declared_calendars — MASTER-RADAR WAVE-E (2026-11-05): DECLARED session/calendar
model for the supported markets (closes the MR-B1-01 residual).

Relationship to the existing P1 machinery (deliberately additive, zero overlap):
- ``app/domain/market_session.py`` (P3.25): Iran TSE session inference —
  untouched; holidays unknown there by documented design.
- ``app/domain/market_calendar.py`` (WS-1/P1): the versioned holiday-TABLE
  contract with fail-closed ``TRADING_DAY_UNCLASSIFIED`` — untouched; it
  defines HOW a declared table is represented but no actual declared tables
  existed in the repository. THIS module is the missing declaration layer and
  also BRIDGES to that contract: ``as_holiday_table(cal, year)`` materializes
  a calendar's declared fixed-date rules into a validated
  ``MarketHolidayTable`` so the existing ``is_trading_day`` machinery can
  consume it deterministically.

Honesty contract (pinned):

1. **Trust class**: every calendar payload carries ``trust_class: "DECLARED"``
   — a calendar-specific marker (NOT the series-level ``TrustClass`` enum;
   series keep their exhaustive 7-value taxonomy). DECLARED means: this
   session/holiday model is a REPOSITORY DECLARATION, written into the code,
   version-stamped, and deterministic — it is NOT a sourced authoritative
   holiday table and NEVER claims to be one.
2. **Owner-gated boundary**: authoritative sourced holiday tables are external
   intelligence and stay owner-gated under R-3/R-7 (Two-Key Rule). No provider
   call, no network, no file IO happens anywhere in this module — the only
   inputs are the declared rules below and the caller-supplied instant.
3. **Determinism**: ``session_state(calendar_id, as_of_utc)`` is a pure
   function of its inputs (zoneinfo conversions + declared rules); the same
   inputs always produce the same answer. The API surface therefore REQUIRES
   the caller to state ``as_of_utc`` explicitly — the server never reads a
   wall clock for calendar decisions (consistent with the data-quality
   family's no-wall-clock gate).
4. **Declared scope, disclosed gaps**: holiday rules are fixed-date rules only
   (month/day). Weekend-adjacency moves (e.g. a holiday falling on a weekend),
   substitution days, government ad-hoc closures, intraday halts and
   auction windows are NOT modeled — every payload discloses this. The Iran
   Nowruz window is declared as an APPROXIMATE multi-day range, not exact.
5. **Session rules**: weekday/time windows are declared in the market's own
   timezone (zoneinfo) and converted from the caller-supplied UTC instant.
   No minute-level auction phases are modeled (disclosed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from app.domain.market_calendar import MarketHolidayTable, load_holiday_table

CALENDAR_TRUST_DECLARED = "DECLARED"

OWNER_GATE_NOTE = (
    "sourced authoritative holiday tables are external intelligence and stay "
    "owner-gated (R-3/R-7, Two-Key Rule); this model never claims sourced status"
)

GAPS_NOTE = (
    "declared scope: fixed-date holiday rules and weekday session windows only; "
    "weekend-adjacency moves, substitution days, ad-hoc closures, intraday halts "
    "and auction phases are NOT modeled"
)

# Fixed deterministic declaration instant for the P1 table bridge (the module
# itself never reads a wall clock; the table's declared_at_utc is part of the
# declaration, not an observation).
_DECLARED_AT_UTC = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SessionWindow:
    """One weekday session window in the calendar's own timezone."""

    weekdays: Tuple[int, ...]  # 0=Monday .. 6=Sunday (Python date.weekday())
    start: str  # "HH:MM" local
    end: str  # "HH:MM" local
    label: str = "REGULAR"


@dataclass(frozen=True)
class HolidayRule:
    """A fixed-date declared holiday rule (month/day), optionally a range."""

    name: str
    month: int
    day: int  # ignored when day_span is set (range uses month/day as start)
    day_span: int = 1  # 1 = single day; >1 = consecutive-days range
    note: str = ""


@dataclass(frozen=True)
class DeclaredCalendar:
    calendar_id: str
    market: str
    timezone: str
    sessions: Tuple[SessionWindow, ...]
    holidays: Tuple[HolidayRule, ...]
    declared_version: str
    notes: Tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Declared calendars (repository declarations, version-stamped)
# ---------------------------------------------------------------------------

_IRAN_NOTES = (
    "Tehran Stock Exchange / Iran Farabourse declared pattern: Saturday..Wednesday "
    "regular sessions; Thursday and Friday closed (declared weekend).",
    "The Nowruz window is declared as an APPROXIMATE multi-day range around the "
    "vernal equinox — exact civil-year holiday dates are owner-gated (not sourced).",
)

IRAN_CAL = DeclaredCalendar(
    calendar_id="IR_EQ_CAL_DECLARED_V1",
    market="IRAN_TSE/IRAN_IFB",
    timezone="Asia/Tehran",
    sessions=(
        SessionWindow(weekdays=(5, 6, 0, 1, 2), start="08:30", end="12:30"),
        # weekday() mapping: Saturday=5, Sunday=6, Monday=0, Tuesday=1, Wednesday=2
    ),
    holidays=(
        HolidayRule(name="Nowruz (declared approximate window)", month=3, day=20, day_span=12,
                    note="approximate declared range; exact dates owner-gated"),
        HolidayRule(name="Islamic Republic Day (declared fixed-date rule)", month=4, day=1),
        HolidayRule(name="Khomeini Passing Anniversary (declared fixed-date rule)", month=6, day=4),
        HolidayRule(name="Government Day (declared fixed-date rule)", month=11, day=13),
    ),
    declared_version="2026-11-05.v1",
    notes=_IRAN_NOTES,
)

FX_NOTES = (
    "Forex interbank convention declared as 24/5: continuous from Sunday 22:00 UTC "
    "(Sydney open) to Friday 22:00 UTC (New York close); Saturday and Sunday closed.",
    "Session labels (Sydney/Tokyo/London/NewYork) are DECLARED conveniences for the "
    "fixture universe; no provider session feed exists (R-3).",
)

FX_CAL = DeclaredCalendar(
    calendar_id="FX_CAL_DECLARED_V1",
    market="FOREX",
    timezone="UTC",
    sessions=(
        SessionWindow(weekdays=(6,), start="22:00", end="23:59"),  # Sunday evening open
        SessionWindow(weekdays=(0, 1, 2, 3), start="00:00", end="23:59"),  # Mon..Thu continuous
        SessionWindow(weekdays=(4,), start="00:00", end="22:00"),  # Friday until NY close
    ),
    holidays=(),  # forex has no declared exchange-holiday rules at this scope
    declared_version="2026-11-05.v1",
    notes=FX_NOTES,
)

US_NOTES = (
    "US equity-index cash sessions declared as Monday..Friday 09:30-16:00 "
    "America/New_York.",
    "Holiday rules are fixed-date only (New Year, Juneteenth, Independence Day, "
    "Christmas); floating rules (e.g. Thanksgiving) and half-days are outside "
    "declared scope and disclosed.",
)

US_CAL = DeclaredCalendar(
    calendar_id="US_IDX_CAL_DECLARED_V1",
    market="US_INDEX",
    timezone="America/New_York",
    sessions=(
        SessionWindow(weekdays=(0, 1, 2, 3, 4), start="09:30", end="16:00"),
    ),
    holidays=(
        HolidayRule(name="New Year's Day (declared fixed-date rule)", month=1, day=1),
        HolidayRule(name="Juneteenth (declared fixed-date rule)", month=6, day=19),
        HolidayRule(name="Independence Day (declared fixed-date rule)", month=7, day=4),
        HolidayRule(name="Christmas Day (declared fixed-date rule)", month=12, day=25),
    ),
    declared_version="2026-11-05.v1",
    notes=US_NOTES,
)

_CALENDARS: Dict[str, DeclaredCalendar] = {
    c.calendar_id: c for c in (IRAN_CAL, FX_CAL, US_CAL)
}

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

STATE_OPEN = "OPEN"
STATE_CLOSED = "CLOSED"
STATE_WEEKEND = "WEEKEND"
STATE_HOLIDAY = "DECLARED_HOLIDAY"


class CalendarNotDeclared(KeyError):
    """Unknown calendar_id — never guessed, never defaulted."""


class InvalidAsOf(ValueError):
    """Malformed caller instant — fail-closed."""


def _parse_hhmm(s: str) -> time:
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"bad HH:MM: {s!r}")
    return time(int(parts[0]), int(parts[1]))


def _holiday_hit(cal: DeclaredCalendar, local_date: date) -> Optional[HolidayRule]:
    for rule in cal.holidays:
        try:
            start = date(local_date.year, rule.month, rule.day)
        except ValueError:
            # declared rule falls on a nonexistent civil date this year —
            # the rule simply does not hit; disclosed scope
            continue
        end = start + timedelta(days=rule.day_span - 1)
        if start <= local_date <= end:
            return rule
    return None


def _is_declared_weekend(cal: DeclaredCalendar, local_date: date) -> bool:
    """Weekend = no session window covers this weekday at all (declared)."""
    covered = set()
    for w in cal.sessions:
        covered.update(w.weekdays)
    return local_date.weekday() not in covered


def session_state(calendar_id: str, as_of_utc: datetime) -> Dict[str, Any]:
    """Deterministic declared session state. Pure function of its inputs."""
    cal = _CALENDARS.get(calendar_id)
    if cal is None:
        raise CalendarNotDeclared(calendar_id)
    if as_of_utc.tzinfo is None:
        raise InvalidAsOf("as_of_utc must carry an explicit UTC offset")
    as_of_utc = as_of_utc.astimezone(timezone.utc)
    local_tz = ZoneInfo(cal.timezone)
    local_dt = as_of_utc.astimezone(local_tz)
    local_date = local_dt.date()
    local_time = local_dt.time()

    holiday = _holiday_hit(cal, local_date)
    weekend = _is_declared_weekend(cal, local_date)

    in_window = False
    window_note = ""
    if not weekend and holiday is None:
        for w in cal.sessions:
            if local_date.weekday() in w.weekdays:
                start = _parse_hhmm(w.start)
                end = _parse_hhmm(w.end)
                if start <= local_time <= end:
                    in_window = True
                    window_note = f"{w.start}-{w.end} {w.label}"
                    break

    if holiday is not None:
        state = STATE_HOLIDAY
        detail = f"{holiday.name} ({cal.timezone} {local_date.isoformat()})"
    elif weekend:
        state = STATE_WEEKEND
        detail = f"no declared session on {WEEKDAY_NAMES[local_date.weekday()]} ({cal.timezone} {local_date.isoformat()})"
    elif in_window:
        state = STATE_OPEN
        detail = f"declared window {window_note} ({cal.timezone} {local_date.isoformat()})"
    else:
        state = STATE_CLOSED
        detail = f"outside declared windows on a declared session day ({cal.timezone} {local_date.isoformat()})"

    return {
        "calendar_id": cal.calendar_id,
        "market": cal.market,
        "timezone": cal.timezone,
        "as_of_utc": as_of_utc.isoformat(),
        "as_of_local": local_dt.isoformat(),
        "state": state,
        "detail": detail,
        "trust_class": CALENDAR_TRUST_DECLARED,
        "declared_version": cal.declared_version,
        "honesty": {
            "owner_gate_note": OWNER_GATE_NOTE,
            "declared_scope_gaps": GAPS_NOTE,
            "no_wall_clock": "state is a pure function of the caller-supplied as_of_utc and the declared rules",
        },
    }


def calendar_payload(cal: DeclaredCalendar) -> Dict[str, Any]:
    """Honest full disclosure payload for one declared calendar."""
    return {
        "calendar_id": cal.calendar_id,
        "market": cal.market,
        "timezone": cal.timezone,
        "declared_version": cal.declared_version,
        "trust_class": CALENDAR_TRUST_DECLARED,
        "sessions": [
            {
                "weekdays": [WEEKDAY_NAMES[d] for d in w.weekdays],
                "start_local": w.start,
                "end_local": w.end,
                "label": w.label,
            }
            for w in cal.sessions
        ],
        "declared_holiday_rules": [
            {
                "name": h.name,
                "rule": f"month={h.month} day={h.day}" + (f" span={h.day_span}d" if h.day_span > 1 else ""),
                "note": h.note or None,
            }
            for h in cal.holidays
        ],
        "notes": list(cal.notes),
        "honesty": {
            "owner_gate_note": OWNER_GATE_NOTE,
            "declared_scope_gaps": GAPS_NOTE,
        },
    }


def list_calendars() -> Dict[str, Any]:
    return {
        "trust_class": CALENDAR_TRUST_DECLARED,
        "count": len(_CALENDARS),
        "calendars": [calendar_payload(c) for c in _CALENDARS.values()],
        "honesty": {
            "owner_gate_note": OWNER_GATE_NOTE,
            "declared_scope_gaps": GAPS_NOTE,
            "no_wall_clock": "the /session-state surface requires the caller to state as_of_utc; the server never reads a wall clock",
        },
    }


def get_calendar(calendar_id: str) -> Dict[str, Any]:
    cal = _CALENDARS.get(calendar_id)
    if cal is None:
        raise CalendarNotDeclared(calendar_id)
    return calendar_payload(cal)


def as_holiday_table(cal: DeclaredCalendar, year: int) -> MarketHolidayTable:
    """WAVE-E bridge to the P1 contract: materialize this calendar's declared
    fixed-date rules into a validated ``MarketHolidayTable`` for ``year`` so
    the existing ``is_trading_day`` machinery can consume them.

    Deterministic: same (calendar, year) -> identical table. Range rules
    materialize one entry per covered civil day. Nonexistent civil dates
    (e.g. Feb 30) are skipped (disclosed scope). The declaration instant is a
    fixed constant — no wall clock. Version id embeds the calendar id, the
    calendar's declared_version and the materialization year.
    """
    entries = []
    for rule in cal.holidays:
        try:
            start = date(year, rule.month, rule.day)
        except ValueError:
            continue
        for i in range(rule.day_span):
            day = start + timedelta(days=i)
            name = rule.name if rule.day_span == 1 else f"{rule.name} (day {i + 1}/{rule.day_span})"
            entries.append({"date": day.isoformat(), "name": name})
    return load_holiday_table(
        {
            "version_id": f"{cal.calendar_id}.{cal.declared_version}.year-{year}",
            "entries": entries,
            "source_ref": f"repository-declared:{cal.calendar_id}@{cal.declared_version}",
            "declared_by": "repository (DECLARED — not a sourced table)",
            "declared_at_utc": _DECLARED_AT_UTC.isoformat(),
        }
    )
