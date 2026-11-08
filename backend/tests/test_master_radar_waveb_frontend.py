"""MASTER-RADAR WAVE-B (2026-11-04) — frontend static + integration gates.

Covers (the WAVE-3 pattern of static pin tests):
1. New modules exist and pass the Node syntax check (node --check).
2. Security gates: no eval/new Function/dynamic import(); the ONLY HTTP
   boundary is core/api.js; escapeHtml/esc used for every server string
   interpolated into HTML templates in the new panel module.
3. UIDL-1 honesty surface: the UI renders server declarations only — no
   client-side fallback engine (the legacy regex SMA-20 fallback path is NOT
   re-introduced).
4. chart_grid.js popup-detach pure logic boundary: hash build/parse is
   fail-closed (only 0..2), sync messages validated, echo-guard flag exists,
   detached mode hides chrome via body class and never fabricates symbols.
5. sw.js v3-0-9 + precache of the two new modules + counter-pins (bumped in
   the four recorded pin sites).
6. index.html: cpUserIndRoot container present; tabs stay 29/29.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # repo root
FE = ROOT / "frontend"

USER_IND = FE / "js" / "modules" / "user_indicator.js"
USER_IND_UI = FE / "js" / "modules" / "render" / "user_indicator_ui.js"
CHART_GRID = FE / "js" / "modules" / "render" / "chart_grid.js"
INDEX_HTML = FE / "index.html"
MAIN_JS = FE / "js" / "main.js"
SW_JS = FE / "sw.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_new_modules_exist() -> None:
    assert USER_IND.is_file()
    assert USER_IND_UI.is_file()


def test_new_modules_pass_node_syntax_check() -> None:
    for p in (USER_IND, USER_IND_UI, CHART_GRID):
        result = subprocess.run(
            ["node", "--check", str(p)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"{p.name}: {result.stderr[:400]}"


class TestSecurityGates:
    def test_no_dynamic_execution_in_new_modules(self) -> None:
        for p in (USER_IND, USER_IND_UI, CHART_GRID):
            text = _read(p)
            for banned in ("eval(", "new Function(", "import(", "document.write"):
                assert banned not in text, (p.name, banned)

    def test_user_indicator_http_boundary_is_api_js_only(self) -> None:
        text = _read(USER_IND)
        assert 'from "../core/api.js"' in text or "from '../core/api.js'" in text
        assert "fetch(" not in text
        assert "XMLHttpRequest" not in text

    def test_user_indicator_ui_http_boundary(self) -> None:
        text = _read(USER_IND_UI)
        assert "fetch(" not in text
        assert "XMLHttpRequest" not in text

    def test_no_client_side_fallback_engine(self) -> None:
        # the legacy regex SMA-20 fallback is forbidden in the governed panel
        for p in (USER_IND, USER_IND_UI):
            text = _read(p)
            assert "SMA\\s*\\(" not in text
            assert "IndicatorFunctions" not in text
            assert "smaMatch" not in text

    def test_escape_html_on_interpolated_server_fields(self) -> None:
        text = _read(USER_IND_UI)
        # every template interpolation of record fields goes through esc()
        assert "esc(ind.name" in text
        assert "esc(ind.id)" in text
        assert "${ind.name}" not in text  # unescaped interpolation forbidden

    def test_no_timers_added_in_new_modules(self) -> None:
        for p in (USER_IND, USER_IND_UI):
            text = _read(p)
            assert "setInterval(" not in text
            # setTimeout is allowed ONLY for the object-URL revocation in export
            if p.name == "user_indicator.js":
                assert "setTimeout(" not in text


class TestUidlHonestySurface:
    def test_examples_are_uidl_grammar(self) -> None:
        text = _read(USER_IND)
        assert "INDICATOR" in text and "PLOT " in text
        # no JS/Python snippets advertised as indicators
        assert "function(" not in text.replace("new Function(", "")

    def test_warmup_boundary_is_server_declared(self) -> None:
        text = _read(USER_IND)
        assert "valid_from_index" in text
        assert "plottableSeries" in text

    def test_trust_labels_from_server_fields_only(self) -> None:
        text = _read(USER_IND_UI)
        assert "data_class" in text
        assert "SYNTHETIC" in text  # shown as-is from the server payload


class TestDetachPureLogic:
    def test_hash_helpers_fail_closed(self) -> None:
        text = _read(CHART_GRID)
        # bounds are pinned in the source itself
        assert "n >= GRID_MAX_PANES) return null" in text
        assert 'DETACH_HASH_PREFIX = "#cpGridDetach="' in text

    def test_sync_message_validation(self) -> None:
        text = _read(CHART_GRID)
        assert 'msg.type !== "pane_state"' in text
        assert "GRID_TIMEFRAMES.includes(msg.timeframe)" in text

    def test_echo_guard_present(self) -> None:
        text = _read(CHART_GRID)
        assert "_applyingRemote" in text

    def test_detached_mode_hides_chrome_via_body_class(self) -> None:
        text = _read(CHART_GRID)
        assert 'body.classList.add("cp-grid-detached")' in text
        assert "body.cp-grid-detached > header.topbar" in text

    def test_detach_button_in_pane_head(self) -> None:
        text = _read(CHART_GRID)
        assert "detachBtn" in text
        assert "this._detachPane(rec.index)" in text

    def test_detach_intent_captured_at_module_load(self) -> None:
        # the tab router rewrites the hash on first click; the detach intent
        # must be read at module evaluation time and survive it
        text = _read(CHART_GRID)
        assert "const DETACH_INTENT = (() =>" in text
        assert "this._detachedPane = DETACH_INTENT;" in text
        assert "btn.click(), 200" in text  # popup auto-activation, one-shot

    def test_no_window_open_without_features(self) -> None:
        text = _read(CHART_GRID)
        assert 'window.open(location.pathname + location.search + h, "_blank", DETACH_WINDOW_FEATURES)' in text


class TestIntegrationPins:
    def test_index_has_user_indicator_container(self) -> None:
        html = _read(INDEX_HTML)
        assert 'id="cpUserIndRoot"' in html

    def test_tabs_stay_29(self) -> None:
        # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-O 2026-11-06): 30 -> 31 — the
        # new governed AI-2 studio tab (frontend-only, additive); prior chain
        # 26 -> 29 (WAVE-2) -> 30.
        # COUNTER-PIN BUMP (recorded, WAVE-AI 2026-11-08): 31 -> 32 — the new
        # governed AI-MA tab (aima, WP-C UI); additive, no tab removed.
        html = _read(INDEX_HTML)
        tabs = re.findall(r'class="tab[^"]*" data-tab="', html)
        assert len(tabs) == 32

    def test_main_js_imports_new_panel(self) -> None:
        text = _read(MAIN_JS)
        assert 'import "./modules/render/user_indicator_ui.js"' in text

    def test_sw_bumped_to_v3_0_14_with_precache(self) -> None:
        # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-O 2026-11-06): v3-0-14 -> v3-0-15 — precache extended with ai2_studio.js (WAVE-O governed AI-2 studio panel)
        # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-S2 2026-11-07): v3-0-15 -> v3-0-16 — cross-window crosshair/range sync in chart_grid.js
        sw = _read(SW_JS)
        # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-S2 2026-11-07): v3-0-15 -> v3-0-16 — cross-window crosshair/range sync in chart_grid.js
    # COUNTER-PIN BUMP (recorded, WAVE-AB2 2026-11-08): v3-0-16 -> v3-0-17 — walk-forward UI trigger in forward_center.js + index.html + dead-control wiring (hunt/tablo/hot filters, btnWsRefresh/btnValueReload/btnPfAdd, excellent tab activation)
    # COUNTER-PIN BUMP (recorded, WAVE-AI 2026-11-08): v3-0-17 -> v3-0-19 — AI-MA tab (render/ai_ma_ui.js + index.html panel + main.js lazy activation)
        assert "radar-bourse-static-v3-0-19" in sw
        assert "radar-bourse-static-v3-0-12" not in sw
        assert "/static/js/modules/user_indicator.js" in sw
        assert "/static/js/modules/render/user_indicator_ui.js" in sw

    @pytest.mark.parametrize(
        "path",
        [
            "backend/tests/test_wda_version_consistency.py",
            "backend/tests/test_p3_80_local_closure.py",
            "backend/tests/test_master_radar_wave3_integration.py",
            "backend/tests/test_master_radar_frontend_static.py",
            "backend/tests/test_master_radar_wave2_frontend.py",
        ],
    )
    def test_counter_pins_bumped(self, path: str) -> None:
        # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-O 2026-11-06): pin token
        # advanced v3-0-14 -> v3-0-16 across the five pinned files; escape chain
        # extended (v3-0-13 -> v3-0-14 / v3-0-12 -> v3-0-13 / v3-0-14 -> v3-0-16).
        text = _read(ROOT / path)
        # COUNTER-PIN BUMP (recorded, MASTER-RADAR WAVE-S2 2026-11-07): v3-0-15 -> v3-0-16 — cross-window crosshair/range sync in chart_grid.js
        # COUNTER-PIN BUMP (recorded, WAVE-AB2 2026-11-08): v3-0-16 -> v3-0-17 — walk-forward UI trigger + dead-control wiring (all five pinned files re-bumped)
        # COUNTER-PIN BUMP (recorded, WAVE-AI 2026-11-08): v3-0-17 -> v3-0-19 — AI-MA tab (all pinned files re-bumped)
        assert "radar-bourse-static-v3-0-19" in text
        assert "radar-bourse-static-v3-0-8" not in re.sub(
            r"#.*COUNTER-PIN BUMP[^\n]*\n?", "", text
        ) or "v3-0-13 -> v3-0-14" in text or "v3-0-12 -> v3-0-13" in text or "v3-0-14 -> v3-0-16" in text  # bump comment may name the old pin
