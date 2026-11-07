"""MASTER-RADAR WAVE-O (2026-11-06) — static gates for the AI-2 Studio panel.

WAVE-O scope: UX integration of the AI-2 governed generation surface
(/api/v10/ai2/*, WAVE-K/L backend — read-only this wave). The new tab
``aistudio`` renders the SERVER's own honesty labels (posture, outcome
status, candidate status, tamper verdict, provenance, honesty envelope);
the client never upgrades or fabricates a trust label, never polls, and
never executes dynamic code. With the committed default AI2_ENABLED=0 the
generate call returns the honest ``gated_not_executed`` outcome and the
panel renders exactly that — no client-side bypass exists.

Mirrors the established source-scan style of test_master_radar_wave2_frontend.py
and test_master_radar_wave3_integration.py. All gates here are ADDITIVE:
no existing test was modified beyond the recorded counter-pin bumps
(tabs 30 -> 31, SW radar-bourse-static-v3-0-14 -> v3-0-16).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "index.html"
MAIN_JS = ROOT / "frontend" / "js" / "main.js"
SW_JS = ROOT / "frontend" / "sw.js"
MODULE = ROOT / "frontend" / "js" / "modules" / "render" / "ai2_studio.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


FORBIDDEN_PRIMITIVES = (
    "fetch(",
    "WebSocket(",
    "eval(",
    "document.write(",
    "XMLHttpRequest",
    "localStorage.setItem(",
)


# ---------------------------------------------------------------------------
# tab + panel
# ---------------------------------------------------------------------------
def test_waveo_tab_button_and_panel_exist():
    idx = _read(INDEX)
    assert 'data-tab="aistudio"' in idx
    assert 'id="tab-aistudio"' in idx
    assert idx.count('id="tab-aistudio"') == 1


def test_waveo_tab_placement_after_loops_before_excellent():
    idx = _read(INDEX)
    positions = [
        idx.find('data-tab="loops"'),
        idx.find('data-tab="aistudio"'),
        idx.find('data-tab="excellent"'),
    ]
    assert -1 not in positions
    assert positions == sorted(positions), "aistudio tab must sit between loops and excellent"


def test_waveo_tab_count_bumped_30_to_31():
    """COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-O 2026-11-06): 30 -> 31 —
    the new governed AI-2 studio tab; prior chain 26 -> 29 (WAVE-2) -> 30."""
    html = _read(INDEX)
    assert len(re.findall(r'class="tab[^"]*" data-tab=', html)) == 31


# ---------------------------------------------------------------------------
# module boundaries (same discipline as the WAVE-2 module gates)
# ---------------------------------------------------------------------------
def test_waveo_module_uses_the_core_api_boundary():
    text = _read(MODULE)
    assert 'from "../../core/api.js"' in text, "must go through core/api.js"
    assert 'from "../../core/format.js"' in text  # esc single source
    assert "data_trust" in text  # trust read from the server envelope
    assert "TRUST_STATE_LABELS" in text  # label derived from server state


def test_waveo_module_forbidden_primitives_absent():
    text = _read(MODULE)
    for primitive in FORBIDDEN_PRIMITIVES:
        assert primitive not in text, f"module contains forbidden primitive {primitive!r}"


def test_waveo_module_targets_the_governed_ai2_endpoints():
    text = _read(MODULE)
    for path in (
        "/api/v10/ai2/posture",
        "/api/v10/ai2/generate",
        "/api/v10/ai2/candidates",
        "/approve",
        "/promote",
        "/api/v10/ai2/runs",
    ):
        assert path in text, f"missing governed endpoint path {path!r}"


def test_waveo_module_renders_server_labels_only():
    """Every status map covers the server's literal values; unknown values
    fall back to the RAW server string (label() helper) — the client can
    never invent or upgrade a state."""
    text = _read(MODULE)
    assert "gated_not_executed" in text  # honest disabled-outcome label
    assert "needs_clarification" in text
    assert "refused" in text
    assert "executed_shadow" in text
    assert "DRAFT" in text and "APPROVED" in text and "PROMOTED" in text
    # fallback rendering of unknown server values:
    assert "function label(" in text
    assert "map[raw] ? map[raw] : esc(raw" in text


def test_waveo_module_no_polling_and_no_timers():
    text = _read(MODULE)
    assert "setInterval" not in text  # no auto-refresh, no polling loop
    assert "MutationObserver" in text  # bind-on-demand pattern (like WAVE-F)


def test_waveo_module_named_human_approver_required():
    text = _read(MODULE)
    # the ONLY authority over approve/promote is a named human approver
    assert "ai2Approver" in text
    assert "length < 4" in text  # client-side mirror of the server bound
    assert "مدل هیچ اختیاری ندارد" in text  # honesty message, Persian


def test_waveo_module_bounded_client_inputs():
    """Client-side bounds mirror the server schema (fail-closed before send)."""
    text = _read(MODULE)
    assert "slice(0, 2000)" in text  # question bound
    assert "slice(0, 64)" in text  # symbol bound
    assert "Math.max(50, Math.min(500" in text  # bar_count bound
    assert "حداکثر ۸ شفاف‌سازی" in text  # clarifications cap
    assert "idem.length < 8" in text  # idempotency key bound


# ---------------------------------------------------------------------------
# wiring
# ---------------------------------------------------------------------------
def test_main_js_imports_ai2_studio():
    js = _read(MAIN_JS)
    assert 'import "./modules/render/ai2_studio.js";' in js
    assert "MASTER-RADAR WAVE-O" in js


def test_sw_bumped_to_v3_0_15_with_waveo_precache():
    sw = _read(SW_JS)
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-O 2026-11-06): v3-0-14 -> v3-0-16 —
    # precache extended with ai2_studio.js (governed AI-2 studio panel).
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-S2 2026-11-07): v3-0-15 -> v3-0-16 — cross-window crosshair/range sync in chart_grid.js
    # COUNTER-PIN BUMP (recorded, WAVE-AB2 2026-11-08): v3-0-16 -> v3-0-17 — walk-forward UI trigger in forward_center.js + index.html + dead-control wiring (hunt/tablo/hot filters, btnWsRefresh/btnValueReload/btnPfAdd, excellent tab activation)
    assert "radar-bourse-static-v3-0-17" in sw
    assert "radar-bourse-static-v3-0-14" not in sw
    assert "/static/js/modules/render/ai2_studio.js" in sw


def test_waveo_files_pass_node_syntax_check():
    for rel in (
        "frontend/js/modules/render/ai2_studio.js",
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


# ---------------------------------------------------------------------------
# honest disclosure in the panel markup
# ---------------------------------------------------------------------------
def test_waveo_panel_honest_disclosure_tokens():
    idx = _read(INDEX)
    start = idx.find('id="tab-aistudio"')
    end = idx.find('id="tab-excellent"')
    panel = idx[start:end]
    # the four honesty anchors of the OA-3 surface, stated in Persian:
    assert "AI2_ENABLED=0" in panel  # committed default disclosed
    assert "gated_not_executed" in panel  # honest disabled outcome named
    assert "مدل هیچ اختیاری" in panel  # model authority: none
    assert "فقط کاغذی" in panel  # promotion is paper-only
    assert "فقط-در-حافظه" in panel  # registry persistence disclosure
    assert "بدون خروج به بیرون" in panel  # no egress
    assert 'id="ai2TrustBadge"' in panel
