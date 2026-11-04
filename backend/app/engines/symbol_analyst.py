"""
symbol_analyst.py - PKG-E (Wave 7) deterministic per-symbol analyst engine.

MASTER-RADAR directive §F (evidence synthesis & claim provenance). Every
user-facing statement is a *claim* with full provenance (source class, as-of
ts, freshness, timeframe, evidence pointer, trust class and -- only for
non-deterministic kinds -- a bounded confidence). The engine is DETERMINISTIC
and RULE-BASED: no network I/O, no clock reads (timestamps injected via
``AnalystInput.as_of_ts``), no LLM / AI-provider calls.

LLM narration seam (owner-gated, deliberately DISCONNECTED): a future package
may post-process ``SymbolAnalysisReport.claims`` through an approved provider
for richer prose. That path is not implemented here, nothing is imported from
any provider here, and the seam must stay behind an explicit owner gate per
directive §F. ``generated_by`` marks reports as purely deterministic.

Documented deterministic rules (rule ids appear inside claim texts):
  TREND-1  EMA20/EMA50 arrangement sets direction (above -> bullish, below ->
           bearish, equal -> flat); slope = sign of change across the last
           five EMA20 values. EMAs are SMA-seeded (same convention as
           ``app.engines.indicators._ema_series``).
  STRUCT-1 swing pivot = bar whose high (low) equals the max (min) of its
           +/-3 neighbourhood; only confirmed pivots (3 bars each side)
           qualify; the MOST RECENT confirmed pivot wins; ties keep the most
           recent bar.
  VOL-1    ATR(14) percentile rank in its own history = share of history
           values <= last value; >= 0.70 elevated, <= 0.30 compressed, else
           normal. ATR via ``app.engines.indicators.atr``.
  LIQ-1    volume ratio = last volume / SMA20(volume); needs the last 20
           volume values present and > 0, else the read is MISSING;
           >= 1.5 above average, <= 0.5 below average, else near average.
  MOM-1    Wilder RSI(14): seed = simple mean of the first 14 changes at
           index 14, Wilder smoothing after, 0.0 before index 14 (no seed
           movement -> 50.0). > 70 strong positive, > 50 positive,
           < 30 strong negative, < 50 negative.
  MOM-2    MACD(12,26,9) histogram sign via ``app.engines.indicators.macd``.
  BB-1     last close vs Bollinger (20, 2) via
           ``app.engines.indicators.bollinger``.
  MTF-1    agreement matrix over analyzed timeframes: AGREE (all equal) /
           DISAGREE (bullish and bearish both present) / PARTIAL (mix incl.
           flat, no opposition) / INSUFFICIENT_DATA (< 2 analyzed). Daily
           priority applies when readings split.
  SCN-1/2/3 base/bullish/bearish scenarios derived ONLY from computed levels
           (no invented numbers); scenario confidence bounded to 0.35..0.65
           (bounded humility); every scenario carries a concrete invalidation.
  RISK-1   deterministic risk-factor mapping (see ``_risk_factors``).
  MISS-1   every unavailable/degraded input surfaces as a missing-data entry
           plus an OBSERVED_FACT claim (trust MISSING/STALE); the engine
           never fabricates content for inputs it did not receive.

Banned-content policy (directive §F, ABSOLUTE): no guaranteed forecasts, no
fabricated citations, no invented fundamentals, no unsupported price targets.
``forbidden_terms_scan`` audits every text field of a report for the banned
strings; ``analyze_symbol`` is fail-closed and refuses to return a report
that fails its own scan.

Shared bar contract: {"ts": int epoch-sec ascending unique,
"o","h","l","c","v": float}. ``app.engines.indicators`` consumes
{"time","open","high","low","close","volume"} dicts; a pure local adapter
bridges the two shapes without modifying the shared module.
"""
from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.engines import indicators

ENGINE_VERSION = "ANALYST-1.0.0"
GENERATED_BY = "deterministic-rules-v1 (no LLM call; provider path is owner-gated and disconnected)"

MIN_BARS = 30
CONF_TREND = 0.60          # MODEL_INTERPRETATION: trend reading (TREND-1)
CONF_READING = 0.60        # MODEL_INTERPRETATION: volatility / momentum reads
CONF_MTF_AGREE = 0.65      # MTF-1 AGREE
CONF_MTF_DISAGREE = 0.55   # MTF-1 DISAGREE
CONF_MTF_PARTIAL = 0.50    # MTF-1 PARTIAL
CONF_BASE = 0.55           # SCN-1 base scenario
CONF_DIR_AGREE = 0.55      # SCN-2/3 when MTF agrees
CONF_DIR_OPPOSED = 0.45    # SCN-2/3 when MTF splits
CONF_DIR_INSUFFICIENT = 0.40  # SCN-2/3 with insufficient MTF data
CONF_RECOMMENDATION = 0.50
SCENARIO_CONF_MIN = 0.35   # documented humility bounds (SCN-*)
SCENARIO_CONF_MAX = 0.65

_TF_SECONDS = {"1d": 86400, "1h": 3600, "1w": 604800, "4h": 14400, "15m": 900, "30m": 1800}
_TF_TAG = {"1d": "d1", "1w": "w1", "1h": "h1"}

FORBIDDEN_TERMS_EN = ("target price", "guarantee", "guaranteed")
FORBIDDEN_TERMS_FA = ("قطعی", "تضمین")

_TRUST_WORST_FIRST = ("MISSING", "STALE", "DELAYED", "SYNTHETIC", "PAPER", "REAL_UNVERIFIED", "REAL_VERIFIED")

_FA_DIR = {"BULLISH": "صعودی", "BEARISH": "نزولی", "FLAT": "بی‌جهت"}


class ClaimKind(str, Enum):
    """Claim taxonomy per MASTER-RADAR directive §F."""

    OBSERVED_FACT = "OBSERVED_FACT"
    CALCULATED_METRIC = "CALCULATED_METRIC"
    MODEL_INTERPRETATION = "MODEL_INTERPRETATION"
    SCENARIO = "SCENARIO"
    RECOMMENDATION = "RECOMMENDATION"


class TrustClass(str, Enum):
    """Trust taxonomy per directive §F."""

    REAL_VERIFIED = "REAL_VERIFIED"
    REAL_UNVERIFIED = "REAL_UNVERIFIED"
    DELAYED = "DELAYED"
    SYNTHETIC = "SYNTHETIC"
    PAPER = "PAPER"
    STALE = "STALE"
    MISSING = "MISSING"


class ClaimProvenance(BaseModel, frozen=True):
    """Full provenance attached to every claim (directive §F).

    ``confidence`` is set ONLY on MODEL_INTERPRETATION / SCENARIO /
    RECOMMENDATION claims; OBSERVED_FACT and CALCULATED_METRIC are
    deterministic and carry confidence=None.
    """

    source_class: str
    as_of_ts: int
    freshness_bars: int | None = None
    timeframe: str = "1d"
    evidence_ref: str
    trust_class: TrustClass
    calculation_ref: str | None = None
    confidence: float | None = None
    conflict_with: list[str] = Field(default_factory=list)


class Claim(BaseModel, frozen=True):
    """A single provenanced, bilingual (EN + FA) statement."""

    claim_id: str
    kind: ClaimKind
    text_en: str
    text_fa: str
    timeframe: str
    provenance: ClaimProvenance


class SeriesInput(BaseModel, frozen=True):
    """One OHLCV series with explicit availability / trust metadata."""

    bars: list[dict] = Field(default_factory=list)
    timeframe: str = "1d"
    trust_class: TrustClass = TrustClass.MISSING
    source_class: str = "UNSPECIFIED"
    stale: bool = False


