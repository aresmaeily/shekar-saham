"""P2 liquidity pinning acceptance tests (hand-derived, deterministic).

Pins the honestly-recorded gap closure: value observations are pinned to their
session (never factor-adjusted), volume comparability reuses the existing
corporate-actions arithmetic with anachronism refusals, publish-time discipline
is honest about unknown publication, and mixed-basis comparisons are refused.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.domain.corporate_actions import CorporateAction
from app.domain.liquidity_pinning import (
    LiquidityObservation,
    LiquidityPinningError,
    liquidity_series_view,
    observation_usability,
    pin_value_observation,
    require_single_basis,
    volume_basis_view,
)

D = dt.date
DT = dt.timezone.utc


def _obs(**kw) -> LiquidityObservation:
    base = dict(
        symbol_id="AAA",
        session_date=D(2026, 11, 10),
        amount=Decimal("1500000000"),
        volume_shares=Decimal("1000000"),
    )
    base.update(kw)
    return LiquidityObservation(**base)


def _split(percent=100.0, ex=D(2026, 11, 12), announce=D(2026, 11, 8)) -> CorporateAction:
    return CorporateAction(
        symbol_id="AAA",
        event_type="STOCK_DIVIDEND",
        ex_date=ex,
        announce_date=announce,
        percent=percent,
    )


# --- value pinning ---------------------------------------------------------------

def test_value_observation_pinned_verbatim():
    rec = pin_value_observation(_obs(), None, D(2026, 11, 10))
    assert rec["amount"] == Decimal("1500000000")
    assert rec["basis"] == "VALUE_OBSERVATION_PINNED"
    assert rec["factor_applied"] is None
    assert rec["unit"] == "toman"


def test_value_observation_refuses_closed_window_factor():
    # event already ex at/before price_date → applying it is refused (fail-closed)
    ev = _split(ex=D(2026, 11, 10))
    with pytest.raises(LiquidityPinningError) as e:
        pin_value_observation(_obs(), ev, D(2026, 11, 10))
    assert e.value.reason_code == "ANACHRONISTIC_ADJUSTMENT"
    with pytest.raises(LiquidityPinningError):
        pin_value_observation(_obs(), ev, D(2026, 11, 15))


def test_value_observation_accepts_pending_event_silently_unadjusted():
    ev = _split(ex=D(2026, 11, 12))
    rec = pin_value_observation(_obs(), ev, D(2026, 11, 10))
    assert rec["amount"] == Decimal("1500000000")  # value never adjusted
    assert rec["factor_applied"] is None


# --- publish-time discipline -------------------------------------------------------

def test_usability_not_yet_observed():
    out = observation_usability(_obs(session_date=D(2026, 11, 20)), dt.datetime(2026, 11, 15, tzinfo=DT))
    assert out["status"] == "NOT_YET_OBSERVED" and out["usable"] is False


def test_usability_not_yet_public():
    out = observation_usability(
        _obs(publication_status="KNOWN", published_at=dt.datetime(2026, 11, 11, 6, tzinfo=DT)),
        dt.datetime(2026, 11, 10, 12, tzinfo=DT),
    )
    assert out["status"] == "NOT_YET_PUBLIC" and out["usable"] is False


def test_usability_publication_unknown_honest():
    out = observation_usability(_obs(), dt.datetime(2026, 11, 15, tzinfo=DT))
    assert out["status"] == "PUBLICATION_UNKNOWN" and out["usable"] is False


def test_usability_usable_when_known_and_before_query():
    out = observation_usability(
        _obs(publication_status="KNOWN", published_at=dt.datetime(2026, 11, 10, 17, tzinfo=DT)),
        dt.datetime(2026, 11, 12, tzinfo=DT),
    )
    assert out["status"] == "USABLE" and out["usable"] is True


def test_naive_query_refused():
    with pytest.raises(LiquidityPinningError) as e:
        observation_usability(_obs(), dt.datetime(2026, 11, 15))
    assert e.value.reason_code == "query_at_must_be_timezone_aware"


def test_publication_invariants_fail_closed():
    with pytest.raises(LiquidityPinningError):
        _obs(publication_status="KNOWN", published_at=None)
    with pytest.raises(LiquidityPinningError):
        _obs(publication_status="UNKNOWN", published_at=dt.datetime(2026, 11, 10, tzinfo=DT))
    with pytest.raises(LiquidityPinningError):
        _obs(amount=Decimal("-1"))


# --- series + volume basis ----------------------------------------------------------

def test_series_view_all_pinned_with_usability():
    view = liquidity_series_view([_obs(), _obs(session_date=D(2026, 11, 11))], dt.datetime(2026, 11, 15, tzinfo=DT))
    assert view["basis"] == "VALUE_OBSERVATION_PINNED"
    assert all(o["basis"] == "VALUE_OBSERVATION_PINNED" for o in view["observations"])
    assert {o["usability"]["status"] for o in view["observations"]} == {"PUBLICATION_UNKNOWN"}


def test_volume_basis_composes_pending_factor_only():
    obs = _obs()
    ev = _split(percent=100.0, ex=D(2026, 11, 12), announce=D(2026, 11, 8))
    view = volume_basis_view([obs], [ev], price_date=D(2026, 11, 10), query_date=D(2026, 11, 15))
    item = view["observations"][0]
    # STOCK_DIVIDEND 100% → volume factor 2.0 (existing corporate-actions arithmetic)
    assert item["composed_factor"] == 2.0
    assert item["volume_shares_comparable"] == Decimal("2000000")
    assert item["basis"] == "VOLUME_ADJUSTED"
    assert item["factor_chain"][0]["pit_status"] == "APPLICABLE_ANNOUNCE_KNOWN"


def test_volume_basis_not_yet_public_chain_records_refusal():
    obs = _obs()
    ev = _split(percent=100.0, ex=D(2026, 11, 12), announce=D(2026, 11, 14))
    # query_date after ex_date but BEFORE announce_date → publish-time refusal
    # (query before ex would report the documented BEFORE_EX_DATE precedence)
    view = volume_basis_view([obs], [ev], price_date=D(2026, 11, 10), query_date=D(2026, 11, 13))
    item = view["observations"][0]
    assert item["composed_factor"] == 1.0  # factor NOT applied (publish-time refusal)
    assert item["factor_chain"][0]["pit_status"] == "NOT_YET_PUBLIC"
    assert item["basis"] == "VOLUME_RAW"


def test_volume_basis_announce_unknown_is_honest():
    obs = _obs()
    ev = _split(percent=100.0, ex=D(2026, 11, 12), announce=None)
    view = volume_basis_view([obs], [ev], price_date=D(2026, 11, 10), query_date=D(2026, 11, 15))
    assert view["observations"][0]["factor_chain"][0]["pit_status"] == "APPLICABLE_ANNOUNCE_UNKNOWN"


def test_volume_basis_before_ex_at_query_not_applied():
    obs = _obs()
    ev = _split(percent=100.0, ex=D(2026, 11, 12), announce=D(2026, 11, 8))
    view = volume_basis_view([obs], [ev], price_date=D(2026, 11, 10), query_date=D(2026, 11, 11))
    item = view["observations"][0]
    assert item["composed_factor"] == 1.0
    assert item["factor_chain"][0]["pit_status"] == "BEFORE_EX_DATE"


def test_volume_basis_refuses_anachronistic_event():
    ev = _split(ex=D(2026, 11, 8))
    with pytest.raises(LiquidityPinningError) as e:
        volume_basis_view([_obs()], [ev], price_date=D(2026, 11, 10), query_date=D(2026, 11, 15))
    assert e.value.reason_code == "ANACHRONISTIC_ADJUSTMENT"


def test_volume_basis_missing_volume_shares_is_none_not_zero():
    view = volume_basis_view([_obs(volume_shares=None)], [], price_date=D(2026, 11, 10), query_date=D(2026, 11, 15))
    assert view["observations"][0]["volume_shares_comparable"] is None
    assert view["observations"][0]["basis"] == "VOLUME_RAW"


# --- basis guard ----------------------------------------------------------------------

def test_mixed_basis_refused():
    records = [
        {"basis": "VALUE_OBSERVATION_PINNED"},
        {"basis": "VOLUME_ADJUSTED"},
    ]
    with pytest.raises(LiquidityPinningError) as e:
        require_single_basis(records)
    assert e.value.reason_code == "MIXED_BASIS"
    with pytest.raises(LiquidityPinningError):
        require_single_basis([])
    assert require_single_basis([{"basis": "VOLUME_RAW"}]) == "VOLUME_RAW"
