"""Tests for app.domain.survivorship_guard (universe-completeness guard).

All scenarios are hand-constructed member sets with explicit listing /
delisting timestamps; boundary semantics (exists iff listed <= as_of;
delisted-before/at iff delisted <= as_of) are pinned by dedicated tests.
"""

import pytest
from pydantic import ValidationError

from app.domain.survivorship_guard import (
    SurvivorshipGuardError,
    UniverseMember,
    UniverseSnapshot,
    survivorship_check,
)


def _member(
    symbol_id: str,
    listed_from_ts: float,
    delisted_at_ts: float | None = None,
    known_from_start: bool = False,
) -> UniverseMember:
    return UniverseMember(
        symbol_id=symbol_id,
        listed_from_ts=listed_from_ts,
        delisted_at_ts=delisted_at_ts,
        known_from_start=known_from_start,
    )


def _snapshot(as_of_ts: float, members: list[UniverseMember]) -> UniverseSnapshot:
    return UniverseSnapshot(as_of_ts=as_of_ts, members=tuple(members))


# A small hand-built registry: ALPHA and GAMMA alive at t=100, BETA delisted
# at t=50, DELTA lists at t=150 (not yet existing at t=100).
ALPHA = _member("ALPHA", 0.0)
BETA = _member("BETA", 0.0, delisted_at_ts=50.0)
GAMMA = _member("GAMMA", 10.0)
DELTA = _member("DELTA", 150.0)
REGISTRY = [ALPHA, BETA, GAMMA, DELTA]


def test_ok_when_complete_and_delisted_member_is_included():
    snapshot = _snapshot(100.0, [ALPHA, BETA, GAMMA])
    verdict = survivorship_check(snapshot, 100.0, REGISTRY)
    assert verdict.verdict == "OK"
    assert verdict.reason_codes == ("UNIVERSE_COMPLETE_AT_EVALUATION_AS_OF",)
    assert verdict.excluded_delisted_symbols == ()
    assert verdict.anachronistic_symbols == ()
    assert verdict.missing_symbols == ()
    assert (verdict.universe_size, verdict.snapshot_size) == (4, 3)


def test_survivorship_bias_risk_when_delisted_member_excluded():
    # The evaluation universe silently drops BETA, which existed and had
    # already delisted at t=50 <= 100 — the classic survivorship filter.
    snapshot = _snapshot(100.0, [ALPHA, GAMMA])
    verdict = survivorship_check(snapshot, 100.0, REGISTRY)
    assert verdict.verdict == "SURVIVORSHIP_BIAS_RISK"
    assert verdict.excluded_delisted_symbols == ("BETA",)
    assert "SURVIVORSHIP_EXCLUDED_DELISTED_MEMBERS" in verdict.reason_codes


def test_bias_boundary_delisted_exactly_at_evaluation_as_of():
    # BETA delisted exactly AT t=100 counts as delisted-before/at (<=).
    beta_at_100 = _member("BETA", 0.0, delisted_at_ts=100.0)
    registry = [ALPHA, beta_at_100]
    verdict = survivorship_check(_snapshot(100.0, [ALPHA]), 100.0, registry)
    assert verdict.verdict == "SURVIVORSHIP_BIAS_RISK"


def test_anachronistic_member_listed_after_evaluation_as_of():
    # DELTA lists at t=150 but the evaluation at t=100 already includes it.
    snapshot = _snapshot(100.0, [ALPHA, BETA, GAMMA, DELTA])
    verdict = survivorship_check(snapshot, 100.0, REGISTRY)
    assert verdict.verdict == "ANACHRONISTIC_MEMBER"
    assert verdict.anachronistic_symbols == ("DELTA",)
    assert "MEMBER_LISTED_AFTER_EVALUATION_AS_OF" in verdict.reason_codes


def test_snapshot_as_of_after_evaluation_as_of_is_anachronistic():
    # The universe claims knowledge from t=120 for an evaluation at t=100.
    snapshot = _snapshot(120.0, [ALPHA, BETA, GAMMA])
    verdict = survivorship_check(snapshot, 100.0, REGISTRY)
    assert verdict.verdict == "ANACHRONISTIC_MEMBER"
    assert "SNAPSHOT_AS_OF_AFTER_EVALUATION_AS_OF" in verdict.reason_codes
    assert verdict.anachronistic_symbols == ()  # no member itself is anachronistic


def test_incomplete_universe_when_alive_member_missing():
    snapshot = _snapshot(100.0, [ALPHA, BETA])  # GAMMA existed and was alive
    verdict = survivorship_check(snapshot, 100.0, REGISTRY)
    assert verdict.verdict == "INCOMPLETE_UNIVERSE"
    assert verdict.missing_symbols == ("GAMMA",)
    assert "EXPECTED_MEMBERS_MISSING" in verdict.reason_codes


