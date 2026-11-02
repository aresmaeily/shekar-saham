"""T2 / CONSOL-NEXT Wave 1 — P3 independent validation of
app.engines.holdout (MA-1 WS-2).

ADDITIVE gap tests. Existing coverage (tests/test_holdout.py, not
duplicated): n=10/f=0.4 split, boundary=7.0 frontier, fraction refusals
(0.0/-0.1/0.5/0.75/1.0, "0.3", nan), empty/unsorted/duplicate bars,
zero-bar holdout, bar_timestamp refusals, selection touching boundary,
selection inside holdout, insample crossing boundary, holdout before
declared boundary, empty segments, non-numeric/inf boundary, frozen
record (mutation attempt).

Gaps filled here: exact-dyadic splits with partition-completeness +
no-leakage proofs; inf and bool fractions; boundary_ts_of on an empty
segment; zero-length selection window; and the adversarial
isolated:True-only-via-passing-path property (no attestation instance
can escape a failing path, and the record type itself refuses
isolated=False at construction).
"""

import pytest
from pydantic import ValidationError

from app.engines.holdout import (
    HoldoutAttestation,
    HoldoutViolation,
    SelectionWindow,
    assert_no_selection_on_holdout,
    boundary_ts_of,
    split_holdout,
)


def _bars(count: int, start: int = 1) -> list[dict]:
    return [{"ts": i, "pl": 100.0 + i} for i in range(start, start + count)]


# ---------------------------------------------------------------------------
# Split semantics: dyadic fractions, partition completeness, no leakage
# ---------------------------------------------------------------------------


def test_p3_split_dyadic_fractions_partition_complete_and_leak_free():
    # Case 1: n = 8, f = 0.375 (= 3/8, exactly representable).
    #   holdout_count = floor(8 * 0.375) = floor(3.0) = 3 (exact product).
    #   insample = ts 1..5, holdout = ts 6..8, boundary = 6.0.
    bars8 = _bars(8)
    insample, holdout = split_holdout(bars8, 0.375)
    assert [b["ts"] for b in insample] == [1, 2, 3, 4, 5]
    assert [b["ts"] for b in holdout] == [6, 7, 8]
    assert boundary_ts_of(holdout) == 6.0
    # NO LEAKAGE across the boundary: every insample timestamp is strictly
    # below every holdout timestamp (max insample < min holdout).
    assert max(b["ts"] for b in insample) < min(b["ts"] for b in holdout)
    # PARTITION COMPLETENESS: the two segments are disjoint and their union
    # is exactly the original sequence — no bar lost, none duplicated.
    assert len(insample) + len(holdout) == len(bars8)
    merged_ts = sorted([b["ts"] for b in insample] + [b["ts"] for b in holdout])
    assert merged_ts == [b["ts"] for b in bars8]

    # Case 2: n = 12, f = 0.25 (= 1/4, exact). floor(12 * 0.25) = 3.
    #   insample = ts 1..9, holdout = ts 10..12, boundary = 10.0.
    bars12 = _bars(12)
    insample12, holdout12 = split_holdout(bars12, 0.25)
    assert [b["ts"] for b in insample12] == list(range(1, 10))
    assert [b["ts"] for b in holdout12] == [10, 11, 12]
    assert max(b["ts"] for b in insample12) < min(b["ts"] for b in holdout12)
    assert len(insample12) + len(holdout12) == 12


def test_p3_split_refuses_inf_and_boolean_fractions():
    # nan was already covered by existing tests; inf and the bool special
    # case (True/False are ints in Python — a flag is not a fraction) were
    # not. All must hit the same closed reason code.
    bars = _bars(8)
    for bad_fraction in (float("inf"), -float("inf"), True, False):
        with pytest.raises(
            HoldoutViolation, match="HOLDOUT_FRACTION_NOT_IN_OPEN_INTERVAL"
        ):
            split_holdout(bars, bad_fraction)  # type: ignore[arg-type]


def test_p3_boundary_ts_of_empty_segment_refused():
    # Reason code exists in the module (EMPTY_HOLDOUT_SEGMENT for a
    # zero-bar holdout passed to boundary_ts_of) — previously untested.
    with pytest.raises(HoldoutViolation, match="EMPTY_HOLDOUT_SEGMENT"):
        boundary_ts_of([])


