"""MASTER-RADAR WAVE-2 (2026-11-04) — static gates for the three new centers.

Additive structural gates for the WAVE-2 frontend tabs `backtestcenter`,
`forwardcenter`, `dataquality`, their render modules, and the sw.js precache
extension. Complements (never replaces) the orchestrator-level validator
(``scripts/validate_frontend_static.py``) whose counter-pins were bumped WITH
this authorized wave (tabs 26->29, SW v3-0-6 -> v3-0-7).

Honesty invariants enforced here:
- ALL HTTP goes through core/api.js (api()) — zero direct fetch()/WebSocket/
  XMLHttpRequest in the new modules; zero eval/document.write; no
  localStorage writes of sensitive data from the new modules.
- Trust labels come from the server trust_envelope; the modules never
  hardcode a "live" claim of their own.
- The Data Quality Center carries an explicit SYNTHETIC-class note (all data
  here is seeded fixtures) and the Forward Center carries the PAPER-only
  note (کاغذی — نه معامله زنده).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "index.html"
MAIN_JS = ROOT / "frontend" / "js" / "main.js"
SW_JS = ROOT / "frontend" / "sw.js"

WAVE2_MODULES = [
    ROOT / "frontend" / "js" / "modules" / "render" / "backtest_center.js",
    ROOT / "frontend" / "js" / "modules" / "render" / "forward_center.js",
    ROOT / "frontend" / "js" / "modules" / "render" / "data_quality_center.js",
]

WAVE2_TAB_IDS = ("backtestcenter", "forwardcenter", "dataquality")
WAVE2_MODULE_NAMES = ("backtest_center.js", "forward_center.js", "data_quality_center.js")

# Forbidden primitives (renderer security + single-client HTTP boundary).
FORBIDDEN_PRIMITIVES = (
    "fetch(",
    "WebSocket(",
    "eval(",
    "document.write(",
    "XMLHttpRequest",
    "localStorage.setItem(",
)

#: The honest SYNTHETIC note strings that MUST exist in index.html per panel.
SYNTHETIC_NOTE = "داده سینتتیک seed شده"
DQ_SYNTHETIC_NOTE = "همه داده‌های این مرکز از کلاس SYNTHETIC است (فیکسچر seed شده)"
FC_PAPER_NOTE = "فقط آزمون کاغذی (PAPER) — نه معامله زنده"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_static_validator_contract_still_green_with_wave2():
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
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-2 2026-11-04): 26 -> 29 —
    # the three WAVE-2 product tabs were added WITH this wave; structural
    # invariants unchanged (every tab keeps its panel, no orphans/duplicates).
    assert data["tabs"]["tabs_count"] == 29
    assert data["tabs"]["panels_count"] == 29
    assert data["tabs"]["missing_panels"] == []
    assert data["tabs"]["orphan_panels"] == []
    assert data["duplicate_ids"]["index"] == []
    assert data["missing_js_imports"] == []


def test_wave2_modules_pass_node_syntax_check():
    if shutil.which("node") is None:
        pytest.skip("node is not available in PATH — syntax gate reported as skipped")
    for p in (*WAVE2_MODULES, SW_JS, MAIN_JS):
        result = subprocess.run(
            ["node", "--check", str(p)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"{p.name}: {result.stderr}"


def test_wave2_modules_forbidden_primitives_absent():
    for p in WAVE2_MODULES:
        text = _read(p)
        for primitive in FORBIDDEN_PRIMITIVES:
            assert primitive not in text, f"{p.name} contains forbidden primitive {primitive!r}"


def test_wave2_modules_import_the_core_api_boundary():
    for p in WAVE2_MODULES:
        text = _read(p)
        assert 'from "../../core/api.js"' in text, f"{p.name} must go through core/api.js"
        assert 'from "../../core/format.js"' in text  # fmtNum/esc single source
        assert "data_trust" in text  # trust read from the server envelope
        assert "TRUST_STATE_LABELS" in text  # label derived from server state


def test_wave2_tabs_and_panels_exist_and_match():
    idx = _read(INDEX)
    for tab in WAVE2_TAB_IDS:
        assert f'data-tab="{tab}"' in idx
        assert f'id="tab-{tab}"' in idx
        assert idx.count(f'id="tab-{tab}"') == 1
    # placement: the three WAVE-2 tabs come right after the strategylab tab
    tab_btns = [m for m in (
        idx.find('data-tab="strategylab"'),
        idx.find('data-tab="backtestcenter"'),
        idx.find('data-tab="forwardcenter"'),
        idx.find('data-tab="dataquality"'),
    ) if m != -1]
    assert tab_btns == sorted(tab_btns), "WAVE-2 tabs must be placed after the strategylab tab"


def test_wave2_honest_synthetic_and_paper_notes_present():
    idx = _read(INDEX)
    # every WAVE-2 panel-head carries an honest SYNTHETIC/data note: the
    # backtest/forward panels use the synthetic-candles wording, the data
    # quality panel its (stricter) SYNTHETIC-class fixture wording.
    for tab in ("backtestcenter", "forwardcenter"):
        start = idx.find(f'id="tab-{tab}"')
        assert start != -1
        end = idx.find("<section", start + 1)
        section = idx[start : end if end != -1 else len(idx)]
        assert SYNTHETIC_NOTE in section, f"panel {tab} lacks the SYNTHETIC data note"
    assert FC_PAPER_NOTE in idx  # forward center: PAPER only, not live trading
    assert DQ_SYNTHETIC_NOTE in idx  # data quality center: all data is SYNTHETIC-class
    # trust-class legend covers every documented class
    for cls in ("REAL_VERIFIED", "REAL_UNVERIFIED", "DELAYED", "SYNTHETIC", "PAPER", "STALE", "MISSING"):
        assert cls in idx


def test_main_js_imports_the_three_wave2_modules():
    text = _read(MAIN_JS)
    for name in WAVE2_MODULE_NAMES:
        assert f'import "./modules/render/{name}"' in text


def test_wave2_endpoints_wired_via_core_api():
    """The WAVE-2 centers must call their designated v10 endpoints through
    api() — export/optimizer/paper-replay/dataquality paths pinned here.

    WAVE-2 integration sync (recorded, 2026-11-04): the paths below are the
    ACTUAL backend contracts (POST /optimize; GET /markets/{m}/coverage +
    GET /symbols/{id}/audit) — the initially guessed /optimizer and
    /coverage?market= paths were corrected during integration, exactly the
    sync the package plan required; no assertion was weakened (each still
    pins a real endpoint call)."""
    bc = _read(WAVE2_MODULES[0])
    fc = _read(WAVE2_MODULES[1])
    dq = _read(WAVE2_MODULES[2])
    assert '"/api/v10/strategylab/backtest"' in bc
    assert '"/api/v10/strategylab/backtest/export"' in bc  # CSV/JSON export
    assert '"/api/v10/strategylab/optimize"' in bc  # actual router path (integration sync)
    assert "/api/v10/strategylab/optimizer" not in bc  # guessed path must not survive
    assert '"/api/v10/strategylab/paper-replay"' in fc
    assert "/api/v10/dataquality/markets/" in dq  # actual router path (integration sync)
    assert "/api/v10/dataquality/symbols/" in dq  # per-symbol drill-down (integration sync)
    # export must download client-side from the response text (Blob + object URL)
    assert "URL.createObjectURL" in bc and "revokeObjectURL" in bc
    # optimizer seed is enforced client-side before any request
    assert 'bcOptSeed' in bc and "الزامی" in bc


def test_sw_precache_includes_wave2_modules_and_bumped():
    sw = _read(SW_JS)
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-3 2026-11-04): v3-0-7 -> v3-0-8 —
    # precache list extended with chart_grid.js + command_palette.js; the WAVE-2
    # module-name assertions below are unchanged (see test_master_radar_wave3_integration.py).
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-B 2026-11-04): v3-0-8 -> v3-0-9
    assert "radar-bourse-static-v3-0-9" in sw
    assert "radar-bourse-static-v3-0-8" not in sw
    for name in WAVE2_MODULE_NAMES:
        assert f"/static/js/modules/render/{name}" in sw


def test_winner_box_reads_actual_oos_contract_keys():
    """AUDIT-MR2 O2 sync (additive pin): the optimizer winner box must read
    the ACTUAL /optimize response keys (oos_evaluated_once / is_objective_value
    / oos_objective_value / bonferroni_note) — not the initially guessed
    aliases that rendered honest dashes instead of the real confirmation."""
    bc = _read(WAVE2_MODULES[0])
    assert "oos_evaluated_once" in bc
    assert "is_objective_value" in bc and "oos_objective_value" in bc
    assert "bonferroni_note" in bc
    # the primary note key must be the real one; the guessed alias is demoted
    # to a harmless fallback (kept defensive, never the primary source)
    assert 'pick(oos, ["confirmed", "ok", "passed"])' not in bc
    assert "res.bonferroni_note ||" in bc


def test_replay_half_speed_button_and_parsing():
    """MR-B3-03 increment (WAVE-2 integration): a ۰.۵× slow replay speed must
    exist and be wired with parseFloat (parseInt('0.5') === 0 would silently
    fall back to 5×)."""
    idx = _read(ROOT / "frontend" / "index.html")
    fx = _read(ROOT / "frontend" / "js" / "modules" / "forex.js")
    assert 'data-sp="0.5"' in idx
    assert "parseFloat(b.dataset.sp)" in fx
    assert "parseInt(b.dataset.sp" not in fx
