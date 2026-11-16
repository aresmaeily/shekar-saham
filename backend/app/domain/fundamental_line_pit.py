"""Per-fundamental-line point-in-time resolution (pure domain).

Closes the honestly-recorded gap ``per-fundamental-line PIT module`` (the
event/membership layers were IMPLEMENTED — ``corporate_actions.py`` publish-time
PIT + ``universe_membership.py`` as-of — while the per-LINE module remained
PARTIAL). Purely additive sibling of ``fundamental_dossier.py``: it consumes
``FundamentalFact`` records and adds LINE-KEYED point-in-time resolution with
restatement chains and conflict surfacing. No I/O, no wall-clock — the cutoff
is an explicit parameter.

Corpus discipline (02 roadmap line 141-142): filings are versioned, time-aware
evidence; conflicting figures, restatements, missing periods and unknown audit
status are SURFACED, never silently resolved; every resolution names its
information cutoff.

Resolution states (deterministic precedence):
  NO_FACT             — no fact for the line at all
  NOT_YET_PUBLIC      — facts exist but none published/retrievable by cutoff
  PUBLICATION_UNKNOWN — candidate fact exists whose publication time is
                        unknown and whose retrieval is after the cutoff
                        (honest unknown; never usable for the cutoff)
  CONFLICTING_SOURCES — ≥2 eligible facts for the same (line, period,
                        restatement_version) with DIFFERENT values; both ids
                        surfaced, nothing silently chosen
  RESOLVED            — exactly one winning fact per period (highest
                        restatement_version announced by cutoff, chain recorded)
  NOT_AVAILABLE       — the winning fact explicitly reports a NOT_AVAILABLE
                        value (missing datum surfaced, never invented)

Statement-level contract (audit remediation 2026-11-16):
  ``resolve_statement_at_cutoff`` resolves EVERY ``(metric, reporting_period)``
  pair present in the fact set independently. A statement is more than its
  latest period: older reporting periods are returned side by side, never
  silently discarded; restatement chains and conflicts are scoped to their own
  period, so a conflict in one period cannot hide a valid result in another.
  ``resolve_line_at_cutoff`` without an explicit ``reporting_period`` remains a
  SINGLE-line resolution across all periods present and collapses to the one
  latest-available winner (its ``period_keys`` field always surfaces which
  periods were considered) — consumers wanting the complete multi-period view
  MUST use ``resolve_statement_at_cutoff``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from app.domain.fundamental_dossier import FundamentalFact

LineResolutionState = Literal[
    "RESOLVED",
    "NOT_AVAILABLE",
    "NOT_YET_PUBLIC",
    "PUBLICATION_UNKNOWN",
    "CONFLICTING_SOURCES",
    "NO_FACT",
]


class FundamentalLinePitError(ValueError):
    """Fail-closed refusal; reason_code machine-readable."""


def _available_at(fact: FundamentalFact, cutoff: dt.datetime) -> dt.datetime | None:
    filing = fact.period
    if filing.publication_status == "KNOWN":
        return filing.publication_time_utc
    return filing.retrieval_time_utc


def _period_key(fact: FundamentalFact) -> str:
    p = fact.period.reporting_period
    s = p.period_start.isoformat() if p.period_start is not None else "UNKNOWN_START"
    e = p.period_end.isoformat() if p.period_end is not None else "UNKNOWN_END"
    return f"{s}:{e}"


@dataclass(frozen=True)
class LineResolution:
    metric: str
    state: LineResolutionState
    cutoff_utc: dt.datetime
    fact: FundamentalFact | None
    conflicting_fact_ids: tuple[str, ...]
    superseded_chain: tuple[str, ...]
    unit: str | None
    currency: str | None
    auditor_status: str
    period_keys: tuple[str, ...]
    note: str
    reporting_period: str | None = None


def resolve_line_at_cutoff(
    facts: Sequence[FundamentalFact],
    metric: str,
    cutoff: dt.datetime,
    *,
    reporting_period: str | None = None,
) -> LineResolution:
    """Point-in-time resolution of ONE fundamental line (metric) at a cutoff.

    Eligibility reuses the ``facts_at_cutoff`` discipline verbatim: KNOWN
    publication requires ``publication_time_utc <= cutoff``; otherwise the
    retrieval time must be ``<= cutoff``. Restatements win by version; the
    superseded chain is recorded, never deleted.

    Period selection is EXPLICIT when ``reporting_period`` is given (a period
    key as produced by ``_period_key``); with no selection the pool spans every
    period present and the result collapses to the winner of the MOST RECENT
    REPORTING PERIOD (period_end), ties broken by latest availability then
    fact_id — a documented, deterministic refinement of the previous collapse,
    which ordered by availability alone and could return an older period when
    publication times coincided (audit remediation 2026-11-16; no pre-existing
    test pinned the undefined tie case; single-period behavior unchanged). For
    the complete multi-period statement view use ``resolve_statement_at_cutoff``,
    which resolves every (metric, reporting_period) pair independently and
    never discards older periods.
    """
    if cutoff.tzinfo is None:
        raise FundamentalLinePitError("cutoff_must_be_timezone_aware")
    pool = [f for f in facts if f.metric == metric]
    if reporting_period is not None:
        pool = [f for f in pool if _period_key(f) == reporting_period]
    period_keys = tuple(sorted({_period_key(f) for f in pool}))
    if not pool:
        return LineResolution(
            metric=metric,
            state="NO_FACT",
            cutoff_utc=cutoff,
            fact=None,
            conflicting_fact_ids=(),
            superseded_chain=(),
            unit=None,
            currency=None,
            auditor_status="UNKNOWN",
            period_keys=(),
            note="no fact for this line",
        )

    eligible = [f for f in pool if (t := _available_at(f, cutoff)) is not None and t <= cutoff]
    if not eligible:
        # Publication KNOWN after cutoff = provably late (NOT_YET_PUBLIC).
        # Publication UNKNOWN (UNAVAILABLE) = the honest unknown: the moment
        # the filing became public is not recorded, so usability at the
        # cutoff cannot be claimed either way (PUBLICATION_UNKNOWN).
        unknown = [f for f in pool if f.period.publication_status != "KNOWN"]
        state = "PUBLICATION_UNKNOWN" if unknown else "NOT_YET_PUBLIC"
        return LineResolution(
            metric=metric,
            state=state,
            cutoff_utc=cutoff,
            fact=None,
            conflicting_fact_ids=(),
            superseded_chain=(),
            unit=None,
            currency=None,
            auditor_status="UNKNOWN",
            period_keys=period_keys,
            note=(
                "publication time unknown and retrieval after cutoff — honest unknown, not usable"
                if state == "PUBLICATION_UNKNOWN"
                else "every filing for this line was published after the cutoff"
            ),
        )

    # restatement chains: highest restatement_version per period wins; chain recorded
    winners: list[FundamentalFact] = []
    chain: list[str] = []
    for key in sorted({_period_key(f) for f in eligible}):
        group = [f for f in eligible if _period_key(f) == key]
        group.sort(key=lambda f: f.restatement_version)
        win = group[-1]
        winners.append(win)
        chain.extend(f.fact_id for f in group[:-1])

    conflicts: list[str] = []
    for key in sorted({_period_key(f) for f in eligible}):
        group = [f for f in eligible if _period_key(f) == key]
        top_version = max(f.restatement_version for f in group)
        top = [f for f in group if f.restatement_version == top_version]
        values = {f.value for f in top if f.value is not None}
        if len(top) > 1 and len(values) > 1:
            conflicts.extend(sorted(f.fact_id for f in top))
    if conflicts:
        return LineResolution(
            metric=metric,
            state="CONFLICTING_SOURCES",
            cutoff_utc=cutoff,
            fact=None,
            conflicting_fact_ids=tuple(sorted(set(conflicts))),
            superseded_chain=tuple(chain),
            unit=None,
            currency=None,
            auditor_status="UNKNOWN",
            period_keys=period_keys,
            note="conflicting eligible values for the same line/period/version — surfaced, never silently resolved",
        )

    win = winners[0] if len(winners) == 1 else max(
        winners,
        key=lambda f: (
            f.period.reporting_period.period_end
            or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
            _available_at(f, cutoff) or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
            f.fact_id,
        ),
    )
    if win.value_status == "NOT_AVAILABLE" or win.value is None:
        return LineResolution(
            metric=metric,
            state="NOT_AVAILABLE",
            cutoff_utc=cutoff,
            fact=win,
            conflicting_fact_ids=(),
            superseded_chain=tuple(chain),
            unit=win.unit,
            currency=win.currency,
            auditor_status=win.auditor_status,
            period_keys=period_keys,
            note="the winning filing explicitly reports this line as NOT_AVAILABLE",
        )
    return LineResolution(
        metric=metric,
        state="RESOLVED",
        cutoff_utc=cutoff,
        fact=win,
        conflicting_fact_ids=(),
        superseded_chain=tuple(chain),
        unit=win.unit,
        currency=win.currency,
        auditor_status=win.auditor_status,
        period_keys=period_keys,
        note="latest restatement announced by the cutoff",
    )


def resolve_statement_at_cutoff(
    facts: Sequence[FundamentalFact], cutoff: dt.datetime
) -> dict[str, Any]:
    """MULTI-PERIOD statement resolution: one independently resolved entry per
    ``(metric, reporting_period)`` pair present in the fact set.

    Audit remediation (2026-11-16): the previous implementation resolved each
    metric once across all periods and kept only one fact per metric, silently
    discarding older reporting periods. That contradicted this module's own
    corpus discipline ("missing periods ... are SURFACED, never silently
    resolved"), so the statement API now preserves every period:

    * one separately resolved entry per (metric, reporting_period) pair;
    * restatement chains preserved independently per period;
    * conflicts surfaced independently per period — a conflict in one period
      cannot hide a valid result in another;
    * publication-time and retrieval-time cutoff rules reused verbatim
      (unchanged financial semantics at line level);
    * no older period is ever silently discarded.

    The returned record names the cutoff explicitly and keeps per-line states
    side by side, so a consumer cannot mix a resolved line with an unresolved
    one without seeing it. Deterministic ordering: (metric, reporting_period).
    """
    if cutoff.tzinfo is None:
        raise FundamentalLinePitError("cutoff_must_be_timezone_aware")
    pairs = sorted({(f.metric, _period_key(f)) for f in facts})
    lines: list[dict[str, Any]] = []
    for metric, period_key in pairs:
        r = resolve_line_at_cutoff(facts, metric, cutoff, reporting_period=period_key)
        d = dict(r.__dict__)
        d["reporting_period"] = period_key
        lines.append(d)
    lines.sort(key=lambda d: (d["metric"], d["reporting_period"] or ""))
    resolved = [l for l in lines if l["state"] == "RESOLVED"]
    unresolved = [l for l in lines if l["state"] != "RESOLVED"]
    return {
        "cutoff_utc": cutoff.isoformat(),
        "lines": lines,
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "metrics_count": len({m for m, _ in pairs}),
        "reporting_periods_count": len({p for _, p in pairs}),
        "note": (
            "one independently resolved entry per (metric, reporting_period) pair; "
            "older periods are never discarded; conflicts are scoped to their own "
            "period; every resolution names its cutoff"
        ),
    }
