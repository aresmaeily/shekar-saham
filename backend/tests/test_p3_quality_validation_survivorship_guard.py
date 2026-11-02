"""T2 / CONSOL-NEXT Wave 1 — P3 independent validation of
app.domain.survivorship_guard (MA-1 WS-2).

ADDITIVE gap tests. Existing coverage (tests/test_survivorship_guard.py,
not duplicated): all four verdicts on a shared 4-member registry,
delisted-exactly-at-as_of boundary, listed-exactly-at-as_of boundary,
not-yet-listed member absent is OK, precedence chain, snapshot-member-
not-in-registry, listed_from conflict, duplicate expected symbols,
duplicate snapshot symbols, delisted-before-listing model refusal,
frozen verdict, empty registry/snapshot.

Gaps filled here: MINIMAL one/two-member universes proving each verdict
is reachable standalone; the delisted-AFTER-as_of exclusion boundary
(excluded member that was still listed at the evaluation point is
MISSING, not a survivorship finding); stale snapshot (as_of strictly
BEFORE evaluation as_of) is not flagged anachronistic — current
behavior pinned with an explicit comment; delisted-field record
conflict; evaluation_as_of_ts type/finite refusals.
"""

import math

import pytest

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
) -> UniverseMember:
    return UniverseMember(
        symbol_id=symbol_id, listed_from_ts=listed_from_ts, delisted_at_ts=delisted_at_ts
    )


def _snapshot(as_of_ts: float, members: list[UniverseMember]) -> UniverseSnapshot:
    return UniverseSnapshot(as_of_ts=as_of_ts, members=tuple(members))


# ---------------------------------------------------------------------------
# Minimal universes: each verdict reachable standalone
# ---------------------------------------------------------------------------


def test_p3_all_four_verdicts_reachable_with_minimal_universes():
    as_of = 100.0
    alive = _member("AAA", 0.0)

    # OK: single-member registry, single-member snapshot, member present.
    ok = survivorship_check(_snapshot(as_of, [alive]), as_of, [alive])
    assert ok.verdict == "OK"
    assert ok.reason_codes == ("UNIVERSE_COMPLETE_AT_EVALUATION_AS_OF",)

    # SURVIVORSHIP_BIAS_RISK: registry of two, snapshot silently drops the
    # delisted member (existed: 0 <= 100; delisted 50 <= 100).
    delisted = _member("BBB", 0.0, delisted_at_ts=50.0)
    bias = survivorship_check(_snapshot(as_of, [alive]), as_of, [alive, delisted])
    assert bias.verdict == "SURVIVORSHIP_BIAS_RISK"
    assert bias.excluded_delisted_symbols == ("BBB",)

    # ANACHRONISTIC_MEMBER: snapshot includes a member listed at 150 for
    # an evaluation at 100 (knowledge from the future).
    late = _member("CCC", 150.0)
    anachron = survivorship_check(_snapshot(as_of, [alive, late]), as_of, [alive, late])
    assert anachron.verdict == "ANACHRONISTIC_MEMBER"
    assert anachron.anachronistic_symbols == ("CCC",)

    # INCOMPLETE_UNIVERSE: an alive expected member is absent.
    alive2 = _member("DDD", 10.0)
    incomplete = survivorship_check(_snapshot(as_of, [alive]), as_of, [alive, alive2])
    assert incomplete.verdict == "INCOMPLETE_UNIVERSE"
    assert incomplete.missing_symbols == ("DDD",)


# ---------------------------------------------------------------------------
# Boundary semantics — delisted AFTER the evaluation point
# ---------------------------------------------------------------------------


