#!/usr/bin/env python3
"""windows_package_readiness.py — MASTER-RADAR WAVE-G (2026-11-05)

Repository-side Windows packaging READINESS validator (deterministic,
cross-platform, no Electron/npm/network needed).

What this validator asserts (and what it deliberately does NOT):
- version consistency: electron/package.json version == backend version
  literal (the same single-source-of-truth rule pinned in
  test_wda_version_consistency.py);
- NSIS target configuration present and complete (appId, productName,
  win.target=nsis, win.icon, output dir, files list includes main.js);
- Electron shell security gates byte-present in electron/main.js
  (contextIsolation true / nodeIntegration false / enableRemoteModule false
  — the same strings pinned by test_wda_electron_shell_gates.py);
- build scripts + icon asset present;
- startup-health contract documented: the shell loads the backend origin and
  the backend exposes /api/health (documented in the runbook);
- SIGNING: the runbook must DISCLOSE that no signing certificate exists and
  that no signed-artifact claim is made anywhere (signing-readiness only).

NOT asserted here (owner-gated, R-1/R-2): an actual installer build, an
install on a Windows target machine, upgrade/rollback execution, signature
verification — none of these can be honestly claimed from this repository
state, and this validator refuses to pretend otherwise.

Exit code 0 = readiness checks pass; 1 = readiness failure; 2 = hostile
usage (e.g. --claim-signed which is always refused).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELECTRON_DIR = ROOT / "electron"
ELECTRON_PKG_PATH = ELECTRON_DIR / "package.json"
ELECTRON_MAIN_PATH = ELECTRON_DIR / "main.js"
ICON_PATH = ELECTRON_DIR / "icon.ico"
RUNBOOK_PATH = ROOT / "docs" / "active" / "WINDOWS_PACKAGING_RUNBOOK_2026-11-05.md"
BACKEND_CONFIG = ROOT / "backend" / "app" / "core" / "config.py"

EXPECTED_VERSION = "3.0.0"
_SECURITY_GATES = (
    "nodeIntegration: false",
    "contextIsolation: true",
    "enableRemoteModule: false",
)


def _fail(code: str, message: str) -> dict:
    return {"check": code, "ok": False, "detail": message}


def _pass(code: str, detail: str) -> dict:
    return {"check": code, "ok": True, "detail": detail}


def validate() -> dict:
    results: list[dict] = []

    # 1) version consistency (electron == backend literal)
    try:
        pkg = json.loads(ELECTRON_PKG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        results.append(_fail("ELECTRON_PKG_PARSE", f"unreadable: {exc}"))
        pkg = {}
    results.append(
        _pass("ELECTRON_VERSION", pkg["version"])
        if pkg.get("version") == EXPECTED_VERSION
        else _fail("ELECTRON_VERSION", f"{pkg.get('version')!r} != {EXPECTED_VERSION!r}")
    )
    config_text = BACKEND_CONFIG.read_text(encoding="utf-8")
    results.append(
        _pass("BACKEND_VERSION_LITERAL", EXPECTED_VERSION)
        if f'version: str = "{EXPECTED_VERSION}"' in config_text
        else _fail("BACKEND_VERSION_LITERAL", "backend version literal drifted")
    )

    # 2) NSIS build configuration completeness
    build = pkg.get("build", {}) or {}
    win = build.get("win", {}) or {}
    nsis_checks = {
        "NSIS_APPID": build.get("appId") == "com.radarbourse.desktop",
        "NSIS_TARGET": win.get("target") == "nsis",
        "NSIS_ICON": bool(win.get("icon")) and ICON_PATH.is_file(),
        "NSIS_OUTPUT_DIR": build.get("directories", {}).get("output") == "dist",
        "NSIS_FILES_INCLUDE_MAIN": "main.js" in (build.get("files") or []),
        "BUILD_SCRIPTS": pkg.get("scripts", {}).get("build") == "electron-builder --win --x64",
    }
    for code, ok in nsis_checks.items():
        results.append(_pass(code, "present") if ok else _fail(code, "missing/incorrect"))

    # 3) Electron security gates byte-present (pinned strings)
    main_text = ELECTRON_MAIN_PATH.read_text(encoding="utf-8")
    for gate in _SECURITY_GATES:
        results.append(
            _pass(f"SHELL_GATE:{gate.split(':')[0]}", "byte-present")
            if gate in main_text
            else _fail(f"SHELL_GATE:{gate.split(':')[0]}", "gate string absent from electron/main.js")
        )

    # 4) runbook present with the mandatory honest disclosures
    if RUNBOOK_PATH.is_file():
        rb = RUNBOOK_PATH.read_text(encoding="utf-8")
        disclosures = {
            "RUNBOOK_BUILD_STEPS": "npm ci" in rb and "electron-builder" in rb,
            "RUNBOOK_CHECKSUM_STEP": "SHA-256" in rb or "sha256sum" in rb,
            "RUNBOOK_UPGRADE_STEP": "ارتقا" in rb or "Upgrade" in rb or "upgrade" in rb,
            "RUNBOOK_ROLLBACK_STEP": "بازگشت" in rb or "rollback" in rb or "Rollback" in rb,
            "RUNBOOK_HEALTH_STEP": "/api/health" in rb,
            "RUNBOOK_NO_SIGNING_CLAIM": "امضا نشده" in rb or "NOT SIGNED" in rb or "NOT-SIGNED" in rb,
            "RUNBOOK_TARGET_MACHINE_GATED": "R-1" in rb and "R-2" in rb,
        }
        for code, ok in disclosures.items():
            results.append(_pass(code, "disclosed") if ok else _fail(code, "runbook disclosure missing"))
    else:
        results.append(_fail("RUNBOOK_PRESENT", f"{RUNBOOK_PATH.name} missing"))

    return {
        "tool": "windows_package_readiness",
        "declared_version": "WINDOWS-PACKAGING-READINESS-V1",
        "all_ok": all(r["ok"] for r in results),
        "results": results,
        "not_claimed": [
            "installer binary built (owner target machine R-1/R-2)",
            "install/upgrade/rollback executed on Windows",
            "code signature present or verified",
        ],
    }


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--claim-signed":
        # hostile usage: this tool can never mint a signing claim
        print('{"error": "SIGNING_CLAIM_REFUSED", "message_en": "no signing certificate exists; claims are never minted", "message_fa": "گواهی امضا وجود ندارد؛ هیچ ادعای امضایی تولید نمی‌شود"}')
        return 2
    report = validate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