def test_incomplete_boundary_member_listed_exactly_at_evaluation_as_of():
    # EPS lists exactly AT t=100 -> it existed (listed <= as_of); missing
    # from the snapshot it makes the universe incomplete.
    eps = _member("EPS", 100.0)
    verdict = survivorship_check(_snapshot(100.0, [ALPHA]), 100.0, [ALPHA, eps])
    assert verdict.verdict == "INCOMPLETE_UNIVERSE"
    assert verdict.missing_symbols == ("EPS",)


def test_expected_member_listed_after_as_of_missing_is_not_reported():
    # DELTA lists at t=150: at an evaluation of t=100 it is correctly
    # absent — neither incomplete nor anachronistic.
    verdict = survivorship_check(_snapshot(100.0, [ALPHA]), 100.0, [ALPHA, DELTA])
    assert verdict.verdict == "OK"


def test_verdict_precedence_bias_over_anachronistic_over_incomplete():
    # All three findings at once: BETA excluded (bias), DELTA anachronistic,
    # GAMMA missing -> headline is SURVIVORSHIP_BIAS_RISK, all findings
    # remain visible.
    snapshot = _snapshot(100.0, [ALPHA, DELTA])
    verdict = survivorship_check(snapshot, 100.0, REGISTRY)
    assert verdict.verdict == "SURVIVORSHIP_BIAS_RISK"
    assert verdict.excluded_delisted_symbols == ("BETA",)
    assert verdict.anachronistic_symbols == ("DELTA",)
    assert verdict.missing_symbols == ("GAMMA",)
    assert verdict.reason_codes == (
        "SURVIVORSHIP_EXCLUDED_DELISTED_MEMBERS",
        "MEMBER_LISTED_AFTER_EVALUATION_AS_OF",
        "EXPECTED_MEMBERS_MISSING",
    )

    # Remove the bias finding (drop BETA from the registry): headline
    # becomes ANACHRONISTIC_MEMBER.
    registry_no_beta = [ALPHA, GAMMA, DELTA]
    verdict2 = survivorship_check(snapshot, 100.0, registry_no_beta)
    assert verdict2.verdict == "ANACHRONISTIC_MEMBER"
    assert verdict2.missing_symbols == ("GAMMA",)

    # Remove the anachronism too: headline becomes INCOMPLETE_UNIVERSE.
    verdict3 = survivorship_check(_snapshot(100.0, [ALPHA]), 100.0, [ALPHA, GAMMA])
    assert verdict3.verdict == "INCOMPLETE_UNIVERSE"


def test_snapshot_member_not_in_expected_universe_refuses_fail_closed():
    # The registry is provably incomplete (it does not even know OMEGA), so
    # NO verdict can be certified — the guard raises instead of classifying.
    omega = _member("OMEGA", 0.0)
    with pytest.raises(SurvivorshipGuardError, match="SNAPSHOT_MEMBER_NOT_IN_EXPECTED_UNIVERSE"):
        survivorship_check(_snapshot(100.0, [ALPHA, omega]), 100.0, [ALPHA])


def test_conflicting_member_record_refuses_fail_closed():
    # Snapshot and registry disagree on ALPHA's lifecycle: refuse.
    alpha_conflict = _member("ALPHA", 5.0)
    with pytest.raises(SurvivorshipGuardError, match="CONFLICTING_MEMBER_RECORD"):
        survivorship_check(_snapshot(100.0, [alpha_conflict]), 100.0, [ALPHA])


def test_duplicate_expected_symbols_refuse():
    with pytest.raises(SurvivorshipGuardError, match="DUPLICATE_EXPECTED_SYMBOL"):
        survivorship_check(_snapshot(100.0, [ALPHA]), 100.0, [ALPHA, ALPHA])


def test_duplicate_snapshot_symbol_ids_refused_at_model_level():
    with pytest.raises(ValidationError, match="duplicate_symbol_ids"):
        _snapshot(100.0, [ALPHA, ALPHA])


def test_universe_member_lifecycle_validation():
    with pytest.raises(ValidationError, match="delisted_before_listing"):
        _member("BAD", 100.0, delisted_at_ts=50.0)


def test_verdict_record_is_frozen():
    verdict = survivorship_check(_snapshot(100.0, [ALPHA]), 100.0, [ALPHA])
    with pytest.raises(ValidationError):
        verdict.verdict = "SURVIVORSHIP_BIAS_RISK"  # type: ignore[misc]


def test_empty_registry_and_empty_snapshot_is_trivially_ok():
    verdict = survivorship_check(_snapshot(100.0, []), 100.0, [])
    assert verdict.verdict == "OK"
    assert (verdict.universe_size, verdict.snapshot_size) == (0, 0)
