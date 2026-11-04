"""Paper/shadow forward-test runtime for the RADAR BOURSE product
(MASTER-RADAR directive, Wave 6, §E: paper forward-test, expected-vs-realized,
immutable audit ledger).

What this module IS
-------------------
- A deterministic, in-memory, bar-based PAPER/SHADOW replay engine. It consumes
  batches of validated bars, consults a caller-supplied strategy adapter, and
  simulates fills with the SAME shared execution-cost model as the backtest
  engine (``app.engines.execution_model``), so expected-vs-realized deltas
  measure model/execution divergence — never a second, divergent cost model.
- An append-only, hash-chained, tamper-evident audit ledger.

What this module is NOT (directive §E paper/shadow boundary)
------------------------------------------------------------
- No broker connectivity, no live orders, no external notifications, no
  network egress of any kind, no thread spawns, no wall-clock reads: every
  ``ts_utc`` written into the ledger is INJECTED by the caller (bar
  timestamps, or explicit pause/resume/stop timestamps).
- Persistence is a CALLER concern: the ledger is in-memory only; callers who
  need durable audit trails must serialize ``PaperLedger.entries`` themselves.
  This module intentionally provides no delete/clear/truncate API.

Honesty labels
--------------
- All fills are bar-based approximations under the configured ``fill_policy``;
  reports echo ``data_trust_label`` (default "SYNTHETIC_OR_PAPER"). Never
  present these numbers as live/real-tick.
- The expected-vs-realized comparison uses the SIGNAL-bar close adjusted by
  the same spread/slippage arithmetic as the execution leg. Both legs are
  bar-based approximations of the SAME model, so the measured delta captures
  MODEL-vs-EXECUTION divergence (timing + latency + fill policy), not market
  impact.
- Outcome maturity: immature signals are EXCLUDED from every aggregate
  statistic. Per directive, no Brier/ECE/drift metrics are implemented here.

Batch semantics (documented limitation)
---------------------------------------
Each ``process_bars`` call is self-contained: adapter indices refer to the
passed batch. An intent whose execution bar falls beyond the batch is REFUSED
with ``execution_index_beyond_data`` (recorded honestly in the ledger) rather
than silently carried across calls. Callers pass complete batches up to "now".

Pessimistic exit ordering
-------------------------
When one bar touches both the stop and the target, the STOP is taken first
(never the favorable leg). Systematic exits (stop/take/trailing) are
risk-priority: they execute at the triggering bar at the touched/close price
and are intentionally NOT deferred by latency, and they bypass the volume cap
(a protective exit must never be liquidity-refused in a paper model).
"""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.engines.execution_model import (
    EXECUTION_MODEL_VERSION,
    ExecutionModelConfig,
    FillResult,
    apply_latency,
    apply_spread_slippage,
    cost_breakdown,
    notional_of,
    simulate_fill,
    validate_bars,
)

__all__ = [
    "ENGINE_VERSION",
    "LEDGER_KINDS",
    "LedgerEntry",
    "LedgerKind",
    "verify_entry_chain",
    "compute_entry_hash",
    "PaperLedger",
    "PaperDecision",
    "PaperAdapter",
    "MaturityRules",
    "ForwardTestConfig",
    "ForwardRunState",
    "PaperPosition",
    "ExpectedVsRealized",
    "ProcessSummary",
    "ForwardTestSummary",
    "ForwardTestRuntime",
]

ENGINE_VERSION = "FT-PAPER-1.0.0"

GAP_THRESHOLD_MULTIPLE = 3.0  # ts gap > 3x median interval => DATA_GAP

SYSTEMATIC_EXIT_REASONS = ("STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP")

LEDGER_KINDS: tuple[str, ...] = (
    "RUN_STARTED",
    "SIGNAL",
    "FILL",
    "POSITION_UPDATE",
    "STATE_CHANGE",
    "DATA_GAP",
    "DELAY_OBSERVATION",
    "OUTCOME_MATURED",
    "RUN_STOPPED",
    "RUN_PAUSED",
    "RUN_RESUMED",
)

LedgerKind = Literal[
    "RUN_STARTED",
    "SIGNAL",
    "FILL",
    "POSITION_UPDATE",
    "STATE_CHANGE",
    "DATA_GAP",
    "DELAY_OBSERVATION",
    "OUTCOME_MATURED",
    "RUN_STOPPED",
    "RUN_PAUSED",
    "RUN_RESUMED",
]


