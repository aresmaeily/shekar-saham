"""WAVE-AB2 (2026-11-08): static gates for dead-control wiring.

The WP-J audit (2026-11-08) recorded dead controls — HTML elements with no
event listener anywhere in the JS, or modules imported by nobody:

- hunt filters fNegOnly / fFundOnly / fMinScore (never read by hunt())
- tablo slider fTabloQ + segmented control #tabloGrade (read at render, no
  listener ever re-rendered them)
- hot segmented controls #hotTier / #hotView
- live-tab button #btnWsRefresh (POST /api/refresh had zero frontend callers)
- value-tab button #btnValueReload
- portfolio inline add form pfSymbol / pfNote / btnPfAdd
- the whole "excellent" tab: render/excellent.js imported by nobody, panels
  stuck at «در حال بارگذاری…»

This wave wires ALL of them. These gates pin the wiring so it cannot silently
regress (the fail-honest repo convention: no silent controls).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = (ROOT / "frontend" / "js" / "main.js").read_text(encoding="utf-8")
DATA = (ROOT / "frontend" / "js" / "tabs" / "data.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
EXC = (ROOT / "frontend" / "js" / "modules" / "render" / "excellent.js").read_text(encoding="utf-8")


def test_hunt_filters_are_read_by_hunt_render():
    assert "fNegOnly" in DATA
    assert "fFundOnly" in DATA
    assert "fMinScore" in DATA
    assert 'r.tags.includes("بنیادی‌خوب")' in DATA


def test_main_wires_hunt_and_tablo_and_hot_controls():
    for element_id in ["fNegOnly", "fFundOnly", "fMinScore", "fTabloQ"]:
        assert f'$("#{element_id}")' in MAIN
    for seg in ["tabloGrade", "hotTier", "hotView"]:
        assert f'"#{seg}"' in MAIN


def test_main_wires_dead_buttons():
    for element_id in ["btnWsRefresh", "btnValueReload", "btnPfAdd"]:
        assert f'$("#{element_id}")' in MAIN
    assert '"/api/refresh"' in MAIN, "POST /api/refresh must finally have a frontend caller"
    assert "addPortfolio(" in MAIN
    assert "bindDataFilters()" in MAIN
    assert "bindExcellentTab()" in MAIN


def test_excellent_module_is_now_loaded_and_uses_api_boundary():
    # loaded by main.js (dynamic import on tab activation)
    assert "modules/render/excellent.js" in MAIN
    # HTTP boundary: core api(), no direct fetch
    assert 'from "../../core/api.js"' in EXC
    assert "fetch(" not in EXC, "legacy direct fetch must be migrated to api()"
    assert "eval(" not in EXC
    assert "new Function" not in EXC
    # all four panels now have renderers
    for fn in ["renderDataQuality", "renderAnomalies", "renderRisk", "renderPortfolioOptimization"]:
        assert f"export async function {fn}" in EXC
    # honest-empty + escaped error paths
    assert "چیزی جعل نمی‌شود" in EXC
    assert "escapeHtml(" in EXC
    # trust honesty: never mint a live label (only the server's own field logic)
    assert EXC.count("live_verified") <= 1
    assert '"LIVE" ? ' not in EXC.replace('=== true) ? "LIVE"', "")


def test_excellent_endpoints_match_tested_v07_router():
    allowed = [
        "/api/v07/data-quality",
        "/api/v07/anomalies?limit=20",
        "/api/v07/risk/position-size?portfolio_value=100000000&entry_price=1000&stop_loss=970&risk_pct=1",
        "/api/v07/portfolio/optimization",
    ]
    import re as _re
    for p in allowed:
        assert p in EXC, f"excellent.js must call {p}"
    for m in _re.finditer(r'/api/[A-Za-z0-9_?=&{}.$/\-]+', EXC):
        token = m.group(0)
        assert token in allowed, f"unexpected endpoint in excellent.js: {token}"


def test_dead_controls_still_exist_in_html():
    for element_id in ["fNegOnly", "fFundOnly", "fMinScore", "fTabloQ", "tabloGrade", "hotTier", "hotView", "btnWsRefresh", "btnValueReload", "btnPfAdd", "pfSymbol", "pfNote"]:
        assert f'id="{element_id}"' in INDEX
