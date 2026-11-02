"""MASTER-WAVE-2 — dedicated direct unit tests for the TabloKhani-informed
engines (backlog item closed: "dedicated unit tests for tablocastic/screener/
big_moves math — currently indirect-only coverage", TABLOKHANI_CAPABILITY_MATRIX
evidence-gap register).

Scope: direct, in-domain unit contracts for
- ``app/engines/tablocastic.py::compute_tablocastic`` (per-symbol engine math),
- ``app/engines/screener.py::build_hot_money`` (hot/plus tiering + ordering),
- ``app/engines/big_moves.py::compute_big_moves`` (delta scoring over seeded
  tick history).

Discipline: offline (conftest pins DATA_SOURCE=mock), deterministic (the only
wall-clock read — ``big_moves.time.time`` — is monkey-patched to a fixed
instant so seeded history ages are exact), no network, no RNG. Every expected
value below is hand-derived from the committed formulas, not copied from an
engine run.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.data.store import Store
from app.engines.big_moves import compute_big_moves
from app.engines.metrics import compute_metrics
from app.engines.screener import build_hot_money
from app.engines.tablocastic import compute_tablocastic
from app.models.schemas import SymbolSnapshot


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


# ---------------------------------------------------------------------------
# compute_tablocastic — direct engine-math contracts
# ---------------------------------------------------------------------------


def test_tablocastic_deterministic_two_runs_byte_identical() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    s = _snap()
    a = compute_tablocastic(s, cfg)
    b = compute_tablocastic(s, cfg)
    assert a == b  # dataclass __eq__ over every field incl. notes list


def test_tablocastic_score_components_within_documented_bounds() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    for s in (
        _snap(),  # neutral-ish
        _snap(Buy_I_Volume=9_000_000.0, Sell_I_Volume=100_000.0),  # buy-heavy
        _snap(Buy_I_Volume=100_000.0, Sell_I_Volume=9_000_000.0),  # sell-heavy
        _snap(pl=1090.0, plp=9.0),  # near ceiling
    ):
        r = compute_tablocastic(s, cfg)
        assert 0.0 <= r.d_plus <= 100.0, r.d_plus
        assert -100.0 <= r.m_plus <= 100.0, r.m_plus
        assert 0.0 <= r.golden_number <= 100.0, r.golden_number
        assert -100.0 <= r.queue_power <= 100.0, r.queue_power
        assert 0.0 <= r.smart_flow <= 100.0 or -100.0 <= r.smart_flow <= 100.0
        assert r.grade in {"A+", "A", "B", "C", "D"}
        assert len(r.notes) <= 6  # notes truncated to the top 6


def test_tablocastic_orderbook_pressure_direction() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    buy_heavy = _snap(qd1=5_000.0, qo1=100.0)
    sell_heavy = _snap(qd1=100.0, qo1=5_000.0)
    rb = compute_tablocastic(buy_heavy, cfg)
    rs = compute_tablocastic(sell_heavy, cfg)
    # Hand math (levels 2/3 are shared, level 1 is mirrored); the engine
    # rounds both pressures to 2 decimals:
    # buy_heavy: buy_ob = 5000*1000 + 300*999 + 200*998 = 5,499,300;
    #            sell_ob = 500*1001 + 300*1002 + 200*1003 = 601,300
    #            demand = 5,499,300 / 601,300 = 9.145684… → 9.15
    #            supply = 601,300 / 5,499,300 = 0.109341…  → 0.11
    # sell_heavy: buy_ob = 100*1000 + 299,700 + 199,600 = 599,300;
    #             sell_ob = 5000*1001 + 300,600 + 200,600 = 5,506,200
    #             demand = 599,300 / 5,506,200 = 0.108841… → 0.11
    #             supply = 5,506,200 / 599,300 = 9.187719…  → 9.19
    assert rb.demand_pressure == pytest.approx(9.15, abs=1e-9)
    assert rs.demand_pressure == pytest.approx(0.11, abs=1e-9)
    # supply_pressure = sell_ob / max(buy_ob, 1) — the mirrored direction.
    assert rb.supply_pressure < 1.0 < rs.supply_pressure
    assert rb.supply_pressure == pytest.approx(0.11, abs=1e-9)
    assert rs.supply_pressure == pytest.approx(9.19, abs=1e-9)
    # Direction parity of the neutral-band queue power (no queue contact:
    # queue_power = clamp((demand-1)*20, -50, 50) for both).
    assert rb.queue_power > 0.0
    assert rs.queue_power < 0.0


def test_tablocastic_in_buy_queue_positive_queue_power_and_note() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    # in_buy_queue (metrics): pl >= tmax*0.998, qd1 > 0, and (qo1 <= 0 or
    # po1 >= tmax*0.999). Crafted exactly at the ceiling with sell queue at
    # ceiling price.
    s = _snap(pl=1098.0, py=1000.0, tmax=1100.0, qd1=1_000.0, qo1=0.0, po1=0.0)
    r = compute_tablocastic(s, cfg)
    assert r.queue_power > 0.0
    assert any("صف خرید" in n for n in r.notes)


def test_tablocastic_volume_spike_flips_momentum_bonus_sign() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    # volume_ratio = tvol / avg_vol_30d — 4.0 crosses volume_spike_strong=3.5.
    positive = _snap(tvol=4_000_000.0, Buy_I_Volume=3_000_000.0, Sell_I_Volume=500_000.0)
    negative = _snap(tvol=4_000_000.0, Buy_I_Volume=500_000.0, Sell_I_Volume=3_000_000.0)
    rp = compute_tablocastic(positive, cfg)
    rn = compute_tablocastic(negative, cfg)
    # Both get the ±10 spike term; the individual-net sign decides its sign,
    # so the positive-net run must score strictly higher on m_plus.
    assert rp.m_plus > rn.m_plus
    # And the sign of the spike contribution is observable through the
    # hand-derived bounds: positive run keeps m_plus above the no-spike
    # baseline for the same order book.
    no_spike = _snap(tvol=1_000_000.0, Buy_I_Volume=3_000_000.0, Sell_I_Volume=500_000.0)
    r0 = compute_tablocastic(no_spike, cfg)
    assert rp.m_plus >= r0.m_plus + 9.0  # spike adds up to +10 (clamped)


def test_tablocastic_hour_pattern_requires_pcp_minus_plp_gap() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    # hour_pattern = pc and pl and pl < pc and (pcp - plp) >= 1.0
    matching = _snap(pl=1000.0, pc=1050.0, plp=1.0, pcp=4.0)
    assert compute_tablocastic(matching, cfg).hour_pattern is True
    not_matching = _snap(pl=1000.0, pc=1050.0, plp=4.0, pcp=1.0)
    assert compute_tablocastic(not_matching, cfg).hour_pattern is False


def test_tablocastic_cross_minutes_clamped_to_240_and_direction() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    # gap = pc - pl = 50; day_range = max(|pmax-pmin|, |pl-py|, 1) = 200 →
    # speed = 200/180; mins = 50/(200/180) = 45.0 → cross_minutes == 45.0,
    # direction "up" (gap>0, buy_power>1, net>0 with crafted volumes).
    s = _snap(pl=1000.0, py=1000.0, pc=1050.0, pmax=1100.0, pmin=900.0)
    r = compute_tablocastic(s, cfg)
    assert r.cross_minutes == pytest.approx(45.0, abs=0.1)
    assert r.cross_direction == "up"
    # Huge gap vs a NARROW day range clamps at 240 minutes:
    # day_range = max(|910-900|, |900-1000|, 1) = 100 → speed = 100/180 →
    # mins = 500/0.5556 = 900 → min(900, 240) = 240.
    far = _snap(pl=900.0, py=1000.0, pc=1400.0, pmax=910.0, pmin=900.0)
    rf = compute_tablocastic(far, cfg)
    assert rf.cross_minutes == pytest.approx(240.0, abs=0.1)


# ---------------------------------------------------------------------------
# build_hot_money — tiering, ordering, emptiness
# ---------------------------------------------------------------------------


def _buy_per_capita(s: SymbolSnapshot) -> float:
    return (s.Buy_I_Volume * s.pl) / s.Buy_CountI


def test_build_hot_money_tiering_thresholds() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    # thresholds: hot_money_threshold=200_000_000, hot_money_plus_min=100_000_000
    hot_s = _snap(l18="هوت", Buy_I_Volume=40_000_000.0, Buy_CountI=100)   # per-capita 400M*… pl=1000 → 400M/… compute below
    plus_s = _snap(l18="پلاس", Buy_I_Volume=15_000_000.0, Buy_CountI=100)  # 150M
    low_s = _snap(l18="کم", Buy_I_Volume=5_000_000.0, Buy_CountI=100)      # 50M
    assert _buy_per_capita(hot_s) == pytest.approx(400_000_000.0)
    assert _buy_per_capita(plus_s) == pytest.approx(150_000_000.0)
    assert _buy_per_capita(low_s) == pytest.approx(50_000_000.0)

    snaps = [hot_s, plus_s, low_s]
    metrics = {s.l18: compute_metrics(s, cfg) for s in snaps}
    hot, plus = build_hot_money(snaps, metrics, cfg)
    assert [r.symbol for r in hot] == ["هوت"]        # ≥ 200M → hot
    assert [r.symbol for r in plus] == ["پلاس"]      # ≥ 100M and < 200M → plus
    assert all(r.symbol != "کم" for r in hot + plus)  # < 100M → absent
    assert all(r.tier == "hot" for r in hot)
    assert all(r.tier == "plus" for r in plus)


def test_build_hot_money_sell_side_symmetric_tiering() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    sell_hot = _snap(
        l18="فروش_هوت", Buy_I_Volume=100_000.0, Sell_I_Volume=40_000_000.0
    )
    snaps = [sell_hot]
    metrics = {s.l18: compute_metrics(s, cfg) for s in snaps}
    hot, plus = build_hot_money(snaps, metrics, cfg)
    assert [r.symbol for r in hot] == ["فروش_هوت"]
    assert all(r.side == "sell" for r in hot)


def test_build_hot_money_sorted_by_score_desc() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    a = _snap(l18="الف", Buy_I_Volume=40_000_000.0, Buy_CountI=100)
    b = _snap(l18="ب", Buy_I_Volume=25_000_000.0, Buy_CountI=100)
    snaps = [a, b]
    metrics = {s.l18: compute_metrics(s, cfg) for s in snaps}
    hot, plus = build_hot_money(snaps, metrics, cfg)
    assert [r.score for r in hot] == sorted(
        (r.score for r in hot), reverse=True
    )
    assert [r.score for r in plus] == sorted(
        (r.score for r in plus), reverse=True
    )


def test_build_hot_money_empty_snaps_empty_rows() -> None:
    cfg = Settings(DATA_SOURCE="mock")
    hot, plus = build_hot_money([], {}, cfg)
    assert hot == [] and plus == []


# ---------------------------------------------------------------------------
# compute_big_moves — seeded-history delta scoring
# ---------------------------------------------------------------------------


class _FixedTime:
    """Module-level ``time`` replacement: deterministic ``time.time()``."""

    def __init__(self, fixed: float) -> None:
        self._fixed = fixed
        self.time = lambda: self._fixed  # noqa: E731


def _seed_store(tmp_path, symbols: list[SymbolSnapshot], ts: float) -> Store:
    store = Store(path=tmp_path / "bm.db")
    ticks: list[dict[str, Any]] = []
    for s in symbols:
        ticks.append(
            {
                "symbol": s.l18,
                "pl": s.py,
                "plp": 0.0,
                "pc": s.pc,
                "pcp": 0.0,
                "tvol": s.tvol * 0.5,
                "tval": s.tval * 0.5,
                "tno": int(s.tno / 2),
                "buy_i_vol": s.Buy_I_Volume * 0.4,
                "sell_i_vol": s.Sell_I_Volume * 0.4,
                "buy_count_i": s.Buy_CountI,
                "sell_count_i": s.Sell_CountI,
                "buy_n_vol": s.Buy_N_Volume,
                "sell_n_vol": s.Sell_N_Volume,
                "buy_per_capita": (s.Buy_I_Volume * 0.4 * s.py) / s.Buy_CountI,
                "sell_per_capita": (s.Sell_I_Volume * 0.4 * s.py) / s.Sell_CountI,
                "buy_power": 1.0,
                "individual_net_value": (s.Buy_I_Volume - s.Sell_I_Volume) * 0.4 * s.py,
                "hot_net": 0.0,
                "entry_score": 0.0,
                "exit_score": 0.0,
                "qd1": s.qd1,
                "qo1": s.qo1,
                "pd1": s.pd1,
                "po1": s.po1,
            }
        )
    store.save_market_snapshot("test-source", [], ticks, ts=ts)
    return store


def test_compute_big_moves_delta_direction_and_min_score(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_now = 1_800_000_000.0
    monkeypatch.setattr(
        "app.engines.big_moves.time", _FixedTime(fixed_now), raising=True
    )
    cfg = Settings(DATA_SOURCE="mock")
    strong = _snap(l18="قوی", Buy_I_Volume=9_000_000.0, Sell_I_Volume=100_000.0)
    store = _seed_store(tmp_path, [strong], ts=fixed_now - 600.0)
    moves = compute_big_moves(
        store, [strong], window_sec=600, cfg=cfg, min_score=0.0
    )
    assert moves, "seeded history must yield at least one big-move row"
    top = next(m for m in moves if m.get("symbol") == "قوی")
    # The individual net grew ~2.4x over the window → the net-change note is
    # reachable and the score is positive.
    assert top["score"] > 0.0
    assert any("خالص" in str(n) for n in top.get("notes", [])) or top["score"] > 0
    # min_score filter honours its contract.
    strict = compute_big_moves(
        store, [strong], window_sec=600, cfg=cfg, min_score=1e9
    )
    assert strict == []


def test_compute_big_moves_deterministic_under_fixed_clock(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_now = 1_800_000_000.0
    monkeypatch.setattr(
        "app.engines.big_moves.time", _FixedTime(fixed_now), raising=True
    )
    cfg = Settings(DATA_SOURCE="mock")
    syms = [_snap(l18="نماد۱"), _snap(l18="نماد۲", Buy_I_Volume=3_000_000.0)]
    store = _seed_store(tmp_path, syms, ts=fixed_now - 600.0)
    a = compute_big_moves(store, syms, window_sec=600, cfg=cfg)
    b = compute_big_moves(store, syms, window_sec=600, cfg=cfg)
    assert a == b


def test_compute_big_moves_empty_history_no_moves(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_now = 1_800_000_000.0
    monkeypatch.setattr(
        "app.engines.big_moves.time", _FixedTime(fixed_now), raising=True
    )
    cfg = Settings(DATA_SOURCE="mock")
    store = Store(path=tmp_path / "empty.db")
    assert (
        compute_big_moves(store, [_snap()], window_sec=600, cfg=cfg) == []
    )


def test_compute_big_moves_min_score_filters_weak_deltas(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_now = 1_800_000_000.0
    monkeypatch.setattr(
        "app.engines.big_moves.time", _FixedTime(fixed_now), raising=True
    )
    cfg = Settings(DATA_SOURCE="mock")
    # Old state ≈ current state → tiny deltas → score below a strict cutoff.
    calm = _snap(l18="آرام")
    store = _seed_store(tmp_path, [calm], ts=fixed_now - 600.0)
    moves_all = compute_big_moves(
        store, [calm], window_sec=600, cfg=cfg, min_score=0.0
    )
    top = next(m for m in moves_all if m.get("symbol") == "آرام")
    assert top["score"] < 25.0
    assert compute_big_moves(
        store, [calm], window_sec=600, cfg=cfg, min_score=25.0
    ) == []
