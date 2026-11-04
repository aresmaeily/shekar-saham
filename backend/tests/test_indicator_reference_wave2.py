"""MR2-A WAVE-2 tests — ref_adx / ref_cci / ref_williams_r (directive §B4).

Every hand fixture below is computed BY HAND in the comments (the arithmetic
is shown step by step); none of the expected values reuse the code under
test.  The seeded cross-validation mirrors the hashlib-seeded bar generator
of ``test_indicator_catalog.py`` (same construction, no random module, no
clock) and compares the independent references against the legacy engine
``app.engines.indicators`` on the overlapping valid ranges, within the
engine's documented rounding half-step (its dict outputs round to 4
decimals).  Where the legacy engine's ADX seed convention differs from the
textbook reference (it seeds ADX with the first DX instead of the mean of
the first ``period`` DX values), the comparison uses the mathematically
bounded convergence tail instead of pretending exact parity — see the
comment inside ``test_cross_validate_adx_convergence_tail``.
"""
from __future__ import annotations

import hashlib
import math
from typing import Dict, List

import pytest

from app.engines import indicator_reference as ref
from app.engines import indicators as eng
from app.engines.indicator_reference import ref_adx, ref_cci, ref_williams_r

# Tolerances (documented): the legacy engine rounds its dict outputs to 4
# decimals, so the max honest deviation is the rounding half-step 5e-5.
ENGINE_ROUNDING_TOL = 5e-5 + 1e-12


def _bars(rows: List[tuple[float, float, float]]) -> List[Dict[str, float | int]]:
    """Shared-contract bars {ts,o,h,l,c,v} from (h, l, c) rows, ts = 60s grid."""
    return [
        {"ts": i * 60, "o": (h + l) / 2, "h": h, "l": l, "c": c, "v": 1000.0}
        for i, (h, l, c) in enumerate(rows)
    ]


def _engine_bars(bars: List[Dict[str, float | int]]) -> List[Dict[str, float | int]]:
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


# ---------------------------------------------------------------------------
# CCI — hand-computed fixture (10 bars, period 3)
# ---------------------------------------------------------------------------
# TP = (h+l+c)/3 per bar; rows chosen so the TP series is 2,3,4,5,6,4,4,4,4,4:
#   i0 (3,1,2)->2  i1 (4,2,3)->3  i2 (5,3,4)->4  i3 (6,4,5)->5  i4 (7,5,6)->6
#   i5..i9 (5,3,4)->4
# CCI[i] = (TP[i] - mean(TP window)) / (0.015 * mean|TP - mean|), period 3:
#   i2: win [2,3,4] mean=3, MD=(1+0+1)/3=2/3 -> (4-3)/(0.015*2/3)=1/0.01=+100
#   i3: win [3,4,5] mean=4, MD=2/3          -> (5-4)/0.01=+100
#   i4: win [4,5,6] mean=5, MD=2/3          -> (6-5)/0.01=+100
#   i5: win [5,6,4] mean=5, MD=(0+1+1)/3=2/3 -> (4-5)/0.01=-100
#   i6: win [6,4,4] mean=14/3, MD=(4/3+2/3+2/3)/3=8/9 -> (4-14/3)/(0.015*8/9)
#       = (-2/3)/(1/75) = -50
#   i7..i9: win [4,4,4] -> MD=0 -> flat window maps to 0.0
def test_ref_cci_hand_computed() -> None:
    bars = _bars(
        [(3, 1, 2), (4, 2, 3), (5, 3, 4), (6, 4, 5), (7, 5, 6)]
        + [(5, 3, 4)] * 5
    )
    out = ref_cci(bars, period=3)
    assert out[:2] == [0.0, 0.0]  # warm-up: period-1 leading zeros
    assert out[2] == pytest.approx(100.0, abs=1e-9)
    assert out[3] == pytest.approx(100.0, abs=1e-9)
    assert out[4] == pytest.approx(100.0, abs=1e-9)
    assert out[5] == pytest.approx(-100.0, abs=1e-9)
    assert out[6] == pytest.approx(-50.0, abs=1e-9)
    assert out[7:] == [0.0, 0.0, 0.0]  # zero mean deviation -> documented 0.0


