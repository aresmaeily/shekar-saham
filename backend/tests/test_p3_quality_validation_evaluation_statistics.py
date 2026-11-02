"""T2 / CONSOL-NEXT Wave 1 — P3 independent validation of
app.domain.evaluation_statistics (MA-1 WS-2).

This file is an ADDITIVE independent cross-check layer. Every expected
value below is hand-computed HERE from first principles with deliberately
different inputs from tests/test_evaluation_statistics.py (dyadic-binary
fractions are used so every intermediate value is EXACT in IEEE-754 and
the asserted equality carries no rounding ambiguity). Where a value
coincides with an existing test by construction, the docstring says so.

Existing coverage (not duplicated here): Bonferroni [0.01,0.04,0.03];
clip [0.9,0.5]; BH [0.01,0.04,0.03] and shuffle; BH ties [0.2,0.1] and
[1.0,1.0]; adjusted_acceptance 3-member Bonf/BH at alpha 0.05; NONE
refusal on a 2-member family; NONE single-attempt honesty flag; alpha
out-of-range; two-family grouping; confusion 2/1/1/2; empty; rates 2/3;
all-TN and perfect-TP undefined cases; format_rate 2/3→0.6667.
"""

import math

import pytest
from pydantic import ValidationError

from app.domain.evaluation_statistics import (
    ConfusionCounts,
    EvaluationFamily,
    OutcomePair,
    adjusted_acceptance,
    benjamin_hochberg_adjust,
    bonferroni_adjust,
    confusion_counts,
    format_rate,
    precision_recall_fp_rate,
)


# ---------------------------------------------------------------------------
# Bonferroni — independent hand computation, m=4, all-dyadic inputs
# ---------------------------------------------------------------------------


def test_p3_bonferroni_m4_dyadic_hand_computed():
    # Hand arithmetic (m = 4; each product is an exact power-of-two scale,
    # so no IEEE-754 rounding is involved anywhere):
    #   0.0625  * 4 = 0.25    (1/16  * 4 = 1/4)
    #   0.125   * 4 = 0.5     (1/8   * 4 = 1/2)
    #   0.21875 * 4 = 0.875   (7/32  * 4 = 7/8)
    #   0.03125 * 4 = 0.125   (1/32  * 4 = 1/8)
    # No product reaches 1.0, so no clipping fires.
    assert bonferroni_adjust([0.0625, 0.125, 0.21875, 0.03125]) == (
        0.25,
        0.5,
        0.875,
        0.125,
    )


def test_p3_bonferroni_clipping_and_identity():
    # Clip case (m = 2): 0.75*2 = 1.5 -> min(1.0, 1.5) = 1.0
    #                    0.625*2 = 1.25 -> min(1.0, 1.25) = 1.0
    assert bonferroni_adjust([0.75, 0.625]) == (1.0, 1.0)
    # m = 1 is the identity: 0.03125 * 1 = 0.03125 (exact).
    assert bonferroni_adjust([0.03125]) == (0.03125,)
    # Empty family: nothing tested, nothing adjusted.
    assert bonferroni_adjust([]) == ()


# ---------------------------------------------------------------------------
# Benjamini-Hochberg — independent hand computation, m=4
# ---------------------------------------------------------------------------


def test_p3_benjamini_hochberg_m4_dyadic_hand_computed():
    # p = [0.1875, 0.5, 0.0625, 0.375], m = 4.
    # Ascending order (stable): 0.0625 (r1), 0.1875 (r2), 0.375 (r3), 0.5 (r4).
    # Raw statistics raw_r = p_(r) * m / r — every quotient is exact:
    #   r1: 0.0625 * 4 / 1 = 0.25
    #   r2: 0.1875 * 4 / 2 = 0.75 / 2 = 0.375
    #   r3: 0.375  * 4 / 3 = 1.5  / 3 = 0.5
    #   r4: 0.5    * 4 / 4 = 2.0  / 4 = 0.5
    # Step-up accumulation from the largest rank down (running starts at 1.0):
    #   r4: running = min(1.0, 0.5) = 0.5   -> adj(r4) = 0.5
    #   r3: 0.5 < 0.5 is False              -> adj(r3) = 0.5
    #   r2: 0.375 < 0.5 -> running = 0.375  -> adj(r2) = 0.375
    #   r1: 0.25  < 0.375 -> running = 0.25 -> adj(r1) = 0.25
    # Mapped back to INPUT order:
    #   idx0 (0.1875, r2) -> 0.375 ; idx1 (0.5, r4) -> 0.5
    #   idx2 (0.0625, r1) -> 0.25  ; idx3 (0.375, r3) -> 0.5
    assert benjamin_hochberg_adjust([0.1875, 0.5, 0.0625, 0.375]) == (
        0.375,
        0.5,
        0.25,
        0.5,
    )


