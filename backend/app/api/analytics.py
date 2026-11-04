"""analytics.py - WDA-3 (2026-11-02) — additive Iran-market analytics paths

Mounted next to the WS-10 chart-pro router on the same /api/v10 family.
STRICTLY ADDITIVE: no existing endpoint contract is changed; every value is
reused from existing services/engines — no new trust logic, no new math, no
network, no wall-clock dependency in the logic itself (the canonical trust
envelope is market_service.data_trust_context(), exactly like chart_pro).

Endpoints (all GET, prefix /api/v10/analytics):
- /search?q=&limit=          — normalized (Persian/Arabic-variant, ZWNJ, digits)
                              symbol search over the mock/synthetic universe
                              (same generator as /api/v10/chartpro/universe).
- /screener                  — parametric filtered view over the current snapshot.
                              Reuses the filter DSL through
                              market_service.run_user_filter (single source of
                              screener math) — no expression is evaluated here.
- /market-map                — industry/sector aggregate (counts, avg change,
                              value) from the EXISTING analysis.industries +
                              overview payload (IndustryFlow model reuse).
- /flow                      — market-flow summary reusing the big-moves path
                              (market_service.get_big_moves) + flow_meta from
                              market_service.status().
- /dossier/{l18}             — company/fundamental dossier from existing symbol
                              data (get_symbol + alert history). Unsupported
                              fields are explicit nulls with available:false and
                              a Persian reason — never fabricated.

Honesty contract: every response and every row/section carries the canonical
market_service trust envelope; SYNTHETIC-class values are labelled
"synthetic-seeded"/"synthetic" and nothing here can ever mint a "live" label.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.data.mock_market import generate_mock_market
from app.data.store import store
from app.services.market_service import market_service

router = APIRouter(prefix="/api/v10/analytics")


# ASSERT-STYLE: data_trust / trust_level MUST come from market_service.
# Hardcoding "live" (or any trust label) in this module is forbidden — the
# trust fields stay the canonical market_service verdict for the current
# runtime (same discipline as chart_pro._trust_envelope).
def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust": market_service.data_trust_context(),
        "trust_level": market_service.trust_level(),
    }


_SYNTHETIC_NOTE = (
    "داده‌های این پاسخ از کلاس SYNTHETIC/آزمایشی است و زنده نیست — مبنای خرید/فروش قرار ندهید"
)

# Persian/Arabic glyph folding for search: Arabic yeh/kaf -> Persian, ZWNJ and
# digit variants fold onto one canonical form. Search-matching concern only.
_FA_CHAR_MAP = {
    "ي": "ی",
    "ك": "ک",
    "ة": "ه",
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ؤ": "و",
    "\u200c": "",  # نیم‌فاصله — در مقایسه حذف می‌شود
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}
_FA_TRANS = str.maketrans(_FA_CHAR_MAP)


def _normalize_fa(text: str) -> str:
    folded = (text or "").strip().lower().translate(_FA_TRANS)
    return " ".join(folded.split())


def _match_rank(query: str, l18: str, l30: str) -> Optional[int]:
    """Prefix-first ranking over normalized fields (lower rank = better).

    Comparison keys are space-stripped on BOTH sides so that a query typed with
    a plain space ("های وب") matches a ZWNJ-carrying symbol ("های‌وب") whose
    normalization dropped the ZWNJ — no insertion-order luck involved.
    """
    q = _normalize_fa(query)
    if not q:
        return None
    sym = _normalize_fa(l18).replace(" ", "")
    name = _normalize_fa(l30).replace(" ", "")
    q = q.replace(" ", "")
    if q == sym:
        return 0
    if sym.startswith(q):
        return 1
    if q == name:
        return 1
    if name.startswith(q):
        return 2
    if q in sym or q in name:
        return 3
    return None


# ---------------------------------------------------------------------------
# GET /search — normalized symbol search over the synthetic universe
# ---------------------------------------------------------------------------

@router.get("/search")
async def analytics_search(
    q: str = Query("", min_length=0, max_length=64),
    limit: int = Query(20, ge=1, le=50),
) -> Dict[str, Any]:
    """Search the mock/synthetic universe (same seeded board as chartpro/universe).

    Persian/Arabic glyph variants, ZWNJ and digit forms are normalized on both
    sides; prefix matches rank before substring matches; results are capped.
    """
    envelope = _trust_envelope()
    query = _normalize_fa(q)
    ranked: List[Dict[str, Any]] = []
    for s in generate_mock_market():
        rank = _match_rank(query, s.l18, s.l30)
        if rank is None:
            continue
        ranked.append(
            {
                "rank": rank,
                "l18": s.l18,
                "l30": s.l30,
                "industry": s.cs,
                "pl": s.pl,
                "plp": s.plp,
                "pe": s.pe,
                "tval": s.tval,
                "market": "TSE",
                "source_class": "synthetic-seeded",
                "data_trust": envelope["data_trust"],
                "trust_level": envelope["trust_level"],
            }
        )
        if len(ranked) >= limit * 4:  # bounded over-ranking pool
            break
    ranked.sort(key=lambda r: r["rank"])
    results = [{k: v for k, v in row.items() if k != "rank"} for row in ranked[:limit]]
    return {
        "ok": True,
        "q": q,
        "normalized_query": query,
        "count": len(results),
        "results": results,
        "source": "synthetic-seeded",
        "note": _SYNTHETIC_NOTE,
        **envelope,
    }


# ---------------------------------------------------------------------------
# GET /screener — parametric filtered view (DSL composed, evaluated by the
# existing engine through market_service.run_user_filter)
# ---------------------------------------------------------------------------

_INDUSTRY_PATTERN = r"^[^'\"\\]+$"  # DSL-quoted string — no quote chars allowed
_SORT_PATTERN = "^(entry_score|plp|tval)$"


def _compose_screener_expr(
    min_plp: Optional[float],
    max_plp: Optional[float],
    min_tval: Optional[float],
    min_entry_score: Optional[float],
    industry: Optional[str],
) -> str:
    parts: List[str] = []
    if min_plp is not None:
        parts.append(f"plp >= {min_plp}")
    if max_plp is not None:
        parts.append(f"plp <= {max_plp}")
    if min_tval is not None:
        parts.append(f"tval >= {min_tval}")
    if min_entry_score is not None:
        parts.append(f"entry_score >= {min_entry_score}")
    if industry:
        parts.append(f"contains(industry, '{industry}')")
    # trivially-true baseline: matches every snapshot row without new math
    return " and ".join(parts) if parts else "entry_score >= 0"


@router.get("/screener")
async def analytics_screener(
    min_plp: Optional[float] = Query(None, ge=-100, le=100),
    max_plp: Optional[float] = Query(None, ge=-100, le=100),
    min_tval: Optional[float] = Query(None, ge=0),
    min_entry_score: Optional[float] = Query(None, ge=0, le=100),
    industry: Optional[str] = Query(None, min_length=1, max_length=64, pattern=_INDUSTRY_PATTERN),
    sort: str = Query("entry_score", pattern=_SORT_PATTERN),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Filtered view over the current snapshot — pure reuse of the filter DSL.

    The composed expression is validated and executed by the existing engine
    (engines.filter_dsl through market_service.run_user_filter); nothing is
    re-implemented here. Trust envelope rides on the same service result.
    """
    await market_service.get_analysis(force=False)
    expr = _compose_screener_expr(min_plp, max_plp, min_tval, min_entry_score, industry)
    result = market_service.run_user_filter(expr, limit=limit)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "خطای فیلتر")
    rows = result.get("rows") or []
    rows = sorted(rows, key=lambda r: (r.get(sort) if r.get(sort) is not None else 0), reverse=True)
    return {
        "ok": True,
        "expr": expr,
        "count": len(rows),
        "rows": rows,
        "filters": {
            "min_plp": min_plp,
            "max_plp": max_plp,
            "min_tval": min_tval,
            "min_entry_score": min_entry_score,
            "industry": industry,
            "sort": sort,
            "limit": limit,
        },
        "note": _SYNTHETIC_NOTE,
        "trust_level": result.get("trust_level") or market_service.trust_level(),
        "data_trust": result.get("data_trust") or market_service.data_trust_context(),
    }


