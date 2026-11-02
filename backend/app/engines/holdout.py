"""Dataset-level holdout isolation for the evaluation harness (P3).

Corpus loci (2026-10-02 amendment corpus):
- 02_EXECUTION_ROADMAP lines 27-30 ("P3 --- Evaluation Harness"): "...
  reproducibility, holdout and multiple-testing controls."
- 02 line 145 ("P3 --- Evaluation and research integrity"): "... holdout
  isolation, multiple-testing controls, ...".
- 06 Product Capability Charter, "Research and feedback": "Reproducible
  runs demonstrate ... holdout protection ...".

Scope: purely additive, deterministic, offline. Bars are the SAME public
bar-mapping shape consumed by `app.engines.backtest` (mappings with a
numeric ``"ts"`` key; price field irrelevant here). This module consumes
only public structures and imports no private helper of any module.

Integrity rules (fail-closed, machine-readable reason codes):
- The holdout segment is ALWAYS a minority: ``holdout_fraction`` must lie
  strictly inside the open interval (0, 0.5). Fractions >= 0.5 would let
  the "locked" segment dominate the evidence and are refused.
- Bars must be non-empty, strictly time-ordered, with unique timestamps.
- The holdout is the TAIL of the dataset: nothing from the holdout window
  may influence selection, so `assert_no_selection_on_holdout` attests
  that the selection window ended STRICTLY before the holdout boundary.
- `HoldoutAttestation.isolated` is typed ``Literal[True]``: the only way
  to obtain an attestation is through the all-checks-passed path; every
  failing path raises `HoldoutViolation` instead of emitting a record.

Rounding policy: the split size is ``floor(n * holdout_fraction)`` in IEEE
double arithmetic (deterministic for fixed inputs); NO other rounding, no
I/O, no wall-clock — every timestamp is an explicit value carried by the
input bars.
"""

from __future__ import annotations

