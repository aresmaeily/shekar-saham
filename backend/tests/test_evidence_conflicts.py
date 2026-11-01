"""Paper tests for cross-provider quote-conflict detection (Agent E, module 1).

Each test cites its roadmap locus (02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md
lines 18-25, 133-142; 06 charter §3.3-3.4). Hand-built two-source fixture
boards; hand-computed expectations; every refusal path asserts its exact
reason code. No network, no provider calls, no wall clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.evidence_conflicts import (
    detect_quote_conflicts,
    detect_syndicated_copies,
)
from app.models.schemas import SymbolSnapshot

T_ASOF = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
T_NOW = datetime(2026, 1, 10, 15, 0, tzinfo=timezone.utc)
TOL = "0.5"  # percent, hand-computed expectations below


def _board_foolad(tsetmc_price, brsapi_price, *, tsetmc_isin="IRO1FOLD0001", brsapi_isin="IRO1FOLD0001"):
    return {
        "tsetmc": [{"symbol": "فولاد", "isin": tsetmc_isin, "last_price": tsetmc_price}],
        "brsapi": [{"symbol": "فولاد", "isin": brsapi_isin, "last_price": brsapi_price}],
    }


# ---------------------------------------------------------------------------
# Agreement / conflict / borderline (06 charter §3.4: contradictions stay
# explicit; borderline within tolerance is not a contradiction)
# ---------------------------------------------------------------------------


def test_agreeing_boards_produce_no_conflicts() -> None:
    conflicts = detect_quote_conflicts(
        _board_foolad(1000, 1000), tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW
    )
    assert conflicts == []  # legitimate empty outcome, not a refusal


def test_conflict_beyond_tolerance_emits_open_evidence_conflict() -> None:
    # Hand-computed: |1006-1000| * 100 / 1000 = 0.6% > 0.5% tol.
    conflicts = detect_quote_conflicts(
        _board_foolad(1000, 1006), tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW
    )
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.status == "OPEN"
    assert conflict.resolution_rule is None and conflict.resolved_by is None
    assert conflict.resolved_at_utc is None
    assert len(conflict.evidence_ids) == 2 and len(set(conflict.evidence_ids)) == 2
    assert "1000" in conflict.description and "1006" in conflict.description
    assert T_ASOF.isoformat() in conflict.description
    assert conflict.conflict_id.startswith("QC-")
    assert "match_key=ISIN" in conflict.notes


def test_borderline_exactly_at_tolerance_is_not_conflict() -> None:
    # Hand-computed: |1005-1000| * 100 / 1000 = 0.5% == tol → not > tol.
    conflicts = detect_quote_conflicts(
        _board_foolad(1000, 1005), tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW
    )
    assert conflicts == []


def test_missing_in_one_source_is_not_a_conflict() -> None:
    boards = {
        "tsetmc": [
            {"symbol": "فولاد", "isin": "IRO1FOLD0001", "last_price": 1000},
            {"symbol": "وبملت", "isin": "IRO1BMLT0001", "last_price": 3000},
        ],
        "brsapi": [{"symbol": "فولاد", "isin": "IRO1FOLD0001", "last_price": 1000}],
    }
    conflicts = detect_quote_conflicts(boards, tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW)
    assert conflicts == []  # وبملت absent from brsapi: coverage gap, not a conflict


# ---------------------------------------------------------------------------
# Syndication vs conflict (06 charter §3.3: copied syndications are not
# independent corroboration; evidence.py CorroborationStatus distinguishes
# SYNDICATED_COPY from CONFLICTING — that distinction is honored)
# ---------------------------------------------------------------------------


def test_syndicated_identical_copy_is_flagged_not_conflicted() -> None:
    boards = _board_foolad(1000, 1000)
    families = {"tsetmc": "TSETMC_CDN", "brsapi": "TSETMC_CDN"}
    conflicts = detect_quote_conflicts(boards, tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW)
    assert conflicts == []  # identical data is not a contradiction
    copies = detect_syndicated_copies(
        boards, origin_family_by_source=families, as_of_utc=T_ASOF, now_utc=T_NOW
    )
    assert len(copies) == 1
    copy = copies[0]
    assert copy.corroboration_status == "SYNDICATED_COPY"  # exact schema vocabulary
    assert (copy.source_a, copy.source_b) == ("brsapi", "tsetmc")
    assert copy.match_key == "ISIN" and copy.isin == "IRO1FOLD0001"


def test_same_family_divergence_still_conflicts() -> None:
    boards = _board_foolad(1000, 1006)
    families = {"tsetmc": "TSETMC_CDN", "brsapi": "TSETMC_CDN"}
    conflicts = detect_quote_conflicts(boards, tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW)
    assert len(conflicts) == 1 and conflicts[0].status == "OPEN"
    copies = detect_syndicated_copies(
        boards, origin_family_by_source=families, as_of_utc=T_ASOF, now_utc=T_NOW
    )
    assert copies == ()  # divergent copy: a conflict, never a clean syndication


# ---------------------------------------------------------------------------
# Matching semantics
# ---------------------------------------------------------------------------


def test_isin_match_key_recorded() -> None:
    conflicts = detect_quote_conflicts(
        _board_foolad(1000, 1006), tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW
    )
    (conflict,) = conflicts
    assert all(":ISIN:IRO1FOLD0001:" in eid for eid in conflict.evidence_ids)


def test_symbol_fallback_key_recorded_when_isin_missing() -> None:
    boards = {
        "tsetmc": [{"symbol": "فولاد", "isin": "", "last_price": 1000}],
        "brsapi": [{"symbol": "فولاد", "last_price": 1006}],
    }
    conflicts = detect_quote_conflicts(boards, tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW)
    (conflict,) = conflicts
    assert "match_key=SYMBOL" in conflict.notes
    assert all(":SYMBOL:فولاد:" in eid for eid in conflict.evidence_ids)


def test_different_isins_same_symbol_never_match() -> None:
    conflicts = detect_quote_conflicts(
        _board_foolad(1000, 1006, brsapi_isin="IRO1OTHER9999"),
        tol_pct=TOL,
        as_of_utc=T_ASOF,
        now_utc=T_NOW,
    )
    assert conflicts == []  # two different instruments, not one contradiction


# ---------------------------------------------------------------------------
# Honest refusals (reason codes, never silent empty results)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bad_tol", "reason"),
    [
        (0, "tol_pct_must_be_positive"),
        (-1, "tol_pct_must_be_positive"),
        ("abc", "tol_pct_not_decimal_representable"),
        (float("nan"), "tol_pct_not_decimal_representable"),
        (float("inf"), "tol_pct_not_decimal_representable"),
        (True, "tol_pct_must_be_number"),
    ],
)
def test_refusals_invalid_tolerance(bad_tol, reason) -> None:
    with pytest.raises(ValueError, match=reason):
        detect_quote_conflicts(_board_foolad(1000, 1000), tol_pct=bad_tol, as_of_utc=T_ASOF)


def test_refusals_empty_mapping_empty_board_duplicate_identity() -> None:
    with pytest.raises(ValueError, match="boards_by_source_must_not_be_empty"):
        detect_quote_conflicts({}, tol_pct=TOL, as_of_utc=T_ASOF)
    with pytest.raises(ValueError, match="board_for_source_must_not_be_empty: brsapi"):
        detect_quote_conflicts(
            {"tsetmc": [{"symbol": "فولاد", "last_price": 1000}], "brsapi": []},
            tol_pct=TOL,
            as_of_utc=T_ASOF,
        )
    with pytest.raises(ValueError, match="duplicate_identity_within_source: tsetmc"):
        detect_quote_conflicts(
            {
                "tsetmc": [
                    {"symbol": "فولاد", "isin": "IRO1FOLD0001", "last_price": 1000},
                    {"symbol": "فولاد", "isin": "IRO1FOLD0001", "last_price": 1006},
                ],
                "brsapi": [{"symbol": "فولاد", "isin": "IRO1FOLD0001", "last_price": 1000}],
            },
            tol_pct=TOL,
            as_of_utc=T_ASOF,
        )


def test_refusal_future_as_of_and_naive_as_of() -> None:
    with pytest.raises(ValueError, match="as_of_must_not_be_in_future"):
        detect_quote_conflicts(
            _board_foolad(1000, 1000),
            tol_pct=TOL,
            as_of_utc=T_NOW + timedelta(hours=1),
            now_utc=T_NOW,
        )
    with pytest.raises(ValueError, match="timestamp_must_be_timezone_aware"):
        detect_quote_conflicts(
            _board_foolad(1000, 1000), tol_pct=TOL, as_of_utc=datetime(2026, 1, 10, 12, 0)
        )


def test_refusal_non_positive_or_missing_price() -> None:
    with pytest.raises(ValueError, match="row_last_price_must_be_positive"):
        detect_quote_conflicts(
            _board_foolad(0, 1000), tol_pct=TOL, as_of_utc=T_ASOF
        )
    with pytest.raises(ValueError, match="row_last_price_missing"):
        detect_quote_conflicts(
            {"tsetmc": [{"symbol": "فولاد", "isin": "IRO1FOLD0001"}], "brsapi": [{"symbol": "فولاد", "last_price": 1}]},
            tol_pct=TOL,
            as_of_utc=T_ASOF,
        )


# ---------------------------------------------------------------------------
# Determinism and row-input composition
# ---------------------------------------------------------------------------


def test_deterministic_ordering_by_symbol_then_source() -> None:
    boards = {
        "brsapi": [
            {"symbol": "فولاد", "isin": "IRO1FOLD0001", "last_price": 1006},
            {"symbol": "وبملت", "isin": "IRO1BMLT0001", "last_price": 3120},
        ],
        "tsetmc": [
            {"symbol": "فولاد", "isin": "IRO1FOLD0001", "last_price": 1000},
            {"symbol": "وبملت", "isin": "IRO1BMLT0001", "last_price": 3000},
        ],
    }
    # Hand-computed: فولاد 0.6% conflict; وبملت |3120-3000|*100/3000 = 4.0% conflict.
    first = detect_quote_conflicts(boards, tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW)
    again = detect_quote_conflicts(boards, tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW)
    assert len(first) == 2
    assert [c.conflict_id for c in first] == [c.conflict_id for c in again]
    assert first[0].description.startswith("Last price for فولاد")
    assert first[1].description.startswith("Last price for وبملت")
    assert "brsapi" in first[0].evidence_ids[0]  # source ordered inside pair ids


def test_snapshot_rows_and_dict_rows_are_equivalent_inputs() -> None:
    snapshot_boards = {
        "tsetmc": [
            SymbolSnapshot(l18="فولاد", isin="IRO1FOLD0001", pl=1000.0, source="tsetmc")
        ],
        "brsapi": [
            SymbolSnapshot(l18="فولاد", isin="IRO1FOLD0001", pl=1006.0, source="brsapi")
        ],
    }
    dict_boards = _board_foolad(1000, 1006)
    from_snapshots = detect_quote_conflicts(
        snapshot_boards, tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW
    )
    from_dicts = detect_quote_conflicts(dict_boards, tol_pct=TOL, as_of_utc=T_ASOF, now_utc=T_NOW)
    assert len(from_snapshots) == len(from_dicts) == 1
    # Same conflict semantics: identical match key, divergence and tolerance.
    assert from_snapshots[0].evidence_ids == from_dicts[0].evidence_ids
    assert from_snapshots[0].notes == from_dicts[0].notes == (
        "match_key=ISIN; divergence_pct=0.6; tol_pct=0.5"
    )