class FundamentalsSection(BaseModel, frozen=True):
    """Fundamental dossier section; rows carry their own trust metadata."""

    available: bool = False
    rows: list[dict] = Field(default_factory=list)  # {field,value,as_of_ts,source_class,trust_class}
    unavailable_reason: str | None = None


class StrategySignalContext(BaseModel, frozen=True):
    """Strategy-signal context; signals carry {strategy_id,side,score,ts}."""

    available: bool = False
    signals: list[dict] = Field(default_factory=list)
    unavailable_reason: str | None = None


class AnalystInput(BaseModel, frozen=True):
    """Full analyst input; EVERY input declares its own availability (§F)."""

    symbol: str
    name_fa: str = ""
    as_of_ts: int
    daily: SeriesInput = Field(default_factory=SeriesInput)
    weekly: SeriesInput = Field(default_factory=lambda: SeriesInput(timeframe="1w"))
    hourly: SeriesInput = Field(default_factory=lambda: SeriesInput(timeframe="1h"))
    fundamentals: FundamentalsSection = Field(default_factory=FundamentalsSection)
    sector_context: dict = Field(default_factory=lambda: {"available": False, "reason": "not_admitted"})
    strategy_signals: StrategySignalContext = Field(default_factory=StrategySignalContext)
    annotations: list[dict] = Field(default_factory=list)  # {kind,price,ts,note}


class ScenarioRecord(BaseModel, frozen=True):
    """One conditional scenario; ``direction`` is the slot, not a forecast."""

    direction: str  # "BULLISH" | "BASE" | "BEARISH"
    claim_id: str
    key_level: float | None = None
    invalidation_en: str
    invalidation_fa: str


class KeyLevel(BaseModel, frozen=True):
    """A structural / indicator level with a pointer back to claim evidence."""

    price: float
    kind: str
    evidence_ref: str
    ts: int


class RiskFactor(BaseModel, frozen=True):
    """Deterministic risk factor (RISK-1 mapping)."""

    code: str
    text_en: str
    text_fa: str


class MissingDataEntry(BaseModel, frozen=True):
    """One unavailable / degraded input (MISS-1 honesty ledger)."""

    item: str
    reason: str
    trust_class: TrustClass


class SymbolAnalysisReport(BaseModel, frozen=True):
    """Deterministic, fully provenanced per-symbol analysis report.

    ``report_digest`` is the sha256 of the canonical JSON of every field
    except the digest itself; same input -> same digest.
    """

    symbol: str
    name_fa: str = ""
    as_of_ts: int
    engine_version: str = ENGINE_VERSION
    claims: list[Claim] = Field(default_factory=list)
    executive_summary_en: str = ""
    executive_summary_fa: str = ""
    scenarios: list[ScenarioRecord] = Field(default_factory=list)
    key_levels: list[KeyLevel] = Field(default_factory=list)
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    missing_data: list[MissingDataEntry] = Field(default_factory=list)
    mtf_agreement: dict = Field(default_factory=dict)
    uncertainty_count: int = 0
    uncertainty_note_en: str = ""
    uncertainty_note_fa: str = ""
    report_digest: str = ""
    generated_by: str = GENERATED_BY


# ---------------------------------------------------------------------------
# small local math helpers (kept local to avoid further coupling)
# ---------------------------------------------------------------------------

def _ema(values: list[float], period: int) -> list[float]:
    """SMA-seeded EMA (same convention as app.engines.indicators._ema_series)."""
    n = len(values)
    if n == 0 or period <= 0:
        return []
    seed = values[: min(period, n)]
    out = [sum(seed) / len(seed)] * len(seed)
    if n <= period:
        return out
    k = 2 / (period + 1)
    prev = out[-1]
    for v in values[period:]:
        prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def _rsi_wilder(closes: list[float], period: int = 14) -> list[float]:
    """Wilder RSI(14): seed = simple mean of the first 14 changes at index 14,
    Wilder smoothing afterwards, 0.0 before index 14 (documented edge: a seed
    window with no movement reads 50.0)."""
    n = len(closes)
    out = [0.0] * n
    if n <= period:
        return out
    first = closes[1 : period + 1]
    avg_gain = sum(max(c - p, 0.0) for c, p in zip(first, closes[:period])) / period
    avg_loss = sum(max(p - c, 0.0) for c, p in zip(first, closes[:period])) / period

    def _rsi(g: float, l: float) -> float:
        if l == 0:
            return 100.0 if g > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + g / l)

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period + 1, n):
        delta = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period
        out[i] = _rsi(avg_gain, avg_loss)
    return out


def _percentile_rank(values: list[float], reference: float) -> float:
    """Share of ``values`` <= ``reference`` (own-history rank, VOL-1)."""
    if not values:
        return 0.0
    return sum(1 for v in values if v <= reference) / len(values)


def _last_pivot(bars: list[dict], side: str) -> dict | None:
    """STRUCT-1: most recent confirmed +/-3-window pivot (high or low side).

    Returns {"ts", "price", "index"} or None when no confirmed pivot exists.
    """
    n = len(bars)
    if n < 7:
        return None
    vals = [float(b["h" if side == "high" else "l"]) for b in bars]
    extreme = max if side == "high" else min
    for i in range(n - 4, 2, -1):
        if vals[i] == extreme(vals[i - 3 : i + 4]):
            return {"ts": int(bars[i]["ts"]), "price": vals[i], "index": i}
    return None


def _to_indicator_bars(bars: list[dict]) -> list[dict]:
    """Adapter: shared contract bars -> app.engines.indicators bar dicts."""
    return [
        {"time": b["ts"], "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"], "volume": b.get("v", 0.0)}
        for b in bars
    ]


def _fmt(value: Any, nd: int = 2) -> str:
    """Deterministic number formatting for claim texts."""
    try:
        return f"{float(value):.{nd}f}"
    except (TypeError, ValueError):
        return str(value)


def _tf_tag(timeframe: str) -> str:
    return _TF_TAG.get(timeframe, timeframe)


