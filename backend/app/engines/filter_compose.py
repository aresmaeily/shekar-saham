"""Filter-Compose continuation engine (D-O2 approved additive implementation).

Reuse policy (approved continuation spec §1, binding): the ONLY expression
substrate is the existing safe Filter DSL (``backend/app/engines/filter_dsl.py``).
This module adds composition semantics on top — it never re-implements
validation or evaluation and never widens the grammar beyond the bounded
``market_*`` runtime-field registry registered once, below.

Lineage / provenance honesty:
  * The eight composed filters and their expressions come from the RECOVERED
    research documentation (TABLOKHANI_WORKSTREAM_PACKAGE_2026-11-14,
    ``TABLOKHANI_FILTER_FORMULAS_AND_SEMANTICS.md`` §2, verified 2026-11-15),
    not from reconstructed source code. The lost implementation commits
    (``97da840`` / ``4ce812e``) remain unrecovered Git objects; this module is
    an independent, reviewable implementation of the same DOCUMENTED semantics.
  * Every filter carries one of exactly four provenance classes
    (DOCUMENTED_PUBLIC_SEMANTICS / RADAR_NATIVE / INDEPENDENT_PROPOSAL /
    CUSTOM_OPERATOR_INPUT) plus a rationale that records deliberate deviations
    (e.g. the inclusive 0.6 threshold, the 30d window vs the reference 3d/14d).

Governance (unchanged): read-only over the market row cache; no scheduler, no
AI-2 path, no egress, no broker/order surface, no trust-label upgrading — the
``data_trust`` envelope is passed through verbatim by the API layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.engines.filter_dsl import (
    FIELD_ALIASES,
    FilterError,
    _execution_context,
    _SafeEval,
    parse_filter,
    register_runtime_fields,
)

# --- market-relative context (spec §7) --------------------------------------
# Numeric-only, strictly-namespaced runtime fields. Registered ONCE at import
# (no per-request registry mutation, no race). The compose engine injects the
# numeric value into every evaluated row; "enrichment off" is represented as
# the value 0.0 with an explicit degenerate disclosure — never by removing the
# field (that would silently change the documented degenerate semantics).
register_runtime_fields(
    {
        "market_buy_per_capita": "میانگین سرانه خرید کل جهان‌نماد ارزیابی‌شده (تومان، شامل صفرها)",
    }
)

# --- composed filter catalog (recovered documentation §2.1–2.8) --------------

PROVENANCE_CLASSES = (
    "DOCUMENTED_PUBLIC_SEMANTICS",
    "RADAR_NATIVE",
    "INDEPENDENT_PROPOSAL",
    "CUSTOM_OPERATOR_INPUT",
)

COMPOSE_FILTERS: tuple[dict[str, str], ...] = (
    {
        "filter_id": "hot_money",
        "name_fa": "پول داغ (خرید)",
        "name_en": "Hot money (buy)",
        "category": "hot_money",
        "expr": "buy_per_capita >= 200000000",
        "provenance": "DOCUMENTED_PUBLIC_SEMANTICS",
        "rationale": (
            "آستانه سرانه خرید ≥۲۰۰ میلیون تومان متنیِ منتشرشدهٔ مرجع است. مرز ۲۰۰M "
            "شمولی و باند بالایی انحصاری است (پارتیشن مستند پول داغ / پول داغ پلاس)."
        ),
    },
    {
        "filter_id": "sus_volume",
        "name_fa": "حجم مشکوک",
        "name_en": "Suspicious volume",
        "category": "flow",
        "expr": "volume_ratio >= 3",
        "provenance": "INDEPENDENT_PROPOSAL",
        "rationale": (
            "ستون «حجم ۳روزه به ۱۴روزه» مرجع مستند است؛ آستانه ۳× نسبت حجم به میانگین "
            "۳۰روزه یک انتخاب مهندسی مستقل RADAR است. انحراف پنجره (۳۰روزه در برابر "
            "۳d/۱۴d مرجع) عمداً و صریحاً ثبت شده است."
        ),
    },
    {
        "filter_id": "legal_sell_retail_buy",
        "name_fa": "کد به کد حقیقی‌خرید / حقوقی‌فروش",
        "name_en": "Legal-to-retail transfer (60/60)",
        "category": "ownership",
        "expr": (
            "Buy_I_Volume > 0 and "
            "Buy_I_Volume/(Buy_I_Volume+Buy_N_Volume) >= 0.6 and "
            "Sell_N_Volume/(Sell_N_Volume+Sell_I_Volume) >= 0.6"
        ),
        "provenance": "DOCUMENTED_PUBLIC_SEMANTICS",
        "rationale": (
            "قاعدهٔ اصلی کد به کد (خرید حقیقی، فروش حقوقی) مستند است. آستانه ۰٫۶ "
            "شمولی یک انحراف آگاهانه از قرائت اکید «بالای ۶۰» مرجع است تا مرزهای "
            "گرد کردن عدد صحیح سیگنال جعلی نسازند؛ در rationale ثبت و با تست پین شده است. "
            "شرایط اضافهٔ مرجع (باند اندازهٔ بازار، ۱٫۵× سرانه بازار، قدرت >۲، ۲–۳× "
            "حجم ۱۰روزه) به فیلترهای جداگانهٔ قابل‌ترکیب منتقل یا صریحاً پیاده‌نشده "
            "ثبت شده‌اند."
        ),
    },
    {
        "filter_id": "per_capita_vs_market",
        "name_fa": "سرانه خرید ≥ ۱٫۵× میانگین بازار",
        "name_en": "Per-capita vs market mean",
        "category": "flow",
        "expr": "buy_per_capita >= 1.5 * market_buy_per_capita",
        "provenance": "DOCUMENTED_PUBLIC_SEMANTICS",
        "rationale": (
            "قاعدهٔ ۱٫۵× میانگین بازار مستند است؛ تعریف «کل بازار» در این موتور = "
            "جهان‌نمادِ ارزیابی‌شده (میانگین حسابی شامل صفرها) — تعریفی مهندسی و "
            "صریح (برچسب INDEPENDENT در مولفهٔ تعریف). حالت degenerate (میانگین صفر "
            "⇒ تطبیق همهٔ ردیف‌ها) مستند و با تست پین شده است و هرگز سیگنال بازار "
            "خوانده نمی‌شود."
        ),
    },
    {
        "filter_id": "buy_queue",
        "name_fa": "صف خرید",
        "name_en": "Buy queue",
        "category": "board",
        "expr": "in_buy_queue == 1",
        "provenance": "RADAR_NATIVE",
        "rationale": (
            "مفهوم صف خرید در مرجع مستند است (شمارش صف خرید/فروش)؛ گزارهٔ دقیق صف "
            "منتشر نشده — پرچم in_buy_queue پیاده‌سازی مستقل RADAR با تست درون-مخزنی است."
        ),
    },
    {
        "filter_id": "smart_inflow_red_board",
        "name_fa": "ورود پول در تابلو منفی",
        "name_en": "Smart inflow on red board",
        "category": "board",
        "expr": "plp <= 0 and individual_net_value > 0 and volume_ratio >= 2",
        "provenance": "RADAR_NATIVE",
        "rationale": (
            "چشمهٔ شکارِ پیش از حرکت خانوادهٔ hunt champion در RADAR؛ قاعدهٔ مرجع "
            "منتشر نشده است (RADAR_NATIVE با تست درون-مخزنی)."
        ),
    },
    {
        "filter_id": "hot_money_plus",
        "name_fa": "پول داغ پلاس",
        "name_en": "Hot money plus",
        "category": "hot_money",
        "expr": "buy_per_capita >= 100000000 and buy_per_capita < 200000000",
        "provenance": "DOCUMENTED_PUBLIC_SEMANTICS",
        "rationale": (
            "باند ۱۰۰–۲۰۰ میلیون تومان متنیِ منتشرشدهٔ مرجع است؛ پایین شمولی، بالا "
            "انحصاری؛ در مرز ۲۰۰M فقط hot_money فعال می‌شود (تست‌پین‌شده)."
        ),
    },
    {
        "filter_id": "retail_exit",
        "name_fa": "خروج پول حقیقی",
        "name_en": "Retail money exit",
        "category": "ownership",
        "expr": "individual_net_value < 0 and sell_per_capita >= 100000000",
        "provenance": "INDEPENDENT_PROPOSAL",
        "rationale": (
            "مرجع هشدار «خروج پول حقیقی» را تبلیغ می‌کند اما هیچ قاعده‌ای منتشر "
            "نکرده است. این قاعده (خالص حقیقی منفی + سرانه فروش ≥۱۰۰M به قرضِ مقیاس "
            "باند پول‌داغ‌پلاس در سمت فروش) یک پیشنهاد مهندسی مستقل است، نه معادلِ "
            "مستند مرجع."
        ),
    },
)

COMPOSE_FILTERS_BY_ID: dict[str, dict[str, str]] = {f["filter_id"]: f for f in COMPOSE_FILTERS}

RANKING_RULE = "match_count desc → golden_number desc → entry_score desc → symbol asc"

UNSUPPORTED_DISCLOSURE = {
    "composition_level_and_or": (
        "NOT_SUPPORTED — ترکیب سطح‌دوم AND/OR/NOT و وزن‌دهی، رفتار مستندِ مرجع نیست "
        "(فقط شمارش عطفی) و طبق مشخصهٔ مصوب §5.6 به بستهٔ تصمیم مالک موکول شده است."
    ),
    "historical_array_dialect": (
        "NOT_SUPPORTED — گویش تاریخی [ih]/[it]/[ic] مرجع عمداً پذیرفته نشده (GM-8)."
    ),
}


class ComposeValidationError(ValueError):
    """Caller-facing validation failure (API maps to HTTP 400)."""


class UnknownFilterError(ComposeValidationError):
    def __init__(self, filter_id: str) -> None:
        super().__init__(f"شناسهٔ فیلتر ناشناخته: {filter_id}")
        self.filter_id = filter_id


@dataclass(frozen=True)
class _CompiledFilter:
    """One composed filter unit (preset definition or operator expression)."""

    filter_id: str
    name_fa: str
    provenance: str
    expr_raw: str
    is_custom: bool
    tree: Any = None
    fields: tuple[str, ...] = ()
    error: str | None = None


def _resolve_expressions(
    filter_ids: Iterable[str] | None, exprs: Iterable[str] | None
) -> list[_CompiledFilter]:
    """Resolve + compile the composed filter set.

    Evaluation order (deterministic regardless of request ordering): requested
    preset filters in CATALOG definition order, then custom expressions in
    request order. A compile error is RECORDED per filter (never silent, never
    fatal to the board) per the approved spec §5.2.
    """
    ids = list(filter_ids or [])
    custom = list(exprs or [])
    if len(ids) > 32:
        raise ComposeValidationError("حداکثر ۳۲ فیلتر نام‌دار مجاز است")
    if len(custom) > 16:
        raise ComposeValidationError("حداکثر ۱۶ عبارت سفارشی مجاز است")
    if not ids and not custom:
        # Documented reference behavior (B-6): the multidimensional board runs
        # the whole 8-filter catalog when no explicit selection is supplied.
        ids = [d["filter_id"] for d in COMPOSE_FILTERS]

    seen: set[str] = set()
    unknown = [i for i in ids if i not in COMPOSE_FILTERS_BY_ID]
    if unknown:
        raise UnknownFilterError(unknown[0])

    units: list[_CompiledFilter] = []
    for definition in COMPOSE_FILTERS:  # definition order, not request order
        fid = definition["filter_id"]
        if fid not in ids or fid in seen:
            continue
        seen.add(fid)
        try:
            compiled = parse_filter(definition["expr"])
            units.append(
                _CompiledFilter(fid, definition["name_fa"], definition["provenance"], definition["expr"], False, compiled.tree, compiled.fields)
            )
        except FilterError as exc:
            units.append(_CompiledFilter(fid, definition["name_fa"], definition["provenance"], definition["expr"], False, error=str(exc)))
    for n, expr in enumerate(custom, start=1):
        fid = f"custom_{n}"
        try:
            compiled = parse_filter(expr)
            units.append(_CompiledFilter(fid, fid, "CUSTOM_OPERATOR_INPUT", expr, True, compiled.tree, compiled.fields))
        except FilterError as exc:
            units.append(_CompiledFilter(fid, fid, "CUSTOM_OPERATOR_INPUT", expr, True, error=str(exc)))
    return units


def market_buy_per_capita(rows: list[dict[str, Any]]) -> float:
    """Arithmetic mean of buy_per_capita over the evaluated universe.

    Zero rows (real rows with no retail buying) are INCLUDED. An empty
    universe resolves to 0.0. The value is numeric-only by construction.
    """
    values: list[float] = []
    for r in rows:
        v = r.get("buy_per_capita")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            values.append(float(v))
    if not values:
        return 0.0
    return sum(values) / len(values)


def _enrich_rows(rows: list[dict[str, Any]], mkt: float) -> list[dict[str, Any]]:
    """Read-only enrichment: returns COPIES with the numeric market context.

    The market row cache is never mutated (spec §2). Rows with a blank symbol
    are dropped here once (spec §5.4): they are never ranked, never counted.
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        symbol = str(r.get("symbol") or "").strip()
        if not symbol:
            continue
        copy = dict(r)
        copy["symbol"] = symbol
        copy["market_buy_per_capita"] = mkt
        out.append(copy)
    return out


