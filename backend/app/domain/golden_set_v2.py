"""Golden Set v2 — versioned, reproducible benchmark extension (WAVE-AI WP-F).

Extends the shipped Golden Set v1 (BACKTEST/WALK_FORWARD/FORWARD_TEST cases
with pinned engine floats) to the capability surface the 06 charter and the
WAVE-AI-ACCEPTANCE directive §7 require:

- MARKET_INTERPRETATION  — AI-1 six-label classification over pinned symbol
  contexts (expected label + reason codes + exact confidence), with explicit
  FALSE-POSITIVE / FALSE-NEGATIVE accounting (label-strength rank order);
- SOURCE_CONFLICT        — G3 ``PRIMARY_OVER_SECONDARY_V1`` resolution over
  pinned evidence items (expected winner + audit row) AND the honest
  same-precedence refusal;
- FUNDAMENTAL_EXTRACTION — G2 section-map extraction over declared documents
  (missing-value refusal rows, unit/currency discipline, restatement
  linkage);
- REGIME_ROBUSTNESS      — declared regime windows over pinned bars with
  pinned per-slice metrics (caller-declared, never data-inferred);
- CALIBRATION            — pinned prediction/outcome pairs with pinned exact
  Brier/ECE.

Every case carries EXPLICIT EXPECTED OUTPUTS and EXPLICIT INVALIDATION
CONDITIONS (the conditions under which the case stops being authoritative —
engine version change, vocabulary change, threshold change). Baseline and
candidate results are REPORTED SEPARATELY and the report structure pins
``superiority_claimed=False`` — no superiority claim of any kind is made or
implied; the Golden Set demonstrates baseline and extended capability
metrics (06:104) without claiming to beat anything.

Determinism: identical structure to v1 — canonical JSON, SHA-256 digests,
exact float equality, no I/O, no clock (instants are explicit fixture
fields). Inputs are digest-bound: an input whose recomputed digest does not
match its pinned ``input_sha256`` is refused at parse (tamper evidence).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.golden_set import GoldenSetIntegrityError, canonical_json, digest_of

GoldenV2CaseKind = Literal[
    "MARKET_INTERPRETATION",
    "SOURCE_CONFLICT",
    "FUNDAMENTAL_EXTRACTION",
    "REGIME_ROBUSTNESS",
    "CALIBRATION",
]

#: Label-strength rank order for FP/FN accounting (higher = stronger action).
#: NO_ACTION and INSUFFICIENT_DATA are non-action ranks; BUY/SELL candidates
#: share the top rank (directional strength, not direction preference).
LABEL_STRENGTH_RANK: dict[str, int] = {
    "INSUFFICIENT_DATA": 0,
    "NO_ACTION": 0,
    "WATCH": 1,
    "HOLD": 2,
    "BUY_CANDIDATE": 3,
    "SELL_CANDIDATE": 3,
}


class GoldenV2Case(BaseModel):
    """One pinned v2 case: digest-bound input + expected output + invalidations."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1, max_length=128)
    kind: GoldenV2CaseKind
    description: str = ""
    input_sha256: str = Field(min_length=64, max_length=64)
    expected: dict[str, Any]
    #: Explicit conditions that INVALIDATE this case (machine-readable):
    #: when one fires, the case must be re-baselined, never silently reused.
    invalidations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _invalidations_nonempty(self) -> "GoldenV2Case":
        if any(not str(i).strip() for i in self.invalidations):
            raise ValueError("invalidation_condition_empty")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "expected": self.expected,
            "input_sha256": self.input_sha256,
            "invalidations": list(self.invalidations),
            "kind": self.kind,
        }