def test_p3_member_delisted_after_as_of_missing_is_incomplete_not_bias():
    # BBB delisted at 150, evaluation at 100: BBB existed (0 <= 100) and
    # was STILL LISTED at the evaluation point (150 > 100). Its exclusion
    # is an INCOMPLETE universe, NOT a survivorship finding — the classic
    # silent survivorship filter only applies to members that had already
    # delisted at/before the evaluation timestamp (delisted <= as_of).
    alive = _member("AAA", 0.0)
    late_delist = _member("BBB", 0.0, delisted_at_ts=150.0)
    verdict = survivorship_check(
        _snapshot(100.0, [alive]), 100.0, [alive, late_delist]
    )
    assert verdict.verdict == "INCOMPLETE_UNIVERSE"
    assert verdict.missing_symbols == ("BBB",)
    assert verdict.excluded_delisted_symbols == ()
    assert "EXPECTED_MEMBERS_MISSING" in verdict.reason_codes
    assert "SURVIVORSHIP_EXCLUDED_DELISTED_MEMBERS" not in verdict.reason_codes


def test_p3_stale_snapshot_older_than_evaluation_is_not_flagged_anachronistic():
    # Snapshot as_of 50 for an evaluation at 100 (snapshot OLDER than the
    # evaluation). The guard flags only knowledge from AFTER the
    # evaluation point (SNAPSHOT_AS_OF_AFTER_EVALUATION_AS_OF); a stale
    # snapshot that still matches the registry classifies purely by
    # membership. PINNING CURRENT BEHAVIOR deliberately: staleness in the
    # other direction is surfaced (if at all) as missing members, not as
    # a staleness code. If the owner later wants a STALE_SNAPSHOT code,
    # that is an additive extension — this test documents today's
    # contract.
    alive = _member("AAA", 0.0)
    verdict = survivorship_check(_snapshot(50.0, [alive]), 100.0, [alive])
    assert verdict.verdict == "OK"
    assert "SNAPSHOT_AS_OF_AFTER_EVALUATION_AS_OF" not in verdict.reason_codes


# ---------------------------------------------------------------------------
# Fail-closed refusals — additional shapes
# ---------------------------------------------------------------------------


def test_p3_conflicting_member_record_on_delisted_field():
    # Same symbol, registry says still listed, snapshot claims a delisting
    # — a lifecycle conflict on the SECOND field (the existing suite only
    # flips listed_from_ts). Refusal, not classification.
    registry_b = _member("BBB", 0.0)
    snapshot_b = _member("BBB", 0.0, delisted_at_ts=60.0)
    with pytest.raises(SurvivorshipGuardError, match="CONFLICTING_MEMBER_RECORD"):
        survivorship_check(
            _snapshot(100.0, [snapshot_b]), 100.0, [registry_b]
        )


def test_p3_evaluation_as_of_ts_must_be_finite_numeric():
    alive = _member("AAA", 0.0)
    with pytest.raises(SurvivorshipGuardError, match="TS_NOT_NUMERIC"):
        survivorship_check(_snapshot(100.0, [alive]), "100", [alive])  # type: ignore[arg-type]
    with pytest.raises(SurvivorshipGuardError, match="TS_NOT_FINITE"):
        survivorship_check(_snapshot(100.0, [alive]), math.nan, [alive])
    with pytest.raises(SurvivorshipGuardError, match="TS_NOT_FINITE"):
        survivorship_check(_snapshot(100.0, [alive]), math.inf, [alive])


def test_p3_verdict_precedence_survivorship_beats_missing_in_minimal_case():
    # Minimal two-finding case: delisted member excluded (bias) AND alive
    # member missing (incomplete) — headline must be SURVIVORSHIP_BIAS_RISK
    # with both findings visible in their per-category lists.
    alive = _member("AAA", 0.0)
    delisted = _member("BBB", 0.0, delisted_at_ts=50.0)
    alive2 = _member("CCC", 10.0)
    verdict = survivorship_check(
        _snapshot(100.0, [alive]), 100.0, [alive, delisted, alive2]
    )
    assert verdict.verdict == "SURVIVORSHIP_BIAS_RISK"
    assert verdict.excluded_delisted_symbols == ("BBB",)
    assert verdict.missing_symbols == ("CCC",)
    assert verdict.reason_codes == (
        "SURVIVORSHIP_EXCLUDED_DELISTED_MEMBERS",
        "EXPECTED_MEMBERS_MISSING",
    )
    assert (verdict.universe_size, verdict.snapshot_size) == (3, 1)
