"""MASTER-RADAR WAVE-3 — static gates for the command palette package.

Source-scan gates only (no network, no runtime UI), in the established style
of test_master_radar_wave2_chartstatic.py / test_master_radar_wave2_frontend.py.
They pin ``frontend/js/modules/command_palette.js`` (MR-H-02):

- Ctrl+K / Cmd+K binding with passive:false and preventDefault only when the
  palette itself consumes the key; Esc / ArrowUp / ArrowDown / Enter handling;
- ARIA listbox/option semantics with aria-activedescendant;
- tab enumeration from the LIVE DOM (no hardcoded tab id list) — the Data
  Quality tab and every other tab come from ``.tab[data-tab]`` buttons;
- recents under ``radar.palette.recent.v1`` capped at 5;
- defensive container handling (#paletteRoot preferred, document.body fallback,
  optional #paletteBtn header binding);
- renderer security posture: no eval/new Function, no fetch/XMLHttpRequest/
  WebSocket/importScripts, no string→HTML construction (textContent only);
- actions execute ONLY on explicit Enter/click — the registry is built at open
  time, nothing runs automatically.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PALETTE = ROOT / "frontend" / "js" / "modules" / "command_palette.js"

RECENT_KEY = "radar.palette.recent.v1"
RECENT_MAX_PIN = "PALETTE_RECENT_MAX = 5"

FORBIDDEN_PRIMITIVES = (
    "eval(",
    "new Function",
    "fetch(",
    "XMLHttpRequest",
    "WebSocket(",
    "importScripts",
    "document.write(",
)

# No hardcoded tab enumeration may exist: tab ids must come from the live DOM.
HARDCODED_TAB_IDS = ('data-tab="chartpro"', 'data-tab="dataquality"', 'data-tab="forex"')


def _read() -> str:
    return PALETTE.read_text(encoding="utf-8")


def test_palette_ctrl_cmd_k_binding():
    t = _read()
    # both modifiers checked, "k" checked case-insensitively
    assert "e.ctrlKey || e.metaKey" in t
    assert 'e.key === "k"' in t
    assert 'e.key === "K"' in t
    # single document keydown listener, passive:false so preventDefault works
    assert 'addEventListener("keydown", onKeydown, { passive: false })' in t
    assert "preventDefault()" in t
    # within the handler, the Ctrl+K branch preventDefaults and then toggles
    m = re.search(r"function onKeydown\(e\) \{[\s\S]*?\n\}", t)
    assert m, "onKeydown handler not found"
    body = m.group(0)
    assert body.index("e.preventDefault();") < body.index("toggle();")


def test_palette_esc_arrows_enter_handling():
    t = _read()
    assert '"Escape"' in t
    assert '"ArrowUp"' in t
    assert '"ArrowDown"' in t
    assert '"Enter"' in t
    # navigation keys are only consumed while the palette is open
    assert "if (!isOpen()) return;" in t
    i_open_guard = t.index("if (!isOpen()) return;")
    for key in ('"Escape"', '"ArrowUp"', '"ArrowDown"', '"Enter"'):
        assert t.index(key) > i_open_guard, f"{key} handled before the open-guard"


def test_palette_aria_listbox_option_semantics():
    t = _read()
    assert 'role", "listbox"' in t
    assert 'role", "option"' in t
    assert '"aria-activedescendant"' in t
    assert '"aria-selected"' in t
    assert '"aria-modal"' in t


def test_palette_tab_enumeration_from_live_dom_only():
    t = _read()
    # tabs (incl. Data Quality) are enumerated from the live DOM buttons
    assert 'querySelectorAll(".tab[data-tab]")' in t
    assert '"رفتن به "' in t
    # no hardcoded tab id list may exist in the module
    for hard in HARDCODED_TAB_IDS:
        assert hard not in t


def test_palette_charttype_and_replay_speed_actions_via_real_clicks():
    t = _read()
    # chart types: the segment's data-ctype buttons, dispatched as real clicks
    assert '"#cpTypeSeg button[data-ctype]"' in t
    assert '"نوع نمودار: "' in t
    # replay speeds: the replay module's data-sp buttons (#rpSpeeds)
    assert '"#rpSpeeds button[data-sp]"' in t
    assert '"سرعت رپلای: "' in t


def test_palette_recent_key_and_cap():
    t = _read()
    assert RECENT_KEY in t
    assert RECENT_MAX_PIN in t
    # cap enforced on both read and write paths
    assert t.count(".slice(0, PALETTE_RECENT_MAX)") >= 2


def test_palette_defensive_container_handling():
    t = _read()
    # #paletteRoot preferred when present, document.body fallback pre-integration
    assert 'document.getElementById("paletteRoot") || document.body' in t
    # optional header button — absence is not an error (defensive binding)
    assert 'document.getElementById("paletteBtn")' in t
    assert "observePaletteBtn" in t


def test_palette_no_forbidden_primitives():
    t = _read()
    for primitive in FORBIDDEN_PRIMITIVES:
        assert primitive not in t, f"palette contains forbidden primitive {primitive!r}"


def test_palette_text_content_only_dynamic_dom():
    t = _read()
    # every dynamic string goes through textContent on createElement'd nodes
    assert t.count("textContent") >= 5
    assert "createElement" in t
    for banned in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert banned not in t, f"palette must not build DOM from strings via {banned}"


def test_palette_actions_run_only_on_explicit_activation():
    t = _read()
    # registry is built at OPEN time from the live DOM — never at import, never auto-run
    assert "actions = buildActions();" in t
    open_idx = t.index("function open() {")
    assert t.index("actions = buildActions();") > open_idx
    # run happens only through the Enter path or the option's click listener
    assert "function runSelected()" in t
    assert 'opt.addEventListener("click"' in t
    assert "function runAction(i)" in t


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not available in PATH")
def test_palette_passes_node_syntax_check():
    result = subprocess.run(
        ["node", "--check", str(PALETTE)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