import math
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HoldoutViolation(ValueError):
    """Deterministic refusal carrying a machine-readable reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}:{detail}" if detail else reason
        super().__init__(message)


def bar_timestamp(bar: Mapping[str, Any]) -> float:
    """Public accessor for the numeric ``"ts"`` field of a backtest bar.

    Refuses missing/non-numeric/boolean timestamps and non-finite values
    with deterministic reason codes (booleans are ints in Python and are
    explicitly rejected: a truth flag is not a timestamp).
    """
    ts = bar.get("ts") if isinstance(bar, Mapping) else None
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        raise HoldoutViolation("BAR_TS_MISSING_OR_NON_NUMERIC", repr(ts))
    tsf = float(ts)
    if not math.isfinite(tsf):
        raise HoldoutViolation("BAR_TS_NOT_FINITE", repr(ts))
    return tsf


def require_sorted_unique_bars(
    bars: Sequence[Mapping[str, Any]],
) -> tuple[float, ...]:
    """Deterministic bar-sequence integrity check.

    Returns the tuple of timestamps; raises `HoldoutViolation` with reason
    ``EMPTY_BAR_SEQUENCE`` (empty input), ``UNSORTED_BARS`` (a timestamp
    decreases) or ``DUPLICATE_TIMESTAMPS`` (a timestamp repeats). Strictly
    increasing time is the precondition for every timestamp-boundary
    operation in this module.
    """
    if len(bars) == 0:
        raise HoldoutViolation("EMPTY_BAR_SEQUENCE")
    tss: list[float] = []
    previous: float | None = None
    for index, bar in enumerate(bars):
        ts = bar_timestamp(bar)
        if previous is not None:
            if ts < previous:
                raise HoldoutViolation("UNSORTED_BARS", f"index={index}")
            if ts == previous:
                raise HoldoutViolation("DUPLICATE_TIMESTAMPS", f"index={index}")
        tss.append(ts)
        previous = ts
    return tuple(tss)


def split_holdout(
    bars: Sequence[Mapping[str, Any]],
    holdout_fraction: float,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    """Split time-ordered bars into ``(insample_bars, holdout_bars)``.

    The holdout is the TAIL of the sequence:
      ``holdout_count = floor(n * holdout_fraction)`` (>= 1),
      ``insample = bars[:n - holdout_count]``, ``holdout = bars[n - holdout_count:]``.
    The split boundary is the timestamp of the first holdout bar (see
    `boundary_ts_of`). The returned tuples hold the SAME bar mappings (no
    copies, no mutation).

    Refusals (all `HoldoutViolation` with reason codes):
      - ``HOLDOUT_FRACTION_NOT_IN_OPEN_INTERVAL``: fraction not finite,
        <= 0 or >= 0.5 — the holdout must remain a minority segment;
      - ``EMPTY_BAR_SEQUENCE``; ``UNSORTED_BARS``; ``DUPLICATE_TIMESTAMPS``;
      - ``HOLDOUT_SEGMENT_EMPTY``: floor(n * fraction) < 1 (fraction too
        small for the dataset — a zero-bar holdout would be a fake
        attestation surface).
    """
    if isinstance(holdout_fraction, bool) or not isinstance(holdout_fraction, (int, float)):
        raise HoldoutViolation(
            "HOLDOUT_FRACTION_NOT_IN_OPEN_INTERVAL", repr(holdout_fraction)
        )
    fraction = float(holdout_fraction)
    if not math.isfinite(fraction) or fraction <= 0.0 or fraction >= 0.5:
        raise HoldoutViolation(
            "HOLDOUT_FRACTION_NOT_IN_OPEN_INTERVAL", repr(holdout_fraction)
        )
    if len(bars) == 0:
        raise HoldoutViolation("EMPTY_BAR_SEQUENCE")
    require_sorted_unique_bars(bars)
    holdout_count = int(len(bars) * fraction)  # floor for positive operands
    if holdout_count < 1:
        raise HoldoutViolation(
            "HOLDOUT_SEGMENT_EMPTY", f"n={len(bars)} fraction={fraction!r}"
        )
    insample = tuple(bars[:-holdout_count])
    holdout = tuple(bars[-holdout_count:])
    return insample, holdout


def boundary_ts_of(holdout_bars: Sequence[Mapping[str, Any]]) -> float:
    """Holdout boundary = timestamp of the FIRST holdout bar."""
    if len(holdout_bars) == 0:
        raise HoldoutViolation("EMPTY_HOLDOUT_SEGMENT")
    return bar_timestamp(holdout_bars[0])


class SelectionWindow(BaseModel):
    """Explicit declaration of WHEN strategy selection happened.

    Selection = any choice among candidate hypotheses/filters/parameters.
    The window is declared by the caller (explicit-in, explicit-out); the
    attestation compares it against the holdout boundary.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    strategy_id: str = Field(min_length=1, max_length=128)
    selection_start_ts: float
    selection_end_ts: float

    @model_validator(mode="after")
    def _ordered(self) -> "SelectionWindow":
        if self.selection_end_ts < self.selection_start_ts:
            raise ValueError("selection_window_end_before_start")
        return self


