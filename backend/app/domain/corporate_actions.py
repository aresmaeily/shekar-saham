"""Point-in-time corporate-actions adjustment arithmetic (P2, purely additive).

Corpus loci (2026-10-02 amendment corpus):
- 02_EXECUTION_ROADMAP lines 24-26 ("P2 --- Deterministic Measurement &
  Evidence Core"): "PIT, corporate actions, survivorship, look-ahead
  protection, ...".
- 02_EXECUTION_ROADMAP line 145 ("P3 --- Evaluation and research
  integrity"): "... survivorship/corporate-action handling ...".
- 06 Product Capability Charter, "Research and feedback": reproducible runs
  with point-in-time correctness.

Scope: pure domain arithmetic for the Iranian-market corporate-action set
(سود نقدی، سهام جایزه، تجزیه/تجمیع سهام، افزایش سرمایه از آورده، کاهش
سرمایه). Closed event taxonomy, multiplicative adjustment factors with
explicit formula constants, chronological composition, and publish-time
PIT discipline. No I/O, no network, no wall-clock: every date is an
explicit parameter. Imports nothing from any data/provider module.

Two time disciplines are kept deliberately separate — conflating them is
the classic look-ahead bug:

1. RETROSPECTIVE BACK-ADJUSTMENT (``adjust_price`` / ``adjust_volume`` /
   ``apply_event_price_factor``): to compare a PRE-event price with
   post-event prices, the pre-event price is multiplied by the event's
   factor. An event whose ``ex_date <= price_date`` is OUT OF WINDOW for
   that price — its factor is already embedded in the quoted price — and
   using it there is refused (``ANACHRONISTIC_ADJUSTMENT``), never
   silently skipped, mirroring the fail-closed refusals of
   ``market_calendar`` / ``regime_slices``. A caller building an adjusted
   series must therefore select, per price date, exactly the events still
   pending (``ex_date > price_date``); ``pit_applicability`` is the gate
   for that selection.

2. POINT-IN-TIME USABILITY (``pit_applicability`` / ``require_pit_usable``):
   an event may drive a decision/evaluation dated ``query_date`` only if
   ``query_date >= ex_date`` AND the event was public by ``query_date``.
   ``announce_date`` is honest-or-absent: when it is ``None`` the module
   reports ``APPLICABLE_ANNOUNCE_UNKNOWN`` (an applicability claim made
   WITHOUT publication evidence) — it never invents a publication date.
   When ``announce_date > query_date`` the ``NOT_YET_PUBLIC`` refusal
   fires (publish-time PIT discipline).

Closed vocabularies: ``CorporateActionType`` (six members) and ``PitStatus``
(four members) are Literal-enforced; extending either is a deliberate,
reviewed change — never a free-form string. All refusal reason codes are
stable machine-readable tags carried by :class:`CorporateActionError`.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "CORPORATE_ACTION_TYPES",
    "ComposedAdjustment",
    "CorporateAction",
    "CorporateActionError",
    "CorporateActionType",
    "PitApplicability",
    "PitStatus",
    "adjust_price",
    "adjust_volume",
    "apply_event_price_factor",
    "apply_event_volume_factor",
    "compose_adjustments",
    "event_price_factor",
    "event_volume_factor",
    "pit_applicability",
    "require_pit_usable",
]

#: Closed event taxonomy — the Iranian-market relevant set, documented:
#: - CASH_DIVIDEND      سود نقدی (cash per share paid out; price drops on ex-date)
#: - STOCK_DIVIDEND     سهام جایزه (bonus shares from retained earnings)
#: - SPLIT              تجزیه سهام (forward split: more shares, proportionally cheaper)
#: - REVERSE_SPLIT      تجمیع سهام (few shares merged into one)
#: - CAPITAL_RAISE      افزایش سرمایه از آورده (rights issue at a subscription price)
#: - CAPITAL_REDUCTION  کاهش سرمایه (shares cancelled, cash returned per cancelled share)
CorporateActionType = Literal[
    "CASH_DIVIDEND",
    "STOCK_DIVIDEND",
    "SPLIT",
    "REVERSE_SPLIT",
    "CAPITAL_RAISE",
    "CAPITAL_REDUCTION",
]

CORPORATE_ACTION_TYPES: tuple[str, ...] = (
    "CASH_DIVIDEND",
    "STOCK_DIVIDEND",
    "SPLIT",
    "REVERSE_SPLIT",
    "CAPITAL_RAISE",
    "CAPITAL_REDUCTION",
)

#: Closed PIT-status vocabulary (see module docstring, discipline 2).
PitStatus = Literal[
    "APPLICABLE_ANNOUNCE_KNOWN",
    "APPLICABLE_ANNOUNCE_UNKNOWN",
    "NOT_YET_PUBLIC",
    "BEFORE_EX_DATE",
]

#: Term fields each event type must carry (exactly these, no others).
_TERM_FIELDS: dict[str, tuple[str, ...]] = {
    "CASH_DIVIDEND": ("dividend_per_share", "base_price"),
    "STOCK_DIVIDEND": ("percent",),
    "SPLIT": ("new_per_old",),
    "REVERSE_SPLIT": ("old_per_new",),
    "CAPITAL_RAISE": ("raise_new_per_old", "issue_price", "base_price"),
    "CAPITAL_REDUCTION": ("cancelled_per_held", "cash_per_cancelled", "base_price"),
}

_ALL_TERM_FIELDS: tuple[str, ...] = (
    "dividend_per_share",
    "percent",
    "new_per_old",
    "old_per_new",
    "raise_new_per_old",
    "issue_price",
    "cancelled_per_held",
    "cash_per_cancelled",
    "base_price",
)


class CorporateActionError(ValueError):
    """Deterministic fail-closed refusal with a machine-readable reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}:{detail}" if detail else reason
        super().__init__(message)


