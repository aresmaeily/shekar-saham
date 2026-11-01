"""Versioned Golden Set contracts (P3, purely additive).

Corpus loci (2026-10-02 amendment corpus):
- 02_EXECUTION_ROADMAP line 189 ("Reference-system strategy"): "'Beyond
  reference sites' may be claimed only after a versioned Golden Set and
  repeatable benchmark show measurable improvement; no unsupported
  superiority claims." — this module delivers the VERSIONING and
  repeatable-benchmark HALF of that requirement (deterministic pinned
  cases + tamper evidence); it makes NO capability claim of any kind and
  asserts NO superiority over any external system.
- 06 Product Capability Charter line 104 ("Market interpretation"): "A
  versioned Golden Set demonstrates baseline and extended capability
  metrics, false positives/negatives, ...".
- scripts/g2_acceptance_battery.py CORPUS_REFERENCE_DIGESTS: the
  pinned-reference-digest precedent mirrored by the tamper-evidence
  checks here (file digest pinned in the test, internal digest recomputed
  from content).

Determinism contract
--------------------
- `canonical_json`: sorted keys, ``,``/``:`` separators, ASCII-escaped,
  floats via Python's repr (shortest round-trip representation). The same
  object always yields the same bytes.
- Digests: SHA-256 over the UTF-8 bytes of `canonical_json`.
  * bars_digest   — over the case's input bars (paths mapping).
  * cases_digest  — over the canonical dump of the case records ONLY
    (never over `created_at_utc` or any wall-clock artifact; timestamps
    appear solely as explicit bar ``ts`` fields).
- Float policy: expected metrics are the EXACT IEEE-754 doubles returned
  by the deterministic engine (which itself rounds to declared digit
  counts at its own presentation boundary). Comparison is EXACT ``==``
  — never approx — because the engine is pure-Python deterministic for
  identical inputs; this equality-at-zero-tolerance policy is verified by
  double-run in the test suite. JSON's repr round-trip preserves the
  exact double, so pinning in JSON is lossless.

No I/O, no network, no wall-clock: `created_at_utc` is an explicit
constructor parameter (parsed from the fixture payload, never read from
a clock).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Mapping
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import ensure_utc

GoldenCaseKind = Literal["BACKTEST", "WALK_FORWARD", "FORWARD_TEST"]


class GoldenSetIntegrityError(ValueError):
    """Deterministic refusal carrying a machine-readable reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}:{detail}" if detail else reason
        super().__init__(message)


