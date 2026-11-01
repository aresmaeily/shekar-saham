"""Universe-completeness / survivorship guard (P2+P3, purely additive).

Corpus loci (2026-10-02 amendment corpus):
- 02_EXECUTION_ROADMAP lines 24-26 ("P2 --- Deterministic Measurement &
  Evidence Core"): "PIT, corporate actions, survivorship, look-ahead
  protection, ..."
- 02_EXECUTION_ROADMAP line 145 ("P3 --- Evaluation and research
  integrity"): "... survivorship/corporate-action handling ...".
- 06 Product Capability Charter, "Research and feedback": reproducible
  runs with point-in-time correctness.

Scope: point-in-time universe completeness classification. The evaluation
universe (the `UniverseSnapshot` a backtest/evaluation actually used) is
checked against an EXPLICIT expected universe (the full member registry
supplied by the caller) as of an explicit evaluation timestamp:

- OK: every member that existed at the evaluation timestamp is present,
  no member is anachronistic.
- SURVIVORSHIP_BIAS_RISK: the evaluation universe EXCLUDES an expected
  member that had existed and had ALREADY DELISTED at/before the
  evaluation timestamp — the classic silent survivorship filter.
- ANACHRONISTIC_MEMBER: the evaluation universe includes a member that
  was not yet listed at the evaluation timestamp (or the snapshot claims
  knowledge from after the evaluation timestamp).
- INCOMPLETE_UNIVERSE: an expected member that existed and was still
  listed at the evaluation timestamp is missing.

Fail-closed refusals (raised, not classified): a snapshot member absent
from the expected registry (the registry is then provably incomplete, so
no verdict can be certified) or a member record conflicting with the
registry (same symbol, different lifecycle).

Closed verdict vocabulary, machine-readable reason codes, no I/O, no
network, no wall-clock: all timestamps are explicit parameters. Boundary
semantics (documented, tested): a member exists at the evaluation
timestamp iff ``listed_from_ts <= evaluation_as_of_ts``; it is
delisted-before/at iff ``delisted_at_ts <= evaluation_as_of_ts``.
"""

from __future__ import annotations

import math
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SurvivorshipVerdictKind = Literal[
    "OK",
    "SURVIVORSHIP_BIAS_RISK",
    "ANACHRONISTIC_MEMBER",
    "INCOMPLETE_UNIVERSE",
]


class SurvivorshipGuardError(ValueError):
    """Deterministic fail-closed refusal with a machine-readable reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}:{detail}" if detail else reason
        super().__init__(message)


class UniverseMember(BaseModel):
    """One point-in-time universe member with its explicit lifecycle.

    ``delisted_at_ts is None`` means still listed as far as the registry
    knows (honest unknown, never invented). ``known_from_start`` marks
    members the registry has covered since the registry's own start —
    informational provenance, carried verbatim.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    symbol_id: str = Field(min_length=1, max_length=64)
    listed_from_ts: float
    delisted_at_ts: float | None = None
    known_from_start: bool = False

    @model_validator(mode="after")
    def _lifecycle_order(self) -> "UniverseMember":
        if self.delisted_at_ts is not None and self.delisted_at_ts < self.listed_from_ts:
            raise ValueError("delisted_before_listing")
        return self


class UniverseSnapshot(BaseModel):
    """The evaluation universe actually used, as of an explicit timestamp."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    as_of_ts: float
    members: tuple[UniverseMember, ...]

    @field_validator("members")
    @classmethod
    def _distinct_symbols(cls, v: tuple[UniverseMember, ...]) -> tuple[UniverseMember, ...]:
        symbol_ids = [m.symbol_id for m in v]
        if len(set(symbol_ids)) != len(symbol_ids):
            raise ValueError("duplicate_symbol_ids")
        return v


class SurvivorshipVerdict(BaseModel):
    """Frozen classification with per-category symbol lists and codes.

    The ``verdict`` is the single headline class (closed vocabulary,
    deterministic precedence when several categories fire:
    SURVIVORSHIP_BIAS_RISK > ANACHRONISTIC_MEMBER > INCOMPLETE_UNIVERSE >
    OK); the per-category symbol lists keep ALL findings visible so the
    precedence never hides information.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    verdict: SurvivorshipVerdictKind
    evaluation_as_of_ts: float
    reason_codes: tuple[str, ...] = ()
    excluded_delisted_symbols: tuple[str, ...] = ()
    anachronistic_symbols: tuple[str, ...] = ()
    missing_symbols: tuple[str, ...] = ()
    universe_size: int = Field(ge=0)
    snapshot_size: int = Field(ge=0)


