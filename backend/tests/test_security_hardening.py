from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import validate_security_configuration


def _client(monkeypatch, **env):
    keys = ["PRIVATE_MODE", "PRIVATE_PASSWORD", "API_KEY", "AUTH_REQUIRED", "ENV", "APP_ENV", "SHEKAR_ENV", "FERNET_KEY"]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    get_settings.cache_clear()
    from app.main import create_app

    get_settings.cache_clear()
    return TestClient(create_app())


def test_private_mode_without_key_blocks_sensitive_route(monkeypatch):
    client = _client(monkeypatch, PRIVATE_MODE="1")
    res = client.get("/api/config/thresholds")
    assert res.status_code in {401, 403}


def test_private_mode_wrong_api_key_blocks_sensitive_route(monkeypatch):
    client = _client(monkeypatch, PRIVATE_MODE="1", API_KEY="correct-key")
    res = client.get("/api/config/thresholds", headers={"X-API-Key": "wrong-key"})
    assert res.status_code in {401, 403}


def test_valid_api_key_allows_sensitive_route(monkeypatch):
    client = _client(monkeypatch, PRIVATE_MODE="1", API_KEY="correct-key")
    res = client.get("/api/config/thresholds", headers={"X-API-Key": "correct-key"})
    assert res.status_code == 200


def test_public_health_allowed_without_key_in_private_mode(monkeypatch):
    client = _client(monkeypatch, PRIVATE_MODE="1")
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_private_mode_requires_owner_secret_in_security_validation(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    settings = SimpleNamespace(private_mode=True, private_password="", api_key="", auth_required=True, fernet_key="")
    with pytest.raises(RuntimeError, match="PRIVATE_MODE requires"):
        validate_security_configuration(settings)


def test_production_requires_auth_and_stable_crypto(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    settings = SimpleNamespace(private_mode=False, private_password="", api_key="", auth_required=False, fernet_key="")
    with pytest.raises(RuntimeError, match="Production requires AUTH_REQUIRED"):
        validate_security_configuration(settings)

    settings = SimpleNamespace(private_mode=True, private_password="owner-secret", api_key="", auth_required=True, fernet_key="")
    with pytest.raises(RuntimeError, match="stable FERNET_KEY"):
        validate_security_configuration(settings)