def _plain_date(value: object, name: str) -> date:
    """Accept a plain calendar date; refuse instants (a day is not a moment)."""
    if isinstance(value, datetime) or not isinstance(value, date):
        raise CorporateActionError(
            f"{name.upper()}_MUST_BE_PLAIN_DATE", f"value={value!r}"
        )
    return value


def _finite_positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CorporateActionError(f"{name.upper()}_NOT_NUMERIC", f"value={value!r}")
    v = float(value)
    if not math.isfinite(v):
        raise CorporateActionError(f"{name.upper()}_NOT_FINITE", f"field={name}")
    return v


class CorporateAction(BaseModel):
    """One corporate action with its closed type and exactly its term fields.

    ``announce_date`` is honest-or-absent: ``None`` means publication time
    unknown (never invented). ``base_price`` is the pre-event reference
    close (ex-date eve) required by the event types whose factor depends on
    a price level (CASH_DIVIDEND, CAPITAL_RAISE, CAPITAL_REDUCTION).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    symbol_id: str = Field(min_length=1, max_length=64)
    event_type: CorporateActionType
    ex_date: date
    announce_date: date | None = None

    dividend_per_share: float | None = None
    percent: float | None = None
    new_per_old: float | None = None
    old_per_new: float | None = None
    raise_new_per_old: float | None = None
    issue_price: float | None = None
    cancelled_per_held: float | None = None
    cash_per_cancelled: float | None = None
    base_price: float | None = None

    @field_validator("event_type", mode="before")
    @classmethod
    def _closed_taxonomy(cls, v: object) -> object:
        # Stable refusal tag for anything outside the closed taxonomy
        # (fires BEFORE the Literal check so the reason is machine-readable).
        if isinstance(v, str) and v not in CORPORATE_ACTION_TYPES:
            raise ValueError("unknown_corporate_action_type")
        return v

    @model_validator(mode="after")
    def _terms_closed_and_valid(self) -> "CorporateAction":
        required = _TERM_FIELDS[self.event_type]
        for field_name in required:
            if getattr(self, field_name) is None:
                raise ValueError(f"term_field_required:{field_name}")
        for field_name in _ALL_TERM_FIELDS:
            if field_name not in required and getattr(self, field_name) is not None:
                raise ValueError(f"term_field_forbidden:{field_name}")
        _validate_event_terms(self)
        return self


def _validate_event_terms(event: CorporateAction) -> None:
    """Per-type range rules; every refusal carries a stable tag."""
    t = event.event_type
    if t == "CASH_DIVIDEND":
        d = float(event.dividend_per_share or 0.0)  # type: ignore[arg-type]
        base = float(event.base_price or 0.0)  # type: ignore[arg-type]
        if not math.isfinite(d) or not math.isfinite(base):
            raise ValueError("term_not_finite")
        if d <= 0:
            raise ValueError("dividend_not_positive")
        if base <= 0:
            raise ValueError("base_price_not_positive")
        if d >= base:
            raise ValueError("dividend_ge_base_price")
    elif t == "STOCK_DIVIDEND":
        p = float(event.percent or 0.0)  # type: ignore[arg-type]
        if not math.isfinite(p):
            raise ValueError("term_not_finite")
        if p <= 0:
            raise ValueError("percent_not_positive")
    elif t == "SPLIT":
        r = float(event.new_per_old or 0.0)  # type: ignore[arg-type]
        if not math.isfinite(r):
            raise ValueError("term_not_finite")
        if r <= 1:
            raise ValueError("split_ratio_must_exceed_one")
    elif t == "REVERSE_SPLIT":
        k = float(event.old_per_new or 0.0)  # type: ignore[arg-type]
        if not math.isfinite(k):
            raise ValueError("term_not_finite")
        if k <= 1:
            raise ValueError("reverse_ratio_must_exceed_one")
    elif t == "CAPITAL_RAISE":
        f = float(event.raise_new_per_old or 0.0)  # type: ignore[arg-type]
        s = float(event.issue_price or 0.0)  # type: ignore[arg-type]
        base = float(event.base_price or 0.0)  # type: ignore[arg-type]
        if not (math.isfinite(f) and math.isfinite(s) and math.isfinite(base)):
            raise ValueError("term_not_finite")
        if f <= 0:
            raise ValueError("raise_fraction_not_positive")
        if s < 0:
            raise ValueError("issue_price_negative")
        if base <= 0:
            raise ValueError("base_price_not_positive")
    elif t == "CAPITAL_REDUCTION":
        c = float(event.cancelled_per_held or 0.0)  # type: ignore[arg-type]
        cash = float(event.cash_per_cancelled or 0.0)  # type: ignore[arg-type]
        base = float(event.base_price or 0.0)  # type: ignore[arg-type]
        if not (math.isfinite(c) and math.isfinite(cash) and math.isfinite(base)):
            raise ValueError("term_not_finite")
        if not (0 < c < 1):
            raise ValueError("cancelled_fraction_out_of_range")
        if cash < 0:
            raise ValueError("cash_per_cancelled_negative")
        if base <= 0:
            raise ValueError("base_price_not_positive")
        if c * cash >= base:
            raise ValueError("reduction_value_ge_base_price")
    else:  # pragma: no cover — Literal-closed taxonomy makes this unreachable
        raise ValueError("unknown_corporate_action_type")


def _event_factors(event: CorporateAction) -> tuple[float, float]:
    """(price_factor, volume_factor) — explicit formula per event type.

    CONVENTION: the price factor maps a PRE-event price onto the POST-event
    scale (``adjusted_pre = raw_pre * price_factor``); the volume factor is
    ``new_share_count / old_share_count`` (pre-event volumes are multiplied
    by it to be comparable with post-event volumes).

    Formulas (P = base_price = pre-event reference close):
    - CASH_DIVIDEND(D):       ex-price = P - D          → price_factor = (P - D) / P, volume 1
    - STOCK_DIVIDEND(p%):     ex-price = P / (1 + p/100) → price_factor = 1 / (1 + p/100), volume 1 + p/100
    - SPLIT(n new per old):   ex-price = P / n          → price_factor = 1 / n, volume n
    - REVERSE_SPLIT(k old per new): ex-price = P * k    → price_factor = k, volume 1 / k
    - CAPITAL_RAISE(f new per old at issue price S):
        ex-price = (P + f·S) / (1 + f)                  → price_factor = (P + f·S) / ((1 + f)·P), volume 1 + f
        (S = 0 reduces to the bonus-share shape 1/(1+f).)
    - CAPITAL_REDUCTION(c cancelled per held, cash D per cancelled share):
        ex-price = (P - c·D) / (1 - c)                  → price_factor = (P - c·D) / ((1 - c)·P), volume 1 - c
    """
    t = event.event_type
    if t == "CASH_DIVIDEND":
        base = float(event.base_price or 0.0)  # type: ignore[arg-type]
        d = float(event.dividend_per_share or 0.0)  # type: ignore[arg-type]
        return (base - d) / base, 1.0
    if t == "STOCK_DIVIDEND":
        r = 1.0 + float(event.percent or 0.0) / 100.0  # type: ignore[arg-type]
        return 1.0 / r, r
    if t == "SPLIT":
        n = float(event.new_per_old or 0.0)  # type: ignore[arg-type]
        return 1.0 / n, n
    if t == "REVERSE_SPLIT":
        k = float(event.old_per_new or 0.0)  # type: ignore[arg-type]
        return k, 1.0 / k
    if t == "CAPITAL_RAISE":
        f = float(event.raise_new_per_old or 0.0)  # type: ignore[arg-type]
        s = float(event.issue_price or 0.0)  # type: ignore[arg-type]
        base = float(event.base_price or 0.0)  # type: ignore[arg-type]
        return (base + f * s) / ((1.0 + f) * base), 1.0 + f
    if t == "CAPITAL_REDUCTION":
        c = float(event.cancelled_per_held or 0.0)  # type: ignore[arg-type]
        cash = float(event.cash_per_cancelled or 0.0)  # type: ignore[arg-type]
        base = float(event.base_price or 0.0)  # type: ignore[arg-type]
        return (base - c * cash) / ((1.0 - c) * base), 1.0 - c
    raise CorporateActionError(
        "UNKNOWN_EVENT_TYPE", f"event_type={event.event_type!r}"
    )  # pragma: no cover — Literal-closed


def event_price_factor(event: CorporateAction) -> float:
    """Multiplicative factor mapping a PRE-event price to the post-event scale."""
    price_factor, _ = _event_factors(event)
    if not math.isfinite(price_factor) or price_factor <= 0:
        raise CorporateActionError(
            "FACTOR_NOT_REPRESENTABLE", f"event_type={event.event_type}"
        )
    return price_factor


def event_volume_factor(event: CorporateAction) -> float:
    """Multiplicative factor = new_share_count / old_share_count for the event."""
    _, volume_factor = _event_factors(event)
    if not math.isfinite(volume_factor) or volume_factor <= 0:
        raise CorporateActionError(
            "FACTOR_NOT_REPRESENTABLE", f"event_type={event.event_type}"
        )
    return volume_factor


def _require_ascending_same_symbol(events: Sequence[CorporateAction]) -> tuple[CorporateAction, ...]:
    """Chronology gate shared by compose/apply/adjust.

    Refusals (stable tags):
    - ``UNORDERED_EX_DATES``      — events must be strictly ascending by ex_date
    - ``DUPLICATE_EX_DATE``       — two events sharing an ex_date are ambiguous
    - ``MIXED_SYMBOL_COMPOSITION``— factors of different symbols never compose
    """
    symbols = {e.symbol_id for e in events}
    if len(symbols) > 1:
        raise CorporateActionError(
            "MIXED_SYMBOL_COMPOSITION", f"symbols={sorted(symbols)}"
        )
    previous: CorporateAction | None = None
    for index, event in enumerate(events):
        if previous is not None:
            if event.ex_date < previous.ex_date:
                raise CorporateActionError(
                    "UNORDERED_EX_DATES",
                    f"index={index} prev={previous.ex_date} cur={event.ex_date}",
                )
            if event.ex_date == previous.ex_date:
                raise CorporateActionError(
                    "DUPLICATE_EX_DATE",
                    f"index={index} ex_date={event.ex_date}",
                )
        previous = event
    return tuple(events)


class ComposedAdjustment(BaseModel):
    """Frozen result of composing events in ascending ex-date order.

    Empty input composes to the honest identity (1.0 / 1.0) with no events
    declared — "no corporate actions" is representable, never guessed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    events: tuple[CorporateAction, ...]
    price_factor: float
    volume_factor: float