def test_ref_cci_warmup_and_length_contract() -> None:
    bars = _bars([(3, 1, 2), (4, 2, 3), (5, 3, 4), (6, 4, 5), (7, 5, 6), (5, 3, 4)])
    out = ref_cci(bars, period=4)
    assert len(out) == len(bars)  # full-length output
    assert out[:3] == [0.0, 0.0, 0.0]  # period-1 leading zeros
    assert all(v == v and math.isfinite(v) for v in out)  # NaN/None-free


# ---------------------------------------------------------------------------
# Williams %R — hand-computed fixture (12 bars, period 4)
# ---------------------------------------------------------------------------
# %R[i] = (HH - C) / (HH - LL) * -100 over the trailing 4 bars (0..-100):
#   rows (h,l,c):
#   i0 (10,8,9) i1 (11,9,10) i2 (12,10,11) i3 (13,11,12) i4 (14,12,13)
#   i5 (15,13,14) i6 (9,7,8) i7 (10,10,10) i8 (10,10,10) i9 (10,10,10)
#   i10 (10,10,10) i11 (10,10,10)
#   i3: win 0..3 HH=13 LL=8 C=12 -> (13-12)/(13-8)*-100 = -20
#   i4: win 1..4 HH=14 LL=9 C=13 -> (14-13)/(14-9)*-100 = -20
#   i5: win 2..5 HH=15 LL=10 C=14 -> (15-14)/(15-10)*-100 = -20
#   i6: win 3..6 HH=15 LL=7 C=8  -> (15-8)/(15-7)*-100 = -87.5
#   i7: win 4..7 HH=15 LL=7 C=10 -> (15-10)/(15-7)*-100 = -62.5
#   i8: win 5..8 HH=15 LL=7 C=10 -> (15-10)/(15-7)*-100 = -62.5
#   i9: win 6..9 HH=10 LL=7 C=10 -> (10-10)/(10-7)*-100 = 0 (close AT the high)
#   i10/i11: windows 7..10 / 8..11 are perfectly flat -> HH==LL -> -50
def test_ref_williams_r_hand_computed() -> None:
    rows = [(10, 8, 9), (11, 9, 10), (12, 10, 11), (13, 11, 12), (14, 12, 13), (15, 13, 14)]
    rows += [(9, 7, 8)] + [(10, 10, 10)] * 5
    bars = _bars(rows)
    out = ref_williams_r(bars, period=4)
    assert out[:3] == [0.0, 0.0, 0.0]  # warm-up: period-1 leading zeros
    assert out[3] == -20.0 and out[4] == -20.0 and out[5] == -20.0
    assert out[6] == pytest.approx(-87.5, abs=1e-9)
    assert out[7] == pytest.approx(-62.5, abs=1e-9)
    assert out[8] == pytest.approx(-62.5, abs=1e-9)
    assert out[9] == 0.0  # close exactly at the window high
    # AUDIT-MR2 O4: == 0.0 cannot distinguish the sign; pin it via copysign
    # (documented convention: +0.0, never -0.0, at close-on-high).
    assert math.copysign(1.0, out[9]) == 1.0
    assert out[10] == -50.0 and out[11] == -50.0  # flat window -> documented -50


def test_ref_williams_r_bounds_and_warmup() -> None:
    bars = _bars([(10, 8, 9), (11, 9, 10), (12, 10, 11), (13, 11, 12)])
    out = ref_williams_r(bars, period=3)
    assert len(out) == 4 and out[:2] == [0.0, 0.0]
    assert all(-100.0 <= v <= 0.0 for v in out[2:])  # 0..-100 scale


