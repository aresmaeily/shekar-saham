"""P2 corporate-actions arithmetic — hand-derived expectation tests.

Every expected value below is derived BY HAND from the committed formulas
(documented in ``app/domain/corporate_actions.py``), never copied from an
engine run. Arithmetic shown in comments. Offline, deterministic, no
wall-clock (all dates explicit), no network.

Boundary/window conventions pinned here:
- The price factor maps a PRE-event price to the POST-event scale
  (``adjusted = raw * factor``).
- ``adjust_price``/``adjust_volume``/``apply_event_*`` require events
  strictly ascending by ex-date and only events whose ex-date is STRICTLY
  AFTER the price date; anything else is refused (fail-closed), never
  silently skipped.
- PIT: applicable iff query_date >= ex_date AND public by query_date;
  unknown announce_date is the honest APPLICABLE_ANNOUNCE_UNKNOWN, never
  an invented publication date.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.domain.corporate_actions import (
    CORPORATE_ACTION_TYPES,
    ComposedAdjustment,
    CorporateAction,
    CorporateActionError,
    PitApplicability,
    adjust_price,
    adjust_volume,
    apply_event_price_factor,
    apply_event_volume_factor,
    compose_adjustments,
    event_price_factor,
    event_volume_factor,
    pit_applicability,
    require_pit_usable,
)

EX_CASH = date(2026, 3, 1)
EX_SPLIT = date(2026, 6, 1)
EX_BONUS = date(2026, 9, 1)


def _cash_dividend(
    dividend: float = 500.0, base: float = 10000.0, symbol: str = "فولاد"
) -> CorporateAction:
    return CorporateAction(
        symbol_id=symbol,
        event_type="CASH_DIVIDEND",
        ex_date=EX_CASH,
        announce_date=date(2026, 2, 20),
        dividend_per_share=dividend,
        base_price=base,
    )


def _split(ratio: float = 2.0, symbol: str = "فولاد") -> CorporateAction:
    return CorporateAction(
        symbol_id=symbol,
        event_type="SPLIT",
        ex_date=EX_SPLIT,
        announce_date=date(2026, 5, 10),
        new_per_old=ratio,
    )


def _bonus(percent: float = 25.0, symbol: str = "فولاد") -> CorporateAction:
    return CorporateAction(
        symbol_id=symbol,
        event_type="STOCK_DIVIDEND",
        ex_date=EX_BONUS,
        announce_date=None,  # honest unknown publication time
        percent=percent,
    )


# ---------------------------------------------------------------------------
# Closed taxonomy
# ---------------------------------------------------------------------------


def test_taxonomy_is_closed_six_iranian_market_members() -> None:
    assert CORPORATE_ACTION_TYPES == (
        "CASH_DIVIDEND",
        "STOCK_DIVIDEND",
        "SPLIT",
        "REVERSE_SPLIT",
        "CAPITAL_RAISE",
        "CAPITAL_REDUCTION",
    )
    # every member of the tuple is constructible (taxonomy is live, not decorative)
    for event_type, terms in (
        ("CASH_DIVIDEND", {"dividend_per_share": 1.0, "base_price": 2.0}),
        ("STOCK_DIVIDEND", {"percent": 1.0}),
        ("SPLIT", {"new_per_old": 2.0}),
        ("REVERSE_SPLIT", {"old_per_new": 2.0}),
        (
            "CAPITAL_RAISE",
            {"raise_new_per_old": 1.0, "issue_price": 0.0, "base_price": 1.0},
        ),
        (
            "CAPITAL_REDUCTION",
            {"cancelled_per_held": 0.5, "cash_per_cancelled": 0.0, "base_price": 1.0},
        ),
    ):
        action = CorporateAction(
            symbol_id="س", event_type=event_type, ex_date=date(2026, 1, 1), **terms
        )
        assert action.event_type == event_type
    # MERGER is outside the closed taxonomy — refused with a stable tag,
    # never coerced into a "closest" event type.
    with pytest.raises(ValidationError, match="unknown_corporate_action_type"):
        CorporateAction(
            symbol_id="فولاد",
            event_type="MERGER",  # type: ignore[arg-type]
            ex_date=date(2026, 1, 1),
            new_per_old=2.0,
        )


# ---------------------------------------------------------------------------
# Factor arithmetic — hand-computed cases
# ---------------------------------------------------------------------------


def test_split_factor_two_for_one_hand_derived() -> None:
    # 2:1 split (2 new shares per old share): the post-event price scale is
    # HALF the pre-event scale → price_factor = 1/2 = 0.5; share count doubles
    # → volume_factor = 2.0. A pre-split 10000 price becomes 5000; a
    # pre-split 1,000,000 volume becomes 2,000,000 in post-event terms.
    event = _split(ratio=2.0)
    assert event_price_factor(event) == 0.5
    assert event_volume_factor(event) == 2.0
    assert apply_event_price_factor(event, 10000.0, date(2026, 5, 31)) == 5000.0
    assert (
        apply_event_volume_factor(event, 1_000_000.0, date(2026, 5, 31))
        == 2_000_000.0
    )


def test_reverse_split_factor_ten_to_one_hand_derived() -> None:
    # 10 old shares merged into 1 (تجمیع): post-event price scale is 10× the
    # pre-event scale → price_factor = 10.0; share count shrinks by 10 →
    # volume_factor = 1/10 = 0.1.
    event = CorporateAction(
        symbol_id="فولاد",
        event_type="REVERSE_SPLIT",
        ex_date=date(2026, 6, 1),
        old_per_new=10.0,
    )
    assert event_price_factor(event) == 10.0
    assert event_volume_factor(event) == 0.1
    assert apply_event_price_factor(event, 1000.0, date(2026, 5, 1)) == 10000.0


def test_cash_dividend_factor_hand_derived() -> None:
    # 500 IRR cash dividend on a 10000 IRR pre-event close:
    #   ex-price = 10000 - 500 = 9500
    #   price_factor = 9500 / 10000 = 0.95
    # Volume unchanged (share count untouched) → 1.0.
    event = _cash_dividend(dividend=500.0, base=10000.0)
    assert event_price_factor(event) == 0.95
    assert event_volume_factor(event) == 1.0
    # Pre-event 10000 price back-adjusted → 9500 (hand: 10000 × 0.95).
    assert apply_event_price_factor(event, 10000.0, date(2026, 2, 28)) == pytest.approx(
        9500.0
    )


def test_stock_dividend_factor_hand_derived() -> None:
    # 25% bonus issue (سهام جایزه): holders get 0.25 new shares per held
    # share → new_per_old = 1 + 25/100 = 1.25
    #   price_factor = 1 / 1.25 = 0.8 ; volume_factor = 1.25
    # Pre-event 1000 price → 800; the price drop funds the new shares.
    event = _bonus(percent=25.0)
    assert event_price_factor(event) == pytest.approx(0.8)
    assert event_volume_factor(event) == 1.25
    assert apply_event_price_factor(event, 1000.0, date(2026, 8, 31)) == pytest.approx(
        800.0
    )


def test_capital_raise_factor_hand_derived() -> None:
    # افزایش سرمایه از آورده: 0.25 new shares per held share at a 4000 IRR
    # subscription price, pre-event close 10000:
    #   ex-price = (10000 + 0.25×4000) / (1 + 0.25) = 11000 / 1.25 = 8800
    #   price_factor = 8800 / 10000 = 0.88 ; volume_factor = 1.25
    event = CorporateAction(
        symbol_id="فولاد",
        event_type="CAPITAL_RAISE",
        ex_date=date(2026, 4, 1),
        raise_new_per_old=0.25,
        issue_price=4000.0,
        base_price=10000.0,
    )
    assert event_price_factor(event) == pytest.approx(0.88)
    assert event_volume_factor(event) == 1.25
    # Subscription at market (issue price == base) → NO dilution adjustment:
    # factor = (P + f·P) / ((1+f)·P) = 1.
    at_market = CorporateAction(
        symbol_id="فولاد",
        event_type="CAPITAL_RAISE",
        ex_date=date(2026, 4, 1),
        raise_new_per_old=1.0,
        issue_price=10000.0,
        base_price=10000.0,
    )
    assert event_price_factor(at_market) == pytest.approx(1.0)


def test_capital_reduction_factor_hand_derived() -> None:
    # کاهش سرمایه: half the shares cancelled (c = 0.5), 2000 IRR cash per
    # cancelled share, pre-event close 10000:
    #   ex-price = (10000 - 0.5×2000) / (1 - 0.5) = 9000 / 0.5 = 18000
    #   price_factor = 18000 / 10000 = 1.8 ; volume_factor = 1 - 0.5 = 0.5
    event = CorporateAction(
        symbol_id="فولاد",
        event_type="CAPITAL_REDUCTION",
        ex_date=date(2026, 4, 1),
        cancelled_per_held=0.5,
        cash_per_cancelled=2000.0,
        base_price=10000.0,
    )
    assert event_price_factor(event) == pytest.approx(1.8)
    assert event_volume_factor(event) == 0.5


# ---------------------------------------------------------------------------
# Term-field closure + per-type range refusals
# ---------------------------------------------------------------------------


def test_term_fields_are_closed_per_type() -> None:
    # required field absent
    with pytest.raises(ValidationError, match="term_field_required:base_price"):
        CorporateAction(
            symbol_id="فولاد",
            event_type="CASH_DIVIDEND",
            ex_date=EX_CASH,
            dividend_per_share=500.0,
        )
    # field foreign to the type present
    with pytest.raises(ValidationError, match="term_field_forbidden:percent"):
        CorporateAction(
            symbol_id="فولاد",
            event_type="SPLIT",
            ex_date=EX_SPLIT,
            new_per_old=2.0,
            percent=20.0,
        )


def test_per_type_range_refusals() -> None:
    # split with ratio <= 1 is a reverse split — refused, taxonomy stays meaningful
    with pytest.raises(ValidationError, match="split_ratio_must_exceed_one"):
        CorporateAction(
            symbol_id="فولاد", event_type="SPLIT", ex_date=EX_SPLIT, new_per_old=1.0
        )
    with pytest.raises(ValidationError, match="reverse_ratio_must_exceed_one"):
        CorporateAction(
            symbol_id="فولاد",
            event_type="REVERSE_SPLIT",
            ex_date=EX_SPLIT,
            old_per_new=0.5,
        )
    # dividend >= base price would make the ex-price <= 0 — unrepresentable
    with pytest.raises(ValidationError, match="dividend_ge_base_price"):
        CorporateAction(
            symbol_id="فولاد",
            event_type="CASH_DIVIDEND",
            ex_date=EX_CASH,
            dividend_per_share=10000.0,
            base_price=10000.0,
        )
    # reduction whose cancelled-value eats the whole price — unrepresentable
    with pytest.raises(ValidationError, match="reduction_value_ge_base_price"):
        CorporateAction(
            symbol_id="فولاد",
            event_type="CAPITAL_REDUCTION",
            ex_date=EX_CASH,
            cancelled_per_held=0.5,
            cash_per_cancelled=20000.0,
            base_price=10000.0,
        )


# ---------------------------------------------------------------------------
# Chronological composition
# ---------------------------------------------------------------------------


def test_compose_three_events_chronologically_hand_derived() -> None:
    # ascending ex-dates: cash dividend (0.95) → split 2:1 (0.5) → 25% bonus (0.8)
    #   price_factor = 0.95 × 0.5 × 0.8 = 0.38
    #   volume_factor = 1.0 × 2.0 × 1.25 = 2.5
    # Sanity walk: a pre-March 10000 price → 9500 → 4750 → 3800 today-scale
    # (10000 × 0.38), and pre-March volume 1000 → 2500 post-event scale.
    composed = compose_adjustments([_cash_dividend(), _split(), _bonus()])
    assert isinstance(composed, ComposedAdjustment)
    assert [e.event_type for e in composed.events] == [
        "CASH_DIVIDEND",
        "SPLIT",
        "STOCK_DIVIDEND",
    ]
    assert composed.price_factor == pytest.approx(0.38)
    assert composed.volume_factor == pytest.approx(2.5)
    assert adjust_price(10000.0, date(2026, 2, 28), [_cash_dividend(), _split(), _bonus()]) == pytest.approx(
        3800.0
    )
    assert adjust_volume(1000.0, date(2026, 2, 28), [_cash_dividend(), _split(), _bonus()]) == pytest.approx(
        2500.0
    )


def test_compose_chronology_refusals_unordered_and_duplicate() -> None:
    # the split (June) handed in BEFORE the cash dividend (March) — refused,
    # the module never re-sorts silently (fail-closed chronology gate)
    with pytest.raises(CorporateActionError) as unordered:
        compose_adjustments([_split(), _cash_dividend()])
    assert unordered.value.reason == "UNORDERED_EX_DATES"
    # two events on the same ex-date: composition order would be ambiguous
    other_cash = CorporateAction(
        symbol_id="فولاد",
        event_type="CASH_DIVIDEND",
        ex_date=EX_SPLIT,
        dividend_per_share=100.0,
        base_price=10000.0,
    )
    with pytest.raises(CorporateActionError) as duplicate:
        compose_adjustments([_split(), other_cash])
    assert duplicate.value.reason == "DUPLICATE_EX_DATE"


def test_compose_refuses_mixed_symbols_and_empty_is_identity() -> None:
    other = _split(symbol="فملی")
    with pytest.raises(CorporateActionError) as err:
        compose_adjustments([_cash_dividend(), other])
    assert err.value.reason == "MIXED_SYMBOL_COMPOSITION"
    # zero events = honest identity, representable and never guessed
    empty = compose_adjustments([])
    assert empty.price_factor == 1.0
    assert empty.volume_factor == 1.0
    assert empty.events == ()


# ---------------------------------------------------------------------------
# Anachronistic-use refusal (post-event factor on an at/after-ex price)
# ---------------------------------------------------------------------------


def test_apply_event_factor_refuses_on_and_after_ex_date() -> None:
    event = _split()
    # ON the ex-date the quoted price is already post-event — applying the
    # factor would double-count the event: refused with the stable tag.
    with pytest.raises(CorporateActionError) as on_ex:
        apply_event_price_factor(event, 10000.0, EX_SPLIT)
    assert on_ex.value.reason == "ANACHRONISTIC_ADJUSTMENT"
    with pytest.raises(CorporateActionError) as after_ex:
        apply_event_volume_factor(event, 1000.0, date(2026, 7, 1))
    assert after_ex.value.reason == "ANACHRONISTIC_ADJUSTMENT"
    # one day BEFORE the ex-date is the legitimate use (hand: 10000 × 0.5)
    assert apply_event_price_factor(event, 10000.0, date(2026, 5, 31)) == 5000.0


def test_adjust_price_refuses_out_of_window_and_unordered_input() -> None:
    # OUT-OF-WINDOW: the March cash dividend is already embedded in any price
    # quoted at/after its ex-date — passing it for such a price is refused.
    with pytest.raises(CorporateActionError) as out_of_window:
        adjust_price(10000.0, EX_CASH, [_cash_dividend()])
    assert out_of_window.value.reason == "ANACHRONISTIC_ADJUSTMENT"
    # unordered input refused even when every event is in-window
    with pytest.raises(CorporateActionError) as unordered:
        adjust_price(10000.0, date(2026, 1, 1), [_split(), _cash_dividend()])
    assert unordered.value.reason == "UNORDERED_EX_DATES"
    # fully pending, ordered events compose for the pre-event price
    assert adjust_price(
        10000.0, date(2026, 1, 1), [_cash_dividend(), _split(), _bonus()]
    ) == pytest.approx(3800.0)
    # no events pending → the raw price passes through untouched
    assert adjust_price(1234.5, date(2026, 1, 1), []) == 1234.5


def test_adjust_volume_hand_derived_with_pending_events_only() -> None:
    # pre-March volume 1000 with all three events pending → 1000 × 2.5 = 2500
    assert adjust_volume(
        1000.0, date(2026, 1, 1), [_cash_dividend(), _split(), _bonus()]
    ) == pytest.approx(2500.0)
    # negative volume refused (stable tag), zero volume is honest zero
    with pytest.raises(CorporateActionError) as neg:
        adjust_volume(-1.0, date(2026, 1, 1), [_split()])
    assert neg.value.reason == "VOLUME_NEGATIVE"
    assert adjust_volume(0.0, date(2026, 1, 1), [_split()]) == 0.0


# ---------------------------------------------------------------------------
# Publish-time PIT discipline
# ---------------------------------------------------------------------------


def test_pit_status_matrix_hand_derived() -> None:
    event = _cash_dividend()  # ex 2026-03-01, announce 2026-02-20
    # 1) before the ex-date: factor not yet in effect
    before = pit_applicability(event, date(2026, 2, 1))
    assert isinstance(before, PitApplicability)
    assert before.status == "BEFORE_EX_DATE" and before.applicable is False
    # 2) on/after ex-date, announcement public: fully usable
    known = pit_applicability(event, date(2026, 3, 1))
    assert known.status == "APPLICABLE_ANNOUNCE_KNOWN" and known.applicable is True
    # 3) on/after ex-date but BEFORE the announcement: publish-time look-ahead
    #    → NOT_YET_PUBLIC (refusal tag)
    late_announce = CorporateAction(
        symbol_id="فولاد",
        event_type="CASH_DIVIDEND",
        ex_date=EX_CASH,
        announce_date=date(2026, 3, 15),
        dividend_per_share=500.0,
        base_price=10000.0,
    )
    not_public = pit_applicability(late_announce, date(2026, 3, 1))
    assert not_public.status == "NOT_YET_PUBLIC" and not_public.applicable is False
    # 4) ex-date reached, announce_date None → honest unknown, applicable
    #    WITHOUT publication evidence (never an invented announce date)
    unknown = pit_applicability(_bonus(), date(2026, 12, 1))
    assert unknown.status == "APPLICABLE_ANNOUNCE_UNKNOWN"
    assert unknown.applicable is True and unknown.announce_date is None


def test_require_pit_usable_refusal_tags_and_usable_paths() -> None:
    late_announce = CorporateAction(
        symbol_id="فولاد",
        event_type="CASH_DIVIDEND",
        ex_date=EX_CASH,
        announce_date=date(2026, 3, 15),
        dividend_per_share=500.0,
        base_price=10000.0,
    )
    with pytest.raises(CorporateActionError) as not_public:
        require_pit_usable(late_announce, date(2026, 3, 1))
    assert not_public.value.reason == "NOT_YET_PUBLIC"
    with pytest.raises(CorporateActionError) as before_ex:
        require_pit_usable(_cash_dividend(), date(2026, 2, 1))
    assert before_ex.value.reason == "BEFORE_EX_DATE"
    # usable paths return the verdict without raising
    assert require_pit_usable(_cash_dividend(), date(2026, 3, 1)).applicable is True
    assert (
        require_pit_usable(_bonus(), date(2026, 9, 1)).status
        == "APPLICABLE_ANNOUNCE_UNKNOWN"
    )


# ---------------------------------------------------------------------------
# Input hygiene (plain dates, finite numerics)
# ---------------------------------------------------------------------------


def test_input_hygiene_plain_date_numeric_refusals() -> None:
    event = _split()
    # a calendar day is not an instant — datetime refused with a stable tag
    with pytest.raises(CorporateActionError, match="PRICE_DATE_MUST_BE_PLAIN_DATE"):
        apply_event_price_factor(event, 100.0, datetime(2026, 5, 31, 12, 0))
    with pytest.raises(CorporateActionError, match="QUERY_DATE_MUST_BE_PLAIN_DATE"):
        pit_applicability(event, datetime(2026, 5, 31, 12, 0))
    with pytest.raises(CorporateActionError, match="PRICE_DATE_MUST_BE_PLAIN_DATE"):
        adjust_price(100.0, datetime(2026, 5, 31, 12, 0), [event])
    # booleans are truth flags, not numbers — refused (survivorship_guard precedent)
    with pytest.raises(CorporateActionError, match="PRICE_NOT_NUMERIC"):
        apply_event_price_factor(event, True, date(2026, 5, 31))
    with pytest.raises(CorporateActionError, match="PRICE_NOT_FINITE"):
        adjust_price(float("nan"), date(2026, 5, 31), [event])
    with pytest.raises(CorporateActionError, match="PRICE_NEGATIVE"):
        adjust_price(-100.0, date(2026, 5, 31), [event])
