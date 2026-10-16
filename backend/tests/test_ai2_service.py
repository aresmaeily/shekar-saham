"""AI-2 Category A offline scaffold tests (mock-based, no network).

Covers: gate default-off, G2 production gate, shadow execution, strict schema
validation (malformed JSON / wrong types / confidence bounds), deterministic
failure mapping (timeout / HTTP error), provenance hashing, stale-data
handling, secret-free logging, and the future live-gated mapping path.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from app.services import ai2_service as ai2_module
from app.services.ai2_service import AI2Request, AI2Interpretation, AI2Service

# Short alias used throughout the tests below.
AIRequest2 = AI2Request


VALID_OUTPUT = {
    "summary": "Structured second-stage interpretation of deterministic context.",
    "observations": ["Entry score is elevated.", "Buy power above threshold."],
    "risks": ["Data trust is not independently verified."],
    "confidence": 0.42,
}


class DummyMarketService:
    """Same convention as tests/test_ai_service.py DummyMarketService."""

    def __init__(self, trust_state: str = "mock"):
        self._data_trust = {
            "state": trust_state,
            "trust_level": "synthetic" if trust_state in {"mock", "synthetic"} else "mixed",
            "source": "mock_fallback",
            "provider": "mock_fallback",
            "is_live": False,
            "live_verified": False,
            "is_generated": trust_state in {"mock", "synthetic"},
            "warning": f"{trust_state.upper()} data",
        }

    async def get_analysis(self, force=False):
        return None

    def status(self):
        return {"source": "mock_fallback", "trust_level": "synthetic", "symbol_count": 1}

    def data_trust_context(self):
        return self._data_trust

    def get_symbol(self, symbol):
        if symbol != "فملی":
            return None
        return {
            "snapshot": {"l18": "فملی", "pl": 1000, "plp": -1.5},
            "metrics": {"entry_score": 75, "exit_score": 20, "buy_power": 2.1},
            "tablocastic": {"grade": "A"},
            "data_trust": self._data_trust,
        }

    def run_user_filter(self, expr, limit=10):
        return {"ok": True, "count": 1, "rows": [], "data_trust": self._data_trust}


class LiveCapableMarketService(DummyMarketService):
    """Crafted trust dict for the future live-gated path unit test only.

    This proves the gate mapping; it does NOT mint live data anywhere in the
    product: build_data_trust_context can never produce this shape today.
    """

    def __init__(self):
        super().__init__()
        self._data_trust = {
            "state": "live",
            "trust_level": "live",
            "source": "tsetmc",
            "provider": "tsetmc",
            "is_live": True,
            "live_verified": True,
            "is_generated": False,
            "warning": "",
        }


def _settings(ai2_enabled: bool):
    return SimpleNamespace(ai2_enabled=ai2_enabled)


def _valid_transport(payload):
    return {"text": json.dumps(VALID_OUTPUT)}


def _spy_transport(payload):  # pragma: no cover - must never be called
    raise AssertionError("transport must not be invoked on a gated path")


@pytest.fixture
def _openai_env(monkeypatch):
    """Configure an external provider so the seam passes its fallback/credential
    checks and reaches the injected test transport (same convention as the
    P3.83 provider-execution tests). No network occurs: transport is mocked."""
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "unit-test-key")


@pytest.mark.asyncio
async def test_ai2_disabled_by_default_gates_before_transport(monkeypatch):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(False))
    invoked = []

    def _spy_seam(payload, **kwargs):
        invoked.append(payload)
        raise AssertionError("provider seam must not be reached while disabled")

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _spy_seam)
    res = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_spy_transport)
    assert res.ok is False
    assert res.status == "gated_not_executed"
    assert res.error_code == "ai2_disabled"
    assert res.safety["no_auto_trading"] is True
    assert invoked == []


@pytest.mark.asyncio
async def test_ai2_production_path_blocked_by_g2_gate(monkeypatch):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    invoked = []

    def _spy_seam(payload, **kwargs):
        invoked.append(payload)
        raise AssertionError("real-data AI-2 must not reach the provider seam")

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _spy_seam)
    res = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=None)
    assert res.status == "gated_not_executed"
    assert res.error_code == "g2_independent_validation_required"
    assert res.provenance.gate["g2_independent_validation"] == "NOT_PASSED"
    assert res.provenance.gate["real_data_ai2_allowed"] is False
    assert res.provenance.live_verified is False
    assert invoked == []


@pytest.mark.asyncio
async def test_ai2_shadow_execution_with_valid_schema(monkeypatch, _openai_env):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res = await AI2Service().run(
        AIRequest2(symbol="فملی"), DummyMarketService(), transport=_valid_transport
    )
    assert res.ok is True
    assert res.status == "executed_shadow"
    assert res.interpretation is not None
    assert isinstance(res.interpretation, AI2Interpretation)
    assert res.interpretation.summary == VALID_OUTPUT["summary"]
    assert res.provenance.schema_valid is True
    assert res.provenance.test_only_transport is True
    assert res.provenance.live_verified is False
    # Deterministic context is domain-owned and present alongside interpretation.
    assert res.deterministic_context["symbol_context"]["snapshot"]["l18"] == "فملی"


@pytest.mark.asyncio
async def test_ai2_schema_rejects_malformed_json(monkeypatch, _openai_env):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res = await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=lambda p: {"text": "not json at all"}
    )
    assert res.ok is False
    assert res.status == "failed_schema"
    assert res.error_code == "invalid_json"
    assert res.interpretation is None


@pytest.mark.asyncio
async def test_ai2_schema_rejects_wrong_types(monkeypatch, _openai_env):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res = await AI2Service().run(
        AIRequest2(),
        DummyMarketService(),
        transport=lambda p: {"text": json.dumps({"summary": 12345, "confidence": "high"})},
    )
    assert res.ok is False
    assert res.status == "failed_schema"
    assert res.error_code and res.error_code.startswith("schema_validation_failed")


@pytest.mark.asyncio
async def test_ai2_confidence_bounds_enforced(monkeypatch, _openai_env):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    bad = dict(VALID_OUTPUT, confidence=1.5)
    res = await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=lambda p: {"text": json.dumps(bad)}
    )
    assert res.status == "failed_schema"
    assert "confidence" in (res.error_code or "")


@pytest.mark.asyncio
async def test_ai2_timeout_maps_deterministically(monkeypatch, _openai_env):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))

    def _timeout_transport(payload):
        raise TimeoutError("timeout")

    res = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_timeout_transport)
    assert res.ok is False
    assert res.status == "failed_provider"
    assert res.error_code == "timeout"
    assert res.provenance.provider_status == "timeout"


@pytest.mark.asyncio
async def test_ai2_http_4xx_no_retry(monkeypatch, _openai_env):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))

    def _http_error_transport(payload):
        exc = RuntimeError("http_403")
        exc.status_code = 403  # type: ignore[attr-defined]
        raise exc

    res = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_http_error_transport)
    assert res.ok is False
    assert res.status == "failed_provider"
    assert res.provenance.provider_status == "http_error"
    assert res.provenance.provider_error_code == "http_403"


@pytest.mark.asyncio
async def test_ai2_provenance_hash_deterministic_and_sensitive_to_input(monkeypatch, _openai_env):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    svc = AI2Service()
    res_a1 = await svc.run(AIRequest2(symbol="فملی"), DummyMarketService(), transport=_valid_transport)
    res_a2 = await svc.run(AIRequest2(symbol="فملی"), DummyMarketService(), transport=_valid_transport)
    res_b = await svc.run(AIRequest2(symbol="وبملت"), DummyMarketService(), transport=_valid_transport)
    assert res_a1.provenance.input_snapshot_sha256 == res_a2.provenance.input_snapshot_sha256
    assert res_a1.provenance.input_snapshot_sha256 != res_b.provenance.input_snapshot_sha256
    assert len(res_a1.provenance.input_snapshot_sha256) == 64


@pytest.mark.asyncio
async def test_ai2_stale_data_recorded_and_warned(monkeypatch, _openai_env):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res = await AI2Service().run(
        AIRequest2(), DummyMarketService(trust_state="stale"), transport=_valid_transport
    )
    assert res.provenance.data_trust_state == "stale"
    assert any("قدیمی" in w or "stale" in w.lower() for w in res.warnings)


@pytest.mark.asyncio
async def test_ai2_no_secret_material_in_result_or_logs(monkeypatch, caplog):
    secret = "super-secret-ai2-key-987"
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", secret)
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    with caplog.at_level(logging.INFO, logger="shekar.ai2"):
        res = await AI2Service().run(
            AIRequest2(question="سلام"), DummyMarketService(), transport=_valid_transport
        )
    assert res.status == "executed_shadow"
    serialized = res.model_dump_json()
    assert secret not in serialized
    assert secret not in caplog.text
    assert res.provenance.provider_mode in {"fallback", "external_not_configured"}


@pytest.mark.asyncio
async def test_ai2_future_live_gated_path_maps_executed(monkeypatch):
    """Unit test for the future path: verified LIVE + gates open + seam ok.

    The trust fixture is crafted (see LiveCapableMarketService); the provider
    seam is mocked, so no network call occurs and no live data is minted.
    """
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))

    def _seam_ok(payload, **kwargs):
        return {
            "ok": True,
            "status": "executed",
            "error_code": None,
            "text": json.dumps(VALID_OUTPUT),
            "live_llm": False,
            "test_only": False,
            "requested": "openai",
            "attempts": 1,
        }

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _seam_ok)
    res = await AI2Service().run(AIRequest2(), LiveCapableMarketService(), transport=None)
    assert res.ok is True
    assert res.status == "executed"
    assert res.interpretation is not None
    assert res.provenance.live_verified is True
    assert res.provenance.test_only_transport is False

