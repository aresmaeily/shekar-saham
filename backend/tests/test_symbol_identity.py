"""Paper tests for runtime symbol identity resolution (Agent E, module 2).

Composes fundamental_dossier.CompanyIdentity exactly: ambiguity is surfaced,
never silently resolved (D-AI-33; 06 charter §3.4). Hand-built registry
fixtures, hand-computed expectations, exact refusal reason codes. No network,
no wall clock (resolved_at_utc is always injected).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.symbol_identity import IdentityRecord, resolve_symbol

T_RESOLVED = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
T_TEHRAN = datetime(2026, 1, 5, 11, 30, tzinfo=timezone(timedelta(hours=3, minutes=30)))

FOOLAD_ISIN = "IRO1FOLD0001"
BMLT_ISIN = "IRO1BMLT0001"


def _rec(l18, isin, *, name="فولاد مبارکه", status="ACTIVE"):
    return {"l18": l18, "isin": isin, "name": name, "official_name_fa": name, "status": status}


# ---------------------------------------------------------------------------
# Resolved-unique paths
# ---------------------------------------------------------------------------


def test_resolved_unique_by_symbol_composes_company_identity() -> None:
    resolution = resolve_symbol("فولاد", None, [_rec("فولاد", FOOLAD_ISIN)], resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "RESOLVED_UNIQUE"
    assert resolution.matched_key == "SYMBOL"
    assert resolution.reason_codes == ("resolved_by_symbol_unique_match",)
    identity = resolution.identity
    assert identity is not None
    # CompanyIdentity composed verbatim (fundamental_dossier constructor).
    assert identity.company_id == FOOLAD_ISIN
    assert identity.symbols == ("فولاد",)
    assert identity.resolution_basis == "REGISTRY_MATCH"
    assert identity.ambiguity_status == "UNAMBIGUOUS"
    assert identity.candidate_matches == ()
    assert identity.resolved_at_utc == T_RESOLVED
    assert identity.source_evidence_ids == ("idrec:فولاد:IRO1FOLD0001",)


def test_resolved_unique_by_isin_query_with_symbol_history() -> None:
    records = [_rec("فولاد", FOOLAD_ISIN), _rec("فولاد1", FOOLAD_ISIN, name="old symbol")]
    resolution = resolve_symbol("فولاد", FOOLAD_ISIN, records, resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "RESOLVED_UNIQUE"
    assert resolution.matched_key == "ISIN"
    assert resolution.identity is not None
    assert resolution.identity.symbols == ("فولاد", "فولاد1")
    assert "multiple_symbols_share_isin" in resolution.reason_codes
    assert "resolved_by_isin_multiple_records_same_isin" in resolution.reason_codes


def test_resolution_is_deterministic_and_inputs_frozen() -> None:
    records = [IdentityRecord(l18="فولاد", isin=FOOLAD_ISIN, status="ACTIVE")]
    first = resolve_symbol("فولاد", None, records, resolved_at_utc=T_RESOLVED)
    second = resolve_symbol("فولاد", None, records, resolved_at_utc=T_RESOLVED)
    assert first == second
    with pytest.raises(ValidationError):
        records[0].l18 = "وبملت"  # frozen record: mutation refused


def test_mapping_records_are_accepted() -> None:
    resolution = resolve_symbol("فولاد", None, [_rec("فولاد", FOOLAD_ISIN)], resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "RESOLVED_UNIQUE"


# ---------------------------------------------------------------------------
# Ambiguity / not-found / degraded honesty (never silently resolved)
# ---------------------------------------------------------------------------


def test_ambiguous_multiple_isin_surfaced_with_candidates() -> None:
    records = [_rec("فولاد", FOOLAD_ISIN), _rec("فولاد", BMLT_ISIN)]
    resolution = resolve_symbol("فولاد", None, records, resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "AMBIGUOUS_MULTIPLE_ISIN"
    identity = resolution.identity
    assert identity is not None
    assert identity.ambiguity_status == "AMBIGUOUS_UNRESOLVED"  # dossier honesty, verbatim
    assert identity.candidate_matches == (BMLT_ISIN, FOOLAD_ISIN)
    assert identity.company_id == "unresolved:فولاد"  # explicitly NOT a resolved key
    assert len(resolution.candidates) == 2
    assert resolution.reason_codes[0] == "multiple_isins_for_symbol"


def test_not_found_by_symbol_invents_nothing() -> None:
    resolution = resolve_symbol("غایب", None, [_rec("فولاد", FOOLAD_ISIN)], resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "NOT_FOUND"
    assert resolution.identity is None
    assert resolution.candidates == ()
    assert resolution.matched_key is None
    assert resolution.reason_codes == ("symbol_not_found_in_records",)


def test_not_found_by_isin() -> None:
    resolution = resolve_symbol("فولاد", "IRO1MISSS9999", [_rec("فولاد", FOOLAD_ISIN)], resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "NOT_FOUND"
    assert resolution.reason_codes == ("isin_not_found_in_records",)


def test_degraded_missing_isin_single_record() -> None:
    resolution = resolve_symbol("فولاد", None, [_rec("فولاد", None)], resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "DEGRADED_MISSING_ISIN"
    identity = resolution.identity
    assert identity is not None
    assert identity.company_id == "l18:فولاد"
    assert identity.ambiguity_status == "UNAMBIGUOUS"
    assert len(resolution.candidates) == 1
    assert resolution.reason_codes == ("isin_missing_in_all_matched_records",)


def test_degraded_multiple_records_without_isin_is_ambiguous() -> None:
    records = [_rec("فولاد", None), _rec("فولاد", None, name="duplicate listing")]
    resolution = resolve_symbol("فولاد", None, records, resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "DEGRADED_MISSING_ISIN"
    identity = resolution.identity
    assert identity is not None
    assert identity.ambiguity_status == "AMBIGUOUS_UNRESOLVED"  # mirror dossier ambiguity
    assert identity.candidate_matches  # candidates listed, never silently collapsed
    assert "multiple_records_without_isin" in resolution.reason_codes


# ---------------------------------------------------------------------------
# Status honesty, refusals, injected timestamps
# ---------------------------------------------------------------------------


def test_non_active_status_is_surfaced_not_hidden() -> None:
    delisted = resolve_symbol(
        "فولاد", None, [_rec("فولاد", FOOLAD_ISIN, status="DELISTED")], resolved_at_utc=T_RESOLVED
    )
    assert delisted.verdict == "RESOLVED_UNIQUE"
    assert delisted.matched_statuses == ("DELISTED",)
    assert "matched_status_delisted" in delisted.reason_codes
    suspended = resolve_symbol(
        "فولاد", None, [_rec("فولاد", FOOLAD_ISIN, status="SUSPENDED")], resolved_at_utc=T_RESOLVED
    )
    assert "matched_status_suspended" in suspended.reason_codes


def test_refusal_empty_or_whitespace_l18() -> None:
    with pytest.raises(ValueError, match="l18_must_not_be_empty"):
        resolve_symbol("", None, [], resolved_at_utc=T_RESOLVED)
    with pytest.raises(ValueError, match="l18_must_not_be_empty"):
        resolve_symbol("   ", None, [], resolved_at_utc=T_RESOLVED)


def test_resolved_at_utc_must_be_injected_and_is_normalized_to_utc() -> None:
    with pytest.raises(ValueError, match="timestamp_must_be_timezone_aware"):
        resolve_symbol("فولاد", None, [_rec("فولاد", FOOLAD_ISIN)], resolved_at_utc=datetime(2026, 1, 5, 8, 0))
    resolution = resolve_symbol("فولاد", None, [_rec("فولاد", FOOLAD_ISIN)], resolved_at_utc=T_TEHRAN)
    assert resolution.identity is not None
    assert resolution.identity.resolved_at_utc == T_RESOLVED  # 11:30+03:30 == 08:00Z


def test_empty_string_isin_is_unknown_isin() -> None:
    resolution = resolve_symbol("فولاد", "", [_rec("فولاد", "")], resolved_at_utc=T_RESOLVED)
    assert resolution.verdict == "DEGRADED_MISSING_ISIN"
    assert resolution.candidates[0].isin is None
