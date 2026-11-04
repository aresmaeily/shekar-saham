"""MASTER-RADAR WAVE-3 — static gates for the chart-pro increments.

Source-scan gates only (no network, no runtime UI), in the established style
of test_master_radar_wave2_chartstatic.py. They pin the WAVE-3 increments in
``frontend/js/modules/render/chart_pro.js`` (additive edits) and the new
``frontend/js/modules/render/chart_grid.js`` module:

1. server-derived chart types (renko/range/kagi/pnf/linebreak) — the client
   NEVER fabricates derived bars locally: the render posts to
   POST /api/v10/chartpro/{symbol}/derived, native overlays (MA/EMA/BB) and
   volume are deliberately emptied in derived views (they are computed on
   NATIVE bars and would be semantically wrong on derived bricks), failures
   keep the previous valid view with an honest Persian status (no silent
   fallback to native candles), and drawing-point collection is disabled
   while a derived type is active;
2. crosshair readout (#cpCrossReadout) — O/H/L/C/V only from the loaded
   series + labeling fields verbatim from the server object, defensive
   null-check on the container (integration adds it later), nothing rendered
   when the hovered bar is not found;
3. chart grid module (MR-B2-01) — localStorage envelope radar.chartgrid.v1
   with fail-closed quarantine key radar.chartgrid.corrupted, the three sync
   toggles (range/crosshair/symbol_follow), the 1/2/4 layout map, api() as
   the only HTTP boundary, and the documented interaction-time-only
   symbol-follow behavior (no background listeners).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHART_PRO = ROOT / "frontend" / "js" / "modules" / "render" / "chart_pro.js"
CHART_GRID = ROOT / "frontend" / "js" / "modules" / "render" / "chart_grid.js"

DERIVED_TYPES = ["renko", "range", "kagi", "pnf", "linebreak"]
DERIVED_POST_PATH = "/derived"
GRID_STORAGE_KEY = "radar.chartgrid.v1"
GRID_CORRUPTED_KEY = "radar.chartgrid.corrupted"

DRAW_DISABLED_HINT = "ابزار رسم فقط در نمای کندل بومی فعال است"
DERIVED_ERROR_PREFIX = "خطای بارگذاری نمودار مشتق"
DERIVED_ERROR_KEEP_VIEW = "نمای قبلی حفظ شد"
OVERLAY_HIDE_DECISION_MARKER = "تصمیم آگاهانه"
SYNC_LABELS = ("همگام‌سازی بازه", "همگام‌سازی کراس‌هیر", "همگام‌سازی نماد")
SYNC_KEYS = ("range", "crosshair", "symbol_follow")
LAYOUT_MAP = "[1, 2, 4]"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _method_body(source: str, signature: str) -> str:
    """Extract a class-method body up to its closing 2-space brace — the same
    fail-closed extraction style used by the WAVE-2 chip gate."""
    m = re.search(re.escape(signature) + r"[\s\S]*?\n  \}", source)
    assert m, f"method not found: {signature}"
    return m.group(0)


def test_derived_chart_types_declared_in_chart_pro():
    cp = _read(CHART_PRO)
    # one authoritative list constant — every derived type string present
    assert "DERIVED_TYPES" in cp
    for t in DERIVED_TYPES:
        assert f'"{t}"' in cp, f"derived type {t} missing"
    assert 'const DERIVED_TYPES = ["renko", "range", "kagi", "pnf", "linebreak"];' in cp
    # routing helper used by both the type applier and the loader
    assert "_isDerivedType()" in cp
    assert cp.count("DERIVED_TYPES.includes(") >= 2


def test_derived_post_path_and_request_contract():
    cp = _read(CHART_PRO)
    loader = _method_body(cp, "async _loadDerived(opts = {}) {")
    # only the designated endpoint, only POST, uppercase type, empty params
    assert DERIVED_POST_PATH in loader
    assert "/api/v10/chartpro/" in loader
    assert 'method: "POST"' in loader
    assert "String(type).toUpperCase()" in loader
    assert "timeframe: this.timeframe" in loader
    assert "limit: this.limit" in loader
    assert "params: {}" in loader
    # the client must NOT fabricate derived bars locally (no heikin-ashi reuse here)
    assert "_heikinAshi" not in loader


def test_derived_render_paths_bars_and_kagi_points():
    cp = _read(CHART_PRO)
    loader = _method_body(cp, "async _loadDerived(opts = {}) {")
    # renko/range/pnf/linebreak: server OHLC bars onto the existing candle series
    assert "res?.bars" in loader
    assert "this.candleSeries.setData(bars)" in loader
    # kagi: server points onto a line series (the _typeSeries mechanism)
    assert 'type === "kagi"' in loader
    assert "res?.points" in loader
    assert "addLineSeries" in loader
    # derived data kept separately for the crosshair readout
    assert "this.currentDerivedData = bars" in loader
    assert "this.currentDerivedData = points" in loader


def test_derived_hides_native_overlays_deliberately():
    cp = _read(CHART_PRO)
    assert "_hideNativeOverlays()" in cp
    hide = _method_body(cp, "_hideNativeOverlays() {")
    # overlays and volume are emptied — never recomputed on derived bars
    assert "this.volumeSeries.setData([])" in hide
    assert '["ma20", "ma50", "ema20", "bbU", "bbM", "bbL"]' in hide
    # the decision is documented in-product, not a silent side effect
    assert OVERLAY_HIDE_DECISION_MARKER in cp
    # loader actually calls it + flags the derived view for state guards
    loader = _method_body(cp, "async _loadDerived(opts = {}) {")
    assert "this._hideNativeOverlays()" in loader
    assert "this._derivedActive = true" in loader


def test_derived_failure_keeps_previous_view_honestly():
    cp = _read(CHART_PRO)
    loader = _method_body(cp, "async _loadDerived(opts = {}) {")
    assert "catch (e)" in loader
    # honest Persian status — the user sees the failure, previous view stays
    assert DERIVED_ERROR_PREFIX in loader
    assert DERIVED_ERROR_KEEP_VIEW in loader
    # NO silent fallback: the failure path must not re-render native candles
    # or re-dispatch a native load from inside the derived loader
    assert "candleSeries.setData(this.currentData" not in loader
    assert "loadAndRender" not in loader.split("catch (e)")[1]


def test_drawing_disabled_while_derived_active():
    cp = _read(CHART_PRO)
    click = _method_body(cp, "_onCanvasClick(e) {")
    # guard at the very entry of the click handler — before any point is collected
    assert "this._isDerivedType()" in click
    assert DRAW_DISABLED_HINT in click
    assert click.index("this._isDerivedType()") < click.index('const tool = this.drawState.tool;')


def test_crosshair_readout_defensive_pattern():
    cp = _read(CHART_PRO)
    # subscription is wired on the main chart (Lightweight Charts v4 API)
    assert "subscribeCrosshairMove" in cp
    readout = _method_body(cp, "_onCrosshairMove(param) {")
    # defensive container check — integration adds #cpCrossReadout later
    assert 'document.getElementById("cpCrossReadout")' in readout
    assert "if (!el) return;" in readout
    # empty hover → clear; bar not found → clear (NEVER invent values)
    assert readout.count('el.textContent = "";') >= 2
    # OHLC only from the loaded series; derived view reads currentDerivedData
    assert "currentDerivedData" in readout
    assert "currentData" in readout
    # labeling fields verbatim from the server object (same pattern as the chip)
    assert "lastLabeling" in readout
    assert "bar_class" in readout
    assert "method" in readout


def test_last_labeling_stored_and_chip_reused_on_both_paths():
    cp = _read(CHART_PRO)
    # the server labeling object is stored on BOTH the native and derived paths
    assert cp.count("this.lastLabeling = res?.labeling ?? null;") >= 2
    # and the EXISTING chip renderer is reused — no new trust-labeling code
    assert cp.count("this._renderLabelingChip(this.lastLabeling);") >= 2


def test_chart_grid_module_contract_and_sync_keys():
    g = _read(CHART_GRID)
    # storage envelope keys + schema + quarantine evidence key
    assert GRID_STORAGE_KEY in g
    assert GRID_CORRUPTED_KEY in g
    assert '"saved_at_iso"' in g or "saved_at_iso:" in g
    # the three sync toggles: keys + honest Persian labels
    for key in SYNC_KEYS:
        assert f'"{key}"' in g
    for label in SYNC_LABELS:
        assert label in g
    # layout map 1/2/4 with Persian digit labels
    assert LAYOUT_MAP in g
    for d in ("۱", "۲", "۴"):
        assert d in g


def test_chart_grid_defensive_container_and_symbol_follow_marker():
    g = _read(CHART_GRID)
    # defensive no-op when the integration container is absent
    assert 'document.getElementById("cpGridRoot") === null' in g
    # controls render into #cpGridBar when integration provides it (defensive)
    assert '"cpGridBar"' in g
    assert "if (!bar) return;" in g
    # symbol-follow is documented as interaction-time-only (no background listener)
    assert "symbol_follow" in g
    assert "لحظه تعامل" in g
    assert "window.chartGrid = instance" in g  # exposed for command_palette


def test_chart_grid_network_boundary_and_forbidden_primitives():
    g = _read(CHART_GRID)
    assert 'from "../../core/api.js"' in g  # api() is the ONLY HTTP boundary
    for primitive in ("fetch(", "WebSocket(", "eval(", "new Function", "XMLHttpRequest", "importScripts"):
        assert primitive not in g, f"chart_grid contains forbidden primitive {primitive!r}"


def test_chart_grid_persistence_fail_closed_validator():
    g = _read(CHART_GRID)
    # fail-closed validator in the workspace.js style
    assert "gridValidateState" in g
    assert '"unknown fields dropped: "' in g
    assert "corrupted_quarantined" in g
    assert "quarantined_at_iso" in g
    # debounced save (single setTimeout) — not a scheduler
    assert "GRID_SAVE_DEBOUNCE_MS = 600" in g
    assert "clearTimeout" in g and "setTimeout" in g


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not available in PATH")
def test_wave3_chart_modules_pass_node_syntax_check():
    for p in (CHART_PRO, CHART_GRID):
        result = subprocess.run(
            ["node", "--check", str(p)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"{p.name}: {result.stderr}"
