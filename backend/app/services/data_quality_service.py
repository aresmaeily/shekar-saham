"""data_quality_service.py — MASTER-RADAR WAVE-2 (2026-11-04) §G glue service.

Bridges the deterministic fixture universes (app.data.fixture_universes) to
the mechanical history auditor and market-coverage builder
(app.engines.universe_data_quality). This module is INTEGRATION GLUE ONLY: it
reuses the public builders of both modules and invents no audit math.

Honesty contract (repeated here because this is the API-facing seam):
- Every instrument here is a declared ``SYNTHETIC_FIXTURE`` record
  (``trust_class=SYNTHETIC``, ``entitlement=NOT_ENTITLED``) resolved through
  the engine ``build_default_universe`` allowlist; the individual-US-equity
  marker market stays EXCLUDED from the default universe (reported with its
  exclusion, never merged silently).
- The as_of/staleness pattern is the engine's INJECTED pattern:
  ``now_ts`` is the fixture universe's fixed declared-at instant
  (2026-01-01T00:00Z) — never a wall clock — so ``stale_bars`` is a
  deterministic, reproducible count relative to that declared as_of.
- Bars come from the fixture seeded generator (sha256-driven; identical
  arguments -> identical bars; no RNG, no clock, no I/O).
- Corporate-action / point-in-time claims are NOT declared by fixtures, so the
  engine's honesty mapping reports UNKNOWN for both (never a guessed claim).
- Canonical non-live provenance note is attached to every output.
- No network, no file IO, no provider calls anywhere in this module.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.data.fixture_universes import (
    FIXTURE_DECLARED_AT_UTC,
    FIXTURE_UNIVERSE_VERSION,
    all_fixture_records,
    fixture_universe,
    synthetic_bars,
)
from app.domain.instrument_master import (
    InstrumentRecord,
    TrustClass,
    build_default_universe,
)
from app.engines.universe_data_quality import (
    UNIVERSE_DQ_VERSION,
    SymbolCoverage,
    audit_symbol_history,
    build_market_coverage,
)

SERVICE_VERSION = "DQ-SVC-1.0.0"

# Documented audit parameters (deterministic; pinned by the WAVE-2 tests).
# NOTE on codes: the timeframe_spec standard table (used by the fixture bar
# generator) spells the daily code "1d"; the chart endpoints' "1D" is a
# separate legacy grid spelling and is NOT a timeframe_spec code.
AUDIT_TIMEFRAME_CODE = "1d"
AUDIT_BAR_COUNT = 200  # documented per-symbol audit depth (fixture seeded bars)
AUDIT_EXPECTED_INTERVAL_SECONDS = 86_400  # the 1D grid the bars are generated on
# Declared staleness policy for fixture history: a bar older than 30 days
# relative to the INJECTED as_of counts as stale (mechanical, reproducible).
AUDIT_MAX_STALENESS_SECONDS = 2_592_000
# The fixture universe's fixed declared-at instant (2026-01-01T00:00Z) — the
# canonical INJECTED as_of for every audit here (never a wall clock).
FIXTURE_AS_OF_TS = int(FIXTURE_DECLARED_AT_UTC.timestamp())

PROVENANCE_NOTE_EN = (
    "Canonical non-live provenance: every instrument and bar in this router is a "
    "declared SYNTHETIC_FIXTURE (app.data.fixture_universes, deterministic "
    "sha256-seeded bars). No network fetch, no provider feed, no wall-clock "
    "dependency; fixture metadata is plausible-but-synthetic and never market truth."
)
PROVENANCE_NOTE_FA = (
    "منشأ قطعی غیرزنده: همهٔ نمادها و کندل‌های این مسیر فیکسچر سینتتیک اعلان‌شده‌اند "
    "(تولید قطعی بر پایه sha256). هیچ درخواست شبکه‌ای، دادهٔ ارائه‌دهنده یا اتکا به "
    "ساعت دیوار در کار نیست؛ متادیتای فیکسچر هرگز حقیقت بازار نیست."
)


def provenance() -> Dict[str, Any]:
    """Canonical non-live provenance block attached to every service output."""
    return {
        "canonical": "NON_LIVE_FIXTURE",
        "service_version": SERVICE_VERSION,
        "fixture_universe_version": FIXTURE_UNIVERSE_VERSION,
        "dq_engine_version": UNIVERSE_DQ_VERSION,
        "as_of_ts": FIXTURE_AS_OF_TS,
        "as_of_utc": FIXTURE_DECLARED_AT_UTC.isoformat(),
        "audit_bar_count": AUDIT_BAR_COUNT,
        "note_en": PROVENANCE_NOTE_EN,
        "note_fa": PROVENANCE_NOTE_FA,
    }


def _all_records() -> List[InstrumentRecord]:
    """Every fixture record (default universe + the excluded marker market)."""
    return all_fixture_records()


def _resolution() -> Any:
    """Resolve fixture records against the default universe spec (mechanical,
    fail-closed; the excluded marker market keeps its explicit reason)."""
    return build_default_universe(_all_records(), fixture_universe())


def _records_by_market(records: List[InstrumentRecord]) -> Dict[str, List[InstrumentRecord]]:
    grouped: Dict[str, List[InstrumentRecord]] = {}
    for record in records:
        grouped.setdefault(record.market.value, []).append(record)
    return grouped


def _market_trust(grouped: Dict[str, List[InstrumentRecord]]) -> Dict[str, str]:
    """Per-market trust label from the instrument master TrustClass.

    A single distinct class across the market's records is used verbatim;
    mixed claims are never guessed and fall back to MISSING (no invented
    trust label). All fixture records are uniformly SYNTHETIC today, so the
    fallback is a defensive guard only."""
    out: Dict[str, str] = {}
    for market, records in grouped.items():
        distinct = {r.trust_class for r in records}
        out[market] = next(iter(distinct)).value if len(distinct) == 1 else TrustClass.MISSING.value
    return out


def _audit_record(record: InstrumentRecord, bar_count: int = AUDIT_BAR_COUNT) -> SymbolCoverage:
    """Mechanical audit of one fixture symbol's seeded bar history.

    The engine's injected as_of/staleness pattern is used verbatim:
    ``now_ts=FIXTURE_AS_OF_TS`` (declared fixture instant, never a clock);
    corporate-action / PIT claims are undeclared for fixtures -> the engine
    reports UNKNOWN rather than guessing."""
    bars = synthetic_bars(record.symbol, AUDIT_TIMEFRAME_CODE, bar_count)
    return audit_symbol_history(
        bars,
        symbol_id=record.instrument_id,
        max_staleness_seconds=AUDIT_MAX_STALENESS_SECONDS,
        expected_interval_seconds=AUDIT_EXPECTED_INTERVAL_SECONDS,
        corporate_actions_declared=None,  # fixtures declare nothing -> UNKNOWN
        pit_available=None,               # generated bars carry no PIT claim -> UNKNOWN
        now_ts=FIXTURE_AS_OF_TS,
        trust_class=record.trust_class.value,
    )


def valid_markets() -> List[str]:
    """Sorted market identifiers present in the fixture records."""
    return sorted(_records_by_market(_all_records()))


def default_universe_markets() -> List[str]:
    """Markets selectable in the default fixture universe spec."""
    return sorted(m.value for m in fixture_universe().markets)


def market_summaries() -> List[Dict[str, Any]]:
    """Per-market coverage summary rows for GET /markets.

    Every market present in the fixture records is listed (including the
    non-selectable individual-US-equity marker market, explicitly flagged
    ``in_default_universe=False`` — exclusion is reported, never hidden).
    ``worst_issues`` aggregates each mechanical issue count across the
    market's audited symbols."""
    records = _all_records()
    grouped = _records_by_market(records)
    trust_by_market = _market_trust(grouped)
    audits = {r.instrument_id: _audit_record(r) for r in records}
    reports = build_market_coverage(
        {market: [audits[r.instrument_id] for r in grouped[market]] for market in grouped},
        trust_by_market,
    )
    report_by_market = {r.market: r for r in reports}
    default_markets = set(default_universe_markets())
    summaries: List[Dict[str, Any]] = []
    for market in sorted(grouped):
        market_records = grouped[market]
        market_audits = [audits[r.instrument_id] for r in market_records]
        summaries.append(
            {
                "market": market,
                "symbol_count": len(market_records),
                "audited_count": len(market_audits),
                "worst_issues": {
                    "duplicate_bars": sum(a.duplicate_bars for a in market_audits),
                    "out_of_order_bars": sum(a.out_of_order_bars for a in market_audits),
                    "invalid_bars": sum(a.invalid_bars for a in market_audits),
                    "stale_bars": sum(a.stale_bars for a in market_audits),
                    "missing_intervals": sum(len(a.missing_intervals) for a in market_audits),
                },
                "trust_class": trust_by_market[market],
                "in_default_universe": market in default_markets,
                "coverage_report": report_by_market[market].model_dump(mode="json"),
            }
        )
    return summaries


