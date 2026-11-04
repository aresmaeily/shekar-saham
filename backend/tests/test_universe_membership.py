"""P2 point-in-time universe membership — hand-derived expectation tests.

Every expectation is derived BY HAND from the committed conventions in
``app/domain/universe_membership.py``:

- Boundary convention (pinned): HALF-OPEN ``[effective_from, effective_to)`` —
  ``effective_from`` is INCLUSIVE, ``effective_to`` is EXCLUSIVE. On the
  listing date the symbol is already IN; on the delist date it is already
  OUT (aligned with survivorship_guard's
  ``listed_from_ts <= t`` / ``delisted_at_ts <= t`` boundaries).
- Composition delegates to survivorship_guard (imported, not copied) with
  ``date.toordinal()`` as the deterministic day-granularity timestamp.
- Fail-closed: absence from the table is UNKNOWN_UNCLASSIFIED, never
  NOT_YET_LISTED; unordered/overlapping input is refused, never repaired.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.domain.universe_membership import (
    MembershipEntry,
    MembershipError,
    MembershipTable,
    members_asof,
    status_asof,
    survivorship_risk_verdict,
)


def _entry(
    symbol: str,
    from_day: date,
    to_day: date | None,
) -> MembershipEntry:
    return MembershipEntry(symbol_id=symbol, effective_from=from_day, effective_to=to_day)


# Canonical order = ascending (effective_from, symbol_id).
def _table() -> MembershipTable:
    return MembershipTable(
        entries=(
            _entry("فولاد", date(2020, 1, 1), None),            # listed, never delisted
            _entry("وبملت", date(2020, 1, 1), date(2022, 6, 30)),  # delisted 2022-06-30
            _entry("خودرو", date(2023, 1, 1), None),             # listed later
        )
    )


# ---------------------------------------------------------------------------
# Table construction: order + interval integrity
# ---------------------------------------------------------------------------


def test_canonical_order_and_touching_intervals_accepted() -> None:
    # delist→relist pair TOUCHING at 2022-06-30 is valid for half-open intervals:
    # [2020-01-01, 2022-06-30) then [2022-06-30, None) — no overlap.
    table = MembershipTable(
        entries=(
            _entry("وبملت", date(2020, 1, 1), date(2022, 6, 30)),
            _entry("وبملت", date(2022, 6, 30), None),
        )
    )
    assert len(table.entries) == 2
    assert members_asof(table, date(2022, 6, 29)) == ("وبملت",)
    assert members_asof(table, date(2022, 6, 30)) == ("وبملت",)  # second interval
    assert members_asof(table, date(2020, 1, 1)) == ("وبملت",)   # first interval


def test_unordered_entries_refused() -> None:
    # خودرو (2023) handed in BEFORE وبملت (2020) — refused, never re-sorted
    with pytest.raises(ValidationError, match="unordered_membership_entries"):
        MembershipTable(
            entries=(
                _entry("خودرو", date(2023, 1, 1), None),
                _entry("وبملت", date(2020, 1, 1), date(2022, 6, 30)),
            )
        )


def test_overlapping_intervals_refused() -> None:
    # same symbol, second interval starts BEFORE the first one closes
    with pytest.raises(ValidationError, match="overlapping_membership_intervals"):
        MembershipTable(
            entries=(
                _entry("وبملت", date(2020, 1, 1), date(2022, 6, 30)),
                _entry("وبملت", date(2021, 1, 1), None),
            )
        )
    # exact duplicate interval also overlaps (half-open [a,b) ∩ [a,b) ≠ ∅)
    with pytest.raises(ValidationError, match="overlapping_membership_intervals"):
        MembershipTable(
            entries=(
                _entry("وبملت", date(2020, 1, 1), date(2022, 6, 30)),
                _entry("وبملت", date(2020, 1, 1), date(2022, 6, 30)),
            )
        )
    # a prior OPEN-ENDED interval [a, None) overlaps any later same-symbol entry
    with pytest.raises(ValidationError, match="overlapping_membership_intervals"):
        MembershipTable(
            entries=(
                _entry("وبملت", date(2020, 1, 1), None),
                _entry("وبملت", date(2021, 1, 1), None),
            )
        )


def test_invalid_interval_refused() -> None:
    with pytest.raises(ValidationError, match="invalid_membership_interval"):
        _entry("وبملت", date(2022, 6, 30), date(2022, 6, 30))  # empty interval
    with pytest.raises(ValidationError, match="invalid_membership_interval"):
        _entry("وبملت", date(2022, 6, 30), date(2021, 1, 1))  # to before from


# ---------------------------------------------------------------------------
# members_asof: point-in-time member set
# ---------------------------------------------------------------------------


def test_members_asof_empty_table_is_honest_empty() -> None:
    assert members_asof(MembershipTable(entries=()), date(2021, 1, 1)) == ()


def test_members_asof_effective_from_is_inclusive() -> None:
    table = _table()
    # ON the listing date itself the symbol is IN (pinned convention)
    assert members_asof(table, date(2020, 1, 1)) == ("فولاد", "وبملت")
    assert members_asof(table, date(2023, 1, 1)) == ("خودرو", "فولاد")


def test_members_asof_effective_to_is_exclusive() -> None:
    table = _table()
    # the day BEFORE the delist date: still a member
    assert "وبملت" in members_asof(table, date(2022, 6, 29))
    # ON the delist date itself the symbol is OUT (pinned convention;
    # aligned with survivorship_guard's delisted_at_ts <= t boundary)
    assert "وبملت" not in members_asof(table, date(2022, 6, 30))
    assert members_asof(table, date(2022, 6, 30)) == ("فولاد",)


def test_members_asof_mixed_board_hand_derived() -> None:
    table = _table()
    assert members_asof(table, date(2021, 6, 15)) == ("فولاد", "وبملت")
    assert members_asof(table, date(2019, 12, 31)) == ()  # before everything
    # open-ended interval (فولاد, effective_to None) covers late dates forever
    # (sorted order is by Unicode code point: خودرو < فولاد)
    assert members_asof(table, date(2030, 1, 1)) == ("خودرو", "فولاد")


# ---------------------------------------------------------------------------
# status_asof: closed status vocabulary, fail-closed unknowns
# ---------------------------------------------------------------------------


def test_status_matrix_member_not_yet_listed_delisted() -> None:
    table = _table()
    assert status_asof(table, "وبملت", date(2021, 6, 15)) == "MEMBER"
    assert status_asof(table, "وبملت", date(2019, 6, 15)) == "NOT_YET_LISTED"
    # the delist date itself is already DELISTED (effective_to exclusive)
    assert status_asof(table, "وبملت", date(2022, 6, 30)) == "DELISTED"
    assert status_asof(table, "وبملت", date(2023, 1, 1)) == "DELISTED"
    assert status_asof(table, "فولاد", date(2026, 1, 1)) == "MEMBER"  # open-ended


def test_status_unknown_unclassified_interior_gap() -> None:
    # وبملت with a declared delist→relist gap: a query INSIDE the gap is
    # neither honestly MEMBER nor honestly DELISTED-forever nor
    # NOT_YET_LISTED — the fail-closed answer is UNKNOWN_UNCLASSIFIED.
    table = MembershipTable(
        entries=(
            _entry("وبملت", date(2020, 1, 1), date(2021, 6, 30)),
            _entry("وبملت", date(2023, 1, 1), None),
        )
    )
    assert status_asof(table, "وبملت", date(2022, 6, 15)) == "UNKNOWN_UNCLASSIFIED"
    # the boundaries around the gap classify normally
    assert status_asof(table, "وبملت", date(2021, 6, 29)) == "MEMBER"
    assert status_asof(table, "وبملت", date(2023, 1, 1)) == "MEMBER"


def test_status_unknown_unclassified_symbol_absent_or_empty_table() -> None:
    # absence from the table is NOT proof of non-listing — an incomplete
    # table must never manufacture a NOT_YET_LISTED answer (fail-closed)
    table = _table()
    assert status_asof(table, "فملی", date(2021, 6, 15)) == "UNKNOWN_UNCLASSIFIED"
    assert (
        status_asof(MembershipTable(entries=()), "فولاد", date(2021, 6, 15))
        == "UNKNOWN_UNCLASSIFIED"
    )


def test_status_refuses_datetime_instant() -> None:
    # a calendar day is not an instant — datetime refused with a stable tag
    with pytest.raises(MembershipError, match="AS_OF_MUST_BE_PLAIN_DATE"):
        status_asof(_table(), "فولاد", datetime(2021, 6, 15, 12, 0))
    with pytest.raises(MembershipError, match="AS_OF_MUST_BE_PLAIN_DATE"):
        members_asof(_table(), datetime(2021, 6, 15, 12, 0))


# ---------------------------------------------------------------------------
# Composition with survivorship_guard (delegated, vocabulary reused)
# ---------------------------------------------------------------------------


def test_composition_ok_when_pit_universe_fully_used() -> None:
    verdict = survivorship_risk_verdict(
        _table(), date(2021, 6, 15), ["فولاد", "وبملت"]
    )
    assert verdict.verdict == "OK"
    assert verdict.universe_size == 3
    assert verdict.snapshot_size == 2
    assert verdict.excluded_delisted_symbols == ()
    assert verdict.anachronistic_symbols == ()
    assert verdict.missing_symbols == ()


def test_composition_anachronistic_member_takes_precedence() -> None:
    # snapshot includes خودرو (listed 2023) at a 2021 evaluation point —
    # ANACHRONISTIC_MEMBER wins over the missing وبملت (precedence pinned by
    # survivorship_guard: ANACHRONISTIC_MEMBER > INCOMPLETE_UNIVERSE), with
    # BOTH findings visible in the per-category lists.
    verdict = survivorship_risk_verdict(
        _table(), date(2021, 6, 15), ["فولاد", "خودرو"]
    )
    assert verdict.verdict == "ANACHRONISTIC_MEMBER"
    assert verdict.anachronistic_symbols == ("خودرو",)
    assert verdict.missing_symbols == ("وبملت",)


def test_composition_survivorship_bias_risk_when_delisted_excluded() -> None:
    # 2023 evaluation: وبملT delisted 2022-06-30 <= evaluation and ABSENT from
    # the snapshot — the classic silent survivorship filter.
    verdict = survivorship_risk_verdict(
        _table(), date(2023, 6, 1), ["فولاد", "خودرو"]
    )
    assert verdict.verdict == "SURVIVORSHIP_BIAS_RISK"
    assert verdict.excluded_delisted_symbols == ("وبملت",)


def test_composition_incomplete_universe_when_member_missing() -> None:
    # وبملت still listed at the 2021 evaluation point but absent from the
    # snapshot → INCOMPLETE_UNIVERSE (no delist, no anachrony).
    verdict = survivorship_risk_verdict(_table(), date(2021, 6, 15), ["فولاد"])
    assert verdict.verdict == "INCOMPLETE_UNIVERSE"
    assert verdict.missing_symbols == ("وبملت",)


def test_composition_snapshot_as_of_after_evaluation_flagged() -> None:
    # same legitimate member set, but the snapshot claims knowledge from
    # AFTER the evaluation point (e.g., a universe built from today's board
    # used for a 2021 backtest) — the guard flags it via its own
    # SNAPSHOT_AS_OF_AFTER_EVALUATION_AS_OF reason code.
    verdict = survivorship_risk_verdict(
        _table(),
        date(2021, 6, 15),
        ["فولاد", "وبملت"],
        snapshot_as_of=date(2026, 11, 3),
    )
    assert verdict.verdict == "ANACHRONISTIC_MEMBER"
    assert "SNAPSHOT_AS_OF_AFTER_EVALUATION_AS_OF" in verdict.reason_codes


def test_composition_fail_closed_refusals_and_empty_paths() -> None:
    # snapshot symbol the table does not know can never be certified
    with pytest.raises(MembershipError) as unknown_snapshot:
        survivorship_risk_verdict(_table(), date(2021, 6, 15), ["فولاد", "فملی"])
    assert unknown_snapshot.value.reason == "SNAPSHOT_SYMBOL_NOT_IN_TABLE"
    # multi-interval symbols have no single lifecycle to hand the guard
    multi = MembershipTable(
        entries=(
            _entry("وبملت", date(2020, 1, 1), date(2021, 6, 30)),
            _entry("وبملت", date(2022, 1, 1), None),
        )
    )
    with pytest.raises(MembershipError) as multi_err:
        survivorship_risk_verdict(multi, date(2021, 6, 15), ["وبملت"])
    assert multi_err.value.reason == "MULTI_INTERVAL_SYMBOL_NOT_COMPOSABLE"
    # empty table + empty snapshot → OK with sizes 0 (honest, certified)
    verdict = survivorship_risk_verdict(
        MembershipTable(entries=()), date(2021, 6, 15), []
    )
    assert verdict.verdict == "OK"
    assert verdict.universe_size == 0 and verdict.snapshot_size == 0
