"""GOV-24/WP-1 — retired legacy-link scheme regression tests (D-24-1).

WS-HARDEN-1/W3 retired the ``?legacy=1`` loader, but ``frontend/js/symbol.js``
kept seven links pointing at ``/?legacy=1#tab-*``. The modern hash router
(``frontend/js/core/router.js``) expects ``#/<tab-id>`` anchors and silently
falls back to the first tab for unknown ids, so users following those links
landed on the wrong tab. These tests pin the corrected state and the
validator's additive ``stale_legacy_links`` check.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
SYMBOL_JS = FRONTEND / "js" / "symbol.js"
INDEX_HTML = FRONTEND / "index.html"

import sys

sys.path.insert(0, str(ROOT / "scripts"))
import validate_frontend_static as vfs  # noqa: E402


def test_frontend_has_no_retired_legacy_links():
    """No frontend file (vendor/sw.js excluded, same set as the validator) may
    reference the retired ?legacy=1 scheme or #tab-* href anchors."""
    assert vfs.check_stale_legacy_links() == []


def test_symbol_js_uses_modern_router_hashes():
    """The corrected symbol-page links must target existing router tabs."""
    text = SYMBOL_JS.read_text(encoding="utf-8")
    targets = set(re.findall(r'href="/#/\#?([a-z]+)"', text)) or set(
        re.findall(r'href="/#/([a-z]+)"', text)
    )
    assert targets, "expected at least one modern #/<tab> link in symbol.js"
    tabs = set(re.findall(r'data-tab="([^"]+)"', INDEX_HTML.read_text(encoding="utf-8")))
    missing = targets - tabs
    assert not missing, f"symbol.js links target unknown tabs: {sorted(missing)}"


def test_main_js_hash_bridge_contract():
    """The live hash contract the links rely on (GOV-24/WP-3): the click path
    writes '#/<id>' via replaceState, and bindNav installs the reverse bridge —
    a hashchange listener plus an initial deep-link activation. (The former
    dead module frontend/js/core/router.js was retired in WP-3; hash 7e6cc6ce….)"""
    text = (ROOT / "frontend" / "js" / "main.js").read_text(encoding="utf-8")
    assert 'history.replaceState(null, "", "#/" + btn.dataset.tab)' in text
    assert 'window.addEventListener("hashchange", activateFromHash)' in text
    assert "activateFromHash();" in text
    assert 'replace(/^#\\/?/, "")' in text


def test_validator_legacy_link_regex_detects_retired_scheme():
    """Negative-control: the validator regex must flag the retired forms."""
    assert vfs.LEGACY_LINK_RE.search('href="/?legacy=1#tab-hot"')
    assert vfs.LEGACY_LINK_RE.search('href="/?legacy=1"')
    assert not vfs.LEGACY_LINK_RE.search('href="/#/hot"')


def test_validator_main_report_includes_stale_legacy_links_key():
    """The additive check is wired into the main report structure."""
    import inspect

    src = inspect.getsource(vfs.main)
    assert "stale_legacy_links" in src
    assert "check_stale_legacy_links" in src
