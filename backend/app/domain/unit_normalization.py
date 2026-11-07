"""Declared unit/currency normalization (WP-G / G2).

WAVE-AB4 (2026-11-08, directive §10 G2): unit+currency are MANDATORY on
REPORTED fundamental facts (fundamental_dossier validators) but no
normalization engine existed — values recorded as "میلیون ریال" and "ریال"
could not be compared deterministically. This module normalizes DECLARED
units to a canonical scale INSIDE ONE CURRENCY:

- Cross-currency conversion is structurally IMPOSSIBLE here (no FX table, no
  invented rates): the currency must be identical on both sides or the
  normalization refuses. Never invents missing data.
- Unknown units are refused, never guessed.
- The canonical unit of the money scale is ``RIAL``; the declared scale
  multipliers are exact integers.
- Percent-like units normalize to themselves (scale-free); dimensioned
  non-money units normalize to themselves.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Closed declared money-unit vocabulary (Iranian market declared units).
MoneyUnit = Literal[
    "RIAL",
    "THOUSAND_RIAL",
    "MILLION_RIAL",
    "BILLION_RIAL",
]

#: Scale-free units normalize to themselves (no dimension to collapse).
ScaleFreeUnit = Literal[
    "PERCENT",
    "SHARES",
    "COUNT",
    "RATIO",
    "TIMES",
]

DeclaredUnit = str  # validated against the closed tables at construction

_CANONICAL_MONEY_UNIT = "RIAL"

#: Exact integer multipliers toward the canonical money unit. Declared once;
#: deterministic forever.
_MONEY_SCALE: dict[str, int] = {
    "RIAL": 1,
    "THOUSAND_RIAL": 1_000,
    "MILLION_RIAL": 1_000_000,
    "BILLION_RIAL": 1_000_000_000,
}

_SCALE_FREE: frozenset[str] = frozenset(
    {"PERCENT", "SHARES", "COUNT", "RATIO", "TIMES"}
)

_KNOWN_UNITS: frozenset[str] = frozenset(_MONEY_SCALE) | _SCALE_FREE

#: Persian display aliases — DECLARED spellings only (no fuzzy matching).
_PERSIAN_ALIASES: dict[str, str] = {
    "ریال": "RIAL",
    "هزار ریال": "THOUSAND_RIAL",
    "میلیون ریال": "MILLION_RIAL",
    "میلیارد ریال": "BILLION_RIAL",
    "درصد": "PERCENT",
    "سهم": "SHARES",
    "نسبت": "RATIO",
    "برابر": "TIMES",
}


class DeclaredQuantity(BaseModel):
    """A declared, source-grounded quantity (value + unit + currency)."""

    model_config = ConfigDict(frozen=True)

    value: Decimal
    unit: str = Field(min_length=1, max_length=32)
    currency: str = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def _unit_known(self) -> "DeclaredQuantity":
        normalized = _PERSIAN_ALIASES.get(self.unit, self.unit)
        if normalized not in _KNOWN_UNITS:
            raise ValueError(f"unknown_unit:{self.unit[:32]}")
        object.__setattr__(self, "unit", normalized)
        # Persian-market declared quantities are RIAL-denominated; other
        # currencies are representable but cross-currency math refuses below.
        return self


class NormalizedQuantity(BaseModel):
    """The canonical-scale quantity plus the provenance of the transform."""

    model_config = ConfigDict(frozen=True)

    value: Decimal
    unit: str
    currency: str
    scale_factor_applied: int = Field(ge=1)
    source_unit: str


def normalize_quantity(q: DeclaredQuantity) -> NormalizedQuantity:
    """Normalize one declared quantity to the canonical money scale.

    Money units collapse to ``RIAL`` inside the SAME currency (exact integer
    multiplication). Scale-free units pass through with factor 1. Unknown
    units are refused at construction; nothing is guessed, nothing invented.
    """
    if q.unit in _MONEY_SCALE:
        factor = _MONEY_SCALE[q.unit]
        return NormalizedQuantity(
            value=q.value * factor,
            unit=_CANONICAL_MONEY_UNIT,
            currency=q.currency,
            scale_factor_applied=factor,
            source_unit=q.unit,
        )
    # scale-free
    return NormalizedQuantity(
        value=q.value,
        unit=q.unit,
        currency=q.currency,
        scale_factor_applied=1,
        source_unit=q.unit,
    )


def normalize_comparable(a: DeclaredQuantity, b: DeclaredQuantity) -> tuple[Decimal, Decimal]:
    """Make two declared quantities comparable — ONLY inside one currency.

    Cross-currency comparison refuses (``cross_currency_comparison_refused``):
    this module has no FX authority and will never invent a rate. Dimension
    mismatches (money vs scale-free) refuse too (``dimension_mismatch``).
    """
    na = normalize_quantity(a)
    nb = normalize_quantity(b)
    if na.currency != nb.currency:
        raise ValueError("cross_currency_comparison_refused")
    a_money = na.unit == _CANONICAL_MONEY_UNIT
    b_money = nb.unit == _CANONICAL_MONEY_UNIT
    if a_money != b_money:
        raise ValueError("dimension_mismatch")
    if na.unit != nb.unit:
        raise ValueError("incomparable_dimensions")
    return na.value, nb.value
