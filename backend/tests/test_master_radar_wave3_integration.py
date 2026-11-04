"""MASTER-RADAR WAVE-3 — integration gates (main-agent integration step).

Static gates for the WAVE-3 integration surface that the parallel packages
deliberately did NOT touch (their ownership was disjoint): index.html DOM
containers + buttons, main.js module imports, and sw.js v3-0-8 precache.
Mirrors the established source-scan style of
test_master_radar_wave2_frontend.py / test_master_radar_frontend_static.py.

Pinned here (and nowhere else):
1. index.html: five DERIVED chart-type buttons (renko/range/kagi/pnf/linebreak)
   with honest DERIVED titles; crosshair readout container; multi-chart grid
   bar + root containers; command palette launcher + root container.
2. main.js: the two new side-effect imports (self-binding modules) with
   WAVE-3 dating comments.
3. sw.js: v3-0-8 + both new modules in the precache list.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "index.html"
MAIN_JS = ROOT / "frontend" / "js" / "main.js"
SW_JS = ROOT / "frontend" / "sw.js"

DERIVED_TYPES = ["renko", "range", "kagi", "pnf", "linebreak"]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_index_has_five_derived_chart_type_buttons():
    html = _read(INDEX)
    seg_start = html.index('id="cpTypeSeg"')
    seg_end = html.index("</div>", seg_start)
    seg = html[seg_start:seg_end]
    for t in DERIVED_TYPES:
        assert f'data-ctype="{t}"' in seg, f"derived button {t} missing from cpTypeSeg"
    # honest DERIVED labeling in the segment title — derived constructions are
    # announced as derived, never as native or real data
    assert "DERIVED" in seg


def test_index_has_crosshair_readout_container():
    html = _read(INDEX)
    assert 'id="cpCrossReadout"' in html
    # honest title: only values from the loaded data, nothing fabricated
    assert "هیچ مقدار ساختگی" in html


def test_index_has_multichart_grid_containers():
    html = _read(INDEX)
    assert 'id="cpGridBar"' in html
    assert 'id="cpGridRoot"' in html
    # the WAVE-3 dating comment anchors the containers to the grid increment
    assert "MASTER-RADAR WAVE-3" in html


def test_index_has_command_palette_containers():
    html = _read(INDEX)
    assert 'id="paletteBtn"' in html
    assert 'id="paletteRoot"' in html
    # honest title: explicit user action only
    assert "فقط با انتخاب صریح کاربر" in html


def test_main_js_imports_wave3_modules():
    js = _read(MAIN_JS)
    assert 'import "./modules/render/chart_grid.js";' in js
    assert 'import "./modules/command_palette.js";' in js
    assert js.count("MASTER-RADAR WAVE-3") >= 2


def test_sw_bumped_to_v3_0_8_with_wave3_precache():
    sw = _read(SW_JS)
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-B 2026-11-04): v3-0-8 -> v3-0-9 -> v3-0-10 (popup-detach-intent fix)
    assert "radar-bourse-static-v3-0-10" in sw
    assert "radar-bourse-static-v3-0-9" not in sw
    assert "/static/js/modules/render/chart_grid.js" in sw
    assert "/static/js/modules/command_palette.js" in sw


def test_tabs_count_unchanged_29():
    """WAVE-3 adds NO new tabs (grid + palette live inside existing surfaces)."""
    html = _read(INDEX)
    # class="tab" (default active state varies: class="tab active" on the first)
    assert len(re.findall(r'class="tab[^"]*" data-tab=', html)) == 29


def test_wave3_files_pass_node_syntax_check():
    for rel in (
        "frontend/js/modules/render/chart_pro.js",
        "frontend/js/modules/render/chart_grid.js",
        "frontend/js/modules/command_palette.js",
        "frontend/js/main.js",
        "frontend/sw.js",
    ):
        r = subprocess.run(
            ["node", "--check", str(ROOT / rel)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert r.returncode == 0, f"node --check failed for {rel}: {r.stderr}"