def test_p3_benjamini_hochberg_stepup_pulls_rank3_below_its_raw():
    # The defining BH step-up property: a raw statistic LARGER than a
    # later (higher-rank) running minimum is pulled DOWN to it.
    # p = [0.0625, 0.1875, 0.375, 0.4375] (already ascending), m = 4.
    #   r1: 0.0625  * 4 / 1 = 0.25
    #   r2: 0.1875  * 4 / 2 = 0.375
    #   r3: 0.375   * 4 / 3 = 0.5      <- raw is 0.5
    #   r4: 0.4375  * 4 / 4 = 0.4375   <- running minimum wins
    # Step-up: adj(r4)=0.4375 ; adj(r3)=min(0.5, 0.4375)=0.4375 (PULLED DOWN);
    #          adj(r2)=min(0.375, 0.4375)=0.375 ; adj(r1)=0.25.
    # Input is ascending, so output order equals sorted order.
    assert benjamin_hochberg_adjust([0.0625, 0.1875, 0.375, 0.4375]) == (
        0.25,
        0.375,
        0.4375,
        0.4375,
    )


def test_p3_benjamini_hochberg_ties_get_single_minimum_and_clip():
    # Ties (m = 2): both raws are 0.125*2/1 = 0.25 (r1) and 0.125*2/2 = 0.125
    # (r2); step-up forces the SMALLER rank down to the larger rank's value:
    # adj(r2) = 0.125, adj(r1) = min(0.25, 0.125) = 0.125 -> both 0.125.
    assert benjamin_hochberg_adjust([0.125, 0.125]) == (0.125, 0.125)
    # Clip case (m = 2, [1.0, 0.75]): raws r1 = 0.75*2 = 1.5, r2 = 1.0*2/2 = 1.0
    # -> running = 1.0 throughout, clipped to 1.0 -> (1.0, 1.0).
    assert benjamin_hochberg_adjust([1.0, 0.75]) == (1.0, 1.0)
    # Invalid input still refused with the same reason-code shape.
    with pytest.raises(ValueError, match="pvalue_out_of_range:index=1"):
        benjamin_hochberg_adjust([0.25, -0.125])


# ---------------------------------------------------------------------------
# adjusted_acceptance — independent two-family batch, boundary equality
# ---------------------------------------------------------------------------


def _fam(pvalue: float, family_id: str, attempt: int, hypothesis: str = "H-P3") -> EvaluationFamily:
    return EvaluationFamily(
        family_id=family_id,
        hypothesis_id=hypothesis,
        attempt_index=attempt,
        metric_name="sharpe_ratio",
        pvalue=pvalue,
    )