def market_coverage(market: str) -> Dict[str, Any]:
    """Full CoverageReport rows for one market; raises KeyError on unknown."""
    records = _all_records()
    grouped = _records_by_market(records)
    if market not in grouped:
        raise KeyError(market)
    market_records = grouped[market]
    audits = [_audit_record(r) for r in market_records]
    report = build_market_coverage({market: audits}, _market_trust(grouped))[0]
    return {
        "market": market,
        "trust_class": report.trust_class,
        "as_of_ts": FIXTURE_AS_OF_TS,
        "report": report.model_dump(mode="json"),
        "symbols": [a.model_dump(mode="json") for a in audits],
        "provenance": provenance(),
    }


def audit_symbol(instrument_id: str) -> Dict[str, Any]:
    """Per-symbol mechanical audit at the documented AUDIT_BAR_COUNT depth;
    raises KeyError for an unknown instrument_id."""
    record = next((r for r in _all_records() if r.instrument_id == instrument_id), None)
    if record is None:
        raise KeyError(instrument_id)
    coverage = _audit_record(record)
    return {
        "instrument_id": record.instrument_id,
        "market": record.market.value,
        "symbol": record.symbol,
        "name_en": record.name_en,
        "status": record.status.value,
        "trust_class": record.trust_class.value,
        "entitlement": record.entitlement.value,
        "source_identity": record.source_identity,
        "as_of_ts": FIXTURE_AS_OF_TS,
        "as_of_utc": FIXTURE_DECLARED_AT_UTC.isoformat(),
        "staleness_policy": {
            "max_staleness_seconds": AUDIT_MAX_STALENESS_SECONDS,
            "expected_interval_seconds": AUDIT_EXPECTED_INTERVAL_SECONDS,
            "note_en": (
                "stale_bars are counted relative to the INJECTED fixture as_of "
                "(2026-01-01T00:00Z), never a wall clock"
            ),
            "note_fa": "کندل‌های کهنه نسبت به as_of تزریق‌شدهٔ فیکسچر شمرده می‌شوند، نه ساعت دیوار",
        },
        "audit": coverage.model_dump(mode="json"),
        "flags": {
            "duplicates": coverage.duplicate_bars,
            "out_of_order": coverage.out_of_order_bars,
            "invalid_ohlcv": coverage.invalid_bars,
            "missing_intervals": len(coverage.missing_intervals),
            "stale_bars": coverage.stale_bars,
        },
        "provenance": provenance(),
    }
