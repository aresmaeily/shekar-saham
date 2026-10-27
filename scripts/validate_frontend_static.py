#!/usr/bin/env python3
"""Static frontend contract validator for RADAR BOURSE Alpha.

This is not a browser E2E test. It checks offline-verifiable invariants:
- main/symbol HTML files exist
- main dashboard tabs have matching panels
- duplicate IDs are absent
- relative JS imports resolve
- critical assets/scripts exist
- version labels are single-sourced (no hardcoded legacy version literals) — WS-HARDEN-1/W4
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

# WS-HARDEN-1/W4: canonical app version is backend settings.version (served via /api/health);
# stale hardcoded frontend version literals (v0.6.x / v0.7.x era) must not return.
LEGACY_VERSION_RE = re.compile(r"\bv0\.[0-7](?:\.[0-9]+)?\b")
VERSION_SCAN_EXCLUDE = ("vendor",)
VERSION_SCAN_FILES_EXCLUDE = ("sw.js",)


def duplicate_ids(html: str) -> list[str]:
    ids = re.findall(r'id="([^"]+)"', html)
    return sorted({item for item in ids if ids.count(item) > 1})


def check_js_imports() -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for f in (FRONTEND / "js").rglob("*.js"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'import(?:[^\n]*?from\s*)?["\']([^"\']+)["\']', text):
            spec = m.group(1)
            if spec.startswith("."):
                target = (f.parent / spec).resolve()
                if target.suffix == "":
                    target = target.with_suffix(".js")
                if not target.exists():
                    missing.append({"file": str(f.relative_to(ROOT)), "import": spec, "target": str(target)})
    return missing


def check_version_labels() -> list[dict[str, str]]:
    """WS-HARDEN-1/W4: no hardcoded legacy version literals in HTML/JS (single source = settings.version)."""
    hits: list[dict[str, str]] = []
    scan_targets = [FRONTEND / "index.html", FRONTEND / "symbol.html"]
    scan_targets += [f for f in (FRONTEND / "js").rglob("*.js")]
    for f in scan_targets:
        if not f.exists() or f.name in VERSION_SCAN_FILES_EXCLUDE:
            continue
        if any(part in VERSION_SCAN_EXCLUDE for part in f.parts):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in LEGACY_VERSION_RE.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            hits.append({"file": str(f.relative_to(ROOT)), "line": str(line_no), "literal": m.group(0)})
    return hits


def main() -> int:
    index = FRONTEND / "index.html"
    symbol = FRONTEND / "symbol.html"
    result: dict = {
        "ok": True,
        "files": {
            "frontend/index.html": index.exists(),
            "frontend/symbol.html": symbol.exists(),
            "frontend/js/main.js": (FRONTEND / "js/main.js").exists(),
            "frontend/js/symbol.js": (FRONTEND / "js/symbol.js").exists(),
            "frontend/vendor/lightweight-charts.standalone.production.js": (FRONTEND / "vendor/lightweight-charts.standalone.production.js").exists(),
        },
        "tabs": {},
        "duplicate_ids": {},
        "missing_js_imports": [],
        "stale_version_literals": [],
    }
    if not all(result["files"].values()):
        result["ok"] = False
    if index.exists():
        idx = index.read_text(encoding="utf-8")
        tabs = re.findall(r'data-tab="([^"]+)"', idx)
        panels = re.findall(r'id="tab-([^"]+)"', idx)
        result["tabs"] = {
            "tabs_count": len(tabs),
            "panels_count": len(panels),
            "missing_panels": sorted(set(tabs) - set(panels)),
            "orphan_panels": sorted(set(panels) - set(tabs)),
        }
        result["duplicate_ids"]["index"] = duplicate_ids(idx)
        if result["tabs"]["missing_panels"] or result["tabs"]["orphan_panels"] or result["duplicate_ids"]["index"]:
            result["ok"] = False
    if symbol.exists():
        result["duplicate_ids"]["symbol"] = duplicate_ids(symbol.read_text(encoding="utf-8"))
        if result["duplicate_ids"]["symbol"]:
            result["ok"] = False
    result["missing_js_imports"] = check_js_imports()
    if result["missing_js_imports"]:
        result["ok"] = False
    result["stale_version_literals"] = check_version_labels()
    if result["stale_version_literals"]:
        result["ok"] = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
