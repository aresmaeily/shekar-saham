"""indicator_catalog.py — PKG-F (MASTER-RADAR directive §B4, Wave 3).

Versioned, metadata-complete registry of the built-in technical indicators.
Every entry carries: bilingual names (English + Persian ``name_fa``), category,
semver, precise math definition including the warm-up policy, parameter specs
with plausibility bounds, series requirements, repaint / missing-data
declarations, and dotted paths to (a) the legacy engine callable and (b) the
independent reference implementation in ``indicator_reference.py``.

Security posture (directive §B4 "do not execute arbitrary downloaded code"):
this module is *metadata only*.  The only imports it ever performs are of
first-party modules named in ``BUILT_IN_CATALOG`` (``app.engines.indicators``
and ``app.engines.indicator_reference``) during the advisory
:func:`validate_catalog` health check.  Imported user packages never carry
executable references — see ``indicator_manager.py``.

Note on ``missing_data`` semantics: it declares the warm-up / missing-data
contract of the *reference* output arrays (full-length, 0.0 or seed filled as
documented per entry).  For ``builtin.adx``/``builtin.cci``/``builtin.williams``
the arrays of the independent reference are full-length and 0.0-filled (see
the reference docstrings); their ``warmup_bars``/``missing_data`` fields keep
declaring the legacy engine behaviour (its dict outputs omit warm-up rows),
and ``builtin.adx`` additionally documents the reference's own longer ADX
warm-up (2*period-1) in its ``math_definition``.
"""

from __future__ import annotations

import importlib
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class IndicatorCategory(str, Enum):
    """Functional family of an indicator (directive §B4 taxonomy)."""

    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    BREADTH = "breadth"
    MARKET_STRUCTURE = "market_structure"


class RepaintDeclaration(str, Enum):
    """Honest repaint declaration for the indicator's closed-bar output."""

    NON_REPAINTING = "non_repainting"
    REPAINTS_LAST_BAR = "repaints_last_bar"
    SESSION_DEPENDENT = "session_dependent"


class MissingDataBehavior(str, Enum):
    """Declared behaviour for warm-up slots / missing input data."""

    ZERO_BEFORE_WARMUP = "zero_before_warmup"
    PARTIAL_WINDOW = "partial_window"
    SKIP = "skip"
    FAIL_CLOSED = "fail_closed"


# ---------------------------------------------------------------------------
# Shared whitelists / helpers
# ---------------------------------------------------------------------------
ALLOWED_PERMISSIONS: tuple[str, ...] = ("series:read", "chart:overlay", "chart:pane")
ALLOWED_SERIES: tuple[str, ...] = ("open", "high", "low", "close", "volume")


def parse_semver(version: str) -> Optional[tuple[int, int, int]]:
    """Parse a strict ``X.Y.Z`` semver string; ``None`` when not parseable.

    Deliberately regex-free (ASCII digits only, exactly three dot-separated
    components) so the module stays free of even ``re.compile`` — directive
    §B4 requires no eval/exec/compile anywhere in PKG-F code.
    """
    if not isinstance(version, str):
        return None
    parts = version.split(".")
    if len(parts) != 3:
        return None
    out: List[int] = []
    for part in parts:
        if not part or not part.isascii() or not part.isdigit():
            return None
        out.append(int(part))
    return (out[0], out[1], out[2])


# ---------------------------------------------------------------------------
# Param / indicator specs
# ---------------------------------------------------------------------------
class IndicatorParamSpec(BaseModel):
    """Single numeric parameter of a built-in indicator (frozen metadata)."""

    model_config = {"frozen": True}

    name: str = Field(min_length=1)
    type: Literal["int", "float"]
    default: float
    minimum: float
    maximum: float

    @model_validator(mode="after")
    def _bounds_plausible(self) -> "IndicatorParamSpec":
        if not (self.minimum < self.default < self.maximum):
            raise ValueError(
                f"param {self.name!r}: require minimum < default < maximum "
                f"(got {self.minimum} / {self.default} / {self.maximum})"
            )
        if self.type == "int":
            for label, v in (
                ("default", self.default),
                ("minimum", self.minimum),
                ("maximum", self.maximum),
            ):
                if not float(v).is_integer():
                    raise ValueError(
                        f"param {self.name!r}: {label} must be an integer for "
                        f"type 'int' (got {v})"
                    )
        return self