class HoldoutAttestation(BaseModel):
    """Frozen attestation that the holdout stayed untouched by selection.

    ``isolated`` is typed ``Literal[True]``: this record exists only on the
    all-checks-passed path; violations raise instead of emitting a record.

    MASTER-WAVE-2 hardening (P3 finding F1, W2-QUANT confirmed): the
    attestation is now cross-field-consistent AT THE TYPE LEVEL. The only
    legitimate emitting path (``assert_no_selection_on_holdout``) already
    enforces every invariant below by construction; the validator closes the
    DIRECT-construction forgery path (a hand-built record whose fields
    contradict each other) so a forged attestation can never round-trip the
    type. Refusals raise ``ValueError`` with stable reason codes (pydantic
    wraps them as ``ValidationError``); legitimate records validate freely.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    strategy_id: str
    holdout_boundary_ts: float
    insample_first_ts: float
    insample_last_ts: float
    holdout_first_ts: float
    holdout_last_ts: float
    insample_bar_count: int
    holdout_bar_count: int
    isolated: Literal[True] = True

    @model_validator(mode="after")
    def _cross_field_consistency(self) -> "HoldoutAttestation":
        if self.insample_bar_count < 1:
            raise ValueError("attestation_insample_bar_count_below_one")
        if self.holdout_bar_count < 1:
            raise ValueError("attestation_holdout_bar_count_below_one")
        if self.insample_first_ts > self.insample_last_ts:
            raise ValueError("attestation_insample_window_inverted")
        if self.holdout_first_ts > self.holdout_last_ts:
            raise ValueError("attestation_holdout_window_inverted")
        if self.insample_last_ts >= self.holdout_boundary_ts:
            # mirrors INSAMPLE_CROSSES_HOLDOUT_BOUNDARY (strict inequality)
            raise ValueError("attestation_insample_crosses_holdout_boundary")
        if self.holdout_first_ts < self.holdout_boundary_ts:
            # mirrors HOLDOUT_SEGMENT_BEFORE_BOUNDARY (first holdout bar at
            # or after the declared boundary)
            raise ValueError("attestation_holdout_before_boundary")
        return self


def assert_no_selection_on_holdout(
    selection_window: SelectionWindow,
    *,
    holdout_boundary_ts: float,
    insample_bars: Sequence[Mapping[str, Any]],
    holdout_bars: Sequence[Mapping[str, Any]],
) -> HoldoutAttestation:
    """Attest that the declared selection window closed strictly before the
    holdout boundary, and that both segments are internally consistent.

    Checks (each refusal is a `HoldoutViolation` with a reason code):
      - ``EMPTY_INSAMPLE_SEGMENT`` / ``EMPTY_HOLDOUT_SEGMENT``: degenerate
        segments would make the attestation vacuous;
      - ``UNSORTED_BARS`` / ``DUPLICATE_TIMESTAMPS`` / ``BAR_TS_*``: segment
        integrity (via `require_sorted_unique_bars`);
      - ``INSAMPLE_CROSSES_HOLDOUT_BOUNDARY``: an insample bar at or after
        the boundary means the "insample" segment leaks into the holdout;
      - ``HOLDOUT_SEGMENT_BEFORE_BOUNDARY``: the holdout segment must start
        exactly at the declared boundary;
      - ``SELECTION_WINDOW_OVERLAPS_HOLDOUT``: the selection window must
        have ended STRICTLY before the boundary — touching the boundary is
        already a violation (strict inequality, no off-by-one leniency).
    """
    if isinstance(holdout_boundary_ts, bool) or not isinstance(
        holdout_boundary_ts, (int, float)
    ):
        raise HoldoutViolation("HOLDOUT_BOUNDARY_NOT_NUMERIC", repr(holdout_boundary_ts))
    boundary = float(holdout_boundary_ts)
    if not math.isfinite(boundary):
        raise HoldoutViolation("HOLDOUT_BOUNDARY_NOT_FINITE", repr(holdout_boundary_ts))
    if len(insample_bars) == 0:
        raise HoldoutViolation("EMPTY_INSAMPLE_SEGMENT")
    if len(holdout_bars) == 0:
        raise HoldoutViolation("EMPTY_HOLDOUT_SEGMENT")
    insample_ts = require_sorted_unique_bars(insample_bars)
    holdout_ts = require_sorted_unique_bars(holdout_bars)
    if insample_ts[-1] >= boundary:
        raise HoldoutViolation(
            "INSAMPLE_CROSSES_HOLDOUT_BOUNDARY", f"last_insample_ts={insample_ts[-1]!r}"
        )
    if holdout_ts[0] < boundary:
        raise HoldoutViolation(
            "HOLDOUT_SEGMENT_BEFORE_BOUNDARY", f"first_holdout_ts={holdout_ts[0]!r}"
        )
    if selection_window.selection_end_ts >= boundary:
        raise HoldoutViolation(
            "SELECTION_WINDOW_OVERLAPS_HOLDOUT",
            f"selection_end_ts={selection_window.selection_end_ts!r} boundary={boundary!r}",
        )
    return HoldoutAttestation(
        strategy_id=selection_window.strategy_id,
        holdout_boundary_ts=boundary,
        insample_first_ts=insample_ts[0],
        insample_last_ts=insample_ts[-1],
        holdout_first_ts=holdout_ts[0],
        holdout_last_ts=holdout_ts[-1],
        insample_bar_count=len(insample_bars),
        holdout_bar_count=len(holdout_bars),
        isolated=True,
    )
