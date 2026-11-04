"""Tests for app.domain.instrument_master (MASTER-RADAR directive Wave 2, §A1/§G).

Offline, deterministic, fail-closed: trust cross-checks, forex metadata
completeness, US cash-index vs ETF-proxy distinction, pseudo-symbol/unsourced
rejection, US individual-equity exclusion with exact reason codes, half-open
membership as-of resolution, and fixture universes passing the register gate.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.data.fixture_universes import (
    FIXTURE_UNIVERSE_VERSION,
    all_fixture_records,
    excluded_us_equity_fixture_records,
    fixture_universe,
    forex_fixture_records,
    iran_fixture_records,
    us_index_fixture_records,
)
from app.domain.instrument_master import (
    DEFAULT_UNIVERSE_MARKETS,
    EntitlementStatus,
    InstrumentRecord,
    InstrumentStatus,
    InstrumentType,
    Market,
    MembershipInterval,
    TrustClass,
    UniverseSpec,
    build_default_universe,
    membership_status_as_of,
    register_instrument,
)

_UTC = timezone.utc
_DECLARED_AT = datetime(2026, 1, 1, tzinfo=_UTC)


def _base_record(**overrides: object) -> InstrumentRecord:
    kwargs: dict = {
        "instrument_id": "IR_TSE:FOLAD",
        "market": Market.IRAN_TSE,
        "symbol": "FOLAD",
        "name_en": "Foolad (test)",
        "name_fa": "فولاد",
        "instrument_type": InstrumentType.COMMON_STOCK,
        "currency": "IRR",
        "timezone": "Asia/Tehran",
        "calendar_id": "TSE_CAL_UNDECLARED",
        "source_identity": "TSETMC",
        "status": InstrumentStatus.ACTIVE,
    }
    kwargs.update(overrides)
    return InstrumentRecord(**kwargs)


def _us_spec() -> UniverseSpec:
    return UniverseSpec(
        spec_id="test-us",
        declared_at_utc=_DECLARED_AT,
        markets={Market.US_INDEX},
        include_statuses={InstrumentStatus.ACTIVE},
    )


# ---------------------------------------------------------------- enum values


def test_trust_class_exact_values() -> None:
    assert [e.value for e in TrustClass] == [
        "REAL_VERIFIED",
        "REAL_UNVERIFIED",
        "DELAYED",
        "SYNTHETIC",
        "PAPER",
        "STALE",
        "MISSING",
    ]


def test_market_exact_values() -> None:
    assert [e.value for e in Market] == [
        "IRAN_TSE",
        "IRAN_IFB",
        "FOREX",
        "US_INDEX",
        "EXCLUDED_US_EQUITY",
    ]


def test_instrument_type_exact_values() -> None:
    assert [e.value for e in InstrumentType] == [
        "COMMON_STOCK",
        "CASH_INDEX",
        "ETF",
        "FUTURE",
        "CFD",
        "CURRENCY_PAIR",
        "UNCLASSIFIED",
    ]


def test_status_and_entitlement_exact_values() -> None:
    assert [e.value for e in InstrumentStatus] == [
        "ACTIVE",
        "SUSPENDED",
        "DELISTED",
        "UNKNOWN",
    ]
    assert [e.value for e in EntitlementStatus] == [
        "ENTITLED_VERIFIED",
        "NOT_ENTITLED",
        "UNKNOWN",
    ]


# ------------------------------------------------------------ construction


def test_valid_minimal_record_defaults() -> None:
    rec = _base_record()
    assert rec.trust_class is TrustClass.MISSING
    assert rec.entitlement is EntitlementStatus.UNKNOWN
    assert rec.aliases == []
    assert rec.membership == []
    assert rec.base_currency is None and rec.quote_currency is None


def test_instrument_id_pattern_rejects_bad_forms() -> None:
    with pytest.raises(ValidationError):
        _base_record(instrument_id="ir_tse:folad")  # lowercase
    with pytest.raises(ValidationError):
        _base_record(instrument_id="FOLAD")  # no market prefix
    with pytest.raises(ValidationError):
        _base_record(instrument_id="IR_TSE:")  # empty suffix


def test_last_updated_utc_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        _base_record(last_updated_utc=datetime(2026, 1, 1))  # naive
    rec = _base_record(last_updated_utc=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert rec.last_updated_utc is not None and rec.last_updated_utc.tzinfo is not None


def test_record_is_frozen() -> None:
    rec = _base_record()
    with pytest.raises(ValidationError):
        rec.symbol = "OTHER"


# ------------------------------------------------- fail-closed trust checks


def test_real_verified_without_entitlement_raises() -> None:
    with pytest.raises(ValidationError, match="real_verified_requires"):
        _base_record(trust_class=TrustClass.REAL_VERIFIED)


def test_real_verified_with_entitlement_and_declared_source_ok() -> None:
    rec = _base_record(
        trust_class=TrustClass.REAL_VERIFIED,
        entitlement=EntitlementStatus.ENTITLED_VERIFIED,
        source_identity="TSETMC",
    )
    assert rec.trust_class is TrustClass.REAL_VERIFIED


def test_real_verified_with_synthetic_source_raises() -> None:
    with pytest.raises(ValidationError, match="real_verified_requires"):
        _base_record(
            trust_class=TrustClass.REAL_VERIFIED,
            entitlement=EntitlementStatus.ENTITLED_VERIFIED,
            source_identity="SYNTHETIC_FIXTURE",
        )


# ------------------------------------------------------------ forex checks


def _forex(**overrides: object) -> InstrumentRecord:
    kwargs: dict = {
        "instrument_id": "FX:EURUSD",
        "market": Market.FOREX,
        "symbol": "EURUSD",
        "instrument_type": InstrumentType.CURRENCY_PAIR,
        "currency": "USD",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "pip_precision": 4,
        "contract_size": 100000.0,
        "timezone": "UTC",
        "calendar_id": "FX_CAL_UNDECLARED",
        "source_identity": "SYNTHETIC_FIXTURE",
        "status": InstrumentStatus.ACTIVE,
    }
    kwargs.update(overrides)
    return InstrumentRecord(**kwargs)


def test_forex_complete_metadata_ok() -> None:
    rec = _forex()
    assert rec.pip_precision == 4
    assert rec.contract_size == 100000.0


@pytest.mark.parametrize("missing_field", ["base_currency", "quote_currency", "pip_precision", "contract_size"])
def test_forex_missing_any_metadata_raises(missing_field: str) -> None:
    kwargs = {missing_field: None}
    with pytest.raises(ValidationError, match="forex_requires"):
        _forex(**kwargs)


def test_base_quote_forbidden_outside_forex() -> None:
    with pytest.raises(ValidationError, match="base_quote_currencies_only_allowed"):
        _base_record(base_currency="EUR", quote_currency="USD")


# ------------------------------------------------- US index / proxy checks


def _us_index(**overrides: object) -> InstrumentRecord:
    kwargs: dict = {
        "instrument_id": "USIDX:SPX",
        "market": Market.US_INDEX,
        "symbol": "SPX",
        "instrument_type": InstrumentType.CASH_INDEX,
        "currency": "USD",
        "timezone": "America/New_York",
        "calendar_id": "US_CAL_UNDECLARED",
        "source_identity": "SYNTHETIC_FIXTURE",
        "status": InstrumentStatus.ACTIVE,
        "is_index_benchmark": True,
        "proxy_kind": "NONE",
    }
    kwargs.update(overrides)
    return InstrumentRecord(**kwargs)


def test_us_index_cash_benchmark_ok() -> None:
    rec = _us_index()
    assert rec.is_index_benchmark is True
    assert rec.proxy_kind == "NONE"


def test_us_index_type_must_be_cash_or_etf() -> None:
    with pytest.raises(ValidationError, match="us_index_instrument_type_must_be"):
        _us_index(instrument_type=InstrumentType.COMMON_STOCK)


def test_us_index_cash_without_benchmark_flag_raises() -> None:
    with pytest.raises(ValidationError, match="us_index_cash_instrument_requires"):
        _us_index(is_index_benchmark=False)


def test_us_index_etf_proxy_ok() -> None:
    rec = _us_index(
        instrument_id="USIDX:SPY",
        symbol="SPY",
        instrument_type=InstrumentType.ETF,
        is_index_benchmark=False,
        proxy_kind="ETF",
    )
    assert rec.proxy_kind == "ETF" and rec.is_index_benchmark is False


def test_us_index_etf_marked_as_benchmark_raises() -> None:
    with pytest.raises(ValidationError, match="us_index_etf_requires"):
        _us_index(
            instrument_type=InstrumentType.ETF,
            is_index_benchmark=True,
            proxy_kind="ETF",
        )


def test_us_index_etf_with_wrong_proxy_kind_raises() -> None:
    with pytest.raises(ValidationError, match="us_index_etf_requires"):
        _us_index(instrument_type=InstrumentType.ETF, is_index_benchmark=False, proxy_kind="CASH")


# --------------------------------------------------------- membership logic


def test_membership_interval_rejects_from_gte_to() -> None:
    with pytest.raises(ValidationError, match="from_lt_to"):
        MembershipInterval(
            symbol_id="IR_TSE:X",
            status=InstrumentStatus.ACTIVE,
            effective_from=date(2020, 1, 2),
            effective_to=date(2020, 1, 2),
        )
    with pytest.raises(ValidationError, match="from_lt_to"):
        MembershipInterval(
            symbol_id="IR_TSE:X",
            status=InstrumentStatus.ACTIVE,
            effective_from=date(2020, 1, 3),
            effective_to=date(2020, 1, 2),
        )


def test_membership_as_of_half_open_boundaries() -> None:
    rec = _base_record(
        status=InstrumentStatus.DELISTED,
        membership=[
            MembershipInterval(
                symbol_id="IR_TSE:FOLAD",
                status=InstrumentStatus.ACTIVE,
                effective_from=date(2012, 5, 6),
                effective_to=date(2023, 8, 20),
            ),
            MembershipInterval(
                symbol_id="IR_TSE:FOLAD",
                status=InstrumentStatus.DELISTED,
                effective_from=date(2023, 8, 20),
                effective_to=None,
            ),
        ],
    )
    # from boundary is INCLUSIVE
    assert membership_status_as_of(rec, date(2012, 5, 6)) is InstrumentStatus.ACTIVE
    # to boundary is EXCLUSIVE (half-open [from, to))
    assert membership_status_as_of(rec, date(2023, 8, 20)) is InstrumentStatus.DELISTED
    assert membership_status_as_of(rec, date(2023, 8, 19)) is InstrumentStatus.ACTIVE
    # before any interval -> honestly None, never guessed
    assert membership_status_as_of(rec, date(2012, 5, 5)) is None


def test_membership_empty_falls_back_to_current_status() -> None:
    rec = _base_record(status=InstrumentStatus.SUSPENDED)
    assert membership_status_as_of(rec, date(2020, 1, 1)) is InstrumentStatus.SUSPENDED


def test_membership_open_start_interval_covers_early_dates() -> None:
    rec = _base_record(
        status=InstrumentStatus.UNKNOWN,
        membership=[
            MembershipInterval(
                symbol_id="IR_TSE:FOLAD",
                status=InstrumentStatus.ACTIVE,
                effective_from=None,
                effective_to=date(2020, 1, 1),
            )
        ],
    )
    assert membership_status_as_of(rec, date(1999, 1, 1)) is InstrumentStatus.ACTIVE
    assert membership_status_as_of(rec, date(2020, 1, 1)) is None


# ------------------------------------------------------- registration gate


def test_register_rejects_undeclared_source_with_pseudo_code() -> None:
    rec = _base_record(source_identity="UNDECLARED")
    with pytest.raises(ValueError, match="pseudo_or_unsourced_symbol"):
        register_instrument(rec, [])


@pytest.mark.parametrize("src", ["UNSOURCED", "UNKNOWN", "NONE"])
def test_register_rejects_unsourced_sentinels(src: str) -> None:
    rec = _base_record(source_identity=src)
    with pytest.raises(ValueError, match="pseudo_or_unsourced_symbol"):
        register_instrument(rec, [])


def test_register_rejects_empty_source_identity() -> None:
    # An empty source cannot pass construction (min_length=1); model_copy
    # bypasses validation, so the gate itself must still refuse it.
    rec = _base_record().model_copy(update={"source_identity": ""})
    with pytest.raises(ValueError, match="pseudo_or_unsourced_symbol"):
        register_instrument(rec, [])


def test_register_fabricated_pattern_without_source_rejected() -> None:
    # "ABCD12" matches the ^[A-Z]{4,6}\d{0,2}$ fabricated pattern; with no
    # declared source it is refused under the same pseudo-symbol code.
    rec = _base_record(instrument_id="IR_TSE:ABCD12", symbol="ABCD12", source_identity="UNDECLARED")
    with pytest.raises(ValueError, match="pseudo_or_unsourced_symbol"):
        register_instrument(rec, [])


def test_register_rejects_duplicate_id() -> None:
    rec = _base_record()
    assert register_instrument(rec, []) == "IR_TSE:FOLAD"
    with pytest.raises(ValueError, match="duplicate_instrument_id"):
        register_instrument(rec, ["IR_TSE:FOLAD"])


def test_register_accepts_declared_fixture_source() -> None:
    rec = _base_record(source_identity="SYNTHETIC_FIXTURE")
    assert register_instrument(rec, set()) == "IR_TSE:FOLAD"


# ----------------------------------------------------------- universe spec


def test_default_spec_markets_never_include_marker_market() -> None:
    assert Market.EXCLUDED_US_EQUITY not in DEFAULT_UNIVERSE_MARKETS
    spec = UniverseSpec(spec_id="s", declared_at_utc=_DECLARED_AT)
    assert Market.EXCLUDED_US_EQUITY not in spec.markets


def test_spec_rejects_marker_market_explicitly() -> None:
    with pytest.raises(ValidationError, match="excluded_marker_market_not_selectable"):
        UniverseSpec(
            spec_id="s",
            declared_at_utc=_DECLARED_AT,
            markets={Market.IRAN_TSE, Market.EXCLUDED_US_EQUITY},
        )


def test_spec_exclusion_flag_is_non_overridable() -> None:
    with pytest.raises(ValidationError, match="non_overridable"):
        UniverseSpec(spec_id="s", declared_at_utc=_DECLARED_AT, exclude_individual_us_equities=False)


def test_spec_requires_timezone_aware_declared_at() -> None:
    with pytest.raises(ValidationError):
        UniverseSpec(spec_id="s", declared_at_utc=datetime(2026, 1, 1))  # naive


# ---------------------------------------------------- universe resolution


def test_build_default_universe_excludes_us_equity_with_exact_reason() -> None:
    aapl = _base_record(
        instrument_id="USEQ:AAPL",
        symbol="AAPL",
        market=Market.EXCLUDED_US_EQUITY,
        source_identity="SYNTHETIC_FIXTURE",
    )
    # The marker market is unselectable in a spec, so the default fixture
    # universe is the resolution context for exclusion demonstrations.
    res = build_default_universe([aapl], fixture_universe())
    assert res.included == []
    assert res.excluded == [("USEQ:AAPL", "US_INDIVIDUAL_EQUITY_EXCLUDED")]


def test_build_default_universe_market_filter_reason() -> None:
    rec = _base_record()
    spec = UniverseSpec(spec_id="s", declared_at_utc=_DECLARED_AT, markets={Market.FOREX})
    res = build_default_universe([rec], spec)
    assert res.excluded == [("IR_TSE:FOLAD", "MARKET_NOT_IN_SPEC")]


def test_build_default_universe_status_filter_reason() -> None:
    rec = _base_record(status=InstrumentStatus.DELISTED)
    spec = UniverseSpec(
        spec_id="s",
        declared_at_utc=_DECLARED_AT,
        include_statuses={InstrumentStatus.ACTIVE},
    )
    res = build_default_universe([rec], spec)
    assert res.excluded == [("IR_TSE:FOLAD", "STATUS_NOT_INCLUDED")]


def test_build_default_universe_type_filter_reason() -> None:
    rec = _base_record(instrument_type=InstrumentType.COMMON_STOCK)
    spec = UniverseSpec(
        spec_id="s",
        declared_at_utc=_DECLARED_AT,
        instrument_types_allowed={InstrumentType.ETF},
    )
    res = build_default_universe([rec], spec)
    assert res.excluded == [("IR_TSE:FOLAD", "TYPE_NOT_ALLOWED")]


def test_build_default_universe_includes_active_iran_record() -> None:
    rec = _base_record()
    res = build_default_universe([rec], fixture_universe())
    assert [r.instrument_id for r in res.included] == ["IR_TSE:FOLAD"]
    assert res.excluded == []
    assert res.considered == 1


def test_build_default_universe_aborts_on_unsourced_record() -> None:
    bad = _base_record(source_identity="UNDECLARED")
    with pytest.raises(ValueError, match="pseudo_or_unsourced_symbol"):
        build_default_universe([bad], fixture_universe())


def test_us_equity_exclusion_takes_precedence_over_market_filter() -> None:
    # Marker market is never in spec.markets; the honest reported reason is
    # the explicit US-equity exclusion, not the generic market filter.
    msni = _base_record(
        instrument_id="USEQ:MSNI",
        symbol="MSNI",
        market=Market.EXCLUDED_US_EQUITY,
        source_identity="SYNTHETIC_FIXTURE",
    )
    spec = UniverseSpec(spec_id="s", declared_at_utc=_DECLARED_AT, markets={Market.FOREX})
    res = build_default_universe([msni], spec)
    assert res.excluded == [("USEQ:MSNI", "US_INDIVIDUAL_EQUITY_EXCLUDED")]


# -------------------------------------------------------- fixture universes


def test_all_fixture_records_pass_register_gate() -> None:
    records = all_fixture_records()
    seen: set[str] = set()
    for rec in records:
        assert register_instrument(rec, seen) == rec.instrument_id
        seen.add(rec.instrument_id)
    assert len(records) >= 30


def test_fixture_ir_records_declared_synthetic() -> None:
    for rec in iran_fixture_records():
        assert rec.source_identity == "SYNTHETIC_FIXTURE"
        assert rec.trust_class is TrustClass.SYNTHETIC
        assert rec.entitlement is EntitlementStatus.NOT_ENTITLED
        assert rec.currency == "IRR"
        assert rec.timezone == "Asia/Tehran"


def test_fixture_delisted_record_survivorship_membership() -> None:
    delisted = [r for r in iran_fixture_records() if r.status is InstrumentStatus.DELISTED]
    assert len(delisted) == 1
    rec = delisted[0]
    assert membership_status_as_of(rec, date(2020, 1, 1)) is InstrumentStatus.ACTIVE
    assert membership_status_as_of(rec, date(2024, 1, 1)) is InstrumentStatus.DELISTED


def test_fixture_forex_metadata_complete() -> None:
    fx = forex_fixture_records()
    assert len(fx) == 13
    jpy = {r.symbol for r in fx if r.pip_precision == 2}
    assert jpy == {"USDJPY", "EURJPY", "GBPJPY"}
    for rec in fx:
        assert rec.market is Market.FOREX
        assert rec.contract_size == 100000.0
        assert rec.timezone == "UTC"
        assert rec.trading_sessions == ["Sydney", "Tokyo", "London", "NewYork"]


def test_fixture_us_index_proxy_distinction() -> None:
    us = us_index_fixture_records()
    spx = [r for r in us if r.symbol == "SPX"][0]
    spy = [r for r in us if r.symbol == "SPY"][0]
    assert spx.instrument_type is InstrumentType.CASH_INDEX and spx.is_index_benchmark
    assert spy.instrument_type is InstrumentType.ETF and not spy.is_index_benchmark
    assert spy.proxy_kind == "ETF"
    assert len([r for r in us if r.instrument_type is InstrumentType.CASH_INDEX]) == 6


def test_fixture_excluded_equities_have_marker_market() -> None:
    eqs = excluded_us_equity_fixture_records()
    assert {r.market for r in eqs} == {Market.EXCLUDED_US_EQUITY}
    assert {r.instrument_type for r in eqs} == {InstrumentType.COMMON_STOCK}


def test_fixture_universe_spec_shape() -> None:
    spec = fixture_universe()
    assert spec.spec_id.endswith(FIXTURE_UNIVERSE_VERSION)
    assert spec.markets == {Market.IRAN_TSE, Market.IRAN_IFB, Market.FOREX, Market.US_INDEX}
    assert spec.exclude_individual_us_equities is True
    assert InstrumentStatus.DELISTED in spec.include_statuses


def test_fixture_universe_resolves_full_fixture_set() -> None:
    res = build_default_universe(all_fixture_records(), fixture_universe())
    ids = {r.instrument_id for r in res.included}
    assert "IR_TSE:DELISTED1" in ids  # delisted included (survivorship)
    assert "FX:EURUSD" in ids and "USIDX:SPY" in ids
    assert {i for i, _ in res.excluded} == {"USEQ:AAPL", "USEQ:MSNI"}
    assert res.considered == len(all_fixture_records())


# ---------------------------------------------------------------------------
# Hardened model_copy (AUDIT-MR1 closure): the non-overridable exclusion
# invariants must hold on COPIES too, not only on construction.
# ---------------------------------------------------------------------------


def _mini_spec() -> "object":
    from datetime import datetime, timezone

    return UniverseSpec(
        spec_id="mini",
        declared_at_utc=datetime(2026, 11, 4, tzinfo=timezone.utc),
    )


def test_model_copy_plain_copy_keeps_invariants_and_passes() -> None:
    spec = _mini_spec()
    clone = spec.model_copy()
    assert clone.exclude_individual_us_equities is True
    assert Market.EXCLUDED_US_EQUITY not in clone.markets


def test_model_copy_cannot_flip_exclusion_flag() -> None:
    import pytest as _pytest

    spec = _mini_spec()
    with _pytest.raises(ValueError, match="exclude_individual_us_equities_is_non_overridable"):
        spec.model_copy(update={"exclude_individual_us_equities": False})


def test_model_copy_cannot_inject_marker_market() -> None:
    import pytest as _pytest

    spec = _mini_spec()
    with _pytest.raises(ValueError, match="excluded_marker_market_not_selectable_in_universe_spec"):
        spec.model_copy(update={"markets": {Market.EXCLUDED_US_EQUITY}})
