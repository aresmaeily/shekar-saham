"""PKG-F tests — built-in indicator catalog + independent reference (§B4).

Offline and deterministic: the bar fixture is hashlib-seeded (no random
module, no clock, no network).  Cross-validation compares the legacy engine
(app.engines.indicators) against the independent reference implementations in
app.engines.indicator_reference on overlapping indices only (>= warm-up of
BOTH), aligned by bar timestamp.  The legacy engine rounds its dict outputs
(macd 8, bollinger/atr/vwap 6, stochastic/obv 4 decimals), so the comparison
asserts (a) reference-vs-engine deviation within the engine's rounding
half-step and (b) exact agreement (<= 1e-9) once the reference is rounded to
the engine's declared output precision.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import math
from typing import Dict, List

import pytest

from app.engines import indicator_catalog as cat
from app.engines import indicator_reference as ref
from app.engines import indicators as eng
from app.engines.indicator_catalog import (
    BUILT_IN_CATALOG,
    ALLOWED_PERMISSIONS,
    IndicatorCategory,
    catalog_version,
    get_spec,
    list_specs,
    validate_catalog,
)
from app.engines.indicator_reference import (
    ref_advance_decline_line,
    ref_atr,
    ref_bollinger,
    ref_ema,
    ref_macd,
    ref_new_high_rate,
    ref_obv,
    ref_rsi,
    ref_sma,
    ref_stochastic,
    ref_vwap,
)


# ---------------------------------------------------------------------------
# Deterministic fixtures (hashlib-seeded; no random module)
# ---------------------------------------------------------------------------
def _u32(seed: str) -> int:
    return int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:4], "big")


def fixture_bars(symbol_like: str, n: int) -> List[Dict[str, float | int]]:
    """Deterministic shared-contract bars {ts,o,h,l,c,v} from hashlib seeds."""
    price = 1000.0 + (_u32(f"{symbol_like}:seed") % 500) / 10.0
    bars: List[Dict[str, float | int]] = []
    for i in range(n):
        r_ret = _u32(f"{symbol_like}:{i}:ret") / 0xFFFFFFFF
        r_hi = _u32(f"{symbol_like}:{i}:hi") / 0xFFFFFFFF
        r_lo = _u32(f"{symbol_like}:{i}:lo") / 0xFFFFFFFF
        r_vol = _u32(f"{symbol_like}:{i}:vol") / 0xFFFFFFFF
        o = price
        c = price * (1.0 + (r_ret - 0.5) * 0.04)
        h = max(o, c) * (1.0 + 0.01 * r_hi)
        low = min(o, c) * (1.0 - 0.01 * r_lo)
        v = 100_000.0 * (0.5 + r_vol)
        bars.append({"ts": 1_700_000_000 + i * 60, "o": o, "h": h, "l": low, "c": c, "v": v})
        price = c
    return bars


def _to_engine(bars: List[Dict[str, float | int]]) -> List[Dict[str, float | int]]:
    """Shared-contract bars -> legacy engine shape {time,open,high,low,close,volume}."""
    return [
        {
            "time": b["ts"],
            "open": b["o"],
            "high": b["h"],
            "low": b["l"],
            "close": b["c"],
            "volume": b["v"],
        }
        for b in bars
    ]


BARS = fixture_bars("PKG-F:CATALOG", 80)
ENGINE_BARS = _to_engine(BARS)
CLOSES = [float(b["c"]) for b in BARS]


def _engine_map(rows: List[Dict]) -> Dict[int, float]:
    return {int(r["time"]): float(r["value"]) for r in rows}


def _assert_cross(
    label: str,
    ref_series: List[float],
    engine_rows: List[Dict],
    warmup: int,
    decimals: int,
) -> float:
    """Reference vs engine on indices >= warmup; returns max abs deviation."""
    m = _engine_map(engine_rows)
    max_dev = 0.0
    for i in range(warmup, len(BARS)):
        ts = int(BARS[i]["ts"])
        assert ts in m, f"{label}: engine output missing bar index {i}"
        rv = ref_series[i]
        ev = m[ts]
        assert math.isfinite(rv), f"{label}: non-finite reference value at {i}"
        dev = abs(rv - ev)
        max_dev = max(max_dev, dev)
        assert abs(round(rv, decimals) - ev) <= 1e-9, (
            f"{label}: rounded reference != engine at index {i}: {rv} vs {ev}"
        )
    bound = 0.5 * (10 ** -decimals) + 1e-12
    assert max_dev <= bound, f"{label}: max deviation {max_dev} exceeds rounding bound {bound}"
    return max_dev


# ---------------------------------------------------------------------------
# Catalog metadata health
# ---------------------------------------------------------------------------
def test_catalog_version_constant():
    assert catalog_version() == "IC-1.0.0"


def test_validate_catalog_healthy():
    assert validate_catalog() == []


def test_catalog_size_and_categories():
    assert len(BUILT_IN_CATALOG) >= 14
    covered = {s.category for s in BUILT_IN_CATALOG}
    assert covered == set(IndicatorCategory)


def test_unique_ids():
    ids = [s.id for s in BUILT_IN_CATALOG]
    assert len(ids) == len(set(ids))


def test_every_entry_metadata_complete():
    for s in BUILT_IN_CATALOG:
        assert s.id.startswith("builtin.")
        assert s.name_en.strip() and s.name_fa.strip()
        assert s.author == "radar-bourse"
        assert cat.parse_semver(s.version) is not None
        assert set(s.permissions) <= set(ALLOWED_PERMISSIONS)
        assert "series:read" in s.permissions
        assert s.warmup_bars >= 0


def test_math_definition_mentions_warmup():
    for s in BUILT_IN_CATALOG:
        assert s.math_definition.strip()
        assert "warm" in s.math_definition.lower()


def test_lookahead_declared_false_everywhere():
    for s in BUILT_IN_CATALOG:
        assert s.lookahead_declared is False


def test_engine_refs_resolve_callable():
    for s in BUILT_IN_CATALOG:
        module_path, _, attr = s.engine_ref.rpartition(".")
        mod = importlib.import_module(module_path)
        fn = getattr(mod, attr)
        assert callable(fn), f"{s.id}: engine_ref not callable"


def test_reference_refs_resolve_callable_when_present():
    for s in BUILT_IN_CATALOG:
        if s.reference_ref is None:
            assert s.id in {"builtin.adx", "builtin.cci", "builtin.williams"}
            continue
        module_path, _, attr = s.reference_ref.rpartition(".")
        mod = importlib.import_module(module_path)
        fn = getattr(mod, attr)
        assert callable(fn), f"{s.id}: reference_ref not callable"


def test_param_bounds_sane():
    for s in BUILT_IN_CATALOG:
        for p in s.inputs:
            assert p.minimum < p.default < p.maximum
            if p.type == "int":
                assert float(p.default).is_integer()
                assert float(p.minimum).is_integer()
                assert float(p.maximum).is_integer()


def test_dual_implementation_honesty():
    for s in BUILT_IN_CATALOG:
        assert s.dual_implementation == (s.engine_ref == s.reference_ref)
    for sid in ("builtin.sma", "builtin.ema", "builtin.rsi"):
        s = get_spec(sid)
        assert s is not None and s.dual_implementation is True
    for sid in ("builtin.macd", "builtin.bollinger", "builtin.atr"):
        s = get_spec(sid)
        assert s is not None and s.dual_implementation is False


def test_expected_warmup_defaults():
    expected = {
        "builtin.sma": 19,
        "builtin.ema": 19,
        "builtin.rsi": 14,
        "builtin.macd": 33,
        "builtin.bollinger": 19,
        "builtin.atr": 13,
        "builtin.adx": 14,
        "builtin.cci": 19,
        "builtin.williams": 13,
        "builtin.stochastic": 15,
        "builtin.obv": 0,
        "builtin.vwap": 0,
        "builtin.new_high_rate": 38,
        "builtin.advance_decline_line": 0,
    }
    for sid, warm in expected.items():
        s = get_spec(sid)
        assert s is not None, sid
        assert s.warmup_bars == warm, f"{sid}: warmup {s.warmup_bars} != {warm}"


def test_persian_labels_exact():
    expected = {
        "builtin.sma": "میانگین متحرک ساده",
        "builtin.ema": "میانگین متحرک نمایی",
        "builtin.rsi": "شاخص قدرت نسبی",
        "builtin.macd": "مکدی",
        "builtin.bollinger": "باندهای بولینگر",
        "builtin.atr": "میانگین دامنه واقعی",
        "builtin.adx": "شاخص میانگین جهت‌دار",
        "builtin.cci": "شاخص کانال کالا",
        "builtin.obv": "حجم انباشته",
        "builtin.williams": "نوسان‌نمای ویلیامز",
        "builtin.stochastic": "نوسان‌نمای تصادفی",
        "builtin.vwap": "میانگین وزنی حجم معاملات",
        "builtin.new_high_rate": "نرخ سقف‌های جدید",
        "builtin.advance_decline_line": "خط پیشرو-تأخیری",
    }
    for sid, fa in expected.items():
        s = get_spec(sid)
        assert s is not None and s.name_fa == fa


def test_series_inputs_and_volume_flags():
    expects = {
        "builtin.sma": ["close"],
        "builtin.macd": ["close"],
        "builtin.atr": ["high", "low", "close"],
        "builtin.stochastic": ["high", "low", "close"],
        "builtin.obv": ["close", "volume"],
        "builtin.vwap": ["high", "low", "close", "volume"],
        "builtin.advance_decline_line": [],
    }
    for sid, series in expects.items():
        s = get_spec(sid)
        assert s is not None and sorted(s.series_inputs) == sorted(series)
    for sid in ("builtin.obv", "builtin.vwap"):
        s = get_spec(sid)
        assert s is not None and s.requires_volume is True
    for sid in ("builtin.sma", "builtin.rsi", "builtin.adx"):
        s = get_spec(sid)
        assert s is not None and s.requires_volume is False


def test_breadth_entry_custom_inputs_doc():
    s = get_spec("builtin.advance_decline_line")
    assert s is not None
    assert s.category is IndicatorCategory.BREADTH
    assert s.series_inputs == [] and s.requires_volume is False
    assert "advances" in s.custom_inputs_doc and "declines" in s.custom_inputs_doc


def test_list_specs_category_filter():
    trend = list_specs(IndicatorCategory.TREND)
    assert {s.id for s in trend} == {"builtin.sma", "builtin.ema", "builtin.adx"}
    assert get_spec("builtin.nope") is None


def test_no_code_execution_primitives_in_pkgf_modules():
    for mod in (ref, cat):
        src = inspect.getsource(mod)
        for token in ("eval(", "exec(", "compile(", "__import__"):
            assert token not in src, f"{mod.__name__} contains {token!r}"


def test_reference_module_is_independent_of_engine_module():
    src_lines = inspect.getsource(ref).splitlines()
    import_lines = [
        ln for ln in src_lines
        if ln.startswith(("import ", "from "))
    ]
    assert import_lines, "sanity: reference module has imports"
    for ln in import_lines:
        assert "indicators import" not in ln and "import indicators" not in ln, ln
        assert "app.engines.indicators" not in ln, ln


# ---------------------------------------------------------------------------
# Reference implementations: hand-computed + naive independent recomputation
# ---------------------------------------------------------------------------
def _naive_sma(values: List[float], period: int) -> List[float]:
    out = []
    for i in range(len(values)):
        if i < period - 1:
            out.append(0.0)
        else:
            out.append(sum(values[i - period + 1 : i + 1]) / period)
    return out


def _naive_ema(values: List[float], period: int) -> List[float]:
    k = 2.0 / (period + 1.0)
    out = []
    prev = sum(values[:period]) / period
    for i, v in enumerate(values):
        if i < period - 1:
            out.append(prev)  # seed carry-over slots
        elif i == period - 1:
            out.append(prev)
        else:
            prev = v * k + prev * (1.0 - k)
            out.append(prev)
    return out


def _naive_rsi(closes: List[float], period: int) -> List[float]:
    out = [0.0] * len(closes)
    if len(closes) <= period:
        return out
    au = sum(max(closes[i] - closes[i - 1], 0.0) for i in range(1, period + 1)) / period
    ad = sum(max(closes[i - 1] - closes[i], 0.0) for i in range(1, period + 1)) / period

    def val(a: float, b: float) -> float:
        return 100.0 if b == 0 else 100.0 - 100.0 / (1.0 + a / b)

    out[period] = val(au, ad)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        au = (au * (period - 1) + max(d, 0.0)) / period
        ad = (ad * (period - 1) + max(-d, 0.0)) / period
        out[i] = val(au, ad)
    return out


def test_ref_sma_hand_computed():
    assert ref_sma([1.0, 2.0, 3.0, 4.0], 2) == [0.0, 1.5, 2.5, 3.5]
    assert ref_sma([1.0, 2.0, 3.0, 4.0], 3) == [0.0, 0.0, 2.0, 3.0]


def test_ref_sma_matches_naive_on_fixture():
    assert ref_sma(CLOSES, 14) == _naive_sma(CLOSES, 14)
    assert ref_sma(CLOSES, 20) == _naive_sma(CLOSES, 20)


def test_ref_ema_hand_computed_and_naive():
    out = ref_ema([1.0, 2.0, 3.0], 2)
    assert out[1] == 1.5  # SMA seed at index period-1
    assert out[2] == pytest.approx(2.5, abs=1e-12)
    assert out[0] == 1.5  # documented seed carry-over slot
    assert ref_ema(CLOSES, 12) == _naive_ema(CLOSES, 12)


def test_ref_rsi_hand_cases():
    assert ref_rsi([1.0, 2.0, 3.0], 2) == [0.0, 0.0, 100.0]  # all gains
    assert ref_rsi([3.0, 2.0, 1.0], 2) == [0.0, 0.0, 0.0]  # all losses
    assert ref_rsi([2.0, 1.0, 2.0], 2) == [0.0, 0.0, 50.0]  # RS = 1
    assert ref_rsi([5.0, 5.0, 5.0], 2) == [0.0, 0.0, 100.0]  # flat → avg_loss == 0 → 100


def test_ref_rsi_matches_naive_on_fixture():
    assert ref_rsi(CLOSES, 14) == _naive_rsi(CLOSES, 14)


# ---------------------------------------------------------------------------
# Cross-validation: legacy engine vs independent reference (n=80)
# ---------------------------------------------------------------------------
def test_cross_validate_macd():
    r = eng.macd(ENGINE_BARS)  # defaults 12/26/9
    rm = ref_macd(CLOSES)  # defaults 12/26/9
    warm = 33  # slow-1 + signal-1
    devs = [
        _assert_cross("macd.macd", rm["macd"], r["macd"], warm, 8),
        _assert_cross("macd.signal", rm["signal"], r["signal"], warm, 8),
        _assert_cross("macd.histogram", rm["histogram"], r["histogram"], warm, 8),
    ]
    assert max(devs) <= 5e-9 + 1e-12


def test_cross_validate_bollinger():
    r = eng.bollinger(ENGINE_BARS)  # defaults 20/2.0
    rb = ref_bollinger(CLOSES)  # defaults 20/2.0
    assert _assert_cross("bollinger.mid", rb["mid"], r["basis"], 19, 6) <= 5e-7 + 1e-12
    assert _assert_cross("bollinger.upper", rb["upper"], r["upper"], 19, 6) <= 5e-7 + 1e-12
    assert _assert_cross("bollinger.lower", rb["lower"], r["lower"], 19, 6) <= 5e-7 + 1e-12


def test_cross_validate_atr():
    r = eng.atr(ENGINE_BARS)  # defaults period=14
    ra = ref_atr(BARS)  # defaults period=14
    assert _assert_cross("atr", ra, r, 13, 6) <= 5e-7 + 1e-12


def test_cross_validate_stochastic():
    r = eng.stochastic(ENGINE_BARS)  # defaults 14/3/3
    rs = ref_stochastic(BARS)  # defaults 14/3/3
    assert _assert_cross("stoch.k", rs["k"], r["k"], 15, 4) <= 5e-5 + 1e-12
    assert _assert_cross("stoch.d", rs["d"], r["d"], 15, 4) <= 5e-5 + 1e-12


def test_cross_validate_obv():
    r = eng.obv(ENGINE_BARS)
    ro = ref_obv(BARS)
    assert _assert_cross("obv", ro, r, 0, 4) <= 5e-5 + 1e-12


def test_cross_validate_vwap():
    r = eng.vwap(ENGINE_BARS)
    rv = ref_vwap(BARS)
    assert _assert_cross("vwap", rv, r, 0, 6) <= 5e-7 + 1e-12


def test_engine_only_adx_shape():
    r = eng.adx(ENGINE_BARS)
    assert set(r) == {"adx", "plus_di", "minus_di"}
    n_expected = len(BARS) - 14  # first row at index `period`
    for key, rows in r.items():
        assert len(rows) == n_expected
        for row in rows:
            v = float(row["value"])
            assert math.isfinite(v) and 0.0 <= v <= 100.0


def test_engine_only_cci_williams_shape():
    cci_rows = eng.cci(ENGINE_BARS)  # period 20
    will_rows = eng.williams(ENGINE_BARS)  # period 14
    assert len(cci_rows) == len(BARS) - 20 + 1
    assert len(will_rows) == len(BARS) - 14 + 1
    for rows in (cci_rows, will_rows):
        for row in rows:
            assert math.isfinite(float(row["value"]))
    assert all(-100.0 <= float(row["value"]) <= 0.0 for row in will_rows)


# ---------------------------------------------------------------------------
# §B4 additions: market structure + breadth
# ---------------------------------------------------------------------------
def test_new_high_rate_hand_computed():
    # 20 bars @5.0, one 6.0, nineteen 1.0 → only index 20 is a rolling 20-bar high
    closes = [5.0] * 20 + [6.0] + [1.0] * 19
    out2 = ref_new_high_rate(closes, lookback=2)
    assert out2[:20] == [0.0] * 20  # warm-up: 19 + lookback - 1 = 20
    assert out2[20] == 1.0  # j=19 (flat window tie counts) and j=20 are highs
    assert out2[21] == 0.5  # j=20 high, j=21 not
    assert out2[22] == 0.0
    assert out2[39] == 0.0
    out20 = ref_new_high_rate(closes, lookback=20)
    assert out20[:38] == [0.0] * 38  # warm-up: 19 + 20 - 1 = 38
    assert out20[39] == pytest.approx(1 / 20, abs=1e-15)


def test_advance_decline_line_hand_computed():
    assert ref_advance_decline_line([3, 0, 2], [1, 2, 0]) == [2, 0, 2]
    assert ref_advance_decline_line([], []) == []
    assert ref_advance_decline_line([5], [5]) == [0]


def test_advance_decline_line_length_mismatch():
    with pytest.raises(ValueError):
        ref_advance_decline_line([1, 2], [1])