class GoldenV2Version(BaseModel):
    """A versioned, content-addressed v2 golden corpus."""

    model_config = ConfigDict(frozen=True)

    version_id: str = Field(pattern=r"^GS2-\d{4}-\d{2}-\d{2}$")
    created_at_utc: datetime
    cases: tuple[GoldenV2Case, ...] = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def _distinct_case_ids(self) -> "GoldenV2Version":
        ids = [c.case_id for c in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate_case_ids")
        return self

    @property
    def cases_digest(self) -> str:
        return digest_of([c.canonical_payload() for c in self.cases])


def parse_golden_set_v2_payload(payload: Mapping[str, Any]) -> GoldenV2Version:
    """Parse + integrity-check a v2 fixture payload.

    Refusals (``GoldenSetIntegrityError``):
    - missing top-level keys ``version_id`` / ``created_at_utc`` / ``cases``
      / ``version_sha256`` / ``inputs``;
    - per-case missing keys or non-matching ``input_sha256`` (the case's
      input payload, looked up by ``input_id`` from ``inputs``, must hash to
      exactly the pinned digest — tampered inputs refused);
    - non-matching ``version_sha256`` over the canonical case records.
    """
    if not isinstance(payload, Mapping):
        raise GoldenSetIntegrityError("PAYLOAD_NOT_MAPPING", repr(type(payload)))
    for key in ("version_id", "created_at_utc", "cases", "version_sha256", "inputs"):
        if key not in payload:
            raise GoldenSetIntegrityError("PAYLOAD_KEY_MISSING", key)
    inputs = payload["inputs"]
    if not isinstance(inputs, Mapping):
        raise GoldenSetIntegrityError("INPUTS_NOT_MAPPING", repr(type(inputs)))
    raw_cases = payload["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise GoldenSetIntegrityError("CASES_NOT_NONEMPTY_LIST")

    parsed: list[GoldenV2Case] = []
    for index, case_payload in enumerate(raw_cases):
        if not isinstance(case_payload, Mapping):
            raise GoldenSetIntegrityError("CASE_PAYLOAD_NOT_MAPPING", f"index={index}")
        for key in ("case_id", "kind", "input_id", "input_sha256", "expected", "invalidations"):
            if key not in case_payload:
                raise GoldenSetIntegrityError(
                    "CASE_PAYLOAD_KEY_MISSING", f"index={index} key={key}"
                )
        input_id = case_payload["input_id"]
        if input_id not in inputs:
            raise GoldenSetIntegrityError("INPUT_PAYLOAD_MISSING", f"case={case_payload['case_id']} input_id={input_id}")
        actual = digest_of(inputs[input_id])
        if actual != case_payload["input_sha256"]:
            raise GoldenSetIntegrityError(
                "CASE_INPUT_DIGEST_MISMATCH",
                f"case_id={case_payload['case_id']} expected={case_payload['input_sha256']} actual={actual}",
            )
        invalidations = tuple(case_payload["invalidations"])
        if not invalidations:
            raise GoldenSetIntegrityError("INVALIDATIONS_REQUIRED", f"case_id={case_payload['case_id']}")
        parsed.append(
            GoldenV2Case(
                case_id=case_payload["case_id"],
                kind=case_payload["kind"],
                description=case_payload.get("description", ""),
                input_sha256=case_payload["input_sha256"],
                expected=dict(case_payload["expected"]),
                invalidations=invalidations,
            )
        )

    version = GoldenV2Version(
        version_id=payload["version_id"],
        created_at_utc=payload["created_at_utc"],
        cases=tuple(parsed),
        notes=payload.get("notes", ""),
    )
    embedded = payload["version_sha256"]
    if version.cases_digest != embedded:
        raise GoldenSetIntegrityError(
            "VERSION_DIGEST_MISMATCH", f"expected={embedded} actual={version.cases_digest}"
        )
    return version


# ---------------------------------------------------------------------------
# Case results + FP/FN accounting
# ---------------------------------------------------------------------------


class GoldenV2CaseResult(BaseModel):
    """One case's comparison outcome (exact equality; failures enumerated)."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    kind: GoldenV2CaseKind
    passed: bool
    failure_reasons: tuple[str, ...] = ()
    false_positive: bool | None = None  # MARKET_INTERPRETATION only
    false_negative: bool | None = None


def _compare(expected: Mapping[str, Any], actual: Mapping[str, Any], label: str, reasons: list[str]) -> None:
    for key, wanted in expected.items():
        if key not in actual:
            reasons.append(f"MISSING_{label}:{key}")
        elif actual[key] != wanted:
            reasons.append(f"{label}_MISMATCH:{key}")
    for key in actual:
        if key not in expected:
            reasons.append(f"EXTRA_{label}:{key}")


def classify_interpretation_result(
    expected_label: str, actual_label: str
) -> tuple[bool | None, bool | None]:
    """FP/FN semantics for the six-label vocabulary.

    A case counts as FALSE POSITIVE when the engine emits a STRICTLY
    STRONGER action than pinned; FALSE NEGATIVE when strictly weaker;
    equal rank is the true/negative class (neither FP nor FN — both None).
    Unknown labels (vocabulary drift) are not classifiable — both None and
    the comparison itself fails on the label mismatch.
    """
    exp = LABEL_STRENGTH_RANK.get(expected_label)
    act = LABEL_STRENGTH_RANK.get(actual_label)
    if exp is None or act is None:
        return None, None
    if act > exp:
        return True, None  # false positive
    if act < exp:
        return None, True  # false negative
    return None, None


def build_v2_report(
    version: GoldenV2Version,
    results: tuple[GoldenV2CaseResult, ...],
    *,
    baseline_summary: Mapping[str, Any],
    candidate_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """The v2 report: baseline and candidate results SEPARATE, FP/FN counts,
    per-kind breakdown, and the structural no-superiority pin.

    ``baseline_summary`` / ``candidate_summary`` are caller-computed metric
    maps (the v1 corpus re-verification and the v2 corpus run respectively);
    the report NEVER compares them into a superiority claim — it only
    reports them side by side with ``superiority_claimed=False``.
    """
    fp = sum(1 for r in results if r.false_positive)
    fn = sum(1 for r in results if r.false_negative)
    per_kind: dict[str, dict[str, int]] = {}
    for r in results:
        bucket = per_kind.setdefault(
            r.kind, {"cases": 0, "passed": 0, "failed": 0, "false_positives": 0, "false_negatives": 0}
        )
        bucket["cases"] += 1
        bucket["passed" if r.passed else "failed"] += 1
        if r.false_positive:
            bucket["false_positives"] += 1
        if r.false_negative:
            bucket["false_negatives"] += 1
    return {
        "version_id": version.version_id,
        "cases_digest": version.cases_digest,
        "total_cases": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "false_positives_total": fp,
        "false_negatives_total": fn,
        "per_kind": per_kind,
        "baseline_results": dict(baseline_summary),
        "candidate_results": dict(candidate_summary),
        "superiority_claimed": False,
        "note": (
            "baseline and candidate results are reported SEPARATELY; no "
            "superiority claim is made or implied without repeatable "
            "evidence (06:104; WAVE-AI WP-F)"
        ),
    }


__all__ = [
    "GoldenV2Case",
    "GoldenV2CaseResult",
    "GoldenV2Version",
    "GoldenV2CaseKind",
    "LABEL_STRENGTH_RANK",
    "parse_golden_set_v2_payload",
    "classify_interpretation_result",
    "build_v2_report",
    "canonical_json",
    "digest_of",
]
