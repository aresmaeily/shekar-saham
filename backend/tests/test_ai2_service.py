"""AI-2 Category A offline scaffold tests (mock-based, no network).

Covers: gate default-off, trust-state enforcement (missing/unavailable data),
G2 production gate, shadow execution, strict schema validation (malformed
JSON / wrong types / confidence bounds / unknown fields / item bounds),
bounded request contracts, deterministic stage-1 integration and degradation,
deterministic failure mapping (timeout / HTTP error / empty output),
provenance hashing + prompt traceability, stale-data handling, secret-free
logging, concurrency isolation, cancellation, test-transport isolation
(no accidental live/"executed" path), and the future live-gated mapping path.

AI2-C hardening additions: cancellation/late-completion containment (the
worker thread is NOT terminated by cancellation and its late result is
discarded), hash-to-payload verifiability (input snapshot and prompt hashes
rebuild from the returned artifacts), request depth/NaN rejection,
seam-contract violation handling, provenance completeness on every outcome,
exact inter-stage value transfer, and missing/whitespace/non-object output
mapping.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.services import ai2_service as ai2_module
from app.services.ai2_service import AI2Request, AI2Interpretation, AI2Service
from app.services.ai_service import build_controlled_provider_prompt

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


# ---------------------------------------------------------------------------
# Runtime G2 gate fixture (GOV-32 Phase 3C).
#
# The runtime G2 gate now guards the production seam: a real-data run
# requires the formal gate state to ALLOW. The future-path tests below
# install a fully valid PASSED gate-state fixture (matching running commit,
# approved procedure, reviewer acknowledgement, COI adjudication, and a
# verifying owner-decision document) so they continue to exercise the seam
# mapping and provenance mechanics of the future state. The denial direction
# (honest NOT_PASSED / missing / malformed / stale / contradictory /
# unverifiable, for every entry point) is covered exhaustively in
# test_g2_runtime_gate.py.
# ---------------------------------------------------------------------------

_GATE_COMMIT = "a" * 40

_VALID_OWNER_DECISION_TEXT = (
    "# OWNER G2 DECISION (fixture)\n\n"
    "G2 verdict: PASSED\n"
    "Approving authority: Project Owner (Role 1)\n"
    "Approval date (UTC): 2026-10-29\n"
    "Approval evidence / locus: convened review record\n"
)


def _gate_fixture_settings(monkeypatch, tmp_path, ai2_enabled: bool = True):
    """Install a fully valid PASSED gate-state fixture and matching settings."""
    from app.domain.g2_gate import PROCEDURE_IDENTITY, PROCEDURE_VERSION_APPROVED, sha256_text

    owner_doc = tmp_path / "OWNER_G2_DECISION_fixture.md"
    owner_doc.write_text(_VALID_OWNER_DECISION_TEXT, encoding="utf-8")
    state_doc = {
        "schema_version": "1.0.0",
        "gate": "G2",
        "verdict": "PASSED",
        "recorded_at_utc": "2026-10-29T12:00:00Z",
        "recorded_by": "owner-recorded state transition (test fixture)",
        "procedure_identity": PROCEDURE_IDENTITY,
        "procedure_version": PROCEDURE_VERSION_APPROVED,
        "reviewer_identity": "independent reviewer (fixture)",
        "reviewer_acknowledgement_utc": "2026-10-29T12:00:00Z",
        "coi_adjudication": "D-O3 recorded (fixture)",
        "convened_review_commit": _GATE_COMMIT,
        "evidence_harness_report_sha256": "1" * 64,
        "owner_decision": {
            "decision": "G2_PASSED",
            "authority": "Project Owner (Role 1)",
            "decided_at_utc": "2026-10-29T12:00:00Z",
            "decision_document": str(owner_doc),
            "decision_document_sha256": sha256_text(_VALID_OWNER_DECISION_TEXT),
        },
        "previous_state_sha256": None,
        "notes": "",
    }
    state_path = tmp_path / "G2_GATE_STATE.json"
    state_path.write_text(json.dumps(state_doc, indent=2), encoding="utf-8")
    settings = SimpleNamespace(
        ai2_enabled=ai2_enabled,
        g2_gate_state_path=str(state_path),
        runtime_commit=_GATE_COMMIT,
    )
    monkeypatch.setattr(ai2_module, "get_settings", lambda: settings)
    return settings


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
async def test_ai2_future_live_gated_path_maps_executed(monkeypatch, tmp_path):
    """Unit test for the future path: verified LIVE + G2 gate ALLOWING + seam ok.

    The trust fixture is crafted (see LiveCapableMarketService); the provider
    seam is mocked, so no network call occurs and no live data is minted.
    The runtime G2 gate (GOV-32 Phase 3C) must allow: the fixture installs a
    fully valid PASSED gate state bound to the fixture's running commit.
    """
    _gate_fixture_settings(monkeypatch, tmp_path, ai2_enabled=True)

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


# ---------------------------------------------------------------------------
# AI2-C additions: async cancellation/late-completion containment, hash-to-
# payload verifiability, bounded-input depth/NaN rejection, seam-contract
# defense, provenance completeness, exact inter-stage value transfer.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai2_cancellation_during_slow_provider_late_success_discarded(monkeypatch, _openai_env):
    """Cancellation containment: the worker thread is NOT terminated (to_thread
    cannot cancel a running thread) — it completes LATE — and the late result
    is discarded: never returned to the cancelled caller and never committed to
    any downstream state (the service singleton stays stateless)."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    started, release, done = threading.Event(), threading.Event(), threading.Event()

    def _blocking_transport(payload):
        started.set()
        release.wait(3.0)  # stays running across the caller's cancellation
        done.set()
        return {"text": json.dumps(VALID_OUTPUT)}

    svc = AI2Service()
    task = asyncio.create_task(
        svc.run(AIRequest2(), DummyMarketService(), transport=_blocking_transport)
    )
    # Yield to the loop while waiting on the threading event (a plain blocking
    # wait would starve the very task that must reach the transport).
    loop = asyncio.get_running_loop()
    assert await loop.run_in_executor(None, started.wait, 2.0)  # worker is inside transport
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Late completion happens AFTER cancellation — and is provably discarded.
    release.set()
    assert done.wait(2.0)
    assert task.cancelled()
    # No late result reached any state: the stateless singleton gained nothing.
    assert vars(svc).keys() == {"_context_builder"}  # stateless: no late result committed