def compose_adjustments(events: Sequence[CorporateAction]) -> ComposedAdjustment:
    """Compose event factors chronologically (ascending ex-date, enforced).

    The caller supplies ONE symbol's events already ordered by ex_date;
    unordered, duplicate-date, or cross-symbol input is refused (see
    :func:`_require_ascending_same_symbol`), not re-sorted silently.
    """
    ordered = _require_ascending_same_symbol(events)
    price_factor = 1.0
    volume_factor = 1.0
    for event in ordered:
        price_factor *= event_price_factor(event)
        volume_factor *= event_volume_factor(event)
    return ComposedAdjustment(
        events=ordered,
        price_factor=price_factor,
        volume_factor=volume_factor,
    )


def apply_event_price_factor(
    event: CorporateAction, raw_price: float, price_date: date
) -> float:
    """Apply ONE event's price factor to a strictly pre-event price.

    ``price_date >= ex_date`` is an anachronistic use (the quoted price is
    already on the post-event scale) and is refused with the stable tag
    ``ANACHRONISTIC_ADJUSTMENT`` — a post-event factor may never be applied
    to a price at/after its own ex-date.
    """
    day = _plain_date(price_date, "price_date")
    price = _finite_positive(raw_price, "price")
    if price < 0:
        raise CorporateActionError("PRICE_NEGATIVE", f"value={raw_price!r}")
    if day >= event.ex_date:
        raise CorporateActionError(
            "ANACHRONISTIC_ADJUSTMENT",
            f"event={event.event_type} ex_date={event.ex_date} price_date={day}",
        )
    return price * event_price_factor(event)