def _canonical_json(value: Any) -> str:
    """Deterministic JSON rendering (sorted keys, tight separators, no NaN)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True)


def compute_entry_hash(seq: int, kind: str, ts_utc: int, payload: Mapping[str, Any], prev_hash: str) -> str:
    """sha256 over the canonical JSON of ``[seq, kind, ts_utc, payload, prev_hash]``.

    This is the single hash formula for the whole ledger; it is deliberately
    simple so external verifiers (and tests) can recompute it independently.
    """
    return hashlib.sha256(
        _canonical_json([seq, kind, ts_utc, payload, prev_hash]).encode("utf-8")
    ).hexdigest()


class LedgerEntry(BaseModel):
    """One immutable hash-chained ledger record.

    ``ts_utc`` is epoch seconds INJECTED by the caller — this module never
    reads a clock. ``payload`` is validated at construction to be strictly
    JSON-serializable with finite floats only (fail-closed), and is deep-copied
    through a canonical JSON round-trip so later caller-side mutation of the
    original mapping cannot alter history.
    """

    model_config = ConfigDict(frozen=True)

    seq: int = Field(ge=0)
    kind: LedgerKind
    ts_utc: int = Field(ge=0)
    payload: dict[str, Any]
    prev_hash: str = ""
    entry_hash: str = ""

    @field_validator("payload")
    @classmethod
    def _payload_must_be_json_safe(cls, v: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(_canonical_json(v))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"payload_not_json_serializable_or_finite: {exc}") from None


def verify_entry_chain(entries: Sequence[LedgerEntry]) -> tuple[bool, int | None]:
    """Recompute the full chain; return ``(ok, first_bad_seq)``.

    Checks, per entry: contiguous 0-based ``seq``; ``prev_hash`` linkage
    (empty string only at seq 0); and that ``entry_hash`` equals the
    independently recomputed hash of the entry's own fields. Any tampering of
    a historical field (payload, ts, kind, ...) invalidates that entry unless
    the attacker also re-mined every subsequent hash.
    """
    prev = ""
    for i, entry in enumerate(entries):
        if entry.seq != i or entry.prev_hash != prev:
            return False, i
        expected = compute_entry_hash(entry.seq, entry.kind, entry.ts_utc, entry.payload, entry.prev_hash)
        if entry.entry_hash != expected:
            return False, i
        prev = entry.entry_hash
    return True, None


class PaperLedger:
    """Append-only, in-memory, hash-chained audit ledger.

    - ``append`` is the ONLY mutation; there is deliberately NO delete, clear,
      truncate, pop or purge API (append-only by design, directive §E).
    - Chain validity is enforced at append time (prev_hash must equal the last
      entry_hash) and can be re-proven at any time via :meth:`verify_chain`.
    - Persistence is a caller concern (serialize ``entries`` yourself); this
      class performs no I/O.
    """

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        """Read-only snapshot of all entries, in append order."""
        return tuple(self._entries)

    def append(self, kind: str, ts_utc: int, payload: Mapping[str, Any]) -> LedgerEntry:
        """Validate and append one entry; returns the stored (hash-sealed) entry."""
        if kind not in LEDGER_KINDS:
            raise ValueError(f"unknown_ledger_kind:{kind}")
        prev_hash = self._entries[-1].entry_hash if self._entries else ""
        seq = len(self._entries)
        ts = int(ts_utc)
        if ts < 0:
            raise ValueError("ts_utc_must_be_non_negative_epoch_seconds")
        entry = LedgerEntry(seq=seq, kind=kind, ts_utc=ts, payload=dict(payload), prev_hash=prev_hash)
        entry = entry.model_copy(
            update={"entry_hash": compute_entry_hash(seq, entry.kind, entry.ts_utc, entry.payload, prev_hash)}
        )
        self._entries.append(entry)
        return entry

    def verify_chain(self) -> tuple[bool, int | None]:
        """``(ok, first_bad_seq)`` over the whole stored chain (None bad_seq when ok)."""
        return verify_entry_chain(self._entries)


# --------------------------------------------------------------------------
# Strategy adapter contract (independent of strategy_dsl / backtest_product).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PaperDecision:
    """One bar's strategy decision expressed in paper-trade terms."""

    entry: bool = False
    exit: bool = False
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_pct: float | None = None
    size_pct: float | None = None


class PaperAdapter(Protocol):
    """Structural contract; the runtime duck-types adapters (no isinstance).

    ``prepare`` is called once per ``process_bars`` batch before iteration;
    ``decide(index)`` is called once per bar, in order, only while RUNNING.
    Adapters are expected to be symbol-scoped by the caller (one adapter per
    symbol) or explicitly symbol-agnostic; the runtime does not interpret.
    """

    strategy_id: str

    def prepare(self, bars: list[dict]) -> None: ...

    def decide(self, index: int) -> PaperDecision: ...


# --------------------------------------------------------------------------
# Configuration / state models.
# --------------------------------------------------------------------------


class MaturityRules(BaseModel):
    """When does a signal's outcome count as matured (directive §E)?

    - ``min_bars_after_signal``: bars that must elapse after the ENTRY FILL.
    - ``require_exit_before_maturity=True``: an outcome needs a CLOSED position
      (matures immediately at the closing fill, even before the window).
      ``False``: the maturity window alone suffices — an open position is
      marked at the current close and flagged ``open_at_maturity``.
    - ``stale_after_seconds``: when set, an outcome whose maturity moment is
      more than this many (injected) seconds after its entry fill is flagged
      ``stale`` and EXCLUDED from all aggregate statistics.
    """

    model_config = ConfigDict(frozen=True)

    min_bars_after_signal: int = Field(default=20, ge=1)
    require_exit_before_maturity: bool = True
    stale_after_seconds: int | None = Field(default=None, ge=0)


class ForwardTestConfig(BaseModel):
    """Paper run configuration. Provenance fields are mandatory."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1, description="required provenance")
    dsl_version: str = "RSL-1.0.0"
    execution: ExecutionModelConfig = Field(default_factory=ExecutionModelConfig)
    data_trust_label: str = "SYNTHETIC_OR_PAPER"
    maturity: MaturityRules = Field(default_factory=MaturityRules)


class ForwardRunState(str, Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class PaperPosition(BaseModel):
    """Open paper position snapshot (one position per symbol, long-only book
    unless the shared execution config enables shorts)."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    qty: float
    entry_fill_price: float
    entry_ts: int
    stop_price: float | None = None
    take_price: float | None = None
    trail_peak: float | None = None
    trailing_pct: float | None = None


class ExpectedVsRealized(BaseModel):
    """Aggregate of DELAY_OBSERVATION price deltas (percent, signed -> abs)."""

    model_config = ConfigDict(frozen=True)

    mean_abs_delta_pct: float | None = None
    max_abs_delta_pct: float | None = None
    observations: int = 0


class ProcessSummary(BaseModel):
    """Per-call result of ``process_bars``."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    bars_processed: int
    signals: int
    fills: int
    refusals: dict[str, int] = Field(default_factory=dict)
    data_gaps: int = 0
    outcomes_matured: int = 0


class ForwardTestSummary(BaseModel):
    """Run-level summary. Immature signals are excluded from ALL aggregates."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    strategy_id: str
    strategy_version: str
    dsl_version: str
    state: ForwardRunState
    data_trust_label: str
    bars_processed: int
    signals_total: int
    signals_filled: int
    signals_refused: dict[str, int]
    immature_count: int
    matured_count: int
    stale_outcomes: int = 0
    realized_return_pct: float
    win_rate_matured: float
    avg_win: float | None = None
    avg_loss: float | None = None
    max_drawdown_pct: float
    fees_total: float
    total_delay_bars_mean: float | None = None
    data_gaps: int
    expected_vs_realized: ExpectedVsRealized
    cost_model_echo: dict[str, Any]
    engine_version: str = ENGINE_VERSION
    execution_model_version: str = EXECUTION_MODEL_VERSION

    def digest(self) -> str:
        """sha256 of the canonical JSON of this summary (determinism anchor)."""
        return hashlib.sha256(_canonical_json(self.model_dump(mode="json")).encode("utf-8")).hexdigest()


