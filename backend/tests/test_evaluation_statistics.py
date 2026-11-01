"""Tests for app.domain.evaluation_statistics (P3 multiple-testing + FP/FN).

All expected values are HAND-COMPUTED (not mirrored from the
implementation output): Bonferroni/BH arithmetic is worked out in the
comments; confusion counts are counted by hand.
"""

import math

import pytest
from pydantic import ValidationError

from app.domain.evaluation_statistics import (
    ClassificationRates,
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
# Bonferroni (hand-computed)
# ---------------------------------------------------------------------------


def test_bonferroni_hand_computed():
    # m = 3: 0.01*3 = 0.03 ; 0.04*3 = 0.12 ; 0.03*3 = 0.09 (all exact)
    assert bonferroni_adjust([0.01, 0.04, 0.03]) == (0.03, 0.12, 0.09)


def test_bonferroni_clips_at_one_and_handles_empty_single():
    # 0.9*2 = 1.8 -> clip 1.0 ; 0.5*2 = 1.0 -> 1.0
    assert bonferroni_adjust([0.9, 0.5]) == (1.0, 1.0)
    # m = 1 is the identity (0.02*1 = 0.02); empty input tests nothing.
    assert bonferroni_adjust([0.02]) == (0.02,)
    assert bonferroni_adjust([]) == ()


def test_bonferroni_refuses_invalid_pvalues_with_reason_codes():
    with pytest.raises(ValueError, match="pvalue_out_of_range:index=0"):
        bonferroni_adjust([1.5, 0.1])
    with pytest.raises(ValueError, match="pvalue_out_of_range:index=1"):
        bonferroni_adjust([0.1, -0.1])
    with pytest.raises(ValueError, match="pvalue_not_finite:index=0"):
        bonferroni_adjust([float("nan")])
    with pytest.raises(ValueError, match="pvalue_not_finite"):
        bonferroni_adjust([float("inf")])
    with pytest.raises(ValueError, match="pvalue_not_numeric:index=0"):
        bonferroni_adjust(["not-a-number"])


# ---------------------------------------------------------------------------
# Benjamini-Hochberg (hand-computed)
# ---------------------------------------------------------------------------


def test_benjamin_hochberg_hand_computed():
    # p = [0.01, 0.04, 0.03], m = 3. Ascending: 0.01(r1), 0.03(r2), 0.04(r3).
    # raw: r1 = 0.01*3/1 = 0.03 ; r2 = 0.03*3/2 = 0.045 ; r3 = 0.04*3/3 = 0.04.
    # Step-up from the largest rank: adj(r3) = 0.04 ;
    # adj(r2) = min(0.045, 0.04) = 0.04 ; adj(r1) = min(0.03, 0.04) = 0.03.
    # Input order: [0.01 -> 0.03, 0.04 -> 0.04, 0.03 -> 0.04].
    assert benjamin_hochberg_adjust([0.01, 0.04, 0.03]) == (0.03, 0.04, 0.04)


def test_benjamin_hochberg_preserves_input_order():
    # Same set as above, shuffled: idx0 = 0.04 -> 0.04, idx1 = 0.01 -> 0.03,
    # idx2 = 0.03 -> 0.04.
    assert benjamin_hochberg_adjust([0.04, 0.01, 0.03]) == (0.04, 0.03, 0.04)


def test_benjamin_hochberg_ties_and_boundaries():
    # [0.2, 0.1]: raw(r1=0.1) = 0.1*2/1 = 0.2 ; raw(r2=0.2) = 0.2*2/2 = 0.2
    # -> both adjusted to 0.2 (monotone step-up keeps them equal).
    assert benjamin_hochberg_adjust([0.2, 0.1]) == (0.2, 0.2)
    assert benjamin_hochberg_adjust([1.0, 1.0]) == (1.0, 1.0)
    assert benjamin_hochberg_adjust([]) == ()


def test_benjamin_hochberg_refuses_invalid_pvalues():
    with pytest.raises(ValueError, match="pvalue_out_of_range"):
        benjamin_hochberg_adjust([0.5, 2.0])
    with pytest.raises(ValueError, match="pvalue_not_finite"):
        benjamin_hochberg_adjust([math.nan])


# ---------------------------------------------------------------------------
# EvaluationFamily + adjusted_acceptance
# ---------------------------------------------------------------------------


def _family(pvalue: float, family_id: str = "F1", attempt: int = 1) -> EvaluationFamily:
    return EvaluationFamily(
        family_id=family_id,
        hypothesis_id="H-100",
        attempt_index=attempt,
        metric_name="total_return",
        pvalue=pvalue,
    )


def test_evaluation_family_model_validation():
    with pytest.raises(ValidationError):
        EvaluationFamily(
            family_id="F1",
            hypothesis_id="H",
            attempt_index=1,
            metric_name="m",
            pvalue=1.5,  # outside [0, 1]
        )
    with pytest.raises(ValidationError):
        EvaluationFamily(
            family_id="F1",
            hypothesis_id="H",
            attempt_index=0,  # attempts are 1-based
            metric_name="m",
            pvalue=0.1,
        )
    member = _family(0.05)
    with pytest.raises(ValidationError):
        member.pvalue = 0.9  # frozen


def test_adjusted_acceptance_bonferroni_hand_computed():
    families = [_family(0.01, attempt=1), _family(0.04, attempt=2), _family(0.03, attempt=3)]
    verdicts = adjusted_acceptance(families, method="BONFERRONI", alpha=0.05)
    assert [v.adjusted_pvalue for v in verdicts] == [0.03, 0.12, 0.09]
    assert [v.verdict for v in verdicts] == ["ACCEPTED", "REJECTED", "REJECTED"]
    assert [v.accepted for v in verdicts] == [True, False, False]
    assert all(v.unadjusted is False for v in verdicts)
    assert verdicts[0].reason_codes == ("ADJUSTED_PVALUE_AT_OR_BELOW_ALPHA",)
    assert verdicts[1].reason_codes == ("ADJUSTED_PVALUE_ABOVE_ALPHA",)


def test_adjusted_acceptance_benjamin_hochberg_accepts_all_three():
    # BH adjusted = (0.03, 0.04, 0.04) — all at or below alpha = 0.05.
    families = [_family(0.01, attempt=1), _family(0.04, attempt=2), _family(0.03, attempt=3)]
    verdicts = adjusted_acceptance(families, method="BENJAMIN_HOCHBERG", alpha=0.05)
    assert [v.adjusted_pvalue for v in verdicts] == [0.03, 0.04, 0.04]
    assert all(v.verdict == "ACCEPTED" for v in verdicts)


def test_adjusted_acceptance_refuses_unadjusted_for_family_over_one():
    families = [_family(0.01, attempt=1), _family(0.04, attempt=2)]
    verdicts = adjusted_acceptance(families, method="NONE", alpha=0.05)
    assert all(v.verdict == "REFUSED" for v in verdicts)
    assert all(v.accepted is None for v in verdicts)
    assert all(v.adjusted_pvalue is None for v in verdicts)
    assert all(
        v.reason_codes == ("UNADJUSTED_ACCEPTANCE_IS_FORBIDDEN_FOR_FAMILIES_OVER_ONE",)
        for v in verdicts
    )


def test_adjusted_acceptance_none_single_attempt_carries_honesty_flag():
    accepted = adjusted_acceptance([_family(0.03)], method="NONE", alpha=0.05)
    assert accepted[0].verdict == "ACCEPTED"
    assert accepted[0].accepted is True
    assert accepted[0].unadjusted is True  # explicit honesty flag
    rejected = adjusted_acceptance([_family(0.06)], method="NONE", alpha=0.05)
    assert rejected[0].verdict == "REJECTED"
    assert rejected[0].accepted is False
    assert rejected[0].unadjusted is True  # flag marks the METHOD, not the outcome


def test_adjusted_acceptance_refuses_alpha_out_of_range():
    families = [_family(0.01)]
    for bad_alpha in (0.0, 1.0, -0.5, 1.5, math.nan):
        with pytest.raises(ValueError, match="alpha_out_of_range"):
            adjusted_acceptance(families, method="BONFERRONI", alpha=bad_alpha)


def test_adjusted_acceptance_groups_families_separately():
    # F1 m=2: 0.2*2=0.4 (rejected), 0.3*2=0.6 (rejected) at alpha=0.05.
    # F2 m=2: 0.01*2=0.02 (accepted), 0.02*2=0.04 (accepted).
    families = [
        _family(0.2, family_id="F1", attempt=1),
        _family(0.3, family_id="F1", attempt=2),
        _family(0.01, family_id="F2", attempt=1),
        _family(0.02, family_id="F2", attempt=2),
    ]
    verdicts = adjusted_acceptance(families, method="BONFERRONI", alpha=0.05)
    assert len(verdicts) == 4
    f1 = [v for v in verdicts if v.family_id == "F1"]
    f2 = [v for v in verdicts if v.family_id == "F2"]
    assert [v.adjusted_pvalue for v in f1] == [0.4, 0.6]
    assert [v.verdict for v in f1] == ["REJECTED", "REJECTED"]
    assert [v.adjusted_pvalue for v in f2] == [0.02, 0.04]
    assert [v.verdict for v in f2] == ["ACCEPTED", "ACCEPTED"]


# ---------------------------------------------------------------------------
# FP / FN confusion analysis (hand-counted)
# ---------------------------------------------------------------------------


def _pair(signal: bool, matured: bool) -> OutcomePair:
    return OutcomePair(signal_positive=signal, matured_positive=matured)


def test_confusion_counts_hand_counted():
    outcomes = [
        _pair(True, True),   # TP
        _pair(True, False),  # FP
        _pair(False, True),  # FN
        _pair(False, False), # TN
        _pair(True, True),   # TP
        _pair(False, False), # TN
    ]
    counts = confusion_counts(outcomes)
    assert (counts.true_positive, counts.false_positive) == (2, 1)
    assert (counts.false_negative, counts.true_negative) == (1, 2)
    assert counts.total == 6


def test_confusion_counts_empty_is_all_zero():
    counts = confusion_counts([])
    assert counts.model_dump() == {
        "true_positive": 0,
        "false_positive": 0,
        "false_negative": 0,
        "true_negative": 0,
        "total": 0,
    }


def test_precision_recall_fp_rate_hand_computed():
    counts = ConfusionCounts(
        true_positive=2, false_positive=1, false_negative=1, true_negative=2, total=6
    )
    rates = precision_recall_fp_rate(counts)
    assert rates.precision == 2 / 3  # 2 / (2 + 1), exact division
    assert rates.recall == 2 / 3     # 2 / (2 + 1)
    assert rates.false_positive_rate == 1 / 3  # 1 / (1 + 2)
    assert rates.undefined == ()


def test_precision_recall_fp_rate_never_fakes_zero_for_undefined():
    # No signal positives at all: precision undefined -> None + reason code,
    # never 0.0. recall undefined too (no matured positives); fp_rate = 0/3.
    counts = ConfusionCounts(true_positive=0, false_positive=0, false_negative=0, true_negative=3, total=3)
    rates = precision_recall_fp_rate(counts)
    assert rates.precision is None
    assert rates.recall is None
    assert rates.false_positive_rate == 0.0
    assert "PRECISION_UNDEFINED_NO_SIGNAL_POSITIVES" in rates.undefined
    assert "RECALL_UNDEFINED_NO_MATURED_POSITIVES" in rates.undefined

    # No signal negatives: fp_rate undefined -> None + reason code.
    perfect = ConfusionCounts(true_positive=2, false_positive=0, false_negative=0, true_negative=0, total=2)
    rates2 = precision_recall_fp_rate(perfect)
    assert rates2.precision == 1.0
    assert rates2.recall == 1.0
    assert rates2.false_positive_rate is None
    assert "FALSE_POSITIVE_RATE_UNDEFINED_NO_SIGNAL_NEGATIVES" in rates2.undefined


def test_format_rate_is_the_only_rounding_point():
    assert format_rate(2 / 3, 4) == 0.6667
    assert format_rate(0.12345, 2) == 0.12
    assert format_rate(None, 3) is None  # undefined stays undefined
    with pytest.raises(ValueError, match="digits_must_be_non_negative_int"):
        format_rate(0.5, -1)
    with pytest.raises(ValueError, match="digits_must_be_non_negative_int"):
        format_rate(0.5, True)  # booleans are not digit counts