def apply_event_volume_factor(
    event: CorporateAction, raw_volume: float, price_date: date
) -> float:
    """Apply ONE event's volume factor to a strictly pre-event volume."""
    day = _plain_date(price_date, "price_date")
    volume = _finite_positive(raw_volume, "volume")
    if volume < 0:
        raise CorporateActionError("VOLUME_NEGATIVE", f"value={raw_volume!r}")
    if day >= event.ex_date:
        raise CorporateActionError(
            "ANACHRONISTIC_ADJUSTMENT",
            f"event={event.event_type} ex_date={event.ex_date} price_date={day}",
        )
    return volume * event_volume_factor(event)


def adjust_price(
    raw_price: float, price_date: date, events: Sequence[CorporateAction]
) -> float:
    """Back-adjust a pre-event price with the events still pending for it.

    Every supplied event must satisfy ``ex_date > price_date`` (it must be
    OUT OF WINDOW otherwise — a factor already embedded in the quoted price
    must never be reapplied) and the sequence must be strictly ascending by
    ex_date. Refuses ``ANACHRONISTIC_ADJUSTMENT`` for out-of-window events,
    ``UNORDERED_EX_DATES`` / ``DUPLICATE_EX_DATE`` for unordered input, and
    ``MIXED_SYMBOL_COMPOSITION`` for cross-symbol input.
    """
    day = _plain_date(price_date, "price_date")
    price = _finite_positive(raw_price, "price")
    if price < 0:
        raise CorporateActionError("PRICE_NEGATIVE", f"value={raw_price!r}")
    ordered = _require_ascending_same_symbol(events)
    for event in ordered:
        if event.ex_date <= day:
            raise CorporateActionError(
                "ANACHRONISTIC_ADJUSTMENT",
                f"event={event.event_type} ex_date={event.ex_date} price_date={day}",
            )
    factor = 1.0
    for event in ordered:
        factor *= event_price_factor(event)
    return price * factor


