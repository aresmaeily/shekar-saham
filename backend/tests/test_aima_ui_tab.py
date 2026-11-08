"""WAVE-AI (2026-11-08, WP-C): AI-MA UI tab static gates.

The directive §4 requires a dedicated AI-MA UI tab on the EXISTING API
boundary (/api/v10/aima) showing the actual runtime posture, execution
trace, branch results, errors and advisory-only limitations. These static
gates pin the honest-frontend discipline for the new surface (same rules as
product_loops_ui / ai2_studio):

- tab + panel registered (32/32, no orphans/missing panels);
- module api()-only (no direct fetch/XHR/WebSocket), esc() everywhere;
- no dynamic code execution, no polling/auto-run (user action only);
- trust label read ONLY from server fields (data_trust_label);
- no live/promotion claims minted client-side;
- sw v3-0-19 with the module precached;
- main.js lazy-activates the module on tab open.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "index.html"
MAIN_JS = ROOT / "frontend" / "js" / "main.js"
SW_JS = ROOT / "frontend" / "sw.js"
MODULE = ROOT / "frontend" / "js" / "modules" / "render" / "ai_ma_ui.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_aima_tab_and_panel_registered():
    html = _read(INDEX)
    assert 'data-tab="aima"' in html, "nav tab for AI-MA must exist"
    assert 'id="tab-aima"' in html, "panel section for AI-MA must exist"
    # 32 tabs / 32 panels, no orphans (mirrors the recorded counter-pin bump)
    tabs = re.findall(r'data-tab="([^"]+)"', html)
    panels = re.findall(r'<section class="panel[^"]*" id="tab-([^"]+)">', html)
    assert len(tabs) == 32
    assert len(panels) == 32
    assert set(tabs) == set(panels), "every tab must keep its panel (no orphans/missing)"


def test_aima_module_uses_api_boundary_only():
    text = _read(MODULE)
    assert 'from "../../core/api.js"' in text, "HTTP must go through core/api()"
    assert "esc(" in text, "output must be escaped"
    for banned in ("fetch(", "XMLHttpRequest", "new WebSocket", "eval(", "new Function"):
        assert banned not in text, f"banned client primitive: {banned}"


def test_aima_module_reads_trust_only_from_server_fields():
    text = _read(MODULE)
    assert "data_trust_label" in text, "trust label must come from the server field"
    # the module never upgrades or mints a trust class client-side
    for banned in ("REAL_VERIFIED", "LIVE_VERIFIED", "verified=true", "is_verified_live"):
        assert banned not in text


def test_aima_module_is_user_action_only():
    text = _read(MODULE)
    assert "setInterval" not in text, "no polling — every call is a user action"
    assert "setTimeout" not in text or "setTimeout" in text and False  # no timers at all
    # no automatic execution on import: the exported binder is called only on tab activation
    assert "export function bindAiMa" in text
    assert text.count("addEventListener") == text.count('el.addEventListener("click"'), (
        "only click bindings, all user-initiated"
    )


def test_aima_module_shows_runtime_trace_and_limitations():
    text = _read(MODULE)
    # runtime posture: specialists table + tools + honesty envelope
    assert "deterministic_tools" in text
    assert "authority_boundary" in text
    # execution record: waves, steps, artifacts, synthesis, trace, governance
    assert "wave_schedule" in text
    assert "synthesis" in text
    assert "trace" in text
    assert "governance" in text
    assert "data_trust_label" in text
    # advisory-only limitations surfaced from the server honesty envelope
    assert "advisory" in text.lower() or "مشورتی" in text


def test_aima_error_and_empty_states_present():
    text = _read(MODULE)
    assert "catch (err)" in text, "every call has an error path"
    assert "خطا" in text, "errors rendered honestly in Persian"
    # loading states before results
    assert "در حال" in text


def test_main_js_lazy_activation():
    text = _read(MAIN_JS)
    assert 'from "./modules/render/ai_ma_ui.js"' in text
    assert "bindAiMaTab" in text
    assert 'id="tab-aima"' in text or '"#tab-aima"' in text


def test_sw_v3_0_18_precaches_the_module():
    sw = _read(SW_JS)
    # COUNTER-PIN BUMP (recorded, STAGE-3 REDESIGN 2026-11-08): v3-0-19 -> v3-0-20 — tokens.css precache + design-system rewrite; module precache assertion unchanged
    assert "radar-bourse-static-v3-0-20" in sw
    assert "/static/js/modules/render/ai_ma_ui.js" in sw


def test_aima_module_passes_node_syntax_check():
    import subprocess

    res = subprocess.run(
        ["node", "--check", str(MODULE)], capture_output=True, text=True
    )
    assert res.returncode == 0, res.stderr
