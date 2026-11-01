"""Paper tests for the versioned holiday-table contract (Agent E, module 3).

Fail-closed honesty: without a declared table, holiday status is
UNREPRESENTABLE (TRADING_DAY_UNCLASSIFIED) — matching market_session.py's
documented exclusion ("Official holiday calendars are NOT applied"). Tables
are passed inline; no file I/O, no network, no wall clock.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.market_calendar import (
    HolidayEntry,
    MarketHolidayTable,
    is_trading_day,
    load_holiday_table,
    validate_holiday_table,
)

DECLARED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def _table_raw(**over):
    base = {
        "version_id": "tse-holidays-2026-v1",
        "source_ref": "TSE official holiday circular 2026 (paper reference)",
        "declared_by": "owner-declared",
        "declared_at_utc": DECLARED_AT,
        "entries": [
            {"date": "2026-03-21", "name": "نوروز"},
            {"date": "2026-03-22", "name": "عید نوروز - روز دوم"},
        ],
    }
    base.update(over)
    return base


def _table(**over) -> MarketHolidayTable:
    return load_holiday_table(_table_raw(**over))


# ---------------------------------------------------------------------------
# Loading + validation from inline payloads
# ---------------------------------------------------------------------------


def test_load_valid_table_parses_fields_and_orders_entries() -> None:
    table = _table()
    assert table.version_id == "tse-holidays-2026-v1"
    assert table.declared_at_utc == DECLARED_AT
    assert len(table.entries) == 2
    ordered = table.sorted_entries()  # deterministic despite frozenset storage
    assert [e.day for e in ordered] == [date(2026, 3, 21), date(2026, 3, 22)]
    assert [e.name for e in ordered] == ["نوروز", "عید نوروز - روز دوم"]


def test_load_accepts_iso_string_declaration_time_and_pair_entries() -> None:
    table = _table(
        declared_at_utc="2026-01-01T00:00:00+00:00",
        entries=[["2026-03-21", "نوروز"], ("2026-03-22", "عید نوروز - روز دوم")],
    )
    assert table.declared_at_utc == DECLARED_AT
    assert len(table.entries) == 2


def test_refusal_duplicate_dates_via_load() -> None:
    with pytest.raises(ValueError, match="duplicate_holiday_date"):
        _table(
            entries=[
                {"date": "2026-03-21", "name": "نوروز"},
                {"date": "2026-03-21", "name": "دو نام برای یک روز"},
            ]
        )


def test_duplicate_dates_refused_even_on_direct_construction() -> None:
    with pytest.raises(ValueError, match="duplicate_holiday_date"):
        MarketHolidayTable(
            version_id="v1",
            entries=frozenset(
                {
                    HolidayEntry(day=date(2026, 3, 21), name="نوروز"),
                    HolidayEntry(day=date(2026, 3, 21), name="جشن دیگر"),
                }
            ),
            source_ref="ref",
            declared_by="owner-declared",
            declared_at_utc=DECLARED_AT,
        )


def test_refusal_malformed_date() -> None:
    with pytest.raises(ValueError, match="malformed_holiday_date"):
        _table(entries=[{"date": "21/03/2026", "name": "نوروز"}])
    with pytest.raises(ValueError, match="malformed_holiday_date"):
        _table(entries=[{"date": "2026-03-21T10:00:00+00:00", "name": "نوروز"}])  # instant ≠ day


def test_refusal_empty_or_blank_name() -> None:
    with pytest.raises(ValueError, match="holiday_name_must_not_be_empty"):
        _table(entries=[{"date": "2026-03-21", "name": "  "}])


def test_refusal_missing_and_unknown_top_level_fields() -> None:
    raw = _table_raw()
    del raw["source_ref"]
    with pytest.raises(ValueError, match="holiday_table_field_missing: source_ref"):
        load_holiday_table(raw)
    with pytest.raises(ValueError, match="holiday_table_unknown_field: rumor"):
        _table(rumor="unverified")


def test_refusal_non_mapping_payload() -> None:
    with pytest.raises(ValueError, match="holiday_table_payload_must_be_mapping"):
        load_holiday_table([("2026-03-21", "نوروز")])  # type: ignore[arg-type]


def test_refusal_naive_declaration_time_is_normalized_when_aware() -> None:
    with pytest.raises(ValueError, match="timestamp_must_be_timezone_aware"):
        _table(declared_at_utc=datetime(2026, 1, 1, 0, 0))
    table = _table(
        declared_at_utc=datetime(2026, 1, 1, 3, 30, tzinfo=timezone(timedelta(hours=3, minutes=30)))
    )
    assert table.declared_at_utc == DECLARED_AT  # 03:30+03:30 == 00:00Z


# ---------------------------------------------------------------------------
# is_trading_day: fail-closed verdicts
# ---------------------------------------------------------------------------


def test_without_table_holiday_status_is_unrepresentable() -> None:
    assessment = is_trading_day(date(2026, 3, 21), None)
    assert assessment.verdict == "TRADING_DAY_UNCLASSIFIED"
    assert assessment.holiday_name is None
    assert assessment.table_version_id is None
    assert assessment.reason_code == "no_declared_table_holiday_status_unrepresentable"


def test_declared_holiday_returns_name_and_version() -> None:
    table = _table()
    assessment = is_trading_day(date(2026, 3, 21), table)
    assert assessment.verdict == "HOLIDAY"
    assert assessment.holiday_name == "نوروز"
    assert assessment.table_version_id == "tse-holidays-2026-v1"
    assert assessment.reason_code == "date_declared_holiday"


def test_non_holiday_with_table_is_a_limited_trading_day_claim() -> None:
    table = _table()
    assessment = is_trading_day(date(2026, 3, 23), table)
    assert assessment.verdict == "TRADING_DAY"
    assert assessment.holiday_name is None
    assert assessment.reason_code == "date_not_in_declared_table"


def test_is_trading_day_refuses_instant_and_non_date() -> None:
    with pytest.raises(ValueError, match="day_must_be_plain_date"):
        is_trading_day(datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc), _table())  # type: ignore[arg-type]


def test_validate_holiday_table_is_idempotent_and_type_checked() -> None:
    table = _table()
    assert validate_holiday_table(table) is table
    with pytest.raises(ValueError, match="not_a_market_holiday_table"):
        validate_holiday_table({"version_id": "v1"})  # type: ignore[arg-type]
