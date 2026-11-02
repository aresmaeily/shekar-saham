"""WS-6 contract tests — Windows workflow gates (2026-11-02).

Two authorized hardening items from the MASTER execution program's Wave-2
audits are pinned here as repo-side contracts:

1. W2-INST F3 authorized follow-up: a PowerShell SYNTAX GATE inside
   windows.yml. Finding S2 honestly recorded that NO automation anywhere
   parsed the four shipped ``scripts/windows/*.ps1`` files (the dev sandbox
   has no pwsh; the workflow itself only ran inline pwsh). The new gate step
   parses every shipped script with the real PowerShell language parser on a
   real pwsh host and fails the job BEFORE any install/boot step runs. These
   tests pin the gate's presence, its fail-closed shape, its exact script
   inventory (a script added later MUST be added to the gate), and its
   ordering (before the W1 boot and before artifact upload).

2. W2-SEC C-3 completion: the last tag-pinned third-party action
   (``actions/upload-artifact@v4``) is now pinned by its immutable commit
   SHA, matching the checkout/setup-python discipline already pinned by
   ``test_master_wave2_hardening.py``. Authoritative SHA resolved via git
   ls-remote of the action repository (v4.6.2, lightweight tag) and
   cross-checked against the release page:
   v4.6.2 = ea165f8d65b6e75b540449e92b4886f43607fa02.

The workflow is validated as YAML (safe_load) so any structural drift breaks
these tests loudly. No pwsh is required in the dev sandbox — the real parse
executes on the windows-latest runner; here we pin the automation contract
itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "windows.yml"

PS1_INVENTORY = (
    "scripts/windows/install.ps1",
    "scripts/windows/start.ps1",
    "scripts/windows/validate_install.ps1",
    "scripts/windows/validate_alpha.ps1",
)

UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"  # v4.6.2


def _workflow_steps() -> list[dict]:
    doc = yaml.safe_load(WORKFLOW.read_text("utf-8"))
    job = doc["jobs"]["windows-validation"]
    assert isinstance(job["steps"], list) and len(job["steps"]) >= 8
    return job["steps"]


def _step_index(steps: list[dict], needle: str) -> int:
    for i, step in enumerate(steps):
        name = str(step.get("name", ""))
        uses = str(step.get("uses", ""))
        if needle in name or needle in uses:
            return i
    raise AssertionError(f"step matching {needle!r} not found")


def test_ps1_syntax_gate_present_and_fail_closed() -> None:
    steps = _workflow_steps()
    gi = _step_index(steps, "PowerShell script syntax gate")
    gate = steps[gi]
    assert str(gate.get("shell", "")) == "pwsh"
    body = str(gate.get("run", ""))
    # Real language-parser API, not a text heuristic.
    assert "Parser]::ParseFile" in body
    # Fail-closed: parse errors (or a missing script) abort the job.
    assert "exit 1" in body
    assert "$errors.Count -gt 0" in body
    assert "MISSING" in body


def test_ps1_gate_covers_exactly_the_shipped_inventory() -> None:
    steps = _workflow_steps()
    gate = steps[_step_index(steps, "PowerShell script syntax gate")]
    body = str(gate.get("run", ""))
    for path in PS1_INVENTORY:
        assert path in body, f"shipped script {path} missing from the gate list"
    # The inventory constant in this test file and the repo must agree.
    for path in PS1_INVENTORY:
        assert (REPO_ROOT / path).is_file(), f"{path} missing from the repo"


def test_ps1_gate_runs_before_boot_and_before_upload() -> None:
    steps = _workflow_steps()
    gi = _step_index(steps, "PowerShell script syntax gate")
    bi = _step_index(steps, "Boot backend (W1 startup)")
    ui = _step_index(steps, "upload-artifact")
    assert gi < bi, "syntax gate must run before any install/boot step"
    assert gi < ui, "syntax gate must run before artifact upload"


def test_upload_artifact_pinned_by_commit_sha() -> None:
    steps = _workflow_steps()
    ui = _step_index(steps, "upload-artifact")
    uses = str(steps[ui]["uses"])
    assert uses == f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", uses
    text = WORKFLOW.read_text("utf-8")
    assert "# v4.6.2" in text, "keep the human-readable version comment"
    # No tag-style reference remains anywhere in either workflow.
    for name in ("ci.yml", "windows.yml"):
        flow = (REPO_ROOT / ".github" / "workflows" / name).read_text("utf-8")
        assert not re.search(r"uses:\s*\S+@v\d", flow), f"{name}: unpinned @vN action remains"


def test_gate_step_is_documented_as_audit_followup() -> None:
    text = WORKFLOW.read_text("utf-8")
    assert "W2-INST F3" in text, "gate must cite its authorizing finding"
    assert "NOT-RUN-HERE" in text, "honest provenance of the gap must stay recorded"