def test_p3_adjusted_acceptance_two_families_different_sizes_bonferroni():
    # alpha = 0.25 (dyadic; comparisons below are all strict except one).
    # F-ALPHA (m = 2): 0.0625*2 = 0.125 ; 0.25*2 = 0.5.
    #   0.125 <= 0.25 -> ACCEPTED ; 0.5 > 0.25 -> REJECTED.
    # F-BETA (m = 4): 0.1875*4 = 0.75 ; 0.5*4 = 2.0 -> clip 1.0 ;
    #                 0.0625*4 = 0.25 ; 0.375*4 = 1.5 -> clip 1.0.
    #   0.75 > 0.25 -> REJECTED ; 1.0 > 0.25 -> REJECTED ;
    #   0.25 <= 0.25 -> ACCEPTED (EXACT boundary equality accepts) ;
    #   1.0 > 0.25 -> REJECTED.
    families = [
        _fam(0.0625, "F-ALPHA", 1),
        _fam(0.25, "F-ALPHA", 2),
        _fam(0.1875, "F-BETA", 1),
        _fam(0.5, "F-BETA", 2),
        _fam(0.0625, "F-BETA", 3),
        _fam(0.375, "F-BETA", 4),
    ]
    verdicts = adjusted_acceptance(families, method="BONFERRONI", alpha=0.25)
    assert [v.adjusted_pvalue for v in verdicts] == [
        0.125,
        0.5,
        0.75,
        1.0,
        0.25,
        1.0,
    ]
    assert [v.verdict for v in verdicts] == [
        "ACCEPTED",
        "REJECTED",
        "REJECTED",
        "REJECTED",
        "ACCEPTED",
        "REJECTED",
    ]
    # Boundary equality is AT-OR-BELOW (accepts) — pinned explicitly.
    assert verdicts[4].reason_codes == ("ADJUSTED_PVALUE_AT_OR_BELOW_ALPHA",)
    assert all(v.unadjusted is False for v in verdicts)
    # Family size is per-group: F-ALPHA used m=2, F-BETA used m=4 (a single
    # global m would have produced 0.0625*6=0.375 for F-ALPHA's first member).
    assert verdicts[0].adjusted_pvalue == 0.125


def test_p3_adjusted_acceptance_none_mixed_batch_refuses_multi_only():
    # One call, method NONE, two families of DIFFERENT sizes:
    #   F-GAMMA (m = 1): p = 0.0625 <= alpha 0.25 -> ACCEPTED with the
    #     honesty flag unadjusted=True and reason
    #     UNADJUSTED_ACCEPTANCE_SINGLE_ATTEMPT (the flag marks the METHOD,
    #     not the outcome).
    #   F-DELTA (m = 2): REFUSED regardless of p — reason
    #     UNADJUSTED_ACCEPTANCE_IS_FORBIDDEN_FOR_FAMILIES_OVER_ONE,
    #     accepted=None, adjusted_pvalue=None, unadjusted=False.
    families = [
        _fam(0.0625, "F-GAMMA", 1),
        _fam(0.01, "F-DELTA", 1),
        _fam(0.02, "F-DELTA", 2),
    ]
    verdicts = adjusted_acceptance(families, method="NONE", alpha=0.25)
    assert len(verdicts) == 3
    solo = verdicts[0]
    assert (solo.family_id, solo.verdict, solo.accepted) == ("F-GAMMA", "ACCEPTED", True)
    assert solo.adjusted_pvalue == 0.0625  # NONE m=1: adjusted == raw
    assert solo.unadjusted is True
    assert solo.reason_codes == ("UNADJUSTED_ACCEPTANCE_SINGLE_ATTEMPT",)
    for refused in verdicts[1:]:
        assert refused.family_id == "F-DELTA"
        assert refused.verdict == "REFUSED"
        assert refused.accepted is None
        assert refused.adjusted_pvalue is None
        assert refused.unadjusted is False
        assert refused.reason_codes == (
            "UNADJUSTED_ACCEPTANCE_IS_FORBIDDEN_FOR_FAMILIES_OVER_ONE",
        )


def test_p3_adjusted_acceptance_alpha_validation_is_fail_closed():
    # alpha must lie strictly inside (0, 1); refusals are exceptions, never
    # silent verdicts. (Pinned by inspection: the module coerces
    # NUMERIC-STRING alphas via float() — the same policy as for p-values —
    # so only genuinely non-numeric values hit alpha_not_numeric.)
    families = [_fam(0.0625, "F-ONE", 1)]
    for bad in (0.0, 1.0, -0.25, 1.25, math.inf, -math.inf):
        with pytest.raises(ValueError, match="alpha_out_of_range"):
            adjusted_acceptance(families, method="BONFERRONI", alpha=bad)
    for non_numeric in (None, "abc", object()):
        with pytest.raises(ValueError, match="alpha_not_numeric"):
            adjusted_acceptance(families, method="BONFERRONI", alpha=non_numeric)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# FP / FN confusion + rates — independent counts
# ---------------------------------------------------------------------------


def _pair(signal: bool, matured: bool) -> OutcomePair:
    return OutcomePair(signal_positive=signal, matured_positive=matured)