# ---------------------------------------------------------------------------
# GET /market-map — industry/sector aggregates from existing analysis payload
# ---------------------------------------------------------------------------

_MAP_SORT_PATTERN = "^(total_value|avg_plp|score)$"


@router.get("/market-map")
async def analytics_market_map(
    sort: str = Query("total_value", pattern=_MAP_SORT_PATTERN),
    min_symbols: int = Query(1, ge=1, le=50),
    limit: int = Query(50, ge=1, le=100),
) -> Dict[str, Any]:
    """Aggregated industries/sectors view — counts and avg change per industry.

    Reuses the existing IndustryFlow aggregates from
    market_service.get_analysis() (no aggregation math is duplicated here).
    """
    analysis = await market_service.get_analysis(force=False)
    rows = [
        r.model_dump(mode="json")
        for r in analysis.industries
        if r.symbol_count >= min_symbols
    ]
    rows.sort(key=lambda r: (r.get(sort) if r.get(sort) is not None else 0), reverse=True)
    rows = rows[:limit]
    ov = analysis.overview
    return {
        "ok": True,
        "industry_count": len(rows),
        "symbol_count": ov.symbol_count,
        "positive_count": ov.positive_count,
        "negative_count": ov.negative_count,
        "total_value": ov.total_value,
        "industries": rows,
        "sort": sort,
        "min_symbols": min_symbols,
        "note": _SYNTHETIC_NOTE,
        **_trust_envelope(),
    }


