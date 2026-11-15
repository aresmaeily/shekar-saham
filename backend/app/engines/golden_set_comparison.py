"""Golden Set symbol-set comparison metrics (overlap-only).

Recovered from the 2026-11-13 research documentation set
(``TABLOKHANI_GOLDEN_SET_COMPARISON_PROTOCOL.md``, verified 2026-11-15) and the
owner-approved continuation spec §8/§12.12. Deliberately NARROW:

* symbol-SET overlap only (precision/recall/FP/FN/coverage/F1/Jaccard);
* every numeric output carries ``OVERLAP_ONLY_NO_SUPERIORITY_CLAIM``;
* any precondition failure emits ``empty_metrics()`` (``status: NOT_MEASURED``)
  instead of numbers — a degraded number is never fabricated;
* a LARGER candidate set is never read as superiority (pinned by test:
  candidate ⊇ reference ⇒ recall 1.0 with precision 1/3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

INTERPRETATION_LABEL = "OVERLAP_ONLY_NO_SUPERIORITY_CLAIM"
NOT_MEASURED = "NOT_MEASURED"

# Recovered protocol §2 (P1..P6): preconditions that must hold for ANY
# reference comparison. A caller that cannot assert all six must use
# empty_metrics() — never partial numbers.
PRECONDITIONS = (
    "P1_universe_aligned",
    "P2_observation_time_aligned",
    "P3_sources_documented",
    "P4_units_normalized",
    "P5_exclusions_accounted",
    "P6_no_superiority_language",
)


def _norm(ids: list[str] | None) -> list[str]:
    """Normalize ids: trim + casefold for Latin; Persian symbols unaffected."""
    out: list[str] = []
    for s in ids or []:
        if not isinstance(s, str):
            continue
        t = s.strip()
        if t:
            out.append(t.casefold())
    return out


@dataclass(frozen=True)
class ComparisonPreconditions:
    """Caller-asserted protocol preconditions (all must be True)."""

    universe_aligned: bool = False
    observation_time_aligned: bool = False
    sources_documented: bool = False
    units_normalized: bool = False
    exclusions_accounted: bool = False

    def failures(self) -> tuple[str, ...]:
        failed = []
        if not self.universe_aligned:
            failed.append("P1_universe_aligned")
        if not self.observation_time_aligned:
            failed.append("P2_observation_time_aligned")
        if not self.sources_documented:
            failed.append("P3_sources_documented")
        if not self.units_normalized:
            failed.append("P4_units_normalized")
        if not self.exclusions_accounted:
            failed.append("P5_exclusions_accounted")
        return tuple(failed)


def empty_metrics(reason: str) -> dict[str, Any]:
    """Honest placeholder when any comparison precondition fails."""
    return {
        "status": NOT_MEASURED,
        "reason": str(reason),
        "metrics": None,
        "interpretation": NOT_MEASURED,
    }


def compare_symbol_sets(
    reference: list[str] | None,
    candidate: list[str] | None,
    *,
    preconditions: ComparisonPreconditions | None = None,
) -> dict[str, Any]:
    """Measure overlap of two symbol sets (overlap-only, no superiority).

    Metric definitions (recovered protocol §4, pinned by tests):
    tp = |ref ∩ cand|; fp = |cand \\ ref|; fn = |ref \\ cand|;
    precision = tp/(tp+fp) (None if cand empty); recall = tp/(tp+fn) (None if
    ref empty); coverage = tp/|ref| (None if ref empty); F1 harmonic mean of
    precision/recall (None if either is None/0); Jaccard = tp/|union|
    (None if both empty).
    """
    failed = preconditions.failures() if preconditions else tuple(PRECONDITIONS[:5])
    if failed:
        return empty_metrics("precondition_failed: " + ",".join(failed))

    ref = set(_norm(reference))
    cand = set(_norm(candidate))
    if not ref and not cand:
        return empty_metrics("both_sets_empty")

    tp_set = ref & cand
    fp_set = cand - ref
    fn_set = ref - cand
    tp, fp, fn = len(tp_set), len(fp_set), len(fn_set)

    precision = (tp / (tp + fp)) if (tp + fp) else None
    recall = (tp / (tp + fn)) if (tp + fn) else None
    coverage = (tp / len(ref)) if ref else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    union = ref | cand
    jaccard = (tp / len(union)) if union else None

    return {
        "status": "MEASURED",
        "metrics": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "coverage": coverage,
            "f1": f1,
            "jaccard": jaccard,
            "reference_size": len(ref),
            "candidate_size": len(cand),
        },
        "matched": sorted(tp_set),
        "reference_only": sorted(fn_set),
        "candidate_only": sorted(fp_set),
        "interpretation": INTERPRETATION_LABEL,
    }
