"""MASTER-RADAR WAVE-2 (MR2-D) — static gates for chart_pro increments.

Source-scan gates only (no network, no runtime UI), in the established style
of test_master_radar_frontend_static.py. They pin the MR2-D increments in
``frontend/js/modules/render/chart_pro.js`` (the only frontend file this
package touches):

1. measured-move drawing tool — 3-click interaction (anchor → move end →
   hypothetical target) with an honest Persian title, registered in the
   existing drawing-tools segment, stored in the existing drawings state
   shape and deletable like trend lines;
2. defensive consumption of the additive ``labeling`` field on the chartpro
   candles response — a chip is rendered ONLY when the server sends the
   field, its text is verbatim from the server values, and the module never
   fabricates a trust claim of its own (no LIVE / REAL_VERIFIED chip strings);
3. renderer security posture — no direct network primitives; all HTTP stays
   behind core/api.js (api()).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHART_PRO = ROOT / "frontend" / "js" / "modules" / "render" / "chart_pro.js"

MEASURE_MOVE_TOOL_ID = "measure-move"
MEASURE_MOVE_TITLE = "اندازه‌گیری حرکت — سه کلیک: شروع، پایان، هدف فرضی"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_measure_move_tool_registered_in_chart_pro():
    cp = _read(CHART_PRO)
    # stable tool id: injected toolbar button + drawing type + hint key
    assert f'data-draw="{MEASURE_MOVE_TOOL_ID}"' in cp
    assert cp.count(f'"{MEASURE_MOVE_TOOL_ID}"') >= 4
    # honest 3-click interaction note in the tool title
    assert MEASURE_MOVE_TITLE in cp
    assert "سه کلیک" in cp
    # drawing shape follows the trend-line point convention + target point
    assert '{ type: "measure-move", p1, p2, p3 }' in cp
    # deletable like trend lines (hit-test branch inside _deleteNear)
    assert 'd.type === "measure-move"' in cp


def test_measure_move_measurement_label_fields():
    cp = _read(CHART_PRO)
    # label builder must surface: price delta, percent delta (2 decimals), bar count
    assert "_measureLabelText" in cp
    assert "_measureBars" in cp
    assert "toFixed(2)" in cp
    assert "کندل" in cp


def test_labeling_field_consumed_defensively():
    cp = _read(CHART_PRO)
    # literal defensive property access on the candles response
    assert "res?.labeling" in cp
    # chip element + verbatim server fields only
    assert "cpLabelingChip" in cp
    assert "bar_class" in cp
    assert "method" in cp
    assert "note_fa" in cp
    # absence path: the chip is REMOVED, never replaced by fallback text
    assert "chip.remove()" in cp


def test_labeling_chip_never_hardcodes_trust_claims():
    cp = _read(CHART_PRO)
    m = re.search(r"_renderLabelingChip\(labeling\) \{[\s\S]*?\n  \}", cp)
    assert m, "chip renderer function not found"
    body = m.group(0)
    # the chip may only echo the server's labeling object — no self-made claim
    assert "LIVE" not in body
    assert "REAL_VERIFIED" not in body
    assert "live" not in body.lower()
    # fixed Persian chip wording (values themselves always come from the server)
    assert "کلاس بار" in body
    assert "روش" in body


def test_chart_pro_no_forbidden_network_primitives():
    cp = _read(CHART_PRO)
    for primitive in ("fetch(", "eval(", "WebSocket(", "XMLHttpRequest"):
        assert primitive not in cp
    # the api() boundary import stays intact
    assert 'from "../../core/api.js"' in cp


def test_measure_move_escape_cancel_path_present():
    cp = _read(CHART_PRO)
    assert '"Escape"' in cp
    assert "this.drawState.points = [];" in cp


def test_chart_pro_passes_node_syntax_check():
    result = subprocess.run(
        ["node", "--check", str(CHART_PRO)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
