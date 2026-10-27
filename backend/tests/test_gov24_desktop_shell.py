"""GOV-24/WP-2 — desktop-shell (Electron) contract tests (D-24-2).

The Electron shell is the Windows desktop entry (P3.43-3 repo side). Before
this work package it drifted out of the version single-source established by
WS-HARDEN-1/W4 (``electron/package.json`` pinned 0.9.0, the window title
carried the stale literal "v0.9 Ultimate") and its electron-builder Windows
icon pointed at an SVG, which is not a valid Windows icon format.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ELECTRON = ROOT / "electron"
PKG = json.loads((ELECTRON / "package.json").read_text(encoding="utf-8"))
MAIN_JS = (ELECTRON / "main.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

from app.core.config import get_settings


def test_package_json_version_is_settings_version():
    """Single source of truth: backend settings.version (W4 contract extended to the shell)."""
    assert PKG["version"] == get_settings().version


def test_main_js_title_has_no_stale_version_literal():
    """The window title must not carry a hardcoded version that can drift; the
    loaded page displays the API-synced authoritative version (W4)."""
    assert "v0.9" not in MAIN_JS
    assert not re.search(r"\bv0\.[0-7]\b", MAIN_JS)
    assert re.search(r"\bv\d", MAIN_JS) is None or "loadURL" in MAIN_JS  # title itself version-free
    title = re.search(r'title:\s*"([^"]+)"', MAIN_JS).group(1)
    assert not re.search(r"\bv\d+(\.\d+)*\b", title)


def test_windows_icon_is_a_valid_ico_and_referenced():
    """electron-builder win target needs a real .ico (SVG was invalid)."""
    icon_path = ELECTRON / PKG["build"]["win"]["icon"]
    assert icon_path.is_file(), f"missing icon file: {icon_path}"
    data = icon_path.read_bytes()
    assert data[:4] == b"\x00\x00\x01\x00", "not a valid ICO header"
    count = int.from_bytes(data[4:6], "little")
    assert count >= 1
    widths = set()
    for i in range(count):
        off = 6 + i * 16
        widths.add(data[off] or 256)
    assert 256 in widths, "a 256px layer is required for modern Windows"


def test_menu_hash_targets_exist_as_tabs():
    """Menu items load '#/<id>' routes; every referenced id must be a real tab."""
    targets = set(re.findall(r"loadURL\(startUrl \+ '/#/([a-z]+)'\)", MAIN_JS))
    tabs = set(re.findall(r'data-tab="([^"]+)"', INDEX_HTML))
    assert targets, "expected at least one menu hash target"
    assert targets <= tabs, f"menu targets unknown tabs: {sorted(targets - tabs)}"


def test_shell_security_preferences_unchanged():
    """Guard the existing isolation posture (no regression allowed here)."""
    assert "contextIsolation: true" in MAIN_JS
    assert "nodeIntegration: false" in MAIN_JS


def test_no_stale_version_literals_in_package_json_strings():
    """No v0.[0-7]-style literals anywhere in the shell manifest strings."""
    raw = (ELECTRON / "package.json").read_text(encoding="utf-8")
    assert not re.search(r"\bv0\.[0-7]\b", raw)