# ---------------------------------------------------------------------------
# ADX — hand-computed fixture (8 bars, period 2)
# ---------------------------------------------------------------------------
# Rows alternate (3,1,2) and (5,3,4). Per-bar DM/TR for i>=1 (prev bar p):
#   TR[i] = max(h-l, |h-c_p|, |l-c_p|) = max(2, 3, 1) = 3 for every i
#   +DM: up = h[i]-h[i-1] = ±2; -DM: dn = l[i-1]-l[i] = ∓2
#   -> +DM = [2,0,2,0,2,0,2], -DM = [0,2,0,2,0,2,0] (bars 1..7), TR = 3 each
# Wilder seeds at bar index 2 (mean over bars 1..2):
#   TRw=3, +DMw=(2+0)/2=1, -DMw=(0+2)/2=1
#   +DI[2]=1/3*100=33.3333..  -DI[2]=33.3333..  DX[2]=|0|/(2/3*100)*100=0
# Wilder recursion (avg=(prev*1+next)/2), per bar k=3..7:
#   k=3: TRw=3, +DMw=(1+2)/2=1.5, -DMw=(1+0)/2=0.5
#        +DI=50, -DI=16.6667, DX=|1.5-0.5|/2*100=50
#   k=4: +DMw=(1.5+0)/2=0.75, -DMw=(0.5+2)/2=1.25 -> +DI=25, -DI=41.6667, DX=25
#   k=5: +DMw=(0.75+2)/2=1.375, -DMw=(1.25+0)/2=0.625 -> +DI=45.8333,
#        -DI=20.8333, DX=0.75/2*100=37.5
#   k=6: +DMw=(1.375+0)/2=0.6875, -DMw=(0.625+2)/2=1.3125 -> +DI=22.9167,
#        -DI=43.75, DX=0.625/2*100=31.25
#   k=7: +DMw=(0.6875+2)/2=1.34375, -DMw=(1.3125+0)/2=0.65625 -> +DI=44.7917,
#        -DI=21.875, DX=0.6875/2*100=34.375
# ADX (textbook): first ADX = mean(DX[2..3]) at index 2*period-1 = 3:
#   ADX[3]=(0+50)/2=25; ADX[4]=(25+25)/2=25; ADX[5]=(25+37.5)/2=31.25;
#   ADX[6]=(31.25+31.25)/2=31.25; ADX[7]=(31.25+34.375)/2=32.8125
ADX_ROWS = [(3, 1, 2), (5, 3, 4), (3, 1, 2), (5, 3, 4), (3, 1, 2), (5, 3, 4), (3, 1, 2), (5, 3, 4)]


def test_ref_adx_hand_computed() -> None:
    bars = _bars(ADX_ROWS)
    out = ref_adx(bars, period=2)
    # exact warm-up: DI from index `period`, ADX from index 2*period-1
    assert out["adx"][:3] == [0.0, 0.0, 0.0]
    assert out["plus_di"][:2] == [0.0, 0.0]
    assert out["minus_di"][:2] == [0.0, 0.0]
    # ADX line (all-dyadic steps -> exact)
    assert out["adx"][3:] == pytest.approx([25.0, 25.0, 31.25, 31.25, 32.8125], abs=1e-9)
    exp_plus = [0.0, 0.0, 100 / 3, 50.0, 25.0, 137.5 / 3, 22.916666666666668, 44.79166666666667]
    exp_minus = [0.0, 0.0, 100 / 3, 50 / 3, 125 / 3, 62.5 / 3, 43.75, 21.875]
    assert out["plus_di"] == pytest.approx(exp_plus, abs=1e-9)
    assert out["minus_di"] == pytest.approx(exp_minus, abs=1e-9)


def test_ref_adx_short_series_all_warmup() -> None:
    # 4 bars, period 14: no DM/TR window at all -> every array all-zero,
    # full length, no NaN/None.
    bars = _bars(ADX_ROWS[:4])
    out = ref_adx(bars, period=14)
    assert len(out["adx"]) == 4 and out["adx"] == [0.0] * 4
    assert out["plus_di"] == [0.0] * 4 and out["minus_di"] == [0.0] * 4