def _finite_ts(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SurvivorshipGuardError("TS_NOT_NUMERIC", f"field={name} value={value!r}")
    v = float(value)
    if not math.isfinite(v):
        raise SurvivorshipGuardError("TS_NOT_FINITE", f"field={name}")
    return v


def survivorship_check(
    snapshot: UniverseSnapshot,
    evaluation_as_of_ts: float,
    expected_members: Sequence[UniverseMember],
) -> SurvivorshipVerdict:
    """Classify the evaluation universe for survivorship/anachrony/completeness.

    Parameters
    ----------
    snapshot:
        The universe the evaluation actually used.
    evaluation_as_of_ts:
        The point in time the evaluation claims to represent (explicit).
    expected_members:
        The full member registry the evaluation universe is accountable
        to. Duplicates are refused.

    Returns
    -------
    SurvivorshipVerdict
        Headline class per the module docstring plus complete per-symbol
        findings.
    """
    as_of = _finite_ts(evaluation_as_of_ts, "evaluation_as_of_ts")

    expected_by_symbol: dict[str, UniverseMember] = {}
    for member in expected_members:
        if member.symbol_id in expected_by_symbol:
            raise SurvivorshipGuardError(
                "DUPLICATE_EXPECTED_SYMBOL", f"symbol={member.symbol_id}"
            )
        expected_by_symbol[member.symbol_id] = member

    for member in snapshot.members:
        expected = expected_by_symbol.get(member.symbol_id)
        if expected is None:
            raise SurvivorshipGuardError(
                "SNAPSHOT_MEMBER_NOT_IN_EXPECTED_UNIVERSE", f"symbol={member.symbol_id}"
            )
        if (
            member.listed_from_ts != expected.listed_from_ts
            or member.delisted_at_ts != expected.delisted_at_ts
        ):
            raise SurvivorshipGuardError(
                "CONFLICTING_MEMBER_RECORD",
                f"symbol={member.symbol_id} "
                f"snapshot=({member.listed_from_ts!r},{member.delisted_at_ts!r}) "
                f"registry=({expected.listed_from_ts!r},{expected.delisted_at_ts!r})",
            )

    excluded_delisted: list[str] = []
    anachronistic: list[str] = []
    missing: list[str] = []
    snapshot_symbols = {m.symbol_id for m in snapshot.members}

    for member in snapshot.members:
        if member.listed_from_ts > as_of:
            anachronistic.append(member.symbol_id)

    for symbol_id, member in expected_by_symbol.items():
        if symbol_id in snapshot_symbols:
            continue
        if member.listed_from_ts > as_of:
            continue  # not yet existing at the evaluation point: not missing
        if member.delisted_at_ts is not None and member.delisted_at_ts <= as_of:
            excluded_delisted.append(symbol_id)
        else:
            missing.append(symbol_id)

    reason_codes: list[str] = []
    snapshot_as_of_after_evaluation = snapshot.as_of_ts > as_of
    if snapshot_as_of_after_evaluation:
        # The universe claims knowledge from AFTER the evaluation point.
        reason_codes.append("SNAPSHOT_AS_OF_AFTER_EVALUATION_AS_OF")
    if excluded_delisted:
        reason_codes.append("SURVIVORSHIP_EXCLUDED_DELISTED_MEMBERS")
    if anachronistic:
        reason_codes.append("MEMBER_LISTED_AFTER_EVALUATION_AS_OF")
    if missing:
        reason_codes.append("EXPECTED_MEMBERS_MISSING")

    excluded_delisted.sort()
    anachronistic.sort()
    missing.sort()

    if excluded_delisted:
        verdict_kind: SurvivorshipVerdictKind = "SURVIVORSHIP_BIAS_RISK"
    elif anachronistic or snapshot_as_of_after_evaluation:
        verdict_kind = "ANACHRONISTIC_MEMBER"
    elif missing:
        verdict_kind = "INCOMPLETE_UNIVERSE"
    else:
        verdict_kind = "OK"
        reason_codes.append("UNIVERSE_COMPLETE_AT_EVALUATION_AS_OF")

    return SurvivorshipVerdict(
        verdict=verdict_kind,
        evaluation_as_of_ts=as_of,
        reason_codes=tuple(reason_codes),
        excluded_delisted_symbols=tuple(excluded_delisted),
        anachronistic_symbols=tuple(anachronistic),
        missing_symbols=tuple(missing),
        universe_size=len(expected_by_symbol),
        snapshot_size=len(snapshot.members),
    )
