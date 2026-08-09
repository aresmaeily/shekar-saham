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


def test_alpha_runtime_script_smoke_contract():
    result = run_script("scripts/validate_alpha_runtime.py")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    paths = {item["path"] for item in data["checks"]}
    assert "/api/ai/assistant" in paths
    assert "/api/backtest/run" in paths
    assert "/api/analyze" in paths
