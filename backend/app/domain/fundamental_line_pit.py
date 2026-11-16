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
  ``resolve_line_at_cutoff`` remains a SINGLE-line, SELECTED-period
  resolution: with an explicit ``reporting_period`` it resolves exactly that
  period (exact key match, fail-closed on an unknown key); without one it
  collapses to the MOST RECENT REPORTING PERIOD (period_end, ties by latest
  availability then fact_id) and conflict detection is scoped to that
  SELECTED period, so a conflict in an older period can never mask the
  selected period's result (final RC1 audit remediation 2026-11-17; the full
  contract is documented in the function docstring and
  docs/active/RC1_LINE_PIT_CONTRACT_RECORD_2026-11-17.md). Older periods,
  including any of their conflicts, are never silently resolved — they remain
  fully inspectable via ``resolve_statement_at_cutoff``, which is what
  consumers wanting the complete multi-period view MUST use; the collapse
  result names the period it selected in ``LineResolution.reporting_period``
  and its ``period_keys`` field always surfaces which periods were present.
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

    Documented contract (final RC1 audit remediation 2026-11-17; rationale in
    docs/active/RC1_LINE_PIT_CONTRACT_RECORD_2026-11-17.md):

    * C1 period selection — with an explicit ``reporting_period`` (a period
      key as produced by ``_period_key``) the pool is EXACTLY that period:
      exact key match, never fuzzy. A key matching no fact returns ``NO_FACT``
      with the requested key still named in ``LineResolution.reporting_period``
      (fail-closed; a missing or ambiguous/malformed key can never silently
      resolve to something else).
    * C2 collapse — with no explicit period the pool spans every period
      present and the result collapses to the MOST RECENT REPORTING PERIOD
      (period_end, ties broken by latest availability then fact_id — the same
      deterministic ordering as the winner selection; a documented,
      deterministic refinement of the previous collapse, which ordered by
      availability alone and could return an older period when publication
      times coincided).
    * C3 conflict scoping — conflict detection applies ONLY to the selected
      period. A conflict in a non-selected period can never mask the selected
      period's result. Nothing is silently resolved: older periods — including
      any of their conflicts — remain fully inspectable via
      ``resolve_statement_at_cutoff``, which resolves every (metric,
      reporting_period) pair independently, and ``period_keys`` always
      surfaces which periods were present in the pool. A conflict in the
      SELECTED period still refuses to silently choose
      (``CONFLICTING_SOURCES``).
    * C4 metadata — ``LineResolution.reporting_period`` is populated on every
      return path: the requested key for explicit selections (including
      ``NO_FACT``), the selected period's key for the collapse path whenever a
      period was selected, and ``None`` only where no period could be selected
      (empty pool, or no eligible fact with no explicit selection — the pool
      periods remain visible via ``period_keys``).
    * C5 chain scoping + unchanged semantics — ``superseded_chain`` is the
      SELECTED period's chain (history recorded, never deleted); per-period
      chains for other periods are available through the statement API.
      Eligibility rules, restatement-version precedence and NOT_AVAILABLE
      honesty are unchanged.

    For the complete multi-period statement view use
    ``resolve_statement_at_cutoff``, which resolves every (metric,
    reporting_period) pair independently and never discards older periods.
    """
    if cutoff.tzinfo is None:
        raise FundamentalLinePitError("cutoff_must_be_timezone_aware")
    pool = [f for f in facts if f.metric == metric]
    if reporting_period is not None:
        pool = [f for f in pool if _period_key(f) == reporting_period]
    period_keys = tuple(sorted({_period_key(f) for f in pool}))
    if not pool:
        # C1: an explicit unknown/malformed period key fails closed as NO_FACT
        # with the requested key still named (never a fuzzy fallback). C4.
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
            reporting_period=reporting_period,
            note=(
                "no fact for this line in the requested reporting period"
                if reporting_period is not None
                else "no fact for this line"
            ),
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
            reporting_period=reporting_period,
            note=(
                "publication time unknown and retrieval after cutoff — honest unknown, not usable"
                if state == "PUBLICATION_UNKNOWN"
                else "every filing for this line was published after the cutoff"
            ),
        )

    # restatement chains, scoped PER PERIOD (C5): highest restatement_version
    # wins; the superseded chain is recorded, never deleted.
    winners: dict[str, FundamentalFact] = {}
    chains: dict[str, tuple[str, ...]] = {}
    for key in sorted({_period_key(f) for f in eligible}):
        group = [f for f in eligible if _period_key(f) == key]
        group.sort(key=lambda f: f.restatement_version)
        winners[key] = group[-1]
        chains[key] = tuple(f.fact_id for f in group[:-1])

    # C1/C2: SELECT the target period — the explicitly requested key, or (with
    # no selection) the documented collapse: the most recent reporting period
    # by period_end, ties broken by latest availability then fact_id.
    if reporting_period is not None:
        selected_key = reporting_period
    else:
        selected_key = _period_key(
            max(
                winners.values(),
                key=lambda f: (
                    f.period.reporting_period.period_end
                    or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
                    _available_at(f, cutoff) or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
                    f.fact_id,
                ),
            )
        )

    # C3: conflict detection is scoped to the SELECTED period only — a
    # conflict in a non-selected period can never mask this result; it stays
    # surfaced via resolve_statement_at_cutoff (per-period independence), and
    # period_keys discloses the other periods present in the pool.
    group = [f for f in eligible if _period_key(f) == selected_key]
    top_version = max(f.restatement_version for f in group)
    top = [f for f in group if f.restatement_version == top_version]
    values = {f.value for f in top if f.value is not None}
    if len(top) > 1 and len(values) > 1:
        return LineResolution(
            metric=metric,
            state="CONFLICTING_SOURCES",
            cutoff_utc=cutoff,
            fact=None,
            conflicting_fact_ids=tuple(sorted(f.fact_id for f in top)),
            superseded_chain=chains[selected_key],
            unit=None,
            currency=None,
            auditor_status="UNKNOWN",
            period_keys=period_keys,
            reporting_period=selected_key,
            note="conflicting eligible values for the same line/period/version — surfaced, never silently resolved",
        )

    win = winners[selected_key]
    if win.value_status == "NOT_AVAILABLE" or win.value is None:
        return LineResolution(
            metric=metric,
            state="NOT_AVAILABLE",
            cutoff_utc=cutoff,
            fact=win,
            conflicting_fact_ids=(),
            superseded_chain=chains[selected_key],
            unit=win.unit,
            currency=win.currency,
            auditor_status=win.auditor_status,
            period_keys=period_keys,
            reporting_period=selected_key,
            note="the winning filing explicitly reports this line as NOT_AVAILABLE",
        )
    return LineResolution(
        metric=metric,
        state="RESOLVED",
        cutoff_utc=cutoff,
        fact=win,
        conflicting_fact_ids=(),
        superseded_chain=chains[selected_key],
        unit=win.unit,
        currency=win.currency,
        auditor_status=win.auditor_status,
        period_keys=period_keys,
        reporting_period=selected_key,
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