class IndicatorSpec(BaseModel):
    """Full metadata record for a built-in indicator (directive §B4)."""

    model_config = {"frozen": True}

    id: str
    name_en: str = Field(min_length=1)
    name_fa: str = Field(min_length=1)
    category: IndicatorCategory
    version: str
    author: str = "radar-bourse"
    permissions: List[str] = Field(default_factory=lambda: ["series:read"])
    math_definition: str = Field(min_length=1)
    inputs: List[IndicatorParamSpec] = Field(default_factory=list)
    warmup_bars: int = Field(ge=0)
    missing_data: MissingDataBehavior
    repaint: RepaintDeclaration
    lookahead_declared: bool = False
    series_inputs: List[str] = Field(default_factory=list)
    engine_ref: str
    reference_ref: Optional[str] = None
    requires_volume: bool = False
    dual_implementation: bool = False
    custom_inputs_doc: str = ""

    @field_validator("id")
    @classmethod
    def _id_reserved_namespace(cls, v: str) -> str:
        if not v.startswith("builtin."):
            raise ValueError("built-in spec ids must live in the reserved 'builtin.*' namespace")
        return v

    @field_validator("version")
    @classmethod
    def _semver(cls, v: str) -> str:
        if parse_semver(v) is None:
            raise ValueError(f"version must be semver X.Y.Z (got {v!r})")
        return v

    @field_validator("permissions")
    @classmethod
    def _permissions_whitelisted(cls, v: List[str]) -> List[str]:
        bad = [p for p in v if p not in ALLOWED_PERMISSIONS]
        if bad:
            raise ValueError(f"permissions outside whitelist: {bad}")
        return v

    @field_validator("series_inputs")
    @classmethod
    def _series_known(cls, v: List[str]) -> List[str]:
        bad = [s for s in v if s not in ALLOWED_SERIES]
        if bad:
            raise ValueError(f"series_inputs outside the OHLCV set: {bad}")
        return v

    @field_validator("math_definition")
    @classmethod
    def _math_mentions_warmup(cls, v: str) -> str:
        if "warm" not in v.lower():
            raise ValueError("math_definition must state the warm-up policy")
        return v

    @model_validator(mode="after")
    def _consistency(self) -> "IndicatorSpec":
        if self.lookahead_declared is not False:
            raise ValueError(
                "lookahead_declared must be False for every built-in entry "
                "(directive §B4: built-ins are backward-looking only)"
            )
        if self.dual_implementation != (self.engine_ref == self.reference_ref):
            raise ValueError(
                f"{self.id}: dual_implementation must be True exactly when "
                "engine_ref == reference_ref (honesty invariant)"
            )
        if not self.series_inputs and not self.custom_inputs_doc:
            raise ValueError(
                f"{self.id}: entries without OHLCV series_inputs must document "
                "their custom inputs via custom_inputs_doc"
            )
        return self