def test_ref_adx_flat_bars_zero_di_and_dx() -> None:
    # perfectly flat bars: TR=0 -> +DI/-DI=0 (documented), sum 0 -> DX=0
    bars = _bars([(5, 5, 5)] * 6)
    out = ref_adx(bars, period=2)
    assert out["plus_di"] == [0.0] * 6 and out["minus_di"] == [0.0] * 6
    assert out["adx"] == [0.0] * 6


def test_ref_adx_period2_matches_engine_on_hand_fixture() -> None:
    # For period==2 the textbook ADX seed (mean of the first 2 DX values)
    # coincides with the engine's first-DX seed: one Wilder step from DX[2]
    # IS the mean of DX[2..3]. So exact engine parity holds for p=2 and is
    # asserted here (engine rounds to 4 decimals).
    bars = _bars(ADX_ROWS)
    engine = eng.adx(_engine_bars(bars), period=2)

    def rows_to_map(rows: List[Dict]) -> Dict[int, float]:
        return {int(r["time"]): float(r["value"]) for r in rows}

    adx_m = rows_to_map(engine["adx"])
    plus_m = rows_to_map(engine["plus_di"])
    minus_m = rows_to_map(engine["minus_di"])
    reference = ref_adx(bars, period=2)
    for i in range(3, len(bars)):  # engine emits rows from index `period`=2;
        ts = int(bars[i]["ts"])  # the reference ADX is valid from 2*2-1=3
        assert ts in adx_m
        assert round(reference["adx"][i], 4) == pytest.approx(adx_m[ts], abs=1e-9)
        assert round(reference["plus_di"][i], 4) == pytest.approx(plus_m[ts], abs=1e-9)
        assert round(reference["minus_di"][i], 4) == pytest.approx(minus_m[ts], abs=1e-9)


# ---------------------------------------------------------------------------
# Seeded cross-validation vs the legacy engine (same construction as the
# catalog tests: hashlib digests, no random module, no clock)
# ---------------------------------------------------------------------------
def _u32(seed: str) -> int:
    return int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:4], "big")


def fixture_bars(symbol_like: str, n: int) -> List[Dict[str, float | int]]:
    """Deterministic shared-contract bars; mirrors test_indicator_catalog.fixture_bars."""
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


BARS = fixture_bars("MR2-A:WAVE2", 80)
ENGINE_BARS = _engine_bars(BARS)


def _cross_check(
    label: str,
    ref_series: List[float],
    engine_rows: List[Dict],
    first_valid: int,
) -> float:
    """Reference vs engine on indices >= first_valid; returns max abs deviation."""
    engine_map = {int(r["time"]): float(r["value"]) for r in engine_rows}
    max_dev = 0.0
    for i in range(first_valid, len(BARS)):
        ts = int(BARS[i]["ts"])
        assert ts in engine_map, f"{label}: engine output missing index {i}"
        rv = ref_series[i]
        ev = engine_map[ts]
        assert math.isfinite(rv), f"{label}: non-finite reference value at {i}"
        max_dev = max(max_dev, abs(rv - ev))
        # exact once rounded to the engine's declared 4-decimal precision
        assert abs(round(rv, 4) - ev) <= 1e-9, (
            f"{label}: rounded reference != engine at index {i}: {rv} vs {ev}"
        )
    assert max_dev <= ENGINE_ROUNDING_TOL, (
        f"{label}: max deviation {max_dev} exceeds rounding half-step {ENGINE_ROUNDING_TOL}"
    )
    return max_dev


def test_cross_validate_cci_seeded() -> None:
    # CCI default period 20; both implementations share the exact formula,
    # so agreement within the engine's rounding half-step must hold on the
    # whole overlapping valid range (indices >= 19 of the 80-bar series).
    ref_series = ref_cci(BARS)  # defaults period=20
    engine_rows = eng.cci(ENGINE_BARS)  # defaults period=20
    assert len(engine_rows) == len(BARS) - 20 + 1
    _cross_check("cci", ref_series, engine_rows, 19)


