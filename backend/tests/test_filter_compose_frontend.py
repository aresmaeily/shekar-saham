"""D-O2 filter-compose frontend static contract tests (additive).

Pins the UI contract of the multidimensional compose panel: elements exist,
the module binds them, the API paths are the D-O2 endpoints, the panel is
read-only (no timers, no alert dispatch) and always renders the honest
mock/trust disclosure. Follows the existing static-contract test pattern
(test_filter_intelligence_ui_workflow.py).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_compose_panel_elements_exist_in_filter_tab():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    for needle in (
        'id="btnComposeRun"',
        'id="composeFilters"',
        'id="composeExprs"',
        'id="composeMinMatches"',
        'id="composeTrust"',
        'id="composeNotes"',
        'id="composeTable"',
        "تحلیل چندبعدی",
        "حالت رانتی = حداقل ۲ تطبیق",
        "ترکیب AND/OR سطح‌دوم عمداً پشتیبانی نمی‌شود",
    ):
        assert needle in html, needle
    # panel lives INSIDE the existing filter tab (no new tab, tabs count unchanged)
    tab_filter_start = html.index('id="tab-filter"')
    tab_filter_intel_start = html.index('id="tab-filter-intel"')
    assert tab_filter_start < html.index('id="btnComposeRun"') < tab_filter_intel_start


def test_compose_binds_and_uses_d_o2_endpoints():
    js = (ROOT / "frontend/js/tabs/forms.js").read_text(encoding="utf-8")
    assert "export function bindFilterCompose" in js
    assert '"/api/filter/compose/presets"' in js
    assert '"/api/filter/compose"' in js
    # min_matches control (رانتی rule documented default 2)
    assert "composeMinMatches" in js
    assert 'min_matches: minMatches' in js
    # per-result matched chips carry filter identity
    assert "match_count" in js
    assert "m.name_fa" in js or "name_fa" in js


def test_compose_panel_read_only_and_honest_trust():
    js = (ROOT / "frontend/js/tabs/forms.js").read_text(encoding="utf-8")
    # the compose renderer exists and discloses trust + errors honestly
    assert "live_verified" in js
    assert "دادهٔ شبیه‌سازی‌شده" in js
    assert "degenerate" in js
    assert "unsupported" in js
    # read-only panel: no auto-refresh timers and no alert dispatch inside the compose section
    compose_src = js[js.index("export function bindFilterCompose") : js.index("/* ----------------------------- هوش فیلتر")]
    for forbidden in ("setInterval", "setTimeout", "/api/alerts", "notify"):
        assert forbidden not in compose_src, forbidden


def test_main_js_wires_compose_once():
    js = (ROOT / "frontend/js/main.js").read_text(encoding="utf-8")
    assert js.count("bindFilterCompose") == 2  # import + one call site


def test_sw_version_bumped_for_compose_panel():
    sw = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    assert "radar-bourse-static-v3-0-21" in sw
    assert "D-O2 filter-compose" in sw