# ---------------------------------------------------------------------------
# Built-in catalog (directive §B4)
# ---------------------------------------------------------------------------
BUILT_IN_CATALOG: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        id="builtin.sma",
        name_en="Simple Moving Average",
        name_fa="میانگین متحرک ساده",
        category=IndicatorCategory.TREND,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "SMA[i] = (close[i-period+1] + ... + close[i]) / period. "
            "Output arrays are 0.0 for i < period-1. "
            "Warm-up: period-1 bars; the first valid value sits at index period-1."
        ),
        inputs=[IndicatorParamSpec(name="period", type="int", default=20, minimum=1, maximum=500)],
        warmup_bars=19,
        missing_data=MissingDataBehavior.ZERO_BEFORE_WARMUP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["close"],
        engine_ref="app.engines.indicator_reference.ref_sma",
        reference_ref="app.engines.indicator_reference.ref_sma",
        requires_volume=False,
        dual_implementation=True,
    ),
    IndicatorSpec(
        id="builtin.ema",
        name_en="Exponential Moving Average",
        name_fa="میانگین متحرک نمایی",
        category=IndicatorCategory.TREND,
        version="1.1.0",
        permissions=["series:read"],
        math_definition=(
            "EMA[i] = close[i]*k + EMA[i-1]*(1-k) with k = 2/(period+1); "
            "seeded with SMA(close[0..period-1]) at index period-1 (indices before "
            "period-1 repeat the seed as a documented carry-over artifact). "
            "Warm-up: period-1 bars; first valid value at index period-1."
        ),
        inputs=[IndicatorParamSpec(name="period", type="int", default=20, minimum=1, maximum=500)],
        warmup_bars=19,
        missing_data=MissingDataBehavior.PARTIAL_WINDOW,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["close"],
        engine_ref="app.engines.indicator_reference.ref_ema",
        reference_ref="app.engines.indicator_reference.ref_ema",
        requires_volume=False,
        dual_implementation=True,
    ),
    IndicatorSpec(
        id="builtin.rsi",
        name_en="Relative Strength Index",
        name_fa="شاخص قدرت نسبی",
        category=IndicatorCategory.MOMENTUM,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "Wilder RSI on close deltas: up=max(d,0), dn=max(-d,0); first averages are "
            "the SMA of the first `period` deltas, then avg=(prev*(period-1)+next)/period; "
            "RSI = 100 - 100/(1 + avg_up/avg_dn); avg_dn == 0 maps to 100.0 (flat window "
            "included). Warm-up: `period` bars; 0.0 before index period."
        ),
        inputs=[IndicatorParamSpec(name="period", type="int", default=14, minimum=2, maximum=100)],
        warmup_bars=14,
        missing_data=MissingDataBehavior.ZERO_BEFORE_WARMUP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["close"],
        engine_ref="app.engines.indicator_reference.ref_rsi",
        reference_ref="app.engines.indicator_reference.ref_rsi",
        requires_volume=False,
        dual_implementation=True,
    ),
    IndicatorSpec(
        id="builtin.macd",
        name_en="MACD",
        name_fa="مکدی",
        category=IndicatorCategory.MOMENTUM,
        version="1.2.0",
        permissions=["series:read"],
        math_definition=(
            "macd[i] = EMA_fast(close)[i] - EMA_slow(close)[i]; signal = EMA_signal(macd); "
            "histogram[i] = macd[i] - signal[i]; EMAs use the SMA-seeded convention. "
            "Warm-up: slow-1 bars for macd and slow+signal-2 bars for signal/histogram; "
            "earlier slots are seed carry-over artifacts and must be ignored."
        ),
        inputs=[
            IndicatorParamSpec(name="fast", type="int", default=12, minimum=2, maximum=100),
            IndicatorParamSpec(name="slow", type="int", default=26, minimum=3, maximum=200),
            IndicatorParamSpec(name="signal", type="int", default=9, minimum=1, maximum=50),
        ],
        warmup_bars=33,
        missing_data=MissingDataBehavior.PARTIAL_WINDOW,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["close"],
        engine_ref="app.engines.indicators.macd",
        reference_ref="app.engines.indicator_reference.ref_macd",
        requires_volume=False,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.bollinger",
        name_en="Bollinger Bands",
        name_fa="باندهای بولینگر",
        category=IndicatorCategory.VOLATILITY,
        version="1.0.0",
        permissions=["series:read", "chart:overlay"],
        math_definition=(
            "mid = SMA(close, period); sd = population standard deviation (ddof=0) of the "
            "same window; upper = mid + mult*sd; lower = mid - mult*sd; arrays are 0.0 "
            "before the warm-up index. Warm-up: period-1 bars; first valid value at index "
            "period-1."
        ),
        inputs=[
            IndicatorParamSpec(name="period", type="int", default=20, minimum=2, maximum=400),
            IndicatorParamSpec(name="mult", type="float", default=2.0, minimum=0.5, maximum=5.0),
        ],
        warmup_bars=19,
        missing_data=MissingDataBehavior.ZERO_BEFORE_WARMUP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["close"],
        engine_ref="app.engines.indicators.bollinger",
        reference_ref="app.engines.indicator_reference.ref_bollinger",
        requires_volume=False,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.atr",
        name_en="Average True Range",
        name_fa="میانگین دامنه واقعی",
        category=IndicatorCategory.VOLATILITY,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "TR[0] = h-l; TR[i] = max(h-l, |h-prev_close|, |l-prev_close|); ATR seeded with "
            "SMA(TR[0..period-1]) at index period-1, then Wilder smoothing "
            "ATR[i] = (ATR[i-1]*(period-1)+TR[i])/period; arrays are 0.0 before the warm-up "
            "index. Warm-up: period-1 bars."
        ),
        inputs=[IndicatorParamSpec(name="period", type="int", default=14, minimum=1, maximum=100)],
        warmup_bars=13,
        missing_data=MissingDataBehavior.ZERO_BEFORE_WARMUP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["high", "low", "close"],
        engine_ref="app.engines.indicators.atr",
        reference_ref="app.engines.indicator_reference.ref_atr",
        requires_volume=False,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.adx",
        name_en="Average Directional Index",
        name_fa="شاخص میانگین جهت‌دار",
        category=IndicatorCategory.TREND,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "Wilder DMI: +DM/-DM from bar-to-bar range extensions, TR as in ATR; "
            "+DI/-DI = 100 * Wilder-smoothed(DM)/Wilder-smoothed(TR); "
            "DX = 100*|+DI - -DI|/(+DI + -DI) (0.0 when the sum is 0); "
            "ADX = Wilder-smoothed DX. Warm-up: `period` bars; the engine emits the first "
            "ADX/+DI/-DI row at index `period` and omits earlier rows. The independent "
            "reference arrays are full-length and 0.0-filled: +DI/-DI first valid at "
            "index `period`, the ADX line (textbook Wilder seed = mean of the first "
            "`period` DX values) first valid at index 2*period-1."
        ),
        inputs=[IndicatorParamSpec(name="period", type="int", default=14, minimum=2, maximum=100)],
        warmup_bars=14,
        missing_data=MissingDataBehavior.SKIP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["high", "low", "close"],
        engine_ref="app.engines.indicators.adx",
        reference_ref="app.engines.indicator_reference.ref_adx",
        requires_volume=False,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.cci",
        name_en="Commodity Channel Index",
        name_fa="شاخص کانال کالا",
        category=IndicatorCategory.MOMENTUM,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "TP = (h+l+c)/3; CCI = (TP[i] - SMA(TP, period)) / (0.015 * mean absolute "
            "deviation of TP over the same window); zero mean deviation maps to 0.0. "
            "Warm-up: period-1 bars; the engine omits earlier rows. The independent "
            "reference array is full-length with 0.0 before the warm-up index."
        ),
        inputs=[IndicatorParamSpec(name="period", type="int", default=20, minimum=2, maximum=200)],
        warmup_bars=19,
        missing_data=MissingDataBehavior.SKIP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["high", "low", "close"],
        engine_ref="app.engines.indicators.cci",
        reference_ref="app.engines.indicator_reference.ref_cci",
        requires_volume=False,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.obv",
        name_en="On-Balance Volume",
        name_fa="حجم انباشته",
        category=IndicatorCategory.VOLUME,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "OBV[0] = volume[0]; OBV[i] = OBV[i-1] + volume[i] when close[i] > close[i-1], "
            "OBV[i-1] - volume[i] when close[i] < close[i-1], otherwise unchanged; missing "
            "volume counts as a 0 contribution. Warm-up: none — valid from the first bar."
        ),
        inputs=[],
        warmup_bars=0,
        missing_data=MissingDataBehavior.ZERO_BEFORE_WARMUP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["close", "volume"],
        engine_ref="app.engines.indicators.obv",
        reference_ref="app.engines.indicator_reference.ref_obv",
        requires_volume=True,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.williams",
        name_en="Williams %R",
        name_fa="نوسان‌نمای ویلیامز",
        category=IndicatorCategory.MOMENTUM,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "%R = -100 * (highest_high(period) - close) / (highest_high - lowest_low) over "
            "the trailing `period` bars; a flat window maps to -50. "
            "Warm-up: period-1 bars; the engine omits earlier rows. The independent "
            "reference array is full-length with 0.0 before the warm-up index."
        ),
        inputs=[IndicatorParamSpec(name="period", type="int", default=14, minimum=1, maximum=200)],
        warmup_bars=13,
        missing_data=MissingDataBehavior.SKIP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["high", "low", "close"],
        engine_ref="app.engines.indicators.williams",
        reference_ref="app.engines.indicator_reference.ref_williams_r",
        requires_volume=False,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.stochastic",
        name_en="Stochastic Oscillator",
        name_fa="نوسان‌نمای تصادفی",
        category=IndicatorCategory.MOMENTUM,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "raw %K = 100*(close - lowest_low(k_period)) / (highest_high - lowest_low), flat "
            "window maps to 50.0; K = mean of the raw %K values available in the clipped "
            "`smooth` window (partial windows allowed during warm-up); D = mean of the last "
            "d_period K values once all exist (divided by d_period exactly). "
            "Warm-up: k_period + d_period - 2 bars for D; K is fully smoothed from "
            "k_period + smooth - 2."
        ),
        inputs=[
            IndicatorParamSpec(name="k_period", type="int", default=14, minimum=2, maximum=200),
            IndicatorParamSpec(name="d_period", type="int", default=3, minimum=1, maximum=50),
            IndicatorParamSpec(name="smooth", type="int", default=3, minimum=1, maximum=50),
        ],
        warmup_bars=15,
        missing_data=MissingDataBehavior.PARTIAL_WINDOW,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["high", "low", "close"],
        engine_ref="app.engines.indicators.stochastic",
        reference_ref="app.engines.indicator_reference.ref_stochastic",
        requires_volume=False,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.vwap",
        name_en="Volume Weighted Average Price",
        name_fa="میانگین وزنی حجم معاملات",
        category=IndicatorCategory.VOLUME,
        version="1.1.0",
        permissions=["series:read", "chart:overlay"],
        math_definition=(
            "typical = (h+l+c)/3; VWAP[i] = sum(typical[j]*v[j], j<=i) / sum(v[j], j<=i), "
            "cumulative over the supplied window and re-anchored per session by the caller. "
            "Warm-up: none; leading bars with zero cumulative volume are skipped."
        ),
        inputs=[],
        warmup_bars=0,
        missing_data=MissingDataBehavior.SKIP,
        repaint=RepaintDeclaration.SESSION_DEPENDENT,
        lookahead_declared=False,
        series_inputs=["high", "low", "close", "volume"],
        engine_ref="app.engines.indicators.vwap",
        reference_ref="app.engines.indicator_reference.ref_vwap",
        requires_volume=True,
        dual_implementation=False,
    ),
    IndicatorSpec(
        id="builtin.new_high_rate",
        name_en="New High Rate (20)",
        name_fa="نرخ سقف‌های جدید",
        category=IndicatorCategory.MARKET_STRUCTURE,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "At each bar, the fraction of the last `lookback` closes that equal the maximum "
            "of their trailing 20-bar close window (ties count as highs); 0.0 before the "
            "warm-up index. Warm-up: 19 + lookback - 1 bars (20-bar high test plus the "
            "lookback fraction window)."
        ),
        inputs=[IndicatorParamSpec(name="lookback", type="int", default=20, minimum=2, maximum=250)],
        warmup_bars=38,
        missing_data=MissingDataBehavior.ZERO_BEFORE_WARMUP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=["close"],
        engine_ref="app.engines.indicator_reference.ref_new_high_rate",
        reference_ref="app.engines.indicator_reference.ref_new_high_rate",
        requires_volume=False,
        dual_implementation=True,
    ),
    IndicatorSpec(
        id="builtin.advance_decline_line",
        name_en="Advance-Decline Line",
        name_fa="خط پیشرو-تأخیری",
        category=IndicatorCategory.BREADTH,
        version="1.0.0",
        permissions=["series:read"],
        math_definition=(
            "ADL[i] = ADL[i-1] + advances[i] - declines[i], starting from 0 before the first "
            "session. Breadth inputs are two provider-dependent per-session integer series "
            "(counts of advancing and declining symbols), not OHLCV bars; missing sessions "
            "contribute 0. Warm-up: none — valid from the first session."
        ),
        inputs=[],
        warmup_bars=0,
        missing_data=MissingDataBehavior.ZERO_BEFORE_WARMUP,
        repaint=RepaintDeclaration.NON_REPAINTING,
        lookahead_declared=False,
        series_inputs=[],
        engine_ref="app.engines.indicator_reference.ref_advance_decline_line",
        reference_ref="app.engines.indicator_reference.ref_advance_decline_line",
        requires_volume=False,
        dual_implementation=True,
        custom_inputs_doc=(
            "Requires two aligned provider-dependent integer series: `advances` and "
            "`declines` (per-session counts of advancing/declining symbols). Not "
            "computable from OHLCV bars; the data provider must supply the breadth pair."
        ),
    ),
)

