"""Per-fundamental-line PIT acceptance tests (hand-derived, deterministic).

Pins the closure of the honestly-recorded per-line gap: line-keyed resolution
at an explicit cutoff, restatement chains that never delete history, conflict
surfacing (never silently resolved), NOT_AVAILABLE honesty, and the
publication-unknown state that can never be used at its cutoff.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.evidence import Period
from app.domain.fundamental_dossier import FilingPeriod, FundamentalFact
from app.domain.fundamental_line_pit import (
    FundamentalLinePitError,
    resolve_line_at_cutoff,
    resolve_statement_at_cutoff,
)

UTC = dt.timezone.utc
T_PUB = dt.datetime(2025, 12, 31, tzinfo=UTC)
T_RET = dt.datetime(2026, 1, 15, tzinfo=UTC)
CUT = dt.datetime(2026, 3, 1, tzinfo=UTC)


def _filing(**over) -> FilingPeriod:
    base = dict(
        filing_id="f-1",
        company_id="co-1",
        reporting_period=Period(
            period_start=dt.datetime(2025, 1, 1, tzinfo=UTC),
            period_end=dt.datetime(2025, 12, 31, tzinfo=UTC),
        ),
        fiscal_calendar="iran-fiscal-1404",
        publication_status="KNOWN",
        publication_time_utc=T_PUB,
        retrieval_time_utc=T_RET,
        source_evidence_ids=("ev-f-1",),
    )
    base.update(over)
    return FilingPeriod(**base)


def _fact(**over) -> FundamentalFact:
    base = dict(
        fact_id="fact-1",
        company_id="co-1",
        metric="revenue",
        value=Decimal("1000.5"),
        value_status="REPORTED",
        unit="billion-IRR",
        currency="IRR",
        period=_filing(),
        source_evidence_ids=("ev-f-1",),
    )
    base.update(over)
    return FundamentalFact(**base)


def test_resolved_line_carries_value_unit_currency_auditor():
    r = resolve_line_at_cutoff([_fact()], "revenue", CUT)
    assert r.state == "RESOLVED"
    assert r.fact.value == Decimal("1000.5")
    assert r.unit == "billion-IRR" and r.currency == "IRR"
    assert r.superseded_chain == ()
    assert r.cutoff_utc == CUT


def test_no_fact_state():
    r = resolve_line_at_cutoff([_fact()], "eps", CUT)
    assert r.state == "NO_FACT" and r.fact is None and r.period_keys == ()


def test_not_yet_public_refuses_future_filing():
    late = _fact(fact_id="fact-2", period=_filing(filing_id="f-2", publication_time_utc=dt.datetime(2026, 4, 1, tzinfo=UTC)))
    r = resolve_line_at_cutoff([late], "revenue", CUT)
    assert r.state == "NOT_YET_PUBLIC" and r.fact is None


def test_publication_unknown_never_usable_at_cutoff():
    f = _fact(
        period=_filing(publication_status="UNAVAILABLE", publication_time_utc=None, retrieval_time_utc=dt.datetime(2026, 5, 1, tzinfo=UTC))
    )
    r = resolve_line_at_cutoff([f], "revenue", CUT)
    assert r.state == "PUBLICATION_UNKNOWN" and r.fact is None
    assert "unknown" in r.note


def test_retrieval_fallback_is_pit_usable():
    # publication UNAVAILABLE + retrieval BEFORE cutoff = eligible (facts_at_cutoff discipline)
    f = _fact(
        period=_filing(publication_status="UNAVAILABLE", publication_time_utc=None, retrieval_time_utc=dt.datetime(2026, 1, 15, tzinfo=UTC))
    )
    r = resolve_line_at_cutoff([f], "revenue", CUT)
    assert r.state == "RESOLVED" and r.fact.fact_id == "fact-1"


def test_restatement_chain_latest_version_wins_history_recorded():
    v1 = _fact(fact_id="fact-v1", value=Decimal("900"), restatement_version=1)
    v2 = _fact(
        fact_id="fact-v2",
        value=Decimal("950"),
        restatement_version=2,
        supersedes_fact_id="fact-v1",
        period=_filing(filing_id="f-2", publication_time_utc=dt.datetime(2026, 2, 15, tzinfo=UTC)),
    )
    r = resolve_line_at_cutoff([v1, v2], "revenue", CUT)
    assert r.state == "RESOLVED"
    assert r.fact.fact_id == "fact-v2" and r.fact.value == Decimal("950")
    assert r.superseded_chain == ("fact-v1",)


def test_restatement_after_cutoff_does_not_leak():
    v1 = _fact(fact_id="fact-v1", value=Decimal("900"), restatement_version=1)
    v2 = _fact(
        fact_id="fact-v2",
        value=Decimal("950"),
        restatement_version=2,
        supersedes_fact_id="fact-v1",
        period=_filing(filing_id="f-2", publication_time_utc=dt.datetime(2026, 4, 15, tzinfo=UTC)),
    )
    r = resolve_line_at_cutoff([v1, v2], "revenue", CUT)
    assert r.state == "RESOLVED"
    assert r.fact.fact_id == "fact-v1" and r.fact.value == Decimal("900")
    assert r.superseded_chain == ()


def test_conflicting_sources_surfaced_never_silently_resolved():
    a = _fact(fact_id="fact-a", value=Decimal("100"), source_evidence_ids=("ev-a",))
    b = _fact(fact_id="fact-b", value=Decimal("200"), source_evidence_ids=("ev-b",))
    r = resolve_line_at_cutoff([a, b], "revenue", CUT)
    assert r.state == "CONFLICTING_SOURCES"
    assert r.conflicting_fact_ids == ("fact-a", "fact-b")
    assert r.fact is None


def test_same_value_from_two_sources_is_not_conflict():
    a = _fact(fact_id="fact-a", value=Decimal("100"))
    b = _fact(fact_id="fact-b", value=Decimal("100"))
    r = resolve_line_at_cutoff([a, b], "revenue", CUT)
    assert r.state == "RESOLVED"


def test_not_available_value_surfaces_missing_line():
    f = _fact(value=None, value_status="NOT_AVAILABLE")
    r = resolve_line_at_cutoff([f], "revenue", CUT)
    assert r.state == "NOT_AVAILABLE" and r.fact.fact_id == "fact-1"


def test_period_filter_selects_one_period():
    p2024 = _fact(
        fact_id="fact-2024",
        value=Decimal("500"),
        period=_filing(
            filing_id="f-2024",
            reporting_period=Period(
                period_start=dt.datetime(2024, 1, 1, tzinfo=UTC),
                period_end=dt.datetime(2024, 12, 31, tzinfo=UTC),
            ),
        ),
    )
    r = resolve_line_at_cutoff([p2024, _fact()], "revenue", CUT, reporting_period="2024-01-01T00:00:00+00:00:2024-12-31T00:00:00+00:00")
    assert r.state == "RESOLVED" and r.fact.fact_id == "fact-2024"


def test_statement_resolution_names_cutoff_and_counts():
    facts = [
        _fact(),
        _fact(fact_id="fact-eps", metric="eps", value=Decimal("120"), unit="IRR", value_status="REPORTED"),
        _fact(fact_id="fact-na", metric="capex", value=None, value_status="NOT_AVAILABLE"),
    ]
    out = resolve_statement_at_cutoff(facts, CUT)
    assert out["cutoff_utc"] == CUT.isoformat()
    assert out["resolved_count"] == 2 and out["unresolved_count"] == 1
    states = {l["metric"]: l["state"] for l in out["lines"]}
    assert states == {"revenue": "RESOLVED", "eps": "RESOLVED", "capex": "NOT_AVAILABLE"}


def test_naive_cutoff_refused():
    with pytest.raises(FundamentalLinePitError):
        resolve_line_at_cutoff([_fact()], "revenue", dt.datetime(2026, 3, 1))


def test_dossier_fact_model_still_guarded():
    # restatement without a superseded id stays rejected at the model layer
    with pytest.raises(ValidationError):
        _fact(restatement_version=2)


# ---------------------------------------------------------------------------
# MULTI-PERIOD statement contract (audit remediation 2026-11-16).
# The statement API must resolve EVERY (metric, reporting_period) pair
# independently: older periods are never discarded, restatement chains and
# conflicts are scoped per period, and a conflict in one period cannot hide
# a valid result in another.
# ---------------------------------------------------------------------------

P2024_KEY = "2024-01-01T00:00:00+00:00:2024-12-31T00:00:00+00:00"
P2025_KEY = "2025-01-01T00:00:00+00:00:2025-12-31T00:00:00+00:00"


def _fact_2024_kw(**over) -> FundamentalFact:
    """2024-period fact builder accepting full keyword overrides (kw-merge,
    unlike _fact_2024 which pins value/fact_id positionally)."""
    base = dict(
        fact_id="fact-2024",
        value=Decimal("500"),
        period=_filing(
            filing_id="f-2024",
            reporting_period=Period(
                period_start=dt.datetime(2024, 1, 1, tzinfo=UTC),
                period_end=dt.datetime(2024, 12, 31, tzinfo=UTC),
            ),
        ),
    )
    base.update(over)
    return _fact(**base)


def _fact_2024(**over) -> FundamentalFact:
    return _fact(
        fact_id="fact-2024",
        value=Decimal("500"),
        period=_filing(
            filing_id="f-2024",
            reporting_period=Period(
                period_start=dt.datetime(2024, 1, 1, tzinfo=UTC),
                period_end=dt.datetime(2024, 12, 31, tzinfo=UTC),
            ),
        ),
        **over,
    )


def test_statement_preserves_two_reporting_periods():
    # same metric, two eligible periods — BOTH must come back, never collapsed
    facts = [_fact_2024(), _fact()]  # fact-1 = 2025 revenue 1000.5
    out = resolve_statement_at_cutoff(facts, CUT)
    rev = [l for l in out["lines"] if l["metric"] == "revenue"]
    assert len(rev) == 2, "older reporting period must not be silently discarded"
    by_period = {l["reporting_period"]: l for l in rev}
    assert set(by_period) == {P2024_KEY, P2025_KEY}
    assert by_period[P2024_KEY]["state"] == "RESOLVED"
    assert by_period[P2024_KEY]["fact"].fact_id == "fact-2024"
    assert by_period[P2025_KEY]["state"] == "RESOLVED"
    assert by_period[P2025_KEY]["fact"].fact_id == "fact-1"
    assert out["resolved_count"] == 2 and out["unresolved_count"] == 0
    assert out["metrics_count"] == 1 and out["reporting_periods_count"] == 2


def test_statement_restatement_in_only_one_period_keeps_chains_independent():
    # 2025 carries a v1→v2 restatement; 2024 has only its original fact.
    v1 = _fact(fact_id="fact-v1", value=Decimal("900"), restatement_version=1)
    v2 = _fact(
        fact_id="fact-v2",
        value=Decimal("950"),
        restatement_version=2,
        supersedes_fact_id="fact-v1",
        period=_filing(filing_id="f-2", publication_time_utc=dt.datetime(2026, 2, 15, tzinfo=UTC)),
    )
    facts = [_fact_2024(), v1, v2]
    out = resolve_statement_at_cutoff(facts, CUT)
    by_period = {l["reporting_period"]: l for l in out["lines"] if l["metric"] == "revenue"}
    assert len(by_period) == 2
    p2025, p2024 = by_period[P2025_KEY], by_period[P2024_KEY]
    assert p2025["state"] == "RESOLVED" and p2025["fact"].fact_id == "fact-v2"
    assert p2025["superseded_chain"] == ("fact-v1",)
    # the 2024 period resolves independently: own winner, own (empty) chain
    assert p2024["state"] == "RESOLVED" and p2024["fact"].fact_id == "fact-2024"
    assert p2024["superseded_chain"] == (), "chains must never bleed across periods"
    assert out["resolved_count"] == 2 and out["unresolved_count"] == 0


def test_statement_conflict_in_one_period_does_not_hide_other_period():
    # 2025 has two same-version different-value facts (conflict);
    # 2024 is a clean single fact and must still resolve.
    a = _fact(fact_id="fact-a", value=Decimal("100"), source_evidence_ids=("ev-a",))
    b = _fact(fact_id="fact-b", value=Decimal("200"), source_evidence_ids=("ev-b",))
    facts = [_fact_2024(), a, b]
    out = resolve_statement_at_cutoff(facts, CUT)
    by_period = {l["reporting_period"]: l for l in out["lines"] if l["metric"] == "revenue"}
    assert len(by_period) == 2
    p2025, p2024 = by_period[P2025_KEY], by_period[P2024_KEY]
    assert p2025["state"] == "CONFLICTING_SOURCES"
    assert p2025["conflicting_fact_ids"] == ("fact-a", "fact-b")
    assert p2025["fact"] is None
    # the valid 2024 result survives the unrelated conflict
    assert p2024["state"] == "RESOLVED" and p2024["fact"].fact_id == "fact-2024"
    assert out["resolved_count"] == 1 and out["unresolved_count"] == 1


def test_statement_counts_and_deterministic_ordering():
    facts = [
        _fact(),  # revenue 2025
        _fact_2024(),  # revenue 2024
        _fact(fact_id="fact-eps", metric="eps", value=Decimal("120"), unit="IRR"),
    ]
    out = resolve_statement_at_cutoff(facts, CUT)
    assert out["resolved_count"] == 3 and out["unresolved_count"] == 0
    assert out["metrics_count"] == 2 and out["reporting_periods_count"] == 2
    order = [(l["metric"], l["reporting_period"]) for l in out["lines"]]
    assert order == sorted(order), "lines must be deterministically ordered"


def test_statement_naive_cutoff_refused_even_for_empty_fact_set():
    naive = dt.datetime(2026, 3, 1)
    with pytest.raises(FundamentalLinePitError):
        resolve_statement_at_cutoff([_fact()], naive)
    with pytest.raises(FundamentalLinePitError):
        resolve_statement_at_cutoff([], naive)


def test_line_level_multi_period_collapse_is_explicit_not_silent():
    # the single-line API collapses by design, but never silently: both
    # candidate periods stay visible via period_keys.
    facts = [_fact_2024(), _fact()]
    r = resolve_line_at_cutoff(facts, "revenue", CUT)
    assert r.state == "RESOLVED" and r.fact.fact_id == "fact-1"
    assert set(r.period_keys) == {P2024_KEY, P2025_KEY}


# ---------------------------------------------------------------------------
# LINE-LEVEL selected-period contract (final RC1 audit remediation 2026-11-17).
# Contract documented BEFORE implementation in
# docs/active/RC1_LINE_PIT_CONTRACT_RECORD_2026-11-17.md:
#   C1 exact-key period selection, fail-closed on unknown keys;
#   C2 collapse to the most recent reporting period (period_end, ties by
#      latest availability then fact_id);
#   C3 conflict detection scoped to the SELECTED period only — an older-period
#      conflict can never mask the selected period's result (and is still
#      surfaced by the statement-level API);
#   C4 LineResolution.reporting_period populated on every return path;
#   C5 superseded_chain scoped to the selected period; cutoff semantics and
#      the statement-level API unchanged.
# ---------------------------------------------------------------------------


def test_line_collapse_older_period_conflict_does_not_mask_latest_period():
    # 2024 (older) carries a same-version two-source conflict; 2025 (latest)
    # is a clean single fact. The documented collapse must return the valid
    # 2025 result — the older-period conflict may not mask it.
    a = _fact_2024_kw(fact_id="fact-2024-a", value=Decimal("500"), source_evidence_ids=("ev-a",))
    b = _fact_2024_kw(fact_id="fact-2024-b", value=Decimal("600"), source_evidence_ids=("ev-b",))
    facts = [a, b, _fact()]  # fact-1 = clean 2025 revenue
    r = resolve_line_at_cutoff(facts, "revenue", CUT)
    assert r.state == "RESOLVED" and r.fact.fact_id == "fact-1"
    assert r.reporting_period == P2025_KEY, "collapse must name the period it selected"
    assert r.conflicting_fact_ids == (), "conflict ids are scoped to the selected period"
    assert set(r.period_keys) == {P2024_KEY, P2025_KEY}
    # the older-period conflict is NOT silently resolved: the statement-level
    # API still surfaces it, scoped to its own period.
    out = resolve_statement_at_cutoff(facts, CUT)
    by_period = {l["reporting_period"]: l for l in out["lines"] if l["metric"] == "revenue"}
    assert by_period[P2024_KEY]["state"] == "CONFLICTING_SOURCES"
    assert by_period[P2024_KEY]["conflicting_fact_ids"] == ("fact-2024-a", "fact-2024-b")
    assert by_period[P2025_KEY]["state"] == "RESOLVED"
    assert by_period[P2025_KEY]["fact"].fact_id == "fact-1"


def test_line_conflict_in_selected_period_surfaced_with_metadata():
    # explicit selection of the conflicting period → CONFLICTING_SOURCES,
    # metadata names the conflicting period, nothing silently chosen.
    a = _fact_2024_kw(fact_id="fact-2024-a", value=Decimal("500"), source_evidence_ids=("ev-a",))
    b = _fact_2024_kw(fact_id="fact-2024-b", value=Decimal("600"), source_evidence_ids=("ev-b",))
    r = resolve_line_at_cutoff([a, b], "revenue", CUT, reporting_period=P2024_KEY)
    assert r.state == "CONFLICTING_SOURCES"
    assert r.conflicting_fact_ids == ("fact-2024-a", "fact-2024-b")
    assert r.reporting_period == P2024_KEY and r.fact is None
    # same discipline when the conflicting period is the latest and no
    # explicit selection is made: the collapse surfaces it, metadata named.
    c = _fact(fact_id="fact-2025-a", value=Decimal("100"), source_evidence_ids=("ev-c",))
    d = _fact(fact_id="fact-2025-b", value=Decimal("200"), source_evidence_ids=("ev-d",))
    r2 = resolve_line_at_cutoff([c, d], "revenue", CUT)
    assert r2.state == "CONFLICTING_SOURCES"
    assert r2.conflicting_fact_ids == ("fact-2025-a", "fact-2025-b")
    assert r2.reporting_period == P2025_KEY


def test_line_explicit_period_metadata_populated_in_every_state():
    facts = [_fact_2024(), _fact()]
    r = resolve_line_at_cutoff(facts, "revenue", CUT, reporting_period=P2024_KEY)
    assert r.state == "RESOLVED" and r.fact.fact_id == "fact-2024"
    assert r.reporting_period == P2024_KEY
    r2 = resolve_line_at_cutoff(facts, "revenue", CUT, reporting_period=P2025_KEY)
    assert r2.state == "RESOLVED" and r2.fact.fact_id == "fact-1"
    assert r2.reporting_period == P2025_KEY
    # NOT_AVAILABLE state also carries the selected-period metadata
    na = _fact_2024_kw(value=None, value_status="NOT_AVAILABLE")
    r3 = resolve_line_at_cutoff([na], "revenue", CUT, reporting_period=P2024_KEY)
    assert r3.state == "NOT_AVAILABLE"
    assert r3.reporting_period == P2024_KEY


def test_line_missing_or_ambiguous_period_fails_closed_named():
    facts = [_fact_2024(), _fact()]
    # a well-formed key that matches no reporting period: NO_FACT, the
    # requested key stays named in the metadata, never guessed.
    unknown = "2099-01-01T00:00:00+00:00:2099-12-31T00:00:00+00:00"
    r = resolve_line_at_cutoff(facts, "revenue", CUT, reporting_period=unknown)
    assert r.state == "NO_FACT" and r.fact is None
    assert r.reporting_period == unknown
    assert r.period_keys == ()
    assert "requested" in r.note
    # a malformed/partial key can never fuzzy-match an existing period:
    # exact-match contract, fail-closed with the key named.
    r2 = resolve_line_at_cutoff(facts, "revenue", CUT, reporting_period="2024-01-01")
    assert r2.state == "NO_FACT" and r2.reporting_period == "2024-01-01"
    assert r2.fact is None


def test_line_collapse_names_selected_period_and_scopes_chain():
    # restatement chain lives in the LATEST period; an older clean period is
    # present. Omitted selection: collapse resolves the latest winner, names
    # the selected period, and the chain stays scoped to that period.
    v1 = _fact(fact_id="fact-v1", value=Decimal("900"), restatement_version=1)
    v2 = _fact(
        fact_id="fact-v2",
        value=Decimal("950"),
        restatement_version=2,
        supersedes_fact_id="fact-v1",
        period=_filing(filing_id="f-2", publication_time_utc=dt.datetime(2026, 2, 15, tzinfo=UTC)),
    )
    facts = [_fact_2024(), v1, v2]
    r = resolve_line_at_cutoff(facts, "revenue", CUT)
    assert r.state == "RESOLVED" and r.fact.fact_id == "fact-v2"
    assert r.reporting_period == P2025_KEY
    assert r.superseded_chain == ("fact-v1",), "chain must be scoped to the selected period"
    assert set(r.period_keys) == {P2024_KEY, P2025_KEY}
