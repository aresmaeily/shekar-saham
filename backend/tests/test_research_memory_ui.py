"""Static gates for the 2026-11-08 owner-directive frontend increments:
- product loops tab: AI-3 durable memory + audit trail section (read-only)
  + Golden Set v2 report section (no-superiority banner);
- AI-MA tab: artifact content viewer + session run history;
- command palette integration via [data-palette-label] (keyboard access).

Mirrors the shipped static-gate discipline: api()-only HTTP boundary,
esc() everywhere, trust labels from server fields only, user-action-only.
"""

from __future__ import annotations

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
INDEX = FRONTEND / "index.html"
PL_UI = FRONTEND / "js" / "modules" / "render" / "product_loops_ui.js"
AIMA_UI = FRONTEND / "js" / "modules" / "render" / "ai_ma_ui.js"
PALETTE = FRONTEND / "js" / "modules" / "command_palette.js"


def test_memory_and_goldenset_elements_present_unique() -> None:
    html = INDEX.read_text(encoding="utf-8")
    for el in (
        "plMemPosture",
        "plMemIntegrity",
        "plMemAudit",
        "plMemBackup",
        "plMemOut",
        "plGs2Report",
        "plGs2Out",
    ):
        assert len(re.findall(f'id="{el}"', html)) == 1, f"{el} must exist exactly once"


def test_memory_surface_is_read_only_and_action_only() -> None:
    js = PL_UI.read_text(encoding="utf-8")
    # api()-only boundary: every memory/goldenset call goes through api(
    for endpoint in (
        '"/api/v10/memory/posture"',
        '"/api/v10/memory/integrity"',
        '"/api/v10/memory/audit"',
        '"/api/v10/productloops/goldenset/v2/report"',
    ):
        assert endpoint in js
    # no direct fetch in the module at all (boundary discipline)
    assert not re.search(r"\bfetch\(", js)
    # no delete/purge ACTION exists in the memory surface (the word appears
    # only inside server-provided disclosure strings / comments)
    assert "/memory/purge" not in js and "/memory/delete" not in js
    assert "/memory/episodic" not in js  # write path deliberately NOT exposed client-side
    assert "/lessons" not in js


def test_memory_render_escapes_server_fields() -> None:
    js = PL_UI.read_text(encoding="utf-8")
    # every interpolated dynamic field in the new sections goes through esc(
    for fn in ("loadMemoryPosture", "loadMemoryIntegrity", "loadMemoryAudit", "runMemoryBackup", "loadGoldenSetV2Report"):
        assert f"function {fn}" in js or fn in js


def test_no_superiority_banner_pinned_in_ui() -> None:
    js = PL_UI.read_text(encoding="utf-8")
    assert "بدون ادعای برتری" in js  # visible banner chip


def test_aima_artifact_viewer_and_history_present() -> None:
    js = AIMA_UI.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")
    # per-step artifact content viewer renders ONLY server payloads
    assert "artifact_contents" in js
    assert "JSON.stringify(c, null, 2)" in js  # verbatim server payload, esc'd on output
    assert "esc(JSON.stringify(c" in js
    # session run history: client-session only, bounded, no persistence
    assert "RUN_HISTORY_MAX" in js
    assert "runHistory" in js
    assert 'id="amHistoryOut"' in html
    assert "تاریخچه اجراهای این نشست" in html
    # localStorage/sessionStorage must NOT be used for run history
    assert "localStorage" not in js and "sessionStorage" not in js


def test_palette_labels_present_for_keyboard_access() -> None:
    html = INDEX.read_text(encoding="utf-8")
    assert 'data-palette-label="هوش چندعاملی: اجرای ارکستراسیون"' in html
    assert 'data-palette-label="هوش چندعاملی: خواندن وضعیت متخصص‌ها"' in html
    assert 'data-palette-label="حافظه پژوهش: خواندن وضعیت"' in html
    assert 'data-palette-label="حلقه‌های محصول: گزارش Golden Set v2"' in html
    pal = PALETTE.read_text(encoding="utf-8")
    assert "[data-palette-label]" in pal  # the palette picks them up
    assert "el.click()" in pal  # execution = the element's own click action


def test_tab_count_unchanged_no_new_tab_added() -> None:
    html = INDEX.read_text(encoding="utf-8")
    tabs = re.findall(r'data-tab="([a-z-]+)"', html)
    assert len(tabs) == 32, f"tab count must stay 32 (counter-pin discipline), got {len(tabs)}"
    assert "aima" in tabs  # AI-MA tab intact
    # the new sections live INSIDE tab-loops (no tab inflation)
    loops_start = html.index('id="tab-loops"')
    aistudio_start = html.index('id="tab-aistudio"')
    section = html[loops_start:aistudio_start]
    assert "plMemPosture" in section and "plGs2Report" in section
