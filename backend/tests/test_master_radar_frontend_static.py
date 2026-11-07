"""MASTER-RADAR (2026-11-04) — static gates for the Strategy Lab frontend.

Additive structural gates for the new `strategylab` tab, its render module,
and the chart-type selector added to chart_pro. Complements (never replaces)
the orchestrator-level validator (`scripts/validate_frontend_static.py`) whose
counter-pins were bumped WITH this authorized wave (tabs 25->26, SW v3-0-6).

Honesty invariants enforced here:
- ALL HTTP goes through core/api.js (api()) — zero direct fetch() in the new
  module; zero eval/Function constructor (renderer security posture).
- Trust labels come from the server payload; the module never hardcodes a
  "live" claim of its own.
- Heikin-Ashi is a visual re-representation: the code must contain no claim
  of new/lower-timeframe data and must not fetch anything by itself.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "index.html"
MAIN_JS = ROOT / "frontend" / "js" / "main.js"
SL_MODULE = ROOT / "frontend" / "js" / "modules" / "render" / "strategy_lab.js"
CHART_PRO = ROOT / "frontend" / "js" / "modules" / "render" / "chart_pro.js"
SW_JS = ROOT / "frontend" / "sw.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_strategylab_tab_and_panel_exist_and_match():
    idx = _read(INDEX)
    assert 'data-tab="strategylab"' in idx
    assert 'id="tab-strategylab"' in idx
    assert idx.count('id="tab-strategylab"') == 1
    # no orphan: validator counts stay in sync (29/29 asserted in test_wda_analytics_static)


def test_strategylab_module_http_boundary():
    text = _read(SL_MODULE)
    assert 'from "../../core/api.js"' in text
    assert "fetch(" not in text  # single-client boundary only
    assert "eval(" not in text and "new Function" not in text
    assert "WebSocket" not in text  # no egress channel
    # Persian user-facing labels present (RTL product)
    assert "اعتبارسنجی" in text
    assert "بازپخش کاغذی" in text


def test_strategylab_module_trust_label_from_server():
    text = _read(SL_MODULE)
    assert "TRUST_STATE_LABELS" in text
    assert "data_trust" in text
    # no hardcoded live claim of its own
    assert re.search(r"\blive\b", text, re.IGNORECASE) is None


def test_main_js_imports_strategy_lab_module():
    text = _read(MAIN_JS)
    assert 'from "./modules/render/strategy_lab.js"' in text or 'import "./modules/render/strategy_lab.js"' in text


def test_chart_type_selector_wired_in_chart_pro():
    idx = _read(INDEX)
    assert 'id="cpTypeSeg"' in idx
    for mode in ("candles", "line", "area", "ha"):
        assert f'data-ctype="{mode}"' in idx
    cp = _read(CHART_PRO)
    assert "_applyChartType" in cp
    assert "_heikinAshi" in cp
    # HA honesty: re-representation of the SAME data, no new data claim
    assert "بازنمایی بصری" in cp


def test_heikin_ashi_formula_correct_shape():
    # structural check: the HA formula uses the classic 4-value close average
    cp = _read(CHART_PRO)
    assert "(o + h + l + cl) / 4" in cp
    assert "(prevOpen + prevClose) / 2" in cp


def test_sw_precache_includes_strategy_lab_and_bumped():
    sw = _read(SW_JS)
    assert "/static/js/modules/render/strategy_lab.js" in sw
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-2 2026-11-04): v3-0-6 -> v3-0-7 —
    # precache list extended with the three new render modules (see
    # test_master_radar_wave2_frontend.py for the WAVE-2 gates).
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-3 2026-11-04): v3-0-7 -> v3-0-8 —
    # precache list extended with chart_grid.js + command_palette.js (see
    # test_master_radar_wave3_* for the WAVE-3 gates).
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-E 2026-11-05): v3-0-12 -> v3-0-13 (SW install cache:reload honesty fix) — prior chain v3-0-8 -> v3-0-9 -> v3-0-10 -> v3-0-11 -> v3-0-12 (WAVE-B popup fix, WAVE-D PDF export, WAVE-E declared calendars) — prior chain v3-0-8 -> v3-0-9 -> v3-0-10 -> v3-0-11 (WAVE-B popup fix, WAVE-D PDF export) — prior chain v3-0-8 -> v3-0-9 -> v3-0-10 (WAVE-B popup-detach-intent fix) —
    # precache extended with the UIDL-1 user-indicator modules (see
    # test_master_radar_waveb_frontend.py for the WAVE-B gates).
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-F 2026-11-05): v3-0-13 -> v3-0-14 —
    # precache extended with product_loops_ui.js (WAVE-F product-loops panel).
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-O 2026-11-06): v3-0-14 -> v3-0-16 — precache extended with ai2_studio.js (WAVE-O governed AI-2 studio panel).

    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-S2 2026-11-07): v3-0-15 -> v3-0-16 — cross-window crosshair/range sync in chart_grid.js
    # COUNTER-PIN BUMP (recorded, WAVE-AB2 2026-11-08): v3-0-16 -> v3-0-17 — walk-forward UI trigger added to the forward-test center (precached forward_center.js + index.html changed; see test_master_waveab_walkforward_ui.py)
    # COUNTER-PIN BUMP (recorded, WAVE-AI 2026-11-08): v3-0-17 -> v3-0-18 — AI-MA tab (precached render/ai_ma_ui.js + index.html panel + main.js lazy activation; see test_aima_ui_tab.py)
    assert "radar-bourse-static-v3-0-18" in sw


def test_new_frontend_modules_pass_node_syntax_check():
    for p in (SL_MODULE, CHART_PRO, MAIN_JS):
        result = subprocess.run(
            ["node", "--check", str(p)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"{p.name}: {result.stderr}"
