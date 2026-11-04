"""WDA/roadmap cycle 2026-11-03 — AI-3 D5/R-6 reconciliation: the
owner-activated backup trigger CLI.

Directive resolution: D5 records a daily backup cadence while R-6 keeps every
in-app scheduler dormant and manual-trigger-only. Honest resolution recorded
in AI3_OPERATIONAL_STATUS_2026-11-03.md: daily AUTOMATED backup is NOT
OPERATIONAL in this release; the activation path is the owner running the
trigger below (manually or via an owner-issued OS-level scheduled task on the
OWNER machine — the exact "separate dated owner act on the owner machine"
R-6 names).

Pinned here:
1. `python -m app.data.research_memory_sqlite backup` end-to-end: WAL snapshot
   + sha256 sidecar produced under the given destination; exit 0.
2. `verify-backup` on the produced snapshot: exit 0 (fail-closed verification
   path reachable from the CLI).
3. Invalid key material → exit 2 with FAILED on stderr; no plaintext fallback.
4. verify-backup on a nonexistent snapshot → exit 2 (fail-closed).
5. DORMANCY source guard: the CLI is referenced only by its defining module
   and its tests — no application-runtime caller exists.
"""
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODULE = "app.data.research_memory_sqlite"
_KEY = "ab" * 32  # valid 32-byte hex key material (D4 env override)


def _run(*argv: str, key: str | None = _KEY) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("RADAR_RESEARCH_MEMORY_KEY", None)
    if key is not None:
        env["RADAR_RESEARCH_MEMORY_KEY"] = key
    return subprocess.run(
        [sys.executable, "-m", MODULE, *argv],
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_backup_trigger_end_to_end(tmp_path):
    dest = tmp_path / "backups"
    proc = _run(
        "backup",
        "--directory", str(tmp_path / "store"),
        "--dest", str(dest),
        "--keep", "14",
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "backup OK" in proc.stdout
    snapshots = list(dest.glob("research-memory-*.sqlite"))
    assert len(snapshots) == 1, list(dest.iterdir())
    sidecars = list(dest.glob("research-memory-*.sqlite.sha256"))
    assert len(sidecars) == 1
    assert snapshots[0].stat().st_size > 0


def test_verify_backup_trigger_on_produced_snapshot(tmp_path):
    dest = tmp_path / "backups"
    bak = _run(
        "backup",
        "--directory", str(tmp_path / "store"),
        "--dest", str(dest),
    )
    assert bak.returncode == 0, (bak.stdout, bak.stderr)
    snapshot = next(dest.glob("research-memory-*.sqlite"))
    proc = _run("verify-backup", "--path", str(snapshot))
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "verify-backup OK" in proc.stdout


def test_invalid_key_refused_fail_closed_no_plaintext_fallback(tmp_path):
    proc = _run(
        "backup",
        "--directory", str(tmp_path / "store"),
        "--dest", str(tmp_path / "backups"),
        key="this-is-not-valid-hex-or-base64-key-material!!",
    )
    assert proc.returncode == 2
    assert "FAILED" in proc.stderr
    assert not (tmp_path / "backups").exists() or not any(
        (tmp_path / "backups").iterdir()
    )


def test_verify_backup_missing_snapshot_fail_closed(tmp_path):
    proc = _run("verify-backup", "--path", str(tmp_path / "nope.sqlite"))
    assert proc.returncode == 2
    assert "FAILED" in proc.stderr


def test_cli_is_dormant_no_runtime_caller():
    """The trigger is reachable ONLY from the command line: no module in the
    application runtime imports the CLI or invokes it — it cannot activate
    itself (R-6 dormancy contract)."""
    offenders: list[str] = []
    for py in (BACKEND_ROOT / "app").rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        rel = py.relative_to(BACKEND_ROOT).as_posix()
        if rel == "app/data/research_memory_sqlite.py":
            continue
        if "_cli" in src and "research_memory" in src:
            offenders.append(rel)
    assert offenders == [], offenders