def adjust_volume(
    raw_volume: float, price_date: date, events: Sequence[CorporateAction]
) -> float:
    """Back-adjust a pre-event volume; same chronology/window rules as adjust_price."""
    day = _plain_date(price_date, "price_date")
    volume = _finite_positive(raw_volume, "volume")
    if volume < 0:
        raise CorporateActionError("VOLUME_NEGATIVE", f"value={raw_volume!r}")
    ordered = _require_ascending_same_symbol(events)
    for event in ordered:
        if event.ex_date <= day:
            raise CorporateActionError(
                "ANACHRONISTIC_ADJUSTMENT",
                f"event={event.event_type} ex_date={event.ex_date} price_date={day}",
            )
    factor = 1.0
    for event in ordered:
        factor *= event_volume_factor(event)
    return volume * factor


class PitApplicability(BaseModel):
    """Frozen PIT verdict for one event against one explicit query date."""

    model_config = ConfigDict(frozen=True)

    status: PitStatus
    applicable: bool
    reason_code: str = Field(min_length=1)
    query_date: date
    ex_date: date
    announce_date: date | None = None


def pit_applicability(event: CorporateAction, query_date: date) -> PitApplicability:
    """Publish-time PIT gate (module docstring, discipline 2).

    Order of determination (deterministic precedence):
    1. ``query_date < ex_date``                → BEFORE_EX_DATE (not in effect)
    2. ``announce_date is None``               → APPLICABLE_ANNOUNCE_UNKNOWN
       (applicable BY ex-date, but the applicability claim carries NO
       publication evidence — the honest unknown)
    3. ``query_date < announce_date``          → NOT_YET_PUBLIC (refusal tag;
       using the event at query_date would be publish-time look-ahead)
    4. otherwise                               → APPLICABLE_ANNOUNCE_KNOWN
    """
    day = _plain_date(query_date, "query_date")
    if day < event.ex_date:
        return PitApplicability(
            status="BEFORE_EX_DATE",
            applicable=False,
            reason_code="query_before_ex_date_factor_not_in_effect",
            query_date=day,
            ex_date=event.ex_date,
            announce_date=event.announce_date,
        )
    if event.announce_date is None:
        return PitApplicability(
            status="APPLICABLE_ANNOUNCE_UNKNOWN",
            applicable=True,
            reason_code="announce_date_unknown_honest_unknown",
            query_date=day,
            ex_date=event.ex_date,
            announce_date=None,
        )
    if day < event.announce_date:
        return PitApplicability(
            status="NOT_YET_PUBLIC",
            applicable=False,
            reason_code="query_before_announce_date",
            query_date=day,
            ex_date=event.ex_date,
            announce_date=event.announce_date,
        )
    return PitApplicability(
        status="APPLICABLE_ANNOUNCE_KNOWN",
        applicable=True,
        reason_code="event_public_and_in_effect_at_query_date",
        query_date=day,
        ex_date=event.ex_date,
        announce_date=event.announce_date,
    )


def require_pit_usable(event: CorporateAction, query_date: date) -> PitApplicability:
    """Same verdict, refuse-and-raise form: only the applicable paths return.

    Raises ``CorporateActionError`` with the stable refusal tags
    ``NOT_YET_PUBLIC`` / ``BEFORE_EX_DATE`` on the non-applicable paths.
    """
    verdict = pit_applicability(event, query_date)
    if not verdict.applicable:
        raise CorporateActionError(
            verdict.status,
            f"{verdict.reason_code} ex_date={event.ex_date} "
            f"announce={event.announce_date} query={verdict.query_date}",
        )
    return verdict