# Fixed catalog version (directive §B4: versioned registry).
_CATALOG_VERSION = "IC-1.0.0"


# ---------------------------------------------------------------------------
# Accessors / health check
# ---------------------------------------------------------------------------
def catalog_version() -> str:
    """Return the immutable built-in catalog version (currently ``IC-1.0.0``)."""
    return _CATALOG_VERSION


def get_spec(indicator_id: str) -> Optional[IndicatorSpec]:
    """Return the built-in spec for ``indicator_id`` or ``None``."""
    for spec in BUILT_IN_CATALOG:
        if spec.id == indicator_id:
            return spec
    return None


def list_specs(category: Optional[IndicatorCategory] = None) -> List[IndicatorSpec]:
    """List built-in specs, optionally filtered by category (catalog order)."""
    if category is None:
        return list(BUILT_IN_CATALOG)
    return [s for s in BUILT_IN_CATALOG if s.category == category]


def resolve_dotted(dotted: str) -> object:
    """Resolve ``package.module.attr`` to a Python object via importlib.

    Returns ``None`` when the dotted path cannot be resolved.  Only ever used
    on first-party dotted paths declared inside ``BUILT_IN_CATALOG`` — never
    on imported user packages (directive §B4: imported packages are validated
    JSON documents, not code).
    """
    if not dotted or "." not in dotted:
        return None
    module_path, _, attr_chain = dotted.rpartition(".")
    try:
        obj: object = importlib.import_module(module_path)
    except Exception:
        return None
    for part in attr_chain.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def validate_catalog() -> List[str]:
    """Advisory health check over ``BUILT_IN_CATALOG``; ``[]`` when healthy.

    Checks: unique ids, parseable semver, ``lookahead_declared is False``,
    non-empty ``name_fa``, permissions within the whitelist, and that every
    ``engine_ref`` (and every declared ``reference_ref``) resolves to an
    importable, callable object via importlib.  Warm-up consistency against
    the reference docstrings cannot be auto-checked and is intentionally not
    asserted here (it is covered by the PKG-F cross-validation tests).
    """
    problems: List[str] = []
    seen: set[str] = set()
    for spec in BUILT_IN_CATALOG:
        if spec.id in seen:
            problems.append(f"{spec.id}: duplicate id in BUILT_IN_CATALOG")
        seen.add(spec.id)
        if parse_semver(spec.version) is None:
            problems.append(f"{spec.id}: version {spec.version!r} is not semver X.Y.Z")
        if spec.lookahead_declared is not False:
            problems.append(f"{spec.id}: lookahead_declared must be False for built-ins")
        if not spec.name_fa.strip():
            problems.append(f"{spec.id}: name_fa must be non-empty")
        bad_perms = [p for p in spec.permissions if p not in ALLOWED_PERMISSIONS]
        if bad_perms:
            problems.append(f"{spec.id}: permissions outside whitelist: {bad_perms}")
        engine = resolve_dotted(spec.engine_ref)
        if not callable(engine):
            problems.append(f"{spec.id}: engine_ref {spec.engine_ref!r} does not resolve to a callable")
        if spec.reference_ref is not None:
            ref = resolve_dotted(spec.reference_ref)
            if not callable(ref):
                problems.append(
                    f"{spec.id}: reference_ref {spec.reference_ref!r} does not resolve to a callable"
                )
    return problems