def canonical_json(payload: Any) -> str:
    """Canonical JSON serialization (sorted keys, compact, ASCII).

    Determinism notes: ``sort_keys=True`` makes key order irrelevant;
    ``separators=(",", ":")`` removes whitespace variance; ``ensure_ascii``
    pins the escaping; floats serialize via ``repr`` (shortest round-trip),
    so ``json.loads(canonical_json(x))`` preserves exact doubles. Objects
    containing datetimes or other non-JSON types raise TypeError — the
    golden-set policy keeps timestamps OUT of digested payloads (only
    explicit numeric ``ts`` fields inside bars are allowed).
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_of(payload: Any) -> str:
    """SHA-256 hex digest over the canonical JSON of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class GoldenWindowExpectation(BaseModel):
    """Pinned per-window expectation for a WALK_FORWARD golden case."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    metrics: dict[str, float] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)


class GoldenSetCase(BaseModel):
    """One pinned golden case.

    ``bars_digest`` binds the case to its exact input bars (the bars
    themselves live in the fixture payload and are verified at parse
    time). ``expected_metrics`` pins engine floats exactly (see the
    module float policy); ``expected_counts`` pins exact integers;
    ``expected_flags`` pins exact string facts (e.g. report mode);
    ``expected_windows`` pins per-window expectations for WFO cases.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    case_id: str = Field(min_length=1, max_length=128)
    kind: GoldenCaseKind
    description: str = ""
    bars_digest: str = Field(min_length=64, max_length=64)
    expected_metrics: dict[str, float] = Field(default_factory=dict)
    expected_counts: dict[str, int] = Field(default_factory=dict)
    expected_flags: dict[str, str] = Field(default_factory=dict)
    expected_windows: tuple[GoldenWindowExpectation, ...] = ()

    @field_validator("expected_metrics")
    @classmethod
    def _finite_metrics(cls, v: dict[str, float]) -> dict[str, float]:
        for key, value in v.items():
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"expected_metric_not_finite:{key}")
        return v

    @field_validator("bars_digest")
    @classmethod
    def _hex64(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("bars_digest_must_be_64_hex")
        return v.lower()

    def canonical_payload(self) -> dict[str, Any]:
        """The exact dict whose canonical JSON the version digest covers."""
        return {
            "bars_digest": self.bars_digest,
            "case_id": self.case_id,
            "description": self.description,
            "expected_counts": self.expected_counts,
            "expected_flags": self.expected_flags,
            "expected_metrics": self.expected_metrics,
            "expected_windows": [w.model_dump() for w in self.expected_windows],
            "kind": self.kind,
        }


class GoldenSetVersion(BaseModel):
    """A versioned, content-addressed set of golden cases.

    ``version_id`` follows ``GS-YYYY-MM-DD``. ``created_at_utc`` is an
    EXPLICIT parameter (from the fixture or the caller) — the digest NEVER
    covers it, so the same case content yields the same digest regardless
    of when the version record was minted.
    """

    model_config = ConfigDict(frozen=True)

    version_id: str = Field(pattern=r"^GS-\d{4}-\d{2}-\d{2}$")
    created_at_utc: datetime
    cases: tuple[GoldenSetCase, ...] = Field(min_length=1)
    notes: str = ""

    @field_validator("created_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _distinct_case_ids(self) -> "GoldenSetVersion":
        case_ids = [c.case_id for c in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("duplicate_case_ids")
        return self

    @property
    def cases_digest(self) -> str:
        """SHA-256 over the canonical JSON of the case records (only)."""
        return digest_of([case.canonical_payload() for case in self.cases])


class GoldenCaseResult(BaseModel):
    """Outcome of comparing a recomputation against pinned expectations.

    Failures are enumerated with machine-readable reason codes naming the
    exact key; comparison is EXACT equality (never approximate).
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    passed: bool
    failure_reasons: tuple[str, ...] = ()


def _compare_mapping(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any] | None,
    kind_label: str,
    reasons: list[str],
) -> None:
    actual_map = {} if actual is None else dict(actual)
    for key, wanted in expected.items():
        if key not in actual_map:
            reasons.append(f"MISSING_{kind_label}:{key}")
        elif actual_map[key] != wanted:  # exact equality; no tolerance, no rounding
            reasons.append(f"{kind_label}_MISMATCH:{key}")
    for key in actual_map:
        if key not in expected:
            reasons.append(f"EXTRA_{kind_label}:{key}")


def verify_case(
    case: GoldenSetCase,
    actual_metrics: Mapping[str, Any] | None = None,
    actual_counts: Mapping[str, Any] | None = None,
    actual_flags: Mapping[str, Any] | None = None,
) -> GoldenCaseResult:
    """Compare recomputed metrics/counts/flags against the pinned case.

    Exact equality on every pinned key; missing and extra keys are
    reported (silently ignoring drift would weaken tamper evidence).
    """
    reasons: list[str] = []
    _compare_mapping(case.expected_metrics, actual_metrics, "METRIC", reasons)
    _compare_mapping(case.expected_counts, actual_counts, "COUNT", reasons)
    _compare_mapping(case.expected_flags, actual_flags, "FLAG", reasons)
    return GoldenCaseResult(
        case_id=case.case_id,
        passed=not reasons,
        failure_reasons=tuple(reasons),
    )


def parse_golden_set_version(payload: Mapping[str, Any]) -> GoldenSetVersion:
    """Parse and integrity-check a golden-set fixture payload.

    Checks (each failure raises `GoldenSetIntegrityError`):
      - required top-level keys: ``version_id``, ``created_at_utc``,
        ``cases``, ``version_sha256``;
      - per-case required keys: ``case_id``, ``kind``, ``bars``,
        ``bars_sha256``, ``expected``;
      - ``bars_sha256`` MUST equal the recomputed digest of the case's
        bars (CASE_BARS_DIGEST_MISMATCH otherwise — tampered inputs are
        refused, never silently accepted);
      - ``version_sha256`` MUST equal the recomputed cases digest
        (VERSION_DIGEST_MISMATCH otherwise).
    """
    if not isinstance(payload, Mapping):
        raise GoldenSetIntegrityError("PAYLOAD_NOT_MAPPING", repr(type(payload)))
    for key in ("version_id", "created_at_utc", "cases", "version_sha256"):
        if key not in payload:
            raise GoldenSetIntegrityError("PAYLOAD_KEY_MISSING", key)
    raw_cases = payload["cases"]
    if not isinstance(raw_cases, list) or len(raw_cases) == 0:
        raise GoldenSetIntegrityError("CASES_NOT_NONEMPTY_LIST")

    parsed_cases: list[GoldenSetCase] = []
    for index, case_payload in enumerate(raw_cases):
        if not isinstance(case_payload, Mapping):
            raise GoldenSetIntegrityError("CASE_PAYLOAD_NOT_MAPPING", f"index={index}")
        for key in ("case_id", "kind", "bars", "bars_sha256", "expected"):
            if key not in case_payload:
                raise GoldenSetIntegrityError("CASE_PAYLOAD_KEY_MISSING", f"index={index} key={key}")
        case_id = case_payload["case_id"]
        actual_bars_digest = digest_of(case_payload["bars"])
        if actual_bars_digest != case_payload["bars_sha256"]:
            raise GoldenSetIntegrityError(
                "CASE_BARS_DIGEST_MISMATCH",
                f"case_id={case_id} expected={case_payload['bars_sha256']} actual={actual_bars_digest}",
            )
        expected = case_payload["expected"]
        if not isinstance(expected, Mapping):
            raise GoldenSetIntegrityError("EXPECTED_NOT_MAPPING", f"case_id={case_id}")
        windows = tuple(
            GoldenWindowExpectation(**w) for w in expected.get("windows", ())
        )
        parsed_cases.append(
            GoldenSetCase(
                case_id=case_id,
                kind=case_payload["kind"],
                description=case_payload.get("description", ""),
                bars_digest=case_payload["bars_sha256"],
                expected_metrics=dict(expected.get("metrics", {})),
                expected_counts=dict(expected.get("counts", {})),
                expected_flags=dict(expected.get("flags", {})),
                expected_windows=windows,
            )
        )

    version = GoldenSetVersion(
        version_id=payload["version_id"],
        created_at_utc=payload["created_at_utc"],
        cases=tuple(parsed_cases),
        notes=payload.get("notes", ""),
    )
    embedded_digest = payload["version_sha256"]
    if version.cases_digest != embedded_digest:
        raise GoldenSetIntegrityError(
            "VERSION_DIGEST_MISMATCH",
            f"expected={embedded_digest} actual={version.cases_digest}",
        )
    return version
