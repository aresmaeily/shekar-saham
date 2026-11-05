"""MASTER-RADAR WAVE-E (2026-11-05): DECLARED session/calendar model tests.

Closes the MR-B1-01 residual: declared session/calendar model for the
supported markets with an honest calendar-level DECLARED trust marker
(series-level TrustClass enum untouched). Sourced authoritative holiday
tables stay owner-gated (R-3/R-7); the module performs no network, no file
IO, and — on the API surface — never reads a wall clock (as_of_utc is
REQUIRED from the caller).

Relationship to the existing P1 suite (tests/test_market_calendar.py, 14
tests, untouched): that file pins the versioned holiday-TABLE contract; this
file pins the DECLARED declaration layer built on top of it plus the
``as_holiday_table`` bridge that feeds the existing ``is_trading_day``
machinery deterministically.

Pinned contracts under test:
1. Determinism: same (calendar_id, as_of_utc) -> identical payload (no wall
   clock anywhere in the state function; the trust envelope's checked_at is
   the canonical wall-clock instant and excluded from byte-identity, same
   convention as the strategylab exports).
2. Session logic per declared calendar: Iran Sat..Wed 08:30-12:30 Tehran,
   Forex 24/5 UTC convention, US Mon..Fri 09:30-16:00 New York.
3. Declared fixed-date holiday rules hit (and the approximate Nowruz range
   declared to end Mar 31 so the Apr 1 rule stays unambiguous per the P1
   duplicate-date contract), weekend classification, closed-vs-open bounds.
4. Honesty envelope: trust_class DECLARED, owner-gate note, disclosed scope
   gaps, declared_version on every payload.
5. Fail-closed: unknown calendar_id -> CalendarNotDeclared (404 at the API),
   naive as_of -> InvalidAsOf (422), malformed as_of -> 422, missing
   as_of_utc -> 422 (never a silent wall-clock default).
6. API surface: /dataquality/calendars, /calendars/{id}, /calendars/{id}/
   session-state — additive under the governed prefix.
7. P1 bridge: as_holiday_table materialization is deterministic, range rules
   expand, duplicate dates are impossible, and is_trading_day consumes the
   materialized table (HOLIDAY / TRADING_DAY verdicts) while the fail-closed
   UNCLASSIFIED semantics without a table remain untouched.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain import declared_calendars as dc

# Settings-cache hygiene (same pattern as test_report_pdf.py)
@pytest.fixture(autouse=True)
def _settings_cache_hygiene():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _utc(y: int, mo: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# determinism + honesty envelope
# ---------------------------------------------------------------------------

def test_session_state_is_pure_and_deterministic():
    a = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 11, 7, 6, 0))
    b = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 11, 7, 6, 0))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_every_payload_carries_declared_trust_and_honesty():
    listing = dc.list_calendars()
    assert listing["trust_class"] == "DECLARED"
    for cal in listing["calendars"]:
        assert cal["trust_class"] == "DECLARED"
        assert cal["declared_version"]
        assert "owner-gated" in cal["honesty"]["owner_gate_note"]
        assert "NOT modeled" in cal["honesty"]["declared_scope_gaps"]
    state = dc.session_state("FX_CAL_DECLARED_V1", _utc(2026, 11, 9, 12, 0))
    assert state["trust_class"] == "DECLARED"
    assert state["declared_version"] == "2026-11-05.v1"
    assert state["honesty"]["no_wall_clock"].startswith("state is a pure function")


def test_unknown_calendar_fails_closed():
    with pytest.raises(dc.CalendarNotDeclared):
        dc.session_state("NOT_A_CALENDAR", _utc(2026, 11, 9, 12, 0))
    with pytest.raises(dc.CalendarNotDeclared):
        dc.get_calendar("NOT_A_CALENDAR")


def test_naive_instant_refused():
    with pytest.raises(dc.InvalidAsOf):
        dc.session_state("FX_CAL_DECLARED_V1", datetime(2026, 11, 9, 12, 0))  # naive


# ---------------------------------------------------------------------------
# Iran declared calendar (Asia/Tehran, Sat..Wed 08:30-12:30)
# ---------------------------------------------------------------------------

def test_iran_saturday_midday_open():
    st = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 11, 7, 6, 30))
    assert st["state"] == "OPEN"
    assert "08:30-12:30" in st["detail"]
    assert st["as_of_local"].startswith("2026-11-07T10:00")


def test_iran_friday_weekend():
    st = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 11, 6, 6, 30))
    assert st["state"] == "WEEKEND"


def test_iran_thursday_weekend():
    st = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 11, 5, 5, 30))
    assert st["state"] == "WEEKEND"


def test_iran_before_open_closed():
    st = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 11, 7, 3, 30))
    assert st["state"] == "CLOSED"


def test_iran_after_close_closed():
    st = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 11, 7, 10, 30))
    assert st["state"] == "CLOSED"


def test_iran_nowruz_declared_range_hits():
    st = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 3, 25, 6, 30))
    assert st["state"] == "DECLARED_HOLIDAY"
    assert "Nowruz" in st["detail"]


def test_iran_nowruz_range_ends_mar31_ap1_rule_unambiguous():
    # Apr 1 = Islamic Republic Day rule (the Nowruz span ends Mar 31 so the
    # P1 duplicate-date contract holds); Apr 2 2026 is a Thursday (weekend).
    st1 = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 4, 1, 6, 30))
    assert st1["state"] == "DECLARED_HOLIDAY"
    assert "Islamic Republic Day" in st1["detail"]
    st2 = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 4, 2, 6, 30))
    assert st2["state"] == "WEEKEND"


def test_iran_fixed_holiday_rule_hits():
    # Khomeini Passing declared rule: month=6 day=4 -> Jun 4 2026 (Thursday, a
    # declared non-session day). The holiday classification WINS over weekend
    # (precedence pinned; weekend-adjacency moves are NOT modeled — the
    # fixed-date rule hit is disclosed as-is).
    st = dc.session_state("IR_EQ_CAL_DECLARED_V1", _utc(2026, 6, 4, 6, 30))
    assert st["state"] == "DECLARED_HOLIDAY"
    assert "Khomeini" in st["detail"]


# ---------------------------------------------------------------------------
# Forex declared calendar (UTC 24/5 convention)
# ---------------------------------------------------------------------------

def test_forex_monday_open():
    st = dc.session_state("FX_CAL_DECLARED_V1", _utc(2026, 11, 9, 12, 0))
    assert st["state"] == "OPEN"


def test_forex_saturday_weekend():
    st = dc.session_state("FX_CAL_DECLARED_V1", _utc(2026, 11, 7, 12, 0))
    assert st["state"] == "WEEKEND"


def test_forex_sunday_evening_open():
    st = dc.session_state("FX_CAL_DECLARED_V1", _utc(2026, 11, 8, 23, 0))
    assert st["state"] == "OPEN"


def test_forex_sunday_afternoon_closed():
    # Sunday 14:00 UTC — before the declared 22:00 open. Sunday HAS a declared
    # (evening) window, so the declared state is CLOSED (outside declared
    # windows on a day with a declared window), not WEEKEND — semantics pinned.
    st = dc.session_state("FX_CAL_DECLARED_V1", _utc(2026, 11, 8, 14, 0))
    assert st["state"] == "CLOSED"


def test_forex_friday_after_close_closed():
    st = dc.session_state("FX_CAL_DECLARED_V1", _utc(2026, 11, 6, 23, 0))
    assert st["state"] == "CLOSED"


def test_forex_friday_just_before_close_open():
    st = dc.session_state("FX_CAL_DECLARED_V1", _utc(2026, 11, 6, 21, 59))
    assert st["state"] == "OPEN"


# ---------------------------------------------------------------------------
# US declared calendar (America/New_York, Mon..Fri 09:30-16:00)
# ---------------------------------------------------------------------------

def test_us_monday_midday_open():
    st = dc.session_state("US_IDX_CAL_DECLARED_V1", _utc(2026, 11, 9, 17, 0))
    assert st["state"] == "OPEN"
    assert st["timezone"] == "America/New_York"


def test_us_saturday_weekend():
    st = dc.session_state("US_IDX_CAL_DECLARED_V1", _utc(2026, 11, 7, 17, 0))
    assert st["state"] == "WEEKEND"


def test_us_christmas_holiday():
    st = dc.session_state("US_IDX_CAL_DECLARED_V1", _utc(2026, 12, 25, 17, 0))
    assert st["state"] == "DECLARED_HOLIDAY"
    assert "Christmas" in st["detail"]


def test_us_pre_open_closed():
    st = dc.session_state("US_IDX_CAL_DECLARED_V1", _utc(2026, 11, 9, 14, 0))
    assert st["state"] == "CLOSED"


def test_us_dst_transition_handled_deterministically():
    # 2026-07-06 (EDT, -4): Monday 12:00 New York == 16:00 UTC -> OPEN
    st = dc.session_state("US_IDX_CAL_DECLARED_V1", _utc(2026, 7, 6, 16, 0))
    assert st["state"] == "OPEN"


# ---------------------------------------------------------------------------
# API surface (additive under the governed /api/v10/dataquality prefix)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client() -> TestClient:
    from app.main import app

    # Distinct rate-limit identity (AUDIT-MR2 contract; census 12345..12350 —
    # this module uses 12351 so no later health/limiter-sensitive test is
    # starved by module order).
    with TestClient(app, client=("mr-wavee-cal", 12351)) as c:
        yield c


def test_api_calendars_listing(client: TestClient):
    r = client.get("/api/v10/dataquality/calendars")
    assert r.status_code == 200
    d = r.json()
    assert d["trust_class"] == "DECLARED"
    assert d["count"] == 3
    assert d["synthetic_note"]
    assert d["trust_envelope"]["trust_level"]
    ids = {c["calendar_id"] for c in d["calendars"]}
    assert ids == {"IR_EQ_CAL_DECLARED_V1", "FX_CAL_DECLARED_V1", "US_IDX_CAL_DECLARED_V1"}


def test_api_calendar_detail(client: TestClient):
    r = client.get("/api/v10/dataquality/calendars/IR_EQ_CAL_DECLARED_V1")
    assert r.status_code == 200
    d = r.json()
    assert d["timezone"] == "Asia/Tehran"
    assert any("Nowruz" in h["name"] for h in d["declared_holiday_rules"])
    assert d["trust_envelope"]["data_trust"]["state"]


def test_api_calendar_detail_unknown_404(client: TestClient):
    r = client.get("/api/v10/dataquality/calendars/NOPE")
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "CALENDAR_NOT_DECLARED"


def test_api_session_state_deterministic_and_honest(client: TestClient):
    q = "2026-11-09T12:00:00+00:00"  # Monday noon UTC -> forex OPEN
    a = client.get("/api/v10/dataquality/calendars/FX_CAL_DECLARED_V1/session-state", params={"as_of_utc": q})
    b = client.get("/api/v10/dataquality/calendars/FX_CAL_DECLARED_V1/session-state", params={"as_of_utc": q})
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["state"] == "OPEN"
    # the calendar payload itself is deterministic; the trust envelope carries
    # the canonical wall-clock checked_at by design (same convention as the
    # strategylab exports) — byte-identity is pinned for the calendar part.
    strip = lambda d: {k: v for k, v in d.items() if k not in ("trust_envelope",)}
    assert json.dumps(strip(a.json()), sort_keys=True) == json.dumps(strip(b.json()), sort_keys=True)
    assert "checked_at" in a.json()["trust_envelope"]["data_trust"]


def test_api_session_state_z_suffix_accepted(client: TestClient):
    r = client.get("/api/v10/dataquality/calendars/US_IDX_CAL_DECLARED_V1/session-state", params={"as_of_utc": "2026-12-25T17:00:00Z"})
    assert r.status_code == 200
    assert r.json()["state"] == "DECLARED_HOLIDAY"


def test_api_session_state_requires_as_of(client: TestClient):
    r = client.get("/api/v10/dataquality/calendars/FX_CAL_DECLARED_V1/session-state")
    assert r.status_code == 422  # FastAPI missing-query 422 — never a silent wall-clock default


@pytest.mark.parametrize("bad", ["not-a-date", "2026-11-09 12:00", "2026-13-40T00:00:00+00:00"])
def test_api_session_state_malformed_422(client: TestClient, bad: str):
    r = client.get("/api/v10/dataquality/calendars/FX_CAL_DECLARED_V1/session-state", params={"as_of_utc": bad})
    assert r.status_code == 422


def test_api_session_state_unknown_calendar_404(client: TestClient):
    r = client.get("/api/v10/dataquality/calendars/NOPE/session-state", params={"as_of_utc": "2026-11-09T12:00:00+00:00"})
    assert r.status_code == 404


def test_api_calendar_routes_scoped(client: TestClient):
    paths = client.get("/openapi.json").json()["paths"]
    for p in (
        "/api/v10/dataquality/calendars",
        "/api/v10/dataquality/calendars/{calendar_id}",
        "/api/v10/dataquality/calendars/{calendar_id}/session-state",
    ):
        assert p in paths
    assert all(p.startswith("/api/v10/dataquality/") for p in paths if "/calendar" in p)


def test_series_trustclass_enum_untouched():
    """The calendar-level DECLARED marker is NOT a series TrustClass — the
    exhaustive series taxonomy stays exactly the recorded 7 values."""
    from app.domain.instrument_master import TrustClass

    assert {t.value for t in TrustClass} == {
        "REAL_VERIFIED", "REAL_UNVERIFIED", "DELAYED", "SYNTHETIC",
        "PAPER", "STALE", "MISSING",
    }


# ---------------------------------------------------------------------------
# WAVE-E bridge to the P1 holiday-table contract (market_calendar.py, untouched)
# ---------------------------------------------------------------------------

def test_bridge_materializes_deterministic_table():
    t1 = dc.as_holiday_table(dc.US_CAL, 2026)
    t2 = dc.as_holiday_table(dc.US_CAL, 2026)
    assert t1 == t2  # frozen pydantic value object; identical materialization
    assert t1.version_id == "US_IDX_CAL_DECLARED_V1.2026-11-05.v1.year-2026"
    assert t1.declared_by.startswith("repository (DECLARED")
    assert len(t1.entries) == 4  # four fixed-date rules


def test_bridge_range_rule_expands_and_validates():
    from datetime import date as _date

    from app.domain.market_calendar import is_trading_day

    table = dc.as_holiday_table(dc.IRAN_CAL, 2026)
    # Nowruz range Mar20+12d -> 12 distinct entries; singles -> 3 more
    assert len(table.entries) == 12 + 3
    # duplicate-date validator held (construction succeeded)
    verdict = is_trading_day(_date(2026, 3, 25), table)
    assert verdict.verdict == "HOLIDAY"
    assert verdict.holiday_name is not None and "Nowruz" in verdict.holiday_name
    assert verdict.table_version_id == table.version_id


def test_bridge_no_table_still_unclassified_fail_closed():
    """The P1 fail-closed semantics are untouched: without a table the holiday
    status remains UNREPRESENTABLE (the declared tables are opt-in inputs)."""
    from datetime import date as _date

    from app.domain.market_calendar import is_trading_day

    verdict = is_trading_day(_date(2026, 3, 25), None)
    assert verdict.verdict == "TRADING_DAY_UNCLASSIFIED"


def test_bridge_non_holiday_weekday_verdict():
    from datetime import date as _date

    from app.domain.market_calendar import is_trading_day

    table = dc.as_holiday_table(dc.US_CAL, 2026)
    verdict = is_trading_day(_date(2026, 11, 9), table)  # Monday, no rule hit
    assert verdict.verdict == "TRADING_DAY"
    assert verdict.holiday_name is None


def test_p1_contract_module_untouched_by_this_wave():
    """The committed P1 contract (market_calendar.py) is intact: its public
    surface still exists and the DECLARED layer imports it, never replaces it."""
    from app.domain import market_calendar as p1

    for name in ("MarketHolidayTable", "HolidayEntry", "is_trading_day", "load_holiday_table", "validate_holiday_table"):
        assert hasattr(p1, name)
