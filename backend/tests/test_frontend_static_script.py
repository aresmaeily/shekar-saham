import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_static_validator_contract():
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
    # WS-10 (2026-11-02, owner directive): the "chartpro" pro-chart tab was
    # added -> 25 tabs/panels. Counter pin updated with the feature; every
    # structural check (matching panel, no orphans/duplicates) unchanged.
    # MASTER-RADAR (2026-11-04): the "strategylab" tab (Strategy Lab studio +
    # Indicator Manager) was added -> 26 tabs/panels. Same recorded counter-pin
    # bump discipline; structural invariants unchanged.
    # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-2 2026-11-04): 26 -> 29 —
    # three new product tabs (backtestcenter / forwardcenter / dataquality)
    # were added WITH this wave; structural invariants unchanged.
    assert data["tabs"]["tabs_count"] == 29
    assert data["tabs"]["panels_count"] == 29
    assert data["tabs"]["missing_panels"] == []
    assert data["tabs"]["orphan_panels"] == []
    assert data["duplicate_ids"]["index"] == []
    assert data["duplicate_ids"]["symbol"] == []
    assert data["missing_js_imports"] == []