def test_p3_zero_length_selection_window_is_valid_when_strictly_before_boundary():
    # SelectionWindow requires end >= start; start == end (a point
    # decision, no window) is legal. The attestation must accept it when
    # the point lies strictly before the holdout boundary.
    insample, holdout = split_holdout(_bars(8), 0.375)  # boundary = 6.0
    point_window = SelectionWindow(
        strategy_id="S-POINT", selection_start_ts=3.0, selection_end_ts=3.0
    )
    attestation = assert_no_selection_on_holdout(
        point_window,
        holdout_boundary_ts=boundary_ts_of(holdout),
        insample_bars=insample,
        holdout_bars=holdout,
    )
    assert attestation.isolated is True
    assert attestation.strategy_id == "S-POINT"
    assert (attestation.insample_bar_count, attestation.holdout_bar_count) == (5, 3)


# ---------------------------------------------------------------------------
# Adversarial: isolated=True is reachable ONLY through the passing path
# ---------------------------------------------------------------------------


def test_p3_no_failing_path_can_produce_an_attestation_instance():
    # For EVERY refusal scenario, the call raises HoldoutViolation and —
    # because the function raises instead of returning — no attestation
    # object exists afterwards. If any failing path ever returned a record
    # (or a subclass instance), this test would fail loudly.
    insample, holdout = split_holdout(_bars(8), 0.375)  # boundary = 6.0
    good_window = SelectionWindow(
        strategy_id="S1", selection_start_ts=1.0, selection_end_ts=5.0
    )
    adversarial_scenarios = [
        # (label, kwargs) — each must RAISE, never return a record.
        (
            "selection_touches_boundary",
            dict(
                selection_window=SelectionWindow(
                    strategy_id="S1", selection_start_ts=1.0, selection_end_ts=6.0
                ),
                holdout_boundary_ts=6.0,
                insample_bars=insample,
                holdout_bars=holdout,
            ),
        ),
        (
            "selection_after_boundary",
            dict(
                selection_window=SelectionWindow(
                    strategy_id="S1", selection_start_ts=7.0, selection_end_ts=8.0
                ),
                holdout_boundary_ts=6.0,
                insample_bars=insample,
                holdout_bars=holdout,
            ),
        ),
        (
            "insample_crosses_boundary",
            dict(
                selection_window=good_window,
                holdout_boundary_ts=6.0,
                insample_bars=_bars(7, start=1),  # ts 1..7 leaks past 6.0
                holdout_bars=holdout,
            ),
        ),
        (
            "holdout_starts_after_declared_boundary",
            dict(
                selection_window=good_window,
                holdout_boundary_ts=5.0,  # holdout actually starts at 6.0
                insample_bars=insample,
                holdout_bars=holdout,
            ),
        ),
        (
            "empty_insample",
            dict(
                selection_window=good_window,
                holdout_boundary_ts=6.0,
                insample_bars=[],
                holdout_bars=holdout,
            ),
        ),
        (
            "empty_holdout",
            dict(
                selection_window=good_window,
                holdout_boundary_ts=6.0,
                insample_bars=insample,
                holdout_bars=[],
            ),
        ),
        (
            "nonfinite_boundary",
            dict(
                selection_window=good_window,
                holdout_boundary_ts=float("nan"),
                insample_bars=insample,
                holdout_bars=holdout,
            ),
        ),
    ]
    for label, kwargs in adversarial_scenarios:
        with pytest.raises(HoldoutViolation) as excinfo:
            assert_no_selection_on_holdout(**kwargs)
        # A refusal carries a machine-readable reason (never an empty one).
        assert excinfo.value.reason, label


def test_p3_attestation_type_refuses_isolated_false_at_construction():
    # The type itself is a second line of defense: Literal[True] means a
    # record with isolated=False cannot even be CONSTRUCTED (directly or
    # via model_validate) — not merely that mutation is refused (the
    # mutation case is already covered by the existing suite).
    fields = dict(
        strategy_id="S1",
        holdout_boundary_ts=6.0,
        insample_first_ts=1.0,
        insample_last_ts=5.0,
        holdout_first_ts=6.0,
        holdout_last_ts=8.0,
        insample_bar_count=5,
        holdout_bar_count=3,
    )
    with pytest.raises(ValidationError):
        HoldoutAttestation(**fields, isolated=False)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        HoldoutAttestation.model_validate({**fields, "isolated": False})
    # The only constructible value is isolated=True with all fields present.
    record = HoldoutAttestation(**fields)
    assert record.isolated is True
