import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_script(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True, timeout=120)


def test_alpha_environment_script_json_contract():
    result = run_script("scripts/validate_alpha_environment.py", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["files"]["backend/app/main.py"] is True
    assert "PRIVATE_MODE" in data["environment"]
    assert "Secret values are intentionally not printed." in data["notes"]


def test_provider_validation_mock_contract_no_false_live():
    result = run_script("scripts/validate_providers.py", "--source", "mock")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["requested_source"] == "mock"
    assert data["row_count"] > 0
    assert data["data_trust"]["state"] == "mock"
    assert data["data_trust"]["trust_level"] == "synthetic"
    assert data["data_trust"]["is_live"] is False
    assert data["live_verified"] is False


def test_provider_validation_brsapi_missing_key_is_safe(monkeypatch):
    monkeypatch.delenv("BRSAPI_KEY", raising=False)
    result = run_script("scripts/validate_providers.py", "--source", "brsapi")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["brsapi_key_status"] == "missing"
    assert data["data_trust"]["is_live"] is False
    assert "BRSAPI_KEY" not in json.dumps(data, ensure_ascii=False)


def _param_block(text: str) -> str:
    start = text.find("param(")
    assert start != -1
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError("unclosed param() block")


def test_windows_scripts_do_not_use_psscriptroot_in_param_defaults():
    windows = ROOT / "scripts" / "windows"
    for name in ("validate_install.ps1", "install.ps1", "start.ps1"):
        text = (windows / name).read_text(encoding="utf-8")
        block = _param_block(text)
        assert "$PSScriptRoot" not in block, name
        assert "Resolve-RadarBourseProjectRoot" in text
        assert "$PSCommandPath" in text
        assert "Pass -ProjectRoot explicitly" in text


def test_windows_script_relative_root_is_repository_root():
    script_dir = ROOT / "scripts" / "windows"
    resolved = (script_dir / ".." / "..").resolve()
    assert resolved == ROOT
    assert (resolved / "backend" / "app" / "main.py").is_file()
    assert (resolved / ".env.example").is_file()


def test_alpha_runtime_script_smoke_contract():
    result = run_script("scripts/validate_alpha_runtime.py")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    paths = {item["path"] for item in data["checks"]}
    assert "/api/ai/assistant" in paths
    assert "/api/backtest/run" in paths
    assert "/api/analyze" in paths
