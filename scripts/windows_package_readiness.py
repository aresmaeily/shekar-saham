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
- WAVE-T3 (MR-I-02, 2026-11-07): EMBEDDED-RUNTIME bundling contract — the
  installer workflow must pin the embedded CPython runtime (URL + published
  MD5 + fail-closed verification), wire the local dependency bundle through
  the runtime's own ._pth, prove the wiring with a real import smoke, and
  record runtime provenance; the shell must prefer the bundled python.exe
  with the system launcher only as fallback; the PSF license notice must be
  present in-repo;
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
ELECTRON_BACKEND_SERVICE_PATH = ELECTRON_DIR / "backend_service.js"
ICON_PATH = ELECTRON_DIR / "icon.ico"
RUNBOOK_PATH = ROOT / "docs" / "active" / "WINDOWS_PACKAGING_RUNBOOK_2026-11-05.md"
BACKEND_CONFIG = ROOT / "backend" / "app" / "core" / "config.py"
WORKFLOW_INSTALLER_PATH = ROOT / ".github" / "workflows" / "windows-installer.yml"
LICENSE_PYTHON_PATH = ELECTRON_DIR / "resources" / "python-runtime" / "LICENSE_PYTHON.txt"

EXPECTED_VERSION = "3.0.0"
_SECURITY_GATES = (
    "nodeIntegration: false",
    "contextIsolation: true",
    "enableRemoteModule: false",
)

# WAVE-N remainder (OA-1, 2026-11-06): the supervised-backend contract the
# shell must carry (resolves the recorded "shell-does-not-spawn-backend"
# residual). Byte-present strings in electron/backend_service.js + main.js.
_SUPERVISED_BACKEND_GATES = (
    # loopback-only binding (structural, not advisory)
    ("backend_service.js", "LOCAL_HOST = '127.0.0.1'"),
    ("backend_service.js", "'--host', LOCAL_HOST"),
    # bounded startup + health poll on /api/health (loopback only)
    ("backend_service.js", "BACKEND_STARTUP_TIMEOUT_MS"),
    ("backend_service.js", "'/api/health'"),
    # graceful shutdown with bounded grace window
    ("backend_service.js", "GRACEFUL_SHUTDOWN_MS"),
    # bounded crash recovery (restart budget, never infinite)
    ("backend_service.js", "MAX_RESTARTS"),
    # honest degraded state surfaced (never silent)
    ("backend_service.js", "'degraded'"),
)

