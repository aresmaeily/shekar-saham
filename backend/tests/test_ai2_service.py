"""AI-2 Category A offline scaffold tests (mock-based, no network).

Covers: gate default-off, trust-state enforcement (missing/unavailable data),
G2 production gate, shadow execution, strict schema validation (malformed
JSON / wrong types / confidence bounds / unknown fields / item bounds),
bounded request contracts, deterministic stage-1 integration and degradation,
deterministic failure mapping (timeout / HTTP error / empty output),
provenance hashing + prompt traceability, stale-data handling, secret-free
logging, concurrency isolation, cancellation, test-transport isolation
(no accidental live/"executed" path), and the future live-gated mapping path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

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


class EmptyTrustMarketService(DummyMarketService):
    """Market service whose trust context is missing entirely (fail-closed path)."""

    def data_trust_context(self):
        return {}


def _settings(ai2_enabled: bool):
    return SimpleNamespace(ai2_enabled=ai2_enabled)


def _valid_transport(payload):
    return {"text": json.dumps(VALID_OUTPUT)}


def _spy_transport(payload):  # pragma: no cover - must never be called
    raise AssertionError("transport must not be invoked on a gated path")


def _seam_returning(payload, text):
    """Seam stand-in returning a fixed execution dict (seam-contract shape).

    Always ok=True regardless of text — used to prove AI-2's own defensive
    handling of a seam-contract violation (ok=True with empty text)."""

    def _seam(p, **kwargs):
        return {
            "ok": True,
            "status": "executed_test_only",
            "error_code": None,
            "text": text,
            "live_llm": False,
            "test_only": True,
            "requested": "openai",
            "attempts": 1,
        }

    return _seam


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
    # Prompt content (question text, stage-1 summary) is never logged either.
    assert "سلام" not in caplog.text
    assert "بازار فعلی" not in caplog.text
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


# ---------------------------------------------------------------------------
# AI2-B additions: bounded contracts, stage-1 integration, trust-state gate,
# provenance traceability, isolation, concurrency, cancellation.
# ---------------------------------------------------------------------------


def test_ai2_request_bounds_enforced():
    """Bounded request contract: oversized fields are rejected at construction."""
    with pytest.raises(ValidationError):
        AIRequest2(question="x" * 2001)
    with pytest.raises(ValidationError):
        AIRequest2(symbol="x" * 65)
    with pytest.raises(ValidationError):
        AIRequest2(language="x" * 17)
    with pytest.raises(ValidationError):
        AIRequest2(backtest_result={"blob": "y" * 70000})
    with pytest.raises(ValidationError):
        AIRequest2(backtest_result={"a": object()})  # not JSON-serializable
    # Boundary values are accepted.
    req = AIRequest2(question="x" * 2000, symbol="x" * 64, language="fa")
    assert req.question == "x" * 2000


@pytest.mark.asyncio
async def test_ai2_interpretation_rejects_unknown_fields(monkeypatch, _openai_env):
    """extra="forbid": model-emitted unspecified fields fail the schema, and
    model output can never mutate the deterministic context or provenance."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    smuggled = dict(VALID_OUTPUT, price=999, data_trust={"state": "live", "live_verified": True})
    res = await AI2Service().run(
        AIRequest2(symbol="فملی"),
        DummyMarketService(),
        transport=lambda p: {"text": json.dumps(smuggled)},
    )
    assert res.ok is False
    assert res.status == "failed_schema"
    assert "price" in (res.error_code or "")
    assert res.interpretation is None
    # Deterministic context is untouched: trust state stays "mock", no price.
    assert res.deterministic_context["data_trust"]["state"] == "mock"
    assert "price" not in json.dumps(res.deterministic_context)


@pytest.mark.asyncio
async def test_ai2_boundary_limits_accepted(monkeypatch, _openai_env):
    """Schema boundaries: max-length summary/items and extreme confidence pass."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    at_limit = {
        "summary": "x" * 2000,
        "observations": ["o" * 500],
        "risks": ["r" * 500],
        "confidence": 1.0,
    }
    res = await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=lambda p: {"text": json.dumps(at_limit)}
    )
    assert res.ok is True
    assert res.status == "executed_shadow"
    assert res.provenance.schema_valid is True
    # One char over the item bound fails the schema.
    over = dict(at_limit, observations=["o" * 501])
    res_over = await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=lambda p: {"text": json.dumps(over)}
    )
    assert res_over.status == "failed_schema"
    assert "observations" in (res_over.error_code or "")


@pytest.mark.asyncio
async def test_ai2_stage1_present_traceable_and_idempotent(monkeypatch, _openai_env):
    """Stage-1 deterministic analysis is attached, hashed into the snapshot and
    the prompt, and identical across repeated identical runs (idempotency)."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    svc = AI2Service()
    res_a = await svc.run(AIRequest2(symbol="فملی"), DummyMarketService(), transport=_valid_transport)
    res_b = await svc.run(AIRequest2(symbol="فملی"), DummyMarketService(), transport=_valid_transport)
    for res in (res_a, res_b):
        stage1 = res.deterministic_context["stage1"]
        assert stage1["available"] is True
        assert stage1["summary"]
        assert isinstance(stage1["key_observations"], list)
        assert len(res.provenance.prompt_sha256) == 64
    assert res_a.deterministic_context["stage1"] == res_b.deterministic_context["stage1"]
    assert res_a.provenance.prompt_sha256 == res_b.provenance.prompt_sha256
    # The prompt hash differs from the input snapshot hash (distinct artifacts).
    assert res_a.provenance.prompt_sha256 != res_a.provenance.input_snapshot_sha256