def _freshness_bars(bars: list[dict], timeframe: str, as_of_ts: int) -> int | None:
    """Bars of lag between as_of and the last bar (None when unknowable)."""
    if not bars:
        return None
    seconds = _TF_SECONDS.get(timeframe)
    if seconds is None:
        return None
    return int(max(0, as_of_ts - int(bars[-1]["ts"])) // seconds)


def _coerce_trust(value: Any) -> TrustClass:
    """Coerce an externally supplied trust marker to the enum, fail honest."""
    try:
        return TrustClass(str(value))
    except ValueError:
        return TrustClass.REAL_UNVERIFIED


def _worst_trust(trusts: list[TrustClass]) -> TrustClass:
    """Worst (least trusted) class among the provided ones."""
    if not trusts:
        return TrustClass.MISSING
    ranks = {name: rank for rank, name in enumerate(_TRUST_WORST_FIRST)}
    return TrustClass(min(trusts, key=lambda t: ranks.get(t.value, len(_TRUST_WORST_FIRST))).value)


def _volume_ratio(bars: list[dict]) -> float | None:
    """LIQ-1 ratio; None when the last 20 volumes are absent or non-positive."""
    if len(bars) < 20:
        return None
    vols = [float(b.get("v") or 0.0) for b in bars[-20:]]
    if any(v <= 0 for v in vols):
        return None
    avg = sum(vols) / 20.0
    return vols[-1] / avg if avg > 0 else None


class _ClaimBuilder:
    """Collects claim drafts in fixed order; assigns deterministic ids c001.."""

    def __init__(self, as_of_ts: int) -> None:
        self._as_of = as_of_ts
        self._items: list[dict] = []

    def add(
        self,
        kind: ClaimKind,
        evidence_ref: str,
        trust_class: TrustClass,
        text_en: str,
        text_fa: str,
        timeframe: str,
        source_class: str,
        calculation_ref: str | None = None,
        confidence: float | None = None,
        conflict_with: list[str] | None = None,
        freshness_bars: int | None = None,
    ) -> str:
        """Append a claim draft; returns the deterministic id it will get."""
        self._items.append(
            {
                "kind": kind,
                "text_en": text_en,
                "text_fa": text_fa,
                "timeframe": timeframe,
                "prov": {
                    "source_class": source_class,
                    "as_of_ts": self._as_of,
                    "freshness_bars": freshness_bars,
                    "timeframe": timeframe,
                    "evidence_ref": evidence_ref,
                    "trust_class": trust_class,
                    "calculation_ref": calculation_ref,
                    "confidence": confidence,
                    "conflict_with": list(conflict_with or []),
                },
            }
        )
        return f"c{len(self._items):03d}"

    def finalize(self) -> list[Claim]:
        claims: list[Claim] = []
        for idx, item in enumerate(self._items, start=1):
            claims.append(
                Claim(
                    claim_id=f"c{idx:03d}",
                    kind=item["kind"],
                    text_en=item["text_en"],
                    text_fa=item["text_fa"],
                    timeframe=item["timeframe"],
                    provenance=ClaimProvenance(**item["prov"]),
                )
            )
        return claims


# ---------------------------------------------------------------------------
# per-timeframe deterministic analysis
# ---------------------------------------------------------------------------

def _analyze_series(series: SeriesInput, inp: AnalystInput, tag: str, builder: _ClaimBuilder,
                    missing: list[MissingDataEntry]) -> dict:
    """Deterministic single-timeframe analysis; returns the facts ledger."""
    tf = series.timeframe
    bars = series.bars
    facts: dict = {"analyzed": False, "direction": None, "timeframe": tf}
    if len(bars) < MIN_BARS:
        builder.add(
            ClaimKind.OBSERVED_FACT, f"availability.{tag}", TrustClass.MISSING,
            f"{tf} series unavailable for analysis: {len(bars)} bars provided (minimum {MIN_BARS} required); "
            f"no {tf} claims are made.",
            f"داده {tf} برای تحلیل کافی نیست: {len(bars)} کندل ارائه شده (حداقل {MIN_BARS} کندل لازم است)؛ "
            f"هیچ گزاره‌ای برای {tf} ساخته نمی‌شود.",
            tf, series.source_class,
        )
        missing.append(MissingDataEntry(item=f"series_{tag}",
                                        reason=f"fewer than {MIN_BARS} bars provided ({len(bars)})",
                                        trust_class=TrustClass.MISSING))
        return facts

    fresh = _freshness_bars(bars, tf, inp.as_of_ts)
    if series.stale:
        builder.add(
            ClaimKind.OBSERVED_FACT, f"availability.stale.{tag}", TrustClass.STALE,
            f"{tf} series is flagged stale by upstream (freshness about {fresh} bars).",
            f"سری {tf} به‌عنوان مندرس علامت خورده است (تازگی حدود {fresh} کندل).",
            tf, series.source_class, freshness_bars=fresh,
        )
        missing.append(MissingDataEntry(item=f"series_{tag}_freshness",
                                        reason="series flagged stale by upstream",
                                        trust_class=TrustClass.STALE))
    facts.update(analyzed=True, stale=bool(series.stale), freshness_bars=fresh,
                 source_class=series.source_class, trust_class=series.trust_class)
    src, trust = series.source_class, series.trust_class
    closes = [float(b["c"]) for b in bars]
    ind_bars = _to_indicator_bars(bars)

    # TREND-1: EMA20/EMA50 arrangement + 5-value EMA20 slope
    ema20, ema50 = _ema(closes, 20), _ema(closes, 50)
    e20, e50 = ema20[-1], ema50[-1]
    slope_vals = ema20[-5:]
    slope_en, slope_fa = (("positive", "مثبت") if slope_vals[-1] > slope_vals[0]
                          else ("negative", "منفی") if slope_vals[-1] < slope_vals[0]
                          else ("unchanged", "بدون تغییر"))
    if e20 > e50:
        direction = "BULLISH"
    elif e20 < e50:
        direction = "BEARISH"
    else:
        direction = "FLAT"
    facts.update(direction=direction, ema20=e20, ema50=e50, ema_ts=int(bars[-1]["ts"]))
    rel_en = {"BULLISH": "above", "BEARISH": "below", "FLAT": "equal to"}[direction]
    builder.add(
        ClaimKind.CALCULATED_METRIC, f"trend.ema_values.{tag}", trust,
        f"{tf} EMA20 last value {e20:.2f}; EMA50 last value {e50:.2f}; "
        f"EMA20 slope across the last five values is {slope_en}.",
        f"آخرین مقدار EMA20 در {tf} برابر {e20:.2f} و آخرین مقدار EMA50 برابر {e50:.2f} است؛ "
        f"شیب EMA20 در پنج مقدار آخر {slope_fa} است.",
        tf, src, calculation_ref="local.ema_sma_seed(20|50)", freshness_bars=fresh,
    )
    builder.add(
        ClaimKind.MODEL_INTERPRETATION, f"trend.ema_arrangement.{tag}", trust,
        f"{tf} trend read as {direction.lower()} per rule TREND-1 (EMA20 {rel_en} EMA50).",
        f"بر پایه قاعده TREND-1 روند {tf} {_FA_DIR[direction]} خوانده می‌شود (موقعیت EMA20 نسبت به EMA50).",
        tf, src, confidence=CONF_TREND, freshness_bars=fresh,
    )

    # STRUCT-1: confirmed swing pivots
    for side, fa_word in (("high", "سقف"), ("low", "کف")):
        pivot = _last_pivot(bars, side)
        facts[f"swing_{side}"] = pivot
        if pivot is not None:
            builder.add(
                ClaimKind.CALCULATED_METRIC, f"structure.swing_{side}.{tag}", trust,
                f"Most recent confirmed {tf} swing {side} is {pivot['price']:.2f} "
                f"(bar ts {pivot['ts']}, +/-3-bar window, rule STRUCT-1).",
                f"آخرین {fa_word} سوئینگ تأییدشده در {tf} برابر {pivot['price']:.2f} است "
                f"(زمان کندل {pivot['ts']}، پنجره همسایگی سه‌کندلی، قاعده STRUCT-1).",
                tf, src, calculation_ref="local.pivot_window(±3)", freshness_bars=fresh,
            )
        else:
            builder.add(
                ClaimKind.OBSERVED_FACT, f"structure.swing_{side}.{tag}", TrustClass.MISSING,
                f"No confirmed {tf} swing {side} found within the analyzed window (rule STRUCT-1).",
                f"در بازه بررسی، {fa_word} سوئینگ تأییدشده‌ای در {tf} یافت نشد (قاعده STRUCT-1).",
                tf, src, freshness_bars=fresh,
            )
            missing.append(MissingDataEntry(item=f"swing_{side}_{tag}",
                                            reason="no confirmed swing pivot within lookback",
                                            trust_class=TrustClass.MISSING))

    # VOL-1: ATR(14) + own-history percentile
    atr_series = indicators.atr(ind_bars, 14)
    if atr_series:
        atr_values = [float(d["value"]) for d in atr_series]
        atr_last = atr_values[-1]
        atr_pct = _percentile_rank(atr_values, atr_last)
        facts.update(atr_value=atr_last, atr_percentile=atr_pct)
        builder.add(
            ClaimKind.CALCULATED_METRIC, f"volatility.atr14.{tag}", trust,
            f"{tf} ATR(14) last value {atr_last:.2f}; own-history percentile rank {atr_pct:.2f}.",
            f"مقدار ATR(14) در {tf} برابر {atr_last:.2f} و صدک آن در تاریخچه خود {atr_pct:.2f} است.",
            tf, src, calculation_ref="app.engines.indicators.atr(14)+local.percentile_rank", freshness_bars=fresh,
        )
        vol_en, vol_fa = (("elevated", "بالا") if atr_pct >= 0.70
                          else ("compressed", "فشرده") if atr_pct <= 0.30 else ("normal", "معمول"))
        facts["volatility_word"] = vol_en
        builder.add(
            ClaimKind.MODEL_INTERPRETATION, f"volatility.reading.{tag}", trust,
            f"{tf} volatility read as {vol_en} per rule VOL-1 (percentile thresholds 0.70 / 0.30; "
            f"measured {atr_pct:.2f}).",
            f"بر پایه قاعده VOL-1 (آستانه‌های 0.70 و 0.30؛ مقدار اندازه‌گیری‌شده {atr_pct:.2f}) "
            f"نوسان {tf} {vol_fa} ارزیابی می‌شود.",
            tf, src, confidence=CONF_READING, freshness_bars=fresh,
        )
    else:
        facts["atr_percentile"] = None
        missing.append(MissingDataEntry(item=f"atr_{tag}", reason="ATR(14) not computable on this series",
                                        trust_class=TrustClass.MISSING))

    # LIQ-1: volume vs SMA20
    ratio = _volume_ratio(bars)
    facts["volume_ratio"] = ratio
    if ratio is None:
        builder.add(
            ClaimKind.OBSERVED_FACT, f"volume.sma20_ratio.{tag}", TrustClass.MISSING,
            f"{tf} volume read unavailable: last 20 volume values are absent or non-positive; "
            "no volume-average ratio is computed.",
            f"خوانش حجم در {tf} در دسترس نیست: بیست مقدار آخر حجم ناموجود یا صفر است؛ "
            "نسبت حجم به میانگین محاسبه نشد.",
            tf, src, freshness_bars=fresh,
        )
        missing.append(MissingDataEntry(item=f"volume_ratio_{tag}",
                                        reason="volume values absent or non-positive in last 20 bars",
                                        trust_class=TrustClass.MISSING))
    else:
        liq_en, liq_fa = (("above average", "بالاتر از میانگین") if ratio >= 1.5
                          else ("below average", "پایین‌تر از میانگین") if ratio <= 0.5
                          else ("near average", "نزدیک میانگین"))
        facts["liquidity_word"] = liq_en
        builder.add(
            ClaimKind.CALCULATED_METRIC, f"volume.sma20_ratio.{tag}", trust,
            f"{tf} last-bar volume is {ratio:.2f}x its 20-bar average (rule LIQ-1, {liq_en}).",
            f"حجم آخرین کندل {tf} برابر {ratio:.2f} برابر میانگین بیست‌کندله است (قاعده LIQ-1؛ {liq_fa}).",
            tf, src, calculation_ref="local.sma20(volume) ratio", freshness_bars=fresh,
        )

    # MOM-1: local Wilder RSI(14)
    rsi_series = _rsi_wilder(closes, 14)
    rsi_last = rsi_series[-1] if len(rsi_series) == len(closes) else None
    facts["rsi14"] = rsi_last
    if rsi_last is not None:
        builder.add(
            ClaimKind.CALCULATED_METRIC, f"momentum.rsi14.{tag}", trust,
            f"{tf} RSI(14) last value {rsi_last:.1f} (Wilder definition, seed at index 14).",
            f"مقدار RSI(14) در {tf} برابر {rsi_last:.1f} است (تعریف وایلدر، بذر در کندل 14).",
            tf, src, calculation_ref="local.rsi_wilder(14)", freshness_bars=fresh,
        )
        mom_en, mom_fa = (("strong positive", "به‌شدت مثبت") if rsi_last > 70
                          else ("positive", "مثبت") if rsi_last > 50
                          else ("strong negative", "به‌شدت منفی") if rsi_last < 30
                          else ("negative", "منفی") if rsi_last < 50 else ("neutral", "خنثی"))
        facts["momentum_word"] = mom_en
        builder.add(
            ClaimKind.MODEL_INTERPRETATION, f"momentum.rsi_reading.{tag}", trust,
            f"{tf} momentum read as {mom_en} per rule MOM-1 (RSI(14) = {rsi_last:.1f}).",
            f"بر پایه قاعده MOM-1 مومنتوم {tf} {mom_fa} ارزیابی می‌شود (RSI(14) برابر {rsi_last:.1f}).",
            tf, src, confidence=CONF_READING, freshness_bars=fresh,
        )

    # MOM-2: MACD histogram sign
    hist = (indicators.macd(ind_bars).get("histogram") or [])
    if hist:
        hist_last = float(hist[-1]["value"])
        sign_en = "positive" if hist_last > 0 else "negative" if hist_last < 0 else "zero"
        sign_fa = {"positive": "مثبت", "negative": "منفی", "zero": "صفر"}[sign_en]
        facts["macd_hist"] = hist_last
        builder.add(
            ClaimKind.CALCULATED_METRIC, f"momentum.macd.{tag}", trust,
            f"{tf} MACD(12,26,9) histogram last value {hist_last:.4f} (sign: {sign_en}).",
            f"آخرین مقدار هیستوگرام MACD(12،26،9) در {tf} برابر {hist_last:.4f} است (علامت: {sign_fa}).",
            tf, src, calculation_ref="app.engines.indicators.macd(12,26,9).histogram", freshness_bars=fresh,
        )

    # BB-1: Bollinger position
    bb = indicators.bollinger(ind_bars, 20, 2.0)
    upper, lower = bb.get("upper") or [], bb.get("lower") or []
    if upper and lower:
        up_last, lo_last, c_last = float(upper[-1]["value"]), float(lower[-1]["value"]), closes[-1]
        pos_en = ("above the upper band" if c_last > up_last
                  else "below the lower band" if c_last < lo_last else "within the bands")
        pos_fa = {"above the upper band": "بالای باند بالایی", "below the lower band": "زیر باند پایینی",
                  "within the bands": "داخل باندهای"}[pos_en]
        facts["bb_position"] = pos_en
        builder.add(
            ClaimKind.CALCULATED_METRIC, f"bollinger.position.{tag}", trust,
            f"{tf} last close {c_last:.2f} is {pos_en} of Bollinger (20, 2) "
            f"[lower {lo_last:.2f}, upper {up_last:.2f}] (rule BB-1).",
            f"آخرین قیمت بسته‌شده {tf} برابر {c_last:.2f} است و {pos_fa} بولینگر (20، 2) قرار دارد "
            f"[کف {lo_last:.2f}، سقف {up_last:.2f}] (قاعده BB-1).",
            tf, src, calculation_ref="app.engines.indicators.bollinger(20,2)", freshness_bars=fresh,
        )
    return facts


# ---------------------------------------------------------------------------
# scenarios (SCN-1/2/3): derived ONLY from computed levels
# ---------------------------------------------------------------------------

def _scenario_confidence(agreement: str) -> float:
    """Deterministic, humility-bounded scenario confidence (0.35..0.65)."""
    return (CONF_DIR_AGREE if agreement == "AGREE"
            else CONF_DIR_INSUFFICIENT if agreement == "INSUFFICIENT_DATA"
            else CONF_DIR_OPPOSED)


def _build_scenarios(inp: AnalystInput, facts_by_tag: dict, agreement: str, dominant: str | None,
                     builder: _ClaimBuilder) -> list[ScenarioRecord]:
    """Build base/bullish/bearish scenarios from computed levels only."""
    daily = facts_by_tag["d1"]
    trust = daily.get("trust_class") if daily.get("analyzed") else None
    src_trust = trust if trust is not None else TrustClass.MISSING
    swing_high = daily.get("swing_high") if daily.get("analyzed") else None
    swing_low = daily.get("swing_low") if daily.get("analyzed") else None
    sh = swing_high["price"] if swing_high else None
    sl = swing_low["price"] if swing_low else None
    conf = _scenario_confidence(agreement)
    scenarios: list[ScenarioRecord] = []

    # SCN-1 base case: continuation of the dominant MTF reading
    if dominant is not None:
        dom_en, dom_fa = dominant.lower(), _FA_DIR.get(dominant, dominant)
        e50 = daily.get("ema50")
        if dominant == "BULLISH":
            inv_en = (f"Base case invalidated if the daily close is below EMA50 ({e50:.2f}) "
                      "for 2 consecutive daily bars.") if e50 is not None else \
                "Base case invalidated when the dominant multi-timeframe reading flips on a daily close."
            inv_fa = (f"سناریوی پایه باطل می‌شود اگر دو کندل روزانه متوالی زیر EMA50 ({e50:.2f}) بسته شود.") \
                if e50 is not None else \
                "سناریوی پایه با تغییر خوانش غالب چندزمانی در یک بسته‌شدن روزانه باطل می‌شود."
        elif dominant == "BEARISH":
            inv_en = (f"Base case invalidated if the daily close is above EMA50 ({e50:.2f}) "
                      "for 2 consecutive daily bars.") if e50 is not None else \
                "Base case invalidated when the dominant multi-timeframe reading flips on a daily close."
            inv_fa = (f"سناریوی پایه باطل می‌شود اگر دو کندل روزانه متوالی بالای EMA50 ({e50:.2f}) بسته شود.") \
                if e50 is not None else \
                "سناریوی پایه با تغییر خوانش غالب چندزمانی در یک بسته‌شدن روزانه باطل می‌شود."
        else:
            inv_en = "Base case invalidated when the daily EMA20/EMA50 arrangement leaves the equal state."
            inv_fa = "سناریوی پایه با خروج چیدمان EMA20/EMA50 روزانه از حالت برابری باطل می‌شود."
        cid = builder.add(
            ClaimKind.SCENARIO, "scenario.base", src_trust,
            f"Base case: continuation of the dominant multi-timeframe reading ({dom_en}). "
            "Conditional scenario, not a forecast.",
            f"سناریوی پایه: تداوم خوانش غالب چندزمانی ({dom_fa}). سناریوی شرطی است و پیش‌بینی نیست.",
            "1d", "ANALYST_SYNTHESIS", confidence=CONF_BASE,
        )
        scenarios.append(ScenarioRecord(direction="BASE", claim_id=cid, key_level=None,
                                        invalidation_en=inv_en, invalidation_fa=inv_fa))
    else:
        cid = builder.add(
            ClaimKind.SCENARIO, "scenario.base", TrustClass.MISSING,
            "Base case: no dominant multi-timeframe reading is available; neutral stance until a second "
            "timeframe series becomes analyzable. Conditional scenario, not a forecast.",
            "سناریوی پایه: خوانش غالب چندزمانی در دسترس نیست؛ موضع خنثی تا آماده شدن سری زمانی دوم. "
            "سناریوی شرطی است و پیش‌بینی نیست.",
            "1d", "ANALYST_SYNTHESIS", confidence=CONF_DIR_INSUFFICIENT,
        )
        scenarios.append(ScenarioRecord(
            direction="BASE", claim_id=cid, key_level=None,
            invalidation_en="Base case is re-evaluated as soon as a second timeframe series becomes analyzable.",
            invalidation_fa="سناریوی پایه به‌محض آماده شدن سری زمانی دوم دوباره ارزیابی می‌شود."))

    # SCN-2 bullish break above confirmed daily swing high
    sh_txt_en = f" at {sh:.2f}" if sh is not None else ""
    sh_txt_fa = f" در محدوده {sh:.2f}" if sh is not None else ""
    inv_sl_en = (f"Scenario invalidated if the daily close is below the confirmed swing low {sl:.2f} "
                 "for 2 consecutive daily bars.") if sl is not None else \
        "Scenario invalidated if the daily close is below the most recent confirmed daily swing low " \
        "for 2 consecutive daily bars."
    inv_sl_fa = (f"سناریو باطل می‌شود اگر دو کندل روزانه متوالی زیر کف سوئینگ تأییدشده {sl:.2f} بسته شود.") \
        if sl is not None else \
        "سناریو باطل می‌شود اگر دو کندل روزانه متوالی زیر آخرین کف سوئینگ تأییدشده بسته شود."
    cid = builder.add(
        ClaimKind.SCENARIO, "scenario.bullish", src_trust,
        f"Bullish scenario (conditional): a daily close above the confirmed swing-high resistance{sh_txt_en} "
        "would open an upside continuation case. This requires confirmation and is not a forecast.",
        f"سناریوی صعودی (شرطی): بسته‌شدن روزانه بالای مقاومت سقف سوئینگ تأییدشده{sh_txt_fa} "
        "فرض تداوم رشد را فعال می‌کند. این سناریو نیازمند تأیید است و پیش‌بینی نیست.",
        "1d", "ANALYST_SYNTHESIS", confidence=conf,
        conflict_with=["mtf.agreement"] if dominant == "BEARISH" else None,
    )
    scenarios.append(ScenarioRecord(direction="BULLISH", claim_id=cid, key_level=sh,
                                    invalidation_en=inv_sl_en, invalidation_fa=inv_sl_fa))

    # SCN-3 bearish break below confirmed daily swing low
    sl_txt_en = f" at {sl:.2f}" if sl is not None else ""
    sl_txt_fa = f" در محدوده {sl:.2f}" if sl is not None else ""
    inv_sh_en = (f"Scenario invalidated if the daily close is above the confirmed swing high {sh:.2f} "
                 "for 2 consecutive daily bars.") if sh is not None else \
        "Scenario invalidated if the daily close is above the most recent confirmed daily swing high " \
        "for 2 consecutive daily bars."
    inv_sh_fa = (f"سناریو باطل می‌شود اگر دو کندل روزانه متوالی بالای سقف سوئینگ تأییدشده {sh:.2f} بسته شود.") \
        if sh is not None else \
        "سناریو باطل می‌شود اگر دو کندل روزانه متوالی بالای آخرین سقف سوئینگ تأییدشده بسته شود."
    cid = builder.add(
        ClaimKind.SCENARIO, "scenario.bearish", src_trust,
        f"Bearish scenario (conditional): a daily close below the confirmed swing-low support{sl_txt_en} "
        "would open a downside continuation case. This requires confirmation and is not a forecast.",
        f"سناریوی نزولی (شرطی): بسته‌شدن روزانه زیر حمایت کف سوئینگ تأییدشده{sl_txt_fa} "
        "فرض تداوم افت را فعال می‌کند. این سناریو نیازمند تأیید است و پیش‌بینی نیست.",
        "1d", "ANALYST_SYNTHESIS", confidence=conf,
        conflict_with=["mtf.agreement"] if dominant == "BULLISH" else None,
    )
    scenarios.append(ScenarioRecord(direction="BEARISH", claim_id=cid, key_level=sl,
                                    invalidation_en=inv_sh_en, invalidation_fa=inv_sh_fa))
    return scenarios


# ---------------------------------------------------------------------------
# deterministic risk factors (RISK-1)
# ---------------------------------------------------------------------------

def _risk_factors(facts_by_tag: dict, agreement: str, inp: AnalystInput,
                  fundamentals_available: bool) -> list[RiskFactor]:
    """RISK-1 mapping; order is fixed for determinism."""
    out: list[RiskFactor] = []
    daily = facts_by_tag["d1"]
    atr_pct = daily.get("atr_percentile")
    if daily.get("analyzed") and atr_pct is not None and atr_pct >= 0.70:
        out.append(RiskFactor(
            code="VOL_RISK",
            text_en=f"Elevated volatility: daily ATR(14) own-history percentile {atr_pct:.2f} (>= 0.70).",
            text_fa=f"نوسان بالاست: صدک ATR(14) روزانه در تاریخچه خود {atr_pct:.2f} است (0.70 یا بیشتر)."))
    if any(s.stale or s.trust_class == TrustClass.STALE for s in (inp.daily, inp.weekly, inp.hourly) if s.bars):
        out.append(RiskFactor(
            code="DATA_RISK",
            text_en="One or more input series are flagged stale; readings may lag the market.",
            text_fa="یک یا چند سری ورودی مندرس علامت خورده است؛ خوانش‌ها ممکن است از بازار عقب باشند."))
    vol_ratio = daily.get("volume_ratio") if daily.get("analyzed") else None
    if vol_ratio is None or vol_ratio < 0.5:
        out.append(RiskFactor(
            code="LIQ_RISK",
            text_en="Liquidity read unavailable or weak: daily volume ratio missing or below 0.5x average.",
            text_fa="خوانش نقدشوندگی در دسترس نیست یا ضعیف است: نسبت حجم روزانه ناموجود یا زیر 0.5 برابر میانگین است."))
    if not fundamentals_available:
        out.append(RiskFactor(
            code="INFO_RISK",
            text_en="Fundamentals section unavailable; the information set is incomplete.",
            text_fa="بخش بنیادی در دسترس نیست؛ مجموعه اطلاعات ناقص است."))
    if agreement == "DISAGREE":
        out.append(RiskFactor(
            code="REGIME_RISK",
            text_en="Multi-timeframe trend readings disagree; the regime reading is unstable.",
            text_fa="خوانش روند در بازه‌های زمانی ناهم‌جهت است؛ رژیم بازار ناپایدار ارزیابی می‌شود."))
    return out


# ---------------------------------------------------------------------------
# forbidden-content self-scan (directive §F, ABSOLUTE)
# ---------------------------------------------------------------------------

def forbidden_terms_scan(report: SymbolAnalysisReport) -> list[str]:
    """Scan every text field of the report for banned strings.

    Returns findings as "path: banned term '...'" entries; an empty list
    means the report is clean. English terms match case-insensitively,
    Persian terms exactly. Banned: "target price", "guarantee(d)",
    "قطعی", "تضمین".
    """
    findings: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                walk(value, f"{path}[{idx}]")
        elif isinstance(node, str):
            lowered = node.lower()
            findings.extend(f"{path}: banned term '{t}'" for t in FORBIDDEN_TERMS_EN if t in lowered)
            findings.extend(f"{path}: banned term '{t}'" for t in FORBIDDEN_TERMS_FA if t in node)

    walk(report.model_dump(mode="json"), "report")
    return findings


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------

def analyze_symbol(inp: AnalystInput) -> SymbolAnalysisReport:
    """Build the deterministic, fully provenanced analysis report.

    Pure function of ``inp``: same input -> identical digest. No I/O, no
    clock access, no AI-provider calls. Fail-closed on banned content.
    """
    builder = _ClaimBuilder(inp.as_of_ts)
    missing: list[MissingDataEntry] = []
    facts_by_tag: dict = {}

    # 1) per-timeframe analysis (MISS-1 honesty first)
    for tf in ("1d", "1w", "1h"):
        series = getattr(inp, {"1d": "daily", "1w": "weekly", "1h": "hourly"}[tf])
        facts_by_tag[_tf_tag(tf)] = _analyze_series(series, inp, _tf_tag(tf), builder, missing)

    # 2) MTF synthesis (MTF-1)
    directions = {tf: facts_by_tag[_tf_tag(tf)]["direction"] for tf in ("1d", "1w", "1h")
                  if facts_by_tag[_tf_tag(tf)]["analyzed"]}
    analyzed_trusts = [facts_by_tag[tag]["trust_class"] for tag in ("d1", "w1", "h1")
                       if facts_by_tag[tag]["analyzed"] and facts_by_tag[tag].get("trust_class")]
    mtf_trust = _worst_trust(analyzed_trusts)

    def _mtf_prov(conf: float | None = None, conflict: list[str] | None = None) -> dict:
        return {"source_class": "ANALYST_SYNTHESIS", "as_of_ts": inp.as_of_ts, "timeframe": "multi",
                "evidence_ref": "mtf.agreement", "trust_class": mtf_trust,
                "confidence": conf, "conflict_with": list(conflict or [])}

    vals = list(directions.values())
    if len(vals) < 2:
        agreement = "INSUFFICIENT_DATA"
        builder.add(
            ClaimKind.OBSERVED_FACT, "mtf.agreement", mtf_trust,
            f"Multi-timeframe synthesis needs at least two analyzed timeframes; {len(vals)} available "
            f"({', '.join(sorted(directions)) or 'none'}).",
            f"ترکیب چندزمانی به دست‌کم دو تایم‌فریم تحلیل‌شده نیاز دارد؛ {len(vals)} تایم‌فریم "
            f"در دسترس است ({'، '.join(sorted(directions)) or 'هیچ'}).",
            "multi", "ANALYST_SYNTHESIS",
        )
    elif len(set(vals)) == 1:
        agreement = "AGREE"
        builder.add(
            ClaimKind.MODEL_INTERPRETATION, "mtf.agreement", mtf_trust,
            f"Multi-timeframe trend readings agree ({vals[0].lower()}) across "
            f"{', '.join(sorted(directions))} (rule MTF-1).",
            f"خوانش روند در تایم‌فریم‌های {'، '.join(sorted(directions))} هم‌جهت است "
            f"({_FA_DIR[vals[0]]}) (قاعده MTF-1).",
            "multi", "ANALYST_SYNTHESIS", confidence=CONF_MTF_AGREE,
        )
    elif "BULLISH" in vals and "BEARISH" in vals:
        agreement = "DISAGREE"
        base_dir = directions.get("1d") or vals[0]
        conflict = [f"trend.ema_arrangement.{_tf_tag(t)}" for t, d in sorted(directions.items()) if d != base_dir]
        reading_fa = "، ".join(f"{t}: {_FA_DIR.get(d, d)}" for t, d in sorted(directions.items()))
        builder.add(
            ClaimKind.MODEL_INTERPRETATION, "mtf.agreement", mtf_trust,
            f"Multi-timeframe trend readings disagree (rule MTF-1): "
            f"{', '.join(f'{t}={d.lower()}' for t, d in sorted(directions.items()))}; "
            "regime uncertainty is raised.",
            f"خوانش روند چندزمانی ناهم‌جهت است (قاعده MTF-1): {reading_fa}؛ ابهام رژیم بیشتر می‌شود.",
            "multi", "ANALYST_SYNTHESIS", confidence=CONF_MTF_DISAGREE, conflict_with=conflict,
        )
    else:
        agreement = "PARTIAL"
        builder.add(
            ClaimKind.MODEL_INTERPRETATION, "mtf.agreement", mtf_trust,
            f"Multi-timeframe trend readings are partially aligned (rule MTF-1): "
            f"{', '.join(f'{t}={d.lower()}' for t, d in sorted(directions.items()))}; "
            "no direct bullish/bearish opposition.",
            "خوانش روند چندزمانی نیمه‌هم‌جهت است (قاعده MTF-1)؛ تقابل مستقیم صعودی/نزولی وجود ندارد.",
            "multi", "ANALYST_SYNTHESIS", confidence=CONF_MTF_PARTIAL,
        )
    mtf_agreement = {"daily": directions.get("1d", "MISSING"), "weekly": directions.get("1w", "MISSING"),
                     "hourly": directions.get("1h", "MISSING"), "agreement": agreement}

    # dominant reading: daily priority on splits (documented in MTF-1)
    if agreement == "AGREE":
        dominant = vals[0]
    elif agreement == "DISAGREE":
        dominant = directions.get("1d", vals[0])
    elif agreement == "PARTIAL":
        dominant = next((d for d in (directions.get("1d"), directions.get("1w"), directions.get("1h"))
                         if d and d != "FLAT"), "FLAT")
    else:
        dominant = directions.get("1d")

    # 3) scenarios (SCN-1/2/3) — only from computed levels
    scenarios = _build_scenarios(inp, facts_by_tag, agreement, dominant, builder)

    # 4) fundamentals section (MISS-1 honesty)
    fundamentals_available = bool(inp.fundamentals.available)
    if fundamentals_available and inp.fundamentals.rows:
        for row in inp.fundamentals.rows:
            field = str(row.get("field", "unknown"))
            safe = re.sub(r"[^0-9A-Za-z_\u0600-\u06FF]", "_", field)
            builder.add(
                ClaimKind.OBSERVED_FACT, f"fundamentals.row.{safe}", _coerce_trust(row.get("trust_class")),
                f"Fundamental field '{field}' = {_fmt(row.get('value'))} "
                f"(as_of {row.get('as_of_ts')}, source {row.get('source_class')}).",
                f"شاخص بنیادی «{field}» برابر {_fmt(row.get('value'))} است "
                f"(تاریخ {row.get('as_of_ts')}، منبع {row.get('source_class')}).",
                "n/a", str(row.get("source_class", "FUNDAMENTAL_DOSSIER")),
            )
    elif fundamentals_available:
        builder.add(
            ClaimKind.OBSERVED_FACT, "fundamentals.rows", TrustClass.REAL_UNVERIFIED,
            "Fundamentals section is marked available but contains no rows.",
            "بخش بنیادی موجود علامت خورده اما هیچ سطری ندارد.",
            "n/a", "FUNDAMENTAL_DOSSIER",
        )
    else:
        reason = inp.fundamentals.unavailable_reason or "no reason recorded"
        builder.add(
            ClaimKind.OBSERVED_FACT, "fundamentals.availability", TrustClass.MISSING,
            f"Fundamentals section unavailable: {reason}. No fundamental claims are made.",
            f"بخش بنیادی در دسترس نیست: {reason}. هیچ گزاره بنیادی ساخته نمی‌شود.",
            "n/a", "FUNDAMENTAL_DOSSIER",
        )
        missing.append(MissingDataEntry(item="fundamentals", reason=reason, trust_class=TrustClass.MISSING))

    # 5) strategy signal context (MISS-1 honesty + decision-support rec)
    sig_ctx = inp.strategy_signals
    if sig_ctx.available and sig_ctx.signals:
        buys = sum(1 for s in sig_ctx.signals if str(s.get("side", "")).upper() == "BUY")
        sells = sum(1 for s in sig_ctx.signals if str(s.get("side", "")).upper() == "SELL")
        latest = sig_ctx.signals[0]
        for s in sig_ctx.signals[1:]:
            if (s.get("ts") or 0) >= (latest.get("ts") or 0):
                latest = s
        builder.add(
            ClaimKind.OBSERVED_FACT, "strategy.signals", TrustClass.REAL_UNVERIFIED,
            f"Strategy signal context holds {len(sig_ctx.signals)} signals (BUY: {buys}, SELL: {sells}).",
            f"زمینه سیگنال استراتژی شامل {len(sig_ctx.signals)} سیگنال است (خرید: {buys}، فروش: {sells}).",
            "n/a", "STRATEGY_SIGNALS",
        )
        builder.add(
            ClaimKind.OBSERVED_FACT, "strategy.latest", TrustClass.REAL_UNVERIFIED,
            f"Latest strategy signal: strategy {latest.get('strategy_id')}, side {latest.get('side')}, "
            f"score {_fmt(latest.get('score'))}, ts {latest.get('ts')}.",
            f"آخرین سیگنال استراتژی: استراتژی {latest.get('strategy_id')}، جهت {latest.get('side')}، "
            f"امتیاز {_fmt(latest.get('score'))}، زمان {latest.get('ts')}.",
            "n/a", "STRATEGY_SIGNALS",
        )
        builder.add(
            ClaimKind.RECOMMENDATION, "strategy.review", mtf_trust,
            "Review the strategy signal context and apply your own judgment before any decision; "
            "this is decision support, not an instruction.",
            "زمینه سیگنال‌های استراتژی را بررسی کنید و پیش از هر تصمیم قضاوت شخصی خود را اعمال کنید؛ "
            "این پشتیبانی تصمیم است و دستور عمل نیست.",
            "n/a", "ANALYST_SYNTHESIS", confidence=CONF_RECOMMENDATION,
        )
    else:
        reason = sig_ctx.unavailable_reason or "no reason recorded"
        builder.add(
            ClaimKind.OBSERVED_FACT, "strategy.availability", TrustClass.MISSING,
            f"Strategy signal context unavailable: {reason}. No strategy-signal claims are made.",
            f"زمینه سیگنال‌های استراتژی در دسترس نیست: {reason}. هیچ گزاره سیگنالی ساخته نمی‌شود.",
            "n/a", "STRATEGY_SIGNALS",
        )
        missing.append(MissingDataEntry(item="strategy_signals", reason=reason, trust_class=TrustClass.MISSING))

    # 6) user chart annotations (optional input; reported only when present)
    if inp.annotations:
        latest_ann = inp.annotations[0]
        for a in inp.annotations[1:]:
            if (a.get("ts") or 0) >= (latest_ann.get("ts") or 0):
                latest_ann = a
        builder.add(
            ClaimKind.OBSERVED_FACT, "annotations.user", TrustClass.REAL_UNVERIFIED,
            f"{len(inp.annotations)} user chart annotation(s) on record "
            f"(latest: kind {latest_ann.get('kind')}, price {_fmt(latest_ann.get('price'))}).",
            f"{len(inp.annotations)} یادداشت کاربر روی نمودار ثبت شده است "
            f"(آخرین: نوع {latest_ann.get('kind')}، قیمت {_fmt(latest_ann.get('price'))}).",
            "n/a", "USER_ANNOTATIONS",
        )

    # 7) sector context (MISS-1 honesty)
    if bool(inp.sector_context.get("available")):
        names = sorted(str(k) for k in inp.sector_context if k not in ("available", "reason"))
        builder.add(
            ClaimKind.OBSERVED_FACT, "sector.context", TrustClass.REAL_UNVERIFIED,
            f"Sector context admitted with {len(names)} field(s): {', '.join(names) or 'none'}.",
            f"زمینه بخش (سکتور) ارائه شده و شامل {len(names)} فیلد است: {', '.join(names) or 'هیچ'}.",
            "n/a", "SECTOR_CONTEXT",
        )
    else:
        reason = str(inp.sector_context.get("reason") or "no reason recorded")
        builder.add(
            ClaimKind.OBSERVED_FACT, "sector.availability", TrustClass.MISSING,
            f"Sector context unavailable: {reason}. No sector claims are made.",
            f"زمینه بخش (سکتور) در دسترس نیست: {reason}. هیچ گزاره سکتوری ساخته نمی‌شود.",
            "n/a", "SECTOR_CONTEXT",
        )
        missing.append(MissingDataEntry(item="sector_context", reason=reason, trust_class=TrustClass.MISSING))

    claims = builder.finalize()

    # 8) key levels (daily structure + daily EMAs); refs point at claim evidence
    key_levels: list[KeyLevel] = []
    daily = facts_by_tag["d1"]
    if daily["analyzed"]:
        if daily.get("swing_high"):
            key_levels.append(KeyLevel(price=float(daily["swing_high"]["price"]), kind="swing_high",
                                       evidence_ref="structure.swing_high.d1", ts=int(daily["swing_high"]["ts"])))
        if daily.get("swing_low"):
            key_levels.append(KeyLevel(price=float(daily["swing_low"]["price"]), kind="swing_low",
                                       evidence_ref="structure.swing_low.d1", ts=int(daily["swing_low"]["ts"])))
        key_levels.append(KeyLevel(price=float(daily["ema20"]), kind="ema20",
                                   evidence_ref="trend.ema_values.d1", ts=int(daily["ema_ts"])))
        key_levels.append(KeyLevel(price=float(daily["ema50"]), kind="ema50",
                                   evidence_ref="trend.ema_values.d1", ts=int(daily["ema_ts"])))

    # 9) risk factors (RISK-1) and 10) uncertainty ledger
    risk_factors = _risk_factors(facts_by_tag, agreement, inp, fundamentals_available)
    uncertainty_count = len(missing)
    uncertainty_note_en = (f"{uncertainty_count} input gap(s) or degraded input(s) on record; see the "
                           "missing-data ledger. Conclusions are limited accordingly.")
    uncertainty_note_fa = (f"{uncertainty_count} مورد شکاف یا افت کیفیت داده ثبت شده است؛ فهرست داده‌های "
                           "ناموجود را ببینید. نتیجه‌گیری‌ها متناسب محدود شده‌اند.")

    # 11) executive summary — composed ONLY from the computed facts above
    def _dir_word(direction: str | None) -> tuple[str, str]:
        return {"BULLISH": ("bullish", "صعودی"), "BEARISH": ("bearish", "نزولی"),
                "FLAT": ("flat", "بی‌جهت")}.get(direction or "", ("unavailable", "در دسترس نیست"))

    d_word, d_fa = _dir_word(directions.get("1d"))
    w_word, w_fa = _dir_word(directions.get("1w"))
    h_word, h_fa = _dir_word(directions.get("1h"))
    daily_f = facts_by_tag["d1"]
    if daily_f["analyzed"]:
        vol_word = daily_f.get("volatility_word", "unavailable")
        vol_fa = {"elevated": "بالا", "normal": "معمول", "compressed": "فشرده"}.get(vol_word, "نامشخص")
        rsi_txt = f"{daily_f['rsi14']:.1f}" if daily_f.get("rsi14") is not None else "n/a"
        liq_txt = (f"volume at {daily_f['volume_ratio']:.2f}x its 20-bar average"
                   if daily_f.get("volume_ratio") is not None else "volume read unavailable")
        liq_fa = (f"حجم برابر {daily_f['volume_ratio']:.2f} برابر میانگین بیست‌کندله"
                  if daily_f.get("volume_ratio") is not None else "خوانش حجم در دسترس نیست")
    else:
        vol_word, vol_fa, rsi_txt = "unavailable", "نامشخص", "n/a"
        liq_txt, liq_fa = "volume read unavailable", "خوانش حجم در دسترس نیست"
    agr_fa = {"AGREE": "هم‌جهت", "DISAGREE": "ناهم‌جهت", "PARTIAL": "نیمه‌هم‌جهت",
              "INSUFFICIENT_DATA": "داده ناکافی"}.get(agreement, agreement)
    summary_en = (
        f"Rules-based evidence synthesis for {inp.symbol} (as_of {inp.as_of_ts}). "
        f"Daily trend read: {d_word}; weekly: {w_word}; hourly: {h_word}; multi-timeframe agreement: {agreement}. "
        f"Daily volatility read: {vol_word}. Daily liquidity read: {liq_txt}. Daily RSI(14): {rsi_txt}. "
        f"Missing or degraded inputs on record: {uncertainty_count}. "
        "All statements are deterministic rule outputs over the provided inputs; "
        "they are decision support, not investment advice."
    )
    summary_fa = (
        f"ترکیب قاعده‌محور شواهد برای نماد {inp.symbol} (زمان {inp.as_of_ts}). "
        f"روند روزانه: {d_fa}؛ هفتگی: {w_fa}؛ ساعتی: {h_fa}؛ هم‌جهتی چندزمانی: {agr_fa}. "
        f"نوسان روزانه: {vol_fa}. نقدشوندگی روزانه: {liq_fa}. RSI(14) روزانه: {rsi_txt}. "
        f"ورودی‌های ناموجود یا افت‌کرده: {uncertainty_count} مورد. "
        "همه گزاره‌ها خروجی قواعد معین روی ورودی‌های ارائه‌شده است؛ "
        "اینها پشتیبانی تصمیم است و توصیه سرمایه‌گذاری نیست."
    )

    report = SymbolAnalysisReport(
        symbol=inp.symbol, name_fa=inp.name_fa, as_of_ts=inp.as_of_ts, claims=claims,
        executive_summary_en=summary_en, executive_summary_fa=summary_fa, scenarios=scenarios,
        key_levels=key_levels, risk_factors=risk_factors, missing_data=missing,
        mtf_agreement=mtf_agreement, uncertainty_count=uncertainty_count,
        uncertainty_note_en=uncertainty_note_en, uncertainty_note_fa=uncertainty_note_fa,
        report_digest="",
    )
    payload = report.model_dump(mode="json")
    canonical = json.dumps({k: v for k, v in payload.items() if k != "report_digest"},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    report = report.model_copy(
        update={"report_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest()})

    # fail-closed banned-content gate (directive §F)
    findings = forbidden_terms_scan(report)
    if findings:
        raise ValueError(f"banned-content self-scan failed: {findings}")
    return report


__all__ = [
    "AnalystInput", "Claim", "ClaimKind", "ClaimProvenance", "FundamentalsSection", "KeyLevel",
    "MissingDataEntry", "RiskFactor", "ScenarioRecord", "SeriesInput", "StrategySignalContext",
    "SymbolAnalysisReport", "TrustClass", "analyze_symbol", "forbidden_terms_scan",
]