# ---------------------------------------------------------------------------
# GET /flow — market-flow summary reusing the big-moves/flow metadata path
# ---------------------------------------------------------------------------

@router.get("/flow")
async def analytics_flow(
    window_sec: Optional[int] = Query(None, ge=60, le=7200),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Market-flow summary — reuse of market_service.get_big_moves + flow_meta.

    Counts and net sums are plain aggregations over the EXISTING big-moves rows
    (same engine output the /api/big-moves endpoint serves); no flow logic is
    re-implemented here.
    """
    await market_service.get_analysis(force=False)
    moves = market_service.get_big_moves(window_sec=window_sec, limit=300)
    flow_meta = market_service.status().get("flow_meta") or {}
    inflow = [m for m in moves if m.get("side") == "inflow"]
    outflow = [m for m in moves if m.get("side") == "outflow"]
    inflow_net = round(sum(float(m.get("delta_net_value") or 0) for m in inflow), 1)
    outflow_net = round(sum(float(m.get("delta_net_value") or 0) for m in outflow), 1)
    window = (moves[0].get("window_sec") if moves else None) or window_sec or flow_meta.get("window_sec")
    return {
        "ok": True,
        "window_sec": window,
        "moves_count": len(moves),
        "inflow_count": len(inflow),
        "outflow_count": len(outflow),
        "inflow_net_value": inflow_net,
        "outflow_net_value": outflow_net,
        "net_flow_value": round(inflow_net + outflow_net, 1),
        "coverage_sec": flow_meta.get("coverage_sec"),
        "sufficient": flow_meta.get("sufficient"),
        "top_moves": moves[:limit],
        "note": _SYNTHETIC_NOTE,
        **_trust_envelope(),
    }


# ---------------------------------------------------------------------------
# GET /dossier/{l18} — company/fundamental dossier (existing data only)
# ---------------------------------------------------------------------------

def _unsupported(name: str, reason: str, envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Explicit honest null — unsupported fields are never fabricated."""
    return {
        "available": False,
        "reason": reason,
        "data": None,
        **envelope,
    }


def _supported(payload: Dict[str, Any], envelope: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "available": True,
        "reason": "",
        "data": payload,
        **envelope,
    }


@router.get("/dossier/{l18}")
async def analytics_dossier(l18: str) -> Dict[str, Any]:
    """Company/fundamental dossier from EXISTING data structures only.

    Sections are built from market_service.get_symbol() (snapshot + metrics +
    tablocastic + synthetic-marked fundamental) and the persisted alert history.
    Fields with no backing data structure in this product (dividends, corporate
    events/news, shareholders, analyst target price, holiday-calendar
    membership) are explicit nulls with available:false + reason — never guessed.
    """
    data = market_service.get_symbol(l18)
    if not data:
        await market_service.get_analysis(force=False)
        data = market_service.get_symbol(l18)
    if not data:
        raise HTTPException(status_code=404, detail=f"نماد {l18} یافت نشد")

    envelope = _trust_envelope()
    s = data.get("snapshot") or {}
    tc = data.get("tablocastic") or {}
    fund = data.get("fundamental") or {}

    sections: Dict[str, Dict[str, Any]] = {
        "identity": _supported(
            {
                "l18": s.get("l18"),
                "name": s.get("l30"),
                "isin": s.get("isin"),
                "instrument_id": s.get("id"),
                "industry": s.get("cs"),
                "industry_id": s.get("cs_id"),
                "market": "TSE",
            },
            envelope,
        ),
        "price_snapshot": _supported(
            {
                "pl": s.get("pl"),
                "plc": s.get("plc"),
                "plp": s.get("plp"),
                "pc": s.get("pc"),
                "pcp": s.get("pcp"),
                "py": s.get("py"),
                "day_low": s.get("pmin"),
                "day_high": s.get("pmax"),
                "limit_low": s.get("tmin"),
                "limit_high": s.get("tmax"),
                "tvol": s.get("tvol"),
                "tval": s.get("tval"),
                "tno": s.get("tno"),
                "mv": s.get("mv"),
                "bvol": s.get("bvol"),
                "pe": s.get("pe"),
                "eps": s.get("eps"),
            },
            envelope,
        ),
        "tablo": _supported(
            {
                "d_plus": tc.get("d_plus"),
                "m_plus": tc.get("m_plus"),
                "golden_number": tc.get("golden_number"),
                "quality_score": tc.get("quality_score"),
                "grade": tc.get("grade"),
            },
            envelope,
        ),
        "fundamental": _supported(
            {
                # Synthetic statements — market_service already stamps
                # fundamental_source/is_synthetic/warning on this payload.
                "pe": fund.get("pe"),
                "eps": fund.get("eps"),
                "roe": fund.get("roe"),
                "roa": fund.get("roa"),
                "debt_ratio": fund.get("debt_ratio"),
                "current_ratio": fund.get("current_ratio"),
                "profit_growth": fund.get("profit_growth"),
                "revenue_growth": fund.get("revenue_growth"),
                "book_value_ps": fund.get("book_value_ps"),
                "pb": fund.get("pb"),
                "peg": fund.get("peg"),
                "dividend_yield": fund.get("dividend_yield"),  # بدون داده قطعی — None صادقانه
                "fund_score": fund.get("fund_score"),
                "value_score": fund.get("value_score"),
                "value_grade": fund.get("value_grade"),
                "is_synthetic": fund.get("is_synthetic"),
                "fundamental_source": fund.get("fundamental_source"),
                "warning": fund.get("warning"),
            },
            envelope,
        ),
        "flow": _supported(
            _dossier_flow_section(l18, envelope),
            envelope,
        ),
        "alerts_history": _supported(
            {
                "count": len(store.list_alerts(symbol=l18, limit=5)),
                "items": store.list_alerts(symbol=l18, limit=5),
            },
            envelope,
        ),
        "calendar": _unsupported(
            "calendar",
            "تقویم تعطیلات نسخه‌بندی‌شده به داده نماد متصل نیست (قرارداد market_calendar در این محصول fail-closed است و تعطیلی‌ها نامعلوم‌اند)",
            envelope,
        ),
        "dividends": _unsupported(
            "dividends",
            "ساختار داده سود تقسیمی در این محصول وجود ندارد؛ dividend_yield در موتور بنیادی فعلی هم None صادقانه است",
            envelope,
        ),
        "corporate_events": _unsupported(
            "corporate_events",
            "خبر/رویداد شرکتی تأییدشده در ساختارهای فعلی وجود ندارد و جعل داده ممنوع است",
            envelope,
        ),
        "shareholders": _unsupported(
            "shareholders",
            "فهرست سهامداران عمده در ساختارهای داده فعلی وجود ندارد",
            envelope,
        ),
        "target_price": _unsupported(
            "target_price",
            "هدف قیمتی تحلیل‌گران در ساختارهای داده فعلی وجود ندارد",
            envelope,
        ),
    }
    unavailable = [k for k, v in sections.items() if not v.get("available")]
    return {
        "ok": True,
        "symbol": l18,
        "l18": s.get("l18") or l18,
        "name": s.get("l30") or "",
        "sections": sections,
        "unavailable_sections": unavailable,
        "note": _SYNTHETIC_NOTE,
        **envelope,
    }


def _dossier_flow_section(l18: str, envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Membership of the symbol in the EXISTING big-moves (flow) path."""
    moves = [m for m in market_service.get_big_moves(limit=300) if m.get("symbol") == l18]
    latest = moves[0] if moves else None
    return {
        "in_recent_moves": bool(moves),
        "recent_move": latest,
        "moves_count": len(moves),
        "data_trust": envelope["data_trust"],
        "trust_level": envelope["trust_level"],
    }