@pytest.mark.asyncio
async def test_ai2_cancellation_late_provider_failure_discarded_and_reusable(monkeypatch, _openai_env):
    """A provider that fails LATE (after caller cancellation) leaves no stale
    error state: the late failure is discarded and the same service instance
    serves a fresh, correct run afterwards."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    started, release, done = threading.Event(), threading.Event(), threading.Event()

    def _late_failure_transport(payload):
        started.set()
        release.wait(3.0)
        done.set()
        raise TimeoutError("timeout")

    svc = AI2Service()
    task = asyncio.create_task(
        svc.run(AIRequest2(), DummyMarketService(), transport=_late_failure_transport)
    )
    loop = asyncio.get_running_loop()
    assert await loop.run_in_executor(None, started.wait, 2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    assert await loop.run_in_executor(None, done.wait, 2.0)  # the late failure did occur in the worker thread
    assert vars(svc).keys() == {"_context_builder"}  # stateless: no late result committed
    # Reuse: a fresh run on the same instance is unaffected by the discarded failure.
    res = await svc.run(AIRequest2(), DummyMarketService(), transport=_valid_transport)
    assert res.ok is True
    assert res.status == "executed_shadow"
    assert res.provenance.provider_error_code is None


@pytest.mark.asyncio
async def test_ai2_cancellation_before_seam_no_invocation(monkeypatch):
    """Cancellation during context building aborts the run before the provider
    seam is ever invoked (no invocation, no late payload, no partial result)."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    invoked = []

    def _spy_seam(payload, **kwargs):
        invoked.append(payload)
        return {"text": json.dumps(VALID_OUTPUT)}

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _spy_seam)

    class _SlowAnalysisMarketService(DummyMarketService):
        async def get_analysis(self, force=False):
            await asyncio.sleep(0.3)
            return None

    task = asyncio.create_task(
        AI2Service().run(AIRequest2(), _SlowAnalysisMarketService(), transport=_spy_seam)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert invoked == []


# ---------------------------------------------------------------------------
# AI2-C — deterministic-context integrity: the recorded hashes must be
# re-derivable from the exact payloads they claim to represent.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai2_input_hash_verifiable_from_returned_context(monkeypatch, _openai_env):
    """input_snapshot_sha256 is the canonical digest of the deterministic_context
    actually returned in the result — verifiable from the artifact alone."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res = await AI2Service().run(
        AIRequest2(symbol="فملی", backtest_result={"trades": [1, 2, 3]}),
        DummyMarketService(),
        transport=_valid_transport,
    )
    digest, size = AI2Service._input_digest(res.deterministic_context)
    assert digest == res.provenance.input_snapshot_sha256
    assert size > 0
    # Stable serialization: re-digesting is idempotent.
    digest_again, _ = AI2Service._input_digest(res.deterministic_context)
    assert digest_again == digest


@pytest.mark.asyncio
async def test_ai2_prompt_hash_rebuilds_from_recorded_inputs(monkeypatch, _openai_env):
    """prompt_sha256 is the exact hash of the prompt rebuilt from the recorded
    deterministic inputs (task, data_trust, stage-1 summary/observations) plus
    the request question — proving the hash represents the real prompt payload."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    req = AIRequest2(symbol="فملی", question="تحلیل وضعیت نماد")
    res = await AI2Service().run(req, DummyMarketService(), transport=_valid_transport)
    ctx = res.deterministic_context
    rebuilt = build_controlled_provider_prompt(
        {
            "task": ctx["task"],
            "data_trust": ctx["data_trust"],
            "summary": ctx["stage1"]["summary"],
            "key_observations": ctx["stage1"]["key_observations"],
        },
        question=req.question,
    )
    assert len(res.provenance.prompt_sha256) == 64
    assert hashlib.sha256(rebuilt.encode("utf-8")).hexdigest() == res.provenance.prompt_sha256


@pytest.mark.asyncio
async def test_ai2_input_hash_sensitive_to_backtest_and_question(monkeypatch, _openai_env):
    """Modified inputs change the recorded hashes (no stale-digest reuse)."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    svc = AI2Service()
    base = await svc.run(
        AIRequest2(symbol="فملی", backtest_result={"a": 1}), DummyMarketService(), transport=_valid_transport
    )
    other_backtest = await svc.run(
        AIRequest2(symbol="فملی", backtest_result={"a": 2}), DummyMarketService(), transport=_valid_transport
    )
    other_question = await svc.run(
        AIRequest2(symbol="فملی", question="سوال دیگر"), DummyMarketService(), transport=_valid_transport
    )
    assert base.provenance.input_snapshot_sha256 != other_backtest.provenance.input_snapshot_sha256
    assert base.provenance.input_snapshot_sha256 != other_question.provenance.input_snapshot_sha256
    # The question enters the prompt as well.
    assert base.provenance.prompt_sha256 != other_question.provenance.prompt_sha256


@pytest.mark.asyncio
async def test_ai2_model_output_cannot_override_deterministic_values(monkeypatch, _openai_env):
    """A schema-valid model output claiming different deterministic facts leaves
    the deterministic context bit-for-bit identical to a gated (model-free) run."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    claim = {
        "summary": "Model claims entry_score=999 and price=999999.",
        "observations": ["entry_score is 999"],
        "risks": [],
        "confidence": 0.9,
    }
    svc = AI2Service()
    req = AIRequest2(symbol="فملی")
    res_exec = await svc.run(req, DummyMarketService(), transport=lambda p: {"text": json.dumps(claim)})
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(False))
    res_gated = await svc.run(req, DummyMarketService(), transport=_valid_transport)
    assert res_exec.ok is True and res_exec.interpretation is not None
    assert res_exec.interpretation.summary.startswith("Model claims")
    assert res_exec.deterministic_context == res_gated.deterministic_context
    assert res_exec.deterministic_context["symbol_context"]["metrics"]["entry_score"] == 75
    assert res_exec.deterministic_context["stage1"]["available"] is True


