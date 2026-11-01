"""Cross-provider quote-conflict detection (paper).

P1/P2 scope (02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 18-25, 133-142):
trusted market data must treat conflicting figures across sources as explicit,
surfaced contradictions — never silently reconciled — and syndicated copies
must not be mistaken for independent corroboration (06 charter §3.3-3.4;
D-AI-33).

Row input contract (composes app.models.schemas.SymbolSnapshot verbatim):
- a pydantic snapshot is read as  symbol <- l18, isin <- isin,
  last_price <- pl  (the exact SymbolSnapshot field names);
- a plain Mapping row is read as  symbol <- "symbol" or "l18",
  isin <- "isin", last_price <- "last_price" or "pl";
- `isin` may be empty/missing (symbol fallback matching); `last_price` must be
  a positive finite decimal-representable number (fail-closed refusal
  otherwise — a zero/unknown price is never treated as a quote).

Matching across sources: two rows match when both have non-empty isin and the
isin values are equal (match key ISIN), or when at least one isin is missing
and the symbols are equal (match key SYMBOL). Rows whose non-empty isins
differ never match, even when their symbols are equal. The match key used is
recorded on every emitted record.

Syndication vs conflict (06 charter §3.3): evidence.py's CorroborationStatus
vocabulary distinguishes SYNDICATED_COPY from CONFLICTING. Identical prices
from two sources of the same declared origin family are NOT conflicts (no
EvidenceConflict is emitted); `detect_syndicated_copies` reports such pairs
with the schema's exact SYNDICATED_COPY corroboration status. Divergent prices
remain CONFLICTING (an open EvidenceConflict) even within one origin family —
syndication never excuses divergence.

Contract/domain only: no network, no I/O, no clock reads. Timestamps are
always injected; "future as_of" is only judgeable against an explicitly
injected reference instant (`now_utc`), never against a wall clock.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, EvidenceConflict, _finite_decimal, ensure_utc

__all__ = [
    "MatchKey",
    "QuoteRow",
    "SyndicatedCopyPair",
    "detect_quote_conflicts",
    "detect_syndicated_copies",
]

MatchKey = Literal["ISIN", "SYMBOL"]


class QuoteRow(BaseModel):
    """Normalized view of one board row (snapshot or dict) — internal record."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    isin: str = ""
    last_price: Decimal


