"""TabloKhani direct capability tests (WDA-D) — actual public surfaces, hand-derived.

Companion to ``docs/active/TABLOKHANI_CAPABILITY_MATRIX_2026-11-03.md``: every
capability row the matrix marks EXISTS pins a test HERE (or cites the
pre-existing hardening-wave tests — see "no duplication" below).

Capabilities exercised against the ACTUAL public functions/services:
- ``app.engines.tablocastic.rank_tablocastic``  — ranking order, limit, determinism,
  blank-symbol skip, stable output schema
- ``app.engines.tablocastic.compute_tablocastic`` — grade banding, honest
  insufficient-data flags (zero order book, no estimable cross)
- ``app.engines.screener.build_hot_money``      — exact tier boundaries
- ``app.services.market_service.MarketService.get_tablocastic`` — min-quality filter,
  honest empty state

NO DUPLICATION: 15 dedicated tablocastic/screener/big-moves unit tests already
exist in ``tests/test_tablocastic_screener_bigmoves_units.py`` (determinism of
``compute_tablocastic``, score bounds, order-book pressure direction, buy-queue
note, volume-spike sign flip, hour-pattern gap, cross-minutes clamp at the 45.0
case, hot-money tiering at 400M/150M/50M, hot-money ordering, hot-money empty,
big-moves delta/clamp/determinism/empty/min-score). This file deliberately uses
DIFFERENT hand-computed inputs (30.0-minute cross case, exact 200M/100M/99M tier
boundaries, service-level filters, rank-order surfaces) — complementary pins,
not re-runs.

Discipline: every expected value is hand-derived from the committed formulas
(arithmetic in comments) — never copied from an engine run; offline
(DATA_SOURCE=mock via conftest); no wall-clock, no network, no RNG.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.engines.metrics import compute_metrics
from app.engines.screener import build_hot_money
from app.engines.tablocastic import compute_tablocastic, rank_tablocastic
from app.models.schemas import SymbolSnapshot
from app.services.market_service import MarketService


def _snap(**over: Any) -> SymbolSnapshot:
    base: dict[str, Any] = dict(
        l18="فولاد",
        l30="فولاد مبارکه",
        pl=1000.0,
        py=1000.0,
        pc=1050.0,
        plp=0.0,
        pcp=0.0,
        tvol=5_000_000.0,
        tval=5_000_000_000.0,
        tno=10_000,
        Buy_CountI=100,
        Sell_CountI=100,
        Buy_I_Volume=2_000_000.0,
        Sell_I_Volume=1_000_000.0,
        Buy_CountN=5,
        Sell_CountN=5,
        Buy_N_Volume=100_000.0,
        Sell_N_Volume=100_000.0,
        qd1=500.0,
        pd1=1000.0,
        qd2=300.0,
        pd2=999.0,
        qd3=200.0,
        pd3=998.0,
        qo1=500.0,
        po1=1001.0,
        qo2=300.0,
        po2=1002.0,
        qo3=200.0,
        po3=1003.0,
        tmax=1100.0,
        tmin=900.0,
        avg_vol_30d=1_000_000.0,
    )
    base.update(over)
    return SymbolSnapshot(**base)


def _strong_board() -> SymbolSnapshot:
    """Textbook strong board: buy-queue at ceiling + heavy individual buying.

    Hand-derived component dominance over the neutral base (from the committed
    formulas): demand_pressure ≈ 9.15 vs 1.0; buy_per_capita 400M vs 20M;
    positive plp 9.8; in_buy_queue +12 → d_plus clamps at 100 vs ≈38;
    golden per-cap/power/volume/demand terms all higher → golden 100 vs ≈57;
    m_plus 75 vs ≈17; entry ≈77 vs ≈39 → quality ≈90 vs ≈41.
    """
    return _snap(
        l18="قوی",
        pl=1098.0,
        py=1000.0,
        plp=9.8,
        qd1=1000.0,
        qo1=0.0,
        po1=0.0,
        Buy_I_Volume=40_000_000.0,
        Sell_I_Volume=1_000_000.0,
    )


def _dead_board() -> SymbolSnapshot:
    """Textbook dead board: sell-side pressure + heavy individual selling.

    Hand-derived: demand_pressure ≈ 0.11; buy_per_capita 1M; buy_power ≈ 0.0025;
    plp −9.8 → d_plus ≈ 2; m_plus negative (clamped to 0 in the quality mix);
    golden ≈ 22 → quality ≈ 14.
    """
    return _snap(
        l18="مرده",
        pl=902.0,
        py=1000.0,
        plp=-9.8,
        qd1=100.0,
        qo1=5000.0,
        Buy_I_Volume=100_000.0,
        Sell_I_Volume=40_000_000.0,
    )


# ---------------------------------------------------------------------------
# rank_tablocastic — ranking order, limit, determinism, schema
# ---------------------------------------------------------------------------


def test_rank_tablocastic_orders_strong_neutral_dead() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    strong, neutral, dead = _strong_board(), _snap(l18="خنثی"), _dead_board()
    rows = rank_tablocastic([dead, strong, neutral], cfg=cfg)
    # Full order pinned (input deliberately shuffled): the board-quality sort
    # key (quality_score, golden_number, d_plus) must reproduce the hand-derived
    # dominance chain strong ≈90 > neutral ≈41 > dead ≈14 on quality, with the
    # same strict chain on each key component.
    assert [r["symbol"] for r in rows] == ["قوی", "خنثی", "مرده"]
    assert rows[0]["quality_score"] > rows[1]["quality_score"] > rows[2]["quality_score"]
    assert rows[0]["golden_number"] > rows[1]["golden_number"] > rows[2]["golden_number"]
    assert rows[0]["d_plus"] > rows[1]["d_plus"] > rows[2]["d_plus"]


def test_rank_tablocastic_limit_truncates_to_top_ranked() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    symbols = [_strong_board(), _snap(l18="خنثی"), _dead_board()]
    top2 = rank_tablocastic(symbols, cfg=cfg, limit=2)
    assert [r["symbol"] for r in top2] == ["قوی", "خنثی"]  # the derived top-2
    top1 = rank_tablocastic(symbols, cfg=cfg, limit=1)
    assert [r["symbol"] for r in top1] == ["قوی"]
    # a limit beyond the input keeps everything, in the derived order
    assert [r["symbol"] for r in rank_tablocastic(symbols, cfg=cfg, limit=10)] == [
        "قوی",
        "خنثی",
        "مرده",
    ]


def test_rank_tablocastic_empty_input_honest_empty() -> None:
    assert rank_tablocastic([], cfg=Settings(DATA_SOURCE="mock")) == []


def test_rank_tablocastic_double_run_identical() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    symbols = [_strong_board(), _snap(l18="خنثی"), _dead_board()]
    first = rank_tablocastic(symbols, cfg=cfg)
    second = rank_tablocastic(symbols, cfg=cfg)
    assert first == second  # dict-level equality over every field incl. notes


def test_rank_tablocastic_skips_blank_symbol_rows() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    blank = _snap(l18="")
    rows = rank_tablocastic([blank, _strong_board()], cfg=cfg)
    assert [r["symbol"] for r in rows] == ["قوی"]  # blank l18 never ranked


def test_rank_rows_carry_stable_output_schema() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    rows = rank_tablocastic([_strong_board()], cfg=cfg)
    assert len(rows) == 1
    # The published row contract (TablocasticResult.to_dict) — pinned so
    # downstream consumers (API/UI) can rely on the field set.
    assert set(rows[0].keys()) == {
        "symbol",
        "name",
        "industry",
        "pl",
        "plp",
        "pc",
        "pcp",
        "d_plus",
        "m_plus",
        "m_over_d",
        "golden_number",
        "queue_power",
        "supply_pressure",
        "demand_pressure",
        "cross_minutes",
        "cross_direction",
        "hour_pattern",
        "smart_flow",
        "quality_score",
        "grade",
        "notes",
    }


# ---------------------------------------------------------------------------
# compute_tablocastic — grade banding + honest insufficient-data flags
# ---------------------------------------------------------------------------


def test_grade_banding_extremes_hand_derived() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    strong = compute_tablocastic(_strong_board(), cfg)
    # Strong-board hand math: golden clamps at 100 (→ 35), d_plus at 100 (→ 25),
    # m_plus 75 (→ 15), entry ≈77 (→ ≈15.4) → quality ≈ 90 ≥ 85 → "A+".
    assert strong.grade == "A+"
    dead = compute_tablocastic(_dead_board(), cfg)
    # Dead-board hand math: golden ≈22 (→ ≈7.7), d_plus ≈2 (→ ≈0.5),
    # m_plus term 0, entry ≈31 (→ ≈6.2) → quality ≈ 14 ≤ 45 → "D".
    assert dead.grade == "D"
    # the grade vocabulary is closed
    for grade in (strong.grade, dead.grade):
        assert grade in {"A+", "A", "B", "C", "D"}


def test_zero_flow_board_honest_flags() -> None:
    """Insufficient-data honesty: no order book, no flow, no estimable cross."""
    cfg = Settings(DATA_SOURCE="mock")
    empty_board = _snap(
        l18="خالی",
        qd1=0.0,
        pd1=0.0,
        qd2=0.0,
        pd2=0.0,
        qd3=0.0,
        pd3=0.0,
        qo1=0.0,
        po1=0.0,
        qo2=0.0,
        po2=0.0,
        qo3=0.0,
        po3=0.0,
        pl=1000.0,
        py=1000.0,
        pc=1000.0,  # pc == pl → no gap → no cross estimable
        pcp=0.0,
        plp=0.0,
        Buy_I_Volume=0.0,
        Sell_I_Volume=0.0,
        tvol=0.0,
    )
    r = compute_tablocastic(empty_board, cfg)
    # Order-book pressure: buy_val_ob = sell_val_ob = 0 → both pressures are
    # the honest _div default 0/1 = 0.0 (NOT fabricated demand).
    assert r.demand_pressure == 0.0
    assert r.supply_pressure == 0.0
    # buy_per_capita 0/0 → metrics default 0; buy_power defaults to 1.0 →
    # d_plus = 0 + 0 + 0 + 0 (no queue contact: dist-to-ceiling ≈ 9.1% > 1.5%,
    # plp 0 gives min(8, 0) = 0) = 0.0; m_plus: individual_net_value = 0 → 0.0.
    assert r.d_plus == 0.0
    assert r.m_plus == 0.0
    # m_over_d = _div(0, max(0, 1)) = 0/1 = 0.0 — the honest default, not a ratio.
    assert r.m_over_d == 0.0
    # gap = 0 (pc == pl) → no crossing estimable: cross_minutes stays None and
    # the direction is "none" — the estimate is withheld, not invented.
    assert r.cross_minutes is None
    assert r.cross_direction == "none"
    assert r.hour_pattern is False
    # quality = golden·0.35 + d_plus·0.25 + 0 + 0 with golden = 12.5 (buy_power
    # default 1.0 → power_norm 1/2·25) → 4.375 → 4.4 ≤ 45 → "D".
    assert r.quality_score == pytest.approx(4.4)
    assert r.grade == "D"


def test_cross_minutes_hand_derived_distinct_case() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    # gap = pc - pl = 1025 - 1000 = 25; day_range = max(|1075-925|, |1000-1000|, 1)
    # = 150 → speed = 150/180 → minutes = 25 / (150/180) = 25·180/150 = 30.0.
    # Direction "up": gap > 0 and buy_power = (20M/100)/(10M/100) = 2.0 ≥ 1 and
    # individual_net_value = (2M − 1M)·1000 = +1e9 > 0.
    s = _snap(pl=1000.0, py=1000.0, pc=1025.0, pmax=1075.0, pmin=925.0)
    r = compute_tablocastic(s, cfg)
    assert r.cross_minutes == pytest.approx(30.0)
    assert r.cross_direction == "up"


# ---------------------------------------------------------------------------
# build_hot_money — exact tier boundaries (≥ semantics pinned)
# ---------------------------------------------------------------------------


def test_hot_money_exact_tier_boundaries() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    # buy_per_capita = Buy_I_Volume·pl / Buy_CountI = Buy_I_Volume·1000/100:
    #   20M  → exactly 200,000,000  == hot_money_threshold → HOT (≥ boundary)
    #   10M  → exactly 100,000,000  == hot_money_plus_min  → PLUS (≥ boundary)
    #   9.9M → 99,000,000           <  hot_money_plus_min  → absent from both
    hot = _snap(l18="داغ", Buy_I_Volume=20_000_000.0, Sell_I_Volume=100_000.0)
    plus = _snap(l18="پلاس", Buy_I_Volume=10_000_000.0, Sell_I_Volume=100_000.0)
    low = _snap(l18="کم", Buy_I_Volume=9_900_000.0, Sell_I_Volume=100_000.0)
    snaps = [hot, plus, low]
    metrics = {s.l18: compute_metrics(s, cfg) for s in snaps}
    hot_rows, plus_rows = build_hot_money(snaps, metrics, cfg)
    assert [r.symbol for r in hot_rows] == ["داغ"]
    assert all(r.tier == "hot" and r.side == "buy" for r in hot_rows)
    assert [r.symbol for r in plus_rows] == ["پلاس"]
    assert all(r.tier == "plus" and r.side == "buy" for r in plus_rows)
    assert all(r.symbol != "کم" for r in hot_rows + plus_rows)


# ---------------------------------------------------------------------------
# MarketService.get_tablocastic — service-level min-quality filter + honest empty
# ---------------------------------------------------------------------------


def _bare_service() -> MarketService:
    """MarketService without provider wiring (pattern of test_refresh_false_fresh)."""
    service = MarketService.__new__(MarketService)
    service._last_tablocastic = []
    service._last_symbols = []
    return service


def test_service_get_tablocastic_min_quality_filter() -> None:
    service = _bare_service()
    service._last_tablocastic = [
        {"symbol": "الف", "quality_score": 90.0},
        {"symbol": "ب", "quality_score": 40.0},
        {"symbol": "پ", "quality_score": 65.0},
    ]
    # min_quality=60 keeps ≥ 60 only, preserving the ranked order: الف(90), پ(65).
    rows = service.get_tablocastic(limit=10, min_quality=60.0)
    assert [r["symbol"] for r in rows] == ["الف", "پ"]
    # the limit applies AFTER the quality filter
    assert [r["symbol"] for r in service.get_tablocastic(limit=1, min_quality=60.0)] == [
        "الف"
    ]
    # min_quality=0 keeps everything
    assert len(service.get_tablocastic(limit=10, min_quality=0.0)) == 3


def test_service_get_tablocastic_empty_state_honest_empty() -> None:
    # No cached ranking and no cached symbols → the service falls back to
    # ranking an empty board: the honest answer is [], never fabricated rows.
    service = _bare_service()
    assert service.get_tablocastic(limit=10, min_quality=0.0) == []