@pytest.mark.asyncio
async def test_ai2_missing_symbol_context_recorded_hashed_and_prompted(monkeypatch, _openai_env):
    """Missing symbol context degrades deterministically: empty symbol_context,
    explicit warning, hashes still recorded, prompt rebuilds from the degraded
    recorded inputs."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    req = AIRequest2(symbol="نماد-غایب", question="سلام")
    res = await AI2Service().run(req, DummyMarketService(), transport=_valid_transport)
    assert res.ok is True
    assert res.deterministic_context["symbol_context"] == {}
    assert any("نماد-غایب" in w for w in res.warnings)
    assert len(res.provenance.input_snapshot_sha256) == 64
    ctx = res.deterministic_context
    rebuilt = build_controlled_provider_prompt(
        {
            "task": ctx["task"],
            "data_trust": ctx["data_trust"],
            "summary": ctx["stage1"]["summary"],
            "key_observations": ctx["stage1"]["key_observations"],
        },
        question=req.question,
    )
    assert hashlib.sha256(rebuilt.encode("utf-8")).hexdigest() == res.provenance.prompt_sha256


# ---------------------------------------------------------------------------
# AI2-C — bounded-input security: deterministic rejection of deep, non-JSON,
# and oversized request payloads (no crash, no payload echo).
# ---------------------------------------------------------------------------


def _nest(depth: int):
    value: Any = 1
    for _ in range(depth):
        value = {"a": value}
    return value


def test_ai2_request_rejects_deep_nesting():
    """Demonstrated risks contained at the contract boundary: depth-1000
    payloads crash pydantic-core serialization and ~10.9k-deep payloads overflow
    json.dumps recursion; both are now rejected deterministically at
    construction, while the depth-24 boundary is accepted."""
    assert AIRequest2(backtest_result=_nest(24)).backtest_result is not None
    for depth in (25, 100, 1000):
        with pytest.raises(ValidationError) as exc:
            AIRequest2(backtest_result=_nest(depth))
        assert "backtest_result_too_deep" in str(exc.value)
    # Wide-but-shallow structures stay legal.
    wide = {f"k{i}": [i, {"x": i}] for i in range(100)}
    assert AIRequest2(backtest_result=wide).backtest_result == wide


def test_ai2_request_rejects_non_json_values_without_payload_echo():
    """NaN/Infinity are not RFC 8259 JSON and sets are not JSON-compatible:
    all are rejected deterministically; the error text carries only the code —
    pydantic truncates the input repr, so no unbounded payload echo occurs."""
    for bad in ({"x": float("nan")}, {"x": float("inf")}, {"x": -float("inf")}, {"x": {1, 2}}):
        with pytest.raises(ValidationError) as exc:
            AIRequest2(backtest_result=bad)
        assert "backtest_result_not_json_serializable" in str(exc.value)
        assert len(str(exc.value)) < 500
    # Finite extreme floats are JSON-legal and accepted.
    req = AIRequest2(backtest_result={"hi": 1e308, "lo": -1e308})
    assert req.backtest_result["hi"] == 1e308


# ---------------------------------------------------------------------------
# AI2-C — output and provenance depth: missing/whitespace/non-object outputs,
# seam-contract violations, provenance completeness on every outcome, and
# exact inter-stage value transfer.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai2_missing_required_fields_maps_schema_error(monkeypatch, _openai_env):
    """Missing required fields (summary/confidence) map to a structured schema
    error naming the fields; no interpretation is attached."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    res_empty = await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=lambda p: {"text": "{}"}
    )
    assert res_empty.status == "failed_schema"
    assert "summary" in (res_empty.error_code or "")
    assert "confidence" in (res_empty.error_code or "")
    res_partial = await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=lambda p: {"text": json.dumps({"summary": "s"})}
    )
    assert res_partial.status == "failed_schema"
    assert "confidence" in (res_partial.error_code or "")
    assert res_partial.interpretation is None


