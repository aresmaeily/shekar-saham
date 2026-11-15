"""P2 liquidity pinning — observation-pinned liquidity semantics (pure domain).

Closes the honestly-recorded gap ``P2 liquidity pinning`` (ROADMAP_TRACEABILITY_DELTA
line 12; OWNER_COMPLETION_STAGE_2026-11-08 record §7). Purely additive sibling of
``corporate_actions.py`` / ``universe_membership.py``: no I/O, no network, no
wall-clock — every date is an explicit parameter; imports nothing from any
data/provider module.

What "pinning" means here (kept deliberately narrow, never invented finance):

1. VALUE-BASED liquidity (traded turnover, e.g. ``tval``-style amounts) is
   PINNED TO ITS OBSERVATION SESSION. A turnover amount is already denominated
   in the toman of its own session; multiplying it by a corporate-action price
   factor fabricates a value that was never traded. ``pin_value_observation``
   refuses any attempt to apply an out-of-window event factor to a value
   observation (``ANACHRONISTIC_ADJUSTMENT``), mirroring the fail-closed
   refusals of ``corporate_actions.adjust_price``.

2. VOLUME-BASED liquidity comparability ACROSS an ex-date is delegated to the
   existing, test-pinned arithmetic of ``corporate_actions`` (``event_volume_factor``
   / ``pit_applicability``): share-count measures may be put on a comparable
   basis only with an IN-WINDOW (``ex_date > price_date``) event, and only
   with an explicit basis label.

3. Publish-time discipline (module docstring discipline 2 of corporate_actions):
   an observation may drive a decision dated ``query_at`` only if the session
   has occurred AND the data was public by then; an unknown publication time is
   the honest ``PUBLICATION_UNKNOWN`` — never silently usable.

4. Basis discipline: a comparison set that mixes ``VALUE_OBSERVATION_PINNED``
   and ``VOLUME_ADJUSTED`` bases is refused (``MIXED_BASIS``) — mixing adjusted
   and unadjusted denominators is the classic liquidity-comparability bug.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Sequence

from app.domain.corporate_actions import (
    CorporateAction,
    event_volume_factor,
    pit_applicability,
)

LiquidityBasis = Literal["VALUE_OBSERVATION_PINNED", "VOLUME_RAW", "VOLUME_ADJUSTED"]

ObservationUsability = Literal[
    "USABLE",
    "NOT_YET_OBSERVED",
    "NOT_YET_PUBLIC",
    "PUBLICATION_UNKNOWN",
]


class LiquidityPinningError(ValueError):
    """Module refusal (fail-closed); reason_code is machine-readable."""

    def __init__(self, reason_code: str, message: str | None = None) -> None:
        super().__init__(message or reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class LiquidityObservation:
    """One session-scoped liquidity observation, honest about publication.

    ``amount`` is the session turnover in toman (value basis). ``volume_shares``
    is the optional raw share count. ``publication_status`` mirrors the dossier
    discipline: KNOWN requires ``published_at``; UNKNOWN forbids it.
    """

    symbol_id: str
    session_date: dt.date
    amount: Decimal
    unit: str = "toman"
    volume_shares: Decimal | None = None
    publication_status: Literal["KNOWN", "UNKNOWN"] = "UNKNOWN"
    published_at: dt.datetime | None = None

    def __post_init__(self) -> None:
        if self.publication_status == "KNOWN" and self.published_at is None:
            raise LiquidityPinningError("known_publication_requires_timestamp")
        if self.publication_status == "UNKNOWN" and self.published_at is not None:
            raise LiquidityPinningError("unknown_publication_forbids_timestamp")
        if self.amount < 0:
            raise LiquidityPinningError("negative_liquidity_amount")


def pin_value_observation(
    obs: LiquidityObservation,
    event: CorporateAction | None,
    price_date: dt.date,
) -> dict[str, Any]:
    """Value-based amounts are pinned to their observation session.

    The returned record pins ``amount`` verbatim (same numeric value, same
    session unit) with basis ``VALUE_OBSERVATION_PINNED``. If a caller supplies
    an event whose factor window has already closed for ``price_date``
    (``ex_date <= price_date``) the attempt is REFUSED — applying a closed
    factor to a value observation would fabricate history.
    """
    if not isinstance(price_date, dt.date) or isinstance(price_date, dt.datetime):
        raise LiquidityPinningError("price_date_must_be_plain_date")
    if event is not None and event.ex_date <= price_date:
        raise LiquidityPinningError(
            "ANACHRONISTIC_ADJUSTMENT",
            f"event ex_date={event.ex_date.isoformat()} is out of window for price_date={price_date.isoformat()}; value observations are never factor-adjusted",
        )
    return {
        "symbol_id": obs.symbol_id,
        "session_date": obs.session_date,
        "amount": obs.amount,
        "unit": obs.unit,
        "basis": "VALUE_OBSERVATION_PINNED",
        "factor_applied": None,
        "event_ref": None,
        "note": "value liquidity pinned to observation session; no factor ever applied",
    }


def observation_usability(obs: LiquidityObservation, query_at: dt.datetime) -> dict[str, Any]:
    """Publish-time discipline for using an observation at ``query_at``.

    Deterministic precedence:
    1. session in the future relative to query  → NOT_YET_OBSERVED
    2. publication KNOWN and ``published_at > query_at`` → NOT_YET_PUBLIC
    3. publication UNKNOWN                      → PUBLICATION_UNKNOWN (honest)
    4. otherwise                                → USABLE
    """
    if query_at.tzinfo is None:
        raise LiquidityPinningError("query_at_must_be_timezone_aware")
    if obs.session_date > query_at.date():
        return {
            "status": "NOT_YET_OBSERVED",
            "usable": False,
            "reason_code": "session_after_query",
            "session_date": obs.session_date,
            "query_date": query_at.date(),
        }
    if obs.publication_status == "KNOWN":
        if obs.published_at > query_at:
            return {
                "status": "NOT_YET_PUBLIC",
                "usable": False,
                "reason_code": "published_after_query",
                "session_date": obs.session_date,
                "query_date": query_at.date(),
            }
        return {
            "status": "USABLE",
            "usable": True,
            "reason_code": "session_and_publication_before_query",
            "session_date": obs.session_date,
            "query_date": query_at.date(),
        }
    return {
        "status": "PUBLICATION_UNKNOWN",
        "usable": False,
        "reason_code": "publication_time_unknown_honest_unknown",
        "session_date": obs.session_date,
        "query_date": query_at.date(),
    }


def liquidity_series_view(
    observations: Sequence[LiquidityObservation], query_at: dt.datetime
) -> dict[str, Any]:
    """Per-observation usability + explicit pinned basis over a series."""
    items = []
    for obs in observations:
        item = pin_value_observation(obs, None, obs.session_date)
        item["usability"] = observation_usability(obs, query_at)
        items.append(item)
    return {
        "basis": "VALUE_OBSERVATION_PINNED",
        "unit": "toman",
        "observations": items,
        "note": "value amounts pinned to observation sessions; factors never applied",
    }


def volume_basis_view(
    observations: Sequence[LiquidityObservation],
    events: Sequence[CorporateAction],
    price_date: dt.date,
    query_date: dt.date,
) -> dict[str, Any]:
    """Share-count liquidity on a comparable basis across an ex-date.

    Two explicit dates, deliberately separate (corporate_actions docstring
    disciplines 1/2):
      * ``price_date`` — the session whose RAW share count is being put on a
        comparable basis: only events still pending at that session
        (``ex_date > price_date``) contribute their factor; an event already
        in effect at the session is refused (``ANACHRONISTIC_ADJUSTMENT``).
      * ``query_date`` — the date at which this comparability view is
        COMPUTED and used: the publish-time gate (``pit_applicability``)
        must be applicable at ``query_date`` for the factor to be applied;
        a not-yet-public or before-ex-date event is recorded in the chain
        with ``applied: False`` — never silently skipped.
    """
    if not isinstance(price_date, dt.date) or isinstance(price_date, dt.datetime):
        raise LiquidityPinningError("price_date_must_be_plain_date")
    if not isinstance(query_date, dt.date) or isinstance(query_date, dt.datetime):
        raise LiquidityPinningError("query_date_must_be_plain_date")
    ordered = sorted(events, key=lambda e: e.ex_date)
    items = []
    for obs in observations:
        factor = 1.0
        chain: list[dict[str, Any]] = []
        for event in ordered:
            if event.symbol_id != obs.symbol_id:
                continue
            if event.ex_date <= price_date:
                raise LiquidityPinningError(
                    "ANACHRONISTIC_ADJUSTMENT",
                    f"event ex_date={event.ex_date.isoformat()} out of window for price_date={price_date.isoformat()}",
                )
            gate = pit_applicability(event, query_date)
            if not gate.applicable:
                chain.append(
                    {
                        "event_type": event.event_type,
                        "ex_date": event.ex_date.isoformat(),
                        "pit_status": gate.status,
                        "applied": False,
                    }
                )
                continue
            f = event_volume_factor(event)
            factor *= f
            chain.append(
                {
                    "event_type": event.event_type,
                    "ex_date": event.ex_date.isoformat(),
                    "pit_status": gate.status,
                    "applied": True,
                    "volume_factor": f,
                }
            )
        raw = obs.volume_shares if obs.volume_shares is not None else None
        comparable = (Decimal(str(factor)) * raw) if raw is not None else None
        items.append(
            {
                "symbol_id": obs.symbol_id,
                "session_date": obs.session_date,
                "volume_shares_raw": raw,
                "volume_shares_comparable": comparable,
                "basis": "VOLUME_ADJUSTED" if (chain and factor != 1.0) else "VOLUME_RAW",
                "factor_chain": chain,
                "composed_factor": factor,
            }
        )
    return {"price_date": price_date, "query_date": query_date, "observations": items}


def require_single_basis(records: Sequence[dict[str, Any]]) -> str:
    """Fail-closed basis guard for any cross-observation comparison."""
    bases = {r.get("basis") for r in records}
    if len(bases) > 1:
        raise LiquidityPinningError(
            "MIXED_BASIS",
            f"comparison set mixes liquidity bases: {sorted(str(b) for b in bases)}",
        )
    if not bases:
        raise LiquidityPinningError("EMPTY_COMPARISON_SET")
    return next(iter(bases))
