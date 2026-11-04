"""Deterministic fixture universes and seeded synthetic bars (declared synthetic).

MASTER-RADAR directive Wave 2 ("deterministic fixture universes"). Honest
scope: EVERY record here is a declared ``SYNTHETIC_FIXTURE`` with
``trust_class=SYNTHETIC`` and ``entitlement=NOT_ENTITLED``. Nothing in this
module is real, verified or live market data; fixture metadata (tick sizes,
lot sizes, listing dates) is plausible-but-synthetic and must never be
presented to users as market truth. The same arguments always produce the
same records/bytes (no RNG, no clock, no I/O — the bar generator is driven by
sha256 digests only).

All fixture records pass the ``register_instrument`` allowlist policy because
``SYNTHETIC_FIXTURE`` is a declared source identity.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from app.domain.instrument_master import (
    EntitlementStatus,
    InstrumentRecord,
    InstrumentStatus,
    InstrumentType,
    Market,
    MembershipInterval,
    TrustClass,
    UniverseSpec,
)

__all__ = [
    "FIXTURE_UNIVERSE_VERSION",
    "FIXTURE_DECLARED_AT_UTC",
    "iran_fixture_records",
    "forex_fixture_records",
    "us_index_fixture_records",
    "excluded_us_equity_fixture_records",
    "all_fixture_records",
    "synthetic_bars",
    "fixture_universe",
]

FIXTURE_UNIVERSE_VERSION = "FU-1.0.0"

# Fixed injection instant for all fixture timestamps (deterministic, no clock).
FIXTURE_DECLARED_AT_UTC = datetime(2026, 1, 1, tzinfo=timezone.utc)

_DEFAULT_BAR_END_TS = 1735689600  # 2025-01-01T00:00:00Z (fixed, deterministic)


def _record(**kwargs: Any) -> InstrumentRecord:
    """Shared fixture defaults: declared synthetic, not entitled, no receipts."""
    kwargs.setdefault("source_identity", "SYNTHETIC_FIXTURE")
    kwargs.setdefault("entitlement", EntitlementStatus.NOT_ENTITLED)
    kwargs.setdefault("trust_class", TrustClass.SYNTHETIC)
    kwargs.setdefault("last_updated_utc", FIXTURE_DECLARED_AT_UTC)
    return InstrumentRecord(**kwargs)


def _iran_equity(
    symbol: str,
    name_en: str,
    name_fa: str,
    *,
    status: InstrumentStatus,
    listing_date: date,
    delisting_date: date | None = None,
    membership: list[MembershipInterval] | None = None,
) -> InstrumentRecord:
    market = Market.IRAN_TSE
    return _record(
        instrument_id=f"IR_TSE:{symbol}",
        market=market,
        symbol=symbol,
        aliases=[name_fa, symbol],
        name_en=name_en,
        name_fa=name_fa,
        instrument_type=InstrumentType.COMMON_STOCK,
        currency="IRR",
        lot_size=1.0,  # 1 share
        tick_size=1.0,  # 1 IRR
        timezone="Asia/Tehran",
        calendar_id="TSE_CAL_UNDECLARED",
        listing_date=listing_date,
        delisting_date=delisting_date,
        status=status,
        coverage_start=listing_date,
        coverage_end=delisting_date,
        membership=membership if membership is not None else [],
    )


def iran_fixture_records() -> list[InstrumentRecord]:
    """~10 declared-synthetic TSE/IFB instruments incl. survivorship examples.

    ``IR_TSE:DELISTED1`` carries the historical membership example: an ACTIVE
    interval up to its delisting date, then an open DELISTED interval — so
    as-of resolution before the delisting date yields ACTIVE (survivorship
    handling is representable, never rewritten in place).
    """
    records = [
        _iran_equity(
            "FOLAD",
            "Foolad Mobarakeh Steel (fixture)",
            "فولاد مبارکهٔ ایران",
            status=InstrumentStatus.ACTIVE,
            listing_date=date(2010, 3, 14),
            membership=[
                MembershipInterval(
                    symbol_id="IR_TSE:FOLAD",
                    status=InstrumentStatus.ACTIVE,
                    effective_from=date(2010, 3, 14),
                    effective_to=None,
                )
            ],
        ),
        _iran_equity(
            "FAMLI",
            "National Iranian Copper Industries (fixture)",
            "ملی صنایع مس ایران",
            status=InstrumentStatus.ACTIVE,
            listing_date=date(2011, 6, 5),
        ),
        _iran_equity(
            "SHPNA",
            "Isfahan Oil Refining (fixture)",
            "پالایش نفت اصفهان",
            status=InstrumentStatus.ACTIVE,
            listing_date=date(2013, 2, 20),
        ),
        _iran_equity(
            "KHODRO",
            "Iran Khodro (fixture)",
            "ایران خودرو",
            status=InstrumentStatus.ACTIVE,
            listing_date=date(2010, 9, 1),
        ),
        _iran_equity(
            "WEBMLT",
            "Bank Mellat (fixture)",
            "بانک ملت",
            status=InstrumentStatus.ACTIVE,
            listing_date=date(2012, 4, 15),
        ),
        _iran_equity(
            "SHAST",
            "Social Security Investment (fixture)",
            "سرمایه‌گذاری تأمین اجتماعی",
            status=InstrumentStatus.ACTIVE,
            listing_date=date(2011, 11, 10),
        ),
        _record(
            instrument_id="IR_IFB:KALA",
            market=Market.IRAN_IFB,
            symbol="KALA",
            aliases=["کاله", "KALA"],
            name_en="Kalleh Dairy (fixture)",
            name_fa="کاله (نماد آزمایشی فرابورس)",
            instrument_type=InstrumentType.COMMON_STOCK,
            currency="IRR",
            lot_size=1.0,
            tick_size=1.0,
            timezone="Asia/Tehran",
            calendar_id="IFB_CAL_UNDECLARED",
            listing_date=date(2014, 7, 8),
            status=InstrumentStatus.ACTIVE,
            coverage_start=date(2014, 7, 8),
        ),
        _record(
            instrument_id="IR_IFB:SHEPA",
            market=Market.IRAN_IFB,
            symbol="SHEPA",
            aliases=["شپا", "SHEPA"],
            name_en="IFB fixture instrument B",
            name_fa="نماد آزمایشی فرابورس ب",
            instrument_type=InstrumentType.COMMON_STOCK,
            currency="IRR",
            lot_size=1.0,
            tick_size=1.0,
            timezone="Asia/Tehran",
            calendar_id="IFB_CAL_UNDECLARED",
            listing_date=date(2015, 1, 25),
            status=InstrumentStatus.ACTIVE,
            coverage_start=date(2015, 1, 25),
        ),
        _iran_equity(
            "SUSPENDED1",
            "Suspended TSE fixture",
            "نماد آزمایشی متوقف‌شده",
            status=InstrumentStatus.SUSPENDED,
            listing_date=date(2013, 2, 10),
            membership=[
                MembershipInterval(
                    symbol_id="IR_TSE:SUSPENDED1",
                    status=InstrumentStatus.ACTIVE,
                    effective_from=date(2013, 2, 10),
                    effective_to=date(2025, 3, 1),
                ),
                MembershipInterval(
                    symbol_id="IR_TSE:SUSPENDED1",
                    status=InstrumentStatus.SUSPENDED,
                    effective_from=date(2025, 3, 1),
                    effective_to=None,
                ),
            ],
        ),
        _iran_equity(
            "DELISTED1",
            "Delisted TSE fixture",
            "نماد آزمایشی حذف‌شده",
            status=InstrumentStatus.DELISTED,
            listing_date=date(2012, 5, 6),
            delisting_date=date(2023, 8, 20),
            membership=[
                MembershipInterval(
                    symbol_id="IR_TSE:DELISTED1",
                    status=InstrumentStatus.ACTIVE,
                    effective_from=date(2012, 5, 6),
                    effective_to=date(2023, 8, 20),
                ),
                MembershipInterval(
                    symbol_id="IR_TSE:DELISTED1",
                    status=InstrumentStatus.DELISTED,
                    effective_from=date(2023, 8, 20),
                    effective_to=None,
                ),
            ],
        ),
    ]
    return records


def forex_fixture_records() -> list[InstrumentRecord]:
    """13 FX pairs (majors/minors/exotics) with full mandatory FX metadata.

    ``pip_precision`` is the number of decimals of one pip (EURUSD pip
    0.0001 -> 4; JPY-quote pip 0.01 -> 2).
    """
    specs: list[tuple[str, str, str, int, str]] = [
        # (symbol, base, quote, pip_precision, english name)
        ("EURUSD", "EUR", "USD", 4, "Euro / US Dollar"),
        ("GBPUSD", "GBP", "USD", 4, "British Pound / US Dollar"),
        ("USDJPY", "USD", "JPY", 2, "US Dollar / Japanese Yen"),
        ("USDCHF", "USD", "CHF", 4, "US Dollar / Swiss Franc"),
        ("AUDUSD", "AUD", "USD", 4, "Australian Dollar / US Dollar"),
        ("USDCAD", "USD", "CAD", 4, "US Dollar / Canadian Dollar"),
        ("NZDUSD", "NZD", "USD", 4, "New Zealand Dollar / US Dollar"),
        ("EURGBP", "EUR", "GBP", 4, "Euro / British Pound"),
        ("EURJPY", "EUR", "JPY", 2, "Euro / Japanese Yen"),
        ("GBPJPY", "GBP", "JPY", 2, "British Pound / Japanese Yen"),
        ("USDTRY", "USD", "TRY", 4, "US Dollar / Turkish Lira"),
        ("USDSEK", "USD", "SEK", 4, "US Dollar / Swedish Krona"),
        ("USDMXN", "USD", "MXN", 4, "US Dollar / Mexican Peso"),
    ]
    sessions = ["Sydney", "Tokyo", "London", "NewYork"]
    records: list[InstrumentRecord] = []
    for symbol, base, quote, pip, name_en in specs:
        records.append(
            _record(
                instrument_id=f"FX:{symbol}",
                market=Market.FOREX,
                symbol=symbol,
                aliases=[f"{base}/{quote}"],
                name_en=name_en,
                name_fa=f"{base} / {quote}",
                instrument_type=InstrumentType.CURRENCY_PAIR,
                currency=quote,
                base_currency=base,
                quote_currency=quote,
                pip_precision=pip,
                contract_size=100000.0,
                lot_size=1.0,
                tick_size=10.0 ** (-pip),
                timezone="UTC",
                calendar_id="FX_CAL_UNDECLARED",
                trading_sessions=list(sessions),
                status=InstrumentStatus.ACTIVE,
            )
        )
    return records


def us_index_fixture_records() -> list[InstrumentRecord]:
    """Six cash index benchmarks plus ONE ETF proxy (SPY) to exercise the
    directive's cash-index-vs-tradable-proxy distinction (never silently
    substituted: benchmark flag vs proxy_kind are validated opposites)."""
    indices: list[tuple[str, str, str]] = [
        ("SPX", "S&P 500 (fixture)", "شاخص اس‌اند‌پی ۵۰۰"),
        ("NDX", "Nasdaq-100 (fixture)", "شاخص نزدک ۱۰۰"),
        ("COMP", "Nasdaq Composite (fixture)", "شاخص ترکیبی نزدک"),
        ("DJI", "Dow Jones Industrial Average (fixture)", "شاخص داوجونز"),
        ("RUT", "Russell 2000 (fixture)", "شاخص راسل ۲۰۰۰"),
        ("RUA", "Russell 1000 (fixture)", "شاخص راسل ۱۰۰۰"),
    ]
    records = [
        _record(
            instrument_id=f"USIDX:{symbol}",
            market=Market.US_INDEX,
            symbol=symbol,
            aliases=[symbol],
            name_en=name_en,
            name_fa=name_fa,
            instrument_type=InstrumentType.CASH_INDEX,
            currency="USD",
            timezone="America/New_York",
            calendar_id="US_CAL_UNDECLARED",
            is_index_benchmark=True,
            proxy_kind="NONE",
            status=InstrumentStatus.ACTIVE,
        )
        for symbol, name_en, name_fa in indices
    ]
    records.append(
        _record(
            instrument_id="USIDX:SPY",
            market=Market.US_INDEX,
            symbol="SPY",
            aliases=["SPY", "SPDR S&P 500 ETF"],
            name_en="SPDR S&P 500 ETF proxy (fixture)",
            name_fa="صندوق قابل معامله اس‌پی‌وای (جایگزین)",
            instrument_type=InstrumentType.ETF,
            currency="USD",
            timezone="America/New_York",
            calendar_id="US_CAL_UNDECLARED",
            is_index_benchmark=False,
            proxy_kind="ETF",
            status=InstrumentStatus.ACTIVE,
        )
    )
    return records


def excluded_us_equity_fixture_records() -> list[InstrumentRecord]:
    """Two individual-US-equity stand-ins on the marker market — these exist
    ONLY to test/exercise the exclusion policy and can never enter a default
    universe (spec guard refuses the marker market outright)."""
    return [
        _record(
            instrument_id="USEQ:AAPL",
            market=Market.EXCLUDED_US_EQUITY,
            symbol="AAPL",
            aliases=["AAPL"],
            name_en="US equity stand-in A (excluded)",
            name_fa="سهام آزمایشی آمریکایی الف (حذف‌شده)",
            instrument_type=InstrumentType.COMMON_STOCK,
            currency="USD",
            timezone="America/New_York",
            calendar_id="US_CAL_UNDECLARED",
            status=InstrumentStatus.ACTIVE,
        ),
        _record(
            instrument_id="USEQ:MSNI",
            market=Market.EXCLUDED_US_EQUITY,
            symbol="MSNI",
            aliases=["MSNI"],
            name_en="US equity stand-in B (excluded)",
            name_fa="سهام آزمایشی آمریکایی ب (حذف‌شده)",
            instrument_type=InstrumentType.COMMON_STOCK,
            currency="USD",
            timezone="America/New_York",
            calendar_id="US_CAL_UNDECLARED",
            status=InstrumentStatus.ACTIVE,
        ),
    ]


def all_fixture_records() -> list[InstrumentRecord]:
    """Every fixture record in one deterministic list (IR, FX, US index, excluded)."""
    return (
        iran_fixture_records()
        + forex_fixture_records()
        + us_index_fixture_records()
        + excluded_us_equity_fixture_records()
    )


def _seeded_values(key: str, count: int) -> list[int]:
    """Small deterministic PRNG built from sha256 digests (NO random module)."""
    values: list[int] = []
    payload = key.encode("utf-8")
    counter = 0
    while len(values) < count:
        digest = hashlib.sha256(payload + b"|" + str(counter).encode("ascii")).digest()
        for offset in range(0, 32, 4):
            values.append(int.from_bytes(digest[offset : offset + 4], "big"))
        counter += 1
    return values[:count]


def synthetic_bars(
    symbol: str,
    timeframe_code: str,
    count: int,
    end_ts: int | None = None,
) -> list[dict[str, float]]:
    """Deterministic seeded OHLCV bars on the timeframe grid.

    Bar ``i`` is fully driven by ``sha256("<symbol>|<timeframe_code>|<i>|<n>")``
    digests; identical arguments produce identical bars across calls (and
    across processes). Prices and volumes are strictly positive and OHLCV
    self-consistent. ``end_ts`` defaults to a FIXED epoch (2025-01-01T00:00Z)
    — never the wall clock.
    """
    from app.domain.timeframe_spec import get_standard_timeframe

    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("count_must_be_non_negative_int")
    tf = get_standard_timeframe(timeframe_code)
    if count == 0:
        return []
    effective_end = _DEFAULT_BAR_END_TS if end_ts is None else int(end_ts)
    last_bucket = effective_end // tf.seconds
    first_bucket = last_bucket - (count - 1)
    bars: list[dict[str, float]] = []
    for i in range(count):
        v = _seeded_values(f"{symbol}|{timeframe_code}|{i}", 6)
        o = 10.0 + (v[0] % 99000) / 1000.0
        c = 10.0 + (v[1] % 99000) / 1000.0
        h = max(o, c) + 0.001 + (v[2] % 500) / 1000.0
        low = min(o, c) - 0.001 - (v[3] % 500) / 1000.0
        volume = float(100 + (v[4] % 100000))
        bars.append(
            {
                "ts": (first_bucket + i) * tf.seconds,
                "o": o,
                "h": h,
                "l": low,
                "c": c,
                "v": volume,
            }
        )
    return bars


def fixture_universe() -> UniverseSpec:
    """Default fixture universe spec: IR + FX + US index, delisted included
    (survivorship honesty), individual US equities excluded (non-overridable)."""
    return UniverseSpec(
        spec_id=f"FIXTURE-UNIVERSE:{FIXTURE_UNIVERSE_VERSION}",
        declared_at_utc=FIXTURE_DECLARED_AT_UTC,
        markets={Market.IRAN_TSE, Market.IRAN_IFB, Market.FOREX, Market.US_INDEX},
        include_statuses={
            InstrumentStatus.ACTIVE,
            InstrumentStatus.DELISTED,
            InstrumentStatus.SUSPENDED,
        },
        instrument_types_allowed=set(InstrumentType),
        exclude_individual_us_equities=True,
    )