def _missing_fields(unit: _CompiledFilter, row: dict[str, Any]) -> list[str]:
    """Fields referenced by the filter that are absent/None on this row.

    Missing data is never coerced to 0/false to fabricate a negative match
    (spec §8): the (filter,row) pair is marked erroneous and contributes no
    match. Aliases are resolved exactly like the evaluator resolves them.
    """
    missing: list[str] = []
    for f in unit.fields:
        key = FIELD_ALIASES.get(f, f)
        if row.get(key) is None:
            missing.append(f)
    return missing


def compose_filters(
    rows: list[dict[str, Any]],
    *,
    filter_ids: list[str] | None = None,
    exprs: list[str] | None = None,
    min_matches: int = 1,
    limit: int = 50,
) -> dict[str, Any]:
    """Compose the catalog/custom filters over a board and rank by match count.

    Deterministic: pure function of (rows, params); no wall clock, no RNG,
    no store mutation. Raises ComposeValidationError/UnknownFilterError on bad
    parameters (API → 400). Per-filter errors are recorded, not silent.
    """
    if not isinstance(min_matches, int) or isinstance(min_matches, bool) or not (1 <= min_matches <= 8):
        raise ComposeValidationError("min_matches باید عدد صحیح در بازهٔ ۱ تا ۸ باشد")
    if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= 200):
        raise ComposeValidationError("limit باید عدد صحیح در بازهٔ ۱ تا ۲۰۰ باشد")

    units = _resolve_expressions(filter_ids, exprs)
    mkt = market_buy_per_capita(rows)
    enriched = _enrich_rows(rows, mkt)

    per_filter_stats: dict[str, int] = {u.filter_id: 0 for u in units}
    per_filter_row_errors: dict[str, int] = {u.filter_id: 0 for u in units}
    matched_by_symbol: dict[str, list[str]] = {}
    row_meta: dict[str, dict[str, Any]] = {}

    for row in enriched:
        hits: list[str] = []
        for unit in units:
            if unit.error is not None:
                continue  # compile-time error already recorded; contributes zero matches
            missing = _missing_fields(unit, row)
            if missing:
                per_filter_row_errors[unit.filter_id] += 1
                continue
            try:
                ok = bool(_SafeEval(_execution_context(row)).visit(unit.tree))
            except FilterError:
                per_filter_row_errors[unit.filter_id] += 1
                continue
            except Exception:  # noqa: BLE001 — defensive, recorded honestly
                per_filter_row_errors[unit.filter_id] += 1
                continue
            if ok:
                hits.append(unit.filter_id)
                per_filter_stats[unit.filter_id] += 1
        if hits:
            matched_by_symbol[row["symbol"]] = hits
            row_meta[row["symbol"]] = row

    # ranking: match_count desc → golden_number desc → entry_score desc → symbol asc
    def _num_or_zero(v: Any) -> float:
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0

    ranked = sorted(
        matched_by_symbol.keys(),
        key=lambda s: (
            -len(matched_by_symbol[s]),
            -_num_or_zero(row_meta[s].get("golden_number")),
            -_num_or_zero(row_meta[s].get("entry_score")),
            s,
        ),
    )
    shortlist = [s for s in ranked if len(matched_by_symbol[s]) >= min_matches]
    results = []
    for s in shortlist[:limit]:
        row = row_meta[s]
        results.append(
            {
                "symbol": s,
                "name": row.get("name"),
                "industry": row.get("industry"),
                "plp": row.get("plp"),
                "pcp": row.get("pcp"),
                "golden_number": row.get("golden_number"),
                "entry_score": row.get("entry_score"),
                "match_count": len(matched_by_symbol[s]),
                "matched": [
                    {"filter_id": fid, "name_fa": next(u.name_fa for u in units if u.filter_id == fid)}
                    for fid in matched_by_symbol[s]
                ],
            }
        )

    filters_payload = []
    id_order = {u.filter_id: i for i, u in enumerate(units)}
    for fid in sorted(per_filter_stats, key=lambda k: id_order[k]):
        unit = next(u for u in units if u.filter_id == fid)
        err = unit.error
        if err is None and per_filter_row_errors[fid]:
            err = f"{per_filter_row_errors[fid]} ردیف به‌دلیل دادهٔ مفقود/ناموجود ارزیابی نشد (fail-closed)"
        filters_payload.append(
            {
                "filter_id": fid,
                "name_fa": unit.name_fa,
                "provenance": unit.provenance,
                "expr": unit.expr_raw,
                "is_custom": unit.is_custom,
                "matched_count": per_filter_stats[fid],
                "error": err,
            }
        )

    return {
        "ok": True,
        "min_matches": min_matches,
        "limit": limit,
        "symbols_evaluated": len(enriched),
        "symbols_matched": len(shortlist),
        "total_matched": sum(per_filter_stats.values()),
        "market_context": {
            "market_buy_per_capita": mkt,
            "universe_size": len(enriched),
            "degenerate": mkt == 0.0,
            "degenerate_note": (
                "میانگین بازار صفر است؛ آستانهٔ ۱٫۵×۰ یعنی سرانهٔ خریدِ هر ردیفی با آن "
                "مقایسه می‌شود — این حالت سیگنال بازار نیست و صریحاً افشا می‌شود."
                if mkt == 0.0
                else None
            ),
        },
        "ranking_rule": RANKING_RULE,
        "filters": filters_payload,
        "results": results,
        "unsupported": UNSUPPORTED_DISCLOSURE,
    }


def compose_presets() -> list[dict[str, str]]:
    """Preset definitions for the API/UI (defensive copies)."""
    return [dict(f) for f in COMPOSE_FILTERS]