@pytest.mark.asyncio
async def test_ai2_non_object_output_maps_schema_not_object(monkeypatch, _openai_env):
    """JSON-valid but non-object model outputs (array/string/number/null) map
    deterministically to schema_not_object."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    for text in ("[1, 2]", '"just text"', "5", "null"):
        res = await AI2Service().run(
            AIRequest2(), DummyMarketService(), transport=lambda p, t=text: {"text": t}
        )
        assert res.status == "failed_schema"
        assert res.error_code == "schema_not_object"
        assert res.interpretation is None


@pytest.mark.asyncio
async def test_ai2_whitespace_only_output_maps_empty_output(monkeypatch, _openai_env):
    """Whitespace-only output is treated as empty content (no interpretation).
    The seam itself rejects whitespace text as malformed, so this reaches the
    service only through a seam-contract stand-in (ok=True + whitespace text)."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _seam_returning(None, "   \n\t  "))
    res = await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=_valid_transport
    )
    assert res.status == "failed_schema"
    assert res.error_code == "empty_output"


@pytest.mark.asyncio
async def test_ai2_provenance_complete_on_every_outcome(monkeypatch, _openai_env, tmp_path):
    """Every outcome path carries complete provenance: input hash, timestamp,
    trust state, provider identity, gate report; prompt hash is recorded iff the
    provider prompt was actually constructed; attempts recorded on seam-reached
    paths."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    gate_keys = {
        "ai2_enabled",
        "live_verified",
        "g2_owner_acceptance",
        "g2_independent_validation",
        "provider_invocation_ready",
        "real_data_ai2_allowed",
    }
    outcomes = []

    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(False))
    outcomes.append(("ai2_disabled", await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=_spy_transport)))

    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    outcomes.append(("data_trust_unavailable", await AI2Service().run(
        AIRequest2(), DummyMarketService(trust_state="unavailable"), transport=_valid_transport)))
    outcomes.append(("trust_missing", await AI2Service().run(
        AIRequest2(), EmptyTrustMarketService(), transport=_valid_transport)))
    outcomes.append(("g2_gate", await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=None)))

    def _timeout_transport(payload):
        raise TimeoutError("timeout")

    outcomes.append(("failed_provider_timeout", await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=_timeout_transport)))
    outcomes.append(("failed_schema", await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=lambda p: {"text": "not json"})))
    outcomes.append(("executed_shadow", await AI2Service().run(
        AIRequest2(), DummyMarketService(), transport=_valid_transport)))

    def _seam_attempts(payload, **kwargs):
        return {
            "ok": True, "status": "executed", "error_code": None,
            "text": json.dumps(VALID_OUTPUT), "live_llm": False, "test_only": False,
            "requested": "openai", "attempts": 1,
        }

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _seam_attempts)
    # future_executed exercises the future production seam; the runtime G2
    # gate must be ALLOWING for that (valid PASSED gate-state fixture bound
    # to the fixture running commit — GOV-32 Phase 3C).
    _gate_fixture_settings(monkeypatch, tmp_path, ai2_enabled=True)
    outcomes.append(("future_executed", await AI2Service().run(
        AIRequest2(), LiveCapableMarketService(), transport=None)))

    prompt_not_built = {"ai2_disabled", "data_trust_unavailable", "trust_missing", "g2_gate"}
    schema_valid_expected = {"executed_shadow", "future_executed"}
    for name, res in outcomes:
        prov = res.provenance
        assert prov is not None, name
        assert len(prov.input_snapshot_sha256) == 64, name
        assert prov.created_at_utc, name
        datetime.fromisoformat(prov.created_at_utc)  # parseable UTC timestamp
        assert prov.data_trust_state, name
        assert prov.provider_mode and prov.provider_label, name
        assert gate_keys <= set(prov.gate), name
        assert (name in prompt_not_built) == (prov.prompt_sha256 == ""), name
        if name not in prompt_not_built:
            assert len(prov.prompt_sha256) == 64, name
        assert prov.schema_valid == (name in schema_valid_expected), name
        if name not in prompt_not_built:
            assert prov.provider_attempts == 1, name
        else:
            assert prov.provider_attempts is None, name
    statuses = {name: res.status for name, res in outcomes}
    assert statuses["ai2_disabled"] == "gated_not_executed"
    assert statuses["g2_gate"] == "gated_not_executed"
    assert statuses["failed_provider_timeout"] == "failed_provider"
    assert statuses["future_executed"] == "executed"


@pytest.mark.asyncio
async def test_ai2_inter_stage_values_exact(monkeypatch, _openai_env):
    """The exact values passed between stages are verified: the transport sees
    the deterministic task/trust/prompt; the interpretation carries the model
    values through unchanged."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    captured: dict[str, Any] = {}

    def _spy(payload):
        captured["payload"] = payload
        return {"text": json.dumps(VALID_OUTPUT)}

    req = AIRequest2(symbol="فملی", question="تحلیل وضعیت نماد")
    res = await AI2Service().run(req, DummyMarketService(), transport=_spy)
    payload = captured["payload"]
    assert payload["task"] == "analyst"
    # The transport receives the seam's bounded execution payload: the trust
    # STATE (not the full dict) plus the exact prompt built by AI-2.
    assert payload["data_trust_state"] == res.deterministic_context["data_trust"]["state"]
    prompt = payload["prompt"]
    assert "Task: analyst" in prompt
    assert "Data trust state: mock" in prompt
    assert "live_verified: false" in prompt
    assert req.question in prompt
    assert res.deterministic_context["stage1"]["summary"][:100] in prompt
    observations = res.deterministic_context["stage1"]["key_observations"]
    assert observations and observations[0] in prompt
    assert len(prompt) <= 2000
    # Exact model values pass through to the interpretation.
    assert res.interpretation.summary == VALID_OUTPUT["summary"]
    assert res.interpretation.confidence == 0.42
    assert res.interpretation.observations == VALID_OUTPUT["observations"]


