"""test_windows_packaging_readiness.py — MASTER-RADAR WAVE-G (2026-11-05)

Repository-side Windows packaging readiness pins:
- the deterministic validator passes (NSIS config, version consistency,
  Electron shell gates, runbook disclosures) — no Electron/npm/network;
- the runbook exists and carries the mandatory honest disclosures
  (NOT SIGNED, R-1/R-2 target-machine gating, checksum recording);
- the validator REFUSES to mint a signing claim (--claim-signed → exit 2);
- the Electron security-gate strings stay pinned at the byte level;
- the untracked-runtime surface stays honest: no installer artifact is
  claimed to exist.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "windows_package_readiness.py"
RUNBOOK = ROOT / "docs" / "active" / "WINDOWS_PACKAGING_RUNBOOK_2026-11-05.md"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
    )


def test_validator_reports_all_readiness_checks_green() -> None:
    res = _run()
    assert res.returncode == 0, res.stdout + res.stderr
    report = json.loads(res.stdout)
    assert report["all_ok"] is True
    checks = {r["check"] for r in report["results"]}
    for expected in (
        "ELECTRON_VERSION",
        "BACKEND_VERSION_LITERAL",
        "NSIS_APPID",
        "NSIS_TARGET",
        "NSIS_ICON",
        "NSIS_OUTPUT_DIR",
        "NSIS_FILES_INCLUDE_MAIN",
        "BUILD_SCRIPTS",
        "SHELL_GATE:nodeIntegration",
        "SHELL_GATE:contextIsolation",
        "RUNBOOK_NO_SIGNING_CLAIM",
        "RUNBOOK_TARGET_MACHINE_GATED",
    ):
        assert expected in checks
    # honesty: the tool itself lists what it does NOT claim
    assert "code signature present or verified" in " ".join(report["not_claimed"])


def test_validator_refuses_to_mint_a_signing_claim() -> None:
    res = _run("--claim-signed")
    assert res.returncode == 2
    payload = json.loads(res.stdout)
    assert payload["error"] == "SIGNING_CLAIM_REFUSED"


def test_runbook_carries_mandatory_honest_disclosures() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "NOT SIGNED" in text
    assert "sha256sum" in text  # checksum recording step
    assert "R-1" in text and "R-2" in text  # target-machine gates named
    assert "/api/health" in text  # startup health verification step
    assert "reproducibility" in text.lower()  # honest reproducibility disclosure
    assert "Rollback" in text or "بازگشت" in text


def test_no_installer_artifact_is_claimed_into_the_repo() -> None:
    dist = ROOT / "electron" / "dist"
    if dist.exists():
        # if an owner-side build ever drops artifacts, they must stay untracked;
        # the readiness validator still must not claim them
        report = json.loads(_run().stdout)
        assert "installer binary built (owner target machine R-1/R-2)" in report["not_claimed"]
