# -*- coding: utf-8 -*-
"""MASTER-RADAR WAVE-S2 — cross-window crosshair/range sync static gates.

WAVE-S2 closes the recorded WAVE-B residual: inter-window crosshair/range
sync (previously only symbol/timeframe crossed windows). These pins are
ADDITIVE — no existing assertion was weakened, skipped, or deleted. They
scan the chart_grid.js source for the new fail-closed message validators,
the echo guards, the sender-identity rule (pane === -1 means the primary
chart), and the honest-note updates, mirroring the WAVE-2/3/B static-pin
discipline. Browser-level behavior of the same surface is exercised by the
recorded runtime/E2E evidence, not here.
"""
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
GRID = (FRONTEND / "js" / "modules" / "render" / "chart_grid.js").read_text(encoding="utf-8")


def test_s2_validators_present_and_fail_closed():
    assert 'msg.type !== "pane_cross"' in GRID
    assert 'msg.type !== "pane_cross_clear"' in GRID
    assert 'msg.type !== "pane_range"' in GRID
    # sender identity: -1 (primary) .. GRID_MAX_PANES-1, integer-guarded
    assert "n < -1 || n >= GRID_MAX_PANES" in GRID
    # range bounds finite + ordered
    assert "Number.isFinite(f) && Number.isFinite(t) && f <= t" in GRID
    # cross requires a non-null time and finite value
    assert "if (msg.time == null) return false;" in GRID
    assert "Number.isFinite(Number(msg.value))" in GRID


def test_s2_channel_dispatcher_dispatches_all_four_types():
    assert "if (validDetachSyncMsg(msg))" in GRID
    assert "if (validGridCrossMsg(msg))" in GRID
    assert "if (validGridCrossClearMsg(msg))" in GRID
    assert "if (validGridRangeMsg(msg))" in GRID
    assert "fail-closed" in GRID


def test_s2_broadcast_helpers_gated_by_sync_toggles():
    assert 'if (!this._channel || !this.state.sync.crosshair) return;' in GRID
    assert 'if (!this._channel || !this.state.sync.range || !range) return;' in GRID
    assert '{ type: "pane_cross", pane: paneIndex, time, value }' in GRID
    assert '{ type: "pane_cross_clear", pane: paneIndex }' in GRID
    assert '{ type: "pane_range", pane: paneIndex, from, to }' in GRID


def test_s2_echo_guards_double_layer():
    # remote-apply flag exists beside the WAVE-B flag
    assert "this._gridCrossRemote = false;" in GRID
    assert "this._gridCrossRemote = true;" in GRID
    # local pane crosshair handler refuses while a remote apply is in flight
    assert "if (!this.state.sync.crosshair || this._gridCrossRemote) return;" in GRID
    # remote range apply reuses the grid re-entrancy flag
    assert "this._gridSyncing = true;" in GRID
    # sender pane never applies to itself
    assert "if (p.index === sender) continue;" in GRID
    assert "if (other !== rec)" in GRID


def test_s2_primary_sender_identity_minus_one():
    assert 'this._broadcastRange(-1, range);' in GRID
    assert "this._broadcastCross(-1, param.time, param.point.y);" in GRID
    assert "this._broadcastCrossClear(-1);" in GRID
    # remote range from the primary must NOT be pushed back into the primary
    assert "if (primary && sender !== -1) primary.timeScale().setVisibleLogicalRange(range);" in GRID
    # remote cross from the primary must NOT be pushed back into the primary
    assert "if (sender !== -1) this._setPrimaryCrossAt(msg.time);" in GRID


def test_s2_no_fabricated_values_rule_preserved():
    # values ALWAYS come from local data — a missing time must never mint a price
    assert "این زمان در داده این پنل نیست — هیچ مقدار ساختگی" in GRID
    assert "if (!pt) return;" in GRID
    assert "if (val == null) return;" in GRID
    # primary lookup prefers derived data when active, then native
    assert "s.currentDerivedData && s.currentDerivedData.length ? s.currentDerivedData : s.currentData" in GRID


def test_s2_honest_notes_updated():
    assert "همگام‌سازی نماد/تایم‌فریم/بازه/کراس‌هیر دوسویه" in GRID
    assert "WAVE-S2" in GRID
    # the OLD honest note (crosshair/range NOT synced) must be gone
    assert "کراس‌هیر/بازه\n   * بین پنجره‌های جدا همگام نمی‌شود" not in GRID


def test_s2_zero_polling_unchanged():
    import re
    assert "setInterval" not in GRID, "WAVE-S2 must not add polling"
    assert "XMLHttpRequest" not in GRID and "WebSocket(" not in GRID


def test_s2_no_forbidden_primitives():
    for tok in ("eval(", "new Function(", "document.write(", "localStorage.setItem(  "):
        assert tok.strip() not in GRID


# ---------------- WAVE-S2W: Windows shell / installer payload gates ----------------

ELECTRON = Path(__file__).resolve().parents[2] / "electron"
MAIN_JS = (ELECTRON / "main.js").read_text(encoding="utf-8")
WFLOW = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8")
RUNBOOK = (Path(__file__).resolve().parents[2] / "docs" / "active" / "WINDOWS_PACKAGING_RUNBOOK_2026-11-05.md").read_text(encoding="utf-8")


def test_s2w_frontend_payload_bundled_in_installer_workflow():
    # the recorded payload defect: packaged app served /api/* but 404 on /
    assert "Copy-Item -Recurse -Force frontend electron/resources/frontend" in WFLOW
    assert "'electron/resources/frontend/index.html'" in WFLOW
    # payload verification step fails the build on an incomplete payload
    assert "Payload verification" in WFLOW
    assert "incomplete payload" in WFLOW
    assert "Write-Error" in WFLOW
    assert "frontend_files_bundled=" in WFLOW
    # ROOT = config.py parents[3] = resources/ — the copy target must match
    assert "parents[3]" in WFLOW


def test_s2w_non_loopback_override_enforced_not_log_only():
    assert "startUrl = loopbackDefault;" in MAIN_JS
    assert "refusing non-loopback RADAR_BOURSE_URL override" in MAIN_JS
    # the fallback is inside the refusal branch (enforced), not log-only
    assert MAIN_JS.index("refusing non-loopback") < MAIN_JS.index("startUrl = loopbackDefault;")
    assert "let startUrl" in MAIN_JS


def test_s2w_port_consistency_with_supervised_backend():
    assert "RADAR_BACKEND_PORT" in MAIN_JS
    assert "'http://127.0.0.1:' + backendPort" in MAIN_JS
    # backend_service resolves the same env var
    bs = (ELECTRON / "backend_service.js").read_text(encoding="utf-8")
    assert "RADAR_BACKEND_PORT" in bs


def test_s2w_degraded_page_dependency_hint():
    assert "ModuleNotFoundError" in MAIN_JS
    assert "pip install -r backend/requirements.txt" in MAIN_JS
    # still zero egress: data: URL page
    assert "data:text/html;charset=utf-8," in MAIN_JS


def test_s2w_runbook_drift_fixed():
    assert "backend_service.js` (supervised backend, WAVE-N remainder)" in RUNBOOK
    assert "BUILT IN AUTHORIZED CI" in RUNBOOK
    assert "scripts/windows/install.ps1" in RUNBOOK


def test_s2w_electron_lockfile_present():
    lock = ELECTRON / "package-lock.json"
    assert lock.exists(), "runbook npm ci requires the lockfile"
    import json
    data = json.loads(lock.read_text(encoding="utf-8"))
    assert data.get("lockfileVersion") == 3
    assert "node_modules/electron" in data.get("packages", {})