def test_p3_confusion_seven_outcomes_hand_counted_and_order_independent():
    # Hand tally over 7 explicit outcomes:
    #   3 x (signal, matured)      -> TP
    #   2 x (signal, not matured)  -> FP
    #   1 x (no signal, matured)   -> FN
    #   1 x (no signal, not matur) -> TN
    outcomes = [
        _pair(True, True),
        _pair(True, False),
        _pair(True, True),
        _pair(False, False),
        _pair(False, True),
        _pair(True, True),
        _pair(True, False),
    ]
    counts = confusion_counts(outcomes)
    assert counts.true_positive == 3
    assert counts.false_positive == 2
    assert counts.false_negative == 1
    assert counts.true_negative == 1
    assert counts.total == 7  # 3 + 2 + 1 + 1
    # Order-independence: a permutation of the SAME outcomes yields the
    # identical counts (counting, not sequence statistics).
    shuffled = [
        _pair(False, True),
        _pair(True, False),
        _pair(True, True),
        _pair(True, False),
        _pair(False, False),
        _pair(True, True),
        _pair(True, True),
    ]
    assert confusion_counts(shuffled) == counts
    # Rates from these exact integers (single divisions, no rounding):
    #   precision = TP/(TP+FP) = 3/5 = 0.6
    #   recall    = TP/(TP+FN) = 3/4 = 0.75
    #   fp_rate   = FP/(FP+TN) = 2/3  (nearest double to 2/3)
    rates = precision_recall_fp_rate(counts)
    assert rates.precision == 3 / 5
    assert rates.recall == 3 / 4
    assert rates.false_positive_rate == 2 / 3
    assert rates.undefined == ()


def test_p3_rates_all_false_positives_precision_is_exact_zero_not_none():
    # Adversarial honesty case: the model signalled twice, matured labels
    # are negative, and one no-signal/no-event pair exists.
    #   TP=0, FP=2, FN=0, TN=1.
    #   precision = 0/(0+2) = 0.0  -> DEFINED and exactly 0.0 (a real
    #     measurement of zero, NOT a faked placeholder: the denominator
    #     is non-zero, so None would be wrong here).
    #   recall    = TP/(TP+FN) = 0/0 -> UNDEFINED -> None + reason code
    #     RECALL_UNDEFINED_NO_MATURED_POSITIVES.
    #   fp_rate   = FP/(FP+TN) = 2/3.
    counts = ConfusionCounts(
        true_positive=0, false_positive=2, false_negative=0, true_negative=1, total=3
    )
    rates = precision_recall_fp_rate(counts)
    assert rates.precision == 0.0
    assert rates.precision is not None
    assert rates.recall is None
    assert rates.false_positive_rate == 2 / 3
    assert rates.undefined == ("RECALL_UNDEFINED_NO_MATURED_POSITIVES",)


def test_p3_format_rate_zero_digits_and_ties_to_even():
    # digits=0 boundary (integer display) was not pinned by existing tests.
    # round() is deterministic for a fixed input double:
    assert format_rate(0.6, 0) == 1.0
    assert format_rate(0.4, 0) == 0.0
    # Exactly representable tie 0.5 at digits=0: Python's round uses
    # ties-to-even -> 0.0 (NOT 1.0). Pinned as documented behavior.
    assert format_rate(0.5, 0) == 0.0
    # None stays None at any digit count (undefined is never a number).
    assert format_rate(None, 0) is None
    with pytest.raises(ValueError, match="digits_must_be_non_negative_int"):
        format_rate(0.5, 2.0)  # type: ignore[arg-type]  # float digit count refused


def test_p3_evaluation_family_rejects_non_finite_pvalue():
    # allow_inf_nan=False on the frozen model: NaN/inf p-values cannot even
    # enter a family (defense in depth behind _validated_pvalue).
    with pytest.raises(ValidationError):
        _fam(math.nan, "F-NAN", 1)
    with pytest.raises(ValidationError):
        _fam(math.inf, "F-INF", 1)
    with pytest.raises(ValidationError):
        EvaluationFamily(
            family_id="",  # empty family_id refused by min_length
            hypothesis_id="H",
            attempt_index=1,
            metric_name="m",
            pvalue=0.1,
        )