def test_cross_validate_williams_seeded() -> None:
    # Williams %R default period 14; identical formula in both -> the only
    # honest deviation is the engine's 4-decimal rounding.
    ref_series = ref_williams_r(BARS)  # defaults period=14
    engine_rows = eng.williams(ENGINE_BARS)  # defaults period=14
    assert len(engine_rows) == len(BARS) - 14 + 1
    _cross_check("williams", ref_series, engine_rows, 13)


def test_cross_validate_adx_di_and_period2_line_seeded() -> None:
    # +DI/-DI use the identical Wilder seed in both implementations for ANY
    # period -> tight parity from index `period` on.  The ADX LINE is compared
    # at period=2, where the textbook seed (mean of the first `period` DX
    # values) coincides with the engine's first-DX seed, so exact parity is
    # computable (see the period-2 hand fixture above for why).
    r2 = ref_adx(BARS, period=2)
    e2 = eng.adx(ENGINE_BARS, period=2)
    assert len(e2["adx"]) == len(BARS) - 2
    _cross_check("adx.p2.line", r2["adx"], e2["adx"], 3)
    _cross_check("adx.p2.plus_di", r2["plus_di"], e2["plus_di"], 2)
    _cross_check("adx.p2.minus_di", r2["minus_di"], e2["minus_di"], 2)

    r14 = ref_adx(BARS, period=14)
    e14 = eng.adx(ENGINE_BARS, period=14)
    _cross_check("adx.p14.plus_di", r14["plus_di"], e14["plus_di"], 14)
    _cross_check("adx.p14.minus_di", r14["minus_di"], e14["minus_di"], 14)


def test_cross_validate_adx_convergence_tail() -> None:
    # ADX line at the default period 14: the reference uses the TEXTBOOK seed
    # (mean of DX[14..27] at index 27) while the engine seeds with DX[14].
    # Both then run the SAME Wilder recursion over the SAME (bit-identical)
    # DX inputs, so the deviation decays exactly by (period-1)/period per
    # bar: dev[j] = ((p-1)/p)^(j-27) * dev[27] with dev[27] <= 100 (both
    # values live in [0, 100]).  At j=200: 100*(13/14)^173 ~= 2.7e-4; adding
    # the engine's 4-decimal rounding (5e-5) stays under the asserted 5e-4.
    long_bars = fixture_bars("MR2-A:WAVE2-LONG", 320)
    long_engine_bars = _engine_bars(long_bars)
    r = ref_adx(long_bars, period=14)
    e = eng.adx(long_engine_bars, period=14)
    engine_map = {int(row["time"]): float(row["value"]) for row in e["adx"]}
    for j in range(200, len(long_bars)):
        ts = int(long_bars[j]["ts"])
        dev = abs(r["adx"][j] - engine_map[ts])
        assert dev <= 5e-4, f"adx convergence tail: dev {dev} at index {j}"
    # and the documented warm-up is exactly zero before 2*period-1
    assert r["adx"][:27] == [0.0] * 27


def test_wave2_reference_module_stays_independent() -> None:
    # guard for the three new functions: still no import of the engine module
    # (import-line scan, same pattern as test_indicator_catalog) and still no
    # dynamic-evaluation primitives anywhere in the file.
    import inspect

    src_lines = inspect.getsource(ref).splitlines()
    import_lines = [ln for ln in src_lines if ln.startswith(("import ", "from "))]
    assert import_lines, "sanity: reference module has imports"
    for ln in import_lines:
        assert "app.engines.indicators" not in ln, ln
        assert "indicators import" not in ln and "import indicators" not in ln, ln
    src = "\n".join(src_lines)
    for token in ("eval(", "exec(", "compile(", "__import__"):
        assert token not in src, token
