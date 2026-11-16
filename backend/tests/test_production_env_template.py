"""RC1 audit remediation (2026-11-16): production env template contract.

Pins the audit fix: the RC1 release-engineering docs referenced
``.env.production.example`` while the file was missing from the committed
tree. The template now exists at the exact documented path (repo root) and
these tests keep the docs claim and the tree in lock-step:

* the template is placeholder-only — no real credential anywhere;
* the governance gates stay pinned (AI2_ENABLED=0, SCHEDULER_ENABLED=0);
* the production posture flags are present (ENV=production, PRIVATE_MODE=1,
  COOKIE_SECURE=1);
* using the template VERBATIM in production FAILS CLOSED at startup
  (validate_security_configuration refuses change-me* owner secrets);
* a correctly FILLED template passes production validation — the documented
  install path is achievable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.core.security import validate_security_configuration

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".env.production.example"

_SECRET_LIKE_KEYS = (
    "PRIVATE_PASSWORD",
    "API_KEY",
    "FERNET_KEY",
    "BRSAPI_KEY",
    "TELEGRAM_BOT_TOKEN",
    "BALE_BOT_TOKEN",
    "AI_API_KEY",
)


def _parse_env_template() -> dict[str, str]:
    """Parse KEY=VALUE lines; comments/blank lines ignored, inline comments stripped."""
    pairs: dict[str, str] = {}
    for raw in TEMPLATE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        pairs[key.strip()] = value
    return pairs


def test_template_exists_at_documented_path():
    assert TEMPLATE.is_file(), (
        "docs reference .env.production.example at the repo root; the file must be committed"
    )


def test_template_is_placeholder_only_no_real_secrets():
    pairs = _parse_env_template()
    for key in _SECRET_LIKE_KEYS:
        if key in pairs and pairs[key]:
            assert pairs[key].lower().startswith("change-me"), (
                f"{key} must be an obvious change-me placeholder, never a real value"
            )
    text = TEMPLATE.read_text(encoding="utf-8")
    # no key-shaped blob (>=32 hex chars) and no base64-looking 40+ char run
    assert not re.search(r"\b[0-9a-fA-F]{32,}\b", text), "hex credential blob in template"
    assert not re.search(r"[A-Za-z0-9+/]{43}=", text), "base64 credential blob in template"


def test_template_pins_governance_gates():
    pairs = _parse_env_template()
    assert pairs.get("AI2_ENABLED") == "0"
    assert pairs.get("SCHEDULER_ENABLED") == "0"
    assert pairs.get("NOTIFY_ALLOW_SYNTHETIC") == "0"


def test_template_production_posture_flags():
    pairs = _parse_env_template()
    assert pairs.get("ENV") == "production"
    assert pairs.get("PRIVATE_MODE") == "1"
    assert pairs.get("COOKIE_SECURE") == "1"


def test_verbatim_template_fails_closed_in_production(monkeypatch):
    pairs = _parse_env_template()
    for key, value in pairs.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ENV", "production")
    settings = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="insecure placeholder"):
        validate_security_configuration(settings)


def test_filled_template_passes_production_validation(monkeypatch):
    pairs = dict(_parse_env_template())
    pairs["PRIVATE_PASSWORD"] = "s3cure-owner-passphrase-9f3b1c"
    pairs["API_KEY"] = "ak-owner-rotated-7c1d2e3f4a5b"
    pairs["FERNET_KEY"] = Fernet.generate_key().decode()
    for key, value in pairs.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ENV", "production")
    settings = Settings(_env_file=None)
    # must not raise: the documented install path (fill placeholders) is achievable
    validate_security_configuration(settings)
