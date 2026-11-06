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


# ---------------------------------------------------------------------------
# WAVE-N remainder (OA-1, 2026-11-06): supervised local backend lifecycle.
# Resolves the recorded "shell-does-not-spawn-backend" limitation: the shell
# now STARTS and SUPERVISES the bundled backend as a loopback-only child
# process with a bounded startup window + health check, graceful shutdown,
# bounded crash recovery, and an honest degraded-state surface. These are
# static contract pins (the shell is never executed in pytest).
# ---------------------------------------------------------------------------

BACKEND_SERVICE_JS = (ROOT / "electron" / "backend_service.js").read_text(encoding="utf-8")


def test_supervised_backend_module_exists_and_is_wired():
    """The shell wires the supervised backend service — the recorded
    residual is resolved, not silently inherited."""
    assert "require('./backend_service')" in MAIN_JS
    assert "backendService.start(" in MAIN_JS


def test_supervised_backend_binds_loopback_only():
    """Structural local-only binding: the child is spawned with
    --host 127.0.0.1 and HOST=127.0.0.1 env — never a wildcard interface."""
    assert "LOCAL_HOST = '127.0.0.1'" in BACKEND_SERVICE_JS
    assert "'--host', LOCAL_HOST" in BACKEND_SERVICE_JS
    assert "'--port', DEFAULT_PORT" in BACKEND_SERVICE_JS
    assert "HOST: LOCAL_HOST" in BACKEND_SERVICE_JS
    # no wildcard binding anywhere in the supervised spawn
    assert "--host 0.0.0.0" not in BACKEND_SERVICE_JS


def test_supervised_backend_health_check_is_loopback_bounded():
    """The startup window is bounded and the health poll targets the
    loopback /api/health endpoint only."""
    assert "BACKEND_STARTUP_TIMEOUT_MS" in BACKEND_SERVICE_JS
    assert "90000" in BACKEND_SERVICE_JS  # bounded startup window value
    assert "'/api/health'" in BACKEND_SERVICE_JS
    assert "host: LOCAL_HOST" in BACKEND_SERVICE_JS  # probe → loopback only


def test_supervised_backend_graceful_shutdown_bounded():
    """Quit path: graceful kill first, bounded grace window, then a forced
    kill — the backend is never left running silently."""
    assert "GRACEFUL_SHUTDOWN_MS" in BACKEND_SERVICE_JS
    assert "intentionalStop" in BACKEND_SERVICE_JS
    assert "taskkill" in BACKEND_SERVICE_JS  # forced kill on Windows
    assert "app.on('will-quit'" in MAIN_JS
    assert "backendService.stop()" in MAIN_JS


def test_supervised_backend_bounded_crash_recovery():
    """Unexpected backend exits restart a BOUNDED number of times with
    backoff — beyond the budget the state is honestly degraded."""
    assert "MAX_RESTARTS" in BACKEND_SERVICE_JS
    assert "RESTART_BACKOFF_MS" in BACKEND_SERVICE_JS
    assert "restart-budget-exhausted" in BACKEND_SERVICE_JS
    assert "restarts < MAX_RESTARTS" in BACKEND_SERVICE_JS


def test_supervised_backend_degraded_state_is_honest_never_silent():
    """Degraded states are machine-labeled and surfaced to the user via a
    LOCAL data:-URL status page (no remote content, no egress)."""
    assert "'degraded'" in BACKEND_SERVICE_JS
    assert "python-not-found" in BACKEND_SERVICE_JS
    assert "startup-timeout" in BACKEND_SERVICE_JS
    assert "loadDegradedStatusPage" in MAIN_JS
    assert "data:text/html" in MAIN_JS
    assert "127.0.0.1" in MAIN_JS  # the status page names the loopback fact


def test_supervised_backend_has_no_remote_paths():
    """The supervised service contains NO remote URL literal, NO updater, NO
    fetch path — its only egress is the loopback health probe."""
    for banned in ("https://", "http://", "autoUpdate", "update-electron-app", "download"):
        assert banned not in BACKEND_SERVICE_JS, banned


def test_supervised_backend_respects_fail_closed_gates():
    """The spawned backend inherits the repo's fail-closed defaults: the
    supervised spawn passes AI2_ENABLED=0 and SCHEDULER_ENABLED=0 unless the
    operator explicitly overrode them in the environment."""
    assert "AI2_ENABLED: process.env.AI2_ENABLED || '0'" in BACKEND_SERVICE_JS
    assert "SCHEDULER_ENABLED: process.env.SCHEDULER_ENABLED || '0'" in BACKEND_SERVICE_JS


def test_supervised_backend_data_dir_outside_install_dir():
    """OA-1 data contract: the packaged shell relocates the backend's data
    directory OUTSIDE the install directory (%APPDATA%/radar-bourse) via
    RADAR_DATA_DIR, honored by backend/app/core/config.py — stores survive
    upgrade/uninstall instead of living in the (deletable) install dir."""
    assert "resolveDataDir" in BACKEND_SERVICE_JS
    assert "RADAR_DATA_DIR" in BACKEND_SERVICE_JS
    assert "radar-bourse" in BACKEND_SERVICE_JS
    assert "APPDATA" in BACKEND_SERVICE_JS
    config_text = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
    assert "RADAR_DATA_DIR" in config_text
    # the in-repo default stays ROOT/data (development/CI byte-compat)
    assert 'ROOT / "data"' in config_text


def test_supervised_backend_payload_is_unpacked_not_asar():
    """A Python child cannot execute from inside app.asar — the bundled
    payload must ship via extraResources (REAL filesystem path exposed by
    Electron's process.resourcesPath), and the resolver must use it."""
    pkg = (ROOT / "electron" / "package.json").read_text(encoding="utf-8")
    assert "extraResources" in pkg
    assert '"from": "resources/"' in pkg
    assert "process.resourcesPath" in BACKEND_SERVICE_JS
    # the payload must NOT ride inside app.asar
    assert "resources/**/*" not in pkg