@pytest.mark.asyncio
async def test_ai2_seam_contract_violation_non_dict_maps_failed_provider(monkeypatch, _openai_env):
    """Defense in depth: a seam returning a non-dict payload is mapped to a
    deterministic provider failure instead of crashing with AttributeError."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))
    for bad in (None, ["x"], "text"):
        monkeypatch.setattr(ai2_module, "invoke_ai_provider", lambda p, **k: bad)
        res = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_valid_transport)
        assert res.ok is False
        assert res.status == "failed_provider"
        assert res.error_code == "provider_contract_violation"
        assert res.interpretation is None
        assert res.provenance.provider_status is None
        assert any("seam contract" in w for w in res.warnings)


@pytest.mark.asyncio
async def test_ai2_provider_attempts_recorded_or_none(monkeypatch, _openai_env):
    """provider_attempts mirrors the seam's attempts contract: valid ints are
    recorded; missing or non-int values degrade to None (never a crash)."""
    monkeypatch.setattr(ai2_module, "get_settings", lambda: _settings(True))

    def _seam(payload, *, attempts="MISSING", **kwargs):
        out = {
            "ok": True, "status": "executed_test_only", "error_code": None,
            "text": json.dumps(VALID_OUTPUT), "live_llm": False, "test_only": True,
            "requested": "openai",
        }
        if attempts != "MISSING":
            out["attempts"] = attempts
        return out

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", lambda p, **k: _seam(p, attempts=3))
    res3 = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_valid_transport)
    assert res3.provenance.provider_attempts == 3

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", lambda p, **k: _seam(p, attempts="3"))
    res_bad = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_valid_transport)
    assert res_bad.provenance.provider_attempts is None

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", lambda p, **k: _seam(p))
    res_missing = await AI2Service().run(AIRequest2(), DummyMarketService(), transport=_valid_transport)
    assert res_missing.provenance.provider_attempts is None