@pytest.mark.asyncio
async def test_ai2_stage1_failure_degrades_deterministically(monkeypatch, _openai_env):
    """Stage-1 failure is recorded, warned, and never blocks the run or raises."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))

    def _boom(self, ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(ai2_module.FallbackAIProvider, "analyst", _boom)
    res = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_valid_transport)
    stage1 = res.deterministic_context["stage1"]
    assert stage1["available"] is False
    assert stage1["error_code"] == "stage1_unavailable:RuntimeError"
    assert any("stage-1" in w for w in res.warnings)
    # The run still completes the interpretation path (degraded, not broken).
    assert res.status == "executed_shadow"
    assert len(res.provenance.prompt_sha256) == 64


@pytest.mark.asyncio
async def test_ai2_unavailable_data_gated_fail_closed(monkeypatch):
    """Trust-state gate: unavailable data refuses execution before the seam."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    invoked = []

    def _spy_seam(payload, **kwargs):
        invoked.append(payload)
        raise AssertionError("provider seam must not run on unavailable data")

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _spy_seam)
    res = await AI2Service().run(
        AIRequest2(), DummyMarketService(trust_state="unavailable"), transport=_valid_transport
    )
    assert res.ok is False
    assert res.status == "gated_not_executed"
    assert res.error_code == "data_trust_unavailable"
    assert res.provenance.data_trust_state == "unavailable"
    assert invoked == []


@pytest.mark.asyncio
async def test_ai2_missing_trust_state_gated(monkeypatch):
    """A market service with no trust context at all is refused (fail-closed)."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res = await AI2Service().run(AIRequest2(), EmptyTrustMarketService(), transport=_valid_transport)
    assert res.status == "gated_not_executed"
    assert res.error_code == "data_trust_unavailable"
    assert res.provenance.data_trust_state == "unknown"


@pytest.mark.asyncio
async def test_ai2_test_transport_never_yields_executed_status(monkeypatch, _openai_env):
    """Test-transport isolation: an injected transport can only ever produce
    executed_shadow — the "executed" status is unreachable with mock output."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_valid_transport)
    assert res.status != "executed"
    assert res.status == "executed_shadow"
    assert res.provenance.test_only_transport is True
    assert res.provenance.live_verified is False
    assert any("TEST ONLY" in w for w in res.warnings)


@pytest.mark.asyncio
async def test_ai2_empty_output_from_ok_seam_maps_failed_schema(monkeypatch, _openai_env):
    """Defense in depth: a seam-contract violation (ok=True with empty text)
    maps deterministically to failed_schema/empty_output, never to a result."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _seam_returning(None, ""))
    res = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_valid_transport)
    assert res.ok is False
    assert res.status == "failed_schema"
    assert res.error_code == "empty_output"
    assert res.interpretation is None


@pytest.mark.asyncio
async def test_ai2_concurrent_runs_isolated(monkeypatch, _openai_env):
    """Concurrency: two runs on the shared singleton do not cross-contaminate."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res_a, res_b = await asyncio.gather(
        ai2_module.ai2_service.run(
            AIRequest2(symbol="فملی"), DummyMarketService(), transport=_valid_transport
        ),
        ai2_module.ai2_service.run(
            AIRequest2(symbol="وبملت"), DummyMarketService(), transport=_valid_transport
        ),
    )
    assert res_a.status == res_b.status == "executed_shadow"
    assert res_a.provenance.input_snapshot_sha256 != res_b.provenance.input_snapshot_sha256
    assert res_a.deterministic_context["symbol_context"]["snapshot"]["l18"] == "فملی"
    # The mock only serves فملی: the second run must see its OWN empty symbol
    # context + its own insufficient-data warning (no cross-contamination).
    assert res_b.deterministic_context["symbol_context"] == {}
    assert any("وبملت" in w for w in res_b.warnings)
    assert not any("وبملت" in w for w in res_a.warnings)


@pytest.mark.asyncio
async def test_ai2_cancellation_propagates_no_fabricated_result(monkeypatch, _openai_env):
    """Cancellation of the awaiting caller propagates; no result is fabricated."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))

    def _slow_transport(payload):
        time.sleep(0.5)
        return {"text": json.dumps(VALID_OUTPUT)}

    task = asyncio.create_task(
        AI2Service().run(AIRequest2(), DummyMarketService(), transport=_slow_transport)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

