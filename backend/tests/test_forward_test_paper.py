"""Offline tests for the paper forward-test runtime (MASTER-RADAR directive,
Wave 6 / PKG-D, directive §E).

Scope pinned here:
- Hash-chained append-only ledger: integrity, independent hash recomputation,
  tamper evidence, no deletion API.
- State machine: pause/resume/stop with injected timestamps only.
- Entry->fill pipeline: exact cost arithmetic identical to the SHARED
  execution model (app.engines.execution_model) — no second cost model.
- Pessimistic exits (stop before target), refusal paths, outcome maturity,
  delay observations, data gaps, determinism, and source hygiene (no egress).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.engines.execution_model import (
    EXECUTION_MODEL_VERSION,
    ExecutionModelConfig,
    cost_breakdown,
    simulate_fill,
)
from app.engines.forward_test_paper import (
    ENGINE_VERSION,
    ForwardRunState,
    ForwardTestConfig,
    ForwardTestRuntime,
    MaturityRules,
    PaperDecision,
    PaperLedger,
    verify_entry_chain,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "engines" / "forward_test_paper.py"

START_TS = 1_700_000_000
STEP = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def bar(ts: int, o: float, h: float, l: float, c: float, v: float = 1_000_000.0) -> dict:
    return {"ts": ts, "o": o, "h": h, "l": l, "c": c, "v": v}


def trend_bars(closes: list[float], start_ts: int = START_TS, step: int = STEP, pad: float = 1.0) -> list[dict]:
    """Bars whose open == previous close; high/low padded around the body."""
    bars = []
    prev_close = closes[0]
    for i, close in enumerate(closes):
        o = prev_close
        bars.append(bar(start_ts + i * step, o, max(o, close) + pad, min(o, close) - pad, close))
        prev_close = close
    return bars


def rising_bars(n: int = 10, start: float = 100.0) -> list[dict]:
    return trend_bars([start + i for i in range(n)])


class ScriptedAdapter:
    """Minimal PaperAdapter: decisions keyed by bar index, flat otherwise."""

    strategy_id = "scripted"

    def __init__(self, decisions: dict[int, PaperDecision] | None = None):
        self._decisions = dict(decisions or {})
        self.prepared: list[list[dict]] = []

    def prepare(self, bars: list[dict]) -> None:
        self.prepared.append(bars)

    def decide(self, index: int) -> PaperDecision:
        return self._decisions.get(index, PaperDecision())


def make_runtime(
    *, run_id: str = "run-1", maturity: MaturityRules | None = None, **exec_kwargs
) -> tuple[ForwardTestRuntime, PaperLedger]:
    cfg = ForwardTestConfig(
        run_id=run_id,
        strategy_id="strat-a",
        strategy_version="v1.0.0",
        execution=ExecutionModelConfig(**exec_kwargs),
        maturity=maturity or MaturityRules(),
    )
    ledger = PaperLedger()
    return ForwardTestRuntime(cfg, ledger), ledger


def kinds_of(ledger: PaperLedger) -> list[str]:
    return [e.kind for e in ledger.entries]


def all_of(ledger: PaperLedger, kind: str) -> list:
    return [e for e in ledger.entries if e.kind == kind]


def first_of(ledger: PaperLedger, kind: str):
    return next(e for e in ledger.entries if e.kind == kind)


# Default costed config used across pipeline tests.
COSTED = dict(commission_pct=0.1, spread_pct=0.2, slippage_pct=0.1)


# ---------------------------------------------------------------------------
# Ledger chain integrity
# ---------------------------------------------------------------------------


class TestLedgerChain:
    def test_append_and_verify_chain_ok(self):
        ledger = PaperLedger()
        for i in range(5):
            ledger.append("SIGNAL", 1000 + i, {"n": i, "x": 1.5})
        assert len(ledger) == 5
        assert ledger.verify_chain() == (True, None)

    def test_prev_hash_linkage_and_seq_zero_empty_prev(self):
        ledger = PaperLedger()
        for i in range(4):
            ledger.append("FILL", 1000 + i, {"i": i})
        entries = ledger.entries
        assert entries[0].prev_hash == ""
        assert entries[0].seq == 0
        for prev, cur in zip(entries, entries[1:]):
            assert cur.prev_hash == prev.entry_hash
            assert cur.seq == prev.seq + 1

    def test_entry_hash_matches_independent_recompute(self):
        ledger = PaperLedger()
        ledger.append("RUN_STARTED", 1000, {"run_id": "r"})
        ledger.append("SIGNAL", 1060, {"k": "v", "price": 12.5})
        ledger.append("FILL", 1120, {"qty": 3.0})
        for e in ledger.entries:
            blob = json.dumps([e.seq, e.kind, e.ts_utc, e.payload, e.prev_hash],
                              sort_keys=True, separators=(",", ":"))
            expected = hashlib.sha256(blob.encode("utf-8")).hexdigest()
            assert e.entry_hash == expected

    def test_tampered_payload_fails_at_exact_seq(self):
        ledger = PaperLedger()
        for i in range(4):
            ledger.append("STATE_CHANGE", 1000 + i, {"i": i})
        doctored = [
            e.model_copy(update={"payload": {**e.payload, "tamper": True}}) if e.seq == 2 else e
            for e in ledger.entries
        ]
        assert verify_entry_chain(doctored) == (False, 2)

    def test_tampered_ts_utc_fails_at_exact_seq(self):
        ledger = PaperLedger()
        for i in range(4):
            ledger.append("DELAY_OBSERVATION", 1000 + i, {"i": i})
        doctored = [
            e.model_copy(update={"ts_utc": e.ts_utc + 1}) if e.seq == 1 else e
            for e in ledger.entries
        ]
        assert verify_entry_chain(doctored) == (False, 1)

    def test_rejects_non_finite_payload(self):
        ledger = PaperLedger()
        with pytest.raises(ValueError):
            ledger.append("SIGNAL", 1000, {"x": float("nan")})
        with pytest.raises(ValueError):
            ledger.append("SIGNAL", 1000, {"x": float("inf")})

    def test_rejects_non_serializable_payload(self):
        ledger = PaperLedger()
        with pytest.raises(ValueError):
            ledger.append("SIGNAL", 1000, {"s": {1, 2}})
        with pytest.raises(ValueError):
            ledger.append("SIGNAL", 1000, {"o": object()})

    def test_rejects_unknown_kind(self):
        ledger = PaperLedger()
        with pytest.raises(ValueError):
            ledger.append("NOT_A_KIND", 1000, {})

    def test_payload_deep_copied_at_append(self):
        ledger = PaperLedger()
        payload = {"nested": {"a": [1, 2]}}
        ledger.append("SIGNAL", 1000, payload)
        payload["nested"]["a"].append(3)
        payload["nested"]["b"] = "injected"
        entry = ledger.entries[0]
        assert entry.payload == {"nested": {"a": [1, 2]}}
        assert ledger.verify_chain() == (True, None)

    def test_no_delete_clear_truncate_api(self):
        ledger = PaperLedger()
        for name in ("delete", "clear", "truncate", "pop", "remove", "purge", "drop", "reset"):
            assert not hasattr(ledger, name), f"ledger must not expose {name!r}"

    def test_verify_empty_chain_ok(self):
        assert PaperLedger().verify_chain() == (True, None)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class TestStateMachine:
    def test_run_started_recorded_lazily_with_injected_ts(self):
        rt, ledger = make_runtime()
        bars = rising_bars(3)
        rt.process_bars("X", bars, ScriptedAdapter())
        first = ledger.entries[0]
        assert first.kind == "RUN_STARTED"
        assert first.ts_utc == bars[0]["ts"]  # injected from bar data, never a clock
        assert first.prev_hash == ""

    def test_pause_stops_processing_zero_bars_no_fills(self):
        rt, ledger = make_runtime()
        adapter = ScriptedAdapter({2: PaperDecision(entry=True)})
        rt.pause(999)
        assert rt.state is ForwardRunState.PAUSED
        summary = rt.process_bars("X", rising_bars(6), adapter)
        assert summary.bars_processed == 0
        assert rt.summary().bars_processed == 0
        assert rt.summary().signals_filled == 0
        assert all_of(ledger, "FILL") == []
        assert all_of(ledger, "SIGNAL") == []
        assert adapter.prepared == []  # prepare never called while paused

    def test_paused_noop_recorded_once_per_pause(self):
        rt, ledger = make_runtime()
        bars = rising_bars(4)
        rt.pause(999)
        rt.process_bars("X", bars, ScriptedAdapter())
        rt.process_bars("X", bars, ScriptedAdapter())
        skips = [e for e in all_of(ledger, "STATE_CHANGE") if e.payload.get("event") == "PROCESS_BARS_SKIPPED"]
        assert len(skips) == 1  # recorded once, not per-bar spam
        rt.resume(1_500)
        rt.pause(1_600)
        rt.process_bars("X", bars, ScriptedAdapter())
        skips = [e for e in all_of(ledger, "STATE_CHANGE") if e.payload.get("event") == "PROCESS_BARS_SKIPPED"]
        assert len(skips) == 2  # one per pause episode

    def test_resume_continues_and_ledger_order(self):
        rt, ledger = make_runtime()
        rt.process_bars("X", rising_bars(3), ScriptedAdapter())
        rt.pause(1_000_000)
        paused_summary = rt.process_bars("X", rising_bars(3), ScriptedAdapter())
        assert paused_summary.bars_processed == 0
        rt.resume(1_100_000)
        adapter = ScriptedAdapter({0: PaperDecision(entry=True)})
        rt.process_bars("X", rising_bars(6), adapter)
        assert kinds_of(ledger) == [
            "RUN_STARTED",
            "STATE_CHANGE",  # paused
            "STATE_CHANGE",  # process_bars skipped note
            "STATE_CHANGE",  # resumed
            "SIGNAL",
            "FILL",
            "POSITION_UPDATE",
            "DELAY_OBSERVATION",
        ]
        assert rt.summary().signals_filled == 1

    def test_stop_is_terminal_valueerror(self):
        rt, _ = make_runtime()
        rt.stop(999)
        assert rt.state is ForwardRunState.STOPPED
        with pytest.raises(ValueError):
            rt.process_bars("X", rising_bars(3), ScriptedAdapter())
        with pytest.raises(ValueError):
            rt.stop(1_000)  # double stop refused

    def test_pause_after_stop_raises(self):
        rt, _ = make_runtime()
        rt.stop(999)
        with pytest.raises(ValueError):
            rt.pause(1_000)
        with pytest.raises(ValueError):
            rt.resume(1_000)

    def test_state_transitions_in_ledger_order(self):
        rt, ledger = make_runtime()
        rt.pause(1_000)
        rt.resume(2_000)
        rt.stop(3_000)
        assert kinds_of(ledger) == ["RUN_STARTED", "STATE_CHANGE", "STATE_CHANGE", "STATE_CHANGE"]
        transitions = [e.payload for e in all_of(ledger, "STATE_CHANGE")]
        assert [(t["from"], t["to"]) for t in transitions] == [
            ("RUNNING", "PAUSED"),
            ("PAUSED", "RUNNING"),
            ("RUNNING", "STOPPED"),
        ]

    def test_invalid_bars_fail_closed_before_any_state_change(self):
        rt, ledger = make_runtime()
        bad = [bar(START_TS + 60, 100, 101, 99, 100), bar(START_TS, 100, 101, 99, 100)]  # descending ts
        with pytest.raises(ValueError):
            rt.process_bars("X", bad, ScriptedAdapter())
        assert len(ledger) == 0  # not even RUN_STARTED: validation precedes everything
        assert rt.state is ForwardRunState.RUNNING


# ---------------------------------------------------------------------------
# Entry -> fill pipeline and cost consistency with the shared execution model
# ---------------------------------------------------------------------------


class TestEntryPipeline:
    def test_entry_fills_next_bar_open_with_spread_slippage(self):
        rt, ledger = make_runtime(**COSTED)
        bars = rising_bars(10)
        rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}))
        fills = all_of(ledger, "FILL")
        assert len(fills) == 1
        fill = fills[0].payload
        expected_price = bars[3]["o"] * (1 + 0.2 / 100 / 2) * (1 + 0.1 / 100)
        assert fill["fill_price"] == pytest.approx(expected_price, rel=1e-12)
        assert fill["raw_price"] == pytest.approx(bars[3]["o"])
        assert fill["signal_index"] == 2
        assert fill["execution_index"] == 3
        assert fills[0].ts_utc == bars[3]["ts"]

    def test_fill_entry_payload_fields_exact(self):
        rt, ledger = make_runtime(**COSTED)
        bars = rising_bars(10)
        rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}))
        fill = first_of(ledger, "FILL").payload
        efp = bars[3]["o"] * (1 + 0.2 / 100 / 2) * (1 + 0.1 / 100)
        desired = 100_000.0 / (efp * (1 + 0.1 / 100))  # runtime sizing formula
        assert fill["side"] == "buy"
        assert fill["qty"] == pytest.approx(math.floor(desired), abs=1e-9)  # lot_size=1.0 floor
        assert set(fill["costs"]) == {"commission", "spread_cost", "slippage_cost", "total"}
        assert fill["latency_bars"] == 0
        assert fill["volume_cap_applied"] is False
        assert fill["lot_rounded"] is True  # fractional desired qty floored to the lot grid

    def test_signal_intent_recorded_at_decision_bar(self):
        rt, ledger = make_runtime(**COSTED)
        bars = rising_bars(10)
        summary = rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}))
        signal = first_of(ledger, "SIGNAL")
        assert signal.payload["symbol"] == "X"
        assert signal.payload["index"] == 2
        assert signal.payload["ts"] == bars[2]["ts"]
        assert signal.payload["action"] == "ENTRY"
        assert signal.payload["resolution"] == "intent"
        assert signal.payload["decision"]["entry"] is True
        assert signal.payload["decision"]["stop_loss_pct"] is None
        assert summary.signals == 1

    def test_position_update_opened_with_mark(self):
        rt, ledger = make_runtime(**COSTED)
        bars = rising_bars(10)
        rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}))
        signal_seq = first_of(ledger, "SIGNAL").seq
        pu = first_of(ledger, "POSITION_UPDATE")
        assert pu.payload["event"] == "OPENED"
        assert pu.payload["signal_ref_seq"] == signal_seq
        assert pu.payload["mark_to_market_pct"] == pytest.approx(0.0)
        assert pu.payload["qty"] == first_of(ledger, "FILL").payload["qty"]
        assert rt.position("X") is not None

    def test_fill_price_identical_to_direct_simulate_fill(self):
        rt, ledger = make_runtime(**COSTED)
        bars = rising_bars(10)
        rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}))
        fill = first_of(ledger, "FILL").payload
        efp = bars[3]["o"] * (1 + 0.2 / 100 / 2) * (1 + 0.1 / 100)
        desired = 100_000.0 / (efp * (1 + 0.1 / 100))
        direct = simulate_fill(
            bars=bars, signal_index=2, side="buy", desired_quantity=desired,
            cfg=ExecutionModelConfig(**COSTED), free_equity=100_000.0, current_position=0.0,
        )
        assert direct.filled
        assert direct.fill_price == fill["fill_price"]  # exact: same shared arithmetic
        assert direct.quantity == fill["qty"]
        assert direct.raw_price == fill["raw_price"]

    def test_costs_breakdown_matches_execution_model(self):
        rt, ledger = make_runtime(**COSTED)
        bars = rising_bars(10)
        rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}))
        fill = first_of(ledger, "FILL").payload
        expected = cost_breakdown(fill["fill_price"] * fill["qty"] * 1.0, ExecutionModelConfig(**COSTED))
        assert fill["costs"] == pytest.approx(expected)

    def test_same_bar_close_policy_fills_at_signal_close(self):
        rt, ledger = make_runtime(fill_policy="SAME_BAR_CLOSE", **COSTED)
        bars = rising_bars(10)
        rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}),
                        signal_delay_reference="SAME_BAR_CLOSE")
        fill = first_of(ledger, "FILL").payload
        expected_price = bars[2]["c"] * (1 + 0.2 / 100 / 2) * (1 + 0.1 / 100)
        assert fill["fill_price"] == pytest.approx(expected_price, rel=1e-12)
        assert fill["execution_index"] == 2  # same bar as the signal
        delay = first_of(ledger, "DELAY_OBSERVATION").payload
        assert delay["delay_bars"] == 0
        assert delay["signal_delay_reference"] == "SAME_BAR_CLOSE"
        assert delay["price_delta_pct"] == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# Exits
# ---------------------------------------------------------------------------


class TestExits:
    def test_signal_exit_fills_next_bar_open(self):
        rt, ledger = make_runtime()  # zero costs
        closes = [100, 100, 100, 110, 110, 110, 110]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True), 3: PaperDecision(exit=True)}))
        sell_fills = [e for e in all_of(ledger, "FILL") if e.payload["side"] == "sell"]
        assert len(sell_fills) == 1
        assert sell_fills[0].payload["execution_index"] == 4  # NEXT_BAR_OPEN after signal at 3
        assert sell_fills[0].payload["exit_reason"] == "SIGNAL_EXIT"
        assert sell_fills[0].payload["fill_price"] == pytest.approx(bars[4]["o"])
        pu_events = [e.payload["event"] for e in all_of(ledger, "POSITION_UPDATE")]
        assert pu_events == ["OPENED", "CLOSED"]
        assert len(all_of(ledger, "DELAY_OBSERVATION")) == 2  # entry + signal exit
        assert rt.position("X") is None

    def test_intrabar_stop_loss_exit(self):
        rt, ledger = make_runtime(intrabar_tp_sl=True)  # zero costs
        bars = [
            bar(START_TS + 0 * STEP, 100, 101, 99, 100),
            bar(START_TS + 1 * STEP, 100, 101, 99, 100),  # entry signal
            bar(START_TS + 2 * STEP, 100, 101, 99, 100),  # fill at open 100
            bar(START_TS + 3 * STEP, 100, 101, 94, 99),   # low 94 pierces stop 95
            bar(START_TS + 4 * STEP, 99, 100, 98, 99),
        ]
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True, stop_loss_pct=5.0)}))
        sell = [e for e in all_of(ledger, "FILL") if e.payload["side"] == "sell"][0]
        assert sell.payload["exit_reason"] == "STOP_LOSS"
        assert sell.payload["raw_price"] == pytest.approx(95.0)  # min(open, stop)
        assert sell.payload["fill_price"] == pytest.approx(95.0)
        assert sell.payload["index"] == 3
        outcome = first_of(ledger, "OUTCOME_MATURED")
        assert outcome.payload["outcome"] == "LOSS"
        assert outcome.payload["realized_return_pct"] == pytest.approx(-5.0)

    def test_stop_wins_over_target_same_bar_pessimistic(self):
        rt, ledger = make_runtime(intrabar_tp_sl=True)  # zero costs
        bars = [
            bar(START_TS + 0 * STEP, 100, 101, 99, 100),
            bar(START_TS + 1 * STEP, 100, 101, 99, 100),
            bar(START_TS + 2 * STEP, 100, 101, 99, 100),  # fill @100; stop 95, take 105
            bar(START_TS + 3 * STEP, 100, 106, 94, 100),  # touches BOTH
        ]
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True, stop_loss_pct=5.0, take_profit_pct=5.0)}))
        sells = [e for e in all_of(ledger, "FILL") if e.payload["side"] == "sell"]
        assert len(sells) == 1
        assert sells[0].payload["exit_reason"] == "STOP_LOSS"  # pessimistic: stop first
        assert sells[0].payload["raw_price"] == pytest.approx(95.0)

    def test_intrabar_take_profit_exit(self):
        rt, ledger = make_runtime(intrabar_tp_sl=True)  # zero costs
        bars = [
            bar(START_TS + 0 * STEP, 100, 101, 99, 100),
            bar(START_TS + 1 * STEP, 100, 101, 99, 100),
            bar(START_TS + 2 * STEP, 100, 101, 99, 100),  # fill @100; take 105
            bar(START_TS + 3 * STEP, 100, 106, 99, 100),  # high 106 >= 105
        ]
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True, take_profit_pct=5.0)}))
        sell = [e for e in all_of(ledger, "FILL") if e.payload["side"] == "sell"][0]
        assert sell.payload["exit_reason"] == "TAKE_PROFIT"
        assert sell.payload["raw_price"] == pytest.approx(105.0)  # pessimistic: no gap credit
        outcome = first_of(ledger, "OUTCOME_MATURED")
        assert outcome.payload["outcome"] == "WIN"
        assert outcome.payload["realized_return_pct"] == pytest.approx(5.0)

    def test_close_based_no_intrabar_when_disabled(self):
        rt, ledger = make_runtime()  # intrabar_tp_sl default False
        bars = [
            bar(START_TS + 0 * STEP, 100, 101, 99, 100),
            bar(START_TS + 1 * STEP, 100, 101, 99, 100),
            bar(START_TS + 2 * STEP, 100, 101, 99, 100),   # fill @100; stop 95
            bar(START_TS + 3 * STEP, 100, 101, 94, 99),    # dips but closes above stop
            bar(START_TS + 4 * STEP, 99, 100, 94, 94.5),   # close 94.5 <= 95 -> exit at close
        ]
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True, stop_loss_pct=5.0)}))
        sells = [e for e in all_of(ledger, "FILL") if e.payload["side"] == "sell"]
        assert len(sells) == 1
        assert sells[0].payload["index"] == 4  # NOT intrabar at index 3
        assert sells[0].payload["raw_price"] == pytest.approx(94.5)
        assert sells[0].payload["exit_reason"] == "STOP_LOSS"
        assert first_of(ledger, "OUTCOME_MATURED").payload["matured_at_index"] == 4

    def test_trailing_stop_exit(self):
        rt, ledger = make_runtime(intrabar_tp_sl=True)  # zero costs
        bars = [
            bar(START_TS + 0 * STEP, 100, 101, 99, 100),
            bar(START_TS + 1 * STEP, 100, 101, 99, 100),   # entry signal
            bar(START_TS + 2 * STEP, 100, 101, 99, 100),   # fill @100, trail peak 100
            bar(START_TS + 3 * STEP, 100, 110, 100, 108),  # peak -> 110, stop 104.5
            bar(START_TS + 4 * STEP, 105, 106, 103, 104),  # low 103 <= 104.5 -> exit
        ]
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True, trailing_pct=5.0)}))
        sell = [e for e in all_of(ledger, "FILL") if e.payload["side"] == "sell"][0]
        assert sell.payload["exit_reason"] == "TRAILING_STOP"
        assert sell.payload["raw_price"] == pytest.approx(104.5)  # min(open 105, stop 104.5)
        outcome = first_of(ledger, "OUTCOME_MATURED")
        assert outcome.payload["outcome"] == "WIN"
        assert outcome.payload["realized_return_pct"] == pytest.approx(4.5)

    def test_trail_peak_update_emits_trailed_update(self):
        rt, ledger = make_runtime(intrabar_tp_sl=True)  # zero costs
        bars = [
            bar(START_TS + 0 * STEP, 100, 101, 99, 100),
            bar(START_TS + 1 * STEP, 100, 101, 99, 100),   # entry signal
            bar(START_TS + 2 * STEP, 100, 100, 99, 100),   # fill @100, trail peak 100 (no up-move yet)
            bar(START_TS + 3 * STEP, 100, 110, 100, 108),  # peak -> 110, stop 104.5
            bar(START_TS + 4 * STEP, 108, 109, 107, 108),
        ]
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True, trailing_pct=5.0)}))
        trailed = [e for e in all_of(ledger, "POSITION_UPDATE") if e.payload["event"] == "TRAILED"]
        assert len(trailed) == 1
        assert trailed[0].payload["trail_peak"] == pytest.approx(110.0)
        assert trailed[0].payload["trail_stop"] == pytest.approx(104.5)
        assert rt.position("X").trail_peak == pytest.approx(110.0)


# ---------------------------------------------------------------------------
# Refusal paths
# ---------------------------------------------------------------------------


class TestRefusals:
    def test_refusal_position_already_open_immediate(self):
        rt, ledger = make_runtime()  # zero costs
        bars = rising_bars(8)
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True), 3: PaperDecision(entry=True)}))
        rejected = [e for e in all_of(ledger, "SIGNAL") if e.payload["resolution"] == "rejected"]
        assert len(rejected) == 1
        assert rejected[0].payload["refusal_reason"] == "position_already_open"
        assert rejected[0].payload["index"] == 3  # immediate, at the decision bar
        assert len(all_of(ledger, "FILL")) == 1
        assert rt.summary().signals_refused == {"position_already_open": 1}
        assert rt.summary().signals_total == 1

    def test_refusal_below_min_lot_deferred(self):
        rt, ledger = make_runtime(initial_capital=50.0, min_lot=10.0, lot_size=5.0)  # zero costs
        bars = rising_bars(6)  # price ~100 -> desired 0.5 units -> lots floor to 0
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True)}))
        rejected = [e for e in all_of(ledger, "SIGNAL") if e.payload["resolution"] == "rejected"]
        assert len(rejected) == 1
        assert rejected[0].payload["refusal_reason"] == "below_min_lot"
        assert rejected[0].payload["index"] == 2  # recorded at the execution bar
        assert rt.summary().signals_refused == {"below_min_lot": 1}
        assert rt.summary().signals_filled == 0

    def test_exit_only_adapter_refused_short_not_allowed(self):
        rt, ledger = make_runtime()  # allow_short=False default
        bars = rising_bars(6)
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(exit=True)}))
        rejected = [e for e in all_of(ledger, "SIGNAL") if e.payload["resolution"] == "rejected"]
        assert len(rejected) == 1
        assert rejected[0].payload["refusal_reason"] == "short_not_allowed"
        assert rt.summary().signals_refused == {"short_not_allowed": 1}
        assert rt.summary().signals_filled == 0
        assert rt.position("X") is None  # graceful: exit-only adapter is fine, stays flat

    def test_refusals_counted_by_reason_in_summary(self):
        rt, ledger = make_runtime()  # zero costs
        bars = rising_bars(9)
        rt.process_bars("X", bars, ScriptedAdapter({
            1: PaperDecision(exit=True),           # flat -> short_not_allowed at bar 2
            3: PaperDecision(entry=True),          # fills at bar 4
            5: PaperDecision(entry=True),          # position open -> position_already_open
        }))
        assert rt.summary().signals_refused == {
            "short_not_allowed": 1,
            "position_already_open": 1,
        }
        assert rt.summary().signals_filled == 1
        assert rt.summary().signals_total == 2  # one entry intent + one exit intent


# ---------------------------------------------------------------------------
# Outcome maturity
# ---------------------------------------------------------------------------


class TestMaturity:
    def test_win_matures_at_exit_fill_basis(self):
        rt, ledger = make_runtime(maturity=MaturityRules(min_bars_after_signal=5))
        closes = [100, 100, 100, 110, 110, 110]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True), 3: PaperDecision(exit=True)}))
        entry_signal_seq = all_of(ledger, "SIGNAL")[0].seq
        outcome = first_of(ledger, "OUTCOME_MATURED")
        assert outcome.payload["signal_ref_seq"] == entry_signal_seq
        assert outcome.payload["outcome"] == "WIN"
        assert outcome.payload["basis"] == "EXIT_FILL"
        assert outcome.payload["matured_at_index"] == 4  # exit fill bar
        assert outcome.payload["open_at_maturity"] is False
        assert outcome.payload["realized_return_pct"] == pytest.approx(10.0)
        summary = rt.summary()
        assert summary.matured_count == 1
        assert summary.immature_count == 0
        assert summary.realized_return_pct == pytest.approx(10.0)
        assert summary.win_rate_matured == pytest.approx(100.0)

    def test_loss_outcome_at_exit(self):
        rt, ledger = make_runtime(maturity=MaturityRules(min_bars_after_signal=5))
        closes = [100, 100, 100, 90, 90, 90]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True), 3: PaperDecision(exit=True)}))
        outcome = first_of(ledger, "OUTCOME_MATURED")
        assert outcome.payload["outcome"] == "LOSS"
        assert outcome.payload["realized_return_pct"] == pytest.approx(-10.0)
        summary = rt.summary()
        assert summary.avg_loss == pytest.approx(-10.0)
        assert summary.avg_win is None
        assert summary.win_rate_matured == pytest.approx(0.0)

    def test_open_position_matures_at_window_maturity_mark(self):
        rt, ledger = make_runtime(
            maturity=MaturityRules(min_bars_after_signal=3, require_exit_before_maturity=False))
        closes = [100, 100, 100, 101, 102, 103, 104, 105]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True)}))
        outcome = first_of(ledger, "OUTCOME_MATURED")
        assert outcome.payload["basis"] == "MATURITY_MARK"
        assert outcome.payload["open_at_maturity"] is True
        assert outcome.payload["matured_at_index"] == 5  # entry fill at 2, +3 bars
        assert outcome.payload["mark_price"] == pytest.approx(103.0)
        assert outcome.payload["realized_return_pct"] == pytest.approx(3.0)
        assert outcome.payload["outcome"] == "WIN"
        assert rt.position("X") is not None  # still open
        # Honesty: MATURITY_MARK is NOT a closed trade -> excluded from realized stats.
        summary = rt.summary()
        assert summary.realized_return_pct == 0.0
        assert summary.matured_count == 1
        assert summary.immature_count == 0

    def test_require_exit_keeps_open_position_immature(self):
        rt, ledger = make_runtime(maturity=MaturityRules(min_bars_after_signal=3))
        bars = rising_bars(9)
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True)}))
        assert all_of(ledger, "OUTCOME_MATURED") == []
        summary = rt.summary()
        assert summary.immature_count == 1
        assert summary.matured_count == 0
        assert summary.realized_return_pct == 0.0
        assert summary.win_rate_matured == 0.0

    def test_immature_excluded_from_aggregates(self):
        rt, ledger = make_runtime(maturity=MaturityRules(min_bars_after_signal=5))
        closes = [100, 100, 100, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter({
            1: PaperDecision(entry=True),   # trade 1: fill@2 @100
            3: PaperDecision(exit=True),    # fill@4 @110 -> matured WIN +10%
            5: PaperDecision(entry=True),   # trade 2: fill@6 @110, never exits -> immature
        }))
        summary = rt.summary()
        assert summary.immature_count == 1
        assert summary.matured_count == 1
        assert summary.realized_return_pct == pytest.approx(10.0)  # trade 2 ignored
        assert summary.win_rate_matured == pytest.approx(100.0)
        assert summary.avg_win == pytest.approx(10.0)
        assert summary.signals_filled == 3  # 2 buys + 1 sell

    def test_stale_after_seconds_flags_and_excludes(self):
        rt, ledger = make_runtime(
            maturity=MaturityRules(min_bars_after_signal=2, require_exit_before_maturity=False,
                                   stale_after_seconds=100))
        bars = rising_bars(8)  # 60s bars: maturity at +120s after entry fill -> stale
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True)}))
        outcome = first_of(ledger, "OUTCOME_MATURED")
        assert outcome.payload["stale"] is True
        summary = rt.summary()
        assert summary.matured_count == 1
        assert summary.stale_outcomes == 1
        assert summary.realized_return_pct == 0.0  # stale excluded from aggregates
        assert summary.win_rate_matured == 0.0

    def test_outcome_matures_once(self):
        rt, ledger = make_runtime(
            maturity=MaturityRules(min_bars_after_signal=2, require_exit_before_maturity=False))
        closes = [100, 100, 100, 101, 102, 103, 104, 105, 106]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True), 6: PaperDecision(exit=True)}))
        outcomes = all_of(ledger, "OUTCOME_MATURED")
        assert len(outcomes) == 1  # maturity mark at bar 4; later close adds no second outcome
        assert outcomes[0].payload["basis"] == "MATURITY_MARK"
        closes_events = [e.payload["event"] for e in all_of(ledger, "POSITION_UPDATE")]
        assert "CLOSED" in closes_events
        assert len(all_of(ledger, "FILL")) == 2  # entry + exit fills still recorded
        assert rt.summary().matured_count == 1


# ---------------------------------------------------------------------------
# Delay observations and data gaps
# ---------------------------------------------------------------------------


class TestDelayAndGaps:
    def test_delay_observation_with_latency_two(self):
        rt, ledger = make_runtime(latency_bars=2)
        bars = rising_bars(10)
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True)}),
                        signal_delay_reference="NEXT_BAR_OPEN")
        delay = first_of(ledger, "DELAY_OBSERVATION").payload
        assert delay["signal_index"] == 1
        assert delay["execution_index"] == 4  # 1 + latency 2 + 1 policy bar
        assert delay["delay_bars"] == 3
        assert delay["signal_delay_reference"] == "NEXT_BAR_OPEN"
        assert rt.summary().total_delay_bars_mean == pytest.approx(3.0)

    def test_expected_vs_realized_recomputed_independently(self):
        rt, ledger = make_runtime(**COSTED)
        bars = rising_bars(10)
        rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}))
        delay = first_of(ledger, "DELAY_OBSERVATION").payload
        expected = bars[2]["c"] * (1 + 0.2 / 100 / 2) * (1 + 0.1 / 100)
        realized = bars[3]["o"] * (1 + 0.2 / 100 / 2) * (1 + 0.1 / 100)
        assert delay["expected_price"] == pytest.approx(expected, rel=1e-12)
        assert delay["realized_price"] == pytest.approx(realized, rel=1e-12)
        delta = (realized / expected - 1.0) * 100.0
        assert delay["price_delta_pct"] == pytest.approx(delta, rel=1e-9)
        evr = rt.summary().expected_vs_realized
        assert evr.observations == 1
        assert evr.mean_abs_delta_pct == pytest.approx(abs(delta), rel=1e-9)
        assert evr.max_abs_delta_pct == pytest.approx(abs(delta), rel=1e-9)

    def test_delay_mean_in_summary(self):
        rt, ledger = make_runtime(latency_bars=1)
        closes = [100, 100, 100, 105, 110, 110, 110, 110, 110]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True), 3: PaperDecision(exit=True)}))
        delays = [e.payload["delay_bars"] for e in all_of(ledger, "DELAY_OBSERVATION")]
        assert delays == [2, 2]  # latency 1 + 1 policy bar, for both fills
        assert rt.summary().total_delay_bars_mean == pytest.approx(2.0)

    def test_data_gap_detected_exact_ts(self):
        rt, ledger = make_runtime()
        tss = [START_TS, START_TS + 60, START_TS + 120, START_TS + 180, START_TS + 480, START_TS + 540]
        bars = [bar(ts, 100.0, 101.0, 99.0, 100.0) for ts in tss]
        rt.process_bars("X", bars, ScriptedAdapter())
        gaps = all_of(ledger, "DATA_GAP")
        assert len(gaps) == 1
        payload = gaps[0].payload
        assert payload["gap_start_ts"] == START_TS + 180
        assert payload["gap_end_ts"] == START_TS + 480
        assert payload["gap_seconds"] == 300
        assert payload["median_interval_seconds"] == 60.0
        assert rt.summary().data_gaps == 1

    def test_no_gap_uniform_bars(self):
        rt, ledger = make_runtime()
        rt.process_bars("X", rising_bars(8), ScriptedAdapter())
        assert all_of(ledger, "DATA_GAP") == []
        assert rt.summary().data_gaps == 0

    def test_volume_cap_applied_flag_reaches_fill_entry(self):
        rt, ledger = make_runtime(volume_cap_pct=0.0001)  # tiny liquidity
        bars = rising_bars(8)  # v=1e6 -> cap qty 100
        rt.process_bars("X", bars, ScriptedAdapter({2: PaperDecision(entry=True)}))
        fill = first_of(ledger, "FILL").payload
        assert fill["volume_cap_applied"] is True
        assert fill["qty"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Summary, determinism, backtest comparison
# ---------------------------------------------------------------------------


class TestSummaryAndCompare:
    def test_summary_identity_fields_and_versions(self):
        rt, _ = make_runtime(maturity=MaturityRules(min_bars_after_signal=7))
        rt.process_bars("X", rising_bars(3), ScriptedAdapter())
        s = rt.summary()
        assert s.run_id == "run-1"
        assert s.strategy_id == "strat-a"
        assert s.strategy_version == "v1.0.0"
        assert s.dsl_version == "RSL-1.0.0"
        assert s.state is ForwardRunState.RUNNING
        assert s.data_trust_label == "SYNTHETIC_OR_PAPER"
        assert s.engine_version == ENGINE_VERSION == "FT-PAPER-1.0.0"
        assert s.execution_model_version == EXECUTION_MODEL_VERSION
        assert s.bars_processed == 3
        assert s.cost_model_echo["fill_policy"] == "NEXT_BAR_OPEN"
        assert s.matured_count == 0 and s.immature_count == 0

    def test_summary_win_rate_avg_win_avg_loss(self):
        rt, ledger = make_runtime()
        closes = [100, 100, 100, 110, 110, 110, 105.6, 105.6, 105.6]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter({
            1: PaperDecision(entry=True),  # fill@2 @100
            3: PaperDecision(exit=True),   # fill@4 @110 -> +10%
            5: PaperDecision(entry=True),  # fill@6 @110
            6: PaperDecision(exit=True),   # fill@7 @105.6 -> -4%
        }))
        s = rt.summary()
        assert s.realized_return_pct == pytest.approx(6.0)
        assert s.win_rate_matured == pytest.approx(50.0)
        assert s.avg_win == pytest.approx(10.0)
        assert s.avg_loss == pytest.approx(-4.0)
        assert s.matured_count == 2

    def test_summary_max_drawdown_pct(self):
        rt, _ = make_runtime()
        closes = [100, 100, 100, 90, 95, 100]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter({1: PaperDecision(entry=True)}))
        assert rt.summary().max_drawdown_pct == pytest.approx(10.0)  # equity 100k -> 90k

    def test_summary_fees_total(self):
        rt, ledger = make_runtime(**COSTED)
        closes = [100, 100, 100, 105, 110, 110, 110]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True), 3: PaperDecision(exit=True)}))
        expected_fees = sum(
            cost_breakdown(e.payload["fill_price"] * e.payload["qty"], ExecutionModelConfig(**COSTED))["total"]
            for e in all_of(ledger, "FILL")
        )
        assert rt.summary().fees_total == pytest.approx(expected_fees)

    def test_summary_digest_deterministic_and_sensitive(self):
        rt1, _ = make_runtime()
        rt1.process_bars("X", rising_bars(6), ScriptedAdapter({1: PaperDecision(entry=True)}))
        rt2, _ = make_runtime()
        rt2.process_bars("X", rising_bars(6), ScriptedAdapter({1: PaperDecision(entry=True)}))
        rt3, _ = make_runtime(run_id="run-OTHER")
        rt3.process_bars("X", rising_bars(6), ScriptedAdapter({1: PaperDecision(entry=True)}))
        s1, s2, s3 = rt1.summary(), rt2.summary(), rt3.summary()
        assert s1.digest() == s2.digest()
        assert s1.digest() == s1.digest()  # stable across calls
        assert s1.digest() != s3.digest()  # sensitive to identity
        assert len(s1.digest()) == 64

    def test_full_run_determinism_identical_hashes(self):
        def full_run():
            ledger = PaperLedger()
            rt = ForwardTestRuntime(
                ForwardTestConfig(run_id="det", strategy_id="s", strategy_version="v1",
                                  execution=ExecutionModelConfig(**COSTED),
                                  maturity=MaturityRules(min_bars_after_signal=3,
                                                         require_exit_before_maturity=False)),
                ledger,
            )
            adapter = ScriptedAdapter({
                1: PaperDecision(entry=True, stop_loss_pct=8.0, take_profit_pct=12.0),
                4: PaperDecision(exit=True),
            })
            rt.process_bars("X", rising_bars(10), adapter, signal_delay_reference="NEXT_BAR_OPEN")
            return rt, ledger

        rt1, led1 = full_run()
        rt2, led2 = full_run()
        assert [e.entry_hash for e in led1.entries] == [e.entry_hash for e in led2.entries]
        assert led1.verify_chain() == (True, None) and led2.verify_chain() == (True, None)
        assert rt1.summary().digest() == rt2.summary().digest()

    def test_compare_with_backtest_present_keys_arithmetic(self):
        rt, _ = make_runtime(maturity=MaturityRules(min_bars_after_signal=5))
        closes = [100, 100, 100, 110, 110, 110]
        bars = trend_bars([float(c) for c in closes])
        rt.process_bars("X", bars, ScriptedAdapter(
            {1: PaperDecision(entry=True), 3: PaperDecision(exit=True)}))
        backtest = {"total_return_pct": 12.0, "win_rate": 55.0, "trade_count": 10.0, "sharpe": 1.5}
        rows = rt.compare_with_backtest(backtest)
        by_metric = {r["metric"]: r for r in rows}
        assert by_metric["total_return_pct"] == {
            "metric": "total_return_pct", "backtest": 12.0, "forward": 10.0, "delta": -2.0}
        assert by_metric["win_rate"]["delta"] == pytest.approx(45.0)
        assert by_metric["trade_count"]["delta"] == pytest.approx(-9.0)
        # 'sharpe' is honestly NOT tracked by the paper engine -> note row, no numbers
        assert by_metric["sharpe"]["delta"] is None
        assert by_metric["sharpe"]["note"] == "not_tracked_by_forward_engine"

    def test_compare_with_backtest_missing_key_note(self):
        rt, _ = make_runtime()
        rt.process_bars("X", rising_bars(4), ScriptedAdapter())
        backtest = {"total_return_pct": 5.0}  # 'win_rate' absent on the backtest side
        rows = rt.compare_with_backtest(backtest, keys=("total_return_pct", "win_rate"))
        assert rows[0]["metric"] == "total_return_pct"
        assert rows[0]["delta"] == pytest.approx(-5.0)
        assert rows[1] == {"metric": "win_rate", "backtest": None, "forward": None,
                           "delta": None, "note": "missing_in_backtest_summary"}


# ---------------------------------------------------------------------------
# Source hygiene and contracts
# ---------------------------------------------------------------------------


class TestHygieneAndContracts:
    def test_module_source_has_no_network_imports(self):
        lines = MODULE_PATH.read_text(encoding="utf-8").splitlines()
        banned = ("requests", "httpx", "websocket", "urllib", "smtplib", "socket.",
                  "threading", "multiprocessing", "subprocess", "asyncio")
        import_lines = [ln for ln in lines if re.match(r"\s*(from|import)\s", ln)]
        assert import_lines, "sanity: module must contain import lines"
        for line in import_lines:
            for token in banned:
                assert token not in line, f"forbidden egress/concurrency import: {line!r}"

    def test_paper_decision_frozen_defaults(self):
        d = PaperDecision()
        assert d.entry is False and d.exit is False
        assert d.stop_loss_pct is None and d.take_profit_pct is None
        assert d.trailing_pct is None and d.size_pct is None
        with pytest.raises(FrozenInstanceError):  # decisions are immutable
            d.entry = True  # type: ignore[misc]

    def test_engine_version_constant(self):
        assert ENGINE_VERSION == "FT-PAPER-1.0.0"

    def test_no_module_level_runtime_instances(self):
        import app.engines.forward_test_paper as mod

        for name in dir(mod):
            obj = getattr(mod, name)
            assert not isinstance(obj, (ForwardTestRuntime, PaperLedger)), (
                f"module-level runtime/ledger singleton leaked: {name}"
            )
