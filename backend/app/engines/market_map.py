"""نقشه بازار — داده Treemap بر اساس صنعت و نماد."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.engines.metrics import compute_metrics
from app.engines.tablocastic import compute_tablocastic
from app.models.schemas import SymbolSnapshot

SIZE_MODES = {
    "tval": "ارزش معاملات",
    "tvol": "حجم",
    "mv": "ارزش بازار",
    "abs_net": "قدر مطلق پول حقیقی",
    "equal": "یکسان",
}

COLOR_MODES = {
    "plp": "درصد قیمت",
    "entry_score": "امتیاز ورود",
    "exit_score": "امتیاز خروج",
    "hot_net": "پول داغ",
    "buy_power": "قدرت خریدار",
    "individual_net": "خالص حقیقی",
}


def _size_value(s: SymbolSnapshot, m, mode: str) -> float:
    if mode == "tvol":
        return max(float(s.tvol or 0), 1.0)
    if mode == "mv":
        return max(float(s.mv or 0), float(s.tval or 1))
    if mode == "abs_net":
        return max(abs(float(m.individual_net_value or 0)), 1.0)
    if mode == "equal":
        return 1.0
    return max(float(s.tval or 0), 1.0)


def _color_value(s: SymbolSnapshot, m, mode: str) -> float:
    if mode == "entry_score":
        return float(m.entry_score)
    if mode == "exit_score":
        return float(m.exit_score)
    if mode == "hot_net":
        return float(m.hot_net)
    if mode == "buy_power":
        return float(m.buy_power)
    if mode == "individual_net":
        # normalize-ish to percent-like scale
        v = float(m.individual_net_value or 0)
        return max(-5.0, min(5.0, v / 5e10))
    return float(s.plp or 0)


def build_market_map(
    symbols: list[SymbolSnapshot],
    cfg: Settings | None = None,
    size_by: str = "tval",
    color_by: str = "plp",
    min_tval: float = 0,
) -> dict[str, Any]:
    cfg = cfg or get_settings()
    size_by = size_by if size_by in SIZE_MODES else "tval"
    color_by = color_by if color_by in COLOR_MODES else "plp"

    industries: dict[str, list[dict[str, Any]]] = {}
    leaves: list[dict[str, Any]] = []

    for s in symbols:
        if not s.l18:
            continue
        if min_tval and (s.tval or 0) < min_tval:
            continue
        m = compute_metrics(s, cfg)
        tc = compute_tablocastic(s, cfg)
        ind = s.cs or "سایر"
        node = {
            "symbol": s.l18,
            "name": s.l30,
            "industry": ind,
            "pl": s.pl,
            "plp": s.plp,
            "tval": s.tval,
            "tvol": s.tvol,
            "pe": s.pe,
            "entry_score": round(m.entry_score, 1),
            "exit_score": round(m.exit_score, 1),
            "buy_power": round(m.buy_power, 2),
            "hot_net": round(m.hot_net, 1),
            "volume_ratio": round(m.volume_ratio, 2),
            "individual_net_value": m.individual_net_value,
            "golden_number": tc.golden_number,
            "grade": tc.grade,
            "size": _size_value(s, m, size_by),
            "color": _color_value(s, m, color_by),
            "side": m.side.value if hasattr(m.side, "value") else str(m.side),
        }
        industries.setdefault(ind, []).append(node)
        leaves.append(node)

    groups = []
    for ind, kids in industries.items():
        groups.append(
            {
                "name": ind,
                "industry": ind,
                "size": sum(k["size"] for k in kids),
                "avg_plp": sum(k["plp"] for k in kids) / len(kids),
                "count": len(kids),
                "children": sorted(kids, key=lambda x: x["size"], reverse=True),
            }
        )
    groups.sort(key=lambda g: g["size"], reverse=True)
    leaves.sort(key=lambda x: x["size"], reverse=True)

    return {
        "size_by": size_by,
        "color_by": color_by,
        "size_modes": SIZE_MODES,
        "color_modes": COLOR_MODES,
        "symbol_count": len(leaves),
        "industry_count": len(groups),
        "groups": groups,
        "leaves": leaves,
    }
