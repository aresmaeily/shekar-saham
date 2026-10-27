"""WS-HARDEN-1/W1 — compose/Dockerfile hardening regression tests.

Owner-ordered workstream (charter: docs/active/WS_HARDEN_1_CHARTER_2026-10-27.md).
Fail-closed rule: PRIVATE_MODE owner secrets must never be insecure compose-style
placeholders ("change-me*"); container port must come from env, not a hardcoded CMD.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.security import validate_security_configuration

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
DOCKERFILE = ROOT / "Dockerfile"
ENTRYPOINT = ROOT / "entrypoint.sh"


def _settings(**kwargs) -> SimpleNamespace:
    base = dict(
        private_mode=True,
        private_password="",
        api_key="",
        auth_required=True,
        fernet_key="",
        cookie_secure=False,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_placeholder_private_password_rejected():
    with pytest.raises(RuntimeError, match="insecure placeholder"):
        validate_security_configuration(_settings(private_password="change-me-strong-password"))


def test_placeholder_api_key_rejected():
    with pytest.raises(RuntimeError, match="insecure placeholder"):
        validate_security_configuration(_settings(api_key="change-me-api-key"))


def test_strong_owner_secret_passes_validation():
    validate_security_configuration(_settings(private_password="s3cure-owner-passphrase"))


def test_compose_has_no_insecure_placeholder_defaults():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "change-me" not in text, "compose must not carry insecure literal credentials"
    assert "PRIVATE_PASSWORD: ${PRIVATE_PASSWORD:-}" in text
    assert "API_KEY: ${API_KEY:-}" in text


def test_compose_port_is_env_interpolated():
    text = COMPOSE.read_text(encoding="utf-8")
    assert '"${PORT:-8000}:${PORT:-8000}"' in text
    assert '"8000:8000"' not in text


def test_dockerfile_uses_entrypoint_and_env_port():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert 'CMD ["/app/entrypoint.sh"]' in dockerfile
    assert "COPY entrypoint.sh /app/entrypoint.sh" in dockerfile
    # no hardcoded uvicorn --port in CMD anymore
    assert '"--port", "8000"' not in dockerfile
    # healthcheck reads PORT from env
    assert "os.environ.get('PORT', '8000')" in dockerfile
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    assert '--port "$PORT_VALUE"' in entrypoint
    assert '--host "$HOST_VALUE"' in entrypoint


def test_entrypoint_shell_syntax_valid():
    import subprocess

    proc = subprocess.run(["sh", "-n", str(ENTRYPOINT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
