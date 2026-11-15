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
