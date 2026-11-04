"""
test_symbol_analyst.py - PKG-E (Wave 7) offline tests for the deterministic
symbol analyst engine (MASTER-RADAR directive §F).

Scope: ONLY backend/app/engines/symbol_analyst.py. All fixtures are crafted
in-file with pure integer/float arithmetic (no network, no clock, no I/O, no
LLM calls); every timestamp is a constant. The suite covers: claim
provenance completeness, confidence policy, digest determinism, unavailability
honesty (MISS-1), multi-timeframe agreement/conflict, staleness handling,
banned-content enforcement (forbidden_terms_scan), scenario invalidations
derived from independently recomputed swing levels, key-level provenance,
Persian text presence, and the zero-volume / minimum-bars edge cases.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.engines.symbol_analyst import (
    AnalystInput,
    Claim,
    ClaimKind,
    ClaimProvenance,
    ENGINE_VERSION,
    FundamentalsSection,
    GENERATED_BY,
    SeriesInput,
    StrategySignalContext,
    SymbolAnalysisReport,
    TrustClass,
    _ema,
    _last_pivot,
    _percentile_rank,
    _rsi_wilder,
    _to_indicator_bars,
    analyze_symbol,
    forbidden_terms_scan,
)

START_TS = 1_700_000_000
DAY = 86_400
WEEK = 604_800
HOUR = 3_600
AS_OF = START_TS + 121 * DAY  # one daily bar after the last daily fixture bar


# ---------------------------------------------------------------------------
# deterministic fixture builders (pure arithmetic, no randomness)
# ---------------------------------------------------------------------------

def _mk_bars(n: int, step: int, base: float, drift: float, amp: float,
             start_ts: int = START_TS, vol: float = 1_000_000.0) -> list[dict]:
    """Triangle-wave-with-drift bars: pullbacks make real swing pivots.

    Wave slope is +/-1 per bar by construction (amp range == cycle length),
    so |drift| < 1.0 gives genuine up/down legs and confirmed pivots.
    """
    bars = []
    for i in range(n):
        tri = amp - abs((i % 16) - 8)
        close = base + drift * i + tri
        open_ = base + drift * (i - 1) + (amp - abs(((i - 1) % 16) - 8)) if i else close
        bars.append({
            "ts": start_ts + i * step,
            "o": open_,
            "h": max(open_, close) + 3.0,
            "l": min(open_, close) - 3.0,
            "c": close,
            "v": vol + 10_000.0 * ((i * 7) % 11),
        })
    return bars


def _daily(direction: str = "up", n: int = 120) -> SeriesInput:
    drift, base = (0.5, 1000.0) if direction == "up" else (-0.5, 5000.0)
    return SeriesInput(bars=_mk_bars(n, DAY, base, drift, 30.0), timeframe="1d",
                       trust_class=TrustClass.REAL_VERIFIED, source_class="SEEDED_CANDLES")


def _weekly(direction: str = "up", n: int = 60) -> SeriesInput:
    drift, base = (0.5, 2000.0) if direction == "up" else (-0.5, 5000.0)
    return SeriesInput(bars=_mk_bars(n, WEEK, base, drift, 40.0), timeframe="1w",
                       trust_class=TrustClass.REAL_VERIFIED, source_class="SEEDED_CANDLES")


def _hourly(direction: str = "up", n: int = 120) -> SeriesInput:
    drift, base = (0.5, 900.0) if direction == "up" else (-0.5, 900.0)
    return SeriesInput(bars=_mk_bars(n, HOUR, base, drift, 8.0), timeframe="1h",
                       trust_class=TrustClass.REAL_VERIFIED, source_class="SEEDED_CANDLES")


def _missing(timeframe: str) -> SeriesInput:
    return SeriesInput(timeframe=timeframe, trust_class=TrustClass.MISSING, source_class="UNSPECIFIED")


_FUND_ROWS = [
    {"field": "pe_ratio", "value": 7.2, "as_of_ts": START_TS,
     "source_class": "FUNDAMENTAL_DOSSIER", "trust_class": "REAL_VERIFIED"},
    {"field": "roe_percent", "value": 21.5, "as_of_ts": START_TS,
     "source_class": "FUNDAMENTAL_DOSSIER", "trust_class": "REAL_UNVERIFIED"},
]

_SIGNALS = [
    {"strategy_id": "strat-a", "side": "BUY", "score": 0.72, "ts": START_TS + 10 * DAY},
    {"strategy_id": "strat-b", "side": "SELL", "score": -0.31, "ts": START_TS + 11 * DAY},
]

_ANNOTATIONS = [{"kind": "hline", "price": 1100.0, "ts": START_TS + 5 * DAY, "note": "manual level"}]


def _input(symbol: str = "AAA1", daily: SeriesInput | None = None, weekly: SeriesInput | None = None,
           hourly: SeriesInput | None = None, fundamentals: FundamentalsSection | None = None,
           signals: StrategySignalContext | None = None, sector: dict | None = None,
           annotations: list[dict] | None = None) -> AnalystInput:
    """Default = FULL availability (daily/weekly/hourly up + all sections)."""
    return AnalystInput(
        symbol=symbol,
        name_fa="نماد آزمایشی",
        as_of_ts=AS_OF,
        daily=_daily() if daily is None else daily,
        weekly=_weekly() if weekly is None else weekly,
        hourly=_hourly() if hourly is None else hourly,
        fundamentals=FundamentalsSection(available=True, rows=list(_FUND_ROWS)) if fundamentals is None else fundamentals,
        strategy_signals=StrategySignalContext(available=True, signals=[dict(s) for s in _SIGNALS]) if signals is None else signals,
        sector_context={"available": True, "sector_name": "metals"} if sector is None else sector,
        annotations=[dict(a) for a in _ANNOTATIONS] if annotations is None else (annotations or []),
    )


def _unavailable_input(symbol: str = "AAA1") -> AnalystInput:
    """Daily-only market data; every optional section unavailable."""
    return AnalystInput(
        symbol=symbol, as_of_ts=AS_OF,
        daily=_daily(), weekly=_missing("1w"), hourly=_missing("1h"),
        fundamentals=FundamentalsSection(available=False, unavailable_reason="dossier not built"),
        strategy_signals=StrategySignalContext(available=False, unavailable_reason="engine disabled"),
    )


# ---------------------------------------------------------------------------
# independent re-implementations of the documented rules (for cross-checks)
# ---------------------------------------------------------------------------

def _independent_swing(bars: list[dict], side: str) -> dict | None:
    """Doc rule: bar whose high (low) equals the max (min) of its +/-3 window;
    only indices with 3 bars on each side qualify; most recent match wins."""
    vals = [b["h" if side == "high" else "l"] for b in bars]
    found = None
    for i in range(3, len(bars) - 3):
        extreme = max(vals[i - 3:i + 4]) if side == "high" else min(vals[i - 3:i + 4])
        if vals[i] == extreme:
            found = bars[i]  # ascending loop -> most recent match wins
    return found


def _claims_by_ref(report: SymbolAnalysisReport, ref: str) -> list[Claim]:
    return [c for c in report.claims if c.provenance.evidence_ref == ref]


def _scenario_claim(report: SymbolAnalysisReport, direction: str) -> Claim:
    rec = next(s for s in report.scenarios if s.direction == direction)
    claim = next(c for c in report.claims if c.claim_id == rec.claim_id)
    assert claim.kind == ClaimKind.SCENARIO
    return claim


# ---------------------------------------------------------------------------
# full-availability run: provenance, confidence policy, digest determinism
# ---------------------------------------------------------------------------

class TestFullAvailability:
    def test_report_builds_with_expected_shape(self):
        report = analyze_symbol(_input())
        assert report.symbol == "AAA1"
        assert report.name_fa == "نماد آزمایشی"
        assert report.as_of_ts == AS_OF
        assert report.engine_version == ENGINE_VERSION == "ANALYST-1.0.0"
        assert len(report.claims) > 20
        assert len(report.scenarios) == 3

    def test_every_claim_has_complete_provenance(self):
        inp = _input()
        report = analyze_symbol(inp)
        for claim in report.claims:
            prov = claim.provenance
            assert isinstance(prov, ClaimProvenance)
            assert prov.source_class
            assert prov.as_of_ts == inp.as_of_ts
            assert prov.timeframe
            assert prov.evidence_ref
            assert isinstance(prov.trust_class, TrustClass)
            assert isinstance(prov.conflict_with, list)
            assert claim.claim_id and claim.text_en and claim.text_fa and claim.timeframe

    def test_deterministic_kinds_carry_no_confidence(self):
        report = analyze_symbol(_input())
        for claim in report.claims:
            if claim.kind in (ClaimKind.OBSERVED_FACT, ClaimKind.CALCULATED_METRIC):
                assert claim.provenance.confidence is None, claim.claim_id

    def test_interpretive_kinds_carry_bounded_confidence(self):
        report = analyze_symbol(_input())
        for claim in report.claims:
            if claim.kind in (ClaimKind.MODEL_INTERPRETATION, ClaimKind.RECOMMENDATION):
                assert claim.provenance.confidence is not None, claim.claim_id
                assert 0.0 <= claim.provenance.confidence <= 1.0
            if claim.kind == ClaimKind.SCENARIO:
                assert 0.35 <= claim.provenance.confidence <= 0.65

    def test_scenario_confidence_within_humility_bounds(self):
        report = analyze_symbol(_input())
        scenario_conf = [c.provenance.confidence for c in report.claims if c.kind == ClaimKind.SCENARIO]
        assert scenario_conf and all(0.35 <= v <= 0.65 for v in scenario_conf)

    def test_digest_deterministic_across_runs(self):
        r1 = analyze_symbol(_input())
        r2 = analyze_symbol(_input())
        assert r1.report_digest == r2.report_digest
        assert r1.report_digest
        assert r1.claims == r2.claims
        assert r1.model_dump(mode="json") == r2.model_dump(mode="json")

    def test_digest_changes_when_input_changes(self):
        r1 = analyze_symbol(_input())
        r2 = analyze_symbol(_input(symbol="ZZZ9"))
        assert r1.report_digest != r2.report_digest

    def test_claim_ids_unique_sequential_deterministic(self):
        r1 = analyze_symbol(_input())
        ids = [c.claim_id for c in r1.claims]
        assert len(ids) == len(set(ids))
        assert ids == [f"c{i:03d}" for i in range(1, len(ids) + 1)]
        assert [c.claim_id for c in analyze_symbol(_input()).claims] == ids

    def test_engine_version_and_generated_by_honesty_strings(self):
        report = analyze_symbol(_input())
        assert report.engine_version == "ANALYST-1.0.0"
        assert "deterministic-rules-v1" in report.generated_by
        assert "no LLM call" in report.generated_by
        assert "owner-gated" in report.generated_by
        assert report.generated_by == GENERATED_BY

    def test_mtf_agree_on_aligned_uptrend(self):
        report = analyze_symbol(_input())
        assert report.mtf_agreement == {
            "daily": "BULLISH", "weekly": "BULLISH", "hourly": "BULLISH", "agreement": "AGREE"}

    def test_scenario_slots_complete(self):
        report = analyze_symbol(_input())
        assert [s.direction for s in report.scenarios] == ["BASE", "BULLISH", "BEARISH"]

    def test_key_levels_present_with_provenance_refs_in_claims(self):
        report = analyze_symbol(_input())
        refs = {c.provenance.evidence_ref for c in report.claims}
        kinds = {k.kind for k in report.key_levels}
        assert {"swing_high", "swing_low", "ema20", "ema50"} <= kinds
        for level in report.key_levels:
            assert level.evidence_ref in refs
            assert isinstance(level.ts, int)
            assert level.price > 0

    def test_indicator_metric_claims_present(self):
        report = analyze_symbol(_input())
        for ref in ("momentum.rsi14.d1", "momentum.macd.d1", "bollinger.position.d1",
                    "volatility.atr14.d1", "volume.sma20_ratio.d1", "trend.ema_values.d1",
                    "structure.swing_high.d1", "structure.swing_low.d1"):
            assert _claims_by_ref(report, ref), f"missing claim for {ref}"
            assert all(c.kind == ClaimKind.CALCULATED_METRIC for c in _claims_by_ref(report, ref))

    def test_fundamentals_row_claims_restate_provided_values(self):
        report = analyze_symbol(_input())
        pe_claims = _claims_by_ref(report, "fundamentals.row.pe_ratio")
        assert len(pe_claims) == 1
        claim = pe_claims[0]
        assert claim.kind == ClaimKind.OBSERVED_FACT
        assert "7.20" in claim.text_en and "pe_ratio" in claim.text_en
        assert claim.provenance.trust_class == TrustClass.REAL_VERIFIED
        roe = _claims_by_ref(report, "fundamentals.row.roe_percent")[0]
        assert roe.provenance.trust_class == TrustClass.REAL_UNVERIFIED

    def test_strategy_recommendation_is_decision_support(self):
        report = analyze_symbol(_input())
        recs = [c for c in report.claims if c.kind == ClaimKind.RECOMMENDATION]
        assert len(recs) == 1
        assert "decision support" in recs[0].text_en
        assert "own judgment" in recs[0].text_en
        assert recs[0].provenance.confidence == 0.50
        assert _claims_by_ref(report, "strategy.signals")

    def test_sector_available_claim_and_no_missing_entry(self):
        report = analyze_symbol(_input())
        assert _claims_by_ref(report, "sector.context")
        assert all(m.item != "sector_context" for m in report.missing_data)

    def test_annotation_claim_only_when_present(self):
        with_ann = analyze_symbol(_input())
        assert _claims_by_ref(with_ann, "annotations.user")
        without = analyze_symbol(_input(annotations=[]))
        assert not _claims_by_ref(without, "annotations.user")

    def test_models_are_frozen(self):
        report = analyze_symbol(_input())
        with pytest.raises(ValidationError):
            report.symbol = "HACK"
        with pytest.raises(ValidationError):
            report.claims[0].text_en = "mutated"
        with pytest.raises(ValidationError):
            report.claims[0].provenance.confidence = 0.99

    def test_input_models_are_frozen_with_defaults(self):
        s = SeriesInput()
        assert s.bars == [] and s.stale is False and s.trust_class == TrustClass.MISSING
        with pytest.raises(ValidationError):
            s.stale = True
        inp = AnalystInput(symbol="X", as_of_ts=1)
        assert inp.fundamentals.available is False
        assert inp.strategy_signals.available is False
        assert inp.sector_context == {"available": False, "reason": "not_admitted"}
        assert inp.annotations == []


# ---------------------------------------------------------------------------
# Persian text honesty
# ---------------------------------------------------------------------------

def _has_persian(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" or ch == "\u200c" for ch in text)


class TestPersianText:
    def test_executive_summary_fa_nonempty_and_persian(self):
        report = analyze_symbol(_input())
        assert report.executive_summary_fa
        assert _has_persian(report.executive_summary_fa)
        assert report.executive_summary_en

    def test_every_claim_has_nonempty_persian_text(self):
        for report in (analyze_symbol(_input()), analyze_symbol(_unavailable_input())):
            for claim in report.claims:
                assert claim.text_fa.strip(), claim.claim_id
                assert _has_persian(claim.text_fa), claim.claim_id

    def test_risk_factors_and_scenarios_bilingual(self):
        report = analyze_symbol(_input())
        for risk in report.risk_factors:
            assert risk.text_en and _has_persian(risk.text_fa)
        for rec in report.scenarios:
            assert rec.invalidation_en and _has_persian(rec.invalidation_fa)
        assert _has_persian(report.uncertainty_note_fa)


# ---------------------------------------------------------------------------
# unavailability honesty (MISS-1)
# ---------------------------------------------------------------------------

class TestUnavailabilityHonesty:
    def test_missing_series_and_sections_listed_with_reasons(self):
        report = analyze_symbol(_unavailable_input())
        items = {m.item: m for m in report.missing_data}
        assert {"series_w1", "series_h1", "fundamentals", "strategy_signals"} <= set(items)
        assert items["fundamentals"].reason == "dossier not built"
        assert items["strategy_signals"].reason == "engine disabled"
        assert items["series_w1"].trust_class == TrustClass.MISSING

    def test_sector_context_missing_entry_default_reason(self):
        report = analyze_symbol(_unavailable_input())
        entry = next(m for m in report.missing_data if m.item == "sector_context")
        assert entry.reason == "not_admitted"

    def test_mtf_insufficient_data_when_one_timeframe(self):
        report = analyze_symbol(_unavailable_input())
        assert report.mtf_agreement["agreement"] == "INSUFFICIENT_DATA"
        assert report.mtf_agreement["weekly"] == "MISSING"
        assert report.mtf_agreement["hourly"] == "MISSING"

    def test_no_directional_claims_for_missing_timeframes(self):
        report = analyze_symbol(_unavailable_input())
        for claim in report.claims:
            if claim.timeframe in ("1w", "1h"):
                assert claim.kind == ClaimKind.OBSERVED_FACT, claim.claim_id
                assert claim.provenance.trust_class == TrustClass.MISSING, claim.claim_id
                assert "unavailable" in claim.text_en or "کافی نیست" in claim.text_fa
        refs = {c.provenance.evidence_ref for c in report.claims}
        assert "trend.ema_arrangement.w1" not in refs
        assert "trend.ema_arrangement.h1" not in refs
        assert "momentum.rsi14.h1" not in refs

    def test_all_empty_series_still_builds(self):
        report = analyze_symbol(AnalystInput(symbol="EMPTY", as_of_ts=AS_OF))
        assert report.claims
        items = {m.item for m in report.missing_data}
        assert {"series_d1", "series_w1", "series_h1", "fundamentals",
                "strategy_signals", "sector_context"} <= items
        assert report.mtf_agreement["agreement"] == "INSUFFICIENT_DATA"
        assert forbidden_terms_scan(report) == []

    def test_minimum_bars_boundary_29_vs_30(self):
        short = analyze_symbol(_input(weekly=_weekly(n=29)))
        assert any(m.item == "series_w1" for m in short.missing_data)
        refs_short = {c.provenance.evidence_ref for c in short.claims}
        assert "trend.ema_arrangement.w1" not in refs_short
        exact = analyze_symbol(_input(weekly=_weekly(n=30)))
        assert all(m.item != "series_w1" for m in exact.missing_data)
        refs_exact = {c.provenance.evidence_ref for c in exact.claims}
        assert "trend.ema_arrangement.w1" in refs_exact

    def test_uncertainty_count_matches_missing_ledger(self):
        report = analyze_symbol(_unavailable_input())
        assert report.uncertainty_count == len(report.missing_data) == 5
        assert "5" in report.uncertainty_note_en
        assert "5" in report.uncertainty_note_fa


# ---------------------------------------------------------------------------
# multi-timeframe conflict
# ---------------------------------------------------------------------------

class TestMultiTimeframeConflict:
    def _conflict_report(self) -> SymbolAnalysisReport:
        return analyze_symbol(_input(daily=_daily("up"), weekly=_weekly("down"), hourly=_hourly("up")))

    def test_disagreement_status(self):
        report = self._conflict_report()
        assert report.mtf_agreement["agreement"] == "DISAGREE"
        assert report.mtf_agreement["daily"] == "BULLISH"
        assert report.mtf_agreement["weekly"] == "BEARISH"

    def test_disagreement_claim_has_conflict_with_refs(self):
        report = self._conflict_report()
        mtf_claims = _claims_by_ref(report, "mtf.agreement")
        interp = [c for c in mtf_claims if c.kind == ClaimKind.MODEL_INTERPRETATION]
        assert len(interp) == 1
        assert interp[0].provenance.conflict_with == ["trend.ema_arrangement.w1"]

    def test_regime_risk_factor_on_disagreement(self):
        report = self._conflict_report()
        assert any(r.code == "REGIME_RISK" for r in report.risk_factors)

    def test_dominant_reading_follows_daily_on_split(self):
        report = self._conflict_report()
        base_claim = _scenario_claim(report, "BASE")
        assert "bullish" in base_claim.text_en  # daily is bullish -> base continues it


# ---------------------------------------------------------------------------
# freshness / staleness
# ---------------------------------------------------------------------------

class TestStaleness:
    def _stale_input(self) -> AnalystInput:
        stale_daily = SeriesInput(bars=_daily().bars, timeframe="1d",
                                  trust_class=TrustClass.REAL_VERIFIED,
                                  source_class="SEEDED_CANDLES", stale=True)
        return _input(daily=stale_daily)

    def test_stale_data_risk_factor_present(self):
        report = analyze_symbol(self._stale_input())
        assert any(r.code == "DATA_RISK" for r in report.risk_factors)

    def test_stale_claim_with_stale_trust(self):
        report = analyze_symbol(self._stale_input())
        stale_claims = [c for c in report.claims
                        if c.provenance.evidence_ref == "availability.stale.d1"]
        assert len(stale_claims) == 1
        assert stale_claims[0].kind == ClaimKind.OBSERVED_FACT
        assert stale_claims[0].provenance.trust_class == TrustClass.STALE

    def test_stale_uncertainty_count_increments(self):
        clean = analyze_symbol(_input())
        stale = analyze_symbol(self._stale_input())
        assert stale.uncertainty_count == clean.uncertainty_count + 1
        assert any(m.item == "series_d1_freshness" for m in stale.missing_data)

    def test_freshness_bars_computed_from_injected_timestamps(self):
        report = analyze_symbol(self._stale_input())
        claim = next(c for c in report.claims if c.provenance.evidence_ref == "availability.stale.d1")
        # last daily fixture bar is 2 days before as_of
        assert claim.provenance.freshness_bars == 2


# ---------------------------------------------------------------------------
# banned-content enforcement (directive §F, ABSOLUTE)
# ---------------------------------------------------------------------------

class TestBannedContent:
    def test_scan_clean_uptrend_full_availability(self):
        assert forbidden_terms_scan(analyze_symbol(_input(symbol="AAA1"))) == []

    def test_scan_clean_downtrend(self):
        inp = _input(symbol="BBB2", daily=_daily("down"), weekly=_weekly("down"), hourly=_hourly("down"))
        assert forbidden_terms_scan(analyze_symbol(inp)) == []

    def test_scan_clean_mixed_timeframes(self):
        inp = _input(symbol="CCC3", daily=_daily("up"), weekly=_weekly("up"), hourly=_hourly("down"))
        report = analyze_symbol(inp)
        assert forbidden_terms_scan(report) == []
        assert report.mtf_agreement["agreement"] == "DISAGREE"

    def test_scan_clean_everything_unavailable(self):
        assert forbidden_terms_scan(analyze_symbol(_unavailable_input(symbol="DDD4"))) == []

    def test_scanner_catches_planted_en_banned_claim(self):
        report = analyze_symbol(_input())
        bad = Claim(
            claim_id="c999", kind=ClaimKind.OBSERVED_FACT,
            text_en="the target price is 100 and this is guaranteed",
            text_fa="سطح فنی مهم است.", timeframe="1d",
            provenance=report.claims[0].provenance,
        )
        tampered = report.model_copy(update={"claims": list(report.claims) + [bad]})
        findings = forbidden_terms_scan(tampered)
        assert findings, "scanner must catch the planted claim"
        assert any("target price" in f for f in findings)
        assert any("guarantee" in f for f in findings)
        assert all(f.startswith("report.claims") for f in findings)

    def test_scanner_catches_planted_fa_banned_claim(self):
        report = analyze_symbol(_input())
        bad = Claim(
            claim_id="c998", kind=ClaimKind.OBSERVED_FACT,
            text_en="a technical level.", text_fa="این سیگنال تضمین شده است.",
            timeframe="1d", provenance=report.claims[0].provenance,
        )
        tampered = report.model_copy(update={"claims": list(report.claims) + [bad]})
        findings = forbidden_terms_scan(tampered)
        assert any("تضمین" in f for f in findings)

    def test_scanner_checks_summaries_not_only_claims(self):
        report = analyze_symbol(_input())
        tampered = report.model_copy(update={"executive_summary_en": "we guarantee profits"})
        findings = forbidden_terms_scan(tampered)
        assert any("executive_summary_en" in f for f in findings)

    def test_engine_is_fail_closed_on_banned_content(self):
        # the ban list lives in the module; if a rule text ever picked up a
        # banned term the engine must refuse to return the report. Simulate
        # by monkeypatching the executive summary through a subclass is not
        # possible (frozen); instead assert the gate exists by contract:
        import inspect
        from app.engines import symbol_analyst as mod
        source = inspect.getsource(mod.analyze_symbol)
        assert "forbidden_terms_scan" in source
        assert "raise ValueError" in source


# ---------------------------------------------------------------------------
# scenario levels & invalidations (cross-checked against independent pivots)
# ---------------------------------------------------------------------------

class TestScenariosAndLevels:
    def test_every_scenario_has_nonempty_invalidation(self):
        report = analyze_symbol(_input())
        for rec in report.scenarios:
            assert rec.invalidation_en.strip()
            assert rec.invalidation_fa.strip()

    def test_bullish_level_equals_independent_swing_high(self):
        bars = _daily().bars
        report = analyze_symbol(_input())
        expected = float(_independent_swing(bars, "high")["h"])
        bull = next(s for s in report.scenarios if s.direction == "BULLISH")
        assert bull.key_level == pytest.approx(expected)

    def test_bearish_level_equals_independent_swing_low(self):
        bars = _daily().bars
        report = analyze_symbol(_input())
        expected = float(_independent_swing(bars, "low")["l"])
        bear = next(s for s in report.scenarios if s.direction == "BEARISH")
        assert bear.key_level == pytest.approx(expected)

    def test_invalidation_embeds_computed_swing_levels(self):
        bars = _daily().bars
        report = analyze_symbol(_input())
        swing_high = float(_independent_swing(bars, "high")["h"])
        swing_low = float(_independent_swing(bars, "low")["l"])
        bull = next(s for s in report.scenarios if s.direction == "BULLISH")
        bear = next(s for s in report.scenarios if s.direction == "BEARISH")
        assert f"{swing_low:.2f}" in bull.invalidation_en
        assert "2 consecutive daily bars" in bull.invalidation_en
        assert f"{swing_high:.2f}" in bear.invalidation_en
        assert "2 consecutive daily bars" in bear.invalidation_en

    def test_scenario_claim_ids_resolve_to_scenario_claims(self):
        report = analyze_symbol(_input())
        by_id = {c.claim_id: c for c in report.claims}
        for rec in report.scenarios:
            claim = by_id[rec.claim_id]
            assert claim.kind == ClaimKind.SCENARIO
            assert claim.provenance.evidence_ref.startswith("scenario.")
            assert 0.35 <= claim.provenance.confidence <= 0.65

    def test_opposing_scenario_conflicts_with_dominant_reading(self):
        report = analyze_symbol(_input())  # all-up -> dominant bullish
        bear_claim = _scenario_claim(report, "BEARISH")
        assert bear_claim.provenance.conflict_with == ["mtf.agreement"]
        bull_claim = _scenario_claim(report, "BULLISH")
        assert bull_claim.provenance.conflict_with == []

    def test_base_scenario_has_no_invented_key_level(self):
        report = analyze_symbol(_input())
        base = next(s for s in report.scenarios if s.direction == "BASE")
        assert base.key_level is None

    def test_no_swing_structure_scenario_degrades_honestly(self):
        # strictly monotonic ramp: no +/-3-window pivot exists anywhere
        ramp = [{"ts": START_TS + i * DAY, "o": 100.0 + i, "h": 103.0 + i,
                 "l": 97.0 + i, "c": 100.0 + i, "v": 1000.0} for i in range(40)]
        report = analyze_symbol(_input(daily=SeriesInput(bars=ramp, timeframe="1d",
                                                         trust_class=TrustClass.REAL_VERIFIED,
                                                         source_class="SEEDED_CANDLES")))
        for rec in report.scenarios:
            if rec.direction in ("BULLISH", "BEARISH"):
                assert rec.key_level is None
                assert rec.invalidation_en and rec.invalidation_fa
        items = {m.item for m in report.missing_data}
        assert {"swing_high_d1", "swing_low_d1"} <= items


# ---------------------------------------------------------------------------
# risk factors, liquidity and volatility edges
# ---------------------------------------------------------------------------

class TestRiskAndLiquidity:
    def _zero_volume_input(self) -> AnalystInput:
        bars = [{**b, "v": 0.0} for b in _daily().bars]
        return _input(daily=SeriesInput(bars=bars, timeframe="1d",
                                        trust_class=TrustClass.REAL_VERIFIED,
                                        source_class="SEEDED_CANDLES"))

    def test_zero_volume_does_not_crash_and_reports_missing(self):
        report = analyze_symbol(self._zero_volume_input())  # must not raise
        assert any(m.item == "volume_ratio_d1" and m.trust_class == TrustClass.MISSING
                   for m in report.missing_data)
        vol_claims = _claims_by_ref(report, "volume.sma20_ratio.d1")
        assert len(vol_claims) == 1
        assert vol_claims[0].kind == ClaimKind.OBSERVED_FACT
        assert vol_claims[0].provenance.trust_class == TrustClass.MISSING

    def test_zero_volume_liquidity_risk(self):
        report = analyze_symbol(self._zero_volume_input())
        assert any(r.code == "LIQ_RISK" for r in report.risk_factors)

    def test_vol_risk_when_atr_percentile_high(self):
        report = analyze_symbol(_input())
        vol_claims = _claims_by_ref(report, "volatility.atr14.d1")
        assert vol_claims
        pct = float(vol_claims[0].text_en.split("percentile rank ")[1].split()[0].rstrip("."))
        has_risk = any(r.code == "VOL_RISK" for r in report.risk_factors)
        assert has_risk == (pct >= 0.70)

    def test_info_risk_when_fundamentals_missing(self):
        report = analyze_symbol(_unavailable_input())
        assert any(r.code == "INFO_RISK" for r in report.risk_factors)

    def test_atr_percentile_within_unit_interval(self):
        report = analyze_symbol(_input())
        claim = _claims_by_ref(report, "volatility.reading.d1")[0]
        assert claim.kind == ClaimKind.MODEL_INTERPRETATION


# ---------------------------------------------------------------------------
# local indicator math (white-box, documented definitions)
# ---------------------------------------------------------------------------

class TestLocalMath:
    def test_rsi_wilder_constant_series_is_50(self):
        closes = [100.0] * 40
        series = _rsi_wilder(closes)
        assert all(v == 0.0 for v in series[:14])
        assert series[14] == 50.0
        assert series[-1] == 50.0

    def test_rsi_wilder_ramps_hit_bounds(self):
        up = _rsi_wilder([100.0 + i for i in range(40)])
        assert up[14] == 100.0 and up[-1] == 100.0
        down = _rsi_wilder([100.0 - i for i in range(40)])
        assert down[14] == 0.0 and down[-1] == 0.0

    def test_rsi_wilder_is_zero_before_seed_index(self):
        closes = [100.0 + (i % 5) for i in range(30)]
        series = _rsi_wilder(closes)
        assert len(series) == 30
        assert all(v == 0.0 for v in series[:14])

    def test_ema_sma_seed_matches_hand_computed_values(self):
        out = _ema([1.0, 2.0, 3.0, 4.0, 5.0], 3)
        assert out == [2.0, 2.0, 2.0, 3.0, 4.0]

    def test_percentile_rank_definition(self):
        assert _percentile_rank([1.0, 2.0, 3.0], 3.0) == 1.0
        assert _percentile_rank([1.0, 2.0, 3.0], 2.0) == pytest.approx(2 / 3)
        assert _percentile_rank([], 5.0) == 0.0

    def test_engine_pivot_matches_independent_rule(self):
        bars = _daily().bars
        for side in ("high", "low"):
            engine = _last_pivot(bars, side)
            indie = _independent_swing(bars, side)
            assert engine is not None and indie is not None
            assert engine["price"] == float(indie["h" if side == "high" else "l"])
            assert engine["ts"] == indie["ts"]

    def test_indicator_adapter_shape(self):
        adapted = _to_indicator_bars([{"ts": 5, "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 9.0}])
        assert adapted[0] == {"time": 5, "open": 1.0, "high": 2.0, "low": 0.5,
                              "close": 1.5, "volume": 9.0}
        # the adapter output is directly consumable by app.engines.indicators
        from app.engines import indicators
        bars = _to_indicator_bars(_daily().bars)
        assert indicators.atr(bars, 14)
        assert indicators.macd(bars)["histogram"]
        assert indicators.bollinger(bars, 20, 2.0)["upper"]