class SyndicatedCopyPair(BaseModel):
    """Identical quote carried by two sources of the same origin family.

    `corroboration_status` reuses the exact evidence.py CorroborationStatus
    value SYNDICATED_COPY: a copy is not independent corroboration and is not
    a conflict either.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    symbol: str = Field(min_length=1)
    isin: str = ""
    match_key: MatchKey
    source_a: str = Field(min_length=1)
    source_b: str = Field(min_length=1)
    corroboration_status: Literal["SYNDICATED_COPY"] = "SYNDICATED_COPY"
    observed_as_of_utc: datetime
    notes: str = ""

    @field_validator("observed_as_of_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _consistency(self) -> "SyndicatedCopyPair":
        if self.source_a == self.source_b:
            raise ValueError("syndicated_pair_sources_must_differ")
        if self.source_a > self.source_b:
            raise ValueError("syndicated_pair_sources_must_be_canonically_ordered")
        return self


def _row_view(source_id: str, row: Any) -> QuoteRow:
    """Normalize one snapshot-or-dict row; fail-closed refusals, no guessing."""
    if isinstance(row, Mapping):
        symbol = None
        for key in ("symbol", "l18"):
            if key in row:
                symbol = row[key]
                break
        isin = row.get("isin") or ""
        price_raw = None
        for key in ("last_price", "pl"):
            if key in row:
                price_raw = row[key]
                break
        if symbol is None:
            raise ValueError("row_symbol_missing")
        if price_raw is None:
            raise ValueError("row_last_price_missing")
    elif isinstance(row, BaseModel):
        # SymbolSnapshot mapping (verbatim field names): l18 -> symbol,
        # isin -> isin, pl -> last_price.
        symbol = getattr(row, "l18", None)
        isin = getattr(row, "isin", "") or ""
        price_raw = getattr(row, "pl", None)
        if symbol is None:
            raise ValueError("row_symbol_missing")
        if price_raw is None:
            raise ValueError("row_last_price_missing")
    else:
        raise ValueError("row_must_be_mapping_or_pydantic_model")
    symbol = str(symbol).strip()
    if not symbol:
        raise ValueError("row_symbol_must_not_be_empty")
    try:
        price = _finite_decimal(price_raw)
    except ValueError as exc:
        raise ValueError("row_last_price_not_decimal_representable") from exc
    if price <= 0:
        raise ValueError("row_last_price_must_be_positive")
    return QuoteRow(source_id=source_id, symbol=symbol, isin=str(isin).strip(), last_price=price)


def _normalize_boards(
    boards_by_source: Mapping[str, Sequence[Any]],
) -> list[tuple[str, list[QuoteRow]]]:
    if not isinstance(boards_by_source, Mapping):
        raise ValueError("boards_by_source_must_be_mapping")
    if len(boards_by_source) == 0:
        raise ValueError("boards_by_source_must_not_be_empty")
    boards: list[tuple[str, list[QuoteRow]]] = []
    for source_id in sorted(boards_by_source):
        rows = boards_by_source[source_id]
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise ValueError("board_rows_must_be_sequence")
        if len(rows) == 0:
            raise ValueError(f"board_for_source_must_not_be_empty: {source_id}")
        seen: set[tuple[str, str]] = set()
        normalized: list[QuoteRow] = []
        for row in rows:
            view = _row_view(source_id, row)
            identity = (view.isin, view.symbol)
            if identity in seen:
                raise ValueError(f"duplicate_identity_within_source: {source_id}:{view.symbol}")
            seen.add(identity)
            normalized.append(view)
        boards.append((source_id, normalized))
    return boards


def _matched_pairs(
    boards: list[tuple[str, list[QuoteRow]]],
) -> list[tuple[str, QuoteRow, str, QuoteRow, MatchKey, str]]:
    """Cross-source matched pairs, canonically ordered (source_a < source_b).

    Returns tuples (source_a, row_a, source_b, row_b, match_key, identity_value).
    """
    pairs: list[tuple[str, QuoteRow, str, QuoteRow, MatchKey, str]] = []
    all_rows: list[QuoteRow] = [r for _, rows in boards for r in rows]
    # ISIN matches: both isins present and equal.
    by_isin: dict[str, list[QuoteRow]] = {}
    for row in all_rows:
        if row.isin:
            by_isin.setdefault(row.isin, []).append(row)
    for isin in sorted(by_isin):
        group = by_isin[isin]
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a.source_id == b.source_id:
                    continue
                lo, hi = (a, b) if a.source_id < b.source_id else (b, a)
                pairs.append((lo.source_id, lo, hi.source_id, hi, "ISIN", isin))
    # Symbol fallback matches: at least one isin missing, symbols equal.
    by_symbol: dict[str, list[QuoteRow]] = {}
    for row in all_rows:
        by_symbol.setdefault(row.symbol, []).append(row)
    for symbol in sorted(by_symbol):
        group = by_symbol[symbol]
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a.source_id == b.source_id:
                    continue
                if a.isin and b.isin:
                    continue  # both isins known: only ISIN matching applies
                lo, hi = (a, b) if a.source_id < b.source_id else (b, a)
                pairs.append((lo.source_id, lo, hi.source_id, hi, "SYMBOL", symbol))
    return pairs


def _parse_tol(tol_pct: Any) -> Decimal:
    if isinstance(tol_pct, bool) or not isinstance(tol_pct, (int, float, str, Decimal)):
        raise ValueError("tol_pct_must_be_number")
    try:
        tol = _finite_decimal(tol_pct)
    except ValueError as exc:
        raise ValueError("tol_pct_not_decimal_representable") from exc
    if tol <= 0:
        raise ValueError("tol_pct_must_be_positive")
    return tol


def detect_quote_conflicts(
    boards_by_source: Mapping[str, Sequence[Any]],
    *,
    tol_pct: Any,
    as_of_utc: datetime,
    now_utc: datetime | None = None,
) -> list[EvidenceConflict]:
    """Detect cross-provider last-price conflicts as OPEN EvidenceConflicts.

    Divergence is |a-b| * 100 / min(a, b) in percent (relative to the lower
    price — the conservative reading that maximizes detected divergence). A
    pair is a conflict only when divergence is STRICTLY greater than tol_pct;
    the borderline case (divergence == tol_pct) is not a conflict.

    Refusals (ValueError reason codes, never a silent empty result):
    - boards_by_source_must_be_mapping / _must_not_be_empty
    - board_for_source_must_not_be_empty: <source>
    - duplicate_identity_within_source: <source>:<symbol>
    - row_symbol_missing / row_symbol_must_not_be_empty
    - row_last_price_missing / _not_decimal_representable / _must_be_positive
    - tol_pct_must_be_number / _not_decimal_representable / _must_be_positive
    - as_of_must_be_timezone_aware (via shared ensure_utc vocabulary)
    - now_utc_must_be_timezone_aware / as_of_must_not_be_in_future
      ("future" is only judgeable against the injected now_utc; when now_utc
      is None this check is not performed — no wall clock is ever read)

    Ordering: deterministic, by (symbol, source_a, source_b).
    """
    as_of = ensure_utc(as_of_utc)
    if now_utc is not None:
        now = ensure_utc(now_utc)
        if as_of > now:
            raise ValueError("as_of_must_not_be_in_future")
    tol = _parse_tol(tol_pct)
    boards = _normalize_boards(boards_by_source)

    staged: list[tuple[str, str, str, EvidenceConflict]] = []
    for source_a, row_a, source_b, row_b, match_key, identity in _matched_pairs(boards):
        divergence = abs(row_a.last_price - row_b.last_price) * 100 / min(
            row_a.last_price, row_b.last_price
        )
        if divergence <= tol:
            continue
        id_a = f"quote:{source_a}:{match_key}:{identity}:{row_a.symbol}"
        id_b = f"quote:{source_b}:{match_key}:{identity}:{row_b.symbol}"
        evidence_ids = tuple(sorted((id_a, id_b)))
        conflict_id = (
            "QC-" + sha256(f"{'|'.join(evidence_ids)}|{divergence}|{tol}".encode()).hexdigest()[:12]
        )
        conflict = EvidenceConflict(
            conflict_id=conflict_id,
            evidence_ids=evidence_ids,
            description=(
                f"Last price for {row_a.symbol} diverges across sources "
                f"{source_a} and {source_b}: {row_a.last_price} vs {row_b.last_price} "
                f"({divergence}% > tol {tol}%), matched by {match_key}, "
                f"observed as of {as_of.isoformat()}"
            ),
            status="OPEN",
            notes=f"match_key={match_key}; divergence_pct={divergence}; tol_pct={tol}",
        )
        staged.append((row_a.symbol, source_a, source_b, conflict))
    staged.sort(key=lambda item: (item[0], item[1], item[2]))
    return [conflict for _, _, _, conflict in staged]


def detect_syndicated_copies(
    boards_by_source: Mapping[str, Sequence[Any]],
    *,
    origin_family_by_source: Mapping[str, str],
    as_of_utc: datetime,
    now_utc: datetime | None = None,
) -> tuple[SyndicatedCopyPair, ...]:
    """Report identical quotes carried by sources of the same origin family.

    06 charter §3.3: copied syndications must not be mistaken for independent
    corroboration. A pair is a syndicated copy only when its prices are
    EXACTLY equal and both sources declare the same origin family. Divergent
    same-family pairs are NOT reported here — they remain conflicts of
    `detect_quote_conflicts`.
    """
    as_of = ensure_utc(as_of_utc)
    if now_utc is not None:
        if as_of > ensure_utc(now_utc):
            raise ValueError("as_of_must_not_be_in_future")
    if not isinstance(origin_family_by_source, Mapping):
        raise ValueError("origin_family_by_source_must_be_mapping")
    boards = _normalize_boards(boards_by_source)
    for source_id, _ in boards:
        if source_id not in origin_family_by_source:
            raise ValueError(f"origin_family_missing_for_source: {source_id}")

    copies: list[tuple[str, str, str, SyndicatedCopyPair]] = []
    for source_a, row_a, source_b, row_b, match_key, identity in _matched_pairs(boards):
        if row_a.last_price != row_b.last_price:
            continue
        if origin_family_by_source[source_a] != origin_family_by_source[source_b]:
            continue
        copy = SyndicatedCopyPair(
            symbol=row_a.symbol,
            isin=row_a.isin or row_b.isin,
            match_key=match_key,
            source_a=source_a,
            source_b=source_b,
            observed_as_of_utc=as_of,
            notes=f"identity={identity}; origin_family={origin_family_by_source[source_a]}",
        )
        copies.append((row_a.symbol, source_a, source_b, copy))
    copies.sort(key=lambda item: (item[0], item[1], item[2]))
    return tuple(copy for _, _, _, copy in copies)
