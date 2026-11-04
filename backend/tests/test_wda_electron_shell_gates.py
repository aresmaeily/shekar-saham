"""WDA-1 — Electron shell gates (static contract tests).

Static assertions on ``electron/main.js`` following the established
read-only pattern (see ``test_gov24_desktop_shell.py`` and
``test_p3_79_local_hardening.py`` — the shell is never executed in pytest).

Scope notes (honest labeling):
- Renderer security: ``contextIsolation: true`` / ``nodeIntegration: false`` /
  ``enableRemoteModule: false`` are explicit in source. A ``sandbox`` key is
  NOT explicitly set — Electron >= 20 sandboxes renderers by default, so this
  suite pins the ABSENCE of ``sandbox: false`` (regression guard) instead of
  fabricating a literal that is not in the source. Same for ``webSecurity``
  (default true; absence of ``webSecurity: false`` is pinned) and ``preload``
  (not used; absence pinned so its introduction must be a conscious change).
- IPC: the shell registers no ``ipcMain``/``ipcRenderer`` handlers at all, so
  an IPC allowlist is not applicable today; the empty surface is pinned so
  any future IPC must be added deliberately (with an allowlist).
- WDA-1 additive hardening pinned here: app-level ``render-process-gone`` /
  ``child-process-gone`` / ``uncaughtException`` / ``unhandledRejection``
  handlers with a rate-limited single renderer reload.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_JS = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_chartpro_menu_item_and_route_present():
    """WS-10 menu item routes to the chartpro deep-link."""
    assert "📈 چارت حرفه‌ای" in MAIN_JS
    assert "loadURL(startUrl + '/#/chartpro')" in MAIN_JS


def test_chartpro_route_targets_a_real_frontend_tab():
    """The shell route must resolve to an existing tab + panel (index.html)."""
    assert 'data-tab="chartpro"' in INDEX_HTML
    assert 'id="tab-chartpro"' in INDEX_HTML


def test_renderer_security_posture_pinned():
    """Isolation settings that ARE true in source are pinned verbatim;
    dangerous opt-outs are pinned as absent."""
    assert "nodeIntegration: false" in MAIN_JS
    assert "contextIsolation: true" in MAIN_JS
    assert "enableRemoteModule: false" in MAIN_JS
    assert "sandbox: false" not in MAIN_JS
    assert "webSecurity: false" not in MAIN_JS
    assert "preload" not in MAIN_JS  # no preload script today — must stay a conscious change


def test_navigation_origin_guards_present():
    """Origin allowlist: will-navigate/will-redirect preventDefault on foreign
    origins; setWindowOpenHandler denies foreign popups."""
    assert "will-navigate" in MAIN_JS
    assert "will-redirect" in MAIN_JS
    assert "isAllowedNavigation" in MAIN_JS
    assert "setWindowOpenHandler" in MAIN_JS
    assert "event.preventDefault()" in MAIN_JS
    assert "action: 'deny'" in MAIN_JS


def test_no_ipc_surface_so_allowlist_not_applicable():
    """Empty IPC surface today — pinned so any future handler addition is a
    conscious, allowlisted change (docstring rationale)."""
    assert "ipcMain" not in MAIN_JS
    assert "ipcRenderer" not in MAIN_JS


def test_default_origin_is_local_loopback():
    """The shell loads the local backend by default; no remote default origin."""
    assert "http://127.0.0.1:8000" in MAIN_JS
    assert MAIN_JS.count("http://127.0.0.1:8000") >= 2  # startUrl fallback + allowedOrigin fallback


def test_window_lifecycle_handlers_present():
    assert "window-all-closed" in MAIN_JS
    assert "app.quit()" in MAIN_JS
    assert "app.on('activate'" in MAIN_JS
    assert "BrowserWindow.getAllWindows()" in MAIN_JS


def test_app_level_error_handlers_present_wda1():
    """WDA-1 (2026-11-03) additive hardening: renderer/child-process crash
    events and main-process uncaught errors are handled, not dropped."""
    assert "render-process-gone" in MAIN_JS
    assert "child-process-gone" in MAIN_JS
    assert "process.on('uncaughtException'" in MAIN_JS
    assert "process.on('unhandledRejection'" in MAIN_JS


def test_renderer_reload_is_rate_limited_and_guarded():
    """The reload-on-crash path is guarded: no reload on clean exit, destroyed
    windows skipped, and at most one reload per 5 seconds (no loop)."""
    assert "details.reason !== 'clean-exit'" in MAIN_JS
    assert "!mainWindow.isDestroyed()" in MAIN_JS
    assert "_lastRendererReloadAt" in MAIN_JS
    assert "5000" in MAIN_JS


def test_external_targets_open_in_os_browser():
    """Foreign origins are handed to the OS browser (never rendered in-shell)."""
    assert MAIN_JS.count("shell.openExternal") >= 2