@dataclass
class _PendingIntent:
    """An entry/exit intent awaiting its (latency + policy) execution bar."""

    action: Literal["ENTRY", "EXIT"]
    signal_index: int
    exec_index: int
    signal_seq: int
    ts_utc: int
    decision: PaperDecision


@dataclass
class _CallTally:
    bars: int = 0
    signals: int = 0
    fills: int = 0
    data_gaps: int = 0
    outcomes_matured: int = 0
    refusals: dict[str, int] = field(default_factory=dict)

    def add_refusal(self, reason: str) -> None:
        self.refusals[reason] = self.refusals.get(reason, 0) + 1


class ForwardTestRuntime:
    """Paper/shadow forward-test runtime (directive §E).

    Deterministic, clock-free, egress-free. All timestamps are injected from
    bar data or explicit state-transition calls. Single position per symbol;
    account-level cash/equity accounting shared across symbols.
    """

    def __init__(self, config: ForwardTestConfig, ledger: PaperLedger) -> None:
        self._config = config
        self._ledger = ledger
        self._state = ForwardRunState.RUNNING
        self._cash = float(config.execution.initial_capital)
        self._positions: dict[str, PaperPosition] = {}
        self._entry_signal_seq: dict[str, int] = {}
        self._pending_entries: dict[str, _PendingIntent] = {}
        self._pending_exits: dict[str, _PendingIntent] = {}
        self._last_ts: dict[str, int] = {}
        self._median_interval: dict[str, float] = {}
        self._last_close: dict[str, float] = {}
        self._bars_processed = 0
        self._fill_count = 0
        self._intent_signal_count = 0
        self._refusals: dict[str, int] = {}
        self._fees_total = 0.0
        self._data_gaps = 0
        self._delay_observations: list[dict[str, float]] = []
        self._open_outcomes: dict[int, dict[str, Any]] = {}
        self._matured_outcomes: list[dict[str, Any]] = []
        self._equity_peak = float(config.execution.initial_capital)
        self._max_drawdown_pct = 0.0
        self._paused_noop_recorded = False
        self._run_started_seq: int | None = None

    # -- read accessors ----------------------------------------------------

    @property
    def state(self) -> ForwardRunState:
        return self._state

    @property
    def config(self) -> ForwardTestConfig:
        return self._config

    @property
    def ledger(self) -> PaperLedger:
        return self._ledger

    def position(self, symbol: str) -> PaperPosition | None:
        return self._positions.get(symbol)

    # -- state machine -----------------------------------------------------

    def _ensure_run_started(self, ts_utc: int) -> None:
        if self._run_started_seq is None:
            entry = self._ledger.append(
                "RUN_STARTED",
                ts_utc,
                {
                    "run_id": self._config.run_id,
                    "strategy_id": self._config.strategy_id,
                    "strategy_version": self._config.strategy_version,
                    "dsl_version": self._config.dsl_version,
                    "engine_version": ENGINE_VERSION,
                    "execution_model_version": EXECUTION_MODEL_VERSION,
                    "data_trust_label": self._config.data_trust_label,
                },
            )
            self._run_started_seq = entry.seq

    def pause(self, ts_utc: int) -> None:
        self._ensure_run_started(ts_utc)
        if self._state is not ForwardRunState.RUNNING:
            raise ValueError("pause_requires_running_state")
        self._state = ForwardRunState.PAUSED
        self._paused_noop_recorded = False
        self._ledger.append("STATE_CHANGE", ts_utc, {"event": "STATE_CHANGE", "from": "RUNNING", "to": "PAUSED"})

    def resume(self, ts_utc: int) -> None:
        self._ensure_run_started(ts_utc)
        if self._state is not ForwardRunState.PAUSED:
            raise ValueError("resume_requires_paused_state")
        self._state = ForwardRunState.RUNNING
        self._paused_noop_recorded = False
        self._ledger.append("STATE_CHANGE", ts_utc, {"event": "STATE_CHANGE", "from": "PAUSED", "to": "RUNNING"})

    def stop(self, ts_utc: int) -> None:
        self._ensure_run_started(ts_utc)
        if self._state is ForwardRunState.STOPPED:
            raise ValueError("runtime_already_stopped")
        previous = self._state
        self._state = ForwardRunState.STOPPED
        self._ledger.append(
            "STATE_CHANGE", ts_utc, {"event": "STATE_CHANGE", "from": previous.value, "to": "STOPPED"}
        )

    # -- main processing ---------------------------------------------------

    def process_bars(
        self,
        symbol: str,
        bars: list[dict],
        adapter: PaperAdapter,
        *,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None = None,
    ) -> ProcessSummary:
        """Process one symbol batch, in order, under the paper/shadow model.

        While PAUSED this is a no-op returning 0 processed bars (recorded ONCE
        per pause episode as a STATE_CHANGE note, never per bar). While STOPPED
        it raises ``ValueError`` (terminal state).
        """
        if self._state is ForwardRunState.STOPPED:
            raise ValueError("runtime_stopped: terminal state, further processing refused")
        if self._state is ForwardRunState.PAUSED:
            if bars and not self._paused_noop_recorded:
                first = bars[0]
                if isinstance(first, Mapping) and "ts" in first:
                    self._ensure_run_started(int(first["ts"]))
                    self._ledger.append(
                        "STATE_CHANGE",
                        int(first["ts"]),
                        {
                            "event": "PROCESS_BARS_SKIPPED",
                            "reason": "runtime_paused",
                            "symbol": symbol,
                            "offered_bars": len(bars),
                        },
                    )
                    self._paused_noop_recorded = True
            return ProcessSummary(symbol=symbol, bars_processed=0, signals=0, fills=0)

        validate_bars(bars)  # fail-closed; no state mutated on invalid input
        if bars:
            self._ensure_run_started(int(bars[0]["ts"]))
        adapter.prepare(list(bars))

        tally = _CallTally()
        diffs = [int(bars[i]["ts"]) - int(bars[i - 1]["ts"]) for i in range(1, len(bars))]
        batch_median = float(statistics.median(diffs)) if diffs else None
        if batch_median is not None and batch_median > 0:
            self._median_interval[symbol] = batch_median

        for i, bar in enumerate(bars):
            ts = int(bar["ts"])
            self._maybe_record_gap(symbol, bars, i, ts, batch_median, tally)
            self._resolve_due_pendings(symbol, bars, i, tally, signal_delay_reference)
            self._check_systematic_exit(symbol, bars, i, tally)
            decision = adapter.decide(i)
            self._handle_decision(symbol, bars, i, decision, tally, signal_delay_reference)
            self._update_trailing(symbol, bars, i)
            self._check_maturity(symbol, bars, i, tally)
            self._mark_equity(symbol, float(bar["c"]))
            tally.bars += 1

        self._resolve_leftover_pendings(symbol, bars, tally, signal_delay_reference)
        self._bars_processed += tally.bars
        self._data_gaps += tally.data_gaps
        for reason, n in tally.refusals.items():
            self._refusals[reason] = self._refusals.get(reason, 0) + n
        return ProcessSummary(
            symbol=symbol,
            bars_processed=tally.bars,
            signals=tally.signals,
            fills=tally.fills,
            refusals=dict(sorted(tally.refusals.items())),
            data_gaps=tally.data_gaps,
            outcomes_matured=tally.outcomes_matured,
        )

    # -- per-bar helpers ---------------------------------------------------

    def _maybe_record_gap(
        self,
        symbol: str,
        bars: list[dict],
        i: int,
        ts: int,
        batch_median: float | None,
        tally: _CallTally,
    ) -> None:
        prev_ts = int(bars[i - 1]["ts"]) if i > 0 else self._last_ts.get(symbol)
        med = batch_median if i > 0 else self._median_interval.get(symbol)
        if prev_ts is None or med is None or med <= 0:
            return
        gap = ts - prev_ts
        if gap > GAP_THRESHOLD_MULTIPLE * med:
            tally.data_gaps += 1
            self._ledger.append(
                "DATA_GAP",
                ts,
                {
                    "symbol": symbol,
                    "gap_start_ts": prev_ts,
                    "gap_end_ts": ts,
                    "gap_seconds": gap,
                    "median_interval_seconds": med,
                    "threshold": f">{GAP_THRESHOLD_MULTIPLE}x_median",
                },
            )

    def _resolve_due_pendings(
        self,
        symbol: str,
        bars: list[dict],
        i: int,
        tally: _CallTally,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None,
    ) -> None:
        for store in (self._pending_entries, self._pending_exits):
            pending = store.get(symbol)
            if pending is not None and pending.exec_index == i:
                del store[symbol]
                if pending.action == "ENTRY":
                    self._attempt_entry_fill(symbol, bars, i, pending, tally, signal_delay_reference)
                else:
                    self._attempt_exit_fill(symbol, bars, i, pending, tally, signal_delay_reference)

    def _handle_decision(
        self,
        symbol: str,
        bars: list[dict],
        i: int,
        decision: PaperDecision,
        tally: _CallTally,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None,
    ) -> None:
        """Record SIGNAL intents/refusals. Exit precedence when both flags set."""
        if decision.exit:
            seq = self._record_signal(symbol, bars, i, "EXIT", decision, "intent", None, tally)
            pending = _PendingIntent("EXIT", i, apply_latency(i, self._config.execution, len(bars)), seq,
                                     int(bars[i]["ts"]), decision)
            self._pending_exits[symbol] = pending
            if pending.exec_index == i:  # SAME_BAR_CLOSE policy: fill at this bar's close, now
                del self._pending_exits[symbol]
                self._attempt_exit_fill(symbol, bars, i, pending, tally, signal_delay_reference)
        elif decision.entry:
            if symbol in self._positions or symbol in self._pending_entries:
                self._record_signal(symbol, bars, i, "ENTRY", decision, "rejected", "position_already_open", tally)
                tally.add_refusal("position_already_open")
            else:
                seq = self._record_signal(symbol, bars, i, "ENTRY", decision, "intent", None, tally)
                pending = _PendingIntent("ENTRY", i, apply_latency(i, self._config.execution, len(bars)), seq,
                                         int(bars[i]["ts"]), decision)
                self._pending_entries[symbol] = pending
                if pending.exec_index == i:
                    del self._pending_entries[symbol]
                    self._attempt_entry_fill(symbol, bars, i, pending, tally, signal_delay_reference)

    def _record_signal(
        self,
        symbol: str,
        bars: list[dict],
        i: int,
        action: Literal["ENTRY", "EXIT"],
        decision: PaperDecision,
        resolution: Literal["intent", "rejected"],
        refusal_reason: str | None,
        tally: _CallTally,
    ) -> int:
        if resolution == "intent":
            tally.signals += 1
            self._intent_signal_count += 1
        entry = self._ledger.append(
            "SIGNAL",
            int(bars[i]["ts"]),
            {
                "symbol": symbol,
                "index": i,
                "ts": int(bars[i]["ts"]),
                "action": action,
                "resolution": resolution,
                "refusal_reason": refusal_reason,
                "decision": {
                    "entry": decision.entry,
                    "exit": decision.exit,
                    "stop_loss_pct": decision.stop_loss_pct,
                    "take_profit_pct": decision.take_profit_pct,
                    "trailing_pct": decision.trailing_pct,
                    "size_pct": decision.size_pct,
                },
            },
        )
        return entry.seq

    def _record_rejection(
        self,
        symbol: str,
        bars: list[dict],
        i: int,
        intent: _PendingIntent,
        reason: str,
        tally: _CallTally,
    ) -> None:
        self._record_signal(symbol, bars, i, intent.action, intent.decision, "rejected", reason, tally)
        tally.add_refusal(reason)

    # -- fills ---------------------------------------------------------------

    def _desired_entry_quantity(self, symbol: str, bars: list[dict], intent: _PendingIntent) -> float:
        """Size against the EXPECTED unit cost: raw price adjusted for spread +
        slippage uplift AND the entry commission, so a full-equity entry lands
        exactly on ``size_pct * equity`` without self-refusing on margin."""
        cfg = self._config.execution
        alloc_pct = intent.decision.size_pct if intent.decision.size_pct is not None else 1.0
        idx = intent.exec_index if intent.exec_index < len(bars) else len(bars) - 1
        raw = float(bars[idx]["o"] if cfg.fill_policy == "NEXT_BAR_OPEN" else bars[idx]["c"])
        if raw <= 0:
            return 0.0
        unit_cost = apply_spread_slippage(raw, "buy", cfg) * (1.0 + cfg.commission_pct / 100.0)
        return max(alloc_pct, 0.0) * self._equity_mark() / unit_cost

    def _attempt_entry_fill(
        self,
        symbol: str,
        bars: list[dict],
        i: int,
        intent: _PendingIntent,
        tally: _CallTally,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None,
    ) -> None:
        cfg = self._config.execution
        fr = simulate_fill(
            bars=bars,
            signal_index=intent.signal_index,
            side="buy",
            desired_quantity=self._desired_entry_quantity(symbol, bars, intent),
            cfg=cfg,
            free_equity=self._cash,
            current_position=self._positions[symbol].qty if symbol in self._positions else 0.0,
        )
        if fr.filled:
            self._apply_entry_fill(symbol, bars, fr, intent, tally, signal_delay_reference)
        else:
            self._record_rejection(symbol, bars, i, intent, fr.refusal_reason or "unknown", tally)

    def _apply_entry_fill(
        self,
        symbol: str,
        bars: list[dict],
        fr: FillResult,
        intent: _PendingIntent,
        tally: _CallTally,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None,
    ) -> None:
        cfg = self._config.execution
        ts = int(bars[fr.execution_index]["ts"])
        notional = notional_of(fr.fill_price, fr.quantity, cfg)
        costs = cost_breakdown(notional, cfg)
        self._cash -= notional + costs["commission"]  # fill_price already embeds spread+slippage
        self._fees_total += costs["total"]
        self._fill_count += 1
        tally.fills += 1
        decision = intent.decision
        stop_price = (
            fr.fill_price * (1.0 - decision.stop_loss_pct / 100.0) if decision.stop_loss_pct is not None else None
        )
        take_price = (
            fr.fill_price * (1.0 + decision.take_profit_pct / 100.0) if decision.take_profit_pct is not None else None
        )
        position = PaperPosition(
            symbol=symbol,
            qty=fr.quantity,
            entry_fill_price=fr.fill_price,
            entry_ts=ts,
            stop_price=stop_price,
            take_price=take_price,
            trail_peak=fr.fill_price,
            trailing_pct=decision.trailing_pct,
        )
        self._positions[symbol] = position
        self._entry_signal_seq[symbol] = intent.signal_seq
        self._ledger.append(
            "FILL",
            ts,
            {
                "symbol": symbol,
                "side": "buy",
                "qty": fr.quantity,
                "fill_price": fr.fill_price,
                "raw_price": fr.raw_price,
                "costs": costs,
                "latency_bars": fr.latency_bars,
                "volume_cap_applied": fr.volume_cap_applied,
                "lot_rounded": fr.lot_rounded,
                "signal_index": fr.signal_index,
                "execution_index": fr.execution_index,
                "index": fr.execution_index,
                "ts": ts,
            },
        )
        self._ledger.append(
            "POSITION_UPDATE",
            ts,
            {
                "symbol": symbol,
                "index": fr.execution_index,
                "ts": ts,
                "event": "OPENED",
                "qty": fr.quantity,
                "entry_fill_price": fr.fill_price,
                "entry_ts": ts,
                "mark_price": fr.fill_price,
                "mark_to_market_pct": 0.0,
                "stop_price": stop_price,
                "take_price": take_price,
                "trail_peak": fr.fill_price,
                "trailing_pct": decision.trailing_pct,
                "signal_ref_seq": intent.signal_seq,
            },
        )
        self._open_outcomes[intent.signal_seq] = {
            "signal_ref_seq": intent.signal_seq,
            "symbol": symbol,
            "entry_exec_index": fr.execution_index,
            "entry_fill_ts": ts,
            "entry_cost": notional + costs["commission"],
            "qty": fr.quantity,
            "exit_proceeds_net": 0.0,
            "exit_reason": None,
        }
        expected = apply_spread_slippage(float(bars[intent.signal_index]["c"]), "buy", cfg)
        self._record_delay_observation(symbol, intent, fr, expected, ts, signal_delay_reference)

    def _attempt_exit_fill(
        self,
        symbol: str,
        bars: list[dict],
        i: int,
        intent: _PendingIntent,
        tally: _CallTally,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None,
    ) -> None:
        cfg = self._config.execution
        pos_qty = self._positions[symbol].qty if symbol in self._positions else 0.0
        desired = pos_qty if pos_qty > 0 else max(cfg.min_lot, cfg.lot_size)
        fr = simulate_fill(
            bars=bars,
            signal_index=intent.signal_index,
            side="sell",
            desired_quantity=desired,
            cfg=cfg,
            free_equity=self._equity_mark(),  # exits are collateralized by the open book
            current_position=pos_qty,
        )
        if fr.filled:
            self._apply_exit_fill(
                symbol,
                bars,
                qty_filled=fr.quantity,
                fill_price=fr.fill_price,
                raw_price=fr.raw_price,
                reason="SIGNAL_EXIT",
                index=fr.execution_index,
                signal_seq=intent.signal_seq,
                via_intent=True,
                intent=intent,
                cap_applied=fr.volume_cap_applied,
                lot_rounded=fr.lot_rounded,
                latency_bars=fr.latency_bars,
                tally=tally,
                signal_delay_reference=signal_delay_reference,
            )
        else:
            self._record_rejection(symbol, bars, i, intent, fr.refusal_reason or "unknown", tally)

    def _check_systematic_exit(self, symbol: str, bars: list[dict], i: int, tally: _CallTally) -> None:
        """Stop FIRST (pessimistic), then target. Trailing rides the hard stop."""
        pos = self._positions.get(symbol)
        if pos is None:
            return
        cfg = self._config.execution
        bar = bars[i]
        open_, high, low, close = float(bar["o"]), float(bar["h"]), float(bar["l"]), float(bar["c"])
        trail_stop = (
            pos.trail_peak * (1.0 - pos.trailing_pct / 100.0)
            if pos.trail_peak is not None and pos.trailing_pct is not None
            else None
        )
        stops = [s for s in (pos.stop_price, trail_stop) if s is not None]
        if stops:
            eff_stop = max(stops)
            hit = (low <= eff_stop) if cfg.intrabar_tp_sl else (close <= eff_stop)
            if hit:
                basis = min(open_, eff_stop) if cfg.intrabar_tp_sl else close  # gap-through fills at open
                reason = (
                    "TRAILING_STOP"
                    if trail_stop is not None and (pos.stop_price is None or trail_stop >= pos.stop_price)
                    else "STOP_LOSS"
                )
                self._apply_exit_fill(
                    symbol, bars, qty_filled=pos.qty,
                    fill_price=apply_spread_slippage(basis, "sell", cfg), raw_price=basis,
                    reason=reason, index=i, signal_seq=self._entry_signal_seq.get(symbol, -1),
                    via_intent=False, intent=None, cap_applied=False, lot_rounded=False, latency_bars=0,
                    tally=tally, signal_delay_reference=None,
                )
                return
        if pos.take_price is not None:
            hit = (high >= pos.take_price) if cfg.intrabar_tp_sl else (close >= pos.take_price)
            if hit:
                basis = pos.take_price if cfg.intrabar_tp_sl else close  # pessimistic: no gap credit
                self._apply_exit_fill(
                    symbol, bars, qty_filled=pos.qty,
                    fill_price=apply_spread_slippage(basis, "sell", cfg), raw_price=basis,
                    reason="TAKE_PROFIT", index=i, signal_seq=self._entry_signal_seq.get(symbol, -1),
                    via_intent=False, intent=None, cap_applied=False, lot_rounded=False, latency_bars=0,
                    tally=tally, signal_delay_reference=None,
                )

    def _apply_exit_fill(
        self,
        symbol: str,
        bars: list[dict],
        *,
        qty_filled: float,
        fill_price: float,
        raw_price: float,
        reason: str,
        index: int,
        signal_seq: int,
        via_intent: bool,
        intent: _PendingIntent | None,
        cap_applied: bool,
        lot_rounded: bool,
        latency_bars: int,
        tally: _CallTally,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None,
    ) -> None:
        cfg = self._config.execution
        ts = int(bars[index]["ts"])
        notional = notional_of(fill_price, qty_filled, cfg)
        costs = cost_breakdown(notional, cfg)
        self._cash += notional - costs["commission"]
        self._fees_total += costs["total"]
        self._fill_count += 1
        tally.fills += 1
        self._ledger.append(
            "FILL",
            ts,
            {
                "symbol": symbol,
                "side": "sell",
                "qty": qty_filled,
                "fill_price": fill_price,
                "raw_price": raw_price,
                "costs": costs,
                "latency_bars": latency_bars,
                "volume_cap_applied": cap_applied,
                "lot_rounded": lot_rounded,
                "exit_reason": reason,
                "signal_index": intent.signal_index if intent is not None else None,
                "execution_index": index,
                "index": index,
                "ts": ts,
            },
        )
        if via_intent and intent is not None:
            expected = apply_spread_slippage(float(bars[intent.signal_index]["c"]), "sell", cfg)
            self._record_delay_observation(symbol, intent, FillResult(
                filled=True, side="sell", signal_index=intent.signal_index, execution_index=index,
                raw_price=raw_price, fill_price=fill_price, quantity=qty_filled,
                latency_bars=latency_bars), expected, ts, signal_delay_reference)

        pos = self._positions.get(symbol)
        if pos is None:
            return
        remaining = pos.qty - qty_filled
        rec_key = self._entry_signal_seq.get(symbol, signal_seq)
        rec = self._open_outcomes.get(rec_key)
        if rec is not None:
            rec["exit_proceeds_net"] += notional - costs["commission"]
            rec["exit_reason"] = reason
        if remaining <= 1e-9:
            del self._positions[symbol]
            self._entry_signal_seq.pop(symbol, None)
            event = "STOPPED" if reason in SYSTEMATIC_EXIT_REASONS else "CLOSED"
            self._ledger.append(
                "POSITION_UPDATE",
                ts,
                {
                    "symbol": symbol,
                    "index": index,
                    "ts": ts,
                    "event": event,
                    "exit_reason": reason,
                    "qty": 0.0,
                    "entry_fill_price": pos.entry_fill_price,
                    "mark_price": fill_price,
                    "signal_ref_seq": rec_key,
                },
            )
            if rec is not None:
                realized = (
                    (rec["exit_proceeds_net"] - rec["entry_cost"]) / rec["entry_cost"] * 100.0
                    if rec["entry_cost"] > 0
                    else 0.0
                )
                self._mature_outcome(
                    rec,
                    basis="EXIT_FILL",
                    matured_at_index=index,
                    matured_at_ts=ts,
                    realized_return_pct=realized,
                    open_at_maturity=False,
                    mark_price=fill_price,
                    tally=tally,
                )
        else:
            self._positions[symbol] = pos.model_copy(update={"qty": remaining})
            self._ledger.append(
                "POSITION_UPDATE",
                ts,
                {
                    "symbol": symbol,
                    "index": index,
                    "ts": ts,
                    "event": "PARTIAL_EXIT",
                    "exit_reason": reason,
                    "qty": remaining,
                    "mark_price": fill_price,
                    "signal_ref_seq": rec_key,
                },
            )

    def _record_delay_observation(
        self,
        symbol: str,
        intent: _PendingIntent,
        fr: FillResult,
        expected_price: float,
        ts: int,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None,
    ) -> None:
        delay_bars = fr.execution_index - intent.signal_index
        delta = (fr.fill_price / expected_price - 1.0) * 100.0 if expected_price > 0 else 0.0
        self._ledger.append(
            "DELAY_OBSERVATION",
            ts,
            {
                "symbol": symbol,
                "signal_ref_seq": intent.signal_seq,
                "side": fr.side,
                "signal_index": intent.signal_index,
                "execution_index": fr.execution_index,
                "delay_bars": delay_bars,
                "expected_price": expected_price,
                "realized_price": fr.fill_price,
                "price_delta_pct": delta,
                "signal_delay_reference": signal_delay_reference,
            },
        )
        self._delay_observations.append({"delay_bars": float(delay_bars), "abs_delta_pct": abs(delta)})

    # -- position maintenance / outcomes -------------------------------------

    def _update_trailing(self, symbol: str, bars: list[dict], i: int) -> None:
        pos = self._positions.get(symbol)
        if pos is None or pos.trailing_pct is None:
            return
        high = float(bars[i]["h"])
        if pos.trail_peak is not None and high <= pos.trail_peak + 1e-12:
            return
        self._positions[symbol] = pos.model_copy(update={"trail_peak": high})
        trail_stop = high * (1.0 - pos.trailing_pct / 100.0)
        self._ledger.append(
            "POSITION_UPDATE",
            int(bars[i]["ts"]),
            {
                "symbol": symbol,
                "index": i,
                "ts": int(bars[i]["ts"]),
                "event": "TRAILED",
                "trail_peak": high,
                "trail_stop": trail_stop,
                "trailing_pct": pos.trailing_pct,
                "signal_ref_seq": self._entry_signal_seq.get(symbol),
            },
        )

    def _check_maturity(self, symbol: str, bars: list[dict], i: int, tally: _CallTally) -> None:
        if self._config.maturity.require_exit_before_maturity:
            return  # matures at the closing fill, handled in _apply_exit_fill
        for rec in list(self._open_outcomes.values()):
            if rec["symbol"] != symbol:
                continue
            if i - rec["entry_exec_index"] < self._config.maturity.min_bars_after_signal:
                continue
            mark = float(bars[i]["c"])
            cfg = self._config.execution
            est_proceeds = notional_of(mark, rec["qty"], cfg) * (1.0 - cfg.commission_pct / 100.0)
            realized = (
                (est_proceeds - rec["entry_cost"]) / rec["entry_cost"] * 100.0 if rec["entry_cost"] > 0 else 0.0
            )
            self._mature_outcome(
                rec,
                basis="MATURITY_MARK",
                matured_at_index=i,
                matured_at_ts=int(bars[i]["ts"]),
                realized_return_pct=realized,
                open_at_maturity=True,
                mark_price=mark,
                tally=tally,
            )

    def _mature_outcome(
        self,
        rec: dict[str, Any],
        *,
        basis: Literal["EXIT_FILL", "MATURITY_MARK"],
        matured_at_index: int,
        matured_at_ts: int,
        realized_return_pct: float,
        open_at_maturity: bool,
        mark_price: float,
        tally: _CallTally,
    ) -> None:
        stale = False
        stale_after = self._config.maturity.stale_after_seconds
        if stale_after is not None and (matured_at_ts - rec["entry_fill_ts"]) > stale_after:
            stale = True
        r = realized_return_pct
        outcome = "WIN" if r > 1e-9 else ("LOSS" if r < -1e-9 else "FLAT")
        payload = {
            "signal_ref_seq": rec["signal_ref_seq"],
            "symbol": rec["symbol"],
            "outcome": outcome,
            "realized_return_pct": r,
            "matured_at_index": matured_at_index,
            "basis": basis,
            "open_at_maturity": open_at_maturity,
            "stale": stale,
            "mark_price": mark_price,
            "exit_reason": rec.get("exit_reason"),
        }
        self._ledger.append("OUTCOME_MATURED", matured_at_ts, payload)
        self._matured_outcomes.append(dict(payload))
        self._open_outcomes.pop(rec["signal_ref_seq"], None)
        tally.outcomes_matured += 1

    # -- accounting ----------------------------------------------------------

    def _equity_mark(self) -> float:
        total = self._cash
        for sym, pos in self._positions.items():
            close = self._last_close.get(sym, pos.entry_fill_price)
            total += pos.qty * close * self._config.execution.currency_multiplier
        return total

    def _mark_equity(self, symbol: str, close: float) -> None:
        self._last_close[symbol] = close
        equity = self._equity_mark()
        if equity > self._equity_peak:
            self._equity_peak = equity
        if self._equity_peak > 0:
            dd = (self._equity_peak - equity) / self._equity_peak * 100.0
            if dd > self._max_drawdown_pct:
                self._max_drawdown_pct = dd

    def _resolve_leftover_pendings(
        self,
        symbol: str,
        bars: list[dict],
        tally: _CallTally,
        signal_delay_reference: Literal["NEXT_BAR_OPEN", "SAME_BAR_CLOSE"] | None,
    ) -> None:
        """Batch-scoped semantics: intents whose execution bar lies beyond the
        batch are refused honestly (never silently carried across calls)."""
        leftovers = sorted(
            list(self._pending_entries.values()) + list(self._pending_exits.values()),
            key=lambda p: p.signal_seq,
        )
        self._pending_entries.pop(symbol, None)
        self._pending_exits.pop(symbol, None)
        if not leftovers or not bars:
            return
        last_index = len(bars) - 1
        for intent in leftovers:
            cfg = self._config.execution
            pos_qty = self._positions[symbol].qty if symbol in self._positions else 0.0
            if intent.action == "ENTRY":
                fr = simulate_fill(
                    bars=bars, signal_index=intent.signal_index, side="buy",
                    desired_quantity=self._desired_entry_quantity(symbol, bars, intent),
                    cfg=cfg, free_equity=self._cash, current_position=pos_qty,
                )
            else:
                desired = pos_qty if pos_qty > 0 else max(cfg.min_lot, cfg.lot_size)
                fr = simulate_fill(
                    bars=bars, signal_index=intent.signal_index, side="sell",
                    desired_quantity=desired, cfg=cfg, free_equity=self._equity_mark(),
                    current_position=pos_qty,
                )
            if fr.filled and fr.execution_index < len(bars):
                if intent.action == "ENTRY":
                    self._apply_entry_fill(symbol, bars, fr, intent, tally, signal_delay_reference)
                else:
                    self._apply_exit_fill(
                        symbol, bars, qty_filled=fr.quantity, fill_price=fr.fill_price, raw_price=fr.raw_price,
                        reason="SIGNAL_EXIT", index=fr.execution_index, signal_seq=intent.signal_seq,
                        via_intent=True, intent=intent, cap_applied=fr.volume_cap_applied,
                        lot_rounded=fr.lot_rounded, latency_bars=fr.latency_bars, tally=tally,
                        signal_delay_reference=signal_delay_reference,
                    )
            else:
                self._record_rejection(
                    symbol, bars, last_index, intent, fr.refusal_reason or "execution_index_beyond_data", tally
                )

    # -- summary -------------------------------------------------------------

    def summary(self) -> ForwardTestSummary:
        """Run-level summary. Immature and stale outcomes excluded from stats."""
        closed = [o for o in self._matured_outcomes if o["basis"] == "EXIT_FILL" and not o["stale"]]
        rets = [o["realized_return_pct"] for o in closed]
        wins = [r for r in rets if r > 1e-9]
        losses = [r for r in rets if r < -1e-9]
        cfg = self._config.execution
        delays = [d["delay_bars"] for d in self._delay_observations]
        deltas = [d["abs_delta_pct"] for d in self._delay_observations]
        return ForwardTestSummary(
            run_id=self._config.run_id,
            strategy_id=self._config.strategy_id,
            strategy_version=self._config.strategy_version,
            dsl_version=self._config.dsl_version,
            state=self._state,
            data_trust_label=self._config.data_trust_label,
            bars_processed=self._bars_processed,
            signals_total=self._intent_signal_count,
            signals_filled=self._fill_count,
            signals_refused=dict(sorted(self._refusals.items())),
            immature_count=len(self._open_outcomes),
            matured_count=len(self._matured_outcomes),
            stale_outcomes=sum(1 for o in self._matured_outcomes if o["stale"]),
            realized_return_pct=sum(rets) if rets else 0.0,
            win_rate_matured=(len(wins) / len(rets) * 100.0) if rets else 0.0,
            avg_win=(sum(wins) / len(wins)) if wins else None,
            avg_loss=(sum(losses) / len(losses)) if losses else None,
            max_drawdown_pct=self._max_drawdown_pct,
            fees_total=self._fees_total,
            total_delay_bars_mean=(sum(delays) / len(delays)) if delays else None,
            data_gaps=self._data_gaps,
            expected_vs_realized=ExpectedVsRealized(
                mean_abs_delta_pct=(sum(deltas) / len(deltas)) if deltas else None,
                max_abs_delta_pct=max(deltas) if deltas else None,
                observations=len(deltas),
            ),
            cost_model_echo={
                "commission_pct": cfg.commission_pct,
                "spread_pct": cfg.spread_pct,
                "slippage_pct": cfg.slippage_pct,
                "latency_bars": cfg.latency_bars,
                "lot_size": cfg.lot_size,
                "min_lot": cfg.min_lot,
                "min_notional": cfg.min_notional,
                "leverage": cfg.leverage,
                "allow_short": cfg.allow_short,
                "volume_cap_pct": cfg.volume_cap_pct,
                "currency_multiplier": cfg.currency_multiplier,
                "fill_policy": cfg.fill_policy,
                "intrabar_tp_sl": cfg.intrabar_tp_sl,
            },
            engine_version=ENGINE_VERSION,
            execution_model_version=EXECUTION_MODEL_VERSION,
        )

    # -- backtest comparison ---------------------------------------------------

    def _forward_metric_view(self) -> dict[str, float]:
        closed = [o for o in self._matured_outcomes if o["basis"] == "EXIT_FILL" and not o["stale"]]
        rets = [o["realized_return_pct"] for o in closed]
        wins = [r for r in rets if r > 1e-9]
        view: dict[str, float] = {
            "total_return_pct": sum(rets) if rets else 0.0,
            "win_rate": (len(wins) / len(rets) * 100.0) if rets else 0.0,
            "trade_count": float(len(closed)),
            "max_drawdown_pct": self._max_drawdown_pct,
            "fees_total": self._fees_total,
        }
        if wins:
            view["avg_win"] = sum(wins) / len(wins)
        losses = [r for r in rets if r < -1e-9]
        if losses:
            view["avg_loss"] = sum(losses) / len(losses)
        return view

    def compare_with_backtest(
        self,
        backtest_summary_like: Mapping[str, float],
        keys: tuple[str, ...] = ("total_return_pct", "win_rate", "trade_count", "sharpe"),
    ) -> list[dict]:
        """Pure table builder: ``{metric, backtest, forward, delta}`` rows.

        Only keys present in BOTH mappings produce comparable rows. Keys that
        are missing on either side are skipped as comparable rows and reported
        honestly as note-rows (``backtest``/``forward``/``delta`` = None) —
        never silently dropped, never imputed.
        """
        forward_view = self._forward_metric_view()
        rows: list[dict] = []
        for key in keys:
            if key in backtest_summary_like and key in forward_view:
                backtest_value = float(backtest_summary_like[key])
                forward_value = float(forward_view[key])
                rows.append(
                    {"metric": key, "backtest": backtest_value, "forward": forward_value,
                     "delta": round(forward_value - backtest_value, 6)}
                )
            else:
                note = (
                    "missing_in_backtest_summary"
                    if key not in backtest_summary_like
                    else "not_tracked_by_forward_engine"
                )
                rows.append({"metric": key, "backtest": None, "forward": None, "delta": None, "note": note})
        return rows
