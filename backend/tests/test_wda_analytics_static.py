"""WDA-3 static wiring battery — additive analytics flow panel.

Follows tests/test_frontend_static_script.py pattern: offline, static checks of
the frontend wiring only (no browser, no network).

Pinned contract (additive-only):
- NO new tab/panel: tabs/panels count stays 25 (orchestrator-owned counter —
  adding tabs is NOT part of WDA-3; the panel hooks into the existing
  "تحرکات بزرگان" tab).
- The flow panel lives inside #tab-big and renders from /api/v10/analytics/flow.
- All HTTP goes through core/api.js api() — no direct fetch in the new module.
- No forged trust labels: the module reads data_trust from the server and never
  hardcodes a live claim.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "index.html"
MAIN_JS = ROOT / "frontend" / "js" / "main.js"
FLOW_MODULE = ROOT / "frontend" / "js" / "modules" / "render" / "analytics_flow.js"

FLOW_ENDPOINT = "/api/v10/analytics/flow"


def _tab_big_section(html: str) -> str:
    """Slice the #tab-big section (from its opening tag to the next panel)."""
    match = re.search(r'<section class="panel[^"]*" id="tab-big">', html)
    assert match, "tab-big section not found"
    end = html.find('<section class="panel', match.end())
    return html[match.start(): end if end != -1 else len(html)]


def test_static_validator_contract_still_green_with_wiring():
    result = subprocess.run(
        [sys.executable, "scripts/validate_frontend_static.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR 2026-11-04): 25 -> 26 — one new
    # authorized tab `strategylab` (Strategy Lab studio + Indicator Manager,
    # directive §B4/§C1) was added WITH this wave; the WDA-3 "no new tab"
    # posture was specific to that wave's scope and is superseded by the new
    # directive's explicit product scope. Structural invariants unchanged:
    # every tab keeps its panel, no orphans/duplicates/missing imports.
    assert data["tabs"]["tabs_count"] == 26
    assert data["tabs"]["panels_count"] == 26
    assert data["tabs"]["missing_panels"] == []
    assert data["tabs"]["orphan_panels"] == []
    assert data["duplicate_ids"]["index"] == []
    assert data["missing_js_imports"] == []


def test_flow_panel_div_inside_existing_big_tab():
    section = _tab_big_section(INDEX.read_text(encoding="utf-8"))
    assert 'id="analyticsFlowPanel"' in section
    # pinned to the big-moves tab and nowhere else
    whole = INDEX.read_text(encoding="utf-8")
    assert whole.count('id="analyticsFlowPanel"') == 1
    assert 'data-tab="analyticsflow"' not in whole  # no new tab registered


def test_flow_module_uses_core_api_and_flow_endpoint():
    text = FLOW_MODULE.read_text(encoding="utf-8")
    assert 'from "../../core/api.js"' in text  # HTTP فقط از core/api.js
    assert f'api("{FLOW_ENDPOINT}")' in text
    assert "fetch(" not in text  # no direct fetch bypassing the single client
    # Persian labels present (RTL product)
    assert "جمع‌بندی جریان پول" in text
    assert "داده آزمایشی" in text


def test_flow_module_trust_label_comes_from_server_payload():
    text = FLOW_MODULE.read_text(encoding="utf-8")
    assert "data_trust" in text  # trust read from the server envelope
    # honesty: the module never hardcodes a live claim of its own — the trust
    # text comes from TRUST_STATE_LABELS[data_trust.state] or the raw state
    assert re.search(r"\blive\b", text, re.IGNORECASE) is None
    assert 'TRUST_STATE_LABELS[state]' in text  # label derived from server state


def test_main_js_imports_and_calls_the_flow_panel():
    text = MAIN_JS.read_text(encoding="utf-8")
    assert 'from "./modules/render/analytics_flow.js"' in text
    assert "renderAnalyticsFlow()" in text


def test_wda3_import_chain_resolves():
    """The new module import in main.js must resolve on disk (validator also
    checks all relative imports; this pins the WDA-3 edge explicitly)."""
    target = (MAIN_JS.parent / "./modules/render/analytics_flow.js").resolve()
    assert target.exists()
    # and the module's own imports resolve too
    for spec in ('../../core/api.js', '../../core/format.js'):
        assert (FLOW_MODULE.parent / spec).resolve().exists()