# Tokens that must NEVER appear in the supervised-backend service or the
# shell wiring: no download path, no auto-updater, no remote URL literals
# (the only egress the service performs is loopback health probes).
_SUPERVISED_BACKEND_ABSENT = ("https://", "http://", "autoUpdate", "update-electron-app", "download")  # in backend_service.js


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
        "NSIS_FILES_INCLUDE_BACKEND_SERVICE": "backend_service.js" in (build.get("files") or []),
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

    # 3b) WAVE-N remainder: supervised local backend contract (resolves the
    # recorded "shell-does-not-spawn-backend" residual — the shell now
    # STARTS and SUPERVISES the bundled backend: bounded startup, loopback
    # health check, graceful shutdown, bounded restart, honest degraded).
    if ELECTRON_BACKEND_SERVICE_PATH.is_file():
        svc_text = ELECTRON_BACKEND_SERVICE_PATH.read_text(encoding="utf-8")
        for target, gate in _SUPERVISED_BACKEND_GATES:
            text = svc_text if target == "backend_service.js" else main_text
            results.append(
                _pass(f"SUPERVISED_BACKEND:{gate[:24]}", "byte-present")
                if gate in text
                else _fail(f"SUPERVISED_BACKEND:{gate[:24]}", f"gate string absent from electron/{target}")
            )
        for banned in _SUPERVISED_BACKEND_ABSENT:
            results.append(
                _pass(f"SUPERVISED_BACKEND_ABSENT:{banned}", "absent (no remote path)")
                if banned not in svc_text
                else _fail(f"SUPERVISED_BACKEND_ABSENT:{banned}", "remote/download token present in backend_service.js")
            )
        results.append(
            _pass("SUPERVISED_BACKEND_WIRING", "main.js requires ./backend_service")
            if "require('./backend_service')" in main_text
            else _fail("SUPERVISED_BACKEND_WIRING", "main.js does not wire the supervised backend")
        )
        results.append(
            _pass("SUPERVISED_BACKEND_HONEST_DEGRADED", "degraded status page wired")
            if "loadDegradedStatusPage" in main_text
            else _fail("SUPERVISED_BACKEND_HONEST_DEGRADED", "no honest degraded-state surface in main.js")
        )
    else:
        results.append(_fail("SUPERVISED_BACKEND_PRESENT", "electron/backend_service.js missing"))

    # 3c) WAVE-T3 (MR-I-02, 2026-11-07): embedded-runtime bundling contract.
    # The installer ships a PINNED embedded CPython (3.12.10 embeddable amd64)
    # MD5-verified against python.org's published value, plus a LOCAL
    # dependency bundle — first launch needs NO system Python, NO pip, NO
    # venv, NO network. The wiring must be proven by a real import smoke in
    # CI. Honest scope: still NOT claimed here — execution on a target
    # machine (owner R-1/R-2).
    if WORKFLOW_INSTALLER_PATH.is_file():
        wf = WORKFLOW_INSTALLER_PATH.read_text(encoding="utf-8")
        runtime_gates = {
            "EMBEDDED_RUNTIME_PINNED_URL": "python-3.12.10-embed-amd64.zip" in wf,
            "EMBEDDED_RUNTIME_PINNED_MD5": "fe8ef205f2e9c3ba44d0cf9954e1abd3" in wf,
            "EMBEDDED_RUNTIME_FAIL_CLOSED": "MD5 mismatch" in wf and "refusing to bundle an unverified runtime" in wf,
            "EMBEDDED_RUNTIME_PTH_WIRING": "Add-Content -Path $pth" in wf and "'../site-packages'" in wf,
            "EMBEDDED_RUNTIME_LOCAL_DEPS": "--only-binary=:all:" in wf and "--target electron/resources/site-packages" in wf,
            "EMBEDDED_RUNTIME_IMPORT_SMOKE": "IMPORT-SMOKE-OK" in wf and "import smoke FAILED" in wf,
            "EMBEDDED_RUNTIME_PAYLOAD_VERIFY": "python-runtime/python.exe" in wf and "python-runtime/LICENSE_PYTHON.txt" in wf and "site-packages/numpy" in wf,
            "EMBEDDED_RUNTIME_PROVENANCE": "python_runtime_version=3.12.10" in wf and "python_runtime_sha256_recorded" in wf and "python_runtime_import_smoke" in wf,
            "EMBEDDED_RUNTIME_LICENSE_META": "PSF LICENSE VERSION 2" in wf and "python_runtime = [ordered]@{" in wf,
        }
        for code, ok in runtime_gates.items():
            results.append(_pass(code, "pinned") if ok else _fail(code, "installer workflow gate missing"))
    else:
        results.append(_fail("EMBEDDED_RUNTIME_WORKFLOW", f"{WORKFLOW_INSTALLER_PATH.name} missing"))

    if ELECTRON_BACKEND_SERVICE_PATH.is_file():
        svc_text = ELECTRON_BACKEND_SERVICE_PATH.read_text(encoding="utf-8")
        shell_gates = {
            "EMBEDDED_RUNTIME_SHELL_PREFER": "'python-runtime', 'python.exe'" in svc_text,
            "EMBEDDED_RUNTIME_SHELL_HONEST_FALLBACK": "FALLBACK (development only)" in svc_text,
            "EMBEDDED_RUNTIME_NO_RUNTIME_FETCH": "bundled: true" in svc_text and "an unverified runtime is never fetched" in svc_text,
        }
        for code, ok in shell_gates.items():
            results.append(_pass(code, "present") if ok else _fail(code, "shell runtime-resolution gate missing"))
    else:
        results.append(_fail("EMBEDDED_RUNTIME_SHELL", "electron/backend_service.js missing"))

    if LICENSE_PYTHON_PATH.is_file():
        lic = LICENSE_PYTHON_PATH.read_text(encoding="utf-8")
        results.append(
            _pass("EMBEDDED_RUNTIME_LICENSE_FILE", "PSF v2 text present")
            if "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2" in lic and "docs.python.org/3/license.html" in lic
            else _fail("EMBEDDED_RUNTIME_LICENSE_FILE", "PSF license text incomplete")
        )
    else:
        results.append(_fail("EMBEDDED_RUNTIME_LICENSE_FILE", f"{LICENSE_PYTHON_PATH.name} missing"))

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
            "RUNBOOK_EMBEDDED_RUNTIME": "3.12.10" in rb and "EMBEDDED_RUNTIME" in rb and "._pth" in rb,
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
